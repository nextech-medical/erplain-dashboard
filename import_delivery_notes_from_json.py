# import_delivery_notes_from_json.py
import json
import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def import_json():
    with open('delivery_notes.json', 'r', encoding='utf-8') as f:
        notes = json.load(f)
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Ajouter la colonne synced_at si elle n'existe pas
    cursor.execute("ALTER TABLE delivery_notes ADD COLUMN IF NOT EXISTS synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    
    count = 0
    for note in notes:
        try:
            cursor.execute("""
                INSERT INTO delivery_notes (id, order_number, external_reference, shipping_date, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    external_reference = EXCLUDED.external_reference,
                    status = EXCLUDED.status,
                    shipping_date = EXCLUDED.shipping_date
            """, (
                str(note.get('id')),
                note.get('order_number'),
                note.get('external_reference'),
                note.get('shipping_date'),
                note.get('shipping_order_status'),
                note.get('created')
            ))
            count += 1
        except Exception as e:
            print(f"Erreur: {e}")
    conn.commit()
    cursor.close()
    conn.close()
    print(f"Importé {count} BL depuis JSON")

if __name__ == "__main__":
    import_json()