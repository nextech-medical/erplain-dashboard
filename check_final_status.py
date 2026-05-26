# check_final_status.py
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
print("📊 SITUATION FINALE DES GESTIONNAIRES")
print("=" * 80)

# 1. Distribution par gestionnaire
query = """
    SELECT 
        gestionnaire,
        COUNT(*) as nb_factures,
        ROUND(SUM(total)::numeric, 2) as ca_total,
        COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as avec_ref
    FROM invoices
    WHERE invoice_created >= '2026-01-01'
    GROUP BY gestionnaire
    ORDER BY ca_total DESC
"""
df = pd.read_sql_query(query, conn)
print("\n📋 PAR GESTIONNAIRE:")
print(df.to_string(index=False))

# 2. Vérifier les références Amazon et Temu
print("\n" + "=" * 80)
print("🔍 VÉRIFICATION DES RÉFÉRENCES AMAZON/TEMU")
print("=" * 80)

query2 = """
    SELECT 
        gestionnaire,
        COUNT(*) as total,
        COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as avec_ref,
        COUNT(CASE WHEN reference_externe IS NULL OR reference_externe = '' THEN 1 END) as sans_ref
    FROM invoices
    WHERE gestionnaire IN ('Amazon .fr', 'TEMU FR')
    AND invoice_created >= '2026-01-01'
    GROUP BY gestionnaire
"""
df2 = pd.read_sql_query(query2, conn)
print(df2.to_string(index=False))

# 3. Afficher quelques exemples de références Amazon
print("\n" + "=" * 80)
print("📋 EXEMPLES DE RÉFÉRENCES AMAZON (après mise à jour)")
print("=" * 80)

query3 = """
    SELECT order_number, reference_externe, total
    FROM invoices
    WHERE gestionnaire = 'Amazon .fr'
    AND reference_externe IS NOT NULL AND reference_externe != ''
    LIMIT 10
"""
df3 = pd.read_sql_query(query3, conn)
if not df3.empty:
    print(df3.to_string(index=False))
else:
    print("⚠️ Aucune référence Amazon trouvée")

conn.close()