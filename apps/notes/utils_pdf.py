"""
Service de génération et d'archivage des bulletins officiels IAI-Cameroun
"""
import os
import io
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from django.db.models import Avg, Max, Min

from apps.notes.models import Bulletin, DetailBulletin, Note, Matiere, UniteEnseignement, Cours
from apps.etudiants.models import Etudiant, Classe


def structurer_donnees_bulletin(etudiant, classe):
    """
    Construit le contexte complet des données pour un bulletin officiel S1+S2
    conforme au modèle physique IAI-Cameroun téléversé.
    """
    filiere = classe.filiere
    niveau = classe.niveau
    annee_academique = classe.annee_academique.code

    # Récupération de l'ensemble des étudiants de la classe pour le calcul des rangs et min/max
    tous_etudiants = list(classe.etudiants.filter(statut__in=['INSCRIT', 'ACTIF']))
    
    # Charger les cours de la classe
    cours_classe = Cours.objects.filter(filiere=filiere, niveau=niveau, annee_academique=annee_academique)
    evaluations_cours = []
    for c in cours_classe:
        evaluations_cours.extend(c.evaluations.all())

    # Precharger les UEs de la filière et du niveau
    ues_qs = UniteEnseignement.objects.filter(filiere=filiere, niveau=niveau).prefetch_related('matieres')
    ues_all = list(ues_qs)

    # Récupérer toutes les notes des étudiants de cette classe
    notes_qs = Note.objects.filter(
        etudiant__in=tous_etudiants,
        evaluation__in=evaluations_cours,
        est_validee=True
    ).select_related('etudiant', 'evaluation', 'evaluation__cours', 'evaluation__cours__matiere', 'evaluation__type_evaluation')

    # Dictionnaire des notes : dict[etudiant_id][matiere_code][type_code] = valeur
    notes_map = {}
    for n in notes_qs:
        eid = n.etudiant_id
        mcode = n.evaluation.cours.matiere.code
        tcode = n.evaluation.type_evaluation.code
        if eid not in notes_map:
            notes_map[eid] = {}
        if mcode not in notes_map[eid]:
            notes_map[eid][mcode] = {}
        notes_map[eid][mcode][tcode] = float(n.valeur)

    # Precharger les Détails de Bulletins (remplis depuis les PVs)
    from apps.notes.models import DetailBulletin, LigneProcesVerbalNotes
    details_qs = DetailBulletin.objects.filter(
        bulletin__etudiant__in=tous_etudiants
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

    # Precharger les PVs validés/transmis
    lignes_pv_qs = LigneProcesVerbalNotes.objects.filter(
        etudiant__in=tous_etudiants,
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

    # Fonction d'extraction des données d'un étudiant
    def calculer_bilan_etudiant(et):
        et_notes = notes_map.get(et.id, {})
        
        s1_ues = []
        s2_ues = []
        
        s1_pts, s1_coefs, s1_creds = 0.0, 0.0, 0
        s2_pts, s2_coefs, s2_creds = 0.0, 0.0, 0
        s1_rows_count = 0
        s2_rows_count = 0

        for ue in ues_all:
            matieres_ue = list(ue.matieres.all())
            if not matieres_ue:
                continue

            ue_matieres_s1 = []
            ue_matieres_s2 = []
            
            ue_s1_pts, ue_s1_coef = 0.0, 0.0
            ue_s2_pts, ue_s2_coef = 0.0, 0.0

            for mat in matieres_ue:
                mat_n = et_notes.get(mat.code, {})
                cc = mat_n.get('CC')
                exam = mat_n.get('EXAM')
                ratt = mat_n.get('RATT')

                mcode_key = mat.code.strip().upper() if getattr(mat, 'code', None) else ''

                if cc is not None or exam is not None or ratt is not None:
                    exam_final = ratt if ratt is not None else (exam if exam is not None else 0.0)
                    cc_final = cc if cc is not None else 0.0
                    note_calc = (cc_final * 0.4) + (exam_final * 0.6)
                    if note_calc == 0.0 and ((et.id, mat.id) in details_dict or (et.id, mcode_key) in details_dict or (et.id, mat.id) in pvs_dict or (et.id, mcode_key) in pvs_dict):
                        note_finale = details_dict.get((et.id, mat.id), details_dict.get((et.id, mcode_key), pvs_dict.get((et.id, mat.id), pvs_dict.get((et.id, mcode_key), 0.0))))
                    else:
                        note_finale = note_calc
                elif (et.id, mat.id) in details_dict or (et.id, mcode_key) in details_dict:
                    note_finale = details_dict.get((et.id, mat.id), details_dict.get((et.id, mcode_key), 0.0))
                elif (et.id, mat.id) in pvs_dict or (et.id, mcode_key) in pvs_dict:
                    note_finale = pvs_dict.get((et.id, mat.id), pvs_dict.get((et.id, mcode_key), 0.0))
                else:
                    note_finale = 0.0

                note_finale = round(note_finale, 2)
                coef = float(mat.credit)
                total_mat = round(note_finale * coef, 2)

                mat_dict = {
                    'matiere': mat,
                    'code': mat.code,
                    'nom': mat.nom,
                    'note': note_finale,
                    'note_format': f"{note_finale:.2f}".replace('.', ','),
                    'coef': int(coef),
                    'total': total_mat,
                    'total_format': f"{total_mat:.2f}".replace('.', ','),
                    'session': 'Rattrapage' if ratt is not None else 'Normale'
                }

                if mat.semestre == 1:
                    ue_matieres_s1.append(mat_dict)
                    ue_s1_pts += total_mat
                    ue_s1_coef += coef
                    s1_pts += total_mat
                    s1_coefs += coef
                    if note_finale >= 10.0:
                        s1_creds += mat.credit
                else:
                    ue_matieres_s2.append(mat_dict)
                    ue_s2_pts += total_mat
                    ue_s2_coef += coef
                    s2_pts += total_mat
                    s2_coefs += coef
                    if note_finale >= 10.0:
                        s2_creds += mat.credit

            if ue_matieres_s1:
                moy_ue_s1 = round(ue_s1_pts / ue_s1_coef, 2) if ue_s1_coef > 0 else 0.0
                s1_rows_count += len(ue_matieres_s1)
                s1_ues.append({
                    'ue': ue,
                    'matieres': ue_matieres_s1,
                    'moyenne_ue': moy_ue_s1,
                    'moyenne_ue_format': f"{moy_ue_s1:.2f}".replace('.', ','),
                    'mention_ue': 'VALIDEE' if moy_ue_s1 >= 10.0 else 'NON VALIDEE',
                    'credits_ue': sum(m['coef'] for m in ue_matieres_s1 if m['note'] >= 10.0)
                })

            if ue_matieres_s2:
                moy_ue_s2 = round(ue_s2_pts / ue_s2_coef, 2) if ue_s2_coef > 0 else 0.0
                s2_rows_count += len(ue_matieres_s2)
                s2_ues.append({
                    'ue': ue,
                    'matieres': ue_matieres_s2,
                    'moyenne_ue': moy_ue_s2,
                    'moyenne_ue_format': f"{moy_ue_s2:.2f}".replace('.', ','),
                    'mention_ue': 'VALIDEE' if moy_ue_s2 >= 10.0 else 'NON VALIDEE',
                    'credits_ue': sum(m['coef'] for m in ue_matieres_s2 if m['note'] >= 10.0)
                })

        moy_s1 = round(s1_pts / s1_coefs, 2) if s1_coefs > 0 else 0.0
        moy_s2 = round(s2_pts / s2_coefs, 2) if s2_coefs > 0 else 0.0
        
        tot_pts = s1_pts + s2_pts
        tot_coefs = s1_coefs + s2_coefs
        moy_annuelle = round(tot_pts / tot_coefs, 2) if tot_coefs > 0 else 0.0

        return {
            'etudiant': et,
            's1_ues': s1_ues,
            's1_rows_count': s1_rows_count,
            's1_pts': s1_pts,
            's1_coefs': int(s1_coefs),
            's1_creds': s1_creds,
            'moy_s1': moy_s1,

            's2_ues': s2_ues,
            's2_rows_count': s2_rows_count,
            's2_pts': s2_pts,
            's2_coefs': int(s2_coefs),
            's2_creds': s2_creds,
            'moy_s2': moy_s2,

            'tot_pts': tot_pts,
            'tot_coefs': int(tot_coefs),
            'tot_creds': s1_creds + s2_creds,
            'moy_annuelle': moy_annuelle,
        }

    # Calculer les bilans de la classe pour extraire rangs et statistiques
    bilans_classe = [calculer_bilan_etudiant(e) for e in tous_etudiants]
    
    # Rangs annuels
    bilans_classe.sort(key=lambda x: x['moy_annuelle'], reverse=True)
    for rang, b in enumerate(bilans_classe, 1):
        b['rang_annuel'] = rang

    # Rangs S1
    bilans_classe.sort(key=lambda x: x['moy_s1'], reverse=True)
    for rang, b in enumerate(bilans_classe, 1):
        b['rang_s1'] = rang

    # Rangs S2
    bilans_classe.sort(key=lambda x: x['moy_s2'], reverse=True)
    for rang, b in enumerate(bilans_classe, 1):
        b['rang_s2'] = rang

    # Statistiques globales de la classe
    moyennes_annuelles = [b['moy_annuelle'] for b in bilans_classe]
    moy_gen_classe = round(sum(moyennes_annuelles) / len(moyennes_annuelles), 2) if moyennes_annuelles else 0.0
    moy_max_classe = max(moyennes_annuelles) if moyennes_annuelles else 0.0
    moy_min_classe = min(moyennes_annuelles) if moyennes_annuelles else 0.0

    # Retrouver le bilan spécifique de l'étudiant cible
    target_bilan = next((b for b in bilans_classe if b['etudiant'].id == etudiant.id), None)
    if not target_bilan:
        target_bilan = calculer_bilan_etudiant(etudiant)
        target_bilan['rang_annuel'] = 1
        target_bilan['rang_s1'] = 1
        target_bilan['rang_s2'] = 1

    # Décision du conseil des professeurs
    moy = target_bilan['moy_annuelle']
    if moy >= 10.0:
        decision = "Admis (e)"
    elif moy >= 8.5:
        decision = "Autorisé (e) à composer en Rattrapage"
    else:
        decision = "Ajourné (e)"

    from apps.cours.presence_service import calculer_total_absences_cumulees
    total_absences_cumulees = calculer_total_absences_cumulees(etudiant)

    context = {
        'etudiant': etudiant,
        'filiere': filiere,
        'niveau': niveau,
        'classe': classe,
        'annee_academique': annee_academique,
        'domaine': 'Informatique',
        
        's1_data': {
            'ues': target_bilan['s1_ues'],
            'total_rows': target_bilan['s1_rows_count'],
            'total_coef': target_bilan['s1_coefs'],
            'total_points_format': f"{target_bilan['s1_pts']:.2f}".replace('.', ','),
            'moyenne_s1_format': f"{target_bilan['moy_s1']:.2f}".replace('.', ','),
            'rang_s1': target_bilan['rang_s1'],
            'credits_s1': target_bilan['s1_creds'],
        },
        's2_data': {
            'ues': target_bilan['s2_ues'],
            'total_rows': target_bilan['s2_rows_count'],
            'total_coef': target_bilan['s2_coefs'],
            'total_points_format': f"{target_bilan['s2_pts']:.2f}".replace('.', ','),
            'moyenne_s2_format': f"{target_bilan['moy_s2']:.2f}".replace('.', ','),
            'rang_s2': target_bilan['rang_s2'],
            'credits_s2': target_bilan['s2_creds'],
        },
        'recap_data': {
            'total_coef': target_bilan['tot_coefs'],
            'total_points_format': f"{target_bilan['tot_pts']:.2f}".replace('.', ','),
            'total_credits_annuels': target_bilan['tot_creds'],
        },
        'moyenne_annuelle_format': f"{target_bilan['moy_annuelle']:.2f}".replace('.', ','),
        'moyenne_classe_generale_format': f"{moy_gen_classe:.2f}".replace('.', ','),
        'moyenne_classe_max_format': f"{moy_max_classe:.2f}".replace('.', ','),
        'moyenne_classe_min_format': f"{moy_min_classe:.2f}".replace('.', ','),
        'rang_annuel': target_bilan['rang_annuel'],
        'total_effectif': len(tous_etudiants),
        'decision_finale': decision,
        'date_edition': timezone.now(),
        'retards': 0,
        'absences': total_absences_cumulees,
        'discipline': '-',
    }
    return context


def generer_et_archiver_bulletin_pdf(etudiant, classe, user_valideur=None):
    """
    Génère le bulletin HTML/PDF, le sauvegarde sur disque dans media/bulletins/YYYY/CLASSE/
    et met à jour l'instance Bulletin en base de données.
    """
    context = structurer_donnees_bulletin(etudiant, classe)
    annee_code = classe.annee_academique.code
    
    # Créer ou récupérer le Bulletin en base de données
    bulletin, created = Bulletin.objects.get_or_create(
        etudiant=etudiant,
        annee_academique=annee_code,
        semestre=1,
        defaults={'credits_totaux': context['recap_data']['total_credits_annuels']}
    )
    
    # Mettre à jour les données calculées
    bulletin.moyenne_semestre = context['moyenne_annuelle_format'].replace(',', '.')
    bulletin.credits_obtenus = context['recap_data']['total_credits_annuels']
    bulletin.rang = context['rang_annuel']
    bulletin.effectif = context['total_effectif']
    bulletin.moyenne_classe_generale = context['moyenne_classe_generale_format'].replace(',', '.')
    bulletin.moyenne_classe_max = context['moyenne_classe_max_format'].replace(',', '.')
    bulletin.moyenne_classe_min = context['moyenne_classe_min_format'].replace(',', '.')
    bulletin.numero_bulletin = f"{bulletin.id:03d}"
    context['bulletin'] = bulletin

    # Rendu HTML du bulletin officiel
    html_content = render_to_string('notes/bulletin_officiel_pdf.html', context)

    # Répertoire d'archivage sur le serveur
    sanitized_annee = annee_code.replace('/', '_').replace('-', '_')
    sanitized_classe = classe.nom.replace(' ', '_')
    rel_dir = os.path.join('bulletins', sanitized_annee, sanitized_classe)
    abs_dir = os.path.join(settings.MEDIA_ROOT, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)

    filename = f"Bulletin_{etudiant.matricule}_{sanitized_annee}.html"
    abs_filepath = os.path.join(abs_dir, filename)
    rel_filepath = os.path.join(rel_dir, filename)

    # Essayer de convertir en PDF réel avec xhtml2pdf ou reportlab if available
    try:
        from xhtml2pdf import pisa
        pdf_filename = f"Bulletin_{etudiant.matricule}_{sanitized_annee}.pdf"
        abs_pdfpath = os.path.join(abs_dir, pdf_filename)
        rel_pdfpath = os.path.join(rel_dir, pdf_filename)
        
        with open(abs_pdfpath, "wb") as pdf_file:
            pisa_status = pisa.CreatePDF(html_content, dest=pdf_file)
            
        if not pisa_status.err:
            bulletin.pdf_file.name = rel_pdfpath
        else:
            with open(abs_filepath, "w", encoding="utf-8") as f:
                f.write(html_content)
            bulletin.pdf_file.name = rel_filepath
    except Exception:
        with open(abs_filepath, "w", encoding="utf-8") as f:
            f.write(html_content)
        bulletin.pdf_file.name = rel_filepath

    bulletin.est_valide = True
    bulletin.est_publie = True
    bulletin.date_publication = timezone.now()
    if user_valideur:
        bulletin.valide_par = user_valideur
    bulletin.save()

    return bulletin
