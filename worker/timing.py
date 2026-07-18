"""Time-from-first-signal-to-decision instrumentation.

The rubric asks for two different things that are easy to conflate, so this
module keeps them apart on purpose:

* **Latency** is compute — how long a model call or a fetch took. That is
  measured in milliseconds and lives in the batch log, not here.
* **Time to decision** is calendar — how long a real opportunity sat between the
  first observable signal in the world and a typed decision. That is measured in
  hours and days, and it is what this module computes. The two are four orders of
  magnitude apart and must never share an axis.

It also computes the RELIABILITY half, which is the part most submissions skip:
a median time-to-decision computed only over the opportunities that reached a
decision is a survivorship statistic. So we report the completion rate, the
stage at which the rest stalled, and the honest split between clock time we
control (our compute and our queue) and clock time we do not (waiting on a human
to answer). Everything is derived from stage_transition rows and from the ledger
through the one read path — nothing is stored as a mutable status field.

All reads go through :mod:`worker.ledger`, so every number here is itself
asof-filtered and a past ``asof`` reproduces the funnel as it stood then.
"""

from __future__ import annotations

import statistics
from typing import Any, Iterable

from worker import ledger
from worker.ledger import parse_iso, to_iso

DECISION_STAGES = {"decision", "decided", "committed"}
TERMINAL_REASONS = {"decided", "screened_out", "passed", "rejected"}
STALL_REASONS = {"stalled", "no_response", "expired"}


def _minutes(start: str, end: str) -> float:
    return round((parse_iso(end) - parse_iso(start)).total_seconds() / 60.0, 1)


def _median(values: Iterable[float]) -> float | None:
    vals = [v for v in values if v is not None]
    return round(statistics.median(vals), 1) if vals else None


def opportunity_timing(opportunity_id: str, asof: str) -> dict[str, Any]:
    """Full timing record for one opportunity as it stood at ``asof``.

    ``first_signal_at`` is when the world produced the signal, not when we
    noticed it. The gap between that and our first stage entry is the channel's
    days of edge, and we report it as such rather than quietly starting the clock
    when we happened to run the crawler.

    Which row supplies it matters, so it is resolved explicitly rather than by
    taking a global minimum:

    * The opportunity's own ``first_signal_at`` wins when set. For an INBOUND
      deck that is the submission — the founder's earlier history belongs to the
      PERSON and follows them across ventures, and letting a 2024 observation
      start an opportunity opened in 2026 would report a two-year time-to-
      decision for a thirty-eight minute one.
    * Otherwise the earliest visible observation, read through the chokepoint.
    * Otherwise the first stage entry, which is the weakest of the three and is
      only ever a fallback.
    """
    asof = to_iso(asof)
    obs = ledger.read_observations(asof, opportunity_id=opportunity_id, order="asc")
    transitions = ledger.read_stage_transitions(asof, opportunity_id=opportunity_id)

    opp = next(
        (o for o in ledger.list_opportunities(asof) if o["opportunity_id"] == opportunity_id),
        None,
    )
    first_signal_at = (opp or {}).get("first_signal_at")
    first_signal_basis = "opportunity.first_signal_at"
    if not first_signal_at:
        first_signal_at = obs[0]["observed_at"] if obs else None
        first_signal_basis = "earliest visible observation"
    if not first_signal_at and transitions:
        first_signal_at = transitions[0]["entered_at"]
        first_signal_basis = "first stage entry (no observation visible at this asof)"

    stages: list[dict[str, Any]] = []
    human_wait_minutes = 0.0
    for idx, row in enumerate(transitions):
        nxt = transitions[idx + 1]["entered_at"] if idx + 1 < len(transitions) else None
        end = row["exited_at"] or nxt
        duration = _minutes(row["entered_at"], end) if end else None
        is_human = bool(row.get("wait_is_human"))
        if is_human and duration:
            human_wait_minutes += duration
        stages.append(
            {
                "stage": row["stage"],
                "entered_at": row["entered_at"],
                "entered_by": row.get("entered_by"),
                "duration_minutes": duration,
                "exited_reason": row.get("exited_reason"),
                "wait_is_human": is_human,
                "blocked_on": row.get("blocked_on"),
                "is_open": end is None,
            }
        )

    decision_row = next((r for r in transitions if r["stage"] in DECISION_STAGES), None)
    decided_at = decision_row["entered_at"] if decision_row else None

    elapsed = (
        _minutes(first_signal_at, decided_at)
        if (first_signal_at and decided_at)
        else None
    )

    if decision_row is not None:
        state = "decided"
        stalled_at_stage = None
    else:
        last = transitions[-1] if transitions else None
        if last is None:
            state, stalled_at_stage = "not_entered", None
        elif last.get("exited_reason") in TERMINAL_REASONS or last.get("is_terminal"):
            state, stalled_at_stage = "closed_without_decision", last["stage"]
        else:
            state, stalled_at_stage = "stalled", last["stage"]

    return {
        "opportunity_id": opportunity_id,
        "asof": asof,
        "first_signal_at": first_signal_at,
        "first_signal_basis": first_signal_basis,
        "first_stage_entered_at": transitions[0]["entered_at"] if transitions else None,
        "decided_at": decided_at,
        "state": state,
        "stalled_at_stage": stalled_at_stage,
        "blocked_on": (transitions[-1].get("blocked_on") if transitions else None),
        "n_observations": len(obs),
        "n_stages": len(stages),
        "stages": stages,
        "elapsed_first_signal_to_decision_minutes": elapsed,
        "elapsed_first_signal_to_decision_hours": (
            round(elapsed / 60.0, 1) if elapsed is not None else None
        ),
        "human_wait_minutes": round(human_wait_minutes, 1),
        "elapsed_excluding_human_wait_minutes": (
            round(elapsed - human_wait_minutes, 1) if elapsed is not None else None
        ),
        "discovery_lag_minutes": (
            _minutes(first_signal_at, transitions[0]["entered_at"])
            if (first_signal_at and transitions)
            else None
        ),
    }


def cohort_timing(asof: str, *, opportunity_ids: Iterable[str] | None = None) -> dict[str, Any]:
    """Cohort-level timing and reliability at ``asof``.

    The headline number is deliberately reported three ways:

    * ``median_minutes_including_human_wait`` — the real wall-clock experience.
    * ``median_minutes_excluding_human_wait`` — the part of the clock we own.
    * ``reached_decision_pct`` — the denominator that makes the first two honest.

    Reporting only the second without the third is the standard way to make a
    pipeline look fast, and it is why the stall breakdown sits in the same
    return value rather than in a footnote.
    """
    asof = to_iso(asof)
    if opportunity_ids is None:
        opportunity_ids = [o["opportunity_id"] for o in ledger.list_opportunities()]
    records = [opportunity_timing(oid, asof) for oid in opportunity_ids]
    records = [r for r in records if r["state"] != "not_entered"]

    decided = [r for r in records if r["state"] == "decided"]
    stalled = [r for r in records if r["state"] == "stalled"]
    closed = [r for r in records if r["state"] == "closed_without_decision"]

    stall_breakdown: dict[str, int] = {}
    for rec in stalled + closed:
        key = rec["stalled_at_stage"] or "unknown"
        stall_breakdown[key] = stall_breakdown.get(key, 0) + 1

    incl = [r["elapsed_first_signal_to_decision_minutes"] for r in decided]
    excl = [r["elapsed_excluding_human_wait_minutes"] for r in decided]

    per_stage: dict[str, list[float]] = {}
    for rec in records:
        for stage in rec["stages"]:
            if stage["duration_minutes"] is not None:
                per_stage.setdefault(stage["stage"], []).append(stage["duration_minutes"])

    n = len(records)
    return {
        "asof": asof,
        "n_opportunities": n,
        "n_reached_decision": len(decided),
        "n_stalled": len(stalled),
        "n_closed_without_decision": len(closed),
        "reached_decision_pct": round(100.0 * len(decided) / n, 1) if n else None,
        "stalled_pct": round(100.0 * (len(stalled) + len(closed)) / n, 1) if n else None,
        "stalled_at_stage": stall_breakdown,
        "median_minutes_including_human_wait": _median(incl),
        "median_minutes_excluding_human_wait": _median(excl),
        "median_hours_including_human_wait": (
            round(_median(incl) / 60.0, 1) if _median(incl) is not None else None
        ),
        "median_hours_excluding_human_wait": (
            round(_median(excl) / 60.0, 1) if _median(excl) is not None else None
        ),
        "median_human_wait_minutes": _median([r["human_wait_minutes"] for r in decided]),
        "median_discovery_lag_minutes": _median([r["discovery_lag_minutes"] for r in records]),
        "median_minutes_by_stage": {k: _median(v) for k, v in sorted(per_stage.items())},
        "n_by_stage": {k: len(v) for k, v in sorted(per_stage.items())},
        "basis": (
            "Median over opportunities that reached a typed decision at this asof. "
            "The completion rate is reported alongside it because a median over "
            "survivors alone is not a latency, it is a selection effect."
        ),
        "records": records,
    }


def to_demo_block(asof: str, *, opportunity_ids: Iterable[str] | None = None) -> dict[str, Any]:
    """Emit the cohort timing in the demo.json ``{value, n}`` convention.

    Every rendered number carries its own n, because a number without its n is an
    assertion and the whole product is an argument against those.
    """
    c = cohort_timing(asof, opportunity_ids=opportunity_ids)
    n = c["n_opportunities"]
    d = c["n_reached_decision"]
    return {
        "asof": c["asof"],
        "plain_line": (
            "How long it took from the first signal existing in the world to a typed "
            "decision — and how many opportunities never got one."
        ),
        "n_opportunities": {"value": n, "n": n},
        "reached_decision": {"value": d, "n": n},
        "reached_decision_pct": {"value": c["reached_decision_pct"], "n": n},
        "stalled_pct": {"value": c["stalled_pct"], "n": n},
        "stalled_at_stage": [
            {"stage": k, "count": {"value": v, "n": n}} for k, v in c["stalled_at_stage"].items()
        ],
        "median_hours_to_decision": {
            "value": c["median_hours_including_human_wait"],
            "n": d,
            "basis": "wall clock from first_signal_at, human wait included",
        },
        "median_hours_to_decision_excluding_human_wait": {
            "value": c["median_hours_excluding_human_wait"],
            "n": d,
            "basis": "human response wait subtracted — the part of the clock we control",
        },
        "median_discovery_lag_minutes": {
            "value": c["median_discovery_lag_minutes"],
            "n": n,
            "basis": "signal existed in the world before we entered it — the channel's edge, not our latency",
        },
        "median_minutes_by_stage": [
            {"stage": k, "median_minutes": {"value": v, "n": c["n_by_stage"][k]}}
            for k, v in c["median_minutes_by_stage"].items()
        ],
        "basis": c["basis"],
    }


if __name__ == "__main__":  # pragma: no cover
    import json

    ledger.open_ledger()
    stamp = ledger.now_iso()
    print(json.dumps(to_demo_block(stamp), indent=2))
