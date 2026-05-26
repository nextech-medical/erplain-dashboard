# update_from_orders.py
import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def update_from_orders():
    """Met à jour les références et gestionnaires depuis la table orders"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 60)
    print("🔄 MISE À JOUR DEPUIS LES COMMANDES")
    print("=" * 60)
    
    # Vérifier si orders existe
    cursor.execute("""
        SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'orders')
    """)
    
    if not cursor.fetchone()[0]:
        print("❌ Table 'orders' non trouvée")
        return 0
    
    # 1. Mettre à jour les références externes
    print("\n📌 Mise à jour des références externes...")
    cursor.execute("""
        UPDATE invoices i
        SET reference_externe = o.external_reference
        FROM orders o
        WHERE i.order_number = o.order_id
        AND i.reference_externe IS NULL
        AND o.external_reference IS NOT NULL
    """)
    
    updated_refs = cursor.rowcount
    print(f"   ✅ {updated_refs} factures mises à jour depuis orders")
    
    # 2. Mettre à jour les gestionnaires
    print("\n📌 Mise à jour des gestionnaires depuis account_manager...")
    cursor.execute("""
        UPDATE invoices i
        SET gestionnaire = o.account_manager_name
        FROM orders o
        WHERE i.order_number = o.order_id
        AND o.account_manager_name IS NOT NULL
        AND o.account_manager_name != ''
        AND (i.gestionnaire IS NULL OR i.gestionnaire = 'Direct')
    """)
    
    print(f"   ✅ {cursor.rowcount} factures mises à jour")
    
    conn.commit()
    
    # 3. Résultat
    cursor.execute("""
        SELECT 
            gestionnaire,
            COUNT(*) as nb
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        GROUP BY gestionnaire
        ORDER BY nb DESC
    """)
    
    print("\n📊 RÉPARTITION FINALE:")
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]} factures")
    
    cursor.close()
    conn.close()
    
    return updated_refs

if __name__ == "__main__":
    update_from_orders()