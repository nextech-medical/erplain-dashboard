import requests
import pandas as pd
from datetime import datetime
from config import ERPLAIN_TOKEN, ERPLAIN_ENDPOINT, ERPLAIN_PAGE_SIZE, ERPLAIN_FETCH_LIMIT, FETCH_YEAR

def run_graphql_query(query, variables=None):
    """Exécute une requête GraphQL et retourne le JSON."""
    headers = {
        "Authorization": f"Bearer {ERPLAIN_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    response = requests.post(ERPLAIN_ENDPOINT, json=payload, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Erreur HTTP {response.status_code}: {response.text}")
    data = response.json()
    if "errors" in data:
        raise Exception(f"Erreur GraphQL: {data['errors']}")
    return data

def fetch_sales_orders_for_year(year=2026):
    """
    Récupère toutes les commandes (orders) d'une année donnée.
    Utilise les vrais noms de champs ERPlein : orders, reference, createdAt, etc.
    """
    date_from = f"{year}-01-01T00:00:00Z"
    date_to = f"{year}-12-31T23:59:59Z"
    
    query = """
    query GetOrders($first: Int!, $after: String, $dateFrom: DateTime, $dateTo: DateTime) {
      orders(first: $first, after: $after, filters: { createdAt: { from: $dateFrom, to: $dateTo } }) {
        edges {
          node {
            id
            reference
            createdAt
            totalExclTax
            shippingCostExclTax
            customer {
              shippingAddress {
                countryCode
              }
            }
            orderLines {
              edges {
                node {
                  product {
                    name
                  }
                  quantity
                  totalExclTax
                }
              }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
    """
    
    all_orders = []
    has_next_page = True
    after = None
    total_fetched = 0
    
    while has_next_page and total_fetched < ERPLAIN_FETCH_LIMIT:
        variables = {
            "first": ERPLAIN_PAGE_SIZE,
            "dateFrom": date_from,
            "dateTo": date_to
        }
        if after:
            variables["after"] = after
        
        result = run_graphql_query(query, variables)
        orders_edges = result["data"]["orders"]["edges"]
        print(f"Page: {len(orders_edges)} commandes récupérées")
        
        for edge in orders_edges:
            order = edge["node"]
            order_ref = order.get("reference")
            if not order_ref:
                continue
            order_date = order.get("createdAt", "")[:10]
            # Récupération du pays depuis l'adresse de livraison
            customer = order.get("customer", {})
            shipping = customer.get("shippingAddress", {})
            country = shipping.get("countryCode")
            shipping_cost = float(order.get("shippingCostExclTax", 0.0))
            
            # Lignes de commande
            for line_edge in order.get("orderLines", {}).get("edges", []):
                line = line_edge["node"]
                product = line.get("product", {})
                product_name = product.get("name")
                if not product_name:
                    continue
                quantity = line.get("quantity", 0)
                total_ht = float(line.get("totalExclTax", 0.0))
                all_orders.append({
                    "commande_id": order_ref,
                    "date": order_date,
                    "produit": product_name,
                    "quantite": quantity,
                    "prix_ht": total_ht,
                    "cout_livraison_fournisseur": shipping_cost,
                    "pays": country
                })
        
        page_info = result["data"]["orders"]["pageInfo"]
        has_next_page = page_info.get("hasNextPage", False)
        after = page_info.get("endCursor")
        total_fetched += len(orders_edges)
        print(f"Total commandes traitées: {total_fetched}")
    
    if not all_orders:
        print("Aucune commande trouvée pour l'année", year)
    return pd.DataFrame(all_orders)

def fetch_product_costs():
    """
    Récupère le coût d'achat (hors taxe) de tous les produits.
    Supposons que le champ s'appelle 'costPriceExclTax'.
    """
    query = """
    query GetProducts($first: Int!) {
      products(first: $first) {
        edges {
          node {
            name
            costPriceExclTax
          }
        }
      }
    }
    """
    variables = {"first": ERPLAIN_FETCH_LIMIT}
    result = run_graphql_query(query, variables)
    costs = {}
    for edge in result["data"]["products"]["edges"]:
        p = edge["node"]
        name = p.get("name")
        cost = float(p.get("costPriceExclTax", 0.0))
        if name:
            costs[name] = cost
    return costs