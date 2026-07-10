# IAI-Gestion

Système de Gestion Universitaire pour l'IAI-Cameroun - Centre de Douala

## Description

IAI-Gestion est une application web complète et moderne développée avec Django pour la gestion de l'Institut Africain d'Informatique au Cameroun, Centre de Douala. Elle couvre tous les aspects de la gestion universitaire :

- **Gestion des Étudiants** : Inscriptions, dossiers, documents, suivi académique
- **Gestion des Professeurs** : Enseignants, départements, charge horaire
- **Gestion des Cours** : Matières, emplois du temps, salles, présences
- **Gestion des Notes** : Évaluations, bulletins, délibération
- **Gestion des Inscriptions** : Paiements, bourses, certificats
- **Tableau de Bord** : Statistiques, rapports, notifications

## Caractéristiques

- ✅ Interface moderne et ergonomique avec Tailwind CSS
- ✅ Design responsive (mobile, tablette, desktop)
- ✅ Système d'authentification et d'autorisation robuste
- ✅ Gestion des rôles (Administrateur, Secrétaire, Professeur, Étudiant)
- ✅ Tableaux de bord avec statistiques en temps réel
- ✅ Export des données (CSV, Excel, PDF)
- ✅ Génération de rapports et attestations
- ✅ Journal d'activités complet
- ✅ Notifications et messagerie interne

## Prérequis

- Python 3.10+
- pip
- virtualenv (recommandé)

## Installation

### 1. Cloner le projet

```bash
cd /mnt/okcomputer/output/iai_gestion
```

### 2. Créer un environnement virtuel

```bash
python -m venv venv
```

### 3. Activer l'environnement virtuel

**Windows:**
```bash
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 4. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 5. Créer la base de données

```bash
python manage.py migrate
```

### 6. Créer un superutilisateur

```bash
python manage.py createsuperuser
```

### 7. Charger les données initiales (optionnel)

```bash
python manage.py loaddata fixtures/initial_data.json
```

### 8. Lancer le serveur de développement

```bash
python manage.py runserver
```

L'application est accessible à l'adresse : http://127.0.0.1:8000/

## Structure du Projet

```
iai_gestion/
├── iai_gestion/          # Configuration principale
│   ├── settings.py       # Paramètres Django
│   ├── urls.py           # URLs principales
│   ├── wsgi.py           # Configuration WSGI
│   └── asgi.py           # Configuration ASGI
├── apps/                 # Applications Django
│   ├── etudiants/        # Gestion des étudiants
│   ├── professeurs/      # Gestion des professeurs
│   ├── cours/            # Gestion des cours
│   ├── notes/            # Gestion des notes
│   ├── inscriptions/     # Gestion des inscriptions
│   └── tableau_bord/     # Tableau de bord
├── templates/            # Templates HTML
├── static/               # Fichiers statiques (CSS, JS, images)
├── media/                # Fichiers uploadés
├── requirements.txt      # Dépendances Python
└── manage.py             # Script de gestion Django
```

## Modules

### Gestion des Étudiants

- Fiches étudiants complètes
- Documents (photos, actes de naissance, diplômes)
- Suivi académique
- Cartes étudiant
- Historique des modifications

### Gestion des Professeurs

- Fiches professeurs
- Départements
- Charge horaire
- Disponibilités
- Documents

### Gestion des Cours

- Matières et filières
- Emplois du temps
- Salles
- Séances de cours
- Feuilles de présence
- Ressources pédagogiques

### Gestion des Notes

- Types d'évaluation (CC, TP, Examen)
- Saisie des notes
- Validation et publication
- Bulletins semestriels
- Délibération du jury
- Recours sur notes

### Gestion des Inscriptions

- Inscriptions et réinscriptions
- Paiements (scolarité, inscription)
- Échéanciers
- Bourses
- Certificats de scolarité

### Tableau de Bord

- Statistiques en temps réel
- Graphiques et visualisations
- Activités récentes
- Notifications
- Tâches à effectuer
- Messagerie interne

## Rôles et Permissions

### Administrateur
- Accès complet à toutes les fonctionnalités
- Gestion des utilisateurs
- Configuration du système

### Secrétaire
- Gestion des étudiants et inscriptions
- Gestion des paiements
- Génération des attestations

### Professeur
- Saisie des notes
- Gestion des cours
- Consultation des emplois du temps

### Étudiant
- Consultation des notes
- Téléchargement des documents
- Messagerie

## Sécurité

- Authentification obligatoire
- Gestion des permissions par rôle
- Protection CSRF
- Validation des formulaires
- Journal d'activités
- Sauvegardes automatiques

## Technologies Utilisées

- **Backend** : Django 5.0, Python 3.10+
- **Frontend** : HTML5, Tailwind CSS, Font Awesome
- **Base de données** : SQLite (développement), PostgreSQL (production)
- **Autres** : Crispy Forms, Django Filter, ReportLab

## Déploiement en Production

### 1. Configurer la base de données PostgreSQL

```python
# iai_gestion/settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'iai_gestion',
        'USER': 'iai_user',
        'PASSWORD': 'votre_mot_de_passe',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### 2. Définir les variables d'environnement

```bash
export DEBUG=False
export SECRET_KEY="votre_cle_secrete"
export ALLOWED_HOSTS="votre-domaine.com"
```

### 3. Collecter les fichiers statiques

```bash
python manage.py collectstatic
```

### 4. Configurer Gunicorn

```bash
gunicorn iai_gestion.wsgi:application --bind 0.0.0.0:8000
```

### 5. Configurer Nginx (recommandé)

```nginx
server {
    listen 80;
    server_name votre-domaine.com;
    
    location /static/ {
        alias /chemin/vers/staticfiles/;
    }
    
    location /media/ {
        alias /chemin/vers/media/;
    }
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Maintenance

### Sauvegarde de la base de données

```bash
python manage.py dumpdata > backup.json
```

### Restauration de la base de données

```bash
python manage.py loaddata backup.json
```

### Mise à jour des dépendances

```bash
pip install -r requirements.txt --upgrade
```

## Support

Pour toute question ou problème, veuillez contacter :

- Email : support@iai-cameroun.com
- Téléphone : +237 233 42 00 00

## Licence

Ce projet est propriétaire de l'IAI-Cameroun - Centre de Douala.
Tous droits réservés.

## Auteurs

- Développé par l'équipe informatique de l'IAI-Cameroun
- Version : 1.0.0
- Date : 2024
