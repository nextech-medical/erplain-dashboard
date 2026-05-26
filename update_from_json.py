# update_from_json.py
import json
import psycopg2
import re
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def detect_platform(reference):
    """Détecte la plateforme à partir de la référence"""
    if not reference:
        return None
    
    ref = str(reference)
    
    # Amazon: 123-1234567-1234567
    if re.match(r'^\d{3}-\d{7}-\d{7}$', ref):
        return 'Amazon'
    
    # Temu: PO-...
    if ref.startswith('PO-'):
        return 'Temu'
    
    # Temu: E...
    if ref.startswith('E') and len(ref) >= 6 and ref[1:].isdigit():
        return 'Temu'
    
    return None

def update_from_json():
    """Met à jour les factures depuis le fichier JSON"""
    
    # Charger le JSON
    try:
        with open('factures_depuis_2026.json', 'r', encoding='utf-8') as f:
            invoices = json.load(f)
        print(f"📁 {len(invoices)} factures chargées")
    except FileNotFoundError:
        print("❌ Fichier factures_depuis_2026.json non trouvé")
        print("   Exécutez d'abord: python get_invoices.py")
        return 0
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 60)
    print("🔄 MISE À JOUR DEPUIS LE JSON")
    print("=" * 60)
    
    updated_refs = 0
    updated_managers = 0
    
    for inv in invoices:
        invoice_id = str(inv.get('id'))
        # Utiliser external_reference (le bon nom de champ)
        external_ref = inv.get('external_reference')
        order_number = inv.get('order_number')
        label = inv.get('label')
        
        if external_ref and external_ref != 'None':
            platform = detect_platform(external_ref)
            
            # Mettre à jour la référence
            cursor.execute("""
                UPDATE invoices 
                SET reference_externe = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s 
                AND (reference_externe IS NULL OR reference_externe = '')
            """, (external_ref, invoice_id))
            
            if cursor.rowcount > 0:
                updated_refs += 1
                
                # Mettre à jour le gestionnaire
                if platform:
                    cursor.execute("""
                        UPDATE invoices 
                        SET gestionnaire = %s
                        WHERE id = %s 
                        AND (gestionnaire IS NULL OR gestionnaire = 'Direct')
                    """, (platform, invoice_id))
                    if cursor.rowcount > 0:
                        updated_managers += 1
                
                if updated_refs <= 30:
                    print(f"   ✅ {order_number or label}: {external_ref[:40]} -> {platform or '?'}")
    
    conn.commit()
    
    # Statistiques finales
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as avec_ref,
            COUNT(CASE WHEN gestionnaire = 'Amazon' THEN 1 END) as amazon,
            COUNT(CASE WHEN gestionnaire = 'Temu' THEN 1 END) as temu,
            COUNT(CASE WHEN gestionnaire = 'Direct' THEN 1 END) as direct
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
    """)
    
    row = cursor.fetchone()
    print(f"\n📊 RÉSULTAT FINAL:")
    print(f"   Total factures: {row[0]}")
    print(f"   Avec référence: {row[1]}")
    print(f"   Amazon: {row[2]}")
    print(f"   Temu: {row[3]}")
    print(f"   Direct: {row[4]}")
    
    cursor.close()
    conn.close()
    
    return updated_refs

def show_missing_examples():
    """Affiche les factures sans référence"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    print("\n" + "=" * 60)
    print("📋 FACTURES SANS RÉFÉRENCE (20 premiers)")
    print("=" * 60)
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT order_number, label, invoice_created
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        AND (reference_externe IS NULL OR reference_externe = '')
        LIMIT 20
    """)
    
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]} ({row[2]})")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--missing":
        show_missing_examples()
    else:
        updated = update_from_json()
        print(f"\n✅ {updated} factures mises à jour")
        show_missing_examples()