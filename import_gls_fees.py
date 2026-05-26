# import_gls_fees.py
"""
Script pour importer les frais GLS depuis un fichier CSV
Format attendu: commande_id, reference_client, total_facture
"""

import pandas as pd
import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def create_gls_fees_table():
    """Crée la table pour stocker les frais GLS"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gls_fees (
            id SERIAL PRIMARY KEY,
            commande_id VARCHAR(100),
            reference_client VARCHAR(100),
            total_facture DECIMAL(10,2),
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Table gls_fees créée")

def import_gls_fees_from_csv(csv_path):
    """Importe les frais GLS depuis un CSV"""
    
    try:
        df = pd.read_csv(csv_path)
        print(f"📁 {len(df)} lignes chargées")
        print(f"   Colonnes: {list(df.columns)}")
        
        # Normaliser les noms
        df.columns = [col.lower().strip() for col in df.columns]
        
        # Identifier les colonnes
        col_map = {}
        for expected in ['commande_id', 'reference_client', 'total_facture']:
            for col in df.columns:
                if expected in col or col in expected:
                    col_map[expected] = col
                    break
        
        if len(col_map) < 3:
            print(f"⚠️ Colonnes détectées: {col_map}")
            print("   Format attendu: commande_id, reference_client, total_facture")
            return 0
        
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        
        count = 0
        for _, row in df.iterrows():
            try:
                cursor.execute("""
                    INSERT INTO gls_fees (commande_id, reference_client, total_facture)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (commande_id) DO UPDATE SET
                        reference_client = EXCLUDED.reference_client,
                        total_facture = EXCLUDED.total_facture
                """, (
                    str(row[col_map['commande_id']]),
                    str(row[col_map['reference_client']]),
                    float(row[col_map['total_facture']])
                ))
                count += 1
            except Exception as e:
                print(f"⚠️ Erreur ligne {_}: {e}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ {count} lignes importées dans gls_fees")
        return count
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return 0

def update_delivery_notes_from_gls_fees():
    """Met à jour les BL avec les frais GLS depuis la table gls_fees"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Mise à jour par numéro de suivi
    cursor.execute("""
        UPDATE delivery_notes dn
        SET gls_shipping_cost = gf.total_facture,
            gls_reference_client = gf.reference_client,
            gls_checked_at = CURRENT_TIMESTAMP
        FROM gls_fees gf
        WHERE dn.tracking_number = gf.commande_id
        AND (dn.gls_shipping_cost IS NULL OR dn.gls_shipping_cost = 0)
    """)
    
    updated = cursor.rowcount
    print(f"✅ {updated} BL mis à jour via numéro de suivi")
    
    # Mise à jour par référence client
    cursor.execute("""
        UPDATE delivery_notes dn
        SET gls_shipping_cost = gf.total_facture,
            gls_reference_client = gf.reference_client,
            gls_checked_at = CURRENT_TIMESTAMP
        FROM gls_fees gf
        WHERE dn.tracking_number = gf.reference_client
        AND (dn.gls_shipping_cost IS NULL OR dn.gls_shipping_cost = 0)
    """)
    
    updated2 = cursor.rowcount
    print(f"✅ {updated2} BL mis à jour via référence client")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return updated + updated2

if __name__ == "__main__":
    import sys
    
    create_gls_fees_table()
    
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
        import_gls_fees_from_csv(csv_file)
        update_delivery_notes_from_gls_fees()
    else:
        print("Usage: python import_gls_fees.py <chemin_fichier_csv>")
        print("Exemple: python import_gls_fees.py data/frais_gls.csv")