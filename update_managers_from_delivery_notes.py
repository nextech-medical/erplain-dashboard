# update_managers_complete.py
"""
Script complet pour mettre à jour les gestionnaires/plateformes
à partir des références externes et des bons de livraison
"""
import psycopg2
import re
import pandas as pd
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def detect_platform_from_reference(reference):
    """Détecte la plateforme à partir de la référence externe"""
    if not reference:
        return None
    
    ref = str(reference).upper()
    
    # Amazon: 40X-XXXXXXX-XXXXXXX (ex: 408-6188742-3458704)
    if re.match(r'^40\d-\d{7}-\d{7}$', ref):
        return 'Amazon'
    
    # Amazon: autre format avec tirets (ex: 402-6063336-8998700)
    if ref.count('-') >= 2 and len(ref) > 15:
        return 'Amazon'
    
    # Temu: PO-XXXXX (ex: PO-12345678)
    if ref.startswith('PO-'):
        return 'Temu'
    
    # Temu: EXXXXXX (ex: E157353)
    if ref.startswith('E') and len(ref) >= 6 and ref[1:].isdigit():
        return 'Temu'
    
    # Shopify
    if 'SHOP' in ref:
        return 'Shopify'
    
    return None

def extract_reference_from_notes(notes):
    """Extrait la référence externe des notes HTML"""
    if not notes:
        return None
    
    # Nettoyer le HTML
    clean_notes = re.sub(r'<[^>]+>', ' ', notes)
    clean_notes = re.sub(r'&[a-z]+;', ' ', clean_notes)
    clean_notes = re.sub(r'\s+', ' ', clean_notes)
    
    # Patterns pour trouver les références
    patterns = [
        r'ID Commande.*?(\d{3}-\d{7}-\d{7})',
        r'Commande\s*[Nn]°?\s*[:\s]*([A-Z0-9\-/]+)',
        r'N°\s*d\'engagement\s*:\s*([A-Z0-9]+)',
        r'bon de commande\s*[Nn]°?\s*[:\s]*([A-Z0-9\-/]+)',
        r'Référence\s*[:\s]*([A-Z0-9\-]+)',
        r'PO[-\s]*([A-Z0-9]+)',
        r'E(\d{6,})',
        r'BC[-\s]*([A-Z0-9]+)',
        r'(\d{3}-\d{7}-\d{7})',  # Format Amazon
    ]
    
    for pattern in patterns:
        match = re.search(pattern, clean_notes, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None

def update_references_from_notes():
    """Extrait les références externes depuis les notes des factures"""
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
    print(f"📋 {len(invoices)} factures sans référence externe")
    
    updated = 0
    for inv_id, order_number, notes in invoices:
        reference = extract_reference_from_notes(notes)
        if reference:
            cursor.execute("""
                UPDATE invoices 
                SET reference_externe = %s
                WHERE id = %s
            """, (reference, inv_id))
            updated += 1
            
            if updated % 50 == 0:
                print(f"   {updated} références extraites...")
                conn.commit()
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ {updated} références externes extraites")
    return updated

def update_managers_from_references():
    """Met à jour les gestionnaires à partir des références externes"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Récupérer les références à analyser
    cursor.execute("""
        SELECT id, order_number, reference_externe, gestionnaire
        FROM invoices
        WHERE reference_externe IS NOT NULL 
        AND reference_externe != ''
    """)
    
    invoices = cursor.fetchall()
    print(f"📋 {len(invoices)} factures avec référence externe")
    
    updated = 0
    for inv_id, order_number, reference, current_manager in invoices:
        # Si déjà un gestionnaire spécifique (pas Direct), on garde
        if current_manager and current_manager not in ['Direct', 'Non spécifié', None, '']:
            continue
        
        platform = detect_platform_from_reference(reference)
        if platform:
            cursor.execute("""
                UPDATE invoices 
                SET gestionnaire = %s
                WHERE id = %s
            """, (platform, inv_id))
            updated += 1
            print(f"   {order_number}: {reference[:20]}... -> {platform}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ {updated} gestionnaires mis à jour")
    return updated

def update_from_delivery_notes():
    """Met à jour depuis la table delivery_notes"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Vérifier si delivery_notes existe
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'delivery_notes'
        )
    """)
    
    if not cursor.fetchone()[0]:
        print("⚠️ Table delivery_notes non trouvée")
        return 0
    
    # Mettre à jour depuis delivery_notes
    cursor.execute("""
        UPDATE invoices i
        SET gestionnaire = 
            CASE 
                WHEN dn.external_reference LIKE '40%' THEN 'Amazon'
                WHEN dn.external_reference LIKE 'PO-%' THEN 'Temu'
                WHEN dn.external_reference LIKE 'E%' THEN 'Temu'
                WHEN dn.external_reference LIKE 'SHOP%' THEN 'Shopify'
                ELSE i.gestionnaire
            END
        FROM delivery_notes dn
        WHERE i.order_number = dn.order_number
        AND i.reference_externe IS NOT NULL
        AND i.reference_externe != ''
        AND (i.gestionnaire IS NULL OR i.gestionnaire IN ('Direct', 'Non spécifié', ''))
    """)
    
    updated = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ {updated} factures mises à jour depuis delivery_notes")
    return updated

def show_detailed_stats():
    """Affiche les statistiques détaillées"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    # Distribution par gestionnaire
    print("\n" + "="*60)
    print("📊 DISTRIBUTION PAR GESTIONNAIRE")
    print("="*60)
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            gestionnaire,
            COUNT(*) as nb_factures,
            ROUND(SUM(total)::numeric, 2) as ca_total
        FROM invoices
        WHERE gestionnaire IS NOT NULL
        GROUP BY gestionnaire
        ORDER BY ca_total DESC
    """)
    
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]} factures, {row[2]:,.2f} €")
    
    # Analyse par type de référence
    print("\n" + "="*60)
    print("📊 ANALYSE PAR TYPE DE RÉFÉRENCE")
    print("="*60)
    
    cursor.execute("""
        SELECT 
            CASE 
                WHEN reference_externe LIKE '40%' THEN 'Amazon (40X)'
                WHEN reference_externe LIKE 'PO-%' THEN 'Temu (PO)'
                WHEN reference_externe LIKE 'E%' THEN 'Temu (E)'
                WHEN reference_externe LIKE 'SHOP%' THEN 'Shopify'
                WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 'Autre'
                ELSE 'Sans référence'
            END as type_ref,
            COUNT(*) as nb,
            COUNT(CASE WHEN gestionnaire NOT IN ('Direct', 'Non spécifié') THEN 1 END) as avec_bon_gest,
            ROUND(SUM(total)::numeric, 2) as ca
        FROM invoices
        GROUP BY type_ref
        ORDER BY ca DESC
    """)
    
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]} factures, CA: {row[3]:,.2f} €")
    
    # Afficher les références non catégorisées
    cursor.execute("""
        SELECT order_number, reference_externe, gestionnaire
        FROM invoices
        WHERE reference_externe IS NOT NULL 
        AND reference_externe != ''
        AND reference_externe NOT LIKE '40%'
        AND reference_externe NOT LIKE 'PO-%'
        AND reference_externe NOT LIKE 'E%'
        AND reference_externe NOT LIKE 'SHOP%'
        LIMIT 10
    """)
    
    unknown = cursor.fetchall()
    if unknown:
        print("\n📋 Exemples de références non catégorisées:")
        for row in unknown:
            print(f"   {row[0]}: {row[1][:30]}... -> gestionnaire: {row[2]}")
    
    cursor.close()
    conn.close()

def show_current_data():
    """Affiche les données actuelles pour debug"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT order_number, reference_externe, gestionnaire
        FROM invoices
        WHERE reference_externe IS NOT NULL AND reference_externe != ''
        LIMIT 15
    """)
    
    print("\n" + "="*60)
    print("📋 EXEMPLES DE FACTURES AVEC RÉFÉRENCE")
    print("="*60)
    
    for row in cursor.fetchall():
        order = row[0]
        ref = row[1]
        current = row[2]
        detected = detect_platform_from_reference(ref)
        print(f"   {order}: {ref}")
        print(f"      → Plateforme détectée: {detected}")
        print(f"      → Gestionnaire actuel: {current}")
        print()
    
    cursor.close()
    conn.close()

def reset_managers():
    """Réinitialise les gestionnaires pour les recalculer"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Mettre à NULL les gestionnaires 'Direct' et 'Non spécifié'
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = NULL
        WHERE gestionnaire IN ('Direct', 'Non spécifié')
    """)
    
    count = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ {count} gestionnaires réinitialisés")
    return count

def set_default_managers():
    """Définit 'Direct' comme valeur par défaut pour les factures sans gestionnaire"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Direct'
        WHERE gestionnaire IS NULL
    """)
    
    count = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ {count} factures définies comme 'Direct'")
    return count

def sync_all():
    """Synchronisation complète"""
    print("\n" + "="*60)
    print("🔄 SYNCHRONISATION COMPLÈTE DES GESTIONNAIRES")
    print("="*60)
    
    # 1. Vérifier l'état actuel
    print("\n📊 État avant mise à jour:")
    show_detailed_stats()
    
    # 2. Extraire les références des notes
    print("\n📝 Extraction des références externes...")
    ref_count = update_references_from_notes()
    
    # 3. Mettre à jour les gestionnaires depuis les références
    print("\n🏭 Mise à jour des gestionnaires depuis les références...")
    managers_count = update_managers_from_references()
    
    # 4. Mettre à jour depuis delivery_notes
    print("\n📦 Mise à jour depuis les bons de livraison...")
    dn_count = update_from_delivery_notes()
    
    # 5. Définir les valeurs par défaut
    print("\n📝 Définition des valeurs par défaut...")
    default_count = set_default_managers()
    
    # 6. Afficher les résultats
    print("\n📊 État après mise à jour:")
    show_detailed_stats()
    
    print("\n" + "="*60)
    print(f"✅ {ref_count} références extraites")
    print(f"✅ {managers_count} gestionnaires mis à jour via références")
    print(f"✅ {dn_count} gestionnaires mis à jour via delivery_notes")
    print(f"✅ {default_count} valeurs par défaut définies")
    print("="*60)

def quick_sync():
    """Synchronisation rapide (sans réinitialisation)"""
    print("\n" + "="*60)
    print("🔄 SYNCHRONISATION RAPIDE DES GESTIONNAIRES")
    print("="*60)
    
    # Extraire les références
    ref_count = update_references_from_notes()
    
    # Mettre à jour les gestionnaires
    managers_count = update_managers_from_references()
    
    # Afficher les résultats
    show_detailed_stats()
    
    print("\n" + "="*60)
    print(f"✅ {ref_count} références extraites")
    print(f"✅ {managers_count} gestionnaires mis à jour")
    print("="*60)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--show":
            show_current_data()
        elif sys.argv[1] == "--reset":
            reset_managers()
        elif sys.argv[1] == "--stats":
            show_detailed_stats()
        elif sys.argv[1] == "--quick":
            quick_sync()
        else:
            print("Usage: python update_managers_complete.py [--show] [--reset] [--stats] [--quick]")
    else:
        sync_all()