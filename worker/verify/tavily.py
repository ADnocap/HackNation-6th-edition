"""Tavily search — for entities ALREADY INDEXED on the public web. Nothing else.

TAVILY IS A SEARCH INDEX, NOT A FETCHER. That sentence is the entire reason this module
is separate from :mod:`worker.verify.fetch`, and the reason it refuses work rather than
doing it badly.

A search index can only return what it has crawled, whenever it last crawled it. Our
three fixture origins went live during this build. No index has seen them, and none will
before the deadline. So if receipt verification were routed through Tavily:

    * the query would succeed,
    * the API would return zero results,
    * and zero results renders *identically* to "we fetched the page and could not find
      the claim" — which is a different fact, and the opposite of true.

That is a silent, plausible-looking failure sitting directly under the peak of our demo.
:func:`search` therefore raises on a fixture origin and :func:`verify_indexed_entity`
refuses one, instead of returning an empty list that somebody downstream would render as
a finding. Guard, not comment.

WHAT TAVILY IS LEGITIMATELY FOR HERE
------------------------------------
Claims about entities that have been on the public web for months and are genuinely in
an index: a cited market comparable, a prior funding round, a competitor's stage. Those
are exactly the claims a direct fetch cannot help with, because we do not know which URL
to fetch — finding the URL is the task. That is search's job and it is good at it.

DEGRADES, NEVER CRASHES
-----------------------
``TAVILY_API_KEY`` is read from the environment (falling back to ``.env`` via
:func:`worker.collectors.base.env`). With no key, every entry point returns a result
object with ``available=False`` and a stated reason. It does not raise, and it does not
quietly return an empty result set that looks like a finding — a verification layer that
cannot distinguish "we looked and found nothing" from "we never looked" is worse than no
verification layer at all.

Responses are cached to disk beside every other external response, keyed by content
hash, so a re-run costs nothing against a credit budget that does not survive a loop.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from worker.collectors import base
from worker.verify import fetch as _fetch

API_URL = "https://api.tavily.com/search"
ENV_KEY = "TAVILY_API_KEY"
CACHE_TTL_SECONDS = base.CACHE_TTL_SECONDS


@dataclass
class SearchResult:
    """One Tavily call. ``available`` is False when we never actually looked.

    The distinction ``available=False`` (no key / refused) versus ``available=True`` with
    an empty ``results`` list is load-bearing. The first means we did not check. The
    second means we checked and the public web has nothing. Rendering them the same way
    is the failure this class exists to prevent.
    """

    query: str
    available: bool
    results: list[dict[str, Any]] = field(default_factory=list)
    answer: str | None = None
    reason: str | None = None
    fetched_at: str = ""
    from_cache: bool = False
    error: str | None = None

    @property
    def n(self) -> int:
        return len(self.results)


def api_key() -> str | None:
    """The Tavily key, or None. Never raises, never prints the key."""
    return base.env(ENV_KEY)


def is_available() -> bool:
    return bool(api_key())


def _unavailable(query: str, reason: str) -> SearchResult:
    return SearchResult(
        query=query,
        available=False,
        reason=reason,
        fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def _cached_post(payload: dict[str, Any], *, timeout: float) -> tuple[dict[str, Any] | None, bool, str, str | None]:
    """POST to Tavily through the shared on-disk cache.

    :func:`worker.collectors.base.fetch` is GET-only and Tavily's search endpoint is a
    POST, so the request itself is made here — but the cache directory, the TTL and the
    blob shape are base's, so there is exactly one place on disk where external
    responses live and one thing to delete to force a refresh. The API key is hashed
    into the cache key but never written into the cached blob.
    """
    keyed = {k: v for k, v in payload.items() if k != "api_key"}
    raw = json.dumps(["POST", API_URL, keyed], sort_keys=True)
    key = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    path = base.cache_path(key)
    base.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if path.exists():
        try:
            blob = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - blob.get("_cached_at", 0) < CACHE_TTL_SECONDS:
                return blob.get("body"), True, blob.get("fetched_at", ""), blob.get("error")
        except (json.JSONDecodeError, KeyError, OSError):
            pass

    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body: dict[str, Any] | None = None
    error: str | None = None
    try:
        with httpx.Client(timeout=timeout, headers={"User-Agent": base.USER_AGENT}) as client:
            resp = client.post(API_URL, json=payload)
        if resp.status_code >= 400:
            error = f"HTTP {resp.status_code}: {resp.text[:200]}"
        else:
            body = resp.json()
    except Exception as exc:  # noqa: BLE001 — a search outage must not end a run
        error = f"{type(exc).__name__}: {exc}"

    try:
        path.write_text(
            json.dumps(
                {"_cached_at": time.time(), "fetched_at": fetched_at, "body": body, "error": error},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass

    return body, False, fetched_at, error


def search(
    query: str,
    *,
    max_results: int = 5,
    search_depth: str = "basic",
    include_domains: list[str] | None = None,
    timeout: float = 25.0,
) -> SearchResult:
    """Search the public web for an entity that has been indexed for months.

    Refuses a query aimed at a fixture origin. That refusal is the whole point of this
    module existing separately: a fixture lookup here would succeed as an API call and
    fail as a fact, and the two are indistinguishable downstream.
    """
    for origin in _fetch.FIXTURE_ORIGINS:
        host = origin.split("//", 1)[-1]
        if host in query or host in " ".join(include_domains or []):
            raise ValueError(
                f"Refusing to search Tavily for {host!r}. Tavily is a search INDEX and "
                "has never crawled our fixture origins — this query would return zero "
                "results, which renders identically to 'we fetched it and the claim was "
                "not there'. Use worker.verify.fetch.retrieve() for that URL: it asks "
                "the origin server and works on a page published ten minutes ago."
            )

    key = api_key()
    if not key:
        return _unavailable(
            query,
            f"{ENV_KEY} is not set, so no search was performed. This is 'we did not "
            "look', which is NOT the same as 'we looked and found nothing' — the "
            "verification layer reports the difference rather than hiding it.",
        )

    payload: dict[str, Any] = {
        "api_key": key,
        "query": query,
        "max_results": int(max_results),
        "search_depth": search_depth,
        "include_answer": True,
    }
    if include_domains:
        payload["include_domains"] = include_domains

    body, from_cache, fetched_at, error = _cached_post(payload, timeout=timeout)
    if error or body is None:
        return SearchResult(
            query=query,
            available=False,
            reason=f"Tavily call failed, so nothing was checked: {error}",
            fetched_at=fetched_at,
            from_cache=from_cache,
            error=error,
        )

    results = [
        {
            "title": r.get("title"),
            "url": r.get("url"),
            "content": r.get("content"),
            "score": r.get("score"),
        }
        for r in (body.get("results") or [])
    ]
    return SearchResult(
        query=query,
        available=True,
        results=results,
        answer=body.get("answer"),
        fetched_at=fetched_at,
        from_cache=from_cache,
    )


def verify_indexed_entity(
    entity: str,
    assertion: str,
    *,
    max_results: int = 5,
) -> dict[str, Any]:
    """Look for public-web support for one assertion about one long-indexed entity.

    Intended callers are market-comparable and prior-round claims — "Acme raised a
    Series A at €40M post" — where we do not know the URL in advance and finding it is
    the work. Returns a dict carrying the query, the hits with their URLs, and an
    explicit ``checked`` flag so a caller can never mistake an unchecked claim for a
    refuted one.

    It deliberately does NOT emit a verdict. Deciding whether a snippet supports a claim
    is scoring, and scoring lives in :mod:`worker.scoring.trust` behind a published
    reliability table. This function's job is to hand that module cited URLs.
    """
    query = f"{entity} {assertion}".strip()
    res = search(query, max_results=max_results)
    return {
        "entity": entity,
        "assertion": assertion,
        "query": query,
        "checked": res.available,
        "n_results": res.n,
        "reason": res.reason,
        "answer": res.answer,
        "fetched_at": res.fetched_at,
        "from_cache": res.from_cache,
        "verifier": "tavily",
        "fetch_method": "tavily_search",
        "source_class": "press",
        "results": res.results,
        "note": (
            "Search index, not a retrieval. Applies only to entities already indexed on "
            "the public web; our own fixture origins are refused by this module."
        ),
    }


def status() -> dict[str, Any]:
    """Whether Tavily is usable, for the honesty panel. Safe to call with no key."""
    available = is_available()
    return {
        "mechanism": "tavily_search",
        "available": available,
        "env_var": ENV_KEY,
        "scope": "entities already indexed on the public web (comparables, prior rounds)",
        "excluded": list(_fetch.FIXTURE_ORIGINS),
        "reason": (
            None
            if available
            else f"{ENV_KEY} not set — search-backed checks report 'not checked', never 'not found'."
        ),
        "why_not_receipts": (
            "Tavily has never crawled our fixture origins, so a receipt routed through "
            "it would return zero results and look exactly like a failed verification. "
            "Receipts go through worker.verify.fetch, which asks the origin server."
        ),
    }
