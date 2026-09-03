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


def synchroniser_fiche_presence_automatique(fiche):
    """
    Synchronise les présences sur la fiche hebdomadaire à partir des séances de cours (Presence),
    TOUT EN CONSERVANT l'historique et les données déjà saisies ou importées sur la fiche.
    """
    if not fiche or not fiche.semaine_du:
        return

    from datetime import timedelta
    from apps.cours.models import Presence, LignePresenceHebdomadaire
    from apps.etudiants.models import Etudiant
    import json

    date_lundi = fiche.semaine_du
    jours_map = {0: 'lun', 1: 'mar', 2: 'mer', 3: 'jeu', 4: 'ven', 5: 'sam'}

    etudiants = list(fiche.classe.etudiants.filter(statut__in=['INSCRIT', 'ACTIF']).order_by('nom', 'prenom')) if fiche.classe else []
    if not etudiants and fiche.filiere and fiche.niveau:
        etudiants = list(Etudiant.objects.filter(filiere=fiche.filiere, niveau=fiche.niveau, statut__in=['INSCRIT', 'ACTIF']).order_by('nom', 'prenom'))

    for etudiant in etudiants:
        ligne, created = LignePresenceHebdomadaire.objects.get_or_create(
            fiche=fiche,
            etudiant=etudiant
        )
        
        # Récupérer les données existantes de la ligne
        existing_grid = {}
        if ligne.details_jours_json:
            try:
                existing_grid = json.loads(ligne.details_jours_json)
            except Exception:
                existing_grid = {}

        grid_data = {}
        total_absences = 0
        has_seance_presence = False

        for i in range(6):
            date_jour = date_lundi + timedelta(days=i)
            code_jour = jours_map[i]
            
            # Vérifier si des séances de cours réelles avec présence existent pour cette date
            presences_seance = Presence.objects.filter(
                etudiant=etudiant,
                seance__date=date_jour
            )
            
            if presences_seance.exists():
                has_seance_presence = True
                absences_count = presences_seance.filter(statut='ABSENT').count()
                slots = ['A' for _ in range(absences_count)]
                grid_data[code_jour] = slots
                total_absences += absences_count
            else:
                # Conserver les données existantes sur la ligne s'il n'y a pas de séance explicite enregistrée
                existing_slots = existing_grid.get(code_jour, [])
                grid_data[code_jour] = existing_slots
                if isinstance(existing_slots, list):
                    total_absences += sum(1 for val in existing_slots if str(val).strip().upper() == 'A')

        if has_seance_presence or created or not ligne.nombre_absences:
            ligne.nombre_absences = total_absences
            ligne.details_jours_json = json.dumps(grid_data)
            ligne.save()


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


def calculer_stats_seances_enseignant(user):
    """
    Calcule automatiquement et dynamiquement les statistiques de séances d'un enseignant :
    - seances_hebdo : nombre de séances hebdomadaires d'un enseignant d'après l'emploi du temps hebdomadaire officiel
    - heures_hebdo : nombre d'heures par semaine (seances_hebdo * 2h)
    - seances_total : nombre total de séances programmées sur l'année/semestre
    - seances_effectuees : nombre de séances où l'enseignant a été pointé 'PRESENT' par le Chef de la Scolarité
    - taux_realisation : % effectif accompli
    """
    from apps.cours.models import CreneauEmploiDuTemps, EmploiDuTempsHebdomadaire, PointagePresenceEnseignant, SeanceCours, Cours
    from apps.professeurs.models import Professeur
    
    professeur = None
    if isinstance(user, Professeur):
        professeur = user
        user = professeur.utilisateur
    elif hasattr(user, 'type_utilisateur'):
        professeur = Professeur.objects.filter(utilisateur=user).first()
        
    if not professeur and not user:
        return {
            'seances_hebdo': 0,
            'heures_hebdo': 0,
            'seances_total': 0,
            'seances_effectuees': 0,
            'taux_realisation': 0.0
        }

    # 1. Identifier tous les emplois du temps hebdomadaires validés par le Chef des Études
    emplois_valides = EmploiDuTempsHebdomadaire.objects.filter(statut='VALIDE')
    if not emplois_valides.exists():
        emplois_valides = EmploiDuTempsHebdomadaire.objects.all()

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

    cours_assignes = list(Cours.objects.filter(professeur=professeur).select_related('matiere')) if professeur else []
    intitules_cours = [normaliser_chaine(c.matiere.nom) for c in cours_assignes if c.matiere] + [normaliser_chaine(c.code) for c in cours_assignes if c.code]

    nb_semaines = emplois_valides.values('date_debut_semaine').distinct().count() or 1

    seances_hebdo_set = set()
    seances_total = 0

    if emplois_valides.exists():
        tous_creneaux = CreneauEmploiDuTemps.objects.filter(
            emploi_du_temps__in=emplois_valides
        ).exclude(type_evenement='PAUSE').select_related('emploi_du_temps', 'emploi_du_temps__filiere')
        
        for c in tous_creneaux:
            str_ens = normaliser_chaine(c.enseignant_nom)
            str_intitule = normaliser_chaine(c.intitule)
            match = False
            if str_ens and mots_cles:
                if mots_cles.intersection(set(str_ens.split())):
                    match = True
            if not match and str_intitule and intitules_cours:
                for ic in intitules_cours:
                    if ic in str_intitule or str_intitule in ic:
                        match = True
                        break
            if match:
                seances_total += 1
                filiere_code = c.emploi_du_temps.filiere.code if c.emploi_du_temps and c.emploi_du_temps.filiere else ''
                seances_hebdo_set.add((filiere_code, c.jour, c.plage, str_intitule))

    seances_hebdo = len(seances_hebdo_set)

    # Fallback si pas de créneaux dans l'emploi du temps hebdomadaire
    if seances_hebdo == 0 and professeur:
        cours_qs = Cours.objects.filter(professeur=professeur)
        seances_hebdo = cours_qs.count()
        if seances_total == 0:
            seances_total = sum(c.volume_horaire // 2 for c in cours_qs if hasattr(c, 'volume_horaire') and c.volume_horaire) or (seances_hebdo * 15)

    if seances_total == 0:
        seances_total = seances_hebdo * max(1, nb_semaines)

    heures_hebdo = seances_hebdo * 2

    # 2. Séances effectuées (pointages "PRESENT" du Chef de la Scolarité ou SeanceCours.est_effectuee)
    seances_effectuees = 0
    if professeur:
        seances_effectuees = PointagePresenceEnseignant.objects.filter(
            enseignant=professeur,
            statut='PRESENT'
        ).count()
        
        if seances_effectuees == 0:
            cours_qs = Cours.objects.filter(professeur=professeur)
            seances_effectuees = SeanceCours.objects.filter(cours__in=cours_qs, est_effectuee=True).count()
    elif user:
        seances_effectuees = PointagePresenceEnseignant.objects.filter(
            enseignant__utilisateur=user,
            statut='PRESENT'
        ).count()

    taux = round((seances_effectuees / seances_total * 100), 1) if seances_total > 0 else 0.0

    return {
        'seances_hebdo': seances_hebdo,
        'heures_hebdo': heures_hebdo,
        'seances_total': seances_total,
        'seances_effectuees': seances_effectuees,
        'taux_realisation': float(taux),
    }


def synchroniser_fiche_presence_enseignant_auto(emploi_du_temps=None, user=None):
    """
    Création/Synchronisation automatique d'une Fiche Hebdo Émargement & Présence Enseignants
    déclenchée dès que le Chef des Études soumet, publie ou importe un nouvel emploi du temps.
    """
    from datetime import timedelta
    from django.utils import timezone
    from apps.cours.models import FichePresenceEnseignantHebdo, PointagePresenceEnseignant, CreneauEmploiDuTemps, EmploiDuTempsHebdomadaire
    from apps.professeurs.models import Professeur
    from apps.etudiants.models import AnneeAcademique
    from apps.inscriptions.utils import get_current_academic_year_code

    if emploi_du_temps:
        semaine_du = emploi_du_temps.date_debut_semaine
        semaine_au = emploi_du_temps.date_fin_semaine
    else:
        today = timezone.now().date()
        semaine_du = today - timedelta(days=today.weekday())
        semaine_au = semaine_du + timedelta(days=5)

    annee_active = AnneeAcademique.get_active()
    annee_code = annee_active.code if annee_active else get_current_academic_year_code()

    fiche, created = FichePresenceEnseignantHebdo.objects.get_or_create(
        semaine_du=semaine_du,
        defaults={
            'semaine_au': semaine_au,
            'annee_academique': annee_code,
            'rempli_par': user,
            'statut': 'BROUILLON'
        }
    )

    if not created and fiche.annee_academique != annee_code:
        fiche.annee_academique = annee_code
        fiche.save(update_fields=['annee_academique'])

    # Récupérer les emplois du temps de cette semaine
    if emploi_du_temps:
        emplois = EmploiDuTempsHebdomadaire.objects.filter(
            date_debut_semaine=semaine_du
        )
    else:
        emplois = EmploiDuTempsHebdomadaire.objects.filter(statut='VALIDE')
        if not emplois.exists():
            emplois = EmploiDuTempsHebdomadaire.objects.all()

    creneaux = CreneauEmploiDuTemps.objects.filter(emploi_du_temps__in=emplois).exclude(type_evenement='PAUSE')
    professeurs = Professeur.objects.filter(est_actif=True)

    pointages_crees = 0
    for prof in professeurs:
        mots_cles = set()
        if prof.nom: mots_cles.update(normaliser_chaine(prof.nom).split())
        if prof.prenom: mots_cles.update(normaliser_chaine(prof.prenom).split())
        mots_cles = {m for m in mots_cles if len(m) > 2 and m not in ['mme', 'prof', 'docteur', 'monsieur']}

        for c in creneaux:
            str_ens = normaliser_chaine(c.enseignant_nom)
            if str_ens and mots_cles and mots_cles.intersection(set(str_ens.split())):
                p, p_created = PointagePresenceEnseignant.objects.get_or_create(
                    fiche=fiche,
                    enseignant=prof,
                    creneau=c,
                    date_seance=semaine_du,
                    defaults={'statut': 'PRESENT'}
                )
                if p_created:
                    pointages_crees += 1

    return fiche, created, pointages_crees


