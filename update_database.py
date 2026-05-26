# update_database.py - Version qui utilise requests au lieu de gql
import psycopg2
import pandas as pd
import requests
from datetime import datetime
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, ERPLAIN_TOKEN, ERPLAIN_ENDPOINT

def fetch_orders_from_erplain(year=2026):
    """
    Récupère les commandes depuis Erplain via API REST
    """
    date_from = f"{year}-01-01"
    date_to = f"{year}-12-31"
    
    headers = {
        "Authorization": f"Bearer {ERPLAIN_TOKEN}",
        "Content-Type": "application/json"
    }
    
    query = """
    query GetSalesOrders($first: Int!, $dateFrom: Date, $dateTo: Date) {
        salesOrders(first: $first, filters: { date: { from: $dateFrom, to: $dateTo } }) {
            edges {
                node {
                    orderNumber
                    date
                    totalExclTax
                    accountManager
                    orderLines {
                        edges {
                            node {
                                product { name }
                                quantity
                                totalExclTax
                            }
                        }
                    }
                }
            }
        }
    }
    """
    
    variables = {
        "first": 100,
        "dateFrom": date_from,
        "dateTo": date_to
    }
    
    try:
        print("📡 Envoi de la requête à Erplain...")
        response = requests.post(
            ERPLAIN_ENDPOINT,
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Vérifier les erreurs GraphQL
            if "errors" in data:
                print(f"❌ Erreur GraphQL: {data['errors']}")
                return pd.DataFrame()
            
            edges = data.get("data", {}).get("salesOrders", {}).get("edges", [])
            print(f"📦 {len(edges)} commandes trouvées")
            
            all_orders = []
            for edge in edges:
                order = edge["node"]
                order_number = order.get("orderNumber")
                if not order_number:
                    continue
                
                order_date = order.get("date", "")[:10]
                gestionnaire = order.get("accountManager", "Non spécifié")
                if not gestionnaire:
                    gestionnaire = "Non spécifié"
                
                for line_edge in order.get("orderLines", {}).get("edges", []):
                    line = line_edge["node"]
                    product_name = line.get("product", {}).get("name")
                    if not product_name:
                        continue
                    
                    quantity = line.get("quantity", 0)
                    total_ht = float(line.get("totalExclTax", 0.0))
                    
                    all_orders.append({
                        "commande_id": order_number,
                        "date": order_date,
                        "produit": product_name,
                        "produit_sku": "",
                        "quantite": quantity,
                        "prix_ht": total_ht,
                        "gestionnaire_de_compte": gestionnaire,
                        "order_number": order_number,
                        "customer_name": "",
                        "customer_email": "",
                        "fournisseur": "Non spécifié"
                    })
            
            print(f"✅ {len(all_orders)} lignes de détail récupérées")
            return pd.DataFrame(all_orders)
        else:
            print(f"❌ Erreur HTTP {response.status_code}: {response.text[:200]}")
            return pd.DataFrame()
            
    except requests.exceptions.Timeout:
        print("❌ Délai d'attente dépassé")
        return pd.DataFrame()
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()

def get_existing_invoices(conn):
    """Récupère les numéros de factures existants"""
    query = "SELECT DISTINCT label FROM invoices WHERE label IS NOT NULL"
    df = pd.read_sql_query(query, conn)
    return set(df['label'].tolist()) if not df.empty else set()

def update_invoices_table(conn, df_orders):
    """Met à jour la table invoices avec les nouvelles commandes"""
    cursor = conn.cursor()
    
    existing_invoices = get_existing_invoices(conn)
    df_new = df_orders[~df_orders['commande_id'].isin(existing_invoices)]
    
    if df_new.empty:
        print("📭 Aucune nouvelle facture à ajouter")
        return 0
    
    print(f"📥 Ajout de {len(df_new)} nouvelles factures...")
    
    for _, row in df_new.iterrows():
        try:
            cursor.execute("""
                INSERT INTO invoices (
                    label, order_number, invoice_created, subtotal,
                    total, customer_name, customer_email,
                    fournisseur, gestionnaire, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (label) DO NOTHING
            """, (
                row.get('commande_id'),
                row.get('order_number', ''),
                row.get('date'),
                row.get('prix_ht', 0),
                row.get('prix_ht', 0),
                row.get('customer_name', ''),
                row.get('customer_email', ''),
                row.get('fournisseur', 'Non spécifié'),
                row.get('gestionnaire_de_compte', 'Non spécifié'),
                datetime.now(),
                datetime.now()
            ))
        except Exception as e:
            print(f"⚠️ Erreur insertion {row.get('commande_id')}: {e}")
    
    conn.commit()
    print(f"✅ {len(df_new)} factures ajoutées")
    return len(df_new)

def update_invoice_lines_table(conn, df_orders):
    """Met à jour la table invoice_lines"""
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, label FROM invoices")
    invoice_map = {row[1]: row[0] for row in cursor.fetchall()}
    
    count = 0
    for _, row in df_orders.iterrows():
        invoice_label = row.get('commande_id')
        if invoice_label not in invoice_map:
            continue
            
        invoice_id = invoice_map[invoice_label]
        
        cursor.execute("""
            SELECT id FROM invoice_lines 
            WHERE invoice_id = %s AND product_sku = %s
        """, (invoice_id, row.get('produit_sku', '')))
        
        if cursor.fetchone():
            continue
        
        try:
            cursor.execute("""
                INSERT INTO invoice_lines (
                    invoice_id, product_label, product_sku, quantity,
                    unit_price, line_total, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                invoice_id,
                row.get('produit', ''),
                row.get('produit_sku', ''),
                row.get('quantite', 0),
                row.get('prix_ht', 0) / max(row.get('quantite', 1), 1),
                row.get('prix_ht', 0),
                datetime.now()
            ))
            count += 1
        except Exception as e:
            print(f"⚠️ Erreur insertion ligne: {e}")
    
    conn.commit()
    print(f"✅ {count} lignes de facture ajoutées")
    return count

def update_products_table(conn, df_orders):
    """Met à jour la table products avec les nouveaux produits"""
    cursor = conn.cursor()
    
    products = df_orders[['produit', 'produit_sku']].drop_duplicates()
    products = products[products['produit'].notna() & (products['produit'] != '')]
    
    count = 0
    for _, row in products.iterrows():
        product_name = row['produit']
        
        cursor.execute("SELECT id FROM products WHERE name = %s", (product_name,))
        if cursor.fetchone():
            continue
        
        try:
            cursor.execute("""
                INSERT INTO products (name, sku, supplier_name, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (product_name, row.get('produit_sku', ''), 'À déterminer', datetime.now(), datetime.now()))
            count += 1
        except Exception as e:
            print(f"⚠️ Erreur insertion produit {product_name}: {e}")
    
    conn.commit()
    print(f"✅ {count} nouveaux produits ajoutés")
    return count

def main():
    print("=" * 60)
    print("🔄 MISE À JOUR DE LA BASE DE DONNÉES")
    print("=" * 60)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 1. Récupérer les données
    print("📡 Étape 1: Récupération des commandes depuis Erplain...")
    df_orders = fetch_orders_from_erplain(2026)
    
    if df_orders.empty:
        print("❌ Aucune donnée récupérée. Vérifiez votre token et endpoint.")
        print(f"   Endpoint: {ERPLAIN_ENDPOINT}")
        return
    
    print(f"✅ {len(df_orders)} lignes récupérées")
    print()
    
    # 2. Connexion à PostgreSQL
    print("🔌 Étape 2: Connexion à PostgreSQL...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        print("✅ Connecté")
    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")
        return
    print()
    
    try:
        # 3. Mettre à jour les tables
        print("📝 Étape 3: Mise à jour des tables...")
        print("-" * 40)
        
        nb_products = update_products_table(conn, df_orders)
        nb_invoices = update_invoices_table(conn, df_orders)
        nb_invoice_lines = update_invoice_lines_table(conn, df_orders)
        
        print("-" * 40)
        print()
        
        # 4. Résumé
        print("📊 RÉSUMÉ DE LA MISE À JOUR:")
        print(f"   🆕 Nouveaux produits: {nb_products}")
        print(f"   🆕 Nouvelles factures: {nb_invoices}")
        print(f"   🆕 Nouvelles lignes factures: {nb_invoice_lines}")
        
    except Exception as e:
        print(f"❌ Erreur lors de la mise à jour: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()
        print()
        print("=" * 60)
        print("✅ MISE À JOUR TERMINÉE")
        print("=" * 60)

if __name__ == "__main__":
    main()