"""
URLs pour le tableau de bord
IAI-Cameroun - Centre de Douala
"""
from django.urls import path
from . import views

app_name = 'tableau_bord'

urlpatterns = [
    # Page principale
    path('', views.tableau_bord, name='tableau_bord'),
    path('accueil/', views.tableau_bord, name='accueil'),
    
    # Statistiques et rapports
    path('statistiques/', views.statistiques, name='statistiques'),
    path('statistiques/filieres/', views.statistiques_filieres, name='statistiques_filieres'),
    path('statistiques/paiements/', views.statistiques_paiements, name='statistiques_paiements'),
    path('statistiques/export/', views.exporter_statistiques, name='exporter_statistiques'),
    
    # Notifications
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/<int:pk>/lue/', views.marquer_notification_lue, name='marquer_notification_lue'),
    path('notifications/marquer-toutes-lues/', views.marquer_toutes_notifications_lues, name='marquer_toutes_lues'),
    path('notifications/supprimer/<int:pk>/', views.supprimer_notification, name='supprimer_notification'),
    
    # Tâches et rappels
    path('taches/', views.taches, name='taches'),
    path('taches/ajouter/', views.ajouter_tache, name='ajouter_tache'),
    path('taches/<int:pk>/modifier/', views.modifier_tache, name='modifier_tache'),
    path('taches/<int:pk>/supprimer/', views.supprimer_tache, name='supprimer_tache'),
    path('taches/<int:pk>/terminer/', views.terminer_tache, name='terminer_tache'),
    
    # Messages
    path('messages/', views.messages_view, name='messages'),
    path('messages/envoyer/', views.envoyer_message, name='envoyer_message'),
    path('messages/<int:pk>/', views.detail_message, name='detail_message'),
    path('messages/<int:pk>/repondre/', views.repondre_message, name='repondre_message'),
    path('messages/archiver/', views.archiver_messages, name='archiver_messages'),
    
    # Profil utilisateur
    path('profil/', views.profil, name='profil'),
    path('profil/modifier/', views.modifier_profil, name='modifier_profil'),
    path('profil/changer-mot-de-passe/', views.changer_mot_de_passe, name='changer_mot_de_passe'),
    
    # Calendrier et événements
    path('calendrier/', views.calendrier, name='calendrier'),
    path('calendrier/evenements/', views.liste_evenements, name='liste_evenements'),
    path('calendrier/evenements/ajouter/', views.ajouter_evenement, name='ajouter_evenement'),
    
    # Alertes et rappels
    path('alertes/', views.alertes, name='alertes'),
    path('alertes/<int:pk>/ignorer/', views.ignorer_alerte, name='ignorer_alerte'),
    
    # Export et impressions
    path('export/', views.export_dashboard, name='export_dashboard'),
    path('imprimer/', views.imprimer_dashboard, name='imprimer_dashboard'),
    path('geolocalisation/', views.geolocalisation, name='geolocalisation'),
    
    # API pour les graphiques (AJAX)
    path('api/donnees/', views.api_donnees_dashboard, name='api_donnees_dashboard'),
    path('api/notifications-non-lues/', views.api_notifications_non_lues, name='api_notifications_non_lues'),
    path('api/statistiques-rapides/', views.api_statistiques_rapides, name='api_statistiques_rapides'),
]

# URLs pour les vues basées sur les classes (si utilisées)
# from .views import (
#     TableauBordView, StatistiquesView, NotificationsView,
#     TachesListView, MessagesListView, ProfilView
# )
# 
# urlpatterns = [
#     path('', TableauBordView.as_view(), name='tableau_bord'),
#     path('statistiques/', StatistiquesView.as_view(), name='statistiques'),
#     path('notifications/', NotificationsView.as_view(), name='notifications'),
#     path('taches/', TachesListView.as_view(), name='taches'),
#     path('messages/', MessagesListView.as_view(), name='messages'),
#     path('profil/', ProfilView.as_view(), name='profil'),
# ]