"""Rebuild the whole ledger and regenerate demo.json, in the right order.

    uv run python -m worker.run_all

This exists because the sequence has a hard ordering constraint that is easy to
get wrong and expensive when you do: ``seed`` drops every table, so running it
after the collectors silently destroys the crawl. Doing this by hand is how the
ledger got wiped twice.

Order:
    1. init_db     — create the schema
    2. seed        — the hero narrative (DROPS EVERYTHING, so it must run first)
    3. collectors  — uspto, hn, arxiv, domains  (replay from the on-disk cache)
    4. channels    — days-of-edge over whatever the collectors actually found
    5. export_demo — regenerate demo.json, deriving what the ledger can support

Step 3 is network-free on a warm cache, which is what makes a full rebuild cheap
enough to run casually. That is the whole payoff for caching from the first
commit rather than "once it works".

Nothing here fabricates: if a collector finds nothing, the ledger holds nothing
for it, and the exporter keeps the hand-authored override for that block and
says so.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The USPTO snapshot is committed precisely because a live TSDR sweep is slow,
# throttle-prone, and can return a partial serial band.  A normal rebuild must
# replay that dated fixture; refreshing it is an explicit collector operation.
# The other collectors use their content-addressed response caches.
COLLECTORS: list[tuple[str, list[str]]] = [
    ("uspto", ["--offline"]),
    ("hn", []),
    ("arxiv", []),
    ("domains", []),
]

# Windows consoles default to cp1252, which cannot encode the em-dashes and arrows
# our collectors print. Without this, a rebuild dies on a PRINT statement after
# doing all the real work — the most annoying possible failure.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def run(module: str, args: list[str] | None = None, *, timeout: int = 1800) -> tuple[bool, str]:
    cmd = [sys.executable, "-m", module, *(args or [])]
    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT after {timeout}s"
    elapsed = time.time() - started
    tail = (proc.stdout or "").strip().splitlines()
    summary = tail[-1] if tail else ""
    if proc.returncode != 0:
        err = (proc.stderr or "").strip().splitlines()
        summary = err[-1] if err else f"exit {proc.returncode}"
    return proc.returncode == 0, f"{summary}  ({elapsed:.1f}s)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-collectors",
        action="store_true",
        help="seed and export only — use when you deliberately want the hero data alone",
    )
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="rebuild the ledger but leave demo.json alone",
    )
    opts = parser.parse_args(argv)

    steps: list[tuple[str, str, list[str]]] = [
        ("schema", "worker.init_db", []),
        ("seed", "worker.seed", []),
    ]
    if not opts.skip_collectors:
        steps += [
            (f"collect:{name}", f"worker.collectors.{name}", args)
            for name, args in COLLECTORS
        ]
        steps.append(("channels", "worker.collectors.channels", []))
    if not opts.no_export:
        steps.append(("export", "worker.export_demo", ["--from-ledger"]))

    failures = 0
    print("counterproof — full rebuild")
    print("=" * 78)
    for label, module, args in steps:
        ok, summary = run(module, args)
        mark = "ok  " if ok else "FAIL"
        print(f"  [{mark}] {label:18s} {summary}")
        if not ok:
            failures += 1
            # A failing collector is survivable — the ledger simply holds less and
            # the exporter keeps the override. A failing seed or schema is not.
            if label in ("schema", "seed"):
                print("\n  aborting: the ledger could not be built.")
                return 1

    print("=" * 78)
    try:
        from worker import store  # noqa: PLC0415

        store.open_ledger()
        total = store.count_observations("2026-07-19T02:14:33Z")
        people = store.conn().execute("SELECT COUNT(*) c FROM person").fetchone()["c"]
        evidence = store.conn().execute("SELECT COUNT(*) c FROM evidence").fetchone()["c"]
        print(f"  ledger: {total} observations · {people} people · {evidence} evidence rows")
    except Exception as exc:  # noqa: BLE001
        print(f"  ledger summary unavailable: {exc}")

    if failures:
        print(f"  {failures} step(s) failed — see above")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
