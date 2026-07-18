# 6th Global AI Hackathon — Challenges

Six challenges. Pick **one**. Full briefs are PDFs in `docs/assets/challenges/`. Each challenge is judged and prized separately (1st/2nd/3rd per challenge → finalist pitches July 25).

Portal: https://projects.hack-nation.ai/

| # | Name | Sponsor | One-liner | Core deliverable |
|---|------|---------|-----------|------------------|
| 01 | The Negotiator | ElevenLabs | Voice agents that call, compare, and haggle for the best price in a vertical you pick | Voice-agent MVP w/ live calls |
| 02 | The VC Brain | Maschmeyer Group | AI that sources founders, scores them, and deploys $100K checks in 24h | Data + reasoning + investor UI |
| 03 | RealDoor | RealPage | Renter-side copilot for affordable-housing application readiness (no eligibility decisions) | Web app, 3-stage flow |
| 04 | Data Legend | Databricks | Trust layer over 10k messy Indian healthcare facility records | Live Databricks App |
| 05 | Women's Hormonal Health | Hack-Nation / OpenAI | Open reusable building block (dataset/benchmark/model/app) for women's hormonal health | Open-sourced scientific asset |
| 06 | Genome Firewall | OpenAI | Predict which antibiotics fail from a bacterial genome, with calibrated confidence | Streamlit/Gradio ML demo |

---

## 01 — The Negotiator (ElevenLabs)
**Voice agents that call, compare, and haggle — pick your market, never overpay again.**

Build an end-to-end voice-agent system that, for a vertical you choose (moving, medical bills, car buying, contractor bids, freight, equipment rental, wedding vendors…), gathers real prices by phone, reports them comparably, and negotiates. Three mandatory modules:
1. **The Estimator (intake):** voice interview (on ElevenLabs Agents) **plus** at least one document type (photos/quotes/bills), both producing the **same structured job spec (JSON)**, user-confirmed, reused verbatim on every call.
2. **The Caller (quote gathering):** live calls against **≥3 distinct negotiation styles** — real businesses (Twilio/SIP), you role-playing counterparts, or built counter-agents. Every quote captured structured with fees itemised.
3. **The Closer (negotiate + report):** ≥1 negotiation where **price/terms measurably change during the call** because of leverage; apply the 30%-below-market red-flag rule; final ranked report citing transcripts/recordings.

Vertical params (taxonomy, benchmarks, red-flag rules, levers) = **config, not code**. Must handle AI disclosure ("are you a robot?"), friction, and an honesty line (never invent bids/inventory). **Won in call design, not model architecture.** Weak = two agents reading a script at each other.

**Success:** closed loop intake→calls→negotiation→ranked rec; one spec from voice+doc; ≥3 live styles; ≥1 real price move; honesty/disclosure holds; every call ends in a structured outcome.
**Stack hints:** ElevenLabs Agents + Batch Calling + Twilio/SIP; Google Places/Yelp for call lists; vision/OCR for docs; vertical benchmarks (FMCSA, FAIR Health, RepairPal, KBB).

## 02 — The VC Brain (Maschmeyer Group)
**Deploy $100K checks in 24 hours.** Data- & AI-first VC operating system: Sourcing → Screening → Diligence → Decision (downstream out of scope).

Three pillars: **Memory** (ingest decks/GitHub/social, dedup, timestamp, houses the persistent **Founder Score**), **Intelligence** (reasoning layer, transparent about confidence), **Experience** (investor UX). MVP must show: configurable **Thesis Engine**; smart data collection; **multi-attribute NL queries** ("technical founder, Berlin, AI infra, no prior VC backing…"); inbound apply+screen; **outbound** founder discovery (scan GitHub/hackathons/papers) + activation; **3-axis screening** (Founder / Market / Idea-vs-Market — **not averaged**, each with trend); per-claim **Trust Score** with evidence; evidence-backed investment memos.

**The priority is Sourcing** (least commercial competition — go deepest here) and the **cold-start case** (first-time founder, no GitHub/funding/network) — generic ingestion that ignores it scores poorly.
**Evaluation:** Data Architecture & Intelligence **30%**, Intelligent Analysis & Trust **25%**, Investment Utility & Execution **30%**, UX **15%**. No dataset provided — bring/synthesize (Crunchbase/LinkedIn/GitHub/ProductHunt/HN/arXiv or synthetic profiles with seeded contradictions). Best single stretch: **Agentic Traceability** (cite exact data point per conclusion).

## 03 — RealDoor (RealPage)
**Application-readiness copilot for affordable housing.** Design principle: *AI extracts/explains/retrieves/calculates/prepares; the renter confirms; a qualified human decides.* One metro, one program, synthetic docs, human decision.

Three-stage flow: **Profile** (extract allowlisted fields from synthetic pay stubs/benefit letters, with source boxes + confidence, user confirms) → **Understand** (cited rules + deterministic math from a versioned corpus, show value/threshold/formula/source/effective-date, **abstain** when uncertain, never label eligible) → **Prepare** (flag missing/expired vs gold checklist; renter can preview/edit/download/delete; never auto-send).

**Non-negotiable, demoed live:** no decisioning/scoring/ranking; no hidden proxies for protected traits; consent + correction; privacy (synthetic docs, ephemeral, deletion, never train on uploads); prompt-injection resistance (treat doc text as untrusted); **WCAG 2.2 AA** accessibility. Organizers provide a data pack (LIHTC subset, frozen 2026 MTSP limits, synthetic docs, checklists, starter repo).
**Rubric:** Profile accuracy 25% · Rules & math 25% · Safety & privacy 20% · Accessibility 15% · End-to-end usefulness 15%. **Minimum bar:** any submission that approves/denies/scores/ranks/leaks data cannot win.

## 04 — Data Legend (Databricks)
**Trust layer for Indian healthcare.** Ship a **live Databricks App (Free Edition)** over 10,000 messy facility records (51 cols, noisy free-text claims). Pick **ONE** mission track:
- **Facility Trust Desk** — can this facility do what it claims? Ranked facilities + trust signals + citations + override.
- **Medical Desert Planner** — where are the highest-risk gaps, how confident? Trust-weighted regional coverage → drill to records → save scenario.
- **Referral Copilot** — where should a patient go? Evidence-attached shortlist with distance/gaps.
- **Data Readiness Desk** — what must be fixed before trusting the data? Flagged review queue, persisted decisions.

Every output traces to row-level citations; reason about **confidence** (no ground truth); distinguish **data desert vs medical desert** (only 25% have capacity, 36% doctor counts). Must **persist user actions** across sessions.
**Stack (required):** Databricks Apps + Agent Bricks + Genie + MLflow 3 tracing + Mosaic AI Vector Search + Lakebase. Submit Git repo + live app; 1-min demo.
**Evaluation:** Evidence & Trust 35% · Product Judgment 30% · Technical Execution 25% · Ambition 10%. **Needs a Databricks (Free Edition) account.**

## 05 — Women's Hormonal Health (Hack-Nation / OpenAI)
**Build one reusable building block** — dataset, benchmark, model, or app — for women's hormonal health, and **open-source it**. Not a one-weekend foundation model; a reusable scientific asset. Three layers (pick one): **Data & Benchmark Infra** (standardized multimodal dataset + splits + eval), **AI Model Infra** (focused, reproducible, explainable — e.g. hormone-state/menopause-onset prediction), **Application Infra** (symptom tracking, hormone journals, digital twins, data-donation pathway).
**Deliverables:** working prototype + code, technical + dataset docs, benchmark methodology, demo video.
**Success:** Women's Health Impact (reach × quality of life) · Technical Excellence (rigor/reproducibility) · Foundation Value (reusable infra). Datasets: **mcPHASES (PhysioNet)**, **NHANES (CDC)**. $50 OpenAI credits/team (gpt-image-2, multimodal). Weak = polished UI with no scientific validation or reusable contribution.

## 06 — Genome Firewall (OpenAI)
**Predict which antibiotics fail from a bacterial genome, before lab results.** Research prototype for ONE bacterial species. Input: quality-checked FASTA → per antibiotic: **likely to fail / likely to work / no-call**, with calibrated confidence + supporting genes/mutations. Strictly **defensive** — never design/modify organisms. In scope starts *after* isolation/sequencing/reconstruction.

Three modules: **Genome Reader** (FASTA → features, default annotation = **AMRFinderPlus**) → **Predictor** (per-drug prediction; deterministic gate on drug's molecular target; **de-dup by sequence homology** so near-identical genomes don't leak train↔test) → **Decision Report** (Streamlit/Gradio app; evidence category: known gene / statistical-only / none; mandatory "confirm with standard lab testing").
**Judged on honest metrics:** balanced accuracy, resistant/susceptible recall separately, F1, AUROC, PR-AUC per drug, **Brier score + reliability plot**, no-call rate, and **grouped-split generalization** on a hidden test set. Data: **BV-BRC** (15k+ genomes w/ lab results), AMRFinderPlus, ResFinder. **Baseline recommended:** regularized logistic regression per antibiotic on CPU — fast, calibratable, explainable. Deep-learning (HyenaDNA/DNABERT-2) is optional stretch on GPU. $50 OpenAI credits/team. Weak = random split with genome leakage → inflated score.

---

## Quick fit notes for our team

- **Fastest to a working demo:** 01 Negotiator (voice + you role-play the counterparties — no real telephony needed) and 03 RealDoor (organizer data pack removes wrangling; scope is tightly defined). Both are UI + agent orchestration, no training.
- **Plays to HPC/ML strength:** 06 Genome Firewall — but the winning move is the *calibrated* logistic-regression baseline with an honest grouped split, which runs on CPU. The A100s only matter if we chase the deep-learning stretch. 05 Hormonal Health also ML-leaning but rewards open-sourcing a reusable asset over a flashy demo.
- **Most "venture/incubation" upside:** 02 VC Brain — meaty, on-brand for the program, but it's the widest scope (sourcing + reasoning + UX) and easiest to spread too thin. Sourcing depth + cold-start is where it's won.
- **Highest infra lock-in:** 04 Data Legend requires a Databricks Free Edition account and their specific stack — great if we want to learn Databricks, friction if not.
