"""
Configuration de l'administration pour les inscriptions
IAI-Cameroun - Centre de Douala
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    AnneeAcademique, Inscription, DocumentInscription
)


@admin.register(AnneeAcademique)
class AnneeAcademiqueAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'date_debut', 'date_fin',
        'est_actuelle', 'est_ouverte_inscription'
    ]
    list_filter = ['est_actuelle', 'est_ouverte_inscription']
    search_fields = ['code']
    list_editable = ['est_actuelle', 'est_ouverte_inscription']
    fieldsets = (
        ('Informations générales', {
            'fields': ('code', 'date_debut', 'date_fin')
        }),
        ('Statut', {
            'fields': ('est_actuelle', 'est_ouverte_inscription')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """S'assurer qu'une seule année est active"""
        if obj.est_actuelle:
            AnneeAcademique.objects.filter(est_actuelle=True).update(est_actuelle=False)
        if obj.est_ouverte_inscription:
            AnneeAcademique.objects.filter(est_ouverte_inscription=True).update(est_ouverte_inscription=False)
        super().save_model(request, obj, form, change)
    
    actions = ['activer_annee', 'ouvrir_inscriptions']
    
    def activer_annee(self, request, queryset):
        """Action pour activer une année académique"""
        queryset.update(est_actuelle=True)
        self.message_user(request, "Année académique activée avec succès.")
    activer_annee.short_description = "Activer l'année académique"
    
    def ouvrir_inscriptions(self, request, queryset):
        """Action pour ouvrir les inscriptions"""
        queryset.update(est_ouverte_inscription=True)
        self.message_user(request, "Inscriptions ouvertes avec succès.")
    ouvrir_inscriptions.short_description = "Ouvrir les inscriptions"


@admin.register(Inscription)
class InscriptionAdmin(admin.ModelAdmin):
    list_display = [
        'etudiant_link', 'annee_academique', 'type_inscription',
        'filiere_link', 'statut', 'statut_badge', 'date_inscription'
    ]
    list_filter = ['statut', 'type_inscription', 'annee_academique', 'date_inscription']
    search_fields = [
        'etudiant__nom', 'etudiant__prenom',
        'etudiant__matricule', 'filiere__nom'
    ]
    date_hierarchy = 'date_inscription'
    list_editable = ['statut']
    readonly_fields = ['date_inscription', 'date_validation', 'validee_par']
    
    fieldsets = (
        ('Étudiant', {
            'fields': ('etudiant', 'filiere', 'annee_academique')
        }),
        ('Détails de l\'inscription', {
            'fields': ('type_inscription', 'statut', 'commentaire')
        }),
        ('Validation', {
            'fields': ('date_validation', 'validee_par'),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': ('date_inscription',),
            'classes': ('collapse',)
        }),
    )
    
    def etudiant_link(self, obj):
        """Lien vers l'étudiant dans l'admin"""
        try:
            url = reverse('admin:etudiants_etudiant_change', args=[obj.etudiant.id])
            return format_html('<a href="{}">{}</a>', url, obj.etudiant)
        except:
            return str(obj.etudiant)
    etudiant_link.short_description = "Étudiant"
    
    def filiere_link(self, obj):
        """Lien vers la filière dans l'admin"""
        try:
            url = reverse('admin:etudiants_filiere_change', args=[obj.filiere.id])
            return format_html('<a href="{}">{}</a>', url, obj.filiere)
        except:
            return str(obj.filiere)
    filiere_link.short_description = "Filière"
    
    def statut_badge(self, obj):
        """Badge coloré pour le statut"""
        colors = {
            'PREINSCRIPTION': '#FFA500',
            'EN_ATTENTE': '#FFC107',
            'VALIDEE': '#28A745',
            'REJETEE': '#DC3545',
            'ANNULEE': '#6C757D',
        }
        color = colors.get(obj.statut, '#007BFF')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px;">{}</span>',
            color, obj.get_statut_display()
        )
    statut_badge.short_description = "Statut"
    
    actions = ['valider_inscriptions', 'rejeter_inscriptions']
    
    def valider_inscriptions(self, request, queryset):
        """Action pour valider les inscriptions"""
        from django.utils import timezone
        updated = queryset.update(statut='VALIDEE', date_validation=timezone.now(), validee_par=request.user)
        self.message_user(request, f"{updated} inscription(s) validée(s) avec succès.")
    valider_inscriptions.short_description = "Valider les inscriptions sélectionnées"
    
    def rejeter_inscriptions(self, request, queryset):
        """Action pour rejeter les inscriptions"""
        updated = queryset.update(statut='REJETEE')
        self.message_user(request, f"{updated} inscription(s) rejetée(s).")
    rejeter_inscriptions.short_description = "Rejeter les inscriptions sélectionnées"


@admin.register(DocumentInscription)
class DocumentInscriptionAdmin(admin.ModelAdmin):
    list_display = [
        'inscription_link', 'type_document', 'est_valide', 'est_valide_badge',
        'date_ajout', 'document_link'
    ]
    list_filter = ['type_document', 'est_valide', 'date_ajout']
    search_fields = ['inscription__etudiant__nom', 'inscription__etudiant__prenom']
    list_editable = ['est_valide']
    
    def inscription_link(self, obj):
        """Lien vers l'inscription dans l'admin"""
        try:
            url = reverse('admin:inscriptions_inscription_change', args=[obj.inscription.id])
            return format_html('<a href="{}">{}</a>', url, obj.inscription)
        except:
            return str(obj.inscription)
    inscription_link.short_description = "Inscription"
    
    def est_valide_badge(self, obj):
        """Badge pour l'état de validation"""
        if obj.est_valide:
            return format_html('<span style="color: #28A745;">✅ Validé</span>')
        return format_html('<span style="color: #FFC107;">⏳ En attente</span>')
    est_valide_badge.short_description = "Statut"
    
    def document_link(self, obj):
        """Lien pour télécharger le document"""
        if obj.fichier and hasattr(obj.fichier, 'url'):
            return format_html('<a href="{}" target="_blank" style="color: #007BFF;">📄 Télécharger</a>', obj.fichier.url)
        return "-"
    document_link.short_description = "Document"
    
    actions = ['valider_documents']
    
    def valider_documents(self, request, queryset):
        """Action pour valider les documents"""
        updated = queryset.update(est_valide=True)
        self.message_user(request, f"{updated} document(s) validé(s) avec succès.")
    valider_documents.short_description = "Valider les documents sélectionnés"