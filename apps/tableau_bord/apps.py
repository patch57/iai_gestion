from django.apps import AppConfig


class TableauBordConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tableau_bord'
    verbose_name = 'Tableau de Bord IAI-Cameroun'
    
    def ready(self):
        """
        Méthode appelée lorsque l'application est prête
        Permet d'importer les signaux et d'initialiser des données
        """
       #import apps.tableau_bord.signals  # Décommentez si vous avez des signaux