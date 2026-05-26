# check_tracking.py
import psycopg2
import pandas as pd
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME,
    user=DB_USER, password=DB_PASSWORD
)

df = pd.read_sql_query("""
    SELECT order_number, tracking_number, shipping_date 
    FROM delivery_notes 
    WHERE tracking_number IS NOT NULL AND tracking_number NOT LIKE '2026-%'
    LIMIT 30
""", conn)

print(df.to_string(index=False))
conn.close()