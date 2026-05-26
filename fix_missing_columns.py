# fix_all_missing_columns.py
import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def fix_all_columns():
    """Ajoute toutes les colonnes manquantes"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Liste complète des colonnes à ajouter
    columns_to_add = [
        ("customer_name", "TEXT"),
        ("customer_email", "TEXT"),
        ("reference_externe", "TEXT"),
        ("bl_number", "TEXT"),
        ("fournisseur", "TEXT"),
        ("gestionnaire", "TEXT"),
        ("notes_text", "TEXT"),
        ("shipping_date", "DATE"),
        ("delivery_note_id", "TEXT"),
    ]
    
    print("🔧 Ajout des colonnes manquantes à la table invoices...")
    print("="*50)
    
    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE invoices ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
            print(f"   ✅ Colonne '{col_name}' ajoutée")
        except Exception as e:
            print(f"   ⚠️ Colonne '{col_name}': {e}")
    
    # Ajouter les colonnes à invoice_lines si nécessaire
    lines_columns = [
        ("discount", "DECIMAL(10,2) DEFAULT 0"),
    ]
    
    print("\n🔧 Ajout des colonnes à invoice_lines...")
    for col_name, col_type in lines_columns:
        try:
            cursor.execute(f"ALTER TABLE invoice_lines ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
            print(f"   ✅ Colonne '{col_name}' ajoutée")
        except Exception as e:
            print(f"   ⚠️ Colonne '{col_name}': {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print("="*50)
    print("✅ Toutes les colonnes ont été ajoutées")

def verify_columns():
    """Vérifie les colonnes existantes"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'invoices'
        ORDER BY ordinal_position
    """)
    
    columns = cursor.fetchall()
    print("\n📋 Colonnes dans la table invoices:")
    print("="*50)
    for col in columns:
        print(f"   - {col[0]} ({col[1]})")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    fix_all_columns()
    verify_columns()