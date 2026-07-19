# Hero deck — Ledgerline (C1)

**AUTHORED fixture.** This deck was written by us, not received from a founder. We planted four
contradictions and one gap on purpose; the demo's validator catches them by cross-referencing
the fixture sites (C2).

## Files

- `ledgerline-deck.html` — source of truth. Plain HTML/CSS, one 960×540pt page per slide.
- `ledgerline-seed-2026.pdf` — the export the pipeline parses. Filename is contractual
  (`worker/demo_overrides.json` → `deck.filename`).

## Regenerate the PDF

```powershell
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --headless --disable-gpu `
  --no-pdf-header-footer `
  --print-to-pdf="demo-assets\deck\ledgerline-seed-2026.pdf" `
  "file:///.../demo-assets/deck/ledgerline-deck.html"
```

## Load-bearing geometry — do not reflow

`worker/demo_overrides.json` hardcodes two slide-crop bboxes against 960×540pt pages
(pdfplumber coordinates, origin top-left):

| Page | bbox | Text that must sit inside it |
|---|---|---|
| 2 | [70, 156, 498, 204] | `Founded January 2025 · 18 months of engineering` |
| 7 | [64, 388, 512, 452] | `€41K MRR, June 2026 · 12 employees · founded January 2025` |

Both are absolutely positioned in the HTML and verified by cropping the PDF with pdfplumber.
If you edit the deck, re-run that check before committing.

## Structure — real-deck anatomy inside contractual slide numbers

The slide *numbers* are fixed by `demo_overrides.json` (`deck_slide` per claim), so the deck
follows real seed-deck anatomy (cover → problem → solution/product proof → team → moat &
alternatives → bottom-up market → traction chart → unit economics → milestone-driven ask,
per YC / VeryCreatives 2026 structure guides) *within* those positions: the cover carries a
one-line metric teaser, slide 2 is problem-framed with quantified pain, slide 3 shows a
product-UI mock as proof it's real, slide 6 does the market bottom-up (43K merchants × €4.6K
ACV ≈ €200M SOM inside €2.4B TAM), slide 7 has an MRR bar chart (Jan→Jun 26, ending €41K —
deliberately consistent with the deck's own founding lie, and inconsistent with the fixture
changelog), and slide 9 states milestones + use-of-funds with **no round amount, no
post-money, no instrument**.

## What's planted where

| Slide | Claim | Type |
|---|---|---|
| 1 | Ledgerline GmbH, Berlin, HRB 284119, incorporated | verified (imprint fixture) |
| 2 | Founded January 2025 · 18 months of engineering | **contradiction #3** — first commit 2026-03-04, first TLS 2026-03-22 (14 months later) |
| 3 | Live and accepting payment, €89/€229/€640 tiers | verified (pricing + checkout fixtures) |
| 4 | 12 employees | **contradiction #2** — team page names 3 |
| 5 | Trademark serial 98/441,207, filed 2026-04-08, attorney of record | verified — deliberate contrast vs. Northgate's no-attorney filing |
| 6 | €2.4B market; comparable **Tallystack** raised at €60M post "in this exact wedge" | **contradiction #4** — Tallystack raised at Series A, not this stage (unverified, misleading not false) |
| 7 | **€41K MRR, June 2026** + growth chart Jan–Jun 26 | **contradiction #1** — changelog cadence + 11 reviews imply <200 users; the chart's Jan–Apr bars predate the first public release (2026-04-30), reinforcing #1 and #3 |
| 8 | €180K pipeline · 14 design partners · <2% churn · 4.1x LTV:CAC | deliberately unverifiable (state stays "unverified", not contradicted) |
| 9 | "Raising our seed round" — **no round amount, no post-money, no instrument, no cap table anywhere** | **the gap** — memo renders "Cap table: not disclosed", decision card renders "ownership: cannot compute" |

## Names that must stay in sync with the C2 fixture sites

- Founder: **Daniel Rehmke** (on-screen pseudonym "D. R."; prior venture Kestrel Ops uses a
  *different spelling* — the entity merge keys on handle/email-domain, never the name).
- Team page must name exactly these 3: Daniel Rehmke, Mara Vogel, Jonas Pfeiffer.
- Fictional comparable: **Tallystack** (invented company — keep it invented).
- Contact/domain in the deck: `ledgerline.dev` — placeholder until C2's real fixture URLs land
  in `demo-assets/FIXTURE-URLS.md` (integration then updates `demo_overrides.json`, not us).
