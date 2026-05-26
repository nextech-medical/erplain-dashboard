# auto_sync_scheduler.py
import schedule
import time
import logging
from datetime import datetime
from fetch_suppliers_auto import sync_suppliers

# Configuration des logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('supplier_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def job():
    """Tâche de synchronisation"""
    logger.info("Démarrage synchronisation fournisseurs...")
    count = sync_suppliers()
    logger.info(f"Synchronisation terminée: {count} fournisseurs")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🤖 SYNCHRONISEUR AUTOMATIQUE FOURNISSEURS ERPLEAN")
    print("="*60)
    
    # Exécution immédiate
    job()
    
    # Planification
    print("\n📅 Planification:")
    print("   - Toutes les heures: Synchronisation")
    print("   - Tous les jours à 02:00: Synchronisation complète")
    
    schedule.every().hour.do(job)  # Toutes les heures
    schedule.every().day.at("02:00").do(job)  # Aussi à 2h du matin
    
    print("\n⏰ Service démarré. Appuyez sur Ctrl+C pour arrêter\n")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n⏹️ Service arrêté")