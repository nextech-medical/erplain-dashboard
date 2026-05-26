# find_matching_field.py
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
print("RECHERCHE DU CHAMP DE CORRESPONDANCE")
print("=" * 70)

# 1. Voir les colonnes disponibles dans invoices
print("\n1. Colonnes dans invoices:")
cursor.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'invoices'
    ORDER BY ordinal_position
""")
for row in cursor.fetchall():
    print(f"   - {row[0]}")

# 2. Voir un exemple complet d'une facture
print("\n2. Exemple d'une facture (S29110):")
cursor.execute("""
    SELECT * FROM invoices 
    WHERE order_number = 'S29110' 
    LIMIT 1
""")
col_names = [desc[0] for desc in cursor.description]
row = cursor.fetchone()
if row:
    for i, col in enumerate(col_names):
        if row[i] and str(row[i]) != '':
            print(f"   {col}: {row[i]}")

# 3. Voir un exemple d'une commande
print("\n3. Exemple d'une commande (BC217837237):")
cursor.execute("""
    SELECT * FROM orders 
    WHERE order_id = 'BC217837237' 
    LIMIT 1
""")
col_names = [desc[0] for desc in cursor.description]
row = cursor.fetchone()
if row:
    for i, col in enumerate(col_names):
        if row[i] and str(row[i]) != '':
            print(f"   {col}: {row[i]}")

# 4. Chercher des correspondances possibles
print("\n4. Recherche de correspondances...")

# Vérifier si external_reference peut correspondre
cursor.execute("""
    SELECT i.order_number, i.reference_externe, o.order_id, o.external_reference
    FROM invoices i
    LEFT JOIN orders o ON i.reference_externe = o.external_reference
    WHERE i.reference_externe IS NOT NULL AND i.reference_externe != ''
    LIMIT 10
""")
matches = cursor.fetchall()
print("\n   Correspondances par reference_externe:")
for row in matches:
    if row[1] and row[3] and row[1] == row[3]:
        print(f"      ✅ {row[0]} (invoice) = {row[2]} (order) via ref: {row[1]}")
    else:
        print(f"      ❌ {row[0]} -> ref: {row[1]} | order ref: {row[3]}")

# 5. Compter les correspondances potentielles
cursor.execute("""
    SELECT COUNT(*)
    FROM invoices i
    INNER JOIN orders o ON i.reference_externe = o.external_reference
    WHERE i.reference_externe IS NOT NULL AND i.reference_externe != ''
""")
count = cursor.fetchone()[0]
print(f"\n   Correspondances trouvées: {count}")

conn.close()