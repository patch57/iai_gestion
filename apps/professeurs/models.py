"""
Modèles pour la gestion des professeurs
IAI-Cameroun - Centre de Douala
"""
from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator
import os


def photo_professeur_path(instance, filename):
    """Chemin de stockage des photos de professeurs"""
    ext = filename.split('.')[-1]
    filename = f"{instance.matricule}.{ext}"
    return os.path.join('professeurs/photos', filename)


class Departement(models.Model):
    """Départements de l'IAI"""
    code = models.CharField(max_length=10, unique=True)
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    responsable = models.ForeignKey(
        'Professeur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='departement_dirige'
    )
    est_actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'professeurs'
        verbose_name = "Département"
        verbose_name_plural = "Départements"
        ordering = ['nom']
    
    def __str__(self):
        return f"{self.code} - {self.nom}"


class Professeur(models.Model):
    """Modèle représentant un professeur de l'IAI"""
    
    SEXE_CHOICES = [
        ('M', 'Masculin'),
        ('F', 'Féminin'),
    ]
    
    GRADE_CHOICES = [
        ('ASSISTANT', 'Assistant'),
        ('MAITRE_CONF', 'Maître de Conférences'),
        ('PROFESSEUR', 'Professeur'),
        ('VACATAIRE', 'Vacataire'),
        ('EXPERT', 'Expert Professionnel'),
    ]
    
    STATUT_CHOICES = [
        ('ACTIF', 'Actif'),
        ('CONGE', 'En Congé'),
        ('DETACHE', 'Détaché'),
        ('RETRAITE', 'Retraité'),
        ('SUSPENDU', 'Suspendu'),
    ]
    
    # Informations d'identification
    matricule = models.CharField(max_length=20, unique=True)
    
    # Informations personnelles
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    date_naissance = models.DateField()
    lieu_naissance = models.CharField(max_length=100)
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES)
    nationalite = models.CharField(max_length=50, default='Camerounaise')
    
    # Contact
    telephone = models.CharField(
        max_length=20,
        validators=[RegexValidator(r'^\+?\d{9,15}$', 'Numéro de téléphone invalide')]
    )
    email = models.EmailField(unique=True)
    adresse = models.TextField()
    
    # Informations professionnelles
    grade = models.CharField(max_length=20, choices=GRADE_CHOICES)
    departement = models.ForeignKey(
        Departement,
        on_delete=models.PROTECT,
        related_name='professeurs'
    )
    specialite = models.CharField(max_length=200, help_text="Domaine de spécialité")
    diplomes = models.TextField(help_text="Liste des diplômes obtenus")
    annee_experience = models.PositiveIntegerField(default=0)
    statut = models.CharField(max_length=10, choices=STATUT_CHOICES, default='ACTIF')
    
    # Informations contractuelles
    date_embauche = models.DateField()
    type_contrat = models.CharField(
        max_length=20,
        choices=[
            ('CDI', 'Contrat à Durée Indéterminée'),
            ('CDD', 'Contrat à Durée Déterminée'),
            ('VACATAIRE', 'Vacataire'),
        ],
        default='CDI'
    )
    salaire_base = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Photo
    photo = models.ImageField(upload_to=photo_professeur_path, blank=True, null=True)
    
    # Métadonnées
    utilisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='profil_professeur'
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'professeurs'
        verbose_name = "Professeur"
        verbose_name_plural = "Professeurs"
        ordering = ['nom', 'prenom']
        permissions = [
            ('peut_exporter_professeurs', 'Peut exporter la liste des professeurs'),
            ('peut_voir_salaires', 'Peut voir les informations salariales'),
        ]
    
    def __str__(self):
        return f"{self.matricule} - {self.nom} {self.prenom} ({self.get_grade_display()})"
    
    def get_nom_complet(self):
        return f"{self.nom} {self.prenom}"
    
    def get_anciennete(self):
        """Calcule l'ancienneté du professeur en années"""
        from datetime import date
        return (date.today() - self.date_embauche).days // 365
    
    def get_nombre_cours(self):
        """Retourne le nombre de cours assignés"""
        return self.cours_assignes.filter(est_actif=True).count()
    
    def get_heures_enseignement(self, annee_academique=None):
        """Calcule les heures d'enseignement"""
        from apps.cours.models import SeanceCours
        seances = SeanceCours.objects.filter(
            cours__professeur=self,
            est_effectuee=True
        )
        if annee_academique:
            seances = seances.filter(cours__annee_academique=annee_academique)
        total_heures = sum(s.duree_heures for s in seances)
        return total_heures


class ChargeHoraire(models.Model):
    """Charge horaire d'un professeur pour une année académique"""
    professeur = models.ForeignKey(Professeur, on_delete=models.CASCADE, related_name='charges_horaires')
    annee_academique = models.CharField(max_length=9, default='2024-2025')
    heures_assignees = models.PositiveIntegerField(default=0)
    heures_effectuees = models.PositiveIntegerField(default=0)
    heures_supplementaires = models.PositiveIntegerField(default=0)
    taux_horaire = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    montant_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    est_paye = models.BooleanField(default=False)
    date_paiement = models.DateField(blank=True, null=True)
    
    class Meta:
        app_label = 'professeurs'
        verbose_name = "Charge Horaire"
        verbose_name_plural = "Charges Horaires"
        unique_together = ['professeur', 'annee_academique']
        ordering = ['-annee_academique']
    
    def __str__(self):
        return f"{self.professeur} - {self.annee_academique}"
    
    def calculer_montant(self):
        """Calcule le montant total à payer"""
        heures_normales = min(self.heures_effectuees, self.heures_assignees)
        heures_sup = max(0, self.heures_effectuees - self.heures_assignees)
        self.heures_supplementaires = heures_sup
        self.montant_total = (heures_normales + heures_sup * 1.5) * self.taux_horaire
        return self.montant_total


class DocumentProfesseur(models.Model):
    """Documents associés à un professeur"""
    TYPE_DOCUMENT_CHOICES = [
        ('DIPLOME', 'Diplôme'),
        ('CV', 'Curriculum Vitae'),
        ('CNI', 'Carte Nationale d\'Identité'),
        ('CONTRAT', 'Contrat de Travail'),
        ('CERTIFICAT', 'Certificat de Travail'),
        ('AUTRE', 'Autre Document'),
    ]
    
    professeur = models.ForeignKey(Professeur, on_delete=models.CASCADE, related_name='documents')
    type_document = models.CharField(max_length=20, choices=TYPE_DOCUMENT_CHOICES)
    fichier = models.FileField(upload_to='professeurs/documents/')
    description = models.TextField(blank=True)
    date_ajout = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'professeurs'
        verbose_name = "Document Professeur"
        verbose_name_plural = "Documents Professeurs"
        ordering = ['-date_ajout']
    
    def __str__(self):
        return f"{self.get_type_document_display()} - {self.professeur}"


class DisponibiliteProfesseur(models.Model):
    """Disponibilités des professeurs pour les cours"""
    JOUR_CHOICES = [
        ('LUN', 'Lundi'),
        ('MAR', 'Mardi'),
        ('MER', 'Mercredi'),
        ('JEU', 'Jeudi'),
        ('VEN', 'Vendredi'),
        ('SAM', 'Samedi'),
    ]
    
    professeur = models.ForeignKey(Professeur, on_delete=models.CASCADE, related_name='disponibilites')
    jour = models.CharField(max_length=3, choices=JOUR_CHOICES)
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    est_disponible = models.BooleanField(default=True)
    
    class Meta:
        app_label = 'professeurs'
        verbose_name = "Disponibilité Professeur"
        verbose_name_plural = "Disponibilités Professeurs"
        ordering = ['jour', 'heure_debut']
    
    def __str__(self):
        return f"{self.professeur} - {self.get_jour_display()} ({self.heure_debut}-{self.heure_fin})"