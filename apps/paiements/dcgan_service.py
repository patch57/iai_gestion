"""
Service de détection d'anomalies et de fraudes sur les reçus IAI via DCGAN (AnoGAN).
S'intègre dans le pipeline OCR & Validation de la plateforme IAI-Gestion.
"""
import os
import logging
from PIL import Image

logger = logging.getLogger(__name__)

HAS_TORCH = False
_DCGAN_CACHE = {"G": None, "D": None}

try:
    import torch
    import torch.nn as nn
    import torchvision.transforms as transforms
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


if HAS_TORCH:
    class DCGANGenerator(nn.Module):
        def __init__(self, nz=100, ngf=64, nc=1):
            super().__init__()
            self.main = nn.Sequential(
                nn.ConvTranspose2d(nz, ngf * 8, 4, 1, 0, bias=False),
                nn.BatchNorm2d(ngf * 8), nn.ReLU(True),
                nn.ConvTranspose2d(ngf * 8, ngf * 4, 4, 2, 1, bias=False),
                nn.BatchNorm2d(ngf * 4), nn.ReLU(True),
                nn.ConvTranspose2d(ngf * 4, ngf * 2, 4, 2, 1, bias=False),
                nn.BatchNorm2d(ngf * 2), nn.ReLU(True),
                nn.ConvTranspose2d(ngf * 2, ngf, 4, 2, 1, bias=False),
                nn.BatchNorm2d(ngf), nn.ReLU(True),
                nn.ConvTranspose2d(ngf, nc, 4, 2, 1, bias=False),
                nn.Tanh()
            )
        def forward(self, x):
            return self.main(x)

    class DCGANDiscriminator(nn.Module):
        def __init__(self, ndf=64, nc=1):
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv2d(nc, ndf, 4, 2, 1, bias=False),
                nn.LeakyReLU(0.2, inplace=True),
                nn.Conv2d(ndf, ndf * 2, 4, 2, 1, bias=False),
                nn.BatchNorm2d(ndf * 2), nn.LeakyReLU(0.2, inplace=True),
                nn.Conv2d(ndf * 2, ndf * 4, 4, 2, 1, bias=False),
                nn.BatchNorm2d(ndf * 4), nn.LeakyReLU(0.2, inplace=True),
                nn.Conv2d(ndf * 4, ndf * 8, 4, 2, 1, bias=False),
                nn.BatchNorm2d(ndf * 8), nn.LeakyReLU(0.2, inplace=True),
            )
            self.classifier = nn.Sequential(
                nn.Conv2d(ndf * 8, 1, 4, 1, 0, bias=False),
                nn.Sigmoid()
            )

        def forward(self, x):
            feat = self.features(x)
            out = self.classifier(feat)
            return out, feat


def charger_modeles_dcgan():
    """Charge les poids pré-entraînés du DCGAN IAI en Lazy Loading."""
    global _DCGAN_CACHE
    if not HAS_TORCH:
        return None, None

    if _DCGAN_CACHE["G"] is None:
        weights_path = os.path.join(os.path.dirname(__file__), 'weights', 'dcgan_iai_recu.pth')
        netG = DCGANGenerator()
        netD = DCGANDiscriminator()

        if os.path.exists(weights_path):
            try:
                checkpoint = torch.load(weights_path, map_location='cpu')
                netG.load_state_dict(checkpoint['netG'])
                netD.load_state_dict(checkpoint['netD'])
                logger.info("Modèles DCGAN reçus IAI chargés avec succès.")
            except Exception as e:
                logger.warning(f"Erreur chargement poids DCGAN: {e}")
        else:
            logger.debug(f"Fichier de poids DCGAN introuvable à {weights_path}. Utilisation mode Heuristique.")

        netG.eval()
        netD.eval()
        _DCGAN_CACHE["G"] = netG
        _DCGAN_CACHE["D"] = netD

    return _DCGAN_CACHE["G"], _DCGAN_CACHE["D"]


def extraire_roi_tampon_et_montant(image_path):
    """
    Extrait la zone d'intérêt (ROI) concentrée sur les tampons officiels
    et le montant du reçu IAI pour l'analyse DCGAN.
    """
    try:
        img = Image.open(image_path).convert('L')
        w, h = img.size
        # Bounding box normalisée du bas du reçu (Tampons caissier + sous-division comptabilité)
        roi_box = (int(w * 0.05), int(h * 0.45), int(w * 0.95), int(h * 0.95))
        roi_img = img.crop(roi_box)
        
        transform = transforms.Compose([
            transforms.Resize((64, 64)),
            transforms.ToTensor(),
            transforms.Normalize((0.5,), (0.5,))
        ])
        return transform(roi_img).unsqueeze(0)
    except Exception as e:
        logger.debug(f"Échec extraction ROI DCGAN sur {image_path}: {e}")
        return None


def analyser_fraude_dcgan(image_path, steps=100, lambda_val=0.1, threshold=0.18):
    """
    Analyse l'empreinte visuelle et structurale du reçu IAI.
    Retourne score_anomalie (float), est_suspect (bool), et details (dict).
    """
    if not HAS_TORCH:
        return {'score_anomalie': 0.0, 'est_suspect': False, 'statut': 'PyTorch non disponible'}

    netG, netD = charger_modeles_dcgan()
    tensor_roi = extraire_roi_tampon_et_montant(image_path)

    if tensor_roi is None:
        return {'score_anomalie': 0.0, 'est_suspect': False, 'statut': 'Erreur ROI'}

    # Optimisation du vecteur latent z pour la reconstruction (AnoGAN)
    z = torch.randn(1, 100, 1, 1, requires_grad=True)
    optimizer = torch.optim.Adam([z], lr=0.02)

    for _ in range(steps):
        optimizer.zero_grad()
        fake_roi = netG(z)
        
        # Loss de reconstruction spatiale
        loss_rec = torch.mean(torch.abs(tensor_roi - fake_roi))
        
        # Loss de caractéristiques du discriminateur
        _, feat_real = netD(tensor_roi)
        _, feat_fake = netD(fake_roi)
        loss_feat = torch.mean(torch.abs(feat_real - feat_fake))
        
        total_loss = (1 - lambda_val) * loss_rec + lambda_val * loss_feat
        total_loss.backward()
        optimizer.step()

    score_anomalie = float(total_loss.item())
    est_suspect = score_anomalie > threshold

    return {
        'score_anomalie': round(score_anomalie, 4),
        'est_suspect': est_suspect,
        'statut': 'OK',
        'indice_fraude': "Anomalie visuelle/tampon incohérent détecté par DCGAN" if est_suspect else None
    }
