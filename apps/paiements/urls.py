"""
URLs pour la gestion des paiements
IAI-Cameroun - Centre de Douala
"""
from django.urls import path
from . import views

app_name = 'paiements'

urlpatterns = [
    # Gestion des reçus
    path('', views.liste_recus, name='liste_recus'),
    path('televerser/<int:etudiant_id>/', views.televerser_recu, name='televerser_recu'),
    path('televerser/<int:etudiant_id>/<int:tranche_id>/', views.televerser_recu_tranche, name='televerser_recu_tranche'),
    path('recus/<int:pk>/', views.detail_recu, name='detail_recu'),
    path('recus/<int:pk>/valider/', views.valider_recu, name='valider_recu'),
    path('recus/<int:pk>/rejeter/', views.rejeter_recu, name='rejeter_recu'),
    
    # Gestion des tranches
    path('tranches/', views.liste_tranches, name='liste_tranches'),
    path('tranches/ajouter/', views.ajouter_tranche, name='ajouter_tranche'),
    path('tranches/<int:pk>/modifier/', views.modifier_tranche, name='modifier_tranche'),
    path('tranches/<int:pk>/supprimer/', views.supprimer_tranche, name='supprimer_tranche'),
    
    # Statistiques
    path('statistiques/', views.statistiques_paiements, name='statistiques_paiements'),
    
    # API
    path('api/recus-attente/', views.api_recus_attente, name='api_recus_attente'),
    
    # Paiement mobile money
    path('payer-penalites/', views.payer_penalites, name='payer_penalites'),
    path('api/momo/initier/', views.initier_paiement_momo, name='initier_paiement_momo'),
    path('api/momo/verifier/', views.verifier_paiement_momo, name='verifier_paiement_momo'),
    path('paiement-succes/', views.paiement_succes, name='paiement_succes'),
]