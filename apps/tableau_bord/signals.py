import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Notification, Message

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Notification)
def notifier_websocket_nouvelle_notification(sender, instance, created, **kwargs):
    """
    Déclenché automatiquement lors de la création d'une notification.
    Pousse l'événement en temps réel sur le WebSocket de l'utilisateur concerné.
    """
    if created and instance.utilisateur:
        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                compteur = Notification.objects.filter(utilisateur=instance.utilisateur, est_lue=False).count()
                group_name = f"user_{instance.utilisateur.id}"
                
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        'type': 'notification_message',
                        'id': instance.id,
                        'titre': instance.titre,
                        'message': instance.message,
                        'notification_type': instance.type,
                        'lien': instance.lien or '',
                        'compteur_non_lues': compteur,
                        'date_creation': instance.date_creation.strftime('%H:%M - %d/%m/%Y') if instance.date_creation else ''
                    }
                )
                logger.info(f"[WebSocket Signal] Push notification #{instance.id} au groupe {group_name}")
        except Exception as e:
            logger.error(f"[WebSocket Signal] Erreur d'envoi notification: {e}")


@receiver(post_save, sender=Message)
def notifier_websocket_nouveau_message(sender, instance, created, **kwargs):
    """
    Déclenché automatiquement lors de l'envoi d'un nouveau message privé.
    Pousse le message au destinataire via WebSocket.
    """
    if created and instance.destinataire:
        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                compteur_msg = Message.objects.filter(destinataire=instance.destinataire, est_lu=False).count()
                
                async_to_sync(channel_layer.group_send)(
                    f"user_{instance.destinataire.id}",
                    {
                        'type': 'chat_message',
                        'id': instance.id,
                        'expediteur_id': instance.expediteur.id if instance.expediteur else None,
                        'expediteur_nom': instance.expediteur.get_full_name() or instance.expediteur.username if instance.expediteur else "Système",
                        'destinataire_id': instance.destinataire.id,
                        'sujet': instance.sujet,
                        'contenu': instance.contenu,
                        'date_envoi': instance.date_envoi.strftime('%H:%M') if instance.date_envoi else '',
                        'compteur_messages_non_lus': compteur_msg
                    }
                )
                logger.info(f"[WebSocket Signal] Push message #{instance.id} à l'utilisateur {instance.destinataire.id}")
        except Exception as e:
            logger.error(f"[WebSocket Signal] Erreur d'envoi message: {e}")
