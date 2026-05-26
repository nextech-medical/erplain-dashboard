# sync_suppliers.py
import requests
import psycopg2
import pandas as pd
from datetime import datetime
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, ERPLAIN_API_KEY, ERPLAIN_DOMAIN

def fetch_suppliers_from_erplain():
    """
    Récupère les fournisseurs depuis l'API Erplain
    """
    if not ERPLAIN_API_KEY:
        print("⚠️ API key manquante. L'API Erplain n'est pas configurée.")
        print("💡 Pour activer l'API, contactez le support Erplain (module payant)")
        return []
    
    url = f"https://{ERPLAIN_DOMAIN}/graphql"
    
    headers = {
        "Authorization": f"Bearer {ERPLAIN_API_KEY}",
        "Content-Type": "application/json"
    }
    
    query = """
    query {
        suppliers {
            id
            name
            email
            phone
            address
            city
            postalCode
            country
            vatNumber
            status
            createdAt
            updatedAt
        }
    }
    """
    
    try:
        response = requests.post(url, json={"query": query}, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            suppliers = data.get("data", {}).get("suppliers", [])
            print(f"✅ {len(suppliers)} fournisseurs récupérés depuis Erplain")
            return suppliers
        else:
            print(f"❌ Erreur API: {response.status_code}")
            print(f"Message: {response.text}")
            return []
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur de connexion: {e}")
        return []

def create_suppliers_table():
    """
    Crée la table des fournisseurs si elle n'existe pas
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255),
            phone VARCHAR(50),
            address TEXT,
            city VARCHAR(100),
            postal_code VARCHAR(20),
            country VARCHAR(100),
            vat_number VARCHAR(50),
            status VARCHAR(50),
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Table 'suppliers' créée/vérifiée")

def save_suppliers_to_postgres(suppliers):
    """
    Sauvegarde les fournisseurs dans PostgreSQL
    """
    if not suppliers:
        print("⚠️ Aucun fournisseur à sauvegarder")
        return 0
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    count = 0
    for supplier in suppliers:
        try:
            cursor.execute("""
                INSERT INTO suppliers (id, name, email, phone, address, city, 
                                       postal_code, country, vat_number, status, 
                                       created_at, updated_at, synced_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    email = EXCLUDED.email,
                    phone = EXCLUDED.phone,
                    address = EXCLUDED.address,
                    city = EXCLUDED.city,
                    postal_code = EXCLUDED.postal_code,
                    country = EXCLUDED.country,
                    vat_number = EXCLUDED.vat_number,
                    status = EXCLUDED.status,
                    updated_at = EXCLUDED.updated_at,
                    synced_at = CURRENT_TIMESTAMP
            """, (
                supplier.get('id'),
                supplier.get('name'),
                supplier.get('email'),
                supplier.get('phone'),
                supplier.get('address'),
                supplier.get('city'),
                supplier.get('postalCode'),
                supplier.get('country'),
                supplier.get('vatNumber'),
                supplier.get('status'),
                supplier.get('createdAt'),
                supplier.get('updatedAt')
            ))
            count += 1
        except Exception as e:
            print(f"❌ Erreur pour le fournisseur {supplier.get('name')}: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    print(f"✅ {count} fournisseurs sauvegardés dans PostgreSQL")
    return count

def update_invoices_with_suppliers():
    """
    Met à jour les factures existantes avec les fournisseurs
    Associe les fournisseurs aux factures basées sur les produits
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Cette requête associe les fournisseurs aux factures via les produits
    # À adapter selon votre structure de données
    cursor.execute("""
        UPDATE invoices i
        SET fournisseur = s.name
        FROM invoice_lines il
        JOIN suppliers s ON s.name = il.product_supplier  -- À adapter
        WHERE i.id = il.invoice_id
        AND i.fournisseur IS NULL
    """)
    
    conn.commit()
    affected = cursor.rowcount
    cursor.close()
    conn.close()
    
    print(f"✅ {affected} factures mises à jour avec les fournisseurs")
    return affected

def sync_all():
    """
    Synchronisation complète
    """
    print("\n" + "="*50)
    print(f"🔄 SYNCHRONISATION - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)
    
    # 1. Créer la table
    create_suppliers_table()
    
    # 2. Récupérer les fournisseurs depuis Erplain
    suppliers = fetch_suppliers_from_erplain()
    
    if not suppliers:
        print("\n⚠️ Aucun fournisseur récupéré depuis l'API.")
        print("\n📌 Pour importer les fournisseurs manuellement via CSV:")
        print("   1. Exportez les fournisseurs depuis Erplain en CSV")
        print("   2. Utilisez la fonction import_suppliers_from_csv()")
        return 0
    
    # 3. Sauvegarder dans PostgreSQL
    count = save_suppliers_to_postgres(suppliers)
    
    # 4. Mettre à jour les factures existantes
    update_invoices_with_suppliers()
    
    print("\n" + "="*50)
    print(f"✅ Synchronisation terminée - {count} fournisseurs")
    print("="*50 + "\n")
    
    return count

def import_suppliers_from_csv(csv_path):
    """
    Alternative: Importe les fournisseurs depuis un fichier CSV exporté d'Erplain
    """
    try:
        df = pd.read_csv(csv_path)
        print(f"📄 Fichier CSV chargé: {len(df)} lignes")
        
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        
        # Créer la table si nécessaire
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS suppliers (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) UNIQUE,
                email VARCHAR(255),
                phone VARCHAR(50),
                address TEXT,
                city VARCHAR(100),
                country VARCHAR(100),
                synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        count = 0
        for _, row in df.iterrows():
            try:
                cursor.execute("""
                    INSERT INTO suppliers (name, email, phone, address, city, country)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (name) DO UPDATE SET
                        email = EXCLUDED.email,
                        phone = EXCLUDED.phone,
                        address = EXCLUDED.address,
                        city = EXCLUDED.city,
                        country = EXCLUDED.country,
                        synced_at = CURRENT_TIMESTAMP
                """, (
                    row.get('name') or row.get('Supplier Name'),
                    row.get('email') or row.get('Email'),
                    row.get('phone') or row.get('Phone'),
                    row.get('address') or row.get('Address'),
                    row.get('city') or row.get('City'),
                    row.get('country') or row.get('Country')
                ))
                count += 1
            except Exception as e:
                print(f"❌ Erreur ligne {_}: {e}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ {count} fournisseurs importés depuis CSV")
        return count
        
    except Exception as e:
        print(f"❌ Erreur lors de l'import CSV: {e}")
        return 0

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--csv":
        # Mode CSV
        csv_file = input("Chemin du fichier CSV: ") if len(sys.argv) < 3 else sys.argv[2]
        import_suppliers_from_csv(csv_file)
    else:
        # Mode API
        print("\n🤖 Synchronisation avec l'API Erplain")
        print("⚠️  Note: L'API Erplain nécessite un module payant")
        print("   Contactez le support Erplain pour l'activer\n")
        
        response = input("Continuer? (o/n): ")
        if response.lower() == 'o':
            sync_all()
        else:
            print("Synchronisation annulée")