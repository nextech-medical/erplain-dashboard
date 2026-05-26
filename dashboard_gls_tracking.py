# dashboard_gls_tracking.py
"""
Dashboard pour visualiser les numéros de suivi GLS
"""
import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

st.set_page_config(page_title="Suivi GLS", page_icon="📮", layout="wide")

@st.cache_data(ttl=300)
def load_tracking_data():
    """Charge les données de suivi GLS"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    query = """
        SELECT 
            order_number,
            tracking_number,
            external_reference,
            shipping_date,
            status,
            last_event,
            last_event_date,
            estimated_delivery,
            last_sync,
            CASE 
                WHEN status = 'delivered' THEN '✅ Livré'
                WHEN status = 'in_transit' THEN '🚚 En transit'
                WHEN status = 'not_found' THEN '❌ Non trouvé'
                WHEN status IS NULL OR status = '' THEN '⏳ En attente'
                ELSE '📦 ' || status
            END as status_label
        FROM gls_tracking
        ORDER BY shipping_date DESC, order_number DESC
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Conversion dates
    if 'shipping_date' in df.columns:
        df['shipping_date'] = pd.to_datetime(df['shipping_date'], errors='coerce')
    if 'last_event_date' in df.columns:
        df['last_event_date'] = pd.to_datetime(df['last_event_date'], errors='coerce')
    if 'last_sync' in df.columns:
        df['last_sync'] = pd.to_datetime(df['last_sync'], errors='coerce')
    
    return df

def main():
    st.title("📮 Suivi des colis GLS")
    st.markdown("---")
    
    # Chargement des données
    with st.spinner("Chargement des données..."):
        df = load_tracking_data()
    
    if df.empty:
        st.warning("⚠️ Aucun numéro de suivi GLS trouvé")
        st.info("Lancez d'abord: `python sync_gls_tracking.py`")
        return
    
    # KPIs
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("📦 Total colis", len(df))
    with col2:
        st.metric("✅ Livrés", len(df[df['status'] == 'delivered']))
    with col3:
        st.metric("🚚 En transit", len(df[df['status'] == 'in_transit']))
    with col4:
        st.metric("❌ Non trouvés", len(df[df['status'] == 'not_found']))
    with col5:
        st.metric("⏳ En attente", len(df[df['status'].isna()]))
    
    st.markdown("---")
    
    # Filtres
    col_filter1, col_filter2, col_filter3 = st.columns(3)
    
    with col_filter1:
        search = st.text_input("🔍 Rechercher (numéro BL ou tracking)", placeholder="Entrez un numéro...")
    
    with col_filter2:
        status_filter = st.multiselect(
            "Statut",
            options=['✅ Livré', '🚚 En transit', '❌ Non trouvé', '⏳ En attente'],
            default=[]
        )
    
    with col_filter3:
        date_range = st.date_input(
            "📅 Période d'expédition",
            value=[],
            key="shipping_date_filter"
        )
    
    # Application des filtres
    df_filtered = df.copy()
    
    if search:
        df_filtered = df_filtered[
            df_filtered['order_number'].astype(str).str.contains(search, case=False, na=False) |
            df_filtered['tracking_number'].astype(str).str.contains(search, case=False, na=False)
        ]
    
    if status_filter:
        df_filtered = df_filtered[df_filtered['status_label'].isin(status_filter)]
    
    if len(date_range) == 2:
        start_date, end_date = date_range
        df_filtered = df_filtered[
            (df_filtered['shipping_date'] >= pd.Timestamp(start_date)) &
            (df_filtered['shipping_date'] <= pd.Timestamp(end_date))
        ]
    
    # Tableau des résultats
    st.subheader(f"📋 Résultats ({len(df_filtered)} colis)")
    
    display_cols = ['order_number', 'tracking_number', 'status_label', 'shipping_date', 
                    'last_event', 'last_event_date', 'last_sync']
    
    if not df_filtered.empty:
        # Formatage
        display_df = df_filtered[display_cols].copy()
        display_df.columns = ['BL', 'Tracking GLS', 'Statut', 'Date expédition', 
                              'Dernier événement', 'Date événement', 'Dernière sync']
        
        # Formatage dates
        for col in ['Date expédition', 'Date événement', 'Dernière sync']:
            if col in display_df.columns:
                display_df[col] = pd.to_datetime(display_df[col]).dt.strftime('%d/%m/%Y %H:%M')
        
        st.dataframe(display_df, use_container_width=True, height=400)
        
        # Export CSV
        csv = display_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            "📥 Télécharger les données (CSV)",
            csv,
            f"gls_tracking_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "text/csv"
        )
    else:
        st.info("Aucun résultat pour ces filtres")
    
    # Graphiques
    st.markdown("---")
    st.subheader("📊 Statistiques")
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        if not df.empty:
            status_counts = df['status_label'].value_counts()
            st.bar_chart(status_counts)
    
    with col_chart2:
        if 'shipping_date' in df.columns and not df['shipping_date'].isna().all():
            df['mois'] = df['shipping_date'].dt.to_period('M').astype(str)
            monthly = df.groupby('mois').size()
            st.line_chart(monthly)
    
    # Footer
    st.markdown("---")
    st.caption(f"📊 Dernière mise à jour: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()