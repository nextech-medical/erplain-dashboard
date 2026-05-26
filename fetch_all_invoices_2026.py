# fetch_all_invoices_2026.py
"""
Récupère TOUTES les factures 2026 depuis Erplain et les importe avec les bons gestionnaires
"""

import requests
import json
import psycopg2
import re
from datetime import datetime
from config import API_URL, BEARER_TOKEN, DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def fetch_all_invoices():
    """Récupère TOUTES les factures 2026"""
    
    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "Content-Type": "application/json"
    }
    
    all_invoices = []
    page = 1
    page_size = 100
    
    print("\n📥 Récupération de TOUTES les factures 2026...")
    print("=" * 60)
    
    while True:
        query = f"""
        {{
          Invoices(
            page: {page}
            page_size: {page_size}
            sort: {{ by: "created", direction: "DESC" }}
          ) {{
            edges {{
              node {{
                id
                label
                order_number
                created
                due_date
                subtotal
                total
                customer {{
                  label
                  emails
                }}
                line_items {{
                  edges {{
                    node {{
                      quantity
                      price
                      total
                      product {{
                        label
                        sku
                      }}
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """
        
        try:
            response = requests.post(API_URL, json={"query": query}, headers=headers, timeout=60)
            data = response.json()
            
            if "errors" in data:
                print(f"❌ Erreur: {data['errors'][0].get('message', 'Unknown')[:100]}")
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
                print(f"   ✅ Plus de factures à la page {page}")
                break
            
            # Filtrer par année 2026
            for node in nodes:
                created = node.get("created", "")
                if created and created.startswith("2026"):
                    all_invoices.append(node)
            
            print(f"   Page {page}: {len(nodes)} factures brutes, {len([n for n in nodes if n.get('created', '').startswith('2026')])} factures 2026")
            print(f"   Total 2026: {len(all_invoices)}")
            
            if len(nodes) < page_size:
                break
            page += 1
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            break
    
    print(f"\n✅ Total factures 2026 récupérées: {len(all_invoices)}")
    return all_invoices

def detect_gestionnaire_from_order(order_number, reference_externe):
    """Détecte le gestionnaire à partir du numéro de commande ou référence"""
    
    # Par référence externe
    if reference_externe:
        ref = str(reference_externe).upper()
        
        # Amazon: format 40X-XXXXXXX-XXXXXXX
        if re.match(r'^\d{3}-\d{7}-\d{7}$', ref):
            return 'Amazon .fr'
        
        # Temu: PO-...
        if ref.startswith('PO-'):
            return 'TEMU FR'
        
        # Appels d'offres
        if ref.startswith('PH') or ref.startswith('DMS') or ref.startswith('BS'):
            return 'Appels doffres'
        
        # Numéros simples (boutique)
        if ref.isdigit() and len(ref) >= 4:
            return 'NEXTECH Boutique'
    
    # Par numéro de commande
    if order_number:
        order = str(order_number).upper()
        
        if order.startswith('S') and order[1:].isdigit():
            return 'NEXTECH Boutique'
        
        if order.startswith('BC'):
            return 'NEXTECH Boutique'
    
    return 'Direct'

def import_invoices_to_db(invoices):
    """Importe les factures dans PostgreSQL"""
    
    if not invoices:
        print("❌ Aucune facture à importer")
        return 0
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Nettoyer les anciennes factures 2026
    cursor.execute("DELETE FROM invoices WHERE invoice_created >= '2026-01-01'")
    print(f"🗑️  Anciennes factures supprimées: {cursor.rowcount}")
    
    inserted = 0
    for inv in invoices:
        try:
            invoice_id = str(inv.get('id'))
            order_number = inv.get('order_number')
            label = inv.get('label')
            created = inv.get('created', '')[:10] if inv.get('created') else None
            due_date = inv.get('due_date', '')[:10] if inv.get('due_date') else None
            subtotal = float(inv.get('subtotal', 0) or 0)
            total = float(inv.get('total', 0) or 0)
            
            # Infos client
            customer = inv.get('customer', {})
            customer_name = customer.get('label') if isinstance(customer, dict) else None
            emails = customer.get('emails', []) if isinstance(customer, dict) else []
            customer_email = emails[0] if emails else None
            
            # Détection du gestionnaire
            gestionnaire = detect_gestionnaire_from_order(order_number, None)
            
            # Insérer la facture
            cursor.execute("""
                INSERT INTO invoices (
                    id, order_number, label, invoice_created, due_date,
                    subtotal, total, customer_name, customer_email, gestionnaire
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    order_number = EXCLUDED.order_number,
                    total = EXCLUDED.total,
                    customer_name = EXCLUDED.customer_name,
                    gestionnaire = EXCLUDED.gestionnaire
            """, (
                invoice_id, order_number, label, created, due_date,
                subtotal, total, customer_name, customer_email, gestionnaire
            ))
            
            # Insérer les lignes de facture
            line_items = inv.get('line_items', {})
            edges = line_items.get('edges', {})
            nodes = edges.get('node', []) if isinstance(edges, dict) else []
            
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                
                product = node.get('product', {})
                quantity = int(node.get('quantity', 0) or 0)
                price = float(node.get('price', 0) or 0)
                line_total = float(node.get('total', 0) or 0)
                product_label = product.get('label') if isinstance(product, dict) else None
                product_sku = product.get('sku') if isinstance(product, dict) else None
                
                cursor.execute("""
                    INSERT INTO invoice_lines (
                        invoice_id, product_label, product_sku, quantity,
                        unit_price, line_total
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (invoice_id, product_label, product_sku, quantity, price, line_total))
            
            inserted += 1
            if inserted % 100 == 0:
                conn.commit()
                print(f"   {inserted} factures importées...")
                
        except Exception as e:
            print(f"❌ Erreur facture {inv.get('order_number')}: {e}")
            continue
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\n✅ {inserted} factures importées")
    return inserted

def update_references_from_orders():
    """Met à jour les références externes depuis la table orders"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n📌 MISE À JOUR DES RÉFÉRENCES DEPUIS ORDERS:")
    
    cursor.execute("""
        UPDATE invoices i
        SET reference_externe = o.external_reference,
            gestionnaire = o.account_manager_name
        FROM orders o
        WHERE i.order_number = o.order_id
        AND o.external_reference IS NOT NULL
    """)
    print(f"   ✅ {cursor.rowcount} factures mises à jour")
    
    conn.commit()
    cursor.close()
    conn.close()

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🚀 RÉCUPÉRATION DE TOUTES LES FACTURES 2026")
    print("=" * 80)
    
    # 1. Récupérer toutes les factures
    invoices = fetch_all_invoices()
    
    if invoices:
        # 2. Importer dans la base
        import_invoices_to_db(invoices)
        
        # 3. Mettre à jour les références depuis orders
        update_references_from_orders()
        
        # 4. Afficher les statistiques finales
        import check_total_invoices
    else:
        print("❌ Aucune facture récupérée")