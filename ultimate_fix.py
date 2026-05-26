# ultimate_fix.py
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
print("SOLUTION DÉFINITIVE - LIAISON FACTURES/COMMANDES")
print("=" * 70)

# 1. Voir la structure complète des deux tables
print("\n1. ANALYSE DES TABLES")

# Colonnes de invoices
cursor.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'invoices'
    ORDER BY ordinal_position
""")
print("\n   Colonnes INVOICES:")
for col in cursor.fetchall():
    print(f"      - {col[0]} ({col[1]})")

# Colonnes de orders
cursor.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'orders'
    ORDER BY ordinal_position
""")
print("\n   Colonnes ORDERS:")
for col in cursor.fetchall():
    print(f"      - {col[0]} ({col[1]})")

# 2. Créer une nouvelle colonne dans invoices pour stocker le gestionnaire
print("\n2. CRÉATION DE LA COLONNE GESTIONNAIRE DANS INVOICES")

try:
    cursor.execute("""
        ALTER TABLE invoices 
        ADD COLUMN IF NOT EXISTS account_manager VARCHAR(255)
    """)
    conn.commit()
    print("   ✅ Colonne 'account_manager' ajoutée")
except Exception as e:
    print(f"   ⚠️ {e}")

# 3. Remplir manuellement les gestionnaires (solution pragmatique)
print("\n3. REMPLISSAGE MANUEL DES GESTIONNAIRES")

# Récupérer les correspondances depuis orders
cursor.execute("""
    SELECT DISTINCT order_id, account_manager_name 
    FROM orders 
    WHERE account_manager_name IS NOT NULL AND account_manager_name != ''
""")
order_managers = cursor.fetchall()
print(f"   📋 {len(order_managers)} commandes avec gestionnaire dans orders")

# Récupérer les factures sans gestionnaire
cursor.execute("""
    SELECT id, label, order_number, reference_externe 
    FROM invoices 
    WHERE invoice_created IS NOT NULL 
    LIMIT 20
""")
invoices_sample = cursor.fetchall()

print("\n   Échantillon des factures:")
for inv in invoices_sample[:10]:
    print(f"      ID: {inv[0]}, Label: {inv[1]}, Order: {inv[2]}, Ref: {inv[3]}")

# 4. Mise à jour basée sur des règles
print("\n4. MISE À JOUR AUTOMATIQUE")

# Règle 1: Si le order_number commence par "S", c'est probablement une commande directe
cursor.execute("""
    UPDATE invoices 
    SET account_manager = 'Direct'
    WHERE order_number LIKE 'S%' 
      AND account_manager IS NULL
      AND invoice_created IS NOT NULL
""")
updated = cursor.rowcount
print(f"   ✅ {updated} factures marquées 'Direct' (order_number S...)")

# Règle 2: Si le order_number contient "BC", c'est une commande externe
cursor.execute("""
    UPDATE invoices 
    SET account_manager = 'Plateforme externe'
    WHERE order_number LIKE 'BC%' 
      AND account_manager IS NULL
      AND invoice_created IS NOT NULL
""")
updated = cursor.rowcount
print(f"   ✅ {updated} factures marquées 'Plateforme externe' (order_number BC...)")

# Règle 3: Correspondance par external_reference
cursor.execute("""
    UPDATE invoices 
    SET account_manager = orders.account_manager_name
    FROM orders 
    WHERE invoices.reference_externe = orders.external_reference
      AND orders.external_reference IS NOT NULL
      AND orders.external_reference != ''
      AND invoices.account_manager IS NULL
      AND invoices.reference_externe IS NOT NULL
      AND invoices.reference_externe != ''
""")
updated = cursor.rowcount
print(f"   ✅ {updated} factures mises à jour (correspondance external_reference)")

# 5. Si aucune correspondance, créer une table de mapping manuelle
print("\n5. CRÉATION D'UNE TABLE DE MAPPING MANUELLE")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS invoice_order_mapping (
        invoice_id VARCHAR(100) PRIMARY KEY,
        order_id VARCHAR(100),
        account_manager VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()
print("   ✅ Table invoice_order_mapping créée")

# 6. Statistiques finales
print("\n6. STATISTIQUES FINALES")

cursor.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(account_manager) as avec_gestionnaire,
        COUNT(CASE WHEN account_manager = 'Direct' THEN 1 END) as direct,
        COUNT(CASE WHEN account_manager NOT IN ('Direct', 'Plateforme externe') THEN 1 END) as externe
    FROM invoices
    WHERE invoice_created IS NOT NULL
""")
stats = cursor.fetchone()
print(f"\n   Total factures: {stats[0]}")
print(f"   Avec gestionnaire: {stats[1]}")
print(f"   - Direct: {stats[2]}")
print(f"   - Externe: {stats[3]}")

# Afficher les gestionnaires trouvés
cursor.execute("""
    SELECT account_manager, COUNT(*) 
    FROM invoices 
    WHERE account_manager IS NOT NULL 
      AND account_manager NOT IN ('Direct', 'Plateforme externe')
    GROUP BY account_manager
    ORDER BY COUNT(*) DESC
""")
managers = cursor.fetchall()
if managers:
    print("\n   Gestionnaires trouvés:")
    for m in managers:
        print(f"      - {m[0]}: {m[1]} factures")
else:
    print("\n   ⚠️ Aucun gestionnaire externe trouvé")
    print("   💡 Vous devez créer manuellement les correspondances")

conn.commit()
cursor.close()
conn.close()

print("\n" + "=" * 70)
print("✅ TERMINÉ")
print("=" * 70)
print("\n📌 PROCHAINES ÉTAPES:")
print("   1. Lancez maintenant le dashboard")
print("   2. Les gestionnaires 'Direct' et 'Plateforme externe' sont créés")
print("   3. Pour des gestionnaires spécifiques (Amazon, TEMU),")
print("      vous devez lier manuellement les factures aux commandes")