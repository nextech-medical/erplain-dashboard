# fetch_delivery_notes.py (version finale avec internal_notes)
import requests
import json
import csv
import re
from datetime import datetime
from config import API_URL, BEARER_TOKEN

YEAR_FILTER = 2026
headers = {"Authorization": f"Bearer {BEARER_TOKEN}", "Content-Type": "application/json"}

def safe_str(value):
    return "" if value is None else str(value)

def extraire_tracking(notes_html):
    if not notes_html:
        return None
    clean = re.sub(r'<[^>]+>', ' ', str(notes_html))
    clean = re.sub(r'\s+', ' ', clean).strip()
    patterns = [r'\b(\d{12,16})\b', r'\b(00[A-Z0-9]{4,10})\b', r'\b(GL\d{10,14}FR?)\b']
    for p in patterns:
        m = re.search(p, clean)
        if m:
            return m.group(1)
    return None

def fetch_all_delivery_notes():
    all_notes = []
    page, page_size = 1, 100
    print("📦 Récupération des BL...")
    while True:
        query = f"""
        {{
          ShippingOrders(
            page: {page}
            page_size: {page_size}
            sort: {{ by: "shipping_date", direction: "DESC" }}
          ) {{
            edges {{ node {{
              id, order_number, external_reference, shipping_date, shipping_order_status, created, notes, internal_notes
            }} }}
          }}
        }}
        """
        r = requests.post(API_URL, json={"query": query}, headers=headers, timeout=60)
        data = r.json()
        nodes = data.get("data", {}).get("ShippingOrders", {}).get("edges", {}).get("node", [])
        if not nodes:
            break
        all_notes.extend(nodes)
        print(f"Page {page}: {len(nodes)} BL (total {len(all_notes)})")
        if len(nodes) < page_size:
            break
        page += 1
    return all_notes

def main():
    notes = fetch_all_delivery_notes()
    print(f"\n✅ {len(notes)} BL récupérés")
    # Ajouter tracking extrait
    for n in notes:
        n["tracking_gls"] = extraire_tracking(n.get("internal_notes", ""))
    with open(f"delivery_notes_{YEAR_FILTER}.json", "w", encoding="utf-8") as f:
        json.dump(notes, f, indent=2, ensure_ascii=False, default=str)
    print(f"💾 JSON sauvegardé: delivery_notes_{YEAR_FILTER}.json")
    # Afficher les tracking trouvés
    tracking_list = [n for n in notes if n.get("tracking_gls")]
    print(f"\n🔍 {len(tracking_list)} tracking trouvés :")
    for t in tracking_list[:20]:
        print(f"   {t['order_number']} → {t['tracking_gls']}")

if __name__ == "__main__":
    main()