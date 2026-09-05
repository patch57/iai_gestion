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

    # 1. Détermination stricte des matières rattachées à cette filière / niveau / classe
    from apps.notes.models import Cours as NotesCours, FicheNotesAnonymat, ProcesVerbalNotes
    from apps.cours.models import Cours as CoursApp

    # (a) Matières officielles rattachées aux UEs de cette filière et de ce niveau
    ues_qs = UniteEnseignement.objects.filter(filiere=filiere, niveau=niveau).distinct()
    matieres_curriculum = set(Matiere.objects.filter(unite_enseignement__in=ues_qs, est_actif=True).values_list('id', flat=True)) if ues_qs.exists() else set()

    # (b) Matières officielles programmées en Cours pour cette filière et ce niveau
    matieres_cours = set(NotesCours.objects.filter(filiere=filiere, niveau=niveau).values_list('matiere_id', flat=True))
    salle_obj = getattr(classe, 'salle', None)
    if salle_obj:
        matieres_cours.update(CoursApp.objects.filter(filiere=filiere, salle=salle_obj).values_list('matiere_id', flat=True))

    matieres_ids = matieres_curriculum | matieres_cours

    # (c) Si AUCUNE matière officielle (UE / Cours) n'est définie pour ce niveau, rechercher les Fiches/PVs créés spécifiquement pour la classe
    if not matieres_ids:
        nom_classe = getattr(classe, 'nom', '')
        if salle_obj:
            salle_filter = Q(salle=salle_obj)
        elif nom_classe:
            salle_filter = Q(salle__nom__icontains=nom_classe) | Q(salle__code__icontains=nom_classe)
        else:
            salle_filter = Q(salle__isnull=True)

        matieres_ids.update(FicheNotesAnonymat.objects.filter(
            salle_filter, filiere=filiere, niveau=niveau
        ).values_list('matiere_id', flat=True))
        matieres_ids.update(ProcesVerbalNotes.objects.filter(
            salle_filter, filiere=filiere, niveau=niveau
        ).values_list('matiere_id', flat=True))

        etudiants_classe = list(classe.etudiants.filter(est_actif=True).order_by('nom', 'prenom'))
        etudiants_ids = [e.id for e in etudiants_classe]
        if etudiants_ids:
            matieres_ids.update(Note.objects.filter(etudiant_id__in=etudiants_ids).values_list('evaluation__cours__matiere_id', flat=True))

    matieres_ids = {m_id for m_id in matieres_ids if m_id is not None}

    # Sélection et filtrage des matières actives par semestre
    if is_annuel:
        matieres_qs = Matiere.objects.filter(id__in=matieres_ids, est_actif=True).order_by('semestre', 'code')
    else:
        try:
            sem_int = int(semestre)
        except (ValueError, TypeError):
            sem_int = 1
        matieres_qs = Matiere.objects.filter(id__in=matieres_ids, semestre=sem_int, est_actif=True).order_by('code')

    matieres_all = list(matieres_qs)
    ues_structure = []

    # Regroupement des matières par UE s'il y en a
    ue_ids = set(m.unite_enseignement_id for m in matieres_all if m.unite_enseignement_id)
    if ue_ids:
        ues_defined = UniteEnseignement.objects.filter(id__in=ue_ids).order_by('code')
        for ue in ues_defined:
            mats_ue = [m for m in matieres_all if m.unite_enseignement_id == ue.id]
            if mats_ue:
                total_credits_ue = sum(m.credit for m in mats_ue)
                ues_structure.append({
                    'id': ue.id,
                    'code': ue.code,
                    'nom': ue.nom,
                    'matieres': mats_ue,
                    'total_credits': total_credits_ue
                })

    # Matières orphelines (sans UE)
    mats_sans_ue = [m for m in matieres_all if not m.unite_enseignement_id]
    if mats_sans_ue:
        sem_code = "UE_ANNUEL" if is_annuel else f"UE_S{semestre}"
        ues_structure.append({
            'id': 0,
            'code': sem_code,
            'nom': 'Enseignements Généraux',
            'matieres': mats_sans_ue,
            'total_credits': sum(m.credit for m in mats_sans_ue)
        })

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

    # 3b. Préchargement des Détails de Bulletin (remplis depuis les PVs)
    details_qs = DetailBulletin.objects.filter(
        bulletin__etudiant__in=etudiants
    ).select_related('bulletin', 'matiere')

    details_dict = {}
    for d in details_qs:
        eid = d.bulletin.etudiant_id
        mid = d.matiere_id
        mcode = d.matiere.code.strip().upper() if (d.matiere and d.matiere.code) else None
        val_mat = float(d.moyenne_matiere) if d.moyenne_matiere is not None else 0.0
        
        details_dict[(eid, mid)] = val_mat
        if mcode:
            details_dict[(eid, mcode)] = val_mat

    # 3c. Préchargement des PVs validés/transmis
    from apps.notes.models import LigneProcesVerbalNotes
    lignes_pv_qs = LigneProcesVerbalNotes.objects.filter(
        etudiant__in=etudiants,
        pv__est_transmis=True
    ).select_related('pv', 'pv__matiere')

    pvs_dict = {}
    for l in lignes_pv_qs:
        eid = l.etudiant_id
        mid = l.pv.matiere_id if l.pv else None
        mcode = l.pv.matiere.code.strip().upper() if (l.pv and l.pv.matiere and l.pv.matiere.code) else None
        val_pv = float(l.note_finale) if l.note_finale is not None else 0.0

        if mid:
            pvs_dict[(eid, mid)] = val_pv
        if mcode:
            pvs_dict[(eid, mcode)] = val_pv

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

                m_code_key = mat.code.strip().upper() if getattr(mat, 'code', None) else ''

                # Logique de note finale avec fallbacks sur DetailBulletin et PVs transmis
                if cc is not None or exam is not None or ratt is not None:
                    note_exam = ratt if ratt is not None else (exam if exam is not None else 0.0)
                    note_cc = cc if cc is not None else 0.0
                    note_calc = (note_cc * 0.4) + (note_exam * 0.6)
                    if note_calc == 0.0 and ((et.id, mat.id) in details_dict or (et.id, m_code_key) in details_dict or (et.id, mat.id) in pvs_dict or (et.id, m_code_key) in pvs_dict):
                        note_finale = details_dict.get((et.id, mat.id), details_dict.get((et.id, m_code_key), pvs_dict.get((et.id, mat.id), pvs_dict.get((et.id, m_code_key), 0.0))))
                    else:
                        note_finale = note_calc
                elif (et.id, mat.id) in details_dict or (et.id, m_code_key) in details_dict:
                    note_finale = details_dict.get((et.id, mat.id), details_dict.get((et.id, m_code_key), 0.0))
                elif (et.id, mat.id) in pvs_dict or (et.id, m_code_key) in pvs_dict:
                    note_finale = pvs_dict.get((et.id, mat.id), pvs_dict.get((et.id, m_code_key), 0.0))
                else:
                    note_finale = 0.0

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
