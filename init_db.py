import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def init_database():
    """Crée toutes les tables nécessaires dans PostgreSQL"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # ========== 1. TABLE DES COMMANDES ==========
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            label TEXT,
            created TEXT,
            customer_label TEXT,
            customer_emails TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_lines (
            id SERIAL PRIMARY KEY,
            order_id TEXT REFERENCES orders(id),
            product_label TEXT,
            sku TEXT,
            quantity REAL,
            unit_price REAL
        )
    ''')
    
    print("✅ Tables orders et order_lines créées")
    
    # ========== 2. TABLE DES FACTURES (avec TOUTES les colonnes) ==========
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id TEXT PRIMARY KEY,
            label TEXT,
            order_number TEXT,
            invoice_created TIMESTAMP,
            due_date DATE,
            subtotal DECIMAL(10,2),
            total DECIMAL(10,2),
            tax_amount DECIMAL(10,2),
            customer_id INTEGER,
            customer_name TEXT,
            customer_email TEXT,
            reference_externe TEXT,
            bl_number TEXT,
            fournisseur TEXT,
            gestionnaire TEXT,
            poids_total DECIMAL(10,2),
            quantite_total INTEGER,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    print("✅ Table invoices créée avec toutes les colonnes")
    
    # ========== 3. TABLE DES LIGNES DE FACTURE ==========
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoice_lines (
            id SERIAL PRIMARY KEY,
            invoice_id TEXT REFERENCES invoices(id) ON DELETE CASCADE,
            product_label TEXT,
            product_sku TEXT,
            quantity INTEGER,
            unit_price DECIMAL(10,2),
            line_total DECIMAL(10,2),
            discount DECIMAL(10,2),
            poids_unitaire DECIMAL(10,2),
            frais_transport DECIMAL(10,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    print("✅ Table invoice_lines créée")
    
    # ========== 4. INDEX ==========
    
    # Index pour orders
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_label)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_order_lines_product ON order_lines(product_label)')
    
    # Index pour invoices (vérifier l'existence des colonnes)
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_created ON invoices(invoice_created)")
        print("✅ Index idx_invoices_created créé")
    except Exception as e:
        print(f"⚠️ Index idx_invoices_created: {e}")
    
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_customer ON invoices(customer_name)")
        print("✅ Index idx_invoices_customer créé")
    except Exception as e:
        print(f"⚠️ Index idx_invoices_customer: {e}")
    
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_order ON invoices(order_number)")
        print("✅ Index idx_invoices_order créé")
    except Exception as e:
        print(f"⚠️ Index idx_invoices_order: {e}")
    
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_fournisseur ON invoices(fournisseur)")
        print("✅ Index idx_invoices_fournisseur créé")
    except Exception as e:
        print(f"⚠️ Index idx_invoices_fournisseur: {e}")
    
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_gestionnaire ON invoices(gestionnaire)")
        print("✅ Index idx_invoices_gestionnaire créé")
    except Exception as e:
        print(f"⚠️ Index idx_invoices_gestionnaire: {e}")
    
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_email ON invoices(customer_email)")
        print("✅ Index idx_invoices_email créé")
    except Exception as e:
        print(f"⚠️ Index idx_invoices_email: {e}")
    
    # Index pour invoice_lines
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_inv_lines_invoice ON invoice_lines(invoice_id)")
        print("✅ Index idx_inv_lines_invoice créé")
    except Exception as e:
        print(f"⚠️ Index idx_inv_lines_invoice: {e}")
    
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_inv_lines_product ON invoice_lines(product_label)")
        print("✅ Index idx_inv_lines_product créé")
    except Exception as e:
        print(f"⚠️ Index idx_inv_lines_product: {e}")
    
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_inv_lines_sku ON invoice_lines(product_sku)")
        print("✅ Index idx_inv_lines_sku créé")
    except Exception as e:
        print(f"⚠️ Index idx_inv_lines_sku: {e}")
    
    # ========== 5. TABLE DES PARAMÈTRES ==========
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parametres (
            id SERIAL PRIMARY KEY,
            type_transport TEXT,
            tarif_unitaire DECIMAL(10,2),
            cout_fixe DECIMAL(10,2),
            date_maj TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Insertion des paramètres par défaut si la table est vide
    cursor.execute("SELECT COUNT(*) FROM parametres")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO parametres (type_transport, tarif_unitaire, cout_fixe)
            VALUES ('quantite', 0.50, 2.00)
        """)
        print("✅ Paramètres par défaut ajoutés")
    
    print("✅ Table parametres créée")
    
    # ========== 6. TABLE DES STATISTIQUES ==========
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stats_kpis (
            id SERIAL PRIMARY KEY,
            type VARCHAR(50),
            calcul_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ca_total DECIMAL(15,2),
            nb_factures INTEGER,
            nb_commandes INTEGER,
            nb_clients INTEGER,
            nb_produits_vendus INTEGER,
            panier_moyen DECIMAL(10,2),
            data JSONB
        )
    """)
    
    print("✅ Table stats_kpis créée")
    
    # ========== 7. VUES ==========
    
    cursor.execute("""
        CREATE OR REPLACE VIEW view_invoices_summary AS
        SELECT 
            i.id,
            i.order_number,
            i.invoice_created as created,
            i.customer_name,
            i.customer_email,
            i.total,
            i.fournisseur,
            i.gestionnaire,
            i.reference_externe,
            i.bl_number,
            COUNT(il.id) as nb_products,
            COALESCE(SUM(il.quantity), 0) as total_quantity,
            COALESCE(SUM(il.line_total), 0) as total_amount
        FROM invoices i
        LEFT JOIN invoice_lines il ON i.id = il.invoice_id
        GROUP BY i.id, i.order_number, i.invoice_created, i.customer_name, i.customer_email, 
                 i.total, i.fournisseur, i.gestionnaire, i.reference_externe, i.bl_number
    """)
    
    print("✅ Vue view_invoices_summary créée")
    
    # ========== 8. VUE POUR LE DASHBOARD ==========
    
    cursor.execute("""
        CREATE OR REPLACE VIEW view_dashboard_stats AS
        SELECT 
            DATE(i.invoice_created) as date,
            COUNT(DISTINCT i.id) as nb_factures,
            COUNT(DISTINCT i.customer_email) as nb_clients,
            SUM(i.total) as ca_total,
            SUM(il.quantity) as produits_vendus,
            AVG(i.total) as panier_moyen
        FROM invoices i
        LEFT JOIN invoice_lines il ON i.id = il.invoice_id
        WHERE i.invoice_created IS NOT NULL
        GROUP BY DATE(i.invoice_created)
        ORDER BY date DESC
    """)
    
    print("✅ Vue view_dashboard_stats créée")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 50)
    print("✅ Toutes les tables PostgreSQL ont été créées avec succès")
    print("=" * 50)

def drop_all_tables():
    """Supprime toutes les tables"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Supprimer les vues
    cursor.execute("DROP VIEW IF EXISTS view_dashboard_stats CASCADE")
    cursor.execute("DROP VIEW IF EXISTS view_invoices_summary CASCADE")
    
    # Supprimer les tables
    cursor.execute("DROP TABLE IF EXISTS invoice_lines CASCADE")
    cursor.execute("DROP TABLE IF EXISTS invoices CASCADE")
    cursor.execute("DROP TABLE IF EXISTS order_lines CASCADE")
    cursor.execute("DROP TABLE IF EXISTS orders CASCADE")
    cursor.execute("DROP TABLE IF EXISTS parametres CASCADE")
    cursor.execute("DROP TABLE IF EXISTS stats_kpis CASCADE")
    
    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Toutes les tables ont été supprimées")

def reset_database():
    """Réinitialise complètement la base"""
    print("🔄 Réinitialisation complète de la base...")
    drop_all_tables()
    init_database()

def check_database():
    """Vérifie la structure de la base de données"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Vérifier les tables
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    
    tables = cursor.fetchall()
    print("\n📋 Tables dans la base de données:")
    for table in tables:
        print(f"   - {table[0]}")
    
    # Vérifier les colonnes de invoices
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'invoices'
        ORDER BY ordinal_position
    """)
    
    columns = cursor.fetchall()
    print("\n📋 Colonnes de la table invoices:")
    for col in columns:
        print(f"   - {col[0]} ({col[1]})")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "--drop":
            drop_all_tables()
        elif sys.argv[1] == "--reset":
            reset_database()
        elif sys.argv[1] == "--check":
            check_database()
        else:
            print("Usage: python init_db.py [--drop] [--reset] [--check]")
    else:
        init_database()