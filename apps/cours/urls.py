"""
URLs pour la gestion des cours
"""
from django.urls import path
from . import views
from . import views_apprenants

app_name = 'cours'

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
    path('emploi-du-temps/officiel/', views.emploi_du_temps_officiel, name='emploi_du_temps_officiel'),
    path('emploi-du-temps/creer/', views.creer_emploi_du_temps_hebdo, name='creer_emploi_du_temps_hebdo'),
    path('emploi-du-temps/<int:pk>/editer/', views.editer_creneaux_emploi_du_temps, name='editer_creneaux_emploi_du_temps'),
    path('emploi-du-temps/<int:pk>/soumettre/', views.soumettre_emploi_du_temps, name='soumettre_emploi_du_temps'),
    path('emploi-du-temps/<int:pk>/approuver/', views.approuver_emploi_du_temps, name='approuver_emploi_du_temps'),
    path('emploi-du-temps/<int:pk>/imprimer/', views.imprimer_emploi_du_temps_officiel, name='imprimer_emploi_du_temps_officiel'),

    
    # Présences
    path('seance/<int:seance_id>/presence/', views.feuille_presence, name='feuille_presence'),
    
    # Planning
    path('planning-professeur/', views.planning_professeur, name='planning_professeur'),
    
    # Apprenants & Certifications
    path('apprenants/registre/', views_apprenants.liste_apprenants_categories, name='liste_apprenants_categories'),
    path('apprenants/notes/', views_apprenants.saisir_notes_apprenants, name='saisir_notes_apprenants'),
    path('apprenants/supports/', views_apprenants.liste_supports_apprenant, name='liste_supports_apprenant'),
    path('apprenants/supports/ajouter/', views_apprenants.ajouter_support_apprenant, name='ajouter_support_apprenant'),
]
