"""Classified export failures (ticket #32).

Every ``catpart-export`` failure is machine-readable: an
:class:`ExportError` carries a kebab-case ``error_class`` and a human
``detail`` naming the violated evidence claim, printed as one JSON line
on stderr with exit code 1 (usage errors exit 2 via argparse, mirroring
``catpart-inspect``/``catpart-fitness``).

Error classes (ticket #32, consistent with the fitness classification
convention of kebab-case classes plus evidence-citing detail):

- ``missing-geometry-store``: no ``CATStdCont`` block, or no validated
  nested stream store in any ``CATStdCont`` region (G1's miss taxonomy,
  docs/evidence/2026-11-09-nested-store.md section 6).
- ``undecoded-variant``: a store is present but its geometry is not
  exportable under the pinned decode model — composite index space
  (G3 claim F8, open question 1), facet references beyond the pool
  (G3 open question 2), or no exportable facet content at all
  (0x41/0x44/0x4b/0x4e-only stores, G3 open questions 3-5).
- ``malformed-store-header``: a ``V5_CFV2`` header is present but fails
  the G1 N2 validation (ff x 8, zeros x 8, sane dwords, catalog magic).
- ``malformed-pool-group``: a ``01 06`` pool group's walked vertex-record
  count does not equal its count field (G2 claim P2g violation; 2,090/
  2,090 corpus groups walk exactly, so a mismatch is broken structure).
- ``malformed-pool-vertex``: non-finite (NaN/inf) coordinates in the
  pool (G2 claim P3 violation; 100% finite corpus-wide).
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
