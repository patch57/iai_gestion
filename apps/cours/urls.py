"""
URLs pour la gestion des cours
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.liste_cours, name='liste_cours'),
    path('ajouter/', views.ajouter_cours, name='ajouter_cours'),
    path('<int:pk>/', views.detail_cours, name='detail_cours'),
    path('<int:pk>/modifier/', views.modifier_cours, name='modifier_cours'),
    path('<int:pk>/supprimer/', views.supprimer_cours, name='supprimer_cours'),
    
    # Matières
    path('matieres/', views.liste_matieres, name='liste_matieres'),
    path('matieres/ajouter/', views.ajouter_matiere, name='ajouter_matiere'),
    
    # Salles
    path('salles/', views.liste_salles, name='liste_salles'),
    path('salles/ajouter/', views.ajouter_salle, name='ajouter_salle'),
    
    # Emplois du temps
    path('emplois-du-temps/', views.emploi_du_temps, name='emploi_du_temps'),
    
    # Présences
    path('seance/<int:seance_id>/presence/', views.feuille_presence, name='feuille_presence'),
    
    # Planning
    path('planning-professeur/', views.planning_professeur, name='planning_professeur'),
]
