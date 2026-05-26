import psycopg2
import pandas as pd
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def check_bl_data():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

    # --- DELIVERY NOTES ---
    print("\n📋 Bons de livraison:")

    df_bl = pd.read_sql_query("""
        SELECT *
        FROM delivery_notes
        LIMIT 50
    """, conn)

    print(df_bl.to_string(index=False))

    # --- INVOICES ---
    print("\n📋 Factures avec BL:")

    df_invoices = pd.read_sql_query("""
        SELECT *
        FROM invoices
        WHERE bl_number IS NOT NULL
        LIMIT 10
    """, conn)

    print(df_invoices.to_string(index=False))

    conn.close()

if __name__ == "__main__":
    check_bl_data()