# Counterproof

**An AI venture operating system that asks what evidence *should* exist — and prices the gap.**

Our entry for the [Hack-Nation 6th Global AI Hackathon](https://hack-nation.ai/) (18–19 July 2026),
**Challenge 02 — The VC Brain**, sponsored by Maschmeyer Group.

---

## What it does

Every venture sourcing tool asks *"who has already emitted a signal?"* — a question that returns
null, by construction, for a first-time founder with no GitHub, no funding and no network.

Counterproof asks a different question. For any claim — *"€41K MRR"*, *"500 users"*, *"technical
founder"* — it derives an **expected-evidence manifest** *before* it searches: the artifacts that
would be observable if the claim were true, each with a findability prior conditioned on the
founder's resource class. Then it looks for exactly those, and scores a likelihood ratio rather
than a sum of whatever it happened to find.

The consequence is that **absence counts as evidence only when absence was predicted to be
unlikely**:

- Against a founder inflating a deck, missing-but-expected evidence is a *refutation*. The claim
  goes red, with the receipt.
- Against a solo founder with no public code, the manifest itself predicted that absence — so it
  costs them nothing, and the interval stays **wide rather than low**.

That asymmetry is the whole product. Every other tool sums present signals, which structurally
punishes the invisible founder and rewards the loud one. Scoring the *gap* between expected and
observed is the same mechanism as the lie detector, which is why it is buildable in a day.

**Sourcing** runs on channels chosen so they can fire for someone with no track record at all —
self-filed trademark applications with an empty attorney field (someone is building, has no law
firm, therefore no funding, therefore no network), low-visibility Hacker News activity, live
domain payment endpoints, and arXiv preprints.

## How to run

Requires **Python 3.11+**, [**uv**](https://docs.astral.sh/uv/), and **Node 20+**.

### 1. The worker (ledger, scoring, collectors)

`uv` is the only supported path — it gives every teammate a byte-identical environment from
the committed `uv.lock`. Don't use pip or a manual venv.

```bash
uv sync                             # create the env from uv.lock
uv run python -m worker.init_db     # create db/counterproof.db from db/schema.sql
uv run python -m worker.seed        # load the hero dataset into the ledger
uv run python -m worker.prove_asof  # prove the point-in-time chokepoint holds
uv run python -m worker.timing      # first-signal-to-decision instrumentation
uv run python -m worker.export_demo # regenerate web/public/demo.json from the ledger
```

`prove_asof` is the one to run if you want to see the core architectural idea in ten seconds: it
re-reads the identical code path at four different `asof` dates and shows strictly fewer
observations visible at each earlier one. That is what makes trend *computed* rather than asserted.

### 2. The web app

```bash
cd web
npm install
npm run dev     # http://localhost:3000
```

The frontend is a **pure renderer over `web/public/demo.json`** — no database client, no API
routes, no client-side environment variables. This is deliberate: a backend bug at hour 20 cannot
break the demo.

### 3. Environment

Copy `.env.example` to `.env` and fill in your keys. `.env` is gitignored and must stay that way.

### The five views

| Route | What it shows |
|---|---|
| `/` | Signal Feed — ranked board, the raw ↔ pedigree-neutralized toggle, funnel counters, SLA clocks |
| `/person/per_mo` | Cold-Start Bench — prior weight, interval, expected-evidence manifest, founder score across two ventures |
| `/opportunity/opp_ledgerline` | Claims with per-claim trust states, and the receipt modal behind the contradiction |
| `/opportunity/opp_ledgerline/memo` | Investment memo — five required sections plus an explicit gaps block |
| `/honesty` | Days-of-edge per channel with honest `n`, the not-collected ledger, the recognition probe |

## Design commitments

These are load-bearing, not stylistic. They come from the challenge brief and we hold them
everywhere in the codebase:

- **No composite score, anywhere.** The three axes (Founder / Market / Idea-vs-Market) are scored
  independently and never averaged — Market is categorical precisely so it *cannot* be. Collapsing
  them would hide exactly the disagreement an investor needs to see.
- **Trust is per claim, not per company** — four states: verified, unverified, contradicted,
  absent-but-expected.
- **The Founder Score follows the person, not the company.** Append-only versions, never reset, so
  its history replays as a step function across different ventures.
- **Missing data is flagged, never fabricated.** The memo says "Cap table: not disclosed" because
  the renderer physically cannot invent it.
- **Every number carries its `n`.** If we can't state the sample size, the number doesn't ship.

## Docs

- [The concept, architecture and build plan](docs/IDEA.md)
- [Task assignments & ownership](docs/TASKS.md)
- [Challenge briefs](docs/CHALLENGES.md) · [Competition schedule](docs/HACKATHON.md)
- [Submission checklist](docs/SUBMISSION.md)

## Team

- Alexandre Dalban
- Ali
- Wacil
