"""
graph_builder.py — Build graph nodes and edges from the O2C database.

Color scheme:
  Customer  = #4CAF50 (green)
  Order     = #2196F3 (blue)
  Delivery  = #FF9800 (orange)
  Invoice   = #9C27B0 (purple)
  Product   = #F44336 (red)
  Payment   = #00BCD4 (cyan)
"""

from db import execute_query

# Node type colors
COLORS = {
    "Customer": "#4CAF50",
    "Order": "#2196F3",
    "Delivery": "#FF9800",
    "Invoice": "#9C27B0",
    "Product": "#F44336",
    "Payment": "#00BCD4",
}


def build_graph(customer_id: str | None = None, order_id: str | None = None) -> dict:
    """
    Build a graph of nodes and edges from the O2C database.

    Args:
        customer_id: Optional filter by customer/business_partner ID
        order_id: Optional filter by sales order ID

    Returns:
        { "nodes": [...], "edges": [...] }
    """
    nodes = []
    edges = []
    node_ids = set()

    def add_node(node_id: str, node_type: str, label: str, metadata: dict | None = None):
        if node_id not in node_ids:
            node_ids.add(node_id)
            nodes.append({
                "id": node_id,
                "type": node_type,
                "label": label,
                "color": COLORS.get(node_type, "#999999"),
                "metadata": metadata or {},
            })

    def add_edge(source: str, target: str, relation: str):
        edges.append({
            "source": source,
            "target": target,
            "relation": relation,
        })

    # ── 1. Customers ──────────────────────────────────────────────────────
    cust_filter = ""
    cust_params = None
    if customer_id:
        cust_filter = "WHERE business_partner = ?"
        cust_params = (customer_id,)

    customers = execute_query(
        f"SELECT business_partner, organization_bp_name1, business_partner_is_blocked FROM [business_partners] {cust_filter}",
        cust_params,
    )
    for c in customers:
        add_node(
            f"cust_{c['business_partner']}",
            "Customer",
            c["organization_bp_name1"] or f"Customer {c['business_partner']}",
            {"business_partner": c["business_partner"], "is_blocked": c["business_partner_is_blocked"]},
        )

    # ── 2. Sales Orders ───────────────────────────────────────────────────
    order_filter_parts = []
    order_params = []
    if customer_id:
        order_filter_parts.append("sold_to_party = ?")
        order_params.append(customer_id)
    if order_id:
        order_filter_parts.append("sales_order = ?")
        order_params.append(order_id)

    order_where = ""
    if order_filter_parts:
        order_where = "WHERE " + " AND ".join(order_filter_parts)

    orders = execute_query(
        f"""SELECT sales_order, sold_to_party, creation_date, total_net_amount,
                   sales_order_type, transaction_currency
            FROM [sales_order_headers] {order_where}
            LIMIT 200""",
        tuple(order_params) if order_params else None,
    )

    for o in orders:
        so = str(int(o["sales_order"])) if isinstance(o["sales_order"], float) else str(o["sales_order"])
        add_node(
            f"order_{so}",
            "Order",
            f"SO {so}",
            {
                "sales_order": so,
                "creation_date": o["creation_date"],
                "total_net_amount": o["total_net_amount"],
                "currency": o["transaction_currency"],
            },
        )
        # Edge: Order → Customer
        cust_id = str(int(o["sold_to_party"])) if isinstance(o["sold_to_party"], float) else str(o["sold_to_party"])
        cust_node_id = f"cust_{cust_id}"
        if cust_node_id not in node_ids:
            # Add customer node if not yet present (missing from filter)
            add_node(cust_node_id, "Customer", f"Customer {cust_id}", {"business_partner": cust_id})
        add_edge(f"order_{so}", cust_node_id, "sold_to")

    # ── 3. Outbound Deliveries ────────────────────────────────────────────
    if orders:
        # Find deliveries linked to our orders via delivery_items.reference_sd_document
        order_ids = [str(int(o["sales_order"])) if isinstance(o["sales_order"], float) else str(o["sales_order"]) for o in orders]
        placeholders = ",".join(["?"] * len(order_ids))

        # Get delivery docs that reference our sales orders
        del_items = execute_query(
            f"""SELECT DISTINCT di.delivery_document, di.reference_sd_document
                FROM [outbound_delivery_items] di
                WHERE di.reference_sd_document IN ({placeholders})""",
            tuple(order_ids),
        )

        # Build a map: delivery_document → list of order references
        delivery_order_map = {}
        for di in del_items:
            dd = str(int(di["delivery_document"])) if isinstance(di["delivery_document"], float) else str(di["delivery_document"])
            ref = str(int(float(di["reference_sd_document"]))) if di["reference_sd_document"] else None
            if ref:
                delivery_order_map.setdefault(dd, set()).add(ref)

        if delivery_order_map:
            del_ids = list(delivery_order_map.keys())
            placeholders2 = ",".join(["?"] * len(del_ids))

            deliveries = execute_query(
                f"""SELECT delivery_document, creation_date,
                           overall_goods_movement_status, shipping_point
                    FROM [outbound_delivery_headers]
                    WHERE delivery_document IN ({placeholders2})
                    LIMIT 200""",
                tuple(del_ids),
            )

            for d in deliveries:
                dd = str(int(d["delivery_document"])) if isinstance(d["delivery_document"], float) else str(d["delivery_document"])
                add_node(
                    f"deliv_{dd}",
                    "Delivery",
                    f"DL {dd}",
                    {
                        "delivery_document": dd,
                        "creation_date": d["creation_date"],
                        "goods_movement_status": d["overall_goods_movement_status"],
                    },
                )
                # Add edges from delivery to linked orders
                for ref_order in delivery_order_map.get(dd, []):
                    order_node = f"order_{ref_order}"
                    if order_node in node_ids:
                        add_edge(f"deliv_{dd}", order_node, "delivers")

    # ── 4. Billing Documents (Invoices) ───────────────────────────────────
    if orders:
        sold_to_parties = list(set(str(int(o["sold_to_party"])) if isinstance(o["sold_to_party"], float) else str(o["sold_to_party"]) for o in orders))
        placeholders = ",".join(["?"] * len(sold_to_parties))

        invoices = execute_query(
            f"""SELECT billing_document, sold_to_party, creation_date,
                       total_net_amount, transaction_currency,
                       billing_document_is_cancelled
                FROM [billing_document_headers]
                WHERE sold_to_party IN ({placeholders})
                AND (billing_document_is_cancelled IS NULL OR billing_document_is_cancelled = '' OR billing_document_is_cancelled = 'false')
                LIMIT 200""",
            tuple(sold_to_parties),
        )

        for inv in invoices:
            bd = str(int(inv["billing_document"])) if isinstance(inv["billing_document"], float) else str(inv["billing_document"])
            add_node(
                f"inv_{bd}",
                "Invoice",
                f"INV {bd}",
                {
                    "billing_document": bd,
                    "creation_date": inv["creation_date"],
                    "total_net_amount": inv["total_net_amount"],
                    "currency": inv["transaction_currency"],
                },
            )

        # Link invoices to deliveries via billing_document_items.reference_sd_document
        if invoices:
            inv_ids = [str(int(inv["billing_document"])) if isinstance(inv["billing_document"], float) else str(inv["billing_document"]) for inv in invoices]
            placeholders3 = ",".join(["?"] * len(inv_ids))
            bill_items = execute_query(
                f"""SELECT billing_document, reference_sd_document
                    FROM [billing_document_items]
                    WHERE billing_document IN ({placeholders3})""",
                tuple(inv_ids),
            )
            for bi in bill_items:
                bd = str(int(bi["billing_document"])) if isinstance(bi["billing_document"], float) else str(bi["billing_document"])
                ref = str(int(float(bi["reference_sd_document"]))) if bi["reference_sd_document"] else None
                if ref:
                    # Link to delivery if exists
                    deliv_node = f"deliv_{ref}"
                    if deliv_node in node_ids:
                        add_edge(f"inv_{bd}", deliv_node, "bills")

    # ── 5. Payments ───────────────────────────────────────────────────────
    if customer_id or orders:
        pay_filter_parts = []
        pay_params = []
        if customer_id:
            pay_filter_parts.append("customer = ?")
            pay_params.append(customer_id)
        elif orders:
            cust_ids = list(set(str(int(o["sold_to_party"])) if isinstance(o["sold_to_party"], float) else str(o["sold_to_party"]) for o in orders))
            placeholders = ",".join(["?"] * len(cust_ids))
            pay_filter_parts.append(f"customer IN ({placeholders})")
            pay_params.extend(cust_ids)

        # Only show positive payments (not reversals)
        pay_filter_parts.append("CAST(amount_in_transaction_currency AS REAL) > 0")
        pay_where = "WHERE " + " AND ".join(pay_filter_parts)

        payments = execute_query(
            f"""SELECT accounting_document, customer,
                       amount_in_transaction_currency, transaction_currency,
                       clearing_date, posting_date
                FROM [payments_accounts_receivable]
                {pay_where}
                LIMIT 100""",
            tuple(pay_params) if pay_params else None,
        )

        for p in payments:
            ad = str(p["accounting_document"])
            add_node(
                f"pay_{ad}",
                "Payment",
                f"PAY {ad}",
                {
                    "accounting_document": ad,
                    "amount": p["amount_in_transaction_currency"],
                    "currency": p["transaction_currency"],
                    "clearing_date": p["clearing_date"],
                },
            )
            # Edge: Payment → Customer
            cust_id = str(p["customer"])
            cust_node = f"cust_{cust_id}"
            if cust_node in node_ids:
                add_edge(f"pay_{ad}", cust_node, "paid_by")

    # ── 6. Products (from order items) ────────────────────────────────────
    if orders:
        order_ids = [str(int(o["sales_order"])) if isinstance(o["sales_order"], float) else str(o["sales_order"]) for o in orders]
        placeholders = ",".join(["?"] * len(order_ids))

        order_items = execute_query(
            f"""SELECT sales_order, material, net_amount
                FROM [sales_order_items]
                WHERE sales_order IN ({placeholders})
                LIMIT 500""",
            tuple(order_ids),
        )

        # Get unique materials
        material_ids = list(set(oi["material"] for oi in order_items if oi["material"]))

        if material_ids:
            placeholders_m = ",".join(["?"] * len(material_ids))
            products = execute_query(
                f"""SELECT product, product_old_id, product_type, product_group
                    FROM [products]
                    WHERE product IN ({placeholders_m})""",
                tuple(material_ids),
            )

            prod_names = {p["product"]: p["product_old_id"] or p["product"] for p in products}

            for oi in order_items:
                mat = oi["material"]
                if mat:
                    prod_label = prod_names.get(mat, mat)
                    add_node(
                        f"prod_{mat}",
                        "Product",
                        prod_label,
                        {"product": mat, "product_old_id": prod_label},
                    )
                    so = str(int(oi["sales_order"])) if isinstance(oi["sales_order"], float) else str(oi["sales_order"])
                    add_edge(f"order_{so}", f"prod_{mat}", "contains")

    return {"nodes": nodes, "edges": edges}
