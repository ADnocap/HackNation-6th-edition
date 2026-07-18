# Fixture site URLs (C2)

Status: **built and verified locally (26/26 path/excerpt checks) — deployment pending.**
Source lives in `demo-assets/fixtures/{ledgerline,northgate,kestrelops}/`. Each site deploys as
its own static project (Vercel), so each gets its own origin like the fiction requires.

Once deployed, fill the "Live URL" column and tell the integration side — they own the
`demo_overrides.json` edit that swaps the placeholder domains for these URLs. Do not edit
`worker/` from this lane.

## Ledgerline (placeholder domain in overrides: `ledgerline.dev`)

| Path | Purpose | Must contain / status | Live URL |
|---|---|---|---|
| `/` | landing | — | _pending_ |
| `/pricing/` | pricing tiers | `Starter €89/mo · Team €229/mo · Scale €640/mo` | _pending_ |
| `/changelog/` | release cadence (contradiction #1) | `2026-04-30 · v0.4.0 — first public release`, `2026-06-02 · v0.4.1 — retry backoff`, nothing else | _pending_ |
| `/team/` | 3 named people (contradiction #2) | Daniel Rehmke (`github.com/drehmke`), Mara Vogel, Jonas Pfeiffer | _pending_ |
| `/customers/` | review volume (contradiction #1) | `Trusted by teams at 3 named companies · 11 reviews` | _pending_ |
| `/legal/` | trademark + goods-and-services | `serial 98/441,207 · filed 2026-04-08 · attorney of record present` | _pending_ |
| `/imprint/` | incorporation | `HRB 284119 · registered 2026-03-22` · contact `daniel@drehmke.dev` (merge key) | _pending_ |
| `/checkout/` | transacting probe | `Stripe checkout session` + checkout.stripe.com link | _pending_ |
| `/careers` | **must 404** | expected-and-absent evidence (`evd_mrr_2`, `evd_hc_2`) | _pending_ |

## Northgate Settle (placeholder domain: `northgatesettle.com`)

| Path | Purpose | Must contain / status | Live URL |
|---|---|---|---|
| `/` | landing + pricing | `$29` / `$79` per month, solo-founder story ("two years reconciling") | _pending_ |
| `/checkout/` | transacting probe | `checkout.stripe.com` marker | _pending_ |
| `/receipts/2026-07-16/` | elicitation-response verification | `Payout 2026-07-16 · $412.00` | _pending_ |
| `/changelog` | **must 404** | expected-absent (`evd_mo_chlog`) | _pending_ |
| `/team` | **must 404** | solo operator — absence not penalised | _pending_ |

## Kestrel Ops — archived prior venture (placeholder: `kestrelops.archive`)

| Path | Purpose | Must contain / status | Live URL |
|---|---|---|---|
| `/` | archived landing | `ARCHIVED SNAPSHOT` banner | _pending_ |
| `/imprint/` | 2024 incorporation (merge key) | `registered 2024-03-11` · founder **Daniel Riehmke** (different spelling!) · `hello@drehmke.dev` | _pending_ |
| `/team/` | archived team page (merge key) | `github.com/drehmke` — same handle as Ledgerline | _pending_ |

## The merge-key design (do not break)

The two-venture entity merge keys on **shared code-host handle (`drehmke`) and shared
registrant email domain (`drehmke.dev`)** — never on the founder's name, whose spelling
deliberately differs (Rehmke vs. Riehmke). Both team pages carry the handle; both imprints
carry the email domain.
