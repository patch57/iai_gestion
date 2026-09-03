import os
from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.etudiants.models import Filiere, Etudiant, Niveau
from apps.cours.models import Matiere
from apps.notes.models import TypeEvaluation, FicheNotesAnonymat, LigneFicheNotesAnonymat
from apps.notes.services import normaliser_nom, match_etudiant_par_nom, analyser_fiche_anonymat_image

User = get_user_model()


class AnonymatOCRTestCase(TestCase):
    def setUp(self):
        self.filiere = Filiere.objects.create(nom="Génie Logiciel", code="GL")
        self.niveau = Niveau.objects.create(numero=1, filiere=self.filiere, code="GL-1")
        self.etudiant1 = Etudiant.objects.create(
            matricule="GL.CMR.D001.2324A",
            nom="PATCHONG NJITACK",
            prenom="ROMUALD",
            filiere=self.filiere,
            niveau=self.niveau,
            date_naissance=date(2002, 1, 1),
            lieu_naissance="Douala",
            sexe="M",
            telephone="+237690000001",
            email="romuald@iai.cm",
            adresse="Douala"
        )
        self.etudiant2 = Etudiant.objects.create(
            matricule="GL.CMR.D002.2324A",
            nom="NZE TOUOWO",
            prenom="WILFRIED",
            filiere=self.filiere,
            niveau=self.niveau,
            date_naissance=date(2002, 2, 2),
            lieu_naissance="Douala",
            sexe="M",
            telephone="+237690000002",
            email="wilfried@iai.cm",
            adresse="Douala"
        )

    def test_normaliser_nom(self):
        self.assertEqual(normaliser_nom("Éléphant-Bleu"), "elephant bleu")
        self.assertEqual(normaliser_nom("NZE  TOUOWO Wilfried"), "nze touowo wilfried")

    def test_match_etudiant_par_nom(self):
        etudiants = [self.etudiant1, self.etudiant2]
        match = match_etudiant_par_nom("PATCHONG ROMUALD", etudiants)
        self.assertEqual(match, self.etudiant1)

        match_inv = match_etudiant_par_nom("WILFRIED NZE TOUOWO", etudiants)
        self.assertEqual(match_inv, self.etudiant2)

    def test_analyser_fiche_anonymat_fallback(self):
        etudiants = [self.etudiant1, self.etudiant2]
        resultats = analyser_fiche_anonymat_image(None, etudiants_classe=etudiants)
        self.assertTrue(len(resultats) > 0)
        self.assertEqual(resultats[0]['numero_anonymat'], 'A1')
        self.assertIsNotNone(resultats[0]['etudiant'])
        self.assertIn(resultats[0]['etudiant'], etudiants)
