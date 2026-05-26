# fix_all_data.py
"""
Script complet pour corriger les fournisseurs et gestionnaires dans toutes les tables
"""

import psycopg2
import pandas as pd
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def fix_all():
    """Corrige toutes les données"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 70)
    print("🔧 CORRECTION COMPLÈTE DES DONNÉES")
    print("=" * 70)
    
    # =========================================================
    # 1. CRÉER LES COLONNES MANQUANTES
    # =========================================================
    print("\n1️⃣ Création des colonnes manquantes...")
    
    # Dans invoices
    columns_to_add = [
        ("fournisseur", "TEXT"),
        ("gestionnaire", "VARCHAR(100)"),
        ("reference_externe", "TEXT"),
        ("bl_number", "TEXT"),
    ]
    
    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE invoices ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
            print(f"   ✅ Colonne '{col_name}' ajoutée")
        except Exception as e:
            print(f"   ⚠️ {col_name}: {e}")
    
    # Dans sales_orders (si nécessaire)
    cursor.execute("""
        ALTER TABLE sales_orders 
        ADD COLUMN IF NOT EXISTS supplier_name VARCHAR(255),
        ADD COLUMN IF NOT EXISTS supplier_id VARCHAR(100)
    """)
    
    conn.commit()
    
    # =========================================================
    # 2. METTRE À JOUR LES GESTIONNAIRES DEPUIS SALES_ORDERS
    # =========================================================
    print("\n2️⃣ Mise à jour des gestionnaires...")
    
    # Par order_number
    cursor.execute("""
        UPDATE invoices i
        SET gestionnaire = so.account_manager_name
        FROM sales_orders so
        WHERE i.order_number = so.order_number
        AND so.account_manager_name IS NOT NULL
        AND so.account_manager_name != ''
        AND (i.gestionnaire IS NULL OR i.gestionnaire = '' OR i.gestionnaire = 'Direct')
    """)
    print(f"   ✅ {cursor.rowcount} factures mises à jour par order_number")
    
    # Par label
    cursor.execute("""
        UPDATE invoices i
        SET gestionnaire = so.account_manager_name
        FROM sales_orders so
        WHERE i.label = so.order_number
        AND so.account_manager_name IS NOT NULL
        AND so.account_manager_name != ''
        AND (i.gestionnaire IS NULL OR i.gestionnaire = '' OR i.gestionnaire = 'Direct')
    """)
    print(f"   ✅ {cursor.rowcount} factures mises à jour par label")
    
    # Par référence externe
    cursor.execute("""
        UPDATE invoices i
        SET gestionnaire = so.account_manager_name
        FROM sales_orders so
        WHERE i.reference_externe = so.external_reference
        AND so.account_manager_name IS NOT NULL
        AND so.account_manager_name != ''
        AND (i.gestionnaire IS NULL OR i.gestionnaire = '' OR i.gestionnaire = 'Direct')
    """)
    print(f"   ✅ {cursor.rowcount} factures mises à jour par référence")
    
    # Par email
    cursor.execute("""
        UPDATE invoices i
        SET gestionnaire = so.account_manager_name
        FROM sales_orders so
        WHERE i.customer_email = so.customer_email
        AND so.account_manager_name IS NOT NULL
        AND so.account_manager_name != ''
        AND (i.gestionnaire IS NULL OR i.gestionnaire = '' OR i.gestionnaire = 'Direct')
    """)
    print(f"   ✅ {cursor.rowcount} factures mises à jour par email")
    
    conn.commit()
    
    # =========================================================
    # 3. DÉTECTION AUTOMATIQUE DES GESTIONNAIRES
    # =========================================================
    print("\n3️⃣ Détection automatique des gestionnaires...")
    
    # Amazon par référence
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Amazon.fr'
        WHERE (gestionnaire IS NULL OR gestionnaire = '' OR gestionnaire = 'Direct')
        AND reference_externe IS NOT NULL
        AND reference_externe ~ '^[0-9]{3}-[0-9]{7}-[0-9]{7}$'
    """)
    print(f"   ✅ {cursor.rowcount} factures -> Amazon.fr")
    
    # Temu par référence
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'TEMU FR'
        WHERE (gestionnaire IS NULL OR gestionnaire = '' OR gestionnaire = 'Direct')
        AND reference_externe LIKE 'PO-%'
    """)
    print(f"   ✅ {cursor.rowcount} factures -> TEMU FR")
    
    # Appels d'offres
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Appels d''offres'
        WHERE (gestionnaire IS NULL OR gestionnaire = '' OR gestionnaire = 'Direct')
        AND customer_name IS NOT NULL
        AND (customer_name LIKE 'CH %' 
             OR customer_name LIKE 'CENTRE HOSPITALIER%'
             OR customer_name LIKE 'HOPITAL%'
             OR customer_name LIKE 'CLINIQUE%'
             OR customer_name LIKE 'UGAP%')
    """)
    print(f"   ✅ {cursor.rowcount} factures -> Appels d'offres")
    
    # NEXTECH Boutique
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'NEXTECH Boutique'
        WHERE (gestionnaire IS NULL OR gestionnaire = '' OR gestionnaire = 'Direct')
        AND customer_email = 'roua.faroukh@nextechmedical.fr'
    """)
    print(f"   ✅ {cursor.rowcount} factures -> NEXTECH Boutique")
    
    # Echantillons
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Echantillons'
        WHERE (gestionnaire IS NULL OR gestionnaire = '' OR gestionnaire = 'Direct')
        AND total = 0
    """)
    print(f"   ✅ {cursor.rowcount} factures -> Echantillons")
    
    # Direct par défaut
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Direct'
        WHERE gestionnaire IS NULL OR gestionnaire = '' OR gestionnaire = 'Non spécifié'
    """)
    print(f"   ✅ {cursor.rowcount} factures -> Direct")
    
    conn.commit()
    
    # =========================================================
    # 4. METTRE À JOUR LES FOURNISSEURS DEPUIS LES PRODUITS
    # =========================================================
    print("\n4️⃣ Mise à jour des fournisseurs...")
    
    # Depuis order_lines (commandes)
    cursor.execute("""
        UPDATE invoices i
        SET fournisseur = ol.supplier_name
        FROM order_lines ol
        JOIN sales_orders so ON so.id = ol.order_id
        WHERE (i.order_number = so.order_number OR i.label = so.order_number)
        AND ol.supplier_name IS NOT NULL
        AND ol.supplier_name != ''
        AND (i.fournisseur IS NULL OR i.fournisseur = '' OR i.fournisseur = 'Non spécifié')
    """)
    print(f"   ✅ {cursor.rowcount} factures mises à jour depuis order_lines")
    
    # Depuis invoice_lines par SKU
    cursor.execute("""
        UPDATE invoices i
        SET fournisseur = p.supplier_name
        FROM invoice_lines il
        JOIN products p ON p.sku = il.product_sku
        WHERE i.id = il.invoice_id
        AND p.supplier_name IS NOT NULL
        AND p.supplier_name != ''
        AND (i.fournisseur IS NULL OR i.fournisseur = '' OR i.fournisseur = 'Non spécifié')
    """)
    print(f"   ✅ {cursor.rowcount} factures mises à jour depuis products")
    
    # Détection par marque dans product_label
    brand_mapping = {
        'ZARYS': 'ZARYS',
        'ABENA': 'Abena',
        'ONTEX': 'Ontex',
        'HARTMANN': 'Hartmann',
        'CHIRANA': 'Chirana',
        'BASTOS': 'Bastos',
        'COMED': 'Comed',
        'TENA': 'Tena',
        'SIDAPHARM': 'Sidapharm',
        'PHARMAPLAST': 'Pharmaplast',
        'VITREX': 'Vitrex',
        'BD': 'BD Medical',
        'FL MEDICAL': 'FL Medical',
        'MOLTEX': 'Moltex',
        'BAMBO': 'Bambo Nature'
    }
    
    updated = 0
    for brand, supplier in brand_mapping.items():
        cursor.execute("""
            UPDATE invoices i
            SET fournisseur = %s
            FROM invoice_lines il
            WHERE i.id = il.invoice_id
            AND UPPER(il.product_label) LIKE %s
            AND (i.fournisseur IS NULL OR i.fournisseur = '' OR i.fournisseur = 'Non spécifié')
        """, (supplier, f'%{brand}%'))
        updated += cursor.rowcount
    
    print(f"   ✅ {updated} factures mises à jour par détection de marque")
    
    # Non spécifié par défaut
    cursor.execute("""
        UPDATE invoices 
        SET fournisseur = 'Non spécifié'
        WHERE fournisseur IS NULL OR fournisseur = '' OR fournisseur = 'None'
    """)
    print(f"   ✅ {cursor.rowcount} factures marquées 'Non spécifié'")
    
    conn.commit()
    
    # =========================================================
    # 5. METTRE À JOUR LES RÉFÉRENCES EXTERNES
    # =========================================================
    print("\n5️⃣ Mise à jour des références externes...")
    
    cursor.execute("""
        UPDATE invoices i
        SET reference_externe = so.external_reference
        FROM sales_orders so
        WHERE (i.order_number = so.order_number OR i.label = so.order_number)
        AND so.external_reference IS NOT NULL
        AND so.external_reference != ''
        AND (i.reference_externe IS NULL OR i.reference_externe = '')
    """)
    print(f"   ✅ {cursor.rowcount} références mises à jour")
    
    conn.commit()
    
    # =========================================================
    # 6. STATISTIQUES FINALES
    # =========================================================
    print("\n" + "=" * 70)
    print("📊 STATISTIQUES FINALES")
    print("=" * 70)
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN gestionnaire IS NOT NULL AND gestionnaire NOT IN ('Direct', 'Non spécifié') THEN 1 END) as avec_gestionnaire,
            COUNT(CASE WHEN fournisseur IS NOT NULL AND fournisseur != 'Non spécifié' THEN 1 END) as avec_fournisseur,
            COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as avec_reference
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
    """)
    stats = cursor.fetchone()
    
    print(f"\n📄 Factures 2026:")
    print(f"   - Total: {stats[0]}")
    print(f"   - Avec gestionnaire: {stats[1]}")
    print(f"   - Avec fournisseur: {stats[2]}")
    print(f"   - Avec référence externe: {stats[3]}")
    
    # Détail par gestionnaire
    cursor.execute("""
        SELECT gestionnaire, COUNT(*) as nb, ROUND(SUM(total)::numeric, 2) as ca
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        GROUP BY gestionnaire
        ORDER BY nb DESC
    """)
    print(f"\n📱 RÉPARTITION PAR GESTIONNAIRE:")
    for row in cursor.fetchall():
        print(f"   - {row[0]}: {row[1]} factures, {row[2]:,.2f} €")
    
    # Top fournisseurs
    cursor.execute("""
        SELECT fournisseur, COUNT(*) as nb, ROUND(SUM(total)::numeric, 2) as ca
        FROM invoices
        WHERE fournisseur IS NOT NULL AND fournisseur != 'Non spécifié'
        AND invoice_created >= '2026-01-01'
        GROUP BY fournisseur
        ORDER BY ca DESC
        LIMIT 10
    """)
    print(f"\n🏭 TOP FOURNISSEURS:")
    for row in cursor.fetchall():
        print(f"   - {row[0]}: {row[1]} factures, {row[2]:,.2f} €")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 70)
    print("✅ CORRECTION TERMINÉE")
    print("=" * 70)


def check_data():
    """Vérifie l'état des données"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    print("\n" + "=" * 70)
    print("🔍 VÉRIFICATION DES DONNÉES")
    print("=" * 70)
    
    # Gestionnaires dans sales_orders
    df_so = pd.read_sql_query("""
        SELECT DISTINCT account_manager_name, COUNT(*) as nb
        FROM sales_orders
        WHERE account_manager_name IS NOT NULL AND account_manager_name != ''
        GROUP BY account_manager_name
        ORDER BY nb DESC
    """, conn)
    
    print("\n📋 Gestionnaires dans sales_orders:")
    print(df_so.to_string(index=False))
    
    # Gestionnaires dans invoices
    df_inv = pd.read_sql_query("""
        SELECT gestionnaire, COUNT(*) as nb
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        GROUP BY gestionnaire
        ORDER BY nb DESC
    """, conn)
    
    print("\n📋 Gestionnaires dans invoices:")
    print(df_inv.to_string(index=False))
    
    # Fournisseurs dans invoices
    df_four = pd.read_sql_query("""
        SELECT fournisseur, COUNT(*) as nb
        FROM invoices
        WHERE fournisseur IS NOT NULL AND fournisseur != 'Non spécifié'
        AND invoice_created >= '2026-01-01'
        GROUP BY fournisseur
        ORDER BY nb DESC
        LIMIT 15
    """, conn)
    
    print("\n📋 Fournisseurs dans invoices:")
    print(df_four.to_string(index=False))
    
    conn.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--check":
            check_data()
        elif sys.argv[1] == "--fix":
            fix_all()
        else:
            print("Usage: python fix_all_data.py [--check] [--fix]")
    else:
        fix_all()