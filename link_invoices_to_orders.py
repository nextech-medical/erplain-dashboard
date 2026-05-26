# link_invoices_to_orders.py
"""
Lie les factures existantes aux commandes et met à jour les gestionnaires
"""

import psycopg2
import re
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def link_and_update():
    """Lie les factures aux commandes et met à jour les gestionnaires"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 80)
    print("🔗 LIAISON FACTURES → COMMANDES")
    print("=" * 80)
    
    # 1. Voir combien de commandes on a dans orders
    cursor.execute("SELECT COUNT(*) FROM orders")
    total_orders = cursor.fetchone()[0]
    print(f"\n📦 Commandes dans orders: {total_orders}")
    
    cursor.execute("SELECT COUNT(*) FROM invoices WHERE invoice_created >= '2026-01-01'")
    total_invoices = cursor.fetchone()[0]
    print(f"📄 Factures dans invoices: {total_invoices}")
    
    # 2. Lier par numéro de commande
    print("\n📌 LIAISON PAR ORDER_NUMBER:")
    
    # Voir les correspondances possibles
    cursor.execute("""
        SELECT COUNT(*)
        FROM invoices i
        JOIN orders o ON i.order_number = o.order_id
    """)
    matched = cursor.fetchone()[0]
    print(f"   Correspondances order_number = order_id: {matched}")
    
    cursor.execute("""
        SELECT COUNT(*)
        FROM invoices i
        JOIN orders o ON i.label = o.order_id
    """)
    matched2 = cursor.fetchone()[0]
    print(f"   Correspondances label = order_id: {matched2}")
    
    cursor.execute("""
        SELECT COUNT(*)
        FROM invoices i
        JOIN orders o ON i.order_number = o.label
    """)
    matched3 = cursor.fetchone()[0]
    print(f"   Correspondances order_number = label: {matched3}")
    
    # 3. Mettre à jour les gestionnaires depuis orders
    print("\n📌 MISE À JOUR DES GESTIONNAIRES:")
    
    # Par order_number
    cursor.execute("""
        UPDATE invoices i
        SET gestionnaire = o.account_manager_name,
            reference_externe = COALESCE(i.reference_externe, o.external_reference)
        FROM orders o
        WHERE i.order_number = o.order_id
        AND o.account_manager_name IS NOT NULL
    """)
    print(f"   ✅ {cursor.rowcount} factures mises à jour (order_number)")
    
    # Par label
    cursor.execute("""
        UPDATE invoices i
        SET gestionnaire = o.account_manager_name,
            reference_externe = COALESCE(i.reference_externe, o.external_reference)
        FROM orders o
        WHERE i.label = o.order_id
        AND o.account_manager_name IS NOT NULL
        AND (i.gestionnaire IS NULL OR i.gestionnaire = 'NEXTECH Boutique')
    """)
    print(f"   ✅ {cursor.rowcount} factures mises à jour (label)")
    
    conn.commit()
    
    # 4. Afficher les résultats
    print("\n📊 RÉSULTATS APRÈS LIAISON:")
    cursor.execute("""
        SELECT 
            gestionnaire,
            COUNT(*) as nb,
            ROUND(SUM(total)::numeric, 2) as ca,
            COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as avec_ref
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        GROUP BY gestionnaire
        ORDER BY ca DESC
    """)
    
    for row in cursor.fetchall():
        print(f"   {row[0]:<20}: {row[1]:>5} factures, {row[2]:>12,.2f} € ({row[3]} avec réf)")
    
    cursor.close()
    conn.close()

def show_missing_matches():
    """Affiche les factures qui n'ont pas de correspondance"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    print("\n" + "=" * 80)
    print("🔍 FACTURES SANS CORRESPONDANCE DANS ORDERS")
    print("=" * 80)
    
    query = """
        SELECT 
            i.order_number,
            i.label,
            i.customer_name,
            i.total,
            i.gestionnaire
        FROM invoices i
        LEFT JOIN orders o ON i.order_number = o.order_id OR i.label = o.order_id
        WHERE i.invoice_created >= '2026-01-01'
        AND o.id IS NULL
        LIMIT 20
    """
    
    import pandas as pd
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df.empty:
        print(df.to_string(index=False))
        print(f"\n⚠️ {len(df)} factures sans correspondance")
    else:
        print("✅ Toutes les factures ont une correspondance")
    
    return df

def fix_remaining_manually():
    """Corrige manuellement les gestionnaires restants"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 80)
    print("🔧 CORRECTION MANUELLE DES GESTIONNAIRES RESTANTS")
    print("=" * 80)
    
    # 1. Amazon par pattern (même sans correspondance)
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Amazon .fr'
        WHERE reference_externe ~ '^[0-9]{3}-[0-9]{7}-[0-9]{7}$'
        AND (gestionnaire IS NULL OR gestionnaire = 'NEXTECH Boutique')
    """)
    print(f"   ✅ Amazon par pattern: {cursor.rowcount}")
    
    # 2. Temu par pattern
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'TEMU FR'
        WHERE reference_externe LIKE 'PO-%'
        AND (gestionnaire IS NULL OR gestionnaire = 'NEXTECH Boutique')
    """)
    print(f"   ✅ Temu par pattern: {cursor.rowcount}")
    
    # 3. Appels d'offres par pattern
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Appels d''offres'
        WHERE (reference_externe LIKE 'PH%' 
            OR reference_externe LIKE 'DMS%'
            OR reference_externe LIKE 'BS%'
            OR reference_externe LIKE '2026/%')
        AND (gestionnaire IS NULL OR gestionnaire = 'NEXTECH Boutique')
    """)
    print(f"   ✅ Appels d'offres par pattern: {cursor.rowcount}")
    
    conn.commit()
    
    # Résultat final
    cursor.execute("""
        SELECT 
            gestionnaire,
            COUNT(*) as nb,
            ROUND(SUM(total)::numeric, 2) as ca
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        GROUP BY gestionnaire
        ORDER BY ca DESC
    """)
    
    print("\n📊 DISTRIBUTION FINALE:")
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]} factures, {row[2]:,.2f} €")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--show":
            show_missing_matches()
        elif sys.argv[1] == "--fix":
            fix_remaining_manually()
        else:
            print("Usage: python link_invoices_to_orders.py [--show] [--fix]")
    else:
        link_and_update()
        print("\n" + "=" * 80)
        print("Pour voir les factures sans correspondance, lancez:")
        print("python link_invoices_to_orders.py --show")
        print("=" * 80)