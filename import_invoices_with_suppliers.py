# import_invoices_with_suppliers.py
import json
import psycopg2
from datetime import datetime
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def get_product_supplier_mapping():
    """Récupère le mapping produit -> fournisseur depuis la table products"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Récupérer tous les produits avec leur fournisseur
    cursor.execute("""
        SELECT sku, supplier_name 
        FROM products 
        WHERE supplier_name IS NOT NULL AND supplier_name != ''
    """)
    
    mapping = {}
    for sku, supplier in cursor.fetchall():
        if sku:
            mapping[sku] = supplier
    
    cursor.close()
    conn.close()
    
    print(f"📋 {len(mapping)} produits avec fournisseur trouvés")
    return mapping

def get_platform_from_order(order_number, reference_externe):
    """Détermine la plateforme à partir du numéro de commande ou référence"""
    if reference_externe:
        if reference_externe.startswith('PO-') or reference_externe.startswith('E'):
            return 'Temu'
        elif reference_externe.startswith('40') or '-' in reference_externe:
            return 'Amazon'
        elif 'SHOP' in reference_externe.upper():
            return 'Shopify'
    
    if order_number:
        if order_number.startswith('PO-'):
            return 'Temu'
        elif order_number.startswith('40'):
            return 'Amazon'
        elif 'SHOP' in order_number.upper():
            return 'Shopify'
    
    return 'Direct'

def import_invoices_with_suppliers():
    """Importe les factures avec les fournisseurs depuis la table products"""
    
    # Récupérer le mapping produit -> fournisseur
    product_supplier_mapping = get_product_supplier_mapping()
    
    # Charger les factures
    try:
        with open("factures.json", "r", encoding="utf-8") as f:
            invoices = json.load(f)
        print(f"📁 {len(invoices)} factures chargées")
    except FileNotFoundError:
        print("❌ Fichier factures.json non trouvé")
        return 0, 0
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Vérifier les colonnes existantes
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'invoices'
    """)
    existing_cols = [row[0] for row in cursor.fetchall()]
    
    # Ajouter les colonnes si nécessaire
    if 'fournisseur' not in existing_cols:
        cursor.execute("ALTER TABLE invoices ADD COLUMN fournisseur TEXT")
    if 'gestionnaire' not in existing_cols:
        cursor.execute("ALTER TABLE invoices ADD COLUMN gestionnaire TEXT")
    if 'reference_externe' not in existing_cols:
        cursor.execute("ALTER TABLE invoices ADD COLUMN reference_externe TEXT")
    
    conn.commit()
    
    inserted_invoices = 0
    inserted_lines = 0
    updated_suppliers = 0
    
    for inv in invoices:
        if not isinstance(inv, dict):
            continue
        
        try:
            invoice_id = str(inv.get("id"))
            order_number = inv.get("order_number")
            reference_externe = inv.get("external_reference")
            invoice_created = inv.get("created")
            due_date = inv.get("due_date")
            subtotal = inv.get("subtotal")
            total = inv.get("total")
            status = inv.get("status")
            
            # Déterminer la plateforme automatiquement
            gestionnaire = get_platform_from_order(order_number, reference_externe)
            
            # Collecter les fournisseurs uniques pour cette facture
            suppliers_found = set()
            
            # Lignes de facture
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
            
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                
                product = node.get("product", {})
                product_sku = product.get("sku")
                product_label = product.get("label")
                quantity = node.get("quantity", 0)
                unit_price = node.get("price", 0)
                line_total = node.get("total", 0)
                
                # Trouver le fournisseur à partir du SKU
                fournisseur = product_supplier_mapping.get(product_sku)
                if fournisseur:
                    suppliers_found.add(fournisseur)
                
                # Insérer la ligne
                cursor.execute("""
                    INSERT INTO invoice_lines (invoice_id, product_label, product_sku, 
                                              quantity, unit_price, line_total)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (invoice_id, product_label, product_sku, quantity, unit_price, line_total))
                inserted_lines += 1
            
            # Déterminer le fournisseur principal (le plus fréquent)
            fournisseur_principal = list(suppliers_found)[0] if suppliers_found else None
            
            # Insérer ou mettre à jour la facture
            cursor.execute("""
                INSERT INTO invoices (id, order_number, invoice_created, due_date, 
                                     subtotal, total, status, reference_externe,
                                     fournisseur, gestionnaire)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    order_number = EXCLUDED.order_number,
                    total = EXCLUDED.total,
                    reference_externe = EXCLUDED.reference_externe,
                    fournisseur = COALESCE(invoices.fournisseur, EXCLUDED.fournisseur),
                    gestionnaire = COALESCE(invoices.gestionnaire, EXCLUDED.gestionnaire),
                    updated_at = CURRENT_TIMESTAMP
            """, (invoice_id, order_number, invoice_created, due_date,
                  subtotal, total, status, reference_externe,
                  fournisseur_principal, gestionnaire))
            
            if cursor.rowcount > 0:
                inserted_invoices += 1
                if fournisseur_principal:
                    updated_suppliers += 1
            
            if inserted_invoices % 50 == 0:
                conn.commit()
                print(f"   {inserted_invoices} factures importées...")
                
        except Exception as e:
            print(f"❌ Erreur facture {inv.get('order_number')}: {e}")
            continue
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\n✅ Import terminé:")
    print(f"   - Factures: {inserted_invoices}")
    print(f"   - Lignes: {inserted_lines}")
    print(f"   - Factures avec fournisseur: {updated_suppliers}")
    
    return inserted_invoices, inserted_lines

def update_existing_invoices_with_suppliers():
    """Met à jour les factures existantes avec les fournisseurs depuis products"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Récupérer le mapping produit -> fournisseur
    cursor.execute("""
        SELECT sku, supplier_name 
        FROM products 
        WHERE supplier_name IS NOT NULL AND supplier_name != ''
    """)
    product_suppliers = {sku: supplier for sku, supplier in cursor.fetchall()}
    
    if not product_suppliers:
        print("⚠️ Aucun fournisseur trouvé dans la table products")
        print("   Exécutez d'abord: python fetch_suppliers_auto.py")
        return 0
    
    print(f"📋 {len(product_suppliers)} produits avec fournisseur trouvés")
    
    # Mettre à jour les fournisseurs des factures via les lignes
    cursor.execute("""
        SELECT DISTINCT il.invoice_id, il.product_sku
        FROM invoice_lines il
        WHERE il.product_sku IS NOT NULL
        AND il.product_sku != ''
    """)
    
    invoice_products = {}
    for invoice_id, sku in cursor.fetchall():
        if invoice_id not in invoice_products:
            invoice_products[invoice_id] = set()
        if sku in product_suppliers:
            invoice_products[invoice_id].add(product_suppliers[sku])
    
    # Mettre à jour chaque facture
    updated = 0
    for invoice_id, suppliers in invoice_products.items():
        if suppliers:
            fournisseur = list(suppliers)[0]  # Prendre le premier fournisseur
            cursor.execute("""
                UPDATE invoices 
                SET fournisseur = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND (fournisseur IS NULL OR fournisseur = 'Non spécifié')
            """, (fournisseur, invoice_id))
            updated += cursor.rowcount
    
    # Mettre à jour les plateformes
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = CASE
            WHEN reference_externe LIKE 'PO-%' OR reference_externe LIKE 'E%' THEN 'Temu'
            WHEN reference_externe LIKE '40%' OR reference_externe LIKE '%-%-%' THEN 'Amazon'
            WHEN order_number LIKE 'SHOP-%' THEN 'Shopify'
            ELSE 'Direct'
        END
        WHERE gestionnaire IS NULL OR gestionnaire = 'Non spécifié'
    """)
    
    platform_updated = cursor.rowcount
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ {updated} factures mises à jour avec fournisseur")
    print(f"✅ {platform_updated} factures mises à jour avec plateforme")
    
    return updated

def show_statistics():
    """Affiche les statistiques finales"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM invoices")
    total_inv = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM invoices WHERE fournisseur IS NOT NULL AND fournisseur != 'Non spécifié'")
    with_supplier = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM invoices WHERE gestionnaire IS NOT NULL AND gestionnaire != 'Non spécifié'")
    with_platform = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT fournisseur, COUNT(*) 
        FROM invoices 
        WHERE fournisseur IS NOT NULL AND fournisseur != 'Non spécifié'
        GROUP BY fournisseur 
        ORDER BY COUNT(*) DESC 
        LIMIT 10
    """)
    top_suppliers = cursor.fetchall()
    
    cursor.execute("""
        SELECT gestionnaire, COUNT(*) 
        FROM invoices 
        WHERE gestionnaire IS NOT NULL AND gestionnaire != 'Non spécifié'
        GROUP BY gestionnaire 
        ORDER BY COUNT(*) DESC
    """)
    platforms = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    print("\n" + "="*50)
    print("📊 STATISTIQUES FINALES")
    print("="*50)
    print(f"   📄 Total factures: {total_inv}")
    print(f"   🏭 Avec fournisseur: {with_supplier}")
    print(f"   📱 Avec plateforme: {with_platform}")
    
    if top_suppliers:
        print("\n🏆 Top fournisseurs:")
        for supplier, count in top_suppliers:
            print(f"   - {supplier}: {count} factures")
    
    if platforms:
        print("\n📱 Plateformes:")
        for platform, count in platforms:
            print(f"   - {platform}: {count} factures")
    
    print("="*50)

if __name__ == "__main__":
    print("="*50)
    print("📥 IMPORT DES FACTURES AVEC FOURNISSEURS")
    print("="*50)
    print()
    
    # 1. Importer les nouvelles factures
    import_invoices_with_suppliers()
    
    # 2. Mettre à jour les factures existantes
    print("\n🔄 Mise à jour des factures existantes...")
    update_existing_invoices_with_suppliers()
    
    # 3. Afficher les statistiques
    show_statistics()