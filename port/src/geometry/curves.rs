//! The curve-entry (U4) skip-slot coordinate law and the ``33 3X``
//! curve records — the twin of ``catpart/geometry/curves.py`` (A4,
//! W16, marathon wave 4, 2026-11-22).
//!
//! Every claim in the Python twin's module header is measured there
//! (evidence: ``docs/evidence/marathon/w16-progress.md`` + the stage-4a
//! note).  The law set:
//!
//! - **U4-D (dup-prev, established)**: a skip slot's coordinates are
//!   the bit-exact coordinates of its immediately preceding written
//!   element; the unpinnable class is empty on the targets (Motor 0/5,616,
//!   Audi R8 0/13,788, Vulcan 0/445,719).  The port's emission-side
//!   consumption of the law is ``vote::dup_pin_map``; this module
//!   carries the law's pure measurement surface (pin all skips, the
//!   coplanarity battery, the degenerate split).
//! - **Hypothesis 1 (offset into neighbouring curve records) refuted
//!   as a source, confirmed as corroboration**: the ``33 3X`` records
//!   are per-curve (18-30 B), not per-slot; the ring cross-check ties
//!   them to the same curves the dup copies tile.
//! - **Hypothesis 2 (inline compressed coordinate) refuted**: the
//!   point region consumes exactly the declared write count.
//! - **The A4 lever (degenerate split)**: a dup-pinned loop one of
//!   whose strip triangles collapses (the writer's degenerate-quad
//!   convention, ``(P, X, P, Y)`` = triangle ``(X, P, Y)``) yields its
//!   real triangles under the G3 F7 skip-degenerate convention —
//!   measured recoverable: Motor 121 triangles / 5,534 mm², Audi R8
//!   (see the CSV), Vulcan 22,421 triangles / 19.0M mm² gross.

/// Loop-coplanarity tolerance (twin: ``curves.PLANE_TOL`` /
/// ``vote::PLANE_TOL``).
pub const PLANE_TOL: f64 = 2e-3;

/// |distance(vertex, center) - |r|| tolerance for the ring
/// cross-check (f32 rounding; twin: ``curves.R_TOL``).
pub const R_TOL: f64 = 5e-3;

use super::composite::Element;

/// An f64 coordinate triple (the port's element-space point shape).
pub type Point = (f64, f64, f64);

/// A parsed ``33 3X`` record (twin: ``parse_curve_records``).
#[derive(Debug, Clone, PartialEq)]
pub struct CurveRecord {
    pub off: usize,
    pub fam: u8,
    pub a: u8,
    pub b: u8,
    pub id: u16,
    pub len: usize,
    pub payload: Vec<u8>,
}

fn be_f32(bytes: &[u8]) -> f32 {
    f32::from_be_bytes([bytes[0], bytes[1], bytes[2], bytes[3]])
}

/// Every ``33 3X`` record behind its 7-B header in ``data[lo..hi)``
/// (the stage-4a decoder's walker and sanity rule: known family,
/// plausible length, finite pool-scale leading coordinates on the
/// BE-float families).
pub fn parse_curve_records(data: &[u8], lo: usize, hi: usize) -> Vec<CurveRecord> {
    const FAMILIES: [u8; 5] = [0x32, 0x33, 0x36, 0x37, 0x38];
    let mut out = Vec::new();
    let mut p = lo;
    while p + 9 < hi {
        if data[p] == 0x33 && FAMILIES.contains(&data[p + 1]) {
            let ln = u16::from_le_bytes([data[p - 2], data[p - 1]]) as usize;
            let fam = data[p + 1];
            if ln > 0 && ln <= 256 && p + 2 + ln <= data.len() {
                let pay = data[p + 2..p + 2 + ln].to_vec();
                let mut ok = true;
                if matches!(fam, 0x33 | 0x37 | 0x38) {
                    let nbe = ((ln - 2) / 4).min(4);
                    for i in 0..nbe {
                        let v = be_f32(&pay[i * 4..i * 4 + 4]);
                        ok &= v.is_finite() && v.abs() < 1e7;
                    }
                }
                if ok {
                    out.push(CurveRecord {
                        off: p,
                        fam,
                        a: data[p - 7],
                        b: data[p - 6],
                        id: u16::from_le_bytes([data[p - 5], data[p - 4]]),
                        len: ln,
                        payload: pay,
                    });
                    p += 2 + ln;
                    continue;
                }
            }
        }
        p += 1;
    }
    out
}

/// ``(cx, cy, cz, r)`` of a ``33 37``/``33 33`` record (twin:
/// ``circle_of``); ``None`` for the other families or short payloads.
pub fn circle_of(rec: &CurveRecord) -> Option<(f32, f32, f32, f32)> {
    if !matches!(rec.fam, 0x33 | 0x37) {
        return None;
    }
    let nbe = (rec.len - 2) / 4;
    match rec.fam {
        0x33 if nbe < 6 => None,
        0x37 if nbe < 4 => None,
        0x33 => Some((
            be_f32(&rec.payload[0..4]),
            be_f32(&rec.payload[4..8]),
            be_f32(&rec.payload[8..12]),
            be_f32(&rec.payload[20..24]),
        )),
        _ => Some((
            be_f32(&rec.payload[0..4]),
            be_f32(&rec.payload[4..8]),
            be_f32(&rec.payload[8..12]),
            be_f32(&rec.payload[12..16]),
        )),
    }
}

/// ``(P, Q)`` of a ``33 32`` line record's 40-B f32le ``[P][Q][P]+|Q|``
/// block (twin: ``line_of``); ``None`` otherwise.
pub fn line_of(rec: &CurveRecord) -> Option<([f32; 3], [f32; 3])> {
    if rec.fam != 0x32 || rec.len < 42 {
        return None;
    }
    let le = |i: usize| {
        f32::from_le_bytes([
            rec.payload[i],
            rec.payload[i + 1],
            rec.payload[i + 2],
            rec.payload[i + 3],
        ])
    };
    // the block sits at payload +2 (2-B lead, then 10 f32: P, Q, P, |Q|)
    let at = |k: usize| [le(2 + 12 * k), le(2 + 12 * k + 4), le(2 + 12 * k + 8)];
    Some((at(0), at(1)))
}

/// The U4-D dup law over the whole element space (twin:
/// ``pin_skips``): every skip slot pins to its preceding written
/// element; ``None`` where no preceding write exists (the unpinned
/// class). Returns ``(pins, unpinned)`` with ``pins[i]`` indexed by
/// element position.
pub fn pin_skips(elements: &[Element]) -> (Vec<Option<Point>>, Vec<usize>) {
    let mut pins = vec![None; elements.len()];
    let mut unpinned = Vec::new();
    let mut prev = None;
    for (i, (_v, pt)) in elements.iter().enumerate() {
        if pt.is_some() {
            prev = *pt;
        } else {
            pins[i] = prev;
            if prev.is_none() {
                unpinned.push(i);
            }
        }
    }
    (pins, unpinned)
}

/// Dup-pinned point per loop reference (twin:
/// ``loop_pinned_points``); ``None`` where a reference is
/// out-of-space or its skip is unpinnable (the caller fails that loop
/// closed).
pub fn loop_pinned_points(
    loop_refs: &[u32],
    elements: &[Element],
    pins: &[Option<Point>],
) -> Option<Vec<Point>> {
    let mut pts = Vec::with_capacity(loop_refs.len());
    for &r in loop_refs {
        let idx = r as usize;
        if idx >= elements.len() {
            return None;
        }
        pts.push(elements[idx].1.or(pins[idx])?);
    }
    Some(pts)
}

/// Max |signed distance| of ``points`` from the plane through
/// ``points[0]`` with unit ``normal`` (twin: ``plane_residual``);
/// ``None`` for a zero normal or no points.
pub fn plane_residual(points: &[(f64, f64, f64)], normal: (f64, f64, f64)) -> Option<f64> {
    let nn = (normal.0.powf(2.0) + normal.1.powf(2.0) + normal.2.powf(2.0)).powf(0.5);
    if nn == 0.0 || points.is_empty() {
        return None;
    }
    let p0 = points[0];
    Some(
        points[1..]
            .iter()
            .map(|q| {
                (q.0 - p0.0).abs() * normal.0 / nn
                    + (q.1 - p0.1).abs() * normal.1 / nn
                    + (q.2 - p0.2).abs() * normal.2 / nn
            })
            .fold(0.0_f64, f64::max),
    )
}

/// The weld's battery (twin: ``loop_is_battery_supported``): a
/// normal-less record is accepted untested; a normal-carrying one must
/// be coplanar at [`PLANE_TOL`].
pub fn loop_is_battery_supported(
    normal: Option<(f64, f64, f64)>,
    pinned_points: &[(f64, f64, f64)],
) -> bool {
    match normal {
        None => true,
        Some(n) => matches!(plane_residual(pinned_points, n), Some(res) if res <= PLANE_TOL),
    }
}

/// A loop's triangle POSITIONS under its marker family's emission
/// convention (twin: ``loop_triangles``): strips fan consecutive
/// triples; fans start from position 0.
pub fn loop_triangles(mk: u8, loop_len: usize) -> Vec<(usize, usize, usize)> {
    match mk {
        0x41 | 0x44 | 0x4C => (1..loop_len - 1).map(|i| (0, i, i + 1)).collect(),
        _ => (0..loop_len.saturating_sub(2))
            .map(|i| (i, i + 1, i + 2))
            .collect(),
    }
}

fn tri_is_degenerate(a: (f64, f64, f64), b: (f64, f64, f64), c: (f64, f64, f64)) -> bool {
    if a == b || b == c || a == c {
        return true;
    }
    let (ux, uy, uz) = (b.0 - a.0, b.1 - a.1, b.2 - a.2);
    let (vx, vy, vz) = (c.0 - a.0, c.1 - a.1, c.2 - a.2);
    let (cx, cy, cz) = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx);
    cx == 0.0 && cy == 0.0 && cz == 0.0
}

fn tri_area(a: (f64, f64, f64), b: (f64, f64, f64), c: (f64, f64, f64)) -> f64 {
    let (ux, uy, uz) = (b.0 - a.0, b.1 - a.1, b.2 - a.2);
    let (vx, vy, vz) = (c.0 - a.0, c.1 - a.1, c.2 - a.2);
    let (cx, cy, cz) = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx);
    0.5 * (cx * cx + cy * cy + cz * cz).powf(0.5)
}

/// One split triangle outcome (twin: ``split_loop_triangles``).
#[derive(Debug, Clone, PartialEq)]
pub enum SplitTri {
    /// a real triangle: the element triple and its area
    Real([u32; 3], f64),
    /// a collapsed or unresolvable emission: the element triple
    Degenerate([u32; 3]),
}

/// Dup-pinned emission with the degenerate split (twin:
/// ``split_loop_triangles``): the writer's degenerate-quad collapses
/// split off instead of refusing the loop — the same G3 F7 skip
/// convention the primary strips apply. An unresolvable reference
/// fails its triangles closed (``Degenerate``).
pub fn split_loop_triangles(
    mk: u8,
    loop_refs: &[u32],
    pinned_points: &[Option<(f64, f64, f64)>],
) -> Vec<SplitTri> {
    let mut out = Vec::new();
    for (i, j, k) in loop_triangles(mk, loop_refs.len()) {
        let refs = [loop_refs[i], loop_refs[j], loop_refs[k]];
        let (pa, pb, pc) = (pinned_points[i], pinned_points[j], pinned_points[k]);
        match (pa, pb, pc) {
            (Some(a), Some(b), Some(c)) => {
                if tri_is_degenerate(a, b, c) {
                    out.push(SplitTri::Degenerate(refs));
                } else {
                    out.push(SplitTri::Real(refs, tri_area(a, b, c)));
                }
            }
            _ => out.push(SplitTri::Degenerate(refs)),
        }
    }
    out
}

/// Curve-record corroboration (twin: ``ring_cross_check``): counts the
/// ``33 37`` circles matching a written ring ``(z, radius about the
/// circles' centroid)`` within the f32 tolerances. Returns
/// ``(matched, total)``; ``total`` is 0 without circles.
pub fn ring_cross_check(records: &[CurveRecord], elements: &[Element]) -> (usize, usize) {
    let circles: Vec<_> = records.iter().filter_map(circle_of).collect();
    if circles.is_empty() {
        return (0, 0);
    }
    let n = circles.len() as f32;
    let cx = circles.iter().map(|c| c.0).sum::<f32>() / n;
    let cy = circles.iter().map(|c| c.1).sum::<f32>() / n;
    let mut rings: Vec<(f32, f32)> = Vec::new();
    for (_v, pt) in elements.iter() {
        let pt = match pt {
            Some(p) => *p,
            None => continue,
        };
        let (x, y, z) = (pt.0 as f32, pt.1 as f32, pt.2 as f32);
        let key = (
            (z * 1000.0).round() / 1000.0,
            (((x - cx).powf(2.0) + (y - cy).powf(2.0)).powf(0.5) * 1000.0).round() / 1000.0,
        );
        if !rings.contains(&key) {
            rings.push(key);
        }
    }
    let matched = circles
        .iter()
        .filter(|(_x, _y, cz, r)| {
            rings
                .iter()
                .any(|(zr, rr)| (zr - cz).abs() <= 2e-3 && (rr - r.abs()).abs() <= R_TOL as f32)
        })
        .count();
    (matched, circles.len())
}

#[cfg(test)]
mod tests {
    use super::*;

    const P: (f64, f64, f64) = (0.0, 0.0, 0.0);
    const Q: (f64, f64, f64) = (1.0, 0.0, 0.0);
    const R: (f64, f64, f64) = (0.0, 1.0, 0.0);
    const T: (f64, f64, f64) = (0.5, 0.5, 2.0);

    fn elements_with_skips() -> Vec<(u8, Option<(f64, f64, f64)>)> {
        vec![
            (0, Some(P)),
            (1, None),
            (2, Some(Q)),
            (1, None),
            (1, None),
            (0, Some(R)),
            (1, None),
            (1, None),
            (1, None),
        ]
    }

    #[test]
    fn dup_law_pins_to_preceding_written() {
        let els = elements_with_skips();
        let (pins, unpinned) = pin_skips(&els);
        assert_eq!(pins[1], Some(P));
        assert_eq!(pins[3], Some(Q));
        assert_eq!(pins[4], Some(Q));
        assert_eq!(pins[6], Some(R));
        assert!(unpinned.is_empty());
    }

    #[test]
    fn leading_skip_is_unpinned() {
        let els = vec![(1, None), (0, Some(P)), (1, None)];
        let (pins, unpinned) = pin_skips(&els);
        assert_eq!(pins[0], None);
        assert_eq!(pins[2], Some(P));
        assert_eq!(unpinned, vec![0]);
    }

    #[test]
    fn loop_pinned_points_resolves_and_fails_closed() {
        let els = elements_with_skips();
        let (pins, _) = pin_skips(&els);
        assert_eq!(
            loop_pinned_points(&[0, 1, 2], &els, &pins),
            Some(vec![P, P, Q])
        );
        assert_eq!(loop_pinned_points(&[0, 1, 99], &els, &pins), None);
        let els2 = vec![(1, None), (0, Some(P))];
        let (pins2, _) = pin_skips(&els2);
        assert_eq!(loop_pinned_points(&[0, 1], &els2, &pins2), None);
    }

    #[test]
    fn battery_gates() {
        let normal = Some((0.0, 0.0, 1.0));
        assert!(loop_is_battery_supported(None, &[P, Q, (9.9, 9.9, 9.9)]));
        assert!(loop_is_battery_supported(normal, &[P, Q, R]));
        assert!(!loop_is_battery_supported(
            normal,
            &[P, Q, R, (0.0, 0.0, 50.0)]
        ));
        assert!(!loop_is_battery_supported(
            Some((0.0, 0.0, 0.0)),
            &[P, Q, R]
        ));
    }

    #[test]
    fn strip_quad_and_degenerate_quad_split() {
        // full quad: two real triangles
        let real = split_loop_triangles(0x42, &[0, 1, 2, 3], &[Some(P), Some(Q), Some(T), Some(R)]);
        assert_eq!(
            real.iter()
                .filter(|t| matches!(t, SplitTri::Real(..)))
                .count(),
            2
        );
        // (P, X, P, Y): one collapsed half, one real triangle
        let out = split_loop_triangles(0x42, &[0, 1, 2, 3], &[Some(P), Some(Q), Some(P), Some(T)]);
        assert_eq!(out.len(), 2);
        assert_eq!(out[0], SplitTri::Degenerate([0, 1, 2]));
        assert!(matches!(out[1], SplitTri::Real([1, 2, 3], _)));
    }

    #[test]
    fn fan_split_and_full_collapse() {
        let out = split_loop_triangles(0x4C, &[0, 1, 2, 3], &[Some(P), Some(Q), Some(R), Some(P)]);
        assert!(matches!(out[0], SplitTri::Real([0, 1, 2], _)));
        assert!(matches!(out[1], SplitTri::Degenerate([0, 2, 3])));
        let out2 = split_loop_triangles(0x4C, &[0, 1, 0, 2], &[Some(P), Some(Q), Some(P), Some(R)]);
        assert!(out2.iter().all(|t| matches!(t, SplitTri::Degenerate(..))));
    }

    #[test]
    fn zero_area_cross_product_is_degenerate() {
        let out = split_loop_triangles(
            0x42,
            &[0, 1, 2],
            &[
                Some((0.0, 0.0, 0.0)),
                Some((1.0, 0.0, 0.0)),
                Some((2.0, 0.0, 0.0)),
            ],
        );
        assert_eq!(out, vec![SplitTri::Degenerate([0, 1, 2])]);
    }

    #[test]
    fn unresolvable_reference_fails_closed() {
        let out = split_loop_triangles(0x42, &[0, 1, 2], &[Some(P), Some(Q), None]);
        assert_eq!(out, vec![SplitTri::Degenerate([0, 1, 2])]);
    }

    fn rec(fam: u8, payload: &[u8]) -> Vec<u8> {
        // 7-B header: a b <u16le id> 00 <u16le len>, then 33 fam
        let mut blob = vec![0x01u8, 0x02];
        blob.extend_from_slice(&7u16.to_le_bytes());
        blob.push(0x00);
        blob.extend_from_slice(&(payload.len() as u16).to_le_bytes());
        blob.push(0x33);
        blob.push(fam);
        blob.extend_from_slice(payload);
        blob
    }

    #[test]
    fn circle_record_parses() {
        let mut pay = Vec::new();
        for v in [395.0f32, 435.5, 2.1, 2.78] {
            pay.extend_from_slice(&v.to_be_bytes());
        }
        pay.extend_from_slice(&[0x00, 0x00]);
        let mut blob = vec![0x00u8, 0x08];
        blob.extend(rec(0x37, &pay));
        blob.extend_from_slice(&[0x00, 0x00]);
        let recs = parse_curve_records(&blob, 0, blob.len());
        assert_eq!(recs.len(), 1);
        assert_eq!(recs[0].fam, 0x37);
        assert_eq!(recs[0].len, 18);
        let c = circle_of(&recs[0]).unwrap();
        assert!((c.0 - 395.0).abs() < 1e-4);
        assert!((c.3 - 2.78).abs() < 1e-4);
    }

    #[test]
    fn line_record_parses() {
        let mut pay = vec![0x21u8, 0x43];
        for v in [0.0f32, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0] {
            pay.extend_from_slice(&v.to_le_bytes());
        }
        let blob = rec(0x32, &pay);
        let recs = parse_curve_records(&blob, 0, blob.len());
        assert_eq!(recs.len(), 1);
        let (p, q) = line_of(&recs[0]).unwrap();
        assert_eq!(p, [0.0, 0.0, 0.0]);
        assert_eq!(q, [1.0, 0.0, 0.0]);
    }

    #[test]
    fn garbage_stream_yields_nothing() {
        let blob: Vec<u8> = (0..=255u8).collect();
        assert!(parse_curve_records(&blob, 0, blob.len()).is_empty());
    }

    #[test]
    fn ring_cross_check_matches_written_ring() {
        let mut els = Vec::new();
        for k in 0..8 {
            let ang = 2.0 * std::f64::consts::PI * k as f64 / 8.0;
            els.push((
                0u8,
                Some((395.0 + 2.78 * ang.cos(), 435.5 + 2.78 * ang.sin(), 2.1)),
            ));
        }
        let mut pay = Vec::new();
        for v in [395.0f32, 435.5, 2.1, 2.78] {
            pay.extend_from_slice(&v.to_be_bytes());
        }
        pay.extend_from_slice(&[0x00, 0x00]);
        let mut rec = CurveRecord {
            off: 0,
            fam: 0x37,
            a: 0,
            b: 0,
            id: 0,
            len: pay.len(),
            payload: pay,
        };
        assert_eq!(ring_cross_check(&[rec.clone()], &els), (1, 1));
        rec.payload = vec![0; 18];
        assert_eq!(ring_cross_check(&[rec], &els), (0, 1));
    }

    #[test]
    fn loop_triangles_positions() {
        assert_eq!(loop_triangles(0x42, 4), vec![(0, 1, 2), (1, 2, 3)]);
        assert_eq!(
            loop_triangles(0x4C, 5),
            vec![(0, 1, 2), (0, 2, 3), (0, 3, 4)]
        );
        assert!(loop_triangles(0x42, 2).is_empty());
    }
}
