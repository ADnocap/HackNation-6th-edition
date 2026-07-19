"""A6 — the verification layer. Two mechanisms, rigidly separate.

This package exists to make one demo moment honest: when the board says a claim was
contradicted by a page we fetched, somebody can re-run this and watch the fetch happen.

    worker/verify/fetch.py    RETRIEVAL. httpx GET of a specific URL. Deterministic,
                              disk-cached by content hash, offline-replayable, and it
                              works on a page published ten minutes ago. This is what
                              backs the receipt pane.

    worker/verify/tavily.py   SEARCH. Tavily's index, for entities ALREADY indexed on
                              the public web — market comparables, prior funding
                              rounds. Never for our own fixture sites.

    worker/verify/check.py    The auditor. Re-fetches every evidence row that carries a
                              source_url and asks whether the excerpt we attributed to
                              that page is actually on it.

WHY THE SPLIT IS ENFORCED RATHER THAN REMEMBERED
------------------------------------------------
Tavily is a search index, not a fetcher. It has never crawled our fixture origins and
will not before the deadline. Route a receipt through it and you get zero results —
which renders identically to "we could not check", except it is not true and it costs
an hour to diagnose at 3am. :mod:`worker.verify.tavily` therefore refuses fixture
origins outright and says why, instead of returning an empty list.

Run the auditor::

    uv run python -m worker.verify.check
"""

from __future__ import annotations
