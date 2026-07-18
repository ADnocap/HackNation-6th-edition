# Hero deck — Ledgerline (C1)

**AUTHORED fixture.** This deck was written by us, not received from a founder. We planted four
contradictions and one gap on purpose; the demo's validator catches them by cross-referencing
the fixture sites (C2). See `wl/plan_wacil.md` for the full fact sheet.

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

## What's planted where

| Slide | Claim | Type |
|---|---|---|
| 1 | Ledgerline GmbH, Berlin, HRB 284119, incorporated | verified (imprint fixture) |
| 2 | Founded January 2025 · 18 months of engineering | **contradiction #3** — first commit 2026-03-04, first TLS 2026-03-22 (14 months later) |
| 3 | Live and accepting payment, €89/€229/€640 tiers | verified (pricing + checkout fixtures) |
| 4 | 12 employees | **contradiction #2** — team page names 3 |
| 5 | Trademark serial 98/441,207, filed 2026-04-08, attorney of record | verified — deliberate contrast vs. Northgate's no-attorney filing |
| 6 | €2.4B market; comparable **Tallystack** raised at €60M post "in this exact wedge" | **contradiction #4** — Tallystack raised at Series A, not this stage (unverified, misleading not false) |
| 7 | **€41K MRR, June 2026** | **contradiction #1** — changelog cadence + 11 reviews imply <200 users |
| 8 | €180K pipeline · 14 design partners · <2% churn · 4.1x LTV:CAC | deliberately unverifiable (state stays "unverified", not contradicted) |
| 9 | "Raising our seed round" — **no post-money, no instrument, no cap table anywhere** | **the gap** — memo renders "Cap table: not disclosed" |

## Names that must stay in sync with the C2 fixture sites

- Founder: **Daniel Rehmke** (on-screen pseudonym "D. R."; prior venture Kestrel Ops uses a
  *different spelling* — the entity merge keys on handle/email-domain, never the name).
- Team page must name exactly these 3: Daniel Rehmke, Mara Vogel, Jonas Pfeiffer.
- Fictional comparable: **Tallystack** (invented company — keep it invented).
- Contact/domain in the deck: `ledgerline.dev` — placeholder until C2's real fixture URLs land
  in `demo-assets/FIXTURE-URLS.md` (integration then updates `demo_overrides.json`, not us).
