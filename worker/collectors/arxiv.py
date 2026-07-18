"""arXiv preprints — the cold-start-native academic channel.

WHY THIS CHANNEL EXISTS
-----------------------
A first-time academic founder has no company, no funding, no cap table, no press and
frequently no GitHub. Every commercial sourcing tool on the market is blind to them until
they incorporate, which is precisely the moment the edge disappears. But they have published
a paper, under their own name, with a *dated* timestamp arXiv assigns and never rewrites.

That makes this channel genuinely ``discovery``: it fires for a person with zero track
record, zero network, and zero commercial footprint. It is not ranking anything by
popularity — no citation counts, no h-index, no institutional prestige. It reads the
*artifact*: what the person built, in their own words, on a date we can check.

WHAT WE CAPTURE
---------------
Author name, affiliation when the author declared one, the title, the abstract, and the
real submission date. ``observed_at`` is arXiv's ``<published>`` — when the preprint
existed in the world — never our fetch time. Getting that backwards would silently break
days-of-edge (a channel would appear to have zero lead time because every row would be
stamped "now") and would leak hindsight into every asof replay.

THE HONEST LIMITATION, stated on the channel row rather than discovered by a judge
---------------------------------------------------------------------------------
arXiv skews hard toward fields that preprint — CS, physics, quant finance. A founder
building in a field that publishes only in closed venues, or one who never publishes at
all, is invisible here. **The absence of a paper says nothing about a founder.** This
channel can raise a hand; it can never lower one.

REQUEST DISCIPLINE
------------------
arXiv asks API clients to leave roughly three seconds between requests. We sleep 3s between
*network* calls and cap the run at ``MAX_REQUESTS``. A cached response sleeps for zero
seconds, so a second run of the pipeline is instant and makes no network calls at all.

Run it::

    uv run python -m worker.collectors.arxiv
"""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Iterable

from worker import ledger, store
from worker.collectors import base

# --------------------------------------------------------------------------- config

API_URL = "http://export.arxiv.org/api/query"

CHANNEL_ID = "ch_arxiv"
CHANNEL_NAME = "arXiv preprints — small-team authors, no company required"
SOURCE = "arxiv_api"

LIMITATION = (
    "arXiv skews toward fields that preprint (CS, physics, quant-fin). A founder in a "
    "field that publishes only in closed venues, or who does not publish at all, is "
    "invisible here — the ABSENCE of a paper says nothing about a founder. This channel "
    "can raise a hand; it can never lower one. Author-name entity resolution is exact-match "
    "only, so two distinct researchers sharing a name will block together."
)

RATIONALE = (
    "Cold-start-native: fires for a person with no company, no funding, no press and no "
    "GitHub. Scores the artifact and its text, never citations, h-index or institution."
)

# Papers with more authors than this are skipped. Not a quality judgement — a
# twenty-author consortium paper is not a founding team, and this channel exists to find
# people who could plausibly start something. Recorded on every row as n_authors.
MAX_AUTHORS = 4

# Hard cap on network calls, so a bad query cannot turn into a crawl.
MAX_REQUESTS = 10
REQUEST_DELAY_SECONDS = 3.0
RESULTS_PER_QUERY = 40

ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"

# Thesis sector -> [(arXiv category, abstract keywords)]. The Thesis Engine is meant to be
# load-bearing at the point of collection, not a filter bar bolted on after the fact: we
# scan through the fund's lens rather than scraping all of arXiv and sorting later.
SECTOR_QUERIES: dict[str, list[tuple[str, list[str]]]] = {
    "b2b_fintech_infra": [
        ("q-fin.TR", ["market microstructure", "settlement", "execution"]),
        ("cs.CR", ["payment", "financial", "fraud detection"]),
        ("cs.DC", ["ledger", "transaction processing", "consensus protocol"]),
    ],
    "devtools": [
        ("cs.SE", ["developer tooling", "build system", "continuous integration"]),
        ("cs.PL", ["compiler", "program synthesis", "type system"]),
    ],
    "vertical_saas": [
        ("cs.IR", ["enterprise search", "document retrieval", "workflow"]),
        ("cs.CY", ["compliance", "regulation", "clinical workflow"]),
        ("cs.LG", ["production deployment", "industrial application"]),
    ],
}

# Used when the configured thesis names a sector we have no mapping for. Better a broad
# applied-ML sweep than a silently empty run.
FALLBACK_QUERIES: list[tuple[str, list[str]]] = [
    ("cs.LG", ["real-world deployment", "applied"]),
    ("cs.SE", ["tooling", "practitioner"]),
]

_WHITESPACE = re.compile(r"\s+")


# --------------------------------------------------------------------------- parsing


@dataclass
class Paper:
    """One preprint, flattened out of the Atom entry."""

    arxiv_id: str
    abs_url: str
    title: str
    abstract: str
    published: str
    updated: str
    primary_category: str
    categories: list[str]
    authors: list[tuple[str, str | None]] = field(default_factory=list)
    comment: str | None = None

    @property
    def n_authors(self) -> int:
        return len(self.authors)


def _clean(text: str | None) -> str:
    """arXiv wraps titles and abstracts across lines; collapse to one line."""
    return _WHITESPACE.sub(" ", (text or "")).strip()


def _iso(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return store.to_iso(value)
    except (ValueError, TypeError):
        return None


def parse_feed(xml_text: str) -> list[Paper]:
    """Parse an arXiv Atom feed into papers. Malformed XML yields [] rather than a crash."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    papers: list[Paper] = []
    for entry in root.findall(f"{ATOM}entry"):
        raw_id = _clean(entry.findtext(f"{ATOM}id"))
        if not raw_id:
            continue
        arxiv_id = raw_id.rsplit("/abs/", 1)[-1]
        published = _iso(entry.findtext(f"{ATOM}published"))
        if not published:
            continue  # a row with no real world-date is worthless to an asof ledger

        authors: list[tuple[str, str | None]] = []
        for node in entry.findall(f"{ATOM}author"):
            name = _clean(node.findtext(f"{ATOM}name"))
            if not name:
                continue
            affiliation = _clean(node.findtext(f"{ARXIV_NS}affiliation")) or None
            authors.append((name, affiliation))
        if not authors:
            continue

        primary = entry.find(f"{ARXIV_NS}primary_category")
        papers.append(
            Paper(
                arxiv_id=arxiv_id,
                abs_url=f"https://arxiv.org/abs/{arxiv_id}",
                title=_clean(entry.findtext(f"{ATOM}title")),
                abstract=_clean(entry.findtext(f"{ATOM}summary")),
                published=published,
                updated=_iso(entry.findtext(f"{ATOM}updated")) or published,
                primary_category=(primary.get("term") if primary is not None else "") or "",
                categories=[
                    c.get("term", "") for c in entry.findall(f"{ATOM}category") if c.get("term")
                ],
                authors=authors,
                comment=_clean(entry.findtext(f"{ARXIV_NS}comment")) or None,
            )
        )
    return papers


def build_query(category: str, keywords: Iterable[str]) -> str:
    """``cat:cs.SE AND (abs:"build system" OR abs:"developer tooling")``."""
    terms = " OR ".join(f'abs:"{k}"' for k in keywords)
    return f"cat:{category} AND ({terms})" if terms else f"cat:{category}"


# --------------------------------------------------------------------------- collect


def _ensure_channel() -> None:
    """Register the channel once. Re-running a collector must not blow up on the PK."""
    c = store.conn()
    existing = c.execute(
        "SELECT channel_id FROM channel WHERE channel_id = ?", (CHANNEL_ID,)
    ).fetchone()
    if existing:
        return
    base.register_channel(
        channel_id=CHANNEL_ID,
        channel_name=CHANNEL_NAME,
        kind="discovery",
        cold_start_native=True,
        rationale=RATIONALE,
        limitation=LIMITATION,
        note=(
            f"export.arxiv.org Atom API, keyless. <={MAX_AUTHORS} authors per paper. "
            f"observed_at = arXiv <published>, not fetch time."
        ),
    )


def emit_paper(run: base.CollectorRun, paper: Paper, sector: str, fetched: base.Fetched) -> int:
    """Write one paper's rows. Returns how many observations landed.

    ``observed_at`` is the preprint's submission date. ``http_status`` / ``fetched_at``
    describe the arXiv API call that returned this record — we did not fetch the abstract
    page itself, so ``final_url`` is deliberately left empty rather than guessed.
    """
    before = run.emitted
    context = (
        f"{paper.title} — arXiv:{paper.arxiv_id} [{paper.primary_category}], "
        f"{paper.n_authors} author(s), submitted {paper.published}."
    )

    first_person_id: str | None = None
    seen_affiliations: set[str] = set()

    for name, affiliation in paper.authors:
        try:
            resolved = ledger.upsert_person(
                display_name=name,
                sector=sector,
                discovered_via=CHANNEL_ID,
                is_real_person=True,
                # We know they published; we know nothing about their funding. 'unknown'
                # is the truthful tier — guessing 'bootstrapped' would be an authored fact.
                resource_tier="unknown",
                solo_or_team="solo" if paper.n_authors == 1 else "team",
                provenance_class="live",
                observed_at=paper.published,
                alias_source=SOURCE,
                alias_source_class="preprint",
            )
        except Exception as exc:  # noqa: BLE001 — one bad name must not end the run
            run.skipped += 1
            run.errors.append(f"upsert_person({name!r}): {type(exc).__name__}: {exc}")
            continue

        person_id = resolved["person_id"]
        first_person_id = first_person_id or person_id

        base.emit(
            run,
            person_id=person_id,
            observed_at=paper.published,
            source=SOURCE,
            source_class="preprint",
            provenance_class="live",
            source_url=paper.abs_url,
            http_status=fetched.status,
            fetch_method="httpx_get",
            fetched_at=fetched.fetched_at,
            claim_type="preprint_authorship",
            artifact_type="preprint",
            value=name,
            raw_excerpt=context,
            confidence=0.95,
        )

        if affiliation and affiliation not in seen_affiliations:
            seen_affiliations.add(affiliation)
            base.emit(
                run,
                person_id=person_id,
                observed_at=paper.published,
                source=SOURCE,
                source_class="preprint",
                provenance_class="live",
                source_url=paper.abs_url,
                http_status=fetched.status,
                fetch_method="httpx_get",
                fetched_at=fetched.fetched_at,
                claim_type="affiliation",
                artifact_type="preprint",
                value=affiliation,
                raw_excerpt=f"Declared on arXiv:{paper.arxiv_id}: {affiliation}",
                # Self-declared and frequently stale — a founder may have left months ago.
                confidence=0.7,
            )

    if first_person_id and paper.abstract:
        base.emit(
            run,
            person_id=first_person_id,
            observed_at=paper.published,
            source=SOURCE,
            source_class="preprint",
            provenance_class="live",
            source_url=paper.abs_url,
            http_status=fetched.status,
            fetch_method="httpx_get",
            fetched_at=fetched.fetched_at,
            claim_type="preprint_abstract",
            artifact_type="preprint",
            value=paper.title,
            # The abstract is the machine-readable statement of what was built. It feeds
            # the Idea-vs-Market axis directly, so it is stored verbatim, not summarised.
            raw_excerpt=paper.abstract[:1800],
            confidence=0.9,
        )

    return run.emitted - before


def collect(
    *,
    sectors: Iterable[str] | None = None,
    max_requests: int = MAX_REQUESTS,
    results_per_query: int = RESULTS_PER_QUERY,
    max_authors: int = MAX_AUTHORS,
) -> tuple[base.CollectorRun, dict[str, Any]]:
    """Run the collector. Returns the run plus a stats dict for the printed summary."""
    _ensure_channel()
    run = base.CollectorRun(channel_id=CHANNEL_ID)

    wanted = list(sectors) if sectors else base.thesis_sectors()
    plan: list[tuple[str, str, list[str]]] = []
    for sector in wanted:
        for category, keywords in SECTOR_QUERIES.get(sector, FALLBACK_QUERIES):
            plan.append((sector, category, keywords))

    stats: dict[str, Any] = {
        "sectors": wanted,
        "requests": 0,
        "network_requests": 0,
        "cached_requests": 0,
        "papers_seen": 0,
        "papers_kept": 0,
        "papers_skipped_large_team": 0,
        "queries": [],
        "earliest_observed_at": None,
        "latest_observed_at": None,
    }

    seen_ids: set[str] = set()
    first_network_call = True

    for sector, category, keywords in plan:
        if stats["requests"] >= max_requests:
            run.errors.append(
                f"request cap {max_requests} reached; {len(plan) - stats['requests']} "
                "queries not run"
            )
            break

        params = {
            "search_query": build_query(category, keywords),
            "start": 0,
            "max_results": results_per_query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        # arXiv asks for ~3s between requests. A cache hit is not a request, so a second
        # run of the pipeline neither sleeps nor touches the network.
        probe = base.cache_path(base._cache_key("GET", API_URL, params)).exists()
        if not probe and not first_network_call:
            time.sleep(REQUEST_DELAY_SECONDS)

        fetched = base.fetch(API_URL, params=params, timeout=30.0)
        stats["requests"] += 1
        if fetched.from_cache:
            stats["cached_requests"] += 1
        else:
            stats["network_requests"] += 1
            first_network_call = False

        if not fetched.ok:
            run.errors.append(
                f"{category}: HTTP {fetched.status} {fetched.error or ''}".strip()
            )
            stats["queries"].append(
                {"sector": sector, "category": category, "papers": 0, "emitted": 0,
                 "status": fetched.status, "error": fetched.error}
            )
            continue

        papers = parse_feed(fetched.text)
        stats["papers_seen"] += len(papers)
        emitted_here = 0
        kept_here = 0

        for paper in papers:
            if paper.arxiv_id in seen_ids:
                continue  # the same paper can match two sector queries
            if paper.n_authors > max_authors:
                stats["papers_skipped_large_team"] += 1
                continue
            seen_ids.add(paper.arxiv_id)
            kept_here += 1
            emitted_here += emit_paper(run, paper, sector, fetched)

            lo, hi = stats["earliest_observed_at"], stats["latest_observed_at"]
            stats["earliest_observed_at"] = min(lo or paper.published, paper.published)
            stats["latest_observed_at"] = max(hi or paper.published, paper.published)

        stats["papers_kept"] += kept_here
        stats["queries"].append(
            {
                "sector": sector,
                "category": category,
                "papers": len(papers),
                "kept": kept_here,
                "emitted": emitted_here,
                "from_cache": fetched.from_cache,
                "status": fetched.status,
            }
        )

    store.commit()
    return run, stats


# --------------------------------------------------------------------------- main


def main() -> int:
    run, stats = collect()

    print(f"\n{'=' * 74}")
    print(f"  {CHANNEL_NAME}")
    print(f"  channel_id={CHANNEL_ID}  kind=discovery  cold_start_native=True")
    print(f"{'=' * 74}\n")

    print(f"thesis sectors : {', '.join(stats['sectors'])}")
    print(
        f"requests       : {stats['requests']} "
        f"(network={stats['network_requests']}, cache={stats['cached_requests']}, "
        f"cap={MAX_REQUESTS})"
    )
    print(
        f"papers         : seen={stats['papers_seen']} kept={stats['papers_kept']} "
        f"skipped_team>{MAX_AUTHORS}={stats['papers_skipped_large_team']}"
    )
    print(
        f"observed_at    : {stats['earliest_observed_at']} .. "
        f"{stats['latest_observed_at']}   (arXiv submission dates, NOT fetch time)"
    )
    print()

    print(f"{'sector':<20} {'category':<10} {'papers':>7} {'kept':>6} {'obs':>6}  cache")
    print("-" * 74)
    for q in stats["queries"]:
        print(
            f"{q['sector']:<20} {q['category']:<10} {q['papers']:>7} "
            f"{q.get('kept', 0):>6} {q.get('emitted', 0):>6}  {q.get('from_cache')}"
        )
    print("-" * 74)
    print(f"\n{run.summary()}")

    asof = store.now_iso()
    n = store.count_observations(asof, channel_id=CHANNEL_ID)
    print(f"ledger via chokepoint: n={n} observations at asof={asof}")
    print(f"limitation: {LIMITATION}\n")

    if run.errors:
        print(f"errors ({len(run.errors)}), first 5:")
        for err in run.errors[:5]:
            print(f"  - {err}")
        print()

    return 0 if n > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
