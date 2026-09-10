#!/bin/sh

set -e

# Attendre que la base de données PostgreSQL soit prête
if [ "$DATABASE_ENGINE" = "django.db.backends.postgresql" ] || [ "$DATABASE_ENGINE" = "postgresql" ]; then
    echo "🔍 Attente de la base de données PostgreSQL ($DATABASE_HOST:$DATABASE_PORT)..."
    while ! nc -z ${DATABASE_HOST:-db} ${DATABASE_PORT:-5432}; do
      sleep 0.5
    done
    echo "✅ PostgreSQL est prêt et accessible !"
fi

# Appliquer les migrations de base de données
echo "📦 Application des migrations Django..."
python manage.py migrate --noinput

# Collecter les fichiers statiques
echo "🎨 Collecte des fichiers statiques..."
python manage.py collectstatic --noinput --clear

# Démarrer le serveur approprié
echo "🚀 Démarrage du serveur IAI-Gestion..."
if [ "$DEBUG" = "True" ] || [ "$DEBUG" = "true" ] || [ "$DEBUG" = "1" ]; then
    echo "🛠 Mode Développement activé (Django Runserver)"
    exec python manage.py runserver 0.0.0.0:8000
else
    echo "🔒 Mode Production activé (Gunicorn WSGI - 4 Workers)"
    exec gunicorn iai_gestion.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers 4 \
        --threads 2 \
        --timeout 120 \
        --access-logfile /app/logs/gunicorn_access.log \
        --error-logfile /app/logs/gunicorn_error.log
fi

