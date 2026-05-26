# fix_duplicates_and_references.py
"""
Script pour corriger les doublons de gestionnaires et lier les références manquantes
"""

import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def fix_duplicate_managers():
    """
    Corrige les doublons de gestionnaires (Amazon.fr vs Amazon .fr)
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 70)
    print("🔧 CORRECTION DES DOUBLONS DE GESTIONNAIRES")
    print("=" * 70)
    
    # 1. Voir les valeurs actuelles
    print("\n📊 Valeurs actuelles des gestionnaires:")
    cursor.execute("""
        SELECT gestionnaire, COUNT(*) as nb
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        GROUP BY gestionnaire
        ORDER BY nb DESC
    """)
    for row in cursor.fetchall():
        print(f"   '{row[0]}': {row[1]} factures")
    
    # 2. Normaliser Amazon
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Amazon.fr'
        WHERE gestionnaire LIKE 'Amazon%'
    """)
    print(f"\n   ✅ {cursor.rowcount} factures normalisées -> Amazon.fr")
    
    # 3. Normaliser Appels d'offres
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Appels d''offres'
        WHERE gestionnaire LIKE 'Appels%'
    """)
    print(f"   ✅ {cursor.rowcount} factures normalisées -> Appels d'offres")
    
    # 4. Normaliser NEXTECH Boutique
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'NEXTECH Boutique'
        WHERE gestionnaire LIKE 'NEXTECH%' AND gestionnaire NOT LIKE '%RELAIS%'
    """)
    print(f"   ✅ {cursor.rowcount} factures normalisées -> NEXTECH Boutique")
    
    # 5. Normaliser TEMU
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'TEMU FR'
        WHERE gestionnaire LIKE 'TEMU%'
    """)
    print(f"   ✅ {cursor.rowcount} factures normalisées -> TEMU FR")
    
    conn.commit()
    
    # 6. Résultat final
    print("\n📊 Valeurs après normalisation:")
    cursor.execute("""
        SELECT gestionnaire, COUNT(*) as nb
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        GROUP BY gestionnaire
        ORDER BY nb DESC
    """)
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]} factures")
    
    cursor.close()
    conn.close()


def link_missing_references():
    """
    Lie les références manquantes pour les factures NEXTECH Boutique
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 70)
    print("🔗 LIAISON DES RÉFÉRENCES MANQUANTES")
    print("=" * 70)
    
    # 1. Identifier les factures NEXTECH sans référence
    cursor.execute("""
        SELECT i.id, i.order_number, i.label, i.customer_name
        FROM invoices i
        WHERE i.gestionnaire = 'NEXTECH Boutique'
        AND (i.reference_externe IS NULL OR i.reference_externe = '')
        AND i.invoice_created >= '2026-01-01'
    """)
    missing = cursor.fetchall()
    print(f"\n📄 {len(missing)} factures NEXTECH sans référence")
    
    if missing:
        print("\n📋 Factures sans référence (10 premiers):")
        for row in missing[:10]:
            print(f"   {row[1]} | {row[2]} | {row[3]}")
    
    # 2. Lier par order_number avec la table orders
    cursor.execute("""
        UPDATE invoices i
        SET reference_externe = o.external_reference,
            bl_number = o.order_id
        FROM orders o
        WHERE i.gestionnaire = 'NEXTECH Boutique'
        AND (i.reference_externe IS NULL OR i.reference_externe = '')
        AND (i.order_number = o.order_id OR i.label = o.order_id)
        AND o.external_reference IS NOT NULL
    """)
    print(f"\n   ✅ {cursor.rowcount} références liées par order_number")
    
    # 3. Lier par correspondance avec le numéro (sans préfixe)
    cursor.execute("""
        UPDATE invoices i
        SET reference_externe = o.external_reference,
            bl_number = o.order_id
        FROM orders o
        WHERE i.gestionnaire = 'NEXTECH Boutique'
        AND (i.reference_externe IS NULL OR i.reference_externe = '')
        AND (SUBSTRING(i.order_number, 2) = o.order_id)
        AND o.external_reference IS NOT NULL
    """)
    print(f"   ✅ {cursor.rowcount} références liées par correspondance sans préfixe")
    
    # 4. Lier par email
    cursor.execute("""
        UPDATE invoices i
        SET reference_externe = o.external_reference,
            gestionnaire = COALESCE(o.account_manager_name, 'NEXTECH Boutique')
        FROM orders o
        WHERE i.gestionnaire = 'NEXTECH Boutique'
        AND (i.reference_externe IS NULL OR i.reference_externe = '')
        AND i.customer_email = o.customer_email
        AND o.external_reference IS NOT NULL
    """)
    print(f"   ✅ {cursor.rowcount} références liées par email")
    
    conn.commit()
    
    # 5. Vérifier le résultat
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as avec_ref
        FROM invoices
        WHERE gestionnaire = 'NEXTECH Boutique'
        AND invoice_created >= '2026-01-01'
    """)
    row = cursor.fetchone()
    print(f"\n📊 Résultat: {row[1]}/{row[0]} factures NEXTECH avec référence")
    
    cursor.close()
    conn.close()


def link_all_missing_references():
    """
    Lie toutes les références manquantes pour tous les gestionnaires
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 70)
    print("🔗 LIAISON DE TOUTES LES RÉFÉRENCES MANQUANTES")
    print("=" * 70)
    
    # Compter les factures sans référence
    cursor.execute("""
        SELECT COUNT(*)
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        AND (reference_externe IS NULL OR reference_externe = '')
    """)
    missing_total = cursor.fetchone()[0]
    print(f"\n📄 {missing_total} factures sans référence externe")
    
    # Lier par order_number
    cursor.execute("""
        UPDATE invoices i
        SET reference_externe = o.external_reference,
            gestionnaire = COALESCE(o.account_manager_name, i.gestionnaire)
        FROM orders o
        WHERE (i.order_number = o.order_id OR i.label = o.order_id)
        AND (i.reference_externe IS NULL OR i.reference_externe = '')
        AND o.external_reference IS NOT NULL
    """)
    print(f"   ✅ {cursor.rowcount} références liées par order_number")
    
    # Lier par email
    cursor.execute("""
        UPDATE invoices i
        SET reference_externe = o.external_reference,
            gestionnaire = COALESCE(o.account_manager_name, i.gestionnaire)
        FROM orders o
        WHERE i.customer_email = o.customer_email
        AND (i.reference_externe IS NULL OR i.reference_externe = '')
        AND o.external_reference IS NOT NULL
    """)
    print(f"   ✅ {cursor.rowcount} références liées par email")
    
    conn.commit()
    
    # Résultat final
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as avec_ref
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
    """)
    row = cursor.fetchone()
    print(f"\n📊 Résultat final: {row[1]}/{row[0]} factures avec référence externe")
    
    cursor.close()
    conn.close()


def show_repartition():
    """Affiche la répartition finale des gestionnaires"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    print("\n" + "=" * 70)
    print("📊 RÉPARTITION FINALE DES GESTIONNAIRES")
    print("=" * 70)
    
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
    conn.close()
    
    print(df.to_string(index=False))
    return df


if __name__ == "__main__":
    import sys
    import pandas as pd
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--fix-duplicates":
            fix_duplicate_managers()
        elif sys.argv[1] == "--link-nexttech":
            link_missing_references()
        elif sys.argv[1] == "--link-all":
            link_all_missing_references()
        elif sys.argv[1] == "--show":
            show_repartition()
        elif sys.argv[1] == "--all":
            fix_duplicate_managers()
            link_all_missing_references()
            show_repartition()
        else:
            print("Usage: python fix_duplicates_and_references.py [--fix-duplicates] [--link-nexttech] [--link-all] [--show] [--all]")
    else:
        fix_duplicate_managers()
        link_all_missing_references()
        show_repartition()