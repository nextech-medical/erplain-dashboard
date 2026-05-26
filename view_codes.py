# view_codes.py
import json
import os

DATA_DIR = "data"

def main():
    print("\n" + "=" * 60)
    print("📋 CODES DE SUIVI EXTRAITS")
    print("=" * 60)
    
    # Trouver le dernier fichier JSON
    if not os.path.exists(DATA_DIR):
        print("❌ Dossier data/ non trouvé")
        return
    
    json_files = [f for f in os.listdir(DATA_DIR) if f.startswith('tracking_') and f.endswith('.json')]
    
    if not json_files:
        print("❌ Aucun fichier de tracking trouvé")
        print("   Exécutez d'abord: python extract_tracking_fixed.py")
        return
    
    # Prendre le plus récent
    latest = max(json_files, key=lambda f: os.path.getmtime(os.path.join(DATA_DIR, f)))
    
    with open(os.path.join(DATA_DIR, latest), 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"\n📁 Fichier: {latest}")
    print(f"📊 {len(data)} codes trouvés\n")
    
    for item in data:
        print(f"   {item['order_number']:<15} → {item['tracking_code']}")

if __name__ == "__main__":
    main()