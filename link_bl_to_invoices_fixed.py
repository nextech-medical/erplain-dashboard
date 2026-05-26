# link_bl_to_invoices_fixed.py
import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def link_bl_to_invoices():
    """Lie les BL aux factures et met à jour les références"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 60)
    print("🔗 LIAISON BL ↔ FACTURES")
    print("=" * 60)
    
    # 1. Voir les BL disponibles
    cursor.execute("""
        SELECT order_number, external_reference 
        FROM delivery_notes 
        WHERE external_reference IS NOT NULL
        LIMIT 10
    """)
    
    print("\n📦 Bons de livraison disponibles:")
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1][:40] if row[1] else 'None'}")
    
    # 2. Mettre à jour les factures avec les références des BL
    print("\n📌 Mise à jour des références...")
    cursor.execute("""
        UPDATE invoices i
        SET reference_externe = dn.external_reference,
            bl_number = dn.order_number,
            updated_at = CURRENT_TIMESTAMP
        FROM delivery_notes dn
        WHERE i.order_number = dn.order_number
        AND dn.external_reference IS NOT NULL
        AND (i.reference_externe IS NULL OR i.reference_externe = '')
    """)
    
    updated = cursor.rowcount
    print(f"   ✅ {updated} factures mises à jour")
    
    # 3. Mettre à jour les gestionnaires
    print("\n📌 Mise à jour des gestionnaires...")
    
    # Amazon
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Amazon'
        WHERE reference_externe ~ '^[0-9]{3}-[0-9]{7}-[0-9]{7}$'
        AND (gestionnaire IS NULL OR gestionnaire = 'Direct')
    """)
    print(f"   ✅ {cursor.rowcount} -> Amazon")
    
    # Temu (PO-)
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Temu'
        WHERE reference_externe LIKE 'PO-%'
        AND (gestionnaire IS NULL OR gestionnaire = 'Direct')
    """)
    print(f"   ✅ {cursor.rowcount} -> Temu")
    
    # Temu (E...)
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Temu'
        WHERE reference_externe LIKE 'E%'
        AND LENGTH(reference_externe) >= 6
        AND reference_externe NOT LIKE 'PO-%'
        AND (gestionnaire IS NULL OR gestionnaire = 'Direct')
    """)
    print(f"   ✅ {cursor.rowcount} -> Temu (format E)")
    
    conn.commit()
    
    # 4. Résultat final
    print("\n📊 RÉSULTAT FINAL:")
    cursor.execute("""
        SELECT 
            gestionnaire,
            COUNT(*) as nb,
            COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as avec_ref
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        GROUP BY gestionnaire
        ORDER BY nb DESC
    """)
    
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]} factures ({row[2]} avec réf)")
    
    cursor.close()
    conn.close()
    
    return updated

if __name__ == "__main__":
    link_bl_to_invoices()