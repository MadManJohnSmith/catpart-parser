//! Display carriers for a part with **no surface** — never a reconstruction.
//!
//! The port of the Python reference module ``catpart.geometry.display``
//! (``src/catpart/geometry/display.py``), per spec §2.1 of
//! ``docs/specs/phase5-viewer-spec.md``.  The evidence is
//! ``docs/evidence/2026-11-19-no-surface-fallback.md``.
//!
//! The 120 no-facet parts of the 128-part population open as nothing:
//! the nested-store path raises, there is no ``a5 03 34`` surface frame
//! and no structured grid triangulates.  Their bytes still carry geometry
//! — the 3-divisible f64 point runs (profiles, limit boxes, sub-grid
//! arrays) and, in the store bodies, the ``33 3X`` curve records — so the
//! viewer shows exactly that: a point cloud and the curve segments the
//! record laws pin.
//!
//! - points are the decoded carrier coordinates, rounded once to f32 (the
//!   viewer's array precision);
//! - a segment exists only where a curve record's own law pins two
//!   endpoints: the ``33 32`` line under the committed G2 ``[P][Q][P]+|Q|``
//!   reading, where the first triple is P and the second is the
//!   displacement Q (the trailing float is ``|Q|``), so the segment spans
//!   ``P -> P+Q``.  Measured: on the law-holding records of 120
//!   pool-bearing files ``P+Q`` lands on a decoded pool vertex
//!   3,503/5,531 = 0.6333 at 5e-3 mm, against 11/5,531 for P and 38/5,531
//!   for Q (claim DF-03);
//! - the circle / mid-ring / conic families expose a center and a radius
//!   but no orientation, so they contribute their center as a point and
//!   never a guessed polyline;
//! - the bag-rep payload's count-framed f32 point arrays (source label
//!   ``bagrep-f32-points``) contribute their declared triples as points
//!   (``docs/evidence/2026-11-19-bagrep.md``: coordinates only, no face
//!   list and no implicit strip, so they are never connected);
//! - no triangle, no weld, no inferred join.  The summary block says
//!   ``surface = false`` and the warning class is ``no-surface-display``.
//!
//! Fail-closed: a malformed record (short payload, non-finite or
//! out-of-envelope field, failed direction/length law) contributes
//! nothing and is counted as skipped; a framed array must pass every
//! gate of the count-first measurement or contributes nothing; a part
//! with no displayable carrier keeps its pre-display classification.
//!
//! Numeric contract (spec §2.2): f64 decode arithmetic in the twin's
//! expression order; the single ``f64 -> f32`` narrowing is the viewer
//! array precision and is applied through ``as f32`` (round to nearest),
//! the same narrowing the twin performs with ``struct.pack("<f")``.
#![allow(clippy::suboptimal_flops)]

use std::collections::BTreeMap;

use super::{grid, store};

/// The summary block's honesty labels (the twin's ``KIND``/``SURFACE``).
pub const KIND: &str = "decoded-carriers";
/// The added source label for the bag-rep count-framed f32 arrays.
pub const SOURCE_BAGREP: &str = "bagrep-f32-points";
/// The added source label for the empty-scan f32 point-run fallback.
pub const SOURCE_F32_RUNS: &str = "store-f32-points";
pub const SURFACE: bool = false;

/// The feature/spec-tree block's honesty label: the tree is a display
/// of the part's parametric records, never geometry (no triangle, no
/// point, no segment comes from it and the honest open rate does not
/// credit it) — the twin's ``FEATURE_KIND``.
pub const FEATURE_KIND: &str = "feature-tree-only";
/// The feature-tree block's source label (the framing the names sit in).
pub const SOURCE_FEATURE_TREE: &str = "catprtcont-feature-tokens";
/// The part-container token the kind law names the part marker.
pub const CONTAINER_TOKEN: &[u8] = b"CATPrtCont";
/// The measured feature-type vocabulary (the audit probe's shipped
/// subset): every type carries >= 1 length-framed occurrence in the
/// BLANK population.  The parameter-type family (``Volume``/``Density``
/// /``Area``/``Mass`` — mass-properties headers) is excluded.
pub const FEATURE_TYPES: [&str; 17] = [
    "Axis",
    "Boundary",
    "Chamfer",
    "Circle",
    "Curve",
    "EdgeFillet",
    "Hole",
    "Line",
    "Mirror",
    "Offset",
    "Pad",
    "Pattern",
    "Plane",
    "Point",
    "Pocket",
    "Rib",
    "Sketch",
];

/// The empty-scan fallback's 12-byte f32 point-run law (the missing-store
/// census measurement, the twin's ``F32_RUN_*``): finite triples inside
/// the (1e-2, 1e5) envelope (no near-zero coordinates — the measured
/// law), runs chained at exactly the 12-byte stride, from 3 triples.
/// It applies ONLY when every primary carrier came up empty.
pub const F32_RUN_FLOOR: f64 = 1e-2;
pub const F32_RUN_CEIL: f64 = 1e5;
pub const F32_RUN_MIN_TRIPLES: usize = 3;
pub const F32_SCAN_MAX_REGION: usize = 16 * 1024 * 1024;
/// The parametric blocks the fallback never reads (ticket #69, the twin's
/// ``F32_RUN_SKIP_BLOCKS``).  These blocks are the part tree / feature
/// parameters; the runs law was measured only in body and geometry
/// containers (CATSeeBodyCont 57, CATBRepModeContainer 11, CATStdCont 9,
/// CGMGeom 6 — 0/83 census files in CATPrtCont).  The McLaren Senna's
/// 244,817 points were 244,811 f32 triples of CATPrtCont tessellation
/// cache, read as runs.
const F32_RUN_SKIP_BLOCKS: [&str; 3] = ["CATPrtCont", "CATProdCont", "CATMechProdCont"];

/// The bag-rep payload containers the count-framed arrays live in.
const BAGREP_PAYLOAD_BLOCKS: [&str; 5] = [
    "CATStdCont",
    "CATSeeBodyCont",
    "CATBRepModeContainer",
    "CGMGeom",
    "CATCGRCont",
];
/// Count-first framing bounds (the bag-rep measurement).
const BAGREP_MAX_FLOATS: usize = 3_000_000;
/// Largest payload region the count-first scan walks (the twin's
/// ``BAGREP_MAX_REGION``): larger regions are skipped fail-closed.
const BAGREP_MAX_REGION: usize = 4 * 1024 * 1024;
const BAGREP_MIN_NONZERO: f64 = 0.5;
const BAGREP_MAX_CONST_RUN: usize = 64;
/// The clean-f32 window the framing test uses; the display envelope is
/// applied per point afterwards.
const BAGREP_VALUE_FLOOR: f64 = 1e-6;
const BAGREP_VALUE_CEIL: f64 = 1e6;

pub const FAMILY_LINE: u8 = 0x32;
pub const FAMILY_MIDRING: u8 = 0x33;
pub const FAMILY_CIRCLE: u8 = 0x37;
pub const FAMILY_CONIC: u8 = 0x38;

/// The families the BR3 walker accepts (``33 36`` is walked, not decoded).
const FAMILIES: [u8; 5] = [0x32, 0x33, 0x36, 0x37, 0x38];

const HEADER_BYTES: usize = 7;
const MAX_RECORD_LEN: usize = 256;
/// Pool-scale plausibility cap for the BE-float families (BR3).
const MAX_VALUE: f64 = 1e7;
/// Unit-norm tolerance for the direction pair (BR3).
const DIR_TOL: f64 = 2e-3;
/// Relative tolerance for the ``|Q|`` length law (BR3).
const LEN_TOL: f64 = 1e-6;
/// The canonical ``33 32`` record's 40-B f32le block.
const LINE_BLOCK_BYTES: usize = 40;

/// One walked ``33 3X`` curve record (BR3 C1 layout).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct CurveRecord {
    offset: usize,
    family: u8,
    length: usize,
    payload: usize,
    end: usize,
}

/// Maximal 12-byte-stride f32 point runs in `[lo, hi)` as
/// `(start, triples)` (the twin's `_f32_point_runs`; the missing-store
/// census law verbatim, region-local).
fn f32_point_runs(data: &[u8], lo: usize, hi: usize) -> Vec<(usize, usize)> {
    let size = hi.saturating_sub(lo);
    if size < 12 {
        return Vec::new();
    }
    let mut ok = vec![0u8; size - 11];
    for (offset, flag) in ok.iter_mut().enumerate() {
        let o = lo + offset;
        let x = bagrep_f32(data, o);
        let y = bagrep_f32(data, o + 4);
        let z = bagrep_f32(data, o + 8);
        *flag = (x.is_finite()
            && y.is_finite()
            && z.is_finite()
            && F32_RUN_FLOOR < x.abs()
            && x.abs() < F32_RUN_CEIL
            && F32_RUN_FLOOR < y.abs()
            && y.abs() < F32_RUN_CEIL
            && F32_RUN_FLOOR < z.abs()
            && z.abs() < F32_RUN_CEIL) as u8;
    }
    let mut runs = Vec::new();
    let mut offset = 0usize;
    while offset < ok.len() {
        if ok[offset] == 1 && (offset < 12 || ok[offset - 12] == 0) {
            let mut length = 0usize;
            let mut cursor = offset;
            while cursor < ok.len() && ok[cursor] == 1 {
                length += 1;
                cursor += 12;
            }
            if length >= F32_RUN_MIN_TRIPLES {
                runs.push((lo + offset, length));
            }
            offset = cursor.max(offset + 1);
        } else {
            offset += 1;
        }
    }
    runs
}

/// Every body/geometry block's payload region, bounded per region (the
/// twin's `_raw_block_regions`) — the empty-scan fallback's scope.  The
/// parametric blocks (`F32_RUN_SKIP_BLOCKS`) are dropped from the scan
/// set, but every valid block still bounds its neighbours' regions.
fn raw_block_regions(data: &[u8]) -> Vec<(usize, usize)> {
    let size = data.len();
    let outer = if size >= 12 {
        u32::from_be_bytes([data[8], data[9], data[10], data[11]]) as usize
    } else {
        0
    };
    let blocks = store::valid_blocks(data);
    let mut regions: Vec<(usize, usize)> = blocks
        .iter()
        .filter(|(_, name)| !F32_RUN_SKIP_BLOCKS.contains(&name.as_str()))
        .map(|(blk, _)| (*blk, store::probe_region(*blk, &blocks, outer, size)))
        .collect();
    regions.sort_unstable();
    regions.dedup();
    regions
        .into_iter()
        .filter(|(lo, hi)| hi.saturating_sub(*lo) <= F32_SCAN_MAX_REGION)
        .collect()
}

/// One part's display carriers: the point cloud and the pinned segments.
#[derive(Debug, Clone, PartialEq)]
pub struct DisplayScan {
    pub block: Option<usize>,
    pub regions: usize,
    pub point_runs: usize,
    pub run_points: usize,
    pub pool_points: usize,
    pub curve_records: usize,
    pub decoded_curve_records: usize,
    pub skipped_curve_records: usize,
    pub curve_points: usize,
    pub line_records: usize,
    pub families: BTreeMap<String, usize>,
    pub bagrep_regions: usize,
    pub bagrep_arrays: usize,
    pub bagrep_floats: usize,
    pub bagrep_points: usize,
    pub bagrep_skipped: usize,
    pub points: Vec<(f64, f64, f64)>,
    pub segments: Vec<(u32, u32)>,
    pub f32_runs: usize,
    pub f32_points: usize,
}

impl DisplayScan {
    pub fn has_carriers(&self) -> bool {
        !self.points.is_empty()
    }

    /// The non-empty source labels behind the displayed points (the
    /// twin's ``sources``).
    pub fn sources(&self) -> Vec<String> {
        let mut names = Vec::new();
        if self.pool_points > 0 || self.run_points > 0 || self.curve_points > 0 {
            names.push(KIND.to_string());
        }
        if self.bagrep_points > 0 {
            names.push(SOURCE_BAGREP.to_string());
        }
        if self.f32_points > 0 {
            names.push(SOURCE_F32_RUNS.to_string());
        }
        names
    }

    /// The visible, never-a-surface label (the twin's ``label_for``).
    pub fn label(&self) -> String {
        label_for(self.points.len(), self.segments.len())
    }
}

/// The twin's ``label_for``: grammatical, and always says "no surface".
pub fn label_for(points: usize, segments: usize) -> String {
    let point_word = if points == 1 { "point" } else { "points" };
    let segment_word = if segments == 1 { "segment" } else { "segments" };
    format!("no surface — showing {points} {point_word}, {segments} curve {segment_word}")
}

/// One part's feature/spec tree: the framed feature-type names — the
/// twin's :class:`catpart.geometry.display.FeatureTreeScan`.  Nothing
/// here is geometry: the scan names records, it does not decode
/// coordinates.
#[derive(Debug, Clone, PartialEq)]
pub struct FeatureTreeScan {
    /// The ``CATPrtCont`` token count (the kind law's part marker).
    pub containers: usize,
    /// ``(type, count, first_offset)`` in first-occurrence (byte) order
    /// — the writer emits the feature records in creation order, so the
    /// byte order approximates the spec tree's order.
    pub features: Vec<(String, usize, usize)>,
    /// The total framed occurrences.
    pub feature_names: usize,
}

impl FeatureTreeScan {
    pub fn has_tree(&self) -> bool {
        self.containers > 0 || !self.features.is_empty()
    }
}

/// Count ``token``'s occurrences (the twin's ``_count_token``).
fn count_token(data: &[u8], token: &[u8]) -> usize {
    let mut count = 0usize;
    let mut pos = 0usize;
    while let Some(at) = super::store::find(data, token, pos, data.len()) {
        count += 1;
        pos = at + 1;
    }
    count
}

/// The candidate-name charset (the twin's ``[A-Za-z0-9_.]``).
fn name_byte(b: u8) -> bool {
    b.is_ascii_alphanumeric() || b == b'_' || b == b'.'
}

/// The type of one framed name, ``Some(type)`` when the full text
/// matches a pinned :data:`FEATURE_TYPES` entry with an optional
/// instance suffix (``.N`` / ``N``) — the twin's
/// ``_FEATURE_INSTANCE_RE`` full-name match.
fn feature_type_of(name: &str) -> Option<&'static str> {
    for typ in FEATURE_TYPES {
        if let Some(rest) = name.strip_prefix(typ) {
            // the instance suffix is optional: bare types match too
            let ok = match rest.strip_prefix('.') {
                Some(digits) => !digits.is_empty() && digits.bytes().all(|b| b.is_ascii_digit()),
                None => rest.is_empty() || rest.bytes().all(|b| b.is_ascii_digit()),
            };
            if ok {
                return Some(typ);
            }
        }
    }
    None
}

/// The name bytes one candidate regex reads at ``i`` (the twin's
/// ``FEATURE_CANDIDATE_RE`` greedy ``[A-Z][A-Za-z0-9_.]{2,38}``): the
/// maximal charset run from ``i + 1``, capped at 39 characters, or
/// ``None`` when the run is shorter than the regex's minimum (an
/// uppercase letter + 2 more).
fn candidate_name(data: &[u8], i: usize) -> Option<&[u8]> {
    let mut run = 0usize;
    let cap = (data.len() - (i + 1)).min(39);
    while run < cap && name_byte(data[i + 1 + run]) {
        run += 1;
    }
    if run < 3 {
        return None;
    }
    Some(&data[i + 1..i + 1 + run])
}

/// Decode one part's feature/spec-tree names — the twin's
/// :func:`catpart.geometry.display.scan_feature_tree`.
///
/// The whole file is scanned for the writer's length-framed ASCII names:
/// a length byte ``L`` (4..40) followed by exactly ``L - 1`` ASCII name
/// bytes whose FULL text matches one of the pinned ``FEATURE_TYPES``
/// (instance suffixes ``.N`` / ``N`` allowed) — the framing measured on
/// the anchors (``00 07 Sketch``, ``05 Pad1``, ``09 Sketch.1``,
/// ``0b EdgeFillet``).  The name is the candidate regex's maximal
/// charset run, so a run that continues past the length byte's promise
/// rejects (the same validation the twin's regex + ``len(name) + 1``
/// check performs).  A name census only: no coordinate is decoded, no
/// geometry is claimed.
pub fn scan_feature_tree(data: &[u8]) -> FeatureTreeScan {
    let containers = count_token(data, CONTAINER_TOKEN);
    // first-occurrence offset per type, in scan order (byte order)
    let mut order: Vec<&'static str> = Vec::new();
    let mut counts: BTreeMap<&'static str, usize> = BTreeMap::new();
    let mut total = 0usize;
    let mut i = 0usize;
    while i + 4 <= data.len() {
        let length = data[i] as usize;
        if (4..=40).contains(&length) && i + length <= data.len() {
            if let Some(name) = candidate_name(data, i) {
                if name.len() == length - 1 {
                    if let Ok(text) = std::str::from_utf8(name) {
                        if let Some(typ) = feature_type_of(text) {
                            total += 1;
                            *counts.entry(typ).or_insert(0) += 1;
                            if !order.contains(&typ) {
                                order.push(typ);
                            }
                        }
                    }
                }
            }
        }
        i += 1;
    }
    let features = order
        .into_iter()
        .map(|typ| (typ.to_string(), counts[&typ], find_first_offset(data, typ)))
        .collect();
    FeatureTreeScan {
        containers,
        features,
        feature_names: total,
    }
}

/// The first framed occurrence's name offset for ``typ`` (the twin's
/// ``match.start() + 1``: the length byte's position + 1).
fn find_first_offset(data: &[u8], typ: &str) -> usize {
    let mut i = 0usize;
    while i + 4 <= data.len() {
        let length = data[i] as usize;
        if (4..=40).contains(&length) && i + length <= data.len() {
            if let Some(name) = candidate_name(data, i) {
                if name.len() == length - 1 {
                    if let Ok(text) = std::str::from_utf8(name) {
                        if let Some(found) = feature_type_of(text) {
                            if found == typ {
                                return i + 1;
                            }
                        }
                    }
                }
            }
        }
        i += 1;
    }
    0
}

/// Round one coordinate to f32 (the viewer's precision), kept as f64.
fn f32_round(value: f64) -> f64 {
    f64::from(value as f32)
}

/// A model coordinate: finite, zero allowed, inside the 100 m envelope.
fn plausible(value: f64) -> bool {
    value.is_finite()
        && (value == 0.0 || (grid::COORD_FLOOR <= value.abs() && value.abs() <= grid::COORD_CEIL))
}

/// The part's carrier regions: the located store bodies + ``CATPrtCont``.
fn region_list(data: &[u8], spans: &[(usize, usize)]) -> Vec<(usize, usize)> {
    let mut regions: Vec<(usize, usize)> = spans.to_vec();
    regions.extend(grid::regions(data));
    regions.extend(located_store_regions(data));
    regions.sort_unstable();
    regions.dedup();
    regions
}

/// The container-probing law's store bodies (the census/brep-probe law;
/// the twin's `_located_store_regions`): CATStdCont, CATXDocLinkCont,
/// CATSeeBodyCont, then any other block.  Failures contribute nothing.
fn located_store_regions(data: &[u8]) -> Vec<(usize, usize)> {
    let d8 = if data.len() >= 12 {
        u32::from_be_bytes([data[8], data[9], data[10], data[11]]) as usize
    } else {
        0
    };
    let blocks = store::valid_blocks(data);
    let mut out: Vec<(usize, usize)> = Vec::new();
    for container in [
        store::CONTAINER_STDCONT,
        store::CONTAINER_XDOCLINK,
        store::CONTAINER_SEEBODY,
        store::CONTAINER_OTHER,
    ] {
        let want = match container {
            store::CONTAINER_STDCONT => Some("CATStdCont"),
            store::CONTAINER_XDOCLINK => Some("CATXDocLinkCont"),
            store::CONTAINER_SEEBODY => Some("CATSeeBodyCont"),
            _ => None,
        };
        for (blk, name) in &blocks {
            if want.is_some_and(|want| name != want) {
                continue;
            }
            if let Ok(Some(span)) = store::locate_store(data, *blk, &blocks, d8, container) {
                out.push((span.body_lo, span.body_hi));
            }
        }
    }
    out
}

/// The bag-rep payload containers' ``(start, end)``, in byte order (the
/// twin's ``_bagrep_regions``).
fn bagrep_regions(data: &[u8]) -> Vec<(usize, usize)> {
    let size = data.len();
    let outer = if size >= 12 {
        u32::from_be_bytes([data[8], data[9], data[10], data[11]]) as usize
    } else {
        0
    };
    let blocks = store::valid_blocks(data);
    let mut regions: Vec<(usize, usize)> = blocks
        .iter()
        .filter(|(_, name)| BAGREP_PAYLOAD_BLOCKS.contains(&name.as_str()))
        .map(|(blk, _)| (*blk, store::probe_region(*blk, &blocks, outer, size)))
        .filter(|(lo, hi)| hi - lo <= BAGREP_MAX_REGION)
        .collect();
    regions.sort_unstable();
    regions.dedup();
    regions
}

/// The count-first measurement's clean-f32 test (pool scale).
fn bagrep_clean(value: f64) -> bool {
    value.is_finite()
        && (value == 0.0 || (BAGREP_VALUE_FLOOR <= value.abs() && value.abs() <= BAGREP_VALUE_CEIL))
}

fn bagrep_f32(data: &[u8], off: usize) -> f64 {
    f32::from_le_bytes([data[off], data[off + 1], data[off + 2], data[off + 3]]) as f64
}

/// Clean-f32 prefix sums per 4-byte frame (the twin's ``_BagrepClean``).
///
/// A candidate count is tested against a multi-hundred-KB region, so the
/// all-clean window and the clean-run-end test are prefix differences
/// instead of O(count) scans.
struct BagrepClean {
    lo: usize,
    sums: [Vec<u32>; 4],
}

impl BagrepClean {
    fn new(data: &[u8], lo: usize, hi: usize) -> Self {
        let mut sums: [Vec<u32>; 4] = [Vec::new(), Vec::new(), Vec::new(), Vec::new()];
        for (shift, prefix) in sums.iter_mut().enumerate() {
            let count = (hi - lo).saturating_sub(shift).div_euclid(4);
            prefix.reserve(count + 1);
            prefix.push(0);
            let mut total = 0u32;
            for index in 0..count {
                if bagrep_clean(bagrep_f32(data, lo + shift + 4 * index)) {
                    total += 1;
                }
                prefix.push(total);
            }
        }
        Self { lo, sums }
    }

    fn all_clean(&self, start: usize, count: usize) -> bool {
        let relative = start - self.lo;
        let shift = relative % 4;
        let index = (relative - shift) / 4;
        let prefix = &self.sums[shift];
        index + count < prefix.len() && prefix[index + count] - prefix[index] == count as u32
    }

    fn clean_at(&self, start: usize) -> bool {
        let relative = start - self.lo;
        let shift = relative % 4;
        let index = (relative - shift) / 4;
        let prefix = &self.sums[shift];
        index + 1 < prefix.len() && prefix[index + 1] - prefix[index] == 1
    }
}

fn bagrep_nonzero(data: &[u8], start: usize, count: usize) -> f64 {
    let mut nonzero = 0usize;
    for index in 0..count {
        if bagrep_f32(data, start + 4 * index) != 0.0 {
            nonzero += 1;
        }
    }
    nonzero as f64 / count as f64
}

fn bagrep_max_const_run(data: &[u8], start: usize, count: usize) -> usize {
    let mut longest = 1usize;
    let mut run = 1usize;
    let mut previous = bagrep_f32(data, start);
    for index in 1..count {
        let value = bagrep_f32(data, start + 4 * index);
        if value == previous {
            run += 1;
            if run > longest {
                longest = run;
            }
        } else {
            run = 1;
            previous = value;
        }
    }
    longest
}

/// The count-framed f32 arrays in ``[lo, hi)`` as ``(start, floats)``
/// (the twin's ``_bagrep_arrays``).
fn bagrep_arrays(data: &[u8], lo: usize, hi: usize) -> Vec<(usize, usize)> {
    let clean = BagrepClean::new(data, lo, hi);
    let mut found: Vec<(usize, usize)> = Vec::new();
    let mut seen: Vec<(usize, usize)> = Vec::new();
    let mut offset = lo;
    while offset + 4 < hi {
        if data[offset + 3] == 0 {
            let count = u32::from_le_bytes([
                data[offset],
                data[offset + 1],
                data[offset + 2],
                data[offset + 3],
            ]) as usize;
            #[allow(clippy::manual_range_contains, clippy::manual_is_multiple_of)]
            if count >= 9 && count <= BAGREP_MAX_FLOATS && count % 3 == 0 {
                for delta in 0..17 {
                    let start = offset + 4 + delta;
                    if start + 4 * count > hi {
                        break;
                    }
                    if !clean.all_clean(start, count) {
                        continue;
                    }
                    if clean.clean_at(start + 4 * count) {
                        continue;
                    }
                    if bagrep_nonzero(data, start, count) < BAGREP_MIN_NONZERO {
                        continue;
                    }
                    if bagrep_max_const_run(data, start, count) > BAGREP_MAX_CONST_RUN {
                        continue;
                    }
                    let key = (start, count);
                    if !seen.contains(&key) {
                        seen.push(key);
                        found.push(key);
                    }
                    break;
                }
            }
        }
        offset += 1;
    }
    found.sort_by(|a, b| a.0.cmp(&b.0).then(b.1.cmp(&a.1)));
    let mut keep: Vec<(usize, usize)> = Vec::new();
    for item in found {
        let contained = keep.iter().any(|kept: &(usize, usize)| {
            kept.0 <= item.0 && kept.0 + 4 * kept.1 >= item.0 + 4 * item.1
        });
        if !contained {
            keep.push(item);
        }
    }
    keep
}

fn append_point(points: &mut Vec<(f64, f64, f64)>, point: (f64, f64, f64)) -> Option<u32> {
    let rounded = (f32_round(point.0), f32_round(point.1), f32_round(point.2));
    if !(plausible(rounded.0) && plausible(rounded.1) && plausible(rounded.2)) {
        return None;
    }
    points.push(rounded);
    Some((points.len() - 1) as u32)
}

/// Decode one part's display carriers (the twin's ``scan_part``).
///
/// ``spans`` are the located store bodies the export path already
/// validated; ``pool_points`` are the store path's decoded vertices (the
/// vertices-only success), displayed first.  Nothing here raises: a
/// record or run that does not decode is skipped and counted.
pub fn scan_part(
    data: &[u8],
    spans: &[(usize, usize)],
    pool_points: &[(f64, f64, f64)],
) -> DisplayScan {
    let regions = region_list(data, spans);
    let mut points: Vec<(f64, f64, f64)> = Vec::new();
    let mut segments: Vec<(u32, u32)> = Vec::new();

    let mut pool_count = 0usize;
    for point in pool_points {
        if append_point(&mut points, *point).is_some() {
            pool_count += 1;
        }
    }

    let mut point_runs = 0usize;
    let mut run_points = 0usize;
    for run in grid::iter_runs(data) {
        point_runs += 1;
        for point in &run.points {
            if append_point(&mut points, *point).is_some() {
                run_points += 1;
            }
        }
    }

    let bagrep_spans = bagrep_regions(data);
    let mut bagrep_array_count = 0usize;
    let mut bagrep_floats = 0usize;
    let mut bagrep_points = 0usize;
    let mut bagrep_skipped = 0usize;
    for (lo, hi) in &bagrep_spans {
        for (start, count) in bagrep_arrays(data, *lo, *hi) {
            bagrep_array_count += 1;
            bagrep_floats += count;
            for index in 0..(count / 3) {
                let off = start + 12 * index;
                let point = (
                    bagrep_f32(data, off),
                    bagrep_f32(data, off + 4),
                    bagrep_f32(data, off + 8),
                );
                if append_point(&mut points, point).is_some() {
                    bagrep_points += 1;
                } else {
                    bagrep_skipped += 1;
                }
            }
        }
    }

    let mut records: BTreeMap<usize, CurveRecord> = BTreeMap::new();
    for (lo, hi) in &regions {
        for record in iter_curve_records(data, *lo, *hi) {
            records.entry(record.offset).or_insert(record);
        }
    }

    let mut families: BTreeMap<String, usize> = BTreeMap::new();
    let mut decoded = 0usize;
    let mut skipped = 0usize;
    let mut curve_points = 0usize;
    let mut line_records = 0usize;
    for record in records.values() {
        *families
            .entry(format!("33 {:02x}", record.family))
            .or_insert(0) += 1;
        if record.family == FAMILY_LINE {
            match line_segment(data, record, &mut points) {
                Some((first, second)) => {
                    curve_points += 2;
                    line_records += 1;
                    decoded += 1;
                    segments.push((first, second));
                }
                None => skipped += 1,
            }
            continue;
        }
        if matches!(record.family, FAMILY_MIDRING | FAMILY_CIRCLE | FAMILY_CONIC) {
            match centre(data, record) {
                Some(center) if append_point(&mut points, center).is_some() => {
                    curve_points += 1;
                    decoded += 1;
                }
                _ => skipped += 1,
            }
            continue;
        }
        // 33 36 is out of decode scope (no established payload form).
        skipped += 1;
    }

    // The empty-scan fallback (#60): a container-less `V5_CFV2` binary
    // (no container-name table, so no located spans and no carriers
    // above) still carries 12-byte f32 point runs in its blocks — the
    // missing-store census measured them (CAAMaiUdfForMfgHoleInstance:
    // 93 points at 75029 in CATSeeBodyCont).  Only when every primary
    // source came up empty, over the valid blocks' payload regions,
    // under the measured run law — never instead of a decoded carrier.
    let mut f32_runs = 0usize;
    let mut f32_points = 0usize;
    if points.is_empty() {
        for (lo, hi) in raw_block_regions(data) {
            for (start, length) in f32_point_runs(data, lo, hi) {
                f32_runs += 1;
                for index in 0..length {
                    let off = start + 12 * index;
                    let point = (
                        bagrep_f32(data, off),
                        bagrep_f32(data, off + 4),
                        bagrep_f32(data, off + 8),
                    );
                    if append_point(&mut points, point).is_some() {
                        f32_points += 1;
                    }
                }
            }
        }
    }

    DisplayScan {
        block: regions.first().map(|(blk, _)| *blk),
        regions: regions.len(),
        point_runs,
        run_points,
        pool_points: pool_count,
        curve_records: records.len(),
        decoded_curve_records: decoded,
        skipped_curve_records: skipped,
        curve_points,
        line_records,
        families,
        bagrep_regions: bagrep_spans.len(),
        bagrep_arrays: bagrep_array_count,
        bagrep_floats,
        bagrep_points,
        bagrep_skipped,
        points,
        segments,
        f32_runs,
        f32_points,
    }
}

/// Walk every ``33 3X`` curve record behind its 7-B header (BR3 C1).
fn iter_curve_records(data: &[u8], lo: usize, hi: usize) -> Vec<CurveRecord> {
    let mut out: Vec<CurveRecord> = Vec::new();
    let mut p = lo;
    while p + HEADER_BYTES + 2 < hi && p + 1 < data.len() {
        if data[p] == 0x33 && FAMILIES.contains(&data[p + 1]) {
            let length = u16::from_le_bytes([data[p - 2], data[p - 1]]) as usize;
            let family = data[p + 1];
            if length > 0 && length <= MAX_RECORD_LEN && p >= lo + 6 {
                let payload = p + 2;
                let end = (p + 2 + length).min(data.len());
                let mut ok = end - payload == length;
                if ok && matches!(family, FAMILY_MIDRING | FAMILY_CIRCLE | FAMILY_CONIC) {
                    let nbe = if length >= 2 {
                        ((length - 2) / 4).min(7)
                    } else {
                        0
                    };
                    for index in 0..nbe {
                        let off = payload + 4 * index;
                        if off + 4 > end {
                            ok = false;
                            break;
                        }
                        let value = f32::from_be_bytes([
                            data[off],
                            data[off + 1],
                            data[off + 2],
                            data[off + 3],
                        ]) as f64;
                        if !(value.is_finite() && value.abs() < MAX_VALUE) {
                            ok = false;
                            break;
                        }
                    }
                }
                if ok {
                    out.push(CurveRecord {
                        offset: p,
                        family,
                        length,
                        payload,
                        end,
                    });
                    p += if family == FAMILY_LINE && length == 2 {
                        LINE_BLOCK_BYTES + 2
                    } else {
                        2 + length
                    };
                    continue;
                }
            }
        }
        p += 1;
    }
    out
}

/// The ``P -> P+Q`` segment of a law-holding ``33 32`` record, or None.
fn line_segment(
    data: &[u8],
    record: &CurveRecord,
    points: &mut Vec<(f64, f64, f64)>,
) -> Option<(u32, u32)> {
    let start = record.offset + 2;
    if start + LINE_BLOCK_BYTES > data.len() {
        return None;
    }
    let mut floats = [0.0f64; 10];
    for (index, value) in floats.iter_mut().enumerate() {
        let off = start + 4 * index;
        *value =
            f32::from_le_bytes([data[off], data[off + 1], data[off + 2], data[off + 3]]) as f64;
        if !(value.is_finite() && value.abs() < MAX_VALUE) {
            return None;
        }
    }
    let p_rep_ok = floats[6] == floats[0] && floats[7] == floats[1] && floats[8] == floats[2];
    let norm = (floats[3] * floats[3] + floats[4] * floats[4] + floats[5] * floats[5]).sqrt();
    let length_ok = (floats[9] - norm).abs() <= LEN_TOL * floats[9].abs().max(norm.abs());
    if !(p_rep_ok && length_ok) {
        return None;
    }
    let p = (floats[0], floats[1], floats[2]);
    let end = (p.0 + floats[3], p.1 + floats[4], p.2 + floats[5]);
    if !(plausible(p.0) && plausible(p.1) && plausible(p.2)) {
        return None;
    }
    if !(plausible(end.0) && plausible(end.1) && plausible(end.2)) {
        return None;
    }
    if floats[9] <= 0.0 || p == end {
        return None;
    }
    let first = append_point(points, p)?;
    let second = match append_point(points, end) {
        Some(second) => second,
        None => {
            points.pop();
            return None;
        }
    };
    Some((first, second))
}

fn be_f32(data: &[u8], off: usize) -> f64 {
    f32::from_be_bytes([data[off], data[off + 1], data[off + 2], data[off + 3]]) as f64
}

/// The decoded center of a ``33 33`` / ``33 37`` / ``33 38`` record.
fn centre(data: &[u8], record: &CurveRecord) -> Option<(f64, f64, f64)> {
    let payload = record.payload;
    let available = record.end - payload;
    match record.family {
        FAMILY_CIRCLE => {
            // 4 BE f32 (cx, cy, cz, r) + 2-B trailer.
            if record.length < 18 || available < 18 {
                return None;
            }
            let v = [
                be_f32(data, payload),
                be_f32(data, payload + 4),
                be_f32(data, payload + 8),
                be_f32(data, payload + 12),
            ];
            if !v.iter().all(|value| value.is_finite()) || v[3] == 0.0 {
                return None;
            }
            Some((v[0], v[1], v[2]))
        }
        FAMILY_MIDRING => {
            // 6 BE f32 (cx, cy, cz, cos t, sin t, r) + 2-B trailer.
            if record.length < 26 || available < 26 {
                return None;
            }
            let v: Vec<f64> = (0..6)
                .map(|index| be_f32(data, payload + 4 * index))
                .collect();
            if !v
                .iter()
                .all(|value| value.is_finite() && value.abs() < MAX_VALUE)
            {
                return None;
            }
            let (cos_t, sin_t) = (v[3], v[4]);
            let norm = (cos_t * cos_t + sin_t * sin_t).sqrt();
            let mid = DIR_TOL < cos_t.abs()
                && cos_t.abs() < 1.0 - DIR_TOL
                && DIR_TOL < sin_t.abs()
                && sin_t.abs() < 1.0 - DIR_TOL;
            if mid && (norm - 1.0).abs() > DIR_TOL {
                return None;
            }
            Some((v[0], v[1], v[2]))
        }
        FAMILY_CONIC => {
            // 7 BE f32 (cx, cy, cz, cos t, sin t, a, b) + 2-B trailer.
            if record.length < 30 || available < 30 {
                return None;
            }
            let v: Vec<f64> = (0..7)
                .map(|index| be_f32(data, payload + 4 * index))
                .collect();
            if !v
                .iter()
                .all(|value| value.is_finite() && value.abs() < MAX_VALUE)
            {
                return None;
            }
            let (cos_t, sin_t) = (v[3], v[4]);
            let norm = (cos_t * cos_t + sin_t * sin_t).sqrt();
            let mid = DIR_TOL < cos_t.abs()
                && cos_t.abs() < 1.0 - DIR_TOL
                && DIR_TOL < sin_t.abs()
                && sin_t.abs() < 1.0 - DIR_TOL;
            if mid && (norm - 1.0).abs() > DIR_TOL {
                return None;
            }
            if v[6] <= 0.0 {
                return None;
            }
            Some((v[0], v[1], v[2]))
        }
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// One ``33 32`` record: the 7-B header, the family, the 40-B block.
    fn line_record(floats: [f32; 10]) -> Vec<u8> {
        let mut data = Vec::new();
        data.extend_from_slice(&[0x02, 0x00, 0x07, 0x00, 0x00, 0x02, 0x00]);
        data.extend_from_slice(&[0x33, FAMILY_LINE]);
        for value in floats {
            data.extend_from_slice(&value.to_le_bytes());
        }
        data
    }

    fn law_holding() -> [f32; 10] {
        // P = (10, 0, 0), Q = (0, 10, 0), the repeated P, |Q| = 10.
        [10.0, 0.0, 0.0, 0.0, 10.0, 0.0, 10.0, 0.0, 0.0, 10.0]
    }

    #[test]
    fn label_names_the_carriers_plural_and_singular() {
        assert_eq!(
            label_for(6, 0),
            "no surface — showing 6 points, 0 curve segments"
        );
        assert_eq!(
            label_for(3, 1),
            "no surface — showing 3 points, 1 curve segment"
        );
        assert_eq!(
            label_for(1, 0),
            "no surface — showing 1 point, 0 curve segments"
        );
    }

    #[test]
    fn a_law_holding_line_pins_the_p_plus_q_segment() {
        let data = line_record(law_holding());
        let records = iter_curve_records(&data, 0, data.len());
        assert_eq!(records.len(), 1);
        let mut points = Vec::new();
        let segment =
            line_segment(&data, &records[0], &mut points).expect("the G2 laws hold on this block");
        assert_eq!(segment, (0, 1));
        assert_eq!(points, vec![(10.0, 0.0, 0.0), (10.0, 10.0, 0.0)]);
    }

    #[test]
    fn a_law_failing_line_pins_nothing() {
        let mut floats = law_holding();
        floats[9] = 7.0; // the trailing length no longer equals |Q|
        let data = line_record(floats);
        let records = iter_curve_records(&data, 0, data.len());
        assert_eq!(records.len(), 1, "the record is still walked");
        let mut points = Vec::new();
        assert_eq!(line_segment(&data, &records[0], &mut points), None);
        assert!(points.is_empty(), "no point is emitted for a refused law");
    }

    /// One count-framed f32 array: ``u32le count`` + the floats.
    fn bagrep_array(floats: &[f32]) -> Vec<u8> {
        let mut data = Vec::new();
        data.extend_from_slice(&(floats.len() as u32).to_le_bytes());
        for value in floats {
            data.extend_from_slice(&value.to_le_bytes());
        }
        data
    }

    #[test]
    fn a_count_framed_f32_array_frames_as_points() {
        let data = bagrep_array(&[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]);
        let arrays = bagrep_arrays(&data, 0, data.len());
        assert_eq!(arrays, vec![(4, 9)]);
        // The triples are the points; the array carries no connectivity.
        let points: Vec<(f64, f64, f64)> = (0..3)
            .map(|index| {
                let off = 4 + 12 * index;
                (
                    bagrep_f32(&data, off),
                    bagrep_f32(&data, off + 4),
                    bagrep_f32(&data, off + 8),
                )
            })
            .collect();
        assert_eq!(
            points,
            vec![(1.0, 2.0, 3.0), (4.0, 5.0, 6.0), (7.0, 8.0, 9.0)]
        );
    }

    #[test]
    fn a_count_framed_block_that_does_not_end_frames_nothing() {
        // The declared 9-float block is followed by more clean f32: the
        // count-first framing rejects it (a byte pattern, not an array).
        let mut data = bagrep_array(&(1..=9).map(|value| value as f32).collect::<Vec<f32>>());
        for value in 10..=21 {
            data.extend_from_slice(&(value as f32).to_le_bytes());
        }
        assert!(bagrep_arrays(&data, 0, data.len()).is_empty());
    }

    #[test]
    fn a_count_that_is_not_a_multiple_of_three_frames_nothing() {
        let data = bagrep_array(&[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]);
        assert!(bagrep_arrays(&data, 0, data.len()).is_empty());
    }

    #[test]
    fn an_out_of_envelope_line_pins_nothing() {
        let mut floats = law_holding();
        floats[0] = 1.0e6; // P outside the 100 m model envelope
        floats[6] = 1.0e6; // keep the P-repeat law exact
        let data = line_record(floats);
        let records = iter_curve_records(&data, 0, data.len());
        let mut points = Vec::new();
        assert_eq!(line_segment(&data, &records[0], &mut points), None);
        assert!(points.is_empty());
    }

    #[test]
    fn f32_point_runs_follow_the_missing_store_law() {
        // 7 consecutive 12-byte-stride triples: one run of 7 (#60).
        let mut data = Vec::new();
        for i in 1..8u32 {
            data.extend_from_slice(&(10.0f32 * i as f32).to_le_bytes());
            data.extend_from_slice(&(5.0f32 * i as f32).to_le_bytes());
            data.extend_from_slice(&(1.0f32 * i as f32).to_le_bytes());
        }
        assert_eq!(f32_point_runs(&data, 0, data.len()), vec![(0, 7)]);
        // near-zero coordinates sit outside the measured envelope
        let mut flat = Vec::new();
        for _ in 0..5 {
            flat.extend_from_slice(&0.0f32.to_le_bytes());
            flat.extend_from_slice(&0.0f32.to_le_bytes());
            flat.extend_from_slice(&0.0f32.to_le_bytes());
        }
        assert!(f32_point_runs(&flat, 0, flat.len()).is_empty());
    }

    /// One CATStorageProperty storage block named `name` (the
    /// `tests/fixtures_gen.py::storage_property_block` layout).
    fn storage_block(name: &str) -> Vec<u8> {
        let mut block = Vec::new();
        block.extend_from_slice(b"\x34\x12CATStorageProperty");
        block.extend_from_slice(b"\x80\x01\x00\x00\x00\x00\x22\x0c\x00\x00\x00");
        block.extend_from_slice(b"\x34\x01\x01\x00\x34\x10CATUnicodeString");
        block.extend_from_slice(b"\xa0\x02\x00\x00\x00\x00\x34");
        block.push(name.len() as u8);
        block.extend_from_slice(name.as_bytes());
        block.push(0x9f);
        block.extend_from_slice(b"\xa0\x02\x00\x00\x00\x00\x34\x00\x9f");
        block.extend_from_slice(b"\x3b\x10");
        block.extend_from_slice(&[0u8; 16]);
        block.push(0x9f);
        block
    }

    #[test]
    fn raw_block_regions_drop_the_parametric_blocks_without_resizing_neighbours() {
        // #69: the parametric blocks are not part of the fallback's
        // scan set, but they still bound their neighbours — the region
        // before a CATPrtCont block ends at its start.
        let mut data = storage_block("CGMGeom");
        data.extend_from_slice(&[0u8; 16]);
        let part_tree = data.len();
        data.extend_from_slice(&storage_block("CATPrtCont"));
        data.extend_from_slice(&[0u8; 16]);
        let body = data.len();
        data.extend_from_slice(&storage_block("CATSeeBodyCont"));
        data.extend_from_slice(&[0u8; 16]);
        assert_eq!(
            raw_block_regions(&data),
            vec![(0, part_tree), (body, data.len())]
        );
    }

    /// The writer's length-framed name: ``len = strlen + 1`` then the
    /// ASCII bytes (the twin's ``tests.test_no_surface_fallback.framed``).
    fn framed(name: &str) -> Vec<u8> {
        let mut out = vec![name.len() as u8 + 1];
        out.extend_from_slice(name.as_bytes());
        out
    }

    #[test]
    fn the_feature_tree_scans_the_length_framed_names() {
        let mut data = Vec::new();
        data.push(0x00);
        data.extend_from_slice(&framed("Sketch"));
        data.extend_from_slice(&[0x80, 0x40]);
        data.extend_from_slice(&framed("Pad1"));
        data.extend_from_slice(&framed("Sketch.1"));
        data.extend_from_slice(&framed("EdgeFillet"));
        data.extend_from_slice(&[0x00, 0x00]);
        let tree = scan_feature_tree(&data);
        assert_eq!(tree.containers, 0);
        assert_eq!(tree.feature_names, 4);
        assert_eq!(
            tree.features
                .iter()
                .map(|(typ, count, _off)| (typ.as_str(), *count))
                .collect::<Vec<_>>(),
            vec![("Sketch", 2), ("Pad", 1), ("EdgeFillet", 1)]
        );
        assert_eq!(tree.features[0].2, 2); // the name offset after its length byte
        assert!(tree.has_tree());
    }

    #[test]
    fn the_feature_tree_rejects_wrong_framing_and_unknown_types() {
        // the length byte must equal strlen + 1; a full name outside
        // the vocabulary is rejected; the parameter-type family is not
        // in the shipped vocabulary
        let mut data = Vec::new();
        data.extend_from_slice(b"\x05Sketch");
        data.extend_from_slice(b"\x0ePointVisuAttr");
        data.extend_from_slice(b"\x07Volume");
        data.push(0x00);
        let tree = scan_feature_tree(&data);
        assert_eq!(tree.feature_names, 0);
        assert!(tree.features.is_empty());
        assert!(!tree.has_tree());
    }

    #[test]
    fn the_feature_tree_counts_the_container_token() {
        let mut data = b"CATPrtCont\x80".to_vec();
        data.push(0x00);
        data.extend_from_slice(&framed("Pad"));
        data.extend_from_slice(b"\x9fCATPrtCont");
        let tree = scan_feature_tree(&data);
        assert_eq!(tree.containers, 2);
        assert_eq!(tree.feature_names, 1);
        assert!(tree.has_tree());
    }
}
