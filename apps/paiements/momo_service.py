"""
Service de paiement Mobile Money via CinetPay
IAI-Cameroun - Centre de Douala

Passerelle réelle : CinetPay (https://cinetpay.com)
Supporte : MTN Mobile Money + Orange Money (Cameroun)
"""
import logging
import requests
from django.conf import settings
from django.utils import timezone
from apps.tableau_bord.models import PenalitePaiement, Notification, Activite

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 15


class CinetPayService:
    """
    Client CinetPay pour les paiements Mobile Money au Cameroun.
    Utilise l'API REST v2 de CinetPay (2 endpoints seulement).
    """

    @staticmethod
    def initier_paiement(transaction_id, amount, description, notify_url, return_url, customer_name='', customer_email=''):
        """
        Initialise un paiement via CinetPay.
        Retourne un dict avec payment_url (URL de redirection) ou une erreur.

        Endpoint : POST https://api-checkout.cinetpay.com/v2/payment
        """
        payload = {
            'apikey': settings.CINETPAY_API_KEY,
            'site_id': settings.CINETPAY_SITE_ID,
            'transaction_id': transaction_id,
            'amount': int(amount),
            'currency': 'XAF',
            'description': description,
            'notify_url': notify_url,
            'return_url': return_url,
            'channels': 'MOBILE_MONEY',
            'lang': 'FR',
            'metadata': description,
            'customer_name': customer_name or 'Etudiant IAI',
            'customer_email': customer_email or '',
            'customer_phone_number': '',
            'customer_address': 'Douala, Cameroun',
            'customer_city': 'Douala',
            'customer_country': 'CM',
        }

        logger.info(f"[CinetPay] Initialisation paiement {transaction_id} - {amount} XAF")

        try:
            response = requests.post(
                settings.CINETPAY_PAYMENT_URL,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=TIMEOUT_SECONDS
            )
            data = response.json()
    
            logger.info(f"[CinetPay] Réponse init: code={data.get('code')} message={data.get('message')}")
    
            if data.get('code') == '201':
                payment_data = data.get('data', {})
                return {
                    'status': 'PENDING',
                    'payment_url': payment_data.get('payment_url', ''),
                    'payment_token': payment_data.get('payment_token', ''),
                    'transaction_id': transaction_id,
                    'message': 'Redirection vers la page de paiement CinetPay...'
                }
            else:
                logger.error(f"[CinetPay] Échec init: {data}")
                if getattr(settings, 'CINETPAY_MODE', 'PRODUCTION') == 'SANDBOX':
                    logger.info("[CinetPay] Mode SANDBOX activé, simulation locale suite à l'échec de la réponse de l'API")
                    return {
                        'status': 'PENDING',
                        'payment_url': return_url,
                        'payment_token': 'sandbox_token_123456789',
                        'transaction_id': transaction_id,
                        'message': 'Simulation locale CinetPay en cours...'
                    }
                return {
                    'status': 'FAILED',
                    'message': data.get('message', "Erreur lors de l'initialisation du paiement."),
                    'transaction_id': transaction_id
                }
    
        except (requests.Timeout, requests.ConnectionError, Exception) as e:
            logger.error(f"[CinetPay] Erreur lors de l'appel à l'API: {e}")
            if getattr(settings, 'CINETPAY_MODE', 'PRODUCTION') == 'SANDBOX':
                logger.info("[CinetPay] Mode SANDBOX activé, simulation locale suite à l'erreur de connexion/timeout")
                return {
                    'status': 'PENDING',
                    'payment_url': return_url,
                    'payment_token': 'sandbox_token_123456789',
                    'transaction_id': transaction_id,
                    'message': 'Simulation locale CinetPay en cours...'
                }
            
            if isinstance(e, requests.Timeout):
                return {
                    'status': 'FAILED',
                    'message': "Le serveur de paiement met trop de temps à répondre. Réessayez.",
                    'transaction_id': transaction_id
                }
            elif isinstance(e, requests.ConnectionError):
                return {
                    'status': 'FAILED',
                    'message': "Impossible de joindre le serveur de paiement. Vérifiez votre connexion.",
                    'transaction_id': transaction_id
                }
            else:
                return {
                    'status': 'FAILED',
                    'message': "Erreur interne. Contactez l'administration.",
                    'transaction_id': transaction_id
                }

    @staticmethod
    def verifier_statut_paiement(transaction_id):
        """
        Vérifie le statut d'une transaction auprès de CinetPay.

        Endpoint : POST https://api-checkout.cinetpay.com/v2/payment/check
        
        Codes retour CinetPay :
        - "00" : Paiement réussi
        - "600" : En attente de paiement
        - "627" : Paiement annulé
        - Autre : Échec
        """
        payload = {
            'apikey': settings.CINETPAY_API_KEY,
            'site_id': settings.CINETPAY_SITE_ID,
            'transaction_id': transaction_id,
        }

        logger.info(f"[CinetPay] Vérification statut {transaction_id}")

        try:
            if getattr(settings, 'CINETPAY_MODE', 'PRODUCTION') == 'SANDBOX':
                logger.info(f"[CinetPay] Mode SANDBOX activé, confirmation automatique de la transaction {transaction_id}")
                return {
                    'status': 'SUCCESS',
                    'message': 'Paiement simulé avec succès.',
                    'data': {
                        'status': 'ACCEPTED',
                        'payment_method': 'MOCK_MONEY',
                        'phone_number': '677777777',
                    },
                    'payment_method': 'MOCK_MONEY',
                    'phone_number': '677777777',
                    'operator': 'MOCK_MONEY',
                }
            
            response = requests.post(
                settings.CINETPAY_CHECK_URL,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=TIMEOUT_SECONDS
            )
            data = response.json()
            code = data.get('code', '')
            tx_data = data.get('data', {})

            logger.info(f"[CinetPay] Vérification: code={code} status={tx_data.get('status', 'N/A')}")

            if code == '00':
                return {
                    'status': 'SUCCESS',
                    'message': 'Paiement effectué avec succès.',
                    'data': tx_data,
                    'payment_method': tx_data.get('payment_method', ''),
                    'phone_number': tx_data.get('phone_prefix', '') + tx_data.get('phone_suffix', ''),
                    'operator': tx_data.get('payment_method', ''),
                }
            elif code == '600':
                return {
                    'status': 'PENDING',
                    'message': 'Paiement en cours de traitement...',
                    'data': tx_data
                }
            elif code == '627':
                return {
                    'status': 'CANCELLED',
                    'message': "Le paiement a été annulé.",
                    'data': tx_data
                }
            else:
                return {
                    'status': 'FAILED',
                    'message': data.get('message', 'Le paiement a échoué.'),
                    'data': tx_data
                }

        except requests.Timeout:
            logger.error(f"[CinetPay] Timeout vérification ({TIMEOUT_SECONDS}s)")
            return {'status': 'PENDING', 'message': 'Vérification en cours...'}
        except Exception as e:
            logger.exception(f"[CinetPay] Erreur vérification: {e}")
            return {'status': 'PENDING', 'message': 'Impossible de vérifier le statut pour le moment.'}

    @classmethod
    def regler_penalites_etudiant(cls, etudiant, cinetpay_data, amount_to_pay):
        """
        Règle les pénalités non réglées de l'étudiant après confirmation du paiement.
        """
        penalites = PenalitePaiement.objects.filter(etudiant=etudiant, est_regle=False)
        montant_restant = float(amount_to_pay)
        details_reglement = []

        for penalite in penalites:
            if montant_restant <= 0:
                break
            if montant_restant >= penalite.montant_penalite:
                montant_restant -= penalite.montant_penalite
                penalite.marquer_paye()
                details_reglement.append(f"{penalite.get_tranche_display()} ({penalite.montant_penalite} FCFA)")

        operator = cinetpay_data.get('payment_method', 'Mobile Money')
        phone = cinetpay_data.get('phone_number', 'N/A')

        Activite.objects.create(
            utilisateur=etudiant.utilisateur,
            type_action='PAIEMENT',
            description=f"Paiement de pénalités via CinetPay ({operator}). "
                        f"Montant: {amount_to_pay} FCFA. "
                        f"Détails: {', '.join(details_reglement)}",
            module='PAIEMENTS'
        )

        logger.info(
            f"[CinetPay] Pénalités réglées pour {etudiant.matricule}: "
            f"{len(details_reglement)} tranche(s), {amount_to_pay} FCFA"
        )

        return len(details_reglement) > 0
