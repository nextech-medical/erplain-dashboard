# fetch_suppliers_auto.py
import requests
import json
import psycopg2
import pandas as pd
from datetime import datetime
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

# Configuration API Erplain
API_URL = "https://app.erplain.net/public-api/graphql/endpoint"
BEARER_TOKEN = "437b4d61de0d0be070992852610f685f"

def fetch_all_products_from_erplain():
    """Récupère TOUS les produits depuis l'API Erplain (basé sur le code qui fonctionne)."""
    all_products = []
    page = 1
    page_size = 100
    
    while True:
        print(f"📥 Récupération page {page}...")
        
        # Requête basée sur votre code original qui fonctionne
        query = f"""
        query {{
          Products(page: {page}, page_size: {page_size}, sort: {{ by: "label", direction: "ASC" }}) {{
            edges {{
              node {{
                id
                label
                sku
                description
                country_of_origin
                supplier_description
                created
                changed
                brand {{
                  id
                  label
                }}
                supplier {{
                  id
                  label
                  email
                  phone
                }}
                variants {{
                  edges {{
                    node {{
                      id
                      label
                      sku
                    }}
                  }}
                }}
                tags {{
                  edges {{
                    node {{
                      label
                    }}
                  }}
                }}
                user {{
                  display_name
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
            response = requests.post(API_URL, json={"query": query}, headers=headers)
            
            if response.status_code != 200:
                print(f"❌ Erreur HTTP {response.status_code}")
                break
            
            data = response.json()
            
            if "errors" in data:
                print(f"❌ Erreurs GraphQL: {data['errors']}")
                break
            
            products_data = data.get("data", {}).get("Products", {})
            edges = products_data.get("edges", [])
            
            if not edges:
                print("✅ Plus de produits à récupérer.")
                break
            
            # Extraction robuste des nœuds
            nodes = []
            if isinstance(edges, list):
                for edge in edges:
                    if isinstance(edge, dict):
                        node = edge.get("node")
                        if node and isinstance(node, dict):
                            nodes.append(node)
                    else:
                        nodes.append(edge)
            elif isinstance(edges, dict):
                node_data = edges.get("node")
                if isinstance(node_data, list):
                    nodes = node_data
                elif node_data:
                    nodes = [node_data]
            
            if not nodes:
                print("⚠️ Aucun nœud trouvé dans edges")
                break
            
            all_products.extend(nodes)
            print(f"   ✅ {len(nodes)} produits récupérés (total: {len(all_products)})")
            
            if len(nodes) < page_size:
                break
            page += 1
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Erreur réseau: {e}")
            break
        except json.JSONDecodeError as e:
            print(f"❌ Erreur de décodage JSON: {e}")
            break
        except Exception as e:
            print(f"❌ Erreur inattendue: {e}")
            break
    
    return all_products

def extract_suppliers_from_products(products):
    """Extrait la liste des fournisseurs uniques à partir des produits."""
    suppliers_dict = {}
    
    for product in products:
        supplier = product.get('supplier')
        if supplier and isinstance(supplier, dict):
            supplier_id = supplier.get('id')
            if supplier_id and supplier_id not in suppliers_dict:
                suppliers_dict[supplier_id] = {
                    'id': str(supplier_id),
                    'name': supplier.get('label', ''),
                    'email': supplier.get('email', ''),
                    'phone': supplier.get('phone', ''),
                    'address': '',
                    'city': '',
                    'country': '',
                    'vat_number': '',
                    'is_active': True,
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
    
    return suppliers_dict

def extract_products_for_db(products):
    """Extrait les produits pour la base de données."""
    products_list = []
    
    for product in products:
        supplier = product.get('supplier', {})
        
        product_dict = {
            'id': str(product.get('id', '')),
            'name': product.get('label', ''),
            'sku': product.get('sku', ''),
            'supplier_id': str(supplier.get('id')) if supplier and supplier.get('id') else None,
            'supplier_name': supplier.get('label') if supplier else None,
            'brand': product.get('brand', {}).get('label') if product.get('brand') else None,
            'description': product.get('description', ''),
            'created_at': product.get('created'),
            'updated_at': product.get('changed')
        }
        products_list.append(product_dict)
    
    return products_list

def create_tables():
    """Crée les tables des produits et fournisseurs dans PostgreSQL."""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Créer la table des fournisseurs
    cursor.execute("DROP TABLE IF EXISTS suppliers CASCADE")
    cursor.execute("""
        CREATE TABLE suppliers (
            id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255),
            phone VARCHAR(50),
            address TEXT,
            city VARCHAR(100),
            country VARCHAR(100),
            vat_number VARCHAR(50),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Créer la table des produits
    cursor.execute("DROP TABLE IF EXISTS products CASCADE")
    cursor.execute("""
        CREATE TABLE products (
            id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            sku VARCHAR(100),
            supplier_id VARCHAR(50),
            supplier_name VARCHAR(255),
            brand VARCHAR(255),
            description TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Tables 'suppliers' et 'products' créées")

def save_suppliers_to_db(suppliers_dict):
    """Sauvegarde les fournisseurs dans PostgreSQL."""
    if not suppliers_dict:
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
    for supplier_id, supplier in suppliers_dict.items():
        try:
            cursor.execute("""
                INSERT INTO suppliers (
                    id, name, email, phone, address, city, country, 
                    vat_number, is_active, created_at, updated_at, synced_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    email = EXCLUDED.email,
                    phone = EXCLUDED.phone,
                    address = EXCLUDED.address,
                    city = EXCLUDED.city,
                    country = EXCLUDED.country,
                    vat_number = EXCLUDED.vat_number,
                    is_active = EXCLUDED.is_active,
                    updated_at = EXCLUDED.updated_at,
                    synced_at = CURRENT_TIMESTAMP
            """, (
                supplier.get('id'),
                supplier.get('name'),
                supplier.get('email'),
                supplier.get('phone'),
                supplier.get('address'),
                supplier.get('city'),
                supplier.get('country'),
                supplier.get('vat_number'),
                supplier.get('is_active'),
                supplier.get('created_at'),
                supplier.get('updated_at')
            ))
            count += 1
        except Exception as e:
            print(f"❌ Erreur fournisseur {supplier.get('name')}: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    print(f"✅ {count} fournisseurs sauvegardés")
    return count

def save_products_to_db(products_list):
    """Sauvegarde les produits dans PostgreSQL."""
    if not products_list:
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
    for product in products_list:
        try:
            cursor.execute("""
                INSERT INTO products (
                    id, name, sku, supplier_id, supplier_name, brand,
                    description, created_at, updated_at, synced_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    sku = EXCLUDED.sku,
                    supplier_id = EXCLUDED.supplier_id,
                    supplier_name = EXCLUDED.supplier_name,
                    brand = EXCLUDED.brand,
                    description = EXCLUDED.description,
                    updated_at = EXCLUDED.updated_at,
                    synced_at = CURRENT_TIMESTAMP
            """, (
                product.get('id'),
                product.get('name'),
                product.get('sku'),
                product.get('supplier_id'),
                product.get('supplier_name'),
                product.get('brand'),
                product.get('description'),
                product.get('created_at'),
                product.get('updated_at')
            ))
            count += 1
            if count % 50 == 0:
                print(f"   Produits sauvegardés: {count}/{len(products_list)}...")
        except Exception as e:
            print(f"❌ Erreur produit {product.get('name')}: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    print(f"✅ {count} produits sauvegardés")
    return count

def update_invoices_with_suppliers():
    """Met à jour les factures avec les noms des fournisseurs."""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Vérifier si la colonne fournisseur existe dans invoices
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='invoices' AND column_name='fournisseur'
    """)
    
    if cursor.fetchone():
        # Mettre à jour les factures avec les fournisseurs
        cursor.execute("""
            UPDATE invoices i
            SET fournisseur = COALESCE(
                (SELECT p.supplier_name 
                 FROM invoice_lines il 
                 JOIN products p ON p.sku = il.product_sku 
                 WHERE il.invoice_id = i.id 
                 AND p.supplier_name IS NOT NULL 
                 LIMIT 1),
                'Non spécifié'
            )
            WHERE i.fournisseur IS NULL OR i.fournisseur = 'Non spécifié'
        """)
        
        conn.commit()
        affected = cursor.rowcount
        print(f"✅ {affected} factures mises à jour avec les fournisseurs")
    else:
        print("⚠️ La colonne 'fournisseur' n'existe pas dans la table invoices")
    
    cursor.close()
    conn.close()

def sync_suppliers():
    """Synchronisation complète des produits et fournisseurs."""
    print("\n" + "="*60)
    print(f"🔄 SYNCHRONISATION - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # 1. Créer les tables
    create_tables()
    
    # 2. Récupérer les produits depuis Erplain
    print("\n📦 Récupération des produits depuis Erplain...")
    products = fetch_all_products_from_erplain()
    
    if not products:
        print("❌ Aucun produit récupéré")
        print("   Vérifiez que votre token est valide")
        print("   et que vous avez des produits dans Erplain")
        return 0
    
    # 3. Extraire les fournisseurs et produits
    suppliers_dict = extract_suppliers_from_products(products)
    products_list = extract_products_for_db(products)
    
    print(f"\n📊 Résumé:")
    print(f"   - Produits: {len(products)}")
    print(f"   - Fournisseurs uniques: {len(suppliers_dict)}")
    
    # Afficher les fournisseurs trouvés
    if suppliers_dict:
        print("\n🏭 Fournisseurs trouvés:")
        for supplier in list(suppliers_dict.values())[:10]:
            print(f"   - {supplier['name']}")
        if len(suppliers_dict) > 10:
            print(f"   ... et {len(suppliers_dict) - 10} autres")
    
    # 4. Sauvegarder les fournisseurs
    supplier_count = save_suppliers_to_db(suppliers_dict)
    
    # 5. Sauvegarder les produits
    product_count = save_products_to_db(products_list)
    
    # 6. Mettre à jour les factures
    update_invoices_with_suppliers()
    
    print("="*60)
    print(f"✅ Synchronisation terminée - {supplier_count} fournisseurs, {product_count} produits")
    print("="*60 + "\n")
    
    return supplier_count

def get_suppliers_from_db():
    """Récupère les fournisseurs depuis PostgreSQL pour affichage."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        query = """
            SELECT name, email, phone, is_active, synced_at 
            FROM suppliers 
            ORDER BY name
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return pd.DataFrame()

def get_statistics():
    """Affiche les statistiques des produits et fournisseurs."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        cursor = conn.cursor()
        
        # Compter les fournisseurs
        cursor.execute("SELECT COUNT(*) FROM suppliers")
        supplier_count = cursor.fetchone()[0]
        
        # Compter les produits
        cursor.execute("SELECT COUNT(*) FROM products")
        product_count = cursor.fetchone()[0]
        
        # Compter les produits avec fournisseur
        cursor.execute("SELECT COUNT(*) FROM products WHERE supplier_id IS NOT NULL")
        products_with_supplier = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        print("\n" + "="*50)
        print("📊 STATISTIQUES DE LA BASE DE DONNÉES")
        print("="*50)
        print(f"   🏭 Nombre de fournisseurs: {supplier_count}")
        print(f"   📦 Nombre de produits: {product_count}")
        print(f"   🏷️  Produits avec fournisseur: {products_with_supplier}")
        print("="*50)
        
    except Exception as e:
        print(f"❌ Erreur statistiques: {e}")

if __name__ == "__main__":
    # Exécuter la synchronisation
    sync_suppliers()
    
    # Afficher les statistiques
    get_statistics()
    
    # Afficher les fournisseurs
    df = get_suppliers_from_db()
    if not df.empty:
        print("\n📋 Liste des fournisseurs dans la base:")
        print(df.to_string(index=False))
    else:
        print("\n📋 Aucun fournisseur trouvé dans la base")