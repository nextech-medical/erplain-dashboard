# extract_references_auto.py
"""
Script pour extraire automatiquement les références externes depuis les notes des factures
"""
import psycopg2
import re
import pandas as pd
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def extract_reference_from_notes(notes):
    """
    Extrait la référence externe des notes HTML
    """
    if not notes:
        return None
    
    # Nettoyer le HTML
    clean_notes = re.sub(r'<[^>]+>', ' ', notes)
    clean_notes = re.sub(r'&[a-z]+;', ' ', clean_notes)
    clean_notes = re.sub(r'\s+', ' ', clean_notes)
    
    # Patterns pour trouver les références (par ordre de priorité)
    patterns = [
        # Pattern pour "Commande n°XXXXX" ou "bon de commande n°XXXXX"
        r'(?:Commande|bon de commande)\s*[Nn]°?\s*[:\s]*([A-Z0-9\-/]+)',
        
        # Pattern pour "N° d'engagement : XXXXX"
        r'N°\s*d\'engagement\s*:\s*([A-Z0-9]+)',
        
        # Pattern pour "Référence : XXXXX"
        r'Référence\s*[:\s]*([A-Z0-9\-]+)',
        
        # Pattern pour PO-XXXXX (Temu)
        r'PO[-\s]*([A-Z0-9]+)',
        
        # Pattern pour EXXXXXX (Temu)
        r'E(\d{6,})',
        
        # Pattern pour BCXXXXX
        r'BC[-\s]*([A-Z0-9]+)',
        
        # Pattern pour référence Amazon (format 40X-XXXXX-XXXXX)
        r'(\d{3}-\d{7}-\d{7})',
        
        # Pattern pour référence Amazon (format 40X-XXXXXXX-XXXXXXX)
        r'(\d{3}-\d{7,8}-\d{7,8})',
        
        # Pattern générique pour tout nombre avec tirets
        r'([0-9]{3,}[-/][0-9]{3,})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, clean_notes, re.IGNORECASE)
        if match:
            return match.group(1)
    
    # Chercher des patterns spécifiques dans le texte
    # Pour Amazon
    if 'amazon' in clean_notes.lower():
        amazon_match = re.search(r'(\d{3}-\d{7}-\d{7})', clean_notes)
        if amazon_match:
            return amazon_match.group(1)
    
    # Pour Temu
    if 'temu' in clean_notes.lower() or 'po-' in clean_notes.lower():
        temu_match = re.search(r'(PO-?\s*[A-Z0-9]+)', clean_notes, re.IGNORECASE)
        if temu_match:
            return temu_match.group(1)
    
    return None

def extract_bl_number_from_notes(notes):
    """
    Extrait le numéro de bon de livraison des notes
    """
    if not notes:
        return None
    
    clean_notes = re.sub(r'<[^>]+>', ' ', notes)
    clean_notes = re.sub(r'&[a-z]+;', ' ', clean_notes)
    
    patterns = [
        r'BL\s*[Nn]°?\s*[:\s]*([A-Z0-9\-]+)',
        r'N°\s*BL\s*[:\s]*([A-Z0-9\-]+)',
        r'Bon de livraison\s*[Nn]°?\s*[:\s]*([A-Z0-9\-]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, clean_notes, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None

def detect_platform_from_reference(reference):
    """
    Détecte la plateforme à partir de la référence externe
    """
    if not reference:
        return None
    
    ref = str(reference).upper()
    
    # Amazon: 40X-XXXXXXX-XXXXXXX ou contient des tirets
    if re.match(r'^40\d-\d{7}-\d{7}$', ref) or (ref.count('-') >= 2 and len(ref) > 15):
        return 'Amazon'
    
    # Temu: PO-XXXXX ou EXXXXXX
    if ref.startswith('PO-') or (ref.startswith('E') and len(ref) >= 6 and ref[1:].isdigit()):
        return 'Temu'
    
    # Shopify: SHOP-XXXXX
    if ref.startswith('SHOP') or 'SHOP' in ref:
        return 'Shopify'
    
    return None

def extract_references_from_all_invoices():
    """
    Extrait les références de toutes les factures qui en sont dépourvues
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Récupérer les factures sans référence externe
    cursor.execute("""
        SELECT id, order_number, notes_text
        FROM invoices
        WHERE (reference_externe IS NULL OR reference_externe = '')
        AND notes_text IS NOT NULL
        AND notes_text != ''
    """)
    
    invoices = cursor.fetchall()
    print(f"📋 {len(invoices)} factures sans référence externe trouvées")
    
    count = 0
    for inv_id, order_number, notes in invoices:
        reference = extract_reference_from_notes(notes)
        if reference:
            cursor.execute("""
                UPDATE invoices 
                SET reference_externe = %s,
                    gestionnaire = COALESCE(gestionnaire, %s)
                WHERE id = %s
            """, (reference, detect_platform_from_reference(reference), inv_id))
            count += 1
            
            if count % 50 == 0:
                print(f"   {count} références extraites...")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ {count} références externes extraites")
    return count

def extract_bl_numbers_from_all_invoices():
    """
    Extrait les numéros de BL de toutes les factures qui en sont dépourvues
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Récupérer les factures sans BL
    cursor.execute("""
        SELECT id, order_number, notes_text
        FROM invoices
        WHERE (bl_number IS NULL OR bl_number = '')
        AND notes_text IS NOT NULL
        AND notes_text != ''
    """)
    
    invoices = cursor.fetchall()
    print(f"📋 {len(invoices)} factures sans BL trouvées")
    
    count = 0
    for inv_id, order_number, notes in invoices:
        bl_number = extract_bl_number_from_notes(notes)
        if bl_number:
            cursor.execute("""
                UPDATE invoices 
                SET bl_number = %s
                WHERE id = %s
            """, (bl_number, inv_id))
            count += 1
            
            if count % 50 == 0:
                print(f"   {count} BL extraits...")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ {count} BL extraits")
    return count

def update_platforms_from_references():
    """
    Met à jour les plateformes (gestionnaires) à partir des références externes
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Amazon
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Amazon'
        WHERE (gestionnaire IS NULL OR gestionnaire = 'Non spécifié')
        AND reference_externe IS NOT NULL
        AND reference_externe != ''
        AND reference_externe ~ '^40\d-\d{7}-\d{7}$'
    """)
    print(f"   Amazon: {cursor.rowcount} factures")
    
    # Temu
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Temu'
        WHERE (gestionnaire IS NULL OR gestionnaire = 'Non spécifié')
        AND reference_externe IS NOT NULL
        AND reference_externe != ''
        AND (reference_externe LIKE 'PO-%' OR reference_externe LIKE 'E%')
    """)
    print(f"   Temu: {cursor.rowcount} factures")
    
    # Shopify
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Shopify'
        WHERE (gestionnaire IS NULL OR gestionnaire = 'Non spécifié')
        AND reference_externe IS NOT NULL
        AND reference_externe != ''
        AND reference_externe LIKE 'SHOP%'
    """)
    print(f"   Shopify: {cursor.rowcount} factures")
    
    conn.commit()
    cursor.close()
    conn.close()

def show_statistics():
    """
    Affiche les statistiques après extraction
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    # Statistiques des références
    df_ref = pd.read_sql_query("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as with_ref,
            COUNT(CASE WHEN bl_number IS NOT NULL AND bl_number != '' THEN 1 END) as with_bl,
            COUNT(CASE WHEN gestionnaire IS NOT NULL AND gestionnaire != 'Non spécifié' THEN 1 END) as with_platform
        FROM invoices
    """, conn)
    
    # Distribution des plateformes
    df_platforms = pd.read_sql_query("""
        SELECT 
            gestionnaire,
            COUNT(*) as nb_factures,
            ROUND(SUM(total)::numeric, 2) as ca_total
        FROM invoices
        WHERE gestionnaire IS NOT NULL AND gestionnaire != 'Non spécifié'
        GROUP BY gestionnaire
        ORDER BY ca_total DESC
    """, conn)
    
    # Exemples de références
    df_examples = pd.read_sql_query("""
        SELECT order_number, reference_externe, gestionnaire
        FROM invoices
        WHERE reference_externe IS NOT NULL AND reference_externe != ''
        LIMIT 10
    """, conn)
    
    conn.close()
    
    print("\n" + "="*60)
    print("📊 STATISTIQUES APRÈS EXTRACTION")
    print("="*60)
    print(f"   📄 Total factures: {df_ref['total'].iloc[0]}")
    print(f"   🏷️ Avec référence externe: {df_ref['with_ref'].iloc[0]}")
    print(f"   🚚 Avec BL: {df_ref['with_bl'].iloc[0]}")
    print(f"   📱 Avec plateforme: {df_ref['with_platform'].iloc[0]}")
    
    if not df_platforms.empty:
        print("\n📱 Distribution par plateforme:")
        for _, row in df_platforms.iterrows():
            print(f"   - {row['gestionnaire']}: {row['nb_factures']} factures, {row['ca_total']:,.2f} €")
    
    if not df_examples.empty:
        print("\n📋 Exemples de références extraites:")
        print(df_examples.to_string(index=False))
    
    print("="*60)

def sync_all_references():
    """
    Synchronisation complète des références
    """
    print("\n" + "="*60)
    print("🔄 EXTRACTION AUTOMATIQUE DES RÉFÉRENCES")
    print("="*60)
    
    # 1. Extraire les références externes
    print("\n📝 Extraction des références externes...")
    ref_count = extract_references_from_all_invoices()
    
    # 2. Extraire les BL
    print("\n📝 Extraction des numéros de BL...")
    bl_count = extract_bl_numbers_from_all_invoices()
    
    # 3. Mettre à jour les plateformes
    print("\n📱 Mise à jour des plateformes...")
    update_platforms_from_references()
    
    # 4. Afficher les statistiques
    show_statistics()
    
    print("\n" + "="*60)
    print(f"✅ {ref_count} références et {bl_count} BL extraits")
    print("="*60)

def test_extraction_on_notes():
    """
    Teste l'extraction sur quelques notes d'exemple
    """
    test_notes = [
        '<p>Commande n°24000305 du 16/01/2024<br />Contact : Mme Christine MONTES</p>',
        '<p>Commande n°5299 du 17/01/2024<br />Contact : SAUMET Amandine</p>',
        '<p>PO-12345678 du 15/01/2024</p>',
        '<p>Référence : 24001078</p>',
        '<p>N° d\'engagement : E157353</p>',
    ]
    
    print("\n" + "="*60)
    print("🧪 TEST D'EXTRACTION")
    print("="*60)
    
    for note in test_notes:
        ref = extract_reference_from_notes(note)
        platform = detect_platform_from_reference(ref)
        print(f"Note: {note[:50]}...")
        print(f"   Référence: {ref}")
        print(f"   Plateforme: {platform}")
        print()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            test_extraction_on_notes()
        elif sys.argv[1] == "--stats":
            show_statistics()
        else:
            print("Usage: python extract_references_auto.py [--test] [--stats]")
    else:
        sync_all_references()