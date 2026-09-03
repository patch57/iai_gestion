from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.etudiants.models import Filiere, Etudiant, Niveau
from apps.paiements.models import TranchePaiement, RecuPaiement


class PaiementsTestCase(TestCase):
    def setUp(self):
        self.filiere = Filiere.objects.create(nom="Génie Logiciel", code="GL")
        self.niveau = Niveau.objects.create(numero=2, filiere=self.filiere, code="GL-2")
        self.etudiant = Etudiant.objects.create(
            matricule="GL.CMR.D099.2324A",
            nom="TCHAMBA",
            prenom="ARNAUD",
            filiere=self.filiere,
            niveau=self.niveau,
            date_naissance=date(2002, 3, 3),
            lieu_naissance="Douala",
            sexe="M",
            telephone="+237690000099",
            email="arnaud@iai.cm",
            adresse="Douala"
        )
        self.tranche1 = TranchePaiement.objects.create(
            numero=1,
            montant=Decimal("71000"),
            date_limite=date(2026, 9, 30),
            annee_academique="2024-2025"
        )

    def test_tranche_creation(self):
        self.assertEqual(self.tranche1.numero, 1)
        self.assertEqual(self.tranche1.montant, Decimal("71000"))
        self.assertFalse(self.tranche1.est_depassee())

    def test_recu_paiement_creation(self):
        f = SimpleUploadedFile("test_recu.pdf", b"content", content_type="application/pdf")
        recu = RecuPaiement.objects.create(
            etudiant=self.etudiant,
            tranche=self.tranche1,
            recu_fichier=f,
            montant_mentionne=Decimal("71000"),
            reference_recu="REC-2026-TEST-001",
            statut="VALIDE"
        )
        self.assertEqual(recu.statut, "VALIDE")
        self.assertEqual(recu.reference_recu, "REC-2026-TEST-001")

    def test_api_prescan_recu(self):
        from apps.authentification.models import Utilisateur
        user = Utilisateur.objects.create_user(username="test_prescan", password="password123")
        self.client.login(username="test_prescan", password="password123")

        test_file = SimpleUploadedFile("recu_SCB-2026-999_115000FCFA.png", b"fake_image_content", content_type="image/png")
        response = self.client.post('/paiements/api/pre-scan-recu/', {'recu_fichier': test_file})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

