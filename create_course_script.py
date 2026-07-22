import os
import django
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'iai_gestion.settings')
django.setup()

from apps.etudiants.models import Filiere
from apps.cours.models import Cours, Matiere
from apps.professeurs.models import Professeur

def run():
    print("Début de la création du cours pour Otabela Joël...")
    
    # 1. Récupérer le professeur Otabela Joël
    try:
        prof = Professeur.objects.get(matricule="ENS.CMR.D100.2026.E")
        print(f"Professeur trouvé : {prof.nom} {prof.prenom}")
    except Professeur.DoesNotExist:
        print("Erreur : Le professeur Otabela Joël avec le matricule ENS.CMR.D100.2026.E n'existe pas.")
        return

    # 2. Récupérer ou créer la filière
    filiere, created = Filiere.objects.get_or_create(
        code="GL",
        defaults={
            'nom': "Génie Logiciel",
            'description': "Formation en développement de logiciels",
            'est_active': True
        }
    )
    if created:
        print("Filière GL créée.")

    # 3. Créer ou récupérer la matière (sans le champ 'departement')
    matiere, created = Matiere.objects.get_or_create(
        code="PYTHON",
        defaults={
            'nom': "Programmation Python",
            'description': "Introduction et approfondissement en langage Python",
            'credits': 4,
            'heures_cours': 30,
            'heures_tp': 15,
            'semestre': 1
        }
    )
    if created:
        print("Matière PYTHON créée.")

    # 4. Créer le cours associé au professeur
    cours, created = Cours.objects.get_or_create(
        code="GL-PYTHON-2425",
        defaults={
            'matiere': matiere,
            'filiere': filiere,
            'annee_academique': '2024-2025',
            'professeur': prof,
            'type_cours': 'COURS',
            'jour': 'Lundi',
            'heure_debut': '08:00:00',
            'heure_fin': '12:00:00',
            'date_debut': date(2024, 10, 1),
            'date_fin': date(2025, 6, 30)
        }
    )
    if created:
        print(f"Cours '{cours.code}' créé avec succès et attribué à {prof.get_nom_complet()}.")
    else:
        if cours.professeur != prof:
            cours.professeur = prof
            cours.save()
            print(f"Cours '{cours.code}' réattribué à {prof.get_nom_complet()}.")
        else:
            print(f"Le cours '{cours.code}' est déjà attribué à {prof.get_nom_complet()}.")

if __name__ == '__main__':
    run()
