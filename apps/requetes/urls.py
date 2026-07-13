from django.urls import path
from . import views

app_name = 'requetes'

urlpatterns = [
    path('', views.liste_requetes, name='liste_requetes'),
    path('creer/', views.creer_requete, name='creer_requete'),
    path('<int:pk>/', views.detail_requete, name='detail_requete'),
    path('<int:pk>/repondre/', views.repondre_requete, name='repondre_requete'),
    path('<int:pk>/escalader/', views.escalader_requete, name='escalader_requete'),
    path('<int:pk>/renvoyer/', views.renvoyer_requete, name='renvoyer_requete'),
    path('export/csv/', views.export_requetes_csv, name='export_requetes_csv'),
    path('import/csv/', views.import_requetes_csv, name='import_requetes_csv'),
]
