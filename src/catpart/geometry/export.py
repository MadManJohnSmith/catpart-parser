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

Store search is the stage-3a locator recovery extension (#34, the L5
lever): after the shipped ``CATStdCont`` law finds nothing,
``CATXDocLinkCont`` then ``CATSeeBodyCont`` regions are probed with the
same law, and the two G1-documented catalog-tail variants (dword8-
overshoot, padded) recover under a relaxed tail law — all fail-closed,
with the recovery named on the span, the success summary
(``store_recovery``) or the failure detail.
"""

from __future__ import annotations

import mmap

from catpart.geometry.errors import ExportError
from catpart.geometry import facets, mesh, pool, ply, store
from catpart.geometry import composite

EXPORT_SCHEMA_VERSION = 1

WARN_UNRESOLVED_FAMILY = "unresolved-facet-family"
WARN_DEGENERATE = "degenerate-triangles-skipped"
WARN_OPEN_SHELL = "open-shell"
WARN_UNUSED_VERTICES = "unused-pool-vertices"
WARN_NO_FACETS = "no-facet-records"
WARN_CURVE_ENTRY = "curve-entry-loops-unexported"
WARN_CURVE_ENTRY_EXPORTED = "curve-entry-loops-exported-dup-pin"


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
    """Decode ``data``'s first exportable nested store.

    Returns ``(summary, vertices, triangles)``. With several candidate
    blocks the first store passing G3's export gate wins; when all of
    them fail, the first classification is re-raised.

    Store search (stage 3a #34): the ``CATStdCont`` regions carry the
    shipped law; when no ``CATStdCont`` region located a store, the
    ``CATXDocLinkCont`` regions (G1's next_block_store family) and then
    the ``CATSeeBodyCont`` regions are probed with the same law — the
    stage-3a locator recovery extension. Probing is fail-closed: a
    region probed and not matching stays as-is (``missing-geometry-
    store``), a region that matches names its probe on the span, and a
    part whose ``CATStdCont`` store located (passing or failing decode)
    never reaches the probes.
    """
    size = len(data)
    d8_outer = int.from_bytes(data[8:12], "big") if size >= 12 else 0
    blocks = store.valid_blocks(data)
    stdcont = [b for b, nm in blocks if nm == "CATStdCont"]
    xdoclink = [b for b, nm in blocks if nm == "CATXDocLinkCont"]
    seebody = [b for b, nm in blocks if nm == "CATSeeBodyCont"]
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
                first_error = _recovered_error(exc, span)
            continue
        return summary, vertices, triangles
    if not located and first_error is None:
        # Stage 3a recovery extension (#34): probe the non-CATStdCont
        # containers, xdoclink first (G1's next_block_store family is
        # xdoc-carrying, R19), then seebody. Parts whose CATStdCont
        # store located — or whose CATStdCont header raised — never
        # reach these probes, so every pre-stage-3a classification
        # except missing-geometry-store is unchanged.
        for tag, cands in (
            (store.CONTAINER_XDOCLINK, xdoclink),
            (store.CONTAINER_SEEBODY, seebody),
        ):
            for ordinal, blk in enumerate(cands):
                try:
                    span = store.locate_store(
                        data, blk, blocks, d8_outer, container=tag
                    )
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
                        first_error = _recovered_error(exc, span)
                    continue
                return summary, vertices, triangles
        if not located and first_error is None:
            if not stdcont:
                raise ExportError(
                    "missing-geometry-store",
                    "no CATStdCont storage block in the file and no "
                    "validated nested stream store in any "
                    "CATXDocLinkCont/CATSeeBodyCont region (G1 N1: "
                    "204/1,377 dev parts carry no CATStdCont; stage-3a "
                    "probes exhausted)",
                )
            raise ExportError(
                "missing-geometry-store",
                "no validated nested stream store in any CATStdCont/"
                "CATXDocLinkCont/CATSeeBodyCont region (G1 N10 miss "
                "taxonomy: none_in_region / embedded_doc families; "
                "stage-3a probes exhausted)",
            )
    raise first_error  # all located stores failed classification


def _recovered_error(exc: ExportError, span: store.StoreSpan) -> ExportError:
    """Record the recovery provenance on a recovered store's failure.

    A store recovered by the stage-3a extension (a non-``CATStdCont``
    probe, or a relaxed tail law) that then fails the decode keeps its
    classification with the probe/law named in the detail; a store the
    shipped law located passes through unchanged.
    """
    if span.container == store.CONTAINER_STDCONT and span.tail_law == store.TAIL_LAW_SHIPPED:
        return exc
    return ExportError(
        exc.error_class,
        f"{exc.detail} [store recovered via the {span.container} probe, "
        f"{span.tail_law} tail law]",
    )


def _export_store(data, span, ordinal: int) -> tuple[dict, list, list]:
    """Decode one store span through G3's export gate."""
    groups, kinds = pool.scan_pool_groups(data, span.body_lo, span.body_hi)
    if pool.has_composite_space(kinds):
        # G6 stage 2c (#34): composite stores decode under the recovered
        # merge law (the pool + the list node's decoded points, M2b).
        # The decode is fail-closed: a store the law does not cover
        # keeps its undecoded-variant classification with the specific
        # gap named (small-form-only; big-form = U3, unabsorbed pools,
        # law-failing records).
        return _export_composite_store(data, span, ordinal, groups, kinds)
    flat = [v for g in groups for v in g.vertices]
    if not flat:
        raise ExportError(
            "undecoded-variant",
            "no 01 06 vertex pool decoded from the store body "
            "(G2 P8 family: strips without a pool, or an empty store)",
        )
    lex = facets.lex_rank_map(flat)
    # The store-width context is bounded to the clean store class (#35,
    # 2026-11-10): composite stores never reach this line — they took
    # the composite path above — so the class knowledge this decode
    # already performed is always "clean" here.
    scan = facets.scan_facets(
        data,
        span.body_lo,
        span.body_hi,
        clean_store=True,
    )
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
                "detail": "facet records of families whose primitive "
                "reading G3 has not pinned: "
                f"{_marker_names(scan.skipped_markers) or 'none'}"
                f"; unparseable header candidates: "
                f"{scan.unresolved_candidates} (G3 open questions 3-5; "
                "in-pool loops of these markers still decode under the "
                "structural strip reading, without the pinned winding "
                "check)",
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
    if span.container != store.CONTAINER_STDCONT or span.tail_law != store.TAIL_LAW_SHIPPED:
        # Stage 3a (#34): the store was recovered — name the probe and
        # the tail law on the summary (additive; absent on stores the
        # shipped law located).
        summary["store_recovery"] = {
            "container": span.container,
            "tail_law": span.tail_law,
        }
    _self_check(summary)
    return summary, flat, list(soup.triangles)


def _export_composite_store(data, span, ordinal: int, groups, kinds):
    """Decode one composite store span under the identity law.

    The G6 stage-3d integration (#34, 2026-11-11): the list node's
    point region decodes through the deterministic 2-bit table walk
    (both forms), facet/edge references resolve as 0-based element
    indices in region order (M2b identity — no sigma search; the
    stage-2c shift-profile solver is superseded), and vertices are the
    written points (the pool is re-listed verbatim on every store the
    law decodes).  Fail-closed: any law gap raises
    ``undecoded-variant`` with the specific reason from
    :func:`composite.decode_composite_store` (layout, walk-exact,
    non-finite coordinates, unabsorbed pool, references beyond the
    element space).  Loops referencing skip slots (curve entries, U4)
    are not exported — their coordinates are not pinned — and surface
    as the ``curve-entry-loops-unexported`` warning; the stage-10 E0-b
    dup-pin law is the one exception (composite.py's restricted
    subset): on an otherwise-empty primary triangulation whose every
    dropped loop is battery-supported under the dup pin, those loops
    export and surface as ``curve-entry-loops-exported-dup-pin``.
    """
    points, triangles, degenerate, info = composite.decode_composite_store(
        data, span, groups, kinds
    )
    stats = mesh.mesh_stats(list(triangles))
    warnings = []
    if degenerate:
        warnings.append(
            {
                "class": WARN_DEGENERATE,
                "detail": f"{degenerate} degenerate strip triangles "
                "skipped (G3 F7 export convention, composite decode)",
            }
        )
    if info.get("loops_curve_entry"):
        warnings.append(
            {
                "class": WARN_CURVE_ENTRY,
                "detail": f"{info['loops_curve_entry']} facet loops "
                "reference skip slots (curve entries): their coordinates "
                "live in the curve records (U4, open) so those loops are "
                "not exported — no guessing; the store's other loops "
                "export under the identity mapping",
            }
        )
    if info.get("curve_entry_law"):
        warnings.append(
            {
                "class": WARN_CURVE_ENTRY_EXPORTED,
                "detail": f"{info['loops_curve_entry_exported']} facet "
                "loops referencing skip slots (curve entries) exported "
                "under the stage-10 E0-b dup-pin law (#34, 2026-11-12): "
                "the store's primary triangulation is empty (E0) and "
                "every dropped loop is normal-carrying and coplanar "
                "against its record's stored normal with the dup-pinned "
                "coordinates (each skip slot welded to the written "
                "vertex of its immediately preceding written element, "
                "no new vertices — the landed analysis's restricted "
                "battery-supported subset)",
            }
        )
    skipped_markers = info.get("skipped_markers") or {}
    if skipped_markers:
        warnings.append(
            {
                "class": WARN_UNRESOLVED_FAMILY,
                "detail": "facet records of families whose primitive "
                "reading G3 has not pinned: "
                f"{_marker_names(skipped_markers)} (G3 open questions "
                "3-5, composite body)",
            }
        )
    if not triangles:
        warnings.append(
            {
                "class": WARN_NO_FACETS,
                "detail": "composite element space decoded without "
                "exportable facet records; vertices exported without "
                "faces (the node point region decodes under the "
                "recovered law, the facet loops do not map)",
            }
        )
    if triangles and stats.boundary_edges:
        warnings.append(
            {
                "class": WARN_OPEN_SHELL,
                "detail": f"{stats.boundary_edges} boundary edges: the "
                "mesh is a manifold but not closed (G3 F6: sheet-like "
                "open shells are legitimate geometry)",
            }
        )
    if triangles:
        unused = len(points) - mesh.used_vertex_count(list(triangles), len(points))
        if unused:
            warnings.append(
                {
                    "class": WARN_UNUSED_VERTICES,
                    "detail": f"{unused} of {len(points)} element-space "
                    "vertices are not referenced by any exported triangle",
                }
            )

    bbox_min, bbox_max = mesh.bounding_box(points)
    summary = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "vertex_count": len(points),
        "triangle_count": len(triangles),
        "bounding_box": {"min": bbox_min, "max": bbox_max},
        "warnings": warnings,
        "store_ordinal": ordinal,
        "origin_kind": span.origin_kind,
        "pool_group_count": len(groups),
        "facet_candidate_count": info["facet_candidates"],
        "facet_record_count": info["facet_records"],
        "degenerate_triangle_count": degenerate,
        "mesh": {
            "edge_count": stats.edge_count,
            "manifold": stats.manifold,
            "closed": stats.closed,
            "oriented": stats.oriented,
            "boundary_edge_count": stats.boundary_edges,
        },
        # additive, composite-only (consumers ignore unknown properties):
        "composite": info,
    }
    _self_check(summary)
    return summary, points, list(triangles)


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
