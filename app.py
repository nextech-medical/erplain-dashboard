# dashboard_avance_final.py

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
import json
import os
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

st.set_page_config(page_title="Nextech Medical", page_icon="📊", layout="wide")

# ========== FRAIS GLS APPROXIMATIFS (basés sur factures réelles) ==========
# Valeurs moyennes calculées à partir des factures GLS fournies
GLS_PRIX_MOYEN_PAR_COLIS = 8.28  # 198.83€ / 24 colis
GLS_TARIF_PETIT_COLIS = 4.50     # Pour les petits colis (type BP/FDP léger)
GLS_TARIF_GRAND_COLIS = 12.00    # Pour les grands colis (type FDP lourd)
GLS_TARIF_CHRONO = 26.88         # Pour le service express (SHD2)
GLS_FRAIS_FIXE = 0.50            # Frais fixe par commande

# Nombre approximatif de colis par commande (à ajuster selon votre réalité)
# Hypothèse: 1 colis = regroupement de 5 à 10 produits
COLIS_PAR_COMMANDE_MOYEN = 1

# Taux de TVA pour les frais GLS
GLS_TVA = 0.20


def calculer_frais_gls_approximatifs(quantite_totale, ca_facture):
    """
    Calcule les frais GLS approximatifs basés sur les valeurs réelles des factures
    
    Args:
        quantite_totale: Nombre total de produits dans la commande
        ca_facture: Chiffre d'affaires de la commande
    
    Returns:
        Frais GLS estimés en HT
    """
    # Méthode 1: Basé sur la quantité (1 colis pour environ 10 produits)
    nb_colis_estime = max(1, round(quantite_totale / 10))
    
    # Méthode 2: Basé sur le CA (pour les petites commandes)
    if ca_facture < 50:
        # Petite commande: 1 petit colis
        frais_base = GLS_TARIF_PETIT_COLIS
        nb_colis_estime = 1
    elif ca_facture < 200:
        # Commande moyenne: 1-2 colis
        frais_base = GLS_PRIX_MOYEN_PAR_COLIS
    else:
        # Grande commande: plusieurs colis
        frais_base = GLS_PRIX_MOYEN_PAR_COLIS
    
    frais_ht = (nb_colis_estime * frais_base) + GLS_FRAIS_FIXE
    
    # Plafonner à 15% du CA pour les petites commandes, 10% pour les grandes
    plafond = ca_facture * 0.12
    frais_ht = min(frais_ht, plafond)
    
    return round(frais_ht, 2)


@st.cache_data(ttl=300)
def load_data():
    """Charge les données depuis PostgreSQL"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        options="-c client_encoding=UTF8"
    )
    
    # D'abord, vérifions quelles colonnes existent dans la table products
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'products'
        """)
        existing_columns = [row[0] for row in cursor.fetchall()]
        cursor.close()
    except:
        existing_columns = []
    
    # Construire la requête dynamiquement
    purchase_price_col = "NULL as purchase_price"
    weight_col = "NULL as weight_kg"
    customs_col = "NULL as customs_rate"
    
    if 'purchase_price' in existing_columns:
        purchase_price_col = "p.purchase_price"
    if 'weight_kg' in existing_columns:
        weight_col = "p.weight_kg"
    if 'customs_rate' in existing_columns:
        customs_col = "p.customs_rate"
    if 'cout_achat' in existing_columns:
        purchase_price_col = "p.cout_achat"
    
    query = f"""
    SELECT 
        i.id,
        i.label as invoice_number,
        i.invoice_created as date,
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
        COALESCE({purchase_price_col}, 0) as purchase_price,
        COALESCE({weight_col}, 0) as weight_kg,
        COALESCE({customs_col}, 0) as customs_rate
    FROM invoices i
    LEFT JOIN invoice_lines il ON i.id = il.invoice_id
    LEFT JOIN products p ON il.product_sku = p.sku
    WHERE i.invoice_created IS NOT NULL
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
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        
        # Vérifier si la table shipping_costs existe
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
            query = """
            SELECT 
                invoice_id,
                carrier,
                shipping_cost,
                tracking_number
            FROM shipping_costs
            """
            df = pd.read_sql_query(query, conn)
            conn.close()
            return df
        else:
            conn.close()
            return pd.DataFrame(columns=['invoice_id', 'carrier', 'shipping_cost', 'tracking_number'])
    except:
        return pd.DataFrame(columns=['invoice_id', 'carrier', 'shipping_cost', 'tracking_number'])


def get_gestionnaires_list(df):
    """Récupère la liste des gestionnaires uniques"""
    if df is not None and not df.empty and 'gestionnaire' in df.columns:
        gestionnaires = df['gestionnaire'].unique().tolist()
        gestionnaires = [g for g in gestionnaires if g not in ['Direct', 'Non spécifié', '', 'None']]
        return sorted(gestionnaires)
    return []


def get_fournisseurs_list(df):
    """Récupère la liste des fournisseurs uniques"""
    if df is not None and not df.empty and 'fournisseur' in df.columns:
        fournisseurs = df['fournisseur'].unique().tolist()
        fournisseurs = [f for f in fournisseurs if f not in ['Non spécifié', '', 'None']]
        return sorted(fournisseurs)
    return []


def calculer_cogs(df, cogs_ratio):
    """
    Calcule le COGS :
    - Si purchase_price existe, l'utilise
    - Sinon, utilise le ratio COGS/CA
    """
    produits_avec_prix = df[df['purchase_price'] > 0]
    produits_sans_prix = df[df['purchase_price'] == 0]
    
    # Pour les produits avec prix d'achat
    if not produits_avec_prix.empty:
        produits_avec_prix['cout_achat'] = produits_avec_prix['quantity'] * produits_avec_prix['purchase_price']
        produits_avec_prix['droits_douane'] = produits_avec_prix['cout_achat'] * (produits_avec_prix['customs_rate'] / 100)
        produits_avec_prix['cogs_ligne'] = produits_avec_prix['cout_achat'] + produits_avec_prix['droits_douane']
    
    # Pour les produits sans prix d'achat, utiliser le ratio
    if not produits_sans_prix.empty:
        produits_sans_prix['cout_achat'] = 0
        produits_sans_prix['droits_douane'] = 0
        produits_sans_prix['cogs_ligne'] = produits_sans_prix['line_total'] * cogs_ratio
    
    # Combiner
    df = pd.concat([produits_avec_prix, produits_sans_prix], ignore_index=True)
    
    return df, len(produits_avec_prix), len(produits_sans_prix)


def calculer_frais_gls(df):
    """
    Calcule les frais GLS approximatifs basés sur les valeurs réelles des factures
    """
    # Calculer le CA total par facture et la quantité totale
    ca_par_facture = df.groupby('id')['line_total'].sum().reset_index()
    ca_par_facture.columns = ['id', 'ca_facture']
    
    quantite_par_facture = df.groupby('id')['quantity'].sum().reset_index()
    quantite_par_facture.columns = ['id', 'quantite_totale']
    
    # Fusionner
    df = df.merge(ca_par_facture, on='id', how='left')
    df = df.merge(quantite_par_facture, on='id', how='left')
    
    # Appliquer la fonction de calcul des frais GLS pour chaque facture
    df['frais_gls_facture'] = df.apply(
        lambda row: calculer_frais_gls_approximatifs(row['quantite_totale'], row['ca_facture']), 
        axis=1
    )
    
    # Répartir proportionnellement par produit
    df['ratio_produit'] = df['line_total'] / df['ca_facture']
    df['ratio_produit'] = df['ratio_produit'].fillna(0)
    df['frais_gls_ligne'] = df['frais_gls_facture'] * df['ratio_produit']
    
    return df


def calculer_kpis_produits(df):
    """
    Calcule les KPIS par produit
    """
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
    
    # Calcul des indicateurs
    produits['cogs_ratio'] = (produits['cogs_ligne'] / produits['line_total'] * 100).round(1).fillna(0)
    produits['transport_ratio'] = (produits['frais_gls_ligne'] / produits['line_total'] * 100).round(1).fillna(0)
    produits['taux_marge'] = (produits['marge_ligne'] / produits['line_total'] * 100).round(1).fillna(0)
    produits['part_ca'] = (produits['line_total'] / produits['line_total'].sum() * 100).round(1).fillna(0)
    
    # Prix unitaire moyen
    produits['prix_unitaire_moyen'] = (produits['line_total'] / produits['quantity']).round(2).fillna(0)
    produits['cout_achat_unitaire'] = (produits['cout_achat'] / produits['quantity']).round(2).fillna(0)
    produits['cogs_unitaire_moyen'] = (produits['cogs_ligne'] / produits['quantity']).round(2).fillna(0)
    produits['frais_gls_unitaire'] = (produits['frais_gls_ligne'] / produits['quantity']).round(2).fillna(0)
    produits['marge_unitaire_moyenne'] = (produits['marge_ligne'] / produits['quantity']).round(2).fillna(0)
    
    return produits


# ========== CHARGEMENT DES DONNÉES ==========
with st.spinner("Chargement des données..."):
    df = load_data()
    df_shipping = load_shipping_costs()

if df.empty:
    st.error("❌ Aucune donnée trouvée dans la base")
    st.stop()


# ========== SIDEBAR - FILTRES ==========
st.sidebar.title("🔍 Filtres")

st.sidebar.markdown("### 📅 Période")
date_min = df['date'].min().date()
date_max = df['date'].max().date()
start_date, end_date = st.sidebar.date_input("Date de facture", (date_min, date_max))

st.sidebar.markdown("---")

st.sidebar.markdown("### 👤 Gestionnaire")
gestionnaires_list = get_gestionnaires_list(df)
if gestionnaires_list:
    selected_gestionnaire = st.sidebar.selectbox("Sélectionner", ["Tous"] + gestionnaires_list, index=0)
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

st.sidebar.markdown("### ⚙️ Paramètres de calcul")

# Ratio COGS par défaut (utilisé uniquement pour produits sans prix d'achat)
cogs_ratio_default = st.sidebar.slider("COGS par défaut (% du CA)", 0, 100, 50, 5) / 100
st.sidebar.caption("💡 Utilisé uniquement pour les produits sans prix d'achat")

# Informations sur les frais GLS
st.sidebar.markdown("---")
st.sidebar.markdown("### 📦 Frais GLS approximatifs")
st.sidebar.metric("💰 Prix moyen par colis", f"{GLS_PRIX_MOYEN_PAR_COLIS:.2f} €")
st.sidebar.metric("🚚 Petit colis", f"{GLS_TARIF_PETIT_COLIS:.2f} €")
st.sidebar.metric("📦 Grand colis", f"{GLS_TARIF_GRAND_COLIS:.2f} €")
st.sidebar.metric("⚡ Chrono (SHD2)", f"{GLS_TARIF_CHRONO:.2f} €")
st.sidebar.caption("💡 Valeurs basées sur les factures GLS réelles")

# ========== APPLICATION DES FILTRES ==========
df_filtre = df[(df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date)]

if selected_gestionnaire != "Tous":
    df_filtre = df_filtre[df_filtre['gestionnaire'] == selected_gestionnaire]

if fournisseurs_sel:
    df_filtre = df_filtre[df_filtre['fournisseur'].isin(fournisseurs_sel)]

if df_filtre.empty:
    st.warning("⚠️ Aucune donnée avec les filtres sélectionnés")
    st.stop()


# ========== CALCULS ==========

# 1. Calcul du COGS
df_filtre, nb_avec_prix, nb_sans_prix = calculer_cogs(df_filtre, cogs_ratio_default)

# 2. Calcul des frais GLS (approximatifs basés sur valeurs réelles)
df_filtre = calculer_frais_gls(df_filtre)

# 3. Marge par ligne
df_filtre['marge_ligne'] = df_filtre['line_total'] - df_filtre['cogs_ligne'] - df_filtre['frais_gls_ligne']


# ========== AGRÉGATION PAR FACTURE ==========
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

# Calcul du taux de marge
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

# Vérification de cohérence
somme_verif = total_cogs + total_gls + total_marge
verification_finale = total_ca - somme_verif

if abs(verification_finale) > 1:
    st.warning(f"⚠️ Écart de {verification_finale:.2f} € - Vérifiez les prix d'achat")
else:
    st.success(f"✅ Calculs cohérents (écart: {verification_finale:.2f} €)")


# ========== CALCUL DES KPIS PAR PRODUIT ==========
produits_kpis = calculer_kpis_produits(df_filtre)


# ========== HEADER ==========
st.title("📊 Nextech Medical Dashboard")

# Alertes
if part_gls > 30:
    st.warning(f"⚠️ Les frais GLS représentent {part_gls:.0f}% du CA !")
if taux_marge_moyen < 0:
    st.error(f"⚠️ Marge négative moyenne: {taux_marge_moyen:.1f}%")


# ========== AFFICHAGE KPIS PRINCIPAUX ==========
st.subheader("📊 Indicateurs clés")

col1, col2, col3, col4 = st.columns(4)
col1.metric("💰 CA total", f"{total_ca:,.2f} €")
col2.metric("📄 Nombre factures", f"{nb_factures:,}")
col3.metric("👥 Clients distincts", f"{nb_clients:,}")
col4.metric("📦 Produits vendus", f"{nb_produits_total:,.0f}")

st.markdown("---")

col5, col6, col7, col8, col9 = st.columns(5)
col5.metric("📦 COGS total", f"{total_cogs:,.2f} €")
col6.metric("🚚 Frais GLS", f"{total_gls:,.2f} €")
col7.metric("💰 Marge nette", f"{total_marge:,.2f} €")
col8.metric("📈 Taux marge moyen", f"{taux_marge_moyen:.1f}%")
col9.metric("📊 Ratio COGS+GLS", f"{(part_cogs+part_gls):.1f}%")

st.markdown("---")

cogs_mode = "prix d'achat" if nb_avec_prix > 0 else "estimation"

if selected_gestionnaire != "Tous":
    st.info(f"📌 Gestionnaire filtré: **{selected_gestionnaire}**")

if fournisseurs_sel:
    st.info(f"🏭 Fournisseurs filtrés: **{', '.join(fournisseurs_sel[:3])}{'...' if len(fournisseurs_sel) > 3 else ''}**")


# ========== ONGLETS ==========
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 Vue d'ensemble",
    "🏆 Top produits",
    "👥 Top clients",
    "🏭 Fournisseurs",
    "📋 Détail factures"
])


# ========== TAB 1: VUE D'ENSEMBLE ==========
with tab1:
    col_graph1, col_graph2 = st.columns(2)
    
    with col_graph1:
        if not invoices_unique.empty:
            ca_jour = invoices_unique.groupby('date')['ca_produits'].sum().reset_index()
            fig_ca = px.line(ca_jour, x='date', y='ca_produits', 
                            title="CA par jour", markers=True,
                            labels={'ca_produits': 'CA (€)', 'date': 'Date'})
            st.plotly_chart(fig_ca, use_container_width=True)
    
    with col_graph2:
        if not invoices_unique.empty:
            gls_jour = invoices_unique.groupby('date')['frais_gls'].sum().reset_index()
            fig_gls = px.line(gls_jour, x='date', y='frais_gls',
                              title="Frais GLS par jour", markers=True,
                              labels={'frais_gls': 'Frais GLS (€)', 'date': 'Date'},
                              color_discrete_sequence=['#FFB347'])
            st.plotly_chart(fig_gls, use_container_width=True)
    
    # Graphique COGS / GLS / Marge
    st.subheader("💰 Analyse détaillée des coûts")
    
    daily_costs = invoices_unique.groupby('date').agg({
        'ca_produits': 'sum',
        'cogs_total': 'sum',
        'frais_gls': 'sum',
        'marge_nette': 'sum'
    }).reset_index()
    
    fig_costs = go.Figure()
    
    fig_costs.add_trace(go.Bar(
        x=daily_costs['date'],
        y=daily_costs['cogs_total'],
        name='COGS',
        marker_color='#FF6B6B',
        text=daily_costs['cogs_total'].apply(lambda x: f'{x:,.0f}€'),
        textposition='inside'
    ))
    
    fig_costs.add_trace(go.Bar(
        x=daily_costs['date'],
        y=daily_costs['frais_gls'],
        name='Frais GLS',
        marker_color='#FFB347',
        text=daily_costs['frais_gls'].apply(lambda x: f'{x:,.0f}€'),
        textposition='inside'
    ))
    
    fig_costs.add_trace(go.Bar(
        x=daily_costs['date'],
        y=daily_costs['marge_nette'],
        name='Marge nette',
        marker_color='#4ECDC4',
        text=daily_costs['marge_nette'].apply(lambda x: f'{x:,.0f}€'),
        textposition='inside'
    ))
    
    fig_costs.update_layout(
        title="COGS / Frais GLS / Marge par jour",
        xaxis_title="Date",
        yaxis_title="Montant (€)",
        barmode='group',
        legend=dict(x=0, y=1, orientation='h'),
        height=450
    )
    
    st.plotly_chart(fig_costs, use_container_width=True)
    
    # Version pourcentage
    daily_costs['total'] = daily_costs['ca_produits']
    
    fig_costs_pct = go.Figure()
    
    fig_costs_pct.add_trace(go.Bar(
        x=daily_costs['date'],
        y=(daily_costs['cogs_total'] / daily_costs['total'] * 100).fillna(0),
        name='COGS',
        marker_color='#FF6B6B',
        text=(daily_costs['cogs_total'] / daily_costs['total'] * 100).fillna(0),
        texttemplate='%{text:.1f}%',
        textposition='inside'
    ))
    
    fig_costs_pct.add_trace(go.Bar(
        x=daily_costs['date'],
        y=(daily_costs['frais_gls'] / daily_costs['total'] * 100).fillna(0),
        name='Frais GLS',
        marker_color='#FFB347',
        text=(daily_costs['frais_gls'] / daily_costs['total'] * 100).fillna(0),
        texttemplate='%{text:.1f}%',
        textposition='inside'
    ))
    
    fig_costs_pct.add_trace(go.Bar(
        x=daily_costs['date'],
        y=(daily_costs['marge_nette'] / daily_costs['total'] * 100).fillna(0),
        name='Marge nette',
        marker_color='#4ECDC4',
        text=(daily_costs['marge_nette'] / daily_costs['total'] * 100).fillna(0),
        texttemplate='%{text:.1f}%',
        textposition='inside'
    ))

    
    # ========== DISTRIBUTION DES MARGES ==========
    st.subheader("📊 Analyse des marges par facture")
    
    col_dist1, col_dist2 = st.columns(2)
    
    with col_dist1:
        # Statistiques simples
        st.metric("📈 Taux de marge moyen", f"{taux_marge_moyen:.1f}%")
        st.metric("📊 Factures avec marge positive", f"{len(invoices_unique[invoices_unique['taux_marge'] > 0])} / {nb_factures}")
        st.metric("📉 Factures avec marge négative", f"{len(invoices_unique[invoices_unique['taux_marge'] < 0])} / {nb_factures}")
    
    with col_dist2:
        # Pie chart simple
        marge_status = invoices_unique['taux_marge'].apply(lambda x: 'Marge positive' if x > 0 else 'Marge négative')
        marge_counts = marge_status.value_counts()
        
        if not marge_counts.empty:
            fig_pie = px.pie(
                values=marge_counts.values,
                names=marge_counts.index,
                title="Proportion factures rentables vs non rentables",
                color=marge_counts.index,
                color_discrete_map={'Marge positive': '#4ECDC4', 'Marge négative': '#FF6B6B'}
            )
            st.plotly_chart(fig_pie, use_container_width=True)
    
    # Graphique simplifié : seulement les marges entre -100% et +100%
    st.subheader("Distribution des taux de marge (zoom sur -100% à +100%)")
    
    # Filtrer pour éviter les outliers extrêmes
    marges_filtered = invoices_unique[(invoices_unique['taux_marge'] > -100) & (invoices_unique['taux_marge'] < 100)]['taux_marge']
    
    if not marges_filtered.empty:
        fig_hist_simple = px.histogram(
            marges_filtered,
            nbins=30,
            title="Distribution des taux de marge (valeurs normales)",
            labels={'value': 'Taux de marge (%)', 'count': 'Nombre de factures'},
            color_discrete_sequence=['#4ECDC4']
        )
        fig_hist_simple.add_vline(x=0, line_dash="dash", line_color="red", 
                                  annotation_text="Seuil rentabilité")
        fig_hist_simple.add_vline(x=taux_marge_moyen, line_dash="dash", line_color="blue",
                                  annotation_text=f"Moyenne: {taux_marge_moyen:.1f}%")
        fig_hist_simple.update_layout(height=400)
        st.plotly_chart(fig_hist_simple, use_container_width=True)
        
        # Ajouter une explication
        st.caption("📖 **Lecture**: Chaque barre représente le nombre de factures ayant un taux de marge dans cet intervalle.")
        st.caption("🔴 **Ligne rouge**: Seuil de rentabilité (0%). Les barres à gauche sont des pertes.")
        st.caption("🔵 **Ligne bleue**: Taux de marge moyen sur la période.")
    else:
        st.info("Pas assez de données pour afficher la distribution")


# ========== TAB 2: TOP PRODUITS ==========
with tab2:
    st.subheader("🏆 Analyse détaillée des produits")
    
    if not produits_kpis.empty:
        nb_prod = st.slider("Nombre de produits à afficher", 5, min(50, len(produits_kpis)), 15, key="top_products")
        
        top_produits_affiches = produits_kpis.head(nb_prod)
        
        # Graphique à barres empilées
        st.subheader("💰 Composition de la valeur par produit")
        
        top_prod_stack = top_produits_affiches.copy()
        top_prod_stack['COGS'] = top_prod_stack['cogs_ligne']
        top_prod_stack['GLS'] = top_prod_stack['frais_gls_ligne']
        top_prod_stack['Marge'] = top_prod_stack['marge_ligne']
        
        fig_prod = go.Figure()
        fig_prod.add_trace(go.Bar(
            y=top_prod_stack['product_sku'],
            x=top_prod_stack['COGS'],
            name='COGS',
            orientation='h',
            marker_color='#FF6B6B',
            text=top_prod_stack['COGS'].apply(lambda x: f'{x:,.0f}€'),
            textposition='inside'
        ))
        fig_prod.add_trace(go.Bar(
            y=top_prod_stack['product_sku'],
            x=top_prod_stack['GLS'],
            name='Frais GLS',
            orientation='h',
            marker_color='#FFB347',
            text=top_prod_stack['GLS'].apply(lambda x: f'{x:,.0f}€'),
            textposition='inside'
        ))
        fig_prod.add_trace(go.Bar(
            y=top_prod_stack['product_sku'],
            x=top_prod_stack['Marge'],
            name='Marge',
            orientation='h',
            marker_color='#4ECDC4',
            text=top_prod_stack['Marge'].apply(lambda x: f'{x:,.0f}€'),
            textposition='inside'
        ))
        
        fig_prod.update_layout(
            title=f"Composition de la valeur par produit (Top {nb_prod})",
            xaxis_title="Montant (€)",
            yaxis_title="SKU",
            barmode='stack',
            height=500
        )
        st.plotly_chart(fig_prod, use_container_width=True)
        
        # Tableau détaillé
        st.subheader("📋 Tableau détaillé des produits")
        
        df_aff = top_produits_affiches[['product_sku', 'line_total', 'quantity', 'cout_achat', 
                                        'cogs_ligne', 'frais_gls_ligne', 'marge_ligne', 
                                        'taux_marge', 'part_ca']].copy()
        df_aff = df_aff.rename(columns={
            'product_sku': 'SKU',
            'line_total': 'CA (€)',
            'quantity': 'Qté',
            'cout_achat': 'Achat (€)',
            'cogs_ligne': 'COGS (€)',
            'frais_gls_ligne': 'GLS (€)',
            'marge_ligne': 'Marge (€)',
            'taux_marge': 'Taux (%)',
            'part_ca': 'Part CA (%)'
        })
        
        st.dataframe(df_aff.style.format({
            'CA (€)': '{:,.2f}',
            'Achat (€)': '{:,.2f}',
            'COGS (€)': '{:,.2f}',
            'GLS (€)': '{:.2f}',
            'Marge (€)': '{:,.2f}',
            'Taux (%)': '{:.1f}',
            'Part CA (%)': '{:.1f}'
        }), use_container_width=True)
        
        # Produits à marge négative
        produits_negatifs = produits_kpis[produits_kpis['marge_ligne'] < 0]
        if not produits_negatifs.empty:
            st.warning(f"⚠️ {len(produits_negatifs)} produits ont une marge négative")
            with st.expander("🔴 Voir les produits à marge négative"):
                st.dataframe(produits_negatifs[['product_sku', 'line_total', 'cogs_ligne', 
                                                'frais_gls_ligne', 'marge_ligne', 'taux_marge']]
                           .head(20).rename(columns={
                               'product_sku': 'SKU',
                               'line_total': 'CA (€)',
                               'cogs_ligne': 'COGS (€)',
                               'frais_gls_ligne': 'GLS (€)',
                               'marge_ligne': 'Marge (€)',
                               'taux_marge': 'Taux (%)'
                           }), use_container_width=True)
    else:
        st.warning("Aucun produit trouvé")


# ========== TAB 3: TOP CLIENTS ==========
with tab3:
    st.subheader("👥 Analyse des clients")
    
    clients = invoices_unique.groupby('customer_name').agg({
        'ca_produits': 'sum',
        'id': 'count',
        'marge_nette': 'sum',
        'frais_gls': 'sum'
    }).reset_index()
    clients.columns = ['Client', 'CA', 'Nb factures', 'Marge', 'Frais GLS']
    clients = clients[clients['Client'].notna() & (clients['Client'] != '')]
    clients = clients.sort_values('CA', ascending=False)
    clients['Taux marge'] = (clients['Marge'] / clients['CA'] * 100).round(1).fillna(0)
    clients['Part CA'] = (clients['CA'] / total_ca * 100).round(1).fillna(0)
    
    if not clients.empty:
        nb_clients_display = st.slider("Nombre de clients à afficher", 5, min(50, len(clients)), 10, key="top_clients")
        
        col_client1, col_client2 = st.columns([2, 1])
        
        with col_client1:
            st.dataframe(clients.head(nb_clients_display).style.format({
                'CA': '{:,.2f} €',
                'Marge': '{:,.2f} €',
                'Frais GLS': '{:.2f} €',
                'Taux marge': '{:.1f}%',
                'Part CA': '{:.1f}%'
            }), use_container_width=True)
        
        with col_client2:
            fig_clients = px.bar(clients.head(nb_clients_display), x='CA', y='Client', orientation='h',
                                title=f"Top {nb_clients_display} clients", text='CA')
            fig_clients.update_traces(texttemplate='%{text:,.0f} €', textposition='outside')
            st.plotly_chart(fig_clients, use_container_width=True)
        
        clients_negatifs = clients[clients['Marge'] < 0]
        if not clients_negatifs.empty:
            st.warning(f"⚠️ {len(clients_negatifs)} clients ont une marge négative")
            with st.expander("Voir les clients à marge négative"):
                st.dataframe(clients_negatifs[['Client', 'CA', 'Marge', 'Taux marge']].head(20), use_container_width=True)
    else:
        st.warning("Aucun client trouvé")


# ========== TAB 4: FOURNISSEURS ==========
with tab4:
    st.subheader("🏭 Analyse par fournisseur")
    
    fourn_analysis = invoices_unique[invoices_unique['fournisseur'] != 'Non spécifié'].groupby('fournisseur').agg({
        'ca_produits': 'sum',
        'id': 'count',
        'marge_nette': 'sum',
        'frais_gls': 'sum'
    }).reset_index()
    
    if not fourn_analysis.empty:
        fourn_analysis.columns = ['Fournisseur', 'CA', 'Nb factures', 'Marge', 'Frais GLS']
        fourn_analysis = fourn_analysis.sort_values('CA', ascending=False)
        fourn_analysis['Taux marge'] = (fourn_analysis['Marge'] / fourn_analysis['CA'] * 100).round(1).fillna(0)
        fourn_analysis['Part CA'] = (fourn_analysis['CA'] / total_ca * 100).round(1).fillna(0)
        
        st.dataframe(fourn_analysis.style.format({
            'CA': '{:,.2f} €',
            'Marge': '{:,.2f} €',
            'Frais GLS': '{:.2f} €',
            'Taux marge': '{:.1f}%',
            'Part CA': '{:.1f}%'
        }), use_container_width=True)
        
        col_fourn1, col_fourn2 = st.columns(2)
        
        with col_fourn1:
            fig_fourn = px.bar(fourn_analysis.head(15), x='Fournisseur', y='CA', 
                              title="CA par fournisseur", text='CA')
            fig_fourn.update_traces(texttemplate='%{text:,.0f} €', textposition='outside')
            st.plotly_chart(fig_fourn, use_container_width=True)
        
        with col_fourn2:
            fig_fourn_marge = px.bar(fourn_analysis.head(15), x='Fournisseur', y='Taux marge',
                                     title="Taux de marge par fournisseur", text='Taux marge',
                                     color='Taux marge', color_continuous_scale='RdYlGn')
            fig_fourn_marge.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            st.plotly_chart(fig_fourn_marge, use_container_width=True)
    else:
        st.info("Aucune donnée fournisseur disponible")


# ========== TAB 5: DÉTAIL FACTURES ==========
with tab5:
    st.subheader("📋 Détail des factures")
    
    cols_aff = ['invoice_number', 'customer_name', 'date', 'gestionnaire', 'fournisseur', 
                'ca_produits', 'cogs_total', 'frais_gls', 'marge_nette', 'taux_marge', 
                'total_quantite']
    
    disp = invoices_unique[cols_aff].copy()
    disp = disp.rename(columns={
        'invoice_number': 'Facture',
        'customer_name': 'Client',
        'date': 'Date',
        'gestionnaire': 'Gestionnaire',
        'fournisseur': 'Fournisseur',
        'ca_produits': 'CA (€)',
        'cogs_total': 'COGS (€)',
        'frais_gls': 'GLS (€)',
        'marge_nette': 'Marge (€)',
        'taux_marge': 'Taux (%)',
        'total_quantite': 'Qté'
    })
    
    if 'Date' in disp.columns:
        disp['Date'] = pd.to_datetime(disp['Date']).dt.strftime('%d/%m/%Y')
    
    col_filter1, col_filter2 = st.columns(2)
    with col_filter1:
        show_negatives = st.checkbox("🔴 Afficher uniquement les marges négatives", key="show_negatives")
    with col_filter2:
        search_invoice = st.text_input("🔍 Rechercher une facture", placeholder="Ex: F2428...")
    
    if show_negatives:
        disp = disp[disp['Marge (€)'] < 0]
    if search_invoice:
        disp = disp[disp['Facture'].str.contains(search_invoice, case=False, na=False)]
    
    st.dataframe(disp, use_container_width=True, height=500)
    
    st.markdown("---")
    csv_export = invoices_unique.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 Exporter toutes les factures (CSV)", csv_export, 
                      f"factures_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv")


# ========== COMMANDES À RISQUE ==========
st.markdown("---")
st.subheader("⚠️ Commandes avec marge négative")

commandes_negatives = invoices_unique[invoices_unique['marge_nette'] < 0].copy()
if not commandes_negatives.empty:
    st.warning(f"🔴 {len(commandes_negatives)} commandes ont une marge négative (sur {nb_factures} total)")
    
    ca_negatif = commandes_negatives['ca_produits'].sum()
    gls_negatif = commandes_negatives['frais_gls'].sum()
    
    col_neg1, col_neg2, col_neg3 = st.columns(3)
    col_neg1.metric("CA des commandes négatives", f"{ca_negatif:,.2f} €", 
                   delta=f"{ca_negatif/total_ca*100:.1f}% du CA total")
    col_neg2.metric("Frais GLS associés", f"{gls_negatif:,.2f} €")
    col_neg3.metric("Perte totale", f"{commandes_negatives['marge_nette'].sum():,.2f} €")
    
    st.dataframe(commandes_negatives[['invoice_number', 'customer_name', 'ca_produits', 
                                      'cogs_total', 'frais_gls', 'marge_nette', 'taux_marge']]
                 .head(20).rename(columns={
                     'invoice_number': 'Facture',
                     'customer_name': 'Client',
                     'ca_produits': 'CA (€)',
                     'cogs_total': 'COGS (€)',
                     'frais_gls': 'GLS (€)',
                     'marge_nette': 'Marge (€)',
                     'taux_marge': 'Taux (%)'
                 }), use_container_width=True)
else:
    st.success("✅ Toutes les commandes ont une marge positive")


# ========== RÉSUMÉ DE LA PÉRIODE ==========
with st.expander("📊 Résumé de la période"):
    col_sum1, col_sum2, col_sum3 = st.columns(3)
    
    with col_sum1:
        st.metric("📅 Période", f"{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}")
        st.metric("📄 Factures", f"{nb_factures}")
        st.metric("👥 Clients actifs", f"{nb_clients}")
    
    with col_sum2:
        st.metric("💰 CA moyen par facture", f"{total_ca/nb_factures:.2f} €" if nb_factures > 0 else "0 €")
        st.metric("📦 Produits moyen par facture", f"{nb_produits_total/nb_factures:.1f}" if nb_factures > 0 else "0")
        st.metric("🚚 GLS moyen par facture", f"{total_gls/nb_factures:.2f} €" if nb_factures > 0 else "0 €")
    
    with col_sum3:
        st.metric("💰 Marge moyenne par facture", f"{total_marge/nb_factures:.2f} €" if nb_factures > 0 else "0 €")
        st.metric("📈 Taux de marge moyen", f"{taux_marge_moyen:.1f}%")
        st.metric("📊 Ratio GLS/CA", f"{part_gls:.1f}%")


# ========== FOOTER ==========
st.markdown("---")
st.caption(f"📊 Dernière mise à jour: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.caption(f"📅 Période analysée: {start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}")