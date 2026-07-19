"""
Modèles pour la gestion des cours
IAI-Cameroun - Centre de Douala
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class Salle(models.Model):
    """Salles de cours de l'IAI"""
    TYPE_SALLE_CHOICES = [
        ('COURS', 'Salle de Cours'),
        ('TP', 'Salle de TP'),
        ('LABO', 'Laboratoire'),
        ('AMPHI', 'Amphithéâtre'),
        ('REUNION', 'Salle de Réunion'),
    ]
    
    code = models.CharField(max_length=10, unique=True)
    nom = models.CharField(max_length=100)
    type_salle = models.CharField(max_length=10, choices=TYPE_SALLE_CHOICES, default='COURS')
    capacite = models.PositiveIntegerField(default=30)
    etage = models.PositiveIntegerField(default=0)
    est_equipee = models.BooleanField(default=True, help_text="Est équipée pour les cours")
    a_projecteur = models.BooleanField(default=False)
    a_climatisation = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    est_disponible = models.BooleanField(default=True)
    
    class Meta:
        app_label = 'cours'
        verbose_name = "Salle"
        verbose_name_plural = "Salles"
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.nom} ({self.capacite} places)"


class Matiere(models.Model):
    """Matières enseignées à l'IAI"""
    code = models.CharField(max_length=20, unique=True)
    nom = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    credits = models.PositiveIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(30)]
    )
    heures_cours = models.PositiveIntegerField(default=30)
    heures_td = models.PositiveIntegerField(default=15)
    heures_tp = models.PositiveIntegerField(default=0)
    semestre = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(2)]
    )
    est_optionnelle = models.BooleanField(default=False)
    prerequis = models.ManyToManyField('self', blank=True, symmetrical=False)
    
    class Meta:
        app_label = 'cours'
        verbose_name = "Matière"
        verbose_name_plural = "Matières"
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.nom}"
    
    def get_heures_totales(self):
        return self.heures_cours + self.heures_td + self.heures_tp


class Cours(models.Model):
    """Cours dispensés dans une filière"""
    
    TYPE_COURS_CHOICES = [
        ('COURS', 'Cours Magistral'),
        ('TD', 'Travaux Dirigés'),
        ('TP', 'Travaux Pratiques'),
    ]
    
    code = models.CharField(max_length=20, unique=True)
    matiere = models.ForeignKey(Matiere, on_delete=models.PROTECT, related_name='cours')
    filiere = models.ForeignKey('etudiants.Filiere', on_delete=models.PROTECT, related_name='cours')
    professeur = models.ForeignKey(
        'professeurs.Professeur',
        on_delete=models.PROTECT,
        related_name='cours_assignes'
    )
    type_cours = models.CharField(max_length=10, choices=TYPE_COURS_CHOICES, default='COURS')
    annee_academique = models.CharField(max_length=9, default='2024-2025')
    
    # Horaires
    jour = models.CharField(
        max_length=10,
        choices=[
            ('Lundi', 'Lundi'),
            ('Mardi', 'Mardi'),
            ('Mercredi', 'Mercredi'),
            ('Jeudi', 'Jeudi'),
            ('Vendredi', 'Vendredi'),
            ('Samedi', 'Samedi'),
        ]
    )
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    salle = models.ForeignKey(Salle, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Informations complémentaires
    capacite_max = models.PositiveIntegerField(default=50)
    est_actif = models.BooleanField(default=True)
    date_debut = models.DateField()
    date_fin = models.DateField()
    
    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'cours'
        verbose_name = "Cours"
        verbose_name_plural = "Cours"
        ordering = ['code']
        unique_together = ['matiere', 'filiere', 'type_cours', 'annee_academique']
    
    def __str__(self):
        return f"{self.code} - {self.matiere.nom} ({self.filiere})"
    
    def get_nombre_inscrits(self):
        """Retourne le nombre d'étudiants inscrits"""
        return self.inscriptions_cours.filter(est_actif=True).count()
    
    def get_places_disponibles(self):
        return self.capacite_max - self.get_nombre_inscrits()
    
    def est_complet(self):
        return self.get_nombre_inscrits() >= self.capacite_max


class SeanceCours(models.Model):
    """Séances de cours individuelles"""
    cours = models.ForeignKey(Cours, on_delete=models.CASCADE, related_name='seances')
    date = models.DateField()
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    duree_heures = models.DecimalField(max_digits=4, decimal_places=2, default=2)
    salle = models.ForeignKey(Salle, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Contenu
    titre = models.CharField(max_length=200)
    contenu = models.TextField(blank=True)
    supports_cours = models.FileField(upload_to='cours/supports/', blank=True, null=True)
    
    # Suivi
    est_effectuee = models.BooleanField(default=False)
    est_annulee = models.BooleanField(default=False)
    motif_annulation = models.TextField(blank=True)
    
    # Présences
    nombre_present = models.PositiveIntegerField(default=0)
    nombre_absent = models.PositiveIntegerField(default=0)
    
    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'cours'
        verbose_name = "Séance de Cours"
        verbose_name_plural = "Séances de Cours"
        ordering = ['-date', 'heure_debut']
    
    def __str__(self):
        return f"{self.cours} - {self.date}"


class InscriptionCours(models.Model):
    """Inscription des étudiants aux cours"""
    etudiant = models.ForeignKey('etudiants.Etudiant', on_delete=models.CASCADE, related_name='inscriptions_cours')
    cours = models.ForeignKey(Cours, on_delete=models.CASCADE, related_name='inscriptions_cours')
    date_inscription = models.DateTimeField(auto_now_add=True)
    est_actif = models.BooleanField(default=True)
    
    class Meta:
        app_label = 'cours'
        verbose_name = "Inscription au Cours"
        verbose_name_plural = "Inscriptions aux Cours"
        unique_together = ['etudiant', 'cours']
    
    def __str__(self):
        return f"{self.etudiant} - {self.cours}"


class Presence(models.Model):
    """Feuilles de présence"""
    STATUT_CHOICES = [
        ('PRESENT', 'Présent'),
        ('ABSENT', 'Absent'),
        ('RETARD', 'En Retard'),
        ('EXCUSE', 'Excusé'),
    ]
    
    seance = models.ForeignKey(SeanceCours, on_delete=models.CASCADE, related_name='presences')
    etudiant = models.ForeignKey('etudiants.Etudiant', on_delete=models.CASCADE, related_name='presences')
    statut = models.CharField(max_length=10, choices=STATUT_CHOICES, default='PRESENT')
    heure_arrivee = models.TimeField(blank=True, null=True)
    commentaire = models.TextField(blank=True)
    
    class Meta:
        app_label = 'cours'
        verbose_name = "Présence"
        verbose_name_plural = "Présences"
        unique_together = ['seance', 'etudiant']
    
    def __str__(self):
        return f"{self.etudiant} - {self.seance} - {self.get_statut_display()}"


class RessourceCours(models.Model):
    """Ressources pédagogiques des cours"""
    TYPE_RESSOURCE_CHOICES = [
        ('COURS', 'Support de Cours'),
        ('TD', 'Sujet de TD'),
        ('TP', 'Sujet de TP'),
        ('EXAMEN', 'Sujet d\'Examen'),
        ('CORRIGE', 'Corrigé'),
        ('LIVRE', 'Livre Recommandé'),
        ('ARTICLE', 'Article Scientifique'),
        ('VIDEO', 'Vidéo'),
        ('LIEN', 'Lien Web'),
    ]
    
    cours = models.ForeignKey(Cours, on_delete=models.CASCADE, related_name='ressources')
    type_ressource = models.CharField(max_length=10, choices=TYPE_RESSOURCE_CHOICES)
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    fichier = models.FileField(upload_to='cours/ressources/', blank=True, null=True)
    lien_externe = models.URLField(blank=True, null=True)
    est_public = models.BooleanField(default=True)
    date_ajout = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'cours'
        verbose_name = "Ressource de Cours"
        verbose_name_plural = "Ressources de Cours"
        ordering = ['-date_ajout']
    
    def __str__(self):
        return f"{self.titre} - {self.cours}"


class EmploiDuTemps(models.Model):
    """Emplois du temps par filière"""
    filiere = models.ForeignKey('etudiants.Filiere', on_delete=models.CASCADE, related_name='emplois_du_temps')
    annee_academique = models.CharField(max_length=9, default='2024-2025')
    semestre = models.PositiveIntegerField(default=1)
    fichier_pdf = models.FileField(upload_to='emplois_du_temps/', blank=True, null=True)
    est_actif = models.BooleanField(default=True)
    date_debut = models.DateField()
    date_fin = models.DateField()
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'cours'
        verbose_name = "Emploi du Temps"
        verbose_name_plural = "Emplois du Temps"
        unique_together = ['filiere', 'annee_academique', 'semestre']
        ordering = ['-annee_academique', 'filiere']
    
    def __str__(self):
        return f"Emploi du temps - {self.filiere} - {self.annee_academique}"


class SupportPedagogiqueApprenant(models.Model):
    """Supports de cours (TP/TD/Cours) ciblés pour les apprenants en formation continue/certifiante"""
    
    TYPE_DOC_CHOICES = [
        ('COURS', 'Support de Cours'),
        ('TD', 'Sujet de TD'),
        ('TP', 'Sujet de TP'),
    ]
    
    TYPE_FORMATION_CHOICES = [
        ('CERTIFICATION', 'Formation de Certification'),
        ('CONTINUE', 'Formation Continue'),
        ('TOUS', 'Toutes les Formations'),
    ]
    
    MODULE_CHOICES = [
        ('SECRETARIAT', 'Secrétariat bureautique et comptable'),
        ('MARKETING', 'Marketing digital'),
        ('INFOGRAPHIE', 'Infographie'),
        ('MAINTENANCE', 'Maintenance informatique'),
        ('RESEAUX', 'Réseaux informatiques'),
        ('WEBMASTER', 'Webmaster'),
        ('MIJEF', 'Formation continue MIJEF 2035'),
        ('TOUS', 'Tous les Modules'),
    ]
    
    formateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='supports_apprenants',
        verbose_name="Formateur"
    )
    titre = models.CharField(max_length=200, verbose_name="Titre du document")
    type_document = models.CharField(max_length=10, choices=TYPE_DOC_CHOICES, verbose_name="Type de document")
    type_formation = models.CharField(max_length=20, choices=TYPE_FORMATION_CHOICES, default='TOUS', verbose_name="Type de formation")
    module_formation = models.CharField(max_length=50, choices=MODULE_CHOICES, default='TOUS', verbose_name="Module de formation")
    niveau_etude = models.CharField(max_length=100, blank=True, verbose_name="Niveau d'étude", help_text="Laisser vide pour tous les niveaux d'apprenants")
    fichier = models.FileField(upload_to='cours/apprenants/', verbose_name="Fichier (PDF, ZIP, DOCX...)")
    date_depot = models.DateTimeField(auto_now_add=True, verbose_name="Date de dépôt")

    class Meta:
        app_label = 'cours'
        verbose_name = "Support Pédagogique Apprenant"
        verbose_name_plural = "Supports Pédagogiques Apprenants"
        ordering = ['-date_depot']

    def __str__(self):
        return f"{self.titre} - {self.get_module_formation_display()}"

    def get_nom_fichier(self):
        import os
        if self.fichier:
            return os.path.basename(self.fichier.name)
        return None


class EmploiDuTempsHebdomadaire(models.Model):
    """Emploi du temps hebdomadaire officiel - IAI Cameroun Centre de Douala"""
    NIVEAU_CHOICES = [
        ('LEVEL_1', 'Niveau 1 (LEVEL 1)'),
        ('LEVEL_2', 'Niveau 2 (LEVEL 2)'),
    ]
    
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon (Chef des Études)'),
        ('EN_ATTENTE_VALIDATION', 'Soumis pour approbation au Directeur'),
        ('VALIDE', 'Approuvé & Publié (Directeur)'),
        ('REJETE', 'Rejeté / À réviser'),
    ]
    
    filiere = models.ForeignKey('etudiants.Filiere', on_delete=models.CASCADE, related_name='emplois_du_temps_hebdo')
    salle = models.ForeignKey(Salle, on_delete=models.SET_NULL, null=True, blank=True, related_name='emplois_du_temps')
    niveau = models.CharField(max_length=10, choices=NIVEAU_CHOICES, default='LEVEL_1')
    titre_semaine = models.CharField(max_length=100, help_text="Ex: SEMAINE: 11 MAI - 16 MAI 2026")
    date_debut_semaine = models.DateField()
    date_fin_semaine = models.DateField()
    annee_academique = models.CharField(max_length=9, default='2024-2025')
    statut = models.CharField(max_length=25, choices=STATUT_CHOICES, default='BROUILLON')
    
    soumis_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='emplois_soumis')
    approuve_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='emplois_approuves')
    date_approbation = models.DateTimeField(null=True, blank=True)
    motif_rejet = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'cours'
        verbose_name = "Emploi du Temps Hebdomadaire"
        verbose_name_plural = "Emplois du Temps Hebdomadaires"
        ordering = ['-date_debut_semaine', 'filiere']

    def __str__(self):
        return f"{self.titre_semaine} - {self.filiere.code} ({self.get_niveau_display()}) [{self.get_statut_display()}]"


class CreneauEmploiDuTemps(models.Model):
    """Créneau individuel d'un emploi du temps hebdomadaire (Lundi à Samedi)"""
    JOUR_CHOICES = [
        ('LUNDI', 'Lundi'),
        ('MARDI', 'Mardi'),
        ('MERCREDI', 'Mercredi'),
        ('JEUDI', 'Jeudi'),
        ('VENDREDI', 'Vendredi'),
        ('SAMEDI', 'Samedi'),
    ]
    
    PLAGE_CHOICES = [
        ('P1', '07:30 - 09:30'),
        ('P2', '09:30 - 11:30'),
        ('PAUSE', '11:30 - 12:45 (PAUSE)'),
        ('P3', '12:45 - 14:45'),
        ('P4', '14:45 - 16:45'),
    ]
    
    TYPE_EVENEMENT_CHOICES = [
        ('COURS', 'Cours / TP standard (Bleu)'),
        ('EVALUATION', 'Devoir / Contrôle Continu (CA) / Rattrapage (Rose)'),
        ('PAUSE', 'Pause (Jaune)'),
        ('AUTRE', 'Autre (Sport, Activité)'),
    ]
    
    emploi_du_temps = models.ForeignKey(EmploiDuTempsHebdomadaire, on_delete=models.CASCADE, related_name='creneaux')
    jour = models.CharField(max_length=10, choices=JOUR_CHOICES)
    plage = models.CharField(max_length=10, choices=PLAGE_CHOICES)
    
    intitule = models.CharField(max_length=200, blank=True, help_text="Ex: TP(TRAVAUX PRATIQUE), Devoir Séminaire")
    enseignant_nom = models.CharField(max_length=100, blank=True, help_text="Ex: M NNANGA, M DASSY, Mme MELLA")
    salle_nom = models.CharField(max_length=50, blank=True, help_text="Ex: GL3D, Stadium")
    progression_heures = models.CharField(max_length=50, blank=True, help_text="Ex: 28/30 hrs, 70/300 hrs")
    type_evenement = models.CharField(max_length=20, choices=TYPE_EVENEMENT_CHOICES, default='COURS')
    
    class Meta:
        app_label = 'cours'
        verbose_name = "Créneau d'Emploi du Temps"
        verbose_name_plural = "Créneaux d'Emploi du Temps"
        unique_together = ['emploi_du_temps', 'jour', 'plage']