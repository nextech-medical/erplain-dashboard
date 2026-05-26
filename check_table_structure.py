# check_table_structure.py
import psycopg2
import pandas as pd
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def check_structure():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    # Lister les colonnes de la table invoices
    query = """
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'invoices'
        ORDER BY ordinal_position
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print("\n📋 Structure actuelle de la table 'invoices':")
    print("="*50)
    for _, row in df.iterrows():
        print(f"   - {row['column_name']}: {row['data_type']}")
    
    return df

if __name__ == "__main__":
    check_structure()