"""Minimal invariants over the ``catpart-inspect`` output.

A Clean parse — L1's unit (GLOSSARY.md) — "terminates without error,
emits JSON valid against the repo's versioned schema, and satisfies the
minimal invariants". The fitness runner (ticket #14) classifies a
schema-valid report that fails an invariant as ``missing-invariant``.

The glossary names the eventual minimal invariants (units present,
feature tree present when the file has one); those output fields do not
exist in schema v0, so v0 ships exactly one invariant — the only one the
v0 output can express with committed evidence:

- ``header-dword-below-file-size``: the big-endian dword at header bytes
  8-12 is smaller than the file size across the whole Phase 1 corpus
  (docs/evidence/2026-11-07-container-triage.md, "Outer container
  structure": always < file size; ``size - dword`` has median 10280 and
  min 3138). A parse reporting ``header_dword >= file_size`` describes
  a file that contradicts the only structure v0 parses.

Later levels add invariants next to the output fields they need; every
entry must cite its evidence note and byte ranges, like the parser
modules do.
"""

from __future__ import annotations

from collections.abc import Callable

#: Name of each invariant paired with its check. A check receives the
#: schema-validated ``catpart-inspect`` report and returns ``None`` when
#: the invariant holds, otherwise a short failure description.
Invariant = tuple[str, Callable[[dict], str | None]]


def _header_dword_below_file_size(report: dict) -> str | None:
    dword = report["header_dword"]
    size = report["file_size"]
    if dword >= size:
        return f"header_dword {dword} is not below file_size {size}"
    return None


INVARIANTS: tuple[Invariant, ...] = (
    ("header-dword-below-file-size", _header_dword_below_file_size),
)


def check_invariants(report: dict) -> str | None:
    """Return the first invariant failure, or ``None`` when all hold.

    ``report`` must already be schema-valid (the runner validates against
    schema v0 first), so the keys the checks read are guaranteed present.
    """
    for name, check in INVARIANTS:
        failure = check(report)
        if failure is not None:
            return f"{name}: {failure}"
    return None
