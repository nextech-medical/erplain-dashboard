import requests
import json
from datetime import datetime

# --- 1. Configuration ---
API_URL = "https://app.erplain.net/public-api/graphql/endpoint" # Endpoint unique[reference:4]
BEARER_TOKEN = "437b4d61de0d0be070992852610f685f"  # <-- Remplacez par votre vrai token

# --- 2. La requête GraphQL pour récupérer transactions ET produits ---
# Clé pour trier les résultats par date si nécessaire : vous pouvez ajouter `, order_by: {field: "date", direction: DESC}` si le champ existe.
query = """
query GetTransactionsWithProducts($first: Int = 100) {
  transactions(first: $first) {
    edges {
      node {
        id
        date
        invoice_number
        lines {
          product {
            label
            id
            sku
            brand {
              label
            }
          }
          unit_price
          quantity
        }
        customer {
          email
        }
      }
      cursor
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

# --- 3. Configuration de la requête HTTP ---
headers = {
    "Authorization": f"Bearer {BEARER_TOKEN}",
    "Content-Type": "application/json"
}

def fetch_all_transactions():
    """Récupère toutes les transactions en gérant la pagination."""
    all_nodes = []
    has_next_page = True
    end_cursor = None
    first = 50  # Nombre d'éléments par page

    while has_next_page:
        variables = {"first": first}
        if end_cursor:
            variables["after"] = end_cursor

        payload = {"query": query, "variables": variables}

        try:
            response = requests.post(API_URL, json=payload, headers=headers)
            response.raise_for_status()  # Lève une exception en cas d'erreur HTTP

            result = response.json()

            if "errors" in result:
                print("Erreur GraphQL :", json.dumps(result["errors"], indent=2))
                break

            page_data = result.get("data", {}).get("transactions", {})
            new_nodes = page_data.get("edges", [])
            all_nodes.extend(new_nodes)

            page_info = page_data.get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)
            end_cursor = page_info.get("endCursor")

            print(f"--- Page récupérée : {len(new_nodes)} transactions (Total: {len(all_nodes)})")

        except requests.exceptions.RequestException as e:
            print(f"Erreur réseau : {e}")
            break
        except json.JSONDecodeError as e:
            print(f"Erreur de décodage JSON : {e}")
            break

    return all_nodes


def format_to_table(transactions_data):
    """Transforme les données brutes en tableau comme demandé."""
    table_rows = []
    for transaction_edge in transactions_data:
        transaction = transaction_edge.get("node", {})
        for line in transaction.get("lines", []):
            product = line.get("product", {})
            row = {
                "commande_id": transaction.get("invoice_number") or transaction.get("id"),
                "produit": product.get("label", "Nom produit non trouvé"),  # Le nom réel du produit !
                "quantité": line.get("quantity"),
                "ca_unitaire": line.get("unit_price"),
                "date": transaction.get("date"),
                "client_email": transaction.get("customer", {}).get("email")
                # Ajoutez d'autres champs ici selon vos besoins
            }
            table_rows.append(row)
    return table_rows


# --- 4. Exécution du script ---
if __name__ == "__main__":
    print("Début de la récupération des données...")
    all_transactions = fetch_all_transactions()

    if all_transactions:
        print(f"\n{len(all_transactions)} transactions récupérées. Construction du tableau...")
        formatted_data = format_to_table(all_transactions)

        # Sauvegarde en JSON pour une utilisation ultérieure
        with open("transactions_completes.json", "w", encoding="utf-8") as f:
            json.dump(formatted_data, f, indent=2, ensure_ascii=False)

        # Affichage des premières lignes
        print("\nExtrait des données récupérées :")
        for row in formatted_data[:3]:  # Affiche les 3 premières lignes de commandes
            print(json.dumps(row, indent=2, ensure_ascii=False))
        print("\nFichier 'transactions_completes.json' créé avec succès.")
    else:
        print("Aucune donnée récupérée.")