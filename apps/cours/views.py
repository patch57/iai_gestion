"""
Vues pour la gestion des cours
IAI-Cameroun - Centre de Douala
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from apps.authentification.decorators import role_required
from django.contrib import messages
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.utils import timezone

from .models import Salle, Matiere, Cours, SeanceCours, Presence, RessourceCours, EmploiDuTemps
from .forms import SalleForm, MatiereForm, CoursForm, SeanceCoursForm, RessourceCoursForm, AttributionMatiereForm
from apps.etudiants.models import Filiere


@login_required
def liste_cours(request):
    """Liste des cours & Programme Quotidien extrait de l'emploi du temps officiel (Section Cours Sidebar)"""
    from apps.cours.models import EmploiDuTempsHebdomadaire, CreneauEmploiDuTemps, Salle
    from apps.etudiants.models import Etudiant, Filiere, Niveau
    from django.utils import timezone
    from django.db.models import Q
    
    today = timezone.now().date()
    weekday_num = today.weekday()
    
    JOUR_MAP = {
        0: 'LUNDI', 1: 'MARDI', 2: 'MERCREDI', 3: 'JEUDI', 4: 'VENDREDI', 5: 'SAMEDI'
    }
    JOUR_NOMS = {
        0: 'Lundi', 1: 'Mardi', 2: 'Mercredi', 3: 'Jeudi', 4: 'Vendredi', 5: 'Samedi', 6: 'Dimanche'
    }
    JOUR_REV_MAP = {
        'LUNDI': 'Lundi', 'MARDI': 'Mardi', 'MERCREDI': 'Mercredi',
        'JEUDI': 'Jeudi', 'VENDREDI': 'Vendredi', 'SAMEDI': 'Samedi'
    }
    
    jour_choisi = request.GET.get('jour', '').upper()
    if jour_choisi in JOUR_REV_MAP:
        jour_code_actuel = jour_choisi
        nom_jour_actuel = JOUR_REV_MAP[jour_choisi]
    else:
        jour_code_actuel = JOUR_MAP.get(weekday_num, 'LUNDI')
        nom_jour_actuel = JOUR_NOMS.get(weekday_num, 'Lundi')
    
    user = request.user
    etudiant = getattr(user, 'etudiant_profile', None) if hasattr(user, 'etudiant_profile') else None
    if not etudiant:
        etudiant = Etudiant.objects.filter(utilisateur=user).first()
        
    is_professeur = (getattr(user, 'type_utilisateur', None) == 'PROFESSEUR')

    filiere_id = request.GET.get('filiere', '')
    niveau_id = request.GET.get('niveau', '')
    salle_id = request.GET.get('salle', '')

    filiere_obj = Filiere.objects.filter(id=filiere_id).first() if filiere_id else None
    niveau_obj = Niveau.objects.filter(id=niveau_id).first() if niveau_id else None
    salle_obj = Salle.objects.filter(id=salle_id).first() if salle_id else None

    # Base des créneaux pour la journée
    creneaux_base = CreneauEmploiDuTemps.objects.filter(jour=jour_code_actuel).exclude(type_evenement='PAUSE')

    if filiere_obj:
        creneaux_base = creneaux_base.filter(emploi_du_temps__filiere=filiere_obj)

    if niveau_obj:
        niveau_num = str(niveau_obj.numero)
        creneaux_base = creneaux_base.filter(
            Q(emploi_du_temps__niveau=f"LEVEL_{niveau_num}") | 
            Q(emploi_du_temps__niveau=f"LEVEL {niveau_num}") | 
            Q(emploi_du_temps__niveau__icontains=niveau_num)
        )

    if salle_obj:
        creneaux_base = creneaux_base.filter(
            Q(emploi_du_temps__salle=salle_obj) | Q(salle_nom__icontains=salle_obj.code) | Q(salle_nom__icontains=salle_obj.nom)
        )

    is_etudiant = bool(etudiant or getattr(user, 'type_utilisateur', '') in ['ETUDIANT', 'APPRENANT'])

    # Filtrage automatique pour l'étudiant connecté (selon sa salle ou filière/niveau)
    if is_etudiant and etudiant and not (filiere_obj or niveau_obj or salle_obj or user.is_staff or user.is_superuser):
        salle_etu = getattr(etudiant, 'salle', None)
        if salle_etu:
            creneaux_base = creneaux_base.filter(
                Q(emploi_du_temps__salle=salle_etu) | 
                Q(salle_nom__icontains=salle_etu.code) | 
                Q(salle_nom__icontains=salle_etu.nom)
            )
        elif etudiant.filiere:
            creneaux_base = creneaux_base.filter(emploi_du_temps__filiere=etudiant.filiere)
            if etudiant.niveau:
                niveau_num = str(etudiant.niveau.numero)
                creneaux_base = creneaux_base.filter(
                    Q(emploi_du_temps__niveau=f"LEVEL_{niveau_num}") | 
                    Q(emploi_du_temps__niveau=f"LEVEL {niveau_num}") | 
                    Q(emploi_du_temps__niveau__icontains=niveau_num)
                )

    if not filiere_obj and not niveau_obj and not salle_obj and is_professeur:
        nom_prof = user.get_full_name() or user.username
        last_name = user.last_name or nom_prof
        creneaux_du_jour = creneaux_base.filter(
            Q(enseignant_nom__icontains=last_name) | Q(enseignant_nom__icontains=user.username)
        ).order_by('plage', 'id')

        if not creneaux_du_jour.exists():
            creneaux_du_jour = creneaux_base.all().order_by('plage', 'id')
    else:
        creneaux_du_jour = creneaux_base.all().order_by('plage', 'id')

    filieres = Filiere.objects.filter(est_active=True)
    niveaux = Niveau.objects.all().order_by('numero')
    salles = Salle.objects.filter(est_disponible=True).order_by('nom')
    
    # Chargement des supports pédagogiques (Cours, TP, TD)
    from apps.cours.models import RessourceCours
    if etudiant and etudiant.filiere:
        salle_etu = getattr(etudiant, 'salle', None)
        if salle_etu:
            ressources = RessourceCours.objects.filter(
                Q(salle=salle_etu) | Q(salle__isnull=True, cours__filiere=etudiant.filiere)
            ).select_related('cours', 'cours__matiere').order_by('-date_ajout')
        else:
            ressources = RessourceCours.objects.filter(
                Q(cours__filiere=etudiant.filiere) | Q(cours__isnull=True)
            ).select_related('cours', 'cours__matiere').order_by('-date_ajout')
    elif filiere_obj:
        ressources = RessourceCours.objects.filter(
            Q(cours__filiere=filiere_obj) | Q(cours__isnull=True)
        ).select_related('cours', 'cours__matiere').order_by('-date_ajout')
    else:
        ressources = RessourceCours.objects.select_related('cours', 'cours__matiere').order_by('-date_ajout')[:20]

    context = {
        'creneaux_du_jour': creneaux_du_jour,
        'nom_jour_actuel': nom_jour_actuel,
        'jour_code_actuel': jour_code_actuel,
        'filiere_selectionnee': filiere_obj,
        'niveau_selectionne': niveau_obj,
        'salle_selectionnee': salle_obj,
        'filieres': filieres,
        'niveaux': niveaux,
        'salles': salles,
        'etudiant': etudiant,
        'is_etudiant': is_etudiant,
        'is_professeur': is_professeur,
        'ressources': ressources,
        'titre': 'Programme Quotidien & Cours'
    }
    return render(request, 'cours/liste.html', context)



@login_required
def detail_cours(request, pk):
    """Détail d'un cours"""
    cours = get_object_or_404(Cours, pk=pk)
    
    # Séances
    seances = SeanceCours.objects.filter(cours=cours).order_by('-date')
    
    # Étudiants inscrits
    inscriptions = cours.inscriptions_cours.filter(est_actif=True).select_related('etudiant').order_by('etudiant__nom', 'etudiant__prenom')
    
    # Ressources
    ressources = RessourceCours.objects.filter(cours=cours)
    
    context = {
        'cours': cours,
        'seances': seances,
        'inscriptions': inscriptions,
        'ressources': ressources,
        'titre': str(cours)
    }
    return render(request, 'cours/detail.html', context)


@login_required
@permission_required('cours.add_cours', raise_exception=True)
def ajouter_cours(request):
    """Ajouter un nouveau cours"""
    if request.method == 'POST':
        form = CoursForm(request.POST)
        if form.is_valid():
            cours = form.save()
            messages.success(request, f'Le cours {cours} a été créé avec succès.')
            return redirect('detail_cours', pk=cours.pk)
    else:
        form = CoursForm()
    
    context = {
        'form': form,
        'titre': 'Nouveau Cours'
    }
    return render(request, 'cours/form.html', context)


@login_required
@permission_required('cours.change_cours', raise_exception=True)
def modifier_cours(request, pk):
    """Modifier un cours"""
    cours = get_object_or_404(Cours, pk=pk)
    
    if request.method == 'POST':
        form = CoursForm(request.POST, instance=cours)
        if form.is_valid():
            cours = form.save()
            messages.success(request, f'Le cours {cours} a été modifié avec succès.')
            return redirect('detail_cours', pk=cours.pk)
    else:
        form = CoursForm(instance=cours)
    
    context = {
        'form': form,
        'cours': cours,
        'titre': f'Modifier {cours}'
    }
    return render(request, 'cours/form.html', context)


@login_required
@permission_required('cours.delete_cours', raise_exception=True)
def supprimer_cours(request, pk):
    """Supprimer un cours"""
    cours = get_object_or_404(Cours, pk=pk)
    
    if request.method == 'POST':
        nom_cours = str(cours)
        cours.delete()
        messages.success(request, f'Le cours {nom_cours} a été supprimé avec succès.')
        return redirect('liste_cours')
    
    context = {
        'cours': cours,
        'titre': 'Supprimer le cours'
    }
    return render(request, 'cours/confirmer_suppression.html', context)


@role_required('DIRECTEUR', 'ADMIN_SYSTEME', 'ADMIN_PEDAGOGIQUE', 'CHEF_ETUDES')
def liste_matieres(request):
    """Liste et gestion complète des matières avec leurs enseignants attribués"""
    search_query = request.GET.get('q', '').strip()
    semestre_filter = request.GET.get('semestre', '').strip()
    
    matieres = Matiere.objects.all().prefetch_related(
        'cours__professeur', 
        'cours__filiere'
    ).annotate(
        nombre_cours=Count('cours')
    )
    
    if search_query:
        matieres = matieres.filter(
            Q(code__icontains=search_query) | Q(nom__icontains=search_query)
        )
        
    if semestre_filter.isdigit():
        matieres = matieres.filter(semestre=int(semestre_filter))
        
    context = {
        'matieres': matieres,
        'search_query': search_query,
        'semestre_filter': semestre_filter,
        'titre': 'Gestion des Matières & Unités d\'Enseignement'
    }
    return render(request, 'cours/matieres.html', context)


@role_required('DIRECTEUR', 'ADMIN_SYSTEME', 'ADMIN_PEDAGOGIQUE', 'CHEF_ETUDES')
def attribuer_matiere(request, matiere_id=None):
    """Permet d'attribuer une matière à un enseignant avec gestion automatique des filières, niveaux et charges horaires"""
    from apps.professeurs.models import Professeur, ChargeHoraire
    from apps.etudiants.models import Filiere, Niveau
    import datetime

    matiere_obj = None
    if matiere_id:
        matiere_obj = get_object_or_404(Matiere, pk=matiere_id)

    professeur_id = request.GET.get('professeur')
    professeur_obj = None
    if professeur_id:
        professeur_obj = Professeur.objects.filter(pk=professeur_id, est_actif=True).first()

    if request.method == 'POST':
        form = AttributionMatiereForm(request.POST)
        if form.is_valid():
            matiere = form.cleaned_data['matiere']
            professeur = form.cleaned_data['professeur']
            filiere_choice = form.cleaned_data['filiere']
            niveau_choice = form.cleaned_data['niveau']
            type_cours = form.cleaned_data['type_cours']
            annee_academique = form.cleaned_data['annee_academique']

            # Détermination des filières cibles
            if filiere_choice == 'ALL':
                filieres_cibles = list(Filiere.objects.all())
                filiere_label = "Toutes les filières"
            else:
                filiere_obj = get_object_or_404(Filiere, pk=filiere_choice)
                filieres_cibles = [filiere_obj]
                filiere_label = filiere_obj.nom

            cours_attribues = 0
            for fil in filieres_cibles:
                # Code du cours généré intelligemment
                cours_code = f"{matiere.code}-{fil.code}-{type_cours}"
                cours, created = Cours.objects.get_or_create(
                    matiere=matiere,
                    filiere=fil,
                    type_cours=type_cours,
                    annee_academique=annee_academique,
                    defaults={
                        'code': cours_code,
                        'professeur': professeur,
                        'jour': 'Lundi',
                        'heure_debut': datetime.time(8, 0),
                        'heure_fin': datetime.time(10, 0),
                        'date_debut': datetime.date.today(),
                        'date_fin': datetime.date.today() + datetime.timedelta(days=120),
                        'est_actif': True
                    }
                )

                if not created:
                    cours.professeur = professeur
                    cours.est_actif = True
                    cours.save()
                cours_attribues += 1

                # Synchronisation avec le module des notes & bulletins
                try:
                    import apps.notes.models as notes_models
                    notes_mat, _ = notes_models.Matiere.objects.get_or_create(
                        code=matiere.code,
                        defaults={
                            'nom': matiere.nom,
                            'description': matiere.description,
                            'credit': matiere.credits,
                            'semestre': matiere.semestre,
                            'volume_horaire': matiere.get_heures_totales(),
                            'est_actif': True
                        }
                    )
                    
                    niveaux_qs = Niveau.objects.filter(filiere=fil)
                    if niveau_choice != 'ALL':
                        niveaux_qs = niveaux_qs.filter(numero=int(niveau_choice))
                    
                    for niv in niveaux_qs:
                        notes_c, _ = notes_models.Cours.objects.get_or_create(
                            matiere=notes_mat,
                            filiere=fil,
                            niveau=niv,
                            annee_academique=annee_academique,
                            defaults={
                                'semestre': matiere.semestre,
                                'volume_horaire': matiere.get_heures_totales(),
                                'est_actif': True
                            }
                        )
                        if professeur.utilisateur:
                            notes_c.professeur = professeur.utilisateur
                            notes_c.save()
                except Exception:
                    pass

            # Mise à jour ou création de la charge horaire
            charge, _ = ChargeHoraire.objects.get_or_create(
                professeur=professeur,
                annee_academique=annee_academique,
                defaults={'heures_assignees': matiere.get_heures_totales() * cours_attribues}
            )

            niveau_label = f"Niveau {niveau_choice}"
            messages.success(
                request,
                f'La matière "{matiere.nom}" ({matiere.code}) a été attribuée avec succès à M./Mme {professeur.get_nom_complet()} pour {filiere_label} ({niveau_label}) - Année {annee_academique}.'
            )

            if professeur_id or 'from_prof' in request.POST:
                return redirect('liste_professeurs')
            return redirect('cours:liste_matieres')
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        initial_data = {}
        if matiere_obj:
            initial_data['matiere'] = matiere_obj
        if professeur_obj:
            initial_data['professeur'] = professeur_obj
        form = AttributionMatiereForm(initial=initial_data)

    context = {
        'form': form,
        'matiere_obj': matiere_obj,
        'professeur_obj': professeur_obj,
        'titre': f'Attribuer la matière "{matiere_obj.nom}"' if matiere_obj else 'Attribution d\'une Matière'
    }
    return render(request, 'cours/attribuer_matiere.html', context)


@role_required('DIRECTEUR', 'ADMIN_SYSTEME', 'ADMIN_PEDAGOGIQUE', 'CHEF_ETUDES')
def desattribuer_matiere(request, cours_id):
    """Retire l'attribution d'un enseignant sur un cours/matière"""
    cours = get_object_or_404(Cours, pk=cours_id)
    nom_prof = cours.professeur.get_nom_complet()
    nom_mat = cours.matiere.nom
    filiere_nom = cours.filiere.nom
    
    cours.delete()

    messages.success(request, f'L\'attribution de la matière "{nom_mat}" à M./Mme {nom_prof} pour {filiere_nom} a été retirée.')
    return redirect(request.META.get('HTTP_REFERER', 'cours:liste_matieres'))


@role_required('DIRECTEUR', 'ADMIN_SYSTEME', 'ADMIN_PEDAGOGIQUE')
def ajouter_matiere(request):
    """Ajouter une matière"""
    if request.method == 'POST':
        form = MatiereForm(request.POST)
        if form.is_valid():
            matiere = form.save()
            messages.success(request, f'La matière "{matiere.nom}" ({matiere.code}) a été créée avec succès.')
            return redirect('cours:liste_matieres')
    else:
        form = MatiereForm()
    
    context = {
        'form': form,
        'titre': 'Nouvelle Matière'
    }
    return render(request, 'cours/matiere_form.html', context)


@role_required('DIRECTEUR', 'ADMIN_SYSTEME', 'ADMIN_PEDAGOGIQUE')
def modifier_matiere(request, pk):
    """Modifier une matière existante"""
    matiere = get_object_or_404(Matiere, pk=pk)
    if request.method == 'POST':
        form = MatiereForm(request.POST, instance=matiere)
        if form.is_valid():
            form.save()
            messages.success(request, f'La matière "{matiere.nom}" ({matiere.code}) a été modifiée avec succès.')
            return redirect('cours:liste_matieres')
    else:
        form = MatiereForm(instance=matiere)
    
    context = {
        'form': form,
        'matiere': matiere,
        'titre': f'Modifier {matiere.nom}'
    }
    return render(request, 'cours/matiere_form.html', context)


@role_required('DIRECTEUR', 'ADMIN_SYSTEME', 'ADMIN_PEDAGOGIQUE')
def supprimer_matiere(request, pk):
    """Supprimer une matière"""
    from django.db.models import ProtectedError
    matiere = get_object_or_404(Matiere, pk=pk)
    if request.method == 'POST':
        nom = matiere.nom
        try:
            matiere.delete()
            messages.success(request, f'La matière "{nom}" a été supprimée avec succès.')
        except ProtectedError:
            messages.error(request, f'Impossible de supprimer la matière "{nom}" car elle est actuellement liée à des cours.')
        return redirect('cours:liste_matieres')
    
    context = {
        'matiere': matiere,
        'titre': f'Supprimer {matiere.nom}'
    }
    return render(request, 'cours/matiere_confirm_delete.html', context)


@login_required
def liste_salles(request):
    """Liste des salles"""
    salles = Salle.objects.all().annotate(
        nombre_cours=Count('cours')
    )
    
    context = {
        'salles': salles,
        'titre': 'Liste des Salles'
    }
    return render(request, 'cours/salles.html', context)


@login_required
@permission_required('cours.add_salle', raise_exception=True)
def ajouter_salle(request):
    """Ajouter une salle"""
    if request.method == 'POST':
        form = SalleForm(request.POST)
        if form.is_valid():
            salle = form.save()
            messages.success(request, f'La salle {salle} a été créée avec succès.')
            return redirect('liste_salles')
    else:
        form = SalleForm()
    
    context = {
        'form': form,
        'titre': 'Nouvelle Salle'
    }
    return render(request, 'cours/salle_form.html', context)


@login_required
def emploi_du_temps(request):
    """Emplois du temps"""
    filiere_id = request.GET.get('filiere', '')
    annee = request.GET.get('annee', '2024-2025')
    
    emplois = EmploiDuTemps.objects.filter(
        annee_academique=annee
    ).select_related('filiere', 'niveau', 'salle')
    
    role = getattr(request.user, 'type_utilisateur', 'ETUDIANT')
    if role == 'ETUDIANT':
        from apps.etudiants.models import Etudiant
        etudiant = Etudiant.objects.filter(utilisateur=request.user).first()
        if etudiant:
            # Recherche de la salle physique correspondant à la classe de l'étudiant
            matching_salle = find_matching_salle(etudiant.classe)
            # 1. Essayer d'abord niveau et salle exacts
            emplois_exact = emplois.filter(filiere=etudiant.filiere, niveau=etudiant.niveau, salle=matching_salle)
            if emplois_exact.exists():
                emplois = emplois_exact
            else:
                # 2. Sinon niveau exact sans salle
                emplois_niveau = emplois.filter(filiere=etudiant.filiere, niveau=etudiant.niveau, salle__isnull=True)
                if emplois_niveau.exists():
                    emplois = emplois_niveau
                else:
                    # 3. Sinon filière générale
                    emplois = emplois.filter(filiere=etudiant.filiere, niveau__isnull=True, salle__isnull=True)
        else:
            emplois = emplois.none()
    elif filiere_id:
        emplois = emplois.filter(filiere_id=filiere_id)
    
    filieres = Filiere.objects.filter(est_active=True)
    
    context = {
        'emplois': emplois,
        'filieres': filieres,
        'filtre_filiere': filiere_id,
        'annee': annee,
        'titre': 'Emplois du Temps'
    }
    return render(request, 'cours/emplois_du_temps.html', context)


@login_required
def feuille_presence(request, seance_id):
    """Feuille de présence pour une séance"""
    seance = get_object_or_404(SeanceCours, pk=seance_id)
    
    # Étudiants inscrits au cours
    inscriptions = seance.cours.inscriptions_cours.filter(est_actif=True).order_by('etudiant__nom', 'etudiant__prenom')
    
    if request.method == 'POST':
        for inscription in inscriptions:
            statut = request.POST.get(f'presence_{inscription.etudiant_id}', 'PRESENT')
            Presence.objects.update_or_create(
                seance=seance,
                etudiant=inscription.etudiant,
                defaults={'statut': statut}
            )
        messages.success(request, 'La feuille de présence a été enregistrée.')
        return redirect('detail_cours', pk=seance.cours_id)
    
    # Présences déjà enregistrées
    presences = {p.etudiant_id: p.statut for p in seance.presences.all()}
    
    context = {
        'seance': seance,
        'inscriptions': inscriptions,
        'presences': presences,
        'titre': f'Feuille de Présence - {seance.cours}'
    }
    return render(request, 'cours/feuille_presence.html', context)


@login_required
def planning_professeur(request):
    """Planning des cours par professeur"""
    from apps.professeurs.models import Professeur
    
    professeur_id = request.GET.get('professeur', '')
    annee = request.GET.get('annee', '2024-2025')
    
    cours = []
    professeur = None
    
    if professeur_id:
        professeur = get_object_or_404(Professeur, pk=professeur_id)
        cours = Cours.objects.filter(
            professeur=professeur,
            annee_academique=annee,
            est_actif=True
        ).order_by('jour', 'heure_debut')
    
    professeurs = Professeur.objects.filter(statut='ACTIF')
    
    context = {
        'professeurs': professeurs,
        'professeur': professeur,
        'cours': cours,
        'annee': annee,
        'titre': 'Planning Professeur'
    }
    return render(request, 'cours/planning_professeur.html', context)


from .models import EmploiDuTempsHebdomadaire, CreneauEmploiDuTemps

@login_required
def emploi_du_temps_officiel(request):
    """Consultation et liste des emplois du temps hebdomadaires officiels"""
    user = request.user
    role = getattr(user, 'type_utilisateur', 'ETUDIANT')
    
    queryset = EmploiDuTempsHebdomadaire.objects.select_related('filiere', 'salle', 'soumis_par', 'approuve_par')
    
    # Restreindre les non-admins/non-chefs aux seuls emplois du temps approuvés
    if role not in ['CHEF_ETUDES', 'ADMIN_SYSTEME', 'DIRECTEUR']:
        queryset = queryset.filter(statut='VALIDE')
        
    if role == 'ETUDIANT':
        from apps.etudiants.models import Etudiant
        etudiant = Etudiant.objects.filter(utilisateur=user).first()
        if etudiant:
            queryset = queryset.filter(filiere=etudiant.filiere)
            if etudiant.niveau:
                niveau_code = f"LEVEL_{etudiant.niveau.numero}"
                queryset = queryset.filter(niveau=niveau_code)
        else:
            queryset = queryset.none()
            
    filiere_id = request.GET.get('filiere')
    niveau = request.GET.get('niveau')
    statut = request.GET.get('statut')
    
    if filiere_id and role != 'ETUDIANT':
        queryset = queryset.filter(filiere_id=filiere_id)
    if niveau and role != 'ETUDIANT':
        queryset = queryset.filter(niveau=niveau)
    if statut and role in ['CHEF_ETUDES', 'ADMIN_SYSTEME', 'DIRECTEUR']:
        queryset = queryset.filter(statut=statut)
        
    emplois = queryset.order_by('-date_debut_semaine')
    filieres = Filiere.objects.filter(est_active=True)
    
    context = {
        'emplois': emplois,
        'filieres': filieres,
        'niveaux': EmploiDuTempsHebdomadaire.NIVEAU_CHOICES,
        'statuts': EmploiDuTempsHebdomadaire.STATUT_CHOICES,
        'role': role,
        'titre': 'Emplois du Temps Officiels (Centre de Douala)'
    }
    return render(request, 'cours/emploi_du_temps_officiel_liste.html', context)


@login_required
def creer_emploi_du_temps_hebdo(request):
    """Création d'un nouvel emploi du temps par le Chef des Études"""
    if request.user.type_utilisateur not in ['CHEF_ETUDES', 'ADMIN_SYSTEME', 'DIRECTEUR']:
        messages.error(request, "Accès réservé au Chef des Études et à la Direction.")
        return redirect('cours:emploi_du_temps_officiel')
        
    if request.method == 'POST':
        filiere_id = request.POST.get('filiere')
        salle_id = request.POST.get('salle')
        niveau = request.POST.get('niveau', 'LEVEL_1')
        titre_semaine = request.POST.get('titre_semaine')
        date_debut = request.POST.get('date_debut_semaine')
        date_fin = request.POST.get('date_fin_semaine')
        
        if not filiere_id or not titre_semaine or not date_debut or not date_fin:
            messages.error(request, "Veuillez remplir tous les champs obligatoires.")
        else:
            filiere = get_object_or_404(Filiere, pk=filiere_id)
            salle = get_object_or_404(Salle, pk=salle_id) if salle_id else None
            
            emploi = EmploiDuTempsHebdomadaire.objects.create(
                filiere=filiere,
                salle=salle,
                niveau=niveau,
                titre_semaine=titre_semaine,
                date_debut_semaine=date_debut,
                date_fin_semaine=date_fin,
                soumis_par=request.user,
                statut='BROUILLON'
            )
            messages.success(request, f"Emploi du temps '{emploi.titre_semaine}' créé en brouillon. Vous pouvez maintenant définir les créneaux.")
            return redirect('cours:editer_creneaux_emploi_du_temps', pk=emploi.pk)
            
    filieres = Filiere.objects.filter(est_active=True)
    salles = Salle.objects.filter(est_disponible=True).order_by('nom')
    
    context = {
        'filieres': filieres,
        'salles': salles,
        'niveaux': EmploiDuTempsHebdomadaire.NIVEAU_CHOICES,
        'titre': 'Nouveau Tableau d\'Emploi du Temps'
    }
    return render(request, 'cours/emploi_du_temps_form.html', context)


@login_required
def editer_creneaux_emploi_du_temps(request, pk):
    """Éditer la grille hebdomadaire (du Lundi au Samedi)"""
    emploi = get_object_or_404(EmploiDuTempsHebdomadaire, pk=pk)
    
    if request.user.type_utilisateur not in ['CHEF_ETUDES', 'ADMIN_SYSTEME', 'DIRECTEUR']:
        messages.error(request, "Permissions insuffisantes.")
        return redirect('cours:emploi_du_temps_officiel')
        
    jours = ['LUNDI', 'MARDI', 'MERCREDI', 'JEUDI', 'VENDREDI', 'SAMEDI']
    plages = [
        ('P1', '07:30 - 09:30'),
        ('P2', '09:30 - 11:30'),
        ('PAUSE', '11:30 - 12:45'),
        ('P3', '12:45 - 14:45'),
        ('P4', '14:45 - 16:45'),
    ]
    
    if request.method == 'POST':
        for jour in jours:
            for plage_code, _ in plages:
                intitule = request.POST.get(f'intitule_{jour}_{plage_code}', '').strip()
                enseignant = request.POST.get(f'enseignant_{jour}_{plage_code}', '').strip()
                salle_nom = request.POST.get(f'salle_{jour}_{plage_code}', '').strip()
                progression = request.POST.get(f'progression_{jour}_{plage_code}', '').strip()
                type_evt = request.POST.get(f'type_{jour}_{plage_code}', 'COURS')
                
                if intitule or plage_code == 'PAUSE':
                    CreneauEmploiDuTemps.objects.update_or_create(
                        emploi_du_temps=emploi,
                        jour=jour,
                        plage=plage_code,
                        defaults={
                            'intitule': 'PAUSE' if plage_code == 'PAUSE' else intitule,
                            'enseignant_nom': enseignant,
                            'salle_nom': salle_nom or (emploi.salle.code if emploi.salle else ''),
                            'progression_heures': progression,
                            'type_evenement': 'PAUSE' if plage_code == 'PAUSE' else type_evt,
                        }
                    )
                else:
                    CreneauEmploiDuTemps.objects.filter(emploi_du_temps=emploi, jour=jour, plage=plage_code).delete()
                    
        messages.success(request, "Grille de l'emploi du temps mise à jour avec succès.")
        return redirect('cours:imprimer_emploi_du_temps_officiel', pk=emploi.pk)
        
    # Organiser les créneaux existants sous forme de dict (jour, plage) -> creneau
    creneaux_list = emploi.creneaux.all()
    grid = {}
    for c in creneaux_list:
        grid[(c.jour, c.plage)] = c
        
    context = {
        'emploi': emploi,
        'jours': ['LUNDI', 'MARDI', 'MERCREDI', 'JEUDI', 'VENDREDI', 'SAMEDI'],
        'plages': plages,
        'grid': grid,
        'titre': f"Édition Grille : {emploi.titre_semaine}"
    }
    return render(request, 'cours/emploi_du_temps_editeur.html', context)


@login_required
def soumettre_emploi_du_temps(request, pk):
    """Soumettre l'emploi du temps au Directeur pour approbation"""
    emploi = get_object_or_404(EmploiDuTempsHebdomadaire, pk=pk)
    
    if request.user.type_utilisateur not in ['CHEF_ETUDES', 'ADMIN_SYSTEME', 'DIRECTEUR']:
        messages.error(request, "Seul le Chef des Études peut soumettre l'emploi du temps.")
        return redirect('cours:emploi_du_temps_officiel')
        
    emploi.statut = 'EN_ATTENTE_VALIDATION'
    emploi.soumis_par = request.user
    emploi.save()
    messages.info(request, f"📩 L'emploi du temps '{emploi.titre_semaine}' a été transmis au Directeur pour approbation.")
    return redirect('cours:imprimer_emploi_du_temps_officiel', pk=emploi.pk)


@login_required
def approuver_emploi_du_temps(request, pk):
    """Approbation / Rejet par le Directeur (Redistribution automatique aux étudiants et enseignants)"""
    emploi = get_object_or_404(EmploiDuTempsHebdomadaire, pk=pk)
    
    if request.user.type_utilisateur not in ['DIRECTEUR', 'ADMIN_SYSTEME']:
        messages.error(request, "Seul le Directeur peut approuver l'emploi du temps.")
        return redirect('cours:emploi_du_temps_officiel')
        
    action = request.POST.get('action')
    if action == 'approuver':
        emploi.statut = 'VALIDE'
        emploi.approuve_par = request.user
        emploi.date_approbation = timezone.now()
        emploi.save()

        # Synchroniser automatiquement la fiche hebdo présence enseignants
        try:
            from apps.cours.presence_service import synchroniser_fiche_presence_enseignant_auto
            synchroniser_fiche_presence_enseignant_auto(emploi, request.user)
        except Exception:
            pass

        # --- Notification Tri-canal des Enseignants et Étudiants ---
        from django.conf import settings
        from django.contrib.auth import get_user_model
        from apps.tableau_bord.models import Notification
        from apps.tableau_bord.whatsapp_service import WhatsAppService
        from django.core.mail import send_mail

        User = get_user_model()
        enseignants = User.objects.filter(
            type_utilisateur__in=['ENSEIGNANT', 'PROFESSEUR', 'FORMATEUR'],
            est_actif=True
        )

        titre_notif = f"📅 Emploi du temps publié : {emploi.titre_semaine}"
        msg_notif = (
            f"Le nouvel emploi du temps officiellement approuvé pour la période "
            f"({emploi.titre_semaine}) est disponible. Veuillez consulter vos créneaux de cours."
        )
        site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')

        for ens in enseignants:
            # 1. Notification In-App
            Notification.objects.create(
                utilisateur=ens,
                type='INFO',
                titre=titre_notif,
                message=msg_notif,
                lien=f'/cours/emploi-du-temps-officiel/{emploi.pk}/imprimer/'
            )
            # 2. Email réel
            if ens.email:
                try:
                    send_mail(
                        subject=f"{getattr(settings, 'EMAIL_SUBJECT_PREFIX', '[IAI-Cameroun] ')}Nouveau Planning - {emploi.titre_semaine}",
                        message=f"Bonjour {ens.get_full_name() or ens.username},\n\n{msg_notif}\n\nConsultez le planning complet sur : {site_url}/cours/emploi-du-temps-officiel/{emploi.pk}/imprimer/",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[ens.email],
                        fail_silently=True
                    )
                except Exception:
                    pass
            # 3. WhatsApp
            tel = getattr(ens, 'telephone', '') or getattr(ens, 'contact', '')
            if tel:
                try:
                    WhatsAppService.envoyer_message(
                        tel,
                        f"*IAI-CAMEROUN (Douala)* 📅\n*Publication d'Emploi du Temps*\n\nBonjour {ens.get_full_name() or ens.username},\n{msg_notif}\n\nLien : {site_url}/cours/emploi-du-temps-officiel/{emploi.pk}/imprimer/"
                    )
                except Exception:
                    pass

        # --- Notification des Étudiants ---
        from apps.etudiants.models import Etudiant
        etudiants_qs = Etudiant.objects.filter(statut__in=['PREINSCRIT', 'INSCRIT', 'ACTIF']).select_related('utilisateur')
        if hasattr(emploi, 'filiere') and emploi.filiere:
            etudiants_qs = etudiants_qs.filter(filiere=emploi.filiere)

        for etud in etudiants_qs:
            if etud.utilisateur:
                Notification.objects.create(
                    utilisateur=etud.utilisateur,
                    type='INFO',
                    titre=titre_notif,
                    message=msg_notif,
                    lien=f'/cours/emploi-du-temps-officiel/{emploi.pk}/imprimer/'
                )
            dest_email = etud.email or (etud.utilisateur.email if etud.utilisateur else None)
            if dest_email:
                try:
                    send_mail(
                        subject=f"{getattr(settings, 'EMAIL_SUBJECT_PREFIX', '[IAI-Cameroun] ')}Nouveau Planning - {emploi.titre_semaine}",
                        message=f"Bonjour {etud.get_nom_complet()},\n\n{msg_notif}\n\nConsultez votre planning complet sur : {site_url}/cours/emploi-du-temps-officiel/{emploi.pk}/imprimer/",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[dest_email],
                        fail_silently=True
                    )
                except Exception:
                    pass
            try:
                WhatsAppService.notifier_etudiant(
                    etudiant=etud,
                    titre="Nouveau Planning Publié",
                    message=f"Alerte Emploi du Temps - IAI-Cameroun\n\nBonjour {etud.get_nom_complet()},\n{msg_notif}\n\nLien : {site_url}/cours/emploi-du-temps-officiel/{emploi.pk}/imprimer/"
                )
            except Exception:
                pass

        messages.success(
            request, 
            f"✅ Emploi du temps '{emploi.titre_semaine}' approuvé et publié ! Il a été notifié aux Enseignants et Étudiants."
        )
    elif action == 'rejeter':
        motif = request.POST.get('motif_rejet', '')
        emploi.statut = 'REJETE'
        emploi.motif_rejet = motif
        emploi.save()
        messages.warning(request, f"⚠️ Emploi du temps renvoyé au Chef des Études pour révision. Motif : {motif}")
        
    return redirect('cours:imprimer_emploi_du_temps_officiel', pk=emploi.pk)


@login_required
def imprimer_emploi_du_temps_officiel(request, pk):
    """Vue réplique exacte haute fidélité pour affichage et impression PDF"""
    emploi = get_object_or_404(EmploiDuTempsHebdomadaire.objects.select_related('filiere', 'salle', 'soumis_par', 'approuve_par'), pk=pk)
    
    jours = [
        ('LUNDI', 'Lundi'),
        ('MARDI', 'Mardi'),
        ('MERCREDI', 'Mercredi'),
        ('JEUDI', 'Jeudi'),
        ('VENDREDI', 'Vendredi'),
        ('SAMEDI', 'Samedi')
    ]
    
    plages = [
        ('P1', '07:30 - 09:30'),
        ('P2', '09:30 - 11:30'),
        ('PAUSE', 'PAUSE: 11:30 - 12:45'),
        ('P3', '12:45 - 14:45'),
        ('P4', '14:45 - 16:45'),
    ]
    
    creneaux_list = emploi.creneaux.all()
    grid = {}
    for c in creneaux_list:
        grid[(c.jour, c.plage)] = c
        
    context = {
        'emploi': emploi,
        'jours': jours,
        'plages': plages,
        'grid': grid,
        'role': getattr(request.user, 'type_utilisateur', 'ETUDIANT'),
        'titre': f"Emploi du temps - {emploi.titre_semaine}"
    }
    return render(request, 'cours/emploi_du_temps_officiel.html', context)


from functools import lru_cache

@lru_cache(maxsize=128)
def _find_matching_salle_cached(classe_nom):
    from apps.cours.models import Salle
    # 1. Match exact par nom (insensible à la casse)
    salle = Salle.objects.filter(nom__iexact=classe_nom).first()
    if salle:
        return salle
        
    # 2. Match partiel par nom
    salle = Salle.objects.filter(nom__icontains=classe_nom).first()
    if salle:
        return salle
        
    # 3. Remplacement & commercial
    salle = Salle.objects.filter(nom__icontains=classe_nom.replace('et', '&')).first()
    if salle:
        return salle
        
    # 4. Match par code (Génie Logiciel 1A -> GL1A)
    words = classe_nom.split()
    initials = "".join([w[0].upper() for w in words if w.lower() not in ['et', '&', 'de', 'la', 'les', 'des']])
    salle = Salle.objects.filter(code__iexact=initials).first()
    if salle:
        return salle
        
    # 5. Recherche du code dans le nom complet de la classe
    for s in Salle.objects.all():
        if s.code.upper() in "".join(words).upper():
            return s
            
    return None


def find_matching_salle(classe):
    """
    Associe de manière robuste une classe académique d'un étudiant (ex: 'Génie Logiciel 1A')
    à une salle de cours physique (ex: code='GL1A', nom='Génie Logiciel 1A') créée par le directeur.
    """
    if not classe:
        return None
    return _find_matching_salle_cached(classe.nom)


# ==================== LISTES HEBDOMADAIRES DE PRESENCE ====================

@login_required
def liste_fiches_presence(request):
    """Liste et archivage des fiches de présence hebdomadaires (LISTE DE PRESENCE IAI)"""
    user = request.user
    role = getattr(user, 'type_utilisateur', None)
    
    if role not in ('CHEF_SCOLARITE', 'ADMIN_SYSTEME', 'CHEF_ETUDES') and not user.is_superuser:
        messages.error(request, "❌ Accès réservé à la Scolarité et à la Direction.")
        return redirect('tableau_bord:tableau_bord')

    from apps.cours.models import FichePresenceHebdomadaire
    from apps.etudiants.models import Classe
    
    queryset = FichePresenceHebdomadaire.objects.all().select_related('classe', 'filiere', 'niveau', 'cree_par')

    # Filtres
    classe_id = request.GET.get('classe', '')
    if classe_id:
        queryset = queryset.filter(classe_id=classe_id)
        
    statut = request.GET.get('statut', '')
    if statut:
        queryset = queryset.filter(statut=statut)

    context = {
        'fiches': queryset.order_by('-semaine_du'),
        'classes': Classe.objects.all(),
        'titre': 'Fiches Hebdomadaires de Présence'
    }
    return render(request, 'cours/presences/liste.html', context)


@login_required
def creer_fiche_presence(request):
    """Créer une nouvelle fiche de présence hebdomadaire pour une classe"""
    user = request.user
    role = getattr(user, 'type_utilisateur', None)
    if role not in ('CHEF_SCOLARITE', 'ADMIN_SYSTEME', 'CHEF_ETUDES') and not user.is_superuser:
        messages.error(request, "❌ Accès réservé au Chef de la Scolarité.")
        return redirect('tableau_bord:tableau_bord')

    from apps.etudiants.models import Classe
    from apps.cours.models import FichePresenceHebdomadaire, LignePresenceHebdomadaire

    if request.method == 'POST':
        classe_id = request.POST.get('classe')
        semaine_du = request.POST.get('semaine_du')
        semaine_au = request.POST.get('semaine_au')

        classe = get_object_or_404(Classe, pk=classe_id)
        
        # Contrôle d'unicité : une seule liste de présence par salle/classe et par semaine
        fiche_existante = FichePresenceHebdomadaire.objects.filter(
            classe=classe,
            semaine_du=semaine_du
        ).first()

        if fiche_existante:
            messages.warning(
                request,
                f"⚠️ Une liste de présence pour {classe.nom} existe déjà pour la semaine du {semaine_du} au {semaine_au}. "
                f"Vous avez été redirigé vers celle-ci."
            )
            return redirect('cours:saisie_grille_presence', pk=fiche_existante.pk)

        fiche = FichePresenceHebdomadaire.objects.create(
            classe=classe,
            filiere=classe.filiere,
            niveau=classe.niveau,
            annee_academique=classe.annee_academique.code if classe.annee_academique else '2025-2026',
            semaine_du=semaine_du,
            semaine_au=semaine_au,
            cree_par=user,
            statut='BROUILLON'
        )

        # Pré-remplir les lignes pour chaque étudiant de la classe
        etudiants = classe.etudiants.filter(statut__in=['INSCRIT', 'ACTIF'])
        for et in etudiants:
            LignePresenceHebdomadaire.objects.get_or_create(
                fiche=fiche,
                etudiant=et,
                defaults={'nombre_absences': 0}
            )

        messages.success(request, f"✅ Fiche de présence créée pour {classe.nom} (Semaine du {semaine_du} au {semaine_au}).")
        return redirect('cours:saisie_grille_presence', pk=fiche.pk)

    context = {
        'classes': Classe.objects.all(),
        'titre': 'Nouvelle Fiche de Présence'
    }
    return render(request, 'cours/presences/importer.html', context)


@login_required
def supprimer_fiche_presence(request, pk):
    """Supprimer définitivement une fiche de présence hebdomadaire pour une salle / classe"""
    user = request.user
    role = getattr(user, 'type_utilisateur', None)
    if role not in ('CHEF_SCOLARITE', 'ADMIN_SYSTEME', 'CHEF_ETUDES') and not user.is_superuser:
        messages.error(request, "❌ Accès réservé au Chef de la Scolarité.")
        return redirect('cours:liste_fiches_presence')

    from apps.cours.models import FichePresenceHebdomadaire
    fiche = get_object_or_404(FichePresenceHebdomadaire, pk=pk)
    nom_classe = fiche.classe.nom
    sem_du = fiche.semaine_du
    sem_au = fiche.semaine_au
    fiche.delete()

    messages.success(request, f"🗑️ La fiche de présence de {nom_classe} (Semaine du {sem_du} au {sem_au}) a été supprimée.")
    return redirect('cours:liste_fiches_presence')


@login_required
def saisie_grille_presence(request, pk):
    """Grille de présence hebdomadaire (Lun-Sam) avec possibilité d'édition pour le Chef de la Scolarité"""
    from apps.cours.models import FichePresenceHebdomadaire, LignePresenceHebdomadaire
    from apps.cours.presence_service import synchroniser_fiche_presence_automatique
    import json

    fiche = get_object_or_404(FichePresenceHebdomadaire, pk=pk)

    user = request.user
    role = getattr(user, 'type_utilisateur', '')
    peut_editer = role in ['CHEF_SCOLARITE', 'CHEF_ETUDES', 'ADMIN_SYSTEME'] or user.is_superuser

    lignes = fiche.lignes.all().select_related('etudiant').order_by('etudiant__nom', 'etudiant__prenom')

    if request.method == 'POST':
        if not peut_editer:
            messages.error(request, "❌ Seul le Chef de la Scolarité est autorisé à modifier cette grille de présence.")
            return redirect('cours:saisie_grille_presence', pk=fiche.pk)

        for ligne in lignes:
            e_id = ligne.etudiant.id
            grid_data = {}
            total_abs = 0

            for jour in ['lun', 'mar', 'mer', 'jeu', 'ven', 'sam']:
                slots = []
                for slot_num in range(1, 5):
                    field_name = f"abs_{e_id}_{jour}_{slot_num}"
                    val = request.POST.get(field_name, '').strip().upper()
                    slots.append(val if val == 'A' else '')
                    if val == 'A':
                        total_abs += 1
                grid_data[jour] = slots

            ligne.nombre_absences = total_abs
            ligne.details_jours_json = json.dumps(grid_data)
            ligne.save()

        messages.success(request, f"💾 Grille de présence mise à jour avec succès ({fiche.classe.nom if fiche.classe else ''}).")
        return redirect('cours:saisie_grille_presence', pk=fiche.pk)

    # Synchroniser automatiquement les absences issues des cours lors de la consultation
    synchroniser_fiche_presence_automatique(fiche)

    lignes = fiche.lignes.all().select_related('etudiant').order_by('etudiant__nom', 'etudiant__prenom')

    lignes_data = []
    for l in lignes:
        try:
            details = json.loads(l.details_jours_json) if l.details_jours_json else {}
        except Exception:
            details = {}
            
        formatted_details = {}
        for jour in ['lun', 'mar', 'mer', 'jeu', 'ven', 'sam']:
            raw_slots = details.get(jour, [])
            if isinstance(raw_slots, str):
                raw_slots = list(raw_slots)
            slots_4 = []
            for i in range(4):
                if i < len(raw_slots):
                    val = str(raw_slots[i]).strip().upper()
                    slots_4.append(val if val == 'A' else '')
                else:
                    slots_4.append('')
            formatted_details[jour] = slots_4
            
        lignes_data.append({
            'ligne': l,
            'etudiant': l.etudiant,
            'details': details,
            'formatted_details': formatted_details,
            'absences': l.nombre_absences
        })

    context = {
        'fiche': fiche,
        'lignes_data': lignes_data,
        'peut_editer': peut_editer,
        'titre': f"Grille de Présence - {fiche.classe.nom if fiche.classe else 'Classe'}"
    }
    return render(request, 'cours/presences/grille_hebdomadaire.html', context)


@login_required
def importer_fiche_presence(request):
    """Importation multi-format (CSV, Excel, PDF, TXT) avec matching automatique et fiable"""
    user = request.user
    role = getattr(user, 'type_utilisateur', None)
    if role not in ('CHEF_SCOLARITE', 'ADMIN_SYSTEME', 'CHEF_ETUDES') and not user.is_superuser:
        messages.error(request, "❌ Accès réservé au Chef de la Scolarité.")
        return redirect('tableau_bord:tableau_bord')

    from apps.etudiants.models import Classe
    from apps.cours.models import FichePresenceHebdomadaire, LignePresenceHebdomadaire
    from apps.cours.presence_service import matcher_etudiant_presence
    import csv, io

    if request.method == 'POST':
        classe_id = request.POST.get('classe')
        semaine_du = request.POST.get('semaine_du')
        semaine_au = request.POST.get('semaine_au')
        fichier = request.FILES.get('fichier')

        classe = get_object_or_404(Classe, pk=classe_id)
        etudiants_classe = list(classe.etudiants.filter(statut__in=['INSCRIT', 'ACTIF']))

        fiche = FichePresenceHebdomadaire.objects.create(
            classe=classe,
            filiere=classe.filiere,
            niveau=classe.niveau,
            annee_academique=classe.annee_academique.code if classe.annee_academique else '2025-2026',
            semaine_du=semaine_du,
            semaine_au=semaine_au,
            cree_par=user,
            statut='BROUILLON'
        )

        matched_count = 0
        if fichier:
            filename = fichier.name.lower()
            rows_data = []

            if filename.endswith('.xlsx') or filename.endswith('.xls'):
                try:
                    import openpyxl
                    wb = openpyxl.load_workbook(fichier, data_only=True)
                    sheet = wb.active
                    for row in sheet.iter_rows(values_only=True):
                        if row and any(row):
                            rows_data.append([str(c) if c is not None else '' for c in row])
                except Exception:
                    pass

            if not rows_data:
                try:
                    content = fichier.read().decode('utf-8-sig', errors='ignore')
                    delimiter = ';' if ';' in content else (',' if ',' in content else '\t')
                    reader = csv.reader(io.StringIO(content), delimiter=delimiter)
                    for row in reader:
                        if row:
                            rows_data.append(row)
                except Exception:
                    pass

            for row in rows_data:
                if not row or len(row) < 2:
                    continue
                
                identifiant = row[2] if len(row) > 2 and row[2].strip() else row[0]
                etudiant_match, score = matcher_etudiant_presence(identifiant, etudiants_classe)

                if etudiant_match:
                    absences = sum(1 for val in row[1:] if str(val).strip().upper() in ('A', 'ABSENT', '1'))
                    LignePresenceHebdomadaire.objects.update_or_create(
                        fiche=fiche,
                        etudiant=etudiant_match,
                        defaults={'nombre_absences': absences}
                    )
                    matched_count += 1

        messages.success(request, f"✅ Importation réussie ! {matched_count} étudiant(s) matché(s) avec succès pour la classe {classe.nom}.")
        return redirect('cours:saisie_grille_presence', pk=fiche.pk)

    context = {
        'classes': Classe.objects.all(),
        'titre': 'Importer une Liste de Présence'
    }
    return render(request, 'cours/presences/importer.html', context)


@login_required
def publier_fiche_presence(request, pk):
    """Publie la fiche de présence, alerte chaque étudiant (Dashboard, Mail, WhatsApp) et cumule la discipline"""
    user = request.user
    role = getattr(user, 'type_utilisateur', None)
    if role not in ('CHEF_SCOLARITE', 'ADMIN_SYSTEME') and not user.is_superuser:
        messages.error(request, "❌ Seul le Chef de la Scolarité peut publier les présences.")
        return redirect('tableau_bord:tableau_bord')

    from apps.cours.models import FichePresenceHebdomadaire
    from apps.cours.presence_service import calculer_total_absences_cumulees
    from apps.tableau_bord.models import Notification
    from apps.tableau_bord.whatsapp_service import WhatsAppService
    from django.core.mail import send_mail
    from django.utils import timezone

    fiche = get_object_or_404(FichePresenceHebdomadaire, pk=pk)

    if request.method == 'POST':
        fiche.statut = 'PUBLIE'
        fiche.date_publication = timezone.now()
        fiche.save()
        fiche.lignes.update(est_cumulee=True)

        # Alertes tri-canal automatiques pour chaque étudiant
        alertes_envoyees = 0
        for ligne in fiche.lignes.select_related('etudiant', 'etudiant__utilisateur'):
            etudiant = ligne.etudiant
            if not etudiant:
                continue

            total_abs = calculer_total_absences_cumulees(etudiant)

            # 1. Alerte Dashboard
            if etudiant.utilisateur:
                Notification.objects.create(
                    utilisateur=etudiant.utilisateur,
                    titre="⚠️ Notification d'Absences Hebdomadaires",
                    message=f"Fiche de présence publiée (du {fiche.semaine_du} au {fiche.semaine_au}). Absences cette semaine : {ligne.nombre_absences} h. Total cumulé : {total_abs} h.",
                    type='WARNING',
                    lien='/tableau-de-bord/'
                )

            # 2. Alerte E-mail
            if etudiant.email:
                try:
                    send_mail(
                        subject=f"IAI-Cameroun - Suivi d'Absences ({etudiant.get_nom_complet()})",
                        message=f"Bonjour {etudiant.get_nom_complet()},\n\nLa fiche de présence pour la semaine du {fiche.semaine_du} au {fiche.semaine_au} a été publiée.\nAbsences enregistrées cette semaine : {ligne.nombre_absences} heure(s).\nTotal d'absences cumulées : {total_abs} heure(s).\n\nConsultez votre tableau de bord pour plus de détails.",
                        from_email="scolarite@iai-cameroun.cm",
                        recipient_list=[etudiant.email],
                        fail_silently=True
                    )
                except Exception:
                    pass

            # 3. Alerte WhatsApp
            try:
                WhatsAppService.notifier_etudiant(
                    etudiant=etudiant,
                    titre="Alerte Absences Hebdomadaires",
                    message=f"Alerte Absences - IAI-Cameroun (Douala)\n\nBonjour {etudiant.get_nom_complet()},\nLa fiche de présence pour la semaine du {fiche.semaine_du} au {fiche.semaine_au} est disponible.\n- Absences cette semaine : {ligne.nombre_absences} heure(s)\n- Total d'absences cumulées : {total_abs} heure(s)."
                )
            except Exception:
                pass

            alertes_envoyees += 1

        messages.success(
            request, 
            f"🎉 La liste de présence de {fiche.classe.nom} a été PUBLIÉE ! {alertes_envoyees} étudiant(s) ont été alertés (Dashboard, E-mail & WhatsApp) et la liste de discipline a été synchronisée."
        )
        return redirect('cours:liste_fiches_presence')

    return redirect('cours:liste_fiches_presence')


@login_required
def liste_fiches_presence_enseignant(request):
    """Liste, archivage et suivi des fiches hebdo de présence enseignants (Scolarité)"""
    user = request.user
    role = getattr(user, 'type_utilisateur', None)
    if role not in ('CHEF_SCOLARITE', 'ADMIN_SYSTEME', 'CHEF_ETUDES') and not user.is_superuser:
        messages.error(request, "❌ Accès réservé au Chef de la Scolarité et à la Direction.")
        return redirect('tableau_bord:tableau_bord')

    from apps.cours.models import FichePresenceEnseignantHebdo
    fiches = FichePresenceEnseignantHebdo.objects.all().select_related('rempli_par').order_by('-semaine_du')
    
    context = {
        'fiches': fiches,
        'titre': 'Suivi Hebdomadaire des Présences Enseignants'
    }
    return render(request, 'cours/presences/fiches_enseignants.html', context)


@login_required
def creer_fiche_presence_enseignant(request):
    """Créer une fiche d'émargement hebdo enseignants basés sur les créneaux d'emploi du temps validés"""
    user = request.user
    role = getattr(user, 'type_utilisateur', None)
    if role not in ('CHEF_SCOLARITE', 'ADMIN_SYSTEME', 'CHEF_ETUDES') and not user.is_superuser:
        messages.error(request, "❌ Accès réservé au Chef de la Scolarité.")
        return redirect('tableau_bord:tableau_bord')

    from datetime import datetime
    from apps.cours.models import FichePresenceEnseignantHebdo, PointagePresenceEnseignant, CreneauEmploiDuTemps, EmploiDuTempsHebdomadaire
    from apps.professeurs.models import Professeur
    from apps.cours.presence_service import normaliser_chaine

    if request.method == 'POST':
        semaine_du_str = request.POST.get('semaine_du')
        semaine_au_str = request.POST.get('semaine_au')

        try:
            semaine_du = datetime.strptime(semaine_du_str, '%Y-%m-%d').date()
            semaine_au = datetime.strptime(semaine_au_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, "Date invalide.")
            return redirect('cours:liste_fiches_presence_enseignant')

        from apps.etudiants.models import AnneeAcademique
        from apps.inscriptions.utils import get_current_academic_year_code
        annee_active = AnneeAcademique.get_active()
        annee_code = annee_active.code if annee_active else get_current_academic_year_code()

        fiche, created = FichePresenceEnseignantHebdo.objects.get_or_create(
            semaine_du=semaine_du,
            defaults={
                'semaine_au': semaine_au,
                'annee_academique': annee_code,
                'rempli_par': user,
                'statut': 'BROUILLON'
            }
        )
        if not created and fiche.annee_academique != annee_code:
            fiche.annee_academique = annee_code
            fiche.save(update_fields=['annee_academique'])

        emplois_valides = EmploiDuTempsHebdomadaire.objects.filter(statut='VALIDE')
        if not emplois_valides.exists():
            emplois_valides = EmploiDuTempsHebdomadaire.objects.all()

        creneaux = CreneauEmploiDuTemps.objects.filter(emploi_du_temps__in=emplois_valides).exclude(type_evenement='PAUSE')
        professeurs = Professeur.objects.filter(est_actif=True)

        for prof in professeurs:
            mots_cles = set()
            if prof.nom: mots_cles.update(normaliser_chaine(prof.nom).split())
            if prof.prenom: mots_cles.update(normaliser_chaine(prof.prenom).split())
            mots_cles = {m for m in mots_cles if len(m) > 2 and m not in ['mme', 'prof', 'docteur', 'monsieur']}

            for c in creneaux:
                str_ens = normaliser_chaine(c.enseignant_nom)
                if str_ens and mots_cles and mots_cles.intersection(set(str_ens.split())):
                    PointagePresenceEnseignant.objects.get_or_create(
                        fiche=fiche,
                        enseignant=prof,
                        creneau=c,
                        date_seance=semaine_du,
                        defaults={'statut': 'PRESENT'}
                    )

        messages.success(request, f"✅ Fiche hebdo présence enseignants créée pour la semaine du {semaine_du}.")
        return redirect('cours:saisir_fiche_presence_enseignant', pk=fiche.pk)

    return redirect('cours:liste_fiches_presence_enseignant')


@login_required
def saisir_fiche_presence_enseignant(request, pk):
    """Saisie / Émargement des présences effectives des enseignants (Chef de la Scolarité)"""
    user = request.user
    role = getattr(user, 'type_utilisateur', None)
    if role not in ('CHEF_SCOLARITE', 'ADMIN_SYSTEME', 'CHEF_ETUDES') and not user.is_superuser:
        messages.error(request, "❌ Accès réservé au Chef de la Scolarité.")
        return redirect('tableau_bord:tableau_bord')

    from apps.cours.models import FichePresenceEnseignantHebdo, PointagePresenceEnseignant, CreneauEmploiDuTemps, EmploiDuTempsHebdomadaire
    from apps.professeurs.models import Professeur

    fiche = get_object_or_404(FichePresenceEnseignantHebdo, pk=pk)

    if request.method == 'POST':
        for key, value in request.POST.items():
            if key.startswith('statut_'):
                pointage_id = key.split('_')[1]
                pointage = PointagePresenceEnseignant.objects.filter(pk=pointage_id, fiche=fiche).first()
                if pointage:
                    pointage.statut = value
                    obs = request.POST.get(f'obs_{pointage_id}', '').strip()
                    pointage.observations = obs
                    pointage.save()

        if 'valider_archivage' in request.POST:
            fiche.statut = 'VALIDE'
            fiche.save()
            messages.success(request, f"🔒 Fiche de présence enseignants du {fiche.semaine_du} validée et archivée.")
            return redirect('cours:liste_fiches_presence_enseignant')

        messages.success(request, f"💾 Modifications enregistrées pour la fiche du {fiche.semaine_du}.")
        return redirect('cours:saisir_fiche_presence_enseignant', pk=fiche.pk)

    pointages = fiche.pointages.select_related('enseignant', 'creneau', 'creneau__emploi_du_temps', 'creneau__emploi_du_temps__filiere').order_by('enseignant__nom', 'creneau__jour')

    if not pointages.exists():
        emplois_valides = EmploiDuTempsHebdomadaire.objects.filter(statut='VALIDE')
        if not emplois_valides.exists():
            emplois_valides = EmploiDuTempsHebdomadaire.objects.all()

        creneaux = CreneauEmploiDuTemps.objects.filter(emploi_du_temps__in=emplois_valides).exclude(type_evenement='PAUSE').select_related('emploi_du_temps', 'emploi_du_temps__filiere')
        professeurs = Professeur.objects.filter(est_actif=True)

        from apps.cours.presence_service import normaliser_chaine
        for prof in professeurs:
            mots_cles = set()
            if prof.nom: mots_cles.update(normaliser_chaine(prof.nom).split())
            if prof.prenom: mots_cles.update(normaliser_chaine(prof.prenom).split())
            mots_cles = {m for m in mots_cles if len(m) > 2 and m not in ['mme', 'prof', 'docteur', 'monsieur']}

            for c in creneaux:
                str_ens = normaliser_chaine(c.enseignant_nom)
                if str_ens and mots_cles and mots_cles.intersection(set(str_ens.split())):
                    PointagePresenceEnseignant.objects.get_or_create(
                        fiche=fiche,
                        enseignant=prof,
                        creneau=c,
                        date_seance=fiche.semaine_du,
                        defaults={'statut': 'PRESENT'}
                    )
        pointages = fiche.pointages.select_related('enseignant', 'creneau', 'creneau__emploi_du_temps', 'creneau__emploi_du_temps__filiere').order_by('enseignant__nom', 'creneau__jour')

    context = {
        'fiche': fiche,
        'pointages': pointages,
        'statut_choices': PointagePresenceEnseignant.STATUT_PRESENCE_CHOICES,
        'titre': f'Émargement Enseignants - Semaine du {fiche.semaine_du}'
    }
    return render(request, 'cours/presences/saisie_enseignants.html', context)


@login_required
def exporter_fiche_presence_enseignant_pdf(request, pk):
    """Téléchargement PDF de la Fiche Hebdomadaire d'Émargement & Présence Enseignants"""
    user = request.user
    role = getattr(user, 'type_utilisateur', None)
    if role not in ('CHEF_SCOLARITE', 'ADMIN_SYSTEME', 'CHEF_ETUDES', 'DIRECTEUR') and not user.is_superuser:
        messages.error(request, "❌ Accès réservé au Chef de la Scolarité et à la Direction.")
        return redirect('tableau_bord:tableau_bord')

    from apps.cours.models import FichePresenceEnseignantHebdo
    from apps.inscriptions.pdf_services import generer_fiche_presence_enseignant_pdf

    fiche = get_object_or_404(FichePresenceEnseignantHebdo, pk=pk)
    base_url = request.build_absolute_uri('/')[:-1]

    pdf_bytes = generer_fiche_presence_enseignant_pdf(fiche, domain_url=base_url)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f"Fiche_Emargement_Enseignants_Semaine_{fiche.semaine_du.strftime('%Y%m%d')}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@login_required
def note_annuelle_discipline(request, salle_id):
    """Génère le document officiel NOTES ANNUELLES DE DISCIPLINE (HA, HJ, HNJ et Décision HNJ > 30)"""
    user = request.user
    role = getattr(user, 'type_utilisateur', None)
    if role not in ('CHEF_SCOLARITE', 'ADMIN_SYSTEME', 'CHEF_ETUDES') and not user.is_superuser:
        messages.error(request, "❌ Accès réservé au Chef de la Scolarité.")
        return redirect('tableau_bord:tableau_bord')

    from apps.cours.presence_service import calculer_notes_annuelles_discipline
    from apps.cours.models import LignePresenceHebdomadaire
    from django.utils import timezone

    if request.method == 'POST':
        for key, val in request.POST.items():
            if key.startswith('hj_'):
                etudiant_id = key.split('_')[1]
                try:
                    hj_val = int(val)
                    lignes = LignePresenceHebdomadaire.objects.filter(etudiant_id=etudiant_id, fiche__classe_id=salle_id)
                    if lignes.exists():
                        derniere_ligne = lignes.last()
                        derniere_ligne.heures_justifiees = hj_val
                        derniere_ligne.save()
                except ValueError:
                    pass

        messages.success(request, "✅ Heures justifiées (HJ) enregistrées avec succès.")

    data = calculer_notes_annuelles_discipline(salle_id)

    if request.GET.get('format') == 'pdf' or request.GET.get('export') == 'pdf':
        from apps.inscriptions.pdf_services import generer_notes_annuelles_discipline_pdf
        base_url = request.build_absolute_uri('/')[:-1]
        pdf_bytes = generer_notes_annuelles_discipline_pdf(data['classe'], data['results'], domain_url=base_url)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = f"Notes_Annuelles_Discipline_{getattr(data['classe'], 'nom', 'Classe')}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response

    context = {
        'data': data,
        'classe': data['classe'],
        'annee_academique': data['annee_academique'],
        'date_aujourdhui': timezone.now(),
        'titre': f"Notes Annuelles de Discipline - {data['classe'].nom}"
    }
    return render(request, 'cours/presences/note_annuelle_discipline_pdf.html', context)


@login_required
def exporter_liste_classe_presence_pdf(request, classe_id):
    """Génère la liste de classe sous forme de Fiche de Présence officielle PDF par salle/filière/niveau"""
    user = request.user
    role = getattr(user, 'type_utilisateur', None)
    if role not in ('CHEF_SCOLARITE', 'ADMIN_SYSTEME', 'CHEF_ETUDES') and not user.is_superuser:
        messages.error(request, "❌ Accès réservé au Chef de la Scolarité.")
        return redirect('tableau_bord:tableau_bord')

    from apps.etudiants.models import Classe, Etudiant
    from apps.cours.models import Salle
    from django.utils import timezone
    import datetime

    classe = Classe.objects.filter(pk=classe_id).select_related('filiere', 'niveau', 'annee_academique').first()
    if classe:
        etudiants = classe.etudiants.filter(statut__in=['INSCRIT', 'ACTIF']).order_by('nom', 'prenom')
    else:
        salle = Salle.objects.filter(pk=classe_id).first()
        if salle:
            classe_match = Classe.objects.filter(nom__icontains=salle.nom).first() or Classe.objects.filter(nom__icontains=salle.code).first()
            if classe_match:
                classe = classe_match
                etudiants = classe.etudiants.filter(statut__in=['INSCRIT', 'ACTIF']).order_by('nom', 'prenom')
            else:
                etudiants = Etudiant.objects.filter(statut__in=['INSCRIT', 'ACTIF']).order_by('nom', 'prenom')
                class FacticeClasse:
                    id = salle.id
                    nom = salle.nom
                    filiere = type('F', (), {'code': salle.code[:2] if salle.code else 'GL', 'nom': salle.nom})()
                    niveau = type('N', (), {'numero': 1})()
                    annee_academique = type('A', (), {'code': '2025-2026'})()
                classe = FacticeClasse()
        else:
            classe = Classe.objects.first()
            if not classe:
                messages.error(request, "Aucune classe disponible.")
                return redirect('tableau_bord:tableau_bord')
            etudiants = classe.etudiants.filter(statut__in=['INSCRIT', 'ACTIF']).order_by('nom', 'prenom')

    today = timezone.now().date()
    semaine_du = today - datetime.timedelta(days=today.weekday())
    semaine_au = semaine_du + datetime.timedelta(days=5)
    annee_code = getattr(getattr(classe, 'annee_academique', None), 'code', '2025-2026')

    # Récupérer la fiche de présence hebdomadaire si disponible pour injecter dynamiquement la grille d'absences
    from apps.cours.models import FichePresenceHebdomadaire
    import json

    fiche_id = request.GET.get('fiche')
    fiche = None
    if fiche_id:
        fiche = FichePresenceHebdomadaire.objects.filter(pk=fiche_id).first()
    
    if not fiche and classe and hasattr(classe, 'pk'):
        fiche = FichePresenceHebdomadaire.objects.filter(classe_id=classe.id, semaine_du=semaine_du).first()

    lignes_map = {}
    if fiche:
        semaine_du = fiche.semaine_du
        semaine_au = fiche.semaine_au
        for l in fiche.lignes.all():
            try:
                lignes_map[l.etudiant_id] = {
                    'absences': l.nombre_absences,
                    'details': json.loads(l.details_jours_json or '{}')
                }
            except Exception:
                lignes_map[l.etudiant_id] = {'absences': l.nombre_absences, 'details': {}}

    etudiants_liste = []
    for et in etudiants:
        info = lignes_map.get(et.id, {'absences': 0, 'details': {}})
        et.total_absences = info['absences']
        details = info['details']
        
        slots_flat = []
        for jour_key in ['lun', 'mar', 'mer', 'jeu', 'ven', 'sam']:
            day_slots = details.get(jour_key, [])
            if not isinstance(day_slots, list):
                day_slots = []
            for i in range(4):
                val = day_slots[i] if i < len(day_slots) else ''
                slots_flat.append(val)
        et.slots_flat = slots_flat
        etudiants_liste.append(et)

    if request.GET.get('format') == 'pdf' or request.GET.get('export') == 'pdf':
        from apps.inscriptions.pdf_services import generer_liste_presence_etudiants_pdf
        base_url = request.build_absolute_uri('/')[:-1]
        pdf_bytes = generer_liste_presence_etudiants_pdf(classe, semaine_du, semaine_au, etudiants_liste, domain_url=base_url)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = f"Liste_Presence_{getattr(classe, 'nom', 'Classe')}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response

    context = {
        'classe': classe,
        'etudiants': etudiants_liste,
        'fiche': fiche,
        'annee_academique': annee_code,
        'semaine_du': semaine_du,
        'semaine_au': semaine_au,
        'titre': f"Liste de Présence - {getattr(classe, 'nom', 'Classe')}"
    }
    return render(request, 'cours/presences/liste_classe_presence_pdf.html', context)


@login_required
def importer_emploi_du_temps_csv(request):
    """
    Importation multi-format de l'emploi du temps (Salle, Filière, Niveau) par le Chef des Études.
    Formats acceptés : CSV, Excel (.xlsx, .xls), PDF (.pdf), Image (.png, .jpg, .jpeg).
    """
    if request.user.type_utilisateur not in ['CHEF_ETUDES', 'ADMIN_SYSTEME', 'DIRECTEUR']:
        messages.error(request, "Accès réservé au Chef des Études et à la Direction.")
        return redirect('cours:emploi_du_temps_officiel')

    if request.method == 'POST' and (request.FILES.get('fichier_csv') or request.FILES.get('fichier_emploi')):
        uploaded_file = request.FILES.get('fichier_csv') or request.FILES.get('fichier_emploi')
        filiere_id = request.POST.get('filiere')
        salle_id = request.POST.get('salle')
        niveau = request.POST.get('niveau', 'LEVEL_1')
        titre_semaine = request.POST.get('titre_semaine', 'SEMAINE IMPORTÉE')
        date_debut = request.POST.get('date_debut_semaine')
        date_fin = request.POST.get('date_fin_semaine')

        if not filiere_id or not date_debut or not date_fin:
            messages.error(request, "Veuillez spécifier la filière, la date de début et la date de fin.")
            return redirect('cours:emploi_du_temps_officiel')

        filiere = get_object_or_404(Filiere, pk=filiere_id)
        salle = get_object_or_404(Salle, pk=salle_id) if salle_id else None

        emploi = EmploiDuTempsHebdomadaire.objects.create(
            filiere=filiere,
            salle=salle,
            niveau=niveau,
            titre_semaine=titre_semaine,
            date_debut_semaine=date_debut,
            date_fin_semaine=date_fin,
            soumis_par=request.user,
            statut='BROUILLON'
        )

        from .import_service import extraire_creneaux_multi_format
        try:
            import_result = extraire_creneaux_multi_format(uploaded_file)
            valid_items = import_result.get('valid_items', [])
            errors = import_result.get('errors', [])
            conflits = import_result.get('conflits', [])
            stats = import_result.get('stats', {})

            creneaux_crees = 0

            for c in valid_items:
                salle_nom = c.get('salle_nom') or (salle.code if salle else '')
                CreneauEmploiDuTemps.objects.update_or_create(
                    emploi_du_temps=emploi,
                    jour=c['jour'],
                    plage=c['plage'],
                    defaults={
                        'intitule': c['intitule'],
                        'enseignant_nom': c['enseignant_nom'],
                        'salle_nom': salle_nom,
                        'progression_heures': c['progression_heures'],
                        'type_evenement': c['type_evenement']
                    }
                )
                creneaux_crees += 1

            if creneaux_crees > 0:
                msg_success = f"✅ Emploi du temps '{emploi.titre_semaine}' importé avec succès ({creneaux_crees} créneaux enregistrés)."
                if conflits:
                    msg_success += f" ⚠️ {len(conflits)} conflit(s) de créneaux détecté(s)."
                messages.success(request, msg_success)
            else:
                messages.warning(request, f"⚠️ Emploi du temps créé en brouillon, mais aucun créneau valide n'a pu être extrait de '{uploaded_file.name}'.")

            if errors:
                for err in errors[:5]:
                    messages.error(request, f"Erreur import : {err}")
                if len(errors) > 5:
                    messages.error(request, f"... et {len(errors) - 5} autre(s) erreur(s).")

            return redirect('cours:imprimer_emploi_du_temps_officiel', pk=emploi.pk)

        except Exception as e:
            messages.error(request, f"Erreur lors de la lecture du fichier : {str(e)}")
            emploi.delete()
            return redirect('cours:emploi_du_temps_officiel')

    filieres = Filiere.objects.filter(est_active=True)
    salles = Salle.objects.filter(est_disponible=True)
    context = {
        'filieres': filieres,
        'salles': salles,
        'niveaux': EmploiDuTempsHebdomadaire.NIVEAU_CHOICES,
        'titre': "Importer un Emploi du Temps (Multi-Format)"
    }
    return render(request, 'cours/emploi_du_temps_importer.html', context)



@login_required
def exporter_emploi_du_temps_pdf(request, pk):
    """Téléchargement direct du PDF officiel de l'emploi du temps"""
    from apps.inscriptions.pdf_services import generer_emploi_du_temps_pdf
    emploi = get_object_or_404(EmploiDuTempsHebdomadaire.objects.select_related('filiere', 'salle'), pk=pk)

    base_url = request.build_absolute_uri('/')[:-1]
    pdf_bytes = generer_emploi_du_temps_pdf(emploi, domain_url=base_url)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f"Emploi_du_Temps_{emploi.filiere.code}_{emploi.niveau}_{emploi.pk}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@login_required
def exporter_emploi_du_temps_ics(request, pk):
    """Téléchargement du fichier iCalendar (.ics) pour synchronisation agenda"""
    from .ical_service import generer_ics_emploi_du_temps
    emploi = get_object_or_404(EmploiDuTempsHebdomadaire.objects.select_related('filiere', 'salle'), pk=pk)

    base_url = request.build_absolute_uri('/')[:-1]
    ics_bytes = generer_ics_emploi_du_temps(emploi, domain_url=base_url)

    response = HttpResponse(ics_bytes, content_type='text/calendar')
    filename = f"Emploi_du_Temps_{emploi.filiere.code}_{emploi.niveau}.ics"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def supprimer_ressource(request, pk):
    """Suppression d'un support pédagogique par l'enseignant ou l'admin avec répercussion immédiate"""
    ressource = get_object_or_404(RessourceCours, pk=pk)

    user = request.user
    prof_profile = getattr(user, 'profil_professeur', getattr(user, 'professeur', None))
    is_author = prof_profile is not None and ressource.cours.professeur == prof_profile
    is_admin = user.is_superuser or user.type_utilisateur in ['ADMIN_SYSTEME', 'CHEF_ETUDES']

    if not (is_author or is_admin):
        messages.error(request, "Vous n'avez pas la permission de supprimer ce support.")
        return redirect('tableau_bord:tableau_bord')

    titre = ressource.titre
    cours = ressource.cours

    # 1. Notifier les étudiants inscrits au cours de la suppression du support
    try:
        from apps.tableau_bord.models import Notification
        from apps.cours.models import InscriptionCours
        inscriptions = InscriptionCours.objects.filter(cours=cours, est_actif=True).select_related('etudiant__utilisateur')
        for insc in inscriptions:
            if insc.etudiant and insc.etudiant.utilisateur:
                Notification.objects.create(
                    utilisateur=insc.etudiant.utilisateur,
                    type='INFO',
                    titre=f"Support retiré : {cours.matiere.nom}",
                    message=f"Le support pédagogique '{titre}' a été retiré par l'enseignant.",
                    lien='/tableau-de-bord/'
                )
    except Exception:
        pass

    # 2. Suppression en BDD (django_cleanup supprime automatiquement le fichier physique du disque)
    ressource.delete()
    messages.success(request, f"Le support '{titre}' a été supprimé. La modification est appliquée en temps réel chez les étudiants.")
    return redirect(request.META.get('HTTP_REFERER', 'tableau_bord:tableau_bord'))


@login_required
def modifier_echeance_ressource(request, pk):
    """Modification ou définition de la date limite de remise physique par l'enseignant/admin"""
    ressource = get_object_or_404(RessourceCours, pk=pk)

    user = request.user
    prof_profile = getattr(user, 'profil_professeur', getattr(user, 'professeur', None))
    is_author = prof_profile is not None and ressource.cours.professeur == prof_profile
    is_admin = user.is_superuser or user.type_utilisateur in ['ADMIN_SYSTEME', 'CHEF_ETUDES', 'ENSEIGNANT']

    if not (is_author or is_admin):
        messages.error(request, "Vous n'avez pas la permission de modifier cette échéance.")
        return redirect('tableau_bord:tableau_bord')

    if request.method == 'POST':
        nouvelle_date = request.POST.get('date_limite_remise_physique')
        if nouvelle_date:
            ressource.date_limite_remise_physique = nouvelle_date
            ressource.save()
            messages.success(request, f"L'échéance de remise physique pour '{ressource.titre}' a été mise à jour.")
        else:
            ressource.date_limite_remise_physique = None
            ressource.save()
            messages.info(request, f"L'échéance de remise physique pour '{ressource.titre}' a été retirée.")

    return redirect(request.META.get('HTTP_REFERER', 'tableau_bord:tableau_bord'))


@login_required
def supprimer_echeance_ressource(request, pk):
    """Suppression directe de la date limite de remise physique pour un support"""
    ressource = get_object_or_404(RessourceCours, pk=pk)

    user = request.user
    prof_profile = getattr(user, 'profil_professeur', getattr(user, 'professeur', None))
    is_author = prof_profile is not None and ressource.cours.professeur == prof_profile
    is_admin = user.is_superuser or user.type_utilisateur in ['ADMIN_SYSTEME', 'CHEF_ETUDES', 'ENSEIGNANT']

    if not (is_author or is_admin):
        messages.error(request, "Vous n'avez pas la permission de modifier cette échéance.")
        return redirect('tableau_bord:tableau_bord')

    if request.method == 'POST':
        ressource.date_limite_remise_physique = None
        ressource.save()
        messages.success(request, f"L'échéance de remise physique pour '{ressource.titre}' a été supprimée avec succès.")

    return redirect(request.META.get('HTTP_REFERER', 'tableau_bord:tableau_bord'))





