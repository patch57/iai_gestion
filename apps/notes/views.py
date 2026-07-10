"""
Vues pour la gestion des notes
IAI-Cameroun - Centre de Douala
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db.models import Q, Avg, Count, Sum, Min, Max, StdDev
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, timedelta
import csv
import json
import math

from .models import (
    TypeEvaluation, Evaluation, Note, Bulletin, DetailBulletin, 
    Deliberation, RecoursNote, NoteAnonyme, SessionAnonymat,
    CampusLocation, PointInteret
)
from .forms import (
    TypeEvaluationForm, EvaluationForm, NoteForm, SaisieNotesForm,
    RecoursNoteForm
)
from apps.etudiants.models import Etudiant, Filiere, AnneeAcademique
from apps.cours.models import Cours


def get_annee_academique_active(request):
    """Récupère l'année académique active"""
    annee_active = AnneeAcademique.objects.filter(est_active=True).first()
    return request.GET.get('annee', annee_active.code if annee_active else '2024-2025')


@login_required
def liste_evaluations(request):
    """Liste des évaluations"""
    queryset = Evaluation.objects.all().select_related('cours__matiere', 'type_evaluation')
    
    # Filtres
    cours_id = request.GET.get('cours', '')
    if cours_id:
        queryset = queryset.filter(cours_id=cours_id)
    
    type_eval = request.GET.get('type', '')
    if type_eval:
        queryset = queryset.filter(type_evaluation_id=type_eval)
    
    statut = request.GET.get('statut', '')
    if statut:
        queryset = queryset.filter(statut=statut)
    
    annee = get_annee_academique_active(request)
    queryset = queryset.filter(cours__annee_academique=annee)
    
    # Pagination
    paginator = Paginator(queryset.order_by('-date_evaluation'), 20)
    page = request.GET.get('page')
    evaluations = paginator.get_page(page)
    
    context = {
        'evaluations': evaluations,
        'types_eval': TypeEvaluation.objects.filter(est_actif=True),
        'annee': annee,
        'statut_choices': Evaluation.STATUT_CHOICES,
        'titre': 'Liste des Évaluations'
    }
    return render(request, 'notes/liste_evaluations.html', context)


@login_required
def detail_evaluation(request, pk):
    """Détail d'une évaluation"""
    evaluation = get_object_or_404(Evaluation, pk=pk)
    
    # Notes
    notes = Note.objects.filter(evaluation=evaluation, est_validee=True).select_related('etudiant')
    notes_non_validees = Note.objects.filter(evaluation=evaluation, est_validee=False).count()
    
    # Vérifier si l'anonymat est activé
    anonymat_actif = hasattr(evaluation, 'session_anonymat') and evaluation.session_anonymat.est_active
    
    # Calcul des statistiques avancées
    stats = {
        'total': notes.count(),
        'total_non_validees': notes_non_validees,
        'moyenne': notes.aggregate(Avg('valeur'))['valeur__avg'],
        'reussites': notes.filter(valeur__gte=10).count(),
        'echecs': notes.filter(valeur__lt=10).count(),
        'min': notes.aggregate(Min('valeur'))['valeur__min'],
        'max': notes.aggregate(Max('valeur'))['valeur__max'],
    }
    
    if stats['total'] > 0:
        stats['taux_reussite'] = round((stats['reussites'] / stats['total']) * 100, 1)
        # Calcul de l'écart type
        variance = notes.aggregate(variance=Avg((F('valeur') - stats['moyenne']) ** 2))['variance']
        stats['ecart_type'] = round(math.sqrt(variance), 2) if variance else 0
    
    # Répartition des notes par tranche
    repartition = evaluation.get_repartition_notes()
    
    # Série statistique pour le graphique
    serie_notes = list(notes.values_list('valeur', flat=True))
    
    context = {
        'evaluation': evaluation,
        'notes': notes,
        'stats': stats,
        'repartition': repartition,
        'serie_notes': json.dumps(serie_notes),
        'anonymat_actif': anonymat_actif,
        'titre': str(evaluation)
    }
    return render(request, 'notes/detail_evaluation.html', context)


@login_required
@permission_required('notes.add_evaluation', raise_exception=True)
def ajouter_evaluation(request):
    """Ajouter une évaluation"""
    if request.method == 'POST':
        form = EvaluationForm(request.POST)
        if form.is_valid():
            evaluation = form.save(commit=False)
            evaluation.cree_par = request.user
            evaluation.save()
            messages.success(request, f'✅ L\'évaluation "{evaluation}" a été créée avec succès.')
            return redirect('notes:detail_evaluation', pk=evaluation.pk)
    else:
        form = EvaluationForm()
    
    context = {
        'form': form,
        'titre': 'Nouvelle Évaluation'
    }
    return render(request, 'notes/evaluation_form.html', context)


@login_required
@permission_required('notes.change_evaluation', raise_exception=True)
def modifier_evaluation(request, pk):
    """Modifier une évaluation"""
    evaluation = get_object_or_404(Evaluation, pk=pk)
    
    if request.method == 'POST':
        form = EvaluationForm(request.POST, instance=evaluation)
        if form.is_valid():
            form.save()
            messages.success(request, '✅ Évaluation modifiée avec succès.')
            return redirect('notes:detail_evaluation', pk=evaluation.pk)
    else:
        form = EvaluationForm(instance=evaluation)
    
    context = {
        'form': form,
        'evaluation': evaluation,
        'titre': f'Modifier {evaluation}'
    }
    return render(request, 'notes/evaluation_form.html', context)


@login_required
@permission_required('notes.delete_evaluation', raise_exception=True)
def supprimer_evaluation(request, pk):
    """Supprimer une évaluation"""
    evaluation = get_object_or_404(Evaluation, pk=pk)
    
    if request.method == 'POST':
        evaluation.delete()
        messages.success(request, '🗑️ Évaluation supprimée avec succès.')
        return redirect('notes:liste_evaluations')
    
    context = {
        'evaluation': evaluation,
        'titre': 'Supprimer l\'évaluation'
    }
    return render(request, 'notes/supprimer_evaluation.html', context)


@login_required
@permission_required('notes.add_note', raise_exception=True)
def saisie_notes(request, evaluation_id):
    """Saisie des notes pour une évaluation"""
    evaluation = get_object_or_404(Evaluation, pk=evaluation_id)
    
    # Vérifier si l'anonymat est activé
    if hasattr(evaluation, 'session_anonymat') and evaluation.session_anonymat.est_active:
        return redirect('notes:saisie_notes_anonymes', evaluation_id=evaluation.id)
    
    # Vérifier si l'évaluation est terminée
    if evaluation.statut == 'TERMINEE':
        messages.warning(request, "⚠️ Cette évaluation est déjà terminée. Vous ne pouvez plus modifier les notes.")
        return redirect('notes:detail_evaluation', pk=evaluation_id)
    
    # Étudiants inscrits au cours
    inscriptions = evaluation.cours.inscriptions_cours.filter(est_actif=True)
    
    if request.method == 'POST':
        modified_count = 0
        for inscription in inscriptions:
            valeur = request.POST.get(f'note_{inscription.etudiant_id}')
            if valeur:
                try:
                    note, created = Note.objects.update_or_create(
                        etudiant=inscription.etudiant,
                        evaluation=evaluation,
                        defaults={
                            'valeur': float(valeur),
                            'saisie_par': request.user
                        }
                    )
                    modified_count += 1
                except ValueError:
                    messages.warning(request, f'⚠️ Note invalide pour {inscription.etudiant.get_nom_complet()}')
        
        messages.success(request, f'✅ {modified_count} note(s) enregistrée(s) avec succès.')
        return redirect('notes:detail_evaluation', pk=evaluation_id)
    
    # Notes déjà saisies
    notes_existantes = {
        n.etudiant_id: n.valeur 
        for n in Note.objects.filter(evaluation=evaluation)
    }
    
    context = {
        'evaluation': evaluation,
        'inscriptions': inscriptions,
        'notes_existantes': notes_existantes,
        'titre': f'Saisie des Notes - {evaluation}'
    }
    return render(request, 'notes/saisie_notes.html', context)


@login_required
@permission_required('notes.change_note', raise_exception=True)
def valider_notes(request, evaluation_id):
    """Valider les notes d'une évaluation"""
    evaluation = get_object_or_404(Evaluation, pk=evaluation_id)
    
    if request.method == 'POST':
        notes = Note.objects.filter(evaluation=evaluation, est_validee=False)
        count = notes.count()
        
        if count == 0:
            messages.warning(request, "⚠️ Aucune note à valider.")
        else:
            notes.update(est_validee=True)
            evaluation.est_publiee = True
            evaluation.statut = 'TERMINEE'
            evaluation.save()
            messages.success(request, f'✅ {count} note(s) validée(s) et publiée(s).')
        
        return redirect('notes:detail_evaluation', pk=evaluation_id)
    
    context = {
        'evaluation': evaluation,
        'titre': 'Valider les Notes'
    }
    return render(request, 'notes/valider_notes.html', context)


# ========== ANONYMAT ==========

@login_required
@permission_required('notes.add_evaluation', raise_exception=True)
def activer_anonymat(request, evaluation_id):
    """Activer l'anonymat pour une évaluation"""
    evaluation = get_object_or_404(Evaluation, pk=evaluation_id)
    
    # Vérifier que le professeur est celui qui enseigne
    if not request.user.est_professeur() and not request.user.is_staff:
        messages.error(request, "❌ Seuls les professeurs ou administrateurs peuvent activer l'anonymat.")
        return redirect('notes:detail_evaluation', pk=evaluation_id)
    
    # Vérifier si une session existe déjà
    if hasattr(evaluation, 'session_anonymat'):
        messages.warning(request, "⚠️ L'anonymat est déjà activé pour cette évaluation.")
        return redirect('notes:detail_evaluation', pk=evaluation_id)
    
    if request.method == 'POST':
        # Créer la session d'anonymat
        session = SessionAnonymat.objects.create(
            evaluation=evaluation,
            code_session=f"ANON-{evaluation.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
            date_expiration=timezone.now() + timedelta(days=30),
            professeur=request.user
        )
        
        # Récupérer les étudiants inscrits
        inscriptions = evaluation.cours.inscriptions_cours.filter(est_actif=True)
        etudiants = [inscription.etudiant for inscription in inscriptions]
        
        # Générer les codes anonymes
        codes = session.generer_codes_anonymes(etudiants)
        
        messages.success(
            request, 
            f'✅ Anonymat activé avec succès. {len(codes)} codes anonymes générés.'
        )
        return redirect('notes:saisie_notes_anonymes', evaluation_id=evaluation.id)
    
    context = {
        'evaluation': evaluation,
        'titre': f'Activer l\'anonymat - {evaluation}'
    }
    return render(request, 'notes/activer_anonymat.html', context)


@login_required
def saisie_notes_anonymes(request, evaluation_id):
    """Saisie des notes avec codes anonymes"""
    evaluation = get_object_or_404(Evaluation, pk=evaluation_id)
    
    # Vérifier l'anonymat
    if not hasattr(evaluation, 'session_anonymat') or not evaluation.session_anonymat.est_active:
        messages.error(request, "❌ L'anonymat n'est pas activé pour cette évaluation.")
        return redirect('notes:detail_evaluation', pk=evaluation_id)
    
    session = evaluation.session_anonymat
    
    if request.method == 'POST':
        modified_count = 0
        for note_anonyme in session.evaluation.notes_anonymes.all():
            valeur = request.POST.get(f'note_{note_anonyme.id}')
            if valeur:
                try:
                    note_anonyme.valeur = float(valeur)
                    note_anonyme.saisie_par = request.user
                    note_anonyme.save()
                    modified_count += 1
                except ValueError:
                    messages.warning(request, f'⚠️ Note invalide pour le code {note_anonyme.code_anonyme}')
        
        messages.success(request, f'✅ {modified_count} note(s) anonyme(s) enregistrée(s).')
        return redirect('notes:detail_evaluation', pk=evaluation_id)
    
    context = {
        'evaluation': evaluation,
        'session': session,
        'notes_anonymes': session.evaluation.notes_anonymes.all(),
        'titre': f'Saisie des notes anonymes - {evaluation}'
    }
    return render(request, 'notes/saisie_notes_anonymes.html', context)


@login_required
def reveler_identites(request, evaluation_id):
    """Révéler les identités après correction (réservé aux admins)"""
    if not request.user.is_staff:
        messages.error(request, "❌ Seuls les administrateurs peuvent révéler les identités.")
        return redirect('notes:detail_evaluation', pk=evaluation_id)
    
    evaluation = get_object_or_404(Evaluation, pk=evaluation_id)
    
    if request.method == 'POST':
        created_count = 0
        # Créer les notes réelles à partir des notes anonymes
        for note_anonyme in evaluation.notes_anonymes.all():
            if note_anonyme.valeur and note_anonyme.etudiant_origine:
                note, created = Note.objects.update_or_create(
                    etudiant=note_anonyme.etudiant_origine,
                    evaluation=evaluation,
                    defaults={
                        'valeur': note_anonyme.valeur,
                        'saisie_par': request.user,
                        'est_validee': False
                    }
                )
                if created:
                    created_count += 1
        
        # Désactiver la session
        evaluation.session_anonymat.est_active = False
        evaluation.session_anonymat.save()
        
        messages.success(
            request, 
            f'✅ Identités révélées. {created_count} note(s) associée(s).'
        )
        return redirect('notes:detail_evaluation', pk=evaluation_id)
    
    context = {
        'evaluation': evaluation,
        'titre': f'Révéler les identités - {evaluation}'
    }
    return render(request, 'notes/reveler_identites.html', context)


# ========== BULLETINS ==========

@login_required
def liste_bulletins(request):
    """Liste des bulletins"""
    queryset = Bulletin.objects.all().select_related('etudiant', 'etudiant__filiere')
    
    # Filtres
    filiere_id = request.GET.get('filiere', '')
    if filiere_id:
        queryset = queryset.filter(etudiant__filiere_id=filiere_id)
    
    annee = get_annee_academique_active(request)
    queryset = queryset.filter(annee_academique=annee)
    
    semestre = request.GET.get('semestre', '')
    if semestre:
        queryset = queryset.filter(semestre=semestre)
    
    decision = request.GET.get('decision', '')
    if decision:
        queryset = queryset.filter(decision=decision)
    
    # Pagination
    paginator = Paginator(queryset.order_by('-annee_academique', 'semestre', '-moyenne_semestre'), 20)
    page = request.GET.get('page')
    bulletins = paginator.get_page(page)
    
    context = {
        'bulletins': bulletins,
        'filieres': Filiere.objects.filter(est_active=True),
        'annee': annee,
        'titre': 'Liste des Bulletins'
    }
    return render(request, 'notes/liste_bulletins.html', context)


@login_required
def detail_bulletin(request, pk):
    """Détail d'un bulletin"""
    bulletin = get_object_or_404(Bulletin, pk=pk)
    details = bulletin.details.all().select_related('matiere')
    
    # Calculer la progression
    total_credits = sum(d.credits for d in details)
    credits_obtenus = bulletin.credits_obtenus
    progression = round((credits_obtenus / total_credits) * 100, 1) if total_credits > 0 else 0
    
    context = {
        'bulletin': bulletin,
        'details': details,
        'progression': progression,
        'titre': f'Bulletin - {bulletin.etudiant}'
    }
    return render(request, 'notes/detail_bulletin.html', context)


@login_required
@permission_required('notes.add_bulletin', raise_exception=True)
def generer_bulletins(request):
    """Générer les bulletins pour une filière"""
    if request.method == 'POST':
        filiere_id = request.POST.get('filiere')
        annee = request.POST.get('annee_academique', get_annee_academique_active(request))
        semestre = request.POST.get('semestre', 1)
        
        filiere = get_object_or_404(Filiere, pk=filiere_id)
        etudiants = Etudiant.objects.filter(
            filiere=filiere,
            annee_academique=annee,
            statut__in=['ACTIF', 'INSCRIT']
        )
        
        count = 0
        for etudiant in etudiants:
            bulletin, created = Bulletin.objects.get_or_create(
                etudiant=etudiant,
                annee_academique=annee,
                semestre=semestre,
                defaults={'filiere': filiere}
            )
            if created:
                count += 1
        
        messages.success(request, f'✅ {count} bulletin(s) généré(s).')
        return redirect('notes:liste_bulletins')
    
    context = {
        'filieres': Filiere.objects.filter(est_active=True),
        'titre': 'Générer les Bulletins'
    }
    return render(request, 'notes/generer_bulletins.html', context)


@login_required
def deliberation(request):
    """Page de délibération"""
    filiere_id = request.GET.get('filiere', '')
    annee = get_annee_academique_active(request)
    semestre = request.GET.get('semestre', 1)
    
    bulletins = []
    filiere = None
    
    if filiere_id:
        filiere = get_object_or_404(Filiere, pk=filiere_id)
        bulletins = Bulletin.objects.filter(
            etudiant__filiere=filiere,
            annee_academique=annee,
            semestre=semestre
        ).select_related('etudiant').order_by('-moyenne_semestre')
        
        # Calculer les statistiques
        stats = {
            'total': bulletins.count(),
            'moyenne_generale': bulletins.aggregate(Avg('moyenne_semestre'))['moyenne_semestre__avg'],
            'admis': bulletins.filter(decision='ADMIS').count(),
            'ajournes': bulletins.filter(decision='AJOURNE').count(),
            'exclus': bulletins.filter(decision='EXCLU').count(),
        }
    else:
        stats = None
    
    context = {
        'filieres': Filiere.objects.filter(est_active=True),
        'filiere': filiere,
        'bulletins': bulletins,
        'stats': stats,
        'annee': annee,
        'semestre': semestre,
        'titre': 'Délibération'
    }
    return render(request, 'notes/deliberation.html', context)


@login_required
@permission_required('notes.change_bulletin', raise_exception=True)
def valider_deliberation(request):
    """Valider la délibération"""
    if request.method == 'POST':
        filiere_id = request.POST.get('filiere')
        annee = request.POST.get('annee_academique')
        semestre = request.POST.get('semestre')
        
        bulletins = Bulletin.objects.filter(
            etudiant__filiere_id=filiere_id,
            annee_academique=annee,
            semestre=semestre
        )
        
        # Mettre à jour les décisions
        for bulletin in bulletins:
            bulletin.calculer_moyenne()
            bulletin.determiner_decision()
            bulletin.est_valide = True
            bulletin.save()
        
        # Attribuer les rangs
        bulletins_valides = bulletins.filter(est_valide=True).order_by('-moyenne_semestre')
        for rang, bulletin in enumerate(bulletins_valides, 1):
            bulletin.rang = rang
            bulletin.effectif = bulletins_valides.count()
            bulletin.save()
        
        messages.success(request, '✅ La délibération a été validée avec succès.')
        return redirect('notes:deliberation')


# ========== NOTES ÉTUDIANT ==========

@login_required
def mes_notes(request):
    """Notes de l'étudiant connecté"""
    try:
        etudiant = Etudiant.objects.get(utilisateur=request.user)
    except Etudiant.DoesNotExist:
        messages.error(request, '❌ Vous n\'êtes pas un étudiant.')
        return redirect('tableau_bord:tableau_bord')
    
    notes = Note.objects.filter(
        etudiant=etudiant,
        est_validee=True
    ).select_related('evaluation__cours__matiere', 'evaluation__type_evaluation')
    
    bulletins = Bulletin.objects.filter(etudiant=etudiant).order_by('-annee_academique', 'semestre')
    
    # Calcul des statistiques
    stats = {
        'moyenne_generale': notes.aggregate(Avg('valeur'))['valeur__avg'],
        'total_credits': bulletins.aggregate(Sum('credits_obtenus'))['credits_obtenus__sum'] or 0,
        'meilleure_note': notes.aggregate(Max('valeur'))['valeur__max'],
        'matieres_validees': notes.filter(valeur__gte=10).count(),
        'total_matieres': notes.count(),
    }
    
    if stats['total_matieres'] > 0:
        stats['taux_reussite'] = round((stats['matieres_validees'] / stats['total_matieres']) * 100, 1)
    
    context = {
        'etudiant': etudiant,
        'notes': notes,
        'bulletins': bulletins,
        'stats': stats,
        'titre': 'Mes Notes'
    }
    return render(request, 'notes/mes_notes.html', context)


# ========== EXPORT ==========

@login_required
def exporter_releve(request, bulletin_id):
    """Exporter un relevé de notes en CSV"""
    bulletin = get_object_or_404(Bulletin, pk=bulletin_id)
    
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="releve_{bulletin.etudiant.matricule}_{bulletin.annee_academique}_S{bulletin.semestre}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['RELEVÉ DE NOTES'])
    writer.writerow(['IAI-Cameroun - Centre de Douala'])
    writer.writerow([])
    writer.writerow([f"Étudiant: {bulletin.etudiant.get_nom_complet()}"])
    writer.writerow([f"Matricule: {bulletin.etudiant.matricule}"])
    writer.writerow([f"Filière: {bulletin.etudiant.filiere.nom}"])
    writer.writerow([f"Année Académique: {bulletin.annee_academique}"])
    writer.writerow([f"Semestre: {bulletin.semestre}"])
    writer.writerow([])
    writer.writerow(['Matière', 'CC (30%)', 'TP (20%)', 'Examen (50%)', 'Moyenne', 'Crédits', 'Validée'])
    writer.writerow(['-' * 80])
    
    for detail in bulletin.details.all():
        writer.writerow([
            detail.matiere.nom,
            detail.note_cc or '-',
            detail.note_tp or '-',
            detail.note_examen or '-',
            f"{detail.moyenne_matiere:.2f}" if detail.moyenne_matiere else '-',
            detail.credits_obtenus,
            'Oui' if detail.est_validee else 'Non'
        ])
    
    writer.writerow([])
    writer.writerow([f"Moyenne Générale: {bulletin.moyenne_semestre:.2f}/20" if bulletin.moyenne_semestre else "Moyenne: -"])
    writer.writerow([f"Rang: {bulletin.rang}/{bulletin.effectif}" if bulletin.rang else "Rang: -"])
    writer.writerow([f"Décision: {bulletin.get_decision_display()}"])
    writer.writerow([f"Mention: {bulletin.mention}" if bulletin.mention else "Mention: -"])
    
    return response


@login_required
def exporter_notes_evaluation(request, evaluation_id):
    """Exporter les notes d'une évaluation"""
    evaluation = get_object_or_404(Evaluation, pk=evaluation_id)
    notes = Note.objects.filter(evaluation=evaluation, est_validee=True).select_related('etudiant')
    
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="notes_{evaluation.titre}_{datetime.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([f"Notes - {evaluation.titre}"])
    writer.writerow([f"Cours: {evaluation.cours.matiere.nom}"])
    writer.writerow([f"Type: {evaluation.type_evaluation.nom}"])
    writer.writerow([f"Coefficient: {evaluation.coefficient}"])
    writer.writerow([f"Date: {evaluation.date_evaluation.strftime('%d/%m/%Y')}"])
    writer.writerow([])
    writer.writerow(['Matricule', 'Nom', 'Prénom', 'Note', 'Observation'])
    writer.writerow(['-' * 80])
    
    for note in notes:
        writer.writerow([
            note.etudiant.matricule,
            note.etudiant.nom,
            note.etudiant.prenom,
            note.valeur,
            note.observation
        ])
    
    # Ajouter les statistiques
    writer.writerow([])
    writer.writerow(['STATISTIQUES'])
    writer.writerow([f"Nombre d'étudiants:", notes.count()])
    writer.writerow([f"Moyenne:", f"{notes.aggregate(Avg('valeur'))['valeur__avg']:.2f}/20"])
    writer.writerow([f"Taux de réussite:", f"{notes.filter(valeur__gte=10).count() / notes.count() * 100:.1f}%"])
    
    return response


# ========== STATISTIQUES ==========

@login_required
@permission_required('notes.view_statistiques', raise_exception=True)
def statistiques_notes(request):
    """Statistiques des notes"""
    annee = get_annee_academique_active(request)
    semestre = request.GET.get('semestre', 1)
    
    # Statistiques par filière
    stats_par_filiere = []
    for filiere in Filiere.objects.filter(est_active=True):
        bulletins = Bulletin.objects.filter(
            etudiant__filiere=filiere,
            annee_academique=annee,
            semestre=semestre,
            est_valide=True
        )
        
        if bulletins.exists():
            stats_par_filiere.append({
                'filiere': filiere,
                'effectif': bulletins.count(),
                'moyenne': round(bulletins.aggregate(Avg('moyenne_semestre'))['moyenne_semestre__avg'] or 0, 2),
                'admis': bulletins.filter(decision='ADMIS').count(),
                'ajournes': bulletins.filter(decision='AJOURNE').count(),
                'exclus': bulletins.filter(decision='EXCLU').count(),
                'taux_reussite': round(bulletins.filter(decision='ADMIS').count() / bulletins.count() * 100, 1),
                'meilleure_moyenne': round(bulletins.aggregate(Max('moyenne_semestre'))['moyenne_semestre__max'] or 0, 2),
            })
    
    context = {
        'stats_par_filiere': stats_par_filiere,
        'annee': annee,
        'semestre': semestre,
        'titre': 'Statistiques des Notes'
    }
    return render(request, 'notes/statistiques_notes.html', context)


# ========== RECOURS ==========

@login_required
def demander_recours(request, evaluation_id):
    """Formulaire de demande de recours sur une note"""
    evaluation = get_object_or_404(Evaluation, pk=evaluation_id)
    
    try:
        etudiant = Etudiant.objects.get(utilisateur=request.user)
        note = Note.objects.get(etudiant=etudiant, evaluation=evaluation)
    except (Etudiant.DoesNotExist, Note.DoesNotExist):
        messages.error(request, "❌ Vous n'avez pas de note pour cette évaluation.")
        return redirect('notes:mes_notes')
    
    # Vérifier si un recours existe déjà
    recours_existant = RecoursNote.objects.filter(
        etudiant=etudiant, 
        evaluation=evaluation,
        statut='EN_ATTENTE'
    ).first()
    
    if recours_existant:
        messages.warning(request, "⚠️ Vous avez déjà une demande de recours en cours pour cette évaluation.")
        return redirect('notes:mes_notes')
    
    if request.method == 'POST':
        form = RecoursNoteForm(request.POST)
        if form.is_valid():
            recours = form.save(commit=False)
            recours.etudiant = etudiant
            recours.evaluation = evaluation
            recours.note_actuelle = note.valeur
            recours.save()
            messages.success(request, "✅ Votre demande de recours a été enregistrée.")
            return redirect('notes:mes_notes')
    else:
        form = RecoursNoteForm(initial={'note_demandee': note.valeur})
    
    context = {
        'evaluation': evaluation,
        'note': note,
        'form': form,
        'titre': 'Demander un recours'
    }
    return render(request, 'notes/demander_recours.html', context)


# ========== GÉO-LOCALISATION ==========

@login_required
def carte_campus(request):
    """Vue pour afficher la carte du campus et des environs"""
    campus = CampusLocation.objects.first()
    
    if not campus:
        campus = CampusLocation.objects.create(
            nom='IAI-Cameroun Centre de Douala',
            adresse='PK9, Douala - Station MRS, avant boulangerie Saker',
            latitude=4.051056,
            longitude=9.767865,
            instructions="Venant du marché Ndokoti, continuer tout droit. Juste avant la boulangerie Saker, au niveau de la station MRS."
        )
    
    # Points d'intérêt à proximité
    points_interet = PointInteret.objects.all()
    
    context = {
        'campus': campus,
        'points_interet': points_interet,
        'center_lat': campus.latitude,
        'center_lng': campus.longitude,
        'titre': 'Plan d\'accès - IAI-Cameroun'
    }
    return render(request, 'notes/carte_campus.html', context)


@login_required
def itineraire(request):
    """Calcul d'itinéraire vers le campus"""
    campus = CampusLocation.objects.first()
    
    if request.method == 'POST':
        depart = request.POST.get('depart')
        
        if campus:
            context = {
                'depart': depart,
                'campus': campus,
                'distance_estimee': "environ 15 minutes",
                'moyens_transport': [
                    {'nom': 'Taxi', 'duree': '15-20 min', 'prix': '500-1000 FCFA', 'icon': 'fa-taxi'},
                    {'nom': 'Moto-taxi', 'duree': '10-15 min', 'prix': '300-500 FCFA', 'icon': 'fa-motorcycle'},
                    {'nom': 'Voiture personnelle', 'duree': '15-20 min', 'prix': 'Carburant', 'icon': 'fa-car'},
                    {'nom': 'Bus', 'duree': '25-30 min', 'prix': '200-300 FCFA', 'icon': 'fa-bus'},
                    {'nom': 'Marche', 'duree': '45-60 min', 'prix': 'Gratuit', 'icon': 'fa-walking'},
                ]
            }
            return render(request, 'notes/itineraire.html', context)
    
    context = {
        'campus': campus,
        'titre': 'Calcul d\'itinéraire'
    }
    return render(request, 'notes/itineraire.html', context)


# ========== API ==========

@login_required
def api_stats_evaluation(request, evaluation_id):
    """API pour les statistiques d'une évaluation (AJAX)"""
    evaluation = get_object_or_404(Evaluation, pk=evaluation_id)
    notes = Note.objects.filter(evaluation=evaluation, est_validee=True)
    
    if notes.exists():
        moyenne = notes.aggregate(Avg('valeur'))['valeur__avg']
        # Calcul de l'écart type
        variance = notes.aggregate(variance=Avg((F('valeur') - moyenne) ** 2))['variance']
        ecart_type = math.sqrt(variance) if variance else 0
    else:
        moyenne = 0
        ecart_type = 0
    
    data = {
        'moyenne': round(moyenne, 2) if moyenne else 0,
        'mediane': round(notes.aggregate(Avg('valeur'))['valeur__avg'], 2) or 0,
        'ecart_type': round(ecart_type, 2),
        'reussite': notes.filter(valeur__gte=10).count(),
        'echec': notes.filter(valeur__lt=10).count(),
        'total': notes.count(),
        'meilleure': notes.aggregate(Max('valeur'))['valeur__max'] or 0,
        'moins_bonne': notes.aggregate(Min('valeur'))['valeur__min'] or 0,
        'repartition': evaluation.get_repartition_notes(),
        'taux_reussite': round(notes.filter(valeur__gte=10).count() / notes.count() * 100, 1) if notes.count() > 0 else 0
    }
    
    return JsonResponse(data)