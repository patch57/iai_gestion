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
