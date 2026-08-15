"""
URLs pour la gestion des cours
"""
from django.urls import path
from . import views
from . import views_apprenants
from . import views_evaluations

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

    
    # Présences & Fiches Hebdomadaires (LISTE DE PRESENCE IAI)
    path('seance/<int:seance_id>/presence/', views.feuille_presence, name='feuille_presence'),
    path('presences/fiches/', views.liste_fiches_presence, name='liste_fiches_presence'),
    path('presences/fiches/creer/', views.creer_fiche_presence, name='creer_fiche_presence'),
    path('presences/fiches/<int:pk>/saisie/', views.saisie_grille_presence, name='saisie_grille_presence'),
    path('presences/fiches/importer/', views.importer_fiche_presence, name='importer_fiche_presence'),
    path('presences/fiches/<int:pk>/publier/', views.publier_fiche_presence, name='publier_fiche_presence'),
    path('presences/discipline/salle/<int:salle_id>/', views.note_annuelle_discipline, name='note_annuelle_discipline'),
    path('presences/liste-classe/<int:classe_id>/pdf/', views.exporter_liste_classe_presence_pdf, name='exporter_liste_classe_presence_pdf'),
    
    # Planning
    path('planning-professeur/', views.planning_professeur, name='planning_professeur'),
    
    # Apprenants & Certifications
    path('apprenants/registre/', views_apprenants.liste_apprenants_categories, name='liste_apprenants_categories'),
    path('apprenants/notes/', views_apprenants.saisir_notes_apprenants, name='saisir_notes_apprenants'),
    path('apprenants/supports/', views_apprenants.liste_supports_apprenant, name='liste_supports_apprenant'),
    path('apprenants/supports/ajouter/', views_apprenants.ajouter_support_apprenant, name='ajouter_support_apprenant'),

    # Évaluation Anonyme des Enseignants par les Apprenants
    path('evaluations/', views_evaluations.liste_evaluations_etudiant, name='liste_evaluations_etudiant'),
    path('evaluations/cours/<int:cours_id>/', views_evaluations.evaluer_cours, name='evaluer_cours'),
    path('evaluations/synthese/', views_evaluations.synthese_evaluations_professeur, name='synthese_evaluations_professeur'),
    path('evaluations/synthese/<int:professeur_id>/', views_evaluations.synthese_evaluations_professeur, name='synthese_evaluations_professeur_detail'),
]
