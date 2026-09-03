"""
Service centralisé d'envoi et de gestion des notifications multi-acteurs
IAI-Cameroun - Centre de Douala
"""
from django.contrib.auth import get_user_model
from django.db import transaction
from .models import Notification

User = get_user_model()


class NotificationService:
    """Service d'envoi de notifications ciblées selon le rôle ou l'utilisateur"""

    @staticmethod
    def notifier_utilisateur(user, titre, message, type_notif='INFO', lien=None):
        """Envoie une notification individuelle à un utilisateur spécifique"""
        if not user or not user.is_active:
            return None
        
        return Notification.objects.create(
            utilisateur=user,
            titre=titre,
            message=message,
            type=type_notif,
            lien=lien
        )

    @staticmethod
    def notifier_roles(roles, titre, message, type_notif='INFO', lien=None, inclure_superusers=True):
        """
        Envoie une notification à tous les utilisateurs actifs possédant l'un des rôles spécifiés.
        :param roles: liste de chaînes (ex: ['DIRECTEUR', 'CHEF_SCOLARITE'])
        """
        if isinstance(roles, str):
            roles = [roles]

        query = User.objects.filter(is_active=True)
        
        if inclure_superusers:
            destinataires = query.filter(models_q_roles_or_superuser(roles))
        else:
            destinataires = query.filter(type_utilisateur__in=roles)

        notifications_a_creer = [
            Notification(
                utilisateur=user,
                titre=titre,
                message=message,
                type=type_notif,
                lien=lien
            )
            for user in destinataires.distinct()
        ]

        if notifications_a_creer:
            with transaction.atomic():
                return Notification.objects.bulk_create(notifications_a_creer)
        return []

    @classmethod
    def notifier_directeur(cls, titre, message, type_notif='INFO', lien=None):
        """Notifie le Directeur / Représentant Résident (et Admins système)"""
        return cls.notifier_roles(['DIRECTEUR', 'ADMIN_SYSTEME'], titre, message, type_notif=type_notif, lien=lien)

    @classmethod
    def notifier_chef_scolarite(cls, titre, message, type_notif='INFO', lien=None):
        """Notifie le Chef de la Scolarité"""
        return cls.notifier_roles(['CHEF_SCOLARITE'], titre, message, type_notif=type_notif, lien=lien)

    @classmethod
    def notifier_admin_financier(cls, titre, message, type_notif='INFO', lien=None):
        """Notifie l'Admin Financier et le Chef Comptabilité"""
        return cls.notifier_roles(['ADMIN_FINANCIER', 'CHEF_COMPTABILITE'], titre, message, type_notif=type_notif, lien=lien)

    @classmethod
    def notifier_chef_anonymat(cls, titre, message, type_notif='INFO', lien=None):
        """Notifie le Chef Anonymat"""
        return cls.notifier_roles(['CHEF_ANONYMAT'], titre, message, type_notif=type_notif, lien=lien)

    @classmethod
    def notifier_chef_etudes(cls, titre, message, type_notif='INFO', lien=None):
        """Notifie le Chef des Études et Admin Pédagogique"""
        return cls.notifier_roles(['CHEF_ETUDES', 'ADMIN_PEDAGOGIQUE'], titre, message, type_notif=type_notif, lien=lien)


def models_q_roles_or_superuser(roles):
    """Génère un Q filter pour les rôles + superusers"""
    from django.db.models import Q
    return Q(type_utilisateur__in=roles) | Q(is_superuser=True)
