# worker/scoring/ — Alexandre's area (scoring & modelling)

Brief: `docs/TASKS.md`, section **ALEXANDRE**. Rationale: `docs/IDEA.md` sections B and C.

## Scope

You own `worker/scoring/`. Ali is in `worker/collectors/` and `worker/verify/` — don't touch those.

**Read but never edit:** `worker/ledger.py`, `worker/db.py`, `db/schema.sql`.
All reads go through `read_observations(asof, ...)`. Never query the ledger directly — the
`asof` chokepoint is what makes trend computation and point-in-time replay possible at all.

## Rules specific to this directory

- **No composite score. No averaging of the three axes.** There is no composite column in the
  schema; do not add one. Market is categorical (bullish/neutral/bear) so it structurally cannot
  be averaged. Collapsing the axes hides exactly the disagreement an investor needs to see.
- **The scorer is closed-form numpy, never an LLM.** This is what makes leave-one-evidence-out
  attribution exact and instantaneous rather than the model narrating a story about itself.
- **Absence widens the interval; it never lowers the score** — when the findability prior
  predicted that absence for this resource class. This asymmetry is the anti-network-gate and
  it is the single most important line of code in the project.
- **The reference class contains no pedigree field.** `{artifact type, sector, solo/team,
  resource tier, region}`. No school, no employer, no accelerator, no investor.
- **Findability priors are computed from Ali's crawl**, with cell counts shown and thin cells
  shrunk to the margin. Hardcoded priors are the most attackable number in the demo.
- **Every number you emit carries its `n`.** If you can't state the sample size, don't ship the
  number.
- **Trend is computed, never asserted:** re-score at `asof−90/−60/−30/0`. Label improving or
  declining only when the OLS slope band excludes zero; otherwise render
  "insufficient dated observations (n=2)".
- **Founder Score versions are append-only.** Never update in place — the whole point is that
  the history replays as a step function across two different ventures.

## Deliberately on the cut list — do not build these

Conformal prediction, Benjamini-Hochberg FDR, SPRT operating characteristics, Thompson sampling,
Mondrian binning, the pedigree R². Not because the maths is wrong, but because none of them has
a target variable, a null distribution, or a sample size that exists inside 18 hours. A
tautological coverage number in front of a finance-native sponsor is worse than shipping none.
The reasoning is written up in `docs/IDEA.md` section B — it's a credibility asset, not a gap.

## Working

Branch `feat/alex-scoring`. Push every 45 minutes minimum.

```bash
uv sync
uv run python -m worker.prove_asof    # proves the asof chokepoint still holds
```
