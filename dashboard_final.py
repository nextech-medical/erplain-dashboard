# dashboard_final.py
"""
Dashboard commercial Nextech Medical - Version stable
"""

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
        i.order_number,
        i.invoice_created as date,
        i.due_date,
        i.subtotal,
        i.total,
        i.customer_name,
        i.customer_email,
        COALESCE(dn.external_reference, '') as reference_externe,
        dn.order_number as bl_number,
        dn.shipping_date,
        dn.status as bl_status,
        dn.tracking_number,
        COALESCE(i.fournisseur, 'Non spécifié') as fournisseur,
        CASE 
            WHEN i.gestionnaire IS NOT NULL AND i.gestionnaire != 'Non spécifié' THEN i.gestionnaire
            ELSE 'Direct'
        END as gestionnaire,
        il.product_label,
        il.product_sku,
        il.quantity,
        il.unit_price,
        il.line_total
    FROM invoices i
    LEFT JOIN invoice_lines il ON i.id = il.invoice_id
    LEFT JOIN delivery_notes dn ON dn.order_number = i.order_number
    WHERE i.invoice_created IS NOT NULL
    ORDER BY i.invoice_created DESC
    """

    df = pd.read_sql_query(query, conn)
    conn.close()

    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['shipping_date'] = pd.to_datetime(df['shipping_date'], errors='coerce')
    df['due_date'] = pd.to_datetime(df['due_date'], errors='coerce')
    
    numeric_cols = ['total', 'quantity', 'subtotal', 'unit_price', 'line_total']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    string_cols = ['product_sku', 'product_label', 'customer_name', 'reference_externe', 
                   'bl_number', 'invoice_number', 'tracking_number', 'customer_email',
                   'fournisseur', 'gestionnaire']
    for col in string_cols:
        if col in df.columns:
            df[col] = df[col].fillna('').astype(str)
            df[col] = df[col].str.strip()
    
    df['fournisseur'] = df['fournisseur'].apply(lambda x: 'Non spécifié' if x == '' or x == 'None' else x)
    df['gestionnaire'] = df['gestionnaire'].apply(lambda x: 'Direct' if x == '' or x == 'None' else x)
    df['product_sku'] = df['product_sku'].apply(lambda x: 'SANS_SKU' if x == '' or x == 'None' else x)
    
    return df


@st.cache_data(ttl=300)
def get_gestionnaires_list(df):
    if df is not None and not df.empty and 'gestionnaire' in df.columns:
        gestionnaires = df['gestionnaire'].unique().tolist()
        gestionnaires = [g for g in gestionnaires if g not in ['Direct', 'Non spécifié', '', 'None']]
        return sorted(gestionnaires)
    return []


@st.cache_data(ttl=300)
def get_fournisseurs_list(df):
    if df is not None and not df.empty and 'fournisseur' in df.columns:
        fournisseurs = df['fournisseur'].unique().tolist()
        fournisseurs = [f for f in fournisseurs if f not in ['Non spécifié', '', 'None']]
        return sorted(fournisseurs)
    return []


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
    return {"type": "quantite", "tarif": 0.50, "cout_fixe": 2.00}


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


# ========== CHARGEMENT ==========
with st.spinner("Chargement des données..."):
    df = load_data()

if df.empty:
    st.error("❌ Aucune donnée")
    st.stop()


# ========== FILTRES ==========
st.sidebar.title("🔍 Filtres")

st.sidebar.markdown("### 📅 Période")
if 'date' in df.columns and not df['date'].isna().all():
    date_min = df['date'].min().date()
    date_max = df['date'].max().date()
else:
    date_min = datetime.now().date()
    date_max = datetime.now().date()

start_date, end_date = st.sidebar.date_input("Date de facture", (date_min, date_max))

st.sidebar.markdown("---")

st.sidebar.markdown("### 👤 Gestionnaire")
gestionnaires_list = get_gestionnaires_list(df)

if gestionnaires_list:
    gestionnaires_options = ["Tous"] + gestionnaires_list
    selected_gestionnaire = st.sidebar.selectbox("Sélectionner", options=gestionnaires_options, index=0)
else:
    selected_gestionnaire = "Tous"

st.sidebar.markdown("---")

st.sidebar.markdown("### 🏭 Fournisseur")
fournisseurs_list = get_fournisseurs_list(df)

if fournisseurs_list:
    fournisseurs_sel = st.sidebar.multiselect("Sélectionner", fournisseurs_list, default=[])
else:
    fournisseurs_sel = []

st.sidebar.markdown("---")

st.sidebar.markdown("### ⚙️ Paramètres")
cogs_ratio = st.sidebar.slider("COGS (% du CA)", 0, 100, 70, 5) / 100

params_transport = load_parametres()
st.sidebar.markdown("### 🚚 Transport")
st.sidebar.info(f"{params_transport['type']} | Tarif: {params_transport['tarif']}€ | Fixe: {params_transport['cout_fixe']}€")


# ========== APPLICATION DES FILTRES ==========
if 'date' in df.columns:
    df_filtre = df[(df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date)]
else:
    df_filtre = df.copy()

if selected_gestionnaire != "Tous" and 'gestionnaire' in df_filtre.columns:
    df_filtre = df_filtre[df_filtre['gestionnaire'] == selected_gestionnaire]

if fournisseurs_sel and 'fournisseur' in df_filtre.columns:
    df_filtre = df_filtre[df_filtre['fournisseur'].isin(fournisseurs_sel)]

if df_filtre.empty:
    st.warning("⚠️ Aucune donnée")
    st.stop()


# ========== CALCULS ==========
# Frais de transport
df_filtre['frais_transport'] = (df_filtre['quantity'] * params_transport['tarif']) + params_transport['cout_fixe']

# COGS
df_filtre['cogs'] = df_filtre['line_total'] * cogs_ratio

# Agrégation par facture
cogs_by_invoice = df_filtre.groupby('id')['cogs'].sum().reset_index()
cogs_by_invoice.columns = ['id', 'cogs_total']

transport_by_invoice = df_filtre.groupby('id')['frais_transport'].first().reset_index()
transport_by_invoice.columns = ['id', 'frais_transport']

# Factures uniques
invoices_unique = df_filtre.drop_duplicates(subset=['id']).copy()

# Fusion (ATTENTION: on ne fait PAS fillna avant la fusion)
invoices_unique = invoices_unique.merge(cogs_by_invoice, on='id', how='left')
invoices_unique = invoices_unique.merge(transport_by_invoice, on='id', how='left')

# Remplacer les NaN APRES la fusion
invoices_unique['cogs_total'] = invoices_unique['cogs_total'].fillna(0)
invoices_unique['frais_transport'] = invoices_unique['frais_transport'].fillna(0)

# Marge
invoices_unique['marge_nette'] = invoices_unique['total'] - invoices_unique['cogs_total'] - invoices_unique['frais_transport']
invoices_unique['taux_marge'] = (invoices_unique['marge_nette'] / invoices_unique['total'] * 100).round(2).fillna(0)


# ========== KPIS ==========
total_ca = invoices_unique['total'].sum()
nb_factures = len(invoices_unique)
nb_clients = invoices_unique['customer_name'].nunique()
nb_produits = df_filtre['quantity'].sum()
total_cogs = invoices_unique['cogs_total'].sum()
total_transport = invoices_unique['frais_transport'].sum()
total_marge = invoices_unique['marge_nette'].sum()
taux_marge_moyen = (total_marge / total_ca * 100) if total_ca > 0 else 0


# ========== HEADER ==========
col_h1, col_h2, col_h3 = st.columns([2, 4, 1])
with col_h1:
    st.title("📊 Nextech Medical")
with col_h3:
    if st.button("⚙️"):
        st.session_state.show_settings = True

if st.session_state.get('show_settings', False):
    with st.expander("Paramètres transport", expanded=True):
        p = load_parametres()
        new_type = st.radio("Mode", ["quantite", "poids"], index=0 if p['type'] == 'quantite' else 1)
        new_tarif = st.number_input("Tarif (€)", 0.0, 10.0, p['tarif'], 0.1)
        new_fixe = st.number_input("Fixe (€)", 0.0, 10.0, p['cout_fixe'], 0.5)
        if st.button("Sauvegarder"):
            save_parametres(new_type, new_tarif, new_fixe)
            st.success("✅ Sauvegardé")
            st.session_state.show_settings = False
            st.rerun()
        if st.button("Fermer"):
            st.session_state.show_settings = False
            st.rerun()


# ========== AFFICHAGE KPIS ==========
c1, c2, c3, c4 = st.columns(4)
c1.metric("💰 CA", f"{total_ca:,.2f} €")
c2.metric("📄 Factures", f"{nb_factures:,}")
c3.metric("👥 Clients", f"{nb_clients:,}")
c4.metric("📦 Produits", f"{nb_produits:,.0f}")

st.markdown("---")

c5, c6, c7, c8, c9 = st.columns(5)
c5.metric("📦 COGS", f"{total_cogs:,.2f} €")
c6.metric("🚚 Transport", f"{total_transport:,.2f} €")
c7.metric("💰 Marge nette", f"{total_marge:,.2f} €")
c8.metric("📈 Taux marge", f"{taux_marge_moyen:.1f}%")
c9.metric("💶 Part transport", f"{(total_transport/total_ca*100):.1f}%" if total_ca > 0 else "0%")

st.markdown("---")

with_ref = invoices_unique[invoices_unique['reference_externe'] != ''].shape[0]
with_bl = invoices_unique[invoices_unique['bl_number'] != ''].shape[0]
with_fourn = invoices_unique[invoices_unique['fournisseur'] != 'Non spécifié'].shape[0]
with_gest = invoices_unique[invoices_unique['gestionnaire'] != 'Direct'].shape[0]

k1, k2, k3, k4 = st.columns(4)
k1.metric("🏷️ Réf externe", f"{with_ref}/{nb_factures}")
k2.metric("🚚 BL", f"{with_bl}/{nb_factures}")
k3.metric("🏭 Fournisseur", f"{with_fourn}/{nb_factures}")
k4.metric("📱 Plateforme", f"{with_gest}/{nb_factures}")

if selected_gestionnaire != "Tous":
    st.info(f"📌 Gestionnaire: {selected_gestionnaire}")


# ========== ONGLETS ==========
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 Vue d'ensemble",
    "🏆 Top produits",
    "👥 Top clients",
    "🏭 Fournisseurs",
    "📋 Détail factures"
])


# TAB 1
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        if not invoices_unique.empty:
            ca_jour = invoices_unique.groupby('date')['total'].sum().reset_index()
            fig = px.line(ca_jour, x='date', y='total', title="CA par jour", markers=True)
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        if not invoices_unique.empty:
            trans_jour = invoices_unique.groupby('date')['frais_transport'].sum().reset_index()
            fig = px.line(trans_jour, x='date', y='frais_transport', title="Transport par jour", markers=True)
            st.plotly_chart(fig, use_container_width=True)


# TAB 2
with tab2:
    st.subheader("🏆 Top produits")
    df_top = df.copy()
    df_top = df_top[(df_top['date'].dt.date >= start_date) & (df_top['date'].dt.date <= end_date)]
    if selected_gestionnaire != "Tous":
        df_top = df_top[df_top['gestionnaire'] == selected_gestionnaire]
    if fournisseurs_sel:
        df_top = df_top[df_top['fournisseur'].isin(fournisseurs_sel)]
    
    top = df_top.groupby('product_sku')['line_total'].sum().reset_index()
    top = top[top['product_sku'].astype(str).str.strip() != '']
    top = top.sort_values('line_total', ascending=False)
    
    if not top.empty:
        nb = st.slider("Nombre", 5, min(50, len(top)), 10)
        top_n = top.head(nb).iloc[::-1]
        fig = px.bar(top_n, x='line_total', y='product_sku', orientation='h', text='line_total')
        fig.update_traces(texttemplate='%{text:,.0f} €', textposition='outside')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Aucun produit")


# TAB 3
with tab3:
    st.subheader("👥 Top clients")
    clients = invoices_unique.groupby('customer_name')['total'].agg(['sum', 'count']).reset_index()
    clients.columns = ['Client', 'CA', 'Nb factures']
    clients = clients[clients['Client'].notna() & (clients['Client'] != '')]
    clients = clients.sort_values('CA', ascending=False)
    if not clients.empty:
        st.dataframe(clients.head(20), use_container_width=True)
        fig = px.bar(clients.head(10), x='CA', y='Client', orientation='h')
        st.plotly_chart(fig, use_container_width=True)


# TAB 4
with tab4:
    st.subheader("🏭 Fournisseurs")
    fourn = invoices_unique[invoices_unique['fournisseur'] != 'Non spécifié'].groupby('fournisseur')['total'].sum().reset_index()
    fourn = fourn.sort_values('total', ascending=False)
    if not fourn.empty:
        st.dataframe(fourn, use_container_width=True)
        fig = px.bar(fourn.head(15), x='fournisseur', y='total', title="CA par fournisseur")
        st.plotly_chart(fig, use_container_width=True)


# TAB 5
with tab5:
    st.subheader("📋 Détail factures")
    cols = ['invoice_number', 'customer_name', 'date', 'gestionnaire', 'total', 'cogs_total', 'frais_transport', 'marge_nette', 'taux_marge']
    cols = [c for c in cols if c in invoices_unique.columns]
    if cols:
        disp = invoices_unique[cols].copy()
        disp = disp.rename(columns={
            'invoice_number': 'Facture', 'customer_name': 'Client', 'date': 'Date',
            'gestionnaire': 'Gestionnaire', 'total': 'CA', 'cogs_total': 'COGS',
            'frais_transport': 'Transport', 'marge_nette': 'Marge', 'taux_marge': 'Taux'
        })
        if 'Date' in disp.columns:
            disp['Date'] = pd.to_datetime(disp['Date']).dt.strftime('%d/%m/%Y')
        st.dataframe(disp, use_container_width=True, height=500)
        csv = disp.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 CSV", csv, "factures.csv")


# ========== EXPORT ==========
st.markdown("---")
csv_all = invoices_unique.to_csv(index=False).encode('utf-8-sig')
st.download_button("📥 Toutes les factures", csv_all, f"factures_{start_date}_{end_date}.csv")


# ========== FOOTER ==========
st.caption(f"📊 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.caption(f"📅 {start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}")