# fetch_invoices_fixed.py
import requests
import json
import psycopg2
from datetime import datetime
from config import API_URL, BEARER_TOKEN, DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def fetch_invoices_with_refs():
    """Récupère les factures avec leurs références externes"""
    
    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "Content-Type": "application/json"
    }
    
    all_invoices = []
    page = 1
    page_size = 100
    
    print("\n" + "=" * 60)
    print("📥 RÉCUPÉRATION DES FACTURES (méthode get_invoices.py)")
    print("=" * 60)
    
    while True:
        print(f"   Page {page}...")
        
        # Utiliser la même structure que get_invoices.py qui fonctionne
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
                reference_externe
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
                # Afficher plus de détails pour debug
                print(f"   Détails: {data['errors']}")
                break
            
            invoices_data = data.get("data", {}).get("Invoices", {})
            edges = invoices_data.get("edges", {})
            
            # Extraire les nodes comme dans get_invoices.py
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

def update_database(invoices):
    """Met à jour la base avec les références"""
    
    if not invoices:
        print("❌ Aucune facture à traiter")
        return 0
    
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
    
    updated_refs = 0
    updated_managers = 0
    
    for inv in invoices:
        invoice_id = str(inv.get('id'))
        # Note: le champ dans l'API peut être 'reference_externe' ou 'external_reference'
        external_ref = inv.get('reference_externe') or inv.get('external_reference')
        order_number = inv.get('order_number')
        label = inv.get('label')
        
        if external_ref and external_ref != 'None':
            # Détecter la plateforme
            platform = None
            if '-' in external_ref and len(external_ref) > 10:
                if external_ref.count('-') >= 2:
                    platform = 'Amazon'
                elif external_ref.startswith('PO-'):
                    platform = 'Temu'
            
            # Mettre à jour la facture
            cursor.execute("""
                UPDATE invoices 
                SET reference_externe = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND (reference_externe IS NULL OR reference_externe = '')
            """, (external_ref, invoice_id))
            
            if cursor.rowcount > 0:
                updated_refs += 1
                
                # Mettre à jour le gestionnaire
                if platform:
                    cursor.execute("""
                        UPDATE invoices 
                        SET gestionnaire = %s
                        WHERE id = %s AND (gestionnaire IS NULL OR gestionnaire = 'Direct')
                    """, (platform, invoice_id))
                    if cursor.rowcount > 0:
                        updated_managers += 1
                
                if updated_refs <= 30:
                    print(f"   ✅ {order_number or label}: {external_ref[:40]} -> {platform or '?'}")
    
    conn.commit()
    
    # Statistiques
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
    
    return updated_refs

def main():
    # 1. Récupérer les factures
    invoices = fetch_invoices_with_refs()
    
    if not invoices:
        print("\n⚠️ Aucune facture récupérée")
        print("\n💡 Suggestions:")
        print("   1. Vérifiez votre token ERPLAIN_TOKEN dans config.py")
        print("   2. Vérifiez que vous avez des factures dans Erplain")
        print("   3. Essayez d'exécuter get_invoices.py pour tester l'API")
        return
    
    # 2. Mettre à jour la base
    updated = update_database(invoices)
    
    print(f"\n✅ {updated} factures mises à jour avec références")

if __name__ == "__main__":
    main()