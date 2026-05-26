# diagnostic_erplain.py
import requests
import json

API_URL = "https://app.erplain.net/public-api/graphql/endpoint"
BEARER_TOKEN = "437b4d61de0d0be070992852610f685f"

def test_query(query, name):
    """Teste une requête GraphQL."""
    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(API_URL, json={"query": query}, headers=headers, timeout=30)
        data = response.json()
        
        if "errors" in data:
            print(f"❌ {name}: {data['errors'][0]['message'][:80]}")
            return None
        else:
            print(f"✅ {name}: Fonctionne!")
            return data.get("data", {})
    except Exception as e:
        print(f"❌ {name}: {e}")
        return None

def discover_schema():
    """Découvre la structure du schéma GraphQL."""
    
    print("\n" + "="*60)
    print("🔍 DÉCOUVERTE DU SCHÉMA ERPLEIN")
    print("="*60)
    
    # 1. Récupérer tous les types disponibles
    query_types = """
    {
        __schema {
            types {
                name
                kind
                fields {
                    name
                }
            }
        }
    }
    """
    
    print("\n📋 Récupération des types GraphQL...")
    result = test_query(query_types, "Schema")
    
    if result:
        types = result.get("__schema", {}).get("types", [])
        
        # Filtrer les types pertinents
        relevant_types = [
            t for t in types 
            if any(keyword in t.get('name', '').lower() for keyword in 
                   ['shipping', 'order', 'delivery', 'shipment', 'fulfillment'])
        ]
        
        print(f"\n📦 Types liés aux livraisons trouvés ({len(relevant_types)}):")
        for t in relevant_types[:20]:
            print(f"   - {t.get('name')}")
    
    # 2. Tester les différents endpoints possibles
    endpoints = [
        "shippingOrders",
        "ShippingOrders", 
        "shipping_orders",
        "Shipping_orders",
        "deliveryOrders",
        "DeliveryOrders",
        "fulfillments",
        "Fulfillments",
        "shipments",
        "Shipments",
        "deliveryNotes",
        "DeliveryNotes",
        "salesOrders",
        "SalesOrders",
        "orders",
        "Orders"
    ]
    
    print("\n🔍 Test des endpoints possibles...")
    working_endpoints = []
    
    for endpoint in endpoints:
        query = f"""
        {{
          {endpoint} {{
            __typename
          }}
        }}
        """
        
        result = test_query(query, endpoint)
        if result and endpoint in result:
            working_endpoints.append(endpoint)
            print(f"   ✅ {endpoint} est accessible!")
    
    if not working_endpoints:
        print("\n❌ Aucun endpoint trouvé")
        return
    
    # 3. Pour chaque endpoint fonctionnel, récupérer la structure
    for endpoint in working_endpoints:
        print(f"\n📖 Structure de {endpoint}:")
        query = f"""
        {{
          {endpoint} {{
            edges {{
              node {{
                __typename
                ... on __Field {{
                  name
                  type {{
                    name
                  }}
                }}
              }}
            }}
          }}
        }}
        """
        
        result = test_query(query, f"Structure {endpoint}")
        if result:
            print(f"   Structure trouvée pour {endpoint}")
    
    # 4. Essayer de récupérer une petite quantité de données
    print("\n📥 Tentative de récupération de données...")
    for endpoint in working_endpoints[:3]:
        query = f"""
        {{
          {endpoint}(first: 5) {{
            edges {{
              node {{
                id
              }}
            }}
          }}
        }}
        """
        
        result = test_query(query, f"Data {endpoint}")
        if result and result.get(endpoint, {}).get('edges'):
            print(f"   ✅ {endpoint} contient {len(result[endpoint]['edges'])} éléments")

if __name__ == "__main__":
    discover_schema()