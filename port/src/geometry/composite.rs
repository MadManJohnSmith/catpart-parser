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
//! stage-8/9 mixedwrite composition, the stage-10 E0-b dup-pin law
//! (RELAXED 2026-11-13 stage 15, owner-authorized — the battery
//! criterion removed) and the stage-15 unordered-triangle dedup. The
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
//! 3. **Stage 3**: the E0-b dup-pin law (relaxed), the stage-15
//!    unordered-triangle dedup, and the curve exposure for the
//!    viewer's overlay — spec §2.3 pins the curve-entry point
//!    sequences ADDITIVE and OUTSIDE the Fidelity definition (the
//!    Python reference has no counterpart artifact); the boundary is
//!    pinned in code there.
//!
//! Named-ambiguity discipline (the dispatch's rule): the twin's
//! docstring carries dated law amendments; where two passages could
//! disagree, the LATEST dated law wins. Verified at port time: the
//! stage-10 battery criterion (2026-11-12) vs the stage-15 relaxation
//! (2026-11-13) — the twin's code implements the RELAXED law
//! consistently (``_e0b_dup_pin`` carries the removal comment dated
//! 2026-11-13, the battery call sites are gone); no passage
//! disagreement remains. The twin is untouchable — a twin bug
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
use super::mesh;
use super::pool::{EDGE_SUBKIND, PoolGroup};
use super::store::{StoreSpan, find};

/// The scene-graph node record magic (twin: ``NODE_MAGIC``).
pub const NODE_MAGIC: &[u8; 4] = b"\x04\x04\xfd\xff";
/// The list-node token (twin: ``LIST_TOKEN``).
pub const LIST_TOKEN: &[u8; 5] = b"\xff\xff\x02\x00\x01";

/// The element-count sanity cap (twin: ``MAX_ELEMENT_COUNT``).
pub const MAX_ELEMENT_COUNT: u32 = 10_000_000;
/// The 2-bit table sanity cap (twin: ``MAX_TABLE_BYTES``).
pub const MAX_TABLE_BYTES: usize = 1 << 20;
/// The loop-count byte cap of the width rank (twin: ``MAX_LOOP_COUNTS``).
pub const MAX_LOOP_COUNTS: usize = 16;

/// Table value -> f32 words written (0 = skip: the element carries no
/// coordinates in the region — the curve entries, U4). Index = the
/// 2-bit slot value (twin: ``SHAPES = {0: 3, 1: 0, 2: 1, 3: 2}``).
pub const SHAPES: [usize; 4] = [3, 0, 1, 2];

/// Plane tolerance of the committed loop battery (stage 3b): the
/// per-coordinate normal distance bound; f32 coordinate rounding
/// ~1e-4 (twin: ``PLANE_TOL``, composite.py:524).
pub const PLANE_TOL: f64 = 2e-3;

/// The gated families whose references must resolve in-bounds (the
/// exported markers plus the normal-carrying 0x49, the stage-2c gate
/// set) — twin: ``GATED``.
pub const GATED: [u8; 4] = [0x42, 0x49, 0x4A, 0x4C];

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
    /// The payload-relative offset the walk ended at.
    pub walk_end: usize,
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
    /// The ``k`` loop-count bytes (summing to ``n``).
    pub counts: Vec<u8>,
    /// The ``n`` width-byte big-endian references (element indices).
    pub refs: Vec<u32>,
    /// The winning width (1/2/3 bytes per reference).
    pub width: u8,
}

/// The loop counters of one :fn:`triangulate` call — the twin's
/// ``stats`` dict: the two loop counters plus the stage-10 ``dup_pin``
/// candidate (present exactly when this call's primary triangulation
/// is empty and dropped curve-entry loops exist).
#[derive(Debug, Clone, PartialEq, Default)]
pub struct LoopStats {
    /// Loops exported (no skip reference).
    pub loops_exported: u32,
    /// Loops dropped for referencing a skip slot (the curve entries).
    pub loops_curve_entry: u32,
    /// The stage-10 ``stats["dup_pin"]`` key: ``Some(None)`` =
    /// evaluated but UNPINNABLE (a referenced skip slot with no
    /// preceding written element — the fail-closed veto);
    /// ``Some(Some(_))`` = pinnable (the merge candidate);
    /// ``None`` = not evaluated (triangles exported, or no dropped
    /// loops).
    pub dup_pin: Option<Option<DupPin>>,
}

/// The stage-10 E0-b dup-pin candidate (RELAXED 2026-11-13 stage 15,
/// owner-authorized — the battery criterion removed): the pinned
/// loops' triangles (written-rank indexed), the degenerate count and
/// the pinned loop count.
#[derive(Debug, Clone, PartialEq)]
pub struct DupPin {
    /// The pinned loops' triangles (written-rank indexed).
    pub triangles: Vec<(u32, u32, u32)>,
    /// The pinned loops' degenerate skips.
    pub degenerate: u32,
    /// The pinned loop count (``len(dropped)``).
    pub loops: u32,
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
    /// Stage-10 (relaxed stage 15): the law name on a firing store.
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

/// Coplanarity of one fully-resolved loop against the record's stored
/// normal (the stage-3b battery criterion; ported from the stage-4b
/// width re-test, ``not_manifold_audit.py``) — the twin's
/// ``_loop_plane_status``. Returns ``("coplanar", worst)`` or
/// ``("nonplanar", max_distance)``. See the module header for the
/// ``powf`` probe.
fn loop_plane_status(
    loop_refs: &[u32],
    normal: (f64, f64, f64),
    elements: &[Element],
) -> (&'static str, f64) {
    let nn = (normal.0.powf(2.0) + normal.1.powf(2.0) + normal.2.powf(2.0)).powf(0.5);
    if nn == 0.0 {
        return ("nonplanar", 0.0);
    }
    let pts: Vec<(f64, f64, f64)> = loop_refs
        .iter()
        .map(|&r| {
            elements[r as usize]
                .1
                .expect("guarded: the caller skips loops with skip slots or out-of-space refs")
        })
        .collect();
    let p0 = pts[0];
    let mut worst = 0.0f64;
    for p in &pts[1..] {
        let d = ((p.0 - p0.0) * normal.0 + (p.1 - p0.1) * normal.1 + (p.2 - p0.2) * normal.2) / nn;
        if d.abs() > worst {
            worst = d.abs();
        }
        if d.abs() > PLANE_TOL {
            return ("nonplanar", d.abs());
        }
    }
    ("coplanar", worst)
}

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

/// Every strip record with the width disambiguated (stage-3b rule,
/// extended 2026-11-11 stage 4b: u24be candidate + the loop plane
/// tiebreak; integrated 2026-11-12 stage 5, #34) — the twin's
/// ``parse_strip_records``.
///
/// Candidate parses: width u8/u16be (plus u24be ONLY when
/// ``element_count > 65,535`` — a 2-byte ref cannot index such an
/// element space, and on smaller spaces a 3-byte candidate can only
/// read junk past them: measured on the corpus A/B, 4 exported stores
/// flip to OOB junk when u24be is offered below the threshold) x
/// count-byte ``k`` (0..16) summing to ``n``, ending at or before the
/// next header. Rank: exact tiling, then no-repeated-refs-within-a-
/// loop, then no out-of-range refs, then non-coplanar
/// normal-carrying loops (only computed when ``elements`` — the
/// decoded element space the refs index — is passed; a candidate
/// whose loops are non-coplanar against the record's stored normal
/// loses to one that is coplanar; without ``elements`` the rank is
/// the committed stage-3b one), then the narrower width. Returns the
/// records plus the header-candidate count.
fn parse_strip_records(
    data: &[u8],
    lo: usize,
    hi: usize,
    element_count: u32,
    elements: Option<&[Element]>,
) -> (Vec<CompositeRecord>, usize) {
    let hdrs = facets::strip_headers(data, lo, hi);
    let widths: &[u8] = if element_count > 65_535 {
        &[1, 2, 3]
    } else {
        &[1, 2]
    };
    let skips: Option<HashSet<usize>> = elements.map(|els| {
        els.iter()
            .enumerate()
            .filter(|(_, (_, pt))| pt.is_none())
            .map(|(i, _)| i)
            .collect()
    });
    let mut out = Vec::new();
    for (i, &o) in hdrs.iter().enumerate() {
        let nxt = if i + 1 < hdrs.len() { hdrs[i + 1] } else { hi };
        let mk = data[o + 1];
        let hlen: usize = if data[o + 3] == 0xFF { 4 } else { 5 };
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
        type Rank = (u8, u8, u8, u32, u8, u32);
        let mut best: Option<(Rank, Vec<u8>, Vec<u32>, u8)> = None;
        for &width in widths {
            for k in 0..=MAX_LOOP_COUNTS {
                if base + k > nxt {
                    break;
                }
                let counts: Vec<u8> = (0..k).map(|j| data[base + j]).collect();
                let sum: u32 = counts.iter().map(|&c| u32::from(c)).sum();
                if sum != n {
                    continue;
                }
                let end = base + k + width as usize * n as usize;
                if end > nxt {
                    continue;
                }
                let refs: Vec<u32> = (0..n)
                    .map(|j| {
                        let at = base + k + width as usize * j as usize;
                        match width {
                            1 => u32::from(data[at]),
                            2 => u32::from(u16::from_be_bytes([data[at], data[at + 1]])),
                            _ => u32::from_be_bytes([0, data[at], data[at + 1], data[at + 2]]),
                        }
                    })
                    .collect();
                let mut repeats = false;
                let mut off = 0usize;
                for c in &counts {
                    let loop_refs = &refs[off..off + *c as usize];
                    if *c > 0 {
                        let distinct: HashSet<u32> = loop_refs.iter().copied().collect();
                        if distinct.len() < loop_refs.len() {
                            repeats = true;
                        }
                    }
                    off += *c as usize;
                }
                let oob = refs.iter().any(|&r| r >= element_count);
                let mut nonplanar = 0u32;
                if let (Some(nm), Some(els), Some(sk)) = (normal, elements, skips.as_ref()) {
                    let mut off = 0usize;
                    for c in &counts {
                        let loop_refs = &refs[off..off + *c as usize];
                        off += *c as usize;
                        if loop_refs.is_empty() {
                            continue;
                        }
                        if loop_refs
                            .iter()
                            .any(|&r| sk.contains(&(r as usize)) || r as usize >= els.len())
                        {
                            continue;
                        }
                        let (st, _m) = loop_plane_status(loop_refs, nm, els);
                        if st == "nonplanar" {
                            nonplanar += 1;
                        }
                    }
                }
                let rank: Rank = (
                    if end == nxt { 0 } else { 1 },
                    if repeats { 1 } else { 0 },
                    if oob { 1 } else { 0 },
                    nonplanar,
                    width,
                    k as u32,
                );
                if best.as_ref().is_none_or(|(b, _, _, _)| rank < *b) {
                    best = Some((rank, counts, refs, width));
                }
            }
        }
        if let Some((_rank, counts, refs, width)) = best {
            out.push(CompositeRecord {
                offset: o,
                marker: mk,
                normal,
                counts,
                refs,
                width,
            });
        }
    }
    (out, hdrs.len())
}

/// Triangles under the identity mapping (strip/polygon semantics) —
/// the twin's ``_triangulate``. Loop references are 0-based element
/// indices; triangles index the WRITTEN points (the exported vertex
/// list), so referenced elements are remapped through the written
/// rank. Loops referencing skip slots (curve entries — their
/// coordinates live in the curve records, U4) are skipped and
/// counted: the conservative rule names the gap instead of guessing
/// coordinates (the dup-pin law — the one exception — lands with
/// stage 3). Strip triangles (0x42/0x4a) skip the degenerate ones
/// (repeated coordinates or exactly-zero cross product, G3 F7);
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
    /// The stage-10 ``stats["dup_pin"]`` candidate.
    dup_pin: Option<Option<DupPin>>,
    /// The dropped curve-entry loops (marker, loop refs) in encounter
    /// order — the dup-pin input and the §2.3 curve exposure's raw
    /// material (pre-weld).
    dropped_loops: Vec<(u8, Vec<u32>)>,
}

fn triangulate(elements: &[Element], records: &[CompositeRecord]) -> Triangulation {
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

    let mut triangles: Vec<(u32, u32, u32)> = Vec::new();
    let mut degenerate = 0u32;
    let mut loops_exported = 0u32;
    let mut loops_curve_entry = 0u32;
    let mut dropped_loops: Vec<(u8, Vec<u32>)> = Vec::new();
    for rec in records {
        if !matches!(rec.marker, 0x42 | 0x4A | 0x4C) {
            continue;
        }
        let mut loops: Vec<&[u32]> = Vec::new();
        let mut o = 0usize;
        for c in &rec.counts {
            loops.push(&rec.refs[o..o + *c as usize]);
            o += *c as usize;
        }
        for loop_refs in loops {
            if loop_refs.is_empty() {
                continue;
            }
            if loop_refs.iter().any(|&r| skips.contains(&(r as usize))) {
                loops_curve_entry += 1;
                dropped_loops.push((rec.marker, loop_refs.to_vec()));
                continue;
            }
            loops_exported += 1;
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
            degenerate += deg;
            triangles.extend(tris);
        }
    }
    // The stage-10 candidate: this call's primary triangulation is
    // empty and dropped loops exist — evaluate (the None case rides
    // for the per-rep unpinnable veto, stage-10 review F1).
    let dup_pin = if triangles.is_empty() && !dropped_loops.is_empty() {
        Some(e0b_dup_pin(
            elements,
            &points,
            &written_rank,
            &dropped_loops,
        ))
    } else {
        None
    };
    Triangulation {
        triangles,
        degenerate,
        loops_exported,
        loops_curve_entry,
        dup_pin,
        dropped_loops,
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

/// The sequence-of-reps reading (stage-4b per-rep law, stage-5
/// integration) — the twin's ``_decode_per_rep``. Rep k = (pool group
/// k, the k-th walk-exact token node, that node's record territory
/// ``[region_end_k, node_{k+1})``); the k-th pool re-lists verbatim
/// (or within :const:`NOISE_REL`) in the k-th rep's region. A rep
/// exports only when its pool absorbs and its gated references
/// resolve in-bounds against its OWN element count; failing reps stay
/// unexported with the reason named. When no rep exports, raises the
/// stage-3d ``unabsorbed`` classification with the per-rep residue
/// named (fail-closed, no guessing).
fn decode_per_rep(
    data: &[u8],
    lo: usize,
    hi: usize,
    groups: &[PoolGroup],
    n_missing: usize,
    n_pool: usize,
) -> Result<CompositeDecode, ExportError> {
    let mut decoded: Vec<DecodedRep> = Vec::new();
    for node in scan_token_nodes(data, lo, hi) {
        let payload = &data[node.plo..node.phi];
        // walk-exact failure: the rep has no decoded region
        let Ok((elements, info)) = decode_region(payload, node.elem) else {
            continue;
        };
        let pts: Vec<(f64, f64, f64)> = elements.iter().filter_map(|e| e.1).collect();
        decoded.push(DecodedRep {
            pos: node.pos,
            payload_len: node.phi - node.plo,
            elem: node.elem,
            elements,
            pts,
            // absolute end of the point region (the territory start)
            region_end: node.pos + 4 + info.walk_end,
            write_count: info.write_count,
            table_bytes: info.table_bytes,
        });
    }
    if decoded.is_empty() {
        return Err(ExportError::new(
            UNDECODED_VARIANT,
            format!(
                "node list does not re-list the pool: {n_missing} of \
                 {n_pool} pool vertices absent from the decoded point \
                 region (unabsorbed variant; the per-rep decomposition \
                 finds no walk-exact rep region either)"
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
    let mut write_count = 0usize;
    let mut table_bytes = 0usize;
    let mut element_decl = 0usize;
    let mut curve_entries = 0usize;
    let mut node_bytes = 0usize;
    let mut reps_unexported: Vec<String> = Vec::new();
    let mut reps_dup_pin: Vec<(usize, Option<DupPin>)> = Vec::new();
    let mut curves: Vec<Vec<(f64, f64, f64)>> = Vec::new();
    for (k, d) in decoded.iter().enumerate() {
        node_bytes += d.payload_len;
        if k >= groups.len() {
            // stage-5 review O2 hardening: a walk-exact rep beyond the
            // pool groups has no pool to re-list — per-rep absorption
            // is unestablished, so it stays unexported (fail-closed;
            // measured 0/152 on the corpus A/B).
            reps_unexported.push(format!(
                "rep {k}: no pool group to re-list ({} pool \
                 groups for {} walk-exact reps; per-rep \
                 absorption unestablished)",
                groups.len(),
                decoded.len()
            ));
            continue;
        }
        let gv = &groups[k].vertices;
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
        let nxt = if k + 1 < decoded.len() {
            decoded[k + 1].pos
        } else {
            hi
        };
        let (records, n_hdrs) =
            parse_strip_records(data, d.region_end, nxt, d.elem, Some(&d.elements));
        let grefs: Vec<u32> = records
            .iter()
            .filter(|r| GATED.contains(&r.marker))
            .flat_map(|r| r.refs.iter().copied())
            .collect();
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
        let tri_res = triangulate(&d.elements, &records);
        // stage-10 E0-b candidate for this rep (its own triangulation
        // is empty and its dropped loops were dup-pin-evaluated):
        // recorded even when the law REJECTED (None — an unpinnable
        // referenced skip slot) — a rep with an unpinnable dropped loop
        // must veto another rep's fire at the store-level gate below
        // (stage-10 review F1: dropping the None candidate made that
        // veto dead code and zeroed the curve-entry counters while
        // unexported loops remained). Merged at the STORE level below
        // only when the whole store's mesh is empty — a rep-level fire
        // inside an otherwise-exporting store would be the
        // 471-passing-stores downside exposure.
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
        // The §2.3 curve exposure: this exported rep's dropped loops'
        // pre-weld sequences (additive, outside Fidelity).
        for (_mk, loop_refs) in &tri_res.dropped_loops {
            curves.push(curve_sequence(loop_refs, &d.elements));
        }
        facet_candidates += n_hdrs;
        facet_records += records.len();
        write_count += d.write_count as usize;
        table_bytes += d.table_bytes;
        element_decl += d.elem as usize;
        curve_entries += d.elements.len() - d.pts.len();
        for rec in &records {
            if !matches!(rec.marker, 0x42 | 0x4A | 0x4C) {
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
    // Stage-10 E0-b store-level gate: fire only when the WHOLE store's
    // mesh is empty and every rep with dropped loops is pinnable; one
    // unpinnable rep keeps everything conservative.
    let mut curve_entry_law = 0u32;
    if triangles.is_empty()
        && !reps_dup_pin.is_empty()
        && reps_dup_pin.iter().all(|(_b, c)| c.is_some())
    {
        for (b, c) in &reps_dup_pin {
            let dp = c.as_ref().expect("all(...) guarded");
            triangles.extend(
                dp.triangles
                    .iter()
                    .map(|&(a, s, t)| (a + *b as u32, s + *b as u32, t + *b as u32)),
            );
            degenerate += dp.degenerate;
            loops_exported += dp.loops;
            curve_entry_law += dp.loops;
        }
        loops_curve_entry = 0;
    }
    let mut info = CompositeInfo {
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
        reps_decoded: Some(decoded.len()),
        reps_exported: Some(decoded.len() - reps_unexported.len()),
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
        curve_entry_law: None,
        loops_curve_entry_exported: None,
        unordered_dedup_dropped: None,
        unordered_dedup_declined: None,
    };
    if curve_entry_law > 0 {
        info.curve_entry_law = Some("e0b-dup-pin");
        info.loops_curve_entry_exported = Some(curve_entry_law);
    }
    // Stage-15 unordered-triangle dedup (see apply_unordered_dedup):
    // the store-level gate — the reps' element spaces are disjoint, so
    // same-rep duplicates are the only possible matches, and a passing
    // store's mesh is never touched.
    let triangles = apply_unordered_dedup(triangles, &mut info);
    Ok(CompositeDecode {
        points,
        triangles,
        degenerate,
        info,
        curves,
    })
}

/// The U4-D dup law over one call's dropped loops — the twin's
/// ``_e0b_dup_pin`` (the curve-entry coordinate law; see the module
/// header). Ported from the stage-4a decoder's ``dup_prev``, not
/// re-derived: a loop-referenced skip slot carries the bit-exact
/// coordinates of the written vertex of its immediately preceding
/// written element (the per-face copy — no new vertices). RELAXED
/// 2026-11-13 (stage 15, #34; owner-authorized overturn of the
/// stage-10 U4 conservative rule, handoff cont. 23): the stage-10 E0-b
/// battery criterion (every dropped loop normal-carrying AND coplanar
/// against its record normal with the dup-pinned coordinates) is
/// REMOVED — normal-less and nonplanar dropped loops export under the
/// dup pin exactly like the battery-supported ones (stage-14
/// probe-measured: 25/26 pinned meshes pass every gate check incl.
/// degenerate, docs/evidence/2026-11-13-stage14-export-failures.md
/// section 2 + the review's C4). The fail-closed arm stays: a
/// loop-referenced skip slot with NO preceding written element to weld
/// to (element 0 — unpinnable) rejects the whole store onto the
/// conservative non-export rule.
///
/// Returns ``Some`` (the pinned loops' triangles, written-rank
/// indexed) when every referenced skip slot is pinnable, ``None``
/// otherwise.
fn e0b_dup_pin(
    elements: &[Element],
    points: &[(f64, f64, f64)],
    written_rank: &HashMap<usize, usize>,
    dropped: &[(u8, Vec<u32>)],
) -> Option<DupPin> {
    let skips: HashSet<usize> = elements
        .iter()
        .enumerate()
        .filter(|(_, (_, pt))| pt.is_none())
        .map(|(i, _)| i)
        .collect();
    let mut pin: HashMap<usize, usize> = HashMap::new();
    for (_mk, loop_refs) in dropped {
        for &r in loop_refs {
            let r = r as usize;
            if skips.contains(&r) && !pin.contains_key(&r) {
                let mut j = r as i64 - 1;
                while j >= 0 && elements[j as usize].1.is_none() {
                    j -= 1;
                }
                if j >= 0 {
                    pin.insert(r, j as usize);
                }
                // j < 0: no preceding written element — unpinnable
            }
        }
    }
    if dropped.iter().any(|(_mk, loop_refs)| {
        loop_refs.iter().any(|&r| {
            let r = r as usize;
            skips.contains(&r) && !pin.contains_key(&r)
        })
    }) {
        return None;
    }
    // The battery criterion is removed (owner-authorized 2026-11-13,
    // see the docstring): normal-less and nonplanar dropped loops
    // export under the dup pin — the weld's written ranks are exact
    // (the pinned coordinates are bit-identical to the pin target's,
    // so the mesh never needed them; only the battery did).
    let mut triangles: Vec<(u32, u32, u32)> = Vec::new();
    let mut degenerate = 0u32;
    for (mk, loop_refs) in dropped {
        let resolved: Vec<u32> = loop_refs
            .iter()
            .map(|&r| {
                let r = r as usize;
                pin.get(&r).copied().unwrap_or(r) as u32
            })
            .collect();
        let idxs: Vec<u32> = resolved
            .iter()
            .map(|&r| {
                u32::try_from(written_rank[&(r as usize)]).expect(
                    "guarded: the pin targets and non-skip refs are all \
                     written elements (ranked in the caller)",
                )
            })
            .collect();
        let (tris, deg) = loop_triangles(*mk, &idxs, points);
        triangles.extend(tris);
        degenerate += deg;
    }
    Some(DupPin {
        triangles,
        degenerate,
        loops: dropped.len() as u32,
    })
}

/// The unordered-triangle dedup at one store's assembled mesh — the
/// twin's ``_apply_unordered_dedup`` (stage 15, 2026-11-13, #34; the
/// stage-14 review F1 family, owner-authorized).
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
) -> Vec<(u32, u32, u32)> {
    if triangles.len() < 2 || mesh::mesh_stats(&triangles).manifold {
        return triangles;
    }
    let mut seen: HashSet<[u32; 3]> = HashSet::new();
    let mut kept: Vec<(u32, u32, u32)> = Vec::new();
    let mut dropped = 0u32;
    for tri in &triangles {
        if tri.0 == tri.1 || tri.1 == tri.2 || tri.0 == tri.2 {
            kept.push(*tri); // degenerate-shaped: never deduped
            continue;
        }
        let mut key = [tri.0, tri.1, tri.2];
        key.sort_unstable();
        if !seen.insert(key) {
            dropped += 1; // the later copy: first occurrence's winding wins
            continue;
        }
        kept.push(*tri);
    }
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
pub fn decode_composite_store(
    data: &[u8],
    span: &StoreSpan,
    groups: &[PoolGroup],
    kinds: &[Vec<u8>],
    allow_unrouted_elements: bool,
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
            match decode_raw_array_path(data, lo, hi, groups, payload, elem_decl) {
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
                    match decode_mixedwrite(data, lo, hi, groups) {
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
        return decode_per_rep(data, lo, hi, groups, missing, pool_set.len());
    }

    let (records, n_hdrs) = parse_strip_records(data, lo, hi, elem_decl, Some(&elements));
    // Refs are 0-based element indices: every gated family's references
    // must resolve inside the element space (the exported markers plus
    // the normal-carrying 0x49, the stage-2c gate set).
    let all_refs: Vec<u32> = records
        .iter()
        .filter(|r| GATED.contains(&r.marker))
        .flat_map(|r| r.refs.iter().copied())
        .collect();
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

    let tri_res = triangulate(&elements, &records);
    let mut triangles = tri_res.triangles;
    let mut degenerate = tri_res.degenerate;
    let mut loops_exported = tri_res.loops_exported;
    let mut loops_curve_entry = tri_res.loops_curve_entry;
    // Stage-10 E0-b dup-pin law (2026-11-12, #34; RELAXED 2026-11-13
    // stage 15, #34 — the E0-b battery criterion removed,
    // owner-authorized overturn, handoff cont. 23): the primary
    // triangulation is empty (the census's empty-mesh class) and every
    // dropped curve-entry loop is pinnable under the dup pin — the
    // loops export with their skip slots welded (single-rep path, so
    // this call IS the store-level mesh). ``None`` (unpinnable, or no
    // candidate) keeps the conservative non-export rule and its
    // warning; the U4-M mid law stays unsupported and is not
    // implemented.
    let mut curve_entry_law = 0u32;
    if let Some(Some(dp)) = &tri_res.dup_pin {
        triangles.extend(dp.triangles.iter().copied());
        degenerate += dp.degenerate;
        loops_exported += dp.loops;
        curve_entry_law = dp.loops;
        loops_curve_entry = 0;
    }
    let mut skipped_markers: BTreeMap<u8, u32> = BTreeMap::new();
    for rec in &records {
        if !matches!(rec.marker, 0x42 | 0x4A | 0x4C) {
            *skipped_markers.entry(rec.marker).or_insert(0) += 1;
        }
    }
    let mut info = CompositeInfo {
        stage: "identity-table-walk",
        element_decl: elem_decl as usize,
        node_points: points.len(),
        curve_entries: skip_slots,
        write_count: Some(region_info.write_count as usize),
        table_bytes: Some(region_info.table_bytes),
        facet_candidates: n_hdrs,
        facet_records: records.len(),
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
        curve_entry_law: None,
        loops_curve_entry_exported: None,
        unordered_dedup_dropped: None,
        unordered_dedup_declined: None,
    };
    if curve_entry_law > 0 {
        info.curve_entry_law = Some("e0b-dup-pin");
        info.loops_curve_entry_exported = Some(curve_entry_law);
    }
    // Stage-15 unordered-triangle dedup (see apply_unordered_dedup):
    // fires only on a not-manifold assembled mesh whose duplicate
    // unordered triples resolve it — a passing store's mesh is never
    // touched.
    let triangles = apply_unordered_dedup(triangles, &mut info);
    // The §2.3 curve exposure: the dropped loops' pre-weld sequences
    // (additive, outside Fidelity — see the boundary note).
    let curves: Vec<Vec<(f64, f64, f64)>> = tri_res
        .dropped_loops
        .iter()
        .map(|(_mk, loop_refs)| curve_sequence(loop_refs, &elements))
        .collect();
    Ok(CompositeDecode {
        points,
        triangles,
        degenerate,
        info,
        curves,
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
fn decode_raw_array_path(
    data: &[u8],
    lo: usize,
    hi: usize,
    groups: &[PoolGroup],
    payload: &[u8],
    elem_decl: u32,
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
    let all_refs: Vec<u32> = records
        .iter()
        .filter(|r| GATED.contains(&r.marker))
        .flat_map(|r| r.refs.iter().copied())
        .collect();
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
    // curve-entry loops exist and the dup-pin candidate is never
    // evaluated (triangles-empty-with-dropped is unreachable here).
    let tri_res = triangulate(&elements, &records);
    let triangles = tri_res.triangles;
    let degenerate = tri_res.degenerate;
    let loops_exported = tri_res.loops_exported;
    let loops_curve_entry = tri_res.loops_curve_entry;
    let mut skipped_markers: BTreeMap<u8, u32> = BTreeMap::new();
    for rec in &records {
        if !matches!(rec.marker, 0x42 | 0x4A | 0x4C) {
            *skipped_markers.entry(rec.marker).or_insert(0) += 1;
        }
    }
    let info = CompositeInfo {
        stage: "identity-raw-array",
        element_decl: elem_decl as usize,
        node_points: points.len(),
        curve_entries: 0,
        write_count: None,
        table_bytes: None,
        facet_candidates: n_hdrs,
        facet_records: records.len(),
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
        curve_entry_law: None,
        loops_curve_entry_exported: None,
        unordered_dedup_dropped: None,
        unordered_dedup_declined: None,
    };
    // Stage-15 unordered-triangle dedup (see apply_unordered_dedup):
    // the raw path triangulates facet records like the other paths, so
    // the same duplicated-writer-content mechanism is in scope
    // (measured corpus incidence 0 — no identity-raw-array row is
    // not-manifold).
    let mut info = info;
    let triangles = apply_unordered_dedup(triangles, &mut info);
    // The §2.3 curve exposure: the raw element space has NO skip
    // slots, so no dropped curve-entry loops exist and the artifact is
    // empty (measured corpus incidence 0).
    Ok(CompositeDecode {
        points,
        triangles,
        degenerate,
        info,
        curves: Vec::new(),
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
/// Rep k = (pool group k, the k-th law-decoded token node in body
/// order — the diagonal, measured on the census population: all 81
/// region-absorbable stores pair diagonally with exact f32 —, that
/// node's record territory ``[region_end_k, next decoded node)``).
/// The store exports only when EVERY pool vertex is absorbed by its
/// diagonal rep's region (exact f32, then the stage-4b noise
/// tolerance capped at 10,000-vertex pools): vertices no region
/// re-lists are the sub-node record route's residue — their element
/// slots are unpinned, the store stays fail-closed for export (the
/// stage-8 note's integration item (e); bad44bdf's class). Per rep:
/// the M2b refs gate against the rep's own element count, records
/// parsed with the committed width laws, strip/polygon
/// triangulation; merged meshes concatenate the exported reps'
/// written points. A rep whose gated references leave its own
/// element space stays unexported with the reason named (stage-5
/// per-rep fail-closed); reps beyond the pool groups have no pool to
/// re-list and stay unexported (stage-5 O2).
///
/// Raises ``undecoded-variant`` with the specific gap when no node
/// decodes, absorption is not established, or no rep exports.
fn decode_mixedwrite(
    data: &[u8],
    lo: usize,
    hi: usize,
    groups: &[PoolGroup],
) -> Result<CompositeDecode, ExportError> {
    let poolv: Vec<(f64, f64, f64)> = groups
        .iter()
        .flat_map(|g| g.vertices.iter().copied())
        .collect();
    let pool_set: HashSet<(u64, u64, u64)> = poolv.iter().copied().map(vkey).collect();
    let nodes = scan_token_nodes(data, lo, hi);
    let n_nodes = nodes.len();
    let mut decoded: Vec<MixedRep> = Vec::new();
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
        let nd = decode_node_mixedwrite(payload, node.elem, counts_end, &poolv);
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
        decoded.push(MixedRep {
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
        });
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
    // diagonal rep's region (exact f32, then the stage-4b noise
    // tolerance; the census measured exact f32 on all 81). Vertices no
    // region re-lists are the sub-node record route's residue — their
    // element slots are unpinned, the store stays fail-closed (named).
    let mut uncovered = 0usize;
    for (k, g) in groups.iter().enumerate() {
        let rep = decoded.get(k).map(|m| &m.rep);
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
    let mut write_count = 0usize;
    let mut table_bytes = 0usize;
    let mut element_decl = 0usize;
    let mut curve_entries = 0usize;
    let mut node_bytes = 0usize;
    let mut reps_unexported: Vec<String> = Vec::new();
    let mut reps_dup_pin: Vec<(usize, Option<DupPin>)> = Vec::new();
    let mut curves: Vec<Vec<(f64, f64, f64)>> = Vec::new();
    for (k, m) in decoded.iter().enumerate() {
        let d = &m.rep;
        node_bytes += d.payload_len;
        if k >= groups.len() {
            reps_unexported.push(format!(
                "rep {k}: no pool group to re-list ({} pool \
                 groups for {} law-decoded reps; per-rep \
                 absorption unestablished)",
                groups.len(),
                decoded.len()
            ));
            continue;
        }
        let nxt = if k + 1 < decoded.len() {
            decoded[k + 1].rep.pos
        } else {
            hi
        };
        let (records, n_hdrs) =
            parse_strip_records(data, d.region_end, nxt, d.elem, Some(&d.elements));
        let grefs: Vec<u32> = records
            .iter()
            .filter(|r| GATED.contains(&r.marker))
            .flat_map(|r| r.refs.iter().copied())
            .collect();
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
        let tri_res = triangulate(&d.elements, &records);
        // stage-10 E0-b candidate (see decode_per_rep; the None case
        // recorded too — the unpinnable veto, stage-10 review F1):
        // merged at the store level below, only when the whole mesh is
        // empty.
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
        // The §2.3 curve exposure: this exported rep's dropped loops'
        // pre-weld sequences (additive, outside Fidelity).
        for (_mk, loop_refs) in &tri_res.dropped_loops {
            curves.push(curve_sequence(loop_refs, &d.elements));
        }
        facet_candidates += n_hdrs;
        facet_records += records.len();
        write_count += d.write_count as usize;
        // the twin's ``table_bytes += (d["elem"] + 3) // 4`` — the
        // table-law reps' declared table length only
        #[allow(clippy::manual_div_ceil)]
        if m.law == "table" {
            table_bytes += (d.elem as usize + 3) / 4;
        }
        element_decl += d.elem as usize;
        curve_entries += d.elements.len() - d.pts.len();
        for rec in &records {
            if !matches!(rec.marker, 0x42 | 0x4A | 0x4C) {
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
    // Stage-10 E0-b store-level gate (see decode_per_rep).
    let mut curve_entry_law = 0u32;
    if triangles.is_empty()
        && !reps_dup_pin.is_empty()
        && reps_dup_pin.iter().all(|(_b, c)| c.is_some())
    {
        for (b, c) in &reps_dup_pin {
            let dp = c.as_ref().expect("all(...) guarded");
            triangles.extend(
                dp.triangles
                    .iter()
                    .map(|&(a, s, t)| (a + *b as u32, s + *b as u32, t + *b as u32)),
            );
            degenerate += dp.degenerate;
            loops_exported += dp.loops;
            curve_entry_law += dp.loops;
        }
        loops_curve_entry = 0;
    }
    let mut info = CompositeInfo {
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
        reps_decoded: Some(decoded.len()),
        reps_exported: Some(decoded.len() - reps_unexported.len()),
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
        curve_entry_law: None,
        loops_curve_entry_exported: None,
        unordered_dedup_dropped: None,
        unordered_dedup_declined: None,
    };
    if curve_entry_law > 0 {
        info.curve_entry_law = Some("e0b-dup-pin");
        info.loops_curve_entry_exported = Some(curve_entry_law);
    }
    // Stage-15 unordered-triangle dedup (see apply_unordered_dedup):
    // the store-level gate, as in decode_per_rep.
    let triangles = apply_unordered_dedup(triangles, &mut info);
    Ok(CompositeDecode {
        points,
        triangles,
        degenerate,
        info,
        curves,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

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

    /// The stage-10 dup-pin law (relaxed): a loop-referenced skip slot
    /// welds to the immediately preceding written element; element 0
    /// (no predecessor) is unpinnable and vetoes.
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
        let dropped = vec![(0x4Au8, vec![1u32, 2, 3])];
        let pin = e0b_dup_pin(&elements, &points, &written_rank, &dropped).expect("pinnable");
        assert_eq!(pin.loops, 1);
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
        let dropped0 = vec![(0x4Au8, vec![0u32, 1])];
        assert!(e0b_dup_pin(&elements0, &points0, &rank0, &dropped0).is_none());
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
            curve_entry_law: None,
            loops_curve_entry_exported: None,
            unordered_dedup_dropped: None,
            unordered_dedup_declined: None,
        };
        let tris = vec![(0u32, 1u32, 2u32), (2, 1, 0), (0, 1, 3)];
        let kept = apply_unordered_dedup(tris, &mut info);
        assert_eq!(kept, vec![(0, 1, 2), (0, 1, 3)]);
        assert_eq!(info.unordered_dedup_dropped, Some(1));
        assert_eq!(info.unordered_dedup_declined, None);
        // Declined: a fin that is NOT a duplicate keeps the mesh
        // over-used after the dup's removal.
        let mut info2 = info.clone();
        info2.unordered_dedup_dropped = None;
        info2.unordered_dedup_declined = None;
        let tris2 = vec![(0u32, 1u32, 2u32), (2, 1, 0), (0, 1, 3), (1, 0, 4)];
        let kept2 = apply_unordered_dedup(tris2, &mut info2);
        assert_eq!(kept2, vec![(0, 1, 2), (2, 1, 0), (0, 1, 3), (1, 0, 4)]);
        assert_eq!(info2.unordered_dedup_dropped, None);
        assert_eq!(info2.unordered_dedup_declined, Some(1));
        // A manifold two-sided sheet never fires (the zero-regression
        // direction).
        let mut info3 = info.clone();
        info3.unordered_dedup_dropped = None;
        let sheet = vec![(0u32, 1u32, 2u32), (2, 1, 0)];
        let kept3 = apply_unordered_dedup(sheet, &mut info3);
        assert_eq!(kept3, vec![(0, 1, 2), (2, 1, 0)]);
        assert_eq!(info3.unordered_dedup_dropped, None);
        // Degenerate-shaped triples are never deduped.
        let mut info4 = info.clone();
        info4.unordered_dedup_dropped = None;
        let degenerate = vec![(0u32, 0u32, 1u32), (0, 0, 1)];
        let kept4 = apply_unordered_dedup(degenerate, &mut info4);
        assert_eq!(kept4, vec![(0, 0, 1), (0, 0, 1)]);
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
}
