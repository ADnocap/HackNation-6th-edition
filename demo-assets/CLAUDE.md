# demo-assets/ — Wacil's area (demo assets & submission)

Your brief is `docs/TASKS.md`, section **WACIL**. The demo script is `docs/IDEA.md` section H.

## Scope

You own `demo-assets/` — and **only** `demo-assets/`. This is deliberate: nothing you do can
break the build, so you never have to worry about that. Everything here is content, not code.

**You may read any file in the repo. Do not edit anything outside `demo-assets/`.**
If you spot a problem elsewhere (a wrong name in `web/public/demo.json`, a broken README step),
write it down in `demo-assets/PSEUDONYMIZATION.md` or `docs/HANDOFF.md` and tell Alexandre.
Do not fix it yourself — someone is editing that file right now.

## Why this work matters

The single best moment in our three-minute demo is a lie caught on camera *with the receipt*:
the pitch deck claims €41K MRR, and a live page fetch shows three employees and a silent
changelog. Both halves of that moment are your files. If they aren't right, our peak doesn't exist.

## Rules specific to this directory

- **The fixture sites must be deployed to real, public URLs** (free Vercel or GitHub Pages).
  Our validator performs a genuine HTTP GET. Served from `localhost`, the receipt is
  indistinguishable from a mock and a judge can tell. Record the URLs in
  `demo-assets/FIXTURE-URLS.md` as soon as they're live.
- **The deck's planted contradictions must match the fixture sites exactly.** They are two
  halves of one puzzle — the deck says 12 employees, the team page shows 3. Author them together.
- **Never use LinkedIn as a fixture source.** We publicly decline LinkedIn in our own
  not-collected ledger, so citing it contradicts our stated method on camera. Use a team page
  or a job listing instead.
- **The fictional company must be clearly fictional** — invented name, invented customer. We
  are demonstrating that our system catches exaggeration; doing that with a real company's
  name attached to a fabricated lie would be defamatory, and a judge would rightly hate it.
- **Real people appearing anywhere in the demo get pseudonymized** to initials + channel +
  signals. We build scored dossiers on private individuals from public records; on camera they
  are anonymous, and outreach is drafted but never sent.
- Plain HTML and CSS for the fixture sites. No frameworks, no build step.

## Working

Branch `feat/wacil-demo-assets`. Push every 45 minutes minimum. Never commit to `main`.

**Hard checkpoint: the deck and the fixture sites must be done by 20:00 ET / 02:00 Paris.**
If they won't be, say so early — Alexandre takes them over and we need the runway.
