# check_gls_shipping_costs.py
"""
Script pour vérifier les coûts de livraison GLS pour les BL liés aux factures
Associe les numéros de suivi des BL avec les frais GLS et met à jour les factures
"""

import psycopg2
import pandas as pd
import os
from datetime import datetime
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def load_gls_fees(csv_path="data/frais_gls.csv"):
    """
    Charge les frais GLS depuis le fichier CSV
    Format attendu: commande_id, reference_client, total_facture
    """
    if not os.path.exists(csv_path):
        print(f"❌ Fichier CSV non trouvé: {csv_path}")
        print("   Format attendu: commande_id, reference_client, total_facture")
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(csv_path)
        print(f"📁 Fichier GLS chargé: {len(df)} lignes")
        print(f"   Colonnes: {list(df.columns)}")
        
        # Normaliser les noms de colonnes
        df.columns = df.columns.str.lower()
        
        # Identifier les colonnes importantes
        expected_cols = ['commande_id', 'reference_client', 'total_facture']
        for col in expected_cols:
            if col not in df.columns:
                print(f"⚠️ Colonne '{col}' non trouvée dans le CSV")
        
        return df
        
    except Exception as e:
        print(f"❌ Erreur lecture CSV: {e}")
        return pd.DataFrame()

def add_gls_columns_to_db():
    """Ajoute les colonnes nécessaires pour les frais GLS"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Ajouter les colonnes
    columns = [
        ("gls_tracking_number", "TEXT"),
        ("gls_shipping_cost", "DECIMAL(10,2)"),
        ("gls_reference_client", "TEXT"),
        ("gls_checked_at", "TIMESTAMP"),
    ]
    
    for col_name, col_type in columns:
        try:
            cursor.execute(f"ALTER TABLE delivery_notes ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
            print(f"✅ Colonne '{col_name}' ajoutée à delivery_notes")
        except Exception as e:
            print(f"⚠️ {col_name}: {e}")
    
    # Ajouter les colonnes à invoices
    invoice_columns = [
        ("gls_shipping_cost", "DECIMAL(10,2)"),
        ("gls_tracking_number", "TEXT"),
        ("gls_checked_at", "TIMESTAMP"),
    ]
    
    for col_name, col_type in invoice_columns:
        try:
            cursor.execute(f"ALTER TABLE invoices ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
            print(f"✅ Colonne '{col_name}' ajoutée à invoices")
        except Exception as e:
            print(f"⚠️ {col_name}: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()

def get_delivery_notes_with_tracking():
    """Récupère les BL qui ont un numéro de suivi"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    query = """
        SELECT 
            id,
            order_number,
            tracking_number,
            shipping_date,
            status,
            gls_tracking_number,
            gls_shipping_cost,
            gls_checked_at
        FROM delivery_notes
        WHERE tracking_number IS NOT NULL 
        AND tracking_number != ''
        ORDER BY shipping_date DESC
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print(f"\n📦 BL avec numéro de suivi: {len(df)}")
    return df

def match_gls_fees(delivery_notes_df, gls_fees_df):
    """
    Associe les BL aux frais GLS par numéro de suivi ou référence client
    """
    if delivery_notes_df.empty:
        print("❌ Aucun BL avec numéro de suivi")
        return pd.DataFrame()
    
    if gls_fees_df.empty:
        print("❌ Aucune donnée GLS")
        return pd.DataFrame()
    
    matches = []
    
    # Normaliser les colonnes GLS
    gls_fees_df = gls_fees_df.copy()
    
    # Convertir en string pour la comparaison
    if 'reference_client' in gls_fees_df.columns:
        gls_fees_df['reference_client_str'] = gls_fees_df['reference_client'].astype(str)
    
    if 'commande_id' in gls_fees_df.columns:
        gls_fees_df['commande_id_str'] = gls_fees_df['commande_id'].astype(str)
    
    for idx, dn in delivery_notes_df.iterrows():
        tracking = str(dn['tracking_number']) if dn['tracking_number'] else ''
        order_number = str(dn['order_number']) if dn['order_number'] else ''
        
        # Chercher par numéro de suivi
        match = None
        
        # 1. Correspondance exacte par numéro de suivi (commande_id)
        if 'commande_id_str' in gls_fees_df.columns:
            exact_match = gls_fees_df[gls_fees_df['commande_id_str'] == tracking]
            if not exact_match.empty:
                match = exact_match.iloc[0]
        
        # 2. Correspondance par référence client (si similaire au numéro de suivi)
        if match is None and 'reference_client_str' in gls_fees_df.columns:
            ref_match = gls_fees_df[gls_fees_df['reference_client_str'] == tracking]
            if not ref_match.empty:
                match = ref_match.iloc[0]
        
        # 3. Correspondance partielle (si le numéro de suivi est contenu)
        if match is None and 'commande_id_str' in gls_fees_df.columns:
            partial = gls_fees_df[gls_fees_df['commande_id_str'].str.contains(tracking[-10:], na=False)]
            if not partial.empty:
                match = partial.iloc[0]
        
        # 4. Correspondance par numéro de commande
        if match is None and 'reference_client_str' in gls_fees_df.columns:
            order_match = gls_fees_df[gls_fees_df['reference_client_str'] == order_number]
            if not order_match.empty:
                match = order_match.iloc[0]
        
        if match is not None:
            shipping_cost = 0
            if 'total_facture' in match:
                try:
                    shipping_cost = float(match['total_facture'])
                except:
                    shipping_cost = 0
            
            matches.append({
                'delivery_note_id': dn['id'],
                'order_number': dn['order_number'],
                'tracking_number': tracking,
                'gls_reference_client': match.get('reference_client', ''),
                'gls_command_id': match.get('commande_id', ''),
                'gls_shipping_cost': shipping_cost,
                'match_type': 'tracking_number' if 'commande_id' in match else 'reference_client'
            })
    
    return pd.DataFrame(matches)

def update_database_with_gls_costs(matches_df):
    """Met à jour la base avec les frais GLS trouvés"""
    if matches_df.empty:
        print("❌ Aucune correspondance trouvée")
        return 0, 0
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Mettre à jour delivery_notes
    dn_updated = 0
    for _, match in matches_df.iterrows():
        try:
            cursor.execute("""
                UPDATE delivery_notes 
                SET gls_tracking_number = %s,
                    gls_shipping_cost = %s,
                    gls_reference_client = %s,
                    gls_checked_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                match['tracking_number'],
                match['gls_shipping_cost'],
                match['gls_reference_client'],
                match['delivery_note_id']
            ))
            dn_updated += cursor.rowcount
        except Exception as e:
            print(f"❌ Erreur mise à jour BL {match['delivery_note_id']}: {e}")
    
    # Mettre à jour invoices via la liaison
    cursor.execute("""
        UPDATE invoices i
        SET gls_shipping_cost = dn.gls_shipping_cost,
            gls_tracking_number = dn.tracking_number,
            gls_checked_at = CURRENT_TIMESTAMP
        FROM delivery_notes dn
        WHERE i.order_number = dn.order_number
        AND dn.gls_shipping_cost IS NOT NULL
        AND dn.gls_shipping_cost > 0
        AND (i.gls_shipping_cost IS NULL OR i.gls_shipping_cost = 0)
    """)
    
    inv_updated = cursor.rowcount
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return dn_updated, inv_updated

def show_gls_statistics():
    """Affiche les statistiques des coûts GLS"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    print("\n" + "="*60)
    print("📊 STATISTIQUES DES COÛTS GLS")
    print("="*60)
    
    # BL avec coût GLS
    query_bl = """
        SELECT 
            COUNT(*) as total_bl_avec_suivi,
            COUNT(CASE WHEN gls_shipping_cost IS NOT NULL THEN 1 END) as avec_cout_gls,
            COUNT(CASE WHEN gls_shipping_cost IS NULL AND tracking_number IS NOT NULL THEN 1 END) as sans_cout,
            ROUND(AVG(gls_shipping_cost)::numeric, 2) as cout_moyen,
            ROUND(SUM(gls_shipping_cost)::numeric, 2) as cout_total
        FROM delivery_notes
        WHERE tracking_number IS NOT NULL AND tracking_number != ''
    """
    
    df_bl = pd.read_sql_query(query_bl, conn)
    
    if not df_bl.empty:
        print(f"\n📦 Bons de livraison:")
        print(f"   - Total BL avec suivi: {df_bl['total_bl_avec_suivi'].iloc[0]}")
        print(f"   - Avec coût GLS trouvé: {df_bl['avec_cout_gls'].iloc[0]}")
        print(f"   - Sans coût GLS: {df_bl['sans_cout'].iloc[0]}")
        if df_bl['cout_moyen'].iloc[0]:
            print(f"   - Coût moyen: {df_bl['cout_moyen'].iloc[0]:.2f} €")
            print(f"   - Coût total: {df_bl['cout_total'].iloc[0]:.2f} €")
    
    # Factures avec coût GLS
    query_inv = """
        SELECT 
            COUNT(*) as total_factures,
            COUNT(CASE WHEN gls_shipping_cost IS NOT NULL AND gls_shipping_cost > 0 THEN 1 END) as avec_cout,
            ROUND(AVG(gls_shipping_cost)::numeric, 2) as cout_moyen,
            ROUND(SUM(gls_shipping_cost)::numeric, 2) as cout_total
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
    """
    
    df_inv = pd.read_sql_query(query_inv, conn)
    
    if not df_inv.empty:
        print(f"\n📄 Factures 2026:")
        print(f"   - Total factures: {df_inv['total_factures'].iloc[0]}")
        print(f"   - Avec coût GLS: {df_inv['avec_cout'].iloc[0]}")
        if df_inv['cout_moyen'].iloc[0]:
            print(f"   - Coût moyen: {df_inv['cout_moyen'].iloc[0]:.2f} €")
            print(f"   - Coût total GLS: {df_inv['cout_total'].iloc[0]:.2f} €")
    
    conn.close()

def show_detailed_matches():
    """Affiche les détails des correspondances trouvées"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    query = """
        SELECT 
            dn.order_number,
            dn.tracking_number,
            dn.gls_shipping_cost,
            dn.gls_reference_client,
            dn.shipping_date,
            i.total as invoice_total,
            i.customer_name
        FROM delivery_notes dn
        LEFT JOIN invoices i ON i.order_number = dn.order_number
        WHERE dn.gls_shipping_cost IS NOT NULL 
        AND dn.gls_shipping_cost > 0
        ORDER BY dn.shipping_date DESC
        LIMIT 20
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df.empty:
        print("\n📋 Détail des correspondances GLS (20 derniers):")
        print("="*80)
        for _, row in df.iterrows():
            print(f"   Commande: {row['order_number']}")
            print(f"     Suivi: {row['tracking_number']}")
            print(f"     Coût GLS: {row['gls_shipping_cost']:.2f} €")
            print(f"     Client: {row['customer_name'][:40] if row['customer_name'] else 'N/A'}")
            print(f"     Total facture: {row['invoice_total']:.2f} €" if row['invoice_total'] else "")
            print()

def show_unmatched_tracking():
    """Affiche les BL avec suivi mais sans coût GLS trouvé"""
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
            shipping_date,
            status
        FROM delivery_notes
        WHERE tracking_number IS NOT NULL 
        AND tracking_number != ''
        AND (gls_shipping_cost IS NULL OR gls_shipping_cost = 0)
        ORDER BY shipping_date DESC
        LIMIT 20
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df.empty:
        print("\n⚠️ BL avec suivi SANS coût GLS trouvé (20 derniers):")
        print("="*60)
        for _, row in df.iterrows():
            print(f"   {row['order_number']}: {row['tracking_number']} ({row['shipping_date']})")
    else:
        print("\n✅ Tous les BL avec suivi ont un coût GLS associé")

def sync_gls_costs(csv_path="data/frais_gls.csv"):
    """
    Fonction principale de synchronisation des coûts GLS
    """
    print("\n" + "="*60)
    print("🚚 VÉRIFICATION DES COÛTS DE LIVRAISON GLS")
    print("="*60)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. Ajouter les colonnes nécessaires
    print("\n🔧 Vérification de la structure...")
    add_gls_columns_to_db()
    
    # 2. Charger les frais GLS
    print("\n📂 Chargement des frais GLS...")
    gls_fees = load_gls_fees(csv_path)
    
    if gls_fees.empty:
        print("\n⚠️ Aucune donnée GLS trouvée.")
        print("\n📌 Pour importer les frais GLS:")
        print("   1. Assurez-vous que le fichier existe dans data/frais_gls.csv")
        print("   2. Format: commande_id, reference_client, total_facture")
        return
    
    # 3. Récupérer les BL avec suivi
    print("\n📦 Récupération des BL avec numéro de suivi...")
    delivery_notes = get_delivery_notes_with_tracking()
    
    if delivery_notes.empty:
        print("❌ Aucun BL avec numéro de suivi trouvé")
        return
    
    # 4. Associer les frais GLS
    print("\n🔗 Association des frais GLS...")
    matches = match_gls_fees(delivery_notes, gls_fees)
    print(f"   {len(matches)} correspondances trouvées")
    
    # 5. Mettre à jour la base
    print("\n💾 Mise à jour de la base...")
    dn_updated, inv_updated = update_database_with_gls_costs(matches)
    print(f"   ✅ {dn_updated} BL mis à jour")
    print(f"   ✅ {inv_updated} factures mises à jour")
    
    # 6. Afficher les statistiques
    show_gls_statistics()
    
    # 7. Afficher les détails
    show_detailed_matches()
    show_unmatched_tracking()
    
    print("\n" + "="*60)
    print(f"✅ Synchronisation GLS terminée")
    print("="*60)

def export_gls_report(output_file="rapport_frais_gls.xlsx"):
    """Exporte un rapport détaillé des frais GLS"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    query = """
        SELECT 
            dn.order_number,
            dn.tracking_number,
            dn.shipping_date,
            dn.gls_shipping_cost,
            dn.gls_reference_client,
            dn.status,
            i.total as invoice_total,
            i.customer_name,
            i.customer_email,
            i.gestionnaire
        FROM delivery_notes dn
        LEFT JOIN invoices i ON i.order_number = dn.order_number
        WHERE dn.tracking_number IS NOT NULL AND dn.tracking_number != ''
        ORDER BY dn.shipping_date DESC
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df.empty:
        # Renommer les colonnes
        df.columns = [
            'Numéro commande', 'Numéro de suivi', 'Date d\'expédition',
            'Coût GLS (€)', 'Référence client', 'Statut BL',
            'Total facture (€)', 'Client', 'Email client', 'Gestionnaire'
        ]
        
        # Ajouter une colonne de vérification
        df['Coût trouvé'] = df['Coût GLS (€)'].notna()
        df['Coût GLS (€)'] = df['Coût GLS (€)'].fillna(0)
        
        # Exporter
        df.to_excel(output_file, index=False)
        print(f"\n📊 Rapport exporté: {output_file}")
    else:
        print("❌ Aucune donnée à exporter")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--export":
            export_gls_report()
        elif sys.argv[1] == "--stats":
            show_gls_statistics()
        elif sys.argv[1] == "--unmatched":
            show_unmatched_tracking()
        else:
            print("Usage: python check_gls_shipping_costs.py [--export] [--stats] [--unmatched]")
    else:
        # Exécution normale avec chemin du CSV
        csv_file = "data/frais_gls.csv"
        if len(sys.argv) > 2:
            csv_file = sys.argv[2]
        sync_gls_costs(csv_file)