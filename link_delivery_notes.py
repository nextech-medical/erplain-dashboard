# link_delivery_notes.py
import psycopg2
import pandas as pd
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def link_delivery_notes():
    """Lie les bons de livraison aux factures."""
    
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
    delivery_exist = cursor.fetchone()[0]
    
    if not delivery_exist:
        print("⚠️ Table 'delivery_notes' non trouvée")
        print("   Importez d'abord les BL avec fetch_delivery_notes.py")
        return 0
    
    # Ajouter la colonne delivery_note_id si elle n'existe pas
    cursor.execute("""
        ALTER TABLE invoices 
        ADD COLUMN IF NOT EXISTS delivery_note_id TEXT,
        ADD COLUMN IF NOT EXISTS tracking_number TEXT,
        ADD COLUMN IF NOT EXISTS carrier TEXT,
        ADD COLUMN IF NOT EXISTS shipping_date DATE
    """)
    
    # Lier par numéro de commande
    cursor.execute("""
        UPDATE invoices i
        SET delivery_note_id = dn.id,
            tracking_number = dn.tracking_number,
            carrier = dn.carrier,
            shipping_date = dn.shipping_date
        FROM delivery_notes dn
        WHERE i.order_number = dn.order_number
        AND dn.order_number IS NOT NULL
    """)
    
    conn.commit()
    affected = cursor.rowcount
    cursor.close()
    conn.close()
    
    print(f"✅ {affected} factures liées aux bons de livraison")
    return affected

def show_update_status():
    """Affiche le statut après mise à jour."""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    query = """
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN customer_name IS NOT NULL AND customer_name != '' THEN 1 END) as with_customer,
            COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as with_ref,
            COUNT(CASE WHEN fournisseur IS NOT NULL AND fournisseur != 'Non spécifié' THEN 1 END) as with_supplier,
            COUNT(CASE WHEN delivery_note_id IS NOT NULL THEN 1 END) as with_bl
        FROM invoices
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print("\n📊 STATUT DES FACTURES APRÈS MISE À JOUR")
    print("="*50)
    print(f"   📄 Total factures: {df['total'].iloc[0]}")
    print(f"   👥 Avec client: {df['with_customer'].iloc[0]}")
    print(f"   🏷️ Avec référence externe: {df['with_ref'].iloc[0]}")
    print(f"   🏭 Avec fournisseur: {df['with_supplier'].iloc[0]}")
    print(f"   🚚 Avec BL lié: {df['with_bl'].iloc[0]}")
    print("="*50)

if __name__ == "__main__":
    link_delivery_notes()
    show_update_status()