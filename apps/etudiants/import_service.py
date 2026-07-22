import re
import os
import openpyxl
from django.utils import timezone
from apps.etudiants.models import Etudiant, Filiere, AnneeAcademique, Classe
from apps.authentification.models import Utilisateur
from apps.paiements.ocr_service import extraire_texte

class EtudiantImportService:
    """
    Service d'importation d'étudiants depuis divers formats (Excel, PDF, Images).
    Utilise l'OCR si nécessaire.
    """

    @classmethod
    def importer_depuis_fichier(cls, fichier, user_createur):
        """
        Détermine le format et lance l'importation.
        Retourne (nb_ajoutes, nb_mis_a_jour, erreurs)
        """
        nom_fichier = fichier.name.lower()
        extension = os.path.splitext(nom_fichier)[1]

        # Récupérer l'année académique active
        annee_active = AnneeAcademique.objects.filter(est_active=True).first()
        if not annee_active:
            raise ValueError("Aucune année académique active configurée.")

        if extension in ['.xlsx', '.xls']:
            return cls._importer_excel(fichier, annee_active)
        elif extension in ['.pdf', '.jpg', '.jpeg', '.png']:
            return cls._importer_ocr(fichier, annee_active)
        else:
            raise ValueError("Format de fichier non supporté. (Excel, PDF, Images uniquement).")

    @classmethod
    def _importer_excel(cls, fichier, annee_active):
        """Importation depuis un fichier Excel (.xlsx)"""
        wb = openpyxl.load_workbook(fichier, read_only=True)
        sheet = wb.active

        nb_ajoutes = 0
        nb_mis_a_jour = 0
        erreurs = []

        # Parcourir les lignes à partir de la ligne 2 (pour ignorer les entêtes)
        for idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            if not row or not any(row):
                continue

            try:
                # Format attendu : Nom, Prénom, Email, Téléphone, Filière (GL/SR), Sexe (M/F)
                nom = row[0]
                prenom = row[1]
                email = row[2]
                telephone = str(row[3]) if row[3] else ""
                filiere_code = str(row[4]).upper().strip() if row[4] else "GL"
                sexe = str(row[5]).upper().strip() if row[5] else "M"

                if not nom or not email:
                    erreurs.append(f"Ligne {idx} : Nom et Email requis.")
                    continue

                ajoute, mis_a_jour = cls._creer_ou_mettre_a_jour_etudiant(
                    nom=nom, prenom=prenom, email=email, telephone=telephone,
                    filiere_code=filiere_code, sexe=sexe, annee_active=annee_active
                )

                if ajoute:
                    nb_ajoutes += 1
                else:
                    nb_mis_a_jour += 1

            except Exception as e:
                erreurs.append(f"Ligne {idx} : Erreur inattendue : {str(e)}")

        return nb_ajoutes, nb_mis_a_jour, erreurs

    @classmethod
    def _importer_ocr(cls, fichier, annee_active):
        """Importation depuis PDF/Image en extrayant le texte via OCR"""
        # Extraire le texte brut du fichier (OCR ou PDF text)
        texte = extraire_texte(fichier)
        if not texte or len(texte.strip()) < 10:
            raise ValueError("Impossible d'extraire du texte lisible du document.")

        nb_ajoutes = 0
        nb_mis_a_jour = 0
        erreurs = []

        # Découper le texte en lignes
        lignes = texte.split('\n')
        
        # Pattern regex pour détecter des adresses email
        email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
        # Pattern pour numéro de téléphone (8 ou 9 chiffres)
        phone_pattern = r'\b(6|2)\d{8}\b'

        for idx, ligne in enumerate(lignes, start=1):
            ligne = ligne.strip()
            if not ligne or len(ligne) < 5:
                continue

            # Tenter d'extraire un email
            email_match = re.search(email_pattern, ligne)
            if not email_match:
                continue
            email = email_match.group(0)

            # Extraire le téléphone si présent
            phone_match = re.search(phone_pattern, ligne)
            telephone = phone_match.group(0) if phone_match else ""

            # Extraire la filière (GL ou SR)
            filiere_match = re.search(r'\b(GL|SR)\b', ligne, re.IGNORECASE)
            filiere_code = filiere_match.group(0).upper() if filiere_match else "GL"

            # Tenter de trouver le nom et le prénom
            # On nettoie la ligne en enlevant les infos connues (email, téléphone, filière)
            reste = ligne.replace(email, "").replace(telephone, "").replace(filiere_code, "")
            # Nettoyer les caractères spéciaux restants
            reste = re.sub(r'[\d\+\-\/\:\;\,\.\(\)]', '', reste).strip()

            mots = reste.split()
            if len(mots) >= 1:
                nom = mots[0]
                prenom = " ".join(mots[1:]) if len(mots) > 1 else ""
            else:
                nom = "Etudiant"
                prenom = "Import-OCR"

            try:
                ajoute, mis_a_jour = cls._creer_ou_mettre_a_jour_etudiant(
                    nom=nom, prenom=prenom, email=email, telephone=telephone,
                    filiere_code=filiere_code, sexe='M', annee_active=annee_active
                )

                if ajoute:
                    nb_ajoutes += 1
                else:
                    nb_mis_a_jour += 1
            except Exception as e:
                erreurs.append(f"Ligne {idx} : Erreur d'importation de {nom} ({email}) : {str(e)}")

        return nb_ajoutes, nb_mis_a_jour, erreurs

    @classmethod
    def _creer_ou_mettre_a_jour_etudiant(cls, nom, prenom, email, telephone, filiere_code, sexe, annee_active):
        """Crée ou met à jour l'utilisateur et son profil étudiant"""
        # Récupérer la filière
        filiere = Filiere.objects.filter(code=filiere_code).first()
        if not filiere:
            filiere = Filiere.objects.first()

        # Créer le nom d'utilisateur (username) à partir de l'email
        username = email.split('@')[0]
        
        # Vérifier si l'utilisateur existe déjà
        user = Utilisateur.objects.filter(email=email).first()
        ajoute = False

        if not user:
            # Créer l'utilisateur
            user = Utilisateur.objects.create(
                username=username,
                email=email,
                first_name=prenom,
                last_name=nom,
                telephone=telephone,
                type_utilisateur='ETUDIANT',
                statut_inscription='COMPTE_ACTIF'
            )
            # Générer un mot de passe par défaut sécurisé
            user.set_password('IaiCameroun2026!')
            user.save()
            ajoute = True
        else:
            # Mettre à jour l'utilisateur existant
            user.first_name = prenom
            user.last_name = nom
            user.telephone = telephone
            user.save(update_fields=['first_name', 'last_name', 'telephone'])

        # Créer ou mettre à jour le profil étudiant
        etudiant, created = Etudiant.objects.get_or_create(
            utilisateur=user,
            defaults={
                'nom': nom,
                'prenom': prenom,
                'email': email,
                'telephone': telephone,
                'sexe': sexe if sexe in ['M', 'F'] else 'M',
                'filiere': filiere,
                'annee_academique': annee_active,
                'matricule': user.matricule or f"{filiere.code}.CMR.D014.{annee_active.code[-4:]}A"
            }
        )

        if not created:
            etudiant.nom = nom
            etudiant.prenom = prenom
            etudiant.telephone = telephone
            etudiant.filiere = filiere
            etudiant.save(update_fields=['nom', 'prenom', 'telephone', 'filiere'])

        return ajoute, not ajoute
