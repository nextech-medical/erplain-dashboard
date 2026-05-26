# extract_tracking_fixed.py
import requests
import json
import re
import csv
import os
from datetime import datetime, timedelta

# Configuration - Utilise vos variables existantes
ERPLAIN_TOKEN = "437b4d61de0d0be070992852610f685f"
ERPLAIN_ENDPOINT = "https://app.erplain.net/public-api/graphql/endpoint"
DATA_DIR = "data"

HEADERS = {
    "Authorization": f"Bearer {ERPLAIN_TOKEN}",
    "Content-Type": "application/json"
}

def ensure_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def fetch_shipping_orders():
    """Récupère les BL - Version CORRIGÉE sans virgules dans la requête"""
    all_orders = []
    page = 1
    page_size = 50
    
    print("📥 Récupération des BL depuis ERPLAIN...")
    print("-" * 50)
    
    while True:
        # Requête CORRIGÉE - pas de virgules après les accolades
        query = f"""
        {{
          ShippingOrders(
            page: {page}
            page_size: {page_size}
            sort: {{
              by: "shipping_date"
              direction: "DESC"
            }}
          ) {{
            edges {{
              node {{
                id
                order_number
                external_reference
                shipping_date
                shipping_order_status
                internal_notes
                notes
              }}
            }}
          }}
        }}
        """
        
        try:
            response = requests.post(ERPLAIN_ENDPOINT, json={"query": query}, headers=HEADERS, timeout=30)
            
            if response.status_code != 200:
                print(f"   ❌ HTTP {response.status_code}")
                break
            
            data = response.json()
            
            if "errors" in data:
                print(f"   ❌ GraphQL: {data['errors'][0].get('message', 'Unknown')[:150]}")
                # Afficher la structure pour debug
                print(f"   Debug - Réponse: {str(data)[:300]}")
                break
            
            # Extraction des nodes
            shipping_orders = data.get("data", {}).get("ShippingOrders", {})
            edges = shipping_orders.get("edges", {})
            
            nodes = []
            if isinstance(edges, dict):
                nodes = edges.get("node", [])
            elif isinstance(edges, list):
                for edge in edges:
                    if isinstance(edge, dict):
                        node = edge.get("node")
                        if node:
                            nodes.append(node)
            
            if not nodes:
                print(f"   ✅ Plus de BL page {page}")
                break
            
            all_orders.extend(nodes)
            print(f"   Page {page}: {len(nodes)} BL (total: {len(all_orders)})")
            
            if len(nodes) < page_size:
                break
                
            page += 1
            
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
            break
    
    return all_orders

def extract_code(text):
    """Extrait les codes des notes"""
    if not text or not isinstance(text, str):
        return None
    
    # Nettoyer
    clean = re.sub(r'<[^>]+>', ' ', text)
    clean = re.sub(r'&[a-z]+;', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    
    if not clean:
        return None
    
    # Patterns pour les codes
    patterns = [
        r'\b(00[A-Z0-9]{4,14})\b',  # Comme 00KT0Q4C
        r'\b(GL\d{10,14}FR?)\b',     # GLS standard
        r'\b([A-Z0-9]{8,16})\b',     # Autres codes
    ]
    
    for pattern in patterns:
        match = re.search(pattern, clean, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    
    return clean if len(clean) >= 4 and len(clean) <= 20 else None

def main():
    print("\n" + "=" * 60)
    print(f"🚀 EXTRACTION - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 1. Récupérer les BL
    orders = fetch_shipping_orders()
    
    if not orders:
        print("\n❌ Aucun BL récupéré")
        print("\n💡 Vérifiez:")
        print("   1. Votre token ERPLAIN est valide")
        print("   2. Vous avez des BL dans ERPLAIN")
        return
    
    print(f"\n📊 Total BL récupérés: {len(orders)}")
    
    # 2. Extraire les codes
    print("\n🔍 Extraction des codes depuis internal_notes...")
    print("-" * 60)
    
    results = []
    for order in orders:
        order_number = order.get('order_number')
        internal_notes = order.get('internal_notes', '')
        
        code = extract_code(internal_notes)
        
        if code:
            results.append({
                'order_number': order_number,
                'tracking_code': code,
                'shipping_date': order.get('shipping_date'),
                'external_reference': order.get('external_reference'),
                'status': order.get('shipping_order_status')
            })
            print(f"   ✅ {order_number} → {code}")
        elif internal_notes:
            # Afficher ce qui n'a pas été capturé
            clean = re.sub(r'<[^>]+>', ' ', internal_notes).strip()
            if clean:
                print(f"   ⚠️ {order_number} → non capturé: '{clean}'")
    
    # 3. Sauvegarder
    if results:
        ensure_dir()
        
        # JSON
        output_file = os.path.join(DATA_DIR, f'tracking_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Sauvegardé: {output_file}")
        
        # CSV
        csv_file = os.path.join(DATA_DIR, f'tracking_{datetime.now().strftime("%Y%m%d")}.csv')
        with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=['order_number', 'tracking_code', 'shipping_date', 'external_reference', 'status'])
            writer.writeheader()
            writer.writerows(results)
        print(f"💾 CSV: {csv_file}")
    
    # 4. Résumé
    print("\n" + "=" * 60)
    print(f"📊 RÉSULTAT: {len(results)} codes trouvés sur {len(orders)} BL")
    print("=" * 60)
    
    return results

if __name__ == "__main__":
    main()