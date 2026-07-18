"""Three axes, scored independently, never reduced to one number.

    uv run python -m worker.scoring.axes

WHAT THIS MODULE REFUSES TO DO
------------------------------
There is no averaged column in ``db/schema.sql`` and there is no averaged value
anywhere in this file. Founder and Idea-vs-Market are numeric on 0-100. Market is
CATEGORICAL — ``bullish`` / ``neutral`` / ``bear`` — and its ``value`` is ``None``
by construction, so the three cannot be combined even by accident by a later
caller who was not paying attention. Collapsing them would hide exactly the
disagreement an investor is paying to see, which is why the disagreement is
promoted to a typed field (``axes_disagree``) and a headline naming the BINDING
axis and the DISSENTING one, and why nothing here resolves it.

Comparing the axes is not averaging them. Each axis is banded into the same three
words (bear / neutral / bullish) purely so the headline can say which one binds;
the bands come from the active thesis's ``conviction_threshold`` rather than from
a constant in this file, so re-configuring the fund re-bands the board.

THE ASOF CHOKEPOINT IS THE POINT
--------------------------------
Every observation read goes through ``store.read_observations(asof, ...)``. Trend
is produced by calling :func:`score_axes_at` four times — at ``asof-90``,
``asof-60``, ``asof-30`` and ``asof`` — on the IDENTICAL code path, and running
OLS across the four results. Nothing is filtered in Python after a single read;
if it were, the trend would be a redrawing of one score rather than four scores,
and the point-in-time claim would be false. ``improving`` / ``declining`` is
printed only when the slope's 95% band excludes zero. Otherwise the axis says
``insufficient dated observations`` and shows the count, because a line drawn
through two points is a decoration, not a measurement.

ABSENCE
-------
Missing expected evidence WIDENS the interval and never lowers the point, unless
the findability prior for that artifact in this reference class said the artifact
was likely to be observable. The reference class is
``{artifact_type, sector, solo_or_team, resource_tier, region}`` and carries no
pedigree field — no school, no employer, no accelerator, no investor.

MEMORY WRITEBACK (MVP element 6)
--------------------------------
When a Market verdict lands, :func:`writeback_market_prior` appends a
``sector_prior`` row for that sector. The NEXT company scored in the same sector
reads it as its reference class, so a bear verdict marks down the whole sector for
whoever comes next. Append-only: a re-run appends nothing it has already written.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from worker import ledger, store  # noqa: E402
from worker.ledger import append_row, read_claims  # noqa: E402
from worker.store import parse_iso, read_observations, to_iso  # noqa: E402

DEFAULT_ASOF = "2026-07-19T02:14:33Z"

# The four re-scoring instants. This tuple is the entire trend mechanism.
TREND_OFFSETS_DAYS = (-90, -60, -30, 0)

# Empirical-Bayes shrinkage constants: w = n / (n + k). Stated, not learned.
K_FOUNDER = 6.0
K_IDEA = 5.0

# Market stance thresholds on the internal ordinal index. The index exists ONLY
# to order a categorical verdict and to give the categorical axis something to
# run OLS over (bear=-1 / neutral=0 / bullish=+1); it is never rendered as the
# axis value and it never leaves this module as `value`.
MARKET_BEAR_AT = -0.35
MARKET_BULLISH_AT = 0.35

# Learning rate on the Memory writeback: how hard one Market verdict marks its
# sector for the next company through the door.
SECTOR_PRIOR_LR = 0.5

# Two-sided 95% t critical values. Four trend points means dof = 2.
T_CRIT = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447}

AXES = ("founder", "market", "idea_vs_market")

_DOMAIN_STATE_POINTS = {
    "transacting": 12.0,
    "pricing_page": 6.0,
    "changelog": 4.0,
    "calendly": 0.0,
    "waitlist": -4.0,
    "parked": -10.0,
    "unreachable": -10.0,
}

# claim_type -> the artifact whose findability prior governs its absence.
_ABSENCE_ARTIFACT = {
    "code_artifact": "github_repo",
    "ship_cadence": "changelog",
    "team_page": "team_page",
    "press_mention": "press_mention",
    "cap_table": "cap_table",
    "round_terms": "cap_table",
    "open_roles": "job_posting",
    "pricing_published": "pricing_page",
}


# --------------------------------------------------------------------------- #
# small numerics — stdlib only, closed form, exact
# --------------------------------------------------------------------------- #

def _clip(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs)


def ols_slope_band(
    xs: Sequence[float], ys: Sequence[float]
) -> dict[str, Any] | None:
    """OLS slope with its two-sided 95% band. ``None`` when it cannot be computed.

    Closed form, so it is exact and instantaneous and a judge can redo it by
    hand. The band — not the sign of the slope — is what decides whether a trend
    label is allowed to exist.
    """
    n = len(xs)
    if n < 3 or n != len(ys):
        return None
    xbar, ybar = _mean(xs), _mean(ys)
    sxx = sum((x - xbar) ** 2 for x in xs)
    if sxx == 0:
        return None
    slope = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys)) / sxx
    intercept = ybar - slope * xbar
    dof = n - 2
    resid = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    s2 = sum(r * r for r in resid) / dof
    se = math.sqrt(s2 / sxx)
    t = T_CRIT.get(dof, 1.96)
    return {
        "slope_per_day": slope,
        "se": se,
        "dof": dof,
        "t_crit": t,
        "band_per_day": (slope - t * se, slope + t * se),
        # A perfectly linear series at four points gives a zero-width band. That
        # is arithmetically correct and rhetorically overconfident, so it is
        # flagged rather than presented as certainty.
        "exact_fit": s2 == 0.0,
    }


def _trend_from_series(
    points: list[dict[str, Any]], *, scale_days: float = 30.0
) -> dict[str, Any]:
    """Label a series of re-scored points. Never asserts; only reports.

    ``points`` are the outputs of the same scorer at the four asof instants,
    each carrying the observation ids it read, so every plotted point clicks
    through to its source rows.
    """
    scored = [p for p in points if p["value"] is not None]
    n_pts = len(scored)
    base = {
        "trend": "insufficient_data",
        "trend_band": None,
        "trend_slope": None,
        "n_trend_points": n_pts,
        "trend_basis": f"OLS over {len(points)} asof re-scores; slope in units per {int(scale_days)} days",
        "trend_note": None,
        "trend_points": points,
    }
    if n_pts < 3:
        base["trend_note"] = (
            f"insufficient dated observations (n={n_pts}) — a line through "
            f"{n_pts} point(s) is a decoration, not a measurement"
        )
        return base

    xs = [float(p["offset_days"]) for p in scored]
    ys = [float(p["value"]) for p in scored]
    fit = ols_slope_band(xs, ys)
    if fit is None:
        base["trend_note"] = "slope not identifiable at these asof points"
        return base

    lo = round(fit["band_per_day"][0] * scale_days, 2)
    hi = round(fit["band_per_day"][1] * scale_days, 2)
    slope = round(fit["slope_per_day"] * scale_days, 2)
    if lo > 0:
        label = "improving"
    elif hi < 0:
        label = "declining"
    else:
        label = "stable"
    base.update(
        {
            "trend": label,
            "trend_band": [lo, hi],
            "trend_slope": slope,
            "trend_note": (
                (
                    f"band [{lo}, {hi}] excludes zero at dof={fit['dof']}"
                    + (
                        " — residual variance is exactly zero, so this band is degenerate "
                        "and the label rests on a perfectly linear series"
                        if fit["exact_fit"]
                        else ""
                    )
                )
                if label != "stable"
                else f"band [{lo}, {hi}] includes zero — no trend claimed"
            ),
        }
    )
    return base


# --------------------------------------------------------------------------- #
# reference class and priors — read at an asof like everything else
# --------------------------------------------------------------------------- #

def _reliability_table(conn: sqlite3.Connection) -> dict[str, float]:
    return {
        r["source_class"]: float(r["log_odds"])
        for r in conn.execute("SELECT source_class, log_odds FROM source_reliability")
    }


def _active_thesis(conn: sqlite3.Connection, asof: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM thesis WHERE is_active = 1 AND observed_at <= :asof "
        "ORDER BY observed_at DESC, version_number DESC LIMIT 1",
        {"asof": asof},
    ).fetchone()
    if row:
        return row
    return {"conviction_threshold": 55.0, "max_interval_width": 30.0, "risk_appetite": "medium"}


def _reference_class(person: dict[str, Any] | None, org: dict[str, Any] | None) -> dict[str, Any]:
    """{artifact_type, sector, solo_or_team, resource_tier, region}. No pedigree."""
    person = person or {}
    org = org or {}
    return {
        "sector": person.get("sector") or org.get("sector"),
        "solo_or_team": person.get("solo_or_team") or "unknown",
        "resource_tier": person.get("resource_tier") or "unknown",
        "region": person.get("region") or org.get("region"),
        "pedigree_fields": [],
        "pedigree_note": "No school, employer, accelerator or investor field exists in this class.",
    }


def _findability(
    conn: sqlite3.Connection, asof: str, artifact_type: str, ref: dict[str, Any]
) -> dict[str, Any]:
    """P(artifact observable | reference class), with its cell count.

    Exact cell first; if the cell does not exist we shrink to the artifact
    margin and say so. If nothing exists at all we return ``p=None`` — and an
    unknown prior NEVER penalises, because penalising on an absent prior is
    exactly the network gate wearing a lab coat.
    """
    exact = conn.execute(
        "SELECT * FROM findability_prior WHERE observed_at <= :asof "
        "AND artifact_type = :a AND sector IS :s AND solo_or_team IS :t "
        "AND resource_tier IS :r ORDER BY observed_at DESC LIMIT 1",
        {
            "asof": asof,
            "a": artifact_type,
            "s": ref.get("sector"),
            "t": ref.get("solo_or_team"),
            "r": ref.get("resource_tier"),
        },
    ).fetchone()
    if exact:
        return {
            "p": float(exact["p"]),
            "n": int(exact["n"]),
            "cell": "exact",
            "shrunk_to_margin": bool(exact["shrunk_to_margin"]),
            "thin_cell": bool(exact["thin_cell"]),
        }
    margin = conn.execute(
        "SELECT p, n FROM findability_prior WHERE observed_at <= :asof "
        "AND artifact_type = :a AND sector IS :s",
        {"asof": asof, "a": artifact_type, "s": ref.get("sector")},
    ).fetchall()
    if margin:
        total = sum(int(m["n"]) for m in margin) or 1
        p = sum(float(m["p"]) * int(m["n"]) for m in margin) / total
        return {
            "p": round(p, 3),
            "n": total,
            "cell": "shrunk_to_margin",
            "shrunk_to_margin": True,
            "thin_cell": total < 25,
        }
    return {"p": None, "n": 0, "cell": "absent", "shrunk_to_margin": False, "thin_cell": True}


def read_sector_priors(
    asof: str,
    sector: str | None,
    axis: str,
    *,
    exclude_written_by: Iterable[str] = (),
    connection: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    """Sector priors visible at ``asof`` — the Memory writeback, read back.

    ``exclude_written_by`` exists for one honest purpose: showing what the next
    company in a sector would have scored BEFORE a given verdict marked the
    sector down. It never hides a row from a real score.
    """
    if not sector:
        return []
    c = connection or store.conn()
    rows = c.execute(
        "SELECT * FROM sector_prior WHERE observed_at <= :asof "
        "AND sector = :sector AND axis = :axis ORDER BY observed_at ASC",
        {"asof": asof, "sector": sector, "axis": axis},
    ).fetchall()
    skip = set(exclude_written_by)
    return [r for r in rows if r["written_by_opportunity"] not in skip]


def _prior_shift(rows: list[dict[str, Any]]) -> float:
    return round(sum(float(r["prior_shift"] or 0.0) for r in rows), 3)


# --------------------------------------------------------------------------- #
# the per-asof context — ONE pass through the chokepoint per instant
# --------------------------------------------------------------------------- #

def _context(
    asof: str,
    opportunity: dict[str, Any],
    *,
    exclude_priors_from: Iterable[str] = (),
) -> dict[str, Any]:
    c = store.conn()
    opp_id = opportunity["opportunity_id"]
    # An opportunity never reads back its OWN Memory writeback. Your own verdict
    # is not evidence about you, and without this a second run of the module
    # would score each company against a sector prior it wrote itself.
    exclude_priors_from = set(exclude_priors_from) | {opp_id}

    # THE read. Everything downstream is a pure function of these rows.
    obs = read_observations(asof, opportunity_id=opp_id, order="asc")
    claims = read_claims(asof, opportunity_id=opp_id)

    person = ledger.get_person(opportunity["person_id"]) if opportunity.get("person_id") else None
    org = None
    if opportunity.get("org_id"):
        org = c.execute(
            "SELECT * FROM org WHERE org_id = ?", (opportunity["org_id"],)
        ).fetchone()
    ref = _reference_class(person, org)
    sector = opportunity.get("sector") or ref.get("sector")

    history = (
        ledger.read_founder_score_history(opportunity["person_id"], asof)
        if opportunity.get("person_id")
        else []
    )
    latest: dict[str, dict[str, Any]] = {}
    for row in history:  # already ordered ascending; last write per component wins
        latest[row["component"]] = row

    return {
        "asof": asof,
        "opportunity": opportunity,
        "opportunity_id": opp_id,
        "sector": sector,
        "person": person,
        "org": org,
        "reference_class": ref,
        "observations": obs,
        "claims": claims,
        "founder_score": latest,
        "reliability": _reliability_table(c),
        "thesis": _active_thesis(c, asof),
        "priors": {
            axis: read_sector_priors(
                asof, sector, axis, exclude_written_by=exclude_priors_from, connection=c
            )
            for axis in AXES
        },
        "conn": c,
    }


def _absence(ctx: dict[str, Any]) -> dict[str, Any]:
    """Split absent-but-expected claims into penalised and widen-only.

    This is the single most important arithmetic in the project. An artifact the
    findability prior said we probably would NOT see for this resource class
    costs nothing — it only widens the interval. An artifact the prior said we
    probably WOULD see, and did not, is a refutation and is priced as one.
    """
    penalised, widen_only = [], []
    for claim in ctx["claims"]:
        if claim["state"] != "absent_but_expected":
            continue
        artifact = _ABSENCE_ARTIFACT.get(claim["claim_type"], claim["claim_type"])
        prior = _findability(ctx["conn"], ctx["asof"], artifact, ctx["reference_class"])
        entry = {
            "claim_id": claim["claim_id"],
            "claim_type": claim["claim_type"],
            "artifact_type": artifact,
            "findability_p": prior["p"],
            "findability_n": prior["n"],
            "cell": prior["cell"],
        }
        if prior["p"] is not None and prior["p"] >= 0.5:
            entry["verdict"] = (
                f"expected at p={prior['p']} (n={prior['n']}) and not found — priced as a refutation"
            )
            penalised.append(entry)
        else:
            entry["verdict"] = (
                f"not expected for this founder profile (p={prior['p']}, n={prior['n']}) "
                "— not penalised, widens the interval only"
            )
            widen_only.append(entry)
    return {"penalised": penalised, "widen_only": widen_only}


# --------------------------------------------------------------------------- #
# AXIS 1 — Founder. Traits and track record.
# --------------------------------------------------------------------------- #

def score_founder_axis(ctx: dict[str, Any]) -> dict[str, Any]:
    """Numeric, 0-100.

    FOUR inputs, and the persistent Founder Score is only ONE of them. It is read
    from ``founder_score_version`` at this asof — the per-person score that
    crosses companies and never resets — and it informs the axis rather than
    standing in for it. An axis that WAS the Founder Score would make the
    per-person history and the per-opportunity read the same object, and the
    brief separates them for a reason.
    """
    obs = ctx["observations"]
    claims = ctx["claims"]
    rel = ctx["reliability"]
    absence = _absence(ctx)

    n_obs = len(obs)
    w = n_obs / (n_obs + K_FOUNDER) if n_obs else 0.0

    # input 1 — direct observable evidence, weighted by the published, hand-set
    # source-reliability table (self-report is negative; registry filing is +2.4)
    signal = _mean([rel.get(o["source_class"], 0.0) for o in obs]) if obs else 0.0
    evidence_component = _clip(50.0 + 9.0 * signal)

    # input 2 — what survived verification at this asof
    n_verified = sum(1 for c in claims if c["state"] == "verified")
    n_contradicted = sum(1 for c in claims if c["state"] == "contradicted")
    claim_delta = 4.0 * n_verified - 9.0 * n_contradicted - 6.0 * len(absence["penalised"])

    # input 3 — the persistent Founder Score out of Memory. ONE input.
    fs = ctx["founder_score"]
    cred = fs.get("credibility")
    build = fs.get("build_capability")
    memory_component = None
    memory_n = 0
    if cred or build:
        parts = [float(r["point"]) for r in (cred, build) if r]
        memory_component = _mean(parts)
        memory_n = max(int(r["n"] or 0) for r in (cred, build) if r)

    direct = evidence_component + claim_delta
    if memory_component is not None:
        direct = 0.55 * direct + 0.45 * memory_component
    direct = _clip(direct)

    # input 4 — the reference class, carrying whatever Memory has written back
    prior_rows = ctx["priors"]["founder"]
    prior_mean = _clip(50.0 + 8.0 * _prior_shift(prior_rows))

    point = round(w * direct + (1.0 - w) * prior_mean, 1)
    half = min(45.0, 8.0 + 22.0 * (1.0 - w) + 2.5 * len(absence["widen_only"]))
    interval = [round(_clip(point - half), 1), round(_clip(point + half), 1)]

    return {
        "axis": "founder",
        "value": point,
        "interval": interval,
        "n": n_obs,
        "prior_weight": round(1.0 - w, 3),
        "categorical": False,
        "inputs": {
            "observable_evidence": {"value": round(evidence_component, 1), "n": n_obs},
            "claim_outcomes": {"value": round(claim_delta, 1), "n": len(claims)},
            "memory_founder_score": (
                {"value": round(memory_component, 1), "n": memory_n,
                 "source": "founder_score_version (credibility + build_capability)"}
                if memory_component is not None
                else {"value": None, "n": 0, "source": "no founder score version at this asof"}
            ),
            "reference_class_prior": {"value": round(prior_mean, 1), "n": len(prior_rows)},
        },
        "absence": absence,
        "reference_class": ctx["reference_class"],
        "observation_ids": [o["observation_id"] for o in obs],
        "claim_ids": [c["claim_id"] for c in claims],
        "rationale": (
            f"{n_obs} direct observations at this asof, {n_verified} claims verified and "
            f"{n_contradicted} contradicted. Prior weight {round((1.0 - w) * 100)}% — that share "
            f"of this number is the reference class, not the person. The persistent Founder Score "
            f"is one of four inputs here, not a substitute for the axis. "
            f"{len(absence['widen_only'])} absent-but-expected item(s) widened the interval "
            f"without lowering the point."
        ),
    }


# --------------------------------------------------------------------------- #
# AXIS 2 — Market. CATEGORICAL, so it cannot be averaged with the other two.
# --------------------------------------------------------------------------- #

def score_market_axis(ctx: dict[str, Any]) -> dict[str, Any]:
    """bullish / neutral / bear. ``value`` is None, always, by construction.

    The internal ordinal index below orders the verdict and gives the axis a
    series to run OLS over. It is never emitted as ``value`` and it is not on a
    scale shared with the numeric axes.
    """
    obs = ctx["observations"]
    claims = ctx["claims"]
    terms: list[dict[str, Any]] = []
    used_obs: list[str] = []
    used_claims: list[str] = []

    def add(label: str, delta: float, ids: list[str], n: int, claim_ids: Sequence[str] = ()) -> None:
        terms.append(
            {"label": label, "delta": round(delta, 3), "n": n,
             "observation_ids": list(ids), "claim_ids": list(claim_ids)}
        )
        used_obs.extend(ids)
        used_claims.extend(claim_ids)

    # sizing — claimed market size, and whether it survived verification
    for claim in claims:
        if claim["claim_type"] not in ("market_size", "market_comparable"):
            continue
        cid = [claim["claim_id"]]
        if claim["state"] == "verified":
            add(f"{claim['claim_type']} verified", 0.3, [], 1, cid)
        elif claim["state"] == "contradicted":
            add(f"{claim['claim_type']} contradicted", -0.8, [], 1, cid)
        else:
            add(f"{claim['claim_type']} unverified — no sizing evidence either way", 0.0, [], 1, cid)

    # competitors — a comparable on file means the wedge already has an occupant
    comparables = [c["claim_id"] for c in claims if c["claim_type"] == "market_comparable"]
    n_comparable = len(comparables)
    if n_comparable:
        add("comparable on file — wedge is occupied", -0.4 * min(n_comparable, 2), [], n_comparable, comparables)

    # demand, read off public third-party surfaces rather than a self-report
    reviews = [o for o in obs if o["claim_type"] == "review_volume"]
    if len(reviews) >= 2:
        first, last = _to_float(reviews[0]["value"]), _to_float(reviews[-1]["value"])
        if first is not None and last is not None and first > 0:
            direction = 1.0 if last > first else (-1.0 if last < first else 0.0)
            # scaled by absolute base: 19 public reviews is a direction, not a market
            magnitude = min(1.0, last / 50.0)
            add(
                f"public review volume {int(first)} -> {int(last)} (base scales the weight)",
                0.6 * direction * magnitude,
                [r["observation_id"] for r in reviews],
                len(reviews),
            )

    # a comparable in this sector that wound down is a market fact, not a person fact
    wound = [o for o in obs if o["claim_type"] == "wind_down" or o["milestone_type"] == "wound_down"]
    if wound:
        add(
            "a venture in this sector wound down — observed, not inferred",
            -0.6,
            [o["observation_id"] for o in wound],
            len(wound),
        )

    press = [o for o in obs if o["artifact_type"] == "press_mention" and o["claim_type"] != "wind_down"]
    if press:
        add("independent press coverage exists", 0.2, [p["observation_id"] for p in press], len(press))

    own_n = sum(t["n"] for t in terms)
    own_index = sum(t["delta"] for t in terms)

    # THE MEMORY WRITEBACK, READ BACK: what previous Market verdicts in this
    # sector did to the reference class the next company inherits.
    prior_rows = ctx["priors"]["market"]
    prior_shift = _prior_shift(prior_rows)
    index = round(own_index + prior_shift, 3)

    if index <= MARKET_BEAR_AT:
        label = "bear"
    elif index >= MARKET_BULLISH_AT:
        label = "bullish"
    else:
        label = "neutral"

    n_total = own_n + len(prior_rows)
    prior_weight = round(len(prior_rows) / n_total, 3) if n_total else 1.0

    if own_n == 0 and prior_rows:
        rationale = (
            f"No market evidence of its own at this asof (own n=0). This verdict is the "
            f"reference class: {len(prior_rows)} prior Market verdict(s) in {ctx['sector']} "
            f"written back to Memory, net shift {prior_shift}. 100% of this label is the "
            f"sector prior and we say so rather than dressing it as a read."
        )
    else:
        rationale = (
            f"{own_n} market row(s) at this asof, stance index {round(own_index, 3)} "
            f"from the terms listed, plus a sector prior of {prior_shift} carried over from "
            f"{len(prior_rows)} previous Market verdict(s) in {ctx['sector']}. Categorical on "
            f"purpose: there is no number here, so there is nothing that could be combined with "
            f"the other two axes even by accident."
        )

    return {
        "axis": "market",
        "value": None,
        "interval": None,
        "label": label,
        "stance": label,
        "categorical": True,
        "n": n_total,
        "prior_weight": prior_weight,
        "value_blocked_reason": (
            "Market is categorical by construction. A number here would be the first step "
            "towards an averaged axis, which this system does not have."
        ),
        "stance_index": index,
        "stance_index_note": (
            f"ordinal encoding bear<={MARKET_BEAR_AT} / neutral / bullish>={MARKET_BULLISH_AT}; "
            "used to order the verdict and to give a categorical axis a series to fit. "
            "It is not the axis value and it is not on the numeric axes' scale."
        ),
        "terms": terms,
        "sector_prior": {
            "value": prior_shift,
            "n": len(prior_rows),
            "written_by": [r["written_by_opportunity"] for r in prior_rows],
        },
        "observation_ids": used_obs,
        "claim_ids": used_claims,
        "rationale": rationale,
    }


def _to_float(value: Any) -> float | None:
    try:
        return float(str(value).split("_")[0])
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# AXIS 3 — Idea vs Market. Survives as-is, or is the team strong enough to pivot?
# --------------------------------------------------------------------------- #

def score_idea_vs_market_axis(
    ctx: dict[str, Any], market: dict[str, Any]
) -> dict[str, Any]:
    """Numeric, 0-100, plus a typed ``survives_as_is`` / ``requires_pivot``.

    The second clause of the brief's own definition legitimately reads the
    founder side: build capability out of Memory answers "can this team carry a
    pivot". That is the ONLY cross-axis link in the system and it is declared
    here rather than smuggled in.
    """
    obs = ctx["observations"]
    claims = ctx["claims"]
    absence = _absence(ctx)
    terms: list[dict[str, Any]] = []
    used_obs: list[str] = []
    used_claims: list[str] = []

    def add(label: str, delta: float, ids: list[str], n: int, claim_ids: Sequence[str] = ()) -> None:
        terms.append(
            {"label": label, "delta": round(delta, 2), "n": n,
             "observation_ids": list(ids), "claim_ids": list(claim_ids)}
        )
        used_obs.extend(ids)
        used_claims.extend(claim_ids)

    # does the market transact against this product today?
    domain = [o for o in obs if o["claim_type"] == "domain_state"]
    if domain:
        state = str(domain[-1]["value"])
        add(
            f"latest domain state '{state}' — transacting-vs-parked is the highest-value bit here",
            _DOMAIN_STATE_POINTS.get(state, 0.0),
            [domain[-1]["observation_id"]],
            len(domain),
        )

    # is it still being built?
    cadence = [o for o in obs if o["claim_type"] == "ship_cadence"]
    if len(cadence) >= 2:
        first, last = _to_float(cadence[0]["value"]), _to_float(cadence[-1]["value"])
        if first is not None and last is not None and first > 0:
            ratio = max(-1.0, min(1.0, (last - first) / first))
            add(
                f"ship cadence {int(first)} -> {int(last)} entries/90d",
                8.0 * ratio,
                [c["observation_id"] for c in cadence],
                len(cadence),
            )

    for claim in claims:
        if claim["claim_type"] not in ("product_shipped", "payments_live", "pricing_published", "integrations"):
            continue
        if claim["state"] == "verified":
            add(f"{claim['claim_type']} verified", 5.0, [], 1, [claim["claim_id"]])
        elif claim["state"] == "contradicted":
            add(f"{claim['claim_type']} contradicted", -8.0, [], 1, [claim["claim_id"]])

    comparables = [c["claim_id"] for c in claims if c["claim_type"] == "market_comparable"]
    n_comparable = len(comparables)
    if n_comparable:
        add("wedge already occupied by a comparable", -6.0 * min(n_comparable, 2), [], n_comparable, comparables)

    # the idea is scored AGAINST the market read — that is the name of the axis
    stance_points = {"bear": -6.0, "neutral": 0.0, "bullish": 6.0}[market["label"]]
    add(f"market read is {market['label'].upper()}", stance_points, [], market["n"])

    n_terms = sum(t["n"] for t in terms)
    w = n_terms / (n_terms + K_IDEA) if n_terms else 0.0
    direct = _clip(50.0 + sum(t["delta"] for t in terms))
    prior_rows = ctx["priors"]["idea_vs_market"]
    prior_mean = _clip(50.0 + 8.0 * _prior_shift(prior_rows))
    point = round(w * direct + (1.0 - w) * prior_mean, 1)
    half = min(45.0, 7.0 + 20.0 * (1.0 - w) + 2.5 * len(absence["widen_only"]))
    interval = [round(_clip(point - half), 1), round(_clip(point + half), 1)]

    build = ctx["founder_score"].get("build_capability")
    pivot_capacity = (
        {
            "value": round(float(build["point"]), 1),
            "n": int(build["n"] or 0),
            "interval_low": round(float(build["interval_low"]), 1),
            "source": "founder_score.build_capability",
        }
        if build
        else {"value": None, "n": 0, "interval_low": None, "source": "no build_capability version at this asof"}
    )

    survives = "survives_as_is" if point >= 50.0 else "requires_pivot"
    threshold = float(ctx["thesis"]["conviction_threshold"])
    if survives == "requires_pivot" and pivot_capacity["interval_low"] is not None:
        carries = pivot_capacity["interval_low"] >= threshold
        reading = (
            f"Idea fails as-is. This is a pivot bet on the person — and the build-capability "
            f"lower bound of {pivot_capacity['interval_low']} "
            f"{'clears' if carries else 'does not clear'} the {threshold} gate, "
            f"so the person {'can' if carries else 'cannot yet be said to'} carry it."
        )
    elif survives == "requires_pivot":
        reading = (
            "Idea fails as-is and there is no build-capability version at this asof, so the "
            "pivot question is unanswered rather than answered optimistically."
        )
    else:
        reading = "The idea survives scrutiny as stated at this asof."

    return {
        "axis": "idea_vs_market",
        "value": point,
        "interval": interval,
        "n": n_terms,
        "prior_weight": round(1.0 - w, 3),
        "categorical": False,
        "output_type": survives,
        "survives_as_is": survives,
        "team_pivot_capacity": pivot_capacity,
        "terms": terms,
        "absence": absence,
        "observation_ids": used_obs,
        "claim_ids": used_claims,
        "reading": reading,
        "rationale": (
            f"{n_terms} scored input(s) at this asof against a {market['label'].upper()} market "
            f"read. Prior weight {round((1.0 - w) * 100)}%. The pivot clause reads build "
            f"capability out of Memory — the one declared cross-axis link in the system."
        ),
    }


# --------------------------------------------------------------------------- #
# the three axes at ONE instant — the function the trend calls four times
# --------------------------------------------------------------------------- #

def score_axes_at(
    asof: str,
    opportunity: dict[str, Any],
    *,
    exclude_priors_from: Iterable[str] = (),
) -> dict[str, Any]:
    """All three axes as they stood at ``asof``. No trend here — trend needs four."""
    ctx = _context(asof, opportunity, exclude_priors_from=exclude_priors_from)
    founder = score_founder_axis(ctx)
    market = score_market_axis(ctx)
    idea = score_idea_vs_market_axis(ctx, market)
    return {
        "asof": asof,
        "opportunity_id": ctx["opportunity_id"],
        "sector": ctx["sector"],
        "n_observations": len(ctx["observations"]),
        "founder": founder,
        "market": market,
        "idea_vs_market": idea,
        "thesis": ctx["thesis"],
    }


# --------------------------------------------------------------------------- #
# disagreement — named, never resolved, never averaged away
# --------------------------------------------------------------------------- #

def _stance_of(axis: dict[str, Any], threshold: float) -> str:
    """Band a numeric axis into the same three words the Market axis uses.

    Comparing stances is not averaging values: nothing is added, nothing is
    divided, and no number crosses between axes. The bands hang off the active
    thesis's conviction threshold, so re-configuring the fund re-bands the board.
    """
    if axis.get("categorical"):
        return str(axis["label"])
    value = axis.get("value")
    if value is None:
        return "unknown"
    if value < threshold - 10.0:
        return "bear"
    if value > threshold + 10.0:
        return "bullish"
    return "neutral"


_STANCE_RANK = {"bear": 0, "neutral": 1, "bullish": 2, "unknown": 1}
_AXIS_LABEL = {"founder": "Founder", "market": "Market", "idea_vs_market": "Idea-vs-Market"}


def disagreement(scored: dict[str, Any]) -> dict[str, Any]:
    """AXES DISAGREE, with the binding axis and the dissenting one named."""
    threshold = float(scored["thesis"]["conviction_threshold"])
    stances = {a: _stance_of(scored[a], threshold) for a in AXES}
    disagree = len(set(stances.values())) > 1

    binding = min(AXES, key=lambda a: (_STANCE_RANK[stances[a]], a))
    dissent = None
    if disagree:
        others = [a for a in AXES if stances[a] != stances[binding]]
        dissent = max(others, key=lambda a: (_STANCE_RANK[stances[a]], a))

    def describe(axis_key: str) -> str:
        axis = scored[axis_key]
        if axis.get("categorical"):
            return (
                f"{_AXIS_LABEL[axis_key]} is {axis['label'].upper()} at n={axis['n']}. "
                f"Nothing on the other axes offsets it, because we do not offset axes."
            )
        return (
            f"{_AXIS_LABEL[axis_key]} axis {axis['value']} "
            f"[{axis['interval'][0]}, {axis['interval'][1]}], "
            f"{axis.get('trend', 'trend not computed')}, n={axis['n']}."
        )

    headline = None
    if disagree:
        parts = ", ".join(f"{_AXIS_LABEL[a]} {stances[a]}" for a in AXES)
        tail = ""
        if scored["idea_vs_market"].get("output_type") == "requires_pivot":
            tail = " This is a pivot bet on the person."
        headline = (
            f"AXES DISAGREE — {parts}.{tail} We don't average them and we don't resolve it."
        )

    return {
        "axes_disagree": disagree,
        "axes_disagree_headline": headline,
        "stances": stances,
        "binding_axis": binding,
        "binding_axis_reason": describe(binding),
        "dissenting_axis": dissent,
        "dissenting_axis_reason": describe(dissent) if dissent else None,
        "stance_band_note": (
            f"bear < {threshold - 10.0} · neutral · bullish > {threshold + 10.0}, "
            f"banded off the active thesis conviction threshold of {threshold}. "
            "Stances are compared; values are not."
        ),
    }


# --------------------------------------------------------------------------- #
# the whole opportunity: four asof re-scores, three trends, one disagreement
# --------------------------------------------------------------------------- #

def score_opportunity(
    opportunity_id: str,
    asof: str = DEFAULT_ASOF,
    *,
    exclude_priors_from: Iterable[str] = (),
) -> dict[str, Any]:
    """Score at asof-90 / -60 / -30 / 0 through the identical code path."""
    c = store.conn()
    opportunity = c.execute(
        "SELECT * FROM opportunity WHERE opportunity_id = ?", (opportunity_id,)
    ).fetchone()
    if opportunity is None:
        raise store.LedgerViolation(f"No opportunity '{opportunity_id}'.")

    anchor = parse_iso(to_iso(asof))
    slices: list[dict[str, Any]] = []
    for days in TREND_OFFSETS_DAYS:
        stamp = to_iso(anchor + timedelta(days=days))
        scored = score_axes_at(stamp, opportunity, exclude_priors_from=exclude_priors_from)
        scored["offset_days"] = days
        scored["label"] = "now" if days == 0 else f"{days}d"
        slices.append(scored)

    current = slices[-1]
    out: dict[str, Any] = {
        "opportunity_id": opportunity_id,
        "person_id": opportunity["person_id"],
        "org_id": opportunity["org_id"],
        "sector": current["sector"],
        "asof": current["asof"],
        "asof_slices": [
            {"label": s["label"], "asof": s["asof"], "n_observations": {"value": s["n_observations"], "n": s["n_observations"]}}
            for s in slices
        ],
        "axes": {},
    }

    for axis_key in AXES:
        axis = dict(current[axis_key])
        points = []
        for s in slices:
            a = s[axis_key]
            series_value = a["stance_index"] if a.get("categorical") else a["value"]
            # An axis with no inputs at all at that instant is not a zero; it is
            # a point that does not exist, and it is dropped from the fit.
            if a["n"] == 0:
                series_value = None
            points.append(
                {
                    "label": s["label"],
                    "asof": s["asof"],
                    "offset_days": s["offset_days"],
                    "value": series_value,
                    "n": a["n"],
                    # every plotted point clicks through to the rows it was
                    # computed from — at THAT asof, not at the anchor
                    "observation_ids": a.get("observation_ids", []),
                    "claim_ids": a.get("claim_ids", []),
                }
            )
        scale = 30.0
        trend = _trend_from_series(points, scale_days=scale)
        axis.update(
            {
                "trend": trend["trend"],
                "trend_band": trend["trend_band"],
                "trend_slope": trend["trend_slope"],
                "n_trend_points": trend["n_trend_points"],
                "trend_note": trend["trend_note"],
                "trend_basis": trend["trend_basis"]
                + (" on the bear/neutral/bullish ordinal" if axis.get("categorical") else " on the 0-100 axis"),
                "trend_points": trend["trend_points"],
            }
        )
        out["axes"][axis_key] = axis

    out.update(disagreement({**{a: out["axes"][a] for a in AXES}, "thesis": current["thesis"]}))
    out["thesis"] = {
        "conviction_threshold": current["thesis"]["conviction_threshold"],
        "max_interval_width": current["thesis"]["max_interval_width"],
        "risk_appetite": current["thesis"]["risk_appetite"],
    }
    return out


# --------------------------------------------------------------------------- #
# MVP element 6 — the axis feeds back into Memory
# --------------------------------------------------------------------------- #

def writeback_market_prior(scored: dict[str, Any]) -> dict[str, Any]:
    """Append a ``sector_prior`` row so the NEXT company in this sector inherits it.

    Append-only, like everything else: if this verdict has already been written
    back at this asof the row is left alone and nothing is rewritten. A second
    run of this module therefore does not stack the sector down twice.
    """
    market = scored["axes"]["market"]
    sector = scored["sector"]
    opp_id = scored["opportunity_id"]
    if not sector:
        return {"written": False, "reason": "opportunity carries no sector"}

    own_index = round(market["stance_index"] - float(market["sector_prior"]["value"]), 3)
    own_n = market["n"] - market["sector_prior"]["n"]
    if own_n <= 0:
        return {
            "written": False,
            "reason": (
                "verdict carries no market evidence of its own (own n=0) — it IS the sector "
                "prior, and a prior that writes itself back would compound into a fact"
            ),
        }

    c = store.conn()
    existing = c.execute(
        "SELECT sector_prior_id FROM sector_prior WHERE sector = ? AND axis = 'market' "
        "AND written_by_opportunity = ? AND observed_at <= ?",
        (sector, opp_id, scored["asof"]),
    ).fetchone()
    if existing:
        return {
            "written": False,
            "reason": "already written back — append-only, so it is not written twice",
            "sector_prior_id": existing["sector_prior_id"],
        }

    shift = round(SECTOR_PRIOR_LR * own_index, 3)
    row_id = f"sp_{uuid.uuid4().hex[:12]}"
    append_row(
        "sector_prior",
        {
            "sector_prior_id": row_id,
            "sector": sector,
            "axis": "market",
            "prior_shift": shift,
            "categorical_value": market["label"],
            "n": market["n"],
            "written_by_opportunity": opp_id,
            "reason": (
                f"Market verdict {market['label'].upper()} for {opp_id} at {scored['asof']} "
                f"on {market['n']} row(s), own stance index {own_index}. Learning rate "
                f"{SECTOR_PRIOR_LR}, so the next company in {sector} starts from a reference "
                f"class shifted by {shift}."
            ),
            "observed_at": scored["asof"],
        },
        connection=c,
    )
    store.commit()
    return {
        "written": True,
        "sector_prior_id": row_id,
        "sector": sector,
        "prior_shift": shift,
        "categorical_value": market["label"],
        "n": market["n"],
    }


# --------------------------------------------------------------------------- #
# render — the shape export_demo.py adopts with no frontend change
# --------------------------------------------------------------------------- #

def _render_axis(axis: dict[str, Any]) -> dict[str, Any]:
    """Exactly the keys web/public/demo.json already carries, plus receipts."""
    # `n` is emitted immediately after `value` in both branches, before any
    # nested object, so export_demo.py's line-based n-audit — which scans from
    # `"value":` to the next `}` looking for `"n"` — sees it wherever the
    # formatter chooses to break lines. Every number carries its n.
    common = {
        "trend": axis["trend"],
        "trend_band": axis["trend_band"],
        "n_trend_points": axis["n_trend_points"],
        "trend_note": axis["trend_note"],
        "trend_basis": axis["trend_basis"],
        "trend_points": axis["trend_points"],
        "prior_weight": axis["prior_weight"],
        "rationale": axis["rationale"],
    }
    if axis.get("categorical"):
        return {
            "value": None,
            "interval": None,
            "n": axis["n"],
            "label": axis["label"],
            "stance": axis["stance"],
            "categorical": True,
            "value_blocked_reason": axis["value_blocked_reason"],
            "stance_index": axis["stance_index"],
            "stance_index_note": axis["stance_index_note"],
            "terms": axis["terms"],
            "sector_prior": axis["sector_prior"],
            **common,
        }
    out = {
        "value": axis["value"],
        "interval": axis["interval"],
        "n": axis["n"],
        **common,
        "reference_class": axis.get("reference_class"),
        "inputs": axis.get("inputs"),
        "absence": axis.get("absence"),
    }
    if axis["axis"] == "idea_vs_market":
        out.update(
            {
                "output_type": axis["output_type"],
                "team_pivot_capacity": axis["team_pivot_capacity"],
                "reading": axis["reading"],
                "terms": axis["terms"],
            }
        )
    return out


def render(asof: str = DEFAULT_ASOF, *, writeback: bool = True) -> dict[str, Any]:
    """Render-ready: ``people.<id>.axes`` and the opportunity axis fields.

    Opportunities are scored in the order they were opened, which is what makes
    the Memory writeback observable: the first company's Market verdict is in the
    sector prior by the time the second company in that sector is scored.

    ``writeback=True`` appends ``sector_prior`` rows as a side effect — that IS
    MVP element 6. Callers that only want to read (``export_demo.py``, say) pass
    ``writeback=False`` and get the identical scores with no ledger write.
    """
    opportunities = ledger.list_opportunities(asof)
    people: dict[str, Any] = {}
    opps: dict[str, Any] = {}
    writebacks: list[dict[str, Any]] = []

    for opp in opportunities:
        scored = score_opportunity(opp["opportunity_id"], asof)
        axes = {a: _render_axis(scored["axes"][a]) for a in AXES}

        if opp["person_id"]:
            people[opp["person_id"]] = {
                "axes": axes,
                "axes_disagree": scored["axes_disagree"],
                "axes_disagree_headline": scored["axes_disagree_headline"],
            }
        opps[opp["opportunity_id"]] = {
            "opportunity_id": opp["opportunity_id"],
            "person_id": opp["person_id"],
            "sector": scored["sector"],
            "asof": scored["asof"],
            "asof_slices": scored["asof_slices"],
            "axes": axes,
            "axes_disagree": scored["axes_disagree"],
            "axes_disagree_headline": scored["axes_disagree_headline"],
            "binding_axis": scored["binding_axis"],
            "binding_axis_reason": scored["binding_axis_reason"],
            "dissenting_axis": scored["dissenting_axis"],
            "dissenting_axis_reason": scored["dissenting_axis_reason"],
            "stance_band_note": scored["stance_band_note"],
        }
        if writeback:
            writebacks.append({"opportunity_id": opp["opportunity_id"], **writeback_market_prior(scored)})

    return {
        "asof": asof,
        "people": people,
        "opportunities": opps,
        "sector_prior_writebacks": writebacks,
        "no_averaged_axes": (
            "Three axes, three separate objects, no averaged value in this payload. "
            "Market carries value=None by construction so the three cannot be combined."
        ),
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _fmt_axis(key: str, axis: dict[str, Any]) -> str:
    band = axis["trend_band"]
    band_txt = f"band [{band[0]}, {band[1]}]/30d" if band else "band n/a"
    trend = f"{axis['trend']} · {band_txt} · {axis['n_trend_points']}pts"
    if axis.get("categorical"):
        head = f"{axis['label'].upper():<9} (value=None, categorical)"
    else:
        head = f"{axis['value']:<9} [{axis['interval'][0]}, {axis['interval'][1]}]"
    return f"  {_AXIS_LABEL[key]:<15} {head}  n={axis['n']:<3} prior_weight={axis['prior_weight']:<6} {trend}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Three axes, never averaged.")
    parser.add_argument("--asof", default=DEFAULT_ASOF)
    parser.add_argument("--json", action="store_true", help="emit the render-ready dict")
    parser.add_argument("--no-writeback", action="store_true")
    args = parser.parse_args(argv)

    store.open_ledger()  # no reset, ever — four agents share this ledger
    asof = to_iso(args.asof)

    payload = render(asof, writeback=not args.no_writeback)
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
        return 0

    print(f"THREE AXES · asof {asof} · {store.count_observations(asof)} observations visible")
    print("no averaged value anywhere in this output — Market has none to average\n")

    for opp_id, block in payload["opportunities"].items():
        print("=" * 78)
        print(f"{opp_id}  ({block['sector']})  person={block['person_id']}")
        print("-" * 78)
        for key in AXES:
            print(_fmt_axis(key, block["axes"][key]))
        idea = block["axes"]["idea_vs_market"]
        print(f"  {'':<15} idea verdict: {idea['output_type']} · {idea['reading']}")
        print()
        if block["axes_disagree"]:
            print(f"  {block['axes_disagree_headline']}")
        else:
            print("  Axes agree at this asof.")
        print(f"  binding   : {block['binding_axis']} — {block['binding_axis_reason']}")
        print(f"  dissenting: {block['dissenting_axis']} — {block['dissenting_axis_reason']}")
        print(f"  {block['stance_band_note']}")
        print()
        print("  TREND — the same scorer at four asof instants, not one score redrawn:")
        for key in AXES:
            axis = block["axes"][key]
            print(f"    {_AXIS_LABEL[key]}:")
            for p in axis["trend_points"]:
                val = "—" if p["value"] is None else f"{p['value']:>7}"
                ids = list(p["observation_ids"]) + list(p["claim_ids"])
                receipt = f"{len(ids)} source row(s)" + (f", first {ids[0]}" if ids else "")
                print(f"      {p['label']:<5} {p['asof']}  value={val}  n={p['n']:<3} {receipt}")
            print(f"      -> {axis['trend']}: {axis['trend_note']}")
        print()

    # ------------------------------------------------------------------ #
    # MVP element 6, demonstrated rather than asserted
    # ------------------------------------------------------------------ #
    print("=" * 78)
    print("AXIS -> MEMORY WRITEBACK (MVP element 6)")
    print("-" * 78)
    for wb in payload["sector_prior_writebacks"]:
        if wb.get("written"):
            print(f"  {wb['opportunity_id']:<16} appended sector_prior {wb['sector_prior_id']} · "
                  f"{wb['sector']} · market={wb['categorical_value']} · shift={wb['prior_shift']} · n={wb['n']}")
        else:
            print(f"  {wb['opportunity_id']:<16} no new row — {wb['reason']}")

    ordered = list(payload["opportunities"].values())
    by_sector: dict[str, list[dict[str, Any]]] = {}
    for block in ordered:
        by_sector.setdefault(block["sector"] or "unknown", []).append(block)

    for sector, blocks in by_sector.items():
        if len(blocks) < 2:
            continue
        first, second = blocks[0], blocks[1]
        print()
        print(f"  Second company in '{sector}' scoring off the updated prior:")
        before = score_opportunity(
            second["opportunity_id"], asof, exclude_priors_from=[first["opportunity_id"]]
        )
        after = score_opportunity(second["opportunity_id"], asof)
        bm, am = before["axes"]["market"], after["axes"]["market"]
        print(f"    {second['opportunity_id']} market BEFORE {first['opportunity_id']}'s verdict: "
              f"{bm['label'].upper():<8} index={bm['stance_index']:<7} n={bm['n']} "
              f"(sector_prior {bm['sector_prior']['value']}, n={bm['sector_prior']['n']})")
        print(f"    {second['opportunity_id']} market AFTER  {first['opportunity_id']}'s verdict: "
              f"{am['label'].upper():<8} index={am['stance_index']:<7} n={am['n']} "
              f"(sector_prior {am['sector_prior']['value']}, n={am['sector_prior']['n']})")
        changed = (bm["label"] != am["label"]) or (bm["stance_index"] != am["stance_index"])
        print(f"    -> reference class {'MOVED' if changed else 'unchanged'}"
              + (f": {bm['label']} -> {am['label']}" if bm["label"] != am["label"] else ""))
        print(f"    -> {am['rationale']}")
        # the knock-on: Idea-vs-Market reads the market stance, so it moves too
        bi, ai = before["axes"]["idea_vs_market"], after["axes"]["idea_vs_market"]
        print(f"    -> knock-on, Idea-vs-Market {bi['value']} ({bi['output_type']}) "
              f"-> {ai['value']} ({ai['output_type']})")

    print()
    print("=" * 78)
    text = json.dumps(payload, default=str).lower()
    banned = [t for t in ("composite", "overall_score", "blended", "average_score") if t in text]
    print(f"self-audit · banned tokens in payload: {banned or 'none'}")
    print(f"self-audit · market 'value' fields: "
          f"{sorted({str(b['axes']['market']['value']) for b in payload['opportunities'].values()})}")
    print(f"self-audit · observations still in ledger at asof: {store.count_observations(asof)}")
    return 1 if banned else 0


if __name__ == "__main__":
    raise SystemExit(main())
