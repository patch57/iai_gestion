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
    
    # Sessions de concours (Niveau 1) & Résultats
    path('sessions-concours/', views.gestion_sessions_concours, name='gestion_sessions_concours'),
    path('sessions-concours/creer/', views.creer_session_concours, name='creer_session_concours'),
    path('sessions-concours/<int:pk>/', views.detail_session_concours, name='detail_session_concours'),
    path('sessions-concours/<int:pk>/echeances/', views.editer_echeances_session, name='editer_echeances_session'),
    path('sessions-concours/<int:pk>/importer/', views.importer_resultats_concours, name='importer_resultats_concours'),
    path('sessions-concours/<int:pk>/exporter/', views.exporter_resultats_concours, name='exporter_resultats_concours'),
    path('sessions-concours/<int:pk>/exporter-pdf/', views.exporter_resultats_concours_pdf, name='exporter_resultats_concours_pdf'),
    path('resultats-concours/<int:pk>/payer-preinscription/', views.marquer_preinscription_payee, name='marquer_preinscription_payee'),
    path('resultats-concours/<int:pk>/payer-tranche/<int:tranche_num>/', views.marquer_tranche_payee, name='marquer_tranche_payee'),


    path('resultats-concours/<int:pk>/supprimer/', views.supprimer_resultat_concours, name='supprimer_resultat_concours'),
    path('telecharger-modele-concours/', views.telecharger_modele_csv_concours, name='telecharger_modele_csv_concours'),


    
    # Statistiques
    path('statistiques/', views.statistiques_paiements, name='statistiques_paiements'),
    
    # API
    path('api/recus-attente/', views.api_recus_attente, name='api_recus_attente'),
    
    # Paiement mobile money (CinetPay)
    path('payer-penalites/', views.payer_penalites, name='payer_penalites'),
    path('api/momo/initier/', views.initier_paiement_momo, name='initier_paiement_momo'),
    path('api/momo/verifier/', views.verifier_paiement_momo, name='verifier_paiement_momo'),
    path('api/cinetpay/webhook/', views.webhook_cinetpay, name='webhook_cinetpay'),
    path('paiement-succes/', views.paiement_succes, name='paiement_succes'),
]