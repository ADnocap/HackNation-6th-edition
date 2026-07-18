"""B2 — the per-claim trust engine. Posterior log-odds, itemized.

TRUST IS PER CLAIM. There is no company-level trust score in this system, no
company-level trust column in the schema, and no function in this module that
will produce one. "LedgerLine is 71% trustworthy" is not a sentence Counterproof
can emit, because a company whose revenue is fabricated and whose incorporation
is genuine does not have an average — it has two facts, and averaging them
destroys exactly the one an investor needs.

Four states, from ``db/schema.sql``: ``verified`` / ``unverified`` /
``contradicted`` / ``absent_but_expected``.

WHY THE ARITHMETIC IS PRINTED
-----------------------------
Any language model will emit ``0.87`` for a claim, and it will sound confident,
and there is no way to check it. The difference here is not that our number is
better — it is that our number **decomposes**. Every claim's score is a sum of
named terms, each term carrying the source class it came from, the published
weight for that source class, its own contribution, and the running total. A
judge can add the column up by hand. That is the whole product:

    −1.2 + 0.6 − 2.8 − 1.3 = −4.7

THE SOURCE RELIABILITY TABLE
----------------------------
:data:`SOURCE_RELIABILITY` is hand-set, published in advance, and defended row by
row. Nothing in it was learned and nothing in it came out of a language model.
It is persisted to the ``source_reliability`` table so it is inspectable in the
database rather than buried in a constant, and :func:`print_reliability_table`
puts it on screen.

The row that carries the argument is ``self_report = −1.2``. A founder asserting
their own metric is **negative evidence, not neutral evidence** — it is the
weakest signal in the system and it moves the posterior DOWN, so a claim with
nothing behind it but the deck starts underwater and has to be rescued by
something observable. Most tools treat the deck as the base case and search for
confirmation. Inverting that sign is the entire posture of the product.

Run it::

    uv run python -m worker.scoring.trust
"""

from __future__ import annotations

import math
import sys
from typing import Any, Iterable

from worker import ledger, store
from worker.scoring import manifest as _manifest

# --------------------------------------------------------------------------- #
# THE TABLE. Hand-set. Published. Defended line by line.
# --------------------------------------------------------------------------- #

SOURCE_RELIABILITY: tuple[dict[str, Any], ...] = (
    {
        "source_class": "self_report",
        "log_odds": -1.2,
        "rationale": (
            "A founder asserting their own metric is the weakest evidence in the "
            "system. Negative, not zero — a claim backed only by the deck should "
            "start below even odds and have to be rescued by something observable."
        ),
    },
    {
        "source_class": "interview",
        "log_odds": 0.0,
        "rationale": (
            "Neutral prior. Interview and elicitation content is scored on atom "
            "density and verified-pointer yield, never on the fact that it was said."
        ),
    },
    {
        "source_class": "forum_post",
        "log_odds": 0.0,
        "rationale": (
            "Neutral. We score the text for lived domain exposure, never the karma. "
            "Upvotes are a popularity measure and would re-import the network gate."
        ),
    },
    {
        "source_class": "press",
        "log_odds": 0.2,
        "rationale": (
            "Barely positive. Most early-stage press is a rewritten founder "
            "self-report with a byline on it, so it is only marginally more than the "
            "self-report we already counted."
        ),
    },
    {
        "source_class": "code_host",
        "log_odds": 0.8,
        "rationale": (
            "First-commit dates and cadence only. Confirmation, never discovery — "
            "and never stars or followers, which measure attention rather than work."
        ),
    },
    {
        "source_class": "preprint",
        "log_odds": 0.9,
        "rationale": "Dated, versioned, publicly timestamped and hard to backdate.",
    },
    {
        "source_class": "third_party_observable",
        "log_odds": 1.1,
        "rationale": (
            "A live endpoint, a dated changelog, a team page. Costly to fake, cheap "
            "to check, and it exists whether or not anyone was watching."
        ),
    },
    {
        "source_class": "registry_filing",
        "log_odds": 2.4,
        "rationale": (
            "USPTO and incorporation records. Perjury risk attaches to the filing, "
            "which is a stronger guarantee than any reputational one. Strongest row "
            "in the table."
        ),
    },
)

RELIABILITY: dict[str, float] = {
    r["source_class"]: float(r["log_odds"]) for r in SOURCE_RELIABILITY
}

#: Thresholds, matching ``claim.threshold_verified`` / ``threshold_contradicted``.
#: ±2.0 log-odds is roughly 88% / 12% posterior. Set once, applied everywhere,
#: never tuned per claim — a threshold that moves per claim is not a threshold.
THRESHOLD_VERIFIED = 2.0
THRESHOLD_CONTRADICTED = -2.0

#: High / Medium / Low is what a non-technical reader sees by default. The
#: log-odds number is one click down and never the first thing on screen.
CONFIDENCE_MAPPING = {
    "high": "|log-odds| >= 2.0",
    "medium": "0.5 <= |log-odds| < 2.0",
    "low": "|log-odds| < 0.5",
    "note": (
        "High/Medium/Low is the default render for a non-technical reader. The "
        "log-odds number is one click down, never the first thing shown."
    ),
}

MINUS = "−"  # U+2212 MINUS SIGN, not a hyphen. It is a number, not a dash.


# --------------------------------------------------------------------------- #
# formatting
# --------------------------------------------------------------------------- #

def _q(value: Any, n: Any) -> dict[str, Any]:
    return {"value": value, "n": n}


def _fmt(v: float) -> str:
    return f"{MINUS}{abs(v):.1f}" if v < 0 else f"{v:.1f}"


def arithmetic_string(values: list[float], total: float) -> str:
    """``−1.2 + 0.6 − 2.8 − 1.3 = −4.7`` — the line a judge can check by hand."""
    if not values:
        return f"no terms at this asof = {_fmt(total)}"
    parts = [_fmt(values[0])]
    for v in values[1:]:
        parts.append(("+ " if v >= 0 else f"{MINUS} ") + f"{abs(v):.1f}")
    return " ".join(parts) + f" = {_fmt(total)}"


def posterior(log_odds: float) -> float:
    """Logistic. The only place a probability is produced in this module."""
    return round(1.0 / (1.0 + math.exp(-log_odds)), 3)


def confidence_band(log_odds: float) -> str:
    a = abs(log_odds)
    if a >= 2.0:
        return "high"
    if a >= 0.5:
        return "medium"
    return "low"


# --------------------------------------------------------------------------- #
# the table: persist it, render it, print it
# --------------------------------------------------------------------------- #

def persist_source_reliability(*, connection: Any = None) -> dict[str, Any]:
    """Write the hand-set table into ``source_reliability`` so it is inspectable.

    ``source_class`` is the primary key and the table is reference data, so rows
    already present are left alone rather than re-inserted — appending a
    duplicate would fail the unique constraint, and rewriting one would be a
    mutation. Reports what it appended and what was already there.
    """
    c = connection or store.conn()
    existing = {
        r["source_class"]
        for r in c.execute("SELECT source_class FROM source_reliability").fetchall()
    }
    appended: list[str] = []
    for row in SOURCE_RELIABILITY:
        if row["source_class"] in existing:
            continue
        ledger.append_row(
            "source_reliability",
            {
                "source_class": row["source_class"],
                "log_odds": row["log_odds"],
                "rationale": row["rationale"],
                "set_by": "hand_set",
            },
            connection=c,
        )
        appended.append(row["source_class"])
    ledger.commit()
    return {
        "appended": appended,
        "already_present": sorted(existing),
        "n": len(SOURCE_RELIABILITY),
    }


def reliability_table() -> dict[str, Any]:
    """Render-ready, matching ``demo.json :: honesty.reliability_table`` exactly."""
    rows = [dict(r) for r in SOURCE_RELIABILITY]
    return {
        "title": "Source reliability — published in advance, defended line by line",
        "plain_line": (
            "These weights are ours. We set them by hand, we print them, and we will "
            "argue any row. Nothing here was learned and nothing here came out of a "
            "language model."
        ),
        "rows": rows,
        "n_rows": _q(len(rows), len(rows)),
        "thresholds": {
            "verified": THRESHOLD_VERIFIED,
            "contradicted": THRESHOLD_CONTRADICTED,
        },
        "confidence_mapping": dict(CONFIDENCE_MAPPING),
        "set_by": "hand_set",
    }


def print_reliability_table() -> None:
    t = reliability_table()
    print()
    print("=" * 94)
    print("SOURCE RELIABILITY — hand-set, published in advance, defended line by line")
    print("=" * 94)
    print(t["plain_line"])
    print()
    print(f"{'source class':<24} {'log-odds':>9}   rationale")
    print("-" * 94)
    for r in t["rows"]:
        print(f"{r['source_class']:<24} {r['log_odds']:>+9.1f}   {r['rationale'][:60]}")
        rest = r["rationale"][60:]
        while rest:
            print(f"{'':<24} {'':>9}   {rest[:60]}")
            rest = rest[60:]
    print("-" * 94)
    print(
        f"verified at >= {THRESHOLD_VERIFIED:+.1f} log-odds · "
        f"contradicted at <= {THRESHOLD_CONTRADICTED:+.1f} · "
        f"high/medium/low: {CONFIDENCE_MAPPING['high']}, "
        f"{CONFIDENCE_MAPPING['medium']}, {CONFIDENCE_MAPPING['low']}"
    )
    print(
        "The row carrying the argument is self_report = -1.2. A founder asserting "
        "their own\nmetric is NEGATIVE evidence, not neutral. Most tools treat the "
        "deck as the base case\nand search for confirmation; inverting that sign is "
        "the posture of the whole product."
    )


# --------------------------------------------------------------------------- #
# scoring one claim
# --------------------------------------------------------------------------- #

def _term_label(ev: dict[str, Any]) -> str:
    kind = ev.get("kind")
    sc = ev.get("source_class")
    finding = (ev.get("finding") or "").strip().rstrip(".")
    artifact = ev.get("artifact_type") or ""
    prior_p, prior_n = ev.get("findability_prior"), ev.get("findability_n")

    if kind == "expected_absent":
        if not ev.get("expected"):
            return "Not expected for this profile — not penalised"
        tail = (
            f" (P={float(prior_p):.2f}, n={prior_n})" if prior_p is not None else ""
        )
        what = finding or artifact or "predicted artifact"
        return f"Expected and absent — {what}{tail}"
    if sc == "self_report":
        # The finding on a self-report row usually restates "founder self-report";
        # repeating it in the label reads as a stutter in the Receipt modal.
        extra = "" if finding.lower().startswith("founder self-report") else finding
        slide = ev.get("page_number") or ev.get("source_slide")
        label = "Prior — founder self-report"
        if slide:
            label += f", deck slide {slide}"
        return label + (f", {extra}" if extra else "")
    if kind == "contradicting":
        return f"Direct contradiction — {finding or artifact or sc}"
    return f"Corroborating — {finding or artifact or sc}"


def _term_n(ev: dict[str, Any]) -> Any:
    if ev.get("findability_n") is not None:
        return ev["findability_n"]
    if ev.get("source_class") == "self_report":
        return None
    return 1


def _delta_for(ev: dict[str, Any]) -> tuple[float, str]:
    """The term's contribution, and how it was arrived at.

    Prefers the delta the verifier recorded on the evidence row — that row is the
    ledger's own account of what the fetch was worth, and overriding it here
    would make the stored evidence and the rendered score disagree. Falls back to
    the published reliability table when the row carries no delta, which is where
    the table earns its keep rather than merely being printed.
    """
    stored = ev.get("log_odds_delta")
    sc = ev.get("source_class")
    if stored not in (None, 0.0):
        return float(stored), "ledger"
    if ev.get("kind") == "expected_absent":
        # Absence: zero unless it was expected AND penalised. This is the
        # asymmetry, and it is enforced here as well as in the manifest so no
        # code path can charge for a predicted absence.
        if ev.get("found") or not ev.get("expected") or not ev.get("penalised"):
            return 0.0, "absence_not_penalised"
        p = ev.get("findability_prior")
        if p is None:
            return 0.0, "absence_no_prior"
        lr = _manifest.likelihood_ratio(float(p), _manifest.P_FLOOR * 10)
        return float(lr["llr_absent"]), "likelihood_ratio"
    if sc in RELIABILITY:
        direction = -1.0 if ev.get("kind") == "contradicting" else 1.0
        base = RELIABILITY[sc]
        # A contradicting observation from a class we trust counts AGAINST the
        # claim with that class's weight; self-report keeps its own sign either
        # way, because a founder contradicting themselves is not a strong source
        # suddenly, it is the same weak source.
        return (base if sc == "self_report" else direction * abs(base)), "reliability_table"
    return 0.0, "unclassified"


def score_claim(
    claim: dict[str, Any],
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Accumulate posterior log-odds for ONE claim from its evidence rows.

    Returns the ``log_odds`` block the Receipt modal renders — ``terms`` with a
    running total, the ``sum``, the arithmetic string, the thresholds and a
    deterministic verdict sentence — plus the derived state, band and posterior.

    Degrades honestly. A claim with no evidence returns ``unverified`` with an
    explicitly wide interval and a stated reason; it never returns a verdict it
    did not earn.
    """
    ordered = sorted(
        evidence, key=lambda e: (e.get("ordinal") if e.get("ordinal") is not None else 99)
    )

    terms: list[dict[str, Any]] = []
    values: list[float] = []
    running = 0.0
    widen_total = 0.0

    for ev in ordered:
        delta, basis = _delta_for(ev)

        # THE INVARIANT, enforced at the scoring boundary as well as at the
        # manifest boundary. An absence the findability prior predicted may
        # widen the interval; it may never lower the score.
        if (
            ev.get("kind") == "expected_absent"
            and not ev.get("expected")
            and delta != 0.0
        ):
            raise AssertionError(
                f"evidence {ev.get('evidence_id')} charges {delta} log-odds for an "
                "unexpected absence. Absence the findability prior predicted must "
                "never lower the score."
            )

        running = round(running + delta, 4)
        widen_total += float(ev.get("interval_widen") or 0.0)
        sc = ev.get("source_class")
        terms.append(
            {
                "label": _term_label(ev),
                "source_class": sc,
                "value": round(delta, 2),
                "running_total": round(running, 2),
                "evidence_id": ev.get("evidence_id"),
                "n": _term_n(ev),
                # additive keys — the itemization a judge checks the row against
                "reliability": RELIABILITY.get(sc) if sc else None,
                "reliability_rationale": next(
                    (r["rationale"] for r in SOURCE_RELIABILITY if r["source_class"] == sc),
                    None,
                ),
                "kind": ev.get("kind"),
                "basis": basis,
                "interval_widen": round(float(ev.get("interval_widen") or 0.0), 2),
                "findability_prior": (
                    _q(round(float(ev["findability_prior"]), 2), ev.get("findability_n"))
                    if ev.get("findability_prior") is not None
                    else None
                ),
            }
        )
        values.append(round(delta, 2))

    total = round(sum(values), 2)

    # ---- state, in a fixed precedence -------------------------------------
    manifest_predicted = bool(claim.get("is_manifest_predicted"))
    only_absence = bool(ordered) and all(
        e.get("kind") == "expected_absent" for e in ordered
    )
    if manifest_predicted or only_absence:
        state = "absent_but_expected"
    elif total >= THRESHOLD_VERIFIED:
        state = "verified"
    elif total <= THRESHOLD_CONTRADICTED:
        state = "contradicted"
    else:
        state = "unverified"

    block: dict[str, Any] = {
        "terms": terms,
        "sum": total,
        "posterior_prob": None if state == "absent_but_expected" else posterior(total),
        "arithmetic_string": arithmetic_string(values, total),
        "threshold_verified": THRESHOLD_VERIFIED,
        "threshold_contradicted": THRESHOLD_CONTRADICTED,
        "verdict_sentence": _verdict_sentence(claim, state, total, terms, widen_total),
        "interval_widen_total": round(widen_total, 2),
        "n_terms": _q(len(terms), len(terms)),
        "computed_by": "closed_form_log_odds",
    }

    if not terms:
        block["arithmetic_string"] = (
            "no evidence rows at this asof — no arithmetic to show"
        )
        block["degraded_reason"] = (
            "Zero evidence rows visible at this asof. The claim stays UNVERIFIED "
            "with a maximally wide interval. An unverified claim is not a rejected "
            "one and it is not an accepted one — it is a claim we have not yet "
            "earned a verdict on, and saying so is the honest output."
        )

    return {
        "log_odds": block,
        "state": state,
        "confidence_band": confidence_band(total),
        "posterior_prob": block["posterior_prob"],
        "interval_widen_total": round(widen_total, 2),
        "n_evidence": len(ordered),
    }


def _verdict_sentence(
    claim: dict[str, Any],
    state: str,
    total: float,
    terms: list[dict[str, Any]],
    widen: float,
) -> str:
    """Deterministic. Templated from the terms, never generated by a model."""
    strongest = max(terms, key=lambda t: abs(t["value"]), default=None)
    driver = strongest["label"] if strongest else "no evidence"
    n_pos = sum(1 for t in terms if t["value"] > 0)
    n_neg = sum(1 for t in terms if t["value"] < 0)

    if state == "contradicted":
        keep = ""
        if n_pos:
            keep = (
                f" We found {n_pos} term{'s' if n_pos > 1 else ''} FOR this claim and "
                "kept them in the sum — dropping a corroborating term to make a "
                "cleaner story would be the same sin we are catching here."
            )
        return (
            f"Contradicted at {_fmt(total)}, past the {_fmt(THRESHOLD_CONTRADICTED)} "
            f"threshold. The binding term is: {driver}.{keep}"
        )
    if state == "verified":
        return (
            f"Verified at {_fmt(total)}, clearing the {_fmt(THRESHOLD_VERIFIED)} "
            f"threshold across {n_pos} supporting term{'s' if n_pos != 1 else ''}. "
            f"The strongest is: {driver}."
        )
    if state == "absent_but_expected":
        if abs(total) < 1e-9:
            return (
                "Absent, expected to be absent, not penalised. The findability prior "
                "predicted this absence for this reference class, so it costs exactly "
                "zero log-odds. This is the grey row."
            )
        return (
            f"Absent but expected. Contributes {_fmt(total)} and widens the interval "
            f"by {widen:.1f} points. It widens the interval; it does not lower the "
            "point estimate."
        )
    return (
        f"Unverified at {_fmt(total)} — between {_fmt(THRESHOLD_CONTRADICTED)} and "
        f"{_fmt(THRESHOLD_VERIFIED)}, so neither threshold is crossed. "
        f"{n_pos} term{'s' if n_pos != 1 else ''} for, {n_neg} against. "
        "Unverified is a real state here, not a rounding of 'probably fine'."
    )


# --------------------------------------------------------------------------- #
# render-ready output — the shape export_demo.py is refusing to adopt today
# --------------------------------------------------------------------------- #

def _render_evidence(ev: dict[str, Any]) -> dict[str, Any]:
    out = {
        "evidence_id": ev.get("evidence_id"),
        "kind": ev.get("kind"),
        "artifact_type": ev.get("artifact_type"),
        "found": bool(ev.get("found")),
        "expected": bool(ev.get("expected")),
        "penalised": bool(ev.get("penalised")),
        "source_class": ev.get("source_class"),
        "source_url": ev.get("source_url"),
        "final_url": ev.get("final_url"),
        "http_status": ev.get("http_status"),
        "fetched_at": ev.get("fetched_at"),
        "fetch_method": ev.get("fetch_method"),
        "verifier": ev.get("verifier"),
        "excerpt": ev.get("excerpt"),
        "finding": ev.get("finding"),
        "log_odds_delta": round(float(ev.get("log_odds_delta") or 0.0), 2),
        "interval_widen": round(float(ev.get("interval_widen") or 0.0), 2),
        "reliability": RELIABILITY.get(ev.get("source_class") or ""),
        "provenance_class": ev.get("provenance_class"),
    }
    if ev.get("findability_prior") is not None:
        out["findability_prior"] = _q(
            round(float(ev["findability_prior"]), 2), ev.get("findability_n")
        )
    return out


def _render_receipt(
    claim: dict[str, Any], evidence: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Left pane: what they said. Right panes: what we fetched.

    Built only when both halves genuinely exist. A receipt with an empty right
    pane is a screenshot of an assertion, which is the thing this product exists
    to stop showing people.
    """
    left_row = next(
        (e for e in evidence if e.get("source_class") == "self_report"), None
    )
    right_rows = [
        e for e in evidence if e.get("source_url") or e.get("http_status") is not None
    ]
    if left_row is None or not right_rows:
        return None

    return {
        "title": f"{claim.get('claim_type')} — {claim.get('claim_text')}",
        "left": {
            "kind": "deck_slide_crop" if claim.get("source_slide") else "self_report_excerpt",
            "source_class": "self_report",
            "label": (
                f"Deck slide {claim['source_slide']} — cropped region"
                if claim.get("source_slide")
                else "Founder self-report"
            ),
            "observed_at": left_row.get("observed_at"),
            "page": claim.get("source_slide"),
            "bbox": claim.get("source_bbox"),
            "excerpt": left_row.get("excerpt"),
            "provenance_class": left_row.get("provenance_class"),
            "provenance_badge": (
                "AUTHORED — this row was written by us, not received from a founder."
                if left_row.get("provenance_class") in ("synthetic", "fixture")
                else None
            ),
            "caption": (
                "The exact text the number was read from, with the timestamp that "
                "produced it. Not a paraphrase of the source — the source."
            ),
        },
        "right": [
            {
                "kind": "fetched_page",
                "label": e.get("artifact_type") or e.get("verifier") or "fetched page",
                "verifier": e.get("verifier"),
                "fetch_method": e.get("fetch_method"),
                "source_url": e.get("source_url"),
                "final_url": e.get("final_url"),
                "http_status": e.get("http_status"),
                "fetched_at": e.get("fetched_at"),
                "excerpt": e.get("excerpt"),
                "finding": e.get("finding"),
                "provenance_class": e.get("provenance_class"),
            }
            for e in right_rows
        ],
    }


def render_claim(
    claim: dict[str, Any],
    evidence: list[dict[str, Any]],
    asof: str,
) -> dict[str, Any]:
    """One claim, in the exact shape ``web/public/demo.json`` renders.

    ``export_demo.py :: _claims_are_renderable`` refuses ledger claims today
    because ``read_claims`` hands back flat table rows: ``log_odds_sum`` is a
    column, but the per-term breakdown, the evidence list and the receipt panes
    are nested structures a single row cannot hold. Producing exactly that nested
    shape is what this function is for.
    """
    scored = score_claim(claim, evidence)
    out: dict[str, Any] = {
        "claim_id": claim.get("claim_id"),
        "claim_type": claim.get("claim_type"),
        "claim_text": claim.get("claim_text"),
        "stated_value": claim.get("stated_value"),
        "stated_unit": claim.get("stated_unit"),
        "state": scored["state"],
        "confidence_band": scored["confidence_band"],
        "posterior_prob": scored["posterior_prob"],
        "is_material": bool(claim.get("is_material")),
        "is_manifest_predicted": bool(claim.get("is_manifest_predicted")),
        "memo_blocked": bool(claim.get("memo_blocked")),
        "asserted_at": claim.get("asserted_at"),
        "evaluated_at": claim.get("evaluated_at"),
        "asof": asof,
        "n_evidence": _q(len(evidence), len(evidence)),
        "log_odds": scored["log_odds"],
        "interval_widen_total": scored["interval_widen_total"],
        "evidence": [_render_evidence(e) for e in evidence],
    }
    if claim.get("source_slide") is not None:
        out["deck_slide"] = claim.get("source_slide")

    if out["state"] == "absent_but_expected":
        out["renders_as"] = "gap_row"
        out["posterior_blocked_reason"] = (
            "No posterior of its own. "
            + scored["log_odds"]["verdict_sentence"]
            + " It renders as a gap row in the memo, never as prose."
        )
    if out["state"] == "contradicted":
        out["memo_blocked"] = True
        out["memo_blocked_reason"] = (
            "Contradicted claims do not appear in the memo body. The memo renders "
            "from surviving claims only; this one appears in the bear case and "
            "nowhere else."
        )
    if not evidence and out["state"] != "absent_but_expected":
        out["memo_blocked"] = True
        out["memo_blocked_reason"] = (
            "Zero evidence rows. A claim with no evidence cannot render as memo "
            "prose — it renders as a gap row. That is a schema property, not a "
            "prompt instruction."
        )

    # The ledger's own stored verdict, kept beside the recomputed one. Where they
    # disagree it is ALWAYS because the claim row carries a `state` and a
    # `log_odds_sum` that no evidence row supports — an assertion, not a
    # derivation. We report the recomputed verdict and flag the gap rather than
    # adopting a number we cannot itemize: a score that cannot decompose into
    # named terms is the exact thing this engine exists to replace.
    stored_state = claim.get("state")
    stored_sum = claim.get("log_odds_sum")
    out["state_in_ledger"] = stored_state
    out["log_odds_sum_in_ledger"] = stored_sum
    if stored_state and stored_state != out["state"]:
        out["state_disagrees_with_ledger"] = True
        out["state_disagreement_reason"] = (
            f"claim.state='{stored_state}' with log_odds_sum={stored_sum}, but "
            f"{len(evidence)} evidence row(s) are visible at this asof, which sum "
            f"to {scored['log_odds']['sum']}. The stored verdict is not reproducible "
            "from the ledger, so the recomputed one — "
            f"'{out['state']}' — is what renders. Fix by appending the evidence "
            "rows that justified the stored number; never by trusting the column."
        )

    receipt = _render_receipt(claim, evidence)
    if receipt:
        out["receipt"] = receipt
    return out


def render_claims(
    asof: str,
    *,
    opportunity_id: str | None = None,
    person_id: str | None = None,
    connection: Any = None,
) -> list[dict[str, Any]]:
    """Every claim for an opportunity or a person, render-ready, read at ``asof``."""
    claims = ledger.read_claims(
        asof,
        opportunity_id=opportunity_id,
        person_id=person_id,
        connection=connection,
    )
    out = []
    for claim in claims:
        evidence = ledger.read_evidence(
            asof, claim_id=claim["claim_id"], connection=connection
        )
        out.append(render_claim(claim, evidence, asof))
    return out


def claim_distribution(claims: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """"6 verified / 5 unverified / 3 contradicted / 2 expected-but-absent".

    A DISTRIBUTION, never a mean. This function is the reason there is no
    ``company_trust_score`` anywhere in the codebase: the honest summary of a
    company's claims is the shape of the four buckets, and any single number
    collapsing them would hide the disagreement an investor is paying for.
    """
    claims = list(claims)
    counts = {k: 0 for k in ("verified", "unverified", "contradicted", "absent_but_expected")}
    for c in claims:
        counts[c.get("state", "unverified")] = counts.get(c.get("state", "unverified"), 0) + 1
    n = len(claims)
    return {
        "counts": counts,
        "n": n,
        "headline": " / ".join(f"{v} {k.replace('_', '-')}" for k, v in counts.items()),
        "is_mean": False,
        "note": (
            "A distribution, never a mean. Trust is per claim; there is no "
            "company-level trust score in this system and no column for one."
        ),
    }


# --------------------------------------------------------------------------- #
# printing
# --------------------------------------------------------------------------- #

def print_claim(rendered: dict[str, Any]) -> None:
    lo = rendered["log_odds"]
    print()
    print("-" * 94)
    print(
        f"{rendered['claim_id']}  [{rendered['state'].upper()}]  "
        f"{(rendered.get('claim_text') or '')[:64]}"
    )
    print("-" * 94)
    print(
        f"{'term':<58} {'source class':<22} {'Δ':>6} {'run':>6} {'n':>5}"
    )
    for t in lo["terms"]:
        print(
            f"{t['label'][:58]:<58} {str(t['source_class'] or '—'):<22} "
            f"{t['value']:>+6.1f} {t['running_total']:>+6.1f} "
            f"{('—' if t['n'] is None else t['n']):>5}"
        )
        if t.get("reliability") is not None:
            print(
                f"{'':<58} {'published weight ' + format(t['reliability'], '+.1f'):<22} "
                f"{'':>6} {'':>6} {'':>5}"
            )
    print()
    print(f"  {lo['arithmetic_string']}")
    print(
        f"  posterior={lo['posterior_prob']}  band={rendered['confidence_band']}  "
        f"verified>={lo['threshold_verified']:+.1f}  "
        f"contradicted<={lo['threshold_contradicted']:+.1f}  "
        f"interval widened by {lo['interval_widen_total']:.1f}"
    )
    print(f"  {lo['verdict_sentence']}")
    if rendered.get("posterior_blocked_reason"):
        print(f"  BLOCKED: {rendered['posterior_blocked_reason']}")
    if lo.get("degraded_reason"):
        print(f"  DEGRADED: {lo['degraded_reason']}")


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

    print(f"asof {asof} · {store.count_observations(asof)} observations visible")
    print_reliability_table()

    persisted = persist_source_reliability()
    print()
    print(
        f"source_reliability: {len(persisted['appended'])} appended, "
        f"{len(persisted['already_present'])} already present, "
        f"{persisted['n']} rows in the published table"
    )

    for opp in ledger.list_opportunities(asof):
        opp_id = opp["opportunity_id"]
        claims = render_claims(asof, opportunity_id=opp_id)
        dist = claim_distribution(claims)
        print()
        print("=" * 94)
        print(f"OPPORTUNITY {opp_id} — trust is PER CLAIM, never per company")
        print("=" * 94)
        print(f"  {dist['headline']}   (n={dist['n']})")
        print(f"  {dist['note']}")

        # Lead with the states that carry the argument.
        order = {"contradicted": 0, "absent_but_expected": 1, "verified": 2, "unverified": 3}
        for claim in sorted(claims, key=lambda c: (order.get(c["state"], 9), c["claim_id"])):
            if claim["log_odds"]["terms"]:
                print_claim(claim)

        empty = [c for c in claims if not c["log_odds"]["terms"]]
        if empty:
            print()
            print(f"  GRACEFUL DEGRADATION — {len(empty)} claim(s) with no evidence rows at this asof:")
            for c in empty:
                print(
                    f"    {c['claim_id']:<26} recomputed={c['state']:<12} "
                    f"ledger says={str(c.get('state_in_ledger')):<12} "
                    f"stored_sum={c.get('log_odds_sum_in_ledger')}"
                )
            print(f"    {empty[0]['log_odds']['degraded_reason']}")

        disagree = [c for c in claims if c.get("state_disagrees_with_ledger")]
        if disagree:
            print()
            print(
                f"  LEDGER DISAGREEMENT — {len(disagree)} claim(s) carry a stored "
                "state that no evidence row reproduces:"
            )
            print(f"    {disagree[0]['state_disagreement_reason']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
