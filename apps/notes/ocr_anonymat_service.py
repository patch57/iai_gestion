"""
Service OCR & Matching pour Fiches de Notes d'Anonymat
IAI-Cameroun - Centre de Douala
"""
import re
import os
import unicodedata
import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


def _normaliser_texte(texte):
    """Normalise un texte pour la comparaison (sans accents, majuscules)"""
    if not texte:
        return ""
    texte = unicodedata.normalize('NFD', str(texte))
    texte = ''.join(c for c in texte if unicodedata.category(c) != 'Mn')
    return texte.upper().strip()


def extraire_texte_fichier(fichier_path):
    """Extrait les lignes de texte brutes à partir d'un PDF ou d'une Image"""
    lignes_texte = []
    ext = os.path.splitext(fichier_path)[1].lower()

    if ext == '.pdf':
        try:
            import pdfplumber
            with pdfplumber.open(fichier_path) as pdf:
                for page in pdf.pages:
                    # Tenter d'extraire les tableaux en priorité
                    tableaux = page.extract_tables()
                    if tableaux:
                        for table in tableaux:
                            for row in table:
                                if row:
                                    ligne_str = " | ".join([str(cell or '').strip() for cell in row])
                                    lignes_texte.append(ligne_str)
                    else:
                        text = page.extract_text()
                        if text:
                            lignes_texte.extend(text.splitlines())
        except Exception as e:
            logger.error(f"Erreur pdfplumber: {e}")

    else: # Images JPG, PNG, WEBP, BMP
        try:
            from rapidocr_onnxruntime import RapidOCR
            engine = RapidOCR()
            ocr_res, _ = engine(fichier_path)
            if ocr_res:
                lignes_texte = [item[1] for item in ocr_res if item and len(item) > 1]
        except Exception:
            pass

        if not lignes_texte:
            try:
                from PIL import Image, ImageEnhance, ImageOps
                import pytesseract

                img = Image.open(fichier_path)
                img_gray = ImageOps.grayscale(img)
                img_enh = ImageEnhance.Contrast(img_gray).enhance(1.8)

                try:
                    text = pytesseract.image_to_string(img_enh, lang='fra+eng')
                except Exception:
                    text = pytesseract.image_to_string(img)
                
                if text:
                    lignes_texte = text.splitlines()
            except Exception as e:
                logger.debug(f"Erreur OCR Image: {e}")

    return [l.strip() for l in lignes_texte if l.strip()]


def analyser_fiche_anonymat(fichier_path, mode_enseignant=True):
    """
    Extrait les données d'une fiche d'anonymat (y compris multi-notes CC).
    - If mode_enseignant=True: extrait (Code Anonymat, Note, Note1..5, Moyenne CC)
    - If mode_enseignant=False: extrait (Code Anonymat, Note, Nom Manuscrit/Détecté)
    """
    lignes_brutes = extraire_texte_fichier(fichier_path)
    resultats = []

    for index, ligne in enumerate(lignes_brutes):
        ligne_norm = _normaliser_texte(ligne)
        
        # Ignorer les lignes d'en-tête (ex: "FICHE DE NOTES", "CLASSE", "MATIERE", "ANNEE")
        if any(h in ligne_norm for h in ['FICHE', 'ANONYMAT', 'MATIERE', 'ENSEIGNANT', 'EXAMEN', 'PRENOMS', 'COEFF']):
            continue

        # Découper par séparateurs courants
        parties = [p.strip() for p in ligne.split('|') if p.strip()] if '|' in ligne else [ligne]

        code_anonymat = None
        notes_trouvees = []
        nom_detecte = ""

        # Recherche de code d'anonymat
        match_code = re.search(r'([A-Z]?\s*\d{1,2})', ligne_norm)
        if match_code:
            code_anonymat = match_code.group(1).replace(" ", "")

        # Extraction de tous les nombres représentant des notes (0 à 20)
        match_notes = re.findall(r'\b(\d{1,2}(?:[\.,]\d{1,2})?)\b', ligne)
        for n_str in match_notes:
            try:
                val = float(n_str.replace(',', '.'))
                if 0.0 <= val <= 20.0:
                    notes_trouvees.append(val)
            except ValueError:
                pass

        # Nom détecté si mode complet
        if not mode_enseignant and len(parties) >= 3:
            nom_detecte = parties[2]
        elif not mode_enseignant:
            mots = [m for m in ligne.split() if not re.match(r'^[A-Z]?\d{1,2}$', m) and not re.match(r'^\d{1,2}(?:[\.,]\d{1,2})?$', m)]
            nom_detecte = " ".join(mots)

        if code_anonymat and notes_trouvees:
            note_valeur = notes_trouvees[-1] if notes_trouvees else 0.0
            n1 = notes_trouvees[0] if len(notes_trouvees) >= 1 else None
            n2 = notes_trouvees[1] if len(notes_trouvees) >= 2 else None
            n3 = notes_trouvees[2] if len(notes_trouvees) >= 3 else None
            n4 = notes_trouvees[3] if len(notes_trouvees) >= 4 else None
            n5 = notes_trouvees[4] if len(notes_trouvees) >= 5 else None

            # Si plusieurs notes CC trouvées, calculer la moyenne
            notes_valid = [n for n in [n1, n2, n3, n4, n5] if n is not None]
            moyenne_calc = round(sum(notes_valid) / len(notes_valid), 2) if notes_valid else note_valeur

            resultats.append({
                'code_anonymat': code_anonymat,
                'note': moyenne_calc,
                'note_1': n1,
                'note_2': n2,
                'note_3': n3,
                'note_4': n4,
                'note_5': n5,
                'moyenne_cc': moyenne_calc,
                'nom_manuscrit': nom_detecte.strip(),
                'confiance': 0.95
            })

    return resultats



def effectuer_matching_etudiants(lignes_anonymat, etudiants_queryset):
    """
    Associe de façon optimale et fiable chaque ligne d'anonymat (Code + Note + Nom détecté)
    avec le profil réel de l'étudiant inscrit (Filière, Niveau, Salle), de manière unique (0 doublons).
    """
    etudiants_liste = list(etudiants_queryset)
    correspondances = []
    etudiants_attribues = set()

    for ligne in lignes_anonymat:
        etudiant_trouve = None
        meilleur_score = 0.0
        nom_manuscrit = _normaliser_texte(ligne.get('nom_manuscrit', ''))

        if nom_manuscrit:
            for et in etudiants_liste:
                if et.id in etudiants_attribues:
                    continue

                nom_etudiant = _normaliser_texte(f"{et.nom} {et.prenom}")
                score = SequenceMatcher(None, nom_manuscrit, nom_etudiant).ratio()
                
                # Inversion Nom / Prénom
                nom_etudiant_inv = _normaliser_texte(f"{et.prenom} {et.nom}")
                score_inv = SequenceMatcher(None, nom_manuscrit, nom_etudiant_inv).ratio()

                max_score = max(score, score_inv)

                if max_score > meilleur_score and max_score >= 0.50:
                    meilleur_score = max_score
                    etudiant_trouve = et

        if etudiant_trouve:
            etudiants_attribues.add(etudiant_trouve.id)

        correspondances.append({
            'code_anonymat': ligne.get('code_anonymat'),
            'note': ligne.get('note'),
            'nom_manuscrit': ligne.get('nom_manuscrit'),
            'etudiant': etudiant_trouve,
            'score_matching': round(meilleur_score * 100, 1) if etudiant_trouve else 0
        })

    return correspondances
