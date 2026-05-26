# fix_gestionnaire_avance.py
"""
Script avancé pour corriger les gestionnaires dans invoices
en utilisant plusieurs méthodes de correspondance
"""

import psycopg2
import re
import pandas as pd
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

def show_detailed_comparison():
    """Affiche une comparaison détaillée entre invoices et orders"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    print("\n" + "=" * 80)
    print("🔍 COMPARAISON INVOICES VS ORDERS")
    print("=" * 80)
    
    # Afficher les 10 premières factures
    print("\n📋 10 PREMIÈRES FACTURES:")
    query_inv = """
        SELECT order_number, label, reference_externe, gestionnaire, total
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        LIMIT 10
    """
    df_inv = pd.read_sql_query(query_inv, conn)
    print(df_inv.to_string(index=False))
    
    # Afficher les 10 premières commandes
    print("\n📋 10 PREMIÈRES COMMANDES ORDERS:")
    query_ord = """
        SELECT order_id, label, external_reference, account_manager_name
        FROM orders
        LIMIT 10
    """
    df_ord = pd.read_sql_query(query_ord, conn)
    print(df_ord.to_string(index=False))
    
    # Vérifier les correspondances possibles
    print("\n🔗 RECHERCHE DE CORRESPONDANCES:")
    
    # Par order_number = order_id
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) 
        FROM invoices i
        JOIN orders o ON i.order_number = o.order_id
    """)
    count1 = cursor.fetchone()[0]
    print(f"   Correspondance order_number = order_id: {count1}")
    
    # Par order_number = label
    cursor.execute("""
        SELECT COUNT(*) 
        FROM invoices i
        JOIN orders o ON i.order_number = o.label
    """)
    count2 = cursor.fetchone()[0]
    print(f"   Correspondance order_number = label: {count2}")
    
    # Par label = order_id
    cursor.execute("""
        SELECT COUNT(*) 
        FROM invoices i
        JOIN orders o ON i.label = o.order_id
    """)
    count3 = cursor.fetchone()[0]
    print(f"   Correspondance label = order_id: {count3}")
    
    # Par label = label
    cursor.execute("""
        SELECT COUNT(*) 
        FROM invoices i
        JOIN orders o ON i.label = o.label
    """)
    count4 = cursor.fetchone()[0]
    print(f"   Correspondance label = label: {count4}")
    
    # Par reference_externe
    cursor.execute("""
        SELECT COUNT(*) 
        FROM invoices i
        JOIN orders o ON i.reference_externe = o.external_reference
    """)
    count5 = cursor.fetchone()[0]
    print(f"   Correspondance reference_externe = external_reference: {count5}")
    
    cursor.close()
    conn.close()
    
    return count1, count2, count3, count4, count5

def fix_by_pattern():
    """Corrige les gestionnaires par pattern de référence"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 80)
    print("🔧 CORRECTION PAR PATTERN DE RÉFÉRENCE")
    print("=" * 80)
    
    # 1. Amazon: référence externe qui contient un pattern Amazon (3 chiffres - 7 chiffres - 7 chiffres)
    print("\n📌 AMAZON:")
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Amazon .fr'
        WHERE reference_externe IS NOT NULL
        AND reference_externe ~ '^[0-9]{3}-[0-9]{7}-[0-9]{7}$'
    """)
    print(f"   ✅ {cursor.rowcount} factures → Amazon .fr")
    
    # 2. Temu: référence externe qui commence par PO-
    print("\n📌 TEMU:")
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'TEMU FR'
        WHERE reference_externe IS NOT NULL
        AND reference_externe LIKE 'PO-%'
    """)
    print(f"   ✅ {cursor.rowcount} factures → TEMU FR")
    
    # 3. Appels d'offres: PH..., DMS..., BS..., etc.
    print("\n📌 APPELS D'OFFRES:")
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Appels doffres'
        WHERE reference_externe IS NOT NULL
        AND (reference_externe LIKE 'PH%' 
             OR reference_externe LIKE 'DMS%'
             OR reference_externe LIKE 'BS%'
             OR reference_externe LIKE '2026/%'
             OR reference_externe LIKE '%/9991')
    """)
    print(f"   ✅ {cursor.rowcount} factures → Appels doffres")
    
    # 4. NEXTECH Boutique: numéros simples (4-8 chiffres)
    print("\n📌 NEXTECH BOUTIQUE:")
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'NEXTECH Boutique'
        WHERE reference_externe IS NOT NULL
        AND reference_externe ~ '^[0-9]{4,8}$'
    """)
    print(f"   ✅ {cursor.rowcount} factures → NEXTECH Boutique")
    
    # 5. Par email client
    print("\n📌 PAR EMAIL CLIENT:")
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'NEXTECH Boutique'
        WHERE customer_email = 'roua.faroukh@nextechmedical.fr'
        AND (gestionnaire IS NULL OR gestionnaire = 'Direct')
    """)
    print(f"   ✅ {cursor.rowcount} factures → NEXTECH Boutique")
    
    conn.commit()
    cursor.close()
    conn.close()

def fix_by_customer_name():
    """Corrige par nom de client (hôpitaux, cliniques)"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("\n" + "=" * 80)
    print("🔧 CORRECTION PAR NOM DE CLIENT")
    print("=" * 80)
    
    # Hôpitaux et cliniques -> Appels d'offres
    print("\n📌 HÔPITAUX ET CLINIQUES:")
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = 'Appels doffres'
        WHERE customer_name IS NOT NULL
        AND (customer_name LIKE 'CH %' 
             OR customer_name LIKE 'CENTRE HOSPITALIER%'
             OR customer_name LIKE 'HOPITAL%'
             OR customer_name LIKE 'CLINIQUE%'
             OR customer_name LIKE 'HOSPICES%'
             OR customer_name LIKE 'GH %'
             OR customer_name LIKE 'GCS %'
             OR customer_name LIKE 'CHU%')
        AND (gestionnaire IS NULL OR gestionnaire = 'Direct')
    """)
    print(f"   ✅ {cursor.rowcount} factures → Appels doffres")
    
    conn.commit()
    cursor.close()
    conn.close()

def show_final_stats():
    """Affiche les statistiques finales détaillées"""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    print("\n" + "=" * 80)
    print("📊 STATISTIQUES FINALES PAR GESTIONNAIRE")
    print("=" * 80)
    
    # Statistiques par gestionnaire
    query = """
        SELECT 
            COALESCE(gestionnaire, 'Sans gestionnaire') as gestionnaire,
            COUNT(*) as nb_factures,
            COUNT(DISTINCT customer_name) as nb_clients,
            ROUND(SUM(total)::numeric, 2) as ca_total,
            ROUND(AVG(total)::numeric, 2) as panier_moyen,
            COUNT(CASE WHEN reference_externe IS NOT NULL AND reference_externe != '' THEN 1 END) as avec_ref
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        GROUP BY gestionnaire
        ORDER BY ca_total DESC
    """
    
    df = pd.read_sql_query(query, conn)
    print("\n" + df.to_string(index=False))
    
    # Vérifier les références sans gestionnaire
    print("\n" + "=" * 80)
    print("🔍 RÉFÉRENCES SANS GESTIONNAIRE CORRESPONDANT")
    print("=" * 80)
    
    query2 = """
        SELECT 
            reference_externe,
            order_number,
            customer_name,
            total
        FROM invoices
        WHERE invoice_created >= '2026-01-01'
        AND (gestionnaire IS NULL OR gestionnaire = '' OR gestionnaire = 'Direct')
        AND reference_externe IS NOT NULL
        AND reference_externe != ''
        LIMIT 20
    """
    
    df2 = pd.read_sql_query(query2, conn)
    if not df2.empty:
        print("\n⚠️ Ces références n'ont pas été catégorisées:")
        print(df2.to_string(index=False))
    else:
        print("\n✅ Toutes les références ont été catégorisées")
    
    conn.close()
    return df

def fix_all():
    """Exécute toutes les corrections"""
    
    print("\n" + "=" * 80)
    print("🚀 CORRECTION COMPLÈTE DES GESTIONNAIRES")
    print("=" * 80)
    
    # 1. Afficher la situation avant
    print("\n📊 AVANT CORRECTION:")
    show_final_stats()
    
    # 2. Analyser les correspondances
    show_detailed_comparison()
    
    # 3. Appliquer les corrections
    fix_by_pattern()
    fix_by_customer_name()
    
    # 4. Afficher le résultat après
    print("\n📊 APRÈS CORRECTION:")
    show_final_stats()
    
    print("\n" + "=" * 80)
    print("✅ CORRECTION TERMINÉE")
    print("=" * 80)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--compare":
            show_detailed_comparison()
        elif sys.argv[1] == "--stats":
            show_final_stats()
        elif sys.argv[1] == "--pattern":
            fix_by_pattern()
            show_final_stats()
        elif sys.argv[1] == "--all":
            fix_all()
        else:
            print("""
Usage: python fix_gestionnaire_avance.py [OPTION]

Options:
  --compare   Affiche la comparaison entre invoices et orders
  --stats     Affiche les statistiques actuelles
  --pattern   Corrige uniquement par pattern de référence
  --all       Exécute toutes les corrections

Sans option: Exécute la correction complète
            """)
    else:
        fix_all()