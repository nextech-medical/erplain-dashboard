from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport
import pandas as pd
from datetime import datetime
from config import ERPLAIN_TOKEN, ERPLAIN_ENDPOINT, ERPLAIN_PAGE_SIZE, ERPLAIN_FETCH_LIMIT, FETCH_YEAR

def fetch_sales_orders_for_year(year=2026):
    """
    Récupère toutes les commandes (sales orders) d'une année donnée.
    """
    date_from = f"{year}-01-01T00:00:00Z"
    date_to = f"{year}-12-31T23:59:59Z"
    
    # Requête GraphQL avec le champ accountManager
    query_str = """
    query GetSalesOrders($first: Int!, $after: String, $dateFrom: DateTime, $dateTo: DateTime) {
        salesOrders(first: $first, after: $after, filters: { date: { from: $dateFrom, to: $dateTo } }) {
            edges {
                node {
                    id
                    orderNumber
                    date
                    totalExclTax
                    shippingCostExclTax
                    accountManager
                    customer {
                        country { code }
                    }
                    orderLines {
                        edges {
                            node {
                                product { name }
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
    
    transport = RequestsHTTPTransport(
        url=ERPLAIN_ENDPOINT,
        headers={"Authorization": f"Bearer {ERPLAIN_TOKEN}"},
        use_json=True
    )
    client = Client(transport=transport, fetch_schema_from_transport=False)
    
    query = gql(query_str)
    variables = {"first": ERPLAIN_PAGE_SIZE, "dateFrom": date_from, "dateTo": date_to}
    all_orders = []
    has_next = True
    after = None
    total_fetched = 0
    
    try:
        while has_next and total_fetched < ERPLAIN_FETCH_LIMIT:
            if after:
                variables["after"] = after
            result = client.execute(query, variable_values=variables)
            edges = result.get("salesOrders", {}).get("edges", [])
            print(f"Nombre de commandes dans cette page : {len(edges)}")
            
            for edge in edges:
                order = edge["node"]
                order_number = order.get("orderNumber")
                if not order_number:
                    print("Commande sans numéro ignorée")
                    continue
                order_date = order.get("date", "")[:10]
                country = order.get("customer", {}).get("country", {}).get("code") if order.get("customer") else None
                shipping_cost = float(order.get("shippingCostExclTax", 0.0))
                
                # 🔥 Récupérer le gestionnaire de compte (accountManager)
                gestionnaire_de_compte = order.get("accountManager", "Non spécifié")
                if not gestionnaire_de_compte or gestionnaire_de_compte == "":
                    gestionnaire_de_compte = "Non spécifié"
                
                for line_edge in order.get("orderLines", {}).get("edges", []):
                    line = line_edge["node"]
                    product_name = line.get("product", {}).get("name")
                    if not product_name:
                        continue
                    quantity = line.get("quantity", 0)
                    total_ht = float(line.get("totalExclTax", 0.0))
                    all_orders.append({
                        "commande_id": order_number,
                        "date": order_date,
                        "produit": product_name,
                        "quantite": quantity,
                        "prix_ht": total_ht,
                        "cout_livraison_fournisseur": shipping_cost,
                        "pays": country,
                        "Gestionnaire_de_compte": gestionnaire_de_compte  # ✅ Ajouté
                    })
            
            page_info = result.get("salesOrders", {}).get("pageInfo", {})
            has_next = page_info.get("hasNextPage", False)
            after = page_info.get("endCursor")
            total_fetched += len(edges)
            print(f"Total commandes traitées : {total_fetched}")
        
        if not all_orders:
            print("Aucune commande récupérée. Vérifiez le token, l'endpoint ou les dates.")
        
        df = pd.DataFrame(all_orders)
        
        # Afficher les statistiques des gestionnaires trouvés
        if not df.empty:
            print(f"\n📊 Statistiques des gestionnaires de compte:")
            gestionnaires_stats = df['Gestionnaire_de_compte'].value_counts()
            for gestionnaire, count in gestionnaires_stats.items():
                print(f"  - {gestionnaire}: {count} lignes")
        
        return df
    
    except Exception as e:
        print(f"Erreur lors de l'appel API : {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


# Test rapide pour vérifier les gestionnaires
def test_gestionnaires():
    """Test pour voir les gestionnaires récupérés"""
    query_str = """
    query TestGestionnaires {
        salesOrders(first: 10) {
            edges {
                node {
                    orderNumber
                    accountManager
                }
            }
        }
    }
    """
    
    transport = RequestsHTTPTransport(
        url=ERPLAIN_ENDPOINT,
        headers={"Authorization": f"Bearer {ERPLAIN_TOKEN}"},
        use_json=True
    )
    client = Client(transport=transport, fetch_schema_from_transport=False)
    
    try:
        result = client.execute(gql(query_str))
        edges = result.get("salesOrders", {}).get("edges", [])
        
        print("🔍 Test des gestionnaires de compte:")
        print("="*50)
        
        gestionnaires_vus = set()
        for edge in edges:
            order = edge["node"]
            gestionnaire = order.get("accountManager", "Non spécifié")
            if not gestionnaire or gestionnaire == "":
                gestionnaire = "Non spécifié"
            gestionnaires_vus.add(gestionnaire)
            print(f"Commande {order.get('orderNumber')}: {gestionnaire}")
        
        print(f"\n📋 Gestionnaires uniques trouvés: {sorted(gestionnaires_vus)}")
        
    except Exception as e:
        print(f"Erreur: {e}")


if __name__ == "__main__":
    # Tester d'abord
    test_gestionnaires()
    
    print("\n" + "="*50)
    print("📥 Récupération complète des commandes...")
    
    # Récupérer toutes les commandes
    df = fetch_sales_orders_for_year(year=2026)
    
    if not df.empty:
        print(f"\n✅ {len(df)} lignes récupérées")
        print(f"\n📋 Aperçu des 10 premières lignes:")
        print(df.head(10))
        
        print(f"\n📊 Résumé par gestionnaire:")
        summary = df.groupby('Gestionnaire_de_compte').agg({
            'commande_id': 'nunique',
            'prix_ht': 'sum',
            'quantite': 'sum'
        }).rename(columns={
            'commande_id': 'nb_commandes',
            'prix_ht': 'ca_ht_total',
            'quantite': 'nb_produits'
        })
        print(summary)
        
        # Sauvegarder en CSV
        output_file = f"sales_orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n💾 Données sauvegardées dans {output_file}")
    else:
        print("❌ Aucune donnée récupérée")