import sys
sys.argv = ["streamlit", "run", __file__, "--server.port=8080", "--server.address=0.0.0.0"]

import streamlit as st
import psycopg2

st.title("🔍 Diagnostic base de données")

try:
    conn = psycopg2.connect(
        host='postgresql-20fb082e-o33c4d6e5.database.cloud.ovh.net',
        port='20184',
        database='defaultdb',
        user='avnadmin',
        password='RwoL3kUjOpi0Y1x9V4JN',
        sslmode='require'
    )
    st.success("✅ Connexion réussie !")
    
    cursor = conn.cursor()
    
    # Lister toutes les tables
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    tables = cursor.fetchall()
    
    st.subheader("📋 Tables disponibles dans la base :")
    if tables:
        for table in tables:
            st.write(f"- `{table[0]}`")
    else:
        st.warning("Aucune table trouvée dans la base !")
    
    # Vérifier la présence des tables nécessaires
    required_tables = ['invoices', 'invoice_lines', 'products']
    st.subheader("🔎 Vérification des tables nécessaires :")
    for req in required_tables:
        cursor.execute(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{req}')")
        exists = cursor.fetchone()[0]
        if exists:
            st.success(f"✅ {req} existe")
        else:
            st.error(f"❌ {req} n'existe pas")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    st.error(f"❌ Erreur: {e}")
