"""Hacker News sourcing, via the Algolia index — the cheapest genuinely cold-start channel.

WHY THIS CHANNEL EXISTS
-----------------------
Hacker News is the one large, free, keyless corpus where a person with no GitHub, no funding
and no network still leaves a dated, quotable, first-person artifact. That is the whole
definition of a *discovery* channel in this project, so ``ch_hn`` registers as
``cold_start_native=True`` and means it: nothing here requires the author to already be
someone. The Algolia endpoint gives second-resolution unix timestamps over complete history,
which is what makes days-of-edge arithmetic possible at all.

WHAT WE DELIBERATELY DO NOT DO
------------------------------
We do not read the front page, and we never look at points, karma, or comment counts. Those
fields are stripped from every hit by :func:`_strip_popularity` BEFORE scoring, so a future
edit cannot quietly reintroduce them: ranking by points is track-record sourcing with extra
steps, and it rebuilds the exact consensus gate this project exists to replace. The front page
is, by construction, the set of people everybody has already seen — zero days of edge.

WHAT WE SCORE INSTEAD: THE TEXT
-------------------------------
A comment earns a row on evidence of *lived domain exposure* — the operational detail someone
only writes down if they have actually done the work. Five signals, none of them social:

    substance     how much they actually said (length, floored at MIN_CHARS)
    specificity   quantified claims: numbers with units, money, versions, latencies
    entities      named systems and standards (ACH, HL7 FHIR, p99, Bazel, ISO 20022, ...)
    lived         first-person operational markers ("we migrated", "in production", "on-call")
    sector        affinity with the configured thesis sectors, so we scan through the fund's lens

``lived`` carries the largest weight. The rationale for every emitted row is appended to
``raw_excerpt`` behind a ``[text-signal]`` marker so a judge can ask "why did this fire?" and
get a per-row answer that contains no popularity term.

THE THREE SURFACES SCANNED
--------------------------
1. Deep sector threads (``tags=comment``), queried from :func:`base.thesis_sectors`.
2. ``Show HN`` launches (``tags=show_hn``) — a shipped artifact with a real timestamp, and the
   product URL is handed downstream to the domain reader as a candidate.
3. "Who wants to be hired" threads — operator history, self-reported, dated, no network needed.

Then, for the strongest candidates only (the request budget is small on purpose), one probe per
author against ``tags=author_<handle>`` yields two further FACTS, not opinions: when the account
first spoke, and how many items it has. A young account with a small footprint writing a long,
specific, operationally-detailed comment is precisely the person the consensus channels cannot
see yet.

Run it::

    uv run python -m worker.collectors.hn
"""

from __future__ import annotations

import html
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from worker import ledger, store
from worker.collectors import base

# --------------------------------------------------------------------------- constants

CHANNEL_ID = "ch_hn"
SOURCE = "hn_algolia"
API = "https://hn.algolia.com/api/v1/search_by_date"
ITEM_URL = "https://news.ycombinator.com/item?id={}"
USER_URL = "https://news.ycombinator.com/user?id={}"

# Politeness. The Algolia HN endpoint is free and keyless; the only way to abuse it is a
# runaway loop, so the cap is hard and counted rather than hoped for. Both the first and the
# second run make exactly the same number of fetch() calls — the second just serves them all
# from disk — which is what keeps the demo safe when conference wifi dies.
MAX_REQUESTS = 30
REQUEST_DELAY_S = 0.4          # applied only after a real network call, never after a cache hit
HITS_PER_PAGE = 50             # modest page size for the corpus scans
PROBE_HITS_PER_PAGE = 100      # one probe request per author instead of paging them

COMMENT_QUERY_BUDGET = 12
SHOW_HN_QUERY_BUDGET = 3
HIRING_BUDGET = 3
AUTHOR_PROBE_LIMIT = 10
SHOW_HN_PROBE_SLOTS = 6        # the rest go to quiet, high-signal commenters

# Text thresholds. Tuned to the corpus, not to a popularity distribution.
MIN_CHARS = 320
SCORE_THRESHOLD = 0.42
# A "who wants to be hired" thread is already pre-filtered to people describing their own
# operator history, so the prose bar is lower there — the structured template IS the signal.
HIRING_SCORE_THRESHOLD = 0.30
SUBSTANCE_CEILING = 2200
MAX_PER_AUTHOR = 4             # one prolific commenter must not crowd out ten quiet ones
NEW_ACCOUNT_DAYS = 90
LOW_FOOTPRINT_ITEMS = 60

EXCERPT_CHARS = 1200
VALUE_CHARS = 240

# Fields that encode how many other people already noticed this person. Removed before the
# scorer ever sees a hit. This is the anti-popularity rule expressed as code rather than as a
# comment someone can forget.
_POPULARITY_FIELDS = ("points", "num_comments", "children", "relevancy_score")


# --------------------------------------------------------------------------- thesis lexicon

# Queries and vocabulary per thesis sector. The Thesis Engine is meant to be load-bearing, so
# an unrecognised sector degrades to a keyword scan built from the sector's own name rather
# than to silence — reconfiguring the fund changes what this collector looks for.
SECTOR_LEXICON: dict[str, dict[str, list[str]]] = {
    "b2b_fintech_infra": {
        "show_queries": ["payments"],
        "queries": [
            "ACH payments",
            "payment reconciliation",
            "double-entry ledger",
            "KYC onboarding",
            "card issuing",
            "chargeback disputes",
            "ISO 20022",
            "merchant underwriting",
        ],
        "terms": [
            "ach", "sepa", "iso 20022", "interchange", "chargeback", "reconciliation",
            "ledger", "double-entry", "settlement", "kyc", "kyb", "aml", "pci", "psd2",
            "acquirer", "issuer", "underwriting", "payout", "stripe", "adyen", "plaid",
            "idempotency", "nacha", "fedwire", "swift", "escrow", "bin sponsor", "ledgering",
            "chargeback ratio", "3ds", "sca", "open banking", "custody",
        ],
    },
    "vertical_saas": {
        "show_queries": ["workflow"],
        "queries": [
            "practice management software",
            "EHR integration",
            "dispatch software",
            "field service software",
            "HL7 FHIR",
            "restaurant POS",
            "construction software",
        ],
        "terms": [
            "ehr", "emr", "hl7", "fhir", "hipaa", "claims", "edi", "837", "dispatch",
            "route planning", "pos", "inventory", "scheduling", "work order", "audit trail",
            "erp", "broker", "carrier", "tms", "clinic", "practice", "prior authorization",
            "reimbursement", "procurement", "compliance", "seat", "churn", "onboarding",
        ],
    },
    "devtools": {
        "show_queries": ["devtools"],
        "queries": [
            "CI pipeline flaky",
            "observability tracing",
            "build system caching",
            "developer experience tooling",
            "kubernetes operator",
            "static analysis",
        ],
        "terms": [
            "ci", "cd", "pipeline", "flaky", "observability", "tracing", "opentelemetry",
            "span", "profiler", "build cache", "bazel", "monorepo", "lsp", "compiler",
            "linter", "sdk", "kubernetes", "container", "latency", "p99", "p95", "throughput",
            "rollback", "canary", "feature flag", "telemetry", "sre", "runbook", "toolchain",
        ],
    },
}

# Named systems and standards that appear across every sector. Presence of these is an
# *entity* signal, not a quality signal — it says the author is talking about a specific thing
# rather than about a category.
GENERIC_ENTITY_TERMS: tuple[str, ...] = (
    "postgres", "postgresql", "mysql", "sqlite", "redis", "kafka", "rabbitmq", "clickhouse",
    "elasticsearch", "dynamodb", "s3", "aws", "gcp", "azure", "cloudflare", "nginx", "envoy",
    "docker", "terraform", "ansible", "graphql", "grpc", "rest api", "webhook", "oauth",
    "saml", "soc 2", "gdpr", "hipaa", "cron", "celery", "sidekiq", "django", "rails",
    "kubernetes", "lambda", "airflow", "dbt", "snowflake", "databricks", "twilio", "sendgrid",
    "stripe", "salesforce", "hubspot", "netsuite", "quickbooks", "sap", "oracle",
)

# First-person operational markers. Each distinct pattern that fires counts once — a comment
# that says "we migrated ... in production ... at my last company" has three independent
# markers of having been there, which is worth far more than one marker repeated ten times.
LIVED_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bwe (ran|run|built|migrated|shipped|deployed|switched|rewrote|handled?|processed?|ended up|had to|tried)\b",
        r"\bi (built|wrote|ran|shipped|maintained|debugged|migrated|implemented|spent|managed|rebuilt)\b",
        r"\bin production\b",
        r"\bon-?call\b",
        r"\bpost-?mortem\b",
        r"\b(outage|incident|regression|downtime)\b",
        r"\bat my (last|previous|old) (job|company|startup|gig)\b",
        r"\b(when|while) i (was|worked) at\b",
        r"\bi(?:'ve| have) (been|worked|spent|shipped|seen)\b",
        r"\bour (customers|users|clients|team|stack|infra|pipeline)\b",
        r"\bwe (learned|found|discovered|realised|realized)\b",
        r"\bthe hard way\b",
        r"\bmy (co-?founder|startup|company|team)\b",
        r"\bwe were (doing|running|using|paying)\b",
        r"\b(currently|used to) (work|build|run|maintain)\b",
        r"\bi (do|did) this (for|at)\b",
        r"\bfrom experience\b",
        r"\bwe (charge|bill|invoice|onboard)\b",
    )
)

# Quantified-claim detectors. Specificity is what separates "reconciliation is hard" from
# "reconciliation drifted about 40bps a month until we moved to a double-entry ledger".
NUMERIC_UNIT_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s?"
    r"(?:ms|µs|us|ns|sec|secs|seconds?|mins?|minutes?|hrs?|hours?|days?|weeks?|months?|years?|"
    r"k|m|b|kb|mb|gb|tb|qps|rps|rpm|req/s|reqs?|tps|bps|%|x|percent|users?|customers?|"
    r"employees?|engineers?|seats?|tenants?|rows?|records?|nodes?|instances?|cores?)\b",
    re.IGNORECASE,
)
MONEY_RE = re.compile(r"[$€£¥]\s?\d[\d,.]*\s?[kmb]?\b", re.IGNORECASE)
VERSION_RE = re.compile(r"\bv?\d+\.\d+(?:\.\d+)?\b")
URL_RE = re.compile(r"https?://\S+")
QUOTE_LINE_RE = re.compile(r"^\s*>", re.MULTILINE)

# The monthly thread, not the meta-threads that discuss it. "Tell HN: 'Who wants to be hired'
# posts outpace 'Who's hiring'" is a conversation ABOUT the thread and contains no operator
# history at all, which is exactly what an unanchored substring match pulls in.
HIRING_TITLE_RE = re.compile(r"^\s*ask hn:\s*who wants to be hired", re.IGNORECASE)

# The self-description template these threads use, in both its labelled and pipe-delimited
# forms. Three or more of these fields is a structured operator record whether or not the
# author also wrote reflective prose.
HIRING_FIELD_RE = re.compile(
    r"(?:^|\n|\|)\s*(location|remote|willing to relocate|relocate|technologies|tech stack|"
    r"stack|r[ée]sum[ée]|resume|cv|email|linkedin|github|website|availability|seeking|role)\s*[:|]",
    re.IGNORECASE,
)
HIRING_HEADER_RE = re.compile(r"^[^\n|]{2,60}\|[^\n|]{2,60}\|", re.MULTILINE)

_TAG_RE = re.compile(r"<[^>]+>")


# --------------------------------------------------------------------------- text handling

def clean_html(raw: str | None) -> str:
    """Algolia returns HN's stored HTML. Strip it to the words the person actually typed."""
    if not raw:
        return ""
    text = raw.replace("</p>", "\n\n").replace("<p>", "\n\n")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _one_line(text: str, limit: int) -> str:
    flat = re.sub(r"\s+", " ", text).strip()
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def _strip_popularity(hit: dict[str, Any]) -> dict[str, Any]:
    """Return the hit with every social-proof field removed.

    The scorer is only ever handed the output of this function. If someone later adds a
    ``points``-based term to :func:`score_text`, it will read ``None`` and do nothing, which is
    the intended outcome: popularity is the one input this channel refuses.
    """
    return {k: v for k, v in hit.items() if k not in _POPULARITY_FIELDS and not k.startswith("_")}


def _clamp(value: float) -> float:
    return 0.0 if value < 0 else (1.0 if value > 1 else value)


@dataclass
class TextSignal:
    """The per-row explanation of why a comment earned a ledger row."""

    score: float
    chars: int
    specificity_hits: int
    entities: list[str]
    lived_markers: int
    sector_terms: list[str]

    def rationale(self) -> str:
        ents = ", ".join(self.entities[:6]) or "none"
        sect = ", ".join(self.sector_terms[:5]) or "none"
        return (
            f"[text-signal] score={self.score:.2f} chars={self.chars} "
            f"lived-exposure-markers={self.lived_markers} quantified-claims={self.specificity_hits} "
            f"entities=[{ents}] thesis-terms=[{sect}] "
            f"(scored on text only; points/karma/comment-count never read)"
        )


def score_text(text: str, sector_terms: Iterable[str]) -> TextSignal:
    """Score an utterance for evidence of lived domain exposure. No popularity input exists.

    Weights put ``lived`` first on purpose. Length alone is a blog post; numbers alone are a
    press release; the combination of a first-person operational claim WITH a number WITH a
    named system is what an actual practitioner writes and what a commentator cannot fake
    cheaply.
    """
    chars = len(text)
    lower = text.lower()

    substance = _clamp((chars - MIN_CHARS) / float(SUBSTANCE_CEILING - MIN_CHARS))

    spec_hits = (
        len(NUMERIC_UNIT_RE.findall(text))
        + len(MONEY_RE.findall(text))
        + len(VERSION_RE.findall(text))
    )
    specificity = _clamp(spec_hits / 6.0)

    entities = sorted({term for term in GENERIC_ENTITY_TERMS if term in lower})
    entity_score = _clamp(len(entities) / 5.0)

    lived_markers = sum(1 for pattern in LIVED_PATTERNS if pattern.search(text))
    lived = _clamp(lived_markers / 3.0)

    matched_sector = sorted({term for term in sector_terms if term in lower})
    sector_affinity = _clamp(len(matched_sector) / 2.0)

    score = (
        0.20 * substance
        + 0.20 * specificity
        + 0.20 * entity_score
        + 0.30 * lived
        + 0.10 * sector_affinity
    )

    # A comment that is mostly links is a pointer, not testimony. A comment that is mostly
    # quoted text is somebody else's testimony.
    link_chars = sum(len(m) for m in URL_RE.findall(text))
    if chars and link_chars / chars > 0.25:
        score *= 0.6
    if len(QUOTE_LINE_RE.findall(text)) >= 4:
        score *= 0.8

    return TextSignal(
        score=round(score, 4),
        chars=chars,
        specificity_hits=spec_hits,
        entities=entities,
        lived_markers=lived_markers,
        sector_terms=matched_sector,
    )


# --------------------------------------------------------------------------- fetching

@dataclass
class Budget:
    """A counted request cap. A runaway loop cannot hammer a free keyless API past this."""

    limit: int
    used: int = 0
    network: int = 0
    cached: int = 0
    failures: int = 0

    def spend(self) -> bool:
        if self.used >= self.limit:
            return False
        self.used += 1
        return True


def _hit_time(hit: dict[str, Any]) -> str | None:
    """The instant the signal existed IN THE WORLD, to the second.

    ``created_at_i`` is HN's unix timestamp and is preferred: it is unambiguous and it is what
    makes days-of-edge arithmetic exact. This value becomes ``observed_at``. Using fetch time
    here instead would silently break every asof replay in the system.
    """
    stamp = hit.get("created_at_i")
    if stamp:
        try:
            return datetime.fromtimestamp(int(stamp), tz=timezone.utc).strftime(store.ISO_FMT)
        except (ValueError, OSError, OverflowError):
            pass
    if hit.get("created_at"):
        try:
            return store.to_iso(hit["created_at"])
        except (ValueError, TypeError):
            return None
    return None


def search(budget: Budget, params: dict[str, Any]) -> tuple[list[dict[str, Any]], int, base.Fetched | None]:
    """One Algolia page through the disk cache. Returns (hits, nbHits, receipt)."""
    if not budget.spend():
        return [], 0, None

    fetched = base.fetch(API, params=params)
    if fetched.from_cache:
        budget.cached += 1
    else:
        budget.network += 1
        time.sleep(REQUEST_DELAY_S)  # only a real call earns a delay; a cached run stays fast

    if not fetched.ok:
        budget.failures += 1
        return [], 0, fetched
    try:
        payload = json.loads(fetched.text)
    except json.JSONDecodeError:
        budget.failures += 1
        return [], 0, fetched
    hits = payload.get("hits") or []
    return [_strip_popularity(h) for h in hits], int(payload.get("nbHits") or 0), fetched


# --------------------------------------------------------------------------- channel

def ensure_channel() -> bool:
    """Register ``ch_hn`` once. Returns True if this run created the row.

    The channel table is keyed by ``channel_id``, so re-registering on a second run would
    raise. We check first rather than catching, because a swallowed IntegrityError here would
    look identical to a schema problem.
    """
    existing = store.conn().execute(
        "SELECT channel_id FROM channel WHERE channel_id = ?", (CHANNEL_ID,)
    ).fetchone()
    if existing:
        return False

    base.register_channel(
        channel_id=CHANNEL_ID,
        channel_name="Hacker News (Algolia, low-visibility surface)",
        kind="discovery",
        cold_start_native=True,
        status="active",
        rationale=(
            "Fires for a person with no GitHub, no funding and no network: a dated, quotable, "
            "first-person artifact exists the moment they post. Scanned on comment TEXT — "
            "lived domain exposure, specificity, named systems — never on points or karma, and "
            "never from the front page, which is by construction the set of people everyone has "
            "already seen."
        ),
        limitation=(
            "Coverage skews US/English/technical and self-selects for people comfortable posting "
            "publicly. Non-English founders, non-technical operators, and anyone who reads HN "
            "without commenting are invisible to this channel — a real cold-start blind spot we "
            "name rather than paper over. Account age is inferred from the earliest item in the "
            "Algolia index, which is a floor on true account age, not the signup date. Handles "
            "are pseudonyms: identity resolution to a legal name is out of scope here."
        ),
        note=(
            "hn.algolia.com/api/v1/search_by_date — free, keyless, second-resolution unix "
            f"timestamps, complete history. Capped at {MAX_REQUESTS} requests/run, "
            f"{HITS_PER_PAGE} hits/page, {REQUEST_DELAY_S}s between live calls; every response "
            "cached to disk by content hash so a re-run costs zero network."
        ),
    )
    return True


# --------------------------------------------------------------------------- emission

class _SeenKeys:
    """In-run guard against re-emitting an item two different queries both returned."""

    def __init__(self) -> None:
        self.keys: set[tuple[str, str]] = set()
        self.collisions = 0

    def add_once(self, source_url: str, claim_type: str) -> bool:
        key = (source_url, claim_type)
        if key in self.keys:
            self.collisions += 1
            return False
        self.keys.add(key)
        return True


_seen = _SeenKeys()


@dataclass
class Candidate:
    """One author we have seen, with everything needed to decide whether to probe them."""

    handle: str
    person_id: str | None = None
    sector: str | None = None
    best_score: float = 0.0
    corpus_hits: int = 0
    # How many of this author's items PASSED THE TEXT FILTER. Deliberately not the number the
    # ledger accepted: on a second run the unique index rejects every row we already wrote, so
    # keying selection off acceptance would make the corpus decide differently each run and the
    # author probe would fetch a different set of handles every time — turning a cached re-run
    # back into a network run.
    qualified: int = 0
    emitted: int = 0
    show_hn: bool = False
    earliest_seen: str | None = None


def _resolve_person(cand: Candidate, observed_at: str) -> str | None:
    """Create or resolve the person spine row for an HN handle.

    An HN handle is a public pseudonym, so the display name IS the handle and the person is
    flagged pseudonymized: we hold a real person behind a name we have not resolved, and
    saying so is more honest than inventing one.
    """
    if cand.person_id:
        return cand.person_id
    try:
        result = ledger.upsert_person(
            display_name=f"@{cand.handle}",
            handle=cand.handle,
            sector=cand.sector,
            discovered_via=CHANNEL_ID,
            resource_tier="unknown",
            solo_or_team="unknown",
            contact_status="none",
            is_real_person=True,
            is_pseudonymized=True,
            provenance_class="live",
            observed_at=observed_at,
            alias_source=SOURCE,
            alias_source_class="forum_post",
        )
    except Exception as exc:  # noqa: BLE001 — one bad handle must not end the run
        print(f"  ! person resolve failed for {cand.handle}: {type(exc).__name__}: {exc}")
        return None
    cand.person_id = result["person_id"]
    return cand.person_id


def _emit_utterance(
    run: base.CollectorRun,
    cand: Candidate,
    hit: dict[str, Any],
    text: str,
    signal: TextSignal,
    observed_at: str,
    fetched: base.Fetched,
    *,
    artifact_type: str,
    claim_type: str,
    extra_rationale: str = "",
) -> bool:
    item_id = str(hit.get("objectID") or "")
    # The same comment can be returned by two different sector queries. The ledger's unique
    # index would reject the second copy anyway; catching it here keeps that expected collision
    # out of the run's error list, where it would look like a real failure.
    if not _seen.add_once(ITEM_URL.format(item_id), claim_type):
        return False
    cand.qualified += 1

    person_id = _resolve_person(cand, observed_at)
    if not person_id:
        return False

    context = hit.get("story_title") or hit.get("title") or ""
    excerpt = text[:EXCERPT_CHARS]
    if len(text) > EXCERPT_CHARS:
        excerpt += "…"
    header = f"@{cand.handle} on HN"
    if context:
        header += f" — thread: {_one_line(str(context), 120)}"

    obs_id = base.emit(
        run,
        person_id=person_id,
        observed_at=observed_at,          # HN's own created_at, NOT fetch time
        source=SOURCE,
        source_class="forum_post",
        provenance_class="live",
        source_url=ITEM_URL.format(item_id),
        # The retrieval we actually performed, verbatim and re-runnable. source_url stays the
        # citable human-readable permalink a judge clicks.
        final_url=fetched.final_url,
        http_status=fetched.status,
        fetch_method="httpx_get",
        fetched_at=fetched.fetched_at,
        artifact_type=artifact_type,
        claim_type=claim_type,
        value=_one_line(text, VALUE_CHARS),
        raw_excerpt=(
            f"{header}\n\n{excerpt}\n\n{signal.rationale()}"
            + (f" {extra_rationale}" if extra_rationale else "")
        ),
        confidence=min(0.95, round(0.35 + 0.6 * signal.score, 3)),
    )
    if obs_id:
        cand.emitted += 1
        return True
    return False


# --------------------------------------------------------------------------- passes

def _sector_config(sectors: list[str]) -> tuple[list[tuple[str, str]], dict[str, list[str]]]:
    """(sector, query) pairs and per-sector vocabulary, derived from the configured thesis."""
    per_sector: list[tuple[str, list[str]]] = []
    terms: dict[str, list[str]] = {}
    for sector in sectors:
        conf = SECTOR_LEXICON.get(sector)
        if conf:
            terms[sector] = conf["terms"]
            sector_queries = conf["queries"]
        else:
            # An unrecognised sector still scans, using its own name. Reconfiguring the thesis
            # must change what we look for rather than silently collecting nothing.
            words = sector.replace("_", " ").strip()
            terms[sector] = [w for w in words.split() if len(w) > 3]
            sector_queries = [words]
        per_sector.append((sector, list(sector_queries)))

    # Round-robin across sectors so a budget cut costs every sector equally rather than
    # wiping the last one out entirely.
    flat: list[tuple[str, str]] = []
    depth = max((len(q) for _, q in per_sector), default=0)
    for i in range(depth):
        for sector, sector_queries in per_sector:
            if i < len(sector_queries):
                flat.append((sector, sector_queries[i]))
    return flat, terms


def collect_comments(
    run: base.CollectorRun,
    budget: Budget,
    candidates: dict[str, Candidate],
    sectors: list[str],
) -> int:
    """Pass 1 — long, specific, operationally-detailed comments in deep sector threads."""
    flat, terms = _sector_config(sectors)
    emitted = 0
    for sector, query in flat[:COMMENT_QUERY_BUDGET]:
        hits, nb, fetched = search(
            budget,
            {"query": query, "tags": "comment", "hitsPerPage": HITS_PER_PAGE, "page": 0},
        )
        if fetched is None:
            break
        print(f"  comments  [{sector:<18}] {query!r:<34} hits={len(hits):<3} pool={nb}")
        for hit in hits:
            handle = (hit.get("author") or "").strip()
            observed_at = _hit_time(hit)
            if not handle or not observed_at:
                continue
            text = clean_html(hit.get("comment_text"))
            cand = candidates.setdefault(handle, Candidate(handle=handle, sector=sector))
            cand.corpus_hits += 1
            if cand.earliest_seen is None or observed_at < cand.earliest_seen:
                cand.earliest_seen = observed_at
            if len(text) < MIN_CHARS or cand.qualified >= MAX_PER_AUTHOR:
                continue
            signal = score_text(text, terms.get(sector, []))
            cand.best_score = max(cand.best_score, signal.score)
            if signal.score < SCORE_THRESHOLD:
                continue
            if _emit_utterance(
                run, cand, hit, text, signal, observed_at, fetched,
                artifact_type="forum_comment",
                claim_type="forum_utterance",
            ):
                emitted += 1
    return emitted


def collect_show_hn(
    run: base.CollectorRun,
    budget: Budget,
    candidates: dict[str, Candidate],
    sectors: list[str],
) -> int:
    """Pass 2 — Show HN launches. A shipped artifact with an exact timestamp.

    The launch is recorded as a milestone (``shipped``) and, when the post carries a link, the
    product URL is emitted as its own row so the domain reader downstream has a candidate to
    fetch. That link is frequently the founder's very first public surface.
    """
    _, terms = _sector_config(sectors)
    all_terms = [t for v in terms.values() for t in v]
    # Launch posts are titled in product language, not in the analyst's sector language, so
    # each sector carries its own Show HN query. An unconfigured sector falls back to its name.
    queries: list[str] = []
    for sector in sectors:
        conf = SECTOR_LEXICON.get(sector) or {}
        queries.extend(conf.get("show_queries") or [sector.replace("_", " ")])
    queries = queries[:SHOW_HN_QUERY_BUDGET]
    emitted = 0
    for query in queries:
        hits, nb, fetched = search(
            budget,
            {"query": query, "tags": "show_hn", "hitsPerPage": HITS_PER_PAGE, "page": 0},
        )
        if fetched is None:
            break
        print(f"  show_hn   [{'launch':<18}] {query!r:<34} hits={len(hits):<3} pool={nb}")
        for hit in hits:
            handle = (hit.get("author") or "").strip()
            observed_at = _hit_time(hit)
            if not handle or not observed_at:
                continue
            title = clean_html(hit.get("title"))
            body = clean_html(hit.get("story_text"))
            text = f"{title}\n\n{body}".strip()
            cand = candidates.setdefault(handle, Candidate(handle=handle, sector=None))
            cand.corpus_hits += 1
            cand.show_hn = True
            if cand.earliest_seen is None or observed_at < cand.earliest_seen:
                cand.earliest_seen = observed_at
            if cand.qualified >= MAX_PER_AUTHOR:
                continue

            # A Show HN is scored more leniently than a comment: the artifact itself is the
            # evidence, and launch posts are structurally short.
            signal = score_text(text, all_terms)
            cand.best_score = max(cand.best_score, signal.score)
            if len(text) < 120:
                continue
            if _emit_utterance(
                run, cand, hit, text, signal, observed_at, fetched,
                artifact_type="show_hn_post",
                claim_type="forum_utterance",
            ):
                emitted += 1

            product_url = (hit.get("url") or "").strip()
            person_id = cand.person_id
            item_url = ITEM_URL.format(hit.get("objectID"))
            # Same guard as the utterance: three Show HN queries overlap, and the same launch
            # coming back twice is a duplicate, not a second launch.
            if product_url and person_id and _seen.add_once(item_url, "shipped_artifact"):
                if base.emit(
                    run,
                    person_id=person_id,
                    observed_at=observed_at,
                    source=SOURCE,
                    source_class="forum_post",
                    provenance_class="live",
                    source_url=item_url,
                    final_url=fetched.final_url,
                    http_status=fetched.status,
                    fetch_method="httpx_get",
                    fetched_at=fetched.fetched_at,
                    artifact_type="product_url",
                    claim_type="shipped_artifact",
                    value=product_url,
                    raw_excerpt=(
                        f"@{handle} launched on HN: {_one_line(title, 200)}\n"
                        f"Artifact: {product_url}\n\n"
                        "[milestone] shipped — a public artifact with an exact timestamp, "
                        "which is available for a founder with no GitHub, no funding and no "
                        "network. Candidate URL for the domain reader."
                    ),
                    is_milestone=True,
                    milestone_type="shipped",
                    confidence=0.9,
                ):
                    emitted += 1
    return emitted


def collect_hiring(
    run: base.CollectorRun,
    budget: Budget,
    candidates: dict[str, Candidate],
    sectors: list[str],
) -> int:
    """Pass 3 — 'Who wants to be hired' threads: dated, self-reported operator history.

    Nobody needs a network to post in these, which is exactly why they are worth reading.
    """
    _, terms = _sector_config(sectors)
    all_terms = [t for v in terms.values() for t in v]
    emitted = 0

    stories, _, fetched = search(
        budget,
        {"query": "Who wants to be hired?", "tags": "story", "hitsPerPage": 10, "page": 0},
    )
    if fetched is None:
        return 0
    # Anchored: only the canonical monthly "Ask HN:" thread. The meta-threads that discuss it
    # match a naive substring and contain no operator history whatsoever.
    thread_ids = [
        str(s.get("objectID"))
        for s in stories
        if HIRING_TITLE_RE.match(s.get("title") or "")
    ][:1]
    print(f"  hiring    [{'threads':<18}] canonical={thread_ids}")

    pages = max(0, HIRING_BUDGET - 1)
    for story_id in thread_ids:
        for page in range(pages):
            hits, nb, fetched = search(
                budget,
                {
                    "tags": f"comment,story_{story_id}",
                    "hitsPerPage": HITS_PER_PAGE,
                    "page": page,
                },
            )
            if fetched is None:
                break
            print(
                f"  hiring    [{'story_' + story_id:<18}] page={page:<28} "
                f"hits={len(hits):<3} pool={nb}"
            )
            if not hits:
                break
            for hit in hits:
                handle = (hit.get("author") or "").strip()
                observed_at = _hit_time(hit)
                if not handle or not observed_at:
                    continue
                text = clean_html(hit.get("comment_text"))
                cand = candidates.setdefault(handle, Candidate(handle=handle, sector=None))
                cand.corpus_hits += 1
                if cand.earliest_seen is None or observed_at < cand.earliest_seen:
                    cand.earliest_seen = observed_at
                if len(text) < MIN_CHARS or cand.qualified >= MAX_PER_AUTHOR:
                    continue
                signal = score_text(text, all_terms)
                cand.best_score = max(cand.best_score, signal.score)
                # Either reflective prose about work done, OR the structured self-description
                # template — which is operator history in tabular form and just as dated.
                template_fields = len({m.lower() for m in HIRING_FIELD_RE.findall(text)})
                if HIRING_HEADER_RE.search(text):
                    template_fields += 2
                if signal.score < HIRING_SCORE_THRESHOLD and template_fields < 3:
                    continue
                if _emit_utterance(
                    run, cand, hit, text, signal, observed_at, fetched,
                    artifact_type="hiring_thread_post",
                    claim_type="operator_history",
                    extra_rationale=f"hiring-template-fields={template_fields}",
                ):
                    emitted += 1
    return emitted


def probe_authors(
    run: base.CollectorRun,
    budget: Budget,
    candidates: dict[str, Candidate],
) -> tuple[int, int]:
    """Pass 4 — account age and footprint for the strongest candidates. Facts, not opinions.

    One request per author: ``search_by_date`` is newest-first, so if the account's total item
    count fits in a single page we also hold its very first item, and therefore a floor on the
    account's age. An account that is young AND quiet AND writing operationally-specific prose
    is the person the consensus channels structurally cannot see yet.

    Emits two rows per probed author:
      * ``first_forum_activity``  — observed_at = the first item's own timestamp
      * ``forum_footprint_size``  — observed_at = the newest item's timestamp (when it was true)

    Footprint is a COUNT OF THE PERSON'S OWN OUTPUT. It is not karma and not a popularity
    measure: low is interesting here, high is not.
    """
    eligible = [c for c in candidates.values() if c.person_id and c.qualified > 0]
    # Deliberately split rather than one ranked list. Launch authors are the richest probe
    # (a shipped artifact plus an account age is the cold-start founder signature), but if
    # they took every slot we would never learn the age of the quiet commenter who wrote the
    # single most specific thing in the corpus — and that person is the whole point.
    quiet_first = lambda c: (c.corpus_hits, -c.best_score)  # noqa: E731
    launchers = sorted((c for c in eligible if c.show_hn), key=quiet_first)
    commenters = sorted((c for c in eligible if not c.show_hn), key=quiet_first)
    slots = [*launchers[:SHOW_HN_PROBE_SLOTS], *commenters[: AUTHOR_PROBE_LIMIT - SHOW_HN_PROBE_SLOTS]]

    emitted = 0
    young = 0
    for cand in slots[:AUTHOR_PROBE_LIMIT]:
        hits, nb, fetched = search(
            budget,
            {"tags": f"author_{cand.handle}", "hitsPerPage": PROBE_HITS_PER_PAGE, "page": 0},
        )
        if fetched is None:
            break
        if not hits:
            continue

        newest_at = _hit_time(hits[0])
        complete = nb <= len(hits)
        first_at = _hit_time(hits[-1]) if complete else None
        age_days: int | None = None
        if first_at:
            age_days = (datetime.now(timezone.utc) - store.parse_iso(first_at)).days
            if age_days <= NEW_ACCOUNT_DAYS:
                young += 1

        flags = []
        if age_days is not None and age_days <= NEW_ACCOUNT_DAYS:
            flags.append(f"account<{NEW_ACCOUNT_DAYS}d")
        if nb <= LOW_FOOTPRINT_ITEMS:
            flags.append("low-footprint")
        if cand.show_hn:
            flags.append("show-hn")
        print(
            f"  probe     [{cand.handle[:18]:<18}] items={nb:<5} "
            f"first={first_at or 'unknown(>1 page)'} age_days={age_days} {' '.join(flags)}"
        )

        if first_at and complete:
            if base.emit(
                run,
                person_id=cand.person_id,
                observed_at=first_at,
                source=SOURCE,
                source_class="forum_post",
                provenance_class="live",
                source_url=ITEM_URL.format(hits[-1].get("objectID")),
                final_url=fetched.final_url,
                http_status=fetched.status,
                fetch_method="httpx_get",
                fetched_at=fetched.fetched_at,
                artifact_type="account_first_post",
                claim_type="first_forum_activity",
                value=first_at,
                raw_excerpt=(
                    f"@{cand.handle}'s earliest item in the HN index is {first_at} "
                    f"({age_days}d ago). Floor on account age, not the signup date — the index "
                    "cannot see an account that never posted. "
                    + (
                        f"Under {NEW_ACCOUNT_DAYS} days: cold-start candidate."
                        if age_days is not None and age_days <= NEW_ACCOUNT_DAYS
                        else "Established account."
                    )
                ),
                confidence=0.8,
            ):
                emitted += 1

        if newest_at:
            if base.emit(
                run,
                person_id=cand.person_id,
                observed_at=newest_at,
                source=SOURCE,
                source_class="forum_post",
                provenance_class="live",
                source_url=USER_URL.format(cand.handle),
                final_url=fetched.final_url,
                http_status=fetched.status,
                fetch_method="httpx_get",
                fetched_at=fetched.fetched_at,
                artifact_type="account_footprint",
                claim_type="forum_footprint_size",
                value=str(nb),
                raw_excerpt=(
                    f"@{cand.handle} has {nb} items in the HN index as of {newest_at}. "
                    "This is a count of the person's OWN output — not karma, not points, not "
                    "followers. A small footprint alongside operationally-specific writing is "
                    "the low-visibility surface this channel exists to read."
                ),
                confidence=0.85,
            ):
                emitted += 1
    return emitted, young


# --------------------------------------------------------------------------- entrypoint

def collect() -> dict[str, Any]:
    """Run every pass. Returns the summary dict the runner prints."""
    global _seen

    store.open_ledger()
    created = ensure_channel()

    sectors = base.thesis_sectors()
    run = base.CollectorRun(channel_id=CHANNEL_ID)
    budget = Budget(limit=MAX_REQUESTS)
    candidates: dict[str, Candidate] = {}
    _seen = _SeenKeys()

    print(f"channel {CHANNEL_ID} {'registered' if created else 'already registered'}")
    print(f"thesis sectors: {sectors}")
    print(f"request cap: {MAX_REQUESTS}\n")

    n_comment = collect_comments(run, budget, candidates, sectors)
    n_show = collect_show_hn(run, budget, candidates, sectors)
    n_hire = collect_hiring(run, budget, candidates, sectors)
    n_probe, n_young = probe_authors(run, budget, candidates)

    ledger.commit()

    # base.emit already separates a UNIQUE-constraint rejection (the dedup index working, on a
    # row an earlier run legitimately wrote) from a real failure. Both are reported under their
    # own names; neither is folded into the other.
    real_errors = list(run.errors)

    return {
        "n": run.emitted,
        "n_people": len(run.people),
        "n_authors_seen": len(candidates),
        "by_pass": {
            "comments": n_comment,
            "show_hn": n_show,
            "hiring": n_hire,
            "author_probe": n_probe,
        },
        "young_accounts": n_young,
        "deduped_in_run": _seen.collisions,
        "deduped_by_ledger": run.deduped,
        "real_errors": len(real_errors),
        "requests_used": budget.used,
        "requests_network": budget.network,
        "requests_cached": budget.cached,
        "request_failures": budget.failures,
        "cache": base.cache_stats(),
        "errors": real_errors[:5],
        "summary": run.summary(),
    }


def main() -> int:
    result = collect()
    print()
    print("=" * 78)
    print(f"  {result['summary']}")
    print(f"  n (observations emitted) = {result['n']}   distinct people = {result['n_people']}")
    print(f"  authors seen in corpus   = {result['n_authors_seen']}")
    print(f"  by pass                  = {result['by_pass']}")
    print(f"  accounts < {NEW_ACCOUNT_DAYS}d old        = {result['young_accounts']}")
    print(
        f"  deduped                  = {result['deduped_in_run']} in-run, "
        f"{result['deduped_by_ledger']} already in ledger"
    )
    print(f"  real errors              = {result['real_errors']}")
    print(
        f"  requests                 = {result['requests_used']}/{MAX_REQUESTS} "
        f"(network={result['requests_network']} cached={result['requests_cached']} "
        f"failed={result['request_failures']})"
    )
    print(f"  disk cache               = {result['cache']}")
    if result["errors"]:
        print(f"  first errors             = {result['errors']}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
