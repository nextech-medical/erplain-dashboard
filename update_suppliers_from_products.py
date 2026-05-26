# update_suppliers_from_products.py
"""
Script pour mettre à jour les fournisseurs dans invoices
à partir de la table products (synchronisée avec Erplain)
"""
import psycopg2
import pandas as pd
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def update_suppliers_from_products():
    """Met à jour les fournisseurs dans invoices à partir de la table products"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # 1. Vérifier que la table products existe
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'products'
        )
    """)
    
    if not cursor.fetchone()[0]:
        print("⚠️ Table 'products' non trouvée")
        print("   Exécutez d'abord: python fetch_suppliers_auto.py")
        return 0
    
    # 2. Mettre à jour via les lignes de facture et les produits
    print("\n🔄 Mise à jour des fournisseurs depuis la table products...")
    
    cursor.execute("""
        UPDATE invoices i
        SET fournisseur = p.supplier_name
        FROM invoice_lines il
        JOIN products p ON p.sku = il.product_sku
        WHERE i.id = il.invoice_id
        AND p.supplier_name IS NOT NULL
        AND p.supplier_name != ''
        AND (i.fournisseur IS NULL OR i.fournisseur = 'Non spécifié')
    """)
    
    updated = cursor.rowcount
    print(f"   ✅ {updated} factures mises à jour")
    
    # 3. Pour les factures sans fournisseur, essayer via la marque
    cursor.execute("""
        UPDATE invoices i
        SET fournisseur = p.brand
        FROM invoice_lines il
        JOIN products p ON p.sku = il.product_sku
        WHERE i.id = il.invoice_id
        AND p.brand IS NOT NULL
        AND p.brand != ''
        AND (i.fournisseur IS NULL OR i.fournisseur = 'Non spécifié')
    """)
    
    updated2 = cursor.rowcount
    print(f"   ✅ {updated2} factures mises à jour via la marque")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return updated + updated2

def show_supplier_stats():
    """Affiche les statistiques des fournisseurs"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    # Statistiques des fournisseurs dans products
    query_products = """
        SELECT 
            supplier_name,
            COUNT(*) as nb_produits
        FROM products
        WHERE supplier_name IS NOT NULL AND supplier_name != ''
        GROUP BY supplier_name
        ORDER BY nb_produits DESC
        LIMIT 20
    """
    
    df_products = pd.read_sql_query(query_products, conn)
    
    # Statistiques des fournisseurs dans invoices
    query_invoices = """
        SELECT 
            fournisseur,
            COUNT(*) as nb_factures,
            ROUND(SUM(total)::numeric, 2) as ca_total
        FROM invoices
        WHERE fournisseur IS NOT NULL AND fournisseur != 'Non spécifié'
        GROUP BY fournisseur
        ORDER BY ca_total DESC
        LIMIT 20
    """
    
    df_invoices = pd.read_sql_query(query_invoices, conn)
    
    conn.close()
    
    print("\n" + "="*60)
    print("📊 FOURNISSEURS DANS LA TABLE PRODUCTS")
    print("="*60)
    if not df_products.empty:
        print(df_products.to_string(index=False))
    else:
        print("   Aucun fournisseur trouvé dans products")
    
    print("\n" + "="*60)
    print("📊 FOURNISSEURS DANS LES FACTURES")
    print("="*60)
    if not df_invoices.empty:
        print(df_invoices.to_string(index=False))
    else:
        print("   Aucun fournisseur trouvé dans les factures")
    
    return df_products, df_invoices

def get_missing_suppliers():
    """Identifie les produits sans fournisseur dans products"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    query = """
        SELECT 
            sku,
            name,
            brand
        FROM products
        WHERE (supplier_name IS NULL OR supplier_name = '')
        AND sku IS NOT NULL
        LIMIT 50
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if not df.empty:
        print("\n" + "="*60)
        print("📋 PRODUITS SANS FOURNISSEUR")
        print("="*60)
        print(df.to_string(index=False))
    else:
        print("\n✅ Tous les produits ont un fournisseur assigné")
    
    return df

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔄 MISE À JOUR DES FOURNISSEURS")
    print("="*60)
    
    # Mettre à jour les fournisseurs
    count = update_suppliers_from_products()
    
    # Afficher les statistiques
    show_supplier_stats()
    
    # Afficher les produits sans fournisseur
    get_missing_suppliers()
    
    print("\n" + "="*60)
    print(f"✅ {count} fournisseurs mis à jour")
    print("="*60)