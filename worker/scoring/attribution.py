"""B5 — leave-one-evidence-out attribution over the Founder Score.

    uv run python -m worker.scoring.attribution

WHY THIS IS MEASUREMENT AND NOT NARRATION
-----------------------------------------
:mod:`worker.scoring.founder_score` is closed-form arithmetic over ledger rows —
a weighted mean shrunk toward a reference class. No language model is anywhere in
the scoring path. That single fact is what makes this module possible: to find
out what one piece of evidence is worth, we DELETE IT AND RE-RUN THE SCORER, and
the answer is exact rather than a plausible-sounding story the model tells about
its own reasoning. The whole computation for a person is a few hundred
floating-point operations and finishes in well under a millisecond, so the CLI
prints how long it took — the timing is the proof that nothing was generated.

WHAT GETS DROPPED
-----------------
One INDEPENDENT EVIDENCE STREAM, not one ledger row. Seventeen fetches of the
same domain are one stream carrying seventeen rows; dropping them one at a time
would report seventeen deltas of nearly zero and hide the fact that the entire
domain signal is load-bearing. Each row of the waterfall names the stream, how
many ledger rows stand behind it, and what the score AND the interval become
without it.

READ THE INTERVAL COLUMN, NOT ONLY THE DELTA
--------------------------------------------
Removing evidence does two things at once: it moves the point estimate, and it
shrinks ``n``, which widens the interval and hands more of the number back to the
reference class. A stream with a delta near zero that widens the interval by ten
points was not useless — it was buying certainty rather than score, which is the
same distinction the Cold-Start Bench makes when it says the evidence bought
certainty, not a higher number.

The bottom row of every waterfall is the prior-only baseline: what this person
would score if we deleted everything we know about them. The distance between
that row and the top of the table is, exactly, how much our collection did.
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Any

from worker import ledger, store
from worker.scoring.founder_score import (
    COMPONENTS,
    Item,
    Population,
    fit_population,
    pick_demo_people,
    q,
    score_component,
)

LOO_CAPTION = (
    "Measured deltas from an exact closed-form recompute with each evidence stream "
    "removed and the scorer re-run — not the model narrating its own reasoning. The "
    "Founder Score is arithmetic over ledger rows, so dropping one stream and "
    "re-scoring is exact, and it is what produced every number in this table."
)

PLAIN_LINE = (
    "We deleted each piece of evidence in turn and re-ran the score. This is what "
    "each one is actually worth — measured, not asserted."
)


def attribute(
    pid: str,
    component: str,
    pop: Population,
) -> dict[str, Any]:
    """Drop each evidence stream, re-score, and report the exact delta.

    Returns the full score, one row per dropped stream sorted by magnitude, and
    the prior-only baseline that remains when everything is dropped.
    """
    started = time.perf_counter()
    full = score_component(pid, component, pop)
    items: list[Item] = list(full["items"])
    absences = full["absences"]

    prior_only = score_component(pid, component, pop, items=[], absences=absences)
    rows: list[dict[str, Any]] = []
    for idx, dropped in enumerate(items):
        kept = [it for j, it in enumerate(items) if j != idx]
        without = score_component(pid, component, pop, items=kept, absences=absences)
        rows.append(
            {
                "dropped": dropped.label,
                "evidence_id": dropped.key,
                "kind": dropped.kind,
                "n_rows": dropped.n_rows,
                "y": round(dropped.y, 4),
                "observed_at": dropped.observed_at,
                "source_class": dropped.source_class,
                "artifact_type": dropped.artifact_type,
                "claim_id": dropped.claim_id,
                "observation_ids": dropped.observation_ids[:8],
                "point_without": without["point"],
                "delta": round(full["point"] - without["point"], 2),
                "interval_without": without["interval"],
                "width_without": without["interval_width"],
                "width_delta": round(without["interval_width"] - full["interval_width"], 2),
                "prior_weight_without": without["prior_weight"],
                "n": without["n"],
                "state_without": f"n={without['n']}",
            }
        )
    rows.sort(key=lambda r: (-abs(r["delta"]), -abs(r["width_delta"])))
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    return {
        "person_id": pid,
        "component": component,
        "asof": pop.asof,
        "point": full["point"],
        "interval": full["interval"],
        "interval_width": full["interval_width"],
        "n": full["n"],
        "n_rows": full["n_rows"],
        "prior_weight": full["prior_weight"],
        "rows": rows,
        "prior_only": {
            "dropped": "everything — the reference class alone",
            "evidence_id": "prior_only",
            "point_without": prior_only["point"],
            "delta": round(full["point"] - prior_only["point"], 2),
            "interval_without": prior_only["interval"],
            "width_without": prior_only["interval_width"],
            "width_delta": round(
                prior_only["interval_width"] - full["interval_width"], 2
            ),
            "n": 0,
            "state_without": "class prior only",
        },
        "n_recomputes": len(items) + 2,
        "elapsed_ms": round(elapsed_ms, 3),
        "is_exact_recompute": True,
        "scorer": "closed-form; no language model in the scoring path",
    }


def _interpretation(att: dict[str, Any]) -> str:
    if not att["rows"]:
        return (
            "No evidence streams at this asof, so there is nothing to drop. The score "
            "is the reference class, and the interval says so."
        )
    top = att["rows"][0]
    widest = max(att["rows"], key=lambda r: r["width_delta"])
    rows_word = f"{top['n_rows']} ledger row" + ("" if top["n_rows"] == 1 else "s")
    if abs(top["delta"]) < 0.05:
        parts = [
            f"No single stream moves the point estimate here: dropping '{top['dropped']}' "
            f"({rows_word}) leaves the score at {att['point']} because this person's "
            "evidence and their reference class agree. What the evidence bought was the "
            f"interval — width {att['interval_width']:.1f} with it, "
            f"{top['width_without']:.1f} without. Certainty, not score, which is exactly "
            "the distinction the Cold-Start Bench draws."
        ]
    else:
        parts = [
            f"Dropping '{top['dropped']}' moves the score by {top['delta']:+.1f} points "
            f"({att['point']} -> {top['point_without']}), which makes it the load-bearing "
            f"evidence on this component. It stands on {rows_word}."
        ]
    if widest["evidence_id"] != top["evidence_id"] and widest["width_delta"] > 0.5:
        parts.append(
            f"'{widest['dropped']}' barely moves the point ({widest['delta']:+.1f}) but "
            f"widens the interval by {widest['width_delta']:+.1f} points — it was buying "
            "certainty, not score."
        )
    prior = att["prior_only"]
    if abs(prior["delta"]) < 0.05:
        parts.append(
            f"With everything removed the score stays at {prior['point_without']} on an "
            f"interval of width {prior['width_without']:.1f} (from "
            f"{att['interval_width']:.1f}): our collection bought "
            f"{prior['width_without'] - att['interval_width']:.1f} points of interval and "
            "confirmed the class rather than departing from it."
        )
    else:
        parts.append(
            f"With everything removed the score falls back to {prior['point_without']} on "
            f"an interval of width {prior['width_without']:.1f}: that gap is exactly what "
            "our collection contributed."
        )
    return " ".join(parts)


def attribution_block(
    pid: str,
    asof: str,
    *,
    pop: Population | None = None,
    connection: Any = None,
) -> dict[str, Any]:
    """Render-ready ``people.<id>.founder_score_attribution``.

    Row shape deliberately mirrors the per-claim ``loo_waterfall`` the frontend
    already renders (``dropped`` / ``evidence_id`` / ``delta`` / ``state_without``
    / ``n``), so the same component draws it. The one difference is the units:
    these deltas are Founder Score points, so the row carries ``point_without``
    where a claim row carries ``log_odds_without``.
    """
    pop = pop or fit_population(asof, connection=connection)
    block: dict[str, Any] = {
        "plain_line": PLAIN_LINE,
        "loo_caption": LOO_CAPTION,
        "asof": pop.asof,
        "units": "founder score points (0-100)",
    }
    for comp in COMPONENTS:
        att = attribute(pid, comp, pop)
        block[comp] = {
            "point": q(att["point"], att["n"]),
            "interval": att["interval"],
            "n": q(att["n"], att["n"]),
            "n_ledger_rows": q(att["n_rows"], att["n"]),
            "prior_weight": q(att["prior_weight"], att["n"]),
            "loo_waterfall": att["rows"],
            "prior_only": att["prior_only"],
            "interpretation": _interpretation(att),
            "recomputes": q(att["n_recomputes"], att["n_recomputes"]),
            "elapsed_ms": q(att["elapsed_ms"], att["n_recomputes"]),
        }
    return block


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _bar(delta: float, scale: float, width: int = 24) -> str:
    if scale <= 0:
        return " " * (2 * width + 1)
    units = int(round(abs(delta) / scale * width))
    units = min(units, width)
    left = ("#" * units).rjust(width) if delta < 0 else " " * width
    right = ("#" * units).ljust(width) if delta >= 0 else " " * width
    return f"{left}|{right}"


def _print_attribution(pid: str, component: str, pop: Population) -> None:
    att = attribute(pid, component, pop)
    display = pop.people[pid].get("display_name")
    print("-" * 96)
    print(f"LEAVE-ONE-EVIDENCE-OUT · {pid} ({display}) · {component}")
    print("-" * 96)
    print(
        f"  full score {att['point']} on [{att['interval'][0]}, {att['interval'][1]}] "
        f"(n={att['n']} streams over {att['n_rows']} ledger rows, "
        f"prior weight {att['prior_weight'] * 100:.0f}%)"
    )
    print(
        f"  {att['n_recomputes']} exact recomputes in {att['elapsed_ms']:.3f} ms — "
        "closed-form, no language model in the scoring path"
    )
    print()
    if not att["rows"]:
        print("  no evidence streams to drop at this asof; the score IS the class prior")
        print()
        return
    scale = max(abs(r["delta"]) for r in att["rows"]) or 1.0
    print(
        f"  {'dropped stream':<34} {'rows':>4} {'delta':>7}  "
        f"{'-':^24}|{'+':^24}  {'score':>6} {'interval':>16} {'width':>6} {'n':>3}"
    )
    for r in att["rows"]:
        print(
            f"  {r['dropped'][:34]:<34} {r['n_rows']:>4} {r['delta']:>+7.2f}  "
            f"{_bar(r['delta'], scale)}  {r['point_without']:>6.1f} "
            f"{'[' + format(r['interval_without'][0], '.1f') + ', ' + format(r['interval_without'][1], '.1f') + ']':>16} "
            f"{r['width_without']:>6.1f} {r['n']:>3}"
        )
    p = att["prior_only"]
    print(
        f"  {'PRIOR ONLY (drop everything)':<34} {'-':>4} {p['delta']:>+7.2f}  "
        f"{_bar(p['delta'], scale)}  {p['point_without']:>6.1f} "
        f"{'[' + format(p['interval_without'][0], '.1f') + ', ' + format(p['interval_without'][1], '.1f') + ']':>16} "
        f"{p['width_without']:>6.1f} {0:>3}"
    )
    print()
    print(f"  {_interpretation(att)}")
    print()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Leave-one-evidence-out attribution over the Founder Score (B5)."
    )
    ap.add_argument("--asof", default=None, help="ISO-8601 UTC; defaults to now")
    ap.add_argument("--person", action="append", default=[], help="person_id (repeatable)")
    ap.add_argument(
        "--component", default=None, choices=list(COMPONENTS), help="default: both"
    )
    ap.add_argument("--json", action="store_true", help="dump the render-ready block")
    args = ap.parse_args(argv)

    store.open_ledger()  # NEVER reset=True — four agents share this database
    asof = ledger.to_iso(args.asof) if args.asof else ledger.now_iso()

    t0 = time.perf_counter()
    pop = fit_population(asof)
    fit_ms = (time.perf_counter() - t0) * 1000.0

    if args.person:
        people = list(dict.fromkeys(args.person))
    else:
        picked = pick_demo_people(pop)
        for hero in ("per_dr", "per_mo"):
            if hero in pop.people and hero not in picked.values():
                picked[f"hero {hero}"] = hero
        people = list(dict.fromkeys(picked.values()))

    if args.json:
        print(json.dumps(
            {pid: attribution_block(pid, asof, pop=pop) for pid in people if pid in pop.people},
            indent=2,
            ensure_ascii=False,
        ))
        return 0

    print("=" * 96)
    print("B5 — LEAVE-ONE-EVIDENCE-OUT ATTRIBUTION")
    print("=" * 96)
    print(
        f"  asof {pop.asof} · {pop.n_people} people · {pop.n_observations} observations · "
        f"population refit in {fit_ms:.0f} ms"
    )
    print(f"  {LOO_CAPTION}")
    print()
    components = [args.component] if args.component else list(COMPONENTS)
    for pid in people:
        if pid not in pop.people:
            print(f"  (no person '{pid}' visible at {asof})")
            continue
        for comp in components:
            _print_attribution(pid, comp, pop)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
