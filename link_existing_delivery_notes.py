# link_existing_delivery_notes.py
import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def link_existing_bl_to_invoices():
    """Lie les BL existants aux factures."""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Vérifier si la table delivery_notes existe
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'delivery_notes'
        )
    """)
    
    if not cursor.fetchone()[0]:
        print("❌ Table 'delivery_notes' non trouvée")
        print("   Exécutez d'abord: python fetch_and_link_delivery_notes.py")
        return 0
    
    # Ajouter les colonnes si nécessaire
    cursor.execute("""
        ALTER TABLE invoices 
        ADD COLUMN IF NOT EXISTS bl_number TEXT,
        ADD COLUMN IF NOT EXISTS bl_id TEXT,
        ADD COLUMN IF NOT EXISTS bl_status TEXT,
        ADD COLUMN IF NOT EXISTS shipping_date DATE
    """)
    conn.commit()
    
    # Lier par order_number
    cursor.execute("""
        UPDATE invoices i
        SET 
            bl_number = dn.order_number,
            bl_id = dn.id,
            bl_status = dn.status,
            shipping_date = dn.shipping_date
        FROM delivery_notes dn
        WHERE i.order_number = dn.order_number
        AND i.bl_number IS NULL
    """)
    
    linked = cursor.rowcount
    conn.commit()
    
    # Statistiques
    cursor.execute("SELECT COUNT(*) FROM invoices WHERE bl_number IS NOT NULL")
    total_linked = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM delivery_notes")
    total_bl = cursor.fetchone()[0]
    
    cursor.close()
    conn.close()
    
    print(f"✅ {linked} nouvelles factures liées")
    print(f"📊 Total: {total_linked} factures liées sur {total_bl} BL")
    
    return linked

if __name__ == "__main__":
    link_existing_bl_to_invoices()