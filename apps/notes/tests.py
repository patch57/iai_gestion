from django.test import TestCase
from datetime import date
from apps.authentification.models import Utilisateur
from apps.etudiants.models import Etudiant, Filiere, AnneeAcademique, Niveau
from apps.notes.models import TypeEvaluation, Matiere, Cours, Evaluation, Note, Bulletin

class NotesModelsTestCase(TestCase):
    def setUp(self):
        self.filiere = Filiere.objects.create(code='GL', nom='Génie Logiciel', duree_ans=3)
        self.niveau = Niveau.objects.create(filiere=self.filiere, numero=1, code='GL1')
        self.annee = AnneeAcademique.objects.create(
            code='2024-2025',
            date_debut=date(2024, 9, 1),
            date_fin=date(2025, 8, 31),
            est_active=True
        )
        self.user = Utilisateur.objects.create_user(
            username='studentnotes@iai.com',
            email='studentnotes@iai.com',
            password='password123',
            type_utilisateur='ETUDIANT',
            matricule='GL.CMR.D014.2425A'
        )
        self.etudiant = Etudiant.objects.create(
            utilisateur=self.user,
            nom='NomTest',
            prenom='PrenomTest',
            email='studentnotes@iai.com',
            telephone='670000000',
            adresse='Douala',
            date_naissance=date(2000, 1, 1),
            lieu_naissance='Douala',
            sexe='M',
            filiere=self.filiere,
            annee_academique=self.annee,
            matricule='GL.CMR.D014.2425A'
        )
        self.type_eval = TypeEvaluation.objects.create(
            code='CC',
            nom='Contrôle Continu',
            coefficient_default=1.00
        )
        self.matiere = Matiere.objects.create(
            code='INF101',
            nom='Algorithmique',
            credit=4,
            semestre=1
        )
        self.cours = Cours.objects.create(
            matiere=self.matiere,
            filiere=self.filiere,
            niveau=self.niveau,
            annee_academique='2024-2025',
            semestre=1
        )

    def test_creation_evaluation_et_note(self):
        evaluation = Evaluation.objects.create(
            cours=self.cours,
            type_evaluation=self.type_eval,
            titre='CC1 Algorithmique',
            date_evaluation=date.today(),
            coefficient=1.00,
            note_maximale=20.00
        )
        note = Note.objects.create(
            evaluation=evaluation,
            etudiant=self.etudiant,
            valeur=16.50
        )
        self.assertEqual(note.valeur, 16.50)
        self.assertEqual(note.evaluation.titre, 'CC1 Algorithmique')

    def test_creation_bulletin(self):
        bulletin = Bulletin.objects.create(
            etudiant=self.etudiant,
            annee_academique='2024-2025',
            semestre=1,
            moyenne_semestre=15.75,
            decision='ADMIS'
        )
        self.assertEqual(bulletin.moyenne_semestre, 15.75)
        self.assertEqual(bulletin.decision, 'ADMIS')
