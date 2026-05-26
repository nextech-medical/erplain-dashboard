# sync_delivery_notes.py corrigé
import requests
import json
import psycopg2
from datetime import datetime
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, API_URL, BEARER_TOKEN

def create_delivery_notes_table():
    """Crée la table delivery_notes avec la colonne synced_at"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS delivery_notes (
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
    print("✅ Table 'delivery_notes' vérifiée/créée (avec synced_at)")

def save_delivery_notes_to_db(notes):
    """Sauvegarde les BL dans PostgreSQL sans utiliser synced_at dans la mise à jour"""
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
            if count % 50 == 0:
                print(f"   Sauvegarde: {count}/{len(notes)}...")
                conn.commit()
        except Exception as e:
            print(f"❌ Erreur BL {note.get('id')}: {e}")
            conn.rollback()
    conn.commit()
    cursor.close()
    conn.close()
    print(f"✅ {count} BL sauvegardés")
    return count

# Le reste du code (fetch_all_delivery_notes, sync_delivery_notes) est identique