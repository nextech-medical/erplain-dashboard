import requests
import json
from datetime import datetime, timezone
from dateutil import parser  # pip install python-dateutil

# Configuration API Erplain
API_URL = "https://app.erplain.net/public-api/graphql/endpoint"
BEARER_TOKEN = "437b4d61de0d0be070992852610f685f"  # Remplacez par votre token

# Date de début (1er janvier 2026, UTC)
START_DATE = datetime(2026, 1, 1, tzinfo=timezone.utc)

def parse_datetime(date_str: str) -> datetime:
    """Convertit une chaîne de date (ex: '2026-05-14T00:00:00+02:00') en datetime UTC"""
    dt = parser.parse(date_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def fetch_all_invoices_since_2026():
    """Tente d'abord un filtre GraphQL, sinon récupère toutes les factures et filtre localement"""
    print("📥 Tentative de récupération avec filtre GraphQL...")
    invoices = try_fetch_with_graphql_filter()
    if invoices is not None:
        return invoices
    print("⚠️ Le filtre GraphQL n'est pas supporté ou a échoué. Passage en mode récupération complète + filtrage local...")
    return fetch_all_invoices_and_filter_in_python()

def try_fetch_with_graphql_filter():
    """Essaie d'utiliser le filtre GraphQL. Retourne la liste des factures si succès, sinon None."""
    all_invoices = []
    page = 1
    page_size = 100
    start_date_iso = START_DATE.isoformat().replace('+00:00', 'Z')

    while True:
        print(f"📥 Récupération page {page} (avec filtre)...")
        query = f"""
        query {{
          Invoices(page: {page}, page_size: {page_size}, sort: {{ by: "created", direction: "DESC" }}, filter: {{ created: {{ gte: "{start_date_iso}" }} }}) {{
            edges {{
              node {{
                id
                label
                order_number
                created
                due_date
                subtotal
                total
                shipping_tax_amount
                customer {{ id label emails }}
                line_items {{
                  edges {{
                    node {{
                      quantity
                      price
                      discount
                      total
                      product {{
                        id
                        label
                        ... on variantType {{ sku }}
                      }}
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """
        response = requests.post(API_URL, json={"query": query}, headers={"Authorization": f"Bearer {BEARER_TOKEN}"})
        if response.status_code != 200:
            print(f"❌ Erreur HTTP {response.status_code}")
            return None
        data = response.json()
        if "errors" in data:
            # Si l'erreur est liée au filtre, on abandonne cette méthode
            if any("filter" in str(err).lower() for err in data['errors']):
                print("⚠️ Erreur de filtre GraphQL détectée.")
                return None
            else:
                print(f"❌ Erreurs GraphQL: {data['errors']}")
                return None

        invoices_data = data.get("data", {}).get("Invoices", {})
        edges = invoices_data.get("edges", [])
        nodes = []
        if isinstance(edges, dict):
            node = edges.get("node")
            if isinstance(node, list):
                nodes = node
            elif node:
                nodes = [node]
        elif isinstance(edges, list):
            for edge in edges:
                if isinstance(edge, dict) and "node" in edge:
                    nodes.append(edge["node"])
                else:
                    nodes.append(edge)

        if not nodes:
            break

        all_invoices.extend(nodes)
        print(f"   ✅ {len(nodes)} factures (total cumulé: {len(all_invoices)})")

        if len(nodes) < page_size:
            break
        page += 1

    return all_invoices

def fetch_all_invoices_and_filter_in_python():
    """Récupère TOUTES les factures (sans filtre) puis filtre celles postérieures à 2026-01-01."""
    print("📥 Récupération complète de toutes les factures...")
    all_invoices = []
    page = 1
    page_size = 100

    while True:
        print(f"📥 Récupération page {page}...")
        query = f"""
        query {{
          Invoices(page: {page}, page_size: {page_size}, sort: {{ by: "created", direction: "DESC" }}) {{
            edges {{
              node {{
                id
                label
                order_number
                created
                due_date
                subtotal
                total
                shipping_tax_amount
                customer {{ id label emails }}
                line_items {{
                  edges {{
                    node {{
                      quantity
                      price
                      discount
                      total
                      product {{
                        id
                        label
                        ... on variantType {{ sku }}
                      }}
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """
        response = requests.post(API_URL, json={"query": query}, headers={"Authorization": f"Bearer {BEARER_TOKEN}"})
        if response.status_code != 200:
            print(f"❌ Erreur HTTP {response.status_code}")
            break
        data = response.json()
        if "errors" in data:
            print(f"❌ Erreurs GraphQL: {data['errors']}")
            break

        invoices_data = data.get("data", {}).get("Invoices", {})
        edges = invoices_data.get("edges", [])
        nodes = []
        if isinstance(edges, dict):
            node = edges.get("node")
            if isinstance(node, list):
                nodes = node
            elif node:
                nodes = [node]
        elif isinstance(edges, list):
            for edge in edges:
                if isinstance(edge, dict) and "node" in edge:
                    nodes.append(edge["node"])
                else:
                    nodes.append(edge)

        if not nodes:
            break

        all_invoices.extend(nodes)
        print(f"   ✅ {len(nodes)} factures brutes (total cumulé: {len(all_invoices)})")

        if len(nodes) < page_size:
            break
        page += 1

    # Filtrage local
    filtered = []
    for inv in all_invoices:
        created_str = inv.get("created")
        if created_str:
            try:
                created_date = parse_datetime(created_str)
                if created_date >= START_DATE:
                    filtered.append(inv)
            except Exception as e:
                print(f"⚠️ Impossible de parser la date {created_str}: {e}")
    print(f"✅ Filtrage local terminé : {len(filtered)} factures conservées sur {len(all_invoices)}")
    return filtered

def save_invoices_to_json(invoices):
    if not invoices:
        print("❌ Aucune facture à sauvegarder")
        return
    filename = "factures_depuis_2026.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(invoices, f, indent=2, ensure_ascii=False)
    print(f"✅ {len(invoices)} factures sauvegardées dans '{filename}'")
    print("\n📋 Aperçu des 5 premières factures:")
    for inv in invoices[:5]:
        order_number = inv.get("order_number") or inv.get("label", "N/A")
        created = inv.get("created", "N/A")
        total = inv.get("total", 0)
        print(f"   - {order_number} | {created} | {total} €")

def get_statistics(invoices):
    if not invoices:
        return
    total_ca = 0.0
    clients = set()
    factures_avec_client = 0
    for inv in invoices:
        total_ca += float(inv.get("total", 0))
        customer = inv.get("customer")
        if customer and isinstance(customer, dict):
            label = customer.get("label")
            if label:
                clients.add(label)
                factures_avec_client += 1
    total_factures = len(invoices)
    print("\n" + "=" * 50)
    print("📊 STATISTIQUES DES FACTURES (à partir de 2026)")
    print("=" * 50)
    print(f"   📄 Nombre de factures: {total_factures}")
    print(f"   💰 Chiffre d'affaires total: {total_ca:,.2f} €")
    print(f"   👥 Nombre de clients uniques: {len(clients)}")
    print(f"   📋 Factures avec client: {factures_avec_client}")
    if total_factures > 0:
        print(f"   💶 Facture moyenne: {total_ca / total_factures:,.2f} €")
    print("=" * 50)

if __name__ == "__main__":
    print("=" * 50)
    print("📥 RÉCUPÉRATION DES FACTURES ERPLEIN DEPUIS 2026")
    print("=" * 50)
    invoices = fetch_all_invoices_since_2026()
    if invoices:
        save_invoices_to_json(invoices)
        get_statistics(invoices)
    else:
        print("❌ Aucune facture trouvée pour l'année 2026.")
        print("   Vérifiez que:")
        print("   1. Votre token est valide")
        print("   2. Vous avez bien des factures émises à partir du 01/01/2026")
        print("   3. L'API est activée sur votre abonnement")