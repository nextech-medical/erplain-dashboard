# fetch_last_5_months_2026.py
import requests
import json
import psycopg2
import pandas as pd
from datetime import datetime, timedelta
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, API_URL, BEARER_TOKEN

def fetch_all_invoices():
    """Récupère TOUTES les factures depuis l'API Erplain."""
    
    all_invoices = []
    page = 1
    page_size = 100
    
    while True:
        print(f"📥 Récupération des factures page {page}...")
        
        query = f"""
        query {{
          Invoices(page: {page}, page_size: {page_size}) {{
            edges {{
              node {{
                id
                label
                order_number
                status
                created
                due_date
                subtotal
                total
                external_reference
                notes
                line_items {{
                  edges {{
                    node {{
                      product {{
                        id
                        label
                        ... on variantType {{
                          sku
                        }}
                      }}
                      quantity
                      price
                      total
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """
        
        headers = {
            "Authorization": f"Bearer {BEARER_TOKEN}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(API_URL, json={"query": query}, headers=headers, timeout=30)
            
            if response.status_code != 200:
                print(f"❌ Erreur HTTP {response.status_code}")
                break
            
            data = response.json()
            
            if "errors" in data:
                print(f"❌ Erreurs GraphQL: {data['errors']}")
                break
            
            invoices_data = data.get("data", {}).get("Invoices", {})
            edges = invoices_data.get("edges", {})
            
            nodes = []
            if isinstance(edges, dict):
                node_data = edges.get("node")
                if isinstance(node_data, list):
                    nodes = node_data
                elif node_data:
                    nodes = [node_data]
            
            if not nodes:
                print("✅ Plus de factures à récupérer")
                break
            
            all_invoices.extend(nodes)
            
            # Afficher les années trouvées
            years_found = set()
            for inv in nodes[-5:]:
                created = inv.get('created')
                if created:
                    year = created[:4] if isinstance(created, str) else str(created.year)
                    years_found.add(year)
            
            print(f"   ✅ {len(nodes)} factures (total: {len(all_invoices)}) - Années: {sorted(years_found)}")
            
            if len(nodes) < page_size:
                break
            page += 1
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            break
    
    return all_invoices

def filter_last_5_months_2026(invoices):
    """Filtre les 5 derniers mois de 2026 (août à décembre)"""
    
    # Mois cibles: août(8), septembre(9), octobre(10), novembre(11), décembre(12)
    target_months = [8, 9, 10, 11, 12]
    
    filtered_invoices = []
    stats = {month: 0 for month in target_months}
    
    for inv in invoices:
        created = inv.get('created')
        if created:
            if isinstance(created, str):
                year = int(created[:4])
                month = int(created[5:7])
            else:
                year = created.year
                month = created.month
            
            if year == 2026 and month in target_months:
                filtered_invoices.append(inv)
                stats[month] += 1
    
    return filtered_invoices, stats

def save_invoices_to_db(invoices):
    """Sauvegarde les factures dans PostgreSQL."""
    
    if not invoices:
        print("⚠️ Aucune facture des 5 derniers mois 2026 à sauvegarder")
        return 0
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Supprimer les anciennes factures des 5 derniers mois 2026
    cursor.execute("""
        DELETE FROM invoice_lines WHERE invoice_id IN (
            SELECT id FROM invoices 
            WHERE EXTRACT(YEAR FROM invoice_created) = 2026 
            AND EXTRACT(MONTH FROM invoice_created) IN (8,9,10,11,12)
        )
    """)
    cursor.execute("""
        DELETE FROM invoices 
        WHERE EXTRACT(YEAR FROM invoice_created) = 2026 
        AND EXTRACT(MONTH FROM invoice_created) IN (8,9,10,11,12)
    """)
    print("🗑️ Anciennes factures des 5 derniers mois 2026 supprimées")
    
    invoice_count = 0
    line_count = 0
    
    for invoice in invoices:
        try:
            cursor.execute("""
                INSERT INTO invoices (
                    id, label, order_number, status, invoice_created,
                    due_date, subtotal, total, reference_externe, notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    label = EXCLUDED.label,
                    status = EXCLUDED.status,
                    total = EXCLUDED.total,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                str(invoice.get('id')),
                invoice.get('label'),
                invoice.get('order_number'),
                invoice.get('status'),
                invoice.get('created'),
                invoice.get('due_date'),
                invoice.get('subtotal'),
                invoice.get('total'),
                invoice.get('external_reference'),
                invoice.get('notes')
            ))
            invoice_count += 1
            
            # Insérer les lignes
            line_items = invoice.get('line_items', {})
            edges = line_items.get('edges', {})
            items = edges.get('node', []) if isinstance(edges, dict) else []
            
            for item in items:
                product = item.get('product', {})
                sku = product.get('sku')
                
                cursor.execute("""
                    INSERT INTO invoice_lines (
                        invoice_id, product_label, product_sku, quantity,
                        unit_price, line_total
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    str(invoice.get('id')),
                    product.get('label'),
                    sku,
                    item.get('quantity'),
                    item.get('price'),
                    item.get('total')
                ))
                line_count += 1
            
            if invoice_count % 50 == 0:
                print(f"   Sauvegarde: {invoice_count} factures, {line_count} lignes...")
                conn.commit()
                
        except Exception as e:
            print(f"❌ Erreur pour facture {invoice.get('id')}: {e}")
            continue
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\n✅ {invoice_count} factures sauvegardées")
    print(f"✅ {line_count} lignes de facture sauvegardées")
    
    return invoice_count

def update_platforms():
    """Met à jour les plateformes automatiquement."""
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE invoices 
        SET gestionnaire = CASE
            WHEN reference_externe LIKE 'PO-%' OR reference_externe LIKE 'E%' THEN 'Temu'
            WHEN reference_externe LIKE '40%' OR reference_externe LIKE '%-%-%' THEN 'Amazon'
            WHEN order_number LIKE 'SHOP-%' THEN 'Shopify'
            ELSE 'Direct'
        END
        WHERE gestionnaire IS NULL OR gestionnaire = ''
        AND EXTRACT(YEAR FROM invoice_created) = 2026
    """)
    
    updated = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ {updated} factures mises à jour avec plateforme")
    return updated

def show_statistics(stats):
    """Affiche les statistiques par mois."""
    
    month_names = {
        8: "Août 2026",
        9: "Septembre 2026",
        10: "Octobre 2026",
        11: "Novembre 2026",
        12: "Décembre 2026"
    }
    
    print("\n" + "="*50)
    print("📊 FACTURES DES 5 DERNIERS MOIS 2026")
    print("="*50)
    
    total = 0
    for month, count in stats.items():
        print(f"   {month_names.get(month, month)}: {count} factures")
        total += count
    
    print(f"\n   📄 TOTAL: {total} factures")
    print("="*50)

def save_to_json(invoices, filename="factures_5_derniers_mois_2026.json"):
    """Sauvegarde les factures en JSON."""
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(invoices, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n💾 Fichier JSON sauvegardé: {filename}")

def main():
    print("\n" + "="*60)
    print("🔄 RÉCUPÉRATION DES 5 DERNIERS MOIS 2026")
    print("   (Août, Septembre, Octobre, Novembre, Décembre 2026)")
    print("="*60)
    
    # 1. Récupérer toutes les factures
    print("\n📦 Récupération de toutes les factures depuis Erplain...")
    all_invoices = fetch_all_invoices()
    
    if not all_invoices:
        print("❌ Aucune facture récupérée")
        return
    
    print(f"\n📊 Total factures récupérées: {len(all_invoices)}")
    
    # 2. Analyser les années disponibles
    years = {}
    for inv in all_invoices:
        created = inv.get('created')
        if created:
            year = created[:4] if isinstance(created, str) else str(created.year)
            years[year] = years.get(year, 0) + 1
    
    print("\n📅 Factures par année dans l'API:")
    for year in sorted(years.keys()):
        print(f"   {year}: {years[year]} factures")
    
    # 3. Filtrer les 5 derniers mois 2026
    invoices_filtered, stats = filter_last_5_months_2026(all_invoices)
    
    if not invoices_filtered:
        print("\n❌ Aucune facture trouvée pour les 5 derniers mois de 2026!")
        print("\n🔍 Vérifications:")
        print("   1. Des factures existent-elles pour août-décembre 2026?")
        print("   2. Votre token API a-t-il accès à toutes les factures?")
        return
    
    # 4. Afficher les résultats
    print(f"\n🎯 {len(invoices_filtered)} factures trouvées pour les 5 derniers mois 2026")
    show_statistics(stats)
    
    # 5. Sauvegarder en JSON
    save_to_json(invoices_filtered)
    
    # 6. Sauvegarder dans PostgreSQL
    print("\n💾 Sauvegarde dans PostgreSQL...")
    count = save_invoices_to_db(invoices_filtered)
    
    # 7. Mettre à jour les plateformes
    if count > 0:
        print("\n📱 Mise à jour des plateformes...")
        update_platforms()
    
    # 8. Afficher un échantillon
    print("\n📋 Échantillon des factures trouvées:")
    for inv in invoices_filtered[:10]:
        created = inv.get('created', '')[:10]
        print(f"   {inv.get('order_number')}: {created} - {inv.get('total')}€ - {inv.get('status')}")
    
    print("\n" + "="*60)
    print(f"✅ {count} factures des 5 derniers mois 2026 importées!")
    print("="*60)

if __name__ == "__main__":
    main()