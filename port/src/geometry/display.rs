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
//! - no triangle, no weld, no inferred join.  The summary block says
//!   ``surface = false`` and the warning class is ``no-surface-display``.
//!
//! Fail-closed: a malformed record (short payload, non-finite or
//! out-of-envelope field, failed direction/length law) contributes
//! nothing and is counted as skipped; a part with no displayable carrier
//! keeps its pre-display classification.
//!
//! Numeric contract (spec §2.2): f64 decode arithmetic in the twin's
//! expression order; the single ``f64 -> f32`` narrowing is the viewer
//! array precision and is applied through ``as f32`` (round to nearest),
//! the same narrowing the twin performs with ``struct.pack("<f")``.
#![allow(clippy::suboptimal_flops)]

use std::collections::BTreeMap;

use super::grid;

/// The summary block's honesty labels (the twin's ``KIND``/``SURFACE``).
pub const KIND: &str = "decoded-carriers";
pub const SURFACE: bool = false;

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
    pub points: Vec<(f64, f64, f64)>,
    pub segments: Vec<(u32, u32)>,
}

impl DisplayScan {
    pub fn has_carriers(&self) -> bool {
        !self.points.is_empty()
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
    regions.sort_unstable();
    regions.dedup();
    regions
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
        points,
        segments,
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
}
