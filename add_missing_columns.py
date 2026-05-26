# add_all_columns.py
import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def add_all_columns():
    """Ajoute toutes les colonnes nécessaires aux tables"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Colonnes pour la table invoices
    invoices_columns = [
        ("customer_name", "TEXT"),
        ("customer_email", "TEXT"),
        ("reference_externe", "TEXT"),
        ("bl_number", "TEXT"),
        ("bl_id", "TEXT"),
        ("bl_status", "TEXT"),
        ("shipping_date", "DATE"),
        ("tracking_number", "TEXT"),
        ("carrier", "TEXT"),
        ("fournisseur", "TEXT"),
        ("gestionnaire", "TEXT"),
    ]
    
    print("🔧 Ajout des colonnes à la table invoices...")
    for col_name, col_type in invoices_columns:
        try:
            cursor.execute(f"ALTER TABLE invoices ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
            print(f"   ✅ {col_name} ajoutée")
        except Exception as e:
            print(f"   ⚠️ {col_name}: {e}")
    
    # Colonnes pour la table invoice_lines
    lines_columns = [
        ("poids_unitaire", "DECIMAL(10,2)"),
        ("frais_transport", "DECIMAL(10,2)"),
    ]
    
    print("\n🔧 Ajout des colonnes à la table invoice_lines...")
    for col_name, col_type in lines_columns:
        try:
            cursor.execute(f"ALTER TABLE invoice_lines ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
            print(f"   ✅ {col_name} ajoutée")
        except Exception as e:
            print(f"   ⚠️ {col_name}: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print("\n✅ Toutes les colonnes ont été ajoutées")

if __name__ == "__main__":
    add_all_columns()