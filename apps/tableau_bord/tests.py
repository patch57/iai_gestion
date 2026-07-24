from django.test import TestCase, Client
from django.urls import reverse
from apps.authentification.models import Utilisateur
from apps.etudiants.models import AnneeAcademique as AA_etud
from apps.inscriptions.models import AnneeAcademique as AA_insc
from datetime import date

class ListeClassesPartageeTestCase(TestCase):
    def setUp(self):
        # Créer les années académiques dans les deux applications
        self.annee_insc = AA_insc.objects.create(
            code='2026-2027',
            date_debut=date(2026, 9, 1),
            date_fin=date(2027, 8, 31),
            est_actuelle=True
        )
        self.annee_etud = AA_etud.objects.create(
            code='2026-2027',
            date_debut=date(2026, 9, 1),
            date_fin=date(2027, 8, 31),
            est_active=True
        )
        
        # Création du personnel autorisé (ex. Chef Scolarité)
        self.scolarite_user = Utilisateur.objects.create_user(
            username='scol_chef',
            email='scol_chef@test.com',
            password='password123',
            type_utilisateur='CHEF_SCOLARITE',
            matricule='CSE.CMR.D001.2026.A'
        )
        self.client = Client()

    def test_liste_classes_partagee_succes(self):
        """Vérifie que la vue partagée des classes se charge sans erreur (ValueError résolue)"""
        self.client.login(username='scol_chef', password='password123')
        response = self.client.get(reverse('tableau_bord:liste_classes_partagee'))
        
        # Le code d'année académique actif doit être résolu correctement
        self.assertEqual(response.status_code, 200)
