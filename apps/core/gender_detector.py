"""
Module de détection autonome de genre (sexe M/F) pour l'IAI-Cameroun.
Permet d'attribuer automatiquement le sexe ('F' ou 'M') d'un étudiant ou candidat
en analysant son nom et ses prénoms (prénoms francophones, anglophones et camerounais).
"""

import re
import unicodedata

# Liste explicite de prénoms et marqueurs féminins courants
PRENOMS_FEMININS = {
    'stella', 'merveille', 'marie', 'anne', 'flore', 'grace', 'alice', 'beatrice', 'nicole',
    'sophie', 'chantal', 'brigitte', 'rose', 'elisabeth', 'claude', 'charlotte', 'laure',
    'nadine', 'audrey', 'edwige', 'leslie', 'patricia', 'vanessa', 'sylvie', 'cynthia',
    'christelle', 'carine', 'corinne', 'jessica', 'brenda', 'delphine', 'sandrine',
    'benedicte', 'monique', 'francoise', 'genevieve', 'mireille', 'aurelie', 'valerie',
    'isabelle', 'esther', 'ruth', 'rebecca', 'naomi', 'sarah', 'lea', 'chloe', 'emma',
    'camille', 'lucie', 'mathilde', 'juliette', 'clemence', 'margaux', 'pauline', 'solene',
    'agathe', 'ines', 'manon', 'eva', 'clara', 'laura', 'marion', 'amandine', 'oceane',
    'morgane', 'maeva', 'lisa', 'emilie', 'fanny', 'romane', 'noemie', 'elodie', 'celine',
    'stephanie', 'virginie', 'caroline', 'severine', 'christine', 'catherine', 'dominique',
    'pascale', 'bernadette', 'antoinette', 'georgette', 'henriette', 'marcelle', 'jeanne',
    'denise', 'jacqueline', 'colette', 'suzanne', 'germaine', 'yvonne', 'simone',
    'marguerite', 'lucienne', 'paulette', 'raymonde', 'odette', 'madeleine', 'therese',
    'berthe', 'adele', 'aimee', 'alix', 'amelie', 'anais', 'angele', 'angelique',
    'anne-marie', 'annick', 'arlette', 'astrid', 'avrile', 'barbara', 'berenice',
    'blandine', 'capucine', 'cathy', 'cecile', 'christiane', 'claire', 'claudine',
    'clementina', 'clementyne', 'daniele', 'danielle', 'daphne', 'diane', 'dorothee',
    'edith', 'emmanuelle', 'estelle', 'evelyne', 'fabienne', 'florence', 'frederique',
    'gabrielle', 'ghislaine', 'gisele', 'huguette', 'jane', 'jocelyne', 'joelle', 'josiane',
    'judith', 'julia', 'julie', 'justine', 'karine', 'laetitia', 'laurence', 'leone',
    'liliane', 'louise', 'ludivine', 'lydie', 'magali', 'maite', 'marianne', 'marie-christine',
    'marie-claire', 'marie-france', 'marie-helene', 'marie-laure', 'marie-luce',
    'marie-noelle', 'marie-therese', 'marjorie', 'marlene', 'martine', 'maud',
    'mauricette', 'meganne', 'meredith', 'muriel', 'murielle', 'myriam', 'nadege',
    'nathalie', 'odile', 'olivia', 'ophelie', 'paulette', 'regine', 'renee', 'roselyne',
    'sabine', 'sabrina', 'sandra', 'silvia', 'solange', 'stephanie', 'veronique',
    'victoria', 'victoire', 'viviane', 'yvette', 'blanche', 'clarisse', 'doria',
    'dorcas', 'eugenie', 'flora', 'gladys', 'gloria', 'hermine', 'irene',
    'joan', 'joanna', 'joy', 'judicaelle', 'linda', 'lorraine', 'madison',
    'marcela', 'michele', 'michelle', 'miriam', 'nadia', 'nancy', 'pamela',
    'priscilla', 'rachel', 'rita', 'rosine', 'samanta', 'samantha', 'sharon', 'stecy',
    'stacy', 'tatiana', 'tracy', 'tiffany', 'vivian', 'winnie', 'yolande', 'yasmine',
    'zita', 'dzuakou', 'dzou'
}

# Prefixes ou patronymes indiquant le genre féminin au Cameroun
PREFIXES_FEMININS = {'ngo', 'nga'}

# Prénoms masculins explicites
PRENOMS_MASCULINS = {
    'jean', 'paul', 'pierre', 'jacques', 'michel', 'philippe', 'alain', 'bernard',
    'christian', 'daniel', 'eric', 'francois', 'guy', 'henri', 'laurent', 'marc',
    'nicolas', 'patrick', 'rene', 'serge', 'thierry', 'yves', 'alexandre', 'antoine',
    'benjamin', 'charles', 'david', 'emmanuel', 'fabrice', 'frederic', 'gilles',
    'guillaume', 'herve', 'jerome', 'julien', 'louis', 'mathieu', 'matthieu',
    'olivier', 'pascal', 'patrice', 'richard', 'romain', 'sebastien',
    'stephane', 'thomas', 'vincent', 'xavier', 'arthur', 'baptiste', 'clement', 'dylan',
    'enzo', 'gabriel', 'hugo', 'jules', 'leo', 'lucas', 'maxime', 'nathan', 'quentin',
    'raphael', 'theophile', 'victor', 'joseph', 'mike', 'bertrand', 'brayand'
}


def _normaliser(s: str) -> str:
    """Convertit en minuscules sans accents."""
    if not s:
        return ''
    s = unicodedata.normalize('NFD', str(s))
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s.lower().strip()


def detecter_sexe_etudiant(nom: str, prenom: str = '') -> str:
    """
    Détermine automatiquement le sexe de l'étudiant ('F' ou 'M') à partir de son nom et prénom.
    
    Returns:
        'F' pour Féminin
        'M' pour Masculin (valeur par défaut)
    """
    nom_norm = _normaliser(nom)
    prenom_norm = _normaliser(prenom)
    
    texte_complet = f"{prenom_norm} {nom_norm}".strip()
    mots = set(re.findall(r'[a-z]+', texte_complet))
    
    # 1. Vérification des préfixes/patronymes féminins (ex: NGO, NGA)
    for pfix in PREFIXES_FEMININS:
        if pfix in mots:
            return 'F'
            
    # 2. Intersections avec les listes de prénoms
    mots_fem = mots.intersection(PRENOMS_FEMININS)
    mots_masc = mots.intersection(PRENOMS_MASCULINS)
    
    if mots_fem and not mots_masc:
        return 'F'
        
    if mots_fem:
        # Prioriser le genre féminin si un prénom féminin marquant est présent
        return 'F'
        
    return 'M'
