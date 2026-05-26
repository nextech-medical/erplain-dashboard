# rebuild_delivery_notes.py
import json
import psycopg2
import re
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def extract_tracking(text):
    if not text:
        return None
    clean = re.sub(r'<[^>]+>', ' ', str(text))
    clean = re.sub(r'\s+', ' ', clean).strip()
    patterns = [r'\b(\d{12,16})\b', r'\b(00[A-Z0-9]{4,10})\b', r'\b(GL\d{10,14}FR?)\b']
    for p in patterns:
        m = re.search(p, clean)
        if m:
            return m.group(1)
    return None

def safe_text(value, max_len=500):
    """Convertit None en chaîne vide et tronque"""
    if value is None:
        return ""
    s = str(value)
    return s[:max_len]

# Charger le JSON
with open('delivery_notes_2026.json', 'r', encoding='utf-8') as f:
    notes = json.load(f)
print(f"📁 {len(notes)} BL chargés depuis JSON")

# Connexion PostgreSQL
conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME,
    user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

# S'assurer que la table existe avec les bonnes colonnes
cur.execute("""
    CREATE TABLE IF NOT EXISTS delivery_notes (
        id VARCHAR(50) PRIMARY KEY,
        order_number VARCHAR(100),
        external_reference TEXT,
        shipping_date DATE,
        status VARCHAR(50),
        tracking_number TEXT,
        internal_notes TEXT,
        notes TEXT,
        created_at TIMESTAMP,
        synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()

print("🔄 Mise à jour de la table...")
count = 0
for n in notes:
    order_num = n.get('order_number')
    if not order_num:
        continue
    internal = n.get('internal_notes', '')
    tracking = extract_tracking(internal)
    
    # Utiliser safe_text pour éviter None
    cur.execute("""
        INSERT INTO delivery_notes 
        (id, order_number, external_reference, shipping_date, status, tracking_number, internal_notes, notes, created_at, synced_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (id) DO UPDATE SET
            order_number = EXCLUDED.order_number,
            external_reference = EXCLUDED.external_reference,
            shipping_date = EXCLUDED.shipping_date,
            status = EXCLUDED.status,
            tracking_number = EXCLUDED.tracking_number,
            internal_notes = EXCLUDED.internal_notes,
            notes = EXCLUDED.notes,
            synced_at = CURRENT_TIMESTAMP
    """, (
        str(n.get('id')),
        order_num,
        n.get('external_reference'),
        n.get('shipping_date'),
        n.get('shipping_order_status'),
        tracking,
        safe_text(internal),
        safe_text(n.get('notes', '')),
        n.get('created')
    ))
    count += 1

conn.commit()

# Vérifier les résultats
cur.execute("SELECT order_number, tracking_number FROM delivery_notes WHERE tracking_number IS NOT NULL LIMIT 20")
rows = cur.fetchall()
print("\n📋 Numéros de suivi maintenant en base :")
for r in rows:
    print(f"   {r[0]} → {r[1]}")

cur.execute("SELECT COUNT(*) FROM delivery_notes WHERE tracking_number IS NOT NULL")
total = cur.fetchone()[0]
print(f"\n✅ Total BL avec tracking valide : {total} sur {count}")

cur.close()
conn.close()