# update_invoice_data.py
import requests
import json
import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, API_URL, BEARER_TOKEN

def fetch_all_invoices_with_details():
    """Récupère toutes les factures avec les détails clients."""
    
    all_invoices = []
    page = 1
    page_size = 100
    
    while True:
        print(f"📥 Récupération page {page}...")
        
        query = f"""
        query {{
          Invoices(page: {page}, page_size: {page_size}) {{
            edges {{
              node {{
                id
                label
                order_number
                status
                created
                due_date
                subtotal
                total
                external_reference
                notes
                customer {{
                  id
                  label
                  emails
                }}
                line_items {{
                  edges {{
                    node {{
                      product {{
                        id
                        label
                        ... on variantType {{
                          sku
                        }}
                      }}
                      quantity
                      price
                      total
                    }}
                  }}
                }}
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
                print(f"❌ Erreurs: {data['errors']}")
                break
            
            invoices_data = data.get("data", {}).get("Invoices", {})
            edges = invoices_data.get("edges", {})
            nodes = edges.get("node", [])
            
            if not nodes:
                print("✅ Plus de factures")
                break
            
            all_invoices.extend(nodes)
            print(f"   ✅ {len(nodes)} factures (total: {len(all_invoices)})")
            
            if len(nodes) < page_size:
                break
            page += 1
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            break
    
    return all_invoices

def update_invoices_database(invoices):
    """Met à jour la base de données avec les infos clients."""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Ajouter les colonnes si elles n'existent pas
    cursor.execute("""
        ALTER TABLE invoices 
        ADD COLUMN IF NOT EXISTS customer_name TEXT,
        ADD COLUMN IF NOT EXISTS customer_email TEXT,
        ADD COLUMN IF NOT EXISTS reference_externe TEXT,
        ADD COLUMN IF NOT EXISTS notes_text TEXT
    """)
    conn.commit()
    
    count = 0
    for invoice in invoices:
        try:
            customer = invoice.get('customer', {})
            customer_name = customer.get('label')
            customer_emails = customer.get('emails', [])
            customer_email = customer_emails[0] if customer_emails else None
            
            cursor.execute("""
                UPDATE invoices 
                SET customer_name = %s,
                    customer_email = %s,
                    reference_externe = %s,
                    notes_text = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                customer_name,
                customer_email,
                invoice.get('external_reference'),
                invoice.get('notes'),
                str(invoice.get('id'))
            ))
            count += 1
            
            if count % 50 == 0:
                print(f"   Mise à jour: {count}/{len(invoices)}...")
                conn.commit()
                
        except Exception as e:
            print(f"❌ Erreur facture {invoice.get('id')}: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ {count} factures mises à jour")
    return count

def update_suppliers_from_products():
    """Met à jour les fournisseurs des factures à partir des produits."""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Vérifier si la table products existe
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'products'
        )
    """)
    products_exist = cursor.fetchone()[0]
    
    if not products_exist:
        print("⚠️ Table 'products' non trouvée")
        return 0
    
    # Mettre à jour les fournisseurs via les SKU
    cursor.execute("""
        UPDATE invoices i
        SET fournisseur = p.supplier_name
        FROM invoice_lines il
        JOIN products p ON p.sku = il.product_sku
        WHERE i.id = il.invoice_id
        AND p.supplier_name IS NOT NULL
        AND p.supplier_name != ''
        AND (i.fournisseur IS NULL OR i.fournisseur = 'Non spécifié')
    """)
    
    conn.commit()
    affected = cursor.rowcount
    cursor.close()
    conn.close()
    
    print(f"✅ {affected} factures mises à jour avec fournisseur")
    return affected

def update_platforms():
    """Met à jour les plateformes (gestionnaire) des factures."""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Déduire la plateforme du numéro de commande ou référence
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = CASE
            WHEN order_number LIKE 'PO-%' THEN 'TEMU FR'
            WHEN reference_externe LIKE 'PO-%' THEN 'TEMU FR'
            WHEN order_number LIKE '40%' THEN 'Amazon .fr'
            WHEN reference_externe LIKE '40%' THEN 'Amazon .fr'
            WHEN order_number LIKE 'S%' THEN 'Appels d\'offres'
            ELSE 'Autre'
        END
        WHERE gestionnaire IS NULL OR gestionnaire = 'Non spécifié'
    """)
    
    conn.commit()
    affected = cursor.rowcount
    cursor.close()
    conn.close()
    
    print(f"✅ {affected} factures mises à jour avec plateforme")
    return affected

def show_statistics():
    """Affiche les statistiques après mise à jour."""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM invoices")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM invoices WHERE customer_name IS NOT NULL AND customer_name != ''")
    with_customer = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM invoices WHERE reference_externe IS NOT NULL AND reference_externe != ''")
    with_ref = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM invoices WHERE fournisseur IS NOT NULL AND fournisseur != 'Non spécifié'")
    with_supplier = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM invoices WHERE gestionnaire IS NOT NULL AND gestionnaire != 'Non spécifié'")
    with_platform = cursor.fetchone()[0]
    
    cursor.close()
    conn.close()
    
    print("\n" + "="*50)
    print("📊 STATISTIQUES APRÈS MISE À JOUR")
    print("="*50)
    print(f"   📄 Total factures: {total}")
    print(f"   👥 Avec nom client: {with_customer}")
    print(f"   🏷️ Avec référence externe: {with_ref}")
    print(f"   🏭 Avec fournisseur: {with_supplier}")
    print(f"   📱 Avec plateforme: {with_platform}")
    print("="*50)

def sync_all():
    """Synchronisation complète."""
    
    print("\n" + "="*60)
    print("🔄 MISE À JOUR DES FACTURES")
    print("="*60)
    
    # 1. Récupérer les factures depuis l'API
    print("\n📦 Récupération des factures depuis Erplain...")
    invoices = fetch_all_invoices_with_details()
    
    if invoices:
        # 2. Mettre à jour clients et références
        print("\n👥 Mise à jour des clients...")
        update_invoices_database(invoices)
    else:
        print("⚠️ Aucune facture récupérée")
    
    # 3. Mettre à jour les fournisseurs
    print("\n🏭 Mise à jour des fournisseurs...")
    update_suppliers_from_products()
    
    # 4. Mettre à jour les plateformes
    print("\n📱 Mise à jour des plateformes...")
    update_platforms()
    
    # 5. Afficher les statistiques
    show_statistics()
    
    print("\n" + "="*60)
    print("✅ Synchronisation terminée")
    print("="*60)

if __name__ == "__main__":
    sync_all()