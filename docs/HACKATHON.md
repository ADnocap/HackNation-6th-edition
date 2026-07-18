# Hack-Nation — 6th Global AI Hackathon & Venture Incubation Program

> Sources: official info deck (Google Drive, July 2026), hack-nation.ai, Luma event page.
> Local copy of the deck: `docs/assets/hacknation-6th-deck.pdf`

## The event in one paragraph

A 24-hour global AI hackathon on **July 18–19, 2026**, run by Hack-Nation in collaboration with the MIT Club of Germany and MIT Club of Northern California. ~2,000+ admitted hackers (from 5,500+ applications, ~50% graduate level+) from MIT, Harvard, Stanford, Oxford, ETH Zürich and 60+ countries, competing online or at 12+ physical hubs (Stanford, SF, Cambridge US, NYC, London, Dresden, Munich, Zurich, Linz, Brussels, Delhi…). Teams pick from a set of sponsor challenges revealed at kickoff and build an AI product from scratch in 24 hours. 200+ judges from MIT, Harvard and big tech review 400+ submissions.

## Schedule (all times ET — Paris = ET + 6h)

| When | What | ET | Paris |
|---|---|---|---|
| Sat, Jul 18 | Kick-off & speaker session | 11:15 AM – 12:05 PM | 5:15 – 6:05 PM |
| Sat, Jul 18 | **Reveal of challenges** | 12:05 – 12:15 PM | 6:05 – 6:15 PM |
| Sat, Jul 18 | **Hacking begins** | 12:15 PM | 6:15 PM |
| Sun, Jul 19 | **Submission deadline** | **9:00 AM** | **3:00 PM** |
| Sat, Jul 25 | Finalist pitches (3 min; top 3 per challenge) | 12:00 – 2:00 PM | 6:00 – 8:00 PM |
| Sat, Jul 25 | Awards ceremony | 2:15 PM | 8:15 PM |

Net build time: ~21 hours (12:15 PM ET Sat → 9:00 AM ET Sun).

## Format

- Challenges are **revealed at kickoff** — no pre-formed idea needed; teams choose one challenge to compete in.
- Each challenge is sponsored by a partner company (past sponsors of challenges: ElevenLabs, AkashX, and "VC Big Bet" open tracks).
- 1st, 2nd and 3rd place **of each challenge** advance to the finalist pitches on July 25 (3-minute pitch, public event).

## The 6 challenges (revealed — see `docs/CHALLENGES.md` for full briefs)

1. **The Negotiator** (ElevenLabs) — voice agents that call, compare, and haggle.
2. **The VC Brain** (Maschmeyer Group) — AI that sources founders and deploys $100K checks in 24h.
3. **RealDoor** (RealPage) — renter-side affordable-housing application-readiness copilot.
4. **Data Legend** (Databricks) — trust layer over 10k messy Indian healthcare records; live Databricks App.
5. **Women's Hormonal Health** (Hack-Nation/OpenAI) — open reusable dataset/benchmark/model/app.
6. **Genome Firewall** (OpenAI) — predict antibiotic resistance from a bacterial genome, calibrated + defensive.

Each challenge is judged and prized separately; 1st/2nd/3rd per challenge advance to the July 25 finalist pitches.

Past winning projects (for flavor): generative 3D jewelry design, anomaly detection on thermal drone footage, multilingual WhatsApp scam-detection agent, financial document analysis, protein structure prediction from small datasets.

## What winning looks like (inferred from past winners & format)

The deck doesn't publish formal judging criteria (they typically come with each challenge brief), but the pattern from winners and the 3-minute-pitch format is clear:

1. **A live, working demo** — every showcased winner has a demo video; "1500+ trained AI models and prototypes" is the stat they brag about. Real functionality > slideware.
2. **Direct hit on the sponsor's challenge** — winners are picked *per challenge*, judged largely by the sponsor's people. Solve their stated problem, use their product/API if there is one.
3. **A tight, compelling 3-minute pitch** — the finalist format is 3 minutes. Problem → demo → why it matters. Practice it.
4. **Venture potential** — this is explicitly a "Hackathon & Venture Incubation Program". The top 30 teams get a 3-month incubation (Venture Lab, with EWOR — "the Y Combinator of Europe", plus a16z/Greylock/Antler/Creandum exposure on investor day, 1M€+ compute credits, MBA co-founder matching). Framing the project as a plausible startup helps.

## Prizes & what's at stake

- $28K+ prize pool historically per edition ($3,500 cash winner prize + $25K OpenAI API credits at recent editions).
- $150K+ in API credits from partners (OpenAI, Cursor, Lovable, …) available **during** the event.
- **Venture Lab**: top 30 teams → 3-month incubation, 30M€ total partner credits, dedicated senior mentor (YC/EWOR/Google/Adobe operators), Demo Day + Investor Day. Alumni have gotten into Y Combinator (e.g. Anto, YC F25) off their hackathon idea.

## Key partners / sponsors (6th edition deck)

OpenAI, Databricks, Lovable, Cursor, Vercel, Supabase, Tavily, ElevenLabs, TeamViewer, DSV Gruppe, Spiral, The World Bank, yfood, Manage & More, Start2 Group, Boost Startup Factory, YETI, Red Bull, HRT, Masters' Union, MIT Sloan AI Club, HALKIN, Eleveight, AgentPark, Factory 300, ESGI, Amundi ACBA, Novu Campus, and more.

## Links

- Website: https://hack-nation.ai/
- Luma event: https://luma.com/8rfryv5k
- Official deck: https://drive.google.com/file/d/19O8pY997EJkzojEbEDmge4YMiuif9Usb/view
- Instagram: https://www.instagram.com/hacknation.globalai/
- LinkedIn: https://www.linkedin.com/company/hack-nation

## Status

- [x] List of 6th-edition challenges + briefs — see `docs/CHALLENGES.md` and `docs/assets/challenges/`
- [x] Official judging criteria per challenge — in each brief / `CHALLENGES.md`
- [x] Submission portal — https://projects.hack-nation.ai/
- [ ] Our team's chosen challenge — TBD (update `CLAUDE.md`)
- [x] API credit codes / sponsor tool access — decided, see below

## Credits & accounts — decision

Only two things on the sponsor credits page are worth touching for Challenge 02:

| Offer | Verdict | Why |
|---|---|---|
| **Tavily** (shared code, instant) | **Claim now** | On the critical path — the Validator's external claim checks. Use it *only* for entities already indexed on the public web (market comparables, prior rounds). **Not** for the demo's receipt pane: our fixture sites are hours old and Tavily will never have crawled them. That pane is a direct `httpx.get()` with the response body, final URL and fetch timestamp. See pre-mortem #5 in `IDEA.md`. |
| **Woz** (shared code, instant) | Claim the code, **don't install today** | Free option value for later. Installing new tooling mid-sprint is how you lose hour 3. |
| Lovable | Skip | Approval latency; not the Challenge 02 sponsor so there is no scoring bonus; and our frontend is a pure renderer over a committed `demo.json` with no client-side DB — Lovable's generated Supabase wiring fights that architecture (pre-mortem #10: 95 min lost to RLS + anon key). |
| ElevenLabs | Skip | Challenge 01's sponsor. No voice anywhere in our plan. A synthetic voiceover on a pitch whose whole thesis is honesty reads slightly off; use a human voice. |
| Emdash | Skip | Unfamiliar agent orchestrator, adopted mid-sprint. Violates "no exotic dependencies." |
| OpenAI | Not needed | Using our own key. Extraction is plain structured output; provider-agnostic. |

Tavily's hacker guide is committed at `docs/assets/tavily-hacker-guide.pdf`.

**Free tiers, no credits needed** — create accounts if not already done: **Supabase** (63 rows of Postgres), **Vercel** (one app deploy **plus a second static project for the contradiction fixtures — these must live at real public URLs**).

**Highest-urgency credential:** the **USPTO** account/API key is plan risk #1 (identity verification can take hours). Register immediately and start the daily bulk-XML download in the background now — that download is the committed fallback regardless of whether the key lands.
