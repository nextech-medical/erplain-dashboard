FROM python:3.9-slim

WORKDIR /app

# Installer les dépendances système
RUN apt-get update && apt-get install -y libpq-dev gcc && apt-get clean

# Copier et installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier tout le code
COPY . .

# Créer les répertoires avec les bonnes permissions
RUN mkdir -p /app/.streamlit /workspace && \
    chmod -R 777 /app /workspace

# Changer l'utilisateur pour ovh (42420)
USER 42420

# Exposer le port
EXPOSE 8080

# Lancer l'application avec les bons paramètres
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0", "--server.fileWatcherType=none", "--browser.gatherUsageStats=false"]
