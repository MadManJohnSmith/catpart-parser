//! The exact-analytic surface availability scanner (W11, marathon B8) —
//! the 1:1 port of the Python twin ``catpart/geometry/analytic.py``
//! (evidence: ``docs/evidence/2026-11-22-w11-analytic-surfaces.md``).
//!
//! The B8 answer is a measured negative on the ``undecoded-variant``
//! population: no evaluable analytic surface record (no per-part
//! ``01 56`` plane object, no cylinder/cone axis+radius block, no
//! NURBS payload, no ``a5 03 34`` frame). This module walks the three
//! streams that could carry such records so the taxonomy is
//! re-derivable per file:
//!
//! - the nested store body's object stream (``<seq u32le>``-prefixed
//!   records: ``ff ff 02 00`` objects, ``ff 03 01 00`` property
//!   definitions, ``14 0c ff ff ff ff ff`` scene records) — the only
//!   analytic shapes are the class-``0x56`` plane objects whose
//!   direction pair is byte-identical in every observed file (the
//!   store's template default), with no parametric bounds;
//! - the ``CATPrtCont`` content bulk under the committed A/B frame law
//!   (bulk-stream §3.1: ``a4+a``/``b1+b`` family bytes, flag ∈
//!   {0x03, 0x13, 0x83}, class byte, length field, retained token);
//! - the NURBS content signatures (the BR5-03 knot/weight detector,
//!   mirrored inline here because the Python twin reuses
//!   ``catpart.brep.cgm_nurbs.nurbs_signatures``, which has no Rust
//!   home yet) and the shipped ``a5 03 34`` frame scan.
//!
//! Detector honesty (as the twin's doc header): the unit-vector shape
//! detector does NOT discriminate intent (an axis frame or rotation
//! pair looks identical), and its phase-census reads alias — the
//! fixed-point-ladder guard removes the measured 2^-k alias family,
//! and the shape census is diagnostic, never verdict-driving. The
//! verdict flips only on law-pinned detections: a per-part plane
//! object, an ``a5 03 34`` surface frame, or a NURBS signature run.

use std::collections::BTreeMap;

use super::store::{CONTAINER_STDCONT, locate_store, valid_blocks};
use super::surface;

pub const VERDICT_NO_ANALYTIC: &str = "no-evaluable-analytic-surface";
pub const VERDICT_ANALYTIC_PRESENT: &str = "analytic-surface-records-present";

/// The store body's template plane payloads (W11: byte-identical in
/// all ten population files and present in passing files' bodies too).
/// Two measured default direction pairs — the Z-normal 45° pair and
/// the Y-normal pair — measured as bytes, not recomputed floats.
pub const TEMPLATE_PLANE_UV: [&[u8]; 2] = [
    &[
        0xf3, 0x04, 0x35, 0x3f, 0xf3, 0x04, 0x35, 0x3f, 0x00, 0x00, 0x00, 0x00, 0xf3, 0x04, 0x35,
        0x3f, 0xf3, 0x04, 0x35, 0xbf,
    ],
    &[
        0xf3, 0x04, 0x35, 0x3f, 0x00, 0x00, 0x00, 0x00, 0xf3, 0x04, 0x35, 0x3f, 0xf3, 0x04, 0x35,
        0xbf, 0x00, 0x00, 0x00, 0x00, 0xf3, 0x04, 0x35, 0x3f,
    ],
];

const OBJECT_HEADER: &[u8] = &[0xff, 0xff, 0x02, 0x00];
const PROPERTY_VALUE_HEADER: &[u8] = &[0x04, 0x04, 0xfd, 0xff];
const SCENE_HEADER: &[u8] = &[0x14, 0x0c, 0xff, 0xff, 0xff, 0xff, 0xff];

const A_FAMILY_BASE: u8 = 0xA4;
const B_FAMILY_BASE: u8 = 0xB1;
const MAX_WIDTH: u8 = 4;
const MAX_PAYLOAD: usize = 1 << 20;
const FLAGS: [u8; 3] = [0x03, 0x13, 0x83];

const KNOT_FLOOR: f64 = 1e-8;
const KNOT_MIN_COUNT: usize = 8;
const KNOT_MIN_DISTINCT: usize = 3;
const KNOT_CHAIN_BAR: f64 = 0.75;

/// One class-``0x56`` object record of the store body object stream.
/// ``start`` is body-relative; ``object_id`` the u32le that follows the
/// ``01 56`` class bytes; ``is_template`` the byte-exact template law
/// (either measured default direction pair).
#[derive(Debug, Clone, PartialEq)]
pub struct PlaneRecord {
    pub start: usize,
    pub object_id: u32,
    pub is_template: bool,
}

/// Diagnostic axis-shape census over phase-census floats (twin's
/// ``ShapeHits``): a repeated template record inflates ``count`` but
/// not ``distinct``.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct ShapeHits {
    pub count: usize,
    pub distinct: usize,
}

/// One A/B frame class census entry of the content bulk.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BulkFrameClass {
    pub family: char,
    pub width: usize,
    pub cls: u8,
    pub count: usize,
    pub payload_bytes: usize,
}

/// One accepted knot-array run (twin's ``KnotRun``).
#[derive(Debug, Clone, PartialEq)]
pub struct KnotRun {
    pub offset: usize,
    pub count: usize,
    pub distinct: usize,
    pub repeats: usize,
    pub lo: f64,
    pub hi: f64,
}

/// The analytic-availability taxonomy of one part (twin's
/// ``AnalyticScan``).
#[derive(Debug, Clone, PartialEq, Default)]
pub struct AnalyticScan {
    pub verdict: &'static str,
    pub store_body_size: Option<usize>,
    pub object_records: usize,
    pub plane_records: Vec<PlaneRecord>,
    pub template_planes: usize,
    pub scene_records: usize,
    pub property_values: usize,
    pub cylinder_candidates: ShapeHits,
    pub cone_candidates: ShapeHits,
    pub nurbs_knot_runs: usize,
    pub nurbs_weight_runs: usize,
    pub a5_surface_frames: usize,
    pub bulk_dialect: Option<&'static str>,
    pub bulk_frame_classes: Vec<BulkFrameClass>,
}

impl AnalyticScan {
    /// Objects carrying a non-template payload (the per-part planes).
    pub fn per_part_planes(&self) -> usize {
        self.plane_records.len() - self.template_planes
    }
}

fn find(haystack: &[u8], needle: &[u8], from: usize, to: usize) -> Option<usize> {
    if needle.is_empty() || from >= to || to > haystack.len() {
        return None;
    }
    let end = to.min(haystack.len());
    let mut pos = from;
    while pos + needle.len() <= end {
        let window = &haystack[pos..pos + needle.len()];
        if window == needle {
            return Some(pos);
        }
        pos += 1;
    }
    None
}

/// The object-stream record spans of a store body (twin's
/// ``_record_spans``): a record starts at one of the three observed
/// headers and ends at the next header (or the body end). An
/// ``ff ff 02 00`` occurrence whose next bytes are not an ``01/07 5X``
/// class pair is dropped so it cannot split a real record.
fn record_boundaries(body: &[u8]) -> Vec<usize> {
    let mut events = Vec::new();
    for header in [OBJECT_HEADER, b"\xff\x03\x01\x00".as_slice(), SCENE_HEADER] {
        let mut pos = 0;
        while let Some(hit) = find(body, header, pos, body.len()) {
            events.push(hit);
            pos = hit + 1;
        }
    }
    events.sort_unstable();
    events.dedup();
    let mut boundaries = Vec::new();
    for start in events {
        if body[start..].starts_with(OBJECT_HEADER) {
            let cls = body.get(start + 4..start + 6);
            let ok = match cls {
                Some(pair) => {
                    (pair[0] == 0x01 || pair[0] == 0x07) && (0x50..=0x58).contains(&pair[1])
                }
                None => false,
            };
            if !ok {
                continue;
            }
        }
        boundaries.push(start);
    }
    boundaries
}

/// The ``01 56`` plane objects in ``body`` (twin's ``plane_records``).
pub fn plane_records(body: &[u8]) -> Vec<PlaneRecord> {
    let boundaries = record_boundaries(body);
    let mut out = Vec::new();
    for i in 0..boundaries.len() {
        let start = boundaries[i];
        let end = boundaries.get(i + 1).copied().unwrap_or(body.len());
        if !body[start..].starts_with(OBJECT_HEADER)
            || body.get(start + 4) != Some(&0x01)
            || body.get(start + 5) != Some(&0x56)
        {
            continue;
        }
        if start + 10 > body.len() {
            continue;
        }
        let object_id = u32::from_le_bytes([
            body[start + 6],
            body[start + 7],
            body[start + 8],
            body[start + 9],
        ]);
        let payload = &body[start + 10..end];
        let is_template = TEMPLATE_PLANE_UV.iter().any(|pattern| {
            payload
                .windows(pattern.len())
                .any(|window| window == *pattern)
        });
        out.push(PlaneRecord {
            start,
            object_id,
            is_template,
        });
    }
    out
}

/// Phase-tolerant f32 census reads (twin's ``_f32_values``): the first
/// finite hit per 4-byte window.
pub fn f32_values(body: &[u8]) -> Vec<f32> {
    let mut out = Vec::new();
    let mut seen: std::collections::HashSet<usize> = std::collections::HashSet::new();
    for off in 0..body.len().saturating_sub(3) {
        let v = f32::from_le_bytes([body[off], body[off + 1], body[off + 2], body[off + 3]]);
        if v == 0.0 || !v.is_finite() {
            continue;
        }
        let a = (v as f64).abs();
        if a < 1e-4 || a >= 1e7 {
            continue;
        }
        if !seen.insert(off / 4) {
            continue;
        }
        out.push(v);
    }
    out
}

fn dyadic(v: f64) -> bool {
    if v <= 0.0 || v >= 1e7 {
        return false;
    }
    let k = v.log2().round();
    (v - 2f64.powf(k)).abs() <= 1e-15 * v.max(1.0)
}

/// The W2 fixed-point-ladder alias: every non-unit axis component an
/// exact 2^-k (twin's ``_fixed_point_alias``).
fn fixed_point_alias(axis: (f64, f64, f64)) -> bool {
    let others: Vec<f64> = [axis.0, axis.1, axis.2]
        .iter()
        .copied()
        .filter(|c| (c.abs() - 1.0).abs() > 1e-9 && *c != 0.0)
        .collect();
    !others.is_empty() && others.iter().all(|c| dyadic(c.abs()))
}

fn is_unit(v: (f64, f64, f64)) -> bool {
    let n = v.0 * v.0 + v.1 * v.1 + v.2 * v.2;
    (0.999..=1.001).contains(&n)
}

/// Axis+radius shape detections over census floats (twin's
/// ``analytic_shape_candidates``): cylinder ``(axis(3), radius)`` and
/// cone ``(axis(3), tan)`` with a unit axis, a positive in-band fourth
/// value, and the fixed-point alias guard. Spheres are not detected
/// (no measured law distinguishes a center from an axis). The census
/// read is candidate-grade and never verdict-driving.
pub fn analytic_shape_candidates(values: &[f32]) -> BTreeMap<&'static str, ShapeHits> {
    let mut cyl: Vec<(f64, f64, f64, f64)> = Vec::new();
    let n = values.len();
    for i in 0..n.saturating_sub(3) {
        let a = (values[i] as f64, values[i + 1] as f64, values[i + 2] as f64);
        let r = values[i + 3] as f64;
        if !(1e-3..1e6).contains(&r) {
            continue;
        }
        if is_unit(a) && !fixed_point_alias(a) {
            cyl.push((a.0, a.1, a.2, r));
        }
    }
    let distinct = cyl
        .iter()
        .map(|t| t.to_bits_tuple())
        .collect::<std::collections::HashSet<_>>()
        .len();
    let hits = ShapeHits {
        count: cyl.len(),
        distinct,
    };
    let mut out = BTreeMap::new();
    out.insert("cylinder", hits);
    out.insert("cone", hits);
    out
}

trait BitsTuple {
    fn to_bits_tuple(&self) -> (u64, u64, u64, u64);
}

impl BitsTuple for (f64, f64, f64, f64) {
    fn to_bits_tuple(&self) -> (u64, u64, u64, u64) {
        (
            self.0.to_bits(),
            self.1.to_bits(),
            self.2.to_bits(),
            self.3.to_bits(),
        )
    }
}

/// One A/B frame at ``pos`` (twin's ``_parse_frame``):
/// ``(family, width, cls, end)`` or ``None`` when it does not close.
pub fn parse_frame(data: &[u8], pos: usize, hi: usize) -> Option<(char, usize, u8, usize)> {
    if pos + 4 > hi || hi > data.len() {
        return None;
    }
    let byte0 = data[pos];
    if byte0 > A_FAMILY_BASE && byte0 <= A_FAMILY_BASE + MAX_WIDTH {
        let width = (byte0 - A_FAMILY_BASE) as usize;
        if pos + 7 + width > hi || !FLAGS.contains(&data[pos + 1]) {
            return None;
        }
        let payload_len =
            u32::from_le_bytes([data[pos + 3], data[pos + 4], data[pos + 5], data[pos + 6]])
                as usize;
        if payload_len > MAX_PAYLOAD {
            return None;
        }
        let end = pos + 7 + width + payload_len;
        if end > hi {
            return None;
        }
        return Some(('A', width, data[pos + 2], end));
    }
    if byte0 > B_FAMILY_BASE && byte0 <= B_FAMILY_BASE + MAX_WIDTH {
        let width = (byte0 - B_FAMILY_BASE) as usize;
        if pos + 4 + width > hi || !FLAGS.contains(&data[pos + 1]) {
            return None;
        }
        let payload_len = data[pos + 3] as usize;
        let end = pos + 4 + width + payload_len;
        if end > hi {
            return None;
        }
        return Some(('B', width, data[pos + 2], end));
    }
    None
}

/// Contiguous A/B frame runs of >= ``min_chain`` frames (twin's
/// ``bulk_clusters``): a run counts when it chains and closes exactly;
/// later clusters resume at the previous end. Returns the cluster
/// spans and the frame-class census (chains below ``min_chain`` do not
/// become clusters but their frames still count, mirroring the twin).
pub fn bulk_clusters(
    data: &[u8],
    lo: usize,
    hi: usize,
) -> (Vec<(usize, usize)>, Vec<BulkFrameClass>) {
    let mut clusters = Vec::new();
    let mut counts: BTreeMap<(char, usize, u8), [usize; 2]> = BTreeMap::new();
    let mut pos = lo;
    while pos + 8 < hi {
        if parse_frame(data, pos, hi).is_none() {
            pos += 1;
            continue;
        }
        let mut chain = 0usize;
        let mut scan = pos;
        while let Some((family, width, cls, end)) = parse_frame(data, scan, hi) {
            chain += 1;
            let entry = counts.entry((family, width, cls)).or_insert([0, 0]);
            entry[0] += 1;
            entry[1] += end - scan;
            scan = end;
        }
        if chain >= 3 {
            clusters.push((pos, scan));
            pos = scan;
        } else {
            pos += 1;
        }
    }
    let classes = counts
        .into_iter()
        .map(|((family, width, cls), count)| BulkFrameClass {
            family,
            width,
            cls,
            count: count[0],
            payload_bytes: count[1],
        })
        .collect();
    (clusters, classes)
}

/// ``(block_start, name, region_end)`` for every storage block (the
/// twin imports ``cgm_nurbs.valid_regions``; the same three-step law
/// built here from the store module).
fn valid_regions(data: &[u8]) -> Vec<(usize, String, usize)> {
    let blocks = valid_blocks(data);
    let d8_outer = if data.len() >= 12 {
        u32::from_be_bytes([data[8], data[9], data[10], data[11]]) as usize
    } else {
        0
    };
    blocks
        .iter()
        .map(|(blk, name)| {
            let rend = super::store::probe_region(*blk, &blocks, d8_outer, data.len());
            (*blk, name.clone(), rend)
        })
        .collect()
}

/// The content dialect word of the ``CATPrtCont`` region (twin's
/// ``_bulk_dialect``): ``object-stream`` on any cluster, ``E5`` on an
/// ``e5 0d`` head marker, ``other`` otherwise; ``None`` without the
/// region.
fn bulk_dialect(data: &[u8]) -> Option<&'static str> {
    for (blk, name, rend) in valid_regions(data) {
        if name != "CATPrtCont" {
            continue;
        }
        let head_end = blk.saturating_add(1024).min(rend).min(data.len());
        let head = &data[blk..head_end];
        let (clusters, _) = bulk_clusters(data, blk, rend);
        if !clusters.is_empty() {
            return Some("object-stream");
        }
        if find(head, b"\xe5\x0d", 0, head.len()).is_some() {
            return Some("E5");
        }
        return Some("other");
    }
    None
}

/// Runs of >= ``minimum`` consecutive exact f64 ``1.0`` (twin's
/// ``_weight_runs``); ``(offset, count)`` pairs.
pub fn weight_runs(data: &[u8], lo: usize, hi: usize, minimum: usize) -> Vec<(usize, usize)> {
    const ONE: [u8; 8] = 1.0f64.to_le_bytes();
    let mut runs = Vec::new();
    let mut pos = lo;
    loop {
        let i = match find(data, &ONE, pos, hi) {
            Some(i) => i,
            None => return runs,
        };
        let mut j = i;
        while j + 8 <= hi && data[j..j + 8] == ONE {
            j += 8;
        }
        let count = (j - i) / 8;
        if count >= minimum {
            runs.push((i, count));
        }
        pos = j.max(i + 1);
    }
}

/// Share of consecutive f64 words chaining as a u32le array (twin's
/// ``_chain_fraction``) — the anti-alias guard's discriminating edge.
fn chain_fraction(words: &[[u8; 8]]) -> f64 {
    if words.len() < 2 {
        return 0.0;
    }
    let chained = words
        .windows(2)
        .filter(|pair| pair[0][4..8] == pair[1][0..4])
        .count();
    chained as f64 / (words.len() - 1) as f64
}

fn accept_knot_run(data: &[u8], run_start: usize, run_end: usize) -> Option<KnotRun> {
    let count = (run_end - run_start) / 8;
    if count < KNOT_MIN_COUNT {
        return None;
    }
    let mut vals = Vec::with_capacity(count);
    for k in 0..count {
        let off = run_start + k * 8;
        vals.push(f64::from_le_bytes([
            data[off],
            data[off + 1],
            data[off + 2],
            data[off + 3],
            data[off + 4],
            data[off + 5],
            data[off + 6],
            data[off + 7],
        ]));
    }
    let mut distinct_vals = vals.clone();
    distinct_vals.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    distinct_vals.dedup();
    let distinct = distinct_vals.len();
    if distinct < KNOT_MIN_DISTINCT || count - distinct < 1 {
        return None;
    }
    let words: Vec<[u8; 8]> = (0..count)
        .map(|k| {
            let off = run_start + k * 8;
            let mut w = [0u8; 8];
            w.copy_from_slice(&data[off..off + 8]);
            w
        })
        .collect();
    if chain_fraction(&words) >= KNOT_CHAIN_BAR {
        return None;
    }
    Some(KnotRun {
        offset: run_start,
        count,
        distinct,
        repeats: count - distinct,
        lo: vals[0],
        hi: vals[count - 1],
    })
}

/// The knot-array runs of ``[lo, hi)`` at the shipped phases (twin's
/// ``_knot_runs``, all-defaults policy: phases (0, 2, 4, 6), floor
/// 1e-8, >= 8 count, >= 3 distinct, >= 1 repeat, chain guard, overlap
/// suppression).
pub fn knot_runs(data: &[u8], lo: usize, hi: usize) -> Vec<KnotRun> {
    let mut accepted: Vec<KnotRun> = Vec::new();
    for phase in [0usize, 2, 4, 6] {
        // the twin's start law: lo + ((phase - lo) % 8), Python's
        // always-positive modulo
        let start = lo + ((phase as isize - lo as isize).rem_euclid(8)) as usize;
        let n = hi.saturating_sub(start) / 8;
        let mut run_start: Option<usize> = None;
        let mut prev: Option<f64> = None;
        for idx in 0..=n {
            if idx < n {
                let off = start + idx * 8;
                let v = f64::from_le_bytes([
                    data[off],
                    data[off + 1],
                    data[off + 2],
                    data[off + 3],
                    data[off + 4],
                    data[off + 5],
                    data[off + 6],
                    data[off + 7],
                ]);
                let ok = v.is_finite()
                    && (v == 0.0 || v >= KNOT_FLOOR)
                    && v < 1e7
                    && prev.is_none_or(|p| v >= p - 1e-9);
                if ok {
                    if run_start.is_none() {
                        run_start = Some(off);
                    }
                    prev = Some(v);
                    continue;
                }
            }
            if let Some(rs) = run_start
                && let Some(cand) = accept_knot_run(data, rs, start + idx * 8)
            {
                let overlaps = accepted.iter().any(|r| {
                    r.offset < cand.offset + cand.count * 8 && cand.offset < r.offset + r.count * 8
                });
                if !overlaps {
                    accepted.push(cand);
                }
            }
            run_start = None;
            prev = None;
        }
    }
    accepted
}

/// The NURBS content signatures over ``[lo, hi)`` (twin reuses
/// ``cgm_nurbs.nurbs_signatures``): knot runs + weight runs.
pub fn nurbs_signatures(data: &[u8], lo: usize, hi: usize) -> (Vec<KnotRun>, Vec<(usize, usize)>) {
    (knot_runs(data, lo, hi), weight_runs(data, lo, hi, 4))
}

fn store_body_span(data: &[u8]) -> Option<(usize, usize)> {
    let blocks = valid_blocks(data);
    let stdcont = blocks
        .iter()
        .find(|(_, name)| name == "CATStdCont")
        .map(|(blk, _)| *blk)?;
    let d8_outer = if data.len() >= 12 {
        u32::from_be_bytes([data[8], data[9], data[10], data[11]]) as usize
    } else {
        0
    };
    let fallback = || -> Option<(usize, usize)> {
        let index = blocks.iter().position(|(b, _)| *b == stdcont)?;
        let next = blocks.get(index + 1).map(|(b, _)| *b).unwrap_or(data.len());
        Some((stdcont, next))
    };
    match locate_store(data, stdcont, &blocks, d8_outer, CONTAINER_STDCONT) {
        Ok(Some(span)) => Some((span.body_lo, span.body_hi)),
        _ => fallback(),
    }
}

fn add_shape(
    mut total: BTreeMap<&'static str, ShapeHits>,
    extra: BTreeMap<&'static str, ShapeHits>,
) -> BTreeMap<&'static str, ShapeHits> {
    for (key, hits) in extra {
        let entry = total.entry(key).or_default();
        entry.count += hits.count;
        entry.distinct += hits.distinct;
    }
    total
}

/// Classify one part's analytic-surface availability (twin's
/// ``scan_part``).
pub fn scan_part(data: &[u8]) -> AnalyticScan {
    let mut scan = AnalyticScan {
        verdict: VERDICT_NO_ANALYTIC,
        ..Default::default()
    };
    let mut shape: BTreeMap<&'static str, ShapeHits> = BTreeMap::new();
    shape.insert("cylinder", ShapeHits::default());
    shape.insert("cone", ShapeHits::default());
    let mut knot_total = 0usize;
    let mut weight_total = 0usize;
    if let Some((body_lo, body_hi)) = store_body_span(data) {
        scan.store_body_size = Some(body_hi - body_lo);
        let body = &data[body_lo..body_hi];
        scan.plane_records = plane_records(body);
        scan.template_planes = scan.plane_records.iter().filter(|p| p.is_template).count();
        for start in record_boundaries(body) {
            if body[start..].starts_with(OBJECT_HEADER) {
                scan.object_records += 1;
            } else if body[start..].starts_with(SCENE_HEADER) {
                scan.scene_records += 1;
            }
        }
        let mut pos = 0;
        while let Some(hit) = find(body, PROPERTY_VALUE_HEADER, pos, body.len()) {
            scan.property_values += 1;
            pos = hit + 1;
        }
        let values = f32_values(body);
        shape = add_shape(shape, analytic_shape_candidates(&values));
        let (knots, weights) = nurbs_signatures(data, body_lo, body_hi);
        knot_total += knots.len();
        weight_total += weights.len();
    }
    scan.bulk_dialect = bulk_dialect(data);
    for (blk, name, rend) in valid_regions(data) {
        if name != "CATPrtCont" {
            continue;
        }
        let (clusters, classes) = bulk_clusters(data, blk, rend);
        scan.bulk_frame_classes = classes;
        let mut bulk_values: Vec<f32> = Vec::new();
        for (cl_start, cl_end) in clusters {
            let mut scan_pos = cl_start;
            while scan_pos < cl_end {
                match parse_frame(data, scan_pos, cl_end) {
                    Some((_, _, _, end)) => {
                        bulk_values.extend(f32_values(&data[scan_pos..end]));
                        scan_pos = end;
                    }
                    None => break,
                }
            }
        }
        shape = add_shape(shape, analytic_shape_candidates(&bulk_values));
        let (knots, weights) = nurbs_signatures(data, blk, rend);
        knot_total += knots.len();
        weight_total += weights.len();
        break;
    }
    scan.cylinder_candidates = shape["cylinder"];
    scan.cone_candidates = shape["cone"];
    scan.nurbs_knot_runs = knot_total;
    scan.nurbs_weight_runs = weight_total;
    scan.a5_surface_frames = surface::candidate_frames(data).len();
    let analytic_present = scan.per_part_planes() > 0
        || knot_total > 0
        || weight_total > 0
        || scan.a5_surface_frames > 0;
    scan.verdict = if analytic_present {
        VERDICT_ANALYTIC_PRESENT
    } else {
        VERDICT_NO_ANALYTIC
    };
    scan
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::f32::consts::FRAC_1_SQRT_2;

    /// One ``01 56`` object record laid out as the corpus measures it.
    fn plane_body(object_id: u32, payload: &[u8]) -> Vec<u8> {
        let mut body = Vec::new();
        body.extend_from_slice(&[0xff, 0xff, 0x02, 0x00, 0x01, 0x56]);
        body.extend_from_slice(&object_id.to_le_bytes());
        body.extend_from_slice(&[0u8; 14]);
        body.extend_from_slice(payload);
        body.extend_from_slice(&[0x00, 0x00, 0x14, 0x04, 0xff, 0xff, 0xff, 0xff, 0xff]);
        body
    }

    fn f32s(values: &[f32]) -> Vec<u8> {
        values.iter().flat_map(|v| v.to_le_bytes()).collect()
    }

    fn f64s(values: &[f64]) -> Vec<u8> {
        values.iter().flat_map(|v| v.to_le_bytes()).collect()
    }

    #[test]
    fn the_measured_template_pair_flags_a_plane() {
        let mut body = vec![0u8; 8];
        body.extend(plane_body(
            34,
            &f32s(&[
                FRAC_1_SQRT_2,
                FRAC_1_SQRT_2,
                0.0,
                FRAC_1_SQRT_2,
                -FRAC_1_SQRT_2,
                0.0,
                15.0,
            ]),
        ));
        let records = plane_records(&body);
        assert_eq!(records.len(), 1);
        assert_eq!(records[0].object_id, 34);
        assert!(records[0].is_template);
    }

    #[test]
    fn the_second_measured_template_pair_flags_too() {
        let body = plane_body(
            67,
            &f32s(&[
                FRAC_1_SQRT_2,
                0.0,
                FRAC_1_SQRT_2,
                -FRAC_1_SQRT_2,
                0.0,
                FRAC_1_SQRT_2,
                10.0,
            ]),
        );
        let records = plane_records(&body);
        assert_eq!(records.len(), 1);
        assert!(records[0].is_template);
    }

    #[test]
    fn a_different_unit_pair_is_per_part() {
        let body = plane_body(7, &f32s(&[0.6, 0.8, 0.0, 0.8, -0.6, 0.0, 3.5]));
        let records = plane_records(&body);
        assert_eq!(records.len(), 1);
        assert!(!records[0].is_template);
    }

    #[test]
    fn a_coincidental_object_header_does_not_split_a_record() {
        let mut payload = vec![0xff, 0xff, 0x02, 0x00, 0x09, 0x09];
        payload.extend(f32s(&[
            FRAC_1_SQRT_2,
            FRAC_1_SQRT_2,
            0.0,
            FRAC_1_SQRT_2,
            -FRAC_1_SQRT_2,
            0.0,
            15.0,
        ]));
        let body = plane_body(1, &payload);
        let records = plane_records(&body);
        assert_eq!(records.len(), 1);
        assert!(records[0].is_template);
    }

    #[test]
    fn a_real_unit_axis_with_radius_is_accepted() {
        let hits = analytic_shape_candidates(&[0.6f32, 0.8, 0.0, 5.0]);
        assert_eq!(hits["cylinder"].count, 1);
        assert_eq!(hits["cylinder"].distinct, 1);
        assert_eq!(hits["cone"].count, 1);
    }

    #[test]
    fn the_fixed_point_alias_family_is_refused() {
        // the measured 550.000 alias: exact 2^-k components + 1.0
        let ladder = [
            2f32.powi(-13),
            1.0,
            2f32.powi(-11),
            1.0,
            2f32.powi(-13),
            1.0,
            2f32.powi(-11),
            1.0,
        ];
        let hits = analytic_shape_candidates(&f32_values(&f32s(&ladder)));
        assert_eq!(hits["cylinder"].count, 0);
        assert_eq!(hits["cone"].count, 0);
    }

    #[test]
    fn repeated_tuples_inflate_count_not_distinct() {
        let values = [0.6f32, 0.8, 0.0, 5.0, 0.6, 0.8, 0.0, 5.0];
        let hits = analytic_shape_candidates(&values);
        assert_eq!(hits["cylinder"].count, 2);
        assert_eq!(hits["cylinder"].distinct, 1);
    }

    fn a_frame(payload: &[u8]) -> Vec<u8> {
        let mut frame = vec![0xA5, 0x03, 0x34];
        frame.extend_from_slice(&(payload.len() as u32).to_le_bytes());
        frame.push(0x0f);
        frame.extend_from_slice(payload);
        frame
    }

    fn b_frame(payload: &[u8]) -> Vec<u8> {
        let mut frame = vec![0xB2, 0x03, 0x06, payload.len() as u8, 0x5A];
        frame.extend_from_slice(payload);
        frame
    }

    #[test]
    fn both_frame_families_close() {
        let a = a_frame(b"payload");
        let parsed = parse_frame(&a, 0, a.len()).expect("the A frame closes");
        assert_eq!((parsed.0, parsed.1, parsed.2), ('A', 1, 0x34));
        assert_eq!(parsed.3, a.len());
        let b = b_frame(b"xy");
        let parsed = parse_frame(&b, 0, b.len()).expect("the B frame closes");
        assert_eq!((parsed.0, parsed.1, parsed.2), ('B', 1, 0x06));
        assert_eq!(parsed.3, b.len());
    }

    #[test]
    fn the_b1_family_byte_is_refused() {
        assert!(parse_frame(&[0xb1, 0x03, 0x06, 0x02, 0x5A, b'x', b'y'], 0, 7).is_none());
    }

    #[test]
    fn clusters_need_three_chained_frames() {
        let mut stream = Vec::new();
        stream.extend(b_frame(b"ab"));
        stream.extend(b_frame(b"cd"));
        stream.extend(b_frame(b"ef"));
        let (clusters, classes) = bulk_clusters(&stream, 0, stream.len());
        assert_eq!(clusters, vec![(0, stream.len())]);
        assert_eq!(classes.iter().map(|c| c.count).sum::<usize>(), 3);
    }

    #[test]
    fn a_two_frame_run_is_not_a_cluster() {
        let mut stream = Vec::new();
        stream.extend(b_frame(b"ab"));
        stream.extend(b_frame(b"cd"));
        stream.extend_from_slice(&[0u8; 4]);
        let (clusters, _) = bulk_clusters(&stream, 0, stream.len());
        assert!(clusters.is_empty());
    }

    #[test]
    fn a_real_knot_vector_is_accepted() {
        // 10 knots, non-decreasing, 5 distinct values, 5 repeats
        let data = f64s(&[0.0, 0.0, 0.25, 0.5, 0.5, 0.75, 1.0, 1.0, 1.0, 1.0]);
        let runs = knot_runs(&data, 0, data.len());
        assert_eq!(runs.len(), 1);
        assert_eq!(runs[0].count, 10);
        assert_eq!(runs[0].distinct, 5);
        assert_eq!(runs[0].repeats, 5);
    }

    #[test]
    fn a_short_or_uniform_run_is_refused() {
        let short = f64s(&[0.1, 0.2, 0.3]);
        assert!(knot_runs(&short, 0, short.len()).is_empty());
        let uniform = f64s(&[0.5; 10]);
        assert!(knot_runs(&uniform, 0, uniform.len()).is_empty());
    }

    #[test]
    fn weight_runs_need_four_ones() {
        let three = f64s(&[1.0, 1.0, 1.0]);
        let four = f64s(&[1.0, 1.0, 1.0, 1.0]);
        assert!(weight_runs(&three, 0, three.len(), 4).is_empty());
        assert_eq!(weight_runs(&four, 0, four.len(), 4), vec![(0, 4)]);
    }

    #[test]
    fn the_denormal_band_is_excluded() {
        // (0, 1e-8) values alias integer index arrays; with both halves
        // below the 8-value bar nothing qualifies
        let denorm = f64s(&[0.0, 1e-9, 0.25, 0.5, 0.5, 0.75, 1.0, 1.0, 1.0]);
        assert!(knot_runs(&denorm, 0, denorm.len()).is_empty());
        // the same vector without the denormal qualifies
        let clean = f64s(&[0.0, 0.25, 0.5, 0.5, 0.75, 1.0, 1.0, 1.0]);
        assert_eq!(knot_runs(&clean, 0, clean.len()).len(), 1);
    }

    #[test]
    fn the_u32_chain_alias_is_refused() {
        // a u32le array misread as f64 chains: word k's high half equals
        // word k+1's low half (the anti-alias guard's edge, mirrored
        // from the Python twin's fixture)
        let halves: [u32; 16] = [
            0x11111111, 0x41600000, 0x41600000, 0x4163D70A, 0x4163D70A, 0x4167AE14, 0x4167AE14,
            0x416B851F, 0x416B851F, 0x416F5C28, 0x416F5C28, 0x416F5C29, 0x416F5C29, 0x416F5C2A,
            0x416F5C2A, 0x416F5C2B,
        ];
        let data: Vec<u8> = halves.iter().flat_map(|v| v.to_le_bytes()).collect();
        assert!(knot_runs(&data, 0, data.len()).is_empty());
    }

    #[test]
    fn the_two_template_pairs_are_distinct_measured_bytes() {
        assert_ne!(TEMPLATE_PLANE_UV[0], TEMPLATE_PLANE_UV[1]);
    }
}
