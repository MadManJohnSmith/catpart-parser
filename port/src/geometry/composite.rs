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
/// ``stats`` dict minus the stage-3 ``dup_pin`` candidate.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct LoopStats {
    /// Loops exported (no skip reference).
    pub loops_exported: u32,
    /// Loops dropped for referencing a skip slot (the curve entries).
    pub loops_curve_entry: u32,
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
/// ``(points, triangles, degenerate, info)`` return tuple (the
/// duplicate ``points`` of the summary's ``vertices`` kept separate so
/// the stage-3 curve exposure can hang off the same decode).
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
/// polygon fans (0x4c) skip repeated coordinates.
fn triangulate(
    elements: &[Element],
    records: &[CompositeRecord],
) -> (Vec<(u32, u32, u32)>, u32, LoopStats) {
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
    let mut stats = LoopStats::default();
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
                stats.loops_curve_entry += 1;
                continue;
            }
            stats.loops_exported += 1;
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
    (triangles, degenerate, stats)
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
        let (tri_k, deg_k, stats_k) = triangulate(&d.elements, &records);
        // stage-10 E0-b candidate for this rep lands with stage 3
        // (its store-level merge gate is the whole-mesh-empty one);
        // the loop counters here are already the twin's.
        points.extend(d.pts.iter().copied());
        triangles.extend(
            tri_k
                .iter()
                .map(|&(a, b, c)| (a + base as u32, b + base as u32, c + base as u32)),
        );
        degenerate += deg_k;
        loops_exported += stats_k.loops_exported;
        loops_curve_entry += stats_k.loops_curve_entry;
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
    // Stage-10 E0-b store-level gate lands with stage 3 (the fire
    // needs the candidates the dup-pin evaluation produces).
    let info = CompositeInfo {
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
    // Stage-15 unordered-triangle dedup lands with stage 3 (the
    // store-level gate; the reps' element spaces are disjoint).
    Ok(CompositeDecode {
        points,
        triangles,
        degenerate,
        info,
    })
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
            // the family (its own failure is re-raised). PORT STAGE 1:
            // the raw-array + mixedwrite consumers land with stage 2 —
            // the branch fails closed with the twin's class naming the
            // stage-2 gap (error classes are the machine contract, §3.2).
            return Err(ExportError::new(
                UNDECODED_VARIANT,
                format!(
                    "{}; the stage-4a raw-array law and the stage-8 \
                     mixed-write per-rep composition land with port \
                     stage 2 (ticket #42): fail-closed interim",
                    exc.detail
                ),
            ));
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

    let (triangles, degenerate, loop_stats) = triangulate(&elements, &records);
    // Stage-10 E0-b dup-pin law lands with stage 3 (single-rep path:
    // the merge fires on this call's empty primary triangulation when
    // every dropped curve-entry loop is pinnable).
    let mut skipped_markers: BTreeMap<u8, u32> = BTreeMap::new();
    for rec in &records {
        if !matches!(rec.marker, 0x42 | 0x4A | 0x4C) {
            *skipped_markers.entry(rec.marker).or_insert(0) += 1;
        }
    }
    let info = CompositeInfo {
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
        loops_exported: loop_stats.loops_exported,
        loops_curve_entry: loop_stats.loops_curve_entry,
        curve_entry_law: None,
        loops_curve_entry_exported: None,
        unordered_dedup_dropped: None,
        unordered_dedup_declined: None,
    };
    // Stage-15 unordered-triangle dedup lands with stage 3 (fires
    // only on a not-manifold assembled mesh whose duplicate unordered
    // triples resolve it — a passing store's mesh is never touched).
    Ok(CompositeDecode {
        points,
        triangles,
        degenerate,
        info,
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
