from django.apps import AppConfig


class TableauBordConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tableau_bord'
    verbose_name = 'Tableau de Bord IAI-Cameroun'
    
    def ready(self):
        """
        Méthode appelée lorsque l'application est prête
        Permet d'importer les signaux et d'initialiser des données
        """
        # Surcharger dynamiquement les settings à partir de la base de données
        try:
            from apps.tableau_bord.models import Configuration
            from django.conf import settings as django_settings
            
            # 1. Configurer CinetPay
            for key, setting_name in [
                ('CINETPAY_API_KEY', 'CINETPAY_API_KEY'),
                ('CINETPAY_SITE_ID', 'CINETPAY_SITE_ID'),
                ('CINETPAY_SECRET_KEY', 'CINETPAY_SECRET_KEY'),
                ('CINETPAY_MODE', 'CINETPAY_MODE'),
                ('SITE_BASE_URL', 'SITE_BASE_URL'),
            ]:
                val = Configuration.get_valeur(key)
                if val:
                    setattr(django_settings, setting_name, val)
                    
            # Mettre à jour les URL dérivées de CinetPay
            django_settings.CINETPAY_PAYMENT_URL = f'{getattr(django_settings, "CINETPAY_BASE_URL", "https://api-checkout.cinetpay.com")}/v2/payment'
            django_settings.CINETPAY_CHECK_URL = f'{getattr(django_settings, "CINETPAY_BASE_URL", "https://api-checkout.cinetpay.com")}/v2/payment/check'

            # 2. Configurer la messagerie SMTP
            for key, setting_name in [
                ('EMAIL_HOST', 'EMAIL_HOST'),
                ('EMAIL_PORT', 'EMAIL_PORT'),
                ('EMAIL_HOST_USER', 'EMAIL_HOST_USER'),
                ('EMAIL_HOST_PASSWORD', 'EMAIL_HOST_PASSWORD'),
                ('EMAIL_USE_TLS', 'EMAIL_USE_TLS'),
                ('EMAIL_USE_SSL', 'EMAIL_USE_SSL'),
                ('DEFAULT_FROM_EMAIL', 'DEFAULT_FROM_EMAIL'),
            ]:
                val = Configuration.get_valeur(key)
                if val:
                    if setting_name == 'EMAIL_PORT':
                        setattr(django_settings, setting_name, int(val))
                    elif setting_name in ['EMAIL_USE_TLS', 'EMAIL_USE_SSL']:
                        setattr(django_settings, setting_name, val.lower() == 'true')
                    else:
                        setattr(django_settings, setting_name, val)
        except Exception:
            # Éviter de bloquer si la base de données n'est pas encore prête/migrée
            pass