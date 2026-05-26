# auto_sync_suppliers.py
"""
Synchronisation automatique des fournisseurs (à exécuter périodiquement)
"""
import schedule
import time
import logging
from datetime import datetime
from fetch_and_update_all_suppliers import sync_all_suppliers

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

def sync_job():
    """Tâche de synchronisation"""
    logger.info("🔄 Démarrage synchronisation des fournisseurs...")
    try:
        supplier_count, product_count, updated_count = sync_all_suppliers()
        logger.info(f"✅ Synchronisation terminée: {supplier_count} fournisseurs, {product_count} produits, {updated_count} factures mises à jour")
    except Exception as e:
        logger.error(f"❌ Erreur lors de la synchronisation: {e}")

def run_scheduler():
    """Exécute le planificateur"""
    print("\n" + "="*60)
    print("🤖 SYNCHRONISEUR AUTOMATIQUE DE FOURNISSEURS")
    print("="*60)
    
    # Exécution immédiate
    sync_job()
    
    # Planification
    print("\n📅 Planification:")
    print("   - Toutes les heures: Synchronisation des fournisseurs")
    print("   - Tous les jours à 03:00: Synchronisation complète")
    
    schedule.every().hour.do(sync_job)
    schedule.every().day.at("03:00").do(sync_job)
    
    print("\n⏰ Service démarré. Appuyez sur Ctrl+C pour arrêter\n")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n⏹️ Service arrêté")

if __name__ == "__main__":
    run_scheduler()