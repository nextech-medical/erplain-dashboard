# fetch_gls_tracking_from_api.py
"""
Script pour récupérer les informations de suivi GLS via leur API
"""
import requests
import psycopg2
from datetime import datetime
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

# Configuration GLS (à ajouter dans config.py)
GLS_API_URL = "https://api.gls-group.eu"  # URL de l'API GLS
GLS_CLIENT_ID = "votre_client_id"
GLS_CLIENT_SECRET = "votre_client_secret"

def get_gls_access_token():
    """Récupère un token d'accès GLS"""
    auth_url = f"{GLS_API_URL}/oauth2/v2/token"
    
    data = {
        'grant_type': 'client_credentials',
        'client_id': GLS_CLIENT_ID,
        'client_secret': GLS_CLIENT_SECRET
    }
    
    response = requests.post(auth_url, data=data)
    
    if response.status_code == 200:
        return response.json().get('access_token')
    else:
        print(f"❌ Erreur GLS auth: {response.status_code}")
        return None

def get_gls_tracking_info(tracking_number):
    """Récupère les infos de suivi GLS pour un numéro"""
    token = get_gls_access_token()
    if not token:
        return None
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    url = f"{GLS_API_URL}/tracking/parceldetails"
    payload = {'TrackID': tracking_number}
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Erreur tracking {tracking_number}: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return None

def update_tracking_status_in_db():
    """Met à jour les statuts de livraison dans la base"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    # Récupérer les BL avec numéro de suivi GLS
    cursor.execute("""
        SELECT order_number, tracking_number 
        FROM delivery_notes 
        WHERE tracking_number IS NOT NULL 
        AND tracking_number != ''
        AND tracking_number LIKE 'GL%'
    """)
    
    bl_list = cursor.fetchall()
    print(f"📦 {len(bl_list)} BL avec numéro GLS à vérifier")
    
    updated = 0
    for order_number, tracking in bl_list:
        tracking_info = get_gls_tracking_info(tracking)
        
        if tracking_info:
            # Extraire le statut
            status = tracking_info.get('Status', '')
            events = tracking_info.get('Events', [])
            last_event = events[0] if events else {}
            
            cursor.execute("""
                UPDATE delivery_notes 
                SET gls_status = %s,
                    gls_last_event = %s,
                    gls_last_check = CURRENT_TIMESTAMP
                WHERE order_number = %s
            """, (
                status,
                last_event.get('Description', ''),
                order_number
            ))
            updated += cursor.rowcount
            print(f"   ✅ {order_number}: {status}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ {updated} BL mis à jour")
    return updated