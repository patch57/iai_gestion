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


class UniteEnseignement(models.Model):
    """Modèle représentant une Unité d'Enseignement (UE) regroupant plusieurs matières"""
    code = models.CharField(max_length=20, unique=True)
    nom = models.CharField(max_length=150)
    filiere = models.ForeignKey('etudiants.Filiere', on_delete=models.CASCADE, related_name='ues', null=True, blank=True)
    niveau = models.ForeignKey('etudiants.Niveau', on_delete=models.CASCADE, related_name='ues', null=True, blank=True)
    
    class Meta:
        app_label = 'notes'
        verbose_name = "Unité d'Enseignement"
        verbose_name_plural = "Unités d'Enseignement"
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
    unite_enseignement = models.ForeignKey(UniteEnseignement, on_delete=models.SET_NULL, null=True, blank=True, related_name='matieres')
    
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
        validators=[MinValueValidator(1), MaxValueValidator(3)]
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
    
    # Classement et Statistiques de classe
    rang = models.PositiveIntegerField(null=True, blank=True)
    effectif = models.PositiveIntegerField(null=True, blank=True)
    moyenne_classe_min = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    moyenne_classe_max = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    moyenne_classe_generale = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    retards = models.PositiveIntegerField(default=0)
    absences = models.PositiveIntegerField(default=0)
    discipline = models.CharField(max_length=50, default='-')

    # Publication et Archivage PDF
    pdf_file = models.FileField(upload_to='bulletins/%Y/', null=True, blank=True)
    est_publie = models.BooleanField(default=False)
    date_publication = models.DateTimeField(null=True, blank=True)
    numero_bulletin = models.CharField(max_length=100, blank=True)
    
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
        """Calcule la moyenne de la matière (CC 40% et Examen 60%)"""
        notes = []
        coeffs = []
        
        if self.note_cc is not None:
            notes.append(float(self.note_cc))
            coeffs.append(0.4)
        if self.note_examen is not None:
            notes.append(float(self.note_examen))
            coeffs.append(0.6)
        
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


class NoteApprenant(models.Model):
    """Notes d'évaluation des apprenants en certifications / formation continue"""
    
    apprenant = models.ForeignKey(
        'etudiants.Apprenant',
        on_delete=models.CASCADE,
        related_name='notes_apprenant',
        verbose_name="Apprenant"
    )
    formation = models.ForeignKey(
        'etudiants.Formation',
        on_delete=models.CASCADE,
        related_name='notes_apprenant',
        verbose_name="Formation"
    )
    matiere = models.ForeignKey(
        'cours.MatiereFormation',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notes_apprenant',
        verbose_name="Matière"
    )
    formateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notes_attribuees_apprenants',
        verbose_name="Formateur / Enseignant"
    )
    note = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(20)],
        verbose_name="Note / 20"
    )
    date_evaluation = models.DateField(default=timezone.now, verbose_name="Date d'évaluation")
    commentaire = models.CharField(max_length=200, blank=True, verbose_name="Appréciation / Commentaire")

    class Meta:
        app_label = 'notes'
        verbose_name = "Note Apprenant"
        verbose_name_plural = "Notes Apprenants"
        unique_together = ['apprenant', 'formation', 'matiere']
        ordering = ['-date_evaluation']


    def __str__(self):
        return f"{self.apprenant.nom_complet} - {self.formation.get_nom_display()} : {self.note}/20"


class FicheNotesAnonymat(models.Model):
    """Modèle représentant une fiche de notes d'anonymat (par Salle, Filière et Niveau)"""
    STATUT_CHOICES = [
        ('BROUILLON', '📝 Brouillon (Enseignant)'),
        ('TRANSMIS_CHEF_ANONYMAT', '📨 Transmis au Chef de l\'Anonymat'),
        ('MATCH_EFFECTUE', '🔍 Matching Effectué (Chef Anonymat)'),
        ('PV_GENERE', '📋 PV de Notes Généré'),
        ('TRANSMIS_CHEF_ETUDES', '📩 Transmis au Chef des Études'),
        ('VALIDE', '✅ Validé & Publié'),
    ]
    
    matiere = models.ForeignKey('cours.Matiere', on_delete=models.CASCADE, related_name='fiches_anonymat')
    filiere = models.ForeignKey('etudiants.Filiere', on_delete=models.CASCADE, related_name='fiches_anonymat', null=True, blank=True)
    niveau = models.ForeignKey('etudiants.Niveau', on_delete=models.CASCADE, related_name='fiches_anonymat', null=True, blank=True)
    salle = models.ForeignKey('cours.Salle', on_delete=models.CASCADE, related_name='fiches_anonymat', verbose_name="Salle / Classe physical", null=True, blank=True)
    annee_academique = models.CharField(max_length=9, default='2025-2026')
    type_evaluation = models.ForeignKey(TypeEvaluation, on_delete=models.CASCADE, related_name='fiches_anonymat')
    enseignant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='fiches_anonymat_enseignant')
    enseignant_nom = models.CharField(max_length=150, blank=True)
    fichier_fiche = models.FileField(upload_to='fiches_anonymat/', blank=True, null=True)
    MODE_FICHE_CHOICES = [
        ('EXPOSE_TP_TD', '📋 Exposés, TP, TD & CC Continu (Noms, Matricules & Notes CC 1..5)'),
        ('DEVOIR_SUR_TABLE', '🔒 Devoir sur Table / Examen (Anonymat 3 colonnes : Code + Note)'),
    ]
    mode_fiche = models.CharField(max_length=30, choices=MODE_FICHE_CHOICES, default='EXPOSE_TP_TD', verbose_name="Mode / Nature de la Fiche")

    statut = models.CharField(max_length=30, choices=STATUT_CHOICES, default='BROUILLON')

    
    date_creation = models.DateTimeField(auto_now_add=True)
    date_transmission_anonymat = models.DateTimeField(null=True, blank=True)
    date_transmission_etudes = models.DateTimeField(null=True, blank=True)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='fiches_anonymat_creees')

    def recalculer_toutes_les_moyennes(self):
        """
        Détermine le nombre d'évaluations N_eval global (max colonne renseignée sur toute la fiche, 1..5).
        Dividende = somme des notes jusqu'à N_eval (case vide = 0.00).
        Dénominateur = N_eval.
        """
        lignes = list(self.lignes.all())
        if not lignes:
            return

        # 1. Déterminer le nombre d'évaluations global sur l'ensemble du PV
        max_eval = 0
        for ligne in lignes:
            for idx, n in enumerate([ligne.note_1, ligne.note_2, ligne.note_3, ligne.note_4, ligne.note_5], start=1):
                if n is not None:
                    max_eval = max(max_eval, idx)

        # 2. Recalculer la moyenne de chaque ligne sur N_eval
        for ligne in lignes:
            ligne.calculer_moyenne_cc(nb_evaluations_global=max_eval)
            ligne.save()

    class Meta:
        app_label = 'notes'
        verbose_name = "Fiche de Notes d'Anonymat"
        verbose_name_plural = "Fiches de Notes d'Anonymat"
        ordering = ['-date_creation']

    def __str__(self):
        filiere_code = self.filiere.code if self.filiere else ''
        niveau_num = f"L{self.niveau.numero}" if self.niveau else ''
        salle_code = self.salle.code if self.salle else ''
        return f"Fiche Anonymat {self.matiere.code} - {filiere_code} {niveau_num} ({salle_code}) - {self.get_statut_display()}"


class LigneFicheNotesAnonymat(models.Model):
    """Modèle représentant une ligne de note d'une fiche d'anonymat"""
    fiche = models.ForeignKey(FicheNotesAnonymat, on_delete=models.CASCADE, related_name='lignes')
    numero_anonymat = models.CharField(max_length=20)
    note = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Notes multiples de CC (Note 1 à Note 5)
    note_1 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    note_2 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    note_3 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    note_4 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    note_5 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    moyenne_cc = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    nom_manuscrit_detecte = models.CharField(max_length=255, blank=True)
    score_ocr = models.FloatField(default=1.0)
    etudiant = models.ForeignKey('etudiants.Etudiant', on_delete=models.SET_NULL, null=True, blank=True, related_name='lignes_anonymat')

    class Meta:
        app_label = 'notes'
        verbose_name = "Ligne de Fiche d'Anonymat"
        verbose_name_plural = "Lignes de Fiche d'Anonymat"
        ordering = ['numero_anonymat']

    def __str__(self):
        return f"{self.numero_anonymat} : {self.note if self.note is not None else 'N/A'}/20 -> {self.etudiant.get_nom_complet() if self.etudiant else self.nom_manuscrit_detecte or 'Anonyme'}"

    def calculer_moyenne_cc(self, imputer_zero_si_vide=True, nb_evaluations_global=None):
        """
        Calcule la moyenne des notes de CC (Note 1 à Note 5).
        - Si nb_evaluations_global est fourni (ex: 3), le dénominateur est 3 et les cases vides sont imputées 0.00.
        - Sinon, trouve la dernière note renseignée pour cette ligne et divise par dernier_idx.
        """
        toutes_notes = [self.note_1, self.note_2, self.note_3, self.note_4, self.note_5]
        
        count = nb_evaluations_global
        if not count:
            for idx, val in enumerate(toutes_notes, start=1):
                if val is not None:
                    count = idx

        if count and count > 0:
            notes_effectives = []
            for idx in range(count):
                val = toutes_notes[idx]
                if val is None:
                    notes_effectives.append(0.0)
                else:
                    try:
                        notes_effectives.append(float(val))
                    except (TypeError, ValueError):
                        notes_effectives.append(0.0)
            
            m = sum(notes_effectives) / count
            self.moyenne_cc = round(m, 2)
            self.note = self.moyenne_cc
        elif imputer_zero_si_vide:
            self.moyenne_cc = 0.00
            self.note = 0.00
        else:
            self.moyenne_cc = None
            self.note = None
        return self.moyenne_cc



class ProcesVerbalNotes(models.Model):
    """Procès-verbal de notes confidentiel unique par Matière et Salle généré dynamiquement par le Chef de l'Anonymat pour le Chef des Études"""
    fiche_anonymat = models.OneToOneField(FicheNotesAnonymat, on_delete=models.CASCADE, related_name='proces_verbal', null=True, blank=True)
    titre = models.CharField(max_length=255)
    filiere = models.ForeignKey('etudiants.Filiere', on_delete=models.CASCADE, related_name='pvs_notes', null=True, blank=True)
    niveau = models.ForeignKey('etudiants.Niveau', on_delete=models.CASCADE, related_name='pvs_notes', null=True, blank=True)
    salle = models.ForeignKey('cours.Salle', on_delete=models.CASCADE, related_name='pvs_notes', null=True, blank=True)
    matiere = models.ForeignKey('cours.Matiere', on_delete=models.CASCADE, related_name='pvs_notes', null=True, blank=True)
    annee_academique = models.CharField(max_length=9, default='2025-2026')
    
    date_generation = models.DateTimeField(auto_now_add=True)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='pvs_crees')
    est_transmis = models.BooleanField(default=False, verbose_name="Transmis au Chef des Études")
    date_transmission = models.DateTimeField(null=True, blank=True)
    est_valide_par_chef_etudes = models.BooleanField(default=False)
    date_validation_chef_etudes = models.DateTimeField(null=True, blank=True)
    fichier_excel = models.FileField(upload_to='proces_verbaux/', blank=True, null=True)

    class Meta:
        app_label = 'notes'
        verbose_name = "Procès-verbal de Notes"
        verbose_name_plural = "Procès-verbaux de Notes"
        ordering = ['-date_generation']

    def __str__(self):
        return f"PV Notes - {self.titre}"

    def get_nb_cc(self):
        """
        Détermine le nombre de sous-évaluations CC réellement présent sur ce PV (0 à 5).
        Si nb_cc <= 1, seule la colonne finale 'Moyenne CC' est affichée.
        """
        max_sub = 0
        for ligne in self.lignes.all():
            for idx, val in enumerate([ligne.note_1, ligne.note_2, ligne.note_3, ligne.note_4, ligne.note_5], start=1):
                if val is not None:
                    max_sub = max(max_sub, idx)
        return max_sub

    def actualiser_depuis_fiches_anonymat(self):
        """
        Agrège dynamiquement les fiches d'anonymat (CC, Examen, Rattrapage) associées à cette matière et cette salle.
        Remplit et recalcule les colonnes du PV pour chaque étudiant de la classe.
        """
        from apps.etudiants.models import Etudiant
        
        # 1. Obtenir les étudiants de la salle/filière/niveau
        etudiants_qs = Etudiant.objects.filter(est_actif=True)
        if self.salle and hasattr(self.salle, 'etudiants'):
            etudiants_salle = etudiants_qs.filter(salle=self.salle)
            if etudiants_salle.exists():
                etudiants_qs = etudiants_salle
            else:
                etudiants_qs = etudiants_qs.filter(filiere=self.filiere, niveau=self.niveau)
        elif self.filiere and self.niveau:
            etudiants_qs = etudiants_qs.filter(filiere=self.filiere, niveau=self.niveau)

        # 2. Chercher toutes les fiches d'anonymat matchées/PV pour cette matière et salle/filière
        fiches_qs = FicheNotesAnonymat.objects.filter(
            matiere=self.matiere
        ).exclude(statut='BROUILLON')

        if self.salle:
            fiches_salle = fiches_qs.filter(salle=self.salle)
            if fiches_salle.exists():
                fiches_qs = fiches_salle
            else:
                fiches_qs = fiches_qs.filter(filiere=self.filiere, niveau=self.niveau)
        elif self.filiere and self.niveau:
            fiches_qs = fiches_qs.filter(filiere=self.filiere, niveau=self.niveau)

        cc_fiches = []
        exam_fiches = []
        ratt_fiches = []
        types_transmis = set()

        for fiche in fiches_qs:
            code_type = fiche.type_evaluation.code.upper() if fiche.type_evaluation else ''
            is_cc = 'CC' in code_type or 'CONTROLE' in code_type or 'TP' in code_type or 'TD' in code_type
            is_ratt = 'RATT' in code_type or 'RATTRAPAGE' in code_type
            is_exam = ('EXAM' in code_type or 'EXAMEN' in code_type) and not is_ratt

            est_fiche_transmise = (fiche.statut in ['TRANSMIS_CHEF_ETUDES', 'VALIDE']) or self.est_transmis

            if is_cc:
                cc_fiches.append(fiche)
                if est_fiche_transmise:
                    types_transmis.add('CC')
            elif is_ratt:
                ratt_fiches.append(fiche)
            elif is_exam:
                exam_fiches.append(fiche)
                if est_fiche_transmise:
                    types_transmis.add('EXAM')

        # Dict: student_id -> dict avec note_1..5, CC, EXAM, RATT
        notes_par_etudiant = {}
        nb_cc_effective = 0

        if len(cc_fiches) == 1:
            fiche = cc_fiches[0]
            max_sub = 0
            for ligne in fiche.lignes.all():
                for idx, n in enumerate([ligne.note_1, ligne.note_2, ligne.note_3, ligne.note_4, ligne.note_5], start=1):
                    if n is not None:
                        max_sub = max(max_sub, idx)

            if max_sub > 1:
                nb_cc_effective = max_sub
                for ligne in fiche.lignes.select_related('etudiant').all():
                    if ligne.etudiant:
                        eid = ligne.etudiant.id
                        if eid not in notes_par_etudiant:
                            notes_par_etudiant[eid] = {}
                        
                        sub_notes = [ligne.note_1, ligne.note_2, ligne.note_3, ligne.note_4, ligne.note_5][:nb_cc_effective]
                        sum_val = 0.0
                        for idx, sn in enumerate(sub_notes, start=1):
                            val_sn = float(sn) if sn is not None else 0.0
                            notes_par_etudiant[eid][f'note_{idx}'] = val_sn
                            sum_val += val_sn
                        
                        notes_par_etudiant[eid]['CC'] = round(sum_val / nb_cc_effective, 2)
            else:
                nb_cc_effective = 1
                for ligne in fiche.lignes.select_related('etudiant').all():
                    if ligne.etudiant:
                        eid = ligne.etudiant.id
                        if eid not in notes_par_etudiant:
                            notes_par_etudiant[eid] = {}
                        
                        val = ligne.note if ligne.note is not None else ligne.moyenne_cc
                        if val is None and ligne.note_1 is not None:
                            val = ligne.note_1
                        
                        if val is not None:
                            notes_par_etudiant[eid]['CC'] = float(val)

        elif len(cc_fiches) > 1:
            nb_cc_effective = min(len(cc_fiches), 5)
            for idx_f, fiche in enumerate(cc_fiches[:nb_cc_effective], start=1):
                for ligne in fiche.lignes.select_related('etudiant').all():
                    if ligne.etudiant:
                        eid = ligne.etudiant.id
                        if eid not in notes_par_etudiant:
                            notes_par_etudiant[eid] = {}
                        val = ligne.note if ligne.note is not None else ligne.moyenne_cc
                        if val is None and ligne.note_1 is not None:
                            val = ligne.note_1
                        if val is not None:
                            notes_par_etudiant[eid][f'note_{idx_f}'] = float(val)

            for eid, data in notes_par_etudiant.items():
                sum_val = 0.0
                for k in range(1, nb_cc_effective + 1):
                    val_k = data.get(f'note_{k}')
                    val_float = float(val_k) if val_k is not None else 0.0
                    data[f'note_{k}'] = val_float
                    sum_val += val_float
                data['CC'] = round(sum_val / nb_cc_effective, 2)

        for fiche in exam_fiches:
            for ligne in fiche.lignes.select_related('etudiant').all():
                if ligne.etudiant:
                    eid = ligne.etudiant.id
                    if eid not in notes_par_etudiant:
                        notes_par_etudiant[eid] = {}
                    val = ligne.note if ligne.note is not None else ligne.moyenne_cc
                    if val is not None:
                        notes_par_etudiant[eid]['EXAM'] = float(val)

        for fiche in ratt_fiches:
            for ligne in fiche.lignes.select_related('etudiant').all():
                if ligne.etudiant:
                    eid = ligne.etudiant.id
                    if eid not in notes_par_etudiant:
                        notes_par_etudiant[eid] = {}
                    val = ligne.note if ligne.note is not None else ligne.moyenne_cc
                    if val is not None:
                        notes_par_etudiant[eid]['RATT'] = float(val)

        cc_transmis = 'CC' in types_transmis or (self.est_transmis and any('CC' in n for n in notes_par_etudiant.values()))
        exam_transmis = 'EXAM' in types_transmis or (self.est_transmis and any('EXAM' in n for n in notes_par_etudiant.values()))
        les_deux_transmis = cc_transmis and exam_transmis

        # 3. Synchroniser avec LigneProcesVerbalNotes
        for etudiant in etudiants_qs:
            ligne_pv, _ = LigneProcesVerbalNotes.objects.get_or_create(
                pv=self,
                etudiant=etudiant
            )
            et_notes = notes_par_etudiant.get(etudiant.id, {})

            if nb_cc_effective > 1:
                ligne_pv.note_1 = et_notes.get('note_1', 0.0)
                ligne_pv.note_2 = et_notes.get('note_2', 0.0)
                ligne_pv.note_3 = et_notes.get('note_3', 0.0)
                ligne_pv.note_4 = et_notes.get('note_4', 0.0)
                ligne_pv.note_5 = et_notes.get('note_5', 0.0)
            else:
                ligne_pv.note_1 = et_notes.get('note_1')
                ligne_pv.note_2 = None
                ligne_pv.note_3 = None
                ligne_pv.note_4 = None
                ligne_pv.note_5 = None

            if 'CC' in et_notes:
                ligne_pv.note_cc = et_notes['CC']
            elif not cc_transmis:
                ligne_pv.note_cc = None
                ligne_pv.note_cc_manquante = False
            elif cc_transmis and nb_cc_effective > 1:
                ligne_pv.note_cc = 0.0

            if 'EXAM' in et_notes:
                ligne_pv.note_examen = et_notes['EXAM']
            elif not exam_transmis:
                ligne_pv.note_examen = None
                ligne_pv.note_examen_manquante = False

            if 'RATT' in et_notes:
                ligne_pv.note_rattrapage = et_notes['RATT']

            ligne_pv.calculer_note_finale(
                cc_transmis=cc_transmis,
                exam_transmis=exam_transmis,
                imputer_zero_si_transmis=les_deux_transmis
            )
            ligne_pv.save()


class LigneProcesVerbalNotes(models.Model):
    """Ligne individuelle d'un PV de Notes unifié par Matière pour un étudiant"""
    pv = models.ForeignKey(ProcesVerbalNotes, on_delete=models.CASCADE, related_name='lignes')
    etudiant = models.ForeignKey('etudiants.Etudiant', on_delete=models.CASCADE, related_name='lignes_pv')
    
    note_1 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    note_2 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    note_3 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    note_4 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    note_5 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    note_cc = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    note_examen = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    note_rattrapage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    note_finale = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    note_cc_manquante = models.BooleanField(default=False)
    note_examen_manquante = models.BooleanField(default=False)
    
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'notes'
        verbose_name = "Ligne de Procès-Verbal de Notes"
        verbose_name_plural = "Lignes de Procès-Verbal de Notes"
        unique_together = ['pv', 'etudiant']
        ordering = ['etudiant__nom', 'etudiant__prenom']

    def __str__(self):
        return f"{self.etudiant.get_nom_complet()} - CC: {self.note_cc if self.note_cc is not None else 'N/A'}, EX: {self.note_examen if self.note_examen is not None else 'N/A'}, RATT: {self.note_rattrapage if self.note_rattrapage is not None else 'N/A'} -> Final: {self.note_finale if self.note_finale is not None else 'N/A'}"

    def get_sub_cc_notes(self, nb_cc):
        """
        Retourne la liste des sous-notes CC de la ligne jusqu'à nb_cc.
        Si nb_cc <= 1, retourne une liste vide [].
        Si nb_cc > 1 et une sous-note est absente/None, elle vaut 0.00.
        """
        if nb_cc <= 1:
            return []
        notes = [self.note_1, self.note_2, self.note_3, self.note_4, self.note_5]
        res = []
        for idx in range(nb_cc):
            val = notes[idx]
            res.append(float(val) if val is not None else 0.0)
        return res

    def calculer_note_finale(self, cc_transmis=False, exam_transmis=False, imputer_zero_si_transmis=False):
        """
        Calcul dynamique de la note finale :
        - Imputation de 0.00 (Absence/Note manquante) effectuée SEULEMENT si le PV est transmis au Chef des Études.
        - Si les deux notes (CC et Examen) sont présentes ou imputées suite à la transmission, la moyenne finale est calculée.
        - Sinon, tant que l'une des deux notes manque et que le PV n'est pas transmis, la moyenne reste à 0.00.
        """
        ratt = float(self.note_rattrapage) if self.note_rattrapage is not None else None
        exam = float(self.note_examen) if self.note_examen is not None else None
        cc = float(self.note_cc) if self.note_cc is not None else None

        exam_effective = ratt if ratt is not None else exam
        les_deux_transmises = (cc_transmis and exam_transmis) or imputer_zero_si_transmis

        if les_deux_transmises:
            if cc is None:
                cc = 0.0
                self.note_cc = 0.0
                self.note_cc_manquante = True
            if exam_effective is None:
                exam_effective = 0.0
                if ratt is None and exam is None:
                    self.note_examen = 0.0
                    self.note_examen_manquante = True

        if cc is not None and exam_effective is not None:
            self.note_finale = round((cc * 0.40) + (exam_effective * 0.60), 2)
        else:
            self.note_finale = 0.0

        return self.note_finale