# Handoff requests

Cross-area requests go here so nobody edits a file they don't own.

**How to use it:** add a bullet under the owner you need something from, on your own branch.
Say what you need and why. Then tell them in chat — this file is a record, not a notification.

Owners: **Ali** = `worker/collectors/`, `worker/verify/` · **Alexandre** = `worker/scoring/`,
contract files, `web/`, `db/` · **Wacil** = `demo-assets/`

Contract files (`db/schema.sql`, `worker/ledger.py`, `worker/db.py`, `web/lib/types.ts`,
`web/public/demo.json`) are changed by Alexandre only. Requesting a change takes two minutes;
editing it yourself costs an hour of merge conflict.

---

## → Alexandre (schema / contract / frontend)

- **Fixture sites are live — swap the placeholder domains in `worker/demo_overrides.json`.**
  (Wacil, 18 July.) The three fixture sites are deployed and verified (25/25 live HTTP checks,
  including the required 404s on `/careers` and Northgate's `/changelog`):
  `ledgerline.dev` → `https://ledgerline-sage.vercel.app` ·
  `northgatesettle.com` → `https://northgate-three.vercel.app` ·
  `kestrelops.archive` → `https://kestrelops.vercel.app`.
  Full path/content table in `demo-assets/FIXTURE-URLS.md`. The overrides' evidence
  `source_url`/`final_url` fields still point at the placeholder domains — that edit is yours,
  not ours.

## → Ali (collectors / verification)

- **Reassignment, 18 July ~17:30 ET.** `worker/collectors/` was still an empty stub and Sourcing
  carries 30% of the grade, so A1–A5 got built without you: `base.py` (shared cache + ledger
  write path + the cold-start guard on `register_channel`), plus the trademark, HN, arXiv, domain
  and channel-scoring collectors. Nothing of yours was overwritten — the branch syncs were plain
  fast-forwards, which would have been rejected had you pushed anything.
- **`worker/verify/` is untouched and is yours** — see `docs/TASKS.md` A6. The one thing to get
  right: `verify/fetch.py` is a direct `httpx.get()` returning body + final URL + fetch timestamp
  and backs the demo receipt; `verify/tavily.py` is *only* for entities already indexed on the
  public web. Tavily is a search index, not a fetcher — it will never have crawled our fixture
  sites, so routing receipts through it returns zero results that look identical to "we couldn't
  check."

## → Wacil (demo assets)

- _(none yet)_

---

## Resolved

- _(none yet)_
