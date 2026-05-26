# add_external_reference_column.py
import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def add_external_reference_column():
    """Ajoute la colonne reference_externe à la table invoices."""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Ajouter la colonne si elle n'existe pas
    cursor.execute("""
        ALTER TABLE invoices 
        ADD COLUMN IF NOT EXISTS reference_externe TEXT
    """)
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print("✅ Colonne 'reference_externe' ajoutée à la table invoices")

if __name__ == "__main__":
    add_external_reference_column()