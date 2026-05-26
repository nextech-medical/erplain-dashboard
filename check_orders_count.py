# check_orders_count.py
import psycopg2
import pandas as pd
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

print("\n" + "=" * 70)
print("📊 COMPARAISON DES VOLUMES")
print("=" * 70)

# Compter les commandes par gestionnaire dans orders
query_orders = """
    SELECT 
        account_manager_name,
        COUNT(*) as nb_commandes,
        COUNT(DISTINCT external_reference) as nb_ref_uniques
    FROM orders
    WHERE account_manager_name IS NOT NULL
    GROUP BY account_manager_name
    ORDER BY nb_commandes DESC
"""

df_orders = pd.read_sql_query(query_orders, conn)
print("\n📋 COMMANDES DANS ORDERS:")
print(df_orders.to_string(index=False))

# Compter les factures par gestionnaire dans invoices
query_invoices = """
    SELECT 
        gestionnaire,
        COUNT(*) as nb_factures,
        COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as avec_ref
    FROM invoices
    WHERE invoice_created >= '2026-01-01'
    GROUP BY gestionnaire
    ORDER BY nb_factures DESC
"""

df_invoices = pd.read_sql_query(query_invoices, conn)
print("\n📋 FACTURES DANS INVOICES:")
print(df_invoices.to_string(index=False))

# Vérifier les références externes communes
print("\n🔗 RECHERCHE DES CORRESPONDANCES PAR RÉFÉRENCE:")

cursor = conn.cursor()
cursor.execute("""
    SELECT COUNT(DISTINCT i.reference_externe)
    FROM invoices i
    WHERE i.reference_externe IS NOT NULL 
    AND i.reference_externe != ''
    AND i.reference_externe IN (SELECT external_reference FROM orders WHERE external_reference IS NOT NULL)
""")
common_ref = cursor.fetchone()[0]
print(f"   Références communes entre invoices et orders: {common_ref}")

cursor.execute("""
    SELECT COUNT(DISTINCT external_reference)
    FROM orders
    WHERE external_reference IS NOT NULL
""")
total_ref_orders = cursor.fetchone()[0]
print(f"   Total références uniques dans orders: {total_ref_orders}")

cursor.close()
conn.close()