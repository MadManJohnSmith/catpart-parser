//! Exact ``a5 03 34`` B-spline surfaces: decode, evaluate, tessellate —
//! the port of the Python reference module ``catpart.geometry.surface``
//! (``src/catpart/geometry/surface.py``), per spec §2.1 of
//! ``docs/specs/phase5-viewer-spec.md``.
//!
//! This is the shipped half of ``docs/evidence/2026-11-19-surface-head.md``
//! (the payload grammar) joined to
//! ``docs/evidence/2026-11-19-surface-tessellation.md`` (the mesh).
//!
//! The record is a self-delimiting degree-5, C2, non-rational
//! tensor-product B-spline surface.  Each lane block names ``n``
//! distinct knots; the pole net that follows is exactly ``3*n_u`` by
//! ``3*n_v`` triples, and the only constant ``(degree, interior
//! multiplicity)`` pair that maps a lane of ``n`` knots to ``3*n`` poles
//! is ``(5, 3)``.  The knot vector is therefore
//! ``[u0]*6 + interior*3 + [un]*6`` (length ``3n + 6``), and the grid
//! begins exactly after the head (``30 + 8*(n_u + n_v)`` bytes).
//!
//! The tessellator subdivides each knot span by a bounded adaptive
//! tensor grid: cells whose centre departs from the bilinear cell by
//! more than ``1e-3`` of the pole-net bounding-box diagonal refine that
//! span, up to a fixed per-span and total sample budget.  A tensor grid
//! has no T-junctions, so every patch is a manifold sheet with boundary
//! by construction.  Patches are concatenated into one mesh with
//! disjoint index spaces — no topology join is attempted between
//! records.
//!
//! The evaluable battery is the probe's measured one: exact corner
//! poles, finite samples on a 21x21 lattice, containment in the pole
//! hull, no normal fold, model scale and a chord-length-coherent knot
//! span.  The compact grammar (2026-11-21) stores its own degrees and
//! multiplicities and is the one branch where the chord-length band does
//! not apply: its parameterisation is not chord-length.
//!
//! Numeric contract (spec §2.2): decode module — all arithmetic in f64,
//! verbatim expression shape and order with the Python twin (the
//! ``suboptimal_flops`` allow is the pinned carve-out; ``mul_add``
//! changes rounding and would break the byte-identical PLY).  See the
//! crate docs in ``../lib.rs`` for the full policy.
#![allow(clippy::suboptimal_flops)]

use super::mesh;
use super::store;

/// Marker that seeds the surface scan (A family, flag 0x03, class 0x34).
pub const SURFACE_MARKER: [u8; 3] = [0xa5, 0x03, 0x34];
/// Class byte of the consolidated freeform surface record.
pub const SURFACE_CLASS: u8 = 0x34;
/// The two decoded payload subtypes: the two-lane surface and the patch.
pub const SUBTYPE_TWO_LANE: u8 = 0;
pub const SUBTYPE_PATCH: u8 = 4;
/// Grammar discriminator of the compact head.  It is not a stored byte: this
/// grammar has no subtype field, and is recognised by its own lane tokens.
pub const SUBTYPE_COMPACT: u8 = 2;
/// Compact lane markers: implicit clamped multiplicities, explicit vector.
pub const COMPACT_KNOTS_IMPLICIT: u8 = 0x0C;
pub const COMPACT_KNOTS_EXPLICIT: u8 = 0x04;
/// Bytes that open the compact pole net (measured 0x01 and 0x05).
pub const COMPACT_POLE_MARKERS: [u8; 2] = [0x01, 0x05];
/// Compact lane limits (measured degrees 1..5, knot counts 2..16).
pub const MAX_COMPACT_DEGREE: usize = 15;
pub const MAX_COMPACT_KNOTS: usize = 64;
/// Record tag at the head of each lane block.
pub const HEAD_TAG: u32 = 5;
/// Second-lane tag byte after the u lane.
pub const LANE_TAG: u8 = 1;
/// Closing bytes after the v lane (two-lane) and the measured middle flag.
pub const CLOSING: [u8; 3] = [0x01, 0x00, 0x00];
pub const CLOSING_RATIONAL: u8 = 0x01;
/// A lane length is a distinct-knot count: small, and never zero.
pub const MIN_LANE: u32 = 2;
pub const MAX_LANE: u32 = 256;
/// The two measured surface payload tails (the bulk probe's closure law).
pub const SURFACE_TAILS: [usize; 2] = [152, 154];

/// Degree and interior multiplicity of the two-lane grammar (both
/// directions) and of the patch grammar's u direction.
pub const DEGREE: usize = 5;
pub const MULTIPLICITY: usize = 3;
/// Largest v degree a patch head may declare (corpus range: 1..5).
pub const MAX_PATCH_DEGREE: u32 = 16;

/// The E5 bulk dialect's exact-surface record class (the ``e5 0d`` stream's
/// ``class:u16le`` value; docs/evidence/2026-11-22-e5-class-table.md).
pub const E5_SURFACE_CLASS: u16 = 0x00E7;
/// Payload tag that opens an E5 surface record: one u32 header per lane.
pub const E5_SURFACE_TAG: u8 = 0x80;
/// The two measured pole-net markers: non-rational, and coordinates then
/// weights (rational; the marker law is ``tail - 8 * poles == 148`` on the
/// rational population and ``tail == 148`` on the plain one).
pub const E5_POLE_MARKER_PLAIN: [u8; 2] = [0x00, 0x00];
pub const E5_POLE_MARKER_RATIONAL: [u8; 2] = [0x01, 0x00];
/// Measured E5 lane limits (degrees 1..15, knot counts 2..256).
pub const E5_MAX_DEGREE: usize = 15;
pub const E5_MAX_KNOTS: usize = 256;

/// Plausible model coordinate upper band (mm): the bulk probe's net band.
/// There is no lower floor — a pole may legitimately sit at 0 or 1e-16.
pub const NET_CEIL: f64 = 1e6;
/// A coordinate outside a 100 m envelope is not a two-lane part coordinate.
/// A patch is admitted to a 1 km envelope: the merged-allocation frames sit
/// at ~993 m and are still refused by the chord-length and fold checks,
/// while a coherent 211 m patch is real.
pub const MODEL_SCALE_TWO_LANE: f64 = 1e5;
pub const MODEL_SCALE_PATCH: f64 = 1e6;
/// ``u knot span / pole-polygon arc length`` band for a chord-length lane.
pub const ARC_RATIO_BAND: (f64, f64) = (0.5, 2.0);
/// Parameter-lattice steps used by the evaluable battery.
pub const NORMAL_STEPS: usize = 20;
/// Corner-pole residual bound, relative to the pole-net diagonal.
pub const CORNER_TOL: f64 = 1e-9;

/// Maximum chord error as a fraction of the pole-net bbox diagonal.
pub const TOLERANCE_FRACTION: f64 = 1e-3;
/// Cells per span before the first refinement round.
pub const INITIAL_STEPS: usize = 2;
/// Hard per-span subdivision cap.
pub const MAX_STEPS: usize = 16;
/// Refinement rounds before the budget stops the loop.
pub const MAX_ROUNDS: usize = 8;
/// Total parameter samples per patch (vertices, not triangles).
pub const MAX_GRID_POINTS: usize = 65_536;
/// A triangle whose area is below this fraction of diagonal^2 is degenerate.
pub const DEGENERATE_AREA_FRACTION: f64 = 1e-12;

/// One sampled tensor grid: ``(u samples, v samples, points)``.
type Grid = (Vec<f64>, Vec<f64>, Vec<Vec<(f64, f64, f64)>>);
/// The decoded pole matrix (rows in u, columns in v).
type PoleMatrix = Vec<Vec<(f64, f64, f64)>>;
/// The parallel rational-weight matrix.
type WeightMatrix = Vec<Vec<f64>>;
/// One decoded compact lane: ``(degree, knot_count, knots, mult, next)``.
type CompactLane = (usize, usize, Vec<f64>, Vec<usize>, usize);

/// The decoded head of one surface payload; ``grid`` is predicted.
///
/// ``degree_v`` is the patch grammar's stored v degree and 5 for the
/// two-lane grammar; ``rational`` selects the 32-byte coordinate-then-
/// weights layout.  The two stored grammars are clamped with interior
/// multiplicity 3, so ``poles = (degree + 1) + 3*(n - 2)`` per direction.
/// The compact grammar stores its multiplicities: ``mult_u``/``mult_v``
/// are then non-empty and ``poles = sum(mult) - degree - 1``.
#[derive(Debug, Clone, PartialEq)]
pub struct SurfaceHead {
    pub start: usize,
    pub end: usize,
    pub n_u: usize,
    pub n_v: usize,
    pub knots_u: Vec<f64>,
    pub knots_v: Vec<f64>,
    pub mode_u: u32,
    pub mode_v: u32,
    pub grid: usize,
    pub subtype: u8,
    pub degree_u: usize,
    pub degree_v: usize,
    pub rational: bool,
    pub mult_u: Vec<usize>,
    pub mult_v: Vec<usize>,
}

impl SurfaceHead {
    pub fn head_bytes(&self) -> usize {
        self.grid - self.start
    }
    pub fn poles_u(&self) -> usize {
        if self.subtype == SUBTYPE_COMPACT {
            self.mult_u.iter().sum::<usize>() - self.degree_u - 1
        } else {
            (self.degree_u + 1) + MULTIPLICITY * (self.n_u - 2)
        }
    }
    pub fn poles_v(&self) -> usize {
        if self.subtype == SUBTYPE_COMPACT {
            self.mult_v.iter().sum::<usize>() - self.degree_v - 1
        } else {
            (self.degree_v + 1) + MULTIPLICITY * (self.n_v - 2)
        }
    }
    pub fn points(&self) -> usize {
        self.poles_u() * self.poles_v()
    }
    pub fn bytes_per_pole(&self) -> usize {
        if self.rational { 32 } else { 24 }
    }
    pub fn net_bytes(&self) -> usize {
        self.bytes_per_pole() * self.points()
    }
    pub fn tail(&self) -> usize {
        self.end - (self.grid + self.net_bytes())
    }
    pub fn scale_limit(&self) -> f64 {
        if self.subtype == SUBTYPE_TWO_LANE {
            MODEL_SCALE_TWO_LANE
        } else {
            MODEL_SCALE_PATCH
        }
    }
    pub fn knots(&self) -> (Vec<f64>, Vec<f64>) {
        if self.subtype == SUBTYPE_COMPACT {
            (
                compact_knot_vector(&self.knots_u, &self.mult_u),
                compact_knot_vector(&self.knots_v, &self.mult_v),
            )
        } else {
            (
                knot_vector(&self.knots_u, self.degree_u),
                knot_vector(&self.knots_v, self.degree_v),
            )
        }
    }
}

/// The evaluable battery's measurements for one decoded surface.
///
/// ``arc_applicable`` is false only on the compact grammar, whose knots are
/// not chord-length: there the corner residual, hull, folds, finiteness and
/// scale remain the grid-integrity gates and the band is not a coherency law.
#[derive(Debug, Clone, PartialEq)]
pub struct SurfaceAssessment {
    pub corner_residual: f64,
    pub finite: bool,
    pub hull_violations: usize,
    pub folds: usize,
    pub arc_ratio: f64,
    pub bbox: [f64; 6],
    pub scale_ok: bool,
    pub arc_applicable: bool,
}

impl SurfaceAssessment {
    pub fn plausible_scale(&self) -> bool {
        self.scale_ok
    }
    pub fn arc_coherent(&self) -> bool {
        self.arc_ratio >= ARC_RATIO_BAND.0 && self.arc_ratio <= ARC_RATIO_BAND.1
    }
    pub fn arc_ok(&self) -> bool {
        self.arc_coherent() || !self.arc_applicable
    }
    pub fn evaluable(&self) -> bool {
        self.corner_residual <= CORNER_TOL
            && self.finite
            && self.hull_violations == 0
            && self.folds == 0
            && self.plausible_scale()
            && self.arc_ok()
    }
}

/// One surface's triangle sheet (indices are patch-local).
#[derive(Debug, Clone, PartialEq)]
pub struct TessellatedPatch {
    pub vertices: Vec<(f64, f64, f64)>,
    pub triangles: Vec<(u32, u32, u32)>,
    pub degenerate: usize,
    pub tolerance: f64,
    pub grid_points: usize,
    pub manifold: bool,
    pub oriented: bool,
}

/// One part's surface census plus the merged tessellation.
#[derive(Debug, Clone, PartialEq)]
pub struct SurfaceScan {
    pub block: Option<usize>,
    pub candidates: usize,
    pub decoded: usize,
    pub evaluable: usize,
    pub tessellated: usize,
    pub refused: usize,
    pub manifold_patches: usize,
    pub vertices: Vec<(f64, f64, f64)>,
    pub triangles: Vec<(u32, u32, u32)>,
    pub degenerate: usize,
    pub tolerances: Vec<f64>,
    pub points: usize,
    /// The E5 dialect's own census (class ``0x00e7`` records).  They fold
    /// into the totals and the mesh only when at least one E5 surface
    /// tessellated; with nothing tessellated every pre-E5 output is
    /// unchanged (the no-regret law).
    pub e5_candidates: usize,
    pub e5_decoded: usize,
    pub e5_evaluable: usize,
    pub e5_tessellated: usize,
    pub e5_refused: usize,
}

impl SurfaceScan {
    pub fn has_mesh(&self) -> bool {
        !self.triangles.is_empty()
    }
}

fn u32_le(data: &[u8], off: usize) -> Option<u32> {
    let bytes = data.get(off..off + 4)?;
    Some(u32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]))
}

fn f64_le(data: &[u8], off: usize) -> Option<f64> {
    let bytes = data.get(off..off + 8)?;
    Some(f64::from_le_bytes([
        bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5], bytes[6], bytes[7],
    ]))
}

fn strictly_increasing(values: &[f64]) -> bool {
    values.windows(2).all(|pair| pair[0] < pair[1])
}

/// ``(payload, end, class)`` of an A-family frame at ``pos``.
fn parse_frame(data: &[u8], pos: usize, hi: usize) -> Option<(usize, usize, u8)> {
    if pos + 8 > hi {
        return None;
    }
    let family = data[pos];
    if !(0xa5..=0xa8).contains(&family) {
        return None;
    }
    if !matches!(data[pos + 1], 0x03 | 0x13 | 0x83) {
        return None;
    }
    let width = (family - 0xa4) as usize;
    let payload = pos + 7 + width;
    let length = u32_le(data, pos + 3)? as usize;
    let end = payload.checked_add(length)?;
    if payload > hi || end > hi {
        return None;
    }
    Some((payload, end, data[pos + 2]))
}

/// The first ``CATPrtCont`` block's ``(start, region_end)``.
fn surface_block(data: &[u8]) -> Option<(usize, usize)> {
    let blocks = store::valid_blocks(data);
    let outer = if data.len() >= 12 {
        u32::from_be_bytes([data[8], data[9], data[10], data[11]]) as usize
    } else {
        0
    };
    for (blk, name) in &blocks {
        if name == "CATPrtCont" {
            return Some((*blk, store::probe_region(*blk, &blocks, outer, data.len())));
        }
    }
    None
}

/// Every marker-class ``a5 03 34`` frame ``(start, payload, end)``.
pub fn candidate_frames(data: &[u8]) -> Vec<(usize, usize, usize)> {
    let Some((lo, hi)) = surface_block(data) else {
        return Vec::new();
    };
    let mut out = Vec::new();
    let mut pos = lo;
    while pos + SURFACE_MARKER.len() <= hi {
        let Some(offset) = data[pos..hi]
            .windows(SURFACE_MARKER.len())
            .position(|window| window == SURFACE_MARKER)
        else {
            break;
        };
        let hit = pos + offset;
        pos = hit + 1;
        if hit + 8 > hi {
            break;
        }
        let Some((payload, end, class)) = parse_frame(data, hit, hi) else {
            continue;
        };
        if class != SURFACE_CLASS {
            continue;
        }
        out.push((hit, payload, end));
    }
    out
}

/// One compact lane block: ``(degree, n, knots, mult, next)``.
///
/// The first two bytes are ``(degree << 2) | 1`` and ``(knot_count << 2) | 1``;
/// the third is the lane marker: ``0x0c`` for implicit clamped multiplicities,
/// ``0x04`` for an explicit vector of ``(mult << 2) | 1`` bytes after the knots.
fn parse_compact_lane(data: &[u8], pos: usize, end: usize) -> Option<CompactLane> {
    if pos + 3 > end {
        return None;
    }
    let token_degree = *data.get(pos)?;
    let token_count = *data.get(pos + 1)?;
    let marker = *data.get(pos + 2)?;
    if !matches!(marker, COMPACT_KNOTS_IMPLICIT | COMPACT_KNOTS_EXPLICIT) {
        return None;
    }
    if token_degree & 3 != 1 || token_count & 3 != 1 {
        return None;
    }
    let degree = (token_degree >> 2) as usize;
    let n = (token_count >> 2) as usize;
    if !(1..=MAX_COMPACT_DEGREE).contains(&degree) {
        return None;
    }
    if !(MIN_LANE as usize..=MAX_COMPACT_KNOTS).contains(&n) {
        return None;
    }
    let lane = pos + 3;
    if lane + 8 * n > end {
        return None;
    }
    let knots: Vec<f64> = (0..n)
        .map(|i| f64_le(data, lane + 8 * i))
        .collect::<Option<_>>()?;
    if !strictly_increasing(&knots) {
        return None;
    }
    let mut nxt = lane + 8 * n;
    let mult: Vec<usize> = if marker == COMPACT_KNOTS_EXPLICIT {
        if nxt + n > end {
            return None;
        }
        let tokens = data.get(nxt..nxt + n)?;
        if tokens.iter().any(|token| token & 3 != 1) {
            return None;
        }
        let mult: Vec<usize> = tokens.iter().map(|&token| (token >> 2) as usize).collect();
        if mult.iter().any(|&count| count < 1) {
            return None;
        }
        nxt += n;
        mult
    } else {
        let mut mult = vec![1usize; n];
        mult[0] = degree + 1;
        mult[n - 1] = degree + 1;
        mult
    };
    if mult.iter().sum::<usize>() < degree + 3 {
        return None;
    }
    Some((degree, n, knots, mult, nxt))
}

/// Decode the compact head (``docs/evidence/2026-11-21-surface-compact-head.md``).
///
/// The grammar has no subtype field: two lane blocks carry their own degree,
/// knot count and multiplicities, then ``0x01``/``0x05`` opens the
/// ``poles_u x poles_v`` net.  ``poles = sum(mult) - degree - 1`` per
/// direction.  The tail is not a closure law here (141..3597 B measured), so
/// the net length is the only closure check.
pub fn parse_compact_head(data: &[u8], payload: usize, end: usize) -> Option<SurfaceHead> {
    if payload + 6 > end || end > data.len() {
        return None;
    }
    let (degree_u, n_u, knots_u, mult_u, pos) = parse_compact_lane(data, payload, end)?;
    let (degree_v, n_v, knots_v, mult_v, pos) = parse_compact_lane(data, pos, end)?;
    if pos + 1 > end {
        return None;
    }
    if !COMPACT_POLE_MARKERS.contains(data.get(pos)?) {
        return None;
    }
    let grid = pos + 1;
    let head = SurfaceHead {
        start: payload,
        end,
        n_u,
        n_v,
        knots_u,
        knots_v,
        mode_u: 0,
        mode_v: 0,
        grid,
        subtype: SUBTYPE_COMPACT,
        degree_u,
        degree_v,
        rational: false,
        mult_u,
        mult_v,
    };
    if head.poles_u() < 2 || head.poles_v() < 2 {
        return None;
    }
    if grid + head.net_bytes() > end {
        return None;
    }
    Some(head)
}

/// Decode the E5 dialect's exact-surface record (class ``0x00e7``).
///
/// Measured layout (corpus rates in
/// ``docs/evidence/2026-11-22-e5-class-table.md``):
///
/// ```text
/// 0x80 | deg_v:u32 | a:u32 | b:u32 | n_v:u32 | q:u32
///      | knots_v f64[n_v]    strictly increasing
///      | mults_v u32[n_v]    each >= 1
///      | deg_u:u32 | a2:u32 | b2:u32 | n_u:u32 | q2:u32
///      | knots_u f64[n_u]    strictly increasing
///      | mults_u u32[n_u]    each >= 1
///      | 00 00 | 01 00       pole marker: plain / rational
///      | pole net            v-major outer (see e5_pole_data)
///      | tail                148 B law (not a closure gate)
/// ```
///
/// ``poles = sum(mult) - degree - 1`` per direction — the compact head's
/// pole law with u32 fields instead of byte tokens.  The ``a``/``b``/``q``
/// slots are a measured vocabulary (reported by the probe, not interpreted),
/// so they do not gate the decode; the knot monotonicity, the multiplicity
/// law and the net-fit closure are the validators.  The tail is not a
/// closure law here either (148 B on 97 % of the population, 142..152 on
/// the rest): the grid is predicted by the head and validated by the net,
/// never by a tail size.
pub fn parse_e5_surface(data: &[u8], payload: usize, end: usize) -> Option<SurfaceHead> {
    if payload + 21 > end || end > data.len() || data[payload] != E5_SURFACE_TAG {
        return None;
    }
    let u32_at = |off: usize| -> u32 { u32_le(data, off).unwrap_or(u32::MAX) };
    let deg_v = u32_at(payload + 1) as usize;
    let n_v = u32_at(payload + 13) as usize;
    if !(1..=E5_MAX_DEGREE).contains(&deg_v) {
        return None;
    }
    if !(MIN_LANE as usize..=E5_MAX_KNOTS).contains(&n_v) {
        return None;
    }
    let mut pos = payload + 21;
    if pos + 12 * n_v > end {
        return None;
    }
    let mut knots_v = Vec::with_capacity(n_v);
    for i in 0..n_v {
        knots_v.push(f64_le(data, pos + 8 * i)?);
    }
    if !strictly_increasing(&knots_v) {
        return None;
    }
    pos += 8 * n_v;
    let mut mult_v = Vec::with_capacity(n_v);
    for i in 0..n_v {
        let m = u32_at(pos + 4 * i) as usize;
        if m < 1 {
            return None;
        }
        mult_v.push(m);
    }
    pos += 4 * n_v;
    if pos + 20 > end {
        return None;
    }
    let deg_u = u32_at(pos) as usize;
    let n_u = u32_at(pos + 12) as usize;
    pos += 20;
    if !(1..=E5_MAX_DEGREE).contains(&deg_u) {
        return None;
    }
    if !(MIN_LANE as usize..=E5_MAX_KNOTS).contains(&n_u) {
        return None;
    }
    if pos + 12 * n_u > end {
        return None;
    }
    let mut knots_u = Vec::with_capacity(n_u);
    for i in 0..n_u {
        knots_u.push(f64_le(data, pos + 8 * i)?);
    }
    if !strictly_increasing(&knots_u) {
        return None;
    }
    pos += 8 * n_u;
    let mut mult_u = Vec::with_capacity(n_u);
    for i in 0..n_u {
        let m = u32_at(pos + 4 * i) as usize;
        if m < 1 {
            return None;
        }
        mult_u.push(m);
    }
    pos += 4 * n_u;
    if pos + 2 > end {
        return None;
    }
    let marker = [data[pos], data[pos + 1]];
    let rational = marker == E5_POLE_MARKER_RATIONAL;
    if marker != E5_POLE_MARKER_PLAIN && !rational {
        return None;
    }
    let grid = pos + 2;
    let head = SurfaceHead {
        start: payload,
        end,
        n_u,
        n_v,
        knots_u,
        knots_v,
        mode_u: 0,
        mode_v: 0,
        grid,
        subtype: SUBTYPE_COMPACT,
        degree_u: deg_u,
        degree_v: deg_v,
        rational,
        mult_u,
        mult_v,
    };
    if head.poles_u() < 2 || head.poles_v() < 2 {
        return None;
    }
    if grid + head.net_bytes() > end {
        return None;
    }
    Some(head)
}

/// Decode one payload head; ``None`` when its arithmetic does not close.
///
/// The compact grammar has no subtype field and is tried first, positively,
/// on its own lane tokens; the two stored grammars are then selected by the
/// byte at ``+8``.  Both of those close on a measured tail and predict the
/// grid rather than searching for it.
pub fn parse_surface_head(data: &[u8], payload: usize, end: usize) -> Option<SurfaceHead> {
    if let Some(head) = parse_compact_head(data, payload, end) {
        return Some(head);
    }
    if end > data.len() || payload + 9 > end {
        return None;
    }
    let subtype = data[payload + 8];
    if subtype == SUBTYPE_PATCH {
        return parse_patch_head(data, payload, end);
    }
    if subtype != SUBTYPE_TWO_LANE {
        return None;
    }
    if payload + 13 > end {
        return None;
    }
    if u32_le(data, payload)? != HEAD_TAG {
        return None;
    }
    let n_u = u32_le(data, payload + 4)?;
    if !(MIN_LANE..=MAX_LANE).contains(&n_u) {
        return None;
    }
    let mode_u = u32_le(data, payload + 9)?;
    let lane_u = payload + 13;
    if lane_u + 8 * n_u as usize + 14 > end {
        return None;
    }
    let knots_u: Vec<f64> = (0..n_u as usize)
        .map(|i| f64_le(data, lane_u + 8 * i))
        .collect::<Option<_>>()?;
    if !strictly_increasing(&knots_u) {
        return None;
    }
    let second = lane_u + 8 * n_u as usize;
    if data[second] != LANE_TAG {
        return None;
    }
    if u32_le(data, second + 1)? != HEAD_TAG {
        return None;
    }
    let n_v = u32_le(data, second + 5)?;
    if !(MIN_LANE..=MAX_LANE).contains(&n_v) {
        return None;
    }
    if data[second + 9] != 0 {
        return None;
    }
    let mode_v = u32_le(data, second + 10)?;
    let lane_v = second + 14;
    if lane_v + 8 * n_v as usize + CLOSING.len() > end {
        return None;
    }
    let knots_v: Vec<f64> = (0..n_v as usize)
        .map(|i| f64_le(data, lane_v + 8 * i))
        .collect::<Option<_>>()?;
    if !strictly_increasing(&knots_v) {
        return None;
    }
    let close = lane_v + 8 * n_v as usize;
    if data.get(close..close + CLOSING.len())? != CLOSING {
        return None;
    }
    let head = SurfaceHead {
        start: payload,
        end,
        n_u: n_u as usize,
        n_v: n_v as usize,
        knots_u,
        knots_v,
        mode_u,
        mode_v,
        grid: close + CLOSING.len(),
        subtype: SUBTYPE_TWO_LANE,
        degree_u: DEGREE,
        degree_v: DEGREE,
        rational: false,
        mult_u: Vec::new(),
        mult_v: Vec::new(),
    };
    if !SURFACE_TAILS.contains(&head.tail()) {
        return None;
    }
    Some(head)
}

/// Decode the subtype-4 patch head (``docs/evidence/2026-11-19-join-order-probe.md``).
///
/// The u lane carries no mode field; the second lane stores the v direction's
/// own degree; a closing middle byte selects the 32-byte rational layout.
/// The u direction stays degree 5 / multiplicity 3, so ``poles_u = 3*n_u``
/// and ``poles_v = (degree_v + 1) + 3*(n_v - 2)``.
pub fn parse_patch_head(data: &[u8], payload: usize, end: usize) -> Option<SurfaceHead> {
    if payload + 22 > end {
        return None;
    }
    if u32_le(data, payload)? != HEAD_TAG {
        return None;
    }
    let n_u = u32_le(data, payload + 4)?;
    if !(MIN_LANE..=MAX_LANE).contains(&n_u) {
        return None;
    }
    let lane_u = payload + 9;
    if lane_u + 8 * n_u as usize + 14 > end {
        return None;
    }
    let knots_u: Vec<f64> = (0..n_u as usize)
        .map(|i| f64_le(data, lane_u + 8 * i))
        .collect::<Option<_>>()?;
    if !strictly_increasing(&knots_u) {
        return None;
    }
    let second = lane_u + 8 * n_u as usize;
    if data[second] != LANE_TAG {
        return None;
    }
    let degree_v = u32_le(data, second + 1)?;
    if !(1..=MAX_PATCH_DEGREE).contains(&degree_v) {
        return None;
    }
    let n_v = u32_le(data, second + 5)?;
    if !(MIN_LANE..=MAX_LANE).contains(&n_v) {
        return None;
    }
    if data[second + 9] != SUBTYPE_PATCH {
        return None;
    }
    let lane_v = second + 10;
    if lane_v + 8 * n_v as usize + CLOSING.len() > end {
        return None;
    }
    let knots_v: Vec<f64> = (0..n_v as usize)
        .map(|i| f64_le(data, lane_v + 8 * i))
        .collect::<Option<_>>()?;
    if !strictly_increasing(&knots_v) {
        return None;
    }
    let close = lane_v + 8 * n_v as usize;
    let closing = data.get(close..close + CLOSING.len())?;
    if closing[0] != 0x01 || closing[2] != 0x00 || !matches!(closing[1], 0x00 | 0x01) {
        return None;
    }
    let head = SurfaceHead {
        start: payload,
        end,
        n_u: n_u as usize,
        n_v: n_v as usize,
        knots_u,
        knots_v,
        mode_u: 0,
        mode_v: degree_v,
        grid: close + CLOSING.len(),
        subtype: SUBTYPE_PATCH,
        degree_u: DEGREE,
        degree_v: degree_v as usize,
        rational: closing[1] == CLOSING_RATIONAL,
        mult_u: Vec::new(),
        mult_v: Vec::new(),
    };
    if head.poles_u() < 2 || head.poles_v() < 2 {
        return None;
    }
    if !SURFACE_TAILS.contains(&head.tail()) {
        return None;
    }
    Some(head)
}

/// The full knot vector of a compact lane: each value repeated ``mult`` times.
pub fn compact_knot_vector(distinct: &[f64], multiplicities: &[usize]) -> Vec<f64> {
    assert!(
        distinct.len() == multiplicities.len(),
        "a compact lane needs one multiplicity per knot"
    );
    let mut out = Vec::new();
    for (value, count) in distinct.iter().zip(multiplicities) {
        out.extend(std::iter::repeat_n(*value, *count));
    }
    out
}

/// Clamped degree-``degree`` knots with multiplicity-3 interior values.
pub fn knot_vector(distinct: &[f64], degree: usize) -> Vec<f64> {
    assert!(
        distinct.len() >= 2,
        "a knot lane needs at least two distinct values"
    );
    let mut out = vec![distinct[0]; degree + 1];
    for value in &distinct[1..distinct.len() - 1] {
        out.extend(std::iter::repeat_n(*value, MULTIPLICITY));
    }
    out.extend(std::iter::repeat_n(
        distinct[distinct.len() - 1],
        degree + 1,
    ));
    out
}

/// All ``count`` degree-``degree`` basis values at ``t`` (Cox-de Boor).
pub fn basis_values(t: f64, knots: &[f64], degree: usize, count: usize) -> Vec<f64> {
    let width = count + degree;
    let mut current = vec![0.0; width];
    let limit = std::cmp::min(knots.len() - 1, width);
    let mut found = false;
    for i in 0..limit {
        if knots[i] <= t && t < knots[i + 1] {
            current[i] = 1.0;
            found = true;
            break;
        }
    }
    if !found {
        for i in (0..limit).rev() {
            if knots[i] < knots[i + 1] {
                current[i] = 1.0;
                break;
            }
        }
    }
    for p in 1..=degree {
        let mut next = vec![0.0; width];
        for i in 0..(width - p) {
            let mut left = 0.0;
            let den = knots[i + p] - knots[i];
            if den > 0.0 {
                left = (t - knots[i]) / den * current[i];
            }
            let mut right = 0.0;
            let den = knots[i + p + 1] - knots[i + 1];
            if den > 0.0 {
                right = (knots[i + p + 1] - t) / den * current[i + 1];
            }
            next[i] = left + right;
        }
        current = next;
    }
    current.truncate(count);
    current
}

/// Evaluate the tensor-product surface at ``(u, v)``.
///
/// ``weights`` is ``None`` for a non-rational patch and a parallel matrix for
/// a rational one; the rational sum is divided by the total weight, which is
/// what makes the corner poles reproduce exactly either way.  The eight
/// arguments are the two knot vectors, the two degrees and the weights on
/// top of the parameter pair: a decode-time tuple would only move them.
#[allow(clippy::too_many_arguments)]
pub fn evaluate(
    poles: &[Vec<(f64, f64, f64)>],
    knots_u: &[f64],
    knots_v: &[f64],
    u: f64,
    v: f64,
    degree_u: usize,
    degree_v: usize,
    weights: Option<&[Vec<f64>]>,
) -> (f64, f64, f64) {
    let nu = poles.len();
    let nv = poles[0].len();
    let bu = basis_values(u, knots_u, degree_u, nu);
    let bv = basis_values(v, knots_v, degree_v, nv);
    let Some(weights) = weights else {
        let mut out = [0.0, 0.0, 0.0];
        for (i, &wi) in bu.iter().enumerate() {
            if wi == 0.0 {
                continue;
            }
            let row = &poles[i];
            for (j, &wj) in bv.iter().enumerate() {
                let weight = wi * wj;
                if weight == 0.0 {
                    continue;
                }
                let point = row[j];
                out[0] += weight * point.0;
                out[1] += weight * point.1;
                out[2] += weight * point.2;
            }
        }
        return (out[0], out[1], out[2]);
    };
    let mut out = [0.0, 0.0, 0.0];
    let mut total = 0.0;
    for (i, &wi) in bu.iter().enumerate() {
        if wi == 0.0 {
            continue;
        }
        let row = &poles[i];
        let wrow = &weights[i];
        for (j, &wj) in bv.iter().enumerate() {
            let weight = wi * wj;
            if weight == 0.0 {
                continue;
            }
            let value = weight * wrow[j];
            let point = row[j];
            out[0] += value * point.0;
            out[1] += value * point.1;
            out[2] += value * point.2;
            total += value;
        }
    }
    if total == 0.0 {
        return (f64::NAN, f64::NAN, f64::NAN);
    }
    (out[0] / total, out[1] / total, out[2] / total)
}

/// The pole matrix and (for rational heads) its parallel weight matrix.
pub fn pole_data(data: &[u8], head: &SurfaceHead) -> (PoleMatrix, Option<WeightMatrix>) {
    let nv = head.poles_v();
    let poles: PoleMatrix = (0..head.poles_u())
        .map(|i| {
            (0..nv)
                .map(|j| {
                    let off = head.grid + 24 * (i * nv + j);
                    (
                        f64_le(data, off).unwrap_or(f64::NAN),
                        f64_le(data, off + 8).unwrap_or(f64::NAN),
                        f64_le(data, off + 16).unwrap_or(f64::NAN),
                    )
                })
                .collect()
        })
        .collect();
    if !head.rational {
        return (poles, None);
    }
    let base = head.grid + 24 * head.points();
    let weights: WeightMatrix = (0..head.poles_u())
        .map(|i| {
            (0..nv)
                .map(|j| f64_le(data, base + 8 * (i * nv + j)).unwrap_or(f64::NAN))
                .collect()
        })
        .collect();
    (poles, Some(weights))
}

/// The ``poles_u x poles_v`` coordinate matrix the head predicts.
pub fn pole_net(data: &[u8], head: &SurfaceHead) -> Vec<Vec<(f64, f64, f64)>> {
    pole_data(data, head).0
}

/// The E5 pole matrix and (rational) its parallel weight matrix.
///
/// The E5 pole net is stored **v-major outer**: pole ``(i, j)`` sits at
/// ``grid + 24 * (j * poles_u + i)`` — consecutive ``poles_u`` triples are
/// the u-polygon at a fixed v, which is what makes the E5 census' row law
/// (rows ``= poles_v``) hold.  The orientation is corpus-pinned: on the
/// non-square nets 85 evaluate *only* under this reading and none *only*
/// under the u-major one.  A rational net appends the weights in the same
/// order after the coordinates (the marker ``01 00`` law).
pub fn e5_pole_data(data: &[u8], head: &SurfaceHead) -> (PoleMatrix, Option<WeightMatrix>) {
    let nu = head.poles_u();
    let nv = head.poles_v();
    let poles: PoleMatrix = (0..nu)
        .map(|i| {
            (0..nv)
                .map(|j| {
                    let off = head.grid + 24 * (j * nu + i);
                    (
                        f64_le(data, off).unwrap_or(f64::NAN),
                        f64_le(data, off + 8).unwrap_or(f64::NAN),
                        f64_le(data, off + 16).unwrap_or(f64::NAN),
                    )
                })
                .collect()
        })
        .collect();
    if !head.rational {
        return (poles, None);
    }
    let base = head.grid + 24 * head.points();
    let weights: WeightMatrix = (0..nu)
        .map(|i| {
            (0..nv)
                .map(|j| f64_le(data, base + 8 * (j * nu + i)).unwrap_or(f64::NAN))
                .collect()
        })
        .collect();
    (poles, Some(weights))
}

/// Every admitted E5 record of class ``0x00e7`` as ``(payload, end)``.
///
/// The record walk is the grid module's admitted-run law; the surface
/// class filter is the E5 class table's exact-surface family.
pub fn e5_surface_frames(data: &[u8]) -> Vec<(usize, usize)> {
    super::grid::e5_records(data)
        .into_iter()
        .filter(|&(_, _, cls)| cls == E5_SURFACE_CLASS)
        .map(|(payload, end, _)| (payload, end))
        .collect()
}

fn bbox(points: &[(f64, f64, f64)]) -> [f64; 6] {
    let mut box_ = [
        f64::INFINITY,
        f64::NEG_INFINITY,
        f64::INFINITY,
        f64::NEG_INFINITY,
        f64::INFINITY,
        f64::NEG_INFINITY,
    ];
    for &(x, y, z) in points {
        box_[0] = box_[0].min(x);
        box_[1] = box_[1].max(x);
        box_[2] = box_[2].min(y);
        box_[3] = box_[3].max(y);
        box_[4] = box_[4].min(z);
        box_[5] = box_[5].max(z);
    }
    box_
}

fn distance(a: (f64, f64, f64), b: (f64, f64, f64)) -> f64 {
    let dx = a.0 - b.0;
    let dy = a.1 - b.1;
    let dz = a.2 - b.2;
    (dx * dx + dy * dy + dz * dz).sqrt()
}

fn diagonal(box_: [f64; 6]) -> f64 {
    distance((box_[0], box_[2], box_[4]), (box_[1], box_[3], box_[5]))
}

fn pole_arc_polyline(poles: &[Vec<(f64, f64, f64)>], lo: usize, hi: usize) -> f64 {
    let nv = poles[0].len();
    let mut total = 0.0;
    for r in lo..hi {
        let mut row = 0.0;
        for (a, b) in poles[r].iter().zip(&poles[r + 1]) {
            row += distance(*a, *b);
        }
        total += row / nv as f64;
    }
    total
}

/// A finite model coordinate inside the bulk probe's 1 km band.
///
/// There is no lower floor: a pole legitimately sits at ``0`` or ``1e-16``
/// where the patch crosses its own coordinate plane.  The upper band is what
/// rejects a predicted grid landing on non-numeric bytes (the two-lane
/// note's four coincidences decode to ~1e307).
fn plausible(value: f64) -> bool {
    value.is_finite() && value.abs() <= NET_CEIL
}

/// Every pole is a finite model coordinate (the tail-closed gate).
pub fn plausible_net(poles: &[Vec<(f64, f64, f64)>]) -> bool {
    poles.iter().all(|row| {
        row.iter()
            .all(|p| plausible(p.0) && plausible(p.1) && plausible(p.2))
    })
}

/// A rational net's weights are finite and strictly positive.
pub fn plausible_weights(weights: Option<&[Vec<f64>]>) -> bool {
    weights.is_none_or(|rows| {
        rows.iter()
            .all(|row| row.iter().all(|v| v.is_finite() && *v > 0.0))
    })
}

/// Run the evaluable battery (the surface-head note's four checks).
pub fn assess(
    head: &SurfaceHead,
    poles: &[Vec<(f64, f64, f64)>],
    weights: Option<&[Vec<f64>]>,
) -> SurfaceAssessment {
    let (knots_u, knots_v) = head.knots();
    let u0 = head.knots_u[0];
    let u1 = head.knots_u[head.knots_u.len() - 1];
    let v0 = head.knots_v[0];
    let v1 = head.knots_v[head.knots_v.len() - 1];
    let steps = NORMAL_STEPS;
    let us: Vec<f64> = (0..=steps)
        .map(|a| u0 + (u1 - u0) * a as f64 / steps as f64)
        .collect();
    let vs: Vec<f64> = (0..=steps)
        .map(|b| v0 + (v1 - v0) * b as f64 / steps as f64)
        .collect();
    let grid: Vec<Vec<(f64, f64, f64)>> = us
        .iter()
        .map(|&u| {
            vs.iter()
                .map(|&v| {
                    evaluate(
                        poles,
                        &knots_u,
                        &knots_v,
                        u,
                        v,
                        head.degree_u,
                        head.degree_v,
                        weights,
                    )
                })
                .collect()
        })
        .collect();
    let flat: Vec<(f64, f64, f64)> = poles.iter().flatten().copied().collect();
    let box_ = bbox(&flat);
    let diag = diagonal(box_);
    let diagonal = if diag == 0.0 { 1.0 } else { diag };
    let last_row = poles.len() - 1;
    let last_col = poles[0].len() - 1;
    let corners = [
        distance(grid[0][0], poles[0][0]),
        distance(grid[steps][steps], poles[last_row][last_col]),
        distance(grid[0][steps], poles[0][last_col]),
        distance(grid[steps][0], poles[last_row][0]),
    ];
    let mut finite = true;
    for row in &grid {
        for point in row {
            if !(point.0.is_finite() && point.1.is_finite() && point.2.is_finite()) {
                finite = false;
            }
        }
    }
    let mut violations = 0;
    for row in &grid {
        for point in row {
            let point = [point.0, point.1, point.2];
            for k in 0..3 {
                if !(box_[2 * k] - 1e-6 <= point[k] && point[k] <= box_[2 * k + 1] + 1e-6) {
                    violations += 1;
                }
            }
        }
    }
    let mut normals: std::collections::HashMap<(usize, usize), (f64, f64, f64)> =
        std::collections::HashMap::new();
    for a in 0..steps {
        for b in 0..steps {
            let p00 = grid[a][b];
            let p01 = grid[a][b + 1];
            let p10 = grid[a + 1][b];
            let du = [p01.0 - p00.0, p01.1 - p00.1, p01.2 - p00.2];
            let dv = [p10.0 - p00.0, p10.1 - p00.1, p10.2 - p00.2];
            let normal = (
                du[1] * dv[2] - du[2] * dv[1],
                du[2] * dv[0] - du[0] * dv[2],
                du[0] * dv[1] - du[1] * dv[0],
            );
            let length = (normal.0 * normal.0 + normal.1 * normal.1 + normal.2 * normal.2).sqrt();
            if length > 0.0 {
                normals.insert(
                    (a, b),
                    (normal.0 / length, normal.1 / length, normal.2 / length),
                );
            }
        }
    }
    let mut folds = 0;
    for (&(a, b), normal) in &normals {
        for neighbour in [(a, b + 1), (a + 1, b)] {
            if let Some(other) = normals.get(&neighbour)
                && normal.0 * other.0 + normal.1 * other.1 + normal.2 * other.2 < 0.0
            {
                folds += 1;
            }
        }
    }
    let arc = pole_arc_polyline(poles, 0, poles.len() - 1);
    let arc_ratio = if arc > 0.0 { (u1 - u0) / arc } else { 0.0 };
    let scale_ok = box_.iter().all(|c| c.abs() <= head.scale_limit());
    SurfaceAssessment {
        corner_residual: corners.iter().fold(0.0_f64, |m, &c| m.max(c)) / diagonal,
        finite,
        hull_violations: violations,
        folds,
        arc_ratio,
        bbox: box_,
        scale_ok,
        arc_applicable: head.subtype != SUBTYPE_COMPACT,
    }
}

fn sample_axis(distinct: &[f64], counts: &[usize]) -> (Vec<f64>, Vec<usize>) {
    let mut values = Vec::new();
    let mut spans = Vec::new();
    for (span, &count) in counts.iter().enumerate() {
        let lo = distinct[span];
        let hi = distinct[span + 1];
        let step = hi - lo;
        for k in 0..count {
            values.push(lo + step * k as f64 / count as f64);
            spans.push(span);
        }
    }
    values.push(distinct[distinct.len() - 1]);
    (values, spans)
}

fn refined(counts: &mut [usize], errors: &[f64], tolerance: f64) -> bool {
    let mut changed = false;
    for (span, &error) in errors.iter().enumerate() {
        if error > tolerance && counts[span] < MAX_STEPS {
            counts[span] *= 2;
            changed = true;
        }
    }
    changed
}

fn area2(a: (f64, f64, f64), b: (f64, f64, f64), c: (f64, f64, f64)) -> f64 {
    let ux = b.0 - a.0;
    let uy = b.1 - a.1;
    let uz = b.2 - a.2;
    let vx = c.0 - a.0;
    let vy = c.1 - a.1;
    let vz = c.2 - a.2;
    let cx = uy * vz - uz * vy;
    let cy = uz * vx - ux * vz;
    let cz = ux * vy - uy * vx;
    (cx * cx + cy * cy + cz * cz).sqrt()
}

/// Tessellate one evaluable surface; ``None`` when no sane mesh exists.
pub fn tessellate(
    head: &SurfaceHead,
    poles: &[Vec<(f64, f64, f64)>],
    weights: Option<&[Vec<f64>]>,
    tolerance_factor: f64,
) -> Option<TessellatedPatch> {
    let (knots_u, knots_v) = head.knots();
    let distinct_u = &head.knots_u;
    let distinct_v = &head.knots_v;
    let flat: Vec<(f64, f64, f64)> = poles.iter().flatten().copied().collect();
    let box_ = bbox(&flat);
    let diag = diagonal(box_);
    let diagonal = if diag == 0.0 { 1.0 } else { diag };
    let tolerance = tolerance_factor * diagonal;
    let mut counts_u = vec![INITIAL_STEPS; distinct_u.len() - 1];
    let mut counts_v = vec![INITIAL_STEPS; distinct_v.len() - 1];
    let mut best: Option<Grid> = None;
    for _ in 0..MAX_ROUNDS {
        let (us, span_u) = sample_axis(distinct_u, &counts_u);
        let (vs, span_v) = sample_axis(distinct_v, &counts_v);
        if us.len() * vs.len() > MAX_GRID_POINTS {
            break;
        }
        let grid: Vec<Vec<(f64, f64, f64)>> = us
            .iter()
            .map(|&u| {
                vs.iter()
                    .map(|&v| {
                        evaluate(
                            poles,
                            &knots_u,
                            &knots_v,
                            u,
                            v,
                            head.degree_u,
                            head.degree_v,
                            weights,
                        )
                    })
                    .collect()
            })
            .collect();
        best = Some((us, vs, grid));
        let (us, vs, grid) = best.as_ref().unwrap();
        let mut errors_u = vec![0.0; counts_u.len()];
        let mut errors_v = vec![0.0; counts_v.len()];
        for i in 0..us.len() - 1 {
            for j in 0..vs.len() - 1 {
                let p00 = grid[i][j];
                let p10 = grid[i + 1][j];
                let p01 = grid[i][j + 1];
                let p11 = grid[i + 1][j + 1];
                let middle = (
                    (p00.0 + p10.0 + p01.0 + p11.0) / 4.0,
                    (p00.1 + p10.1 + p01.1 + p11.1) / 4.0,
                    (p00.2 + p10.2 + p01.2 + p11.2) / 4.0,
                );
                let centre = evaluate(
                    poles,
                    &knots_u,
                    &knots_v,
                    (us[i] + us[i + 1]) / 2.0,
                    (vs[j] + vs[j + 1]) / 2.0,
                    head.degree_u,
                    head.degree_v,
                    weights,
                );
                let deviation = distance(centre, middle);
                if deviation > errors_u[span_u[i]] {
                    errors_u[span_u[i]] = deviation;
                }
                if deviation > errors_v[span_v[j]] {
                    errors_v[span_v[j]] = deviation;
                }
            }
        }
        let changed_u = refined(&mut counts_u, &errors_u, tolerance);
        let changed_v = refined(&mut counts_v, &errors_v, tolerance);
        if !(changed_u || changed_v) {
            break;
        }
    }
    let (us, vs, grid) = best?;
    let nv = vs.len();
    let vertices: Vec<(f64, f64, f64)> = (0..us.len())
        .flat_map(|i| (0..nv).map(move |j| (i, j)))
        .map(|(i, j)| grid[i][j])
        .collect();
    let mut triangles: Vec<(u32, u32, u32)> = Vec::new();
    let mut degenerate = 0;
    let area_floor = DEGENERATE_AREA_FRACTION * diagonal * diagonal;
    for i in 0..us.len() - 1 {
        for j in 0..nv - 1 {
            let a = i * nv + j;
            let b = (i + 1) * nv + j;
            let c = (i + 1) * nv + j + 1;
            let d = i * nv + j + 1;
            if area2(vertices[a], vertices[b], vertices[c]) > area_floor {
                triangles.push((a as u32, b as u32, c as u32));
            } else {
                degenerate += 1;
            }
            if area2(vertices[a], vertices[c], vertices[d]) > area_floor {
                triangles.push((a as u32, c as u32, d as u32));
            } else {
                degenerate += 1;
            }
        }
    }
    if triangles.is_empty() {
        return None;
    }
    let stats = mesh::mesh_stats(&triangles);
    if !stats.manifold {
        return None;
    }
    Some(TessellatedPatch {
        vertices,
        triangles,
        degenerate,
        tolerance,
        grid_points: us.len() * nv,
        manifold: stats.manifold,
        oriented: stats.oriented,
    })
}

/// Census one part and merge every tessellatable surface's mesh.
pub fn scan_part(data: &[u8], tolerance_factor: f64) -> SurfaceScan {
    let region = surface_block(data);
    let frames = candidate_frames(data);
    let mut decoded = 0;
    let mut evaluable = 0;
    let mut tessellated = 0;
    let mut refused = 0;
    let mut manifold_patches = 0;
    let mut vertices: Vec<(f64, f64, f64)> = Vec::new();
    let mut triangles: Vec<(u32, u32, u32)> = Vec::new();
    let mut tolerances: Vec<f64> = Vec::new();
    let mut degenerate = 0;
    let mut points = 0;
    for (_, payload, end) in frames.iter().copied() {
        let Some(head) = parse_surface_head(data, payload, end) else {
            continue;
        };
        let (poles, weights) = pole_data(data, &head);
        if !plausible_net(&poles) || !plausible_weights(weights.as_deref()) {
            continue;
        }
        decoded += 1;
        points += head.points();
        if !assess(&head, &poles, weights.as_deref()).evaluable() {
            refused += 1;
            continue;
        }
        evaluable += 1;
        let Some(patch) = tessellate(&head, &poles, weights.as_deref(), tolerance_factor) else {
            refused += 1;
            continue;
        };
        tessellated += 1;
        if mesh::mesh_stats(&patch.triangles).manifold {
            manifold_patches += 1;
        }
        let base = vertices.len() as u32;
        vertices.extend(patch.vertices);
        triangles.extend(
            patch
                .triangles
                .iter()
                .map(|&(a, b, c)| (a + base, b + base, c + base)),
        );
        tolerances.push(patch.tolerance);
        degenerate += patch.degenerate;
    }
    // The E5 dialect's 0x00e7 records, under the same battery.  They fold
    // into the totals and the mesh only when at least one tessellated;
    // with nothing tessellated the E5 census rides on the e5_* fields
    // alone and the totals, the mesh and the route decision are exactly
    // what they were before the E5 route existed (the no-regret law).
    let e5_frames = e5_surface_frames(data);
    let e5_candidates = e5_frames.len();
    let mut e5_decoded = 0;
    let mut e5_evaluable = 0;
    let mut e5_refused = 0;
    let mut e5_points = 0;
    let mut e5_patches: Vec<TessellatedPatch> = Vec::new();
    for (payload, end) in e5_frames.iter().copied() {
        let Some(head) = parse_e5_surface(data, payload, end) else {
            continue;
        };
        let (poles, weights) = e5_pole_data(data, &head);
        if !plausible_net(&poles) || !plausible_weights(weights.as_deref()) {
            continue;
        }
        e5_decoded += 1;
        e5_points += head.points();
        if !assess(&head, &poles, weights.as_deref()).evaluable() {
            e5_refused += 1;
            continue;
        }
        let Some(patch) = tessellate(&head, &poles, weights.as_deref(), tolerance_factor) else {
            e5_refused += 1;
            continue;
        };
        e5_evaluable += 1;
        e5_patches.push(patch);
    }
    let mut candidates = frames.len();
    if !e5_patches.is_empty() {
        let e5_tessellated = e5_patches.len();
        points += e5_points;
        for patch in &e5_patches {
            if mesh::mesh_stats(&patch.triangles).manifold {
                manifold_patches += 1;
            }
            let base = vertices.len() as u32;
            vertices.extend(patch.vertices.clone());
            triangles.extend(
                patch
                    .triangles
                    .iter()
                    .map(|&(a, b, c)| (a + base, b + base, c + base)),
            );
            tolerances.push(patch.tolerance);
            degenerate += patch.degenerate;
        }
        candidates += e5_candidates;
        decoded += e5_decoded;
        evaluable += e5_evaluable;
        tessellated += e5_tessellated;
        refused += e5_refused;
        SurfaceScan {
            block: region.map(|(blk, _)| blk),
            candidates,
            decoded,
            evaluable,
            tessellated,
            refused,
            manifold_patches,
            vertices,
            triangles,
            degenerate,
            tolerances,
            points,
            e5_candidates,
            e5_decoded,
            e5_evaluable,
            e5_tessellated,
            e5_refused,
        }
    } else {
        SurfaceScan {
            block: region.map(|(blk, _)| blk),
            candidates,
            decoded,
            evaluable,
            tessellated,
            refused,
            manifold_patches,
            vertices,
            triangles,
            degenerate,
            tolerances,
            points,
            e5_candidates,
            e5_decoded: 0,
            e5_evaluable: 0,
            e5_tessellated: 0,
            e5_refused: 0,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn push_f64(out: &mut Vec<u8>, value: f64) {
        out.extend_from_slice(&value.to_le_bytes());
    }

    fn head_bytes() -> Vec<u8> {
        let knots_u = [0.0, 30.0, 60.0, 110.0];
        let knots_v = [0.0, 24.0, 64.0];
        let mut out = Vec::new();
        out.extend_from_slice(&HEAD_TAG.to_le_bytes());
        out.extend_from_slice(&(knots_u.len() as u32).to_le_bytes());
        out.push(0);
        out.extend_from_slice(&2u32.to_le_bytes());
        for value in knots_u {
            push_f64(&mut out, value);
        }
        out.push(LANE_TAG);
        out.extend_from_slice(&HEAD_TAG.to_le_bytes());
        out.extend_from_slice(&(knots_v.len() as u32).to_le_bytes());
        out.push(0);
        out.extend_from_slice(&2u32.to_le_bytes());
        for value in knots_v {
            push_f64(&mut out, value);
        }
        out.extend_from_slice(&CLOSING);
        out
    }

    fn payload(degenerate: bool) -> Vec<u8> {
        let mut out = head_bytes();
        for i in 0..12 {
            for j in 0..9 {
                let (x, y, z) = if degenerate {
                    (0.0, 0.0, 0.0)
                } else {
                    (10.0 * i as f64, 8.0 * j as f64, 0.02 * (i * i) as f64)
                };
                push_f64(&mut out, x);
                push_f64(&mut out, y);
                push_f64(&mut out, z);
            }
        }
        out.extend(std::iter::repeat_n(0u8, 152));
        out
    }

    fn part_data(degenerate: bool) -> Vec<u8> {
        let mut data = vec![0u8; 32];
        data.extend_from_slice(b"\x34\x12CATStorageProperty");
        data.extend(std::iter::repeat_n(0u8, 10));
        data.extend_from_slice(b"CATUnicodeString");
        data.extend_from_slice(b"\xa0\x02\x00\x00\x00\x00\x34");
        let name = b"CATPrtCont";
        data.push(name.len() as u8);
        data.extend_from_slice(name);
        data.extend(std::iter::repeat_n(0u8, 64));
        let blob = payload(degenerate);
        data.extend_from_slice(&SURFACE_MARKER);
        data.extend_from_slice(&(blob.len() as u32).to_le_bytes());
        data.push(0x0f);
        data.extend_from_slice(&blob);
        data
    }

    fn patch_head(n_u: usize, degree_v: u32, n_v: usize, rational: bool) -> Vec<u8> {
        // Chord-length lanes: the u span matches the sweep of this test net.
        let knots_u: Vec<f64> = (0..n_u).map(|i| 50.0 * i as f64).collect();
        let knots_v: Vec<f64> = (0..n_v).map(|j| 16.0 * j as f64).collect();
        let mut out = Vec::new();
        out.extend_from_slice(&HEAD_TAG.to_le_bytes());
        out.extend_from_slice(&(n_u as u32).to_le_bytes());
        out.push(SUBTYPE_PATCH);
        for value in knots_u {
            push_f64(&mut out, value);
        }
        out.push(LANE_TAG);
        out.extend_from_slice(&degree_v.to_le_bytes());
        out.extend_from_slice(&(n_v as u32).to_le_bytes());
        out.push(SUBTYPE_PATCH);
        for value in knots_v {
            push_f64(&mut out, value);
        }
        out.push(0x01);
        out.push(if rational { 0x01 } else { 0x00 });
        out.push(0x00);
        out
    }

    fn patch_payload(rational: bool, bad_weight: bool) -> Vec<u8> {
        let n_u = 2usize;
        let degree_v = 2u32;
        let n_v = 2usize;
        let poles_u = 3 * n_u;
        let poles_v = (degree_v as usize + 1) + 3 * (n_v - 2);
        let mut out = patch_head(n_u, degree_v, n_v, rational);
        for i in 0..poles_u {
            for j in 0..poles_v {
                push_f64(&mut out, 10.0 * i as f64);
                push_f64(&mut out, 8.0 * j as f64);
                push_f64(&mut out, 0.02 * (i * i) as f64);
            }
        }
        if rational {
            for i in 0..poles_u {
                for _ in 0..poles_v {
                    let weight = if bad_weight && i == 0 { 0.0 } else { 1.0 };
                    push_f64(&mut out, weight);
                }
            }
        }
        out.extend(std::iter::repeat_n(0u8, 152));
        out
    }

    // ----------------------------------------------------- E5 surfaces

    fn e5_lane(degree: usize, knots: &[f64], mult: &[usize]) -> Vec<u8> {
        let mut out = Vec::new();
        out.extend_from_slice(&(degree as u32).to_le_bytes());
        out.extend_from_slice(&0u32.to_le_bytes());
        out.extend_from_slice(&0u32.to_le_bytes());
        out.extend_from_slice(&(knots.len() as u32).to_le_bytes());
        out.extend_from_slice(&0u32.to_le_bytes());
        for value in knots {
            push_f64(&mut out, *value);
        }
        for value in mult {
            out.extend_from_slice(&(*value as u32).to_le_bytes());
        }
        out
    }

    /// Two lanes + marker + a v-major pole net (+ optional weights) + tail.
    /// Pole ``(i, j)`` = ``(5i, 7j, 2 + 0.5i + 0.25j)``: consecutive
    /// ``poles_u`` triples are the u-polygon at a fixed v.
    fn e5_payload(
        lane_v: &[u8],
        lane_u: &[u8],
        poles_u: usize,
        poles_v: usize,
        rational: bool,
    ) -> Vec<u8> {
        let mut out = vec![E5_SURFACE_TAG];
        out.extend_from_slice(lane_v);
        out.extend_from_slice(lane_u);
        out.extend_from_slice(if rational {
            &E5_POLE_MARKER_RATIONAL
        } else {
            &E5_POLE_MARKER_PLAIN
        });
        for j in 0..poles_v {
            for i in 0..poles_u {
                push_f64(&mut out, 5.0 * i as f64);
                push_f64(&mut out, 7.0 * j as f64);
                push_f64(&mut out, 2.0 + 0.5 * i as f64 + 0.25 * j as f64);
            }
        }
        if rational {
            for _ in 0..poles_u * poles_v {
                push_f64(&mut out, 1.0);
            }
        }
        out.extend(std::iter::repeat_n(0u8, 148));
        out
    }

    fn e5_record(out: &mut Vec<u8>, cls: u16, payload: &[u8]) {
        out.extend_from_slice(&[0xe5, 0x0d, 0x03]);
        out.extend_from_slice(&cls.to_le_bytes());
        out.extend_from_slice(&(payload.len() as u32).to_le_bytes());
        out.extend_from_slice(&100u32.to_le_bytes());
        out.extend_from_slice(payload);
    }

    fn e5_part(records: &[(u16, &[u8])]) -> Vec<u8> {
        let mut data = vec![0u8; 32];
        data.extend_from_slice(b"\x34\x12CATStorageProperty");
        data.extend(std::iter::repeat_n(0u8, 10));
        data.extend_from_slice(b"CATUnicodeString");
        data.extend_from_slice(b"\xa0\x02\x00\x00\x00\x00\x34");
        data.push(10);
        data.extend_from_slice(b"CATPrtCont");
        data.extend(std::iter::repeat_n(0u8, 64));
        for &(cls, payload) in records {
            e5_record(&mut data, cls, payload);
        }
        data
    }

    #[test]
    fn e5_head_pins_the_lane_law_and_the_pole_law() {
        let lane_v = e5_lane(3, &[0.0, 2.0, 4.0], &[4, 1, 4]);
        let lane_u = e5_lane(1, &[0.0, 1.0], &[2, 2]);
        let blob = e5_payload(&lane_v, &lane_u, 2, 5, false);
        let head = parse_e5_surface(&blob, 0, blob.len()).unwrap();
        assert_eq!(head.subtype, SUBTYPE_COMPACT);
        assert_eq!((head.degree_u, head.degree_v), (1, 3));
        assert_eq!((head.n_u, head.n_v), (2, 3));
        assert_eq!(head.mult_v, vec![4, 1, 4]);
        assert_eq!((head.poles_u(), head.poles_v()), (2, 5));
        assert_eq!(head.points(), 10);
        assert_eq!(head.grid, 1 + lane_v.len() + lane_u.len() + 2);
        assert_eq!(head.tail(), 148);
    }

    #[test]
    fn e5_rational_marker_reads_the_weights_that_follow_the_net() {
        let lane = e5_lane(1, &[0.0, 1.0], &[2, 2]);
        let rational = e5_payload(&lane, &lane, 2, 2, true);
        let head = parse_e5_surface(&rational, 0, rational.len()).unwrap();
        assert!(head.rational);
        let (_poles, weights) = e5_pole_data(&rational, &head);
        let weights = weights.unwrap();
        assert!(weights.iter().all(|row| row.iter().all(|&w| w == 1.0)));
        let plain_blob = e5_payload(&lane, &lane, 2, 2, false);
        let plain = parse_e5_surface(&plain_blob, 0, plain_blob.len()).unwrap();
        assert_eq!(plain.tail(), head.tail());
        assert_eq!(head.end, plain.end + 8 * head.points());
    }

    #[test]
    fn e5_pole_net_is_v_major_outer() {
        let lane_v = e5_lane(1, &[0.0, 0.5, 1.0], &[2, 2, 2]);
        let lane_u = e5_lane(1, &[0.0, 1.0], &[3, 2]);
        let blob = e5_payload(&lane_v, &lane_u, 3, 4, false);
        let head = parse_e5_surface(&blob, 0, blob.len()).unwrap();
        assert_eq!((head.poles_u(), head.poles_v()), (3, 4));
        let poles = e5_pole_data(&blob, &head).0;
        assert_eq!(poles[0][0], (0.0, 0.0, 2.0));
        assert_eq!(poles[1][0], (5.0, 0.0, 2.5));
        assert_eq!(poles[0][1], (0.0, 7.0, 2.25));
        assert_eq!(poles[2][3], (10.0, 21.0, 3.75));
    }

    #[test]
    fn e5_the_battery_accepts_a_plane() {
        let lane = e5_lane(1, &[0.0, 1.0], &[2, 2]);
        let blob = e5_payload(&lane, &lane, 2, 2, false);
        let head = parse_e5_surface(&blob, 0, blob.len()).unwrap();
        let (poles, weights) = e5_pole_data(&blob, &head);
        assert!(plausible_net(&poles));
        let assessment = assess(&head, &poles, weights.as_deref());
        assert!(assessment.evaluable());
        assert!((assessment.corner_residual - 0.0).abs() < 1e-12);
        assert!(!assessment.arc_applicable);
        let patch = tessellate(&head, &poles, weights.as_deref(), TOLERANCE_FRACTION).unwrap();
        assert_eq!(patch.degenerate, 0);
    }

    #[test]
    fn e5_refusals() {
        let lane = e5_lane(1, &[0.0, 1.0], &[2, 2]);
        let blob = e5_payload(&lane, &lane, 2, 2, false);
        // A non-monotone knot lane refuses.
        let bad_v = e5_lane(1, &[0.0, 2.0, 1.0], &[2, 2, 2]);
        let bad = e5_payload(&bad_v, &lane, 2, 2, false);
        assert!(parse_e5_surface(&bad, 0, bad.len()).is_none());
        // A zero multiplicity refuses.
        let zero = e5_lane(1, &[0.0, 1.0], &[0, 2]);
        let bad = e5_payload(&lane, &zero, 2, 2, false);
        assert!(parse_e5_surface(&bad, 0, bad.len()).is_none());
        // A net that overruns the record refuses; a truncated tail does not.
        assert!(parse_e5_surface(&blob, 0, 160).is_none());
        assert!(parse_e5_surface(&blob, 0, blob.len() - 40).is_some());
        // A marker outside the measured pair refuses.
        let mut marker = blob.clone();
        let marker_at = 1 + e5_lane(1, &[0.0, 1.0], &[2, 2]).len() * 2;
        marker[marker_at] = 0x02;
        assert!(parse_e5_surface(&marker, 0, marker.len()).is_none());
        // A tag outside the measured one refuses.
        let mut tag = blob.clone();
        tag[0] = 0x81;
        assert!(parse_e5_surface(&tag, 0, tag.len()).is_none());
    }

    #[test]
    fn e5_the_walk_yields_the_surface_class_and_a_lone_record_is_not_admitted() {
        let lane = e5_lane(1, &[0.0, 1.0], &[2, 2]);
        let blob = e5_payload(&lane, &lane, 2, 2, false);
        let filler = [0u8; 8];
        let chained = e5_part(&[
            (0x000Eu16, &filler),
            (E5_SURFACE_CLASS, &blob),
            (0x000Du16, &filler),
        ]);
        let records = super::super::grid::e5_records(&chained);
        let classes: Vec<u16> = records.iter().map(|&(_, _, cls)| cls).collect();
        assert_eq!(classes, vec![0x000E, E5_SURFACE_CLASS, 0x000D]);
        let frames = e5_surface_frames(&chained);
        assert_eq!(frames.len(), 1);
        let lone = e5_part(&[(E5_SURFACE_CLASS, &blob)]);
        assert!(super::super::grid::e5_records(&lone).is_empty());
        assert!(e5_surface_frames(&lone).is_empty());
    }

    #[test]
    fn e5_the_scan_folds_only_when_a_surface_tessellates() {
        let lane = e5_lane(1, &[0.0, 1.0], &[2, 2]);
        let blob = e5_payload(&lane, &lane, 2, 2, false);
        let filler = [0u8; 8];
        let chained = e5_part(&[
            (0x000Eu16, &filler),
            (E5_SURFACE_CLASS, &blob),
            (E5_SURFACE_CLASS, &blob),
        ]);
        let scan = scan_part(&chained, TOLERANCE_FRACTION);
        assert_eq!(scan.candidates, 2);
        assert_eq!(
            (scan.e5_candidates, scan.e5_decoded, scan.e5_evaluable),
            (2, 2, 2)
        );
        assert_eq!((scan.e5_tessellated, scan.e5_refused), (2, 0));
        assert_eq!(scan.tessellated, 2);
        assert!(scan.has_mesh());
        // Implausible nets: nothing folds, the totals are the pre-E5 ones.
        let mut huge = blob.clone();
        let net_at = 1 + 2 * lane.len() + 2;
        for k in 0..4usize {
            let off = net_at + 24 * k;
            huge[off..off + 8].copy_from_slice(&5e6f64.to_le_bytes());
            huge[off + 8..off + 16].copy_from_slice(&7e6f64.to_le_bytes());
            huge[off + 16..off + 24].copy_from_slice(&2e6f64.to_le_bytes());
        }
        let refused = e5_part(&[
            (0x000Eu16, &filler),
            (E5_SURFACE_CLASS, &huge),
            (E5_SURFACE_CLASS, &huge),
        ]);
        let scan = scan_part(&refused, TOLERANCE_FRACTION);
        assert_eq!((scan.e5_candidates, scan.e5_decoded), (2, 0));
        assert_eq!(
            (scan.e5_evaluable, scan.e5_tessellated, scan.e5_refused),
            (0, 0, 0)
        );
        assert_eq!(scan.candidates, 0);
        assert!(!scan.has_mesh());
    }

    #[test]
    fn patch_head_pins_the_v_degree_and_the_pole_law() {
        for rational in [false, true] {
            let blob = patch_payload(rational, false);
            let head = parse_surface_head(&blob, 0, blob.len()).unwrap();
            assert_eq!(head.subtype, SUBTYPE_PATCH);
            assert_eq!((head.n_u, head.n_v), (2, 2));
            assert_eq!((head.degree_u, head.degree_v), (5, 2));
            assert_eq!((head.poles_u(), head.poles_v()), (6, 3));
            assert_eq!(head.points(), 18);
            assert_eq!(head.rational, rational);
            assert_eq!(head.tail(), 152);
            let (poles, weights) = pole_data(&blob, &head);
            assert!(plausible_net(&poles));
            assert!(plausible_weights(weights.as_deref()));
            assert!(assess(&head, &poles, weights.as_deref()).evaluable());
            assert!(tessellate(&head, &poles, weights.as_deref(), TOLERANCE_FRACTION).is_some());
        }
        let bad = patch_payload(true, true);
        let head = parse_surface_head(&bad, 0, bad.len()).unwrap();
        let (_, weights) = pole_data(&bad, &head);
        assert!(!plausible_weights(weights.as_deref()));
    }

    #[test]
    fn head_predicts_the_grid_and_the_knots_are_clamped_degree_five() {
        let blob = payload(false);
        let head = parse_surface_head(&blob, 0, blob.len()).unwrap();
        assert_eq!((head.n_u, head.n_v), (4, 3));
        assert_eq!((head.poles_u(), head.poles_v()), (12, 9));
        assert_eq!(head.points(), 108);
        assert_eq!(head.head_bytes(), 30 + 8 * (4 + 3));
        assert_eq!(head.grid, head.head_bytes());
        assert_eq!(head.tail(), 152);
        let knots = knot_vector(&head.knots_u, DEGREE);
        assert_eq!(knots.len(), 3 * 4 + 6);
        assert_eq!(&knots[..6], &[0.0; 6]);
        assert_eq!(&knots[6..9], &[30.0; 3]);
        assert_eq!(&knots[9..12], &[60.0; 3]);
        assert_eq!(&knots[12..], &[110.0; 6]);
    }

    #[test]
    fn basis_partitions_unity_and_has_the_degree_five_support() {
        let knots = knot_vector(&[0.0, 30.0, 60.0, 110.0], DEGREE);
        for t in [0.0, 1.0, 15.0, 30.0, 45.0, 60.0, 90.0, 110.0] {
            let values = basis_values(t, &knots, DEGREE, 12);
            let sum: f64 = values.iter().sum();
            assert!((sum - 1.0).abs() < 1e-12);
            assert!(values.iter().all(|&value| value >= 0.0));
        }
        let active = |t: f64| {
            basis_values(t, &knots, DEGREE, 12)
                .iter()
                .filter(|&&value| value > 0.0)
                .count()
        };
        assert_eq!(active(45.0), 6);
        assert_eq!(active(30.0), 3);
        assert_eq!(active(110.0), 1);
    }

    #[test]
    fn assessment_accepts_the_synthetic_surface_and_refuses_the_zero_arc_net() {
        let blob = payload(false);
        let head = parse_surface_head(&blob, 0, blob.len()).unwrap();
        let poles = pole_net(&blob, &head);
        assert!(plausible_net(&poles));
        assert!(assess(&head, &poles, None).evaluable());
        let zero = payload(true);
        let head = parse_surface_head(&zero, 0, zero.len()).unwrap();
        assert!(!assess(&head, &pole_net(&zero, &head), None).evaluable());
    }

    #[test]
    fn tessellation_is_a_manifold_open_sheet_with_no_degenerate_triangles() {
        let blob = payload(false);
        let head = parse_surface_head(&blob, 0, blob.len()).unwrap();
        let patch = tessellate(&head, &pole_net(&blob, &head), None, TOLERANCE_FRACTION).unwrap();
        assert!(!patch.triangles.is_empty());
        assert_eq!(patch.degenerate, 0);
        let stats = mesh::mesh_stats(&patch.triangles);
        assert!(stats.manifold);
        assert!(!stats.closed);
        assert!(stats.boundary_edges > 0);
        assert_eq!(patch.vertices.len(), patch.grid_points);
        let loose = tessellate(&head, &pole_net(&blob, &head), None, 1e-1).unwrap();
        assert!(loose.grid_points < patch.grid_points);
    }

    #[test]
    fn scan_part_censuses_the_synthetic_record() {
        let scan = scan_part(&part_data(false), TOLERANCE_FRACTION);
        assert_eq!(scan.candidates, 1);
        assert_eq!(scan.decoded, 1);
        assert_eq!(scan.evaluable, 1);
        assert_eq!(scan.tessellated, 1);
        assert_eq!(scan.refused, 0);
        assert_eq!(scan.manifold_patches, 1);
        assert!(scan.has_mesh());
        let refused = scan_part(&part_data(true), TOLERANCE_FRACTION);
        assert_eq!(
            (refused.decoded, refused.evaluable, refused.tessellated),
            (1, 0, 0)
        );
        assert!(!refused.has_mesh());
    }

    // ------------------------------------------------------- compact head

    fn hex_bytes(text: &str) -> Vec<u8> {
        (0..text.len() / 2)
            .map(|i| u8::from_str_radix(&text[2 * i..2 * i + 2], 16).unwrap())
            .collect()
    }

    fn compact_lane(degree: usize, knots: &[f64], mult: Option<&[usize]>) -> Vec<u8> {
        let mut out = Vec::new();
        out.push(((degree as u8) << 2) | 1);
        out.push(((knots.len() as u8) << 2) | 1);
        out.push(if mult.is_some() {
            COMPACT_KNOTS_EXPLICIT
        } else {
            COMPACT_KNOTS_IMPLICIT
        });
        for &value in knots {
            push_f64(&mut out, value);
        }
        if let Some(mult) = mult {
            for &count in mult {
                out.push(((count as u8) << 2) | 1);
            }
        }
        out
    }

    fn compact_head_bytes() -> Vec<u8> {
        let mut out = compact_lane(3, &[0.0, 1.0], None);
        out.extend(compact_lane(1, &[0.0, 1.0], None));
        out.push(0x01);
        out
    }

    fn flat_net(rows: usize, cols: usize) -> Vec<u8> {
        let mut out = Vec::new();
        for i in 0..rows {
            for j in 0..cols {
                push_f64(&mut out, 10.0 * i as f64);
                push_f64(&mut out, 8.0 * j as f64);
                push_f64(&mut out, 0.0);
            }
        }
        out
    }

    fn compact_payload(tail: usize) -> Vec<u8> {
        let mut out = compact_head_bytes();
        out.extend(flat_net(4, 2));
        out.extend(std::iter::repeat_n(0u8, tail));
        out
    }

    fn compact_part_data() -> Vec<u8> {
        let mut data = vec![0u8; 32];
        data.extend_from_slice(b"\x34\x12CATStorageProperty");
        data.extend(std::iter::repeat_n(0u8, 10));
        data.extend_from_slice(b"CATUnicodeString");
        data.extend_from_slice(b"\xa0\x02\x00\x00\x00\x00\x34");
        let name = b"CATPrtCont";
        data.push(name.len() as u8);
        data.extend_from_slice(name);
        data.extend(std::iter::repeat_n(0u8, 64));
        let blob = compact_payload(141);
        data.extend_from_slice(&SURFACE_MARKER);
        data.extend_from_slice(&(blob.len() as u32).to_le_bytes());
        data.push(0x0f);
        data.extend_from_slice(&blob);
        data
    }

    fn legacy_head_bytes(knots_u: &[f64], knots_v: &[f64]) -> Vec<u8> {
        fn push_lane_block(out: &mut Vec<u8>, knots: &[f64]) {
            out.extend_from_slice(&HEAD_TAG.to_le_bytes());
            out.extend_from_slice(&(knots.len() as u32).to_le_bytes());
            out.push(0);
            out.extend_from_slice(&2u32.to_le_bytes());
            for &value in knots {
                push_f64(out, value);
            }
        }
        let mut out = Vec::new();
        push_lane_block(&mut out, knots_u);
        out.push(LANE_TAG);
        push_lane_block(&mut out, knots_v);
        out.extend_from_slice(&CLOSING);
        out
    }

    fn legacy_payload(net: &[(f64, f64, f64)], knots_u: &[f64], knots_v: &[f64]) -> Vec<u8> {
        let mut out = legacy_head_bytes(knots_u, knots_v);
        for &(x, y, z) in net {
            push_f64(&mut out, x);
            push_f64(&mut out, y);
            push_f64(&mut out, z);
        }
        out.extend(std::iter::repeat_n(0u8, 152));
        out
    }

    #[test]
    fn compact_head_pins_the_lane_tokens_and_the_pole_law() {
        let blob = compact_payload(141);
        let head = parse_surface_head(&blob, 0, blob.len()).unwrap();
        assert_eq!(head.subtype, SUBTYPE_COMPACT);
        assert_eq!((head.degree_u, head.degree_v), (3, 1));
        assert_eq!((head.n_u, head.n_v), (2, 2));
        assert_eq!(head.mult_u, vec![4, 4]);
        assert_eq!(head.mult_v, vec![2, 2]);
        assert_eq!((head.poles_u(), head.poles_v()), (4, 2));
        assert_eq!(head.points(), 8);
        assert_eq!(head.head_bytes(), 2 * (3 + 16) + 1);
        assert_eq!(head.grid, head.head_bytes());
        assert_eq!(head.tail(), 141);
        assert_eq!(head.knots().0, vec![0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0]);
    }

    #[test]
    fn compact_head_decodes_the_measured_frame_hex() {
        // ST-Stern-ins.CATPart frame 0x5a56: 0d 09 0c / 0.0 / 1.0 /
        // 05 09 0c / 0.0 / 1.0 / 01, then the 4 x 2 net.
        let mut blob = hex_bytes(
            "0d090c0000000000000000000000000000f03f\
             05090c0000000000000000000000000000f03f01",
        );
        blob.extend(flat_net(4, 2));
        blob.extend(std::iter::repeat_n(0u8, 141));
        let head = parse_surface_head(&blob, 0, blob.len()).unwrap();
        assert_eq!((head.degree_u, head.degree_v), (3, 1));
        assert_eq!((head.n_u, head.n_v), (2, 2));
        assert_eq!(head.mult_u, vec![4, 4]);
        assert_eq!(head.mult_v, vec![2, 2]);
        assert_eq!((head.poles_u(), head.poles_v()), (4, 2));
        assert_eq!(head.grid, 0x27);
        assert_eq!(head.head_bytes(), 39);
        assert_eq!(head.tail(), 141);
    }

    #[test]
    fn compact_explicit_multiplicity_vector() {
        // BW-Hull-Bow-YL.CATPart frame 0x6f2e: degree 5, 3 knots, explicit
        // 19 05 19 = (6, 1, 6), then an implicit degree-5 lane.
        let mut blob = hex_bytes(
            "150d048109a7b5e046843fbf59b59d1683e13fcae236e9ffffef3f190519\
             150d0c0000000000000000000000000000e03f000000000000f03f01",
        );
        blob.extend(flat_net(7, 7));
        blob.extend(std::iter::repeat_n(0u8, 477));
        let head = parse_surface_head(&blob, 0, blob.len()).unwrap();
        assert_eq!((head.degree_u, head.degree_v), (5, 5));
        assert_eq!(head.mult_u, vec![6, 1, 6]);
        assert_eq!(head.mult_v, vec![6, 1, 6]);
        assert_eq!((head.poles_u(), head.poles_v()), (7, 7));
        assert_eq!(head.head_bytes(), 58);
        assert_eq!(head.tail(), 477);
        assert_eq!(
            head.poles_u(),
            head.mult_u.iter().sum::<usize>() - head.degree_u - 1
        );
    }

    #[test]
    fn compact_tail_is_not_a_closure_law() {
        for tail in [0usize, 141, 185, 3597] {
            let blob = compact_payload(tail);
            let head = parse_surface_head(&blob, 0, blob.len()).unwrap();
            assert_eq!(head.tail(), tail);
        }
    }

    #[test]
    fn compact_accepts_both_pole_markers_and_refuses_others() {
        for marker in COMPACT_POLE_MARKERS {
            let mut blob = compact_head_bytes();
            let last = blob.len() - 1;
            blob[last] = marker;
            blob.extend(flat_net(4, 2));
            blob.extend(std::iter::repeat_n(0u8, 141));
            assert!(parse_surface_head(&blob, 0, blob.len()).is_some());
        }
        let mut blob = compact_head_bytes();
        let last = blob.len() - 1;
        blob[last] = 0x0f;
        blob.extend(flat_net(4, 2));
        blob.extend(std::iter::repeat_n(0u8, 141));
        assert!(parse_surface_head(&blob, 0, blob.len()).is_none());
    }

    #[test]
    fn compact_arc_band_is_not_applied_while_legacy_keeps_it() {
        let net: Vec<(f64, f64, f64)> = (0..6)
            .flat_map(|i| (0..6).map(move |j| (10.0 * i as f64, 8.0 * j as f64, 0.0)))
            .collect();
        let legacy = legacy_payload(&net, &[0.0, 1.0], &[0.0, 1.0]);
        let legacy_head = parse_surface_head(&legacy, 0, legacy.len()).unwrap();
        let legacy_fit = assess(&legacy_head, &pole_net(&legacy, &legacy_head), None);
        assert!(!legacy_fit.arc_coherent());
        assert!(legacy_fit.arc_applicable);
        assert!(!legacy_fit.evaluable());

        let mut compact = compact_lane(5, &[0.0, 1.0], None);
        compact.extend(compact_lane(5, &[0.0, 1.0], None));
        compact.push(0x01);
        for &(x, y, z) in &net {
            push_f64(&mut compact, x);
            push_f64(&mut compact, y);
            push_f64(&mut compact, z);
        }
        compact.extend(std::iter::repeat_n(0u8, 141));
        let head = parse_surface_head(&compact, 0, compact.len()).unwrap();
        let poles = pole_net(&compact, &head);
        let fit = assess(&head, &poles, None);
        assert_eq!(fit.arc_ratio, legacy_fit.arc_ratio);
        assert!(!fit.arc_coherent());
        assert!(!fit.arc_applicable);
        assert!(fit.arc_ok());
        assert!(fit.evaluable());
        assert!(tessellate(&head, &poles, None, TOLERANCE_FRACTION).is_some());
    }

    #[test]
    fn d7ed0772_legacy_frames_stay_refused() {
        // SH-15: two ~993 m nets (merged allocation) and one folded,
        // non-station-constant net.  The compact branch must not weaken the
        // legacy battery.
        let knots_u: Vec<f64> = (0..5).map(|i| 10.0 * 14.0 * i as f64 / 4.0).collect();
        let knots_v: Vec<f64> = (0..3).map(|j| 8.0 * 8.0 * j as f64 / 2.0).collect();
        let in_scale: Vec<(f64, f64, f64)> = (0..15)
            .flat_map(|i| {
                (0..9).map(move |j| (10.0 * i as f64, 8.0 * j as f64, 0.02 * (i * i) as f64))
            })
            .collect();
        let kilometre: Vec<(f64, f64, f64)> = in_scale
            .iter()
            .map(|&(x, y, z)| (1000.0 * x, 1000.0 * y, 1000.0 * z))
            .collect();
        let blob = legacy_payload(&kilometre, &knots_u, &knots_v);
        let head = parse_surface_head(&blob, 0, blob.len()).unwrap();
        let fit = assess(&head, &pole_net(&blob, &head), None);
        assert!(!fit.plausible_scale());
        assert!(!fit.evaluable());

        let junk = vec![(1.47e308, 1.47e308, 1.47e308); 135];
        let blob = legacy_payload(&junk, &knots_u, &knots_v);
        let head = parse_surface_head(&blob, 0, blob.len()).unwrap();
        assert!(!plausible_net(&pole_net(&blob, &head)));

        let folded: Vec<(f64, f64, f64)> = (0..15)
            .flat_map(|i| {
                let x = if i < 7 { i } else { 14 - i };
                (0..9).map(move |j| (10.0 * x as f64, 8.0 * j as f64, 0.0))
            })
            .collect();
        let wide: Vec<f64> = (0..5).map(|i| 14000.0 * i as f64 / 4.0).collect();
        let blob = legacy_payload(&folded, &wide, &knots_v);
        let head = parse_surface_head(&blob, 0, blob.len()).unwrap();
        let fit = assess(&head, &pole_net(&blob, &head), None);
        assert!(fit.folds > 0);
        assert!(!fit.arc_coherent());
        assert!(!fit.evaluable());
    }

    #[test]
    fn scan_part_censuses_the_compact_record() {
        let scan = scan_part(&compact_part_data(), TOLERANCE_FRACTION);
        assert_eq!(scan.candidates, 1);
        assert_eq!(scan.decoded, 1);
        assert_eq!(scan.evaluable, 1);
        assert_eq!(scan.tessellated, 1);
        assert_eq!(scan.refused, 0);
        assert!(scan.has_mesh());
    }
}
