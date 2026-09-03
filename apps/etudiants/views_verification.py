"""
Vue de vérification publique d'authenticité par QR Code pour IAI-Gestion.
IAI-Cameroun - Centre de Douala
"""
import base64
from io import BytesIO
from django.shortcuts import render, get_object_or_404
from django.http import Http404
from .models import Etudiant


def generer_qr_code_base64(url_verification):
    """
    Génère une chaîne de caractères au format Data URI base64 représentant le QR Code.
    Ne nécessite aucun stockage temporaire sur disque.
    """
    try:
        import qrcode
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=6,
            border=2,
        )
        qr.add_data(url_verification)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
        
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        qr_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return f"data:image/png;base64,{qr_b64}"
    except Exception as e:
        return ""


def verifier_etudiant_public(request, token):
    """
    Vue publique accessible via le scan du QR Code d'un étudiant.
    Affiche le statut officiel de la carte/certificat sans nécessiter de connexion.
    """
    etudiant = get_object_or_404(Etudiant, verification_token=token)
    
    # Détermination de l'état de validité
    est_valide = etudiant.est_actif and etudiant.statut in ['INSCRIT', 'ACTIF']
    
    context = {
        'etudiant': etudiant,
        'est_valide': est_valide,
        'titre_page': f"Vérification Officielle - {etudiant.get_full_name if hasattr(etudiant, 'get_full_name') else etudiant.nom}",
    }
    return render(request, 'etudiants/verification_public.html', context)
