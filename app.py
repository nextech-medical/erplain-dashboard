import sys
sys.argv = ["streamlit", "run", __file__, "--server.port=8080", "--server.address=0.0.0.0"]

import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="Nextech Medical", page_icon="📊", layout="wide")

# ========== FRAIS GLS ==========
GLS_PRIX_MOYEN_PAR_COLIS = 8.28
GLS_TARIF_PETIT_COLIS = 4.50
GLS_TARIF_GRAND_COLIS = 12.00
GLS_FRAIS_FIXE = 0.50

def calculer_frais_gls_approximatifs(quantite_totale, ca_facture):
    nb_colis_estime = max(1, round(quantite_totale / 10))
    if ca_facture < 50:
        frais_base = GLS_TARIF_PETIT_COLIS
        nb_colis_estime = 1
    elif ca_facture < 200:
        frais_base = GLS_PRIX_MOYEN_PAR_COLIS
    else:
        frais_base = GLS_PRIX_MOYEN_PAR_COLIS
    frais_ht = (nb_colis_estime * frais_base) + GLS_FRAIS_FIXE
    plafond = ca_facture * 0.12
    frais_ht = min(frais_ht, plafond)
    return round(frais_ht, 2)

# ========== CHARGEMENT DES DONNÉES ==========
@st.cache_data(ttl=300)
def load_data():
    """Charge les données depuis PostgreSQL"""
    
    try:
        conn = psycopg2.connect(
            host='postgresql-20fb082e-o33c4d6e5.database.cloud.ovh.net',
            port='20184',
            database='defaultdb',
            user='avnadmin',
            password='RwoL3kUjOpi0Y1x9V4JN',
            sslmode='require'
        )
    except Exception as e:
        st.error(f"❌ Erreur de connexion: {e}")
        return pd.DataFrame()
    
    # Requête adaptée à VOS tables (created au lieu de invoice_created)
    query = """
    SELECT 
        i.id,
        i.label as invoice_number,
        i.created as date,
        i.total,
        i.customer_name,
        'Non spécifié' as fournisseur,
        'Direct' as gestionnaire,
        il.product_sku,
        il.quantity,
        il.total as line_total,
        0 as purchase_price,
        0 as weight_kg,
        0 as customs_rate
    FROM invoices i
    LEFT JOIN invoice_lines il ON i.id = il.invoice_id
    WHERE i.created IS NOT NULL
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        return df
    
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['total'] = pd.to_numeric(df['total'], errors='coerce').fillna(0)
    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
    df['line_total'] = pd.to_numeric(df['line_total'], errors='coerce').fillna(0)
    df['purchase_price'] = pd.to_numeric(df['purchase_price'], errors='coerce').fillna(0)
    
    return df

# ========== CHARGEMENT ==========
st.title("📊 Nextech Medical Dashboard")

with st.spinner("Chargement des données..."):
    df = load_data()

if df.empty:
    st.error("❌ Aucune donnée trouvée dans la base")
    st.stop()

st.success(f"✅ {len(df)} lignes chargées")

# ========== SIDEBAR ==========
st.sidebar.title("🔍 Filtres")

st.sidebar.markdown("### 📅 Période")
date_min = df['date'].min().date()
date_max = df['date'].max().date()
start_date, end_date = st.sidebar.date_input("Date de facture", (date_min, date_max))

# ========== APPLICATION FILTRES ==========
df_filtre = df[(df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date)]

if df_filtre.empty:
    st.warning("⚠️ Aucune donnée avec les filtres sélectionnés")
    st.stop()

# ========== CALCULS ==========
# Calcul du COGS et frais GLS
cogs_ratio_default = 0.5

produits_avec_prix = df_filtre[df_filtre['purchase_price'] > 0]
produits_sans_prix = df_filtre[df_filtre['purchase_price'] == 0]

if not produits_avec_prix.empty:
    produits_avec_prix['cogs_ligne'] = produits_avec_prix['quantity'] * produits_avec_prix['purchase_price']
else:
    produits_avec_prix['cogs_ligne'] = 0

if not produits_sans_prix.empty:
    produits_sans_prix['cogs_ligne'] = produits_sans_prix['line_total'] * cogs_ratio_default

df_filtre = pd.concat([produits_avec_prix, produits_sans_prix], ignore_index=True)

# Calcul frais GLS
ca_par_facture = df_filtre.groupby('id')['line_total'].sum().reset_index()
ca_par_facture.columns = ['id', 'ca_facture']
quantite_par_facture = df_filtre.groupby('id')['quantity'].sum().reset_index()
quantite_par_facture.columns = ['id', 'quantite_totale']
df_filtre = df_filtre.merge(ca_par_facture, on='id', how='left')
df_filtre = df_filtre.merge(quantite_par_facture, on='id', how='left')
df_filtre['frais_gls_ligne'] = df_filtre.apply(
    lambda row: calculer_frais_gls_approximatifs(row['quantite_totale'], row['ca_facture']) * (row['line_total'] / row['ca_facture'] if row['ca_facture'] > 0 else 0),
    axis=1
)

df_filtre['marge_ligne'] = df_filtre['line_total'] - df_filtre['cogs_ligne'] - df_filtre['frais_gls_ligne']

# ========== AGRÉGATION PAR FACTURE ==========
invoices_unique = df_filtre.groupby('id').agg({
    'invoice_number': 'first',
    'date': 'first',
    'customer_name': 'first',
    'gestionnaire': 'first',
    'fournisseur': 'first',
    'line_total': 'sum',
    'cogs_ligne': 'sum',
    'marge_ligne': 'sum',
    'quantity': 'sum'
}).reset_index()

invoices_unique = invoices_unique.rename(columns={
    'line_total': 'ca_produits',
    'cogs_ligne': 'cogs_total',
    'marge_ligne': 'marge_nette',
    'quantity': 'total_quantite'
})
invoices_unique['taux_marge'] = (invoices_unique['marge_nette'] / invoices_unique['ca_produits'] * 100).round(2).fillna(0)

# ========== KPIS ==========
total_ca = invoices_unique['ca_produits'].sum()
nb_factures = len(invoices_unique)
nb_clients = invoices_unique['customer_name'].nunique()
nb_produits_total = invoices_unique['total_quantite'].sum()
total_cogs = invoices_unique['cogs_total'].sum()
total_marge = invoices_unique['marge_nette'].sum()
taux_marge_moyen = (total_marge / total_ca * 100) if total_ca > 0 else 0

# ========== AFFICHAGE ==========
st.subheader("📊 Indicateurs clés")

col1, col2, col3, col4 = st.columns(4)
col1.metric("💰 CA total", f"{total_ca:,.2f} €")
col2.metric("📄 Nombre factures", f"{nb_factures:,}")
col3.metric("👥 Clients distincts", f"{nb_clients:,}")
col4.metric("📦 Produits vendus", f"{nb_produits_total:,.0f}")

st.markdown("---")

col5, col6, col7 = st.columns(3)
col5.metric("📦 COGS total", f"{total_cogs:,.2f} €")
col6.metric("💰 Marge nette", f"{total_marge:,.2f} €")
col7.metric("📈 Taux marge moyen", f"{taux_marge_moyen:.1f}%")

# ========== TOP PRODUITS ==========
st.subheader("🏆 Top produits")

produits_kpis = df_filtre.groupby('product_sku').agg({
    'line_total': 'sum',
    'quantity': 'sum'
}).reset_index()
produits_kpis = produits_kpis[produits_kpis['product_sku'].astype(str).str.strip() != '']
produits_kpis = produits_kpis.sort_values('line_total', ascending=False).head(10)

if not produits_kpis.empty:
    fig = px.bar(produits_kpis, x='line_total', y='product_sku', orientation='h', 
                 title="Top 10 produits par CA", labels={'line_total': 'CA (€)', 'product_sku': 'SKU'})
    st.plotly_chart(fig, use_container_width=True)

# ========== CA PAR JOUR ==========
st.subheader("📈 Évolution du CA")

ca_jour = invoices_unique.groupby('date')['ca_produits'].sum().reset_index()
if not ca_jour.empty:
    fig_ca = px.line(ca_jour, x='date', y='ca_produits', title="CA par jour", markers=True)
    st.plotly_chart(fig_ca, use_container_width=True)

# ========== FOOTER ==========
st.markdown("---")
st.caption(f"📊 Dernière mise à jour: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
