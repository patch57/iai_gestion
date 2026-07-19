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
    """Liste des cours avec recherche et filtrage"""
    queryset = Cours.objects.all().select_related('matiere', 'filiere', 'professeur', 'salle')
    
    # Recherche
    recherche = request.GET.get('q', '')
    if recherche:
        queryset = queryset.filter(
            Q(code__icontains=recherche) |
            Q(matiere__nom__icontains=recherche) |
            Q(professeur__nom__icontains=recherche)
        )
    
    # Filtres
    filiere = request.GET.get('filiere', '')
    if filiere:
        queryset = queryset.filter(filiere_id=filiere)
    
    professeur = request.GET.get('professeur', '')
    if professeur:
        queryset = queryset.filter(professeur_id=professeur)
    
    type_cours = request.GET.get('type_cours', '')
    if type_cours:
        queryset = queryset.filter(type_cours=type_cours)
    
    annee = request.GET.get('annee', '')
    if annee:
        queryset = queryset.filter(annee_academique=annee)
    
    # Tri
    queryset = queryset.order_by('jour', 'heure_debut')
    
    # Pagination
    paginator = Paginator(queryset, 20)
    page = request.GET.get('page')
    cours = paginator.get_page(page)
    
    # Données pour les filtres
    filieres = Filiere.objects.filter(est_active=True)
    
    context = {
        'cours': cours,
        'filieres': filieres,
        'types_cours': Cours.TYPE_COURS_CHOICES,
        'recherche': recherche,
        'titre': 'Liste des Cours'
    }
    return render(request, 'cours/liste.html', context)


@login_required
def detail_cours(request, pk):
    """Détail d'un cours"""
    cours = get_object_or_404(Cours, pk=pk)
    
    # Séances
    seances = SeanceCours.objects.filter(cours=cours).order_by('-date')
    
    # Étudiants inscrits
    inscriptions = cours.inscriptions_cours.filter(est_actif=True).select_related('etudiant')
    
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
    ).select_related('filiere')
    
    if filiere_id:
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
    inscriptions = seance.cours.inscriptions_cours.filter(est_actif=True)
    
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
        
    filiere_id = request.GET.get('filiere')
    niveau = request.GET.get('niveau')
    statut = request.GET.get('statut')
    
    if filiere_id:
        queryset = queryset.filter(filiere_id=filiere_id)
    if niveau:
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

