# fetch_delivery_notes.py - Version CORRIGÉE
import requests
import json
import csv
import re
from datetime import datetime
from config import API_URL, BEARER_TOKEN

YEAR_FILTER = 2026

headers = {
    "Authorization": f"Bearer {BEARER_TOKEN}",
    "Content-Type": "application/json"
}

def extraire_numero_suivi_gls(notes_html):
    """Extrait le numéro de suivi GLS depuis les notes internes"""
    if not notes_html or not isinstance(notes_html, str):
        return None
    
    # Nettoyer le HTML
    notes_clean = re.sub(r'<[^>]+>', ' ', notes_html)
    notes_clean = re.sub(r'&[a-z]+;', ' ', notes_clean)
    notes_clean = re.sub(r'\s+', ' ', notes_clean).strip()
    
    if not notes_clean:
        return None
    
    # Patterns pour différents formats de tracking
    patterns = [
        # GLS standard (GL + chiffres)
        r'\b(GL\d{10,14}FR?)\b',
        # Numéros longs (comme 26140097200012)
        r'\b(\d{14,16})\b',
        # Numéros moyens (comme 20005535800010)
        r'\b(\d{12,16})\b',
        # Codes 00KTxxx
        r'\b(00[A-Z0-9]{4,10})\b',
        # Autres formats
        r'\b([A-Z0-9]{8,16})\b',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, notes_clean, re.IGNORECASE)
        if match:
            resultat = match.group(1) if match.groups() else match.group(0)
            resultat = resultat.upper().strip()
            if len(resultat) >= 8:  # Au moins 8 caractères
                return resultat
    return None

def fetch_all_delivery_notes():
    """Récupère tous les bons de livraison depuis l'API Erplain"""
    all_notes = []
    page = 1
    page_size = 100
    
    print("=" * 70)
    print("📦 RÉCUPÉRATION DES BONS DE LIVRAISON")
    print("=" * 70)
    
    while True:
        print(f"\n📥 Page {page}...")
        
        query = f"""
        {{
          ShippingOrders(
            page: {page}
            page_size: {page_size}
            sort: {{ by: "shipping_date", direction: "DESC" }}
          ) {{
            edges {{
              node {{
                id
                order_number
                external_reference
                shipping_date
                shipping_order_status
                created
                notes
                internal_notes
              }}
            }}
          }}
        }}
        """
        
        try:
            response = requests.post(API_URL, json={"query": query}, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()
            
            if "errors" in data:
                print(f"❌ Erreur GraphQL: {data['errors']}")
                break
            
            shipping_orders = data.get("data", {}).get("ShippingOrders", {})
            edges_data = shipping_orders.get("edges", {})
            
            nodes = []
            if isinstance(edges_data, dict):
                nodes = edges_data.get("node", [])
            elif isinstance(edges_data, list):
                for edge in edges_data:
                    if isinstance(edge, dict):
                        node = edge.get("node")
                        if node:
                            nodes.append(node)
            
            if not nodes:
                print("✅ Plus de BL à récupérer")
                break
            
            print(f"  📊 {len(nodes)} BL récupérés")
            all_notes.extend(nodes)
            
            if len(nodes) < page_size:
                print("✅ Dernière page")
                break
            
            page += 1
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            break
    
    return all_notes

def safe_str(value):
    """Convertit une valeur en string de façon sûre"""
    if value is None:
        return ""
    return str(value)

def main():
    # Récupérer tous les BL
    all_notes = fetch_all_delivery_notes()
    
    print(f"\n📊 Total BL récupérés: {len(all_notes)}")
    
    # Supprimer les doublons
    unique_notes = {}
    for note in all_notes:
        order_number = note.get("order_number")
        if order_number and order_number not in unique_notes:
            unique_notes[order_number] = note
    
    final_notes = list(unique_notes.values())
    print(f"📊 Après dédoublonnage: {len(final_notes)}")
    
    # Extraire les numéros de suivi
    print("\n" + "=" * 70)
    print("🔍 EXTRACTION DES NUMÉROS DE SUIVI GLS")
    print("=" * 70)
    
    tracking_found = 0
    
    for note in final_notes:
        order_number = note.get("order_number")
        # Récupérer les notes de façon sécurisée
        internal_notes = note.get("internal_notes")
        if internal_notes is None:
            internal_notes = ""
        regular_notes = note.get("notes")
        if regular_notes is None:
            regular_notes = ""
        
        tracking = None
        
        # Chercher d'abord dans internal_notes
        if internal_notes:
            tracking = extraire_numero_suivi_gls(internal_notes)
        
        # Si pas trouvé, chercher dans notes
        if not tracking and regular_notes:
            tracking = extraire_numero_suivi_gls(regular_notes)
        
        note["tracking_gls"] = tracking
        
        if tracking:
            tracking_found += 1
            if tracking_found <= 50:
                print(f"✅ {order_number} → {tracking}")
        else:
            if tracking_found < 10 and (internal_notes or regular_notes):
                preview = re.sub(r'<[^>]+>', ' ', internal_notes if internal_notes else regular_notes)[:50]
                if preview.strip():
                    print(f"❌ {order_number} → non trouvé: '{preview}'")
    
    # Sauvegarde JSON
    json_file = f"delivery_notes_{YEAR_FILTER}.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(final_notes, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n💾 JSON sauvegardé: {json_file}")
    
    # Sauvegarde CSV avec gestion sécurisée
    csv_file = f"delivery_notes_{YEAR_FILTER}.csv"
    with open(csv_file, "w", newline="", encoding="utf-8-sig") as csvfile:
        fieldnames = ["order_number", "external_reference", "shipping_date", 
                      "shipping_order_status", "tracking_gls", "internal_notes_preview"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for note in final_notes:
            internal = note.get("internal_notes")
            if internal is None:
                internal = ""
            internal_preview = re.sub(r'<[^>]+>', ' ', internal)[:200] if internal else ""
            
            writer.writerow({
                "order_number": note.get("order_number"),
                "external_reference": note.get("external_reference"),
                "shipping_date": note.get("shipping_date"),
                "shipping_order_status": note.get("shipping_order_status"),
                "tracking_gls": note.get("tracking_gls"),
                "internal_notes_preview": internal_preview
            })
    
    print(f"💾 CSV sauvegardé: {csv_file}")
    
    # Afficher uniquement les tracking trouvés
    tracking_list = [n for n in final_notes if n.get("tracking_gls")]
    
    print("\n" + "=" * 70)
    print(f"📊 RÉSULTAT: {tracking_found} tracking trouvés sur {len(final_notes)} BL")
    print("=" * 70)
    
    if tracking_list:
        print("\n📋 LISTE DES NUMÉROS DE SUIVI TROUVÉS:")
        print("-" * 60)
        for note in tracking_list:
            print(f"   {note['order_number']:<15} → {note['tracking_gls']}")
    
    # Sauvegarder la liste propre des tracking
    clean_tracking_file = f"gls_tracking_list_{YEAR_FILTER}.json"
    clean_tracking = [{
        'order_number': n['order_number'],
        'tracking_number': n['tracking_gls'],
        'shipping_date': n.get('shipping_date'),
        'external_reference': n.get('external_reference')
    } for n in tracking_list]
    
    with open(clean_tracking_file, 'w', encoding='utf-8') as f:
        json.dump(clean_tracking, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Liste propre sauvegardée: {clean_tracking_file}")

if __name__ == "__main__":
    main()