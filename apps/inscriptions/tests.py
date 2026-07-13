from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

from apps.etudiants.models import Etudiant, Filiere, AnneeAcademique as AnneeAcademiqueEtudiant
from apps.inscriptions.models import AnneeAcademique, Bourse
from apps.inscriptions.forms import BourseForm

User = get_user_model()

class BourseTestCase(TestCase):
    def setUp(self):
        # Création de l'utilisateur
        self.user = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='password123',
            type_utilisateur='ADMIN_SYSTEME'
        )
        
        # Année académique (Etudiants)
        self.annee_etudiant = AnneeAcademiqueEtudiant.objects.create(
            code="2024-2025",
            date_debut=timezone.now().date(),
            date_fin=timezone.now().date(),
            est_active=True
        )
        
        # Année académique (Inscriptions)
        self.annee = AnneeAcademique.objects.create(
            code="2024-2025",
            date_debut=timezone.now().date(),
            date_fin=timezone.now().date(),
            est_actuelle=True,
            est_ouverte_inscription=True
        )
        
        # Filière
        self.filiere = Filiere.objects.create(
            code="GL",
            nom="Génie Logiciel",
            est_active=True
        )
        
        # Création de l'utilisateur étudiant
        self.user_etudiant = User.objects.create_user(
            username='jean_dupont',
            email='jean.dupont@iai.com',
            password='password123',
            type_utilisateur='ETUDIANT',
            matricule="GL.CMR.D014.2425A"
        )
        
        # Étudiant
        self.etudiant = Etudiant.objects.create(
            nom="Dupont",
            prenom="Jean",
            sexe="M",
            date_naissance="2000-01-01",
            lieu_naissance="Douala",
            telephone="677777777",
            email="jean.dupont@iai.com",
            adresse="Douala, PK10",
            matricule="GL.CMR.D014.2425A",
            filiere=self.filiere,
            annee_academique=self.annee_etudiant,
            statut="INSCRIT",
            utilisateur=self.user_etudiant
        )
        
        self.client = Client()
        self.client.login(username='admin_test', password='password123')

    def test_bourse_creation_and_validation(self):
        """Tester la création et les contraintes du modèle Bourse"""
        # Créer une bourse d'excellence à 100%
        bourse = Bourse.objects.create(
            etudiant=self.etudiant,
            type_bourse="EXCELLENCE",
            montant=Decimal('440000.00'),
            annee_academique=self.annee,
            est_active=True
        )
        self.assertEqual(bourse.montant, Decimal('440000.00'))
        self.assertEqual(str(bourse), f"Bourse Bourse d'Excellence (100%) - Dupont Jean ({self.annee})")

    def test_bourse_form_validation(self):
        """Tester les règles de validation du formulaire BourseForm"""
        data = {
            'etudiant': self.etudiant.id,
            'type_bourse': 'EXCELLENCE',
            'montant': '440000.00',
            'annee_academique': self.annee.id,
            'date_attribution': timezone.now().date().isoformat(),
            'est_active': True,
            'commentaire': 'Bourse d\'excellence académique'
        }
        form = BourseForm(data=data)
        self.assertTrue(form.is_valid())

    def test_scholarship_views(self):
        """Tester le bon fonctionnement des vues de bourses"""
        # Test de la vue liste
        response = self.client.get(reverse('inscriptions:liste_bourses'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'inscriptions/bourses/liste.html')
        
        # Test de l'attribution
        data = {
            'etudiant': self.etudiant.id,
            'type_bourse': 'SOCIALE',
            'montant': '150000.00',
            'annee_academique': self.annee.id,
            'date_attribution': timezone.now().date().isoformat(),
            'est_active': True,
            'commentaire': 'Aide sociale'
        }
        response = self.client.post(reverse('inscriptions:attribuer_bourse'), data)
        self.assertEqual(response.status_code, 302)  # Redirection après création
        self.assertTrue(Bourse.objects.filter(type_bourse='SOCIALE').exists())
