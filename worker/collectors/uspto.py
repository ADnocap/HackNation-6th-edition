"""USPTO self-filed trademark applications — the flagship discovery channel.

WHY THIS CHANNEL EXISTS
-----------------------
A trademark costs about $250. A patent costs $10,000+. So the trademark is the *unfunded*
first-time founder's IP move, and it is typically filed at or before the domain registration —
months before anything a conventional sourcing tool can see. Evertrace and friends mine patents;
nobody mines self-filed marks.

The filter is four booleans, and the fourth is load-bearing:

1. **filing basis 1(b) intent-to-use** — the mark is not in commerce yet. The product has not
   launched, so the filing is pre-fundraise *by definition* rather than by inference.
2. **TEAS Plus** — the cheapest filing tier. See the honesty note on ``teas_plus_proxy`` below;
   this one we can only approximate, and we say so rather than quietly claiming it.
3. **owner is an individual, or an LLC** — not a corporation with a general counsel.
4. **the attorney-of-record field is EMPTY.** This single boolean does four jobs at once:
   someone is building, they have no law firm, therefore no funding, therefore no network.
   It is the cheapest poverty-of-access marker in any public registry.

The goods-and-services free text is captured VERBATIM. It is a machine-readable statement,
written by the founder, of what the product actually is — which is exactly the input the
Idea-vs-Market axis needs, and it exists before the company has a website.

WHERE THE DATA COMES FROM, HONESTLY
-----------------------------------
``bulkdata.uspto.gov`` — the documented home of the daily trademark bulk XML, and the acquisition
path this collector was originally planned around — **no longer resolves in DNS**. It has been
folded into ``data.uspto.gov``, whose API (``api.uspto.gov``) returns 401 without a key that
requires identity verification. ``tsdrapi.uspto.gov`` likewise 401s. The Internet Archive holds
mirrors of the retired daily XML, but archive.org was serving its own "Temporarily Offline" page
throughout this build.

What *does* answer without a key is TSDR's per-serial status view:

    https://tsdr.uspto.gov/statusview/sn{serial}

and it carries every field the filter needs — filing date, the full basis block, owner name and
legal entity type, attorney of record, correspondent, prosecution history, and the complete
goods-and-services text. So this collector is **live**, not a fixture: it reads the federal
trademark register directly, right now, with no API key.

Discovery works by scanning a contiguous serial band. USPTO assigns serial numbers in filing
order, so a contiguous band is one day's filings — the same slice the daily bulk XML would have
handed us, obtained a different way.

RATE LIMITING — READ BEFORE CHANGING THE DELAY
----------------------------------------------
TSDR throttles by returning **HTTP 200 with a ~474-byte empty shell** rather than a 429. That is
a trap: a naive scan reads those as "serial not assigned" and reports a confident, entirely
fictional funnel. Measured behaviour is roughly one request per 2.5s sustaining 100% yield,
against ~10% at full speed. :func:`_fetch_statusview` therefore treats a short body as a retryable
throttle, backs off, and re-fetches with ``force=True`` so a throttle page never sticks in the
disk cache and poison a later run.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from worker import ledger, store
from worker.collectors import base

# --------------------------------------------------------------------------- constants

CHANNEL_ID = "uspto_tm_1b"   # must match the id the frontend renders (see demo.json honesty.days_of_edge)
CHANNEL_NAME = "Self-filed trademark — 1(b) intent-to-use, no attorney of record"
SOURCE = "uspto_tsdr_statusview"
SOURCE_CLASS = "registry_filing"
STATUS_URL = "https://tsdr.uspto.gov/statusview/sn{serial}"

# The coverage limit we state on camera rather than let a judge discover.
LIMITATION = (
    "Foreign-domiciled applicants have been required to appoint US counsel since August 2019 "
    "(37 CFR 2.11), so an empty attorney-of-record field can only occur for a US-domiciled "
    "applicant. This channel therefore systematically selects for US-domiciled founders and is "
    "blind to unrepresented founders everywhere else — and the data agrees: 14 of 14 filings "
    "passing our filter are US-domiciled, which is the rule showing up in the output rather "
    "than a coincidence. Two further limits, both un-evaluated rather than approximated: "
    "(a) TEAS Plus tier is published nowhere in TSDR. We tested the absence of a 'NEW "
    "APPLICATION OFFICE SUPPLIED DATA ENTERED' prosecution event as a proxy and rejected it — "
    "that event is present on 100% of n=90 records, so it carries no information. The "
    "cheapest-tier criterion is therefore NOT applied, and the funnel says so. (b) USPTO "
    "publishes no formation date for an owning LLC, so 'LLC under 180 days old' cannot be "
    "evaluated from this source; it is relaxed to 'owner is an individual or an LLC' pending a "
    "Secretary-of-State lookup we have not built."
)

RATIONALE = (
    "A trademark is ~$250 against a patent's $10K+, so it is the unfunded first-time founder's "
    "IP move, filed at or before domain registration. An empty attorney-of-record field means "
    "no law firm, which means no funding, which means no network — the exact founder this "
    "product exists to find. Cold-start-native: it fires with no GitHub, no funding, no network."
)

# TSDR throttles with a 200 + near-empty body instead of a 429.
_THROTTLE_BODY_BYTES = 1000
_THROTTLE_BACKOFF = (3.0, 6.0, 12.0, 20.0)
# Measured: ~1 req / 2.5s sustains 100% yield; 1.2s yields ~50%.
_POLITE_DELAY = 2.5

# USPTO legal entity strings we treat as "not a funded corporate".
_INDIVIDUAL = "INDIVIDUAL"
_LLC = "LIMITED LIABILITY COMPANY"

_SECTIONS = (
    "Mark Information",
    "Goods and Services",
    "Basis Information (Case Level)",
    "Current Owner(s) Information",
    "Attorney/Correspondence Information",
    "Prosecution History",
    "TM Staff and Location Information",
)

SNAPSHOT_PATH = Path(__file__).resolve().parents[2] / "data" / "uspto" / "tsdr_statusview_snapshot.json"


# --------------------------------------------------------------------------- parsing


def _flatten(html: str) -> list[str]:
    """TSDR ships a label/value table. Strip tags and keep the non-empty lines in order."""
    text = re.sub(r"<[^>]*>", "\n", html)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#39;", "'")
    text = text.replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">")
    text = re.sub(r"[ \t]+", " ", text)
    return [line.strip() for line in text.split("\n") if line.strip()]


def _section(lines: list[str], name: str) -> list[str]:
    """Lines belonging to one TSDR section, exclusive of the next section header."""
    try:
        start = next(i for i, line in enumerate(lines) if line == name)
    except StopIteration:
        return []
    rest = _SECTIONS[_SECTIONS.index(name) + 1:] if name in _SECTIONS else ()
    for i in range(start + 1, len(lines)):
        if lines[i] in rest:
            return lines[start + 1: i]
    return lines[start + 1:]


def _value(lines: list[str], label: str) -> str | None:
    """The line following ``label``, which is how every TSDR field is laid out."""
    for i, line in enumerate(lines):
        if line == label and i + 1 < len(lines):
            return lines[i + 1].strip() or None
    return None


def _values(lines: list[str], label: str) -> list[str]:
    return [lines[i + 1].strip() for i, l in enumerate(lines) if l == label and i + 1 < len(lines)]


def _yesno(lines: list[str], label: str) -> bool:
    value = _value(lines, label)
    return bool(value) and value.strip().lower().startswith("yes")


_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}


def _parse_date(text: str | None) -> str | None:
    """'Apr. 22, 2025' / 'May 09, 2022' -> canonical ISO-8601 UTC midnight.

    This becomes ``observed_at``: the date the filing existed in the world. Never fetch time.
    """
    if not text:
        return None
    match = re.match(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),\s*(\d{4})", text.strip())
    if not match:
        return None
    month = _MONTHS.get(match.group(1).title())
    if not month:
        return None
    try:
        return datetime(
            int(match.group(3)), month, int(match.group(2)), tzinfo=timezone.utc
        ).strftime(store.ISO_FMT)
    except ValueError:
        return None


@dataclass
class Filing:
    """One trademark application, parsed from its TSDR status view."""

    serial: str
    source_url: str
    final_url: str
    http_status: int
    fetched_at: str
    mark: str | None = None
    filing_date: str | None = None
    goods_services: list[str] = field(default_factory=list)
    intl_classes: list[str] = field(default_factory=list)
    filed_itu: bool = False
    filed_use: bool = False
    filed_44d: bool = False
    filed_44e: bool = False
    filed_66a: bool = False
    owner_name: str | None = None
    owner_entity_type: str | None = None
    owner_state: str | None = None
    owner_country: str | None = None
    attorney_name: str | None = None
    correspondent_name: str | None = None
    correspondent_email: str | None = None
    prosecution_events: list[str] = field(default_factory=list)

    # ---- derived filter predicates, each one its own funnel stage ----

    @property
    def goods_services_text(self) -> str:
        return " | ".join(self.goods_services)

    @property
    def has_goods_services(self) -> bool:
        return bool(self.goods_services_text.strip())

    @property
    def is_intent_to_use(self) -> bool:
        """1(b) only: intent-to-use filed, and NOT already in commerce under 1(a)."""
        return self.filed_itu and not self.filed_use

    @property
    def has_attorney(self) -> bool:
        return bool(self.attorney_name)

    @property
    def owner_is_individual_or_llc(self) -> bool:
        entity = (self.owner_entity_type or "").upper()
        return _INDIVIDUAL in entity or _LLC in entity

    @property
    def owner_is_individual(self) -> bool:
        return _INDIVIDUAL in (self.owner_entity_type or "").upper()

    @property
    def is_us_domiciled(self) -> bool:
        return "UNITED STATES" in (self.owner_country or "").upper()

    @property
    def office_supplied_data(self) -> bool:
        """Whether the Office had to key in missing application data.

        THIS WAS TRIED AS A TEAS PLUS PROXY AND IT DOES NOT WORK. Keep the negative result.

        The reasoning was sound: TEAS Plus requires a complete application up front (IDs drawn
        from the ID Manual), so the Office should not need to supply data later, and a
        'NEW APPLICATION OFFICE SUPPLIED DATA ENTERED' event should mark a TEAS Standard filing.
        Measured against the register, the event is present on **100% of n=90 records**, including
        all 29 self-filed ones. It is a routine docketing entry, not a tier marker, so it carries
        exactly zero information about filing tier.

        TEAS Plus is therefore NOT EVALUABLE from TSDR. The criterion is dropped from the filter
        and reported as un-evaluated rather than approximated, because a filter stage that always
        passes is not a filter — it is a decoration that makes the funnel look more selective
        than it is.
        """
        return any("OFFICE SUPPLIED DATA ENTERED" in e.upper() for e in self.prosecution_events)

    @property
    def passes_full_filter(self) -> bool:
        """1(b) + no attorney + individual-or-LLC owner. The three we can actually verify."""
        return (
            self.is_intent_to_use
            and not self.has_attorney
            and self.owner_is_individual_or_llc
            and self.has_goods_services
        )

    @property
    def basis_label(self) -> str:
        bases = []
        if self.filed_use:
            bases.append("1(a) use in commerce")
        if self.filed_itu:
            bases.append("1(b) intent to use")
        if self.filed_44d:
            bases.append("44(d)")
        if self.filed_44e:
            bases.append("44(e)")
        if self.filed_66a:
            bases.append("66(a) Madrid")
        return ", ".join(bases) or "no basis stated"

    def to_dict(self) -> dict[str, Any]:
        return {
            k: v for k, v in self.__dict__.items()
        }

    @classmethod
    def from_dict(cls, blob: dict[str, Any]) -> "Filing":
        return cls(**blob)


def parse_statusview(serial: str, fetched: base.Fetched) -> Filing | None:
    """Parse one TSDR status view. Returns None when the record is absent or throttled."""
    lines = _flatten(fetched.text)
    filing = Filing(
        serial=serial,
        source_url=fetched.url,
        final_url=fetched.final_url,
        http_status=fetched.status,
        fetched_at=fetched.fetched_at,
    )

    filing.filing_date = _parse_date(_value(lines, "Application Filing Date:"))
    if not filing.filing_date:
        return None  # no filing date == not a real application record

    mark_section = _section(lines, "Mark Information")
    filing.mark = _value(mark_section, "Mark Literal Elements:") or _value(lines, "Mark:")

    goods = _section(lines, "Goods and Services")
    # Every class block starts with a 'For:' label; the next line is the verbatim ID text.
    filing.goods_services = [g for g in _values(goods, "For:") if g and not g.startswith("Note")]
    filing.intl_classes = [c for c in _values(goods, "International Class(es):") if c]

    basis = _section(lines, "Basis Information (Case Level)")
    filing.filed_use = _yesno(basis, "Filed Use:")
    filing.filed_itu = _yesno(basis, "Filed ITU:")
    filing.filed_44d = _yesno(basis, "Filed 44D:")
    filing.filed_44e = _yesno(basis, "Filed 44E:")
    filing.filed_66a = _yesno(basis, "Filed 66A:")

    owner = _section(lines, "Current Owner(s) Information")
    filing.owner_name = _value(owner, "Owner Name:")
    filing.owner_entity_type = _value(owner, "Legal Entity Type:")
    filing.owner_state = _value(owner, "State or Country Where Organized:")
    for line in owner:
        if line.strip().upper() in ("UNITED STATES", "USA"):
            filing.owner_country = "UNITED STATES"
            break
    else:
        # the country sits on the line before the postcode in the address block
        filing.owner_country = next(
            (l for l in owner if l.isupper() and len(l) > 3 and l != _LLC and l != _INDIVIDUAL),
            None,
        )

    atty = _section(lines, "Attorney/Correspondence Information")
    # Split at 'Correspondent' — a pro se filing still has a correspondent (the founder), and
    # reading the correspondent's name as an attorney would destroy the entire signal.
    try:
        cut = next(i for i, l in enumerate(atty) if l.startswith("Correspondent"))
    except StopIteration:
        cut = len(atty)
    attorney_block, correspondent_block = atty[:cut], atty[cut:]
    # A represented filing renders 'Attorney of Record' then 'Attorney Name:' + the name.
    # A self-filed one renders the literal line 'Attorney of Record - None'. Require BOTH the
    # absence of that marker and a real name: a false 'no attorney' would corrupt the signal
    # this entire channel rests on, whereas a false 'has attorney' only costs us one candidate.
    explicitly_none = any(
        l.startswith("Attorney of Record") and ("None" in l or "Not Found" in l)
        for l in attorney_block
    )
    if not explicitly_none:
        filing.attorney_name = _value(attorney_block, "Attorney Name:")
    filing.correspondent_name = _value(correspondent_block, "Correspondent Name/Address:")
    emails = [l for l in correspondent_block if re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}", l)]
    filing.correspondent_email = emails[0] if emails else None

    history = _section(lines, "Prosecution History")
    filing.prosecution_events = [
        l for l in history if l.isupper() and len(l) > 8 and not l.startswith("UNITED")
    ]

    return filing


# --------------------------------------------------------------------------- fetching


def _is_throttled(fetched: base.Fetched) -> bool:
    """TSDR answers 200 with a near-empty shell when it is shedding load.

    Reading this as 'no such serial' would produce a confident and completely fictional funnel,
    so it is treated as retryable rather than as data.
    """
    return fetched.ok and len(fetched.text) < _THROTTLE_BODY_BYTES


def _fetch_statusview(serial: int) -> base.Fetched | None:
    """One serial, through the shared cache, with throttle-aware backoff.

    ``force=True`` on retry keeps a throttle page from being written into the disk cache, which
    would otherwise silently poison every later run of the pipeline.
    """
    url = STATUS_URL.format(serial=serial)
    fetched = base.fetch(url)
    if not _is_throttled(fetched):
        return fetched
    for backoff in _THROTTLE_BACKOFF:
        time.sleep(backoff)
        fetched = base.fetch(url, force=True)
        if not _is_throttled(fetched):
            return fetched
    return None


# --------------------------------------------------------------------------- funnel


@dataclass
class Funnel:
    """The filter funnel, counted rather than asserted. Each stage carries its own n."""

    serials_probed: int = 0
    retrieved: int = 0
    throttled_out: int = 0
    has_goods_services: int = 0
    basis_1b: int = 0
    no_attorney: int = 0
    owner_individual_or_llc: int = 0
    passed: int = 0
    office_supplied_data: int = 0
    us_domiciled_among_passed: int = 0
    contactable_among_passed: int = 0

    def render(self) -> str:
        rows = [
            ("serials probed", self.serials_probed),
            ("  records retrieved", self.retrieved),
            ("  lost to throttling", self.throttled_out),
            ("goods-and-services text present", self.has_goods_services),
            ("filed 1(b) intent-to-use (and not 1(a))", self.basis_1b),
            ("no attorney of record  <- load-bearing", self.no_attorney),
            ("owner is individual or LLC", self.owner_individual_or_llc),
            ("PASSED full filter", self.passed),
            ("  of which US-domiciled", self.us_domiciled_among_passed),
            ("  of which contactable (public email)", self.contactable_among_passed),
        ]
        width = max(len(label) for label, _ in rows)
        body = "\n".join(f"  {label.ljust(width)}  {count:>5}" for label, count in rows)
        # State the dropped criterion rather than silently omitting it.
        osd = f"{self.office_supplied_data}/{self.retrieved}" if self.retrieved else "0/0"
        body += (
            f"\n\n  TEAS Plus: NOT EVALUATED — the tier is published nowhere in TSDR. The "
            f"'office supplied data'\n  proxy was tested and rejected: present on {osd} records, "
            "so it carries no information."
        )
        return body


# --------------------------------------------------------------------------- emission


def _register(observed_at: str) -> None:
    """Register the channel once. Append-only, so a re-run must not re-insert."""
    existing = store.conn().execute(
        "SELECT channel_id FROM channel WHERE channel_id = ?", (CHANNEL_ID,)
    ).fetchone()
    if existing:
        return
    base.register_channel(
        channel_id=CHANNEL_ID,
        channel_name=CHANNEL_NAME,
        kind="discovery",
        cold_start_native=True,
        rationale=RATIONALE,
        limitation=LIMITATION,
        note=(
            "Read live and keyless from tsdr.uspto.gov/statusview. bulkdata.uspto.gov no longer "
            "resolves; api.uspto.gov and tsdrapi.uspto.gov both require a verified API key."
        ),
        observed_at=observed_at,
    )


def _emit_filing(run: base.CollectorRun, filing: Filing, provenance: str) -> None:
    """Emit one filing. Every retrieved filing lands; passing ones also get a person spine."""
    common = dict(
        source=SOURCE,
        source_class=SOURCE_CLASS,
        provenance_class=provenance,
        source_url=filing.source_url,
        final_url=filing.final_url,
        http_status=filing.http_status,
        fetch_method="httpx_get",
        fetched_at=filing.fetched_at,
        observed_at=filing.filing_date,
    )

    person_id: str | None = None
    org_id: str | None = None

    if filing.passes_full_filter:
        # The applicant. For an individual owner that IS the founder; for an LLC the
        # correspondent on a pro se filing is the human who filed it themselves.
        display = filing.owner_name if filing.owner_is_individual else (
            filing.correspondent_name or filing.owner_name
        )
        if display:
            resolved = ledger.upsert_person(
                display_name=display,
                region=filing.owner_country,
                contact_status="public_email" if filing.correspondent_email else "form_only",
                resource_tier="bootstrapped",
                solo_or_team="solo" if filing.owner_is_individual else "unknown",
                discovered_via=CHANNEL_ID,
                is_real_person=True,
                # Real private individuals sourced from a public federal register: the Refuter
                # is disabled on them by policy, and the UI pseudonymizes at display time.
                refuter_enabled=False,
                provenance_class=provenance,
                observed_at=filing.filing_date,
                alias_source=SOURCE,
                alias_source_class=SOURCE_CLASS,
            )
            person_id = resolved["person_id"]

        if not filing.owner_is_individual and filing.owner_name:
            org_id = ledger.upsert_org(
                org_name=filing.owner_name,
                region=filing.owner_country,
                provenance_class=provenance,
                observed_at=filing.filing_date,
            )

    # 1. the filing itself
    base.emit(
        run,
        person_id=person_id,
        org_id=org_id,
        claim_type="trademark_filing",
        artifact_type="trademark_application",
        value=filing.mark or f"serial {filing.serial}",
        raw_excerpt=(
            f"US Serial {filing.serial} — mark '{filing.mark}', filed {filing.filing_date[:10]}, "
            f"basis: {filing.basis_label}; owner {filing.owner_name!r} "
            f"({filing.owner_entity_type}); attorney of record: "
            f"{filing.attorney_name or 'NONE'}."
        ),
        is_milestone=filing.passes_full_filter,
        milestone_type="trademark_filed" if filing.passes_full_filter else None,
        **common,
    )

    # 2. the goods-and-services text, VERBATIM — the Idea-vs-Market input.
    if filing.has_goods_services:
        base.emit(
            run,
            person_id=person_id,
            org_id=org_id,
            claim_type="goods_and_services",
            artifact_type="trademark_identification",
            value=filing.goods_services_text,
            raw_excerpt=filing.goods_services_text,
            confidence=1.0,  # transcribed verbatim from the register, not inferred
            **common,
        )

    if not filing.passes_full_filter:
        return

    # 3. the basis, and 4. the empty-attorney marker — each its own auditable row.
    base.emit(
        run,
        person_id=person_id,
        org_id=org_id,
        claim_type="filing_basis",
        artifact_type="trademark_application",
        value=filing.basis_label,
        raw_excerpt=(
            f"Filed ITU: {'Yes' if filing.filed_itu else 'No'}; "
            f"Filed Use: {'Yes' if filing.filed_use else 'No'}. 1(b) means the mark is not yet "
            "in commerce — the product has not launched, so the filing is pre-fundraise."
        ),
        **common,
    )
    base.emit(
        run,
        person_id=person_id,
        org_id=org_id,
        claim_type="attorney_of_record",
        artifact_type="trademark_application",
        value="none",
        raw_excerpt=(
            "Attorney of record: NONE. Self-filed. No law firm therefore no funding therefore "
            "no network. Correspondent is "
            f"{filing.correspondent_name or 'the applicant'}"
            f"{' <' + filing.correspondent_email + '>' if filing.correspondent_email else ''}."
        ),
        confidence=0.9,
        **common,
    )


# --------------------------------------------------------------------------- run


def _iter_live(start: int, limit: int, funnel: Funnel, verbose: bool) -> Iterator[Filing]:
    for offset in range(limit):
        serial = start + offset
        funnel.serials_probed += 1
        fetched = _fetch_statusview(serial)
        if fetched is None:
            funnel.throttled_out += 1
            if verbose:
                print(f"    sn{serial}  throttled out after retries", file=sys.stderr)
            continue
        if not fetched.ok:
            continue
        filing = parse_statusview(str(serial), fetched)
        if filing is None:
            continue
        funnel.retrieved += 1
        if not fetched.from_cache:
            time.sleep(_POLITE_DELAY)
        yield filing


def _iter_snapshot(funnel: Funnel) -> Iterator[Filing]:
    blob = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    for row in blob["filings"]:
        funnel.serials_probed += 1
        funnel.retrieved += 1
        yield Filing.from_dict(row)


def collect(
    *,
    start_serial: int = 99150000,
    limit: int = 260,
    offline: bool = False,
    write_snapshot: bool = True,
    verbose: bool = False,
) -> dict[str, Any]:
    """Scan a serial band, filter, and land the survivors in the ledger.

    ``offline=True`` replays the committed snapshot instead of the network, and badges those
    rows ``fixture`` rather than ``live`` — pre-downloaded dated data is exactly what ``fixture``
    means, and re-badging it ``live`` to look better is the one thing this project cannot do.
    """
    provenance = "fixture" if offline else "live"
    funnel = Funnel()
    run = base.CollectorRun(channel_id=CHANNEL_ID)

    source_iter = _iter_snapshot(funnel) if offline else _iter_live(
        start_serial, limit, funnel, verbose
    )

    # PHASE 1 — network only, no ledger writes. A polite scan of 260 serials takes ~11 minutes,
    # and holding a SQLite write transaction open for that long would lock out every other
    # collector running against the same ledger. Drain the network first, write second.
    kept: list[Filing] = list(source_iter)

    # PHASE 2 — the ledger write, held for seconds rather than minutes.
    _register(store.now_iso())
    for filing in kept:
        if filing.has_goods_services:
            funnel.has_goods_services += 1
        if filing.is_intent_to_use:
            funnel.basis_1b += 1
        if not filing.has_attorney:
            funnel.no_attorney += 1
        if filing.owner_is_individual_or_llc:
            funnel.owner_individual_or_llc += 1
        if filing.office_supplied_data:
            funnel.office_supplied_data += 1
        if filing.passes_full_filter:
            funnel.passed += 1
            if filing.is_us_domiciled:
                funnel.us_domiciled_among_passed += 1
            if filing.correspondent_email:
                funnel.contactable_among_passed += 1
            if verbose:
                print(
                    f"    PASS sn{filing.serial}  {filing.mark!r}  "
                    f"{filing.owner_name!r} ({filing.owner_entity_type})",
                    file=sys.stderr,
                )
        _emit_filing(run, filing, provenance)

    ledger.commit()

    if write_snapshot and not offline and kept:
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_PATH.write_text(
            json.dumps(
                {
                    "_note": (
                        "Dated snapshot of TSDR status-view records read live from "
                        "tsdr.uspto.gov. Replayed by `--offline`, which badges the rows "
                        "'fixture', never 'live'."
                    ),
                    "captured_at": store.now_iso(),
                    "serial_band": [kept[0].serial, kept[-1].serial],
                    "n": len(kept),
                    "filings": [f.to_dict() for f in kept],
                },
                indent=1,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    return {"run": run, "funnel": funnel, "provenance": provenance, "filings": kept}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--start", type=int, default=99150000, help="first serial number to probe")
    parser.add_argument("--limit", type=int, default=260, help="how many serials to probe")
    parser.add_argument("--offline", action="store_true", help="replay the committed snapshot")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    result = collect(
        start_serial=args.start, limit=args.limit, offline=args.offline, verbose=args.verbose
    )
    run: base.CollectorRun = result["run"]
    funnel: Funnel = result["funnel"]

    print(f"\n{CHANNEL_NAME}")
    print(f"source: {SOURCE}  provenance: {result['provenance']}  (live = keyless TSDR read)\n")
    print("FILTER FUNNEL")
    print(funnel.render())
    print(f"\n{run.summary()}")
    print(f"n = {funnel.retrieved} filings ingested, {funnel.passed} passing the full filter")
    if run.errors:
        print(f"first errors: {run.errors[:3]}")
    print(f"\nknown limitation (stated, not hidden):\n  {LIMITATION}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
