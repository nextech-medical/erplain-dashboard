# diagnostic_join.py
import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def check_join():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("=" * 70)
    print("DIAGNOSTIC DE JOINTURE")
    print("=" * 70)
    
    # 1. Vérifier les valeurs dans invoices.label
    cursor.execute("""
        SELECT DISTINCT label 
        FROM invoices 
        WHERE invoice_created IS NOT NULL 
        LIMIT 10
    """)
    invoice_labels = cursor.fetchall()
    print("\n📋 Échantillon invoices.label:")
    for row in invoice_labels[:5]:
        print(f"   - {row[0]}")
    
    # 2. Vérifier les valeurs dans orders.order_id
    cursor.execute("""
        SELECT DISTINCT order_id 
        FROM orders 
        LIMIT 10
    """)
    order_ids = cursor.fetchall()
    print("\n📋 Échantillon orders.order_id:")
    for row in order_ids[:5]:
        print(f"   - {row[0]}")
    
    # 3. Vérifier les correspondances EXACTES
    cursor.execute("""
        SELECT COUNT(DISTINCT i.id) as matching
        FROM invoices i
        INNER JOIN orders o ON o.order_id = i.label
        WHERE i.invoice_created IS NOT NULL
    """)
    matching = cursor.fetchone()[0]
    print(f"\n🔗 Correspondances trouvées: {matching}")
    
    # 4. Vérifier les non-correspondances
    cursor.execute("""
        SELECT COUNT(DISTINCT i.id) as total
        FROM invoices i
        WHERE i.invoice_created IS NOT NULL
    """)
    total = cursor.fetchone()[0]
    print(f"📊 Total factures: {total}")
    print(f"❌ Non-correspondantes: {total - matching}")
    
    # 5. Afficher les gestionnaires trouvés
    if matching > 0:
        cursor.execute("""
            SELECT DISTINCT o.account_manager_name
            FROM invoices i
            INNER JOIN orders o ON o.order_id = i.label
            WHERE o.account_manager_name IS NOT NULL
        """)
        managers = cursor.fetchall()
        print("\n👤 Gestionnaires trouvés:")
        for m in managers:
            print(f"   - {m[0]}")
    
    # 6. Vérifier les types de données
    cursor.execute("""
        SELECT 
            pg_typeof(label) as type_label,
            pg_typeof(order_id) as type_order_id
        FROM invoices i, orders o
        LIMIT 1
    """)
    types = cursor.fetchone()
    print(f"\n📝 Types de données:")
    print(f"   invoices.label: {types[0]}")
    print(f"   orders.order_id: {types[1]}")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    check_join()