"""
Configuration de l'administration pour les étudiants
IAI-Cameroun - Centre de Douala
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Filiere, Etudiant, DocumentEtudiant, HistoriqueEtudiant,
    Niveau, Classe, AnneeAcademique, DocumentObligatoire
)


@admin.register(Filiere)
class FiliereAdmin(admin.ModelAdmin):
    """Configuration admin pour les filières"""
    list_display = ['code', 'nom', 'duree_ans', 'est_active', 'date_creation']
    list_filter = ['code', 'est_active']
    search_fields = ['nom', 'code']
    ordering = ['code']
    list_editable = ['est_active']
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('code', 'nom', 'description')
        }),
        ('Durée de formation', {
            'fields': ('duree_ans',)
        }),
        ('Statut', {
            'fields': ('est_active',)
        }),
    )


@admin.register(Niveau)
class NiveauAdmin(admin.ModelAdmin):
    """Configuration admin pour les niveaux"""
    list_display = ['numero', 'filiere', 'code']
    list_filter = ['filiere', 'numero']
    search_fields = ['code']
    ordering = ['filiere__code', 'numero']


@admin.register(Classe)
class ClasseAdmin(admin.ModelAdmin):
    """Configuration admin pour les classes"""
    list_display = [
        'nom', 'filiere', 'niveau', 'annee_academique', 
        'effectif_actuel', 'effectif_max', 'est_active'
    ]
    list_filter = ['filiere', 'niveau', 'annee_academique', 'est_active']
    search_fields = ['nom']
    ordering = ['filiere__code', 'niveau__numero', 'nom']


@admin.register(AnneeAcademique)
class AnneeAcademiqueAdmin(admin.ModelAdmin):
    """Configuration admin pour les années académiques"""
    list_display = ['code', 'date_debut', 'date_fin', 'est_active']
    list_filter = ['est_active']
    search_fields = ['code']
    ordering = ['-code']
    
    fieldsets = (
        ('Informations', {
            'fields': ('code', 'date_debut', 'date_fin')
        }),
        ('Statut', {
            'fields': ('est_active',)
        }),
    )


@admin.register(Etudiant)
class EtudiantAdmin(admin.ModelAdmin):
    """Configuration admin pour les étudiants"""
    list_display = [
        'matricule', 'nom', 'prenom', 'filiere', 'niveau',
        'annee_academique', 'statut', 'telephone', 'photo_preview'
    ]
    list_filter = [
        'statut', 'filiere', 'niveau', 'annee_academique', 
        'sexe', 'nationalite'
    ]
    search_fields = [
        'matricule', 'nom', 'prenom', 'email', 'telephone'
    ]
    ordering = ['nom', 'prenom']
    list_per_page = 20
    date_hierarchy = 'date_inscription'
    list_editable = ['statut']
    
    fieldsets = (
        ('Informations d\'identification', {
            'fields': ('matricule', 'utilisateur')
        }),
        ('Informations personnelles', {
            'fields': ('nom', 'prenom', 'date_naissance', 'lieu_naissance', 'sexe', 'nationalite')
        }),
        ('Contact', {
            'fields': ('telephone', 'email', 'adresse')
        }),
        ('Informations académiques', {
            'fields': ('filiere', 'niveau', 'classe', 'annee_academique', 'statut')
        }),
        ('Documents', {
            'fields': ('photo', 'recu_preinscription', 'carte_etudiant_delivree', 'date_delivrance_carte')
        }),
        ('Tuteur', {
            'fields': ('nom_tuteur', 'telephone_tuteur', 'email_tuteur')
        }),
        ('Santé', {
            'fields': ('groupe_sanguin', 'allergies', 'informations_medicales'),
            'classes': ('collapse',)
        }),
    )
    
    def photo_preview(self, obj):
        """Affiche un aperçu de la photo dans l'admin"""
        if obj.photo:
            return format_html('<img src="{}" width="50" height="50" style="border-radius: 50%;" />', obj.photo.url)
        return format_html('<span style="color:gray;">Aucune photo</span>')
    photo_preview.short_description = 'Photo'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('filiere', 'niveau', 'classe')


@admin.register(DocumentEtudiant)
class DocumentEtudiantAdmin(admin.ModelAdmin):
    """Configuration admin pour les documents étudiants"""
    list_display = ['etudiant', 'type_document', 'est_valide', 'date_ajout']
    list_filter = ['type_document', 'est_valide', 'date_ajout']
    search_fields = ['etudiant__nom', 'etudiant__prenom', 'etudiant__matricule', 'description']
    ordering = ['-date_ajout']
    
    fieldsets = (
        ('Document', {
            'fields': ('etudiant', 'type_document', 'fichier', 'description')
        }),
        ('Validation', {
            'fields': ('est_valide', 'valide_par', 'date_validation')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('etudiant', 'valide_par')


@admin.register(HistoriqueEtudiant)
class HistoriqueEtudiantAdmin(admin.ModelAdmin):
    """Configuration admin pour l'historique des étudiants"""
    list_display = ['etudiant', 'action', 'utilisateur', 'date_action']
    list_filter = ['action', 'date_action']
    search_fields = ['etudiant__nom', 'etudiant__prenom', 'action', 'details']
    date_hierarchy = 'date_action'
    readonly_fields = ['date_action']
    
    fieldsets = (
        ('Action', {
            'fields': ('etudiant', 'action', 'details')
        }),
        ('Utilisateur', {
            'fields': ('utilisateur', 'ip_address')
        }),
        ('Date', {
            'fields': ('date_action',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('etudiant', 'utilisateur')


@admin.register(DocumentObligatoire)
class DocumentObligatoireAdmin(admin.ModelAdmin):
    """Configuration admin pour les documents obligatoires"""
    list_display = ['nom', 'type_document', 'filiere', 'niveau', 'est_actif', 'est_obligatoire', 'ordre_affichage']
    list_filter = ['est_actif', 'est_obligatoire', 'filiere', 'niveau']
    search_fields = ['nom', 'type_document', 'description']
    ordering = ['ordre_affichage', 'type_document']
    list_editable = ['ordre_affichage', 'est_actif', 'est_obligatoire']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('type_document', 'nom', 'description')
        }),
        ('Format et taille', {
            'fields': ('format_accepte', 'taille_max_mb')
        }),
        ('Filtrage', {
            'fields': ('filiere', 'niveau'),
            'description': 'Laisser vide pour appliquer à tous les étudiants'
        }),
        ('Statut et affichage', {
            'fields': ('est_actif', 'est_obligatoire', 'ordre_affichage')
        }),
    )