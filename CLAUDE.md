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

## Stack (fill in once decided)

- **Frontend:** TBD
- **Backend:** TBD
- **AI/ML:** TBD
- **Deploy:** TBD

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
