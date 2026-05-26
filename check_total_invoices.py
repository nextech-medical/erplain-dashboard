# check_total_invoices.py
import psycopg2
import pandas as pd
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

print("\n" + "=" * 80)
print("📊 STATISTIQUES DES FACTURES 2026")
print("=" * 80)

query = """
    SELECT 
        COUNT(*) as total_factures,
        COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as avec_ref,
        COUNT(CASE WHEN reference_externe IS NULL OR reference_externe = '' THEN 1 END) as sans_ref,
        ROUND(SUM(total)::numeric, 2) as ca_total,
        MIN(invoice_created) as premiere_facture,
        MAX(invoice_created) as derniere_facture
    FROM invoices
    WHERE invoice_created >= '2026-01-01'
"""

df = pd.read_sql_query(query, conn)
print(df.to_string(index=False))

# Distribution par gestionnaire
print("\n📋 DISTRIBUTION PAR GESTIONNAIRE:")
query2 = """
    SELECT 
        gestionnaire,
        COUNT(*) as nb_factures,
        COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as avec_ref,
        ROUND(SUM(total)::numeric, 2) as ca
    FROM invoices
    WHERE invoice_created >= '2026-01-01'
    GROUP BY gestionnaire
    ORDER BY ca DESC
"""

df2 = pd.read_sql_query(query2, conn)
print(df2.to_string(index=False))

conn.close()