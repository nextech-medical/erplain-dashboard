# fix_delivery_notes.py
import psycopg2
import json
import re
import os
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def extract_tracking(text):
    """Extrait le vrai numéro de suivi depuis internal_notes"""
    if not text:
        return None
    # Nettoyer le texte
    clean = re.sub(r'<[^>]+>', ' ', str(text))
    clean = re.sub(r'\s+', ' ', clean).strip()
    # Patterns pour les vrais tracking
    patterns = [
        r'\b(\d{12,16})\b',           # 26140097200012
        r'\b(00[A-Z0-9]{4,10})\b',    # 00KT0Q4C
        r'\b(GL\d{10,14}FR?)\b',      # GL1234567890FR
        r'\b([A-Z0-9]{8,16})\b',      # Autres codes
    ]
    for p in patterns:
        m = re.search(p, clean)
        if m:
            return m.group(1)
    return None

def main():
    # 1. Connexion PostgreSQL
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME,
        user=DB_USER, password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # 2. Ajouter les colonnes manquantes
    print("🔧 Vérification des colonnes...")
    cursor.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'delivery_notes'
    """)
    existing = [row[0] for row in cursor.fetchall()]
    
    for col in ['internal_notes', 'notes', 'tracking_number', 'synced_at']:
        if col not in existing:
            cursor.execute(f"ALTER TABLE delivery_notes ADD COLUMN {col} TEXT")
            print(f"   ✅ Colonne {col} ajoutée")
    conn.commit()
    
    # 3. Charger le fichier JSON (généré par fetch_delivery_notes.py)
    if not os.path.exists('delivery_notes_2026.json'):
        print("❌ Fichier delivery_notes_2026.json introuvable")
        print("   Exécutez d'abord: python fetch_delivery_notes.py")
        conn.close()
        return
    
    with open('delivery_notes_2026.json', 'r', encoding='utf-8') as f:
        notes = json.load(f)
    print(f"\n📁 {len(notes)} BL chargés depuis delivery_notes_2026.json")
    
    # 4. Mettre à jour chaque BL
    updated = 0
    for note in notes:
        order_num = note.get('order_number')
        internal = note.get('internal_notes', '')
        real_tracking = extract_tracking(internal)
        
        # Vérifier si le BL existe déjà
        cursor.execute("SELECT id FROM delivery_notes WHERE order_number = %s", (order_num,))
        exists = cursor.fetchone()
        
        if exists:
            cursor.execute("""
                UPDATE delivery_notes 
                SET tracking_number = %s,
                    internal_notes = %s,
                    notes = %s,
                    external_reference = %s,
                    shipping_date = %s,
                    status = %s,
                    synced_at = CURRENT_TIMESTAMP
                WHERE order_number = %s
            """, (
                real_tracking,
                internal,
                note.get('notes', ''),
                note.get('external_reference'),
                note.get('shipping_date'),
                note.get('shipping_order_status'),
                order_num
            ))
        else:
            cursor.execute("""
                INSERT INTO delivery_notes 
                (id, order_number, external_reference, shipping_date, status, 
                 tracking_number, internal_notes, notes, created_at, synced_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, (
                str(note.get('id')),
                order_num,
                note.get('external_reference'),
                note.get('shipping_date'),
                note.get('shipping_order_status'),
                real_tracking,
                internal,
                note.get('notes', ''),
                note.get('created')
            ))
        
        updated += 1
        if updated % 100 == 0:
            conn.commit()
            print(f"   ⏳ {updated} BL traités...")
    
    conn.commit()
    
    # 5. Afficher quelques résultats
    cursor.execute("""
        SELECT order_number, tracking_number, internal_notes 
        FROM delivery_notes 
        WHERE tracking_number IS NOT NULL AND tracking_number NOT LIKE '2026-%'
        LIMIT 15
    """)
    rows = cursor.fetchall()
    
    print("\n" + "="*60)
    print("📋 NUMÉROS DE SUIVI CORRIGÉS")
    print("="*60)
    for r in rows:
        preview = re.sub(r'<[^>]+>', ' ', r[2])[:40] if r[2] else ''
        print(f"   {r[0]:<15} → {r[1]:<20} ({preview}...)")
    
    # 6. Statistiques
    cursor.execute("SELECT COUNT(*) FROM delivery_notes WHERE tracking_number IS NOT NULL")
    total_with_tracking = cursor.fetchone()[0]
    print(f"\n📊 Total BL avec tracking valide : {total_with_tracking}")
    
    cursor.close()
    conn.close()
    print("\n✅ Correction terminée")

if __name__ == "__main__":
    main()