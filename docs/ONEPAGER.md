# Counterproof — one-pager

**Challenge 02 · The VC Brain · Maschmeyer Group**
Repo: https://github.com/ADnocap/HackNation-6th-edition

---

## The problem

Every venture sourcing tool asks *"who has already emitted a signal?"* — a question that returns
**null, by construction**, for a first-time founder with no GitHub, no funding and no network.
So the tools that promise to widen access mostly re-rank the people access already found. The
brief warns about exactly this: generic ingestion that ignores the cold-start case scores poorly,
because it rebuilds the network gate the challenge exists to replace.

## The idea

Counterproof asks a different question: **what evidence *should* exist if this claim were true?**

For any claim — "€41K MRR", "500 users", "technical founder" — the system derives an
**expected-evidence manifest** *before* it searches: the artifacts that would be observable if the
claim held, each with a findability prior conditioned on the founder's resource class. Then it
looks for exactly those, and scores a likelihood ratio rather than a sum of whatever it happened
to find.

The consequence is one line of arithmetic that does two jobs:

```
llr_absent = log( (1 - p_true) / (1 - p_false) )
```

- Against a founder **inflating a deck**, missing-but-expected evidence is a *refutation*. The
  claim goes red, with the receipt.
- Against a **solo founder with no public code**, the manifest itself predicted that absence — the
  term is exactly zero, so it costs them nothing and the interval stays **wide rather than low**.

No special case, no branch to forget. Every other tool sums present signals, which structurally
punishes the invisible founder and rewards the loud one. Scoring the *gap* is simultaneously the
lie detector and the cold-start engine — which is why it was buildable in a day.

## What it does

**Sourcing** runs on channels chosen so they can fire for someone with no track record at all.
The flagship is **self-filed trademark applications with an empty attorney field** — one boolean
that does four jobs: someone is building, they have no law firm, therefore no funding, therefore
no network. A trademark is ~$250 against a patent's $10K+, so it is the unfunded first-time
founder's IP move. Plus low-visibility Hacker News activity (scored on text, never karma), arXiv
preprints, and live domain payment endpoints. **1,815 observations across 845 people**, collected
live.

**Memory** is a single append-only ledger, enforced by database triggers — `UPDATE` and `DELETE`
are rejected, so the Founder Score *cannot* be reset. Every read goes through one chokepoint that
takes an `asof` and filters `WHERE observed_at <= :asof`. Set it to now and it is a live VC brain;
set it to a past date and the identical code is a point-in-time backtest. That is why **trend is
computed rather than asserted**.

**Intelligence** scores three axes independently — Founder, Market, Idea-vs-Market — and never
averages them. Market is categorical precisely so it *cannot* be. Trust is per claim, in four
states including `absent_but_expected`, with the log-odds arithmetic itemised down to each source's
published reliability weight.

## Why you can believe the numbers

- **Every number carries its `n`.** A mechanical audit runs on the exact bytes before publish; a
  quantity without a sample size fails the build.
- **We deleted our own best statistics.** Conformal coverage, BH-FDR and an SPRT operating
  characteristic were all cut — none has a target variable or a null distribution inside 21 hours,
  and a tautological number in front of a finance-native sponsor is worse than none.
- **Our days-of-edge table reports what it can support**, not what we wish. arXiv shows
  `fully_censored`: 530 people surfaced, *zero* the market has noticed — a lower bound still
  running, not a median we do not have.
- **The Founder axis falls 4.4 points and the label still says "stable"**, because the OLS band
  includes zero. A system that watches a number drop and declines to call it a trend is the whole
  posture in one line.
- **Missing data is flagged, never fabricated.** "Cap table: not disclosed" is there because the
  renderer physically cannot invent it.
- **A privacy gate blocks publish** if any real person's name reaches the rendered file.

## Honest limits

We are not claiming a retrodiction hit rate. We ran a leakage probe first and the model identified
**9 of 15** redacted pre-fame artifacts — that is memory, not skill, so the number would have been
dishonest. `docs/RESEARCH.md` sets out the study we *would* run for Area of Research 3, including
the selection correction, rather than pretending we ran it.

Days-of-edge is input-starved: only one person in the ledger has become consensus-visible, so
three channels sit at n=1 and say so loudly rather than quoting a median.

## Run it

```bash
uv sync && uv run python -m worker.run_all   # ledger + collectors + demo.json
cd web && npm install && npm run dev
```

`uv run python -m worker.prove_asof` demonstrates the core architectural claim in ten seconds.
