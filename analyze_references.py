# analyze_references.py
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
print("🔍 ANALYSE DES RÉFÉRENCES EXTERNES")
print("=" * 80)

# 1. Voir les types de références dans NEXTECH Boutique
print("\n📋 TYPES DE RÉFÉRENCES DANS NEXTECH BOUTIQUE:")
query = """
    SELECT 
        reference_externe,
        COUNT(*) as nb
    FROM invoices
    WHERE gestionnaire = 'NEXTECH Boutique'
    AND reference_externe IS NOT NULL
    AND reference_externe != ''
    GROUP BY reference_externe
    ORDER BY nb DESC
    LIMIT 30
"""
df = pd.read_sql_query(query, conn)
print(df.to_string(index=False))

# 2. Voir les patterns des références (version corrigée sans apostrophe)
print("\n📊 PATTERNS DES RÉFÉRENCES:")
cursor = conn.cursor()

# Version avec double guillemets pour éviter l'apostrophe
cursor.execute("""
    SELECT 
        CASE 
            WHEN reference_externe ~ '^[0-9]{3}-[0-9]{7}-[0-9]{7}$' THEN 'Amazon (format 40X-XXXXXXX-XXXXXXX)'
            WHEN reference_externe LIKE 'PO-%' THEN 'Temu'
            WHEN reference_externe ~ '^[0-9]{4,8}$' THEN 'Nextech Boutique (numerique)'
            WHEN reference_externe LIKE 'PH%%' OR reference_externe LIKE 'DMS%%' THEN 'Appels doffres'
            ELSE 'Autre'
        END as pattern,
        COUNT(*) as nb_factures,
        ROUND(SUM(total)::numeric, 2) as ca
    FROM invoices
    WHERE reference_externe IS NOT NULL AND reference_externe != ''
    GROUP BY pattern
    ORDER BY nb_factures DESC
""")

for row in cursor.fetchall():
    print(f"   {row[0]}: {row[1]} factures, {row[2]:,.2f} €")

# 3. Vérifier les factures sans référence externe
cursor.execute("""
    SELECT COUNT(*) 
    FROM invoices
    WHERE (reference_externe IS NULL OR reference_externe = '')
    AND gestionnaire = 'NEXTECH Boutique'
""")
sans_ref = cursor.fetchone()[0]
print(f"\n⚠️ Factures NEXTECH Boutique SANS référence externe: {sans_ref}")

# 4. Afficher les 20 premières références pour voir les patterns
print("\n📋 APERÇU DES RÉFÉRENCES DANS INVOICES (20 premiers):")
cursor.execute("""
    SELECT reference_externe, gestionnaire, total
    FROM invoices
    WHERE reference_externe IS NOT NULL AND reference_externe != ''
    LIMIT 20
""")
for row in cursor.fetchall():
    print(f"   {row[0]:<30} | {row[1]:<20} | {row[2]:.2f} €")

# 5. Compter par pattern simple
print("\n📊 COMPTAGE SIMPLE PAR PATTERN:")
cursor.execute("""
    SELECT 
        COUNT(CASE WHEN reference_externe ~ '^[0-9]{3}-[0-9]{7}-[0-9]{7}$' THEN 1 END) as amazon,
        COUNT(CASE WHEN reference_externe LIKE 'PO-%' THEN 1 END) as temu,
        COUNT(CASE WHEN reference_externe ~ '^[0-9]{4,8}$' THEN 1 END) as boutique,
        COUNT(CASE WHEN reference_externe LIKE 'PH%%' OR reference_externe LIKE 'DMS%%' THEN 1 END) as appels_offres,
        COUNT(*) as total_avec_ref
    FROM invoices
    WHERE reference_externe IS NOT NULL AND reference_externe != ''
""")
row = cursor.fetchone()
print(f"   Amazon: {row[0]} factures")
print(f"   Temu: {row[1]} factures")
print(f"   Boutique (numerique): {row[2]} factures")
print(f"   Appels d'offres: {row[3]} factures")
print(f"   Total avec reference: {row[4]} factures")

cursor.close()
conn.close()