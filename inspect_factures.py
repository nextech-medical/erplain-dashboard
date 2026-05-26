import json

with open("factures_depuis_2026.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Type de data: {type(data)}")
print(f"Nombre d'éléments: {len(data) if isinstance(data, list) else 1}")

# Prendre la première facture
if isinstance(data, list) and len(data) > 0:
    first_invoice = data[0]
elif isinstance(data, dict):
    first_invoice = data
else:
    print("Structure inconnue")
    exit()

print("\n=== STRUCTURE DE LA PREMIÈRE FACTURE ===\n")
print("Clés disponibles:", list(first_invoice.keys()))

print("\n=== CONTENU DÉTAILLÉ ===\n")
for key, value in first_invoice.items():
    if isinstance(value, dict):
        print(f"{key}: {list(value.keys()) if value else 'None'}")
    elif isinstance(value, list):
        print(f"{key}: liste de {len(value)} éléments")
    else:
        print(f"{key}: {value}")

# Vérifier spécifiquement les montants
print("\n=== RECHERCHE DES MONTANTS ===\n")
for key, value in first_invoice.items():
    if 'total' in key.lower() or 'subtotal' in key.lower() or 'price' in key.lower() or 'amount' in key.lower():
        print(f"{key}: {value}")

# Vérifier la structure des line_items
print("\n=== STRUCTURE DES LINE_ITEMS ===\n")
line_items = first_invoice.get("line_items", {})
print(f"Type de line_items: {type(line_items)}")
if isinstance(line_items, dict):
    print(f"Clés de line_items: {list(line_items.keys())}")
    edges = line_items.get("edges", [])
    print(f"Type de edges: {type(edges)}")
    if isinstance(edges, list) and len(edges) > 0:
        print(f"Premier edge: {edges[0]}")
    elif isinstance(edges, dict):
        print(f"edges est un dict: {list(edges.keys())}")