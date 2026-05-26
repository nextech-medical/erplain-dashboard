# import_all_to_postgres.py - Version corrigée
import json
import psycopg2
from datetime import datetime
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def get_table_columns(table_name):
    """Récupère la liste des colonnes d'une table dans l'ordre"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    columns = [row[0] for row in cursor.fetchall()]
    
    cursor.close()
    conn.close()
    return columns

def add_missing_columns():
    """Ajoute les colonnes manquantes si nécessaire"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Vérifier et ajouter la colonne discount à invoice_lines
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'invoice_lines' AND column_name = 'discount'
    """)
    
    if not cursor.fetchone():
        print("🔧 Ajout de la colonne 'discount' à invoice_lines...")
        cursor.execute("ALTER TABLE invoice_lines ADD COLUMN discount DECIMAL(10,2) DEFAULT 0")
        print("✅ Colonne 'discount' ajoutée")
    
    conn.commit()
    cursor.close()
    conn.close()

def parse_date(date_str):
    """Convertit une chaîne de date en format PostgreSQL"""
    if not date_str:
        return None
    
    try:
        # Supprimer le fuseau horaire et ne garder que la date/heure
        if '+' in date_str:
            date_str = date_str.split('+')[0]
        if 'T' in date_str:
            # Format avec heure
            return datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S')
        else:
            # Format date seule
            return datetime.strptime(date_str, '%Y-%m-%d')
    except:
        try:
            return datetime.strptime(str(date_str), '%Y-%m-%d')
        except:
            return None

def import_invoices():
    """Importe les factures et leurs lignes depuis factures.json"""
    
    # Ajouter les colonnes manquantes
    add_missing_columns()
    
    # Récupérer les colonnes existantes
    invoices_columns = get_table_columns('invoices')
    lines_columns = get_table_columns('invoice_lines')
    
    print(f"📋 Colonnes invoices: {invoices_columns}")
    print(f"📋 Colonnes invoice_lines: {lines_columns}")
    
    # Charger les factures
    try:
        with open("factures_depuis_2026.json", "r", encoding="utf-8") as f:
            invoices = json.load(f)
        print(f"📁 {len(invoices)} factures chargées")
    except FileNotFoundError:
        print("❌ Fichier factures.json non trouvé")
        return 0, 0
    
    inserted_invoices = 0
    inserted_lines = 0
    error_count = 0
    
    # Connexion pour l'import
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Définir l'ordre des colonnes pour l'insertion
    invoice_column_order = ['id', 'order_number', 'invoice_created', 'due_date', 
                           'subtotal', 'total', 'label', 'status', 
                           'reference_externe', 'notes']
    
    for idx, inv in enumerate(invoices):
        if not isinstance(inv, dict):
            continue
        
        try:
            # Nettoyer les données
            invoice_id = str(inv.get("id"))
            order_number = inv.get("order_number")
            
            # Convertir les dates correctement
            invoice_created = parse_date(inv.get("created"))
            due_date = parse_date(inv.get("due_date"))
            
            subtotal = float(inv.get("subtotal", 0)) if inv.get("subtotal") else 0
            total = float(inv.get("total", 0)) if inv.get("total") else 0
            label = inv.get("label")
            status = inv.get("status")
            reference_externe = inv.get("external_reference")
            notes = inv.get("notes")
            
            # Préparer les valeurs dans l'ordre défini
            invoice_values = []
            for col in invoice_column_order:
                if col in invoices_columns:
                    if col == 'id':
                        invoice_values.append(invoice_id)
                    elif col == 'order_number':
                        invoice_values.append(order_number)
                    elif col == 'invoice_created':
                        invoice_values.append(invoice_created)
                    elif col == 'due_date':
                        invoice_values.append(due_date)
                    elif col == 'subtotal':
                        invoice_values.append(subtotal)
                    elif col == 'total':
                        invoice_values.append(total)
                    elif col == 'label':
                        invoice_values.append(label)
                    elif col == 'status':
                        invoice_values.append(status)
                    elif col == 'reference_externe':
                        invoice_values.append(reference_externe)
                    elif col == 'notes':
                        invoice_values.append(notes)
            
            # Filtrer les colonnes qui existent réellement
            existing_columns = [col for col in invoice_column_order if col in invoices_columns]
            
            if existing_columns:
                columns_str = ','.join(existing_columns)
                placeholders_str = ','.join(['%s'] * len(invoice_values))
                
                query = f"""
                    INSERT INTO invoices ({columns_str})
                    VALUES ({placeholders_str})
                    ON CONFLICT (id) DO NOTHING
                """
                
                cursor.execute(query, invoice_values)
                
                if cursor.rowcount > 0:
                    inserted_invoices += 1
            
            # ========== LIGNES DE FACTURE ==========
            line_items_data = inv.get("line_items", {})
            edges = line_items_data.get("edges", {})
            
            # Extraire les nodes
            nodes = []
            if isinstance(edges, dict):
                node_data = edges.get("node")
                if isinstance(node_data, list):
                    nodes = node_data
                elif node_data:
                    nodes = [node_data]
            elif isinstance(edges, list):
                for edge in edges:
                    if isinstance(edge, dict):
                        node = edge.get("node")
                        if node:
                            nodes.append(node)
            
            # Définir l'ordre des colonnes pour invoice_lines
            line_column_order = ['invoice_id', 'product_label', 'product_sku', 
                                 'quantity', 'unit_price', 'line_total', 'discount']
            
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                
                product = node.get("product", {})
                
                # Nettoyer les données des lignes
                product_label = product.get("label")
                product_sku = product.get("sku")
                
                quantity = node.get("quantity")
                if quantity is not None:
                    try:
                        quantity = int(float(quantity))
                    except:
                        quantity = 0
                else:
                    quantity = 0
                
                unit_price = node.get("price")
                if unit_price is not None:
                    try:
                        unit_price = float(unit_price)
                    except:
                        unit_price = 0
                else:
                    unit_price = 0
                
                line_total = node.get("total")
                if line_total is not None:
                    try:
                        line_total = float(line_total)
                    except:
                        line_total = 0
                else:
                    line_total = 0
                
                discount = node.get("discount", 0)
                if discount is not None:
                    try:
                        discount = float(discount)
                    except:
                        discount = 0
                
                # Préparer les valeurs dans l'ordre
                line_values = []
                for col in line_column_order:
                    if col in lines_columns:
                        if col == 'invoice_id':
                            line_values.append(invoice_id)
                        elif col == 'product_label':
                            line_values.append(product_label)
                        elif col == 'product_sku':
                            line_values.append(product_sku)
                        elif col == 'quantity':
                            line_values.append(quantity)
                        elif col == 'unit_price':
                            line_values.append(unit_price)
                        elif col == 'line_total':
                            line_values.append(line_total)
                        elif col == 'discount':
                            line_values.append(discount)
                
                # Filtrer les colonnes qui existent
                existing_line_cols = [col for col in line_column_order if col in lines_columns]
                
                if existing_line_cols:
                    columns_str = ','.join(existing_line_cols)
                    placeholders_str = ','.join(['%s'] * len(line_values))
                    
                    query = f"""
                        INSERT INTO invoice_lines ({columns_str})
                        VALUES ({placeholders_str})
                    """
                    
                    cursor.execute(query, line_values)
                    inserted_lines += 1
            
            # Commit toutes les 100 factures
            if inserted_invoices % 100 == 0 and inserted_invoices > 0:
                conn.commit()
                print(f"   {inserted_invoices} factures importées, {inserted_lines} lignes...")
                
        except psycopg2.Error as e:
            error_count += 1
            if error_count <= 10:
                print(f"❌ Erreur facture {inv.get('order_number', 'inconnue')}: {e}")
            conn.rollback()
            continue
            
        except Exception as e:
            error_count += 1
            if error_count <= 10:
                print(f"❌ Erreur générale {inv.get('order_number', 'inconnue')}: {e}")
            conn.rollback()
            continue
    
    # Commit final
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\n   {inserted_invoices} factures importées, {inserted_lines} lignes...")
    print(f"\n✅ Import terminé:")
    print(f"   - Factures: {inserted_invoices}")
    print(f"   - Lignes: {inserted_lines}")
    print(f"   - Erreurs: {error_count}")
    return inserted_invoices, inserted_lines

def show_final_stats():
    """Affiche les statistiques finales"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM invoices")
    nb_inv = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM invoice_lines")
    nb_lines = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT product_label) FROM invoice_lines WHERE product_label IS NOT NULL")
    nb_products = cursor.fetchone()[0]
    
    cursor.execute("SELECT COALESCE(SUM(total), 0) FROM invoices")
    total_ca = cursor.fetchone()[0] or 0
    
    print("\n" + "=" * 50)
    print("📊 STATISTIQUES FINALES")
    print("=" * 50)
    print(f"   📄 Factures: {nb_inv}")
    print(f"   📋 Lignes: {nb_lines}")
    print(f"   🏷️ Produits distincts: {nb_products}")
    print(f"   💰 CA total: {total_ca:,.2f} €")
    print("=" * 50)
    
    cursor.close()
    conn.close()

def verify_json_structure():
    """Vérifie la structure du fichier JSON"""
    try:
        with open("factures_depuis_2026.json", "r", encoding="utf-8") as f:
            invoices = json.load(f)
        
        if not invoices:
            print("❌ Fichier JSON vide")
            return False
        
        print(f"📁 {len(invoices)} factures dans le fichier")
        
        # Analyser les premières factures
        print("\n🔍 Structure des premières factures:")
        for i, inv in enumerate(invoices[:3]):
            print(f"\n   Facture {i+1}: {inv.get('order_number')}")
            print(f"      - id: {inv.get('id')}")
            print(f"      - created: {inv.get('created')}")
            print(f"      - total: {inv.get('total')}")
            
            # Compter les lignes
            line_items = inv.get("line_items", {})
            edges = line_items.get("edges", {})
            nodes = edges.get("node", [])
            if isinstance(nodes, dict):
                nodes = [nodes] if nodes else []
            print(f"      - Lignes: {len(nodes)}")
        
        return True
        
    except FileNotFoundError:
        print("❌ Fichier factures.json non trouvé")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ Erreur de décodage JSON: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("📥 IMPORT DES FACTURES")
    print("=" * 50)
    print()
    
    # Vérifier le fichier JSON
    if not verify_json_structure():
        exit(1)
    
    # Demander confirmation
    print("\n⚠️ Attention: Cela va ajouter les factures à la base existante")
    confirmation = input("Voulez-vous continuer? (o/n): ")
    
    if confirmation.lower() != 'o':
        print("Import annulé")
        exit(0)
    
    print()
    
    # Importer les factures
    import_invoices()
    
    # Afficher les stats
    show_final_stats()