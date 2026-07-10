#!/bin/sh

# Attendre que la base de données soit prête si PostgreSQL est configuré
if [ "$DATABASE_ENGINE" = "django.db.backends.postgresql" ]; then
    echo "Attente de la base de données PostgreSQL..."
    while ! nc -z $DATABASE_HOST $DATABASE_PORT; do
      sleep 0.1
    done
    echo "PostgreSQL est prêt !"
fi

# Appliquer les migrations de base de données
echo "Application des migrations Django..."
python manage.py migrate --noinput

# Collecter les fichiers statiques
echo "Collecte des fichiers statiques..."
python manage.py collectstatic --noinput

# Charger les données initiales
echo "Chargement des fixtures initiales..."
if [ -f "fixtures/initial_data.json" ]; then
    python manage.py loaddata fixtures/initial_data.json
fi

# Démarrer le serveur
echo "Démarrage du serveur..."
if [ "$DEBUG" = "True" ] || [ "$DEBUG" = "true" ]; then
    # Mode développement
    exec python manage.py runserver 0.0.0.0:8000
else
    # Mode production
    exec gunicorn iai_gestion.wsgi:application --bind 0.0.0.0:8000 --workers 3
fi
