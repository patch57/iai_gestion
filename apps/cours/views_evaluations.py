"""
Vues pour l'évaluation anonyme des enseignants par les apprenants
IAI-Cameroun - Centre de Douala
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db.models import Avg, Count
from django.utils import timezone

from .models import (
    Cours, CampagneEvaluation, QuestionEvaluation,
    ParticipationEvaluation, ReponseEvaluation
)
from apps.etudiants.models import Etudiant
from apps.professeurs.models import Professeur


@login_required
def liste_evaluations_etudiant(request):
    """
    Affiche la liste des cours du semestre de l'étudiant à évaluer.
    """
    etudiant = getattr(request.user, 'etudiant_profile', None)
    if not etudiant:
        try:
            etudiant = Etudiant.objects.get(utilisateur=request.user)
        except Etudiant.DoesNotExist:
            messages.error(request, "Accès réservé aux étudiants.")
            return redirect('tableau_bord:tableau_bord')

    campagne_active = CampagneEvaluation.objects.filter(statut='OUVERTE').first()
    
    # Si aucune campagne n'est ouverte, créer une campagne par défaut si besoin
    if not campagne_active:
        campagne_active = CampagneEvaluation.objects.create(
            titre="Évaluation Pédagogique - Semestre 1 (2025-2026)",
            annee_academique="2025-2026",
            semestre=1,
            date_debut=timezone.now().date(),
            date_fin=timezone.now().date() + timezone.timedelta(days=30),
            statut='OUVERTE',
            description="Votre avis compte ! Évaluez anonymement les enseignements reçus ce semestre."
        )

    # Créer les questions par défaut si la base est vide
    if QuestionEvaluation.objects.count() == 0:
        questions_defaut = [
            ("Maîtrise du sujet et clarté des explications du professeur", "PEDAGOGIE", 1),
            ("Ponctualité et respect des horaires de cours", "PONCTUALITE", 2),
            ("Qualité des supports pédagogiques, TP et devoirs", "SUPPORTS", 3),
            ("Interactivité, disponibilité et écoute des étudiants", "INTERACTIVITE", 4),
            ("Respect du programme et transparence de l'évaluation", "EVALUATION", 5),
            ("Appréciation générale globale du cours", "GLOBAL", 6),
        ]
        for intitule, cat, ordre in questions_defaut:
            QuestionEvaluation.objects.create(intitule=intitule, categorie=cat, ordre=ordre)

    # Récupérer les cours dispensés à la filière de l'étudiant
    cours_filiere = Cours.objects.filter(filiere=etudiant.filiere).select_related('matiere', 'professeur')

    # Cartographier les cours déjà évalués anonymement par cet étudiant
    cours_evalues_ids = set(
        ParticipationEvaluation.objects.filter(
            campagne=campagne_active,
            etudiant=etudiant
        ).values_list('cours_id', flat=True)
    )

    liste_cours_statut = []
    for c in cours_filiere:
        est_evalue = c.id in cours_evalues_ids
        liste_cours_statut.append({
            'cours': c,
            'est_evalue': est_evalue
        })

    context = {
        'campagne': campagne_active,
        'liste_cours': liste_cours_statut,
        'titre': 'Évaluation des Enseignants (Anonyme)'
    }
    return render(request, 'cours/evaluations/liste_evaluations.html', context)


@login_required
def evaluer_cours(request, cours_id):
    """
    Formulaire d'évaluation 5 étoiles anonyme pour un cours spécifique.
    """
    etudiant = getattr(request.user, 'etudiant_profile', None)
    if not etudiant:
        try:
            etudiant = Etudiant.objects.get(utilisateur=request.user)
        except Etudiant.DoesNotExist:
            messages.error(request, "Accès réservé aux étudiants.")
            return redirect('tableau_bord:tableau_bord')

    cours = get_object_or_404(Cours, pk=cours_id)
    campagne_active = CampagneEvaluation.objects.filter(statut='OUVERTE').first()
    
    if not campagne_active:
        messages.warning(request, "Aucune campagne d'évaluation n'est ouverte actuellement.")
        return redirect('cours:liste_evaluations_etudiant')

    # Vérifier si l'étudiant a déjà participé pour ce cours
    deja_evalue = ParticipationEvaluation.objects.filter(
        campagne=campagne_active,
        cours=cours,
        etudiant=etudiant
    ).exists()

    if deja_evalue:
        messages.info(request, f"Vous avez déjà soumis votre évaluation anonyme pour le cours {cours.code}.")
        return redirect('cours:liste_evaluations_etudiant')

    questions = QuestionEvaluation.objects.filter(est_active=True).order_by('ordre')

    if request.method == 'POST':
        commentaire_libre = request.POST.get('commentaire_general', '').strip()

        # 1. Enregistrer la participation de l'étudiant pour bloquer les votes multiples
        ParticipationEvaluation.objects.create(
            campagne=campagne_active,
            cours=cours,
            etudiant=etudiant
        )

        # 2. Enregistrer anonymement les réponses (AUCUN LIEN vers etudiant)
        for q in questions:
            note_val = request.POST.get(f'question_{q.id}', 5)
            try:
                note_val = int(note_val)
                note_val = max(1, min(5, note_val))
            except ValueError:
                note_val = 5

            ReponseEvaluation.objects.create(
                campagne=campagne_active,
                cours=cours,
                question=q,
                note=note_val,
                commentaire=commentaire_libre if q.categorie == 'GLOBAL' else ""
            )

        messages.success(request, f"✅ Merci ! Votre évaluation anonyme pour le cours {cours.matiere.nom} a bien été enregistrée.")
        return redirect('cours:liste_evaluations_etudiant')

    context = {
        'cours': cours,
        'campagne': campagne_active,
        'questions': questions,
        'titre': f'Évaluation anonyme : {cours.matiere.nom}'
    }
    return render(request, 'cours/evaluations/evaluation_form.html', context)


@login_required
def synthese_evaluations_professeur(request, professeur_id=None):
    """
    Tableau de bord synthétique des évaluations d'un professeur (Direction & Enseignants).
    """
    if professeur_id:
        professeur = get_object_or_404(Professeur, pk=professeur_id)
    else:
        # Si aucun ID n'est passé, essayer de charger le profil de l'utilisateur connecté
        try:
            professeur = Professeur.objects.get(utilisateur=request.user)
        except Professeur.DoesNotExist:
            professeur = Professeur.objects.first()

    if not professeur:
        messages.error(request, "Aucun professeur trouvé.")
        return redirect('tableau_bord:tableau_bord')

    cours_prof = Cours.objects.filter(professeur=professeur)
    
    # Calculer la moyenne globale et le nombre d'évaluations
    reponses = ReponseEvaluation.objects.filter(cours__in=cours_prof)
    moyenne_globale = reponses.aggregate(Avg('note'))['note__avg'] or 0.0
    total_reponses = reponses.values('cours', 'date_creation').distinct().count()

    # Moyennes par catégorie de question
    stats_categories = []
    categories = QuestionEvaluation.CATEGORIE_CHOICES
    for cat_code, cat_libelle in categories:
        reps_cat = reponses.filter(question__categorie=cat_code)
        avg_cat = reps_cat.aggregate(Avg('note'))['note__avg'] or 0.0
        stats_categories.append({
            'code': cat_code,
            'libelle': cat_libelle,
            'moyenne': round(avg_cat, 2),
            'pourcentage': round((avg_cat / 5.0) * 100, 1)
        })

    # Commentaires anonymes filtrés (non vides)
    commentaires = reponses.exclude(commentaire='').values('commentaire', 'cours__code', 'date_creation')[:20]

    context = {
        'professeur': professeur,
        'cours_prof': cours_prof,
        'moyenne_globale': round(moyenne_globale, 2),
        'moyenne_pourcentage': round((moyenne_globale / 5.0) * 100, 1),
        'total_reponses': total_reponses,
        'stats_categories': stats_categories,
        'commentaires': commentaires,
        'titre': f'Synthèse d\'évaluation - {professeur.get_nom_complet()}'
    }
    return render(request, 'cours/evaluations/synthese_professeur.html', context)


@login_required
def gestion_evaluations_scolarite(request):
    """
    Tableau de bord complet pour le Chef de la Scolarité :
    - Gestion des campagnes d'évaluation (Création, Ouverture, Clôture).
    - Suivi global des moyennes et retours des étudiants par professeur.
    - Banque de questions d'évaluation.
    """
    user = request.user
    role = getattr(user, 'type_utilisateur', None)
    if role not in ('CHEF_SCOLARITE', 'ADMIN_SYSTEME', 'CHEF_ETUDES', 'ADMIN_PEDAGOGIQUE') and not user.is_superuser:
        messages.error(request, "❌ Accès réservé au Chef de la Scolarité et à la Direction.")
        return redirect('tableau_bord:tableau_bord')

    campagnes = CampagneEvaluation.objects.all().order_by('-date_debut')
    campagne_active = campagnes.filter(statut='OUVERTE').first()
    questions = QuestionEvaluation.objects.all().order_by('ordre')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'creer_campagne':
            titre_c = request.POST.get('titre')
            annee_c = request.POST.get('annee_academique', '2025-2026')
            semestre_c = int(request.POST.get('semestre', 1))
            date_deb = request.POST.get('date_debut')
            date_fi = request.POST.get('date_fin')

            CampagneEvaluation.objects.create(
                titre=titre_c,
                annee_academique=annee_c,
                semestre=semestre_c,
                date_debut=date_deb,
                date_fin=date_fi,
                statut='BROUILLON',
                description=f"Évaluation pédagogique anonyme {annee_c} - Semestre {semestre_c}"
            )
            messages.success(request, f"✅ Campagne '{titre_c}' créée en brouillon.")
            return redirect('cours:gestion_evaluations_scolarite')

        elif action == 'ajouter_question':
            intitule_q = request.POST.get('intitule')
            cat_q = request.POST.get('categorie', 'PEDAGOGIE')
            ordre_q = int(request.POST.get('ordre', 1))
            if intitule_q:
                QuestionEvaluation.objects.create(
                    intitule=intitule_q,
                    categorie=cat_q,
                    ordre=ordre_q
                )
                messages.success(request, "✅ Question d'évaluation ajoutée.")
            return redirect('cours:gestion_evaluations_scolarite')

    professeurs = Professeur.objects.all().select_related('utilisateur')
    stats_professeurs = []
    for prof in professeurs:
        cours_prof = Cours.objects.filter(professeur=prof)
        reponses_prof = ReponseEvaluation.objects.filter(cours__in=cours_prof)
        total_evals = reponses_prof.values('cours', 'date_creation').distinct().count()
        avg_note = reponses_prof.aggregate(Avg('note'))['note__avg'] or 0.0

        stats_professeurs.append({
            'professeur': prof,
            'nb_cours': cours_prof.count(),
            'total_evals': total_evals,
            'moyenne': round(avg_note, 2),
            'pourcentage': round((avg_note / 5.0) * 100, 1)
        })

    context = {
        'campagnes': campagnes,
        'campagne_active': campagne_active,
        'questions': questions,
        'stats_professeurs': stats_professeurs,
        'titre': 'Gestion des Évaluations Pédagogiques (Chef de la Scolarité)'
    }
    return render(request, 'cours/evaluations/gestion_scolarite.html', context)


@login_required
def changer_statut_campagne(request, pk, nouveau_statut):
    """Permet au Chef de la Scolarité d'ouvrir, fermer ou archiver une campagne d'évaluation"""
    user = request.user
    role = getattr(user, 'type_utilisateur', None)
    if role not in ('CHEF_SCOLARITE', 'ADMIN_SYSTEME', 'CHEF_ETUDES') and not user.is_superuser:
        messages.error(request, "❌ Accès non autorisé.")
        return redirect('tableau_bord:tableau_bord')

    campagne = get_object_or_404(CampagneEvaluation, pk=pk)
    if nouveau_statut == 'OUVERTE':
        CampagneEvaluation.objects.filter(statut='OUVERTE').update(statut='CLOTUREE')
        campagne.statut = 'OUVERTE'
        messages.success(request, f"🚀 La campagne '{campagne.titre}' est désormais OUVERTE aux étudiants !")
    elif nouveau_statut == 'CLOTUREE':
        campagne.statut = 'CLOTUREE'
        messages.info(request, f"🔒 La campagne '{campagne.titre}' a été CLÔTURÉE.")
    campagne.save()
    return redirect('cours:gestion_evaluations_scolarite')
