"""Regenerate ``web/public/demo.json`` — the ONLY file the frontend reads.

    python -m worker.export_demo

Design, in one paragraph
------------------------
The frontend is a pure renderer over a committed ``demo.json``. That is the
single largest risk mitigation in the plan: a worker bug at hour 20 must not be
able to break the demo video. So this script is allowed to fail, and when it
fails it leaves the existing ``demo.json`` untouched unless ``--force`` is given.

Where the numbers come from
---------------------------
Every value starts in ``worker/demo_overrides.json`` — hand-authored, dated, and
explicitly marked. As the ledger fills in, this script REPLACES override values
with ledger-derived ones, one block at a time, and records which blocks were
derived in ``meta.provenance_of_this_file``. Nothing is invented inline: if a
value is not in the ledger and not in the overrides, it does not appear.

The chokepoint rule
-------------------
This module never writes SQL. Every ledger read goes through
``worker.ledger.read_observations(asof, ...)`` and friends, which is the only
place in the codebase that touches the observation table. The import is lazy and
guarded, because the ledger module and the database may not exist yet.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
OVERRIDES_PATH = REPO_ROOT / "worker" / "demo_overrides.json"
OUTPUT_PATH = REPO_ROOT / "web" / "public" / "demo.json"

# Top-level keys the contract requires. Validation is a hard gate: we would
# rather ship yesterday's demo.json than a structurally incomplete one.
REQUIRED_TOP_LEVEL = [
    "contract_version",
    "meta",
    "thesis",
    "memory",
    "compound_query",
    "funnel",
    "signal_feed",
    "screen",
    "people",
    "opportunities",
    "portfolio",
    "honesty",
    "asof_slices",
    "ui_rules",
]

# Substrings that must never appear anywhere in the emitted file. The three
# axes are never averaged, so no blended column may exist even by accident.
FORBIDDEN_SUBSTRINGS = ["composite", "overall_score", "blended"]


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------

def _is_quantity(obj: Any) -> bool:
    """A {value, n} quantity — the pervasive shape in the contract."""
    return isinstance(obj, dict) and "value" in obj


def _compact(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(", ", ": "))


def dumps_contract(obj: Any, indent: int = 2, _level: int = 0) -> str:
    """Pretty-print, but keep every {value, n} quantity on ONE line.

    This is not cosmetic. The n-audit is a mechanical grep:

        grep -o '"value":[^}]*}' web/public/demo.json | grep -v '"n"'

    and it must return empty. grep is line-oriented, so a quantity split across
    lines would silently pass the audit without ever being checked. Emitting
    quantities inline is what makes the audit bite.
    """
    pad = " " * (indent * _level)
    pad_in = " " * (indent * (_level + 1))

    if isinstance(obj, dict):
        if not obj:
            return "{}"
        flat = _compact(obj)
        if _is_quantity(obj) or (len(flat) <= 100 and not _has_container(obj)):
            return flat
        parts = [
            f"{pad_in}{json.dumps(k, ensure_ascii=False)}: "
            f"{dumps_contract(v, indent, _level + 1)}"
            for k, v in obj.items()
        ]
        return "{\n" + ",\n".join(parts) + "\n" + pad + "}"

    if isinstance(obj, list):
        if not obj:
            return "[]"
        flat = _compact(obj)
        if len(flat) <= 100 and not any(isinstance(x, (dict, list)) for x in obj):
            return flat
        parts = [f"{pad_in}{dumps_contract(v, indent, _level + 1)}" for v in obj]
        return "[\n" + ",\n".join(parts) + "\n" + pad + "]"

    return json.dumps(obj, ensure_ascii=False)


def _has_container(d: dict) -> bool:
    return any(isinstance(v, (dict, list)) for v in d.values())


# --------------------------------------------------------------------------
# Ledger access — lazy, guarded, never fatal
# --------------------------------------------------------------------------

class LedgerUnavailable(Exception):
    """The ledger could not be read. Not an error; a documented degradation."""


def _ledger():
    """Import the ledger lazily.

    Another agent owns ``worker/ledger.py`` and the database file is gitignored,
    so at hour 1 neither may exist. Importing at module scope would make
    ``python -m worker.export_demo`` crash and take the hour-6 gate with it.
    """
    try:
        from worker import ledger  # noqa: PLC0415
    except Exception as exc:  # pragma: no cover - depends on sibling agent
        raise LedgerUnavailable(f"worker.ledger not importable: {exc}") from exc
    return ledger


def _claims_are_renderable(claims: list) -> bool:
    """A derived claim block must carry everything the Receipt modal renders.

    The ledger stores claims as flat rows: `log_odds_sum` is a column, but the
    per-term breakdown, the receipt panes, the evidence list and the
    leave-one-out waterfall are nested structures the renderer needs and a
    single table row cannot hold. Accepting a flat block would silently empty
    the best thirty seconds of the demo, so we refuse it. Derivation is allowed
    to improve this file; it is never allowed to downgrade it.
    """
    if not claims:
        return False
    required = ("log_odds", "evidence")
    for c in claims:
        if not isinstance(c, dict):
            return False
        if any(k not in c for k in required):
            return False
        if not isinstance(c.get("log_odds"), dict) or "terms" not in c["log_odds"]:
            return False
    return True


def _history_is_renderable(history: list) -> bool:
    """A derived history must draw the step function across ventures.

    It has to be single-component (mixing credibility and build capability into
    one series draws a zig-zag, not a step function) and it has to name the
    venture, because the whole point of the chart is that the line carries over
    when the company changes.
    """
    if not history or len(history) < 2:
        return False
    components = {h.get("component") for h in history if isinstance(h, dict)}
    if len(components - {None}) > 1:
        return False
    return all(
        isinstance(h, dict) and (h.get("org_name") or h.get("venture"))
        for h in history
    )


def derive_from_ledger(demo: dict, asof: str) -> list[str]:
    """Replace override values with ledger-derived ones. Returns block names.

    Every block here is best-effort and independently guarded: one failing
    derivation must not cost us the other blocks, and none of them may fabricate
    a value when the ledger has nothing to say.

    Each block is additionally gated on being at least as renderable as the
    hand-authored value it would replace. A ledger that is real but not yet as
    complete as the contract must not be able to break the demo by being
    switched on.
    """
    derived: list[str] = []

    try:
        ledger = _ledger()
    except LedgerUnavailable as exc:
        print(f"  ledger: unavailable — {exc}")
        print("  ledger: emitting hand-authored overrides verbatim. This is expected")
        print("          before the worker lands and is not a failure.")
        return derived

    # -- observation counts ------------------------------------------------
    try:
        total = ledger.count_observations(asof)
        if total:
            demo["memory"]["observations_ingested"] = {"value": total, "n": total}
            demo["memory"]["derived_from_ledger"] = True
            derived.append("memory.observations_ingested")
    except Exception as exc:
        print(f"  memory.observations_ingested: kept override ({exc})")

    # -- asof slices -------------------------------------------------------
    try:
        slices = ledger.asof_slices(asof)
        if slices:
            demo["asof_slices"]["available"] = slices
            derived.append("asof_slices.available")
    except Exception as exc:
        print(f"  asof_slices: kept override ({exc})")

    # -- per-opportunity claims and founder score history ------------------
    # Keys beginning with "_" are annotations for a human reader, not entities.
    for opp_id, opp in demo.get("opportunities", {}).items():
        if opp_id.startswith("_") or not isinstance(opp, dict):
            continue
        try:
            claims = ledger.read_claims(asof, opportunity_id=opp_id)
            if _claims_are_renderable(claims):
                opp["claims"] = claims
                derived.append(f"opportunities.{opp_id}.claims")
            elif claims:
                print(
                    f"  {opp_id}.claims: kept override — ledger returned "
                    f"{len(claims)} flat rows with no nested log_odds.terms, "
                    f"receipt or evidence. Adopting them would empty the "
                    f"Receipt modal."
                )
        except Exception as exc:
            print(f"  {opp_id}.claims: kept override ({exc})")

    for person_id, person in demo.get("people", {}).items():
        if person_id.startswith("_") or not isinstance(person, dict):
            continue
        try:
            history = ledger.read_founder_score_history(person_id, asof)
            if _history_is_renderable(history):
                person["founder_score_history"] = history
                derived.append(f"people.{person_id}.founder_score_history")
            elif history:
                print(
                    f"  {person_id}.founder_score_history: kept override — "
                    f"ledger returned {len(history)} versions that mix score "
                    f"components or carry no venture name, which would draw a "
                    f"zig-zag instead of a step function across ventures."
                )
        except Exception as exc:
            print(f"  {person_id}.founder_score_history: kept override ({exc})")

    # -- the latency tile reads a real log or does not render ---------------
    log_path = REPO_ROOT / "logs" / "batch_7f3a91.jsonl"
    demo["honesty"]["latency"]["log_present"] = log_path.exists()
    if log_path.exists():
        derived.append("honesty.latency.log_present")

    return derived


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def validate(demo: dict, text: str) -> list[str]:
    """Return a list of contract violations. Empty list means the file ships."""
    problems: list[str] = []

    for key in REQUIRED_TOP_LEVEL:
        if key not in demo:
            problems.append(f"missing required top-level key: {key}")

    lowered = text.lower()
    for bad in FORBIDDEN_SUBSTRINGS:
        if bad in lowered:
            problems.append(
                f"forbidden token {bad!r} present — the three axes are never averaged"
            )

    # The n-audit, run in-process against the exact bytes we are about to write.
    for lineno, line in enumerate(text.splitlines(), start=1):
        idx = 0
        while True:
            idx = line.find('"value":', idx)
            if idx == -1:
                break
            close = line.find("}", idx)
            if close == -1:
                problems.append(
                    f"line {lineno}: quantity split across lines — the n-audit "
                    f"cannot see it"
                )
                break
            if '"n"' not in line[idx:close]:
                problems.append(
                    f'line {lineno}: number without its n: {line[idx:close + 1].strip()}'
                )
            idx = close

    # Every axis block must keep Market categorical: no number to average.
    for person_id, person in demo.get("people", {}).items():
        if person_id.startswith("_") or not isinstance(person, dict):
            continue
        market = (person.get("axes") or {}).get("market")
        if isinstance(market, dict):
            if market.get("value") is not None or market.get("interval") is not None:
                problems.append(
                    f"people.{person_id}.axes.market carries a number — Market is "
                    f"categorical so that it structurally cannot be averaged"
                )

    return problems


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def build(asof: str | None = None, from_ledger: bool = False) -> tuple[dict, str]:
    if not OVERRIDES_PATH.exists():
        raise SystemExit(
            f"missing {OVERRIDES_PATH}. That file is the hand-authored source of "
            f"every value in demo.json; without it there is nothing to emit and "
            f"inventing numbers here is exactly what this product exists to stop."
        )

    demo = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    asof = asof or demo.get("meta", {}).get("asof") or demo["asof_slices"]["default"]

    print(f"  asof: {asof}")
    if from_ledger:
        derived = derive_from_ledger(demo, asof)
    else:
        derived = []
        print("  ledger: not consulted (pass --from-ledger to enable)")
        print("          The hand-authored contract is authoritative until the")
        print("          worker's rows are as complete as the renderer needs.")

    meta = demo.setdefault("meta", {})
    meta["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta["generated_by"] = "worker/export_demo.py"
    meta["provenance_of_this_file"] = {
        "hand_authored_source": "worker/demo_overrides.json",
        "blocks_derived_from_ledger": derived,
        "n_blocks_derived": {"value": len(derived), "n": len(derived)},
        "statement": (
            "Every block not listed as derived came from the hand-authored "
            "overrides file, which is committed and readable. We would rather "
            "show you which numbers we wrote by hand than let you guess."
        ),
    }

    text = dumps_contract(demo) + "\n"
    return demo, text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Regenerate web/public/demo.json")
    parser.add_argument("--asof", default=None, help="ISO-8601 point-in-time cutoff")
    parser.add_argument(
        "--from-ledger",
        action="store_true",
        help=(
            "consult the ledger and replace override blocks with derived ones "
            "where the derived block is at least as complete"
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate only; do not write",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="write even when validation fails (never use before a recording)",
    )
    args = parser.parse_args(argv)

    print("counterproof · export_demo")
    demo, text = build(args.asof, from_ledger=args.from_ledger)

    problems = validate(demo, text)
    if problems:
        print(f"\n  VALIDATION FAILED — {len(problems)} problem(s):")
        for p in problems[:40]:
            print(f"    - {p}")
        if not args.force:
            print("\n  demo.json NOT written. The existing file is untouched, which is")
            print("  the whole reason the frontend reads a committed file.")
            return 1
        print("\n  --force given; writing anyway.")
    else:
        print("  validation: OK")
        print(f"    top-level keys      : {len(demo)}")
        print(f"    people              : {len(demo.get('people', {}))}")
        print(f"    opportunities       : {len(demo.get('opportunities', {}))}")
        print(f"    signal feed rows    : {len(demo.get('signal_feed', {}).get('rows', []))}")
        print("    n-audit             : every rendered number carries its n")
        print("    no averaged axes    : Market is categorical everywhere")

    if args.check:
        print("  --check given; not writing.")
        return 0 if not problems else 1

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(text, encoding="utf-8")
    print(f"  wrote {OUTPUT_PATH} ({len(text):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
