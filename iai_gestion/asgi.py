"""
Configuration ASGI pour le projet IAI-Gestion.
Prend en charge HTTP et WebSockets en temps réel via Django Channels.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'iai_gestion.settings')

# Initialisation précoce de l'application Django ASGI pour charger l'ORM
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import apps.tableau_bord.routing

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(
            apps.tableau_bord.routing.websocket_urlpatterns
        )
    ),
})
