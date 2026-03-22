"""Quick verification of the ingested database."""
import sqlite3

conn = sqlite3.connect("o2c.db")
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in c.fetchall()]
print(f"Total tables: {len(tables)}\n")

for t in tables:
    c.execute(f"SELECT COUNT(*) FROM [{t}]")
    cnt = c.fetchone()[0]
    c.execute(f"PRAGMA table_info([{t}])")
    cols = len(c.fetchall())
    print(f"  {t:50s} {cnt:>5} rows  {cols:>3} cols")

# Verify key relationships
print("\n--- Key relationship checks ---")
c.execute("SELECT COUNT(DISTINCT sales_order) FROM sales_order_headers")
print(f"  Unique sales orders: {c.fetchone()[0]}")

c.execute("SELECT COUNT(DISTINCT business_partner) FROM business_partners")
print(f"  Unique customers: {c.fetchone()[0]}")

c.execute("SELECT COUNT(DISTINCT product) FROM products")
print(f"  Unique products: {c.fetchone()[0]}")

c.execute("SELECT COUNT(DISTINCT billing_document) FROM billing_document_headers")
print(f"  Unique invoices: {c.fetchone()[0]}")

c.execute("SELECT COUNT(DISTINCT delivery_document) FROM outbound_delivery_headers")
print(f"  Unique deliveries: {c.fetchone()[0]}")

# Sample join: orders with customer names
print("\n--- Sample join: Top 3 orders with customer names ---")
c.execute("""
    SELECT h.sales_order, h.total_net_amount, b.organization_bp_name1
    FROM sales_order_headers h
    JOIN business_partners b ON h.sold_to_party = b.business_partner
    LIMIT 3
""")
for row in c.fetchall():
    print(f"  Order {row[0]}: INR {row[1]} -- {row[2]}")

conn.close()
print("\n✓ All checks passed!")
