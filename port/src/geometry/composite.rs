//! The composite index space decoded under the recovered identity law
//! (G6, #34) — the port of the Python reference module
//! ``catpart.geometry.composite``
//! (``src/catpart/geometry/composite.py``, 1,916 lines — "the whale",
//! 55% of the geometry package, spec §10.2), per spec §2.1 of
//! ``docs/specs/phase5-viewer-spec.md``.
//!
//! The Python twin's module docstring IS the law history — this port
//! cites it and the evidence notes, never restates. The landed model:
//! the P1t layout (the 2-bit per-element table of exactly
//! ``ceil(element_count / 4)`` bytes after the zero block), the U1
//! table semantics (2 bits per element, LSB-first: 0 = ``[x][y][z]``,
//! 1 = skip — the curve entries, U4, 2 = ``[z]``, 3 = ``[y][z]``, with
//! the origin as the initial LCP state and partial writes carrying the
//! previous element's coordinates), the M2b element identity
//! (facet/edge references are 0-based element indices in region order
//! — no sigma search), the stage-3b record-width rank (u8/u16be,
//! u24be above 65,535 elements, the no-repeated-refs rule, the loop
//! plane tiebreak), the stage-4b/5 per-rep decomposition with the
//! noise-aware absorption tolerance, the stage-6 raw-array law, the
//! stage-8/9 mixedwrite composition, the stage-10 E0-b dup-pin weld
//! (PER LOOP 2026-11-18: pinnability + 2e-3 coplanarity battery + an
//! incremental mesh-manifold guard, no empty-mesh precondition) and the
//! stage-15 unordered-triangle dedup. The
//! fail-closed ladder names every gap; there is no guessing.
//!
//! Port stage order (ticket #42's internal order, one commit + harness
//! re-run each):
//!
//! 1. **Stage 1 (this commit)**: the table walk + the per-rep
//!    decomposition — ``find_list_node``/``layout``/``table_slots``/
//!    ``decode_region``/``parse_strip_records``/``triangulate``/
//!    ``decode_composite_store`` (single-rep + ``decode_per_rep``).
//!    The walk-mismatch branch fails closed with the twin's class
//!    naming the stage-2 gap; every store the table walk handles
//!    decodes identically to the twin, and every counter of the
//!    composite summary block already carries the twin's semantics.
//! 2. **Stage 2**: the raw-array law + the mixedwrite composition
//!    (``decode_raw_array``/``decode_mixedwrite`` and the per-node
//!    table/raw/flat law set + the walk-mismatch family signature).
//! 3. **Stage 3**: the per-loop dup-pin weld (battery + mesh guard),
//!    the stage-15
//!    unordered-triangle dedup, and the curve exposure for the
//!    viewer's overlay — spec §2.3 pins the curve-entry point
//!    sequences ADDITIVE and OUTSIDE the Fidelity definition (the
//!    Python reference has no counterpart artifact); the boundary is
//!    pinned in code there.
//!
//! Named-ambiguity discipline (the dispatch's rule): the twin's
//! docstring carries dated law amendments; where two passages could
//! disagree, the LATEST dated law wins. Verified at port time: the
//! 2026-11-18 per-loop weld (battery + mesh guard) supersedes the
//! stage-10/15 empty-mesh and relaxed variants; the twin's code and
//! this port implement the same per-loop predicate and the same
//! incremental edge-use guard. The twin is untouchable — a twin bug
//! discovered mid-port is STOP-and-report, never a silent divergence
//! (spec §3.3).
//!
//! Evidence (the same citations the twin's docstring carries):
//!
//! - ``docs/evidence/2026-11-10-node-streams.md`` (the stage-3b/3d
//!   decode; the "Stage 4a-residue" raw-array section)
//! - ``docs/evidence/2026-11-10-composite-space.md`` (E1-E3/N1-N5 —
//!   the polyline-table reading the §2.3 curve exposure cites, NOT
//!   re-decoded here: see ``curve_sequences`` at stage 3)
//! - ``docs/evidence/2026-11-11-per-rep-and-width-laws.md`` (R1-R5
//!   the per-rep decomposition; R10/R11 the u24be width entry,
//!   13bb5c0c byte-verified)
//! - ``docs/evidence/2026-11-12-curve-entry-analysis.md`` (section 5,
//!   claims row ``U4-stage5-recommendation`` — the E0-b dup-pin law's
//!   restricted analysis basis, + the stage-9-baseline recompute
//!   addendum)
//! - ``docs/evidence/2026-11-12-mixedwrite-reps.md`` and
//!   ``docs/evidence/2026-11-12-stage9-integration.md`` (the
//!   mixedwrite composition and the amended declaration)
//! - ``docs/evidence/2026-11-12-stage10-curve-entry-impl.md`` (the
//!   dup-pin integration; the store-level E0 gate)
//! - ``docs/evidence/2026-11-13-stage13-elementspace.md`` (the
//!   second-chance element-space route)
//! - ``docs/evidence/2026-11-13-stage14-export-failures.md``
//!   (section 2 — the stage-15 relaxation measurement, owner decision
//!   handoff cont. 23) and
//!   ``docs/evidence/2026-11-13-stage15-two-levers.md`` (the two
//!   levers' declared row set)
//! - ``docs/evidence/data/residue-raw-scan.csv`` (raw-array rates)
//! - ``docs/evidence/data/stage9-absorption-probe.csv`` (the amended
//!   declaration basis, committed before the A/B)
//!
//! Numeric contract (spec §2.2): decode module — the densest
//! arithmetic surface of the port (the cross-product degenerate test,
//! the ``_nice``/``_raw_nice`` predicates, the plane law's
//! ``PLANE_TOL = 2e-3`` coplanarity, ``NOISE_REL = 1e-5`` re-listing
//! matching with the exact ``max(1.0, abs(...), ...)`` scale). All of
//! it is IEEE-exact ``+ - * /`` and comparisons on f64 widened once
//! from f32 (``f32_widen`` — the twin's ``struct.unpack('<f')`` exact
//! widening); expression shape copies the Python verbatim (no
//! reassociation, no factoring). The plane law's
//! ``nn = (n0**2 + n1**2 + n2**2) ** 0.5`` is the one non-``+ - * /``
//! expression the whale adds to the §2.2 surface (composite.py:532):
//! it is ported as ``powf`` — CPython's ``float.__pow__`` and Rust's
//! ``f64::powf`` both lower to the platform libm ``pow``. Measured
//! 2026-11-14 (the V3 port probe, session dir
//! ``v3-probes/nn_probe2.py``): over ALL 382,793 distinct f32 normal
//! triples carried by the corpus, the pow lowering and the mul/sqrt
//! lowering agree BIT-FOR-BIT (0 non-NaN divergences; the 386
//! NaN-carrying triples are decision-neutral — every comparison is
//! False and both lowerings return "coplanar") — so either lowering
//! is faithful on the measured surface, LLVM's powf-constant-expansion
//! transforms included. The ``clippy::suboptimal_flops`` allow below
//! is the pinned carve-out — mul_add changes rounding and flips
//! exactly such exact-equality decisions; see the crate docs in
//! ``../lib.rs`` for the full policy.
#![allow(clippy::suboptimal_flops)]

use std::collections::{BTreeMap, HashMap, HashSet};

use serde::Serialize;

use super::errors::{ExportError, UNDECODED_VARIANT};
use super::facets;
use super::mesh::{self, EdgeGuard, loop_area};
use super::pool::{EDGE_SUBKIND, PoolGroup};
use super::store::{StoreSpan, find};
use super::vote::{RefVote, WidthCandidate, dup_pin_map, loop_plane_status, vote_ref_width};

/// The scene-graph node record magic (twin: ``NODE_MAGIC``).
pub const NODE_MAGIC: &[u8; 4] = b"\x04\x04\xfd\xff";
/// The list-node token (twin: ``LIST_TOKEN``).
pub const LIST_TOKEN: &[u8; 5] = b"\xff\xff\x02\x00\x01";

/// The element-count sanity cap (twin: ``MAX_ELEMENT_COUNT``).
pub const MAX_ELEMENT_COUNT: u32 = 10_000_000;
/// The 2-bit table sanity cap (twin: ``MAX_TABLE_BYTES``).
pub const MAX_TABLE_BYTES: usize = 1 << 20;
/// The #34-era loop-count byte cap of the width rank: the base the #65
/// extension gates on (twin: ``BASE_LOOP_COUNTS``).
pub const BASE_LOOP_COUNTS: usize = 16;
/// The loop-count byte cap of the width rank (twin: ``MAX_LOOP_COUNTS``).
/// 16 through the #34 era (the corpus's clean stores carry k <= 16); 64
/// from #65 (2026-11-20): the Trappe_Parachute gap records carry k == ty
/// 24..39 — the cap was their only blocker (565 unresolved 0x42
/// candidates on 77 parts parse at (w2, k = ty), 379 of them
/// exact-tiling + in-bounds). The extension is zero-gated: a u16be
/// count table misreads as u8 pairs with a zero at every other entry
/// (the CAAGsiStartVolume regression measured 16/32 zeros and a
/// not-manifold mesh), while every corpus record the extension admits
/// carries a zero-free table.
pub const MAX_LOOP_COUNTS: usize = 64;

/// Table value -> f32 words written (0 = skip: the element carries no
/// coordinates in the region — the curve entries, U4). Index = the
/// 2-bit slot value (twin: ``SHAPES = {0: 3, 1: 0, 2: 1, 3: 2}``).
pub const SHAPES: [usize; 4] = [3, 0, 1, 2];

// Plane tolerance of the committed loop battery (stage 3b): see
// `super::vote::PLANE_TOL` — the battery moved there with the width
// vote (twin: the composite.py guard/vote split).

/// The gated families whose references must resolve in-bounds (the
/// exported markers plus the normal-carrying 0x49, the stage-2c gate
/// set) — twin: ``GATED``.
pub const GATED: [u8; 4] = [0x42, 0x49, 0x4A, 0x4C];

/// Short-record markers the composite path exports — twin:
/// ``EXPORTED_SHORT_MARKERS``. 0x49 is the strip family the clean path
/// already exports (``facets::SOUP_MARKERS``); it is admitted on the
/// 0x42 terms (its pinned reader + the per-loop dup-pin weld's
/// coplanarity battery and incremental edge-use guard).
pub const EXPORTED_SHORT_MARKERS: [u8; 4] = [0x42, 0x49, 0x4A, 0x4C];

/// The T3 relaxed families (#61, 2026-11-20) — twin:
/// ``RELAXED_SHORT_MARKERS``. 0x44 and 0x41 parse under the SAME
/// (width, k) tiling law as the exported families (226/226 carrier
/// records) but carry no 12-B normal. Their primitive is now pinned
/// (#66, 2026-11-20): u16 little-endian, with u8 as the compact
/// fallback — `parse_strip_records` offers the u16le candidate and
/// prefers u16 over u8 for these two markers. Their loops export in
/// the SECOND pass of `triangulate`, under the STRICT mesh guard — no
/// seam-area exception — so a base-manifold mesh stays manifold by
/// construction and the base pass stays byte-identical to the pre-T3
/// behavior.
pub const RELAXED_SHORT_MARKERS: [u8; 2] = [0x44, 0x41];

/// Markers observed in the extended-header form (the family's scope;
/// 2026-11-18, docs/evidence/2026-11-18-extended-header-family.md).
pub const EXTENDED_HEADER_MARKERS: [u8; 2] = [0x47, 0x4F];

/// Extended-header markers carrying the 12-byte normal payload.
pub const EXTENDED_NORMAL_MARKERS: [u8; 1] = [0x4F];

/// The primary-emit seam's keep threshold (2026-11-18, #34; twin:
/// ``PRIMARY_LOOP_AREA_REL``): a refused primary loop is dropped only
/// when its area is at most this fraction of the store mesh's area; a
/// larger over-use is real surface and is kept as before.  Measured on
/// the 24 not-manifold corpus parts the refused loops split at
/// 0.76% / 2.92%, so 1% sits in the gap (docs/evidence/
/// 2026-11-18-primary-emit-seam.md).
pub const PRIMARY_LOOP_AREA_REL: f64 = 1e-2;

/// One extended-header facet record — the twin's
/// ``composite.ExtendedFacetRecord``: ``01 <mk> ty b3 b4 ff``, then
/// ``u32le n``, a 12-B normal on 0x4f, ``b3 + b4`` u8 counts, and the
/// references (``3*ty`` independent triangles first, then the loops the
/// counts delimit; the first ``b3`` strips, the last ``b4`` polygons).
#[derive(Debug, Clone, PartialEq)]
pub struct ExtendedFacetRecord {
    /// The header's absolute offset.
    pub offset: usize,
    /// The marker byte (0x47 or 0x4f).
    pub marker: u8,
    /// ``ty`` — the independent-triangle count (``3*ty`` refs).
    pub triangles: u32,
    /// ``b3`` — the leading loops with strip semantics.
    pub strips: u32,
    /// ``b4`` — the trailing loops with closed-polygon semantics.
    pub polygons: u32,
    /// The ``b3 + b4`` counts (each a u8 by the law).
    pub counts: Vec<u32>,
    /// The ``n`` references (element indices at the record's voted width).
    pub refs: Vec<u32>,
    /// The record's end position (last reference byte).
    pub end: usize,
    /// The widened f64 normal on 0x4f (none on 0x47).
    pub normal: Option<(f64, f64, f64)>,
    /// The voted ref width (u8/u16be/u24be, #62).
    pub width: u8,
}

/// Noise-aware absorption tolerance (stage-4b R3): a pool vertex
/// "re-listed with noise" matches a written point within
/// :const:`NOISE_REL` relative, per coordinate, scaled by
/// ``max(1, |coord|)``. Measured noise <= 1.25e-08 relative; the
/// smallest genuinely-different coordinate pair measured is 4 decades
/// above it (twin: ``NOISE_REL``, composite.py:1002).
pub const NOISE_REL: f64 = 1e-5;

/// One element of the region walk — the twin's ``elements[i] =
/// (slot_value, point_or_None)`` in region order; the point is
/// ``None`` for a skip slot (the curve entries, U4).
pub type Element = (u8, Option<(f64, f64, f64)>);

/// The layout block the twin's ``decode_region`` info dict carries.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RegionInfo {
    /// The 2-bit table's byte length (``ceil(element_count / 4)``).
    pub table_bytes: usize,
    /// The declared P1g write count (f32 words).
    pub write_count: u32,
    /// ``4 * write_count`` (the region's byte span).
    pub region_bytes: usize,
    /// The payload-relative offset the walk ended at.  A container
    /// rep's ``walk_end`` is its payload END (its territory beyond the
    /// payload carries no records of its own).
    pub walk_end: usize,
    /// A container rep's point-window end (payload-relative); ``None``
    /// for a table node (records parse from ``walk_end`` on).
    pub container_window_end: Option<usize>,
}

/// One composite facet record parsed under the width rank — the
/// twin's ``(offset, marker, normal, counts, refs, width)`` tuples.
#[derive(Debug, Clone, PartialEq)]
pub struct CompositeRecord {
    /// The header's absolute offset.
    pub offset: usize,
    /// The marker byte (``0x41..=0x4f``).
    pub marker: u8,
    /// The 12-B f32le normal, widened to f64 at load (spec §2.2), on
    /// the normal-carrying markers.
    pub normal: Option<(f64, f64, f64)>,
    /// The ``k`` loop counts (u8, or ``ff``-escaped u32le; summing to
    /// ``n``) — the P1g form shared with the list node's counts.
    pub counts: Vec<u32>,
    /// The ``n`` width-byte big-endian references (element indices).
    pub refs: Vec<u32>,
    /// The winning width (1/2/3 bytes per reference).
    pub width: u8,
}

/// The loop counters of one :fn:`triangulate` call — the twin's
/// ``stats`` dict: the two loop counters plus the per-loop dup-pin
/// weld block (present exactly when dropped curve-entry loops exist).
#[derive(Debug, Clone, PartialEq, Default)]
pub struct LoopStats {
    /// Loops exported (no skip reference).
    pub loops_exported: u32,
    /// Loops dropped for referencing a skip slot (the curve entries).
    pub loops_curve_entry: u32,
    /// The ``stats["dup_pin"]`` key: the per-loop weld result (the
    /// welded triangles and counts), ``None`` when no dropped loop was
    /// evaluated.
    pub dup_pin: Option<DupPin>,
}

/// The per-loop dup-pin weld result (2026-11-18: battery + mesh guard
/// per loop): the welded loops' triangles (written-rank indexed), the
/// degenerate count, the welded-loop count and the guard/battery
/// refusal count.
#[derive(Debug, Clone, PartialEq)]
pub struct DupPin {
    /// The welded loops' triangles (written-rank indexed).
    pub triangles: Vec<(u32, u32, u32)>,
    /// The welded loops' degenerate skips (always 0: a degenerate
    /// emission refuses the loop, fail-closed).
    pub degenerate: u32,
    /// The welded loop count.
    pub loops: u32,
    /// The loops refused by the pinnability/battery/mesh-guard tests.
    pub refused: u32,
}

/// The mixedwrite ``rep_laws`` block — the twin's
/// ``{"table": n, "raw": n, "flat": n}`` (all three keys present,
/// construction order = field order).
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct RepLaws {
    /// Reps decoded by the table law (with the extent candidates).
    pub table: u32,
    /// Reps decoded by the escape-pinned raw law.
    pub raw: u32,
    /// Reps decoded by the counts_end-pinned flat law.
    pub flat: u32,
}

/// The twin's composite ``info`` dict — the summary's additive
/// ``composite`` block (``export-summary-v1.json`` properties.composite,
/// ``additionalProperties: true``). Field declaration order = the
/// twin's dict construction order; the per-stage key sets are
/// reproduced by the ``Option`` skips (the raw-array stage carries no
/// ``write_count``/``table_bytes``, the per-rep stages add the
/// ``reps_*`` keys, the mixedwrite stage adds ``rep_laws``, the raw
/// stage adds the ``raw_*`` keys, and the stage-10/15 laws append
/// ``curve_entry_law``/``loops_curve_entry_exported`` and the
/// ``unordered_dedup_*`` keys).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct CompositeInfo {
    /// The decode stage (``identity-table-walk`` / ``identity-per-rep``
    /// / ``identity-raw-array`` / ``identity-mixedwrite-reps``).
    pub stage: &'static str,
    /// The declared element count(s) (the sum on the per-rep stages).
    pub element_decl: usize,
    /// The written points in region order (the exported vertices).
    pub node_points: usize,
    /// The skip slots (the curve entries, U4).
    pub curve_entries: usize,
    /// The declared write count(s) — absent on the raw-array stage.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub write_count: Option<usize>,
    /// The table byte length(s) — absent on the raw-array stage; on
    /// the mixedwrite stage the sum over the table-law reps only.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub table_bytes: Option<usize>,
    /// The facet header candidates in the walked territory.
    pub facet_candidates: usize,
    /// The records the width rank accepted.
    pub facet_records: usize,
    /// Parsed records outside the exported markers (the twin's
    /// ``dict[int, int]`` — JSON string keys, first-occurrence order
    /// on the twin, sorted here: parsed-document equality, §3.2, is
    /// order-insensitive on object keys).
    pub skipped_markers: BTreeMap<u8, u32>,
    /// The decoded list-node payload byte span(s) (the stage-5
    /// fold-in; over 4096 B marks the big-form family).
    pub node_bytes: usize,
    /// Per-rep stages: the walk-exact/law-decoded rep count.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reps_decoded: Option<usize>,
    /// Per-rep stages: the reps that exported.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reps_exported: Option<usize>,
    /// Per-rep stages: the reps that stayed unexported.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reps_unexported: Option<usize>,
    /// Per-rep stages: the unexported reps' reasons (fail-closed).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rep_reasons: Option<Vec<String>>,
    /// Mixedwrite stage: the per-law rep counts.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rep_laws: Option<RepLaws>,
    /// Raw stage: the pinned array start.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub raw_start: Option<usize>,
    /// Raw stage: the nice rate (the twin's ``round(rate, 4)``).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub raw_nice_rate: Option<f64>,
    /// Raw stage: the x-ascending rate (the twin's ``round(asc, 4)``).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub raw_x_asc_rate: Option<f64>,
    /// Raw stage: the bytes after the trail-escape byte.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub raw_trail_bytes: Option<usize>,
    /// Raw stage: the count3 field (recorded, never validated — open).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub raw_count3: Option<u32>,
    /// Loops exported (post the stage-3 dup-pin merge).
    pub loops_exported: u32,
    /// Loops still dropped (0 when the dup-pin law exported them all).
    pub loops_curve_entry: u32,
    /// Extended-header family (2026-11-18): the accepted record count
    /// (absent when the store carries none).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub extended_header_records: Option<usize>,
    /// Extended-header family: the triangles those records emitted.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub extended_header_triangles: Option<usize>,
    /// Extended-header family: the records the manifold-assembly gate
    /// declined (their triangles would have tipped an edge past two
    /// uses; absent when none were declined).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub extended_header_declined: Option<usize>,
    /// The degenerate member triangles filtered from accepted extended
    /// records (the member-filter law; None when 0 — the twin only
    /// sets the key when > 0).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub extended_members_filtered: Option<usize>,
    /// Primary-emit seam (2026-11-18): the sliver loops skipped at the
    /// primary emission (absent when none).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub primary_loop_skips: Option<u32>,
    /// Primary-emit seam: candidate slivers the fire gate declined (the
    /// store stays not-manifold, so the pre-seam emission is kept).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub primary_loop_seam_declined: Option<u32>,
    /// Primary-emit seam: over-using loops kept because each is larger
    /// than the sliver bound (real surface — never dropped).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub primary_loop_kept: Option<u32>,
    /// The T3 relaxed families (#61): loops the strict guard accepted
    /// (absent when none).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub relaxed_loops_accepted: Option<u32>,
    /// The T3 relaxed families (#61): loops the strict guard refused
    /// (absent when none).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub relaxed_loops_declined: Option<u32>,
    /// Fase 3 L1 (#70): kept primary loops skipped as re-listed skin
    /// (the fail-closed third pass; absent when it never fired).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub primary_loop_relist_skips: Option<u32>,
    /// Fase 3 L1 (#70): the boundary-edge count before->after the
    /// relist skip (absent when it never fired).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub primary_loop_relist_boundary: Option<String>,
    /// Stage-10 (relaxed stage 15) / 2026-11-18: the law name on a
    /// firing store (``e0b-dup-pin`` or ``closed-manifold-weld``).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub curve_entry_law: Option<&'static str>,
    /// Stage-10 (relaxed stage 15): the dup-pinned loop count.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub loops_curve_entry_exported: Option<u32>,
    /// Stage-15: the dropped duplicate copies on a firing dedup.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub unordered_dedup_dropped: Option<u32>,
    /// Stage-15: a fired-and-declined dedup (fail-closed).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub unordered_dedup_declined: Option<u32>,
    /// W1-B multi-region second chance (2026-11-22): the merged rep
    /// count on an adopted multi-region decode (stage
    /// ``identity-multiregion``).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub multiregion_reps: Option<usize>,
    /// W1-B multi-region second chance: the fail-closed decline reason
    /// on the still-not-manifold residue (the single-rep emission is
    /// kept byte-for-byte; absent when the route never ran).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub multiregion_declined: Option<String>,
    /// W10 (2026-11-22): the node scan's extent-recovered reps (the
    /// stage-8 leading-zero-table overshoot family; absent when none).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub multiregion_extent_reps: Option<usize>,
    /// The W17 container reps (the ``00 00 00 01`` family) among
    /// the merged reading's reps (None when none decoded).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub multiregion_container_reps: Option<usize>,
}

/// The decoded export of one composite store span — the twin's
/// ``(points, triangles, degenerate, info)`` return tuple plus the
/// §2.3 curve exposure (additive, NOT part of the Fidelity definition
/// — see the boundary note above :fn:`curve_sequence`).
#[derive(Debug, Clone, PartialEq)]
pub struct CompositeDecode {
    /// The written points in region order (the exported vertices).
    pub points: Vec<(f64, f64, f64)>,
    /// The triangle soup (indices into ``points``).
    pub triangles: Vec<(u32, u32, u32)>,
    /// The degenerate strip triangles skipped (F7, composite decode).
    pub degenerate: u32,
    /// The composite summary block.
    pub info: CompositeInfo,
    /// The §2.3 curve exposure: every dropped curve-entry loop's
    /// pre-weld point sequence (in dropped-loop encounter order, per
    /// exported rep on the per-rep paths). NEVER serialized into the
    /// summary or the PLY — the harness must not see it (§3.2).
    pub curves: Vec<Vec<(f64, f64, f64)>>,
    /// The emission units' point offsets, ascending (one element on the
    /// single-space paths): the stage-15 dedup's keeper rule ranks a
    /// copy by the unit that emitted it, and a rep's welded loops carry
    /// that rep's point base, so a later rep's re-listing never
    /// displaces the earlier rep's surface. Internal — never
    /// serialized (the twin's private ``_space_offsets``).
    pub space_offsets: Vec<usize>,
    /// Fase 3 L1 (#70): the relist pass's skipped kept loops' triangles
    /// (store-level indices) — the vertex-coverage gate's input.
    /// Internal — never serialized.
    pub kept_loop_tris: Vec<(u32, u32, u32)>,
    /// Fase 3 L1 (#70): how many loops ``kept_loop_tris`` carries.
    /// Internal — never serialized.
    pub kept_loop_count: u32,
    /// Fase 3 L1 (#70): loops the relist pass declined to emit.
    /// Internal — never serialized.
    pub relist_forced: u32,
}

/// The twin's ``_f32`` (composite.py:222): the ONE widening point —
/// an f32 load, widened to f64 exactly (spec §2.2).
fn f32_widen(data: &[u8], pos: usize) -> f64 {
    f32::from_le_bytes([data[pos], data[pos + 1], data[pos + 2], data[pos + 3]]) as f64
}

/// The twin's ``_nice`` (composite.py:226-235): the stage-3b walk's
/// finite/plausible predicate — ``v == v and abs(v) < 1e9``. The
/// table-driven walk needs no pruning predicate (the table fixes the
/// parse), so the stage-2c probe's 1e-6 floor is dropped (dated
/// 2026-11-11); real tessellation coordinates reach ~1e-15 around
/// zero and junk detection falls to the walk-exact / pool / in-bounds
/// checks.
// ``v == v`` is the twin's NaN test verbatim — the "equal operands"
// are the law, not a slip.
#[allow(clippy::eq_op)]
fn nice(v: f64) -> bool {
    v == v && v.abs() < 1e9
}

/// The twin's ``read_count`` (P1g): one byte, ``ff`` escapes to u32le.
/// Returns ``(value, next_pos)``. The escape branch reads a SHORT
/// slice when the payload ends inside the count — Python's
/// ``int.from_bytes`` parses what is there (a smaller value, next
/// ``pos`` still ``pos + 5``); the port mirrors that. A ``pos`` past
/// the payload is the twin's uncaught ``IndexError`` (an unclassified
/// crash the compared populations never reach) — this flavor panics;
/// :fn:`read_count_checked` returns ``None`` where the twin catches.
fn read_count(data: &[u8], pos: usize) -> (u32, usize) {
    if data[pos] == 0xFF {
        let end = (pos + 5).min(data.len());
        let mut value: u32 = 0;
        for (i, b) in data[pos + 1..end].iter().enumerate() {
            value |= u32::from(*b) << (8 * i);
        }
        (value, pos + 5)
    } else {
        (u32::from(data[pos]), pos + 1)
    }
}

/// :fn:`read_count` where the twin catches ``(IndexError,
/// struct.error)``: ``None`` on a ``pos`` past the payload.
fn read_count_checked(data: &[u8], pos: usize) -> Option<(u32, usize)> {
    if pos >= data.len() {
        None
    } else {
        Some(read_count(data, pos))
    }
}

/// The twin's f64-triple set membership: Python's set hashes
/// ``-0.0 == 0.0`` to one element; NaN never equals anything (each
/// NaN object is its own element and never matches a pool vertex).
/// The key canonicalizes ``-0.0`` to ``+0.0`` (bit-equal keys);
/// a NaN key keeps its payload and never matches a finite key.
fn vkey(v: (f64, f64, f64)) -> (u64, u64, u64) {
    fn z(x: f64) -> u64 {
        if x == 0.0 {
            0.0f64.to_bits()
        } else {
            x.to_bits()
        }
    }
    (z(v.0), z(v.1), z(v.2))
}

/// The largest token-bearing scene-graph node in ``[lo, hi)`` — the
/// twin's ``find_list_node``. Returns ``(payload_lo, payload_hi,
/// element_count, edge_ref_bound)`` (absolute ``data`` offsets) or
/// ``None``. Every composite store's node territory carries the token
/// (N1, 939/939); the LIST node is the one whose payload carries the
/// point region — the largest payload (the stage-2b census; on the
/// U3-variant family this payload is a multi-part container — those
/// stores fail the walk below, named).
fn find_list_node(data: &[u8], lo: usize, hi: usize) -> Option<(usize, usize, u32, u32)> {
    let mut best: Option<(usize, usize, u32, u32)> = None;
    let mut pos = lo;
    while let Some(at) = find(data, NODE_MAGIC, pos, hi) {
        let end = match find(data, NODE_MAGIC, at + 4, hi) {
            Some(e) => e,
            None => hi,
        };
        let (plo, phi) = (at + 4, end);
        let payload = &data[plo..phi];
        if let Some(tok) = find(payload, LIST_TOKEN, 0, payload.len())
            && tok <= 64
        {
            let p = tok + 5;
            // The twin's ``read_count`` here is UNCAUGHT: a payload
            // truncated inside the declared counts raises IndexError
            // out of the exporter (an unclassified crash; the
            // compared populations never reach it) — the port
            // mirrors the crash (see ``fidelity-cli.rs``).
            let (c1, p2) = read_count(payload, p);
            let (c2, _p3) = read_count(payload, p2);
            if 0 < c1 && c1 <= MAX_ELEMENT_COUNT {
                let better = match best {
                    None => true,
                    Some((bplo, bphi, _, _)) => phi - plo > bphi - bplo,
                };
                if better {
                    best = Some((plo, phi, c1, c2));
                }
            }
        }
        pos = at + 1;
    }
    best
}

/// Region layout after the zero block (P1t corrected, stage 3b) — the
/// twin's ``layout``. The 2-bit table spans exactly
/// ``ceil(element_count / 4)`` bytes after the zero block, then the
/// P1g write count, then the region. Returns ``(table_start,
/// table_len, count_pos, region_start, write_count)``; raises
/// :struct:`ExportError` (``undecoded-variant``) when the layout does
/// not fit the payload.
// ``(n + 3) / 4`` is the twin's expression shape — the div_ceil
// rewrite would be value-identical but the port keeps the twin's
// arithmetic surface reviewable line-by-line.
#[allow(clippy::manual_div_ceil)]
fn layout(
    payload: &[u8],
    element_count: u32,
) -> Result<(usize, usize, usize, usize, u32), ExportError> {
    let tok = find(payload, LIST_TOKEN, 0, payload.len()).ok_or_else(|| {
        ExportError::new(
            UNDECODED_VARIANT,
            "list node payload without the list token",
        )
    })?;
    let mut p = tok + 5;
    // The twin's count reads are uncaught (see find_list_node) — the
    // panicking flavor mirrors them; both are unreachable here (the
    // callers validated the counts on the same payload).
    let (_, np) = read_count(payload, p);
    p = np;
    let (_, np) = read_count(payload, p);
    p = np;
    while p + 4 <= payload.len() && payload[p..p + 4] == [0u8; 4] {
        p += 4;
    }
    let table_len = (element_count as usize + 3) / 4;
    if table_len > MAX_TABLE_BYTES {
        return Err(ExportError::new(
            UNDECODED_VARIANT,
            format!(
                "declared element count {element_count} implies a \
                 {table_len} B table, above the {MAX_TABLE_BYTES} B sanity cap"
            ),
        ));
    }
    let count_pos = p + table_len;
    if count_pos >= payload.len() {
        return Err(ExportError::new(
            UNDECODED_VARIANT,
            format!(
                "the {table_len} B 2-bit table runs past the payload \
                 (count position {count_pos} >= payload length {}); \
                 the store's layout does not fit the P1t law",
                payload.len()
            ),
        ));
    }
    let (write_count, region_start) = read_count(payload, count_pos);
    let region_end = region_start + 4 * write_count as usize;
    if region_end > payload.len() {
        return Err(ExportError::new(
            UNDECODED_VARIANT,
            format!(
                "declared write count {write_count} overruns the payload \
                 (region end {region_end} > {})",
                payload.len()
            ),
        ));
    }
    Ok((p, table_len, count_pos, region_start, write_count))
}

/// The 2-bit table: LSB-first slots, one per element — the twin's
/// ``table_slots``.
fn table_slots(
    payload: &[u8],
    table_start: usize,
    table_len: usize,
    element_count: u32,
) -> Vec<u8> {
    let mut slots = Vec::with_capacity(table_len * 4);
    for &b in &payload[table_start..table_start + table_len] {
        slots.extend_from_slice(&[b & 3, (b >> 2) & 3, (b >> 4) & 3, (b >> 6) & 3]);
    }
    slots.truncate(element_count as usize);
    slots
}

/// Deterministic table-driven decode of the point region (U1, stage
/// 3b) — the twin's ``decode_region``. Returns the elements in region
/// order plus the layout block. The walk is bounded by the declared
/// region: a slot needing words past ``region_start + 4 *
/// write_count``, a walk ending short of it, or a non-finite/
/// implausible written coordinate each raise :struct:`ExportError`
/// (``undecoded-variant``) with the specific gap — the walk-exact
/// failures are the U3-variant second layout family's signature. The
/// initial LCP state is the origin (P1i subsumed): partial writes
/// carry the previous element's coordinates and only the WRITTEN
/// values are nice-checked.
// The twin's origin initialization (`x = y = z = 0.0`) is the P1i law:
// a region opening with partial writes reads the origin state. The
// lint fires when the first element overwrites before a read — the
// initialization stays (mirroring the twin), the warning is noise.
#[allow(unused_assignments)]
fn decode_region(
    payload: &[u8],
    element_count: u32,
) -> Result<(Vec<Element>, RegionInfo), ExportError> {
    let (table_start, table_len, _count_pos, region_start, write_count) =
        layout(payload, element_count)?;
    if write_count > 3 * element_count {
        return Err(ExportError::new(
            UNDECODED_VARIANT,
            format!(
                "declared write count {write_count} exceeds the table's word \
                 budget (3 x {element_count} elements): the region does not \
                 decode under the table law"
            ),
        ));
    }
    let slots = table_slots(payload, table_start, table_len, element_count);
    let region_end = region_start + 4 * write_count as usize;
    let mut pos = region_start;
    // the initial LCP state is the origin (P1i subsumed)
    let (mut x, mut y, mut z) = (0.0f64, 0.0f64, 0.0f64);
    let mut elements = Vec::with_capacity(slots.len());
    for (i, v) in slots.iter().enumerate() {
        let shape = SHAPES[*v as usize];
        if shape == 0 {
            elements.push((*v, None));
            continue;
        }
        if pos + 4 * shape > region_end {
            return Err(ExportError::new(
                UNDECODED_VARIANT,
                format!(
                    "table walk exceeds the declared region at element {i} \
                     (shape {v} needs {shape} f32 words, {} left \
                     of the declared {write_count}): walk-exact failure — the \
                     store's layout family does not decode under the stage-3b \
                     table law (U3-variant residue)",
                    region_end - pos
                ),
            ));
        }
        let vals: [f64; 3] = match shape {
            3 => {
                x = f32_widen(payload, pos);
                y = f32_widen(payload, pos + 4);
                z = f32_widen(payload, pos + 8);
                [x, y, z]
            }
            2 => {
                y = f32_widen(payload, pos);
                z = f32_widen(payload, pos + 4);
                [x, y, z]
            }
            _ => {
                z = f32_widen(payload, pos);
                [x, y, z]
            }
        };
        // The twin checks only the WRITTEN vals: shape 3 -> (x, y, z),
        // shape 2 -> (y, z), shape 1 -> (z,).
        let written = match shape {
            3 => &vals[..],
            2 => &vals[1..],
            _ => &vals[2..],
        };
        if !written.iter().all(|c| nice(*c)) {
            return Err(ExportError::new(
                UNDECODED_VARIANT,
                format!(
                    "non-finite or implausible coordinate at element {i} \
                     (write shape {v}): {written:?}"
                ),
            ));
        }
        pos += 4 * shape;
        elements.push((*v, Some((x, y, z))));
    }
    if pos != region_end {
        return Err(ExportError::new(
            UNDECODED_VARIANT,
            format!(
                "table walk consumed {} of the declared \
                 {} region words (write count {write_count}): \
                 walk-exact failure — the store's layout family does not decode \
                 under the stage-3b table law (U3-variant residue)",
                pos - region_start,
                4 * write_count as usize
            ),
        ));
    }
    Ok((
        elements,
        RegionInfo {
            table_bytes: table_len,
            write_count,
            region_bytes: 4 * write_count as usize,
            walk_end: pos,
            container_window_end: None,
        },
    ))
}

/// Decode the list node's point region (both forms, identity law) —
/// the twin's ``decode_node_points``. Returns the written point list
/// in region order, the skip count, and the layout block.
// The tuple return is the twin's return shape (points, skip_count,
// info); the type_complexity rewrite would hide the 1:1 mapping.
#[allow(clippy::type_complexity)]
pub fn decode_node_points(
    payload: &[u8],
    element_count: u32,
) -> Result<(Vec<(f64, f64, f64)>, usize, RegionInfo), ExportError> {
    let (elements, info) = decode_region(payload, element_count)?;
    let skip_count = elements.iter().filter(|e| e.1.is_none()).count();
    let points: Vec<(f64, f64, f64)> = elements.iter().filter_map(|e| e.1).collect();
    Ok((points, skip_count, info))
}

// ``PLANE_TOL``, ``loop_plane_status`` and ``dup_pin_map`` live in
// `super::vote` (the battery is shared with the width vote) — twin:
// the composite.py guard/vote split.

/// One exported loop's triangles under the strip/polygon semantics
/// (G3) — the twin's ``_loop_triangles``: 0x4c polygon fans
/// triangulate from the first reference, 0x42/0x4a strips use the
/// sliding window with the odd-triangle winding flip; degenerate
/// triangles (repeated coordinates, or the exactly-zero cross product
/// on strips, G3 F7) are skipped and counted. ``idxs`` are
/// written-point ranks (indices into ``points``, the exported vertex
/// list).
fn loop_triangles(mk: u8, idxs: &[u32], points: &[(f64, f64, f64)]) -> (Vec<(u32, u32, u32)>, u32) {
    let lp: Vec<(f64, f64, f64)> = idxs.iter().map(|&i| points[i as usize]).collect();
    let mut triangles = Vec::new();
    let mut degenerate = 0u32;
    if mk == 0x4C {
        for t in 1..idxs.len().saturating_sub(1) {
            let tri = (idxs[0], idxs[t], idxs[t + 1]);
            let (a, b, c) = (lp[0], lp[t], lp[t + 1]);
            if a == b || b == c || a == c {
                degenerate += 1;
                continue;
            }
            triangles.push(tri);
        }
    } else {
        for t in 0..idxs.len().saturating_sub(2) {
            let mut tri = (idxs[t], idxs[t + 1], idxs[t + 2]);
            if t % 2 == 1 {
                tri = (tri.2, tri.1, tri.0);
            }
            let (a, b, c) = (lp[t], lp[t + 1], lp[t + 2]);
            if a == b || b == c || a == c {
                degenerate += 1;
                continue;
            }
            if cross_zero(a, b, c) {
                degenerate += 1;
                continue;
            }
            triangles.push(tri);
        }
    }
    (triangles, degenerate)
}

/// The twin's ``_loop_triangles_split`` (the W16 A4 emission law,
/// adopted 2026-11-22 from ``curves::split_loop_triangles`` — the same
/// G3 F7 degeneracy predicate, winding-invariant, so the strip flip
/// classifies identically): ``loop_triangles`` with the collapsed
/// triangles named instead of only counted.  The writer's
/// degenerate-quad convention (the pinned ``(P, X, P, Y)``) splits off
/// per triangle; the real remainder still faces the mesh guard.
/// ``(real, degenerate_count, degenerate_triples)``.
type LoopSplit = (Vec<(u32, u32, u32)>, u32, Vec<(u32, u32, u32)>);

fn loop_triangles_split(mk: u8, idxs: &[u32], points: &[(f64, f64, f64)]) -> LoopSplit {
    let lp: Vec<(f64, f64, f64)> = idxs.iter().map(|&i| points[i as usize]).collect();
    let mut real = Vec::new();
    let mut degen = Vec::new();
    if mk == 0x4C {
        for t in 1..idxs.len().saturating_sub(1) {
            let tri = (idxs[0], idxs[t], idxs[t + 1]);
            let (a, b, c) = (lp[0], lp[t], lp[t + 1]);
            if a == b || b == c || a == c {
                degen.push(tri);
                continue;
            }
            real.push(tri);
        }
    } else {
        for t in 0..idxs.len().saturating_sub(2) {
            let mut tri = (idxs[t], idxs[t + 1], idxs[t + 2]);
            if t % 2 == 1 {
                tri = (tri.2, tri.1, tri.0);
            }
            let (a, b, c) = (lp[t], lp[t + 1], lp[t + 2]);
            if a == b || b == c || a == c || cross_zero(a, b, c) {
                degen.push(tri);
                continue;
            }
            real.push(tri);
        }
    }
    (real, degen.len() as u32, degen)
}

/// The twin's ``_cross_zero``: the cross product is EXACTLY the zero
/// triple (``-0.0 == 0.0`` is true, as in the twin's tuple equality —
/// the V2 numeric-contract probe kept that tie order).
fn cross_zero(a: (f64, f64, f64), b: (f64, f64, f64), c: (f64, f64, f64)) -> bool {
    let ab = (b.0 - a.0, b.1 - a.1, b.2 - a.2);
    let ac = (c.0 - a.0, c.1 - a.1, c.2 - a.2);
    let cx = ab.1 * ac.2 - ab.2 * ac.1;
    let cy = ab.2 * ac.0 - ab.0 * ac.2;
    let cz = ab.0 * ac.1 - ab.1 * ac.0;
    cx == 0.0 && cy == 0.0 && cz == 0.0
}

/// The 0x49 triangle-list record under its PINNED law (2026-11-18) —
/// the twin's ``parse_049_record``.
///
/// ``01 49 ty ff`` + ``u32le n`` + the 12-B f32le normal, then **no
/// count table**: the ``n`` references are u16be element indices, three
/// consecutive refs per triangle (``n == 3 * ty``), one 3-ref strip
/// loop per triangle. The record ends at or before the next header.
/// Corpus measurement (docs/evidence/2026-11-18-composite-0x49.md,
/// 0X49-01..07): 270,743/270,762 candidates satisfy ``n == 3*ty``,
/// 269,905 tile exactly, 270,270 keep every ref inside the element
/// space and **270,270/270,270 of those loops are coplanar** against
/// the stored normal at ``PLANE_TOL``. The generic (width, k) vote
/// reaches only 2,233 of them and never reproduces this shape, so the
/// family gets its own reader: the count table is absent, not variant.
fn parse_049_record(
    data: &[u8],
    o: usize,
    nxt: usize,
    n: u32,
    normal: Option<(f64, f64, f64)>,
    element_count: u32,
) -> Option<CompositeRecord> {
    let ty = data[o + 2] as u32;
    if n != 3 * ty {
        return None;
    }
    let end = o + 20 + 2 * n as usize;
    if end > nxt {
        return None;
    }
    let refs: Vec<u32> = (0..n as usize)
        .map(|j| {
            let at = o + 20 + 2 * j;
            u32::from(u16::from_be_bytes([data[at], data[at + 1]]))
        })
        .collect();
    if refs.iter().any(|&r| r >= element_count) {
        return None;
    }
    Some(CompositeRecord {
        offset: o,
        marker: 0x49,
        normal,
        counts: vec![3u32; ty as usize],
        refs,
        width: 2,
    })
}

/// Every strip record with the width disambiguated (stage-3b rule,
/// extended 2026-11-11 stage 4b: u24be candidate + the loop plane
/// tiebreak; integrated 2026-11-12 stage 5, #34) — the twin's
/// ``parse_strip_records``.
///
/// The 0x49 triangle-list family has its own pinned reader
/// (:func:`parse_049_record`): it carries no count table, so the
/// generic (width, k) vote is not applied to it.
///
/// Candidate parses: width u8/u16be (plus u24be ONLY when
/// ``element_count > 65,535`` — a 2-byte ref cannot index such an
/// element space, and on smaller spaces a 3-byte candidate can only
/// read junk past them: measured on the corpus A/B, 4 exported stores
/// flip to OOB junk when u24be is offered below the threshold) x
/// count-byte ``k`` (0..16) summing to ``n``, ending at or before the
/// next header. Rank: exact tiling, then no out-of-range refs, then
/// no-repeated-refs-within-a-loop, then non-coplanar
/// normal-carrying loops (only computed when ``elements`` — the
/// decoded element space the refs index — is passed; a candidate
/// whose loops are non-coplanar against the record's stored normal
/// loses to one that is coplanar; without ``elements`` the rank is
/// the committed stage-3b one), then the narrower width. The winning
/// parse is then gated fail-closed on the element space (#66,
/// 2026-11-20): a record whose refs leave it stays unresolved, the
/// same post-vote rule the extended family applies.
///
/// The relaxed 0x41/0x44 primitive (#66): those two markers are read
/// in **u16 little-endian** as well as the committed u16be/u8
/// candidates (docs/evidence/2026-11-20-composite-relaxed-primitive.md:
/// 6 of the 10 OOB records are u16le, 2 are u8). Two fail-closed
/// conditions keep the u16le hypothesis from claiming byte patterns
/// that are not records: a u16le candidate whose block would swallow a
/// subsequent 6-byte extended-header candidate is a misread, and a u8
/// winner whose 2n-wide block straddles such a header while its u16le
/// reading is a complete in-bounds stream is a half-read, not a
/// record (the Audi 0x301e912 false header). Returns the records plus
/// the header-candidate count.
fn parse_strip_records(
    data: &[u8],
    lo: usize,
    hi: usize,
    element_count: u32,
    elements: Option<&[Element]>,
) -> (Vec<CompositeRecord>, usize) {
    let hdrs = facets::strip_headers(data, lo, hi);
    let ext_hdrs: Vec<usize> = if hdrs
        .iter()
        .any(|&h| RELAXED_SHORT_MARKERS.contains(&data[h + 1]))
    {
        facets::facet_headers(data, lo, hi)
    } else {
        Vec::new()
    };
    let widths: &[u8] = if element_count > 65_535 {
        &[1, 2, 3]
    } else {
        &[1, 2]
    };
    let mut out = Vec::new();
    for (i, &o) in hdrs.iter().enumerate() {
        let nxt = if i + 1 < hdrs.len() { hdrs[i + 1] } else { hi };
        let mk = data[o + 1];
        let hlen: usize = match facets::header_len(data, o) {
            Some(6) | None => continue, // the extended form has its own parser
            Some(length) => length,
        };
        if o + hlen + 4 > nxt {
            continue;
        }
        let n = u32::from_le_bytes([
            data[o + hlen],
            data[o + hlen + 1],
            data[o + hlen + 2],
            data[o + hlen + 3],
        ]);
        if n > 1_000_000 {
            continue;
        }
        let has_normal = facets::NORMAL_MARKERS_ALL.contains(&mk);
        let base = o + hlen + 4 + if has_normal { 12 } else { 0 };
        let mut normal = None;
        if has_normal {
            if base > hi {
                continue;
            }
            normal = Some((
                f32_widen(data, o + hlen + 4),
                f32_widen(data, o + hlen + 8),
                f32_widen(data, o + hlen + 12),
            ));
        }
        if mk == 0x49 {
            // The triangle-list family's own law (no count table; u16be
            // refs; n == 3*ty), twin of parse_049_record. The law is
            // the 4-byte header form; a 5-byte-form candidate (zero
            // accepted corpus records, BR2-17) stays unresolved rather
            // than falling back to the misparse.
            if hlen == 4
                && let Some(rec) = parse_049_record(data, o, nxt, n, normal, element_count)
            {
                out.push(rec);
            }
            continue;
        }
        let relaxed = RELAXED_SHORT_MARKERS.contains(&mk);
        let h6: Option<usize> = if relaxed {
            ext_hdrs.get(ext_hdrs.partition_point(|&h| h <= o)).copied()
        } else {
            None
        };
        // The ONE width vote (`vote_ref_width`): the candidates this
        // record's (width, endian, k) discovery admits, ranked by the
        // shared tuple (exact tiling, OOB, repeats, non-coplanar
        // loops, u16-over-u8, endian, width, k). The u16le-swallow
        // gate and the #65 zero gate stay discovery-level; the #66
        // OOB post-gate lives in the vote itself.
        let mut candidates: Vec<WidthCandidate> = Vec::new();
        for &width in widths {
            let endians: &[bool] = if relaxed && width == 2 {
                &[false, true]
            } else {
                &[false]
            };
            for &little in endians {
                for k in 0..=MAX_LOOP_COUNTS {
                    let Some((counts, counts_bytes)) = facets::read_counts(data, base, k, nxt)
                    else {
                        break;
                    };
                    let sum: u32 = counts.iter().copied().sum();
                    if sum != n {
                        continue;
                    }
                    if k > BASE_LOOP_COUNTS && counts.contains(&0) {
                        // #65 zero gate on the k extension: a u16be count
                        // table misreads as u8 pairs with a zero at every
                        // other entry (CAAGsiStartVolume: 16/32 zeros, a
                        // not-manifold mesh); every corpus record the
                        // extension admits is zero-free.
                        continue;
                    }
                    let counts_end = base + counts_bytes;
                    let end = counts_end + width as usize * n as usize;
                    if end > nxt {
                        continue;
                    }
                    if little && h6.is_some_and(|h| counts_end < h && h < end) {
                        // #66 fail-closed on the u16le hypothesis: a block
                        // that would swallow a 6-byte extended header
                        // candidate is a misread (the two Audi false
                        // headers end inside a real 0x47 this way).
                        continue;
                    }
                    candidates.push(WidthCandidate {
                        width,
                        little,
                        counts,
                        counts_end,
                        end,
                        exact: end == nxt,
                        tri_count: 0,
                        relaxed_u16: relaxed,
                        k: k as u32,
                    });
                }
            }
        }
        let Some(RefVote {
            refs,
            counts,
            width,
            end,
        }) = vote_ref_width(
            data,
            n,
            candidates,
            element_count,
            normal,
            elements,
            // the short-form law RANKS repeats (the misread-detection
            // slot); the u16-over-u8 slot arms on the relaxed markers
            true,
        )
        else {
            continue;
        };
        if relaxed
            && width == 1
            && h6.is_some_and(|h| {
                end < h
                    && h < end + n as usize
                    && h + 2 <= end + n as usize
                    && (end - n as usize..end + n as usize).step_by(2).all(|p| {
                        u32::from(u16::from_le_bytes([data[p], data[p + 1]])) < element_count
                    })
            })
        {
            // #66: a u8 winner whose u16le reading is a complete,
            // in-bounds ref stream reaching at least one whole ref
            // past a 6-byte header is a half-read of that stream,
            // not a u8 record (the Audi 0x301e912 false header).
            continue;
        }
        if width == 1
            && n >= 8
            && end + n as usize <= hi
            && (0..2 * n as usize)
                .step_by(2)
                .all(|j| data[end - n as usize + j] == 0)
            && (0..2 * n as usize).step_by(2).any(|j| {
                u32::from(u16::from_be_bytes([
                    data[end - n as usize + j],
                    data[end - n as usize + j + 1],
                ])) >= element_count
            })
        {
            // W1 marathon anti-half-read (twin of the Python arm): the
            // u8 winner's block is a u16be stream's high-half zeros
            // (every even byte 0x00 over n >= 8 refs) whose u16be
            // re-reading leaves the element space — the store's element
            // space is truncated and the u8 reading is the permuted
            // garbage the gap-edge OOB tiebreak kept (acc-Cont-Lft
            // 0x5255e family). The u8 triangles are false surface and
            // the u16be reading fails the #66 gate too; decline
            // fail-closed.
            continue;
        }
        out.push(CompositeRecord {
            offset: o,
            marker: mk,
            normal,
            counts,
            refs,
            width,
        });
    }
    (out, hdrs.len())
}

/// One dropped curve-entry loop: (marker, record normal, loop refs) in
/// encounter order — the dup-pin input and the §2.3 curve exposure's
/// raw material. Extended-header loops ride here too, with their
/// synthetic kind (0x42 strip / 0x4c polygon).
type DroppedLoop = (u8, Option<(f64, f64, f64)>, Vec<u32>);

/// The escaped-header counts-table cap (#64): ``b3 + b4`` may escape to
/// u32le values, so the counts-table length needs a sanity bound (the
/// corpus's escaped records carry ``k`` 192; 4,096 is 20x that) — twin:
/// ``ESCAPED_MAX_K``.
const ESCAPED_MAX_K: usize = 4_096;

/// The P1g-escaped extended-header records (#64, 2026-11-20) — the
/// twin's ``_parse_escaped_extended_records``.  The 2026-11-18 header law
/// reads ``ty``/``b3``/``b4`` as raw u8; the CAASdd*Stiffener gap
/// forensics measured a second header form where each of them may escape
/// via ``read_count`` (P1g: ``u8`` or ``0xff + u32le``) before the fixed
/// ``ff`` + ``u32le n``.  The +2 shape (``ty`` escaped) and the +4 shape
/// (``b4`` escaped) are invisible to the committed discovery; the +3
/// shape (``b3`` escaped) rides the committed strip-header candidates the
/// 6-byte law skips.  Everything after the header is the #62 law
/// unchanged, with ONE deliberate difference: repeats are RANKED, not
/// disqualified (the escaped records carry legitimate strip joins —
/// 114/453 loop groups on the CAASdd exact-tile records).  A candidate
/// overlapping an already accepted record is skipped, so the bytes are
/// never parsed twice.
#[allow(clippy::too_many_arguments)]
fn parse_escaped_extended_records(
    data: &[u8],
    lo: usize,
    hi: usize,
    hdrs: &[usize],
    element_count: u32,
    elements: Option<&[Element]>,
    shipped: &[ExtendedFacetRecord],
) -> (Vec<ExtendedFacetRecord>, usize) {
    // discovery: ff at +2 (ty escaped), ff at +4 (b4 escaped), and the
    // committed header candidates with an extended marker the 6-byte
    // law skipped (the b3-escaped +3 shape).
    let mut positions: Vec<usize> = Vec::new();
    let mut i = lo;
    while i + 3 <= hi {
        if data[i] == 0x01 && (data[i + 1] == 0x47 || data[i + 1] == 0x4F) && data[i + 2] == 0xFF {
            positions.push(i);
            i += 3;
        } else {
            i += 1;
        }
    }
    let mut i = lo;
    while i + 5 <= hi {
        if data[i] == 0x01 && (data[i + 1] == 0x47 || data[i + 1] == 0x4F) && data[i + 4] == 0xFF {
            positions.push(i);
            i += 5;
        } else {
            i += 1;
        }
    }
    for &h in hdrs {
        if data[h + 1] == 0x47 || data[h + 1] == 0x4F {
            let len_ok = matches!(facets::header_len(data, h), Some(len) if len != 6);
            if len_ok {
                positions.push(h);
            }
        }
    }
    positions.sort_unstable();
    positions.dedup();
    if positions.is_empty() {
        return (Vec::new(), 0);
    }
    let mut bounds: Vec<usize> = hdrs.to_vec();
    bounds.extend_from_slice(&positions);
    bounds.push(hi);
    bounds.sort_unstable();
    bounds.dedup();
    let widths: &[u8] = if element_count > 65_535 {
        &[1, 2, 3]
    } else {
        &[1, 2]
    };
    let mut records: Vec<ExtendedFacetRecord> = Vec::new();
    let mut accepted: Vec<(usize, usize)> = shipped.iter().map(|r| (r.offset, r.end)).collect();
    let mut tried = 0usize;
    for &o in &positions {
        tried += 1;
        if accepted.iter().any(|&(a, e)| a <= o && o < e) {
            continue;
        }
        let mk = data[o + 1];
        if !EXTENDED_HEADER_MARKERS.contains(&mk) {
            continue;
        }
        let Some((ty, mut p)) = read_count_checked(data, o + 2) else {
            continue;
        };
        let Some((b3, p2)) = read_count_checked(data, p) else {
            continue;
        };
        let Some((b4, p3)) = read_count_checked(data, p2) else {
            continue;
        };
        p = p3;
        if p >= hi || data[p] != 0xFF || p + 5 > hi {
            continue;
        }
        let n = u32::from_le_bytes([data[p + 1], data[p + 2], data[p + 3], data[p + 4]]);
        p += 5;
        if n > facets::MAX_REFS {
            continue;
        }
        let has_normal = EXTENDED_NORMAL_MARKERS.contains(&mk);
        let normal = if has_normal {
            if p + 12 > hi {
                continue;
            }
            let nm = Some((
                f32_widen(data, p),
                f32_widen(data, p + 4),
                f32_widen(data, p + 8),
            ));
            p += 12;
            nm
        } else {
            None
        };
        let k = b3 as usize + b4 as usize;
        if k > ESCAPED_MAX_K {
            continue;
        }
        let Some((counts, clen)) = facets::read_counts(data, p, k, hi) else {
            continue;
        };
        let refs_start = p + clen;
        let sum: u32 = counts.iter().copied().sum();
        if n != 3 * ty + sum {
            continue;
        }
        let nxt = bounds.iter().copied().find(|&b| b > o).unwrap_or(hi);
        // The ONE width vote (`vote_ref_width`); the escaped family's
        // strip joins are legitimate repeats, so they RANK (the #64
        // semantic). The OOB post-gate lives in the vote.
        let candidates = widths.iter().filter_map(|&width| {
            let end = refs_start + width as usize * n as usize;
            if end > nxt.min(hi) {
                return None;
            }
            Some(WidthCandidate {
                width,
                little: false,
                counts: counts.clone(),
                counts_end: refs_start,
                end,
                exact: end == nxt,
                tri_count: ty,
                relaxed_u16: false,
                k: 0,
            })
        });
        let Some(RefVote {
            refs, width, end, ..
        }) = vote_ref_width(data, n, candidates, element_count, normal, elements, true)
        else {
            continue;
        };
        accepted.push((o, end));
        records.push(ExtendedFacetRecord {
            offset: o,
            marker: mk,
            triangles: ty,
            strips: b3,
            polygons: b4,
            counts,
            refs,
            end,
            normal,
            width,
        });
    }
    (records, tried)
}

/// Every extended-header record in ``[lo, hi)`` under the 2026-11-18
/// law — the twin's ``composite.parse_extended_facet_records``.
///
/// Returns ``(records, candidates)``: ``candidates`` counts every
/// 6-byte-header position and ``records`` the ones the law accepts. The
/// loop count comes from the header (``b3 + b4``), never from a tiling
/// search (and the counts stay a raw u8 table — the P1g escape never
/// fires on the corpus's 12,376 candidates, #62); a candidate whose
/// refs leave the element space is NOT this family (a false-positive
/// byte pattern) and stays unresolved instead of failing the store on
/// the refs gate.
///
/// The ref width is VOTED per record (#62, 2026-11-20; the corpus probe
/// behind it measured w2 exact-tiling 2.1% vs w3 97.6% on the 19
/// declined files — the family's refs are u24be on the big-element
/// stores, while the small-space stores stay u16be): the candidates are
/// width u8/u16be (plus u24be ONLY when ``element_count > 65,535`` —
/// the threshold the short-form width law uses) ranked by exact tiling
/// first, then refs in bounds, then the loop plane law (0x4f only,
/// tested when ``elements`` is passed, on dup-pinned coordinates for
/// skip-bearing loops), then the narrower width. A candidate whose
/// parse REPEATS a reference within a triangle/loop is DISQUALIFIED
/// outright (the short-form law's misread detector: a narrow misread of
/// a wider record repeats refs inside the loop, and a legitimate record
/// never repeats). A record whose winning candidate's refs leave the
/// element space is declined as a whole, so the accepted records never
/// trip the store-level refs gate.
///
/// CAASdd*Stiffener verification (2026-11-20, the #62 fix design's
/// second probe): the CAASddEditStiffener/CreateStiffener stores carry
/// ``elem_decl`` 640, so u24be is never offered there — and their
/// 0x47/0x4f records exact-tile at NO width (only rec@4772007 and
/// rec@4772268 tile, at w2, areas 531/464 m2 inside the store's 104.6 m
/// exported-mesh bbox diag — kept, no area guard). The non-tiling
/// records' u8 misreads stay in-bounds and used to win the rank on the
/// in-bounds slot; the repeats disqualification declines them (measured
/// 50,779 m2 of km-scale garbage exported without it — the documented
/// decline: no exact tiling, area 4-60x beyond bbox_diag^2).
/// The (start, end) spans of the accepted short records — the #65
/// exact-tiling exception's overlap-guard input (twin:
/// ``_short_record_spans``). Ends are recomputed from the same
/// deterministic walk the vote used; 0x49 has no count table and its
/// law pins ``o + 20 + 2*n``.
fn short_record_spans(data: &[u8], hi: usize, records: &[CompositeRecord]) -> Vec<(usize, usize)> {
    let mut spans = Vec::with_capacity(records.len());
    for r in records {
        if r.marker == 0x49 {
            let n: u32 = r.counts.iter().copied().sum();
            spans.push((r.offset, r.offset + 20 + 2 * n as usize));
            continue;
        }
        let hlen = facets::header_len(data, r.offset).unwrap_or(4);
        let has_normal = facets::NORMAL_MARKERS_ALL.contains(&r.marker);
        let base = r.offset + hlen + 4 + if has_normal { 12 } else { 0 };
        let clen = facets::read_counts(data, base, r.counts.len(), hi)
            .map(|(_, clen)| clen)
            .unwrap_or(0);
        let n: u32 = r.counts.iter().copied().sum();
        spans.push((r.offset, base + clen + r.width as usize * n as usize));
    }
    spans
}

fn parse_extended_facet_records(
    data: &[u8],
    lo: usize,
    hi: usize,
    element_count: u32,
    elements: Option<&[Element]>,
    shipped: &[(usize, usize)],
) -> (Vec<ExtendedFacetRecord>, usize) {
    let mut records = Vec::new();
    let mut candidates = 0usize;
    let mut hdrs = facets::strip_headers(data, lo, hi);
    hdrs.extend(facets::facet_headers(data, lo, hi));
    hdrs.sort_unstable();
    let widths: &[u8] = if element_count > 65_535 {
        &[1, 2, 3]
    } else {
        &[1, 2]
    };
    // The #65 own-accept spans: an extended candidate inside an earlier
    // extended record's span is a false-positive byte pattern in its
    // refs.
    let mut accepted: Vec<(usize, usize)> = Vec::new();
    for (i, &o) in hdrs.iter().enumerate() {
        if facets::header_len(data, o) != Some(6) {
            continue;
        }
        if shipped.iter().any(|&(a, e)| a <= o && o < e)
            || accepted.iter().any(|&(a, e)| a <= o && o < e)
        {
            // #65 (2026-11-20): a candidate inside an already-accepted
            // record's span (a shipped short record, or an earlier
            // extended one) is a false-positive byte pattern in that
            // record's refs, not a record of its own.
            continue;
        }
        candidates += 1;
        let nxt = if i + 1 < hdrs.len() { hdrs[i + 1] } else { hi };
        let mk = data[o + 1];
        if !EXTENDED_HEADER_MARKERS.contains(&mk) {
            continue;
        }
        let ty = u32::from(data[o + 2]);
        let b3 = u32::from(data[o + 3]);
        let b4 = u32::from(data[o + 4]);
        let k = (b3 + b4) as usize;
        let has_normal = EXTENDED_NORMAL_MARKERS.contains(&mk);
        let base = o + 10 + if has_normal { 12 } else { 0 };
        let refs_start = base + k;
        if refs_start > hi {
            continue;
        }
        let n = u32::from_le_bytes([data[o + 6], data[o + 7], data[o + 8], data[o + 9]]);
        let normal = if has_normal {
            Some((
                f32_widen(data, o + 10),
                f32_widen(data, o + 14),
                f32_widen(data, o + 18),
            ))
        } else {
            None
        };
        // The exact-tiling boundary past the internal false positives
        // (#65): the first candidate header at or after ``end`` (hi
        // when none). An ``end`` that IS a header is an exact tile; the
        // candidates strictly inside (o, end) are the record's own ref
        // bytes (its internal STRIP_RE matches), not record boundaries.
        let nxt_eff = |end: usize| -> usize {
            let j = hdrs.partition_point(|&h| h < end);
            if j < hdrs.len() { hdrs[j] } else { hi }
        };
        // The exact-tiling exception must never swallow an
        // already-accepted record: the shipped short spans and this
        // law's own earlier accepts bound it.
        let overlaps = |end: usize| -> bool {
            shipped.iter().any(|&(a, e)| o < e && a < end)
                || accepted.iter().any(|&(a, e)| o < e && a < end)
        };
        // The #62 width vote (exact tiling, in-bounds, repeats, loop
        // plane law, narrower width). ``repeats_ranked`` is the #64
        // escaped law's semantic — repeats are legitimate strip joins
        // on the escaped-form family — so the committed u8 reading
        // keeps the misread disqualification while the #65 fallback
        // readings rank them; the emission keeps the per-record
        // ``mesh_safe`` guard either way.
        let vote = |counts: &[u32],
                    refs_start: usize,
                    repeats_ranked: bool|
         -> Option<(Vec<u32>, u8, usize, Vec<u32>)> {
            // The ONE width vote (`vote_ref_width`). ``repeats_ranked``
            // is the #64 escaped law's semantic — repeats are
            // legitimate strip joins on the escaped-form family — so
            // the committed u8 reading keeps the misread
            // disqualification while the #65 fallback readings rank
            // them; the emission keeps the per-record ``mesh_safe``
            // guard either way. The OOB post-gate lives in the vote.
            let candidates = widths.iter().filter_map(|&width| {
                let end = refs_start + width as usize * n as usize;
                if end > hi {
                    return None;
                }
                if end > nxt.min(hi) {
                    // #65: past the next candidate header only the
                    // exact-tiling exception is viable — the record ends
                    // exactly on a later candidate header, and swallows no
                    // accepted record.
                    if end != nxt_eff(end) || overlaps(end) {
                        return None;
                    }
                }
                Some(WidthCandidate {
                    width,
                    little: false,
                    counts: counts.to_vec(),
                    counts_end: refs_start,
                    end,
                    exact: end == nxt_eff(end),
                    tri_count: ty,
                    relaxed_u16: false,
                    k: 0,
                })
            });
            vote_ref_width(
                data,
                n,
                candidates,
                element_count,
                normal,
                elements,
                repeats_ranked,
            )
            .map(|won| (won.refs, won.width, won.end, counts.to_vec()))
        };
        // The counts-table reading chain (#65, 2026-11-20). The
        // committed u8 reading (the #62 law) runs first and alone on
        // every candidate it covers — every store the #62 law handled
        // keeps its exact parse. A candidate whose u8 table fails the
        // counts law retries the SAME table as P1g counts (u8 or
        // ``ff + u32le`` — the #64 encoding; the povdoigt
        // _NPart#194287 / MINI_RESSORTS gap records carry 16/211 and
        // 22/220 escaped counts and exact-tile at w2 under it), then as
        // ``k`` u16be words (the BundleSegment3 gap records: the table
        // IS 2-byte big-endian there — n-law exact at 767 = 3*18 + 713).
        // The fallback variants join with repeats RANKED and the same
        // gates (in-bounds refs, emission ``mesh_safe``).
        let counts_u8: Vec<u32> = data[base..base + k].iter().map(|&c| u32::from(c)).collect();
        let mut best = if n == 3 * ty + counts_u8.iter().copied().sum::<u32>() {
            vote(&counts_u8, base + k, false)
        } else {
            None
        };
        if best.is_none()
            && let Some((counts_p1g, clen)) = facets::read_counts(data, base, k, hi)
            && n == 3 * ty + counts_p1g.iter().copied().sum::<u32>()
        {
            best = vote(&counts_p1g, base + clen, true);
        }
        if best.is_none() && base + 2 * k <= hi {
            let counts16: Vec<u32> = (0..k)
                .map(|j| {
                    u32::from(u16::from_be_bytes([
                        data[base + 2 * j],
                        data[base + 2 * j + 1],
                    ]))
                })
                .collect();
            if n == 3 * ty + counts16.iter().copied().sum::<u32>() {
                best = vote(&counts16, base + 2 * k, true);
            }
        }
        let Some((refs, width, end, counts)) = best else {
            continue;
        };
        accepted.push((o, end));
        records.push(ExtendedFacetRecord {
            offset: o,
            marker: mk,
            triangles: ty,
            strips: b3,
            polygons: b4,
            counts,
            refs,
            end,
            normal,
            width,
        });
    }
    // #64 (2026-11-20): the P1g-escaped header form joins as a SECOND
    // pass over the same span — the 6-byte form's candidates, boundaries
    // and rank above are byte-identical to the pre-#64 behavior; the
    // escaped-form records only fill the gaps. Overlap rejection keeps
    // both passes from claiming the same bytes.
    let (escaped, escaped_candidates) =
        parse_escaped_extended_records(data, lo, hi, &hdrs, element_count, elements, &records);
    if !escaped.is_empty() {
        records.extend(escaped);
        records.sort_by_key(|r| r.offset);
    }
    (records, candidates + escaped_candidates)
}

/// Triangles under the identity mapping (strip/polygon semantics) —
/// the twin's ``_triangulate``. Loop references are 0-based element
/// indices; triangles index the WRITTEN points (the exported vertex
/// list), so referenced elements are remapped through the written
/// rank. Loops referencing skip slots (curve entries — their
/// coordinates live in the curve records, U4) are skipped and counted:
/// the dup-pin law is the one exception (per loop, behind the battery
/// and the mesh guard). Strip triangles (0x42/0x4a) skip the degenerate
/// ones (repeated coordinates or exactly-zero cross product, G3 F7);
/// polygon fans (0x4c) skip repeated coordinates. The dropped
/// curve-entry loops and the written rank ride on the result for the
/// stage-3 laws (the dup-pin evaluation and the §2.3 curve exposure).
struct Triangulation {
    /// The emitted triangles (written-rank indexed).
    triangles: Vec<(u32, u32, u32)>,
    /// The degenerate skips.
    degenerate: u32,
    /// The loop counters (the twin's ``stats`` minus ``dup_pin``).
    loops_exported: u32,
    loops_curve_entry: u32,
    /// The triangles the extended-header records emitted (the twin's
    /// ``extended_header_triangles`` counter).
    extended_triangles: u32,
    /// The extended records the manifold-assembly gate declined.
    extended_declined: u32,
    /// The degenerate member triangles the member-filter law dropped
    /// from ACCEPTED extended records (named, never counted as
    /// degenerate: the L2 degenerate rate stays 0).
    extended_members_filtered: u32,
    /// The T3 relaxed-family loops the strict guard accepted (#61).
    relaxed_loops_accepted: u32,
    /// The T3 relaxed-family loops the strict guard refused (#61).
    relaxed_loops_declined: u32,
    /// The primary-emit seam: sliver loops skipped at the primary
    /// emission (the twin's ``primary_loop_skips``).
    primary_loop_skips: u32,
    /// The primary-emit seam: over-using loops kept because each is
    /// larger than the sliver bound (the twin's ``primary_loop_kept``).
    primary_loop_kept: u32,
    /// Fase 3 L1 (#70): the relist pass's declined kept loops' triangles
    /// and counters (empty/0 outside the relist pass).
    kept_loop_tris: Vec<(u32, u32, u32)>,
    kept_loop_count: u32,
    relist_forced: u32,
    /// The per-loop dup-pin weld block.
    dup_pin: Option<DupPin>,
    /// The dropped curve-entry loops (marker, record normal, loop
    /// refs) in encounter order — the dup-pin input and the §2.3 curve
    /// exposure's raw material (pre-weld).
    dropped_loops: Vec<DroppedLoop>,
}

/// The mutable emission state shared by the short and extended records.
#[derive(Default)]
struct EmitState {
    triangles: Vec<(u32, u32, u32)>,
    degenerate: u32,
    loops_exported: u32,
    loops_curve_entry: u32,
    dropped_loops: Vec<DroppedLoop>,
    /// The incremental manifold guard over the units emitted so far
    /// (the twin's ``edge_uses`` histogram inside ``EdgeGuard``).
    guard: EdgeGuard,
    /// The primary-emit seam counters (the twin's stats keys).
    primary_loop_skips: u32,
    primary_loop_kept: u32,
    /// Fase 3 L1 (#70): the relist pass's declined kept loops' triangles
    /// (recorded for the vertex-coverage gate) and counters.
    kept_tris: Vec<(u32, u32, u32)>,
    kept_loops: u32,
    relist_forced: u32,
}

/// The shared emission context of one :fn:`triangulate` call (the
/// written rank, the skip set and the written points).
struct EmitCtx<'a> {
    written_rank: &'a HashMap<usize, usize>,
    skips: &'a HashSet<usize>,
    points: &'a [(f64, f64, f64)],
    /// Fase 3 L1 (#70): skip refused above-sliver loops at decision
    /// time (the S5 seam-max world) instead of keeping them.
    relist_skip: bool,
}

impl EmitCtx<'_> {
    /// Emit one loop (or one independent triangle, ``count_loop``
    /// false) — the twin's inner ``emit`` of ``_triangulate``.
    /// ``guard`` runs the incremental manifold guard (the primary
    /// records pass ``true``, the extended records ``false`` like the
    /// twin's inline extended walk); ``seam_area`` arms the seam
    /// (``Some`` = the store mesh area).
    #[allow(clippy::too_many_arguments)]
    fn emit(
        &self,
        st: &mut EmitState,
        kind: u8,
        normal: Option<(f64, f64, f64)>,
        loop_refs: &[u32],
        count_loop: bool,
        guard: bool,
        seam_area: Option<f64>,
    ) {
        if loop_refs.is_empty() {
            return;
        }
        if loop_refs
            .iter()
            .any(|&r| self.skips.contains(&(r as usize)))
        {
            st.loops_curve_entry += 1;
            st.dropped_loops.push((kind, normal, loop_refs.to_vec()));
            return;
        }
        if count_loop {
            st.loops_exported += 1;
        }
        let idxs: Vec<u32> = loop_refs
            .iter()
            .map(|&r| {
                u32::try_from(self.written_rank[&(r as usize)]).expect(
                    "guarded: the refs gate bounds r by the element space \
                     and the skip filter removed the unranked elements",
                )
            })
            .collect();
        let (tris, deg) = loop_triangles(kind, &idxs, self.points);
        st.degenerate += deg;
        // The primary-loop seam (2026-11-18, #34): the same incremental
        // manifold guard the weld and the extended family use, made
        // fidelity-neutral by the area rule — a refused loop is dropped
        // only when it is <= PRIMARY_LOOP_AREA_REL of the store mesh's
        // area; a larger over-use is real surface and is kept as before,
        // counted and named.
        if guard {
            let area = loop_area(&tris, self.points);
            if !st.guard.admit(&tris) {
                if let Some(reference) = seam_area
                    && area <= PRIMARY_LOOP_AREA_REL * reference
                {
                    st.primary_loop_skips += 1;
                    return;
                }
                if self.relist_skip {
                    st.relist_forced += 1;
                    st.kept_loops += 1;
                    st.kept_tris.extend(tris);
                    return;
                }
                st.primary_loop_kept += 1;
                st.guard.fold(&tris);
            }
        }
        st.triangles.extend(tris);
    }
}

fn triangulate(
    elements: &[Element],
    records: &[CompositeRecord],
    extended: &[ExtendedFacetRecord],
    seam_area: Option<f64>,
    relist_skip: bool,
) -> Triangulation {
    let mut written_rank: HashMap<usize, usize> = HashMap::new();
    let mut skips: HashSet<usize> = HashSet::new();
    for (i, (_v, pt)) in elements.iter().enumerate() {
        if pt.is_none() {
            skips.insert(i);
        } else {
            written_rank.insert(i, written_rank.len());
        }
    }
    let points: Vec<(f64, f64, f64)> = elements.iter().filter_map(|e| e.1).collect();

    let ctx = EmitCtx {
        written_rank: &written_rank,
        skips: &skips,
        points: &points,
        relist_skip,
    };
    let mut st = EmitState::default();
    for rec in records {
        if !EXPORTED_SHORT_MARKERS.contains(&rec.marker) {
            continue;
        }
        let mut o = 0usize;
        for c in &rec.counts {
            ctx.emit(
                &mut st,
                rec.marker,
                rec.normal,
                &rec.refs[o..o + *c as usize],
                true,
                true,
                seam_area,
            );
            o += *c as usize;
        }
    }
    // The extended family was the one emission outside a structural
    // check (the 2026-11-18 review: 9 carrier parts flipped to
    // not-manifold), so each record is emitted only when its triangles
    // keep the assembled mesh manifold (mesh_safe — the same lever as
    // the weld) and carry no degenerate emission. A record failing
    // either test is declined as a whole; its skip-bearing loops stay
    // dropped (never weld candidates of a declined record).
    let mut extended_triangles = 0u32;
    let mut extended_declined = 0u32;
    let mut extended_members_filtered = 0u32;
    // The extended/relaxed lineage folds into a CLONE of the primary
    // guard (the twin's shared dict reaches both passes through the
    // same histogram; the clone keeps the primary state untouched).
    let mut lineage = st.guard.clone();
    for rec in extended {
        let mut rec_st = EmitState::default();
        for j in (0..3 * rec.triangles as usize).step_by(3) {
            ctx.emit(
                &mut rec_st,
                0x42,
                rec.normal,
                &rec.refs[j..j + 3],
                false,
                false,
                None,
            );
        }
        let mut o = 3 * rec.triangles as usize;
        for (index, c) in rec.counts.iter().enumerate() {
            let kind = if index < rec.strips as usize {
                0x42
            } else {
                0x4C
            };
            ctx.emit(
                &mut rec_st,
                kind,
                rec.normal,
                &rec.refs[o..o + *c as usize],
                true,
                false,
                None,
            );
            o += *c as usize;
        }
        // The member-filter law (2026-11-21, the Audi R8 forensics):
        // a record WITHOUT degenerate members keeps the committed law
        // verbatim — the valid remainder (possibly EMPTY: an
        // all-skip-bearing record contributes nothing itself but its
        // dropped loops stay weld candidates) passes the incremental
        // guard.  A record WITH degenerate members has them FILTERED
        // and named (``extended_members_filtered``) instead of
        // declining the record whole — its valid siblings still emit
        // behind the same guard, and the skips never count as
        // degenerate (the L2 gate's degenerate-triangle rate stays 0);
        // the valid remainder must be non-empty and guard-passing,
        // else the record is declined as a whole exactly as before.
        let accepted = if rec_st.degenerate == 0 {
            lineage.admit(&rec_st.triangles)
        } else {
            extended_members_filtered += rec_st.degenerate;
            !rec_st.triangles.is_empty() && lineage.admit(&rec_st.triangles)
        };
        if accepted {
            extended_triangles += rec_st.triangles.len() as u32;
            st.triangles.extend(rec_st.triangles);
            st.loops_exported += rec_st.loops_exported;
            st.loops_curve_entry += rec_st.loops_curve_entry;
            st.dropped_loops.extend(rec_st.dropped_loops);
        } else {
            extended_declined += 1;
            st.loops_curve_entry += rec_st.loops_curve_entry;
        }
    }
    // The T3 relaxed families (#61): a SECOND pass over the same
    // records, so the base pass's outcome is bit-identical to the
    // pre-T3 behavior (the relaxed loops never touch the base pass's
    // edge budget).  Each relaxed loop enters only under the STRICT
    // mesh guard — no seam-area exception — so every fold keeps every
    // edge at <= 2 uses and a base-manifold mesh stays manifold by
    // construction.  The `edge_uses` histogram carries the accepted
    // extended records' folds, like the Python twin's dict.
    let mut relaxed_accepted = 0u32;
    let mut relaxed_declined = 0u32;
    for rec in records {
        if !RELAXED_SHORT_MARKERS.contains(&rec.marker) {
            continue;
        }
        let mut o = 0usize;
        for c in &rec.counts {
            let loop_refs = &rec.refs[o..o + *c as usize];
            o += *c as usize;
            if loop_refs.is_empty() {
                continue;
            }
            if loop_refs.iter().any(|&r| skips.contains(&(r as usize))) {
                st.loops_curve_entry += 1;
                st.dropped_loops
                    .push((rec.marker, rec.normal, loop_refs.to_vec()));
                continue;
            }
            st.loops_exported += 1;
            let idxs: Vec<u32> = loop_refs
                .iter()
                .map(|&r| {
                    u32::try_from(written_rank[&(r as usize)]).expect(
                        "guarded: the refs gate bounds r by the element space \
                         and the skip filter removed the unranked elements",
                    )
                })
                .collect();
            let (tris, deg) = loop_triangles(rec.marker, &idxs, &points);
            if deg != 0 {
                // The extended-family precondition: a loop carrying a
                // degenerate emission is declined WHOLE and its skip is
                // never counted (the twin's comment on the L2 law).
                relaxed_declined += 1;
                continue;
            }
            if lineage.admit(&tris) {
                st.triangles.extend(tris);
                relaxed_accepted += 1;
            } else {
                relaxed_declined += 1;
            }
        }
    }
    // The per-loop dup-pin weld: evaluate every dropped loop when any
    // exists (the 2026-11-18 surface-loss fix — no empty-mesh
    // precondition; each loop is welded behind the battery + mesh
    // guard independently).
    let dup_pin = if !st.dropped_loops.is_empty() {
        Some(e0b_dup_pin(
            elements,
            &points,
            &written_rank,
            &st.dropped_loops,
            &st.triangles,
        ))
    } else {
        None
    };
    Triangulation {
        triangles: st.triangles,
        degenerate: st.degenerate,
        loops_exported: st.loops_exported,
        loops_curve_entry: st.loops_curve_entry,
        extended_triangles,
        extended_declined,
        extended_members_filtered,
        relaxed_loops_accepted: relaxed_accepted,
        relaxed_loops_declined: relaxed_declined,
        primary_loop_skips: st.primary_loop_skips,
        primary_loop_kept: st.primary_loop_kept,
        kept_loop_tris: st.kept_tris,
        kept_loop_count: st.kept_loops,
        relist_forced: st.relist_forced,
        dup_pin,
        dropped_loops: st.dropped_loops,
    }
}

/// Every token-bearing list node in ``[lo, hi)`` (stage-4b scan) —
/// the twin's ``_scan_token_nodes``. Returns each node's position and
/// payload range in body order — unlike :fn:`find_list_node` (largest
/// payload BEFORE the first strip header — the stage-3d single-rep
/// window), this scans the whole body: on multi-rep stores the k-th
/// rep's node sits after the previous rep's records.
struct TokenNode {
    /// The NODE_MAGIC position (absolute).
    pos: usize,
    /// The payload range (absolute).
    plo: usize,
    phi: usize,
    /// The declared element count.
    elem: u32,
    /// The declared edge-ref bound (unused by the laws, kept for
    /// fidelity with the twin's tuple).
    #[allow(dead_code)]
    edge_bound: u32,
}

fn scan_token_nodes(data: &[u8], lo: usize, hi: usize) -> Vec<TokenNode> {
    let mut nodes = Vec::new();
    let mut pos = lo;
    while let Some(at) = find(data, NODE_MAGIC, pos, hi) {
        let end = match find(data, NODE_MAGIC, at + 4, hi) {
            Some(e) => e,
            None => hi,
        };
        let (plo, phi) = (at + 4, end);
        let payload = &data[plo..phi];
        if let Some(tok) = find(payload, LIST_TOKEN, 0, payload.len())
            && tok <= 64
        {
            let p = tok + 5;
            // The twin catches (IndexError, struct.error) around
            // BOTH reads — an unreadable count skips the node.
            let first = read_count_checked(payload, p);
            let second = first.and_then(|(_, p2)| read_count_checked(payload, p2));
            if let (Some((c1, _)), Some((c2, _))) = (first, second)
                && 0 < c1
                && c1 <= MAX_ELEMENT_COUNT
            {
                nodes.push(TokenNode {
                    pos: at,
                    plo,
                    phi,
                    elem: c1,
                    edge_bound: c2,
                });
            }
        }
        pos = at + 1;
    }
    nodes
}

/// Pair each pool group with its rep node — the twin's
/// ``_rep_node_positions`` (2026-11-18, #50 B3). The measured corpus
/// law: the pool wrapper FOLLOWS its rep's list node, so the rep node
/// is the last token-bearing list node before the group's wrapper
/// (2,175 groups across 1,036 composite stores, all with a preceding
/// node; the preceding node absorbs 2,149, and the first node after
/// the wrapper absorbs only 2 of 1,186 — both times the preceding node
/// absorbs too, so "after" is never the reading). A node already
/// claimed by an earlier group cannot re-list a second pool: the later
/// group gets ``None`` (ambiguous → fail-closed).
fn rep_node_positions(nodes: &[TokenNode], groups: &[PoolGroup]) -> Vec<Option<usize>> {
    let order: Vec<usize> = nodes.iter().map(|n| n.pos).collect();
    let mut claimed: HashSet<usize> = HashSet::new();
    let mut positions = Vec::with_capacity(groups.len());
    for g in groups {
        let node = order.iter().rev().find(|&&p| p < g.offset).copied();
        let node = match node {
            Some(n) if !claimed.contains(&n) => {
                claimed.insert(n);
                Some(n)
            }
            _ => None,
        };
        positions.push(node);
    }
    positions
}

/// Noise-aware re-listing test — the twin's ``_tol_match``: some
/// written point matches ``v`` within :const:`NOISE_REL` per
/// coordinate; returns the best (smallest) relative delta, or
/// ``None`` when ``pts`` is empty. The scale is the twin's exact
/// ``max(1.0, abs(...), abs(...), abs(...))`` expression.
fn tol_match(v: (f64, f64, f64), pts: &[(f64, f64, f64)]) -> Option<f64> {
    let scale = 1.0f64.max(v.0.abs()).max(v.1.abs()).max(v.2.abs());
    let mut best: Option<f64> = None;
    for p in pts {
        let d = ((p.0 - v.0).abs() / scale)
            .max((p.1 - v.1).abs() / scale)
            .max((p.2 - v.2).abs() / scale);
        if best.is_none_or(|b| d < b) {
            best = Some(d);
        }
    }
    best
}

/// One law-decoded rep of the per-rep decomposition (the twin's
/// ``decoded`` dict entries).
struct DecodedRep {
    /// The NODE_MAGIC position (absolute).
    pos: usize,
    /// The payload byte length (the twin's ``len(payload)``).
    payload_len: usize,
    /// The declared element count.
    elem: u32,
    /// The decoded element space.
    elements: Vec<Element>,
    /// The written points in region order.
    pts: Vec<(f64, f64, f64)>,
    /// Absolute end of the point region (the territory start).
    region_end: usize,
    /// The rep's declared write count.
    write_count: u32,
    /// The rep's table byte length.
    table_bytes: usize,
}

/// One rep node's reading — the twin's ``_decode_rep_node`` record
/// (2026-11-18, #50 B3).
struct RepNodeReading {
    elements: Vec<Element>,
    pts: Vec<(f64, f64, f64)>,
    /// End of the point region, relative to the payload start (the
    /// record territory opens here).
    region_end_rel: usize,
    write_count: u32,
    table_bytes: usize,
}

/// One rep node under the per-rep law ladder — the twin's
/// ``_decode_rep_node`` (2026-11-18, #50 B3): the committed table
/// layout first, then the stage-8 law set (extent table, raw, flat)
/// with the rep's OWN pool group as the flat law's absorption
/// reference. ``None`` when no law decodes the node.
fn decode_rep_node(
    payload: &[u8],
    element_count: u32,
    poolv: &[(f64, f64, f64)],
) -> Option<RepNodeReading> {
    if let Ok((elements, info)) = decode_region(payload, element_count) {
        let pts: Vec<(f64, f64, f64)> = elements.iter().filter_map(|e| e.1).collect();
        return Some(RepNodeReading {
            elements,
            pts,
            region_end_rel: info.walk_end,
            write_count: info.write_count,
            table_bytes: info.table_bytes,
        });
    }
    let counts_end = token_counts_end(payload)?;
    let nd = decode_node_mixedwrite(payload, element_count, counts_end, poolv);
    let law = nd.law?;
    #[allow(clippy::manual_div_ceil)]
    let table_bytes = if law == "table" {
        (element_count as usize + 3) / 4
    } else {
        0
    };
    Some(RepNodeReading {
        elements: nd.elements,
        pts: nd.pts,
        region_end_rel: nd.region_end_rel,
        write_count: nd.write_count as u32,
        table_bytes,
    })
}

/// The sequence-of-reps reading (stage-4b per-rep law, stage-5
/// integration) — the twin's ``_decode_per_rep``. Rep k = (pool group
/// k, the token node immediately preceding that group, that node's
/// record territory ``[region_end_k, next token node)``); the k-th
/// pool re-lists verbatim
/// (or within :const:`NOISE_REL`) in the k-th rep's region. A rep
/// exports only when its pool absorbs and its gated references
/// resolve in-bounds against its OWN element count; failing reps stay
/// unexported with the reason named. When no rep exports, raises the
/// stage-3d ``unabsorbed`` classification with the per-rep residue
/// named (fail-closed, no guessing).
#[allow(clippy::too_many_arguments)]
fn decode_per_rep(
    data: &[u8],
    lo: usize,
    hi: usize,
    groups: &[PoolGroup],
    n_missing: usize,
    n_pool: usize,
    seam_area: Option<f64>,
    relist_skip: bool,
) -> Result<CompositeDecode, ExportError> {
    let nodes = scan_token_nodes(data, lo, hi);
    let rep_nodes = rep_node_positions(&nodes, groups);
    // A paired node's flat law is gated on its OWN group's vertices;
    // an unpaired node decodes against no pool.
    let mut pool_by_node: HashMap<usize, usize> = HashMap::new();
    for (gi, node) in rep_nodes.iter().enumerate() {
        if let Some(n) = node {
            pool_by_node.entry(*n).or_insert(gi);
        }
    }
    let mut decoded: HashMap<usize, DecodedRep> = HashMap::new();
    let mut node_failures: Vec<String> = Vec::new();
    for node in &nodes {
        let payload = &data[node.plo..node.phi];
        let poolv: &[(f64, f64, f64)] = match pool_by_node.get(&node.pos) {
            Some(&gi) => &groups[gi].vertices,
            None => &[],
        };
        let Some(reading) = decode_rep_node(payload, node.elem, poolv) else {
            node_failures.push(format!("node@{}: undecoded", node.pos));
            continue;
        };
        decoded.insert(
            node.pos,
            DecodedRep {
                pos: node.pos,
                payload_len: node.phi - node.plo,
                elem: node.elem,
                elements: reading.elements,
                pts: reading.pts,
                // absolute end of the point region (the territory start)
                region_end: node.pos + 4 + reading.region_end_rel,
                write_count: reading.write_count,
                table_bytes: reading.table_bytes,
            },
        );
    }
    if decoded.is_empty() {
        return Err(ExportError::new(
            UNDECODED_VARIANT,
            format!(
                "node list does not re-list the pool: {n_missing} of \
                 {n_pool} pool vertices absent from the decoded point \
                 region (unabsorbed variant; the per-rep decomposition \
                 decodes no rep node under the table, extent, raw or \
                 flat law either: {})",
                if node_failures.is_empty() {
                    "no nodes".to_string()
                } else {
                    node_failures[..node_failures.len().min(2)].join("; ")
                }
            ),
        ));
    }
    let positions: Vec<usize> = nodes.iter().map(|n| n.pos).collect();
    let mut points: Vec<(f64, f64, f64)> = Vec::new();
    let mut triangles: Vec<(u32, u32, u32)> = Vec::new();
    let mut degenerate = 0u32;
    let mut loops_exported = 0u32;
    let mut loops_curve_entry = 0u32;
    let mut skipped_markers: BTreeMap<u8, u32> = BTreeMap::new();
    let mut facet_candidates = 0usize;
    let mut facet_records = 0usize;
    // N1 (2026-11-18 review): the per-rep paths export the extended
    // family too, so the summary must name it like the single-rep path.
    let mut ext_records = 0usize;
    let mut ext_triangles = 0usize;
    let mut ext_declined = 0usize;
    let mut ext_filtered = 0usize;
    // The primary-emit seam counters (per rep; summed at store level).
    let mut primary_loop_skips = 0u32;
    let mut relaxed_loops_accepted = 0u32;
    let mut relaxed_loops_declined = 0u32;
    let mut primary_loop_kept = 0u32;
    let mut write_count = 0usize;
    let mut table_bytes = 0usize;
    let mut element_decl = 0usize;
    let mut curve_entries = 0usize;
    let node_bytes: usize = decoded.values().map(|d| d.payload_len).sum();
    let mut reps_unexported: Vec<String> = Vec::new();
    let mut reps_dup_pin: Vec<(usize, DupPin)> = Vec::new();
    let mut kept_loop_tris: Vec<(u32, u32, u32)> = Vec::new();
    let mut kept_loop_count = 0u32;
    let mut relist_forced_total = 0u32;
    let mut curves: Vec<Vec<(f64, f64, f64)>> = Vec::new();
    let mut space_offsets: Vec<usize> = Vec::new();
    let mut reps_decoded = 0usize;
    let mut reps_exported = 0usize;
    for (k, group) in groups.iter().enumerate() {
        let Some(node_pos) = rep_nodes[k] else {
            reps_unexported.push(format!(
                "rep {k}: no token node precedes pool group {k} \
                 (the group's rep node is missing or ambiguous; per-rep \
                 absorption not established)"
            ));
            continue;
        };
        let Some(d) = decoded.get(&node_pos) else {
            reps_unexported.push(format!(
                "rep {k}: the token node at {node_pos} has no region under \
                 the committed table layout or the stage-8 extent/raw/\
                 flat laws (its pool group stays unexported)"
            ));
            continue;
        };
        reps_decoded += 1;
        let gv = &group.vertices;
        // distinct pool vertices (the twin's set(gv); -0.0/0.0 one
        // element, per :fn:`vkey`)
        let mut seen: HashSet<(u64, u64, u64)> = HashSet::new();
        let mut distinct_vals: Vec<(f64, f64, f64)> = Vec::new();
        for &v in gv {
            if seen.insert(vkey(v)) {
                distinct_vals.push(v);
            }
        }
        let pts_set: HashSet<(u64, u64, u64)> = d.pts.iter().copied().map(vkey).collect();
        let mut unmatched: Vec<(f64, f64, f64)> = distinct_vals
            .iter()
            .copied()
            .filter(|v| !pts_set.contains(&vkey(*v)))
            .collect();
        if !unmatched.is_empty() {
            // noise-aware absorption (stage-4b R3): the verbatim
            // misses may be double-rounding re-listings
            unmatched.retain(|v| match tol_match(*v, &d.pts) {
                None => true,
                Some(best) => best > NOISE_REL,
            });
        }
        if !unmatched.is_empty() {
            reps_unexported.push(format!(
                "rep {k}: pool group {k} not re-listed \
                 ({} of {} vertices absent \
                 from the rep's region; per-rep absorption not \
                 established)",
                unmatched.len(),
                distinct_vals.len()
            ));
            continue;
        }
        let nxt = positions
            .iter()
            .copied()
            .filter(|&p| p > d.pos)
            .min()
            .unwrap_or(hi);
        let (records, n_hdrs) =
            parse_strip_records(data, d.region_end, nxt, d.elem, Some(&d.elements));
        let (ext_k, ext_cands) = parse_extended_facet_records(
            data,
            d.region_end,
            nxt,
            d.elem,
            Some(&d.elements),
            &short_record_spans(data, nxt, &records),
        );
        let mut grefs: Vec<u32> = records
            .iter()
            .filter(|r| GATED.contains(&r.marker))
            .flat_map(|r| r.refs.iter().copied())
            .collect();
        grefs.extend(ext_k.iter().flat_map(|r| r.refs.iter().copied()));
        if let Some(&mx) = grefs.iter().max()
            && mx >= d.elem
        {
            reps_unexported.push(format!(
                "rep {k}: facet references beyond the rep's element \
                 space (max ref {mx} >= element count {}, \
                 M2b identity per rep)",
                d.elem
            ));
            continue;
        }
        let base = points.len();
        space_offsets.push(base);
        let tri_res = triangulate(&d.elements, &records, &ext_k, seam_area, relist_skip);
        // The per-loop dup-pin weld (2026-11-18): the rep's dropped
        // loops were evaluated independently (pinnable + battery +
        // mesh guard). The welded ones merge at the store level below
        // with this rep's point offset; refused loops stay counted as
        // dropped.
        if let Some(dp) = &tri_res.dup_pin {
            reps_dup_pin.push((base, dp.clone()));
        }
        points.extend(d.pts.iter().copied());
        triangles.extend(
            tri_res
                .triangles
                .iter()
                .map(|&(a, b, c)| (a + base as u32, b + base as u32, c + base as u32)),
        );
        degenerate += tri_res.degenerate;
        loops_exported += tri_res.loops_exported;
        loops_curve_entry += tri_res.loops_curve_entry;
        primary_loop_skips += tri_res.primary_loop_skips;
        primary_loop_kept += tri_res.primary_loop_kept;
        if !tri_res.kept_loop_tris.is_empty() {
            for &(a, b, c) in &tri_res.kept_loop_tris {
                kept_loop_tris.push((a + base as u32, b + base as u32, c + base as u32));
            }
            kept_loop_count += tri_res.kept_loop_count;
            relist_forced_total += tri_res.relist_forced;
        }
        relaxed_loops_accepted += tri_res.relaxed_loops_accepted;
        relaxed_loops_declined += tri_res.relaxed_loops_declined;
        // The §2.3 curve exposure: this exported rep's dropped loops'
        // pre-weld sequences (additive, outside Fidelity).
        for (_mk, _normal, loop_refs) in &tri_res.dropped_loops {
            curves.push(curve_sequence(loop_refs, &d.elements));
        }
        facet_candidates += n_hdrs + ext_cands;
        facet_records += records.len() + ext_k.len();
        ext_records += ext_k.len();
        ext_triangles += tri_res.extended_triangles as usize;
        ext_filtered += tri_res.extended_members_filtered as usize;
        ext_declined += tri_res.extended_declined as usize;
        write_count += d.write_count as usize;
        table_bytes += d.table_bytes;
        element_decl += d.elem as usize;
        curve_entries += d.elements.len() - d.pts.len();
        reps_exported += 1;
        for rec in &records {
            if !EXPORTED_SHORT_MARKERS.contains(&rec.marker)
                && !RELAXED_SHORT_MARKERS.contains(&rec.marker)
            {
                *skipped_markers.entry(rec.marker).or_insert(0) += 1;
            }
        }
    }
    if points.is_empty() {
        return Err(ExportError::new(
            UNDECODED_VARIANT,
            format!(
                "node list does not re-list the pool: {n_missing} of \
                 {n_pool} pool vertices absent from the decoded point \
                 region (unabsorbed variant; the per-rep decomposition \
                 exports no rep: {})",
                if reps_unexported.is_empty() {
                    "no reps".to_string()
                } else {
                    reps_unexported.join("; ")
                }
            ),
        ));
    }
    // The dup-pin weld at the store level (2026-11-18, per loop):
    // every rep's dropped loops were evaluated independently; merge
    // each rep's welded loops with its point offset. A rep whose loops
    // the battery/guard refused contributes none — its loops stay in
    // ``loops_curve_entry``.
    let mut curve_entry_law = 0u32;
    for (b, dp) in &reps_dup_pin {
        if dp.loops == 0 {
            continue;
        }
        triangles.extend(
            dp.triangles
                .iter()
                .map(|&(a, s, t)| (a + *b as u32, s + *b as u32, t + *b as u32)),
        );
        degenerate += dp.degenerate;
        loops_exported += dp.loops;
        loops_curve_entry -= dp.loops;
        curve_entry_law += dp.loops;
    }
    let mut info = CompositeInfo {
        primary_loop_relist_skips: None,
        primary_loop_relist_boundary: None,
        stage: "identity-per-rep",
        element_decl,
        node_points: points.len(),
        curve_entries,
        write_count: Some(write_count),
        table_bytes: Some(table_bytes),
        facet_candidates,
        facet_records,
        skipped_markers,
        node_bytes,
        reps_decoded: Some(reps_decoded),
        reps_exported: Some(reps_exported),
        reps_unexported: Some(reps_unexported.len()),
        rep_reasons: Some(reps_unexported),
        rep_laws: None,
        raw_start: None,
        raw_nice_rate: None,
        raw_x_asc_rate: None,
        raw_trail_bytes: None,
        raw_count3: None,
        loops_exported,
        loops_curve_entry,
        extended_header_records: None,
        extended_header_triangles: None,
        extended_header_declined: None,
        extended_members_filtered: None,
        curve_entry_law: None,
        loops_curve_entry_exported: None,
        primary_loop_skips: None,
        relaxed_loops_accepted: None,
        relaxed_loops_declined: None,
        primary_loop_seam_declined: None,
        primary_loop_kept: None,
        unordered_dedup_dropped: None,
        unordered_dedup_declined: None,
        multiregion_reps: None,
        multiregion_extent_reps: None,
        multiregion_container_reps: None,
        multiregion_declined: None,
    };
    if ext_records > 0 {
        info.extended_header_records = Some(ext_records);
        info.extended_header_triangles = Some(ext_triangles);
        if ext_declined > 0 {
            info.extended_header_declined = Some(ext_declined);
        }
        if ext_filtered > 0 {
            info.extended_members_filtered = Some(ext_filtered);
        }
    }
    if primary_loop_skips > 0 {
        info.primary_loop_skips = Some(primary_loop_skips);
    }
    if primary_loop_kept > 0 {
        info.primary_loop_kept = Some(primary_loop_kept);
    }
    if relaxed_loops_accepted > 0 || relaxed_loops_declined > 0 {
        // the twin emits BOTH keys whenever either counter is nonzero
        info.relaxed_loops_accepted = Some(relaxed_loops_accepted);
        info.relaxed_loops_declined = Some(relaxed_loops_declined);
    }
    if curve_entry_law > 0 {
        info.curve_entry_law = Some("e0b-dup-pin");
        info.loops_curve_entry_exported = Some(curve_entry_law);
    }
    // The disjoint per-rep index spaces, in emission order: the
    // stage-15 dedup's keeper rule (the earliest unit wins) needs them
    // at the assembled mesh, where a rep's re-listing of an earlier
    // rep's facet is visible by COORDINATE identity (the entry point
    // applies the law to the mesh the store actually exports).
    Ok(CompositeDecode {
        kept_loop_tris,
        kept_loop_count,
        relist_forced: relist_forced_total,
        points,
        triangles,
        degenerate,
        info,
        curves,
        space_offsets,
    })
}

// The emission guards moved to `super::mesh` (`EdgeGuard` — the ONE
// topology lever behind the weld, the extended records, the relaxed
// loops and the primary seam — plus `triangle_area` / `loop_area` /
// `mesh_area`), and the dup-pin targets and plane battery to
// `super::vote`; they are imported above under their historical
// semantics (twin: the composite.py guard/vote split).

/// The per-loop dup-pin weld behind the battery and mesh guard — the
/// twin's ``_e0b_dup_pin`` (2026-11-18; the curve-entry coordinate
/// law). Ported from the stage-4a decoder's ``dup_prev``, not
/// re-derived: a loop-referenced skip slot carries the bit-exact
/// coordinates of the written vertex of its immediately preceding
/// written element (the per-face copy — no new vertices).
///
/// Each dropped loop is welded independently when it is (1) fully
/// pinnable, (2) battery-supported (record normal absent, or the
/// dup-pinned coordinates coplanar against it at :const:`PLANE_TOL`),
/// and (3) mesh-safe: no degenerate emission and no undirected edge
/// pushed past two uses in the assembled mesh (``base_triangles`` is
/// the primary mesh already emitted by this call; accepted welds are
/// folded into the histogram as they go). The guard is incremental —
/// O(the loop's triangles) per loop — and fail-closed: a rejected loop
/// leaves the histogram untouched and stays dropped. Refused loops do
/// not veto another loop's weld.
fn e0b_dup_pin(
    elements: &[Element],
    points: &[(f64, f64, f64)],
    written_rank: &HashMap<usize, usize>,
    dropped: &[DroppedLoop],
    base_triangles: &[(u32, u32, u32)],
) -> DupPin {
    let skips: HashSet<usize> = elements
        .iter()
        .enumerate()
        .filter(|(_, (_, pt))| pt.is_none())
        .map(|(i, _)| i)
        .collect();
    let mut welds: Vec<(u32, u32, u32)> = Vec::new();
    let mut degenerate = 0u32;
    let mut welded = 0u32;
    let mut refused = 0u32;
    let mut guard = EdgeGuard::from_triangles(base_triangles);
    for (mk, normal, loop_refs) in dropped {
        let Some(pin) = dup_pin_map(elements, &skips, loop_refs) else {
            refused += 1;
            continue;
        };
        let resolved: Vec<u32> = loop_refs
            .iter()
            .map(|&r| pin.get(&r).copied().unwrap_or(r))
            .collect();
        if let Some(nm) = normal {
            let (status, _dev) = loop_plane_status(&resolved, *nm, elements);
            if status != "coplanar" {
                refused += 1;
                continue;
            }
        }
        let idxs: Vec<u32> = resolved
            .iter()
            .map(|&r| {
                u32::try_from(written_rank[&(r as usize)]).expect(
                    "guarded: the pin targets and non-skip refs are all \
                     written elements (ranked in the caller)",
                )
            })
            .collect();
        let (mut tris, mut deg) = loop_triangles(*mk, &idxs, points);
        if deg > 0 {
            // W16 A4 (2026-11-22): a degenerate emission is the
            // writer's degenerate-quad convention, not a coordinate
            // failure — the loop's dup pins are battery-TRUE, so the
            // collapsed triangles split off (the G3 F7 skip convention
            // the primary strips apply) and the real remainder still
            // faces the mesh guard.  The split-off count joins the
            // store's degenerate count.  A loop whose every triangle
            // collapses has nothing real to weld and stays dropped.
            let (real, deg2, _degen_tris) = loop_triangles_split(*mk, &idxs, points);
            tris = real;
            deg = deg2;
            if tris.is_empty() {
                refused += 1;
                continue;
            }
        }
        if !guard.admit(&tris) {
            refused += 1;
            continue;
        }
        welds.extend(tris);
        degenerate += deg;
        welded += 1;
    }
    DupPin {
        triangles: welds,
        degenerate,
        loops: welded,
        refused,
    }
}

/// The unordered-triangle dedup at one store's assembled mesh — the
/// twin's ``_apply_unordered_dedup`` (stage 15, 2026-11-13, #34; the
/// stage-14 review F1 family, owner-authorized; COORDINATE identity
/// across the disjoint per-rep element spaces added 2026-11-18, #34).
///
/// The mechanism (review F1, byte-verified): the same three ELEMENT
/// indices emitted twice — from two different records 13-42 B apart in
/// the same rep, from two loops of one record, or from two records in
/// the same order — the writer re-listed the facet; territory overlap
/// 0 (two parses never). The second copy's winding is opposite (the
/// plane normals are exact opposites), so the pair over-uses nothing
/// TOGETHER — each shared edge is used once per copy — but every edge
/// shared with the surrounding mesh counts the extra use, and the
/// corpus stores' over-edges resolve when the later copy is dropped.
///
/// The identity is COORDINATE identity (2026-11-18): two triangles are
/// the same facet when their three VERTEX POSITIONS are identical as an
/// unordered triple. An index triple is only a same-rep spelling — the
/// per-rep decomposition keeps each rep's element space disjoint, so a
/// rep that re-lists an earlier rep's facet necessarily writes
/// DIFFERENT indices for it (545707b9: 67 index duplicates in one rep
/// plus 451 coordinate duplicates re-listed by a later rep). Coordinate
/// identity is also what makes the drop AREA-PRESERVING by
/// construction: a triangle's area is a pure function of its three
/// vertex positions, so a dropped copy can never remove surface the
/// kept copy does not already carry.
///
/// The keeper is the copy from the EARLIEST emission unit: the
/// rep-space rank of its first vertex (``space_offsets`` — ties by list
/// order). A rep's welded loops (dup-pin) carry that rep's point base,
/// so they belong to that rep's unit even though they are appended
/// after every rep's primary loops; the earlier rep's listing therefore
/// always wins over a later rep's re-listing.
///
/// Fail-closed fire gate (the law applies ONLY where it resolves the
/// store's over-use): the emitted mesh must be NOT manifold (an
/// over-use) AND the deduplicated list must be manifold. A manifold
/// (passing) store is never touched — its row must not change; a
/// not-manifold store whose duplicates do NOT resolve the over-use
/// keeps its exact emitted triangles (the L2 gate names not-manifold)
/// and the declined dedup is named on the summary. Degenerate
/// triangles never enter the dedup (skipped at emission and counted
/// separately); a repeated-index triple is never deduped regardless.
///
/// Records the outcome on ``info``: ``unordered_dedup_dropped`` (fired:
/// N later duplicate copies dropped, the mesh is manifold) or
/// ``unordered_dedup_declined`` (fired and declined: N duplicates
/// found, removal leaves the mesh not-manifold, the emitted list is
/// kept verbatim).
fn apply_unordered_dedup(
    triangles: Vec<(u32, u32, u32)>,
    info: &mut CompositeInfo,
    points: &[(f64, f64, f64)],
    space_offsets: &[usize],
) -> Vec<(u32, u32, u32)> {
    /// One triangle's canonical coordinate key: its three vertex keys,
    /// sorted (the twin's ``tuple(sorted(points[i] for i in tri))``).
    type CoordKey = [(u64, u64, u64); 3];
    if triangles.len() < 2 || mesh::mesh_stats(&triangles).manifold {
        return triangles;
    }
    // Coordinate keys (``vkey``: exact f64 bits, -0.0 collapsed to
    // 0.0, the twin's float equality), canonicalized by sorting the
    // three vertex keys.
    let mut keyed: Vec<Option<CoordKey>> = Vec::with_capacity(triangles.len());
    // Best (space rank, position) per coordinate key.
    let mut best: HashMap<CoordKey, (usize, usize)> = HashMap::new();
    for (pos, tri) in triangles.iter().enumerate() {
        if tri.0 == tri.1 || tri.1 == tri.2 || tri.0 == tri.2 {
            keyed.push(None); // degenerate-shaped: never deduped
            continue;
        }
        let rank = match space_offsets {
            [] => 0usize,
            offsets => {
                let first = tri.0.min(tri.1).min(tri.2) as usize;
                offsets.partition_point(|&start| start <= first) - 1
            }
        };
        let mut key = [
            vkey(points[tri.0 as usize]),
            vkey(points[tri.1 as usize]),
            vkey(points[tri.2 as usize]),
        ];
        key.sort_unstable();
        keyed.push(Some(key));
        match best.get(&key) {
            Some(existing) if *existing <= (rank, pos) => {}
            _ => {
                best.insert(key, (rank, pos));
            }
        }
    }
    let keep: HashSet<usize> = best.values().map(|&(_rank, pos)| pos).collect();
    let kept: Vec<(u32, u32, u32)> = triangles
        .iter()
        .enumerate()
        .filter(|(pos, _tri)| keyed[*pos].is_none() || keep.contains(pos))
        .map(|(_pos, tri)| *tri)
        .collect();
    let dropped = (triangles.len() - kept.len()) as u32;
    if dropped == 0 {
        return triangles;
    }
    if mesh::mesh_stats(&kept).manifold {
        info.unordered_dedup_dropped = Some(dropped);
        return kept;
    }
    // The duplicates do not explain the over-use (fins/coplanar
    // residue alongside): fail-closed — keep the emitted list, name
    // the gap.
    info.unordered_dedup_declined = Some(dropped);
    triangles
}

// --- stage 3: the §2.3 curve exposure for the viewer's overlay ----------
//
// SPEC BOUNDARY (docs/specs/phase5-viewer-spec.md §2.3, pinned): the
// curve-entry point sequences are ADDITIVE and NOT part of the
// Fidelity definition. The Python reference has no counterpart
// artifact (the curve-entry laws land the loops either unexported or
// dup-pinned *into the mesh*; the overlay shows the pre-weld decoded
// point sequences) — nothing here is compared by the harness, and no
// ``curves`` key may enter the summary JSON or the PLY (that would
// silently widen the §3.2 diff). The artifact exists for the V4 WASM
// boundary (``decode_export``'s ``curves: Array<Float32Array>``);
// V4 converts these widened f64 values to the boundary's f32 arrays.
//
// Reading (pinned here): the pre-weld decoded point sequence of one
// dropped curve-entry loop = the loop's WRITTEN elements' coordinates
// in loop order (repeats kept). A skip slot contributes nothing — its
// coordinates live in the curve records (U4, open; risk 9 pins
// re-decoding the ``33 3X``/polyline-table families OUT of this
// phase), and the dup-pin weld is a MESH law, never applied to the
// overlay's sequences (spec §2.3: "the overlay shows the pre-weld
// decoded point sequences").
fn curve_sequence(loop_refs: &[u32], elements: &[Element]) -> Vec<(f64, f64, f64)> {
    loop_refs
        .iter()
        .filter_map(|&r| elements[r as usize].1)
        .collect()
}

/// The multi-region second-chance reading (W1-B, 2026-11-22; twin:
/// ``_decode_multiregion``).
///
/// The single-rep reading resolves EVERY record of the body against the
/// FIRST token node's region (``find_list_node`` — the largest
/// payload).  On a multi-period body that misresolves every period
/// after the first: each period carries its OWN token node with its
/// OWN element region, and the periods' records share one byte
/// topology, so the misresolved facets are identical index triples
/// over the wrong vertices.  Byte evidence (MB-Frames-middle-centr-YL):
/// 50 walk-exact token nodes (payloads 7,803 B, elem_decl
/// 658/676/679/682), the k-th node's first written point at
/// x = 1646.04 + 120k — a row of frame panels; the single-rep reading
/// exports 40,893 triangles of which 38,873 are unordered duplicates
/// (the dedup declines: the unique mesh still carries 368 over-edges);
/// the multi-region reading merges 50 reps (each manifold) into
/// 33,925 points / 50,423 triangles / 0 degenerate / manifold /
/// 0 over-edges.  Census: 553 of 757 snapshot parts carry >= 2
/// walk-exact nodes; 270 of them PASS L2 through the single-rep
/// reading and are never touched (the route fires only on the
/// still-not-manifold residue); 251 of the 296 failing multi-node
/// parts resolve under this reading (237 not-manifold + 14
/// degenerate-triangles), with 0 out-of-bounds reps
/// (docs/evidence/marathon/w1b-progress.md).
///
/// The law, fail-closed at every step: every token node decodes
/// walk-exact under the committed table law (fewer than 2 is not the
/// family); rep k = node k's territory ``[region_end_k, node k+1)`` —
/// its records parse under the SAME committed record laws against node
/// k's OWN element space; every gated reference resolves in-bounds
/// (one OOB rep declines the whole reading); no surviving record may
/// precede node 0's region end; the merged mesh is adopted ONLY when
/// it is manifold, degenerate and non-empty (the caller enforces this
/// and keeps the single-rep emission byte-for-byte otherwise).
///
/// The multi-region reading's outcome (the twin's
/// ``('ok' | 'family-declined' | 'not-family', result, failure)``).
enum MrOutcome {
    Adopted(Box<CompositeDecode>),
    FamilyDeclined(String),
    NotFamily,
}

/// decode_region with the stage-8 extent recovery on walk failure —
/// the multi-region node scan's second chance (W10, 2026-11-22; the
/// twin of :fn:`_region_decode_with_extent`).  A token node whose
/// region opens with >= 16 full-write slots carries a 2-bit table
/// whose leading bytes form whole zero groups, so the committed
/// layout skip overshoots INTO the table and the primary walk fails
/// (stage-8 artifact 2, the 221df959 shape).  The committed extent
/// law (:fn:`table_decode_extents`) recovers the unique walk-exact
/// extent — the same law the mixedwrite path runs; no new candidate,
/// no re-ordered guess.  Fail-closed: no zero block at the counts
/// end, zero or several walk-exact extents, and the node stays
/// declined (the original walk failure re-raised).  Returns the
/// decoded node plus the recovered flag (false on the primary walk,
/// true on the extent recovery).
// ``(n + 3) / 4`` is the twin's expression shape (see layout).
#[allow(clippy::manual_div_ceil)]
fn region_decode_with_extent(
    payload: &[u8],
    element_count: u32,
) -> Result<(Vec<Element>, RegionInfo, bool), ExportError> {
    match decode_region(payload, element_count) {
        Ok(res) => Ok((res.0, res.1, false)),
        Err(orig) => {
            let Some(tok) = find(payload, LIST_TOKEN, 0, payload.len()) else {
                return Err(orig);
            };
            let Some((_c1, mut q)) = read_count_checked(payload, tok + 5) else {
                return Err(orig);
            };
            let Some((_c2, q2)) = read_count_checked(payload, q) else {
                return Err(orig);
            };
            q = q2;
            match table_decode_extents(payload, element_count, q) {
                Some(Ok(te)) => Ok((
                    te.elements,
                    RegionInfo {
                        table_bytes: (element_count as usize + 3) / 4,
                        write_count: te.write_count,
                        region_bytes: 4 * te.write_count as usize,
                        walk_end: te.region_end_rel,
                        container_window_end: None,
                    },
                    true,
                )),
                _ => Err(orig),
            }
        }
    }
}

/// The head-record container's own reading (W17, 2026-11-22; twin:
/// ``_container_decode``).
///
/// The W10 negative's ``00 00 00 01`` family: token nodes whose region
/// fails the table walk carry, at the counts end, the 4 bytes
/// ``00 00 00 01`` and then the node's OWN point region as ``c1`` RAW
/// f32 triples (no zero block, no 2-bit table, no P1g write count —
/// the second layout family the U3-era probes named, and the
/// raw-array family's continuation past its trail escape).  Byte
/// evidence (4 local instances, probe
/// ``scripts/triage/probe_w17_container_scan.py``): spoke (c1=12),
/// Clocke-pf-Spl (c1=146), ntu-57YL (c1=156), acc-Cont-Lft (c1=256) —
/// every window decodes at nice-rate 1.000 under the walk's own
/// finite/plausible predicate, and the facet records AFTER the window
/// parse under the committed record laws against the container's OWN
/// c1 and triangulate manifold with 0 degenerate emissions (the
/// ntu-57YL container is closed and oriented: 312 triangles, boundary
/// 0).
///
/// Fail-closed: no ``00 00 00 01`` at the counts end, a window that
/// overruns the payload, or one implausible coordinate — ``None``.
/// The bytes between the window and the first record (the container's
/// middle: edge/curve-side data, undecoded) are skipped by the record
/// parsers' own header scan, and the adoption gate (merged manifold +
/// 0 degenerate) is what makes the reading safe to attempt, not the
/// middle's silence.
fn container_decode(payload: &[u8], element_count: u32) -> Option<(Vec<Element>, RegionInfo)> {
    let tok = find(payload, LIST_TOKEN, 0, payload.len())?;
    let (_c1, mut q) = read_count_checked(payload, tok + 5)?;
    let (_c2, q2) = read_count_checked(payload, q)?;
    q = q2;
    if payload.get(q..q + 4)? != b"\x00\x00\x00\x01" {
        return None;
    }
    let start = q + 4;
    let end = start + 12 * element_count as usize;
    if end > payload.len() {
        return None;
    }
    let mut elements: Vec<Element> = Vec::with_capacity(element_count as usize);
    for k in 0..element_count as usize {
        let x = f32_widen(payload, start + 12 * k);
        let y = f32_widen(payload, start + 12 * k + 4);
        let z = f32_widen(payload, start + 12 * k + 8);
        if !nice(x) || !nice(y) || !nice(z) {
            return None;
        }
        elements.push((3, Some((x, y, z))));
    }
    Some((
        elements,
        RegionInfo {
            table_bytes: 0,
            write_count: 3 * element_count,
            region_bytes: 12 * element_count as usize,
            walk_end: payload.len(),
            container_window_end: Some(end),
        },
    ))
}

/// Returns ``NotFamily`` when fewer than 2 walk-exact nodes exist —
/// the single-rep reading is the law there and no decline is named
/// (the not-manifold warning already carries the store's failure).
fn decode_multiregion(data: &[u8], lo: usize, hi: usize) -> MrOutcome {
    let scanned = scan_token_nodes(data, lo, hi);
    let mut nodes: Vec<(usize, u32, Vec<Element>, RegionInfo)> = Vec::new();
    let mut extent_reps = 0usize;
    for tn in &scanned {
        let payload = &data[tn.plo..tn.phi];
        if let Ok((elements, rinfo, extent_recovered)) = region_decode_with_extent(payload, tn.elem)
        {
            if extent_recovered {
                extent_reps += 1;
            }
            nodes.push((tn.pos, tn.elem, elements, rinfo));
            continue;
        }
        // The W17 container second chance: a walk-FAILING node may be
        // the ``00 00 00 01`` container family — its own raw triple
        // region plus the head records (W10's negative).  A node no
        // law decodes stays skipped, as before.
        if let Some((elements, rinfo)) = container_decode(payload, tn.elem) {
            nodes.push((tn.pos, tn.elem, elements, rinfo));
        }
    }
    if nodes.len() < 2 {
        return MrOutcome::NotFamily;
    }
    let region_end_0 = nodes[0].0 + 4 + nodes[0].3.walk_end;
    // Node 0 being a container rep puts its records inside its own
    // payload (attributed to it): the head guard keeps its old law
    // only on the bytes BEFORE the node — the same bytes the per-rep
    // attribution would drop.
    let guard_hi = if nodes[0].3.container_window_end.is_some() {
        nodes[0].0 + 4
    } else {
        region_end_0
    };
    let (head_recs, _) = parse_strip_records(data, lo, guard_hi, nodes[0].1, None);
    if !head_recs.is_empty() {
        return MrOutcome::FamilyDeclined(format!(
            "{} surviving record(s) precede node 0's region end: the \
             per-rep attribution would drop them",
            head_recs.len()
        ));
    }
    let strict = match mr_emit_reps(data, hi, &nodes, extent_reps, None) {
        Ok(decode) => decode,
        Err(msg) => return MrOutcome::FamilyDeclined(msg),
    };
    if !mr_adoptable(&strict) {
        // The per-rep seam second chance (W10, 2026-11-22): the same
        // two-pass discipline the entry point's primary-emit seam runs
        // (2026-11-18, #34), with the store-level law's reference
        // semantics — the sliver is compared against the WHOLE merged
        // mesh's area, not one rep.  Measured precedent: 138 of the
        // 270 multi-node corpus passers carry seam sliver drops
        // (docs/evidence/marathon/w10-progress.md).  The armed reading
        // stands ONLY where it resolves the merged over-use (manifold
        // + degenerate-free); any other outcome keeps the strict
        // (seam-off) emission byte-for-byte.
        let area = mesh::mesh_area(&strict.triangles, &strict.points);
        // An armed-pass Err cannot happen here: the records' parse (and
        // so the per-rep OOB gate) is seam-independent, and the strict
        // pass already cleared it — the arm stays declined either way.
        if let Ok(armed) = mr_emit_reps(data, hi, &nodes, extent_reps, Some(area))
            && mr_adoptable(&armed)
        {
            return MrOutcome::Adopted(armed);
        }
    }
    MrOutcome::Adopted(strict)
}

/// One full per-rep multi-region emission: every rep's territory
/// records triangulated against the rep's OWN element space, merged
/// over the disjoint offsets.  ``seam_area`` arms the primary-loop
/// seam per rep with the merged mesh's area reference (``None`` — the
/// seam off, the W1-B strict reading).  ``Err`` names the fail-closed
/// OOB rep (the #66 post-vote gate per rep).
#[allow(clippy::too_many_lines)]
fn mr_emit_reps(
    data: &[u8],
    hi: usize,
    nodes: &[(usize, u32, Vec<Element>, RegionInfo)],
    extent_reps: usize,
    seam_area: Option<f64>,
) -> Result<Box<CompositeDecode>, String> {
    let mut points: Vec<(f64, f64, f64)> = Vec::new();
    let mut triangles: Vec<(u32, u32, u32)> = Vec::new();
    let mut degenerate = 0u32;
    let mut curves: Vec<Vec<(f64, f64, f64)>> = Vec::new();
    let mut space_offsets: Vec<usize> = Vec::new();
    let mut reps_dup_pin: Vec<(usize, DupPin)> = Vec::new();
    let mut loops_exported = 0u32;
    let mut loops_curve_entry = 0u32;
    let mut primary_loop_skips = 0u32;
    let mut primary_loop_kept = 0u32;
    let mut relaxed_loops_accepted = 0u32;
    let mut relaxed_loops_declined = 0u32;
    let mut skipped_markers: BTreeMap<u8, u32> = BTreeMap::new();
    let mut facet_candidates = 0usize;
    let mut facet_records = 0usize;
    let mut write_count = 0usize;
    let mut table_bytes = 0usize;
    let mut element_decl = 0usize;
    let mut curve_entries = 0usize;
    let mut node_bytes = 0usize;
    let mut ext_records = 0usize;
    let mut ext_triangles = 0usize;
    let mut ext_declined = 0usize;
    let mut ext_filtered = 0usize;
    let mut reps = 0usize;
    let mut container_reps = 0usize;
    for (k, (npos, c1, elements, rinfo)) in nodes.iter().enumerate() {
        let region_end = npos + 4 + rinfo.walk_end;
        let t1 = match nodes.get(k + 1) {
            Some((next_pos, ..)) => *next_pos,
            None => hi,
        };
        let parse_lo = match rinfo.container_window_end {
            // The container's records live INSIDE its payload, from
            // the raw triple window's end on (the middle bytes the
            // parsers skip over); its territory beyond the payload
            // end carries no records of its own.
            Some(win_end) => npos + 4 + win_end,
            None => region_end,
        };
        if rinfo.container_window_end.is_some() {
            container_reps += 1;
        }
        let (records, n_hdrs) = parse_strip_records(data, parse_lo, t1, *c1, Some(elements));
        let (ext_k, ext_cands) = parse_extended_facet_records(
            data,
            parse_lo,
            t1,
            *c1,
            Some(elements),
            &short_record_spans(data, t1, &records),
        );
        let mut grefs: Vec<u32> = records
            .iter()
            .filter(|r| GATED.contains(&r.marker))
            .flat_map(|r| r.refs.iter().copied())
            .collect();
        grefs.extend(ext_k.iter().flat_map(|r| r.refs.iter().copied()));
        let oob: Vec<u32> = grefs.iter().copied().filter(|&r| r >= *c1).collect();
        if !oob.is_empty() {
            let mx = oob.iter().copied().max().unwrap_or(0);
            return Err(format!(
                "rep {k} (node at {npos}): {} gated reference(s) leave \
                 the rep's element space ({mx} >= elem_decl {c1}); the \
                 multi-region reading does not resolve",
                oob.len()
            ));
        }
        let tri_res = triangulate(elements, &records, &ext_k, seam_area, false);
        let base = points.len();
        let pts: Vec<(f64, f64, f64)> = elements
            .iter()
            .filter_map(|(_v, pt)| pt.as_ref().map(|p| (p.0, p.1, p.2)))
            .collect();
        if let Some(dp) = &tri_res.dup_pin {
            reps_dup_pin.push((base, dp.clone()));
        }
        points.extend(pts.iter().copied());
        triangles.extend(
            tri_res
                .triangles
                .iter()
                .map(|&(a, b, c)| (a + base as u32, b + base as u32, c + base as u32)),
        );
        degenerate += tri_res.degenerate;
        space_offsets.push(base);
        // The §2.3 curve exposure: this rep's dropped loops' pre-weld
        // sequences (additive, outside Fidelity).
        for (_mk, _normal, loop_refs) in &tri_res.dropped_loops {
            curves.push(curve_sequence(loop_refs, elements));
        }
        reps += 1;
        loops_exported += tri_res.loops_exported;
        loops_curve_entry += tri_res.loops_curve_entry;
        primary_loop_skips += tri_res.primary_loop_skips;
        primary_loop_kept += tri_res.primary_loop_kept;
        relaxed_loops_accepted += tri_res.relaxed_loops_accepted;
        relaxed_loops_declined += tri_res.relaxed_loops_declined;
        facet_candidates += n_hdrs + ext_cands;
        facet_records += records.len() + ext_k.len();
        ext_records += ext_k.len();
        ext_triangles += tri_res.extended_triangles as usize;
        ext_filtered += tri_res.extended_members_filtered as usize;
        ext_declined += tri_res.extended_declined as usize;
        write_count += rinfo.write_count as usize;
        table_bytes += rinfo.table_bytes;
        element_decl += *c1 as usize;
        curve_entries += elements.len() - pts.len();
        node_bytes += t1 - (npos + 4);
        for rec in &records {
            if !EXPORTED_SHORT_MARKERS.contains(&rec.marker)
                && !RELAXED_SHORT_MARKERS.contains(&rec.marker)
            {
                *skipped_markers.entry(rec.marker).or_insert(0) += 1;
            }
        }
    }
    // The dup-pin weld merged per rep (the same merge the per-rep path
    // runs; a rep's welded loops carry that rep's point offset).
    let mut curve_entry_law = 0u32;
    for (b, dp) in &reps_dup_pin {
        if dp.loops == 0 {
            continue;
        }
        triangles.extend(
            dp.triangles
                .iter()
                .map(|&(a, s, t)| (a + *b as u32, s + *b as u32, t + *b as u32)),
        );
        degenerate += dp.degenerate;
        loops_exported += dp.loops;
        loops_curve_entry -= dp.loops;
        curve_entry_law += dp.loops;
    }
    let mut info = CompositeInfo {
        stage: "identity-multiregion",
        element_decl,
        node_points: points.len(),
        curve_entries,
        write_count: Some(write_count),
        table_bytes: Some(table_bytes),
        facet_candidates,
        facet_records,
        skipped_markers,
        node_bytes,
        multiregion_reps: Some(reps),
        multiregion_extent_reps: if extent_reps > 0 {
            Some(extent_reps)
        } else {
            None
        },
        multiregion_container_reps: if container_reps > 0 {
            Some(container_reps)
        } else {
            None
        },
        multiregion_declined: None,
        reps_decoded: None,
        reps_exported: None,
        reps_unexported: None,
        rep_reasons: None,
        rep_laws: None,
        raw_start: None,
        raw_nice_rate: None,
        raw_x_asc_rate: None,
        raw_trail_bytes: None,
        raw_count3: None,
        loops_exported,
        loops_curve_entry,
        extended_header_records: None,
        extended_header_triangles: None,
        extended_header_declined: None,
        extended_members_filtered: None,
        curve_entry_law: None,
        loops_curve_entry_exported: None,
        primary_loop_skips: None,
        relaxed_loops_accepted: None,
        relaxed_loops_declined: None,
        primary_loop_seam_declined: None,
        primary_loop_kept: None,
        unordered_dedup_dropped: None,
        unordered_dedup_declined: None,
        primary_loop_relist_skips: None,
        primary_loop_relist_boundary: None,
    };
    if ext_records > 0 {
        info.extended_header_records = Some(ext_records);
        info.extended_header_triangles = Some(ext_triangles);
        if ext_declined > 0 {
            info.extended_header_declined = Some(ext_declined);
        }
        if ext_filtered > 0 {
            info.extended_members_filtered = Some(ext_filtered);
        }
    }
    if primary_loop_skips > 0 {
        info.primary_loop_skips = Some(primary_loop_skips);
    }
    if primary_loop_kept > 0 {
        info.primary_loop_kept = Some(primary_loop_kept);
    }
    if relaxed_loops_accepted > 0 || relaxed_loops_declined > 0 {
        info.relaxed_loops_accepted = Some(relaxed_loops_accepted);
        info.relaxed_loops_declined = Some(relaxed_loops_declined);
    }
    if curve_entry_law > 0 {
        info.curve_entry_law = Some("e0b-dup-pin");
        info.loops_curve_entry_exported = Some(curve_entry_law);
    }
    Ok(Box::new(CompositeDecode {
        kept_loop_tris: Vec::new(),
        kept_loop_count: 0,
        relist_forced: 0,
        points,
        triangles,
        degenerate,
        info,
        curves,
        space_offsets,
    }))
}

/// The merged-mesh adoption gate (the caller's, verbatim): non-empty,
/// manifold, degenerate-free.
fn mr_adoptable(decode: &CompositeDecode) -> bool {
    !decode.triangles.is_empty()
        && decode.degenerate == 0
        && mesh::mesh_stats(&decode.triangles).manifold
}

/// Decode one composite store span — the primary-emit seam's entry
/// point (2026-11-18, #34; twin: ``decode_composite_store``).
///
/// The store is decoded twice: a registry pass with the seam off
/// measures the assembled mesh's area, then the guarded pass drops only
/// the refused primary loops whose area is at most
/// :const:`PRIMARY_LOOP_AREA_REL` (1%) of it.  A larger over-use is real
/// surface and is kept exactly as before (counted in
/// ``primary_loop_kept``); the dropped slivers are counted in
/// ``primary_loop_skips``.  The seam stands only where it RESOLVES the
/// store's over-use: a guarded mesh that is still not manifold returns
/// the pre-seam decode unchanged with ``primary_loop_seam_declined``
/// naming the candidates (the dedup law's fail-closed discipline; no
/// surface is lost for no L2 gain).
pub fn decode_composite_store(
    data: &[u8],
    span: &StoreSpan,
    groups: &[PoolGroup],
    kinds: &[Vec<u8>],
    allow_unrouted_elements: bool,
) -> Result<CompositeDecode, ExportError> {
    let baseline = decode_store_once(
        data,
        span,
        groups,
        kinds,
        allow_unrouted_elements,
        None,
        false,
    )?;
    let area = mesh::mesh_area(&baseline.triangles, &baseline.points);
    let seam = decode_store_once(
        data,
        span,
        groups,
        kinds,
        allow_unrouted_elements,
        Some(area),
        false,
    )?;
    let skipped = seam.info.primary_loop_skips.unwrap_or(0);
    let seam_kept = seam.info.primary_loop_kept.unwrap_or(0);
    let mut chosen = if skipped > 0 && !mesh::mesh_stats(&seam.triangles).manifold {
        // The seam fires ONLY where it resolves the store's over-use:
        // a store whose mesh is still not manifold after the slivers
        // are out keeps its exact pre-seam emission — no surface is
        // lost for no L2 gain. The decline is named.
        let mut info = baseline.info;
        info.primary_loop_seam_declined = Some(skipped);
        info.primary_loop_kept = seam.info.primary_loop_kept;
        CompositeDecode {
            kept_loop_tris: Vec::new(),
            kept_loop_count: 0,
            relist_forced: 0,
            points: baseline.points,
            triangles: baseline.triangles,
            degenerate: baseline.degenerate,
            info,
            curves: baseline.curves,
            space_offsets: baseline.space_offsets,
        }
    } else {
        seam
    };
    // Stage-15 unordered-triangle dedup (see apply_unordered_dedup):
    // applied to the mesh the store ACTUALLY exports (the seam's
    // decision above is unchanged, so its committed surface trade
    // stands) — fires only on a not-manifold assembled mesh whose
    // duplicate unordered triples (COORDINATE identity across the
    // store's disjoint index spaces) resolve it, so a passing store's
    // mesh is never touched.
    chosen.triangles = apply_unordered_dedup(
        chosen.triangles,
        &mut chosen.info,
        &chosen.points,
        &chosen.space_offsets,
    );
    // The re-listed-keep skip (Fase 3 L1, #70; the S5 root-cause
    // investigation): a kept primary loop is the NX->CATIA writer's
    // re-listed skin — the same facets the surviving mesh already
    // carries, re-triangulated with the other diagonal (invisible to
    // the coordinate dedup).  It runs AFTER the dedup (each law sees
    // the mesh the previous one actually exports; the dedup's
    // committed outcomes are unchanged) and ONLY on the
    // still-not-manifold residue: a third decode pass re-runs the
    // emission with the refused above-sliver loops SKIPPED AT DECISION
    // TIME (the S5 seam-max world), and its result is adopted ONLY
    // when the candidate mesh is manifold AND its boundary-edge count
    // does not grow against the chosen emission AND every skipped
    // loop's vertex coordinates survive in the candidate (the skin
    // signature; a unique-surface loop with its own apex coordinates
    // is declined) AND — L1.1 (#70, 2026-11-21) — the candidate is
    // DEGENERATE-FREE: the 37 parts L1 landed on
    // ``degenerate-triangles`` carry degenerate skips in the KEPT
    // emission itself (chosen == candidate, measured 37/37 on the
    // submarine snapshot), so adopting a manifold candidate whose
    // emission still skips degenerates only trades the named
    // manifold failure for the L2 degenerate gate.  The condition
    // returns them to their previous (not-manifold) class without
    // touching the 80 adopters whose candidates are degenerate-free.
    // Any failed condition keeps the previous emission byte-for-byte —
    // fail-closed, PRIMARY_LOOP_AREA_REL untouched.
    let chosen_stats = mesh::mesh_stats(&chosen.triangles);
    if !chosen_stats.manifold
        && (seam_kept > 0 || chosen.info.primary_loop_kept.unwrap_or(0) > 0)
        && let Ok(rel) = decode_store_once(
            data,
            span,
            groups,
            kinds,
            allow_unrouted_elements,
            Some(area),
            true,
        )
        && !rel.triangles.is_empty()
    {
        let cand_stats = mesh::mesh_stats(&rel.triangles);
        let mut surviving: HashSet<(u64, u64, u64)> = HashSet::new();
        for &(a, b, c) in &rel.triangles {
            for i in [a, b, c] {
                surviving.insert(vkey(rel.points[i as usize]));
            }
        }
        let covered = rel.kept_loop_tris.iter().all(|t| {
            [t.0, t.1, t.2]
                .iter()
                .all(|&i| surviving.contains(&vkey(rel.points[i as usize])))
        });
        if cand_stats.manifold
            && cand_stats.boundary_edges <= chosen_stats.boundary_edges
            && covered
            && rel.degenerate == 0
        {
            let mut info = rel.info;
            info.primary_loop_relist_skips = Some(rel.relist_forced);
            info.primary_loop_relist_boundary = Some(format!(
                "{}->{}",
                chosen_stats.boundary_edges, cand_stats.boundary_edges
            ));
            chosen = CompositeDecode {
                kept_loop_tris: Vec::new(),
                kept_loop_count: 0,
                relist_forced: 0,
                points: rel.points,
                triangles: rel.triangles,
                degenerate: rel.degenerate,
                info,
                curves: rel.curves,
                space_offsets: rel.space_offsets,
            };
        }
    }
    // The multi-region second chance (W1-B, 2026-11-22): the
    // still-not-manifold residue of a MULTI-PERIOD body is the
    // single-rep reading's misresolution (every period after the first
    // resolved against node 0's region — see :fn:`decode_multiregion`
    // for the byte evidence).  The route fires ONLY here (a passing
    // store's decode never reaches it, so its PLY is byte-identical),
    // re-reads the body per period, and is adopted ONLY when the
    // merged mesh is manifold, degenerate and non-empty; any other
    // outcome keeps the emission above byte-for-byte, with the gap
    // named.
    if !chosen.triangles.is_empty() && !mesh::mesh_stats(&chosen.triangles).manifold {
        match decode_multiregion(data, span.body_lo, span.body_hi) {
            MrOutcome::NotFamily => {}
            MrOutcome::FamilyDeclined(reason) => {
                chosen.info.multiregion_declined = Some(reason);
            }
            MrOutcome::Adopted(cand) => {
                let cand_stats = mesh::mesh_stats(&cand.triangles);
                if !cand.triangles.is_empty() && cand_stats.manifold && cand.degenerate == 0 {
                    chosen = CompositeDecode {
                        kept_loop_tris: Vec::new(),
                        kept_loop_count: 0,
                        relist_forced: 0,
                        points: cand.points,
                        triangles: cand.triangles,
                        degenerate: cand.degenerate,
                        info: cand.info,
                        curves: cand.curves,
                        space_offsets: cand.space_offsets,
                    };
                } else {
                    chosen.info.multiregion_declined = Some(format!(
                        "decoded {} reps: the merged mesh is not adopted \
                         (manifold={}, degenerate={}, triangles={})",
                        cand.info.multiregion_reps.unwrap_or(0),
                        cand_stats.manifold,
                        cand.degenerate,
                        cand.triangles.len()
                    ));
                }
            }
        }
    }
    Ok(chosen)
}

/// Decode one composite store span under the identity law (stage 3d;
/// per-rep decomposition added 2026-11-12 stage 5, #34) — the twin's
/// ``decode_composite_store``. Returns the decoded points (the
/// exported vertices), triangles (indices into them), degenerate
/// count and the composite summary block. Raises
/// :struct:`ExportError` (``undecoded-variant``) with the specific
/// gap when the law does not cover the store: no token-bearing list
/// node (N1), a layout that does not fit the P1t law, a walk-exact
/// failure (the U3-variant second layout family), non-finite
/// coordinates, an unabsorbed pool with no per-rep reading either,
/// facet references beyond the element space, or no exportable facet
/// records' families at all.
///
/// Stage-13 second-chance element-space route (2026-11-13, #34):
/// ``allow_unrouted_elements`` skips ONLY the marker-routing check
/// below. It is set by the export orchestration's clean-path failure
/// points (the no-pool raise and the refs-beyond raise) for stores
/// whose body carries a token-bearing list node: the stage-13 finding
/// is that the element space beyond the pool IS the list node's point
/// region — the composite structure without the ``01 02`` edge group
/// / ``ff ..`` opener markers (docs/evidence/
/// 2026-11-13-stage13-elementspace.md sections 2-3) — so the routing
/// predicate was the only blocker. Every other gate (layout,
/// walk-exact, absorption, per-rep, the M2b refs gate,
/// triangulation) is unchanged; on any failure the caller re-raises
/// the ORIGINAL clean-path error.
///
/// The stage-6 raw-array and stage-9 mixedwrite fallbacks land with
/// port stage 2 (ticket #42's internal order); at stage 1 the
/// walk-mismatch branch fails closed with the twin's class naming the
/// stage-2 gap — every store the table walk handles decodes
/// identically to the twin.
#[allow(clippy::too_many_arguments)]
fn decode_store_once(
    data: &[u8],
    span: &StoreSpan,
    groups: &[PoolGroup],
    kinds: &[Vec<u8>],
    allow_unrouted_elements: bool,
    seam_area: Option<f64>,
    relist_skip: bool,
) -> Result<CompositeDecode, ExportError> {
    let lo = span.body_lo;
    let hi = span.body_hi;
    if !allow_unrouted_elements
        && !kinds
            .iter()
            .any(|k| k == EDGE_SUBKIND || k.first() == Some(&0xff))
    {
        return Err(ExportError::new(
            UNDECODED_VARIANT,
            "composite decode invoked on a store without composite markers",
        ));
    }
    let poolv: Vec<(f64, f64, f64)> = groups
        .iter()
        .flat_map(|g| g.vertices.iter().copied())
        .collect();
    let hdrs = facets::strip_headers(data, lo, hi);
    let node_hi = hdrs.first().copied().unwrap_or(hi);
    let Some((plo, phi, elem_decl, _edge_bound)) = find_list_node(data, lo, node_hi) else {
        return Err(ExportError::new(
            UNDECODED_VARIANT,
            "composite store without a token-bearing list node \
             (N1: 939/939 composite stores carry one)",
        ));
    };
    let payload = &data[plo..phi];
    let (elements, region_info) = match decode_region(payload, elem_decl) {
        Ok(ok) => ok,
        Err(exc) => {
            // Stage-6 (2026-11-12, #34): the walk-mismatch residue's
            // raw-array law runs ONLY where the table walk fails with
            // the census family signature (layout raise, or the
            // probe-semantics walk not ending at the declared region
            // end). A store the table walk handles never reaches this
            // branch; a walk-exact store with junk coordinates is not
            // the family (its own failure is re-raised). When the raw
            // reading does not cover the store either, the stage-9
            // mixed-write composition runs, and only when that
            // declines too do both gaps join the failure (fail-closed).
            if walk_mismatch(payload, elem_decl).is_none() {
                return Err(exc);
            }
            match decode_raw_array_path(
                data,
                lo,
                hi,
                groups,
                payload,
                elem_decl,
                seam_area,
                relist_skip,
            ) {
                Ok(ok) => return Ok(ok),
                Err(raw_exc) => {
                    let raw_detail = raw_exc.detail;
                    // Stage-9 (2026-11-12, #34): the stage-8 mixed-write
                    // composition — the per-rep decomposition over ALL
                    // token nodes on the FULL-body window (the stage-8
                    // locator), each node under the table/raw/flat laws
                    // (the zero-block extent candidates; the flat law's
                    // counts_end-pinned start), runs before the store
                    // fails closed.
                    match decode_mixedwrite(data, lo, hi, groups, seam_area, relist_skip) {
                        Ok(ok) => return Ok(ok),
                        Err(reps_exc) => {
                            return Err(ExportError::new(
                                UNDECODED_VARIANT,
                                format!(
                                    "{}; the stage-4a raw-array law does not \
                                     cover the store either ({}); the stage-8 \
                                     mixed-write per-rep composition does not \
                                     export it either ({})",
                                    exc.detail, raw_detail, reps_exc.detail
                                ),
                            ));
                        }
                    }
                }
            }
        }
    };
    let points: Vec<(f64, f64, f64)> = elements.iter().filter_map(|e| e.1).collect();
    let skip_slots = elements.len() - points.len();

    let pool_set: HashSet<(u64, u64, u64)> = poolv.iter().copied().map(vkey).collect();
    let point_set: HashSet<(u64, u64, u64)> = points.iter().copied().map(vkey).collect();
    let missing = pool_set.difference(&point_set).count();
    if missing > 0 {
        // Stage-5 per-rep decomposition (stage-4b law): try the
        // sequence-of-reps reading before failing closed.
        return decode_per_rep(
            data,
            lo,
            hi,
            groups,
            missing,
            pool_set.len(),
            seam_area,
            relist_skip,
        );
    }

    let (records, n_hdrs) = parse_strip_records(data, lo, hi, elem_decl, Some(&elements));
    let (extended, ext_candidates) = parse_extended_facet_records(
        data,
        lo,
        hi,
        elem_decl,
        Some(&elements),
        &short_record_spans(data, hi, &records),
    );
    // Refs are 0-based element indices: every gated family's references
    // must resolve inside the element space (the exported markers plus
    // the normal-carrying 0x49, the stage-2c gate set). The extended
    // family (2026-11-18) indexes the same space, so its refs are gated
    // too.
    let mut all_refs: Vec<u32> = records
        .iter()
        .filter(|r| GATED.contains(&r.marker))
        .flat_map(|r| r.refs.iter().copied())
        .collect();
    all_refs.extend(extended.iter().flat_map(|r| r.refs.iter().copied()));
    if let Some(&mx) = all_refs.iter().max()
        && mx >= elem_decl
    {
        return Err(ExportError::new(
            UNDECODED_VARIANT,
            format!(
                "facet references beyond the element space: max ref {mx} \
                 >= element count {elem_decl} (refs are 0-based element \
                 indices in region order, M2b identity; G3 open question 2)"
            ),
        ));
    }

    let tri_res = triangulate(&elements, &records, &extended, seam_area, relist_skip);
    let rel_kept_tris = tri_res.kept_loop_tris.clone();
    let rel_kept_count = tri_res.kept_loop_count;
    let rel_forced = tri_res.relist_forced;
    let mut triangles = tri_res.triangles;
    let mut degenerate = tri_res.degenerate;
    let mut loops_exported = tri_res.loops_exported;
    let mut loops_curve_entry = tri_res.loops_curve_entry;
    // The dup-pin weld (2026-11-18, per loop): ``triangulate`` already
    // evaluated every dropped loop independently (pinnable,
    // battery-supported and mesh-safe). Merge the welded loops; refused
    // loops stay counted as dropped.
    let mut curve_entry_law = 0u32;
    if let Some(dp) = &tri_res.dup_pin
        && dp.loops > 0
    {
        triangles.extend(dp.triangles.iter().copied());
        degenerate += dp.degenerate;
        loops_exported += dp.loops;
        loops_curve_entry -= dp.loops;
        curve_entry_law = dp.loops;
    }
    let mut skipped_markers: BTreeMap<u8, u32> = BTreeMap::new();
    for rec in &records {
        if !EXPORTED_SHORT_MARKERS.contains(&rec.marker)
            && !RELAXED_SHORT_MARKERS.contains(&rec.marker)
        {
            *skipped_markers.entry(rec.marker).or_insert(0) += 1;
        }
    }
    let mut info = CompositeInfo {
        primary_loop_relist_skips: None,
        primary_loop_relist_boundary: None,
        stage: "identity-table-walk",
        element_decl: elem_decl as usize,
        node_points: points.len(),
        curve_entries: skip_slots,
        write_count: Some(region_info.write_count as usize),
        table_bytes: Some(region_info.table_bytes),
        facet_candidates: n_hdrs + ext_candidates,
        facet_records: records.len() + extended.len(),
        skipped_markers,
        // stage-5 fold-in (reconciliation note section 5): the list
        // node's payload byte length — lets big/small form be derived
        // from summaries/CSVs (big > 4096 B).
        node_bytes: phi - plo,
        reps_decoded: None,
        reps_exported: None,
        reps_unexported: None,
        rep_reasons: None,
        rep_laws: None,
        raw_start: None,
        raw_nice_rate: None,
        raw_x_asc_rate: None,
        raw_trail_bytes: None,
        raw_count3: None,
        loops_exported,
        loops_curve_entry,
        extended_header_records: None,
        extended_header_triangles: None,
        extended_header_declined: None,
        extended_members_filtered: None,
        curve_entry_law: None,
        loops_curve_entry_exported: None,
        primary_loop_skips: None,
        relaxed_loops_accepted: None,
        relaxed_loops_declined: None,
        primary_loop_seam_declined: None,
        primary_loop_kept: None,
        unordered_dedup_dropped: None,
        unordered_dedup_declined: None,
        multiregion_reps: None,
        multiregion_extent_reps: None,
        multiregion_container_reps: None,
        multiregion_declined: None,
    };
    if !extended.is_empty() {
        info.extended_header_records = Some(extended.len());
        info.extended_header_triangles = Some(tri_res.extended_triangles as usize);
        if tri_res.extended_declined > 0 {
            info.extended_header_declined = Some(tri_res.extended_declined as usize);
        }
        if tri_res.extended_members_filtered > 0 {
            info.extended_members_filtered = Some(tri_res.extended_members_filtered as usize);
        }
    }
    if tri_res.primary_loop_skips > 0 {
        info.primary_loop_skips = Some(tri_res.primary_loop_skips);
    }
    if tri_res.primary_loop_kept > 0 {
        info.primary_loop_kept = Some(tri_res.primary_loop_kept);
    }
    if curve_entry_law > 0 {
        info.curve_entry_law = Some("e0b-dup-pin");
        info.loops_curve_entry_exported = Some(curve_entry_law);
    }
    // One index space on this path: the entry point's stage-15 dedup
    // ranks every copy equal and falls back to emission order.
    // The §2.3 curve exposure: the dropped loops' pre-weld sequences
    // (additive, outside Fidelity — see the boundary note).
    let curves: Vec<Vec<(f64, f64, f64)>> = tri_res
        .dropped_loops
        .iter()
        .map(|(_mk, _normal, loop_refs)| curve_sequence(loop_refs, &elements))
        .collect();
    Ok(CompositeDecode {
        kept_loop_tris: rel_kept_tris,
        kept_loop_count: rel_kept_count,
        relist_forced: rel_forced,
        points,
        triangles,
        degenerate,
        info,
        curves,
        space_offsets: vec![0],
    })
}

// --- stage-6: the walk-mismatch residue's raw-array law (stage 4a,
// integrated 2026-11-12, #34) -------------------------------------------
//
// The law as committed (docs/evidence/2026-11-10-node-streams.md section
// "Stage 4a-residue" + residue-raw-scan.csv + the reference
// implementations classify_residue_family.py --raw / probe_residue_anchor.py):
// a walk-mismatch payload continues past the header as raw f32 triples;
// the start is pinned by the trail-escape condition; strong fit = nice
// AND x-ascending over the full span (the scan's criteria and predicate,
// ported verbatim — not re-derived); the pool must re-list verbatim.
// The tail field's and count3's semantics stay open (named).

/// The committed scan's candidate bound: 4-aligned starts 32..64
/// (``classify_residue_family.py`` ``RAW_MAX_START``).
pub const RAW_MAX_START: usize = 64;

/// The committed strong-fit bar (residue-raw-scan.csv: strong = nice >=
/// 0.98 AND x-ascending >= 0.98 over the full elem_decl span).
pub const RAW_FIT_RATE: f64 = 0.98;

/// The raw scan's coordinate predicate (the stage-2c probe's predicate,
/// kept verbatim: the raw array has no table to fix the parse, so the
/// rate IS the parse validation — :fn:`nice`'s dropped 1e-6 floor was
/// never the measured criterion here) — the twin's ``_raw_nice``:
/// ``v == v and (v == 0.0 or 1e-6 < abs(v) < 1e7)``.
// ``v == v`` is the twin's NaN test verbatim.
#[allow(clippy::eq_op)]
fn raw_nice(v: f64) -> bool {
    v == v && (v == 0.0 || 1e-6 < v.abs() && v.abs() < 1e7)
}

/// The walk-mismatch family signature (the census probe's walk
/// semantics, ``decode_big_form_points.decode_region``: all elem_decl
/// slots walked bounded ONLY by the payload, no coordinate aborts) —
/// the twin's ``_walk_mismatch``. Returns ``Some`` when the declared
/// P1t prefix does not describe the payload — the layout raises, or
/// the walk does not end exactly at the declared region end — and
/// ``None`` when the walk is exact (a walk-exact store with junk
/// coordinates is not the family; the caller re-raises the original
/// failure). The profile's contents are never consumed by the caller
/// (only its presence); the returned string names the mismatch kind
/// for humans.
// ``(n + 3) / 4`` is the twin's expression shape (see layout).
#[allow(clippy::manual_div_ceil)]
fn walk_mismatch(payload: &[u8], elem_decl: u32) -> Option<&'static str> {
    let tok = find(payload, LIST_TOKEN, 0, payload.len())?;
    // unreachable behind find_list_node, kept total
    let mut p = tok + 5;
    let (_, np) = read_count_checked(payload, p)?; // unreadable declared counts
    p = np;
    let (_, np) = read_count_checked(payload, p)?;
    p = np;
    while p + 4 <= payload.len() && payload[p..p + 4] == [0u8; 4] {
        p += 4;
    }
    let table_len = (elem_decl as usize + 3) / 4;
    let count_pos = p + table_len;
    if count_pos >= payload.len() {
        return Some("layout: the 2-bit table runs past the payload");
    }
    let (write_count, region_start) = read_count_checked(payload, count_pos)?; // unreadable write count
    let region_end = region_start + 4 * write_count as usize;
    if region_end > payload.len() {
        return Some("layout: the declared write count overruns the payload");
    }
    let mut pos = region_start;
    for v in table_slots(payload, p, table_len, elem_decl) {
        let shape = SHAPES[v as usize];
        if pos + 4 * shape > payload.len() {
            break; // the probe's clean stop: bounded by the payload only
        }
        pos += 4 * shape;
    }
    if pos != region_end {
        return Some("walk: the probe walk does not end at the declared region end");
    }
    None
}

/// The raw anatomy the twin's ``decode_raw_array`` info dict carries.
#[derive(Debug, Clone, PartialEq)]
pub struct RawInfo {
    /// The pinned array start (payload-relative).
    pub raw_start: usize,
    /// The nice rate — the twin's ``round(rate, 4)``.
    pub raw_nice_rate: f64,
    /// The x-ascending rate — the twin's ``round(asc, 4)``.
    pub raw_x_asc_rate: f64,
    /// The bytes after the trail-escape byte.
    pub raw_trail_bytes: usize,
    /// The count3 field (recorded when readable, never validated — open).
    pub raw_count3: Option<u32>,
}

/// Python's ``round(x, 4)`` on an f64: correct rounding of the exact
/// binary value to 4 decimals (ties-to-even), the result's nearest
/// f64. Rust's ``{:.4}`` performs the same correct rounding of the
/// exact value; parse-back yields the same double. Unit-tested against
/// the Python ground truth (see ``py_round4_matches_python``).
fn py_round4(x: f64) -> f64 {
    format!("{x:.4}")
        .parse::<f64>()
        .expect("a finite f64 formatted with 4 decimals always parses back")
}

/// The raw-array reading of a walk-mismatch list-node payload (stage-4a
/// law, ported from ``classify_residue_family.py --raw`` and the
/// committed start rule — not re-derived) — the twin's
/// ``decode_raw_array``.
///
/// ``[token][count1][count2][tail][elem_decl x [x][y][z] stride 12, x
/// ascending][FF][count3 u32le][trail]``: the array start is the
/// UNIQUE 4-aligned start in ``[32, RAW_MAX_START]`` whose full
/// elem_decl span fits and whose trail-escape byte
/// ``payload[start + 12*elem_decl]`` is ``0xFF`` (the committed start
/// rule — it selected a unique start in 32/39 scan-fit stores; zero or
/// several candidates stay fail-closed). Strong fit = the scan's
/// criteria at the pinned start: both the nice rate and the x-ascending
/// rate at or above RAW_FIT_RATE (the scan's predicate and 1e-6 pair
/// tolerance). Pool absorption = every distinct pool vertex re-listed
/// verbatim in the triples (exact f32 — the scan's
/// ``pool_absorbed_raw`` criterion).
///
/// Returns the raw triples in array order (the element space — no
/// skip slots, every element written) and the raw anatomy. Raises
/// ``undecoded-variant`` with the specific gap otherwise: the start
/// not pinned, a weak fit, or an unabsorbed pool. The tail field's and
/// count3's semantics are OPEN: count3 is recorded when readable,
/// never validated.
// The tuple return is the twin's return shape (points, info).
#[allow(clippy::type_complexity)]
fn decode_raw_array(
    payload: &[u8],
    elem_decl: u32,
    poolv: &[(f64, f64, f64)],
) -> Result<(Vec<(f64, f64, f64)>, RawInfo), ExportError> {
    let ed = elem_decl as usize;
    let candidates: Vec<usize> = (32..=RAW_MAX_START)
        .step_by(4)
        .filter(|&s| s + 12 * ed < payload.len() && payload[s + 12 * ed] == 0xFF)
        .collect();
    let n_cand = (RAW_MAX_START - 32) / 4 + 1;
    if candidates.len() != 1 {
        return Err(ExportError::new(
            UNDECODED_VARIANT,
            format!(
                "raw-array start not pinned: the trail-escape condition \
                 payload[start + 12*{elem_decl}] == 0xFF selects \
                 {} of the {n_cand} candidate starts \
                 (4-aligned 32..{RAW_MAX_START}, the committed scan bound) \
                 — fail-closed (the law's start rule)",
                candidates.len()
            ),
        ));
    }
    let start = candidates[0];
    if elem_decl < 2 {
        return Err(ExportError::new(
            UNDECODED_VARIANT,
            format!(
                "raw-array fit undefined: elem_decl {elem_decl} leaves the \
                 scan's x-ascending rate without a consecutive pair (no-fit)"
            ),
        ));
    }
    let ps: HashSet<(u64, u64, u64)> = poolv.iter().copied().map(vkey).collect();
    let mut xs: Vec<f64> = Vec::with_capacity(elem_decl as usize);
    let mut points: Vec<(f64, f64, f64)> = Vec::with_capacity(elem_decl as usize);
    let mut nicec = 0u32;
    let span = &payload[start..start + 12 * elem_decl as usize];
    for triple in span.as_chunks::<12>().0 {
        let x = f32_widen(triple, 0);
        let y = f32_widen(triple, 4);
        let z = f32_widen(triple, 8);
        if raw_nice(x) && raw_nice(y) && raw_nice(z) {
            nicec += 1;
        }
        xs.push(x);
        points.push((x, y, z));
    }
    let rate = f64::from(nicec) / f64::from(elem_decl);
    let asc =
        xs.windows(2).filter(|w| w[1] >= w[0] - 1e-6).count() as f64 / (elem_decl as f64 - 1.0);
    if rate < RAW_FIT_RATE || asc < RAW_FIT_RATE {
        return Err(ExportError::new(
            UNDECODED_VARIANT,
            format!(
                "raw-array weak fit at the pinned start {start}: nice \
                 {rate:.4} / x-ascending {asc:.4} below the \
                 {RAW_FIT_RATE} strong-fit bar (the committed criteria; \
                 weak-fit family, fail-closed)"
            ),
        ));
    }
    let point_set: HashSet<(u64, u64, u64)> = points.iter().copied().map(vkey).collect();
    let missing = ps.difference(&point_set).count();
    if missing > 0 {
        return Err(ExportError::new(
            UNDECODED_VARIANT,
            format!(
                "raw-array pool not absorbed: {missing} of {} \
                 pool vertices absent from the {elem_decl} raw triples \
                 (exact-f32 absorption, the scan's pool_absorbed_raw \
                 criterion; fail-closed)",
                ps.len()
            ),
        ));
    }
    let trail_at = start + 12 * elem_decl as usize;
    let mut info = RawInfo {
        raw_start: start,
        raw_nice_rate: py_round4(rate),
        raw_x_asc_rate: py_round4(asc),
        raw_trail_bytes: payload.len() - trail_at,
        raw_count3: None,
    };
    // The escape byte's count runs past the payload: open, named —
    // recorded only when readable (the twin's try/except pass).
    if let Some((count3, _after)) = read_count_checked(payload, trail_at) {
        info.raw_count3 = Some(count3);
    }
    Ok((points, info))
}

/// Export path of the raw-array law: decode the array, then the
/// committed export ladder on the raw element space — records parsed
/// over the store body, the M2b identity refs gate (gated families'
/// references resolve inside the elem_decl element space),
/// strip/polygon triangulation. Raises ``undecoded-variant`` with the
/// raw gap when the law does not cover the store — the twin's
/// ``_decode_raw_array``.
#[allow(clippy::too_many_arguments)]
fn decode_raw_array_path(
    data: &[u8],
    lo: usize,
    hi: usize,
    groups: &[PoolGroup],
    payload: &[u8],
    elem_decl: u32,
    seam_area: Option<f64>,
    relist_skip: bool,
) -> Result<CompositeDecode, ExportError> {
    let poolv: Vec<(f64, f64, f64)> = groups
        .iter()
        .flat_map(|g| g.vertices.iter().copied())
        .collect();
    let (points, raw_info) = decode_raw_array(payload, elem_decl, &poolv)?;
    // The raw element space: every element written (slot value 0 —
    // the twin's ``[(0, pt) for pt in points]``), no skip slots.
    let elements: Vec<Element> = points.iter().map(|&pt| (0, Some(pt))).collect();
    let (records, n_hdrs) = parse_strip_records(data, lo, hi, elem_decl, Some(&elements));
    let (extended, ext_candidates) = parse_extended_facet_records(
        data,
        lo,
        hi,
        elem_decl,
        Some(&elements),
        &short_record_spans(data, hi, &records),
    );
    let mut all_refs: Vec<u32> = records
        .iter()
        .filter(|r| GATED.contains(&r.marker))
        .flat_map(|r| r.refs.iter().copied())
        .collect();
    all_refs.extend(extended.iter().flat_map(|r| r.refs.iter().copied()));
    if let Some(&mx) = all_refs.iter().max()
        && mx >= elem_decl
    {
        return Err(ExportError::new(
            UNDECODED_VARIANT,
            format!(
                "facet references beyond the raw-array element space: \
                 max ref {mx} >= element count {elem_decl} (M2b \
                 identity on the raw array; G3 open question 2)"
            ),
        ));
    }
    // The raw element space has no skip slots, so no dropped
    // curve-entry loops exist and the weld candidate is never accepted
    // here (the twin pops it on this path).
    let tri_res = triangulate(&elements, &records, &extended, seam_area, relist_skip);
    let raw_rel_kept_tris = tri_res.kept_loop_tris.clone();
    let raw_rel_kept_count = tri_res.kept_loop_count;
    let raw_rel_forced = tri_res.relist_forced;
    let triangles = tri_res.triangles;
    let degenerate = tri_res.degenerate;
    let loops_exported = tri_res.loops_exported;
    let loops_curve_entry = tri_res.loops_curve_entry;
    let ext_triangles = tri_res.extended_triangles;
    let ext_declined = tri_res.extended_declined;
    let ext_filtered = tri_res.extended_members_filtered;
    let mut skipped_markers: BTreeMap<u8, u32> = BTreeMap::new();
    for rec in &records {
        if !EXPORTED_SHORT_MARKERS.contains(&rec.marker)
            && !RELAXED_SHORT_MARKERS.contains(&rec.marker)
        {
            *skipped_markers.entry(rec.marker).or_insert(0) += 1;
        }
    }
    let info = CompositeInfo {
        primary_loop_relist_skips: None,
        primary_loop_relist_boundary: None,
        stage: "identity-raw-array",
        element_decl: elem_decl as usize,
        node_points: points.len(),
        curve_entries: 0,
        write_count: None,
        table_bytes: None,
        facet_candidates: n_hdrs + ext_candidates,
        facet_records: records.len() + extended.len(),
        skipped_markers,
        node_bytes: payload.len(),
        reps_decoded: None,
        reps_exported: None,
        reps_unexported: None,
        rep_reasons: None,
        rep_laws: None,
        raw_start: Some(raw_info.raw_start),
        raw_nice_rate: Some(raw_info.raw_nice_rate),
        raw_x_asc_rate: Some(raw_info.raw_x_asc_rate),
        raw_trail_bytes: Some(raw_info.raw_trail_bytes),
        raw_count3: raw_info.raw_count3,
        loops_exported,
        loops_curve_entry,
        extended_header_records: None,
        extended_header_triangles: None,
        extended_header_declined: None,
        extended_members_filtered: None,
        curve_entry_law: None,
        loops_curve_entry_exported: None,
        primary_loop_skips: None,
        relaxed_loops_accepted: None,
        relaxed_loops_declined: None,
        primary_loop_seam_declined: None,
        primary_loop_kept: None,
        unordered_dedup_dropped: None,
        unordered_dedup_declined: None,
        multiregion_reps: None,
        multiregion_extent_reps: None,
        multiregion_container_reps: None,
        multiregion_declined: None,
    };
    let mut info = info;
    if !extended.is_empty() {
        info.extended_header_records = Some(extended.len());
        info.extended_header_triangles = Some(ext_triangles as usize);
        if ext_declined > 0 {
            info.extended_header_declined = Some(ext_declined as usize);
        }
        if ext_filtered > 0 {
            info.extended_members_filtered = Some(ext_filtered as usize);
        }
    }
    if tri_res.primary_loop_skips > 0 {
        info.primary_loop_skips = Some(tri_res.primary_loop_skips);
    }
    if tri_res.primary_loop_kept > 0 {
        info.primary_loop_kept = Some(tri_res.primary_loop_kept);
    }
    // One index space on this path (see the single-region note above).
    // The §2.3 curve exposure: the raw element space has NO skip
    // slots, so no dropped curve-entry loops exist and the artifact is
    // empty (measured corpus incidence 0).
    Ok(CompositeDecode {
        kept_loop_tris: raw_rel_kept_tris,
        kept_loop_count: raw_rel_kept_count,
        relist_forced: raw_rel_forced,
        points,
        triangles,
        degenerate,
        info,
        curves: Vec::new(),
        space_offsets: vec![0],
    })
}

// --- stage-9: the mixed-write stream's locator/predicate artifacts
// (stage 8, integrated 2026-11-12, #34) ---------------------------------
//
// The stage-8 census (scripts/triage/mixedwrite_decode.py,
// docs/evidence/2026-11-12-mixedwrite-reps.md) showed the walk-mismatch
// residue's payloads parse end-to-end with the COMMITTED write laws once
// three locator/predicate artifacts are fixed. The functions below port
// the census's laws verbatim (not re-derived): the zero-block extent
// candidates (table_decode), the escape-pinned raw probe (raw_probe),
// the per-node law order table -> raw -> flat (decode_node), and the
// per-rep composition (audit_store), scoped to the walk-mismatch path
// and to the exporter's absorption/refs/triangulation gates.

/// The position after the declared counts (the P1g prefix's end), or
/// ``None`` when unreadable — the twin's ``_token_counts_end``. The
/// mixed-write node decode pins the flat law's start and the
/// zero-block extent candidates on this offset (the stage-8 decoder's
/// ``counts_end``); :fn:`scan_token_nodes` validated the counts
/// already, so ``None`` here is unreachable behind it.
fn token_counts_end(payload: &[u8]) -> Option<usize> {
    let tok = find(payload, LIST_TOKEN, 0, payload.len())?;
    if tok > 64 {
        return None;
    }
    let p = tok + 5;
    let (_, np) = read_count_checked(payload, p)?;
    let (_, np) = read_count_checked(payload, np)?;
    Some(np)
}

/// One walk-exact zero-block extent candidate — the twin's
/// ``_table_decode_extents`` result tuples ``(e, elements, skips,
/// region_end_rel, write_count)``.
struct TableExtent {
    /// The extent (the number of zero groups the table starts after).
    #[allow(dead_code)]
    extent: usize,
    /// The decoded element space.
    elements: Vec<Element>,
    /// The skip-slot count.
    #[allow(dead_code)]
    skips: u32,
    /// The payload-relative region end.
    region_end_rel: usize,
    /// The declared write count.
    write_count: u32,
}

/// The stage-3b table walk with the zero-block EXTENT as a candidate
/// (stage-8 artifact 2; ported from ``mixedwrite_decode.table_decode``
/// — not re-derived) — the twin's ``_table_decode_extents``.
///
/// The committed :fn:`layout` skips ALL consecutive zero groups after
/// the counts; when the region opens with >= 16 full-write slots the
/// 2-bit table's own leading bytes form whole zero groups, the skip
/// overshoots INTO the table, and the P1g count reads misaligned
/// (38/133 decoded table reps, 36 stores; 221df959's "declared 194").
/// The extent law: the table may start at ``counts_end + 4*e`` for
/// ``e`` in ``1..k`` (``k`` = the zero-group run after the counts);
/// exactly one extent must yield the walk-exact decode (the walk
/// consumes exactly the declared write count, every coordinate finite
/// and plausible) — several decode, the extent stays fail-closed
/// (ambiguous); none, this is not a table store. The committed
/// layout() is untouched: a store whose committed skip misaligns
/// fails the primary walk and lands on this path, so the candidates
/// cover the artifact's full incidence without re-routing walk-OK
/// stores (measured: extents inside the zero block read a zero count
/// and can never walk exact — the committed skip position is the only
/// other candidate the law can select).
///
/// Returns the unique walk-exact extent, ``Err(())`` when several
/// decode (ambiguous), or ``None``.
// ``(n + 3) / 4`` is the twin's expression shape (see layout).
#[allow(clippy::manual_div_ceil, clippy::type_complexity)]
fn table_decode_extents(
    payload: &[u8],
    element_count: u32,
    counts_end: usize,
) -> Option<Result<TableExtent, ()>> {
    if !is_zero4(payload, counts_end) {
        return None;
    }
    let mut ext = 1usize;
    while is_zero4(payload, counts_end + 4 * ext) {
        ext += 1;
    }
    let table_len = (element_count as usize + 3) / 4;
    let mut results: Vec<TableExtent> = Vec::new();
    for e in 1..=ext {
        let table_start = counts_end + 4 * e;
        let count_pos = table_start + table_len;
        if count_pos >= payload.len() {
            continue;
        }
        let Some((wc, region_start)) = read_count_checked(payload, count_pos) else {
            continue;
        };
        if wc > 3 * element_count {
            continue;
        }
        let region_end = region_start + 4 * wc as usize;
        if region_end > payload.len() {
            continue;
        }
        let mut pos = region_start;
        let mut elements: Vec<Element> = Vec::with_capacity(element_count as usize);
        let mut skips = 0u32;
        let mut ok = true;
        // the initial LCP state is the origin (P1i)
        #[allow(unused_assignments)]
        let (mut x, mut y, mut z) = (0.0f64, 0.0f64, 0.0f64);
        for i in 0..element_count as usize {
            let v = (payload[table_start + i / 4] >> (2 * (i % 4))) & 3;
            let shape = SHAPES[v as usize];
            if shape == 0 {
                skips += 1;
                elements.push((v, None));
                continue;
            }
            if pos + 4 * shape > region_end {
                ok = false;
                break;
            }
            match shape {
                3 => {
                    x = f32_widen(payload, pos);
                    y = f32_widen(payload, pos + 4);
                    z = f32_widen(payload, pos + 8);
                }
                2 => {
                    y = f32_widen(payload, pos);
                    z = f32_widen(payload, pos + 4);
                }
                _ => {
                    z = f32_widen(payload, pos);
                }
            }
            // the written values only (the twin's vals construction)
            let vals = [x, y, z];
            let written = match shape {
                3 => &vals[..],
                2 => &vals[1..],
                _ => &vals[2..],
            };
            if !written.iter().all(|c| nice(*c)) {
                ok = false;
                break;
            }
            pos += 4 * shape;
            elements.push((v, Some((x, y, z))));
        }
        if ok && pos == region_end {
            results.push(TableExtent {
                extent: e,
                elements,
                skips,
                region_end_rel: region_end,
                write_count: wc,
            });
        }
    }
    match results.len() {
        1 => Some(Ok(results.pop().expect("len 1"))),
        0 => None,
        _ => Some(Err(())),
    }
}

/// The twin's 4-byte zero-group test at ``at``: a short slice at the
/// payload edge is NOT four zeros (Python's short slice != the
/// constant), mirroring the twin's slice comparisons.
fn is_zero4(payload: &[u8], at: usize) -> bool {
    at + 4 <= payload.len() && payload[at..at + 4] == [0u8; 4]
}

/// The stage-4a raw-array start rule + fit rates on one node payload
/// (ported from ``mixedwrite_decode.raw_probe``) — the twin's
/// ``_raw_escape_probe``: the UNIQUE 4-aligned start in
/// ``[32, RAW_MAX_START]`` whose full elem_decl span fits and whose
/// trail-escape byte ``payload[start + 12*elem_decl]`` is ``0xFF``,
/// with the per-triple nice rate (the scan's :fn:`raw_nice` predicate
/// — 1e-6 floor kept verbatim) and the x-ascending rate. Returns
/// ``(start, nice_rate, asc_rate)`` or ``None`` (zero or several
/// candidates — fail-closed).
fn raw_escape_probe(payload: &[u8], element_count: u32) -> Option<(usize, f64, f64)> {
    let ed = element_count as usize;
    let cands: Vec<usize> = (32..=RAW_MAX_START)
        .step_by(4)
        .filter(|&s| s + 12 * ed < payload.len() && payload[s + 12 * ed] == 0xFF)
        .collect();
    if cands.len() != 1 {
        return None;
    }
    let s = cands[0];
    let mut nicec = 0u32;
    let mut xs: Vec<f64> = Vec::with_capacity(element_count as usize);
    for k in 0..element_count as usize {
        let x = f32_widen(payload, s + 12 * k);
        let y = f32_widen(payload, s + 12 * k + 4);
        let z = f32_widen(payload, s + 12 * k + 8);
        if raw_nice(x) && raw_nice(y) && raw_nice(z) {
            nicec += 1;
        }
        xs.push(x);
    }
    let rate = f64::from(nicec) / f64::from(element_count);
    let asc = if element_count > 1 {
        xs.windows(2).filter(|w| w[1] >= w[0] - 1e-6).count() as f64 / (element_count as f64 - 1.0)
    } else {
        1.0
    };
    Some((s, rate, asc))
}

/// One node's mixedwrite decode — the twin's ``_decode_node_mixedwrite``
/// return tuple ``(law, elements, pts, region_end_rel, write_count,
/// failure)`` with ``law`` in ``{table, raw, flat, None}``; raw/flat
/// elements are all written (the stage-6 raw path's shape).
struct NodeMixedwrite {
    law: Option<&'static str>,
    elements: Vec<Element>,
    pts: Vec<(f64, f64, f64)>,
    region_end_rel: usize,
    write_count: usize,
    failure: String,
}

/// Decode one token-node payload with the stage-8 law set (ported from
/// ``mixedwrite_decode.decode_node`` — not re-derived), in the
/// census's order — the twin's ``_decode_node_mixedwrite``:
///
/// (a) the stage-3b table law with the zero-block extent candidates
///     (:fn:`table_decode_extents`);
/// (b) the stage-4a raw law — the committed start rule and fit
///     criteria (RAW_FIT_RATE, the scan's :fn:`raw_nice`). The
///     pool-absorption gate is NOT applied here: the composition
///     judges absorption per rep (a multi-rep store's pool spans
///     several regions);
/// (c) the flat law (the stage-7 container PART-1 reading; stage-8
///     artifact 3): ``element_count`` full triples straight after the
///     4-B tail field — start pinned by ``counts_end``, NO escape
///     required, no zero block or table — all-nice under :fn:`nice`
///     (the exporter predicate; the raw scan's 1e-6 floor rejects
///     real near-zero coordinates on these stores), x-ascending >=
///     RAW_FIT_RATE OR the pool fully re-listed verbatim (junk spans
///     absorb nothing and fail here).
/// Whether `pts` absorbs the paired pool group's vertices — the
/// exact-f32 test, then the stage-4b noise tolerance for pools within
/// the committed 10,000-vertex cap (the store-level absorption
/// semantics of :fn:`decode_mixedwrite`, applied to one region). An
/// empty pool absorbs nothing (no evidence either way).
fn region_absorbs(pts: &[(f64, f64, f64)], poolv: &[(f64, f64, f64)]) -> bool {
    let pset: HashSet<(u64, u64, u64)> = poolv.iter().copied().map(vkey).collect();
    if pset.is_empty() {
        return false;
    }
    let pts_set: HashSet<(u64, u64, u64)> = pts.iter().copied().map(vkey).collect();
    let missing: Vec<(f64, f64, f64)> = poolv
        .iter()
        .copied()
        .filter(|v| !pts_set.contains(&vkey(*v)))
        .collect();
    if missing.is_empty() {
        return true;
    }
    if pset.len() <= 10_000 {
        missing
            .iter()
            .all(|&v| matches!(tol_match(v, pts), Some(best) if best <= NOISE_REL))
    } else {
        false
    }
}

/// The flat law's reading: `element_count` full triples straight after
/// the 4-B tail field (start pinned by `counts_end`), ALL-nice under
/// :fn:`nice` — the points, or `None` when the span does not fit or a
/// coordinate fails the predicate.
fn flat_reading(
    payload: &[u8],
    element_count: u32,
    counts_end: usize,
) -> Option<Vec<(f64, f64, f64)>> {
    let s = counts_end + 4;
    if s + 12 * element_count as usize <= payload.len() && element_count >= 2 {
        let pts: Vec<(f64, f64, f64)> = payload[s..s + 12 * element_count as usize]
            .as_chunks::<12>()
            .0
            .iter()
            .map(|t| (f32_widen(t, 0), f32_widen(t, 4), f32_widen(t, 8)))
            .collect();
        if pts.iter().all(|&(x, y, z)| nice(x) && nice(y) && nice(z)) {
            return Some(pts);
        }
    }
    None
}

fn decode_node_mixedwrite(
    payload: &[u8],
    element_count: u32,
    counts_end: usize,
    poolv: &[(f64, f64, f64)],
) -> NodeMixedwrite {
    match table_decode_extents(payload, element_count, counts_end) {
        Some(Ok(td)) => {
            let pts: Vec<(f64, f64, f64)> = td.elements.iter().filter_map(|e| e.1).collect();
            return NodeMixedwrite {
                law: Some("table"),
                elements: td.elements,
                pts,
                region_end_rel: td.region_end_rel,
                write_count: td.write_count as usize,
                failure: String::new(),
            };
        }
        Some(Err(())) => {
            return NodeMixedwrite {
                law: None,
                elements: Vec::new(),
                pts: Vec::new(),
                region_end_rel: 0,
                write_count: 0,
                failure: "table: ambiguous zero-block extent".to_string(),
            };
        }
        None => {}
    }
    if let Some((s, rate, asc)) = raw_escape_probe(payload, element_count)
        && rate >= RAW_FIT_RATE
        && asc >= RAW_FIT_RATE
    {
        let pts: Vec<(f64, f64, f64)> = payload[s..s + 12 * element_count as usize]
            .as_chunks::<12>()
            .0
            .iter()
            .map(|t| (f32_widen(t, 0), f32_widen(t, 4), f32_widen(t, 8)))
            .collect();
        // Fase 3 L2 (#72, the S6 Dodge store anatomy): the raw-vs-flat
        // absorption tiebreak — the raw claim loses when a flat reading
        // exists that absorbs the PAIRED pool group while the raw does
        // not (evidence of absorption, not probe order; measured on
        // the Dodge Challenger's 43.88 MB store: exactly 1 of the 501
        // raw claims flips).  Stores whose raw region absorbs its
        // paired pool keep their committed decode verbatim.
        if !region_absorbs(&pts, poolv)
            && let Some(flat_pts) = flat_reading(payload, element_count, counts_end)
            && region_absorbs(&flat_pts, poolv)
        {
            return NodeMixedwrite {
                law: Some("flat"),
                elements: flat_pts.iter().map(|&pt| (0, Some(pt))).collect(),
                pts: flat_pts,
                region_end_rel: counts_end + 4 + 12 * element_count as usize,
                write_count: 3 * element_count as usize,
                failure: String::new(),
            };
        }
        return NodeMixedwrite {
            law: Some("raw"),
            // raw elements are all written, slot value 0
            elements: pts.iter().map(|&pt| (0, Some(pt))).collect(),
            pts,
            region_end_rel: s + 12 * element_count as usize,
            write_count: 3 * element_count as usize,
            failure: String::new(),
        };
    }
    // The flat law: start pinned by counts_end (the 4-B tail field),
    // no escape required; the exporter predicate (_nice), and
    // x-ascending >= RAW_FIT_RATE OR the pool fully re-listed.
    let s = counts_end + 4;
    if s + 12 * element_count as usize <= payload.len() && element_count >= 2 {
        let mut ok = true;
        let mut xs: Vec<f64> = Vec::with_capacity(element_count as usize);
        for k in 0..element_count as usize {
            let x = f32_widen(payload, s + 12 * k);
            let y = f32_widen(payload, s + 12 * k + 4);
            let z = f32_widen(payload, s + 12 * k + 8);
            if !(nice(x) && nice(y) && nice(z)) {
                ok = false;
                break;
            }
            xs.push(x);
        }
        if ok {
            let asc = xs.windows(2).filter(|w| w[1] >= w[0] - 1e-6).count() as f64
                / (element_count as f64 - 1.0);
            let pts: Vec<(f64, f64, f64)> = payload[s..s + 12 * element_count as usize]
                .as_chunks::<12>()
                .0
                .iter()
                .map(|t| (f32_widen(t, 0), f32_widen(t, 4), f32_widen(t, 8)))
                .collect();
            let pset: HashSet<(u64, u64, u64)> = poolv.iter().copied().map(vkey).collect();
            let hits = pset
                .intersection(&pts.iter().copied().map(vkey).collect::<HashSet<_>>())
                .count();
            if asc >= RAW_FIT_RATE || (!pset.is_empty() && hits == pset.len()) {
                return NodeMixedwrite {
                    law: Some("flat"),
                    elements: pts.iter().map(|&pt| (0, Some(pt))).collect(),
                    pts,
                    region_end_rel: s + 12 * element_count as usize,
                    write_count: 3 * element_count as usize,
                    failure: String::new(),
                };
            }
        }
    }
    if let Some((s, rate, asc)) = raw_escape_probe(payload, element_count) {
        return NodeMixedwrite {
            law: None,
            elements: Vec::new(),
            pts: Vec::new(),
            region_end_rel: 0,
            write_count: 0,
            failure: format!("raw-weak-fit@{s} nice={rate:.4} asc={asc:.4}"),
        };
    }
    NodeMixedwrite {
        law: None,
        elements: Vec::new(),
        pts: Vec::new(),
        region_end_rel: 0,
        write_count: 0,
        failure: "table: no walk-exact zero-block extent".to_string(),
    }
}

/// One law-decoded rep of the mixedwrite composition — the per-rep
/// ``DecodedRep`` plus the law that decoded it. Built by reusing
/// :struct:`DecodedRep` with ``law`` set.
struct MixedRep {
    rep: DecodedRep,
    law: &'static str,
}

/// The stage-8 mixed-write per-rep composition (stage 9, #34) — the
/// twin's ``_decode_mixedwrite``: the stage-5 per-rep decomposition
/// applied to the walk-mismatch residue over the FULL-body window,
/// with the stage-8 locator/predicate laws per node
/// (:fn:`decode_node_mixedwrite`).
///
/// Rep k = (pool group k, the token node immediately preceding that
/// group's wrapper — the measured order, 2026-11-18 #50 B3 —, that
/// node's record territory ``[region_end_k, next token node)``).
/// The store exports only when EVERY pool vertex is absorbed by its
/// paired rep's region (exact f32, then the stage-4b noise
/// tolerance capped at 10,000-vertex pools): vertices no region
/// re-lists are the sub-node record route's residue — their element
/// slots are unpinned, the store stays fail-closed for export (the
/// stage-8 note's integration item (e); bad44bdf's class). Per rep:
/// the M2b refs gate against the rep's own element count, records
/// parsed with the committed width laws, strip/polygon
/// triangulation; merged meshes concatenate the exported reps'
/// written points. A rep whose gated references leave its own
/// element space stays unexported with the reason named (stage-5
/// per-rep fail-closed); a group whose rep node is missing or was
/// already claimed by an earlier group stays unexported too.
///
/// Raises ``undecoded-variant`` with the specific gap when no node
/// decodes, absorption is not established, or no rep exports.
fn decode_mixedwrite(
    data: &[u8],
    lo: usize,
    hi: usize,
    groups: &[PoolGroup],
    seam_area: Option<f64>,
    relist_skip: bool,
) -> Result<CompositeDecode, ExportError> {
    let poolv: Vec<(f64, f64, f64)> = groups
        .iter()
        .flat_map(|g| g.vertices.iter().copied())
        .collect();
    let pool_set: HashSet<(u64, u64, u64)> = poolv.iter().copied().map(vkey).collect();
    let nodes = scan_token_nodes(data, lo, hi);
    let n_nodes = nodes.len();
    // The rep pairing (2026-11-18, #50 B3; see decode_per_rep): group
    // k pairs with the token node immediately preceding its wrapper.
    // The flat law's absorption gate uses that group's vertices only —
    // a multi-rep store's whole pool cannot re-list in one region.
    let rep_nodes = rep_node_positions(&nodes, groups);
    let mut pool_by_node: HashMap<usize, usize> = HashMap::new();
    for (gi, node) in rep_nodes.iter().enumerate() {
        if let Some(n) = node {
            pool_by_node.entry(*n).or_insert(gi);
        }
    }
    let mut decoded: HashMap<usize, MixedRep> = HashMap::new();
    let mut law_counts = RepLaws {
        table: 0,
        raw: 0,
        flat: 0,
    };
    let mut node_failures: Vec<String> = Vec::new();
    for node in &nodes {
        let payload = &data[node.plo..node.phi];
        let Some(counts_end) = token_counts_end(payload) else {
            // unreachable behind scan_token_nodes
            continue;
        };
        let poolv_node: &[(f64, f64, f64)] = match pool_by_node.get(&node.pos) {
            Some(&gi) => &groups[gi].vertices,
            None => &[],
        };
        let nd = decode_node_mixedwrite(payload, node.elem, counts_end, poolv_node);
        let Some(law) = nd.law else {
            node_failures.push(if nd.failure.is_empty() {
                format!("node@{}: undecoded", node.pos)
            } else {
                format!("node@{}: {}", node.pos, nd.failure)
            });
            continue;
        };
        match law {
            "table" => law_counts.table += 1,
            "raw" => law_counts.raw += 1,
            _ => law_counts.flat += 1,
        }
        decoded.insert(
            node.pos,
            MixedRep {
                rep: DecodedRep {
                    pos: node.pos,
                    payload_len: node.phi - node.plo,
                    elem: node.elem,
                    elements: nd.elements,
                    pts: nd.pts,
                    // absolute end of the point region (the territory start)
                    region_end: node.pos + 4 + nd.region_end_rel,
                    write_count: nd.write_count as u32,
                    table_bytes: 0,
                },
                law,
            },
        );
    }
    if decoded.is_empty() {
        return Err(ExportError::new(
            UNDECODED_VARIANT,
            format!(
                "the stage-8 mixed-write per-rep composition decodes none \
                 of the {} token nodes over the full-body \
                 window (table/raw/flat laws; {})",
                n_nodes,
                if node_failures.is_empty() {
                    "no token nodes".to_string()
                } else {
                    format!("first: {}", node_failures[0])
                }
            ),
        ));
    }
    // Store-level absorption precondition: every pool vertex in its
    // PAIRED rep's region (exact f32, then the stage-4b noise
    // tolerance; the census measured exact f32 on all 81). Vertices no
    // region re-lists are the sub-node record route's residue — their
    // element slots are unpinned, the store stays fail-closed (named).
    let mut uncovered = 0usize;
    for (k, g) in groups.iter().enumerate() {
        let rep = rep_nodes[k].and_then(|n| decoded.get(&n)).map(|m| &m.rep);
        let mut seen: HashSet<(u64, u64, u64)> = HashSet::new();
        let mut distinct_vals: Vec<(f64, f64, f64)> = Vec::new();
        for &v in &g.vertices {
            if seen.insert(vkey(v)) {
                distinct_vals.push(v);
            }
        }
        let Some(rep) = rep else {
            uncovered += distinct_vals.len();
            continue;
        };
        let pts_set: HashSet<(u64, u64, u64)> = rep.pts.iter().copied().map(vkey).collect();
        let mut missing: Vec<(f64, f64, f64)> = distinct_vals
            .iter()
            .copied()
            .filter(|v| !pts_set.contains(&vkey(*v)))
            .collect();
        if !missing.is_empty() && distinct_vals.len() <= 10_000 {
            missing.retain(|v| match tol_match(*v, &rep.pts) {
                None => true,
                Some(best) => best > NOISE_REL,
            });
        }
        uncovered += missing.len();
    }
    if uncovered > 0 {
        return Err(ExportError::new(
            UNDECODED_VARIANT,
            format!(
                "the stage-8 mixed-write per-rep composition does not \
                 establish pool absorption: {uncovered} of {} \
                 pool vertices are absent from every decoded rep region \
                 ({} law-decoded reps for {} pool \
                 groups; vertices re-listed only by the 05 08 01 sub-node \
                 records have unpinned element indices — fail-closed for \
                 export until the sub-node element-index law pins them)",
                pool_set.len(),
                decoded.len(),
                groups.len()
            ),
        ));
    }
    let mut points: Vec<(f64, f64, f64)> = Vec::new();
    let mut triangles: Vec<(u32, u32, u32)> = Vec::new();
    let mut degenerate = 0u32;
    let mut loops_exported = 0u32;
    let mut loops_curve_entry = 0u32;
    let mut skipped_markers: BTreeMap<u8, u32> = BTreeMap::new();
    let mut facet_candidates = 0usize;
    let mut facet_records = 0usize;
    // N1 (2026-11-18 review): the per-rep paths export the extended
    // family too, so the summary must name it like the single-rep path.
    let mut ext_records = 0usize;
    let mut ext_triangles = 0usize;
    let mut ext_declined = 0usize;
    let mut ext_filtered = 0usize;
    // The primary-emit seam counters (per rep; summed at store level).
    let mut primary_loop_skips = 0u32;
    let mut relaxed_loops_accepted = 0u32;
    let mut relaxed_loops_declined = 0u32;
    let mut primary_loop_kept = 0u32;
    let mut write_count = 0usize;
    let mut table_bytes = 0usize;
    let mut element_decl = 0usize;
    let mut curve_entries = 0usize;
    let mut reps_unexported: Vec<String> = Vec::new();
    let mut reps_dup_pin: Vec<(usize, DupPin)> = Vec::new();
    let mut kept_loop_tris: Vec<(u32, u32, u32)> = Vec::new();
    let mut kept_loop_count = 0u32;
    let mut relist_forced_total = 0u32;
    let mut curves: Vec<Vec<(f64, f64, f64)>> = Vec::new();
    let mut space_offsets: Vec<usize> = Vec::new();
    let node_bytes: usize = decoded.values().map(|m| m.rep.payload_len).sum();
    let positions: Vec<usize> = nodes.iter().map(|n| n.pos).collect();
    let mut reps_decoded = 0usize;
    let mut reps_exported = 0usize;
    for (k, node_pos) in rep_nodes.iter().copied().enumerate() {
        let Some(node_pos) = node_pos else {
            reps_unexported.push(format!(
                "rep {k}: the pool group's rep node (missing) has no \
                 law-decoded region (per-rep absorption unestablished)"
            ));
            continue;
        };
        let Some(m) = decoded.get(&node_pos) else {
            reps_unexported.push(format!(
                "rep {k}: the pool group's rep node at {node_pos} has no \
                 law-decoded region (per-rep absorption unestablished)"
            ));
            continue;
        };
        reps_decoded += 1;
        let d = &m.rep;
        // A rep's territory ends at the NEXT TOKEN NODE (decoded or
        // not), so an undecoded node's records are never attributed to
        // its predecessor.
        let nxt = positions
            .iter()
            .copied()
            .filter(|&p| p > d.pos)
            .min()
            .unwrap_or(hi);
        let (records, n_hdrs) =
            parse_strip_records(data, d.region_end, nxt, d.elem, Some(&d.elements));
        let (ext_k, ext_cands) = parse_extended_facet_records(
            data,
            d.region_end,
            nxt,
            d.elem,
            Some(&d.elements),
            &short_record_spans(data, nxt, &records),
        );
        let mut grefs: Vec<u32> = records
            .iter()
            .filter(|r| GATED.contains(&r.marker))
            .flat_map(|r| r.refs.iter().copied())
            .collect();
        grefs.extend(ext_k.iter().flat_map(|r| r.refs.iter().copied()));
        if let Some(&mx) = grefs.iter().max()
            && mx >= d.elem
        {
            reps_unexported.push(format!(
                "rep {k}: facet references beyond the rep's element \
                 space (max ref {mx} >= element count {}, \
                 M2b identity per rep)",
                d.elem
            ));
            continue;
        }
        let base = points.len();
        space_offsets.push(base);
        let tri_res = triangulate(&d.elements, &records, &ext_k, seam_area, relist_skip);
        // The per-loop dup-pin weld (see decode_per_rep).
        if let Some(dp) = &tri_res.dup_pin {
            reps_dup_pin.push((base, dp.clone()));
        }
        points.extend(d.pts.iter().copied());
        triangles.extend(
            tri_res
                .triangles
                .iter()
                .map(|&(a, b, c)| (a + base as u32, b + base as u32, c + base as u32)),
        );
        degenerate += tri_res.degenerate;
        loops_exported += tri_res.loops_exported;
        loops_curve_entry += tri_res.loops_curve_entry;
        primary_loop_skips += tri_res.primary_loop_skips;
        primary_loop_kept += tri_res.primary_loop_kept;
        if !tri_res.kept_loop_tris.is_empty() {
            for &(a, b, c) in &tri_res.kept_loop_tris {
                kept_loop_tris.push((a + base as u32, b + base as u32, c + base as u32));
            }
            kept_loop_count += tri_res.kept_loop_count;
            relist_forced_total += tri_res.relist_forced;
        }
        relaxed_loops_accepted += tri_res.relaxed_loops_accepted;
        relaxed_loops_declined += tri_res.relaxed_loops_declined;
        // The §2.3 curve exposure: this exported rep's dropped loops'
        // pre-weld sequences (additive, outside Fidelity).
        for (_mk, _normal, loop_refs) in &tri_res.dropped_loops {
            curves.push(curve_sequence(loop_refs, &d.elements));
        }
        facet_candidates += n_hdrs + ext_cands;
        facet_records += records.len() + ext_k.len();
        ext_records += ext_k.len();
        ext_triangles += tri_res.extended_triangles as usize;
        ext_filtered += tri_res.extended_members_filtered as usize;
        ext_declined += tri_res.extended_declined as usize;
        write_count += d.write_count as usize;
        // the twin's ``table_bytes += (d["elem"] + 3) // 4`` — the
        // table-law reps' declared table length only
        #[allow(clippy::manual_div_ceil)]
        if m.law == "table" {
            table_bytes += (d.elem as usize + 3) / 4;
        }
        element_decl += d.elem as usize;
        curve_entries += d.elements.len() - d.pts.len();
        reps_exported += 1;
        for rec in &records {
            if !EXPORTED_SHORT_MARKERS.contains(&rec.marker)
                && !RELAXED_SHORT_MARKERS.contains(&rec.marker)
            {
                *skipped_markers.entry(rec.marker).or_insert(0) += 1;
            }
        }
    }
    if points.is_empty() {
        return Err(ExportError::new(
            UNDECODED_VARIANT,
            format!(
                "the stage-8 mixed-write per-rep composition exports no \
                 rep: {}",
                if reps_unexported.is_empty() {
                    "no reps".to_string()
                } else {
                    reps_unexported.join("; ")
                }
            ),
        ));
    }
    // The dup-pin weld at the store level (see decode_per_rep).
    let mut curve_entry_law = 0u32;
    for (b, dp) in &reps_dup_pin {
        if dp.loops == 0 {
            continue;
        }
        triangles.extend(
            dp.triangles
                .iter()
                .map(|&(a, s, t)| (a + *b as u32, s + *b as u32, t + *b as u32)),
        );
        degenerate += dp.degenerate;
        loops_exported += dp.loops;
        loops_curve_entry -= dp.loops;
        curve_entry_law += dp.loops;
    }
    let mut info = CompositeInfo {
        primary_loop_relist_skips: None,
        primary_loop_relist_boundary: None,
        stage: "identity-mixedwrite-reps",
        element_decl,
        node_points: points.len(),
        curve_entries,
        write_count: Some(write_count),
        table_bytes: Some(table_bytes),
        facet_candidates,
        facet_records,
        skipped_markers,
        node_bytes,
        reps_decoded: Some(reps_decoded),
        reps_exported: Some(reps_exported),
        reps_unexported: Some(reps_unexported.len()),
        rep_reasons: Some(reps_unexported),
        rep_laws: Some(law_counts),
        raw_start: None,
        raw_nice_rate: None,
        raw_x_asc_rate: None,
        raw_trail_bytes: None,
        raw_count3: None,
        loops_exported,
        loops_curve_entry,
        extended_header_records: None,
        extended_header_triangles: None,
        extended_header_declined: None,
        extended_members_filtered: None,
        curve_entry_law: None,
        loops_curve_entry_exported: None,
        primary_loop_skips: None,
        relaxed_loops_accepted: None,
        relaxed_loops_declined: None,
        primary_loop_seam_declined: None,
        primary_loop_kept: None,
        unordered_dedup_dropped: None,
        unordered_dedup_declined: None,
        multiregion_reps: None,
        multiregion_extent_reps: None,
        multiregion_container_reps: None,
        multiregion_declined: None,
    };
    if ext_records > 0 {
        info.extended_header_records = Some(ext_records);
        info.extended_header_triangles = Some(ext_triangles);
        if ext_declined > 0 {
            info.extended_header_declined = Some(ext_declined);
        }
        if ext_filtered > 0 {
            info.extended_members_filtered = Some(ext_filtered);
        }
    }
    if primary_loop_skips > 0 {
        info.primary_loop_skips = Some(primary_loop_skips);
    }
    if primary_loop_kept > 0 {
        info.primary_loop_kept = Some(primary_loop_kept);
    }
    if relaxed_loops_accepted > 0 || relaxed_loops_declined > 0 {
        // the twin emits BOTH keys whenever either counter is nonzero
        info.relaxed_loops_accepted = Some(relaxed_loops_accepted);
        info.relaxed_loops_declined = Some(relaxed_loops_declined);
    }
    if curve_entry_law > 0 {
        info.curve_entry_law = Some("e0b-dup-pin");
        info.loops_curve_entry_exported = Some(curve_entry_law);
    }
    // The disjoint per-rep index spaces, in emission order (see the
    // decode_per_rep note above).
    Ok(CompositeDecode {
        kept_loop_tris,
        kept_loop_count,
        relist_forced: relist_forced_total,
        points,
        triangles,
        degenerate,
        info,
        curves,
        space_offsets,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::geometry::store::{CONTAINER_STDCONT, ORIGIN_KIND_HEADER, TAIL_LAW_SHIPPED};

    /// The twin's ``_nice`` constants, verbatim.
    #[test]
    fn nice_predicate_is_the_twin_expression() {
        assert!(nice(0.0));
        assert!(nice(-1e-15));
        assert!(nice(1e9 - 1.0));
        assert!(!nice(1e9));
        assert!(!nice(f64::NAN));
        assert!(!nice(f64::INFINITY));
        assert!(!nice(f64::NEG_INFINITY));
    }

    /// The twin's ``read_count``: one byte, ff escaping to u32le; the
    /// escape branch's short-slice tolerance (a payload ending inside
    /// the count parses what is there).
    #[test]
    fn p1g_count_escapes_ff_to_u32le() {
        let data = [0x05u8, 0xFF, 0x11, 0x22, 0x33, 0x44, 0x00];
        assert_eq!(read_count(&data, 0), (5, 1));
        assert_eq!(read_count(&data, 1), (0x44332211, 6));
        // A truncated escape: one count byte, value 0x11.
        assert_eq!(read_count(&data[..3], 1), (0x11, 6));
    }

    /// The twin's ``table_slots``: LSB-first 2-bit extraction, one
    /// slot per element, truncated to the element count.
    #[test]
    fn table_slots_are_lsb_first_and_truncated() {
        // bytes 0b11100100 -> slots [0, 1, 2, 3]; 0b00011011 -> [3, 2, 1, 0]
        let payload = [0b11_10_01_00u8, 0b00_01_10_11u8];
        let slots = table_slots(&payload, 0, 2, 6);
        assert_eq!(slots, vec![0, 1, 2, 3, 3, 2]);
    }

    /// The origin-state walk: a [z]-write element carries the
    /// previous element's x, y (the LCP law, P1i subsumed) and only
    /// the written values are nice-checked.
    #[test]
    fn region_walk_carries_the_lcp_state() {
        // 3 elements: [x][y][z] = (1, 2, 3), skip, [z] = 7 -> the
        // third element's point is (1, 2, 7). The payload opens with
        // the list token + the two P1g counts (one byte each), the
        // zero block, the 2-bit table (slots 0, 1, 2 LSB-first = 0x24)
        // and the declared write count (4 f32 words).
        let mut payload = Vec::new();
        payload.extend_from_slice(LIST_TOKEN);
        payload.push(3); // c1 (element_count)
        payload.push(3); // c2 (edge_ref_bound)
        payload.extend_from_slice(&[0x00; 4]); // zero block
        payload.push(0b00_10_01_00); // slots: [0, 1, 2] LSB-first
        payload.push(4); // write count = 4 words
        payload.extend_from_slice(&1.0f32.to_le_bytes());
        payload.extend_from_slice(&2.0f32.to_le_bytes());
        payload.extend_from_slice(&3.0f32.to_le_bytes());
        payload.extend_from_slice(&7.0f32.to_le_bytes());
        let (elements, info) = decode_region(&payload, 3).unwrap();
        assert_eq!(info.write_count, 4);
        // walk_end is payload-relative: token(5) + counts(2) + zero
        // block(4) + table(1) + count(1) + region(16) = 29.
        assert_eq!(info.walk_end, 29);
        assert_eq!(elements[0], (0, Some((1.0, 2.0, 3.0))));
        assert_eq!(elements[1], (1, None));
        assert_eq!(elements[2], (2, Some((1.0, 2.0, 7.0))));
    }

    /// The per-loop dup-pin weld: a loop-referenced skip slot welds to
    /// the immediately preceding written element; element 0 (no
    /// predecessor) is unpinnable and refused (per loop — no store
    /// veto).
    #[test]
    fn dup_pin_welds_to_the_preceding_written_element() {
        let elements: Vec<Element> = vec![
            (0, Some((0.0, 0.0, 0.0))),
            (1, None), // the curve entry
            (0, Some((1.0, 0.0, 0.0))),
            (0, Some((0.0, 1.0, 0.0))),
        ];
        let mut written_rank = HashMap::new();
        for (i, (_v, pt)) in elements.iter().enumerate() {
            if pt.is_some() {
                written_rank.insert(i, written_rank.len());
            }
        }
        let points: Vec<(f64, f64, f64)> = elements.iter().filter_map(|e| e.1).collect();
        // One dropped loop referencing the skip slot 1.
        let dropped = vec![(0x4Au8, None, vec![1u32, 2, 3])];
        let pin = e0b_dup_pin(&elements, &points, &written_rank, &dropped, &[]);
        assert_eq!(pin.loops, 1);
        assert_eq!(pin.refused, 0);
        // The skip slot resolved to element 0 (its predecessor): the
        // loop's ranks are [0, 1, 2] -> one strip triangle.
        assert_eq!(pin.triangles, vec![(0u32, 1u32, 2u32)]);
        // Element 0 as a skip slot: no preceding written element.
        let elements0: Vec<Element> = vec![(1, None), (0, Some((1.0, 2.0, 3.0)))];
        let mut rank0 = HashMap::new();
        for (i, (_v, pt)) in elements0.iter().enumerate() {
            if pt.is_some() {
                rank0.insert(i, rank0.len());
            }
        }
        let points0: Vec<(f64, f64, f64)> = elements0.iter().filter_map(|e| e.1).collect();
        let dropped0 = vec![(0x4Au8, None, vec![0u32, 1])];
        let pin0 = e0b_dup_pin(&elements0, &points0, &rank0, &dropped0, &[]);
        assert_eq!(pin0.loops, 0);
        assert_eq!(pin0.refused, 1);
    }

    /// The per-loop battery and mesh guard (2026-11-18, twin parity):
    /// a NONPLANAR loop under the dup pin is refused; a coplanar loop
    /// whose fan would push an edge past two uses is refused; a
    /// disjoint coplanar loop welds; a degenerate emission refuses.
    #[test]
    fn dup_pin_battery_and_mesh_guard_refuse_fail_closed() {
        // Four written points on y=0 plus one skip slot at index 4
        // (pins to element 3).  The coplanar fan (0,1,3) touches edge
        // {0,1}; the base mesh already uses {0,1} twice -> guard
        // refuses.
        let elements: Vec<Element> = vec![
            (0, Some((0.0, 0.0, 0.0))),
            (0, Some((1.0, 0.0, 0.0))),
            (0, Some((0.0, 1.0, 0.0))),
            (0, Some((1.0, 1.0, 0.0))),
            (1, None),
        ];
        let mut written_rank = HashMap::new();
        for (i, (_v, pt)) in elements.iter().enumerate() {
            if pt.is_some() {
                written_rank.insert(i, written_rank.len());
            }
        }
        let points: Vec<(f64, f64, f64)> = elements.iter().filter_map(|e| e.1).collect();
        // A 0x4c fan over [skip(->3), 0, 1] -> triangle (3,0,1).
        let coplanar = (0x4Cu8, Some((0.0, 0.0, 1.0)), vec![4u32, 0, 1]);
        // Base mesh uses {0,1} twice (two triangles over 0-1).
        let base = vec![(0u32, 1u32, 2u32), (1u32, 0u32, 3u32)];
        let pin = e0b_dup_pin(
            &elements,
            &points,
            &written_rank,
            &[coplanar.clone()],
            &base,
        );
        assert_eq!(pin.loops, 0);
        assert_eq!(pin.refused, 1);
        // With no base over-use the same loop welds.
        let pin = e0b_dup_pin(&elements, &points, &written_rank, &[coplanar], &[]);
        assert_eq!(pin.loops, 1);
        assert_eq!(pin.triangles, vec![(3u32, 0u32, 1u32)]);
        // Nonplanar under the stored normal is refused by the battery:
        // the loop (3,0,1) is not coplanar against the x normal.
        let tilted = (0x4Cu8, Some((1.0, 0.0, 0.0)), vec![4u32, 0, 1]);
        let pin = e0b_dup_pin(&elements, &points, &written_rank, &[tilted], &[]);
        assert_eq!(pin.loops, 0);
        assert_eq!(pin.refused, 1);
        // A degenerate emission (repeated coordinates) refuses.
        let degenerate = (0x42u8, None, vec![4u32, 3, 3]);
        let pin = e0b_dup_pin(&elements, &points, &written_rank, &[degenerate], &[]);
        assert_eq!(pin.loops, 0);
        assert_eq!(pin.refused, 1);
    }

    /// The W16 A4 emission law (2026-11-22, the twin of
    /// ``_e0b_dup_pin``'s split): the dup-pinned strip (P, X, P, Y)
    /// collapses its first triangle and its second is real surface —
    /// the split welds the real remainder behind the same mesh guard
    /// and counts the collapsed half; the old whole-loop refusal
    /// dropped both.
    #[test]
    fn dup_pin_degenerate_quad_splits_the_real_remainder() {
        let elements: Vec<Element> = vec![
            (0, Some((0.0, 10.0, 0.0))),  // e0 = P0, rank 0
            (0, Some((0.0, 10.0, 30.0))), // e1 = P1, rank 1
            (1, None),                    // e2 skip -> pins to e1 (P1)
            (0, Some((0.0, 10.0, 60.0))), // e3 = P2, rank 2
            (0, Some((0.0, 110.0, 0.0))), // e4 = P3, rank 3
        ];
        let mut written_rank = HashMap::new();
        for (i, (_v, pt)) in elements.iter().enumerate() {
            if pt.is_some() {
                written_rank.insert(i, written_rank.len());
            }
        }
        let points: Vec<(f64, f64, f64)> = elements.iter().filter_map(|e| e.1).collect();
        // The 0x42 strip loop (skip, 0, 1, 4): resolved [1, 0, 1, 4],
        // ranks [1, 0, 1, 3] — triangle (1,0,1) collapses (repeated
        // coordinate), triangle (0,1,3) flipped (3,1,0) is real.
        let dropped = vec![(0x42u8, None, vec![2u32, 0, 1, 4])];
        let pin = e0b_dup_pin(&elements, &points, &written_rank, &dropped, &[]);
        assert_eq!(pin.loops, 1);
        assert_eq!(pin.refused, 0);
        assert_eq!(pin.degenerate, 1);
        assert_eq!(pin.triangles, vec![(3u32, 1u32, 0u32)]);
        // A loop whose EVERY triangle collapses has nothing real to
        // weld and stays dropped (the fail-closed arm).
        let all_degen = vec![(0x42u8, None, vec![2u32, 0, 1, 3])];
        let pin = e0b_dup_pin(&elements, &points, &written_rank, &all_degen, &[]);
        assert_eq!(pin.loops, 0);
        assert_eq!(pin.refused, 1);
    }

    /// The stage-15 unordered-triangle dedup: fires on a not-manifold
    /// mesh whose duplicate unordered triple resolves it; declines
    /// when the duplicates do not explain the over-use; a manifold
    /// mesh is never touched; degenerate-shaped triples never dedup.
    #[test]
    fn unordered_dedup_fires_declines_and_passes_through() {
        // A dup + a third triangle over-using {0,1}: not-manifold; the
        // dup's removal resolves it.
        let mut info = CompositeInfo {
            primary_loop_relist_skips: None,
            primary_loop_relist_boundary: None,
            stage: "identity-table-walk",
            element_decl: 4,
            node_points: 4,
            curve_entries: 0,
            write_count: None,
            table_bytes: None,
            facet_candidates: 0,
            facet_records: 0,
            skipped_markers: BTreeMap::new(),
            node_bytes: 0,
            reps_decoded: None,
            reps_exported: None,
            reps_unexported: None,
            rep_reasons: None,
            rep_laws: None,
            raw_start: None,
            raw_nice_rate: None,
            raw_x_asc_rate: None,
            raw_trail_bytes: None,
            raw_count3: None,
            loops_exported: 0,
            loops_curve_entry: 0,
            extended_header_records: None,
            extended_header_triangles: None,
            extended_header_declined: None,
            extended_members_filtered: None,
            primary_loop_skips: None,
            relaxed_loops_accepted: None,
            relaxed_loops_declined: None,
            primary_loop_seam_declined: None,
            primary_loop_kept: None,
            curve_entry_law: None,
            loops_curve_entry_exported: None,
            unordered_dedup_dropped: None,
            unordered_dedup_declined: None,
            multiregion_reps: None,
            multiregion_extent_reps: None,
            multiregion_container_reps: None,
            multiregion_declined: None,
        };
        let pts: Vec<(f64, f64, f64)> = vec![
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
            (1.0, 1.0, 0.0),
        ];
        let tris = vec![(0u32, 1u32, 2u32), (2, 1, 0), (0, 1, 3)];
        let kept = apply_unordered_dedup(tris, &mut info, &pts, &[]);
        assert_eq!(kept, vec![(0, 1, 2), (0, 1, 3)]);
        assert_eq!(info.unordered_dedup_dropped, Some(1));
        assert_eq!(info.unordered_dedup_declined, None);
        // Declined: a fin that is NOT a duplicate keeps the mesh
        // over-used after the dup's removal.
        let mut info2 = info.clone();
        info2.unordered_dedup_dropped = None;
        info2.unordered_dedup_declined = None;
        let tris2 = vec![(0u32, 1u32, 2u32), (2, 1, 0), (0, 1, 3), (1, 0, 4)];
        let kept2 = apply_unordered_dedup(tris2, &mut info2, &pts, &[]);
        assert_eq!(kept2, vec![(0, 1, 2), (2, 1, 0), (0, 1, 3), (1, 0, 4)]);
        assert_eq!(info2.unordered_dedup_dropped, None);
        assert_eq!(info2.unordered_dedup_declined, Some(1));
        // A manifold two-sided sheet never fires (the zero-regression
        // direction).
        let mut info3 = info.clone();
        info3.unordered_dedup_dropped = None;
        let sheet = vec![(0u32, 1u32, 2u32), (2, 1, 0)];
        let kept3 = apply_unordered_dedup(sheet, &mut info3, &pts, &[]);
        assert_eq!(kept3, vec![(0, 1, 2), (2, 1, 0)]);
        assert_eq!(info3.unordered_dedup_dropped, None);
        // Degenerate-shaped triples are never deduped.
        let mut info4 = info.clone();
        info4.unordered_dedup_dropped = None;
        let degenerate = vec![(0u32, 0u32, 1u32), (0, 0, 1)];
        let kept4 = apply_unordered_dedup(degenerate, &mut info4, &pts, &[]);
        assert_eq!(kept4, vec![(0, 0, 1), (0, 0, 1)]);
    }

    /// The coordinate-identity arm (2026-11-18): two per-rep element
    /// spaces whose written coordinates coincide. The later space's
    /// re-listed triangle is a coordinate duplicate (never an index
    /// duplicate — the spaces are disjoint), and the EARLIER space's
    /// copy wins even when it sits LATER in the emission list (its
    /// welded loops are appended last, so list order is not the rule).
    /// Dropping the copy is area-preserving: the two triangles are the
    /// same three points.
    #[test]
    fn unordered_dedup_matches_coordinates_across_disjoint_spaces() {
        let mut info = CompositeInfo {
            primary_loop_relist_skips: None,
            primary_loop_relist_boundary: None,
            stage: "identity-per-rep",
            element_decl: 8,
            node_points: 8,
            curve_entries: 0,
            write_count: None,
            table_bytes: None,
            facet_candidates: 0,
            facet_records: 0,
            skipped_markers: BTreeMap::new(),
            node_bytes: 0,
            reps_decoded: None,
            reps_exported: None,
            reps_unexported: None,
            rep_reasons: None,
            rep_laws: None,
            raw_start: None,
            raw_nice_rate: None,
            raw_x_asc_rate: None,
            raw_trail_bytes: None,
            raw_count3: None,
            loops_exported: 0,
            loops_curve_entry: 0,
            extended_header_records: None,
            extended_header_triangles: None,
            extended_header_declined: None,
            extended_members_filtered: None,
            primary_loop_skips: None,
            relaxed_loops_accepted: None,
            relaxed_loops_declined: None,
            primary_loop_seam_declined: None,
            primary_loop_kept: None,
            curve_entry_law: None,
            loops_curve_entry_exported: None,
            unordered_dedup_dropped: None,
            unordered_dedup_declined: None,
            multiregion_reps: None,
            multiregion_extent_reps: None,
            multiregion_container_reps: None,
            multiregion_declined: None,
        };
        // Space 0 = points 0..3, space 1 = points 3..8 (joint at 3).
        // Points 3..6 carry exactly the coordinates of points 0..2.
        let pts: Vec<(f64, f64, f64)> = vec![
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (1.0, 1.0, 0.0),
            (2.0, 0.0, 0.0),
        ];
        // Space 1's re-listing (3,4,5) is first in the list; the fin
        // triangles (3,6,4) and (3,7,4) push the edge {3,4} to three
        // uses. Space 0's copy (0,1,2) comes LAST (the weld position).
        let tris = vec![(3u32, 4u32, 5u32), (3, 6, 4), (3, 7, 4), (0, 1, 2)];
        let kept = apply_unordered_dedup(tris, &mut info, &pts, &[0, 3]);
        assert_eq!(kept, vec![(3, 6, 4), (3, 7, 4), (0, 1, 2)]);
        assert_eq!(info.unordered_dedup_dropped, Some(1));
        // Same list, one index space (no offsets): the list-order copy
        // wins, so the fin's edge keeps three uses and the dedup
        // DECLINES (fail-closed — the emitted list is kept verbatim).
        let mut info2 = info.clone();
        info2.unordered_dedup_dropped = None;
        info2.unordered_dedup_declined = None;
        let tris2 = vec![(3u32, 4u32, 5u32), (3, 6, 4), (3, 7, 4), (0, 1, 2)];
        let kept2 = apply_unordered_dedup(tris2, &mut info2, &pts, &[]);
        assert_eq!(info2.unordered_dedup_dropped, None);
        assert_eq!(info2.unordered_dedup_declined, Some(1));
        assert_eq!(kept2.len(), 4);
        // A manifold two-sided sheet is never touched, even though its
        // two triangles are coordinate twins (the zero-regression
        // direction: the fire gate's pre-condition is not-manifold).
        let mut info3 = info.clone();
        info3.unordered_dedup_dropped = None;
        info3.unordered_dedup_declined = None;
        let sheet = vec![(0u32, 1u32, 2u32), (3, 5, 4)];
        let kept3 = apply_unordered_dedup(sheet, &mut info3, &pts, &[0, 3]);
        assert_eq!(kept3, vec![(0, 1, 2), (3, 5, 4)]);
        assert_eq!(info3.unordered_dedup_dropped, None);
        assert_eq!(info3.unordered_dedup_declined, None);
    }

    /// The §2.3 curve exposure: a dropped loop's pre-weld sequence is
    /// its WRITTEN elements' coordinates in loop order (the skip slot
    /// contributes nothing — U4 open, the weld never applied).
    #[test]
    fn curve_sequence_is_preweld_written_elements_only() {
        let elements: Vec<Element> = vec![
            (0, Some((1.0, 2.0, 3.0))),
            (1, None), // the curve entry: no coordinates in the region
            (0, Some((4.0, 5.0, 6.0))),
        ];
        let seq = curve_sequence(&[0, 1, 2, 0], &elements);
        assert_eq!(seq, vec![(1.0, 2.0, 3.0), (4.0, 5.0, 6.0), (1.0, 2.0, 3.0)]);
    }

    /// The twin's ``round(rate, 4)`` ground truth (Python's
    /// correct-rounding of the exact binary value, ties-to-even):
    /// values computed with ``python3 -c`` on the corpus machine.
    #[test]
    fn py_round4_matches_python() {
        let cases: [(f64, f64); 10] = [
            (157.0 / 160.0, 0.9812), // 0.98124999... -> 0.9812
            (31.0 / 32.0, 0.9688),   // exact 0.96875, tie -> up (odd digit)
            (63.0 / 64.0, 0.9844),   // exact 0.984375 -> digit5=7
            (127.0 / 128.0, 0.9922),
            (41.0 / 42.0, 0.9762),
            (5.0 / 6.0, 0.8333),
            (0.98, 0.98),
            (0.987654321, 0.9877),
            (137.0 / 140.0, 0.9786),
            (1.0, 1.0),
        ];
        for (x, expected) in cases {
            assert_eq!(py_round4(x), expected, "py_round4({x})");
        }
    }

    /// The ``-0.0 == 0.0`` set collapse: the twin's set membership
    /// treats the two as one element (:fn:`vkey`).
    #[test]
    fn vkey_collapses_negative_zero() {
        assert_eq!(vkey((0.0, 1.0, 2.0)), vkey((-0.0, 1.0, 2.0)));
        assert_ne!(vkey((0.0, 1.0, 2.0)), vkey((0.0, 1.0, 3.0)));
    }

    /// The noise-aware absorption test: the exact expression shape
    /// (``max(1.0, abs...)`` scale, per-coordinate relative delta).
    #[test]
    fn tol_match_scales_by_the_twin_expression() {
        let pts = vec![(1.0, 2.0, 3.0)];
        // exact match
        assert_eq!(tol_match((1.0, 2.0, 3.0), &pts), Some(0.0));
        // within NOISE_REL: 1e-9 relative on each coordinate
        let noisy = (1.0 + 1e-9, 2.0 + 1e-9, 3.0 + 1e-9);
        let best = tol_match(noisy, &pts).unwrap();
        assert!(best <= NOISE_REL);
        // a genuinely different vertex is 4 decades above the bar
        let far = (1.0 + 1e-3, 2.0, 3.0);
        assert!(tol_match(far, &pts).unwrap() > NOISE_REL);
        // empty points: None (kept as unmatched)
        assert_eq!(tol_match(noisy, &[]), None);
    }

    /// One extended-header record: ``01 mk ty b3 b4 ff | u32le n |
    /// [normal] | counts | refs``.
    fn extended_record(
        marker: u8,
        ty: u8,
        b3: u8,
        b4: u8,
        counts: &[u8],
        normal: Option<(f32, f32, f32)>,
        refs: &[u16],
    ) -> Vec<u8> {
        let mut out = vec![0x01, marker, ty, b3, b4, 0xFF];
        out.extend_from_slice(&(refs.len() as u32).to_le_bytes());
        if let Some((x, y, z)) = normal {
            out.extend_from_slice(&x.to_le_bytes());
            out.extend_from_slice(&y.to_le_bytes());
            out.extend_from_slice(&z.to_le_bytes());
        }
        out.extend_from_slice(counts);
        for r in refs {
            out.extend_from_slice(&r.to_be_bytes());
        }
        out
    }

    /// The escaped-header forms (#64, 2026-11-20): `ty`/`b3`/`b4` may
    /// each escape via read_count before the fixed `ff` + `u32le n`;
    /// repeats are ranked (strip joins are real geometry), and the
    /// winner's refs must resolve in-bounds.
    #[test]
    fn parse_extended_records_admits_the_p1g_escaped_header() {
        // ty escaped (ff + u32le = 1), b3 = 1, b4 = 0, counts [3],
        // n = 6; the strip loop repeats ref 1 (a strip join).
        let mut body = vec![
            0x01, 0x47, 0xFF, 1, 0, 0, 0, 0x01, 0x00, 0xFF, 6, 0, 0, 0, 3,
        ];
        for r in [0u32, 1, 2, 3, 1, 4] {
            body.extend_from_slice(&(r as u16).to_be_bytes());
        }
        let (records, candidates) =
            parse_extended_facet_records(&body, 0, body.len(), 64, None, &[]);
        assert_eq!(candidates, 1);
        assert_eq!(records.len(), 1);
        let rec = &records[0];
        assert_eq!(rec.triangles, 1);
        assert_eq!(rec.strips, 1);
        assert_eq!(rec.counts, vec![3]);
        assert_eq!(rec.refs, vec![0, 1, 2, 3, 1, 4]);
        assert_eq!(rec.width, 2);
        assert_eq!(rec.end, body.len());
        // Out-of-range refs at the winning width: unresolved.
        let mut bad = vec![
            0x01, 0x47, 0xFF, 1, 0, 0, 0, 0x01, 0x00, 0xFF, 6, 0, 0, 0, 3,
        ];
        for r in [0u32, 1, 2, 3, 1, 0xFFFF] {
            bad.extend_from_slice(&(r as u16).to_be_bytes());
        }
        let (records, candidates) = parse_extended_facet_records(&bad, 0, bad.len(), 64, None, &[]);
        assert_eq!(candidates, 1);
        assert!(records.is_empty());
        // The b3-escaped (+3) and b4-escaped (+4) shapes.
        let mut b3esc = vec![0x01, 0x4F, 0x01, 0xFF, 1, 0, 0, 0, 0x00, 0xFF, 6, 0, 0, 0];
        // the 12-B normal rides right after n; the counts follow.
        b3esc.extend_from_slice(&0.0f32.to_le_bytes());
        b3esc.extend_from_slice(&0.0f32.to_le_bytes());
        b3esc.extend_from_slice(&1.0f32.to_le_bytes());
        b3esc.push(3);
        for r in [0u32, 1, 2, 3, 4, 5] {
            b3esc.extend_from_slice(&(r as u16).to_be_bytes());
        }
        let (records, _c) = parse_extended_facet_records(&b3esc, 0, b3esc.len(), 64, None, &[]);
        assert_eq!(records.len(), 1);
        assert_eq!(records[0].strips, 1);
        assert_eq!(records[0].normal, Some((0.0, 0.0, 1.0)));
        let mut b4esc = vec![
            0x01, 0x47, 0x01, 0x00, 0xFF, 1, 0, 0, 0, 0xFF, 6, 0, 0, 0, 3,
        ];
        b4esc.push(3);
        for r in [0u32, 1, 2, 3, 4, 5] {
            b4esc.extend_from_slice(&(r as u16).to_be_bytes());
        }
        let (records, _c) = parse_extended_facet_records(&b4esc, 0, b4esc.len(), 64, None, &[]);
        assert_eq!(records.len(), 1);
        assert_eq!(records[0].polygons, 1);
    }

    /// The extended-header law (2026-11-18): ``ty`` independent
    /// triangles, ``b3 + b4`` counts, ``sum(counts) + 3*ty == n``;
    /// out-of-range refs are a false-positive pattern, not the family.
    #[test]
    fn parse_extended_records_pins_the_header_law() {
        let refs: Vec<u16> = (0..18).collect();
        let body = extended_record(0x4F, 2, 1, 1, &[5, 7], Some((0.0, 0.0, 1.0)), &refs);
        let (records, candidates) =
            parse_extended_facet_records(&body, 0, body.len(), 64, None, &[]);
        assert_eq!(candidates, 1);
        let rec = &records[0];
        assert_eq!(rec.marker, 0x4F);
        assert_eq!(rec.triangles, 2);
        assert_eq!(rec.strips, 1);
        assert_eq!(rec.polygons, 1);
        assert_eq!(rec.counts, vec![5, 7]);
        assert_eq!(
            rec.refs,
            refs.iter().map(|&r| u32::from(r)).collect::<Vec<_>>()
        );
        assert_eq!(rec.normal, Some((0.0, 0.0, 1.0)));
        assert_eq!(rec.end, body.len());
        // The sum law is load-bearing: one extra ref is not the family.
        let bad = extended_record(0x47, 2, 1, 1, &[5, 7], None, &(0..19).collect::<Vec<_>>());
        assert!(
            parse_extended_facet_records(&bad, 0, bad.len(), 64, None, &[])
                .0
                .is_empty()
        );
        // Out-of-range refs: the candidate stays unresolved.
        let oob = extended_record(0x47, 1, 1, 0, &[3], None, &[0, 1, 2, 0, 1, 0xFFFF]);
        let (records, candidates) = parse_extended_facet_records(&oob, 0, oob.len(), 64, None, &[]);
        assert_eq!(candidates, 1);
        assert!(records.is_empty());
    }

    /// The primary-emit seam (2026-11-18, #34): a candidate loop over
    /// an edge the primary mesh already uses twice is refused by the
    /// incremental guard; the area rule then decides — a sliver
    /// (<= 1% of the store area) is dropped, a larger over-use is real
    /// surface and is kept exactly as before.  ``seam_area: None``
    /// disables the seam (the registry pass), so every refused loop is
    /// kept.
    #[test]
    fn primary_seam_skips_tiny_overuse_and_keeps_large() {
        let elements: Vec<Element> = vec![
            (0, Some((0.0, 0.0, 0.0))),
            (0, Some((10.0, 0.0, 0.0))),
            (0, Some((10.0, 10.0, 0.0))),
            (0, Some((0.0, 10.0, 0.0))),
            // 1 µm off the (1, 2) edge: a 0.005 mm² sliver
            (0, Some((10.001, 5.0, 0.0))),
            // 5 mm off it: 25 mm², 25% of the quad
            (0, Some((15.0, 5.0, 0.0))),
        ];
        let quad = CompositeRecord {
            offset: 0,
            marker: 0x42,
            normal: None,
            counts: vec![4],
            refs: vec![0, 1, 2, 3],
            width: 1,
        };
        let tiny = CompositeRecord {
            offset: 1,
            marker: 0x42,
            normal: None,
            counts: vec![3],
            refs: vec![1, 2, 4],
            width: 1,
        };
        let large = CompositeRecord {
            offset: 2,
            marker: 0x42,
            normal: None,
            counts: vec![3],
            refs: vec![1, 2, 5],
            width: 1,
        };
        let records = vec![quad.clone(), tiny.clone(), large.clone()];
        // The quad's two triangles are 50 mm² each; both candidates
        // over-use its (1, 2) edge (used twice already).
        let tri = triangulate(&elements, &records, &[], Some(100.0), false);
        assert_eq!(tri.triangles.len(), 3); // quad + the large fin
        assert_eq!(tri.primary_loop_skips, 1); // the 0.005 mm² sliver
        assert_eq!(tri.primary_loop_kept, 1); // the 25 mm² fin
        assert!(!mesh::mesh_stats(&tri.triangles).manifold);
        // The seam off (the registry pass): every refused loop is kept.
        let all = triangulate(&elements, &records, &[], None, false);
        assert_eq!(all.triangles.len(), 4);
        assert_eq!(all.primary_loop_skips, 0);
        assert_eq!(all.primary_loop_kept, 2);
        // A store whose only refused loops are slivers becomes
        // manifold: drop the large record and the quad remains.
        let sliver_only = triangulate(&elements, &[quad, tiny], &[], Some(100.0), false);
        assert_eq!(sliver_only.triangles.len(), 2);
        assert_eq!(sliver_only.primary_loop_skips, 1);
        assert_eq!(sliver_only.primary_loop_kept, 0);
        assert!(mesh::mesh_stats(&sliver_only.triangles).manifold);
    }

    /// The extended split: soup triples first (not loops), then the
    /// first ``b3`` loops as strips and the last ``b4`` as polygons —
    /// emitted only when the assembled mesh stays manifold; a record
    /// that would tip an edge past two uses is declined as a whole.
    #[test]
    fn triangulate_extended_soup_strips_polygons() {
        let elements: Vec<Element> = vec![
            (0, Some((0.0, 0.0, 0.0))),
            (0, Some((1.0, 0.0, 0.0))),
            (0, Some((0.0, 1.0, 0.0))),
            (0, Some((1.0, 0.0, 1.0))),
            (0, Some((0.0, 0.0, 1.0))),
            (0, Some((0.0, 1.0, 1.0))),
            (0, Some((2.0, 0.0, 0.0))),
            (0, Some((3.0, 0.0, 0.0))),
            (0, Some((3.0, 1.0, 0.0))),
            (0, Some((2.0, 1.0, 0.0))),
        ];
        let rec = ExtendedFacetRecord {
            offset: 0,
            marker: 0x47,
            triangles: 1,
            strips: 1,
            polygons: 1,
            counts: vec![3, 4],
            refs: vec![0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
            end: 0,
            normal: None,
            width: 2,
        };
        let tri = triangulate(&elements, &[], &[rec.clone()], None, false);
        // 1 soup + 1 strip (3 refs) + 2 fan triangles (4 refs)
        assert_eq!(tri.triangles.len(), 4);
        assert_eq!(tri.degenerate, 0);
        assert_eq!(tri.extended_triangles, 4);
        assert_eq!(tri.extended_declined, 0);
        assert_eq!(tri.loops_exported, 2); // strip + polygon (soup not a loop)
        assert_eq!(tri.loops_curve_entry, 0);
        // The manifold-assembly gate: re-using the fan's (6, 8) edge
        // would push it to three uses -> declined as a whole.
        let overlapping = ExtendedFacetRecord {
            offset: 1,
            marker: 0x47,
            triangles: 0,
            strips: 1,
            polygons: 0,
            counts: vec![3],
            refs: vec![6, 8, 9],
            end: 1,
            normal: None,
            width: 2,
        };
        let tri = triangulate(&elements, &[], &[rec, overlapping], None, false);
        assert_eq!(tri.triangles.len(), 4);
        assert_eq!(tri.extended_triangles, 4);
        assert_eq!(tri.extended_declined, 1);
    }

    /// The 0x49 triangle-list family (2026-11-18), twin of the Python
    /// pins: no count table, u16be refs, ``n == 3*ty``, one 3-ref loop
    /// per triangle. The first reference's high byte is data, never a
    /// count (the generic law's misparse).
    #[test]
    fn parse_049_record_pins_the_no_count_law() {
        let mut body = vec![0x01u8, 0x49, 1, 0xFF];
        body.extend_from_slice(&3u32.to_le_bytes());
        for v in [0.0f32, 0.0, 1.0] {
            body.extend_from_slice(&v.to_le_bytes());
        }
        for r in [0x0201u16, 0x058B, 0x0231] {
            body.extend_from_slice(&r.to_be_bytes());
        }
        let (records, n_hdrs) = parse_strip_records(&body, 0, body.len(), 2000, None);
        assert_eq!(n_hdrs, 1);
        assert_eq!(records.len(), 1);
        let rec = &records[0];
        assert_eq!(rec.marker, 0x49);
        assert_eq!(rec.counts, vec![3u32]);
        assert_eq!(rec.refs, vec![0x0201, 0x058B, 0x0231]);
        assert_eq!(rec.width, 2);
        // ty == 3 splits into three 3-ref loops.
        let mut multi = vec![0x01u8, 0x49, 3, 0xFF];
        multi.extend_from_slice(&9u32.to_le_bytes());
        for v in [0.0f32, 0.0, 1.0] {
            multi.extend_from_slice(&v.to_le_bytes());
        }
        for r in 0..9u16 {
            multi.extend_from_slice(&r.to_be_bytes());
        }
        let (records, _n) = parse_strip_records(&multi, 0, multi.len(), 64, None);
        assert_eq!(records[0].counts, vec![3u32, 3, 3]);
    }

    /// The 0x49 law's fail-closed arms: a reference count that is not
    /// 3*ty, refs outside the element space, and a ref block that would
    /// swallow the next header are all rejected (no guessing).
    #[test]
    fn parse_049_record_rejects_off_law_candidates() {
        let build = |ty: u8, n: u32, refs: &[u16]| {
            let mut b = vec![0x01u8, 0x49, ty, 0xFF];
            b.extend_from_slice(&n.to_le_bytes());
            for v in [0.0f32, 0.0, 1.0] {
                b.extend_from_slice(&v.to_le_bytes());
            }
            for r in refs {
                b.extend_from_slice(&r.to_be_bytes());
            }
            b
        };
        // n != 3*ty
        let body = build(2, 5, &[0, 1, 2, 3, 4]);
        let (records, _n) = parse_strip_records(&body, 0, body.len(), 64, None);
        assert!(records.is_empty());
        // out-of-space refs
        let body = build(1, 3, &[0, 1, 99]);
        let (records, _n) = parse_strip_records(&body, 0, body.len(), 64, None);
        assert!(records.is_empty());
        // the ref block would swallow a following header
        let mut body = build(2, 6, &[0, 1, 2, 3, 4, 5]);
        body.truncate(28);
        body.extend_from_slice(&[0x01, 0x42, 0x01, 0xFF]);
        let (records, _n) = parse_strip_records(&body, 0, body.len(), 64, None);
        assert!(records.is_empty());
    }

    /// The shared incremental guard: accepts units that keep every
    /// undirected edge at two uses or fewer, refuses the rest without
    /// touching the histogram.
    #[test]
    fn mesh_safe_is_the_incremental_edge_use_lever() {
        let mut guard = mesh::EdgeGuard::default();
        assert!(guard.admit(&[(0, 1, 2)]));
        assert!(guard.admit(&[(0, 2, 3)]));
        // (0, 2) is already used twice -> refused and not folded in.
        let before = guard.uses.clone();
        assert!(!guard.admit(&[(0, 2, 9)]));
        assert_eq!(guard.uses, before);
    }

    // --- #66 (2026-11-20): short-form refs gate + the 0x41/0x44
    // primitive (OOB fail-closed rank + u16le/u8) ---------------------

    fn strip_record(marker: u8, n: u32, counts: &[u8], refs: &[u8]) -> Vec<u8> {
        let mut out = vec![0x01, marker, 1, 0xFF];
        out.extend_from_slice(&n.to_le_bytes());
        out.extend_from_slice(counts);
        out.extend_from_slice(refs);
        out
    }

    /// #66 pin: the in-bounds candidate wins even when it repeats refs.
    /// The old rank (exact, repeats, oob, ...) picked the w2be candidate
    /// (no repeat, but all refs >= 100); the committed gate ranks oob
    /// first and declines the winner if it is still OOB.
    #[test]
    fn short_vote_ranks_oob_before_repeats() {
        let rec = strip_record(
            0x42,
            6,
            &[6],
            &[7, 8, 7, 9, 5, 6, 0x01, 0x0A, 0x01, 0x0B, 0x01, 0x0C, 0, 0],
        );
        let (records, n_hdrs) = parse_strip_records(&rec, 0, rec.len(), 100, None);
        assert_eq!(n_hdrs, 1);
        assert_eq!(records.len(), 1);
        assert_eq!(records[0].width, 1);
        assert_eq!(records[0].refs, vec![7, 8, 7, 9, 5, 6]);
    }

    /// #66 post-vote gate: a record with no in-bounds reading stays
    /// unresolved (it never reaches `triangulate`).
    #[test]
    fn short_vote_declines_an_all_oob_winner() {
        let rec = strip_record(0x41, 2, &[2], &[200, 200, 201, 201]);
        let (records, n_hdrs) = parse_strip_records(&rec, 0, rec.len(), 100, None);
        assert_eq!(n_hdrs, 1);
        assert!(records.is_empty());
    }

    /// #66: the MB-chair/Audi byte pattern is u16le [69, 72, 73, 74]
    /// (0x4500 u16be is OOB); u16 outranks u8 for the relaxed markers.
    #[test]
    fn relaxed_primitive_reads_u16_little_endian() {
        let rec = strip_record(0x44, 4, &[4], &[69, 0, 72, 0, 73, 0, 74, 0]);
        let (records, n_hdrs) = parse_strip_records(&rec, 0, rec.len(), 100, None);
        assert_eq!(n_hdrs, 1);
        assert_eq!(records.len(), 1);
        assert_eq!(records[0].width, 2);
        assert_eq!(records[0].refs, vec![69, 72, 73, 74]);
    }

    /// #66: the MB-hatch sub-form — both u16 readings are out of
    /// space, the u8 reading is the record.
    #[test]
    fn relaxed_primitive_falls_back_to_u8() {
        let rec = strip_record(0x41, 5, &[5], &[36, 29, 27, 34, 1]);
        let (records, n_hdrs) = parse_strip_records(&rec, 0, rec.len(), 100, None);
        assert_eq!(n_hdrs, 1);
        assert_eq!(records.len(), 1);
        assert_eq!(records[0].width, 1);
        assert_eq!(records[0].refs, vec![36, 29, 27, 34, 1]);
    }

    /// #66: the Audi 0x301e912 false header, byte for byte. The u8
    /// winner's 2n-wide u16le reading is a complete in-bounds stream
    /// reaching past the real 6-byte extended header at +47 (391 from
    /// `87 01`, 2119 from `47 08`), so the record is a half-read of the
    /// previous record's refs, not a record.
    #[test]
    fn relaxed_u8_half_read_of_a_u16le_stream_is_declined() {
        let mut rec = vec![0u8; 53];
        rec[21..29].copy_from_slice(&[0x01, 0x41, 0x03, 0xFF, 9, 0, 0, 0]);
        rec[29..32].copy_from_slice(&[4, 2, 3]);
        rec[32..44].copy_from_slice(&[0x45, 0, 0x48, 0, 0x49, 0, 0x4A, 0, 0x4B, 0, 0x4C, 0]);
        rec[44..46].copy_from_slice(&[0x87, 0x01]);
        rec[46] = 0;
        rec[47..53].copy_from_slice(&[0x01, 0x47, 0x08, 0x08, 0x04, 0xFF]);
        let (records, n_hdrs) = parse_strip_records(&rec, 0, rec.len(), 3000, None);
        assert_eq!(n_hdrs, 1);
        assert!(records.is_empty());
    }

    /// W1 marathon anti-half-read: the acc-Cont-Lft 0x5255e record,
    /// byte for byte. `01 42 11 ff`, n=97, counts [5,5,5,5,9,5,5,9,
    /// 5,5,5,5,5,5,5,5,9], a ref block whose every even byte is 0x00
    /// (a u16be stream 0, 58, 1, 61, ... 253, 188, 255) over a store
    /// whose declared space is 220. The u16be parse ends past the
    /// truncated span so the vote's only viable candidate is the u8
    /// reading (0, 0, 0, 58, 0, 1, ...) — the permuted garbage; the
    /// u16be re-reading leaves the space too (refs to 255), so the
    /// record is declined fail-closed instead of exporting it.
    #[test]
    fn u8_winner_over_a_truncated_u16be_stream_is_declined() {
        let hex = concat!(
            "014211ff6100000005050505090505090505050505050505090000003a0001",
            "003d00030003003d00080042000e000e004200120048001500150048001900",
            "4e001e001e004e0022005500270059002b005e002f002f005e003300650035",
            "003500650039006b00510051006b00630072007000750079007b0080008000",
            "7b00880081009200920081009e008700ab00ab008700be008d00c200c2008d",
            "00c6009400ca00ca009400ce009900d200d2009900d600a200db00db00a200",
            "df00aa00e300e300aa00e800b500ed00ed00b500f400b700fb00b900fd00bc",
            "00ff"
        );
        let mut data = Vec::with_capacity(hex.len() / 2 + 16);
        for b in (0..hex.len()).step_by(2) {
            data.push(u8::from_str_radix(&hex[b..b + 2], 16).unwrap());
        }
        assert_eq!(data.len(), 219);
        data.extend_from_slice(&[0u8; 16]);
        let (records, n_hdrs) = parse_strip_records(&data, 0, data.len(), 220, None);
        assert_eq!(n_hdrs, 1);
        assert!(records.is_empty());
    }

    /// W1 marathon anti-half-read, the negative control: the same
    /// 0-heavy signature over a store whose u16be re-reading stays
    /// inside the declared space is NOT declined.
    #[test]
    fn u8_record_with_in_bounds_u16be_reread_still_exports() {
        let counts = [5u8, 5, 5, 5, 9, 5, 5, 9, 5, 5, 5, 5, 5, 5, 5, 5, 9];
        let mut rec = vec![0x01, 0x42, 0x11, 0xFF];
        rec.extend_from_slice(&97u32.to_le_bytes());
        rec.extend_from_slice(&counts);
        rec.extend_from_slice(&[0u8; 97]);
        rec.extend_from_slice(&[0u8; 16]);
        let (records, n_hdrs) = parse_strip_records(&rec, 0, rec.len(), 220, None);
        assert_eq!(n_hdrs, 1);
        assert_eq!(records.len(), 1);
        assert_eq!(records[0].width, 1);
        assert_eq!(records[0].refs, vec![0u32; 97]);
    }

    // --- the W1-B multi-region second chance (2026-11-22) ------------------
    //
    // Function-level twins of the twin's test_composite_export tests: a
    // two-period body (each period = its own token node + records over
    // that node's region; no pool groups, no edge groups — the stage-13
    // unrouted family).

    /// The twin's COMPOSITE_POINTS (12 corners, region order).
    const MR_POINTS: [(f64, f64, f64); 12] = [
        (0.0, 10.0, 0.0),
        (0.0, 10.0, 30.0),
        (0.0, 10.0, 60.0),
        (0.0, 110.0, 0.0),
        (0.0, 110.0, 30.0),
        (0.0, 110.0, 60.0),
        (20.0, 10.0, 0.0),
        (20.0, 10.0, 30.0),
        (20.0, 110.0, 0.0),
        (20.0, 110.0, 30.0),
        (20.0, 110.0, 60.0),
        (20.0, 10.0, 60.0),
    ];

    /// The LCP slot walk (the twin's ``_composite_elements``).
    fn mr_elements(points: &[(f64, f64, f64)]) -> Vec<Element> {
        let mut out = Vec::new();
        let (mut px, mut py) = (0.0f64, 0.0f64);
        for &(x, y, z) in points {
            let slot = if x != px {
                0u8
            } else if y != py {
                3
            } else {
                2
            };
            out.push((slot, Some((x, y, z))));
            px = x;
            py = y;
        }
        out
    }

    fn mr_p1g(n: usize) -> Vec<u8> {
        if n < 0xFF {
            vec![n as u8]
        } else {
            let mut v = vec![0xFFu8];
            v.extend_from_slice(&(n as u32).to_le_bytes());
            v
        }
    }

    /// The twin's ``_composite_node_payload`` (29-B header, token,
    /// counts, zero block, 2-bit table, write count, region, U2 tail).
    fn mr_node_payload(elements: &[Element]) -> Vec<u8> {
        let mut body = Vec::new();
        body.extend_from_slice(&1u32.to_le_bytes());
        body.extend_from_slice(&7u32.to_le_bytes());
        body.extend_from_slice(&0u32.to_le_bytes());
        for v in [10.0f32, 60.0, 30.0] {
            body.extend_from_slice(&v.to_le_bytes());
        }
        body.extend_from_slice(&3u32.to_le_bytes());
        body.push(0x00);
        body.extend_from_slice(&[0xFF, 0xFF, 0x02, 0x00, 0x01]);
        body.extend(mr_p1g(elements.len()));
        body.extend(mr_p1g(elements.len()));
        body.extend_from_slice(&[0x00; 4]);
        let n = elements.len();
        let mut table = vec![0u8; (n + 3) / 4];
        for (i, (slot, _pt)) in elements.iter().enumerate() {
            table[i / 4] |= slot << (2 * (i % 4));
        }
        body.extend_from_slice(&table);
        // The write count covers WRITTEN words only (skip slots read
        // none — the twin's ``_composite_node_payload`` excludes them;
        // a skip slot's phantom word misdeclared the region and the
        // walk came up short).
        let words: usize = elements
            .iter()
            .filter(|(s, _pt)| *s != 1)
            .map(|(s, _pt)| match s {
                0 => 3,
                3 => 2,
                _ => 1,
            })
            .sum();
        body.extend(mr_p1g(words));
        for (slot, pt) in elements {
            let Some((x, y, z)) = pt else { continue };
            let (x, y, z) = (*x, *y, *z);
            match slot {
                0 => {
                    for v in [x, y, z] {
                        body.extend_from_slice(&(v as f32).to_le_bytes());
                    }
                }
                3 => {
                    for v in [y, z] {
                        body.extend_from_slice(&(v as f32).to_le_bytes());
                    }
                }
                _ => body.extend_from_slice(&(z as f32).to_le_bytes()),
            }
        }
        body.extend_from_slice(&[0x00; 4]);
        body.extend_from_slice(&[0x00, 0x04, 0x02, 0x0a, 0x02]);
        body
    }

    /// The twin's ``_facet_record`` (u8 refs, one count byte).
    fn mr_record(marker: u8, normal: Option<(f64, f64, f64)>, refs: &[u32]) -> Vec<u8> {
        let mut rec = vec![0x01, marker, 0x01, 0xFF];
        rec.extend_from_slice(&(refs.len() as u32).to_le_bytes());
        if let Some((x, y, z)) = normal {
            for v in [x, y, z] {
                rec.extend_from_slice(&(v as f32).to_le_bytes());
            }
        }
        rec.push(refs.len() as u8);
        rec.extend(refs.iter().map(|&r| r as u8));
        rec
    }

    fn mr_body(
        rep0: &[(u8, Option<(f64, f64, f64)>, [u32; 4])],
        rep1: &[(u8, Option<(f64, f64, f64)>, Vec<u32>)],
    ) -> Vec<u8> {
        let mut body = Vec::new();
        body.extend_from_slice(NODE_MAGIC);
        body.extend(mr_node_payload(&mr_elements(&MR_POINTS)));
        for (m, n, r) in rep0 {
            body.extend(mr_record(*m, *n, r));
        }
        let pts1: Vec<(f64, f64, f64)> = MR_POINTS
            .iter()
            .map(|&(x, y, z)| (x + 200.0, y, z))
            .collect();
        body.extend_from_slice(NODE_MAGIC);
        body.extend(mr_node_payload(&mr_elements(&pts1)));
        for (m, n, r) in rep1 {
            body.extend(mr_record(*m, *n, r));
        }
        body
    }

    fn mr_span(len: usize) -> StoreSpan {
        StoreSpan {
            block_start: 0,
            origin: 0,
            origin_kind: ORIGIN_KIND_HEADER,
            body_lo: 0,
            body_hi: len,
            catalog_len: 0,
            container: CONTAINER_STDCONT,
            tail_law: TAIL_LAW_SHIPPED,
        }
    }

    #[test]
    fn multiregion_merges_per_period_regions() {
        // the box's five quads (the z+ face dropped: an open shell) —
        // rep 0 as written, rep 1 with the OTHER diagonal (strips swap
        // to (b, a, d, c), fans rotate to (b, c, d, a)).
        let rep0: Vec<(u8, Option<(f64, f64, f64)>, [u32; 4])> = vec![
            (0x4A, Some((0.0, 0.0, -1.0)), [6, 0, 9, 3]),
            (0x4A, Some((0.0, 1.0, 0.0)), [11, 9, 5, 3]),
            (0x4A, Some((0.0, -1.0, 0.0)), [6, 8, 0, 2]),
            (0x4C, Some((-1.0, 0.0, 0.0)), [0, 2, 5, 3]),
            (0x4C, Some((1.0, 0.0, 0.0)), [6, 9, 11, 8]),
        ];
        let rep1: Vec<(u8, Option<(f64, f64, f64)>, Vec<u32>)> = vec![
            (0x4A, Some((0.0, 0.0, -1.0)), vec![0, 6, 3, 9]),
            (0x4A, Some((0.0, 1.0, 0.0)), vec![9, 11, 3, 5]),
            (0x4A, Some((0.0, -1.0, 0.0)), vec![8, 6, 2, 0]),
            (0x4C, Some((-1.0, 0.0, 0.0)), vec![2, 5, 3, 0]),
            (0x4C, Some((1.0, 0.0, 0.0)), vec![9, 11, 8, 6]),
        ];
        let body = mr_body(&rep0, &rep1);
        let span = mr_span(body.len());
        let decode = decode_composite_store(&body, &span, &[], &[], true).unwrap();
        assert_eq!(decode.info.stage, "identity-multiregion");
        assert_eq!(decode.info.multiregion_reps, Some(2));
        assert_eq!(decode.degenerate, 0);
        assert_eq!(decode.points.len(), 24);
        assert_eq!(decode.triangles.len(), 20);
        let stats = mesh::mesh_stats(&decode.triangles);
        assert!(stats.manifold);
        let lo = decode
            .triangles
            .iter()
            .filter(|t| t.0 < 12 && t.1 < 12 && t.2 < 12)
            .count();
        let hi = decode.triangles.iter().filter(|t| t.0 >= 12).count();
        assert_eq!(lo, 10);
        assert_eq!(hi, 10);
    }

    #[test]
    fn multiregion_nonmanifold_rep_declines_fail_closed() {
        // rep 1 carries one fin triangle over-using the box edge (0, 2)
        // — its own reading is not manifold, the merged mesh is not
        // adopted, and the single-rep emission is kept with the gap
        // named.
        let rep0: Vec<(u8, Option<(f64, f64, f64)>, [u32; 4])> = vec![
            (0x4A, Some((0.0, 0.0, -1.0)), [6, 0, 9, 3]),
            (0x4A, Some((0.0, 1.0, 0.0)), [11, 9, 5, 3]),
            (0x4A, Some((0.0, -1.0, 0.0)), [6, 8, 0, 2]),
            (0x4C, Some((-1.0, 0.0, 0.0)), [0, 2, 5, 3]),
            (0x4C, Some((1.0, 0.0, 0.0)), [6, 9, 11, 8]),
        ];
        let mut rep1: Vec<(u8, Option<(f64, f64, f64)>, Vec<u32>)> = vec![
            (0x4A, Some((0.0, 0.0, -1.0)), vec![0, 6, 3, 9]),
            (0x4A, Some((0.0, 1.0, 0.0)), vec![9, 11, 3, 5]),
            (0x4A, Some((0.0, -1.0, 0.0)), vec![8, 6, 2, 0]),
            (0x4C, Some((-1.0, 0.0, 0.0)), vec![2, 5, 3, 0]),
            (0x4C, Some((1.0, 0.0, 0.0)), vec![9, 11, 8, 6]),
        ];
        rep1.push((0x42, None, vec![0, 2, 4]));
        let body = mr_body(&rep0, &rep1);
        let span = mr_span(body.len());
        let decode = decode_composite_store(&body, &span, &[], &[], true).unwrap();
        assert_eq!(decode.info.stage, "identity-table-walk");
        let declined = decode.info.multiregion_declined.clone().unwrap();
        assert!(declined.contains("not adopted"), "{declined}");
        let stats = mesh::mesh_stats(&decode.triangles);
        assert!(!stats.manifold);
    }

    // W10 (2026-11-22): the multi-region node scan's extent recovery —
    // a period whose region opens with >= 16 full-write slots carries
    // a leading-zero 2-bit table, the committed layout skip overshoots
    // INTO it (stage-8 artifact 2), and the extent law recovers the
    // unique walk-exact extent.

    /// The x-interleaved index order [0, 6, 1, 7, 2, 8, 3, 9, 4, 10,
    /// 5, 11]: consecutive elements alternate x = 0 / 20, so every
    /// written slot is a full triple (slot 0) and the 2-bit table's
    /// first four bytes are zero.
    fn mr_x_remap(face: [u32; 4]) -> [u32; 4] {
        let perm = [0usize, 6, 1, 7, 2, 8, 3, 9, 4, 10, 5, 11];
        let mut inv = [0usize; 12];
        for (new, old) in perm.iter().enumerate() {
            inv[*old] = new;
        }
        [
            inv[face[0] as usize] as u32,
            inv[face[1] as usize] as u32,
            inv[face[2] as usize] as u32,
            inv[face[3] as usize] as u32,
        ]
    }

    /// The twin's ``_container_node_payload`` (W17, 2026-11-22): the
    /// ``00 00 00 01`` container continuation of the raw-array family
    /// — token + counts + the 4-byte marker + ``c1`` raw f32 triples +
    /// a ``2*c2`` P1g count + ``c2`` four-byte edge entries (undecoded
    /// middle) + the facet records INSIDE the payload.
    fn mr_container_payload(points: &[(f64, f64, f64)], records: &[u8]) -> Vec<u8> {
        let mut body = Vec::new();
        body.extend_from_slice(&1u32.to_le_bytes());
        body.extend_from_slice(&7u32.to_le_bytes());
        body.extend_from_slice(&0u32.to_le_bytes());
        for v in [10.0f32, 60.0, 30.0] {
            body.extend_from_slice(&v.to_le_bytes());
        }
        body.extend_from_slice(&3u32.to_le_bytes());
        body.push(0x00);
        body.extend_from_slice(&[0xFF, 0xFF, 0x02, 0x00, 0x01]);
        body.extend(mr_p1g(points.len()));
        body.extend(mr_p1g(points.len()));
        body.extend_from_slice(&[0x00, 0x00, 0x00, 0x01]);
        for &(x, y, z) in points {
            for v in [x, y, z] {
                body.extend_from_slice(&(v as f32).to_le_bytes());
            }
        }
        body.extend(mr_p1g(2 * points.len()));
        for i in 0..points.len() {
            body.extend_from_slice(&[0x10 + (i % 16) as u8, 0x00, 0x00, 0x6A + (i % 16) as u8]);
        }
        body.extend_from_slice(records);
        body
    }

    #[test]
    fn multiregion_container_adopts_own_space() {
        // The W17 container second chance (2026-11-22): node 0 = the
        // padded table rep (open faces, its territory); node 1 = a
        // ``00 00 00 01`` container whose records sit inside its own
        // payload over its own +200x space (the other diagonal).  The
        // single-rep reading misresolves the container's records
        // against node 0's space (not-manifold) so the route fires;
        // the merged reading (table rep + container rep, disjoint
        // spaces) is adopted manifold + degenerate-free.  The
        // LS-Valv-75 law: the head records are the failing nodes'
        // own surface, not rep 0's.
        let rep0: Vec<(u8, Option<(f64, f64, f64)>, [u32; 4])> = vec![
            (0x4A, Some((0.0, 0.0, -1.0)), [6, 0, 9, 3]),
            (0x4A, Some((0.0, 1.0, 0.0)), [11, 9, 5, 3]),
            (0x4A, Some((0.0, -1.0, 0.0)), [6, 8, 0, 2]),
            (0x4C, Some((-1.0, 0.0, 0.0)), [0, 2, 5, 3]),
            (0x4C, Some((1.0, 0.0, 0.0)), [6, 9, 11, 8]),
        ];
        let cont_recs: Vec<(u8, Option<(f64, f64, f64)>, Vec<u32>)> = vec![
            (0x4A, Some((0.0, 0.0, -1.0)), vec![0, 6, 3, 9]),
            (0x4A, Some((0.0, 1.0, 0.0)), vec![9, 11, 3, 5]),
            (0x4A, Some((0.0, -1.0, 0.0)), vec![8, 6, 2, 0]),
            (0x4C, Some((-1.0, 0.0, 0.0)), vec![2, 5, 3, 0]),
            (0x4C, Some((1.0, 0.0, 0.0)), vec![9, 11, 8, 6]),
        ];
        let pts1: Vec<(f64, f64, f64)> = MR_POINTS
            .iter()
            .map(|&(x, y, z)| (x + 200.0, y, z))
            .collect();
        let mut container_records = Vec::new();
        for (m, n, r) in &cont_recs {
            container_records.extend(mr_record(*m, *n, r));
        }
        let mut body = Vec::new();
        body.extend_from_slice(NODE_MAGIC);
        body.extend(mr_node_payload(&mr_elements(&MR_POINTS)));
        body.extend_from_slice(&[0x00; 140]);
        for (m, n, r) in &rep0 {
            body.extend(mr_record(*m, *n, r));
        }
        body.extend_from_slice(NODE_MAGIC);
        body.extend(mr_container_payload(&pts1, &container_records));
        let span = mr_span(body.len());
        let decode = decode_composite_store(&body, &span, &[], &[], true).unwrap();
        assert_eq!(decode.info.stage, "identity-multiregion");
        assert_eq!(decode.info.multiregion_reps, Some(2));
        assert_eq!(decode.info.multiregion_container_reps, Some(1));
        assert_eq!(decode.degenerate, 0);
        assert_eq!(decode.points.len(), 24);
        assert_eq!(decode.triangles.len(), 20);
        let stats = mesh::mesh_stats(&decode.triangles);
        assert!(stats.manifold);
        let lo = decode
            .triangles
            .iter()
            .filter(|t| t.0 < 12 && t.1 < 12 && t.2 < 12)
            .count();
        let hi = decode.triangles.iter().filter(|t| t.0 >= 12).count();
        assert_eq!(lo, 10);
        assert_eq!(hi, 10);
    }

    #[test]
    fn multiregion_extent_recovery_adopts_leading_zero_table() {
        let rep0: Vec<(u8, Option<(f64, f64, f64)>, [u32; 4])> = vec![
            (0x4A, Some((0.0, 0.0, -1.0)), [6, 0, 9, 3]),
            (0x4A, Some((0.0, 1.0, 0.0)), [11, 9, 5, 3]),
            (0x4A, Some((0.0, -1.0, 0.0)), [6, 8, 0, 2]),
            (0x4C, Some((-1.0, 0.0, 0.0)), [0, 2, 5, 3]),
            (0x4C, Some((1.0, 0.0, 0.0)), [6, 9, 11, 8]),
        ];
        let rep1: Vec<(u8, Option<(f64, f64, f64)>, Vec<u32>)> = vec![
            (
                0x4A,
                Some((0.0, 0.0, -1.0)),
                mr_x_remap([6, 0, 9, 3]).to_vec(),
            ),
            (
                0x4A,
                Some((0.0, 1.0, 0.0)),
                mr_x_remap([11, 9, 5, 3]).to_vec(),
            ),
            (
                0x4A,
                Some((0.0, -1.0, 0.0)),
                mr_x_remap([6, 8, 0, 2]).to_vec(),
            ),
            (
                0x4C,
                Some((-1.0, 0.0, 0.0)),
                mr_x_remap([0, 2, 5, 3]).to_vec(),
            ),
            (
                0x4C,
                Some((1.0, 0.0, 0.0)),
                mr_x_remap([6, 9, 11, 8]).to_vec(),
            ),
        ];
        // node 0: the standard 12-point payload + a zero tail so its
        // payload is the largest (find_list_node's single-rep pick),
        // keeping the single-rep emission misresolved and not-manifold.
        let mut body = Vec::new();
        body.extend_from_slice(NODE_MAGIC);
        body.extend(mr_node_payload(&mr_elements(&MR_POINTS)));
        body.extend_from_slice(&[0x00; 140]);
        for (m, n, r) in &rep0 {
            body.extend(mr_record(*m, *n, r));
        }
        // node 1: 16 full-write slots (x-interleaved box points, x
        // shifted +1 so element 0 also changes x) + 4 skip slots — the
        // table's leading four bytes are zero, the committed skip
        // overshoots, the primary walk fails.
        let perm = [0usize, 6, 1, 7, 2, 8, 3, 9, 4, 10, 5, 11];
        let mut pts1: Vec<(f64, f64, f64)> = perm
            .iter()
            .map(|&k| {
                let (x, y, z) = MR_POINTS[k];
                (x + 1.0, y, z)
            })
            .collect();
        pts1.extend((0..4).map(|i| (60.0 + 20.0 * i as f64, 500.0, 700.0)));
        let mut elements1: Vec<Element> = pts1
            .iter()
            .map(|&(x, y, z)| (0u8, Some((x, y, z))))
            .collect();
        elements1.extend((0..4).map(|_| (1u8, None)));
        body.extend_from_slice(NODE_MAGIC);
        body.extend(mr_node_payload(&elements1));
        for (m, n, r) in &rep1 {
            body.extend(mr_record(*m, *n, r));
        }
        let span = mr_span(body.len());
        let decode = decode_composite_store(&body, &span, &[], &[], true).unwrap();
        assert_eq!(decode.info.stage, "identity-multiregion");
        assert_eq!(decode.info.multiregion_reps, Some(2));
        assert_eq!(decode.info.multiregion_extent_reps, Some(1));
        assert_eq!(decode.degenerate, 0);
        let stats = mesh::mesh_stats(&decode.triangles);
        assert!(stats.manifold);
    }
}
