# clean_managers.py
import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cursor = conn.cursor()

print("\n" + "=" * 80)
print("🔧 NETTOYAGE DES GESTIONNAIRES")
print("=" * 80)

# 1. Fusionner les deux catégories Appels d'offres
print("\n📌 FUSION DES APPELS D'OFFRES:")
cursor.execute("""
    UPDATE invoices 
    SET gestionnaire = 'Appels d''offres'
    WHERE gestionnaire = 'Appels doffres'
""")
print(f"   ✅ {cursor.rowcount} factures fusionnées")

# 2. Vérifier et standardiser les noms
print("\n📌 STANDARDISATION:")
cursor.execute("""
    UPDATE invoices 
    SET gestionnaire = 'Amazon .fr'
    WHERE gestionnaire = 'Amazon'
""")
print(f"   ✅ Amazon: {cursor.rowcount}")

cursor.execute("""
    UPDATE invoices 
    SET gestionnaire = 'TEMU FR'
    WHERE gestionnaire = 'Temu'
""")
print(f"   ✅ Temu: {cursor.rowcount}")

cursor.execute("""
    UPDATE invoices 
    SET gestionnaire = 'NEXTECH Boutique'
    WHERE gestionnaire = 'Boutique' OR gestionnaire = 'Nextech Boutique'
""")
print(f"   ✅ Boutique: {cursor.rowcount}")

conn.commit()

# 3. Afficher le résultat final
print("\n" + "=" * 80)
print("📊 RÉSULTAT FINAL APRÈS NETTOYAGE")
print("=" * 80)

cursor.execute("""
    SELECT 
        gestionnaire,
        COUNT(*) as nb_factures,
        ROUND(SUM(total)::numeric, 2) as ca_total,
        ROUND(AVG(total)::numeric, 2) as panier_moyen,
        COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as avec_ref
    FROM invoices
    WHERE invoice_created >= '2026-01-01'
    GROUP BY gestionnaire
    ORDER BY ca_total DESC
""")

for row in cursor.fetchall():
    print(f"   {row[0]:<20}: {row[1]:>5} factures, {row[2]:>12,.2f} € (moy: {row[3]:.2f} €) - {row[4]} avec réf")

cursor.close()
conn.close()

print("\n" + "=" * 80)
print("✅ NETTOYAGE TERMINÉ")
print("=" * 80)