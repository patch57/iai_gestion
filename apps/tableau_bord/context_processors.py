"""
Context processors pour le tableau de bord
IAI-Cameroun - Centre de Douala
"""
from apps.etudiants.models import AnneeAcademique
from django.conf import settings
from datetime import datetime


def site_config(request):
    """Variables globales pour tout le site - Configuration de l'établissement"""
    return {
        # Informations de l'établissement
        'SITE_NAME': 'IAI-Cameroun',
        'SITE_CENTRE': 'Centre de Douala',
        'SITE_FULL_NAME': 'Institut Africain d\'Informatique - Cameroun',
        'SITE_ADDRESS': 'Bonanjo, Douala, Cameroun',
        'CONTACT_EMAIL': 'contact@iai-cameroun.com',
        'CONTACT_TEL': '+237 233 42 00 00',
        'CONTACT_FAX': '+237 233 42 00 01',
        'VERSION': '2.0',
        'COPYRIGHT_YEAR': datetime.now().year,
        
        # URLs importantes
        'SITE_URL': getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000'),
        'LOGIN_URL': getattr(settings, 'LOGIN_URL', '/login/'),
        'LOGOUT_URL': '/logout/',
        
        # Configuration IAI
        'MONTANT_PREINSCRIPTION': 84000,
        'MONTANT_TOTAL_ANNUEL': 500000,

        'DEVISE': 'FCFA',
    }


def annee_academique(request):
    """Année académique active - disponible partout"""
    from apps.inscriptions.utils import get_current_academic_year_code
    from datetime import date
    default_annee = get_current_academic_year_code()
    default_debut, default_fin = default_annee.split('-')
    
    try:
        annee_active = AnneeAcademique.objects.filter(est_active=True).first()
        
        # Si aucune année n'est active, ou si la date système courante est en avance
        # par rapport à l'année active (obsolète)
        if not annee_active or annee_active.code != default_annee:
            # Créer/Activer l'année par défaut dans etudiants
            annee_active, created = AnneeAcademique.objects.get_or_create(
                code=default_annee,
                defaults={
                    'date_debut': date(int(default_debut), 9, 1),
                    'date_fin': date(int(default_fin), 8, 31),
                    'est_active': True
                }
            )
            if not created and not annee_active.est_active:
                annee_active.est_active = True
                annee_active.save()
            
            # Également synchroniser dans inscriptions
            from apps.inscriptions.models import AnneeAcademique as AnneeAcademiqueInscr
            annee_inscr, created_inscr = AnneeAcademiqueInscr.objects.get_or_create(
                code=default_annee,
                defaults={
                    'date_debut': date(int(default_debut), 9, 1),
                    'date_fin': date(int(default_fin), 8, 31),
                    'est_actuelle': True,
                    'est_ouverte_inscription': True
                }
            )
            if not created_inscr and not annee_inscr.est_actuelle:
                annee_inscr.est_actuelle = True
                annee_inscr.save()

        if annee_active and annee_active.code:
            annee_code = annee_active.code
            # Extraire les années pour affichage
            if '-' in annee_code:
                debut, fin = annee_code.split('-')
                annee_debut = debut
                annee_fin = fin
            else:
                annee_debut = annee_code[:4]
                annee_fin = str(int(annee_debut) + 1)
        else:
            annee_code = default_annee
            annee_debut = default_debut
            annee_fin = default_fin
            annee_active = None
            
        return {
            'annee_academique': annee_code,
            'annee_academique_debut': annee_debut,
            'annee_academique_fin': annee_fin,
            'annee_active': annee_active,
        }
    except Exception:
        return {
            'annee_academique': default_annee,
            'annee_academique_debut': default_debut,
            'annee_academique_fin': default_fin,
            'annee_active': None,
        }


def notifications_non_lues(request):
    """Nombre de notifications pour l'utilisateur connecté"""
    if request.user.is_authenticated and not request.user.is_anonymous:
        try:
            from apps.tableau_bord.models import Notification
            count = Notification.objects.filter(
                utilisateur=request.user, 
                est_lue=False
            ).count()
            return {
                'notifications_count': count,
                'has_notifications': count > 0,
            }
        except Exception:
            return {'notifications_count': 0, 'has_notifications': False}
    return {'notifications_count': 0, 'has_notifications': False}


def taches_en_cours(request):
    """Nombre de tâches en cours pour l'utilisateur connecté"""
    if request.user.is_authenticated and not request.user.is_anonymous:
        try:
            from apps.tableau_bord.models import Tache
            count = Tache.objects.filter(
                assignee_a=request.user,
                statut__in=['A_FAIRE', 'EN_COURS']
            ).count()
            return {
                'taches_en_cours_count': count,
                'has_taches_en_cours': count > 0,
            }
        except Exception:
            return {'taches_en_cours_count': 0, 'has_taches_en_cours': False}
    return {'taches_en_cours_count': 0, 'has_taches_en_cours': False}


def alertes_importantes(request):
    """Alertes importantes pour l'utilisateur connecté"""
    alertes = []
    
    if request.user.is_authenticated and not request.user.is_anonymous:
        try:
            # Alertes paiements en attente (pour les admins financiers)
            if hasattr(request.user, 'type_utilisateur') and request.user.type_utilisateur == 'ADMIN_FINANCIER':
                from apps.paiements.models import RecuPaiement
                recus_attente = RecuPaiement.objects.filter(statut='EN_ATTENTE').count()
                if recus_attente > 0:
                    alertes.append({
                        'type': 'warning',
                        'message': f'{recus_attente} reçu(s) en attente de vérification',
                        'icone': 'receipt',
                        'lien': '/paiements/',
                    })
            
            # Alertes échéances de paiement (pour tous)
            from apps.paiements.models import TranchePaiement
            from datetime import timedelta
            echeances = TranchePaiement.objects.filter(
                date_limite__gte=datetime.now().date(),
                date_limite__lte=datetime.now().date() + timedelta(days=7),
                est_actif=True
            ).count()
            if echeances > 0:
                alertes.append({
                    'type': 'info',
                    'message': f'{echeances} échéance(s) de paiement dans les 7 prochains jours',
                    'icone': 'calendar',
                    'lien': '/paiements/tranches/',
                })
                
        except Exception:
            pass
    
    return {
        'alertes_importantes': alertes,
        'has_alertes': len(alertes) > 0,
    }


def user_info(request):
    """Informations supplémentaires sur l'utilisateur connecté"""
    if request.user.is_authenticated and not request.user.is_anonymous:
        return {
            'user_nom_complet': request.user.get_full_name() or request.user.username,
            'user_initiales': request.user.get_initiales() if hasattr(request.user, 'get_initiales') else request.user.username[:2].upper(),
            'user_est_etudiant': request.user.est_etudiant() if hasattr(request.user, 'est_etudiant') else False,
            'user_est_professeur': request.user.est_professeur() if hasattr(request.user, 'est_professeur') else False,
            'user_est_administrateur': request.user.est_administrateur() if hasattr(request.user, 'est_administrateur') else False,
            'user_completion': request.user.get_profil_completion() if hasattr(request.user, 'get_profil_completion') else 0,
        }
    return {
        'user_nom_complet': '',
        'user_initiales': '?',
        'user_est_etudiant': False,
        'user_est_professeur': False,
        'user_est_administrateur': False,
        'user_completion': 0,
    }


def menu_links(request):
    """Liens du menu principal - centralisé"""
    menu = [
        {'nom': 'Tableau de bord', 'icone': 'tachometer-alt', 'url': '/tableau-de-bord/', 'active': 'tableau_de_bord'},
        {'nom': 'Étudiants', 'icone': 'user-graduate', 'url': '/etudiants/', 'active': 'etudiants'},
        {'nom': 'Professeurs', 'icone': 'chalkboard-teacher', 'url': '/professeurs/', 'active': 'professeurs'},
        {'nom': 'Cours', 'icone': 'book', 'url': '/cours/', 'active': 'cours'},
        {'nom': 'Notes & Évaluations', 'icone': 'chart-line', 'url': '/notes/evaluations/', 'active': 'notes'},
        {'nom': 'Inscriptions & Paiements', 'icone': 'file-signature', 'url': '/inscriptions/', 'active': 'inscriptions'},
        {'nom': 'Statistiques', 'icone': 'chart-pie', 'url': '/tableau-de-bord/statistiques/', 'active': 'statistiques'},
    ]
    
    # Menu pour les admins
    if request.user.is_authenticated and request.user.is_staff:
        menu.append({'nom': 'Administration', 'icone': 'cog', 'url': '/admin/', 'active': 'admin'})
    
    return {'menu_principal': menu}


def couleurs_theme(request):
    """Couleurs du thème - pour une personnalisation facile"""
    return {
        'primary_color': '#10B981',
        'secondary_color': '#F59E0B',
        'danger_color': '#EF4444',
        'warning_color': '#F59E0B',
        'info_color': '#3B82F6',
        'success_color': '#10B981',
        'gradient_primary': 'linear-gradient(135deg, #10B981 0%, #059669 100%)',
        'gradient_secondary': 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)',
    }