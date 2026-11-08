"""Minimal invariants over the ``catpart-inspect`` output.

A clean parse — L1's unit (GLOSSARY.md) — "terminates without error,
emits JSON valid against the repo's versioned schema, and satisfies the
minimal invariants". The fitness runner (ticket #14) classifies a
schema-valid report that fails an invariant as ``missing-invariant``.

The v1 output (ticket #23) can express invariants beyond the one v0
field set; every entry below is a corpus-wide law **within its stated
scope**, citing the evidence note and rates that justify it. Invariants
whose scope is the trailer apply only when the report carries one — the
262/1818 corpus files without a ``CB__END\\0`` tail (including the
dual-region files without one) are not held to trailer laws. "Trailer
presence where applicable" is exactly this scoping: there is no
documented criterion predicting trailer presence, so presence itself is
never an invariant.

- ``header-dword-below-file-size``: the big-endian dword at header bytes
  8-12 is smaller than the file size across the whole Phase 1 corpus
  (docs/evidence/2026-11-07-container-triage.md, "Outer container
  structure": always < file size; ``size - dword`` has median 10280 and
  min 3138).

- ``magic-v5-cfv2``: header bytes 0-8 decode to ``V5_CFV2`` on all 1818
  magic-verified corpus files (Phase 1 evidence note, bytes 0-8); the 6
  corpus files known to lack it are mislabeled non-CATIA files and are
  the honest non-clean denominator.

- ``tail-region-chain`` (trailer present): dword8 + dword12 == file size
  and trailer G == dword12 — law H1 (docs/evidence/
  2026-11-07-container-table-and-trailer.md), 1556/1556 CB__END-ending
  files; dword8 is the ``CATIA_V5 CB0001\\0`` tail region's start offset
  and dword12 its length.

- ``trailer-constants`` (trailer present): trailer A == 1 and C == D —
  1556/1556 CB__END-ending files each (same note, "Trailer"). E == 0
  holds only on 1555/1556 (the exception is a real dual-region file), so
  E is reported as-is and never enforced.

- ``container-kind-known``: a file whose table was parsed names
  ``CATPrtCont`` (part) or ``CATProdCont``/``CATMechProdCont`` (product)
  — 0 counterexamples on 1810 with-table files (law K1, docs/evidence/
  2026-11-07-container-kind-law.md). ``unknown`` kind with a non-empty
  container list contradicts the documented law.

- ``units-present`` — **defined, not enforced (documented negative,
  ticket #25)**. The glossary's clean-parse checklist names "units
  present"; C3 phase A probed the two decoded territories (container
  payload regions, OSMX/stream territory + CB0001 tail) for a model
  unit system on a 108-file R15-R24 sample and found none
  (docs/evidence/2026-11-08-units-names-probe.md): zero framed
  unit-token structures anywhere (U2 0/108, P1 0/108), every unit-token
  hit being either the drafting ``Pixel``/``mm`` drawing-scale store of
  the 2 drafting-namespace files (B3's documented exception — viewport
  scales, not model units) or a verified binary coincidence, and the
  spec-tree ``Volume/Mass/Length`` tokens being model content, not a
  document-level declaration. The parser therefore emits no units field
  (the evidence rule: a structure without a documented claim is not
  implemented), and the invariant, defined with its documented
  exceptions, holds on every file: no file is penalized for lacking
  something the corpus does not document. This is the C2 precedent
  (docs/evidence/2026-11-08-container-tree.md): a claimed structure
  that fails measurement closes as a documented negative. The check
  enters INVARIANTS only when a units claim lands and the parser emits
  the corresponding field; the probe records where a future search
  would have to look (and that a token-less enum encoding is out of
  reach of byte evidence in those territories).

The name-side claim of the same ticket IS parsed: ``document_name``
(the CATIA identity block's save-time document name,
docs/evidence/2026-11-08-units-names-probe.md) — reported as-is, with
no invariant: the field is version-dependent (40/108 sample files,
0/43 on R20+) and optional by design, so absence is a documented
shape, not a defect.
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


def _magic_v5_cfv2(report: dict) -> str | None:
    magic = report["magic"]
    if magic != "V5_CFV2":
        return f"magic {magic!r} is not 'V5_CFV2'"
    return None


def _tail_region_chain(report: dict) -> str | None:
    trailer = report["trailer"]
    if trailer is None:
        return None
    dword8 = report["header_dword"]
    dword12 = report["header_dword12"]
    size = report["file_size"]
    if dword8 + dword12 != size:
        return f"header_dword {dword8} + header_dword12 {dword12} != file_size {size}"
    tail_length = trailer["tail_region_length"]
    if tail_length != dword12:
        return f"trailer tail_region_length {tail_length} != header_dword12 {dword12}"
    return None


def _trailer_constants(report: dict) -> str | None:
    trailer = report["trailer"]
    if trailer is None:
        return None
    if trailer["a"] != 1:
        return f"trailer a {trailer['a']} is not 1"
    if trailer["c"] != trailer["d"]:
        return f"trailer c {trailer['c']} != d {trailer['d']}"
    return None


def _container_kind_known(report: dict) -> str | None:
    if report["containers"] and report["kind"] == "unknown":
        return (
            f"kind is unknown but {len(report['containers'])} table records "
            "were parsed (kind law K1: a with-table file names CATPrtCont "
            "or CATProdCont/CATMechProdCont)"
        )
    return None


INVARIANTS: tuple[Invariant, ...] = (
    ("header-dword-below-file-size", _header_dword_below_file_size),
    ("magic-v5-cfv2", _magic_v5_cfv2),
    ("tail-region-chain", _tail_region_chain),
    ("trailer-constants", _trailer_constants),
    ("container-kind-known", _container_kind_known),
)


def check_invariants(report: dict) -> str | None:
    """Return the first invariant failure, or ``None`` when all hold.

    ``report`` must already be schema-valid (the runner validates against
    schema v1 first), so the keys the checks read are guaranteed present.
    """
    for name, check in INVARIANTS:
        failure = check(report)
        if failure is not None:
            return f"{name}: {failure}"
    return None
