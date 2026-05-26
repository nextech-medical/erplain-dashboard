import pandas as pd
import os
from erplain_api import fetch_sales_orders_for_year, fetch_product_costs
from database import init_db, insert_ventes, insert_frais_amazon, insert_frais_gls
from calculs import calculer_marges
from config import FETCH_YEAR

# Chemins pour les fichiers CSV des frais (optionnels)
AMAZON_CSV = "data/frais_amazon.csv"
GLS_CSV = "data/frais_gls.csv"

def load_amazon_fees():
    if os.path.exists(AMAZON_CSV):
        df = pd.read_csv(AMAZON_CSV)
        # Normalisation des colonnes (à adapter selon votre fichier)
        if 'commande_id' in df.columns and 'commissions' in df.columns:
            df['autres_frais'] = df.get('autres_frais', 0)
            df['total_frais'] = df['commissions'] + df['autres_frais']
            return df[['commande_id', 'commissions', 'autres_frais', 'total_frais']]
    return pd.DataFrame(columns=['commande_id', 'commissions', 'autres_frais', 'total_frais'])

def load_gls_fees():
    if os.path.exists(GLS_CSV):
        df = pd.read_csv(GLS_CSV)
        if 'commande_id' in df.columns and 'total_facture' in df.columns:
            df['reference_client'] = df.get('reference_client', '')
            return df[['commande_id', 'reference_client', 'total_facture']]
    return pd.DataFrame(columns=['commande_id', 'reference_client', 'total_facture'])

def run_etl():
    print("📡 Récupération des commandes ERPlein...")
    df_ventes = fetch_sales_orders_for_year(year=FETCH_YEAR)
    if df_ventes.empty:
        print("Aucune commande récupérée. Arrêt.")
        return
    
    print("📡 Récupération des coûts produits...")
    product_costs = fetch_product_costs()
    df_ventes['couts'] = df_ventes['produit'].map(product_costs).fillna(0)
    # Le bénéfice brut sera recalculé dans calculs.py, on le laisse vide ici
    
    print("📂 Chargement des frais annexes...")
    df_amazon = load_amazon_fees()
    df_gls = load_gls_fees()
    
    print("🗄️ Initialisation de la base...")
    init_db()
    
    print("💾 Insertion des données...")
    insert_ventes(df_ventes)
    if not df_amazon.empty:
        insert_frais_amazon(df_amazon)
    if not df_gls.empty:
        insert_frais_gls(df_gls)
    
    print("🧮 Calcul des marges...")
    calculer_marges()
    
    print("✅ ETL terminé.")

if __name__ == "__main__":
    run_etl()