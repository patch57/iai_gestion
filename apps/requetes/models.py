from django.db import models
from django.conf import settings
from django.utils import timezone


class Requete(models.Model):
    """Modèle pour la gestion des requêtes (tickets) des étudiants et apprenants"""
    
    NATURE_CHOICES = [
        ('SCOLARITE', 'Scolarité'),
        ('ETUDES', 'Diplômes et Attestations'),
        ('ANONYMAT', 'Revendication de notes'),
        ('COMPTABILITE', 'Paiements'),
    ]
    
    STATUT_CHOICES = [
        ('SOUMIS', 'Soumise'),
        ('EN_COURS', 'En cours de traitement'),
        ('ESCALADE', 'Escaladée au Directeur'),
        ('RENVOYE', 'Renvoyée au personnel'),
        ('TRAITE', 'Traitée / Répondue'),
    ]
    
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='requetes_creees',
        verbose_name="Auteur de la requête"
    )
    titre = models.CharField(max_length=150, verbose_name="Titre / Objet")
    nature = models.CharField(max_length=20, choices=NATURE_CHOICES, verbose_name="Nature de la requête")
    description = models.TextField(verbose_name="Description détaillée")
    piece_jointe = models.FileField(
        upload_to='requetes/pieces_jointes/%Y/%m/',
        blank=True,
        null=True,
        verbose_name="Pièce jointe",
        help_text="PDF, JPG, PNG (max 5MB)"
    )
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default='SOUMIS',
        verbose_name="Statut"
    )
    assigne_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requetes_assignees',
        verbose_name="Assignée à"
    )
    reponse = models.TextField(blank=True, default='', verbose_name="Réponse finale")
    reponse_interne = models.TextField(blank=True, default='', verbose_name="Notes / Réponses internes (Directeur)")
    
    # Dates
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    date_modification = models.DateTimeField(auto_now=True, verbose_name="Date de modification")
    
    # Historique de suivi (stocké sous forme de liste de dicts)
    historique = models.JSONField(default=list, blank=True, verbose_name="Historique de suivi")

    class Meta:
        app_label = 'requetes'
        verbose_name = "Requête"
        verbose_name_plural = "Requêtes"
        ordering = ['-date_creation']

    def __str__(self):
        return f"Req #{self.id} - {self.get_nature_display()} - {self.auteur.get_full_name() or self.auteur.username}"

    def ajouter_action_historique(self, action, auteur, details=""):
        """Ajoute une trace d'action dans l'historique"""
        entree = {
            'action': action,
            'auteur': auteur.get_full_name() or auteur.username,
            'role': auteur.get_type_utilisateur_display() if hasattr(auteur, 'get_type_utilisateur_display') else str(auteur),
            'date': timezone.now().isoformat(),
            'details': details
        }
        if not self.historique:
            self.historique = []
        self.historique.append(entree)

    def get_nom_fichier(self):
        """Retourne le nom de la pièce jointe"""
        import os
        if self.piece_jointe:
            return os.path.basename(self.piece_jointe.name)
        return None
