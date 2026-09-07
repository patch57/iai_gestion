"""
Service d'analyse OCR intelligente des reçus bancaires pour IAI-Gestion.
Détection automatique des montants, références, dates et banques (UBA, CBC, BICEC, EU, Mobile Money).
"""
import os
import re
import logging
from PIL import Image

logger = logging.getLogger(__name__)

# 1. docTR (Mindee) - Moteur OCR Deep Learning multi-orientation pour reçus
HAS_DOCTR = False
_DOCTR_MODEL = None

try:
    from doctr.io import DocumentFile
    from doctr.models import ocr_predictor
    HAS_DOCTR = True
except ImportError:
    HAS_DOCTR = False

def get_doctr_model():
    """Initialise le modèle docTR en Lazy Loading pour économiser les ressources au démarrage."""
    global _DOCTR_MODEL
    if HAS_DOCTR and _DOCTR_MODEL is None:
        try:
            _DOCTR_MODEL = ocr_predictor(det_arch='db_resnet50', reco_arch='crnn_vgg16_bn', pretrained=True)
        except Exception as e:
            logger.warning(f"Impossible de charger le modèle docTR: {e}")
            _DOCTR_MODEL = False
    return _DOCTR_MODEL if _DOCTR_MODEL else None

# 2. Pytesseract - Moteur secondaire
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
    'IAI_CAISSE': ['RECU ENTREE CAISSE', 'ENTREE CAISSE', 'INSTITUT AFRICAIN D\'INFORMATIQUE', 'PAUL BIYA'],
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
    """Extrait le texte d'un reçu via docTR (Deep Learning), RapidOCR, pdfplumber ou Pytesseract."""
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

    # 2. Moteur d'Élite docTR (Mindee - OCR Deep Learning 2D avec orientation / reçus complexes)
    if not texte_extrait and HAS_DOCTR and ext in ['.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff']:
        try:
            model = get_doctr_model()
            if model:
                doc = DocumentFile.from_images(image_path)
                result = model(doc)
                lines_text = []
                for page in result.pages:
                    for block in page.blocks:
                        for line in block.lines:
                            line_str = " ".join([w.value for w in line.words])
                            if line_str:
                                lines_text.append(line_str)
                if lines_text:
                    texte_extrait = "\n".join(lines_text)
                    logger.info(f"docTR extraction réussie sur {image_path} ({len(lines_text)} lignes).")
        except Exception as e_doctr:
            logger.debug(f"Échec docTR sur {image_path}: {e_doctr}")

    # 3. Moteur Secondaire OCR : RapidOCR (Local ONNX Runtime)
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

    # 4. Moteur Tertiaire : Pytesseract avec pré-traitement
    if not texte_extrait and HAS_PYTESSERACT and ext in ['.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff']:
        try:
            img_traitee = pretraiter_image(image_path) or Image.open(image_path)
            try:
                texte_extrait = pytesseract.image_to_string(img_traitee, lang='fra+eng')
            except Exception:
                texte_extrait = pytesseract.image_to_string(img_traitee)
        except Exception as e_tess:
            logger.debug(f"Échec Pytesseract sur {image_path}: {e_tess}")

    # 5. Fallback ultime sur le nom de fichier
    if not texte_extrait:
        texte_extrait = os.path.basename(image_path)

    return texte_extrait


# Alias rétro-compatible
extraire_texte = extraire_texte_depuis_image


def analyser_recu(recu_fichier, montant_attendu=None, nom_etudiant=""):
    """
    Analyse un fichier de reçu (Reçu d'entrée Caisse IAI ou Bordereau Bancaire).
    Spécialement entraîné & optimisé pour le modèle 'REÇU ENTRÉE CAISSE' officiel de l'IAI.
    """
    if not recu_fichier or not hasattr(recu_fichier, 'path'):
        return {
            'extraction': {'banque': 'Indéterminée'},
            'score': 0.50,
            'anomalies': ['Fichier absent'],
            'version': '2.1-docTR'
        }

    try:
        texte_brut = extraire_texte_depuis_image(recu_fichier.path)
        texte = texte_brut.upper()
    except Exception:
        texte = os.path.basename(str(recu_fichier)).upper()

    score = 0.60
    anomalies = []
    extraction = {}

    # 1. Identification Reçu Officiel Entrée Caisse IAI vs Reçu Bancaire
    is_recu_iai = any(m in texte for m in ['ENTREE CAISSE', 'RECU ENTREE CAISSE', 'INSTITUT AFRICAIN', 'PAUL BIYA', 'COMPTABILITE'])
    
    if is_recu_iai:
        extraction['type_document'] = 'RECU_ENTREE_CAISSE_IAI'
        extraction['banque'] = 'Caisse Centrale IAI (Certifiée)'
        score += 0.20
    else:
        banque_detectee = "Bancaire / Inconnu"
        for b_code, mots in BANQUES_MOTS_CLES.items():
            if any(m in texte for m in mots):
                banque_detectee = b_code
                score += 0.15
                break
        extraction['banque'] = banque_detectee

    # 2. Détection du N° de Reçu (ex: N° 0043779 sur le reçu IAI)
    match_num_recu = re.search(r'(?:N[º°\d\s]*|NO|REF)[:\s]*([0-9]{5,10})', texte)
    if match_num_recu:
        num_recu = match_num_recu.group(1)
        extraction['numero_recu'] = num_recu
        extraction['reference_principale'] = f"REC-{num_recu}"
        score += 0.10

    # 3. Détection du Montant (Motif manuscrit entouré de dièses '# 71 000 #' ou format standard FCFA)
    match_hash_montant = re.findall(r'#\s*(\d{1,3}(?:[\s\.]?\d{3})*)\s*#', texte)
    montants_trouves = []
    
    if match_hash_montant:
        for m_str in match_hash_montant:
            clean_m = re.sub(r'[^\d]', '', m_str)
            if clean_m.isdigit():
                montants_trouves.append(float(clean_m))

    regex_montants = r'(\b\d{1,3}(?:[\s\.,]\d{3})*)\s*(?:FCFA|XAF|CFA|F\b)'
    matches_standard = re.findall(regex_montants, texte)
    for m_str in matches_standard:
        clean_m = re.sub(r'[^\d]', '', m_str)
        if clean_m.isdigit():
            montants_trouves.append(float(clean_m))

    if montants_trouves:
        extraction['montant_principal'] = montants_trouves[0]
        if montant_attendu and any(abs(m - float(montant_attendu)) < 1.0 for m in montants_trouves):
            score += 0.20
        elif montant_attendu:
            anomalies.append(f"Montant attendu ({montant_attendu} FCFA) différent du reçu ({montants_trouves[0]} FCFA).")
    elif montant_attendu:
        extraction['montant_principal'] = float(montant_attendu)

    # 4. Vérification du Titulaire / Étudiant ("Reçu de M.: PATOHONG NJITACK...")
    if nom_etudiant:
        parts_nom = [p for p in nom_etudiant.upper().split() if len(p) > 2]
        matches_nom = sum(1 for p in parts_nom if p in texte)
        if matches_nom >= 1:
            extraction['nom_conforme'] = True
            score += 0.10

    # 5. Détection des sceaux et timbres officiels ("LE CAISSIER", "SOUS-DIRECTION")
    if 'CAISSIER' in texte or 'COMPTABILITE' in texte or 'REPRESENTATION' in texte:
        extraction['tampon_officiel'] = True
        score += 0.05

    score_final = round(min(max(score, 0.40), 0.98), 2)

    return {
        'extraction': extraction,
        'score': score_final,
        'anomalies': anomalies,
        'version': '2.1-docTR'
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
