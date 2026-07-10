"""
URLs pour la gestion des notes
IAI-Cameroun - Centre de Douala
"""
from django.urls import path
from . import views

app_name = 'notes'

urlpatterns = [
    # ========== ÉVALUATIONS ==========
    path('evaluations/', views.liste_evaluations, name='liste_evaluations'),
    path('evaluations/ajouter/', views.ajouter_evaluation, name='ajouter_evaluation'),
    path('evaluations/<int:pk>/', views.detail_evaluation, name='detail_evaluation'),
    path('evaluations/<int:pk>/modifier/', views.modifier_evaluation, name='modifier_evaluation'),
    path('evaluations/<int:pk>/supprimer/', views.supprimer_evaluation, name='supprimer_evaluation'),
    path('evaluations/<int:evaluation_id>/saisie/', views.saisie_notes, name='saisie_notes'),
    path('evaluations/<int:evaluation_id>/valider/', views.valider_notes, name='valider_notes'),
    path('evaluations/<int:evaluation_id>/exporter/', views.exporter_notes_evaluation, name='exporter_notes_evaluation'),
    
    # ========== ANONYMAT ==========
    path('evaluations/<int:evaluation_id>/activer-anonymat/', views.activer_anonymat, name='activer_anonymat'),
    path('evaluations/<int:evaluation_id>/saisie-anonyme/', views.saisie_notes_anonymes, name='saisie_notes_anonymes'),
    path('evaluations/<int:evaluation_id>/reveler-identites/', views.reveler_identites, name='reveler_identites'),
    
    # ========== BULLETINS ==========
    path('bulletins/', views.liste_bulletins, name='liste_bulletins'),
    path('bulletins/<int:pk>/', views.detail_bulletin, name='detail_bulletin'),
    path('bulletins/generer/', views.generer_bulletins, name='generer_bulletins'),
    path('bulletins/<int:bulletin_id>/exporter/', views.exporter_releve, name='exporter_releve'),
    
    # ========== DÉLIBÉRATION ==========
    path('deliberation/', views.deliberation, name='deliberation'),
    path('deliberation/valider/', views.valider_deliberation, name='valider_deliberation'),
    
    # ========== RECOURS ==========
    path('evaluations/<int:evaluation_id>/recours/', views.demander_recours, name='demander_recours'),
    # À implémenter ultérieurement
    # path('recours/liste/', views.liste_recours, name='liste_recours'),
    # path('recours/<int:pk>/traiter/', views.traiter_recours, name='traiter_recours'),
    
    # ========== ÉTUDIANT ==========
    path('mes-notes/', views.mes_notes, name='mes_notes'),
    # À implémenter ultérieurement
    # path('mon-bulletin/', views.mon_bulletin, name='mon_bulletin'),
    
    # ========== GÉO-LOCALISATION ==========
    path('carte-campus/', views.carte_campus, name='carte_campus'),
    path('itineraire/', views.itineraire, name='itineraire'),
    
    # ========== STATISTIQUES ==========
    path('statistiques/', views.statistiques_notes, name='statistiques_notes'),
    # À implémenter ultérieurement
    # path('statistiques/filieres/', views.statistiques_par_filiere, name='statistiques_par_filiere'),
    # path('statistiques/evaluations/', views.statistiques_evaluations, name='statistiques_evaluations'),
    
    # ========== API (AJAX) ==========
    path('api/evaluation/<int:evaluation_id>/stats/', views.api_stats_evaluation, name='api_stats_evaluation'),
    # À implémenter ultérieurement
    # path('api/etudiant/<int:etudiant_id>/notes/', views.api_notes_etudiant, name='api_notes_etudiant'),
    # path('api/filiere/<int:filiere_id>/moyennes/', views.api_moyennes_filiere, name='api_moyennes_filiere'),
]