import sqlite3
conn = sqlite3.connect('o2c.db')
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in c.fetchall()]
print(f"Total tables: {len(tables)}")
print()
for t in tables:
    c.execute(f"SELECT COUNT(*) FROM [{t}]")
    cnt = c.fetchone()[0]
    print(f"  {t}: {cnt} rows")
conn.close()
