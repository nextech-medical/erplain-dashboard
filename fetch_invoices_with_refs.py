# fetch_invoices_with_refs.py
import requests
import json
import psycopg2
from datetime import datetime
from config import API_URL, BEARER_TOKEN, DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def fetch_invoices_from_api():
    """Récupère les factures depuis l'API Erplain avec leurs références"""
    
    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "Content-Type": "application/json"
    }
    
    all_invoices = []
    page = 1
    page_size = 100
    
    print("\n" + "=" * 60)
    print("📥 RÉCUPÉRATION DES FACTURES DEPUIS L'API")
    print("=" * 60)
    
    while True:
        print(f"   Page {page}...")
        
        query = f"""
        {{
          Invoices(page: {page}, page_size: {page_size}, sort: {{ by: "created", direction: "DESC" }}) {{
            edges {{
              node {{
                id
                label
                order_number
                created
                total
                customer {{
                  label
                  emails
                }}
                external_reference
                notes
              }}
            }}
          }}
        }}
        """
        
        try:
            response = requests.post(API_URL, json={"query": query}, headers=headers, timeout=60)
            
            if response.status_code != 200:
                print(f"   ❌ Erreur HTTP {response.status_code}")
                break
            
            data = response.json()
            
            if "errors" in data:
                print(f"   ❌ Erreur GraphQL: {data['errors'][0].get('message', 'Unknown')[:100]}")
                break
            
            invoices_data = data.get("data", {}).get("Invoices", {})
            edges = invoices_data.get("edges", {})
            
            # Extraire les nodes
            nodes = []
            if isinstance(edges, dict):
                node_data = edges.get("node")
                if isinstance(node_data, list):
                    nodes = node_data
                elif node_data:
                    nodes = [node_data]
            elif isinstance(edges, list):
                for edge in edges:
                    if isinstance(edge, dict):
                        node = edge.get("node")
                        if node:
                            nodes.append(node)
            
            if not nodes:
                print(f"   ✅ Plus de factures")
                break
            
            all_invoices.extend(nodes)
            print(f"   ✅ {len(nodes)} factures (total: {len(all_invoices)})")
            
            if len(nodes) < page_size:
                break
                
            page += 1
            
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
            break
    
    print(f"\n📊 Total factures récupérées: {len(all_invoices)}")
    return all_invoices

def update_database_with_refs(invoices):
    """Met à jour la base avec les références externes"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 60)
    print("💾 MISE À JOUR DE LA BASE")
    print("=" * 60)
    
    updated = 0
    for inv in invoices:
        invoice_id = str(inv.get('id'))
        external_ref = inv.get('external_reference')
        order_number = inv.get('order_number')
        label = inv.get('label')
        
        if external_ref:
            # Détecter la plateforme
            if external_ref and '-' in external_ref and len(external_ref) > 15:
                platform = 'Amazon'
            elif external_ref and external_ref.startswith('PO-'):
                platform = 'Temu'
            else:
                platform = None
            
            cursor.execute("""
                UPDATE invoices 
                SET reference_externe = %s,
                    gestionnaire = COALESCE(%s, gestionnaire),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND (reference_externe IS NULL OR reference_externe = '')
            """, (external_ref, platform, invoice_id))
            
            if cursor.rowcount > 0:
                updated += 1
                if updated <= 20:
                    print(f"   ✅ {order_number or label}: {external_ref[:30]} -> {platform or '?'}")
    
    conn.commit()
    
    # Statistiques finales
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as avec_ref,
            COUNT(CASE WHEN gestionnaire = 'Amazon' THEN 1 END) as amazon,
            COUNT(CASE WHEN gestionnaire = 'Temu' THEN 1 END) as temu,
            COUNT(CASE WHEN gestionnaire = 'Direct' THEN 1 END) as direct
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
    """)
    
    row = cursor.fetchone()
    print(f"\n📊 RÉSULTAT FINAL:")
    print(f"   Total factures: {row[0]}")
    print(f"   Avec référence: {row[1]}")
    print(f"   Amazon: {row[2]}")
    print(f"   Temu: {row[3]}")
    print(f"   Direct: {row[4]}")
    
    cursor.close()
    conn.close()
    
    return updated

def main():
    # 1. Récupérer les factures depuis l'API
    invoices = fetch_invoices_from_api()
    
    if not invoices:
        print("❌ Aucune facture récupérée")
        return
    
    # 2. Mettre à jour la base
    updated = update_database_with_refs(invoices)
    
    print(f"\n✅ {updated} factures mises à jour")

if __name__ == "__main__":
    main()