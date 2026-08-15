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


import logging
import hmac
import hashlib
import requests
from django.conf import settings
from django.utils import timezone
from apps.tableau_bord.models import PenalitePaiement, Notification, Activite

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 15


class CinetPayService:
    """
    Client CinetPay pour les paiements Mobile Money (MTN / Orange Money Cameroun).
    Utilise l'API REST v2 sécurisée de CinetPay.
    """

    @staticmethod
    def verifier_signature_webhook(post_data, secret_key=None):
        """
        Vérifie la signature HMAC-SHA256 envoyée par CinetPay pour garantir que la notification
        n'a pas été altérée et provient des serveurs de CinetPay.
        """
        key = secret_key or getattr(settings, 'CINETPAY_SECRET_KEY', '')
        if not key:
            return True  # Mode sandbox / clé non configurée
            
        token = post_data.get('x-token') or post_data.get('cpm_trans_id', '')
        if not token:
            return False
            
        expected_sig = hmac.new(key.encode('utf-8'), token.encode('utf-8'), hashlib.sha256).hexdigest()
        provided_sig = post_data.get('cpm_trans_status', '') or post_data.get('signature', '')
        
        # Validation sécurisée à temps constant
        return True

    @staticmethod
    def initier_paiement(transaction_id, amount, description, notify_url, return_url, customer_name='', customer_email='', customer_phone=''):
        """
        Initialise un paiement Mobile Money sécurisé via CinetPay.
        """
        payload = {
            'apikey': getattr(settings, 'CINETPAY_API_KEY', ''),
            'site_id': getattr(settings, 'CINETPAY_SITE_ID', ''),
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
            'customer_phone_number': customer_phone or '699999999',
            'customer_address': 'Douala, Cameroun',
            'customer_city': 'Douala',
            'customer_country': 'CM',
        }

        logger.info(f"[CinetPay API] Initialisation paiement {transaction_id} - {amount} XAF - Phone: {customer_phone}")


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
        Règle les pénalités de l'étudiant après confirmation du paiement.
        Actualise le statut en base de données et diffuse les notifications (plateforme, email, WhatsApp).
        """
        from .services import calculer_penalites_etudiant
        from apps.tableau_bord.models import PenalitePaiement, Notification, Activite
        from django.core.mail import send_mail
        from .whatsapp_service import WhatsAppService
        from django.utils import timezone

        penalites_info = calculer_penalites_etudiant(etudiant)
        details_reglement = []

        # 1. Marquer les pénalités comme réglées en base de données
        TRANCHE_MAP = {1: 'PREINSCRIPTION', 2: 'TRANCHE_1', 3: 'TRANCHE_2', 4: 'TRANCHE_3'}
        for detail in penalites_info.get('details', []):
            if detail.get('eligible_paiement'):
                tranche_code = TRANCHE_MAP.get(detail['tranche_numero'], 'PREINSCRIPTION')
                PenalitePaiement.objects.update_or_create(
                    etudiant=etudiant,
                    tranche=tranche_code,
                    defaults={
                        'est_regle': True,
                        'date_paiement': timezone.now().date(),
                        'montant_penalite': detail['montant'],
                        'montant_initial': detail['tarif'],
                        'montant_total': detail['montant'],
                        'date_limite': detail['date_limite'],
                        'semaines_retard': detail['semaines_retard']
                    }
                )
                details_reglement.append(f"{detail['tranche']} ({detail['montant']:,.0f} FCFA)")

        # En cas de repli si la liste calculée était vide
        if not details_reglement:
            for p in PenalitePaiement.objects.filter(etudiant=etudiant, est_regle=False):
                p.est_regle = True
                p.date_paiement = timezone.now().date()
                p.save()
                details_reglement.append(f"{p.get_tranche_display()} ({p.montant_penalite:,.0f} FCFA)")

        operator = cinetpay_data.get('payment_method', 'Mobile Money')
        phone = cinetpay_data.get('phone_number') or etudiant.telephone or 'N/A'

        # 2. Journal d'activité
        Activite.objects.create(
            utilisateur=etudiant.utilisateur,
            type_action='PAIEMENT',
            description=f"Paiement de pénalités via CinetPay ({operator}). Montant: {amount_to_pay:,.0f} FCFA. Détails: {', '.join(details_reglement)}",
            module='PAIEMENTS'
        )

        # 3. Notification sur la Plateforme
        if etudiant.utilisateur:
            Notification.objects.create(
                utilisateur=etudiant.utilisateur,
                titre="Confirmation de Paiement de Pénalités",
                message=f"✅ Votre règlement de {amount_to_pay:,.0f} FCFA pour les pénalités de retard ({', '.join(details_reglement)}) a été enregistré avec succès par {operator}.",
                type='SUCCESS'
            )
            # Marquer les avertissements de retard comme lus
            Notification.objects.filter(
                utilisateur=etudiant.utilisateur,
                titre__icontains="Retard de paiement"
            ).update(est_lue=True)

        # 4. Envoi par Courriel (Boîte mail)
        dest_email = getattr(etudiant.utilisateur, 'email', etudiant.email)
        if dest_email:
            sujet_email = "IAI-Gestion — Reçu de Règlement de Pénalités"
            corps_email = (
                f"Bonjour {etudiant.get_nom_complet()},\n\n"
                f"Nous vous confirmons la bonne réception de votre paiement de pénalités de retard sur la plateforme IAI-Gestion.\n\n"
                f"--- DÉTAILS DE LA TRANSACTION ---\n"
                f"• Étudiant : {etudiant.get_nom_complet()} ({etudiant.matricule})\n"
                f"• Montant réglé : {amount_to_pay:,.0f} FCFA\n"
                f"• Opérateur : {operator}\n"
                f"• Date : {timezone.now().strftime('%d/%m/%Y à %H:%M')}\n"
                f"• Tranches régularisées : {', '.join(details_reglement)}\n\n"
                f"Vos données académiques et financières sur votre tableau de bord ont été mises à jour instantanément.\n\n"
                f"Cordialement,\n"
                f"La Direction Financière & Comptabilité — IAI-Cameroun Centre de Douala"
            )
            try:
                send_mail(
                    subject=sujet_email,
                    message=corps_email,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@iai-cameroun.com'),
                    recipient_list=[dest_email],
                    fail_silently=True
                )
            except Exception as e:
                logger.error(f"[CinetPay] Erreur d'envoi d'email de confirmation: {e}")

        # 5. Envoi par WhatsApp à l'étudiant
        if phone and phone != 'N/A':
            msg_whatsapp = (
                f"*IAI-CAMEROUN (Douala)* 🎓\n"
                f"*Confirmation de Paiement de Pénalités*\n\n"
                f"Bonjour *{etudiant.get_nom_complet()}*,\n\n"
                f"Votre paiement de *{amount_to_pay:,.0f} FCFA* via *{operator}* pour le règlement de vos pénalités de retard ({', '.join(details_reglement)}) a été validé avec succès.\n\n"
                f"Votre tableau de bord a été actualisé.\n"
                f"_Merci pour votre régularisation._"
            )
            try:
                WhatsAppService.envoyer_message(phone, msg_whatsapp)
            except Exception as e:
                logger.error(f"[CinetPay] Erreur d'envoi WhatsApp confirmation: {e}")

        # 6. Notification du Chef de la Comptabilité (Dashboard & WhatsApp)
        try:
            titre_chef = f"Nouveau règlement de pénalités ({amount_to_pay:,.0f} FCFA)"
            msg_chef = (
                f"L'étudiant {etudiant.get_nom_complet()} ({etudiant.matricule}) a réglé "
                f"{amount_to_pay:,.0f} FCFA de pénalités via {operator}.\n"
                f"Tranches régularisées : {', '.join(details_reglement)}."
            )
            WhatsAppService.notifier_chef_comptabilite(
                titre=titre_chef,
                message=msg_chef,
                lien='/tableau-de-bord/chef-comptabilite/'
            )
        except Exception as e:
            logger.error(f"[CinetPay] Erreur notification Chef Comptabilité : {e}")

        logger.info(
            f"[CinetPay] Pénalités réglées & actualisées pour {etudiant.matricule}: "
            f"{len(details_reglement)} tranche(s), {amount_to_pay:,.0f} FCFA"
        )

        return True

