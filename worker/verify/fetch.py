"""The receipt backend — retrieval, not search.

A direct ``httpx.get`` of one specific URL, returning the body, the final URL after
redirects, the HTTP status and the fetch timestamp. Everything the receipt pane needs to
be checkable by somebody who does not trust us.

It delegates the actual request to :func:`worker.collectors.base.fetch`, which means
every response is cached to disk by content hash from the first call. A second run of
the whole pipeline makes zero network calls, so the demo survives conference wifi and
our API budget survives a rebuild loop.

WHY THIS IS NOT TAVILY
----------------------
This mechanism works on a page published ten minutes ago, because it goes and asks the
origin server. A search index cannot do that — it can only tell you what it crawled,
whenever it last crawled it. Our fixture sites went live during the build; no index has
seen them. Receipt verification therefore goes through here and nowhere else. See
:mod:`worker.verify.tavily` for the other half of that rule.

RESERVED TLDs ARE SKIPPED, NEVER FAILED
---------------------------------------
Some evidence in the ledger cites ``.example`` / ``.test`` hosts. Those TLDs are
reserved by RFC 2606 precisely so they can never resolve — the URLs are illustrative
stand-ins for sources we are describing but did not fetch. Reporting them as failures
would be reporting our own documentation convention as a bug, so :func:`is_reserved`
identifies them and the auditor skips them with a stated reason.
"""

from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit

from worker.collectors import base

#: RFC 2606 / RFC 6761 reserved TLDs. Guaranteed never to resolve, by design.
#: A URL on one of these is illustrative, not a retrieval target.
RESERVED_TLDS = ("example", "test", "invalid", "localhost")

#: Origins Wacil deployed for the demo. Real hosts, real HTTP, real 404s.
FIXTURE_ORIGINS = (
    "https://ledgerline-sage.vercel.app",
    "https://northgate-three.vercel.app",
    "https://kestrelops.vercel.app",
)

_SCRIPT_STYLE = re.compile(
    r"<(script|style|noscript)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL
)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


@dataclass
class Receipt:
    """One retrieval, with everything needed to re-check it independently.

    ``text`` is the raw response body. ``visible_text`` is the body with script and
    style blocks removed, tags stripped and entities unescaped — the words a human
    actually sees, which is what an excerpt should be matched against. Matching against
    raw HTML would let a claim "verify" off a CSS rule or a meta tag.
    """

    url: str
    final_url: str
    status: int
    text: str
    visible_text: str
    fetched_at: str
    from_cache: bool
    error: str | None = None
    skipped_reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and 200 <= self.status < 300

    @property
    def not_found(self) -> bool:
        """A 404 is a first-class outcome here, not an error.

        Some of our evidence is ``absent_but_expected``: we predicted a page would not
        exist and went and confirmed it does not. ``/careers`` on Ledgerline and
        ``/changelog`` on Northgate return genuine 404s from a genuine host, and that
        404 IS the evidence. Collapsing it into "error" would delete the finding.
        """
        return self.error is None and self.status == 404

    @property
    def redirected(self) -> bool:
        return bool(self.final_url) and self.final_url.rstrip("/") != self.url.rstrip("/")


def is_reserved(url: str) -> bool:
    """True for URLs on a reserved TLD, which can never resolve and never should."""
    host = (urlsplit(url).hostname or "").lower()
    return any(host == t or host.endswith("." + t) for t in RESERVED_TLDS)


def is_fixture_origin(url: str) -> bool:
    """True for the three origins deployed for this demo."""
    u = url.lower()
    return any(u.startswith(o) for o in FIXTURE_ORIGINS)


def visible_text(body: str) -> str:
    """Body → the words a reader sees. Script/style dropped, tags stripped, entities decoded.

    Northgate and Kestrel inline their whole stylesheet in a ``<style>`` block, so a
    naive tag-strip leaves several hundred words of CSS in the haystack — enough for a
    token like ``640`` (a border radius, a font size) to make an unrelated pricing claim
    look corroborated. Dropping those blocks first is what keeps a match meaningful.
    """
    if not body:
        return ""
    stripped = _SCRIPT_STYLE.sub(" ", body)
    stripped = _TAG.sub(" ", stripped)
    return _WS.sub(" ", _html.unescape(stripped)).strip()


def retrieve(url: str, *, force: bool = False, timeout: float = 20.0) -> Receipt:
    """GET one URL through the shared disk cache. Never raises.

    Returns a :class:`Receipt` in every case, including transport failure — a dead host
    must not take down a verification pass over thirty rows. Reserved-TLD URLs are not
    requested at all; they come back with ``skipped_reason`` set.
    """
    if is_reserved(url):
        return Receipt(
            url=url,
            final_url=url,
            status=0,
            text="",
            visible_text="",
            fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            from_cache=False,
            skipped_reason=(
                "reserved TLD (RFC 2606) — deliberately unresolvable, illustrative "
                "placeholder rather than a source we fetched"
            ),
        )

    f = base.fetch(url, force=force, timeout=timeout)
    return Receipt(
        url=f.url,
        final_url=f.final_url,
        status=f.status,
        text=f.text,
        visible_text=visible_text(f.text),
        fetched_at=f.fetched_at,
        from_cache=f.from_cache,
        error=f.error,
    )


def receipt_dict(r: Receipt) -> dict[str, object]:
    """The receipt as the frontend and the evidence row want it.

    Keys line up with ``evidence`` columns in ``db/schema.sql`` — ``source_url``,
    ``final_url``, ``http_status``, ``fetched_at``, ``fetch_method`` — so an integrator
    can attach this to a row without a translation layer.
    """
    return {
        "source_url": r.url,
        "final_url": r.final_url,
        "http_status": r.status,
        "fetched_at": r.fetched_at,
        "fetch_method": "httpx_get",
        "verifier": "httpx_direct",
        "from_cache": r.from_cache,
        "redirected": r.redirected,
        "error": r.error,
        "skipped_reason": r.skipped_reason,
        "n_chars": len(r.text),
    }
