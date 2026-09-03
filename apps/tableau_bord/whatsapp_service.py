"""
Service de Notification WhatsApp & SMS 100% Gratuit
IAI-Cameroun - Centre de Douala

Fonctionnalités :
1. Génération de liens direct WhatsApp (https://wa.me/237...) sans coût ni abonnement.
2. Envoi direct via passerelle gratuite CallMeBot API (si configurée).
3. Consolidation et journalisation automatique des alertes dans les notifications du système IAI-Gestion.
"""

import urllib.parse
import logging
import requests
from django.utils import timezone
from apps.tableau_bord.models import Notification

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Service de gestion des envois WhatsApp / SMS gratuits"""

    INDICATIF_PAR_DEFAUT = "237"  # Cameroun

    @classmethod
    def normaliser_numero(cls, telephone):
        """Standardise un numéro de téléphone au format international (ex: 237690000000)"""
        if not telephone:
            return ""

        # Retirer espaces, tirets, parenthèses, plus
        nettoye = ''.join(c for c in str(telephone) if c.isdigit())

        # Si le numéro commence par 6 ou 2 et fait 9 chiffres (format Cameroun standard)
        if len(nettoye) == 9 and nettoye.startswith(('6', '2')):
            nettoye = cls.INDICATIF_PAR_DEFAUT + nettoye
        
        return nettoye

    @classmethod
    def generer_lien_whatsapp(cls, telephone, message):
        """
        Génère un lien Click-to-WhatsApp 100% gratuit (wa.me).
        Permet à l'agent comptable ou scolarité d'ouvrir la discussion avec le message pré-rempli.
        """
        num_norm = cls.normaliser_numero(telephone)
        if not num_norm:
            return "#"

        texte_encode = urllib.parse.quote(message)
        return f"https://wa.me/{num_norm}?text={texte_encode}"

    @classmethod
    def envoyer_message_callmebot(cls, telephone, message, api_key=""):
        """
        Envoie un message via l'API CallMeBot gratuite pour WhatsApp (si une clé gratuite est enregistrée).
        """
        num_norm = cls.normaliser_numero(telephone)
        if not num_norm or not api_key:
            return False, "Numéro ou clé API manquante"

        texte_encode = urllib.parse.quote(message)
        url = f"https://api.callmebot.com/whatsapp.php?phone={num_norm}&text={texte_encode}&apikey={api_key}"

        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                return True, "Message WhatsApp transmis via CallMeBot"
            return False, f"Erreur CallMeBot HTTP {resp.status_code}"
        except Exception as e:
            logger.error(f"Erreur envoi CallMeBot: {e}")
            return False, str(e)

    @classmethod
    def envoyer_message(cls, destinataire, message):
        """
        Envoie un message WhatsApp au destinataire spécifié.
        Utilise l'API configurée (UltraMsg, CallMeBot, Chat-API) ou simule l'envoi en dev/log.
        """
        num_norm = cls.normaliser_numero(destinataire)
        if not num_norm:
            logger.warning("[WhatsApp] Numéro de téléphone invalide.")
            return False

        # Charger la configuration dynamique depuis le modèle Configuration
        try:
            from apps.tableau_bord.models import Configuration
            api_enabled = Configuration.get_valeur('WHATSAPP_ENABLED', 'False').lower() == 'true'
            api_url = Configuration.get_valeur('WHATSAPP_API_URL', '').strip()
            api_token = Configuration.get_valeur('WHATSAPP_TOKEN', '').strip()
        except Exception:
            api_enabled, api_url, api_token = False, '', ''

        logger.info(f"[WhatsApp] Tentative d'envoi à +{num_norm}...")

        # En mode simulé si non activé ou non configuré
        if not api_enabled or not api_url:
            msg_log = message.encode('ascii', errors='replace').decode('ascii')
            logger.info(
                f"\n=== [SIMULATION WHATSAPP] ===\n"
                f"Destinataire : +{num_norm}\n"
                f"Message : \n{msg_log}\n"
                f"=============================\n"
            )
            return True

        # Intégration via CallMeBot si l'URL pointe dessus
        if "callmebot" in api_url.lower():
            succes, msg = cls.envoyer_message_callmebot(num_norm, message, api_key=api_token)
            return succes

        # Intégration Meta WhatsApp Business Cloud API (graph.facebook.com)
        if "facebook.com" in api_url.lower() or "meta" in api_url.lower():
            headers = {
                'Authorization': f'Bearer {api_token}',
                'Content-Type': 'application/json'
            }
            payload = {
                'messaging_product': 'whatsapp',
                'recipient_type': 'individual',
                'to': num_norm,
                'type': 'text',
                'text': {
                    'preview_url': False,
                    'body': message
                }
            }
            try:
                resp = requests.post(api_url, json=payload, headers=headers, timeout=10)
                if resp.status_code in (200, 201):
                    logger.info(f"[WhatsApp Meta API] Message envoyé avec succès à +{num_norm}")
                    return True
                else:
                    logger.error(f"[WhatsApp Meta API] Échec d'envoi à +{num_norm} (HTTP {resp.status_code}: {resp.text})")
                    return False
            except Exception as e:
                logger.error(f"[WhatsApp Meta API] Erreur de connexion : {str(e)}")
                return False

        # Intégration générique HTTP API (UltraMsg, Chat-API, Twilio, etc.)
        payload = {
            'token': api_token,
            'to': f"+{num_norm}",
            'body': message
        }

        if "ultramsg" in api_url.lower():
            payload = {'token': api_token, 'to': num_norm, 'body': message}
        elif "chat-api" in api_url.lower():
            payload = {'chatId': f"{num_norm}@c.us", 'body': message}

        try:
            headers = {'Content-Type': 'application/json'}
            resp = requests.post(api_url, json=payload, headers=headers, timeout=8)
            if resp.status_code in (200, 201):
                logger.info(f"[WhatsApp] Message envoyé avec succès à +{num_norm}")
                return True
            else:
                logger.error(f"[WhatsApp] Échec d'envoi à +{num_norm} (HTTP {resp.status_code})")
                return False
        except Exception as e:
            logger.error(f"[WhatsApp] Erreur de connexion avec l'API WhatsApp : {str(e)}")
            return False

    @classmethod
    def notifier_etudiant(cls, etudiant, titre, message, canal='WHATSAPP'):
        """
        Consigne la notification dans le système et prépare le lien/action d'envoi.
        """
        notif_interne = None
        if hasattr(etudiant, 'utilisateur') and etudiant.utilisateur:
            notif_interne = Notification.objects.create(
                utilisateur=etudiant.utilisateur,
                titre=titre,
                message=message,
                type='WARNING',
                est_lue=False
            )

        telephone = getattr(etudiant, 'telephone', '') or (etudiant.utilisateur.telephone if hasattr(etudiant, 'utilisateur') and hasattr(etudiant.utilisateur, 'telephone') else "")
        lien_wa = cls.generer_lien_whatsapp(telephone, f"*[IAI-CAMEROUN - CENTRE DE DOUALA]*\n\n*{titre}*\n\n{message}")

        return {
            'succes': True,
            'etudiant': etudiant.get_nom_complet() if hasattr(etudiant, 'get_nom_complet') else str(etudiant),
            'telephone': telephone,
            'lien_whatsapp': lien_wa,
            'notif_id': notif_interne.id if notif_interne else None
        }

    @classmethod
    def notifier_chef_comptabilite(cls, titre, message, lien='/tableau-de-bord/chef-comptabilite/'):
        """
        Notifie le Chef de la Comptabilité à la fois dans son Dashboard (Notification in-app)
        et via WhatsApp pour les événements financiers (pénalités, formations continues/certifiantes, reçus).
        """
        from django.contrib.auth import get_user_model
        from apps.tableau_bord.models import Notification

        User = get_user_model()
        chefs = User.objects.filter(type_utilisateur='CHEF_COMPTABILITE', est_actif=True)
        if not chefs.exists():
            chefs = User.objects.filter(is_superuser=True, est_actif=True)

        notifs_creees = []
        for chef in chefs:
            # 1. Notification in-app dans son Dashboard
            notif = Notification.objects.create(
                utilisateur=chef,
                type='SUCCESS',
                titre=titre,
                message=message,
                lien=lien
            )
            notifs_creees.append(notif)

            # 2. Notification WhatsApp si le Chef a un numéro de téléphone
            telephone = getattr(chef, 'telephone', '') or getattr(chef, 'contact', '')
            if telephone:
                msg_wa = (
                    f"*IAI-CAMEROUN (Douala)* 💰\n"
                    f"*NOTIFICATION GESTION FINANCIÈRE*\n\n"
                    f"*{titre}*\n\n"
                    f"{message}\n\n"
                    f"_Message automatique pour le Chef de la Comptabilité._"
                )
                try:
                    cls.envoyer_message(telephone, msg_wa)
                except Exception as e:
                    logger.error(f"[WhatsApp Chef Comptabilité] Erreur d'envoi : {e}")

        return notifs_creees


