"""
db.py — Database helper for the Order-to-Cash system.

Provides:
  - get_connection()    → sqlite3.Connection
  - execute_query(sql)  → list[dict]
  - get_schema_summary() → str  (used by LLM prompt)
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(r"e:\dodge ai\backend\o2c.db")


def get_connection() -> sqlite3.Connection:
    """Return a connection to the O2C database."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def execute_query(sql: str, params: tuple | list | None = None) -> list[dict]:
    """Execute a SQL query and return results as a list of dicts."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return rows
    finally:
        conn.close()


def get_schema_summary() -> str:
    """
    Return a formatted string describing every table,
    its columns (with types), row count, and sample values.
    This is fed into the LLM system prompt so it can write SQL.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row[0] for row in cursor.fetchall()]

    lines = []
    lines.append("=== DATABASE SCHEMA ===\n")

    for table in tables:
        # Row count
        cursor.execute(f"SELECT COUNT(*) FROM [{table}];")
        count = cursor.fetchone()[0]

        # Column info
        cursor.execute(f"PRAGMA table_info([{table}]);")
        columns = cursor.fetchall()

        lines.append(f"TABLE: {table} ({count} rows)")
        lines.append("-" * 50)

        # Get one sample row for context
        cursor.execute(f"SELECT * FROM [{table}] LIMIT 1;")
        sample_row = cursor.fetchone()

        for col in columns:
            col_name = col[1]
            col_type = col[2]
            sample_val = ""
            if sample_row:
                idx = col[0]
                val = sample_row[idx]
                if val is not None:
                    sample_val = f" (e.g. {repr(val)[:60]})"
            lines.append(f"  {col_name} {col_type}{sample_val}")

        lines.append("")

    conn.close()
    return "\n".join(lines)


def get_schema_json() -> list[dict]:
    """
    Return structured schema info as a list of dicts.
    Each dict: { table, row_count, columns: [{ name, type }] }
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row[0] for row in cursor.fetchall()]

    result = []
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM [{table}];")
        count = cursor.fetchone()[0]

        cursor.execute(f"PRAGMA table_info([{table}]);")
        columns = [{"name": col[1], "type": col[2]} for col in cursor.fetchall()]

        result.append({
            "table": table,
            "row_count": count,
            "columns": columns,
        })

    conn.close()
    return result


if __name__ == "__main__":
    print(get_schema_summary())
