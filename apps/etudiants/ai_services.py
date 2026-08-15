import io
import numpy as np
from PIL import Image

def verifier_photo_identite(file_obj):
    """
    Vérifie si une photo téléversée est une photo d'identité valide (portrait avec un visage humain).
    Retourne (est_valide: bool, message_erreur: str, details_dict: dict)
    """
    try:
        # 1. Charger l'image avec PIL
        file_obj.seek(0)
        pil_img = Image.open(file_obj)
        pil_img.verify()
        
        # Ré-ouvrir pour lecture
        file_obj.seek(0)
        pil_img = Image.open(file_obj)
        width, height = pil_img.size
        
        # 2. Vérification minimale de résolution
        if width < 120 or height < 120:
            return False, "La résolution de la photo est trop faible. Veuillez importer une photo de type identité nette (d'au moins 200x200 pixels).", {}
            
        # 3. Vérification du format portrait (Ratio Hauteur/Largeur)
        aspect_ratio = height / float(width)
        if aspect_ratio < 0.85:
            return False, "La photo téléversée n'est pas au format portrait. Veuillez importer une photo de type identité (format Passeport / Carte d'Identité).", {"aspect_ratio": aspect_ratio}
            
        if aspect_ratio > 2.5:
            return False, "La photo est anormalement allongée. Veuillez importer une photo de type identité classique.", {"aspect_ratio": aspect_ratio}

        # 4. Conversion RGB pour analyse de la région centrale (visage & teint)
        rgb_img = pil_img.convert('RGB')
        arr = np.array(rgb_img)
        
        # Extraire la zone centrale (entre 15% et 85% en X, 15% et 75% en Y)
        h_start, h_end = int(height * 0.15), int(height * 0.75)
        w_start, w_end = int(width * 0.15), int(width * 0.85)
        center_crop = arr[h_start:h_end, w_start:w_end]
        
        if center_crop.size == 0:
            return False, "Image invalide ou corrompue.", {}
            
        # Calculer le ratio de teints humains (Skin Tone heuristics RGB & YCbCr)
        r = center_crop[:, :, 0].astype(float)
        g = center_crop[:, :, 1].astype(float)
        b = center_crop[:, :, 2].astype(float)
        
        # Heuristique couleur de peau : R > 40, G > 20, B > 15, R > G, R > B, |R-G| > 15
        skin_mask = (r > 40) & (g > 20) & (b > 15) & (r > g) & (r > b) & (np.abs(r - g) > 10)
        skin_ratio = np.mean(skin_mask)
        
        if skin_ratio < 0.08:
            return False, "Aucun visage humain ou portrait d'identité détecté sur la photo. Veuillez importer une photo de type identité avec votre visage net de face.", {
                "skin_ratio": skin_ratio,
                "width": width,
                "height": height
            }
            
        # Photo valide !
        return True, "", {
            "skin_ratio": skin_ratio,
            "aspect_ratio": aspect_ratio,
            "width": width,
            "height": height
        }
        
    except Exception as e:
        try:
            file_obj.seek(0)
        except Exception:
            pass
        return False, f"Fichier photo non valide ou corrompu. Veuillez importer une photo d'identité officielle (JPG ou PNG).", {}
