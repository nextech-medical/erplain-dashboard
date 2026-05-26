import json

with open("factures_depuis_2026.json", "r") as f:
    data = json.load(f)

def extract_skus(obj, skus):
    if isinstance(obj, dict):
        if "product" in obj and isinstance(obj["product"], dict) and "sku" in obj["product"]:
            skus.add(obj["product"]["sku"])
        for v in obj.values():
            extract_skus(v, skus)
    elif isinstance(obj, list):
        for item in obj:
            extract_skus(item, skus)

skus = set()
extract_skus(data, skus)

with open("skus_vides.csv", "w", encoding="utf-8") as f:
    f.write("sku,cost_unit\n")
    for sku in sorted(skus):
        f.write(f"{sku},\n")

print(f"{len(skus)} SKU uniques exportés dans skus_vides.csv")