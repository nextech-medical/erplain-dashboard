# liste_cles_node.py
import json

with open("factures_depuis_2026.json", "r") as f:
    data = json.load(f)

def find_first_node(data):
    if isinstance(data, dict):
        if "line_items" in data and isinstance(data["line_items"], dict):
            edges = data["line_items"].get("edges", [])
            if edges and isinstance(edges[0], dict):
                node = edges[0].get("node", {})
                return node
        for v in data.values():
            res = find_first_node(v)
            if res:
                return res
    elif isinstance(data, list):
        for item in data:
            res = find_first_node(item)
            if res:
                return res
    return None

node = find_first_node(data)
if node:
    print("Clés trouvées dans 'node' :")
    for k in node.keys():
        print(f"  - {k}")
    print("\nValeurs des premières clés :")
    for k in list(node.keys())[:10]:
        print(f"  {k} = {node[k]}")
else:
    print("Aucun node trouvé.")