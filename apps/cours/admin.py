"""
Configuration de l'administration pour les cours
"""
from django.contrib import admin
from .models import (
    Salle, Matiere, Cours, SeanceCours,
    InscriptionCours, Presence, RessourceCours, EmploiDuTemps
)


@admin.register(Salle)
class SalleAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'type_salle', 'capacite', 'etage', 'est_disponible']
    list_filter = ['type_salle', 'est_disponible', 'a_projecteur', 'a_climatisation']
    search_fields = ['code', 'nom']


@admin.register(Matiere)
class MatiereAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'credits', 'heures_cours', 'heures_td', 'heures_tp', 'semestre']
    list_filter = ['semestre', 'est_optionnelle']
    search_fields = ['code', 'nom']


@admin.register(Cours)
class CoursAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'matiere', 'filiere', 'professeur',
        'type_cours', 'jour', 'heure_debut', 'heure_fin', 'est_actif'
    ]
    list_filter = ['type_cours', 'est_actif', 'annee_academique', 'jour']
    search_fields = ['code', 'matiere__nom', 'professeur__nom']
    date_hierarchy = 'date_debut'


@admin.register(SeanceCours)
class SeanceCoursAdmin(admin.ModelAdmin):
    list_display = ['cours', 'date', 'heure_debut', 'heure_fin', 'est_effectuee', 'est_annulee']
    list_filter = ['est_effectuee', 'est_annulee', 'date']
    search_fields = ['cours__code', 'cours__matiere__nom', 'titre']
    date_hierarchy = 'date'


@admin.register(InscriptionCours)
class InscriptionCoursAdmin(admin.ModelAdmin):
    list_display = ['etudiant', 'cours', 'date_inscription', 'est_actif']
    list_filter = ['est_actif', 'date_inscription']
    search_fields = ['etudiant__nom', 'etudiant__prenom', 'cours__code']


@admin.register(Presence)
class PresenceAdmin(admin.ModelAdmin):
    list_display = ['seance', 'etudiant', 'statut', 'heure_arrivee']
    list_filter = ['statut']
    search_fields = ['etudiant__nom', 'etudiant__prenom', 'seance__cours__code']


@admin.register(RessourceCours)
class RessourceCoursAdmin(admin.ModelAdmin):
    list_display = ['cours', 'type_ressource', 'titre', 'est_public', 'date_ajout']
    list_filter = ['type_ressource', 'est_public', 'date_ajout']
    search_fields = ['titre', 'cours__code']


@admin.register(EmploiDuTemps)
class EmploiDuTempsAdmin(admin.ModelAdmin):
    list_display = ['filiere', 'annee_academique', 'semestre', 'est_actif', 'date_creation']
    list_filter = ['est_actif', 'annee_academique', 'semestre']
    search_fields = ['filiere__nom']
