"""
URLs pour la gestion des professeurs
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.liste_professeurs, name='liste_professeurs'),
    path('ajouter/', views.ajouter_professeur, name='ajouter_professeur'),
    path('<int:pk>/', views.detail_professeur, name='detail_professeur'),
    path('<int:pk>/modifier/', views.modifier_professeur, name='modifier_professeur'),
    path('<int:pk>/supprimer/', views.supprimer_professeur, name='supprimer_professeur'),
    path('<int:pk>/charge-horaire/', views.charge_horaire, name='charge_horaire'),
    
    # Départements
    path('departements/', views.liste_departements, name='liste_departements'),
    path('departements/ajouter/', views.ajouter_departement, name='ajouter_departement'),
    
    # Export et statistiques
    path('exporter/', views.exporter_professeurs, name='exporter_professeurs'),
    path('statistiques/', views.statistiques_professeurs, name='statistiques_professeurs'),
]
