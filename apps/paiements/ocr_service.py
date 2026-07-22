"""
Service OCR pour l'analyse de reçus bancaires
IAI-Cameroun - Centre de Douala
Utilise pdfplumber (PDF) et pytesseract (images) pour l'extraction de texte.
"""
import re
import os
import unicodedata
from datetime import datetime, date
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

# Patterns regex pour reçus bancaires camerounais
PATTERNS_MONTANT = [
    r'(\d{1,3}[\s\.\,]\d{3}[\s\.\,]\d{3})\s*(?:FCFA|F\.?CFA|XAF|FRANCS?)?',
    r'(\d{2,3}[\s\.\,]\d{3})\s*(?:FCFA|F\.?CFA|XAF|FRANCS?)?',
    r'(\d{5,7})\s*(?:FCFA|F\.?CFA|XAF|FRANCS?)',
    r'(?:MONTANT|SOMME|TOTAL|VERSEMENT)[:\s]*(\d[\d\s\.\,]*\d)',
]

PATTERNS_REFERENCE = [
    r'(?:REF(?:ERENCE)?|N[°o]|NUM(?:ERO)?|BORDEREAU)[:\s]*([A-Z0-9][\w\-]{3,})',
    r'(?:RECU|RECEPISSE)\s*N[°o]?\s*[:\s]*([A-Z0-9][\w\-]{3,})',
]

PATTERNS_DATE = [
    r'(\d{2}[/\-\.]\d{2}[/\-\.]\d{4})',
    r'(\d{2}[/\-\.]\d{2}[/\-\.]\d{2})',
    r'(\d{4}[/\-\.]\d{2}[/\-\.]\d{2})',
]

BANQUES_CAMEROUN = [
    'SCB', 'BICEC', 'SGBC', 'AFRILAND', 'UBA', 'ECOBANK', 'CBC',
    'CCA', 'BGFI', 'ATLANTIC', 'STANDARD CHARTERED', 'CITIBANK',
    'SOCIETE GENERALE', 'BANQUE ATLANTIQUE', 'NFC BANK',
]

MOTS_CLES_RECU = [
    'VERSEMENT', 'DEPOT', 'RECU', 'BORDEREAU', 'BANQUE', 'AGENCE',
    'REMETTANT', 'BENEFICIAIRE', 'MONTANT', 'REFERENCE', 'CAISSE',
    'VIREMENT', 'PAIEMENT', 'SCOLARITE', 'INSCRIPTION', 'TRANCHE',
    'DROITS', 'IAI', 'INSTITUT AFRICAIN',
]


def _normaliser_texte(texte):
    """Normalise un texte pour comparaison"""
    texte = unicodedata.normalize('NFD', texte)
    texte = ''.join(c for c in texte if unicodedata.category(c) != 'Mn')
    return texte.upper().strip()


def _nettoyer_montant(montant_str):
    """Convertit une chaîne de montant en nombre"""
    montant_str = montant_str.replace(' ', '').replace('.', '').replace(',', '')
    try:
        return float(montant_str)
    except ValueError:
        return 0.0


def extraire_texte_pdf(fichier_path):
    """Extrait le texte d'un fichier PDF avec pdfplumber"""
    try:
        import pdfplumber
        texte_complet = ""
        with pdfplumber.open(fichier_path) as pdf:
            for page in pdf.pages:
                texte = page.extract_text()
                if texte:
                    texte_complet += texte + "\n"
        return texte_complet.strip()
    except ImportError:
        logger.warning("pdfplumber non installé — extraction PDF impossible")
        return ""
    except Exception as e:
        logger.error(f"Erreur extraction PDF: {e}")
        return ""


def extraire_texte_image(fichier_path):
    """Extrait le texte d'une image avec Tesseract OCR"""
    try:
        import pytesseract
        from PIL import Image, ImageFilter, ImageEnhance

        # Pré-traitement de l'image pour améliorer l'OCR
        img = Image.open(fichier_path)

        # Convertir en niveaux de gris
        img = img.convert('L')

        # Augmenter le contraste
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)

        # Augmenter la netteté
        img = img.filter(ImageFilter.SHARPEN)

        # OCR avec Tesseract (français + anglais)
        texte = pytesseract.image_to_string(img, lang='fra+eng', config='--psm 6')
        return texte.strip()

    except ImportError:
        logger.warning("pytesseract non installé — OCR image impossible")
        return ""
    except Exception as e:
        logger.error(f"Erreur OCR image: {e}")
        return ""


def extraire_texte(fichier):
    """
    Extrait le texte d'un fichier (PDF ou image).
    Accepte un FieldFile Django ou un chemin de fichier.
    """
    # Obtenir le chemin du fichier
    if hasattr(fichier, 'path'):
        fichier_path = fichier.path
    elif hasattr(fichier, 'name'):
        fichier_path = fichier.name
    else:
        fichier_path = str(fichier)

    if not os.path.exists(fichier_path):
        logger.error(f"Fichier introuvable: {fichier_path}")
        return ""

    nom_fichier = os.path.basename(fichier_path).lower()
    extension = os.path.splitext(nom_fichier)[1]

    if extension == '.pdf':
        return extraire_texte_pdf(fichier_path)
    elif extension in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif']:
        return extraire_texte_image(fichier_path)
    else:
        logger.warning(f"Format non supporté: {extension}")
        return ""


def extraire_montants(texte):
    """Extrait tous les montants trouvés dans le texte"""
    montants = []
    texte_upper = texte.upper()

    for pattern in PATTERNS_MONTANT:
        for match in re.finditer(pattern, texte_upper, re.IGNORECASE):
            montant_str = match.group(1)
            montant = _nettoyer_montant(montant_str)
            if 1000 <= montant <= 10_000_000:
                montants.append(montant)

    return sorted(set(montants), reverse=True)


def extraire_references(texte):
    """Extrait les références bancaires du texte"""
    references = []
    texte_upper = texte.upper()

    for pattern in PATTERNS_REFERENCE:
        for match in re.finditer(pattern, texte_upper, re.IGNORECASE):
            ref = match.group(1).strip()
            if len(ref) >= 4:
                references.append(ref)

    return list(set(references))


def extraire_dates(texte):
    """Extrait les dates du texte"""
    dates = []
    for pattern in PATTERNS_DATE:
        for match in re.finditer(pattern, texte):
            date_str = match.group(1)
            for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y',
                         '%d/%m/%y', '%d-%m-%y', '%Y-%m-%d', '%Y/%m/%d']:
                try:
                    d = datetime.strptime(date_str, fmt).date()
                    if date(2020, 1, 1) <= d <= date(2030, 12, 31):
                        dates.append(d)
                    break
                except ValueError:
                    continue

    return list(set(dates))


def detecter_banque(texte):
    """Détecte la banque mentionnée dans le texte"""
    texte_upper = _normaliser_texte(texte)
    for banque in BANQUES_CAMEROUN:
        if banque in texte_upper:
            return banque
    return None


def detecter_nom_remettant(texte, nom_etudiant=""):
    """
    Tente de détecter le nom du remettant dans le texte.
    Cherche après les mots-clés "REMETTANT", "DEPOSANT", "NOM", etc.
    """
    texte_upper = _normaliser_texte(texte)
    patterns_remettant = [
        r'(?:REMETTANT|DEPOSANT|DONNEUR\s*D.ORDRE|VERSE\s*PAR|NOM\s*DU\s*CLIENT|EMETTEUR)[:\s]+([A-Z][A-Z\s\-]{3,50})',
    ]

    for pattern in patterns_remettant:
        match = re.search(pattern, texte_upper)
        if match:
            return match.group(1).strip()

    return None


def comparer_noms(nom1, nom2):
    """Compare deux noms de manière flexible (sans accents, casse, espaces)"""
    if not nom1 or not nom2:
        return 0.0

    n1 = _normaliser_texte(nom1)
    n2 = _normaliser_texte(nom2)

    # Correspondance exacte
    if n1 == n2:
        return 1.0

    # Vérifier si l'un contient l'autre
    if n1 in n2 or n2 in n1:
        return 0.8

    # Vérifier les mots en commun
    mots1 = set(n1.split())
    mots2 = set(n2.split())

    if not mots1 or not mots2:
        return 0.0

    communs = mots1 & mots2
    total = mots1 | mots2

    return len(communs) / len(total) if total else 0.0


def analyser_recu(fichier, montant_attendu=None, nom_etudiant=""):
    """
    Analyse complète d'un reçu bancaire.

    Args:
        fichier: FieldFile Django ou chemin vers le fichier
        montant_attendu: montant attendu (float) pour cette tranche
        nom_etudiant: nom complet de l'étudiant

    Returns:
        dict avec: extraction, score, anomalies, texte_brut
    """
    texte = extraire_texte(fichier)

    resultat = {
        'extraction': {},
        'score': 0.0,
        'anomalies': [],
        'texte_brut': texte[:500] if texte else "",
        'version': '2.0-OCR',
    }

    # Si aucun texte extrait
    if not texte or len(texte.strip()) < 10:
        resultat['score'] = 0.1
        resultat['anomalies'].append("Aucun texte lisible extrait du document")
        return resultat

    # --- Extraction ---
    montants = extraire_montants(texte)
    references = extraire_references(texte)
    dates_trouvees = extraire_dates(texte)
    banque = detecter_banque(texte)
    remettant = detecter_nom_remettant(texte, nom_etudiant)

    resultat['extraction'] = {
        'montants_detectes': montants,
        'montant_principal': montants[0] if montants else None,
        'references': references,
        'reference_principale': references[0] if references else None,
        'dates': [d.isoformat() for d in dates_trouvees],
        'date_paiement': dates_trouvees[0].isoformat() if dates_trouvees else None,
        'banque': banque,
        'remettant': remettant,
    }

    # --- Calcul du score de confiance ---
    score_composantes = []

    # 1. Présence de texte lisible (0.0 à 0.15)
    texte_upper = texte.upper()
    mots_cles_trouves = sum(1 for m in MOTS_CLES_RECU if m in texte_upper)
    score_texte = min(0.15, mots_cles_trouves * 0.03)
    score_composantes.append(('texte_pertinent', score_texte))

    # 2. Montant détecté (0.0 à 0.30)
    if montants:
        # L'étudiant peut verser n'importe quel montant, y compris la totalité.
        # Tout montant détecté valide (> 0) donne le score complet.
        score_montant = 0.30
        meilleur_match = montants[0]  # Prendre le montant le plus grand trouvé
        
        if montant_attendu and meilleur_match < (montant_attendu * 0.1):
            # Anomalie uniquement si le montant est extrêmement faible (ex: moins de 10% du montant attendu)
            resultat['anomalies'].append(
                f"Le montant détecté ({meilleur_match:,.0f} FCFA) semble très faible par rapport à la tranche attendue ({montant_attendu:,.0f} FCFA)"
            )
            score_montant = 0.15
            
        resultat['extraction']['montant_principal'] = meilleur_match
        score_composantes.append(('montant', score_montant))
    else:
        score_composantes.append(('montant', 0.0))
        resultat['anomalies'].append("Aucun montant détecté dans le document")

    # 3. Référence bancaire (0.0 à 0.15)
    if references:
        score_composantes.append(('reference', 0.15))
    else:
        score_composantes.append(('reference', 0.05))

    # 4. Date de paiement (0.0 à 0.10)
    date_valide = True
    if dates_trouvees:
        date_recente = max(dates_trouvees)
        
        # Déterminer le début de la campagne académique courante (1er Juin de l'année académique en cours)
        from datetime import date
        courant = date.today()
        annee_campagne = courant.year if courant.month >= 6 else (courant.year - 1)
        debut_campagne = date(annee_campagne, 6, 1)
        
        if date_recente >= debut_campagne:
            jours_diff = abs((courant - date_recente).days)
            if jours_diff <= 365:
                score_composantes.append(('date', 0.10))
            else:
                score_composantes.append(('date', 0.05))
                resultat['anomalies'].append(f"Date de paiement ancienne ({date_recente.isoformat()})")
        else:
            date_valide = False
            score_composantes.append(('date', 0.0))
            resultat['anomalies'].append(
                f"Date de paiement invalide ({date_recente.isoformat()}) : antérieure au début de la campagne {annee_campagne}-{annee_campagne+1}"
            )
    else:
        score_composantes.append(('date', 0.02))

    # 5. Banque détectée (0.0 à 0.10)
    if banque:
        score_composantes.append(('banque', 0.10))
    else:
        score_composantes.append(('banque', 0.02))

    # 6. Correspondance du nom (0.0 à 0.20)
    if nom_etudiant and remettant:
        score_nom = comparer_noms(remettant, nom_etudiant) * 0.20
        score_composantes.append(('nom_remettant', score_nom))
        if score_nom < 0.10:
            resultat['anomalies'].append(
                f"Le nom du remettant ({remettant}) ne correspond pas à l'étudiant ({nom_etudiant})"
            )
    elif nom_etudiant:
        # Chercher le nom directement dans le texte
        nom_norm = _normaliser_texte(nom_etudiant)
        mots_nom = nom_norm.split()
        mots_trouves = sum(1 for mot in mots_nom if mot in _normaliser_texte(texte))
        if mots_trouves >= len(mots_nom) * 0.5:
            score_composantes.append(('nom_remettant', 0.15))
        else:
            score_composantes.append(('nom_remettant', 0.03))
    else:
        score_composantes.append(('nom_remettant', 0.05))

    # Score final
    score_final = sum(s for _, s in score_composantes)
    if not date_valide:
        # Forcer le score à être bas pour empêcher toute auto-validation en cas de reçu périmé
        score_final = min(0.40, score_final)
        
    resultat['score'] = round(score_final, 2)
    resultat['score'] = min(1.0, resultat['score'])
    resultat['extraction']['score_details'] = {nom: round(val, 3) for nom, val in score_composantes}

    return resultat
