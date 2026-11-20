//! Structured point grids -> **candidate** meshes (E5 and f64-net
//! dialects) — the port of the Python reference module
//! ``catpart.geometry.grid`` (``src/catpart/geometry/grid.py``), per spec
//! §2.1 of ``docs/specs/phase5-viewer-spec.md``.
//!
//! This is the shipped half of ``docs/evidence/2026-11-19-grid-meshing.md``
//! (the triangulation), joined to ``docs/evidence/2026-11-19-e5-dialect.md``
//! (the ``e5 0d`` record law and its 98 rectangular grids) and
//! ``docs/evidence/2026-11-19-bulk-stream.md`` (the content-prefix f64
//! allocations).
//!
//! What is decoded is the **grid**, not a surface.  A grid is the largest
//! 3-divisible run of plausible f64le triples in one carrier (an
//! ``e5 0d`` record payload, or the content-prefix f64 allocation), fitted
//! as ``rows x cols`` by the committed shape law: the row length is the
//! **largest** divisor whose every row is near-constant in one coordinate
//! (mean within-row range <= 1% of that axis's span), rows >= 3, cols >= 3,
//! model scale.  Points are ordered **row-major**: consecutive ``cols``
//! points form one station row and rows advance with the outer index — the
//! bytes pin that grouping (a column-major storage is a different grid
//! under the same fit, because its constant groups have another length).
//!
//! Connectivity is an **inference**, never a decoded surface: two
//! triangles per cell with a consistent winding from the station order,
//! patches concatenated with disjoint index spaces (no topology join, no
//! welding).  Every summary and warning says so
//! (``connectivity = candidate``).
//!
//! Fail-closed rules, all measured rather than tuned: a run with no
//! ``rows x cols`` reading (fewer than 3 rows or 3 columns) is not a grid
//! and leaves the part's pre-grid classification untouched; a grid with a
//! stalled station/column step, a zero-area cell or a non-manifold cell
//! complex is refused, then relaxed for the stalled / degenerate gates
//! (near-duplicate station rows collapse to their first row and only the
//! zero-area cells drop, #59 — the prefix gates stay refused, and a
//! relaxed grid merges only under the strict merged-manifold guard); the
//! prefix dialect has no committed dimension, so
//! it must additionally fit monotone stations and a bounded station step
//! ratio (E5 grids use the committed dimension and report monotonicity
//! instead of gating on it).
//!
//! Numeric contract (spec §2.2): decode module — all arithmetic in f64,
//! verbatim expression shape and order with the Python twin (the
//! ``suboptimal_flops`` allow is the pinned carve-out; ``mul_add`` changes
//! rounding and would break the byte-identical PLY).  Distances are the
//! plain ``sqrt`` of the squared-difference sum, never ``hypot``.
#![allow(clippy::suboptimal_flops)]

use std::collections::BTreeMap;

use super::mesh;
use super::store;

/// The two-byte marker every admitted ``e5 0d`` record starts with.
pub const E5_MARKER: [u8; 2] = [0xe5, 0x0d];
/// ``e5 0d | flag:u8 | class:u16le | length:u32le | id:u32le``.
pub const E5_HEADER_BYTES: usize = 13;
/// A payload longer than this is a misread (the bulk note's bound).
pub const E5_MAX_PAYLOAD: usize = 1 << 20;
/// Runs are admitted only with this many chained records.
pub const E5_MIN_CHAIN: usize = 3;

/// A model coordinate: finite, zero allowed, inside the 100 m envelope.
pub const COORD_FLOOR: f64 = 1e-6;
pub const COORD_CEIL: f64 = 1e5;
/// A grid needs at least three stations and three sample columns.
pub const MIN_ROWS: usize = 3;
pub const MIN_COLS: usize = 3;
/// Largest divisor probed for the row length (the committed pole-net bar).
pub const MAX_COLS_PROBE: usize = 256;
/// Mean within-row range / axis span bar (the committed 1% bar).
pub const SPREAD_BAR: f64 = 0.01;

/// A consecutive station/column step below this fraction of the bbox
/// diagonal is a stall (two identical rows/points).
pub const STALL_FRACTION: f64 = 1e-9;
/// A triangle whose area is below this fraction of diagonal^2 is degenerate.
pub const DEGENERATE_AREA_FRACTION: f64 = 1e-12;
/// The f64-net prefix fallback's station step-ratio bound.
pub const PREFIX_STEP_RATIO: f64 = 4.0;

/// Refusal classes (the summary's ``refusals`` census).
pub const REFUSE_STALLED_STATIONS: &str = "stalled-stations";
pub const REFUSE_STALLED_COLUMNS: &str = "stalled-columns";
pub const REFUSE_DEGENERATE: &str = "degenerate-cells";
pub const REFUSE_NOT_MANIFOLD: &str = "not-manifold";
pub const REFUSE_NON_MONOTONE: &str = "non-monotone-stations";
pub const REFUSE_NON_UNIFORM: &str = "non-uniform-stations";

/// The summary's connectivity label: an inference, not a surface.
pub const CONNECTIVITY: &str = "candidate";

pub const KIND_E5: &str = "e5";
pub const KIND_PREFIX: &str = "prefix";

/// One fitted rectangular reading of a point run (row-major).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct GridShape {
    pub rows: usize,
    pub cols: usize,
    pub station_axis: usize,
    pub spread: f64,
}

/// One 3-divisible point run and its (optional) fitted grid shape.
#[derive(Debug, Clone, PartialEq)]
pub struct PointRun {
    pub kind: &'static str,
    pub start: usize,
    pub cls: Option<u16>,
    pub points: Vec<(f64, f64, f64)>,
    pub shape: Option<GridShape>,
}

/// One part's grid census plus the merged candidate mesh.
#[derive(Debug, Clone, PartialEq)]
pub struct GridScan {
    pub block: Option<usize>,
    pub carriers: usize,
    pub shaped: usize,
    pub meshed: usize,
    pub refused: usize,
    pub refusals: BTreeMap<String, usize>,
    pub duplicate_grids: usize,
    pub station_rows: usize,
    pub columns: usize,
    pub monotone_grids: usize,
    pub points: usize,
    pub vertices: Vec<(f64, f64, f64)>,
    pub triangles: Vec<(u32, u32, u32)>,
    pub relaxed: usize,
}

impl GridScan {
    pub fn has_mesh(&self) -> bool {
        !self.triangles.is_empty()
    }

    /// A ``>=3x3`` grid shape exists: the grid path owns the part.
    pub fn has_candidates(&self) -> bool {
        self.shaped > 0
    }
}

fn u16le(data: &[u8], off: usize) -> u16 {
    u16::from_le_bytes([data[off], data[off + 1]])
}

fn u32le(data: &[u8], off: usize) -> u32 {
    u32::from_le_bytes([data[off], data[off + 1], data[off + 2], data[off + 3]])
}

fn u32be(data: &[u8], off: usize) -> u32 {
    u32::from_be_bytes([data[off], data[off + 1], data[off + 2], data[off + 3]])
}

fn f64le(data: &[u8], off: usize) -> f64 {
    f64::from_le_bytes([
        data[off],
        data[off + 1],
        data[off + 2],
        data[off + 3],
        data[off + 4],
        data[off + 5],
        data[off + 6],
        data[off + 7],
    ])
}

fn distance(a: (f64, f64, f64), b: (f64, f64, f64)) -> f64 {
    let dx = b.0 - a.0;
    let dy = b.1 - a.1;
    let dz = b.2 - a.2;
    (dx * dx + dy * dy + dz * dz).sqrt()
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

fn plausible(value: f64) -> bool {
    value.is_finite() && (value == 0.0 || (COORD_FLOOR..=COORD_CEIL).contains(&value.abs()))
}

/// Longest run of plausible f64le values at any byte phase.
fn numeric_run(data: &[u8], lo: usize, hi: usize) -> (usize, usize) {
    let mut best_count = 0usize;
    let mut best_start = lo;
    for phase in 0..8usize {
        let mut pos = lo + phase;
        let mut current = 0usize;
        let mut start = pos;
        while pos + 8 <= hi {
            if plausible(f64le(data, pos)) {
                if current == 0 {
                    start = pos;
                }
                current += 1;
                if current > best_count {
                    best_count = current;
                    best_start = start;
                }
            } else {
                current = 0;
            }
            pos += 8;
        }
    }
    (best_count, best_start)
}

/// Longest plausible f64 run that *begins* at ``lo`` (the prefix law).
fn leading_run(data: &[u8], lo: usize, hi: usize) -> (usize, usize) {
    let mut best_count = 0usize;
    let mut best_start = lo;
    for phase in 0..8usize {
        let mut pos = lo + phase;
        let mut count = 0usize;
        while pos + 8 <= hi {
            if !plausible(f64le(data, pos)) {
                break;
            }
            count += 1;
            pos += 8;
        }
        if count > best_count {
            best_count = count;
            best_start = lo + phase;
        }
    }
    (best_count, best_start)
}

/// ``(record_start, payload, end, cls)`` of an ``e5 0d`` record, or ``None``.
fn parse_record(data: &[u8], pos: usize, hi: usize) -> Option<(usize, usize, usize, u16)> {
    if pos + E5_HEADER_BYTES > hi {
        return None;
    }
    if data[pos] != E5_MARKER[0] || data[pos + 1] != E5_MARKER[1] {
        return None;
    }
    let length = u32le(data, pos + 5) as usize;
    let end = pos + E5_HEADER_BYTES + length;
    if length > E5_MAX_PAYLOAD || end > hi {
        return None;
    }
    Some((pos, pos + E5_HEADER_BYTES, end, u16le(data, pos + 3)))
}

/// Every record of every admitted run in ``[lo, hi)`` (the record law).
fn records(data: &[u8], lo: usize, hi: usize) -> Vec<(usize, usize, usize, u16)> {
    let mut out: Vec<(usize, usize, usize, u16)> = Vec::new();
    if hi <= E5_HEADER_BYTES {
        return out;
    }
    let mut pos = lo;
    while pos < hi - E5_HEADER_BYTES {
        let Some(first) = parse_record(data, pos, hi) else {
            pos += 1;
            continue;
        };
        let mut run: Vec<(usize, usize, usize, u16)> = vec![first];
        let mut walk = first.2;
        while walk < hi {
            let Some(record) = parse_record(data, walk, hi) else {
                break;
            };
            run.push(record);
            walk = record.2;
        }
        if run.len() >= E5_MIN_CHAIN {
            out.extend(run);
            pos = walk;
        } else {
            pos += 1;
        }
    }
    out
}

/// The content-stream start after the block's metadata table, or ``None``.
fn metadata_content(data: &[u8], block: usize, hi: usize) -> Option<usize> {
    let limit = hi.min(block + 8192);
    for start in block..limit {
        if start + 12 > hi {
            break;
        }
        let total = u32be(data, start) as usize;
        let count = u32be(data, start + 8);
        if !(32..=(1 << 20)).contains(&total) || !(1..=128).contains(&count) {
            continue;
        }
        let end = start + total;
        if end > hi {
            continue;
        }
        let mut pos = start + 12;
        let mut texts: Vec<Vec<u8>> = Vec::new();
        let mut ok = true;
        for _ in 0..count {
            if pos + 14 > end {
                ok = false;
                break;
            }
            let size = u32be(data, pos) as usize;
            let value_type = u16::from_be_bytes([data[pos + 8], data[pos + 9]]);
            let value_bytes = u32be(data, pos + 10) as usize;
            if size != 14 + value_bytes || pos + size > end {
                ok = false;
                break;
            }
            if value_type == 2 {
                texts.push(data[pos + 14..pos + size].to_vec());
            }
            pos += size;
        }
        if !ok || pos != end {
            continue;
        }
        let needle = b"\x00C\x00o\x00n\x00t\x00_";
        let named = texts
            .last()
            .is_some_and(|text| text.windows(needle.len()).any(|w| w == needle));
        if !named {
            continue;
        }
        return Some(end);
    }
    None
}

/// Every ``CATPrtCont`` region's ``(start, end)`` in block order.
pub fn regions(data: &[u8]) -> Vec<(usize, usize)> {
    let blocks = store::valid_blocks(data);
    let outer = if data.len() >= 12 {
        u32::from_be_bytes([data[8], data[9], data[10], data[11]]) as usize
    } else {
        0
    };
    blocks
        .iter()
        .filter(|(_, name)| name == "CATPrtCont")
        .map(|(blk, _)| (*blk, store::probe_region(*blk, &blocks, outer, data.len())))
        .collect()
}

fn ratio(axes: &[Vec<f64>; 3], spans: &[f64; 3], n: usize, cols: usize, axis: usize) -> f64 {
    if spans[axis] <= 0.0 {
        return f64::INFINITY;
    }
    let rows = n / cols;
    let mut spread = 0.0;
    for row in 0..rows {
        let window = &axes[axis][row * cols..(row + 1) * cols];
        let mut low = f64::INFINITY;
        let mut high = f64::NEG_INFINITY;
        for &value in window {
            if value < low {
                low = value;
            }
            if value > high {
                high = value;
            }
        }
        spread += high - low;
    }
    spread / rows as f64 / spans[axis]
}

/// The committed grid shape: the largest admissible row length.
pub fn fit_shape(points: &[(f64, f64, f64)]) -> Option<GridShape> {
    let n = points.len();
    if n < MIN_ROWS * MIN_COLS {
        return None;
    }
    let mut axes: [Vec<f64>; 3] = [
        Vec::with_capacity(n),
        Vec::with_capacity(n),
        Vec::with_capacity(n),
    ];
    for point in points {
        axes[0].push(point.0);
        axes[1].push(point.1);
        axes[2].push(point.2);
    }
    let mut spans = [0.0f64; 3];
    for axis in 0..3 {
        let mut low = f64::INFINITY;
        let mut high = f64::NEG_INFINITY;
        for &value in &axes[axis] {
            if value < low {
                low = value;
            }
            if value > high {
                high = value;
            }
        }
        spans[axis] = high - low;
    }
    let top = n.min(MAX_COLS_PROBE);
    for cols in (3..=top).rev() {
        if !n.is_multiple_of(cols) || n / cols < MIN_ROWS {
            continue;
        }
        let mut axis = 0usize;
        let mut best = f64::INFINITY;
        for candidate in 0..3usize {
            let value = ratio(&axes, &spans, n, cols, candidate);
            if value < best {
                best = value;
                axis = candidate;
            }
        }
        let spread = ratio(&axes, &spans, n, cols, axis);
        if spread <= SPREAD_BAR {
            return Some(GridShape {
                rows: n / cols,
                cols,
                station_axis: axis,
                spread,
            });
        }
    }
    None
}

fn diagonal(points: &[(f64, f64, f64)]) -> f64 {
    let mut low = (f64::INFINITY, f64::INFINITY, f64::INFINITY);
    let mut high = (f64::NEG_INFINITY, f64::NEG_INFINITY, f64::NEG_INFINITY);
    for point in points {
        if point.0 < low.0 {
            low.0 = point.0;
        }
        if point.1 < low.1 {
            low.1 = point.1;
        }
        if point.2 < low.2 {
            low.2 = point.2;
        }
        if point.0 > high.0 {
            high.0 = point.0;
        }
        if point.1 > high.1 {
            high.1 = point.1;
        }
        if point.2 > high.2 {
            high.2 = point.2;
        }
    }
    distance(low, high)
}

fn stations(points: &[(f64, f64, f64)], shape: GridShape) -> Vec<(f64, f64, f64)> {
    let cols = shape.cols;
    let mut out = Vec::with_capacity(shape.rows);
    for row in 0..shape.rows {
        let window = &points[row * cols..(row + 1) * cols];
        let mut x = 0.0;
        let mut y = 0.0;
        let mut z = 0.0;
        for point in window {
            x += point.0;
            y += point.1;
            z += point.2;
        }
        let divisor = cols as f64;
        out.push((x / divisor, y / divisor, z / divisor));
    }
    out
}

fn advance(points: &[(f64, f64, f64)], shape: GridShape, eps: f64) -> Option<&'static str> {
    let centers = stations(points, shape);
    for pair in centers.windows(2) {
        if distance(pair[0], pair[1]) <= eps {
            return Some(REFUSE_STALLED_STATIONS);
        }
    }
    let cols = shape.cols;
    for row in 0..shape.rows {
        let window = &points[row * cols..(row + 1) * cols];
        for pair in window.windows(2) {
            if distance(pair[0], pair[1]) <= eps {
                return Some(REFUSE_STALLED_COLUMNS);
            }
        }
    }
    None
}

fn station_measure(points: &[(f64, f64, f64)], shape: GridShape) -> (bool, f64) {
    let centers = stations(points, shape);
    let axis = shape.station_axis;
    let values: Vec<f64> = centers
        .iter()
        .map(|station| match axis {
            0 => station.0,
            1 => station.1,
            _ => station.2,
        })
        .collect();
    let mut monotone_up = true;
    let mut monotone_down = true;
    for pair in values.windows(2) {
        if pair[1] < pair[0] {
            monotone_up = false;
        }
        if pair[1] > pair[0] {
            monotone_down = false;
        }
    }
    let monotone = monotone_up || monotone_down;
    let mut low = f64::INFINITY;
    let mut high = 0.0f64;
    for pair in centers.windows(2) {
        let step = distance(pair[0], pair[1]);
        if step > 0.0 {
            if step < low {
                low = step;
            }
            if step > high {
                high = step;
            }
        }
    }
    let ratio = if low.is_finite() && high > 0.0 {
        high / low
    } else {
        f64::INFINITY
    };
    (monotone, ratio)
}

fn triangulate(
    points: &[(f64, f64, f64)],
    shape: GridShape,
    diagonal: f64,
) -> Option<Vec<(u32, u32, u32)>> {
    let rows = shape.rows;
    let cols = shape.cols;
    let floor = DEGENERATE_AREA_FRACTION * diagonal * diagonal;
    let mut triangles: Vec<(u32, u32, u32)> = Vec::new();
    for i in 0..rows - 1 {
        for j in 0..cols - 1 {
            let a = i * cols + j;
            let b = (i + 1) * cols + j;
            let c = (i + 1) * cols + j + 1;
            let d = i * cols + j + 1;
            if area2(points[a], points[b], points[c]) <= floor {
                return None;
            }
            if area2(points[a], points[c], points[d]) <= floor {
                return None;
            }
            triangles.push((a as u32, b as u32, c as u32));
            triangles.push((a as u32, c as u32, d as u32));
        }
    }
    Some(triangles)
}

fn points_at(data: &[u8], start: usize, count: usize) -> Vec<(f64, f64, f64)> {
    (0..count)
        .map(|i| {
            let base = start + 24 * i;
            (
                f64le(data, base),
                f64le(data, base + 8),
                f64le(data, base + 16),
            )
        })
        .collect()
}

/// Every 3-divisible point run of the part, in the committed scan order.
pub fn iter_runs(data: &[u8]) -> Vec<PointRun> {
    let mut out: Vec<PointRun> = Vec::new();
    for (block, hi) in regions(data) {
        for (_start, payload, end, cls) in records(data, block, hi) {
            let (count, start) = numeric_run(data, payload, end);
            if count % 3 != 0 || count < 3 {
                continue;
            }
            let points = points_at(data, start, count / 3);
            let shape = fit_shape(&points);
            out.push(PointRun {
                kind: KIND_E5,
                start,
                cls: Some(cls),
                points,
                shape,
            });
        }
        let Some(content) = metadata_content(data, block, hi) else {
            continue;
        };
        let (count, start) = leading_run(data, content, hi);
        if count % 3 != 0 || count < 3 {
            continue;
        }
        let points = points_at(data, start, count / 3);
        let shape = fit_shape(&points);
        out.push(PointRun {
            kind: KIND_PREFIX,
            start,
            cls: None,
            points,
            shape,
        });
    }
    out
}

/// ``(triangles, refusal reason, station monotonicity)`` of one grid.
type Admission = (Option<Vec<(u32, u32, u32)>>, Option<&'static str>, bool);

/// Run the triangulability gates for one shaped grid.
fn admit(points: &[(f64, f64, f64)], shape: GridShape, kind: &str) -> Admission {
    let diag = diagonal(points);
    if diag <= 0.0 {
        return (None, Some(REFUSE_DEGENERATE), false);
    }
    if let Some(stall) = advance(points, shape, STALL_FRACTION * diag) {
        return (None, Some(stall), false);
    }
    let (monotone, step_ratio) = station_measure(points, shape);
    if kind == KIND_PREFIX {
        if !monotone {
            return (None, Some(REFUSE_NON_MONOTONE), monotone);
        }
        if step_ratio > PREFIX_STEP_RATIO {
            return (None, Some(REFUSE_NON_UNIFORM), monotone);
        }
    }
    let Some(triangles) = triangulate(points, shape, diag) else {
        return (None, Some(REFUSE_DEGENERATE), monotone);
    };
    if !mesh::mesh_stats(&triangles).manifold {
        return (None, Some(REFUSE_NOT_MANIFOLD), monotone);
    }
    (Some(triangles), None, monotone)
}

/// The T1 relaxation result: `(kept_rows, collapsed_points, triangles)`.
type RelaxedGrid = (Vec<usize>, Vec<(f64, f64, f64)>, Vec<(u32, u32, u32)>);

/// The T1 relaxation (#59) for the stalled / degenerate refusals: the
/// Python twin is `catpart.geometry.grid._relaxed_triangles`.  Near-
/// duplicate station rows collapse to their first row (step <=
/// `STALL_FRACTION` of the grid diagonal, the stall gate's bar) and only
/// the zero-area cells drop, instead of refusing the whole grid.
/// Returns `(kept_rows, new_points, triangles)` or `None`.
fn relaxed_triangles(points: &[(f64, f64, f64)], shape: GridShape) -> Option<RelaxedGrid> {
    let rows = shape.rows;
    let cols = shape.cols;
    let diag = diagonal(points);
    if diag <= 0.0 {
        return None;
    }
    let eps = STALL_FRACTION * diag;
    let centers = stations(points, shape);
    let mut kept: Vec<usize> = vec![0];
    for row in 1..rows {
        if distance(centers[row], centers[*kept.last().unwrap()]) > eps {
            kept.push(row);
        }
    }
    if kept.len() < MIN_ROWS {
        return None;
    }
    let mut new_points: Vec<(f64, f64, f64)> = Vec::new();
    for &row in &kept {
        new_points.extend_from_slice(&points[row * cols..(row + 1) * cols]);
    }
    let diag = diagonal(&new_points);
    if diag <= 0.0 {
        return None;
    }
    let floor = DEGENERATE_AREA_FRACTION * diag * diag;
    let nrows = kept.len();
    let mut triangles: Vec<(u32, u32, u32)> = Vec::new();
    for i in 0..nrows - 1 {
        for j in 0..cols - 1 {
            let a = i * cols + j;
            let b = (i + 1) * cols + j;
            let c = (i + 1) * cols + j + 1;
            let d = i * cols + j + 1;
            if area2(new_points[a], new_points[b], new_points[c]) <= floor {
                continue;
            }
            if area2(new_points[a], new_points[c], new_points[d]) <= floor {
                continue;
            }
            triangles.push((a as u32, b as u32, c as u32));
            triangles.push((a as u32, c as u32, d as u32));
        }
    }
    if triangles.is_empty() {
        return None;
    }
    if !new_points
        .iter()
        .all(|p| p.0.is_finite() && p.1.is_finite() && p.2.is_finite())
    {
        return None;
    }
    Some((kept, new_points, triangles))
}

/// Census one part's point runs and merge every admitted grid mesh.
pub fn scan_part(data: &[u8]) -> GridScan {
    let region_list = regions(data);
    let block = region_list.first().map(|(blk, _)| *blk);
    let mut carriers = 0usize;
    let mut shaped = 0usize;
    let mut meshed = 0usize;
    let mut refused = 0usize;
    let mut relaxed = 0usize;
    let mut refusals: BTreeMap<String, usize> = BTreeMap::new();
    let mut duplicate_grids = 0usize;
    let mut station_rows = 0usize;
    let mut columns = 0usize;
    let mut monotone_grids = 0usize;
    let mut points_count = 0usize;
    let mut vertices: Vec<(f64, f64, f64)> = Vec::new();
    let mut triangles: Vec<(u32, u32, u32)> = Vec::new();
    let mut seen: Vec<Vec<(f64, f64, f64)>> = Vec::new();
    for run in iter_runs(data) {
        carriers += 1;
        let Some(shape) = run.shape else {
            continue;
        };
        shaped += 1;
        if seen.contains(&run.points) {
            duplicate_grids += 1;
            continue;
        }
        seen.push(run.points.clone());
        let (cell_triangles, reason, monotone) = admit(&run.points, shape, run.kind);
        let Some(cells) = cell_triangles else {
            refused += 1;
            let key = reason.unwrap_or(REFUSE_DEGENERATE).to_string();
            let relaxable = matches!(
                reason,
                Some(REFUSE_STALLED_STATIONS)
                    | Some(REFUSE_STALLED_COLUMNS)
                    | Some(REFUSE_DEGENERATE)
            );
            let relaxed_result = if relaxable {
                relaxed_triangles(&run.points, shape)
            } else {
                None
            };
            if let Some((kept_rows, new_points, relaxed_cells)) = relaxed_result {
                let base = vertices.len() as u32;
                let mut merged = triangles.clone();
                merged.extend(
                    relaxed_cells
                        .iter()
                        .map(|&(a, b, c)| (a + base, b + base, c + base)),
                );
                let merged_manifold = vertices.is_empty() || mesh::mesh_stats(&merged).manifold;
                if mesh::mesh_stats(&relaxed_cells).manifold && merged_manifold {
                    relaxed += 1;
                    station_rows += kept_rows.len();
                    columns += shape.cols;
                    points_count += new_points.len();
                    if monotone {
                        monotone_grids += 1;
                    }
                    vertices.extend(new_points.iter().copied());
                    triangles.extend(
                        relaxed_cells
                            .iter()
                            .map(|&(a, b, c)| (a + base, b + base, c + base)),
                    );
                }
            }
            *refusals.entry(key).or_insert(0) += 1;
            continue;
        };
        meshed += 1;
        station_rows += shape.rows;
        columns += shape.cols;
        points_count += run.points.len();
        if monotone {
            monotone_grids += 1;
        }
        let base = vertices.len() as u32;
        vertices.extend(run.points.iter().copied());
        triangles.extend(
            cells
                .iter()
                .map(|&(a, b, c)| (a + base, b + base, c + base)),
        );
    }
    GridScan {
        block,
        carriers,
        shaped,
        meshed,
        refused,
        refusals,
        duplicate_grids,
        station_rows,
        columns,
        monotone_grids,
        points: points_count,
        vertices,
        triangles,
        relaxed,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn grid_points(rows: usize, cols: usize) -> Vec<(f64, f64, f64)> {
        let mut points = Vec::new();
        for i in 0..rows {
            for j in 0..cols {
                points.push((10.0 * i as f64, 8.0 * j as f64, 2.0 * i as f64));
            }
        }
        points
    }

    fn push_f64(out: &mut Vec<u8>, value: f64) {
        out.extend_from_slice(&value.to_le_bytes());
    }

    fn record(out: &mut Vec<u8>, cls: u16, payload: &[u8]) {
        out.extend_from_slice(&E5_MARKER);
        out.push(3);
        out.extend_from_slice(&cls.to_le_bytes());
        out.extend_from_slice(&(payload.len() as u32).to_le_bytes());
        out.extend_from_slice(&100u32.to_le_bytes());
        out.extend_from_slice(payload);
    }

    fn part_data(stalled: bool) -> Vec<u8> {
        let rows = if stalled { 5 } else { 4 };
        let mut points = Vec::new();
        for i in 0..rows {
            let source = if stalled && i == rows - 1 { i - 1 } else { i };
            for j in 0..5 {
                points.push((10.0 * source as f64, 8.0 * j as f64, 2.0 * source as f64));
            }
        }
        let mut payload = Vec::new();
        for point in &points {
            push_f64(&mut payload, point.0);
            push_f64(&mut payload, point.1);
            push_f64(&mut payload, point.2);
        }
        let mut data = vec![0u8; 32];
        data.extend_from_slice(b"\x34\x12CATStorageProperty");
        data.extend(std::iter::repeat_n(0u8, 10));
        data.extend_from_slice(b"CATUnicodeString");
        data.extend_from_slice(b"\xa0\x02\x00\x00\x00\x00\x34");
        data.push(10);
        data.extend_from_slice(b"CATPrtCont");
        data.extend(std::iter::repeat_n(0u8, 64));
        record(&mut data, 0x00E7, &payload);
        record(&mut data, 0x0018, &[1, 2, 3, 4]);
        record(&mut data, 0x0018, &[5, 6, 7, 8]);
        data
    }

    #[test]
    fn fit_shape_pins_the_largest_row_length() {
        let shape = fit_shape(&grid_points(4, 5)).unwrap();
        assert_eq!((shape.rows, shape.cols), (4, 5));
        let shape = fit_shape(&grid_points(5, 4)).unwrap();
        assert_eq!((shape.rows, shape.cols), (5, 4));
        // A single row is not a grid.
        let row: Vec<(f64, f64, f64)> = (0..9).map(|j| (0.0, j as f64, 0.0)).collect();
        assert!(fit_shape(&row).is_none());
    }

    #[test]
    fn scan_part_meshes_the_synthetic_grid() {
        let scan = scan_part(&part_data(false));
        assert_eq!(scan.carriers, 1);
        assert_eq!(scan.shaped, 1);
        assert_eq!(scan.meshed, 1);
        assert_eq!(scan.refused, 0);
        assert_eq!(scan.points, 20);
        assert_eq!(scan.vertices.len(), 20);
        assert_eq!(scan.triangles.len(), 24);
        let stats = mesh::mesh_stats(&scan.triangles);
        assert!(stats.manifold);
        assert!(!stats.closed);
        assert!(stats.boundary_edges > 0);
    }

    #[test]
    fn stalled_station_rows_relax_to_the_real_grid() {
        let scan = scan_part(&part_data(true));
        assert_eq!(scan.shaped, 1);
        assert_eq!(scan.meshed, 0);
        assert_eq!(scan.relaxed, 1);
        assert_eq!(scan.refusals.get(REFUSE_STALLED_STATIONS).copied(), Some(1));
        // the sentinel row collapses: the real 4x5 net triangulates (#59)
        assert!(scan.has_mesh());
        assert_eq!(scan.station_rows, 4);
        assert_eq!(scan.columns, 5);
        assert_eq!(scan.points, 20);
        assert_eq!(scan.triangles.len(), 24);
        let stats = mesh::mesh_stats(&scan.triangles);
        assert!(stats.manifold);
    }

    #[test]
    fn degenerate_cells_skip_instead_of_refusing() {
        // a 3x3 net with one coincident corner pair (p4 := p3): cells
        // (0,0) and (1,0) become zero-area (b==c, a==d) and drop; the
        // other two cells and all nine points stand (#59)
        let mut holed = grid_points(3, 3);
        holed[4] = holed[3];
        let shape = GridShape {
            rows: 3,
            cols: 3,
            station_axis: 0,
            spread: 0.0,
        };
        let (kept, new_points, triangles) = relaxed_triangles(&holed, shape).unwrap();
        assert_eq!(kept, vec![0, 1, 2]);
        assert_eq!(new_points.len(), 9);
        assert_eq!(triangles.len(), 4); // 4 cells = 8 triangles, 2 cells drop
        let stats = mesh::mesh_stats(&triangles);
        assert!(stats.manifold);
    }

    #[test]
    fn relaxed_triangles_unit_laws() {
        // collapse: only near-duplicate station rows fold, the rest stand
        let mut stalled = grid_points(5, 5);
        let tail: Vec<(f64, f64, f64)> = stalled[15..20].to_vec();
        stalled[20..25].clone_from_slice(&tail);
        let shape = GridShape {
            rows: 5,
            cols: 5,
            station_axis: 0,
            spread: 0.0,
        };
        let (kept, new_points, triangles) = relaxed_triangles(&stalled, shape).unwrap();
        assert_eq!(kept, vec![0, 1, 2, 3]);
        assert_eq!(new_points.len(), 20);
        assert_eq!(triangles.len(), 24);
        // a grid of identical rows collapses below MIN_ROWS: None
        let mut flat = grid_points(4, 4);
        let head: Vec<(f64, f64, f64)> = flat[0..4].to_vec();
        for row in 1..4 {
            flat[row * 4..(row + 1) * 4].clone_from_slice(&head);
        }
        assert!(
            relaxed_triangles(
                &flat,
                GridShape {
                    rows: 4,
                    cols: 4,
                    station_axis: 0,
                    spread: 0.0,
                }
            )
            .is_none()
        );
    }

    #[test]
    fn prefix_fit_requires_monotone_uniform_stations() {
        // The same net as a prefix run: monotone, so it meshes.
        let points = grid_points(4, 5);
        let (triangles, reason, monotone) =
            admit(&points, fit_shape(&points).unwrap(), KIND_PREFIX);
        assert!(reason.is_none());
        assert!(monotone);
        assert_eq!(triangles.unwrap().len(), 24);
        // A 360-degree sweep is non-monotone: the prefix fallback refuses.
        let mut ring = Vec::new();
        for i in 0..8 {
            let angle = std::f64::consts::PI * i as f64 / 4.0;
            for j in 0..4 {
                ring.push((angle.cos() * 10.0, angle.sin() * 10.0, j as f64));
            }
        }
        let shape = fit_shape(&ring).unwrap();
        let (triangles, reason, monotone) = admit(&ring, shape, KIND_PREFIX);
        assert_eq!(reason, Some(REFUSE_NON_MONOTONE));
        assert!(!monotone);
        assert!(triangles.is_none());
    }
}
