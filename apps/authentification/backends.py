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
        if not username or not password:
            return None
        
        username = username.strip()
        
        try:
            user = User.objects.filter(
                Q(matricule__iexact=username) |
                Q(email__iexact=username) |
                Q(username__iexact=username) |
                Q(profil_professeur__matricule__iexact=username)
            ).first()
        except Exception:
            return None
        
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
    
    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None