from django.test import TestCase
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
        
        # Création d'une tranche de pré-inscription en retard (limite dépassée de 15 jours, soit 2 semaines)
        self.tranche1 = TranchePaiement.objects.create(
            numero=1,
            montant=50000,
            date_limite=date.today() - timedelta(days=15),
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
        
        self.assertEqual(email.to, ['testetudiant@iai.com'])
        self.assertIn("Rappel : Frais de Scolarité et Pénalités", email.subject)
        # Nettoyer les espaces insécables ou formats possibles du montant
        self.assertTrue(any(x in email.body for x in ["3 000", "3000"]))
        self.assertIn("Pré-inscription", email.body)
