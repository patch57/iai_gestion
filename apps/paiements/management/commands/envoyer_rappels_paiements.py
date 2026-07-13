from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from apps.etudiants.models import Etudiant
from apps.paiements.services import calculer_penalites_etudiant


class Command(BaseCommand):
    help = "Calcule et envoie par e-mail les pénalités de retard accumulées aux étudiants insolvables."

    def handle(self, *args, **options):
        # Récupérer les étudiants actifs
        etudiants = Etudiant.objects.filter(statut__in=['PREINSCRIT', 'INSCRIT', 'ACTIF']).select_related('annee_academique', 'utilisateur')
        
        compteur_insolvables = 0
        compteur_emails_envoyes = 0

        self.stdout.write("Analyse des retards de paiement en cours...")

        for etudiant in etudiants:
            # Calculer les pénalités
            penalites_info = calculer_penalites_etudiant(etudiant)
            
            if penalites_info['total'] > 0:
                compteur_insolvables += 1
                
                # Vérifier si l'étudiant a un e-mail valide
                destinataire = etudiant.email
                if not destinataire and etudiant.utilisateur:
                    destinataire = etudiant.utilisateur.email
                
                if destinataire:
                    try:
                        # Rendu du template HTML de courriel
                        context = {
                            'etudiant': etudiant,
                            'penalites_info': penalites_info,
                            'site_url': getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
                        }
                        html_message = render_to_string('paiements/emails/rappel_penalites.html', context)
                        plain_message = strip_tags(html_message)
                        
                        # Sujet du mail
                        sujet = f"{getattr(settings, 'EMAIL_SUBJECT_PREFIX', '[IAI-Cameroun] ')}Rappel : Frais de Scolarité et Pénalités"
                        
                        # Envoi de l'e-mail
                        send_mail(
                            subject=sujet,
                            message=plain_message,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[destinataire],
                            html_message=html_message,
                            fail_silently=False
                        )
                        compteur_emails_envoyes += 1
                        self.stdout.write(
                            self.style.SUCCESS(f"E-mail de rappel envoyé à {etudiant.get_nom_complet()} ({destinataire}) - Pénalités : {penalites_info['total']} FCFA")
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"Échec de l'envoi de l'e-mail à {etudiant.get_nom_complet()} ({destinataire}) : {str(e)}")
                        )
                else:
                    self.stdout.write(
                        self.style.WARNING(f"Aucune adresse e-mail trouvée pour {etudiant.get_nom_complet()}")
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Analyse terminée. Étudiants insolvables détectés : {compteur_insolvables}, E-mails envoyés : {compteur_emails_envoyes}"
            )
        )
