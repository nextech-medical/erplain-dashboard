# run_sync.py
import schedule
import time
import logging
from datetime import datetime
from sync_suppliers import sync_all, import_suppliers_from_csv

# Configuration des logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sync_suppliers.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def job():
    """Tâche de synchronisation"""
    logger.info("Démarrage de la synchronisation...")
    count = sync_all()
    logger.info(f"Synchronisation terminée: {count} fournisseurs")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔄 SYNCHRONISEUR AUTOMATIQUE ERPLEAN → POSTGRESQL")
    print("="*60)
    print("\nOptions:")
    print("1. Synchronisation unique (API)")
    print("2. Synchronisation automatique (toutes les heures)")
    print("3. Import depuis CSV")
    print("4. Quitter")
    
    choix = input("\nVotre choix (1-4): ")
    
    if choix == "1":
        sync_all()
        
    elif choix == "2":
        print("\n🔄 Synchronisation automatique toutes les heures...")
        print("   (Appuyez sur Ctrl+C pour arrêter)\n")
        
        # Exécution immédiate
        job()
        
        # Planification toutes les heures
        schedule.every().hour.do(job)
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)
        except KeyboardInterrupt:
            print("\n⏹️ Synchroniseur arrêté")
            
    elif choix == "3":
        csv_file = input("Chemin du fichier CSV: ")
        import_suppliers_from_csv(csv_file)
        
    else:
        print("Au revoir!")