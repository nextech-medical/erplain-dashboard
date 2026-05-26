def extract_erplain_orders_with_cogs(invoices):
    orders = []
    sample_shown = False
    for idx, inv in enumerate(invoices):
        if not isinstance(inv, dict):
            continue

        order_id = inv.get("order_number") or inv.get("label") or inv.get("id")
        if not order_id:
            continue
        order_id = clean_order_id(order_id)

        total_ttc = 0.0
        for field in ["total", "grand_total", "amount", "total_ttc"]:
            if field in inv:
                total_ttc = safe_float(inv.get(field))
                if total_ttc != 0:
                    break

        cogs_total = 0.0
        line_items = inv.get("line_items")
        if line_items and isinstance(line_items, dict):
            edges = line_items.get("edges")
            if edges is not None:
                # Cas 1: edges est une liste
                if isinstance(edges, list):
                    for edge in edges:
                        if isinstance(edge, dict) and "node" in edge:
                            node = edge["node"]
                            unit_cost = extract_cost_from_item(node, verbose=VERBOSE and not sample_shown)
                            qty = safe_float(node.get("quantity"), 1)
                            cogs_total += unit_cost * qty
                            if total_ttc == 0:
                                price = safe_float(node.get("price"))
                                total_ttc += price * qty
                # Cas 2: edges est un dictionnaire avec une clé 'node'
                elif isinstance(edges, dict) and "node" in edges:
                    node = edges["node"]
                    unit_cost = extract_cost_from_item(node, verbose=VERBOSE and not sample_shown)
                    qty = safe_float(node.get("quantity"), 1)
                    cogs_total += unit_cost * qty
                    if total_ttc == 0:
                        price = safe_float(node.get("price"))
                        total_ttc += price * qty

        date_str = inv.get("created") or inv.get("date") or inv.get("created_at")
        date = parse_date(date_str)

        orders.append({
            "order_id": order_id,
            "ca_ttc": round(total_ttc, 2),
            "cogs_total": round(cogs_total, 2),
            "date": date
        })

        if not sample_shown and VERBOSE and idx == 0:
            print("\n📄 Exemple du premier 'node' :")
            if line_items and isinstance(line_items, dict):
                edges = line_items.get("edges")
                if edges and isinstance(edges, dict) and "node" in edges:
                    node = edges["node"]
                    print(json.dumps(node, indent=2, ensure_ascii=False)[:1500])
            sample_shown = True

    df = pd.DataFrame(orders)
    print(f"📦 {len(df)} commandes extraites d'Erplain (avec COGS)")
    if VERBOSE:
        print("   Aperçu des 3 premières lignes :")
        print(df.head(3))
        if df['cogs_total'].sum() == 0:
            print("   ❗ Le COGS total est nul. Vérifiez les noms des champs dans votre JSON.")
    return df