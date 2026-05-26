# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration PostgreSQL
DB_HOST = os.getenv('DB_HOST', 'localhost')
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
# Configuration API GLS (à remplacer par vos vraies clés)
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