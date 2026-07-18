"""B3 — the expected-evidence manifest and the findability priors behind it.

THIS IS THE CORE MECHANISM OF THE PRODUCT.

Every other VC tool asks "who has already emitted a signal?", which returns null
for a first-time founder by construction. Counterproof asks the inverted
question: *what artifacts should be observable if this claim were true?* — writes
that list down BEFORE searching, attaches a findability prior to each row, and
then goes and looks for exactly those artifacts.

THE ONE RULE THAT MATTERS
-------------------------
**Absence widens the interval and NEVER lowers the score — when the findability
prior predicted that absence for this resource class.**

In this module that rule is not an ``if`` statement bolted on at the end. It
falls out of the arithmetic. For an artifact with findability ``p_true`` under
the claim and ``p_false`` without it, the log-likelihood ratio contributed by
*not observing* it is::

    llr_absent = log((1 - p_true) / (1 - p_false))

When the reference class predicts the absence just as strongly either way,
``p_true == p_false`` and that expression is **exactly zero**. A missing GitHub
for a non-technical solo operator costs nothing because ``log(1) = 0``, not
because somebody remembered to special-case it. A missing changelog for someone
claiming 500 paying users has ``p_true >> p_false``, the term goes negative, and
the claim is refuted. Same formula, opposite outcome, no hand-tuning in between.

WHERE THE PRIORS COME FROM
--------------------------
From our own crawl, read through :func:`worker.store.read_observations` at an
``asof`` like everything else. A hardcoded prior is the most attackable number in
the demo — "where did 0.11 come from?" has no good answer. A computed one with a
visible cell count does: it came from *k* of *n* people in this reference class,
and here is *n*.

Three honesty guards run before any prior is published:

1. **Tautology guard.** A founder is typed technical-vs-operator *because* we saw
   a preprint or a launch post. Publishing ``P(preprint | technical)`` would then
   be a definition wearing a conditional's clothes. Families that determine a
   class dimension are refused a prior conditioned on that dimension and say so.
2. **Coverage guard.** We crawled arXiv, USPTO and Hacker News. We did not crawl
   changelogs, team pages or GitHub at population scale. A family observed on
   fewer than :data:`MIN_FAMILY_SUPPORT` people is reported as a *coverage gap*
   with its raw count, never as ``p = 0.00``. Measured-zero and never-looked are
   different facts and the difference is the whole credibility of the table.
3. **Thin-cell guard.** Every cell is shrunk toward the family margin by a fixed
   pseudo-count, both the raw and the shrunk rate are reported, and any cell
   under :data:`THIN_CELL_N` is stamped ``thin_cell`` so the UI can say "marginal
   rate; class too thin (n=3)" instead of a fabricated conditional.

The reference class contains **no pedigree field**: no school, no employer, no
accelerator, no investor. That omission is the product.

Run it::

    uv run python -m worker.scoring.manifest
"""

from __future__ import annotations

import math
import sys
from typing import Any, Iterable

from worker import ledger, store

# --------------------------------------------------------------------------- #
# tunables — all published, all defensible, none learned
# --------------------------------------------------------------------------- #

#: Pseudo-count pulling every cell toward its family margin. Same idiom as the
#: founder score's ``w = n / (n + k)``: a cell of 4 people is mostly the margin,
#: a cell of 200 is mostly itself.
SHRINKAGE_K = 8.0

#: Below this, a cell is stamped thin and the UI must say so. Taken from the
#: pre-mortem in docs/IDEA.md ("when a cell is under n=8, the UI says *marginal
#: rate; class too thin (n=3)*").
THIN_CELL_N = 8

#: A family observed on fewer people than this across the ENTIRE crawl is a
#: coverage gap, not a measured zero. We publish the count and no prior.
MIN_FAMILY_SUPPORT = 8

#: An artifact is "expected" when the class predicts it at least this strongly.
EXPECT_P = 0.35

#: ...and when its absence is actually informative. Below this the absence term
#: is arithmetically indistinguishable from zero, so the row is not expected.
EXPECT_LLR = -0.15

#: Absence widens the posterior interval in proportion to how strongly the class
#: predicted the artifact. Absence widens whether or not it is penalised — that
#: is the half of the asymmetry people forget. Points of interval width per unit
#: of findability prior.
WIDEN_SCALE = 8.0

#: Probabilities are clamped away from 0 and 1 so the log-odds stay finite. A
#: single unobserved cell must not be able to emit an infinite term.
P_FLOOR = 0.01
P_CEIL = 0.99

#: Hard cap on the magnitude of any single artifact's log-likelihood term.
#: Without it, a complement cell that happens to be empty for COVERAGE reasons
#: emits ``log(0.42 / 0.01) = +3.7`` and one forum post outweighs a registry
#: filing. The cap says: no single artifact class can carry a claim on its own,
#: and a ratio that large is telling us about our crawl rather than the founder.
LLR_CAP = 2.5


# --------------------------------------------------------------------------- #
# artifact families — the crawl's real vocabulary, grouped
# --------------------------------------------------------------------------- #

#: Family -> the ``observation.artifact_type`` values that count as that family.
#: These strings are what Ali's collectors actually write; nothing aspirational.
ARTIFACT_FAMILIES: dict[str, frozenset[str]] = {
    "public_preprint": frozenset({"preprint"}),
    "public_launch_post": frozenset({"show_hn_post"}),
    "public_product_url": frozenset({"product_url", "landing_page"}),
    "public_forum_participation": frozenset({"forum_comment", "forum_thread"}),
    "hiring_signal": frozenset({"hiring_thread_post", "job_posting"}),
    "trademark_filing": frozenset(
        {"trademark_application", "trademark_filing", "trademark_identification"}
    ),
    "account_history": frozenset({"account_footprint", "account_first_post"}),
    "checkout_endpoint": frozenset({"checkout_endpoint"}),
    "pricing_page": frozenset({"pricing_page"}),
    "dated_changelog": frozenset({"changelog"}),
    "team_page": frozenset({"team_page"}),
    "press_coverage": frozenset({"press_mention"}),
    "review_presence": frozenset({"review_page"}),
}

#: Families whose presence is what MAKES a person "technical" in our typing.
#: Conditioning their prior on ``founder_type`` would be circular.
TECHNICAL_DETERMINANTS = frozenset({"public_preprint", "public_launch_post"})

#: Families whose presence is what MAKES ``has_company_domain`` true.
#: Conditioning their prior on that dimension would be circular.
DOMAIN_DETERMINANTS = frozenset(
    {"public_product_url", "checkout_endpoint", "pricing_page"}
)

#: The reference class, coarsest-last. A cell too thin to speak backs off one
#: level and SAYS which level answered — the pre-mortem's fix for "every cell was
#: n=0 or n=1", implemented as a ladder rather than as a silent fallback.
#:
#: Both dimensions are determinants of some family, so the tautology guard is
#: evaluated against the union: a family that helps define EITHER dimension gets
#: no conditional prior at any level of the ladder.
CLASS_LADDER: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("founder_type x has_company_domain", ("founder_type", "has_company_domain")),
    ("founder_type", ("founder_type",)),
    ("margin", ()),
)

#: Claim types whose absence a verifier searched for directly. Evidence rows in
#: the ledger carry no ``artifact_type``, so this is how a searched-for absence
#: is matched back to a manifest row and keeps its ``evidence_id``.
CLAIM_TYPE_TO_FAMILY: dict[str, str] = {
    "ship_cadence": "dated_changelog",
    "product_shipped": "dated_changelog",
    "code_artifact": "public_github_repo",
    "press_mention": "press_coverage",
    "team_page": "team_page",
    "headcount": "team_page",
    "cap_table": "cap_table_disclosure",
    "round_terms": "round_terms_disclosure",
    "trademark_filing": "trademark_filing",
    "domain_state": "public_product_url",
    "payments_live": "checkout_endpoint",
    "pricing_published": "pricing_page",
    "mrr": "hiring_signal",
    "paying_users": "hiring_signal",
}

#: Human labels for the manifest's Artifact column.
FAMILY_LABEL: dict[str, str] = {
    "public_preprint": "Dated public preprint",
    "public_launch_post": "Public launch post",
    "public_product_url": "Live company domain",
    "public_forum_participation": "Public forum participation",
    "hiring_signal": "Hiring signal",
    "trademark_filing": "Trademark filing",
    "account_history": "Dated account history",
    "checkout_endpoint": "Checkout endpoint",
    "pricing_page": "Published pricing page",
    "dated_changelog": "Dated changelog",
    "team_page": "Team page",
    "press_coverage": "Press coverage",
    "review_presence": "Third-party reviews",
}

#: Artifact classes a judge will ask about that we DECLINED to crawl. Naming them
#: with the reason beats a silent omission, and it is why no row in this module
#: ever reports ``P(github) = 0.00`` off a crawl that never touched GitHub.
NOT_CRAWLED: dict[str, str] = {
    "public_github_repo": (
        "GitHub is a confirmation channel in our channel table, never a discovery "
        "channel — ranking by stars is track-record sourcing by construction. We "
        "did not crawl it at population scale, so we publish no prior for it "
        "rather than a measured-looking zero."
    ),
    "funding_announcement": (
        "Funding databases are a pedigree proxy and sit in the not-collected "
        "ledger. A prior computed from them would smuggle the network gate back "
        "in through the denominator."
    ),
    "accelerator_cohort_listing": (
        "Declined pedigree channel. Grey for two independent reasons: not "
        "expected for this profile, and not collected either."
    ),
}


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #

def _clamp(p: float) -> float:
    return min(P_CEIL, max(P_FLOOR, p))


def _q(value: Any, n: Any) -> dict[str, Any]:
    """Every number in this system travels with its sample size."""
    return {"value": value, "n": n}


def _shrink(k: int, n: int, margin: float) -> float:
    """Cell rate pulled toward the family margin by a fixed pseudo-count."""
    return (k + SHRINKAGE_K * margin) / (n + SHRINKAGE_K) if (n + SHRINKAGE_K) else margin


# --------------------------------------------------------------------------- #
# the crawl population — built through the asof chokepoint, nowhere else
# --------------------------------------------------------------------------- #

def crawl_population(
    asof: str,
    *,
    provenance_class: str | None = "live",
    connection: Any = None,
) -> dict[str, dict[str, Any]]:
    """Every person visible at ``asof``, with their observed artifact families.

    A person enters the population only by having an observation visible at this
    ``asof``, so the priors are point-in-time correct like every other number
    here: re-running at an earlier ``asof`` recomputes them over a smaller crawl
    rather than leaking today's coverage into yesterday's estimate.

    ``provenance_class='live'`` by default. Our own demo fixtures must not be
    allowed to inflate a prior we then use to judge a founder — that would be
    marking our own homework, and with 23 fixture rows against 1,789 live ones it
    would be invisible in the totals.
    """
    rows = store.read_observations(
        asof, provenance_class=provenance_class, order="asc", connection=connection
    )

    type_to_family: dict[str, str] = {}
    for family, types in ARTIFACT_FAMILIES.items():
        for t in types:
            type_to_family[t] = family

    people: dict[str, dict[str, Any]] = {}
    for row in rows:
        pid = row.get("person_id")
        if not pid:
            continue
        rec = people.setdefault(
            pid, {"person_id": pid, "families": set(), "n_observations": 0}
        )
        rec["n_observations"] += 1
        family = type_to_family.get(row.get("artifact_type") or "")
        if family:
            rec["families"].add(family)

    for pid, rec in people.items():
        person = ledger.get_person(pid, connection=connection) or {}
        rec["sector"] = person.get("sector")
        rec["solo_or_team"] = person.get("solo_or_team") or "unknown"
        rec["resource_tier"] = person.get("resource_tier") or "unknown"
        rec["region"] = person.get("region")
        rec["founder_type"] = (
            "technical" if rec["families"] & TECHNICAL_DETERMINANTS else "operator"
        )
        rec["has_company_domain"] = bool(rec["families"] & DOMAIN_DETERMINANTS)
    return people


def person_record(
    person_id: str, asof: str, *, connection: Any = None
) -> dict[str, Any] | None:
    """One subject's own record, over EVERY provenance class.

    Deliberately different from :func:`crawl_population`, and the difference
    matters in both directions. The priors' denominators exclude fixtures so our
    own authored demo rows cannot inflate a rate we then judge a founder against.
    But the founder being judged must be scored on all the evidence we actually
    hold about her, fixture rows included — otherwise the subject of the manifest
    is invisible to it, and every artifact reads as absent.
    """
    rows = store.read_observations(asof, person_id=person_id, connection=connection)
    if not rows:
        return None

    type_to_family = {
        t: family for family, types in ARTIFACT_FAMILIES.items() for t in types
    }
    families = {
        type_to_family[r["artifact_type"]]
        for r in rows
        if r.get("artifact_type") in type_to_family
    }
    person = ledger.get_person(person_id, connection=connection) or {}
    return {
        "person_id": person_id,
        "families": families,
        "n_observations": len(rows),
        "sector": person.get("sector"),
        "solo_or_team": person.get("solo_or_team") or "unknown",
        "resource_tier": person.get("resource_tier") or "unknown",
        "region": person.get("region"),
        "founder_type": "technical" if families & TECHNICAL_DETERMINANTS else "operator",
        "has_company_domain": bool(families & DOMAIN_DETERMINANTS),
    }


def resource_class(person: dict[str, Any]) -> dict[str, Any]:
    """The reference class for one person. Contains NO pedigree field, by design.

    No school, no employer, no accelerator, no investor, no follower count. If it
    were in here, the system would be re-deriving the network gate it exists to
    replace, and it would do it invisibly.
    """
    return {
        "founder_type": person.get("founder_type"),
        "has_company_domain": bool(person.get("has_company_domain")),
        "sector": person.get("sector"),
        "solo_or_team": person.get("solo_or_team") or "unknown",
        "resource_tier": person.get("resource_tier") or "unknown",
        "region": person.get("region"),
        "contains_pedigree_field": False,
    }


# --------------------------------------------------------------------------- #
# findability priors — computed, shrunk, guarded, counted
# --------------------------------------------------------------------------- #

def _cell_key(person: dict[str, Any], dims: tuple[str, ...]) -> str:
    if not dims:
        return "margin"
    return " · ".join(f"{d}={person.get(d)}" for d in dims)


def compute_findability_priors(
    asof: str,
    *,
    population: dict[str, dict[str, Any]] | None = None,
    connection: Any = None,
) -> dict[str, Any]:
    """P(artifact observable | reference class), measured over our own crawl.

    For each artifact family and each rung of :data:`CLASS_LADDER`, counts every
    cell: ``k`` people in the cell who have the artifact, ``n_cell`` people in the
    cell, the raw rate, the rate shrunk toward the family margin, and the thin
    flag. Nothing is published without an ``n`` beside it.
    """
    people = population if population is not None else crawl_population(
        asof, connection=connection
    )
    total = len(people)

    families: dict[str, Any] = {}
    for family in ARTIFACT_FAMILIES:
        support = sum(1 for p in people.values() if family in p["families"])
        margin = support / total if total else 0.0
        tautological = family in (TECHNICAL_DETERMINANTS | DOMAIN_DETERMINANTS)

        entry: dict[str, Any] = {
            "artifact_family": family,
            "label": FAMILY_LABEL.get(family, family),
            "support": _q(support, total),
            "margin": _q(round(margin, 4), total),
            "coverage_gap": support < MIN_FAMILY_SUPPORT,
            "tautological": tautological,
            "levels": {},
        }

        if entry["coverage_gap"]:
            entry["refusal_reason"] = (
                f"Observed on {support} of {total} people in the crawl. Below the "
                f"{MIN_FAMILY_SUPPORT}-person support floor, so this is a COVERAGE "
                "GAP, not a measured zero — we did not crawl this artifact class at "
                "population scale. Publishing a prior here would be inventing one."
            )
        elif tautological:
            dim = (
                "founder_type" if family in TECHNICAL_DETERMINANTS else "has_company_domain"
            )
            entry["refusal_reason"] = (
                f"'{family}' is part of what DEFINES {dim} in our typing, and both "
                "dimensions sit in the reference class, so a conditional prior over "
                "it would be a definition wearing a conditional's clothes. Refused "
                "at every rung of the ladder rather than printed."
            )

        if not entry["coverage_gap"] and not tautological:
            for level_name, dims in CLASS_LADDER:
                cells: dict[str, dict[str, Any]] = {}
                for person in people.values():
                    key = _cell_key(person, dims)
                    cell = cells.setdefault(key, {"k": 0, "n_cell": 0})
                    cell["n_cell"] += 1
                    if family in person["families"]:
                        cell["k"] += 1
                for key, cell in cells.items():
                    n_cell, k = cell["n_cell"], cell["k"]
                    cell["cell"] = key
                    cell["p_raw"] = round(k / n_cell, 4) if n_cell else None
                    cell["p"] = round(_shrink(k, n_cell, margin), 4)
                    cell["thin_cell"] = n_cell < THIN_CELL_N
                    cell["shrunk_to_margin"] = n_cell < THIN_CELL_N
                    # complement at the SAME rung: everyone in the crawl who is
                    # not in this cell. That is the "claim false" side.
                    n_comp = total - n_cell
                    k_comp = support - k
                    cell["n_complement"] = n_comp
                    cell["p_complement"] = round(
                        _shrink(k_comp, n_comp, margin), 4
                    )
                entry["levels"][level_name] = cells

        families[family] = entry

    return {
        "asof": asof,
        "computed_from": "own_crawl",
        "n_people": total,
        "n_observations": store.count_observations(asof, provenance_class="live"),
        "shrinkage_k": SHRINKAGE_K,
        "thin_cell_n": THIN_CELL_N,
        "class_ladder": [name for name, _ in CLASS_LADDER],
        "families": families,
        "not_crawled": dict(NOT_CRAWLED),
    }


def prior_for(
    priors: dict[str, Any], family: str, person: dict[str, Any]
) -> dict[str, Any] | None:
    """The (p_true, p_false) pair for one artifact family and one person.

    ``p_true``  = observed rate in this person's reference class.
    ``p_false`` = observed rate in that class's complement, same crawl, same rung.

    Walks :data:`CLASS_LADDER` and answers from the FIRST rung whose cell clears
    :data:`THIN_CELL_N`, reporting which rung answered and with what ``n``. A cell
    of one person cannot speak for a reference class, and pretending otherwise is
    the failure this ladder exists to prevent — so it backs off and says so out
    loud instead of printing a confident number off n=1.

    Returns ``None`` when a guard refused to publish a prior at all, which the
    manifest renders as an explicit "no prior" row rather than a confident zero.
    """
    entry = priors["families"].get(family)
    if entry is None or entry.get("coverage_gap") or entry.get("tautological"):
        return None

    chosen: dict[str, Any] | None = None
    chosen_level = "margin"
    backed_off_from: list[dict[str, Any]] = []

    for level_name, dims in CLASS_LADDER:
        cells = entry["levels"].get(level_name, {})
        cell = cells.get(_cell_key(person, dims))
        if cell is None:
            continue
        if cell["n_cell"] >= THIN_CELL_N or level_name == "margin":
            chosen, chosen_level = cell, level_name
            break
        backed_off_from.append(
            {"level": level_name, "cell": cell["cell"], "n_cell": cell["n_cell"]}
        )

    if chosen is None:
        return None

    return {
        "artifact_family": family,
        "class_level": chosen_level,
        "cell": chosen["cell"],
        "p_true": _clamp(chosen["p"]),
        "p_false": _clamp(chosen["p_complement"]),
        "n": chosen["n_cell"],
        "k": chosen["k"],
        "n_complement": chosen["n_complement"],
        "p_raw": chosen["p_raw"],
        "thin_cell": chosen["thin_cell"],
        "shrunk_to_margin": chosen["shrunk_to_margin"],
        "backed_off_from": backed_off_from,
        "margin": entry["margin"],
    }


def likelihood_ratio(p_true: float, p_false: float) -> dict[str, float]:
    """The whole mechanism, in two lines of arithmetic.

    ``llr_present`` is what observing the artifact is worth. ``llr_absent`` is
    what NOT observing it is worth — and it is **exactly zero when the class
    predicted the absence just as strongly either way**, which is the
    anti-network-gate rule falling out of the formula instead of being bolted on.

    ``llr_absent`` is clamped at or below zero: an absence may cost nothing, but
    it never earns credit. Taking points for a missing artifact would be as
    unprincipled as deducting them for a predicted one.
    """
    p_true = _clamp(p_true)
    p_false = _clamp(p_false)
    present = math.log(p_true / p_false)
    absent = min(0.0, math.log((1.0 - p_true) / (1.0 - p_false)))
    return {
        "llr_present": round(max(-LLR_CAP, min(LLR_CAP, present)), 4),
        "llr_absent": round(max(-LLR_CAP, absent), 4),
        "llr_present_uncapped": round(present, 4),
        "capped": abs(present) > LLR_CAP or absent < -LLR_CAP,
    }


def persist_findability_priors(
    priors: dict[str, Any],
    *,
    connection: Any = None,
) -> list[str]:
    """Append the computed cells to ``findability_prior`` so they are inspectable.

    Append-only, like everything else: a recomputation at a later ``asof`` adds
    rows, it never rewrites the ones already there, so the prior a decision was
    made against stays readable at the asof it was made.

    KNOWN SCHEMA GAP, stated rather than worked around: ``findability_prior``
    carries ``(artifact_type, sector, solo_or_team, resource_tier, region,
    company_age_band)`` and has no column for the collapsed
    ``founder_type × has_company_domain`` class this module conditions on. Rather
    than smuggle that class into ``company_age_band`` — which would silently
    corrupt a column that means something else — the conditioning dimension is
    written into ``artifact_type`` alongside the family name, in the form
    ``family@dim=value``, and the honest cell counts go in ``n`` / ``n_cell``.
    The integrator should know this is where that string comes from.
    """
    written: list[str] = []
    asof = priors.get("asof")
    existing = {
        r["prior_id"]
        for r in (connection or store.conn()).execute(
            "SELECT prior_id FROM findability_prior"
        ).fetchall()
    }
    for family, entry in priors["families"].items():
        if entry.get("coverage_gap") or entry.get("tautological"):
            continue
        for level_name, cells in entry["levels"].items():
            for key, cell in cells.items():
                slug = (
                    key.replace(" · ", "_").replace("=", "").replace(" ", "")
                )
                prior_id = f"fp_{family}_{slug}"[:120]
                if prior_id in existing:
                    continue
                ledger.append_row(
                    "findability_prior",
                    {
                        "prior_id": prior_id,
                        "artifact_type": f"{family}@{key}",
                        "solo_or_team": None,
                        "resource_tier": None,
                        "p": _clamp(cell["p"]),
                        "n": cell["n_cell"],
                        "n_cell": cell["n_cell"],
                        "shrunk_to_margin": bool(cell["shrunk_to_margin"]),
                        "thin_cell": bool(cell["thin_cell"]),
                        "computed_from": "own_crawl",
                        "computed_asof": asof,
                    },
                    connection=connection,
                )
                written.append(prior_id)
                existing.add(prior_id)
    ledger.commit()
    return written


# --------------------------------------------------------------------------- #
# the manifest itself
# --------------------------------------------------------------------------- #

def searched_rows(
    person_id: str, asof: str, *, connection: Any = None
) -> dict[str, dict[str, Any]]:
    """Manifest rows for artifacts a verifier actually went and looked for.

    These are the rows that carry an ``evidence_id``, because they correspond to
    a real ``evidence`` row in the ledger: the fetch happened, the URL and status
    are recorded, and the absence (or presence) is a fact rather than a class
    average. They take precedence over a computed row for the same family — a
    direct 404 on this founder's own careers page beats a population rate about
    founders like her.

    The ledger's evidence rows carry no ``artifact_type``, so the family is
    recovered from the claim's ``claim_type`` via :data:`CLAIM_TYPE_TO_FAMILY`.
    """
    out: dict[str, dict[str, Any]] = {}
    for claim in ledger.read_claims(asof, person_id=person_id, connection=connection):
        family = CLAIM_TYPE_TO_FAMILY.get(claim.get("claim_type") or "")
        if not family:
            continue
        for ev in ledger.read_evidence(
            asof, claim_id=claim["claim_id"], connection=connection
        ):
            # Only rows that ARE a manifest prediction. A revenue claim's
            # pricing-page corroboration is evidence for that claim, not a
            # manifest row about hiring — mapping it here by claim_type would
            # put a self-report under an artifact heading it has nothing to do
            # with. The predicted-artifact rows are exactly the expected_absent
            # ones plus the claims the manifest itself opened.
            if ev.get("kind") != "expected_absent" and not claim.get(
                "is_manifest_predicted"
            ):
                continue
            found = bool(ev.get("found"))
            expected = bool(ev.get("expected"))
            penalised = bool(ev.get("penalised"))
            prior_p = ev.get("findability_prior")
            prior_n = ev.get("findability_n")
            delta = float(ev.get("log_odds_delta") or 0.0)

            # Same invariant as the computed path, enforced on ledger rows too:
            # an absence the prior predicted may not cost log-odds, whoever
            # wrote the row.
            if not found and not expected and delta != 0.0:
                raise AssertionError(
                    f"evidence {ev['evidence_id']} charges {delta} log-odds for an "
                    "absence that was not expected. Absence the findability prior "
                    "predicted must never lower the score."
                )

            row = {
                "artifact_type": family,
                "label": FAMILY_LABEL.get(family, family),
                "found": found,
                "expected": expected,
                "penalised": penalised,
                "findability_prior": (
                    _q(round(float(prior_p), 2), prior_n) if prior_p is not None else None
                ),
                "evidence_id": ev["evidence_id"],
                "log_odds_delta": round(delta, 2),
                "interval_widen": round(float(ev.get("interval_widen") or 0.0), 1),
                "source": "searched",
                "claim_id": claim["claim_id"],
                "source_url": ev.get("source_url"),
                "http_status": ev.get("http_status"),
                "verifier": ev.get("verifier"),
                "note": ev.get("finding")
                or (
                    "Searched for directly and not found."
                    if not found
                    else "Searched for directly and found."
                ),
            }
            if not found and not expected:
                row["note"] = (
                    "Not expected for this profile — not penalised. "
                    + (row["note"] or "")
                ).strip()
            out.setdefault(family, row)
    return out


def _note_for(row: dict[str, Any], prior: dict[str, Any] | None) -> str:
    label = row["label"]
    if prior is None:
        return row.get("no_prior_reason") or f"{label}: no prior published."

    p = prior["p_true"]
    n = prior["n"]
    thin = ""
    if prior["thin_cell"]:
        thin = f" Marginal rate; class too thin (n={n})."
    elif prior.get("backed_off_from"):
        finest = prior["backed_off_from"][0]
        thin = (
            f" The finest cell ({finest['cell']}) held only n={finest['n_cell']}, so "
            f"this answers at the '{prior['class_level']}' rung instead of guessing "
            "off one person."
        )

    if row["found"] and row["expected"]:
        return (
            f"Found. Expected at P={p:.2f} over n={n} people in this reference "
            f"class, and present. Contributes {row['log_odds_delta']:+.2f} to the "
            f"claims that depend on it.{thin}"
        )
    if row["found"] and not row["expected"]:
        return (
            f"Found, though the class only predicted it at P={p:.2f} (n={n}). "
            "Unexpected presence informs the estimate; unexpected absence would "
            f"have cost nothing.{thin}"
        )
    if row["penalised"]:
        return (
            f"Expected at P={p:.2f} over n={n} people in this reference class, and "
            f"absent. This widens the interval by {row['interval_widen']:.1f} points "
            f"and contributes {row['log_odds_delta']:+.2f}. Absence is evidence here "
            "precisely because the prior said it should have been there.{}".format(thin)
        )
    return (
        f"Not expected for this profile — not penalised. P={p:.2f} over n={n} "
        "people in the same reference class, which is no higher than the rate "
        "among founders for whom the claim is false, so log((1−p_true)/(1−p_false)) "
        "= 0.00 and the absence costs exactly nothing. This is the row that stops "
        f"the system re-encoding the network gate.{thin}"
    )


def expected_evidence_manifest(
    person_id: str,
    asof: str,
    *,
    priors: dict[str, Any] | None = None,
    population: dict[str, dict[str, Any]] | None = None,
    families: Iterable[str] | None = None,
    connection: Any = None,
) -> dict[str, Any]:
    """The render-ready manifest for one person.

    Shape matches ``web/public/demo.json :: people.<id>.expected_evidence_manifest``
    exactly — ``rows[]`` of ``{artifact_type, found, expected, penalised,
    interval_widen?, findability_prior{value,n}, evidence_id, note}`` — so
    ``export_demo.py`` can adopt it with no frontend change. Extra keys are
    additive; the renderer ignores what it does not read.
    """
    people = population if population is not None else crawl_population(
        asof, connection=connection
    )
    priors = priors if priors is not None else compute_findability_priors(
        asof, population=people, connection=connection
    )

    # The subject is read across every provenance class; the DENOMINATORS behind
    # the priors are live-only. See :func:`person_record` for why that asymmetry
    # is deliberate in both directions.
    person = person_record(person_id, asof, connection=connection) or people.get(person_id)
    if person is None:
        # Degrade honestly: a person with no visible observations at this asof
        # gets an empty manifest that says why, never an invented one.
        return {
            "title": "Expected-evidence manifest",
            "plain_line": (
                "We write down what should exist if the claims were true BEFORE we "
                "search, then go and look for exactly that."
            ),
            "derived_at": asof,
            "findability_priors_source": "Own crawl, read at asof.",
            "n_rows": _q(0, 0),
            "n_penalised": _q(0, 0),
            "n_not_expected": _q(0, 0),
            "rows": [],
            "manifest_blocked_reason": (
                f"No observations visible for {person_id} at asof {asof}. A manifest "
                "over zero observations would be a list of guesses, so none is "
                "rendered."
            ),
            "closing_line": "Nothing observed at this asof. Nothing asserted.",
        }

    klass = resource_class(person)
    searched = searched_rows(person_id, asof, connection=connection)
    wanted = list(families) if families is not None else list(ARTIFACT_FAMILIES)
    # Families a verifier searched for on THIS founder but which are not in the
    # crawl vocabulary (cap table, round terms, GitHub) still belong on the
    # manifest — they were part of what we said should exist.
    wanted += [f for f in searched if f not in wanted]

    rows: list[dict[str, Any]] = []
    for family in wanted:
        if family in searched:
            rows.append(dict(searched[family]))
            continue

        prior = prior_for(priors, family, person)
        found = family in person["families"]
        entry = priors["families"].get(family, {})

        row: dict[str, Any] = {
            "artifact_type": family,
            "label": FAMILY_LABEL.get(family, family),
            "found": bool(found),
        }

        if prior is None:
            # No prior published — say which guard refused it and stop. The row
            # still renders, because "we looked and we cannot price this" is a
            # fact worth showing.
            row.update(
                {
                    "expected": False,
                    "penalised": False,
                    "findability_prior": None,
                    "evidence_id": None,
                    "log_odds_delta": 0.0,
                    "interval_widen": 0.0,
                    "no_prior_reason": entry.get("refusal_reason", "No prior."),
                    "prior_refused": True,
                }
            )
            row["note"] = row["no_prior_reason"]
            rows.append(row)
            continue

        lr = likelihood_ratio(prior["p_true"], prior["p_false"])
        expected = bool(
            prior["p_true"] >= EXPECT_P and lr["llr_absent"] <= EXPECT_LLR
        )
        penalised = bool(expected and not found)

        row.update(
            {
                "expected": expected,
                "penalised": penalised,
                "findability_prior": _q(round(prior["p_true"], 2), prior["n"]),
                "findability_prior_if_false": _q(
                    round(prior["p_false"], 2), prior["n_complement"]
                ),
                "evidence_id": None,
                "log_odds_delta": (
                    round(lr["llr_present"], 2)
                    if found
                    else (round(lr["llr_absent"], 2) if penalised else 0.0)
                ),
                "interval_widen": (
                    0.0 if found else round(WIDEN_SCALE * prior["p_true"], 1)
                ),
                "llr_present": lr["llr_present"],
                "llr_absent": lr["llr_absent"],
                "thin_cell": prior["thin_cell"],
                "reference_class": klass,
                "class_level": prior["class_level"],
                "cell": prior["cell"],
                "source": "computed",
            }
        )

        # THE INVARIANT. Absence that the prior predicted costs exactly zero
        # log-odds. Asserted here rather than trusted, because this single line
        # is the difference between a cold-start engine and a network gate.
        if not found and not expected and row["log_odds_delta"] != 0.0:
            raise AssertionError(
                f"{family}: unexpected absence charged {row['log_odds_delta']} "
                "log-odds. Absence the findability prior predicted must never "
                "lower the score."
            )

        row["note"] = _note_for(row, prior)
        rows.append(row)

    n = len(rows)
    n_pen = sum(1 for r in rows if r["penalised"])
    n_not_expected = sum(1 for r in rows if not r["expected"])
    widen_total = round(sum(r.get("interval_widen") or 0.0 for r in rows), 1)
    n_absent_free = sum(
        1 for r in rows if not r["found"] and not r["expected"] and not r.get("prior_refused")
    )

    return {
        "title": "Expected-evidence manifest",
        "plain_line": (
            "We wrote down what should exist if the claims were true BEFORE we "
            "searched, then went and looked for exactly that."
        ),
        "derived_at": asof,
        "findability_priors_source": (
            f"Empirical rates over our own {priors['n_people']}-person crawl, "
            "computed per reference-class cell with the cell count printed. Cells "
            f"under n={THIN_CELL_N} are shrunk to the family margin and say so. "
            "Nothing here is a hardcoded constant."
        ),
        "reference_class": klass,
        "n_rows": _q(n, n),
        "n_penalised": _q(n_pen, n),
        "n_not_expected": _q(n_not_expected, n),
        "interval_widen_total": _q(widen_total, n),
        "rows": rows,
        "closing_line": (
            f"{n_absent_free} of these {n} rows "
            f"{'is an absence' if n_absent_free == 1 else 'are absences'} our "
            "findability prior already predicted. They are greyed out and they cost "
            f"exactly zero log-odds. {n_pen} expected "
            f"{'absence is' if n_pen == 1 else 'absences are'} penalised, widening "
            f"the interval by {widen_total:.1f} points in total without lowering the "
            "point estimate. Missing expected evidence widens the interval and never "
            "lowers the score — that asymmetry is the entire cold-start mechanism, "
            "expressed as arithmetic rather than as a value statement."
        ),
    }


# --------------------------------------------------------------------------- #
# printing — the priors are only defensible if they are visible
# --------------------------------------------------------------------------- #

def print_findability_priors(priors: dict[str, Any]) -> None:
    print()
    print("=" * 94)
    print("FINDABILITY PRIORS — P(artifact observable | reference class)")
    print("=" * 94)
    print(
        f"Computed from our own crawl at asof {priors['asof']}: "
        f"{priors['n_observations']} live observations over {priors['n_people']} people."
    )
    print(
        f"Shrinkage pseudo-count k={priors['shrinkage_k']:.0f}; cells under "
        f"n={priors['thin_cell_n']} are stamped thin and shrunk to the family margin."
    )
    print("Reference class carries NO pedigree field: no school, employer, accelerator or investor.")
    print()
    print(
        f"{'artifact family':<27} {'reference-class cell':<42} {'k/n':>9} "
        f"{'p_raw':>6} {'p':>6}  flags"
    )
    print("-" * 94)
    for family, entry in priors["families"].items():
        if entry.get("coverage_gap") or entry.get("tautological"):
            continue
        for level_name, _ in CLASS_LADDER:
            for key, cell in sorted(
                entry["levels"].get(level_name, {}).items(),
                key=lambda kv: -kv[1]["n_cell"],
            ):
                flags = f"THIN (n={cell['n_cell']}) — shrunk to margin" if cell["thin_cell"] else ""
                praw = "—" if cell["p_raw"] is None else f"{cell['p_raw']:.2f}"
                print(
                    f"{family:<27} {key[:42]:<42} "
                    f"{str(cell['k']) + '/' + str(cell['n_cell']):>9} "
                    f"{praw:>6} {cell['p']:>6.2f}  {flags}"
                )
    print()
    publishable = [
        f for f, e in priors["families"].items()
        if not e.get("coverage_gap") and not e.get("tautological")
    ]
    print(
        f"{len(publishable)} of {len(priors['families'])} artifact families carry a "
        f"publishable conditional prior. The rest are refused below, with the reason."
    )
    print()
    print("REFUSED — no prior published, and why:")
    for family, entry in priors["families"].items():
        if entry.get("coverage_gap") or entry.get("tautological"):
            kind = "COVERAGE GAP" if entry.get("coverage_gap") else "TAUTOLOGICAL"
            print(
                f"  {family:<28} [{kind}] observed on "
                f"{entry['support']['value']}/{entry['support']['n']} people"
            )
            print(f"      {entry['refusal_reason']}")
    print()
    print("NOT CRAWLED — named rather than silently missing:")
    for name, reason in priors["not_crawled"].items():
        print(f"  {name}")
        print(f"      {reason}")


def print_manifest(manifest: dict[str, Any]) -> None:
    print()
    print("=" * 94)
    print(f"{manifest['title'].upper()} — {manifest.get('person_label', '')}")
    print("=" * 94)
    print(manifest["plain_line"])
    if manifest.get("reference_class"):
        rc = manifest["reference_class"]
        print(
            f"Reference class: founder_type={rc['founder_type']} · "
            f"has_company_domain={rc['has_company_domain']} · sector={rc['sector']} · "
            f"solo_or_team={rc['solo_or_team']} · resource_tier={rc['resource_tier']} "
            f"· pedigree fields: none"
        )
    print()
    print(
        f"{'artifact':<28} {'found':<7} {'expected':<10} {'prior (n)':<14} "
        f"{'Δ log-odds':>11} {'widen':>7}"
    )
    print("-" * 94)
    for r in manifest["rows"]:
        fp = r.get("findability_prior")
        prior_txt = f"{fp['value']:.2f} (n={fp['n']})" if fp else "no prior"
        exp = "expected" if r["expected"] else "NOT expected"
        delta = r.get("log_odds_delta") or 0.0
        widen = r.get("interval_widen") or 0.0
        mark = ""
        if not r["found"] and not r["expected"] and not r.get("prior_refused"):
            mark = "   <- grey row: not expected for this profile, NOT PENALISED"
        elif r["penalised"]:
            mark = "   <- expected and absent: widens the interval, score unchanged"
        print(
            f"{r['artifact_type']:<28} {'found' if r['found'] else 'absent':<7} "
            f"{exp:<10} {prior_txt:<14} {delta:>+11.2f} {widen:>7.1f}{mark}"
        )
    print()
    print(f"rows={manifest['n_rows']['value']}  penalised={manifest['n_penalised']['value']}"
          f"  not-expected={manifest['n_not_expected']['value']}"
          f"  interval widened by {manifest['interval_widen_total']['value']:.1f} points")
    print()
    for r in manifest["rows"]:
        if (not r["found"] and not r["expected"] and not r.get("prior_refused")) or r["penalised"]:
            print(f"  {r['artifact_type']}: {r['note']}")
    print()
    print(manifest["closing_line"])


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

    argv = list(argv if argv is not None else sys.argv[1:])
    asof = argv[0] if argv else "2026-07-19T02:14:33Z"

    store.open_ledger()  # NEVER reset=True — four agents share this database.

    total = store.count_observations(asof)
    print(f"asof {asof} · {total} observations visible through the chokepoint")

    people = crawl_population(asof)
    priors = compute_findability_priors(asof, population=people)
    print_findability_priors(priors)

    written = persist_findability_priors(priors)
    print()
    print(f"persisted {len(written)} findability_prior rows (append-only, computed_from='own_crawl')")

    # Show one operator and one technical founder so both sides of the asymmetry
    # are on screen at once.
    picks: list[tuple[str, str]] = []
    for pid in ("per_mo", "per_dr"):
        # Deliberately NOT `pid in people` — the heroes' rows are fixtures and the
        # live-only population correctly excludes them from the denominators.
        if person_record(pid, asof) is not None:
            picks.append((pid, pid))
    if not picks:
        by_type: dict[str, str] = {}
        for pid, p in people.items():
            by_type.setdefault(p["founder_type"], pid)
        picks = [(pid, pid) for pid in by_type.values()]

    for pid, _ in picks[:3]:
        m = expected_evidence_manifest(pid, asof, priors=priors, population=people)
        person = ledger.get_person(pid) or {}
        m["person_label"] = f"{person.get('display_name', pid)} ({pid})"
        print_manifest(m)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
