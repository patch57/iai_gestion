"""
Configuration de l'administration pour les professeurs
"""
from django.contrib import admin
from .models import Departement, Professeur, ChargeHoraire, DocumentProfesseur, DisponibiliteProfesseur


@admin.register(Departement)
class DepartementAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'responsable', 'est_actif']
    list_filter = ['est_actif']
    search_fields = ['code', 'nom']


@admin.register(Professeur)
class ProfesseurAdmin(admin.ModelAdmin):
    list_display = [
        'matricule', 'nom', 'prenom', 'grade', 
        'departement', 'statut', 'telephone'
    ]
    list_filter = ['grade', 'statut', 'departement', 'type_contrat']
    search_fields = ['matricule', 'nom', 'prenom', 'email', 'specialite']
    ordering = ['nom', 'prenom']
    date_hierarchy = 'date_embauche'
    
    fieldsets = (
        ('Informations d\'identification', {
            'fields': ('matricule',)
        }),
        ('Informations personnelles', {
            'fields': ('nom', 'prenom', 'date_naissance', 'lieu_naissance', 'sexe', 'nationalite')
        }),
        ('Contact', {
            'fields': ('telephone', 'email', 'adresse')
        }),
        ('Informations professionnelles', {
            'fields': ('grade', 'departement', 'specialite', 'diplomes', 'annee_experience', 'statut')
        }),
        ('Informations contractuelles', {
            'fields': ('date_embauche', 'type_contrat', 'salaire_base')
        }),
        ('Photo', {
            'fields': ('photo',)
        }),
        ('Compte utilisateur', {
            'fields': ('utilisateur',),
            'classes': ('collapse',)
        }),
    )


@admin.register(ChargeHoraire)
class ChargeHoraireAdmin(admin.ModelAdmin):
    list_display = [
        'professeur', 'annee_academique', 'heures_assignees',
        'heures_effectuees', 'montant_total', 'est_paye'
    ]
    list_filter = ['annee_academique', 'est_paye']
    search_fields = ['professeur__nom', 'professeur__prenom']


@admin.register(DocumentProfesseur)
class DocumentProfesseurAdmin(admin.ModelAdmin):
    list_display = ['professeur', 'type_document', 'date_ajout']
    list_filter = ['type_document', 'date_ajout']
    search_fields = ['professeur__nom', 'professeur__prenom']


@admin.register(DisponibiliteProfesseur)
class DisponibiliteProfesseurAdmin(admin.ModelAdmin):
    list_display = ['professeur', 'jour', 'heure_debut', 'heure_fin', 'est_disponible']
    list_filter = ['jour', 'est_disponible']
    search_fields = ['professeur__nom', 'professeur__prenom']
