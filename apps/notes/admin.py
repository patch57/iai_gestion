"""
Configuration de l'administration pour les notes
IAI-Cameroun - Centre de Douala
"""
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from .models import (
    TypeEvaluation, Evaluation, Note, Bulletin,
    DetailBulletin, Deliberation, RecoursNote,
    UniteEnseignement, Matiere
)


class MatiereInline(admin.TabularInline):
    model = Matiere
    extra = 1
    fields = ['code', 'nom', 'credit', 'semestre', 'volume_horaire', 'est_actif']
    show_change_link = True


@admin.register(UniteEnseignement)
class UniteEnseignementAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'filiere', 'niveau', 'get_nombre_matieres', 'get_total_credits']
    list_filter = ['filiere', 'niveau']
    search_fields = ['code', 'nom']
    inlines = [MatiereInline]
    ordering = ['code']

    @admin.display(description="Nombre de Matières")
    def get_nombre_matieres(self, obj):
        return obj.matieres.count()

    @admin.display(description="Total Crédits")
    def get_total_credits(self, obj):
        res = obj.matieres.aggregate(total=Sum('credit'))['total']
        return res if res is not None else 0


@admin.register(Matiere)
class MatiereAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'unite_enseignement', 'semestre', 'credit', 'volume_horaire', 'est_actif']
    list_filter = ['semestre', 'unite_enseignement__filiere', 'unite_enseignement__niveau', 'unite_enseignement', 'est_actif']
    search_fields = ['code', 'nom', 'unite_enseignement__code', 'unite_enseignement__nom']
    list_editable = ['semestre', 'credit', 'volume_horaire', 'est_actif']
    ordering = ['semestre', 'code']
    actions = ['passer_au_semestre_1', 'passer_au_semestre_2']


    @admin.display(description="Semestre")
    def badge_semestre(self, obj):
        if obj.semestre == 1:
            return format_html('<span style="background-color: #2563EB; color: white; padding: 3px 9px; border-radius: 12px; font-weight: 600; font-size: 11px;">Semestre 1</span>')
        elif obj.semestre == 2:
            return format_html('<span style="background-color: #059669; color: white; padding: 3px 9px; border-radius: 12px; font-weight: 600; font-size: 11px;">Semestre 2</span>')
        return f"Semestre {obj.semestre}"

    @admin.action(description="Définir sur Semestre 1")
    def passer_au_semestre_1(self, request, queryset):
        count = queryset.update(semestre=1)
        self.message_user(request, f"✅ {count} matière(s) configurée(s) pour le Semestre 1.")

    @admin.action(description="Définir sur Semestre 2")
    def passer_au_semestre_2(self, request, queryset):
        count = queryset.update(semestre=2)
        self.message_user(request, f"✅ {count} matière(s) configurée(s) pour le Semestre 2.")



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


from .models import FicheNotesAnonymat, LigneFicheNotesAnonymat


class LigneFicheNotesAnonymatInline(admin.TabularInline):
    model = LigneFicheNotesAnonymat
    extra = 0
    readonly_fields = ['nom_manuscrit_detecte']


@admin.register(FicheNotesAnonymat)
class FicheNotesAnonymatAdmin(admin.ModelAdmin):
    list_display = ['matiere', 'filiere', 'niveau', 'salle', 'type_evaluation', 'annee_academique', 'statut', 'date_creation', 'cree_par']
    list_filter = ['statut', 'annee_academique', 'type_evaluation', 'filiere', 'niveau']
    search_fields = ['matiere__code', 'matiere__nom', 'salle__code']
    inlines = [LigneFicheNotesAnonymatInline]