"""
Service d'analyse OCR intelligente des reçus bancaires pour IAI-Gestion.
Détection automatique des montants, références, dates et banques (UBA, CBC, BICEC, EU, Mobile Money).
"""
import os
import re
import logging
from PIL import Image

logger = logging.getLogger(__name__)

# Essayer d'importer pytesseract pour l'OCR réel si présent sur le système
HAS_PYTESSERACT = False
try:
    import pytesseract
    HAS_PYTESSERACT = True
except ImportError:
    HAS_PYTESSERACT = False

BANQUES_MOTS_CLES = {
    'SCB': ['SCB', 'ATTIJARIWAFA', 'SOCIETE COMMERCIALE DE BANQUE'],
    'UBA': ['UBA', 'UNITED BANK FOR AFRICA', 'AFRICA'],
    'BICEC': ['BICEC', 'BANQUE INTERNATIONALE'],
    'CBC': ['COMMERCIAL BANK', 'CBC'],
    'AFRILAND': ['AFRILAND', 'FIRST BANK'],
    'EXPRESS_UNION': ['EXPRESS UNION', 'EU MOBILE'],
    'ORANGE_MONEY': ['ORANGE MONEY', 'OM', 'ORANGE'],
    'MTN_MOMO': ['MTN', 'MOMO', 'MOBILE MONEY'],
    'ECOBANK': ['ECOBANK'],
}


def pretraiter_image(image_path):
    """Améliore le contraste et convertit l'image en niveau de gris pour maximiser la reconnaissance OCR."""
    try:
        from PIL import ImageEnhance, ImageOps
        img = Image.open(image_path)
        img_gray = ImageOps.grayscale(img)
        enhancer = ImageEnhance.Contrast(img_gray)
        return enhancer.enhance(1.8)
    except Exception:
        return None


def extraire_texte_depuis_image(image_path):
    """Extrait le texte d'un fichier d'image ou PDF via RapidOCR, pdfplumber ou Pytesseract avec pré-traitement."""
    if not image_path or not os.path.exists(image_path):
        return ""

    texte_extrait = ""
    ext = os.path.splitext(image_path)[1].lower()

    # 1. Extraction PDF si document PDF
    if ext == '.pdf':
        try:
            import pdfplumber
            with pdfplumber.open(image_path) as pdf:
                pages_text = [p.extract_text() or "" for p in pdf.pages]
                texte_extrait = "\n".join(pages_text)
        except Exception as e_pdf:
            logger.debug(f"Échec pdfplumber sur {image_path}: {e_pdf}")
            try:
                import pypdf
                reader = pypdf.PdfReader(image_path)
                texte_extrait = "\n".join([p.extract_text() or "" for p in reader.pages])
            except Exception:
                pass

    # 2. Moteur principal OCR d'images : RapidOCR (Haute précision local sans binaire externe)
    if not texte_extrait and ext in ['.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff']:
        try:
            from rapidocr_onnxruntime import RapidOCR
            engine = RapidOCR()
            ocr_res, _ = engine(image_path)
            if ocr_res:
                lines = [item[1] for item in ocr_res if item and len(item) > 1]
                texte_extrait = "\n".join(lines)
        except Exception as e_ocr:
            logger.debug(f"Échec RapidOCR sur {image_path}: {e_ocr}")

    # 3. Moteur secondaire : Pytesseract avec image pré-traitée
    if not texte_extrait and HAS_PYTESSERACT and ext in ['.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff']:
        try:
            img_traitee = pretraiter_image(image_path) or Image.open(image_path)
            try:
                texte_extrait = pytesseract.image_to_string(img_traitee, lang='fra+eng')
            except Exception:
                texte_extrait = pytesseract.image_to_string(img_traitee)
        except Exception as e_tess:
            logger.debug(f"Échec Pytesseract sur {image_path}: {e_tess}")

    # 4. Fallback ultime sur le nom de fichier
    if not texte_extrait:
        texte_extrait = os.path.basename(image_path)

    return texte_extrait


# Alias retro-compatible
extraire_texte = extraire_texte_depuis_image



def analyser_recu(recu_fichier, montant_attendu=None, nom_etudiant=""):
    """
    Analyse un fichier de reçu et retourne un dictionnaire de résultats OCR.
    Compatible avec RecuPaiement.analyser_par_ia().
    """
    if not recu_fichier or not hasattr(recu_fichier, 'path'):
        return {
            'extraction': {'banque': 'Indéterminée'},
            'score': 0.50,
            'anomalies': ['Fichier absent'],
            'version': '2.0-OCR'
        }

    try:
        texte = extraire_texte_depuis_image(recu_fichier.path).upper()
    except Exception:
        texte = os.path.basename(str(recu_fichier)).upper()

    score = 0.60
    anomalies = []
    extraction = {}

    # 1. Détection du type de document et de la banque / caisse
    banque_detectee = "IAI Entrée Caisse"
    mots_cles_caisse = ['ENTREE EN CAISSE', 'CAISSE', 'MANUSCRIT', 'CARNET', 'BORDEREAU DE CAISSE', 'RECU DE CAISSE', 'BON DE CAISSE']
    
    if any(m in texte for m in mots_cles_caisse):
        extraction['type_document'] = 'RECU_MANUSCRIT_IAI'
        banque_detectee = "Caisse Principale IAI (Manuscrit)"
        score += 0.15
    else:
        for b_code, mots in BANQUES_MOTS_CLES.items():
            if any(m in texte for m in mots):
                banque_detectee = b_code
                score += 0.15
                break
    extraction['banque'] = banque_detectee

    # 2. Détection du montant
    regex_montants = r'(\b\d{1,3}(?:[\s\.,]\d{3})*)\s*(?:FCFA|XAF|CFA|F\b)'
    matches_montant = re.findall(regex_montants, texte)

    montants_trouves = []
    for m_str in matches_montant:
        clean_m = re.sub(r'[^\d]', '', m_str)
        if clean_m.isdigit():
            montants_trouves.append(float(clean_m))

    if montants_trouves:
        extraction['montant_principal'] = montants_trouves[0]
        if montant_attendu and any(abs(m - float(montant_attendu)) < 1.0 for m in montants_trouves):
            score += 0.20
        elif montant_attendu:
            anomalies.append(f"Montant attendu ({montant_attendu} FCFA) non confirmé exactement.")
    elif montant_attendu:
        extraction['montant_principal'] = float(montant_attendu)

    # 3. Détection de la référence
    regex_ref = r'(?:REF|TRANSACTION|N°|NO|TXN|ID)[:\s]*([A-Z0-9]{6,20})'
    match_ref = re.search(regex_ref, texte)
    if match_ref:
        extraction['reference_principale'] = match_ref.group(1)
        score += 0.10

    score_final = round(min(max(score, 0.40), 0.98), 2)

    return {
        'extraction': extraction,
        'score': score_final,
        'anomalies': anomalies,
        'version': '2.0-OCR-Pro'
    }


def analyser_recu_bancaire(recu_instance):
    """
    Interface directe avec une instance RecuPaiement.
    """
    montant_att = float(recu_instance.montant_mentionne or 0)
    nom_etu = recu_instance.etudiant.get_nom_complet() if recu_instance.etudiant else ""

    res = analyser_recu(recu_instance.recu_fichier, montant_attendu=montant_att, nom_etudiant=nom_etu)
    recu_instance.verification_ia = res['extraction']
    recu_instance.score_confiance = res['score']
    recu_instance.anomalies_detectees = {'liste': res['anomalies']}
    recu_instance.ia_version = res['version']

    if res['score'] >= 0.85:
        recu_instance.statut = 'IA_VERIFIE'

    recu_instance.save(update_fields=['verification_ia', 'score_confiance', 'anomalies_detectees', 'ia_version', 'statut'])
    return res
