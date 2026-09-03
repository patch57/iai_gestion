"""
Tests unitaires pour la vérification d'authenticité par QR Code (apps/etudiants).
"""
import uuid
from datetime import date
from django.test import TestCase, Client
from django.urls import reverse
from apps.etudiants.models import Etudiant, Filiere, AnneeAcademique, Niveau
from apps.etudiants.views_verification import generer_qr_code_base64


class VerificationQRCodeTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.annee = AnneeAcademique.objects.create(
            code="2025-2026",
            date_debut=date(2025, 9, 1),
            date_fin=date(2026, 6, 30),
            est_active=True
        )
        self.filiere = Filiere.objects.create(code="GL", nom="Génie Logiciel")
        self.niveau = Niveau.objects.create(numero=1, filiere=self.filiere, code="GL-N1")
        self.etudiant = Etudiant.objects.create(
            matricule="GL.CMR.D014.2526A",
            nom="TCHAMOU",
            prenom="Cédric",
            date_naissance=date(2002, 5, 14),
            lieu_naissance="Douala",
            sexe="M",
            nationalite="CMR",
            telephone="+237699887766",
            email="cedric.tchamou@iai.cm",
            adresse="Douala PK10",
            filiere=self.filiere,
            niveau=self.niveau,
            annee_academique=self.annee,
            statut="INSCRIT",
            est_actif=True,
            verification_token=uuid.uuid4()
        )

    def test_generer_qr_code_base64(self):
        url = "https://iai.cm/etudiants/verifier/test-token"
        qr_b64 = generer_qr_code_base64(url)
        self.assertTrue(qr_b64.startswith("data:image/png;base64,"))

    def test_verifier_etudiant_public_view_valide(self):
        url = reverse('etudiants:verifier_etudiant_public', kwargs={'token': self.etudiant.verification_token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DOCUMENT OFFICIEL VALIDE")
        self.assertContains(response, "TCHAMOU")
        self.assertContains(response, "GL.CMR.D014.2526A")

    def test_verifier_etudiant_public_view_invalide(self):
        token_inconnu = uuid.uuid4()
        url = reverse('etudiants:verifier_etudiant_public', kwargs={'token': token_inconnu})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
