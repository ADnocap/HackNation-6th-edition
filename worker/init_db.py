"""Apply db/schema.sql to the local SQLite ledger.

    python worker/init_db.py           # create/refresh db/counterproof.db
    python worker/init_db.py --reset   # drop every table first

This is the command named in the contract's mechanical audits. It prints the
table list so the audit result is visible in the same output.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from worker import db  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Apply the Counterproof ledger schema.")
    ap.add_argument("--reset", action="store_true", help="drop every table first")
    ap.add_argument("--db", default=None, help="path to the sqlite file")
    args = ap.parse_args()

    conn = db.reset_db(args.db) if args.reset else db.init_db(db_path=args.db)
    tables = db.list_tables(conn)
    path = Path(args.db) if args.db else db.DB_PATH

    print(f"schema : {db.schema_sql_path()}")
    print(f"db     : {path}")
    print(f"tables : {len(tables)}")
    for name in tables:
        print(f"  - {name} ({len(db.table_columns(conn, name))} cols)")
    conn.commit()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
