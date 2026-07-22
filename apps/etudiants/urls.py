"""
URLs pour la gestion des étudiants
IAI-Cameroun - Centre de Douala
"""
from django.urls import path
from . import views

app_name = 'etudiants'

urlpatterns = [
    # Gestion des étudiants
    path('', views.liste_etudiants, name='liste_etudiants'),
    path('ajouter/', views.ajouter_etudiant, name='ajouter_etudiant'),
    path('<int:pk>/', views.detail_etudiant, name='detail_etudiant'),
    path('<int:pk>/modifier/', views.modifier_etudiant, name='modifier_etudiant'),
    path('<int:pk>/supprimer/', views.supprimer_etudiant, name='supprimer_etudiant'),
    path('<int:pk>/carte/', views.carte_etudiant, name='carte_etudiant'),
    path('<int:pk>/documents/', views.documents_etudiant, name='documents_etudiant'),
    path('<int:pk>/documents/ajouter/', views.ajouter_document, name='ajouter_document'),
    path('documents/<int:doc_pk>/supprimer/', views.supprimer_document, name='supprimer_document'),
    path('<int:pk>/documents/televerser/<str:type_document>/', views.televerser_document, name='televerser_document'),
    
    # Gestion des filières
    path('filieres/', views.liste_filieres, name='liste_filieres'),
    path('filieres/ajouter/', views.ajouter_filiere, name='ajouter_filiere'),
    path('filieres/<int:pk>/modifier/', views.modifier_filiere, name='modifier_filiere'),
    path('filieres/<int:pk>/supprimer/', views.supprimer_filiere, name='supprimer_filiere'),
    path('filieres/<int:pk>/', views.detail_filiere, name='detail_filiere'),
    
    # Gestion des niveaux
    path('niveaux/', views.liste_niveaux, name='liste_niveaux'),
    path('niveaux/ajouter/', views.ajouter_niveau, name='ajouter_niveau'),
    path('niveaux/<int:pk>/modifier/', views.modifier_niveau, name='modifier_niveau'),
    path('niveaux/<int:pk>/supprimer/', views.supprimer_niveau, name='supprimer_niveau'),
    
    # Gestion des classes
    path('classes/', views.liste_classes, name='liste_classes'),
    path('classes/ajouter/', views.ajouter_classe, name='ajouter_classe'),
    path('classes/<int:pk>/modifier/', views.modifier_classe, name='modifier_classe'),
    path('classes/<int:pk>/supprimer/', views.supprimer_classe, name='supprimer_classe'),
    path('classes/<int:pk>/', views.detail_classe, name='detail_classe'),
    path('classes/<int:pk>/etudiants/', views.etudiants_par_classe, name='etudiants_par_classe'),
    
    # Gestion des années académiques
    path('annees-academiques/', views.liste_annees_academiques, name='liste_annees_academiques'),
    path('annees-academiques/ajouter/', views.ajouter_annee_academique, name='ajouter_annee_academique'),
    path('annees-academiques/<int:pk>/modifier/', views.modifier_annee_academique, name='modifier_annee_academique'),
    path('annees-academiques/<int:pk>/supprimer/', views.supprimer_annee_academique, name='supprimer_annee_academique'),
    path('annees-academiques/<int:pk>/activer/', views.activer_annee_academique, name='activer_annee_academique'),
    
    # Import et export
    path('importer/', views.importer_etudiants, name='importer_etudiants'),
    path('exporter/', views.exporter_etudiants, name='exporter_etudiants'),
    path('exporter/filieres/', views.exporter_filieres, name='exporter_filieres'),
    
    # Statistiques
    path('statistiques/', views.statistiques_etudiants, name='statistiques_etudiants'),
    path('statistiques/filieres/', views.statistiques_par_filiere, name='statistiques_par_filiere'),
    path('statistiques/paiements/', views.statistiques_paiements, name='statistiques_paiements'),
    
    # API pour les requêtes AJAX
    path('api/classes/<int:filiere_id>/', views.api_classes_par_filiere, name='api_classes_par_filiere'),
    path('api/niveaux/<int:filiere_id>/', views.api_niveaux_par_filiere, name='api_niveaux_par_filiere'),
    path('api/recherche/', views.api_recherche_etudiants, name='api_recherche_etudiants'),
    
    # Actions de masse
    path('actions/changement-classe/', views.changement_classe_massif, name='changement_classe_massif'),
    path('actions/export-paiements/', views.export_paiements, name='export_paiements'),
    path('actions/validation-recus/', views.validation_recus_massive, name='validation_recus_massive'),
    
    # Inscriptions
    path('inscriptions/', views.liste_inscriptions, name='liste_inscriptions'),
    path('inscriptions/<int:pk>/valider/', views.valider_inscription, name='valider_inscription'),
    path('inscriptions/<int:pk>/rejeter/', views.rejeter_inscription, name='rejeter_inscription'),
    
    # Documents
    path('documents/en-attente/', views.documents_en_attente, name='documents_en_attente'),
    path('documents/<int:doc_pk>/valider/', views.valider_document, name='valider_document'),
]

# Alternative: Si vous préférez utiliser des vues basées sur les classes
# from .views import (
#     EtudiantListView, EtudiantCreateView, EtudiantDetailView,
#     EtudiantUpdateView, EtudiantDeleteView, CarteEtudiantView,
#     FiliereListView, FiliereCreateView, FiliereUpdateView, FiliereDeleteView,
#     ClasseListView, ClasseCreateView, ClasseUpdateView, ClasseDeleteView
# )
# 
# urlpatterns = [
#     path('', EtudiantListView.as_view(), name='liste_etudiants'),
#     path('ajouter/', EtudiantCreateView.as_view(), name='ajouter_etudiant'),
#     path('<int:pk>/', EtudiantDetailView.as_view(), name='detail_etudiant'),
#     path('<int:pk>/modifier/', EtudiantUpdateView.as_view(), name='modifier_etudiant'),
#     path('<int:pk>/supprimer/', EtudiantDeleteView.as_view(), name='supprimer_etudiant'),
#     path('<int:pk>/carte/', CarteEtudiantView.as_view(), name='carte_etudiant'),
#     path('filieres/', FiliereListView.as_view(), name='liste_filieres'),
#     path('filieres/ajouter/', FiliereCreateView.as_view(), name='ajouter_filiere'),
#     path('classes/', ClasseListView.as_view(), name='liste_classes'),
#     path('classes/ajouter/', ClasseCreateView.as_view(), name='ajouter_classe'),
# ]