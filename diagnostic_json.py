import json

with open("factures_depuis_2026.json", "r") as f:
    data = json.load(f)

def explore(obj, depth=0):
    if depth > 5:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if "line_items" in k.lower():
                print(f"Trouvé '{k}' à profondeur {depth}")
                if isinstance(v, dict):
                    print(f"  Type: dict, clés: {list(v.keys())}")
                    if "edges" in v:
                        edges = v["edges"]
                        print(f"  edges type: {type(edges)}")
                        if isinstance(edges, list) and len(edges) > 0:
                            print(f"    Premier edge: {list(edges[0].keys()) if isinstance(edges[0], dict) else type(edges[0])}")
                        elif isinstance(edges, dict):
                            print(f"    edges est un dict, clés: {list(edges.keys())}")
                elif isinstance(v, list):
                    print(f"  Type: list, longueur: {len(v)}")
                    if v:
                        print(f"    Premier élément: {type(v[0])}")
            explore(v, depth+1)
    elif isinstance(obj, list):
        for item in obj:
            explore(item, depth+1)

explore(data)