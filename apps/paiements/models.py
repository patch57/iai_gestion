"""
Modèles pour la gestion des paiements et reçus
Avec système d'IA pour la vérification des reçus bancaires
IAI-Cameroun - Centre de Douala
"""
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
import os


def recu_upload_path(instance, filename):
    """Chemin de stockage des reçus"""
    ext = filename.split('.')[-1]
    filename = f"{instance.etudiant.matricule}_tranche_{instance.tranche.numero}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
    return os.path.join('recus', str(instance.tranche.annee_academique), filename)


class TranchePaiement(models.Model):
    """
    Tranches de paiement pour l'année académique
    Règles IAI: 4 tranches (pré-inscription + 3 tranches)
    """
    
    NUMERO_TRANCHE = [
        (1, 'Pré-inscription'),
        (2, '1ère Tranche'),
        (3, '2ème Tranche'),
        (4, '3ème Tranche'),
    ]
    
    numero = models.IntegerField(
        choices=NUMERO_TRANCHE,
        verbose_name="Numéro de la tranche"
    )
    montant = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Montant (FCFA)"
    )
    date_limite = models.DateField(
        verbose_name="Date limite de paiement"
    )
    annee_academique = models.CharField(
        max_length=20,
        verbose_name="Année académique",
        help_text="Format: 2024-2025"
    )
    est_actif = models.BooleanField(
        default=True,
        verbose_name="Tranche active"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description"
    )
    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )
    date_modification = models.DateTimeField(
        auto_now=True,
        verbose_name="Date de modification"
    )
    
    class Meta:
        app_label = 'paiements'
        verbose_name = "Tranche de paiement"
        verbose_name_plural = "Tranches de paiement"
        ordering = ['numero']
        unique_together = ['numero', 'annee_academique']
    
    def __str__(self):
        return f"Tranche {self.numero} - {self.get_numero_display()} - {self.montant:,.0f} FCFA ({self.annee_academique})"
    
    def clean(self):
        """Validation des montants selon les nouvelles tranches IAI-Cameroun"""
        if self.numero == 1 and self.montant not in [71000, 84000, 50000]:
            raise ValidationError({
                'montant': 'La pré-inscription doit être de 71 000 FCFA pour le Niveau 2'
            })

        elif self.numero == 2 and self.montant != 175000:
            raise ValidationError({
                'montant': 'La 1ère tranche doit être de 175 000 FCFA'
            })
        elif self.numero == 3 and self.montant != 115000:
            raise ValidationError({
                'montant': 'La 2ème tranche doit être de 115 000 FCFA'
            })
        elif self.numero == 4 and self.montant != 100000:
            raise ValidationError({
                'montant': 'La 3ème tranche doit être de 100 000 FCFA'
            })
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    def est_depassee(self):
        """Vérifie si la date limite est dépassée"""
        from django.utils import timezone
        return self.date_limite < timezone.now().date()
    
    def jours_restants(self):
        """Retourne le nombre de jours restants avant la date limite"""
        from django.utils import timezone
        if self.est_depassee():
            return 0
        delta = self.date_limite - timezone.now().date()
        return delta.days

    def semaines_depassement(self):
        """Nombre de semaines de dépassement de l'échéance"""
        if not self.est_depassee():
            return 0
        from django.utils import timezone
        delta_days = (timezone.now().date() - self.date_limite).days
        w = delta_days // 7
        return w if w >= 1 else 1



class RecuPaiement(models.Model):
    """
    Reçu de paiement téléversé par l'étudiant
    Vérifié par l'IA puis par l'admin financier
    """
    
    STATUT_VERIFICATION = [
        ('EN_ATTENTE', 'En attente de vérification'),
        ('IA_VERIFIE', 'Vérifié par IA'),
        ('VALIDE', 'Validé'),
        ('REJETE', 'Rejeté'),
        ('DUPLICATA', 'Duplicata'),
    ]
    
    # Relations
    etudiant = models.ForeignKey(
        'etudiants.Etudiant',
        on_delete=models.CASCADE,
        related_name='recus',
        verbose_name="Étudiant"
    )
    tranche = models.ForeignKey(
        TranchePaiement,
        on_delete=models.CASCADE,
        related_name='recus',
        verbose_name="Tranche de paiement"
    )
    
    # Fichier et informations
    recu_fichier = models.FileField(
        upload_to=recu_upload_path,
        verbose_name="Reçu bancaire",
        help_text="Format acceptés: PDF, JPG, PNG (max 5MB)"
    )
    date_televersement = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de téléversement"
    )
    montant_mentionne = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Montant mentionné sur le reçu"
    )
    reference_recu = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Référence du reçu",
        help_text="Référence bancaire mentionnée sur le reçu"
    )
    date_paiement = models.DateField(
        blank=True,
        null=True,
        verbose_name="Date de paiement",
        help_text="Date de paiement mentionnée sur le reçu"
    )
    
    # Statut et vérification
    statut = models.CharField(
        max_length=20,
        choices=STATUT_VERIFICATION,
        default='EN_ATTENTE',
        verbose_name="Statut de vérification"
    )
    commentaires = models.TextField(
        blank=True,
        verbose_name="Commentaires",
        help_text="Commentaires sur la vérification"
    )
    
    # Champs pour l'IA
    score_confiance = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Score de confiance IA",
        help_text="Score entre 0 et 1 (1 = très fiable)"
    )
    anomalies_detectees = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Anomalies détectées",
        help_text="Anomalies détectées par l'IA"
    )
    verification_ia = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Résultat vérification IA",
        help_text="Données extraites par l'IA"
    )
    ia_version = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Version IA",
        help_text="Version du modèle d'IA utilisé"
    )
    
    # Vérification manuelle
    verifie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verifications_effectuees',
        verbose_name="Vérifié par"
    )
    date_verification = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de vérification"
    )
    
    # Métadonnées
    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )
    date_modification = models.DateTimeField(
        auto_now=True,
        verbose_name="Date de modification"
    )
    
    class Meta:
        app_label = 'paiements'
        verbose_name = "Reçu de paiement"
        verbose_name_plural = "Reçus de paiement"
        ordering = ['-date_televersement']
        permissions = [
            ('peut_verifier_recus', 'Peut vérifier les reçus de paiement'),
            ('peut_exporter_recus', 'Peut exporter les reçus'),
            ('peut_analyser_ia', 'Peut utiliser l\'IA pour analyser les reçus'),
        ]
    
    def __str__(self):
        return f"{self.etudiant.get_nom_complet()} - Tranche {self.tranche.numero} - {self.get_statut_display()}"
    
    def clean(self):
        """Validation des données"""
        super().clean()
        
        # Vérifier que le montant est cohérent
        if self.montant_mentionne and self.montant_mentionne <= 0:
            raise ValidationError({
                'montant_mentionne': 'Le montant mentionné doit être supérieur à 0'
            })
        
        # Vérifier qu'on ne soumet pas deux fois la même tranche
        if not self.pk:
            recu_existant = RecuPaiement.objects.filter(
                etudiant=self.etudiant,
                tranche=self.tranche,
                statut__in=['EN_ATTENTE', 'IA_VERIFIE', 'VALIDE']
            ).exists()
            if recu_existant:
                raise ValidationError({
                    'tranche': 'Un reçu pour cette tranche est déjà en cours de vérification'
                })
    
    def save(self, *args, **kwargs):
        """Sauvegarde avec gestion du statut"""
        # Mettre à jour la date de vérification si le statut change
        if self.pk:
            old_status = RecuPaiement.objects.get(pk=self.pk).statut
            if old_status != self.statut and self.statut in ['VALIDE', 'REJETE', 'DUPLICATA']:
                self.date_verification = timezone.now()
        
        self.full_clean()
        super().save(*args, **kwargs)
        
        # Si le reçu est validé, mettre à jour le statut de l'étudiant
        if self.statut == 'VALIDE':
            if self.tranche.numero == 1:  # Pré-inscription
                self.etudiant.recu_preinscription_valide = True
                if self.etudiant.statut == 'PREINSCRIT':
                    self.etudiant.statut = 'INSCRIT'
                self.etudiant.save(update_fields=['recu_preinscription_valide', 'statut'])
    
    # ========== MÉTHODES MÉTIER ==========
    
    def est_valide(self):
        """Vérifie si le reçu est validé"""
        return self.statut == 'VALIDE'
    
    def est_rejete(self):
        """Vérifie si le reçu est rejeté"""
        return self.statut == 'REJETE'
    
    def est_en_attente(self):
        """Vérifie si le reçu est en attente"""
        return self.statut in ['EN_ATTENTE', 'IA_VERIFIE']
    
    def peut_etre_verifie_manuellement(self):
        """Vérifie si le reçu peut être vérifié manuellement"""
        return self.statut in ['EN_ATTENTE', 'IA_VERIFIE']
    
    def get_score_confiance_pourcentage(self):
        """Retourne le score de confiance en pourcentage"""
        if self.score_confiance:
            return round(self.score_confiance * 100, 2)
        return None
    
    def get_anomalies_list(self):
        """Retourne la liste des anomalies détectées"""
        if self.anomalies_detectees:
            return self.anomalies_detectees.get('anomalies', [])
        return []
    
    def a_des_anomalies(self):
        """Vérifie si des anomalies ont été détectées"""
        return len(self.get_anomalies_list()) > 0
    
    def est_duplicata_potentiel(self):
        """Vérifie s'il existe des duplicatas potentiels"""
        recus_similaires = RecuPaiement.objects.filter(
            etudiant=self.etudiant,
            tranche=self.tranche,
            montant_mentionne=self.montant_mentionne,
            date_televersement__gte=timezone.now() - timezone.timedelta(days=1)
        ).exclude(pk=self.pk)
        return recus_similaires.exists()
    
    def get_nom_fichier(self):
        """Retourne le nom du fichier uploadé"""
        if self.recu_fichier:
            return os.path.basename(self.recu_fichier.name)
        return None
    
    def valider_manuellement(self, utilisateur, commentaires=""):
        """Validation manuelle du reçu"""
        self.statut = 'VALIDE'
        self.verifie_par = utilisateur
        self.date_verification = timezone.now()
        self.commentaires = commentaires
        self.save()
    
    def rejeter_manuellement(self, utilisateur, commentaires=""):
        """Rejet manuel du reçu"""
        self.statut = 'REJETE'
        self.verifie_par = utilisateur
        self.date_verification = timezone.now()
        self.commentaires = commentaires
        self.save()
    
    def marquer_duplicata(self, utilisateur, commentaires=""):
        """Marquer comme duplicata"""
        self.statut = 'DUPLICATA'
        self.verifie_par = utilisateur
        self.date_verification = timezone.now()
        self.commentaires = commentaires
        self.save()
    
    def analyser_par_ia(self, donnees_ia):
        """
        Analyse du reçu par l'IA
        Données extraites par l'IA et mise à jour
        """
        self.verification_ia = donnees_ia.get('extraction', {})
        self.score_confiance = donnees_ia.get('score_confiance', 0)
        self.anomalies_detectees = donnees_ia.get('anomalies', {})
        self.ia_version = donnees_ia.get('version', '1.0')
        
        # Mettre à jour les champs si l'IA a extrait des données
        if self.verification_ia.get('montant'):
            self.montant_mentionne = self.verification_ia.get('montant')
        if self.verification_ia.get('reference'):
            self.reference_recu = self.verification_ia.get('reference')
        if self.verification_ia.get('date_paiement'):
            self.date_paiement = self.verification_ia.get('date_paiement')
        
        # Si score très élevé, on peut passer en vérifié automatiquement
        if self.score_confiance and self.score_confiance >= 0.95:
            self.statut = 'IA_VERIFIE'
            self.commentaires = "Vérifié automatiquement par l'IA (score très élevé)"
        else:
            self.statut = 'EN_ATTENTE'
            self.commentaires = "En attente de vérification manuelle"
        
        self.save()


class HistoriquePaiement(models.Model):
    """
    Historique des actions sur les paiements
    Pour traçabilité et audit
    """
    ACTION_CHOICES = [
        ('TELEVERSEMENT', 'Téléversement'),
        ('IA_ANALYSE', 'Analyse IA'),
        ('VERIFICATION_MANUELLE', 'Vérification manuelle'),
        ('VALIDATION', 'Validation'),
        ('REJET', 'Rejet'),
        ('DUPLICATA', 'Duplicata'),
    ]
    
    recu = models.ForeignKey(
        RecuPaiement,
        on_delete=models.CASCADE,
        related_name='historique',
        verbose_name="Reçu"
    )
    action = models.CharField(
        max_length=30,  # Changement: 20 -> 30 pour accommoder 'VERIFICATION_MANUELLE' (21 caractères)
        choices=ACTION_CHOICES,
        verbose_name="Action"
    )
    details = models.TextField(
        blank=True,
        verbose_name="Détails"
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Utilisateur"
    )
    date_action = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de l'action"
    )
    ip_address = models.GenericIPAddressField(
        blank=True,
        null=True,
        verbose_name="Adresse IP"
    )
    
    class Meta:
        app_label = 'paiements'
        verbose_name = "Historique paiement"
        verbose_name_plural = "Historique paiements"
        ordering = ['-date_action']
    
    def __str__(self):
        return f"{self.get_action_display()} - {self.recu} - {self.date_action.strftime('%d/%m/%Y %H:%M')}"


class SessionConcours(models.Model):
    """
    Sessions de Concours d'Entrée pour les Étudiants de Niveau 1 (IAI-Cameroun)
    """
    nom = models.CharField(max_length=100, verbose_name="Nom de la session", help_text="Ex: Session de Juin 2026, Session d'Août 2026")
    code = models.CharField(max_length=30, unique=True, verbose_name="Code unique", help_text="Ex: SESS_JUIN_2026")
    date_concours = models.DateField(verbose_name="Date d'organisation du concours")
    annee_academique = models.CharField(max_length=20, default='2024-2025', verbose_name="Année académique")
    est_active = models.BooleanField(default=True, verbose_name="Session active")
    description = models.TextField(blank=True, verbose_name="Description / Remarques")
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'paiements'
        verbose_name = "Session de Concours (Niveau 1)"
        verbose_name_plural = "Sessions de Concours (Niveau 1)"
        ordering = ['date_concours']

    def __str__(self):
        return f"{self.nom} ({self.date_concours.strftime('%d/%m/%Y')})"


class EcheanceSessionNiveau1(models.Model):
    """
    Échéances de paiement spécifiques par Session de Concours pour les étudiants du Niveau 1
    """
    session_concours = models.ForeignKey(SessionConcours, on_delete=models.CASCADE, related_name='echeances')
    tranche_numero = models.IntegerField(choices=TranchePaiement.NUMERO_TRANCHE, verbose_name="Tranche de paiement")
    montant = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Montant (FCFA)")
    date_limite = models.DateField(verbose_name="Date limite de paiement")
    description = models.CharField(max_length=200, blank=True, verbose_name="Remarques / Conditions")
    
    class Meta:
        app_label = 'paiements'
        verbose_name = "Échéance Niveau 1 par Session"
        verbose_name_plural = "Échéances Niveau 1 par Session"
        unique_together = ['session_concours', 'tranche_numero']
        ordering = ['session_concours', 'tranche_numero']

    def __str__(self):
        return f"{self.session_concours.nom} - Tranche {self.tranche_numero} : {self.date_limite.strftime('%d/%m/%Y')}"


class ResultatConcours(models.Model):
    """
    Résultats d'admission au concours d'entrée (Niveau 1) importés par le Chef Comptabilité
    """
    STATUT_ADMISSION_CHOICES = [
        ('ADMIS', 'Admis'),
        ('LISTE_ATTENTE', 'Liste d\'attente'),
    ]

    STATUT_PREINSCRIPTION_CHOICES = [
        ('NON_PAYE', 'Non payé'),
        ('PAYE', 'Payé (84 000 FCFA)'),
    ]


    session_concours = models.ForeignKey(
        SessionConcours,
        on_delete=models.CASCADE,
        related_name='resultats',
        verbose_name="Session de Concours"
    )
    numero_table = models.CharField(
        max_length=50,
        verbose_name="N° de Table / Dossier",
        help_text="N° Anonymat ou N° de dossier du candidat"
    )
    nom = models.CharField(max_length=100, verbose_name="Nom")
    prenom = models.CharField(max_length=100, verbose_name="Prénom")
    email = models.EmailField(blank=True, null=True, verbose_name="Adresse Email")
    telephone = models.CharField(max_length=30, blank=True, null=True, verbose_name="Téléphone")
    filiere = models.ForeignKey(
        'etudiants.Filiere',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Filière d'affectation"
    )
    statut_admission = models.CharField(
        max_length=20,
        choices=STATUT_ADMISSION_CHOICES,
        default='ADMIS',
        verbose_name="Statut d'admission"
    )
    statut_preinscription = models.CharField(
        max_length=20,
        choices=STATUT_PREINSCRIPTION_CHOICES,
        default='NON_PAYE',
        verbose_name="Statut 1ère Tranche (Pré-inscription 84k)"
    )
    statut_tranche2 = models.CharField(
        max_length=20,
        choices=[('NON_PAYE', 'Non payé'), ('PAYE', 'Payé')],
        default='NON_PAYE',
        verbose_name="Statut 2ème Tranche"
    )
    statut_tranche3 = models.CharField(
        max_length=20,
        choices=[('NON_PAYE', 'Non payé'), ('PAYE', 'Payé')],
        default='NON_PAYE',
        verbose_name="Statut 3ème Tranche"
    )
    statut_tranche4 = models.CharField(
        max_length=20,
        choices=[('NON_PAYE', 'Non payé'), ('PAYE', 'Payé')],
        default='NON_PAYE',
        verbose_name="Statut 4ème Tranche"
    )


    etudiant_cree = models.ForeignKey(
        'etudiants.Etudiant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resultat_concours',
        verbose_name="Profil Étudiant Associé"
    )
    date_importation = models.DateTimeField(auto_now_add=True, verbose_name="Date d'importation")
    importe_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Importé par"
    )

    class Meta:
        app_label = 'paiements'
        verbose_name = "Résultat de Concours"
        verbose_name_plural = "Résultats de Concours"
        ordering = ['session_concours', 'nom', 'prenom']
        unique_together = ['session_concours', 'numero_table']

    def __str__(self):
        return f"{self.numero_table} - {self.nom} {self.prenom} ({self.get_statut_admission_display()})"
