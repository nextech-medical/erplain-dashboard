# fix_all_columns.py
import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def add_all_missing_columns():
    """Ajoute toutes les colonnes manquantes à la table invoices."""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Toutes les colonnes nécessaires pour le dashboard
    columns = [
        ("customer_name", "TEXT"),
        ("customer_email", "TEXT"),
        ("reference_externe", "TEXT"),
        ("bon_de_commande", "TEXT"),
        ("facturation_adresse", "TEXT"),
        ("facturation_code_postal", "VARCHAR(20)"),
        ("facturation_ville", "VARCHAR(100)"),
        ("facturation_pays", "VARCHAR(100)"),
        ("notes_internes", "TEXT"),
        ("conditions_ventes", "TEXT"),
        ("fournisseur", "TEXT"),
        ("gestionnaire", "TEXT"),
        ("quantite_total", "INTEGER"),
        ("delivery_note_id", "TEXT"),
        ("tracking_number", "TEXT"),
        ("carrier", "TEXT"),
        ("shipping_date", "DATE"),
        ("shipping_cost", "DECIMAL(10,2)"),
    ]
    
    print("🔧 Ajout des colonnes manquantes à la table invoices...")
    print("="*50)
    
    added_count = 0
    for col_name, col_type in columns:
        try:
            cursor.execute(f"""
                ALTER TABLE invoices 
                ADD COLUMN IF NOT EXISTS {col_name} {col_type}
            """)
            print(f"   ✅ Colonne '{col_name}' ajoutée")
            added_count += 1
        except Exception as e:
            print(f"   ❌ Erreur pour {col_name}: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print("="*50)
    print(f"✅ {added_count} colonnes ajoutées / vérifiées")
    print("="*50)

def verify_columns():
    """Vérifie quelles colonnes existent maintenant."""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'invoices'
        ORDER BY ordinal_position
    """)
    
    columns = cursor.fetchall()
    cursor.close()
    conn.close()
    
    print("\n📋 Colonnes existantes dans la table invoices:")
    print("="*50)
    for col in columns:
        print(f"   - {col[0]}")
    
    return [col[0] for col in columns]

if __name__ == "__main__":
    # Ajouter les colonnes
    add_all_missing_columns()
    
    # Vérifier le résultat
    verify_columns()