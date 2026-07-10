"""
Configuration de l'administration pour les notes
IAI-Cameroun - Centre de Douala
"""
from django.contrib import admin
from .models import (
    TypeEvaluation, Evaluation, Note, Bulletin,
    DetailBulletin, Deliberation, RecoursNote
)


@admin.register(TypeEvaluation)
class TypeEvaluationAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'coefficient_default', 'est_actif']


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    # ✅ Correction : suppression de 'est_terminee'
    list_display = ['titre', 'cours', 'date_evaluation', 'statut', 'est_publiee']
    list_filter = ['statut', 'est_publiee']
    search_fields = ['titre']


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ['etudiant', 'evaluation', 'valeur', 'est_validee']
    list_filter = ['est_validee']


@admin.register(Bulletin)
class BulletinAdmin(admin.ModelAdmin):
    list_display = ['etudiant', 'annee_academique', 'semestre', 'moyenne_semestre', 'decision']


@admin.register(DetailBulletin)
class DetailBulletinAdmin(admin.ModelAdmin):
    list_display = ['bulletin', 'matiere', 'moyenne_matiere']


@admin.register(Deliberation)
class DeliberationAdmin(admin.ModelAdmin):
    list_display = ['filiere', 'annee_academique', 'semestre', 'est_terminee']


@admin.register(RecoursNote)
class RecoursNoteAdmin(admin.ModelAdmin):
    list_display = ['etudiant', 'evaluation', 'statut', 'date_soumission']