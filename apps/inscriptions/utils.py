from datetime import datetime

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
