# update_external_references.py
"""
Récupère et met à jour les références externes pour les factures Amazon et Temu
"""

import requests
import psycopg2
import time
from config import API_URL, BEARER_TOKEN, DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def fetch_invoice_references():
    """Récupère les références externes des factures depuis Erplain"""
    
    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Récupérer les factures qui ont besoin d'une référence externe
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, order_number, label
        FROM invoices
        WHERE gestionnaire IN ('Amazon .fr', 'TEMU FR')
        AND (reference_externe IS NULL OR reference_externe = '')
        AND invoice_created >= '2026-01-01'
        LIMIT 100
    """)
    
    invoices_to_update = cursor.fetchall()
    print(f"\n📋 {len(invoices_to_update)} factures à mettre à jour")
    
    if not invoices_to_update:
        cursor.close()
        conn.close()
        return 0
    
    updated = 0
    
    for inv_id, order_number, label in invoices_to_update:
        # Chercher par order_number ou label
        search_ref = order_number if order_number else label
        
        # Requête pour récupérer la facture spécifique
        query = f"""
        {{
          Invoices(page: 1, page_size: 1, filter: {{ label: "{search_ref}" }}) {{
            edges {{
              node {{
                id
                label
                order_number
                external_reference
                notes
              }}
            }}
          }}
        }}
        """
        
        try:
            response = requests.post(API_URL, json={"query": query}, headers=headers, timeout=30)
            data = response.json()
            
            if "errors" in data:
                print(f"   ⚠️ Erreur pour {order_number}: {data['errors'][0].get('message', 'Unknown')[:50]}")
                continue
            
            edges = data.get("data", {}).get("Invoices", {}).get("edges", {})
            nodes = []
            if isinstance(edges, dict):
                node_data = edges.get("node")
                if isinstance(node_data, list):
                    nodes = node_data
                elif node_data:
                    nodes = [node_data]
            
            if nodes:
                node = nodes[0]
                external_ref = node.get("external_reference")
                notes = node.get("notes")
                
                # Extraire la référence des notes si nécessaire
                if not external_ref and notes:
                    import re
                    # Chercher pattern Amazon ou Temu dans les notes
                    amazon_match = re.search(r'\b(\d{3}-\d{7}-\d{7})\b', notes)
                    if amazon_match:
                        external_ref = amazon_match.group(1)
                    else:
                        temu_match = re.search(r'\b(PO-[A-Z0-9-]+)\b', notes)
                        if temu_match:
                            external_ref = temu_match.group(1)
                
                if external_ref:
                    cursor.execute("""
                        UPDATE invoices 
                        SET reference_externe = %s
                        WHERE id = %s
                    """, (external_ref, inv_id))
                    updated += 1
                    print(f"   ✅ {order_number}: {external_ref}")
                else:
                    print(f"   ⚠️ {order_number}: aucune référence trouvée")
            
            time.sleep(0.5)  # Éviter de surcharger l'API
            
        except Exception as e:
            print(f"   ❌ Erreur {order_number}: {e}")
            continue
        
        if updated % 20 == 0:
            conn.commit()
            print(f"   --- {updated} mises à jour ---")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\n✅ {updated} références mises à jour")
    return updated

def update_from_shipping_orders():
    """Récupère les références depuis les bons de livraison"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n📌 MISE À JOUR DEPUIS LES BONS DE LIVRAISON:")
    
    # Vérifier si la table delivery_notes existe
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'delivery_notes'
        )
    """)
    
    if cursor.fetchone()[0]:
        cursor.execute("""
            UPDATE invoices i
            SET reference_externe = dn.external_reference
            FROM delivery_notes dn
            WHERE i.order_number = dn.order_number
            AND i.gestionnaire IN ('Amazon .fr', 'TEMU FR')
            AND (i.reference_externe IS NULL OR i.reference_externe = '')
            AND dn.external_reference IS NOT NULL
        """)
        print(f"   ✅ {cursor.rowcount} références mises à jour depuis delivery_notes")
    else:
        print("   ⚠️ Table delivery_notes non trouvée")
    
    conn.commit()
    cursor.close()
    conn.close()

def fix_amazon_temu_classification():
    """Reclasse correctement Amazon et Temu en fonction des références"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n📌 RECLASSIFICATION AMAZON/TEMU:")
    
    # Amazon par référence
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Amazon .fr'
        WHERE reference_externe ~ '^[0-9]{3}-[0-9]{7}-[0-9]{7}$'
    """)
    print(f"   ✅ {cursor.rowcount} → Amazon .fr")
    
    # Temu par référence
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'TEMU FR'
        WHERE reference_externe LIKE 'PO-%'
    """)
    print(f"   ✅ {cursor.rowcount} → TEMU FR")
    
    conn.commit()
    cursor.close()
    conn.close()

def show_final_stats():
    """Affiche les statistiques finales"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    print("\n" + "=" * 80)
    print("📊 STATISTIQUES FINALES")
    print("=" * 80)
    
    query = """
        SELECT 
            gestionnaire,
            COUNT(*) as nb,
            ROUND(SUM(total)::numeric, 2) as ca,
            COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as avec_ref
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        GROUP BY gestionnaire
        ORDER BY ca DESC
    """
    
    import pandas as pd
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print(df.to_string(index=False))
    return df

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--fetch":
            fetch_invoice_references()
        elif sys.argv[1] == "--bl":
            update_from_shipping_orders()
        elif sys.argv[1] == "--classify":
            fix_amazon_temu_classification()
        elif sys.argv[1] == "--all":
            update_from_shipping_orders()
            fetch_invoice_references()
            fix_amazon_temu_classification()
            show_final_stats()
        elif sys.argv[1] == "--stats":
            show_final_stats()
        else:
            print("""
Usage: python update_external_references.py [OPTION]

Options:
  --fetch     Récupère les références depuis l'API Erplain
  --bl        Récupère les références depuis delivery_notes
  --classify  Reclassifie Amazon/Temu par pattern
  --stats     Affiche les statistiques
  --all       Exécute tout

Sans option: Exécute la séquence complète
            """)
    else:
        update_from_shipping_orders()
        fetch_invoice_references()
        fix_amazon_temu_classification()
        show_final_stats()