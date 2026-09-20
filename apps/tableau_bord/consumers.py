import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Consumer WebSocket pour la diffusion instantanée des notifications système 
    et des mises à jour des badges en temps réel.
    """

    async def connect(self):
        self.user = self.scope.get('user')

        if not self.user or not self.user.is_authenticated:
            logger.warning("[WebSocket] Connexion rejetée : utilisateur non authentifié.")
            await self.close()
            return

        self.group_name = f"user_{self.user.id}"

        # Joindre le groupe individuel de l'utilisateur
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()
        logger.info(f"[WebSocket] Connexion établie pour l'utilisateur {self.user.username} (ID: {self.user.id})")

        # Envoyer le message de bienvenue avec statut initial
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connecté au flux de notifications temps réel IAI-Gestion',
            'user_id': self.user.id
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
            logger.info(f"[WebSocket] Déconnexion pour l'utilisateur (Group: {self.group_name})")

    async def notification_message(self, event):
        """
        Gestionnaire d'événements déclenché par le signal Channel Layer.
        Transmet le payload JSON directement au client WebSocket.
        """
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'id': event.get('id'),
            'titre': event.get('titre'),
            'message': event.get('message'),
            'notification_type': event.get('notification_type', 'INFO'),
            'lien': event.get('lien', ''),
            'compteur_non_lues': event.get('compteur_non_lues', 0),
            'date_creation': event.get('date_creation')
        }))

    async def chat_message(self, event):
        """
        Gestionnaire d'événements pour les nouveaux messages privés.
        """
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'id': event.get('id'),
            'expediteur_id': event.get('expediteur_id'),
            'expediteur_nom': event.get('expediteur_nom'),
            'destinataire_id': event.get('destinataire_id'),
            'sujet': event.get('sujet'),
            'contenu': event.get('contenu'),
            'date_envoi': event.get('date_envoi'),
            'compteur_messages_non_lus': event.get('compteur_messages_non_lus', 0)
        }))


class ChatConsumer(AsyncWebsocketConsumer):
    """
    Consumer WebSocket pour les salons de discussion en direct (Chat instantané).
    """

    async def connect(self):
        self.user = self.scope.get('user')
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        self.autre_user_id = self.scope['url_route']['kwargs'].get('user_id')
        user_ids = sorted([self.user.id, int(self.autre_user_id)])
        self.room_name = f"chat_{user_ids[0]}_{user_ids[1]}"

        await self.channel_layer.group_add(
            self.room_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_name'):
            await self.channel_layer.group_discard(
                self.room_name,
                self.channel_name
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))
