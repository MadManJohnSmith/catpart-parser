"""Classified export failures (ticket #32).

Every ``catpart-export`` failure is machine-readable: an
:class:`ExportError` carries a kebab-case ``error_class`` and a human
``detail`` naming the violated evidence claim, printed as one JSON line
on stderr with exit code 1 (usage errors exit 2 via argparse, mirroring
``catpart-inspect``/``catpart-fitness``).

Error classes (ticket #32, consistent with the fitness classification
convention of kebab-case classes plus evidence-citing detail):

- ``missing-geometry-store``: no ``CATStdCont`` block, or no validated
  nested stream store in any ``CATStdCont``/``CATXDocLinkCont``/
  ``CATSeeBodyCont`` region (G1's miss taxonomy,
  docs/evidence/2026-11-09-nested-store.md section 6; the non-stdcont
  probes are the stage-3a recovery extension, #34).
- ``undecoded-variant``: a store is present but its geometry is not
  exportable under the pinned decode model — composite index space
  (G3 claim F8, open question 1), facet references beyond the pool
  (G3 open question 2), or no exportable facet content at all
  (0x41/0x44/0x4b/0x4e-only stores, G3 open questions 3-5).
- ``malformed-store-header``: a ``V5_CFV2`` header is present but fails
  the G1 N2 validation (ff x 8, zeros x 8, sane dwords, catalog magic),
  or its catalog tail matches neither the N6 trailer laws nor the two
  stage-3a relaxed-tail recovery families (dword8-overshoot, padded).
- ``malformed-pool-group``: a ``01 06`` pool group's walked vertex-record
  count does not equal its count field (G2 claim P2g violation; 2,326/
  2,326 corpus groups walk exactly, so a mismatch is broken structure).
- ``malformed-pool-vertex``: non-finite (NaN/inf) coordinates in the
  pool (G2 claim P3 violation; 100% finite corpus-wide).
- ``no-evaluable-surface``: the part carries ``a5 03 34`` surface
  frames but none passes the exact B-spline evaluable battery, or none
  yields a sane tessellation (docs/evidence/2026-11-19-surface-head.md
  section 5, 2026-11-19-surface-tessellation.md). A vertices-only or
  empty mesh is never reported as a surface export.
- ``untriangulable-grid``: the part carries at least one structured
  point-grid candidate (a ``rows x cols`` reading of an ``e5 0d`` record
  payload or of the content-prefix f64 allocation, ``rows, cols >= 3``)
  but none passes the triangulation gates — a stalled station/column
  step, a zero-area cell, a non-manifold cell complex, or (prefix
  dialect only) non-monotone / non-uniform stations.  The grid is an
  inferred connectivity, never a decoded surface, and an empty or
  partial mesh is never reported as one (docs/evidence/
  2026-11-19-grid-meshing.md).  A part with no ``>=3x3`` grid candidate
  keeps its pre-grid classification (``missing-geometry-store`` /
  ``undecoded-variant`` / ...).
- ``unreadable-file`` / ``io-error``: input path cannot be read, output
  cannot be written (OSError).
"""

from __future__ import annotations


class ExportError(Exception):
    """A classified ``catpart-export`` failure.

    ``error_class`` is the machine-readable class (kebab-case), ``detail``
    the human explanation citing the evidence claim that was violated.
    """

    def __init__(self, error_class: str, detail: str) -> None:
        super().__init__(f"{error_class}: {detail}")
        self.error_class = error_class
        self.detail = detail
