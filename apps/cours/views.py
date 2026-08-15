"""
Vues pour la gestion des cours
IAI-Cameroun - Centre de Douala
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.utils import timezone

from .models import Salle, Matiere, Cours, SeanceCours, Presence, RessourceCours, EmploiDuTemps
from .forms import SalleForm, MatiereForm, CoursForm, SeanceCoursForm, RessourceCoursForm
from apps.etudiants.models import Filiere


@login_required
def liste_cours(request):
    """Liste des cours & Programme Quotidien extrait de l'emploi du temps officiel (Section Cours Sidebar)"""
    from apps.cours.models import EmploiDuTempsHebdomadaire, CreneauEmploiDuTemps
    from django.utils import timezone
    
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
    
    # Filtre filière si sélectionnée
    filiere_id = request.GET.get('filiere', '')
    etudiant = getattr(request.user, 'etudiant_profile', None) if hasattr(request.user, 'etudiant_profile') else None
    if not etudiant:
        from apps.etudiants.models import Etudiant
        etudiant = Etudiant.objects.filter(utilisateur=request.user).first()
        
    filiere_obj = None
    if filiere_id:
        filiere_obj = Filiere.objects.filter(id=filiere_id).first()
    elif etudiant and etudiant.filiere:
        filiere_obj = etudiant.filiere
    else:
        filiere_obj = Filiere.objects.filter(est_active=True).first()

    emploi_hebdo = None
    if filiere_obj:
        emploi_hebdo = EmploiDuTempsHebdomadaire.objects.filter(
            filiere=filiere_obj,
            statut='VALIDE',
            date_debut_semaine__lte=today,
            date_fin_semaine__gte=today
        ).first()
        if not emploi_hebdo:
            emploi_hebdo = EmploiDuTempsHebdomadaire.objects.filter(
                filiere=filiere_obj,
                statut='VALIDE'
            ).order_by('-date_creation').first()

    creneaux_du_jour = []
    if emploi_hebdo and jour_code_actuel:
        creneaux_du_jour = CreneauEmploiDuTemps.objects.filter(
            emploi_du_temps=emploi_hebdo,
            jour=jour_code_actuel
        ).exclude(type_evenement='PAUSE').order_by('plage')

    filieres = Filiere.objects.filter(est_active=True)
    
    context = {
        'creneaux_du_jour': creneaux_du_jour,
        'nom_jour_actuel': nom_jour_actuel,
        'emploi_hebdo': emploi_hebdo,
        'filiere_selectionnee': filiere_obj,
        'filieres': filieres,
        'etudiant': etudiant,
        'titre': 'Programme Quotidien & Emploi du Temps'
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


@login_required
def liste_matieres(request):
    """Liste des matières"""
    matieres = Matiere.objects.all().annotate(
        nombre_cours=Count('cours')
    )
    
    context = {
        'matieres': matieres,
        'titre': 'Liste des Matières'
    }
    return render(request, 'cours/matieres.html', context)


@login_required
@permission_required('cours.add_matiere', raise_exception=True)
def ajouter_matiere(request):
    """Ajouter une matière"""
    if request.method == 'POST':
        form = MatiereForm(request.POST)
        if form.is_valid():
            matiere = form.save()
            messages.success(request, f'La matière {matiere} a été créée avec succès.')
            return redirect('liste_matieres')
    else:
        form = MatiereForm()
    
    context = {
        'form': form,
        'titre': 'Nouvelle Matière'
    }
    return render(request, 'cours/matiere_form.html', context)


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
    salles = Salle.objects.filter(est_disponible=True)
    
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
        messages.success(
            request, 
            f"✅ Emploi du temps '{emploi.titre_semaine}' approuvé et publié ! Il est désormais distribué aux Étudiants, Enseignants et Chef de la Scolarité."
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
def saisie_grille_presence(request, pk):
    """Grille de saisie et d'édition de la liste de présence hebdomadaire (Lun-Sam)"""
    from apps.cours.models import FichePresenceHebdomadaire, LignePresenceHebdomadaire
    import json

    fiche = get_object_or_404(FichePresenceHebdomadaire, pk=pk)
    lignes = fiche.lignes.all().select_related('etudiant')

    if request.method == 'POST':
        for ligne in lignes:
            e_id = ligne.etudiant.id
            grid_data = {}
            total_abs = 0
            
            for jour in ['lun', 'mar', 'mer', 'jeu', 'ven', 'sam']:
                slots = []
                for slot_num in range(1, 7):
                    field_name = f"abs_{e_id}_{jour}_{slot_num}"
                    val = request.POST.get(field_name, '').strip().upper()
                    slots.append(val)
                    if val == 'A':
                        total_abs += 1
                grid_data[jour] = slots
                
            ligne.nombre_absences = total_abs
            ligne.details_jours_json = json.dumps(grid_data)
            ligne.save()

        messages.success(request, f"💾 Grille de présence enregistrée ({fiche.classe.nom}).")
        return redirect('cours:saisie_grille_presence', pk=fiche.pk)

    lignes_data = []
    for l in lignes:
        try:
            details = json.loads(l.details_jours_json)
        except Exception:
            details = {}
            
        lignes_data.append({
            'ligne': l,
            'etudiant': l.etudiant,
            'details': details,
            'absences': l.nombre_absences
        })

    context = {
        'fiche': fiche,
        'lignes_data': lignes_data,
        'titre': f"Grille de Présence - {fiche.classe.nom}"
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

    context = {
        'classe': classe,
        'etudiants': etudiants,
        'annee_academique': annee_code,
        'semaine_du': semaine_du,
        'semaine_au': semaine_au,
        'titre': f"Liste de Présence - {getattr(classe, 'nom', 'Classe')}"
    }
    return render(request, 'cours/presences/liste_classe_presence_pdf.html', context)



