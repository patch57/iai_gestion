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


class SidebarRestrictionTestCase(TestCase):
    def setUp(self):
        # Créer les années académiques requises
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
        
        # Étudiant
        self.etudiant_user = Utilisateur.objects.create_user(
            username='romuald_etud',
            email='romuald.etud@test.com',
            password='password123',
            type_utilisateur='ETUDIANT',
            matricule='GL.CMR.D014.2425A'
        )
        
        from apps.etudiants.models import Etudiant, Filiere
        self.filiere = Filiere.objects.create(code='GL', nom='Génie Logiciel')
        self.etudiant = Etudiant.objects.create(
            utilisateur=self.etudiant_user,
            nom='Romuald',
            prenom='Romuald',
            email='romuald.etud@test.com',
            telephone='682487912',
            adresse='Douala',
            date_naissance=date(2003, 1, 1),
            lieu_naissance='Douala',
            sexe='M',
            filiere=self.filiere,
            annee_academique=self.annee_etud,
            matricule='GL.CMR.D014.2425A'
        )
        
        # Personnel
        self.scolarite_user = Utilisateur.objects.create_user(
            username='scol_chef_2',
            email='scol_chef2@test.com',
            password='password123',
            type_utilisateur='CHEF_SCOLARITE',
            matricule='CSE.CMR.D002.2026.A'
        )
        
        self.client = Client()

    def test_sidebar_restricted_for_student(self):
        """Un étudiant ne doit pas voir les liens d'administration dans sa sidebar"""
        self.client.login(username='romuald_etud', password='password123')
        response = self.client.get(reverse('tableau_bord:tableau_bord'))
        
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        # Les liens vers étudiants, professeurs, inscriptions doivent être absents
        self.assertNotIn('href="/etudiants/"', content)
        self.assertNotIn('href="/professeurs/"', content)
        self.assertNotIn('href="/inscriptions/"', content)

    def test_sidebar_visible_for_staff(self):
        """Le personnel doit voir les liens d'administration dans la sidebar"""
        self.client.login(username='scol_chef_2', password='password123')
        response = self.client.get(reverse('tableau_bord:tableau_bord'))
        
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        # Les liens doivent être présents pour le personnel
        self.assertIn('href="/etudiants/"', content)
        self.assertIn('href="/professeurs/"', content)
        self.assertIn('href="/inscriptions/"', content)

