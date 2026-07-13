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

## Méthode 2 : Planification par script PowerShell (Alternative)

Si vous préférez exécuter et gérer l'automatisation en tant que service léger directement en ligne de commande administrative :

### Script PowerShell de planification (`schedule_rappels.ps1`)
Exécutez PowerShell en tant qu'administrateur et lancez ces commandes pour programmer le script :

```powershell
$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c c:\iai_gestion\run_rappels.bat"
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 8am
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "IAI_Envoyer_Rappels_Paiements" -Action $Action -Trigger $Trigger -Settings $Settings -Description "Envoi hebdomadaire automatique des rappels d'échéances et de pénalités"
```
