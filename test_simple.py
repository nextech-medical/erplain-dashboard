# test_internal_notes.py - Test simple pour voir les internal_notes
import requests
import json
from config import API_URL, BEARER_TOKEN

headers = {
    "Authorization": f"Bearer {BEARER_TOKEN}",
    "Content-Type": "application/json"
}

query = """
{
  ShippingOrders(page: 1, page_size: 5) {
    edges {
      node {
        order_number
        shipping_date
        internal_notes
        notes
      }
    }
  }
}
"""

print("📥 Récupération des BL avec internal_notes...")

response = requests.post(API_URL, json={"query": query}, headers=headers)
data = response.json()

print(f"Status: {response.status_code}")

if response.status_code == 200:
    shipping_orders = data.get("data", {}).get("ShippingOrders", {})
    edges = shipping_orders.get("edges", {})
    nodes = edges.get("node", [])
    
    print(f"\n✅ {len(nodes)} BL trouvés\n")
    
    for node in nodes:
        print("=" * 50)
        print(f"BL: {node.get('order_number')}")
        print(f"Date: {node.get('shipping_date')}")
        
        internal = node.get('internal_notes', '')
        if internal:
            print(f"📝 internal_notes: {internal[:300]}")
        else:
            print("📝 internal_notes: (vide)")
        
        regular = node.get('notes', '')
        if regular:
            print(f"📝 notes: {regular[:200]}")
        
        print()
else:
    print(f"❌ Erreur: {data}")