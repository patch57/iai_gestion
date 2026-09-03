# Automatisation de l'Envoi des Rappels sous Windows

Ce guide explique comment automatiser l'envoi hebdomadaire des rappels d'échéances et de pénalités aux étudiants insolvables sous Windows, de manière totalement gratuite et robuste.

## Commande Manuelle
La commande de gestion Django créée pour effectuer les calculs et l'envoi d'e-mails est :
```bash
python manage.py envoyer_rappels_paiements
```

---

## Méthode 1 : Automatisation via le Planificateur de Tâches Windows (Recommandé)

Le **Planificateur de tâches Windows** est l'outil natif, gratuit et le plus performant pour exécuter des scripts périodiquement.

### Étape 1 : Créer le script de lancement automatique
Créez un fichier nommé `run_rappels.bat` à la racine de votre projet (`c:\iai_gestion\run_rappels.bat`) avec le contenu suivant :
```bat
@echo off
cd /d "c:\iai_gestion"
:: Activer l'environnement virtuel si vous en utilisez un (ex: .venv)
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)
:: Exécuter la commande Django
python manage.py envoyer_rappels_paiements >> logs\rappels_cron.log 2>&1
```

### Étape 2 : Planifier la tâche sous Windows
1. Ouvrez le **Planificateur de tâches** (recherchez "Planificateur de tâches" ou tapez `taskschd.msc` dans Exécuter).
2. Dans le panneau de droite, cliquez sur **Créer une tâche de base...**.
3. Donnez un nom (ex: `IAI_Rappels_Paiements`) et une description. Cliquez sur **Suivant**.
4. Déclencheur : Choisissez **Toutes les semaines**. Cliquez sur **Suivant**.
5. Paramétrez le jour et l'heure de lancement (ex: tous les lundis à 08:00). Cliquez sur **Suivant**.
6. Action : Choisissez **Démarrer un programme**. Cliquez sur **Suivant**.
7. Programme/script : Cliquez sur **Parcourir** et sélectionnez le fichier `run_rappels.bat` créé à l'étape 1.
8. Dans le champ **Commencer dans (facultatif)**, tapez le chemin du dossier : `c:\iai_gestion`.
9. Cliquez sur **Suivant** puis sur **Terminer**.

La tâche s'exécutera désormais de manière 100% autonome en tâche de fond.

---

## Méthode 2 : Enregistrement Automatique via PowerShell (Recommandé & Rapide)

Un script dédié [`register_task.ps1`](file:///c:/iai_gestion/register_task.ps1) est fourni à la racine du projet pour installer, tester ou désinstaller automatiquement la tâche planifiée sous Windows :

### 1. Enregistrer la tâche planifiée (exécute tous les lundis à 08h00)
Ouvrez PowerShell en administrateur à la racine du projet et lancez :
```powershell
.\register_task.ps1
```

### 2. Tester l'exécution immédiatement en mode manuel
```powershell
.\register_task.ps1 -RunNow
```

### 3. Désinstaller la tâche planifiée
```powershell
.\register_task.ps1 -Uninstall
```

