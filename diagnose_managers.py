# update_managers_from_bl.py
"""
Script pour mettre à jour les gestionnaires à partir des bons de livraison
"""
import psycopg2
import pandas as pd
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def detect_platform_from_reference(reference):
    """
    Détecte la plateforme à partir de la référence externe
    """
    if not reference:
        return None
    
    ref = str(reference).upper()
    
    # Amazon: 40X-XXXXXXX-XXXXXXX
    if ref.startswith('40') and ref.count('-') >= 2:
        return 'Amazon'
    
    # Temu: PO-XXXXX ou EXXXXXX
    if ref.startswith('PO-') or (ref.startswith('E') and len(ref) >= 6 and ref[1:].isdigit()):
        return 'Temu'
    
    
    # Boutique / Direct
    if ref.isdigit() or (ref.startswith('BC') or ref.startswith('PH')):
        return 'Nextech Boutique'
    
    return 'Nextech'

def update_managers_from_delivery_notes():
    """
    Met à jour les gestionnaires dans invoices à partir de delivery_notes
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("🔄 MISE À JOUR DES GESTIONNAIRES DEPUIS LES BL")
    print("="*60)
    
    # Vérifier si la table delivery_notes existe
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'delivery_notes'
        )
    """)
    
    if not cursor.fetchone()[0]:
        print("❌ Table 'delivery_notes' non trouvée")
        return 0
    
    # Récupérer tous les BL
    cursor.execute("""
        SELECT order_number, external_reference, shipping_date
        FROM delivery_notes
        WHERE external_reference IS NOT NULL
    """)
    
    bl_list = cursor.fetchall()
    print(f"📋 {len(bl_list)} bons de livraison trouvés")
    
    updated = 0
    for order_number, external_ref, shipping_date in bl_list:
        platform = detect_platform_from_reference(external_ref)
        
        if platform:
            cursor.execute("""
                UPDATE invoices 
                SET 
                    reference_externe = %s,
                    bl_number = %s,
                    shipping_date = %s,
                    gestionnaire = %s
                WHERE order_number = %s
                AND (gestionnaire IS NULL OR gestionnaire = 'Direct' OR gestionnaire = 'Non spécifié')
            """, (external_ref, order_number, shipping_date, platform, order_number))
            
            updated += cursor.rowcount
            if cursor.rowcount > 0:
                print(f"   ✅ {order_number}: {external_ref[:20]}... -> {platform}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\n✅ {updated} factures mises à jour")
    return updated

def update_from_existing_references():
    """
    Met à jour les gestionnaires à partir des références existantes dans invoices
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("🔄 MISE À JOUR DEPUIS LES RÉFÉRENCES EXISTANTES")
    print("="*60)
    
    # Récupérer les factures avec référence mais sans gestionnaire
    cursor.execute("""
        SELECT id, order_number, reference_externe
        FROM invoices
        WHERE reference_externe IS NOT NULL 
        AND reference_externe != ''
        AND (gestionnaire IS NULL OR gestionnaire = 'Direct' OR gestionnaire = 'Non spécifié')
    """)
    
    invoices = cursor.fetchall()
    print(f"📋 {len(invoices)} factures à analyser")
    
    updated = 0
    for inv_id, order_number, reference in invoices:
        platform = detect_platform_from_reference(reference)
        if platform:
            cursor.execute("""
                UPDATE invoices 
                SET gestionnaire = %s
                WHERE id = %s
            """, (platform, inv_id))
            updated += 1
            print(f"   ✅ {order_number}: {reference[:20]}... -> {platform}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\n✅ {updated} factures mises à jour")
    return updated

def show_platform_distribution():
    """Affiche la distribution des plateformes"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    query = """
        SELECT 
            COALESCE(gestionnaire, 'Non défini') as gestionnaire,
            COUNT(*) as nb_factures,
            COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as avec_ref,
            ROUND(SUM(total)::numeric, 2) as ca_total
        FROM invoices
        GROUP BY gestionnaire
        ORDER BY ca_total DESC
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print("\n" + "="*60)
    print("📊 DISTRIBUTION PAR GESTIONNAIRE")
    print("="*60)
    print(df.to_string(index=False))
    
    return df

def show_bl_examples():
    """Affiche des exemples de BL pour vérification"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    query = """
        SELECT order_number, external_reference, shipping_date
        FROM delivery_notes
        WHERE external_reference IS NOT NULL
        LIMIT 20
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print("\n" + "="*60)
    print("📋 EXEMPLES DE BONS DE LIVRAISON")
    print("="*60)
    
    for _, row in df.iterrows():
        platform = detect_platform_from_reference(row['external_reference'])
        print(f"   {row['order_number']}: {row['external_reference'][:30]}... -> {platform}")

def manual_update_by_order():
    """Mise à jour manuelle basée sur les numéros de commande"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("🔧 MISE À JOUR MANUELLE")
    print("="*60)
    
    # Règles basées sur le numéro de commande
    rules = [
        ("S%", "Boutique"),  # Commandes commençant par S
        ("PO-%", "Temu"),
        ("40%", "Amazon"),
        ("SHOP%", "Shopify"),
    ]
    
    updated = 0
    for pattern, platform in rules:
        cursor.execute("""
            UPDATE invoices 
            SET gestionnaire = %s
            WHERE order_number LIKE %s
            AND (gestionnaire IS NULL OR gestionnaire = 'Direct' OR gestionnaire = 'Non spécifié')
        """, (platform, pattern))
        updated += cursor.rowcount
        print(f"   {pattern}: {cursor.rowcount} factures -> {platform}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\n✅ {updated} factures mises à jour par règle")
    return updated

def full_sync():
    """Synchronisation complète"""
    print("\n" + "="*60)
    print("🚀 SYNCHRONISATION COMPLÈTE DES GESTIONNAIRES")
    print("="*60)
    
    # 1. Afficher les exemples de BL
    show_bl_examples()
    
    # 2. Mettre à jour depuis les BL
    count1 = update_managers_from_delivery_notes()
    
    # 3. Mettre à jour depuis les références existantes
    count2 = update_from_existing_references()
    
    # 4. Mise à jour manuelle par règle
    count3 = manual_update_by_order()
    
    # 5. Afficher la distribution finale
    show_platform_distribution()
    
    print("\n" + "="*60)
    print(f"✅ {count1 + count2 + count3} gestionnaires mis à jour")
    print("="*60)

if __name__ == "__main__":
    full_sync()