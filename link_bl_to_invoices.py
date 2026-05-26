# link_invoices_to_delivery_notes_complete.py
"""
Script pour lier les factures aux bons de livraison et récupérer les références externes
"""

import psycopg2
import pandas as pd
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def link_invoices_to_delivery_notes():
    """
    Lie les factures aux bons de livraison par plusieurs méthodes
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 70)
    print("🔗 LIAISON FACTURES ↔ BONS DE LIVRAISON")
    print("=" * 70)
    
    # 1. Vérifier les tables
    cursor.execute("""
        SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'delivery_notes')
    """)
    if not cursor.fetchone()[0]:
        print("❌ Table 'delivery_notes' non trouvée")
        return 0
    
    # 2. Ajouter les colonnes si nécessaire
    cursor.execute("""
        ALTER TABLE invoices 
        ADD COLUMN IF NOT EXISTS reference_externe TEXT,
        ADD COLUMN IF NOT EXISTS bl_number TEXT,
        ADD COLUMN IF NOT EXISTS bl_id TEXT,
        ADD COLUMN IF NOT EXISTS shipping_date DATE,
        ADD COLUMN IF NOT EXISTS tracking_number TEXT
    """)
    conn.commit()
    print("✅ Colonnes ajoutées/vérifiées")
    
    # =========================================================
    # MÉTHODE 1: Correspondance exacte par order_number
    # =========================================================
    print("\n📌 MÉTHODE 1: Correspondance exacte par order_number")
    cursor.execute("""
        UPDATE invoices i
        SET reference_externe = COALESCE(i.reference_externe, dn.external_reference),
            bl_number = COALESCE(i.bl_number, dn.order_number),
            bl_id = dn.id,
            shipping_date = COALESCE(i.shipping_date, dn.shipping_date),
            tracking_number = COALESCE(i.tracking_number, dn.tracking_number)
        FROM delivery_notes dn
        WHERE i.order_number = dn.order_number
        AND (i.reference_externe IS NULL OR i.reference_externe = '')
    """)
    exact_match = cursor.rowcount
    print(f"   ✅ {exact_match} factures liées")
    
    # =========================================================
    # MÉTHODE 2: Correspondance par label (numéro de facture)
    # =========================================================
    print("\n📌 MÉTHODE 2: Correspondance par label (numéro de facture)")
    cursor.execute("""
        UPDATE invoices i
        SET reference_externe = COALESCE(i.reference_externe, dn.external_reference),
            bl_number = COALESCE(i.bl_number, dn.order_number),
            bl_id = dn.id,
            shipping_date = COALESCE(i.shipping_date, dn.shipping_date),
            tracking_number = COALESCE(i.tracking_number, dn.tracking_number)
        FROM delivery_notes dn
        WHERE i.label = dn.order_number
        AND (i.reference_externe IS NULL OR i.reference_externe = '')
    """)
    label_match = cursor.rowcount
    print(f"   ✅ {label_match} factures liées")
    
    # =========================================================
    # MÉTHODE 3: Correspondance par référence externe existante
    # =========================================================
    print("\n📌 MÉTHODE 3: Correspondance par référence externe")
    cursor.execute("""
        UPDATE invoices i
        SET bl_number = COALESCE(i.bl_number, dn.order_number),
            bl_id = dn.id,
            shipping_date = COALESCE(i.shipping_date, dn.shipping_date)
        FROM delivery_notes dn
        WHERE i.reference_externe = dn.external_reference
        AND dn.external_reference IS NOT NULL
        AND (i.bl_number IS NULL OR i.bl_number = '')
    """)
    ref_match = cursor.rowcount
    print(f"   ✅ {ref_match} BL mis à jour par référence")
    
    # =========================================================
    # MÉTHODE 4: Correspondance partielle (sans préfixe)
    # =========================================================
    print("\n📌 MÉTHODE 4: Correspondance partielle (sans préfixe S/BC)")
    cursor.execute("""
        UPDATE invoices i
        SET reference_externe = COALESCE(i.reference_externe, dn.external_reference),
            bl_number = COALESCE(i.bl_number, dn.order_number),
            bl_id = dn.id,
            shipping_date = COALESCE(i.shipping_date, dn.shipping_date)
        FROM delivery_notes dn
        WHERE (i.order_number LIKE '%' || dn.order_number || '%'
               OR dn.order_number LIKE '%' || i.order_number || '%'
               OR SUBSTRING(i.order_number, 2) = dn.order_number
               OR i.order_number = SUBSTRING(dn.order_number, 2))
        AND (i.reference_externe IS NULL OR i.reference_externe = '')
    """)
    partial_match = cursor.rowcount
    print(f"   ✅ {partial_match} factures liées")
    
    # =========================================================
    # MÉTHODE 5: Par correspondance avec le numéro de commande dans les notes
    # =========================================================
    print("\n📌 MÉTHODE 5: Correspondance par notes_text")
    cursor.execute("""
        UPDATE invoices i
        SET reference_externe = COALESCE(i.reference_externe, dn.external_reference),
            bl_number = COALESCE(i.bl_number, dn.order_number),
            bl_id = dn.id,
            shipping_date = COALESCE(i.shipping_date, dn.shipping_date)
        FROM delivery_notes dn
        WHERE i.notes_text LIKE '%' || dn.order_number || '%'
        AND (i.reference_externe IS NULL OR i.reference_externe = '')
    """)
    notes_match = cursor.rowcount
    print(f"   ✅ {notes_match} factures liées")
    
    conn.commit()
    
    total = exact_match + label_match + ref_match + partial_match + notes_match
    print(f"\n📊 TOTAL DES LIAISONS: {total}")
    
    cursor.close()
    conn.close()
    return total


def show_linking_stats():
    """Affiche les statistiques des liaisons"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    print("\n" + "=" * 70)
    print("📊 STATISTIQUES DES LIAISONS")
    print("=" * 70)
    
    query = """
        SELECT 
            COUNT(*) as total_factures,
            COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as avec_ref,
            COUNT(CASE WHEN bl_number IS NOT NULL AND bl_number != '' THEN 1 END) as avec_bl,
            COUNT(CASE WHEN shipping_date IS NOT NULL THEN 1 END) as avec_date
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
    """
    df = pd.read_sql_query(query, conn)
    
    print(f"\n📄 Factures 2026:")
    print(f"   - Total: {df['total_factures'].iloc[0]}")
    print(f"   - Avec référence externe: {df['avec_ref'].iloc[0]}")
    print(f"   - Avec BL: {df['avec_bl'].iloc[0]}")
    print(f"   - Avec date livraison: {df['avec_date'].iloc[0]}")
    
    # Par gestionnaire
    query2 = """
        SELECT 
            gestionnaire,
            COUNT(*) as nb,
            COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as avec_ref
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        GROUP BY gestionnaire
        ORDER BY nb DESC
    """
    df2 = pd.read_sql_query(query2, conn)
    print(f"\n📱 Par gestionnaire:")
    print(df2.to_string(index=False))
    
    conn.close()
    return df


def show_linked_examples(limit=20):
    """Affiche des exemples de factures liées"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    print("\n" + "=" * 70)
    print(f"📋 EXEMPLES DE FACTURES LIÉES ({limit} premiers)")
    print("=" * 70)
    
    query = f"""
        SELECT 
            i.order_number,
            i.label,
            i.reference_externe,
            i.bl_number,
            i.shipping_date,
            i.gestionnaire
        FROM invoices i
        WHERE i.reference_externe IS NOT NULL 
        AND i.reference_externe != ''
        AND i.invoice_created >= '2026-01-01'
        LIMIT {limit}
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print(df.to_string(index=False))
    return df


def show_unlinked_invoices(limit=30):
    """Affiche les factures non liées"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    print("\n" + "=" * 70)
    print(f"📋 FACTURES SANS RÉFÉRENCE ({limit} premiers)")
    print("=" * 70)
    
    query = f"""
        SELECT 
            i.order_number,
            i.label,
            i.customer_name,
            i.gestionnaire,
            i.notes_text
        FROM invoices i
        WHERE (i.reference_externe IS NULL OR i.reference_externe = '')
        AND i.invoice_created >= '2026-01-01'
        LIMIT {limit}
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print(df.to_string(index=False))
    return df


def sync_all():
    """Synchronisation complète"""
    print("\n" + "=" * 70)
    print("🚀 SYNCHRONISATION COMPLÈTE FACTURES ↔ BL")
    print("=" * 70)
    
    # 1. Lier les factures aux BL
    total_linked = link_invoices_to_delivery_notes()
    
    # 2. Afficher les statistiques
    show_linking_stats()
    
    # 3. Afficher des exemples
    show_linked_examples(15)
    
    # 4. Afficher les non liées
    show_unlinked_invoices(15)
    
    print("\n" + "=" * 70)
    print(f"✅ {total_linked} liaisons effectuées")
    print("=" * 70)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--link":
            link_invoices_to_delivery_notes()
        elif sys.argv[1] == "--stats":
            show_linking_stats()
        elif sys.argv[1] == "--examples":
            show_linked_examples()
        elif sys.argv[1] == "--unlinked":
            show_unlinked_invoices()
        elif sys.argv[1] == "--all":
            sync_all()
        else:
            print("Usage: python link_invoices_to_delivery_notes_complete.py [--link] [--stats] [--examples] [--unlinked] [--all]")
    else:
        sync_all()