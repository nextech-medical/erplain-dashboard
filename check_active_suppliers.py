# check_active_suppliers.py
import psycopg2
import pandas as pd
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

# Fournisseurs avec ventes
df = pd.read_sql_query("""
    SELECT 
        fournisseur, 
        COUNT(DISTINCT id) as nb_factures,
        SUM(total) as ca_total,
        SUM(quantity) as nb_produits
    FROM invoices 
    WHERE fournisseur != 'Non spécifié'
    GROUP BY fournisseur 
    ORDER BY ca_total DESC
""", conn)

print("="*60)
print("📊 FOURNISSEURS AVEC VENTES")
print("="*60)
for _, row in df.iterrows():
    print(f"\n🏭 {row['fournisseur']}")
    print(f"   📄 Factures: {row['nb_factures']}")
    print(f"   💰 CA: {row['ca_total']:.2f} €")
    print(f"   📦 Produits: {row['nb_produits']:.0f}")

print(f"\n✅ Total: {len(df)} fournisseurs actifs sur 26")

conn.close()