import csv
import io
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core import mail
from django.utils import timezone
from apps.requetes.models import Requete

User = get_user_model()


class RequetesTestCase(TestCase):
    def setUp(self):
        # 1. Création des utilisateurs avec différents rôles
        self.etudiant_user = User.objects.create_user(
            username='etudiant_test',
            email='etudiant@test.com',
            password='password123',
            type_utilisateur='ETUDIANT',
            matricule='GL.CMR.D014.2324A'
        )
        self.scolarite_user = User.objects.create_user(
            username='scolarite_test',
            email='scolarite@test.com',
            password='password123',
            type_utilisateur='CHEF_SCOLARITE',
            matricule='CSC.CMR.D001.2024.A'
        )
        self.directeur_user = User.objects.create_user(
            username='dir_test',
            email='directeur@test.com',
            password='password123',
            type_utilisateur='ADMIN_SYSTEME',
            matricule='DIR.CMR.D002.2024.B'
        )
        
        self.client = Client()

    def test_cycle_de_vie_requete(self):
        """Test complet du cycle de vie d'une requête (Soumission -> Escalade -> Renvoi -> Clôture)"""
        # --- A. Soumission par l'étudiant ---
        self.client.login(username='etudiant_test', password='password123')
        data_creation = {
            'titre': 'Problème de carte scolaire',
            'nature': 'SCOLARITE',
            'description': 'Ma carte comporte une erreur sur mon prénom.'
        }
        response = self.client.post(reverse('requetes:creer_requete'), data_creation)
        self.assertEqual(response.status_code, 302)  # Redirection après succès
        
        requete = Requete.objects.first()
        self.assertIsNotNone(requete)
        self.assertEqual(requete.statut, 'SOUMIS')
        self.assertEqual(requete.auteur, self.etudiant_user)
        self.assertEqual(requete.historique[0]['action'], 'Soumission')
        self.client.logout()

        # --- B. Escalade par le Chef de Service Scolarité au Directeur ---
        self.client.login(username='scolarite_test', password='password123')
        data_escalade = {
            'commentaire_interne': 'Dépasse mes compétences de validation.'
        }
        response = self.client.post(reverse('requetes:escalader_requete', args=[requete.id]), data_escalade)
        self.assertEqual(response.status_code, 302)
        
        requete.refresh_from_db()
        self.assertEqual(requete.statut, 'ESCALADE')
        self.assertEqual(requete.reponse_interne, 'Dépasse mes compétences de validation.')
        self.client.logout()

        # --- C. Renvoi par le Directeur au personnel ---
        self.client.login(username='dir_test', password='password123')
        data_renvoi = {
            'assigne_a': self.scolarite_user.id,
            'reponse_interne': 'Faire le changement de carte suite à la modification du profil.'
        }
        response = self.client.post(reverse('requetes:renvoyer_requete', args=[requete.id]), data_renvoi)
        self.assertEqual(response.status_code, 302)
        
        requete.refresh_from_db()
        self.assertEqual(requete.statut, 'RENVOYE')
        self.assertEqual(requete.assigne_a, self.scolarite_user)
        self.client.logout()

        # --- D. Réponse finale et clôture par le personnel & Notification Email ---
        self.client.login(username='scolarite_test', password='password123')
        data_reponse = {
            'reponse': 'Votre nouvelle carte a été réimprimée et est disponible à la scolarité.'
        }
        response = self.client.post(reverse('requetes:repondre_requete', args=[requete.id]), data_reponse)
        self.assertEqual(response.status_code, 302)
        
        requete.refresh_from_db()
        self.assertEqual(requete.statut, 'TRAITE')
        self.assertEqual(requete.reponse, 'Votre nouvelle carte a été réimprimée et est disponible à la scolarité.')
        
        # Vérification de l'envoi d'e-mail de notification
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ['etudiant@test.com'])
        self.assertIn(f"Réponse à votre requête #{requete.id}", email.subject)
        self.assertIn("nouvelle carte a été réimprimée", email.body)
        self.client.logout()

    def test_export_import_csv(self):
        """Vérifie l'exportation et l'importation de requêtes par le Directeur"""
        # Créer une requête préalable
        requete = Requete.objects.create(
            auteur=self.etudiant_user,
            titre='Erreur scolarité',
            nature='SCOLARITE',
            description='Test de description',
            statut='SOUMIS'
        )
        
        self.client.login(username='dir_test', password='password123')
        
        # Test Export
        response = self.client.get(reverse('requetes:export_requetes_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        
        # Test Import
        csv_content = f"ID,Auteur (Email),Titre,Nature,Description,Statut,Date Création,Réponse\n{requete.id},etudiant@test.com,Erreur scolarité,SCOLARITE,Test de description,TRAITE,2026-07-13T00:00:00,Corrigé par l'administrateur après traitement."
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = 'import.csv'
        
        response = self.client.post(reverse('requetes:import_requetes_csv'), {'csv_file': csv_file})
        self.assertEqual(response.status_code, 302)
        
        requete.refresh_from_db()
        self.assertEqual(requete.statut, 'TRAITE')
        self.assertEqual(requete.reponse, "Corrigé par l'administrateur après traitement.")

    def test_securite_acces_personnel_requetes(self):
        """Vérifie le filtrage strict et les accès interdits pour le personnel"""
        # Création de deux requêtes de nature différente
        req_scolarite = Requete.objects.create(
            auteur=self.etudiant_user,
            titre='Requete Scolarité',
            nature='SCOLARITE',
            description='Test Scolarité',
            statut='SOUMIS'
        )
        req_compta = Requete.objects.create(
            auteur=self.etudiant_user,
            titre='Requete Comptabilité',
            nature='COMPTABILITE',
            description='Test Comptabilité',
            statut='SOUMIS'
        )
        
        # Utilisateur Comptabilité
        compta_user = User.objects.create_user(
            username='compta_test',
            email='compta@test.com',
            password='password123',
            type_utilisateur='CHEF_COMPTABILITE',
            matricule='CCO.CMR.D003.2024.A'
        )
        
        # 1. Le Chef Scolarité ne doit voir que la requête Scolarité
        self.client.login(username='scolarite_test', password='password123')
        response = self.client.get(reverse('requetes:liste_requetes'))
        self.assertEqual(response.status_code, 200)
        requetes_liste = list(response.context['requetes'].object_list)
        self.assertIn(req_scolarite, requetes_liste)
        self.assertNotIn(req_compta, requetes_liste)
        
        # 2. Le Chef Scolarité ne doit pas pouvoir accéder au détail de la requête de Comptabilité
        response = self.client.get(reverse('requetes:detail_requete', args=[req_compta.id]))
        self.assertEqual(response.status_code, 302)  # Redirection avec message d'erreur
        
        # 3. Si la requête de Scolarité est assignée au Chef Comptabilité par le Directeur, le Chef Scolarité ne doit plus la voir
        req_scolarite.assigne_a = compta_user
        req_scolarite.save()
        
        response = self.client.get(reverse('requetes:liste_requetes'))
        requetes_liste = list(response.context['requetes'].object_list)
        self.assertNotIn(req_scolarite, requetes_liste)
        
        # Et s'il tente d'y accéder en direct, l'accès lui est refusé
        response = self.client.get(reverse('requetes:detail_requete', args=[req_scolarite.id]))
        self.assertEqual(response.status_code, 302)
        
        # 4. Le Chef Comptabilité doit par contre voir cette requête Scolarité qui lui est affectée
        self.client.logout()
        self.client.login(username='compta_test', password='password123')
        response = self.client.get(reverse('requetes:liste_requetes'))
        requetes_liste = list(response.context['requetes'].object_list)
        self.assertIn(req_scolarite, requetes_liste)
        
        # Et il doit pouvoir accéder au détail
        response = self.client.get(reverse('requetes:detail_requete', args=[req_scolarite.id]))
        self.assertEqual(response.status_code, 200)
        self.client.logout()

