#!/usr/bin/env python3
# extract_tracking.py - Extraction automatique des numéros de suivi GLS

import json
import re
import requests
import os
import sys
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# Configuration
ERPLAIN_TOKEN = "437b4d61de0d0be070992852610f685f"  # Votre token
ERPLAIN_ENDPOINT = "https://app.erplain.net/public-api/graphql/endpoint"
DATA_DIR = "data"

def ensure_dir():
    """Crée le dossier data s'il n'existe pas"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def fetch_shipping_orders(days_back: int = 30) -> List[Dict]:
    """
    Récupère les bons de livraison depuis ERPLAIN
    """
    start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    
    print(f"\n📥 Récupération des BL depuis {start_date}")
    
    all_orders = []
    page = 1
    page_size = 50
    
    headers = {
        "Authorization": f"Bearer {ERPLAIN_TOKEN}",
        "Content-Type": "application/json"
    }
    
    while True:
        query = f"""
        {{
          ShippingOrders(
            page: {page}
            page_size: {page_size}
            sort: {{ by: "shipping_date", direction: "DESC" }}
            shipping_date__Ge: "{start_date}"
          ) {{
            edges {{
              node {{
                id
                order_number
                label
                external_reference
                shipping_date
                shipping_order_status
                notes
              }}
            }}
          }}
        }}
        """
        
        try:
            response = requests.post(
                ERPLAIN_ENDPOINT,
                json={"query": query},
                headers=headers,
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"   ❌ Erreur HTTP {response.status_code}")
                break
            
            data = response.json()
            
            if "errors" in data:
                print(f"   ❌ GraphQL error: {data['errors'][0].get('message', 'Unknown')[:100]}")
                break
            
            edges = data.get("data", {}).get("ShippingOrders", {}).get("edges", [])
            
            if not edges:
                break
            
            for edge in edges:
                node = edge.get("node")
                if node and node.get("order_number"):
                    all_orders.append(node)
            
            print(f"   Page {page}: {len(edges)} BL (total: {len(all_orders)})")
            
            if len(edges) < page_size:
                break
                
            page += 1
            
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
            break
    
    return all_orders

def extract_gls_tracking(notes: str) -> Optional[str]:
    """
    Extrait le numéro de suivi GLS des notes HTML
    """
    if not notes:
        return None
    
    # Nettoyer le HTML
    clean = re.sub(r'<[^>]+>', ' ', str(notes))
    clean = re.sub(r'&nbsp;|&amp;|&lt;|&gt;|&quot;', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean)
    
    # Patterns pour les numéros GLS
    patterns = [
        # GLS standard: GL + 10-14 chiffres + optionnel FR
        r'(GL\d{10,14}FR?)',
        r'(gl\d{10,14}fr?)',
        
        # Suivi explicite
        r'[Ss]uivi\s*:?\s*([A-Z0-9]{10,20})',
        r'[Tt]racking\s*:?\s*([A-Z0-9]{10,20})',
        r'[Nn]°\s*de\s*suivi\s*:?\s*([A-Z0-9]{10,20})',
        
        # GLS dans le texte
        r'GLS\s*:?\s*([A-Z0-9]{10,20})',
        
        # Numéro simple (12-16 chiffres)
        r'\b(\d{12,16})\b',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, clean, re.IGNORECASE)
        if match:
            tracking = match.group(1).upper().strip()
            # Valider le format
            if len(tracking) >= 12:
                return tracking
    
    return None

def process_orders(orders: List[Dict]) -> List[Dict]:
    """
    Traite tous les BL pour extraire les numéros de suivi
    """
    print("\n🔍 Extraction des numéros de suivi...")
    print("-" * 50)
    
    results = []
    found = 0
    
    for order in orders:
        order_number = order.get('order_number')
        notes = order.get('notes', '')
        
        tracking = extract_gls_tracking(notes)
        
        if tracking:
            found += 1
            result = {
                'order_number': order_number,
                'tracking_number': tracking,
                'external_reference': order.get('external_reference'),
                'label': order.get('label'),
                'shipping_date': order.get('shipping_date'),
                'status': order.get('shipping_order_status'),
                'extracted_at': datetime.now().isoformat()
            }
            results.append(result)
            
            if found <= 20:
                print(f"   ✅ {order_number} → {tracking}")
    
    print(f"\n📊 Résultat: {found}/{len(orders)} numéros trouvés")
    return results

def save_results(results: List[Dict]):
    """
    Sauvegarde les résultats
    """
    ensure_dir()
    
    # Sauvegarde JSON
    output_file = os.path.join(DATA_DIR, f'tracking_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n💾 Sauvegardé: {output_file}")
    
    # Sauvegarde permanente
    permanent_file = os.path.join(DATA_DIR, 'tracking_all.json')
    
    existing = []
    if os.path.exists(permanent_file):
        with open(permanent_file, 'r', encoding='utf-8') as f:
            existing = json.load(f)
    
    # Mettre à jour (par order_number)
    existing_by_order = {item['order_number']: item for item in existing}
    for item in results:
        existing_by_order[item['order_number']] = item
    
    with open(permanent_file, 'w', encoding='utf-8') as f:
        json.dump(list(existing_by_order.values()), f, indent=2, ensure_ascii=False, default=str)
    
    print(f"💾 Permanent: {permanent_file} ({len(existing_by_order)} total)")

def display_summary(results: List[Dict]):
    """
    Affiche un résumé
    """
    print("\n" + "=" * 70)
    print("📋 RÉCAPITULATIF DES NUMÉROS DE SUIVI")
    print("=" * 70)
    
    if not results:
        print("   Aucun numéro de suivi trouvé")
        return
    
    print(f"\n{'BL':<20} {'Numéro de suivi':<25} {'Date expédition':<12}")
    print("-" * 70)
    
    for item in results[:30]:
        shipping_date = item.get('shipping_date', '')[:10] if item.get('shipping_date') else 'N/A'
        print(f"{item['order_number']:<20} {item['tracking_number']:<25} {shipping_date:<12}")
    
    if len(results) > 30:
        print(f"\n... et {len(results) - 30} autres")

def run_once():
    """
    Exécution unique
    """
    print("\n" + "=" * 60)
    print(f"🚀 EXTRACTION GLS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 1. Récupérer les BL
    orders = fetch_shipping_orders()
    
    if not orders:
        print("\n❌ Aucun BL récupéré")
        print("   Vérifiez:")
        print("   1. Votre token ERPLAIN est valide")
        print("   2. Vous avez des BL dans la période")
        return
    
    # 2. Extraire les tracking
    results = process_orders(orders)
    
    # 3. Sauvegarder
    if results:
        save_results(results)
    
    # 4. Afficher
    display_summary(results)
    
    return results

def run_daemon(interval_minutes: int = 30):
    """
    Exécution continue
    """
    print(f"\n🔄 Mode démon - Vérification toutes les {interval_minutes} minutes")
    print("   Appuyez sur Ctrl+C pour arrêter\n")
    
    while True:
        try:
            run_once()
            print(f"\n💤 Attente de {interval_minutes} minutes...")
            time.sleep(interval_minutes * 60)
        except KeyboardInterrupt:
            print("\n🛑 Service arrêté")
            break
        except Exception as e:
            print(f"\n❌ Erreur: {e}")
            time.sleep(60)

def show_tracking():
    """
    Affiche tous les tracking sauvegardés
    """
    permanent_file = os.path.join(DATA_DIR, 'tracking_all.json')
    
    if not os.path.exists(permanent_file):
        print("❌ Aucune donnée trouvée")
        print("   Exécutez d'abord: python extract_tracking.py")
        return
    
    with open(permanent_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("\n" + "=" * 70)
    print(f"📦 TOUS LES NUMÉROS DE SUIVI ({len(data)})")
    print("=" * 70)
    
    # Grouper par statut (si disponible)
    with_tracking = [d for d in data if d.get('tracking_number')]
    
    print(f"\n{'BL':<20} {'Numéro GLS':<25} {'Date':<12}")
    print("-" * 70)
    
    for item in with_tracking[:50]:
        date = item.get('shipping_date', '')[:10] if item.get('shipping_date') else 'N/A'
        print(f"{item['order_number']:<20} {item['tracking_number']:<25} {date:<12}")

def main():
    """
    Point d'entrée
    """
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        
        if cmd in ['--daemon', '-d']:
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else INTERVAL_MINUTES
            run_daemon(interval)
        elif cmd in ['--show', '-s']:
            show_tracking()
        elif cmd in ['--help', '-h']:
            print(__doc__)
        else:
            print(f"Commande inconnue: {cmd}")
            print("Utilisation: python extract_tracking.py [--daemon] [--show]")
    else:
        run_once()

if __name__ == "__main__":
    main()