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


from decimal import Decimal
from apps.notes.services import normaliser_nom, match_etudiant_par_nom, analyser_fiche_anonymat_image
from apps.notes.models import FicheNotesAnonymat, LigneFicheNotesAnonymat
from apps.cours.models import Matiere as CoursMatiere, Salle


class FicheAnonymatTestCase(TestCase):
    """Tests pour la fonctionnalité des fiches de notes d'anonymat"""

    def setUp(self):
        self.filiere = Filiere.objects.create(code='GL', nom='Génie Logiciel', duree_ans=3)
        self.niveau = Niveau.objects.create(filiere=self.filiere, numero=1, code='GL1-test')
        self.annee = AnneeAcademique.objects.create(
            code='2025-2026',
            date_debut=date(2025, 9, 1),
            date_fin=date(2026, 8, 31),
            est_active=True
        )
        # Créer des étudiants pour le matching
        self.etud1 = Etudiant.objects.create(
            matricule='GL.CMR.D014.2526A',
            nom='PATCHONG NJITACK', prenom='ROMUALD',
            email='patchong@test.com', telephone='670000001',
            adresse='Douala', date_naissance=date(2000, 1, 1),
            lieu_naissance='Douala', sexe='M',
            filiere=self.filiere, annee_academique=self.annee
        )
        self.etud2 = Etudiant.objects.create(
            matricule='GL.CMR.D014.2526B',
            nom='NZE TOUOWO', prenom='WILFRIED',
            email='nze@test.com', telephone='670000002',
            adresse='Douala', date_naissance=date(2000, 2, 1),
            lieu_naissance='Douala', sexe='M',
            filiere=self.filiere, annee_academique=self.annee
        )
        self.etud3 = Etudiant.objects.create(
            matricule='GL.CMR.D014.2526C',
            nom='MBALLA', prenom='MICHELLE CLARA',
            email='mballa@test.com', telephone='670000003',
            adresse='Douala', date_naissance=date(2001, 3, 1),
            lieu_naissance='Douala', sexe='F',
            filiere=self.filiere, annee_academique=self.annee
        )
        self.etudiants = [self.etud1, self.etud2, self.etud3]
        self.type_eval = TypeEvaluation.objects.create(
            code='EXAM', nom='Examen', coefficient_default=1.00
        )
        self.matiere = CoursMatiere.objects.create(code='IA', nom='Intelligence Artificielle')
        self.salle = Salle.objects.create(code='GL3D', nom='GL3D', capacite=30)

    def test_normaliser_nom(self):
        self.assertEqual(normaliser_nom('PATCHONG NJITACK ROMUALD'), 'patchong njitack romuald')
        self.assertEqual(normaliser_nom('Éric-André'), 'eric andre')
        self.assertEqual(normaliser_nom(''), '')

    def test_matching_etudiant_exact(self):
        result = match_etudiant_par_nom('PATCHONG NJITACK ROMUALD', self.etudiants)
        self.assertEqual(result, self.etud1)

    def test_matching_etudiant_inversions(self):
        result = match_etudiant_par_nom('ROMUALD PATCHONG NJITACK', self.etudiants)
        self.assertEqual(result, self.etud1)

    def test_matching_etudiant_partiel(self):
        result = match_etudiant_par_nom('MBALLA MICHELLE CLARA', self.etudiants)
        self.assertEqual(result, self.etud3)

    def test_matching_etudiant_seuil(self):
        result = match_etudiant_par_nom('XXXXXXX YYYYYYY', self.etudiants)
        self.assertIsNone(result)

    def test_creation_fiche_et_lignes(self):
        user = Utilisateur.objects.create_user(
            username='chef_anon@iai.com', email='chef_anon@iai.com',
            password='password123', type_utilisateur='CHEF_ANONYMAT'
        )
        fiche = FicheNotesAnonymat.objects.create(
            matiere=self.matiere, salle=self.salle,
            type_evaluation=self.type_eval, annee_academique='2025-2026',
            cree_par=user
        )
        LigneFicheNotesAnonymat.objects.create(
            fiche=fiche, numero_anonymat='A1',
            note=Decimal('11.0'), nom_manuscrit_detecte='PATCHONG NJITACK ROMUALD',
            etudiant=self.etud1
        )
        LigneFicheNotesAnonymat.objects.create(
            fiche=fiche, numero_anonymat='A2',
            note=Decimal('13.0'), nom_manuscrit_detecte='NZE TOUOWO WILFRIED',
            etudiant=self.etud2
        )
        self.assertEqual(fiche.lignes.count(), 2)
        self.assertEqual(fiche.statut, 'BROUILLON')

    def test_analyser_fiche_demo_sans_classe(self):
        resultats = analyser_fiche_anonymat_image(None, etudiants_classe=None)
        self.assertEqual(len(resultats), 24)
        self.assertEqual(resultats[0]['numero_anonymat'], 'A1')
        self.assertEqual(resultats[0]['note'], Decimal('11'))
        self.assertEqual(resultats[0]['nom_manuscrit_detecte'], 'PATCHONG NJITACK ROMUALD')
        self.assertIsNone(resultats[0]['etudiant'])

    def test_analyser_fiche_demo_avec_matching(self):
        resultats = analyser_fiche_anonymat_image(None, etudiants_classe=self.etudiants)
        self.assertEqual(len(resultats), 24)
        # Les 3 étudiants de setUp doivent être matchés
        matched = [r for r in resultats if r['etudiant'] is not None]
        self.assertGreaterEqual(len(matched), 2)

    def test_validation_fiche_creates_official_notes(self):
        # Création de l'utilisateur chef anonymat
        chef_anon = Utilisateur.objects.create_user(
            username='chef_anon_test@iai.com', email='chef_anon_test@iai.com',
            password='password123', type_utilisateur='CHEF_ANONYMAT'
        )
        self.client.login(username='chef_anon_test@iai.com', password='password123')
        
        # Création de la fiche d'anonymat
        fiche = FicheNotesAnonymat.objects.create(
            matiere=self.matiere, salle=self.salle,
            type_evaluation=self.type_eval, annee_academique='2025-2026',
            cree_par=chef_anon
        )
        # Ajout d'une ligne avec étudiant matché
        ligne = LigneFicheNotesAnonymat.objects.create(
            fiche=fiche, numero_anonymat='A1',
            note=Decimal('15.5'), nom_manuscrit_detecte='PATCHONG NJITACK ROMUALD',
            etudiant=self.etud1
        )
        
        # Simuler la validation de la fiche via POST
        response = self.client.post(
            f'/notes/fiches-anonymat/{fiche.pk}/valider/',
            {
                'valider': '',
                f'note_{ligne.pk}': '15.50',
                f'etudiant_{ligne.pk}': str(self.etud1.pk)
            }
        )
        
        self.assertEqual(response.status_code, 302)
        fiche.refresh_from_db()
        self.assertEqual(fiche.statut, 'VALIDE')
        
        # Vérifier que l'évaluation et la note ont été créées (en filtrant par code de matière)
        eval_exists = Evaluation.objects.filter(cours__matiere__code=self.matiere.code, type_evaluation=self.type_eval).exists()
        self.assertTrue(eval_exists)
        
        note_exists = Note.objects.filter(etudiant=self.etud1, valeur=Decimal('15.5')).exists()
        self.assertTrue(note_exists)

    def test_recours_workflow(self):
        # Créer d'abord un enseignant et un cours/evaluation
        prof = Utilisateur.objects.create_user(
            username='prof_test@iai.com', email='prof_test@iai.com',
            password='password123', type_utilisateur='PROFESSEUR'
        )
        # Créer une matière de notes correspondante
        from apps.notes.models import Matiere as NotesMatiere
        notes_matiere = NotesMatiere.objects.create(
            code=self.matiere.code, nom=self.matiere.nom, credit=3, semestre=1, volume_horaire=30
        )
        cours = Cours.objects.create(
            matiere=notes_matiere, filiere=self.filiere, niveau=self.niveau,
            professeur=prof, annee_academique='2025-2026', semestre=1
        )
        eval_obj = Evaluation.objects.create(
            cours=cours, type_evaluation=self.type_eval, titre='Exam IA',
            date_evaluation=date.today(), coefficient=1.00
        )
        note_obj = Note.objects.create(
            evaluation=eval_obj, etudiant=self.etud1, valeur=Decimal('08.0'), est_validee=True
        )
        
        # Créer le recours
        from apps.notes.models import RecoursNote
        recours = RecoursNote.objects.create(
            etudiant=self.etud1, evaluation=eval_obj,
            note_actuelle=Decimal('08.0'), note_demandee=Decimal('12.0'),
            motif='Erreur de calcul dans la question 3.', statut='EN_ATTENTE'
        )
        
        # Essayer d'accéder à la liste des recours (En tant qu'étudiant)
        stud_user = Utilisateur.objects.create_user(
            username='stud_test@iai.com', email='stud_test@iai.com',
            password='password123', type_utilisateur='ETUDIANT'
        )
        self.client.login(username='stud_test@iai.com', password='password123')
        
        # L'étudiant ne doit pas voir les recours des autres
        response = self.client.get('/notes/recours/liste/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['recours_list']), 0)
        
        # Enseignant se connecte et traite le recours
        self.client.login(username='prof_test@iai.com', password='password123')
        response = self.client.get('/notes/recours/liste/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['recours_list']), 1)
        
        # Accepter le recours
        response = self.client.post(
            f'/notes/recours/{recours.pk}/traiter/',
            {'statut': 'ACCEPTE', 'decision': 'Après vérification, la question 3 a été recalculée.'}
        )
        self.assertEqual(response.status_code, 302)
        
        recours.refresh_from_db()
        self.assertEqual(recours.statut, 'ACCEPTE')
        
        # Vérifier que la note a été mise à jour
        note_obj.refresh_from_db()
        self.assertEqual(note_obj.valeur, Decimal('12.0'))

    def test_mon_bulletin_view(self):
        # Création de l'étudiant utilisateur avec matricule correspondant
        stud_user = Utilisateur.objects.create_user(
            username='stud_bulletin@iai.com', email='stud_bulletin@iai.com',
            password='password123', type_utilisateur='ETUDIANT',
            matricule='GL.CMR.D014.2526Z'
        )
        etud = Etudiant.objects.create(
            utilisateur=stud_user, nom='Jean', prenom='Dupont',
            email='stud_bulletin@iai.com', telephone='690000000',
            adresse='Douala', date_naissance=date(2000, 1, 1),
            lieu_naissance='Douala', sexe='M',
            filiere=self.filiere, annee_academique=self.annee,
            matricule='GL.CMR.D014.2526Z'
        )
        
        self.client.login(username='stud_bulletin@iai.com', password='password123')
        response = self.client.get('/notes/mon-bulletin/?semestre=1')
        self.assertEqual(response.status_code, 200)

    def test_apis(self):
        chef_anon = Utilisateur.objects.create_user(
            username='api_anon@iai.com', email='api_anon@iai.com',
            password='password123', type_utilisateur='CHEF_ANONYMAT'
        )
        self.client.login(username='api_anon@iai.com', password='password123')
        
        # Test API notes étudiant
        response = self.client.get(f'/notes/api/etudiant/{self.etud1.pk}/notes/')
        self.assertEqual(response.status_code, 200)
        
        # Test API moyennes filière
        response = self.client.get(f'/notes/api/filiere/{self.filiere.pk}/moyennes/')
        self.assertEqual(response.status_code, 200)

    def test_proces_verbal_generation_and_transmission(self):
        chef_anon = Utilisateur.objects.create_user(
            username='chef_anon_pv@iai.com', email='chef_anon_pv@iai.com',
            password='password123', type_utilisateur='CHEF_ANONYMAT'
        )
        self.client.login(username='chef_anon_pv@iai.com', password='password123')
        
        fiche = FicheNotesAnonymat.objects.create(
            matiere=self.matiere, salle=self.salle,
            type_evaluation=self.type_eval, annee_academique='2025-2026',
            cree_par=chef_anon
        )
        ligne = LigneFicheNotesAnonymat.objects.create(
            fiche=fiche, numero_anonymat='A1',
            note=Decimal('14.5'), nom_manuscrit_detecte='PATCHONG NJITACK ROMUALD',
            etudiant=self.etud1
        )
        
        response = self.client.post(
            f'/notes/fiches-anonymat/{fiche.pk}/valider/',
            {
                'valider': '',
                f'note_{ligne.pk}': '14.50',
                f'etudiant_{ligne.pk}': str(self.etud1.pk)
            }
        )
        self.assertEqual(response.status_code, 302)
        
        from apps.notes.models import ProcesVerbalNotes
        pv_exists = ProcesVerbalNotes.objects.filter(fiche_anonymat=fiche).exists()
        self.assertTrue(pv_exists)
        
        pv = ProcesVerbalNotes.objects.get(fiche_anonymat=fiche)
        self.assertFalse(pv.est_transmis)
        
        response = self.client.get(f'/notes/pv/{pv.pk}/')
        self.assertEqual(response.status_code, 200)
        
        response = self.client.post(f'/notes/pv/{pv.pk}/transmettre/')
        self.assertEqual(response.status_code, 302)
        
        pv.refresh_from_db()
        self.assertTrue(pv.est_transmis)

    def test_proces_verbal_deletion_by_chef_anonymat(self):
        chef_anon = Utilisateur.objects.create_user(
            username='chef_anon_del@iai.com', email='chef_anon_del@iai.com',
            password='password123', type_utilisateur='CHEF_ANONYMAT'
        )
        self.client.login(username='chef_anon_del@iai.com', password='password123')
        
        fiche = FicheNotesAnonymat.objects.create(
            matiere=self.matiere, salle=self.salle,
            type_evaluation=self.type_eval, annee_academique='2025-2026',
            cree_par=chef_anon
        )
        
        from apps.notes.models import ProcesVerbalNotes
        pv = ProcesVerbalNotes.objects.create(
            fiche_anonymat=fiche,
            titre="PV de test",
            cree_par=chef_anon,
            est_transmis=True
        )
        
        # S'assurer que le PV existe
        self.assertTrue(ProcesVerbalNotes.objects.filter(pk=pv.pk).exists())
        
        # Supprimer le PV
        response = self.client.post(f'/notes/pv/{pv.pk}/supprimer/')
        self.assertEqual(response.status_code, 302)
        
        # Vérifier qu'il est supprimé de la base de données
        self.assertFalse(ProcesVerbalNotes.objects.filter(pk=pv.pk).exists())

    def test_proces_verbal_deletion_unauthorized(self):
        chef_anon = Utilisateur.objects.create_user(
            username='chef_anon_unauth@iai.com', email='chef_anon_unauth@iai.com',
            password='password123', type_utilisateur='CHEF_ANONYMAT'
        )
        
        fiche = FicheNotesAnonymat.objects.create(
            matiere=self.matiere, salle=self.salle,
            type_evaluation=self.type_eval, annee_academique='2025-2026',
            cree_par=chef_anon
        )
        
        from apps.notes.models import ProcesVerbalNotes
        pv = ProcesVerbalNotes.objects.create(
            fiche_anonymat=fiche,
            titre="PV de test non autorisé",
            cree_par=chef_anon
        )
        
        # Création étudiant pour test d'autorisation si non existant
        stud_user = Utilisateur.objects.filter(username='stud_test@iai.com').first()
        if not stud_user:
            stud_user = Utilisateur.objects.create_user(
                username='stud_test@iai.com',
                email='stud_test@iai.com',
                password='password123',
                type_utilisateur='ETUDIANT'
            )
            
        self.client.login(username='stud_test@iai.com', password='password123')
        
        # Tenter la suppression
        response = self.client.post(f'/notes/pv/{pv.pk}/supprimer/')
        self.assertEqual(response.status_code, 302)
        
        # S'assurer que le PV existe toujours en base de données
        self.assertTrue(ProcesVerbalNotes.objects.filter(pk=pv.pk).exists())

