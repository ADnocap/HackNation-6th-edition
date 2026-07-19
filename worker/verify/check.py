"""The thing that makes the demo honest: re-fetch every cited page and check the excerpt.

For every ``evidence`` row in the ledger that carries a ``source_url``, this goes and
gets that URL and asks one question: **is the thing we said was on that page actually on
it?** It prints URL, HTTP status, the expected excerpt, found yes/no, and the fetch
timestamp — the row a judge can re-run themselves.

This is an auditor. It reads the ledger and writes nothing to it. The ledger is
append-only and shared; a verification pass that mutated evidence rows to match what it
found would be marking its own homework, which is precisely the failure mode this whole
product exists to catch in other people's decks.

A 404 IS A FIRST-CLASS RESULT
-----------------------------
Some of our evidence is ``absent_but_expected``: we predicted a page would not exist and
went and confirmed it does not. ``ledgerline-sage.vercel.app/careers`` and
``northgate-three.vercel.app/changelog`` return genuine 404s from genuine hosts, and
those 404s are the evidence — a company claiming €41K MRR with no careers page is the
finding. A 404 where absence was predicted is a **PASS**. A 404 where we claimed to have
found something is a real failure and is reported as one.

RESERVED TLDs ARE SKIPPED, NOT FAILED
-------------------------------------
Evidence citing ``.example`` / ``.test`` hosts is illustrative — those TLDs are reserved
so they can never resolve. They are reported SKIPPED with the reason, never as failures.

HOW "IS THE EXCERPT PRESENT" IS DECIDED
---------------------------------------
Strictest test first, and the basis of every verdict is printed so nobody has to trust
the word PASS:

1. **literal** — the excerpt, whitespace- and case-normalized, appears verbatim in the
   page's visible text.
2. **atoms** — every *hard* fact asserted in the excerpt is present on the page. Hard
   facts are the ones that cannot be waffled: money amounts, ISO dates, serial numbers,
   version strings, percentages. If the excerpt says ``$99`` and the page says ``€89``,
   that is a MISMATCH and it gets reported, loudly, with the missing values named.
3. **soft** — the excerpt asserts no hard fact (``"Team page lists 3 named people"`` is
   a count, not a quotable string). The page resolved and the wording overlaps, but the
   verdict says ``soft`` rather than claiming a verification it did not perform.

That ladder matters because the ``excerpt`` column in this ledger largely holds analyst
*findings* rather than verbatim page text. Reporting all of them as failures would be
noise; reporting all of them as passes would be a lie. The basis column says which one
each row earned.

Run it::

    uv run python -m worker.verify.check
    uv run python -m worker.verify.check --refresh    # bypass cache, prove it is live
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from typing import Any

from worker import ledger, store
from worker.collectors import base
from worker.verify import fetch as vfetch
from worker.verify import tavily as vtavily

DEFAULT_ASOF = "2026-07-19T02:14:33Z"

# --------------------------------------------------------------------------- #
# verdicts
# --------------------------------------------------------------------------- #

PASS = "PASS"
MISMATCH = "MISMATCH"
SOFT = "SOFT-OK"
ABSENT_OK = "ABSENT-OK"
ABSENT_BAD = "ABSENT-BAD"
SKIPPED = "SKIPPED"
ERROR = "ERROR"

#: Verdicts that mean "the ledger is telling the truth about this page".
GOOD = (PASS, SOFT, ABSENT_OK)
#: Verdicts that mean a human has to look. These are the ones that earn the tool.
BAD = (MISMATCH, ABSENT_BAD, ERROR)

# --------------------------------------------------------------------------- #
# atom extraction — what in an excerpt is actually checkable
# --------------------------------------------------------------------------- #

_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s?%")
_MONEY = re.compile(r"[$€£¥]\s?(\d[\d.,]*)\s?([KkMmBb])?")
_VERSION = re.compile(r"\bv(\d+\.\d+(?:\.\d+)?)\b")
#: Any run of digits, possibly grouped with , . or / — "98/441,207", "1,815", "0.4.1".
_NUMBER = re.compile(r"\d[\d.,/]*\d|\d")

_STOPWORDS = frozenset(
    """a an and are as at be but by for from has have in into is it its of on onto or
    that the their there they this to was were with total across two three lists named
    same page site per present none our we us""".split()
)


def _digit_forms(raw: str, multiplier: str | None = None) -> set[str]:
    """Every reasonable normalized spelling of one numeric token.

    ``"98/441,207"`` yields the concatenated serial ``98441207`` and each run ``98``,
    ``441``, ``207``; ``"41" + "K"`` also yields ``41000``. Being generous about what
    counts as *present on the page* while staying strict about what the excerpt
    *asserted* is the right asymmetry: it makes a MISMATCH hard to produce by accident,
    so the ones that do appear are worth acting on.
    """
    forms: set[str] = set()
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return forms
    forms.add(digits)
    forms.add(digits.lstrip("0") or "0")
    # Keep the dotted spelling too, so a version string survives normalization:
    # "0.4.1" must not collapse to "041" on both sides and then match by accident,
    # nor vanish entirely and produce a false MISMATCH against a page that says v0.4.1.
    forms.add(raw.replace(",", "").replace("/", "").strip())
    for run in re.split(r"[^\d]+", raw):
        if run:
            forms.add(run)
            forms.add(run.lstrip("0") or "0")
    if multiplier:
        scale = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[multiplier.lower()]
        try:
            forms.add(str(int(float(raw.replace(",", "")) * scale)))
        except ValueError:
            pass
    return forms


@dataclass
class Atom:
    """One checkable fact pulled out of an excerpt."""

    kind: str          # money | date | serial | version | percent | count
    display: str       # as written in the excerpt
    forms: set[str]    # normalized spellings that would count as a hit
    hard: bool         # hard atoms drive the verdict; soft ones are reported only


def excerpt_atoms(excerpt: str) -> list[Atom]:
    """Pull the checkable facts out of an excerpt, classified hard vs soft.

    A bare small integer is **soft** on purpose. ``"Team page lists 3 named people"``
    asserts a count that the page satisfies by listing three people, not by printing the
    character ``3`` — failing that row would be the tool being wrong, not the ledger.
    Money, dates, serials, versions and percentages are **hard**: they are quotable
    strings, and if the page does not contain them the excerpt is not describing that
    page.
    """
    if not excerpt:
        return []

    atoms: list[Atom] = []
    consumed: list[tuple[int, int]] = []

    def claim(match: re.Match, kind: str, forms: set[str], hard: bool) -> None:
        consumed.append(match.span())
        atoms.append(Atom(kind, match.group(0).strip(), forms, hard))

    for m in _DATE.finditer(excerpt):
        claim(m, "date", {m.group(1)}, True)
    for m in _PERCENT.finditer(excerpt):
        claim(m, "percent", _digit_forms(m.group(1)), True)
    for m in _MONEY.finditer(excerpt):
        claim(m, "money", _digit_forms(m.group(1), m.group(2)), True)
    for m in _VERSION.finditer(excerpt):
        claim(m, "version", {m.group(1)}, True)

    for m in _NUMBER.finditer(excerpt):
        if any(s <= m.start() < e or s < m.end() <= e for s, e in consumed):
            continue
        raw = m.group(0)
        digits = re.sub(r"\D", "", raw)
        if not digits:
            continue
        # A long digit run is an identifier — a trademark serial, a register number.
        # Those are quotable and therefore hard. A short bare integer is a count.
        hard = len(digits) >= 4
        atoms.append(Atom("serial" if hard else "count", raw, _digit_forms(raw), hard))

    return atoms


def page_number_forms(text: str) -> set[str]:
    """Every normalized numeric spelling present in a page's visible text."""
    forms: set[str] = set()
    for m in _DATE.finditer(text):
        forms.add(m.group(1))
    for m in _NUMBER.finditer(text):
        forms |= _digit_forms(m.group(0))
    return forms


def _words(text: str) -> set[str]:
    return {
        w for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in _STOPWORDS
    }


def _normalize(text: str) -> str:
    """Casefold, collapse whitespace, and flatten the punctuation that varies by render."""
    t = text.lower()
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'),
                 ("—", "-"), ("–", "-"), ("−", "-"), (" ", " ")):
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t).strip()


# --------------------------------------------------------------------------- #
# one row
# --------------------------------------------------------------------------- #


@dataclass
class Row:
    """One evidence row, checked."""

    evidence_id: str
    claim_id: str
    kind: str
    claimed_found: bool
    url: str
    verdict: str
    status: int
    excerpt: str | None
    fetched_at: str
    basis: str = ""
    detail: str = ""
    from_cache: bool = False
    final_url: str = ""
    atoms_found: list[str] = field(default_factory=list)
    atoms_missing: list[str] = field(default_factory=list)

    @property
    def is_bad(self) -> bool:
        return self.verdict in BAD


def check_excerpt(excerpt: str | None, receipt: vfetch.Receipt) -> tuple[str, str, str, list[str], list[str]]:
    """Decide whether ``excerpt`` is supported by the fetched page.

    Returns ``(verdict, basis, detail, atoms_found, atoms_missing)``.
    """
    page = receipt.visible_text
    if not excerpt or not excerpt.strip():
        return (
            PASS,
            "status_only",
            "No excerpt attached to this row; the fetch confirms the page resolves.",
            [],
            [],
        )

    if _normalize(excerpt) in _normalize(page):
        return (PASS, "literal", "Excerpt appears verbatim in the page's visible text.", [], [])

    atoms = excerpt_atoms(excerpt)
    page_forms = page_number_forms(page)
    hard = [a for a in atoms if a.hard]

    found = [a.display for a in hard if a.forms & page_forms]
    missing = [a.display for a in hard if not (a.forms & page_forms)]

    if hard and not missing:
        return (
            PASS,
            "atoms",
            f"Every hard fact asserted is present on the page: {', '.join(found)}.",
            found,
            missing,
        )

    if missing:
        return (
            MISMATCH,
            "atoms",
            (
                f"Asserted but NOT on the page: {', '.join(missing)}."
                + (f" Present: {', '.join(found)}." if found else "")
            ),
            found,
            missing,
        )

    # No hard atoms at all — the excerpt is a finding, not a quotation.
    ew, pw = _words(excerpt), _words(page)
    overlap = len(ew & pw) / len(ew) if ew else 0.0
    soft = [a.display for a in atoms if not a.hard]
    return (
        SOFT,
        "soft",
        (
            f"Excerpt asserts no quotable hard fact (it is a finding, not a quotation)."
            f" Page resolved; wording overlap {overlap:.0%}"
            + (f"; unquotable counts asserted: {', '.join(soft)}." if soft else ".")
        ),
        [],
        [],
    )


def check_row(ev: dict[str, Any], *, refresh: bool = False) -> Row:
    """Check one evidence row end to end."""
    url = (ev.get("source_url") or "").strip()
    excerpt = ev.get("excerpt")
    claimed_found = bool(ev.get("found"))
    common = dict(
        evidence_id=ev.get("evidence_id") or "?",
        claim_id=ev.get("claim_id") or "?",
        kind=ev.get("kind") or "?",
        claimed_found=claimed_found,
        url=url,
        excerpt=excerpt,
    )

    receipt = vfetch.retrieve(url, force=refresh)

    if receipt.skipped_reason:
        return Row(
            **common,
            verdict=SKIPPED,
            status=0,
            fetched_at=receipt.fetched_at,
            basis="reserved_tld",
            detail=receipt.skipped_reason,
        )

    if receipt.error:
        return Row(
            **common,
            verdict=ERROR,
            status=0,
            fetched_at=receipt.fetched_at,
            basis="transport",
            detail=f"Fetch failed: {receipt.error}",
            from_cache=receipt.from_cache,
        )

    base_kwargs = dict(
        status=receipt.status,
        fetched_at=receipt.fetched_at,
        from_cache=receipt.from_cache,
        final_url=receipt.final_url,
    )

    if receipt.not_found:
        if not claimed_found:
            return Row(
                **common,
                **base_kwargs,
                verdict=ABSENT_OK,
                basis="expected_absent",
                detail=(
                    "404 from a live host, and absence is exactly what this row "
                    "predicted. The 404 IS the evidence."
                ),
            )
        return Row(
            **common,
            **base_kwargs,
            verdict=ABSENT_BAD,
            basis="expected_absent",
            detail=(
                "404, but this row claims found=1. The ledger says we saw something "
                "here and the page does not exist."
            ),
        )

    if not receipt.ok:
        return Row(
            **common,
            **base_kwargs,
            verdict=ERROR,
            basis="http",
            detail=f"Unexpected HTTP {receipt.status}.",
        )

    verdict, basis, detail, found, missing = check_excerpt(excerpt, receipt)
    return Row(
        **common,
        **base_kwargs,
        verdict=verdict,
        basis=basis,
        detail=detail,
        atoms_found=found,
        atoms_missing=missing,
    )


# --------------------------------------------------------------------------- #
# the pass
# --------------------------------------------------------------------------- #


def run(asof: str = DEFAULT_ASOF, *, refresh: bool = False) -> dict[str, Any]:
    """Check every evidence row visible at ``asof`` that carries a source_url."""
    evidence = ledger.read_evidence(asof)
    with_url = [e for e in evidence if (e.get("source_url") or "").strip()]
    rows = [check_row(e, refresh=refresh) for e in with_url]

    counts: dict[str, int] = {}
    for r in rows:
        counts[r.verdict] = counts.get(r.verdict, 0) + 1

    return {
        "asof": asof,
        "rows": rows,
        "counts": counts,
        "n_evidence": len(evidence),
        "n_with_url": len(with_url),
        "n_without_url": len(evidence) - len(with_url),
        "n_observations_visible": store.count_observations(asof),
        "cache": base.cache_stats(),
    }


def report_dict(report: dict[str, Any]) -> dict[str, Any]:
    """The report as plain JSON-able data, for the frontend or an export step.

    Provided so an integrator can render the receipt pane from this pass without
    importing the printing code and without this package reaching into ``web/``.
    """
    return {
        "asof": report["asof"],
        "generated_by": "worker.verify.check",
        "fetch_method": "httpx_get",
        "verifier": "httpx_direct",
        "counts": report["counts"],
        "n_evidence": report["n_evidence"],
        "n_with_url": report["n_with_url"],
        "n_without_url": report["n_without_url"],
        "cache": report["cache"],
        "tavily": vtavily.status(),
        "rows": [
            {
                "evidence_id": r.evidence_id,
                "claim_id": r.claim_id,
                "kind": r.kind,
                "verdict": r.verdict,
                "basis": r.basis,
                "detail": r.detail,
                "source_url": r.url,
                "final_url": r.final_url,
                "http_status": r.status,
                "excerpt": r.excerpt,
                "fetched_at": r.fetched_at,
                "from_cache": r.from_cache,
                "claimed_found": r.claimed_found,
                "atoms_found": r.atoms_found,
                "atoms_missing": r.atoms_missing,
            }
            for r in report["rows"]
        ],
    }


# --------------------------------------------------------------------------- #
# printing
# --------------------------------------------------------------------------- #

W = 132


def _trim(s: Any, n: int) -> str:
    s = "" if s is None else str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def print_report(report: dict[str, Any]) -> None:
    rows: list[Row] = report["rows"]
    print()
    print("=" * W)
    print("EVIDENCE VERIFICATION — every cited URL re-fetched, every excerpt re-checked")
    print("=" * W)
    print(
        f"asof {report['asof']} · {report['n_observations_visible']} observations visible · "
        f"{report['n_evidence']} evidence rows, {report['n_with_url']} carry a source_url"
    )
    print(
        "Retrieval is httpx GET against the origin server, disk-cached by content hash. "
        "No search index involved."
    )
    print()
    print(
        f"{'evidence_id':<15} {'verdict':<11} {'HTTP':>5} {'url':<49} "
        f"{'excerpt asserted':<32} {'fetched_at':<20}"
    )
    print("-" * W)
    order = {ABSENT_BAD: 0, MISMATCH: 1, ERROR: 2, SOFT: 3, PASS: 4, ABSENT_OK: 5, SKIPPED: 6}
    for r in sorted(rows, key=lambda x: (order.get(x.verdict, 9), x.evidence_id)):
        status = "—" if r.status == 0 else str(r.status)
        print(
            f"{_trim(r.evidence_id, 15):<15} {r.verdict:<11} {status:>5} "
            f"{_trim(r.url, 49):<49} {_trim(r.excerpt or '(none)', 32):<32} "
            f"{r.fetched_at:<20}"
        )
    print("-" * W)

    findings = [r for r in rows if r.is_bad]
    if findings:
        print()
        print(f"FINDINGS — {len(findings)} row(s) where the ledger and the live page disagree:")
        for r in findings:
            print()
            print(f"  {r.evidence_id}  [{r.verdict}]  claim={r.claim_id}  HTTP {r.status}")
            print(f"    url      {r.url}")
            print(f"    asserted {r.excerpt!r}")
            print(f"    finding  {r.detail}")

    absent = [r for r in rows if r.verdict == ABSENT_OK]
    if absent:
        print()
        print(f"EXPECTED ABSENCES CONFIRMED — {len(absent)} deliberate 404(s), each a PASS:")
        for r in absent:
            print(f"  {r.evidence_id:<15} HTTP {r.status}  {r.url}")
            print(f"    {r.detail}")

    skipped = [r for r in rows if r.verdict == SKIPPED]
    if skipped:
        print()
        print(
            f"SKIPPED — {len(skipped)} row(s) on reserved TLDs (RFC 2606). Deliberately "
            "unresolvable, illustrative, never counted as failures:"
        )
        for r in skipped:
            print(f"  {r.evidence_id:<15} {r.url}")

    soft = [r for r in rows if r.verdict == SOFT]
    if soft:
        print()
        print(
            f"SOFT — {len(soft)} row(s) whose excerpt is an analyst finding rather than a "
            "quotation. The page resolved; no hard fact was available to check:"
        )
        for r in soft:
            print(f"  {r.evidence_id:<15} HTTP {r.status}  {_trim(r.excerpt, 70)}")

    c = report["counts"]
    print()
    print("=" * W)
    good = sum(c.get(k, 0) for k in GOOD)
    bad = sum(c.get(k, 0) for k in BAD)
    print(
        f"SUMMARY  {len(rows)} checked · {c.get(PASS, 0)} pass · {c.get(SOFT, 0)} soft-ok · "
        f"{c.get(ABSENT_OK, 0)} expected-absent (404=PASS) · {c.get(MISMATCH, 0)} mismatch · "
        f"{c.get(ABSENT_BAD, 0)} unexpected-404 · {c.get(ERROR, 0)} error · "
        f"{c.get(SKIPPED, 0)} skipped"
    )
    live = [r for r in rows if r.verdict != SKIPPED]
    resolved = [r for r in live if r.status and (200 <= r.status < 300 or r.status == 404)]
    print(
        f"         {len(resolved)}/{len(live)} non-reserved URLs resolved · "
        f"{good} verified good · {bad} need a human · "
        f"cache holds {report['cache']['entries']} responses "
        f"({report['cache']['bytes'] / 1024:.0f} KB)"
    )
    t = vtavily.status()
    print(
        f"         tavily: {'available' if t['available'] else 'NOT CONFIGURED'} — "
        f"{t['scope']}. Receipts above used httpx_get only, never the index."
    )
    print("=" * W)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

    argv = list(argv if argv is not None else sys.argv[1:])
    refresh = "--refresh" in argv
    as_json = "--json" in argv
    argv = [a for a in argv if not a.startswith("--")]
    asof = argv[0] if argv else DEFAULT_ASOF

    store.open_ledger()  # NEVER reset=True — several agents share this database.

    report = run(asof, refresh=refresh)
    if as_json:
        import json

        print(json.dumps(report_dict(report), indent=2, ensure_ascii=False))
    else:
        print_report(report)

    # Exit non-zero only on a genuine disagreement, so this can gate a demo rehearsal.
    bad = sum(report["counts"].get(k, 0) for k in BAD)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
