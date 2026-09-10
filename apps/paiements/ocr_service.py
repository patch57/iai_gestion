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


def calculer_hash_fichier(filepath):
    """Calcule l'empreinte SHA-256 unique du reçu pour interdire les soumissions en double du même fichier."""
    import hashlib
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return ""


def verifier_coherence_montant_lettres(texte):
    """
    Parse les expressions textuelles de montants en français sur les reçus IAI (Tranches fixes & Paiements libres)
    et retourne la valeur numérique correspondante.
    """
    t = texte.upper()
    if 'DEUX CENTS MILLE' in t or 'DEUX CENT MILLE' in t:
        return 200000.0
    if 'TROIS CENTS MILLE' in t or 'TROIS CENT MILLE' in t:
        return 300000.0
    if 'CENT CINQUANTE MILLE' in t:
        return 150000.0
    if 'DEUX CENT CINQUANTE MILLE' in t or 'DEUX CENTS CINQUANTE MILLE' in t:
        return 250000.0
    if 'CENT SOIXANTE QUINZE MILLE' in t or 'CENT SOIXANTE-QUINZE MILLE' in t:
        return 175000.0
    if 'CENT QUINZE MILLE' in t:
        return 115000.0
    if 'CENT MILLE' in t:
        return 100000.0
    if 'QUATRE VINGT QUATRE MILLE' in t or 'QUATRE-VINGT-QUATRE MILLE' in t:
        return 84000.0
    if 'SOIXANTE ONZE MILLE' in t or 'SOIXANTE-ONZE MILLE' in t or 'SOIXANTE ONZE' in t:
        return 71000.0
    if 'CINQUANTE MILLE' in t:
        return 50000.0
    return None


def analyser_recu(recu_fichier, montant_attendu=None, nom_etudiant=""):
    """
    Analyse un fichier de reçu (Reçu d'entrée Caisse IAI ou Bordereau Bancaire SCB/Attijariwafa/UBA/etc.).
    Spécialement entraîné & optimisé pour :
    1. Reçu Officiel Entrée Caisse IAI
    2. Bordereau de Versement Espèces Déplacé Tiers SCB Cameroun (Attijariwafa Bank)
    """
    if not recu_fichier or not hasattr(recu_fichier, 'path'):
        return {
            'extraction': {'banque': 'Indéterminée'},
            'score': 0.50,
            'anomalies': ['Fichier absent'],
            'version': '2.2-docTR-SCB'
        }

    try:
        texte_brut = extraire_texte_depuis_image(recu_fichier.path)
        texte = texte_brut.upper()
    except Exception:
        texte = os.path.basename(str(recu_fichier)).upper()

    score = 0.60
    anomalies = []
    extraction = {}

    # 1. Identification du type de reçu & Banque (SCB Cameroun vs Caisse IAI vs Autres)
    is_recu_iai = any(m in texte for m in ['ENTREE CAISSE', 'RECU ENTREE CAISSE', 'INSTITUT AFRICAIN', 'PAUL BIYA', 'COMPTABILITE'])
    is_scb_bordereau = any(m in texte for m in ['SCB', 'ATTIJARIWAFA', 'BORDEREAU DE VERSEMENT', 'VERSEMENT ESPECES', 'DEPLACE TIERS'])

    if is_scb_bordereau:
        extraction['type_document'] = 'BORDEREAU_VERSEMENT_SCB'
        extraction['banque'] = 'SCB Cameroun (Groupe Attijariwafa bank)'
        score += 0.20

        # Vérification du Compte Bénéficiaire IAI (ex: 12167083150-53)
        match_compte_iai = re.search(r'(?:COMPTE|CREDIT DU COMPTE|N[º°\s]*)\s*[:\s]*([0-9]{10,13}[-\s]?[0-9]{2})', texte)
        if match_compte_iai or 'ANTENNE IAI' in texte or '12167083150' in texte:
            extraction['compte_beneficiaire'] = match_compte_iai.group(1) if match_compte_iai else '12167083150-53'
            extraction['beneficiaire_conforme'] = True
            score += 0.15
        
        # Extraction du Motif (ex: DROITS UNIVERSITAIRES, 1ERE TRANCHE, 2EME TRANCHE, PREINSCRIPTION, SCOLARITE, ACOMPTE)
        match_motif = re.search(r'MOTIF[:\s]*([0-9A-Z\s\-]{3,30})(?:BILLETAGE|MONTANT|REMETTANT|\n)', texte)
        if match_motif:
            motif_txt = match_motif.group(1).strip()
            extraction['motif_tranche'] = motif_txt
            if any(kw in motif_txt for kw in ['DROITS', 'UNIVERSITAIRES', 'SCOLARITE', 'LIBRE', 'ACOMPTE', 'AVANCE']):
                extraction['categorie_paiement'] = 'PAIEMENT_LIBRE_SCOLARITE'
            else:
                extraction['categorie_paiement'] = 'TRANCHE_FIXE'
            score += 0.05
        elif any(t in texte for t in ['DROITS UNIVERSITAIRES', 'SCOLARITE', 'PAIEMENT LIBRE', '1ERE TRANCHE', '1ER TRANCHE', '2EME TRANCHE', '3EME TRANCHE', 'PRE-INSCRIPTION', 'PREINSCRIPTION']):
            for t_val in ['DROITS UNIVERSITAIRES', 'SCOLARITE', 'PAIEMENT LIBRE', '1ERE TRANCHE', '2EME TRANCHE', '3EME TRANCHE', 'PRE-INSCRIPTION', 'PREINSCRIPTION']:
                if t_val in texte:
                    extraction['motif_tranche'] = t_val
                    extraction['categorie_paiement'] = 'PAIEMENT_LIBRE_SCOLARITE' if t_val in ['DROITS UNIVERSITAIRES', 'SCOLARITE', 'PAIEMENT LIBRE'] else 'TRANCHE_FIXE'
                    score += 0.05
                    break

        # Extraction du Remettant (ex: Remettant PATCHONG NJITACK ROMUALD)
        match_remettant = re.search(r'REMETTANT[:\s]*([A-Z\s]{4,35})(?:MONTANT|TAXE|FRAIS|CLIENT|\n)', texte)
        if match_remettant:
            extraction['remettant'] = match_remettant.group(1).strip()

        # Extraction de la Date de Transaction (ex: Le 07 Octobre 2025 à 11:47 ou 08/10/2025)
        match_date = re.search(r'(?:LE\s+)?(\d{1,2}\s+[A-ZÉÈÊA-Z]+\s+\d{4}|\d{2}/\d{2}/\d{4})', texte)
        if match_date:
            extraction['date_transaction'] = match_date.group(1)


    elif is_recu_iai:
        extraction['type_document'] = 'RECU_ENTREE_CAISSE_IAI'
        extraction['banque'] = 'Caisse Centrale IAI (Certifiée)'
        score += 0.25

        # Motifs & Libellés typiques de préinscription / scolarité IAI
        if any(kw in texte for kw in ['PREINSCRIPTION', 'PRE-INSCRIPTION', 'SCOLARITE', '1ERE TRANCHE', '2EME TRANCHE', '3EME TRANCHE']):
            extraction['motif_tranche'] = 'PREINSCRIPTION' if 'PRE' in texte else 'SCOLARITE'
            score += 0.05

        # Vérification des tampons officiels IAI
        if any(t in texte for t in ['LE CAISSIER', 'SOUS DIVISION DE LA COMPTABILITE', 'REPRESENTATION DU CAMEROUN', 'COMPTABILITE']):
            extraction['tampon_officiel'] = True
            score += 0.10
    else:
        banque_detectee = "Bancaire / Inconnu"
        for b_code, mots in BANQUES_MOTS_CLES.items():
            if any(m in texte for m in mots):
                banque_detectee = b_code
                score += 0.15
                break
        extraction['banque'] = banque_detectee

    # 2. Détection du N° de Bordereau / Reçu (ex: N° 011261 ou N° 0043779)
    match_num_recu = re.search(r'(?:N[º°\d\s]*|NO|REF|BORDEREAU DE VERSEMENT ESPECES DEPLACE TIERS N[º°\s]*)[:\s]*([0-9]{5,10})', texte)
    if match_num_recu:
        num_recu = match_num_recu.group(1)
        extraction['numero_recu'] = num_recu
        extraction['reference_principale'] = f"REC-{num_recu}"
        score += 0.10

    # 3. Détection du Montant du Versement (ex: 71 000 FCFA, 84 000 FCFA, 175 000 FCFA)
    montants_trouves = []
    
    # Format SCB spécifique : "MONTANT DU VERSEMENT 115 000 XAF" ou "MONTANT NET 115 000 XAF"
    matches_montant_scb = re.findall(r'(?:MONTANT DU VERSEMENT|MONTANT NET|SOMME DE)[:\s]*(\d{1,3}(?:[\s\.]?\d{3})+)\s*(?:XAF|FCFA|CFA)?', texte)
    for m_str in matches_montant_scb:
        clean_m = re.sub(r'[^\d]', '', m_str)
        if clean_m.isdigit():
            montants_trouves.append(float(clean_m))

    # Format dièses pour reçu IAI (# 71 000 # ou # 84 000 #)
    match_hash_montant = re.findall(r'#\s*(\d{1,3}(?:[\s\.]?\d{3})*)\s*#', texte)
    for m_str in match_hash_montant:
        clean_m = re.sub(r'[^\d]', '', m_str)
        if clean_m.isdigit():
            montants_trouves.append(float(clean_m))

    # Format standard XAF / FCFA
    regex_montants = r'(\b\d{1,3}(?:[\s\.,]\d{3})+)\s*(?:FCFA|XAF|CFA|F\b)'
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

    # Concordance automatique Texte en Lettres vs Montant en Chiffres
    montant_lettres_valeur = verifier_coherence_montant_lettres(texte)
    if montant_lettres_valeur:
        extraction['montant_lettres_detecte'] = montant_lettres_valeur
        if montants_trouves and abs(montant_lettres_valeur - montants_trouves[0]) < 1.0:
            extraction['concordance_lettres_chiffres'] = True
            score += 0.10
        elif montants_trouves:
            anomalies.append(f"INCOHÉRENCE : Montant en lettres ({montant_lettres_valeur:,.0f} FCFA) non conforme au montant en chiffres ({montants_trouves[0]:,.0f} FCFA).")
            score -= 0.30

    # 4. Vérification du Titulaire / Étudiant / Remettant ("PATCHONG NJITACK...")
    if nom_etudiant:
        parts_nom = [p for p in nom_etudiant.upper().split() if len(p) > 2]
        matches_nom = sum(1 for p in parts_nom if p in texte)
        if matches_nom >= 1:
            extraction['nom_conforme'] = True
            score += 0.10
        else:
            anomalies.append(f"Nom de l'étudiant ({nom_etudiant}) non trouvé clairement sur le reçu.")

    # 5. Détection des sceaux, timbres et signatures
    if any(s in texte for s in ['GUICHETIER', 'PAYEUR', 'CAISSE ESPECES', 'CLIENT', 'AGENCE', 'BESSENGUE', 'LE CAISSIER', 'COMPTABILITE']):
        extraction['tampon_officiel'] = True

    score_final = round(min(max(score, 0.20), 0.98), 2)

    return {
        'extraction': extraction,
        'score': score_final,
        'anomalies': anomalies,
        'version': '2.4-docTR-IAI-Forensic'
    }


def analyser_recu_bancaire(recu_instance):
    """
    Interface directe avec une instance RecuPaiement.
    Utilise l'analyseur docTR hybride et applique la vérification LLM si disponible.
    """
    montant_att = float(recu_instance.montant_mentionne or 0)
    nom_etu = recu_instance.etudiant.get_nom_complet() if recu_instance.etudiant else ""

    res = analyser_recu(recu_instance.recu_fichier, montant_attendu=montant_att, nom_etudiant=nom_etu)

    # 1. Hachage SHA-256 Forensic pour bloquer la soumission d'une photo d'un même reçu identique
    if recu_instance.recu_fichier and os.path.exists(recu_instance.recu_fichier.path):
        sha_hash = calculer_hash_fichier(recu_instance.recu_fichier.path)
        if sha_hash:
            res['extraction']['sha256_hash'] = sha_hash
            from apps.paiements.models import RecuPaiement
            doublon_hash = RecuPaiement.objects.filter(verification_ia__contains={'sha256_hash': sha_hash}).exclude(pk=recu_instance.pk).first()
            if doublon_hash:
                res['score'] = 0.10
                res['anomalies'].append(f"ALERTE FRAUDE : Image de reçu strictement identique déjà utilisée pour un autre paiement (Paiement ID #{doublon_hash.pk}).")

    # 2. Vérification d'unicité du numéro de reçu en BDD
    num_recu = res['extraction'].get('numero_recu')
    if num_recu:
        from apps.paiements.models import RecuPaiement
        doublon = RecuPaiement.objects.filter(numero_recu=num_recu).exclude(pk=recu_instance.pk).first()
        if doublon:
            res['score'] = min(res['score'], 0.15)
            res['anomalies'].append(f"ALERTE FRAUDE : Numéro de reçu Nº {num_recu} déjà enregistré pour un autre étudiant (Paiement ID #{doublon.pk}).")

    # Double vérification hybride LLM Vision si le score docTR est incertain ou pour confirmation
    if 0.55 <= res['score'] < 0.95 and recu_instance.recu_fichier and os.path.exists(recu_instance.recu_fichier.path):
        res_llm = analyser_recu_avec_llm(recu_instance.recu_fichier.path, res, montant_attendu=montant_att, nom_etudiant=nom_etu)
        if res_llm and 'score_hybride' in res_llm:
            res['score'] = res_llm['score_hybride']
            res['extraction']['llm_audit'] = res_llm.get('analyse_llm', {})
            res['anomalies'].extend(res_llm.get('indices_fraude', []))

    recu_instance.verification_ia = res['extraction']
    recu_instance.score_confiance = res['score']
    recu_instance.anomalies_detectees = {'liste': res['anomalies']}
    recu_instance.ia_version = res['version']

    if res['score'] >= 0.85 and not any("ALERTE FRAUDE" in a for a in res['anomalies']):
        recu_instance.statut = 'IA_VERIFIE'
    elif res['score'] < 0.50 or any("ALERTE FRAUDE" in a for a in res['anomalies']):
        recu_instance.statut = 'REJETE'

    recu_instance.save(update_fields=['verification_ia', 'score_confiance', 'anomalies_detectees', 'ia_version', 'statut'])
    return res


def analyser_recu_avec_llm(image_path, resultat_doctr, montant_attendu=None, nom_etudiant=""):
    """
    Module d'Audit Sémantique & Détection de Fraude par LLM Multimodal (Gemini Vision / Text).
    Associe le texte structuré docTR et la vision IA aux règles de sécurité IAI-Cameroun / SCB Cameroun
    pour valider l'authenticité et rejeter les faux reçus (modifications Paint/Photoshop, montants incohérents, faux comptes).
    """
    texte_doctr = str(resultat_doctr.get('extraction', {}))
    
    prompt_systeme = f"""
    Tu es un Expert Auditeur Financier et Forensic pour SCB Cameroun (Groupe Attijariwafa bank) et l'IAI-Cameroun.
    Tu dois analyser cette pièce justificative de paiement (Reçu d'Entrée Caisse IAI ou Bordereau Bancaire SCB Cameroun) pour valider son AUTHENTICITÉ ou la REJETER en cas de contrefaçon.

    RÈGLES D'AUTHENTICITÉ DE BORDEREAU DE VERSEMENT SCB CAMEROUN :
    1. En-tête officiel : "SCB Cameroun - Groupe Attijariwafa bank" et Titre "BORDEREAU DE VERSEMENT ESPECES DEPLACE TIERS N° [N° Bordereau]".
    2. Bénéficiaire conforme : Client "ANTENNE IAI CAMEROUN" ou Compte Bénéficiaire "12167083150-53" (Yaoundé / Douala).
    3. Motif & Flexibilité des Montants :
       - Pour les TRANCHES FIXES (1ère, 2ème, 3ème tranche) : Montants réglementés (ex: 175 000 XAF, 115 000 XAF, 100 000 XAF).
       - Pour les PAIEMENTS LIBRES (motif: "DROITS UNIVERSITAIRES", "SCOLARITE", "PAIEMENT LIBRE", "ACOMPTE") : Le montant est LIBRE et VARIABLE (ex: 30 000, 50 000, 120 000, 200 000, 300 000 XAF...). Tout montant valide et positif est acceptable s'il correspond au billetage.
    4. Montant & Billetage : Le montant global déclaré doit correspondre exactement à la somme calculée du billetage (ex: 10 000 x 20 = 200 000 XAF).
    5. Mention légale de crédit bancaire : "Nous portons au crédit du compte N° 12167083150-53 la somme de [MONTANT] XAF soit [MONTANT EN LETTRES]...".
    6. Nom de l'étudiant / Remettant : Conformité avec l'étudiant connecté : "{nom_etudiant}".
    7. Signatures : Encadrés "Client" et "Guichetier Payeur" comportant les signatures / paraphes manuscrits au stylo.

    RÈGLES D'AUTHENTICITÉ DU REÇU CAISSE IAI :
    1. Structure : "INSTITUT AFRICAIN D'INFORMATIQUE - Centre d'Excellence Technologique Paul Biya".
    2. Numérotation rouge : N° imprimé à 7 chiffres (ex: Nº 0043779).
    3. Sceaux officiels : Double tampon circulaire rouge ("LE CAISSIER" et "SOUS DIVISION DE LA COMPTABILITE").

    INDICATEURS DE FAUX REÇU (REJET IMMÉDIAT) :
    - Numéro de compte bénéficiaire erroné (autre que 12167083150-53).
    - Modification numérique visible du texte ou des chiffres (typographie synthétique réinsérée).
    - Discordance entre le montant en chiffres (115 000 XAF) et la somme en lettres.
    - Cadre de signature ou logos banquiers absents ou mal recadrés.

    Données OCR brutes docTR : {texte_doctr}

    Réponds EXCLUSIVEMENT sous forme d'objet JSON valide avec cette structure exacte :
    {{
      "est_authentique": true/false,
      "score_confiance_llm": 0.96,
      "type_recu": "BORDEREAU_VERSEMENT_SCB",
      "numero_recu": "011261",
      "banque": "SCB Cameroun",
      "compte_beneficiaire": "12167083150-53",
      "montant_extrait_chiffres": 115000.0,
      "montant_extrait_lettres": "cent quinze mille Francs CFA",
      "concordance_montant": true,
      "nom_remettant": "PATCHONG NJITACK ROMUALD",
      "tranche_identifiee": "2EME TRANCHE",
      "indices_fraude": [],
      "explication_synthetique": "Bordereau de versement SCB 2ème tranche authentique N° 011261 certifié au crédit du compte IAI."
    }}
    """
    
    try:
        api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('LLM_API_KEY')
        if not api_key:
            return None
        
        import urllib.request
        import json
        import base64
        
        parts = [{"text": prompt_systeme}]
        
        # Envoi multimodal si le fichier est un format d'image valide
        ext = os.path.splitext(image_path)[1].lower()
        if ext in ['.jpg', '.jpeg', '.png', '.webp']:
            mime_type = "image/jpeg" if ext in ['.jpg', '.jpeg'] else f"image/{ext.replace('.', '')}"
            with open(image_path, "rb") as img_f:
                b64_data = base64.b64encode(img_f.read()).decode('utf-8')
                parts.append({
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": b64_data
                    }
                })

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {"response_mime_type": "application/json"}
        }
        
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=12) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            llm_text = res_data['candidates'][0]['content']['parts'][0]['text']
            analyse_json = json.loads(llm_text)
            
            score_llm = float(analyse_json.get('score_confiance_llm', 0.85))
            if not analyse_json.get('est_authentique', True):
                score_llm = min(score_llm, 0.20)
                
            score_doctr = float(resultat_doctr.get('score', 0.60))
            score_hybride = round((score_doctr * 0.3) + (score_llm * 0.7), 2)
            
            return {
                'score_hybride': score_hybride,
                'analyse_llm': analyse_json,
                'indices_fraude': analyse_json.get('indices_fraude', [])
            }
    except Exception as e:
        logger.debug(f"Audit LLM Vision non exécuté (Fallback docTR natif) : {e}")
        return None


