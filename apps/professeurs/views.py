"""
Vues pour la gestion des professeurs
IAI-Cameroun - Centre de Douala
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db.models import Q, Sum
from django.core.paginator import Paginator
from django.http import HttpResponse

from .models import Professeur, Departement, ChargeHoraire, DocumentProfesseur
from .forms import ProfesseurForm, DepartementForm, ChargeHoraireForm
from apps.cours.models import Cours, SeanceCours


@login_required
def liste_professeurs(request):
    """Liste des professeurs avec recherche et filtrage"""
    queryset = Professeur.objects.all().select_related('departement')
    
    # Recherche
    recherche = request.GET.get('q', '')
    if recherche:
        queryset = queryset.filter(
            Q(matricule__icontains=recherche) |
            Q(nom__icontains=recherche) |
            Q(prenom__icontains=recherche) |
            Q(email__icontains=recherche) |
            Q(specialite__icontains=recherche)
        )
    
    # Filtres
    departement = request.GET.get('departement', '')
    if departement:
        queryset = queryset.filter(departement_id=departement)
    
    grade = request.GET.get('grade', '')
    if grade:
        queryset = queryset.filter(grade=grade)
    
    statut = request.GET.get('statut', '')
    if statut:
        queryset = queryset.filter(statut=statut)
    
    # Tri
    tri = request.GET.get('tri', 'nom')
    queryset = queryset.order_by(tri)
    
    # Pagination
    paginator = Paginator(queryset, 20)
    page = request.GET.get('page')
    professeurs = paginator.get_page(page)
    
    # Données pour les filtres
    departements = Departement.objects.filter(est_actif=True)
    
    context = {
        'professeurs': professeurs,
        'departements': departements,
        'grades': Professeur.GRADE_CHOICES,
        'statuts': Professeur.STATUT_CHOICES,
        'recherche': recherche,
        'filtre_departement': departement,
        'filtre_grade': grade,
        'filtre_statut': statut,
        'titre': 'Liste des Professeurs'
    }
    return render(request, 'professeurs/liste.html', context)


@login_required
def detail_professeur(request, pk):
    """Détail d'un professeur"""
    professeur = get_object_or_404(Professeur, pk=pk)
    
    # Cours assignés
    cours = Cours.objects.filter(
        professeur=professeur,
        est_actif=True
    ).select_related('matiere', 'filiere')
    
    # Charge horaire
    charges = ChargeHoraire.objects.filter(professeur=professeur).order_by('-annee_academique')
    
    # Documents
    documents = DocumentProfesseur.objects.filter(professeur=professeur)
    
    # Heures effectuées cette année
    from datetime import date
    annee_actuelle = '2024-2025'
    heures_effectuees = professeur.get_heures_enseignement(annee_actuelle)
    
    context = {
        'professeur': professeur,
        'cours': cours,
        'charges': charges,
        'documents': documents,
        'heures_effectuees': heures_effectuees,
        'titre': f'{professeur.nom} {professeur.prenom}'
    }
    return render(request, 'professeurs/detail.html', context)


@login_required
@permission_required('professeurs.add_professeur', raise_exception=True)
def ajouter_professeur(request):
    """Ajouter un nouveau professeur"""
    if request.method == 'POST':
        form = ProfesseurForm(request.POST, request.FILES)
        if form.is_valid():
            professeur = form.save()
            messages.success(request, f'Le professeur {professeur} a été créé avec succès.')
            return redirect('detail_professeur', pk=professeur.pk)
    else:
        form = ProfesseurForm()
    
    context = {
        'form': form,
        'titre': 'Nouveau Professeur'
    }
    return render(request, 'professeurs/form.html', context)


@login_required
@permission_required('professeurs.change_professeur', raise_exception=True)
def modifier_professeur(request, pk):
    """Modifier un professeur"""
    professeur = get_object_or_404(Professeur, pk=pk)
    
    if request.method == 'POST':
        form = ProfesseurForm(request.POST, request.FILES, instance=professeur)
        if form.is_valid():
            professeur = form.save()
            messages.success(request, f'Le professeur {professeur} a été modifié avec succès.')
            return redirect('detail_professeur', pk=professeur.pk)
    else:
        form = ProfesseurForm(instance=professeur)
    
    context = {
        'form': form,
        'professeur': professeur,
        'titre': f'Modifier {professeur}'
    }
    return render(request, 'professeurs/form.html', context)


@login_required
@permission_required('professeurs.delete_professeur', raise_exception=True)
def supprimer_professeur(request, pk):
    """Supprimer un professeur"""
    professeur = get_object_or_404(Professeur, pk=pk)
    
    if request.method == 'POST':
        nom_complet = str(professeur)
        professeur.delete()
        messages.success(request, f'Le professeur {nom_complet} a été supprimé avec succès.')
        return redirect('liste_professeurs')
    
    context = {
        'professeur': professeur,
        'titre': 'Supprimer le professeur'
    }
    return render(request, 'professeurs/confirmer_suppression.html', context)


@login_required
def liste_departements(request):
    """Liste des départements"""
    departements = Departement.objects.all().annotate(
        nombre_professeurs=Count('professeurs')
    )
    
    context = {
        'departements': departements,
        'titre': 'Liste des Départements'
    }
    return render(request, 'professeurs/departements.html', context)


@login_required
@permission_required('professeurs.add_departement', raise_exception=True)
def ajouter_departement(request):
    """Ajouter un département"""
    if request.method == 'POST':
        form = DepartementForm(request.POST)
        if form.is_valid():
            departement = form.save()
            messages.success(request, f'Le département {departement} a été créé avec succès.')
            return redirect('liste_departements')
    else:
        form = DepartementForm()
    
    context = {
        'form': form,
        'titre': 'Nouveau Département'
    }
    return render(request, 'professeurs/departement_form.html', context)


@login_required
def charge_horaire(request, pk):
    """Gérer la charge horaire d'un professeur"""
    professeur = get_object_or_404(Professeur, pk=pk)
    
    charges = ChargeHoraire.objects.filter(professeur=professeur).order_by('-annee_academique')
    
    if request.method == 'POST':
        form = ChargeHoraireForm(request.POST)
        if form.is_valid():
            charge = form.save(commit=False)
            charge.professeur = professeur
            charge.save()
            messages.success(request, 'La charge horaire a été ajoutée avec succès.')
            return redirect('charge_horaire', pk=professeur.pk)
    else:
        form = ChargeHoraireForm()
    
    context = {
        'professeur': professeur,
        'charges': charges,
        'form': form,
        'titre': f'Charge Horaire - {professeur}'
    }
    return render(request, 'professeurs/charge_horaire.html', context)


@login_required
def exporter_professeurs(request):
    """Exporter la liste des professeurs"""
    import csv
    
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="professeurs.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Matricule', 'Nom', 'Prénom', 'Grade', 'Département',
        'Spécialité', 'Téléphone', 'Email', 'Date d\'embauche',
        'Type de contrat', 'Statut'
    ])
    
    professeurs = Professeur.objects.all().select_related('departement')
    
    for prof in professeurs:
        writer.writerow([
            prof.matricule,
            prof.nom,
            prof.prenom,
            prof.get_grade_display(),
            prof.departement.nom if prof.departement else '',
            prof.specialite,
            prof.telephone,
            prof.email,
            prof.date_embauche,
            prof.get_type_contrat_display(),
            prof.get_statut_display(),
        ])
    
    return response


@login_required
def statistiques_professeurs(request):
    """Statistiques sur les professeurs"""
    # Par grade
    par_grade = []
    for code, nom in Professeur.GRADE_CHOICES:
        count = Professeur.objects.filter(grade=code).count()
        par_grade.append({'grade': nom, 'count': count})
    
    # Par département
    par_departement = []
    for dept in Departement.objects.filter(est_actif=True):
        count = Professeur.objects.filter(departement=dept).count()
        par_departement.append({'departement': dept.nom, 'count': count})
    
    # Par statut
    par_statut = []
    for code, nom in Professeur.STATUT_CHOICES:
        count = Professeur.objects.filter(statut=code).count()
        par_statut.append({'statut': nom, 'count': count})
    
    total = Professeur.objects.count()
    
    context = {
        'total': total,
        'par_grade': par_grade,
        'par_departement': par_departement,
        'par_statut': par_statut,
        'titre': 'Statistiques Professeurs'
    }
    return render(request, 'professeurs/statistiques.html', context)
