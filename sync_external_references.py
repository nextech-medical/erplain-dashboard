# sync_external_references.py
import requests
import json
import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, API_URL, BEARER_TOKEN

def fetch_external_references():
    """Récupère les références externes des commandes depuis Erplain."""
    
    all_orders = []
    page = 1
    page_size = 100
    
    while True:
        print(f"📥 Récupération des commandes page {page}...")
        
        query = f"""
        query {{
          SalesOrders(page: {page}, page_size: {page_size}, sort: {{ by: "created", direction: "DESC" }}) {{
            edges {{
              node {{
                id
                order_id
                external_reference
                created
              }}
            }}
          }}
        }}
        """
        
        headers = {
            "Authorization": f"Bearer {BEARER_TOKEN}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(API_URL, json={"query": query}, headers=headers, timeout=30)
            
            if response.status_code != 200:
                print(f"❌ Erreur HTTP {response.status_code}")
                break
            
            data = response.json()
            
            if "errors" in data:
                print("❌ Erreur GraphQL:", data["errors"])
                break
            
            orders_data = data.get("data", {}).get("SalesOrders", {})
            edges = orders_data.get("edges", [])
            
            if not edges:
                break
            
            for edge in edges:
                node = edge.get("node")
                if node:
                    all_orders.append(node)
            
            print(f"   Page {page}: {len(edges)} commandes, total {len(all_orders)}")
            
            if len(edges) < page_size:
                break
            page += 1
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            break
    
    return all_orders

def update_invoices_with_external_reference(orders):
    """Met à jour les factures avec les références externes."""
    
    if not orders:
        print("⚠️ Aucune commande récupérée")
        return 0
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    count = 0
    for order in orders:
        order_id = order.get('order_id')
        external_reference = order.get('external_reference')
        
        if order_id and external_reference:
            cursor.execute("""
                UPDATE invoices 
                SET reference_externe = %s
                WHERE order_number = %s
            """, (external_reference, order_id))
            count += cursor.rowcount
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ {count} factures mises à jour avec référence externe")
    return count

def sync_external_references():
    """Synchronisation complète des références externes."""
    
    print("\n" + "="*60)
    print("🔄 SYNCHRONISATION RÉFÉRENCES EXTERNES")
    print("="*60)
    
    # 1. Ajouter la colonne
    add_external_reference_column()
    
    # 2. Récupérer les commandes
    print("\n📦 Récupération des commandes depuis Erplain...")
    orders = fetch_external_references()
    
    # 3. Mettre à jour les factures
    if orders:
        count = update_invoices_with_external_reference(orders)
        print(f"\n📊 {count} factures mises à jour")
    
    print("="*60)

if __name__ == "__main__":
    sync_external_references()