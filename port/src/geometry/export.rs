//! Export orchestration: nested store -> PLY + summary — the port of
//! the Python reference module ``catpart.geometry.export``
//! (``src/catpart/geometry/export.py``), per spec §2.1 of
//! ``docs/specs/phase5-viewer-spec.md`` (orchestration + recovery).
//!
//! The vertical build slice: navigate the nested V5_CFV2 store
//! (``store.rs``, G1), decode the vertex pool (``pool.rs``, G2), decode
//! the facet records under G3's pinned primitive semantics
//! (``facets.rs``), assemble the mesh invariants (``mesh.rs``) and
//! write a binary little-endian PLY (``ply.rs``). The docstring
//! citations below are the twin's.
//!
//! Export rule (ticket #32, "export what the evidence pins"): a store
//! exports fully when G3's soup gate holds — no composite index space
//! (``01 02`` edge group / trailer-opener wrapper, F8 open question 1)
//! and every facet reference inside the pool (open question 2). Stores
//! needing the open composite-space decode fail ``undecoded-variant``;
//! there is no guessing. A pool without any facet header candidates is
//! the G2 P7 family (pools can exist without connectivity) and exports
//! vertices only, with a warning. On success the PLY is written to
//! ``out_path`` and the schema-versioned summary
//! (:const:`EXPORT_SCHEMA_VERSION`, committed as
//! ``src/catpart/schema/export-summary-v1.json``) returned. Every
//! failure raises :struct:`ExportError` with a machine-readable class
//! (see ``errors.rs``).
//!
//! Store search is the stage-3a locator recovery extension (#34, the
//! L5 lever): after the shipped ``CATStdCont`` law finds nothing,
//! ``CATXDocLinkCont`` then ``CATSeeBodyCont`` regions are probed with
//! the same law, and the two G1-documented catalog-tail variants
//! (dword8-overshoot, padded) recover under a relaxed tail law — all
//! fail-closed, with the recovery named on the span, the success
//! summary (``store_recovery``) or the failure detail. Stage 12 (#34,
//! 2026-11-13) adds the final probe family: every remaining valid
//! block whatever its doc-type name (``other-container`` — the
//! census's 53 recoverable stores in CATBRepModeContainer and
//! siblings), same law, probed only when the named families found
//! nothing.
//!
//! # The composite route (V3, ticket #42 — the V2 fail-closed interim is lifted)
//!
//! The twin routes three shapes into the composite decode
//! (``_export_composite_store``): stores whose kinds carry the
//! composite markers (the F8 gate), and the stage-13 second-chance
//! element-space route from the no-pool and refs-beyond raise sites.
//! At V2 the port failed closed with the twin's class for every
//! composite-path refusal (ticket #41's hard stop; the harness
//! excluded composite-path exports as ``excluded-composite-path``).
//! V3 (ticket #42) ports the decode — the route is real, the summary
//! carries the twin's additive ``composite`` block on composite-path
//! exports, and the composite decode's own error vocabulary is the
//! twin's ``undecoded-variant`` at its exact raise sites
//! (``composite.rs``). The stage-13 second-chance route re-raises the
//! ORIGINAL clean-path error when the composite decode declines
//! (fail-closed, row-identical).
//!
//! Evidence: the twin's docstring cites no dedicated evidence note —
//! it composes the sibling modules' models (each cites its own note;
//! see ``store.rs``/``pool.rs``/``facets.rs``/``mesh.rs``/``ply.rs``/
//! ``errors.rs``/``composite.rs`` here) and names the recovery
//! extensions, which trace to
//! ``docs/evidence/2026-11-10-l2-grind-classification.md`` (sections
//! 5-6, stage 3a #34) and the stage-12 ``other-container`` family.
//! The summary schema is the committed
//! ``src/catpart/schema/export-summary-v1.json``. Those are the
//! citations this port carries.
//!
//! The twin's ``_self_check`` (the summary validated against the
//! committed schema at emit time) has no port counterpart: the port's
//! summary is a typed struct whose shape IS the schema-v1 contract
//! (field set, order, types — no JSON-schema validator dependency,
//! spec §2.1's minimal-deps rule). A shape divergence would surface
//! as a Fidelity parsed-document mismatch (§3.2).
//!
//! Numeric contract (spec §2.2): decode module — coordinates are f32
//! widened to f64 once at load (in ``pool.rs``), all arithmetic f64 in
//! verbatim expression shape; the ``clippy::suboptimal_flops`` allow
//! below is the pinned carve-out (mul_add changes rounding and flips
//! exact-equality decisions); see the crate docs in ``../lib.rs`` for
//! the full policy.
#![allow(clippy::suboptimal_flops)]

use serde::Serialize;

use super::composite::{CompositeDecode, CompositeInfo};
use super::errors::{
    ExportError, IO_ERROR, MISSING_GEOMETRY_STORE, UNDECODED_VARIANT, UNREADABLE_FILE,
};
use super::{composite, facets, mesh, ply, pool, store};

/// The summary's schema version (twin: ``EXPORT_SCHEMA_VERSION``).
pub const EXPORT_SCHEMA_VERSION: u32 = 1;

/// The warning-class vocabulary (twin constants, verbatim).
pub const WARN_UNRESOLVED_FAMILY: &str = "unresolved-facet-family";
pub const WARN_DEGENERATE: &str = "degenerate-triangles-skipped";
pub const WARN_OPEN_SHELL: &str = "open-shell";
pub const WARN_UNUSED_VERTICES: &str = "unused-pool-vertices";
pub const WARN_NO_FACETS: &str = "no-facet-records";
/// The composite-path warning classes (stage-10/12/15 #34; V3, #42).
pub const WARN_CURVE_ENTRY: &str = "curve-entry-loops-unexported";
pub const WARN_CURVE_ENTRY_EXPORTED: &str = "curve-entry-loops-exported-dup-pin";
pub const WARN_DEDUP: &str = "duplicate-triangles-deduped";
pub const WARN_DEDUP_DECLINED: &str = "duplicate-triangles-dedup-declined";

/// One ordered warning of the summary (the twin's ``{"class": ...,
/// "detail": ...}`` dict; field order = the twin's construction).
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Warning {
    /// The kebab-case warning class.
    pub class: String,
    /// The human detail citing the claim behind the warning.
    pub detail: String,
}

/// The pool coordinate extents (the twin's
/// ``{"min": bbox_min, "max": bbox_max}``).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct BoundingBox {
    /// ``[min(x), min(y), min(z)]``.
    pub min: [f64; 3],
    /// ``[max(x), max(y), max(z)]``.
    pub max: [f64; 3],
}

/// The mesh invariants block (the twin's ``mesh`` dict; field order =
/// the twin's construction order).
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct MeshBlock {
    /// Distinct undirected edges.
    pub edge_count: usize,
    /// Every edge used at most twice.
    pub manifold: bool,
    /// Every edge used exactly twice.
    pub closed: bool,
    /// Each edge used once per direction.
    pub oriented: bool,
    /// Edges used exactly once.
    pub boundary_edge_count: usize,
}

/// The stage-3a/12 recovery provenance record (the twin's
/// ``_store_recovery_record``; ``container_name`` rides only on the
/// stage-12 ``other-container`` family).
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct StoreRecovery {
    /// The probing container family.
    pub container: String,
    /// The validating catalog-tail law.
    pub tail_law: String,
    /// The block's doc-type name (stage-12 family only).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub container_name: Option<String>,
}

/// The schema-versioned export summary (``export-summary-v1``) — the
/// twin's summary dict; field declaration order = the twin's dict
/// construction order (spec §2.1: even byte JSON equality stays
/// reachable, though Fidelity compares parsed documents, §3.2). The
/// twin's additive ``composite`` block never appears here: the clean
/// path does not emit it (V3 adds it with the composite decode).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct ExportSummary {
    /// The schema version (1).
    pub schema_version: u32,
    /// The flattened pool size (vertices in walk order).
    pub vertex_count: usize,
    /// The exported triangles.
    pub triangle_count: usize,
    /// The pool coordinate extents.
    pub bounding_box: BoundingBox,
    /// The ordered warnings (schema order-fixed).
    pub warnings: Vec<Warning>,
    /// The winning store's ordinal in its probe family.
    pub store_ordinal: usize,
    /// ``v5header`` or ``block`` (the store origin kind).
    pub origin_kind: String,
    /// The decoded ``01 06`` pool groups.
    pub pool_group_count: usize,
    /// The facet header candidates in the store body.
    pub facet_candidate_count: usize,
    /// The records accepted by the tiling law.
    pub facet_record_count: usize,
    /// The degenerate strip triangles skipped (F7).
    pub degenerate_triangle_count: usize,
    /// The mesh invariants block.
    pub mesh: MeshBlock,
    /// The twin's additive composite-only block (stage-2c/3d #34;
    /// present only on composite-path exports — V3, ticket #42;
    /// consumers ignore unknown properties, schema
    /// ``additionalProperties: true``).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub composite: Option<CompositeInfo>,
    /// The stage-3a/12 recovery provenance; absent on stores the
    /// shipped law located.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub store_recovery: Option<StoreRecovery>,
}

/// The decoded export of one store: the summary plus the PLY payload
/// (the flattened pool and the triangle soup).
#[derive(Debug, Clone, PartialEq)]
pub struct ExportOutcome {
    /// The schema-versioned summary.
    pub summary: ExportSummary,
    /// The pool in walk order (the PLY vertices).
    pub vertices: Vec<(f64, f64, f64)>,
    /// The triangle soup (the PLY faces).
    pub triangles: Vec<(u32, u32, u32)>,
}

/// Export ``path``'s nested-store geometry to the PLY ``out_path`` —
/// the twin's :func:`catpart.geometry.export.build_export`.
///
/// Returns the summary (schema ``export-summary-v1``). Raises
/// :struct:`ExportError` on every classified failure; the PLY is
/// written only after the whole store decodes, so failures leave no
/// partial output.
///
/// The twin mmaps the file read-only; the port reads the bytes (the
/// decode is a pure function of the file's content). The twin's
/// ``mmap`` refuses an EMPTY file with an unclassified ``ValueError``
/// (a traceback exit, no error-class JSON); the port mirrors the
/// crash — a panic exits outside the 0/1 seam contract and is recorded
/// as a harness-level failure, never a match (§3.2). No corpus part
/// reaches it (the accepted run carries no crash rows).
pub fn build_export(path: &str, out_path: &str) -> Result<ExportSummary, ExportError> {
    let data = std::fs::read(path)
        .map_err(|err| ExportError::new(UNREADABLE_FILE, format!("{path}: {err}")))?;
    if data.is_empty() {
        // The twin's mmap empty-file ValueError — unclassified there,
        // a crash here (never a Fidelity match, §3.2).
        panic!("catpart-export: the twin's mmap refuses an empty file (unclassified ValueError)");
    }
    let outcome = export_data(&data)?;
    let mut fh = std::fs::File::create(out_path)
        .map_err(|err| ExportError::new(IO_ERROR, format!("cannot write {out_path}: {err}")))?;
    ply::write_binary_little_endian_ply(&mut fh, &outcome.vertices, &outcome.triangles)
        .map_err(|err| ExportError::new(IO_ERROR, format!("cannot write {out_path}: {err}")))?;
    Ok(outcome.summary)
}

/// Decode ``data``'s first exportable nested store — the twin's
/// :func:`catpart.geometry.export._export_data`.
///
/// Returns the (summary, vertices, triangles) triple. With several
/// candidate blocks the first store passing G3's export gate wins;
/// when all of them fail, the first classification is re-raised.
///
/// Store search (stage 3a #34): the ``CATStdCont`` regions carry the
/// shipped law; when no ``CATStdCont`` region located a store, the
/// ``CATXDocLinkCont`` regions (G1's next_block_store family) and then
/// the ``CATSeeBodyCont`` regions are probed with the same law — the
/// stage-3a locator recovery extension. Probing is fail-closed: a
/// region probed and not matching stays as-is (``missing-geometry-
/// store``), a region that matches names its probe on the span, and a
/// part whose ``CATStdCont`` store located (passing or failing decode)
/// never reaches the probes.
pub fn export_data(data: &[u8]) -> Result<ExportOutcome, ExportError> {
    let size = data.len();
    let d8_outer = if size >= 12 {
        u32::from_be_bytes([data[8], data[9], data[10], data[11]]) as usize
    } else {
        0
    };
    let blocks = store::valid_blocks(data);
    let stdcont: Vec<usize> = blocks
        .iter()
        .filter(|(_, nm)| nm == "CATStdCont")
        .map(|(b, _)| *b)
        .collect();
    let xdoclink: Vec<usize> = blocks
        .iter()
        .filter(|(_, nm)| nm == "CATXDocLinkCont")
        .map(|(b, _)| *b)
        .collect();
    let seebody: Vec<usize> = blocks
        .iter()
        .filter(|(_, nm)| nm == "CATSeeBodyCont")
        .map(|(b, _)| *b)
        .collect();
    let mut first_error: Option<ExportError> = None;
    let mut located = false;
    if let Some(outcome) = walk_candidates(
        data,
        &blocks,
        &stdcont,
        store::CONTAINER_STDCONT,
        d8_outer,
        &mut first_error,
        &mut located,
    ) {
        return Ok(outcome);
    }
    if !located && first_error.is_none() {
        // Stage 3a recovery extension (#34): probe the non-CATStdCont
        // containers, xdoclink first (G1's next_block_store family is
        // xdoc-carrying, R19), then seebody. Parts whose CATStdCont
        // store located — or whose CATStdCont header raised — never
        // reach these probes, so every pre-stage-3a classification
        // except missing-geometry-store is unchanged.
        for (tag, cands) in [
            (store::CONTAINER_XDOCLINK, &xdoclink),
            (store::CONTAINER_SEEBODY, &seebody),
        ] {
            if let Some(outcome) = walk_candidates(
                data,
                &blocks,
                cands,
                tag,
                d8_outer,
                &mut first_error,
                &mut located,
            ) {
                return Ok(outcome);
            }
        }
        if !located && first_error.is_none() {
            // Stage 12 recovery extension (#34, 2026-11-13): the final
            // probe family — every remaining valid block whatever its
            // doc-type name (the corpus mass: CATBRepModeContainer,
            // CameraStartupContainer, contmeasure, ... — the stage-12
            // census measured 53 recoverable stores there, 12 of them
            // exporting through the committed laws). Same locate law,
            // same fail-closed rules, probed only when the three named
            // families found nothing; the block's own name travels on
            // the summary (``store_recovery.container_name``).
            let others: Vec<usize> = blocks
                .iter()
                .filter(|(_, nm)| !store::NAMED_PROBE_CONTAINERS.contains(&nm.as_str()))
                .map(|(b, _)| *b)
                .collect();
            if let Some(outcome) = walk_candidates(
                data,
                &blocks,
                &others,
                store::CONTAINER_OTHER,
                d8_outer,
                &mut first_error,
                &mut located,
            ) {
                return Ok(outcome);
            }
            if !located && first_error.is_none() {
                if stdcont.is_empty() {
                    return Err(ExportError::new(
                        MISSING_GEOMETRY_STORE,
                        "no CATStdCont storage block in the file and no \
                         validated nested stream store in any \
                         CATXDocLinkCont/CATSeeBodyCont region (G1 N1: \
                         204/1,377 dev parts carry no CATStdCont; stage-3a \
                         probes exhausted)",
                    ));
                }
                return Err(ExportError::new(
                    MISSING_GEOMETRY_STORE,
                    "no validated nested stream store in any CATStdCont/\
                     CATXDocLinkCont/CATSeeBodyCont region (G1 N10 miss \
                     taxonomy: none_in_region / embedded_doc families; \
                     stage-3a probes exhausted)",
                ));
            }
        }
    }
    Err(first_error.expect("the twin's `raise first_error`: a store located and failed decode"))
}

/// One probe family's candidate walk (the twin's per-family
/// ``for ordinal, blk in enumerate(cands)`` loop). ``first_error``
/// keeps the FIRST classification across the whole search; a decoded
/// store ends the search with the outcome.
fn walk_candidates(
    data: &[u8],
    blocks: &[(usize, String)],
    cands: &[usize],
    container: &'static str,
    d8_outer: usize,
    first_error: &mut Option<ExportError>,
    located: &mut bool,
) -> Option<ExportOutcome> {
    for (ordinal, blk) in cands.iter().enumerate() {
        let span = match store::locate_store(data, *blk, blocks, d8_outer, container) {
            Ok(None) => continue,
            Ok(Some(span)) => span,
            Err(exc) => {
                if first_error.is_none() {
                    *first_error = Some(exc);
                }
                continue;
            }
        };
        *located = true;
        match export_store(data, &span, ordinal) {
            Ok(outcome) => return Some(outcome),
            Err(exc) => {
                if first_error.is_none() {
                    *first_error = Some(recovered_error(exc, &span, data));
                }
            }
        }
    }
    None
}

/// Record the recovery provenance on a recovered store's failure — the
/// twin's :func:`catpart.geometry.export._recovered_error`.
///
/// A store recovered by the stage-3a/stage-12 extensions (a
/// non-``CATStdCont`` probe, or a relaxed tail law) that then fails
/// the decode keeps its classification with the probe/law named in
/// the detail; a store the shipped law located passes through
/// unchanged. The stage-12 ``other-container`` family also names the
/// block's doc-type name.
fn recovered_error(exc: ExportError, span: &store::StoreSpan, data: &[u8]) -> ExportError {
    if span.container == store::CONTAINER_STDCONT && span.tail_law == store::TAIL_LAW_SHIPPED {
        return exc;
    }
    let mut where_probe = format!("{} probe", span.container);
    if span.container == store::CONTAINER_OTHER {
        let name = store::block_name(data, span.block_start).0;
        where_probe = format!("{} ({name}) probe", span.container);
    }
    ExportError::new(
        exc.error_class,
        format!(
            "{} [store recovered via the {where_probe}, {} tail law]",
            exc.detail, span.tail_law
        ),
    )
}

/// The ``store_recovery`` summary record for a recovered store (stage
/// 3a/stage-12 provenance, emitted on BOTH decode paths) — the twin's
/// :func:`catpart.geometry.export._store_recovery_record`. ``None`` on
/// stores the shipped law located.
fn store_recovery_record(data: &[u8], span: &store::StoreSpan) -> Option<StoreRecovery> {
    if span.container == store::CONTAINER_STDCONT && span.tail_law == store::TAIL_LAW_SHIPPED {
        return None;
    }
    let container_name = if span.container == store::CONTAINER_OTHER {
        Some(store::block_name(data, span.block_start).0)
    } else {
        None
    };
    Some(StoreRecovery {
        container: span.container.to_string(),
        tail_law: span.tail_law.to_string(),
        container_name,
    })
}

/// Decode one store span through G3's export gate — the twin's
/// :func:`catpart.geometry.export._export_store` (the clean path; the
/// composite route is the V2 fail-closed arm documented in the module
/// header).
fn export_store(
    data: &[u8],
    span: &store::StoreSpan,
    ordinal: usize,
) -> Result<ExportOutcome, ExportError> {
    let (groups, kinds) = pool::scan_pool_groups(data, span.body_lo, span.body_hi)?;
    if pool::has_composite_space(&kinds) {
        // G6 stage 2c (#34): composite stores decode under the recovered
        // identity law — V3 (ticket #42) ports the decode (the
        // module-header note above documented the V2 fail-closed
        // interim; the route is real from V3 stage 1).
        return export_composite_store(data, span, ordinal, &groups, &kinds, false);
    }
    let flat: Vec<(f64, f64, f64)> = groups
        .iter()
        .flat_map(|group| group.vertices.iter().copied())
        .collect();
    if flat.is_empty() {
        // The twin routes the no-pool raise through the stage-13
        // second-chance element-space route (#34): the composite decode
        // either exports (a composite-path export) or declines and
        // THIS original error re-raises unchanged (fail-closed,
        // row-identical).
        return unrouted_element_space(
            data,
            span,
            ordinal,
            &groups,
            &kinds,
            ExportError::new(
                UNDECODED_VARIANT,
                "no 01 06 vertex pool decoded from the store body (G2 P8 \
                 family: strips without a pool, or an empty store)",
            ),
        );
    }
    let lex = facets::lex_rank_map(&flat);
    // The store-width context is bounded to the clean store class (#35,
    // 2026-11-10): composite stores never reach this line — they took
    // the composite path above — so the class knowledge this decode
    // already performed is always "clean" here.
    let scan = facets::scan_facets(data, span.body_lo, span.body_hi, true);
    let beyond = scan
        .records
        .iter()
        .map(|rec| rec.refs.iter().max().map(|&r| r as i64).unwrap_or(-1))
        .max()
        .unwrap_or(-1);
    if beyond >= flat.len() as i64 {
        // The twin routes the refs-beyond raise through the same
        // stage-13 second-chance route (see the no-pool arm above).
        return unrouted_element_space(
            data,
            span,
            ordinal,
            &groups,
            &kinds,
            ExportError::new(
                UNDECODED_VARIANT,
                format!(
                    "facet references beyond the pool: max ref {beyond} >= pool \
                     size {} (G3 open question 2 — a further element source or \
                     a second pool form; no guessing)",
                    flat.len()
                ),
            ),
        );
    }
    let soup = facets::decode_soup(&flat, &lex, &scan);

    let mut warnings: Vec<Warning> = Vec::new();
    if soup.degenerate_skipped > 0 {
        warnings.push(Warning {
            class: WARN_DEGENERATE.to_string(),
            detail: format!(
                "{} degenerate strip triangles skipped (G3 F7 export convention)",
                soup.degenerate_skipped
            ),
        });
    }
    if soup.triangles.is_empty() {
        if scan.candidates == 0 {
            // G2 P7: pools can exist without connectivity — vertices only.
            warnings.push(Warning {
                class: WARN_NO_FACETS.to_string(),
                detail: "pool with no facet header candidates in the \
                         store body (G2 P7: pools can exist without \
                         connectivity); vertices exported without faces"
                    .to_string(),
            });
        } else {
            return Err(ExportError::new(
                UNDECODED_VARIANT,
                format!(
                    "no exportable facet content: {} header candidates, \
                     {} unparseable (gap variant content), skipped record \
                     markers {} — none of the pinned families (0x4a/0x42 \
                     strips, 0x4c polygons) produced a triangle (G3 open \
                     questions 3-5)",
                    scan.candidates,
                    scan.unresolved_candidates,
                    marker_names(&scan.skipped_markers)
                ),
            ));
        }
    }

    let stats = mesh::mesh_stats(&soup.triangles);
    if !soup.triangles.is_empty() && stats.boundary_edges > 0 {
        warnings.push(Warning {
            class: WARN_OPEN_SHELL.to_string(),
            detail: format!(
                "{} boundary edges: the mesh is a manifold but not closed \
                 (G3 F6: sheet-like open shells are legitimate geometry, \
                 10/76 clean-store soups)",
                stats.boundary_edges
            ),
        });
    }
    if !soup.triangles.is_empty() {
        let unused = flat.len() - mesh::used_vertex_count(&soup.triangles, flat.len());
        if unused > 0 {
            warnings.push(Warning {
                class: WARN_UNUSED_VERTICES.to_string(),
                detail: format!(
                    "{unused} of {} pool vertices are not referenced by any \
                     exported triangle",
                    flat.len()
                ),
            });
        }
    }
    if !scan.skipped_markers.is_empty() || scan.unresolved_candidates > 0 {
        warnings.push(Warning {
            class: WARN_UNRESOLVED_FAMILY.to_string(),
            detail: format!(
                "facet records of families whose primitive reading G3 has \
                 not pinned: {}; unparseable header candidates: {} (G3 \
                 open questions 3-5; in-pool loops of these markers still \
                 decode under the structural strip reading, without the \
                 pinned winding check)",
                if scan.skipped_markers.is_empty() {
                    "none".to_string()
                } else {
                    marker_names(&scan.skipped_markers)
                },
                scan.unresolved_candidates
            ),
        });
    }

    let (bbox_min, bbox_max) = mesh::bounding_box(&flat).expect(
        "the twin's zip(*pool) ValueError arm: unreachable on the clean \
         path (the no-pool store raises undecoded-variant above)",
    );
    let mut summary = ExportSummary {
        schema_version: EXPORT_SCHEMA_VERSION,
        vertex_count: flat.len(),
        triangle_count: soup.triangles.len(),
        bounding_box: BoundingBox {
            min: bbox_min,
            max: bbox_max,
        },
        warnings,
        store_ordinal: ordinal,
        origin_kind: span.origin_kind.to_string(),
        pool_group_count: groups.len(),
        facet_candidate_count: scan.candidates,
        facet_record_count: scan.records.len(),
        degenerate_triangle_count: soup.degenerate_skipped,
        mesh: MeshBlock {
            edge_count: stats.edge_count,
            manifold: stats.manifold,
            closed: stats.closed,
            oriented: stats.oriented,
            boundary_edge_count: stats.boundary_edges,
        },
        composite: None,
        store_recovery: None,
    };
    if span.container != store::CONTAINER_STDCONT || span.tail_law != store::TAIL_LAW_SHIPPED {
        // Stage 3a (#34): the store was recovered — name the probe and
        // the tail law on the summary (additive; absent on stores the
        // shipped law located). Stage 12 (#34): the other-container
        // family also names the block's doc-type name; the same record
        // emits on the composite path (V3).
        summary.store_recovery = Some(
            store_recovery_record(data, span).expect("a recovered span always yields a record"),
        );
    }
    // The twin's _self_check: the typed struct IS the schema shape (no
    // validator dependency; see the module header).
    Ok(ExportOutcome {
        summary,
        vertices: flat,
        triangles: soup.triangles,
    })
}

/// The twin's :func:`catpart.geometry.export._marker_names`:
/// ``", ".join(f"0x{mk:02x}={n}" ...)`` over the sorted markers.
fn marker_names(skipped: &std::collections::BTreeMap<u8, u32>) -> String {
    skipped
        .iter()
        .map(|(mk, n)| format!("0x{mk:02x}={n}"))
        .collect::<Vec<_>>()
        .join(", ")
}

/// The twin's :func:`catpart.geometry.export._unrouted_element_space`
/// (the stage-13 second-chance element-space route, #34, 2026-11-13).
///
/// Fires ONLY where the clean path was about to raise the no-pool
/// error (G2 P8: no ``01 06`` vertex pool decoded) or the refs-beyond
/// error (G3 open question 2: facet references beyond the pool) — the
/// two failure classes the stage-13 census measured. A store whose
/// body carries a token-bearing list node is routed through the
/// UNCHANGED composite decode (``allow_unrouted_elements`` skips only
/// the marker-routing check; the stage-13 finding: the element space
/// beyond the pool IS the list node's point region, the composite
/// structure without its markers — docs/evidence/
/// 2026-11-13-stage13-elementspace.md sections 2-3). Every store the
/// route does not cover re-raises the ORIGINAL clean-path error
/// unchanged (fail-closed, row-identical); every previously-exporting
/// store returned before this function existed.
fn unrouted_element_space(
    data: &[u8],
    span: &store::StoreSpan,
    ordinal: usize,
    groups: &[pool::PoolGroup],
    kinds: &[Vec<u8>],
    original: ExportError,
) -> Result<ExportOutcome, ExportError> {
    match export_composite_store(data, span, ordinal, groups, kinds, true) {
        Ok(outcome) => Ok(outcome),
        Err(_) => Err(original),
    }
}

/// The twin's
/// :func:`catpart.geometry.export._export_composite_store`: decode one
/// composite store span under the identity law and build the
/// composite-path summary (V3, ticket #42).
///
/// The G6 stage-3d integration (#34, 2026-11-11): the list node's
/// point region decodes through the deterministic 2-bit table walk
/// (both forms), facet/edge references resolve as 0-based element
/// indices in region order (M2b identity — no sigma search; the
/// stage-2c shift-profile solver is superseded), and vertices are the
/// written points (the pool is re-listed verbatim on every store the
/// law decodes). Fail-closed: any law gap raises
/// ``undecoded-variant`` with the specific reason from
/// :fn:`composite::decode_composite_store` (layout, walk-exact,
/// non-finite coordinates, unabsorbed pool, references beyond the
/// element space). Loops referencing skip slots (curve entries, U4)
/// are not exported — their coordinates are not pinned — and surface
/// as the ``curve-entry-loops-unexported`` warning; the dup-pin law is
/// the one exception (composite.py; stage-10 2026-11-12, RELAXED
/// stage-15 2026-11-13 owner-authorized — the E0-b battery criterion
/// removed): on an otherwise-empty primary triangulation whose every
/// referenced skip slot has a preceding written element to weld to,
/// those loops export and surface as
/// ``curve-entry-loops-exported-dup-pin`` (stage 3). A not-manifold
/// assembled mesh whose duplicate unordered index triples resolve it
/// drops the later copies (``duplicate-triangles-deduped``; the
/// stage-15 law, review F1 family) — a store whose duplicates do not
/// resolve the over-use keeps its emitted triangles and surfaces
/// ``duplicate-triangles-dedup-declined`` (stage 3).
fn export_composite_store(
    data: &[u8],
    span: &store::StoreSpan,
    ordinal: usize,
    groups: &[pool::PoolGroup],
    kinds: &[Vec<u8>],
    allow_unrouted_elements: bool,
) -> Result<ExportOutcome, ExportError> {
    let CompositeDecode {
        points,
        triangles,
        degenerate,
        info,
        // The §2.3 curve exposure rides on the decode for the V4 WASM
        // boundary; the export surface (summary + PLY) never emits it
        // (additive, NOT part of the Fidelity definition — §3.2).
        curves: _curves,
    } = composite::decode_composite_store(data, span, groups, kinds, allow_unrouted_elements)?;
    let stats = mesh::mesh_stats(&triangles);
    let mut warnings: Vec<Warning> = Vec::new();
    if degenerate > 0 {
        warnings.push(Warning {
            class: WARN_DEGENERATE.to_string(),
            detail: format!(
                "{degenerate} degenerate strip triangles \
                 skipped (G3 F7 export convention, composite decode)"
            ),
        });
    }
    if info.loops_curve_entry > 0 {
        warnings.push(Warning {
            class: WARN_CURVE_ENTRY.to_string(),
            detail: format!(
                "{} facet loops \
                 reference skip slots (curve entries): their coordinates \
                 live in the curve records (U4, open) so those loops are \
                 not exported — no guessing; the store's other loops \
                 export under the identity mapping",
                info.loops_curve_entry
            ),
        });
    }
    if info.curve_entry_law.is_some() {
        warnings.push(Warning {
            class: WARN_CURVE_ENTRY_EXPORTED.to_string(),
            detail: format!(
                "{} facet \
                 loops referencing skip slots (curve entries) exported \
                 under the dup-pin law (#34; stage-10 2026-11-12, \
                 RELAXED stage-15 2026-11-13 owner-authorized — the \
                 E0-b battery criterion removed): the store's primary \
                 triangulation is empty (E0) and every referenced skip \
                 slot is welded to the written vertex of its \
                 immediately preceding written element (no new \
                 vertices — the U4-D dup law); normal-less and \
                 nonplanar dropped loops export under the same weld",
                info.loops_curve_entry_exported.unwrap_or(0)
            ),
        });
    }
    if let Some(dropped) = info.unordered_dedup_dropped {
        warnings.push(Warning {
            class: WARN_DEDUP.to_string(),
            detail: format!(
                "{dropped} duplicate \
                 triangles dropped under the unordered-triangle dedup \
                 law (#34, stage-15 2026-11-13, review F1 family): the \
                 same three element indices re-written from a second \
                 record/loop (opposite winding — the writer re-listed \
                 the facet; territory overlap 0); the emitted mesh was \
                 not-manifold and the deduplicated mesh is manifold, \
                 so the later copies dropped (first occurrence's \
                 winding kept; degenerate skips untouched)"
            ),
        });
    }
    if let Some(declined) = info.unordered_dedup_declined {
        warnings.push(Warning {
            class: WARN_DEDUP_DECLINED.to_string(),
            detail: format!(
                "{declined} duplicate \
                 triangles found (the review F1 mechanism) but their \
                 removal leaves the mesh not-manifold — the dedup \
                 declined fail-closed and the emitted triangles are \
                 kept verbatim (the over-use joins distinct triangles; \
                 the L2 gate records not-manifold)"
            ),
        });
    }
    if !info.skipped_markers.is_empty() {
        warnings.push(Warning {
            class: WARN_UNRESOLVED_FAMILY.to_string(),
            detail: format!(
                "facet records of families whose primitive \
                 reading G3 has not pinned: {} (G3 open questions \
                 3-5, composite body)",
                marker_names(&info.skipped_markers)
            ),
        });
    }
    if triangles.is_empty() {
        warnings.push(Warning {
            class: WARN_NO_FACETS.to_string(),
            detail: "composite element space decoded without \
                     exportable facet records; vertices exported without \
                     faces (the node point region decodes under the \
                     recovered law, the facet loops do not map)"
                .to_string(),
        });
    }
    if !triangles.is_empty() && stats.boundary_edges > 0 {
        warnings.push(Warning {
            class: WARN_OPEN_SHELL.to_string(),
            detail: format!(
                "{} boundary edges: the \
                 mesh is a manifold but not closed (G3 F6: sheet-like \
                 open shells are legitimate geometry)",
                stats.boundary_edges
            ),
        });
    }
    if !triangles.is_empty() {
        let unused = points.len() - mesh::used_vertex_count(&triangles, points.len());
        if unused > 0 {
            warnings.push(Warning {
                class: WARN_UNUSED_VERTICES.to_string(),
                detail: format!(
                    "{unused} of {} element-space \
                     vertices are not referenced by any exported triangle",
                    points.len()
                ),
            });
        }
    }

    let (bbox_min, bbox_max) = mesh::bounding_box(&points).expect(
        "the twin's zip(*points) ValueError arm: unreachable on the \
         compared population (every composite export path carries points)",
    );
    let mut summary = ExportSummary {
        schema_version: EXPORT_SCHEMA_VERSION,
        vertex_count: points.len(),
        triangle_count: triangles.len(),
        bounding_box: BoundingBox {
            min: bbox_min,
            max: bbox_max,
        },
        warnings,
        store_ordinal: ordinal,
        origin_kind: span.origin_kind.to_string(),
        pool_group_count: groups.len(),
        facet_candidate_count: info.facet_candidates,
        facet_record_count: info.facet_records,
        degenerate_triangle_count: degenerate as usize,
        mesh: MeshBlock {
            edge_count: stats.edge_count,
            manifold: stats.manifold,
            closed: stats.closed,
            oriented: stats.oriented,
            boundary_edge_count: stats.boundary_edges,
        },
        composite: Some(info),
        store_recovery: None,
    };
    if span.container != store::CONTAINER_STDCONT || span.tail_law != store::TAIL_LAW_SHIPPED {
        // Stage 3a/12 (#34): recovered stores name HOW on every decode
        // path (the stage-12 corpus passes export through here).
        summary.store_recovery = Some(
            store_recovery_record(data, span).expect("a recovered span always yields a record"),
        );
    }
    // The twin's _self_check: the typed struct IS the schema shape (no
    // validator dependency; see the module header).
    Ok(ExportOutcome {
        summary,
        vertices: points,
        triangles,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The fixture generator's shapes, minimized: a canonical store
    /// (8-vertex pool, 4 strips + 2 polygons over the GEOMETRY_LEX
    /// ranks) inside a CATStdCont storage block.
    fn geometry_pool() -> Vec<(f32, f32, f32)> {
        vec![
            (0.0, 0.0, 0.0),
            (20.0, 0.0, 0.0),
            (0.0, 100.0, 0.0),
            (20.0, 100.0, 0.0),
            (0.0, 100.0, 60.0),
            (20.0, 100.0, 60.0),
            (0.0, 0.0, 60.0),
            (20.0, 0.0, 60.0),
        ]
    }

    fn facet_record(marker: u8, normal: Option<(f32, f32, f32)>, refs: &[u32]) -> Vec<u8> {
        let mut rec = vec![0x01, marker, 0x01, 0xFF];
        rec.extend_from_slice(&(refs.len() as u32).to_le_bytes());
        if let Some((x, y, z)) = normal {
            rec.extend_from_slice(&x.to_le_bytes());
            rec.extend_from_slice(&y.to_le_bytes());
            rec.extend_from_slice(&z.to_le_bytes());
        }
        rec.push(refs.len() as u8);
        for &r in refs {
            rec.push(r as u8);
        }
        rec
    }

    /// The box's faces over the GEOMETRY_LEX ranks (the generator's
    /// GEOMETRY_FACES), minus the x=20 face for the open-shell shape.
    fn faces() -> Vec<(u8, (f32, f32, f32), Vec<u32>)> {
        vec![
            (0x4A, (0.0, 0.0, -1.0), vec![4, 0, 6, 2]),
            (0x4A, (0.0, 1.0, 0.0), vec![6, 2, 7, 3]),
            (0x4A, (0.0, 0.0, 1.0), vec![7, 3, 5, 1]),
            (0x4A, (0.0, -1.0, 0.0), vec![5, 1, 4, 0]),
            (0x4C, (-1.0, 0.0, 0.0), vec![0, 1, 3, 2]),
            (0x4C, (1.0, 0.0, 0.0), vec![4, 6, 7, 5]),
        ]
    }

    fn store_body(pool: &[(f32, f32, f32)], faces: &[(u8, (f32, f32, f32), Vec<u32>)]) -> Vec<u8> {
        let mut body = Vec::new();
        body.extend_from_slice(pool::FULL_WRAP);
        body.extend_from_slice(pool::POOL_SUBKIND);
        body.push(pool.len() as u8);
        for &(x, y, z) in pool {
            body.extend_from_slice(pool::VREC);
            body.extend_from_slice(&x.to_le_bytes());
            body.extend_from_slice(&y.to_le_bytes());
            body.extend_from_slice(&z.to_le_bytes());
        }
        for (marker, normal, refs) in faces {
            body.extend_from_slice(&facet_record(*marker, Some(*normal), refs));
        }
        body
    }

    /// A whole file: the CATStdCont storage block + a nested store
    /// (32-byte header, body, 52-byte catalog).
    fn file_with(body: &[u8]) -> Vec<u8> {
        let catalog_len = 52usize;
        let mut file = Vec::new();
        file.extend_from_slice(store::BLOCK_TAG);
        file.extend_from_slice(store::STORAGE_WORD);
        file.extend_from_slice(b"\x80\x01\x00\x00\x00\x00\x22\x0c\x00\x00\x00");
        file.extend_from_slice(b"\x34\x01\x01\x00\x34\x10CATUnicodeString");
        file.extend_from_slice(b"\xa0\x02\x00\x00\x00\x00\x34\x0aCATStdCont\x9f");
        file.extend_from_slice(&[0x00; 8]); // preamble to the origin
        let origin = file.len();
        file.extend_from_slice(store::V5_CFV2);
        file.extend_from_slice(&((store::HEADER_LEN + body.len()) as u32).to_be_bytes());
        file.extend_from_slice(&(catalog_len as u32).to_be_bytes());
        file.extend_from_slice(&[0xff; 8]);
        file.extend_from_slice(&[0x00; 8]);
        file.extend_from_slice(body);
        file.extend_from_slice(store::CB0001);
        for dword in [1u32, 0, 0xE7, 0xE7, 0, 0, catalog_len as u32] {
            file.extend_from_slice(&dword.to_be_bytes());
        }
        file.extend_from_slice(store::CB_END);
        let _ = origin;
        file
    }

    #[test]
    fn exports_the_canonical_box_with_the_full_summary() {
        let body = store_body(&geometry_pool(), &faces());
        let file = file_with(&body);
        let outcome = export_data(&file).unwrap();
        let summary = &outcome.summary;
        assert_eq!(summary.schema_version, 1);
        assert_eq!(summary.vertex_count, 8);
        assert_eq!(summary.triangle_count, 12);
        assert!(summary.warnings.is_empty());
        assert_eq!(summary.store_ordinal, 0);
        assert_eq!(summary.origin_kind, store::ORIGIN_KIND_HEADER);
        assert_eq!(summary.pool_group_count, 1);
        assert_eq!(summary.facet_candidate_count, 6);
        assert_eq!(summary.facet_record_count, 6);
        assert_eq!(summary.degenerate_triangle_count, 0);
        assert!(summary.mesh.closed);
        assert!(summary.mesh.manifold);
        assert!(summary.mesh.oriented);
        assert_eq!(summary.mesh.edge_count, 18);
        assert!(summary.store_recovery.is_none());
        // The bounding box is the pool's extents (the widened f32s).
        assert_eq!(summary.bounding_box.min, [0.0, 0.0, 0.0]);
        assert_eq!(summary.bounding_box.max, [20.0, 100.0, 60.0]);
    }

    #[test]
    fn open_shell_and_degenerate_warnings_fire_in_schema_order() {
        // The fixture's geometry-open-shell shape: the x=20 face
        // dropped (a sheet-like open shell, F6) plus a well-formed 0x41
        // record whose single loop repeats one rank (the strip reading
        // skips it, F7; the marker surfaces as an unresolved family).
        let mut face_list = faces();
        face_list.remove(5);
        let mut body = store_body(&geometry_pool(), &face_list);
        body.extend_from_slice(&facet_record(0x41, None, &[0, 0, 0]));
        let file = file_with(&body);
        let outcome = export_data(&file).unwrap();
        let classes: Vec<&str> = outcome
            .summary
            .warnings
            .iter()
            .map(|w| w.class.as_str())
            .collect();
        // Schema order: degenerate (skips first), open-shell (the F6
        // sheet), unresolved (0x41 outside EXPORTED_MARKERS) — the
        // fixture's exact class set for this shape.
        assert_eq!(
            classes,
            vec![WARN_DEGENERATE, WARN_OPEN_SHELL, WARN_UNRESOLVED_FAMILY]
        );
        assert_eq!(outcome.summary.triangle_count, 10);
        assert!(outcome.summary.mesh.manifold);
        assert!(!outcome.summary.mesh.closed);
        assert!(outcome.summary.degenerate_triangle_count > 0);
    }

    #[test]
    fn out_of_range_ref_refuses_undecoded_variant() {
        let mut face_list = faces();
        face_list[0].2 = vec![4, 0, 6, 200]; // 200 >= pool size 8
        let file = file_with(&store_body(&geometry_pool(), &face_list));
        let err = export_data(&file).unwrap_err();
        assert_eq!(err.error_class, UNDECODED_VARIANT);
        assert!(err.detail.contains("facet references beyond the pool"));
        assert!(err.detail.contains("max ref 200 >= pool size 8"));
    }

    #[test]
    fn composite_store_without_a_list_node_refuses_undecoded_variant() {
        let mut body = store_body(&geometry_pool(), &faces());
        // An `01 02` edge-group wrapper (G3 F8's composite marker):
        // the composite route runs, finds no token-bearing list node
        // before the first facet header and refuses (the N1 law —
        // 939/939 composite stores carry one).
        body.extend_from_slice(pool::FULL_WRAP);
        body.extend_from_slice(pool::EDGE_SUBKIND);
        body.extend_from_slice(&[0x02, 0x02, 0x00, 0x01, 0x00, 0x02]);
        let file = file_with(&body);
        let err = export_data(&file).unwrap_err();
        assert_eq!(err.error_class, UNDECODED_VARIANT);
        assert!(err.detail.contains("without a token-bearing list node"));
        assert!(err.detail.contains("N1"));
    }

    #[test]
    fn unrouted_second_chance_rejects_and_re_raises_the_original_error() {
        // The stage-13 route's fail-closed arm: a store whose pool
        // wrapper is established-but-insane (the count window exceeds
        // the body — kinds recorded, no group) reaches the no-pool
        // raise site, the second-chance route finds no token-bearing
        // list node and the ORIGINAL clean-path error re-raises
        // (row-identical, the twin's ``raise original from None``).
        let mut body = Vec::new();
        body.extend_from_slice(pool::FULL_WRAP);
        body.extend_from_slice(pool::POOL_SUBKIND);
        body.push(0xFF);
        body.extend_from_slice(&1_000_001u32.to_le_bytes()); // > MAX_COUNT
        let file = file_with(&body);
        let err = export_data(&file).unwrap_err();
        assert_eq!(err.error_class, UNDECODED_VARIANT);
        assert!(
            err.detail
                .contains("no 01 06 vertex pool decoded from the store body")
        );
    }

    #[test]
    fn missing_facet_payload_refuses_undecoded_variant() {
        // Every facet record cut after its count byte: no parse
        // survives the tiling law (the fixture's
        // geometry-missing-facet-payload shape).
        let mut body = Vec::new();
        body.extend_from_slice(pool::FULL_WRAP);
        body.extend_from_slice(pool::POOL_SUBKIND);
        body.push(8);
        for &(x, y, z) in &geometry_pool() {
            body.extend_from_slice(pool::VREC);
            body.extend_from_slice(&x.to_le_bytes());
            body.extend_from_slice(&y.to_le_bytes());
            body.extend_from_slice(&z.to_le_bytes());
        }
        for (marker, normal, refs) in faces() {
            body.extend_from_slice(&[0x01, marker, 0x01, 0xFF]);
            body.extend_from_slice(&(refs.len() as u32).to_le_bytes());
            body.extend_from_slice(&normal.0.to_le_bytes());
            body.extend_from_slice(&normal.1.to_le_bytes());
            body.extend_from_slice(&normal.2.to_le_bytes());
            body.extend_from_slice(&[refs.len() as u8, 0, 0]);
        }
        let file = file_with(&body);
        let err = export_data(&file).unwrap_err();
        assert_eq!(err.error_class, UNDECODED_VARIANT);
        assert!(err.detail.contains("no exportable facet content"));
        assert!(err.detail.contains("gap variant content"));
    }

    #[test]
    fn pool_without_facets_exports_vertices_only_with_warning() {
        // The G2 P7 family: a pool with no facet candidates exports
        // vertices only, warning no-facet-records, empty mesh stats.
        let body = store_body(&geometry_pool(), &[]);
        let file = file_with(&body);
        let outcome = export_data(&file).unwrap();
        assert_eq!(outcome.summary.vertex_count, 8);
        assert_eq!(outcome.summary.triangle_count, 0);
        assert_eq!(outcome.summary.warnings.len(), 1);
        assert_eq!(outcome.summary.warnings[0].class, WARN_NO_FACETS);
        assert!(outcome.summary.mesh.closed); // vacuous (all over empty)
    }

    #[test]
    fn truncated_pool_refuses_malformed_pool_group() {
        let mut pool = geometry_pool();
        pool.truncate(6); // count field still says 8
        let mut body = Vec::new();
        body.extend_from_slice(pool::FULL_WRAP);
        body.extend_from_slice(pool::POOL_SUBKIND);
        body.push(8);
        for &(x, y, z) in &pool {
            body.extend_from_slice(pool::VREC);
            body.extend_from_slice(&x.to_le_bytes());
            body.extend_from_slice(&y.to_le_bytes());
            body.extend_from_slice(&z.to_le_bytes());
        }
        for (marker, normal, refs) in faces() {
            body.extend_from_slice(&facet_record(marker, Some(normal), &refs));
        }
        let file = file_with(&body);
        let err = export_data(&file).unwrap_err();
        assert_eq!(err.error_class, "malformed-pool-group");
        assert!(err.detail.contains("count field 8 but walked 6"));
    }

    #[test]
    fn nan_coordinate_refuses_malformed_pool_vertex() {
        let mut pool = geometry_pool();
        pool[3] = (f32::NAN, 100.0, 0.0);
        let file = file_with(&store_body(&pool, &faces()));
        let err = export_data(&file).unwrap_err();
        assert_eq!(err.error_class, "malformed-pool-vertex");
    }

    #[test]
    fn no_stdcont_block_means_missing_geometry_store() {
        // A file whose only storage block is a CATSeeBodyCont carrying
        // no store: the probes exhaust -> the no-CATStdCont detail.
        let mut file = Vec::new();
        file.extend_from_slice(store::BLOCK_TAG);
        file.extend_from_slice(store::STORAGE_WORD);
        file.extend_from_slice(b"\x80\x01\x00\x00\x00\x00\x22\x0c\x00\x00\x00");
        file.extend_from_slice(b"\x34\x01\x01\x00\x34\x10CATUnicodeString");
        file.extend_from_slice(b"\xa0\x02\x00\x00\x00\x00\x34\x0eCATSeeBodyCont\x9f");
        file.extend_from_slice(&[0x00; 96]);
        let err = export_data(&file).unwrap_err();
        assert_eq!(err.error_class, MISSING_GEOMETRY_STORE);
        assert!(
            err.detail
                .contains("no CATStdCont storage block in the file")
        );
    }

    #[test]
    fn storeless_stdcont_means_missing_geometry_store() {
        // A CATStdCont block whose region carries no store: the miss
        // taxonomy detail (G1 N10).
        let mut file = Vec::new();
        file.extend_from_slice(store::BLOCK_TAG);
        file.extend_from_slice(store::STORAGE_WORD);
        file.extend_from_slice(b"\x80\x01\x00\x00\x00\x00\x22\x0c\x00\x00\x00");
        file.extend_from_slice(b"\x34\x01\x01\x00\x34\x10CATUnicodeString");
        file.extend_from_slice(b"\xa0\x02\x00\x00\x00\x00\x34\x0aCATStdCont\x9f");
        file.extend_from_slice(&[0x00; 96]);
        let err = export_data(&file).unwrap_err();
        assert_eq!(err.error_class, MISSING_GEOMETRY_STORE);
        assert!(err.detail.contains("G1 N10 miss taxonomy"));
    }

    #[test]
    fn seebody_probe_recovers_and_names_the_store_recovery() {
        // The store inside a CATSeeBodyCont block with no CATStdCont
        // at all (the fixture's geometry-seebody-store shape): the
        // stage-3a probe recovers it and the summary carries
        // store_recovery = seebody/shipped.
        let body = store_body(&geometry_pool(), &faces());
        let mut store_bytes = Vec::new();
        store_bytes.extend_from_slice(store::V5_CFV2);
        store_bytes.extend_from_slice(&((store::HEADER_LEN + body.len()) as u32).to_be_bytes());
        store_bytes.extend_from_slice(&(52u32).to_be_bytes());
        store_bytes.extend_from_slice(&[0xff; 8]);
        store_bytes.extend_from_slice(&[0x00; 8]);
        store_bytes.extend_from_slice(&body);
        store_bytes.extend_from_slice(store::CB0001);
        for dword in [1u32, 0, 0xE7, 0xE7, 0, 0, 52u32] {
            store_bytes.extend_from_slice(&dword.to_be_bytes());
        }
        store_bytes.extend_from_slice(store::CB_END);

        let mut file = Vec::new();
        file.extend_from_slice(store::BLOCK_TAG);
        file.extend_from_slice(store::STORAGE_WORD);
        file.extend_from_slice(b"\x80\x01\x00\x00\x00\x00\x22\x0c\x00\x00\x00");
        file.extend_from_slice(b"\x34\x01\x01\x00\x34\x10CATUnicodeString");
        file.extend_from_slice(b"\xa0\x02\x00\x00\x00\x00\x34\x0eCATSeeBodyCont\x9f");
        file.extend_from_slice(&[0x00; 96]); // the preamble to the origin
        file.extend_from_slice(&store_bytes);
        let outcome = export_data(&file).unwrap();
        assert_eq!(outcome.summary.triangle_count, 12);
        let recovery = outcome.summary.store_recovery.as_ref().unwrap();
        assert_eq!(recovery.container, "seebody");
        assert_eq!(recovery.tail_law, "shipped");
        assert!(recovery.container_name.is_none());
    }

    #[test]
    fn othercontainer_probe_names_the_block_on_the_recovery() {
        // The stage-12 family: the store in a CATBRepModeContainer
        // block; the recovery record names the block's doc-type name.
        let body = store_body(&geometry_pool(), &faces());
        let mut store_bytes = Vec::new();
        store_bytes.extend_from_slice(store::V5_CFV2);
        store_bytes.extend_from_slice(&((store::HEADER_LEN + body.len()) as u32).to_be_bytes());
        store_bytes.extend_from_slice(&(52u32).to_be_bytes());
        store_bytes.extend_from_slice(&[0xff; 8]);
        store_bytes.extend_from_slice(&[0x00; 8]);
        store_bytes.extend_from_slice(&body);
        store_bytes.extend_from_slice(store::CB0001);
        for dword in [1u32, 0, 0xE7, 0xE7, 0, 0, 52u32] {
            store_bytes.extend_from_slice(&dword.to_be_bytes());
        }
        store_bytes.extend_from_slice(store::CB_END);

        let mut file = Vec::new();
        file.extend_from_slice(store::BLOCK_TAG);
        file.extend_from_slice(store::STORAGE_WORD);
        file.extend_from_slice(b"\x80\x01\x00\x00\x00\x00\x22\x0c\x00\x00\x00");
        file.extend_from_slice(b"\x34\x01\x01\x00\x34\x10CATUnicodeString");
        file.extend_from_slice(b"\xa0\x02\x00\x00\x00\x00\x34\x14CATBRepModeContainer\x9f");
        file.extend_from_slice(&[0x00; 96]);
        file.extend_from_slice(&store_bytes);
        let outcome = export_data(&file).unwrap();
        assert_eq!(outcome.summary.triangle_count, 12);
        let recovery = outcome.summary.store_recovery.as_ref().unwrap();
        assert_eq!(recovery.container, "other-container");
        assert_eq!(recovery.tail_law, "shipped");
        assert_eq!(
            recovery.container_name.as_deref(),
            Some("CATBRepModeContainer")
        );
    }

    #[test]
    fn marker_names_format_is_the_twin_string() {
        let mut skipped = std::collections::BTreeMap::new();
        skipped.insert(0x41u8, 2);
        skipped.insert(0x4Eu8, 1);
        assert_eq!(marker_names(&skipped), "0x41=2, 0x4e=1");
    }

    #[test]
    fn empty_file_panics_like_the_twin_mmap() {
        let result = std::panic::catch_unwind(|| build_export("/dev/null", "/dev/null"));
        assert!(result.is_err(), "the twin's empty-file ValueError arm");
    }
}
