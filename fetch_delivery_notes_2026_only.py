# fetch_bl.py
import requests
import json
import psycopg2
from datetime import datetime
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, API_URL, BEARER_TOKEN

def fetch_all_delivery_notes():
    """Récupère TOUS les bons de livraison."""
    
    all_notes = []
    page = 1
    page_size = 100
    
    while True:
        print(f"📥 Récupération des BL page {page}...")
        
        # Requête simple sans filtre
        query = f"""
        {{
          ShippingOrders(page: {page}, page_size: {page_size}) {{
            edges {{
              node {{
                id
                order_number
                external_reference
                shipping_date
                shipping_order_status
                created
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
            
            # Gérer la structure: edges peut être un dict avec 'node' qui est une liste
            if isinstance(edges, dict):
                nodes = edges.get("node", [])
            elif isinstance(edges, list):
                nodes = []
                for edge in edges:
                    if isinstance(edge, dict):
                        node = edge.get("node")
                        if node:
                            nodes.append(node)
            else:
                nodes = []
            
            if not nodes:
                print("✅ Plus de BL")
                break
            
            all_notes.extend(nodes)
            print(f"   ✅ {len(nodes)} BL (total: {len(all_notes)})")
            
            if len(nodes) < page_size:
                break
            page += 1
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            import traceback
            traceback.print_exc()
            break
    
    return all_notes

def create_delivery_table():
    """Crée la table des BL dans PostgreSQL."""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    cursor.execute("DROP TABLE IF EXISTS delivery_notes CASCADE")
    cursor.execute("""
        CREATE TABLE delivery_notes (
            id VARCHAR(50) PRIMARY KEY,
            order_number VARCHAR(50),
            external_reference TEXT,
            shipping_date DATE,
            status VARCHAR(50),
            created_at TIMESTAMP,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Table 'delivery_notes' créée")

def save_delivery_notes_to_db(notes):
    """Sauvegarde les BL dans PostgreSQL."""
    if not notes:
        print("⚠️ Aucun BL à sauvegarder")
        return 0
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    count = 0
    for note in notes:
        try:
            cursor.execute("""
                INSERT INTO delivery_notes (
                    id, order_number, external_reference,
                    shipping_date, status, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    external_reference = EXCLUDED.external_reference,
                    status = EXCLUDED.status
            """, (
                str(note.get('id')),
                note.get('order_number'),
                note.get('external_reference'),
                note.get('shipping_date'),
                note.get('shipping_order_status'),
                note.get('created')
            ))
            count += 1
            
            if count % 50 == 0:
                print(f"   Sauvegarde: {count}/{len(notes)}...")
                conn.commit()
                
        except Exception as e:
            print(f"❌ Erreur BL {note.get('id')}: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ {count} BL sauvegardés")
    return count

def show_statistics(notes):
    """Affiche les statistiques des années."""
    
    years = {}
    for note in notes:
        created = note.get('created')
        if created:
            try:
                if isinstance(created, str):
                    year = created[:4]
                else:
                    year = str(created.year)
                years[year] = years.get(year, 0) + 1
            except:
                pass
    
    print("\n" + "="*50)
    print("📊 RÉPARTITION DES BL PAR ANNÉE")
    print("="*50)
    if years:
        for year in sorted(years.keys()):
            print(f"   {year}: {years[year]} BL")
    else:
        print("   Aucune date trouvée")
    print("="*50)

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔄 RÉCUPÉRATION DES BL")
    print("="*60)
    
    # 1. Créer la table
    create_delivery_table()
    
    # 2. Récupérer les BL
    print("\n📦 Récupération des BL depuis Erplain...")
    bl_notes = fetch_all_delivery_notes()
    
    if bl_notes:
        print(f"\n📊 {len(bl_notes)} BL récupérés")
        show_statistics(bl_notes)
        
        # 3. Sauvegarder
        save_delivery_notes_to_db(bl_notes)
        
        # 4. Sauvegarder en JSON
        with open("bl_erplain.json", "w", encoding="utf-8") as f:
            json.dump(bl_notes, f, indent=2, ensure_ascii=False, default=str)
        print("\n💾 Fichier sauvegardé: bl_erplain.json")
    else:
        print("❌ Aucun BL récupéré")