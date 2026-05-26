# import_all_data.py - Script complet pour importer toutes les données
import json
import psycopg2
import re
import pandas as pd
from datetime import datetime
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def init_database():
    """Initialise la base de données avec toutes les tables nécessaires"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Table invoices
    cursor.execute("""
        DROP TABLE IF EXISTS invoice_lines CASCADE
    """)
    cursor.execute("""
        DROP TABLE IF EXISTS invoices CASCADE
    """)
    
    cursor.execute("""
        CREATE TABLE invoices (
            id VARCHAR(50) PRIMARY KEY,
            order_number VARCHAR(100),
            label VARCHAR(200),
            status VARCHAR(50),
            invoice_created DATE,
            due_date DATE,
            subtotal DECIMAL(10,2),
            total DECIMAL(10,2),
            tax_amount DECIMAL(10,2),
            customer_name TEXT,
            customer_email TEXT,
            reference_externe TEXT,
            bl_number TEXT,
            notes_text TEXT,
            fournisseur TEXT,
            gestionnaire TEXT,
            shipping_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Table invoice_lines
    cursor.execute("""
        CREATE TABLE invoice_lines (
            id SERIAL PRIMARY KEY,
            invoice_id VARCHAR(50) REFERENCES invoices(id) ON DELETE CASCADE,
            product_label TEXT,
            product_sku TEXT,
            quantity INTEGER,
            unit_price DECIMAL(10,2),
            discount DECIMAL(10,2),
            line_total DECIMAL(10,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Table parametres
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parametres (
            id SERIAL PRIMARY KEY,
            type_transport TEXT,
            tarif_unitaire DECIMAL(10,2),
            cout_fixe DECIMAL(10,2),
            date_maj TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Table suppliers (si elle n'existe pas)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255),
            phone VARCHAR(50),
            address TEXT,
            city VARCHAR(100),
            country VARCHAR(100),
            vat_number VARCHAR(50),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Table products
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            sku VARCHAR(100),
            supplier_id VARCHAR(50),
            supplier_name VARCHAR(255),
            brand VARCHAR(255),
            description TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Base de données initialisée")

def parse_date(date_str):
    """Convertit une chaîne de date en format date"""
    if not date_str:
        return None
    try:
        if 'T' in date_str:
            date_str = date_str.split('T')[0]
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        return None

def extract_reference_from_notes(notes):
    """Extrait la référence externe des notes HTML"""
    if not notes:
        return None
    
    clean_notes = re.sub(r'<[^>]+>', ' ', notes)
    clean_notes = re.sub(r'&[a-z]+;', ' ', clean_notes)
    
    patterns = [
        r'Commande\s*[Nn]°?\s*[:\s]*([A-Z0-9\-/]+)',
        r'N°\s*d\'engagement\s*:\s*([A-Z0-9]+)',
        r'bon de commande\s*[Nn]°?\s*[:\s]*([A-Z0-9\-/]+)',
        r'Référence\s*[:\s]*([A-Z0-9\-]+)',
        r'PO[-\s]*([A-Z0-9]+)',
        r'E(\d{6})',
        r'BC[-\s]*([A-Z0-9]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, clean_notes, re.IGNORECASE)
        if match:
            return match.group(1)
    return None

def detect_platform(order_number, reference):
    """Détecte la plateforme"""
    if reference:
        if reference.startswith('PO-') or (reference.startswith('E') and len(reference) >= 6):
            return 'Temu'
        elif reference.startswith('40') or '-' in reference:
            return 'Amazon'
        elif 'SHOP' in reference.upper():
            return 'Shopify'
    if order_number:
        if order_number.startswith('PO-'):
            return 'Temu'
        elif order_number.startswith('40'):
            return 'Amazon'
        elif 'SHOP' in order_number.upper():
            return 'Shopify'
    return 'Direct'

def detect_supplier(product_label):
    """Détecte le fournisseur à partir du produit"""
    if not product_label:
        return None
    
    mapping = {
        'ZARYS': 'ZARYS',
        'Abena': 'Abena',
        'Ontex': 'Ontex',
        'HARTMANN': 'Hartmann',
        'Chirana': 'Chirana',
        'BASTOS': 'Bastos',
        'Comed': 'Comed',
        'Tena': 'Tena',
        'SIDAPHARM': 'Sidapharm',
        'PHARMAPLAST': 'Pharmaplast',
        'VITREX': 'Vitrex',
        'BD': 'BD Medical',
        'FL MEDICAL': 'FL Medical',
    }
    
    for marque, fournisseur in mapping.items():
        if marque in product_label.upper():
            return fournisseur
    return None

def import_invoices(json_file="factures_depuis_2026.json"):
    """Importe les factures depuis le fichier JSON"""
    
    # Initialiser la base
    init_database()
    
    # Charger les factures
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            invoices = json.load(f)
        print(f"📁 {len(invoices)} factures chargées")
    except FileNotFoundError:
        print(f"❌ Fichier {json_file} non trouvé")
        return 0, 0
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    inserted = 0
    lines_inserted = 0
    
    for idx, inv in enumerate(invoices):
        try:
            invoice_id = str(inv.get('id'))
            order_number = inv.get('order_number')
            label = inv.get('label')
            created = parse_date(inv.get('created'))
            due_date = parse_date(inv.get('due_date'))
            subtotal = inv.get('subtotal', 0) or 0
            total = inv.get('total', 0) or 0
            shipping_tax = inv.get('shipping_tax_amount')
            
            # Extraire les notes
            notes = inv.get('notes')
            reference_externe = extract_reference_from_notes(notes)
            
            # Informations client
            customer = inv.get('customer', {})
            customer_name = customer.get('label') if isinstance(customer, dict) else None
            customer_emails = customer.get('emails', []) if isinstance(customer, dict) else []
            customer_email = customer_emails[0] if customer_emails else None
            
            # Détecter la plateforme
            gestionnaire = detect_platform(order_number, reference_externe)
            
            # Insérer la facture
            cursor.execute("""
                INSERT INTO invoices (
                    id, order_number, label, invoice_created, due_date,
                    subtotal, total, tax_amount, customer_name, customer_email,
                    reference_externe, notes_text, gestionnaire
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    order_number = EXCLUDED.order_number,
                    total = EXCLUDED.total,
                    customer_name = EXCLUDED.customer_name,
                    gestionnaire = COALESCE(invoices.gestionnaire, EXCLUDED.gestionnaire)
            """, (
                invoice_id, order_number, label, created, due_date,
                subtotal, total, shipping_tax, customer_name, customer_email,
                reference_externe, notes, gestionnaire
            ))
            inserted += 1
            
            # Insérer les lignes de facture
            line_items = inv.get('line_items', {})
            edges = line_items.get('edges', {})
            nodes = edges.get('node', [])
            
            if not isinstance(nodes, list):
                nodes = [nodes] if nodes else []
            
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                
                product = node.get('product', {})
                quantity = node.get('quantity', 0)
                price = node.get('price', 0)
                discount = node.get('discount', 0)
                line_total = node.get('total', 0)
                
                # Convertir les valeurs
                try:
                    quantity = int(quantity) if quantity else 0
                    price = float(price) if price else 0
                    discount = float(discount) if discount else 0
                    line_total = float(line_total) if line_total else 0
                except (ValueError, TypeError):
                    pass
                
                product_label = product.get('label')
                product_sku = product.get('sku')
                
                # Détecter le fournisseur
                fournisseur = detect_supplier(product_label)
                
                cursor.execute("""
                    INSERT INTO invoice_lines (
                        invoice_id, product_label, product_sku, quantity,
                        unit_price, discount, line_total
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    invoice_id, product_label, product_sku,
                    quantity, price, discount, line_total
                ))
                lines_inserted += 1
                
                # Mettre à jour le fournisseur de la facture
                if fournisseur:
                    cursor.execute("""
                        UPDATE invoices 
                        SET fournisseur = %s 
                        WHERE id = %s AND (fournisseur IS NULL OR fournisseur = 'Non spécifié')
                    """, (fournisseur, invoice_id))
            
            # Commit toutes les 50 factures
            if (idx + 1) % 50 == 0:
                conn.commit()
                print(f"   {inserted} factures importées, {lines_inserted} lignes...")
                
        except Exception as e:
            print(f"❌ Erreur facture {inv.get('order_number', 'inconnue')}: {str(e)[:100]}")
            conn.rollback()
            continue
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\n✅ {inserted} factures importées")
    print(f"✅ {lines_inserted} lignes importées")
    
    return inserted, lines_inserted

def import_bons_de_livraison(json_file="bl_erplain.json"):
    """Importe les bons de livraison"""
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            bl_list = json.load(f)
        print(f"\n📁 {len(bl_list)} bons de livraison chargés")
    except FileNotFoundError:
        print(f"⚠️ Fichier {json_file} non trouvé")
        return 0
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    updated = 0
    for bl in bl_list:
        try:
            order_number = bl.get('order_number')
            external_reference = bl.get('external_reference')
            shipping_date = parse_date(bl.get('shipping_date'))
            
            if order_number:
                cursor.execute("""
                    UPDATE invoices 
                    SET bl_number = %s,
                        reference_externe = COALESCE(reference_externe, %s),
                        shipping_date = %s
                    WHERE order_number = %s
                    AND (bl_number IS NULL OR bl_number = '')
                """, (order_number, external_reference, shipping_date, order_number))
                updated += cursor.rowcount
            
            conn.commit()
        except Exception as e:
            print(f"❌ Erreur BL {bl.get('order_number')}: {e}")
            conn.rollback()
            continue
    
    cursor.close()
    conn.close()
    
    print(f"✅ {updated} factures mises à jour avec les BL")
    return updated

def show_statistics():
    """Affiche les statistiques"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    # Compter les factures
    df = pd.read_sql_query("SELECT COUNT(*) as total FROM invoices", conn)
    total = df['total'].iloc[0]
    
    # Compter par plateforme
    df_platform = pd.read_sql_query("""
        SELECT gestionnaire, COUNT(*) as nb 
        FROM invoices 
        WHERE gestionnaire IS NOT NULL 
        GROUP BY gestionnaire
    """, conn)
    
    # Compter les références
    df_ref = pd.read_sql_query("""
        SELECT 
            COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as with_ref,
            COUNT(CASE WHEN bl_number IS NOT NULL AND bl_number != '' THEN 1 END) as with_bl,
            COUNT(CASE WHEN fournisseur IS NOT NULL AND fournisseur != 'Non spécifié' THEN 1 END) as with_fournisseur
        FROM invoices
    """, conn)
    
    conn.close()
    
    print("\n" + "="*60)
    print("📊 STATISTIQUES DE LA BASE")
    print("="*60)
    print(f"   📄 Total factures: {total}")
    if total > 0:
        print(f"   🏷️ Avec référence: {df_ref['with_ref'].iloc[0]} ({df_ref['with_ref'].iloc[0]*100//total}%)")
        print(f"   🚚 Avec BL: {df_ref['with_bl'].iloc[0]} ({df_ref['with_bl'].iloc[0]*100//total}%)")
        print(f"   🏭 Avec fournisseur: {df_ref['with_fournisseur'].iloc[0]} ({df_ref['with_fournisseur'].iloc[0]*100//total}%)")
    
    if not df_platform.empty:
        print("\n📱 Répartition par plateforme:")
        for _, row in df_platform.iterrows():
            print(f"   - {row['gestionnaire']}: {row['nb']} factures")
    
    print("="*60)

def import_parametres_defaut():
    """Importe les paramètres par défaut"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM parametres")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO parametres (type_transport, tarif_unitaire, cout_fixe)
            VALUES ('quantite', 0.50, 2.00)
        """)
        conn.commit()
        print("✅ Paramètres par défaut ajoutés")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔄 IMPORT COMPLET DES DONNÉES")
    print("="*60)
    
    # 1. Importer les factures
    invoice_count, line_count = import_invoices()
    
    if invoice_count > 0:
        # 2. Importer les BL
        bl_count = import_bons_de_livraison()
        
        # 3. Importer les paramètres
        import_parametres_defaut()
        
        # 4. Afficher les statistiques
        show_statistics()
        
        print("\n✅ Import terminé! Vous pouvez maintenant lancer le dashboard:")
        print("   streamlit run dashboard_avance.py")
    else:
        print("\n❌ Aucune facture importée")
        print("   Vérifiez que le fichier 'factures_depuis_2026.json' existe")