"""
Backend d'authentification personnalisé pour IAI-Cameroun
Permet la connexion avec matricule, email ou nom d'utilisateur
"""
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()


class MatriculeAuthBackend(ModelBackend):
    """
    Authentification par matricule, email ou nom d'utilisateur
    
    Ordre de recherche:
    1. Matricule (insensible à la casse)
    2. Email (insensible à la casse)
    3. Nom d'utilisateur
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        
        # Nettoyer l'identifiant
        username = username.strip()
        
        # Rechercher l'utilisateur
        try:
            user = User.objects.get(
                Q(matricule=username.upper()) |
                Q(email=username.lower()) |
                Q(username=username)
            )
        except User.DoesNotExist:
            # Essayer le backend par défaut
            return super().authenticate(request, username, password, **kwargs)
        
        # Vérifier le mot de passe et l'état du compte
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
    
    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None