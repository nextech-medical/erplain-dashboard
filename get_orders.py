# get_orders_with_suppliers_fixed.py
"""
Script corrigé pour récupérer les commandes avec les fournisseurs (suppliers)
"""

import requests
import json
import psycopg2
from datetime import datetime
from config import API_URL, BEARER_TOKEN, DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

# Requête avec la structure CORRECTE pour Erplain (sans address)
QUERY_TEMPLATE = """
query {{
  SalesOrders(page: {page}, page_size: {page_size}, sort: {{ by: "created", direction: "DESC" }}) {{
    edges {{
      node {{
        id
        label
        order_id
        external_reference
        created
        account_manager {{
          id
          label
        }}
        status
        customer {{
          id
          label
          emails
        }}
        line_items {{
          edges {{
            node {{
              id
              quantity
              price
              product {{
                id
                label
                ... on variantType {{
                  sku
                  supplier_id
                  supplier_sku
                }}
                ... on serviceType {{
                  sku
                }}
              }}
            }}
          }}
        }}
      }}
    }}
  }}
}}
"""

# Requête pour récupérer les fournisseurs (sans address)
SUPPLIERS_QUERY = """
{
    Suppliers(page: 1, page_size: 1000) {
        edges {
            node {
                id
                label
                email
                phone
            }
        }
    }
}
"""


def fetch_all_suppliers():
    """Récupère tous les fournisseurs depuis l'API Erplain"""
    print("\n📦 Récupération des fournisseurs depuis Erplain...")
    
    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(API_URL, json={"query": SUPPLIERS_QUERY}, headers=headers, timeout=60)
        
        if response.status_code != 200:
            print(f"   ❌ Erreur HTTP {response.status_code}")
            return {}
        
        data = response.json()
        
        if "errors" in data:
            print(f"   ❌ Erreur GraphQL: {data['errors'][0].get('message', 'Unknown')[:150]}")
            return {}
        
        suppliers_data = data.get("data", {}).get("Suppliers", {})
        edges_data = suppliers_data.get("edges", {})
        nodes = edges_data.get("node", [])
        
        suppliers = {}
        for supplier in nodes:
            supplier_id = str(supplier.get("id"))
            suppliers[supplier_id] = {
                "id": supplier_id,
                "label": supplier.get("label"),
                "email": supplier.get("email"),
                "phone": supplier.get("phone")
            }
        
        print(f"   ✅ {len(suppliers)} fournisseurs récupérés")
        return suppliers
        
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return {}


def fetch_all_orders(page_size=100):
    """
    Récupère TOUTES les commandes avec pagination.
    """
    all_orders = []
    page = 1
    
    print("\n📥 Récupération des commandes depuis Erplain...")
    
    while True:
        print(f"   Page {page}...")
        
        query = QUERY_TEMPLATE.format(page=page, page_size=page_size)
        headers = {
            "Authorization": f"Bearer {BEARER_TOKEN}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(API_URL, json={"query": query}, headers=headers, timeout=60)
            
            if response.status_code != 200:
                print(f"   ❌ Erreur HTTP {response.status_code}")
                break
            
            data = response.json()
            
            if "errors" in data:
                print(f"   ❌ Erreur GraphQL: {data['errors'][0].get('message', 'Unknown')[:150]}")
                break
            
            sales_orders = data.get("data", {}).get("SalesOrders", {})
            edges_data = sales_orders.get("edges", {})
            
            # Structure spéciale Erplain: edges est un dict avec "node" qui est une liste
            nodes = edges_data.get("node", [])
            
            if not nodes:
                print("   ✅ Plus de commandes")
                break
            
            all_orders.extend(nodes)
            print(f"   ✅ {len(nodes)} commandes (total: {len(all_orders)})")
            
            if len(nodes) < page_size:
                break
                
            page += 1
            
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
            break
    
    print(f"\n📊 Total commandes récupérées: {len(all_orders)}")
    return all_orders


def extract_supplier_info(product, suppliers_map):
    """
    Extrait les informations du fournisseur depuis un produit
    """
    if product is None or not isinstance(product, dict):
        return {
            "supplier_id": None,
            "supplier_name": None,
            "supplier_email": None,
            "supplier_phone": None
        }
    
    supplier_id = product.get("supplier_id") or product.get("supplier_sku")
    
    if supplier_id and str(supplier_id) in suppliers_map:
        supplier = suppliers_map[str(supplier_id)]
        return {
            "supplier_id": str(supplier_id),
            "supplier_name": supplier.get("label"),
            "supplier_email": supplier.get("email"),
            "supplier_phone": supplier.get("phone")
        }
    
    return {
        "supplier_id": None,
        "supplier_name": None,
        "supplier_email": None,
        "supplier_phone": None
    }


def extract_product_sku(product):
    """Extrait le SKU du produit"""
    if product is None or not isinstance(product, dict):
        return None
    return product.get("sku")


def extract_order_data(order):
    """
    Extrait les données d'une commande.
    """
    # Extraire le gestionnaire de compte
    account_manager = order.get("account_manager", {})
    if isinstance(account_manager, dict):
        account_manager_name = account_manager.get("label")
        account_manager_id = account_manager.get("id")
    else:
        account_manager_name = None
        account_manager_id = None
    
    # Extraire les infos client
    customer = order.get("customer", {})
    if isinstance(customer, dict):
        customer_label = customer.get("label")
        emails = customer.get("emails", [])
        customer_email = emails[0] if emails else None
    else:
        customer_label = None
        customer_email = None
    
    # Convertir l'ID en string si nécessaire
    order_id = order.get("order_id")
    if order_id is None:
        order_id = order.get("label")
    
    return {
        "id": str(order.get("id")),
        "label": order.get("label"),
        "order_id": str(order_id) if order_id else None,
        "external_reference": order.get("external_reference"),
        "created": order.get("created"),
        "account_manager_id": str(account_manager_id) if account_manager_id else None,
        "account_manager_name": account_manager_name,
        "status": order.get("status"),
        "customer_name": customer_label,
        "customer_email": customer_email
    }


def extract_order_lines(order, order_id, suppliers_map):
    """
    Extrait les lignes d'une commande avec les fournisseurs.
    """
    lines = []
    
    # Récupérer les lignes - structure line_items.edges.node
    line_items = order.get("line_items", {})
    
    if isinstance(line_items, dict):
        edges = line_items.get("edges", {})
        nodes = edges.get("node", [])
    else:
        nodes = []
    
    for node in nodes:
        if not isinstance(node, dict):
            continue
        
        product = node.get("product")
        
        # Récupérer le SKU
        product_sku = extract_product_sku(product)
        
        # Récupérer les infos fournisseur
        supplier_info = extract_supplier_info(product, suppliers_map)
        
        quantity = node.get("quantity", 0)
        unit_price = float(node.get("price", 0) or 0)
        
        product_label = product.get("label") if product and isinstance(product, dict) else None
        
        if product_label or product_sku or quantity > 0:
            lines.append({
                "order_id": order_id,
                "line_id": str(node.get("id")) if node.get("id") else None,
                "product_id": str(product.get("id")) if product and product.get("id") else None,
                "product_label": product_label,
                "product_sku": product_sku,
                "quantity": int(quantity) if quantity else 0,
                "unit_price": unit_price,
                "supplier_id": supplier_info["supplier_id"],
                "supplier_name": supplier_info["supplier_name"],
                "supplier_email": supplier_info["supplier_email"],
                "supplier_phone": supplier_info["supplier_phone"]
            })
    
    return lines


def extract_orders_with_suppliers(orders, suppliers_map):
    """
    Extrait les commandes avec les fournisseurs au niveau de la commande (premier fournisseur trouvé)
    """
    orders_with_suppliers = []
    
    for order in orders:
        # Extraire les données de base
        order_dict = extract_order_data(order)
        
        # Chercher les fournisseurs dans les lignes
        line_items = order.get("line_items", {})
        if isinstance(line_items, dict):
            edges = line_items.get("edges", {})
            nodes = edges.get("node", [])
        else:
            nodes = []
        
        # Prendre le premier fournisseur trouvé
        first_supplier = None
        for node in nodes:
            if not isinstance(node, dict):
                continue
            product = node.get("product")
            supplier_info = extract_supplier_info(product, suppliers_map)
            if supplier_info["supplier_name"]:
                first_supplier = supplier_info
                break
        
        # Ajouter les infos fournisseur à la commande
        if first_supplier:
            order_dict["supplier_id"] = first_supplier["supplier_id"]
            order_dict["supplier_name"] = first_supplier["supplier_name"]
            order_dict["supplier_email"] = first_supplier["supplier_email"]
            order_dict["supplier_phone"] = first_supplier["supplier_phone"]
        else:
            order_dict["supplier_id"] = None
            order_dict["supplier_name"] = None
            order_dict["supplier_email"] = None
            order_dict["supplier_phone"] = None
        
        orders_with_suppliers.append(order_dict)
    
    return orders_with_suppliers


def create_orders_table():
    """
    Crée la table des commandes avec les colonnes fournisseurs.
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Supprimer les anciennes tables
    cursor.execute("DROP TABLE IF EXISTS order_lines CASCADE")
    cursor.execute("DROP TABLE IF EXISTS orders CASCADE")
    
    # Table orders avec colonnes fournisseurs
    cursor.execute("""
        CREATE TABLE orders (
            id VARCHAR(100) PRIMARY KEY,
            label VARCHAR(200),
            order_id VARCHAR(100),
            external_reference TEXT,
            created TIMESTAMP,
            account_manager_id VARCHAR(100),
            account_manager_name VARCHAR(100),
            status VARCHAR(50),
            customer_name TEXT,
            customer_email TEXT,
            supplier_id VARCHAR(100),
            supplier_name VARCHAR(255),
            supplier_email VARCHAR(255),
            supplier_phone VARCHAR(50),
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Table order_lines
    cursor.execute("""
        CREATE TABLE order_lines (
            id SERIAL PRIMARY KEY,
            order_id VARCHAR(100) REFERENCES orders(id) ON DELETE CASCADE,
            line_id VARCHAR(100),
            product_id VARCHAR(100),
            product_label TEXT,
            product_sku VARCHAR(100),
            quantity INTEGER,
            unit_price DECIMAL(12,2),
            supplier_id VARCHAR(100),
            supplier_name VARCHAR(255),
            supplier_email VARCHAR(255),
            supplier_phone VARCHAR(50),
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Index
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_external_ref ON orders(external_reference)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_account_manager ON orders(account_manager_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_lines_order ON order_lines(order_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_lines_sku ON order_lines(product_sku)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_lines_supplier ON order_lines(supplier_id)")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print("✅ Tables orders et order_lines créées")


def insert_orders_to_db(orders_data, lines_data):
    """
    Insère les commandes dans PostgreSQL.
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Insérer les commandes
    orders_inserted = 0
    for order in orders_data:
        try:
            cursor.execute("""
                INSERT INTO orders (
                    id, label, order_id, external_reference, created,
                    account_manager_id, account_manager_name, status,
                    customer_name, customer_email,
                    supplier_id, supplier_name, supplier_email, supplier_phone
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    external_reference = COALESCE(orders.external_reference, EXCLUDED.external_reference),
                    account_manager_name = COALESCE(orders.account_manager_name, EXCLUDED.account_manager_name),
                    supplier_name = COALESCE(orders.supplier_name, EXCLUDED.supplier_name),
                    synced_at = CURRENT_TIMESTAMP
            """, (
                order['id'], order['label'], order['order_id'],
                order['external_reference'], order['created'],
                order['account_manager_id'], order['account_manager_name'],
                order['status'], order['customer_name'], order['customer_email'],
                order['supplier_id'], order['supplier_name'],
                order['supplier_email'], order['supplier_phone']
            ))
            orders_inserted += 1
        except Exception as e:
            print(f"   ⚠️ Erreur commande {order['id']}: {e}")
    
    conn.commit()
    
    # Insérer les lignes
    lines_inserted = 0
    for line in lines_data:
        try:
            cursor.execute("""
                INSERT INTO order_lines (
                    order_id, line_id, product_id, product_label, product_sku,
                    quantity, unit_price, supplier_id, supplier_name, 
                    supplier_email, supplier_phone
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                line['order_id'], line['line_id'], line['product_id'],
                line['product_label'], line['product_sku'],
                line['quantity'], line['unit_price'],
                line['supplier_id'], line['supplier_name'],
                line['supplier_email'], line['supplier_phone']
            ))
            lines_inserted += 1
        except Exception as e:
            print(f"   ⚠️ Erreur ligne: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return orders_inserted, lines_inserted


def show_statistics():
    """
    Affiche les statistiques.
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 70)
    print("📊 STATISTIQUES DES COMMANDES")
    print("=" * 70)
    
    cursor.execute("SELECT COUNT(*) FROM orders")
    total_orders = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM order_lines")
    total_lines = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(CASE WHEN external_reference IS NOT NULL AND external_reference != '' THEN 1 END)
        FROM orders
    """)
    with_ref = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(CASE WHEN account_manager_name IS NOT NULL AND account_manager_name != '' THEN 1 END)
        FROM orders
    """)
    with_manager = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(CASE WHEN supplier_name IS NOT NULL AND supplier_name != '' THEN 1 END)
        FROM orders
    """)
    with_supplier = cursor.fetchone()[0]
    
    print(f"\n📄 COMMANDES")
    print(f"   - Total commandes: {total_orders}")
    print(f"   - Total lignes: {total_lines}")
    print(f"   - Avec référence externe: {with_ref}")
    print(f"   - Avec gestionnaire de compte: {with_manager}")
    print(f"   - Avec fournisseur: {with_supplier}")
    
    # Top fournisseurs
    cursor.execute("""
        SELECT supplier_name, COUNT(*) as nb
        FROM orders
        WHERE supplier_name IS NOT NULL AND supplier_name != ''
        GROUP BY supplier_name
        ORDER BY nb DESC
        LIMIT 10
    """)
    top_suppliers = cursor.fetchall()
    if top_suppliers:
        print(f"\n🏭 TOP FOURNISSEURS:")
        for s in top_suppliers:
            print(f"   - {s[0]}: {s[1]} commandes")
    
    cursor.close()
    conn.close()


def save_orders_to_json(orders_data, filename="commandes_avec_fournisseurs.json"):
    """Sauvegarde les commandes en JSON"""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(orders_data, f, indent=2, ensure_ascii=False, default=str)
    print(f"   ✅ {filename} ({len(orders_data)} commandes)")


def main():
    """
    Fonction principale.
    """
    print("\n" + "=" * 70)
    print("🚀 RÉCUPÉRATION DES COMMANDES AVEC FOURNISSEURS")
    print("=" * 70)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # 1. Récupérer les fournisseurs d'abord
    suppliers_map = fetch_all_suppliers()
    
    # 2. Récupérer les commandes
    orders = fetch_all_orders(page_size=100)
    
    if not orders:
        print("\n❌ Aucune commande récupérée")
        return
    
    # 3. Extraire les données avec les fournisseurs
    print("\n🔧 Extraction des données...")
    
    orders_data = extract_orders_with_suppliers(orders, suppliers_map)
    all_lines = []
    
    for i, order in enumerate(orders):
        if i % 1000 == 0 and i > 0:
            print(f"   Traitement: {i}/{len(orders)}")
        
        order_id = str(order.get("id"))
        lines = extract_order_lines(order, order_id, suppliers_map)
        all_lines.extend(lines)
    
    print(f"   ✅ {len(orders_data)} commandes extraites")
    print(f"   ✅ {len(all_lines)} lignes extraites")
    
    # Afficher les premières commandes pour vérification
    print("\n📋 Aperçu des 5 premières commandes:")
    for order in orders_data[:5]:
        print(f"   - ID: {order['order_id']}")
        print(f"     Réf externe: {order['external_reference']}")
        print(f"     Gestionnaire: {order['account_manager_name']}")
        print(f"     Fournisseur: {order['supplier_name']}")
        print()
    
    # 4. Sauvegarder en JSON
    print("\n💾 Sauvegarde des fichiers JSON...")
    
    save_orders_to_json(orders_data, "commandes_avec_fournisseurs.json")
    
    with open("toutes_commandes.json", "w", encoding="utf-8") as f:
        json.dump(orders, f, indent=2, ensure_ascii=False, default=str)
    print(f"   ✅ toutes_commandes.json ({len(orders)} commandes)")
    
    with open("commandes_lines.json", "w", encoding="utf-8") as f:
        json.dump(all_lines, f, indent=2, ensure_ascii=False, default=str)
    print(f"   ✅ commandes_lines.json ({len(all_lines)} lignes)")
    
    # 5. Créer les tables dans PostgreSQL
    print("\n📁 Création des tables PostgreSQL...")
    create_orders_table()
    
    # 6. Insérer les données
    print("\n💾 Insertion dans PostgreSQL...")
    orders_ins, lines_ins = insert_orders_to_db(orders_data, all_lines)
    print(f"   ✅ {orders_ins} commandes insérées")
    print(f"   ✅ {lines_ins} lignes insérées")
    
    # 7. Afficher les statistiques
    show_statistics()
    
    print("\n" + "=" * 70)
    print("✅ RÉCUPÉRATION TERMINÉE")
    print("=" * 70)


if __name__ == "__main__":
    main()