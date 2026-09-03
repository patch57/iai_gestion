from datetime import datetime
import unicodedata
import re

def get_current_academic_year_code():
    """
    Retourne le code de l'année académique courante en fonction de la date actuelle.
    Ex: En Juillet 2026, retourne '2026-2027'.
    """
    courant = datetime.now()
    annee_debut = courant.year
    # Les campagnes commencent en général en Juin
    if courant.month >= 6:
        return f"{annee_debut}-{annee_debut + 1}"
    else:
        return f"{annee_debut - 1}-{annee_debut}"


def normaliser_chaine(texte):
    """Normalise un texte pour comparaison insensible à la casse et aux accents."""
    if not texte:
        return ""
    texte = unicodedata.normalize('NFD', str(texte))
    texte = ''.join(c for c in texte if unicodedata.category(c) != 'Mn')
    texte = texte.lower().strip()
    texte = re.sub(r'[\s\-]+', ' ', texte)
    return texte


def rechercher_date_concours_etudiant(etudiant):
    """
    Vérifie si l'étudiant est du Niveau 1 et s'il figure dans l'une des listes de candidats
    admis au concours importées par la comptabilité (ResultatConcours).
    Retourne un tuple (date_concours, resultat_concours_obj).
    """
    if not etudiant:
        return None, None

    # 1. Vérification si l'étudiant est du Niveau 1 (ou nouvelle admission / sans niveau)
    is_niveau_1 = False
    if not etudiant.niveau:
        is_niveau_1 = True
    elif hasattr(etudiant.niveau, 'numero') and etudiant.niveau.numero == 1:
        is_niveau_1 = True
    elif etudiant.niveau and ('1' in str(etudiant.niveau.code) or '1' in str(etudiant.niveau.nom)):
        is_niveau_1 = True

    if not is_niveau_1:
        return None, None

    from apps.paiements.models import ResultatConcours

    # 2. Match direct par profil étudiant lié
    resultat = ResultatConcours.objects.filter(etudiant_cree=etudiant, session_concours__isnull=False).select_related('session_concours').first()
    if resultat and resultat.session_concours and resultat.session_concours.date_concours:
        return resultat.session_concours.date_concours, resultat

    # 3. Match par Adresse Email
    if etudiant.email:
        res_email = ResultatConcours.objects.filter(
            email__iexact=etudiant.email.strip(),
            session_concours__isnull=False,
            statut_admission='ADMIS'
        ).select_related('session_concours').first()
        if res_email and res_email.session_concours and res_email.session_concours.date_concours:
            return res_email.session_concours.date_concours, res_email

    # 4. Match par Nom & Prénom (Normalisé & Inversé)
    nom_etud = normaliser_chaine(etudiant.nom)
    prenom_etud = normaliser_chaine(etudiant.prenom)

    if nom_etud:
        res_list = ResultatConcours.objects.filter(
            statut_admission='ADMIS',
            session_concours__isnull=False
        ).select_related('session_concours')

        for r in res_list:
            r_nom = normaliser_chaine(r.nom)
            r_prenom = normaliser_chaine(r.prenom)

            # Match exact direct ou nom/prénom intervertis
            if (r_nom == nom_etud and r_prenom == prenom_etud) or (r_nom == prenom_etud and r_prenom == nom_etud):
                return r.session_concours.date_concours, r
            
            # Match si le nom complet contient les mots principaux
            if nom_etud in r_nom and prenom_etud in r_prenom:
                return r.session_concours.date_concours, r

    return None, None
