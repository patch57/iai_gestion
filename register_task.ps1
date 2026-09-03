# Script PowerShell d'automatisation du Planificateur de Tâches Windows pour IAI-Gestion
# Usage :
#   - Enregistrer la tâche : .\register_task.ps1
#   - Tester immédiatement  : .\register_task.ps1 -RunNow
#   - Supprimer la tâche    : .\register_task.ps1 -Uninstall

param (
    [switch]$RunNow,
    [switch]$Uninstall,
    [string]$TaskName = "IAI_Envoyer_Rappels_Paiements",
    [string]$Time = "08:00"
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BatPath = Join-Path $ScriptDir "run_rappels.bat"

if (-not (Test-Path $BatPath)) {
    Write-Error "Le fichier $BatPath n'a pas été trouvé."
    exit 1
}

if ($Uninstall) {
    Write-Host "Suppression de la tâche planifiée '$TaskName'..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Tâche '$TaskName' supprimée avec succès." -ForegroundColor Green
    exit 0
}

if ($RunNow) {
    Write-Host "Lancement immédiat du script $BatPath..." -ForegroundColor Cyan
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$BatPath`"" -Wait -NoNewWindow
    Write-Host "Exécution terminée. Consultez logs\rappels_cron.log" -ForegroundColor Green
    exit 0
}

Write-Host "Configuration de la tâche planifiée '$TaskName'..." -ForegroundColor Cyan

# 1. Action : exécuter run_rappels.bat
$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$BatPath`"" -WorkingDirectory $ScriptDir

# 2. Déclencheur : Tous les lundis à l'heure spécifiée (ex: 08:00)
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At $Time

# 3. Paramètres de tolérance réseau & batterie
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# 4. Enregistrement ou mise à jour
try {
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Envoi hebdomadaire automatique des rappels d'échéances et de pénalités de scolarité IAI-Cameroun (Douala)" -Force | Out-Null
    Write-Host "La tâche planifiée '$TaskName' a été enregistrée avec succès !" -ForegroundColor Green
    Write-Host "Fréquence : Tous les lundis à $Time" -ForegroundColor Cyan
    Write-Host "Commande  : cmd.exe /c $BatPath" -ForegroundColor Gray
} catch {
    Write-Error "Impossible d'enregistrer la tâche. Veuillez réessayer dans une console PowerShell en tant qu'Administrateur."
}
