"""THE CHOKEPOINT — the one and only read path into the observation ledger.

This module exists so that grepping the worker package for a SELECT against the
observation table returns exactly ONE hit::

    grep -rn "FROM observ""ation" worker/     # (split here so this line is not itself the hit)

That one hit is :func:`read_observations`, below. Every other module in the
system — scoring, memo generation, timing, the demo.json builder — reads the
ledger through it and never touches the table directly. The public import path
is ``from worker.ledger import read_observations``; :mod:`worker.ledger`
re-exports this function so the chokepoint has one implementation and one
obvious name.

THE RULE THIS FILE ENFORCES
---------------------------
``read_observations`` takes a mandatory ``asof`` and always applies
``WHERE observed_at <= :asof`` before any other filter. There is no overload
without it and no hidden default of "now". Rows the world had not produced yet
at that instant are invisible — not down-weighted, not flagged, invisible.

That single predicate is what makes the system two products at once. Pass
``asof=now()`` and it is a live VC brain. Pass a past timestamp and the
*identical code path* is a point-in-time backtest with no hindsight leakage.
Trend is produced by re-scoring at ``asof-90 / -60 / -30 / 0`` over the same
ledger — computed, never asserted.

``observed_at`` is when the fact was true in the world. ``ingested_at`` is when
we found out. Only the first is ever used for point-in-time filtering; if the
two were confused, a backtest would silently see rows the past could not have
known, which is the exact failure the chokepoint exists to prevent.

Timestamps are stored as canonical ISO-8601 UTC strings (``YYYY-MM-DDTHH:MM:SSZ``)
so lexicographic comparison in SQL is identical to chronological comparison in
both SQLite and Postgres. :func:`worker.ledger.to_iso` is the only way a
timestamp enters the ledger, which is what makes the text comparison sound.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from worker import db as _db

ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


class LedgerViolation(RuntimeError):
    """Raised when something tries to modify, remove, or mis-read ledger rows."""


# --------------------------------------------------------------------------- #
# time — canonical, so that text comparison == chronological comparison
# --------------------------------------------------------------------------- #

def to_iso(value: datetime | str) -> str:
    """Normalize any timestamp to canonical ISO-8601 UTC (``...Z``)."""
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime(ISO_FMT)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime(ISO_FMT)


def parse_iso(value: str) -> datetime:
    return datetime.strptime(to_iso(value), ISO_FMT).replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# connection handling
# --------------------------------------------------------------------------- #

_CONN: sqlite3.Connection | None = None


def bind(conn: sqlite3.Connection) -> sqlite3.Connection:
    """Bind a connection for the module-level helpers to use."""
    global _CONN
    _CONN = conn
    return conn


def conn() -> sqlite3.Connection:
    """The bound connection, opening and applying the schema on first use."""
    global _CONN
    if _CONN is None:
        _CONN = _db.init_db()
    return _CONN


def open_ledger(db_path: str | None = None, *, reset: bool = False) -> sqlite3.Connection:
    """Open (optionally rebuild) the ledger and bind it."""
    c = _db.reset_db(db_path) if reset else _db.init_db(db_path=db_path)
    return bind(c)


def commit() -> None:
    conn().commit()


# --------------------------------------------------------------------------- #
# THE READ PATH — the only one
# --------------------------------------------------------------------------- #

# Columns of `observation` that may be used as equality filters. Anything not
# on this list is refused rather than silently ignored, because silently
# dropping a filter returns a WIDER set than the caller asked for — which in a
# scoring system means evidence the caller believed it had excluded.
_FILTERABLE = (
    "person_id",
    "org_id",
    "channel_id",
    "source",
    "source_class",
    "provenance_class",
    "claim_type",
    "artifact_type",
    "fetch_method",
    "is_milestone",
    "milestone_type",
)


def read_observations(
    asof: datetime | str,
    *,
    person_id: str | None = None,
    org_id: str | None = None,
    source_class: str | None = None,
    claim_type: str | None = None,
    limit: int | None = None,
    opportunity_id: str | None = None,
    channel_id: str | None = None,
    provenance_class: str | None = None,
    artifact_type: str | None = None,
    source: str | None = None,
    is_milestone: bool | None = None,
    milestone_type: str | None = None,
    order: str = "desc",
    connection: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    """Read the ledger as it stood at ``asof``. The only read path there is.

    ``asof`` is mandatory. ``WHERE observed_at <= :asof`` is applied first and
    unconditionally; every other argument narrows within that window.

    ``opportunity_id`` is not a column on ``observation`` — an observation is a
    fact about a person or an org, and an opportunity is a later interpretation
    of those facts. Filtering by it therefore resolves the opportunity to its
    ``person_id`` / ``org_id`` and filters on those, so that re-opening a second
    opportunity on the same person does not partition their history. If the
    opportunity carries neither key, no observation can belong to it and the
    result is empty rather than the whole ledger.

    Ordered by ``observed_at`` descending (newest first); pass ``order="asc"``
    for chronological reconstruction. Returns a list of plain dicts.
    """
    c = connection or conn()
    asof_iso = to_iso(asof)

    where = ["observed_at <= :asof"]
    params: dict[str, Any] = {"asof": asof_iso}

    if opportunity_id is not None:
        opp = c.execute(
            "SELECT person_id, org_id FROM opportunity WHERE opportunity_id = ?",
            (opportunity_id,),
        ).fetchone()
        if opp is None:
            raise LedgerViolation(
                f"No opportunity '{opportunity_id}'. Returning an unfiltered ledger "
                "for a bad id would attribute every observation in the system to it."
            )
        if opp["person_id"] is None and opp["org_id"] is None:
            return []
        person_id = person_id or opp["person_id"]
        org_id = org_id or opp["org_id"]

    supplied = {
        "person_id": person_id,
        "org_id": org_id,
        "channel_id": channel_id,
        "source": source,
        "source_class": source_class,
        "provenance_class": provenance_class,
        "claim_type": claim_type,
        "artifact_type": artifact_type,
        "is_milestone": None if is_milestone is None else int(bool(is_milestone)),
        "milestone_type": milestone_type,
    }
    available = set(_db.table_columns(c, "observation"))
    for column, value in supplied.items():
        if value is None:
            continue
        if column not in _FILTERABLE or column not in available:
            raise LedgerViolation(
                f"Cannot filter observations on '{column}': not an available column "
                "in the applied schema. Silently dropping a filter would return a "
                "wider set than the caller asked for."
            )
        where.append(f"{column} = :{column}")
        params[column] = value

    # An opportunity's observations are those of its person OR its org, not the
    # intersection: the outbound hero has person-keyed signals before the org
    # exists at all.
    if opportunity_id is not None and person_id and org_id:
        where = [w for w in where if not w.startswith(("person_id", "org_id"))]
        where.append("(person_id = :person_id OR org_id = :org_id)")

    direction = "DESC" if str(order).lower().startswith("d") else "ASC"
    sql = (
        "SELECT * FROM observation "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY observed_at {direction}, observation_id {direction}"
    )
    if limit is not None:
        sql += " LIMIT :limit"
        params["limit"] = int(limit)

    return c.execute(sql, params).fetchall()


def count_observations(asof: datetime | str, **filters: Any) -> int:
    """Convenience wrapper. Still goes through the one read path."""
    return len(read_observations(asof, **filters))


def first_observation_at(asof: datetime | str, **filters: Any) -> str | None:
    """Earliest visible ``observed_at`` at this asof — the 'first signal' clock."""
    rows = read_observations(asof, order="asc", limit=1, **filters)
    return rows[0]["observed_at"] if rows else None
