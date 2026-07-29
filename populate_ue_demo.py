import os
import sys
import django
from datetime import date

sys.path.append('c:/iai_gestion')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'iai_gestion.settings')
django.setup()

from apps.etudiants.models import Filiere, Niveau, Classe, AnneeAcademique
from apps.notes.models import Matiere, UniteEnseignement, TypeEvaluation, Cours

def populate():
    print("Début du peuplement des UEs de démonstration issues du PDF...")

    # 1. Année Académique 2025-2026
    annee, created = AnneeAcademique.objects.get_or_create(
        code="2025-2026",
        defaults={
            'date_debut': date(2025, 9, 1),
            'date_fin': date(2026, 8, 31),
            'est_active': True
        }
    )
    if created:
        print("Année académique 2025-2026 créée.")

    # 2. Filière GL
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

    # 3. Niveau 3
    niveau, created = Niveau.objects.get_or_create(
        filiere=filiere,
        numero=3
    )
    if created:
        print("Niveau III pour GL créé.")

    # 4. Classe GL3D
    classe, created = Classe.objects.get_or_create(
        nom="GL3D",
        filiere=filiere,
        niveau=niveau,
        annee_academique=annee,
        defaults={
            'effectif_max': 40,
            'est_active': True
        }
    )
    if created:
        print("Classe GL3D créée.")

    # 5. S'assurer que le type d'évaluation RATT existe
    type_ratt, created = TypeEvaluation.objects.get_or_create(
        code="RATT",
        defaults={
            'nom': "Rattrapage",
            'description': "Examen de rattrapage",
            'coefficient_default': 1.00,
            'est_actif': True
        }
    )
    if created:
        print("Type d'évaluation RATT créé.")

    # 6. Définition des UEs et Matières du PDF
    ues_data = [
        {
            "code": "UE_APP_BD",
            "nom": "UE Application des bases de données",
            "matieres": [
                {"code": "SIG", "nom": "Système d'information géographique", "credit": 3},
                {"code": "BIG_DATA", "nom": "BIG DATA (noSQL,...)", "credit": 3},
                {"code": "SIAD", "nom": "Système d'information d'aide à la décision", "credit": 3}
            ]
        },
        {
            "code": "UE_BD_AV",
            "nom": "UE Bases de données avancées",
            "matieres": [
                {"code": "J2E", "nom": "Programmation J2E", "credit": 4},
                {"code": "MOBILE", "nom": "Programmation mobile", "credit": 4},
                {"code": "PYTHON_AV", "nom": "Programmation Python avancée", "credit": 4}
            ]
        },
        {
            "code": "UE_ADMIN_BD_SEC",
            "nom": "UE Administration Bases de données et sécurité",
            "matieres": [
                {"code": "ORACLE", "nom": "Administration des bases de données oracle", "credit": 5},
                {"code": "SEC_BD", "nom": "Sécurité des bases de données", "credit": 3},
                {"code": "SQL_SERVER", "nom": "Administration des bases de données SQL-Server", "credit": 5}
            ]
        },
        {
            "code": "UE_GL",
            "nom": "UE Génie Logiciel",
            "matieres": [
                {"code": "IA", "nom": "Introduction à l'intelligence artificielle", "credit": 3},
                {"code": "ANALYSE_DONNEES", "nom": "Analyse de données", "credit": 3}
            ]
        },
        {
            "code": "UE_LANG_COMM",
            "nom": "Langues et communication",
            "matieres": [
                {"code": "ANGLAIS", "nom": "Anglais expert", "credit": 3},
                {"code": "TECH_COMM", "nom": "Techniques de communication", "credit": 2}
            ]
        },
        {
            "code": "UE_DROIT_ENT",
            "nom": "Droit et Entrepreneuriat",
            "matieres": [
                {"code": "ENTREPRENEURIAT", "nom": "Entrepreneuriat et Création d'entreprise", "credit": 3},
                {"code": "DROIT_TRAVAIL", "nom": "Droit du travail", "credit": 3}
            ]
        },
        {
            "code": "UE_PROG_MULTI",
            "nom": "Programmation avancée et Multimédia",
            "matieres": [
                {"code": "DJANGO_FLASK", "nom": "programmation orientée objet avancée (Django,Flask,...)", "credit": 3},
                {"code": "LARAVEL_NODE", "nom": "Outils de programmation Web (Framework Laravel,NodeJS,...)", "credit": 4},
                {"code": "MULTIMEDIA", "nom": "Techniques Multimédias et Infographie", "credit": 3}
            ]
        },
        {
            "code": "UE_SPORT_COND",
            "nom": "UE Sport et conduite",
            "matieres": [
                {"code": "EPS", "nom": "Education Physique", "credit": 2},
                {"code": "CONDUITE", "nom": "Conduite", "credit": 2}
            ]
        },
        {
            "code": "UE_PROJET_GL",
            "nom": "UE Projet de Génie Logiciel",
            "matieres": [
                {"code": "SEMINAIRE", "nom": "Séminaire", "credit": 2},
                {"code": "PROJET_PERSO", "nom": "Projet Génie Logiciel Personnalisé", "credit": 4}
            ]
        }
    ]

    for ue_dict in ues_data:
        ue, ue_created = UniteEnseignement.objects.get_or_create(
            code=ue_dict["code"],
            defaults={
                'nom': ue_dict["nom"],
                'filiere': filiere,
                'niveau': niveau
            }
        )
        if ue_created:
            print(f"UE créée : {ue.nom}")
        else:
            ue.filiere = filiere
            ue.niveau = niveau
            ue.save()

        for mat_dict in ue_dict["matieres"]:
            matiere, mat_created = Matiere.objects.get_or_create(
                code=mat_dict["code"],
                defaults={
                    'nom': mat_dict["nom"],
                    'credit': mat_dict["credit"],
                    'unite_enseignement': ue,
                    'semestre': 1,
                    'volume_horaire': 30,
                    'est_actif': True
                }
            )
            if mat_created:
                print(f"  Matière créée : {matiere.nom} (UE={ue.code})")
            else:
                matiere.unite_enseignement = ue
                matiere.credit = mat_dict["credit"]
                matiere.save()

            # Créer automatiquement un Cours pour la classe pour que les matières apparaissent sur le bordereau
            cours, cours_created = Cours.objects.get_or_create(
                matiere=matiere,
                filiere=filiere,
                niveau=niveau,
                annee_academique=annee.code,
                defaults={
                    'semestre': 1,
                    'volume_horaire': 30,
                    'est_actif': True
                }
            )
            if cours_created:
                print(f"    Cours créé pour {matiere.nom} (Classe=GL3D)")

    print("Peuplement terminé avec succès !")

if __name__ == '__main__':
    populate()
