# run_gls_sync.py
"""
Script à exécuter périodiquement (cron/task scheduler)
pour synchroniser les numéros de suivi GLS
"""
import os
import sys
import logging
from datetime import datetime
from sync_gls_tracking import sync_all

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/gls_sync_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)

def main():
    logging.info("=== Début synchronisation GLS ===")
    
    try:
        # Synchronisation complète
        tracking_data, status_updated = sync_all(
            year=2026,
            limit_extract=100,  # Limiter pour l'exécution automatique
            limit_status=50
        )
        
        logging.info(f"Synchronisation terminée: {len(tracking_data) if tracking_data else 0} extraits, {status_updated} statuts mis à jour")
        
    except Exception as e:
        logging.error(f"Erreur lors de la synchronisation: {e}", exc_info=True)
        sys.exit(1)
    
    logging.info("=== Fin synchronisation GLS ===")

if __name__ == "__main__":
    # Créer le dossier logs si nécessaire
    os.makedirs("logs", exist_ok=True)
    main()