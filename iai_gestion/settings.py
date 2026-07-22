"""
Configuration Django pour IAI-Gestion
IAI-Cameroun - Centre de Douala
"""

from pathlib import Path
import os
from django.contrib.messages import constants as messages
from decouple import config, Csv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-iai-cameroun-douala-2024-secure-key-for-development')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*', cast=Csv())

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Applications tierces
    'crispy_forms',
    'crispy_tailwind',
    'django_filters',
    'django_cleanup.apps.CleanupConfig',
    # 'leaflet',  # DÉSACTIVÉ - Nécessite GDAL, à activer plus tard
    
    # Applications locales
    'apps.authentification',
    'apps.etudiants',
    'apps.paiements',
    'apps.tableau_bord',
    'apps.notes',  # Activé pour la gestion des notes
    'apps.inscriptions',
    'apps.professeurs',
    'apps.cours',
    'apps.requetes',
]

# Modèle utilisateur personnalisé
AUTH_USER_MODEL = 'authentification.Utilisateur'

# ========== BACKEND D'AUTHENTIFICATION PERSONNALISÉ ==========
# Permet la connexion avec matricule, email ou nom d'utilisateur
AUTHENTICATION_BACKENDS = [
    'apps.authentification.backends.MatriculeAuthBackend',
    'django.contrib.auth.backends.ModelBackend',  # Garder le backend par défaut
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'iai_gestion.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # Context processors personnalisés
                'apps.tableau_bord.context_processors.site_config',
                'apps.tableau_bord.context_processors.annee_academique',
                'apps.tableau_bord.context_processors.notifications_non_lues',
                'apps.tableau_bord.context_processors.user_info',
            ],
        },
    },
]

WSGI_APPLICATION = 'iai_gestion.wsgi.application'

# Database
DATABASE_ENGINE = config('DATABASE_ENGINE', default='django.db.backends.sqlite3')
if DATABASE_ENGINE == 'django.db.backends.sqlite3':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / config('DATABASE_NAME', default='db.sqlite3'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': DATABASE_ENGINE,
            'NAME': config('DATABASE_NAME', default='iai_gestion'),
            'USER': config('DATABASE_USER', default='postgres'),
            'PASSWORD': config('DATABASE_PASSWORD', default='postgres'),
            'HOST': config('DATABASE_HOST', default='db'),
            'PORT': config('DATABASE_PORT', default='5432'),
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Douala'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Crispy Forms Configuration
CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"

# Login Configuration
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/tableau-de-bord/'
LOGOUT_REDIRECT_URL = '/login/'

# Session Configuration
SESSION_COOKIE_AGE = 3600  # 1 heure
SESSION_SAVE_EVERY_REQUEST = True

# ========== EMAIL CONFIGURATION ==========
# Lecture depuis le .env — bascule automatique console/SMTP
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    # Mode production : envoi réel via Gmail SMTP (avec support du contournement SSL en local)
    EMAIL_BACKEND = 'apps.paiements.backends.UnverifiedEmailBackend'
    EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
    DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default=f'IAI-Cameroun <{EMAIL_HOST_USER}>')
    EMAIL_BYPASS_SSL = config('EMAIL_BYPASS_SSL', default=True, cast=bool)  # Activé par défaut en local
else:
    # Mode développement : emails affichés dans le terminal
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    DEFAULT_FROM_EMAIL = 'IAI-Cameroun <noreply@iai-cameroun.com>'
    EMAIL_BYPASS_SSL = False

EMAIL_SUBJECT_PREFIX = '[IAI-Cameroun] '

# URL du site pour les emails
SITE_URL = config('SITE_BASE_URL', default='http://127.0.0.1:8000')

# Admin email pour les notifications
ADMIN_EMAIL = config('ADMIN_EMAIL', default='admin@iai-cameroun.com')

# ========== FIN EMAIL CONFIGURATION ==========

# ========== GEOLOCALISATION CONFIGURATION ==========
# Configuration pour la carte (sans leaflet, utilisation de CDN)
IAI_COORDONNEES = {
    'LATITUDE': 4.051056,
    'LONGITUDE': 9.767865,
    'ADRESSE_COMPLETE': 'PK9, Douala - Station MRS, avant boulangerie Saker',
    'INDICATIONS': 'Venant du marché Ndokoti, juste avant la boulangerie Saker, au niveau de la station MRS',
}

# ========== ANONYMAT CONFIGURATION ==========
ANONYMAT_CONFIG = {
    'DUREE_VALIDITE_JOURS': 365,  # 1 an
    'PSEUDO_PREFIX': 'ETU',
    'PSEUDO_LENGTH': 8,
    'RENOUVELLEMENT_AUTO': False,
    'NOTIFICATION_ADMIN': True,
}

# Messages Configuration
MESSAGE_TAGS = {
    messages.DEBUG: 'bg-gray-100 text-gray-800',
    messages.INFO: 'bg-blue-100 text-blue-800',
    messages.SUCCESS: 'bg-green-100 text-green-800',
    messages.WARNING: 'bg-yellow-100 text-yellow-800',
    messages.ERROR: 'bg-red-100 text-red-800',
}

# Configuration IAI
IAI_CONFIG = {
    'NOM_ETABLISSEMENT': 'IAI-Cameroun',
    'CENTRE': 'Douala',
    'ADRESSE': 'PK9, Douala, Cameroun',
    'TELEPHONE': '+237 242 58 79 52',
    'EMAIL': 'contact@iai-cameroun.com',
    'ANNEE_ACADEMIQUE_DEFAUT': '2025-2026',
}

# Configuration des formats de matricules
MATRICULE_CONFIG = {
    'ETUDIANT_PATTERN': r'^(GL|SR)\.CMR\.D014\.\d{4}[A-Z]$',
    'ADMIN_PATTERN': r'^[A-Z]{3}\.CMR\.D\d{3}\.\d{4}\.[A-Z]$',
    'PROFESSEUR_PATTERN': r'^[A-Z]{3}\.CMR\.D\d{3}\.\d{4}\.[A-Z]$',
    'EXEMPLE_ETUDIANT': 'GL.CMR.D014.2324A',
    'EXEMPLE_ADMIN': 'CSE.CMR.D123.2026.A',
    'EXEMPLE_PROFESSEUR': 'ENS.CMR.D456.2026.B',
}

# Configuration des tranches de paiement
PAIEMENT_CONFIG = {
    'TRANCHES': {
        1: {'nom': 'Pré-inscription', 'montant': 84000},

        2: {'nom': '1ère Tranche', 'montant': 150000},
        3: {'nom': '2ème Tranche', 'montant': 150000},
        4: {'nom': '3ème Tranche', 'montant': 150000},
    },
    'DEVISE': 'FCFA',
    'TOTAL_ANNUEL': 500000,
}

# Configuration des filières
FILIERES_CONFIG = {
    'GL': {'nom': 'Génie Logiciel', 'code': 'GL', 'duree_ans': 2},
    'SR': {'nom': 'Systèmes et Réseaux', 'code': 'SR', 'duree_ans': 2},
}

# Configuration des niveaux
NIVEAUX_CONFIG = {
    1: {'nom': 'Niveau 1', 'code': 'N1'},
    2: {'nom': 'Niveau 2', 'code': 'N2', 'est_diplomant': True, 'diplome': 'DTS'},
}

# Configuration des règles de baccalauréat
BACCALAUREAT_CONFIG = {
    'SERIES_LITTERAIRES': ['A', 'A1', 'A2', 'A3', 'A4', 'B', 'G'],
    'SERIES_SCIENTIFIQUES': ['C', 'D', 'E', 'F', 'TI', 'TC'],
    'FILIERE_GL_AUTORISEE': ['A', 'A1', 'A2', 'A3', 'A4', 'B', 'C', 'D', 'E', 'F', 'G', 'TI', 'TC'],
    'FILIERE_SR_AUTORISEE': ['C', 'D', 'E', 'F', 'TI', 'TC'],
    'REGLE_ORIENTATION': "Les titulaires d'un baccalauréat série A ne peuvent être orientés qu'en Génie Logiciel (GL)",
}

# Configuration de l'IA pour la vérification des reçus
IA_VERIFICATION_CONFIG = {
    'SEUIL_CONFIANCE_AUTO_VALIDATION': 0.95,
    'SEUIL_CONFIANCE_ATTENTION': 0.70,
    'SEUIL_CONFIANCE_REJET_AUTO': 0.30,
    'ACTIVER_OCR': True,
}

# Configuration des permissions par défaut
PERMISSIONS_CONFIG = {
    'ETUDIANT': [
        'peut_voir_notes',
        'peut_voir_emploi_du_temps',
        'peut_televerser_recus',
        'peut_voir_paiements',
    ],
    'PROFESSEUR': [
        'peut_saisir_notes',
        'peut_voir_liste_etudiants',
        'peut_voir_emploi_du_temps',
    ],
    'ADMIN_PEDAGOGIQUE': [
        'peut_gerer_etudiants',
        'peut_gerer_cours',
        'peut_gerer_notes',
        'peut_creer_classes',
    ],
    'ADMIN_FINANCIER': [
        'peut_verifier_recus',
        'peut_gerer_tranches',
        'peut_exporter_paiements',
    ],
    'ADMIN_SYSTEME': [
        'peut_gerer_utilisateurs',
        'peut_gerer_permissions',
        'peut_voir_tous',
    ],
}

# Configuration des notifications
NOTIFICATIONS_CONFIG = {
    'ACTIVER_EMAILS': True,
    'ACTIVER_SMS': False,
    'EMAIL_EXPEDITEUR': 'noreply@iai-cameroun.com',
    'NOTIFICATIONS_PAIEMENT': {
        'RECU_TELEVERSE': True,
        'RECU_VALIDE': True,
        'RECU_REJETE': True,
        'ECHEANCE_PROCHAIN': 7,
    },
    'NOTIFICATIONS_ACADEMIQUES': {
        'INSCRIPTION_VALIDEE': True,
        'CHANGEMENT_CLASSE': True,
        'NOTE_PUBLIEE': True,
    },
}

# Configuration du cache
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs/iai_gestion.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# Créer le dossier logs s'il n'existe pas
os.makedirs(BASE_DIR / 'logs', exist_ok=True)

# ========== Configuration CinetPay (Paiement Mobile Money) ==========
CINETPAY_API_KEY = config('CINETPAY_API_KEY', default='12912847765bcaborz')
CINETPAY_SITE_ID = config('CINETPAY_SITE_ID', default='445160')
CINETPAY_SECRET_KEY = config('CINETPAY_SECRET_KEY', default='sandbox_secret_key')
CINETPAY_MODE = config('CINETPAY_MODE', default='SANDBOX')
SITE_BASE_URL = config('SITE_BASE_URL', default='http://127.0.0.1:8000')

CINETPAY_BASE_URL = 'https://api-checkout.cinetpay.com'
CINETPAY_PAYMENT_URL = f'{CINETPAY_BASE_URL}/v2/payment'
CINETPAY_CHECK_URL = f'{CINETPAY_BASE_URL}/v2/payment/check'