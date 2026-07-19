# Video scripts — 2 × 60 seconds

**Live demo:** https://adnocap.github.io/counterproof/
**Repo:** https://github.com/ADnocap/HackNation-6th-edition

Record from the **live URL** (it can't break — static, no server). Pre-load all
five tabs before recording. 1440px window. Speak at a normal pace — both scripts
below are timed to land just under 60s.

---

# VIDEO 1 — Demo (60s) · UI/UX and product flow

> Judges want: does this feel like a product, and can a non-technical investor use it?
> Show *flow*, not architecture. Save the stack for video 2.

### 0:00–0:12 — The board · `/`

**Do:** Open on the board. Flip **RAW → ACCESS-NEUTRALIZED** once. Let the list
visibly reorder before you speak again.

> "Every venture tool ranks founders by how visible they are. Visibility is
> already priced. We rank on what's left."

**Point at:** the ex-Stripe founder falling from #1 to #19.

> "Nothing about that person changed. We just stopped paying for the part of the
> signal the market had already bid up."

### 0:12–0:28 — The cold-start founder · `/person/per_mo/`

**Do:** Click through from the board.

> "She has no GitHub, no funding, no network. We found her through a self-filed
> trademark — two hundred and fifty dollars, no attorney on record. Someone
> building, with no law firm, therefore no funding, therefore no network."

**Point at:** the grey hatched rows in the manifest.

> "These are things we expected and didn't find. They're hatched, not faded,
> because absence we predicted costs her nothing. It widens the range. It never
> lowers the score."

### 0:28–0:45 — The catch · `/opportunity/opp_ledgerline/`

**Do:** Contradicted claims sort to the top. Open the **MRR** one.

> "Now an inbound deck. It claims forty-one thousand euro monthly revenue."

**Do:** Receipt opens — deck text left, fetched page right.

> "On the right is their own live page, with the URL and the time we fetched it.
> Three employees. A changelog that stopped. Eleven reviews."

### 0:45–0:60 — The decision · `/opportunity/opp_ledgerline/memo/`

**Do:** Scroll once past the five section headers. Stop on the gaps block.

> "The memo writes itself from claims that survived. Cap table: not disclosed —
> the renderer physically cannot invent it. The axes disagree, and we don't
> average them. Thirty-eight minutes from first signal to a decision an investor
> can act on."

---

# VIDEO 2 — Tech (60s) · stack, architecture, implementation

> Judges want: is this real engineering or a demo shell? Lead with the mechanism,
> then the proof. Screen-share the app and the terminal.

### 0:00–0:14 — The mechanism

**Show:** the leave-one-out panel on the MRR claim.

> "One idea runs the whole system. For any claim we derive what evidence *should*
> exist if it were true, then score the gap — a likelihood ratio, not a sum."

**Point at:** the expected-and-absent row at **−0.00**.

> "That's the arithmetic. When the reference class predicted the absence, the
> term is exactly zero. Same formula refutes a liar and protects a founder with
> no paper trail. No special case."

### 0:14–0:30 — The data layer

**Show:** terminal — `uv run python -m worker.prove_asof`

> "Eighteen hundred observations across eight hundred and forty-five people —
> live from USPTO trademark filings, arXiv, and Hacker News. Four collectors,
> every one able to fire for someone with no track record."

> "Memory is one append-only ledger. Every read goes through a single chokepoint
> that takes an as-of date. Same code path: seven-fifty-nine rows, then nine
> forty-three, then twelve-thirteen, then eighteen-fifteen. Set it to now, it's a
> live brain. Set it to the past, it's a backtest."

### 0:30–0:44 — Enforcement, not convention

**Show:** terminal — `uv run python -m worker.verify.check`

> "Append-only is enforced by database triggers, not discipline — update and
> delete are rejected, so the Founder Score cannot be reset."

> "And every evidence URL is re-fetched and checked that the quote we cite is
> actually on the page. Twenty-six checks, zero mismatches. A 404 where we
> predicted absence counts as a pass."

### 0:44–0:60 — The stack, and what we cut

> "Next.js and TypeScript on the front, a pure renderer over one committed JSON
> file — so a worker bug can't break the demo. Python with uv, SQLite, and Claude
> for extraction only. The model never emits a score and never writes prose;
> scoring is closed-form, which is what makes that attribution exact instead of a
> story the model tells about itself."

> "We deleted our own best statistics — conformal coverage, false-discovery
> control — because none had a target variable inside twenty-one hours. A
> tautological number in front of a finance judge is worse than none."

---

## Delivery notes

**Say the synthetic thing out loud in video 1**, ideally around 0:28 as you open
the deck. One clause is enough:

> "The board is real. The company I'm about to catch lying is one we wrote,
> because we needed a lie we knew the shape of — it's badged AUTHORED on screen."

Volunteering it converts the one weak spot into another instance of the honesty
you're selling. A judge who discovers it themselves reads it very differently.

**Pre-flight before each take:**
- `uv run python -m worker.verify.check` → must exit 0
- Hard-refresh the live URL
- Close every other tab and notification

**If you fluff a line, keep rolling.** One complete 60-second take beats three
abandoned perfect ones — and you can only upload one file per slot.

**Numbers you'll say — all verified, don't round them differently:**
1,815 observations · 845 people · 4 collectors · 26 checks, 0 mismatches ·
38 minutes first-signal-to-decision · −0.00 on the expected-absent row
