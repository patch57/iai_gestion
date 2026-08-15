from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect

def role_required(*allowed_roles):
    """
    Décorateur restreignant l'accès d'une vue aux utilisateurs possédant
    au moins l'un des rôles spécifiés. Les superutilisateurs (is_superuser=True) ont un accès universel.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
                
            user_role = getattr(request.user, 'type_utilisateur', None)
            
            if user_role in allowed_roles:
                return view_func(request, *args, **kwargs)
                
            messages.error(request, "Accès refusé. Privilèges insuffisants pour cette action.")
            return redirect('tableau_bord:tableau_bord')
        return _wrapped_view
    return decorator

roles_required = role_required
