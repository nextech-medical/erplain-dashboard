# update_references_from_bl.py
import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def update_references_and_managers():
    """Met à jour les références externes et les gestionnaires depuis les BL"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 60)
    print("🔄 MISE À JOUR DEPUIS LES BONS DE LIVRAISON")
    print("=" * 60)
    
    # Vérifier si delivery_notes existe
    cursor.execute("""
        SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'delivery_notes')
    """)
    
    if not cursor.fetchone()[0]:
        print("❌ Table 'delivery_notes' non trouvée")
        print("   Importez d'abord les BL avec fetch_delivery_notes.py")
        return 0
    
    # 1. Mettre à jour les références externes
    print("\n📌 Mise à jour des références externes...")
    cursor.execute("""
        UPDATE invoices i
        SET reference_externe = dn.external_reference
        FROM delivery_notes dn
        WHERE i.order_number = dn.order_number
        AND i.reference_externe IS NULL
        AND dn.external_reference IS NOT NULL
    """)
    
    updated_refs = cursor.rowcount
    print(f"   ✅ {updated_refs} factures mises à jour avec référence externe")
    
    # 2. Mettre à jour les gestionnaires basés sur les références
    print("\n📌 Mise à jour des gestionnaires...")
    
    # Amazon: format 123-1234567-1234567
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Amazon'
        WHERE reference_externe ~ '^[0-9]{3}-[0-9]{7}-[0-9]{7}$'
        AND (gestionnaire IS NULL OR gestionnaire = 'Direct')
    """)
    print(f"   ✅ {cursor.rowcount} factures -> Amazon")
    
    # Temu: PO-...
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Temu'
        WHERE reference_externe LIKE 'PO-%'
        AND (gestionnaire IS NULL OR gestionnaire = 'Direct')
    """)
    print(f"   ✅ {cursor.rowcount} factures -> Temu")
    
    # Temu: E...
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Temu'
        WHERE reference_externe LIKE 'E%'
        AND LENGTH(reference_externe) >= 6
        AND (gestionnaire IS NULL OR gestionnaire = 'Direct')
    """)
    print(f"   ✅ {cursor.rowcount} factures -> Temu")
    
    # Boutique
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Boutique'
        WHERE reference_externe LIKE 'BC%' 
        OR reference_externe LIKE 'PH%'
        OR reference_externe LIKE 'SHOP%'
        AND (gestionnaire IS NULL OR gestionnaire = 'Direct')
    """)
    print(f"   ✅ {cursor.rowcount} factures -> Boutique")
    
    conn.commit()
    
    # 3. Résultat final
    print("\n📊 ÉTAT FINAL:")
    cursor.execute("""
        SELECT 
            gestionnaire,
            COUNT(*) as nb,
            COUNT(CASE WHEN reference_externe IS NOT NULL THEN 1 END) as avec_ref
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        GROUP BY gestionnaire
        ORDER BY nb DESC
    """)
    
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]} factures ({row[2]} avec réf)")
    
    cursor.close()
    conn.close()
    
    return updated_refs

if __name__ == "__main__":
    update_references_and_managers()