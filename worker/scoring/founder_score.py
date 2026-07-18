"""B1 — the empirical-Bayes Founder Score, fitted on the collected population.

    uv run python -m worker.scoring.founder_score

WHAT THIS COMPUTES
------------------
For every person, per component (``credibility`` and ``build_capability``)::

    theta_hat = w * (direct evidence)  +  (1 - w) * (reference-class posterior mean)
    w         = n / (n + k)

``k`` is not a taste parameter and nobody typed 10. It is ``sigma^2 / tau^2`` —
the ratio of the within-person variance of evidence to the between-person
variance of true means — estimated by method of moments over the whole collected
population (Efron-Morris partial pooling), refitted at every asof. A population
where people differ a lot and individual evidence is quiet produces a small ``k``
and lets thin evidence speak; a population where the noise swamps the signal
produces a large ``k`` and holds everyone near their class.

WHAT COUNTS AS ONE OBSERVATION
------------------------------
Not one ledger row. Three rows scraped off one arXiv record are one fetch, not
three independent reads of a person, and counting them as three would let a
single crawl manufacture confidence. Evidence is therefore collapsed into
INDEPENDENT STREAMS before scoring — by source class for credibility, by
artifact kind for build capability — and every stream reports how many rows it
stands on. ``n`` in this module is a count of streams, and each one is what
:mod:`worker.scoring.attribution` drops.

THE REFERENCE CLASS CONTAINS NO PEDIGREE FIELD
----------------------------------------------
``{primary artifact type, sector, solo/team, resource tier, region}``. No school,
no employer, no accelerator, no investor, no follower count. This is the whole
anti-network-gate and it is the most important constraint in this file: every
other module here could be rebuilt in an hour, but this dimension list cannot be
recovered once it has quietly grown a pedigree column. A class is used at full
depth only when its cell holds at least ``MIN_CELL`` people; otherwise dimensions
are dropped along a fixed ladder and the cell says which ones
(``shrunk_to_margin``, ``thin_cell``, ``n_cell``). A marginal rate wearing a
conditional's clothes is worse than an honest marginal rate.

ABSENCE WIDENS THE INTERVAL AND NEVER LOWERS THE POINT
------------------------------------------------------
Artifacts the reference class predicted and we did not find inflate the posterior
variance in proportion to how likely they were to exist — ``var * (1 + m/(n+k))``
where ``m`` is the summed findability mass of what is missing. The point estimate
is arithmetically untouched by absence: it is a weighted mean over evidence that
exists, and an absence never enters that mean. A solo bootstrapped operator with
no GitHub pays nothing for it. They get a wider interval, which is a request for
evidence rather than a verdict.

EVERY NUMBER CARRIES ITS n
--------------------------
Quantities are emitted as ``{"value": x, "n": n}``. If the sample size cannot be
stated, the number is not shipped.

NEVER RESETS
------------
Versions are appended through :func:`worker.ledger.append_founder_score_version`,
keyed to the PERSON, so the history replays as a step function across however
many ventures they have had. There is no update path here because there is no
update path anywhere in the worker.

NOT AN LLM
----------
Closed-form arithmetic over ledger rows, standard library only. That is what
makes :mod:`worker.scoring.attribution` an exact recompute rather than the model
narrating a story about its own reasoning.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import statistics
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Sequence

from worker import ledger, store

# --------------------------------------------------------------------------- #
# constants — the modelling choices, stated rather than buried
# --------------------------------------------------------------------------- #

COMPONENTS = ("credibility", "build_capability")

#: 95% normal interval. The only distributional assumption in the file.
Z = 1.959964

#: The reference class. Five dimensions, none of them pedigree.
REFERENCE_CLASS_DIMENSIONS = (
    "primary_artifact_type",
    "sector",
    "solo_or_team",
    "resource_tier",
    "region",
)

#: Dimensions deliberately excluded, printed on screen beside the ones used.
PEDIGREE_FIELDS_EXCLUDED = (
    "school",
    "employer",
    "prior_vc_backed_employer",
    "accelerator",
    "investor",
    "follower_count",
)

#: The backoff ladder for the score's reference class, most specific first. We
#: drop geography before resources, resources before team shape, and we keep
#: sector longest because it is the dimension the thesis is written in.
CLASS_LEVELS: tuple[tuple[str, ...], ...] = (
    ("primary_artifact_type", "sector", "solo_or_team", "resource_tier", "region"),
    ("primary_artifact_type", "sector", "solo_or_team", "resource_tier"),
    ("primary_artifact_type", "sector", "solo_or_team"),
    ("primary_artifact_type", "sector"),
    ("sector", "solo_or_team", "resource_tier"),
    ("sector", "solo_or_team"),
    ("primary_artifact_type",),
    ("sector",),
    (),
)

#: The backoff ladder for findability priors. It deliberately does NOT contain
#: primary_artifact_type: conditioning the rate of an artifact on the artifact
#: the person is already known for would make every rate 1.0 and price nothing.
FINDABILITY_LEVELS: tuple[tuple[str, ...], ...] = (
    ("sector", "solo_or_team", "resource_tier", "region"),
    ("sector", "solo_or_team", "resource_tier"),
    ("sector", "solo_or_team"),
    ("sector",),
    (),
)

#: A cell narrower than this is not trusted at full depth; dimensions are dropped.
MIN_CELL = 12

#: An artifact whose class rate clears this is "expected" for the profile.
EXPECT_THRESHOLD = 0.25

#: Class rates below this make an absence uninformative — already priced.
ALREADY_PRICED_BELOW = 0.15

#: k is clamped to this range so a degenerate variance estimate cannot produce
#: either a prior that ignores evidence or evidence that ignores the prior. When
#: a bound binds, the CLI says so rather than letting the number pass silently.
K_BOUNDS = (1.0, 50.0)

#: Below this many people carrying two or more INDEPENDENT streams, the
#: within-person variance is not identifiable and we refuse to pretend it is. On
#: this crawl that is the credibility component's situation exactly: almost
#: nobody is known through two different source classes yet, so a k fitted on the
#: handful who are would be an artefact of those few. In that case k is BORROWED
#: from the component where it is identified, sigma^2 is taken from the
#: population spread of a single stream, and both facts are printed on screen.
MIN_IDENTIFYING_GROUPS = 20

#: Fallback source-class reliabilities, used only when the hand-set table has
#: not been loaded into the ledger. Same numbers, same rationale.
FALLBACK_RELIABILITY = {
    "self_report": -1.2,
    "interview": 0.0,
    "forum_post": 0.0,
    "press": 0.2,
    "code_host": 0.8,
    "preprint": 0.9,
    "third_party_observable": 1.1,
    "registry_filing": 2.4,
}

#: Hand-set build value per artifact type, in [0, 1], published like the
#: reliability table and defended line by line. This is the ONE hand-set table in
#: the scorer; every prior, rate and shrinkage constant below is fitted.
ARTIFACT_VALUE: dict[str, tuple[float, str]] = {
    "changelog": (0.78, "Dated shipping cadence. Costly to fake, trivial to check."),
    "pricing_page": (0.72, "A price is a commitment to a buyer, not a plan."),
    "product_url": (0.62, "Something exists at a URL and answers."),
    "landing_page": (0.58, "A page exists; it may be all that exists."),
    "show_hn_post": (0.66, "Shipped in public, with a date and a thread."),
    "preprint": (0.68, "A dated, versioned technical artifact. Hard to backdate."),
    "trademark_application": (0.60, "Self-filed IP move: ~$250 and a real intent-to-use."),
    "trademark_filing": (0.60, "As above — filed, not announced."),
    "trademark_identification": (0.55, "Machine-readable statement of what the product is."),
    "job_posting": (0.58, "Spending money on people is a build signal."),
    "team_page": (0.56, "Named humans attached to the thing."),
    "hiring_thread_post": (0.52, "Operator history, self-stated, in public and dated."),
    "forum_comment": (0.48, "Lived domain exposure. Weak build evidence on its own."),
    "forum_thread": (0.48, "As above."),
    "account_first_post": (0.45, "An account that started; nothing built yet."),
    "account_footprint": (0.45, "Presence, not production."),
    "no_page": (0.20, "The domain resolves to nothing. Observed, not missing."),
}
ARTIFACT_VALUE_DEFAULT = (
    0.50,
    "Unrecognised artifact type — scored neutral, and listed as such rather than dropped.",
)

#: Milestones override the artifact value. Winding down is absent from this table
#: on purpose: it is not a capability event and we refuse to score it as one.
MILESTONE_VALUE: dict[str, tuple[float, str]] = {
    "first_revenue": (0.88, "Someone paid. The strongest build signal available."),
    "shipped": (0.80, "A thing exists that did not exist before."),
    "first_hire": (0.72, "Someone else bet their salary on it."),
    "incorporated": (0.70, "A registry filing with a date attached."),
    "trademark_filed": (0.66, "Filed, not announced."),
}

#: How hard the rarity of an artifact INSIDE the person's own resource class
#: adjusts its build value. Centred on the population rate, so it moves either
#: way: shipping a pricing page while bootstrapped counts for more than shipping
#: one in a class where every member has had the budget to.
RESOURCE_ADJUST_ALPHA = 0.5


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _clip(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def q(value: Any, n: int) -> dict[str, Any]:
    """The pervasive contract shape: a number that carries its sample size."""
    return {"value": value, "n": int(n)}


# --------------------------------------------------------------------------- #
# evidence streams — one row each, so leave-one-out has something to drop
# --------------------------------------------------------------------------- #

@dataclass
class Item:
    """One INDEPENDENT evidence stream contributing to one component."""

    key: str
    kind: str                 # 'observation' | 'claim'
    component: str
    y: float                  # in [0, 1]
    label: str
    basis: str
    observed_at: str
    n_rows: int = 1
    source_class: str | None = None
    artifact_type: str | None = None
    observation_ids: list[str] = field(default_factory=list)
    claim_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.key,
            "kind": self.kind,
            "label": self.label,
            "y": round(self.y, 4),
            "n_rows": self.n_rows,
            "basis": self.basis,
            "observed_at": self.observed_at,
            "source_class": self.source_class,
            "artifact_type": self.artifact_type,
            "observation_ids": self.observation_ids[:8],
            "claim_id": self.claim_id,
        }


@dataclass
class Absence:
    """An artifact the class predicted that we did not find."""

    artifact_type: str
    p: float
    n_cell: int
    reason: str

    @property
    def expected(self) -> bool:
        return self.p >= EXPECT_THRESHOLD

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": self.artifact_type,
            "findability_prior": q(round(self.p, 3), self.n_cell),
            "expected": self.expected,
            "penalised": False,
            "effect": "widens the interval; the point estimate is untouched",
            "reason": self.reason,
        }


# --------------------------------------------------------------------------- #
# method-of-moments partial pooling — used at person level and at cell level
# --------------------------------------------------------------------------- #

def _mom(groups: Sequence[Sequence[float]], *, borrow_k: float | None = None) -> dict[str, Any]:
    """Efron-Morris shrinkage constants from grouped values.

    ``sigma2`` is the pooled within-group variance, ``tau2`` the between-group
    variance of true means with the sampling component removed, and
    ``k = sigma2 / tau2`` is the shrinkage weight in units of observations.

    ``k`` is identifiable only when enough people carry two or more independent
    streams — one measurement per person cannot tell measurement noise apart from
    real difference between people, no matter how many people there are. Below
    :data:`MIN_IDENTIFYING_GROUPS` such people this returns ``identified=False``,
    and the caller either supplies ``borrow_k`` from a component where the same
    quantity IS identified or accepts a loudly-labelled clamp.
    """
    usable = [list(g) for g in groups if g]
    if not usable:
        return {
            "sigma2": 0.04, "tau2": 0.01, "k": 4.0, "n_groups": 0, "n_values": 0,
            "n_multi": 0, "identified": False, "borrowed": False, "k_at_bound": False,
            "grand_mean": 0.5, "notes": ["no data at this asof; k held at 4.0"],
        }

    values = [v for g in usable for v in g]
    grand = statistics.fmean(values)
    means = [statistics.fmean(g) for g in usable]
    population_var = statistics.pvariance(values) if len(values) > 1 else 0.04
    notes: list[str] = []

    multi = [g for g in usable if len(g) >= 2]
    identified = len(multi) >= MIN_IDENTIFYING_GROUPS

    if identified:
        ss = sum(sum((v - statistics.fmean(g)) ** 2 for v in g) for g in multi)
        df = sum(len(g) - 1 for g in multi)
        sigma2 = (ss / df) if df else population_var
        notes.append(
            f"sigma^2 = pooled within-person variance over {len(multi)} people "
            "carrying two or more independent streams"
        )
        var_means = statistics.pvariance(means) if len(means) > 1 else 0.0
        mean_inv_n = statistics.fmean([1.0 / len(g) for g in usable])
        tau2 = var_means - sigma2 * mean_inv_n
        floor = max(sigma2 / K_BOUNDS[1], 1e-9)
        if tau2 < floor:
            tau2 = floor
            notes.append(
                "tau^2 floored: the spread between people is smaller than the "
                "sampling noise at these sample sizes, so the class carries more"
            )
        raw_k = sigma2 / tau2
    else:
        # Not identifiable. Say so, take sigma^2 from the one thing we CAN
        # measure — the spread of a single stream across the population — and
        # borrow the ratio rather than invent it.
        sigma2 = population_var
        notes.append(
            f"within-person variance NOT identifiable: only {len(multi)} people carry "
            f"two or more independent streams (need {MIN_IDENTIFYING_GROUPS}). "
            "sigma^2 taken from the population spread of a single stream"
        )
        if borrow_k is not None:
            raw_k = borrow_k
            notes.append(
                f"k={borrow_k:.2f} BORROWED from the component where it is identified, "
                "rather than fitted on a handful of people"
            )
        else:
            raw_k = sigma2 / max(
                (statistics.pvariance(means) if len(means) > 1 else 0.0), sigma2 / K_BOUNDS[1]
            )
            notes.append("no donor component available; k left to the clamp")
        tau2 = sigma2 / raw_k if raw_k else sigma2

    k = min(max(raw_k, K_BOUNDS[0]), K_BOUNDS[1])
    return {
        "sigma2": sigma2,
        "tau2": tau2,
        "k": k,
        "raw_k": raw_k,
        "k_at_bound": not (K_BOUNDS[0] < raw_k < K_BOUNDS[1]),
        "identified": identified,
        "borrowed": (not identified) and borrow_k is not None,
        "n_groups": len(usable),
        "n_multi": len(multi),
        "n_values": len(values),
        "grand_mean": grand,
        "notes": notes,
    }


# --------------------------------------------------------------------------- #
# the fitted population
# --------------------------------------------------------------------------- #

def _level_key(profile: dict[str, Any], dims: Sequence[str]) -> tuple:
    return tuple((d, profile.get(d) or "unknown") for d in dims)


@dataclass
class Population:
    """Everything fitted from the collected ledger at one asof."""

    asof: str
    n_people: int
    n_observations: int
    people: dict[str, dict[str, Any]] = field(default_factory=dict)
    items: dict[str, dict[str, list[Item]]] = field(default_factory=dict)
    fit: dict[str, dict[str, Any]] = field(default_factory=dict)
    cell_fit: dict[str, dict[str, Any]] = field(default_factory=dict)
    class_means: dict[str, dict[tuple, tuple[float, int]]] = field(default_factory=dict)
    artifact_rates: dict[tuple, dict[str, tuple[float, int]]] = field(default_factory=dict)
    reliability: dict[str, float] = field(default_factory=dict)
    reliability_source: str = "fallback"

    # -- reference class resolution ----------------------------------------- #

    def resolve_class(self, profile: dict[str, Any], component: str) -> dict[str, Any]:
        """Walk the backoff ladder until the cell is wide enough to trust."""
        table = self.class_means[component]
        chosen_dims: tuple[str, ...] = ()
        raw = None
        n_cell = 0
        idx = len(CLASS_LEVELS) - 1
        for i, dims in enumerate(CLASS_LEVELS):
            entry = table.get(_level_key(profile, dims))
            if entry and (entry[1] >= MIN_CELL or not dims):
                chosen_dims, raw, n_cell, idx = dims, entry[0], entry[1], i
                break
        if raw is None:
            raw = self.fit[component]["grand_mean"]

        # Shrink the cell mean toward the next level up the ladder, by the fitted
        # cell-level constant. A thin cell is pulled almost entirely to its margin.
        parent_mean = self.fit[component]["grand_mean"]
        for dims in CLASS_LEVELS[idx + 1:]:
            entry = table.get(_level_key(profile, dims))
            if entry:
                parent_mean = entry[0]
                break
        k_cell = self.cell_fit[component]["k"]
        mean = (n_cell * raw + k_cell * parent_mean) / (n_cell + k_cell) if n_cell else parent_mean

        dropped = [d for d in REFERENCE_CLASS_DIMENSIONS if d not in chosen_dims]
        return {
            "dimensions_used": list(chosen_dims),
            "dimensions_dropped": dropped,
            "values": {d: profile.get(d) for d in REFERENCE_CLASS_DIMENSIONS},
            "cell_mean_raw": round(100 * raw, 1),
            "cell_mean_shrunk": round(100 * mean, 1),
            "k_cell": round(k_cell, 2),
            "n_cell": n_cell,
            "n_population": self.n_people,
            "thin_cell": n_cell < MIN_CELL,
            "shrunk_to_margin": bool(dropped),
            "contains_no_pedigree_field": True,
            "excluded_fields": list(PEDIGREE_FIELDS_EXCLUDED),
            "mean": mean,
        }

    def rates_for(self, profile: dict[str, Any]) -> tuple[dict[str, tuple[float, int]], list[str]]:
        """Findability rates for this person's resource class, backed off."""
        for dims in FINDABILITY_LEVELS:
            rates = self.artifact_rates.get(_level_key(profile, dims))
            if rates:
                n_cell = max((c for _, c in rates.values()), default=0)
                if n_cell >= MIN_CELL or not dims:
                    return rates, list(dims)
        return self.artifact_rates.get((), {}), []


def _people_at(asof: str, c: sqlite3.Connection) -> list[dict[str, Any]]:
    """Person spine rows visible at ``asof``. Not the observation table."""
    return c.execute(
        "SELECT person_id, display_name, sector, solo_or_team, resource_tier, region, "
        "provenance_class, first_observed_at FROM person WHERE observed_at <= :asof",
        {"asof": ledger.to_iso(asof)},
    ).fetchall()


def _reliability_table(c: sqlite3.Connection) -> tuple[dict[str, float], str]:
    try:
        rows = c.execute("SELECT source_class, log_odds FROM source_reliability").fetchall()
    except sqlite3.Error:
        rows = []
    if rows:
        return {r["source_class"]: float(r["log_odds"]) for r in rows}, "ledger.source_reliability"
    return dict(FALLBACK_RELIABILITY), "module fallback (hand-set table not loaded)"


def _build_value(row: dict[str, Any]) -> tuple[float, str]:
    if row.get("is_milestone") and row.get("milestone_type") in MILESTONE_VALUE:
        v, why = MILESTONE_VALUE[row["milestone_type"]]
        return v, f"milestone '{row['milestone_type']}': {why}"
    art = row.get("artifact_type") or ""
    v, why = ARTIFACT_VALUE.get(art, ARTIFACT_VALUE_DEFAULT)
    return v, f"artifact '{art or 'none'}': {why}"


def fit_population(
    asof: str,
    *,
    connection: sqlite3.Connection | None = None,
) -> Population:
    """Fit class priors, findability rates and shrinkage constants at ``asof``.

    One pass over the ledger through the chokepoint, grouped in Python. Nothing
    here is hardcoded: every rate is counted off the collected population as it
    stood at this instant, and refitting at a past asof refits the priors too.
    """
    c = connection or store.conn()
    asof = ledger.to_iso(asof)

    rows = store.read_observations(asof, order="asc", connection=c)
    claims = ledger.read_claims(asof, connection=c)
    people_rows = _people_at(asof, c)
    reliability, reliability_source = _reliability_table(c)

    by_person: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        if r.get("person_id"):
            by_person.setdefault(r["person_id"], []).append(r)
    claims_by_person: dict[str, list[dict[str, Any]]] = {}
    for cl in claims:
        if cl.get("person_id"):
            claims_by_person.setdefault(cl["person_id"], []).append(cl)

    pop = Population(
        asof=asof,
        n_people=len(people_rows),
        n_observations=len(rows),
        reliability=reliability,
        reliability_source=reliability_source,
    )

    # -- person profiles, including the primary artifact type ---------------- #
    artifact_sets: dict[str, set[str]] = {}
    for p in people_rows:
        pid = p["person_id"]
        obs = by_person.get(pid, [])
        arts = [o["artifact_type"] for o in obs if o.get("artifact_type")]
        artifact_sets[pid] = set(arts)
        profile = dict(p)
        profile["primary_artifact_type"] = statistics.mode(arts) if arts else "none"
        profile["n_observations"] = len(obs)
        pop.people[pid] = profile

    # -- findability rates, per resource-class level ------------------------- #
    all_types = sorted({a for s in artifact_sets.values() for a in s})
    members: dict[tuple, list[str]] = {}
    for pid, profile in pop.people.items():
        for dims in FINDABILITY_LEVELS:
            members.setdefault(_level_key(profile, dims), []).append(pid)
    for key, mem in members.items():
        n_cell = len(mem)
        pop.artifact_rates[key] = {
            a: (sum(1 for m in mem if a in artifact_sets[m]) / n_cell, n_cell)
            for a in all_types
        }

    # -- evidence streams ---------------------------------------------------- #
    global_rates = pop.artifact_rates.get((), {})
    for pid, profile in pop.people.items():
        rates, _ = pop.rates_for(profile)
        pop.items[pid] = _items_for(
            by_person.get(pid, []),
            claims_by_person.get(pid, []),
            reliability=reliability,
            class_rates=rates,
            global_rates=global_rates,
        )

    # -- shrinkage constants and class means, per component ------------------ #
    # Pass one fits every component independently; pass two lets a component
    # whose k is not identifiable borrow it from one where it is, so the
    # unidentified case is a stated borrow rather than a silent clamp.
    grouped = {
        comp: [[i.y for i in pop.items[pid][comp]] for pid in pop.people]
        for comp in COMPONENTS
    }
    first = {comp: _mom(grouped[comp]) for comp in COMPONENTS}
    donors = [c for c in COMPONENTS if first[c]["identified"]]
    donor = max(donors, key=lambda c: first[c]["n_multi"]) if donors else None
    for comp in COMPONENTS:
        if first[comp]["identified"] or donor is None:
            pop.fit[comp] = first[comp]
        else:
            pop.fit[comp] = _mom(grouped[comp], borrow_k=first[donor]["k"])
            pop.fit[comp]["borrowed_from"] = donor

    for comp in COMPONENTS:
        per_level: dict[tuple, list[float]] = {}
        for pid, profile in pop.people.items():
            ys = [i.y for i in pop.items[pid][comp]]
            if not ys:
                continue
            m = statistics.fmean(ys)
            for dims in CLASS_LEVELS:
                per_level.setdefault(_level_key(profile, dims), []).append(m)
        pop.class_means[comp] = {
            key: (statistics.fmean(vals), len(vals)) for key, vals in per_level.items()
        }
        pop.class_means[comp].setdefault((), (pop.fit[comp]["grand_mean"], 0))

        full = len(CLASS_LEVELS[0])
        cells = [vals for key, vals in per_level.items() if len(key) == full and len(vals) > 1]
        pop.cell_fit[comp] = _mom(cells) if cells else dict(pop.fit[comp])

    return pop


def _items_for(
    obs: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    *,
    reliability: dict[str, float],
    class_rates: dict[str, tuple[float, int]],
    global_rates: dict[str, tuple[float, int]],
) -> dict[str, list[Item]]:
    """Collapse ledger rows into independent evidence streams in [0, 1].

    Credibility streams are keyed by SOURCE CLASS: two fetches of the same
    registry tell you one thing about a person, and the second one is not
    corroboration. Build-capability streams are keyed by ARTIFACT KIND, because
    a changelog and a pricing page are two different things having been built.
    """
    out: dict[str, list[Item]] = {c: [] for c in COMPONENTS}

    cred: dict[str, list[dict[str, Any]]] = {}
    build: dict[tuple, list[dict[str, Any]]] = {}
    for r in obs:
        cred.setdefault(r.get("source_class") or "unknown", []).append(r)
        build.setdefault(
            (r.get("artifact_type") or "none", r.get("milestone_type") or ""), []
        ).append(r)

    for sc, group in cred.items():
        lo = reliability.get(sc, 0.0)
        y = _sigmoid(lo)
        sources = sorted({g.get("source") or "?" for g in group})
        out["credibility"].append(
            Item(
                key=f"src:{sc}",
                kind="observation",
                component="credibility",
                y=y,
                label=f"{sc} ({', '.join(sources[:2])})",
                basis=(
                    f"source_class '{sc}' at hand-set log-odds {lo:+.1f} -> p={y:.3f}; "
                    f"{len(group)} ledger row(s) collapsed into one independent stream"
                ),
                observed_at=max(g["observed_at"] for g in group),
                n_rows=len(group),
                source_class=sc,
                observation_ids=[g["observation_id"] for g in group],
            )
        )

    for (art, milestone), group in build.items():
        base, why = _build_value(group[0])
        p_class = class_rates.get(art, (0.0, 0))[0]
        p_pop = global_rates.get(art, (0.0, 0))[0]
        adj = RESOURCE_ADJUST_ALPHA * (p_pop - p_class)
        out["build_capability"].append(
            Item(
                key=f"art:{art}" + (f"/{milestone}" if milestone else ""),
                kind="observation",
                component="build_capability",
                y=max(0.0, min(1.0, base + adj)),
                label=f"{art}" + (f" · {milestone}" if milestone else ""),
                basis=(
                    f"{why} base={base:.2f}; resource adjustment {adj:+.3f} "
                    f"(this class ships one at {p_class:.2f}, the population at {p_pop:.2f}); "
                    f"{len(group)} ledger row(s) in this stream"
                ),
                observed_at=max(g["observed_at"] for g in group),
                n_rows=len(group),
                source_class=group[0].get("source_class"),
                artifact_type=art,
                observation_ids=[g["observation_id"] for g in group],
            )
        )

    for cl in claims:
        state = cl.get("state")
        prob = cl.get("posterior_prob")
        if state not in ("verified", "contradicted") or prob is None:
            # 'unverified' carries no information about the person, and
            # 'absent_but_expected' may NEVER move the point. Both are excluded
            # from the mean by construction; absence is handled as widening.
            continue
        out["credibility"].append(
            Item(
                key=f"clm:{cl['claim_id']}",
                kind="claim",
                component="credibility",
                y=float(prob),
                label=f"claim '{cl.get('claim_type')}' {state}",
                basis=f"claim-verification posterior {float(prob):.3f} ({state})",
                observed_at=cl["observed_at"],
                claim_id=cl["claim_id"],
            )
        )

    for comp in COMPONENTS:
        out[comp].sort(key=lambda i: (i.observed_at, i.key))
    return out


# --------------------------------------------------------------------------- #
# the score itself
# --------------------------------------------------------------------------- #

def absences_for(
    pid: str,
    pop: Population,
    *,
    claims: list[dict[str, Any]] | None = None,
) -> list[Absence]:
    """Artifacts this person's resource class predicted that the ledger lacks."""
    profile = pop.people.get(pid)
    if not profile:
        return []
    rates, _ = pop.rates_for(profile)
    held = {
        i.artifact_type
        for i in pop.items.get(pid, {}).get("build_capability", [])
        if i.artifact_type
    }
    out: list[Absence] = []
    for art, (p, n_cell) in sorted(rates.items(), key=lambda kv: -kv[1][0]):
        if art in held or p < ALREADY_PRICED_BELOW:
            continue
        out.append(
            Absence(
                artifact_type=art,
                p=p,
                n_cell=n_cell,
                reason=(
                    f"{p:.0%} of this reference class (n={n_cell}) has a {art} and we "
                    "do not. Not penalised — the interval widens instead."
                    if p >= EXPECT_THRESHOLD
                    else f"only {p:.0%} of this class (n={n_cell}) has a {art}; its "
                    "absence is already priced."
                ),
            )
        )
    for cl in claims or []:
        if cl.get("state") == "absent_but_expected" and cl.get("posterior_prob") is not None:
            out.append(
                Absence(
                    artifact_type=f"claim:{cl.get('claim_type')}",
                    p=float(cl["posterior_prob"]),
                    n_cell=0,
                    reason="claim marked absent-but-expected; widens the interval, never lowers the point.",
                )
            )
    return out


def score_component(
    pid: str,
    component: str,
    pop: Population,
    *,
    items: list[Item] | None = None,
    absences: list[Absence] | None = None,
) -> dict[str, Any]:
    """theta_hat, its interval, and the split between evidence and class.

    ``items`` may be supplied to score a SUBSET — that is the whole mechanism
    behind leave-one-evidence-out attribution in :mod:`worker.scoring.attribution`,
    and it is why that module is an exact recompute rather than a story.
    """
    profile = pop.people.get(pid)
    if profile is None:
        raise KeyError(f"No person '{pid}' visible at asof {pop.asof}.")

    items = pop.items[pid][component] if items is None else items
    fit = pop.fit[component]
    ref = pop.resolve_class(profile, component)
    m_c, sigma2, k = ref["mean"], fit["sigma2"], fit["k"]

    n = len(items)
    ybar = statistics.fmean([i.y for i in items]) if n else None
    theta = ((n * ybar + k * m_c) / (n + k)) if n else m_c
    w = n / (n + k)

    sd = math.sqrt(sigma2 / (n + k))
    half = Z * sd
    absences = absences_for(pid, pop) if absences is None else absences
    mass = sum(a.p for a in absences if a.expected)
    inflate = math.sqrt(1.0 + mass / (n + k))
    half_wide = half * inflate

    point = _clip(100 * theta)
    lo, hi = _clip(100 * (theta - half_wide)), _clip(100 * (theta + half_wide))

    return {
        "person_id": pid,
        "component": component,
        "point": round(point, 1),
        "interval": [round(lo, 1), round(hi, 1)],
        "interval_width": round(hi - lo, 1),
        "n": n,
        "n_rows": sum(i.n_rows for i in items),
        "prior_weight": round(1 - w, 3),
        "evidence_weight": round(w, 3),
        "direct_mean": round(100 * ybar, 1) if ybar is not None else None,
        "class_mean": round(100 * m_c, 1),
        "k": round(k, 2),
        "sigma": round(math.sqrt(sigma2), 4),
        "posterior_sd": round(100 * sd, 2),
        "absence_widen_points": round(100 * (half_wide - half) * 2, 2),
        "absence_mass": round(mass, 3),
        "n_absent_expected": sum(1 for a in absences if a.expected),
        "reference_class": ref,
        "items": items,
        "absences": absences,
        "zero_evidence": n == 0,
    }


def score_person(
    pid: str,
    asof: str,
    *,
    pop: Population | None = None,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Both components for one person at one asof."""
    pop = pop or fit_population(asof, connection=connection)
    return {c: score_component(pid, c, pop) for c in COMPONENTS}


# --------------------------------------------------------------------------- #
# trend — computed by re-scoring, never asserted
# --------------------------------------------------------------------------- #

def _ols_band(xs: Sequence[float], ys: Sequence[float]) -> tuple[float, float, float] | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    intercept = my - slope * mx
    dof = n - 2
    if dof <= 0:
        return None
    resid = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    s2 = sum(r * r for r in resid) / dof
    se = math.sqrt(s2 / sxx)
    t = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776}.get(dof, 2.0)
    return slope, slope - t * se, slope + t * se


def trend_for(
    pid: str,
    component: str,
    asof: str,
    *,
    offsets_days: Sequence[int] = (-90, -60, -30, 0),
    connection: sqlite3.Connection | None = None,
    populations: dict[int, Population] | None = None,
) -> dict[str, Any]:
    """Re-score the SAME ledger at four asofs. Label only when the band excludes zero."""
    base = ledger.parse_iso(ledger.to_iso(asof))
    points: list[tuple[float, float]] = []
    for d in offsets_days:
        stamp = (base + timedelta(days=d)).strftime(ledger.ISO_FMT)
        pop = (populations or {}).get(d) or fit_population(stamp, connection=connection)
        if populations is not None:
            populations[d] = pop
        if pid not in pop.people or not pop.items[pid][component]:
            continue
        points.append((float(d), score_component(pid, component, pop)["point"]))

    base_out = {
        "n_trend_points": len(points),
        "points": [{"offset_days": int(d), "point": p} for d, p in points],
    }
    band = _ols_band([p[0] for p in points], [p[1] for p in points]) if len(points) >= 3 else None
    if band is None:
        return {
            "trend": "insufficient_data",
            "label": f"insufficient dated observations (n={len(points)})",
            **base_out,
        }
    slope, lo, hi = band
    label = "improving" if lo > 0 else "declining" if hi < 0 else "stable"
    return {
        "trend": label,
        "label": label,
        "trend_slope": round(slope, 4),
        "trend_band": [round(lo, 4), round(hi, 4)],
        "band_excludes_zero": lo > 0 or hi < 0,
        **base_out,
    }


# --------------------------------------------------------------------------- #
# render-ready blocks — shaped to what web/public/demo.json already carries
# --------------------------------------------------------------------------- #

_FOUNDER_SCORE_PLAIN = (
    "Two components, both persistent, both append-only. Splitting them is why a "
    "credibility problem does not silently erase a build record."
)
_NEVER_RESETS = (
    "Stored as append-only versions keyed to the person, never to the company. "
    "There is no UPDATE and no DELETE anywhere in the worker, so there is no code "
    "path that could reset it."
)
_LABELS = {
    "credibility": "Credibility — claim-verification posterior",
    "build_capability": "Build Capability — artifact-derived, resource-adjusted",
}

#: Above this prior weight the person is cold-start and the bench renders.
COLD_START_PRIOR_WEIGHT = 0.35


def founder_score_block(
    pid: str,
    asof: str,
    *,
    pop: Population | None = None,
    with_trend: bool = False,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """``people.<id>.founder_score`` — matches the committed contract shape."""
    pop = pop or fit_population(asof, connection=connection)
    scored = {c: score_component(pid, c, pop) for c in COMPONENTS}
    block: dict[str, Any] = {"plain_line": _FOUNDER_SCORE_PLAIN}
    cache: dict[int, Population] = {0: pop}
    for comp, s in scored.items():
        entry: dict[str, Any] = {
            "point": s["point"],
            "interval": s["interval"],
            "n": s["n"],
            "label": _LABELS[comp],
            "prior_weight": q(s["prior_weight"], s["n"]),
        }
        if with_trend:
            t = trend_for(pid, comp, asof, connection=connection, populations=cache)
            entry["trend"] = t["trend"]
            entry["trend_detail"] = t
        block[comp] = entry
    block["never_resets"] = True
    block["never_resets_mechanism"] = _NEVER_RESETS
    cred, build = scored["credibility"]["point"], scored["build_capability"]["point"]
    if abs(cred - build) >= 12:
        block["divergence_note"] = (
            f"Credibility {cred} against build capability {build} is the shape of this "
            "person. Averaging those two numbers would destroy exactly the information "
            "the investor needs, which is the same reason we never average the axes."
        )
    return block


def cold_start_bench_block(
    pid: str,
    asof: str,
    *,
    component: str = "credibility",
    pop: Population | None = None,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    """``people.<id>.cold_start_bench``, or ``None`` when the bench is wrong.

    ``None`` is not an error: for someone with a real record the bench would
    imply a thinness that does not exist. The caller renders
    :func:`cold_start_bench_blocked_reason` in its place.
    """
    pop = pop or fit_population(asof, connection=connection)
    s = score_component(pid, component, pop)
    if s["prior_weight"] < COLD_START_PRIOR_WEIGHT:
        return None

    ref = s["reference_class"]
    absent = [a for a in s["absences"] if a.expected][:4]
    priced = [a for a in s["absences"] if not a.expected][:2]
    k = s["k"]
    n = s["n"]

    if n:
        statement = (
            f"No track record found. Scoring on {n} independent signal"
            f"{'' if n == 1 else 's'} ({s['n_rows']} ledger row"
            f"{'' if s['n_rows'] == 1 else 's'}). Prior weight "
            f"{s['prior_weight'] * 100:.0f}%. Interval "
            f"[{s['interval'][0]:.0f}, {s['interval'][1]:.0f}]. "
            "Here is what would narrow it."
        )
    else:
        statement = (
            "No direct observations at this asof. The number below IS the reference "
            "class, not the person — rendered wide on purpose rather than left blank "
            "or defaulted to zero."
        )

    narrow = [
        (
            f"A {a.artifact_type.replace('_', ' ')} — expected at P={a.p:.2f} for this "
            f"class (n={a.n_cell}) and currently absent, which is part of what is "
            f"widening the interval by {s['absence_widen_points']:.1f} points."
        )
        for a in absent
    ]
    narrow.append(
        "Any third-party observable naming them as operator, with a date: a partner "
        "announcement, a directory listing, an integration page. That source class "
        f"carries {pop.reliability.get('third_party_observable', 1.1):+.1f} log-odds "
        f"against self-report at {pop.reliability.get('self_report', -1.2):+.1f}."
    )
    narrow.append(
        f"A second INDEPENDENT source class. At n={n} the class carries "
        f"{s['prior_weight'] * 100:.0f}% of this number; with k={k:.1f} fitted from the "
        f"population, n={n + 2} would move it to "
        f"{(k / (n + 2 + k)) * 100:.0f}%. More rows from the same source do not count "
        "twice — they are one stream."
    )

    not_narrow = [
        (
            f"A {a.artifact_type.replace('_', ' ')}. Not expected for this profile at "
            f"P={a.p:.2f} (n={a.n_cell}), so its absence is already priced and its "
            "presence would tell us little."
        )
        for a in priced
    ]
    not_narrow.append(
        "A larger follower count, a school, or a prior employer. The reference class "
        "carries no pedigree field: we do not collect them and would not weight them "
        "if we did."
    )

    return {
        "statement": statement,
        "scored_at": ledger.now_iso(),
        "asof": pop.asof,
        "component": component,
        "prior_weight": q(s["prior_weight"], n),
        "prior_weight_formula": (
            f"w = k/(n+k) with k={k:.1f} — fitted as sigma^2/tau^2 over "
            f"{pop.fit[component]['n_groups']} collected people, not chosen — and n={n} "
            f"independent signal{'' if n == 1 else 's'} -> {k:.1f}/({n}+{k:.1f}) = "
            f"{s['prior_weight']:.3f}. {s['prior_weight'] * 100:.0f} percent of this "
            "number is the reference class, not the person."
        ),
        "n_direct": q(n, n),
        "n_ledger_rows": q(s["n_rows"], n),
        "point": q(s["point"], n),
        "interval": s["interval"],
        "interval_note": (
            f"Width {s['interval_width']:.1f} points, of which "
            f"{s['absence_widen_points']:.1f} comes from {s['n_absent_expected']} "
            "expected-but-absent artifact(s). Absence widened this interval; it did not "
            "lower the point estimate by a single point."
        ),
        "reference_class": {
            "dimensions": ", ".join(ref["dimensions_used"]) or "population margin only",
            **{d: ref["values"].get(d) for d in REFERENCE_CLASS_DIMENSIONS},
            "dimensions_dropped": ref["dimensions_dropped"],
            "n_cell": ref["n_cell"],
            "n_population": ref["n_population"],
            "thin_cell": ref["thin_cell"],
            "shrunk_to_margin": ref["shrunk_to_margin"],
            "cell_mean_raw": ref["cell_mean_raw"],
            "cell_mean_shrunk": ref["cell_mean_shrunk"],
            "contains_no_pedigree_field": True,
            "excluded_fields": ref["excluded_fields"],
            "note": (
                f"Fitted over {ref['n_population']} collected people; this cell holds "
                f"{ref['n_cell']}. Below n={MIN_CELL} we drop dimensions rather than let "
                "a marginal rate wear a conditional's clothes, and we name the ones we "
                "dropped."
            ),
        },
        "what_would_narrow_it": narrow,
        "what_would_not_narrow_it": not_narrow,
        "absences": [a.to_dict() for a in s["absences"][:8]],
    }


def cold_start_bench_blocked_reason(
    pid: str,
    asof: str,
    *,
    component: str = "credibility",
    pop: Population | None = None,
    connection: sqlite3.Connection | None = None,
) -> str | None:
    """The sentence that renders where the bench would have been."""
    pop = pop or fit_population(asof, connection=connection)
    s = score_component(pid, component, pop)
    if s["prior_weight"] >= COLD_START_PRIOR_WEIGHT:
        return None
    return (
        f"Not a cold-start founder. {s['n']} independent signals across {s['n_rows']} "
        f"ledger rows, so the prior weight is {s['k']:.1f}/({s['n']}+{s['k']:.1f}) = "
        f"{s['prior_weight'] * 100:.0f}% and the reference class is doing very little of "
        "the work. The bench is the wrong instrument here and rendering it would imply a "
        "thinness that does not exist."
    )


def founder_score_history_block(
    pid: str,
    asof: str,
    *,
    component: str = "credibility",
    connection: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    """``people.<id>.founder_score_history`` — the append-only step function.

    Single-component by construction: mixing credibility and build capability
    into one series draws a zig-zag, not a step function.
    """
    c = connection or store.conn()
    rows = ledger.read_founder_score_history(pid, asof, component=component, connection=c)
    out = []
    for r in rows:
        org_name = None
        if r.get("org_id"):
            found = c.execute(
                "SELECT org_name FROM org WHERE org_id = ?", (r["org_id"],)
            ).fetchone()
            org_name = found["org_name"] if found else None
        out.append(
            {
                "version": r["version_number"],
                "component": r["component"],
                "observed_at": r["observed_at"],
                "point": r["point"],
                "interval": [r["interval_low"], r["interval_high"]],
                "n": r["n"],
                "prior_weight": q(r["prior_weight"], r["n"] or 0),
                "org_name": org_name,
                "org_id": r.get("org_id"),
                "reason": r.get("reason"),
            }
        )
    return out


def person_blocks(
    pid: str,
    asof: str,
    *,
    pop: Population | None = None,
    with_trend: bool = False,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Everything this module owns for one person, keyed as demo.json keys it."""
    pop = pop or fit_population(asof, connection=connection)
    bench = cold_start_bench_block(pid, asof, pop=pop)
    out: dict[str, Any] = {
        "founder_score": founder_score_block(
            pid, asof, pop=pop, with_trend=with_trend, connection=connection
        ),
        "cold_start_bench": bench,
        "founder_score_history": founder_score_history_block(
            pid, asof, connection=connection
        ),
    }
    if bench is None:
        out["cold_start_bench_blocked_reason"] = cold_start_bench_blocked_reason(
            pid, asof, pop=pop
        )
    return out


# --------------------------------------------------------------------------- #
# writer — append-only, never in place
# --------------------------------------------------------------------------- #

def append_versions(
    pid: str,
    asof: str,
    *,
    reason: str,
    org_id: str | None = None,
    opportunity_id: str | None = None,
    milestone_type: str | None = None,
    observed_at: str | None = None,
    pop: Population | None = None,
    connection: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    """Append one new version per component. Nothing is ever overwritten."""
    c = connection or store.conn()
    pop = pop or fit_population(asof, connection=c)
    written = []
    for comp in COMPONENTS:
        s = score_component(pid, comp, pop)
        ref = s["reference_class"]
        written.append(
            ledger.append_founder_score_version(
                person_id=pid,
                component=comp,
                point=s["point"],
                interval_low=s["interval"][0],
                interval_high=s["interval"][1],
                n=s["n"],
                prior_weight=s["prior_weight"],
                reference_class=json.dumps(
                    {
                        "dimensions_used": ref["dimensions_used"],
                        "values": ref["values"],
                        "n_cell": ref["n_cell"],
                        "n_population": ref["n_population"],
                        "thin_cell": ref["thin_cell"],
                        "contains_no_pedigree_field": True,
                    },
                    ensure_ascii=False,
                ),
                org_id=org_id,
                opportunity_id=opportunity_id,
                reason=reason,
                milestone_type=milestone_type,
                asof=pop.asof,
                observed_at=observed_at or ledger.now_iso(),
                connection=c,
            )
        )
    ledger.commit()
    return written


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _print_fit(pop: Population) -> None:
    print("=" * 78)
    print("POPULATION FIT — everything below is counted at this asof, not chosen")
    print("=" * 78)
    print(f"  asof                 : {pop.asof}")
    print(f"  people visible       : {pop.n_people}")
    print(f"  observations visible : {pop.n_observations}")
    print(f"  reliability table    : {pop.reliability_source}")
    print()
    print("  Source-class reliability (hand-set, published, defended line by line):")
    for sc, lo in sorted(pop.reliability.items(), key=lambda kv: kv[1]):
        print(f"    {sc:<24} {lo:+.1f}   ->  p={_sigmoid(lo):.3f}")
    print()
    print("  Shrinkage constants, method of moments over the collected population:")
    for comp in COMPONENTS:
        f = pop.fit[comp]
        print(
            f"    {comp:<18} k={f['k']:.2f}  sigma={math.sqrt(f['sigma2']):.4f}  "
            f"tau={math.sqrt(f['tau2']):.4f}  class_mean={100 * f['grand_mean']:.1f}  "
            f"(n_people={f['n_groups']}, n_streams={f['n_values']})"
        )
        for note in f.get("notes", []):
            print(f"        note: {note}")
        if f.get("k_at_bound"):
            print(f"        note: raw k={f['raw_k']:.2f} hit the clamp {K_BOUNDS}")
        cf = pop.cell_fit[comp]
        print(f"        cell shrinkage k_cell={cf['k']:.2f} over {cf['n_groups']} full-depth cells")
    print()
    print(f"  Reference class      : {{{', '.join(REFERENCE_CLASS_DIMENSIONS)}}}")
    print(f"  Excluded by design   : {{{', '.join(PEDIGREE_FIELDS_EXCLUDED)}}}")
    print()
    print("  Largest full-depth class cells (credibility), with counts:")
    full = len(CLASS_LEVELS[0])
    cells = sorted(
        ((k, v) for k, v in pop.class_means["credibility"].items() if len(k) == full),
        key=lambda kv: -kv[1][1],
    )[:6]
    for key, (mean, n_cell) in cells:
        flag = "   THIN — dimensions dropped at scoring time" if n_cell < MIN_CELL else ""
        print(f"    n={n_cell:<4} mean={mean * 100:5.1f}  {'/'.join(str(v) for _, v in key)}{flag}")
    print()
    print("  Findability priors, largest resource-class cell (no pedigree, no artifact key):")
    key, rates = max(
        pop.artifact_rates.items(),
        key=lambda kv: (max((c for _, c in kv[1].values()), default=0), -len(kv[0])),
    )
    label = "/".join(str(v) for _, v in key) or "population margin"
    for art, (p, n_cell) in sorted(rates.items(), key=lambda kv: -kv[1][0])[:8]:
        mark = "expected" if p >= EXPECT_THRESHOLD else "already priced"
        print(f"    P({art:<26}| {label}) = {p:.3f}  (n={n_cell})  {mark}")
    print()


def _print_person(pid: str, pop: Population, *, heading: str) -> None:
    profile = pop.people[pid]
    print("-" * 78)
    print(f"{heading}: {pid}  ({profile.get('display_name')})")
    print("-" * 78)
    print(
        f"  class values: sector={profile.get('sector')} "
        f"solo_or_team={profile.get('solo_or_team')} tier={profile.get('resource_tier')} "
        f"region={profile.get('region')} primary_artifact={profile.get('primary_artifact_type')}"
    )
    for comp in COMPONENTS:
        s = score_component(pid, comp, pop)
        ref = s["reference_class"]
        print(
            f"  {comp:<18} point={s['point']:5.1f} (n={s['n']})   "
            f"interval=[{s['interval'][0]:.1f}, {s['interval'][1]:.1f}] "
            f"width={s['interval_width']:.1f} (n={s['n']})"
        )
        print(
            f"      prior_weight={s['prior_weight']:.3f} (n={s['n']})  ->  "
            f"{s['prior_weight'] * 100:.0f}% of this number is the reference class, not them"
        )
        print(
            f"      direct_mean={s['direct_mean']} over {s['n']} stream(s) / "
            f"{s['n_rows']} row(s);  class_mean={s['class_mean']} "
            f"(n_cell={ref['n_cell']}, thin={ref['thin_cell']}, "
            f"dropped={ref['dimensions_dropped'] or 'none'})"
        )
        print(
            f"      absence: {s['n_absent_expected']} expected-but-absent artifact(s), "
            f"mass={s['absence_mass']:.2f} -> widened the interval by "
            f"{s['absence_widen_points']:.1f} points, lowered the point by 0.0"
        )
        for i in s["items"][:4]:
            print(f"        · {i.label:<38} y={i.y:.3f}  rows={i.n_rows}")
        if len(s["items"]) > 4:
            print(f"        · ... {len(s['items']) - 4} more stream(s)")
    bench = cold_start_bench_block(pid, pop.asof, pop=pop)
    if bench:
        print(f"  BENCH: {bench['statement']}")
        print(f"    formula: {bench['prior_weight_formula']}")
        for line in bench["what_would_narrow_it"][:2]:
            print(f"    narrow:  {line}")
        print(f"    not:     {bench['what_would_not_narrow_it'][-1]}")
    else:
        print(f"  BENCH BLOCKED: {cold_start_bench_blocked_reason(pid, pop.asof, pop=pop)}")
    hist = founder_score_history_block(pid, pop.asof)
    if hist:
        print(f"  HISTORY (credibility, append-only, {len(hist)} versions):")
        for h in hist:
            print(
                f"    v{h['version']}  {h['observed_at']}  point={h['point']:5.1f}  "
                f"interval=[{h['interval'][0]}, {h['interval'][1]}]  n={h['n']}  "
                f"{h['org_name'] or 'no org'}"
            )
    else:
        print("  HISTORY: no appended versions for this person at this asof.")
    print()


def pick_demo_people(pop: Population) -> dict[str, str]:
    """A cold-start person and an evidence-rich one, chosen from the real data."""
    ranked = sorted(pop.people, key=lambda pid: len(pop.items[pid]["credibility"]))
    out: dict[str, str] = {}
    with_any = [pid for pid in ranked if pop.items[pid]["credibility"]]
    zero = [pid for pid in ranked if not pop.items[pid]["credibility"]]
    if with_any:
        out["cold start"] = with_any[0]
    if zero:
        out["zero evidence"] = zero[0]
    if ranked:
        out["evidence rich"] = ranked[-1]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Empirical-Bayes Founder Score (B1).")
    ap.add_argument("--asof", default=None, help="ISO-8601 UTC; defaults to now")
    ap.add_argument("--person", action="append", default=[], help="person_id (repeatable)")
    ap.add_argument("--json", action="store_true", help="dump render-ready blocks as JSON")
    ap.add_argument("--trend", action="store_true", help="re-score at asof-90/-60/-30/0")
    ap.add_argument("--write", default=None, help="append versions for this person_id")
    ap.add_argument("--reason", default="Re-scored from the ledger.", help="reason for --write")
    args = ap.parse_args(argv)

    store.open_ledger()  # NEVER reset=True — four agents share this database
    asof = ledger.to_iso(args.asof) if args.asof else ledger.now_iso()
    pop = fit_population(asof)

    if args.write:
        written = append_versions(args.write, asof, reason=args.reason, pop=pop)
        print(f"appended {len(written)} founder_score_version rows for {args.write}:")
        for w in written:
            print(f"  {w}")
        return 0

    if args.person:
        people = list(dict.fromkeys(args.person))
        headings = {p: "PERSON" for p in people}
    else:
        picked = pick_demo_people(pop)
        for hero in ("per_mo", "per_dr"):
            if hero in pop.people and hero not in picked.values():
                picked[f"hero {hero}"] = hero
        headings = {v: k.upper() for k, v in picked.items()}
        people = list(dict.fromkeys(picked.values()))

    if args.json:
        print(json.dumps(
            {
                pid: person_blocks(pid, asof, pop=pop, with_trend=args.trend)
                for pid in people if pid in pop.people
            },
            indent=2,
            ensure_ascii=False,
        ))
        return 0

    _print_fit(pop)
    for pid in people:
        if pid not in pop.people:
            print(f"  (no person '{pid}' visible at {asof})")
            continue
        _print_person(pid, pop, heading=headings.get(pid, "PERSON"))
        if args.trend:
            cache: dict[int, Population] = {0: pop}
            for comp in COMPONENTS:
                t = trend_for(pid, comp, asof, populations=cache)
                print(
                    f"  TREND {comp:<18} {t['trend']:<18} "
                    f"n_trend_points={t['n_trend_points']} "
                    f"slope={t.get('trend_slope')} band={t.get('trend_band')}"
                )
            print()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
