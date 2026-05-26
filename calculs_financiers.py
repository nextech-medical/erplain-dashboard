# app.py
import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
from datetime import datetime
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

st.set_page_config(page_title="Nextech Medical", page_icon="📊", layout="wide")

@st.cache_data(ttl=300)
def load_data():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        options="-c client_encoding=UTF8"
    )
    query = """
    SELECT 
        i.id,
        i.label as invoice_number,
        i.invoice_created as date,
        i.total,
        i.customer_name,
        il.quantity
    FROM invoices i
    LEFT JOIN invoice_lines il ON i.id = il.invoice_id
    WHERE i.invoice_created IS NOT NULL
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['total'] = pd.to_numeric(df['total'], errors='coerce').fillna(0)
    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
    return df

# Chargement
with st.spinner("Chargement..."):
    df = load_data()

if df.empty:
    st.error("Aucune donnée")
    st.stop()

# Filtres
st.sidebar.title("Filtres")
date_min = df['date'].min().date()
date_max = df['date'].max().date()
start_date, end_date = st.sidebar.date_input("Période", (date_min, date_max))

# Filtrage
df_filtre = df[(df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date)]

if df_filtre.empty:
    st.warning("Aucune donnée")
    st.stop()

# Paramètres transport
tarif = st.sidebar.number_input("Tarif transport (€)", 0.0, 10.0, 0.50, 0.1)
fixe = st.sidebar.number_input("Fixe transport (€)", 0.0, 10.0, 2.00, 0.5)

# ========== CALCUL SIMPLE ==========
# Création directe de la colonne
df_filtre['frais_transport'] = (df_filtre['quantity'] * tarif) + fixe

# Agrégation par facture
transport_agg = df_filtre.groupby('id')['frais_transport'].first().reset_index()
transport_agg.columns = ['id', 'frais_transport']

# Factures uniques
invoices = df_filtre.drop_duplicates(subset=['id']).copy()

# Fusion
invoices = invoices.merge(transport_agg, on='id', how='left')

# Fillna (maintenant la colonne existe)
invoices['frais_transport'] = invoices['frais_transport'].fillna(0)

# KPIS
total_ca = invoices['total'].sum()
total_transport = invoices['frais_transport'].sum()

# Affichage
st.title("Nextech Medical")

c1, c2, c3 = st.columns(3)
c1.metric("💰 CA total", f"{total_ca:,.2f} €")
c2.metric("🚚 Frais transport", f"{total_transport:,.2f} €")
c3.metric("📄 Factures", f"{len(invoices):,}")

st.markdown("---")

# Graphique
ca_jour = invoices.groupby('date')['total'].sum().reset_index()
fig = px.line(ca_jour, x='date', y='total', title="CA par jour", markers=True)
st.plotly_chart(fig, use_container_width=True)

# Tableau
st.subheader("Détail des factures")
st.dataframe(invoices[['invoice_number', 'customer_name', 'total', 'frais_transport']].head(50), use_container_width=True)