# fix_external_reference_corrected.py
import requests
import json
import psycopg2
import re
import pandas as pd
from datetime import datetime
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, API_URL, BEARER_TOKEN

def fetch_delivery_notes_with_references():
    """Récupère les bons de livraison avec les bons champs."""
    
    all_notes = []
    page = 1
    page_size = 100
    
    while True:
        print(f"📥 Récupération des BL page {page}...")
        
        # Requête avec les bons noms de champs
        query = f"""
        query {{
          ShippingOrders(page: {page}, page_size: {page_size}) {{
            edges {{
              node {{
                id
                order_number
                notes
                external_reference
                shipping_date
                shipping_order_status
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
            
            notes_data = data.get("data", {}).get("ShippingOrders", {})
            edges = notes_data.get("edges", {})
            nodes = edges.get("node", [])
            
            if not nodes:
                break
            
            all_notes.extend(nodes)
            print(f"   ✅ {len(nodes)} BL (total: {len(all_notes)})")
            
            if len(nodes) < page_size:
                break
            page += 1
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            break
    
    return all_notes

def extract_reference_from_notes(notes):
    """Extrait la référence externe des notes."""
    
    if not notes:
        return None
    
    # Nettoyer le HTML
    import re
    clean_notes = re.sub(r'<[^>]+>', ' ', notes)
    
    # Patterns pour trouver les références
    patterns = [
        r'Commande\s*[Nn]°?\s*[:\s]*([A-Z0-9\-]+)',
        r'Référence\s*[:\s]*([A-Z0-9\-]+)',
        r'PO[-\s]*([A-Z0-9]+)',
        r'E(\d{6})',
        r'N°\s*d\'engagement\s*:\s*([A-Z0-9]+)',
        r'bon de commande\s*[Nn]°?\s*[:\s]*([A-Z0-9\-]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, clean_notes, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None

def update_invoices_from_notes():
    """Met à jour les factures à partir des notes existantes."""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Récupérer les factures avec notes mais sans référence
    cursor.execute("""
        SELECT id, order_number, notes_text 
        FROM invoices 
        WHERE notes_text IS NOT NULL 
        AND (reference_externe IS NULL OR reference_externe = '')
    """)
    
    invoices = cursor.fetchall()
    
    count = 0
    for inv_id, order_number, notes in invoices:
        if notes:
            reference = extract_reference_from_notes(notes)
            if reference:
                cursor.execute("""
                    UPDATE invoices 
                    SET reference_externe = %s
                    WHERE id = %s
                """, (reference, inv_id))
                count += 1
                
                if count % 10 == 0:
                    print(f"   {count} références trouvées...")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ {count} références externes extraites des notes")
    return count

def update_from_delivery_notes():
    """Met à jour à partir des BL si disponibles."""
    
    print("\n📦 Récupération des BL...")
    delivery_notes = fetch_delivery_notes_with_references()
    
    if not delivery_notes:
        print("⚠️ Aucun BL récupéré (peut-être normal si pas de BL)")
        return 0
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    count = 0
    for note in delivery_notes:
        try:
            order_number = note.get('order_number')
            external_ref = note.get('external_reference')
            
            if external_ref and order_number:
                cursor.execute("""
                    UPDATE invoices 
                    SET reference_externe = %s,
                        shipping_date = %s
                    WHERE order_number = %s
                    AND (reference_externe IS NULL OR reference_externe = '')
                """, (external_ref, note.get('shipping_date'), order_number))
                count += cursor.rowcount
                
        except Exception as e:
            print(f"❌ Erreur: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ {count} références mises à jour depuis les BL")
    return count

def show_statistics():
    """Affiche les statistiques."""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    query = """
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as with_ref
        FROM invoices
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print("\n" + "="*50)
    print("📊 STATISTIQUES DES RÉFÉRENCES")
    print("="*50)
    print(f"   📄 Total factures: {df['total'].iloc[0]}")
    print(f"   🏷️ Avec référence externe: {df['with_ref'].iloc[0]}")
    print("="*50)

def show_examples():
    """Affiche des exemples."""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    query = """
        SELECT order_number, customer_name, reference_externe
        FROM invoices 
        WHERE reference_externe IS NOT NULL AND reference_externe != ''
        LIMIT 10
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df.empty:
        print("\n📋 Exemples de références externes:")
        print(df.to_string(index=False))

def sync_all():
    """Synchronisation complète."""
    
    print("\n" + "="*60)
    print("🔄 CORRECTION DES RÉFÉRENCES EXTERNES")
    print("="*60)
    
    # 1. Extraire des notes des factures
    print("\n📝 Extraction des références depuis les notes...")
    count1 = update_invoices_from_notes()
    
    # 2. Essayer depuis les BL
    count2 = update_from_delivery_notes()
    
    # 3. Afficher les résultats
    show_statistics()
    show_examples()
    
    print("\n" + "="*60)
    print(f"✅ {count1 + count2} références mises à jour")
    print("="*60)

if __name__ == "__main__":
    sync_all()