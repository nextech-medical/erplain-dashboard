# final_reference_fix.py
"""
Correction finale des références pour les 455 factures Amazon sans référence
"""

import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def fix_remaining_references():
    """Génère des références pour les factures Amazon/Temu sans référence"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 80)
    print("🔧 CORRECTION DES RÉFÉRENCES MANQUANTES")
    print("=" * 80)
    
    # 1. Pour Amazon : générer une référence basée sur le numéro de commande
    cursor.execute("""
        UPDATE invoices 
        SET reference_externe = 'AMZ-' || order_number
        WHERE gestionnaire = 'Amazon .fr'
        AND (reference_externe IS NULL OR reference_externe = '')
    """)
    amazon_fixed = cursor.rowcount
    print(f"   ✅ Amazon: {amazon_fixed} références générées")
    
    # 2. Pour Temu
    cursor.execute("""
        UPDATE invoices 
        SET reference_externe = 'TEMU-' || order_number
        WHERE gestionnaire = 'TEMU FR'
        AND (reference_externe IS NULL OR reference_externe = '')
    """)
    temu_fixed = cursor.rowcount
    print(f"   ✅ Temu: {temu_fixed} références générées")
    
    conn.commit()
    
    # 3. Vérification finale
    cursor.execute("""
        SELECT 
            gestionnaire,
            COUNT(*) as total,
            COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as avec_ref
        FROM invoices
        WHERE gestionnaire IN ('Amazon .fr', 'TEMU FR')
        AND invoice_created >= '2026-01-01'
        GROUP BY gestionnaire
    """)
    
    print("\n📊 APRÈS CORRECTION:")
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]} factures, {row[2]} avec référence")
    
    cursor.close()
    conn.close()
    
    return amazon_fixed, temu_fixed

def show_final_summary():
    """Affiche le résumé final pour le dashboard"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 80)
    print("📊 RÉSUMÉ FINAL POUR LE DASHBOARD")
    print("=" * 80)
    
    cursor.execute("""
        SELECT 
            gestionnaire,
            COUNT(*) as nb_factures,
            ROUND(SUM(total)::numeric, 2) as ca_total,
            ROUND(AVG(total)::numeric, 2) as panier_moyen,
            MIN(invoice_created) as debut,
            MAX(invoice_created) as fin
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        GROUP BY gestionnaire
        ORDER BY ca_total DESC
    """)
    
    print(f"\n{'Gestionnaire':<20} {'Factures':>10} {'CA Total':>15} {'Panier moyen':>12} {'Période'}")
    print("-" * 80)
    
    for row in cursor.fetchall():
        # Correction: convertir les dates en string avant de les slicer
        debut = str(row[4])[:10] if row[4] else '?'
        fin = str(row[5])[:10] if row[5] else '?'
        periode = f"{debut} → {fin}"
        print(f"{row[0]:<20} {row[1]:>10} {row[2]:>15,.2f} € {row[3]:>11,.2f} €  {periode}")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--fix":
        fix_remaining_references()
    
    show_final_summary()