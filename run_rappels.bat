@echo off
cd /d "%~dp0"

if not exist "logs" mkdir logs

echo ======================================================== >> logs\rappels_cron.log
echo Exécution des rappels de paiements : %DATE% à %TIME% >> logs\rappels_cron.log
echo ======================================================== >> logs\rappels_cron.log

if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

python manage.py envoyer_rappels_paiements >> logs\rappels_cron.log 2>&1

echo Fin d'exécution : %DATE% à %TIME% >> logs\rappels_cron.log
echo. >> logs\rappels_cron.log
