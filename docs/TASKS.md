# Task assignments — Counterproof (Challenge 02, The VC Brain)

**Deadline: Sunday 19 July, 09:00 ET / 15:00 Paris.** Hard. No extensions.

Read `docs/IDEA.md` first — it is the agreed plan. Do not re-litigate it; implement it.
This file says *who builds what*. `CLAUDE.md` says *how we work together without stepping on each other*.

---

## The one rule that keeps this from falling apart

**You only edit files inside the directories you own.** Everything below is designed so that
three people can work for eighteen hours and merge with near-zero conflicts — but only if
nobody wanders. If you need a change in someone else's area, do not make it. Add a line to
`docs/HANDOFF.md` on your branch and tell them in chat.

| Area | Owner | Directories owned |
|---|---|---|
| Sourcing + verification | **Ali** | `worker/collectors/`, `worker/verify/` |
| Scoring & modelling | **Alexandre** | `worker/scoring/` |
| Demo assets & submission | **Wacil** | `demo-assets/` |
| Integration, memo, frontend, merges | **Claude/Alexandre** | `web/`, `worker/export_demo.py`, `worker/memo/`, `db/` |

**Contract files — read them, never edit them.** `db/schema.sql`, `worker/ledger.py`,
`worker/db.py`, `web/lib/types.ts`, `web/public/demo.json`. These are the interfaces everyone
depends on. If the schema needs a new column, ask — it takes two minutes and saves a merge war.

---

## Branches

```bash
git checkout feat/ali-sourcing        # Ali
git checkout feat/wacil-demo-assets   # Wacil
git checkout feat/alex-scoring        # Alexandre
```

All three already exist on `origin`. **Never commit directly to `main`** — Alexandre merges.

**Push at least every 45 minutes, even mid-task.** A hackathon has exactly one unrecoverable
failure mode and it is unpushed work on a laptop that dies. Commit messages can be terrible.

**Merge to `main` every ~3 hours, not once at the end.** Directories are disjoint, so a merge
should be seconds of work. Merging once tomorrow morning is how this project dies at hour 19.
Merge before you sleep, no matter what state you're in.

---

# ALI — Sourcing & Verification

You have the largest and highest-scoring block. **Sourcing is 30% of the grade and the brief
names it as the priority**: *"least commercial competition today — go further here than
anywhere else."* Everything you build lands in the ledger through `append_observation()`
and nothing else, which is why your work merges cleanly with everyone's.

**Design rule, enforced in code:** *a channel qualifies only if it can fire for a person with
no GitHub, no funding and no network.* Ranking GitHub repos by stars is track-record sourcing
with extra steps — it rebuilds the exact network gate this challenge exists to replace.

### A1 · USPTO self-filed trademarks — THE FLAGSHIP. Start here. (target: 2h)
This is our single best sourcing idea and no competitor mines it.

Filter to: **filing basis 1(b) intent-to-use** (product not launched → pre-fundraise by
definition), **TEAS Plus** (cheapest tier), **owner is an individual or an LLC under 180 days
old**, and — the load-bearing one — **the attorney field is empty**. That boolean does four
jobs at once: someone is building, they have no law firm, therefore no funding, therefore no
network. A trademark is ~$250 against a patent's $10K+, so it is the unfunded first-time
founder's IP move.

- Register for a USPTO API key immediately, but **cap the attempt at 15 minutes.** Identity
  verification can take hours. Then download the daily bulk XML and commit it as a dated
  fixture. The fixture *is the plan*, not the fallback.
- Capture the **goods-and-services free text verbatim** — it is a machine-readable statement
  of what the product is, and it feeds the Idea-vs-Market axis directly.
- Known limit, and we say it on camera: foreign applicants have needed US counsel since 2019,
  so the empty-attorney marker selects for US-domiciled founders. Name it before a judge finds it.
- **Done when:** ≥40 real filings in the ledger, ≥10 passing the full filter, goods-and-services
  text present on each, `provenance_class` set honestly.

### A2 · Hacker News via Algolia (target: 1h)
`hn.algolia.com/api/v1/search_by_date` — free, keyless, second-resolution timestamps, complete
history. **Not the front page** — the low-visibility surface: first-ever Show HN posts from
accounts under 90 days old, and long technical answers in domain threads where the author has
no other footprint.

Score the comment **text** for lived domain exposure. **Never score karma** — karma is a
popularity proxy and popularity is what we are explicitly trying not to rank on.

- **Done when:** ≥100 observations, each carrying a person handle, an utterance, and an exact timestamp.

### A3 · Domain page reading, not domain registration (target: 45min)
Everyone tracks *that* a domain was registered. Nobody fetches the page. For each candidate
domain, classify with `httpx` + `selectolax`: live Stripe/Paystack/Lemon Squeezy checkout
endpoint (**transacting today** — the highest-value bit in the entire domain signal), pricing
page, Calendly, dated changelog, waitlist form, or parked.

- **Done when:** it runs over every domain surfaced by A1 and A2, and at least our outbound
  hero classifies as *transacting today*.

### A4 · arXiv (target: 30min)
`export.arxiv.org/api/query` — free, keyless, no HTML parsing. The brief names five Identify
sources and we currently ship two; this is the cheapest compliance purchase available, and it
surfaces first-time academic founders with no company, no funding and no GitHub.
- **Done when:** ≥50 observations across our thesis sectors.

### A5 · Days-of-Edge channel scoring (target: 45min)
One `GROUP BY` over `observed_at`: median lag between a channel signal firing and that person
becoming consensus-visible (funding announcement, press, database entry). Pure date arithmetic,
so it cannot leak through model recognition and needs no outcome labels.

It produces the one sentence no other submission can say: *"GitHub Trending: zero days of edge.
It's beta. Everyone reads it. We defunded it."*

- **Every number carries its `n` and an honest error bar.** A channel at n=6 shows a wide bar
  and says so. This is a hard project rule — see `CLAUDE.md`.
- **Done when:** ≥4 channels in the table, including at least one with near-zero edge.

### A6 · Verification layer — `worker/verify/` (target: 1.5h)
**Read this carefully, it is the most catchable mistake in the build.**

**Split verification into two mechanisms and never confuse them:**
- `verify/fetch.py` — a direct `httpx.get(url)` returning the response body, the final URL and
  the fetch timestamp. This backs the demo's **receipt pane**. It is a *retrieval*:
  deterministic, offline-cacheable, works on a page published ten minutes ago.
- `verify/tavily.py` — Tavily, used **only** for claims about entities already indexed on the
  public web (market comparables, prior funding rounds). Tavily is a **search index, not a
  fetcher**. Our fixture sites go live around hour 10; Tavily will never have crawled them, so
  routing the hero verification through Tavily returns zero results and looks identical to
  "we couldn't check." That failure costs 80 minutes at hour 19 if we get it wrong.

**Cache every external response to disk by content hash from your very first commit** — not
later, not "once it works." Our OpenAI and Tavily budgets do not survive an uncached rebuild loop.

- **Done when:** a second run of the whole pipeline makes zero network calls, and every receipt
  carries a URL and a fetch timestamp.

### If you finish all of that
Take the **not-collected ledger**: a visible table of every source we declined (LinkedIn
headlines, GitHub stars, follower counts) with the reason for each. It scores better than a
broken scraper and it directly answers the brief's Area of Research 2. Then talk to Alexandre —
the next most valuable thing is the findability priors computed from your crawl.

---

# WACIL — Demo assets & submission

**You own the moment the whole demo is built around.** The peak of our three minutes is a lie
caught on camera *with the receipt* — the deck claims €41K MRR, and a live page fetch shows three
employees and a silent changelog. Both halves of that are your files. Judges remember one thing
from a pitch, and this is the thing.

It's also the most self-contained block on the project: `demo-assets/` has no dependencies on
anyone else's code, so you can move at your own pace without waiting on a merge.

### C1 · The hero pitch deck — do this first (target: 1.5h)
A 9-slide deck for a fictional **B2B fintech infrastructure** startup. Google Slides or
Canva is fine; export to PDF into `demo-assets/deck/`. It should look like a real seed deck —
plausible, a bit over-confident, not a parody.

**Plant exactly these four contradictions.** They must be consistent with the fixture sites in
C2, because our system catches them by cross-referencing the two:

1. **Slide 7 claims "€41K MRR, June 2026"** — but the changelog cadence and review volume on
   the fixture site imply well under 200 users.
2. **The deck claims 12 employees** — the fixture team page shows 3.
3. **The founding date precedes the first observable artifact by 14 months.**
4. **A cited market comparable that actually raised at a different stage** than claimed.

Also leave **one deliberate gap**: something a real deck would state and this one simply
doesn't (no cap table). Our memo flags it as "not disclosed" rather than inventing it, and
that flagging is worth points.

### C2 · The fixture sites — CRITICAL (target: 2h)
Three small static sites for the fictional company and its fictional customer: a **newsroom**,
a **changelog**, and a **team page**. Plain HTML and CSS. Ask your Claude to generate them.

**They must be deployed to real public URLs** — a free Vercel or GitHub Pages project is
perfect. This is not optional polish. Our validator performs a genuine HTTP GET against a
genuine domain and genuinely fails to find the claim. If those pages are served from
`localhost`, the best moment in our demo is indistinguishable from a mock, and a judge can tell.
Twenty extra minutes makes the peak forensically real.

Put the live URLs in `demo-assets/FIXTURE-URLS.md` the moment they're up, and tell Alexandre.

**Do not use LinkedIn as a fixture** — we publicly declined LinkedIn in our own not-collected
ledger, so citing it would contradict our own stated method. Use the team page or a job listing.

### C3 · Pseudonymization pass (target: 30min)
Any real person appearing anywhere in the demo gets reduced to initials + channel + signals.
We build scored dossiers on named private individuals from public records, so on camera they
are pseudonymous, the refuter is disabled on them, and outreach is drafted but never sent.
Go through `web/public/demo.json` **as a reader only** — list anything that looks like a real
identifiable person in `demo-assets/PSEUDONYMIZATION.md` and hand it to Alexandre to change.

### C4 · Outreach copy (target: 30min)
Draft the cold-outreach message the system sends an outbound founder. It is **not** "please
apply." It quotes the exact triggering observation with its date and URL, and asks for
counter-evidence to one specific claim. Two short paragraphs, in `demo-assets/outreach/`.

### C5 · Submission checklist — own this end to end (target: ongoing)
Nobody else will remember this and it is worth more than any feature. In `demo-assets/SUBMISSION.md`:
- The submission portal is https://projects.hack-nation.ai/ — find the form early, list every
  field it wants, and tell us what we're missing **while there's still time to build it**.
- A shot list for the 3-minute demo video, following section H of `docs/IDEA.md` beat by beat.
- At **07:00 ET / 13:00 Paris** we freeze. Your job is to verify the repo runs from a clean
  clone at that point — actually delete a copy, re-clone it, and follow the README.

### Checkpoint — 20:00 ET / 02:00 Paris
C1 and C2 gate the demo recording, so we need them by then. If anything is going to slip, flag it
early and we'll move people onto it — same rule applies to all three of us, since everything on
this project has a downstream dependency and late surprises are what actually cost us.

---

# ALEXANDRE — Scoring & modelling

The quant core. Owns `worker/scoring/`. This is the part nobody else on any team can do well,
so it is where the differentiation lives — but it is also the part most likely to eat hours
invisibly, so timebox hard and ship the cheap version first.

- **B1 · Empirical-Bayes founder score.** `θ̂ = w·(direct evidence) + (1−w)·(reference-class
  posterior mean)`, `w = n/(n+k)`. The reference class is `{artifact type, sector, solo/team,
  resource tier, region}` and contains **no pedigree field**. Append-only versions so the
  history replays as a step function across two ventures.
- **B2 · Log-odds trust engine** with a published, hand-set source-reliability table (founder
  self-report −1.2, press +0.2, third-party observable +1.1, primary registry filing +2.4).
  Print the table on screen — defending it line by line is what separates it from an LLM
  emitting `0.87`.
- **B3 · Expected-evidence manifest + findability priors.** The core mechanism. Priors computed
  empirically from Ali's crawl with cell counts shown and thin cells shrunk to the margin — not
  hardcoded. Absence widens the interval and **never lowers the score** when the prior predicted
  that absence.
- **B4 · Three axes + trend.** Independent, never averaged, no composite column anywhere. Market
  is categorical (bullish/neutral/bear) so it structurally cannot be averaged. Trend is computed
  by re-scoring at `asof−90/−60/−30/0`; label improving/declining only when the OLS slope band
  excludes zero, else render "insufficient dated observations (n=2)".
- **B5 · Leave-one-evidence-out attribution.** Exact and instant because the scorer is
  closed-form numpy, not an LLM. This is the FAQ's highest-leverage stretch goal implemented as
  *measurement* rather than the model narrating itself.
- **B6 · Thesis engine + compound NL query.** Six fields; risk appetite maps to the maximum
  acceptable posterior interval width at which capital deploys. The NL query resolves in **one
  pass** — constraints over *missing* attributes ("no prior VC backing") resolve as
  `P(satisfied | evidence)`, never as a hard filter, because a hard filter on absence deletes
  exactly the cold-start founders we exist to find.

**On the cut list, deliberately:** conformal prediction, Benjamini-Hochberg, SPRT operating
characteristics, Thompson sampling, and the pedigree R². Not because the maths is wrong but
because none of them has a target variable, a null distribution, or a sample size inside 18
hours. A tautological "79.4% coverage" in front of a finance-native sponsor is worse than no
number at all. See `docs/IDEA.md` section B.

---

# CLAUDE / ALEXANDRE — Integration

Memo renderer (five required sections + gaps block), typed decision card, timing and SLA
instrumentation, `export_demo.py`, frontend wiring, merges, staging deploy, and keeping `main`
green. Runs continuously; not blocking anyone.
