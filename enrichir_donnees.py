import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def enrichir_fournisseurs():
    """Ajoute les fournisseurs basés sur les produits"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Association produit -> fournisseur (à personnaliser selon vos données)
    mapping_fournisseur = {
        "ZARYS": "ZARYS Medical",
        "Abena": "Abena",
        "Ontex": "Ontex",
        "HARTMANN": "Hartmann",
        "Chirana": "Chirana",
        "BASTOS": "Bastos",
        "Comed": "Comed",
        "Tena": "Tena",
        "LESSA": "LessA",
        "Bambo": "Bambo Nature",
        "Moltex": "Moltex",
        "SIDAPHARM": "Sidapharm",
        "FL MEDICAL": "FL Medical",
        "PHARMAPLAST": "Pharmaplast",
        "VITREX": "Vitrex",
        "BD": "BD Medical",
        "HARTMANN": "Hartmann"
    }
    
    for marque, fournisseur in mapping_fournisseur.items():
        cursor.execute("""
            UPDATE invoices 
            SET fournisseur = %s 
            WHERE fournisseur IS NULL AND id IN (
                SELECT DISTINCT invoice_id 
                FROM invoice_lines 
                WHERE product_label ILIKE %s
            )
        """, (fournisseur, f"%{marque}%"))
        print(f"   {marque}: {cursor.rowcount} factures mises à jour")
    
    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Fournisseurs mis à jour")

def enrichir_gestionnaires():
    """Ajoute les gestionnaires (Amazon, Temu, Shopify)"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Par email client
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Amazon' 
        WHERE gestionnaire IS NULL AND customer_email ILIKE '%amazon%'
    """)
    print(f"   Amazon: {cursor.rowcount} factures")
    
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Shopify' 
        WHERE gestionnaire IS NULL AND (customer_email ILIKE '%shopify%' OR order_number ILIKE 'SHOP-%')
    """)
    print(f"   Shopify: {cursor.rowcount} factures")
    
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Temu' 
        WHERE gestionnaire IS NULL AND (customer_email ILIKE '%temu%' OR order_number ILIKE 'TEMU-%')
    """)
    print(f"   Temu: {cursor.rowcount} factures")
    
    # Par défaut, "Direct" pour les autres
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Direct' 
        WHERE gestionnaire IS NULL
    """)
    print(f"   Direct: {cursor.rowcount} factures")
    
    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Gestionnaires mis à jour")

def init_parametres():
    """Initialise les paramètres par défaut"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO parametres (type_transport, tarif_unitaire, cout_fixe)
        SELECT 'quantite', 0.50, 2.00
        WHERE NOT EXISTS (SELECT 1 FROM parametres)
    """)
    
    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Paramètres par défaut initialisés")

def show_stats():
    """Affiche les statistiques après enrichissement"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 50)
    print("📊 STATISTIQUES APRÈS ENRICHISSEMENT")
    print("=" * 50)
    
    cursor.execute("SELECT COUNT(*) FROM invoices WHERE fournisseur IS NOT NULL")
    fourn_count = cursor.fetchone()[0]
    print(f"   🏭 Factures avec fournisseur: {fourn_count}")
    
    cursor.execute("SELECT COUNT(*) FROM invoices WHERE gestionnaire IS NOT NULL")
    gest_count = cursor.fetchone()[0]
    print(f"   📱 Factures avec plateforme: {gest_count}")
    
    # Top fournisseurs
    cursor.execute("""
        SELECT fournisseur, COUNT(*) as nb, SUM(total) as ca
        FROM invoices 
        WHERE fournisseur IS NOT NULL
        GROUP BY fournisseur
        ORDER BY ca DESC
        LIMIT 5
    """)
    print("\n🏆 Top 5 fournisseurs:")
    for row in cursor.fetchall():
        print(f"   - {row[0]}: {row[1]} factures, {row[2]:,.2f} €")
    
    # Top plateformes
    cursor.execute("""
        SELECT gestionnaire, COUNT(*) as nb, SUM(total) as ca
        FROM invoices 
        WHERE gestionnaire IS NOT NULL
        GROUP BY gestionnaire
        ORDER BY ca DESC
    """)
    print("\n📱 Top plateformes:")
    for row in cursor.fetchall():
        print(f"   - {row[0]}: {row[1]} factures, {row[2]:,.2f} €")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    print("🏭 Enrichissement des données...")
    print()
    enrichir_fournisseurs()
    print()
    enrichir_gestionnaires()
    print()
    init_parametres()
    show_stats()