"""``catpart-export`` orchestration: nested store -> PLY + summary (ticket #32).

The vertical build slice of Phase 4: navigate the nested V5_CFV2 store
(:mod:`catpart.geometry.store`, G1), decode the vertex pool
(:mod:`catpart.geometry.pool`, G2), decode the facet records under G3's
pinned primitive semantics (:mod:`catpart.geometry.facets`), assemble
the mesh invariants (:mod:`catpart.geometry.mesh`) and write a binary
little-endian PLY (:mod:`catpart.geometry.ply`).

Export rule (ticket #32, "export what the evidence pins"): a store
exports fully when G3's soup gate holds — no composite index space
(``01 02`` edge group / trailer-opener wrapper, F8 open question 1) and
every facet reference inside the pool (open question 2). Stores needing
the open composite-space decode fail ``undecoded-variant``; there is no
guessing. A pool without any facet header candidates is the G2 P7
family (pools can exist without connectivity) and exports vertices
only, with a warning.

On success the PLY is written to ``out_path`` and the schema-versioned
summary (:data:`EXPORT_SCHEMA_VERSION`, committed as
``catpart/schema/export-summary-v1.json``) returned; the summary is
self-checked against the committed schema like the fitness runner's
artifacts. Every failure raises :class:`ExportError` with a
machine-readable class (see :mod:`catpart.geometry.errors`).
"""

from __future__ import annotations

import mmap

from catpart.geometry.errors import ExportError
from catpart.geometry import facets, mesh, pool, ply, store

EXPORT_SCHEMA_VERSION = 1

WARN_UNRESOLVED_FAMILY = "unresolved-facet-family"
WARN_DEGENERATE = "degenerate-triangles-skipped"
WARN_OPEN_SHELL = "open-shell"
WARN_UNUSED_VERTICES = "unused-pool-vertices"
WARN_NO_FACETS = "no-facet-records"


def build_export(path, out_path) -> dict:
    """Export ``path``'s nested-store geometry to the PLY ``out_path``.

    Returns the summary dict (schema ``export-summary-v1``). Raises
    :class:`ExportError` on every classified failure; the PLY is written
    only after the whole store decodes, so failures leave no partial
    output.

    ``path``/``out_path`` are anything :func:`open` accepts (usually
    :class:`pathlib.Path`).
    """
    try:
        with open(path, "rb") as fh:
            data = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
    except OSError as exc:
        raise ExportError("unreadable-file", str(exc)) from exc
    try:
        summary, vertices, triangles = _export_data(data)
    finally:
        data.close()
    try:
        with open(out_path, "wb") as fh:
            ply.write_binary_little_endian_ply(fh, vertices, triangles)
    except OSError as exc:
        raise ExportError("io-error", f"cannot write {out_path}: {exc}") from exc
    return summary


def _export_data(data) -> tuple[dict, list, list]:
    """Decode ``data``'s first exportable CATStdCont store.

    Returns ``(summary, vertices, triangles)``. With several CATStdCont
    blocks the first store passing G3's export gate wins; when all of
    them fail, the first classification is re-raised.
    """
    size = len(data)
    d8_outer = int.from_bytes(data[8:12], "big") if size >= 12 else 0
    blocks = store.valid_blocks(data)
    stdcont = [b for b, nm in blocks if nm == "CATStdCont"]
    if not stdcont:
        raise ExportError(
            "missing-geometry-store",
            "no CATStdCont storage block in the file "
            "(G1 N1: 204/1,377 dev parts carry none)",
        )
    first_error: ExportError | None = None
    located = False
    for ordinal, blk in enumerate(stdcont):
        try:
            span = store.locate_store(data, blk, blocks, d8_outer)
        except ExportError as exc:
            if first_error is None:
                first_error = exc
            continue
        if span is None:
            continue
        located = True
        try:
            summary, vertices, triangles = _export_store(data, span, ordinal)
        except ExportError as exc:
            if first_error is None:
                first_error = exc
            continue
        return summary, vertices, triangles
    if not located and first_error is None:
        raise ExportError(
            "missing-geometry-store",
            "no validated nested stream store in any CATStdCont region "
            "(G1 N10 miss taxonomy: none_in_region / embedded_doc / "
            "next_block_store families)",
        )
    raise first_error  # all located stores failed classification


def _export_store(data, span, ordinal: int) -> tuple[dict, list, list]:
    """Decode one store span through G3's export gate."""
    groups, kinds = pool.scan_pool_groups(data, span.body_lo, span.body_hi)
    if pool.has_composite_space(kinds):
        raise ExportError(
            "undecoded-variant",
            "composite index space: an 01 02 edge group and/or a "
            "trailer-opener wrapper is present, so facet references run "
            "beyond the pool (G3 claim F8, open question 1 — the "
            "composite numbering is not decoded; no guessing)",
        )
    flat = [v for g in groups for v in g.vertices]
    if not flat:
        raise ExportError(
            "undecoded-variant",
            "no 01 06 vertex pool decoded from the store body "
            "(G2 P8 family: strips without a pool, or an empty store)",
        )
    lex = facets.lex_rank_map(flat)
    scan = facets.scan_facets(data, span.body_lo, span.body_hi)
    beyond = max((max(rec.refs, default=-1) for rec in scan.records), default=-1)
    if beyond >= len(flat):
        raise ExportError(
            "undecoded-variant",
            f"facet references beyond the pool: max ref {beyond} >= pool "
            f"size {len(flat)} (G3 open question 2 — a further element "
            "source or a second pool form; no guessing)",
        )
    soup = facets.decode_soup(flat, lex, scan)

    warnings = []
    if soup.degenerate_skipped:
        warnings.append(
            {
                "class": WARN_DEGENERATE,
                "detail": f"{soup.degenerate_skipped} degenerate strip "
                "triangles skipped (G3 F7 export convention)",
            }
        )
    if not soup.triangles:
        if scan.candidates == 0:
            # G2 P7: pools can exist without connectivity — vertices only.
            warnings.append(
                {
                    "class": WARN_NO_FACETS,
                    "detail": "pool with no facet header candidates in the "
                    "store body (G2 P7: pools can exist without "
                    "connectivity); vertices exported without faces",
                }
            )
        else:
            raise ExportError(
                "undecoded-variant",
                "no exportable facet content: "
                f"{scan.candidates} header candidates, "
                f"{scan.unresolved_candidates} unparseable (gap variant "
                "content), skipped record markers "
                f"{_marker_names(scan.skipped_markers)} — none of the "
                "pinned families (0x4a/0x42 strips, 0x4c polygons) "
                "produced a triangle (G3 open questions 3-5)",
            )

    stats = mesh.mesh_stats(list(soup.triangles))
    if soup.triangles and stats.boundary_edges:
        warnings.append(
            {
                "class": WARN_OPEN_SHELL,
                "detail": f"{stats.boundary_edges} boundary edges: the "
                "mesh is a manifold but not closed (G3 F6: sheet-like "
                "open shells are legitimate geometry, 10/76 clean-store "
                "soups)",
            }
        )
    if soup.triangles:
        unused = len(flat) - mesh.used_vertex_count(list(soup.triangles), len(flat))
        if unused:
            warnings.append(
                {
                    "class": WARN_UNUSED_VERTICES,
                    "detail": f"{unused} of {len(flat)} pool vertices are "
                    "not referenced by any exported triangle",
                }
            )
    if scan.skipped_markers or scan.unresolved_candidates:
        warnings.append(
            {
                "class": WARN_UNRESOLVED_FAMILY,
                "detail": "skipped facet records outside the pinned "
                f"families: {_marker_names(scan.skipped_markers) or 'none'}"
                f"; unparseable header candidates: "
                f"{scan.unresolved_candidates} (G3 open questions 3-5)",
            }
        )

    bbox_min, bbox_max = mesh.bounding_box(flat)
    summary = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "vertex_count": len(flat),
        "triangle_count": len(soup.triangles),
        "bounding_box": {"min": bbox_min, "max": bbox_max},
        "warnings": warnings,
        "store_ordinal": ordinal,
        "origin_kind": span.origin_kind,
        "pool_group_count": len(groups),
        "facet_candidate_count": scan.candidates,
        "facet_record_count": len(scan.records),
        "degenerate_triangle_count": soup.degenerate_skipped,
        "mesh": {
            "edge_count": stats.edge_count,
            "manifold": stats.manifold,
            "closed": stats.closed,
            "oriented": stats.oriented,
            "boundary_edge_count": stats.boundary_edges,
        },
    }
    _self_check(summary)
    return summary, flat, list(soup.triangles)


def _marker_names(skipped: dict[int, int]) -> str:
    return ", ".join(f"0x{mk:02x}={n}" for mk, n in sorted(skipped.items()))


def _self_check(summary: dict) -> None:
    """Validate the summary against the committed schema (the fitness
    runner's artifact self-check pattern)."""
    from catpart.schema import load_schema
    from catpart.schema.validate import SchemaError, ValidationError, validate

    try:
        validate(summary, load_schema("export-summary-v1"))
    except (SchemaError, ValidationError) as exc:
        raise ExportError(
            "io-error",
            f"internal error: emitted export summary violates its schema: {exc}",
        ) from exc
