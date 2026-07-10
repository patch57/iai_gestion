import os

def check_and_fix_bom(filepath):
    """Vérifie et corrige les fichiers avec BOM"""
    try:
        with open(filepath, 'rb') as f:
            content = f.read()
        
        if content.startswith(b'\xef\xbb\xbf'):
            print(f"⚠️ BOM détecté: {filepath}")
            content_without_bom = content[3:]
            with open(filepath, 'wb') as f:
                f.write(content_without_bom)
            print(f"✅ BOM supprimé: {filepath}")
            return True
        return False
    except Exception as e:
        print(f"❌ Erreur avec {filepath}: {e}")
        return False

def create_template(filepath, content):
    """Crée un fichier template avec UTF-8 sans BOM"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Créé: {filepath}")
        return True
    except Exception as e:
        print(f"❌ Erreur création {filepath}: {e}")
        return False

print("=" * 50)
print("1. Vérification des fichiers HTML existants")
print("=" * 50)

html_files = []
for root, dirs, files in os.walk('.'):
    if 'venv' in root or '__pycache__' in root or 'migrations' in root:
        continue
    for file in files:
        if file.endswith('.html'):
            html_files.append(os.path.join(root, file))

for filepath in html_files:
    check_and_fix_bom(filepath)

print("\n" + "=" * 50)
print("2. Création des templates manquants")
print("=" * 50)

os.makedirs('templates/tableau_bord', exist_ok=True)

# Template pour ajouter une tâche
ajouter_tache = '''{% extends 'base.html' %}
{% load static %}

{% block title %}Ajouter une tâche - IAI-Cameroun{% endblock %}

{% block content %}
<div class="max-w-2xl mx-auto">
    <div class="bg-white rounded-xl shadow-sm p-6">
        <div class="flex items-center mb-6">
            <a href="{% url 'tableau_bord:taches' %}" class="mr-4 text-gray-500 hover:text-gray-700">
                <i class="fas fa-arrow-left text-xl"></i>
            </a>
            <h1 class="text-2xl font-bold text-gray-900">Ajouter une tâche</h1>
        </div>
        
        <form method="post" class="space-y-5">
            {% csrf_token %}
            
            <div>
                <label for="titre" class="block text-sm font-medium text-gray-700 mb-1">Titre *</label>
                <input type="text" name="titre" id="titre" required
                       class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-green-500 focus:border-green-500"
                       placeholder="Ex: Corriger les copies de GL101">
            </div>
            
            <div>
                <label for="description" class="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea name="description" id="description" rows="4"
                          class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-green-500 focus:border-green-500"
                          placeholder="Détails de la tâche..."></textarea>
            </div>
            
            <div class="grid grid-cols-2 gap-4">
                <div>
                    <label for="priorite" class="block text-sm font-medium text-gray-700 mb-1">Priorité *</label>
                    <select name="priorite" id="priorite" required
                            class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-green-500 focus:border-green-500">
                        <option value="BASSE">Basse</option>
                        <option value="MOYENNE" selected>Moyenne</option>
                        <option value="HAUTE">Haute</option>
                        <option value="URGENTE">Urgente</option>
                    </select>
                </div>
                
                <div>
                    <label for="date_echeance" class="block text-sm font-medium text-gray-700 mb-1">Date d'échéance</label>
                    <input type="date" name="date_echeance" id="date_echeance"
                           class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-green-500 focus:border-green-500">
                </div>
            </div>
            
            <div>
                <label for="module" class="block text-sm font-medium text-gray-700 mb-1">Module associé</label>
                <input type="text" name="module" id="module"
                       class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-green-500 focus:border-green-500"
                       placeholder="Ex: Administration, Pédagogie, etc.">
            </div>
            
            <div class="flex justify-end space-x-3 pt-4">
                <a href="{% url 'tableau_bord:taches' %}" 
                   class="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors">
                    Annuler
                </a>
                <button type="submit" 
                        class="px-4 py-2 bg-gradient-to-r from-green-500 to-green-600 text-white rounded-lg hover:from-green-600 hover:to-green-700 transition-all">
                    <i class="fas fa-save mr-2"></i>
                    Créer la tâche
                </button>
            </div>
        </form>
    </div>
</div>
{% endblock %}
'''

create_template('templates/tableau_bord/ajouter_tache.html', ajouter_tache)

# Template pour la liste des tâches
taches_template = '''{% extends 'base.html' %}
{% load static %}

{% block title %}Mes Tâches - IAI-Cameroun{% endblock %}

{% block content %}
<div class="space-y-6">
    <div class="flex items-center justify-between">
        <div>
            <h1 class="text-3xl font-bold text-gray-900">Mes Tâches</h1>
            <p class="text-gray-500 mt-1">Gérez vos tâches et rappels</p>
        </div>
        <a href="{% url 'tableau_bord:ajouter_tache' %}" 
           class="px-4 py-2 bg-gradient-to-r from-green-500 to-green-600 text-white rounded-lg hover:from-green-600 hover:to-green-700 transition-all shadow-md">
            <i class="fas fa-plus mr-2"></i>
            Nouvelle tâche
        </a>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-5 gap-4">
        <div class="bg-white rounded-xl shadow-sm p-4 text-center">
            <p class="text-2xl font-bold text-gray-900">{{ stats_taches.total }}</p>
            <p class="text-sm text-gray-500">Total</p>
        </div>
        <div class="bg-white rounded-xl shadow-sm p-4 text-center">
            <p class="text-2xl font-bold text-blue-600">{{ stats_taches.a_faire }}</p>
            <p class="text-sm text-gray-500">À faire</p>
        </div>
        <div class="bg-white rounded-xl shadow-sm p-4 text-center">
            <p class="text-2xl font-bold text-yellow-600">{{ stats_taches.en_cours }}</p>
            <p class="text-sm text-gray-500">En cours</p>
        </div>
        <div class="bg-white rounded-xl shadow-sm p-4 text-center">
            <p class="text-2xl font-bold text-green-600">{{ stats_taches.terminees }}</p>
            <p class="text-sm text-gray-500">Terminées</p>
        </div>
        <div class="bg-white rounded-xl shadow-sm p-4 text-center">
            <p class="text-2xl font-bold text-red-600">{{ stats_taches.en_retard }}</p>
            <p class="text-sm text-gray-500">En retard</p>
        </div>
    </div>

    <div class="bg-white rounded-xl shadow-sm overflow-hidden">
        <div class="divide-y divide-gray-100">
            {% for tache in taches %}
            <div class="p-4 hover:bg-gray-50 transition-all">
                <div class="flex items-start justify-between">
                    <div class="flex-1">
                        <div class="flex items-center space-x-3">
                            <div class="w-2 h-2 rounded-full 
                                {% if tache.priorite == 'URGENTE' %}bg-red-500
                                {% elif tache.priorite == 'HAUTE' %}bg-orange-500
                                {% elif tache.priorite == 'MOYENNE' %}bg-yellow-500
                                {% else %}bg-green-500{% endif %}">
                            </div>
                            <h3 class="font-semibold text-gray-900">{{ tache.titre }}</h3>
                            <span class="px-2 py-1 text-xs rounded-full 
                                {% if tache.statut == 'A_FAIRE' %}bg-blue-100 text-blue-700
                                {% elif tache.statut == 'EN_COURS' %}bg-yellow-100 text-yellow-700
                                {% elif tache.statut == 'TERMINEE' %}bg-green-100 text-green-700
                                {% else %}bg-gray-100 text-gray-700{% endif %}">
                                {{ tache.get_statut_display }}
                            </span>
                        </div>
                        <p class="text-sm text-gray-600 mt-2">{{ tache.description|truncatewords:30 }}</p>
                        <div class="flex items-center space-x-4 mt-3 text-xs text-gray-500">
                            <span><i class="far fa-calendar-alt mr-1"></i>Échéance: {{ tache.date_echeance|date:"d/m/Y" }}</span>
                            <span><i class="fas fa-tag mr-1"></i>{{ tache.get_priorite_display }}</span>
                        </div>
                    </div>
                    <div class="flex items-center space-x-2 ml-4">
                        {% if tache.statut != 'TERMINEE' %}
                        <a href="{% url 'tableau_bord:terminer_tache' tache.id %}" class="p-2 text-green-600 hover:bg-green-50 rounded-lg">
                            <i class="fas fa-check-circle"></i>
                        </a>
                        {% endif %}
                        <a href="{% url 'tableau_bord:modifier_tache' tache.id %}" class="p-2 text-blue-600 hover:bg-blue-50 rounded-lg">
                            <i class="fas fa-edit"></i>
                        </a>
                    </div>
                </div>
            </div>
            {% empty %}
            <div class="p-12 text-center">
                <i class="fas fa-check-circle text-5xl text-gray-300 mb-4"></i>
                <p class="text-gray-500">Aucune tâche pour le moment</p>
                <a href="{% url 'tableau_bord:ajouter_tache' %}" class="inline-block mt-4 text-green-600 hover:text-green-700">
                    <i class="fas fa-plus mr-1"></i>Créer votre première tâche
                </a>
            </div>
            {% endfor %}
        </div>
    </div>
</div>
{% endblock %}
'''

create_template('templates/tableau_bord/taches.html', taches_template)

# Template de base pour les autres pages
base_template = '''{% extends 'base.html' %}

{% block content %}
<div class="p-6">
    <h1 class="text-2xl font-bold">{{ titre }}</h1>
    <p class="text-gray-600 mt-4">Page en construction...</p>
</div>
{% endblock %}
'''

other_pages = [
    'modifier_tache.html', 'supprimer_tache.html', 'notifications.html',
    'profil.html', 'statistiques.html', 'statistiques_filieres.html',
    'statistiques_paiements.html', 'messages.html', 'calendrier.html',
    'alertes.html', 'modifier_profil.html', 'changer_mot_de_passe.html',
    'imprimer.html', 'evenements.html', 'ajouter_evenement.html',
    'detail_message.html', 'envoyer_message.html', 'repondre_message.html'
]

for page in other_pages:
    create_template(f'templates/tableau_bord/{page}', base_template)

print("\n" + "=" * 50)
print("✅ Correction terminée! Redémarrez le serveur.")
print("=" * 50)