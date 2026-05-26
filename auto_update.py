# auto_update.py
import subprocess
import time
from datetime import datetime
import schedule

def run_update():
    """Exécute la mise à jour"""
    print(f"\n[{datetime.now()}] 🚀 Lancement de la mise à jour...")
    result = subprocess.run(["python", "update_database.py"], capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(f"Erreurs: {result.stderr}")

def run_update_once():
    """Exécute la mise à jour une seule fois"""
    run_update()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        # Exécution unique
        run_update_once()
    else:
        # Exécution automatique toutes les heures
        print("🔄 Démarrage du service de mise à jour automatique")
        print("📅 Les mises à jour s'exécuteront toutes les heures")
        
        schedule.every().hour.do(run_update)
        
        while True:
            schedule.run_pending()
            time.sleep(60)