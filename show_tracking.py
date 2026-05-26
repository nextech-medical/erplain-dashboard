# show_tracking.py
import json

def main():
    print("\n" + "=" * 60)
    print("📦 NUMÉROS DE SUIVI GLS")
    print("=" * 60)
    
    # Essayer de lire le fichier des tracking
    try:
        with open('gls_tracking_list_2026.json', 'r', encoding='utf-8') as f:
            tracking = json.load(f)
        
        print(f"\n✅ {len(tracking)} numéros de suivi trouvés\n")
        
        for t in tracking:
            print(f"   {t['order_number']:<15} → {t['tracking_number']}")
            
    except FileNotFoundError:
        print("\n❌ Aucun fichier de tracking trouvé")
        print("   Exécutez d'abord: python fetch_delivery_notes.py")

if __name__ == "__main__":
    main()