#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AUTO TRACKING GLS - Récupération automatique des numéros de suivi
A utiliser avec votre projet existant
"""

import os
import re
import json
import requests
import sqlite3
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv

# ============================================================
# CHARGEMENT DE LA CONFIGURATION
# ============================================================

# Charger le bon fichier .env
env_file = os.getenv('ENV_FILE', '.env.dev')
if os.path.exists(env_file):
    load_dotenv(env_file)
    print(f"✅ Configuration chargée depuis {env_file}")
else:
    load_dotenv('.env')
    print("✅ Configuration chargée depuis .env")

# Configuration ERPLAIN
ERPLAIN_TOKEN = os.getenv('ERPLAIN_TOKEN')
ERPLAIN_ENDPOINT = os.getenv('ERPLAIN_ENDPOINT', 'https://app.erplain.net/public-api/graphql/endpoint')
ERPLAIN_SHIPPING_FETCH_LIMIT = int(os.getenv('ERPLAIN_SHIPPING_FETCH_LIMIT', 10))

# Configuration GLS
GLS_BASE_URL = os.getenv('GLS_BASE_URL', 'https://api-sandbox.gls-group.net/shipit-farm/v1/backend/rs')
GLS_AUTH_BASE_URL = os.getenv('GLS_AUTH_BASE_URL', 'https://api-sandbox.gls-group.net')
GLS_CLIENT_ID = os.getenv('GLS_CLIENT_ID')
GLS_CLIENT_SECRET = os.getenv('GLS_CLIENT_SECRET')
GLS_CONTACT_ID_MONO = os.getenv('GLS_CONTACT_ID_MONO', '250aaaZAtD')
GLS_CONTACT_ID_MULTI = os.getenv('GLS_CONTACT_ID_MULTI', '250aaaZAw3')

# Configuration
UI_HISTORY_DAYS = int(os.getenv('UI_HISTORY_DAYS', 7))
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
TRACKING_FILE = os.path.join(DATA_DIR, 'gls_tracking.json')
TRACKING_DB = os.path.join(DATA_DIR, 'gls_tracking.db')

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# 1. FONCTIONS DE BASE
# ============================================================

def ensure_data_dir():
    """Crée le dossier data s'il n'existe pas"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"📁 Dossier créé: {DATA_DIR}")

def load_json_file(filepath: str) -> List[Dict]:
    """Charge un fichier JSON"""
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Erreur lecture {filepath}: {e}")
    return []

def save_json_file(filepath: str, data: List[Dict]):
    """Sauvegarde en JSON"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

# ============================================================
# 2. RÉCUPÉRATION DES BL DEPUIS ERPLAIN
# ============================================================

def fetch_delivery_notes_from_erplain(days_back: int = UI_HISTORY_DAYS) -> List[Dict]:
    """
    Récupère les bons de livraison depuis ERPLAIN
    """
    start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    
    print(f"\n📥 Récupération des BL ERPLAIN depuis le {start_date}")
    print("-" * 50)
    
    all_notes = []
    page = 1
    page_size = min(ERPLAIN_SHIPPING_FETCH_LIMIT, 100)
    
    headers = {
        "Authorization": f"Bearer {ERPLAIN_TOKEN}",
        "Content-Type": "application/json"
    }
    
    while True:
        query = f"""
        {{
          ShippingOrders(
            page: {page}, 
            page_size: {page_size},
            sort: {{ by: "shipping_date", direction: "DESC" }},
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
                created
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
                print(f"   ❌ Erreur GraphQL: {data['errors'][0].get('message', 'Unknown')[:100]}")
                break
            
            edges = data.get("data", {}).get("ShippingOrders", {}).get("edges", [])
            
            if not edges:
                print(f"   ✅ Plus de BL à la page {page}")
                break
            
            for edge in edges:
                node = edge.get("node")
                if node and node.get("order_number"):
                    all_notes.append(node)
            
            print(f"   Page {page}: {len(edges)} BL (total: {len(all_notes)})")
            
            if len(edges) < page_size:
                break
                
            page += 1
            
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
            break
    
    print(f"\n📊 Total BL récupérés: {len(all_notes)}")
    return all_notes

# ============================================================
# 3. EXTRACTION DES NUMÉROS DE SUIVI
# ============================================================

def extract_gls_tracking_from_text(text: str) -> Optional[str]:
    """
    Extrait un numéro de suivi GLS depuis un texte
    """
    if not text:
        return None
    
    # Nettoyage
    clean = re.sub(r'<[^>]+>', ' ', str(text))
    clean = re.sub(r'&[a-z]+;', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean)
    
    # Patterns pour GLS (par ordre de priorité)
    patterns = [
        # Format GLS standard: GL + 10-14 chiffres + optionnel FR
        r'\b(GL\d{10,14}FR?)\b',
        r'\b(gl\d{10,14}fr?)\b',
        
        # Suivi explicite
        r'[Ss]uivi[\s:]+([A-Z0-9]{10,20})',
        r'[Tt]racking[\s:]+([A-Z0-9]{10,20})',
        r'[Nn]°\s*de\s*suivi[\s:]+([A-Z0-9]{10,20})',
        r'[Nn]uméro\s*de\s*suivi[\s:]+([A-Z0-9]{10,20})',
        
        # GLS explicite
        r'GLS[\s:]+([A-Z0-9]{10,20})',
        r'[Pp]arcel[\s:]+([A-Z0-9]{10,20})',
        
        # Format numérique seul (12-16 chiffres)
        r'\b(\d{12,16})\b',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, clean, re.IGNORECASE)
        if match:
            tracking = match.group(1) if match.groups() else match.group(0)
            tracking = tracking.upper().strip()
            
            # Validation
            if tracking.startswith('GL') and len(tracking) >= 12:
                return tracking
            if len(re.findall(r'\d', tracking)) >= 12:
                # Ajouter préfixe GL si nécessaire
                return f"GL{tracking}" if not tracking.startswith('GL') else tracking
    
    return None

def extract_all_tracking_numbers(delivery_notes: List[Dict]) -> List[Dict]:
    """
    Extrait tous les numéros de suivi des BL
    """
    print("\n🔍 Extraction des numéros de suivi GLS...")
    print("-" * 50)
    
    tracking_data = []
    found_count = 0
    
    for note in delivery_notes:
        order_number = note.get('order_number')
        
        # Extraire depuis les notes
        tracking = extract_gls_tracking_from_text(note.get('notes', ''))
        
        if tracking:
            found_count += 1
            tracking_data.append({
                'order_number': order_number,
                'tracking_number': tracking,
                'external_reference': note.get('external_reference'),
                'label': note.get('label'),
                'shipping_date': note.get('shipping_date'),
                'status': note.get('shipping_order_status', 'shipped'),
                'extracted_at': datetime.now().isoformat(),
                'source': 'notes'
            })
            
            if found_count <= 20:
                print(f"   ✅ {order_number} → {tracking}")
    
    print(f"\n📊 Résultat: {found_count}/{len(delivery_notes)} numéros trouvés")
    return tracking_data

# ============================================================
# 4. STOCKAGE
# ============================================================

def init_sqlite_db():
    """Initialise la base SQLite"""
    ensure_data_dir()
    
    conn = sqlite3.connect(TRACKING_DB)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gls_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE,
            tracking_number TEXT,
            external_reference TEXT,
            label TEXT,
            shipping_date TEXT,
            status TEXT,
            last_event TEXT,
            last_event_date TEXT,
            estimated_delivery TEXT,
            source TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tracking_number 
        ON gls_tracking(tracking_number)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_order_number 
        ON gls_tracking(order_number)
    """)
    
    conn.commit()
    conn.close()
    
    print("✅ Base SQLite initialisée")

def save_tracking_to_sqlite(tracking_data: List[Dict]) -> int:
    """Sauvegarde les tracking dans SQLite"""
    if not tracking_data:
        return 0
    
    conn = sqlite3.connect(TRACKING_DB)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    saved = 0
    for item in tracking_data:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO gls_tracking 
                (order_number, tracking_number, external_reference, label, 
                 shipping_date, status, source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(
                    (SELECT created_at FROM gls_tracking WHERE order_number = ?), ?
                ), ?)
            """, (
                item['order_number'],
                item['tracking_number'],
                item.get('external_reference'),
                item.get('label'),
                item.get('shipping_date'),
                item.get('status', 'shipped'),
                item.get('source', 'auto'),
                item['order_number'],
                now,
                now
            ))
            saved += 1
        except Exception as e:
            logger.error(f"Erreur {item.get('order_number')}: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"✅ {saved} numéros sauvegardés dans SQLite")
    return saved

def save_tracking_to_json(tracking_data: List[Dict]):
    """Sauvegarde les tracking dans JSON"""
    ensure_data_dir()
    
    # Charger l'existant
    existing = load_json_file(TRACKING_FILE)
    existing_by_order = {item['order_number']: item for item in existing}
    
    # Mettre à jour
    for item in tracking_data:
        existing_by_order[item['order_number']] = item
    
    # Sauvegarder
    save_json_file(TRACKING_FILE, list(existing_by_order.values()))
    print(f"✅ {len(tracking_data)} numéros sauvegardés dans JSON")

# ============================================================
# 5. API GLS - AUTHENTIFICATION ET STATUTS
# ============================================================

class GLSAPIClient:
    """Client pour l'API GLS"""
    
    def __init__(self):
        self.access_token = None
        self.token_expires_at = 0
        self.session = requests.Session()
    
    def get_token(self) -> Optional[str]:
        """Obtient un token OAuth2"""
        if not GLS_CLIENT_ID or not GLS_CLIENT_SECRET:
            return None
        
        now = datetime.now().timestamp()
        if self.access_token and now < self.token_expires_at:
            return self.access_token
        
        url = f"{GLS_AUTH_BASE_URL}/oauth2/v2/token"
        
        data = {
            'grant_type': 'client_credentials',
            'client_id': GLS_CLIENT_ID,
            'client_secret': GLS_CLIENT_SECRET
        }
        
        try:
            response = self.session.post(url, data=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                self.access_token = result.get('access_token')
                expires_in = result.get('expires_in', 3600)
                self.token_expires_at = now + expires_in - 300
                print("   ✅ Token GLS obtenu")
                return self.access_token
            else:
                print(f"   ⚠️ Erreur auth GLS: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"   ⚠️ Erreur connexion GLS: {e}")
            return None
    
    def get_tracking_status(self, tracking_number: str) -> Optional[Dict]:
        """Récupère le statut d'un colis"""
        token = self.get_token()
        if not token:
            return None
        
        url = f"{GLS_BASE_URL}/tracking/parceldetails"
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = self.session.post(
                url,
                json={'TrackID': tracking_number},
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                unit_items = data.get('UnitItems', [])
                
                if unit_items:
                    unit = unit_items[0]
                    events = unit.get('Events', [])
                    last_event = events[0] if events else {}
                    
                    # Mapping des statuts
                    status_map = {
                        'DELIVERED': 'delivered',
                        'IN_TRANSIT': 'in_transit',
                        'PENDING': 'pending',
                        'EXCEPTION': 'exception',
                        'CANCELLED': 'cancelled'
                    }
                    raw_status = unit.get('Status', 'unknown')
                    
                    return {
                        'tracking_number': tracking_number,
                        'status': status_map.get(raw_status, raw_status.lower()),
                        'last_event': last_event.get('Description', ''),
                        'last_event_date': last_event.get('EventDateTime'),
                        'estimated_delivery': unit.get('EstimatedDeliveryDate')
                    }
                    
            elif response.status_code == 404:
                return {'tracking_number': tracking_number, 'status': 'not_found'}
                
        except Exception as e:
            logger.error(f"Erreur API {tracking_number}: {e}")
        
        return None

def update_tracking_statuses(limit: int = 100) -> int:
    """Met à jour les statuts des colis"""
    print("\n🔄 Mise à jour des statuts GLS...")
    print("-" * 50)
    
    if not GLS_CLIENT_ID or not GLS_CLIENT_SECRET:
        print("   ⚠️ API GLS non configurée (GLS_CLIENT_ID manquant)")
        return 0
    
    # Récupérer les tracking à mettre à jour
    conn = sqlite3.connect(TRACKING_DB)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT order_number, tracking_number, updated_at
        FROM gls_tracking
        WHERE tracking_number IS NOT NULL
        ORDER BY 
            CASE WHEN status IS NULL THEN 0 ELSE 1 END,
            updated_at ASC
        LIMIT ?
    """, (limit,))
    
    to_update = cursor.fetchall()
    print(f"📦 {len(to_update)} statuts à vérifier")
    
    if not to_update:
        conn.close()
        return 0
    
    client = GLSAPIClient()
    updated = 0
    
    for order_number, tracking_number, _ in to_update:
        print(f"   🔍 {order_number} ({tracking_number})...", end=" ")
        
        status_info = client.get_tracking_status(tracking_number)
        
        if status_info and status_info.get('status') != 'not_found':
            cursor.execute("""
                UPDATE gls_tracking 
                SET status = ?,
                    last_event = ?,
                    last_event_date = ?,
                    estimated_delivery = ?,
                    updated_at = ?
                WHERE order_number = ?
            """, (
                status_info.get('status'),
                status_info.get('last_event'),
                status_info.get('last_event_date'),
                status_info.get('estimated_delivery'),
                datetime.now().isoformat(),
                order_number
            ))
            updated += 1
            print(f"✅ {status_info.get('status')}")
        else:
            print("❌ non trouvé")
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ {updated} statuts mis à jour")
    return updated

# ============================================================
# 6. SYNCHRONISATION COMPLÈTE
# ============================================================

def sync_all(update_status: bool = True) -> Dict:
    """
    Synchronisation complète
    """
    print("\n" + "=" * 60)
    print(f"🚀 SYNC GLS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    result = {
        'bl_processed': 0,
        'tracking_found': 0,
        'saved': 0,
        'status_updated': 0
    }
    
    # 1. Initialiser la base
    init_sqlite_db()
    
    # 2. Récupérer les BL
    delivery_notes = fetch_delivery_notes_from_erplain()
    result['bl_processed'] = len(delivery_notes)
    
    if not delivery_notes:
        print("\n⚠️ Aucun BL récent trouvé")
        return result
    
    # 3. Extraire les tracking
    tracking_data = extract_all_tracking_numbers(delivery_notes)
    result['tracking_found'] = len(tracking_data)
    
    # 4. Sauvegarder
    if tracking_data:
        result['saved'] = save_tracking_to_sqlite(tracking_data)
        save_tracking_to_json(tracking_data)
    
    # 5. Mettre à jour les statuts
    if update_status and GLS_CLIENT_ID:
        result['status_updated'] = update_tracking_statuses()
    
    # Résumé
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DE LA SYNCHRONISATION")
    print("=" * 60)
    print(f"   📦 BL analysés: {result['bl_processed']}")
    print(f"   🏷️ Numéros trouvés: {result['tracking_found']}")
    print(f"   💾 Numéros sauvegardés: {result['saved']}")
    print(f"   🔄 Statuts mis à jour: {result['status_updated']}")
    print("=" * 60)
    
    return result

# ============================================================
# 7. COMMANDES UTILITAIRES
# ============================================================

def show_tracking_list():
    """Affiche la liste des tracking"""
    conn = sqlite3.connect(TRACKING_DB)
    
    print("\n" + "=" * 80)
    print("📋 LISTE DES NUMÉROS DE SUIVI GLS")
    print("=" * 80)
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT order_number, tracking_number, status, updated_at
        FROM gls_tracking
        WHERE tracking_number IS NOT NULL
        ORDER BY updated_at DESC
        LIMIT 50
    """)
    
    results = cursor.fetchall()
    conn.close()
    
    if results:
        print(f"\n{'BL':<20} {'Tracking GLS':<25} {'Statut':<15} {'Dernière mise à jour'}")
        print("-" * 80)
        for row in results:
            status_display = row[2] if row[2] else 'en attente'
            print(f"{row[0]:<20} {row[1]:<25} {status_display:<15} {row[3][:19] if row[3] else 'N/A'}")
    else:
        print("\n   Aucun numéro de suivi trouvé")
        print("   Lancez d'abord: python auto_tracking.py")

def show_statistics():
    """Affiche les statistiques"""
    conn = sqlite3.connect(TRACKING_DB)
    cursor = conn.cursor()
    
    print("\n" + "=" * 60)
    print("📊 STATISTIQUES GLS")
    print("=" * 60)
    
    cursor.execute("SELECT COUNT(*) FROM gls_tracking WHERE tracking_number IS NOT NULL")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM gls_tracking WHERE status = 'delivered'")
    delivered = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM gls_tracking WHERE status = 'in_transit'")
    in_transit = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM gls_tracking WHERE status IS NULL OR status = ''")
    pending = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"\n   📦 Total tracking: {total}")
    print(f"   ✅ Livrés: {delivered}")
    print(f"   🚚 En transit: {in_transit}")
    print(f"   ⏳ En attente: {pending}")
    print("=" * 60)

def run_daemon(interval_hours: int = 2):
    """Exécute le script en continu"""
    print(f"\n🔄 Démarrage du service GLS (intervalle: {interval_hours}h)")
    print("   Appuyez sur Ctrl+C pour arrêter\n")
    
    while True:
        try:
            sync_all(update_status=True)
            print(f"\n💤 Attente de {interval_hours} heures...")
            time.sleep(interval_hours * 3600)
        except KeyboardInterrupt:
            print("\n🛑 Service arrêté")
            break
        except Exception as e:
            print(f"\n❌ Erreur: {e}")
            time.sleep(300)

# ============================================================
# 8. MAIN
# ============================================================

def main():
    """Point d'entrée principal"""
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == '--sync' or command == 'sync':
            sync_all(update_status=True)
        elif command == '--status' or command == 'status':
            update_tracking_statuses()
        elif command == '--list' or command == 'list':
            show_tracking_list()
        elif command == '--stats' or command == 'stats':
            show_statistics()
        elif command == '--daemon' or command == 'daemon':
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 2
            run_daemon(interval)
        elif command == '--help' or command == 'help':
            print_help()
        else:
            print(f"❌ Commande inconnue: {command}")
            print_help()
    else:
        sync_all(update_status=True)


def print_help():
    """Affiche l'aide"""
    print("""
UTILISATION
===========

  python auto_tracking.py                    # Synchronisation complète
  python auto_tracking.py --sync             # Synchronisation complète
  python auto_tracking.py --status           # Mise à jour des statuts uniquement
  python auto_tracking.py --list             # Liste des tracking
  python auto_tracking.py --stats            # Statistiques
  python auto_tracking.py --daemon [heures]  # Mode continu (défaut: 2h)
  python auto_tracking.py --help             # Cette aide

EXEMPLES
========

  # Exécution unique
  python auto_tracking.py --sync

  # Mise à jour des statuts seulement
  python auto_tracking.py --status

  # Mode daemon (toutes les 2 heures)
  python auto_tracking.py --daemon

  # Mode daemon avec intervalle personnalisé
  python auto_tracking.py --daemon 4

  # Voir la liste des tracking
  python auto_tracking.py --list

  # Voir les statistiques
  python auto_tracking.py --stats
""")


if __name__ == "__main__":
    main()