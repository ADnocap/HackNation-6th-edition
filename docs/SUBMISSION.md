# Submission Checklist — Counterproof (Challenge 02, The VC Brain)

**Deadline: Sunday 19 July, 09:00 ET / 15:00 Paris. Feature freeze 07:00 ET / 13:00 Paris.**
**Portal: https://projects.hack-nation.ai/**

This is the authoritative checklist — don't create a
second one in `demo-assets/`.

> **Find the submission form early.** List every field it asks for and tell the team what we're
> missing *while there's still time to build it*. Discovering a required field at 08:30 is the
> single dumbest way to lose this.

---

## C5 status log

**Portal fields (18–19 July):** https://projects.hack-nation.ai/ is a JS-rendered app — the
form is not visible without logging in with the event account. **Manual action, do this at the
next break:** log in, open the submission form, and screenshot every field. Based on the
deliverables list, expect at minimum: project name · challenge selection (02) · description /
one-pager text · public repo URL · demo video URL · team members. Anything beyond that
(staging URL, tech-stack fields, sponsor-tool usage) we need to know **before** the freeze.

**Clean-clone dry run (night of 18→19 July, done early instead of waiting for 07:00 ET):**
fresh `git clone` of `main` into a scratch directory —
- `web/public/demo.json` present ✓
- `cd web && npm install` ✓ (53 packages, 19s)
- `npm run build` ✓ — compiles, types check, all 5 routes build
- **Worker path not testable on this machine: `uv` is not installed here.** The README's
  worker steps (`uv sync`, `init_db`, `seed`, `prove_asof`, `export_demo`) still need a run
  from a machine with uv before freeze — flag to whoever has one, or install uv locally
  before the 07:00 ET check.

**Demo video shot list:** written, beat-by-beat with routes, spoken lines, per-beat visibility
requirements, the 2:30 backup cut, and fallbacks. Record the first
full take EARLY; it is the submission until a better one exists.

---

## Deliverables

- [ ] **Public GitHub repo** — README states what it does, the challenge, how to run it, the team.
- [ ] **Demo video (~3 min)** — screen recording of the real product, following `docs/IDEA.md` §H
      beat by beat. Unlisted YouTube/Loom as backup. **Record a full take by ~15:00 ET Sunday,
      not at the end** — an unrecorded masterpiece scores zero, and because the frontend renders
      from a committed `demo.json` we can record a complete take while features are still landing.
- [ ] **Write-up / one-pager** — problem, mechanism, what's next. Padding counts against us.
- [ ] **Submission form filled** — every team member listed.
- [ ] **Staging URL live** (Vercel) and reachable in incognito.

## Scorecard — how we are actually judged

Self-check against the published weights before submitting. Be honest; a gap we know about is
cheaper than one a judge finds.

### Data Architecture & Intelligence — 30%
*"Smart ingestion, deduplication, enrichment, and a reasoning layer honest about what it knows."*
The brief warns explicitly that generic ingestion **scores poorly if it ignores cold start**.

- [ ] Sourcing depth: ≥3 live collectors, each able to fire for someone with no track record
- [ ] Cold-start method is a real mechanism (reference-class prior + findability-conditioned
      absence), visible in a named UI module — not an afterthought
- [ ] Append-only ledger, source-tagged, timestamped, deduplicated on a person spine
- [ ] `asof` chokepoint demonstrable: earlier date → strictly fewer observations, identical code
- [ ] "Not collected, and why" ledger visible on screen

### Intelligent Analysis & Trust — 25%
- [ ] Trust Score is **per claim**, four states, never a company-level mean
- [ ] Every claim traces to evidence with a confidence level; contradictions flagged before the
      investor sees them
- [ ] Receipt shows the exact data point — slide crop + live-fetched page with URL and timestamp
- [ ] Uncertainty shown as an interval, and absence widens it rather than lowering the score
- [ ] Every number on screen carries its `n`

### Investment Utility & Execution — 30%
- [ ] A recommendation a human investor could act on within 24h: typed decision card, conditions
      to close, kill criteria, binding + dissenting axis
- [ ] Memo has **exactly the five required sections** (Company snapshot, Investment hypotheses,
      SWOT, Problem & product, Traction & KPIs) plus a gaps block. No padding.
- [ ] Missing data flagged, never fabricated ("Cap table: not disclosed")
- [ ] **Time from first signal to decision is instrumented** — elapsed per opportunity, cohort
      median, and the *reliability* half (% reaching decision vs stalled, and at which stage).
      The criterion names this explicitly and almost nobody implements it.
- [ ] 24-hour SLA clock visible per opportunity

### User Experience & Design — 15%
- [ ] All five views usable without explanation; plain-language line above every quant panel
- [ ] Compound NL query resolves in **one pass** with the parse rendered as chips (a chat UI
      firing five sequential filters actively fails this requirement)

## Things that lose points — verify none have crept in

- [ ] **No composite or averaged score** anywhere in schema or UI. Grep for it.
- [ ] Three axes independent, each with its own trend, and an AXES DISAGREE state when they conflict
- [ ] Founder Score is per-person, append-only, spans two ventures on camera, never resets
- [ ] Nothing built for out-of-scope downstream stages (portfolio monitoring, follow-on, fund ops,
      exit) — not even a nav item
- [ ] Thesis Engine is configurable, not hardcoded to one fund
- [ ] No number on screen without a defensible `n`
- [ ] Real people pseudonymized; outreach drafted but never sent

## Pre-submission sanity checks

- [ ] **Clean clone test** — actually delete a copy, re-clone, follow only the README. `uv sync`
      then `npm install && npm run dev`. If it doesn't work, the README is wrong.
- [ ] No secrets committed — `.env` gitignored, `.env.example` present and current
- [ ] Demo happy path run three times in a row without failure
- [ ] Video uploaded and link tested in incognito
- [ ] All three team members listed

## If we make finals (top 3 of the challenge)

- [ ] 3-minute pitch, Saturday 25 July, 12:00–14:00 ET / 18:00–20:00 Paris, public.
- [ ] Structure: problem (30s) → live demo (90s) → impact & venture potential (45s) → close (15s).
- [ ] Pre-recorded demo fallback ready in case the live one breaks.
