# final_fix_managers.py
"""
Script final pour fusionner les gestionnaires et préparer le dashboard
"""

import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def final_cleanup():
    """Nettoyage final des gestionnaires"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 80)
    print("🔧 NETTOYAGE FINAL DES GESTIONNAIRES")
    print("=" * 80)
    
    # 1. Fusionner les deux catégories Appels d'offres
    print("\n📌 FUSION DES APPELS D'OFFRES:")
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Appels d''offres'
        WHERE gestionnaire IN ('Appels d''offres', 'Appels doffres', 'Appel doffres')
    """)
    print(f"   ✅ {cursor.rowcount} factures fusionnées")
    
    # 2. Nettoyer les espaces et caractères
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = TRIM(gestionnaire)
    """)
    
    # 3. Mettre à jour les références externes manquantes pour Amazon/Temu
    print("\n📌 MISE À JOUR DES RÉFÉRENCES:")
    
    # Amazon
    cursor.execute("""
        UPDATE invoices 
        SET reference_externe = order_number
        WHERE gestionnaire = 'Amazon .fr' 
        AND (reference_externe IS NULL OR reference_externe = '')
    """)
    print(f"   ✅ Amazon: {cursor.rowcount} références mises à jour")
    
    # Temu
    cursor.execute("""
        UPDATE invoices 
        SET reference_externe = order_number
        WHERE gestionnaire = 'TEMU FR' 
        AND (reference_externe IS NULL OR reference_externe = '')
    """)
    print(f"   ✅ Temu: {cursor.rowcount} références mises à jour")
    
    conn.commit()
    
    # 4. Afficher le résultat final
    print("\n" + "=" * 80)
    print("📊 DISTRIBUTION FINALE DES GESTIONNAIRES")
    print("=" * 80)
    
    cursor.execute("""
        SELECT 
            gestionnaire,
            COUNT(*) as nb_factures,
            ROUND(SUM(total)::numeric, 2) as ca_total,
            ROUND(AVG(total)::numeric, 2) as panier_moyen,
            MIN(invoice_created) as premiere_facture,
            MAX(invoice_created) as derniere_facture
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        GROUP BY gestionnaire
        ORDER BY ca_total DESC
    """)
    
    print(f"\n{'Gestionnaire':<20} {'Factures':>10} {'CA Total':>15} {'Panier moyen':>15} {'Période'}")
    print("-" * 80)
    
    for row in cursor.fetchall():
        periode = f"{row[4][:10] if row[4] else '?'} → {row[5][:10] if row[5] else '?'}"
        print(f"{row[0]:<20} {row[1]:>10} {row[2]:>15,.2f} € {row[3]:>14,.2f} €  {periode}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 80)
    print("✅ NETTOYAGE TERMINÉ")
    print("=" * 80)

def get_dashboard_data():
    """Prépare les données pour le dashboard"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    print("\n" + "=" * 80)
    print("📊 DONNÉES POUR LE DASHBOARD")
    print("=" * 80)
    
    # Statistiques globales
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            COUNT(*) as total_factures,
            COUNT(DISTINCT customer_name) as total_clients,
            ROUND(SUM(total)::numeric, 2) as ca_total,
            ROUND(AVG(total)::numeric, 2) as panier_moyen
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
    """)
    
    row = cursor.fetchone()
    print(f"\n📈 STATISTIQUES GLOBALES 2026:")
    print(f"   📄 Factures: {row[0]}")
    print(f"   👥 Clients uniques: {row[1]}")
    print(f"   💰 CA Total: {row[2]:,.2f} €")
    print(f"   🛒 Panier moyen: {row[3]:,.2f} €")
    
    # Détail par gestionnaire
    cursor.execute("""
        SELECT 
            gestionnaire,
            COUNT(*) as nb,
            ROUND(SUM(total)::numeric, 2) as ca,
            ROUND(AVG(total)::numeric, 2) as moyenne
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        GROUP BY gestionnaire
        ORDER BY ca DESC
    """)
    
    print(f"\n📊 DÉTAIL PAR GESTIONNAIRE:")
    for row in cursor.fetchall():
        pct = (row[2] / 270000 * 100) if row[2] else 0
        print(f"   {row[0]:<20}: {row[1]:>5} factures, {row[2]:>12,.2f} € ({pct:.1f}%) - moyenne: {row[3]:.2f} €")
    
    cursor.close()
    conn.close()

def create_dashboard_query():
    """Génère la requête SQL pour le dashboard"""
    
    query = """
    SELECT 
        i.id,
        i.label as invoice_number,
        i.order_number,
        i.invoice_created as date,
        i.due_date,
        i.subtotal,
        i.total,
        i.customer_name,
        i.customer_email,
        COALESCE(i.reference_externe, '') as reference_externe,
        COALESCE(i.fournisseur, 'Non spécifié') as fournisseur,
        COALESCE(i.gestionnaire, 'Direct') as gestionnaire,
        il.product_label,
        il.product_sku,
        il.quantity,
        il.unit_price,
        il.line_total
    FROM invoices i
    LEFT JOIN invoice_lines il ON i.id = il.invoice_id
    WHERE i.invoice_created IS NOT NULL
    ORDER BY i.invoice_created DESC
    """
    
    print("\n" + "=" * 80)
    print("📋 REQUÊTE POUR LE DASHBOARD")
    print("=" * 80)
    print(query)
    
    return query

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--dashboard":
            get_dashboard_data()
        elif sys.argv[1] == "--query":
            create_dashboard_query()
        else:
            print("Usage: python final_fix_managers.py [--dashboard] [--query]")
    else:
        final_cleanup()
        get_dashboard_data()