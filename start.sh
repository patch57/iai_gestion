#!/bin/bash

# Script de démarrage rapide pour IAI-Gestion
# IAI-Cameroun - Centre de Douala

echo "======================================"
echo "  IAI-Gestion - Démarrage rapide"
echo "  IAI-Cameroun - Centre de Douala"
echo "======================================"
echo ""

# Vérifier si Python est installé
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 n'est pas installé. Veuillez l'installer."
    exit 1
fi

echo "✅ Python 3 trouvé"

# Créer l'environnement virtuel si inexistant
if [ ! -d "venv" ]; then
    echo "📦 Création de l'environnement virtuel..."
    python3 -m venv venv
fi

# Activer l'environnement virtuel
echo "🚀 Activation de l'environnement virtuel..."
source venv/bin/activate

# Installer les dépendances
echo "📥 Installation des dépendances..."
pip install -q -r requirements.txt

# Créer les migrations si nécessaire
echo "🗄️  Création des migrations..."
python manage.py makemigrations --noinput

# Appliquer les migrations
echo "🗄️  Application des migrations..."
python manage.py migrate --noinput

# Créer le superutilisateur si inexistant
echo ""
echo "👤 Vérification du superutilisateur..."
python manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    print("⚠️  Aucun superutilisateur trouvé.")
    print("📝 Création d'un superutilisateur par défaut:")
    print("   Nom d'utilisateur: admin")
    print("   Mot de passe: admin123")
    User.objects.create_superuser('admin', 'admin@iai-cameroun.com', 'admin123')
    print("✅ Superutilisateur créé avec succès!")
else:
    print("✅ Superutilisateur existant")
EOF

echo ""
echo "======================================"
echo "  ✅ Configuration terminée!"
echo "======================================"
echo ""
echo "🌐 Démarrage du serveur..."
echo ""
echo "📍 Accès à l'application:"
echo "   - Site web: http://127.0.0.1:8000/"
echo "   - Administration: http://127.0.0.1:8000/admin/"
echo ""
echo "👤 Identifiants par défaut:"
echo "   - Nom d'utilisateur: admin"
echo "   - Mot de passe: admin123"
echo ""
echo "⚠️  N'oubliez pas de changer le mot de passe par défaut!"
echo ""
echo "Appuyez sur Ctrl+C pour arrêter le serveur"
echo ""

# Lancer le serveur
python manage.py runserver
