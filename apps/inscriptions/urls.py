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
    
    # Certificats de Scolarité
    path('certificats/', views.liste_certificats, name='liste_certificats'),
    path('certificats/imprimer-groupe/', views.imprimer_certificats_masse, name='imprimer_certificats_masse'),
    path('certificat/delivrer/', views.delivrer_certificat_scolarite, name='delivrer_certificat_scolarite_choix'),
    path('certificat/delivrer/<int:etudiant_id>/', views.delivrer_certificat_scolarite, name='delivrer_certificat_scolarite'),


    path('certificat/apercu/<uuid:token>/', views.apercu_certificat_scolarite, name='apercu_certificat_scolarite'),
    path('certificat/annuler/<uuid:token>/', views.annuler_certificat_scolarite, name='annuler_certificat_scolarite'),
    path('certificat/verifier/<uuid:token>/', views.verifier_certificat_public, name='verifier_certificat_public'),
    path('certificat/<int:etudiant_id>/', views.delivrer_certificat_scolarite, name='certificat_scolarite'),

    
    # Statistiques
    path('statistiques/', views.statistiques_financieres, name='statistiques_financieres'),
    
    # Fiche de Renseignement
    path('fiche-renseignement/', views.fiche_renseignement_etudiant, name='fiche_renseignement_etudiant'),
    path('fiche-renseignement/<int:pk>/', views.detail_fiche_renseignement, name='detail_fiche_renseignement'),
    path('fiche-renseignement/<int:pk>/pdf/', views.telecharger_fiche_pdf, name='telecharger_fiche_pdf'),

    # Export
    path('exporter/', views.exporter_inscriptions, name='exporter_inscriptions'),
]