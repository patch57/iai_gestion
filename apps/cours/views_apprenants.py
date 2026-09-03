from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse

from apps.etudiants.models import Apprenant, Formation
from apps.notes.models import NoteApprenant
from apps.notes.forms import NoteApprenantForm
from .models import SupportPedagogiqueApprenant, EmploiDuTempsApprenant
from .forms import SupportPedagogiqueApprenantForm, EmploiDuTempsApprenantForm


@login_required
def liste_apprenants_categories(request):
    """Consulter et imprimer la liste des apprenants par catégories"""
    if request.user.type_utilisateur not in ['ENSEIGNANT', 'PROFESSEUR', 'FORMATEUR', 'CHEF_FORMATION_CONTINUE', 'ADMIN_SYSTEME', 'DIRECTEUR', 'CHEF_ETUDES']:
        messages.error(request, "Accès refusé.")
        return redirect('tableau_bord:tableau_bord')
        
    apprenants = Apprenant.objects.all().prefetch_related('formations')
    
    # Filtres
    type_formation = request.GET.get('type_formation', '')
    if type_formation:
        apprenants = apprenants.filter(formations__type_formation=type_formation).distinct()
        
    module = request.GET.get('module', '')
    if module:
        apprenants = apprenants.filter(formations__nom=module).distinct()
        
    niveau = request.GET.get('niveau', '')
    if niveau:
        apprenants = apprenants.filter(niveau_etude__icontains=niveau)
        
    # Liste des modules et types pour le formulaire de filtrage
    formations = Formation.objects.all()
    
    context = {
        'apprenants': apprenants,
        'formations': formations,
        'type_formation_choices': Formation.TYPES,
        'module_choices': Formation.NOM_CHOICES,
        'titre': 'Registre des Apprenants'
    }
    return render(request, 'cours/apprenants/liste_apprenants.html', context)


@login_required
@login_required
def gestion_matieres_formation(request):
    """Configuration et définition des matières par type/module de formation continue et certifiante"""
    if request.user.type_utilisateur not in ['CHEF_FORMATION_CONTINUE', 'ADMIN_SYSTEME', 'DIRECTEUR', 'CHEF_ETUDES', 'FORMATEUR', 'ENSEIGNANT']:
        messages.error(request, "Accès réservé aux responsables de la formation.")
        return redirect('tableau_bord:tableau_bord')

    from apps.cours.models import MatiereFormation
    formation_id = request.GET.get('formation_id', '')
    formation = None
    if formation_id:
        formation = get_object_or_404(Formation, id=formation_id)

    if request.method == 'POST':
        action = request.POST.get('action', 'ajouter')
        if action == 'supprimer':
            matiere_id = request.POST.get('matiere_id')
            mat = get_object_or_404(MatiereFormation, id=matiere_id)
            nom_mat = mat.nom
            mat.delete()
            messages.success(request, f"🗑️ Matière '{nom_mat}' supprimée avec succès.")
        else:
            form_id = request.POST.get('formation_id')
            target_form = get_object_or_404(Formation, id=form_id)
            nom_matiere = request.POST.get('nom_matiere', '').strip()
            coeff_val = float(request.POST.get('coefficient', 1.0))
            code_mat = request.POST.get('code_matiere', '').strip()

            if nom_matiere:
                MatiereFormation.objects.update_or_create(
                    formation=target_form,
                    nom=nom_matiere,
                    defaults={
                        'coefficient': coeff_val,
                        'code': code_mat,
                        'est_active': True
                    }
                )
                messages.success(request, f"✅ Matière '{nom_matiere}' (Coeff {coeff_val}) configurée pour {target_form.get_nom_display()}.")

        redirect_url = f"{request.path}?formation_id={formation_id}" if formation_id else request.path
        return redirect(redirect_url)

    matieres = formation.matieres.filter(est_active=True) if formation else MatiereFormation.objects.all()
    formations = Formation.objects.filter(est_active=True)

    context = {
        'formations': formations,
        'formation_selectionnee': formation,
        'matieres': matieres,
        'titre': 'Gestion des Matières par Formation'
    }
    return render(request, 'cours/apprenants/gestion_matieres.html', context)


@login_required
def saisir_notes_apprenants(request):
    """Saisie des notes d'évaluation multi-matières des apprenants avec calcul automatique des moyennes"""
    if request.user.type_utilisateur not in ['ENSEIGNANT', 'PROFESSEUR', 'FORMATEUR', 'CHEF_FORMATION_CONTINUE', 'ADMIN_SYSTEME', 'DIRECTEUR', 'CHEF_ETUDES']:
        messages.error(request, "Accès refusé.")
        return redirect('tableau_bord:tableau_bord')

    from apps.cours.models import MatiereFormation
    formation_id = request.GET.get('formation_id', '')
    formation = None
    apprenants = []
    matieres = []

    if formation_id:
        formation = get_object_or_404(Formation, id=formation_id)
        apprenants = Apprenant.objects.filter(formations=formation)
        matieres = list(formation.matieres.filter(est_active=True))

        # Si aucune matière n'est définie, créer des matières par défaut pour ce module
        if not matieres:
            m1 = MatiereFormation.objects.create(formation=formation, nom="Évaluation Théorique", coefficient=1.0)
            m2 = MatiereFormation.objects.create(formation=formation, nom="Travaux Pratiques / Projet", coefficient=2.0)
            matieres = [m1, m2]

    if request.method == 'POST' and formation:
        compteur = 0
        for key, value in request.POST.items():
            if key.startswith('note_'):
                parts = key.split('_')
                if len(parts) >= 3:
                    apprenant_id = parts[1]
                    matiere_id = parts[2]
                    note_val = value.strip().replace(',', '.')
                    commentaire = request.POST.get(f'commentaire_{apprenant_id}_{matiere_id}', '')

                    if note_val != '':
                        try:
                            apprenant_obj = Apprenant.objects.get(id=apprenant_id)
                            matiere_obj = MatiereFormation.objects.get(id=matiere_id)
                            val_float = float(note_val)

                            NoteApprenant.objects.update_or_create(
                                apprenant=apprenant_obj,
                                formation=formation,
                                matiere=matiere_obj,
                                defaults={
                                    'formateur': request.user,
                                    'note': val_float,
                                    'commentaire': commentaire
                                }
                            )
                            compteur += 1
                        except Exception as e:
                            messages.error(request, f"Erreur de saisie : {str(e)}")

        messages.success(request, f"✅ {compteur} note(s) par matière enregistrée(s) avec succès. Les moyennes ont été recalculées.")
        return redirect(f"{request.path}?formation_id={formation.id}")

    # Structuration des données d'apprenants avec leurs notes par matière et moyenne générale
    donnees_apprenants = []
    if formation:
        notes_qs = NoteApprenant.objects.filter(formation=formation).select_related('apprenant', 'matiere')
        dict_notes = {(n.apprenant_id, n.matiere_id): n for n in notes_qs}

        for app in apprenants:
            notes_row = []
            total_points = 0.0
            total_coeffs = 0.0

            for mat in matieres:
                n_obj = dict_notes.get((app.id, mat.id))
                val_note = float(n_obj.note) if n_obj else None
                val_note_str = str(val_note).replace(',', '.') if val_note is not None else ''
                comment = n_obj.commentaire if n_obj else ''

                if val_note is not None:
                    coeff = float(mat.coefficient)
                    total_points += val_note * coeff
                    total_coeffs += coeff

                notes_row.append({
                    'matiere_id': mat.id,
                    'matiere_nom': mat.nom,
                    'coefficient': mat.coefficient,
                    'note': val_note,
                    'note_str': val_note_str,
                    'commentaire': comment
                })

            moyenne = round(total_points / total_coeffs, 2) if total_coeffs > 0 else None
            statut_decision = 'Admis(e)' if (moyenne is not None and moyenne >= 10.0) else ('Ajourné(e)' if moyenne is not None else 'En attente')
            statut_color = 'bg-emerald-100 text-emerald-800 border-emerald-200' if (moyenne is not None and moyenne >= 10.0) else ('bg-rose-100 text-rose-800 border-rose-200' if moyenne is not None else 'bg-gray-100 text-gray-700 border-gray-200')

            donnees_apprenants.append({
                'apprenant': app,
                'notes_row': notes_row,
                'moyenne': moyenne,
                'statut_decision': statut_decision,
                'statut_color': statut_color
            })

    formations = Formation.objects.filter(est_active=True)

    context = {
        'formations': formations,
        'formation_selectionnee': formation,
        'matieres': matieres,
        'donnees_apprenants': donnees_apprenants,
        'titre': 'Saisie Multi-Matières & Moyennes des Apprenants'
    }
    return render(request, 'cours/apprenants/saisie_notes.html', context)



@login_required
def ajouter_support_apprenant(request):
    """Dépôt de supports de cours ciblés pour les apprenants"""
    if request.user.type_utilisateur not in ['ENSEIGNANT', 'PROFESSEUR', 'FORMATEUR', 'CHEF_FORMATION_CONTINUE', 'ADMIN_SYSTEME', 'DIRECTEUR', 'CHEF_ETUDES']:
        messages.error(request, "Accès refusé.")
        return redirect('tableau_bord:tableau_bord')
        
    if request.method == 'POST':
        form = SupportPedagogiqueApprenantForm(request.POST, request.FILES)
        if form.is_valid():
            support = form.save(commit=False)
            support.formateur = request.user
            support.save()

            # --- Envoi des notifications Tri-Canal pour remise physique des TP/TD ---
            if support.type_document in ['TP', 'TD'] and support.date_limite_remise_physique:
                from apps.etudiants.models import Apprenant, Etudiant
                from apps.tableau_bord.models import Notification
                from apps.tableau_bord.whatsapp_service import WhatsAppService
                from django.core.mail import send_mail
                from django.conf import settings

                date_str = support.date_limite_remise_physique.strftime('%d/%m/%Y')
                titre_notif = f"📌 Remise physique {support.type_document} : {support.titre}"
                msg_notif = (
                    f"Le sujet de {support.get_type_document_display()} '{support.titre}' a été mis en ligne par le formateur {request.user.get_full_name() or request.user.username}.\n"
                    f"⚠️ DATE LIMITE DE REMISE PHYSIQUE OBLIGATOIRE : {date_str}."
                )
                site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')

                # 1. CIBLAGE DES APPRENANTS CONCERNÉS (Formation Continue & Certifiante)
                apprenants_qs = Apprenant.objects.all().prefetch_related('formations')
                if support.type_formation != 'TOUS':
                    apprenants_qs = apprenants_qs.filter(formations__type_formation=support.type_formation)
                if support.module_formation != 'TOUS':
                    apprenants_qs = apprenants_qs.filter(formations__nom=support.module_formation)
                if support.niveau_etude:
                    apprenants_qs = apprenants_qs.filter(niveau_etude__icontains=support.niveau_etude)
                apprenants_qs = apprenants_qs.distinct()

                for app in apprenants_qs:
                    if app.utilisateur:
                        Notification.objects.create(
                            utilisateur=app.utilisateur,
                            type='AVERTISSEMENT',
                            titre=titre_notif,
                            message=msg_notif,
                            lien='/cours/apprenants/supports/'
                        )
                    dest_email = app.email or (app.utilisateur.email if app.utilisateur else None)
                    if dest_email:
                        try:
                            send_mail(
                                subject=f"{getattr(settings, 'EMAIL_SUBJECT_PREFIX', '[IAI-Cameroun] ')}{titre_notif}",
                                message=f"Bonjour {app.nom_complet},\n\n{msg_notif}\n\nConsultez le document : {site_url}/cours/apprenants/supports/",
                                from_email=settings.DEFAULT_FROM_EMAIL,
                                recipient_list=[dest_email],
                                fail_silently=True
                            )
                        except Exception:
                            pass
                    tel = getattr(app, 'contact', '') or getattr(app, 'telephone', '') or (app.utilisateur.telephone if hasattr(app.utilisateur, 'telephone') else '')
                    if tel:
                        try:
                            WhatsAppService.envoyer_message(
                                tel,
                                f"*IAI-CAMEROUN (Douala)* 📌\n*{support.get_type_document_display()} - Remise physique*\n\nBonjour {app.nom_complet},\n{msg_notif}\n\nDocument : {site_url}/cours/apprenants/supports/"
                            )
                        except Exception:
                            pass

            messages.success(request, "✅ Le support pédagogique a été chargé et les étudiants ont été notifiés.")
            return redirect('cours:liste_supports_apprenant')
    else:
        form = SupportPedagogiqueApprenantForm()
        
    context = {
        'form': form,
        'titre': 'Charger un support de formation'
    }
    return render(request, 'cours/apprenants/supports.html', context)


@login_required
def liste_supports_apprenant(request):
    """Affiche la liste des supports de formation (cours/TP/TD) accessibles"""
    user = request.user
    role = user.type_utilisateur
    
    supports = SupportPedagogiqueApprenant.objects.all().select_related('formateur')
    
    # Si c'est un apprenant, on filtre selon son profil et ses inscriptions
    if role == 'APPRENANT':
        apprenant = getattr(user, 'profil_apprenant', None)
        if apprenant:
            formations_apprenant = apprenant.formations.all()
            modules_noms = [f.nom for f in formations_apprenant]
            types_formations = [f.type_formation for f in formations_apprenant]
            
            supports = supports.filter(
                (Q(module_formation__in=modules_noms) | Q(module_formation='TOUS')) &
                (Q(type_formation__in=types_formations) | Q(type_formation='TOUS'))
            )
            if apprenant.niveau_etude:
                supports = supports.filter(Q(niveau_etude=apprenant.niveau_etude) | Q(niveau_etude=''))
        else:
            supports = supports.none()
    elif role in ['ENSEIGNANT', 'PROFESSEUR', 'FORMATEUR']:
        supports = supports.filter(formateur=user)
    elif role == 'CHEF_FORMATION_CONTINUE':
        # Le Chef de Service voit tous les supports de formation continue
        supports = supports.all()
        
    context = {
        'supports': supports,
        'titre': 'Supports de Formation'
    }
    return render(request, 'cours/apprenants/liste_supports.html', context)


@login_required
def supprimer_support_apprenant(request, pk):
    """Suppression d'un support de formation continue par son formateur ou l'administration"""
    support = get_object_or_404(SupportPedagogiqueApprenant, pk=pk)
    user = request.user
    
    is_author = (support.formateur == user)
    is_admin = user.is_superuser or user.type_utilisateur in ['ADMIN_SYSTEME', 'CHEF_FORMATION_CONTINUE', 'CHEF_ETUDES']
    
    if not (is_author or is_admin):
        messages.error(request, "Vous n'avez pas la permission de supprimer ce support.")
        return redirect('cours:liste_supports_apprenant')
        
    titre = support.titre
    support.delete()
    messages.success(request, f"Le support '{titre}' a été supprimé avec succès et retiré de l'espace des apprenants.")
    return redirect('cours:liste_supports_apprenant')


@login_required
def creer_emploi_du_temps_apprenant(request):
    """Établir et publier un emploi du temps pour la Formation Continue & Certifiante avec notifications ciblées"""
    if request.user.type_utilisateur not in ['CHEF_FORMATION_CONTINUE', 'ADMIN_SYSTEME', 'DIRECTEUR', 'CHEF_ETUDES']:
        messages.error(request, "Accès refusé. Seul le Chef de la Formation Continue peut publier des emplois du temps ciblés.")
        return redirect('tableau_bord:tableau_bord')
        
    if request.method == 'POST':
        form = EmploiDuTempsApprenantForm(request.POST, request.FILES)
        if form.is_valid():
            edt = form.save(commit=False)
            edt.cree_par = request.user
            edt.save()
            
            # --- Envoi des notifications Tri-Canal (In-App, Email, WhatsApp) STRICTEMENT CIBLÉES ---
            if edt.est_publie:
                from apps.etudiants.models import Apprenant
                from apps.tableau_bord.models import Notification
                from apps.tableau_bord.whatsapp_service import WhatsAppService
                from django.core.mail import send_mail
                from django.conf import settings
                from django.contrib.auth import get_user_model
                
                User = get_user_model()
                site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
                date_debut_str = edt.date_debut.strftime('%d/%m/%Y')
                date_fin_str = edt.date_fin.strftime('%d/%m/%Y')
                
                titre_notif = f"📅 Nouvel Emploi du Temps Publié : {edt.titre}"
                msg_notif = (
                    f"L'emploi du temps pour {edt.get_type_formation_display()} - {edt.get_module_formation_display()} "
                    f"pour la période du {date_debut_str} au {date_fin_str} a été officiellement publié."
                )
                
                # 1. CIBLAGE APPRENANTS CONCERNÉS
                apprenants_qs = Apprenant.objects.all().prefetch_related('formations')
                if edt.type_formation != 'TOUS':
                    apprenants_qs = apprenants_qs.filter(formations__type_formation=edt.type_formation)
                if edt.module_formation != 'TOUS':
                    apprenants_qs = apprenants_qs.filter(formations__nom=edt.module_formation)
                if edt.niveau_etude:
                    apprenants_qs = apprenants_qs.filter(niveau_etude__icontains=edt.niveau_etude)
                apprenants_qs = apprenants_qs.distinct()

                for app in apprenants_qs:
                    if app.utilisateur:
                        Notification.objects.create(
                            utilisateur=app.utilisateur,
                            type='INFO',
                            titre=titre_notif,
                            message=msg_notif,
                            lien='/cours/apprenants/emploi-du-temps/'
                        )
                    dest_email = app.email or (app.utilisateur.email if app.utilisateur else None)
                    if dest_email:
                        try:
                            send_mail(
                                subject=f"{getattr(settings, 'EMAIL_SUBJECT_PREFIX', '[IAI-Cameroun] ')}{titre_notif}",
                                message=f"Bonjour {app.nom_complet},\n\n{msg_notif}\n\nConsultez votre emploi du temps : {site_url}/cours/apprenants/emploi-du-temps/",
                                from_email=settings.DEFAULT_FROM_EMAIL,
                                recipient_list=[dest_email],
                                fail_silently=True
                            )
                        except Exception:
                            pass
                    tel = getattr(app, 'contact', '') or getattr(app, 'telephone', '') or (app.utilisateur.telephone if hasattr(app.utilisateur, 'telephone') else '')
                    if tel:
                        try:
                            WhatsAppService.envoyer_message(
                                tel,
                                f"*IAI-CAMEROUN (Douala)* 📅\n*Publication d'Emploi du Temps Apprenant*\n\nBonjour {app.nom_complet},\n{msg_notif}\n\nLien : {site_url}/cours/apprenants/emploi-du-temps/"
                            )
                        except Exception:
                            pass
                
                # 2. CIBLAGE FORMATEURS / ENSEIGNANTS
                formateurs = User.objects.filter(type_utilisateur__in=['FORMATEUR', 'ENSEIGNANT', 'PROFESSEUR'], est_actif=True)
                for formateur in formateurs:
                    Notification.objects.create(
                        utilisateur=formateur,
                        type='INFO',
                        titre=titre_notif,
                        message=msg_notif,
                        lien='/cours/apprenants/emploi-du-temps/'
                    )
                    if formateur.email:
                        try:
                            send_mail(
                                subject=f"{getattr(settings, 'EMAIL_SUBJECT_PREFIX', '[IAI-Cameroun] ')}{titre_notif}",
                                message=f"Bonjour {formateur.get_full_name() or formateur.username},\n\n{msg_notif}\n\nConsultez le planning : {site_url}/cours/apprenants/emploi-du-temps/",
                                from_email=settings.DEFAULT_FROM_EMAIL,
                                recipient_list=[formateur.email],
                                fail_silently=True
                            )
                        except Exception:
                            pass

            messages.success(request, "✅ L'emploi du temps a été publié et transmis aux apprenants et formateurs concernés.")
            return redirect('cours:liste_emplois_du_temps_apprenant')
    else:
        form = EmploiDuTempsApprenantForm()
        
    context = {
        'form': form,
        'titre': 'Publier un Emploi du Temps Apprenant'
    }
    return render(request, 'cours/apprenants/emploi_du_temps_form.html', context)


@login_required
def liste_emplois_du_temps_apprenant(request):
    """Affiche la liste des emplois du temps filtrée strictement selon le rôle de l'utilisateur"""
    user = request.user
    role = user.type_utilisateur
    
    emplois = EmploiDuTempsApprenant.objects.filter(est_publie=True)
    
    # 1. APPRENANTS : Filtrage strict selon les formations et le module inscrits
    if role == 'APPRENANT':
        apprenant = getattr(user, 'profil_apprenant', None)
        if apprenant:
            formations_apprenant = apprenant.formations.all()
            modules_noms = [f.nom for f in formations_apprenant]
            types_formations = [f.type_formation for f in formations_apprenant]
            
            emplois = emplois.filter(
                (Q(module_formation__in=modules_noms) | Q(module_formation='TOUS')) &
                (Q(type_formation__in=types_formations) | Q(type_formation='TOUS'))
            )
            if apprenant.niveau_etude:
                emplois = emplois.filter(Q(niveau_etude__icontains=apprenant.niveau_etude) | Q(niveau_etude=''))
        else:
            emplois = emplois.none()
    elif role in ['ENSEIGNANT', 'PROFESSEUR', 'FORMATEUR']:
        emplois = emplois.all()
    elif role in ['CHEF_FORMATION_CONTINUE', 'ADMIN_SYSTEME', 'DIRECTEUR', 'CHEF_ETUDES']:
        emplois = EmploiDuTempsApprenant.objects.all()

    context = {
        'emplois': emplois,
        'titre': 'Emplois du Temps Apprenants'
    }
    return render(request, 'cours/apprenants/liste_emplois_du_temps.html', context)


@login_required
def supprimer_emploi_du_temps_apprenant(request, pk):
    """Suppression d'un emploi du temps d'apprenant par les responsables"""
    if request.user.type_utilisateur not in ['CHEF_FORMATION_CONTINUE', 'ADMIN_SYSTEME', 'DIRECTEUR', 'CHEF_ETUDES']:
        messages.error(request, "Permission insuffisante.")
        return redirect('cours:liste_emplois_du_temps_apprenant')

    edt = get_object_or_404(EmploiDuTempsApprenant, pk=pk)
    titre_edt = edt.titre
    edt.delete()
    messages.success(request, f"🗑️ L'emploi du temps '{titre_edt}' a été supprimé avec succès.")
    return redirect('cours:liste_emplois_du_temps_apprenant')

