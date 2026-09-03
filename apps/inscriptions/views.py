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
    AnneeAcademique, Inscription, DocumentInscription, HistoriqueInscription, Bourse, CertificatScolarite
)
from .forms import (
    InscriptionForm, DocumentInscriptionForm, BourseForm
)
from .utils_qr import generer_qr_code_data_uri
from apps.authentification.decorators import role_required
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
    paginator = Paginator(queryset.order_by('etudiant__nom', 'etudiant__prenom'), 20)
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
    
    # Prévention IDOR : Cloisonnement strict pour les étudiants
    if request.user.type_utilisateur == 'ETUDIANT' and inscription.etudiant.utilisateur != request.user:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Vous n'êtes pas autorisé à consulter cette inscription.")
    
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
            
            # Notifications ciblées Chef Scolarité & Directeur
            try:
                from apps.tableau_bord.services_notification import NotificationService
                from django.urls import reverse
                link = reverse('inscriptions:detail_inscription', kwargs={'pk': inscription.pk})
                nom_etud = inscription.etudiant.get_nom_complet()
                NotificationService.notifier_chef_scolarite(
                    titre=f"Nouvelle Inscription : {nom_etud}",
                    message=f"Dossier créé pour {nom_etud} en {inscription.filiere.code}.",
                    type_notif='INFO',
                    lien=link
                )
                NotificationService.notifier_directeur(
                    titre=f"Nouvelle Inscription : {nom_etud}",
                    message=f"Nouvelle inscription enregistrée pour {nom_etud}.",
                    type_notif='INFO',
                    lien=link
                )
            except Exception:
                pass
            
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

        # Notifications ciblées
        try:
            from apps.tableau_bord.services_notification import NotificationService
            from django.urls import reverse
            link = reverse('inscriptions:detail_inscription', kwargs={'pk': inscription.pk})
            nom_etud = inscription.etudiant.get_nom_complet()
            
            # Notifier l'étudiant s'il a un compte utilisateur
            if hasattr(inscription.etudiant, 'utilisateur') and inscription.etudiant.utilisateur:
                NotificationService.notifier_utilisateur(
                    inscription.etudiant.utilisateur,
                    titre="Inscription Validée 🎉",
                    message=f"Félicitations {nom_etud}, votre inscription pour l'année académique {inscription.annee_academique} a été validée !",
                    type_notif='SUCCESS',
                    lien=link
                )
            
            NotificationService.notifier_chef_scolarite(
                titre=f"Inscription Validée : {nom_etud}",
                message=f"L'inscription de {nom_etud} a été validée par {request.user.get_full_name()}.",
                type_notif='SUCCESS',
                lien=link
            )
            NotificationService.notifier_directeur(
                titre=f"Validation Inscription : {nom_etud}",
                message=f"L'étudiant {nom_etud} ({inscription.filiere.code}) a été validé.",
                type_notif='SUCCESS',
                lien=link
            )
        except Exception:
            pass
        
        messages.success(request, f'✅ L\'inscription a été validée avec succès.')
        return redirect('inscriptions:detail_inscription', pk=pk)
    
    context = {
        'inscription': inscription,
        'titre': 'Valider l\'inscription'
    }
    return render(request, 'inscriptions/valider.html', context)


@login_required
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

        try:
            from apps.tableau_bord.services_notification import NotificationService
            if hasattr(inscription.etudiant, 'utilisateur') and inscription.etudiant.utilisateur:
                NotificationService.notifier_utilisateur(
                    inscription.etudiant.utilisateur,
                    titre="Inscription Non Validée ⚠️",
                    message=f"Votre dossier d'inscription nécessite une correction. Motif : {motif}",
                    type_notif='WARNING'
                )
        except Exception:
            pass
        
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
def valider_recu_preinscription(request, pk):
    """Valider le reçu de pré-inscription"""
    inscription = get_object_or_404(Inscription, pk=pk)
    inscription.valider_recu_preinscription(request.user)
    messages.success(request, '✅ Reçu de pré-inscription validé avec succès !')
    return redirect('inscriptions:detail_inscription', pk=pk)


@login_required
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
    bourses = Bourse.objects.all().select_related('etudiant', 'annee_academique', 'etudiant__filiere').order_by('etudiant__nom', 'etudiant__prenom')
    
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


# ==================== CERTIFICATS DE SCOLARITÉ ====================

@login_required
def liste_certificats(request):
    """
    Vue d'administration des certificats de scolarité :
    - Réservé exclusivement au Chef de la Scolarité / Admin Système.
    - L'étudiant ne dispose plus d'accès à ce registre.
    """
    is_chef_scolarite = (
        request.user.is_superuser or 
        request.user.type_utilisateur in ['CHEF_SCOLARITE', 'ADMIN_SYSTEME']
    )
    
    if not is_chef_scolarite:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Accès réservé au Chef de la Scolarité. Les étudiants n'ont pas accès au registre des certificats.")

    query = request.GET.get('q', '')
    statut_filter = request.GET.get('statut', '')
    filiere_filter = request.GET.get('filiere', '')
    
    certificats = CertificatScolarite.objects.select_related('etudiant', 'etudiant__filiere', 'annee_academique', 'emetteur').all()
    
    # Statistiques globales du registre
    total_certificats = certificats.count()
    total_valides = certificats.filter(statut='VALIDE').count()
    total_derogations = certificats.filter(derogation_accordee=True).count()
    total_impressions = certificats.aggregate(Sum('telechargements_count'))['telechargements_count__sum'] or 0

    if query:
        certificats = certificats.filter(
            Q(numero_reference__icontains=query) |
            Q(etudiant__user__first_name__icontains=query) |
            Q(etudiant__user__last_name__icontains=query) |
            Q(etudiant__nom__icontains=query) |
            Q(etudiant__prenom__icontains=query) |
            Q(etudiant__matricule__icontains=query)
        )
    if statut_filter:
        certificats = certificats.filter(statut=statut_filter)
    if filiere_filter:
        certificats = certificats.filter(etudiant__filiere_id=filiere_filter)
        
    paginator = Paginator(certificats.order_by('-date_delivrance'), 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'certificats': page_obj,
        'query': query,
        'statut_filter': statut_filter,
        'filiere_filter': filiere_filter,
        'filieres': Filiere.objects.filter(est_active=True),
        'total_certificats': total_certificats,
        'total_valides': total_valides,
        'total_derogations': total_derogations,
        'total_impressions': total_impressions,
        'is_chef_scolarite': True,
        'titre': 'Registre Officiel des Certificats de Scolarité',
        'annee_active': AnneeAcademique.get_active(),
    }
    return render(request, 'inscriptions/liste_certificats.html', context)



@login_required
def delivrer_certificat_scolarite(request, etudiant_id=None):
    """
    Formulaire et vue d'émission officielle d'un ou plusieurs certificats de scolarité.
    - Filtre automatiquement la liste déroulante sur les étudiants ÉLIGIBLES (frais réglés + compte validé).
    - Permet l'émission individuelle ou l'émission en masse (sélection multiple d'étudiants).
    """
    is_chef_scolarite = (
        request.user.is_superuser or 
        request.user.type_utilisateur in ['CHEF_SCOLARITE', 'ADMIN_SYSTEME']
    )
    if not is_chef_scolarite:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Seul le Chef de la Scolarité est habilité à délivrer un certificat de scolarité.")

    from decimal import Decimal
    from django.db.models import Sum
    seuil_minimal = Decimal('84000')

    # Calcul des paiements de tous les étudiants pour déterminer l'éligibilité
    etudiants_tous = Etudiant.objects.select_related('filiere', 'utilisateur').all().order_by('nom', 'prenom')
    paiements_dict = dict(
        RecuPaiement.objects.filter(statut='VALIDE')
        .values('etudiant_id')
        .annotate(total=Sum('montant_mentionne'))
        .values_list('etudiant_id', 'total')
    )

    etudiants_eligibles = []
    etudiants_non_eligibles = []

    for etu in etudiants_tous:
        total = paiements_dict.get(etu.id, Decimal('0.00')) or Decimal('0.00')
        statut_ok = (etu.utilisateur and etu.utilisateur.statut_inscription in ['COMPTE_ACTIF', 'DOCUMENT_VALIDE']) if etu.utilisateur else True
        etu.total_paye = total
        if total >= seuil_minimal and statut_ok:
            etudiants_eligibles.append(etu)
        else:
            etudiants_non_eligibles.append(etu)

    # Option de filtre d'affichage (par défaut : éligibles uniquement)
    afficher_tous = request.GET.get('tous') == '1'
    etudiants_liste = etudiants_tous if afficher_tous else etudiants_eligibles

    # TRAITEMENT DE L'ÉMISSION EN MASSE (Formulaire POST avec plusieurs IDs)
    if request.method == 'POST' and request.POST.get('action') == 'emission_masse':
        selected_ids = request.POST.getlist('etudiant_ids')
        motif = request.POST.get('motif', 'Usage administratif').strip()
        force_derogation = request.POST.get('force_derogation') == 'on'
        motif_derogation = request.POST.get('motif_derogation', '').strip()

        if not selected_ids:
            messages.error(request, "Veuillez cocher au moins un étudiant dans la liste pour l'émission en masse.")
        else:
            annee_active = AnneeAcademique.get_active() or AnneeAcademique.objects.first()
            created_tokens = []
            
            for eid in selected_ids:
                try:
                    etu = Etudiant.objects.get(pk=eid)
                    tot = paiements_dict.get(etu.id, Decimal('0.00')) or Decimal('0.00')
                    ok_fin = tot >= seuil_minimal
                    
                    if ok_fin or force_derogation:
                        certif = CertificatScolarite.objects.create(
                            etudiant=etu,
                            annee_academique=annee_active,
                            emetteur=request.user,
                            motif=motif,
                            statut='VALIDE',
                            derogation_accordee=(not ok_fin and force_derogation),
                            motif_derogation=motif_derogation if (not ok_fin and force_derogation) else '',
                            date_delivrance=timezone.now()
                        )
                        created_tokens.append(str(certif.token_verification))
                except Etudiant.DoesNotExist:
                    continue
            
            if created_tokens:
                messages.success(request, f"Génération réussie de {len(created_tokens)} certificat(s) de scolarité.")
                tokens_str = ",".join(created_tokens)
                return redirect(f"{reverse('inscriptions:imprimer_certificats_masse')}?tokens={tokens_str}")
            else:
                messages.warning(request, "Aucun certificat n'a pu être généré (vérifiez l'éligibilité financière).")

    # TRAITEMENT ÉMISSION INDIVIDUELLE
    if not etudiant_id and request.method == 'GET' and request.GET.get('etudiant_id'):
        etudiant_id = request.GET.get('etudiant_id')
    if not etudiant_id and request.method == 'POST' and request.POST.get('etudiant_id'):
        etudiant_id = request.POST.get('etudiant_id')

    etudiant = get_object_or_404(Etudiant, pk=etudiant_id) if etudiant_id else None
    annee_active = AnneeAcademique.get_active() or AnneeAcademique.objects.first()

    statut_valide = True
    total_paye = Decimal('0.00')
    est_a_jour_financierement = False

    if etudiant:
        user = etudiant.utilisateur
        statut_valide = (user.statut_inscription in ['COMPTE_ACTIF', 'DOCUMENT_VALIDE']) if user else True
        total_paye = paiements_dict.get(etudiant.id, Decimal('0.00')) or Decimal('0.00')
        est_a_jour_financierement = total_paye >= seuil_minimal

    if request.method == 'POST' and etudiant and request.POST.get('action') != 'emission_masse':
        motif = request.POST.get('motif', 'Usage administratif').strip()
        force_derogation = request.POST.get('force_derogation') == 'on'
        motif_derogation = request.POST.get('motif_derogation', '').strip()

        if not est_a_jour_financierement and not force_derogation:
            messages.error(
                request,
                f"Éligibilité financière non atteinte (Payé : {total_paye:,.0f} FCFA / Exigé : {seuil_minimal:,.0f} FCFA). "
                "Cochez l'option dérogation administrative avec un motif valide pour outrepasser."
            )
        else:
            certificat = CertificatScolarite.objects.create(
                etudiant=etudiant,
                annee_academique=annee_active,
                emetteur=request.user,
                motif=motif,
                statut='VALIDE',
                derogation_accordee=force_derogation,
                motif_derogation=motif_derogation if force_derogation else '',
                date_delivrance=timezone.now()
            )
            messages.success(request, f"Certificat de scolarité N° {certificat.numero_reference} émis avec succès.")
            return redirect('inscriptions:apercu_certificat_scolarite', token=certificat.token_verification)

    context = {
        'etudiant': etudiant,
        'etudiants_liste': etudiants_liste,
        'etudiants_eligibles': etudiants_eligibles,
        'etudiants_non_eligibles': etudiants_non_eligibles,
        'afficher_tous': afficher_tous,
        'annee_active': annee_active,
        'statut_valide': statut_valide,
        'total_paye': total_paye,
        'seuil_minimal': seuil_minimal,
        'est_a_jour_financierement': est_a_jour_financierement,
        'titre': f'Émettre Certificat - {etudiant.get_nom_complet()}' if etudiant else 'Émettre des Certificats de Scolarité'
    }
    return render(request, 'inscriptions/delivrer_certificat.html', context)


@login_required
def imprimer_certificats_masse(request):
    """
    Rendu d'impression groupée pour plusieurs certificats de scolarité.
    Reçoit un paramètre GET 'tokens' séparés par des virgules.
    Chaque certificat est rendu sous forme de page A4 autonome.
    """
    is_chef_scolarite = (
        request.user.is_superuser or 
        request.user.type_utilisateur in ['CHEF_SCOLARITE', 'ADMIN_SYSTEME']
    )
    if not is_chef_scolarite:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Seul le Chef de la Scolarité est habilité à imprimer les certificats de scolarité en masse.")

    tokens_raw = request.GET.get('tokens', '')
    tokens_list = [t.strip() for t in tokens_raw.split(',') if t.strip()]

    certificats = CertificatScolarite.objects.select_related(
        'etudiant', 'etudiant__filiere', 'annee_academique'
    ).filter(token_verification__in=tokens_list)

    certificats_data = []
    for certif in certificats:
        url_verification = request.build_absolute_uri(
            reverse('inscriptions:verifier_certificat_public', kwargs={'token': certif.token_verification})
        )
        qr_code_base64 = generer_qr_code_data_uri(url_verification)
        certificats_data.append({
            'certificat': certif,
            'etudiant': certif.etudiant,
            'annee_academique': certif.annee_academique,
            'qr_code_base64': qr_code_base64,
        })

    context = {
        'certificats_data': certificats_data,
        'titre': f'Impression de {len(certificats_data)} Certificats',
        'date_aujourdhui': timezone.now(),
    }
    return render(request, 'inscriptions/certificats_impression_masse.html', context)




@login_required
def apercu_certificat_scolarite(request, token):
    """
    Rendu officiel et imprimable du certificat de scolarité.
    Accessible au Chef Scolarité / Admin Système uniquement.
    """
    certificat = get_object_or_404(CertificatScolarite, token_verification=token)
    etudiant = certificat.etudiant

    # Vérification d'accès : Réservé exclusivement au Chef de la Scolarité
    is_chef_scolarite = (
        request.user.is_superuser or 
        request.user.type_utilisateur in ['CHEF_SCOLARITE', 'ADMIN_SYSTEME']
    )

    if not is_chef_scolarite:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Accès refusé. Seul le Chef de la Scolarité est habilité à consulter et imprimer ce certificat.")

    if not is_chef_scolarite and certificat.statut != 'VALIDE':
        messages.error(request, "Ce certificat de scolarité est annulé ou expiré.")
        return redirect('tableau_bord:tableau_bord')

    # Incrémenter le compteur de consultation
    certificat.telechargements_count += 1
    certificat.save(update_fields=['telechargements_count'])

    # URL publique absolue pour le QR Code
    url_verification = request.build_absolute_uri(
        reverse('inscriptions:verifier_certificat_public', kwargs={'token': certificat.token_verification})
    )
    qr_code_base64 = generer_qr_code_data_uri(url_verification)

    context = {
        'certificat': certificat,
        'etudiant': etudiant,
        'annee_academique': certificat.annee_academique,
        'qr_code_base64': qr_code_base64,
        'url_verification': url_verification,
        'titre': f'Certificat de scolarité - {etudiant.get_nom_complet()}',
        'date_aujourdhui': certificat.date_delivrance,
    }
    return render(request, 'inscriptions/certificat_scolarite.html', context)


@login_required
@role_required('CHEF_SCOLARITE', 'ADMIN_SYSTEME')
def annuler_certificat_scolarite(request, token):
    """Révocation/Annulation administrative d'un certificat"""
    certificat = get_object_or_404(CertificatScolarite, token_verification=token)
    
    if request.method == 'POST':
        certificat.statut = 'ANNULE'
        certificat.save(update_fields=['statut'])
        messages.warning(request, f"Le certificat N° {certificat.numero_reference} a été marqué comme ANNULÉ.")
        return redirect('inscriptions:liste_certificats')

    context = {
        'certificat': certificat,
        'titre': 'Confirmer la révocation du certificat'
    }
    return render(request, 'inscriptions/confirmer_annulation_certificat.html', context)


def verifier_certificat_public(request, token):
    """
    Portail public universel de vérification d'authenticité par QR Code (sans authentification)
    """
    try:
        certificat = CertificatScolarite.objects.select_related(
            'etudiant', 'etudiant__filiere', 'annee_academique', 'emetteur'
        ).get(token_verification=token)
        trouve = True
    except CertificatScolarite.DoesNotExist:
        certificat = None
        trouve = False

    context = {
        'trouve': trouve,
        'certificat': certificat,
        'token': str(token),
        'titre': 'Vérification d\'authenticité - IAI-Cameroun'
    }
    return render(request, 'inscriptions/verifier_certificat.html', context)



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


# ==================== FICHE DE RENSEIGNEMENT ====================

@login_required
def fiche_renseignement_etudiant(request):
    """
    Remplissage ou modification de la Fiche de Renseignement par l'étudiant
    avec contrôle IA de la photo et vérification du reçu bancaire.
    """
    from apps.etudiants.models import Etudiant
    from apps.etudiants.ai_services import verifier_photo_identite
    from apps.paiements.models import RecuPaiement, TranchePaiement
    from .forms import FicheRenseignementEtudiantForm
    from .models import FicheRenseignement, AnneeAcademique, Inscription

    user = request.user
    etudiant = getattr(user, 'profil_etudiant', None)

    # Si l'utilisateur n'a pas encore de profil étudiant lié, le trouver par email ou en créer un
    if not etudiant and user.email:
        etudiant = Etudiant.objects.filter(email=user.email).first()
        if etudiant:
            etudiant.utilisateur = user
            etudiant.save(update_fields=['utilisateur'])

    if not etudiant:
        messages.error(request, "⚠️ Aucun profil étudiant associé à votre compte. Veuillez contacter l'administration.")
        return redirect('tableau_bord:index')

    from apps.inscriptions.utils import get_current_academic_year_code, rechercher_date_concours_etudiant
    
    # Auto-détection de la filière et de la date de concours pour les étudiants Niveau 1 admis
    date_concours_auto, resultat_match = rechercher_date_concours_etudiant(etudiant)
    if resultat_match:
        fields_to_update = []
        if date_concours_auto and etudiant.date_concours != date_concours_auto:
            etudiant.date_concours = date_concours_auto
            fields_to_update.append('date_concours')
        if resultat_match.filiere and etudiant.filiere != resultat_match.filiere:
            etudiant.filiere = resultat_match.filiere
            fields_to_update.append('filiere')
        if fields_to_update:
            etudiant.save(update_fields=fields_to_update)

    annee_active = AnneeAcademique.get_active() or AnneeAcademique.objects.first()
    fiche_existante = FicheRenseignement.objects.filter(etudiant=etudiant).order_by('-date_soumission').first()

    if request.method == 'POST':
        form = FicheRenseignementEtudiantForm(request.POST, request.FILES)
        if form.is_valid():
            photo_file = request.FILES.get('photo_identite')
            recu_file = request.FILES.get('recu_paiement_fichier')

            # 1. Vérification de la photo par l'Agent IA
            photo_valide, msg_photo, details_photo = verifier_photo_identite(photo_file)
            if not photo_valide:
                messages.error(request, f"❌ Erreur Photo d'Identité (Agent IA) : {msg_photo}")
                tranches_err = []
                for num in [3, 4]:
                    t_err = TranchePaiement.objects.filter(numero=num, est_actif=True).first()
                    if t_err and t_err not in tranches_err:
                        tranches_err.append(t_err)
                return render(request, 'inscriptions/fiche_renseignement_form.html', {
                    'form': form,
                    'etudiant': etudiant,
                    'fiche': fiche_existante,
                    'tranches': tranches_err,
                    'date_concours_auto': date_concours_auto or etudiant.date_concours,
                    'filiere_auto': resultat_match.filiere if resultat_match else None,
                    'session_concours_match': resultat_match.session_concours if resultat_match else None,
                    'titre': 'Fiche de Renseignement'
                })

            # 2. Mise à jour des informations de l'étudiant
            etudiant.nom = form.cleaned_data['nom'].upper()
            etudiant.prenom = form.cleaned_data['prenom']
            etudiant.date_naissance = form.cleaned_data['date_naissance']
            etudiant.lieu_naissance = form.cleaned_data['lieu_naissance']
            etudiant.pays_naissance = form.cleaned_data['pays_naissance']
            etudiant.situation_matrimoniale = form.cleaned_data['situation_matrimoniale']
            etudiant.nationalite = form.cleaned_data['nationalite']
            etudiant.region_origine = form.cleaned_data['region_origine']
            etudiant.adresse = form.cleaned_data['adresse_permanente']
            etudiant.telephone = form.cleaned_data['telephone']
            etudiant.lieu_residence = form.cleaned_data['lieu_residence']
            etudiant.email = form.cleaned_data['email']

            etudiant.personne_contact_nom_prenom = form.cleaned_data['personne_contact_nom_prenom']
            etudiant.personne_contact_telephone = form.cleaned_data['personne_contact_telephone']
            etudiant.personne_contact_residence = form.cleaned_data['personne_contact_residence']

            # VERROUILLAGE SÉCURISÉ : Si admis au concours, la filière et la date ne sont pas modifiables par l'étudiant
            if resultat_match and resultat_match.filiere:
                etudiant.filiere = resultat_match.filiere
            else:
                etudiant.filiere = form.cleaned_data['filiere']

            etudiant.serie_bacc = form.cleaned_data['serie_bacc']

            if form.cleaned_data.get('date_premiere_rentree'):
                etudiant.date_premiere_rentree = form.cleaned_data['date_premiere_rentree']
            etudiant.statut_etudiant_fiche = form.cleaned_data['statut_etudiant_fiche']
            
            if date_concours_auto:
                etudiant.date_concours = date_concours_auto
            elif form.cleaned_data.get('date_concours'):
                etudiant.date_concours = form.cleaned_data['date_concours']

            if form.cleaned_data.get('matricule'):
                etudiant.matricule = form.cleaned_data['matricule']

            if photo_file:
                etudiant.photo = photo_file

            etudiant.save()

            # 3. Création du reçu de paiement et analyse OCR IA
            tranche_1 = TranchePaiement.objects.filter(numero=1).first()
            recu = RecuPaiement.objects.create(
                etudiant=etudiant,
                tranche=tranche_1,
                recu_fichier=recu_file,
                statut='EN_ATTENTE'
            )
            # Exécuter l'analyse IA du reçu
            recu.analyser_par_ia()
            recu.save()

            # Vérification si le reçu est authentique et validé par l'IA (score >= 90%)
            recu_valide_ia = recu.statut == 'VALIDE' or (recu.score_confiance and recu.score_confiance >= 0.90)

            # 4. Inscription associée
            inscription, _ = Inscription.objects.get_or_create(
                etudiant=etudiant,
                annee_academique=annee_active,
                defaults={
                    'filiere': etudiant.filiere,
                    'type_inscription': 'NOUVELLE',
                    'statut': 'VALIDEE' if recu_valide_ia else 'EN_ATTENTE'
                }
            )
            if recu_valide_ia:
                inscription.statut = 'VALIDEE'
                inscription.save()
                etudiant.statut = 'INSCRIT'
                etudiant.save(update_fields=['statut'])

            # 5. Création/Mise à jour de la FicheRenseignement
            statut_fiche = 'VALIDE' if recu_valide_ia else 'EN_ATTENTE_VERIFICATION'
            msg_ia = "✅ Photo d'identité conforme. Reçu bancaire authentifié et validé automatiquement par l'IA !" if recu_valide_ia else "✅ Photo d'identité conforme. Reçu bancaire transmis au Chef de la Comptabilité pour vérification finale."

            fiche = FicheRenseignement.objects.create(
                etudiant=etudiant,
                annee_academique=annee_active,
                inscription=inscription,
                recu_paiement=recu,
                photo_validee_ia=True,
                recu_valide_ia=recu_valide_ia,
                statut_validation=statut_fiche,
                details_ia_photo=details_photo,
                details_ia_recu=recu.verification_ia or {},
                message_ia=msg_ia
            )

            if recu_valide_ia:
                messages.success(request, f"🎉 Fiche enregistrée avec succès ! {msg_ia}")
            else:
                messages.warning(request, f"📋 Fiche enregistrée avec succès. {msg_ia}")

            return redirect('inscriptions:detail_fiche_renseignement', pk=fiche.pk)

    else:
        # Données initiales
        initial_data = {
            'nom': etudiant.nom,
            'prenom': etudiant.prenom,
            'date_naissance': etudiant.date_naissance,
            'lieu_naissance': etudiant.lieu_naissance,
            'pays_naissance': etudiant.pays_naissance or 'Cameroun',
            'situation_matrimoniale': etudiant.situation_matrimoniale or 'Célibataire',
            'nationalite': etudiant.nationalite or 'CMR',
            'region_origine': etudiant.region_origine,
            'adresse_permanente': etudiant.adresse,
            'telephone': etudiant.telephone,
            'lieu_residence': etudiant.lieu_residence,
            'email': etudiant.email,
            'personne_contact_nom_prenom': etudiant.personne_contact_nom_prenom or etudiant.nom_tuteur,
            'personne_contact_telephone': etudiant.personne_contact_telephone or etudiant.telephone_tuteur,
            'personne_contact_residence': etudiant.personne_contact_residence,
            'filiere': etudiant.filiere,
            'serie_bacc': etudiant.serie_bacc,
            'niveau': etudiant.niveau.numero if etudiant.niveau else '1',
            'date_premiere_rentree': etudiant.date_premiere_rentree,
            'statut_etudiant_fiche': etudiant.statut_etudiant_fiche or 'Nouvelle admission',
            'date_concours': etudiant.date_concours or date_concours_auto,
            'matricule': etudiant.matricule,
        }
        form = FicheRenseignementEtudiantForm(initial=initial_data)

    annee_code = etudiant.annee_academique.code if etudiant and etudiant.annee_academique else (annee_active.code if annee_active else get_current_academic_year_code())

    tranches = []
    for num in [3, 4]:
        t = TranchePaiement.objects.filter(annee_academique=annee_code, numero=num, est_actif=True).first()
        if not t:
            t = TranchePaiement.objects.filter(numero=num, est_actif=True).first()
        if t and t not in tranches:
            tranches.append(t)

    context = {
        'form': form,
        'etudiant': etudiant,
        'fiche': fiche_existante,
        'tranches': tranches,
        'date_concours_auto': date_concours_auto or etudiant.date_concours,
        'filiere_auto': resultat_match.filiere if resultat_match else None,
        'session_concours_match': resultat_match.session_concours if resultat_match else None,
        'titre': 'Fiche de Renseignement'
    }
    return render(request, 'inscriptions/fiche_renseignement_form.html', context)


@login_required
def detail_fiche_renseignement(request, pk):
    """
    Affichage de la Fiche de Renseignement d'un étudiant.
    Textuellement et visuellement identique à la version papier imprimée.
    """
    from .models import FicheRenseignement
    fiche = get_object_or_404(FicheRenseignement.objects.select_related('etudiant', 'annee_academique', 'inscription', 'recu_paiement'), pk=pk)
    etudiant = fiche.etudiant

    context = {
        'fiche': fiche,
        'etudiant': etudiant,
        'titre': f'Fiche de Renseignement - {etudiant.get_nom_complet()}'
    }
    return render(request, 'inscriptions/detail_fiche_renseignement.html', context)


@login_required
def telecharger_fiche_pdf(request, pk):
    """Générer et télécharger la Fiche de Renseignement officielle en PDF"""
    from .models import FicheRenseignement
    from .pdf_services import generer_fiche_renseignement_pdf

    fiche = get_object_or_404(FicheRenseignement.objects.select_related('etudiant', 'annee_academique'), pk=pk)
    etudiant = fiche.etudiant

    base_url = request.build_absolute_uri('/')[:-1]
    pdf_bytes = generer_fiche_renseignement_pdf(etudiant, fiche=fiche, domain_url=base_url)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f"Fiche_Renseignement_{etudiant.matricule or etudiant.id}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response