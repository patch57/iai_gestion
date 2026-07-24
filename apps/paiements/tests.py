from django.test import TestCase, Client
from django.core.management import call_command
from django.core import mail
from datetime import date, timedelta
from apps.etudiants.models import Etudiant, Filiere, AnneeAcademique
from apps.paiements.models import TranchePaiement
from apps.paiements.services import calculer_penalites_etudiant
from apps.authentification.models import Utilisateur

class PenalitesServicesTestCase(TestCase):
    def setUp(self):
        # Création des objets de base
        self.user = Utilisateur.objects.create_user(
            username='testetudiant@iai.com',
            email='testetudiant@iai.com',
            password='testpassword123',
            type_utilisateur='ETUDIANT',
            matricule='GL.CMR.D014.2324A'
        )
        
        self.filiere = Filiere.objects.create(
            code='GL',
            nom='Génie Logiciel',
            duree_ans=2
        )
        
        self.annee = AnneeAcademique.objects.create(
            code='2024-2025',
            date_debut=date(2024, 9, 1),
            date_fin=date(2025, 8, 31),
            est_active=True
        )
        
        self.etudiant = Etudiant.objects.create(
            utilisateur=self.user,
            nom='Etudiant',
            prenom='Test',
            email='testetudiant@iai.com',
            telephone='699999999',
            adresse='Douala',
            date_naissance=date(2002, 5, 10),
            lieu_naissance='Douala',
            sexe='M',
            filiere=self.filiere,
            annee_academique=self.annee,
            matricule='GL.CMR.D014.2324A',
            recu_preinscription_valide=False
        )
        
        # Création d'une tranche de pré-inscription en retard (limite dépassée de 14 jours, soit 2 semaines)
        self.tranche1 = TranchePaiement.objects.create(
            numero=1,
            montant=84000,
            date_limite=date.today() - timedelta(days=14),
            annee_academique='2024-2025',
            est_actif=True
        )

        
    def test_calcul_penalites_retard(self):
        """Vérifie que la pénalité calculée correspond à 2 semaines de retard (2 * 1500 = 3000 FCFA)"""
        penalites = calculer_penalites_etudiant(self.etudiant)
        self.assertEqual(penalites['total'], 3000)
        self.assertEqual(len(penalites['details']), 1)
        self.assertEqual(penalites['details'][0]['semaines_retard'], 2)
        self.assertEqual(penalites['details'][0]['montant'], 3000)

    def test_envoyer_rappels_paiements_command(self):
        """Vérifie que la commande Django calcule bien les pénalités et envoie un courriel d'avertissement"""
        # Exécuter la commande
        call_command('envoyer_rappels_paiements')
        
        # Vérifier que le courriel est envoyé dans la boîte d'envoi factice
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        
        self.assertIn("Pré-inscription", email.body)


from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from apps.paiements.forms import valider_fichier_recu

class TeleverserRecuValidationTestCase(TestCase):
    def test_fichier_valide_pdf(self):
        file = SimpleUploadedFile("recu_scb.pdf", b"%PDF-1.4 test content", content_type="application/pdf")
        self.assertEqual(valider_fichier_recu(file), file)

    def test_fichier_valide_png(self):
        file = SimpleUploadedFile("recu_scb.png", b"\x89PNG\r\n\x1a\nfake png image content", content_type="image/png")
        self.assertEqual(valider_fichier_recu(file), file)

    def test_fichier_extension_interdite(self):
        file = SimpleUploadedFile("script.sh", b"echo hack", content_type="text/x-sh")
        with self.assertRaises(ValidationError) as ctx:
            valider_fichier_recu(file)
        self.assertIn("Format de fichier non supporté", str(ctx.exception))

    def test_fichier_trop_volumineux(self):
        # Fichier simulé de 6 Mo
        contenu_volumineux = b"0" * (6 * 1024 * 1024)
        file = SimpleUploadedFile("gros_recu.pdf", contenu_volumineux, content_type="application/pdf")
        with self.assertRaises(ValidationError) as ctx:
            valider_fichier_recu(file)
        self.assertIn("Fichier trop volumineux", str(ctx.exception))


from apps.paiements.models import SessionConcours, EcheanceSessionNiveau1
from django.urls import reverse

class SessionConcoursTestCase(TestCase):
    def setUp(self):
        self.comptable = Utilisateur.objects.create_user(
            username='SCC.CMR.D001.2024.A',
            email='rahinatoutapoya@gmail.com',
            password='Password123!',
            type_utilisateur='CHEF_COMPTABILITE'
        )

    def test_creer_session_concours_et_echeances(self):
        self.client.login(username='SCC.CMR.D001.2024.A', password='Password123!')
        response = self.client.post(reverse('paiements:creer_session_concours'), {
            'nom': 'Session de Juin 2026',
            'code': 'SESS_JUIN_2026',
            'date_concours': '2026-06-15',
            'annee_academique': '2024-2025',
            'description': 'Session de concours ordinaire',
            'date_limite_t1': '2026-07-01',
            'date_limite_t2': '2026-10-15',
            'date_limite_t3': '2027-01-15',
            'date_limite_t4': '2027-04-15',
        })
        self.assertEqual(response.status_code, 302)
        
        session = SessionConcours.objects.get(code='SESS_JUIN_2026')
        self.assertEqual(session.nom, 'Session de Juin 2026')
        self.assertEqual(session.echeances.count(), 4)
        
        ech1 = session.echeances.get(tranche_numero=1)
        self.assertEqual(ech1.montant, 84000)

        self.assertEqual(str(ech1.date_limite), '2026-07-01')


from apps.paiements.models import ResultatConcours

class ResultatConcoursTestCase(TestCase):
    def setUp(self):
        self.comptable = Utilisateur.objects.create_user(
            username='comptable_test',
            email='comptable@iai.com',
            password='Password123!',
            type_utilisateur='CHEF_COMPTABILITE'
        )
        self.session = SessionConcours.objects.create(
            nom="Session Test 2026",
            code="SESS_TEST_2026",
            date_concours=date(2026, 6, 1),
            annee_academique="2024-2025"
        )
        self.filiere_gl = Filiere.objects.create(code="GL", nom="Génie Logiciel", duree_ans=2)

    def test_importer_resultats_concours_csv(self):
        self.client.login(username='comptable_test', password='Password123!')
        
        csv_content = "NUMERO_TABLE;NOM;PRENOM;EMAIL;TELEPHONE;CODE_FILIERE;STATUT_ADMISSION\n" \
                      "N2026-101;EBOUA;Paul;paul@test.com;690000001;GL;ADMIS\n" \
                      "N2026-102;MBALLA;Claire;claire@test.com;690000002;GL;ADMIS\n"
                      
        fichier_csv = SimpleUploadedFile("admis.csv", csv_content.encode('utf-8'), content_type="text/csv")
        
        url = reverse('paiements:importer_resultats_concours', kwargs={'pk': self.session.pk})
        response = self.client.post(url, {'fichier_csv': fichier_csv})
        
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ResultatConcours.objects.filter(session_concours=self.session).count(), 2)
        
        res1 = ResultatConcours.objects.get(numero_table='N2026-101')
        self.assertEqual(res1.nom, 'EBOUA')
        self.assertEqual(res1.filiere, self.filiere_gl)
        self.assertEqual(res1.statut_preinscription, 'NON_PAYE')

    def test_marquer_preinscription_payee(self):
        self.client.login(username='comptable_test', password='Password123!')
        res = ResultatConcours.objects.create(
            session_concours=self.session,
            numero_table="N2026-200",
            nom="TCHINDA",
            prenom="Kevin",
            statut_preinscription='NON_PAYE'
        )
        url = reverse('paiements:marquer_preinscription_payee', kwargs={'pk': res.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        
        res.refresh_from_db()
        self.assertEqual(res.statut_preinscription, 'PAYE')

    def test_exporter_resultats_concours_pdf(self):
        self.client.login(username='comptable_test', password='Password123!')
        ResultatConcours.objects.create(
            session_concours=self.session,
            numero_table="N2026-300",
            nom="FOTSO",
            prenom="Alain"
        )
        url = reverse('paiements:exporter_resultats_concours_pdf', kwargs={'pk': self.session.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF-'))

    def test_importer_resultats_concours_douala_filtre(self):
        self.client.login(username='comptable_test', password='Password123!')
        content = "NUMERO_TABLE;NOM;PRENOM;EMAIL;TELEPHONE;CODE_FILIERE;STATUT_ADMISSION\n" \
                  "N2026-DLA-01;TCHINDA;Arnaud;arnaud@douala.cm;690000001;GL;ADMIS (DOUALA)\n" \
                  "N2026-YDE-01;NKOLO;Bertrand;bertrand@yaounde.cm;690000002;GL;ADMIS YAOUNDE\n" \
                  "N2026-DLA-02;KENGNE;Diane;diane@douala.cm;690000003;GL;ADMIS DLA\n"
                  
        fichier = SimpleUploadedFile("resultats.csv", content.encode('utf-8'), content_type="text/csv")
        url = reverse('paiements:importer_resultats_concours', kwargs={'pk': self.session.pk})
        response = self.client.post(url, {'fichier_csv': fichier})
        
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ResultatConcours.objects.filter(session_concours=self.session).count(), 2)

    def test_importer_pv_officiel_iai_douala(self):
        self.client.login(username='comptable_test', password='Password123!')
        pv_content = """
        I. Centre de formation de Yaoundé
        Filière Systèmes et Réseaux (Ordre alphabétique)
        ABOUEME GEORGES; AMASSOKA BARACK; AMOUGOU MENGUE JOSEPH;

        II. Centre de formation de Douala
        Filière Génie Logiciel (Ordre alphabétique)
        CHENDJOU FOKOU KAMGANG WILFRID ARTHUR; PARAISO ABUBAKR AS-SIDDIQ; PIERRETTE NOELLA FOTSA; TCHUISSEU PAMI JENNY ANAUELLE;
        Liste d'attente
        TCHATCHOU NYAMSI HERNANDEZ;

        Filière Systèmes et Réseaux (Ordre alphabétique)
        BIKAI EBEM JOSEPH ALAIN; DIKWA JEAN BERTRAND; FOFIE NGALEU MIKE BRAYAND; FOKAM DZOUAKOU STELLA MERVEILLE;

        III. Centre de formation de Garoua
        Filière Systèmes et Réseaux (Ordre alphabétique)
        BANBANE OUSSEINI; FADI YERIMA;
        """
        fichier = SimpleUploadedFile("pv_officiel.txt", pv_content.encode('utf-8'), content_type="text/plain")
        url = reverse('paiements:importer_resultats_concours', kwargs={'pk': self.session.pk})
        response = self.client.post(url, {'fichier_csv': fichier})
        
        self.assertEqual(response.status_code, 302)
        res_douala = ResultatConcours.objects.filter(session_concours=self.session)
        self.assertEqual(res_douala.count(), 9)
        self.assertTrue(res_douala.filter(nom="CHENDJOU").exists())
        self.assertTrue(res_douala.filter(nom="TCHATCHOU").exists())


class ProfilObligatoireTeleversementTestCase(TestCase):
    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            username='romuald@test.com',
            email='romuald@test.com',
            password='password123',
            type_utilisateur='ETUDIANT',
            matricule='GL.CMR.D014.2324A'
        )
        self.filiere = Filiere.objects.create(code='GL', nom='Génie Logiciel')
        self.annee = AnneeAcademique.objects.create(
            code='2024-2025',
            date_debut=date(2024, 9, 1),
            date_fin=date(2025, 8, 31),
            est_active=True
        )
        self.etudiant = Etudiant.objects.create(
            utilisateur=self.user,
            nom='Romuald',
            prenom='Romuald',
            email='romuald@test.com',
            telephone='682487912',
            adresse='Douala',
            date_naissance=date(2003, 1, 1),
            lieu_naissance='Douala',
            sexe='M',
            filiere=self.filiere,
            annee_academique=self.annee,
            matricule='GL.CMR.D014.2324A',
            # nom_tuteur et telephone_tuteur vides par défaut -> profil incomplet
        )
        self.client = Client()

    def test_televersement_bloque_si_profil_incomplet(self):
        """Un étudiant avec un profil incomplet doit être redirigé vers modifier_profil"""
        self.client.login(username='romuald@test.com', password='password123')
        
        # Tentative d'accès à la page de téléversement
        response = self.client.get(reverse('paiements:televerser_recu', args=[self.etudiant.id]))
        
        # On attend une redirection (302) vers modifier_profil
        self.assertEqual(response.status_code, 302)
        self.assertIn('profil/modifier/?compte_incomplet=1', response.url)

    def test_televersement_autorise_si_profil_complet(self):
        """Un étudiant avec un profil complet doit pouvoir accéder au téléversement"""
        self.etudiant.nom_tuteur = 'Tuteur Test'
        self.etudiant.telephone_tuteur = '699999999'
        self.etudiant.save()
        
        self.client.login(username='romuald@test.com', password='password123')
        response = self.client.get(reverse('paiements:televerser_recu', args=[self.etudiant.id]))
        
        # Doit afficher la page de téléversement (200 OK)
        self.assertEqual(response.status_code, 200)





