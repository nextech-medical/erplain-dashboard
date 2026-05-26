# fetch_all_invoices_fixed.py
"""
Récupère TOUTES les factures 2026 depuis Erplain (version corrigée)
"""

import requests
import json
import psycopg2
import re
from datetime import datetime
from config import API_URL, BEARER_TOKEN, DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def fetch_all_invoices():
    """Récupère TOUTES les factures 2026 sans l'erreur sur sku"""
    
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
        # Requête sans le champ sku qui pose problème
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
            
            print(f"   Page {page}: {len(nodes)} factures, {len([n for n in nodes if n.get('created', '').startswith('2026')])} en 2026")
            print(f"   Total 2026: {len(all_invoices)}")
            
            if len(nodes) < page_size:
                break
            page += 1
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            break
    
    print(f"\n✅ Total factures 2026 récupérées: {len(all_invoices)}")
    return all_invoices

def detect_gestionnaire(order_number, customer_email):
    """Détecte le gestionnaire"""
    
    # Par email
    if customer_email:
        if 'amazon' in customer_email.lower():
            return 'Amazon .fr'
        if 'temu' in customer_email.lower():
            return 'TEMU FR'
    
    # Par numéro de commande
    if order_number:
        if order_number.startswith('PO-'):
            return 'TEMU FR'
        if order_number.startswith('S') and order_number[1:].isdigit():
            return 'NEXTECH Boutique'
        if order_number.startswith('BC'):
            return 'NEXTECH Boutique'
    
    return 'NEXTECH Boutique'

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
            gestionnaire = detect_gestionnaire(order_number, customer_email)
            
            cursor.execute("""
                INSERT INTO invoices (
                    id, order_number, label, invoice_created, due_date,
                    subtotal, total, customer_name, customer_email, gestionnaire
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    order_number = EXCLUDED.order_number,
                    total = EXCLUDED.total,
                    gestionnaire = EXCLUDED.gestionnaire
            """, (
                invoice_id, order_number, label, created, due_date,
                subtotal, total, customer_name, customer_email, gestionnaire
            ))
            
            inserted += 1
            if inserted % 100 == 0:
                conn.commit()
                print(f"   {inserted} factures importées...")
                
        except Exception as e:
            print(f"❌ Erreur: {e}")
            continue
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\n✅ {inserted} factures importées")
    return inserted

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🚀 RÉCUPÉRATION DE TOUTES LES FACTURES 2026")
    print("=" * 80)
    
    invoices = fetch_all_invoices()
    
    if invoices:
        import_invoices_to_db(invoices)
        print("\n✅ Import terminé! Lancez maintenant:")
        print("   python clean_managers.py")
        print("   streamlit run dashboard_avance.py")
    else:
        print("❌ Aucune facture récupérée")