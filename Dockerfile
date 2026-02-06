FROM python:3.11-slim

# Installation des dépendances système pour Chrome
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Définir le répertoire de travail
WORKDIR /app

# Copier les requirements et installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code de l'application
COPY main.py .

# Variables d'environnement pour Chrome
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Exposer le port
EXPOSE 8001

# Commande de démarrage
CMD ["python", "main.py"]
