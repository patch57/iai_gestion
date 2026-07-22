import ssl
from django.core.mail.backends.smtp import EmailBackend as SMTPBackend
from django.utils.functional import cached_property
from django.conf import settings

class UnverifiedEmailBackend(SMTPBackend):
    """
    Backend de messagerie SMTP qui contourne la vérification SSL.
    Utile pour le développement sur des machines où les magasins de certificats 
    locaux ou les antivirus provoquent des erreurs de vérification de certificat CA.
    """
    @cached_property
    def ssl_context(self):
        # Récupérer la configuration de contournement
        bypass_ssl = getattr(settings, 'EMAIL_BYPASS_SSL', False)
        
        if bypass_ssl:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            return ssl_context
            
        return super().ssl_context
