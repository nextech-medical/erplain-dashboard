# link_invoices_to_delivery_notes_fixed.py
import psycopg2
import pandas as pd
from datetime import datetime
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def link_invoices_to_delivery_notes():
    """
    Lie les factures aux bons de livraison.
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # 1. Créer une table de liaison avec des colonnes plus grandes
    cursor.execute("DROP TABLE IF EXISTS invoice_delivery_link CASCADE")
    cursor.execute("""
        CREATE TABLE invoice_delivery_link (
            id SERIAL PRIMARY KEY,
            invoice_id TEXT,
            invoice_number TEXT,
            delivery_note_id TEXT,
            delivery_note_number TEXT,
            match_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 2. Lier par bl_number (delivery_notes) = order_number (invoices)
    print("\n🔗 Liaison des factures aux BL par numéro de commande...")
    
    cursor.execute("""
        INSERT INTO invoice_delivery_link (
            invoice_id, invoice_number, delivery_note_id, 
            delivery_note_number, match_type
        )
        SELECT DISTINCT
            i.id as invoice_id,
            i.order_number as invoice_number,
            dn.id as delivery_note_id,
            dn.bl_number as delivery_note_number,
            'exact_match'
        FROM invoices i
        INNER JOIN delivery_notes dn ON dn.bl_number = i.order_number
        WHERE i.order_number IS NOT NULL 
        AND dn.bl_number IS NOT NULL
        AND i.order_number != ''
        AND dn.bl_number != ''
    """)
    
    exact_matches = cursor.rowcount
    print(f"   ✅ {exact_matches} liaisons exactes (par order_number/bl_number)")
    
    # 3. Lier par correspondance partielle (si les numéros contiennent des préfixes/suffixes)
    cursor.execute("""
        INSERT INTO invoice_delivery_link (
            invoice_id, invoice_number, delivery_note_id, 
            delivery_note_number, match_type
        )
        SELECT DISTINCT
            i.id,
            i.order_number,
            dn.id,
            dn.bl_number,
            'partial_match'
        FROM invoices i
        INNER JOIN delivery_notes dn ON 
            POSITION(dn.bl_number IN i.order_number) > 0 
            OR POSITION(i.order_number IN dn.bl_number) > 0
        WHERE i.order_number IS NOT NULL 
        AND dn.bl_number IS NOT NULL
        AND i.order_number != ''
        AND dn.bl_number != ''
        AND NOT EXISTS (
            SELECT 1 FROM invoice_delivery_link l 
            WHERE l.invoice_id = i.id AND l.delivery_note_id = dn.id
        )
    """)
    
    partial_matches = cursor.rowcount
    print(f"   ✅ {partial_matches} liaisons partielles")
    
    conn.commit()
    
    # 4. Afficher les statistiques
    cursor.execute("""
        SELECT 
            COUNT(DISTINCT invoice_id) as invoices_linked,
            COUNT(DISTINCT delivery_note_id) as delivery_notes_linked,
            COUNT(*) as total_links
        FROM invoice_delivery_link
    """)
    stats = cursor.fetchone()
    
    print(f"\n📊 Statistiques des liaisons:")
    print(f"   - Factures liées: {stats[0] or 0}")
    print(f"   - BL liés: {stats[1] or 0}")
    print(f"   - Total liaisons: {stats[2] or 0}")
    
    cursor.close()
    conn.close()

def add_delivery_column_to_invoices():
    """Ajoute une colonne delivery_note_id à la table invoices."""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Ajouter la colonne si elle n'existe pas (en TEXT pour éviter les problèmes de longueur)
    cursor.execute("""
        ALTER TABLE invoices 
        ADD COLUMN IF NOT EXISTS delivery_note_id TEXT
    """)
    
    # Mettre à jour la colonne avec les liaisons
    cursor.execute("""
        UPDATE invoices i
        SET delivery_note_id = l.delivery_note_id
        FROM invoice_delivery_link l
        WHERE i.id = l.invoice_id
    """)
    
    updated = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ {updated} factures mises à jour avec delivery_note_id")

def show_linked_data():
    """Affiche les données liées."""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    query = """
        SELECT 
            i.order_number as facture_numero,
            ROUND(i.total::numeric, 2) as facture_montant,
            i.customer_name as client,
            l.delivery_note_number as bl_numero,
            l.match_type as type_liaison
        FROM invoices i
        JOIN invoice_delivery_link l ON l.invoice_id = i.id
        ORDER BY i.invoice_created DESC
        LIMIT 20
    """
    
    try:
        df = pd.read_sql_query(query, conn)
        if not df.empty:
            print("\n📋 Aperçu des liaisons (20 premiers):")
            print(df.to_string(index=False))
        else:
            print("\n📋 Aucune liaison trouvée")
    except Exception as e:
        print(f"❌ Erreur: {e}")
    
    conn.close()

def show_unlinked():
    """Affiche les factures et BL non liés."""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    # Factures sans BL
    query_invoices = """
        SELECT i.order_number, i.customer_name, ROUND(i.total::numeric, 2) as montant
        FROM invoices i
        LEFT JOIN invoice_delivery_link l ON l.invoice_id = i.id
        WHERE l.id IS NULL
        LIMIT 20
    """
    
    df_invoices = pd.read_sql_query(query_invoices, conn)
    
    # BL sans facture
    query_delivery = """
        SELECT dn.bl_number, dn.status, dn.date_creation
        FROM delivery_notes dn
        LEFT JOIN invoice_delivery_link l ON l.delivery_note_id = dn.id
        WHERE l.id IS NULL
        LIMIT 20
    """
    
    try:
        df_delivery = pd.read_sql_query(query_delivery, conn)
    except:
        df_delivery = pd.DataFrame()
    
    conn.close()
    
    print("\n📋 Factures sans BL associé:")
    if not df_invoices.empty:
        print(df_invoices.to_string(index=False))
    else:
        print("   Aucune")
    
    print("\n📋 BL sans facture associée:")
    if not df_delivery.empty:
        print(df_delivery.to_string(index=False))
    else:
        print("   Aucun")

def show_statistics():
    """Affiche les statistiques détaillées."""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    # Compter les BL par statut
    query_stats = """
        SELECT 
            dn.status,
            COUNT(*) as total_bl,
            COUNT(l.id) as bl_lies
        FROM delivery_notes dn
        LEFT JOIN invoice_delivery_link l ON l.delivery_note_id = dn.id
        GROUP BY dn.status
        ORDER BY total_bl DESC
    """
    
    df_stats = pd.read_sql_query(query_stats, conn)
    
    print("\n📊 Statistiques par statut des BL:")
    if not df_stats.empty:
        print(df_stats.to_string(index=False))
    
    conn.close()

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🔗 LINK FACTURES ↔ BONS DE LIVRAISON")
    print("="*60)
    
    # 1. Lier les données
    link_invoices_to_delivery_notes()
    
    # 2. Ajouter la colonne aux factures
    add_delivery_column_to_invoices()
    
    # 3. Afficher les statistiques
    show_statistics()
    
    # 4. Afficher les liaisons
    show_linked_data()
    
    # 5. Afficher les non-liés
    show_unlinked()
    
    print("\n" + "="*60)
    print("✅ Liaison terminée")
    print("="*60)