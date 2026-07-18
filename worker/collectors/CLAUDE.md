# worker/collectors/ — Ali's area (sourcing)

Your brief is `docs/TASKS.md`, section **ALI**. The plan is `docs/IDEA.md` section D.

## Scope

You own `worker/collectors/` and `worker/verify/`. Nothing else. Other people are actively
editing `worker/scoring/`, `web/` and `demo-assets/` right now — do not touch them.

**Read but never edit:** `worker/ledger.py`, `worker/db.py`, `db/schema.sql`.
Every collector writes to the ledger through `append_observation()` and no other path.

Need a new column? Write the request in `docs/HANDOFF.md`. Do not edit the schema.

## The design rule

**A channel qualifies only if it can fire for a person with no GitHub, no funding and no
network.** If a signal requires an existing track record, it rebuilds the network gate this
challenge exists to replace. GitHub-trending-by-stars is banned as a discovery channel.

## Rules specific to this directory

- **Cache every external response to disk by content hash, from the first commit.** Not later.
  A second full run of the pipeline must make zero network calls. Our API budget does not
  survive an uncached rebuild loop.
- **Never score popularity.** Not karma, not stars, not follower counts. Score the *text* and
  the *artifact*. Popularity is what we are explicitly refusing to rank on.
- **`provenance_class` is honest on every row:** `live` (fetched now), `fixture` (pre-downloaded
  dated bulk data), `synthetic` (authored). A judge can filter to `live` on camera, so a wrong
  badge is worse than no data.
- **Every aggregate number carries its `n`.** A channel at n=6 shows a wide error bar and says so.
- **Verification is two mechanisms, never confused:** `verify/fetch.py` is a direct `httpx.get()`
  returning body + final URL + fetch timestamp, and it backs the demo's receipt pane.
  `verify/tavily.py` is for entities *already indexed* on the public web only. Tavily is a search
  index, not a fetcher — it has never crawled our fixture sites and never will in time.
- Prefer boring libraries: `httpx`, `selectolax`, stdlib. No Playwright, no LangChain, no
  scrapers that need JS rendering — a source needing a headless browser gets cut, not debugged.

## Working

Branch `feat/ali-sourcing`. Push every 45 minutes minimum, even mid-task. Never commit to `main`.

```bash
uv sync                                  # setup
uv run python -m worker.collectors.<name>   # run a collector
uv run python -m worker.prove_asof       # sanity-check the ledger still works
```
