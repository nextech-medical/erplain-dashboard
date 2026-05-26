# fetch_and_update_all_suppliers_fixed.py
"""
Script pour récupérer automatiquement tous les fournisseurs depuis Erplain
Version corrigée
"""
import requests
import psycopg2
import pandas as pd
import json
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

# Configuration API
API_URL = "https://app.erplain.net/public-api/graphql/endpoint"
BEARER_TOKEN = "437b4d61de0d0be070992852610f685f"

def fetch_suppliers_from_products():
    """
    Récupère les fournisseurs depuis les produits (méthode fiable)
    """
    print("\n📦 Récupération des fournisseurs via les produits...")
    
    all_products = []
    page = 1
    page_size = 100
    
    # Dictionnaire pour stocker les fournisseurs uniques
    suppliers_dict = {}
    
    while True:
        print(f"   Page {page}...")
        
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
                  email
                  phone
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
            data = response.json()
            
            if "errors" in data:
                print(f"   ⚠️ Erreur: {data['errors'][0]['message'][:100] if data['errors'] else 'Unknown'}")
                # Afficher la structure pour debug
                print(f"   Structure de la réponse: {json.dumps(data, indent=2)[:500]}")
                break
            
            products_data = data.get("data", {}).get("Products", {})
            edges = products_data.get("edges", [])
            
            if not edges:
                print("   ✅ Plus de produits")
                break
            
            for edge in edges:
                # edge peut être un dict ou une string
                if isinstance(edge, dict):
                    node = edge.get("node")
                else:
                    continue
                    
                if node and isinstance(node, dict):
                    supplier = node.get("supplier")
                    if supplier and isinstance(supplier, dict):
                        supplier_id = supplier.get('id')
                        if supplier_id and supplier_id not in suppliers_dict:
                            suppliers_dict[supplier_id] = {
                                'id': str(supplier_id),
                                'label': supplier.get('label'),
                                'email': supplier.get('email'),
                                'phone': supplier.get('phone'),
                            }
                    
                    # Stocker les produits aussi
                    all_products.append({
                        'id': str(node.get('id')),
                        'name': node.get('label'),
                        'sku': node.get('sku'),
                        'supplier_id': str(supplier.get('id')) if supplier and supplier.get('id') else None,
                        'supplier_name': supplier.get('label') if supplier else None,
                    })
            
            print(f"   ✅ {len(edges)} produits traités (total fournisseurs: {len(suppliers_dict)})")
            
            if len(edges) < page_size:
                break
            page += 1
            
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
            import traceback
            traceback.print_exc()
            break
    
    return list(suppliers_dict.values()), all_products

def create_tables():
    """Crée les tables nécessaires"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Table suppliers
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255),
            phone VARCHAR(50),
            is_active BOOLEAN DEFAULT TRUE,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Table products
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            sku VARCHAR(100),
            supplier_id VARCHAR(50),
            supplier_name VARCHAR(255),
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Ajouter la colonne brand_name si elle n'existe pas dans products
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'products' AND column_name = 'brand_name'
    """)
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE products ADD COLUMN brand_name VARCHAR(255)")
    
    # Ajouter les colonnes manquantes dans invoices
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'invoices' AND column_name = 'fournisseur'
    """)
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE invoices ADD COLUMN fournisseur TEXT")
    
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'invoices' AND column_name = 'gestionnaire'
    """)
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE invoices ADD COLUMN gestionnaire TEXT")
    
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'invoices' AND column_name = 'reference_externe'
    """)
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE invoices ADD COLUMN reference_externe TEXT")
    
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'invoices' AND column_name = 'bl_number'
    """)
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE invoices ADD COLUMN bl_number TEXT")
    
    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Tables créées/vérifiées")

def save_suppliers_to_db(suppliers):
    """Sauvegarde les fournisseurs"""
    if not suppliers:
        print("⚠️ Aucun fournisseur à sauvegarder")
        return 0
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    count = 0
    for supplier in suppliers:
        try:
            cursor.execute("""
                INSERT INTO suppliers (id, name, email, phone, is_active, synced_at)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    email = EXCLUDED.email,
                    phone = EXCLUDED.phone,
                    synced_at = CURRENT_TIMESTAMP
            """, (
                supplier.get('id'),
                supplier.get('label') or supplier.get('name'),
                supplier.get('email'),
                supplier.get('phone'),
                True
            ))
            count += 1
        except Exception as e:
            print(f"❌ Erreur fournisseur {supplier.get('label')}: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ {count} fournisseurs sauvegardés")
    return count

def save_products_to_db(products):
    """Sauvegarde les produits"""
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
            cursor.execute("""
                INSERT INTO products (id, name, sku, supplier_id, supplier_name, synced_at)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    sku = EXCLUDED.sku,
                    supplier_id = EXCLUDED.supplier_id,
                    supplier_name = EXCLUDED.supplier_name,
                    synced_at = CURRENT_TIMESTAMP
            """, (
                product.get('id'),
                product.get('name'),
                product.get('sku'),
                product.get('supplier_id'),
                product.get('supplier_name')
            ))
            count += 1
        except Exception as e:
            print(f"❌ Erreur produit {product.get('name')}: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ {count} produits sauvegardés")
    return count

def update_invoices_with_suppliers():
    """
    Met à jour les factures avec les fournisseurs depuis la table products
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
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
    
    updated = cursor.rowcount
    print(f"   ✅ {updated} factures mises à jour via SKU")
    
    # Mettre à jour via le nom du produit (fallback)
    cursor.execute("""
        UPDATE invoices i
        SET fournisseur = 
            CASE 
                WHEN il.product_label ILIKE '%ZARYS%' THEN 'ZARYS'
                WHEN il.product_label ILIKE '%Abena%' THEN 'Abena'
                WHEN il.product_label ILIKE '%Ontex%' THEN 'Ontex'
                WHEN il.product_label ILIKE '%HARTMANN%' THEN 'Hartmann'
                WHEN il.product_label ILIKE '%Chirana%' THEN 'Chirana'
                WHEN il.product_label ILIKE '%BASTOS%' THEN 'Bastos'
                WHEN il.product_label ILIKE '%Comed%' THEN 'Comed'
                WHEN il.product_label ILIKE '%Tena%' THEN 'Tena'
                WHEN il.product_label ILIKE '%SIDAPHARM%' THEN 'Sidapharm'
                WHEN il.product_label ILIKE '%PHARMAPLAST%' THEN 'Pharmaplast'
                WHEN il.product_label ILIKE '%VITREX%' THEN 'Vitrex'
            END
        FROM invoice_lines il
        WHERE i.id = il.invoice_id
        AND (i.fournisseur IS NULL OR i.fournisseur = 'Non spécifié')
        AND (
            il.product_label ILIKE '%ZARYS%' OR
            il.product_label ILIKE '%Abena%' OR
            il.product_label ILIKE '%Ontex%' OR
            il.product_label ILIKE '%HARTMANN%' OR
            il.product_label ILIKE '%Chirana%' OR
            il.product_label ILIKE '%BASTOS%' OR
            il.product_label ILIKE '%Comed%' OR
            il.product_label ILIKE '%Tena%' OR
            il.product_label ILIKE '%SIDAPHARM%' OR
            il.product_label ILIKE '%PHARMAPLAST%' OR
            il.product_label ILIKE '%VITREX%'
        )
    """)
    
    updated2 = cursor.rowcount
    print(f"   ✅ {updated2} factures mises à jour via nom produit")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return updated + updated2

def detect_platforms():
    """
    Détecte les plateformes (Amazon, Temu, Shopify, Direct)
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Amazon: références qui commencent par 40 ou contiennent des tirets
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Amazon'
        WHERE (gestionnaire IS NULL OR gestionnaire = 'Non spécifié')
        AND (reference_externe LIKE '40%' OR reference_externe LIKE '%-%-%')
    """)
    print(f"   Amazon: {cursor.rowcount} factures")
    
    # Temu: références qui commencent par PO- ou E
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Temu'
        WHERE (gestionnaire IS NULL OR gestionnaire = 'Non spécifié')
        AND (reference_externe LIKE 'PO-%' OR reference_externe LIKE 'E%')
    """)
    print(f"   Temu: {cursor.rowcount} factures")
    
    # Shopify
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Shopify'
        WHERE (gestionnaire IS NULL OR gestionnaire = 'Non spécifié')
        AND (reference_externe LIKE 'SHOP%' OR order_number LIKE 'SHOP%')
    """)
    print(f"   Shopify: {cursor.rowcount} factures")
    
    # Direct par défaut
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Direct'
        WHERE gestionnaire IS NULL OR gestionnaire = 'Non spécifié'
    """)
    print(f"   Direct: {cursor.rowcount} factures")
    
    conn.commit()
    cursor.close()
    conn.close()

def show_supplier_stats():
    """Affiche les statistiques"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    # Fournisseurs dans la base
    df_suppliers = pd.read_sql_query("""
        SELECT name, email, phone, synced_at
        FROM suppliers
        ORDER BY name
    """, conn)
    
    # Produits par fournisseur
    df_products = pd.read_sql_query("""
        SELECT supplier_name, COUNT(*) as nb_products
        FROM products
        WHERE supplier_name IS NOT NULL
        GROUP BY supplier_name
        ORDER BY nb_products DESC
    """, conn)
    
    # Fournisseurs dans les factures
    df_invoices = pd.read_sql_query("""
        SELECT 
            fournisseur,
            COUNT(*) as nb_factures,
            ROUND(SUM(total)::numeric, 2) as ca_total
        FROM invoices
        WHERE fournisseur IS NOT NULL AND fournisseur != 'Non spécifié'
        GROUP BY fournisseur
        ORDER BY ca_total DESC
        LIMIT 20
    """, conn)
    
    # Plateformes
    df_platforms = pd.read_sql_query("""
        SELECT 
            gestionnaire,
            COUNT(*) as nb_factures,
            ROUND(SUM(total)::numeric, 2) as ca_total
        FROM invoices
        WHERE gestionnaire IS NOT NULL AND gestionnaire != 'Non spécifié'
        GROUP BY gestionnaire
        ORDER BY ca_total DESC
    """, conn)
    
    conn.close()
    
    print("\n" + "="*60)
    print("📊 FOURNISSEURS DANS LA BASE")
    print("="*60)
    if not df_suppliers.empty:
        print(df_suppliers.to_string(index=False))
    else:
        print("   Aucun fournisseur trouvé")
    
    print("\n" + "="*60)
    print("📊 PRODUITS PAR FOURNISSEUR")
    print("="*60)
    if not df_products.empty:
        print(df_products.to_string(index=False))
    
    print("\n" + "="*60)
    print("📊 FOURNISSEURS DANS LES FACTURES")
    print("="*60)
    if not df_invoices.empty:
        print(df_invoices.to_string(index=False))
    
    print("\n" + "="*60)
    print("📱 PLATEFORMES")
    print("="*60)
    if not df_platforms.empty:
        print(df_platforms.to_string(index=False))

def sync_all_suppliers():
    """
    Synchronisation complète
    """
    print("\n" + "="*60)
    print("🔄 SYNCHRONISATION COMPLÈTE DES FOURNISSEURS")
    print("="*60)
    
    # 1. Créer les tables
    create_tables()
    
    # 2. Récupérer les fournisseurs et produits
    print("\n📦 Récupération des fournisseurs et produits depuis Erplain...")
    suppliers, products = fetch_suppliers_from_products()
    
    # 3. Sauvegarder
    supplier_count = save_suppliers_to_db(suppliers)
    product_count = save_products_to_db(products)
    
    # 4. Mettre à jour les factures
    print("\n🏭 Mise à jour des factures avec les fournisseurs...")
    updated_count = update_invoices_with_suppliers()
    
    # 5. Détecter les plateformes
    print("\n📱 Détection des plateformes...")
    detect_platforms()
    
    # 6. Afficher les statistiques
    show_supplier_stats()
    
    print("\n" + "="*60)
    print(f"✅ Synchronisation terminée: {supplier_count} fournisseurs, {product_count} produits")
    print(f"✅ {updated_count} factures mises à jour")
    print("="*60)
    
    return supplier_count, product_count, updated_count

if __name__ == "__main__":
    sync_all_suppliers()