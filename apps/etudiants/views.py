"""
Vues pour la gestion des étudiants
IAI-Cameroun - Centre de Douala
Version moderne avec interface attrayante et ergonomique
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db.models import Q, Avg, Count, Sum, F
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET
import json
import csv
from datetime import datetime, timedelta

from .models import (
    Etudiant, Filiere, Niveau, Classe, AnneeAcademique, 
    DocumentEtudiant, HistoriqueEtudiant, DocumentObligatoire
)
from .forms import (
    EtudiantForm, FiliereForm, NiveauForm, ClasseForm,
    DocumentEtudiantForm, RechercheEtudiantForm, 
    ImportEtudiantForm, ExportEtudiantForm,
    DocumentObligatoireForm
)
from apps.paiements.models import RecuPaiement, TranchePaiement
from apps.notes.models import Note, Bulletin
from apps.inscriptions.models import Inscription


# ==================== TABLEAU DE BORD MODERNE ====================

@login_required
def tableau_de_bord(request):
    """Tableau de bord moderne avec graphiques et indicateurs"""
    annee_active = AnneeAcademique.get_active()
    annee_code = annee_active.code if annee_active else '2024-2025'
    
    # Statistiques principales
    stats = {
        'total_etudiants': Etudiant.objects.filter(statut__in=['ACTIF', 'INSCRIT']).count(),
        'total_filieres': Filiere.objects.filter(est_active=True).count(),
        'total_classes': Classe.objects.filter(est_active=True).count(),
        'total_professeurs': 0,
        'evolution_mensuelle': _get_evolution_mensuelle(),
        'repartition_sexe': _get_repartition_sexe(),
        'repartition_statut': _get_repartition_statut(),
        'top_filieres': _get_top_filieres(),
        'paiements_en_attente': RecuPaiement.objects.filter(statut='EN_ATTENTE').count(),
        'documents_attente': DocumentEtudiant.objects.filter(est_valide=False, est_obligatoire=True).count(),
        'taux_remplissage': _get_taux_remplissage_classes(),
    }
    
    # Graphique d'évolution
    evolution = _get_evolution_5_ans()
    
    # Dernières inscriptions
    derniers_etudiants = Etudiant.objects.select_related('filiere', 'classe').order_by('-date_inscription')[:8]
    
    # Prochaines échéances
    echeances = TranchePaiement.objects.filter(
        date_limite__gte=timezone.now().date(),
        est_actif=True
    ).order_by('date_limite')[:5]
    
    # Alertes système
    alertes = _generer_alertes()
    
    context = {
        'stats': stats,
        'evolution': json.dumps(evolution),
        'derniers_etudiants': derniers_etudiants,
        'echeances': echeances,
        'alertes': alertes,
        'annee_active': annee_code,
        'titre': 'Tableau de Bord',
        'page': 'dashboard'
    }
    return render(request, 'etudiants/dashboard.html', context)


# ==================== GESTION DES ÉTUDIANTS ====================

@login_required
def liste_etudiants(request):
    """Liste des étudiants avec recherche avancée et filtres interactifs"""
    queryset = Etudiant.objects.select_related('filiere', 'classe', 'utilisateur')
    
    # Formulaire de recherche
    form = RechercheEtudiantForm(request.GET)
    recherche_active = False
    
    if form.is_valid():
        recherche = form.cleaned_data.get('recherche')
        if recherche:
            recherche_active = True
            queryset = queryset.filter(
                Q(matricule__icontains=recherche) |
                Q(nom__icontains=recherche) |
                Q(prenom__icontains=recherche) |
                Q(email__icontains=recherche)
            )
        
        filiere = form.cleaned_data.get('filiere')
        if filiere:
            recherche_active = True
            queryset = queryset.filter(filiere=filiere)
        
        statut = form.cleaned_data.get('statut')
        if statut:
            recherche_active = True
            queryset = queryset.filter(statut=statut)
        
        sexe = form.cleaned_data.get('sexe')
        if sexe:
            recherche_active = True
            queryset = queryset.filter(sexe=sexe)
    
    # Tri
    tri = request.GET.get('tri', '-date_inscription')
    queryset = queryset.order_by(tri)
    
    # Pagination
    paginator = Paginator(queryset, 20)
    page = request.GET.get('page', 1)
    etudiants = paginator.get_page(page)
    
    # Statistiques rapides
    stats_rapides = {
        'total': Etudiant.objects.count(),
        'actifs': Etudiant.objects.filter(statut='ACTIF').count(),
        'nouveaux': Etudiant.objects.filter(date_inscription__gte=timezone.now() - timedelta(days=30)).count(),
        'diplomes': Etudiant.objects.filter(statut='DIPLOME').count(),
    }
    
    context = {
        'etudiants': etudiants,
        'form': form,
        'recherche_active': recherche_active,
        'stats_rapides': stats_rapides,
        'filieres': Filiere.objects.filter(est_active=True),
        'titre': 'Liste des Étudiants',
        'page': 'etudiants'
    }
    return render(request, 'etudiants/liste.html', context)


@login_required
def detail_etudiant(request, pk):
    """Détail complet d'un étudiant avec onglets modernes"""
    etudiant = get_object_or_404(
        Etudiant.objects.select_related('filiere', 'classe', 'utilisateur', 'annee_academique'), 
        pk=pk
    )
    
    # Notes et résultats
    notes = Note.objects.filter(etudiant=etudiant, est_validee=True).select_related('evaluation__cours__matiere')
    moyenne_generale = notes.aggregate(Avg('valeur'))['valeur__avg']
    
    # Graphique des notes par matière
    graph_notes = _preparer_graphique_notes(notes)
    
    # Bulletins
    bulletins = Bulletin.objects.filter(etudiant=etudiant).order_by('-annee_academique', '-semestre')
    
    # Paiements
    recus = RecuPaiement.objects.filter(etudiant=etudiant).select_related('tranche').order_by('-date_televersement')
    statut_paiement = etudiant.statut_paiement()
    
    # Documents
    documents = DocumentEtudiant.objects.filter(etudiant=etudiant).order_by('-date_ajout')
    docs_manquants = _verifier_documents_obligatoires_etudiant(etudiant)
    
    # Inscriptions
    inscriptions = Inscription.objects.filter(etudiant=etudiant).select_related('annee_academique')
    
    # Historique
    historique = HistoriqueEtudiant.objects.filter(etudiant=etudiant).select_related('utilisateur')[:15]
    
    # Statistiques personnelles
    stats_perso = {
        'age': etudiant.get_age(),
        'duree_inscription': (timezone.now().date() - etudiant.date_inscription.date()).days,
        'nb_documents': documents.count(),
        'docs_valides': documents.filter(est_valide=True).count(),
    }
    
    context = {
        'etudiant': etudiant,
        'notes': notes[:10],
        'moyenne_generale': round(moyenne_generale, 2) if moyenne_generale else None,
        'graph_notes': json.dumps(graph_notes),
        'bulletins': bulletins,
        'recus': recus,
        'statut_paiement': statut_paiement,
        'documents': documents,
        'docs_manquants': docs_manquants,
        'inscriptions': inscriptions,
        'historique': historique,
        'stats_perso': stats_perso,
        'titre': f'{etudiant.get_nom_complet()}',
        'page': 'detail'
    }
    return render(request, 'etudiants/detail.html', context)


@login_required
@permission_required('etudiants.add_etudiant', raise_exception=True)
def ajouter_etudiant(request):
    """Ajouter un étudiant avec assistant étape par étape"""
    if request.method == 'POST':
        form = EtudiantForm(request.POST, request.FILES)
        if form.is_valid():
            etudiant = form.save()
            
            HistoriqueEtudiant.objects.create(
                etudiant=etudiant,
                action='CREATION',
                details=f'Création de la fiche étudiant par {request.user.get_full_name()}',
                utilisateur=request.user
            )
            
            messages.success(
                request, 
                f'🎉 Étudiant {etudiant.get_nom_complet()} créé avec succès !',
                extra_tags='animated bounceIn'
            )
            return redirect('etudiants:detail_etudiant', pk=etudiant.pk)
    else:
        form = EtudiantForm()
    
    context = {
        'form': form,
        'titre': 'Nouvel Étudiant',
        'page': 'ajout'
    }
    return render(request, 'etudiants/form.html', context)


@login_required
@permission_required('etudiants.change_etudiant', raise_exception=True)
def modifier_etudiant(request, pk):
    """Modifier un étudiant"""
    etudiant = get_object_or_404(Etudiant, pk=pk)
    
    if request.method == 'POST':
        form = EtudiantForm(request.POST, request.FILES, instance=etudiant)
        if form.is_valid():
            etudiant = form.save()
            
            HistoriqueEtudiant.objects.create(
                etudiant=etudiant,
                action='MODIFICATION',
                details=f'Modification des informations par {request.user.get_full_name()}',
                utilisateur=request.user
            )
            
            messages.success(request, f'✏️ Étudiant modifié avec succès !')
            return redirect('etudiants:detail_etudiant', pk=etudiant.pk)
    else:
        form = EtudiantForm(instance=etudiant)
    
    context = {
        'form': form,
        'etudiant': etudiant,
        'titre': f'Modifier {etudiant.get_nom_complet()}',
        'page': 'modification'
    }
    return render(request, 'etudiants/form.html', context)


@login_required
@permission_required('etudiants.delete_etudiant', raise_exception=True)
def supprimer_etudiant(request, pk):
    """Supprimer un étudiant avec confirmation AJAX"""
    etudiant = get_object_or_404(Etudiant, pk=pk)
    
    if request.method == 'POST':
        nom_complet = etudiant.get_nom_complet()
        etudiant.delete()
        messages.success(request, f'🗑️ Étudiant {nom_complet} supprimé avec succès !')
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return redirect('etudiants:liste_etudiants')
    
    context = {
        'etudiant': etudiant,
        'titre': 'Confirmation de suppression'
    }
    return render(request, 'etudiants/confirmer_suppression.html', context)


@login_required
def carte_etudiant(request, pk):
    """Générer la carte d'étudiant (vue imprimable)"""
    etudiant = get_object_or_404(Etudiant, pk=pk)
    
    if not etudiant.carte_etudiant_delivree:
        etudiant.carte_etudiant_delivree = True
        etudiant.date_delivrance_carte = timezone.now().date()
        etudiant.save()
    
    context = {
        'etudiant': etudiant,
        'date_aujourdhui': timezone.now(),
        'annee_active': AnneeAcademique.get_active(),
        'titre': f'Carte Étudiant - {etudiant.get_nom_complet()}'
    }
    return render(request, 'etudiants/carte.html', context)


# ==================== GESTION DES FILIÈRES ====================

@login_required
def liste_filieres(request):
    """Liste des filières avec statistiques visuelles"""
    filieres = Filiere.objects.annotate(
        nb_etudiants=Count('etudiants', filter=Q(etudiants__statut__in=['ACTIF', 'INSCRIT'])),
        nb_niveaux=Count('niveaux', distinct=True),
        nb_classes=Count('classes', filter=Q(classes__est_active=True))
    )
    
    # Calcul des pourcentages
    total_etudiants = sum(f.nb_etudiants for f in filieres)
    for f in filieres:
        f.pourcentage = round(f.nb_etudiants / total_etudiants * 100, 1) if total_etudiants > 0 else 0
    
    context = {
        'filieres': filieres,
        'total_etudiants': total_etudiants,
        'titre': 'Filières de Formation',
        'page': 'filieres'
    }
    return render(request, 'etudiants/filieres/liste.html', context)


@login_required
def detail_filiere(request, pk):
    """Détail d'une filière avec toutes les informations"""
    filiere = get_object_or_404(Filiere, pk=pk)
    
    # Statistiques
    stats = {
        'total_etudiants': Etudiant.objects.filter(filiere=filiere, statut__in=['ACTIF', 'INSCRIT']).count(),
        'total_classes': filiere.classes.filter(est_active=True).count(),
        'taux_reussite': _calculer_taux_reussite_filiere(filiere),
        'moyenne_generale': _calculer_moyenne_generale_filiere(filiere),
    }
    
    # Niveaux
    niveaux = Niveau.objects.filter(filiere=filiere)
    
    # Classes
    classes = Classe.objects.filter(filiere=filiere, est_active=True).annotate(
        effectif=Count('etudiants')
    )
    
    # Évolution des inscriptions
    evolution = []
    for i in range(5):
        annee = f"{datetime.now().year - 4 + i}-{datetime.now().year - 3 + i}"
        count = Etudiant.objects.filter(filiere=filiere, annee_academique=annee).count()
        evolution.append({'annee': annee, 'count': count})
    
    context = {
        'filiere': filiere,
        'stats': stats,
        'niveaux': niveaux,
        'classes': classes,
        'evolution': json.dumps(evolution),
        'titre': f'Filière {filiere.nom}'
    }
    return render(request, 'etudiants/filieres/detail.html', context)


@login_required
@permission_required('etudiants.add_filiere', raise_exception=True)
def ajouter_filiere(request):
    """Ajouter une filière"""
    if request.method == 'POST':
        form = FiliereForm(request.POST)
        if form.is_valid():
            filiere = form.save()
            messages.success(request, f'✅ Filière {filiere} créée avec succès !')
            return redirect('etudiants:liste_filieres')
    else:
        form = FiliereForm()
    
    context = {
        'form': form,
        'titre': 'Nouvelle Filière'
    }
    return render(request, 'etudiants/filieres/form.html', context)


@login_required
@permission_required('etudiants.change_filiere', raise_exception=True)
def modifier_filiere(request, pk):
    """Modifier une filière"""
    filiere = get_object_or_404(Filiere, pk=pk)
    
    if request.method == 'POST':
        form = FiliereForm(request.POST, instance=filiere)
        if form.is_valid():
            form.save()
            messages.success(request, f'✏️ Filière modifiée avec succès !')
            return redirect('etudiants:liste_filieres')
    else:
        form = FiliereForm(instance=filiere)
    
    context = {
        'form': form,
        'filiere': filiere,
        'titre': f'Modifier {filiere.nom}'
    }
    return render(request, 'etudiants/filieres/form.html', context)


@login_required
@permission_required('etudiants.delete_filiere', raise_exception=True)
def supprimer_filiere(request, pk):
    """Supprimer une filière"""
    filiere = get_object_or_404(Filiere, pk=pk)
    
    if request.method == 'POST':
        filiere.delete()
        messages.success(request, f'🗑️ Filière supprimée avec succès !')
        return redirect('etudiants:liste_filieres')
    
    context = {
        'filiere': filiere,
        'titre': 'Supprimer la filière'
    }
    return render(request, 'etudiants/filieres/supprimer.html', context)


# ==================== GESTION DES CLASSES ====================

@login_required
def liste_classes(request):
    """Liste des classes avec effectifs et indicateurs"""
    classes = Classe.objects.select_related('filiere', 'niveau', 'annee_academique').annotate(
        effectif=Count('etudiants')
    )
    
    # Calcul du taux de remplissage
    for classe in classes:
        classe.taux_remplissage = round(classe.effectif / classe.effectif_max * 100, 1) if classe.effectif_max > 0 else 0
    
    context = {
        'classes': classes,
        'titre': 'Classes',
        'page': 'classes'
    }
    return render(request, 'etudiants/classes/liste.html', context)


@login_required
def detail_classe(request, pk):
    """Détail d'une classe avec liste des étudiants"""
    classe = get_object_or_404(Classe.objects.select_related('filiere', 'niveau', 'annee_academique'), pk=pk)
    
    etudiants = Etudiant.objects.filter(classe=classe, statut__in=['ACTIF', 'INSCRIT']).select_related('utilisateur')
    
    # Statistiques de la classe
    stats = {
        'effectif': etudiants.count(),
        'capacite': classe.effectif_max,
        'taux_remplissage': round(etudiants.count() / classe.effectif_max * 100, 1) if classe.effectif_max > 0 else 0,
        'garcons': etudiants.filter(sexe='M').count(),
        'filles': etudiants.filter(sexe='F').count(),
    }
    
    context = {
        'classe': classe,
        'etudiants': etudiants,
        'stats': stats,
        'titre': f'Classe {classe.nom}'
    }
    return render(request, 'etudiants/classes/detail.html', context)


@login_required
@permission_required('etudiants.add_classe', raise_exception=True)
def ajouter_classe(request):
    """Ajouter une classe"""
    if request.method == 'POST':
        form = ClasseForm(request.POST)
        if form.is_valid():
            classe = form.save()
            messages.success(request, f'✅ Classe {classe.nom} créée avec succès !')
            return redirect('etudiants:liste_classes')
    else:
        form = ClasseForm()
    
    context = {
        'form': form,
        'titre': 'Nouvelle Classe'
    }
    return render(request, 'etudiants/classes/form.html', context)


@login_required
@permission_required('etudiants.change_classe', raise_exception=True)
def modifier_classe(request, pk):
    """Modifier une classe"""
    classe = get_object_or_404(Classe, pk=pk)
    
    if request.method == 'POST':
        form = ClasseForm(request.POST, instance=classe)
        if form.is_valid():
            form.save()
            messages.success(request, f'✏️ Classe modifiée avec succès !')
            return redirect('etudiants:liste_classes')
    else:
        form = ClasseForm(instance=classe)
    
    context = {
        'form': form,
        'classe': classe,
        'titre': f'Modifier {classe.nom}'
    }
    return render(request, 'etudiants/classes/form.html', context)


@login_required
@permission_required('etudiants.delete_classe', raise_exception=True)
def supprimer_classe(request, pk):
    """Supprimer une classe"""
    classe = get_object_or_404(Classe, pk=pk)
    
    if request.method == 'POST':
        classe.delete()
        messages.success(request, f'🗑️ Classe supprimée avec succès !')
        return redirect('etudiants:liste_classes')
    
    context = {
        'classe': classe,
        'titre': 'Supprimer la classe'
    }
    return render(request, 'etudiants/classes/supprimer.html', context)


# ==================== GESTION DES NIVEAUX ====================

@login_required
def liste_niveaux(request):
    """Liste des niveaux"""
    niveaux = Niveau.objects.select_related('filiere').annotate(
        nb_etudiants=Count('etudiants', filter=Q(etudiants__statut__in=['ACTIF', 'INSCRIT']))
    )
    
    context = {
        'niveaux': niveaux,
        'titre': 'Niveaux'
    }
    return render(request, 'etudiants/niveaux/liste.html', context)


@login_required
@permission_required('etudiants.add_niveau', raise_exception=True)
def ajouter_niveau(request):
    """Ajouter un niveau"""
    if request.method == 'POST':
        form = NiveauForm(request.POST)
        if form.is_valid():
            niveau = form.save()
            messages.success(request, f'✅ Niveau {niveau} créé avec succès !')
            return redirect('etudiants:liste_niveaux')
    else:
        form = NiveauForm()
    
    context = {
        'form': form,
        'titre': 'Nouveau Niveau'
    }
    return render(request, 'etudiants/niveaux/form.html', context)


@login_required
@permission_required('etudiants.change_niveau', raise_exception=True)
def modifier_niveau(request, pk):
    """Modifier un niveau"""
    niveau = get_object_or_404(Niveau, pk=pk)
    
    if request.method == 'POST':
        form = NiveauForm(request.POST, instance=niveau)
        if form.is_valid():
            form.save()
            messages.success(request, f'✏️ Niveau modifié avec succès !')
            return redirect('etudiants:liste_niveaux')
    else:
        form = NiveauForm(instance=niveau)
    
    context = {
        'form': form,
        'niveau': niveau,
        'titre': f'Modifier Niveau {niveau.numero}'
    }
    return render(request, 'etudiants/niveaux/form.html', context)


@login_required
@permission_required('etudiants.delete_niveau', raise_exception=True)
def supprimer_niveau(request, pk):
    """Supprimer un niveau"""
    niveau = get_object_or_404(Niveau, pk=pk)
    
    if request.method == 'POST':
        niveau.delete()
        messages.success(request, f'🗑️ Niveau supprimé avec succès !')
        return redirect('etudiants:liste_niveaux')
    
    context = {
        'niveau': niveau,
        'titre': 'Supprimer le niveau'
    }
    return render(request, 'etudiants/niveaux/supprimer.html', context)


# ==================== GESTION DES ANNÉES ACADÉMIQUES ====================

@login_required
def liste_annees_academiques(request):
    """Liste des années académiques"""
    annees = AnneeAcademique.objects.annotate(
        nb_etudiants=Count('etudiants')
    )
    
    context = {
        'annees': annees,
        'titre': 'Années académiques'
    }
    return render(request, 'etudiants/annees_academiques/liste.html', context)


@login_required
@permission_required('etudiants.add_anneeacademique', raise_exception=True)
def ajouter_annee_academique(request):
    """Ajouter une année académique"""
    if request.method == 'POST':
        form = AnneeAcademiqueForm(request.POST)
        if form.is_valid():
            annee = form.save()
            messages.success(request, f'✅ Année académique {annee} créée avec succès !')
            return redirect('etudiants:liste_annees_academiques')
    else:
        form = AnneeAcademiqueForm()
    
    context = {
        'form': form,
        'titre': 'Nouvelle année académique'
    }
    return render(request, 'etudiants/annees_academiques/form.html', context)


@login_required
@permission_required('etudiants.change_anneeacademique', raise_exception=True)
def modifier_annee_academique(request, pk):
    """Modifier une année académique"""
    annee = get_object_or_404(AnneeAcademique, pk=pk)
    
    if request.method == 'POST':
        form = AnneeAcademiqueForm(request.POST, instance=annee)
        if form.is_valid():
            form.save()
            messages.success(request, f'✏️ Année académique modifiée avec succès !')
            return redirect('etudiants:liste_annees_academiques')
    else:
        form = AnneeAcademiqueForm(instance=annee)
    
    context = {
        'form': form,
        'annee': annee,
        'titre': f'Modifier {annee.code}'
    }
    return render(request, 'etudiants/annees_academiques/form.html', context)


@login_required
@permission_required('etudiants.delete_anneeacademique', raise_exception=True)
def supprimer_annee_academique(request, pk):
    """Supprimer une année académique"""
    annee = get_object_or_404(AnneeAcademique, pk=pk)
    
    if request.method == 'POST':
        annee.delete()
        messages.success(request, f'🗑️ Année académique supprimée avec succès !')
        return redirect('etudiants:liste_annees_academiques')
    
    context = {
        'annee': annee,
        'titre': 'Supprimer l\'année académique'
    }
    return render(request, 'etudiants/annees_academiques/supprimer.html', context)


@login_required
@permission_required('etudiants.change_anneeacademique', raise_exception=True)
def activer_annee_academique(request, pk):
    """Activer une année académique"""
    annee = get_object_or_404(AnneeAcademique, pk=pk)
    annee.est_active = True
    annee.save()
    messages.success(request, f'✅ Année académique {annee.code} activée avec succès !')
    return redirect('etudiants:liste_annees_academiques')


# ==================== GESTION DES DOCUMENTS ====================

@login_required
def documents_etudiant(request, pk):
    """Gestion des documents d'un étudiant"""
    etudiant = get_object_or_404(Etudiant, pk=pk)
    
    # Documents déjà téléversés
    documents = DocumentEtudiant.objects.filter(etudiant=etudiant).order_by('-date_ajout')
    
    # Documents obligatoires requis
    docs_requis = DocumentObligatoire.objects.filter(
        est_actif=True
    ).filter(
        Q(filiere__isnull=True) | Q(filiere=etudiant.filiere)
    ).filter(
        Q(niveau__isnull=True) | Q(niveau=etudiant.niveau)
    )
    
    # Statut des documents
    docs_statut = []
    for doc_requis in docs_requis:
        doc_etudiant = documents.filter(type_document=doc_requis.type_document).first()
        docs_statut.append({
            'requis': doc_requis,
            'televerse': doc_etudiant is not None,
            'valide': doc_etudiant and doc_etudiant.est_valide,
            'doc_id': doc_etudiant.id if doc_etudiant else None,
            'url_televerser': reverse('etudiants:televerser_document', args=[etudiant.id, doc_requis.type_document])
        })
    
    context = {
        'etudiant': etudiant,
        'documents': documents,
        'docs_statut': docs_statut,
        'progression': _calculer_progression_documents(etudiant),
        'titre': f'Documents - {etudiant.get_nom_complet()}'
    }
    return render(request, 'etudiants/documents/liste.html', context)


@login_required
def televerser_document(request, pk, type_document):
    """Téléverser un document spécifique"""
    etudiant = get_object_or_404(Etudiant, pk=pk)
    
    doc_obligatoire = DocumentObligatoire.objects.filter(
        type_document=type_document, est_actif=True
    ).first()
    
    if request.method == 'POST':
        form = DocumentEtudiantForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.etudiant = etudiant
            document.type_document = type_document
            document.est_obligatoire = doc_obligatoire is not None
            
            if doc_obligatoire:
                document.description = doc_obligatoire.description
            
            document.save()
            
            messages.success(request, f'✅ Document téléversé avec succès !')
            return redirect('etudiants:documents_etudiant', pk=etudiant.pk)
    else:
        form = DocumentEtudiantForm()
    
    context = {
        'form': form,
        'etudiant': etudiant,
        'type_document': type_document,
        'type_display': dict(DocumentEtudiant.TYPE_DOCUMENT_CHOICES).get(type_document, type_document),
        'est_obligatoire': doc_obligatoire is not None,
        'description': doc_obligatoire.description if doc_obligatoire else '',
        'titre': f'Téléverser {dict(DocumentEtudiant.TYPE_DOCUMENT_CHOICES).get(type_document, type_document)}'
    }
    return render(request, 'etudiants/documents/televerser.html', context)


@login_required
def supprimer_document(request, doc_pk):
    """Supprimer un document"""
    document = get_object_or_404(DocumentEtudiant, pk=doc_pk)
    etudiant_pk = document.etudiant.pk
    
    if request.method == 'POST':
        document.delete()
        messages.success(request, '🗑️ Document supprimé avec succès !')
        return redirect('etudiants:documents_etudiant', pk=etudiant_pk)
    
    context = {
        'document': document,
        'titre': 'Supprimer le document'
    }
    return render(request, 'etudiants/documents/supprimer.html', context)


@login_required
@permission_required('etudiants.can_validate_documents', raise_exception=True)
def valider_document(request, doc_pk):
    """Valider un document"""
    document = get_object_or_404(DocumentEtudiant, pk=doc_pk)
    
    if request.method == 'POST':
        document.est_valide = True
        document.date_validation = timezone.now()
        document.valide_par = request.user
        document.save()
        
        _verifier_documents_complets(document.etudiant)
        
        messages.success(request, f'✅ Document "{document.get_type_document_display()}" validé avec succès !')
        return redirect('etudiants:documents_etudiant', pk=document.etudiant.pk)
    
    context = {
        'document': document,
        'titre': 'Valider le document'
    }
    return render(request, 'etudiants/documents/valider.html', context)


@login_required
@permission_required('etudiants.can_validate_documents', raise_exception=True)
def rejeter_document(request, doc_pk):
    """Rejeter un document"""
    document = get_object_or_404(DocumentEtudiant, pk=doc_pk)
    
    if request.method == 'POST':
        commentaire = request.POST.get('commentaire', '')
        document.est_valide = False
        document.commentaire = commentaire
        document.save()
        
        messages.warning(request, f'⚠️ Document "{document.get_type_document_display()}" rejeté.')
        return redirect('etudiants:documents_etudiant', pk=document.etudiant.pk)
    
    context = {
        'document': document,
        'titre': 'Rejeter le document'
    }
    return render(request, 'etudiants/documents/rejeter.html', context)


@login_required
@permission_required('etudiants.can_validate_documents', raise_exception=True)
def documents_en_attente(request):
    """Liste des documents en attente de validation"""
    documents = DocumentEtudiant.objects.filter(
        est_valide=False
    ).select_related('etudiant', 'etudiant__filiere').order_by('-date_ajout')
    
    # Filtres
    type_doc = request.GET.get('type')
    if type_doc:
        documents = documents.filter(type_document=type_doc)
    
    filiere_id = request.GET.get('filiere')
    if filiere_id:
        documents = documents.filter(etudiant__filiere_id=filiere_id)
    
    paginator = Paginator(documents, 20)
    page = request.GET.get('page', 1)
    documents_page = paginator.get_page(page)
    
    context = {
        'documents': documents_page,
        'total': documents.count(),
        'types_documents': DocumentEtudiant.TYPE_DOCUMENT_CHOICES,
        'filieres': Filiere.objects.filter(est_active=True),
        'titre': 'Documents en attente de validation'
    }
    return render(request, 'etudiants/documents/en_attente.html', context)


# ==================== GESTION DES DOCUMENTS OBLIGATOIRES ====================

@login_required
@permission_required('etudiants.can_manage_documents', raise_exception=True)
def liste_documents_obligatoires(request):
    """Liste des documents obligatoires (administration)"""
    documents = DocumentObligatoire.objects.select_related('filiere', 'niveau').all()
    
    context = {
        'documents': documents,
        'titre': 'Documents Obligatoires',
        'page': 'documents'
    }
    return render(request, 'etudiants/documents_obligatoires/liste.html', context)


@login_required
@permission_required('etudiants.can_manage_documents', raise_exception=True)
def ajouter_document_obligatoire(request):
    """Ajouter un document obligatoire"""
    if request.method == 'POST':
        form = DocumentObligatoireForm(request.POST)
        if form.is_valid():
            document = form.save()
            messages.success(request, f'✅ Document "{document.nom}" ajouté avec succès !')
            return redirect('etudiants:liste_documents_obligatoires')
    else:
        form = DocumentObligatoireForm()
    
    context = {
        'form': form,
        'titre': 'Ajouter un document obligatoire'
    }
    return render(request, 'etudiants/documents_obligatoires/form.html', context)


@login_required
@permission_required('etudiants.can_manage_documents', raise_exception=True)
def modifier_document_obligatoire(request, pk):
    """Modifier un document obligatoire"""
    document = get_object_or_404(DocumentObligatoire, pk=pk)
    
    if request.method == 'POST':
        form = DocumentObligatoireForm(request.POST, instance=document)
        if form.is_valid():
            form.save()
            messages.success(request, f'✏️ Document "{document.nom}" modifié avec succès !')
            return redirect('etudiants:liste_documents_obligatoires')
    else:
        form = DocumentObligatoireForm(instance=document)
    
    context = {
        'form': form,
        'document': document,
        'titre': f'Modifier {document.nom}'
    }
    return render(request, 'etudiants/documents_obligatoires/form.html', context)


@login_required
@permission_required('etudiants.can_manage_documents', raise_exception=True)
def supprimer_document_obligatoire(request, pk):
    """Supprimer un document obligatoire"""
    document = get_object_or_404(DocumentObligatoire, pk=pk)
    
    if request.method == 'POST':
        document.delete()
        messages.success(request, f'🗑️ Document "{document.nom}" supprimé avec succès !')
        return redirect('etudiants:liste_documents_obligatoires')
    
    context = {
        'document': document,
        'titre': 'Supprimer le document'
    }
    return render(request, 'etudiants/documents_obligatoires/supprimer.html', context)


# ==================== STATISTIQUES ====================

@login_required
def statistiques_etudiants(request):
    """Statistiques avancées avec graphiques"""
    annee = request.GET.get('annee', AnneeAcademique.get_active().code if AnneeAcademique.get_active() else '2024-2025')
    
    stats = {
        'total': Etudiant.objects.filter(annee_academique=annee).count(),
        'par_sexe': _get_stats_par_sexe(annee),
        'par_statut': _get_stats_par_statut(annee),
        'par_filiere': _get_stats_par_filiere(annee),
        'par_nationalite': _get_stats_par_nationalite(annee),
        'evolution_5_ans': _get_evolution_5_ans(),
        'age_pyramide': _get_pyramide_ages(annee),
        'taux_reussite': _get_taux_reussite_par_filiere(annee),
    }
    
    context = {
        'stats': stats,
        'annee': annee,
        'annees_disponibles': AnneeAcademique.objects.values_list('code', flat=True),
        'titre': 'Statistiques',
        'page': 'statistiques'
    }
    return render(request, 'etudiants/statistiques.html', context)


# ==================== EXPORT ====================

@login_required
def exporter_etudiants(request):
    """Exporter les étudiants en CSV"""
    format_export = request.GET.get('format', 'csv')
    filiere_id = request.GET.get('filiere')
    statut = request.GET.get('statut')
    
    queryset = Etudiant.objects.select_related('filiere', 'classe')
    
    if filiere_id:
        queryset = queryset.filter(filiere_id=filiere_id)
    if statut:
        queryset = queryset.filter(statut=statut)
    
    if format_export == 'csv':
        return _exporter_csv(queryset)
    elif format_export == 'excel':
        return _exporter_excel(queryset)
    elif format_export == 'pdf':
        return _exporter_pdf(queryset)
    
    return redirect('etudiants:liste_etudiants')


@login_required
def importer_etudiants(request):
    """Importer des étudiants"""
    if request.method == 'POST':
        form = ImportEtudiantForm(request.POST, request.FILES)
        if form.is_valid():
            messages.success(request, '✅ Import terminé avec succès !')
            return redirect('etudiants:liste_etudiants')
    else:
        form = ImportEtudiantForm()
    
    context = {
        'form': form,
        'titre': 'Importer des étudiants'
    }
    return render(request, 'etudiants/importer.html', context)


# ==================== API ====================

@require_GET
def api_recherche_etudiants(request):
    """API de recherche d'étudiants"""
    q = request.GET.get('q', '')
    if len(q) < 2:
        return JsonResponse({'results': []})
    
    etudiants = Etudiant.objects.filter(
        Q(matricule__icontains=q) |
        Q(nom__icontains=q) |
        Q(prenom__icontains=q)
    )[:10]
    
    results = [{
        'id': e.id,
        'matricule': e.matricule,
        'nom_complet': e.get_nom_complet(),
        'filiere': e.filiere.nom if e.filiere else '',
        'url': reverse('etudiants:detail_etudiant', args=[e.id])
    } for e in etudiants]
    
    return JsonResponse({'results': results})


@require_GET
def api_classes_par_filiere(request, filiere_id):
    """API pour récupérer les classes d'une filière"""
    classes = Classe.objects.filter(
        filiere_id=filiere_id,
        est_active=True
    ).values('id', 'nom')
    
    return JsonResponse({'classes': list(classes)})


# ==================== FONCTIONS UTILITAIRES ====================

def _get_evolution_mensuelle():
    """Évolution des inscriptions par mois"""
    from django.db.models.functions import TruncMonth
    evolution = Etudiant.objects.annotate(
        mois=TruncMonth('date_inscription')
    ).values('mois').annotate(
        count=Count('id')
    ).order_by('mois')[:12]
    
    return {
        'labels': [e['mois'].strftime('%b %Y') for e in evolution if e['mois']],
        'values': [e['count'] for e in evolution]
    }


def _get_repartition_sexe():
    """Répartition par sexe"""
    total = Etudiant.objects.count()
    if total == 0:
        return {'masculin': 0, 'feminin': 0}
    
    masculin = Etudiant.objects.filter(sexe='M').count()
    feminin = Etudiant.objects.filter(sexe='F').count()
    
    return {
        'masculin': round(masculin / total * 100, 1),
        'feminin': round(feminin / total * 100, 1)
    }


def _get_repartition_statut():
    """Répartition par statut"""
    statuts = {}
    for code, nom in Etudiant.STATUT_CHOICES:
        count = Etudiant.objects.filter(statut=code).count()
        if count > 0:
            statuts[nom] = count
    return statuts


def _get_top_filieres():
    """Top filières par nombre d'étudiants"""
    filieres = Filiere.objects.annotate(
        count=Count('etudiants')
    ).order_by('-count')[:5]
    
    return {
        'labels': [f.nom for f in filieres],
        'values': [f.count for f in filieres]
    }


def _get_taux_remplissage_classes():
    """Taux de remplissage des classes"""
    classes = Classe.objects.filter(est_active=True)
    if not classes:
        return 0
    
    total_remplissage = sum(c.effectif_actuel / c.effectif_max * 100 for c in classes)
    return round(total_remplissage / classes.count(), 1)


def _generer_alertes():
    """Générer les alertes du système"""
    alertes = []
    
    recus_attente = RecuPaiement.objects.filter(statut='EN_ATTENTE').count()
    if recus_attente > 0:
        alertes.append({
            'type': 'warning',
            'message': f'{recus_attente} reçu(s) en attente de vérification',
            'url': reverse('paiements:liste_recus'),
            'icon': 'receipt'
        })
    
    docs_attente = DocumentEtudiant.objects.filter(est_valide=False).count()
    if docs_attente > 0:
        alertes.append({
            'type': 'info',
            'message': f'{docs_attente} document(s) en attente de validation',
            'url': reverse('etudiants:documents_en_attente'),
            'icon': 'file-check'
        })
    
    return alertes


def _get_evolution_5_ans():
    """Évolution sur 5 ans"""
    evolution = []
    annee_actuelle = datetime.now().year
    
    for annee in range(annee_actuelle - 4, annee_actuelle + 1):
        code = f"{annee}-{annee+1}"
        count = Etudiant.objects.filter(annee_academique=code).count()
        evolution.append({'annee': code, 'count': count})
    
    return evolution


def _get_stats_par_sexe(annee):
    """Statistiques par sexe"""
    total = Etudiant.objects.filter(annee_academique=annee).count()
    if total == 0:
        return {'M': 0, 'F': 0}
    
    masculin = Etudiant.objects.filter(annee_academique=annee, sexe='M').count()
    feminin = Etudiant.objects.filter(annee_academique=annee, sexe='F').count()
    
    return {'M': round(masculin / total * 100, 1), 'F': round(feminin / total * 100, 1)}


def _get_stats_par_statut(annee):
    """Statistiques par statut"""
    statuts = {}
    for code, nom in Etudiant.STATUT_CHOICES:
        count = Etudiant.objects.filter(annee_academique=annee, statut=code).count()
        if count > 0:
            statuts[nom] = count
    return statuts


def _get_stats_par_filiere(annee):
    """Statistiques par filière"""
    filieres = Filiere.objects.annotate(
        count=Count('etudiants', filter=Q(etudiants__annee_academique=annee))
    )
    return {f.nom: f.count for f in filieres if f.count > 0}


def _get_stats_par_nationalite(annee):
    """Statistiques par nationalité"""
    nationalites = Etudiant.objects.filter(
        annee_academique=annee
    ).values('nationalite').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    return {n['nationalite']: n['count'] for n in nationalites}


def _get_pyramide_ages(annee):
    """Pyramide des âges"""
    from dateutil.relativedelta import relativedelta
    
    aujourdhui = timezone.now().date()
    tranches = {'18-20': 0, '21-25': 0, '26-30': 0, '31-35': 0, '35+': 0}
    
    for e in Etudiant.objects.filter(annee_academique=annee):
        age = relativedelta(aujourdhui, e.date_naissance).years
        if age <= 20:
            tranches['18-20'] += 1
        elif age <= 25:
            tranches['21-25'] += 1
        elif age <= 30:
            tranches['26-30'] += 1
        elif age <= 35:
            tranches['31-35'] += 1
        else:
            tranches['35+'] += 1
    
    return tranches


def _get_taux_reussite_par_filiere(annee):
    """Taux de réussite par filière"""
    taux = {}
    for f in Filiere.objects.all():
        total = Etudiant.objects.filter(filiere=f, annee_academique=annee).count()
        diplomes = Etudiant.objects.filter(filiere=f, annee_academique=annee, statut='DIPLOME').count()
        taux[f.nom] = round(diplomes / total * 100, 1) if total > 0 else 0
    return taux


def _preparer_graphique_notes(notes):
    """Préparer les données pour le graphique des notes"""
    matieres = {}
    for note in notes:
        matiere = note.evaluation.cours.matiere.nom
        if matiere not in matieres:
            matieres[matiere] = []
        matieres[matiere].append(note.valeur)
    
    return {
        'labels': list(matieres.keys()),
        'values': [round(sum(v)/len(v), 1) for v in matieres.values()]
    }


def _calculer_taux_reussite_filiere(filiere):
    """Calculer le taux de réussite par filière"""
    total = Etudiant.objects.filter(filiere=filiere).count()
    diplomes = Etudiant.objects.filter(filiere=filiere, statut='DIPLOME').count()
    return round(diplomes / total * 100, 1) if total > 0 else 0


def _calculer_moyenne_generale_filiere(filiere):
    """Calculer la moyenne générale par filière"""
    notes = Note.objects.filter(etudiant__filiere=filiere, est_validee=True)
    moyenne = notes.aggregate(Avg('valeur'))['valeur__avg']
    return round(moyenne, 2) if moyenne else 0


def _verifier_documents_obligatoires_etudiant(etudiant):
    """Vérifier quels documents obligatoires manquent"""
    docs_requis = DocumentObligatoire.objects.filter(
        est_actif=True
    ).filter(
        Q(filiere__isnull=True) | Q(filiere=etudiant.filiere)
    ).filter(
        Q(niveau__isnull=True) | Q(niveau=etudiant.niveau)
    )
    
    manquants = []
    for doc in docs_requis:
        existe = DocumentEtudiant.objects.filter(
            etudiant=etudiant,
            type_document=doc.type_document,
            est_valide=True
        ).exists()
        if not existe:
            manquants.append(doc)
    
    return manquants


def _verifier_documents_complets(etudiant):
    """Vérifier si tous les documents sont validés"""
    docs_manquants = _verifier_documents_obligatoires_etudiant(etudiant)
    
    if not docs_manquants and etudiant.statut == 'PREINSCRIT':
        etudiant.statut = 'INSCRIT'
        etudiant.save()
        messages.success(None, f'✅ Tous les documents de {etudiant.get_nom_complet()} sont validés !')


def _calculer_progression_documents(etudiant):
    """Calculer la progression des documents"""
    docs_requis = DocumentObligatoire.objects.filter(
        est_actif=True
    ).filter(
        Q(filiere__isnull=True) | Q(filiere=etudiant.filiere)
    ).filter(
        Q(niveau__isnull=True) | Q(niveau=etudiant.niveau)
    )
    
    if not docs_requis:
        return 100
    
    valides = 0
    for doc in docs_requis:
        if DocumentEtudiant.objects.filter(
            etudiant=etudiant,
            type_document=doc.type_document,
            est_valide=True
        ).exists():
            valides += 1
    
    return round(valides / docs_requis.count() * 100)


def _exporter_csv(queryset):
    """Export CSV"""
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="etudiants.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Matricule', 'Nom', 'Prénom', 'Date Naissance', 'Sexe', 'Nationalité', 'Téléphone', 'Email', 'Filière', 'Statut'])
    
    for e in queryset:
        writer.writerow([
            e.matricule, e.nom, e.prenom, e.date_naissance,
            e.get_sexe_display(), e.get_nationalite_display(),
            e.telephone, e.email,
            e.filiere.nom if e.filiere else '', e.get_statut_display()
        ])
    
    return response


def _exporter_excel(queryset):
    """Export Excel"""
    try:
        import xlwt
        response = HttpResponse(content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = 'attachment; filename="etudiants.xls"'
        
        wb = xlwt.Workbook(encoding='utf-8')
        ws = wb.add_sheet('Étudiants')
        
        style_header = xlwt.XFStyle()
        font_header = xlwt.Font()
        font_header.bold = True
        style_header.font = font_header
        
        headers = ['Matricule', 'Nom', 'Prénom', 'Date Naissance', 'Sexe', 'Nationalité', 'Téléphone', 'Email', 'Filière']
        for col, header in enumerate(headers):
            ws.write(0, col, header, style_header)
        
        for row, e in enumerate(queryset, 1):
            ws.write(row, 0, e.matricule)
            ws.write(row, 1, e.nom)
            ws.write(row, 2, e.prenom)
            ws.write(row, 3, e.date_naissance.strftime('%d/%m/%Y'))
            ws.write(row, 4, e.get_sexe_display())
            ws.write(row, 5, e.get_nationalite_display())
            ws.write(row, 6, e.telephone)
            ws.write(row, 7, e.email)
            ws.write(row, 8, e.filiere.nom if e.filiere else '')
        
        wb.save(response)
        return response
    except ImportError:
        return _exporter_csv(queryset)


def _exporter_pdf(queryset):
    """Export PDF"""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="etudiants.pdf"'
        
        doc = SimpleDocTemplate(response, pagesize=A4)
        story = []
        styles = getSampleStyleSheet()
        
        titre = Paragraph("Liste des Étudiants", styles['Title'])
        story.append(titre)
        story.append(Spacer(1, 20))
        
        data = [['Matricule', 'Nom', 'Prénom', 'Filière']]
        for e in queryset[:50]:
            data.append([e.matricule, e.nom, e.prenom, e.filiere.nom if e.filiere else ''])
        
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        story.append(table)
        doc.build(story)
        return response
    except ImportError:
        return _exporter_csv(queryset)
    
# ==================== EXPORT DES FILIÈRES ====================

@login_required
def exporter_filieres(request):
    """Exporter la liste des filières en CSV"""
    import csv
    
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="filieres.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Code', 'Nom', 'Durée (ans)', 'Active', 'Nombre d\'étudiants', 'Nombre de classes'])
    
    filieres = Filiere.objects.annotate(
        nb_etudiants=Count('etudiants'),
        nb_classes=Count('classes')
    )
    
    for f in filieres:
        writer.writerow([
            f.code,
            f.nom,
            f.duree_ans,
            'Oui' if f.est_active else 'Non',
            f.nb_etudiants,
            f.nb_classes
        ])
    
    return response


# ==================== STATISTIQUES PAR FILIÈRE ====================

@login_required
def statistiques_par_filiere(request):
    """Statistiques détaillées par filière"""
    filieres = Filiere.objects.filter(est_active=True).annotate(
        nb_etudiants=Count('etudiants', filter=Q(etudiants__statut__in=['ACTIF', 'INSCRIT'])),
        nb_diplomes=Count('etudiants', filter=Q(etudiants__statut='DIPLOME')),
        moyenne_generale=Avg('etudiants__notes__valeur', filter=Q(etudiants__notes__est_validee=True))
    )
    
    stats = []
    for f in filieres:
        taux_reussite = round(f.nb_diplomes / f.nb_etudiants * 100, 1) if f.nb_etudiants > 0 else 0
        stats.append({
            'filiere': f,
            'nb_etudiants': f.nb_etudiants,
            'nb_diplomes': f.nb_diplomes,
            'taux_reussite': taux_reussite,
            'moyenne_generale': round(f.moyenne_generale, 2) if f.moyenne_generale else 0
        })
    
    context = {
        'stats': stats,
        'titre': 'Statistiques par Filière',
        'page': 'statistiques'
    }
    return render(request, 'etudiants/statistiques_filieres.html', context)


# ==================== STATISTIQUES DES PAIEMENTS ====================

@login_required
def statistiques_paiements(request):
    """Statistiques des paiements"""
    annee = request.GET.get('annee', AnneeAcademique.get_active().code if AnneeAcademique.get_active() else '2024-2025')
    
    # Statistiques globales
    total_etudiants = Etudiant.objects.filter(annee_academique=annee).count()
    
    # Paiements par tranche
    stats_tranches = []
    for i in range(1, 5):
        tranche_nom = ['Pré-inscription', '1ère Tranche', '2ème Tranche', '3ème Tranche'][i-1]
        
        if i == 1:
            payes = Etudiant.objects.filter(annee_academique=annee, recu_preinscription_valide=True).count()
        else:
            payes = Etudiant.objects.filter(annee_academique=annee).filter(
                id__in=RecuPaiement.objects.filter(
                    tranche__numero=i, 
                    statut='VALIDE'
                ).values('etudiant_id')
            ).count()
        
        stats_tranches.append({
            'tranche': i,
            'nom': tranche_nom,
            'payes': payes,
            'total': total_etudiants,
            'taux': round(payes / total_etudiants * 100, 1) if total_etudiants > 0 else 0
        })
    
    # Recettes totales
    recettes_total = RecuPaiement.objects.filter(
        statut='VALIDE',
        tranche__annee_academique=annee
    ).aggregate(Sum('montant_mentionne'))['montant_mentionne__sum'] or 0
    
    context = {
        'stats_tranches': stats_tranches,
        'recettes_total': recettes_total,
        'annee': annee,
        'titre': 'Statistiques des Paiements',
        'page': 'statistiques'
    }
    return render(request, 'etudiants/statistiques_paiements.html', context)


# ==================== API NIVEAUX PAR FILIÈRE ====================

@require_GET
def api_niveaux_par_filiere(request, filiere_id):
    """API pour récupérer les niveaux d'une filière"""
    niveaux = Niveau.objects.filter(
        filiere_id=filiere_id
    ).values('id', 'numero', 'code')
    
    return JsonResponse({'niveaux': list(niveaux)})


# ==================== ÉTUDIANTS PAR CLASSE ====================

@login_required
def etudiants_par_classe(request, pk):
    """Liste des étudiants d'une classe"""
    classe = get_object_or_404(Classe.objects.select_related('filiere', 'niveau'), pk=pk)
    etudiants = Etudiant.objects.filter(classe=classe, statut__in=['ACTIF', 'INSCRIT']).select_related('utilisateur')
    
    context = {
        'classe': classe,
        'etudiants': etudiants,
        'effectif': etudiants.count(),
        'titre': f'Étudiants de la classe {classe.nom}'
    }
    return render(request, 'etudiants/classes/etudiants.html', context)


# ==================== ACTIONS DE MASSE ====================

@login_required
@permission_required('etudiants.change_etudiant', raise_exception=True)
def changement_classe_massif(request):
    """Changement de classe en masse"""
    if request.method == 'POST':
        classe_origine_id = request.POST.get('classe_origine')
        classe_destination_id = request.POST.get('classe_destination')
        statut = request.POST.get('statut', 'ACTIF')
        
        classe_origine = get_object_or_404(Classe, pk=classe_origine_id)
        classe_destination = get_object_or_404(Classe, pk=classe_destination_id)
        
        etudiants = Etudiant.objects.filter(classe=classe_origine, statut=statut)
        count = etudiants.count()
        
        for etudiant in etudiants:
            etudiant.classe = classe_destination
            etudiant.save()
            
            HistoriqueEtudiant.objects.create(
                etudiant=etudiant,
                action='CHANGEMENT_CLASSE',
                details=f'Changement de classe de {classe_origine.nom} vers {classe_destination.nom}',
                utilisateur=request.user
            )
        
        messages.success(request, f'✅ {count} étudiant(s) transféré(s) avec succès !')
        return redirect('etudiants:liste_classes')
    
    classes = Classe.objects.filter(est_active=True).select_related('filiere', 'niveau')
    
    context = {
        'classes': classes,
        'titre': 'Changement de classe en masse'
    }
    return render(request, 'etudiants/actions/changement_classe.html', context)


@login_required
def export_paiements(request):
    """Exporter les paiements en CSV"""
    import csv
    
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="paiements.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Matricule', 'Nom', 'Prénom', 'Pré-inscription', '1ère Tranche', '2ème Tranche', '3ème Tranche', 'Total Payé'])
    
    etudiants = Etudiant.objects.select_related('filiere').all()
    
    for e in etudiants:
        statuts = e.statut_paiement()
        total_paye = sum([
            1 if statuts['preinscription'] else 0,
            1 if statuts['tranche_1'] else 0,
            1 if statuts['tranche_2'] else 0,
            1 if statuts['tranche_3'] else 0
        ])
        
        writer.writerow([
            e.matricule,
            e.nom,
            e.prenom,
            '✓' if statuts['preinscription'] else '✗',
            '✓' if statuts['tranche_1'] else '✗',
            '✓' if statuts['tranche_2'] else '✗',
            '✓' if statuts['tranche_3'] else '✗',
            f"{total_paye}/4"
        ])
    
    return response


@login_required
@permission_required('etudiants.can_validate_documents', raise_exception=True)
def validation_recus_massive(request):
    """Validation massive des reçus"""
    if request.method == 'POST':
        recus_ids = request.POST.getlist('recus_ids')
        action = request.POST.get('action')
        
        recus = RecuPaiement.objects.filter(id__in=recus_ids)
        count = recus.count()
        
        if action == 'valider':
            recus.update(statut='VALIDE', date_verification=timezone.now(), verifie_par=request.user)
            messages.success(request, f'✅ {count} reçu(s) validé(s) avec succès !')
        elif action == 'rejeter':
            recus.update(statut='REJETE', date_verification=timezone.now(), verifie_par=request.user)
            messages.warning(request, f'⚠️ {count} reçu(s) rejeté(s).')
        
        return redirect('paiements:liste_recus')
    
    recus = RecuPaiement.objects.filter(statut='EN_ATTENTE').select_related('etudiant', 'tranche')
    
    context = {
        'recus': recus,
        'titre': 'Validation massive des reçus'
    }
    return render(request, 'etudiants/actions/validation_recus.html', context)


# ==================== GESTION DES INSCRIPTIONS ====================

@login_required
def liste_inscriptions(request):
    """Liste des inscriptions en attente"""
    inscriptions = Inscription.objects.select_related('etudiant', 'filiere', 'annee_academique').order_by('-date_inscription')
    
    # Filtres
    statut = request.GET.get('statut')
    if statut:
        inscriptions = inscriptions.filter(statut=statut)
    
    filiere_id = request.GET.get('filiere')
    if filiere_id:
        inscriptions = inscriptions.filter(filiere_id=filiere_id)
    
    paginator = Paginator(inscriptions, 20)
    page = request.GET.get('page', 1)
    inscriptions_page = paginator.get_page(page)
    
    context = {
        'inscriptions': inscriptions_page,
        'filieres': Filiere.objects.filter(est_active=True),
        'titre': 'Inscriptions'
    }
    return render(request, 'etudiants/inscriptions/liste.html', context)


@login_required
@permission_required('etudiants.can_validate_inscriptions', raise_exception=True)
def valider_inscription(request, pk):
    """Valider une inscription"""
    inscription = get_object_or_404(Inscription, pk=pk)
    inscription.statut = 'VALIDEE'
    inscription.date_validation = timezone.now()
    inscription.validee_par = request.user
    inscription.save()
    
    # Mettre à jour le statut de l'étudiant
    inscription.etudiant.statut = 'INSCRIT'
    inscription.etudiant.annee_academique = inscription.annee_academique
    inscription.etudiant.save()
    
    messages.success(request, f'✅ Inscription de {inscription.etudiant.get_nom_complet()} validée !')
    return redirect('etudiants:liste_inscriptions')


@login_required
@permission_required('etudiants.can_validate_inscriptions', raise_exception=True)
def rejeter_inscription(request, pk):
    """Rejeter une inscription"""
    inscription = get_object_or_404(Inscription, pk=pk)
    inscription.statut = 'REJETEE'
    inscription.save()
    
    messages.warning(request, f'⚠️ Inscription de {inscription.etudiant.get_nom_complet()} rejetée.')
    return redirect('etudiants:liste_inscriptions')


# ==================== VALIDATION DES DOCUMENTS ====================

@login_required
@permission_required('etudiants.can_validate_documents', raise_exception=True)
def valider_document(request, doc_pk):
    """Valider un document"""
    document = get_object_or_404(DocumentEtudiant, pk=doc_pk)
    document.est_valide = True
    document.date_validation = timezone.now()
    document.valide_par = request.user
    document.save()
    
    # Vérifier si tous les documents sont validés
    _verifier_documents_complets(document.etudiant)
    
    messages.success(request, f'✅ Document "{document.get_type_document_display()}" validé avec succès !')
    
    # Rediriger vers la page précédente
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('etudiants:documents_en_attente')


# ==================== DOCUMENTS EN ATTENTE ====================

@login_required
@permission_required('etudiants.can_validate_documents', raise_exception=True)
def documents_en_attente(request):
    """Liste des documents en attente de validation"""
    documents = DocumentEtudiant.objects.filter(
        est_valide=False
    ).select_related('etudiant', 'etudiant__filiere').order_by('-date_ajout')
    
    # Filtres
    type_doc = request.GET.get('type')
    if type_doc:
        documents = documents.filter(type_document=type_doc)
    
    filiere_id = request.GET.get('filiere')
    if filiere_id:
        documents = documents.filter(etudiant__filiere_id=filiere_id)
    
    paginator = Paginator(documents, 20)
    page = request.GET.get('page', 1)
    documents_page = paginator.get_page(page)
    
    context = {
        'documents': documents_page,
        'total': documents.count(),
        'types_documents': DocumentEtudiant.TYPE_DOCUMENT_CHOICES,
        'filieres': Filiere.objects.filter(est_active=True),
        'titre': 'Documents en attente de validation'
    }
    return render(request, 'etudiants/documents/en_attente.html', context)

# ==================== GESTION DES DOCUMENTS ÉTUDIANTS ====================

@login_required
def ajouter_document(request, pk):
    """Ajouter un document à un étudiant"""
    etudiant = get_object_or_404(Etudiant, pk=pk)
    
    if request.method == 'POST':
        form = DocumentEtudiantForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.etudiant = etudiant
            document.save()
            
            HistoriqueEtudiant.objects.create(
                etudiant=etudiant,
                action='DOCUMENT_AJOUTE',
                details=f'Ajout du document: {document.get_type_document_display()}',
                utilisateur=request.user
            )
            
            messages.success(request, '✅ Document ajouté avec succès !')
            return redirect('etudiants:documents_etudiant', pk=etudiant.pk)
    else:
        form = DocumentEtudiantForm()
    
    context = {
        'form': form,
        'etudiant': etudiant,
        'titre': 'Ajouter un document'
    }
    return render(request, 'etudiants/documents/ajouter.html', context)


@login_required
def televerser_document(request, pk, type_document):
    """Téléverser un document spécifique pour un étudiant"""
    etudiant = get_object_or_404(Etudiant, pk=pk)
    
    # Vérifier si c'est un document obligatoire
    doc_obligatoire = DocumentObligatoire.objects.filter(
        type_document=type_document,
        est_actif=True
    ).filter(
        Q(filiere__isnull=True) | Q(filiere=etudiant.filiere)
    ).filter(
        Q(niveau__isnull=True) | Q(niveau=etudiant.niveau)
    ).first()
    
    if request.method == 'POST':
        form = DocumentEtudiantForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.etudiant = etudiant
            document.type_document = type_document
            document.est_obligatoire = doc_obligatoire is not None
            
            if doc_obligatoire:
                document.description = doc_obligatoire.description
            
            document.save()
            
            HistoriqueEtudiant.objects.create(
                etudiant=etudiant,
                action='DOCUMENT_AJOUTE',
                details=f'Document "{document.get_type_document_display()}" téléversé',
                utilisateur=request.user
            )
            
            messages.success(request, f'✅ Document "{document.get_type_document_display()}" téléversé avec succès !')
            return redirect('etudiants:documents_etudiant', pk=etudiant.pk)
    else:
        initial = {}
        if doc_obligatoire:
            initial['description'] = doc_obligatoire.description
        form = DocumentEtudiantForm(initial=initial)
    
    context = {
        'form': form,
        'etudiant': etudiant,
        'type_document': type_document,
        'type_display': dict(DocumentEtudiant.TYPE_DOCUMENT_CHOICES).get(type_document, type_document),
        'est_obligatoire': doc_obligatoire is not None,
        'description_obligatoire': doc_obligatoire.description if doc_obligatoire else '',
        'titre': f'Téléverser {dict(DocumentEtudiant.TYPE_DOCUMENT_CHOICES).get(type_document, type_document)}'
    }
    return render(request, 'etudiants/documents/televerser.html', context)


@login_required
def documents_etudiant(request, pk):
    """Gestion des documents d'un étudiant"""
    etudiant = get_object_or_404(Etudiant, pk=pk)
    
    # Récupérer les documents déjà téléversés
    documents = DocumentEtudiant.objects.filter(etudiant=etudiant).order_by('-date_ajout')
    
    # Récupérer les documents obligatoires pour la filière de l'étudiant
    docs_obligatoires = DocumentObligatoire.objects.filter(
        est_actif=True
    ).filter(
        Q(filiere__isnull=True) | Q(filiere=etudiant.filiere)
    ).filter(
        Q(niveau__isnull=True) | Q(niveau=etudiant.niveau)
    )
    
    # Créer un dictionnaire des documents déjà téléversés par type
    docs_televerses = {d.type_document: d for d in documents}
    
    # Préparer la liste des documents obligatoires avec statut
    docs_statut = []
    for doc_oblig in docs_obligatoires:
        doc_etudiant = docs_televerses.get(doc_oblig.type_document)
        docs_statut.append({
            'obligatoire': doc_oblig,
            'televerse': doc_etudiant is not None,
            'valide': doc_etudiant and doc_etudiant.est_valide,
            'doc_id': doc_etudiant.id if doc_etudiant else None,
            'url_televerser': reverse('etudiants:televerser_document', args=[etudiant.pk, doc_oblig.type_document])
        })
    
    # Progression
    total_obligatoires = docs_obligatoires.count()
    valides = sum(1 for d in docs_statut if d['valide'])
    progression = round(valides / total_obligatoires * 100) if total_obligatoires > 0 else 100
    
    context = {
        'etudiant': etudiant,
        'documents': documents,
        'docs_statut': docs_statut,
        'progression': progression,
        'titre': f'Documents - {etudiant.get_nom_complet()}'
    }
    return render(request, 'etudiants/documents/liste.html', context)


@login_required
def supprimer_document(request, doc_pk):
    """Supprimer un document"""
    document = get_object_or_404(DocumentEtudiant, pk=doc_pk)
    etudiant_pk = document.etudiant.pk
    
    if request.method == 'POST':
        document.delete()
        
        HistoriqueEtudiant.objects.create(
            etudiant_id=etudiant_pk,
            action='DOCUMENT_SUPPRIME',
            details=f'Suppression du document: {document.get_type_document_display()}',
            utilisateur=request.user
        )
        
        messages.success(request, '🗑️ Document supprimé avec succès !')
        return redirect('etudiants:documents_etudiant', pk=etudiant_pk)
    
    context = {
        'document': document,
        'titre': 'Supprimer le document'
    }
    return render(request, 'etudiants/documents/supprimer.html', context)


@login_required
@permission_required('etudiants.can_validate_documents', raise_exception=True)
def valider_document(request, doc_pk):
    """Valider un document (pour les administrateurs)"""
    document = get_object_or_404(DocumentEtudiant, pk=doc_pk)
    
    if request.method == 'POST':
        document.est_valide = True
        document.date_validation = timezone.now()
        document.valide_par = request.user
        document.save()
        
        # Vérifier si tous les documents obligatoires sont validés
        _verifier_documents_complets(document.etudiant)
        
        messages.success(request, f'✅ Document "{document.get_type_document_display()}" validé avec succès !')
        return redirect(request.META.get('HTTP_REFERER', reverse('etudiants:documents_etudiant', args=[document.etudiant.pk])))
    
    context = {
        'document': document,
        'titre': 'Valider le document'
    }
    return render(request, 'etudiants/documents/valider.html', context)


@login_required
@permission_required('etudiants.can_validate_documents', raise_exception=True)
def rejeter_document(request, doc_pk):
    """Rejeter un document (pour les administrateurs)"""
    document = get_object_or_404(DocumentEtudiant, pk=doc_pk)
    
    if request.method == 'POST':
        commentaire = request.POST.get('commentaire', '')
        document.est_valide = False
        document.commentaire = commentaire
        document.save()
        
        messages.warning(request, f'⚠️ Document "{document.get_type_document_display()}" rejeté.')
        return redirect(request.META.get('HTTP_REFERER', reverse('etudiants:documents_etudiant', args=[document.etudiant.pk])))
    
    context = {
        'document': document,
        'titre': 'Rejeter le document'
    }
    return render(request, 'etudiants/documents/rejeter.html', context)


@login_required
@permission_required('etudiants.can_validate_documents', raise_exception=True)
def documents_en_attente(request):
    """Liste des documents en attente de validation (admin)"""
    documents = DocumentEtudiant.objects.filter(
        est_valide=False
    ).select_related('etudiant', 'etudiant__filiere').order_by('-date_ajout')
    
    # Filtrer par type de document
    type_doc = request.GET.get('type')
    if type_doc:
        documents = documents.filter(type_document=type_doc)
    
    # Filtrer par filière
    filiere_id = request.GET.get('filiere')
    if filiere_id:
        documents = documents.filter(etudiant__filiere_id=filiere_id)
    
    # Pagination
    paginator = Paginator(documents, 20)
    page = request.GET.get('page', 1)
    documents_page = paginator.get_page(page)
    
    context = {
        'documents': documents_page,
        'total': documents.count(),
        'types_documents': DocumentEtudiant.TYPE_DOCUMENT_CHOICES,
        'filieres': Filiere.objects.filter(est_active=True),
        'titre': 'Documents en attente de validation'
    }
    return render(request, 'etudiants/documents/en_attente.html', context)


# ==================== FONCTIONS UTILITAIRES POUR LES DOCUMENTS ====================

def _verifier_documents_complets(etudiant):
    """Vérifier si tous les documents obligatoires sont validés"""
    docs_obligatoires = DocumentObligatoire.objects.filter(
        est_actif=True
    ).filter(
        Q(filiere__isnull=True) | Q(filiere=etudiant.filiere)
    ).filter(
        Q(niveau__isnull=True) | Q(niveau=etudiant.niveau)
    )
    
    tous_valides = True
    for doc_oblig in docs_obligatoires:
        doc_etudiant = DocumentEtudiant.objects.filter(
            etudiant=etudiant,
            type_document=doc_oblig.type_document,
            est_valide=True
        ).first()
        
        if not doc_etudiant:
            tous_valides = False
            break
    
    if tous_valides and docs_obligatoires.exists():
        if etudiant.statut == 'PREINSCRIT':
            etudiant.statut = 'INSCRIT'
            etudiant.save()
            
            # Créer une notification
            from apps.tableau_bord.models import Notification
            Notification.objects.create(
                utilisateur=etudiant.utilisateur,
                type='SUCCESS',
                titre='Dossier complet !',
                message='Tous vos documents obligatoires ont été validés. Votre inscription est maintenant complète.',
                lien=reverse('etudiants:detail_etudiant', args=[etudiant.id])
            )


def _verifier_documents_obligatoires_etudiant(etudiant):
    """Vérifier quels documents obligatoires manquent pour un étudiant"""
    docs_obligatoires = DocumentObligatoire.objects.filter(
        est_actif=True
    ).filter(
        Q(filiere__isnull=True) | Q(filiere=etudiant.filiere)
    ).filter(
        Q(niveau__isnull=True) | Q(niveau=etudiant.niveau)
    )
    
    manquants = []
    for doc_oblig in docs_obligatoires:
        doc_etudiant = DocumentEtudiant.objects.filter(
            etudiant=etudiant,
            type_document=doc_oblig.type_document,
            est_valide=True
        ).first()
        
        if not doc_etudiant:
            manquants.append({
                'type_document': doc_oblig.type_document,
                'nom': doc_oblig.nom,
                'description': doc_oblig.description,
                'url_televerser': reverse('etudiants:televerser_document', args=[etudiant.id, doc_oblig.type_document])
            })
    
    return manquants


def _calculer_progression_documents(etudiant):
    """Calculer la progression des documents"""
    docs_obligatoires = DocumentObligatoire.objects.filter(
        est_actif=True
    ).filter(
        Q(filiere__isnull=True) | Q(filiere=etudiant.filiere)
    ).filter(
        Q(niveau__isnull=True) | Q(niveau=etudiant.niveau)
    )
    
    if not docs_obligatoires:
        return 100
    
    valides = 0
    for doc in docs_obligatoires:
        if DocumentEtudiant.objects.filter(
            etudiant=etudiant,
            type_document=doc.type_document,
            est_valide=True
        ).exists():
            valides += 1
    
    return round(valides / docs_obligatoires.count() * 100)