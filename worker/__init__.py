"""Counterproof worker.

The worker owns the append-only ledger and every read path into it.

Import rule for the rest of the system:

    from worker.ledger import read_observations

`read_observations(asof, ...)` is THE CHOKEPOINT. It is the only function in the
codebase that reads the observation table, and it always filters
``WHERE observed_at <= :asof``. Set ``asof=now()`` and the identical code path is
a live VC brain; set ``asof`` to a past date and it is a point-in-time backtest.
"""

__all__ = ["db", "ledger", "timing", "seed"]
__version__ = "0.1.0"
