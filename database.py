import psycopg2
import pandas as pd
from sqlalchemy import create_engine
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def get_connection():
    """Retourne une connexion PostgreSQL brute (psycopg2)."""
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def get_engine():
    """Retourne un moteur SQLAlchemy pour pandas.to_sql."""
    return create_engine(f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}')

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Table ventes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ventes (
        commande_id TEXT,
        produit TEXT,
        quantite INTEGER,
        prix_ht REAL,
        cout_livraison_fournisseur REAL,
        pays TEXT,
        date TEXT,
        PRIMARY KEY (commande_id, produit)
    )
    """)
    
    # Table frais_amazon
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS frais_amazon (
        commande_id TEXT PRIMARY KEY,
        commissions REAL,
        autres_frais REAL,
        total_frais REAL
    )
    """)
    
    # Table frais_gls
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS frais_gls (
        commande_id TEXT,
        reference_client TEXT,
        total_facture REAL,
        PRIMARY KEY (commande_id, reference_client)
    )
    """)
    
    # Table marges_calculees
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS marges_calculees (
        commande_id TEXT,
        produit TEXT,
        quantite INTEGER,
        ca_unitaire_ht REAL,
        ca_unitaire_avec_transport_fourn REAL,
        cogs_unitaire REAL,
        marge_brute_unitaire REAL,
        transport_gls_unitaire REAL,
        frais_amazon_unitaire REAL,
        marge_nette_unitaire REAL,
        date TEXT,
        pays TEXT,
        PRIMARY KEY (commande_id, produit)
    )
    """)
    
    conn.commit()
    conn.close()
    print("✅ Tables PostgreSQL créées avec succès.")

def insert_ventes(df):
    """Insère ou remplace la table ventes."""
    engine = get_engine()
    df.to_sql("ventes", engine, if_exists="replace", index=False)
    print("✅ Données insérées dans la table 'ventes'.")

def insert_frais_amazon(df):
    engine = get_engine()
    df.to_sql("frais_amazon", engine, if_exists="replace", index=False)
    print("✅ Données insérées dans la table 'frais_amazon'.")

def insert_frais_gls(df):
    engine = get_engine()
    df.to_sql("frais_gls", engine, if_exists="replace", index=False)
    print("✅ Données insérées dans la table 'frais_gls'.")