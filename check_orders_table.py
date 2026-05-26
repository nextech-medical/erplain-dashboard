# check_orders_table.py
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
print("CONTENU DE LA TABLE ORDERS")
print("=" * 70)

# 1. Voir toutes les colonnes
cursor.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'orders'
    ORDER BY ordinal_position
""")
print("\n📋 Colonnes disponibles:")
for col in cursor.fetchall():
    print(f"   - {col[0]} ({col[1]})")

# 2. Voir les 5 premières lignes
cursor.execute("SELECT * FROM orders LIMIT 5")
col_names = [desc[0] for desc in cursor.description]
print(f"\n📊 Aperçu des données ({len(col_names)} colonnes):")
for row in cursor.fetchall():
    print("\n   Nouvelle commande:")
    for i, col in enumerate(col_names):
        if row[i] and str(row[i]) != '':
            print(f"      {col}: {row[i]}")

# 3. Voir les valeurs uniques de account_manager_name
cursor.execute("""
    SELECT DISTINCT account_manager_name 
    FROM orders 
    WHERE account_manager_name IS NOT NULL AND account_manager_name != ''
""")
print("\n👤 Gestionnaires dans orders:")
for row in cursor.fetchall():
    print(f"   - {row[0]}")

# 4. Compter les commandes
cursor.execute("SELECT COUNT(*) FROM orders")
print(f"\n📦 Total commandes: {cursor.fetchone()[0]}")

cursor.close()
conn.close()