# sync_exact_managers.py
import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def sync_exact_managers():
    """Synchronise les gestionnaires EXACTS depuis orders vers invoices"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 70)
    print("🔄 SYNCHRONISATION DES GESTIONNAIRES (NOMS EXACTS)")
    print("=" * 70)
    
    # 1. Voir les gestionnaires disponibles dans orders
    print("\n📋 Gestionnaires dans la table orders:")
    cursor.execute("""
        SELECT DISTINCT account_manager_name, COUNT(*) as nb
        FROM orders
        WHERE account_manager_name IS NOT NULL AND account_manager_name != ''
        GROUP BY account_manager_name
        ORDER BY nb DESC
    """)
    
    managers_orders = cursor.fetchall()
    for row in managers_orders:
        print(f"   • {row[0]}: {row[1]} commandes")
    
    # 2. Mettre à jour les factures depuis orders
    print("\n📌 Mise à jour des factures...")
    
    # Par order_number
    cursor.execute("""
        UPDATE invoices i
        SET gestionnaire = o.account_manager_name,
            reference_externe = COALESCE(i.reference_externe, o.external_reference),
            updated_at = CURRENT_TIMESTAMP
        FROM orders o
        WHERE i.order_number = o.order_id
        AND o.account_manager_name IS NOT NULL
        AND o.account_manager_name != ''
    """)
    
    updated1 = cursor.rowcount
    print(f"   ✅ {updated1} factures mises à jour par order_number")
    
    # Par label
    cursor.execute("""
        UPDATE invoices i
        SET gestionnaire = o.account_manager_name,
            reference_externe = COALESCE(i.reference_externe, o.external_reference),
            updated_at = CURRENT_TIMESTAMP
        FROM orders o
        WHERE i.label = o.order_id
        AND o.account_manager_name IS NOT NULL
        AND o.account_manager_name != ''
        AND (i.gestionnaire IS NULL OR i.gestionnaire = '')
    """)
    
    updated2 = cursor.rowcount
    print(f"   ✅ {updated2} factures mises à jour par label")
    
    # Par external_reference
    cursor.execute("""
        UPDATE invoices i
        SET gestionnaire = o.account_manager_name,
            updated_at = CURRENT_TIMESTAMP
        FROM orders o
        WHERE i.reference_externe = o.external_reference
        AND o.account_manager_name IS NOT NULL
        AND o.account_manager_name != ''
        AND (i.gestionnaire IS NULL OR i.gestionnaire = '')
    """)
    
    updated3 = cursor.rowcount
    print(f"   ✅ {updated3} factures mises à jour par référence externe")
    
    conn.commit()
    
    # 3. Pour les factures sans correspondance (type S...), les mettre à "Nextech Boutique"
    print("\n📌 Factures sans correspondance -> Nextech Boutique")
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Nextech Boutique'
        WHERE invoice_created >= '2026-01-01'
        AND (gestionnaire IS NULL OR gestionnaire = '' OR gestionnaire = 'Direct' OR gestionnaire = 'Boutique')
        AND order_number LIKE 'S%'
    """)
    
    updated4 = cursor.rowcount
    print(f"   ✅ {updated4} factures -> Nextech Boutique")
    
    conn.commit()
    
    # 4. Résultat final
    print("\n📊 RÉPARTITION FINALE DES GESTIONNAIRES:")
    cursor.execute("""
        SELECT 
            gestionnaire,
            COUNT(*) as nb,
            ROUND(SUM(total)::numeric, 2) as ca,
            COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as avec_ref
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        GROUP BY gestionnaire
        ORDER BY nb DESC
    """)
    
    for row in cursor.fetchall():
        print(f"   • {row[0]}: {row[1]} factures, {row[2]:,.2f} € ({row[3]} avec réf)")
    
    cursor.close()
    conn.close()
    
    return updated1 + updated2 + updated3 + updated4

def show_manager_distribution():
    """Affiche la distribution détaillée"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    print("\n" + "=" * 70)
    print("📊 DISTRIBUTION DÉTAILLÉE PAR GESTIONNAIRE")
    print("=" * 70)
    
    query = """
        SELECT 
            gestionnaire,
            COUNT(*) as nb_factures,
            COUNT(DISTINCT customer_name) as nb_clients,
            ROUND(SUM(total)::numeric, 2) as ca_total,
            ROUND(AVG(total)::numeric, 2) as panier_moyen,
            MIN(invoice_created) as premiere_facture,
            MAX(invoice_created) as derniere_facture
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        AND gestionnaire IS NOT NULL
        AND gestionnaire != ''
        GROUP BY gestionnaire
        ORDER BY ca_total DESC
    """
    
    import pandas as pd
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print(df.to_string(index=False))
    
    # Pourcentage du CA
    print("\n📊 PART DU CA PAR GESTIONNAIRE:")
    total_ca = df['ca_total'].sum()
    for _, row in df.iterrows():
        pct = (row['ca_total'] / total_ca * 100) if total_ca > 0 else 0
        barre = "█" * int(pct / 2)
        print(f"   {row['gestionnaire']:<20} {pct:>5.1f}% {barre}")

if __name__ == "__main__":
    import pandas as pd
    
    sync_exact_managers()
    show_manager_distribution()
    
    print("\n" + "=" * 70)
    print("✅ Gestionnaires synchronisés:")
    print("   • Amazon.fr")
    print("   • Nextech Boutique")
    print("   • Temu")
    print("   • Nextech Relais")
    print("=" * 70)