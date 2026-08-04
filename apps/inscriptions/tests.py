from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

from apps.etudiants.models import Etudiant, Filiere, AnneeAcademique as AnneeAcademiqueEtudiant
from apps.inscriptions.models import AnneeAcademique, Bourse, Inscription
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

    def test_securite_idor_inscription(self):
        """Vérifie qu'un étudiant ne peut pas consulter l'inscription d'un autre étudiant"""
        # Création d'un second étudiant et de son inscription
        user_etudiant_2 = User.objects.create_user(
            username='autre_etudiant',
            email='autre.etudiant@iai.com',
            password='password123',
            type_utilisateur='ETUDIANT',
            matricule="GL.CMR.D015.2425A"
        )
        etudiant_2 = Etudiant.objects.create(
            nom="Martin",
            prenom="Paul",
            sexe="M",
            date_naissance="2001-02-02",
            lieu_naissance="Yaoundé",
            telephone="678888888",
            email="autre.etudiant@iai.com",
            adresse="Yaoundé, Ngoa",
            matricule="GL.CMR.D015.2425A",
            filiere=self.filiere,
            annee_academique=self.annee_etudiant,
            statut="INSCRIT",
            utilisateur=user_etudiant_2
        )
        inscription_2 = Inscription.objects.create(
            etudiant=etudiant_2,
            annee_academique=self.annee,
            filiere=self.filiere,
            statut='VALIDEE'
        )
        
        # Connexion en tant que premier étudiant (jean_dupont)
        self.client.login(username='jean_dupont', password='password123')
        
        # Tenter d'accéder au détail de l'inscription du deuxième étudiant
        response = self.client.get(reverse('inscriptions:detail_inscription', args=[inscription_2.id]))
        
        # L'accès doit être interdit (code HTTP 403)
        self.assertEqual(response.status_code, 403)

