# fix_all_amazon_temu.py
"""
Script pour corriger TOUTES les factures Amazon et Temu
en se basant sur les patterns des références externes
"""

import psycopg2
import re
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def fix_all_by_reference_pattern():
    """Corrige toutes les factures par pattern de référence externe"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 80)
    print("🔧 CORRECTION COMPLÈTE PAR RÉFÉRENCE EXTERNE")
    print("=" * 80)
    
    # 1. Voir la situation avant
    print("\n📊 AVANT CORRECTION:")
    cursor.execute("""
        SELECT gestionnaire, COUNT(*) as nb
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        GROUP BY gestionnaire
        ORDER BY nb DESC
    """)
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]} factures")
    
    # 2. Corriger Amazon (pattern: 3 chiffres - 7 chiffres - 7 chiffres)
    print("\n📌 CORRECTION AMAZON:")
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Amazon .fr'
        WHERE reference_externe ~ '^[0-9]{3}-[0-9]{7}-[0-9]{7}$'
    """)
    print(f"   ✅ {cursor.rowcount} factures corrigées en Amazon .fr")
    
    # 3. Corriger Temu (pattern: PO-...)
    print("\n📌 CORRECTION TEMU:")
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'TEMU FR'
        WHERE reference_externe LIKE 'PO-%'
    """)
    print(f"   ✅ {cursor.rowcount} factures corrigées en TEMU FR")
    
    # 4. Corriger Appels d'offres
    print("\n📌 CORRECTION APPELS D'OFFRES:")
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Appels d''offres'
        WHERE reference_externe LIKE 'PH%' 
           OR reference_externe LIKE 'DMS%'
           OR reference_externe LIKE 'BS%'
           OR reference_externe LIKE '2026/%'
    """)
    print(f"   ✅ {cursor.rowcount} factures corrigées en Appels d'offres")
    
    # 5. Par email client pour Nextech Boutique
    print("\n📌 CORRECTION NEXTECH BOUTIQUE (par email):")
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'NEXTECH Boutique'
        WHERE customer_email = 'roua.faroukh@nextechmedical.fr'
        AND (gestionnaire IS NULL OR gestionnaire = 'Direct' OR gestionnaire = '')
    """)
    print(f"   ✅ {cursor.rowcount} factures → NEXTECH Boutique")
    
    # 6. Les factures avec total = 0 (échantillons)
    print("\n📌 ÉCHANTILLONS (total = 0):")
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Echantillons'
        WHERE total = 0
        AND (gestionnaire IS NULL OR gestionnaire = 'Direct' OR gestionnaire = '')
    """)
    print(f"   ✅ {cursor.rowcount} factures → Echantillons")
    
    conn.commit()
    
    # 7. Voir la situation après
    print("\n📊 APRÈS CORRECTION:")
    cursor.execute("""
        SELECT gestionnaire, COUNT(*) as nb, ROUND(SUM(total)::numeric, 2) as ca
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        GROUP BY gestionnaire
        ORDER BY ca DESC
    """)
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]} factures, {row[2]:,.2f} €")
    
    cursor.close()
    conn.close()

def show_uncorrected():
    """Affiche les factures qui n'ont pas encore de gestionnaire correct"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    print("\n" + "=" * 80)
    print("🔍 FACTURES SANS GESTIONNAIRE CORRECT")
    print("=" * 80)
    
    query = """
        SELECT 
            order_number,
            reference_externe,
            customer_name,
            total,
            gestionnaire
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        AND (gestionnaire IS NULL 
             OR gestionnaire = '' 
             OR gestionnaire = 'Direct'
             OR gestionnaire = 'Non spécifié')
        AND reference_externe IS NOT NULL
        AND reference_externe != ''
        LIMIT 30
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df.empty:
        print(df.to_string(index=False))
        print(f"\n⚠️ {len(df)} factures non corrigées (limité à 30)")
    else:
        print("✅ Toutes les factures ont un gestionnaire correct")
    
    return df

def show_distribution():
    """Affiche la distribution détaillée"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    print("\n" + "=" * 80)
    print("📊 DISTRIBUTION FINALE")
    print("=" * 80)
    
    query = """
        SELECT 
            gestionnaire,
            COUNT(*) as nb_factures,
            COUNT(DISTINCT customer_name) as nb_clients,
            ROUND(SUM(total)::numeric, 2) as ca_total,
            ROUND(AVG(total)::numeric, 2) as panier_moyen,
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
        if sys.argv[1] == "--show":
            show_uncorrected()
        elif sys.argv[1] == "--distrib":
            show_distribution()
        else:
            print("Usage: python fix_all_amazon_temu.py [--show] [--distrib]")
    else:
        fix_all_by_reference_pattern()
        show_distribution()