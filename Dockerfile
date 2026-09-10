# Image de base Python 3.10 slim
FROM python:3.10-slim

# Variables d'environnement Python & OCR
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TESSERACT_CMD=/usr/bin/tesseract

# Répertoire de travail dans le conteneur
WORKDIR /app

# Dépendances système nécessaires pour psycopg2, Pillow, ReportLab, Tesseract OCR et outils réseau
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    postgresql-client \
    netcat-openbsd \
    tesseract-ocr \
    tesseract-ocr-fra \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    libwebp-dev \
    libtiff-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libopenjp2-7-dev \
    libpng-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copier le fichier requirements.txt
COPY requirements.txt /app/

# Installer les dépendances Python
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Créer les dossiers nécessaires
RUN mkdir -p /app/logs /app/staticfiles /app/media

# Copier le reste de l'application
COPY . /app/

# Rendre les scripts d'entrée exécutables
RUN chmod +x /app/entrypoint.sh

# Exposer le port par défaut de Django
EXPOSE 8000

# Utiliser le script d'entrée
ENTRYPOINT ["/app/entrypoint.sh"]

