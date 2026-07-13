"""
Vues pour la gestion des inscriptions
IAI-Cameroun - Centre de Douala
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.urls import reverse

from .models import (
    AnneeAcademique, Inscription, DocumentInscription, HistoriqueInscription, Bourse
)
from .forms import (
    InscriptionForm, DocumentInscriptionForm, BourseForm
)
from apps.etudiants.models import Etudiant, Filiere, Niveau, Classe
from apps.paiements.models import RecuPaiement, TranchePaiement


@login_required
def liste_inscriptions(request):
    """Liste des inscriptions"""
    queryset = Inscription.objects.all().select_related('etudiant', 'filiere', 'annee_academique')
    
    # Filtres
    recherche = request.GET.get('q', '')
    if recherche:
        queryset = queryset.filter(
            Q(etudiant__matricule__icontains=recherche) |
            Q(etudiant__nom__icontains=recherche) |
            Q(etudiant__prenom__icontains=recherche)
        )
    
    filiere = request.GET.get('filiere', '')
    if filiere:
        queryset = queryset.filter(filiere_id=filiere)
    
    statut = request.GET.get('statut', '')
    if statut:
        queryset = queryset.filter(statut=statut)
    
    type_inscription = request.GET.get('type', '')
    if type_inscription:
        queryset = queryset.filter(type_inscription=type_inscription)
    
    annee_id = request.GET.get('annee', '')
    if annee_id:
        queryset = queryset.filter(annee_academique_id=annee_id)
    
    # Pagination
    paginator = Paginator(queryset.order_by('-date_inscription'), 20)
    page = request.GET.get('page')
    inscriptions = paginator.get_page(page)
    
    context = {
        'inscriptions': inscriptions,
        'filieres': Filiere.objects.filter(est_active=True),
        'annees': AnneeAcademique.objects.all(),
        'statuts': Inscription.STATUT_CHOICES,
        'types': Inscription.TYPE_INSCRIPTION_CHOICES,
        'titre': 'Liste des Inscriptions'
    }
    return render(request, 'inscriptions/liste.html', context)


@login_required
def detail_inscription(request, pk):
    """Détail d'une inscription"""
    inscription = get_object_or_404(
        Inscription.objects.select_related('etudiant', 'filiere', 'annee_academique'),
        pk=pk
    )
    
    # Récupérer les reçus de paiement associés
    recus = RecuPaiement.objects.filter(
        etudiant=inscription.etudiant,
        tranche__annee_academique=inscription.annee_academique.code
    ).select_related('tranche')
    
    # Documents d'inscription
    documents = DocumentInscription.objects.filter(inscription=inscription).order_by('-date_ajout')
    
    # Historique
    historique = HistoriqueInscription.objects.filter(inscription=inscription).select_related('utilisateur')[:20]
    
    # Calcul des statistiques de paiement
    statut_paiement = inscription.statut_paiement()
    pourcentage_paiement = inscription.pourcentage_paiement()
    
    context = {
        'inscription': inscription,
        'recus': recus,
        'documents': documents,
        'historique': historique,
        'statut_paiement': statut_paiement,
        'pourcentage_paiement': round(pourcentage_paiement, 1),
        'titre': f'Inscription - {inscription.etudiant.get_nom_complet()}'
    }
    return render(request, 'inscriptions/detail.html', context)


@login_required
@permission_required('inscriptions.add_inscription', raise_exception=True)
def nouvelle_inscription(request):
    """Nouvelle inscription"""
    if request.method == 'POST':
        form = InscriptionForm(request.POST)
        if form.is_valid():
            inscription = form.save()
            
            # Créer l'historique
            HistoriqueInscription.objects.create(
                inscription=inscription,
                action='CREATION',
                details=f'Inscription créée par {request.user.get_full_name()}',
                utilisateur=request.user
            )
            
            messages.success(
                request, 
                f'✅ L\'inscription de {inscription.etudiant.get_nom_complet()} a été créée avec succès.'
            )
            return redirect('inscriptions:detail_inscription', pk=inscription.pk)
    else:
        form = InscriptionForm()
    
    context = {
        'form': form,
        'titre': 'Nouvelle Inscription'
    }
    return render(request, 'inscriptions/form.html', context)


@login_required
@permission_required('inscriptions.change_inscription', raise_exception=True)
def modifier_inscription(request, pk):
    """Modifier une inscription"""
    inscription = get_object_or_404(Inscription, pk=pk)
    
    if request.method == 'POST':
        form = InscriptionForm(request.POST, instance=inscription)
        if form.is_valid():
            inscription = form.save()
            
            HistoriqueInscription.objects.create(
                inscription=inscription,
                action='MODIFICATION',
                details=f'Inscription modifiée par {request.user.get_full_name()}',
                utilisateur=request.user
            )
            
            messages.success(request, f'✏️ Inscription modifiée avec succès.')
            return redirect('inscriptions:detail_inscription', pk=inscription.pk)
    else:
        form = InscriptionForm(instance=inscription)
    
    context = {
        'form': form,
        'inscription': inscription,
        'titre': f'Modifier l\'inscription'
    }
    return render(request, 'inscriptions/form.html', context)


@login_required
@permission_required('inscriptions.change_inscription', raise_exception=True)
def valider_inscription(request, pk):
    """Valider une inscription"""
    inscription = get_object_or_404(Inscription, pk=pk)
    
    if request.method == 'POST':
        inscription.statut = 'VALIDEE'
        inscription.date_validation = timezone.now()
        inscription.validee_par = request.user
        inscription.save()
        
        # Mettre à jour le statut de l'étudiant
        inscription.etudiant.statut = 'INSCRIT'
        inscription.etudiant.annee_academique = inscription.annee_academique
        inscription.etudiant.save()
        
        HistoriqueInscription.objects.create(
            inscription=inscription,
            action='VALIDATION',
            details=f'Inscription validée par {request.user.get_full_name()}',
            utilisateur=request.user
        )
        
        messages.success(request, f'✅ L\'inscription a été validée avec succès.')
        return redirect('inscriptions:detail_inscription', pk=pk)
    
    context = {
        'inscription': inscription,
        'titre': 'Valider l\'inscription'
    }
    return render(request, 'inscriptions/valider.html', context)


@login_required
@permission_required('inscriptions.change_inscription', raise_exception=True)
def rejeter_inscription(request, pk):
    """Rejeter une inscription"""
    inscription = get_object_or_404(Inscription, pk=pk)
    
    if request.method == 'POST':
        motif = request.POST.get('motif', '')
        inscription.statut = 'REJETEE'
        inscription.commentaire = motif
        inscription.save()
        
        HistoriqueInscription.objects.create(
            inscription=inscription,
            action='REJET',
            details=f'Inscription rejetée par {request.user.get_full_name()}. Motif: {motif}',
            utilisateur=request.user
        )
        
        messages.warning(request, f'⚠️ L\'inscription a été rejetée.')
        return redirect('inscriptions:liste_inscriptions')
    
    context = {
        'inscription': inscription,
        'titre': 'Rejeter l\'inscription'
    }
    return render(request, 'inscriptions/rejeter.html', context)


@login_required
def supprimer_inscription(request, pk):
    """Supprimer une inscription"""
    inscription = get_object_or_404(Inscription, pk=pk)
    
    if request.method == 'POST':
        inscription.delete()
        messages.success(request, '🗑️ Inscription supprimée avec succès.')
        return redirect('inscriptions:liste_inscriptions')
    
    context = {
        'inscription': inscription,
        'titre': 'Supprimer l\'inscription'
    }
    return render(request, 'inscriptions/supprimer.html', context)


@login_required
@permission_required('inscriptions.add_document', raise_exception=True)
def ajouter_document(request, pk):
    """Ajouter un document à une inscription"""
    inscription = get_object_or_404(Inscription, pk=pk)
    
    if request.method == 'POST':
        form = DocumentInscriptionForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.inscription = inscription
            document.save()
            
            HistoriqueInscription.objects.create(
                inscription=inscription,
                action='DOCUMENT_AJOUTE',
                details=f'Ajout du document: {document.get_type_document_display()} par {request.user.get_full_name()}',
                utilisateur=request.user
            )
            
            messages.success(request, '✅ Document ajouté avec succès !')
            return redirect('inscriptions:detail_inscription', pk=inscription.pk)
    else:
        form = DocumentInscriptionForm()
    
    context = {
        'form': form,
        'inscription': inscription,
        'titre': 'Ajouter un document'
    }
    return render(request, 'inscriptions/ajouter_document.html', context)


@login_required
@permission_required('inscriptions.change_document', raise_exception=True)
def valider_document(request, doc_pk):
    """Valider un document d'inscription"""
    document = get_object_or_404(DocumentInscription, pk=doc_pk)
    
    if request.method == 'POST':
        document.est_valide = True
        document.date_validation = timezone.now()
        document.valide_par = request.user
        document.save()
        
        HistoriqueInscription.objects.create(
            inscription=document.inscription,
            action='DOCUMENT_VALIDE',
            details=f'Document "{document.get_type_document_display()}" validé par {request.user.get_full_name()}',
            utilisateur=request.user
        )
        
        messages.success(request, f'✅ Document "{document.get_type_document_display()}" validé avec succès !')
        return redirect('inscriptions:detail_inscription', pk=document.inscription.pk)
    
    context = {
        'document': document,
        'titre': 'Valider le document'
    }
    return render(request, 'inscriptions/valider_document.html', context)


@login_required
def supprimer_document(request, doc_pk):
    """Supprimer un document d'inscription"""
    document = get_object_or_404(DocumentInscription, pk=doc_pk)
    inscription_pk = document.inscription.pk
    
    if request.method == 'POST':
        document.delete()
        
        HistoriqueInscription.objects.create(
            inscription_id=inscription_pk,
            action='DOCUMENT_SUPPRIME',
            details=f'Suppression du document: {document.get_type_document_display()}',
            utilisateur=request.user
        )
        
        messages.success(request, '🗑️ Document supprimé avec succès !')
        return redirect('inscriptions:detail_inscription', pk=inscription_pk)
    
    context = {
        'document': document,
        'titre': 'Supprimer le document'
    }
    return render(request, 'inscriptions/supprimer_document.html', context)


@login_required
def documents_en_attente(request):
    """Liste des documents en attente de validation"""
    documents = DocumentInscription.objects.filter(
        est_valide=False
    ).select_related('inscription__etudiant', 'inscription__filiere').order_by('-date_ajout')
    
    # Filtres
    type_doc = request.GET.get('type')
    if type_doc:
        documents = documents.filter(type_document=type_doc)
    
    filiere_id = request.GET.get('filiere')
    if filiere_id:
        documents = documents.filter(inscription__filiere_id=filiere_id)
    
    # Pagination
    paginator = Paginator(documents, 20)
    page = request.GET.get('page', 1)
    documents_page = paginator.get_page(page)
    
    context = {
        'documents': documents_page,
        'total': documents.count(),
        'types_documents': DocumentInscription.TYPE_DOCUMENT_CHOICES,
        'filieres': Filiere.objects.filter(est_active=True),
        'titre': 'Documents en attente de validation'
    }
    return render(request, 'inscriptions/documents_attente.html', context)


@login_required
def statistiques_inscriptions(request):
    """Statistiques des inscriptions"""
    annee_active = AnneeAcademique.get_active()
    annee = request.GET.get('annee', annee_active.code if annee_active else '2024-2025')
    
    # Statistiques par filière
    stats_filiere = []
    for filiere in Filiere.objects.filter(est_active=True):
        inscriptions = Inscription.objects.filter(
            filiere=filiere,
            annee_academique__code=annee
        )
        
        total = inscriptions.count()
        validees = inscriptions.filter(statut='VALIDEE').count()
        rejetees = inscriptions.filter(statut='REJETEE').count()
        en_attente = inscriptions.filter(statut__in=['PREINSCRIPTION', 'EN_ATTENTE']).count()
        
        stats_filiere.append({
            'filiere': filiere,
            'total': total,
            'validees': validees,
            'rejetees': rejetees,
            'en_attente': en_attente,
            'taux_reussite': round(validees / total * 100, 1) if total > 0 else 0
        })
    
    # Évolution des inscriptions
    evolution = []
    for i in range(5):
        annee_code = f"{2020 + i}-{2021 + i}"
        count = Inscription.objects.filter(annee_academique__code=annee_code).count()
        evolution.append({'annee': annee_code, 'count': count})
    
    context = {
        'stats_filiere': stats_filiere,
        'evolution': evolution,
        'annee': annee,
        'annees': AnneeAcademique.objects.values_list('code', flat=True),
        'titre': 'Statistiques des inscriptions'
    }
    return render(request, 'inscriptions/statistiques.html', context)


@login_required
def api_inscriptions_attente(request):
    """API pour le nombre d'inscriptions en attente"""
    count = Inscription.objects.filter(statut__in=['PREINSCRIPTION', 'EN_ATTENTE']).count()
    return JsonResponse({'count': count})


@login_required
def exporter_inscriptions(request):
    """Exporter les inscriptions en CSV"""
    import csv
    
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="inscriptions.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Matricule', 'Nom', 'Prénom', 'Filière', 'Année Académique',
        'Type', 'Statut', 'Date Inscription', 'Pré-inscription', '1ère Tranche',
        '2ème Tranche', '3ème Tranche'
    ])
    
    inscriptions = Inscription.objects.select_related('etudiant', 'filiere', 'annee_academique')
    
    for ins in inscriptions:
        statut_paiement = ins.statut_paiement()
        writer.writerow([
            ins.etudiant.matricule,
            ins.etudiant.nom,
            ins.etudiant.prenom,
            ins.filiere.nom,
            ins.annee_academique.code,
            ins.get_type_inscription_display(),
            ins.get_statut_display(),
            ins.date_inscription.strftime('%d/%m/%Y'),
            '✓' if statut_paiement['preinscription'] else '✗',
            '✓' if statut_paiement['tranche_1'] else '✗',
            '✓' if statut_paiement['tranche_2'] else '✗',
            '✓' if statut_paiement['tranche_3'] else '✗',
        ])
    
    return response


# ==================== VALIDATION DES REÇUS ====================

@login_required
@permission_required('inscriptions.can_validate_recus', raise_exception=True)
def valider_recu_preinscription(request, pk):
    """Valider le reçu de pré-inscription"""
    inscription = get_object_or_404(Inscription, pk=pk)
    inscription.valider_recu_preinscription(request.user)
    messages.success(request, '✅ Reçu de pré-inscription validé avec succès !')
    return redirect('inscriptions:detail_inscription', pk=pk)


@login_required
@permission_required('inscriptions.can_validate_recus', raise_exception=True)
def valider_recu_tranche(request, pk, numero_tranche):
    """Valider le reçu d'une tranche"""
    inscription = get_object_or_404(Inscription, pk=pk)
    inscription.valider_recu_tranche(numero_tranche, request.user)
    messages.success(request, f'✅ Reçu de la {numero_tranche}ème tranche validé avec succès !')
    return redirect('inscriptions:detail_inscription', pk=pk)


# ==================== PAIEMENTS (REDIRECTION) ====================

@login_required
def ajouter_paiement(request, inscription_id):
    """Ajouter un paiement (redirige vers l'application paiements)"""
    messages.info(request, '⚠️ Les paiements sont gérés dans l\'application Paiements.')
    return redirect('paiements:televerser_recu')


@login_required
def liste_paiements(request):
    """Liste des paiements (redirige vers l'application paiements)"""
    return redirect('paiements:liste_recus')


@login_required
def valider_paiement(request, pk):
    """Valider un paiement (redirige vers l'application paiements)"""
    messages.info(request, '⚠️ La validation des paiements se fait dans l\'application Paiements.')
    return redirect('paiements:liste_recus')


@login_required
def recu_paiement(request, pk):
    """Afficher le reçu de paiement (redirige vers l'application paiements)"""
    return redirect('paiements:detail_recu', pk=pk)


# ==================== BOURSES ====================

@login_required
def liste_bourses(request):
    """Liste des bourses d'études"""
    bourses = Bourse.objects.all().select_related('etudiant', 'annee_academique', 'etudiant__filiere')
    
    # Filtres
    q = request.GET.get('q', '')
    if q:
        bourses = bourses.filter(
            Q(etudiant__nom__icontains=q) | 
            Q(etudiant__prenom__icontains=q) | 
            Q(etudiant__matricule__icontains=q)
        )
        
    type_bourse = request.GET.get('type_bourse', '')
    if type_bourse:
        bourses = bourses.filter(type_bourse=type_bourse)
        
    filiere = request.GET.get('filiere', '')
    if filiere:
        bourses = bourses.filter(etudiant__filiere_id=filiere)
        
    paginator = Paginator(bourses, 15)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    filieres = Filiere.objects.filter(est_active=True)
    types_bourse = Bourse.TYPE_BOURSE_CHOICES
    
    context = {
        'bourses': page_obj,
        'filieres': filieres,
        'types_bourse': types_bourse,
        'titre': 'Gestion des Bourses d\'Études'
    }
    return render(request, 'inscriptions/bourses/liste.html', context)


@login_required
def attribuer_bourse(request):
    """Attribuer une bourse à un étudiant"""
    if request.method == 'POST':
        form = BourseForm(request.POST)
        if form.is_valid():
            bourse = form.save()
            # Création d'une notification pour l'étudiant
            from apps.tableau_bord.models import Notification
            Notification.objects.create(
                utilisateur=bourse.etudiant.utilisateur,
                type='INFO',
                titre='Bourse d\'études attribuée',
                message=f'Une bourse d\'études de type {bourse.get_type_bourse_display()} d\'un montant de {bourse.montant:,.0f} FCFA vous a été attribuée.',
                lien='/inscriptions/'
            )
            messages.success(request, f'✅ Bourse d\'études attribuée avec succès à {bourse.etudiant.get_nom_complet()}.')
            return redirect('inscriptions:liste_bourses')
    else:
        form = BourseForm()
        
    context = {
        'form': form,
        'titre': 'Attribuer une bourse d\'études',
        'page': 'ajout'
    }
    return render(request, 'inscriptions/bourses/form.html', context)


@login_required
def modifier_bourse(request, pk):
    """Modifier une bourse d'études existante"""
    bourse = get_object_or_404(Bourse, pk=pk)
    if request.method == 'POST':
        form = BourseForm(request.POST, instance=bourse)
        if form.is_valid():
            form.save()
            messages.success(request, f'✏️ La bourse de {bourse.etudiant.get_nom_complet()} a été modifiée.')
            return redirect('inscriptions:liste_bourses')
    else:
        form = BourseForm(instance=bourse)
        
    context = {
        'form': form,
        'bourse': bourse,
        'titre': 'Modifier la bourse d\'études',
        'page': 'modification'
    }
    return render(request, 'inscriptions/bourses/form.html', context)


@login_required
def supprimer_bourse(request, pk):
    """Supprimer une bourse d'études"""
    bourse = get_object_or_404(Bourse, pk=pk)
    if request.method == 'POST':
        nom_etudiant = bourse.etudiant.get_nom_complet()
        bourse.delete()
        messages.success(request, f'🗑️ Bourse d\'études de {nom_etudiant} supprimée avec succès.')
        return redirect('inscriptions:liste_bourses')
        
    context = {
        'bourse': bourse,
        'titre': 'Confirmer la suppression de la bourse'
    }
    return render(request, 'inscriptions/bourses/confirmer_suppression.html', context)


# ==================== CERTIFICATS ====================

@login_required
def certificat_scolarite(request, etudiant_id):
    """Générer un certificat de scolarité"""
    etudiant = get_object_or_404(Etudiant, pk=etudiant_id)
    
    context = {
        'etudiant': etudiant,
        'titre': f'Certificat de scolarité - {etudiant.get_nom_complet()}',
        'date_aujourdhui': timezone.now(),
        'annee_academique': AnneeAcademique.get_active()
    }
    return render(request, 'inscriptions/certificat_scolarite.html', context)


# ==================== STATISTIQUES FINANCIÈRES ====================

@login_required
def statistiques_financieres(request):
    """Statistiques financières"""
    annee_active = AnneeAcademique.get_active()
    annee = request.GET.get('annee', annee_active.code if annee_active else '2024-2025')
    
    # Recettes par tranche
    recettes_par_tranche = []
    for i in range(1, 5):
        montant_total = RecuPaiement.objects.filter(
            tranche__numero=i,
            tranche__annee_academique=annee,
            statut='VALIDE'
        ).aggregate(Sum('montant_mentionne'))['montant_mentionne__sum'] or 0
        
        recettes_par_tranche.append({
            'tranche': i,
            'nom': ['Pré-inscription', '1ère Tranche', '2ème Tranche', '3ème Tranche'][i-1],
            'montant': montant_total
        })
    
    # Total général
    total_general = sum(r['montant'] for r in recettes_par_tranche)
    
    context = {
        'recettes_par_tranche': recettes_par_tranche,
        'total_general': total_general,
        'annee': annee,
        'annees': AnneeAcademique.objects.values_list('code', flat=True),
        'titre': 'Statistiques Financières'
    }
    return render(request, 'inscriptions/statistiques_financieres.html', context)