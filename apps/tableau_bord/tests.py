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
        
        # Le lien statistiques doit être présent
        self.assertIn('href="/tableau-de-bord/statistiques/"', content)

    def test_sidebar_visible_for_staff(self):
        """Le personnel doit voir les liens d'administration dans la sidebar"""
        self.client.login(username='scol_chef_2', password='password123')
        response = self.client.get(reverse('tableau_bord:tableau_bord'))
        
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        # Les liens d'administration étudiants & professeurs doivent être présents
        self.assertIn('href="/etudiants/"', content)
        self.assertIn('href="/professeurs/"', content)
        # Inscriptions est masqué pour le Chef de la Scolarité selon la règle métier
        self.assertNotIn('href="/inscriptions/"', content)


class NoteInformationTestCase(TestCase):
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
        
        # Chef des études
        self.chef_etudes = Utilisateur.objects.create_user(
            username='chef_etudes_test',
            email='chef_etudes@test.com',
            password='password123',
            type_utilisateur='CHEF_ETUDES',
            matricule='CSE.CMR.D003.2026.A'
        )
        
        # Étudiant
        self.etudiant_user = Utilisateur.objects.create_user(
            username='romuald_etud_pv',
            email='romuald.etud.pv@test.com',
            password='password123',
            type_utilisateur='ETUDIANT',
            matricule='GL.CMR.D014.2425B'
        )
        
        from apps.etudiants.models import Etudiant, Filiere
        self.filiere = Filiere.objects.create(code='GL', nom='Génie Logiciel')
        self.etudiant = Etudiant.objects.create(
            utilisateur=self.etudiant_user,
            nom='Romuald',
            prenom='Romuald',
            email='romuald.etud.pv@test.com',
            telephone='682487912',
            adresse='Douala',
            date_naissance=date(2003, 1, 1),
            lieu_naissance='Douala',
            sexe='M',
            filiere=self.filiere,
            annee_academique=self.annee_etud,
            matricule='GL.CMR.D014.2425B'
        )
        self.client = Client()

    def test_note_information_lifecycle(self):
        # 1. Publier une note par le Chef des études
        self.client.login(username='chef_etudes_test', password='password123')
        
        from django.core.files.uploadedfile import SimpleUploadedFile
        pdf_file = SimpleUploadedFile("communique.pdf", b"test pdf content", content_type="application/pdf")
        
        response = self.client.post(
            reverse('tableau_bord:tableau_bord'),
            {
                'sujet': 'Report de la rentrée académique',
                'contenu': 'La rentrée est reportée au 15 Septembre.',
                'note_fichier': pdf_file
            }
        )
        self.assertEqual(response.status_code, 302)
        
        from apps.tableau_bord.models import NoteInformation
        self.assertTrue(NoteInformation.objects.filter(titre='Report de la rentrée académique').exists())
        note = NoteInformation.objects.get(titre='Report de la rentrée académique')
        self.assertTrue(note.est_active)
        self.assertIsNotNone(note.fichier_pdf)
        
        # 2. Vérifier que l'étudiant voit la note sur son dashboard
        self.client.login(username='romuald_etud_pv', password='password123')
        response = self.client.get(reverse('tableau_bord:tableau_bord'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Report de la rentrée académique')
        self.assertContains(response, 'La rentrée est reportée au 15 Septembre.')
        
        # 3. Supprimer la note en tant que Chef des Études
        self.client.login(username='chef_etudes_test', password='password123')
        response = self.client.post(
            reverse('tableau_bord:supprimer_note_info', kwargs={'pk': note.pk})
        )
        self.assertEqual(response.status_code, 302)
        
        note.refresh_from_db()
        self.assertFalse(note.est_active)


class ExportPDFPaiementsClasseTestCase(TestCase):
    def setUp(self):
        # Créer les années académiques
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
        
        # Créer une salle
        from apps.cours.models import Salle
        self.salle = Salle.objects.create(code='GL1A', nom='Génie Logiciel 1A', capacite=30)
        
        # Création des utilisateurs
        self.compta_user = Utilisateur.objects.create_user(
            username='compta_chef',
            email='compta@test.com',
            password='password123',
            type_utilisateur='CHEF_COMPTABILITE',
            matricule='CSE.CMR.D004.2026.A'
        )
        
        self.etudiant_user = Utilisateur.objects.create_user(
            username='etud_test_pdf',
            email='etud_pdf@test.com',
            password='password123',
            type_utilisateur='ETUDIANT',
            matricule='GL.CMR.D014.2425C'
        )
        
        self.client = Client()

    def test_export_pdf_success_as_compta(self):
        """Le Chef de la Comptabilité doit pouvoir télécharger l'état de paiement en PDF"""
        self.client.login(username='compta_chef', password='password123')
        url = reverse('tableau_bord:export_pdf_paiements_classe', kwargs={'salle_id': self.salle.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF-'))

    def test_export_pdf_forbidden_as_student(self):
        """Un étudiant ne doit pas avoir accès au téléchargement du PDF de la classe"""
        self.client.login(username='etud_test_pdf', password='password123')
        url = reverse('tableau_bord:export_pdf_paiements_classe', kwargs={'salle_id': self.salle.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 302)


class EmploiDuTempsOverwritingTestCase(TestCase):
    def setUp(self):
        # Années académiques
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
        
        # Chef des études
        self.chef_etudes = Utilisateur.objects.create_user(
            username='chef_etudes_test_edt',
            email='chef_etudes_edt@test.com',
            password='password123',
            type_utilisateur='CHEF_ETUDES',
            matricule='CSE.CMR.D005.2026.A'
        )
        
        from apps.etudiants.models import Filiere, Niveau
        from apps.cours.models import Salle
        self.filiere = Filiere.objects.create(code='GL', nom='Génie Logiciel')
        self.niveau = Niveau.objects.create(numero=1, filiere=self.filiere)
        self.salle = Salle.objects.create(code='GL1A', nom='Salle GL1A', capacite=30)
        
        self.client = Client()

    def test_overwrite_schedule(self):
        """Vérifie qu'un nouvel emploi du temps écrase l'ancien pour la même combinaison filière/niveau/salle"""
        self.client.login(username='chef_etudes_test_edt', password='password123')
        
        from django.core.files.uploadedfile import SimpleUploadedFile
        pdf_file_1 = SimpleUploadedFile("edt1.pdf", b"test pdf content 1", content_type="application/pdf")
        pdf_file_2 = SimpleUploadedFile("edt2.pdf", b"test pdf content 2", content_type="application/pdf")
        
        # Publier le premier
        response = self.client.post(
            reverse('tableau_bord:tableau_bord'),
            {
                'filiere_id': self.filiere.id,
                'niveau_id': self.niveau.id,
                'salle_id': self.salle.id,
                'emploi_fichier': pdf_file_1
            }
        )
        self.assertEqual(response.status_code, 302)
        
        from apps.cours.models import EmploiDuTemps
        self.assertEqual(EmploiDuTemps.objects.filter(filiere=self.filiere, niveau=self.niveau, salle=self.salle).count(), 1)
        
        # Publier le second pour les mêmes critères
        response = self.client.post(
            reverse('tableau_bord:tableau_bord'),
            {
                'filiere_id': self.filiere.id,
                'niveau_id': self.niveau.id,
                'salle_id': self.salle.id,
                'emploi_fichier': pdf_file_2
            }
        )
        self.assertEqual(response.status_code, 302)
        
        # Il doit toujours y avoir un seul emploi du temps
        self.assertEqual(EmploiDuTemps.objects.filter(filiere=self.filiere, niveau=self.niveau, salle=self.salle).count(), 1)


class TransitionAnneeTestCase(TestCase):
    def setUp(self):
        # 1. Années académiques initiales actives
        self.annee_insc = AA_insc.objects.create(
            code='2025-2026',
            date_debut=date(2025, 10, 1),
            date_fin=date(2026, 9, 30),
            est_actuelle=True
        )
        self.annee_etud = AA_etud.objects.create(
            code='2025-2026',
            date_debut=date(2025, 10, 1),
            date_fin=date(2026, 9, 30),
            est_active=True
        )
        
        # Admin système
        self.admin_user = Utilisateur.objects.create_user(
            username='admin_transition_test',
            email='admin_t@test.com',
            password='password123',
            type_utilisateur='ADMIN_SYSTEME',
            matricule='CSE.CMR.D006.2026.A'
        )
        
        # Filières et Niveaux
        from apps.etudiants.models import Filiere, Niveau, Etudiant, Classe
        self.filiere = Filiere.objects.create(code='GL', nom='Génie Logiciel')
        self.niveau1 = Niveau.objects.create(numero=1, filiere=self.filiere)
        self.niveau2 = Niveau.objects.create(numero=2, filiere=self.filiere)
        
        # Classes
        self.classe_gl2 = Classe.objects.create(
            nom='GL 2A',
            filiere=self.filiere,
            niveau=self.niveau2,
            annee_academique=self.annee_etud,
            effectif_max=30,
            est_active=True
        )
        
        # Étudiants
        self.etudiant_n1_user = Utilisateur.objects.create_user(
            username='etud_n1',
            email='etud_n1@test.com',
            password='password123',
            type_utilisateur='ETUDIANT',
            matricule='GL.CMR.D040.2526A'
        )
        self.etudiant_n1 = Etudiant.objects.create(
            utilisateur=self.etudiant_n1_user,
            nom='Niveau1',
            prenom='GL',
            email='etud_n1@test.com',
            telephone='682487910',
            adresse='Douala',
            date_naissance=date(2005, 1, 1),
            lieu_naissance='Douala',
            sexe='M',
            filiere=self.filiere,
            niveau=self.niveau1,
            annee_academique=self.annee_etud,
            statut='ACTIF',
            matricule='GL.CMR.D040.2526A'
        )
        
        self.etudiant_n2_user = Utilisateur.objects.create_user(
            username='etud_n2',
            email='etud_n2@test.com',
            password='password123',
            type_utilisateur='ETUDIANT',
            matricule='GL.CMR.D041.2526A'
        )
        self.etudiant_n2 = Etudiant.objects.create(
            utilisateur=self.etudiant_n2_user,
            nom='Niveau2',
            prenom='GL',
            email='etud_n2@test.com',
            telephone='682487911',
            adresse='Douala',
            date_naissance=date(2004, 1, 1),
            lieu_naissance='Douala',
            sexe='F',
            filiere=self.filiere,
            niveau=self.niveau2,
            classe=self.classe_gl2,
            annee_academique=self.annee_etud,
            statut='ACTIF',
            matricule='GL.CMR.D041.2526A'
        )
        
        self.client = Client()

    def test_transition_annee_management_command(self):
        """Vérifie le bon fonctionnement de la commande d'administration transition_annee"""
        from django.core.management import call_command
        from io import StringIO
        
        out = StringIO()
        call_command('transition_annee', stdout=out)
        
        # Vérifier les sorties de la commande
        self.assertIn("Transition de l'année universitaire effectuée avec succès !", out.getvalue())
        
        # Vérifier que les anciennes années sont inactives
        self.annee_etud.refresh_from_db()
        self.annee_insc.refresh_from_db()
        self.assertFalse(self.annee_etud.est_active)
        self.assertFalse(self.annee_insc.est_actuelle)
        
        # Vérifier que la nouvelle année 2026-2027 est créée et active
        new_etud = AA_etud.objects.get(code='2026-2027')
        new_insc = AA_insc.objects.get(code='2026-2027')
        self.assertTrue(new_etud.est_active)
        self.assertTrue(new_insc.est_actuelle)
        self.assertTrue(new_insc.est_ouverte_inscription)
        
        # Vérifier que l'étudiant de niveau 2 est passé à DIPLOME
        self.etudiant_n2.refresh_from_db()
        self.assertEqual(self.etudiant_n2.statut, 'DIPLOME')
        
        # Vérifier que l'étudiant de niveau 1 est resté ACTIF (sera réinscrit plus tard)
        self.etudiant_n1.refresh_from_db()
        self.assertEqual(self.etudiant_n1.statut, 'ACTIF')
        
        # Vérifier que la classe GL 2A de l'année précédente est inactive
        self.classe_gl2.refresh_from_db()
        self.assertFalse(self.classe_gl2.est_active)

    def test_transition_annee_view_access(self):
        """Vérifie l'accès sécurisé à la vue de transition par l'administrateur système"""
        self.client.login(username='admin_transition_test', password='password123')
        url = reverse('tableau_bord:lancer_transition_annee')
        
        # POST de transition
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302) # Redirection vers le dashboard
        
        # Vérifier que la nouvelle année 2026-2027 est créée et active suite à l'appel POST
        self.assertTrue(AA_etud.objects.filter(code='2026-2027', est_active=True).exists())


class NotificationServiceTestCase(TestCase):
    def setUp(self):
        self.directeur = Utilisateur.objects.create_user(
            username='dir_test',
            email='dir@test.com',
            password='password123',
            type_utilisateur='DIRECTEUR'
        )
        self.scolarite = Utilisateur.objects.create_user(
            username='scol_test',
            email='scol@test.com',
            password='password123',
            type_utilisateur='CHEF_SCOLARITE'
        )
        self.etudiant_user = Utilisateur.objects.create_user(
            username='etud_test',
            email='etud@test.com',
            password='password123',
            type_utilisateur='ETUDIANT'
        )
        self.client = Client()

    def test_notification_service_role_dispatch(self):
        """Vérifie que NotificationService envoie bien la notification aux bons rôles"""
        from apps.tableau_bord.services_notification import NotificationService
        from apps.tableau_bord.models import Notification

        # Envoyer notification au Directeur
        NotificationService.notifier_directeur("Alerte Direction", "Message pour la direction", type_notif='WARNING')
        
        # Envoyer notification à la Scolarité
        NotificationService.notifier_chef_scolarite("Alerte Scolarité", "Nouveau dossier étudiant", type_notif='INFO')

        self.assertEqual(Notification.objects.filter(utilisateur=self.directeur).count(), 1)
        self.assertEqual(Notification.objects.filter(utilisateur=self.scolarite).count(), 1)
        self.assertEqual(Notification.objects.filter(utilisateur=self.etudiant_user).count(), 0)

    def test_api_notifications_non_lues(self):
        """Vérifie l'API AJAX retournant les notifications non lues"""
        from apps.tableau_bord.services_notification import NotificationService
        NotificationService.notifier_utilisateur(self.etudiant_user, "Test Titre", "Message test", type_notif='SUCCESS')

        self.client.login(username='etud_test', password='password123')
        response = self.client.get(reverse('tableau_bord:api_notifications_non_lues'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['notifications'][0]['titre'], "Test Titre")




