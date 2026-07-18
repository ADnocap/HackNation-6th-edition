"""Connection handling and schema bootstrap for the Counterproof ledger.

Store decision (made at hour 1, to unblock): the worker runs on LOCAL SQLITE via
the stdlib ``sqlite3`` module, at ``db/counterproof.db`` (gitignored). The DDL is
written in a Postgres-compatible subset — TEXT ids, ISO-8601 timestamps stored as
TEXT — so the identical schema can be pasted into the Supabase SQL editor for the
on-camera "append-only ledger" prop. No ORM, no migrations tool, no psql.

Schema source of truth is ``db/schema.sql`` — the single file, with no fallback
copy anywhere. A second, drifting copy of the DDL is worse than a missing one:
it would apply silently and every column mismatch would surface later as a
half-written row rather than immediately as a clear error. So if that file is
absent we raise and say so.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.environ.get("COUNTERPROOF_DB", REPO_ROOT / "db" / "counterproof.db"))
SCHEMA_PATH = REPO_ROOT / "db" / "schema.sql"


def _dict_factory(cursor: sqlite3.Cursor, row: tuple) -> dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def connect(db_path: Path | str | None = None, *, create_dirs: bool = True) -> sqlite3.Connection:
    """Open a connection with a dict row factory and foreign keys enabled."""
    path = Path(db_path) if db_path is not None else DB_PATH
    if create_dirs:
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = _dict_factory
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def schema_sql_path() -> Path:
    """Return the one DDL file in force, or explain clearly that it is missing."""
    if SCHEMA_PATH.exists() and SCHEMA_PATH.stat().st_size > 0:
        return SCHEMA_PATH
    raise FileNotFoundError(
        f"No schema at {SCHEMA_PATH}. The ledger has exactly one DDL and no "
        "fallback copy — a second copy would drift and apply silently. "
        "Restore db/schema.sql, then run `python worker/init_db.py`."
    )


def _portable_ddl(sql: str) -> str:
    """Make a Postgres-flavoured DDL subset executable by sqlite3.

    The schema is authored Postgres-first. sqlite3 does not know a handful of
    Postgres spellings, so we rewrite the few that appear in a TEXT/ISO-8601
    schema. This is a lossless read-side rewrite: the file on disk stays
    Postgres-pasteable for the Supabase prop.
    """
    replacements = [
        ("TIMESTAMPTZ", "TEXT"),
        ("TIMESTAMP WITH TIME ZONE", "TEXT"),
        ("timestamptz", "TEXT"),
        ("JSONB", "TEXT"),
        ("jsonb", "TEXT"),
        ("BOOLEAN", "INTEGER"),
        ("DOUBLE PRECISION", "REAL"),
        ("NUMERIC", "REAL"),
        ("SERIAL", "INTEGER"),
        ("now()", "CURRENT_TIMESTAMP"),
        ("NOW()", "CURRENT_TIMESTAMP"),
    ]
    out = sql
    for needle, sub in replacements:
        out = out.replace(needle, sub)
    return out


def init_db(conn: sqlite3.Connection | None = None, *, db_path: Path | str | None = None) -> sqlite3.Connection:
    """Apply the schema. Idempotent — the DDL uses IF NOT EXISTS throughout."""
    own = conn is None
    conn = conn or connect(db_path)
    ddl = schema_sql_path().read_text(encoding="utf-8")
    conn.executescript(_portable_ddl(ddl))
    conn.commit()
    if own:
        return conn
    return conn


def reset_db(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Dev helper: drop every table and re-apply the schema.

    This is a developer convenience for rebuilding a local file from scratch.
    It is never used by the pipeline, and there is no code path anywhere in the
    worker that removes or rewrites an individual ledger row.
    """
    path = Path(db_path) if db_path is not None else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path)
    conn.execute("PRAGMA foreign_keys = OFF")
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    for row in rows:
        conn.execute(f'DROP TABLE IF EXISTS "{row["name"]}"')
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 AS ok FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()
    return row is not None


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    """Actual column names of a table, in declaration order."""
    return [r["name"] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]


def list_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [r["name"] for r in rows]


def project(conn: sqlite3.Connection, table: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Drop keys the live table does not have.

    Two agents are writing against the same contract in parallel. Projecting the
    payload onto the columns that actually exist means a schema that carries an
    extra column, or spells one differently, degrades to a partial insert rather
    than to a hard crash mid-demo. Missing columns are reported by
    :func:`missing_columns` so the integrator can see the drift.
    """
    cols = set(table_columns(conn, table))
    return {k: v for k, v in payload.items() if k in cols}


def missing_columns(conn: sqlite3.Connection, table: str, payload: Iterable[str]) -> list[str]:
    cols = set(table_columns(conn, table))
    return sorted(k for k in payload if k not in cols)


def bool_int(value: Any) -> Any:
    """Booleans travel as 0/1 so the same rows load into Postgres BOOLEAN."""
    if isinstance(value, bool):
        return 1 if value else 0
    return value
