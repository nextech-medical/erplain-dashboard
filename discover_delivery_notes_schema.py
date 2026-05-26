# get_delivery_notes_2026_corrected.py
"""
Script pour récupérer TOUS les bons de livraison (Shipments) de 2026
avec la syntaxe correcte de l'API Erplain
"""

import requests
import json
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any

# Configuration API
API_URL = "https://app.erplain.net/public-api/graphql/endpoint"
BEARER_TOKEN = "437b4d61de0d0be070992852610f685f"

def discover_correct_schema():
    """Découvre la structure correcte de l'API"""
    
    print("\n" + "="*60)
    print("🔍 DÉCOUVERTE DE LA STRUCTURE CORRECTE")
    print("="*60)
    
    # Tester Shipments avec la bonne syntaxe
    print("\n📡 Test de Shipments:")
    query = """
    {
      Shipments(page: 1, page_size: 5) {
        edges {
          node {
            id
            order_number
            external_reference
            status
            created
            shipping_date
          }
        }
      }
    }
    """
    
    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(API_URL, json={"query": query}, headers=headers, timeout=30)
        data = response.json()
        
        if "errors" in data:
            print(f"❌ Erreur: {data['errors'][0]['message'][:200] if data['errors'] else 'Unknown'}")
        else:
            shipments = data.get("data", {}).get("Shipments", {})
            edges = shipments.get("edges", [])
            print(f"✅ Shipments fonctionne! {len(edges)} BL trouvés")
            
            if edges:
                # Afficher tous les champs disponibles
                first_node = edges[0].get("node", {})
                print("\n📋 Champs disponibles dans Shipments:")
                for key in first_node.keys():
                    print(f"   - {key}")
            
            return data
    
    except Exception as e:
        print(f"❌ Erreur: {e}")
    
    return None

def fetch_all_shipments_2026(page_size: int = 100) -> List[Dict[str, Any]]:
    """
    Récupère tous les shipments (bons de livraison) de 2026
    Utilise la pagination page/page_size
    """
    all_shipments = []
    page = 1
    start_date = "2026-01-01"
    
    print("\n" + "="*60)
    print("📦 RÉCUPÉRATION DES BONS DE LIVRAISON 2026")
    print("="*60)
    
    while True:
        print(f"\n📥 Page {page}...")
        
        # Requête avec tous les champs possibles
        query = f"""
        {{
          Shipments(
            page: {page}, 
            page_size: {page_size},
            sort: {{ by: "created", direction: "DESC" }},
            filters: {{ created_from: "{start_date}" }}
          ) {{
            edges {{
              node {{
                id
                order_number
                external_reference
                status
                created
                shipping_date
                tracking_number
                notes
                internal_notes
                total_units
                customer {{
                  id
                  label
                  emails
                  phone
                }}
                line_items {{
                  edges {{
                    node {{
                      product {{
                        id
                        label
                        sku
                        barcode
                      }}
                      quantity
                      batch_number
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
            response = requests.post(API_URL, json={"query": query}, headers=headers, timeout=60)
            
            if response.status_code != 200:
                print(f"❌ Erreur HTTP {response.status_code}")
                break
            
            data = response.json()
            
            if "errors" in data:
                print(f"❌ Erreur GraphQL: {data['errors'][0]['message'][:200] if data['errors'] else 'Unknown'}")
                # Essayer une version avec moins de champs
                return fetch_shipments_simplified(page_size)
            
            shipments_data = data.get("data", {}).get("Shipments", {})
            edges = shipments_data.get("edges", [])
            
            if not edges:
                print("✅ Plus de BL à récupérer")
                break
            
            # Extraire les nodes
            nodes = []
            for edge in edges:
                if isinstance(edge, dict):
                    node = edge.get("node")
                    if node:
                        nodes.append(node)
            
            all_shipments.extend(nodes)
            print(f"   ✅ {len(nodes)} BL récupérés (total: {len(all_shipments)})")
            
            # Vérifier si on a tout récupéré
            if len(nodes) < page_size:
                break
            page += 1
                
        except requests.exceptions.Timeout:
            print(f"❌ Timeout - Réduction de la taille de page...")
            page_size = max(50, page_size // 2)
            continue
        except Exception as e:
            print(f"❌ Erreur: {e}")
            break
    
    print(f"\n📊 Total: {len(all_shipments)} bons de livraison récupérés")
    return all_shipments

def fetch_shipments_simplified(page_size: int = 100) -> List[Dict[str, Any]]:
    """
    Version simplifiée avec moins de champs
    """
    print("\n🔄 Utilisation de la version simplifiée...")
    
    all_shipments = []
    page = 1
    start_date = "2026-01-01"
    
    while True:
        query = f"""
        {{
          Shipments(
            page: {page}, 
            page_size: {page_size},
            filters: {{ created_from: "{start_date}" }}
          ) {{
            edges {{
              node {{
                id
                order_number
                external_reference
                status
                created
                shipping_date
                notes
                customer {{
                  id
                  label
                }}
                line_items {{
                  edges {{
                    node {{
                      product {{
                        label
                        sku
                      }}
                      quantity
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
            response = requests.post(API_URL, json={"query": query}, headers=headers, timeout=60)
            data = response.json()
            
            if "errors" in data:
                print(f"❌ Erreur: {data['errors'][0]['message'][:100] if data['errors'] else 'Unknown'}")
                break
            
            shipments_data = data.get("data", {}).get("Shipments", {})
            edges = shipments_data.get("edges", [])
            
            if not edges:
                break
            
            for edge in edges:
                if isinstance(edge, dict) and edge.get("node"):
                    all_shipments.append(edge["node"])
            
            print(f"   ✅ Page {page}: {len(edges)} BL (total: {len(all_shipments)})")
            
            if len(edges) < page_size:
                break
            page += 1
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            break
    
    return all_shipments

def normalize_shipment(shipment: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalise un bon de livraison pour le format CSV
    """
    # Extraire les infos client
    customer = shipment.get("customer", {}) or {}
    
    # Extraire les emails
    emails = customer.get("emails", [])
    customer_email = emails[0] if emails else None
    
    # Extraire les lignes de produits
    lines = []
    line_items_data = shipment.get("line_items", {})
    edges = line_items_data.get("edges", []) if isinstance(line_items_data, dict) else []
    
    for edge in edges:
        if isinstance(edge, dict):
            line = edge.get("node", {})
            product = line.get("product", {}) or {}
            lines.append({
                "product_label": product.get("label"),
                "product_sku": product.get("sku"),
                "product_barcode": product.get("barcode"),
                "quantity": line.get("quantity"),
                "batch_number": line.get("batch_number")
            })
    
    return {
        # Identifiants
        "id": shipment.get("id"),
        "order_number": shipment.get("order_number"),
        "external_reference": shipment.get("external_reference"),
        
        # Statut et dates
        "status": shipment.get("status"),
        "created_at": shipment.get("created"),
        "shipping_date": shipment.get("shipping_date"),
        
        # Transport
        "tracking_number": shipment.get("tracking_number"),
        
        # Notes
        "notes": shipment.get("notes"),
        "internal_notes": shipment.get("internal_notes"),
        
        # Quantités
        "total_units": shipment.get("total_units"),
        
        # Client
        "customer_id": customer.get("id"),
        "customer_name": customer.get("label"),
        "customer_email": customer_email,
        "customer_phone": customer.get("phone"),
        
        # Lignes
        "lines_count": len(lines),
        "lines": lines
    }

def extract_lines_data(shipments: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Extrait les lignes de produits dans un DataFrame séparé
    """
    rows = []
    
    for shipment in shipments:
        order_number = shipment.get("order_number")
        shipping_date = shipment.get("shipping_date")
        
        line_items_data = shipment.get("line_items", {})
        edges = line_items_data.get("edges", []) if isinstance(line_items_data, dict) else []
        
        for edge in edges:
            if isinstance(edge, dict):
                line = edge.get("node", {})
                product = line.get("product", {}) or {}
                
                rows.append({
                    "delivery_note_id": shipment.get("id"),
                    "order_number": order_number,
                    "shipping_date": shipping_date,
                    "product_label": product.get("label"),
                    "product_sku": product.get("sku"),
                    "product_barcode": product.get("barcode"),
                    "quantity": line.get("quantity"),
                    "batch_number": line.get("batch_number")
                })
    
    return pd.DataFrame(rows)

def save_shipments(shipments: List[Dict[str, Any]]):
    """
    Sauvegarde les bons de livraison dans différents formats
    """
    if not shipments:
        print("❌ Aucun BL à sauvegarder")
        return None, None
    
    # Normaliser les données
    normalized = [normalize_shipment(shipment) for shipment in shipments]
    
    # 1. Sauvegarde JSON complet
    with open("delivery_notes_2026_complet.json", "w", encoding="utf-8") as f:
        json.dump(shipments, f, indent=2, ensure_ascii=False, default=str)
    print(f"✅ JSON complet sauvegardé: delivery_notes_2026_complet.json")
    
    # 2. Sauvegarde CSV principal
    df_main = pd.DataFrame([{
        k: v for k, v in note.items() 
        if k != "lines"  # Exclure les lignes du main
    } for note in normalized])
    
    # Réorganiser les colonnes
    column_order = [
        'id', 'order_number', 'external_reference', 'status',
        'created_at', 'shipping_date', 'tracking_number',
        'total_units', 'customer_name', 'customer_email',
        'customer_phone', 'notes', 'internal_notes', 'lines_count'
    ]
    
    existing_cols = [col for col in column_order if col in df_main.columns]
    other_cols = [col for col in df_main.columns if col not in column_order]
    df_main = df_main[existing_cols + other_cols]
    
    df_main.to_csv("delivery_notes_2026.csv", index=False, encoding="utf-8-sig")
    print(f"✅ CSV principal sauvegardé: delivery_notes_2026.csv ({len(df_main)} lignes)")
    
    # 3. Sauvegarde des lignes de produits
    df_lines = extract_lines_data(shipments)
    if not df_lines.empty:
        df_lines.to_csv("delivery_notes_lines_2026.csv", index=False, encoding="utf-8-sig")
        print(f"✅ Lignes de produits sauvegardées: delivery_notes_lines_2026.csv ({len(df_lines)} lignes)")
    
    return df_main, df_lines

def show_statistics(shipments: List[Dict[str, Any]]):
    """
    Affiche les statistiques des BL récupérés
    """
    if not shipments:
        print("❌ Aucune donnée à analyser")
        return
    
    df_main, df_lines = save_shipments(shipments)
    
    print("\n" + "="*60)
    print("📊 STATISTIQUES DES BONS DE LIVRAISON 2026")
    print("="*60)
    
    # Statistiques générales
    print(f"\n📦 Général:")
    print(f"   - Nombre de BL: {len(shipments)}")
    print(f"   - Nombre de lignes produits: {len(df_lines) if df_lines is not None else 0}")
    
    if df_main is not None and not df_main.empty:
        # Par statut
        if 'status' in df_main.columns:
            status_counts = df_main['status'].value_counts()
            print(f"\n📊 Par statut:")
            for status, count in status_counts.items():
                print(f"   - {status}: {count}")
        
        # Avec/sans tracking
        if 'tracking_number' in df_main.columns:
            with_tracking = df_main['tracking_number'].notna().sum()
            print(f"\n🚚 Transport:")
            print(f"   - Avec numéro de suivi: {with_tracking}/{len(df_main)}")
            print(f"   - Sans numéro de suivi: {len(df_main) - with_tracking}/{len(df_main)}")
        
        # Avec/sans client
        if 'customer_name' in df_main.columns:
            with_customer = df_main['customer_name'].notna().sum()
            print(f"\n👥 Clients:")
            print(f"   - Avec client: {with_customer}/{len(df_main)}")
            print(f"   - Sans client: {len(df_main) - with_customer}/{len(df_main)}")
    
    if df_lines is not None and not df_lines.empty:
        print(f"\n🏷️ Produits:")
        if 'product_sku' in df_lines.columns:
            unique_products = df_lines['product_sku'].nunique()
            print(f"   - Produits distincts: {unique_products}")
        if 'quantity' in df_lines.columns:
            print(f"   - Quantité totale: {df_lines['quantity'].sum():.0f}")
        
        # Top produits
        if 'product_label' in df_lines.columns and 'quantity' in df_lines.columns:
            top_products = df_lines.groupby('product_label')['quantity'].sum().sort_values(ascending=False).head(10)
            if not top_products.empty:
                print(f"\n🏆 Top 10 produits:")
                for product, qty in top_products.items():
                    print(f"   - {product[:50]}: {qty:.0f} unités")
    
    print("="*60)

def show_examples(shipments: List[Dict[str, Any]], limit: int = 5):
    """
    Affiche des exemples de BL
    """
    if not shipments:
        return
    
    print(f"\n📋 Exemples des {limit} premiers BL:")
    print("-" * 80)
    
    for i, shipment in enumerate(shipments[:limit]):
        print(f"\n🔹 BL #{i+1}")
        print(f"   ID: {shipment.get('id')}")
        print(f"   Numéro commande: {shipment.get('order_number')}")
        print(f"   Référence externe: {shipment.get('external_reference')}")
        print(f"   Statut: {shipment.get('status')}")
        print(f"   Date création: {shipment.get('created')}")
        print(f"   Date livraison: {shipment.get('shipping_date')}")
        print(f"   Tracking: {shipment.get('tracking_number')}")
        
        # Client
        customer = shipment.get("customer", {})
        if customer:
            print(f"   Client: {customer.get('label')}")
        
        # Lignes
        line_items_data = shipment.get("line_items", {})
        edges = line_items_data.get("edges", []) if isinstance(line_items_data, dict) else []
        if edges:
            print(f"   Produits:")
            for edge in edges[:3]:
                line = edge.get("node", {})
                product = line.get("product", {})
                print(f"      - {product.get('label')}: {line.get('quantity')} x {product.get('sku')}")
            if len(edges) > 3:
                print(f"      ... et {len(edges) - 3} autres")

def update_invoices_with_delivery_notes():
    """
    Met à jour les factures avec les informations des BL
    """
    import psycopg2
    from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD
    
    print("\n" + "="*60)
    print("🔄 MISE À JOUR DES FACTURES AVEC LES BL")
    print("="*60)
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Ajouter les colonnes si elles n'existent pas
    cursor.execute("""
        ALTER TABLE invoices 
        ADD COLUMN IF NOT EXISTS bl_number TEXT,
        ADD COLUMN IF NOT EXISTS bl_status TEXT,
        ADD COLUMN IF NOT EXISTS shipping_date DATE,
        ADD COLUMN IF NOT EXISTS tracking_number TEXT
    """)
    conn.commit()
    
    # Récupérer les BL
    shipments = fetch_all_shipments_2026(page_size=100)
    
    if not shipments:
        print("❌ Aucun BL récupéré")
        return 0
    
    updated = 0
    for shipment in shipments:
        order_number = shipment.get('order_number')
        if not order_number:
            continue
        
        cursor.execute("""
            UPDATE invoices 
            SET bl_number = %s,
                bl_status = %s,
                shipping_date = %s,
                tracking_number = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE order_number = %s
            AND (bl_number IS NULL OR bl_number = '')
        """, (
            shipment.get('order_number'),
            shipment.get('status'),
            shipment.get('shipping_date'),
            shipment.get('tracking_number'),
            order_number
        ))
        updated += cursor.rowcount
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ {updated} factures mises à jour avec les BL")
    return updated

def main():
    """
    Fonction principale
    """
    print("\n" + "="*60)
    print("🚚 RÉCUPÉRATION DES BONS DE LIVRAISON 2026")
    print("="*60)
    
    # 1. Découvrir la structure correcte
    discover_correct_schema()
    
    # 2. Récupérer tous les BL de 2026
    shipments = fetch_all_shipments_2026(page_size=100)
    
    if not shipments:
        print("\n❌ Aucun bon de livraison trouvé pour 2026")
        print("   Vérifiez que:")
        print("   1. Votre token est valide")
        print("   2. Vous avez des bons de livraison dans Erplain")
        print("   3. L'API est activée sur votre abonnement")
        return
    
    # 3. Afficher les statistiques
    show_statistics(shipments)
    
    # 4. Afficher des exemples
    show_examples(shipments)
    
    # 5. Mettre à jour les factures
    update_invoices_with_delivery_notes()
    
    print("\n" + "="*60)
    print("✅ Récupération terminée!")
    print("="*60)
    print("\n📁 Fichiers générés:")
    print("   - delivery_notes_2026_complet.json (données brutes)")
    print("   - delivery_notes_2026.csv (tableau principal)")
    print("   - delivery_notes_lines_2026.csv (lignes de produits)")

if __name__ == "__main__":
    main()