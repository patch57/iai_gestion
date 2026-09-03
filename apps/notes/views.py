"""
Vues pour la gestion des notes
IAI-Cameroun - Centre de Douala
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from apps.authentification.decorators import role_required
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
    CampusLocation, PointInteret, FicheNotesAnonymat, ProcesVerbalNotes
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
    if getattr(request.user, 'type_utilisateur', None) == 'CHEF_ANONYMAT':
        messages.warning(request, "⚠️ L'accès à la liste générale des évaluations est restreint pour le Chef Anonymat.")
        return redirect('notes:dashboard_chef_anonymat')

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

            # --- Notification Tri-canal des Étudiants pour la publication de leurs notes ---
            from django.conf import settings
            from apps.tableau_bord.models import Notification
            from apps.tableau_bord.whatsapp_service import WhatsAppService
            from django.core.mail import send_mail

            site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')

            for note_obj in Note.objects.filter(evaluation=evaluation).select_related('etudiant', 'etudiant__utilisateur'):
                etud = note_obj.etudiant
                if not etud:
                    continue

                titre_notif = f"📊 Publication de Note : {evaluation.titre}"
                msg_notif = f"Votre note pour l'évaluation '{evaluation.titre}' a été validée et publiée. Note : {note_obj.valeur}/20."

                # 1. Dashboard In-App
                if etud.utilisateur:
                    Notification.objects.create(
                        utilisateur=etud.utilisateur,
                        type='INFO',
                        titre=titre_notif,
                        message=msg_notif,
                        lien='/notes/mes-notes/'
                    )

                # 2. Email réel
                dest_email = etud.email or (etud.utilisateur.email if etud.utilisateur else None)
                if dest_email:
                    try:
                        send_mail(
                            subject=f"{getattr(settings, 'EMAIL_SUBJECT_PREFIX', '[IAI-Cameroun] ')}Publication de Note - {evaluation.titre}",
                            message=f"Bonjour {etud.get_nom_complet()},\n\n{msg_notif}\n\nConsultez l'ensemble de vos résultats sur : {site_url}/notes/mes-notes/",
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[dest_email],
                            fail_silently=True
                        )
                    except Exception:
                        pass

                # 3. WhatsApp
                try:
                    WhatsAppService.notifier_etudiant(
                        etudiant=etud,
                        titre=f"Note Publiée ({evaluation.titre})",
                        message=f"Alerte Note - IAI-Cameroun (Douala)\n\nBonjour {etud.get_nom_complet()},\n{msg_notif}\n\nConsultez vos résultats : {site_url}/notes/mes-notes/"
                    )
                except Exception:
                    pass

            messages.success(request, f'✅ {count} note(s) validée(s), publiée(s) et notifiées aux étudiants !')
        
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
@role_required('CHEF_ANONYMAT', 'CHEF_ETUDES', 'ADMIN_PEDAGOGIQUE', 'ADMIN_SYSTEME')
def reveler_identites(request, evaluation_id):
    """Révéler les identités après correction (réservé aux rôles autorisés)"""
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
    """Notes de l'étudiant ou de l'apprenant connecté"""
    if request.user.type_utilisateur == 'APPRENANT':
        from apps.etudiants.models import Apprenant
        from apps.notes.models import NoteApprenant

        apprenant = getattr(request.user, 'profil_apprenant', None)
        if not apprenant:
            apprenant = Apprenant.objects.filter(email=request.user.email).first()

        if not apprenant:
            messages.error(request, "❌ Aucun profil d'apprenant trouvé pour cet utilisateur.")
            return redirect('tableau_bord:tableau_bord')

        formations = apprenant.formations.all()
        notes_qs = NoteApprenant.objects.filter(apprenant=apprenant).select_related('formation', 'matiere', 'formateur')

        formations_data = []
        for formation in formations:
            matieres = list(formation.matieres.filter(est_active=True))
            notes_dict = {n.matiere_id: n for n in notes_qs.filter(formation=formation)}

            matieres_data = []
            total_pts = 0.0
            total_coef = 0.0

            for mat in matieres:
                n_obj = notes_dict.get(mat.id)
                val_note = float(n_obj.note) if n_obj else None
                coeff = float(mat.coefficient)

                if val_note is not None:
                    total_pts += val_note * coeff
                    total_coef += coeff

                matieres_data.append({
                    'matiere': mat,
                    'note': val_note,
                    'commentaire': n_obj.commentaire if n_obj else '',
                    'date_eval': n_obj.date_evaluation if n_obj else None,
                    'formateur': n_obj.formateur if n_obj else None,
                })

            moyenne = round(total_pts / total_coef, 2) if total_coef > 0 else None
            decision = 'Admis(e)' if (moyenne is not None and moyenne >= 10.0) else ('Ajourné(e)' if moyenne is not None else 'En attente')
            decision_color = 'bg-emerald-100 text-emerald-800 border-emerald-200' if (moyenne is not None and moyenne >= 10.0) else ('bg-rose-100 text-rose-800 border-rose-200' if moyenne is not None else 'bg-gray-100 text-gray-700 border-gray-200')

            formations_data.append({
                'formation': formation,
                'matieres_data': matieres_data,
                'moyenne': moyenne,
                'decision': decision,
                'decision_color': decision_color,
            })

        context = {
            'apprenant': apprenant,
            'formations_data': formations_data,
            'titre': 'Mes Notes & Évaluations'
        }
        return render(request, 'notes/mes_notes_apprenant.html', context)

    # Étudiants cursus classique
    try:
        etudiant = Etudiant.objects.get(utilisateur=request.user)
    except Etudiant.DoesNotExist:
        messages.error(request, '❌ Vous n\'êtes pas un étudiant.')
        return redirect('tableau_bord:tableau_bord')
    
    from .models import Note, LigneProcesVerbalNotes, FicheNotesAnonymat
    from apps.cours.models import Matiere

    salle_etu = getattr(etudiant, 'salle', None)
    filiere_etu = etudiant.filiere
    niveau_etu = etudiant.niveau

    # Matières du cursus de l'étudiant
    matieres_qs = Matiere.objects.all().order_by('code', 'nom')
    if filiere_etu:
        mats_fil = matieres_qs.filter(cours__filiere=filiere_etu).distinct()
        if mats_fil.exists():
            matieres_qs = mats_fil

    # Notes saisies directement (Note objects)
    notes_directes = Note.objects.filter(
        etudiant=etudiant,
        est_validee=True
    ).select_related('evaluation__cours__matiere', 'evaluation__type_evaluation')

    # Lignes de PVs transmises au Chef des Études
    lignes_pv = LigneProcesVerbalNotes.objects.filter(
        etudiant=etudiant,
        pv__est_transmis=True
    ).select_related('pv__matiere', 'pv__salle')

    pv_dict_by_matiere = {lpv.pv.matiere_id: lpv for lpv in lignes_pv if lpv.pv and lpv.pv.matiere_id}

    notes_directes_dict = {}
    for nd in notes_directes:
        if nd.evaluation and nd.evaluation.cours and nd.evaluation.cours.matiere_id:
            m_id = nd.evaluation.cours.matiere_id
            t_code = nd.evaluation.type_evaluation.code.upper()
            notes_directes_dict[(m_id, t_code)] = float(nd.valeur)

    # Récupérer les fiches transmises par matière
    fiches_transmises_qs = FicheNotesAnonymat.objects.filter(
        statut__in=['TRANSMIS_CHEF_ETUDES', 'VALIDE']
    ).select_related('matiere', 'type_evaluation')
    if salle_etu:
        fiches_transmises_qs = fiches_transmises_qs.filter(salle=salle_etu)

    fiches_by_matiere = {}
    for f in fiches_transmises_qs:
        mid = f.matiere_id
        if mid not in fiches_by_matiere:
            fiches_by_matiere[mid] = set()
        tcode = f.type_evaluation.code.upper()
        if 'CC' in tcode or 'CONTROLE' in tcode or 'TP' in tcode or 'TD' in tcode:
            fiches_by_matiere[mid].add('CC')
        elif 'EXAM' in tcode and 'RATT' not in tcode:
            fiches_by_matiere[mid].add('EXAM')
        elif 'RATT' in tcode:
            fiches_by_matiere[mid].add('RATT')

    releve_matieres = []

    for mat in matieres_qs:
        lpv = pv_dict_by_matiere.get(mat.id)
        f_types = fiches_by_matiere.get(mat.id, set())

        cc_tr = 'CC' in f_types or (lpv and lpv.note_cc is not None)
        exam_tr = 'EXAM' in f_types or (lpv and lpv.note_examen is not None)

        les_deux_transmis = cc_tr and exam_tr

        # Note CC
        val_cc = None
        is_cc_manquante = False
        if (mat.id, 'CC') in notes_directes_dict:
            val_cc = notes_directes_dict[(mat.id, 'CC')]
            cc_tr = True
        elif lpv and lpv.note_cc is not None:
            val_cc = float(lpv.note_cc)
            is_cc_manquante = lpv.note_cc_manquante and les_deux_transmis

        # Note Examen
        val_exam = None
        is_exam_manquante = False
        if (mat.id, 'EXAM') in notes_directes_dict:
            val_exam = notes_directes_dict[(mat.id, 'EXAM')]
            exam_tr = True
        elif lpv and lpv.note_examen is not None:
            val_exam = float(lpv.note_examen)
            is_exam_manquante = lpv.note_examen_manquante and les_deux_transmis

        # Note Rattrapage
        val_ratt = None
        if (mat.id, 'RATT') in notes_directes_dict:
            val_ratt = notes_directes_dict[(mat.id, 'RATT')]
        elif lpv and lpv.note_rattrapage is not None:
            val_ratt = float(lpv.note_rattrapage)

        # Ne retenir que les matières ayant au moins une note ou une transmission
        if val_cc is None and val_exam is None and val_ratt is None and not cc_tr and not exam_tr:
            continue

        # Note finale / Moyenne
        note_finale = 0.0
        if les_deux_transmis:
            exam_eff = val_ratt if val_ratt is not None else (val_exam if val_exam is not None else 0.0)
            cc_eff = val_cc if val_cc is not None else 0.0
            note_finale = round((cc_eff * 0.40) + (exam_eff * 0.60), 2)
        elif lpv and lpv.note_finale is not None and lpv.pv.est_transmis and les_deux_transmis:
            note_finale = float(lpv.note_finale)

        # Déterminer la mention / observation
        if les_deux_transmis:
            if note_finale >= 16:
                mention = "Très Bien"
                badge_style = "bg-green-100 text-green-800 border-green-200"
            elif note_finale >= 14:
                mention = "Bien"
                badge_style = "bg-emerald-100 text-emerald-800 border-emerald-200"
            elif note_finale >= 12:
                mention = "Assez Bien"
                badge_style = "bg-blue-100 text-blue-800 border-blue-200"
            elif note_finale >= 10:
                mention = "Passable (Validée)"
                badge_style = "bg-sky-100 text-sky-800 border-sky-200"
            else:
                mention = "Échec (Ajournée)"
                badge_style = "bg-rose-100 text-rose-800 border-rose-200"
        elif cc_tr and not exam_tr:
            mention = "CC Transmis (Examen en attente)"
            badge_style = "bg-amber-100 text-amber-800 border-amber-200"
        elif exam_tr and not cc_tr:
            mention = "Examen Transmis (CC en attente)"
            badge_style = "bg-amber-100 text-amber-800 border-amber-200"
        else:
            mention = "En attente de transmission"
            badge_style = "bg-gray-100 text-gray-700 border-gray-200"

        releve_matieres.append({
            'matiere': mat,
            'coefficient': float(getattr(mat, 'coefficient', 1.0)),
            'val_cc': val_cc,
            'cc_transmis': cc_tr,
            'is_cc_manquante': is_cc_manquante,
            'val_exam': val_exam,
            'exam_transmis': exam_tr,
            'is_exam_manquante': is_exam_manquante,
            'val_ratt': val_ratt,
            'note_finale': note_finale,
            'les_deux_transmis': les_deux_transmis,
            'mention': mention,
            'badge_style': badge_style
        })

    bulletins = Bulletin.objects.filter(etudiant=etudiant).order_by('-annee_academique', 'semestre')

    # Statistiques
    notes_completes = [m['note_finale'] for m in releve_matieres if m['les_deux_transmis']]
    mat_validees = sum(1 for m in releve_matieres if m['les_deux_transmis'] and m['note_finale'] >= 10)
    moyenne_gen = round(sum(notes_completes) / len(notes_completes), 2) if notes_completes else 0.0
    meilleure_note = max(notes_completes) if notes_completes else 0.0

    stats = {
        'moyenne_generale': moyenne_gen,
        'total_credits': bulletins.aggregate(Sum('credits_obtenus'))['credits_obtenus__sum'] or 0,
        'meilleure_note': meilleure_note,
        'matieres_validees': mat_validees,
        'total_matieres': len(releve_matieres),
    }

    if stats['total_matieres'] > 0:
        stats['taux_reussite'] = round((stats['matieres_validees'] / stats['total_matieres']) * 100, 1)

    context = {
        'etudiant': etudiant,
        'releve_matieres': releve_matieres,
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
def statistiques_notes(request):
    """Tableau de bord synthétique des statistiques de notes"""
    annee_code = get_annee_academique_active(request)
    annee_obj = AnneeAcademique.objects.filter(code=annee_code).first() or AnneeAcademique.objects.filter(est_active=True).first()
    semestre_val = request.GET.get('semestre')
    semestre = int(semestre_val) if semestre_val and semestre_val.isdigit() else 1
    
    # 1. Statistiques par filière
    stats_par_filiere = []
    filieres_noms = []
    filieres_moyennes = []
    filieres_taux_reussite = []
    
    filieres = Filiere.objects.filter(est_active=True)
    for filiere in filieres:
        bulletins = Bulletin.objects.filter(
            etudiant__filiere=filiere,
            semestre=semestre,
            est_valide=True
        )
        if annee_obj:
            bulletins = bulletins.filter(annee_academique=annee_obj)
        
        count = bulletins.count()
        if count > 0:
            avg_moyenne = round(bulletins.aggregate(Avg('moyenne_semestre'))['moyenne_semestre__avg'] or 0, 2)
            admis_count = bulletins.filter(decision='ADMIS').count()
            ajournes_count = bulletins.filter(decision='AJOURNE').count()
            exclus_count = bulletins.filter(decision='EXCLU').count()
            taux_reussite = round((admis_count / count) * 100, 1)
            max_moyenne = round(bulletins.aggregate(Max('moyenne_semestre'))['moyenne_semestre__max'] or 0, 2)
            min_moyenne = round(bulletins.aggregate(Min('moyenne_semestre'))['moyenne_semestre__min'] or 0, 2)

            stats_par_filiere.append({
                'filiere': filiere,
                'effectif': count,
                'moyenne': avg_moyenne,
                'admis': admis_count,
                'ajournes': ajournes_count,
                'exclus': exclus_count,
                'taux_reussite': taux_reussite,
                'meilleure_moyenne': max_moyenne,
                'plus_basse_moyenne': min_moyenne,
            })

            filieres_noms.append(filiere.code)
            filieres_moyennes.append(avg_moyenne)
            filieres_taux_reussite.append(taux_reussite)

    # 2. KPIs Globaux
    bulletins_tous = Bulletin.objects.filter(semestre=semestre, est_valide=True)
    if annee_obj:
        bulletins_tous = bulletins_tous.filter(annee_academique=annee_obj)
    
    total_bulletins = bulletins_tous.count()
    moyenne_globale = round(bulletins_tous.aggregate(Avg('moyenne_semestre'))['moyenne_semestre__avg'] or 0, 2)
    total_admis = bulletins_tous.filter(decision='ADMIS').count()
    taux_reussite_global = round((total_admis / total_bulletins * 100), 1) if total_bulletins > 0 else 0

    evaluations_qs = Evaluation.objects.all()
    if annee_obj:
        evaluations_qs = evaluations_qs.filter(annee_academique=annee_obj)
    total_evaluations = evaluations_qs.count()

    # 3. Statistiques par type d'évaluation
    stats_par_type = []
    for type_eval in TypeEvaluation.objects.all():
        evals_type = evaluations_qs.filter(type_evaluation=type_eval)
        evals_count = evals_type.count()
        notes_type = Note.objects.filter(evaluation__in=evals_type)
        avg_note = round(notes_type.aggregate(Avg('valeur'))['valeur__avg'] or 0, 2)
        stats_par_type.append({
            'type': type_eval,
            'count': evals_count,
            'moyenne_note': avg_note
        })

    context = {
        'stats_par_filiere': stats_par_filiere,
        'stats_par_type': stats_par_type,
        'total_bulletins': total_bulletins,
        'moyenne_globale': moyenne_globale,
        'total_admis': total_admis,
        'taux_reussite_global': taux_reussite_global,
        'total_evaluations': total_evaluations,
        'annee': annee_code,
        'annee_obj': annee_obj,
        'semestre': semestre,
        'filieres_noms_json': json.dumps(filieres_noms),
        'filieres_moyennes_json': json.dumps(filieres_moyennes),
        'filieres_taux_json': json.dumps(filieres_taux_reussite),
        'titre': 'Statistiques des Notes'
    }
    return render(request, 'notes/statistiques_notes.html', context)


@login_required
def statistiques_par_filiere(request):
    """Analyse statistique détaillée par Filière et Classe"""
    annee_code = get_annee_academique_active(request)
    annee_obj = AnneeAcademique.objects.filter(code=annee_code).first() or AnneeAcademique.objects.filter(est_active=True).first()
    
    filieres = Filiere.objects.filter(est_active=True)
    filiere_id = request.GET.get('filiere_id')
    semestre_val = request.GET.get('semestre')
    semestre = int(semestre_val) if semestre_val and semestre_val.isdigit() else 1

    filiere_selectionnee = None
    if filiere_id and filiere_id.isdigit():
        filiere_selectionnee = Filiere.objects.filter(pk=filiere_id).first()
    if not filiere_selectionnee:
        filiere_selectionnee = filieres.first()

    stats_detail = []
    distribution_tranches = {
        'moins_8': 0,
        'de_8_a_10': 0,
        'de_10_a_12': 0,
        'de_12_a_14': 0,
        'de_14_a_16': 0,
        'plus_16': 0,
    }
    top_etudiants = []
    matieres_performances = []

    if filiere_selectionnee:
        bulletins = Bulletin.objects.filter(
            etudiant__filiere=filiere_selectionnee,
            semestre=semestre,
            est_valide=True
        ).select_related('etudiant')

        if annee_obj:
            bulletins = bulletins.filter(annee_academique=annee_obj)

        for b in bulletins:
            m = b.moyenne_semestre or 0
            if m < 8:
                distribution_tranches['moins_8'] += 1
            elif 8 <= m < 10:
                distribution_tranches['de_8_a_10'] += 1
            elif 10 <= m < 12:
                distribution_tranches['de_10_a_12'] += 1
            elif 12 <= m < 14:
                distribution_tranches['de_12_a_14'] += 1
            elif 14 <= m < 16:
                distribution_tranches['de_14_a_16'] += 1
            else:
                distribution_tranches['plus_16'] += 1

        top_etudiants = bulletins.order_by('-moyenne_semestre')[:5]

        # Performances par matière (via DetailBulletin)
        details = DetailBulletin.objects.filter(bulletin__in=bulletins).values(
            'matiere__code', 'matiere__nom'
        ).annotate(
            moyenne_matiere=Avg('moyenne'),
            note_min=Min('moyenne'),
            note_max=Max('moyenne'),
            nb_notes=Count('id')
        ).order_by('-moyenne_matiere')

        matieres_performances = [
            {
                'code': d['matiere__code'],
                'nom': d['matiere__nom'],
                'moyenne': round(d['moyenne_matiere'] or 0, 2),
                'min': round(d['note_min'] or 0, 2),
                'max': round(d['note_max'] or 0, 2),
                'effectif': d['nb_notes'],
            }
            for d in details
        ]

    context = {
        'filieres': filieres,
        'filiere_selectionnee': filiere_selectionnee,
        'semestre': semestre,
        'annee': annee_code,
        'tranches': distribution_tranches,
        'top_etudiants': top_etudiants,
        'matieres_performances': matieres_performances,
        'tranches_json': json.dumps(list(distribution_tranches.values())),
        'titre': f'Statistiques Filière - {filiere_selectionnee.nom if filiere_selectionnee else ""}'
    }
    return render(request, 'notes/statistiques_filieres.html', context)


@login_required
def statistiques_evaluations(request):
    """Statistiques détaillées des Évaluations (CC, TP, Examens)"""
    annee_code = get_annee_academique_active(request)
    annee_obj = AnneeAcademique.objects.filter(code=annee_code).first() or AnneeAcademique.objects.filter(est_active=True).first()

    types_eval = TypeEvaluation.objects.all()
    filieres = Filiere.objects.filter(est_active=True)

    type_id = request.GET.get('type_id')
    filiere_id = request.GET.get('filiere_id')
    query_search = request.GET.get('q', '').strip()

    evaluations_qs = Evaluation.objects.all().select_related('cours__matiere', 'cours__filiere', 'type_evaluation')

    if annee_obj:
        evaluations_qs = evaluations_qs.filter(annee_academique=annee_obj)

    if type_id and type_id.isdigit():
        evaluations_qs = evaluations_qs.filter(type_evaluation_id=type_id)

    if filiere_id and filiere_id.isdigit():
        evaluations_qs = evaluations_qs.filter(cours__filiere_id=filiere_id)

    if query_search:
        evaluations_qs = evaluations_qs.filter(
            Q(titre__icontains=query_search) | 
            Q(cours__matiere__nom__icontains=query_search) | 
            Q(cours__matiere__code__icontains=query_search)
        )

    stats_evaluations = []
    for ev in evaluations_qs[:50]:  # Limiter à 50 évaluations récentes pour la performance
        notes = Note.objects.filter(evaluation=ev)
        count_notes = notes.count()
        if count_notes > 0:
            avg_val = round(notes.aggregate(Avg('valeur'))['valeur__avg'] or 0, 2)
            min_val = round(notes.aggregate(Min('valeur'))['valeur__min'] or 0, 2)
            max_val = round(notes.aggregate(Max('valeur'))['valeur__max'] or 0, 2)
            reussites = notes.filter(valeur__gte=10).count()
            taux_reussite = round((reussites / count_notes) * 100, 1)
        else:
            avg_val, min_val, max_val, taux_reussite = 0, 0, 0, 0

        stats_evaluations.append({
            'evaluation': ev,
            'nombre_notes': count_notes,
            'moyenne': avg_val,
            'min': min_val,
            'max': max_val,
            'taux_reussite': taux_reussite,
        })

    # Métriques résumé
    notes_toutes = Note.objects.filter(evaluation__in=evaluations_qs)
    moyenne_toutes = round(notes_toutes.aggregate(Avg('valeur'))['valeur__avg'] or 0, 2) if notes_toutes.exists() else 0
    total_evals_count = evaluations_qs.count()

    context = {
        'evaluations': stats_evaluations,
        'types_eval': types_eval,
        'filieres': filieres,
        'selected_type': int(type_id) if type_id and type_id.isdigit() else None,
        'selected_filiere': int(filiere_id) if filiere_id and filiere_id.isdigit() else None,
        'search_query': query_search,
        'total_evaluations': total_evals_count,
        'moyenne_globale_evals': moyenne_toutes,
        'annee': annee_code,
        'titre': 'Statistiques des Évaluations'
    }
    return render(request, 'notes/statistiques_evaluations.html', context)


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

            # --- Notification Tri-Canal du Chef Anonymat & Chef des Études ---
            from apps.tableau_bord.models import Notification
            from apps.tableau_bord.whatsapp_service import WhatsAppService
            from django.contrib.auth import get_user_model
            from django.core.mail import send_mail
            from django.conf import settings

            User = get_user_model()
            destinataires = User.objects.filter(
                type_utilisateur__in=['CHEF_ANONYMAT', 'CHEF_ETUDES', 'ADMIN_PEDAGOGIQUE'],
                est_actif=True
            )
            if not destinataires.exists():
                destinataires = User.objects.filter(is_superuser=True, est_actif=True)

            titre_notif = "🚩 Nouveau Recours sur Note soumis"
            msg_notif = f"L'étudiant {etudiant.nom_complet} ({etudiant.matricule}) a déposé un recours pour {evaluation.titre}."
            site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')

            for dest in destinataires:
                Notification.objects.create(
                    utilisateur=dest,
                    type='AVERTISSEMENT',
                    titre=titre_notif,
                    message=msg_notif,
                    lien='/notes/recours/'
                )
                if dest.email:
                    try:
                        send_mail(
                            subject=f"{getattr(settings, 'EMAIL_SUBJECT_PREFIX', '[IAI-Cameroun] ')}{titre_notif}",
                            message=f"Bonjour {dest.get_full_name() or dest.username},\n\n{msg_notif}\n\nConsultez les recours : {site_url}/notes/recours/",
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[dest.email],
                            fail_silently=True
                        )
                    except Exception:
                        pass
                tel = getattr(dest, 'telephone', '') or getattr(dest, 'contact', '')
                if tel:
                    try:
                        WhatsAppService.envoyer_message(
                            tel,
                            f"*IAI-CAMEROUN (Douala)* 🚩\n*Nouveau Recours sur Note*\n\nBonjour {dest.get_full_name() or dest.username},\n{msg_notif}\n\nLien : {site_url}/notes/recours/"
                        )
                    except Exception:
                        pass

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


@login_required
def liste_bordereaux(request):
    """Affiche la liste des classes pour lesquelles générer un bordereau"""
    role = getattr(request.user, 'type_utilisateur', None)
    if role not in ('CHEF_ETUDES', 'ADMIN_SYSTEME') and not request.user.is_superuser:
        messages.error(request, "❌ Accès réservé au Chef des Études.")
        return redirect('tableau_bord:tableau_bord')

    from apps.etudiants.models import Classe, AnneeAcademique
    annee_active = AnneeAcademique.get_active()
    classes = Classe.objects.filter(annee_academique=annee_active, est_active=True).order_by('nom')

    context = {
        'classes': classes,
        'annee_active': annee_active,
        'titre': 'Bordereaux de Notes'
    }
    return render(request, 'notes/bordereau/liste_salles.html', context)


@login_required
def generer_bordereau(request, salle_id):
    """Génère le bordereau de notes officiel d'une classe regroupé par UE"""
    role = getattr(request.user, 'type_utilisateur', None)
    if role not in ('CHEF_ETUDES', 'ADMIN_SYSTEME') and not request.user.is_superuser:
        messages.error(request, "❌ Accès réservé au Chef des Études.")
        return redirect('tableau_bord:tableau_bord')

    from apps.etudiants.models import Classe
    from apps.notes.models import UniteEnseignement, Matiere, Note, TypeEvaluation
    
    classe = get_object_or_404(Classe, pk=salle_id)
    etudiants = classe.etudiants.filter(statut__in=['INSCRIT', 'ACTIF']).order_by('nom', 'prenom')
    filiere = classe.filiere
    niveau = classe.niveau
    annee_academique = classe.annee_academique

    # Récupérer les UEs associées à la filière et au niveau
    ues = list(UniteEnseignement.objects.filter(filiere=filiere, niveau=niveau).prefetch_related('matieres'))
    
    # Récupérer toutes les matières de la filière/niveau
    from apps.notes.models import Cours
    cours_classe = Cours.objects.filter(filiere=filiere, niveau=niveau, annee_academique=annee_academique.code)
    matieres_ids = cours_classe.values_list('matiere_id', flat=True)
    matieres_toutes = list(Matiere.objects.filter(id__in=matieres_ids))

    # Associer les matières sans UE à une UE virtuelle pour ne rien perdre
    matieres_avec_ue = []
    for ue in ues:
        matieres_avec_ue.extend(ue.matieres.all())
    
    matieres_sans_ue = [m for m in matieres_toutes if m not in matieres_avec_ue]
    
    if matieres_sans_ue:
        ue_virtuelle = UniteEnseignement(code='UE_AUTRES', nom='Matières Fondamentales / Optionnelles')
        # On attache temporairement dans le code
        ue_virtuelle.temp_matieres = matieres_sans_ue
        ues.append(ue_virtuelle)

    # Récupérer les types d'évaluations
    type_cc = TypeEvaluation.objects.filter(code='CC').first()
    type_exam = TypeEvaluation.objects.filter(code='EXAM').first()
    type_ratt = TypeEvaluation.objects.filter(code='RATT').first()
    if not type_ratt:
        # Créer à la volée le type Rattrapage s'il n'existe pas en base de données
        type_ratt = TypeEvaluation.objects.create(code='RATT', nom='Rattrapage', coefficient_default=1.00)

    # Pré-charger toutes les notes des étudiants pour cette classe
    from django.db.models import Q
    evaluations_cours = []
    for c in cours_classe:
        evaluations_cours.extend(c.evaluations.all())
        
    notes_queryset = Note.objects.filter(
        etudiant__in=etudiants,
        evaluation__in=evaluations_cours,
        est_validee=True
    ).select_related('etudiant', 'evaluation', 'evaluation__cours', 'evaluation__cours__matiere', 'evaluation__type_evaluation')

    # Structurer les notes pour un accès rapide : dict[etudiant_id][matiere_code][type_code] = valeur
    notes_dict = {}
    for note in notes_queryset:
        et_id = note.etudiant_id
        mat_code = note.evaluation.cours.matiere.code
        type_code = note.evaluation.type_evaluation.code
        
        if et_id not in notes_dict:
            notes_dict[et_id] = {}
        if mat_code not in notes_dict[et_id]:
            notes_dict[et_id][mat_code] = {}
        notes_dict[et_id][mat_code][type_code] = float(note.valeur)

    # Construire la grille des résultats par étudiant
    resultats_etudiants = []
    for index, etudiant in enumerate(etudiants, 1):
        et_id = etudiant.id
        et_notes = notes_dict.get(et_id, {})
        
        detail_etudiant = {
            'index': index,
            'etudiant': etudiant,
            'ues': [],
            'total_points': 0.0,
            'total_coefficients': 0.0,
            'credits_capitalises': 0,
            'moyenne_generale': 0.0,
            'decision': 'Ajourné',
            'mention': 'Insuffisant'
        }

        for ue in ues:
            matieres_ue = getattr(ue, 'temp_matieres', ue.matieres.all())
            ue_notes = []
            ue_total_points = 0.0
            ue_total_coefficients = 0.0
            
            for mat in matieres_ue:
                coef = float(mat.credit)  # Le crédit fait office de coefficient pour le calcul de moyenne d'UE
                mat_n = et_notes.get(mat.code, {})
                
                cc_val = mat_n.get('CC')
                exam_val = mat_n.get('EXAM')
                ratt_val = mat_n.get('RATT')
                
                # Règle de calcul : Rattrapage écrase et remplace Examen
                exam_envisage = exam_val
                if exam_envisage is None:
                    exam_envisage = 0.0
                if ratt_val is not None:
                    exam_envisage = ratt_val
                
                cc_envisage = cc_val if cc_val is not None else 0.0
                
                # Calcul de la note finale : (CC * 40% + EXAM * 60%)
                if cc_val is None and exam_val is None and ratt_val is None:
                    note_finale = 0.0
                else:
                    note_finale = (cc_envisage * 0.4) + (exam_envisage * 0.6)
                
                note_finale = round(note_finale, 2)
                
                ue_notes.append({
                    'matiere': mat,
                    'note': note_finale,
                    'note_format': f"{note_finale:.1f}".replace('.', ',') if (cc_val is not None or exam_val is not None or ratt_val is not None) else "0,0"
                })
                
                ue_total_points += note_finale * coef
                ue_total_coefficients += coef
                
                if note_finale >= 10.0:
                    detail_etudiant['credits_capitalises'] += mat.credit

            # Calcul moyenne UE
            moyenne_ue = 0.0
            if ue_total_coefficients > 0:
                moyenne_ue = round(ue_total_points / ue_total_coefficients, 3)
                
            ue_mention = "V" if moyenne_ue >= 10.0 else "NV"
            
            detail_etudiant['ues'].append({
                'ue': ue,
                'notes_matieres': ue_notes,
                'moyenne': moyenne_ue,
                'moyenne_format': f"{moyenne_ue:.3f}".replace('.', ','),
                'mention': ue_mention
            })
            
            detail_etudiant['total_points'] += ue_total_points
            detail_etudiant['total_coefficients'] += ue_total_coefficients

        # Moyenne générale
        moyenne_g = 0.0
        if detail_etudiant['total_coefficients'] > 0:
            moyenne_g = round(detail_etudiant['total_points'] / detail_etudiant['total_coefficients'], 4)
            
        detail_etudiant['moyenne_generale'] = moyenne_g
        detail_etudiant['moyenne_format'] = f"{moyenne_g:.4f}".replace('.', ',')
        
        # Décision et mention générale
        if moyenne_g >= 10.0:
            detail_etudiant['decision'] = 'Admis'
            if moyenne_g >= 16.0:
                detail_etudiant['mention'] = 'Très Bien'
            elif moyenne_g >= 14.0:
                detail_etudiant['mention'] = 'Bien'
            elif moyenne_g >= 12.0:
                detail_etudiant['mention'] = 'Assez Bien'
            else:
                detail_etudiant['mention'] = 'Passable'
        else:
            detail_etudiant['decision'] = 'Ajourné'
            detail_etudiant['mention'] = 'Insuffisant'
            
        resultats_etudiants.append(detail_etudiant)

    # Calcul des rangs
    resultats_etudiants.sort(key=lambda x: x['moyenne_generale'], reverse=True)
    for rang, det in enumerate(resultats_etudiants, 1):
        det['rang'] = rang

    # Restaurer l'ordre alphabétique pour l'affichage final
    resultats_etudiants.sort(key=lambda x: (x['etudiant'].nom, x['etudiant'].prenom))

    # Calcul des statistiques globales du bordereau
    stats_bordereau = {
        'moyennes_matieres': {},
        'taux_reussite': 0.0
    }
    if resultats_etudiants:
        admis_count = sum(1 for d in resultats_etudiants if d['decision'] == 'Admis')
        stats_bordereau['taux_reussite'] = round((admis_count / len(resultats_etudiants)) * 100, 1)

    from django.utils import timezone
    context = {
        'classe': classe,
        'ues': ues,
        'resultats': resultats_etudiants,
        'stats': stats_bordereau,
        'date_generation': timezone.now(),
        'titre': f"Bordereau de notes {classe.nom}"
    }
    return render(request, 'notes/bordereau/detail_bordereau.html', context)


@login_required
def diffuser_resultats(request, salle_id):
    """Envoie par e-mail les résultats individuels et sécurisés de chaque étudiant"""
    role = getattr(request.user, 'type_utilisateur', None)
    if role not in ('CHEF_ETUDES', 'ADMIN_SYSTEME') and not request.user.is_superuser:
        messages.error(request, "❌ Accès réservé au Chef des Études.")
        return redirect('tableau_bord:tableau_bord')

    from apps.etudiants.models import Classe
    from django.core import signing
    from django.core.mail import send_mail
    from django.conf import settings
    from django.urls import reverse
    
    classe = get_object_or_404(Classe, pk=salle_id)
    etudiants = classe.etudiants.filter(statut__in=['INSCRIT', 'ACTIF'])
    
    if request.method == 'POST':
        email_sent = 0
        site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
        
        for etudiant in etudiants:
            if not etudiant.email and etudiant.utilisateur and etudiant.utilisateur.email:
                etudiant.email = etudiant.utilisateur.email
                
            if etudiant.email:
                # Génération du jeton signé sécurisé
                token_data = {
                    'etudiant_id': etudiant.id,
                    'salle_id': classe.id,
                    'annee_code': classe.annee_academique.code
                }
                token = signing.dumps(token_data)
                
                url_consultation = f"{site_url}{reverse('notes:consulter_resultat_individuel', kwargs={'token': token})}"
                
                sujet = f"Publication de vos résultats — {classe.annee_academique.code}"
                message_html = f"""
                <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e5e7eb; border-radius: 16px; padding: 24px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
                    <div style="text-align: center; margin-bottom: 24px;">
                        <h2 style="color: #15803d; margin: 0; text-transform: uppercase; font-size: 20px;">IAI-Cameroun</h2>
                        <p style="color: #6b7280; font-size: 12px; margin: 4px 0 0 0;">Centre d'Excellence Technologique Paul Biya</p>
                    </div>
                    
                    <div style="margin-bottom: 24px;">
                        <p style="font-size: 16px; font-weight: bold; color: #1f2937; margin: 0 0 12px 0;">Bonjour {etudiant.get_nom_complet()},</p>
                        <p style="font-size: 14px; color: #4b5563; line-height: 1.5; margin: 0 0 16px 0;">Les résultats officiels du semestre pour la classe de <strong>{classe.nom}</strong> ont été publiés par le Chef des Études.</p>
                        <p style="font-size: 14px; color: #4b5563; line-height: 1.5; margin: 0 0 16px 0;">Pour consulter et télécharger votre relevé de notes individuel de manière 100% sécurisée, veuillez cliquer sur le bouton ci-dessous :</p>
                    </div>
                    
                    <div style="text-align: center; margin-bottom: 24px;">
                        <a href="{url_consultation}" style="display: inline-block; background: linear-gradient(to right, #15803d, #16a34a); color: white; font-weight: bold; text-decoration: none; padding: 12px 24px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(22, 163, 74, 0.2); font-size: 14px;">Consulter mes Notes</a>
                    </div>
                    
                    <div style="border-top: 1px solid #f3f4f6; pt: 16px; text-align: center;">
                        <p style="font-size: 11px; color: #9ca3af; margin: 12px 0 0 0;">Ce lien de consultation est personnel, unique et sécurisé. Ne le partagez avec personne.</p>
                        <p style="font-size: 11px; color: #9ca3af; margin: 4px 0 0 0;">© 2026 IAI-Cameroun Douala — Tous droits réservés.</p>
                    </div>
                </div>
                """
                
                # Envoi de l'e-mail
                send_mail(
                    sujet,
                    f"Bonjour {etudiant.get_nom_complet()},\n\nVos résultats de {classe.nom} sont disponibles. Veuillez vous connecter ou suivre ce lien sécurisé pour les consulter : {url_consultation}",
                    settings.DEFAULT_FROM_EMAIL,
                    [etudiant.email],
                    html_message=message_html,
                    fail_silently=True
                )
                email_sent += 1
                
        messages.success(request, f"✉️ Résultats diffusés avec succès ! {email_sent} e-mail(s) sécurisé(s) envoyé(s) aux étudiants de {classe.nom}.")
        return redirect('notes:generer_bordereau', salle_id=classe.id)
        
    return redirect('notes:liste_bordereaux')


def consulter_resultat_individuel(request, token):
    """Permet à un étudiant d'accéder de manière sécurisée et confidentielle à son propre relevé"""
    from django.core import signing
    from apps.etudiants.models import Classe, Etudiant
    from apps.notes.models import UniteEnseignement, Matiere, Note, TypeEvaluation
    
    try:
        # Décoder le token sécurisé
        token_data = signing.loads(token, max_age=86400 * 30)  # Validité de 30 jours
        etudiant_id = token_data['etudiant_id']
        salle_id = token_data['salle_id']
    except (signing.SignatureExpired, signing.BadSignature):
        messages.error(request, "❌ Lien de consultation expiré ou invalide. Veuillez contacter le secrétariat.")
        return redirect('tableau_bord:tableau_bord')

    etudiant = get_object_or_404(Etudiant, pk=etudiant_id)
    classe = get_object_or_404(Classe, pk=salle_id)
    filiere = classe.filiere
    niveau = classe.niveau
    annee_academique = classe.annee_academique

    # Récupérer les UEs et les matières
    ues = list(UniteEnseignement.objects.filter(filiere=filiere, niveau=niveau).prefetch_related('matieres'))
    from apps.notes.models import Cours
    cours_classe = Cours.objects.filter(filiere=filiere, niveau=niveau, annee_academique=annee_academique.code)
    matieres_ids = cours_classe.values_list('matiere_id', flat=True)
    matieres_toutes = list(Matiere.objects.filter(id__in=matieres_ids))

    matieres_avec_ue = []
    for ue in ues:
        matieres_avec_ue.extend(ue.matieres.all())
    
    matieres_sans_ue = [m for m in matieres_toutes if m not in matieres_avec_ue]
    if matieres_sans_ue:
        ue_virtuelle = UniteEnseignement(code='UE_AUTRES', nom='Matières Complémentaires')
        ue_virtuelle.temp_matieres = matieres_sans_ue
        ues.append(ue_virtuelle)

    # Récupérer les notes de cet étudiant spécifique
    evaluations_cours = []
    for c in cours_classe:
        evaluations_cours.extend(c.evaluations.all())
        
    notes_etudiant = Note.objects.filter(
        etudiant=etudiant,
        evaluation__in=evaluations_cours,
        est_validee=True
    ).select_related('evaluation', 'evaluation__cours', 'evaluation__cours__matiere', 'evaluation__type_evaluation')

    notes_dict = {}
    for note in notes_etudiant:
        mat_code = note.evaluation.cours.matiere.code
        type_code = note.evaluation.type_evaluation.code
        if mat_code not in notes_dict:
            notes_dict[mat_code] = {}
        notes_dict[mat_code][type_code] = float(note.valeur)

    # Calcul de la grille individuelle
    releve_ues = []
    total_points = 0.0
    total_coefficients = 0.0
    credits_capitalises = 0

    for ue in ues:
        matieres_ue = getattr(ue, 'temp_matieres', ue.matieres.all())
        ue_notes = []
        ue_total_points = 0.0
        ue_total_coefficients = 0.0
        
        for mat in matieres_ue:
            coef = float(mat.credit)
            mat_n = notes_dict.get(mat.code, {})
            
            cc_val = mat_n.get('CC')
            exam_val = mat_n.get('EXAM')
            ratt_val = mat_n.get('RATT')
            
            exam_envisage = exam_val if exam_val is not None else 0.0
            if ratt_val is not None:
                exam_envisage = ratt_val
            
            cc_envisage = cc_val if cc_val is not None else 0.0
            
            if cc_val is None and exam_val is None and ratt_val is None:
                note_finale = 0.0
            else:
                note_finale = (cc_envisage * 0.4) + (exam_envisage * 0.6)
                
            note_finale = round(note_finale, 2)
            
            ue_notes.append({
                'matiere': mat,
                'cc': cc_val,
                'exam': exam_val,
                'rattrapage': ratt_val,
                'note_finale': note_finale,
                'note_finale_format': f"{note_finale:.1f}".replace('.', ',')
            })
            
            ue_total_points += note_finale * coef
            ue_total_coefficients += coef
            
            if note_finale >= 10.0:
                credits_capitalises += mat.credit

        # Moyenne UE
        moyenne_ue = 0.0
        if ue_total_coefficients > 0:
            moyenne_ue = round(ue_total_points / ue_total_coefficients, 3)
            
        releve_ues.append({
            'ue': ue,
            'notes': ue_notes,
            'moyenne': moyenne_ue,
            'moyenne_format': f"{moyenne_ue:.3f}".replace('.', ','),
            'mention': 'V' if moyenne_ue >= 10.0 else 'NV'
        })
        
        total_points += ue_total_points
        total_coefficients += ue_total_coefficients

    # Moyenne Générale
    moyenne_generale = 0.0
    if total_coefficients > 0:
        moyenne_generale = round(total_points / total_coefficients, 4)

    # Déterminer la décision finale et mention
    decision = 'Ajourné'
    mention = 'Insuffisant'
    if moyenne_generale >= 10.0:
        decision = 'Admis'
        if moyenne_generale >= 16.0:
            mention = 'Très Bien'
        elif moyenne_generale >= 14.0:
            mention = 'Bien'
        elif moyenne_generale >= 12.0:
            mention = 'Assez Bien'
        else:
            mention = 'Passable'

    # Calculer le rang dans la classe pour ce semestre
    tous_etudiants = classe.etudiants.filter(statut__in=['INSCRIT', 'ACTIF'])
    classe_moyennes = []
    
    # Pour calculer le rang de manière équitable
    for et in tous_etudiants:
        et_n = Note.objects.filter(etudiant=et, evaluation__in=evaluations_cours, est_validee=True)
        et_dict = {}
        for n in et_n:
            mc = n.evaluation.cours.matiere.code
            tc = n.evaluation.type_evaluation.code
            if mc not in et_dict:
                et_dict[mc] = {}
            et_dict[mc][tc] = float(n.valeur)
            
        tp_sum = 0.0
        tc_sum = 0.0
        for u in ues:
            m_ue = getattr(u, 'temp_matieres', u.matieres.all())
            for mt in m_ue:
                c_cf = float(mt.credit)
                mt_n = et_dict.get(mt.code, {})
                cc = mt_n.get('CC')
                ex = mt_n.get('EXAM')
                rt = mt_n.get('RATT')
                ex_e = ex if ex is not None else 0.0
                if rt is not None:
                    ex_e = rt
                cc_e = cc if cc is not None else 0.0
                if cc is None and ex is None and rt is None:
                    nf = 0.0
                else:
                    nf = (cc_e * 0.4) + (ex_e * 0.6)
                tp_sum += round(nf, 2) * c_cf
                tc_sum += c_cf
        moy = tp_sum / tc_sum if tc_sum > 0 else 0.0
        classe_moyennes.append((et.id, moy))
        
    classe_moyennes.sort(key=lambda x: x[1], reverse=True)
    rang = 1
    for rank, (et_id, _) in enumerate(classe_moyennes, 1):
        if et_id == etudiant.id:
            rang = rank
            break

    from django.utils import timezone
    context = {
        'etudiant': etudiant,
        'classe': classe,
        'releve_ues': releve_ues,
        'moyenne_generale': moyenne_generale,
        'moyenne_format': f"{moyenne_generale:.4f}".replace('.', ','),
        'credits_capitalises': credits_capitalises,
        'total_coefficients': total_coefficients,
        'decision': decision,
        'mention': mention,
        'rang': rang,
        'effectif': len(tous_etudiants),
        'date_impression': timezone.now(),
        'titre': f"Relevé de notes - {etudiant.get_nom_complet()}"
    }
    return render(request, 'notes/bordereau/releve_individuel.html', context)


@login_required
def publier_bulletins_salle(request, salle_id):
    """Génère, archive et publie les bulletins officiels PDF pour toute la salle"""
    role = getattr(request.user, 'type_utilisateur', None)
    if role not in ('CHEF_ETUDES', 'ADMIN_SYSTEME') and not request.user.is_superuser:
        messages.error(request, "❌ Accès réservé au Chef des Études.")
        return redirect('tableau_bord:tableau_bord')

    from apps.etudiants.models import Classe
    from apps.notes.utils_pdf import generer_et_archiver_bulletin_pdf
    
    classe = get_object_or_404(Classe, pk=salle_id)
    etudiants = classe.etudiants.filter(statut__in=['INSCRIT', 'ACTIF'])

    if request.method == 'POST':
        publies = 0
        for etudiant in etudiants:
            generer_et_archiver_bulletin_pdf(etudiant, classe, user_valideur=request.user)
            publies += 1
            
        messages.success(
            request, 
            f"✅ {publies} bulletin(s) officiel(s) généré(s), archivé(s) en PDF et publié(s) sur le dashboard des étudiants de {classe.nom} !"
        )
        return redirect('notes:generer_bordereau', salle_id=classe.id)

    return redirect('notes:liste_bordereaux')


@login_required
def voir_bulletin_officiel(request, bulletin_id):
    """Affiche et permet de télécharger le bulletin officiel PDF d'un étudiant"""
    bulletin = get_object_or_404(Bulletin, pk=bulletin_id)
    user = request.user
    role = getattr(user, 'type_utilisateur', None)

    # Vérification des droits d'accès
    est_proprietaire = hasattr(user, 'etudiant_profile') and user.etudiant_profile.id == bulletin.etudiant.id
    est_admin_ou_chef = role in ('CHEF_ETUDES', 'ADMIN_SYSTEME', 'CHEF_SCOLARITE') or user.is_superuser

    if not est_proprietaire and not est_admin_ou_chef:
        messages.error(request, "❌ Accès refusé à ce bulletin officiel.")
        return redirect('tableau_bord:tableau_bord')

    if est_proprietaire and not bulletin.est_publie:
        messages.warning(request, "⚠️ Votre bulletin officiel n'a pas encore été publié par le Chef des Études.")
        return redirect('notes:mes_notes')

    from apps.etudiants.models import Classe
    classe = Classe.objects.filter(filiere=bulletin.etudiant.filiere, niveau=bulletin.etudiant.niveau).first()
    if not classe:
        classe = Classe(nom=f"{bulletin.etudiant.filiere.code} - L{bulletin.etudiant.niveau.numero}", filiere=bulletin.etudiant.filiere, niveau=bulletin.etudiant.niveau)

    from apps.notes.utils_pdf import structurer_donnees_bulletin
    context = structurer_donnees_bulletin(bulletin.etudiant, classe)
    context['bulletin'] = bulletin

    return render(request, 'notes/bulletin_officiel_pdf.html', context)


# ==============================================================================
# WORKFLOW CONFIDENTIEL DES FICHES D'ANONYMAT (PAR SALLE, FILIÈRE ET NIVEAU)
# ==============================================================================

@login_required
def dashboard_anonymat_enseignant(request):
    """
    Tableau de bord pour l'Enseignant : 
    1. Workflow PV CC par Salle, Filière et Niveau (Saisie multi-notes, moyenne, transmission confidentielle).
    2. Workflow d'Anonymat par Évaluation individuelle (SessionAnonymat, génération de codes, saisie anonyme).
    """
    from apps.etudiants.models import Filiere, Niveau, Etudiant
    from apps.cours.models import Salle, Matiere
    from .models import FicheNotesAnonymat, LigneFicheNotesAnonymat, TypeEvaluation, Evaluation, SessionAnonymat

    user = request.user
    fiches = FicheNotesAnonymat.objects.filter(enseignant=user).select_related('matiere', 'filiere', 'niveau', 'salle', 'type_evaluation')

    # Récupération de l'année académique active
    annee_active = AnneeAcademique.objects.filter(est_active=True).first()
    annee_courante = annee_active.code if annee_active else '2025-2026'
    annees_academiques = AnneeAcademique.objects.all()

    # Évaluations de l'enseignant (ou toutes si administrateur)
    if user.is_superuser or getattr(user, 'type_utilisateur', None) in ('ADMIN_SYSTEME', 'ADMIN_PEDAGOGIQUE'):
        evaluations_enseignant = Evaluation.objects.all().select_related('cours__matiere', 'cours__filiere', 'cours__niveau', 'type_evaluation', 'session_anonymat').order_by('-date_evaluation')
    else:
        evaluations_enseignant = Evaluation.objects.filter(cours__professeur=user).select_related('cours__matiere', 'cours__filiere', 'cours__niveau', 'type_evaluation', 'session_anonymat').order_by('-date_evaluation')

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'creer_fiche':
            matiere_id = request.POST.get('matiere_id')
            filiere_id = request.POST.get('filiere_id')
            niveau_id = request.POST.get('niveau_id')
            salle_id = request.POST.get('salle_id')
            type_eval_id = request.POST.get('type_eval_id')
            annee = request.POST.get('annee_academique') or annee_courante

            if not salle_id:
                messages.error(request, "❌ Le champ 'Salle Physique' est obligatoire.")
                return redirect('notes:dashboard_anonymat_enseignant')

            matiere = get_object_or_404(Matiere, pk=matiere_id)
            filiere = get_object_or_404(Filiere, pk=filiere_id)
            niveau = get_object_or_404(Niveau, pk=niveau_id)
            salle = get_object_or_404(Salle, pk=salle_id)
            type_eval = get_object_or_404(TypeEvaluation, pk=type_eval_id)

            # Si le type d'évaluation est Examen ou Rattrapage, forcer automatiquement le mode DEVOIR_SUR_TABLE
            if type_eval.code in ['EXAM', 'EXAMEN', 'RATT']:
                mode_fiche = 'DEVOIR_SUR_TABLE'
            else:
                mode_fiche = request.POST.get('mode_fiche', 'EXPOSE_TP_TD')

            # Contrôle d'unicité : un seul PV par salle/matière/type d'évaluation/année
            fiche_existante = FicheNotesAnonymat.objects.filter(
                matiere=matiere,
                filiere=filiere,
                niveau=niveau,
                salle=salle,
                type_evaluation=type_eval,
                annee_academique=annee
            ).first()

            if fiche_existante:
                messages.warning(
                    request,
                    f"⚠️ Un PV / Fiche de notes pour {type_eval.nom} en {matiere.code} ({filiere.code} L{niveau.numero}) "
                    f"existe déjà dans la salle {salle.nom}. Vous avez été redirigé vers celui-ci."
                )
                return redirect('notes:saisie_fiche_enseignant', fiche_id=fiche_existante.id)

            fiche = FicheNotesAnonymat.objects.create(
                matiere=matiere,
                filiere=filiere,
                niveau=niveau,
                salle=salle,
                type_evaluation=type_eval,
                mode_fiche=mode_fiche,
                annee_academique=annee,
                enseignant=user,
                enseignant_nom=user.get_full_name() or user.username,
                cree_par=user,
                statut='BROUILLON'
            )

            # Pré-générer les lignes
            etudiants_liste = list(Etudiant.objects.filter(filiere=filiere, niveau=niveau).order_by('nom', 'prenom'))
            if mode_fiche == 'EXPOSE_TP_TD' and etudiants_liste:
                for i, et in enumerate(etudiants_liste, start=1):
                    LigneFicheNotesAnonymat.objects.create(
                        fiche=fiche,
                        numero_anonymat=f"A{i}",
                        etudiant=et
                    )
            else:
                nb_lignes = len(etudiants_liste) if etudiants_liste else 24
                for i in range(1, nb_lignes + 1):
                    LigneFicheNotesAnonymat.objects.create(
                        fiche=fiche,
                        numero_anonymat=f"A{i}"
                    )

            messages.success(request, f"✅ Fiche de notes créée en mode '{fiche.get_mode_fiche_display()}' pour {matiere.nom} ({filiere.code} L{niveau.numero}) - Salle {salle.nom}.")
            return redirect('notes:saisie_fiche_enseignant', fiche_id=fiche.id)

    # Séparation stricte et mutuellement exclusive entre Section 1 (CC) et Section 2 (Examen/Rattrapage)
    fiches_cc = fiches.filter(Q(type_evaluation__code='CC') | Q(mode_fiche='EXPOSE_TP_TD')).exclude(type_evaluation__code__in=['EXAM', 'EXAMEN', 'RATT'])
    fiches_exam = fiches.exclude(id__in=fiches_cc.values_list('id', flat=True))

    context = {
        'fiches': fiches,
        'fiches_cc_brouillons': fiches_cc.filter(statut='BROUILLON'),
        'fiches_cc_transmises': fiches_cc.filter(statut__in=['TRANSMIS_CHEF_ANONYMAT', 'MATCH_EFFECTUE']),
        'fiches_cc_archives': fiches_cc.filter(statut__in=['TRANSMIS_CHEF_ETUDES', 'PV_GENERE', 'VALIDE', 'ARCHIVE']),

        'fiches_exam_brouillons': fiches_exam.filter(statut='BROUILLON'),
        'fiches_exam_transmises': fiches_exam.filter(statut__in=['TRANSMIS_CHEF_ANONYMAT', 'MATCH_EFFECTUE']),
        'fiches_exam_archives': fiches_exam.filter(statut__in=['TRANSMIS_CHEF_ETUDES', 'PV_GENERE', 'VALIDE', 'ARCHIVE']),

        'evaluations_enseignant': evaluations_enseignant,
        'annee_courante': annee_courante,
        'annees_academiques': annees_academiques,
        'filieres': Filiere.objects.all(),
        'niveaux': Niveau.objects.all(),
        'salles': Salle.objects.all(),
        'matieres': Matiere.objects.all(),
        'types_eval': TypeEvaluation.objects.filter(est_actif=True),
        'titre': "Mes Fiches d'Anonymat & Procès-Verbaux (Enseignant)"
    }
    return render(request, 'notes/anonymat/dashboard_enseignant.html', context)


@login_required
def saisie_fiche_enseignant(request, fiche_id):
    """
    Page de saisie / OCR pour l'enseignant.
    Permet de remplir (Code + Note) et de transmettre au Chef de l'Anonymat.
    Les Noms des étudiants ne sont PAS affichés à l'enseignant en mode Devoir sur Table.
    """
    from .models import FicheNotesAnonymat, LigneFicheNotesAnonymat
    from .ocr_anonymat_service import analyser_fiche_anonymat

    fiche = get_object_or_404(FicheNotesAnonymat, pk=fiche_id)

    if request.user.type_utilisateur == 'CHEF_ETUDES':
        messages.error(request, "Le Chef des Études ne consulte pas les fiches d'anonymat brutes. Seuls les Procès-Verbaux officiels de notes lui sont transmis.")
        return redirect('notes:liste_proces_verbaux')

    if request.method == 'POST':
        action = request.POST.get('action')

        def _sauvegarder_post():
            for key, value in request.POST.items():
                if key.startswith('code_'):
                    ligne_id = key.replace('code_', '')
                    code_val = value.strip()
                    try:
                        ligne = LigneFicheNotesAnonymat.objects.get(pk=ligne_id, fiche=fiche)
                        if code_val:
                            ligne.numero_anonymat = code_val

                        def _parse_val(val_str):
                            if not val_str or not val_str.strip():
                                return None
                            try:
                                v = float(val_str.replace(',', '.'))
                                if v > 20.0:
                                    return 20.0
                                elif v < 0.0:
                                    return 0.0
                                return v
                            except ValueError:
                                return None

                        n1 = _parse_val(request.POST.get(f'note1_{ligne_id}'))
                        n2 = _parse_val(request.POST.get(f'note2_{ligne_id}'))
                        n3 = _parse_val(request.POST.get(f'note3_{ligne_id}'))
                        n4 = _parse_val(request.POST.get(f'note4_{ligne_id}'))
                        n5 = _parse_val(request.POST.get(f'note5_{ligne_id}'))

                        note_unique = _parse_val(request.POST.get(f'note_{ligne_id}'))
                        if note_unique is not None and n1 is None:
                            n1 = note_unique
                            if fiche.mode_fiche == 'DEVOIR_SUR_TABLE':
                                ligne.note = note_unique

                        ligne.note_1 = n1
                        ligne.note_2 = n2
                        ligne.note_3 = n3
                        ligne.note_4 = n4
                        ligne.note_5 = n5
                        
                        ligne.calculer_moyenne_cc(imputer_zero_si_vide=True)
                        ligne.save()
                    except LigneFicheNotesAnonymat.DoesNotExist:
                        pass
            
            # Recalculer les moyennes de toutes les lignes sur le nombre d'évaluations global N_eval
            fiche.recalculer_toutes_les_moyennes()

        if action == 'enregistrer_notes':
            _sauvegarder_post()
            messages.success(request, "💾 Saisies et moyennes enregistrées avec succès.")
            return redirect('notes:saisie_fiche_enseignant', fiche_id=fiche.id)

        elif action == 'ajouter_ligne':
            # 1. Sauvegarder impérativement les saisies actuellement en cours dans le formulaire
            _sauvegarder_post()

            # 2. Récupérer le code de la dernière ligne et incrémenter de manière intelligente (ex: KB1 -> KB2)
            import re
            dernieres_lignes = list(fiche.lignes.order_by('id'))
            if dernieres_lignes and dernieres_lignes[-1].numero_anonymat:
                code_prec = dernieres_lignes[-1].numero_anonymat.strip()
                match = re.search(r'^(.*?)(0*\d+)$', code_prec)
                if match:
                    prefixe = match.group(1)
                    num_str = match.group(2)
                    num_val = int(num_str) + 1
                    nouveau_code = f"{prefixe}{str(num_val).zfill(len(num_str))}"
                else:
                    nouveau_code = f"{code_prec}-1"
            else:
                nouveau_code = "A1"

            LigneFicheNotesAnonymat.objects.create(
                fiche=fiche,
                numero_anonymat=nouveau_code
            )
            messages.success(request, f"➕ Ligne {nouveau_code} ajoutée (saisies précédentes conservées).")
            return redirect('notes:saisie_fiche_enseignant', fiche_id=fiche.id)

        elif action == 'supprimer_ligne':
            ligne_id = request.POST.get('ligne_id')
            if ligne_id:
                LigneFicheNotesAnonymat.objects.filter(pk=ligne_id, fiche=fiche).delete()
                messages.success(request, "🗑️ Ligne supprimée.")
            return redirect('notes:saisie_fiche_enseignant', fiche_id=fiche.id)

        elif action == 'importer_ocr':
            fichier = request.FILES.get('fichier_ocr')
            if fichier:
                fiche.fichier_fiche = fichier
                fiche.save()
                
                resultats = analyser_fiche_anonymat(fiche.fichier_fiche.path, mode_enseignant=True)
                if resultats:
                    for item in resultats:
                        code = item.get('code_anonymat')
                        moyenne = item.get('moyenne_cc', item.get('note'))
                        n1 = item.get('note_1')
                        n2 = item.get('note_2')
                        n3 = item.get('note_3')
                        n4 = item.get('note_4')
                        n5 = item.get('note_5')

                        ligne, created = LigneFicheNotesAnonymat.objects.get_or_create(
                            fiche=fiche,
                            numero_anonymat=code,
                            defaults={
                                'note': moyenne,
                                'note_1': n1,
                                'note_2': n2,
                                'note_3': n3,
                                'note_4': n4,
                                'note_5': n5,
                                'moyenne_cc': moyenne
                            }
                        )
                        if not created:
                            ligne.note_1 = n1
                            ligne.note_2 = n2
                            ligne.note_3 = n3
                            ligne.note_4 = n4
                            ligne.note_5 = n5
                            ligne.calculer_moyenne_cc(imputer_zero_si_vide=True)
                            ligne.save()
                    messages.success(request, f"✨ OCR exécuté : {len(resultats)} ligne(s) de note CC extraite(s) avec succès !")
                else:
                    messages.warning(request, "⚠️ OCR terminé, aucune note détectée. Saisie manuelle requise.")
            return redirect('notes:saisie_fiche_enseignant', fiche_id=fiche.id)

        elif action == 'transmettre_chef_anonymat':
            from django.db.models import Q
            lignes = fiche.lignes.all()

            if not lignes.exists():
                messages.error(request, "❌ Transmission impossible : La fiche d'anonymat est vide (aucune ligne).")
                return redirect('notes:saisie_fiche_enseignant', fiche_id=fiche.id)

            # S'assurer que toutes les lignes ont une moyenne calculée (cases vides imputées à 0)
            for ligne in lignes:
                if ligne.note is None or ligne.moyenne_cc is None:
                    ligne.calculer_moyenne_cc(imputer_zero_si_vide=True)
                    ligne.save()

            lignes_sans_code = lignes.filter(Q(numero_anonymat__isnull=True) | Q(numero_anonymat='')).count()

            if lignes_sans_code > 0:
                messages.error(
                    request,
                    f"❌ Transmission impossible : {lignes_sans_code} ligne(s) ne possèdent pas de code d'anonymat valide."
                )
                return redirect('notes:saisie_fiche_enseignant', fiche_id=fiche.id)

            # Valider et transmettre au Chef Anonymat
            fiche.statut = 'TRANSMIS_CHEF_ANONYMAT'
            fiche.date_transmission_anonymat = timezone.now()
            fiche.save()

            # --- Notification du Chef de l'Anonymat ---
            from django.conf import settings
            from django.contrib.auth import get_user_model
            from apps.tableau_bord.models import Notification
            from apps.tableau_bord.whatsapp_service import WhatsAppService
            from django.core.mail import send_mail

            User = get_user_model()
            chefs_anonymat = User.objects.filter(
                type_utilisateur__in=['CHEF_ANONYMAT', 'ADMIN_PEDAGOGIQUE'],
                est_actif=True
            )
            if not chefs_anonymat.exists():
                chefs_anonymat = User.objects.filter(is_superuser=True, est_actif=True)

            titre_notif = f"📨 Nouvelle Fiche/PV d'Anonymat reçue"
            nom_matiere = fiche.matiere.nom if hasattr(fiche, 'matiere') and fiche.matiere else "Évaluation"
            nom_classe = fiche.salle.code if hasattr(fiche, 'salle') and fiche.salle else "Classe"
            msg_notif = f"Le Procès-Verbal / Fiche d'Anonymat pour {nom_matiere} ({nom_classe}) a été transmis confidentiellement."
            site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')

            for chef in chefs_anonymat:
                # 1. Notification In-App Dashboard
                Notification.objects.create(
                    utilisateur=chef,
                    type='INFO',
                    titre=titre_notif,
                    message=msg_notif,
                    lien='/notes/anonymat/chef/'
                )
                # 2. Notification Email
                if chef.email:
                    try:
                        send_mail(
                            subject=f"{getattr(settings, 'EMAIL_SUBJECT_PREFIX', '[IAI-Cameroun] ')}{titre_notif}",
                            message=f"Bonjour {chef.get_full_name() or chef.username},\n\n{msg_notif}\n\nConsultez votre espace Chef Anonymat : {site_url}/notes/anonymat/chef/",
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[chef.email],
                            fail_silently=True
                        )
                    except Exception:
                        pass
                # 3. Notification WhatsApp
                tel = getattr(chef, 'telephone', '') or getattr(chef, 'contact', '')
                if tel:
                    try:
                        WhatsAppService.envoyer_message(
                            tel,
                            f"*IAI-CAMEROUN (Douala)* 🔐\n*Fiche d'Anonymat Transmise*\n\nBonjour {chef.get_full_name() or chef.username},\n{msg_notif}\n\nEspace Anonymat : {site_url}/notes/anonymat/chef/"
                        )
                    except Exception:
                        pass

            messages.success(request, "📨 Procès-Verbal de CC transmis confidentiellement au Chef de l'Anonymat !")
            return redirect('notes:dashboard_anonymat_enseignant')

    context = {
        'fiche': fiche,
        'lignes': fiche.lignes.all().order_by('id'),
        'titre': f"Saisie Anonymat - {fiche.matiere.nom}"
    }
    return render(request, 'notes/anonymat/saisie_enseignant.html', context)


@login_required
def dashboard_chef_anonymat(request):
    """
    Tableau de bord du Chef de l'Anonymat :
    Réception des fiches transmises par les enseignants, matching et génération du PV.
    """
    role = getattr(request.user, 'type_utilisateur', None)
    if role not in ('CHEF_ANONYMAT', 'ADMIN_PEDAGOGIQUE', 'ADMIN_SYSTEME') and not request.user.is_superuser:
        messages.error(request, "❌ Accès réservé au Chef de l'Anonymat.")
        return redirect('tableau_bord:tableau_bord')

    from .models import FicheNotesAnonymat
    from apps.etudiants.models import Filiere, Niveau

    fiches = FicheNotesAnonymat.objects.exclude(statut='BROUILLON').select_related('matiere', 'filiere', 'niveau', 'salle', 'type_evaluation', 'enseignant')

    # Filtres par Salle, Filière, Niveau
    filiere_id = request.GET.get('filiere')
    niveau_id = request.GET.get('niveau')
    if filiere_id:
        fiches = fiches.filter(filiere_id=filiere_id)
    if niveau_id:
        fiches = fiches.filter(niveau_id=niveau_id)

    context = {
        'fiches': fiches,
        'filieres': Filiere.objects.all(),
        'niveaux': Niveau.objects.all(),
        'titre': "Tableau de Bord - Chef de l'Anonymat"
    }
    return render(request, 'notes/anonymat/dashboard_chef_anonymat.html', context)


@login_required
def matching_anonymat_chef(request, fiche_id):
    """
    Interface du Chef de l'Anonymat :
    1. Matching manuel ou OCR (3 colonnes: Code + Note + NOMS) avec les étudiants réels.
    2. Génération du Procès-Verbal de Notes officiel.
    3. Transmission confidentielle au Chef des Études.
    """
    role = getattr(request.user, 'type_utilisateur', None)
    if role not in ('CHEF_ANONYMAT', 'ADMIN_PEDAGOGIQUE', 'ADMIN_SYSTEME') and not request.user.is_superuser:
        messages.error(request, "❌ Accès réservé au Chef de l'Anonymat.")
        return redirect('tableau_bord:tableau_bord')

    from .models import FicheNotesAnonymat, LigneFicheNotesAnonymat, ProcesVerbalNotes
    from apps.etudiants.models import Etudiant
    from .ocr_anonymat_service import analyser_fiche_anonymat, effectuer_matching_etudiants

    fiche = get_object_or_404(FicheNotesAnonymat, pk=fiche_id)
    etudiants_classe = Etudiant.objects.filter(filiere=fiche.filiere, niveau=fiche.niveau).order_by('nom', 'prenom')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'enregistrer_matching':
            selections = {}
            comptage_etudiants = {}

            # 1. Analyser toutes les sélections et vérifier les doublons
            for ligne in fiche.lignes.all():
                etudiant_id = request.POST.get(f'etudiant_{ligne.id}')
                if etudiant_id and etudiant_id.strip():
                    et_id = int(etudiant_id)
                    selections[ligne.id] = et_id
                    comptage_etudiants[et_id] = comptage_etudiants.get(et_id, 0) + 1

            # 2. Détecter les doublons
            doublons_ids = [et_id for et_id, count in comptage_etudiants.items() if count > 1]
            if doublons_ids:
                etudiants_doublons = Etudiant.objects.filter(id__in=doublons_ids)
                noms_doublons = ", ".join([f"{e.get_nom_complet()} ({e.matricule})" for e in etudiants_doublons])
                messages.error(
                    request, 
                    f"❌ Erreur de matching : Un étudiant ne peut pas être associé à plusieurs codes anonymes sur la même fiche ! "
                    f"Doublon(s) détecté(s) : {noms_doublons}."
                )
                return redirect('notes:matching_anonymat_chef', fiche_id=fiche.id)

            # 3. Enregistrer les correspondances et les notes modifiées par le Chef Anonymat
            for ligne in fiche.lignes.all():
                et_id = selections.get(ligne.id)
                ligne.etudiant_id = et_id
                
                note_str = request.POST.get(f'note_{ligne.id}')
                if note_str and note_str.strip():
                    try:
                        ligne.note = float(note_str.replace(',', '.'))
                    except ValueError:
                        pass
                ligne.save()

            fiche.statut = 'MATCH_EFFECTUE'
            fiche.save()

            from .services import actualiser_pv_unifie
            actualiser_pv_unifie(fiche.matiere, fiche.salle, fiche.filiere, fiche.niveau, request.user)

            messages.success(request, "✅ Matching Étudiants/Codes Anonymes et modifications de notes enregistrés avec succès.")
            return redirect('notes:matching_anonymat_chef', fiche_id=fiche.id)

        elif action == 'importer_ocr_complet':
            fichier = request.FILES.get('fichier_ocr_complet')
            if fichier:
                fiche.fichier_fiche = fichier
                fiche.save()

                # OCR mode complet (3 colonnes)
                resultats = analyser_fiche_anonymat(fiche.fichier_fiche.path, mode_enseignant=False)
                if resultats:
                    correspondances = effectuer_matching_etudiants(resultats, etudiants_classe)
                    for item in correspondances:
                        code = item.get('code_anonymat')
                        note = item.get('note')
                        nom_m = item.get('nom_manuscrit')
                        et_trouve = item.get('etudiant')

                        ligne, created = LigneFicheNotesAnonymat.objects.get_or_create(
                            fiche=fiche,
                            numero_anonymat=code,
                            defaults={
                                'note': note,
                                'nom_manuscrit_detecte': nom_m,
                                'etudiant': et_trouve
                            }
                        )
                        if not created:
                            ligne.note = note
                            ligne.nom_manuscrit_detecte = nom_m
                            if et_trouve:
                                ligne.etudiant = et_trouve
                            ligne.save()

                    fiche.statut = 'MATCH_EFFECTUE'
                    fiche.save()

                    from .services import actualiser_pv_unifie
                    actualiser_pv_unifie(fiche.matiere, fiche.salle, fiche.filiere, fiche.niveau, request.user)

                    messages.success(request, f"🔍 Matching OCR complet réussi sur {len(correspondances)} lignes !")
                else:
                    messages.warning(request, "⚠️ OCR incomplet, veuillez vérifier les lignes ci-dessous.")
            return redirect('notes:matching_anonymat_chef', fiche_id=fiche.id)

        elif action == 'generer_et_transmettre_pv':
            from .services import actualiser_pv_unifie, transmettre_pv_au_chef_etudes

            pv = actualiser_pv_unifie(
                matiere=fiche.matiere,
                salle=fiche.salle,
                filiere=fiche.filiere,
                niveau=fiche.niveau,
                user=request.user
            )
            transmettre_pv_au_chef_etudes(pv.id, request.user)

            fiche.statut = 'TRANSMIS_CHEF_ETUDES'
            fiche.date_transmission_etudes = timezone.now()
            fiche.save()

            messages.success(
                request, 
                "📋 Procès-Verbal de Notes unifié (CC, Examen, Rattrapage) dûment calculé et transmis au Chef des Études ! "
                "Les notes ont été publiées pour les étudiants et les absences de note ont été imputées à 0.00."
            )
            return redirect('notes:dashboard_chef_anonymat')

    context = {
        'fiche': fiche,
        'lignes': fiche.lignes.all().select_related('etudiant'),
        'etudiants_classe': etudiants_classe,
        'pv': getattr(fiche, 'proces_verbal', None),
        'titre': f"Matching & PV Notes - {fiche.matiere.nom}"
    }
    return render(request, 'notes/anonymat/matching_chef.html', context)


@login_required
def supprimer_fiche_enseignant(request, fiche_id):
    """
    Supprime une fiche d'anonymat (par l'Enseignant).
    Impossible si le statut est 'TRANSMIS_CHEF_ETUDES'.
    """
    fiche = get_object_or_404(FicheNotesAnonymat, pk=fiche_id)

    if fiche.statut == 'TRANSMIS_CHEF_ETUDES' and not request.user.is_superuser:
        messages.error(request, "❌ Action impossible : Cette fiche a déjà été transmise au Chef des Études et ne peut plus être supprimée par l'enseignant.")
        return redirect('notes:dashboard_anonymat_enseignant')

    if request.user == fiche.enseignant or request.user.is_superuser or getattr(request.user, 'type_utilisateur', None) == 'ADMIN_SYSTEME':
        fiche.delete()
        messages.success(request, "🗑️ Fiche d'anonymat supprimée. Elle a été automatiquement retirée du Chef de l'Anonymat.")
    else:
        messages.error(request, "❌ Action non autorisée.")
    return redirect('notes:dashboard_anonymat_enseignant')


@login_required
def supprimer_fiche_chef_anonymat(request, fiche_id):
    """
    Supprime une fiche / PV d'anonymat (par le Chef de l'Anonymat).
    La suppression retire le PV chez le Chef de l'Anonymat ET chez le Chef des Études.
    """
    role = getattr(request.user, 'type_utilisateur', None)
    if role not in ('CHEF_ANONYMAT', 'ADMIN_PEDAGOGIQUE', 'ADMIN_SYSTEME') and not request.user.is_superuser:
        messages.error(request, "❌ Accès réservé au Chef de l'Anonymat.")
        return redirect('tableau_bord:tableau_bord')

    fiche = get_object_or_404(FicheNotesAnonymat, pk=fiche_id)
    fiche.delete()
    messages.success(request, "🗑️ Procès-Verbal / Fiche d'anonymat supprimé(e). Retiré(e) également du Chef des Études.")
    return redirect('notes:dashboard_chef_anonymat')


@login_required
def detail_pv(request, pk):
    """Affiche le Procès-Verbal de Notes unifié d'une Matière (CC 40%, Examen 60%, Rattrapage, Note Finale)."""
    from .models import ProcesVerbalNotes
    pv = get_object_or_404(ProcesVerbalNotes, pk=pk)
    pv.actualiser_depuis_fiches_anonymat()

    lignes = pv.lignes.select_related('etudiant').order_by('etudiant__nom', 'etudiant__prenom')

    context = {
        'pv': pv,
        'lignes': lignes,
        'titre': f"Procès-Verbal - {pv.matiere.nom if pv.matiere else ''}"
    }
    return render(request, 'notes/detail_pv.html', context)


@login_required
def supprimer_pv(request, pk):
    """Supprime spécifiquement un Procès-Verbal de Notes."""
    pv = get_object_or_404(ProcesVerbalNotes, pk=pk)
    role = getattr(request.user, 'type_utilisateur', None)
    if role in ('CHEF_ANONYMAT', 'ADMIN_PEDAGOGIQUE', 'ADMIN_SYSTEME') or request.user.is_superuser:
        pv.delete()
        messages.success(request, "🗑️ Procès-Verbal de Notes supprimé définitivement (mis à jour chez le Chef des Études).")
    else:
        messages.error(request, "❌ Action non autorisée.")
    return redirect('notes:dashboard_chef_anonymat')


# ==================== BORDEREAUX DE NOTES MATRICIELS & DÉLIBÉRATION ====================

@login_required
def liste_bordereaux(request):
    """Liste des classes disponibles pour la génération des bordereaux de notes officiels."""
    from apps.etudiants.models import Classe, AnneeAcademique
    annee_active = AnneeAcademique.get_active()
    classes = Classe.objects.filter(est_active=True).select_related('filiere', 'niveau', 'annee_academique').order_by('filiere__code', 'niveau__numero', 'nom')
    
    context = {
        'classes': classes,
        'annee_active': annee_active,
        'titre': "Bordereaux de Notes & Délibérations Officiels"
    }
    return render(request, 'notes/liste_bordereaux.html', context)


@login_required
def generer_bordereau(request, salle_id):
    """
    Génère le Bordereau de Notes matriciel officiel (conforme au format Excel IAI-Cameroun)
    pour une classe (salle) et un semestre.
    Permet l'auto-remplissage fiable à partir des PVs transmis.
    """
    from apps.etudiants.models import Classe
    from .services_bordereau import calculer_bordereau_matrice
    from .services import remplir_bordereau_depuis_pv
    
    classe = get_object_or_404(Classe, pk=salle_id)
    semestre = int(request.GET.get('semestre', 1))
    
    if request.method == 'POST' and request.POST.get('action') == 'remplir_bordereau_depuis_pvs':
        res = remplir_bordereau_depuis_pv(classe, semestre=semestre, user=request.user)
        msg = f"✅ Bordereau synchronisé depuis les PVs validés : {len(res['remplis'])} matière(s) remplie(s) ({', '.join(res['remplis'])})."
        if res['en_attente']:
            msg += f" ⚠️ En attente de PV validé avec note finale pour : {', '.join(res['en_attente'])}."
        messages.info(request, msg)
        return redirect(reverse('notes:generer_bordereau', kwargs={'salle_id': classe.id}) + f"?semestre={semestre}")

    data_matrice = calculer_bordereau_matrice(classe, semestre=semestre)
    
    context = {
        'classe': classe,
        'semestre': semestre,
        'header': data_matrice['header'],
        'ues': data_matrice['ues'],
        'matieres_all': data_matrice['matieres_all'],
        'etudiants_rows': data_matrice['etudiants_rows'],
        'statistiques': data_matrice['statistiques'],
        'titre': f"Bordereau de Notes {classe.nom} - Semestre {semestre}"
    }
    return render(request, 'notes/bordereau_notes.html', context)


@login_required
def publier_bulletins_salle(request, salle_id):
    """
    Publie officiellement les bulletins semestriels de la classe et débloque l'accès individuel étudiant.
    """
    from apps.etudiants.models import Classe
    from .services_bordereau import publier_bulletins_classe
    
    classe = get_object_or_404(Classe, pk=salle_id)
    semestre = int(request.POST.get('semestre', request.GET.get('semestre', 1)))
    
    nb_publies = publier_bulletins_classe(classe, semestre, request.user)
    messages.success(request, f"✅ {nb_publies} bulletin(s) du Semestre {semestre} ont été publiés avec succès pour la classe {classe.nom}. Les étudiants peuvent désormais consulter leur résultat.")
    return redirect('notes:generer_bordereau', salle_id=classe.id)


@login_required
def voir_bulletin_officiel(request, bulletin_id):
    """Affiche le bulletin officiel certifié d'un étudiant avec QR code."""
    from .models import Bulletin
    from apps.etudiants.views_verification import generer_qr_code_base64
    from django.urls import reverse
    
    bulletin = get_object_or_404(Bulletin.objects.select_related('etudiant', 'etudiant__filiere', 'etudiant__niveau'), pk=bulletin_id)
    
    user = request.user
    is_student_owner = (getattr(user, 'etudiant_profile', None) == bulletin.etudiant or getattr(user, 'email', '') == bulletin.etudiant.email)
    is_staff = user.is_superuser or getattr(user, 'type_utilisateur', None) in ['ADMIN_SYSTEME', 'CHEF_ETUDES', 'DIRECTEUR']
    
    if not (is_student_owner or is_staff):
        messages.error(request, "Accès réservé au titulaire du bulletin ou à l'administration.")
        return redirect('tableau_bord:tableau_bord')
        
    if is_student_owner and not bulletin.est_publie and not is_staff:
        messages.warning(request, "Le bulletin pour ce semestre n'a pas encore été officiellement publié par l'administration.")
        return redirect('tableau_bord:tableau_bord')

    url_verif = request.build_absolute_uri(
        reverse('etudiants:verifier_etudiant_public', kwargs={'token': bulletin.etudiant.verification_token})
    )
    qr_code_b64 = generer_qr_code_base64(url_verif)

    context = {
        'bulletin': bulletin,
        'etudiant': bulletin.etudiant,
        'qr_code_b64': qr_code_b64,
        'titre': f"Bulletin Officiel S{bulletin.semestre} - {bulletin.etudiant.nom}"
    }
    return render(request, 'notes/bulletin_etudiant.html', context)


@login_required
def diffuser_resultats(request, salle_id):
    """Redirection utilitaire de diffusion."""
    return publier_bulletins_salle(request, salle_id)


@login_required
def consulter_resultat_individuel(request, token):
    """Consulter un résultat individuel à partir d'un jeton direct de vérification."""
    from apps.etudiants.models import Etudiant
    from .models import Bulletin
    etudiant = get_object_or_404(Etudiant, verification_token=token)
    bulletin = Bulletin.objects.filter(etudiant=etudiant, est_publie=True).order_by('-semestre').first()
    if not bulletin:
        messages.warning(request, "Aucun bulletin publié disponible pour cet étudiant.")
        return redirect('tableau_bord:tableau_bord')
    return redirect('notes:voir_bulletin_officiel', bulletin_id=bulletin.id)


@login_required
def liste_proces_verbaux(request):
    """
    Registre centralisé des Procès-Verbaux (PV) de notes transmis par le Chef de Service de l'Anonymat.
    Structuré par Salle, Filière et Niveau, et catégorisé par Type (Contrôle Continu, Examen, Rattrapage).
    """
    user_type = getattr(request.user, 'type_utilisateur', '')
    if user_type not in ['CHEF_ETUDES', 'CHEF_ANONYMAT', 'ADMIN_PEDAGOGIQUE', 'ADMIN_SYSTEME', 'DIRECTEUR'] and not request.user.is_superuser:
        messages.error(request, "Accès confidentiel réservé au Chef des Études, Chef Anonymat et à l'Administration.")
        return redirect('tableau_bord:tableau_bord')

    from apps.etudiants.models import Filiere, Niveau
    from apps.cours.models import Salle

    # Récupération des filtres depuis la requête GET
    filiere_id = request.GET.get('filiere_id', '').strip()
    niveau_id = request.GET.get('niveau_id', '').strip()
    salle_id = request.GET.get('salle_id', '').strip()
    q = request.GET.get('q', '').strip()

    # Queryset de base : uniquement les Procès-Verbaux de Notes générés/transmis (exclut les fiches d'anonymat brutes)
    fiches = FicheNotesAnonymat.objects.filter(
        proces_verbal__isnull=False,
        statut__in=['TRANSMIS_CHEF_ETUDES', 'PV_GENERE', 'VALIDE']
    ).select_related('matiere', 'filiere', 'niveau', 'salle', 'type_evaluation', 'enseignant', 'proces_verbal').order_by('-date_transmission_etudes', '-date_creation')

    # Filtrage dynamique
    if filiere_id:
        fiches = fiches.filter(filiere_id=filiere_id)
    if niveau_id:
        fiches = fiches.filter(niveau_id=niveau_id)
    if salle_id:
        fiches = fiches.filter(salle_id=salle_id)
    if q:
        fiches = fiches.filter(
            Q(matiere__nom__icontains=q) |
            Q(matiere__code__icontains=q) |
            Q(enseignant_nom__icontains=q) |
            Q(proces_verbal__titre__icontains=q)
        )

    # Répartition stricte par type d'évaluation (CC, EXAMEN, RATTRAPAGE)
    fiches_cc = []
    fiches_examen = []
    fiches_rattrapage = []

    for f in fiches:
        code_type = f.type_evaluation.code.upper() if (f.type_evaluation and hasattr(f.type_evaluation, 'code')) else 'CC'
        nom_type = str(f.type_evaluation).upper() if f.type_evaluation else ''
        
        if 'EXAM' in code_type or 'EXAM' in nom_type:
            fiches_examen.append(f)
        elif 'RATT' in code_type or 'RATT' in nom_type:
            fiches_rattrapage.append(f)
        else:
            fiches_cc.append(f)

    # Données pour les filtres déroulants
    filieres = Filiere.objects.filter(est_active=True)
    niveaux = Niveau.objects.all().order_by('numero')
    salles = Salle.objects.filter(est_disponible=True)

    context = {
        'fiches_cc': fiches_cc,
        'fiches_examen': fiches_examen,
        'fiches_rattrapage': fiches_rattrapage,
        'total_pvs': len(fiches),
        'count_cc': len(fiches_cc),
        'count_examen': len(fiches_examen),
        'count_rattrapage': len(fiches_rattrapage),
        'filieres': filieres,
        'niveaux': niveaux,
        'salles': salles,
        'filiere_id': filiere_id,
        'niveau_id': niveau_id,
        'salle_id': salle_id,
        'q': q,
        'titre': 'Procès-Verbaux d\'Anonymat'
    }
    return render(request, 'notes/liste_proces_verbaux.html', context)