"""
URLs pour l'application d'authentification
IAI-Cameroun - Centre de Douala
"""
from django.urls import path
from . import views

app_name = 'authentification'

urlpatterns = [
    # Inscription
    path('inscription/', views.inscription, name='inscription'),
    path('inscription/confirmation/', views.inscription_confirmation, name='inscription_confirmation'),
    
    # Profil
    path('profil/', views.profil, name='profil'),
    
    # Demandes d'inscription (admin)
    path('demandes/', views.liste_demandes, name='liste_demandes'),
    path('liste-demandes/', views.liste_demandes, name='liste_demandes_alt'),
    path('demandes/<int:pk>/', views.detail_demande, name='detail_demande'),
    path('demandes/<int:pk>/valider/', views.valider_demande, name='valider_demande'),
    path('demandes/<int:pk>/rejeter/', views.rejeter_demande, name='rejeter_demande'),
]