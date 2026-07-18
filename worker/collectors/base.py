"""Shared plumbing for every sourcing collector.

Four collectors need the same four things, and doing them four inconsistent ways is how a
sourcing layer rots in a sprint. This module owns them:

1.  **Disk cache, keyed by content hash, from the first call.** Not "once it works". A second
    full run of the pipeline must make zero network calls — our API budget does not survive an
    uncached rebuild loop, and a cached run is what makes the demo safe when conference wifi
    dies. See ``fetch``.
2.  **Honest provenance.** Every row is badged ``live`` / ``fixture`` / ``synthetic`` so a judge
    can filter the board to real data on camera. A wrong badge is worse than no data, so the
    badge is a required argument, never a default.
3.  **One ledger write path.** Collectors call :func:`emit`, which wraps
    ``ledger.append_observation``. Nothing else. That is what keeps the append-only invariant
    and the ``asof`` chokepoint true for data nobody has written yet.
4.  **Channel registration**, so days-of-edge and the not-collected ledger are computed from the
    same table the collectors populate rather than from a second hand-maintained list.

THE DESIGN RULE, enforced here rather than remembered:
    A channel qualifies as *discovery* only if it can fire for a person with no GitHub, no
    funding and no network. :func:`register_channel` refuses to register a discovery channel
    with ``cold_start_native=False``. Ranking repos by stars is track-record sourcing with extra
    steps, and it rebuilds the exact network gate this project exists to replace. GitHub is
    still welcome as a ``confirmation`` channel keyed to a person we already found.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import httpx

from worker import ledger, store

# --------------------------------------------------------------------------- cache

CACHE_DIR = Path(__file__).resolve().parents[2] / "worker" / ".cache"
CACHE_TTL_SECONDS = 60 * 60 * 24 * 7  # a week; the sprint is a day, so effectively forever

USER_AGENT = (
    "Counterproof/0.1 (Hack-Nation 6th, Challenge 02; research prototype; "
    "contact via repo) httpx"
)


def _cache_key(method: str, url: str, params: dict[str, Any] | None) -> str:
    raw = json.dumps([method.upper(), url, params or {}], sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


@dataclass
class Fetched:
    """One HTTP retrieval, with everything a receipt needs to be checkable."""

    url: str
    final_url: str
    status: int
    text: str
    fetched_at: str
    from_cache: bool
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and 200 <= self.status < 300


def fetch(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: float = 20.0,
    force: bool = False,
    headers: dict[str, str] | None = None,
) -> Fetched:
    """GET a URL through the disk cache. Never raises — failure comes back as a ``Fetched``.

    A collector that raises on a dead link takes the whole run down at 3am. Every caller gets a
    result object and decides what a failure means; ``error`` is populated and ``ok`` is False.

    This is *retrieval*, deliberately distinct from search. It works on a page published ten
    minutes ago, which is precisely why receipts use this and not a search index.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = _cache_key("GET", url, params)
    path = cache_path(key)

    if path.exists() and not force:
        try:
            blob = json.loads(path.read_text(encoding="utf-8"))
            age = time.time() - blob.get("_cached_at", 0)
            if age < CACHE_TTL_SECONDS:
                return Fetched(
                    url=blob["url"],
                    final_url=blob["final_url"],
                    status=blob["status"],
                    text=blob["text"],
                    fetched_at=blob["fetched_at"],
                    from_cache=True,
                    error=blob.get("error"),
                )
        except (json.JSONDecodeError, KeyError, OSError):
            pass  # a corrupt cache entry is not worth a crash; refetch below

    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    hdrs = {"User-Agent": USER_AGENT, **(headers or {})}

    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=hdrs) as client:
            resp = client.get(url, params=params)
        result = Fetched(
            url=url,
            final_url=str(resp.url),
            status=resp.status_code,
            text=resp.text,
            fetched_at=fetched_at,
            from_cache=False,
        )
    except Exception as exc:  # noqa: BLE001 — a dead host must not end the run
        result = Fetched(
            url=url,
            final_url=url,
            status=0,
            text="",
            fetched_at=fetched_at,
            from_cache=False,
            error=f"{type(exc).__name__}: {exc}",
        )

    try:
        path.write_text(
            json.dumps(
                {
                    "_cached_at": time.time(),
                    "url": result.url,
                    "final_url": result.final_url,
                    "status": result.status,
                    "text": result.text,
                    "fetched_at": result.fetched_at,
                    "error": result.error,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass  # an unwritable cache is a slowdown, not a failure

    return result


def cache_stats() -> dict[str, int]:
    """How many responses are cached. The honesty panel can show this; so can a sanity check."""
    if not CACHE_DIR.exists():
        return {"entries": 0, "bytes": 0}
    entries = list(CACHE_DIR.glob("*.json"))
    return {"entries": len(entries), "bytes": sum(p.stat().st_size for p in entries)}


# --------------------------------------------------------------------------- channels


def register_channel(
    *,
    channel_id: str,
    channel_name: str,
    kind: str,
    cold_start_native: bool,
    status: str = "active",
    rationale: str | None = None,
    limitation: str | None = None,
    note: str | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Register a sourcing channel.

    Refuses a ``discovery`` channel that is not cold-start-native. This is the project's central
    design rule expressed as a guard rather than a comment: if a channel cannot fire for someone
    with no GitHub, no funding and no network, it is not discovery — it is confirmation, and
    calling it discovery would quietly rebuild the network gate.
    """
    if kind == "discovery" and not cold_start_native:
        raise ValueError(
            f"channel {channel_id!r} registered as 'discovery' but cold_start_native=False. "
            "A discovery channel must be able to fire for a founder with no GitHub, no funding "
            "and no network. Register it as kind='confirmation' instead (keyed to a person we "
            "already found), or as kind='declined' with a rationale for the not-collected ledger."
        )
    if kind == "declined" and not rationale:
        raise ValueError(
            f"channel {channel_id!r} is declined but has no rationale. The not-collected ledger "
            "scores better than a broken scraper only if it says WHY each source was declined."
        )

    stamp = observed_at or store.now_iso()
    return ledger.append_row(
        "channel",
        {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "kind": kind,
            "status": status,
            "cold_start_native": 1 if cold_start_native else 0,
            "rationale": rationale,
            "limitation": limitation,
            "note": note,
            "observed_at": stamp,
            "ingested_at": store.now_iso(),
        },
    )


# --------------------------------------------------------------------------- emit


@dataclass
class CollectorRun:
    """Bookkeeping for one collector run, so every number we print carries its ``n``."""

    channel_id: str
    emitted: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    people: set[str] = field(default_factory=set)

    def summary(self) -> str:
        cache = cache_stats()
        return (
            f"{self.channel_id}: emitted={self.emitted} people={len(self.people)} "
            f"skipped={self.skipped} errors={len(self.errors)} "
            f"cache_entries={cache['entries']}"
        )


def emit(
    run: CollectorRun,
    *,
    observed_at: str,
    source: str,
    source_class: str,
    provenance_class: str,
    person_id: str | None = None,
    **kwargs: Any,
) -> str | None:
    """Append one observation. The only write path a collector may use.

    ``observed_at`` is when the signal existed *in the world*, not when we fetched it. Getting
    this wrong silently breaks days-of-edge and every ``asof`` replay, because the whole system
    reads ``WHERE observed_at <= :asof``.
    """
    if provenance_class not in ("live", "fixture", "synthetic", "derived"):
        raise ValueError(
            f"provenance_class={provenance_class!r} is not one of live/fixture/synthetic/derived. "
            "A judge filters the board to 'live' on camera; a wrong badge is worse than no data."
        )
    try:
        observation_id = ledger.append_observation(
            observed_at=observed_at,
            source=source,
            source_class=source_class,
            provenance_class=provenance_class,
            person_id=person_id,
            channel_id=run.channel_id,
            **kwargs,
        )
        run.emitted += 1
        if person_id:
            run.people.add(person_id)
        return observation_id
    except Exception as exc:  # noqa: BLE001
        run.skipped += 1
        run.errors.append(f"{type(exc).__name__}: {exc}")
        return None


def thesis_sectors(default: Iterable[str] = ("b2b_fintech_infra", "vertical_saas", "devtools")) -> list[str]:
    """Sectors from the configured thesis, falling back to the seeded default.

    Collectors scan through the fund's lens rather than scraping the whole world — the Thesis
    Engine is meant to be load-bearing, not a filter bar bolted on at the end.
    """
    try:
        rows = store.conn().execute(
            "SELECT sectors FROM thesis ORDER BY observed_at DESC LIMIT 1"
        ).fetchone()
        if rows and rows["sectors"]:
            parsed = json.loads(rows["sectors"])
            if isinstance(parsed, list) and parsed:
                return [str(s) for s in parsed]
    except Exception:  # noqa: BLE001 — a missing thesis must not stop a collector
        pass
    return list(default)


def env(name: str, default: str | None = None) -> str | None:
    """Read an API key without importing dotenv everywhere."""
    value = os.environ.get(name)
    if value:
        return value
    envfile = Path(__file__).resolve().parents[2] / ".env"
    if envfile.exists():
        for line in envfile.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k.strip() == name:
                return v.strip().strip('"').strip("'")
    return default
