# inspect_nexttech.py
"""
Script pour inspecter les données NEXTECH Boutique
"""

import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def inspect_nexttech():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 70)
    print("🔍 INSPECTION NEXTECH BOUTIQUE")
    print("=" * 70)
    
    # 1. Voir les commandes sales_orders avec external_reference
    print("\n📦 Commandes dans sales_orders avec external_reference (10 premiers):")
    cursor.execute("""
        SELECT order_number, label, external_reference, account_manager_name, customer_email
        FROM sales_orders
        WHERE external_reference IS NOT NULL 
        AND external_reference != ''
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"   order: {row[0]} | label: {row[1]} | ref: {row[2][:30]} | manager: {row[3]} | email: {row[4]}")
    
    # 2. Voir les factures NEXTECH Boutique
    print("\n📄 Factures NEXTECH Boutique (10 premiers):")
    cursor.execute("""
        SELECT order_number, label, reference_externe, customer_email, notes_text
        FROM invoices
        WHERE gestionnaire = 'NEXTECH Boutique'
        LIMIT 10
    """)
    for row in cursor.fetchall():
        notes = row[4][:50] if row[4] else 'None'
        print(f"   order: {row[0]} | label: {row[1]} | ref: {row[2]} | email: {row[3]} | notes: {notes}")
    
    # 3. Chercher des correspondances possibles
    print("\n🔍 Recherche de correspondances entre les deux tables:")
    
    # Par email
    cursor.execute("""
        SELECT DISTINCT i.customer_email, so.customer_email
        FROM invoices i
        JOIN sales_orders so ON i.customer_email = so.customer_email
        WHERE i.gestionnaire = 'NEXTECH Boutique'
        AND so.external_reference IS NOT NULL
        LIMIT 10
    """)
    matches = cursor.fetchall()
    if matches:
        print("\n✅ Correspondances par email trouvées:")
        for row in matches:
            print(f"   Email: {row[0]}")
    else:
        print("\n❌ Aucune correspondance par email")
    
    # 4. Vérifier si les numéros de commande des factures apparaissent dans sales_orders
    print("\n🔍 Vérification des numéros de commande:")
    cursor.execute("""
        SELECT i.order_number, COUNT(so.id)
        FROM invoices i
        LEFT JOIN sales_orders so ON so.order_number = i.order_number
        WHERE i.gestionnaire = 'NEXTECH Boutique'
        GROUP BY i.order_number
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"   {row[0]} -> trouvé dans sales_orders: {row[1] > 0}")
    
    # 5. Voir les commandes sales_orders avec account_manager_name 'NEXTECH Boutique'
    print("\n📦 Commandes sales_orders avec manager 'NEXTECH Boutique':")
    cursor.execute("""
        SELECT order_number, external_reference, customer_email
        FROM sales_orders
        WHERE account_manager_name = 'NEXTECH Boutique'
        AND external_reference IS NOT NULL
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"   order: {row[0]} | ref: {row[1][:30] if row[1] else 'None'} | email: {row[2]}")
    
    # 6. Compter
    cursor.execute("""
        SELECT COUNT(*) FROM sales_orders WHERE account_manager_name = 'NEXTECH Boutique'
    """)
    count_so = cursor.fetchone()[0]
    print(f"\n📊 Total commandes avec manager 'NEXTECH Boutique': {count_so}")
    
    cursor.close()
    conn.close()


def fix_manually():
    """
    Correction manuelle - à exécuter après inspection
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 70)
    print("🔧 CORRECTION MANUELLE")
    print("=" * 70)
    
    # Mettre à jour les factures qui ont déjà une référence (comme S30006)
    # Ces factures ont un BL correspondant, on peut les utiliser comme template
    cursor.execute("""
        SELECT i.order_number, i.reference_externe, i.bl_number
        FROM invoices i
        WHERE i.gestionnaire = 'NEXTECH Boutique'
        AND i.reference_externe IS NOT NULL
        AND i.reference_externe != ''
    """)
    existing = cursor.fetchall()
    print(f"\n📋 {len(existing)} factures ont déjà une référence:")
    for row in existing:
        print(f"   {row[0]} -> {row[1]} (BL: {row[2]})")
    
    # Chercher si les commandes correspondantes existent dans sales_orders
    for order_num, ref, bl in existing:
        cursor.execute("""
            SELECT order_number, external_reference, account_manager_name
            FROM sales_orders
            WHERE external_reference = %s
        """, (ref,))
        row = cursor.fetchone()
        if row:
            print(f"   ✅ Commande trouvée: {row[0]} -> {row[1]} ({row[2]})")
        else:
            print(f"   ❌ Aucune commande trouvée pour la référence {ref}")
    
    cursor.close()
    conn.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--fix":
        fix_manually()
    else:
        inspect_nexttech()