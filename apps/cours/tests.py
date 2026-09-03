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
        
        from apps.cours.models import MatiereFormation
        matiere = MatiereFormation.objects.filter(formation=self.formation).first()
        self.assertIsNotNone(matiere)

        # Enregistrer une note de 18.5/20 pour notre apprenant
        data = {
            f'note_{self.apprenant.id}_{matiere.id}': '18.5',
            f'commentaire_{self.apprenant.id}_{matiere.id}': 'Excellent apprenant'
        }
        response = self.client.post(f"{reverse('cours:saisir_notes_apprenants')}?formation_id={self.formation.id}", data)
        self.assertEqual(response.status_code, 302) # Redirection après succès
        
        # Vérifier en BD
        note_obj = NoteApprenant.objects.filter(apprenant=self.apprenant, formation=self.formation, matiere=matiere).first()
        self.assertIsNotNone(note_obj)
        self.assertEqual(note_obj.note, 18.5)
        self.assertEqual(note_obj.commentaire, 'Excellent apprenant')
        self.assertEqual(note_obj.formateur, self.formateur)
        self.client.logout()


from apps.etudiants.models import Filiere
from apps.cours.models import EmploiDuTempsHebdomadaire, CreneauEmploiDuTemps, Salle

class EmploiDuTempsOfficielTestCase(TestCase):
    def setUp(self):
        self.chef_etudes = User.objects.create_user(
            username='chef_etudes',
            email='chef_etudes@iai.com',
            password='password123',
            type_utilisateur='CHEF_ETUDES',
            matricule='CHE.CMR.D001.2024.A'
        )
        self.directeur = User.objects.create_user(
            username='directeur',
            email='directeur@iai.com',
            password='password123',
            type_utilisateur='ADMIN_SYSTEME',
            matricule='DIR.CMR.D001.2024.A'
        )
        self.filiere = Filiere.objects.create(code='GL', nom='Génie Logiciel', duree_ans=2)
        self.salle = Salle.objects.create(code='GL3D', nom='Salle GL3D', capacite=35)
        self.client = Client()

    def test_workflow_creation_soumission_approbation(self):
        """Vérifie le cycle de vie : Création Brouillon -> Soumission Directeur -> Approbation/Publication (Lundi au Samedi)"""
        # 1. Création par le Chef des Études
        emploi = EmploiDuTempsHebdomadaire.objects.create(
            filiere=self.filiere,
            salle=self.salle,
            niveau='LEVEL_1',
            titre_semaine='SEMAINE: 11 MAI - 16 MAI 2026',
            date_debut_semaine='2026-05-11',
            date_fin_semaine='2026-05-16',
            soumis_par=self.chef_etudes,
            statut='BROUILLON'
        )
        self.assertEqual(emploi.statut, 'BROUILLON')

        # 2. Ajout de créneaux du Lundi au Samedi
        creneau_lundi = CreneauEmploiDuTemps.objects.create(
            emploi_du_temps=emploi,
            jour='LUNDI',
            plage='P1',
            intitule='Revue de projets',
            enseignant_nom='M NNANGA',
            salle_nom='GL3D',
            progression_heures='28/30 hrs',
            type_evenement='COURS'
        )
        creneau_samedi = CreneauEmploiDuTemps.objects.create(
            emploi_du_temps=emploi,
            jour='SAMEDI',
            plage='P2',
            intitule='TP(TRAVAUX PRATIQUE)',
            enseignant_nom='TPL3',
            salle_nom='GL3D',
            progression_heures='72/300 hrs',
            type_evenement='COURS'
        )
        self.assertEqual(emploi.creneaux.count(), 2)

        # 3. Soumission par le Chef des Études au Directeur
        self.client.login(username='chef_etudes', password='password123')
        response = self.client.get(reverse('cours:soumettre_emploi_du_temps', args=[emploi.pk]))
        self.assertEqual(response.status_code, 302)
        emploi.refresh_from_db()
        self.assertEqual(emploi.statut, 'EN_ATTENTE_VALIDATION')
        self.client.logout()

        # 4. Approbation par le Directeur et redistribution
        self.client.login(username='directeur', password='password123')
        response = self.client.post(reverse('cours:approuver_emploi_du_temps', args=[emploi.pk]), {'action': 'approuver'})
        self.assertEqual(response.status_code, 302)
        emploi.refresh_from_db()
        self.assertEqual(emploi.statut, 'VALIDE')
        self.assertEqual(emploi.approuve_par, self.directeur)
        self.client.logout()

    def test_rejet_emploi_du_temps_avec_motif(self):
        """Vérifie le rejet par le Directeur avec enregistrement du motif"""
        emploi = EmploiDuTempsHebdomadaire.objects.create(
            filiere=self.filiere,
            salle=self.salle,
            niveau='LEVEL_2',
            titre_semaine='SEMAINE: 18 MAI - 23 MAI 2026',
            date_debut_semaine='2026-05-18',
            date_fin_semaine='2026-05-23',
            soumis_par=self.chef_etudes,
            statut='EN_ATTENTE_VALIDATION'
        )
        
        self.client.login(username='directeur', password='password123')
        data = {
            'action': 'rejeter',
            'motif_rejet': 'Veuillez déplacer le cours de Réseaux du Lundi après-midi au Mardi matin.'
        }
        response = self.client.post(reverse('cours:approuver_emploi_du_temps', args=[emploi.pk]), data)
        self.assertEqual(response.status_code, 302)
        emploi.refresh_from_db()
        self.assertEqual(emploi.statut, 'REJETE')
        self.assertEqual(emploi.motif_rejet, 'Veuillez déplacer le cours de Réseaux du Lundi après-midi au Mardi matin.')
        self.client.logout()


class PresenceHebdomadaireTestCase(TestCase):
    def setUp(self):
        self.scolarite = User.objects.create_user(
            username='scolarite_test', email='scolarite@test.com',
            password='password123', type_utilisateur='CHEF_SCOLARITE'
        )
        self.filiere = Filiere.objects.create(code='GL', nom='Génie Logiciel', duree_ans=3)
        from apps.etudiants.models import Niveau, Classe, Etudiant, AnneeAcademique
        self.niveau = Niveau.objects.create(filiere=self.filiere, numero=1, code='GL1-pres')
        self.annee = AnneeAcademique.objects.create(code='2025-2026', date_debut='2025-09-01', date_fin='2026-08-31', est_active=True)
        self.classe = Classe.objects.create(nom='GL1A', filiere=self.filiere, niveau=self.niveau, annee_academique=self.annee)

        self.etud1 = Etudiant.objects.create(
            matricule='GL.CMR.D001.2526A', nom='ALIMA NDAM', prenom='FARIDA',
            email='alima@test.com', telephone='670000010', adresse='Douala',
            date_naissance='2000-01-01', lieu_naissance='Douala', sexe='F',
            filiere=self.filiere, classe=self.classe, statut='INSCRIT'
        )
        self.etud2 = Etudiant.objects.create(
            matricule='GL.CMR.D003.2526A', nom='BABINNE DIGWE', prenom='ELIAS',
            email='babinne@test.com', telephone='670000011', adresse='Douala',
            date_naissance='2000-01-01', lieu_naissance='Douala', sexe='M',
            filiere=self.filiere, classe=self.classe, statut='INSCRIT'
        )

    def test_matching_etudiant_presence(self):
        from apps.cours.presence_service import matcher_etudiant_presence
        etudiants = [self.etud1, self.etud2]
        
        match, score = matcher_etudiant_presence('GL.CMR.D003.2526A', etudiants)
        self.assertEqual(match, self.etud2)
        self.assertGreaterEqual(score, 0.9)

        match_name, score_name = matcher_etudiant_presence('ALIMA NDAM FARIDA', etudiants)
        self.assertEqual(match_name, self.etud1)

    def test_cumul_absences_publication(self):
        from apps.cours.models import FichePresenceHebdomadaire, LignePresenceHebdomadaire
        from apps.cours.presence_service import calculer_total_absences_cumulees

        fiche = FichePresenceHebdomadaire.objects.create(
            classe=self.classe, filiere=self.filiere, niveau=self.niveau,
            semaine_du='2026-05-25', semaine_au='2026-05-29', cree_par=self.scolarite
        )
        LignePresenceHebdomadaire.objects.create(fiche=fiche, etudiant=self.etud2, nombre_absences=6)

        # Après publication : 6
        fiche.statut = 'PUBLIE'
        fiche.save()
        self.assertEqual(calculer_total_absences_cumulees(self.etud2), 6)

    def test_notes_annuelles_discipline_rule(self):
        from apps.cours.models import FichePresenceHebdomadaire, LignePresenceHebdomadaire
        from apps.cours.presence_service import calculer_notes_annuelles_discipline

        fiche = FichePresenceHebdomadaire.objects.create(
            classe=self.classe, filiere=self.filiere, niveau=self.niveau,
            semaine_du='2026-05-25', semaine_au='2026-05-29', cree_par=self.scolarite,
            statut='PUBLIE'
        )
        # Etudiant 1 : 35 absences non justifiées -> Exclu(e)
        LignePresenceHebdomadaire.objects.create(fiche=fiche, etudiant=self.etud1, nombre_absences=35, heures_justifiees=0)
        # Etudiant 2 : 35 absences dont 10 justifiées -> HNJ = 25 -> Décision vide
        LignePresenceHebdomadaire.objects.create(fiche=fiche, etudiant=self.etud2, nombre_absences=35, heures_justifiees=10)

        data = calculer_notes_annuelles_discipline(self.classe.id)
        r1 = next(item for item in data['results'] if item['etudiant'] == self.etud1)
        r2 = next(item for item in data['results'] if item['etudiant'] == self.etud2)

        self.assertEqual(r1['ha'], 35)
        self.assertEqual(r1['hnj'], 35)
        self.assertEqual(r1['decision'], 'Exclu(e)')

        self.assertEqual(r2['ha'], 35)
        self.assertEqual(r2['hj'], 10)
        self.assertEqual(r2['hnj'], 25)
        self.assertEqual(r2['decision'], '')

    def test_exporter_liste_classe_presence_pdf_view(self):
        self.client.login(username='scolarite_test', password='password123')
        url = reverse('cours:exporter_liste_classe_presence_pdf', args=[self.classe.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('LISTE DE PRESENCE', response.content.decode('utf-8'))
        self.assertIn(self.classe.nom, response.content.decode('utf-8'))
        self.client.logout()

    def test_programme_quotidien_enseignant(self):
        from apps.professeurs.models import Professeur, Departement
        from apps.cours.models import EmploiDuTempsHebdomadaire, CreneauEmploiDuTemps
        from apps.cours.presence_service import obtenir_programme_quotidien_enseignant
        import datetime

        user_prof = User.objects.create_user(
            username='prof_nnanga', email='nnanga@test.com',
            password='password123', type_utilisateur='PROFESSEUR',
            first_name='Dieudonné', last_name='NNANGA'
        )
        dept = Departement.objects.create(code='INFO', nom='Informatique')
        prof = Professeur.objects.create(
            utilisateur=user_prof, matricule='PR100', nom='NNANGA', prenom='Dieudonné',
            email='nnanga@test.com', telephone='690000000', adresse='Douala',
            date_naissance='1980-01-01', date_embauche='2020-01-01', grade='TITULAIRE',
            specialite='Génie Logiciel', departement=dept
        )

        emploi = EmploiDuTempsHebdomadaire.objects.create(
            filiere=self.filiere, niveau='LEVEL_1', titre_semaine='SEMAINE TEST',
            date_debut_semaine='2026-05-01', date_fin_semaine='2026-05-31', statut='VALIDE'
        )

        # Créer deux créneaux un Lundi (P2 puis P1)
        CreneauEmploiDuTemps.objects.create(
            emploi_du_temps=emploi, jour='LUNDI', plage='P2',
            intitule='Base de données', enseignant_nom='M. NNANGA', salle_nom='GL1'
        )
        CreneauEmploiDuTemps.objects.create(
            emploi_du_temps=emploi, jour='LUNDI', plage='P1',
            intitule='Algorithmique', enseignant_nom='M. NNANGA', salle_nom='GL1'
        )

        # Tester pour une date qui tombe un Lundi (ex: 2026-05-18)
        lundi_date = datetime.date(2026, 5, 18)
        resultat = obtenir_programme_quotidien_enseignant(user_prof, date_cible=lundi_date)

        self.assertEqual(len(resultat['creneaux']), 2)
        # Vérifier l'ordre chronologique (P1 avant P2)
        self.assertEqual(resultat['creneaux'][0].plage, 'P1')
        self.assertEqual(resultat['creneaux'][1].plage, 'P2')


class ImportServiceTestCase(TestCase):
    def test_extraire_creneaux_csv(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.cours.import_service import extraire_creneaux_multi_format

        csv_content = (
            "Jour,Plage,Intitule,Enseignant,Salle,Type\n"
            "LUNDI,P1,Python Avancé,M. TCHAMOU,GL1,COURS\n"
            "MARDI,P2,Réseaux CISCO,M. NDOMBE,SR2,COURS\n"
        ).encode('utf-8')

        file_obj = SimpleUploadedFile("emploi_test.csv", csv_content, content_type="text/csv")
        result = extraire_creneaux_multi_format(file_obj)

        self.assertEqual(result['stats']['valid'], 2)
        self.assertEqual(result['stats']['errors'], 0)
        self.assertEqual(result['stats']['conflits'], 0)
        self.assertEqual(result['valid_items'][0]['intitule'], "Python Avancé")

    def test_detection_conflits_creneaux(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.cours.import_service import extraire_creneaux_multi_format

        csv_content = (
            "Jour,Plage,Intitule,Enseignant,Salle,Type\n"
            "LUNDI,P1,Python Avancé,M. TCHAMOU,GL1,COURS\n"
            "LUNDI,P1,Base de données,M. KENGNE,GL1,COURS\n"
        ).encode('utf-8')

        file_obj = SimpleUploadedFile("conflit_test.csv", csv_content, content_type="text/csv")
        result = extraire_creneaux_multi_format(file_obj)

        self.assertEqual(result['stats']['valid'], 2)
        self.assertEqual(result['stats']['conflits'], 1)
        self.assertTrue(any("Conflit de créneau" in c for c in result['conflits']))


class RessourceEcheanceTestCase(TestCase):
    def setUp(self):
        self.prof_user = User.objects.create_user(
            username='prof_echeance', email='prof@test.com',
            password='password123', type_utilisateur='ENSEIGNANT',
            matricule='ENS.CMR.D555.2026.A'
        )
        from apps.professeurs.models import Professeur, Departement
        dept = Departement.objects.create(code='MATH', nom='Mathématiques')
        self.prof = Professeur.objects.create(
            utilisateur=self.prof_user, matricule='P555', nom='KOUAM', prenom='Jean',
            email='prof@test.com', telephone='699000000', adresse='Douala',
            date_naissance='1985-01-01', date_embauche='2020-01-01', grade='TITULAIRE',
            specialite='Algèbre', departement=dept
        )
        from apps.cours.models import Matiere, Cours, RessourceCours
        self.filiere = Filiere.objects.create(code='GL', nom='Génie Logiciel', duree_ans=2)
        self.matiere = Matiere.objects.create(code='PY101', nom='Python', credits=4, heures_cours=30)
        self.cours = Cours.objects.create(
            code='C-PY101', matiere=self.matiere, professeur=self.prof, filiere=self.filiere,
            annee_academique='2025-2026', jour='Lundi', heure_debut='08:00', heure_fin='10:00',
            date_debut='2025-09-01', date_fin='2026-06-30'
        )
        self.client = Client()

    def test_gestion_et_compte_a_rebours_echeance(self):
        """Vérifie la création, la mise à jour, la suppression d'échéance physique et le compte à rebours"""
        from apps.cours.models import RessourceCours
        import datetime

        today = timezone.now().date()
        date_futur = today + datetime.timedelta(days=3)

        # 1. Créer ressource avec date limite
        res = RessourceCours.objects.create(
            cours=self.cours, type_ressource='TP', titre='TP Chapitre 1',
            date_limite_remise_physique=date_futur
        )

        self.assertEqual(res.jours_restants_remise, 3)
        self.assertIn("J-3", res.compte_a_rebours_display)

        # 2. Se connecter et modifier l'échéance à +7 jours via la vue
        self.client.login(username='prof_echeance', password='password123')
        date_7j = (today + datetime.timedelta(days=7)).strftime('%Y-%m-%d')
        
        response = self.client.post(
            reverse('cours:modifier_echeance_ressource', args=[res.pk]),
            {'date_limite_remise_physique': date_7j}
        )
        self.assertEqual(response.status_code, 302)
        res.refresh_from_db()
        self.assertEqual(res.jours_restants_remise, 7)
        self.assertIn("J-7", res.compte_a_rebours_display)

        # 3. Supprimer l'échéance via la vue
        response = self.client.post(reverse('cours:supprimer_echeance_ressource', args=[res.pk]))
        self.assertEqual(response.status_code, 302)
        res.refresh_from_db()
        self.assertIsNone(res.date_limite_remise_physique)
        self.assertIsNone(res.jours_restants_remise)
        self.assertIsNone(res.compte_a_rebours_display)

        # 4. Supprimer la ressource elle-même par l'enseignant auteur
        response_del = self.client.post(reverse('cours:supprimer_ressource', args=[res.pk]))
        self.assertEqual(response_del.status_code, 302)
        self.client.logout()

    def test_presence_enseignant_auto_sync_and_pdf(self):
        """Test de la synchronisation automatique des fiches hebdo enseignants et de l'export PDF"""
        import datetime
        from apps.cours.models import FichePresenceEnseignantHebdo
        from apps.cours.presence_service import synchroniser_fiche_presence_enseignant_auto

        # 1. Tester la synchronisation automatique
        today = datetime.date.today()
        lundi = today - datetime.timedelta(days=today.weekday())
        samedi = lundi + datetime.timedelta(days=5)

        from apps.authentification.models import Utilisateur
        scol_user = Utilisateur.objects.create_user(
            username='scol_user_test', password='password123', type_utilisateur='CHEF_SCOLARITE'
        )

        fiche, created, count = synchroniser_fiche_presence_enseignant_auto(user=scol_user)
        self.assertIsNotNone(fiche)
        self.assertEqual(fiche.semaine_du, lundi)
        self.assertEqual(fiche.semaine_au, samedi)

        # 2. Tester la vue d'export PDF
        self.client.login(username='scol_user_test', password='password123')
        response = self.client.get(reverse('cours:exporter_fiche_presence_enseignant_pdf', args=[fiche.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.client.logout()







