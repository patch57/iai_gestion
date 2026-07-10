"""
Configuration des URLs pour IAI-Gestion
IAI-Cameroun - Centre de Douala
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.views.generic import TemplateView

# Import des vues disponibles
try:
    from apps.tableau_bord.views import accueil
except ImportError:
    # Fonction de fallback si l'application n'est pas encore prête
    def accueil(request):
        return redirect('login')

urlpatterns = [
    # Administration
    path('admin/', admin.site.urls),
    
    # Page d'accueil
    path('', accueil, name='accueil'),

    path('deconnexion-page/', TemplateView.as_view(template_name='deconnexion.html'), name='deconnexion_page'),
    
    # Authentification
    path('login/', auth_views.LoginView.as_view(
        template_name='base/login.html',
        redirect_authenticated_user=True
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('password-change/', auth_views.PasswordChangeView.as_view(
        template_name='base/password_change.html'
    ), name='password_change'),
    path('password-change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='base/password_change_done.html'
    ), name='password_change_done'),
    
    # ✅ Application d'authentification (inscription, etc.)
    path('authentification/', include('apps.authentification.urls')),
    
    # Applications
    path('tableau-de-bord/', include('apps.tableau_bord.urls')),
    path('etudiants/', include('apps.etudiants.urls')),
    path('paiements/', include('apps.paiements.urls')),
    path('professeurs/', include('apps.professeurs.urls')),
    path('cours/', include('apps.cours.urls')),
    path('notes/', include('apps.notes.urls')),
    path('inscriptions/', include('apps.inscriptions.urls')),
]

# Configuration pour les fichiers médias et statiques en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)