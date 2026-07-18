# CLAUDE.md — HackNation 6th Edition

## What this repo is

Our team's project for the **Hack-Nation 6th Global AI Hackathon & Venture Incubation Program** (July 18–19, 2026). It's a 24-hour AI build sprint. See `docs/HACKATHON.md` for full event info and `docs/SUBMISSION.md` for the deliverables checklist.

**Hard deadline: Sunday, July 19, 9:00 AM ET (3:00 PM Paris time).**

## Challenge

The 6 challenges are revealed and documented in `docs/CHALLENGES.md` (full briefs in `docs/assets/challenges/`). Fill in once we commit to one:

- **Challenge chosen:** 02 — The VC Brain
- **Sponsor:** Maschmeyer Group
- **One-line pitch:** TBD
- **Chosen track/vertical (if applicable):** n/a — scope is Sourcing → Screening → Diligence → Decision

Key constraints from the brief (`docs/assets/challenges/02-maschmeyer-vc-brain.pdf`):
- **Sourcing is the priority** and the **cold-start founder** (no GitHub / funding / network) must be handled explicitly — generic ingestion scores poorly.
- 3-axis screening (Founder / Market / Idea-vs-Market) is **never averaged**; each carries its own trend.
- **Founder Score** ≠ 3-axis score: it lives in Memory, persists across applications, never resets.
- **Trust Score is per claim**, not per company — every claim cites evidence + confidence, contradictions flagged.
- Memo required sections: Company snapshot, Investment hypotheses, SWOT, Problem & product, Traction & KPIs. Missing data must be **flagged, never fabricated**.
- Thesis Engine must be **configurable**, not hardcoded to one fund.
- Downstream (portfolio monitoring, follow-on, fund ops, exit) is **out of scope** — don't build UI for it.
- Weights: Data Architecture 30% · Analysis & Trust 25% · Investment Utility 30% · UX 15%.

## Stack (decided)

- **Frontend:** Next.js 15 (App Router) + TypeScript + Tailwind, in `web/`. A **pure renderer over
  `web/public/demo.json`** — no database client, no API routes, no client env vars. This is deliberate:
  a backend bug at hour 20 must not be able to break the demo video.
- **Backend/worker:** Python 3.11 in `worker/`, managed with **uv**. Local SQLite ledger at
  `db/counterproof.db` (gitignored); `db/schema.sql` is Postgres-compatible so it can be pasted into
  Supabase later for the on-camera "append-only ledger" prop.
- **AI/ML:** LLM with strict structured outputs for extraction and claim typing only — **the LLM never
  emits a score and never writes prose**. Scoring is closed-form numpy so leave-one-out attribution is
  exact. Tavily for verification of already-indexed public entities.
- **Deploy:** Vercel (static export). See "Staging" below.

## Team & ownership

Four-way split designed so people can work for eighteen hours and merge with near-zero conflicts.
Full task briefs are in `docs/TASKS.md`.

| Area | Owner | Owns |
|---|---|---|
| Sourcing + verification | **Ali** | `worker/collectors/`, `worker/verify/` |
| Scoring & modelling | **Alexandre** | `worker/scoring/` |
| Demo assets & submission | **Wacil** | `demo-assets/` |
| Integration, memo, frontend | **Claude/Alexandre** | `web/`, `worker/export_demo.py`, `worker/memo/`, `db/` |

**Contract files — read, never edit:** `db/schema.sql`, `worker/ledger.py`, `worker/db.py`,
`web/lib/types.ts`, `web/public/demo.json`. Need a schema change? Ask; don't just make it.

### If you are Claude working for a teammate — read this

**Stay in your lane. Do not build the whole product.** The other three areas are being actively
built by other people right now; anything you "helpfully" add there will be thrown away in a merge
conflict, or worse, will silently overwrite working code.

- Work **only** inside your owner's directories from the table above.
- **Never edit a contract file.** If your task genuinely needs a new column or a new demo.json field,
  write the request in `docs/HANDOFF.md` and tell Alexandre. Do not edit the schema.
- **Never commit to `main`.** Work on your branch (`feat/ali-sourcing`, `feat/wacil-demo-assets`,
  `feat/alex-scoring`). Alexandre merges.
- **Do not refactor, reformat, or "clean up" code you don't own.** Not even obvious improvements.
  A tidy diff in someone else's file costs more in merge time than it saves.
- **Push at least every 45 minutes**, even mid-task, even broken. Unpushed work on a dying laptop is
  the only unrecoverable failure in a hackathon. Commit messages can be terrible.
- If you finish your assigned work, **do not invent new scope** — check `docs/TASKS.md` for the
  "if you finish" note in your section, or ask.

### Branches

`main` is always green and only Alexandre merges into it. Merge branches into `main` roughly every
3 hours — not once at the end. Because the directories are disjoint, a merge should take seconds;
a big-bang merge at hour 19 is how this project dies.

## Non-negotiables (we lose points if these slip)

These come straight from the brief and the FAQ. They are cheap to preserve and expensive to retrofit.

- **No composite or averaged score. Anywhere.** Not in the schema, not in the UI. The three axes
  (Founder / Market / Idea-vs-Market) are independent, each with its own trend. Market is categorical
  (bullish/neutral/bear) precisely so it cannot be averaged.
- **Trust Score is per claim**, never per company. Four states: verified / unverified / contradicted /
  absent-but-expected.
- **Founder Score is per person**, persists across companies, never resets, append-only versions.
  It is one *input* to the Founder axis, not a substitute for it.
- **Never fabricate a missing data point.** Flag it ("Cap table: not disclosed"). A memo that marks
  its own gaps scores as *more* trustworthy, not less.
- **Every number on screen carries its `n`.** If we can't state the sample size, the number gets
  deleted rather than shipped. One unearned statistic in front of a finance-native sponsor discredits
  the whole honesty pitch.
- **Absence only counts against a founder when the prior predicted that absence.** Missing evidence
  widens the interval; it does not lower the score. This is the anti-network-gate, and it is the one
  thing a generalist team won't converge on.
- **Sourcing channels must be able to fire for someone with no GitHub, no funding, no network.**
  Ranking GitHub repos by stars is track-record sourcing with extra steps.
- **Downstream is out of scope** — portfolio monitoring, follow-on, fund ops, exit. Not even a nav item.

## Staging

Deploy to **Vercel**, not to the Hetzner box at `89.167.101.136`. That box runs the `taut-prod`
trading stack and holds a live wallet key; a judge-facing URL should not resolve to the same machine.
The frontend is a static renderer, so `next build` output deploys anywhere with zero config.

Sponsor credits are available (OpenAI API, Lovable, Cursor, Vercel, Supabase, ElevenLabs, Tavily, Databricks — ~$150K+ pool during the event). Prefer sponsor tools where they fit; judges from sponsor challenges like seeing their tech used.

## How to work in this repo (hackathon mode)

This is a 24-hour sprint, not a production codebase. Priorities, in order:

1. **A working demo beats everything.** Judges see a ~3-minute pitch and a demo. Optimize for the happy path that will be shown live; do not build for edge cases nobody will trigger.
2. **Ship vertical slices.** Get an end-to-end skeleton (input → AI → output visible in UI) working as early as possible, then improve pieces. Never leave the app in a broken state for long.
3. **Commit early, commit often.** Small commits directly on `main` are fine during the sprint. No PR ceremony unless we're touching something fragile near the deadline.
4. **Don't gold-plate.** No test suites, no CI, no abstractions for hypothetical futures. Hardcode config, mock what's slow, stub what's not demo-visible. Mark shortcuts with `# HACK:` comments so we can find them later.
5. **Freeze early.** In the last ~2 hours before the deadline, stop adding features: record the demo video, write the README, verify the submission runs from a clean clone.

## Things Claude should do proactively

- Keep the README's "how to run" section accurate as the stack evolves — judges may try to run it.
- When adding an API key or service, add it to `.env.example` and make sure `.env` is gitignored.
- Prefer boring, well-known libraries over clever ones; there is no time to debug exotic dependencies.
- If a task risks taking more than ~30 minutes without visible progress, say so and propose a cheaper path.

## Resources available

- The user has GPU access on the LaRuche HPC cluster (A100s, see global instructions) if the challenge needs model training/fine-tuning — but only reach for it if an API model genuinely can't do the job; the round-trip cost is high in a 24h window.
- Sponsor API credits (details announced with the challenges).
