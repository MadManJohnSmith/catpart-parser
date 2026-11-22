"""Deterministic binary-signature families for store-level failures
(W8, marathon wave 4; the ``fail-unclassified`` residue).

The W6 Top-1 ROI row (366 ``fail-unclassified`` submarine parts) is
closed at base dae7dd1: the per-file harness names every failure
(``error_class`` / ``failed_check``) and the census at base counts 0
unclassified rows on both corpora (docs/evidence/
2026-11-22-w8-unclassified.md). What remained unnamed is the VARIANT
level: ``undecoded-variant`` covers both real variant gaps (content the
pinned decode families do not cover) and stores that carry no geometry
payload at all. This module names the latter deterministically.

The ``empty-geometry-store`` family (W8 signature law; measured 10/10
on the official corpus's ``undecoded-variant`` cluster — CAA
fixture parts whose located ``CATStdCont`` store bodies are 648-2,575 B
with no payload markers):

- the store located and validated (G1 N2/N6 passed — this is NOT
  ``missing-geometry-store``);
- zero pool groups (the no-pool arm: the flattened pool is empty);
- zero ``10 24 04 ff ff 00 00 00`` wrapper markers (``kinds == []`` —
  no pool sub-kind, no composite index space, no trailer opener);
- zero facet-header candidates (the facet scan finds nothing).

Such a body cannot export under ANY pinned decode family — there is
nothing to decode — so the honest classification is the store's own.
A body with ANY wrapper marker or ANY facet candidate keeps
``undecoded-variant`` (a real variant gap). The check runs where the
no-pool error is constructed, before the stage-13 second-chance route
(:func:`catpart.geometry.export._unrouted_element_space`): a
token-bearing list-node store still exports through that route and the
constructed error object is discarded, so every exporting store is
row-identical (fail-closed wiring).
"""

from __future__ import annotations

import dataclasses

from catpart.geometry import facets, pool, store
from catpart.geometry.errors import ExportError

#: The W8 named class: a located, validated store whose body carries no
#: geometry payload of any pinned kind (the kebab-case vocabulary of
#: ``errors.py``).
EMPTY_GEOMETRY_STORE = "empty-geometry-store"

#: The G2 P8 no-pool classification this module refines (kept verbatim:
#: bodies outside the signature law keep it).
UNDECODED_VARIANT = "undecoded-variant"

_NO_POOL_DETAIL = (
    "no 01 06 vertex pool decoded from the store body (G2 P8 family: "
    "strips without a pool, or an empty store)"
)


@dataclasses.dataclass(frozen=True)
class BodySignature:
    """The W8 binary signature of one store body.

    Every field is a direct measurement of the body bytes (no parse
    beyond the pinned scanners): the wrapper sub-kinds found after the
    full wrapper, the facet-header candidate count, and the body
    length. ``pool_groups`` travels separately from the pool scan (the
    caller has it; the no-pool arm implies zero groups).
    """

    body_bytes: int
    kinds: tuple[bytes, ...]
    facet_candidates: int
    pool_groups: int

    @property
    def is_empty_payload(self) -> bool:
        """The ``empty-geometry-store`` signature law (W8).

        Zero pool groups, zero wrapper markers, zero facet candidates:
        no pinned payload marker of any kind. A body with any marker
        keeps ``undecoded-variant``.
        """
        return (
            self.pool_groups == 0
            and not self.kinds
            and self.facet_candidates == 0
        )

    @property
    def signature(self) -> str:
        """The stable cluster signature string for the census tool."""
        return (
            f"body={self.body_bytes} pools={self.pool_groups} "
            f"kinds={','.join(k.hex() for k in self.kinds) or '-'} "
            f"facet-cands={self.facet_candidates}"
        )


def body_signature(data, body_lo: int, body_hi: int, pool_groups: int = 0) -> BodySignature:
    """Measure one store body's binary signature (W8 census law).

    Reads the wrapper sub-kinds in ``[body_lo, body_hi)`` (the same
    ``10 24 04 ff ff 00 00 00`` scan the pool decoder uses) and the
    facet-header candidate count (the same :func:`facets.scan_facets`
    call the exporter's clean path makes). No other parse.
    """
    kinds: list[bytes] = []
    for offset in store.find_all(data, pool.FULL_WRAP, body_lo, body_hi):
        kinds.append(bytes(data[offset + 8 : offset + 10]))
    scan = facets.scan_facets(data, body_lo, body_hi, clean_store=True)
    return BodySignature(
        body_bytes=body_hi - body_lo,
        kinds=tuple(kinds),
        facet_candidates=scan.candidates,
        pool_groups=pool_groups,
    )


def no_pool_error(data, span: store.StoreSpan, kinds: list[bytes]) -> ExportError:
    """The no-pool arm's classification (W8 wiring for ``export.py``).

    Called where ``_export_store`` is about to raise the G2 P8 no-pool
    error (flattened pool empty). ``kinds`` is the caller's pool-scan
    sub-kind list (the authoritative body-order measurement, already in
    hand); the facet candidate count comes from the same
    :func:`facets.scan_facets` call the clean path makes. A body
    matching the ``empty-geometry-store`` signature law raises the
    named class; any other body keeps the original
    ``undecoded-variant`` error verbatim (fail-closed: the stage-13
    second-chance route and the composite path are untouched).
    """
    scan = facets.scan_facets(data, span.body_lo, span.body_hi, clean_store=True)
    signature = BodySignature(
        body_bytes=span.body_hi - span.body_lo,
        kinds=tuple(kinds),
        facet_candidates=scan.candidates,
        pool_groups=0,
    )
    if signature.is_empty_payload:
        return ExportError(
            EMPTY_GEOMETRY_STORE,
            f"the located store body carries no geometry payload of any "
            f"pinned kind ({signature.signature}; W8 signature law, "
            f"docs/evidence/2026-11-22-w8-unclassified.md — the part's "
            f"geometry, if any, lives outside the nested stream store)",
        )
    return ExportError(UNDECODED_VARIANT, _NO_POOL_DETAIL)
