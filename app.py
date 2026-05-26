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
        il.product_sku,
        il.quantity,
        il.line_total
    FROM invoices i
    LEFT JOIN invoice_lines il ON i.id = il.invoice_id
    WHERE i.invoice_created IS NOT NULL
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['total'] = pd.to_numeric(df['total'], errors='coerce').fillna(0)
    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
    df['line_total'] = pd.to_numeric(df['line_total'], errors='coerce').fillna(0)
    return df

def load_parametres():
    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cursor = conn.cursor()
        cursor.execute("SELECT type_transport, tarif_unitaire, cout_fixe FROM parametres ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        conn.close()
        if result:
            return {"type": result[0], "tarif": float(result[1]), "cout_fixe": float(result[2])}
    except:
        pass
    return {"type": "quantite", "tarif": 0.15, "cout_fixe": 0.50}

def save_parametres(type_transport, tarif, cout_fixe):
    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO parametres (type_transport, tarif_unitaire, cout_fixe, date_maj)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
        """, (type_transport, tarif, cout_fixe))
        conn.commit()
        conn.close()
    except:
        pass

# Chargement
with st.spinner("Chargement..."):
    df = load_data()

if df.empty:
    st.error("Aucune donnée")
    st.stop()

# Filtres
st.sidebar.title("🔍 Filtres")
date_min = df['date'].min().date()
date_max = df['date'].max().date()
start_date, end_date = st.sidebar.date_input("Période", (date_min, date_max))

st.sidebar.markdown("---")

# Paramètres
params = load_parametres()

tarif = st.sidebar.number_input("Tarif transport (€/unité)", 0.0, 5.0, params['tarif'], 0.05)
fixe = st.sidebar.number_input("Frais fixe transport (€/commande)", 0.0, 10.0, params['cout_fixe'], 0.25)
cogs_ratio = st.sidebar.slider("COGS (% du prix de vente)", 0, 100, 50, 5) / 100

if st.sidebar.button("💾 Sauvegarder mes paramètres"):
    save_parametres("quantite", tarif, fixe)
    st.sidebar.success("✅ Paramètres sauvegardés")

st.sidebar.markdown("---")
st.sidebar.caption(f"💡 **Aperçu transport**\n10 produits = {(10 * tarif) + fixe:.2f}€")

# Filtrage
df_filtre = df[(df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date)]

if df_filtre.empty:
    st.warning("Aucune donnée")
    st.stop()

# ========== ÉTAPE 1 : CALCULER LES FRAIS DE TRANSPORT PAR FACTURE ==========
# Calculer le total des quantités par facture
quantite_par_facture = df_filtre.groupby('id')['quantity'].sum().reset_index()
quantite_par_facture.columns = ['id', 'total_quantite_facture']

# Joindre au dataframe principal
df_filtre = df_filtre.merge(quantite_par_facture, on='id', how='left')

# Calculer les frais de transport PAR FACTURE
df_filtre['frais_transport_facture_total'] = (df_filtre['total_quantite_facture'] * tarif) + fixe

# Limiter à 30% du CA de la facture (plafond)
# D'abord, récupérer le CA par facture
ca_par_facture = df_filtre.groupby('id')['line_total'].sum().reset_index()
ca_par_facture.columns = ['id', 'ca_facture']
df_filtre = df_filtre.merge(ca_par_facture, on='id', how='left')

# Appliquer le plafond de 30% du CA
df_filtre['transport_max_facture'] = df_filtre['ca_facture'] * 0.3
df_filtre['frais_transport_facture_total'] = df_filtre[['frais_transport_facture_total', 'transport_max_facture']].min(axis=1)

# ========== ÉTAPE 2 : RÉPARTIR PROPORTIONNELLEMENT PAR PRODUIT ==========
# Calculer le ratio de chaque produit dans la facture
df_filtre['ratio_produit'] = df_filtre['line_total'] / df_filtre.groupby('id')['line_total'].transform('sum')
df_filtre['ratio_produit'] = df_filtre['ratio_produit'].fillna(0)

# Répartir les frais de transport proportionnellement au CA de chaque produit
df_filtre['frais_transport_ligne'] = df_filtre['frais_transport_facture_total'] * df_filtre['ratio_produit']

# COGS par ligne
df_filtre['cogs_ligne'] = df_filtre['line_total'] * cogs_ratio

# Marge par ligne
df_filtre['marge_ligne'] = df_filtre['line_total'] - df_filtre['cogs_ligne'] - df_filtre['frais_transport_ligne']
df_filtre['taux_marge_ligne'] = (df_filtre['marge_ligne'] / df_filtre['line_total'] * 100).round(2).fillna(0)

# ========== ÉTAPE 3 : AGRÉGATION PAR FACTURE ==========
invoices = df_filtre.groupby('id').agg({
    'invoice_number': 'first',
    'date': 'first',
    'customer_name': 'first',
    'total': 'first',
    'ca_facture': 'first',
    'quantity': 'sum',
    'line_total': 'sum',
    'cogs_ligne': 'sum',
    'frais_transport_facture_total': 'first',
    'marge_ligne': 'sum'
}).reset_index()

invoices = invoices.rename(columns={
    'total': 'ca_reel_facture',
    'line_total': 'ca_produits',
    'cogs_ligne': 'cogs_total',
    'frais_transport_facture_total': 'frais_transport',
    'marge_ligne': 'marge_nette'
})

invoices['taux_marge'] = (invoices['marge_nette'] / invoices['ca_reel_facture'] * 100).round(2).fillna(0)

# ========== KPIS GLOBAUX ==========
total_ca = invoices['ca_reel_facture'].sum()
total_cogs = invoices['cogs_total'].sum()
total_transport = invoices['frais_transport'].sum()
total_marge = invoices['marge_nette'].sum()
taux_marge_moyen = (total_marge / total_ca * 100) if total_ca > 0 else 0
part_transport = (total_transport / total_ca * 100) if total_ca > 0 else 0
part_cogs = (total_cogs / total_ca * 100) if total_ca > 0 else 0

# ========== HEADER ==========
st.title("📊 Nextech Medical")

# Alertes
if part_transport > 30:
    st.warning(f"⚠️ **Attention** : Les frais de transport représentent {part_transport:.0f}% du CA !")
    st.info(f"💡 **Solution** : Réduisez le tarif transport (actuel: {tarif:.2f}€) ou le fixe (actuel: {fixe:.2f}€)")

if taux_marge_moyen < 0:
    st.error(f"⚠️ **Marge négative** : {taux_marge_moyen:.1f}% - Ajustez vos paramètres")

# ========== KPIS ==========
st.subheader("📊 Indicateurs clés")

col1, col2, col3, col4 = st.columns(4)
col1.metric("💰 CA total", f"{total_ca:,.2f} €")
col2.metric("📦 COGS total", f"{total_cogs:,.2f} €")
col3.metric("🚚 Frais transport", f"{total_transport:,.2f} €")
col4.metric("💰 Marge nette", f"{total_marge:,.2f} €")

st.markdown("---")

col5, col6, col7 = st.columns(3)
col5.metric("📈 Taux marge moyen", f"{taux_marge_moyen:.1f} %")
col6.metric("📄 Nombre factures", f"{len(invoices):,}")
col7.metric("📦 Produits vendus", f"{invoices['quantity'].sum():,.0f}")

st.markdown("---")

# ========== GRAPHIQUES ==========
st.subheader("📈 Évolution quotidienne")

daily = invoices.groupby('date').agg({
    'ca_reel_facture': 'sum',
    'cogs_total': 'sum',
    'frais_transport': 'sum',
    'marge_nette': 'sum'
}).reset_index()
daily.columns = ['date', 'CA', 'COGS', 'Transport', 'Marge']

fig1 = px.line(daily, x='date', y=['CA', 'Transport'], title="CA vs Frais transport", markers=True)
st.plotly_chart(fig1, use_container_width=True)

fig2 = px.line(daily, x='date', y='Marge', title="Marge nette par jour", markers=True, color_discrete_sequence=['green'])
fig2.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Seuil rentabilité")
st.plotly_chart(fig2, use_container_width=True)

# Distribution des frais transport
st.subheader("📊 Distribution des frais de transport")
fig3 = px.histogram(invoices, x='frais_transport', nbins=30, title="Frais transport par commande",
                    labels={'frais_transport': 'Frais transport (€)', 'count': 'Nombre commandes'})
st.plotly_chart(fig3, use_container_width=True)

# ========== ANALYSE PAR PRODUIT ==========
st.subheader("🏆 Top produits par CA")

top_produits = df_filtre.groupby('product_sku').agg({
    'line_total': 'sum',
    'quantity': 'sum',
    'cogs_ligne': 'sum',
    'frais_transport_ligne': 'sum',
    'marge_ligne': 'sum'
}).reset_index()
top_produits = top_produits[top_produits['product_sku'].astype(str).str.strip() != '']
top_produits = top_produits.sort_values('line_total', ascending=False)
top_produits['taux_marge'] = (top_produits['marge_ligne'] / top_produits['line_total'] * 100).round(2).fillna(0)

if not top_produits.empty:
    col_prod1, col_prod2 = st.columns([2, 1])
    with col_prod1:
        st.dataframe(top_produits.head(15).rename(columns={
            'product_sku': 'SKU',
            'line_total': 'CA (€)',
            'quantity': 'Qté',
            'cogs_ligne': 'COGS (€)',
            'frais_transport_ligne': 'Transport (€)',
            'marge_ligne': 'Marge (€)',
            'taux_marge': 'Taux (%)'
        }), use_container_width=True)
    
    with col_prod2:
        top_n = top_produits.head(10).iloc[::-1]
        fig_prod = px.bar(top_n, x='line_total', y='product_sku', orientation='h', 
                          title="Top 10 produits", text='line_total')
        fig_prod.update_traces(texttemplate='%{text:,.0f} €', textposition='outside')
        st.plotly_chart(fig_prod, use_container_width=True)

# ========== COMMANDES À RISQUE ==========
st.subheader("⚠️ Commandes avec marge négative")

commandes_negatives = invoices[invoices['marge_nette'] < 0].copy()
if not commandes_negatives.empty:
    st.warning(f"🔴 {len(commandes_negatives)} commandes ont une marge négative")
    st.dataframe(commandes_negatives[['invoice_number', 'customer_name', 'ca_reel_facture', 'frais_transport', 'marge_nette', 'taux_marge']]
                 .head(20).rename(columns={
                     'invoice_number': 'Facture',
                     'customer_name': 'Client',
                     'ca_reel_facture': 'CA (€)',
                     'frais_transport': 'Transport (€)',
                     'marge_nette': 'Marge (€)',
                     'taux_marge': 'Taux (%)'
                 }), use_container_width=True)
else:
    st.success("✅ Toutes les commandes ont une marge positive")

# ========== DÉTAIL FACTURES ==========
with st.expander("📋 Détail complet des factures"):
    st.dataframe(invoices[['invoice_number', 'customer_name', 'date', 'ca_reel_facture', 'cogs_total', 'frais_transport', 'marge_nette', 'taux_marge']]
                 .head(100).rename(columns={
                     'invoice_number': 'Facture',
                     'customer_name': 'Client',
                     'date': 'Date',
                     'ca_reel_facture': 'CA (€)',
                     'cogs_total': 'COGS (€)',
                     'frais_transport': 'Transport (€)',
                     'marge_nette': 'Marge (€)',
                     'taux_marge': 'Taux (%)'
                 }), use_container_width=True)

# ========== EXPORT ==========
st.markdown("---")
csv = invoices.to_csv(index=False).encode('utf-8-sig')
st.download_button("📥 Télécharger toutes les données (CSV)", csv, f"nextech_export_{datetime.now().strftime('%Y%m%d')}.csv")

# ========== FOOTER ==========
st.caption(f"📅 Période : {start_date} - {end_date}")
st.caption(f"⚙️ Paramètres actifs : COGS = {cogs_ratio*100:.0f}% | Transport = {tarif:.2f}€/unité + {fixe:.2f}€ fixe")
st.caption(f"📊 Ratio transport/CA : {part_transport:.1f}% | Ratio COGS/CA : {part_cogs:.1f}%")