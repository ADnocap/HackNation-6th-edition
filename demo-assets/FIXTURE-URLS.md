# Fixture site URLs (C2)

Status: **DEPLOYED — 25/25 live HTTP checks passed** (paths, verbatim excerpts, and required
404s, verified against the production URLs below on 2026-07-18).

Source lives in `demo-assets/fixtures/{ledgerline,northgate,kestrelops}/`. Each site is its own
Vercel project (account `wass-ad`), so each has its own origin like the fiction requires.
Redeploy: `npx vercel deploy --prod --yes` from the site's directory.

**→ Integration (Alexandre/Claude):** swap the placeholder domains in
`worker/demo_overrides.json` (`ledgerline.dev`, `northgatesettle.com`, `kestrelops.archive`)
for the live origins below — that edit belongs to your lane, see `docs/HANDOFF.md`.

## Ledgerline — live origin: `https://ledgerline-sage.vercel.app`

| Path | Purpose | Verified content | Status |
|---|---|---|---|
| `/` | landing | — | 200 ✓ |
| `/pricing/` | pricing tiers | `Starter €89/mo · Team €229/mo · Scale €640/mo` | 200 ✓ |
| `/changelog/` | release cadence (contradiction #1) | `2026-04-30 · v0.4.0 — first public release`, `2026-06-02 · v0.4.1 — retry backoff`, nothing else | 200 ✓ |
| `/team/` | 3 named people (contradiction #2) | Daniel Rehmke (`github.com/drehmke`), Mara Vogel, Jonas Pfeiffer | 200 ✓ |
| `/customers/` | review volume (contradiction #1) | `Trusted by teams at 3 named companies · 11 reviews` | 200 ✓ |
| `/legal/` | trademark + goods-and-services | `serial 98/441,207 · filed 2026-04-08 · attorney of record present` + goods text verbatim | 200 ✓ |
| `/imprint/` | incorporation | `HRB 284119 · registered 2026-03-22` · contact `daniel@drehmke.dev` (merge key) | 200 ✓ |
| `/checkout/` | transacting probe | `Stripe checkout session` + checkout.stripe.com link | 200 ✓ |
| `/careers` | **404 required** | expected-and-absent evidence (`evd_mrr_2`, `evd_hc_2`) | 404 ✓ |

## Northgate Settle — live origin: `https://northgate-three.vercel.app`

| Path | Purpose | Verified content | Status |
|---|---|---|---|
| `/` | landing + pricing | `$29` / `$79` per month, solo-founder story ("two years reconciling") | 200 ✓ |
| `/checkout/` | transacting probe | `checkout.stripe.com` marker | 200 ✓ |
| `/receipts/2026-07-16/` | elicitation-response verification | `Payout 2026-07-16 · $412.00` | 200 ✓ |
| `/changelog` | **404 required** | expected-absent (`evd_mo_chlog`) | 404 ✓ |
| `/team` | **404 required** | solo operator — absence not penalised | 404 ✓ |

## Kestrel Ops (archived prior venture) — live origin: `https://kestrelops.vercel.app`

| Path | Purpose | Verified content | Status |
|---|---|---|---|
| `/` | archived landing | `ARCHIVED SNAPSHOT` banner | 200 ✓ |
| `/imprint/` | 2024 incorporation (merge key) | `registered 2024-03-11` · founder **Daniel Riehmke** (different spelling!) · `hello@drehmke.dev` | 200 ✓ |
| `/team/` | archived team page (merge key) | `github.com/drehmke` — same handle as Ledgerline | 200 ✓ |

## The merge-key design (do not break)

The two-venture entity merge keys on **shared code-host handle (`drehmke`) and shared
registrant email domain (`drehmke.dev`)** — never on the founder's name, whose spelling
deliberately differs (Rehmke vs. Riehmke). Both team pages carry the handle; both imprints
carry the email domain.
