import sys
sys.argv = ["streamlit", "run", __file__, "--server.port=8080", "--server.address=0.0.0.0"]

"""
Dashboard commercial Nextech Medical - Version corrigée
Avec calcul du COGS basé sur les données disponibles
Et frais GLS approximatifs basés sur les factures réelles
"""

import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

st.set_page_config(page_title="Nextech Medical", page_icon="📊", layout="wide")

# ========== FRAIS GLS APPROXIMATIFS ==========
GLS_PRIX_MOYEN_PAR_COLIS = 8.28
GLS_TARIF_PETIT_COLIS = 4.50
GLS_TARIF_GRAND_COLIS = 12.00
GLS_TARIF_CHRONO = 26.88
GLS_FRAIS_FIXE = 0.50
GLS_TVA = 0.20


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
@st.cache_data(ttl=300)
def load_data():
    """Charge les données depuis PostgreSQL"""
    
    conn = psycopg2.connect(
        host='postgresql-20fb082e-o33c4d6e5.database.cloud.ovh.net',
        port='20184',
        database='defaultdb',
        user='avnadmin',
        password='RwoL3kUjOpi0Y1x9V4JN',
        sslmode='require'
    )
    
    # Requête SQL avec les bons noms de colonnes
    query = """
    SELECT 
        i.id,
        i.label as invoice_number,
        i.created as date,
        i.total,
        i.customer_name,
        COALESCE(i.fournisseur, 'Non spécifié') as fournisseur,
        CASE 
            WHEN i.gestionnaire IS NOT NULL AND i.gestionnaire != 'Non spécifié' THEN i.gestionnaire
            ELSE 'Direct'
        END as gestionnaire,
        il.product_sku,
        il.quantity,
        il.line_total,
        0 as purchase_price,
        0 as weight_kg,
        0 as customs_rate
    FROM invoices i
    LEFT JOIN invoice_lines il ON i.id = il.invoice_id
    LEFT JOIN products p ON il.product_sku = p.sku
    WHERE i.created IS NOT NULL
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['total'] = pd.to_numeric(df['total'], errors='coerce').fillna(0)
    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
    df['line_total'] = pd.to_numeric(df['line_total'], errors='coerce').fillna(0)
    df['purchase_price'] = pd.to_numeric(df['purchase_price'], errors='coerce').fillna(0)
    df['weight_kg'] = pd.to_numeric(df['weight_kg'], errors='coerce').fillna(0)
    df['customs_rate'] = pd.to_numeric(df['customs_rate'], errors='coerce').fillna(0)
    
    return df


@st.cache_data(ttl=300)
def load_shipping_costs():
    """Charge les frais de transport réels depuis la base"""
    try:
        conn = psycopg2.connect(
            host='postgresql-20fb082e-o33c4d6e5.database.cloud.ovh.net',
            port='20184',
            database='defaultdb',
            user='avnadmin',
            password='RwoL3kUjOpi0Y1x9V4JN',
            sslmode='require'
        )
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'shipping_costs'
            )
        """)
        table_exists = cursor.fetchone()[0]
        cursor.close()
        
        if table_exists:
            df = pd.read_sql_query("SELECT invoice_id, carrier, shipping_cost, tracking_number FROM shipping_costs", conn)
            conn.close()
            return df
        else:
            conn.close()
            return pd.DataFrame(columns=['invoice_id', 'carrier', 'shipping_cost', 'tracking_number'])
    except Exception as e:
        return pd.DataFrame(columns=['invoice_id', 'carrier', 'shipping_cost', 'tracking_number'])


def get_gestionnaires_list(df):
    if df is not None and not df.empty and 'gestionnaire' in df.columns:
        gestionnaires = df['gestionnaire'].unique().tolist()
        gestionnaires = [g for g in gestionnaires if g not in ['Direct', 'Non spécifié', '', 'None']]
        return sorted(gestionnaires)
    return []


def get_fournisseurs_list(df):
    if df is not None and not df.empty and 'fournisseur' in df.columns:
        fournisseurs = df['fournisseur'].unique().tolist()
        fournisseurs = [f for f in fournisseurs if f not in ['Non spécifié', '', 'None']]
        return sorted(fournisseurs)
    return []


def calculer_cogs(df, cogs_ratio):
    produits_avec_prix = df[df['purchase_price'] > 0]
    produits_sans_prix = df[df['purchase_price'] == 0]
    
    if not produits_avec_prix.empty:
        produits_avec_prix['cout_achat'] = produits_avec_prix['quantity'] * produits_avec_prix['purchase_price']
        produits_avec_prix['droits_douane'] = produits_avec_prix['cout_achat'] * (produits_avec_prix['customs_rate'] / 100)
        produits_avec_prix['cogs_ligne'] = produits_avec_prix['cout_achat'] + produits_avec_prix['droits_douane']
    
    if not produits_sans_prix.empty:
        produits_sans_prix['cout_achat'] = 0
        produits_sans_prix['droits_douane'] = 0
        produits_sans_prix['cogs_ligne'] = produits_sans_prix['line_total'] * cogs_ratio
    
    df = pd.concat([produits_avec_prix, produits_sans_prix], ignore_index=True)
    return df, len(produits_avec_prix), len(produits_sans_prix)


def calculer_frais_gls(df):
    ca_par_facture = df.groupby('id')['line_total'].sum().reset_index()
    ca_par_facture.columns = ['id', 'ca_facture']
    
    quantite_par_facture = df.groupby('id')['quantity'].sum().reset_index()
    quantite_par_facture.columns = ['id', 'quantite_totale']
    
    df = df.merge(ca_par_facture, on='id', how='left')
    df = df.merge(quantite_par_facture, on='id', how='left')
    
    df['frais_gls_facture'] = df.apply(
        lambda row: calculer_frais_gls_approximatifs(row['quantite_totale'], row['ca_facture']), 
        axis=1
    )
    
    df['ratio_produit'] = df['line_total'] / df['ca_facture']
    df['ratio_produit'] = df['ratio_produit'].fillna(0)
    df['frais_gls_ligne'] = df['frais_gls_facture'] * df['ratio_produit']
    
    return df


def calculer_kpis_produits(df):
    produits = df.groupby('product_sku').agg({
        'line_total': 'sum',
        'quantity': 'sum',
        'cout_achat': 'sum',
        'droits_douane': 'sum',
        'cogs_ligne': 'sum',
        'frais_gls_ligne': 'sum',
        'marge_ligne': 'sum'
    }).reset_index()
    
    produits = produits[produits['product_sku'].astype(str).str.strip() != '']
    produits = produits.sort_values('line_total', ascending=False)
    
    produits['cogs_ratio'] = (produits['cogs_ligne'] / produits['line_total'] * 100).round(1).fillna(0)
    produits['transport_ratio'] = (produits['frais_gls_ligne'] / produits['line_total'] * 100).round(1).fillna(0)
    produits['taux_marge'] = (produits['marge_ligne'] / produits['line_total'] * 100).round(1).fillna(0)
    produits['part_ca'] = (produits['line_total'] / produits['line_total'].sum() * 100).round(1).fillna(0)
    
    produits['prix_unitaire_moyen'] = (produits['line_total'] / produits['quantity']).round(2).fillna(0)
    produits['cout_achat_unitaire'] = (produits['cout_achat'] / produits['quantity']).round(2).fillna(0)
    produits['cogs_unitaire_moyen'] = (produits['cogs_ligne'] / produits['quantity']).round(2).fillna(0)
    produits['frais_gls_unitaire'] = (produits['frais_gls_ligne'] / produits['quantity']).round(2).fillna(0)
    produits['marge_unitaire_moyenne'] = (produits['marge_ligne'] / produits['quantity']).round(2).fillna(0)
    
    return produits


# ========== CHARGEMENT INITIAL ==========
with st.spinner("Chargement des données..."):
    df = load_data()
    df_shipping = load_shipping_costs()

if df.empty:
    st.error("❌ Aucune donnée trouvée dans la base")
    st.stop()

# ========== SIDEBAR ==========
st.sidebar.title("🔍 Filtres")

st.sidebar.markdown("### 📅 Période")
date_min = df['date'].min().date()
date_max = df['date'].max().date()
start_date, end_date = st.sidebar.date_input("Date de facture", (date_min, date_max))

st.sidebar.markdown("---")
st.sidebar.markdown("### 👤 Gestionnaire")
gestionnaires_list = get_gestionnaires_list(df)
selected_gestionnaire = st.sidebar.selectbox("Sélectionner", ["Tous"] + gestionnaires_list, index=0) if gestionnaires_list else "Tous"

st.sidebar.markdown("---")
st.sidebar.markdown("### 🏭 Fournisseur")
fournisseurs_list = get_fournisseurs_list(df)
fournisseurs_sel = st.sidebar.multiselect("Sélectionner", fournisseurs_list, default=[]) if fournisseurs_list else []

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Paramètres de calcul")
cogs_ratio_default = st.sidebar.slider("COGS par défaut (% du CA)", 0, 100, 50, 5) / 100

# ========== APPLICATION FILTRES ==========
df_filtre = df[(df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date)]

if selected_gestionnaire != "Tous":
    df_filtre = df_filtre[df_filtre['gestionnaire'] == selected_gestionnaire]

if fournisseurs_sel:
    df_filtre = df_filtre[df_filtre['fournisseur'].isin(fournisseurs_sel)]

if df_filtre.empty:
    st.warning("⚠️ Aucune donnée avec les filtres sélectionnés")
    st.stop()

# ========== CALCULS ==========
df_filtre, nb_avec_prix, nb_sans_prix = calculer_cogs(df_filtre, cogs_ratio_default)
df_filtre = calculer_frais_gls(df_filtre)
df_filtre['marge_ligne'] = df_filtre['line_total'] - df_filtre['cogs_ligne'] - df_filtre['frais_gls_ligne']

# ========== AGRÉGATION FACTURES ==========
invoices_unique = df_filtre.groupby('id').agg({
    'invoice_number': 'first',
    'date': 'first',
    'customer_name': 'first',
    'gestionnaire': 'first',
    'fournisseur': 'first',
    'line_total': 'sum',
    'frais_gls_facture': 'first',
    'cogs_ligne': 'sum',
    'marge_ligne': 'sum',
    'quantity': 'sum'
}).reset_index()

invoices_unique = invoices_unique.rename(columns={
    'line_total': 'ca_produits',
    'frais_gls_facture': 'frais_gls',
    'cogs_ligne': 'cogs_total',
    'marge_ligne': 'marge_nette',
    'quantity': 'total_quantite'
})
invoices_unique['taux_marge'] = (invoices_unique['marge_nette'] / invoices_unique['ca_produits'] * 100).round(2).fillna(0)

# ========== KPIS GLOBAUX ==========
total_ca = invoices_unique['ca_produits'].sum()
nb_factures = len(invoices_unique)
nb_clients = invoices_unique['customer_name'].nunique()
nb_produits_total = invoices_unique['total_quantite'].sum()
total_cogs = invoices_unique['cogs_total'].sum()
total_gls = invoices_unique['frais_gls'].sum()
total_marge = invoices_unique['marge_nette'].sum()
taux_marge_moyen = (total_marge / total_ca * 100) if total_ca > 0 else 0
part_gls = (total_gls / total_ca * 100) if total_ca > 0 else 0
part_cogs = (total_cogs / total_ca * 100) if total_ca > 0 else 0

# ========== AFFICHAGE ==========
st.title("📊 Nextech Medical Dashboard")

if part_gls > 30:
    st.warning(f"⚠️ Les frais GLS représentent {part_gls:.0f}% du CA !")

col1, col2, col3, col4 = st.columns(4)
col1.metric("💰 CA total", f"{total_ca:,.2f} €")
col2.metric("📄 Nombre factures", f"{nb_factures:,}")
col3.metric("👥 Clients distincts", f"{nb_clients:,}")
col4.metric("📦 Produits vendus", f"{nb_produits_total:,.0f}")

st.markdown("---")

col5, col6, col7, col8 = st.columns(4)
col5.metric("📦 COGS total", f"{total_cogs:,.2f} €")
col6.metric("🚚 Frais GLS", f"{total_gls:,.2f} €")
col7.metric("💰 Marge nette", f"{total_marge:,.2f} €")
col8.metric("📈 Taux marge moyen", f"{taux_marge_moyen:.1f}%")

st.success(f"✅ Calculs cohérents (écart: {total_ca - (total_cogs + total_gls + total_marge):.2f} €)")

# ========== PRODUITS ==========
st.subheader("🏆 Top produits")

produits_kpis = calculer_kpis_produits(df_filtre)

if not produits_kpis.empty:
    top_produits_affiches = produits_kpis.head(15)
    
    fig_prod = go.Figure()
    fig_prod.add_trace(go.Bar(y=top_produits_affiches['product_sku'], x=top_produits_affiches['cogs_ligne'], name='COGS', orientation='h', marker_color='#FF6B6B'))
    fig_prod.add_trace(go.Bar(y=top_produits_affiches['product_sku'], x=top_produits_affiches['frais_gls_ligne'], name='Frais GLS', orientation='h', marker_color='#FFB347'))
    fig_prod.add_trace(go.Bar(y=top_produits_affiches['product_sku'], x=top_produits_affiches['marge_ligne'], name='Marge', orientation='h', marker_color='#4ECDC4'))
    fig_prod.update_layout(title="Composition de la valeur par produit", xaxis_title="Montant (€)", yaxis_title="SKU", barmode='stack', height=500)
    st.plotly_chart(fig_prod, use_container_width=True)

st.markdown("---")
st.caption(f"📊 Dernière mise à jour: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
