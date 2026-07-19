"""B6a — the Thesis Engine. Six configurable fields, wired into the uncertainty mechanic.

    uv run python -m worker.scoring.thesis

WHY THIS IS NOT A FILTER BAR
----------------------------
A thesis that only filters is a `WHERE` clause with a nice UI. The brief is
explicit that the Thesis Engine must be **configurable, never hardcoded to one
fund**, and the only way to prove a configuration is load-bearing is to show a
field change moving capital. So one field — ``risk_appetite`` — maps to
``max_interval_width``: the widest posterior interval at which this fund is
willing to write a cheque.

That single mapping wires the thesis into our own core mechanic. A low-risk
fund refuses to deploy on a wide interval, so the *same* opportunity, over the
*same* ledger, with the *same* score, moves from ``decide_now`` to
``probe_further``. Nothing about the evidence changed; the fund's tolerance for
width did. Width costs money and nothing else — that is the lower-bound gate
from ``docs/IDEA.md`` section C, expressed as a config field.

THE HARD-FILTER SEMANTICS. Read this before changing anything.
--------------------------------------------------------------
Sector / stage / geography are hard filters, and they are hard in exactly one
direction::

    known value that mismatches the thesis  ->  EXCLUDED
    value we could not resolve for a person ->  NOT excluded; carried into the
                                                probabilistic layer with its n

This is the same rule ``query.py`` applies to "no prior VC backing", generalized
to every attribute. A hard filter that also deletes *unknowns* deletes exactly
the cold-start founders this product exists to find: 812 of our 845 people have
no resolved region, so a naive geography filter would empty the board and look
like a working feature while doing so. Excluding on absence silently inverts the
thesis. Excluding on contradiction is the thesis.

THE THREE AXES ARE NOT AVERAGED HERE EITHER
-------------------------------------------
Soft weights order the board; they never produce a composite score. Ranking is:

  1. Pareto non-dominated sorting over the 3-vector (market participates as an
     ordinal — bear < neutral < bullish — so dominance is well defined without
     arithmetic on a categorical).
  2. Within a front, a **rank-aggregation tiebreak**: the weighted sum of each
     candidate's *percentile rank* per axis. Ranks, not values. Nothing on a
     0-100 scale is ever averaged with a categorical, and the tiebreak is
     emitted as ``order_key`` — never as a score, never rendered as one.

Scoring note: this module owns *ranking*, not the Founder Score. It carries a
local closed-form estimate so it runs standalone, and takes a ``score_fn`` hook
so the integrator can swap in ``worker.scoring.founder_score`` /
``worker.scoring.axes`` in one line without touching this file.

Every number emitted here carries its ``n``.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Callable, Iterable, Sequence

from worker import ledger, store
from worker.store import read_observations

# --------------------------------------------------------------------------- #
# policy constants — hand-set, published, defended line by line
# --------------------------------------------------------------------------- #

#: risk_appetite -> the maximum posterior interval width at which capital deploys.
#: Hand-set fund policy, not an estimate. There is no dataset that could produce
#: it, so it carries n=None and says so rather than wearing a fake sample size.
RISK_APPETITE_MAP: dict[str, float] = {"low": 20.0, "medium": 30.0, "high": 42.0}

#: Empirical-Bayes shrinkage constant. w = n/(n+K_PRIOR).
K_PRIOR = 5.0

#: Interval half-width at n=0, before any absence widening. Scales as
#: sqrt(K/(n+K)), so evidence narrows it and nothing else does.
BASE_HALF_WIDTH = 24.0

#: A reference-class cell below this many people is thin and shrinks to the margin.
THIN_CELL_N = 20

#: Fallback source-class log-odds if `source_reliability` is unavailable. The
#: table in the ledger is the authority; this only keeps the module runnable.
_FALLBACK_RELIABILITY = {
    "self_report": -1.2, "interview": 0.0, "forum_post": 0.0, "press": 0.2,
    "code_host": 0.8, "preprint": 0.9, "third_party_observable": 1.1,
    "registry_filing": 2.4,
}

SECTOR_VOCAB: dict[str, tuple[str, ...]] = {
    "b2b_fintech_infra": ("payment", "payments", "settlement", "clearing", "ledger",
                          "invoic", "billing", "treasury", "banking", "fintech",
                          "reconcil", "payout", "kyc", "underwrit", "merchant"),
    "ai_infra": ("inference", "llm", "large language model", "gpu", "vector database",
                 "embedding", "model serving", "fine-tun", "training run", "rag",
                 "transformer", "neural network", "machine learning infra"),
    "devtools": ("sdk", "developer tool", "ci/cd", "continuous integration", "debugger",
                 "compiler", "runtime", "observability", "api gateway", "linter",
                 "deployment", "framework for developers"),
    "data_infra": ("data pipeline", "etl", "warehouse", "streaming", "kafka",
                   "orchestration", "data catalog", "lakehouse", "query engine"),
    "regtech": ("compliance", "regulatory", "aml", "audit trail", "sanctions",
                "gdpr", "reporting obligation", "supervis"),
    "vertical_saas": ("web application for", "software as a service", "platform for",
                      "saas", "workflow software", "practice management",
                      "appraisal", "scheduling"),
}

TECHNICAL_VOCAB = (
    "api", "sdk", "compiler", "kernel", "latency", "throughput", "database",
    "distributed", "protocol", "algorithm", "benchmark", "architecture", "runtime",
    "open source", "repository", "deployment", "inference", "schema", "encryption",
    "backend", "infrastructure", "concurrency", "typescript", "rust", "golang",
    "python", "postgres", "kubernetes",
)

OPERATOR_VOCAB = (
    "go-to-market", "sales", "revenue", "pipeline", "account executive", "partnerships",
    "customer success", "operations", "procurement", "p&l", "quota", "churn",
)

ENTERPRISE_VOCAB = (
    "enterprise", "b2b", "soc 2", "soc2", "sso", "saml", "procurement", "msa",
    "pilot with", "fortune 500", "on-premise", "sla", "rfp", "seat licence",
    "seat license", "annual contract",
)

#: Terms that route to a pedigree channel we DECLINED to collect. Resolving one
#: of these to a number would mean rebuilding the network gate we exist to
#: replace, so they resolve to a reasoned refusal instead.
PEDIGREE_TERMS = (
    "accelerator", "y combinator", "ycombinator", " yc ", "techstars", "antler",
    "entrepreneur first", "elite school", "ivy league", "stanford", "mit ",
    "ex-google", "ex-meta", "ex-faang", "well-connected", "warm intro",
    "top-tier", "tier 1 vc", "notable angel", "follower", "github stars",
)

#: city / country surface form -> region code. Deliberately small and auditable.
REGION_LEXICON: tuple[tuple[str, str], ...] = (
    ("berlin", "DE-BE"), ("münchen", "DE"), ("munich", "DE"), ("hamburg", "DE"),
    ("germany", "DE"), ("deutschland", "DE"),
    ("vienna", "AT"), ("austria", "AT"), ("zurich", "CH"), ("zürich", "CH"),
    ("switzerland", "CH"),
    ("paris", "FR"), ("france", "FR"), ("amsterdam", "NL"), ("netherlands", "NL"),
    ("madrid", "ES"), ("barcelona", "ES"), ("spain", "ES"), ("lisbon", "PT"),
    ("portugal", "PT"), ("milan", "IT"), ("italy", "IT"), ("stockholm", "SE"),
    ("sweden", "SE"), ("copenhagen", "DK"), ("denmark", "DK"), ("helsinki", "FI"),
    ("finland", "FI"), ("oslo", "NO"), ("norway", "NO"), ("dublin", "IE"),
    ("ireland", "IE"), ("warsaw", "PL"), ("poland", "PL"), ("prague", "CZ"),
    ("london", "UK"), ("cambridge, uk", "UK"), ("edinburgh", "UK"), ("oxford", "UK"),
    ("manchester", "UK"), ("united kingdom", "UK"), ("england", "UK"), ("scotland", "UK"),
    ("san francisco", "US-CA"), ("bay area", "US-CA"), ("palo alto", "US-CA"),
    ("berkeley", "US-CA"), ("los angeles", "US-CA"), ("california", "US-CA"),
    ("new york", "US-NY"), ("brooklyn", "US-NY"), ("boston", "US-MA"),
    ("cambridge, ma", "US-MA"), ("seattle", "US-WA"), ("austin", "US-TX"),
    ("chicago", "US-IL"), ("denver", "US-CO"), ("atlanta", "US-GA"),
    ("tampa", "US-FL"), ("miami", "US-FL"), ("united states", "US"), ("usa", "US"),
    ("toronto", "CA"), ("vancouver", "CA"), ("montreal", "CA"), ("canada", "CA"),
    ("bangalore", "IN"), ("bengaluru", "IN"), ("mumbai", "IN"), ("delhi", "IN"),
    ("india", "IN"), ("singapore", "SG"), ("tokyo", "JP"), ("japan", "JP"),
    ("seoul", "KR"), ("sydney", "AU"), ("melbourne", "AU"), ("australia", "AU"),
    ("tel aviv", "IL"), ("israel", "IL"), ("lagos", "NG"), ("nairobi", "KE"),
    ("são paulo", "BR"), ("sao paulo", "BR"), ("brazil", "BR"), ("pakistan", "PK"),
)

#: Region code -> the geography buckets a thesis may name.
REGION_GROUPS: dict[str, tuple[str, ...]] = {
    "DE-BE": ("DE-BE", "DE", "DACH", "EU", "EMEA"),
    "DE": ("DE", "DACH", "EU", "EMEA"), "AT": ("AT", "DACH", "EU", "EMEA"),
    "CH": ("CH", "DACH", "EMEA"), "FR": ("FR", "EU", "EMEA"),
    "NL": ("NL", "EU", "EMEA"), "ES": ("ES", "EU", "EMEA"), "PT": ("PT", "EU", "EMEA"),
    "IT": ("IT", "EU", "EMEA"), "SE": ("SE", "EU", "EMEA"), "DK": ("DK", "EU", "EMEA"),
    "FI": ("FI", "EU", "EMEA"), "NO": ("NO", "EMEA"), "IE": ("IE", "EU", "EMEA"),
    "PL": ("PL", "EU", "EMEA"), "CZ": ("CZ", "EU", "EMEA"),
    "UK": ("UK", "GB", "EMEA"), "IL": ("IL", "EMEA"), "NG": ("NG", "EMEA"),
    "KE": ("KE", "EMEA"),
    "US": ("US", "NA"), "US-CA": ("US-CA", "US", "NA"), "US-NY": ("US-NY", "US", "NA"),
    "US-MA": ("US-MA", "US", "NA"), "US-WA": ("US-WA", "US", "NA"),
    "US-TX": ("US-TX", "US", "NA"), "US-IL": ("US-IL", "US", "NA"),
    "US-CO": ("US-CO", "US", "NA"), "US-GA": ("US-GA", "US", "NA"),
    "US-FL": ("US-FL", "US", "NA"), "CA": ("CA", "NA"),
    "IN": ("IN", "APAC"), "SG": ("SG", "APAC"), "JP": ("JP", "APAC"),
    "KR": ("KR", "APAC"), "AU": ("AU", "APAC"), "PK": ("PK", "APAC"),
    "BR": ("BR", "LATAM"),
}

_LOCATION_RE = re.compile(r"location\s*:\s*([^\n|]{2,60})", re.I)


# --------------------------------------------------------------------------- #
# the thesis object
# --------------------------------------------------------------------------- #

@dataclass
class Thesis:
    """Six configurable fields plus the conviction threshold. Nothing hardcoded."""

    sectors: list[str]
    stage: str
    geography: list[str]
    check_size_usd: int
    ownership_target_pct: tuple[float, float]
    risk_appetite: str
    conviction_threshold: float = 55.0
    thesis_id: str = "th_default"
    name: str = "Unnamed thesis"
    soft_weights: dict[str, float] = field(
        default_factory=lambda: {"founder_axis": 0.40, "idea_vs_market_axis": 0.35,
                                 "market_axis": 0.25}
    )
    version_number: int = 1
    supersedes_id: str | None = None

    def __post_init__(self) -> None:
        if self.risk_appetite not in RISK_APPETITE_MAP:
            raise ValueError(
                f"risk_appetite must be one of {sorted(RISK_APPETITE_MAP)}, "
                f"got {self.risk_appetite!r}. It is not decoration: it maps to the "
                "maximum interval width at which this fund deploys capital."
            )
        self.sectors = [str(s) for s in self.sectors]
        self.geography = [str(g) for g in self.geography]

    # risk appetite is the load-bearing field: it IS the gate width.
    @property
    def max_interval_width(self) -> float:
        return RISK_APPETITE_MAP[self.risk_appetite]

    def replace(self, **changes: Any) -> "Thesis":
        """A new Thesis with fields changed. Configuration is never mutated in place."""
        data = {
            "sectors": list(self.sectors), "stage": self.stage,
            "geography": list(self.geography), "check_size_usd": self.check_size_usd,
            "ownership_target_pct": tuple(self.ownership_target_pct),
            "risk_appetite": self.risk_appetite,
            "conviction_threshold": self.conviction_threshold,
            "thesis_id": self.thesis_id, "name": self.name,
            "soft_weights": dict(self.soft_weights),
            "version_number": self.version_number + 1,
            "supersedes_id": self.thesis_id,
        }
        data.update(changes)
        return Thesis(**data)


def load_active_thesis(
    asof: str, *, connection: sqlite3.Connection | None = None
) -> Thesis:
    """The active thesis as it stood at ``asof``. Config, read append-only."""
    c = connection or ledger._conn()
    row = c.execute(
        "SELECT * FROM thesis WHERE observed_at <= :asof AND is_active = 1 "
        "ORDER BY observed_at DESC, version_number DESC LIMIT 1",
        {"asof": ledger.to_iso(asof)},
    ).fetchone()
    if row is None:
        raise ledger.LedgerViolation(
            "No active thesis at this asof. The Thesis Engine is configurable, which "
            "means the configuration has to exist — there is no hardcoded fund to "
            "fall back on, by design."
        )
    return Thesis(
        thesis_id=row["thesis_id"],
        name=row.get("name") or "Active thesis",
        sectors=json.loads(row["sectors"]),
        stage=row["stage"],
        geography=json.loads(row["geography"]),
        check_size_usd=int(row["check_size_usd"]),
        ownership_target_pct=(row["ownership_target_low"], row["ownership_target_high"]),
        risk_appetite=row["risk_appetite"],
        conviction_threshold=float(row["conviction_threshold"]),
        version_number=int(row["version_number"] or 1),
    )


def save_thesis(
    thesis: Thesis,
    *,
    observed_at: str | None = None,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """APPEND a thesis version. Never an update — reconfiguration stays replayable.

    A thesis edit is a fact about what the fund believed at a moment. Overwriting
    it would make every past decision unauditable against the policy in force
    when it was taken.
    """
    payload = {
        "thesis_id": thesis.thesis_id,
        "sectors": json.dumps(thesis.sectors),
        "stage": thesis.stage,
        "geography": json.dumps(thesis.geography),
        "check_size_usd": int(thesis.check_size_usd),
        "ownership_target_low": thesis.ownership_target_pct[0],
        "ownership_target_high": thesis.ownership_target_pct[1],
        "risk_appetite": thesis.risk_appetite,
        "max_interval_width": thesis.max_interval_width,
        "conviction_threshold": thesis.conviction_threshold,
        "is_active": 1,
        "version_number": thesis.version_number,
        "supersedes_id": thesis.supersedes_id,
    }
    if observed_at:
        payload["observed_at"] = observed_at
    return ledger.append_row("thesis", payload, connection=connection)


# --------------------------------------------------------------------------- #
# the population — one ledger read, everything derived from it
# --------------------------------------------------------------------------- #

def _reliability_table(c: sqlite3.Connection) -> dict[str, float]:
    try:
        rows = c.execute("SELECT source_class, log_odds FROM source_reliability").fetchall()
    except sqlite3.Error:
        rows = []
    table = {r["source_class"]: float(r["log_odds"]) for r in rows}
    return table or dict(_FALLBACK_RELIABILITY)


def _read_person_spine(asof: str, c: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    """The person spine at ``asof``.

    Observations go through ``store.read_observations`` and nothing else. ``person``
    is the spine table, not the ledger, so it is read here — with the *same*
    ``observed_at <= :asof`` predicate, so a point-in-time replay cannot see a
    person the past had not discovered yet.
    """
    rows = c.execute(
        "SELECT * FROM person WHERE observed_at <= :asof", {"asof": ledger.to_iso(asof)}
    ).fetchall()
    return {r["person_id"]: r for r in rows}


def _norm_region(raw: str | None) -> str | None:
    if not raw:
        return None
    text = str(raw).strip().lower()
    for surface, code in REGION_LEXICON:
        if surface in text:
            return code
    upper = str(raw).strip().upper()
    if upper in REGION_GROUPS:
        return upper
    return None


def _region_from_text(text: str) -> str | None:
    hit = _LOCATION_RE.search(text)
    if hit:
        found = _norm_region(hit.group(1))
        if found:
            return found
    return _norm_region(text[:400])


def _sector_from_text(text: str) -> tuple[str | None, int]:
    """Infer sector from what the person actually wrote. Returns (sector, n_hits)."""
    low = text.lower()
    best, best_hits = None, 0
    for sector, vocab in SECTOR_VOCAB.items():
        hits = sum(1 for term in vocab if term in low)
        if hits > best_hits:
            best, best_hits = sector, hits
    return (best, best_hits) if best_hits else (None, 0)


def _attr(state: str, p: float, n: int, basis: str, evidence: list[str] | None = None
          ) -> dict[str, Any]:
    """Every derived attribute is a state + a probability + its n + why."""
    return {"state": state, "p": round(p, 4), "n": n, "basis": basis,
            "evidence": evidence or []}


def _logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def build_population(
    asof: str,
    *,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Every person visible at ``asof``, with attributes derived in ONE pass.

    Returns ``{"asof", "people": [...], "n_observations", "market_by_sector", ...}``.
    The whole ledger is read once, through the chokepoint; every attribute below
    is computed from those rows plus the person spine. No per-person queries.
    """
    c = connection or ledger._conn()
    asof_iso = ledger.to_iso(asof)
    rows = read_observations(asof_iso, order="asc", connection=c)  # <- the one read
    spine = _read_person_spine(asof_iso, c)
    reliability = _reliability_table(c)

    by_person: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        pid = row["person_id"]
        if pid:
            by_person.setdefault(pid, []).append(row)

    cutoff_90 = ledger.to_iso(ledger.parse_iso(asof_iso) - timedelta(days=90))
    cutoff_180 = ledger.to_iso(ledger.parse_iso(asof_iso) - timedelta(days=180))
    sector_recent: dict[str, int] = {}
    sector_prior_window: dict[str, int] = {}

    people: list[dict[str, Any]] = []
    for pid, obs in by_person.items():
        person = spine.get(pid, {})
        text_blobs: list[str] = []
        channels: set[str] = set()
        log_odds = 0.0
        n_registry = n_preprint = n_third_party = n_forum = 0
        region_code = _norm_region(person.get("region"))
        region_evidence: list[str] = []
        funding_evidence: list[str] = []
        traction_evidence: list[str] = []
        technical_evidence: list[str] = []
        operator_evidence: list[str] = []
        artifacts_found: set[str] = set()

        for row in obs:
            sc = row["source_class"]
            log_odds += reliability.get(sc, 0.0)
            n_registry += sc == "registry_filing"
            n_preprint += sc == "preprint"
            n_third_party += sc == "third_party_observable"
            n_forum += sc == "forum_post"
            if row["channel_id"]:
                channels.add(row["channel_id"])
            if row["artifact_type"]:
                artifacts_found.add(row["artifact_type"])
            blob = " ".join(str(x) for x in (row["value"], row["raw_excerpt"]) if x)
            if blob:
                text_blobs.append(blob)
            if region_code is None and blob:
                found = _region_from_text(blob)
                if found:
                    region_code, region_evidence = found, [row["observation_id"]]

            ctype = row["claim_type"]
            # --- prior VC backing: POSITIVE evidence only. Absence is handled
            # --- probabilistically below and never as a filter.
            if (ctype == "attorney_of_record"
                    and str(row["value"] or "").lower() not in ("", "none", "null", "n/a")):
                funding_evidence.append(row["observation_id"])
            if ctype in ("round_terms", "funding_round", "investor"):
                funding_evidence.append(row["observation_id"])
            # --- enterprise / commercial traction
            if ctype == "domain_state" and str(row["value"]) in ("transacting", "pricing_page"):
                traction_evidence.append(row["observation_id"])
            if ctype in ("paying_users", "review_volume", "mrr", "open_roles", "headcount"):
                traction_evidence.append(row["observation_id"])
            if row["artifact_type"] in ("checkout_endpoint", "pricing_page", "job_posting",
                                        "changelog", "review_page"):
                traction_evidence.append(row["observation_id"])
            # --- founder type
            if sc in ("preprint", "code_host") or ctype in ("shipped_artifact", "preprint_authorship"):
                technical_evidence.append(row["observation_id"])
            if ctype == "operator_history":
                operator_evidence.append(row["observation_id"])

        text = "\n".join(text_blobs)
        low = text.lower()
        n_obs = len(obs)

        # sector: spine value first, then what the person actually wrote about
        sector = person.get("sector")
        sector_basis, sector_n = "person_spine", n_obs if sector else 0
        if not sector:
            inferred, hits = _sector_from_text(text)
            if inferred:
                sector, sector_basis, sector_n = inferred, "inferred_from_artifact_text", hits

        if sector:
            # Bucket each observation by ITS OWN observed_at, not by the person's
            # latest one — otherwise one recent signal backdates a whole history
            # into the current window and every sector reads bullish.
            for row in obs:
                stamp = row["observed_at"]
                if stamp >= cutoff_90:
                    sector_recent[sector] = sector_recent.get(sector, 0) + 1
                elif stamp >= cutoff_180:
                    sector_prior_window[sector] = sector_prior_window.get(sector, 0) + 1

        # founder type
        tech_hits = sum(1 for t in TECHNICAL_VOCAB if t in low)
        op_hits = sum(1 for t in OPERATOR_VOCAB if t in low)
        # A dated technical artifact settles it. Vocabulary alone needs a real
        # cluster — two stray mentions of "api" in a forum comment is not a
        # founder type, and treating it as one would resolve an attribute we do
        # not actually know.
        if technical_evidence or tech_hits >= 4:
            founder_type = _attr("known_true", 1.0, len(technical_evidence) + tech_hits,
                                 "dated technical artifact or technical vocabulary in the "
                                 "person's own text", technical_evidence[:5])
            founder_type_value = "technical"
        elif operator_evidence or op_hits >= 2:
            founder_type = _attr("known_true", 1.0, len(operator_evidence) + op_hits,
                                 "operator history post", operator_evidence[:5])
            founder_type_value = "operator"
        else:
            founder_type = _attr("unknown", 0.5, 0,
                                 "no artifact speaks to founder type; unresolved, not zero")
            founder_type_value = None

        # stage: a 1(b) intent-to-use filing is POSITIVE evidence of pre-launch,
        # not an inference from missing funding data.
        if "1(b)" in low or "intent to use" in low:
            stage = _attr("known_true", 1.0, 1,
                          "USPTO filing basis 1(b) intent-to-use: product not launched, "
                          "therefore pre-fundraise by definition")
            stage_value = "pre_seed"
        else:
            stage = _attr("unknown", 0.5, 0, "no dated stage marker observed")
            stage_value = None

        people.append({
            "person_id": pid,
            "display_name": person.get("display_name") or pid,
            "is_real_person": bool(person.get("is_real_person", 1)),
            "provenance_class": person.get("provenance_class") or "live",
            "contact_status": person.get("contact_status") or "none",
            "resource_tier": person.get("resource_tier") or "unknown",
            "solo_or_team": person.get("solo_or_team") or "unknown",
            "channels": sorted(channels),
            "discovered_via": person.get("discovered_via"),
            "first_observed_at": obs[0]["observed_at"],
            "last_observed_at": obs[-1]["observed_at"],
            "n_observations": n_obs,
            # matches the manifest module's `has_company_domain` conditioning key
            "has_company_domain": bool(person.get("primary_domain")) or bool(
                {"product_url", "landing_page", "checkout_endpoint", "pricing_page",
                 "changelog", "team_page"} & artifacts_found),
            "n_registry": n_registry, "n_preprint": n_preprint,
            "n_third_party": n_third_party, "n_forum": n_forum,
            "log_odds": round(log_odds, 3),
            "artifacts_found": sorted(artifacts_found),
            "sector": sector,
            "sector_attr": (_attr("known_true", 1.0, sector_n, sector_basis) if sector
                            else _attr("unknown", 0.5, 0, "no sector resolvable from any artifact")),
            "region": region_code,
            "region_attr": (_attr("known_true", 1.0, 1, "resolved from spine or artifact text",
                                  region_evidence)
                            if region_code else
                            _attr("unknown", 0.5, 0,
                                  "no location stated in any observed artifact")),
            "stage": stage_value, "stage_attr": stage,
            "founder_type": founder_type_value, "founder_type_attr": founder_type,
            "funding_evidence": funding_evidence,
            "traction_evidence": traction_evidence,
            "enterprise_vocab_hits": sum(1 for t in ENTERPRISE_VOCAB if t in low),
            "text_len": len(text),
        })

    market = _market_by_sector(sector_recent, sector_prior_window)
    return {
        "asof": asof_iso,
        "people": people,
        "n_people": {"value": len(people), "n": len(people)},
        "n_observations": {"value": len(rows), "n": len(rows)},
        "n_ledger_reads": {"value": 1, "n": 1},
        "market_by_sector": market,
        "reliability_table": reliability,
    }


def _market_by_sector(recent: dict[str, int], prior: dict[str, int]) -> dict[str, Any]:
    """Market axis: CATEGORICAL, computed from observation momentum, never averaged.

    bullish / neutral / bear from the 90-day observation volume against the prior
    90 days. Date arithmetic over our own crawl, so it carries an honest n and
    cannot leak through model recognition.
    """
    out: dict[str, Any] = {}
    for sector in set(recent) | set(prior):
        a, b = recent.get(sector, 0), prior.get(sector, 0)
        n = a + b
        if n < 8:
            label, basis = "neutral", f"insufficient dated observations (n={n})"
        elif a > b * 1.25:
            label, basis = "bullish", f"90d volume {a} vs prior 90d {b}"
        elif a * 1.25 < b:
            label, basis = "bear", f"90d volume {a} vs prior 90d {b}"
        else:
            label, basis = "neutral", f"90d volume {a} vs prior 90d {b}"
        out[sector] = {"label": label, "n": n, "basis": basis}
    return out


# --------------------------------------------------------------------------- #
# the local ranking estimate — swappable via score_fn
# --------------------------------------------------------------------------- #

_MARKET_ORDINAL = {"bear": 0, "neutral": 1, "bullish": 2}


def _reference_class_means(people: Sequence[dict[str, Any]]) -> dict[tuple, dict[str, Any]]:
    """Reference class = {sector, solo/team, resource tier, region-known}.

    NO PEDIGREE FIELD. No school, no employer, no accelerator, no investor —
    that omission is the point of the class, not an oversight. Thin cells shrink
    to the population margin and say so.
    """
    direct = {p["person_id"]: 100.0 * _logistic(p["log_odds"] / 6.0) for p in people}
    margin = sum(direct.values()) / len(direct) if direct else 50.0
    cells: dict[tuple, list[float]] = {}
    for p in people:
        key = (p["sector"], p["solo_or_team"], p["resource_tier"], p["region"] is not None)
        cells.setdefault(key, []).append(direct[p["person_id"]])
    out = {}
    for key, values in cells.items():
        n_cell = len(values)
        raw = sum(values) / n_cell
        thin = n_cell < THIN_CELL_N
        # shrink thin cells toward the margin, weight n/(n+THIN_CELL_N)
        w = n_cell / (n_cell + THIN_CELL_N)
        out[key] = {
            "mean": w * raw + (1 - w) * margin,
            "n_cell": n_cell,
            "thin_cell": thin,
            "shrunk_to_margin": thin,
            "margin": margin,
        }
    return out


def default_score_fn(
    person: dict[str, Any], population: dict[str, Any], _cache: dict[str, Any]
) -> dict[str, Any]:
    """Closed-form empirical-Bayes ranking estimate. Not the Founder Score.

    ``theta = w * direct + (1-w) * reference_class_mean``, ``w = n/(n+k)``.

    Absence widens the interval and NEVER lowers the point estimate — the
    assertion below is load-bearing, not decorative. A solo operator whose
    missing changelog was predicted by their resource class pays in width, not
    in score. That asymmetry is the anti-network-gate.
    """
    refs = _cache.get("refs")
    if refs is None:
        refs = _cache["refs"] = _reference_class_means(population["people"])
    priors = _cache.get("priors")
    if priors is None:
        priors = _cache["priors"] = _findability_priors(_cache.get("connection"))

    n = person["n_observations"]
    direct = 100.0 * _logistic(person["log_odds"] / 6.0)
    key = (person["sector"], person["solo_or_team"], person["resource_tier"],
           person["region"] is not None)
    ref = refs.get(key, {"mean": 50.0, "n_cell": 0, "thin_cell": True,
                         "shrunk_to_margin": True})
    w = n / (n + K_PRIOR)
    point = w * direct + (1 - w) * ref["mean"]

    half = BASE_HALF_WIDTH * math.sqrt(K_PRIOR / (n + K_PRIOR))
    point_before_absence = point

    matching = _matching_priors(priors, person)
    absent_expected: list[dict[str, Any]] = []
    for prior in matching:
        if prior["_found"]:
            continue
        if prior["p"] < 0.4:  # the class PREDICTED this absence — not expected, not priced
            continue
        widen = 6.0 * prior["p"]
        half += widen
        absent_expected.append({
            "artifact_type": prior["artifact_type"],
            "findability_prior": prior["p"], "n": prior["n"],
            "interval_widen": round(widen, 2), "penalised": False,
            "note": "expected but not found — widens the interval, does not lower the score",
        })
    half = min(half, 45.0)
    absence_basis = (
        f"{len(matching)} findability prior cell(s) matched this reference class"
        if matching else
        "no findability prior cell matches this reference class (n=0) — absence carries "
        "no information here, so it neither widens the interval nor lowers the score")

    # The anti-network-gate, enforced rather than promised: the absence loop above
    # may only touch `half`. If a future edit lets it touch the point estimate,
    # this fails loudly instead of quietly re-encoding the network gate.
    if point != point_before_absence:
        raise AssertionError(
            "Absence moved the point estimate. Missing expected evidence widens the "
            "interval and NEVER lowers the score when the findability prior predicted "
            "that absence for this resource class."
        )

    return {
        "point": round(point, 2),
        "interval_low": round(max(0.0, point - half), 2),
        "interval_high": round(min(100.0, point + half), 2),
        "width": round(min(100.0, point + half) - max(0.0, point - half), 2),
        "n": n,
        "prior_weight": round(1 - w, 3),
        "direct": round(direct, 2),
        "reference_class_mean": round(ref["mean"], 2),
        "reference_class": {
            "sector": person["sector"], "solo_or_team": person["solo_or_team"],
            "resource_tier": person["resource_tier"],
            "region_resolved": person["region"] is not None,
            "n_cell": ref["n_cell"], "thin_cell": ref["thin_cell"],
            "shrunk_to_margin": ref["shrunk_to_margin"],
            "contains_pedigree_field": False,
        },
        "absent_but_expected": absent_expected,
        "absence_basis": absence_basis,
        "n_findability_cells_matched": len(matching),
    }


#: ``findability_prior.artifact_type`` is written by the manifest module in its own
#: namespace (``base@founder_type=technical · has_company_domain=False``), which is
#: NOT ``observation.artifact_type``. This maps a manifest base type onto the
#: observation artifact types that would actually evidence it.
#:
#: A base type with no entry here is SKIPPED rather than treated as absent. We
#: cannot call an artifact missing if we never had a name under which we could
#: have recorded it — that would widen every interval on the board by a constant
#: derived from a vocabulary mismatch, which is noise dressed as uncertainty.
#: ``github_repo`` is absent from this map on purpose: we declined GitHub as a
#: primary channel, so its absence is a fact about our sourcing, not the founder.
_MANIFEST_ARTIFACT_ALIASES: dict[str, tuple[str, ...]] = {
    "public_preprint": ("preprint",),
    "public_launch_post": ("show_hn_post", "product_url", "landing_page"),
    "public_forum_participation": ("forum_comment", "forum_thread", "show_hn_post",
                                   "hiring_thread_post", "account_first_post"),
    "public_product_url": ("product_url", "landing_page", "checkout_endpoint",
                           "pricing_page"),
    "hiring_signal": ("job_posting", "hiring_thread_post"),
    "trademark_filing": ("trademark_filing", "trademark_application",
                         "trademark_identification"),
    "account_history": ("account_footprint", "account_first_post"),
    "changelog": ("changelog",),
    "team_page": ("team_page",),
    "job_posting": ("job_posting",),
    "pricing_page": ("pricing_page",),
    "press_mention": ("press_mention",),
}

_TRUE = ("true", "1", "yes")


def _parse_prior_key(artifact_type: str) -> tuple[str, dict[str, str]]:
    """``base@k=v · k2=v2`` -> ``(base, {k: v, ...})``. ``@margin`` carries no conditions."""
    base, _, tail = artifact_type.partition("@")
    conditions: dict[str, str] = {}
    if tail and tail != "margin":
        for part in re.split(r"[·;]", tail):
            key, _, value = part.strip().partition("=")
            if key and value:
                conditions[key.strip()] = value.strip().lower()
    return base.strip(), conditions


def _matching_priors(
    priors: list[dict[str, Any]], person: dict[str, Any]
) -> list[dict[str, Any]]:
    """The priors that actually describe THIS person, one per base artifact type.

    Three filters, each of which was a real bug before it existed:

    1. Demographic columns must match (NULL is a marginal prior and matches all).
    2. Conditions inside the key must match. A prior conditioned on
       ``founder_type=operator`` says nothing about a technical founder, and an
       attribute we could not resolve for this person disqualifies the
       conditioned row entirely — we fall back to the marginal instead of
       guessing which branch they are on.
    3. Exactly ONE prior survives per base artifact type: the most specific
       match. Otherwise ``hiring_signal@founder_type=operator`` and
       ``hiring_signal@founder_type=operator · has_company_domain=False`` both
       fire and the same single absence is priced twice.
    """
    person_conditions = {
        "founder_type": (person.get("founder_type") or "").lower() or None,
        "has_company_domain": "true" if person.get("has_company_domain") else "false",
        "solo_or_team": (person.get("solo_or_team") or "").lower() or None,
        "sector": (person.get("sector") or "").lower() or None,
    }

    best: dict[str, tuple[int, dict[str, Any]]] = {}
    for pr in priors:
        if pr["sector"] is not None and pr["sector"] != person["sector"]:
            continue
        if pr["solo_or_team"] is not None and pr["solo_or_team"] != person["solo_or_team"]:
            continue
        if pr["resource_tier"] is not None and pr["resource_tier"] != person["resource_tier"]:
            continue

        base, conditions = _parse_prior_key(pr["artifact_type"])
        aliases = _MANIFEST_ARTIFACT_ALIASES.get(base)
        if aliases is None:
            continue  # vocabulary we cannot check absence against — skip, do not widen

        ok = True
        for key, want in conditions.items():
            have = person_conditions.get(key)
            if have is None or have != want:
                ok = False
                break
        if not ok:
            continue

        specificity = len(conditions) + sum(
            1 for col in ("sector", "solo_or_team", "resource_tier") if pr[col] is not None)
        current = best.get(base)
        if current is None or specificity > current[0]:
            row = dict(pr)
            row["_found"] = any(a in person["artifacts_found"] for a in aliases)
            row["_base"] = base
            best[base] = (specificity, row)

    return [row for _, row in best.values()]


def _findability_priors(c: sqlite3.Connection | None) -> list[dict[str, Any]]:
    c = c or ledger._conn()
    try:
        rows = c.execute(
            "SELECT artifact_type, sector, solo_or_team, resource_tier, p, n, thin_cell "
            "FROM findability_prior WHERE computed_from IN ('own_crawl', 'hand_set')"
        ).fetchall()
    except sqlite3.Error:
        return []
    return [dict(r) for r in rows]


def _idea_vs_market(person: dict[str, Any], thesis: Thesis) -> dict[str, Any]:
    """How well the person's own product text lands inside the thesis sectors.

    n is the number of artifacts that carried product text. n=0 renders as
    unresolved, not as a zero — a company we cannot read is not a bad company.
    """
    n_text = 1 if person["text_len"] else 0
    if not n_text:
        return {"point": None, "n": 0, "basis": "no product text observed"}
    in_thesis = person["sector"] in thesis.sectors
    fit = 70.0 if in_thesis else 40.0
    fit += min(15.0, 3.0 * person["enterprise_vocab_hits"])
    fit += min(10.0, 2.0 * person["n_third_party"])
    return {"point": round(min(100.0, fit), 2), "n": person["sector_attr"]["n"] or 1,
            "basis": "sector fit + enterprise vocabulary + third-party observables"}


# --------------------------------------------------------------------------- #
# hard filters — exclude on KNOWN MISMATCH, never on absence
# --------------------------------------------------------------------------- #

def _geography_match(region: str | None, geography: Sequence[str]) -> bool:
    if region is None:
        return True  # unresolved is not a mismatch
    buckets = set(REGION_GROUPS.get(region, (region,)))
    return bool(buckets & {g.upper() for g in geography})


def apply_hard_filters(
    population: dict[str, Any], thesis: Thesis
) -> dict[str, Any]:
    """Sector / stage / geography. Exclusion requires a resolved, conflicting value.

    The counters this returns are the honest ones: how many people the thesis
    ACTUALLY excluded, and — separately — how many it could not resolve and
    therefore kept. Merging those two numbers is how a filter bar quietly becomes
    a network gate.
    """
    kept, excluded = [], []
    unresolved = {"sector": 0, "stage": 0, "geography": 0}
    sectors = {s.lower() for s in thesis.sectors}

    for p in population["people"]:
        reasons = []
        if p["sector"] is None:
            unresolved["sector"] += 1
        elif p["sector"].lower() not in sectors:
            reasons.append({"field": "sector", "thesis": sorted(sectors),
                            "person": p["sector"], "rule": "known mismatch"})
        if p["stage"] is None:
            unresolved["stage"] += 1
        elif p["stage"] != thesis.stage:
            reasons.append({"field": "stage", "thesis": thesis.stage,
                            "person": p["stage"], "rule": "known mismatch"})
        if p["region"] is None:
            unresolved["geography"] += 1
        elif not _geography_match(p["region"], thesis.geography):
            reasons.append({"field": "geography", "thesis": thesis.geography,
                            "person": p["region"], "rule": "known mismatch"})
        if reasons:
            excluded.append({"person_id": p["person_id"],
                             "display_name": p["display_name"], "reasons": reasons})
        else:
            kept.append(p)

    n_total = len(population["people"])
    return {
        "kept": kept,
        "excluded": excluded,
        "n_in": {"value": n_total, "n": n_total},
        "n_kept": {"value": len(kept), "n": n_total},
        "n_excluded": {"value": len(excluded), "n": n_total},
        "n_unresolved_kept": {k: {"value": v, "n": n_total} for k, v in unresolved.items()},
        "rule": ("Hard filters exclude on a RESOLVED conflicting value only. An "
                 "attribute we could not resolve keeps the person on the board and "
                 "moves to the probabilistic layer — a filter that also deleted "
                 "unknowns would delete the cold-start founders this product exists "
                 "to find."),
    }


# --------------------------------------------------------------------------- #
# Pareto sorting + rank-aggregation tiebreak
# --------------------------------------------------------------------------- #

def _dominates(a: tuple[float, int, float], b: tuple[float, int, float]) -> bool:
    return all(x >= y for x, y in zip(a, b)) and any(x > y for x, y in zip(a, b))


def _pareto_fronts(vectors: dict[str, tuple[float, int, float]]) -> dict[str, int]:
    """Non-dominated sorting over (founder point, market ordinal, idea point).

    Market enters as an ORDINAL. Dominance on an ordinal is a comparison, not
    arithmetic, so the categorical axis is never averaged with the numeric ones.

    Deb's fast non-dominated sort — O(M·n²) total rather than O(n²) per front,
    which matters at 845 people on a laptop mid-demo.
    """
    keys = list(vectors)
    dominated_by: dict[str, list[str]] = {k: [] for k in keys}
    n_dominating: dict[str, int] = {k: 0 for k in keys}
    for i, a in enumerate(keys):
        va = vectors[a]
        for b in keys[i + 1:]:
            vb = vectors[b]
            if _dominates(va, vb):
                dominated_by[a].append(b)
                n_dominating[b] += 1
            elif _dominates(vb, va):
                dominated_by[b].append(a)
                n_dominating[a] += 1

    fronts: dict[str, int] = {}
    current = [k for k in keys if n_dominating[k] == 0]
    index = 0
    while current:
        nxt: list[str] = []
        for k in current:
            fronts[k] = index
            for other in dominated_by[k]:
                n_dominating[other] -= 1
                if n_dominating[other] == 0:
                    nxt.append(other)
        current, index = nxt, index + 1
    for k in keys:  # cycle guard; cannot happen with a strict partial order
        fronts.setdefault(k, index)
    return fronts


def _percentile_ranks(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    order = sorted(values.items(), key=lambda kv: kv[1])
    n = len(order)
    return {k: (i / (n - 1) if n > 1 else 1.0) for i, (k, _) in enumerate(order)}


# --------------------------------------------------------------------------- #
# the gate — where risk_appetite becomes money
# --------------------------------------------------------------------------- #

def gate(axes_founder: dict[str, Any], thesis: Thesis) -> dict[str, Any]:
    """The lower-bound gate. Width costs money and nothing else.

    Capital deploys only when the interval's LOWER BOUND clears the conviction
    threshold AND the interval is no wider than the fund's risk appetite allows.
    Both clauses are thesis config; neither is a property of the founder.
    """
    low = axes_founder["interval_low"]
    width = axes_founder["width"]
    clears = low >= thesis.conviction_threshold
    narrow = width <= thesis.max_interval_width

    if clears and narrow:
        verdict, rule = "decide_now", "interval_low >= conviction_threshold AND width <= max_interval_width"
        sentence = (f"Lower bound {low} clears {thesis.conviction_threshold} and the interval "
                    f"is {width} wide, inside the {thesis.max_interval_width} this fund "
                    f"tolerates at risk_appetite={thesis.risk_appetite}. Deploy.")
    elif clears and not narrow:
        verdict, rule = "probe_further", "interval too wide for this risk appetite"
        sentence = (f"Lower bound {low} clears {thesis.conviction_threshold}, but the interval "
                    f"is {width} wide against a {thesis.max_interval_width} ceiling at "
                    f"risk_appetite={thesis.risk_appetite}. The evidence is not weaker — "
                    f"this fund's tolerance for width is. Probe further.")
    elif axes_founder["point"] >= thesis.conviction_threshold:
        verdict, rule = "probe_further", "point clears, lower bound does not"
        sentence = (f"Point {axes_founder['point']} clears {thesis.conviction_threshold} but the "
                    f"lower bound {low} does not. We do not deploy on a point estimate.")
    else:
        verdict, rule = "pass", "point below conviction threshold"
        sentence = (f"Point {axes_founder['point']} is below the {thesis.conviction_threshold} "
                    f"conviction threshold. Pass.")

    return {
        "verdict": verdict, "gate_passed": verdict == "decide_now",
        "gate_rule_applied": rule, "gate_sentence": sentence,
        "interval_low": low, "interval_width": width,
        "max_interval_width": thesis.max_interval_width,
        "conviction_threshold": thesis.conviction_threshold,
        "risk_appetite": thesis.risk_appetite,
        "n": axes_founder["n"],
    }


# --------------------------------------------------------------------------- #
# THE ENTRY POINT — apply a thesis to the collected population
# --------------------------------------------------------------------------- #

def apply_thesis(
    thesis: Thesis,
    asof: str,
    *,
    population: dict[str, Any] | None = None,
    score_fn: Callable[..., dict[str, Any]] | None = None,
    connection: sqlite3.Connection | None = None,
    top: int | None = None,
) -> dict[str, Any]:
    """Apply a thesis to the collected population and return the ranked board.

    ``score_fn(person, population, cache) -> {point, interval_low, interval_high,
    width, n, ...}``. Defaults to the local closed-form estimate so this module
    runs standalone; the integrator passes ``worker.scoring.founder_score`` or
    ``worker.scoring.axes`` here in one line when they land.
    """
    c = connection or ledger._conn()
    population = population or build_population(asof, connection=c)
    score_fn = score_fn or default_score_fn
    cache: dict[str, Any] = {"connection": c}

    filtered = apply_hard_filters(population, thesis)
    market = population["market_by_sector"]

    scored: list[dict[str, Any]] = []
    for p in filtered["kept"]:
        founder = score_fn(p, population, cache)
        m = market.get(p["sector"] or "", {"label": "neutral", "n": 0,
                                           "basis": "sector unresolved"})
        idea = _idea_vs_market(p, thesis)
        scored.append({
            "person_id": p["person_id"], "display_name": p["display_name"],
            "sector": p["sector"], "region": p["region"],
            "founder_type": p["founder_type"],
            "resource_tier": p["resource_tier"], "solo_or_team": p["solo_or_team"],
            "channels": p["channels"], "contact_status": p["contact_status"],
            "provenance_class": p["provenance_class"],
            "n_observations": p["n_observations"],
            "axes": {
                "founder": founder,
                "market": {"value": None, "label": m["label"], "n": m["n"],
                           "categorical": True, "basis": m["basis"]},
                "idea_vs_market": idea,
            },
            "gate": gate(founder, thesis),
            "_person": p,
        })

    # ---- Pareto fronts over the 3-vector; market as an ordinal, never averaged
    vectors = {
        s["person_id"]: (
            s["axes"]["founder"]["point"],
            _MARKET_ORDINAL.get(s["axes"]["market"]["label"], 1),
            s["axes"]["idea_vs_market"]["point"] or 0.0,
        )
        for s in scored
    }
    fronts = _pareto_fronts(vectors)

    # ---- within-front tiebreak: weighted PERCENTILE RANKS, not values
    r_founder = _percentile_ranks({s["person_id"]: s["axes"]["founder"]["point"] for s in scored})
    r_market = _percentile_ranks({s["person_id"]: float(_MARKET_ORDINAL.get(
        s["axes"]["market"]["label"], 1)) for s in scored})
    r_idea = _percentile_ranks({s["person_id"]: (s["axes"]["idea_vs_market"]["point"] or 0.0)
                                for s in scored})
    w = thesis.soft_weights
    for s in scored:
        pid = s["person_id"]
        contrib = {
            "founder_axis": round(w.get("founder_axis", 0.0) * r_founder.get(pid, 0.0), 4),
            "market_axis": round(w.get("market_axis", 0.0) * r_market.get(pid, 0.0), 4),
            "idea_vs_market_axis": round(
                w.get("idea_vs_market_axis", 0.0) * r_idea.get(pid, 0.0), 4),
        }
        s["pareto_front"] = fronts.get(pid, 0)
        s["order_key"] = round(sum(contrib.values()), 4)
        s["order_key_contributions"] = contrib
        s["order_key_note"] = (
            "Weighted percentile RANKS, used only to order within a Pareto front. "
            "It is not a score and is never rendered as one — no composite exists.")

    scored.sort(key=lambda s: (s["pareto_front"], -s["order_key"], s["person_id"]))
    for i, s in enumerate(scored, start=1):
        s["rank"] = i
        s.pop("_person", None)

    counts: dict[str, int] = {}
    for s in scored:
        counts[s["gate"]["verdict"]] = counts.get(s["gate"]["verdict"], 0) + 1

    ranked = scored[:top] if top else scored
    n_total = population["n_people"]["value"]
    return {
        "asof": population["asof"],
        "thesis_id": thesis.thesis_id,
        "thesis_name": thesis.name,
        "risk_appetite": thesis.risk_appetite,
        "max_interval_width": thesis.max_interval_width,
        "conviction_threshold": thesis.conviction_threshold,
        "soft_weights": dict(thesis.soft_weights),
        "n_population": {"value": n_total, "n": n_total},
        "n_observations": population["n_observations"],
        "n_ledger_reads": population["n_ledger_reads"],
        "n_ranked": {"value": len(scored), "n": n_total},
        "hard_filters": {k: v for k, v in filtered.items() if k not in ("kept", "excluded")},
        "excluded_sample": filtered["excluded"][:10],
        "verdict_counts": {k: {"value": v, "n": len(scored)} for k, v in counts.items()},
        "ranked": ranked,
        "market_by_sector": market,
    }


def compare_boards(
    before: dict[str, Any], after: dict[str, Any], *, top: int = 10
) -> dict[str, Any]:
    """Rank and verdict movement between two theses. This is the on-camera diff."""
    a = {s["person_id"]: s for s in before["ranked"]}
    b = {s["person_id"]: s for s in after["ranked"]}
    both = set(a) & set(b)
    entered = sorted(set(b) - set(a))
    left = sorted(set(a) - set(b))

    # Rank and verdict movement is only meaningful for people on BOTH boards.
    # Someone the new thesis filtered out did not "change verdict" — they left
    # the board, and merging the two counts would inflate the headline number.
    moves = []
    for pid in both:
        ra, rb = a[pid]["rank"], b[pid]["rank"]
        va = a[pid]["gate"]["verdict"]
        vb = b[pid]["gate"]["verdict"]
        if ra != rb or va != vb:
            moves.append({
                "person_id": pid, "display_name": a[pid]["display_name"],
                "rank_before": ra, "rank_after": rb, "rank_delta": ra - rb,
                "verdict_before": va, "verdict_after": vb,
                "verdict_changed": va != vb,
            })
    # Verdict changes first, then movement at the top of the board — a swap
    # between rank 710 and 260 is arithmetically large and investably irrelevant.
    moves.sort(key=lambda m: (not m["verdict_changed"],
                              min(m["rank_before"], m["rank_after"]),
                              -abs(m["rank_delta"])))
    n = len(both)
    return {
        "n_on_both_boards": {"value": n, "n": len(set(a) | set(b))},
        "n_rank_changed": {"value": sum(1 for m in moves if m["rank_delta"]), "n": n},
        "n_verdict_changed": {"value": sum(1 for m in moves if m["verdict_changed"]), "n": n},
        "n_entered_board": {"value": len(entered), "n": len(b)},
        "n_left_board": {"value": len(left), "n": len(a)},
        "moves": moves[:top],
        "note": ("Rank/verdict movement counted only over people on both boards. People "
                 "the new thesis filtered in or out are counted separately — merging the "
                 "two would inflate the headline."),
    }


def risk_appetite_sweep(
    thesis: Thesis, asof: str, *, population: dict[str, Any] | None = None,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Run the same ledger at low / medium / high and record who crosses the gate.

    This is the proof that risk_appetite is load-bearing: the observations are
    byte-identical across all three runs.
    """
    c = connection or ledger._conn()
    population = population or build_population(asof, connection=c)
    boards = {level: apply_thesis(thesis.replace(risk_appetite=level), asof,
                                  population=population, connection=c)
              for level in ("low", "medium", "high")}
    verdicts: dict[str, dict[str, str]] = {}
    for level, board in boards.items():
        for s in board["ranked"]:
            verdicts.setdefault(s["person_id"], {})[level] = s["gate"]["verdict"]

    transitions = [
        {"person_id": pid, "low": v.get("low"), "medium": v.get("medium"),
         "high": v.get("high")}
        for pid, v in verdicts.items()
        if len({v.get("low"), v.get("medium"), v.get("high")}) > 1
    ]
    return {
        "boards": boards,
        "map": {level: {"max_interval_width": RISK_APPETITE_MAP[level],
                        "n_decide_now": boards[level]["verdict_counts"]
                        .get("decide_now", {}).get("value", 0),
                        "n_probe_further": boards[level]["verdict_counts"]
                        .get("probe_further", {}).get("value", 0)}
                for level in ("low", "medium", "high")},
        "n_transitions": {"value": len(transitions), "n": len(verdicts)},
        "transitions": transitions,
    }


# --------------------------------------------------------------------------- #
# render — matches web/public/demo.json :: thesis, key for key
# --------------------------------------------------------------------------- #

def render_thesis(
    thesis: Thesis,
    *,
    board: dict[str, Any] | None = None,
    sweep: dict[str, Any] | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """The render-ready dict. Same keys and types as ``demo.json :: thesis``.

    Extra keys are additive (``board``, ``n_decide_now`` inside the risk map), so
    ``export_demo.py`` can adopt this with no frontend change.
    """
    sweep_map = (sweep or {}).get("map", {})
    risk_map = {
        level: {
            "max_interval_width": RISK_APPETITE_MAP[level],
            "n": None,
            "basis": "hand-set policy, not estimated",
            **({"n_decide_now": sweep_map[level]["n_decide_now"],
                "n_probe_further": sweep_map[level]["n_probe_further"]}
               if level in sweep_map else {}),
        }
        for level in ("low", "medium", "high")
    }

    if sweep and sweep.get("transitions"):
        names = {}
        for level in ("low", "medium", "high"):
            for s in sweep["boards"][level]["ranked"]:
                names[s["person_id"]] = s["display_name"]
        parts = []
        for t in sweep["transitions"][:3]:
            parts.append(f"{names.get(t['person_id'], t['person_id'])} goes "
                         f"{t['low']} -> {t['medium']} -> {t['high']}")
        load_bearing = (
            "Risk appetite maps to the maximum posterior interval width at which capital "
            "deploys. That makes the thesis load-bearing on our core mechanic rather than "
            f"a filter bar: over the identical ledger, {sweep['n_transitions']['value']} of "
            f"{sweep['n_transitions']['n']} ranked people change verdict when only this one "
            "field moves — " + "; ".join(parts) + ".")
    else:
        load_bearing = (
            "Risk appetite maps to the maximum posterior interval width at which capital "
            "deploys. That makes the thesis load-bearing on our core mechanic rather than "
            "a filter bar.")

    out: dict[str, Any] = {
        "thesis_id": thesis.thesis_id,
        "name": name or thesis.name,
        "configurable": True,
        "configurable_note": (
            "Six persisted fields. Nothing here is hardcoded to one fund; editing any "
            "field re-ranks the board and can move an opportunity across the decision gate."),
        "sectors": list(thesis.sectors),
        "stage": thesis.stage,
        "geography": list(thesis.geography),
        "check_size_usd": int(thesis.check_size_usd),
        "ownership_target_pct": [thesis.ownership_target_pct[0], thesis.ownership_target_pct[1]],
        "risk_appetite": thesis.risk_appetite,
        "risk_appetite_map": risk_map,
        "max_interval_width": thesis.max_interval_width,
        "conviction_threshold": thesis.conviction_threshold,
        "risk_appetite_is_load_bearing": load_bearing,
        "hard_filters": [
            "sector in thesis.sectors",
            f"stage == '{thesis.stage}'",
            "geography in thesis.geography",
        ],
        "hard_filter_semantics": (
            "A hard filter excludes on a RESOLVED conflicting value only. An attribute we "
            "could not resolve keeps the person on the board and resolves probabilistically "
            "with its n printed. Filtering on absence would delete the cold-start founders "
            "this product exists to find."),
        "soft_weights": {
            **thesis.soft_weights,
            "note": ("Soft weights order the board. They never combine the three axes into "
                     "one number — ranking is Pareto non-dominated sorting over the 3-vector, "
                     "and the weights only order WITHIN a front, over percentile ranks."),
        },
        "conviction_threshold_note": (
            f"An opportunity opens on its own when a person's founder-axis lower bound "
            f"crosses {thesis.conviction_threshold} without any human input. That is what "
            f"makes this an operating system rather than a dashboard."),
    }
    if board is not None:
        out["board"] = render_board(board)
    return out


def render_board(board: dict[str, Any], *, top: int = 20) -> dict[str, Any]:
    """Render-ready ranked board. Every number carries its n."""
    return {
        "asof": board["asof"],
        "thesis_id": board["thesis_id"],
        "risk_appetite": board["risk_appetite"],
        "max_interval_width": board["max_interval_width"],
        "conviction_threshold": board["conviction_threshold"],
        "n_population": board["n_population"],
        "n_ranked": board["n_ranked"],
        "n_ledger_reads": board["n_ledger_reads"],
        "hard_filters": board["hard_filters"],
        "verdict_counts": board["verdict_counts"],
        "ranking_method": (
            "Pareto non-dominated sorting over (founder, market ordinal, idea-vs-market); "
            "weighted percentile ranks order within a front. No composite score exists."),
        "rows": [
            {
                "rank": s["rank"], "person_id": s["person_id"],
                "display_name": s["display_name"], "sector": s["sector"],
                "region": s["region"], "founder_type": s["founder_type"],
                "channels": s["channels"], "provenance_class": s["provenance_class"],
                "n_observations": {"value": s["n_observations"], "n": s["n_observations"]},
                "axes": s["axes"],
                "pareto_front": s["pareto_front"],
                "order_key": s["order_key"],
                "order_key_contributions": s["order_key_contributions"],
                "order_key_note": s["order_key_note"],
                "verdict": s["gate"]["verdict"],
                "gate": s["gate"],
            }
            for s in board["ranked"][:top]
        ],
    }


# --------------------------------------------------------------------------- #
# CLI — the demo
# --------------------------------------------------------------------------- #

DEFAULT_ASOF = "2026-07-19T02:14:33Z"


def _row(s: dict[str, Any]) -> str:
    f = s["axes"]["founder"]
    return (f"{s['rank']:>3}  {s['display_name'][:26]:<26} {str(s['sector'])[:18]:<18} "
            f"{str(s['region'] or '—'):<6} n={s['n_observations']:<4} "
            f"{f['point']:>5} [{f['interval_low']:>5},{f['interval_high']:>5}] "
            f"w={f['width']:>5}  {s['axes']['market']['label']:<8} "
            f"{s['gate']['verdict']}")


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Thesis Engine — configurable, load-bearing.")
    ap.add_argument("--asof", default=DEFAULT_ASOF)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--json", action="store_true", help="emit the render-ready dict")
    args = ap.parse_args(argv)

    store.open_ledger()  # NEVER reset=True — four agents share this ledger
    base = load_active_thesis(args.asof)
    pop = build_population(args.asof)

    print(f"asof {args.asof} · {pop['n_people']['value']} people · "
          f"{pop['n_observations']['value']} observations · "
          f"{pop['n_ledger_reads']['value']} ledger read")
    print(f"\nACTIVE THESIS  {base.thesis_id} v{base.version_number}")
    print(f"  sectors      {base.sectors}")
    print(f"  stage        {base.stage}")
    print(f"  geography    {base.geography}")
    print(f"  check size   ${base.check_size_usd:,}")
    print(f"  ownership    {base.ownership_target_pct[0]}–{base.ownership_target_pct[1]}%")
    print(f"  risk         {base.risk_appetite}  ->  max_interval_width "
          f"{base.max_interval_width}")
    print(f"  conviction   {base.conviction_threshold}")

    board = apply_thesis(base, args.asof, population=pop)
    hf = board["hard_filters"]
    print(f"\nHARD FILTERS  {hf['n_kept']['value']}/{hf['n_in']['value']} kept · "
          f"{hf['n_excluded']['value']} excluded on a RESOLVED mismatch · kept despite "
          f"unresolved: " + ", ".join(f"{k}={v['value']}" for k, v in
                                      hf["n_unresolved_kept"].items()))
    print(f"\nBOARD — top {args.top}   ({base.risk_appetite} risk appetite)")
    print(f"{'#':>3}  {'person':<26} {'sector':<18} {'reg':<6} {'n':<6} "
          f"{'point':>5} {'interval':^15} {'width':>7}  {'market':<8} verdict")
    for s in board["ranked"][:args.top]:
        print(_row(s))
    print("  verdicts: " + ", ".join(f"{k}={v['value']}" for k, v in
                                     board["verdict_counts"].items()))

    # ---- 1. change ONE field: the sector list. The board re-ranks.
    swapped = base.replace(sectors=["ai_infra", "devtools", "data_infra"],
                           soft_weights={"founder_axis": 0.25,
                                         "idea_vs_market_axis": 0.55,
                                         "market_axis": 0.20})
    board2 = apply_thesis(swapped, args.asof, population=pop)
    print(f"\n--- THESIS CHANGED: sectors {base.sectors} -> {swapped.sectors}, "
          f"weights founder .40->.25 / idea .35->.55 ---")
    print(f"HARD FILTERS  {board2['hard_filters']['n_kept']['value']}/"
          f"{board2['hard_filters']['n_in']['value']} kept")
    for s in board2["ranked"][:args.top]:
        print(_row(s))
    diff = compare_boards(board, board2)
    print(f"  re-ranked: {diff['n_rank_changed']['value']}/"
          f"{diff['n_on_both_boards']['value']} people on both boards changed rank · "
          f"{diff['n_verdict_changed']['value']} changed verdict · "
          f"{diff['n_left_board']['value']} left the board · "
          f"{diff['n_entered_board']['value']} entered")
    for m in diff["moves"][:6]:
        print(f"    {m['display_name'][:26]:<26} rank {m['rank_before']} -> {m['rank_after']}"
              f"   verdict {m['verdict_before']} -> {m['verdict_after']}")

    # ---- 2. change ONE field: risk appetite. Same ledger, capital moves.
    sweep = risk_appetite_sweep(base, args.asof, population=pop)
    print("\n--- RISK APPETITE SWEEP (identical ledger, identical scores) ---")
    for level in ("low", "medium", "high"):
        m = sweep["map"][level]
        print(f"  {level:<7} max_interval_width={m['max_interval_width']:<5} "
              f"decide_now={m['n_decide_now']:<4} probe_further={m['n_probe_further']}")
    print(f"  {sweep['n_transitions']['value']}/{sweep['n_transitions']['n']} people "
          f"change verdict on this one field alone.")
    names = {s["person_id"]: s["display_name"] for s in sweep["boards"]["medium"]["ranked"]}
    for t in sweep["transitions"][:8]:
        print(f"    {names.get(t['person_id'], t['person_id'])[:28]:<28} "
              f"low={t['low']:<14} medium={t['medium']:<14} high={t['high']}")

    for level in ("low", "high"):
        for s in sweep["boards"][level]["ranked"]:
            if s["person_id"] in {t["person_id"] for t in sweep["transitions"]}:
                print(f"\n  [{level}] {s['display_name']}: {s['gate']['gate_sentence']}")
                break

    if args.json:
        print("\n" + json.dumps(render_thesis(base, board=board, sweep=sweep), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
