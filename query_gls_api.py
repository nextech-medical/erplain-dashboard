# query_gls_api.py
"""Interroge l'API GLS pour vérifier les codes trouvés"""

import json
import requests
import os
from datetime import datetime
from config import GLS_BASE_URL, GLS_AUTH_BASE_URL, GLS_CLIENT_ID, GLS_CLIENT_SECRET

DATA_DIR = "data"
TRACKING_FILE = os.path.join(DATA_DIR, 'all_tracking_codes.json')

def get_gls_token():
    """Obtient un token GLS"""
    if not GLS_CLIENT_ID or not GLS_CLIENT_SECRET:
        print("⚠️ Configuration GLS manquante")
        return None
    
    url = f"{GLS_AUTH_BASE_URL}/oauth2/v2/token"
    data = {
        'grant_type': 'client_credentials',
        'client_id': GLS_CLIENT_ID,
        'client_secret': GLS_CLIENT_SECRET
    }
    
    try:
        response = requests.post(url, data=data, timeout=30)
        if response.status_code == 200:
            return response.json().get('access_token')
        else:
            print(f"❌ Erreur auth: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return None

def check_tracking_with_gls(tracking_code, token):
    """Vérifie un code avec l'API GLS"""
    url = f"{GLS_BASE_URL}/tracking/parceldetails"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(url, json={'TrackID': tracking_code}, headers=headers, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return {'error': 'not_found'}
        else:
            return {'error': f'HTTP {response.status_code}'}
    except Exception as e:
        return {'error': str(e)}

def main():
    print("\n" + "=" * 70)
    print("🔍 VÉRIFICATION DES CODES AVEC L'API GLS")
    print("=" * 70)
    
    # Charger les codes
    if not os.path.exists(TRACKING_FILE):
        print("❌ Aucune donnée. Exécutez d'abord: python extract_tracking_final.py")
        return
    
    with open(TRACKING_FILE, 'r', encoding='utf-8') as f:
        codes = json.load(f)
    
    if not codes:
        print("❌ Aucun code à vérifier")
        return
    
    # Obtenir le token GLS
    token = get_gls_token()
    if not token:
        print("\n⚠️ Impossible d'obtenir un token GLS")
        print("   Vérifiez votre configuration GLS dans .env.dev")
        return
    
    print(f"\n📊 {len(codes)} codes à vérifier\n")
    
    results = []
    for i, item in enumerate(codes[:50]):  # Limiter à 50 pour ne pas surcharger
        code = item['tracking_code']
        order_number = item['order_number']
        
        print(f"   Test {i+1}: {order_number} -> {code}...", end=" ")
        
        result = check_tracking_with_gls(code, token)
        
        if result and 'error' not in result:
            print("✅ TROUVÉ!")
            results.append({
                'order_number': order_number,
                'tracking_code': code,
                'gls_status': result.get('Status', 'unknown'),
                'gls_data': result
            })
        else:
            error = result.get('error', 'non trouvé') if result else 'erreur'
            print(f"❌ {error}")
    
    # Sauvegarder les résultats
    if results:
        output_file = f"gls_verification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n💾 Résultats sauvegardés: {output_file}")
    
    print("\n" + "=" * 70)
    print(f"✅ {len(results)} codes valides trouvés sur {min(50, len(codes))} testés")
    print("=" * 70)

if __name__ == "__main__":
    main()