# analyze_data_fixed.py
"""
Script pour analyser les données et trouver les correspondances
"""

import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def analyze_data():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 70)
    print("🔍 ANALYSE DES DONNÉES")
    print("=" * 70)
    
    # 1. Voir les order_number des factures NEXTECH sans référence
    print("\n📋 Factures NEXTECH sans référence (10 premiers):")
    cursor.execute("""
        SELECT order_number, label, customer_name
        FROM invoices
        WHERE gestionnaire = 'NEXTECH Boutique'
        AND (reference_externe IS NULL OR reference_externe = '')
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"   {row[0]} | {row[1]} | {row[2]}")
    
    # 2. Voir les order_number des delivery_notes
    print("\n📦 Delivery notes (10 premiers):")
    cursor.execute("""
        SELECT order_number, external_reference, shipping_date
        FROM delivery_notes
        WHERE external_reference IS NOT NULL
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"   {row[0]} | {row[1]} | {row[2]}")
    
    # 3. Compter les factures par gestionnaire
    print("\n📊 Répartition par gestionnaire:")
    cursor.execute("""
        SELECT gestionnaire, COUNT(*) as nb, 
               COUNT(CASE WHEN reference_externe IS NOT NULL THEN 1 END) as avec_ref
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        GROUP BY gestionnaire
        ORDER BY nb DESC
    """)
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]} factures ({row[2]} avec référence)")
    
    # 4. Voir les références déjà existantes pour NEXTECH
    print("\n✅ Références NEXTECH déjà existantes:")
    cursor.execute("""
        SELECT order_number, reference_externe, bl_number
        FROM invoices
        WHERE gestionnaire = 'NEXTECH Boutique'
        AND reference_externe IS NOT NULL
        AND reference_externe != ''
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"   {row[0]} -> {row[1]} (BL: {row[2]})")
    
    # 5. Vérifier si les delivery_notes ont des références pour les commandes Sxxxxx
    print("\n🔍 Delivery notes avec des références (commençant par S):")
    cursor.execute("""
        SELECT order_number, external_reference
        FROM delivery_notes
        WHERE order_number LIKE 'S%'
        AND external_reference IS NOT NULL
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"   {row[0]} -> {row[1]}")
    
    # 6. Compter les delivery_notes par préfixe
    print("\n📊 Préfixes des delivery_notes:")
    cursor.execute("""
        SELECT LEFT(order_number, 1) as prefix, COUNT(*) as nb,
               COUNT(CASE WHEN external_reference IS NOT NULL THEN 1 END) as avec_ref
        FROM delivery_notes
        GROUP BY LEFT(order_number, 1)
        ORDER BY nb DESC
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]} BL ({row[2]} avec référence)")
    
    # 7. Chercher des correspondances potentielles (sans le préfixe S)
    print("\n🔍 Correspondances potentielles (sans le S):")
    cursor.execute("""
        SELECT i.order_number, i.label, dn.order_number, dn.external_reference
        FROM invoices i
        JOIN delivery_notes dn ON SUBSTRING(i.order_number, 2) = dn.order_number
        WHERE i.gestionnaire = 'NEXTECH Boutique'
        AND (i.reference_externe IS NULL OR i.reference_externe = '')
        AND dn.external_reference IS NOT NULL
        LIMIT 10
    """)
    matches = cursor.fetchall()
    if matches:
        for row in matches:
            print(f"   Facture {row[0]} -> BL {row[2]} -> Réf: {row[3]}")
    else:
        print("   Aucune correspondance trouvée")
    
    # 8. Chercher par correspondance inverse (enlever BC des BL)
    print("\n🔍 Correspondances potentielles (enlever BC des BL):")
    cursor.execute("""
        SELECT i.order_number, i.label, dn.order_number, dn.external_reference
        FROM invoices i
        JOIN delivery_notes dn ON i.order_number = SUBSTRING(dn.order_number, 3)
        WHERE i.gestionnaire = 'NEXTECH Boutique'
        AND (i.reference_externe IS NULL OR i.reference_externe = '')
        AND dn.external_reference IS NOT NULL
        LIMIT 10
    """)
    matches2 = cursor.fetchall()
    if matches2:
        for row in matches2:
            print(f"   Facture {row[0]} -> BL {row[2]} -> Réf: {row[3]}")
    else:
        print("   Aucune correspondance trouvée")
    
    conn.close()


def fix_nexttech_correspondence():
    """
    Corrige les références en utilisant les correspondances trouvées
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 70)
    print("🔧 CORRECTION DES RÉFÉRENCES NEXTECH")
    print("=" * 70)
    
    # Méthode 1: Enlever le 'S' du numéro de facture
    print("\n📌 Méthode 1: Correspondance Sxxx -> xxx")
    cursor.execute("""
        UPDATE invoices i
        SET reference_externe = dn.external_reference,
            bl_number = dn.order_number,
            shipping_date = dn.shipping_date
        FROM delivery_notes dn
        WHERE i.gestionnaire = 'NEXTECH Boutique'
        AND dn.external_reference IS NOT NULL
        AND (i.reference_externe IS NULL OR i.reference_externe = '')
        AND SUBSTRING(i.order_number, 2) = dn.order_number
    """)
    print(f"   ✅ {cursor.rowcount} références mises à jour")
    
    # Méthode 2: Enlever le 'BC' des BL
    print("\n📌 Méthode 2: Correspondance facture -> BL sans BC")
    cursor.execute("""
        UPDATE invoices i
        SET reference_externe = dn.external_reference,
            bl_number = dn.order_number,
            shipping_date = dn.shipping_date
        FROM delivery_notes dn
        WHERE i.gestionnaire = 'NEXTECH Boutique'
        AND dn.external_reference IS NOT NULL
        AND (i.reference_externe IS NULL OR i.reference_externe = '')
        AND i.order_number = SUBSTRING(dn.order_number, 3)
    """)
    print(f"   ✅ {cursor.rowcount} références mises à jour")
    
    # Méthode 3: Correspondance partielle (le numéro est contenu)
    print("\n📌 Méthode 3: Correspondance partielle")
    cursor.execute("""
        UPDATE invoices i
        SET reference_externe = dn.external_reference,
            bl_number = dn.order_number,
            shipping_date = dn.shipping_date
        FROM delivery_notes dn
        WHERE i.gestionnaire = 'NEXTECH Boutique'
        AND dn.external_reference IS NOT NULL
        AND (i.reference_externe IS NULL OR i.reference_externe = '')
        AND (
            POSITION(dn.order_number IN i.order_number) > 0
            OR POSITION(SUBSTRING(i.order_number, 2) IN dn.order_number) > 0
        )
    """)
    print(f"   ✅ {cursor.rowcount} références mises à jour")
    
    conn.commit()
    
    # Afficher le résultat
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as avec_ref
        FROM invoices
        WHERE gestionnaire = 'NEXTECH Boutique'
    """)
    row = cursor.fetchone()
    print(f"\n📊 Résultat: {row[1]}/{row[0]} factures NEXTECH avec référence")
    
    cursor.close()
    conn.close()


def show_delivery_notes_for_nexttech():
    """Affiche les delivery_notes qui pourraient correspondre aux factures NEXTECH"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 70)
    print("📦 DELIVERY_NOTES POUR NEXTECH")
    print("=" * 70)
    
    # Prendre les 10 premières factures NEXTECH sans référence
    cursor.execute("""
        SELECT order_number, label
        FROM invoices
        WHERE gestionnaire = 'NEXTECH Boutique'
        AND (reference_externe IS NULL OR reference_externe = '')
        LIMIT 10
    """)
    invoices = cursor.fetchall()
    
    for inv_order, inv_label in invoices:
        print(f"\n🔹 Facture: {inv_order}")
        
        # Chercher des delivery_notes correspondantes
        cursor.execute("""
            SELECT order_number, external_reference, shipping_date
            FROM delivery_notes
            WHERE external_reference IS NOT NULL
            AND (
                order_number = SUBSTRING(%s, 2)
                OR %s = SUBSTRING(order_number, 3)
                OR POSITION(%s IN order_number) > 0
                OR POSITION(order_number IN %s) > 0
            )
            LIMIT 3
        """, (inv_order, inv_order, inv_order, inv_order))
        
        matches = cursor.fetchall()
        if matches:
            for match in matches:
                print(f"   -> BL: {match[0]} | Réf: {match[1]} | Date: {match[2]}")
        else:
            print("   Aucune correspondance trouvée")
    
    cursor.close()
    conn.close()


def fix_by_email():
    """Corrige par email pour NEXTECH"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 70)
    print("🔧 CORRECTION PAR EMAIL")
    print("=" * 70)
    
    # Compter les delivery_notes par email
    cursor.execute("""
        SELECT COUNT(*)
        FROM delivery_notes dn
        JOIN invoices i ON i.customer_email = 'roua.faroukh@nextechmedical.fr'
        WHERE i.gestionnaire = 'NEXTECH Boutique'
        AND dn.external_reference IS NOT NULL
    """)
    print(f"   Delivery_notes trouvés: {cursor.fetchone()[0]}")
    
    # Mettre à jour
    cursor.execute("""
        UPDATE invoices i
        SET reference_externe = dn.external_reference,
            bl_number = dn.order_number,
            shipping_date = dn.shipping_date
        FROM delivery_notes dn
        WHERE i.gestionnaire = 'NEXTECH Boutique'
        AND i.customer_email = 'roua.faroukh@nextechmedical.fr'
        AND dn.external_reference IS NOT NULL
        AND (i.reference_externe IS NULL OR i.reference_externe = '')
        AND i.order_number = dn.order_number
    """)
    print(f"   ✅ {cursor.rowcount} références mises à jour")
    
    conn.commit()
    cursor.close()
    conn.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--analyze":
            analyze_data()
        elif sys.argv[1] == "--fix":
            fix_nexttech_correspondence()
        elif sys.argv[1] == "--show":
            show_delivery_notes_for_nexttech()
        elif sys.argv[1] == "--email":
            fix_by_email()
        else:
            print("Usage: python analyze_data_fixed.py [--analyze] [--fix] [--show] [--email]")
    else:
        analyze_data()