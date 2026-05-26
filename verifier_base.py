# verifier_base.py
import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cursor = conn.cursor()

# Vérifier les colonnes de la table invoices
print("=" * 60)
print("📋 COLONNES DE LA TABLE INVOICES")
print("=" * 60)

cursor.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns 
    WHERE table_name = 'invoices'
    ORDER BY ordinal_position
""")

for row in cursor.fetchall():
    print(f"   - {row[0]} ({row[1]}) nullable={row[2]}")

# Vérifier si la colonne gestionnaire existe
print("\n" + "=" * 60)
print("🔍 VALEURS DE GESTIONNAIRE")
print("=" * 60)

cursor.execute("""
    SELECT gestionnaire, COUNT(*) as nb
    FROM invoices
    WHERE invoice_created >= '2026-01-01'
    GROUP BY gestionnaire
""")

rows = cursor.fetchall()
if rows:
    for row in rows:
        print(f"   {row[0]}: {row[1]} factures")
else:
    print("   Aucune donnée ou colonne gestionnaire inexistante")

# Vérifier les références externes
print("\n" + "=" * 60)
print("🏷️ EXEMPLES DE RÉFÉRENCES EXTERNES")
print("=" * 60)

cursor.execute("""
    SELECT order_number, reference_externe, gestionnaire
    FROM invoices
    WHERE invoice_created >= '2026-01-01'
    LIMIT 10
""")

for row in cursor.fetchall():
    print(f"   {row[0]}: ref='{row[1]}' gest='{row[2]}'")

cursor.close()
conn.close()