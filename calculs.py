import pandas as pd
from database import get_connection, get_engine
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def calculer_marges():
    conn = get_connection()
    
    # 1. Agrégation des frais GLS
    df_gls = pd.read_sql_query("""
        SELECT commande_id, SUM(total_facture) AS transport_gls_total
        FROM frais_gls
        GROUP BY commande_id
    """, conn)
    
    # 2. Jointure principale
    query = """
    SELECT
        v.commande_id,
        v.date,
        v.produit,
        v.quantite,
        v.prix_ht,
        v.cout_livraison_fournisseur,
        v.pays,
        COALESCE(f.commissions, 0) AS commissions_amazon,
        COALESCE(g.transport_gls_total, 0) AS transport_gls_total
    FROM ventes v
    LEFT JOIN frais_amazon f ON v.commande_id = f.commande_id
    LEFT JOIN (
        SELECT commande_id, SUM(total_facture) AS transport_gls_total
        FROM frais_gls
        GROUP BY commande_id
    ) g ON v.commande_id = g.commande_id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # 3. Récupération des coûts produits (simulation – à remplacer par vos vraies données)
    # Ici vous devez charger les coûts depuis votre table `couts_produits` ou depuis l'API.
    # Exemple fictif :
    produits = df['produit'].unique()
    couts = {p: 10.0 + (hash(p) % 50) / 10 for p in produits}
    df['cogs_unitaire'] = df['produit'].map(couts).fillna(0)
    
    # 4. Calculs des marges
    df['ca_unitaire_ht'] = df['prix_ht'] / df['quantite']
    df['ca_unitaire_avec_transport_fourn'] = (df['prix_ht'] + df['cout_livraison_fournisseur']) / df['quantite']
    df['marge_brute_unitaire'] = df['ca_unitaire_avec_transport_fourn'] - df['cogs_unitaire']
    df['transport_gls_unitaire'] = df['transport_gls_total'] / df['quantite']
    df['frais_amazon_unitaire'] = df['commissions_amazon'] / 1.2 / df['quantite']
    df['marge_nette_unitaire'] = df['marge_brute_unitaire'] - df['transport_gls_unitaire'] - df['frais_amazon_unitaire']
    
    # Arrondi
    cols_round = ['ca_unitaire_ht', 'ca_unitaire_avec_transport_fourn', 'cogs_unitaire',
                  'marge_brute_unitaire', 'transport_gls_unitaire', 'frais_amazon_unitaire',
                  'marge_nette_unitaire']
    df[cols_round] = df[cols_round].round(2)
    
    # 5. Sélection des colonnes finales
    df_result = df[[
        'commande_id', 'produit', 'quantite', 'ca_unitaire_ht', 'ca_unitaire_avec_transport_fourn',
        'cogs_unitaire', 'marge_brute_unitaire', 'transport_gls_unitaire', 'frais_amazon_unitaire',
        'marge_nette_unitaire', 'date', 'pays'
    ]]
    
    # 6. Sauvegarde dans la table marges_calculees
    engine = get_engine()
    df_result.to_sql("marges_calculees", engine, if_exists="replace", index=False)
    print("✅ Calculs des marges terminés et table 'marges_calculees' mise à jour.")

if __name__ == "__main__":
    calculer_marges()