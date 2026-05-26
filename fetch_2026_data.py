# fetch_2026_data_fixed.py
import requests
import json
import psycopg2
import pandas as pd
from datetime import datetime
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, API_URL, BEARER_TOKEN

def fetch_invoices_2026():
    """Récupère les factures de 2026 uniquement."""
    
    all_invoices = []
    page = 1
    page_size = 100
    
    # Date de début 2026
    start_date = "2026-01-01T00:00:00+02:00"
    
    while True:
        print(f"📥 Récupération factures 2026 - Page {page}...")
        
        query = f"""
        query {{
          Invoices(page: {page}, page_size: {page_size}, filters: {{ created_from: "{start_date}" }}) {{
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
                notes
                internal_notes
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
                print("✅ Plus de factures 2026")
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

def fetch_products():
    """Récupère tous les produits."""
    
    all_products = []
    page = 1
    page_size = 100
    
    while True:
        print(f"📥 Récupération produits - Page {page}...")
        
        query = f"""
        query {{
          Products(page: {page}, page_size: {page_size}) {{
            edges {{
              node {{
                id
                label
                sku
                supplier {{
                  id
                  label
                }}
                created
                updated
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
            data = response.json()
            
            if "errors" in data:
                print(f"❌ Erreurs: {data['errors']}")
                break
            
            products_data = data.get("data", {}).get("Products", {})
            edges = products_data.get("edges", {})
            nodes = edges.get("node", [])
            
            if not nodes:
                break
            
            all_products.extend(nodes)
            print(f"   ✅ {len(nodes)} produits (total: {len(all_products)})")
            
            if len(nodes) < page_size:
                break
            page += 1
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            break
    
    return all_products

def clear_old_data():
    """Supprime les anciennes données (avant 2026) en respectant les contraintes."""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # 1. D'abord, supprimer les lignes de facture des factures anciennes
    print("🗑️ Suppression des anciennes lignes de facture...")
    cursor.execute("""
        DELETE FROM invoice_lines 
        WHERE invoice_id IN (
            SELECT id FROM invoices 
            WHERE EXTRACT(YEAR FROM invoice_created) < 2026
        )
    """)
    deleted_lines = cursor.rowcount
    print(f"   {deleted_lines} lignes supprimées")
    
    # 2. Ensuite, supprimer les factures anciennes
    print("🗑️ Suppression des anciennes factures...")
    cursor.execute("""
        DELETE FROM invoices 
        WHERE EXTRACT(YEAR FROM invoice_created) < 2026
    """)
    deleted_invoices = cursor.rowcount
    print(f"   {deleted_invoices} factures supprimées")
    
    # 3. Supprimer les produits orphelins (optionnel)
    cursor.execute("""
        DELETE FROM products 
        WHERE id NOT IN (
            SELECT DISTINCT product_id FROM invoice_lines WHERE product_id IS NOT NULL
        )
    """)
    deleted_products = cursor.rowcount
    print(f"   {deleted_products} produits orphelins supprimés")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return deleted_invoices, deleted_lines

def save_invoices_to_db(invoices):
    """Sauvegarde les factures 2026."""
    
    if not invoices:
        print("⚠️ Aucune facture à sauvegarder")
        return 0
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    invoice_count = 0
    line_count = 0
    
    for invoice in invoices:
        try:
            customer = invoice.get('customer', {})
            if customer is None:
                customer = {}
            
            # Sauvegarder la facture
            cursor.execute("""
                INSERT INTO invoices (
                    id, label, order_number, status, invoice_created, due_date,
                    subtotal, total, external_reference, notes_text,
                    customer_name, customer_email, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (id) DO UPDATE SET
                    label = EXCLUDED.label,
                    status = EXCLUDED.status,
                    total = EXCLUDED.total,
                    customer_name = EXCLUDED.customer_name,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                str(invoice.get('id')),
                invoice.get('label'),
                invoice.get('order_number'),
                invoice.get('status'),
                invoice.get('created'),
                invoice.get('due_date'),
                invoice.get('subtotal'),
                invoice.get('total'),
                invoice.get('external_reference'),
                invoice.get('notes'),
                customer.get('label'),
                customer.get('emails', [None])[0] if customer.get('emails') else None
            ))
            invoice_count += 1
            
            # Sauvegarder les lignes de facture
            line_items = invoice.get('line_items', {})
            edges = line_items.get('edges', {})
            items = edges.get('node', [])
            
            for item in items:
                product = item.get('product', {})
                sku = product.get('sku')
                
                cursor.execute("""
                    INSERT INTO invoice_lines (
                        invoice_id, product_label, product_sku, quantity,
                        unit_price, line_total
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    str(invoice.get('id')),
                    product.get('label'),
                    sku,
                    item.get('quantity'),
                    item.get('price'),
                    item.get('total')
                ))
                line_count += 1
            
            if invoice_count % 20 == 0:
                print(f"   {invoice_count} factures, {line_count} lignes...")
                conn.commit()
                
        except Exception as e:
            print(f"❌ Erreur facture {invoice.get('id')}: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ {invoice_count} factures 2026 sauvegardées")
    print(f"✅ {line_count} lignes de facture sauvegardées")
    return invoice_count

def save_products_to_db(products):
    """Sauvegarde les produits."""
    
    if not products:
        print("⚠️ Aucun produit à sauvegarder")
        return 0
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    count = 0
    for product in products:
        try:
            supplier = product.get('supplier', {})
            
            cursor.execute("""
                INSERT INTO products (id, name, sku, supplier_name, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    sku = EXCLUDED.sku,
                    supplier_name = EXCLUDED.supplier_name,
                    updated_at = EXCLUDED.updated_at
            """, (
                str(product.get('id')),
                product.get('label'),
                product.get('sku'),
                supplier.get('label'),
                product.get('created'),
                product.get('updated')
            ))
            count += 1
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ {count} produits sauvegardés")
    return count

def show_statistics():
    """Affiche les statistiques après synchronisation."""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    query = """
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN EXTRACT(YEAR FROM invoice_created) = 2026 THEN 1 END) as y2026,
            COUNT(CASE WHEN EXTRACT(YEAR FROM invoice_created) < 2026 THEN 1 END) as anciennes
        FROM invoices
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print("\n" + "="*50)
    print("📊 STATISTIQUES APRÈS SYNCHRONISATION")
    print("="*50)
    print(f"   📄 Factures 2026: {df['y2026'].iloc[0]}")
    print(f"   🗑️ Anciennes factures: {df['anciennes'].iloc[0]}")
    print(f"   📦 Total produits: {df['total'].iloc[0]}")
    print("="*50)

def sync_2026_data():
    """Synchronisation des données 2026."""
    
    print("\n" + "="*60)
    print("🔄 SYNCHRONISATION DONNÉES 2026")
    print("="*60)
    
    # 1. Nettoyer les anciennes données
    print("\n🗑️ Nettoyage des anciennes données...")
    deleted_invoices, deleted_lines = clear_old_data()
    
    # 2. Récupérer les factures 2026
    print("\n📦 Récupération des factures 2026...")
    invoices = fetch_invoices_2026()
    
    if invoices:
        save_invoices_to_db(invoices)
    else:
        print("⚠️ Aucune facture 2026 trouvée")
    
    # 3. Récupérer les produits
    print("\n📦 Récupération des produits...")
    products = fetch_products()
    
    if products:
        save_products_to_db(products)
    
    # 4. Mettre à jour les fournisseurs
    print("\n🏭 Mise à jour des fournisseurs...")
    update_suppliers_from_products()
    
    # 5. Extraire les références des notes
    print("\n📝 Extraction des références externes...")
    extract_references_from_notes()
    
    # 6. Afficher les statistiques
    show_statistics()
    
    print("\n" + "="*60)
    print("✅ Synchronisation terminée")
    print("="*60)

def update_suppliers_from_products():
    """Met à jour les fournisseurs des factures."""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
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
    
    print(f"   ✅ {affected} factures mises à jour avec fournisseur")

def extract_references_from_notes():
    """Extrait les références externes des notes."""
    
    import re
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, notes_text 
        FROM invoices 
        WHERE notes_text IS NOT NULL 
        AND (reference_externe IS NULL OR reference_externe = '')
    """)
    
    invoices = cursor.fetchall()
    
    count = 0
    for inv_id, notes in invoices:
        if notes:
            # Nettoyer le HTML
            clean_notes = re.sub(r'<[^>]+>', ' ', notes)
            
            # Chercher des patterns de références
            patterns = [
                r'E(\d{6})',
                r'PO[-\s]*([A-Z0-9]+)',
                r'N°\s*d\'engagement\s*:\s*([A-Z0-9]+)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, clean_notes, re.IGNORECASE)
                if match:
                    reference = match.group(1)
                    cursor.execute("""
                        UPDATE invoices 
                        SET reference_externe = %s
                        WHERE id = %s
                    """, (reference, inv_id))
                    count += 1
                    break
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"   ✅ {count} références externes extraites")

if __name__ == "__main__":
    sync_2026_data()