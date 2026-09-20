"""
Script de d'entraînement unisupervisé du DCGAN (AnoGAN)
sur les reçus authentiques d'IAI-Gestion (Reçus Caisse IAI & Bordereaux SCB).
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
import torchvision.transforms as transforms
from PIL import Image, ImageEnhance, ImageOps

from apps.paiements.dcgan_service import DCGANGenerator, DCGANDiscriminator

WEIGHTS_DIR = os.path.join(os.path.dirname(__file__), 'weights')
os.makedirs(WEIGHTS_DIR, exist_ok=True)
CHECKPOINT_PATH = os.path.join(WEIGHTS_DIR, 'dcgan_iai_recu.pth')

class RecuDatasetAugmentee(Dataset):
    """Dataset qui extrait les ROI et génère des variations synthétiques (Data Augmentation)."""
    def __init__(self, image_paths, num_samples=600):
        self.patches = []
        transform_base = transforms.Compose([
            transforms.Resize((64, 64)),
            transforms.ToTensor(),
            transforms.Normalize((0.5,), (0.5,))
        ])
        
        raw_images = []
        for p in image_paths:
            if os.path.exists(p) and p.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                try:
                    img = Image.open(p).convert('L')
                    raw_images.append(img)
                except Exception as e:
                    print(f"Erreur chargement {p}: {e}")

        # Sythèse par augmentation de données si peu d'images sources
        if not raw_images:
            # Image factice de secours pour valider la compilation et l'entraînement
            raw_images.append(Image.new('L', (400, 600), color=240))

        count = 0
        while len(self.patches) < num_samples:
            base_img = raw_images[count % len(raw_images)]
            count += 1
            
            # Crop aléatoire orienté zone basse (Tampons / Signature)
            w, h = base_img.size
            crop_y1 = int(h * 0.35 + (count % 3) * 0.05 * h)
            crop_y2 = min(h, crop_y1 + int(0.5 * h))
            crop_x1 = int(0.05 * w)
            crop_x2 = int(0.95 * w)
            
            roi = base_img.crop((crop_x1, crop_y1, crop_x2, crop_y2))
            
            # Augmentations : Flou léger, contraste, rotation ±5°
            if count % 2 == 0:
                roi = roi.rotate((count % 7) - 3, fillcolor=255)
            if count % 3 == 0:
                enh = ImageEnhance.Contrast(roi)
                roi = enh.enhance(0.8 + (count % 5) * 0.1)
                
            tensor = transform_base(roi)
            self.patches.append(tensor)

    def __len__(self):
        return len(self.patches)

    def __getitem__(self, idx):
        return self.patches[idx]


def entrainer_dcgan(image_paths, epochs=200, batch_size=32, lr=0.0002):
    print("=== DÉMARRAGE DE L'ENTRAÎNEMENT DCGAN IAI ===")
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"Périphérique d'entraînement : {device}")

    dataset = RecuDatasetAugmentee(image_paths, num_samples=640)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    netG = DCGANGenerator().to(device)
    netD = DCGANDiscriminator().to(device)

    criterion = nn.BCELoss()
    optimizerD = optim.Adam(netD.parameters(), lr=lr, betas=(0.5, 0.999))
    optimizerG = optim.Adam(netG.parameters(), lr=lr, betas=(0.5, 0.999))

    fixed_noise = torch.randn(64, 100, 1, 1, device=device)
    real_label = 1.0
    fake_label = 0.0

    for epoch in range(1, epochs + 1):
        for i, data in enumerate(dataloader):
            # 1. Mise à jour du Discriminateur : max log(D(x)) + log(1 - D(G(z)))
            netD.zero_grad()
            real_cpu = data.to(device)
            b_size = real_cpu.size(0)
            label = torch.full((b_size,), real_label, dtype=torch.float, device=device)
            
            output, _ = netD(real_cpu)
            output = output.view(-1)
            errD_real = criterion(output, label)
            errD_real.backward()

            noise = torch.randn(b_size, 100, 1, 1, device=device)
            fake = netG(noise)
            label.fill_(fake_label)
            output, _ = netD(fake.detach())
            output = output.view(-1)
            errD_fake = criterion(output, label)
            errD_fake.backward()
            errD = errD_real + errD_fake
            optimizerD.step()

            # 2. Mise à jour du Générateur : max log(D(G(z)))
            netG.zero_grad()
            label.fill_(real_label)
            output, _ = netD(fake)
            output = output.view(-1)
            errG = criterion(output, label)
            errG.backward()
            optimizerG.step()

        if epoch % 50 == 0 or epoch == epochs:
            print(f"Époque [{epoch}/{epochs}] - Loss D: {errD.item():.4f} - Loss G: {errG.item():.4f}")

    # Sauvegarde du point de contrôle
    torch.save({
        'netG': netG.state_dict(),
        'netD': netD.state_dict(),
        'epoch': epochs
    }, CHECKPOINT_PATH)
    print(f"=== ENTRAÎNEMENT TERMINÉ. Poids sauvegardés dans {CHECKPOINT_PATH} ===")


if __name__ == '__main__':
    # Recherche des images de reçus disponibles dans media/recus
    media_recus = os.path.join(BASE_DIR, 'media', 'recus', '2024-2025')
    image_paths = []
    if os.path.exists(media_recus):
        for root, _, files in os.walk(media_recus):
            for f in files:
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                    image_paths.append(os.path.join(root, f))

    entrainer_dcgan(image_paths, epochs=200)
