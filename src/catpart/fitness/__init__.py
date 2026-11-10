"""Fitness runner (ADR-0001, ticket #14): report, history, no-regret.

One run of ``catpart-fitness`` = one full report JSON plus exactly one
row — accepted or rejected — appended to the committed append-only
``fitness/history.jsonl``. Modules:

- :mod:`catpart.fitness.runner` — manifest reading, per-file
  classification through the in-process ``catpart-inspect`` seam,
  per-split aggregation, report/history writing.
- :mod:`catpart.fitness.history` — the history row contract and the
  no-regret acceptance rule (ADR-0001).
- :mod:`catpart.fitness.invariants` — minimal invariants over the
  ``catpart-inspect`` output (part of the Clean parse definition,
  GLOSSARY.md).

The real corpus is measured only on the machine holding ``corpus/``
(ADR-0003); every test here runs on synthetic fixtures without it.
"""

from __future__ import annotations


class FitnessError(Exception):
    """A fitness run could not be completed or the history is unusable.

    Raised for operator-facing failures: unreadable or malformed
    manifest, corrupt committed history, unwritable artifacts, or an
    internal artifact that violates its committed schema. The console
    script turns it into a ``catpart-fitness: error: ...`` message with
    exit code 1.
    """


# Public API of the fitness seam, re-exported after FitnessError is
# defined: the submodules import FitnessError from this package, so the
# definition above must execute before these imports run.
from catpart.fitness.history import (  # noqa: E402
    LevelScore,
    NoRegret,
    PartScore,
    SplitScore,
    evaluate_no_regret,
)
from catpart.fitness.runner import run_fitness  # noqa: E402

__all__ = [
    "FitnessError",
    "LevelScore",
    "NoRegret",
    "PartScore",
    "SplitScore",
    "evaluate_no_regret",
    "run_fitness",
]
