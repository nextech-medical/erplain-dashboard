# gls_tracking_service.py
"""
Service pour interroger l'API GLS et mettre à jour les statuts
"""
import requests
import psycopg2
import json
from datetime import datetime
from config import GLS_API_URL, GLS_AUTH_URL, GLS_CLIENT_ID, GLS_CLIENT_SECRET, DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

class GLSTrackingService:
    def __init__(self):
        self.access_token = None
        self.token_expires_at = 0
    
    def get_access_token(self):
        """Récupère un token d'accès OAuth2 GLS"""
        if self.access_token and datetime.now().timestamp() < self.token_expires_at:
            return self.access_token
        
        url = f"{GLS_AUTH_URL}/oauth2/v2/token"
        
        data = {
            'grant_type': 'client_credentials',
            'client_id': GLS_CLIENT_ID,
            'client_secret': GLS_CLIENT_SECRET
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        try:
            response = requests.post(url, data=data, headers=headers, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                self.access_token = result.get('access_token')
                expires_in = result.get('expires_in', 3600)
                self.token_expires_at = datetime.now().timestamp() + expires_in - 300
                print(f"✅ Token GLS obtenu, expire dans {expires_in}s")
                return self.access_token
            else:
                print(f"❌ Erreur auth GLS: {response.status_code} - {response.text[:200]}")
                return None
                
        except Exception as e:
            print(f"❌ Erreur connexion GLS: {e}")
            return None
    
    def get_tracking_info(self, tracking_number):
        """
        Récupère les informations de suivi pour un numéro GLS
        """
        token = self.get_access_token()
        if not token:
            return None
        
        url = f"{GLS_API_URL}/tracking/parceldetails"
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        payload = {'TrackID': tracking_number}
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return {'error': 'not_found', 'tracking': tracking_number}
            else:
                print(f"⚠️ Erreur tracking {tracking_number}: {response.status_code}")
                return None
                
        except requests.exceptions.Timeout:
            print(f"⏱️ Timeout pour {tracking_number}")
            return None
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return None
    
    def parse_tracking_response(self, data, tracking_number):
        """
        Parse la réponse API GLS pour extraire les infos pertinentes
        """
        if not data or data.get('error'):
            return {
                'tracking_number': tracking_number,
                'status': 'not_found',
                'status_description': 'Numéro de suivi non trouvé',
                'last_event': None,
                'last_event_date': None,
                'estimated_delivery': None,
                'events': []
            }
        
        # Structure selon l'API GLS
        unit_items = data.get('UnitItems', [])
        if not unit_items:
            unit_items = data.get('UnitItems', [data]) if isinstance(data, dict) else []
        
        first_unit = unit_items[0] if unit_items else {}
        
        # Extraire les événements
        events = []
        raw_events = first_unit.get('Events', []) or first_unit.get('events', [])
        
        for event in raw_events:
            events.append({
                'code': event.get('Code') or event.get('code', ''),
                'description': event.get('Description') or event.get('description', ''),
                'date': event.get('EventDateTime') or event.get('eventDateTime') or event.get('date'),
                'location': event.get('Location') or event.get('location', '')
            })
        
        # Dernier événement
        last_event = events[0] if events else None
        
        # Statut
        status = first_unit.get('Status') or first_unit.get('status', '')
        if not status and last_event:
            status = 'in_transit'
        
        return {
            'tracking_number': tracking_number,
            'status': status,
            'status_description': last_event.get('description', '') if last_event else '',
            'last_event': last_event.get('description') if last_event else None,
            'last_event_date': last_event.get('date') if last_event else None,
            'estimated_delivery': first_unit.get('EstimatedDeliveryDate'),
            'events': events
        }
    
    def update_tracking_status(self, tracking_number):
        """
        Met à jour le statut d'un seul numéro de suivi
        """
        data = self.get_tracking_info(tracking_number)
        return self.parse_tracking_response(data, tracking_number)
    
    def update_all_pending_tracking(self, limit=100):
        """
        Met à jour tous les numéros de suivi en attente
        """
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        
        # Récupérer les numéros GLS à vérifier
        cursor.execute("""
            SELECT order_number, tracking_number
            FROM gls_tracking
            WHERE (status IS NULL OR status = '')
            OR last_sync < NOW() - INTERVAL '1 day'
            LIMIT %s
        """, (limit,))
        
        tracking_list = cursor.fetchall()
        print(f"📦 {len(tracking_list)} numéros GLS à vérifier")
        
        updated = 0
        for order_number, tracking in tracking_list:
            print(f"   🔍 Vérification {order_number} ({tracking})...")
            
            info = self.update_tracking_status(tracking)
            
            if info and info.get('status') != 'not_found':
                cursor.execute("""
                    UPDATE gls_tracking 
                    SET status = %s,
                        last_event = %s,
                        last_event_date = %s,
                        estimated_delivery = %s,
                        events = %s,
                        last_sync = CURRENT_TIMESTAMP
                    WHERE tracking_number = %s
                """, (
                    info.get('status'),
                    info.get('last_event'),
                    info.get('last_event_date'),
                    info.get('estimated_delivery'),
                    json.dumps(info.get('events', [])),
                    tracking
                ))
                updated += cursor.rowcount
                
                # Mettre à jour delivery_notes
                cursor.execute("""
                    UPDATE delivery_notes 
                    SET gls_status = %s, gls_last_check = CURRENT_TIMESTAMP
                    WHERE tracking_number = %s
                """, (info.get('status'), tracking))
                
                # Mettre à jour invoices
                cursor.execute("""
                    UPDATE invoices 
                    SET gls_tracking_status = %s, gls_tracking_updated_at = CURRENT_TIMESTAMP
                    WHERE gls_tracking_number = %s
                """, (info.get('status'), tracking))
                
                print(f"      ✅ Statut: {info.get('status')}")
            else:
                print(f"      ⚠️ Non trouvé ou erreur")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ {updated} statuts mis à jour")
        return updated


def sync_gls_tracking_status(limit=100):
    """Synchronisation des statuts GLS"""
    print("\n" + "=" * 70)
    print("🔄 SYNCHRONISATION DES STATUTS GLS")
    print("=" * 70)
    
    service = GLSTrackingService()
    return service.update_all_pending_tracking(limit)


if __name__ == "__main__":
    sync_gls_tracking_status()