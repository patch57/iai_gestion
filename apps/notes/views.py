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
    inscriptions = evaluation.cours.inscriptions_cours.filter(est_actif=True).order_by('etudiant__nom', 'etudiant__prenom')
    
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
        ).select_related('etudiant').order_by('etudiant__nom', 'etudiant__prenom')
        
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


# ========== FICHES D'ANONYMAT (CONFIDENTIEL) ==========

from .models import FicheNotesAnonymat, LigneFicheNotesAnonymat
from .forms import FicheAnonymatImportForm
from .services import analyser_fiche_anonymat_image, match_etudiant_par_nom
from apps.cours.models import Salle


def _est_autorise_anonymat(user):
    """Vérifie si l'utilisateur a accès aux fiches d'anonymat"""
    return (
        user.is_superuser
        or getattr(user, 'type_utilisateur', None) in ('CHEF_ANONYMAT', 'ADMIN_SYSTEME')
    )


@login_required
def liste_fiches_anonymat(request):
    """Dashboard confidentiel des fiches de notes d'anonymat"""
    if not _est_autorise_anonymat(request.user):
        messages.error(request, "❌ Accès refusé. Section réservée au Chef de l'Anonymat.")
        return redirect('tableau_bord:tableau_bord')

    queryset = FicheNotesAnonymat.objects.all().select_related('matiere', 'salle', 'type_evaluation', 'cree_par')

    # Filtres
    statut = request.GET.get('statut', '')
    if statut:
        queryset = queryset.filter(statut=statut)

    matiere_id = request.GET.get('matiere', '')
    if matiere_id:
        queryset = queryset.filter(matiere_id=matiere_id)

    # Stats
    total = queryset.count()
    brouillons = queryset.filter(statut='BROUILLON').count()
    valides = queryset.filter(statut='VALIDE').count()

    # Pagination
    paginator = Paginator(queryset.order_by('-date_import'), 20)
    page = request.GET.get('page')
    fiches = paginator.get_page(page)

    from apps.cours.models import Matiere as CoursMatiere
    context = {
        'fiches': fiches,
        'matieres': CoursMatiere.objects.all().order_by('code'),
        'stats': {'total': total, 'brouillons': brouillons, 'valides': valides},
        'statut_filtre': statut,
        'matiere_filtre': matiere_id,
        'titre': 'Fiches d\'Anonymat — Dashboard Confidentiel'
    }
    return render(request, 'notes/fiches_anonymat/liste.html', context)


@login_required
def importer_fiche_anonymat(request):
    """Importer une fiche de notes d'anonymat (image ou PDF)"""
    if not _est_autorise_anonymat(request.user):
        messages.error(request, "❌ Accès refusé.")
        return redirect('tableau_bord:tableau_bord')

    if request.method == 'POST':
        form = FicheAnonymatImportForm(request.POST, request.FILES)
        if form.is_valid():
            fiche = form.save(commit=False)
            fiche.cree_par = request.user
            fiche.statut = 'BROUILLON'
            fiche.save()

            # Récupérer les étudiants de la classe liée à la salle
            etudiants_classe = None
            salle = fiche.salle
            # Chercher une Classe correspondant au nom/code de la salle
            from apps.etudiants.models import Classe, AnneeAcademique
            annee_active = AnneeAcademique.get_active()
            if annee_active:
                classe = Classe.objects.filter(
                    nom__icontains=salle.code,
                    annee_academique=annee_active,
                    est_active=True
                ).first()
                if not classe:
                    classe = Classe.objects.filter(
                        nom__icontains=salle.nom,
                        annee_academique=annee_active,
                        est_active=True
                    ).first()
                if classe:
                    etudiants_classe = classe.etudiants.filter(statut__in=['INSCRIT', 'ACTIF'])

            # Lancer l'analyse OCR
            file_path = fiche.fichier_fiche.path if fiche.fichier_fiche else None
            resultats = analyser_fiche_anonymat_image(file_path, etudiants_classe)

            # Créer les lignes
            for r in resultats:
                LigneFicheNotesAnonymat.objects.create(
                    fiche=fiche,
                    numero_anonymat=r['numero_anonymat'],
                    note=r['note'],
                    nom_manuscrit_detecte=r['nom_manuscrit_detecte'],
                    etudiant=r.get('etudiant')
                )

            messages.success(request, f"✅ Fiche importée avec {len(resultats)} ligne(s) détectée(s). Vérifiez et validez.")
            return redirect('notes:valider_fiche_anonymat', pk=fiche.pk)
    else:
        form = FicheAnonymatImportForm()

    context = {
        'form': form,
        'titre': 'Importer une Fiche d\'Anonymat'
    }
    return render(request, 'notes/fiches_anonymat/importer.html', context)


@login_required
def valider_fiche_anonymat(request, pk):
    """Validation côte à côte d'une fiche d'anonymat"""
    if not _est_autorise_anonymat(request.user):
        messages.error(request, "❌ Accès refusé.")
        return redirect('tableau_bord:tableau_bord')

    fiche = get_object_or_404(FicheNotesAnonymat, pk=pk)
    lignes = fiche.lignes.all().select_related('etudiant').order_by('numero_anonymat')

    # Récupérer les étudiants pour les dropdowns de correction
    etudiants_disponibles = []
    from apps.etudiants.models import Classe, AnneeAcademique
    annee_active = AnneeAcademique.get_active()
    if annee_active:
        classe = Classe.objects.filter(
            nom__icontains=fiche.salle.code,
            annee_academique=annee_active,
            est_active=True
        ).first()
        if not classe:
            classe = Classe.objects.filter(
                nom__icontains=fiche.salle.nom,
                annee_academique=annee_active,
                est_active=True
            ).first()
        if classe:
            etudiants_disponibles = list(classe.etudiants.filter(statut__in=['INSCRIT', 'ACTIF']).order_by('nom', 'prenom'))

    if not etudiants_disponibles:
        etudiants_disponibles = list(Etudiant.objects.filter(statut__in=['INSCRIT', 'ACTIF']).order_by('nom', 'prenom')[:50])

    if request.method == 'POST':
        updated = 0
        for ligne in lignes:
            note_val = request.POST.get(f'note_{ligne.id}')
            etud_id = request.POST.get(f'etudiant_{ligne.id}')

            if note_val is not None and note_val != '':
                try:
                    from decimal import Decimal
                    ligne.note = Decimal(note_val)
                except Exception:
                    pass

            if etud_id:
                try:
                    ligne.etudiant_id = int(etud_id) if etud_id != '0' else None
                except (ValueError, TypeError):
                    ligne.etudiant_id = None
            else:
                ligne.etudiant_id = None

            ligne.save()
            updated += 1

        # Vérifier si on valide
        if 'valider' in request.POST:
            # Synchroniser les lignes de notes avec les objets Note officiels en base de données
            from django.utils import timezone
            from apps.etudiants.models import Niveau
            from apps.notes.models import Cours, Evaluation, Note
            
            note_count = 0
            for ligne in lignes:
                etud = ligne.etudiant
                if etud and ligne.note is not None:
                    # Déterminer le niveau
                    niveau = etud.niveau
                    if not niveau and etud.classe:
                        niveau = etud.classe.niveau
                    if not niveau:
                        niveau = Niveau.objects.filter(filiere=etud.filiere).first()
                    
                    if not niveau:
                        continue
                    
                    # Trouver ou créer la matière de notes correspondante
                    from apps.notes.models import Matiere as NotesMatiere
                    notes_matiere, _ = NotesMatiere.objects.get_or_create(
                        code=fiche.matiere.code,
                        defaults={
                            'nom': fiche.matiere.nom,
                            'credit': fiche.matiere.credits,
                            'semestre': fiche.matiere.semestre,
                            'volume_horaire': fiche.matiere.get_heures_totales()
                        }
                    )
                    
                    # Trouver ou créer le cours
                    cours, _ = Cours.objects.get_or_create(
                        matiere=notes_matiere,
                        filiere=etud.filiere,
                        niveau=niveau,
                        annee_academique=fiche.annee_academique,
                        defaults={
                            'semestre': fiche.matiere.semestre,
                            'volume_horaire': fiche.matiere.get_heures_totales()
                        }
                    )
                    
                    # Trouver ou créer l'évaluation
                    evaluation, _ = Evaluation.objects.get_or_create(
                        cours=cours,
                        type_evaluation=fiche.type_evaluation,
                        defaults={
                            'titre': f"{fiche.type_evaluation.nom} - {fiche.matiere.nom}",
                            'date_evaluation': fiche.date_import.date() if fiche.date_import else timezone.now().date(),
                            'coefficient': fiche.type_evaluation.coefficient_default,
                            'statut': 'TERMINEE',
                            'est_publiee': True,
                            'cree_par': request.user
                        }
                    )
                    
                    # Créer ou mettre à jour la note
                    Note.objects.update_or_create(
                        etudiant=etud,
                        evaluation=evaluation,
                        defaults={
                            'valeur': ligne.note,
                            'saisie_par': request.user,
                            'est_validee': True
                        }
                    )
                    note_count += 1
            
            fiche.statut = 'VALIDE'
            fiche.save()
            
            # Créer/mettre à jour automatiquement le procès-verbal de notes
            from apps.notes.models import ProcesVerbalNotes
            titre_pv = f"PV Notes - {fiche.matiere.nom} - {fiche.salle.code} - {fiche.type_evaluation.nom} ({fiche.annee_academique})"
            ProcesVerbalNotes.objects.update_or_create(
                fiche_anonymat=fiche,
                defaults={
                    'titre': titre_pv,
                    'cree_par': request.user
                }
            )
            
            messages.success(request, f"✅ Fiche validée avec {updated} ligne(s) enregistrée(s). {note_count} note(s) officielle(s) créée(s) / mise(s) à jour et Procès-Verbal archivé.")
            return redirect('notes:liste_fiches_anonymat')
        else:
            messages.success(request, f"✅ {updated} ligne(s) mise(s) à jour (brouillon conservé).")
            return redirect('notes:valider_fiche_anonymat', pk=fiche.pk)

    # Calcul des stats pour affichage
    notes_values = [float(l.note) for l in lignes if l.note is not None]
    stats = {}
    if notes_values:
        stats['moyenne'] = round(sum(notes_values) / len(notes_values), 2)
        stats['min'] = min(notes_values)
        stats['max'] = max(notes_values)
        stats['total'] = len(notes_values)
        stats['reussites'] = sum(1 for n in notes_values if n >= 10)
        stats['taux_reussite'] = round((stats['reussites'] / stats['total']) * 100, 1) if stats['total'] > 0 else 0
        matched = sum(1 for l in lignes if l.etudiant is not None)
        stats['matched'] = matched
        stats['taux_matching'] = round((matched / stats['total']) * 100, 1) if stats['total'] > 0 else 0

    context = {
        'fiche': fiche,
        'lignes': lignes,
        'etudiants_disponibles': etudiants_disponibles,
        'stats': stats,
        'titre': f'Validation — {fiche}'
    }
    return render(request, 'notes/fiches_anonymat/valider.html', context)


@login_required
def supprimer_fiche_anonymat(request, pk):
    """Supprimer une fiche d'anonymat brouillon"""
    if not _est_autorise_anonymat(request.user):
        messages.error(request, "❌ Accès refusé.")
        return redirect('tableau_bord:tableau_bord')

    fiche = get_object_or_404(FicheNotesAnonymat, pk=pk)

    if request.method == 'POST':
        fiche.delete()
        messages.success(request, "🗑️ Fiche supprimée avec succès.")
        return redirect('notes:liste_fiches_anonymat')

    return redirect('notes:liste_fiches_anonymat')


# ========== RECOURS ENSEIGNANT / ADMIN ==========

@login_required
def liste_recours(request):
    """Liste des demandes de recours, filtrables par statut et matière"""
    user = request.user
    role = getattr(user, 'type_utilisateur', None)
    
    if role in ('ETUDIANT', 'APPRENANT'):
        queryset = RecoursNote.objects.filter(etudiant__utilisateur=user)
        is_staff_or_teacher = False
    else:
        queryset = RecoursNote.objects.all()
        is_staff_or_teacher = True
        # Si c'est un enseignant/professeur, filtrer par ses cours
        if role in ('ENSEIGNANT', 'PROFESSEUR', 'FORMATEUR'):
            queryset = queryset.filter(evaluation__cours__professeur=user)
            
    # Filtres
    statut = request.GET.get('statut', '')
    if statut:
        queryset = queryset.filter(statut=statut)
        
    matiere_id = request.GET.get('matiere', '')
    if matiere_id:
        queryset = queryset.filter(evaluation__cours__matiere_id=matiere_id)
        
    # Pagination
    paginator = Paginator(queryset.select_related('etudiant', 'evaluation__cours__matiere', 'evaluation__type_evaluation'), 20)
    page = request.GET.get('page')
    recours_list = paginator.get_page(page)
    
    from apps.cours.models import Matiere as CoursMatiere
    context = {
        'recours_list': recours_list,
        'statut_filtre': statut,
        'matiere_filtre': matiere_id,
        'matieres': CoursMatiere.objects.all().order_by('code'),
        'is_staff_or_teacher': is_staff_or_teacher,
        'titre': 'Suivi des Recours de Notes'
    }
    return render(request, 'notes/recours/liste.html', context)


@login_required
def traiter_recours(request, pk):
    """Traiter une demande de recours (validation ou rejet)"""
    user = request.user
    role = getattr(user, 'type_utilisateur', None)
    
    if role in ('ETUDIANT', 'APPRENANT'):
        messages.error(request, "❌ Accès refusé.")
        return redirect('notes:mes_notes')
        
    recours = get_object_or_404(RecoursNote, pk=pk)
    
    # Vérifier l'autorisation pour l'enseignant
    if role in ('ENSEIGNANT', 'PROFESSEUR', 'FORMATEUR') and recours.evaluation.cours.professeur != user:
        messages.error(request, "❌ Accès refusé : vous n'enseignez pas cette matière pour cette classe.")
        return redirect('notes:liste_recours')
        
    if request.method == 'POST':
        statut_decision = request.POST.get('statut')
        decision_comm = request.POST.get('decision', '')
        
        if statut_decision in ('ACCEPTE', 'REJETE'):
            recours.statut = statut_decision
            recours.decision = decision_comm
            recours.date_traitement = timezone.now()
            recours.traite_par = user
            recours.save()
            
            if statut_decision == 'ACCEPTE':
                # Mettre à jour la note réelle de l'étudiant
                note_obj = Note.objects.filter(etudiant=recours.etudiant, evaluation=recours.evaluation).first()
                if note_obj:
                    note_obj.valeur = recours.note_demandee
                    note_obj.observation = f"Modifiée suite au recours #{recours.id}."
                    note_obj.save()
                    
            messages.success(request, f"✅ Recours {recours.get_statut_display()} avec succès.")
            return redirect('notes:liste_recours')
        else:
            messages.error(request, "❌ Action de décision invalide.")
            
    context = {
        'recours': recours,
        'titre': f"Traiter le recours - {recours.etudiant.get_nom_complet()}"
    }
    return render(request, 'notes/recours/traiter.html', context)


# ========== BULLETIN ÉTUDIANT ==========

@login_required
def mon_bulletin(request):
    """Espace personnel étudiant : Bulletin semestriel interactif"""
    try:
        etudiant = Etudiant.objects.get(utilisateur=request.user)
    except Etudiant.DoesNotExist:
        messages.error(request, '❌ Vous n\'êtes pas identifié en tant qu\'étudiant.')
        return redirect('tableau_bord:tableau_bord')
        
    annee = get_annee_academique_active(request)
    bulletins = Bulletin.objects.filter(etudiant=etudiant).order_by('-annee_academique', 'semestre')
    
    semestre = request.GET.get('semestre', '1')
    try:
        semestre_int = int(semestre)
    except ValueError:
        semestre_int = 1
        
    bulletin_actif = bulletins.filter(annee_academique=annee, semestre=semestre_int).first()
    
    details = []
    progression = 0
    total_credits = 0
    credits_obtenus = 0
    
    if bulletin_actif:
        details = bulletin_actif.details.all().select_related('matiere')
        total_credits = sum(d.credits for d in details)
        credits_obtenus = bulletin_actif.credits_obtenus
        progression = round((credits_obtenus / total_credits) * 100, 1) if total_credits > 0 else 0
        
    context = {
        'etudiant': etudiant,
        'bulletins': bulletins,
        'bulletin_actif': bulletin_actif,
        'details': details,
        'progression': progression,
        'total_credits': total_credits,
        'credits_obtenus': credits_obtenus,
        'annee': annee,
        'semestre_actif': semestre_int,
        'titre': 'Mon Bulletin Semestriel'
      }
    return render(request, 'notes/bulletin/mon_bulletin.html', context)


# ========== APIs AJAX (STATISTIQUES) ==========

@login_required
def api_notes_etudiant(request, etudiant_id):
    """API JSON : Notes d'un étudiant particulier"""
    role = getattr(request.user, 'type_utilisateur', None)
    
    if role in ('ETUDIANT', 'APPRENANT'):
        try:
            etudiant = Etudiant.objects.get(utilisateur=request.user)
            if etudiant.id != etudiant_id:
                return JsonResponse({'error': 'Accès interdit'}, status=403)
        except Etudiant.DoesNotExist:
            return JsonResponse({'error': 'Profil étudiant introuvable'}, status=404)
    else:
        etudiant = get_object_or_404(Etudiant, pk=etudiant_id)
        
    notes = Note.objects.filter(etudiant=etudiant, est_validee=True).select_related('evaluation__cours__matiere', 'evaluation__type_evaluation')
    data = []
    for note in notes:
        data.append({
            'evaluation': note.evaluation.titre,
            'matiere_code': note.evaluation.cours.matiere.code,
            'matiere_nom': note.evaluation.cours.matiere.nom,
            'type_evaluation': note.evaluation.type_evaluation.nom,
            'valeur': float(note.valeur),
            'coefficient': float(note.evaluation.coefficient),
            'note_ponderee': float(note.get_note_ponderee()),
            'date': note.evaluation.date_evaluation.isoformat(),
        })
        
    return JsonResponse({
        'etudiant': etudiant.get_nom_complet(),
        'notes': data
    })


@login_required
def api_moyennes_filiere(request, filiere_id):
    """API JSON : Statistiques globales des moyennes par semestre d'une filière"""
    role = getattr(request.user, 'type_utilisateur', None)
    if role in ('ETUDIANT', 'APPRENANT'):
        return JsonResponse({'error': 'Accès interdit'}, status=403)
        
    filiere = get_object_or_404(Filiere, pk=filiere_id)
    annee = get_annee_academique_active(request)
    
    bulletins = Bulletin.objects.filter(
        etudiant__filiere=filiere,
        annee_academique=annee,
        est_valide=True
    )
    
    stats = []
    for sem in [1, 2]:
        avg_sem = bulletins.filter(semestre=sem).aggregate(avg=Avg('moyenne_semestre'))['avg']
        stats.append({
            'semestre': sem,
            'moyenne_generale': round(float(avg_sem), 2) if avg_sem else None,
            'effectif_total': bulletins.filter(semestre=sem).count(),
            'admis': bulletins.filter(semestre=sem, decision='ADMIS').count(),
            'ajournes': bulletins.filter(semestre=sem, decision='AJOURNE').count(),
        })
        
    return JsonResponse({
        'filiere': filiere.nom,
        'annee_academique': annee,
        'statistiques': stats
    })


# ========== PROCÈS-VERBAUX DE NOTES ==========

@login_required
def detail_pv(request, pk):
    """Affiche le procès-verbal de notes (format imprimable officiel)"""
    role = getattr(request.user, 'type_utilisateur', None)
    if role not in ('CHEF_ANONYMAT', 'CHEF_ETUDES', 'ADMIN_SYSTEME') and not request.user.is_superuser:
        messages.error(request, "❌ Accès réservé aux personnes autorisées.")
        return redirect('tableau_bord:tableau_bord')
        
    from apps.notes.models import ProcesVerbalNotes
    from django.utils import timezone
    pv = get_object_or_404(ProcesVerbalNotes, pk=pk)
    
    lignes = []
    coefficient = 1.00
    enseignant_nom = ""
    niveau_nom = "I"
    
    if pv.fiche_anonymat:
        lignes = pv.fiche_anonymat.lignes.all().select_related('etudiant').order_by('etudiant__nom', 'etudiant__prenom')
        coefficient = pv.fiche_anonymat.type_evaluation.coefficient_default
        enseignant_nom = pv.fiche_anonymat.enseignant_nom
        
        # Déterminer le niveau
        if lignes.exists() and lignes.first().etudiant and lignes.first().etudiant.niveau:
            num = lignes.first().etudiant.niveau.numero
            romains = {1: 'I', 2: 'II', 3: 'III'}
            niveau_nom = romains.get(num, str(num))
            
    context = {
        'pv': pv,
        'lignes': lignes,
        'coefficient': coefficient,
        'enseignant_nom': enseignant_nom,
        'niveau_nom': niveau_nom,
        'date_impression': timezone.now(),
        'titre': pv.titre
    }
    return render(request, 'notes/pv/detail_pv.html', context)


@login_required
def transmettre_pv(request, pk):
    """Transmet le PV confidentiellement au Chef des Études"""
    if not _est_autorise_anonymat(request.user):
        messages.error(request, "❌ Action réservée au Chef de l'Anonymat.")
        return redirect('tableau_bord:tableau_bord')
        
    from apps.notes.models import ProcesVerbalNotes
    from django.utils import timezone
    pv = get_object_or_404(ProcesVerbalNotes, pk=pk)
    
    if request.method == 'POST':
        pv.est_transmis = True
        pv.date_transmission = timezone.now()
        pv.save()
        messages.success(request, f"✉️ Le procès-verbal \"{pv.titre}\" a été transmis confidentiellement au Chef des Études.")
        
    return redirect('tableau_bord:tableau_bord')


@login_required
def supprimer_pv(request, pk):
    """Supprime un Procès-verbal de notes (le fait disparaître pour le Chef de l'Anonymat et le Chef des Études)"""
    if not _est_autorise_anonymat(request.user):
        messages.error(request, "❌ Action réservée au Chef de l'Anonymat.")
        return redirect('tableau_bord:tableau_bord')
        
    from apps.notes.models import ProcesVerbalNotes
    pv = get_object_or_404(ProcesVerbalNotes, pk=pk)
    
    if request.method == 'POST':
        titre = pv.titre
        # Supprimer le fichier physique s'il existe
        if pv.fichier_excel:
            pv.fichier_excel.delete(save=False)
        pv.delete()
        messages.success(request, f"🗑️ Le procès-verbal \"{titre}\" a été supprimé avec succès.")
        
    return redirect('tableau_bord:tableau_bord')