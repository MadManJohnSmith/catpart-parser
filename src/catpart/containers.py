"""Container-name string scan (schema v0).

Evidence: docs/evidence/2026-11-07-container-triage.md. The container
name table is plaintext — at offsets ~0x7e4-0xd00 in the Phase 1 deep
sample — and consists of repeating ``CATContainer`` entries with names.
The note lists an explicit open question ("Container-table record format
(name + offsets? bounds?)") and concludes that layout is not
deterministic across saves beyond the 32-byte header. v0 therefore does
NOT parse table records; that is Phase 2 structure-inference work
(docs/ROADMAP.md).

v0 reports which of the evidence-documented container-name strings occur
anywhere in the file, as unique names in first-occurrence order. The
vocabulary is exactly the 18 names listed in the evidence note plus the
generic ``CATContainer`` entry the note describes the table as
repeating.

A needle only counts when bounded by non-name bytes (anything outside
``[A-Za-z0-9_]``): the corpus contains payload strings that merely
*contain* a vocabulary name (e.g. ``CATContainersForLinksNotUpdated``),
and those must not be reported as ``CATContainer``.

Known v0 limitations, both acceptable for schema v0 and revisited once
the record format is inferred: names outside the vocabulary are not
reported, and a vocabulary name counts as found wherever it occurs,
including payload regions (the ticket asks for strings "found in the
file", not for table membership).
"""

from __future__ import annotations

import mmap

# The 18 names documented in the evidence note's container-name table,
# plus the generic CATContainer entry the note describes as repeating.
CONTAINER_NAMES: tuple[str, ...] = (
    "CATCompoundCont",
    "CATProdCont",
    "CATFeatCont",
    "CATPrtCont",
    "CGMGeom",
    "CATMFBRP",
    "CATSeeBodyCont",
    "CATBRepModeContainer",
    "CATStdCont",
    "CATCGRCont",
    "CATContainer",
    "CameraStartupContainer",
    "contmeasure",
    "CATSiMuGenCont",
    "CATMechProdCont",
    "CATCtorProxyCont",
    "CATMaterialCont",
    "AppliCont",
    "V5USERID",
)

_NAME_BYTES = frozenset(
    b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
)


def _is_delimited(data: mmap.mmap | bytes, start: int, end: int) -> bool:
    """True when neither neighbor of ``data[start:end]`` is a name byte."""
    if start > 0 and data[start - 1] in _NAME_BYTES:
        return False
    if end < len(data) and data[end] in _NAME_BYTES:
        return False
    return True


def scan_container_names(data: mmap.mmap | bytes) -> list[str]:
    """Return the container names found in ``data``, in first-occurrence order.

    ``data`` is any bytes-like buffer with ``find()`` (``bytes`` or a
    read-only :class:`mmap.mmap`). Matching is whole-name only (see
    module docstring), so the result is deduplicated by construction.
    """
    hits: list[tuple[int, str]] = []
    for name in CONTAINER_NAMES:
        needle = name.encode("ascii")
        start = 0
        while True:
            offset = data.find(needle, start)
            if offset < 0:
                break
            end = offset + len(needle)
            if _is_delimited(data, offset, end):
                hits.append((offset, name))
            start = end
    hits.sort()
    ordered: list[str] = []
    for _, name in hits:
        if name not in ordered:
            ordered.append(name)
    return ordered
