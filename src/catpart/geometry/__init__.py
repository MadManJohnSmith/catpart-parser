"""Geometry export: the nested V5_CFV2 store's pool + facets as PLY.

The vertical build slice of Phase 4 (ticket #32), consuming the pinned
decode models one level per module:

- :mod:`catpart.geometry.store` — nested-store navigation (G1,
  docs/evidence/2026-11-09-nested-store.md),
- :mod:`catpart.geometry.pool` — the vertex pool (G2,
  docs/evidence/2026-11-09-vertex-pool.md),
- :mod:`catpart.geometry.facets` — facet-record primitive semantics
  (G3, docs/evidence/2026-11-09-facet-semantics.md),
- :mod:`catpart.geometry.mesh` / :mod:`catpart.geometry.ply` — mesh
  invariants and the binary little-endian PLY writer,
- :mod:`catpart.geometry.surface` — the exact ``a5 03 34`` degree-5
  B-spline surface evaluator and adaptive tessellator used when a part
  carries no facet records (docs/evidence/2026-11-19-surface-tessellation.md),
- :mod:`catpart.geometry.grid` — the structured point-grid (E5 / f64-net
  dialect) triangulator used only when a part carries neither facets nor
  an a5 frame; its connectivity is an explicit **candidate** inference
  (docs/evidence/2026-11-19-grid-meshing.md),
- :mod:`catpart.geometry.display` — the last-resort display route for a
  part with no surface at all: the decoded carrier points and the
  law-pinned ``33 32`` curve segments, rendered as exactly that and never
  as a reconstruction (docs/evidence/2026-11-19-no-surface-fallback.md),
- :mod:`catpart.geometry.export` — the ``catpart-export`` orchestration
  and its classified failure surface (:class:`ExportError`).

The decode logic is adapted from the triage decoders
(``scripts/triage/decode_nested_store.py``, ``decode_vertex_pool.py``,
``decode_facet_semantics.py``) with the semantics unchanged; the triage
scripts stay analysis tools and nothing here depends on ``scripts/``.
The core is stdlib-only (ADR-0002).
"""

from catpart.geometry.errors import ExportError
from catpart.geometry.export import EXPORT_SCHEMA_VERSION, build_export
from catpart.geometry.ply import write_binary_little_endian_ply

__all__ = [
    "EXPORT_SCHEMA_VERSION",
    "ExportError",
    "build_export",
    "write_binary_little_endian_ply",
]
