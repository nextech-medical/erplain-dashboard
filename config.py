# config.py
import os
import re

# Connexion directe à la base OVH (pour le déploiement)
DATABASE_URL = os.getenv('DATABASE_URL')

# Configuration PostgreSQL par défaut (pour OVH)
if DATABASE_URL:
    # Extraire les informations de l'URL OVH
    match = re.search(r'postgresql://([^:]+):([^@]+)@([^:]+):([^/]+)/([^?]+)', DATABASE_URL)
    if match:
        DB_HOST = match.group(3)
        DB_PORT = match.group(4)
        DB_USER = match.group(1)
        DB_PASSWORD = match.group(2)
        DB_NAME = match.group(5)
    else:
        # Fallback si l'extraction échoue
        DB_HOST = 'postgresql-20fb082e-o33c4d6e5.database.cloud.ovh.net'
        DB_PORT = '20184'
        DB_USER = 'avnadmin'
        DB_PASSWORD = 'RwoL3kUjOpi0Y1x9V4JN'  # Votre vrai mot de passe
        DB_NAME = 'defaultdb'
else:
    # Configuration pour le développement local uniquement
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'erplain_dashboard')
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '123456')

# Configuration API Erplain
ERPLAIN_TOKEN = os.getenv('ERPLAIN_TOKEN', '437b4d61de0d0be070992852610f685f')
ERPLAIN_ENDPOINT = os.getenv('ERPLAIN_ENDPOINT', 'https://app.erplain.net/public-api/graphql/endpoint')

# Alias pour compatibilité
API_URL = ERPLAIN_ENDPOINT
BEARER_TOKEN = ERPLAIN_TOKEN

# Autres configurations
ERPLAIN_PAGE_SIZE = int(os.getenv('ERPLAIN_PAGE_SIZE', 250))
ERPLAIN_FETCH_LIMIT = int(os.getenv('ERPLAIN_FETCH_LIMIT', 500))

# Configuration API GLS
GLS_API_URL = os.getenv('GLS_API_URL', 'https://api.gls-group.eu')
GLS_AUTH_URL = os.getenv('GLS_AUTH_URL', 'https://auth.gls-group.eu')
GLS_CLIENT_ID = os.getenv('GLS_CLIENT_ID', 'votre_client_id')
GLS_CLIENT_SECRET = os.getenv('GLS_CLIENT_SECRET', 'votre_client_secret')

# Période
FETCH_YEAR = int(os.getenv("FETCH_YEAR", 2026))

# Base de données SQLite (optionnel)
DB_PATH = os.getenv("DB_PATH", "marges.db")

# Chemins pour les fichiers de frais (optionnels)
AMAZON_FEES_CSV = "data/frais_amazon.csv"
GLS_FEES_CSV = "data/frais_gls.csv"

# Pour le débogage - afficher la configuration au démarrage
print(f"Connexion à la base: {DB_HOST}:{DB_PORT} (user: {DB_USER})")
