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
    path('ressources/<int:pk>/supprimer/', views.supprimer_ressource, name='supprimer_ressource'),
    path('ressources/<int:pk>/echeance/modifier/', views.modifier_echeance_ressource, name='modifier_echeance_ressource'),
    path('ressources/<int:pk>/echeance/supprimer/', views.supprimer_echeance_ressource, name='supprimer_echeance_ressource'),
    
    # Matières & Attributions
    path('matieres/', views.liste_matieres, name='liste_matieres'),
    path('matieres/ajouter/', views.ajouter_matiere, name='ajouter_matiere'),
    path('matieres/attribuer/', views.attribuer_matiere, name='attribuer_matiere_globale'),
    path('matieres/<int:matiere_id>/attribuer/', views.attribuer_matiere, name='attribuer_matiere'),
    path('matieres/desattribuer/<int:cours_id>/', views.desattribuer_matiere, name='desattribuer_matiere'),
    path('matieres/<int:pk>/modifier/', views.modifier_matiere, name='modifier_matiere'),
    path('matieres/<int:pk>/supprimer/', views.supprimer_matiere, name='supprimer_matiere'),
    
    # Salles
    path('salles/', views.liste_salles, name='liste_salles'),
    path('salles/ajouter/', views.ajouter_salle, name='ajouter_salle'),
    
    # Emplois du temps
    path('emplois-du-temps/', views.emploi_du_temps, name='emploi_du_temps'),
    path('emploi-du-temps/officiel/', views.emploi_du_temps_officiel, name='emploi_du_temps_officiel'),
    path('emploi-du-temps/creer/', views.creer_emploi_du_temps_hebdo, name='creer_emploi_du_temps_hebdo'),
    path('emploi-du-temps/importer-csv/', views.importer_emploi_du_temps_csv, name='importer_emploi_du_temps_csv'),
    path('emploi-du-temps/<int:pk>/editer/', views.editer_creneaux_emploi_du_temps, name='editer_creneaux_emploi_du_temps'),
    path('emploi-du-temps/<int:pk>/soumettre/', views.soumettre_emploi_du_temps, name='soumettre_emploi_du_temps'),
    path('emploi-du-temps/<int:pk>/approuver/', views.approuver_emploi_du_temps, name='approuver_emploi_du_temps'),
    path('emploi-du-temps/<int:pk>/imprimer/', views.imprimer_emploi_du_temps_officiel, name='imprimer_emploi_du_temps_officiel'),
    path('emploi-du-temps/<int:pk>/pdf/', views.exporter_emploi_du_temps_pdf, name='exporter_emploi_du_temps_pdf'),
    path('emploi-du-temps/<int:pk>/ics/', views.exporter_emploi_du_temps_ics, name='exporter_emploi_du_temps_ics'),


    
    # Présences & Fiches Hebdomadaires (LISTE DE PRESENCE IAI)
    path('seance/<int:seance_id>/presence/', views.feuille_presence, name='feuille_presence'),
    path('presences/fiches/', views.liste_fiches_presence, name='liste_fiches_presence'),
    path('presences/fiches/creer/', views.creer_fiche_presence, name='creer_fiche_presence'),
    path('presences/fiches/<int:pk>/saisie/', views.saisie_grille_presence, name='saisie_grille_presence'),
    path('presences/fiches/<int:pk>/supprimer/', views.supprimer_fiche_presence, name='supprimer_fiche_presence'),
    path('presences/fiches/importer/', views.importer_fiche_presence, name='importer_fiche_presence'),
    path('presences/fiches/<int:pk>/publier/', views.publier_fiche_presence, name='publier_fiche_presence'),
    path('presences/discipline/salle/<int:salle_id>/', views.note_annuelle_discipline, name='note_annuelle_discipline'),
    path('presences/classe/<int:classe_id>/pdf/', views.exporter_liste_classe_presence_pdf, name='exporter_liste_classe_presence_pdf'),
    # Suivi & Émargement Hebdomadaire Présence Enseignants (Scolarité)
    path('presences/enseignants/', views.liste_fiches_presence_enseignant, name='liste_fiches_presence_enseignant'),
    path('presences/enseignants/creer/', views.creer_fiche_presence_enseignant, name='creer_fiche_presence_enseignant'),
    path('presences/enseignants/<int:pk>/saisie/', views.saisir_fiche_presence_enseignant, name='saisir_fiche_presence_enseignant'),
    path('presences/enseignants/<int:pk>/pdf/', views.exporter_fiche_presence_enseignant_pdf, name='exporter_fiche_presence_enseignant_pdf'),

    # Planning
    path('planning-professeur/', views.planning_professeur, name='planning_professeur'),
    
    # Apprenants & Certifications
    path('apprenants/registre/', views_apprenants.liste_apprenants_categories, name='liste_apprenants_categories'),
    path('apprenants/matieres/', views_apprenants.gestion_matieres_formation, name='gestion_matieres_formation'),
    path('apprenants/notes/', views_apprenants.saisir_notes_apprenants, name='saisir_notes_apprenants'),
    path('apprenants/supports/', views_apprenants.liste_supports_apprenant, name='liste_supports_apprenant'),

    path('apprenants/supports/ajouter/', views_apprenants.ajouter_support_apprenant, name='ajouter_support_apprenant'),
    path('apprenants/supports/<int:pk>/supprimer/', views_apprenants.supprimer_support_apprenant, name='supprimer_support_apprenant'),
    path('apprenants/emploi-du-temps/', views_apprenants.liste_emplois_du_temps_apprenant, name='liste_emplois_du_temps_apprenant'),
    path('apprenants/emploi-du-temps/creer/', views_apprenants.creer_emploi_du_temps_apprenant, name='creer_emploi_du_temps_apprenant'),
    path('apprenants/emploi-du-temps/<int:pk>/supprimer/', views_apprenants.supprimer_emploi_du_temps_apprenant, name='supprimer_emploi_du_temps_apprenant'),


    # Évaluation Anonyme des Enseignants par les Apprenants
    path('evaluations/', views_evaluations.liste_evaluations_etudiant, name='liste_evaluations_etudiant'),
    path('evaluations/cours/<int:cours_id>/', views_evaluations.evaluer_cours, name='evaluer_cours'),
    path('evaluations/synthese/', views_evaluations.synthese_evaluations_professeur, name='synthese_evaluations_professeur'),
    path('evaluations/synthese/<int:professeur_id>/', views_evaluations.synthese_evaluations_professeur, name='synthese_evaluations_professeur_detail'),
    path('evaluations/scolarite/', views_evaluations.gestion_evaluations_scolarite, name='gestion_evaluations_scolarite'),
    path('evaluations/campagne/<int:pk>/statut/<str:nouveau_statut>/', views_evaluations.changer_statut_campagne, name='changer_statut_campagne'),
]
