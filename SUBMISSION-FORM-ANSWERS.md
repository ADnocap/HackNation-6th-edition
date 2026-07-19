# Submission form — copy/paste answers

> Scratch file. Not committed. Delete after submitting.
> Every number below was verified against the running system on 2026-07-19.

---

## 1. Problem & Challenge

Every venture sourcing tool asks the same question: **"who has already emitted a signal?"** For a first-time founder with no GitHub, no funding and no network, that question returns null by construction. So tools that promise to widen access mostly re-rank the people access already found.

Two failures follow, and they are the same failure:

- **The invisible founder is unscoreable.** Systems that sum the evidence they find structurally punish whoever left the least behind — which correlates with capital and connections, not with capability.
- **The loud founder is over-scored.** A polished deck asserting €41K MRR gets taken at face value, because nobody checks what *should* be observable if that were true.

The challenge brief warns about exactly this: generic ingestion that ignores the cold-start case scores poorly, because it rebuilds the network gate the challenge exists to replace.

## 2. Target Audience

**Primary: the investor at an early-stage fund** who has to commit a $100K check inside 24 hours, on a founder nobody has vetted, and needs to know which parts of the story survived a check and which did not — without becoming a data engineer to find out.

**Secondary, and the reason this matters: the founder the current system cannot see.** A first-time builder with no GitHub, no funding and no warm intro. Counterproof is designed so that having left no trace is not evidence against you — it is a wider interval, not a lower score.

Configurable by design: the Thesis Engine takes sectors, stage, geography, check size, ownership target and risk appetite, so it is not hardcoded to one fund's shape.

## 3. Solution & Core Features

**Counterproof asks what evidence *should* exist if a claim were true, then prices the gap.**

For any claim — "€41K MRR", "500 users", "technical founder" — the system derives an **expected-evidence manifest** *before* it searches: the artifacts that would be observable if the claim held, each with a findability prior conditioned on the founder's resource class. It then looks for exactly those and scores a likelihood ratio, rather than summing whatever it happened to find.

**Sourcing (4 live collectors, all cold-start-native).** A channel qualifies as discovery only if it can fire for someone with no GitHub, no funding and no network — enforced in code, not policy. The flagship is **self-filed trademark applications with an empty attorney-of-record field**: one boolean that means someone is building, has no law firm, therefore no funding, therefore no network. A trademark is ~$250 against a patent's $10K+, so it is the unfunded first-time founder's IP move. Plus low-visibility Hacker News activity (scored on comment *text*, never karma), arXiv preprints, and live domain payment-endpoint probes. GitHub is present as a **confirmation** source keyed to a person we already found — never as discovery, because ranking repos by stars is track-record sourcing with extra steps.

**Memory.** A single append-only ledger, enforced by database triggers — `UPDATE` and `DELETE` are rejected, so the Founder Score cannot be reset. Every read passes through one chokepoint taking an `asof` and filtering `WHERE observed_at <= :asof`. Set it to now and it is a live brain; set it to a past date and the identical code is a point-in-time backtest.

**Intelligence.** Per-claim trust in four states (verified / unverified / contradicted / **absent-but-expected**), with itemised log-odds against a published source-reliability table. Three independent axes — Founder, Market, Idea-vs-Market — never averaged; Market is categorical precisely so it cannot be. A persistent per-person Founder Score that follows the human across ventures. Leave-one-evidence-out attribution by genuine recomputation.

**Experience.** Five views: ranked board with an access-neutralisation toggle, Cold-Start Bench, claims with receipts, investment memo with a typed decision, and an Honesty panel of our own limitations.

## 4. Unique Selling Proposition (USP)

**One line of arithmetic does two jobs that every competitor does separately or not at all:**

```
llr_absent = log( (1 − p_true) / (1 − p_false) )
```

- Against a founder **inflating a deck**, missing-but-expected evidence is a *refutation* — the claim goes red, with the receipt.
- Against a **founder with no public footprint**, the manifest predicted that absence, so the term is **exactly zero** — it costs them nothing, and the interval stays *wide rather than low*.

No special case, no branch to forget. The lie detector and the cold-start engine are the same code. You can watch this on screen: in the leave-one-out panel, the expected-and-absent evidence has a recomputed delta of **−0.00**.

**What else is genuinely different:**

- **Absence is a first-class, visible object.** The UI gives it its own material — a diagonal hatch, in two variants: graphite where the reference class predicted the gap (costs nothing), indigo where it did not (priced). Most tools render missing data as faded-out. Fading says "this matters less"; hatching says "this region is deliberately blank, and we know it."
- **Trend is computed, not asserted.** Axes re-score at `asof−90/−60/−30/0` through the same chokepoint. On the current ledger the Founder axis falls 4.4 points and the label still reads **stable**, because the OLS band includes zero.
- **We delete our own best statistics.** Conformal coverage, Benjamini-Hochberg and an SPRT operating characteristic were all cut — none has a target variable or null distribution inside 21 hours, and a tautological number in front of a finance-native sponsor is worse than none.
- **We report the leakage probe instead of a hit rate.** Asked to identify 15 redacted pre-fame artifacts, the model got 9. That is memory, not skill, so we publish no retrodiction accuracy at all.

## 5. Implementation & Technology

**Worker** — Python 3.11, managed with `uv` (locked, one command to reproduce). Append-only SQLite ledger, schema written in a Postgres-compatible subset. `httpx` + `selectolax` for retrieval, stdlib/`statistics` for modelling. Roughly: empirical-Bayes reference-class shrinkage with `k` fitted by method of moments (and explicitly *borrowed* where unidentifiable, rather than silently clamped), log-odds accumulation, OLS trend bands, distribution-free order-statistic intervals.

**Frontend** — Next.js 15 (App Router), TypeScript, Tailwind. A **pure renderer** over a committed `demo.json`: no database client, no API routes, no client-side environment variables. Deliberate — a worker bug cannot break the demo.

**LLM** — structured-output extraction and claim typing only. The model never emits a score and never writes prose; scoring is closed-form, which is what makes leave-one-out attribution exact rather than a story the model tells about itself. **Tavily** for verification of entities already indexed on the public web, kept rigidly separate from direct retrieval (a search index has never crawled a page published an hour ago, and zero results look identical to a failed check).

**Engineering decisions that carry weight:**

- Append-only enforced by **database triggers**, not convention. The rejection message reads: *"observation rows are facts, not state. Corrections are appended as a new row."*
- Every external response **cached by content hash from the first commit** — a full rebuild is network-free and takes ~2 seconds. This paid for itself twice when the ledger was accidentally wiped: recovery cost zero API calls.
- A **privacy gate** in the exporter refuses to publish if any real person's name reaches the rendered file. We build scored dossiers on real people from public records; they appear pseudonymised.
- An **n-audit** runs on the exact bytes before publish — a rendered number without its sample size fails the build.
- A **verification pass** (`worker.verify.check`) fetches every cited evidence URL and asserts the excerpt is actually present, treating a 404 as a first-class pass where absence was predicted. It exits non-zero on any drift.

## 6. Results & Impact

**Live data, not a mock.** 1,815 observations across 845 people, of which **1,789 were fetched live**: arXiv 773, USPTO TSDR 583, Hacker News 431, domain probes 14. Four working collectors, every one able to fire for a founder with no track record.

**The architecture is demonstrable in ten seconds.** `prove_asof` re-reads the identical code path at four dates: **759 → 943 → 1,213 → 1,815** observations visible. That is what makes point-in-time replay real rather than claimed.

**Decision-ready, and instrumented honestly.** Median first-signal-to-decision is **41 minutes** excluding founder-response wait, **372 minutes** including it (n=3, flagged thin). And the reliability half the brief asks for and almost nobody implements: **11.5% reached a decision, 34.6% stalled**, with the stalling stage named. That second number is not flattering, which is why it is on screen.

**Verifiable claims.** 26 evidence checks, **0 mismatches**, 17/17 live URLs resolving with real fetch timestamps, both deliberate 404s passing as expected-absent. 12 blocks of the rendered output are computed from the ledger rather than authored, and `meta.provenance_of_this_file` records exactly which — so the split is auditable rather than asserted.

**Impact.** The trademark channel alone surfaced founders who are *transacting today* with no funding, no GitHub and no press — people no ranked-by-visibility tool returns. Our own days-of-edge table says the honest thing about it: arXiv is **fully censored** — 530 people surfaced, zero the market has noticed yet, reported as a lower bound still running rather than a median we do not have.

That is the point. A system that surfaces founders the market has not priced, prices its own uncertainty, and refuses to invent the numbers it lacks.

---

## What was your most fun moment during the hackathon?

> **Edit this to be true for you** — it should be your moment, not mine. Here is the one I would tell:

The verification layer went in around 4am, hours after we had already written all our evidence and deployed our fixture sites. Its job is to fetch every URL we cite and check the quote is actually on the page.

First run, it failed on our flagship claim. Our data asserted the trademark had **no attorney of record** — the empty-attorney field is the entire basis of our cold-start sourcing argument. The live page said an attorney *was* present.

We had written the evidence and the fixture site independently and never reconciled them. If a judge had clicked that receipt mid-demo, our own page would have contradicted us on the one thing we claim to be best at.

And the page was right. The polished inbound company *should* have a law firm — the empty-attorney marker belongs to the cold-start founder, not to them. Our tool caught us making exactly the error it exists to catch, in the one place it would have hurt most, and the fix made the argument sharper than the version we meant to ship.

Watching your own lie detector go off on your own work at 4am is a strange kind of delight.
