import requests
import json

API_URL = "https://app.erplain.net/public-api/graphql/endpoint"
BEARER_TOKEN = "437b4d61de0d0be070992852610f685f"  # <--- Replace with your actual token

# ----- GraphQL Query -----
query = """
query GetSalesOrders($first: Int!, $after: String) {
  salesOrders(first: $first, after: $after) {
    edges {
      node {
        id
        invoiceNumber
        createdAt
        lines {
          product {
            label
            sku
          }
          quantity
          unitPrice
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

# ----- Pagination Loop -----
headers = {
    "Authorization": f"Bearer {BEARER_TOKEN}",
    "Content-Type": "application/json"
}

def fetch_all_sales_orders(page_size=50):
    has_next_page = True
    end_cursor = None
    all_orders = []

    while has_next_page:
        variables = {
            "first": page_size,
            "after": end_cursor
        }
        payload = {
            "query": query,
            "variables": variables
        }

        response = requests.post(API_URL, json=payload, headers=headers)
        if response.status_code != 200:
            print(f"Error {response.status_code}: {response.text}")
            break

        result = response.json()
        if "errors" in result:
            print("GraphQL Errors:", json.dumps(result["errors"], indent=2))
            break

        data = result.get("data", {}).get("salesOrders", {})
        edges = data.get("edges", [])
        for edge in edges:
            node = edge.get("node", {})
            order_data = {
                "invoice_number": node.get("invoiceNumber"),
                "date": node.get("createdAt"),
                "customer_email": node.get("customer", {}).get("email"),
                "lines": []
            }
            for line in node.get("lines", []):
                product = line.get("product", {})
                line_data = {
                    "product_name": product.get("label", "Unknown"),
                    "product_sku": product.get("sku"),
                    "quantity": line.get("quantity"),
                    "unit_price": line.get("unitPrice")
                }
                order_data["lines"].append(line_data)
            all_orders.append(order_data)

        # Pagination handling
        page_info = data.get("pageInfo", {})
        has_next_page = page_info.get("hasNextPage", False)
        end_cursor = page_info.get("endCursor")
        print(f"Fetched {len(edges)} orders. Total so far: {len(all_orders)}")

    return all_orders

# ----- Main -----
if __name__ == "__main__":
    print("Starting to fetch sales orders...")
    orders = fetch_all_sales_orders()

    if orders:
        print(f"\nTotal orders fetched: {len(orders)}")
        # Save to file
        with open("sales_orders.json", "w", encoding="utf-8") as f:
            json.dump(orders, f, indent=2, ensure_ascii=False)
        print("Data saved to sales_orders.json")
    else:
        print("No orders found or an error occurred.")