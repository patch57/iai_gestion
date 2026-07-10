import time
import random
from django.utils import timezone
from apps.tableau_bord.models import PenalitePaiement, Notification, Activite

class MobileMoneyPaymentService:
    """
    Simulateur professionnel d'API de paiement Mobile Money pour le Cameroun.
    Prend en charge Orange Money (OM) et MTN Mobile Money (MoMo).
    """

    @staticmethod
    def initier_paiement(operator, phone, amount, reference_motif):
        """
        Simule l'initialisation du paiement avec envoi du push USSD.
        Retourne un dictionnaire contenant les infos de la transaction.
        """
        # Validation basique du numéro camerounais (6xxxxxxxx ou 2xxxxxxxx)
        if not (phone.startswith('6') or phone.startswith('2')) or len(phone) != 9:
            return {
                'status': 'FAILED',
                'message': 'Numéro de téléphone invalide. Doit comporter 9 chiffres et commencer par 6 ou 2.',
                'transaction_id': None
            }

        # Simuler un ID de transaction unique
        prefix = "OM" if operator.upper() == "ORANGE" else "MTN"
        timestamp = int(time.time())
        transaction_id = f"{prefix}-{timestamp}-{random.randint(1000, 9999)}"

        # Simulation de succès du push (95% de chance que le push soit envoyé avec succès)
        if random.random() > 0.05:
            return {
                'status': 'PENDING',
                'message': f"Push USSD envoyé avec succès sur le numéro {phone}. En attente de confirmation par l'utilisateur.",
                'transaction_id': transaction_id,
                'operator': operator.upper(),
                'phone': phone,
                'amount': amount,
                'reference': reference_motif
            }
        else:
            return {
                'status': 'FAILED',
                'message': "Impossible d'atteindre l'opérateur réseau pour le moment. Veuillez réessayer.",
                'transaction_id': None
            }

    @staticmethod
    def verifier_statut_paiement(transaction_id):
        """
        Simule la vérification du statut auprès de l'opérateur.
        Dans une vraie intégration, ce serait un appel API vers Orange/MTN.
        Ici on simule un succès aléatoire (85% de réussite, 10% d'annulation, 5% d'expiration/solde insuffisant).
        """
        if not transaction_id:
            return {'status': 'FAILED', 'message': 'ID de transaction manquant.'}

        r = random.random()
        if r < 0.85:
            return {
                'status': 'SUCCESS',
                'message': 'Paiement effectué avec succès.',
                'financial_ref': f"REF-{random.randint(100000, 999999)}"
            }
        elif r < 0.95:
            return {
                'status': 'CANCELLED',
                'message': "Paiement annulé par l'utilisateur."
            }
        else:
            return {
                'status': 'FAILED',
                'message': "Solde insuffisant ou session expirée."
            }

    @classmethod
    def regler_penalites_etudiant(cls, etudiant, operator, phone, amount_to_pay):
        """
        Règle l'ensemble des pénalités non réglées de l'étudiant à hauteur du montant payé.
        """
        # Récupérer les pénalités non réglées
        penalites = PenalitePaiement.objects.filter(etudiant=etudiant, est_regle=False)
        montant_restant = amount_to_pay

        details_reglement = []
        for penalite in penalites:
            if montant_restant <= 0:
                break
            
            # Si le montant payé couvre au moins la pénalité
            if montant_restant >= penalite.montant_penalite:
                montant_restant -= penalite.montant_penalite
                penalite.marquer_paye()
                details_reglement.append(f"{penalite.get_tranche_display()} ({penalite.montant_penalite} FCFA)")
            else:
                # Paiement partiel non géré par la logique par défaut de marquer_paye, 
                # mais dans notre cas on règle par tranche entière.
                pass
        
        # Enregistrer l'activité dans le système
        Activite.objects.create(
            utilisateur=etudiant.utilisateur,
            type_action='PAIEMENT',
            description=f"Paiement de pénalités via {operator} sur le numéro {phone}. Montant: {amount_to_pay} FCFA. Détails: {', '.join(details_reglement)}",
            module='PAIEMENTS'
        )

        return len(details_reglement) > 0
