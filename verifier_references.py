# verifier_references.py
import psycopg2
import pandas as pd
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

print("=" * 60)
print("🔍 ANALYSE DES RÉFÉRENCES EXTERNES")
print("=" * 60)

# Compter les factures avec/sans référence
query = """
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as avec_ref,
        COUNT(CASE WHEN reference_externe IS NULL OR reference_externe = '' THEN 1 END) as sans_ref
    FROM invoices
    WHERE invoice_created >= '2026-01-01'
"""

df = pd.read_sql_query(query, conn)
print(f"\n📊 Statistiques:")
print(f"   Total factures: {df['total'].iloc[0]}")
print(f"   Avec référence externe: {df['avec_ref'].iloc[0]}")
print(f"   Sans référence externe: {df['sans_ref'].iloc[0]}")

# Afficher quelques exemples
print("\n📋 Exemples de factures:")
cursor = conn.cursor()
cursor.execute("""
    SELECT order_number, label, reference_externe, invoice_created
    FROM invoices
    WHERE invoice_created >= '2026-01-01'
    LIMIT 10
""")

for row in cursor.fetchall():
    print(f"   {row[0]}: ref='{row[2]}'")

conn.close()