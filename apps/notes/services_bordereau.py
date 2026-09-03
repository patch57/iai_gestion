"""
Service de calcul matriciel complet pour le Bordereau de Notes et Délibérations Officiel IAI-Cameroun.
Conforme au format d'origine (Bordereau Excel avec UEs, Matières, Mentions V/NV, Rangs, Crédits et Décisions).
IAI-Cameroun - Centre de Douala
"""
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.db.models import Q
from apps.notes.models import UniteEnseignement, Matiere, Note, Cours, Bulletin, DetailBulletin
from apps.etudiants.models import Etudiant, Classe


def arrondir_note(valeur, decimales=2):
    """Arrondit proprement une valeur numérique."""
    if valeur is None:
        return 0.0
    d = Decimal(str(valeur))
    fmt = '0.' + '0' * decimales if decimales > 0 else '0'
    return float(d.quantize(Decimal(fmt), rounding=ROUND_HALF_UP))


def calculer_bordereau_matrice(classe, semestre=1):
    """
    Génère la matrice complète du Bordereau de Notes pour une classe et un semestre donnés.
    Structure de retour :
    {
        'header': { ... },
        'ues': [ { 'code': ..., 'nom': ..., 'matieres': [...], 'total_credits': X }, ... ],
        'etudiants_rows': [ { 'etudiant': ..., 'ues_data': { ue_id: { 'matieres': { mat_id: note }, 'moyenne': X, 'mention': 'V'/'NV' } }, 'stats': { ... } }, ... ],
        'statistiques': { 'total_etudiants': N, 'taux_reussite': %, 'admis': A, 'ajournes': B, 'moyennes_matieres': { ... } }
    }
    """
    filiere = classe.filiere
    niveau = classe.niveau
    annee_academique = classe.annee_academique.code if classe.annee_academique else '2025-2026'

    is_annuel = str(semestre).lower() in ['annuel', 'annual', '3', '0']

    # 1. Récupération des UEs rattachées à la filière/niveau ou globales
    ues_qs = UniteEnseignement.objects.filter(
        Q(filiere=filiere, niveau=niveau) | Q(filiere__isnull=True, niveau__isnull=True) | Q(filiere=filiere, niveau__isnull=True)
    ).distinct().order_by('code')

    ues_structure = []
    matieres_all = []
    
    for ue in ues_qs:
        if is_annuel:
            matieres = list(Matiere.objects.filter(unite_enseignement=ue, est_actif=True).order_by('semestre', 'code'))
        else:
            try:
                sem_int = int(semestre)
            except (ValueError, TypeError):
                sem_int = 1
            matieres = list(Matiere.objects.filter(unite_enseignement=ue, semestre=sem_int, est_actif=True).order_by('code'))
            if not matieres:
                matieres = list(Matiere.objects.filter(unite_enseignement=ue, est_actif=True).order_by('code'))
            
        if matieres:
            total_credits_ue = sum(m.credit for m in matieres)
            ues_structure.append({
                'id': ue.id,
                'code': ue.code,
                'nom': ue.nom,
                'matieres': matieres,
                'total_credits': total_credits_ue
            })
            matieres_all.extend(matieres)

    # Si aucune UE spécifique n'est trouvée, récupérer les matières directement par semestre
    if not ues_structure:
        if is_annuel:
            matieres_orphelines = list(Matiere.objects.filter(est_actif=True).order_by('semestre', 'code'))
            sem_code = "UE_ANNUEL"
        else:
            try:
                sem_int = int(semestre)
            except (ValueError, TypeError):
                sem_int = 1
            matieres_orphelines = list(Matiere.objects.filter(semestre=sem_int, est_actif=True).order_by('code'))
            sem_code = f"UE_S{sem_int}"

        if matieres_orphelines:
            ues_structure.append({
                'id': 0,
                'code': sem_code,
                'nom': 'Enseignements Généraux',
                'matieres': matieres_orphelines,
                'total_credits': sum(m.credit for m in matieres_orphelines)
            })
            matieres_all.extend(matieres_orphelines)

    # 2. Liste des étudiants de la classe
    etudiants = list(classe.etudiants.filter(est_actif=True).order_by('nom', 'prenom'))

    # 3. Préchargement des notes
    cours_qs = Cours.objects.filter(filiere=filiere, niveau=niveau, annee_academique=annee_academique)
    evaluations_qs = []
    for c in cours_qs:
        evaluations_qs.extend(c.evaluations.all())

    notes_qs = Note.objects.filter(
        etudiant__in=etudiants,
        evaluation__in=evaluations_qs
    ).select_related('evaluation', 'evaluation__cours', 'evaluation__cours__matiere', 'evaluation__type_evaluation')

    # Dictionnaire des notes: etudiant_id -> matiere_id -> { 'CC': val, 'EXAM': val, 'RATT': val }
    notes_dict = {}
    for n in notes_qs:
        eid = n.etudiant_id
        mid = n.evaluation.cours.matiere_id
        code_type = n.evaluation.type_evaluation.code.upper()
        
        if eid not in notes_dict:
            notes_dict[eid] = {}
        if mid not in notes_dict[eid]:
            notes_dict[eid][mid] = {}
        notes_dict[eid][mid][code_type] = float(n.valeur)

    # 4. Calcul par étudiant
    etudiants_rows = []

    for et in etudiants:
        et_notes = notes_dict.get(et.id, {})
        ues_data = {}
        total_points_cumules = 0.0
        total_credits_possibles = 0
        total_credits_capitalises = 0
        notes_matiere_flat = {}

        ues_list = []

        for ue_item in ues_structure:
            ue_id = ue_item['id']
            ue_matieres_data = {}
            matieres_list = []
            pts_ue = 0.0
            creds_ue = 0

            for mat in ue_item['matieres']:
                m_dict = et_notes.get(mat.id, {})
                cc = m_dict.get('CC') or m_dict.get('CONTROLE')
                exam = m_dict.get('EXAM') or m_dict.get('EXAMEN')
                ratt = m_dict.get('RATT') or m_dict.get('RATTRAPAGE')

                # Logique de note finale
                note_exam = ratt if ratt is not None else (exam if exam is not None else 0.0)
                note_cc = cc if cc is not None else 0.0

                if cc is None and exam is None and ratt is None:
                    note_finale = 0.0
                else:
                    note_finale = (note_cc * 0.4) + (note_exam * 0.6)

                note_finale = arrondir_note(note_finale, 2)
                coef = mat.credit
                pts_mat = note_finale * coef

                mat_info = {
                    'matiere_id': mat.id,
                    'code': mat.code,
                    'note': note_finale,
                    'pts': pts_mat,
                    'credit': coef
                }
                ue_matieres_data[mat.id] = mat_info
                matieres_list.append(mat_info)

                notes_matiere_flat[mat.id] = note_finale
                pts_ue += pts_mat
                creds_ue += coef

            moyenne_ue = (pts_ue / creds_ue) if creds_ue > 0 else 0.0
            moyenne_ue = arrondir_note(moyenne_ue, 2)
            mention_ue = 'V' if moyenne_ue >= 10.0 else 'NV'

            if mention_ue == 'V':
                total_credits_capitalises += creds_ue

            total_points_cumules += pts_ue
            total_credits_possibles += creds_ue

            ue_summary = {
                'ue_id': ue_id,
                'matieres': ue_matieres_data,
                'matieres_list': matieres_list,
                'moyenne': moyenne_ue,
                'mention': mention_ue,
                'points': pts_ue,
                'credits': creds_ue
            }
            ues_data[ue_id] = ue_summary
            ues_list.append(ue_summary)

        moyenne_generale = (total_points_cumules / total_credits_possibles) if total_credits_possibles > 0 else 0.0
        moyenne_generale = arrondir_note(moyenne_generale, 3)

        decision = 'ADMIS' if moyenne_generale >= 10.0 else 'AJOURNÉ'

        etudiants_rows.append({
            'etudiant': et,
            'ues_data': ues_data,
            'ues_list': ues_list,
            'notes_matiere_flat': notes_matiere_flat,
            'total_points': arrondir_note(total_points_cumules, 2),
            'moyenne': moyenne_generale,
            'credits_possibles': total_credits_possibles,
            'credits_capitalises': total_credits_capitalises,
            'absences': getattr(et, 'absences_heures', 0),
            'retards': getattr(et, 'retards_nombre', 0),
            'discipline': getattr(et, 'conduite_statut', '—'),
            'decision': decision,
            'rang': 1  # Sera mis à jour ci-dessous
        })

    # 5. Calcul des rangs
    etudiants_rows.sort(key=lambda x: x['moyenne'], reverse=True)
    for idx, row in enumerate(etudiants_rows, start=1):
        row['rang'] = idx

    # Re-tri par nom/prénom pour l'affichage officiel du bordereau
    etudiants_rows.sort(key=lambda x: (x['etudiant'].nom, x['etudiant'].prenom))

    # 6. Moyennes par matière et par UE sur la classe
    moyennes_matieres = {}
    for mat in matieres_all:
        notes_m = [r['notes_matiere_flat'][mat.id] for r in etudiants_rows if mat.id in r['notes_matiere_flat'] and r['notes_matiere_flat'][mat.id] is not None]
        moy = (sum(notes_m) / len(notes_m)) if notes_m else 0.0
        moyennes_matieres[mat.id] = arrondir_note(moy, 2)

    moyennes_ues = {}
    for ue_item in ues_structure:
        ue_id = ue_item['id']
        notes_ue = [r['ues_data'][ue_id]['moyenne'] for r in etudiants_rows if ue_id in r['ues_data']]
        moy = (sum(notes_ue) / len(notes_ue)) if notes_ue else 0.0
        moyennes_ues[ue_id] = arrondir_note(moy, 2)

    total_etudiants = len(etudiants_rows)
    nb_admis = sum(1 for r in etudiants_rows if r['decision'] == 'ADMIS')
    taux_reussite = (nb_admis / total_etudiants * 100) if total_etudiants > 0 else 0.0

    # 7. Découpage horizontal intelligent par tranches de 3 UEs (conforme modèle PDF IAI-Cameroun)
    chunk_size = 3
    ue_chunks = []
    if ues_structure:
        for i in range(0, len(ues_structure), chunk_size):
            chunk_ues = ues_structure[i:i + chunk_size]
            is_last = (i + chunk_size >= len(ues_structure))

            chunk_etudiants_rows = []
            for r in etudiants_rows:
                chunk_ues_list = [r['ues_data'][u['id']] for u in chunk_ues if u['id'] in r['ues_data']]
                chunk_etudiants_rows.append({
                    'etudiant': r['etudiant'],
                    'ues_list': chunk_ues_list,
                    'total_points': r['total_points'],
                    'moyenne': r['moyenne'],
                    'rang': r['rang'],
                    'credits_possibles': r['credits_possibles'],
                    'credits_capitalises': r['credits_capitalises'],
                    'absences': r['absences'],
                    'retards': r['retards'],
                    'discipline': r['discipline'],
                    'decision': r['decision'],
                })

            ue_chunks.append({
                'chunk_index': len(ue_chunks) + 1,
                'ues': chunk_ues,
                'etudiants_rows': chunk_etudiants_rows,
                'is_last_chunk': is_last,
            })
    else:
        ue_chunks.append({
            'chunk_index': 1,
            'ues': [],
            'etudiants_rows': etudiants_rows,
            'is_last_chunk': True,
        })

    return {
        'header': {
            'campus': 'Douala',
            'niveau': f"Niveau {niveau.numero if niveau else 1}",
            'classe': classe.nom,
            'filiere': filiere.nom if filiere else '',
            'annee_academique': annee_academique,
            'semestre': 'ANNUEL (S1 + S2)' if is_annuel else f"SEMESTRE {semestre}",
            'date_impression': timezone.now().strftime('%d/%m/%Y %H:%M')
        },
        'ues': ues_structure,
        'ue_chunks': ue_chunks,
        'matieres_all': matieres_all,
        'etudiants_rows': etudiants_rows,
        'statistiques': {
            'total_etudiants': total_etudiants,
            'nb_admis': nb_admis,
            'nb_ajournes': total_etudiants - nb_admis,
            'taux_reussite': arrondir_note(taux_reussite, 1),
            'moyennes_matieres': moyennes_matieres,
            'moyennes_ues': moyennes_ues,
        }
    }


def publier_bulletins_classe(classe, semestre, user_publieur):
    """
    Génère et publie officiellement les bulletins individuels pour une classe et un semestre.
    """
    matrice = calculer_bordereau_matrice(classe, semestre)
    annee_code = classe.annee_academique.code if classe.annee_academique else '2025-2026'

    bulletins_crees = 0
    for row in matrice['etudiants_rows']:
        et = row['etudiant']
        sem_val = 3 if str(semestre).lower() in ['annuel', 'annual', '3', '0'] else int(semestre)
        bulletin, created = Bulletin.objects.update_or_create(
            etudiant=et,
            annee_academique=annee_code,
            semestre=sem_val,
            defaults={
                'moyenne_semestre': Decimal(str(row['moyenne'])),
                'credits_obtenus': row['credits_capitalises'],
                'credits_totaux': row['credits_possibles'],
                'rang': row['rang'],
                'effectif': matrice['statistiques']['total_etudiants'],
                'decision': row['decision'],
                'absences': row['absences'],
                'retards': row['retards'],
                'discipline': row['discipline'],
                'est_publie': True,
                'date_publication': timezone.now(),
                'valide_par': user_publieur,
                'est_valide': True,
                'date_validation': timezone.now()
            }
        )
        bulletins_crees += 1

    return bulletins_crees
