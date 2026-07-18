# `db/` — the append-only ledger

`schema.sql` is the whole store. 20 tables, no ORM, no migration tool, no `psql`.

Two invariants govern everything in here. They are restated at the top of `schema.sql`
because they are the product, not the plumbing:

1. **Append-only.** Nothing is ever `UPDATE`d or `DELETE`d. A claim changing state is a new
   row. A founder score moving is a new row. A screen-out is a new `stage_transition` row,
   which is why a rejected founder can re-enter later. Corrections append a superseding row
   and set `supersedes_id`. "The Founder Score never resets" is therefore a property of the
   schema rather than a promise in a README.
2. **The `asof` chokepoint.** Every read filters `WHERE observed_at <= :asof`, and that
   predicate lives in exactly one function, `worker/store.py :: read_observations(asof, ...)`.
   `asof = now()` is a live VC brain; `asof =` a past date is a point-in-time backtest running
   the identical code. Trend is never asserted — it is re-scoring at `asof-90/-60/-30/0`.

If you add a table: it needs `observed_at` (when the fact was true in the world) **and**
`ingested_at` (when we learned it). Both. Always. Filtering on `ingested_at` silently breaks
the backtest.

---

## Create the local database

```bash
python worker/init_db.py
```

That reads `db/schema.sql` and applies it to `db/counterproof.db` (gitignored). The script is
idempotent — every statement is `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS`,
so re-running it is a no-op and never drops data. To start clean, delete the file and re-run.

Verify:

```bash
sqlite3 db/counterproof.db ".tables"      # 20 tables
```

No `sqlite3` binary on the box? Everything here uses stdlib only:

```bash
python -c "import sqlite3;c=sqlite3.connect('db/counterproof.db');print(sorted(r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'\")))"
```

**Turn foreign keys on for every connection.** SQLite ignores `FOREIGN KEY` clauses by
default; Postgres does not. Run `PRAGMA foreign_keys = ON` immediately after `connect()` or
local behaviour will drift from what Supabase will do.

---

## The 20 tables

| # | Table | What it is for |
|---|---|---|
| 1 | `person` | The spine. Persists across companies. Blocking keys, contact status, pseudonymization flags. |
| 2 | `org` | Companies. Also carries the seeded portfolio positions the conflict check runs against. |
| 3 | `channel` | Sourcing channels including declined ones, with Days of Edge and its `n`. |
| 4 | `observation` | **The ledger.** Everything else is a pure function of these rows read at an `asof`. |
| 5 | `opportunity` | One row per company under consideration. Inbound and outbound land in the same table. |
| 6 | `stage_transition` | The funnel. All funnel arithmetic is counted from here, never authored. |
| 7 | `claim` | Trust, per claim. Four states. There is no company-level trust column. |
| 8 | `evidence` | Per-evidence log-odds deltas. Leave-one-out is an exact recompute over these. |
| 9 | `axis_score` | Three axes as three rows, never reduced to one number. |
| 10 | `founder_score_version` | Append-only versions, per person. Replays as a step function across ventures. |
| 11 | `findability_prior` | `P(artifact observable \| reference class)`, computed from our own crawl, with cell counts. |
| 12 | `sector_prior` | The axis → Memory writeback. A verdict shifts the prior for the next company in that sector. |
| 13 | `source_reliability` | The hand-set reliability table, published in advance. |
| 14 | `thesis` | Six fields. `risk_appetite` maps to `max_interval_width`, so the thesis is load-bearing. |
| 15 | `trigger_event` | The system acting unprompted when a signal crosses the conviction threshold. |
| 16 | `elicitation` | VOI-selected challenge, drafted. `sent_at` is always NULL. |
| 17 | `decision` | The typed decision card. Binding and dissenting axes are typed fields, not prose. |
| 18 | `memo` | Five sections + gaps block + bear case. Uncited bullets render blocked. |
| 19 | `excluded_source` | "Not collected, and why." |
| 20 | `channel_outcome` | **Deliberately empty.** Zero funded outcomes. The schema that would rank channels, and the reason we do not yet. |

Milestones are not a table — they are observations with `is_milestone = 1` and a
`milestone_type`, so they render as ticks on the founder score history chart and stay inside
the one ledger. The Apply form is not a table either; its two fields live on `opportunity`.

### Constraints that are load-bearing, not decorative

These are enforced in SQL, so a bug cannot put a forbidden shape on screen:

- **No averaged score column exists anywhere.** If it is not computed it cannot be rendered.
- `axis_score` has a table-level `CHECK` splitting the market axis from the numeric axes: the
  market axis must leave `point`, `interval_low` and `interval_high` NULL and carry
  `categorical_value` instead; the numeric axes must leave `categorical_value` NULL. Market is
  categorical, so it *structurally* cannot be averaged with the other two.
- `founder_score_version` has `CHECK (interval_low <= point AND point <= interval_high)`.
- A unique index on `observation (source_url, claim_type, value_hash)` is what makes the
  de-duplication counter a fact rather than an assertion. Collisions are rejected at insert.
- Every enum in the system is a `CHECK ... IN (...)` — claim states, source classes,
  provenance classes, stages, verdicts, trend labels, screen rules.

---

## Deploying the same schema to Supabase (the on-camera ledger prop)

`schema.sql` is deliberately written in a SQLite/Postgres common subset. The same text applies
to both engines with no edits.

1. Supabase dashboard → **SQL Editor** → **New query**.
2. Paste the entire contents of `db/schema.sql`. Do not edit it first — apply it verbatim, so
   what runs on camera is byte-identical to what runs locally.
3. **Run.** Expect `Success. No rows returned`.
4. **Table Editor** should now list all 20 tables. `observation` is the one to have open on
   camera; sort it by `observed_at` and leave the `provenance_class` column visible so live,
   fixture and authored rows are distinguishable at a glance.
5. Row Level Security is on by default for new tables and the frontend never touches this
   database, so leave RLS enabled and read through the dashboard or the service key from the
   worker only. **The browser must never hold a database credential** — the frontend is a pure
   renderer over a committed `demo.json`, with zero client-side database access and zero client
   env vars. That is the single biggest risk mitigation in the plan; do not undo it to save a
   file copy.

### Why the portable choices look the way they do

| Choice | Reason |
|---|---|
| `TEXT` primary keys, ids generated in Python | No `AUTOINCREMENT`, no `SERIAL`, no sequence to diverge between engines. Ids are readable in the demo (`clm_dr_mrr`, `opp_ledgerline`). |
| Timestamps as `TEXT` holding ISO-8601 UTC (`2026-07-19T02:14:33Z`) | SQLite has no date type. ISO-8601 UTC is lexicographically sortable, so `observed_at <= :asof` is a correct string comparison in both engines. |
| Booleans as `INTEGER` with `CHECK (x IN (0,1))` | SQLite has no boolean type and stores 0/1; Postgres accepts 0/1 into `INTEGER` without complaint. |
| Nested structures as `TEXT` holding JSON | SQLite's JSON1 reads `TEXT` fine and Postgres will cast it. |
| Enums as `CHECK ... IN (...)` | Postgres `CREATE TYPE ... AS ENUM` does not exist in SQLite, and a `CHECK` is easier to read on camera anyway. |
| `REAL` for all floats | Valid in both. |
| No defaults calling a function | `datetime('now')` is SQLite-only and `CURRENT_TIMESTAMP` formats differently across the two. All timestamps are supplied by the worker, which also keeps them deterministic for a fixed `asof`. |

### Optional Postgres upgrades, once it is on Supabase and stable

None of these are required, and none should be attempted before the demo is recorded. They are
listed so nobody has to rediscover them later.

- `sections_json`, `gaps_block_json`, `bear_case_json`, `reference_class`, `bbox`,
  `conditions_to_close`, `falsification_conditions`, `merged_from_json` → `JSONB`, which buys
  GIN indexing and containment queries.
- Timestamp columns → `TIMESTAMPTZ`. Postgres parses the ISO-8601 strings on `ALTER TABLE ...
  USING col::timestamptz` without a data migration. **This breaks SQLite compatibility**, so
  only do it if local SQLite has been retired.
- The `CHECK ... IN (...)` enums → native `ENUM` types.
- Money columns → `NUMERIC` instead of `INTEGER` cents/dollars.

### Enforcing append-only at the database level (optional, post-demo)

The invariant is currently enforced by convention plus the audit
`grep -rniE "UPDATE |DELETE FROM" worker/`, which must come back empty. Database-level
enforcement is a nice prop but the syntax is engine-specific, so it is kept **out of**
`schema.sql` to protect the paste-verbatim property above. If you want it on Supabase:

```sql
-- Postgres only. Do NOT add this to schema.sql; it will not run under SQLite.
CREATE OR REPLACE FUNCTION refuse_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'observation is append-only: % refused', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER observation_append_only
  BEFORE UPDATE OR DELETE ON observation
  FOR EACH ROW EXECUTE FUNCTION refuse_mutation();
```

The SQLite equivalent, if it is ever wanted locally, is
`CREATE TRIGGER ... BEFORE UPDATE ON observation BEGIN SELECT RAISE(ABORT, '...'); END;` — also
kept out of `schema.sql` for the same reason.

---

## Mechanical audits touching this directory

```bash
# no averaged score column, anywhere        -> expect empty
grep -rniE "composite|overall_score|blended" db/schema.sql web/public/demo.json

# the asof chokepoint is exactly one function -> expect exactly one hit, in worker/store.py
grep -rn "FROM observation" worker/

# append-only                                -> expect empty
grep -rniE "UPDATE |DELETE FROM" worker/

# schema applies                             -> expect 20 tables, no error
python worker/init_db.py && sqlite3 db/counterproof.db ".tables"
```

All four were run against this schema before it was committed. The schema itself additionally
survives being applied twice in a row and rejects, at insert time: a market axis carrying a
numeric point, a numeric axis carrying a categorical value, a founder score interval that does
not bracket its point, an unknown claim state, an unknown source class, an unknown verdict, a
duplicate `(source_url, claim_type, value_hash)`, and a foreign key to a nonexistent row.
