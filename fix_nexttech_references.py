# fix_nexttech_orders.py
"""
Script pour lier les factures NEXTECH Boutique à la table orders
"""

import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def inspect_orders_table():
    """Inspecte la table orders"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 70)
    print("🔍 INSPECTION DE LA TABLE ORDERS")
    print("=" * 70)
    
    # Voir les données dans orders
    print("\n📦 Commandes dans orders (20 premiers):")
    cursor.execute("""
        SELECT id, order_id, external_reference, account_manager_name, customer_email
        FROM orders
        WHERE external_reference IS NOT NULL 
        AND external_reference != ''
        LIMIT 20
    """)
    for row in cursor.fetchall():
        ref = row[2][:40] if row[2] else 'None'
        print(f"   id: {row[0]} | order_id: {row[1]} | ref: {ref} | manager: {row[3]} | email: {row[4]}")
    
    # Compter les commandes avec références
    cursor.execute("""
        SELECT COUNT(*) FROM orders
        WHERE external_reference IS NOT NULL AND external_reference != ''
    """)
    count = cursor.fetchone()[0]
    print(f"\n📊 Total commandes avec références: {count}")
    
    # Voir les gestionnaires disponibles
    cursor.execute("""
        SELECT account_manager_name, COUNT(*) as nb
        FROM orders
        WHERE account_manager_name IS NOT NULL
        GROUP BY account_manager_name
        ORDER BY nb DESC
    """)
    print("\n👥 Gestionnaires dans orders:")
    for row in cursor.fetchall():
        print(f"   - {row[0]}: {row[1]} commandes")
    
    cursor.close()
    conn.close()


def link_nexttech_from_orders():
    """
    Lie les factures NEXTECH Boutique à la table orders
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 70)
    print("🔗 LIAISON NEXTECH BOUTIQUE → TABLE ORDERS")
    print("=" * 70)
    
    # 1. Afficher les factures NEXTECH sans référence
    cursor.execute("""
        SELECT i.order_number, i.label, i.customer_email
        FROM invoices i
        WHERE i.gestionnaire = 'NEXTECH Boutique'
        AND (i.reference_externe IS NULL OR i.reference_externe = '')
        LIMIT 10
    """)
    print("\n📄 Factures NEXTECH sans référence:")
    for row in cursor.fetchall():
        print(f"   {row[0]} | {row[1]} | email: {row[2]}")
    
    # 2. Mettre à jour par order_number exact (order_number facture = order_id commande)
    print("\n📌 MÉTHODE 1: Correspondance order_number exact")
    cursor.execute("""
        UPDATE invoices i
        SET reference_externe = o.external_reference,
            gestionnaire = COALESCE(o.account_manager_name, 'NEXTECH Boutique')
        FROM orders o
        WHERE i.gestionnaire = 'NEXTECH Boutique'
        AND (i.reference_externe IS NULL OR i.reference_externe = '')
        AND o.external_reference IS NOT NULL
        AND o.external_reference != ''
        AND i.order_number = o.order_id
    """)
    print(f"   ✅ {cursor.rowcount} factures mises à jour")
    
    # 3. Mettre à jour par correspondance sans le 'S'
    print("\n📌 MÉTHODE 2: Correspondance sans préfixe 'S'")
    cursor.execute("""
        UPDATE invoices i
        SET reference_externe = o.external_reference,
            gestionnaire = COALESCE(o.account_manager_name, 'NEXTECH Boutique')
        FROM orders o
        WHERE i.gestionnaire = 'NEXTECH Boutique'
        AND (i.reference_externe IS NULL OR i.reference_externe = '')
        AND o.external_reference IS NOT NULL
        AND o.external_reference != ''
        AND SUBSTRING(i.order_number, 2) = o.order_id
    """)
    print(f"   ✅ {cursor.rowcount} factures mises à jour")
    
    # 4. Mettre à jour par label (numéro de facture)
    print("\n📌 MÉTHODE 3: Correspondance par label")
    cursor.execute("""
        UPDATE invoices i
        SET reference_externe = o.external_reference,
            gestionnaire = COALESCE(o.account_manager_name, 'NEXTECH Boutique')
        FROM orders o
        WHERE i.gestionnaire = 'NEXTECH Boutique'
        AND (i.reference_externe IS NULL OR i.reference_externe = '')
        AND o.external_reference IS NOT NULL
        AND o.external_reference != ''
        AND i.label = o.order_id
    """)
    print(f"   ✅ {cursor.rowcount} factures mises à jour")
    
    # 5. Mettre à jour par correspondance partielle
    print("\n📌 MÉTHODE 4: Correspondance partielle")
    cursor.execute("""
        UPDATE invoices i
        SET reference_externe = o.external_reference,
            gestionnaire = COALESCE(o.account_manager_name, 'NEXTECH Boutique')
        FROM orders o
        WHERE i.gestionnaire = 'NEXTECH Boutique'
        AND (i.reference_externe IS NULL OR i.reference_externe = '')
        AND o.external_reference IS NOT NULL
        AND o.external_reference != ''
        AND (
            i.order_number LIKE '%' || o.order_id || '%'
            OR o.order_id LIKE '%' || i.order_number || '%'
            OR i.label LIKE '%' || o.order_id || '%'
        )
    """)
    print(f"   ✅ {cursor.rowcount} factures mises à jour")
    
    # 6. Mettre à jour par email
    print("\n📌 MÉTHODE 5: Correspondance par email")
    cursor.execute("""
        UPDATE invoices i
        SET reference_externe = o.external_reference,
            gestionnaire = COALESCE(o.account_manager_name, 'NEXTECH Boutique')
        FROM orders o
        WHERE i.gestionnaire = 'NEXTECH Boutique'
        AND (i.reference_externe IS NULL OR i.reference_externe = '')
        AND o.external_reference IS NOT NULL
        AND o.external_reference != ''
        AND i.customer_email = o.customer_email
    """)
    print(f"   ✅ {cursor.rowcount} factures mises à jour")
    
    conn.commit()
    
    # 7. Résultat
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as avec_ref
        FROM invoices
        WHERE gestionnaire = 'NEXTECH Boutique'
    """)
    row = cursor.fetchone()
    print(f"\n📊 RÉSULTAT FINAL: {row[1]}/{row[0]} factures NEXTECH avec référence")
    
    # Afficher les exemples
    print("\n📋 Exemples de factures NEXTECH après correction:")
    cursor.execute("""
        SELECT order_number, reference_externe
        FROM invoices
        WHERE gestionnaire = 'NEXTECH Boutique'
        AND reference_externe IS NOT NULL
        AND reference_externe != ''
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"   {row[0]} -> {row[1]}")
    
    cursor.close()
    conn.close()


def show_orders_for_nexttech():
    """Affiche les commandes qui pourraient correspondre aux factures NEXTECH"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 70)
    print("🔍 COMMANDES POUR NEXTECH BOUTIQUE")
    print("=" * 70)
    
    # Afficher les commandes avec le même email
    cursor.execute("""
        SELECT order_id, external_reference, account_manager_name, customer_email
        FROM orders
        WHERE customer_email = 'roua.faroukh@nextechmedical.fr'
        AND external_reference IS NOT NULL
        AND external_reference != ''
        LIMIT 20
    """)
    print("\n📦 Commandes avec email roua.faroukh@nextechmedical.fr:")
    for row in cursor.fetchall():
        ref = row[1][:40] if row[1] else 'None'
        print(f"   order_id: {row[0]} | ref: {ref} | manager: {row[2]}")
    
    # Afficher les factures NEXTECH
    cursor.execute("""
        SELECT order_number, label, reference_externe
        FROM invoices
        WHERE gestionnaire = 'NEXTECH Boutique'
        LIMIT 15
    """)
    print("\n📄 Factures NEXTECH Boutique:")
    for row in cursor.fetchall():
        ref = row[2][:40] if row[2] else 'None'
        print(f"   order_number: {row[0]} | label: {row[1]} | ref: {ref}")
    
    cursor.close()
    conn.close()


def fix_all():
    """Exécute toutes les corrections"""
    print("\n" + "=" * 70)
    print("🚀 CORRECTION COMPLÈTE")
    print("=" * 70)
    
    # 1. Inspecter d'abord
    inspect_orders_table()
    
    # 2. Afficher les commandes pour NEXTECH
    show_orders_for_nexttech()
    
    # 3. Lier les factures
    link_nexttech_from_orders()
    
    print("\n" + "=" * 70)
    print("✅ CORRECTION TERMINÉE")
    print("=" * 70)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--inspect":
            inspect_orders_table()
        elif sys.argv[1] == "--show":
            show_orders_for_nexttech()
        elif sys.argv[1] == "--link":
            link_nexttech_from_orders()
        elif sys.argv[1] == "--all":
            fix_all()
        else:
            print("Usage: python fix_nexttech_orders.py [--inspect] [--show] [--link] [--all]")
    else:
        fix_all()