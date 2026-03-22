"""
ingest.py — Load SAP Order-to-Cash JSONL dataset into SQLite.

Usage:
    python ingest.py

This script:
  1. Walks every subdirectory under the dataset path
  2. Reads all .jsonl files per subdirectory
  3. Converts camelCase field names to snake_case
  4. Creates a SQLite table per subdirectory (DROP IF EXISTS → idempotent)
  5. Inserts all rows
  6. Prints a summary
"""

import json
import os
import re
import sqlite3
from pathlib import Path

# ─── Configuration ────────────────────────────────────────────────────────────
# Define paths relative to this script so it works on Render or any other machine
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data" / "sap-order-to-cash-dataset" / "sap-o2c-data"
DB_PATH = BASE_DIR / "o2c.db"

# ─── Helpers ──────────────────────────────────────────────────────────────────

def camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower()


def read_jsonl_files(directory: Path) -> list[dict]:
    """Read and concatenate all .jsonl files in a directory."""
    rows = []
    for fpath in sorted(directory.glob("*.jsonl")):
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


def infer_sql_type(value) -> str:
    """Infer a SQLite column type from a sample Python value."""
    if value is None:
        return "TEXT"
    if isinstance(value, bool):
        return "INTEGER"  # SQLite has no BOOLEAN; store as 0/1
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "REAL"
    # String values — try to detect numbers stored as strings
    if isinstance(value, str):
        try:
            float(value)
            return "REAL"
        except (ValueError, TypeError):
            pass
    return "TEXT"


def normalize_value(value):
    """Normalize a value for SQLite insertion."""
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    if value == "":
        return None
    return value


# ─── Main ingestion ──────────────────────────────────────────────────────────

def ingest():
    """Main entry point: read dataset, create tables, insert rows."""
    if not DATA_DIR.exists():
        print(f"ERROR: Dataset directory not found: {DATA_DIR}")
        return

    # Ensure output directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")

    subdirs = sorted([d for d in DATA_DIR.iterdir() if d.is_dir()])

    summary = []

    for subdir in subdirs:
        table_name = subdir.name  # e.g. "sales_order_headers"
        rows = read_jsonl_files(subdir)

        if not rows:
            print(f"  ⚠  {table_name}: no rows found, skipping.")
            continue

        # Discover columns from all rows (union of keys)
        all_keys_ordered: list[str] = []
        seen_keys: set[str] = set()
        for row in rows:
            for key in row.keys():
                if key not in seen_keys:
                    all_keys_ordered.append(key)
                    seen_keys.add(key)

        # Map camelCase → snake_case
        col_map = {k: camel_to_snake(k) for k in all_keys_ordered}
        snake_cols = [col_map[k] for k in all_keys_ordered]

        # Infer types from first non-null value per column
        col_types: dict[str, str] = {}
        for orig_key, snake_col in col_map.items():
            for row in rows:
                val = row.get(orig_key)
                if val is not None and val != "":
                    col_types[snake_col] = infer_sql_type(val)
                    break
            else:
                col_types[snake_col] = "TEXT"

        # Create table
        cursor.execute(f"DROP TABLE IF EXISTS [{table_name}];")
        col_defs = ", ".join(
            f"[{col}] {col_types[col]}" for col in snake_cols
        )
        create_sql = f"CREATE TABLE [{table_name}] ({col_defs});"
        cursor.execute(create_sql)

        # Insert rows
        placeholders = ", ".join(["?"] * len(snake_cols))
        insert_sql = f"INSERT INTO [{table_name}] VALUES ({placeholders});"

        batch = []
        for row in rows:
            values = tuple(normalize_value(row.get(k)) for k in all_keys_ordered)
            batch.append(values)

        cursor.executemany(insert_sql, batch)
        conn.commit()

        summary.append((table_name, len(rows), len(snake_cols)))
        print(f"  ✓  {table_name}: {len(rows)} rows, {len(snake_cols)} columns")

    conn.close()

    # Print summary
    print("\n" + "=" * 60)
    print(f"  DATABASE CREATED: {DB_PATH}")
    print(f"  TABLES: {len(summary)}")
    print("=" * 60)
    for tname, rcount, ccount in summary:
        print(f"    {tname:45s}  {rcount:>5} rows  {ccount:>3} cols")
    print("=" * 60)


if __name__ == "__main__":
    ingest()
