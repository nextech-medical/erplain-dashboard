# view_tracking.py
"""Affiche tous les codes de suivi extraits"""

import json
import os
from datetime import datetime

DATA_DIR = "data"
TRACKING_FILE = os.path.join(DATA_DIR, 'all_tracking_codes.json')

def main():
    print("\n" + "=" * 70)
    print("📋 LISTE DES CODES DE SUIVI")
    print("=" * 70)
    
    if not os.path.exists(TRACKING_FILE):
        print("❌ Aucune donnée trouvée")
        print("   Exécutez d'abord: python extract_tracking_final.py")
        return
    
    with open(TRACKING_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if not data:
        print("❌ Aucun code trouvé")
        return
    
    # Grouper par type
    by_type = {}
    for item in data:
        code_type = item.get('code_type', 'UNKNOWN')
        if code_type not in by_type:
            by_type[code_type] = []
        by_type[code_type].append(item)
    
    print(f"\n📊 {len(data)} codes trouvés\n")
    
    for code_type, items in by_type.items():
        print(f"\n🔹 Type: {code_type} ({len(items)} codes)")
        print("-" * 50)
        for item in items[:20]:
            date = item.get('shipping_date', '')[:10] if item.get('shipping_date') else 'N/A'
            print(f"   {item['order_number']:<15} → {item['tracking_code']:<20} ({date})")
        
        if len(items) > 20:
            print(f"   ... et {len(items) - 20} autres")

if __name__ == "__main__":
    main()