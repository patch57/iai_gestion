"""
Modèles pour le tableau de bord
IAI-Cameroun - Centre de Douala
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta


class Notification(models.Model):
    """Notifications pour les utilisateurs"""
    TYPE_CHOICES = [
        ('INFO', 'Information'),
        ('SUCCESS', 'Succès'),
        ('WARNING', 'Avertissement'),
        ('ERROR', 'Erreur'),
    ]
    
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='INFO')
    titre = models.CharField(max_length=200)
    message = models.TextField()
    lien = models.URLField(blank=True, null=True)
    
    # Statut
    est_lue = models.BooleanField(default=False)
    date_lecture = models.DateTimeField(null=True, blank=True)
    
    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'tableau_bord'
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-date_creation']
    
    def __str__(self):
        return f"{self.titre} - {self.utilisateur}"


class Activite(models.Model):
    """Journal des activités du système"""
    TYPE_ACTION_CHOICES = [
        ('CONNEXION', 'Connexion'),
        ('DECONNEXION', 'Déconnexion'),
        ('CREATION', 'Création'),
        ('MODIFICATION', 'Modification'),
        ('SUPPRESSION', 'Suppression'),
        ('VALIDATION', 'Validation'),
        ('EXPORT', 'Export'),
        ('IMPORT', 'Import'),
        ('IMPRESSION', 'Impression'),
        ('PAIEMENT', 'Paiement'),
        ('PENALITE', 'Pénalité appliquée'),
    ]
    
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='activites'
    )
    type_action = models.CharField(max_length=20, choices=TYPE_ACTION_CHOICES)  # Augmenté à 20
    description = models.TextField()
    module = models.CharField(max_length=50)
    objet_id = models.PositiveIntegerField(null=True, blank=True)
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    
    # Métadonnées
    date_action = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'tableau_bord'
        verbose_name = "Activité"
        verbose_name_plural = "Activités"
        ordering = ['-date_action']
    
    def __str__(self):
        return f"{self.type_action} - {self.module} - {self.utilisateur}"


class Configuration(models.Model):
    """Configuration du système"""
    cle = models.CharField(max_length=100, unique=True)
    valeur = models.TextField()
    description = models.TextField(blank=True)
    est_modifiable = models.BooleanField(default=True)
    date_modification = models.DateTimeField(auto_now=True)
    modifie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    class Meta:
        app_label = 'tableau_bord'
        verbose_name = "Configuration"
        verbose_name_plural = "Configurations"
    
    def __str__(self):
        return self.cle
    
    @classmethod
    def get_valeur(cls, cle, default=None):
        """Récupère une valeur de configuration"""
        try:
            config = cls.objects.get(cle=cle)
            return config.valeur
        except cls.DoesNotExist:
            return default
    
    @classmethod
    def set_valeur(cls, cle, valeur, utilisateur=None):
        """Définit une valeur de configuration"""
        config, created = cls.objects.get_or_create(cle=cle)
        config.valeur = valeur
        if utilisateur:
            config.modifie_par = utilisateur
        config.save()
        return config


class Rapport(models.Model):
    """Rapports générés par le système"""
    TYPE_RAPPORT_CHOICES = [
        ('EFFECTIFS', 'Effectifs Étudiants'),
        ('RESULTATS', 'Résultats Académiques'),
        ('FINANCIER', 'Rapport Financier'),
        ('PRESENCE', 'Rapport de Présence'),
        ('PAIEMENT', 'Rapport de Paiement'),
        ('PENALITES', 'Rapport des Pénalités'),
        ('STATISTIQUE', 'Rapport Statistique'),
        ('CUSTOM', 'Rapport Personnalisé'),
    ]
    
    type_rapport = models.CharField(max_length=15, choices=TYPE_RAPPORT_CHOICES)
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Fichier
    fichier = models.FileField(upload_to='rapports/', blank=True, null=True)
    format = models.CharField(
        max_length=10,
        choices=[('PDF', 'PDF'), ('EXCEL', 'Excel'), ('CSV', 'CSV')],
        default='PDF'
    )
    
    # Paramètres
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    filiere = models.ForeignKey(
        'etudiants.Filiere',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    annee_academique = models.CharField(max_length=9, default='2024-2025')
    
    # Métadonnées
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='rapports_crees'
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    est_archive = models.BooleanField(default=False)
    
    class Meta:
        app_label = 'tableau_bord'
        verbose_name = "Rapport"
        verbose_name_plural = "Rapports"
        ordering = ['-date_creation']
    
    def __str__(self):
        return f"{self.titre} - {self.date_creation}"


class Statistique(models.Model):
    """Statistiques du système"""
    TYPE_STAT_CHOICES = [
        ('EFFECTIF_TOTAL', 'Effectif Total Étudiants'),
        ('EFFECTIF_FILIERE', 'Effectif par Filière'),
        ('EFFECTIF_NIVEAU', 'Effectif par Niveau'),
        ('TAUX_REUSSITE', 'Taux de Réussite'),
        ('TAUX_ECHEC', "Taux d'Échec"),
        ('TAUX_ABANDON', "Taux d'Abandon"),
        ('RECETTES', 'Recettes Totales'),
        ('RECETTES_PENALITES', 'Recettes avec Pénalités'),
        ('PENALITES_TOTALES', 'Total des Pénalités'),
        ('IMPAYES', 'Impayés'),
        ('MOYENNE_GENERALE', 'Moyenne Générale'),
    ]
    
    type_stat = models.CharField(
        max_length=25,  # Augmenté à 25 pour accommoder tous les choix
        choices=TYPE_STAT_CHOICES,
        verbose_name="Type de statistique"
    )
    valeur = models.DecimalField(max_digits=15, decimal_places=2)
    valeur_texte = models.CharField(max_length=200, blank=True)
    
    # Contexte
    filiere = models.ForeignKey(
        'etudiants.Filiere',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    annee_academique = models.CharField(max_length=9, default='2024-2025')
    semestre = models.PositiveIntegerField(null=True, blank=True)
    
    # Métadonnées
    date_calcul = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'tableau_bord'
        verbose_name = "Statistique"
        verbose_name_plural = "Statistiques"
        ordering = ['-date_calcul']
    
    def __str__(self):
        return f"{self.get_type_stat_display()} - {self.valeur}"


class Message(models.Model):
    """Messages entre utilisateurs"""
    expediteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='messages_envoyes'
    )
    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='messages_recus'
    )
    sujet = models.CharField(max_length=200)
    contenu = models.TextField()
    
    # Statut
    est_lu = models.BooleanField(default=False)
    date_lecture = models.DateTimeField(null=True, blank=True)
    
    # Métadonnées
    date_envoi = models.DateTimeField(auto_now_add=True)
    est_important = models.BooleanField(default=False)
    
    class Meta:
        app_label = 'tableau_bord'
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ['-date_envoi']
    
    def __str__(self):
        return f"{self.sujet} - De: {self.expediteur} À: {self.destinataire}"


class Tache(models.Model):
    """Tâches à effectuer"""
    PRIORITE_CHOICES = [
        ('BASSE', 'Basse'),
        ('MOYENNE', 'Moyenne'),
        ('HAUTE', 'Haute'),
        ('URGENTE', 'Urgente'),
    ]
    
    STATUT_CHOICES = [
        ('A_FAIRE', 'À Faire'),
        ('EN_COURS', 'En Cours'),
        ('TERMINEE', 'Terminée'),
        ('ANNULEE', 'Annulée'),
    ]
    
    titre = models.CharField(max_length=200)
    description = models.TextField()
    assignee_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='taches_assignees'
    )
    assignee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='taches_assignees_par'
    )
    
    # Priorité et statut
    priorite = models.CharField(max_length=10, choices=PRIORITE_CHOICES, default='MOYENNE')
    statut = models.CharField(max_length=10, choices=STATUT_CHOICES, default='A_FAIRE')
    
    # Dates
    date_creation = models.DateTimeField(auto_now_add=True)
    date_echeance = models.DateTimeField()
    date_completion = models.DateTimeField(null=True, blank=True)
    
    # Module concerné
    module = models.CharField(
        max_length=50,
        choices=[
            ('ETUDIANTS', 'Étudiants'),
            ('PROFESSEURS', 'Professeurs'),
            ('COURS', 'Cours'),
            ('NOTES', 'Notes'),
            ('INSCRIPTIONS', 'Inscriptions'),
            ('PAIEMENTS', 'Paiements'),
            ('GENERAL', 'Général'),
        ],
        default='GENERAL'
    )
    
    class Meta:
        app_label = 'tableau_bord'
        verbose_name = "Tâche"
        verbose_name_plural = "Tâches"
        ordering = ['-priorite', 'date_echeance']
    
    def __str__(self):
        return f"{self.titre} - {self.assignee_a}"
    
    def est_en_retard(self):
        """Vérifie si la tâche est en retard"""
        return self.statut != 'TERMINEE' and self.date_echeance < timezone.now()


class PenalitePaiement(models.Model):
    """
    Modèle pour gérer les pénalités de retard de paiement
    Règles IAI-Cameroun:
    - Pré-inscription: 1500 FCFA/semaine de retard
    - 1ère, 2ème, 3ème tranche: 3000 FCFA/semaine de retard par tranche
    """
    
    TRANCHES = [
        ('PREINSCRIPTION', 'Pré-inscription'),
        ('TRANCHE_1', '1ère Tranche'),
        ('TRANCHE_2', '2ème Tranche'),
        ('TRANCHE_3', '3ème Tranche'),
    ]
    
    etudiant = models.ForeignKey(
        'etudiants.Etudiant',
        on_delete=models.CASCADE,
        related_name='penalites'
    )
    tranche = models.CharField(max_length=20, choices=TRANCHES)
    montant_initial = models.DecimalField(max_digits=10, decimal_places=2)
    montant_penalite = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    montant_total = models.DecimalField(max_digits=10, decimal_places=2)
    
    date_limite = models.DateField()
    date_paiement = models.DateField(null=True, blank=True)
    semaines_retard = models.PositiveIntegerField(default=0)
    est_regle = models.BooleanField(default=False)
    
    # Métadonnées
    date_calcul = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'tableau_bord'
        verbose_name = "Pénalité de paiement"
        verbose_name_plural = "Pénalités de paiement"
        unique_together = ['etudiant', 'tranche']
        ordering = ['-date_calcul']
    
    def __str__(self):
        return f"{self.etudiant} - {self.get_tranche_display()} - Pénalité: {self.montant_penalite} FCFA"
    
    def calculer_penalite(self, date_paiement=None):
        """
        Calcule la pénalité selon les règles IAI-Cameroun
        Pré-inscription: 1500 FCFA/semaine
        Autres tranches: 3000 FCFA/semaine
        """
        if date_paiement:
            paiement_date = date_paiement
        else:
            paiement_date = timezone.now().date()
        
        if paiement_date <= self.date_limite:
            self.semaines_retard = 0
            self.montant_penalite = 0
        else:
            # Calculer le nombre de semaines de retard
            delta = paiement_date - self.date_limite
            self.semaines_retard = (delta.days + 6) // 7  # Arrondi à la semaine supérieure
            
            # Appliquer le tarif selon la tranche
            if self.tranche == 'PREINSCRIPTION':
                penalite_par_semaine = 1500
            else:
                penalite_par_semaine = 3000
            
            self.montant_penalite = self.semaines_retard * penalite_par_semaine
        
        self.montant_total = self.montant_initial + self.montant_penalite
        return self.montant_penalite
    
    def marquer_paye(self, date_paiement=None):
        """Marque la pénalité comme payée"""
        if date_paiement:
            self.date_paiement = date_paiement
        else:
            self.date_paiement = timezone.now().date()
        
        self.calculer_penalite(self.date_paiement)
        self.est_regle = True
        self.save()
        
        # Créer une notification pour l'étudiant
        Notification.objects.create(
            utilisateur=self.etudiant.utilisateur,
            type='SUCCESS',
            titre='Paiement enregistré',
            message=f"Votre paiement pour {self.get_tranche_display()} a été enregistré. "
                    f"Montant total: {self.montant_total:,.0f} FCFA "
                    f"(dont {self.montant_penalite:,.0f} FCFA de pénalités).",
            lien='/paiements/'
        )
    
    def get_penalite_formatee(self):
        """Retourne la pénalité formatée"""
        if self.montant_penalite > 0:
            return f"{self.montant_penalite:,.0f} FCFA ({self.semaines_retard} semaine(s) de retard)"
        return "Aucune pénalité"


class HistoriquePenalite(models.Model):
    """Historique des pénalités appliquées"""
    penalite = models.ForeignKey(
        PenalitePaiement,
        on_delete=models.CASCADE,
        related_name='historique'
    )
    ancien_montant_penalite = models.DecimalField(max_digits=10, decimal_places=2)
    nouveau_montant_penalite = models.DecimalField(max_digits=10, decimal_places=2)
    ancien_semaines_retard = models.PositiveIntegerField()
    nouveau_semaines_retard = models.PositiveIntegerField()
    date_modification = models.DateTimeField(auto_now_add=True)
    modifie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='modifications_penalites'
    )
    raison = models.TextField(blank=True)
    
    class Meta:
        app_label = 'tableau_bord'
        verbose_name = "Historique des pénalités"
        verbose_name_plural = "Historique des pénalités"
        ordering = ['-date_modification']
    
    def __str__(self):
        return f"{self.penalite.etudiant} - {self.penalite.get_tranche_display()} - {self.date_modification}"


class AlertePaiement(models.Model):
    """Alertes pour les paiements en retard"""
    TYPE_ALERTE = [
        ('ECHEANCE_PROCHAIN', 'Échéance proche'),
        ('RETARD', 'En retard'),
        ('PENALITE', 'Pénalité appliquée'),
        ('RAPPEL', 'Rappel'),
    ]
    
    etudiant = models.ForeignKey(
        'etudiants.Etudiant',
        on_delete=models.CASCADE,
        related_name='alertes_paiement'
    )
    tranche = models.CharField(max_length=20, choices=PenalitePaiement.TRANCHES)
    type_alerte = models.CharField(max_length=20, choices=TYPE_ALERTE)
    message = models.TextField()
    montant_penalite = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date_envoi = models.DateTimeField(auto_now_add=True)
    est_envoyee = models.BooleanField(default=False)
    date_lecture = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        app_label = 'tableau_bord'
        verbose_name = "Alerte paiement"
        verbose_name_plural = "Alertes paiements"
        ordering = ['-date_envoi']
    
    def __str__(self):
        return f"{self.etudiant} - {self.get_tranche_display()} - {self.get_type_alerte_display()}"
    
    @classmethod
    def generer_alertes_retard(cls):
        """Génère automatiquement les alertes pour les paiements en retard"""
        from apps.paiements.models import TranchePaiement
        from apps.etudiants.models import Etudiant
        
        alertes_crees = 0
        date_aujourdhui = timezone.now().date()
        
        # Récupérer toutes les tranches actives
        tranches_actives = TranchePaiement.objects.filter(est_actif=True)
        
        for etudiant in Etudiant.objects.filter(statut__in=['INSCRIT', 'ACTIF']):
            for tranche in tranches_actives:
                # Vérifier si la tranche est déjà payée
                from apps.paiements.models import RecuPaiement
                recu = RecuPaiement.objects.filter(
                    etudiant=etudiant,
                    tranche=tranche,
                    statut='VALIDE'
                ).first()
                
                if recu:
                    continue
                
                # Vérifier si une alerte existe déjà
                alerte_existante = cls.objects.filter(
                    etudiant=etudiant,
                    tranche=tranche.get_numero_display().upper().replace(' ', '_'),
                    type_alerte='RETARD'
                ).exists()
                
                if alerte_existante:
                    continue
                
                # Calculer le retard
                if date_aujourdhui > tranche.date_limite:
                    delta = date_aujourdhui - tranche.date_limite
                    semaines_retard = (delta.days + 6) // 7
                    
                    if tranche.numero == 1:
                        penalite = semaines_retard * 1500
                    else:
                        penalite = semaines_retard * 3000
                    
                    message = f"⚠️ Paiement de {tranche.get_numero_display()} en retard. "
                    message += f"Pénalité: {penalite:,.0f} FCFA ({semaines_retard} semaine(s) de retard). "
                    message += f"Montant total dû: {tranche.montant + penalite:,.0f} FCFA."
                    
                    cls.objects.create(
                        etudiant=etudiant,
                        tranche=tranche.get_numero_display().upper().replace(' ', '_'),
                        type_alerte='RETARD',
                        message=message,
                        montant_penalite=penalite,
                        est_envoyee=True
                    )
                    alertes_crees += 1
        
        return alertes_crees


class ReglementInterieur(models.Model):
    """
    Modèle de stockage du règlement intérieur de l'établissement.
    Seul le règlement le plus récent marqué comme actif sera téléchargeable par les utilisateurs.
    """
    titre = models.CharField(
        max_length=150,
        default="Règlement Intérieur IAI-Cameroun",
        verbose_name="Titre"
    )
    fichier = models.FileField(
        upload_to='reglements/',
        verbose_name="Fichier PDF"
    )
    date_televersement = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de téléversement"
    )
    est_actif = models.BooleanField(
        default=True,
        verbose_name="Règlement actif"
    )

    class Meta:
        app_label = 'tableau_bord'
        verbose_name = "Règlement Intérieur"
        verbose_name_plural = "Règlements Intérieurs"
        ordering = ['-date_televersement']

    def __str__(self):
        return f"{self.titre} - {self.date_televersement.strftime('%d/%m/%Y')}"

    def save(self, *args, **kwargs):
        # Désactiver les autres règlements si celui-ci est actif
        if self.est_actif:
            ReglementInterieur.objects.filter(est_actif=True).exclude(pk=self.pk).update(est_actif=False)
        super().save(*args, **kwargs)