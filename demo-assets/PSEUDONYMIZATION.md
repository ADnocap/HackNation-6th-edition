# Pseudonymization audit (C3)

Audited: `web/public/demo.json` (read-only pass, 2026-07-18, by Wacil's lane).
Method: mechanical scan of every string field — display names, org names, email addresses,
social/code-host handles, external URLs with their JSON paths, LinkedIn mentions, and
capitalized first-last name bigrams in all free text (verdict sentences, receipt excerpts,
bear-case bullets, challenge/outreach bodies).

**All findings below are handed to the integration lane (Claude/Alexandre) — nothing here was
edited by us. `web/` is not ours to touch.**

## Clean — verified, no action needed

- **All 20 person display names are initials-only** (`D. R.`, `M. O.`, `K. S.` … `Z. R.`),
  consistent between `people.*` and `signal_feed.rows[*]`.
- **All org names are fictional** (Ledgerline, Northgate Settle, Corvid Data, Sable Ledger,
  Kestrel Freight, Arbor Clearing, … plus `Applicant 041/052/058` and "no company yet").
- **Zero email addresses** anywhere in the file.
- **No personal social or code-host handles.** The only github URLs are the fictional org repo
  `github.com/ledgerline/sdk`.
- **LinkedIn appears only as a declined source** (not-collected ledger + two verdict sentences
  saying "we declined LinkedIn") — which is the required posture, not a leak.
- **No real-person name bigrams in free text.** Every hit is a fictional org, the sponsor name
  in `meta.challenge` ("Maschmeyer Group" — intentional), or a declined source name
  ("Product Hunt").

## Findings — for integration to resolve

### F1 · Real-site URLs cited as evidence for fictional people (highest priority)

These evidence rows point at **real, live domains** whose content we do not control. If a judge
clicks one (the Receipt modal renders `source_url`), it either 404s or shows a real person's
content attached to our fictional founder — both break the demo's own honesty frame:

| URL | Where | Risk |
|---|---|---|
| `news.ycombinator.com/item?id=48959447` and `id=48812203` | `opp_northgate.claims[2].evidence[0/1]` (M. O.'s domain-exposure claim) | Real HN item IDs — if they exist, they're a **real person's comments** misattributed to a fictional founder; if not, 404 |
| `reddit.com/r/smallbusiness/` | `opp_northgate.claims[8]` evidence + receipt | Real subreddit; live fetch returns real content that will not contain our excerpt |
| `opencorporates.com/companies/de/HRB-284119` | `opp_ledgerline.claims[7].evidence[0]` | Real registry site — **HRB 284119 may collide with a real German company**; citing a real registry ID for a fictional entity is the one place this could brush a real business |
| `github.com/ledgerline/sdk` (+`/blob/main/billing.ts`) | `opp_ledgerline.claims[14/15]` | Real domain; the `ledgerline` org may exist or be registered by someone else |

**Recommended fix:** follow the pattern already used elsewhere in the same file —
`example-press.test` and `fintechwire.example` (RFC-reserved TLDs, perfectly safe). Swap the
four above to fictional-but-shaped equivalents, or point them at our live fixture origins.
Same note for the fixture sites' `github.com/drehmke` links (our merge-key handle): that
account could belong to a real person — consider whether the demo ever renders it as a link.

### F2 · `web/public/demo.json` is stale relative to `worker/demo_overrides.json`

Not strictly pseudonymization, but surfaced by the same scan and it affects every fixture we
built:

- **Domain drift:** demo.json uses `ledgerline.io` (36 URLs); overrides use `ledgerline.dev`.
- **Founding-date drift:** demo.json `opp_ledgerline.claims[5]` still says "Founded June"
  (the old June-2024 story); overrides + the deck + the fixture sites all say January 2025.
- **Trademark serial drift:** demo.json cites `tsdr.uspto.gov/statusview/sn99150042` /
  `sn99150077`; overrides + deck + fixture sites use `98/441,207` (Ledgerline) and
  `98/447,913` (Northgate).

**Recommended fix:** regenerate `demo.json` from the overrides (`python -m worker.export_demo`),
then apply the live-fixture URL swap from `demo-assets/FIXTURE-URLS.md` in the same pass:
`ledgerline.dev` **and** `ledgerline.io` → `https://ledgerline-sage.vercel.app` ·
`northgatesettle.com` → `https://northgate-three.vercel.app` ·
`kestrelops.archive` → `https://kestrelops.vercel.app`.

### F3 · TSDR links point at the real USPTO

`tsdr.uspto.gov/statusview/sn…` resolves to the real USPTO status viewer — a fetch or click
will show a **real filing (someone else's) or an error**, under our fictional serial. Same
class as F1; same fix (fictional-shaped placeholder, or state `provenance_class` clearly on
the rendered link).

## Statement for the demo

Real people surfaced by live collectors are pseudonymized to initials + channel + signals;
the refuter is disabled on real-person entities; outreach is drafted and rendered but never
sent. The two hero companies and every named individual attached to them (Daniel Rehmke /
Daniel Riehmke, Mara Vogel, Jonas Pfeiffer, the three customer companies) are **fictional by
construction** — invented names, invented registries, fixture domains we control.
