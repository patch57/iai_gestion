"""
URLs pour la gestion des inscriptions
IAI-Cameroun - Centre de Douala
"""
from django.urls import path
from . import views

app_name = 'inscriptions'  # ✅ AJOUT OBLIGATOIRE

urlpatterns = [
    # Inscriptions
    path('', views.liste_inscriptions, name='liste_inscriptions'),
    path('nouvelle/', views.nouvelle_inscription, name='nouvelle_inscription'),
    path('<int:pk>/', views.detail_inscription, name='detail_inscription'),
    path('<int:pk>/modifier/', views.modifier_inscription, name='modifier_inscription'),
    path('<int:pk>/valider/', views.valider_inscription, name='valider_inscription'),
    path('<int:pk>/supprimer/', views.supprimer_inscription, name='supprimer_inscription'),
    
    # Paiements
    path('<int:inscription_id>/paiement/', views.ajouter_paiement, name='ajouter_paiement'),
    path('paiements/', views.liste_paiements, name='liste_paiements'),
    path('paiements/<int:pk>/valider/', views.valider_paiement, name='valider_paiement'),
    path('paiements/<int:pk>/recu/', views.recu_paiement, name='recu_paiement'),
    
    # Bourses
    path('bourses/', views.liste_bourses, name='liste_bourses'),
    path('bourses/attribuer/', views.attribuer_bourse, name='attribuer_bourse'),
    path('bourses/<int:pk>/modifier/', views.modifier_bourse, name='modifier_bourse'),
    path('bourses/<int:pk>/supprimer/', views.supprimer_bourse, name='supprimer_bourse'),
    
    # Documents
    path('<int:inscription_id>/documents/ajouter/', views.ajouter_document, name='ajouter_document'),
    path('documents/<int:pk>/supprimer/', views.supprimer_document, name='supprimer_document'),
    
    # Certificats
    path('certificat/<int:etudiant_id>/', views.certificat_scolarite, name='certificat_scolarite'),
    
    # Statistiques
    path('statistiques/', views.statistiques_financieres, name='statistiques_financieres'),
    
    # Export
    path('exporter/', views.exporter_inscriptions, name='exporter_inscriptions'),
]