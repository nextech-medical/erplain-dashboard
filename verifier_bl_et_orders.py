# verifier_bl_et_orders.py
import psycopg2
import pandas as pd
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

print("=" * 60)
print("🔍 VÉRIFICATION DES SOURCES DE DONNÉES")
print("=" * 60)

# Vérifier la table delivery_notes
try:
    cursor = conn.cursor()
    cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'delivery_notes')")
    has_delivery = cursor.fetchone()[0]
    
    if has_delivery:
        cursor.execute("SELECT COUNT(*) FROM delivery_notes")
        nb_bl = cursor.fetchone()[0]
        print(f"\n📦 Table delivery_notes: {nb_bl} BL")
        
        if nb_bl > 0:
            cursor.execute("""
                SELECT order_number, external_reference, tracking_number 
                FROM delivery_notes 
                LIMIT 5
            """)
            print("\n   Exemples de BL:")
            for row in cursor.fetchall():
                print(f"      - {row[0]}: ref='{row[1]}' tracking='{row[2]}'")
    else:
        print("\n❌ Table delivery_notes n'existe pas")
        
except Exception as e:
    print(f"Erreur delivery_notes: {e}")

# Vérifier la table orders
try:
    cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'orders')")
    has_orders = cursor.fetchone()[0]
    
    if has_orders:
        cursor.execute("SELECT COUNT(*) FROM orders")
        nb_orders = cursor.fetchone()[0]
        print(f"\n📋 Table orders: {nb_orders} commandes")
        
        if nb_orders > 0:
            cursor.execute("""
                SELECT order_id, external_reference, account_manager_name 
                FROM orders 
                LIMIT 5
            """)
            print("\n   Exemples de commandes:")
            for row in cursor.fetchall():
                print(f"      - {row[0]}: ref='{row[1]}' manager='{row[2]}'")
    else:
        print("\n❌ Table orders n'existe pas")
        
except Exception as e:
    print(f"Erreur orders: {e}")

conn.close()