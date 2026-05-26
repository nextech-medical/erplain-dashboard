# simple_tracking.py - Utilise VOTRE fichier delivery_notes_2026.json
import json
import os

# Vérifier si le fichier existe
if not os.path.exists('delivery_notes_2026.json'):
    print("❌ Fichier delivery_notes_2026.json non trouvé")
    print("   Exécutez d'abord: python fetch_delivery_notes.py")
    exit(1)

# Lire le fichier
with open('delivery_notes_2026.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Extraire les tracking
tracking_list = []
for item in data:
    tracking = item.get('tracking_gls')
    if tracking:
        tracking_list.append({
            'order_number': item.get('order_number'),
            'tracking_number': tracking,
            'shipping_date': item.get('shipping_date')
        })

# Afficher
print("\n" + "=" * 60)
print(f"📦 NUMÉROS DE SUIVI GLS ({len(tracking_list)} trouvés)")
print("=" * 60)

if tracking_list:
    for t in tracking_list:
        print(f"   {t['order_number']:<20} → {t['tracking_number']}")
else:
    print("   Aucun numéro de suivi trouvé dans les BL")
    print("   (Les numéros GLS sont peut-être dans un format différent)")

# Sauvegarder
with open('gls_tracking_numbers.json', 'w', encoding='utf-8') as f:
    json.dump(tracking_list, f, indent=2, ensure_ascii=False)

print(f"\n💾 Sauvegardé dans: gls_tracking_numbers.json")