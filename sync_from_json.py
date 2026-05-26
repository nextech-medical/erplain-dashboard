# sync_from_json_fixed.py
"""
Script corrigé pour synchroniser la base PostgreSQL à partir des fichiers JSON
- Corrige le problème 'can't adapt type dict'
- Gère correctement les commandes (sales orders)
"""

import psycopg2
import pandas as pd
import json
import re
from datetime import datetime, date
from typing import Dict, List, Any, Tuple, Optional
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

# ============================================================
# CONFIGURATION
# ============================================================

JSON_FILES = {
    'invoices': 'factures_depuis_2026.json',
    'delivery_notes': 'delivery_notes_2026.json',
    'sales_orders':'commandes_avec_fournisseurs.json',
    
}

BATCH_SIZE = 100


# ============================================================
# FONCTIONS DE TRAITEMENT
# ============================================================

def parse_date(date_str: Any) -> Optional[date]:
    """Convertit une chaîne de date en date."""
    if not date_str:
        return None
    
    try:
        if isinstance(date_str, str):
            if 'T' in date_str:
                date_str = date_str.split('T')[0]
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        elif isinstance(date_str, date):
            return date_str
        elif isinstance(date_str, datetime):
            return date_str.date()
    except:
        pass
    return None


def parse_datetime(dt_str: Any) -> Optional[datetime]:
    """Convertit une chaîne en datetime."""
    if not dt_str:
        return None
    
    try:
        if isinstance(dt_str, str):
            if 'T' in dt_str:
                dt_str = dt_str.split('+')[0].split('Z')[0]
                if len(dt_str) > 19:
                    dt_str = dt_str[:19]
                return datetime.strptime(dt_str, '%Y-%m-%dT%H:%M:%S')
            return datetime.strptime(dt_str, '%Y-%m-%d')
        elif isinstance(dt_str, datetime):
            return dt_str
        elif isinstance(dt_str, date):
            return datetime.combine(dt_str, datetime.min.time())
    except Exception as e:
        pass
    return None


def safe_str(value: Any) -> Optional[str]:
    """Convertit une valeur en string de façon sûre."""
    if value is None:
        return None
    if isinstance(value, dict):
        return None
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    return str(value) if value else None


def safe_float(value: Any) -> float:
    """Convertit une valeur en float de façon sûre."""
    if value is None:
        return 0.0
    if isinstance(value, dict):
        return 0.0
    try:
        return float(value)
    except:
        return 0.0


def safe_int(value: Any) -> int:
    """Convertit une valeur en int de façon sûre."""
    if value is None:
        return 0
    if isinstance(value, dict):
        return 0
    try:
        return int(float(value))
    except:
        return 0


def detect_platform(order_number: Optional[str], reference: Optional[str]) -> str:
    """Détecte la plateforme à partir du numéro de commande ou référence."""
    if reference and isinstance(reference, str):
        ref = reference.upper()
        if ref.startswith('40') and '-' in ref:
            return 'Amazon'
        if ref.startswith('PO-') or (ref.startswith('E') and len(ref) >= 6):
            return 'Temu'
        if 'SHOP' in ref:
            return 'Shopify'
    
    if order_number and isinstance(order_number, str):
        order = order_number.upper()
        if order.startswith('40'):
            return 'Amazon'
        if order.startswith('PO-'):
            return 'Temu'
        if 'SHOP' in order:
            return 'Shopify'
    
    return 'Direct'


# ============================================================
# TRAITEMENT DES COMMANDES (SALES ORDERS)
# ============================================================

def process_sales_order(order: Dict[str, Any]) -> Dict[str, Any]:
    """Traite une commande - version corrigée pour les types dict."""
    
    # Extraire le gestionnaire de compte (peut être un dict ou une string)
    account_manager = order.get('account_manager')
    if isinstance(account_manager, dict):
        account_manager_name = safe_str(account_manager.get('label') or account_manager.get('name'))
        account_manager_id = safe_str(account_manager.get('id'))
    else:
        account_manager_name = safe_str(account_manager)
        account_manager_id = None
    
    # Extraire les infos client
    customer = order.get('customer', {})
    if isinstance(customer, dict):
        customer_name = safe_str(customer.get('label'))
        emails = customer.get('emails', [])
        customer_email = safe_str(emails[0]) if emails and isinstance(emails, list) else None
    else:
        customer_name = None
        customer_email = None
    
    # Récupérer le numéro de commande
    order_number = order.get('order_id') or order.get('order_number') or order.get('label')
    
    # Récupérer la référence externe
    external_reference = order.get('external_reference')
    if isinstance(external_reference, dict):
        external_reference = None
    
    return {
        'id': safe_str(order.get('id')),
        'order_number': safe_str(order_number),
        'label': safe_str(order.get('label')),
        'external_reference': safe_str(external_reference),
        'created': parse_datetime(order.get('created')),
        'account_manager_id': account_manager_id,
        'account_manager_name': account_manager_name,
        'status': safe_str(order.get('status')),
        'customer_name': customer_name,
        'customer_email': customer_email,
        'gestionnaire': detect_platform(order_number, external_reference)
    }


def process_sales_order_lines(order: Dict[str, Any], order_id: str) -> List[Dict[str, Any]]:
    """Extrait les lignes d'une commande - version corrigée."""
    lines = []
    
    # Récupérer les lignes - structure line_items.edges.node
    line_items = order.get('line_items', {})
    
    nodes = []
    if isinstance(line_items, dict):
        edges = line_items.get('edges', {})
        if isinstance(edges, dict):
            nodes = edges.get('node', [])
        elif isinstance(edges, list):
            nodes = [e.get('node') for e in edges if e.get('node')]
    elif isinstance(line_items, list):
        nodes = line_items
    
    for node in nodes:
        if not isinstance(node, dict):
            continue
        
        product = node.get('product', {})
        
        # Récupérer le SKU
        product_sku = None
        if isinstance(product, dict):
            product_sku = safe_str(product.get('sku'))
        
        quantity = safe_int(node.get('quantity', 0))
        unit_price = safe_float(node.get('price', 0))
        
        if product.get('label') or product_sku or quantity > 0:
            lines.append({
                'order_id': order_id,
                'line_id': safe_str(node.get('id')),
                'product_id': safe_str(product.get('id')) if isinstance(product, dict) else None,
                'product_label': safe_str(product.get('label')) if isinstance(product, dict) else None,
                'product_sku': product_sku,
                'quantity': quantity,
                'unit_price': unit_price
            })
    
    return lines


# ============================================================
# TRAITEMENT DES FACTURES
# ============================================================

def process_invoice(invoice: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Traite une facture et retourne (dict_invoice, list_lines)."""
    
    # Extraire les infos client
    customer = invoice.get('customer', {})
    if isinstance(customer, dict):
        customer_name = safe_str(customer.get('label'))
        emails = customer.get('emails', [])
        customer_email = safe_str(emails[0]) if emails and isinstance(emails, list) else None
    else:
        customer_name = None
        customer_email = None
    
    # Récupérer la référence externe
    external_ref = invoice.get('external_reference')
    if isinstance(external_ref, dict):
        external_ref = None
    
    # Détecter la plateforme
    order_number = invoice.get('order_number')
    gestionnaire = detect_platform(order_number, external_ref)
    
    # Date de création
    created = invoice.get('created') or invoice.get('date') or invoice.get('invoice_created')
    
    invoice_dict = {
        'id': safe_str(invoice.get('id')),
        'label': safe_str(invoice.get('label')),
        'order_number': safe_str(order_number),
        'status': safe_str(invoice.get('status')),
        'invoice_created': parse_date(created),
        'due_date': parse_date(invoice.get('due_date')),
        'subtotal': safe_float(invoice.get('subtotal', 0)),
        'total': safe_float(invoice.get('total', 0)),
        'tax_amount': safe_float(invoice.get('tax_amount', 0) or invoice.get('shipping_tax_amount', 0)),
        'customer_name': customer_name,
        'customer_email': customer_email,
        'reference_externe': safe_str(external_ref),
        'notes_text': safe_str(invoice.get('notes')),
        'fournisseur': None,
        'gestionnaire': gestionnaire,
        'bl_number': None,
        'shipping_date': None
    }
    
    # Traiter les lignes de facture
    lines = []
    
    line_items = invoice.get('line_items', {})
    
    nodes = []
    if isinstance(line_items, dict):
        edges = line_items.get('edges', [])
        if isinstance(edges, list):
            nodes = [e.get('node') for e in edges if e.get('node')]
        elif isinstance(edges, dict):
            nodes = edges.get('node', [])
    elif isinstance(line_items, list):
        nodes = line_items
    
    for node in nodes:
        if not isinstance(node, dict):
            continue
        
        product = node.get('product', {})
        product_label = product.get('label') if isinstance(product, dict) else None
        product_sku = product.get('sku') if isinstance(product, dict) else None
        
        quantity = safe_int(node.get('quantity', 0))
        price = safe_float(node.get('price', 0))
        discount = safe_float(node.get('discount', 0))
        line_total = safe_float(node.get('total', 0))
        
        if line_total == 0 and quantity and price:
            line_total = quantity * price
        
        if product_label or product_sku or quantity > 0:
            lines.append({
                'invoice_id': invoice_dict['id'],
                'product_label': safe_str(product_label),
                'product_sku': safe_str(product_sku),
                'quantity': quantity,
                'unit_price': price,
                'discount': discount,
                'line_total': line_total
            })
    
    return invoice_dict, lines


def process_delivery_note(note: Dict[str, Any]) -> Dict[str, Any]:
    """Traite un bon de livraison."""
    return {
        'id': safe_str(note.get('id')),
        'order_number': safe_str(note.get('order_number')),
        'external_reference': safe_str(note.get('external_reference')),
        'shipping_date': parse_date(note.get('shipping_date')),
        'status': safe_str(note.get('status') or note.get('shipping_order_status')),
        'tracking_number': safe_str(note.get('tracking_number')),
        'created_at': parse_datetime(note.get('created') or note.get('created_at'))
    }


# ============================================================
# CHARGEMENT DES FICHIERS JSON
# ============================================================

def load_json_file(filepath: str) -> List[Dict[str, Any]]:
    """Charge un fichier JSON et retourne une liste."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            if 'nodes' in data:
                return data['nodes']
            elif 'edges' in data:
                edges = data['edges']
                if isinstance(edges, list):
                    return [e.get('node') for e in edges if e.get('node')]
                elif isinstance(edges, dict):
                    nodes = edges.get('node', [])
                    return nodes if isinstance(nodes, list) else [nodes]
            return [data]
        return []
    except FileNotFoundError:
        print(f"   ⚠️ Fichier non trouvé: {filepath}")
        return []
    except json.JSONDecodeError as e:
        print(f"   ❌ Erreur JSON dans {filepath}: {e}")
        return []


# ============================================================
# CRÉATION DES TABLES
# ============================================================

def create_tables(cursor):
    """Crée les tables."""
    
    # Supprimer les anciennes tables
    cursor.execute("DROP TABLE IF EXISTS sales_order_lines CASCADE")
    cursor.execute("DROP TABLE IF EXISTS sales_orders CASCADE")
    cursor.execute("DROP TABLE IF EXISTS invoice_lines CASCADE")
    cursor.execute("DROP TABLE IF EXISTS invoices CASCADE")
    cursor.execute("DROP TABLE IF EXISTS delivery_notes CASCADE")
    
    # Table invoices
    cursor.execute("""
        CREATE TABLE invoices (
            id VARCHAR(100) PRIMARY KEY,
            label VARCHAR(200),
            order_number VARCHAR(100),
            status VARCHAR(50),
            invoice_created DATE,
            due_date DATE,
            subtotal DECIMAL(12,2),
            total DECIMAL(12,2),
            tax_amount DECIMAL(12,2),
            customer_name TEXT,
            customer_email TEXT,
            reference_externe TEXT,
            notes_text TEXT,
            fournisseur TEXT,
            gestionnaire VARCHAR(50),
            bl_number TEXT,
            shipping_date DATE,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Table invoice_lines
    cursor.execute("""
        CREATE TABLE invoice_lines (
            id SERIAL PRIMARY KEY,
            invoice_id VARCHAR(100) REFERENCES invoices(id) ON DELETE CASCADE,
            product_label TEXT,
            product_sku VARCHAR(100),
            quantity INTEGER,
            unit_price DECIMAL(12,2),
            discount DECIMAL(12,2),
            line_total DECIMAL(12,2)
        )
    """)
    
    # Table delivery_notes
    cursor.execute("""
        CREATE TABLE delivery_notes (
            id VARCHAR(100) PRIMARY KEY,
            order_number VARCHAR(100),
            external_reference TEXT,
            shipping_date DATE,
            status VARCHAR(50),
            tracking_number TEXT,
            created_at TIMESTAMP,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Table sales_orders
    cursor.execute("""
        CREATE TABLE sales_orders (
            id VARCHAR(100) PRIMARY KEY,
            order_number VARCHAR(100),
            label VARCHAR(200),
            external_reference TEXT,
            created TIMESTAMP,
            account_manager_id VARCHAR(100),
            account_manager_name VARCHAR(100),
            status VARCHAR(50),
            customer_name TEXT,
            customer_email TEXT,
            gestionnaire VARCHAR(50),
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Table sales_order_lines
    cursor.execute("""
        CREATE TABLE sales_order_lines (
            id SERIAL PRIMARY KEY,
            order_id VARCHAR(100) REFERENCES sales_orders(id) ON DELETE CASCADE,
            line_id VARCHAR(100),
            product_id VARCHAR(100),
            product_label TEXT,
            product_sku VARCHAR(100),
            quantity INTEGER,
            unit_price DECIMAL(12,2)
        )
    """)
    
    # Index
    cursor.execute("CREATE INDEX idx_invoices_order ON invoices(order_number)")
    cursor.execute("CREATE INDEX idx_invoices_created ON invoices(invoice_created)")
    cursor.execute("CREATE INDEX idx_invoice_lines_invoice ON invoice_lines(invoice_id)")
    cursor.execute("CREATE INDEX idx_delivery_notes_order ON delivery_notes(order_number)")
    cursor.execute("CREATE INDEX idx_sales_orders_number ON sales_orders(order_number)")
    cursor.execute("CREATE INDEX idx_sales_orders_created ON sales_orders(created)")
    cursor.execute("CREATE INDEX idx_sales_order_lines_order ON sales_order_lines(order_id)")
    
    print("✅ Tables créées")


# ============================================================
# INSERTION DES DONNÉES
# ============================================================

def insert_invoices_batch(cursor, invoices_batch: List[Dict[str, Any]]) -> int:
    """Insère un lot de factures."""
    inserted = 0
    for inv in invoices_batch:
        try:
            cursor.execute("""
                INSERT INTO invoices (
                    id, label, order_number, status, invoice_created,
                    due_date, subtotal, total, tax_amount, customer_name,
                    customer_email, reference_externe, notes_text,
                    fournisseur, gestionnaire
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                inv['id'], inv['label'], inv['order_number'], inv['status'],
                inv['invoice_created'], inv['due_date'], inv['subtotal'],
                inv['total'], inv['tax_amount'], inv['customer_name'],
                inv['customer_email'], inv['reference_externe'], inv['notes_text'],
                inv['fournisseur'], inv['gestionnaire']
            ))
            inserted += 1
        except Exception as e:
            print(f"      ⚠️ Erreur facture {inv['id']}: {e}")
    return inserted


def insert_lines_batch(cursor, lines_batch: List[Dict[str, Any]]) -> int:
    """Insère un lot de lignes de facture."""
    inserted = 0
    for line in lines_batch:
        try:
            cursor.execute("""
                INSERT INTO invoice_lines (
                    invoice_id, product_label, product_sku, quantity,
                    unit_price, discount, line_total
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                line['invoice_id'], line['product_label'], line['product_sku'],
                line['quantity'], line['unit_price'], line['discount'], line['line_total']
            ))
            inserted += 1
        except Exception as e:
            print(f"      ⚠️ Erreur ligne: {e}")
    return inserted


def insert_delivery_notes_batch(cursor, notes_batch: List[Dict[str, Any]]) -> int:
    """Insère un lot de bons de livraison."""
    inserted = 0
    for note in notes_batch:
        try:
            cursor.execute("""
                INSERT INTO delivery_notes (
                    id, order_number, external_reference, shipping_date,
                    status, tracking_number, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                note['id'], note['order_number'], note['external_reference'],
                note['shipping_date'], note['status'], note['tracking_number'],
                note['created_at']
            ))
            inserted += 1
        except Exception as e:
            print(f"      ⚠️ Erreur BL {note['id']}: {e}")
    return inserted


def insert_sales_orders_batch(cursor, orders_batch: List[Dict[str, Any]]) -> int:
    """Insère un lot de commandes."""
    inserted = 0
    for order in orders_batch:
        try:
            cursor.execute("""
                INSERT INTO sales_orders (
                    id, order_number, label, external_reference, created,
                    account_manager_id, account_manager_name, status,
                    customer_name, customer_email, gestionnaire
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (
                order['id'], order['order_number'], order['label'],
                order['external_reference'], order['created'],
                order['account_manager_id'], order['account_manager_name'],
                order['status'], order['customer_name'], order['customer_email'],
                order['gestionnaire']
            ))
            inserted += 1
        except Exception as e:
            print(f"      ⚠️ Erreur commande {order['id']}: {e}")
    return inserted


def insert_sales_order_lines_batch(cursor, lines_batch: List[Dict[str, Any]]) -> int:
    """Insère un lot de lignes de commande."""
    inserted = 0
    for line in lines_batch:
        try:
            cursor.execute("""
                INSERT INTO sales_order_lines (
                    order_id, line_id, product_id, product_label, product_sku,
                    quantity, unit_price
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                line['order_id'], line['line_id'], line['product_id'],
                line['product_label'], line['product_sku'],
                line['quantity'], line['unit_price']
            ))
            inserted += 1
        except Exception as e:
            print(f"      ⚠️ Erreur ligne commande: {e}")
    return inserted


def link_invoices_to_delivery_notes(cursor) -> int:
    """Lie les factures aux BL via order_number."""
    cursor.execute("""
        UPDATE invoices i
        SET 
            bl_number = dn.order_number,
            shipping_date = COALESCE(i.shipping_date, dn.shipping_date),
            reference_externe = COALESCE(i.reference_externe, dn.external_reference)
        FROM delivery_notes dn
        WHERE i.order_number = dn.order_number
        AND i.bl_number IS NULL
    """)
    return cursor.rowcount


# ============================================================
# FONCTION PRINCIPALE
# ============================================================

def sync_from_json():
    """Synchronise la base PostgreSQL à partir des fichiers JSON."""
    
    print("\n" + "=" * 70)
    print("🔄 SYNCHRONISATION DEPUIS LES FICHIERS JSON")
    print("=" * 70)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # 1. Charger les fichiers JSON
    print("\n📥 CHARGEMENT DES FICHIERS JSON")
    print("-" * 50)
    
    invoices_data = load_json_file(JSON_FILES['invoices'])
    print(f"   ✅ Factures: {len(invoices_data)} lignes")
    
    delivery_notes_data = load_json_file(JSON_FILES['delivery_notes'])
    print(f"   ✅ Bons de livraison: {len(delivery_notes_data)} lignes")
    
    sales_orders_data = load_json_file(JSON_FILES['sales_orders'])
    print(f"   ✅ Commandes: {len(sales_orders_data)} lignes")
    
    # 2. Traiter les données
    print("\n🔧 TRAITEMENT DES DONNÉES")
    print("-" * 50)
    
    # Factures
    print("   Traitement des factures...")
    processed_invoices = []
    all_lines = []
    for i, inv in enumerate(invoices_data):
        if i % 500 == 0:
            print(f"      Progression: {i}/{len(invoices_data)}")
        inv_dict, lines = process_invoice(inv)
        processed_invoices.append(inv_dict)
        all_lines.extend(lines)
    print(f"   ✅ {len(processed_invoices)} factures traitées")
    print(f"   ✅ {len(all_lines)} lignes de facture")
    
    # BL
    print("\n   Traitement des BL...")
    processed_notes = [process_delivery_note(note) for note in delivery_notes_data]
    print(f"   ✅ {len(processed_notes)} BL traités")
    
    # Commandes
    print("\n   Traitement des commandes...")
    processed_orders = []
    all_order_lines = []
    for i, order in enumerate(sales_orders_data):
        if i % 500 == 0 and i > 0:
            print(f"      Progression: {i}/{len(sales_orders_data)}")
        order_dict = process_sales_order(order)
        processed_orders.append(order_dict)
        lines = process_sales_order_lines(order, order_dict['id'])
        all_order_lines.extend(lines)
    print(f"   ✅ {len(processed_orders)} commandes traitées")
    print(f"   ✅ {len(all_order_lines)} lignes de commande")
    
    # Aperçu des commandes
    print("\n📋 Aperçu des commandes:")
    for order in processed_orders[:5]:
        print(f"   - {order['order_number']}: ref='{order['external_reference']}', manager='{order['account_manager_name']}'")
    
    # 3. Connexion à PostgreSQL
    print("\n🔌 CONNEXION À POSTGRESQL")
    print("-" * 50)
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        conn.autocommit = False
        cursor = conn.cursor()
        print("   ✅ Connecté")
    except Exception as e:
        print(f"   ❌ Erreur de connexion: {e}")
        return
    
    # 4. Création des tables
    print("\n📁 CRÉATION DES TABLES")
    print("-" * 50)
    
    try:
        create_tables(cursor)
        conn.commit()
        print("   ✅ Tables créées")
    except Exception as e:
        print(f"   ❌ Erreur création tables: {e}")
        conn.rollback()
        cursor.close()
        conn.close()
        return
    
    # 5. Insertion des factures
    print("\n💾 INSERTION DES FACTURES")
    print("-" * 50)
    total_invoices = 0
    for i in range(0, len(processed_invoices), BATCH_SIZE):
        batch = processed_invoices[i:i+BATCH_SIZE]
        inserted = insert_invoices_batch(cursor, batch)
        total_invoices += inserted
        conn.commit()
        print(f"   Lot {i//BATCH_SIZE + 1}: {inserted} factures insérées")
    
    # 6. Insertion des lignes
    print("\n📋 INSERTION DES LIGNES DE FACTURE")
    print("-" * 50)
    total_lines = 0
    for i in range(0, len(all_lines), BATCH_SIZE * 10):
        batch = all_lines[i:i+BATCH_SIZE * 10]
        inserted = insert_lines_batch(cursor, batch)
        total_lines += inserted
        conn.commit()
        print(f"   Lot {i//(BATCH_SIZE*10) + 1}: {inserted} lignes insérées")
    
    # 7. Insertion des BL
    print("\n📦 INSERTION DES BONS DE LIVRAISON")
    print("-" * 50)
    total_dn = 0
    for i in range(0, len(processed_notes), BATCH_SIZE):
        batch = processed_notes[i:i+BATCH_SIZE]
        inserted = insert_delivery_notes_batch(cursor, batch)
        total_dn += inserted
        conn.commit()
        print(f"   Lot {i//BATCH_SIZE + 1}: {inserted} BL insérés")
    
    # 8. Insertion des commandes
    print("\n🛒 INSERTION DES COMMANDES")
    print("-" * 50)
    total_orders = 0
    for i in range(0, len(processed_orders), BATCH_SIZE):
        batch = processed_orders[i:i+BATCH_SIZE]
        inserted = insert_sales_orders_batch(cursor, batch)
        total_orders += inserted
        conn.commit()
        print(f"   Lot {i//BATCH_SIZE + 1}: {inserted} commandes insérées")
    
    # 9. Insertion des lignes de commande
    print("\n📋 INSERTION DES LIGNES DE COMMANDE")
    print("-" * 50)
    total_order_lines = 0
    for i in range(0, len(all_order_lines), BATCH_SIZE * 10):
        batch = all_order_lines[i:i+BATCH_SIZE * 10]
        inserted = insert_sales_order_lines_batch(cursor, batch)
        total_order_lines += inserted
        conn.commit()
        print(f"   Lot {i//(BATCH_SIZE*10) + 1}: {inserted} lignes insérées")
    
    # 10. Liaison factures - BL
    print("\n🔗 LIAISON FACTURES ↔ BL")
    print("-" * 50)
    linked = link_invoices_to_delivery_notes(cursor)
    conn.commit()
    print(f"   ✅ {linked} factures liées aux BL")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 70)
    print("✅ SYNCHRONISATION TERMINÉE")
    print("=" * 70)
    print(f"\n📊 RÉSUMÉ FINAL:")
    print(f"   - Factures insérées: {total_invoices}")
    print(f"   - Lignes facture: {total_lines}")
    print(f"   - BL insérés: {total_dn}")
    print(f"   - Commandes insérées: {total_orders}")
    print(f"   - Lignes commande: {total_order_lines}")


if __name__ == "__main__":
    sync_from_json()