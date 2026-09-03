from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from apps.etudiants.models import Etudiant
from apps.paiements.models import TranchePaiement, RecuPaiement
from apps.paiements.services import calculer_penalites_etudiant


class Command(BaseCommand):
    help = "Gère les rappels d'échéances (2 semaines avant) et les relances hebdomadaires de retard de scolarité dans le Dashboard et par Email/WhatsApp."

    def handle(self, *args, **options):
        aujourdhui = date.today()
        etudiants = Etudiant.objects.filter(statut__in=['PREINSCRIT', 'INSCRIT', 'ACTIF']).select_related('annee_academique', 'utilisateur')
        
        compteur_preventifs = 0
        compteur_retards = 0
        compteur_emails = 0

        self.stdout.write("Traitement des échéanciers et relances de paiement...")

        for etudiant in etudiants:
            annee_code = etudiant.annee_academique.code if etudiant.annee_academique else "2024-2025"
            tranches = TranchePaiement.objects.filter(annee_academique=annee_code, est_actif=True).order_by('numero')
            
            # --- 1. RAPPELS PRÉVENTIFS (2 semaines / 14 jours avant l'échéance) ---
            echeances_imminentes = []
            for tranche in tranches:
                # Vérifier si la tranche est réglée/validée
                recu_valide = False
                if tranche.numero == 1 and etudiant.recu_preinscription_valide:
                    recu_valide = True
                else:
                    recu = RecuPaiement.objects.filter(etudiant=etudiant, tranche=tranche, statut='VALIDE').first()
                    if recu:
                        recu_valide = True

                if not recu_valide and tranche.date_limite >= aujourdhui:
                    jours_restants = (tranche.date_limite - aujourdhui).days
                    if jours_restants <= 14:
                        echeances_imminentes.append({
                            'tranche': tranche,
                            'jours_restants': jours_restants,
                            'date_limite': tranche.date_limite,
                            'montant': tranche.montant
                        })

            if echeances_imminentes and etudiant.utilisateur:
                from apps.tableau_bord.models import Notification
                for ech in echeances_imminentes:
                    compteur_preventifs += 1
                    titre_preventif = f"Rappel Échéance : {ech['tranche'].get_numero_display()}"
                    msg_preventif = (
                        f"Attention : La date limite pour le règlement de la {ech['tranche'].get_numero_display()} "
                        f"({ech['montant']:,} FCFA) approche. Échéance dans {ech['jours_restants']} jour(s) ({ech['date_limite'].strftime('%d/%m/%Y')})."
                    )
                    
                    notif, created = Notification.objects.get_or_create(
                        utilisateur=etudiant.utilisateur,
                        titre=titre_preventif,
                        defaults={
                            'type': 'INFO',
                            'message': msg_preventif,
                            'lien': '/inscriptions/'
                        }
                    )
                    if not created and notif.message != msg_preventif:
                        notif.message = msg_preventif
                        notif.save()

            # --- 2. RAPPELS HEBDOMADAIRES DE RETARD & PÉNALITÉS ---
            penalites_info = calculer_penalites_etudiant(etudiant)
            
            if penalites_info['total_global'] > 0:
                compteur_retards += 1
                
                if etudiant.utilisateur:
                    from apps.tableau_bord.models import Notification
                    from django.utils import timezone
                    
                    notifs_existantes = {
                        n.titre: n for n in Notification.objects.filter(
                            utilisateur=etudiant.utilisateur,
                            type='WARNING',
                            est_lue=False
                        )
                    }
                    
                    tranches_en_retard = set()
                    
                    for detail in penalites_info.get('details', []):
                        nom_tranche = detail['tranche']
                        tranches_en_retard.add(nom_tranche)
                        titre_notif = f"Retard de paiement - {nom_tranche}"
                        message_notif = (
                            f"Vous avez accumulé {detail['montant']:,} FCFA de pénalités pour la {nom_tranche} "
                            f"({detail['semaines_retard']} semaine(s) de retard). "
                            f"Date limite dépassée depuis le {detail['date_limite'].strftime('%d/%m/%Y')}."
                        )
                        
                        if titre_notif in notifs_existantes:
                            notif = notifs_existantes[titre_notif]
                            if notif.message != message_notif:
                                notif.message = message_notif
                                notif.save()
                        else:
                            Notification.objects.create(
                                utilisateur=etudiant.utilisateur,
                                type='WARNING',
                                titre=titre_notif,
                                message=message_notif,
                                lien='/inscriptions/'
                            )
                    
                    for titre, notif in notifs_existantes.items():
                        if titre.startswith("Retard de paiement - "):
                            nom_tranche = titre.replace("Retard de paiement - ", "")
                            if nom_tranche not in tranches_en_retard:
                                notif.est_lue = True
                                notif.date_lecture = timezone.now()
                                notif.save()
                
                # --- ENVOI DES EMAILS ET WHATSAPP ---
                destinataire = etudiant.email or (etudiant.utilisateur.email if etudiant.utilisateur else None)
                
                if destinataire:
                    try:
                        context = {
                            'etudiant': etudiant,
                            'penalites_info': penalites_info,
                            'echeances_imminentes': echeances_imminentes,
                            'site_url': getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
                        }
                        html_message = render_to_string('paiements/emails/rappel_penalites.html', context)
                        plain_message = strip_tags(html_message)
                        
                        sujet = f"{getattr(settings, 'EMAIL_SUBJECT_PREFIX', '[IAI-Cameroun] ')}Rappel d'Échéancier & Relance de Scolarité"
                        
                        # Destinataires (Étudiant + Tuteur en copie si présent)
                        recipients = [destinataire]
                        if getattr(etudiant, 'email_tuteur', None):
                            recipients.append(etudiant.email_tuteur)

                        send_mail(
                            subject=sujet,
                            message=plain_message,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=recipients,
                            html_message=html_message,
                            fail_silently=False
                        )
                        compteur_emails += len(recipients)
                        self.stdout.write(
                            self.style.SUCCESS(f"Rappel envoyé par e-mail à {etudiant.get_nom_complet()} ({', '.join(recipients)})")
                        )

                        # Envoi de la notification WhatsApp
                        try:
                            from apps.tableau_bord.whatsapp_service import WhatsAppService
                            whatsapp_details = []
                            for detail in penalites_info.get('details', []):
                                whatsapp_details.append(
                                    f"• *{detail['tranche']}* : {detail['montant']:,} FCFA ({detail['semaines_retard']} sem. de retard, limite : {detail['date_limite'].strftime('%d/%m/%Y')})"
                                )
                            details_str = "\n".join(whatsapp_details)
                            site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
                            
                            msg_whatsapp = (
                                f"*IAI-CAMEROUN (Douala)* 🎓\n"
                                f"*Relance Hebdomadaire - Scolarité & Pénalités*\n\n"
                                f"Bonjour {etudiant.prenom} {etudiant.nom},\n\n"
                                f"Notre système a répertorié un retard dans vos tranches de scolarité.\n\n"
                                f"*Détails de votre situation :*\n"
                                f"{details_str}\n\n"
                                f"*Total des pénalités :* {penalites_info['total']:,} FCFA\n\n"
                                f"Veuillez régulariser votre situation sur votre espace étudiant :\n"
                                f"{site_url}/paiements/payer-penalites/\n\n"
                                f"_Administration IAI-Cameroun (Douala)._"
                            )
                            
                            tel = etudiant.telephone or (getattr(etudiant.utilisateur, 'telephone', '') if etudiant.utilisateur else '')
                            if tel:
                                WhatsAppService.envoyer_message(tel, msg_whatsapp)
                        except Exception as wa_err:
                            self.stdout.write(self.style.ERROR(f"Erreur WhatsApp ({etudiant.get_nom_complet()}): {wa_err}"))

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Échec de l'envoi de l'e-mail ({etudiant.get_nom_complet()}): {e}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Traitement des échéanciers terminé. Rappels préventifs : {compteur_preventifs}, Relances de retard : {compteur_retards}, E-mails envoyés : {compteur_emails}"
            )
        )
