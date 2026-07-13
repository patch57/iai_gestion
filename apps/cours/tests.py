from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.etudiants.models import Apprenant, Formation
from apps.notes.models import NoteApprenant
from apps.cours.models import SupportPedagogiqueApprenant

User = get_user_model()


class ApprenantsPedagogieTestCase(TestCase):
    def setUp(self):
        # 1. Création des utilisateurs
        self.formateur = User.objects.create_user(
            username='formateur_test',
            email='formateur@test.com',
            password='password123',
            type_utilisateur='ENSEIGNANT',
            matricule='ENS.CMR.D101.2024.A'
        )
        self.apprenant_user = User.objects.create_user(
            username='apprenant_test',
            email='apprenant@test.com',
            password='password123',
            type_utilisateur='APPRENANT',
            matricule='APP.CMR.D102.2024.B'
        )
        
        # 2. Création du profil Apprenant
        self.apprenant = Apprenant.objects.create(
            utilisateur=self.apprenant_user,
            nom_complet='Apprenant de Test',
            email='apprenant@test.com',
            contact='677777777',
            lieu_residence='Douala'
        )
        
        # 3. Création d'une formation
        self.formation = Formation.objects.create(
            type_formation='CERTIFICATION',
            nom='SECRETARIAT',
            tarif=150000,
            est_active=True
        )
        self.apprenant.formations.add(self.formation)
        
        self.client = Client()

    def test_supports_pedagogiques_cibles(self):
        """Vérifie le dépôt et l'affichage ciblé des supports de cours"""
        self.client.login(username='formateur_test', password='password123')
        
        # Déposer un support ciblé pour formation continue / secretariat
        support = SupportPedagogiqueApprenant.objects.create(
            formateur=self.formateur,
            titre='TP de secrétariat bureautique',
            type_document='TP',
            type_formation='CERTIFICATION',
            module_formation='SECRETARIAT',
            fichier='cours/apprenants/test_tp.pdf'
        )
        
        self.assertIsNotNone(support)
        self.assertEqual(support.get_nom_fichier(), 'test_tp.pdf')
        
        # Accéder à la liste en tant que formateur
        response = self.client.get(reverse('cours:liste_supports_apprenant'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(support, response.context['supports'])
        
        self.client.logout()
        
        # Accéder en tant qu'apprenant pour vérifier qu'il le voit car ciblé pour lui
        self.client.login(username='apprenant_test', password='password123')
        response = self.client.get(reverse('cours:liste_supports_apprenant'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(support, response.context['supports'])
        self.client.logout()

    def test_registre_apprenants_print(self):
        """Vérifie l'accès au registre des apprenants par les formateurs"""
        self.client.login(username='formateur_test', password='password123')
        response = self.client.get(reverse('cours:liste_apprenants_categories'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.apprenant, response.context['apprenants'])
        self.client.logout()

    def test_saisie_notes_apprenant(self):
        """Vérifie la saisie et l'enregistrement de notes d'évaluation en lot"""
        self.client.login(username='formateur_test', password='password123')
        
        # Charger la page de saisie pour la formation
        response = self.client.get(reverse('cours:saisir_notes_apprenants'), {'formation_id': self.formation.id})
        self.assertEqual(response.status_code, 200)
        
        # Enregistrer une note de 18.5/20 pour notre apprenant
        data = {
            f'note_{self.apprenant.id}': '18.5',
            f'commentaire_{self.apprenant.id}': 'Excellent apprenant'
        }
        response = self.client.post(f"{reverse('cours:saisir_notes_apprenants')}?formation_id={self.formation.id}", data)
        self.assertEqual(response.status_code, 302) # Redirection après succès
        
        # Vérifier en BD
        note_obj = NoteApprenant.objects.filter(apprenant=self.apprenant, formation=self.formation).first()
        self.assertIsNotNone(note_obj)
        self.assertEqual(note_obj.note, 18.5)
        self.assertEqual(note_obj.commentaire, 'Excellent apprenant')
        self.assertEqual(note_obj.formateur, self.formateur)
        self.client.logout()
