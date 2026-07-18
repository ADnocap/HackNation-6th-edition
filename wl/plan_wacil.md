# Wacil — execution plan for C1–C5 (demo-assets & submission)

Scope: `demo-assets/` only (per `CLAUDE.md` / `docs/TASKS.md`). This file exists so you don't
have to re-open `worker/demo_overrides.json` yourself mid-task — every number you need is below.

**Why this plan looks the way it does:** `worker/demo_overrides.json` (the hand-authored file
that drives everything shown in the demo) already specifies the *content* of the Ledgerline
story in full detail — exact numbers, exact evidence excerpts, exact claim IDs. Your job on C1
and C2 is to build the physical artifacts (deck PDF, real deployed pages) that make those
already-specified numbers **true and fetchable** — not to invent new contradictions. If your
deck says different numbers than the ones below, the deck and the fixture sites stop matching
each other, and the scoring/memo side (Alexandre + integration) has nothing consistent to build
against.

---

## 0. Fact sheet — copy/paste ground truth

**Company:** Ledgerline GmbH — incorporated 2026-03-22, registration HRB 284119, DACH region,
sector `b2b_fintech_infra`. Product: hosted settlement-reconciliation SaaS between payment
processors and merchant ledgers.

**Founder:** pseudonymized on-screen as **"D. R."** Previously operated a prior venture,
**Kestrel Ops (2024–2025)**, under a different name spelling. The system's entity-resolution demo
beat ("THE MOMENT" in `docs/IDEA.md` §H — the founder's credibility follows him across ventures)
depends on this merge working on a **shared code-host handle / registrant email domain**, never
on the name. Keep this in mind if you build the optional Kestrel Ops archive page below.

### The four planted contradictions

| # | Deck must claim | Fixture site must show | Maps to claim | State |
|---|---|---|---|---|
| 1 | **"€41K MRR, June 2026"** (slide 7 — quoted verbatim in the demo script, keep this exact phrasing) | Pricing page: 3 tiers, roughly €89 / €229 / €640 per month. Changelog: ~11 public reviews, 2 releases in the quarter, dated tags starting 2026-04-30, then goes quiet. Together these imply well under 200 users — an order of magnitude below the claim. | `clm_dr_mrr` | contradicted |
| 2 | **"12 employees"** | Team page names exactly **3** people | `clm_dr_headcount` | contradicted |
| 3 | **Founding date: June 2024**, "18 months of work behind the product" | First observable artifact (first commit / first changelog entry) is ~14 months *after* the claimed founding date | `clm_dr_founding` | contradicted |
| 4 | Cites a **named market comparable that raised at a €40M post** | The comparable actually raised at a different (later) stage than implied | `clm_dr_comparable` | unverified — softer: a misleading citation, not a hard fetch-fail |

### The deliberate gap (an omission, not a contradiction)

**No cap table anywhere in the deck.** This is what lets the memo print *"Cap table: not
disclosed"* instead of a fabricated number (`clm_dr_captable`). Also **omit post-money valuation
/ round terms** for the same reason (`clm_dr_round_terms`) — the decision card already renders
"cannot compute — post-money not disclosed" and needs this to stay true.

### What the deck should also state (true, not contradictory — gives the memo strengths to cite)

- Self-filed 1(b) trademark **with an attorney of record** — deliberately contrast this against
  the outbound hero Northgate's *no-attorney* filing; that contrast is itself a demo beat.
- Live Stripe checkout; ~19 weeks of sustained commit cadence.
- €180K stated pipeline, 14 design partners, <2% monthly churn, 4.1x LTV:CAC — leave these
  genuinely unverifiable. No fixture page should confirm or deny them. That's intentional: it's
  the "unverified" contrast against the 4 hard "contradicted" claims above.

### Pseudonymization — already a pattern, not a blank page

Every person already in `worker/demo_overrides.json` — both heroes ("D. R.", "M. O.") and all
16 background signal-feed entries — is already reduced to initials with fictional org names
(Corvid Data, Sable Ledger, Kestrel Freight, Auger Analytics, Gantry Labs, etc.). Treat C3 as an
**audit against this existing pattern**, not authoring from zero.

### Outreach — a first draft already exists

For the *outbound* hero (Northgate / "M. O.", not Ledgerline):

> "I came across your trademark filing from 2026-07-07 (serial 98/447,913) and the live checkout
> on northgatesettle.com. Before I form a view I'd rather ask than assume: you say 40 paying
> users — which channel produced the first ten, and is there a Stripe payout date I can check?"

C4 is polishing this into its own file, not inventing new copy.

---

## C1 · Hero pitch deck (~1.5h)

9 slides, Google Slides or Canva, export to PDF into `demo-assets/deck/`. Tone: plausible,
slightly over-confident seed deck — **not a parody**.

1. Title / company — Ledgerline, one-line pitch.
2. Problem — settlement records from payment processors and merchant ledgers drift apart;
   reconciling them is manual at mid-market scale.
3. Product — hosted reconciliation service, billed per settlement run. Match the
   goods-and-services phrasing style the system reads directly (plain description of what the
   product does).
4. Team — **state 12 employees** (contradiction #2).
5. Traction summary — high level, sets up slide 8's specifics.
6. Market sizing — cite the named comparable at a €40M post (contradiction #4).
7. **"€41K MRR, June 2026"** — the flagship number (contradiction #1). Use this exact phrasing.
8. KPIs — €180K pipeline, 14 design partners, <2% churn, 4.1x LTV:CAC (all left unverifiable).
9. Founding story — "18 months of work," founding date June 2024 (contradiction #3).

No cap table slide. No round-terms/post-money slide. That absence is the gap.

## C2 · Fixture sites — CRITICAL (~2h)

Plain HTML + CSS, no framework, no build step. **Deploy to real public URLs** (free Vercel or
GitHub Pages) — non-negotiable. The Validator performs a genuine `httpx.get()`; served from
localhost, the best moment in the demo is indistinguishable from a mock. Record every live URL
in `demo-assets/FIXTURE-URLS.md` the moment it's up.

Pages to build:

- **Newsroom / legal page** — states the trademark filing *with* an attorney of record (contrast
  vs. Northgate's no-attorney filing), incorporation details (HRB 284119).
- **Changelog** — dated release tags starting 2026-04-30, then silence. Enough entries to back
  "11 public reviews, 2 releases in the quarter."
- **Team page** — names exactly **3** people (contradiction #2). A job-board-style listing is
  fine too. **Never use LinkedIn** as a fixture source — it's already declined in the system's
  own not-collected ledger, and citing it would contradict that stated method on camera.
- **Customers page** — 3 named companies with logos, against the deck's 14 claimed design
  partners.
- **Pricing page** — 3 tiers (~€89/€229/€640/mo) plus a live-looking checkout endpoint (a Stripe
  test-mode button or equivalent), so the domain-transacting probe reads as genuine.
- **Optional stretch, but strongly recommended:** an archived **Kestrel Ops** page (imprint or
  team page), reachable via the *same code-host handle or registrant email domain* as
  Ledgerline — never the same founder name spelling, since the merge must key on
  handle/domain, not name. This backs "THE MOMENT" in the demo script — the single most-quoted
  beat. If you have to cut it for time, say so explicitly rather than letting it quietly vanish.

Author the deck (C1) and the fixture sites (C2) **together** — they're two halves of one puzzle
and must agree exactly on every number above.

## C3 · Pseudonymization audit (~30min)

Read `web/public/demo.json` as a **reader only** (don't edit `web/`). Confirm:
- Every `person_display_name` is initials-only.
- Every `org_name` is fictional.
- Check free-text fields too, not just the obvious name fields — evidence `excerpt`s,
  `challenge_text`/outreach bodies, bear-case bullets — for anything that slipped through.

List any finding in `demo-assets/PSEUDONYMIZATION.md` and hand it to the integration side
(Claude/Alexandre) rather than fixing it yourself.

## C4 · Outreach copy (~30min)

Polish the existing draft (quoted in the fact sheet above) into
`demo-assets/outreach/northgate.md` as two short paragraphs:
1. Quotes the exact triggering observation, with its date and URL.
2. Asks for counter-evidence to one specific claim.

Keep the "drafted, never sent" framing explicit in the file itself — this system drafts and
renders outreach but never actually sends it.

## C5 · Submission checklist (ongoing)

No new content needed — `docs/SUBMISSION.md` is already the authoritative checklist and already
assigned to you. Two things to start now:
- Find the submission portal's (https://projects.hack-nation.ai/) required fields and flag
  anything missing while there's still time to build it.
- Plan the clean-clone verification for the 07:00 ET / 13:00 Paris freeze — actually delete a
  copy, re-clone, follow only the README.

---

## Hand-off points to the Alexandre / integration side

- The real fixture URLs you record in `demo-assets/FIXTURE-URLS.md` need to eventually replace
  the placeholder `ledgerline.dev` URLs already baked into `worker/demo_overrides.json`'s
  evidence rows (`source_url`/`final_url`). That edit belongs to whoever owns
  `demo_overrides.json` (the integration lane) — note it, don't do it yourself.
- If you need to change any of the numbers in the fact sheet above, write it in
  `docs/HANDOFF.md` rather than silently diverging — the scoring engine and memo generator are
  both being built against the numbers currently in `demo_overrides.json`.
- Heads-up: `worker/seed.py`'s pricing figures ("99/399/custom" USD) currently disagree with
  `demo_overrides.json`'s richer version (€89/€229/€640). That's a pre-existing inconsistency
  for Alexandre to reconcile — build your fixtures against the `demo_overrides.json` numbers
  above, since that's what's actually rendered in the demo.
- `PSEUDONYMIZATION.md` findings route to the integration side, not to Alexandre directly.

## Timing

**Hard checkpoint: C1 + C2 done by 20:00 ET / 02:00 Paris** — they gate the demo recording. If
either is going to slip, say so early. Push every 45 minutes minimum, even mid-task. Never
commit directly to `main` — work on `feat/wacil-demo-assets`.