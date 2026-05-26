# extract_external_reference_from_bl.py
import pandas as pd
import re
import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def extract_external_reference(notes_internes):
    """Extrait la référence externe des notes internes du BL."""
    if pd.isna(notes_internes) or not notes_internes:
        return None
    
    notes_str = str(notes_internes)
    
    # Patterns pour trouver les références
    patterns = [
        r'N°Commande\s*:\s*([A-Z0-9\-]+)',  # N°Commande : PO-069-...
        r'ID Commande\s*:\s*([0-9\-]+)',     # ID Commande : 408-4747888-4895520
        r'Commande\s*:\s*([A-Z0-9\-]+)',     # Commande : ...
        r'PO[-\s]*([A-Z0-9]+)',              # PO-069-...
    ]
    
    for pattern in patterns:
        match = re.search(pattern, notes_str, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None

def extract_reference_from_notes(notes):
    """Extrait la référence des notes simples."""
    if pd.isna(notes) or not notes:
        return None
    
    notes_str = str(notes)
    patterns = [
        r'Commande\s*[Nn]°\s*[:\s]*([A-Z0-9\-]+)',
        r'Référence\s*[:\s]*([A-Z0-9\-]+)',
        r'PO[-\s]*([A-Z0-9]+)',
        r'E(\d{6})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, notes_str, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None

def import_bl_and_link_to_invoices(excel_file_path):
    """Importe les BL et lie les références aux factures."""
    
    print(f"📥 Lecture du fichier Excel: {excel_file_path}")
    df = pd.read_excel(excel_file_path)
    
    print(f"   ✅ {len(df)} lignes trouvées")
    print(f"   📋 Colonnes: {list(df.columns)}")
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Créer ou mettre à jour la table des BL
    cursor.execute("DROP TABLE IF EXISTS bl_extracted CASCADE")
    cursor.execute("""
        CREATE TABLE bl_extracted (
            id SERIAL PRIMARY KEY,
            bl_number VARCHAR(50),
            order_number VARCHAR(50),
            client_name TEXT,
            status VARCHAR(50),
            date_creation TIMESTAMP,
            date_livraison DATE,
            plateforme VARCHAR(100),
            external_reference TEXT,
            product_label TEXT,
            product_sku VARCHAR(100),
            quantity INTEGER,
            notes_internes TEXT,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Ajouter la colonne reference_externe à invoices si elle n'existe pas
    cursor.execute("""
        ALTER TABLE invoices 
        ADD COLUMN IF NOT EXISTS reference_externe TEXT,
        ADD COLUMN IF NOT EXISTS bl_number TEXT
    """)
    conn.commit()
    
    bl_count = 0
    link_count = 0
    
    for _, row in df.iterrows():
        try:
            # Extraire la référence externe des notes internes
            notes_internes = row.get('Notes internes')
            external_ref = extract_external_reference(notes_internes)
            
            # Si pas trouvé, essayer dans la colonne "Notes"
            if not external_ref:
                notes = row.get('Notes')
                external_ref = extract_reference_from_notes(notes)
            
            # Si toujours pas trouvé, utiliser la colonne "Référence externe"
            if not external_ref or pd.isna(external_ref):
                external_ref = row.get('Référence externe')
                if pd.isna(external_ref):
                    external_ref = None
            
            order_number = row.get('Numéro de vente')
            
            # Insérer dans la table bl_extracted
            cursor.execute("""
                INSERT INTO bl_extracted (
                    bl_number, order_number, client_name, status,
                    date_creation, date_livraison, plateforme,
                    external_reference, product_label, product_sku,
                    quantity, notes_internes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(row.get('Bon de livraison #')),
                str(order_number) if not pd.isna(order_number) else None,
                str(row.get('Client')) if not pd.isna(row.get('Client')) else None,
                str(row.get('Statut')) if not pd.isna(row.get('Statut')) else None,
                row.get('Date de création'),
                row.get('Date de livraison'),
                str(row.get('Gestionnaire de compte')) if not pd.isna(row.get('Gestionnaire de compte')) else None,
                external_ref,
                str(row.get('Produit')) if not pd.isna(row.get('Produit')) else None,
                str(row.get('SKU')) if not pd.isna(row.get('SKU')) else None,
                int(row.get('Quantité', 0)) if not pd.isna(row.get('Quantité')) else 0,
                notes_internes
            ))
            bl_count += 1
            
            # Lier la référence externe à la facture correspondante
            if external_ref and order_number:
                cursor.execute("""
                    UPDATE invoices 
                    SET reference_externe = %s,
                        bl_number = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE order_number = %s
                    AND (reference_externe IS NULL OR reference_externe = '')
                """, (external_ref, str(row.get('Bon de livraison #')), order_number))
                link_count += cursor.rowcount
            
            if bl_count % 50 == 0:
                print(f"   Traitement: {bl_count} BL...")
                conn.commit()
                
        except Exception as e:
            print(f"❌ Erreur ligne: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\n✅ {bl_count} BL importés")
    print(f"✅ {link_count} factures liées avec référence externe")
    
    return bl_count, link_count

def show_linked_invoices():
    """Affiche les factures avec leurs références externes."""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    query = """
        SELECT order_number, customer_name, reference_externe, bl_number
        FROM invoices 
        WHERE reference_externe IS NOT NULL AND reference_externe != ''
        ORDER BY invoice_created DESC
        LIMIT 20
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df.empty:
        print("\n📋 Factures avec référence externe:")
        print(df.to_string(index=False))
    else:
        print("\n⚠️ Aucune facture avec référence externe")

def show_statistics():
    """Affiche les statistiques."""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM invoices WHERE reference_externe IS NOT NULL AND reference_externe != ''")
    with_ref = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM bl_extracted")
    total_bl = cursor.fetchone()[0]
    
    cursor.close()
    conn.close()
    
    print("\n" + "="*50)
    print("📊 STATISTIQUES")
    print("="*50)
    print(f"   📦 BL importés: {total_bl}")
    print(f"   🏷️ Factures avec référence externe: {with_ref}")
    print("="*50)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        excel_file = sys.argv[1]
    else:
        excel_file = "2026-05-16T11-40-30-Bons de livraison.xlsx"
    
    print("\n" + "="*60)
    print("🔄 EXTRACTION DES RÉFÉRENCES EXTERNES DES BL")
    print("="*60)
    
    # Importer les BL et lier aux factures
    bl_count, link_count = import_bl_and_link_to_invoices(excel_file)
    
    # Afficher les statistiques
    show_statistics()
    
    # Afficher les factures liées
    show_linked_invoices()
    
    print("\n" + "="*60)
    print("✅ Opération terminée")
    print("="*60)