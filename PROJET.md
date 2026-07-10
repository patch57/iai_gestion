# IAI-Gestion - Résumé du Projet

## Vue d'ensemble

**IAI-Gestion** est une application web complète de gestion universitaire développée pour l'**IAI-Cameroun - Centre de Douala**. Elle est construite avec le framework Django et utilise une interface moderne avec Tailwind CSS.

## Architecture du Projet

```
iai_gestion/
├── iai_gestion/              # Configuration Django
│   ├── settings.py           # Paramètres
│   ├── urls.py               # URLs principales
│   ├── wsgi.py               # WSGI
│   └── asgi.py               # ASGI
│
├── apps/                     # Applications métier
│   ├── etudiants/            # Gestion des étudiants
│   │   ├── models.py         # 4 modèles (Filiere, Etudiant, DocumentEtudiant, HistoriqueEtudiant)
│   │   ├── views.py          # 10 vues
│   │   ├── urls.py           # 8 URLs
│   │   ├── forms.py          # 3 formulaires
│   │   └── admin.py          # Configuration admin
│   │
│   ├── professeurs/          # Gestion des professeurs
│   │   ├── models.py         # 5 modèles
│   │   ├── views.py          # 8 vues
│   │   ├── urls.py           # 7 URLs
│   │   ├── forms.py          # 3 formulaires
│   │   └── admin.py
│   │
│   ├── cours/                # Gestion des cours
│   │   ├── models.py         # 8 modèles
│   │   ├── views.py          # 10 vues
│   │   ├── urls.py           # 10 URLs
│   │   ├── forms.py          # 5 formulaires
│   │   └── admin.py
│   │
│   ├── notes/                # Gestion des notes
│   │   ├── models.py         # 7 modèles
│   │   ├── views.py          # 10 vues
│   │   ├── urls.py           # 10 URLs
│   │   ├── forms.py          # 4 formulaires
│   │   └── admin.py
│   │
│   ├── inscriptions/         # Gestion des inscriptions
│   │   ├── models.py         # 7 modèles
│   │   ├── views.py          # 10 vues
│   │   ├── urls.py           # 10 URLs
│   │   ├── forms.py          # 5 formulaires
│   │   └── admin.py
│   │
│   └── tableau_bord/         # Tableau de bord
│       ├── models.py         # 7 modèles
│       ├── views.py          # 7 vues
│       ├── urls.py           # 7 URLs
│       └── admin.py
│
├── templates/                # Templates HTML
│   ├── base.html             # Template de base
│   ├── base/
│   │   ├── login.html        # Page de connexion
│   │   └── accueil.html      # Page d'accueil publique
│   ├── tableau_bord/
│   │   └── dashboard.html    # Tableau de bord
│   ├── etudiants/
│   │   ├── liste.html        # Liste des étudiants
│   │   └── detail.html       # Détail étudiant
│   └── ...
│
├── fixtures/                 # Données initiales
│   └── initial_data.json     # Filières, matières, etc.
│
├── requirements.txt          # Dépendances
├── README.md                 # Documentation
├── INSTALL.md                # Guide d'installation
└── manage.py                 # Script Django
```

## Modèles de Données (38 modèles au total)

### Étudiants (4 modèles)
- **Filière** : SR, GL, SI, DS, IM
- **Etudiant** : Informations complètes (personnelles, académiques, contact)
- **DocumentEtudiant** : Photos, actes, diplômes
- **HistoriqueEtudiant** : Journal des modifications

### Professeurs (5 modèles)
- **Departement** : INFO, MATH, etc.
- **Professeur** : Informations professionnelles et contractuelles
- **ChargeHoraire** : Suivi des heures et paiements
- **DocumentProfesseur** : CV, diplômes, contrats
- **DisponibiliteProfesseur** : Créneaux disponibles

### Cours (8 modèles)
- **Salle** : Cours, TP, laboratoires
- **Matiere** : Programme détaillé
- **Cours** : Assignation professeur-filière
- **SeanceCours** : Séances individuelles
- **InscriptionCours** : Inscription aux cours
- **Presence** : Feuilles de présence
- **RessourceCours** : Supports pédagogiques
- **EmploiDuTemps** : Planning par filière

### Notes (7 modèles)
- **TypeEvaluation** : CC, TP, Examen
- **Evaluation** : Examens et contrôles
- **Note** : Notes des étudiants
- **Bulletin** : Bulletins semestriels
- **DetailBulletin** : Notes par matière
- **Deliberation** : Séances du jury
- **RecoursNote** : Recours sur notes

### Inscriptions (7 modèles)
- **AnneeAcademique** : Configuration annuelle
- **Inscription** : Inscriptions et réinscriptions
- **Paiement** : Suivi des paiements
- **Echeancier** : Échéanciers de paiement
- **Bourse** : Bourses d'études
- **CertificatScolarite** : Attestations
- **DocumentInscription** : Documents requis

### Tableau de Bord (7 modèles)
- **Notification** : Alertes utilisateurs
- **Activite** : Journal système
- **Configuration** : Paramètres
- **Rapport** : Rapports générés
- **Statistique** : Données statistiques
- **Message** : Messagerie interne
- **Tache** : Gestion des tâches

## Fonctionnalités Principales

### 1. Gestion des Étudiants
- ✅ CRUD complet
- ✅ Recherche et filtrage avancés
- ✅ Export CSV
- ✅ Carte étudiant
- ✅ Documents associés
- ✅ Historique des modifications

### 2. Gestion des Professeurs
- ✅ Fiches complètes
- ✅ Charge horaire
- ✅ Disponibilités
- ✅ Départements
- ✅ Export des données

### 3. Gestion des Cours
- ✅ Matières et filières
- ✅ Emplois du temps
- ✅ Salles et ressources
- ✅ Feuilles de présence
- ✅ Ressources pédagogiques

### 4. Gestion des Notes
- ✅ Types d'évaluation
- ✅ Saisie des notes
- ✅ Validation et publication
- ✅ Bulletins semestriels
- ✅ Délibération du jury
- ✅ Export des relevés

### 5. Gestion des Inscriptions
- ✅ Inscriptions/Réinscriptions
- ✅ Paiements multiples
- ✅ Échéanciers
- ✅ Bourses
- ✅ Certificats

### 6. Tableau de Bord
- ✅ Statistiques en temps réel
- ✅ Graphiques visuels
- ✅ Activités récentes
- ✅ Notifications
- ✅ Tâches
- ✅ Messagerie

## Sécurité

- 🔐 Authentification obligatoire
- 🔐 Gestion des permissions par rôle
- 🔐 Protection CSRF
- 🔐 Validation des formulaires
- 🔐 Journal d'activités complet

## Interface Utilisateur

- 🎨 Design moderne avec Tailwind CSS
- 🎨 Interface responsive (mobile, tablette, desktop)
- 🎨 Navigation intuitive
- 🎨 Tableaux de bord interactifs
- 🎨 Thème professionnel

## Technologies

| Composant | Technologie |
|-----------|-------------|
| Backend | Django 5.0 |
| Langage | Python 3.10+ |
| Frontend | HTML5, Tailwind CSS |
| Icons | Font Awesome 6 |
| Forms | Django Crispy Forms |
| Database | SQLite (dev), PostgreSQL (prod) |

## Installation Rapide

```bash
# 1. Installer les dépendances
pip install -r requirements.txt

# 2. Créer la base de données
python manage.py migrate

# 3. Créer un administrateur
python manage.py createsuperuser

# 4. Charger les données initiales (optionnel)
python manage.py loaddata fixtures/initial_data.json

# 5. Lancer le serveur
python manage.py runserver
```

## Accès

- **Application** : http://127.0.0.1:8000/
- **Administration** : http://127.0.0.1:8000/admin/

## Statistiques du Code

- **Fichiers Python** : 30+
- **Fichiers HTML** : 10+
- **Modèles** : 38
- **Vues** : 55+
- **URLs** : 52
- **Formulaires** : 20+
- **Lignes de code** : 5000+

## Équipe de Développement

**IAI-Cameroun - Centre de Douala**
- Direction Informatique
- Année 2024

## Licence

Propriété de l'IAI-Cameroun - Centre de Douala
Tous droits réservés © 2024
