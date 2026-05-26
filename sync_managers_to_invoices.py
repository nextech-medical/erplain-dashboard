# sync_managers_to_invoices_final.py
"""
Script pour synchroniser les gestionnaires depuis sales_orders vers invoices
"""

import psycopg2
import pandas as pd
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def sync_managers_to_invoices():
    """
    Met à jour la colonne gestionnaire dans invoices avec les valeurs de sales_orders
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 70)
    print("🔄 SYNCHRONISATION DES GESTIONNAIRES VERS LES FACTURES")
    print("=" * 70)
    
    # 1. Vérifier que la colonne gestionnaire existe
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'invoices' AND column_name = 'gestionnaire'
    """)
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE invoices ADD COLUMN gestionnaire VARCHAR(100)")
        print("✅ Colonne 'gestionnaire' ajoutée à invoices")
    
    # 2. Mettre à jour par order_number
    print("\n📝 Mise à jour par order_number...")
    cursor.execute("""
        UPDATE invoices i
        SET gestionnaire = so.account_manager_name,
            reference_externe = COALESCE(i.reference_externe, so.external_reference)
        FROM sales_orders so
        WHERE i.order_number = so.order_number
        AND so.account_manager_name IS NOT NULL
        AND so.account_manager_name != ''
        AND (i.gestionnaire IS NULL OR i.gestionnaire = '' OR i.gestionnaire = 'Direct' OR i.gestionnaire = 'Non spécifié')
    """)
    print(f"   ✅ {cursor.rowcount} factures mises à jour")
    
    # 3. Mettre à jour par label (invoice_number)
    print("\n📝 Mise à jour par label...")
    cursor.execute("""
        UPDATE invoices i
        SET gestionnaire = so.account_manager_name,
            reference_externe = COALESCE(i.reference_externe, so.external_reference)
        FROM sales_orders so
        WHERE i.label = so.order_number
        AND so.account_manager_name IS NOT NULL
        AND so.account_manager_name != ''
        AND (i.gestionnaire IS NULL OR i.gestionnaire = '' OR i.gestionnaire = 'Direct' OR i.gestionnaire = 'Non spécifié')
    """)
    print(f"   ✅ {cursor.rowcount} factures mises à jour")
    
    # 4. Mettre à jour par external_reference
    print("\n📝 Mise à jour par référence externe...")
    cursor.execute("""
        UPDATE invoices i
        SET gestionnaire = so.account_manager_name
        FROM sales_orders so
        WHERE i.reference_externe = so.external_reference
        AND so.account_manager_name IS NOT NULL
        AND so.account_manager_name != ''
        AND (i.gestionnaire IS NULL OR i.gestionnaire = '' OR i.gestionnaire = 'Direct' OR i.gestionnaire = 'Non spécifié')
    """)
    print(f"   ✅ {cursor.rowcount} factures mises à jour")
    
    # 5. Mettre à jour par customer_email
    print("\n📝 Mise à jour par email client...")
    cursor.execute("""
        UPDATE invoices i
        SET gestionnaire = so.account_manager_name
        FROM sales_orders so
        WHERE i.customer_email = so.customer_email
        AND so.account_manager_name IS NOT NULL
        AND so.account_manager_name != ''
        AND (i.gestionnaire IS NULL OR i.gestionnaire = '' OR i.gestionnaire = 'Direct' OR i.gestionnaire = 'Non spécifié')
    """)
    print(f"   ✅ {cursor.rowcount} factures mises à jour")
    
    conn.commit()
    cursor.close()
    conn.close()


def show_gestionnaires_stats():
    """Affiche les statistiques des gestionnaires dans les factures"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    print("\n" + "=" * 70)
    print("📊 GESTIONNAIRES DANS LES FACTURES")
    print("=" * 70)
    
    query = """
        SELECT 
            gestionnaire,
            COUNT(*) as nb_factures,
            ROUND(SUM(total)::numeric, 2) as ca_total
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        GROUP BY gestionnaire
        ORDER BY nb_factures DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print(df.to_string(index=False))
    
    # Total
    total = df['nb_factures'].sum()
    with_manager = df[df['gestionnaire'] != 'Direct']['nb_factures'].sum() if 'Direct' in df['gestionnaire'].values else total
    print(f"\n📈 Résumé:")
    print(f"   - Total factures 2026: {total}")
    print(f"   - Avec gestionnaire: {with_manager}")
    direct_count = df[df['gestionnaire'] == 'Direct']['nb_factures'].values[0] if 'Direct' in df['gestionnaire'].values else 0
    print(f"   - Direct (non assigné): {direct_count}")
    
    return df


def show_sales_orders_managers():
    """Affiche les gestionnaires disponibles dans sales_orders"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    print("\n" + "=" * 70)
    print("📊 GESTIONNAIRES DANS SALES_ORDERS")
    print("=" * 70)
    
    query = """
        SELECT 
            account_manager_name,
            COUNT(*) as nb_commandes
        FROM sales_orders
        WHERE account_manager_name IS NOT NULL
        AND account_manager_name != ''
        GROUP BY account_manager_name
        ORDER BY nb_commandes DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print(df.to_string(index=False))
    
    return df


def show_factures_sans_gestionnaire():
    """Affiche les factures qui n'ont pas encore de gestionnaire"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    print("\n" + "=" * 70)
    print("📋 FACTURES SANS GESTIONNAIRE (20 premiers)")
    print("=" * 70)
    
    query = """
        SELECT 
            i.id,
            i.label,
            i.order_number,
            i.reference_externe,
            i.customer_name,
            i.customer_email,
            i.total
        FROM invoices i
        WHERE (i.gestionnaire IS NULL OR i.gestionnaire = '' OR i.gestionnaire = 'Direct')
        AND i.invoice_created >= '2026-01-01'
        LIMIT 20
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df.empty:
        print(df.to_string(index=False))
    else:
        print("✅ Toutes les factures ont un gestionnaire !")
    
    return df


def full_sync():
    """Exécute la synchronisation complète"""
    print("\n" + "=" * 70)
    print("🚀 SYNCHRONISATION COMPLÈTE")
    print("=" * 70)
    
    # Afficher les gestionnaires disponibles
    show_sales_orders_managers()
    
    # Synchroniser
    sync_managers_to_invoices()
    
    # Afficher les résultats
    show_gestionnaires_stats()
    
    # Afficher les factures sans gestionnaire restantes
    show_factures_sans_gestionnaire()
    
    print("\n" + "=" * 70)
    print("✅ SYNCHRONISATION TERMINÉE")
    print("=" * 70)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--show":
            show_gestionnaires_stats()
        elif sys.argv[1] == "--sales":
            show_sales_orders_managers()
        elif sys.argv[1] == "--missing":
            show_factures_sans_gestionnaire()
        elif sys.argv[1] == "--sync":
            sync_managers_to_invoices()
            show_gestionnaires_stats()
        else:
            print("Usage: python sync_managers_to_invoices_final.py [--show] [--sales] [--missing] [--sync]")
    else:
        full_sync()