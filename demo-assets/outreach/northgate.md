# Cold outreach — Northgate Settle (outbound hero)

**Status: DRAFTED, NEVER SENT.** Outbound messages to founders discovered from public records
are drafted and rendered on screen, and never actually sent. This is stated in the demo, on
the outreach panel, and here. The recipient is fictional; the mechanism is what's being shown.

This is the polished version of the draft embedded in the demo data
(`opportunities.opp_northgate.elicitation.outreach.draft_body`). If the two ever diverge, the
demo data wins — flag it in `docs/HANDOFF.md` rather than editing `worker/`.

---

## The message

> **Subject: your trademark filing from 2026-07-07 — one question before I form a view**
>
> I came across your intent-to-use trademark application filed 2026-07-07 (serial 98/447,913,
> attorney field empty) and the live Stripe checkout at northgatesettle.com. A self-filed $250
> mark plus a site that's already taking payment is a stronger signal than most pitch decks —
> it's why I'm writing now, before you've pitched anyone, rather than after.
>
> Your site says 40 paying sellers. Before I form a view I'd rather ask than assume: which
> channel produced the first ten, and is there one Stripe payout date I can verify? A pointer
> is worth more to me than a story — and "it's actually 12" is a perfectly good answer, because
> what I'm evaluating is whether the number survives checking, not how big it is.

---

## Design notes (why the message is shaped like this)

- **It is not "please apply."** The brief's Activate step is *cold outreach, not cold
  investment* — the goal is to trigger a real application by proving the system has already
  done its homework.
- **Paragraph 1 quotes the exact triggering observation with its date and identifiers** —
  filing date 2026-07-07, serial 98/447,913, the empty attorney field, the live checkout URL.
  The founder can verify in ten seconds that this isn't a mail-merge.
- **Paragraph 2 asks for counter-evidence to exactly one claim** (`clm_mo_users`, "40 paying
  users" — the claim the value-of-information computation selected, because resolving it
  narrows the posterior interval the most). It demands a **checkable pointer** (a Stripe payout
  date), not a narrative. Fluent, atom-free prose scores near zero; only someone who did the
  work can produce an atom that corroborates.
- **Conceding is priced up, not down** — "it's actually 12 is a perfectly good answer" is in
  the message on purpose. The scoring rewards volunteered weakness, and saying so up front is
  what makes the ask honest rather than a trap.
- **No flattery, no fund boilerplate, no deadline pressure.** Two paragraphs. The founder's
  time cost is one email and one copy-paste.
