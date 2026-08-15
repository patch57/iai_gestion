"""
Service d'extraction, de matching automatique et de calcul cumulatif des fiches de présence hebdomadaires
IAI-Cameroun - Centre de Douala
"""
import re
import json
import unicodedata
from django.db.models import Sum

def normaliser_chaine(chaine):
    """
    Normalise une chaîne pour la comparaison (sans accent, majuscules, sans espaces superflus).
    Ex: "PATCHONG  NJITACK" -> "patchong njitack"
    """
    if not chaine:
        return ""
    text = unicodedata.normalize('NFD', str(chaine)).encode('ascii', 'ignore').decode("utf-8")
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
    return ' '.join(text.lower().split())


def matcher_etudiant_presence(matricule_ou_nom, etudiants_classe):
    """
    Recherche automatique et fiable d'un étudiant par son matricule ou son nom/prénom.
    """
    if not matricule_ou_nom or not etudiants_classe:
        return None, 0.0

    cle_cherche = normaliser_chaine(matricule_ou_nom)
    
    # 1. Matching exact sur le matricule (ex: GL.CMR.D003.2526A)
    for etudiant in etudiants_classe:
        if etudiant.matricule and normaliser_chaine(etudiant.matricule) in cle_cherche:
            return etudiant, 1.0
        if etudiant.matricule and cle_cherche in normaliser_chaine(etudiant.matricule):
            return etudiant, 0.95

    # 2. Matching sur le nom complet (Nom + Prénom)
    for etudiant in etudiants_classe:
        nom_complet = normaliser_chaine(f"{etudiant.nom} {etudiant.prenom}")
        prenom_nom = normaliser_chaine(f"{etudiant.prenom} {etudiant.nom}")
        
        if cle_cherche == nom_complet or cle_cherche == prenom_nom:
            return etudiant, 1.0

    # 3. Matching partiel sur mots clés (ex: PATCHONG NJITACK)
    mots_cles = set(cle_cherche.split())
    if len(mots_cles) >= 2:
        meilleur_score = 0.0
        meilleur_etudiant = None
        
        for etudiant in etudiants_classe:
            mots_etudiant = set(normaliser_chaine(f"{etudiant.nom} {etudiant.prenom}").split())
            intersection = mots_cles.intersection(mots_etudiant)
            
            if intersection:
                score = len(intersection) / max(len(mots_cles), len(mots_etudiant))
                if score > meilleur_score and score >= 0.5:
                    meilleur_score = score
                    meilleur_etudiant = etudiant
                    
        if meilleur_etudiant:
            return meilleur_etudiant, round(meilleur_score, 2)

    return None, 0.0


def compter_absences_grille(grille_semaine):
    """
    Comptabilise le nombre d'absences ('A') dans les créneaux d'une semaine.
    Case 'A' ou 'a' = 1 absence
    Case vide ou autre (ex: 'FERIE') = 0 absence
    """
    total = 0
    if isinstance(grille_semaine, dict):
        for jour, creneaux in grille_semaine.items():
            if isinstance(creneaux, list):
                for val in creneaux:
                    if str(val).strip().upper() == 'A':
                        total += 1
            elif str(creneaux).strip().upper() == 'A':
                total += 1
    return total


def calculer_total_absences_cumulees(etudiant):
    """
    Calcule la somme totale cumulée des absences pour un étudiant
    à partir de toutes les fiches de présence publiées.
    """
    from apps.cours.models import LignePresenceHebdomadaire
    
    total = LignePresenceHebdomadaire.objects.filter(
        etudiant=etudiant,
        fiche__statut='PUBLIE'
    ).aggregate(total_abs=Sum('nombre_absences'))['total_abs']
    
    return total or 0


def calculer_notes_annuelles_discipline(classe_id):
    """
    Calcule pour tous les étudiants d'une classe la note annuelle de discipline :
    - HA (Heures d'Absences) = somme des absences des fiches de présence publiées
    - HJ (Heures Justifiées) = somme des heures justifiées
    - HNJ (Heures Non Justifiées) = max(0, HA - HJ)
    - DECISION = 'Exclu(e)' si HNJ > 30 sinon ''
    """
    from apps.etudiants.models import Classe, Etudiant
    from apps.cours.models import Salle, LignePresenceHebdomadaire

    classe = Classe.objects.filter(pk=classe_id).select_related('filiere', 'niveau', 'annee_academique').first()
    if classe:
        etudiants = list(classe.etudiants.filter(statut__in=['INSCRIT', 'ACTIF']).order_by('nom', 'prenom'))
    else:
        salle = Salle.objects.filter(pk=classe_id).first()
        if salle:
            classe = Classe.objects.filter(nom__icontains=salle.nom).first() or Classe.objects.filter(nom__icontains=salle.code).first()
            if classe:
                etudiants = list(classe.etudiants.filter(statut__in=['INSCRIT', 'ACTIF']).order_by('nom', 'prenom'))
            else:
                etudiants = list(Etudiant.objects.filter(statut__in=['INSCRIT', 'ACTIF']).order_by('nom', 'prenom'))
                class Factice:
                    nom = salle.nom
                    filiere = type('F', (), {'code': salle.code[:2], 'nom': salle.nom})()
                    niveau = type('N', (), {'numero': 1})()
                    annee_academique = type('A', (), {'code': '2025-2026'})()
                classe = Factice()
        else:
            classe = Classe.objects.first()
            etudiants = list(classe.etudiants.filter(statut__in=['INSCRIT', 'ACTIF']).order_by('nom', 'prenom')) if classe else []

    results = []
    for index, etudiant in enumerate(etudiants, 1):
        lignes = LignePresenceHebdomadaire.objects.filter(
            etudiant=etudiant,
            fiche__statut='PUBLIE'
        )
        
        ha = sum(l.nombre_absences for l in lignes)
        hj = sum(l.heures_justifiees for l in lignes)
        hnj = max(0, ha - hj)
        
        decision = "Exclu(e)" if hnj > 30 else ""

        results.append({
            'index': index,
            'etudiant': etudiant,
            'ha': ha,
            'hj': hj,
            'hnj': hnj,
            'decision': decision,
        })

    annee_code = getattr(getattr(classe, 'annee_academique', None), 'code', '2025-2026')
    return {
        'classe': classe,
        'filiere': getattr(classe, 'filiere', None),
        'niveau': getattr(classe, 'niveau', None),
        'annee_academique': annee_code,
        'results': results
    }


def obtenir_programme_quotidien_enseignant(user, date_cible=None):
    """
    Parcourt tous les emplois du temps officiels publiés par le Chef des Études
    et extrait les tranches horaires du jour pour l'enseignant connecté,
    triées par ordre chronologique.
    Se remplace automatiquement chaque jour à minuit selon timezone.now().date().
    """
    from django.utils import timezone
    from apps.cours.models import EmploiDuTempsHebdomadaire, CreneauEmploiDuTemps, Cours
    from apps.professeurs.models import Professeur

    JOUR_MAP = {
        0: 'LUNDI',
        1: 'MARDI',
        2: 'MERCREDI',
        3: 'JEUDI',
        4: 'VENDREDI',
        5: 'SAMEDI',
    }

    JOUR_NOMS = {
        0: 'Lundi', 1: 'Mardi', 2: 'Mercredi', 3: 'Jeudi', 4: 'Vendredi', 5: 'Samedi', 6: 'Dimanche'
    }

    PLAGE_ORDER = {
        'P1': 1,
        'P2': 2,
        'PAUSE': 3,
        'P3': 4,
        'P4': 5,
    }

    PLAGE_HORAIRES = {
        'P1': '07:30 - 09:30',
        'P2': '09:30 - 11:30',
        'PAUSE': '11:30 - 12:45',
        'P3': '12:45 - 14:45',
        'P4': '14:45 - 16:45',
    }

    if not date_cible:
        date_cible = timezone.now().date()
        
    weekday_num = date_cible.weekday()
    jour_code = JOUR_MAP.get(weekday_num, None)
    nom_jour = JOUR_NOMS.get(weekday_num, 'Aujourd\'hui')
    
    if not jour_code:
        return {
            'date': date_cible,
            'nom_jour': nom_jour,
            'jour_code': None,
            'creneaux': [],
            'message': 'Aucun cours programmé le dimanche.'
        }
        
    # Identifier le professeur
    professeur = None
    if isinstance(user, Professeur):
        professeur = user
        user = professeur.utilisateur
    elif hasattr(user, 'type_utilisateur'):
        professeur = Professeur.objects.filter(utilisateur=user).first()
        
    # Mots-clés pour matcher l'enseignant
    mots_cles = set()
    if professeur:
        if professeur.nom:
            mots_cles.update(normaliser_chaine(professeur.nom).split())
        if professeur.prenom:
            mots_cles.update(normaliser_chaine(professeur.prenom).split())
    if user:
        if user.last_name:
            mots_cles.update(normaliser_chaine(user.last_name).split())
        if user.first_name:
            mots_cles.update(normaliser_chaine(user.first_name).split())
        if user.username:
            mots_cles.update(normaliser_chaine(user.username).split())
            
    mots_cles = {m for m in mots_cles if len(m) > 2 and m not in ['mme', 'prof', 'docteur', 'monsieur']}

    # Intitulés des cours assignés à ce professeur
    cours_assignes = []
    if professeur:
        cours_assignes = list(Cours.objects.filter(professeur=professeur).select_related('matiere'))
    intitules_cours = [normaliser_chaine(c.matiere.nom) for c in cours_assignes if c.matiere] + [normaliser_chaine(c.code) for c in cours_assignes if c.code]

    # Récupération des emplois du temps de la semaine active ou valides
    emplois_hebdos = EmploiDuTempsHebdomadaire.objects.filter(
        statut='VALIDE',
        date_debut_semaine__lte=date_cible,
        date_fin_semaine__gte=date_cible
    ).select_related('filiere', 'salle')
    
    if not emplois_hebdos.exists():
        emplois_hebdos = EmploiDuTempsHebdomadaire.objects.filter(statut='VALIDE').select_related('filiere', 'salle')

    if not emplois_hebdos.exists():
        emplois_hebdos = EmploiDuTempsHebdomadaire.objects.all().select_related('filiere', 'salle')

    creneaux_du_jour = CreneauEmploiDuTemps.objects.filter(
        emploi_du_temps__in=emplois_hebdos,
        jour=jour_code
    ).exclude(type_evenement='PAUSE').select_related('emploi_du_temps', 'emploi_du_temps__filiere', 'emploi_du_temps__salle')

    creneaux_enseignant = []
    for c in creneaux_du_jour:
        str_ens = normaliser_chaine(c.enseignant_nom)
        str_intitule = normaliser_chaine(c.intitule)
        
        est_correspondu = False
        
        # 1. Matching sur le nom du professeur
        if str_ens and mots_cles:
            mots_slot = set(str_ens.split())
            if mots_cles.intersection(mots_slot):
                est_correspondu = True
                
        # 2. Matching sur l'intitulé de la matière/cours
        if not est_correspondu and str_intitule and intitules_cours:
            for ic in intitules_cours:
                if ic in str_intitule or str_intitule in ic:
                    est_correspondu = True
                    break

        if est_correspondu:
            c.horaire_libelle = PLAGE_HORAIRES.get(c.plage, c.get_plage_display())
            creneaux_enseignant.append(c)

    # Tri par tranche horaire chronologique P1 -> P2 -> P3 -> P4
    creneaux_enseignant.sort(key=lambda c: (PLAGE_ORDER.get(c.plage, 99), c.emploi_du_temps.filiere.code if c.emploi_du_temps and c.emploi_du_temps.filiere else ''))

    return {
        'date': date_cible,
        'nom_jour': nom_jour,
        'jour_code': jour_code,
        'creneaux': creneaux_enseignant
    }

