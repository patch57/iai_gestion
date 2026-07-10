"""
Modèles pour la gestion des notes
IAI-Cameroun - Centre de Douala
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Avg, Sum
from django.utils import timezone
from datetime import timedelta
import secrets
import string


class TypeEvaluation(models.Model):
    """Types d'évaluation (CC, TP, Examen, etc.)"""
    code = models.CharField(max_length=10, unique=True)
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    coefficient_default = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=1.00,
        validators=[MinValueValidator(0), MaxValueValidator(10)]
    )
    est_actif = models.BooleanField(default=True)
    couleur = models.CharField(max_length=20, default='#10B981', help_text="Couleur pour l'affichage")
    icon = models.CharField(max_length=50, default='fa-chart-line', help_text="Icône Font Awesome")
    
    class Meta:
        app_label = 'notes'
        verbose_name = "Type d'Évaluation"
        verbose_name_plural = "Types d'Évaluation"
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.nom}"


class Matiere(models.Model):
    """Matière enseignée"""
    SEMESTRE_CHOICES = [
        (1, 'Semestre 1'),
        (2, 'Semestre 2'),
    ]
    
    code = models.CharField(max_length=20, unique=True)
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    credit = models.PositiveIntegerField(default=3)
    semestre = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(2)],
        choices=SEMESTRE_CHOICES
    )
    volume_horaire = models.PositiveIntegerField(default=30)
    est_actif = models.BooleanField(default=True)
    
    class Meta:
        app_label = 'notes'
        verbose_name = "Matière"
        verbose_name_plural = "Matières"
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.nom}"


class Cours(models.Model):
    """Cours associé à une matière"""
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE, related_name='cours_notes')
    filiere = models.ForeignKey('etudiants.Filiere', on_delete=models.CASCADE, related_name='cours_notes')
    niveau = models.ForeignKey('etudiants.Niveau', on_delete=models.CASCADE, related_name='cours_notes')
    professeur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cours_enseignes'
    )
    annee_academique = models.CharField(max_length=9, default='2024-2025')
    semestre = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(2)]
    )
    volume_horaire = models.PositiveIntegerField(default=30)
    est_actif = models.BooleanField(default=True)
    
    class Meta:
        app_label = 'notes'
        verbose_name = "Cours"
        verbose_name_plural = "Cours"
        unique_together = ['matiere', 'filiere', 'niveau', 'annee_academique']
        indexes = [
            models.Index(fields=['annee_academique', 'semestre']),
            models.Index(fields=['filiere', 'niveau']),
        ]
    
    def __str__(self):
        return f"{self.matiere.nom} - {self.filiere.code} - Niveau {self.niveau.numero}"


class Evaluation(models.Model):
    """Évaluations (examens, contrôles continus, etc.)"""
    STATUT_CHOICES = [
        ('PREVUE', 'Prévue'),
        ('EN_COURS', 'En cours'),
        ('TERMINEE', 'Terminée'),
        ('ANNULEE', 'Annulée'),
    ]
    
    cours = models.ForeignKey(Cours, on_delete=models.CASCADE, related_name='evaluations')
    type_evaluation = models.ForeignKey(TypeEvaluation, on_delete=models.PROTECT)
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Coefficient et barème
    coefficient = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=1.00,
        validators=[MinValueValidator(0), MaxValueValidator(10)]
    )
    note_maximale = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=20.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Dates
    date_evaluation = models.DateField()
    heure_debut = models.TimeField(null=True, blank=True)
    heure_fin = models.TimeField(null=True, blank=True)
    duree_minutes = models.PositiveIntegerField(default=120)
    
    # Lieu
    salle = models.CharField(max_length=50, blank=True)
    
    # Statut
    statut = models.CharField(max_length=15, choices=STATUT_CHOICES, default='PREVUE')
    est_publiee = models.BooleanField(default=False)
    
    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='evaluations_crees'
    )
    
    class Meta:
        app_label = 'notes'
        verbose_name = "Évaluation"
        verbose_name_plural = "Évaluations"
        ordering = ['-date_evaluation']
    
    def __str__(self):
        return f"{self.titre} - {self.cours.matiere.nom}"
    
    def get_moyenne(self):
        """Calcule la moyenne de l'évaluation"""
        notes = self.notes.all()
        if notes.exists():
            return notes.aggregate(Avg('valeur'))['valeur__avg']
        return None
    
    def get_nombre_reussites(self):
        """Nombre d'étudiants ayant réussi (note >= 10)"""
        return self.notes.filter(valeur__gte=10).count()
    
    def get_taux_reussite(self):
        """Taux de réussite en pourcentage"""
        total = self.notes.count()
        if total > 0:
            return (self.get_nombre_reussites() / total) * 100
        return 0
    
    def get_repartition_notes(self):
        """Répartition des notes par tranche"""
        tranches = {
            '0-4': 0, '4-8': 0, '8-10': 0, '10-12': 0, '12-14': 0, '14-16': 0, '16-20': 0
        }
        for note in self.notes.all():
            valeur = float(note.valeur)
            if valeur < 4:
                tranches['0-4'] += 1
            elif valeur < 8:
                tranches['4-8'] += 1
            elif valeur < 10:
                tranches['8-10'] += 1
            elif valeur < 12:
                tranches['10-12'] += 1
            elif valeur < 14:
                tranches['12-14'] += 1
            elif valeur < 16:
                tranches['14-16'] += 1
            else:
                tranches['16-20'] += 1
        return tranches


class Note(models.Model):
    """Notes des étudiants"""
    etudiant = models.ForeignKey(
        'etudiants.Etudiant',
        on_delete=models.CASCADE,
        related_name='notes'
    )
    evaluation = models.ForeignKey(
        Evaluation,
        on_delete=models.CASCADE,
        related_name='notes'
    )
    valeur = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    observation = models.TextField(blank=True)
    
    # Métadonnées
    date_saisie = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    saisie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='notes_saisies'
    )
    est_validee = models.BooleanField(default=False)
    
    class Meta:
        app_label = 'notes'
        verbose_name = "Note"
        verbose_name_plural = "Notes"
        unique_together = ['etudiant', 'evaluation']
        ordering = ['-date_saisie']
        permissions = [
            ('peut_saisir_notes', 'Peut saisir des notes'),
            ('peut_valider_notes', 'Peut valider des notes'),
            ('peut_modifier_notes', 'Peut modifier des notes après validation'),
            ('peut_voir_notes_anonymes', 'Peut voir les notes anonymes'),
        ]
    
    def __str__(self):
        return f"{self.etudiant.get_nom_complet()} - {self.evaluation.titre} : {self.valeur}"
    
    def get_note_ponderee(self):
        """Calcule la note pondérée par le coefficient"""
        return float(self.valeur) * float(self.evaluation.coefficient)
    
    def est_reussite(self):
        """Vérifie si la note est une réussite (>= 10)"""
        return self.valeur >= 10


class NoteAnonyme(models.Model):
    """Modèle pour les notes anonymisées"""
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='notes_anonymes')
    code_anonyme = models.CharField(max_length=20, unique=True)
    valeur = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    etudiant_origine = models.ForeignKey('etudiants.Etudiant', on_delete=models.SET_NULL, null=True, blank=True)
    date_saisie = models.DateTimeField(auto_now_add=True)
    saisie_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        app_label = 'notes'
        verbose_name = "Note anonyme"
        verbose_name_plural = "Notes anonymes"
        unique_together = ['evaluation', 'code_anonyme']
    
    def __str__(self):
        return f"{self.code_anonyme} - {self.valeur if self.valeur else 'Non saisie'}"


class SessionAnonymat(models.Model):
    """Session d'anonymat pour une évaluation"""
    evaluation = models.OneToOneField(Evaluation, on_delete=models.CASCADE, related_name='session_anonymat')
    code_session = models.CharField(max_length=50, unique=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_expiration = models.DateTimeField()
    est_active = models.BooleanField(default=True)
    professeur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    class Meta:
        app_label = 'notes'
        verbose_name = "Session d'anonymat"
        verbose_name_plural = "Sessions d'anonymat"
    
    def __str__(self):
        return f"Session {self.code_session} - {self.evaluation}"
    
    def generer_codes_anonymes(self, etudiants):
        """Génère des codes anonymes pour les étudiants"""
        alphabet = string.ascii_uppercase + string.digits
        codes = []
        
        for etudiant in etudiants:
            code = ''.join(secrets.choice(alphabet) for _ in range(8))
            while NoteAnonyme.objects.filter(code_anonyme=code).exists():
                code = ''.join(secrets.choice(alphabet) for _ in range(8))
            
            note_anonyme = NoteAnonyme.objects.create(
                evaluation=self.evaluation,
                code_anonyme=code,
                etudiant_origine=etudiant
            )
            codes.append(note_anonyme)
        
        return codes
    
    def est_expiree(self):
        """Vérifie si la session est expirée"""
        return timezone.now() > self.date_expiration


class Bulletin(models.Model):
    """Bulletins semestriels des étudiants"""
    DECISION_CHOICES = [
        ('ADMIS', 'Admis'),
        ('AJOURNE', 'Ajourné'),
        ('EXCLU', 'Exclu'),
        ('EN_ATTENTE', 'En Attente'),
    ]
    
    MENTION_CHOICES = [
        ('PASSABLE', 'Passable'),
        ('ASSEZ_BIEN', 'Assez Bien'),
        ('BIEN', 'Bien'),
        ('TRES_BIEN', 'Très Bien'),
        ('EXCELLENT', 'Excellent'),
    ]
    
    etudiant = models.ForeignKey(
        'etudiants.Etudiant',
        on_delete=models.CASCADE,
        related_name='bulletins'
    )
    annee_academique = models.CharField(max_length=9, default='2024-2025')
    semestre = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(2)]
    )
    
    # Moyennes
    moyenne_semestre = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )
    credits_obtenus = models.PositiveIntegerField(default=0)
    credits_totaux = models.PositiveIntegerField(default=0)
    
    # Décision
    decision = models.CharField(
        max_length=15,
        choices=DECISION_CHOICES,
        default='EN_ATTENTE'
    )
    mention = models.CharField(max_length=20, blank=True)
    
    # Classement
    rang = models.PositiveIntegerField(null=True, blank=True)
    effectif = models.PositiveIntegerField(null=True, blank=True)
    
    # Métadonnées
    est_valide = models.BooleanField(default=False)
    date_validation = models.DateTimeField(null=True, blank=True)
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bulletins_valides'
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'notes'
        verbose_name = "Bulletin"
        verbose_name_plural = "Bulletins"
        unique_together = ['etudiant', 'annee_academique', 'semestre']
        ordering = ['-annee_academique', 'semestre', '-moyenne_semestre']
    
    def __str__(self):
        return f"Bulletin {self.etudiant.get_nom_complet()} - S{self.semestre} {self.annee_academique}"
    
    def calculer_moyenne(self):
        """Calcule la moyenne semestrielle"""
        notes = Note.objects.filter(
            etudiant=self.etudiant,
            evaluation__cours__annee_academique=self.annee_academique,
            evaluation__cours__semestre=self.semestre,
            est_validee=True
        )
        
        if notes.exists():
            total_points = sum(float(n.get_note_ponderee()) for n in notes)
            total_coeffs = sum(float(n.evaluation.coefficient) for n in notes)
            if total_coeffs > 0:
                self.moyenne_semestre = total_points / total_coeffs
        return self.moyenne_semestre
    
    def determiner_decision(self):
        """Détermine la décision du jury"""
        if self.moyenne_semestre >= 10:
            self.decision = 'ADMIS'
            if self.moyenne_semestre >= 16:
                self.mention = 'Très Bien'
            elif self.moyenne_semestre >= 14:
                self.mention = 'Bien'
            elif self.moyenne_semestre >= 12:
                self.mention = 'Assez Bien'
            else:
                self.mention = 'Passable'
        elif self.moyenne_semestre >= 7:
            self.decision = 'AJOURNE'
        else:
            self.decision = 'EXCLU'
        return self.decision
    
    def get_appreciation(self):
        """Retourne une appréciation selon la moyenne"""
        if self.moyenne_semestre >= 16:
            return "Excellent travail ! Continuez sur cette lancée."
        elif self.moyenne_semestre >= 14:
            return "Très bon semestre. Persévérez !"
        elif self.moyenne_semestre >= 12:
            return "Bon semestre. Peut mieux faire."
        elif self.moyenne_semestre >= 10:
            return "Passable. Des efforts sont nécessaires."
        else:
            return "Insuffisant. Une remise en question s'impose."


class DetailBulletin(models.Model):
    """Détails des notes par matière dans un bulletin"""
    bulletin = models.ForeignKey(Bulletin, on_delete=models.CASCADE, related_name='details')
    matiere = models.ForeignKey(Matiere, on_delete=models.PROTECT)
    
    # Notes
    note_cc = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    note_tp = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    note_examen = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    moyenne_matiere = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Crédits
    credits = models.PositiveIntegerField(default=0)
    credits_obtenus = models.PositiveIntegerField(default=0)
    
    # Décision
    est_validee = models.BooleanField(default=False)
    
    class Meta:
        app_label = 'notes'
        verbose_name = "Détail de Bulletin"
        verbose_name_plural = "Détails de Bulletins"
        unique_together = ['bulletin', 'matiere']
    
    def __str__(self):
        return f"{self.matiere} - {self.bulletin}"
    
    def calculer_moyenne(self):
        """Calcule la moyenne de la matière"""
        notes = []
        coeffs = []
        
        if self.note_cc is not None:
            notes.append(float(self.note_cc))
            coeffs.append(0.3)
        if self.note_tp is not None:
            notes.append(float(self.note_tp))
            coeffs.append(0.2)
        if self.note_examen is not None:
            notes.append(float(self.note_examen))
            coeffs.append(0.5)
        
        if notes and coeffs:
            total_pondere = sum(n * c for n, c in zip(notes, coeffs))
            total_coeffs = sum(coeffs)
            if total_coeffs > 0:
                self.moyenne_matiere = total_pondere / total_coeffs
                self.est_validee = self.moyenne_matiere >= 10
                if self.est_validee:
                    self.credits_obtenus = self.credits
        return self.moyenne_matiere
    
    def get_appreciation(self):
        """Appréciation par matière"""
        if self.moyenne_matiere >= 16:
            return "Excellent"
        elif self.moyenne_matiere >= 14:
            return "Très bien"
        elif self.moyenne_matiere >= 12:
            return "Bien"
        elif self.moyenne_matiere >= 10:
            return "Passable"
        else:
            return "Insuffisant"


class Deliberation(models.Model):
    """Séances de délibération du jury"""
    filiere = models.ForeignKey('etudiants.Filiere', on_delete=models.CASCADE)
    annee_academique = models.CharField(max_length=9, default='2024-2025')
    semestre = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(2)]
    )
    
    date_debut = models.DateTimeField()
    date_fin = models.DateTimeField(null=True, blank=True)
    est_terminee = models.BooleanField(default=False)
    
    # Membres du jury
    president = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deliberations_presidees'
    )
    membres = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='deliberations',
        blank=True
    )
    
    # PV
    proces_verbal = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'notes'
        verbose_name = "Délibération"
        verbose_name_plural = "Délibérations"
        unique_together = ['filiere', 'annee_academique', 'semestre']
    
    def __str__(self):
        return f"Délibération {self.filiere.code} - S{self.semestre} {self.annee_academique}"


class RecoursNote(models.Model):
    """Recours sur des notes"""
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En Attente'),
        ('ACCEPTE', 'Accepté'),
        ('REJETE', 'Rejeté'),
    ]
    
    etudiant = models.ForeignKey(
        'etudiants.Etudiant',
        on_delete=models.CASCADE,
        related_name='recours'
    )
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE)
    note_actuelle = models.DecimalField(max_digits=5, decimal_places=2)
    note_demandee = models.DecimalField(max_digits=5, decimal_places=2)
    motif = models.TextField()
    statut = models.CharField(max_length=15, choices=STATUT_CHOICES, default='EN_ATTENTE')
    decision = models.TextField(blank=True)
    date_soumission = models.DateTimeField(auto_now_add=True)
    date_traitement = models.DateTimeField(null=True, blank=True)
    traite_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recours_traites'
    )
    
    class Meta:
        app_label = 'notes'
        verbose_name = "Recours sur Note"
        verbose_name_plural = "Recours sur Notes"
        ordering = ['-date_soumission']
    
    def __str__(self):
        return f"Recours {self.etudiant.get_nom_complet()} - {self.evaluation.titre}"


# ========== MODÈLES POUR LA GÉO-LOCALISATION ==========

class CampusLocation(models.Model):
    """Localisation du campus IAI-Cameroun"""
    nom = models.CharField(max_length=100, default='IAI-Cameroun Centre de Douala')
    adresse = models.TextField(help_text="PK9, Douala - Station MRS, avant boulangerie Saker")
    latitude = models.FloatField(default=4.051056)
    longitude = models.FloatField(default=9.767865)
    telephone = models.CharField(max_length=20, default='+237 242 58 79 52')
    email = models.EmailField(default='contact@iai-cameroun.com')
    horaires = models.CharField(max_length=200, default='Lundi-Vendredi: 07h30 - 16h30')
    instructions = models.TextField(blank=True, help_text="Indications pour accéder au campus")
    
    class Meta:
        app_label = 'notes'
        verbose_name = "Localisation du campus"
        verbose_name_plural = "Localisations du campus"
    
    def __str__(self):
        return self.nom
    
    def get_coordonnees(self):
        return f"{self.latitude}, {self.longitude}"


class PointInteret(models.Model):
    """Points d'intérêt autour du campus"""
    TYPES = [
        ('RESTAURANT', 'Restaurant'),
        ('BANQUE', 'Banque'),
        ('TRANSPORT', 'Transport'),
        ('HEBERGEMENT', 'Hébergement'),
        ('SANTE', 'Santé'),
        ('COMMERCE', 'Commerce'),
        ('RELIGIEUX', 'Lieu religieux'),
        ('ADMINISTRATIF', 'Service administratif'),
    ]
    
    nom = models.CharField(max_length=100)
    type_poi = models.CharField(max_length=20, choices=TYPES)
    adresse = models.TextField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    description = models.TextField(blank=True)
    distance_approx = models.FloatField(help_text="Distance approximative en mètres", blank=True, null=True)
    horaires = models.CharField(max_length=200, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    
    class Meta:
        app_label = 'notes'
        verbose_name = "Point d'intérêt"
        verbose_name_plural = "Points d'intérêt"
    
    def __str__(self):
        return f"{self.nom} - {self.get_type_poi_display()}"
    
    def get_coordonnees(self):
        return f"{self.latitude}, {self.longitude}"