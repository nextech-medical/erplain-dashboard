# extract_skus.py
import json

with open("factures_depuis_2026.json") as f:
    data = json.load(f)

def extract_skus(obj):
    skus = set()
    if isinstance(obj, dict):
        if "product" in obj and isinstance(obj["product"], dict) and "sku" in obj["product"]:
            skus.add(obj["product"]["sku"])
        for v in obj.values():
            skus.update(extract_skus(v))
    elif isinstance(obj, list):
        for item in obj:
            skus.update(extract_skus(item))
    return skus

skus = extract_skus(data)
with open("couts_produits.csv", "w") as f:
    f.write("sku,cost_unit\n")
    for sku in sorted(skus):
        f.write(f"{sku},\n")
print(f"{len(skus)} SKU uniques exportés dans couts_produits.csv")