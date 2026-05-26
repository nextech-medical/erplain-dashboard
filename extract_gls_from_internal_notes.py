# extract_gls_from_internal_notes.py
import requests
import json
import re
import csv
from datetime import datetime
from config import API_URL, BEARER_TOKEN

headers = {
    "Authorization": f"Bearer {BEARER_TOKEN}",
    "Content-Type": "application/json"
}

def extract_tracking_from_internal_notes(internal_notes):
    """Extrait le numéro de suivi GLS depuis internal_notes"""
    if not internal_notes:
        return None
    
    # Patterns pour trouver les tracking GLS
    patterns = [
        # Format GLS standard
        r'(GL\d{10,14}FR?)',
        r'(gl\d{10,14}fr?)',
        
        # Tracking ID explicite
        r'[Tt]racking\s*(?:ID|id)?\s*[:\-]?\s*([A-Z0-9]{10,20})',
        r'[Ss]uivi\s*(?:ID|id)?\s*[:\-]?\s*([A-Z0-9]{10,20})',
        
        # GLS dans le texte
        r'GLS\s*(?:ID|id)?\s*[:\-]?\s*([A-Z0-9]{10,20})',
        
        # Simple number (10-16 digits)
        r'\b(\d{10,16})\b',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, internal_notes, re.IGNORECASE)
        if match:
            tracking = match.group(1) if match.groups() else match.group(0)
            tracking = tracking.upper().strip()
            if len(tracking) >= 10:
                return tracking
    
    return None

def fetch_all_shipping_orders(limit=500):
    """Récupère tous les BL avec leur internal_notes"""
    all_orders = []
    page = 1
    page_size = 100
    
    print("📥 Récupération des BL depuis ERPLAIN...")
    
    while len(all_orders) < limit:
        query = f"""
        {{
          ShippingOrders(
            page: {page},
            page_size: {page_size},
            sort: {{ by: "shipping_date", direction: "DESC" }}
          ) {{
            edges {{
              node {{
                id
                order_number
                external_reference
                shipping_date
                shipping_order_status
                internal_notes
              }}
            }}
          }}
        }}
        """
        
        try:
            response = requests.post(API_URL, json={"query": query}, headers=headers, timeout=30)
            data = response.json()
            
            if "errors" in data:
                print(f"❌ Erreur: {data['errors']}")
                break
            
            shipping_orders = data.get("data", {}).get("ShippingOrders", {})
            edges = shipping_orders.get("edges", {})
            nodes = edges.get("node", [])
            
            if not nodes:
                break
            
            all_orders.extend(nodes)
            print(f"   Page {page}: {len(nodes)} BL (total: {len(all_orders)})")
            
            if len(nodes) < page_size:
                break
                
            page += 1
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            break
    
    return all_orders

def main():
    print("=" * 70)
    print("🚀 EXTRACTION DES NUMÉROS DE SUIVI GLS")
    print("=" * 70)
    
    # 1. Récupérer les BL
    orders = fetch_all_shipping_orders()
    print(f"\n📊 Total BL récupérés: {len(orders)}")
    
    # 2. Extraire les tracking depuis internal_notes
    print("\n🔍 Extraction des tracking depuis internal_notes...")
    print("-" * 50)
    
    results = []
    for order in orders:
        order_number = order.get('order_number')
        internal_notes = order.get('internal_notes', '')
        
        tracking = extract_tracking_from_internal_notes(internal_notes)
        
        if tracking:
            results.append({
                'order_number': order_number,
                'tracking_number': tracking,
                'shipping_date': order.get('shipping_date'),
                'external_reference': order.get('external_reference'),
                'status': order.get('shipping_order_status'),
                'internal_notes': internal_notes[:200]  # Garder un extrait
            })
            print(f"   ✅ {order_number} → {tracking}")
    
    # 3. Résultats
    print(f"\n📊 Tracking trouvés: {len(results)}/{len(orders)}")
    
    # 4. Sauvegarder
    output_file = f"gls_tracking_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n💾 Sauvegardé: {output_file}")
    
    # 5. CSV
    csv_file = f"gls_tracking_{datetime.now().strftime('%Y%m%d')}.csv"
    with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=['order_number', 'tracking_number', 'shipping_date', 'external_reference', 'status'])
        writer.writeheader()
        writer.writerows(results)
    print(f"💾 CSV sauvegardé: {csv_file}")
    
    # 6. Afficher la liste
    if results:
        print("\n" + "=" * 70)
        print("📋 LISTE COMPLÈTE DES NUMÉROS DE SUIVI")
        print("=" * 70)
        for r in results:
            print(f"   {r['order_number']:<20} → {r['tracking_number']}")
    
    return results

if __name__ == "__main__":
    results = main()