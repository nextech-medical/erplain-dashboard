# fix_suppliers_in_invoices.py
"""
Script pour corriger les fournisseurs dans les factures
"""

import psycopg2
import pandas as pd
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def fix_suppliers_in_invoices():
    """
    Met à jour la colonne fournisseur dans invoices à partir des produits
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 70)
    print("🔧 CORRECTION DES FOURNISSEURS DANS LES FACTURES")
    print("=" * 70)
    
    # 1. Vérifier les colonnes
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'invoices' AND column_name = 'fournisseur'
    """)
    if not cursor.fetchone():
        cursor.execute("ALTER TABLE invoices ADD COLUMN fournisseur VARCHAR(255)")
        print("✅ Colonne 'fournisseur' ajoutée")
    
    # 2. Mettre à jour les fournisseurs depuis order_lines (commandes)
    cursor.execute("""
        UPDATE invoices i
        SET fournisseur = ol.supplier_name
        FROM order_lines ol
        JOIN sales_orders so ON so.id = ol.order_id
        WHERE (i.order_number = so.order_number OR i.label = so.label)
        AND ol.supplier_name IS NOT NULL
        AND ol.supplier_name != ''
        AND (i.fournisseur IS NULL OR i.fournisseur = '' OR i.fournisseur = 'Non spécifié')
    """)
    print(f"   ✅ {cursor.rowcount} factures mises à jour depuis order_lines")
    
    # 3. Mettre à jour depuis products
    cursor.execute("""
        UPDATE invoices i
        SET fournisseur = p.supplier_name
        FROM invoice_lines il
        JOIN products p ON p.sku = il.product_sku OR p.name = il.product_label
        WHERE i.id = il.invoice_id
        AND p.supplier_name IS NOT NULL
        AND p.supplier_name != ''
        AND (i.fournisseur IS NULL OR i.fournisseur = '' OR i.fournisseur = 'Non spécifié')
    """)
    print(f"   ✅ {cursor.rowcount} factures mises à jour depuis products")
    
    # 4. Détection par marque dans le nom du produit
    brand_mapping = {
        'ZARYS': 'ZARYS',
        'ABENA': 'Abena',
        'ONTEX': 'Ontex',
        'HARTMANN': 'Hartmann',
        'CHIRANA': 'Chirana',
        'BASTOS': 'Bastos',
        'COMED': 'Comed',
        'TENA': 'Tena',
        'SIDAPHARM': 'Sidapharm',
        'PHARMAPLAST': 'Pharmaplast',
        'VITREX': 'Vitrex',
        'BD': 'BD Medical',
        'FL MEDICAL': 'FL Medical',
        'MOLTEX': 'Moltex',
        'BAMBO': 'Bambo Nature',
        'LESSA': 'LessA'
    }
    
    updated = 0
    for brand, supplier in brand_mapping.items():
        cursor.execute("""
            UPDATE invoices i
            SET fournisseur = %s
            FROM invoice_lines il
            WHERE i.id = il.invoice_id
            AND UPPER(il.product_label) LIKE %s
            AND (i.fournisseur IS NULL OR i.fournisseur = '' OR i.fournisseur = 'Non spécifié')
        """, (supplier, f'%{brand}%'))
        updated += cursor.rowcount
    
    print(f"   ✅ {updated} factures mises à jour par détection de marque")
    
    # 5. Définir 'Non spécifié' pour les autres
    cursor.execute("""
        UPDATE invoices 
        SET fournisseur = 'Non spécifié'
        WHERE fournisseur IS NULL OR fournisseur = ''
    """)
    print(f"   ✅ {cursor.rowcount} factures marquées 'Non spécifié'")
    
    conn.commit()
    
    # 6. Afficher les statistiques
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN fournisseur != 'Non spécifié' THEN 1 END) as avec_fournisseur
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
    """)
    row = cursor.fetchone()
    print(f"\n📊 Résultat:")
    print(f"   - Total factures 2026: {row[0]}")
    print(f"   - Avec fournisseur: {row[1]}")
    
    cursor.execute("""
        SELECT fournisseur, COUNT(*) as nb
        FROM invoices
        WHERE fournisseur != 'Non spécifié'
        AND invoice_created >= '2026-01-01'
        GROUP BY fournisseur
        ORDER BY nb DESC
        LIMIT 15
    """)
    print(f"\n🏆 Top fournisseurs:")
    for row in cursor.fetchall():
        print(f"   - {row[0]}: {row[1]} factures")
    
    cursor.close()
    conn.close()


def show_suppliers_stats():
    """Affiche les statistiques des fournisseurs"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    query = """
        SELECT 
            fournisseur,
            COUNT(*) as nb_factures,
            ROUND(SUM(total)::numeric, 2) as ca_total
        FROM invoices
        WHERE fournisseur IS NOT NULL 
        AND fournisseur != 'Non spécifié'
        AND invoice_created >= '2026-01-01'
        GROUP BY fournisseur
        ORDER BY ca_total DESC
        LIMIT 20
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print("\n" + "=" * 70)
    print("📊 STATISTIQUES FOURNISSEURS DANS LES FACTURES")
    print("=" * 70)
    print(df.to_string(index=False))
    
    return df


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--show":
        show_suppliers_stats()
    else:
        fix_suppliers_in_invoices()
        show_suppliers_stats()