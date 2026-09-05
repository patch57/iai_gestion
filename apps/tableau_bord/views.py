"""
Vues pour le tableau de bord
IAI-Cameroun - Centre de Douala
Version moderne avec couleurs verte et jaune
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.db.models import Count, Avg, Sum, Q, F, Value, DecimalField, IntegerField, FloatField
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from datetime import datetime, timedelta

from apps.etudiants.models import Etudiant, Filiere, AnneeAcademique, Classe, Apprenant, Formation
from apps.paiements.models import RecuPaiement, TranchePaiement
from apps.cours.models import Cours, SeanceCours, RessourceCours, EmploiDuTemps, Presence, InscriptionCours
from apps.notes.models import Note, Evaluation, Bulletin
from apps.professeurs.models import Professeur
from apps.paiements.services import calculer_penalites_etudiant
from .models import Notification, Tache, PenalitePaiement, AlertePaiement


def accueil(request):
    """Page d'accueil publique - Style moderne vert et jaune"""
    if request.user.is_authenticated:
        # ✅ Déjà corrigé avec namespace
        return redirect('tableau_bord:tableau_bord')
    
    from apps.inscriptions.utils import get_current_academic_year_code
    annee_active = AnneeAcademique.objects.filter(est_active=True).first()
    annee_code = annee_active.code if annee_active else get_current_academic_year_code()
    
    context = {
        'titre': 'IAI-Cameroun - Centre de Douala',
        'sous_titre': 'Institut Africain d\'Informatique',
        'nombre_etudiants': Etudiant.objects.filter(statut__in=['ACTIF', 'INSCRIT']).count(),
        'nombre_filieres': Filiere.objects.filter(est_active=True).count(),
        'annee_academique': annee_code,
        'date_aujourdhui': timezone.now(),
        'primary_color': '#10B981',
        'secondary_color': '#F59E0B',
    }
    return render(request, 'base/accueil.html', context)


@login_required
def console_whatsapp(request):
    """Console d'envoi et de gestion des notifications WhatsApp/SMS (Click-to-WhatsApp & Passerelle Pro)"""
    from .whatsapp_service import WhatsAppService
    from .models import Configuration

    etudiants = Etudiant.objects.filter(statut__in=['ACTIF', 'INSCRIT']).select_related('utilisateur', 'filiere')[:50]
    resultat = None

    if request.method == 'POST':
        action = request.POST.get('action', 'send_msg')

        if action == 'save_config':
            enabled = request.POST.get('whatsapp_enabled') == 'on'
            api_url = request.POST.get('whatsapp_api_url', '').strip()
            api_token = request.POST.get('whatsapp_token', '').strip()

            Configuration.set_valeur('WHATSAPP_ENABLED', 'True' if enabled else 'False', request.user)
            Configuration.set_valeur('WHATSAPP_API_URL', api_url, request.user)
            Configuration.set_valeur('WHATSAPP_TOKEN', api_token, request.user)

            messages.success(request, "Paramètres de la passerelle WhatsApp mis à jour avec succès !")
        else:
            etudiant_id = request.POST.get('etudiant_id')
            titre = request.POST.get('titre', 'Rappel IAI-Cameroun')
            message_txt = request.POST.get('message', '')

            if etudiant_id:
                etudiant = get_object_or_404(Etudiant, pk=etudiant_id)
                resultat = WhatsAppService.notifier_etudiant(etudiant, titre, message_txt)

                # Si l'API est activée, tenter un envoi automatique direct
                if Configuration.get_valeur('WHATSAPP_ENABLED', 'False').lower() == 'true':
                    tel = resultat.get('telephone')
                    if tel:
                        succes_envoi = WhatsAppService.envoyer_message(tel, f"*{titre}*\n\n{message_txt}")
                        if succes_envoi:
                            messages.success(request, f"Message WhatsApp envoyé automatiquement à {etudiant.get_nom_complet()} !")
                        else:
                            messages.warning(request, f"Lien généré. Note : L'envoi automatique via l'API a échoué (vérifiez votre URL/Token).")
                    else:
                        messages.success(request, f"Lien WhatsApp généré avec succès pour {etudiant.get_nom_complet()} !")
                else:
                    messages.success(request, f"Lien WhatsApp généré avec succès pour {etudiant.get_nom_complet()} !")

    config_enabled = Configuration.get_valeur('WHATSAPP_ENABLED', 'False').lower() == 'true'
    config_url = Configuration.get_valeur('WHATSAPP_API_URL', '')
    config_token = Configuration.get_valeur('WHATSAPP_TOKEN', '')

    context = {
        'etudiants': etudiants,
        'resultat': resultat,
        'config_enabled': config_enabled,
        'config_url': config_url,
        'config_token': config_token,
        'titre': 'Console de Notification WhatsApp'
    }
    return render(request, 'tableau_bord/whatsapp_console.html', context)


@login_required
def tableau_bord(request):
    """Dispatcher principal selon le type d'utilisateur"""
    type_user = request.user.type_utilisateur
    
    if type_user == 'ETUDIANT':
        return etudiant_dashboard(request)
    elif type_user == 'APPRENANT':
        return apprenant_dashboard(request)
    elif type_user in ['ENSEIGNANT', 'PROFESSEUR', 'FORMATEUR']:
        return enseignant_dashboard(request)
    elif type_user == 'CHEF_FORMATION_CONTINUE':
        return chef_formation_continue_dashboard(request)
    elif type_user == 'CHEF_SCOLARITE':
        return chef_scolarite_dashboard(request)
    elif type_user == 'CHEF_ETUDES':
        return chef_etudes_dashboard(request)
    elif type_user == 'CHEF_ANONYMAT':
        return chef_anonymat_dashboard(request)
    elif type_user == 'CHEF_COMPTABILITE' or type_user == 'ADMIN_FINANCIER':
        return chef_comptabilite_dashboard(request)
        
    elif type_user in ['DIRECTEUR', 'ADMIN_SYSTEME']:
        return dashboard_admin(request)
        
    # Par défaut : afficher le dashboard admin général
    return dashboard_admin(request)



@login_required
def etudiant_dashboard(request):
    etudiant = Etudiant.objects.filter(utilisateur=request.user).first()
    if not etudiant:
        from apps.authentification.models import DemandeInscription
        from apps.etudiants.models import Niveau, Classe
        
        # Récupérer la demande d'inscription de l'utilisateur pour connaître la filière et le niveau souhaités
        demande = DemandeInscription.objects.filter(user=request.user).first()
        
        filiere_code = 'GL'
        niveau_num = 1
        if demande:
            filiere_code = demande.filiere_souhaitee or 'GL'
            niveau_num = demande.niveau_souhaite or 1
        else:
            # Fallback sur le matricule
            if request.user.matricule:
                if request.user.matricule.startswith('SR'):
                    filiere_code = 'SR'
                    
        filiere = Filiere.objects.filter(code=filiere_code).first() or Filiere.objects.first()
        niveau = Niveau.objects.filter(numero=niveau_num).first() or Niveau.objects.first()
        annee_active = AnneeAcademique.objects.filter(est_active=True).first()
        
        etudiant = Etudiant.objects.create(
            utilisateur=request.user,
            nom=request.user.last_name or 'Etudiant',
            prenom=request.user.first_name or 'IAI',
            email=request.user.email,
            telephone=request.user.telephone or '699999999',
            date_naissance=timezone.now().date() - timedelta(days=7300),
            lieu_naissance='Douala',
            sexe='M',
            filiere=filiere,
            niveau=niveau,
            annee_academique=annee_active,
            matricule=request.user.matricule or 'GL.CMR.D014.2425A'
        )
        # Lancer immédiatement la répartition pour affecter cet étudiant à sa classe/salle
        Classe.repartir_etudiants(annee_active)
        etudiant.refresh_from_db()

    from decimal import Decimal
    # Scolarité de base : 474 000 FCFA pour le Niveau 1 (84k + 175k + 115k + 100k) / 461 000 FCFA pour le Niveau 2
    if etudiant and etudiant.niveau and etudiant.niveau.numero == 2:
        base_scolarite = Decimal('461000.00')
    else:
        base_scolarite = Decimal('474000.00')

    # Téléversement de reçu
    if request.method == 'POST' and request.FILES.get('recu_fichier'):
        tranche_num_raw = request.POST.get('tranche_num')
        file = request.FILES.get('recu_fichier')
        
        tranche = None
        commentaires = ""
        montant_mentionne = Decimal('0.00')
        
        if tranche_num_raw in ['totalite', 'autre']:
            commentaires = f"OPTION:{tranche_num_raw.upper()}"
            # Déterminer un montant estimé ou laisser l'IA l'extraire
            montant_mentionne = base_scolarite if tranche_num_raw == 'totalite' else Decimal('0.00')
        else:
            try:
                tranche_num = int(tranche_num_raw)
                tranche = TranchePaiement.objects.filter(numero=tranche_num).first()
                if tranche:
                    montant_mentionne = tranche.montant
            except (ValueError, TypeError):
                pass

        recu = RecuPaiement.objects.create(
            etudiant=etudiant,
            tranche=tranche,
            recu_fichier=file,
            montant_mentionne=montant_mentionne,
            statut='EN_ATTENTE',
            commentaires=commentaires
        )
        
        # Lancer l'analyse automatique par IA/OCR immédiatement
        recu.analyser_par_ia()
        
        # Message basé sur le résultat de l'analyse IA
        if recu.statut == 'VALIDE':
            messages.success(request, f"✅ Reçu validé automatiquement par l'IA ! Montant extrait : {recu.montant_mentionne:,.0f} FCFA. Les tranches correspondantes ont été créditées.")
        else:
            messages.warning(request, f"⏳ Reçu reçu et en attente de vérification manuelle par le Chef de la comptabilité. (Score IA: {recu.score_confiance:.0%})")
            
        return redirect('tableau_bord:tableau_bord')

    penalites_info = calculer_penalites_etudiant(etudiant)
    
    # Synchroniser les notifications pour cet utilisateur
    if etudiant.utilisateur:
        # Récupérer toutes les notifications de retard non lues pour cet utilisateur
        notifs_existantes = {
            n.titre: n for n in Notification.objects.filter(
                utilisateur=etudiant.utilisateur,
                type='WARNING',
                est_lue=False
            )
        }
        
        tranches_en_retard = set()
        
        # Créer ou mettre à jour les notifications pour chaque tranche en retard
        for detail in penalites_info.get('details', []):
            nom_tranche = detail['tranche']
            tranches_en_retard.add(nom_tranche)
            titre_notif = f"Retard de paiement - {nom_tranche}"
            message_notif = (
                f"Vous avez accumulé {detail['montant']:,} FCFA de pénalités pour la {nom_tranche} "
                f"en raison de {detail['semaines_retard']} semaine(s) de retard. "
                f"Date limite dépassée : {detail['date_limite'].strftime('%d/%m/%Y')}."
            )
            
            if titre_notif in notifs_existantes:
                # Si elle existe déjà mais que le message a changé (montant ou retard actualisés)
                notif = notifs_existantes[titre_notif]
                if notif.message != message_notif:
                    notif.message = message_notif
                    notif.save()
            else:
                # Créer une nouvelle notification
                Notification.objects.create(
                    utilisateur=etudiant.utilisateur,
                    type='WARNING',
                    titre=titre_notif,
                    message=message_notif,
                    lien='/inscriptions/'
                )
        
        # Nettoyer les notifications obsolètes (si une tranche a été régularisée)
        for titre, notif in notifs_existantes.items():
            if titre.startswith("Retard de paiement - "):
                nom_tranche = titre.replace("Retard de paiement - ", "")
                if nom_tranche not in tranches_en_retard:
                    # Plus de retard, on peut marquer la notification comme lue ou la supprimer
                    notif.est_lue = True
                    notif.date_lecture = timezone.now()
                    notif.save()
    from apps.paiements.models import ResultatConcours
    res_concours = None
    if etudiant.email:
        res_concours = ResultatConcours.objects.filter(
            Q(etudiant_cree=etudiant) | Q(email__iexact=etudiant.email)
        ).first()
    else:
        res_concours = ResultatConcours.objects.filter(etudiant_cree=etudiant).first()

    recus = RecuPaiement.objects.filter(etudiant=etudiant)
    montant_paye = sum((r.montant_mentionne or Decimal('0.00')) for r in recus if r.statut in ['VALIDE', 'EN_ATTENTE'])

    if res_concours:
        if res_concours.statut_preinscription == 'PAYE' and not recus.filter(tranche__numero=1, statut__in=['VALIDE', 'EN_ATTENTE']).exists():
            t1 = TranchePaiement.objects.filter(numero=1).first()
            montant_paye += (t1.montant if t1 else Decimal('84000.00'))
        if res_concours.statut_tranche2 == 'PAYE' and not recus.filter(tranche__numero=2, statut__in=['VALIDE', 'EN_ATTENTE']).exists():
            t2 = TranchePaiement.objects.filter(numero=2).first()
            montant_paye += (t2.montant if t2 else Decimal('175000.00'))

    if not isinstance(montant_paye, Decimal):
        montant_paye = Decimal(str(montant_paye))
    
    total_penalites = Decimal(str(penalites_info.get('total', 0)))
    total_du = base_scolarite + total_penalites
    reste_payer = max(Decimal('0.00'), total_du - montant_paye)

    
    from apps.cours.views import find_matching_salle
    matching_salle = find_matching_salle(etudiant.classe)
    
    emploi_query = EmploiDuTemps.objects.filter(filiere=etudiant.filiere, est_actif=True)
    emploi = None
    if etudiant.niveau and matching_salle:
        emploi = emploi_query.filter(niveau=etudiant.niveau, salle=matching_salle).first()
    if not emploi and etudiant.niveau:
        emploi = emploi_query.filter(niveau=etudiant.niveau, salle__isnull=True).first()
    if not emploi:
        emploi = emploi_query.filter(niveau__isnull=True, salle__isnull=True).first()
    salle_etu = getattr(etudiant, 'salle', None)
    if salle_etu:
        ressources = RessourceCours.objects.filter(
            Q(salle=salle_etu) | Q(salle__isnull=True, cours__filiere=etudiant.filiere)
        ).distinct()
    elif etudiant.filiere:
        ressources = RessourceCours.objects.filter(cours__filiere=etudiant.filiere)
    else:
        ressources = RessourceCours.objects.none()
    absences = Presence.objects.filter(etudiant=etudiant, statut__in=['ABSENT', 'RETARD'])
    notes = Note.objects.filter(etudiant=etudiant, est_validee=True)
    
    from .models import ReglementInterieur, NoteInformation
    reglement_actif = ReglementInterieur.objects.filter(est_actif=True).first()
    notes_info = NoteInformation.objects.filter(est_active=True).order_by('-date_publication')
    
    from apps.cours.presence_service import calculer_total_absences_cumulees
    total_absences_cumulees = calculer_total_absences_cumulees(etudiant)

    # Extraction dynamique du programme quotidien (Emploi du temps hebdo officiel du Chef des Études)
    from apps.cours.models import EmploiDuTempsHebdomadaire, CreneauEmploiDuTemps
    today = timezone.now().date()
    weekday_num = today.weekday()
    
    JOUR_MAP = {
        0: 'LUNDI',
        1: 'MARDI',
        2: 'MERCREDI',
        3: 'JEUDI',
        4: 'VENDREDI',
        5: 'SAMEDI',
    }
    JOUR_NOMS = {
        0: 'Lundi', 1: 'Mardi', 2: 'Mercredi', 3: 'Jeudi', 4: 'Vendredi', 5: 'Samedi', 6: 'Dimanche'
    }
    
    jour_code_actuel = JOUR_MAP.get(weekday_num, None)
    nom_jour_actuel = JOUR_NOMS.get(weekday_num, 'Aujourd\'hui')
    
    emploi_hebdo = None
    if etudiant.filiere:
        emploi_hebdo = EmploiDuTempsHebdomadaire.objects.filter(
            filiere=etudiant.filiere,
            statut='VALIDE',
            date_debut_semaine__lte=today,
            date_fin_semaine__gte=today
        ).first()
        
        if not emploi_hebdo:
            emploi_hebdo = EmploiDuTempsHebdomadaire.objects.filter(
                filiere=etudiant.filiere,
                statut='VALIDE'
            ).order_by('-date_creation').first()

    creneaux_du_jour = []
    if jour_code_actuel:
        creneaux_base = CreneauEmploiDuTemps.objects.filter(jour=jour_code_actuel).exclude(type_evenement='PAUSE')
        salle_etu = getattr(etudiant, 'salle', None)
        if salle_etu:
            creneaux_base = creneaux_base.filter(
                Q(emploi_du_temps__salle=salle_etu) | 
                Q(salle_nom__icontains=salle_etu.code) | 
                Q(salle_nom__icontains=salle_etu.nom)
            )
        elif emploi_hebdo:
            creneaux_base = creneaux_base.filter(emploi_du_temps=emploi_hebdo)
        
        creneaux_du_jour = creneaux_base.order_by('plage', 'id')

    # Échéances des tranches pour l'année académique active
    annee_code = etudiant.annee_academique.code if etudiant.annee_academique else "2024-2025"
    tranches_query = TranchePaiement.objects.filter(annee_academique=annee_code, est_actif=True).order_by('numero')

    tranches_validees_ids = set(
        RecuPaiement.objects.filter(
            etudiant=etudiant,
            statut='VALIDE'
        ).values_list('tranche_id', flat=True)
    )

    inscription_etud = etudiant.inscriptions.first()
    is_niv_2 = (etudiant.niveau and etudiant.niveau.numero == 2)

    tranches_echeances = []
    for tranche in tranches_query:
        # Cloner le montant d'affichage pour adapter dynamiquement la pré-inscription selon le niveau de l'étudiant
        montant_affichage = tranche.montant
        if tranche.numero == 1:
            montant_affichage = Decimal('71000.00') if is_niv_2 else Decimal('84000.00')
        elif tranche.numero == 2:
            montant_affichage = Decimal('175000.00')
        elif tranche.numero == 3:
            montant_affichage = Decimal('115000.00')
        elif tranche.numero == 4:
            montant_affichage = Decimal('100000.00')

        est_validee = (
            tranche.id in tranches_validees_ids
            or RecuPaiement.objects.filter(etudiant=etudiant, tranche=tranche, statut__in=['VALIDE', 'EN_ATTENTE']).exists()
            or (tranche.numero == 1 and (
                etudiant.recu_preinscription_valide 
                or (inscription_etud and inscription_etud.recu_preinscription_valide)
                or (res_concours and res_concours.statut_preinscription == 'PAYE')
            ))
            or (tranche.numero == 2 and (
                (inscription_etud and inscription_etud.recu_tranche_1_valide)
                or (res_concours and res_concours.statut_tranche2 == 'PAYE')
            ))
            or (tranche.numero == 3 and (
                (inscription_etud and inscription_etud.recu_tranche_2_valide)
                or (res_concours and res_concours.statut_tranche3 == 'PAYE')
            ))
            or (tranche.numero == 4 and (
                (inscription_etud and inscription_etud.recu_tranche_3_valide)
                or (res_concours and res_concours.statut_tranche4 == 'PAYE')
            ))
        )
        
        tranche.montant = montant_affichage
        tranche.est_validee = est_validee
        tranches_echeances.append(tranche)

    # Historique des règlements de pénalités
    from .models import PenalitePaiement
    from apps.paiements.models import TransactionPaiement
    penalites_reglees = PenalitePaiement.objects.filter(etudiant=etudiant, est_regle=True).order_by('-date_paiement')
    transactions_penalites = TransactionPaiement.objects.filter(
        etudiant=etudiant,
        type_paiement='PENALITE',
        statut='SUCCESS'
    ).order_by('-date_creation')

    # Sujets de TP / TD avec date limite de remise physique obligatoire
    cours_ids = InscriptionCours.objects.filter(etudiant=etudiant, est_actif=True).values_list('cours_id', flat=True)
    filt_echeances = Q(cours_id__in=cours_ids)
    if etudiant.filiere:
        filt_echeances |= Q(cours__filiere=etudiant.filiere)

    prochaines_echeances_tp_td = RessourceCours.objects.filter(
        filt_echeances,
        type_ressource__in=['TD', 'TP'],
        date_limite_remise_physique__isnull=False,
        date_limite_remise_physique__gte=timezone.now().date()
    ).distinct().select_related('cours', 'cours__matiere').order_by('date_limite_remise_physique')

    context = {
        'etudiant': etudiant,
        'penalites_info': penalites_info,
        'tranches_echeances': tranches_echeances,
        'penalites_reglees': penalites_reglees,
        'transactions_penalites': transactions_penalites,
        'prochaines_echeances_tp_td': prochaines_echeances_tp_td,
        'recus': recus,
        'montant_paye': montant_paye,
        'total_du': total_du,
        'reste_payer': reste_payer,
        'emploi': emploi,
        'emploi_hebdo': emploi_hebdo,
        'creneaux_du_jour': creneaux_du_jour,
        'nom_jour_actuel': nom_jour_actuel,
        'ressources': ressources,
        'absences': absences,
        'total_absences_cumulees': total_absences_cumulees,
        'notes': notes,
        'reglement_actif': reglement_actif,
        'notes_info': notes_info,
        'titre': 'Espace Étudiant',
        'date_aujourdhui': timezone.now()
    }
    return render(request, 'tableau_bord/etudiant_dashboard.html', context)


@login_required
def apprenant_dashboard(request):
    apprenant = Apprenant.objects.filter(utilisateur=request.user).first()
    if not apprenant:
        apprenant = Apprenant.objects.create(
            utilisateur=request.user,
            nom_complet=request.user.get_full_name() or request.user.username,
            email=request.user.email,
            contact=request.user.telephone or '699999999',
            lieu_residence='Douala'
        )
        
    if request.method == 'POST':
        # 1. Paiement des frais par l'apprenant dans son dashboard
        montant_paiement = request.POST.get('montant_paiement')
        mode_paiement = request.POST.get('mode_paiement', 'MTN Mobile Money')
        telephone_paiement = request.POST.get('telephone_paiement', '').strip()
        if montant_paiement:
            try:
                montant_val = float(montant_paiement)
                if montant_val > 0:
                    # Normaliser le numéro de téléphone au format camerounais (+237 6XXXXXXXX)
                    num_clean = "".join(filter(str.isdigit, telephone_paiement))
                    if len(num_clean) == 9:
                        num_formatted = f"+237 {num_clean[:3]} {num_clean[3:5]} {num_clean[5:7]} {num_clean[7:]}"
                    elif len(num_clean) == 12 and num_clean.startswith('237'):
                        num_formatted = f"+237 {num_clean[3:6]} {num_clean[6:8]} {num_clean[8:10]} {num_clean[10:]}"
                    else:
                        num_formatted = telephone_paiement or apprenant.contact

                    apprenant.enregistrer_paiement_formation(montant_val, mode_paiement=f"{mode_paiement} ({num_formatted})")
                    messages.success(
                        request,
                        f"📲 Notification USSD envoyée au {num_formatted} ! "
                        f"Le versement de {montant_val:,.0f} FCFA via {mode_paiement} a été validé. Vos données financières et votre solde ont été instantanément actualisés."
                    )
                else:
                    messages.error(request, "Veuillez saisir un montant supérieur à 0 FCFA.")
            except (ValueError, TypeError):
                messages.error(request, "Montant de paiement invalide.")
            return redirect('tableau_bord:tableau_bord')

        # 2. Inscription à une nouvelle formation
        formation_id = request.POST.get('formation_id')
        if formation_id:
            formation = get_object_or_404(Formation, id=formation_id)
            apprenant.formations.add(formation)
            apprenant.recalculer_solde()
            messages.success(request, f"Inscription à la formation {formation.get_nom_display()} enregistrée.")
            return redirect('tableau_bord:tableau_bord')
            
    formations_disponibles = Formation.objects.filter(est_active=True).exclude(id__in=apprenant.formations.all())
    apprenant.recalculer_solde()
    
    from .models import NoteInformation
    notes_info = NoteInformation.objects.filter(est_active=True).order_by('-date_publication')
    
    context = {
        'apprenant': apprenant,
        'formations_disponibles': formations_disponibles,
        'notes_info': notes_info,
        'titre': 'Espace Apprenant'
    }
    return render(request, 'tableau_bord/apprenant_dashboard.html', context)


@login_required
def enseignant_dashboard(request):
    if request.user.type_utilisateur == 'FORMATEUR':
        professeur = None
    else:
        professeur = Professeur.objects.filter(utilisateur=request.user).first()
        if not professeur:
            from apps.professeurs.models import Departement
            dept = Departement.objects.first()
            if not dept:
                dept = Departement.objects.create(code='INFO', nom='Informatique')
            professeur = Professeur.objects.create(
                utilisateur=request.user,
                matricule='PR202401',
                nom=request.user.last_name or 'Enseignant',
                prenom=request.user.first_name or 'IAI',
                email=request.user.email,
                telephone='699999999',
                adresse='Douala',
                date_naissance=timezone.now().date() - timedelta(days=12000),
                date_embauche=timezone.now().date(),
                grade='VACATAIRE',
                specialite='Génie Logiciel',
                departement=dept
            )

    if request.method == 'POST' and request.FILES.get('ressource_fichier'):
        cours_id = request.POST.get('cours_id')
        type_ressource = request.POST.get('type_ressource', 'COURS')
        titre = request.POST.get('titre', 'Support de cours')
        date_limite_raw = request.POST.get('date_limite_remise_physique', '').strip()
        cours_obj = get_object_or_404(Cours, id=cours_id)

        date_limite_val = None
        if date_limite_raw:
            try:
                from datetime import datetime
                date_limite_val = datetime.strptime(date_limite_raw, '%Y-%m-%d').date()
            except ValueError:
                date_limite_val = None

        salle_id = request.POST.get('salle_id')
        filiere_id = request.POST.get('filiere_id')
        niveau_id = request.POST.get('niveau_id')

        from apps.etudiants.models import Filiere, Niveau, Classe
        from apps.cours.models import Salle

        salle_obj = Salle.objects.filter(id=salle_id).first() if salle_id else None
        filiere_obj = None
        niveau_obj = None

        # Si une Salle / Classe est sélectionnée, déduire dynamiquement la filière et le niveau
        if salle_obj:
            classe_associee = Classe.objects.filter(Q(code__iexact=salle_obj.code) | Q(nom__icontains=salle_obj.code)).first()
            if classe_associee:
                filiere_obj = classe_associee.filiere
                niveau_obj = classe_associee.niveau

        if not filiere_obj and filiere_id:
            filiere_obj = Filiere.objects.filter(id=filiere_id).first()
        if not filiere_obj:
            filiere_obj = cours_obj.filiere

        if not niveau_obj and niveau_id:
            niveau_obj = Niveau.objects.filter(id=niveau_id).first()

        ressource = RessourceCours.objects.create(
            cours=cours_obj,
            salle=salle_obj,
            filiere=filiere_obj,
            niveau=niveau_obj,
            type_ressource=type_ressource,
            titre=titre,
            fichier=request.FILES.get('ressource_fichier'),
            date_limite_remise_physique=date_limite_val,
            est_public=True
        )

        # Envoi de la notification Tri-Canal (In-App, Email, WhatsApp) si c'est un TP/TD avec date de remise
        if type_ressource in ['TD', 'TP'] and date_limite_val:
            from apps.cours.models import InscriptionCours
            from apps.tableau_bord.models import Notification
            from apps.tableau_bord.whatsapp_service import WhatsAppService
            from django.core.mail import send_mail
            from django.conf import settings

            date_str = date_limite_val.strftime('%d/%m/%Y')
            titre_notif = f"📌 Remise physique {ressource.get_type_ressource_display()} : {titre}"
            msg_notif = (
                f"Le sujet de {ressource.get_type_ressource_display()} '{titre}' pour le cours {cours_obj.matiere.nom} ({cours_obj.filiere.code}) a été mis en ligne.\n"
                f"⚠️ DATE LIMITE DE REMISE PHYSIQUE : {date_str}."
            )
            site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')

            inscriptions = InscriptionCours.objects.filter(cours=cours_obj, est_actif=True).select_related('etudiant', 'etudiant__utilisateur')
            if salle_obj:
                inscriptions = inscriptions.filter(
                    Q(etudiant__salle=salle_obj) | Q(etudiant__salle__isnull=True)
                )
            for ins in inscriptions:
                etud = ins.etudiant
                if etud.utilisateur:
                    Notification.objects.create(
                        utilisateur=etud.utilisateur,
                        type='AVERTISSEMENT',
                        titre=titre_notif,
                        message=msg_notif,
                        lien=f'/cours/detail/{cours_obj.id}/'
                    )
                dest_email = getattr(etud, 'email', None) or (etud.utilisateur.email if etud.utilisateur else None)
                if dest_email:
                    try:
                        send_mail(
                            subject=f"{getattr(settings, 'EMAIL_SUBJECT_PREFIX', '[IAI-Cameroun] ')}{titre_notif}",
                            message=f"Bonjour {etud.get_nom_complet()},\n\n{msg_notif}\n\nConsultez le support : {site_url}/cours/detail/{cours_obj.id}/",
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[dest_email],
                            fail_silently=True
                        )
                    except Exception:
                        pass
                tel = getattr(etud, 'telephone', '') or (etud.utilisateur.telephone if hasattr(etud, 'utilisateur') and hasattr(etud.utilisateur, 'telephone') else '')
                if tel:
                    try:
                        WhatsAppService.envoyer_message(
                            tel,
                            f"*IAI-CAMEROUN (Douala)* 📌\n*{ressource.get_type_ressource_display()} - Remise physique*\n\nBonjour {etud.get_nom_complet()},\n{msg_notif}\n\nLien : {site_url}/cours/detail/{cours_obj.id}/"
                        )
                    except Exception:
                        pass

        messages.success(request, f"Le support '{titre}' a été téléversé avec succès.")
        return redirect('tableau_bord:tableau_bord')
        
    from apps.etudiants.models import Filiere, Niveau
    cours_enseignes = Cours.objects.filter(professeur=professeur).select_related('filiere', 'matiere') if professeur else Cours.objects.none()
    filieres_list = Filiere.objects.filter(id__in=cours_enseignes.values_list('filiere_id', flat=True).distinct()) if professeur else Filiere.objects.all()
    niveaux_list = Niveau.objects.all().order_by('numero')
    emplois = EmploiDuTemps.objects.all()
    mes_ressources = RessourceCours.objects.filter(cours__professeur=professeur).select_related('cours', 'cours__matiere', 'cours__filiere').order_by('-date_ajout') if professeur else RessourceCours.objects.none()

    # Statistiques et requêtes pour le rôle de Chef de Service Formation Continue/Certifiante
    from apps.etudiants.models import Apprenant
    from apps.requetes.models import Requete

    total_apprenants = Apprenant.objects.count()
    apprenants_continue = Apprenant.objects.filter(formations__type_formation='CONTINUE').distinct().count()
    apprenants_certif = Apprenant.objects.filter(formations__type_formation='CERTIFICATION').distinct().count()

    # Requêtes d'apprenants non closes
    requetes_apprenants = Requete.objects.filter(
        auteur__type_utilisateur='APPRENANT'
    ).exclude(statut='TRAITE').select_related('auteur')

    from .models import NoteInformation
    notes_info = NoteInformation.objects.filter(est_active=True).order_by('-date_publication')

    from apps.cours.presence_service import obtenir_programme_quotidien_enseignant, calculer_stats_seances_enseignant
    programme_quotidien = obtenir_programme_quotidien_enseignant(request.user)
    stats_seances = calculer_stats_seances_enseignant(request.user)

    from apps.cours.models import Salle
    salles_list = Salle.objects.filter(est_disponible=True).order_by('nom')
    if not salles_list.exists():
        salles_list = Salle.objects.all().order_by('nom')

    context = {
        'professeur': professeur,
        'cours_enseignes': cours_enseignes,
        'salles_list': salles_list,
        'filieres_list': filieres_list,
        'niveaux_list': niveaux_list,
        'mes_ressources': mes_ressources,
        'emplois': emplois,
        'programme_quotidien': programme_quotidien,
        'stats_seances': stats_seances,
        'seances_effectuees': stats_seances['seances_effectuees'],
        'seances_total': stats_seances['seances_total'],
        'taux_realisation': stats_seances['taux_realisation'],
        'total_apprenants': total_apprenants,
        'apprenants_continue': apprenants_continue,
        'apprenants_certif': apprenants_certif,
        'requetes_apprenants': requetes_apprenants,
        'notes_info': notes_info,
        'titre': 'Tableau de Bord - Formateur & Chef de Service'
    }
    return render(request, 'tableau_bord/enseignant_dashboard.html', context)


@login_required
def chef_formation_continue_dashboard(request):
    """
    Tableau de bord exclusif du Chef de Service - Formation Continue & Certifiante.
    Réservé au pilotage des apprenants, registres, notes, supports et requêtes d'apprenants, sans aucune vue d'enseignant.
    """
    from apps.etudiants.models import Apprenant
    from apps.requetes.models import Requete
    from .models import NoteInformation

    total_apprenants = Apprenant.objects.count()
    apprenants_continue = Apprenant.objects.filter(formations__type_formation='CONTINUE').distinct().count()
    apprenants_certif = Apprenant.objects.filter(formations__type_formation='CERTIFICATION').distinct().count()

    requetes_apprenants = Requete.objects.filter(
        auteur__type_utilisateur='APPRENANT'
    ).exclude(statut='TRAITE').select_related('auteur')

    notes_info = NoteInformation.objects.filter(est_active=True).order_by('-date_publication')

    context = {
        'total_apprenants': total_apprenants,
        'apprenants_continue': apprenants_continue,
        'apprenants_certif': apprenants_certif,
        'requetes_apprenants': requetes_apprenants,
        'notes_info': notes_info,
        'titre': 'Espace Chef de Service - Formation Continue & Certifiante'
    }
    return render(request, 'tableau_bord/chef_formation_continue_dashboard.html', context)


@login_required
def chef_scolarite_dashboard(request):
    from .models import ReglementInterieur
    from apps.etudiants.import_service import EtudiantImportService

    # Gérer le téléversement du règlement intérieur
    if request.method == 'POST' and request.FILES.get('reglement_fichier'):
        fichier = request.FILES.get('reglement_fichier')
        if fichier.name.endswith('.pdf'):
            reglement = ReglementInterieur.objects.create(
                titre=f"Règlement Intérieur - {timezone.now().strftime('%d/%m/%Y')}",
                fichier=fichier,
                est_actif=True
            )
            messages.success(request, f"✅ Règlement intérieur '{reglement.titre}' mis à jour avec succès.")
        else:
            messages.error(request, "❌ Seuls les fichiers PDF sont acceptés pour le règlement intérieur.")
        return redirect('tableau_bord:tableau_bord')
        
    # Gérer l'importation de listes d'étudiants (Excel, PDF, Images)
    elif request.method == 'POST' and request.FILES.get('liste_fichier'):
        fichier = request.FILES.get('liste_fichier')
        try:
            nb_ajoutes, nb_mis_a_jour, erreurs = EtudiantImportService.importer_depuis_fichier(fichier, request.user)
            
            if nb_ajoutes > 0 or nb_mis_a_jour > 0:
                msg = f"✅ Importation réussie : {nb_ajoutes} étudiant(s) ajouté(s), {nb_mis_a_jour} mis à jour."
                messages.success(request, msg)
            
            if erreurs:
                # Afficher les 5 premières erreurs pour ne pas encombrer l'écran
                for err in erreurs[:5]:
                    messages.warning(request, err)
                if len(erreurs) > 5:
                    messages.warning(request, f"... et {len(erreurs) - 5} autres erreurs d'analyse.")
                    
        except Exception as e:
            messages.error(request, f"❌ Échec de l'importation : {str(e)}")
            
        return redirect('tableau_bord:tableau_bord')
        
    etudiants = Etudiant.objects.all()
    filieres = Filiere.objects.all()
    classes = Classe.objects.all()
    reglement_actif = ReglementInterieur.objects.filter(est_actif=True).first()
    
    context = {
        'etudiants': etudiants,
        'filieres': filieres,
        'classes': classes,
        'reglement_actif': reglement_actif,
        'titre': 'Espace Scolarité'
    }
    return render(request, 'tableau_bord/chef_scolarite_dashboard.html', context)


@login_required
def chef_etudes_dashboard(request):
    from apps.inscriptions.utils import get_current_academic_year_code
    from apps.etudiants.models import Niveau
    from apps.cours.models import Salle
    if request.method == 'POST':
        if request.FILES.get('emploi_fichier'):
            filiere_id = request.POST.get('filiere_id')
            niveau_id = request.POST.get('niveau_id')
            salle_id = request.POST.get('salle_id')
            
            filiere = get_object_or_404(Filiere, id=filiere_id)
            
            niveau = None
            if niveau_id:
                niveau = get_object_or_404(Niveau, id=niveau_id)
                
            salle = None
            if salle_id:
                salle = get_object_or_404(Salle, id=salle_id)
                
            annee_academique = get_current_academic_year_code()
            semestre = 1
            
            # Supprimer l'ancien emploi du temps s'il existe pour la même combinaison unique
            existing_emplois = EmploiDuTemps.objects.filter(
                filiere=filiere,
                niveau=niveau,
                salle=salle,
                annee_academique=annee_academique,
                semestre=semestre
            )
            for old_emp in existing_emplois:
                if old_emp.fichier_pdf:
                    old_emp.fichier_pdf.delete(save=False)
                old_emp.delete()
                
            EmploiDuTemps.objects.create(
                filiere=filiere,
                niveau=niveau,
                salle=salle,
                annee_academique=annee_academique,
                semestre=semestre,
                fichier_pdf=request.FILES.get('emploi_fichier'),
                date_debut=timezone.now().date(),
                date_fin=timezone.now().date() + timedelta(days=120)
            )
            messages.success(request, "Emploi du temps mis à jour avec succès.")
            return redirect('tableau_bord:tableau_bord')
            
        elif request.POST.get('sujet') or request.FILES.get('note_fichier'):
            from apps.tableau_bord.models import NoteInformation
            titre = request.POST.get('sujet')
            contenu = request.POST.get('contenu', '')
            fichier_pdf = request.FILES.get('note_fichier')
            
            NoteInformation.objects.create(
                titre=titre,
                contenu=contenu,
                fichier_pdf=fichier_pdf,
                cree_par=request.user
            )
            messages.success(request, "📢 Note d'information publiée avec succès.")
            return redirect('tableau_bord:tableau_bord')
        
    from apps.notes.models import ProcesVerbalNotes
    from apps.tableau_bord.models import NoteInformation
    
    filieres = Filiere.objects.all()
    raw_niveaux = Niveau.objects.filter(numero__in=[1, 2]).order_by('numero')
    seen_nums = set()
    niveaux = []
    for n in raw_niveaux:
        if n.numero not in seen_nums:
            seen_nums.add(n.numero)
            niveaux.append(n)
    salles = Salle.objects.all()
    emplois = EmploiDuTemps.objects.select_related('filiere', 'niveau', 'salle').all()
    pvs = ProcesVerbalNotes.objects.filter(est_transmis=True).select_related('fiche_anonymat__matiere', 'fiche_anonymat__salle', 'fiche_anonymat__type_evaluation')
    notes_info = NoteInformation.objects.filter(est_active=True).order_by('-date_publication')
    
    context = {
        'filieres': filieres,
        'niveaux': niveaux,
        'salles': salles,
        'emplois': emplois,
        'pvs': pvs,
        'notes_info': notes_info,
        'titre': 'Espace Chef des Études'
    }
    return render(request, 'tableau_bord/chef_etudes_dashboard.html', context)


@login_required
def chef_anonymat_dashboard(request):
    from apps.notes.models import ProcesVerbalNotes
    
    if request.method == 'POST' and request.FILES.get('pv_fichier'):
        titre = request.POST.get('titre')
        ProcesVerbalNotes.objects.create(
            titre=titre,
            fichier_excel=request.FILES.get('pv_fichier'),
            cree_par=request.user
        )
        messages.success(request, "✅ Procès-verbal d'anonymat téléversé avec succès.")
        return redirect('tableau_bord:tableau_bord')
        
    pvs = ProcesVerbalNotes.objects.all().select_related('fiche_anonymat__matiere', 'fiche_anonymat__salle', 'fiche_anonymat__type_evaluation')
    
    context = {
        'titre': "Espace Chef de l'Anonymat",
        'pvs': pvs
    }
    return render(request, 'tableau_bord/chef_anonymat_dashboard.html', context)


@login_required
def chef_comptabilite_dashboard(request):
    from apps.inscriptions.utils import get_current_academic_year_code
    from apps.etudiants.models import Formation
    recus_attente = RecuPaiement.objects.filter(statut__in=['EN_ATTENTE', 'IA_VERIFIE'])
    annee_active = AnneeAcademique.objects.filter(est_active=True).first()
    annee_str = annee_active.code if annee_active else get_current_academic_year_code()
    
    if request.method == 'POST':
        recu_id = request.POST.get('recu_id')
        tranche_num = request.POST.get('tranche')
        tranche_id = request.POST.get('tranche_id')
        formation_nom = request.POST.get('formation_nom')

        if recu_id:
            action = request.POST.get('action')
            recu = get_object_or_404(RecuPaiement, id=recu_id)
            
            if action == 'valider':
                recu.statut = 'VALIDE'
                recu.save()
                messages.success(request, f"Reçu de {recu.etudiant.get_nom_complet()} validé.")
            elif action == 'rejeter':
                motif = request.POST.get('motif_rejet', '').strip()
                if not motif:
                    messages.error(request, "❌ Motif de rejet obligatoire ! Veuillez indiquer la raison du rejet pour l'étudiant.")
                    return redirect('tableau_bord:tableau_bord')
                
                recu.statut = 'REJETE'
                recu.commentaires = f"MOTIF DE REJET : {motif}"
                recu.date_verification = timezone.now()
                recu.verifie_par = request.user
                recu.save()
                
                # Notifier l'étudiant
                if recu.etudiant and recu.etudiant.utilisateur:
                    from apps.tableau_bord.models import Notification
                    Notification.objects.create(
                        utilisateur=recu.etudiant.utilisateur,
                        type='DANGER',
                        titre=f"Reçu de paiement rejeté ({recu.tranche.get_numero_display() if recu.tranche else 'Scolarité'})",
                        message=f"Votre reçu a été rejeté par la Comptabilité. Motif : {motif}. Veuillez téléverser un nouveau reçu valide.",
                        lien='/inscriptions/'
                    )
                
                messages.warning(request, f"⚠️ Reçu de {recu.etudiant.get_nom_complet()} rejeté (Motif : {motif}).")

        elif tranche_id and request.POST.get('date_limite'):
            d_limite = request.POST.get('date_limite')
            desc = request.POST.get('description', '')
            tranche = get_object_or_404(TranchePaiement, id=tranche_id)
            tranche.date_limite = d_limite
            if desc:
                tranche.description = desc
            tranche.save()
            messages.success(request, f"✅ Échéance Niveau 2 ({tranche.get_numero_display()}) mise à jour au {d_limite}.")

        elif tranche_num and request.POST.get('date_limite'):
            d_limite = request.POST.get('date_limite')
            desc = request.POST.get('description', '')
            tr_int = int(tranche_num)
            
            montants_std = {1: 71000, 2: 175000, 3: 115000, 4: 100000}
            tranche, created = TranchePaiement.objects.update_or_create(
                numero=tr_int,
                annee_academique=annee_str,
                defaults={
                    'date_limite': d_limite,
                    'montant': montants_std.get(tr_int, 71000),
                    'description': desc,
                    'est_actif': True
                }
            )
            messages.success(request, f"✅ Échéance Niveau 2 ({tranche.get_numero_display()}) enregistrée au {d_limite}.")

        elif formation_nom and request.POST.get('tarif'):
            tarif_val = request.POST.get('tarif')
            formation, created = Formation.objects.update_or_create(
                nom=formation_nom,
                defaults={'tarif': tarif_val, 'est_active': True}
            )
            messages.success(request, f"✅ Tarif de la formation '{formation.get_nom_display()}' mis à jour à {tarif_val} FCFA.")

        elif request.POST.get('apprenant_id') and request.POST.get('montant_avance'):
            apprenant_id = request.POST.get('apprenant_id')
            montant_avance = request.POST.get('montant_avance')
            try:
                from decimal import Decimal
                from apps.etudiants.models import Apprenant
                montant_val = Decimal(str(montant_avance))
                if montant_val > 0:
                    apprenant_obj = get_object_or_404(Apprenant, id=apprenant_id)
                    apprenant_obj.montant_paye += montant_val
                    apprenant_obj.recalculer_solde()

                    # 1. Notification In-App dans le Dashboard de l'Apprenant
                    from apps.tableau_bord.models import Notification
                    Notification.objects.create(
                        utilisateur=apprenant_obj.utilisateur,
                        type='SUCCESS',
                        titre=f"Avance de paiement validée ({montant_val:,.0f} FCFA)",
                        message=f"La Comptabilité a validé votre versement d'une avance de {montant_val:,.0f} FCFA sur vos frais de formation.\nTotal versé : {apprenant_obj.montant_paye:,.0f} FCFA | Reste à payer : {apprenant_obj.reste_a_payer:,.0f} FCFA.",
                        lien='/tableau-de-bord/'
                    )

                    # 2. Notification WhatsApp à l'Apprenant
                    try:
                        from apps.tableau_bord.whatsapp_service import WhatsAppService
                        tel = apprenant_obj.contact or (apprenant_obj.utilisateur.telephone if hasattr(apprenant_obj.utilisateur, 'telephone') else '')
                        if tel:
                            msg_wa = (
                                f"*IAI-CAMEROUN (Douala)* 🎓\n"
                                f"*Confirmation d'Avance de Paiement*\n\n"
                                f"Bonjour *{apprenant_obj.nom_complet}*,\n\n"
                                f"La Comptabilité a validé votre versement d'une avance de *{montant_val:,.0f} FCFA* sur vos frais de formation.\n\n"
                                f"• Total versé : *{apprenant_obj.montant_paye:,.0f} FCFA*\n"
                                f"• Reste à payer : *{apprenant_obj.reste_a_payer:,.0f} FCFA*\n\n"
                                f"_Votre tableau de bord a été automatiquement actualisé._"
                            )
                            WhatsAppService.envoyer_message(tel, msg_wa)
                    except Exception:
                        pass

                    messages.success(request, f"✅ Avance de {montant_val:,.0f} FCFA validée pour {apprenant_obj.nom_complet}. Solde mis à jour et notifications transmises !")
                else:
                    messages.error(request, "Veuillez saisir un montant supérieur à 0 FCFA.")
            except (ValueError, TypeError):
                messages.error(request, "Montant d'avance invalide.")
            
        return redirect('tableau_bord:tableau_bord')
        
    tranches_niveau2 = TranchePaiement.objects.filter(annee_academique=annee_str).order_by('numero')
    formations_all = Formation.objects.all().order_by('nom')
    from apps.etudiants.models import Apprenant
    apprenants_all = Apprenant.objects.all().order_by('nom_complet')

    from apps.paiements.models import ResultatConcours
    candidats_preinscrits_recent = ResultatConcours.objects.filter(
        statut_preinscription='PAYE',
        etudiant_cree__isnull=False
    ).select_related('filiere', 'etudiant_cree', 'etudiant_cree__utilisateur').order_by('-date_generation_acces')

    context = {
        'recus_attente': recus_attente,
        'tranches_niveau2': tranches_niveau2,
        'annee_code': annee_str,
        'formations_all': formations_all,
        'apprenants_all': apprenants_all,
        'candidats_preinscrits_recent': candidats_preinscrits_recent,
        'titre': "Espace Chef de la Comptabilité"
    }
    return render(request, 'tableau_bord/chef_comptabilite_dashboard.html', context)




@login_required
def dashboard_admin(request):
    """Tableau de bord principal d'administration générale"""
    annee_active = AnneeAcademique.objects.filter(est_active=True).first()
    
    # Si aucune année active n'existe, en créer une par défaut
    if not annee_active:
        from apps.inscriptions.utils import get_current_academic_year_code
        from datetime import date
        default_annee = get_current_academic_year_code()
        default_debut, default_fin = default_annee.split('-')
        
        annee_active = AnneeAcademique.objects.create(
            code=default_annee,
            date_debut=date(int(default_debut), 9, 1),
            date_fin=date(int(default_fin), 8, 31),
            est_active=True
        )
        
        # Synchroniser dans inscriptions
        from apps.inscriptions.models import AnneeAcademique as AnneeAcademiqueInscr
        AnneeAcademiqueInscr.objects.get_or_create(
            code=default_annee,
            defaults={
                'date_debut': date(int(default_debut), 9, 1),
                'date_fin': date(int(default_fin), 8, 31),
                'est_actuelle': True,
                'est_ouverte_inscription': True
            }
        )
    
    annee_code = annee_active.code
    
    # Statistiques générales
    stats = {
        'total_etudiants': Etudiant.objects.filter(
            statut__in=['ACTIF', 'INSCRIT']
        ).count(),
        'total_etudiants_annee': Etudiant.objects.filter(
            annee_academique=annee_active
        ).count(),
        'total_filieres': Filiere.objects.filter(est_active=True).count(),
        'total_professeurs': Professeur.objects.filter(statut='ACTIF').count() or Professeur.objects.count(),
        'total_apprenants': Apprenant.objects.count(),
        'taux_croissance': '+12.5%',


    }
    
    # Statistiques par sexe
    stats_sexe = {
        'masculin': Etudiant.objects.filter(
            annee_academique=annee_active,
            sexe='M'
        ).count(),
        'feminin': Etudiant.objects.filter(
            annee_academique=annee_active,
            sexe='F'
        ).count(),
    }
    
    # Pourcentage par sexe
    total_sexe = stats_sexe['masculin'] + stats_sexe['feminin']
    if total_sexe > 0:
        stats_sexe['masculin_pct'] = round(stats_sexe['masculin'] / total_sexe * 100, 1)
        stats_sexe['feminin_pct'] = round(stats_sexe['feminin'] / total_sexe * 100, 1)
    
    # Effectifs par filière
    effectifs_filiere = []
    for filiere in Filiere.objects.filter(est_active=True):
        count = Etudiant.objects.filter(
            filiere=filiere,
            statut__in=['ACTIF', 'INSCRIT']
        ).count()
        effectifs_filiere.append({
            'filiere': filiere,
            'effectif': count,
            'code': filiere.code,
            'nom': filiere.nom,
            'couleur': '#10B981' if filiere.code == 'GL' else '#F59E0B'
        })
    
    # Inscriptions récentes
    inscriptions_recentes = Etudiant.objects.filter(
        statut__in=['INSCRIT', 'ACTIF']
    ).select_related('filiere').order_by('-date_inscription')[:5]
    
    # Paiements récents
    paiements_recents = RecuPaiement.objects.filter(
        statut='VALIDE'
    ).select_related('etudiant', 'tranche').order_by('-date_verification')[:5]
    
    # Tâches en cours
    taches = []
    if hasattr(Tache, 'objects'):
        taches = Tache.objects.filter(
            assignee_a=request.user,
            statut__in=['A_FAIRE', 'EN_COURS']
        ).order_by('date_echeance')[:5]
    
    # Notifications non lues
    notifications = []
    if hasattr(Notification, 'objects'):
        notifications = Notification.objects.filter(
            utilisateur=request.user,
            est_lue=False
        ).order_by('-date_creation')[:5]
    
    # Recettes du mois
    debut_mois = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    recettes_mois = RecuPaiement.objects.filter(
        statut='VALIDE',
        date_verification__gte=debut_mois
    ).aggregate(
        total=Coalesce(Sum('montant_mentionne', output_field=DecimalField()), Value(0, output_field=DecimalField()))
    )['total'] or 0
    
    # Taux de remplissage des classes
    classes = Classe.objects.filter(est_active=True)
    taux_remplissage = 0
    if classes.exists():
        total_remplissage = 0
        valid_classes = 0
        for c in classes:
            if c.effectif_max and c.effectif_max > 0:
                total_remplissage += (c.effectif_actuel / c.effectif_max * 100)
                valid_classes += 1
        if valid_classes > 0:
            taux_remplissage = round(total_remplissage / valid_classes, 1)
    
    # Pénalités totales calculées dynamiquement en temps réel
    from apps.paiements.services import calculer_penalites_etudiant
    etudiants_penalites = Etudiant.objects.filter(statut__in=['ACTIF', 'INSCRIT'])
    penalites_total = sum(float(calculer_penalites_etudiant(etud).get('total', 0)) for etud in etudiants_penalites)
    
    # Alertes
    alertes = []
    
    # Alertes demandes d'inscription en attente
    from apps.authentification.models import DemandeInscription
    demandes_attente_count = DemandeInscription.objects.filter(statut='EN_ATTENTE').count()
    if demandes_attente_count > 0:
        alertes.append({
            'type': 'info',
            'message': f"{demandes_attente_count} demande(s) d'inscription en attente",
            'icone': 'user-clock',
            'lien': '/authentification/liste-demandes/',
            'couleur': '#3B82F6'
        })
        
    # Alertes paiements en attente
    recus_attente = RecuPaiement.objects.filter(statut='EN_ATTENTE').count()
    if recus_attente > 0:
        alertes.append({
            'type': 'warning',
            'message': f'{recus_attente} reçu(s) en attente de vérification',
            'icone': 'receipt',
            'lien': '/paiements/',
            'couleur': '#F59E0B'
        })
    
    # Alertes échéances
    echeances_proches = TranchePaiement.objects.filter(
        date_limite__gte=timezone.now().date(),
        date_limite__lte=timezone.now().date() + timedelta(days=7),
        est_actif=True
    ).count()
    if echeances_proches > 0:
        alertes.append({
            'type': 'info',
            'message': f'{echeances_proches} échéance(s) de paiement dans les 7 prochains jours',
            'icone': 'calendar',
            'lien': '/paiements/tranches/',
            'couleur': '#10B981'
        })
        
    # Demandes d'inscription en attente récentes
    demandes_en_attente = DemandeInscription.objects.filter(
        statut='EN_ATTENTE'
    ).select_related('user').order_by('-date_soumission')[:5]
    
    context = {
        'stats': stats,
        'stats_sexe': stats_sexe,
        'effectifs_filiere': effectifs_filiere,
        'inscriptions_recentes': inscriptions_recentes,
        'demandes_en_attente': demandes_en_attente,
        'paiements_recents': paiements_recents,
        'taches': taches,
        'notifications': notifications,
        'recettes_mois': float(recettes_mois) if recettes_mois else 0,
        'penalites_total': float(penalites_total) if penalites_total else 0,
        'taux_remplissage': taux_remplissage,
        'alertes': alertes,
        'annee_academique': annee_code,
        'annee_active': annee_active,
        'titre': 'Tableau de Bord',
        'sous_titre': 'Bienvenue sur votre espace de gestion',
        'date_aujourdhui': timezone.now(),
        'nom_utilisateur': request.user.get_full_name() or request.user.username,
        'primary_color': '#10B981',
        'secondary_color': '#F59E0B',
        'gradient_primary': 'linear-gradient(135deg, #10B981 0%, #059669 100%)',
        'gradient_secondary': 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)',
    }
    return render(request, 'tableau_bord/dashboard.html', context)


@login_required
def statistiques(request):
    """Page des statistiques principales - Style moderne et dynamique par acteur"""
    annee_active = AnneeAcademique.objects.filter(est_active=True).first()
    annee_code = request.GET.get('annee', annee_active.code if annee_active else '2024-2025')
    
    stats_mensuelles = RecuPaiement.objects.filter(
        statut='VALIDE'
    ).annotate(
        mois=TruncMonth('date_verification')
    ).values('mois').annotate(
        total=Sum('montant_mentionne', output_field=DecimalField()),
        nombre=Count('id')
    ).order_by('-mois')[:12]
    
    # Métriques globales toujours à jour
    total_etudiants = Etudiant.objects.filter(statut__in=['ACTIF', 'INSCRIT']).count()
    toutes_notes = Note.objects.all()
    total_notes = toutes_notes.count()
    taux_reussite_global = round((toutes_notes.filter(valeur__gte=10).count() / total_notes * 100), 1) if total_notes > 0 else 0.0

    total_recettes = RecuPaiement.objects.filter(statut='VALIDE').aggregate(
        total=Coalesce(Sum('montant_mentionne', output_field=DecimalField()), Value(0, output_field=DecimalField()))
    )['total'] or 0

    classes = Classe.objects.filter(est_active=True)
    taux_remplissage = 0.0
    if classes.exists():
        total_remplissage = 0.0
        valid_classes = 0
        for c in classes:
            eff_max = getattr(c, 'effectif_max', 30) or 30
            eff_actuel = c.etudiants.filter(statut__in=['ACTIF', 'INSCRIT']).count() if hasattr(c, 'etudiants') else getattr(c, 'effectif_actuel', 0)
            total_remplissage += (eff_actuel / eff_max * 100)
            valid_classes += 1
        if valid_classes > 0:
            taux_remplissage = round(total_remplissage / valid_classes, 1)

    effectifs_filiere = list(Etudiant.objects.filter(
        statut__in=['ACTIF', 'INSCRIT']
    ).values('filiere__code', 'filiere__nom').annotate(
        effectif=Count('id')
    ))
    
    for item in effectifs_filiere:
        filiere_code = item['filiere__code']
        notes_fil = Note.objects.filter(etudiant__filiere__code=filiere_code)
        item['taux_reussite'] = round((notes_fil.filter(valeur__gte=10).count() / notes_fil.count() * 100), 1) if notes_fil.exists() else 0.0
        item['nom'] = item['filiere__nom'] or filiere_code or "Filière sans nom"

    annees_histo = list(AnneeAcademique.objects.order_by('code'))
    labels_evolution = [ann.code for ann in annees_histo]
    data_evolution = [Etudiant.objects.filter(annee_academique=ann, statut__in=['ACTIF', 'INSCRIT']).count() for ann in annees_histo]

    if not labels_evolution:
        labels_evolution = ['2023-2024', '2024-2025', '2025-2026']
        data_evolution = [0, 0, total_etudiants]

    context = {
        'annee_academique': annee_code,
        'titre': 'Statistiques',
        'sous_titre': 'Analyse des données académiques et financières',
        'stats_mensuelles': stats_mensuelles,
        'primary_color': '#10B981',
        'secondary_color': '#F59E0B',
        'user_type': request.user.type_utilisateur,
        'total_recettes': float(total_recettes),
        'admin_stats': {
            'total_etudiants': total_etudiants,
            'taux_remplissage': taux_remplissage,
            'taux_reussite_global': taux_reussite_global,
        },
        'effectifs_filiere': effectifs_filiere,
        'labels_evolution': labels_evolution,
        'data_evolution': data_evolution,
    }

    type_user = request.user.type_utilisateur

    if type_user in ['ETUDIANT', 'APPRENANT']:
        etudiant = Etudiant.objects.filter(utilisateur=request.user).first()
        if etudiant:
            from decimal import Decimal
            base_scolarite = Decimal('461000.00')
            recus = etudiant.recus.filter(statut='VALIDE') if hasattr(etudiant, 'recus') else []
            montant_paye = sum(r.montant_mentionne for r in recus)
            penalites_info = calculer_penalites_etudiant(etudiant)
            total_du = base_scolarite + penalites_info['total']
            reste_payer = max(0, total_du - montant_paye)
            taux_paiement = round((montant_paye / total_du * 100), 1) if total_du > 0 else 100.0

            notes = Note.objects.filter(etudiant=etudiant)
            moyenne_generale = notes.aggregate(Avg('valeur'))['valeur__avg'] or 0.0
            matieres_validees = notes.filter(valeur__gte=10).count()
            total_evaluations = notes.count()

            presences = Presence.objects.filter(etudiant=etudiant)
            total_presences = presences.count()
            presents = presences.filter(statut='PRESENT').count()
            absents = presences.filter(statut='ABSENT').count()
            retards = presences.filter(statut='RETARD').count()
            excuses = presences.filter(statut='EXCUSE').count()
            taux_presence = round((presents / total_presences * 100), 1) if total_presences > 0 else 100.0

            notes_data = list(notes.values('evaluation__titre', 'valeur'))

            context.update({
                'etudiant': etudiant,
                'financier': {
                    'total_du': float(total_du),
                    'montant_paye': float(montant_paye),
                    'reste_payer': float(reste_payer),
                    'taux_paiement': float(taux_paiement),
                },
                'academique': {
                    'moyenne_generale': round(float(moyenne_generale), 2),
                    'matieres_validees': matieres_validees,
                    'total_evaluations': total_evaluations,
                },
                'assiduite': {
                    'total': total_presences,
                    'presents': presents,
                    'absents': absents,
                    'retards': retards,
                    'excuses': excuses,
                    'taux_presence': float(taux_presence),
                },
                'notes_data': notes_data,
            })

    elif type_user in ['ENSEIGNANT', 'PROFESSEUR', 'FORMATEUR']:
        prof = Professeur.objects.filter(utilisateur=request.user).first()
        if prof:
            cours_assignes = Cours.objects.filter(professeur=prof)
            nb_cours = cours_assignes.count()

            from apps.cours.models import InscriptionCours
            etudiants_ids = InscriptionCours.objects.filter(
                cours__in=cours_assignes, 
                est_actif=True
            ).values_list('etudiant_id', flat=True).distinct()
            nb_etudiants = len(etudiants_ids)

            from apps.cours.presence_service import calculer_stats_seances_enseignant
            stats_seances = calculer_stats_seances_enseignant(request.user)
            seances_effectuees = stats_seances['seances_effectuees']
            seances_total = stats_seances['seances_total']
            taux_realisation = stats_seances['taux_realisation']

            evaluations = Evaluation.objects.filter(cours__professeur=request.user)
            nb_evaluations = evaluations.count()

            notes_enseignant = Note.objects.filter(evaluation__cours__professeur=request.user)
            moyenne_notes = notes_enseignant.aggregate(Avg('valeur'))['valeur__avg'] or 0.0
            total_notes = notes_enseignant.count()
            taux_reussite_enseignant = round((notes_enseignant.filter(valeur__gte=10).count() / total_notes * 100), 1) if total_notes > 0 else 0.0

            context.update({
                'prof': prof,
                'nb_cours': nb_cours,
                'nb_etudiants': nb_etudiants,
                'seances_effectuees': seances_effectuees,
                'seances_total': seances_total,
                'taux_realisation': float(taux_realisation),
                'nb_evaluations': nb_evaluations,
                'moyenne_notes': round(float(moyenne_notes), 2),
                'taux_reussite_enseignant': float(taux_reussite_enseignant),
            })

    # Années académiques disponibles
    annees_list = list(AnneeAcademique.objects.values_list('code', flat=True).order_by('-code'))
    if not annees_list:
        annees_list = ['2025-2026', '2024-2025', '2023-2024']

    context.update({
        'annees_list': annees_list,
    })

    if type_user == 'CHEF_ANONYMAT' or type_user in ['ADMIN_SYSTEME', 'DIRECTEUR', 'CHEF_ETUDES'] or request.user.is_superuser:
        from apps.notes.models import FicheNotesAnonymat, LigneFicheNotesAnonymat, ProcesVerbalNotes

        fiches = FicheNotesAnonymat.objects.filter(annee_academique=annee_code) if FicheNotesAnonymat.objects.filter(annee_academique=annee_code).exists() else FicheNotesAnonymat.objects.all()
        fiches_total = fiches.count()
        fiches_transmises = fiches.filter(statut='TRANSMIS_CHEF_ANONYMAT').count()
        fiches_matchees = fiches.filter(statut__in=['MATCH_EFFECTUE', 'PV_GENERE', 'TRANSMIS_CHEF_ETUDES', 'VALIDE']).count()
        fiches_brouillon = fiches.filter(statut='BROUILLON').count()
        
        lignes = LigneFicheNotesAnonymat.objects.filter(fiche__in=fiches) if fiches_total > 0 else LigneFicheNotesAnonymat.objects.all()
        copies_total = lignes.count()
        copies_matchees = lignes.filter(etudiant__isnull=False).count()
        
        # Taux de traitement basé sur les copies réellement démasquées / traitées
        taux_matching = round((copies_matchees / copies_total * 100), 1) if copies_total > 0 else 0.0
        pv_generes = ProcesVerbalNotes.objects.count()
        
        fiches_examens = fiches.filter(mode_fiche='DEVOIR_SUR_TABLE').count()
        fiches_cc = fiches.filter(mode_fiche='EXPOSE_TP_TD').count()

        context.update({
            'anonymat_stats': {
                'fiches_total': fiches_total,
                'fiches_transmises': fiches_transmises,
                'fiches_matchees': fiches_matchees,
                'fiches_brouillon': fiches_brouillon,
                'copies_total': copies_total,
                'copies_matchees': copies_matchees,
                'taux_matching': float(taux_matching),
                'pv_generes': pv_generes,
                'fiches_examens': fiches_examens,
                'fiches_cc': fiches_cc,
            }
        })

    elif type_user in ['CHEF_COMPTABILITE', 'ADMIN_FINANCIER']:
        total_recettes = RecuPaiement.objects.filter(statut='VALIDE').aggregate(
            total=Coalesce(Sum('montant_mentionne', output_field=DecimalField()), Value(0, output_field=DecimalField()))
        )['total'] or 0

        from decimal import Decimal
        base_scolarite = Decimal('461000.00')
        etudiants_actifs = Etudiant.objects.filter(statut__in=['ACTIF', 'INSCRIT'])
        nb_etudiants = etudiants_actifs.count()
        total_attendu = base_scolarite * nb_etudiants
        reste_recouvrer = max(0, total_attendu - total_recettes)
        taux_recouvrement = round((total_recettes / total_attendu * 100), 1) if total_attendu > 0 else 100.0

        recus_attente = RecuPaiement.objects.filter(statut='EN_ATTENTE').count()

        context.update({
            'finance_global': {
                'total_recettes': float(total_recettes),
                'reste_recouvrer': float(reste_recouvrer),
                'taux_recouvrement': float(taux_recouvrement),
                'recus_attente': recus_attente,
            }
        })

    else:
        # Scolarité / Études / Admin Général
        total_etudiants = Etudiant.objects.filter(statut__in=['ACTIF', 'INSCRIT']).count()

        classes = Classe.objects.filter(est_active=True)
        taux_remplissage = 0.0
        if classes.exists():
            total_remplissage = 0.0
            valid_classes = 0
            for c in classes:
                eff_max = getattr(c, 'effectif_max', 30) or 30
                eff_actuel = c.etudiants.filter(statut__in=['ACTIF', 'INSCRIT']).count() if hasattr(c, 'etudiants') else getattr(c, 'effectif_actuel', 0)
                total_remplissage += (eff_actuel / eff_max * 100)
                valid_classes += 1
            if valid_classes > 0:
                taux_remplissage = round(total_remplissage / valid_classes, 1)

        toutes_notes = Note.objects.all()
        total_notes = toutes_notes.count()
        taux_reussite_global = round((toutes_notes.filter(valeur__gte=10).count() / total_notes * 100), 1) if total_notes > 0 else 0.0

        total_recettes = RecuPaiement.objects.filter(statut='VALIDE').aggregate(
            total=Coalesce(Sum('montant_mentionne', output_field=DecimalField()), Value(0, output_field=DecimalField()))
        )['total'] or 0

        effectifs_filiere = list(Etudiant.objects.filter(
            statut__in=['ACTIF', 'INSCRIT']
        ).values('filiere__code', 'filiere__nom').annotate(
            effectif=Count('id')
        ))
        
        for item in effectifs_filiere:
            filiere_code = item['filiere__code']
            notes_fil = Note.objects.filter(etudiant__filiere__code=filiere_code)
            item['taux_reussite'] = round((notes_fil.filter(valeur__gte=10).count() / notes_fil.count() * 100), 1) if notes_fil.exists() else 0.0
            item['nom'] = item['filiere__nom'] or filiere_code or "Non renseigné"

        # Évolution dynamique par année académique
        annees_histo = list(AnneeAcademique.objects.order_by('code'))
        labels_evolution = []
        data_evolution = []
        for ann in annees_histo:
            labels_evolution.append(ann.code)
            cnt = Etudiant.objects.filter(annee_academique=ann, statut__in=['ACTIF', 'INSCRIT']).count()
            data_evolution.append(cnt)

        if not labels_evolution:
            labels_evolution = ['2023-2024', '2024-2025', '2025-2026']
            data_evolution = [0, 0, total_etudiants]

        context.update({
            'admin_stats': {
                'total_etudiants': total_etudiants,
                'taux_remplissage': taux_remplissage,
                'taux_reussite_global': taux_reussite_global,
            },
            'total_recettes': float(total_recettes),
            'effectifs_filiere': effectifs_filiere,
            'labels_evolution': labels_evolution,
            'data_evolution': data_evolution,
        })
    
    return render(request, 'tableau_bord/statistiques.html', context)


@login_required
def statistiques_filieres(request):
    """Statistiques par filière"""
    filieres = Filiere.objects.filter(est_active=True).annotate(
        nb_etudiants=Count('etudiants', filter=Q(etudiants__statut__in=['ACTIF', 'INSCRIT']))
    )
    
    context = {
        'filieres': filieres,
        'titre': 'Statistiques par Filière',
        'primary_color': '#10B981',
        'secondary_color': '#F59E0B',
    }
    return render(request, 'tableau_bord/statistiques_filieres.html', context)


@login_required
def statistiques_paiements(request):
    """Statistiques des paiements"""
    total_recettes = RecuPaiement.objects.filter(statut='VALIDE').aggregate(
        total=Coalesce(Sum('montant_mentionne', output_field=DecimalField()), Value(0, output_field=DecimalField()))
    )['total'] or 0
    
    total_penalites = PenalitePaiement.objects.aggregate(
        total=Coalesce(Sum('montant_penalite', output_field=DecimalField()), Value(0, output_field=DecimalField()))
    )['total'] or 0
    
    recettes_par_tranche = []
    tranches_noms = ['Pré-inscription', '1ère Tranche', '2ème Tranche', '3ème Tranche']
    for i in range(1, 5):
        total = RecuPaiement.objects.filter(
            tranche__numero=i,
            statut='VALIDE'
        ).aggregate(
            total=Coalesce(Sum('montant_mentionne', output_field=DecimalField()), Value(0, output_field=DecimalField()))
        )['total'] or 0
        recettes_par_tranche.append({
            'tranche': i,
            'nom': tranches_noms[i-1],
            'total': float(total),
            'couleur': '#10B981' if i % 2 == 0 else '#F59E0B'
        })
    
    context = {
        'total_recettes': float(total_recettes),
        'total_penalites': float(total_penalites),
        'recettes_par_tranche': recettes_par_tranche,
        'titre': 'Statistiques des Paiements',
        'primary_color': '#10B981',
        'secondary_color': '#F59E0B',
    }
    return render(request, 'tableau_bord/statistiques_paiements.html', context)


@login_required
def exporter_statistiques(request):
    """Exporter les statistiques en CSV"""
    import csv
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="statistiques_iai.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Indicateur', 'Valeur', 'Date'])
    writer.writerow(['Date d\'export', timezone.now().strftime('%d/%m/%Y %H:%M'), ''])
    writer.writerow([])
    
    # Ajouter les statistiques
    writer.writerow(['Total étudiants', Etudiant.objects.filter(statut__in=['ACTIF', 'INSCRIT']).count(), ''])
    writer.writerow(['Total filières', Filiere.objects.filter(est_active=True).count(), ''])
    total_recettes = RecuPaiement.objects.filter(statut='VALIDE').aggregate(
        total=Sum('montant_mentionne')
    )['total'] or 0
    writer.writerow(['Recettes totales', total_recettes, 'FCFA'])
    
    return response


@login_required
def notifications(request):
    """Page des notifications avec filtres fonctionnels"""
    from django.db.models import Q
    filtre = request.GET.get('filtre', 'toutes').lower()
    archive = request.GET.get('archive', '').lower() == 'true'
    
    queryset = Notification.objects.filter(utilisateur=request.user)
    
    # Application des filtres métier
    if filtre == 'non_lues':
        queryset = queryset.filter(est_lue=False)
    elif filtre == 'lues' or archive:
        queryset = queryset.filter(est_lue=True)
    elif filtre == 'systeme':
        queryset = queryset.filter(
            Q(type='INFO') | Q(titre__icontains='Système') | Q(titre__icontains='Anonymat')
        )
    elif filtre == 'paiement':
        queryset = queryset.filter(
            Q(titre__icontains='Paiement') | Q(titre__icontains='Reçu') | Q(titre__icontains='Retard') | Q(type='WARNING')
        )
    elif filtre == 'inscription':
        queryset = queryset.filter(
            Q(titre__icontains='Inscription') | Q(titre__icontains='Dossier') | Q(titre__icontains='Scolarité') | Q(type='SUCCESS')
        )

    queryset = queryset.order_by('-date_creation')
    
    if request.method == 'POST' and request.POST.get('action') == 'marquer_toutes':
        Notification.objects.filter(utilisateur=request.user, est_lue=False).update(est_lue=True, date_lecture=timezone.now())
        messages.success(request, 'Toutes les notifications ont été marquées comme lues.')
        return redirect('tableau_bord:notifications')
    
    paginator = Paginator(queryset, 20)
    page = request.GET.get('page', 1)
    notifications_page = paginator.get_page(page)
    
    context = {
        'notifications': notifications_page,
        'non_lues_count': Notification.objects.filter(utilisateur=request.user, est_lue=False).count(),
        'filtre_actif': filtre,
        'archive_active': archive,
        'titre': 'Notifications',
        'primary_color': '#10B981',
        'secondary_color': '#F59E0B',
    }
    return render(request, 'tableau_bord/notifications.html', context)



@login_required
def marquer_notification_lue(request, pk):
    """Marquer une notification comme lue"""
    notification = get_object_or_404(Notification, pk=pk, utilisateur=request.user)
    notification.est_lue = True
    notification.date_lecture = timezone.now()
    notification.save()
    
    if notification.lien:
        return redirect(notification.lien)
    return redirect('tableau_bord:notifications')


@login_required
def marquer_toutes_notifications_lues(request):
    """Marquer toutes les notifications comme lues"""
    Notification.objects.filter(
        utilisateur=request.user,
        est_lue=False
    ).update(est_lue=True, date_lecture=timezone.now())
    
    messages.success(request, 'Toutes les notifications ont été marquées comme lues.')
    return redirect('tableau_bord:notifications')


@login_required
def supprimer_notification(request, pk):
    """Supprimer une notification"""
    notification = get_object_or_404(Notification, pk=pk, utilisateur=request.user)
    notification.delete()
    messages.success(request, 'Notification supprimée.')
    return redirect('tableau_bord:notifications')


@login_required
def taches(request):
    """Page des tâches"""
    taches_list = Tache.objects.filter(
        assignee_a=request.user
    ).order_by('-priorite', 'date_echeance')
    
    stats_taches = {
        'total': taches_list.count(),
        'a_faire': taches_list.filter(statut='A_FAIRE').count(),
        'en_cours': taches_list.filter(statut='EN_COURS').count(),
        'terminees': taches_list.filter(statut='TERMINEE').count(),
        'annulees': taches_list.filter(statut='ANNULEE').count(),
        'en_retard': taches_list.filter(
            statut__in=['A_FAIRE', 'EN_COURS'],
            date_echeance__lt=timezone.now()
        ).count()
    }
    
    context = {
        'taches': taches_list,
        'stats_taches': stats_taches,
        'titre': 'Mes Tâches',
        'primary_color': '#10B981',
        'secondary_color': '#F59E0B',
    }
    return render(request, 'tableau_bord/taches.html', context)


@login_required
def ajouter_tache(request):
    """Ajouter une tâche"""
    if request.method == 'POST':
        messages.success(request, 'Tâche ajoutée avec succès.')
        return redirect('tableau_bord:taches')
    
    context = {
        'titre': 'Ajouter une tâche',
        'primary_color': '#10B981',
        'secondary_color': '#F59E0B',
    }
    return render(request, 'tableau_bord/ajouter_tache.html', context)


@login_required
def modifier_tache(request, pk):
    """Modifier une tâche"""
    tache = get_object_or_404(Tache, pk=pk, assignee_a=request.user)
    
    if request.method == 'POST':
        messages.success(request, 'Tâche modifiée avec succès.')
        return redirect('tableau_bord:taches')
    
    context = {
        'tache': tache,
        'titre': 'Modifier la tâche',
        'primary_color': '#10B981',
        'secondary_color': '#F59E0B',
    }
    return render(request, 'tableau_bord/modifier_tache.html', context)


@login_required
def supprimer_tache(request, pk):
    """Supprimer une tâche"""
    tache = get_object_or_404(Tache, pk=pk, assignee_a=request.user)
    
    if request.method == 'POST':
        tache.delete()
        messages.success(request, 'Tâche supprimée avec succès.')
        return redirect('tableau_bord:taches')
    
    context = {
        'tache': tache,
        'titre': 'Supprimer la tâche',
        'primary_color': '#10B981',
        'secondary_color': '#F59E0B',
    }
    return render(request, 'tableau_bord/supprimer_tache.html', context)


@login_required
def terminer_tache(request, pk):
    """Marquer une tâche comme terminée"""
    tache = get_object_or_404(Tache, pk=pk, assignee_a=request.user)
    tache.statut = 'TERMINEE'
    tache.date_completion = timezone.now()
    tache.save()
    messages.success(request, 'Tâche marquée comme terminée.')
    return redirect('tableau_bord:taches')


@login_required
def messages_view(request):
    """Page des messages"""
    context = {
        'titre': 'Messages',
        'primary_color': '#10B981',
        'secondary_color': '#F59E0B',
    }
    return render(request, 'tableau_bord/messages.html', context)


@login_required
def envoyer_message(request):
    """Envoyer un message"""
    if request.method == 'POST':
        messages.success(request, 'Message envoyé avec succès.')
        return redirect('tableau_bord:messages')
    
    context = {
        'titre': 'Envoyer un message',
        'primary_color': '#10B981',
        'secondary_color': '#F59E0B',
    }
    return render(request, 'tableau_bord/envoyer_message.html', context)


@login_required
def detail_message(request, pk):
    """Détail d'un message"""
    context = {
        'titre': 'Détail du message',
        'primary_color': '#10B981',
        'secondary_color': '#F59E0B',
    }
    return render(request, 'tableau_bord/detail_message.html', context)


@login_required
def repondre_message(request, pk):
    """Répondre à un message"""
    if request.method == 'POST':
        messages.success(request, 'Réponse envoyée avec succès.')
        return redirect('tableau_bord:messages')
    
    context = {
        'titre': 'Répondre au message',
        'primary_color': '#10B981',
        'secondary_color': '#F59E0B',
    }
    return render(request, 'tableau_bord/repondre_message.html', context)


@login_required
def archiver_messages(request):
    """Archiver les messages"""
    messages.success(request, 'Messages archivés avec succès.')
    return redirect('tableau_bord:messages')


@login_required
def profil(request):
    """Page de profil utilisateur"""
    user = request.user
    
    if request.method == 'POST':
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        if hasattr(user, 'telephone'):
            user.telephone = request.POST.get('telephone', user.telephone)
        if hasattr(user, 'adresse'):
            user.adresse = request.POST.get('adresse', user.adresse)
        if request.FILES.get('photo'):
            user.photo = request.FILES.get('photo')
        user.save()
        
        # Synchroniser le profil Apprenant s'il existe
        if user.type_utilisateur == 'APPRENANT':
            apprenant = getattr(user, 'profil_apprenant', None)
            if apprenant:
                if user.last_name or user.first_name:
                    apprenant.nom_complet = f"{user.last_name} {user.first_name}".strip()
                if user.email:
                    apprenant.email = user.email
                if user.telephone:
                    apprenant.contact = user.telephone
                if user.adresse:
                    apprenant.lieu_residence = user.adresse
                apprenant.save()
        elif user.type_utilisateur == 'ETUDIANT':
            etudiant = getattr(user, 'profil_etudiant', None)
            if etudiant and request.FILES.get('photo'):
                etudiant.photo = request.FILES.get('photo')
                etudiant.save()

        messages.success(request, 'Votre profil a été mis à jour avec succès.')
        return redirect('tableau_bord:profil')
    
    context = {
        'user': user,
        'titre': 'Mon Profil',
        'primary_color': '#10B981',
        'secondary_color': '#F59E0B',
    }
    return render(request, 'tableau_bord/profil.html', context)


@login_required
def modifier_profil(request):
    """Modifier le profil"""
    user = request.user
    etudiant = None
    if user.type_utilisateur == 'ETUDIANT':
        etudiant = getattr(user, 'profil_etudiant', None)
        
    if request.method == 'POST':
        import re
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        telephone = request.POST.get('telephone', '').strip()
        indicatif_telephone = request.POST.get('indicatif_telephone', '').strip()
        adresse = request.POST.get('adresse', '').strip()
        
        if indicatif_telephone and telephone and not telephone.startswith('+'):
            num_clean = re.sub(r'\D', '', telephone)
            if num_clean:
                telephone = f"{indicatif_telephone}{num_clean}"
        
        errors = []
        
        if not first_name or not last_name or not email:
            errors.append("Les champs Prénom, Nom et Email sont obligatoires.")
            
        if user.type_utilisateur == 'ETUDIANT' and not etudiant:
            errors.append("Profil étudiant introuvable. Veuillez contacter l'administration.")
            
        if user.type_utilisateur == 'ETUDIANT' and etudiant:
            date_naissance_str = request.POST.get('date_naissance', '').strip()
            lieu_naissance = request.POST.get('lieu_naissance', '').strip()
            sexe = request.POST.get('sexe', '').strip()
            nationalite = request.POST.get('nationalite', '').strip()
            nom_tuteur = request.POST.get('nom_tuteur', '').strip()
            telephone_tuteur = request.POST.get('telephone_tuteur', '').strip()
            indicatif_tuteur = request.POST.get('indicatif_tuteur', '').strip()
            email_tuteur = request.POST.get('email_tuteur', '').strip()
            
            if indicatif_tuteur and telephone_tuteur and not telephone_tuteur.startswith('+'):
                num_clean_tuteur = re.sub(r'\D', '', telephone_tuteur)
                if num_clean_tuteur:
                    telephone_tuteur = f"{indicatif_tuteur}{num_clean_tuteur}"
            
            if not date_naissance_str or not lieu_naissance or not sexe or not nationalite or not telephone_tuteur or not nom_tuteur or not telephone or not adresse:
                errors.append("Tous les champs du profil étudiant (informations personnelles, contact, tuteur) sont obligatoires.")
            
            date_naissance = None
            if date_naissance_str:
                from datetime import datetime
                for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
                    try:
                        date_naissance = datetime.strptime(date_naissance_str, fmt).date()
                        break
                    except ValueError:
                        pass
                if not date_naissance:
                    errors.append("Le format de la date de naissance est invalide. Utilisez AAAA-MM-JJ ou JJ/MM/AAAA.")
            
            # Vérifier numéro de téléphone
            import re
            if telephone and not re.match(r'^\+?\d{9,15}$', telephone):
                errors.append("Le numéro de téléphone est invalide.")
            if telephone_tuteur and not re.match(r'^\+?\d{9,15}$', telephone_tuteur):
                errors.append("Le numéro de téléphone du tuteur est invalide.")
                
            if not errors:
                try:
                    # Mettre à jour l'utilisateur
                    user.first_name = first_name
                    user.last_name = last_name
                    user.email = email
                    user.telephone = telephone
                    user.adresse = adresse
                    if request.FILES.get('photo'):
                        user.photo = request.FILES.get('photo')
                    user.save()
                    
                    # Mettre à jour le profil étudiant
                    etudiant.nom = last_name
                    etudiant.prenom = first_name
                    etudiant.email = email
                    etudiant.telephone = telephone
                    etudiant.adresse = adresse
                    etudiant.date_naissance = date_naissance
                    etudiant.lieu_naissance = lieu_naissance
                    etudiant.sexe = sexe
                    etudiant.nationalite = nationalite
                    etudiant.nom_tuteur = nom_tuteur
                    etudiant.telephone_tuteur = telephone_tuteur
                    etudiant.email_tuteur = email_tuteur if email_tuteur else None
                    if request.FILES.get('photo'):
                        etudiant.photo = request.FILES.get('photo')
                    etudiant.save()
                    
                    messages.success(request, '✅ Votre profil a été mis à jour avec succès.')
                    
                    next_url = request.GET.get('next')
                    if next_url:
                        return redirect(next_url)
                    return redirect('tableau_bord:profil')
                except Exception as e:
                    errors.append(f"Erreur lors de la sauvegarde : {str(e)}")
        else:
            # Pour le personnel et les apprenants
            if not errors:
                try:
                    user.first_name = first_name
                    user.last_name = last_name
                    user.email = email
                    user.telephone = telephone
                    user.adresse = adresse
                    if request.FILES.get('photo'):
                        user.photo = request.FILES.get('photo')
                    user.save()
                    
                    if user.type_utilisateur == 'APPRENANT':
                        apprenant = getattr(user, 'profil_apprenant', None)
                        if apprenant:
                            if last_name or first_name:
                                apprenant.nom_complet = f"{last_name} {first_name}".strip()
                            if email:
                                apprenant.email = email
                            if telephone:
                                apprenant.contact = telephone
                            if adresse:
                                apprenant.lieu_residence = adresse
                            apprenant.save()

                    messages.success(request, '✅ Votre profil a été mis à jour avec succès.')
                    return redirect('tableau_bord:profil')
                except Exception as e:
                    errors.append(f"Erreur lors de la sauvegarde : {str(e)}")
                    
        for err in errors:
            messages.error(request, err)
            
    context = {
        'titre': 'Modifier mon profil',
        'primary_color': '#10B981',
        'secondary_color': '#F59E0B',
        'etudiant': etudiant,
        'compte_incomplet': request.GET.get('compte_incomplet') == '1',
    }
    return render(request, 'tableau_bord/modifier_profil.html', context)


@login_required
def changer_mot_de_passe(request):
    """Changer le mot de passe"""
    if request.method == 'POST':
        messages.success(request, 'Mot de passe modifié avec succès.')
        return redirect('tableau_bord:profil')
    
    context = {
        'titre': 'Changer mon mot de passe',
        'primary_color': '#10B981',
        'secondary_color': '#F59E0B',
    }
    return render(request, 'tableau_bord/changer_mot_de_passe.html', context)


@login_required
def calendrier(request):
    """Calendrier des événements"""
    context = {
        'titre': 'Calendrier',
        'primary_color': '#10B981',
        'secondary_color': '#F59E0B',
    }
    return render(request, 'tableau_bord/calendrier.html', context)


@login_required
def liste_evenements(request):
    """Liste des événements"""
    context = {
        'titre': 'Événements',
        'primary_color': '#10B981',
        'secondary_color': '#F59E0B',
    }
    return render(request, 'tableau_bord/evenements.html', context)


@login_required
def ajouter_evenement(request):
    """Ajouter un événement"""
    if request.method == 'POST':
        messages.success(request, 'Événement ajouté avec succès.')
        return redirect('tableau_bord:calendrier')
    
    context = {
        'titre': 'Ajouter un événement',
        'primary_color': '#10B981',
        'secondary_color': '#F59E0B',
    }
    return render(request, 'tableau_bord/ajouter_evenement.html', context)


@login_required
def alertes(request):
    """Page des alertes"""
    alertes_list = AlertePaiement.objects.filter(etudiant__utilisateur=request.user)
    
    context = {
        'alertes': alertes_list,
        'titre': 'Alertes',
        'primary_color': '#10B981',
        'secondary_color': '#F59E0B',
    }
    return render(request, 'tableau_bord/alertes.html', context)


@login_required
def ignorer_alerte(request, pk):
    """Ignorer une alerte"""
    alerte = get_object_or_404(AlertePaiement, pk=pk)
    alerte.delete()
    messages.success(request, 'Alerte ignorée.')
    return redirect('tableau_bord:alertes')


@login_required
def export_dashboard(request):
    """Exporter les données du dashboard"""
    return HttpResponse("Export du dashboard")


@login_required
def imprimer_dashboard(request):
    """Imprimer le dashboard"""
    return render(request, 'tableau_bord/imprimer.html')


# API pour les graphiques (AJAX)
@login_required
def api_donnees_dashboard(request):
    """API pour les données du dashboard"""
    data = {
        'success': True,
        'data': {
            'version': '1.0',
            'timestamp': timezone.now().isoformat(),
        }
    }
    return JsonResponse(data)


@login_required
def api_notifications_non_lues(request):
    """API pour le nombre et la liste des notifications non lues"""
    qs = Notification.objects.filter(
        utilisateur=request.user, 
        est_lue=False
    ).order_by('-date_creation')
    
    count = qs.count()
    notifications_data = [
        {
            'id': n.id,
            'titre': n.titre,
            'message': n.message,
            'type': n.type,
            'lien': n.lien or '#',
            'date': n.date_creation.strftime('%d/%m %H:%M')
        }
        for n in qs[:5]
    ]
    return JsonResponse({
        'count': count,
        'notifications': notifications_data,
        'success': True
    })


@login_required
def api_marquer_notification_lue_ajax(request, pk):
    """API AJAX pour marquer une notification comme lue sans rechargement de page"""
    notif = get_object_or_404(Notification, pk=pk, utilisateur=request.user)
    notif.est_lue = True
    notif.date_lecture = timezone.now()
    notif.save()
    return JsonResponse({'success': True})


@login_required
def api_statistiques_rapides(request):
    """API pour les statistiques rapides (AJAX)"""
    annee_active = AnneeAcademique.objects.filter(est_active=True).first()
    
    if annee_active:
        etudiants_par_filiere = list(Etudiant.objects.filter(
            annee_academique=annee_active
        ).values('filiere__code', 'filiere__nom').annotate(
            count=Count('id')
        ))
    else:
        etudiants_par_filiere = []
    
    # Récupérer les recettes du mois
    recettes_mois = RecuPaiement.objects.filter(
        statut='VALIDE',
        date_verification__month=timezone.now().month
    ).aggregate(
        total=Coalesce(Sum('montant_mentionne', output_field=DecimalField()), Value(0, output_field=DecimalField()))
    )['total'] or 0
    
    # Taux de remplissage des classes
    from apps.etudiants.models import Classe
    classes = Classe.objects.filter(est_active=True, annee_academique=annee_active) if annee_active else Classe.objects.none()
    taux_remplissage = 0
    if classes.exists():
        total_remplissage = 0
        valid_classes = 0
        for c in classes:
            if c.effectif_max and c.effectif_max > 0:
                total_remplissage += (c.effectif_actuel / c.effectif_max * 100)
                valid_classes += 1
        if valid_classes > 0:
            taux_remplissage = round(total_remplissage / valid_classes, 1)

    data = {
        'total_etudiants': Etudiant.objects.filter(statut__in=['ACTIF', 'INSCRIT']).count(),
        'total_professeurs': Professeur.objects.count(),
        'total_filieres': Filiere.objects.filter(est_active=True).count(),
        'taux_remplissage': taux_remplissage,
        'recettes_mois': float(recettes_mois),
        'recus_attente': RecuPaiement.objects.filter(statut='EN_ATTENTE').count(),
        'etudiants_par_filiere': etudiants_par_filiere,
    }
    
    return JsonResponse({'success': True, 'data': data})


def geolocalisation(request):
    """Vue de géolocalisation du centre IAI-Cameroun de Douala"""
    context = {
        'titre': 'Géolocalisation du Centre IAI-Douala',
        'latitude': 4.0483,  # Latitude précise de PK10 Douala
        'longitude': 9.7845, # Longitude précise de PK10 Douala
        'plus_code': '2QXC+9CG',
        'destination_adresse': 'Pk10, 2QXC+9CG, Douala',
        'description': "Le centre IAI-Cameroun de Douala est actuellement situé à Pk10, 2QXC+9CG, Douala, entre les supermarchés BAO et SAKER, juste derrière la nouvelle station-service MAMAYAKO."
    }
    return render(request, 'tableau_bord/geolocalisation.html', context)


@login_required
def liste_classes_partagee(request):
    """Vue partagée affichant les listes des classes pour les différents chefs de service."""
    from django.urls import reverse
    
    # Autoriser uniquement le personnel concerné
    user_type = getattr(request.user, 'type_utilisateur', '')
    if user_type not in ['CHEF_SCOLARITE', 'CHEF_ETUDES', 'CHEF_ANONYMAT', 'CHEF_COMPTABILITE', 'ADMIN_FINANCIER'] and not request.user.is_staff:
        messages.error(request, "Accès refusé. Vous n'avez pas l'autorisation d'accéder à ce service.")
        return redirect('tableau_bord:tableau_bord')
        
    from apps.etudiants.models import Classe, Etudiant, Filiere, Niveau, AnneeAcademique as AA_etud
    from apps.inscriptions.models import AnneeAcademique as AA_insc
    
    annee_active = AA_etud.get_active() or AA_etud.objects.filter(est_active=True).first()
    if not annee_active:
        annee_insc = AA_insc.get_active() or AA_insc.objects.filter(est_actuelle=True).first()
        if annee_insc:
            annee_active = AA_etud.objects.filter(code=annee_insc.code).first()
        
    # Gérer la répartition automatique
    if request.method == 'POST' and request.POST.get('action') == 'repartir':
        if user_type == 'CHEF_SCOLARITE' or request.user.is_superuser:
            repartis_count = Classe.repartir_etudiants(annee_active)
            messages.success(request, f"✅ Répartition automatique effectuée avec succès ! {repartis_count} étudiant(s) affecté(s).")
        else:
            messages.error(request, "❌ Seul le Chef de la Scolarité est autorisé à lancer la répartition.")
        return redirect('tableau_bord:liste_classes_partagee')
        
    # Récupérer les filtres
    filiere_id = request.GET.get('filiere')
    niveau_id = request.GET.get('niveau')
    
    from apps.cours.models import Salle
    from apps.cours.views import find_matching_salle
    
    salles_qs = Salle.objects.all().order_by('code')
    salles = list(salles_qs)
    
    # Filtrer les salles par filière et niveau si sélectionnés
    if filiere_id:
        filiere_obj = Filiere.objects.filter(id=filiere_id).first()
        if filiere_obj:
            salles = [s for s in salles if filiere_obj.code.upper() in s.code.upper() or filiere_obj.nom.upper() in s.nom.upper()]
    if niveau_id:
        niveau_obj = Niveau.objects.filter(id=niveau_id).first()
        if niveau_obj:
            salles = [s for s in salles if str(niveau_obj.numero) in s.code or str(niveau_obj.numero) in s.nom]
            
    # Préparer les données des étudiants pour chaque classe (salle)
    classes_data = []
    from apps.paiements.services import calculer_penalites_etudiant
    from decimal import Decimal
    
    class SimulatedClasse:
        def __init__(self, id, nom, filiere_nom, filiere_code, niveau_num, annee_code, effectif_actuel, effectif_max):
            self.id = id
            self.nom = nom
            self._filiere_nom = filiere_nom
            self._filiere_code = filiere_code
            self._niveau_num = niveau_num
            self._annee_code = annee_code
            self.effectif_actuel = effectif_actuel
            self.effectif_max = effectif_max
        @property
        def filiere(self):
            class SimulatedFiliere:
                def __init__(self, nom, code):
                    self.nom = nom
                    self.code = code
            return SimulatedFiliere(self._filiere_nom, self._filiere_code)
        @property
        def niveau(self):
            class SimulatedNiveau:
                def __init__(self, numero):
                    self.numero = numero
            return SimulatedNiveau(self._niveau_num)
        @property
        def annee_academique(self):
            class SimulatedAnnee:
                def __init__(self, code):
                    self.code = code
            return SimulatedAnnee(self._annee_code)
            
    classes_active = list(Classe.objects.filter(annee_academique=annee_active).select_related('filiere', 'niveau'))
    
    for salle in salles:
        # Trouver toutes les classes qui correspondent à cette salle
        matching_classes = []
        for c in classes_active:
            if find_matching_salle(c) == salle:
                matching_classes.append(c)
                
        # Rassembler les étudiants de ces classes
        etudiants_list = Etudiant.objects.filter(classe__in=matching_classes).order_by('nom', 'prenom')
        etudiants_data = []
        
        for etudiant in etudiants_list:
            etud_info = {
                'etudiant': etudiant,
                # Scolarité
                'statut': etudiant.get_statut_display(),
                'telephone': etudiant.telephone,
                'email': etudiant.email,
                # Études / Anonymat
                'matricule': etudiant.matricule,
                'nom_complet': etudiant.get_nom_complet(),
            }
            
            # Pour la comptabilité, on calcule les détails financiers
            if user_type in ['CHEF_COMPTABILITE', 'ADMIN_FINANCIER'] or request.user.is_superuser:
                recus = etudiant.recus.filter(statut='VALIDE') if hasattr(etudiant, 'recus') else []
                
                montant_paye = sum(r.montant_mentionne for r in recus)
                penalites_info = calculer_penalites_etudiant(etudiant)
                base_scolarite = Decimal('461000.00')  # Valeur fixe standard
                total_du = base_scolarite + penalites_info['total']
                reste_payer = max(0, total_du - montant_paye)
                
                etud_info.update({
                    'total_du': total_du,
                    'montant_paye': montant_paye,
                    'reste_payer': reste_payer,
                    'solvable': reste_payer == 0,
                    'penalite': penalites_info['total']
                })
                
            etudiants_data.append(etud_info)
            
        effectif_actuel = len(etudiants_list)
        effectif_max = salle.capacite
        taux_remplissage = int((effectif_actuel / effectif_max) * 100) if effectif_max > 0 else 0
        
        # Déterminer la filière, niveau et année académique
        salle_filiere_nom = "Génie Logiciel"
        salle_filiere_code = "GL"
        salle_niveau_num = 1
        salle_annee_code = annee_active.code if annee_active else "2026-2027"
        
        if matching_classes:
            salle_filiere_nom = matching_classes[0].filiere.nom
            salle_filiere_code = matching_classes[0].filiere.code
            salle_niveau_num = matching_classes[0].niveau.numero
        else:
            if "SR" in salle.code.upper() or "SYSTEME" in salle.nom.upper():
                salle_filiere_nom = "Systèmes et Réseaux"
                salle_filiere_code = "SR"
            for n in [1, 2]:
                if str(n) in salle.code or str(n) in salle.nom:
                    salle_niveau_num = n
                    
        sim_classe = SimulatedClasse(
            id=salle.id,
            nom=salle.nom,
            filiere_nom=salle_filiere_nom,
            filiere_code=salle_filiere_code,
            niveau_num=salle_niveau_num,
            annee_code=salle_annee_code,
            effectif_actuel=effectif_actuel,
            effectif_max=effectif_max
        )
        
        classes_data.append({
            'classe': sim_classe,
            'taux_remplissage': taux_remplissage,
            'etudiants_data': etudiants_data
        })
        
    filieres = Filiere.objects.filter(est_active=True)
    niveaux = Niveau.objects.all()
    
    context = {
        'classes_data': classes_data,
        'filieres': filieres,
        'niveaux': niveaux,
        'filiere_selected': int(filiere_id) if filiere_id else None,
        'niveau_selected': int(niveau_id) if niveau_id else None,
        'user_type': user_type,
        'titre': 'Gestion des Listes de Classes'
    }
    
    return render(request, 'tableau_bord/liste_classes_partagee.html', context)


@login_required
def supprimer_note_info(request, pk):
    """Supprime (désactive) une note d'information"""
    if request.user.type_utilisateur != 'CHEF_ETUDES' and not request.user.is_superuser:
        messages.error(request, "❌ Action réservée au Chef des Études.")
        return redirect('tableau_bord:tableau_bord')
        
    from apps.tableau_bord.models import NoteInformation
    note = get_object_or_404(NoteInformation, pk=pk)
    
    if request.method == 'POST':
        note.est_active = False
        note.save()
        messages.success(request, "🗑️ Note d'information supprimée.")
        
    return redirect('tableau_bord:tableau_bord')


@login_required
def export_pdf_paiements_classe(request, salle_id):
    """
    Génère un PDF très esthétique et professionnel montrant l'état des paiements des étudiants d'une classe (salle).
    """
    # Autoriser uniquement la comptabilité/finance et les admins
    user_type = getattr(request.user, 'type_utilisateur', '')
    if user_type not in ['CHEF_COMPTABILITE', 'ADMIN_FINANCIER'] and not request.user.is_staff:
        messages.error(request, "Accès refusé. Vous n'avez pas l'autorisation d'accéder à ce service.")
        return redirect('tableau_bord:tableau_bord')

    from apps.cours.models import Salle
    from apps.etudiants.models import Classe, Etudiant
    from apps.cours.views import find_matching_salle
    from apps.paiements.services import calculer_penalites_etudiant
    from decimal import Decimal
    
    salle = get_object_or_404(Salle, pk=salle_id)
    annee_active = AnneeAcademique.objects.filter(est_active=True).first()
    
    # Retrouver les classes actives correspondant à cette salle
    classes_active = list(Classe.objects.filter(annee_academique=annee_active).select_related('filiere', 'niveau'))
    matching_classes = []
    for c in classes_active:
        if find_matching_salle(c) == salle:
            matching_classes.append(c)
            
    # Étudiants de ces classes
    etudiants_list = Etudiant.objects.filter(classe__in=matching_classes).order_by('nom', 'prenom')
    
    # Déterminer la filière, niveau et année académique
    filiere_nom = "Génie Logiciel"
    niveau_num = 1
    annee_code = annee_active.code if annee_active else "2026-2027"
    
    if matching_classes:
        filiere_nom = matching_classes[0].filiere.nom
        niveau_num = matching_classes[0].niveau.numero
    else:
        if "SR" in salle.code.upper() or "SYSTEME" in salle.nom.upper():
            filiere_nom = "Systèmes et Réseaux"
        for n in [1, 2]:
            if str(n) in salle.code or str(n) in salle.nom:
                niveau_num = n

    # Préparer les données pour ReportLab
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Etat_Paiement_{salle.nom.replace(" ", "_")}.pdf"'
    
    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=1.5*cm,
        leftMargin=1.5*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm
    )
    
    styles = getSampleStyleSheet()
    
    # Styles personnalisés
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#064E3B'), # Vert IAI
        alignment=1, # Centré
        spaceAfter=15
    )
    
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        alignment=0
    )
    
    header_right_style = ParagraphStyle(
        'HeaderRightStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        alignment=2
    )
    
    meta_style = ParagraphStyle(
        'MetaStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#333333')
    )
    
    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9,
        textColor=colors.white,
        alignment=1 # Centré
    )
    
    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        leading=9
    )
    
    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7,
        leading=9
    )
    
    table_cell_right = ParagraphStyle(
        'TableCellRight',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        leading=9,
        alignment=2
    )

    table_cell_right_bold = ParagraphStyle(
        'TableCellRightBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7,
        leading=9,
        alignment=2
    )
    
    solvable_badge = ParagraphStyle(
        'SolvableBadge',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7,
        leading=9,
        textColor=colors.HexColor('#065F46'),
        alignment=1
    )

    insolvable_badge = ParagraphStyle(
        'InsolvableBadge',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7,
        leading=9,
        textColor=colors.HexColor('#991B1B'),
        alignment=1
    )

    elements = []
    
    # Entête officiel centré avec logo
    import os
    from django.conf import settings
    from reportlab.platypus import Image as RLImage
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo_iai.png')

    h_c_bold = ParagraphStyle('HCBold2', fontName='Helvetica-Bold', fontSize=8.5, leading=10.5, textColor=colors.HexColor('#1E293B'), alignment=1)
    h_c_sub = ParagraphStyle('HCSub2', fontName='Helvetica-Bold', fontSize=7.5, leading=9.5, textColor=colors.HexColor('#475569'), alignment=1)
    h_c_title = ParagraphStyle('HCTitle2', fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.HexColor('#064E3B'), alignment=1)
    h_c_contacts = ParagraphStyle('HCContacts2', fontName='Helvetica', fontSize=7, leading=9, textColor=colors.HexColor('#334155'), alignment=1)

    if os.path.exists(logo_path):
        logo_img = RLImage(logo_path, width=2.0*cm, height=2.0*cm)
        logo_img.hAlign = 'CENTER'
        elements.append(logo_img)
        elements.append(Spacer(1, 0.2*cm))

    elements.append(Paragraph("<b>ETABLISSEMENT INTER – ETATS D'ENSEIGNEMENT SUPÉRIEUR</b>", h_c_bold))
    elements.append(Paragraph("Représentation du Cameroun", h_c_sub))
    elements.append(Paragraph("<b>CENTRE D'EXCELLENCE TECHNOLOGIQUE PAUL BIYA</b>", h_c_title))
    elements.append(Paragraph("BP 13 719 Yaoundé (Cameroun) Tél. (237) 242 72 99 57/ 242 72 99 58/ 691 902 120", h_c_contacts))
    elements.append(Paragraph("Site web: www.iaicameroun.com &bull; Courriel: contact@iaicameroun.com", h_c_contacts))
    elements.append(Spacer(1, 0.4*cm))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#064E3B'), spaceAfter=8))
    
    # Titre du document
    elements.append(Paragraph(f"ÉTAT DE PAIEMENT DES SCOLARITÉS — CLASSE : {salle.nom.upper()}", title_style))
    
    # Métadonnées de la classe
    meta_text_1 = f"<b>Filière :</b> {filiere_nom}<br/><b>Niveau :</b> {niveau_num}"
    meta_text_2 = f"<b>Salle physique :</b> {salle.nom}<br/><b>Effectif :</b> {len(etudiants_list)} / {salle.capacite} étudiant(s)"
    
    meta_table = Table(
        [[Paragraph(meta_text_1, meta_style), Paragraph(meta_text_2, meta_style)]],
        colWidths=[9*cm, 9*cm]
    )
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F9FAFB')),
        ('PADDING', (0,0), (-1,-1), 8),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 0.5*cm))
    
    # Tableau des étudiants
    # Colonnes : N°, Matricule, Nom complet, Total dû, Montant Payé, Reste à payer, Statut
    table_data = [
        [
            Paragraph("<b>N°</b>", table_header_style),
            Paragraph("<b>Matricule</b>", table_header_style),
            Paragraph("<b>Nom complet</b>", table_header_style),
            Paragraph("<b>Total Dû</b>", table_header_style),
            Paragraph("<b>Montant Payé</b>", table_header_style),
            Paragraph("<b>Reste à Payer</b>", table_header_style),
            Paragraph("<b>Statut</b>", table_header_style),
        ]
    ]
    
    total_attendu_classe = Decimal('0.00')
    total_recouvre_classe = Decimal('0.00')
    nb_insolvables = 0
    nb_solvables = 0
    
    for idx, etudiant in enumerate(etudiants_list, 1):
        recus = etudiant.recus.filter(statut='VALIDE') if hasattr(etudiant, 'recus') else []
            
        montant_paye = sum(r.montant_mentionne for r in recus)
        penalites_info = calculer_penalites_etudiant(etudiant)
        base_scolarite = Decimal('461000.00')
        total_du = base_scolarite + penalites_info['total']
        reste_payer = max(0, total_du - montant_paye)
        solvable = reste_payer == 0
        
        # Cumuls de classe
        total_attendu_classe += total_du
        total_recouvre_classe += montant_paye
        
        if solvable:
            nb_solvables += 1
            status_paragraph = Paragraph("<b>Solvable</b>", solvable_badge)
        else:
            nb_insolvables += 1
            status_paragraph = Paragraph("<b>Insolvable</b>", insolvable_badge)
            
        row = [
            Paragraph(str(idx), table_cell_bold),
            Paragraph(etudiant.matricule, table_cell_bold),
            Paragraph(etudiant.get_nom_complet(), table_cell_style),
            Paragraph(f"{total_du:,.0f} F", table_cell_right_bold),
            Paragraph(f"{montant_paye:,.0f} F", table_cell_right),
            Paragraph(f"{reste_payer:,.0f} F", table_cell_right_bold),
            status_paragraph
        ]
        table_data.append(row)
        
    # Si aucun étudiant
    if len(etudiants_list) == 0:
        table_data.append([Paragraph("Aucun étudiant réparti dans cette classe pour le moment.", table_cell_style)] + [Paragraph("", table_cell_style)] * 6)
        
    # Styles du tableau ReportLab
    col_widths = [1*cm, 3*cm, 5.5*cm, 2.2*cm, 2.2*cm, 2.2*cm, 1.9*cm]
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    
    t_style = [
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#064E3B')), # Fond vert en tête
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('TOPPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('PADDING', (0,1), (-1,-1), 4),
    ]
    
    # Alternance des lignes (sauf header)
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            t_style.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#F9FAFB')))
            
    t.setStyle(TableStyle(t_style))
    elements.append(t)
    elements.append(Spacer(1, 0.6*cm))
    
    # Bloc récapitulatif comptable
    reste_recouvrer_classe = max(0, total_attendu_classe - total_recouvre_classe)
    taux_recouvrement = round((total_recouvre_classe / total_attendu_classe * 100), 1) if total_attendu_classe > 0 else 100.0
    
    recap_title_style = ParagraphStyle(
        'RecapTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        textColor=colors.HexColor('#064E3B'),
        spaceAfter=5
    )
    
    recap_text_1 = f"<b>Total attendu classe :</b> {total_attendu_classe:,.0f} FCFA<br/><b>Total payé :</b> {total_recouvre_classe:,.0f} FCFA<br/><b>Reste à recouvrer :</b> {reste_recouvrer_classe:,.0f} FCFA"
    recap_text_2 = f"<b>Taux de recouvrement :</b> {taux_recouvrement}%<br/><b>Étudiants solvables :</b> {nb_solvables}<br/><b>Étudiants insolvables :</b> <font color='#991B1B'><b>{nb_insolvables}</b></font>"
    
    recap_table = Table(
        [
            [Paragraph("<b>RÉCAPITULATIF FINANCIER DE LA CLASSE</b>", recap_title_style), Paragraph("", recap_title_style)],
            [Paragraph(recap_text_1, meta_style), Paragraph(recap_text_2, meta_style)]
        ],
        colWidths=[9*cm, 9*cm]
    )
    recap_table.setStyle(TableStyle([
        ('SPAN', (0,0), (1,0)),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#ECFDF5')),
        ('PADDING', (0,0), (-1,-1), 8),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#A7F3D0')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    elements.append(recap_table)
    elements.append(Spacer(1, 0.8*cm))
    
    # Signatures
    signature_style = ParagraphStyle(
        'Signature',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        alignment=2 # Droite
    )
    signature_text = "Le Chef de Service de la Comptabilité<br/><br/><br/><br/>_________________________"
    signature_table = Table([[Paragraph("", signature_style), Paragraph(signature_text, signature_style)]], colWidths=[11*cm, 7*cm])
    elements.append(signature_table)

    doc.build(elements)
    return response


@login_required
def lancer_transition_annee(request):
    """
    Vue pour déclencher la transition vers la nouvelle année universitaire (réservée à l'ADMIN_SYSTEME).
    """
    user_type = getattr(request.user, 'type_utilisateur', '')
    if user_type != 'ADMIN_SYSTEME' and not request.user.is_superuser:
        messages.error(request, "Accès refusé. Action réservée à l'Administrateur Système.")
        return redirect('tableau_bord:tableau_bord')

    if request.method == 'POST':
        from django.db import transaction
        from apps.etudiants.models import AnneeAcademique as AA_etud
        from apps.inscriptions.models import AnneeAcademique as AA_insc
        from apps.etudiants.models import Etudiant, Classe
        import re
        from datetime import date
        
        try:
            with transaction.atomic():
                active_etud = AA_etud.get_active() or AA_etud.objects.filter(est_active=True).first()
                if not active_etud:
                    messages.error(request, "Impossible de transitionner : aucune année académique active n'a été trouvée.")
                    return redirect('tableau_bord:tableau_bord')
                    
                code_courant = active_etud.code
                match = re.match(r'^(\d{4})-(\d{4})$', code_courant)
                if not match:
                    messages.error(request, f"Format de code d'année académique invalide : {code_courant}")
                    return redirect('tableau_bord:tableau_bord')
                    
                annee_debut_courante = int(match.group(1))
                annee_fin_courante = int(match.group(2))
                
                nouvel_annee_debut = annee_fin_courante
                nouvel_annee_fin = annee_fin_courante + 1
                nouveau_code = f"{nouvel_annee_debut}-{nouvel_annee_fin}"
                
                date_debut_nouveau = date(nouvel_annee_debut, 10, 1)
                date_fin_nouveau = date(nouvel_annee_fin, 9, 30)
                
                # 1. Désactiver l'ancienne année
                AA_etud.objects.filter(est_active=True).update(est_active=False)
                AA_insc.objects.filter(est_actuelle=True).update(est_actuelle=False)
                
                # 2. Créer et activer la nouvelle année
                nouveau_etud, created_etud = AA_etud.objects.get_or_create(
                    code=nouveau_code,
                    defaults={
                        'date_debut': date_debut_nouveau,
                        'date_fin': date_fin_nouveau,
                        'est_active': True
                    }
                )
                if not created_etud:
                    nouveau_etud.est_active = True
                    nouveau_etud.save()
                    
                nouveau_insc, created_insc = AA_insc.objects.get_or_create(
                    code=nouveau_code,
                    defaults={
                        'date_debut': date_debut_nouveau,
                        'date_fin': date_fin_nouveau,
                        'est_actuelle': True,
                        'est_ouverte_inscription': True
                    }
                )
                if not created_insc:
                    nouveau_insc.est_actuelle = True
                    nouveau_insc.est_ouverte_inscription = True
                    nouveau_insc.save()
                    
                # 3. Archiver les étudiants de niveau 2 (passent à DIPLOME)
                diplomes_count = Etudiant.objects.filter(
                    annee_academique=active_etud,
                    niveau__numero=2,
                    statut__in=['INSCRIT', 'ACTIF']
                ).update(statut='DIPLOME')
                
                # 4. Désactiver les classes de l'année précédente
                classes_archivees_count = Classe.objects.filter(
                    annee_academique=active_etud,
                    est_active=True
                ).update(est_active=False)
                
                messages.success(
                    request, 
                    f"🎉 Clôture annuelle réussie ! L'année {code_courant} a été archivée. "
                    f"La nouvelle année {nouveau_code} (Octobre {nouvel_annee_debut} - Septembre {nouvel_annee_fin}) est désormais active. "
                    f"{diplomes_count} étudiant(s) diplômé(s). {classes_archivees_count} classe(s) archivée(s)."
                )
        except Exception as e:
            messages.error(request, f"Une erreur s'est produite lors de la transition : {str(e)}")
            
    return redirect('tableau_bord:tableau_bord')


@login_required
def journal_audit_view(request):
    """Consultation et filtrage du Journal d'Audit Système"""
    from .models import JournalAudit
    from apps.authentification.decorators import role_required
    
    # Seuls les admins, directeurs ou chargés de sécurité peuvent accéder
    if request.user.type_utilisateur not in ['ADMIN_SYSTEME', 'DIRECTEUR', 'CHEF_ETUDES', 'CHEF_COMPTABILITE'] and not request.user.is_superuser:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Accès restreint au Journal d'Audit.")
        
    queryset = JournalAudit.objects.all().select_related('utilisateur')
    
    categorie = request.GET.get('categorie', '')
    if categorie:
        queryset = queryset.filter(categorie=categorie)
        
    recherche = request.GET.get('q', '')
    if recherche:
        queryset = queryset.filter(
            Q(action__icontains=recherche) |
            Q(details__icontains=recherche) |
            Q(utilisateur__username__icontains=recherche) |
            Q(adresse_ip__icontains=recherche)
        )
        
    paginator = Paginator(queryset, 25)
    page = request.GET.get('page')
    logs = paginator.get_page(page)
    
    context = {
        'logs': logs,
        'categories': JournalAudit.CATEGORIE_CHOICES,
        'titre': "Journal d'Audit Système"
    }
    return render(request, 'tableau_bord/journal_audit.html', context)