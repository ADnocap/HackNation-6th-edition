# Area of Research 3 — Can a public footprint predict founder success, and how would you test it?

The brief poses this as genuinely open. We did not solve it in 21 hours, and claiming otherwise
would contradict the product. What follows is the test design we would run, stated precisely
enough to be attacked — including the reasons we believe the honest answer is *weaker than the
industry assumes*.

This matters for our system specifically: a founder with no funding and no GitHub history often
*does* still have a public footprint, so the predictive value of that footprint is the direct
determinant of how much a cold-start prior can ever be worth.

---

## 1. The question, stated testably

> For a founder observed at time *t* with no prior funding and no prior exit, does the public
> footprint observable at *t* carry information about an outcome realized after *t*, **beyond**
> what access variables already explain?

The "beyond access" clause is the whole question. A raw correlation between footprint and success
is nearly guaranteed and nearly meaningless, because both are downstream of access. The estimand
is the **incremental** predictive value of footprint after conditioning on elite university, prior
VC-backed employer, accelerator brand, follower count, and metro. Anything that does not
residualize against access is measuring pedigree with extra steps.

## 2. The outcome variable — the binding constraint

There is no clean label for "successful founder," and the usual proxies are traps:

- **Raised a subsequent round** — the most available label and the worst one. It is *investor
  behaviour*, not company merit, so a model trained on it learns to predict what VCs already like.
  For a system whose entire purpose is to find who the network misses, this label bakes in the
  bias we exist to remove.
- **Survival at 24 months** — cheap but weak; dormant companies rarely announce death.
- **Independently observable traction** — package crossing a download threshold, adoption as a
  dependency by ≥5 distinct orgs, sustained paid product, acquisition. Slower and noisier, but it
  is the only family not defined by an investor's decision.

We would use the third, pre-registered before looking, with a fixed 24-month horizon and
right-censoring handled explicitly rather than dropped.

## 3. Cohort construction

Point-in-time by construction, using the same `asof` chokepoint the product runs on: every feature
is computed from `WHERE observed_at <= t`, so the model can only see what was visible then.

Sampling frame is founders **first observed at t through a channel that does not require a track
record** (self-filed trademark, low-visibility forum activity, preprint) — the population our
sourcing layer actually serves. Sampling from an already-funded universe would answer a different
question.

## 4. The selection problem, which is the real difficulty

Outcomes are disproportionately observable for founders who got funded, and funding is caused by
the access variables we are trying to control for. Naively regressing outcome on footprint over
observed cases estimates the effect *conditional on having been selected*, which is biased toward
zero or worse — the textbook Heckman setup.

Two credible treatments:

- **Inverse-probability weighting.** Model `P(outcome observable | access, footprint, channel)`,
  weight by its inverse. Requires overlap: founders with near-zero probability of ever being
  observed contribute nothing, and we must report how much of the sample that excludes.
- **Heckman two-step**, needing an exclusion restriction — a variable affecting observability but
  not the outcome. Geographic proximity to an active investor hub is the least-bad candidate, and
  it is not clean.

**We would report the naive estimate and the corrected estimate side by side.** The gap between
them is itself the most interesting finding, and it is the number the industry never publishes.

## 5. Leakage control — and why we ran this part

Any LLM-derived footprint feature risks the model *recognising* a now-famous founder from training
data rather than inferring from evidence. That would inflate every number here.

This is the one component we did build. We take real pre-fame artifacts, redact and paraphrase
them, and ask the model to name the company. **In our run it identified 9 of 15.** That leak rate
is high enough that we refuse to report a retrodiction hit rate at all — it would be memory, not
skill. Any serious version of this study must publish its leak rate before its accuracy.

## 6. Power

With a base rate near 10% and a target of detecting an AUC improvement of 0.05 over an
access-only baseline at 80% power, the requirement is on the order of low thousands of founders
with resolved 24-month outcomes. That is a data-collection project of months, not a hackathon
task — which is precisely why we are documenting a design rather than reporting a result.

## 7. What we expect, and what would change our minds

Our prior is that footprint carries **real but modest** incremental signal — enough to move a
posterior, not enough to justify a decision on its own — and that most of the apparent predictive
power in commercial tools is access leaking through unresidualized features.

We would abandon that prior if the access-residualized model retained most of its lift under IPW
correction with a published leak rate near zero.

## 8. What we did not do

We did not run this study. We have no outcome labels, no matched cohort, and no corrected
estimate. What we have is the point-in-time infrastructure that makes it runnable — every read
already takes an `asof`, so the counterfactual "what was knowable at time *t*" is a query rather
than a rebuild — plus the leakage probe that says our headline number would have been dishonest.

Publishing a null design honestly is worth more than a coverage statistic we could not have earned
in a day.
