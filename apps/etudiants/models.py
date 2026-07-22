"""
Modèles pour la gestion des étudiants
IAI-Cameroun - Centre de Douala
Conforme aux règles de gestion du centre
"""
from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
import os
import re
from datetime import date


def photo_etudiant_path(instance, filename):
    """Chemin de stockage des photos d'étudiants"""
    ext = filename.split('.')[-1]
    filename = f"{instance.matricule}.{ext}"
    return os.path.join('etudiants/photos', filename)


class AnneeAcademique(models.Model):
    """Gestion des années académiques"""
    code = models.CharField(
        max_length=9, 
        unique=True,
        verbose_name="Année académique",
        help_text="Format: 2024-2025"
    )
    date_debut = models.DateField(verbose_name="Date de début")
    date_fin = models.DateField(verbose_name="Date de fin")
    est_active = models.BooleanField(
        default=False,
        verbose_name="Est active"
    )
    
    class Meta:
        app_label = 'etudiants'
        verbose_name = "Année académique"
        verbose_name_plural = "Années académiques"
        ordering = ['-date_debut']
    
    def __str__(self):
        return self.code
    
    def save(self, *args, **kwargs):
        """Une seule année académique peut être active à la fois"""
        if self.est_active:
            AnneeAcademique.objects.filter(est_active=True).update(est_active=False)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_active(cls):
        """Retourne l'année académique active"""
        try:
            return cls.objects.get(est_active=True)
        except cls.DoesNotExist:
            return None


class Filiere(models.Model):
    """Filières de formation à l'IAI-Cameroun"""
    CODE_FILIERE_CHOICES = [
        ('GL', 'Génie Logiciel'),
        ('SR', 'Systèmes et Réseaux'),
    ]
    
    code = models.CharField(
        max_length=2, 
        choices=CODE_FILIERE_CHOICES, 
        unique=True,
        verbose_name="Code filière"
    )
    nom = models.CharField(
        max_length=100,
        verbose_name="Nom complet"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description"
    )
    duree_ans = models.PositiveIntegerField(
        default=2,
        verbose_name="Durée (années)",
        help_text="Durée de formation en années (DTS: 2 ans)"
    )
    est_active = models.BooleanField(
        default=True,
        verbose_name="Est active"
    )
    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )
    
    class Meta:
        app_label = 'etudiants'
        verbose_name = "Filière"
        verbose_name_plural = "Filières"
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.nom}"
    
    def save(self, *args, **kwargs):
        self.nom = dict(self.CODE_FILIERE_CHOICES).get(self.code, self.code)
        super().save(*args, **kwargs)


class Niveau(models.Model):
    """Niveaux d'études (Niveau 1 et Niveau 2 pour DTS)"""
    NIVEAUX_CHOICES = [
        (1, 'Niveau 1'),
        (2, 'Niveau 2'),
    ]
    
    numero = models.IntegerField(
        choices=NIVEAUX_CHOICES,
        verbose_name="Numéro du niveau"
    )
    filiere = models.ForeignKey(
        Filiere,
        on_delete=models.CASCADE,
        related_name='niveaux',
        verbose_name="Filière"
    )
    code = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        verbose_name="Code"
    )
    
    class Meta:
        app_label = 'etudiants'
        verbose_name = "Niveau"
        verbose_name_plural = "Niveaux"
        ordering = ['filiere__code', 'numero']
        unique_together = ['numero', 'filiere']
    
    def __str__(self):
        return f"{self.filiere.code} - Niveau {self.numero}"
    
    def save(self, *args, **kwargs):
        self.code = f"{self.filiere.code}-N{self.numero}"
        super().save(*args, **kwargs)


class Classe(models.Model):
    """Classe par filière, niveau et année académique"""
    nom = models.CharField(
        max_length=50,
        verbose_name="Nom de la classe"
    )
    filiere = models.ForeignKey(
        Filiere,
        on_delete=models.CASCADE,
        related_name='classes',
        verbose_name="Filière"
    )
    niveau = models.ForeignKey(
        Niveau,
        on_delete=models.CASCADE,
        related_name='classes',
        verbose_name="Niveau"
    )
    annee_academique = models.ForeignKey(
        AnneeAcademique,
        on_delete=models.CASCADE,
        related_name='classes',
        verbose_name="Année académique"
    )
    effectif_max = models.PositiveIntegerField(
        default=40,
        verbose_name="Effectif maximum"
    )
    effectif_actuel = models.PositiveIntegerField(
        default=0,
        verbose_name="Effectif actuel"
    )
    est_active = models.BooleanField(
        default=True,
        verbose_name="Est active"
    )
    
    class Meta:
        app_label = 'etudiants'
        verbose_name = "Classe"
        verbose_name_plural = "Classes"
        ordering = ['filiere__code', 'niveau__numero', 'nom']
        unique_together = ['nom', 'annee_academique']
    
    def __str__(self):
        return f"{self.nom} - {self.filiere.code} ({self.annee_academique.code})"
    
    def places_disponibles(self):
        """Retourne le nombre de places disponibles"""
        return self.effectif_max - self.effectif_actuel
    
    def peut_inscrire(self):
        """Vérifie si la classe peut encore accueillir des étudiants"""
        return self.places_disponibles() > 0 and self.est_active

    @classmethod
    def repartir_etudiants(cls, annee_academique):
        """
        Répartit automatiquement tous les étudiants inscrits/actifs de l'année académique
        dans les différentes classes disponibles par filière et niveau, en respectant la capacité.
        """
        from apps.etudiants.models import Etudiant
        
        # Récupérer toutes les classes actives de cette année académique
        classes_dispos = cls.objects.filter(annee_academique=annee_academique, est_active=True).order_by('id')
        
        # Grouper les classes par (filiere_id, niveau_id)
        classes_par_groupe = {}
        for c in classes_dispos:
            key = (c.filiere_id, c.niveau_id)
            if key not in classes_par_groupe:
                classes_par_groupe[key] = []
            classes_par_groupe[key].append(c)
            
        # Récupérer tous les étudiants inscrits ou actifs pour cette année académique
        etudiants = Etudiant.objects.filter(
            annee_academique=annee_academique,
            statut__in=['INSCRIT', 'ACTIF']
        ).order_by('nom', 'prenom')
        
        repartis_count = 0
        
        for etudiant in etudiants:
            # Si l'étudiant a déjà une classe valide, on le maintient
            if etudiant.classe and etudiant.classe.est_active and etudiant.classe.filiere == etudiant.filiere and etudiant.classe.niveau == etudiant.niveau and etudiant.classe.annee_academique == annee_academique:
                continue
                
            key = (etudiant.filiere_id, etudiant.niveau_id)
            classes_cibles = classes_par_groupe.get(key, [])
            
            # Trouver la première classe avec des places disponibles
            classe_trouvee = None
            for classe in classes_cibles:
                effectif = classe.etudiants.count()
                if effectif < classe.effectif_max:
                    classe_trouvee = classe
                    break
                    
            if classe_trouvee:
                etudiant.classe = classe_trouvee
                etudiant.save(update_fields=['classe'])
                
                # Mettre à jour l'effectif actuel de la classe
                classe_trouvee.effectif_actuel = classe_trouvee.etudiants.count()
                classe_trouvee.save(update_fields=['effectif_actuel'])
                repartis_count += 1
                
        # Recalculer l'effectif de toutes les classes par sécurité
        for c in classes_dispos:
            c.effectif_actuel = c.etudiants.count()
            c.save(update_fields=['effectif_actuel'])
            
        return repartis_count


class DocumentObligatoire(models.Model):
    """
    Documents obligatoires définis par l'administration
    Ces documents sont requis pour l'inscription des étudiants
    Règle de gestion: L'admin définit les documents à fournir par l'étudiant
    """
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
    
    type_document = models.CharField(
        max_length=30,
        choices=TYPE_DOCUMENT_CHOICES,
        unique=True,
        verbose_name="Type de document"
    )
    nom = models.CharField(max_length=100, verbose_name="Nom du document")
    description = models.TextField(blank=True, verbose_name="Description")
    format_accepte = models.CharField(
        max_length=100,
        default='PDF, JPG, PNG',
        verbose_name="Formats acceptés"
    )
    taille_max_mb = models.PositiveIntegerField(default=5, verbose_name="Taille max (Mo)")
    
    # Filtrage par filière et niveau (si applicable)
    filiere = models.ForeignKey(
        'Filiere',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Filière concernée",
        help_text="Laisser vide pour toutes les filières"
    )
    niveau = models.ForeignKey(
        'Niveau',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Niveau concerné",
        help_text="Laisser vide pour tous les niveaux"
    )
    
    # Statut
    est_actif = models.BooleanField(default=True, verbose_name="Document actif")
    est_obligatoire = models.BooleanField(default=True, verbose_name="Obligatoire")
    ordre_affichage = models.PositiveIntegerField(default=0, verbose_name="Ordre d'affichage")
    
    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents_obligatoires_crees'
    )
    
    class Meta:
        app_label = 'etudiants'
        verbose_name = "Document obligatoire"
        verbose_name_plural = "Documents obligatoires"
        ordering = ['ordre_affichage', 'type_document']
        permissions = [
            ('can_manage_documents', 'Peut gérer les documents obligatoires'),
            ('can_validate_documents', 'Peut valider les documents étudiants'),
        ]
    
    def __str__(self):
        return f"{self.nom} ({self.get_type_document_display()})"
    
    def est_requis_pour_etudiant(self, etudiant):
        """Vérifie si ce document est requis pour un étudiant donné"""
        if not self.est_actif:
            return False
        
        if self.filiere and etudiant.filiere != self.filiere:
            return False
        
        if self.niveau and etudiant.niveau != self.niveau:
            return False
        
        return True


class Etudiant(models.Model):
    """Modèle représentant un étudiant de l'IAI-Cameroun"""
    
    SEXE_CHOICES = [
        ('M', 'Masculin'),
        ('F', 'Féminin'),
    ]
    
    STATUT_CHOICES = [
        ('PREINSCRIT', 'Pré-inscrit'),
        ('INSCRIT', 'Inscrit'),
        ('ACTIF', 'Actif'),
        ('SUSPENDU', 'Suspendu'),
        ('EXCLU', 'Exclu'),
        ('DIPLOME', 'Diplômé'),
        ('ABANDON', 'Abandon'),
    ]
    
    NATIONALITE_CHOICES = [
        ('CMR', 'Camerounaise'),
        ('CIV', 'Ivoirienne'),
        ('SEN', 'Sénégalaise'),
        ('GAB', 'Gabonaise'),
        ('TCD', 'Tchadienne'),
        ('RCA', 'Centrafricaine'),
        ('COG', 'Congolaise'),
        ('GIN', 'Guinéenne'),
        ('BEN', 'Béninoise'),
        ('TGO', 'Togolaise'),
        ('FRA', 'Française'),
        ('BEL', 'Belge'),
        ('CAN', 'Canadienne'),
        ('USA', 'Américaine'),
        ('CHN', 'Chinoise'),
        ('AUT', 'Autre'),
    ]
    
    # Informations d'identification
    matricule = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Matricule",
        help_text="Format: GL.CMR.D014.2324A ou SR.CMR.D014.2324A"
    )
    
    # Informations personnelles
    nom = models.CharField(max_length=100, verbose_name="Nom")
    prenom = models.CharField(max_length=100, verbose_name="Prénom")
    date_naissance = models.DateField(verbose_name="Date de naissance")
    lieu_naissance = models.CharField(max_length=100, verbose_name="Lieu de naissance")
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES, verbose_name="Sexe")
    nationalite = models.CharField(
        max_length=3,
        choices=NATIONALITE_CHOICES,
        default='CMR',
        verbose_name="Nationalité"
    )
    
    # Contact
    telephone = models.CharField(
        max_length=20,
        validators=[RegexValidator(r'^\+?\d{9,15}$', 'Numéro de téléphone invalide')],
        verbose_name="Téléphone"
    )
    email = models.EmailField(unique=True, verbose_name="Email")
    adresse = models.TextField(verbose_name="Adresse")
    
    # Informations académiques
    filiere = models.ForeignKey(
        Filiere,
        on_delete=models.PROTECT,
        related_name='etudiants',
        verbose_name="Filière"
    )
    niveau = models.ForeignKey(
        Niveau,
        on_delete=models.PROTECT,
        related_name='etudiants',
        null=True,
        blank=True,
        verbose_name="Niveau"
    )
    classe = models.ForeignKey(
        Classe,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='etudiants',
        verbose_name="Classe"
    )
    annee_academique = models.ForeignKey(
        AnneeAcademique,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Année académique"
    )
    statut = models.CharField(
        max_length=10,
        choices=STATUT_CHOICES,
        default='PREINSCRIT',
        verbose_name="Statut"
    )
    
    # Documents
    photo = models.ImageField(
        upload_to=photo_etudiant_path,
        blank=True,
        null=True,
        verbose_name="Photo"
    )
    recu_preinscription = models.FileField(
        upload_to='etudiants/recus/preinscription/',
        blank=True,
        null=True,
        verbose_name="Reçu de pré-inscription"
    )
    recu_preinscription_valide = models.BooleanField(
        default=False,
        verbose_name="Reçu de pré-inscription validé"
    )
    carte_etudiant_delivree = models.BooleanField(
        default=False,
        verbose_name="Carte d'étudiant délivrée"
    )
    date_delivrance_carte = models.DateField(
        blank=True,
        null=True,
        verbose_name="Date de délivrance carte"
    )
    
    # Informations du tuteur/parent
    nom_tuteur = models.CharField(max_length=100, blank=True, default='', verbose_name="Nom du tuteur")
    telephone_tuteur = models.CharField(max_length=20, blank=True, default='', verbose_name="Téléphone du tuteur")
    email_tuteur = models.EmailField(blank=True, null=True, verbose_name="Email du tuteur")
    nom_pere = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nom du père")
    telephone_pere = models.CharField(max_length=20, blank=True, null=True, verbose_name="Téléphone du père")
    nom_mere = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nom de la mère")
    telephone_mere = models.CharField(max_length=20, blank=True, null=True, verbose_name="Téléphone de la mère")
    
    # Informations de santé
    groupe_sanguin = models.CharField(
        max_length=5,
        blank=True,
        null=True,
        verbose_name="Groupe sanguin"
    )
    allergies = models.TextField(blank=True, null=True, verbose_name="Allergies")
    informations_medicales = models.TextField(
        blank=True,
        null=True,
        verbose_name="Informations médicales"
    )
    
    # Métadonnées
    utilisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='profil_etudiant',
        verbose_name="Utilisateur associé"
    )
    date_inscription = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date d'inscription"
    )
    date_modification = models.DateTimeField(
        auto_now=True,
        verbose_name="Date de modification"
    )
    
    class Meta:
        app_label = 'etudiants'
        verbose_name = "Étudiant"
        verbose_name_plural = "Étudiants"
        ordering = ['nom', 'prenom']
        permissions = [
            ('peut_exporter_etudiants', 'Peut exporter la liste des étudiants'),
            ('peut_importer_etudiants', 'Peut importer des étudiants'),
            ('peut_valider_recus', 'Peut valider les reçus de paiement'),
            ('peut_inscrire_etudiants', 'Peut inscrire des étudiants'),
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_statut = self.statut
        self._original_classe = self.classe
    
    def __str__(self):
        return f"{self.matricule} - {self.nom} {self.prenom}"
    
    def clean(self):
        """Validation globale avant sauvegarde"""
        super().clean()
        if self.matricule:
            self.valider_matricule()
        
        # Vérifier la cohérence avec l'utilisateur
        if self.utilisateur and self.utilisateur.matricule != self.matricule:
            raise ValidationError({
                'matricule': 'Le matricule doit correspondre à celui de l\'utilisateur associé'
            })
        
        # Vérifier la cohérence filière-niveau
        if self.filiere and self.niveau and self.niveau.filiere != self.filiere:
            raise ValidationError({
                'niveau': 'Le niveau doit correspondre à la filière sélectionnée'
            })
    
    def valider_matricule(self):
        """Valide le format du matricule selon les règles IAI"""
        # Format supporté : GL.CMR.DO14.2425 (nouveau) ou GL.CMR.D014.2324A (ancien)
        pattern = r'^(GL|SR)\.CMR\.(D\d{3}|DO\d{2}|D014)\.\d{4}[A-Z]?$'
        if not re.match(pattern, self.matricule):
            raise ValidationError({
                'matricule': 'Format de matricule invalide. Exemples acceptés: GL.CMR.D043.2324A ou GL.CMR.DO14.2425'
            })
        
        # Vérifier que le code filière correspond à la filière choisie
        filiere_code = self.matricule.split('.')[0]
        if self.filiere and filiere_code != self.filiere.code:
            raise ValidationError({
                'matricule': f'Le matricule indique la filière {filiere_code} mais la filière sélectionnée est {self.filiere.code}'
            })
        
        # Vérifier la cohérence avec le bac de l'utilisateur
        if self.utilisateur and self.utilisateur.type_baccalaureat:
            if self.utilisateur.type_baccalaureat.startswith('A') and filiere_code != 'GL':
                raise ValidationError({
                    'matricule': f'Bac série A ({self.utilisateur.type_baccalaureat}) → uniquement Génie Logiciel (GL)'
                })
    
    def save(self, *args, **kwargs):
        """Sauvegarde avec validation et mise à jour automatique"""
        # Synchroniser avec l'utilisateur si nécessaire
        if self.utilisateur and not self.matricule:
            self.matricule = self.utilisateur.matricule
        
        self.full_clean()
        
        # Mettre à jour l'effectif de la classe si le statut change
        if self.pk:
            # Changement de statut
            if self._original_statut != self.statut:
                if self.statut in ['ACTIF', 'INSCRIT'] and self.classe:
                    self.classe.effectif_actuel += 1
                    self.classe.save()
                elif self._original_statut in ['ACTIF', 'INSCRIT'] and self._original_classe:
                    self._original_classe.effectif_actuel -= 1
                    self._original_classe.save()
            
            # Changement de classe
            elif self._original_classe != self.classe:
                if self.classe and self.statut in ['ACTIF', 'INSCRIT']:
                    self.classe.effectif_actuel += 1
                    self.classe.save()
                if self._original_classe:
                    self._original_classe.effectif_actuel -= 1
                    self._original_classe.save()
        
        super().save(*args, **kwargs)
        
        # Mettre à jour l'utilisateur avec les informations de l'étudiant
        if self.utilisateur:
            self.utilisateur.first_name = self.prenom
            self.utilisateur.last_name = self.nom
            self.utilisateur.email = self.email
            if hasattr(self.utilisateur, 'telephone'):
                self.utilisateur.telephone = self.telephone
            if hasattr(self.utilisateur, 'adresse'):
                self.utilisateur.adresse = self.adresse
            self.utilisateur.save(update_fields=['first_name', 'last_name', 'email', 'telephone', 'adresse'])
    
    def generer_matricule(self):
        """Génère un matricule automatiquement"""
        from datetime import datetime
        
        annee_active = AnneeAcademique.get_active()
        if annee_active:
            parties = annee_active.code.split('-')
            suffixe_annee = parties[0][2:] + parties[1][2:]
        else:
            annee = datetime.now().year
            suffixe_annee = f"{str(annee)[2:]}{str(annee+1)[2:]}"
        
        if self.filiere:
            num_ordre = Etudiant.objects.filter(filiere=self.filiere).count() + 1
            self.matricule = f"{self.filiere.code}.CMR.DO{num_ordre:02d}.{suffixe_annee}A"
    
    # ========== MÉTHODES MÉTIER ==========
    
    def get_nom_complet(self):
        """Retourne le nom complet de l'étudiant"""
        return f"{self.nom} {self.prenom}"
    
    def get_age(self):
        """Calcule l'âge de l'étudiant"""
        today = date.today()
        return today.year - self.date_naissance.year - (
            (today.month, today.day) < (self.date_naissance.month, self.date_naissance.day)
        )
    
    def get_filiere_code(self):
        """Retourne le code de la filière"""
        if self.matricule:
            return self.matricule.split('.')[0]
        return None
    
    def est_inscrit_annee_actuelle(self):
        """Vérifie si l'étudiant est inscrit pour l'année académique en cours"""
        annee_active = AnneeAcademique.get_active()
        if annee_active and self.annee_academique:
            return self.annee_academique == annee_active and self.statut in ['INSCRIT', 'ACTIF']
        return False
    
    def a_paye_tranche(self, numero_tranche):
        """Vérifie si l'étudiant a payé une tranche spécifique"""
        from apps.paiements.models import RecuPaiement
        return RecuPaiement.objects.filter(
            etudiant=self,
            tranche__numero=numero_tranche,
            statut='VALIDE'
        ).exists()
    
    def statut_paiement(self):
        """Retourne le statut complet des paiements"""
        statuts = {
            'preinscription': self.recu_preinscription_valide,
            'tranche_1': self.a_paye_tranche(1),
            'tranche_2': self.a_paye_tranche(2),
            'tranche_3': self.a_paye_tranche(3),
        }
        
        paiements_effectues = sum(statuts.values())
        paiements_total = 4
        statuts['pourcentage'] = (paiements_effectues / paiements_total) * 100
        
        return statuts
    
    def est_inscrit_completement(self):
        """Vérifie si l'étudiant est complètement inscrit"""
        return self.recu_preinscription_valide and self.a_paye_tranche(1)
    
    def peut_acceder_cours(self):
        """Vérifie si l'étudiant peut accéder aux cours"""
        return self.statut == 'ACTIF' and self.est_inscrit_completement()
    
    def get_moyenne_generale(self):
        """Calcule la moyenne générale de l'étudiant"""
        from apps.notes.models import Note
        notes = Note.objects.filter(
            etudiant=self,
            annee_academique=self.annee_academique
        )
        if notes.exists():
            return notes.aggregate(models.Avg('valeur'))['valeur__avg']
        return None
    
    def get_statut_display_colore(self):
        """Retourne le statut avec une couleur pour l'affichage"""
        couleurs = {
            'PREINSCRIT': 'warning',
            'INSCRIT': 'info',
            'ACTIF': 'success',
            'SUSPENDU': 'danger',
            'EXCLU': 'danger',
            'DIPLOME': 'primary',
            'ABANDON': 'secondary',
        }
        return {
            'statut': self.get_statut_display(),
            'couleur': couleurs.get(self.statut, 'secondary')
        }
    
    def get_documents_obligatoires_manquants(self):
        """Retourne la liste des documents obligatoires manquants pour cet étudiant"""
        documents_obligatoires = DocumentObligatoire.objects.filter(
            est_actif=True
        ).filter(
            models.Q(filiere__isnull=True) | models.Q(filiere=self.filiere)
        ).filter(
            models.Q(niveau__isnull=True) | models.Q(niveau=self.niveau)
        )
        
        manquants = []
        for doc_oblig in documents_obligatoires:
            doc_existant = DocumentEtudiant.objects.filter(
                etudiant=self,
                type_document=doc_oblig.type_document,
                est_valide=True
            ).exists()
            
            if not doc_existant:
                manquants.append({
                    'type_document': doc_oblig.type_document,
                    'nom': doc_oblig.nom,
                    'description': doc_oblig.description
                })
        
        return manquants
    
    def a_tous_documents_obligatoires(self):
        """Vérifie si l'étudiant a fourni tous les documents obligatoires"""
        return len(self.get_documents_obligatoires_manquants()) == 0


class DocumentEtudiant(models.Model):
    """Documents associés à un étudiant"""
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
        ('RECU_PREINSCRIPTION', 'Reçu de Pré-inscription'),
        ('RECU_TRANCHE1', 'Reçu 1ère Tranche'),
        ('RECU_TRANCHE2', 'Reçu 2ème Tranche'),
        ('RECU_TRANCHE3', 'Reçu 3ème Tranche'),
        ('RELEVE_NOTES', 'Relevé de Notes'),
        ('AUTRE', 'Autre Document'),
    ]
    
    etudiant = models.ForeignKey(
        Etudiant,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name="Étudiant"
    )
    type_document = models.CharField(
        max_length=30,
        choices=TYPE_DOCUMENT_CHOICES,
        verbose_name="Type de document"
    )
    fichier = models.FileField(
        upload_to='etudiants/documents/%Y/%m/',
        verbose_name="Fichier"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description"
    )
    est_obligatoire = models.BooleanField(
        default=False,
        verbose_name="Document obligatoire",
        help_text="Ce document est-il requis pour l'inscription ?"
    )
    est_valide = models.BooleanField(
        default=False,
        verbose_name="Est validé"
    )
    commentaire = models.TextField(
        blank=True,
        verbose_name="Commentaire",
        help_text="Motif de rejet ou remarques"
    )
    date_ajout = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date d'ajout"
    )
    date_validation = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Date de validation"
    )
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents_etudiants_valides',
        verbose_name="Validé par"
    )
    
    class Meta:
        app_label = 'etudiants'
        verbose_name = "Document étudiant"
        verbose_name_plural = "Documents étudiants"
        ordering = ['-date_ajout']
        unique_together = ['etudiant', 'type_document']
    
    def __str__(self):
        return f"{self.get_type_document_display()} - {self.etudiant}"
    
    def save(self, *args, **kwargs):
        if self.est_valide and not self.date_validation:
            self.date_validation = timezone.now()
        super().save(*args, **kwargs)


class HistoriqueEtudiant(models.Model):
    """Historique des modifications sur un étudiant"""
    ACTION_CHOICES = [
        ('CREATION', 'Création'),
        ('MODIFICATION', 'Modification'),
        ('INSCRIPTION', 'Inscription'),
        ('PAIEMENT', 'Paiement'),
        ('CHANGEMENT_CLASSE', 'Changement de classe'),
        ('CHANGEMENT_STATUT', 'Changement de statut'),
        ('DOCUMENT_AJOUTE', 'Document ajouté'),
        ('DOCUMENT_VALIDE', 'Document validé'),
        ('DOCUMENT_REJETE', 'Document rejeté'),
        ('RECU_VALIDE', 'Reçu validé'),
        ('RECU_REJETE', 'Reçu rejeté'),
    ]
    
    etudiant = models.ForeignKey(
        Etudiant,
        on_delete=models.CASCADE,
        related_name='historique',
        verbose_name="Étudiant"
    )
    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
        verbose_name="Action"
    )
    details = models.TextField(verbose_name="Détails")
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
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
        app_label = 'etudiants'
        verbose_name = "Historique étudiant"
        verbose_name_plural = "Historique étudiants"
        ordering = ['-date_action']
    
    def __str__(self):
        return f"{self.get_action_display()} - {self.etudiant} - {self.date_action.strftime('%d/%m/%Y %H:%M')}"


class Formation(models.Model):
    """Formations certifiantes et formation continue"""
    TYPES = [
        ('CERTIFICATION', 'Formation de Certification'),
        ('CONTINUE', 'Formation Continue'),
    ]
    NOM_CHOICES = [
        ('SECRETARIAT', 'Secrétariat bureautique et comptable'),
        ('MARKETING', 'Marketing digital'),
        ('INFOGRAPHIE', 'Infographie'),
        ('MAINTENANCE', 'Maintenance informatique'),
        ('RESEAUX', 'Réseaux informatiques'),
        ('WEBMASTER', 'Webmaster'),
        ('MIJEF', 'Formation continue MIJEF 2035'),
    ]
    type_formation = models.CharField(max_length=20, choices=TYPES, default='CERTIFICATION')
    nom = models.CharField(max_length=50, choices=NOM_CHOICES, unique=True)
    description = models.TextField(blank=True)
    tarif = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Tarif de la formation en FCFA")
    est_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'etudiants'
        verbose_name = "Formation de certification"
        verbose_name_plural = "Formations de certification"

    def __str__(self):
        return f"{self.get_nom_display()} ({self.get_type_formation_display()})"


class Apprenant(models.Model):
    """Profil spécifique d'un apprenant pour les certifications"""
    utilisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profil_apprenant'
    )
    nom_complet = models.CharField(max_length=200)
    date_naissance = models.DateField(null=True, blank=True)
    sexe = models.CharField(max_length=1, choices=[('M', 'Masculin'), ('F', 'Féminin')], default='M')
    niveau_etude = models.CharField(max_length=100, blank=True, help_text="Niveau d'étude actuel ou diplôme le plus élevé")
    email = models.EmailField(unique=True)
    contact = models.CharField(max_length=20)
    lieu_residence = models.CharField(max_length=150)
    
    # Coordonnées des parents
    nom_pere = models.CharField(max_length=100, blank=True)
    contact_pere = models.CharField(max_length=20, blank=True)
    nom_mere = models.CharField(max_length=100, blank=True)
    contact_mere = models.CharField(max_length=20, blank=True)
    
    # Formation suivie
    formations = models.ManyToManyField(Formation, related_name='apprenants', blank=True)
    
    # Suivi financier
    montant_paye = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    reste_a_payer = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Attestation et diplôme
    attestation = models.FileField(upload_to='apprenants/attestations/', blank=True, null=True)
    dqp = models.FileField(upload_to='apprenants/dqp/', blank=True, null=True, verbose_name="Diplôme de Qualification Professionnelle")
    
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'etudiants'
        verbose_name = "Apprenant"
        verbose_name_plural = "Apprenants"

    def __str__(self):
        return f"{self.nom_complet} ({self.email})"
        
    def recalculer_solde(self):
        """Calcule le reste à payer en fonction des tarifs des formations suivies"""
        total_tarif = sum(f.tarif for f in self.formations.all())
        self.reste_a_payer = max(0, total_tarif - self.montant_paye)
        self.save()