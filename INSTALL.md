# Guide d'Installation IAI-Gestion

## Installation Rapide

### Étape 1 : Installer Python

Assurez-vous d'avoir Python 3.10 ou supérieur installé :

```bash
python --version
```

### Étape 2 : Installer les dépendances

```bash
pip install django pillow django-crispy-forms crispy-tailwind django-filter
```

### Étape 3 : Initialiser la base de données

```bash
cd iai_gestion
python manage.py migrate
```

### Étape 4 : Créer un administrateur

```bash
python manage.py createsuperuser
```

Suivez les instructions pour créer votre compte administrateur.

### Étape 5 : Lancer l'application

```bash
python manage.py runserver
```

L'application est accessible à : **http://127.0.0.1:8000/**

## Identifiants par défaut

Après création du superutilisateur, connectez-vous avec :
- URL : http://127.0.0.1:8000/login/
- Nom d'utilisateur : (celui que vous avez créé)
- Mot de passe : (celui que vous avez défini)

## Structure des modules

### 1. Tableau de Bord
- Statistiques globales
- Activités récentes
- Notifications
- Tâches

### 2. Gestion des Étudiants
- Liste des étudiants
- Fiches détaillées
- Documents
- Cartes étudiant

### 3. Gestion des Professeurs
- Liste des professeurs
- Départements
- Charge horaire

### 4. Gestion des Cours
- Matières
- Emplois du temps
- Salles
- Présences

### 5. Gestion des Notes
- Évaluations
- Saisie des notes
- Bulletins
- Délibération

### 6. Gestion des Inscriptions
- Inscriptions
- Paiements
- Bourses
- Certificats

## Configuration avancée

### Changer l'année académique

Modifiez dans `iai_gestion/settings.py` :

```python
IAI_CONFIG = {
    'ANNEE_ACADEMIQUE_DEFAUT': '2024-2025',
}
```

### Configurer l'envoi d'emails

Dans `iai_gestion/settings.py` :

```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'votre-email@gmail.com'
EMAIL_HOST_PASSWORD = 'votre-mot-de-passe'
```

## Dépannage

### Erreur "No module named 'django'"

```bash
pip install django
```

### Erreur de migration

```bash
python manage.py makemigrations
python manage.py migrate
```

### Réinitialiser la base de données

```bash
rm db.sqlite3
python manage.py migrate
python manage.py createsuperuser
```

## Support

Pour toute assistance, contactez :
- Email : support@iai-cameroun.com
- Téléphone : +237 233 42 00 00
