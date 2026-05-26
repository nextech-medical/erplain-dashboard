# force_fix_managers.py
"""
Force la correction de TOUS les gestionnaires en fonction des références externes
"""

import psycopg2
import re
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def force_fix_all():
    """Force la correction de tous les gestionnaires"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 80)
    print("🔧 FORCE LA CORRECTION DE TOUS LES GESTIONNAIRES")
    print("=" * 80)
    
    # 1. Voir la situation AVANT
    print("\n📊 AVANT CORRECTION:")
    cursor.execute("""
        SELECT gestionnaire, COUNT(*) as nb, ROUND(SUM(total)::numeric, 2) as ca
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        GROUP BY gestionnaire
        ORDER BY ca DESC
    """)
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]} factures, {row[2]:,.2f} €")
    
    # 2. Forcer la correction basée sur reference_externe
    print("\n📌 FORCE CORRECTION PAR RÉFÉRENCE EXTERNE:")
    
    # Amazon: pattern 3 chiffres - 7 chiffres - 7 chiffres
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Amazon .fr'
        WHERE reference_externe ~ '^[0-9]{3}-[0-9]{7}-[0-9]{7}$'
    """)
    print(f"   ✅ Amazon .fr: {cursor.rowcount} factures")
    
    # Temu: PO-...
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'TEMU FR'
        WHERE reference_externe LIKE 'PO-%'
    """)
    print(f"   ✅ TEMU FR: {cursor.rowcount} factures")
    
    # Appels d'offres
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Appels d''offres'
        WHERE reference_externe LIKE 'PH%' 
           OR reference_externe LIKE 'DMS%'
           OR reference_externe LIKE 'BS%'
           OR reference_externe LIKE '2026/%'
           OR reference_externe LIKE 'FC%'
           OR reference_externe LIKE 'BC%'
    """)
    print(f"   ✅ Appels d''offres: {cursor.rowcount} factures")
    
    # 3. Pour les factures SANS référence externe, garder NEXTECH Boutique
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'NEXTECH Boutique'
        WHERE (reference_externe IS NULL OR reference_externe = '')
        AND gestionnaire NOT IN ('Amazon .fr', 'TEMU FR', 'Appels d''offres')
    """)
    print(f"   ✅ NEXTECH Boutique (sans ref): {cursor.rowcount} factures")
    
    # 4. Pour les factures AVEC référence mais non catégorisées
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'NEXTECH Boutique'
        WHERE reference_externe IS NOT NULL 
        AND reference_externe != ''
        AND gestionnaire IS NULL
    """)
    print(f"   ✅ NEXTECH Boutique (avec ref non catégorisée): {cursor.rowcount} factures")
    
    conn.commit()
    
    # 5. Voir la situation APRÈS
    print("\n📊 APRÈS CORRECTION:")
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
    
    total_factures = 0
    total_ca = 0
    for row in cursor.fetchall():
        total_factures += row[1]
        total_ca += row[2]
        print(f"   {row[0]:<20}: {row[1]:>5} factures, {row[2]:>12,.2f} € ({row[3]} avec réf)")
    
    print(f"\n   {'TOTAL':<20}: {total_factures:>5} factures, {total_ca:>12,.2f} €")
    
    cursor.close()
    conn.close()

def show_detailed_amazon_temu():
    """Affiche le détail des factures Amazon et Temu"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    print("\n" + "=" * 80)
    print("📋 DÉTAIL DES FACTURES AMAZON ET TEMU")
    print("=" * 80)
    
    query = """
        SELECT 
            order_number,
            reference_externe,
            gestionnaire,
            total,
            customer_name
        FROM invoices
        WHERE gestionnaire IN ('Amazon .fr', 'TEMU FR')
        AND invoice_created >= '2026-01-01'
        ORDER BY total DESC
    """
    
    import pandas as pd
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df.empty:
        print(f"\nTotal: {len(df)} factures")
        print(df.to_string(index=False))
    else:
        print("\n⚠️ Aucune facture Amazon ou Temu trouvée")
    
    return df

def check_references_patterns():
    """Vérifie tous les patterns de références existants"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 80)
    print("🔍 ANALYSE DE TOUTES LES RÉFÉRENCES EXTERNES")
    print("=" * 80)
    
    # Compter par pattern
    cursor.execute("""
        SELECT 
            CASE 
                WHEN reference_externe ~ '^[0-9]{3}-[0-9]{7}-[0-9]{7}$' THEN 'Amazon'
                WHEN reference_externe LIKE 'PO-%' THEN 'Temu'
                WHEN reference_externe LIKE 'PH%' OR reference_externe LIKE 'DMS%' OR reference_externe LIKE 'BS%' THEN 'Appels doffres'
                WHEN reference_externe ~ '^[0-9]+$' AND LENGTH(reference_externe) >= 4 THEN 'Numeric (Boutique)'
                WHEN reference_externe IS NULL OR reference_externe = '' THEN 'Sans reference'
                ELSE 'Autre'
            END as type_ref,
            COUNT(*) as nb,
            ROUND(SUM(total)::numeric, 2) as ca
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        GROUP BY type_ref
        ORDER BY nb DESC
    """)
    
    print("\n📊 RÉPARTITION PAR TYPE DE RÉFÉRENCE:")
    for row in cursor.fetchall():
        print(f"   {row[0]:<25}: {row[1]:>5} factures, {row[2]:>12,.2f} €")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--check":
            check_references_patterns()
        elif sys.argv[1] == "--details":
            show_detailed_amazon_temu()
        elif sys.argv[1] == "--all":
            check_references_patterns()
            force_fix_all()
            show_detailed_amazon_temu()
        else:
            print("""
Usage: python force_fix_managers.py [OPTION]

Options:
  --check     Analyse tous les patterns de références
  --details   Affiche le détail des factures Amazon/Temu
  --all       Exécute tout (analyse + correction + détail)

Sans option: Exécute seulement la correction forcée
            """)
    else:
        force_fix_all()
        show_detailed_amazon_temu()