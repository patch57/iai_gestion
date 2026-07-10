"""
Modèles pour la gestion des inscriptions
IAI-Cameroun - Centre de Douala
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal


class AnneeAcademique(models.Model):
    """Années académiques"""
    code = models.CharField(max_length=9, unique=True, verbose_name="Code")  # Ex: 2024-2025
    date_debut = models.DateField(verbose_name="Date de début")
    date_fin = models.DateField(verbose_name="Date de fin")
    est_actuelle = models.BooleanField(default=False, verbose_name="Est l'année actuelle")
    est_ouverte_inscription = models.BooleanField(default=False, verbose_name="Inscriptions ouvertes")
    
    class Meta:
        app_label = 'inscriptions'
        verbose_name = "Année Académique"
        verbose_name_plural = "Années Académiques"
        ordering = ['-code']
    
    def __str__(self):
        return self.code
    
    def save(self, *args, **kwargs):
        if self.est_actuelle:
            # Désactiver les autres années académiques
            AnneeAcademique.objects.filter(est_actuelle=True).update(est_actuelle=False)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_active(cls):
        """Retourne l'année académique active"""
        try:
            return cls.objects.get(est_actuelle=True)
        except cls.DoesNotExist:
            return None


class Inscription(models.Model):
    """Inscriptions des étudiants"""
    TYPE_INSCRIPTION_CHOICES = [
        ('NOUVELLE', 'Nouvelle Inscription'),
        ('REINSCRIPTION', 'Réinscription'),
        ('TRANSFERT', 'Transfert'),
    ]
    
    STATUT_CHOICES = [
        ('PREINSCRIPTION', 'Pré-inscription'),
        ('EN_ATTENTE', 'En Attente de Validation'),
        ('COMPLETEE', 'Complétée'),
        ('VALIDEE', 'Validée'),
        ('REJETEE', 'Rejetée'),
        ('ANNULEE', 'Annulée'),
    ]
    
    etudiant = models.ForeignKey(
        'etudiants.Etudiant',
        on_delete=models.CASCADE,
        related_name='inscriptions'
    )
    annee_academique = models.ForeignKey(
        AnneeAcademique,
        on_delete=models.PROTECT,
        related_name='inscriptions'
    )
    type_inscription = models.CharField(
        max_length=15,
        choices=TYPE_INSCRIPTION_CHOICES,
        default='NOUVELLE',
        verbose_name="Type d'inscription"
    )
    filiere = models.ForeignKey(
        'etudiants.Filiere',
        on_delete=models.PROTECT,
        related_name='inscriptions',
        verbose_name="Filière choisie"
    )
    
    # Statut
    statut = models.CharField(
        max_length=15,
        choices=STATUT_CHOICES,
        default='PREINSCRIPTION',
        verbose_name="Statut"
    )
    
    # Dates
    date_inscription = models.DateTimeField(auto_now_add=True, verbose_name="Date d'inscription")
    date_validation = models.DateTimeField(null=True, blank=True, verbose_name="Date de validation")
    validee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inscriptions_validees',
        verbose_name="Validée par"
    )
    
    # Reçu de pré-inscription (téléversé, pas de paiement sur la plateforme)
    recu_preinscription = models.FileField(
        upload_to='inscriptions/recus/preinscription/%Y/%m/',
        blank=True,
        null=True,
        verbose_name="Reçu de pré-inscription",
        help_text="Téléversez le reçu de paiement de la pré-inscription (format PDF, JPG, PNG)"
    )
    recu_preinscription_valide = models.BooleanField(
        default=False,
        verbose_name="Reçu de pré-inscription validé",
        help_text="Cochez après vérification manuelle du reçu"
    )
    
    # Reçus des tranches de paiement (téléversés, pas de paiement sur la plateforme)
    recu_tranche_1 = models.FileField(
        upload_to='inscriptions/recus/tranches/%Y/%m/',
        blank=True,
        null=True,
        verbose_name="Reçu 1ère Tranche"
    )
    recu_tranche_1_valide = models.BooleanField(default=False, verbose_name="1ère Tranche validée")
    
    recu_tranche_2 = models.FileField(
        upload_to='inscriptions/recus/tranches/%Y/%m/',
        blank=True,
        null=True,
        verbose_name="Reçu 2ème Tranche"
    )
    recu_tranche_2_valide = models.BooleanField(default=False, verbose_name="2ème Tranche validée")
    
    recu_tranche_3 = models.FileField(
        upload_to='inscriptions/recus/tranches/%Y/%m/',
        blank=True,
        null=True,
        verbose_name="Reçu 3ème Tranche"
    )
    recu_tranche_3_valide = models.BooleanField(default=False, verbose_name="3ème Tranche validée")
    
    # Documents fournis
    documents_complets = models.BooleanField(default=False, verbose_name="Documents complets")
    
    # Métadonnées
    commentaire = models.TextField(blank=True, verbose_name="Commentaire")
    date_modification = models.DateTimeField(auto_now=True, verbose_name="Date de modification")
    
    class Meta:
        app_label = 'inscriptions'
        verbose_name = "Inscription"
        verbose_name_plural = "Inscriptions"
        unique_together = ['etudiant', 'annee_academique']
        ordering = ['-date_inscription']
        permissions = [
            ('peut_valider_inscriptions', 'Peut valider les inscriptions'),
            ('peut_valider_recus', 'Peut valider les reçus de paiement'),
            ('peut_exporter_inscriptions', 'Peut exporter les inscriptions'),
        ]
    
    def __str__(self):
        return f"{self.etudiant.get_nom_complet()} - {self.annee_academique.code}"
    
    def est_validee(self):
        """Vérifie si l'inscription est validée"""
        return self.statut == 'VALIDEE'
    
    def peut_acceder_cours(self):
        """Vérifie si l'étudiant peut accéder aux cours"""
        return (self.statut == 'VALIDEE' and 
                self.recu_preinscription_valide and 
                self.recu_tranche_1_valide)
    
    def statut_paiement(self):
        """Retourne le statut des paiements pour l'inscription"""
        return {
            'preinscription': self.recu_preinscription_valide,
            'tranche_1': self.recu_tranche_1_valide,
            'tranche_2': self.recu_tranche_2_valide,
            'tranche_3': self.recu_tranche_3_valide,
        }
    
    def pourcentage_paiement(self):
        """Calcule le pourcentage de paiement effectué"""
        statuts = self.statut_paiement()
        valides = sum(statuts.values())
        total = 4  # Pré-inscription + 3 tranches
        return (valides / total) * 100
    
    def valider_recu_preinscription(self, utilisateur):
        """Valider manuellement le reçu de pré-inscription"""
        self.recu_preinscription_valide = True
        self.save()
        
        # Créer une notification
        from apps.tableau_bord.models import Notification
        Notification.objects.create(
            utilisateur=self.etudiant.utilisateur,
            type='SUCCESS',
            titre='Reçu de pré-inscription validé',
            message='Votre reçu de pré-inscription a été validé. Vous pouvez maintenant compléter votre inscription.',
            lien='/inscriptions/'
        )
    
    def valider_recu_tranche(self, numero_tranche, utilisateur):
        """Valider manuellement un reçu de tranche"""
        if numero_tranche == 1:
            self.recu_tranche_1_valide = True
        elif numero_tranche == 2:
            self.recu_tranche_2_valide = True
        elif numero_tranche == 3:
            self.recu_tranche_3_valide = True
        
        self.save()
        
        # Créer une notification
        from apps.tableau_bord.models import Notification
        noms_tranches = {1: '1ère', 2: '2ème', 3: '3ème'}
        Notification.objects.create(
            utilisateur=self.etudiant.utilisateur,
            type='SUCCESS',
            titre=f'{noms_tranches[numero_tranche]} tranche validée',
            message=f'Votre reçu de la {noms_tranches[numero_tranche]} tranche a été validé.',
            lien='/inscriptions/'
        )


class DocumentInscription(models.Model):
    """Documents requis pour l'inscription"""
    TYPE_DOCUMENT_CHOICES = [
        ('EXTRAIT_NAISSANCE', 'Extrait de Naissance'),
        ('CNI', 'Carte Nationale d\'Identité'),
        ('PASSEPORT', 'Passeport'),
        ('BAC', 'Diplôme BAC'),
        ('RELEVE_BAC', 'Relevé de Notes BAC'),
        ('PHOTO', 'Photo d\'Identité'),
        ('CERTIFICAT_MEDICAL', 'Certificat Médical'),
        ('CV', 'Curriculum Vitae'),
        ('LETTRE_MOTIVATION', 'Lettre de Motivation'),
        ('RECOMMANDATION', 'Lettre de Recommandation'),
        ('AUTRE', 'Autre Document'),
    ]
    
    inscription = models.ForeignKey(
        Inscription,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    type_document = models.CharField(
        max_length=20,
        choices=TYPE_DOCUMENT_CHOICES,
        verbose_name="Type de document"
    )
    fichier = models.FileField(
        upload_to='inscriptions/documents/%Y/%m/',
        verbose_name="Fichier"
    )
    est_valide = models.BooleanField(default=False, verbose_name="Document validé")
    commentaire = models.TextField(blank=True, verbose_name="Commentaire")
    date_ajout = models.DateTimeField(auto_now_add=True, verbose_name="Date d'ajout")
    date_validation = models.DateTimeField(null=True, blank=True, verbose_name="Date de validation")
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents_valides',
        verbose_name="Validé par"
    )
    
    class Meta:
        app_label = 'inscriptions'
        verbose_name = "Document d'Inscription"
        verbose_name_plural = "Documents d'Inscription"
        ordering = ['-date_ajout']
    
    def __str__(self):
        return f"{self.get_type_document_display()} - {self.inscription.etudiant.get_nom_complet()}"
    
    def valider(self, utilisateur):
        """Valider le document"""
        self.est_valide = True
        self.date_validation = timezone.now()
        self.valide_par = utilisateur
        self.save()


class HistoriqueInscription(models.Model):
    """Historique des modifications d'inscription"""
    ACTION_CHOICES = [
        ('CREATION', 'Création'),
        ('MODIFICATION', 'Modification'),
        ('VALIDATION', 'Validation'),
        ('REJET', 'Rejet'),
        ('ANNULATION', 'Annulation'),
        ('RECU_TELEVERSE', 'Reçu téléversé'),
        ('RECU_VALIDE', 'Reçu validé'),
        ('DOCUMENT_AJOUTE', 'Document ajouté'),
        ('DOCUMENT_VALIDE', 'Document validé'),
    ]
    
    inscription = models.ForeignKey(
        Inscription,
        on_delete=models.CASCADE,
        related_name='historique'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name="Action")
    details = models.TextField(verbose_name="Détails")
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Utilisateur"
    )
    date_action = models.DateTimeField(auto_now_add=True, verbose_name="Date de l'action")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Adresse IP")
    
    class Meta:
        app_label = 'inscriptions'
        verbose_name = "Historique d'inscription"
        verbose_name_plural = "Historiques d'inscription"
        ordering = ['-date_action']
    
    def __str__(self):
        return f"{self.get_action_display()} - {self.inscription} - {self.date_action.strftime('%d/%m/%Y %H:%M')}"