"""
Configuration de l'administration pour le tableau de bord
"""
from django.contrib import admin
from .models import (
    Notification, Activite, Configuration, Rapport,
    Statistique, Message, Tache
)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['utilisateur', 'type', 'titre', 'est_lue', 'date_creation']
    list_filter = ['type', 'est_lue', 'date_creation']
    search_fields = ['utilisateur__username', 'titre', 'message']
    date_hierarchy = 'date_creation'


@admin.register(Activite)
class ActiviteAdmin(admin.ModelAdmin):
    list_display = ['utilisateur', 'type_action', 'module', 'date_action']
    list_filter = ['type_action', 'module', 'date_action']
    search_fields = ['utilisateur__username', 'description']
    date_hierarchy = 'date_action'


@admin.register(Configuration)
class ConfigurationAdmin(admin.ModelAdmin):
    list_display = ['cle', 'valeur', 'est_modifiable', 'date_modification']
    list_filter = ['est_modifiable']
    search_fields = ['cle', 'description']


@admin.register(Rapport)
class RapportAdmin(admin.ModelAdmin):
    list_display = [
        'titre', 'type_rapport', 'format',
        'cree_par', 'date_creation', 'est_archive'
    ]
    list_filter = ['type_rapport', 'format', 'est_archive', 'date_creation']
    search_fields = ['titre', 'description']
    date_hierarchy = 'date_creation'


@admin.register(Statistique)
class StatistiqueAdmin(admin.ModelAdmin):
    list_display = ['type_stat', 'valeur', 'annee_academique', 'date_calcul']
    list_filter = ['type_stat', 'annee_academique', 'date_calcul']
    search_fields = ['valeur_texte']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['expediteur', 'destinataire', 'sujet', 'est_lu', 'date_envoi']
    list_filter = ['est_lu', 'est_important', 'date_envoi']
    search_fields = ['expediteur__username', 'destinataire__username', 'sujet']
    date_hierarchy = 'date_envoi'


@admin.register(Tache)
class TacheAdmin(admin.ModelAdmin):
    list_display = [
        'titre', 'assignee_a', 'priorite',
        'statut', 'date_echeance', 'module'
    ]
    list_filter = ['priorite', 'statut', 'module', 'date_echeance']
    search_fields = ['titre', 'description', 'assignee_a__username']
