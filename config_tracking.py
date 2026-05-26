# config_tracking.py
import os
from dotenv import load_dotenv

# Charger votre configuration existante
load_dotenv('.env.dev')

# ERPLAIN
ERPLAIN_TOKEN = os.getenv('437b4d61de0d0be070992852610f685f')
ERPLAIN_ENDPOINT = os.getenv('ERPLAIN_ENDPOINT', 'https://app.erplain.net/public-api/graphql/endpoint')

# Dossiers
DATA_DIR = 'data'
TRACKING_FILE = os.path.join(DATA_DIR, 'tracking_numbers.json')

# Pour le mode démon
INTERVAL_MINUTES = 30  # Vérification toutes les 30 minutes