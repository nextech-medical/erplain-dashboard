# fix_tracking_complete.py
import psycopg2
import json
import re
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def extract_tracking(text):
    if not text:
        return None
    clean = re.sub(r'<[^>]+>', ' ', str(text))
    clean = re.sub(r'\s+', ' ', clean).strip()
    patterns = [
        r'\b(\d{12,16})\b',           # 26140097200012
        r'\b(00[A-Z0-9]{4,10})\b',    # 00KT0Q4C
        r'\b(GL\d{10,14}FR?)\b',      # GL1234567890FR
    ]
    for p in patterns:
        m = re.search(p, clean)
        if m:
            return m.group(1)
    return None

def add_missing_columns(cursor):
    # Vérifier et ajouter les colonnes manquantes
    cursor.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'delivery_notes'
    """)
    existing = [row[0] for row in cursor.fetchall()]
    if 'internal_notes' not in existing:
        cursor.execute("ALTER TABLE delivery_notes ADD COLUMN internal_notes TEXT")
        print("✅ Colonne internal_notes ajoutée")
    if 'notes' not in existing:
        cursor.execute("ALTER TABLE delivery_notes ADD COLUMN notes TEXT")
        print("✅ Colonne notes ajoutée")
    if 'tracking_number' not in existing:
        cursor.execute("ALTER TABLE delivery_notes ADD COLUMN tracking_number TEXT")
        print("✅ Colonne tracking_number ajoutée")
    if 'synced_at' not in existing:
        cursor.execute("ALTER TABLE delivery_notes ADD COLUMN synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        print("✅ Colonne synced_at ajoutée")

def main():
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME,
        user=DB_USER, password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # 1. Ajouter les colonnes si nécessaires
    add_missing_columns(cursor)
    conn.commit()
    
    # 2. Lire le fichier JSON
    try:
        with open('delivery_notes_2026.json', 'r', encoding='utf-8') as f:
            notes = json.load(f)
        print(f"📁 Fichier JSON chargé : {len(notes)} BL")
    except FileNotFoundError:
        print("❌ Fichier delivery_notes_2026.json introuvable")
        conn.close()
        return
    
    # 3. Mettre à jour ou insérer les BL avec les bons tracking
    updated = 0
    for note in notes:
        order_number = note.get('order_number')
        internal = note.get('internal_notes', '')
        real_tracking = extract_tracking(internal)
        if not real_tracking:
            # Essayer avec notes classiques si internal_notes vide
            real_tracking = extract_tracking(note.get('notes', ''))
        
        # Vérifier si le BL existe déjà
        cursor.execute("SELECT id FROM delivery_notes WHERE order_number = %s", (order_number,))
        exists = cursor.fetchone()
        
        if exists:
            # Mise à jour
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
                order_number
            ))
        else:
            # Insertion
            cursor.execute("""
                INSERT INTO delivery_notes 
                (id, order_number, external_reference, shipping_date, status, 
                 tracking_number, internal_notes, notes, created_at, synced_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, (
                str(note.get('id')),
                order_number,
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
            print(f"   {updated} BL traités...")
            conn.commit()
    
    conn.commit()
    
    # 4. Vérifier le résultat
    cursor.execute("""
        SELECT order_number, tracking_number 
        FROM delivery_notes 
        WHERE tracking_number IS NOT NULL AND tracking_number NOT LIKE '2026-%'
        LIMIT 20
    """)
    rows = cursor.fetchall()
    print("\n📋 Exemples de tracking corrigés :")
    for r in rows:
        print(f"   {r[0]} → {r[1]}")
    
    cursor.close()
    conn.close()
    print(f"\n✅ {updated} BL mis à jour/insérés")

if __name__ == "__main__":
    main()