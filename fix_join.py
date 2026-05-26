# fix_join.py
import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cursor = conn.cursor()

print("=" * 70)
print("CRÉATION D'UNE TABLE DE CORRESPONDANCE")
print("=" * 70)

# 1. Vérifier ce qu'il y a dans invoices.order_number
cursor.execute("""
    SELECT DISTINCT order_number 
    FROM invoices 
    WHERE order_number IS NOT NULL AND order_number != ''
    LIMIT 10
""")
print("\n📋 order_number dans invoices:")
for row in cursor.fetchall():
    print(f"   - {row[0]}")

# 2. Vérifier ce qu'il y a dans invoices.label
cursor.execute("""
    SELECT DISTINCT label 
    FROM invoices 
    WHERE label IS NOT NULL AND label != ''
    LIMIT 10
""")
print("\n📋 label dans invoices:")
for row in cursor.fetchall():
    print(f"   - {row[0]}")

# 3. SOLUTION: Ajouter une colonne gestionnaire à la table invoices si elle n'existe pas
try:
    cursor.execute("""
        ALTER TABLE invoices 
        ADD COLUMN IF NOT EXISTS gestionnaire_import VARCHAR(255)
    """)
    print("\n✅ Colonne gestionnaire_import ajoutée à invoices")
except Exception as e:
    print(f"⚠️ {e}")

# 4. Mettre à jour invoices.gestionnaire_import avec les valeurs de orders
cursor.execute("""
    UPDATE invoices 
    SET gestionnaire_import = orders.account_manager_name
    FROM orders 
    WHERE invoices.order_number = orders.order_id 
       OR invoices.label = orders.order_id
       OR invoices.label = orders.label
       OR invoices.order_number = orders.label
    WHERE invoices.gestionnaire_import IS NULL
""")
updated = cursor.rowcount
print(f"\n✅ {updated} factures mises à jour avec gestionnaire depuis orders")

# 5. Vérifier le résultat
cursor.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN gestionnaire_import IS NOT NULL AND gestionnaire_import != '' THEN 1 END) as avec_gest
    FROM invoices
    WHERE invoice_created IS NOT NULL
""")
result = cursor.fetchone()
print(f"\n📊 Résultat:")
print(f"   Total factures: {result[0]}")
print(f"   Avec gestionnaire: {result[1]}")
print(f"   Sans gestionnaire: {result[0] - result[1]}")

conn.commit()
cursor.close()
conn.close()