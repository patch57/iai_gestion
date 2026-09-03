"""
Service d'importation multi-format et d'analyse de conformité des emplois du temps pour IAI-Gestion.
Formats supportés : CSV, Excel (.xlsx, .xls), PDF (.pdf), Image (.png, .jpg, .jpeg).
IAI-Cameroun - Centre de Douala
"""
import io
import os
import re
import csv
import logging

logger = logging.getLogger(__name__)

VALID_JOURS = ['LUNDI', 'MARDI', 'MERCREDI', 'JEUDI', 'VENDREDI', 'SAMEDI']
VALID_PLAGES = ['P1', 'P2', 'PAUSE', 'P3', 'P4']


def _normaliser_creneau_dict(raw_dict, index_ligne=1):
    """
    Nettoie et valide un dictionnaire de créneau extrait.
    Retourne (creneau_normalise, erreur_str).
    """
    jour = str(raw_dict.get('Jour') or raw_dict.get('jour') or '').strip().upper()
    plage = str(raw_dict.get('Plage') or raw_dict.get('plage') or '').strip().upper()
    intitule = str(raw_dict.get('Intitule') or raw_dict.get('intitule') or '').strip()

    if not jour:
        return None, f"Ligne {index_ligne}: Jour manquant."
    if jour not in VALID_JOURS:
        return None, f"Ligne {index_ligne}: Jour invalide '{jour}'. Jours acceptés: {', '.join(VALID_JOURS)}."
    if not plage:
        return None, f"Ligne {index_ligne}: Plage horaire manquante."
    if plage not in VALID_PLAGES:
        return None, f"Ligne {index_ligne}: Plage invalide '{plage}'. Plages acceptées: {', '.join(VALID_PLAGES)}."

    enseignant = str(raw_dict.get('Enseignant') or raw_dict.get('enseignant') or '').strip()
    salle_nom = str(raw_dict.get('Salle') or raw_dict.get('salle') or '').strip()
    progression = str(raw_dict.get('Progression') or raw_dict.get('progression') or '').strip()
    type_evt = str(raw_dict.get('Type') or raw_dict.get('type') or 'COURS').strip().upper()

    if type_evt not in ['COURS', 'EVALUATION', 'PAUSE', 'AUTRE']:
        type_evt = 'COURS'

    creneau = {
        'ligne': index_ligne,
        'jour': jour,
        'plage': plage,
        'intitule': 'PAUSE' if plage == 'PAUSE' else (intitule or 'COURS'),
        'enseignant_nom': enseignant,
        'salle_nom': salle_nom,
        'progression_heures': progression,
        'type_evenement': 'PAUSE' if plage == 'PAUSE' else type_evt,
    }
    return creneau, None


def extraire_depuis_csv(file_bytes):
    """Extraction avec journalisation des erreurs ligne par ligne depuis un fichier CSV."""
    valid_items = []
    errors = []
    
    try:
        decoded = file_bytes.decode('utf-8-sig', errors='ignore')
        reader = csv.DictReader(io.StringIO(decoded))
        for idx, row in enumerate(reader, start=2):
            creneau, err = _normaliser_creneau_dict(row, index_ligne=idx)
            if err:
                errors.append(err)
            elif creneau:
                valid_items.append(creneau)
    except Exception as e:
        logger.error(f"Erreur extraction CSV: {e}")
        errors.append(f"Erreur globale de lecture CSV: {e}")

    return valid_items, errors


def extraire_depuis_excel(file_bytes):
    """Extraction sécurisée depuis Excel (.xlsx, .xls)."""
    valid_items = []
    errors = []
    
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        sheet = wb.active

        headers = []
        for row_idx, row in enumerate(sheet.iter_rows(values_only=True), start=1):
            if row_idx == 1:
                headers = [str(cell or '').strip() for cell in row]
                continue
            if not any(row):
                continue
            row_dict = {headers[i]: row[i] for i in range(min(len(headers), len(row)))}
            creneau, err = _normaliser_creneau_dict(row_dict, index_ligne=row_idx)
            if err:
                errors.append(err)
            elif creneau:
                valid_items.append(creneau)
    except Exception as e:
        logger.error(f"Erreur extraction Excel: {e}")
        errors.append(f"Erreur de lecture du fichier Excel: {e}")

    return valid_items, errors


def extraire_depuis_texte_brut(texte):
    """Parse un bloc de texte brut (PDF / OCR)."""
    valid_items = []
    errors = []
    lignes = texte.splitlines()

    pattern = r'(LUNDI|MARDI|MERCREDI|JEUDI|VENDREDI|SAMEDI)[\s,;|]+(P1|P2|PAUSE|P3|P4)[\s,;|]+([^,;|\n]+)'

    for idx, line in enumerate(lignes, start=1):
        if not line.strip():
            continue
        match = re.search(pattern, line.upper())
        if match:
            jour = match.group(1)
            plage = match.group(2)
            reste = match.group(3).strip()
            parts = [p.strip() for p in reste.split('-') if p.strip()]

            creneau, err = _normaliser_creneau_dict({
                'jour': jour,
                'plage': plage,
                'intitule': parts[0] if len(parts) > 0 else 'COURS',
                'enseignant': parts[1] if len(parts) > 1 else '',
                'salle': parts[2] if len(parts) > 2 else '',
            }, index_ligne=idx)
            
            if err:
                errors.append(err)
            elif creneau:
                valid_items.append(creneau)

    return valid_items, errors


def extraire_depuis_pdf(file_bytes):
    """Extraction d'un fichier PDF."""
    texte_cumule = ""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        for page in reader.pages:
            texte_cumule += page.extract_text() or ""
    except Exception as e:
        logger.error(f"Erreur extraction PDF: {e}")
        return [], [f"Échec de lecture du document PDF: {e}"]

    return extraire_depuis_texte_brut(texte_cumule)


def extraire_depuis_image(file_bytes, file_name):
    """Extraction d'une image via OCR."""
    try:
        from PIL import Image
        import pytesseract
        img = Image.open(io.BytesIO(file_bytes))
        texte_extrait = pytesseract.image_to_string(img, lang='fra+eng')
    except Exception as e:
        logger.warning(f"Échec Pytesseract sur image {file_name}: {e}")
        return [], [f"Erreur d'analyse OCR sur l'image '{file_name}': {e}"]

    return extraire_depuis_texte_brut(texte_extrait)


def analyser_conflits_creneaux(creneaux):
    """
    Détecte les conflits de doublons (même jour et même plage horaire dans la liste).
    """
    conflits = []
    vus = {}
    for c in creneaux:
        cle = (c['jour'], c['plage'])
        if cle in vus:
            conflits.append(
                f"Conflit de créneau aux lignes {vus[cle]['ligne']} et {c['ligne']} : "
                f"Plusieurs cours programmés le {c['jour']} sur la plage {c['plage']}."
            )
        else:
            vus[cle] = c
    return conflits


def extraire_creneaux_multi_format(uploaded_file):
    """
    Fonction principale d'entrée qui détecte le format et retourne un dictionnaire de synthèse.
    Structure de retour:
    {
        'valid_items': [...],
        'errors': [...],
        'conflits': [...],
        'stats': {'total': X, 'valid': Y, 'errors': Z, 'conflits': W}
    }
    """
    filename = uploaded_file.name.lower()
    file_bytes = uploaded_file.read()

    if filename.endswith('.csv') or filename.endswith('.txt'):
        valid_items, errors = extraire_depuis_csv(file_bytes)
    elif filename.endswith('.xlsx') or filename.endswith('.xls'):
        valid_items, errors = extraire_depuis_excel(file_bytes)
    elif filename.endswith('.pdf'):
        valid_items, errors = extraire_depuis_pdf(file_bytes)
    elif filename.endswith(('.png', '.jpg', '.jpeg')):
        valid_items, errors = extraire_depuis_image(file_bytes, uploaded_file.name)
    else:
        valid_items, errors = extraire_depuis_csv(file_bytes)

    conflits = analyser_conflits_creneaux(valid_items)

    return {
        'valid_items': valid_items,
        'errors': errors,
        'conflits': conflits,
        'stats': {
            'total': len(valid_items) + len(errors),
            'valid': len(valid_items),
            'errors': len(errors),
            'conflits': len(conflits),
        }
    }
