# fix_references_2026.py
import re
import psycopg2
import pandas as pd
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def extract_reference_from_notes(notes):
    """Extrait la référence externe des notes."""
    
    if not notes:
        return None
    
    # Nettoyer le HTML
    clean_notes = re.sub(r'<[^>]+>', ' ', notes)
    
    patterns = [
        r'Commande\s*[Nn]°?\s*[:\s]*([A-Z0-9\-]+)',
        r'Référence\s*[:\s]*([A-Z0-9\-]+)',
        r'PO[-\s]*([A-Z0-9]+)',
        r'E(\d{6})',
        r'N°\s*d\'engagement\s*:\s*([A-Z0-9]+)',
        r'bon de commande\s*[Nn]°?\s*[:\s]*([A-Z0-9\-]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, clean_notes, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None

def update_references_2026():
    """Met à jour les références des factures 2026."""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Récupérer les factures 2026 sans référence
    cursor.execute("""
        SELECT id, order_number, notes 
        FROM invoices 
        WHERE EXTRACT(YEAR FROM invoice_created) = 2026
        AND (reference_externe IS NULL OR reference_externe = '')
        AND notes IS NOT NULL
    """)
    
    invoices = cursor.fetchall()
    
    count = 0
    for inv_id, order_number, notes in invoices:
        reference = extract_reference_from_notes(notes)
        if reference:
            cursor.execute("""
                UPDATE invoices 
                SET reference_externe = %s
                WHERE id = %s
            """, (reference, inv_id))
            count += 1
            
            if count % 10 == 0:
                print(f"   {count} références trouvées...")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ {count} références externes ajoutées pour 2026")
    return count

def show_statistics_2026():
    """Affiche les statistiques 2026."""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    query = """
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as with_ref,
            MIN(invoice_created) as first_date,
            MAX(invoice_created) as last_date
        FROM invoices
        WHERE EXTRACT(YEAR FROM invoice_created) = 2026
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print("\n" + "="*50)
    print("📊 STATISTIQUES 2026")
    print("="*50)
    print(f"   📄 Total factures 2026: {df['total'].iloc[0]}")
    print(f"   🏷️ Avec référence externe: {df['with_ref'].iloc[0]}")
    print(f"   📅 Période: {df['first_date'].iloc[0]} au {df['last_date'].iloc[0]}")
    print("="*50)

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔄 CORRECTION RÉFÉRENCES 2026")
    print("="*60)
    
    count = update_references_2026()
    show_statistics_2026()
    
    print("="*60)
    print(f"✅ {count} références mises à jour")
    print("="*60)