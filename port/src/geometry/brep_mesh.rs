//! The B-rep meshing lane of the W2 marathon round — the port twin of
//! the Python reference module ``catpart.geometry.brep_mesh``
//! (``src/catpart/geometry/brep_mesh.py``).
//!
//! First committed content: the **counts-less ``0x49`` triangle-record
//! family** — the population behind the official 211 ``empty-mesh``
//! parts' biggest store (``PalmDown5motors2``: 171,916 of its 171,978
//! unresolved facet candidates parse here with zero rejects). The
//! family law, the fail-closed gates and the NOT-WIRED decision mirror
//! the Python twin's module docs verbatim; the mapping-refutation
//! measurements and the reopening criterion live there and in
//! ``docs/evidence/marathon/w2-progress.md``.
//!
//! Law (W2 census 2026-11-22, corpus-measured): header ``01 49 ty ff``
//! (4 B), ``u32le n`` with ``n == 3*ty``, 12 B f32le unit normal
//! (|n-1| <= 1e-6), ``3*ty`` u16be big-endian references, no counts
//! table — loop ``i`` is ``refs[3i:3i+3]``, one triangle per loop; the
//! record's end stays inside the span. ``ty`` is capped at 16 (T65's
//! base cap; the corpus measures 1..5).

/// The family's marker byte.
pub const MARKER: u8 = 0x49;
/// Structural bound on ``ty`` (T65's base cap; corpus measures 1..5).
pub const MAX_TY: u8 = 16;
/// The unit-normal bar (BR2-06: 54,265/54,265 corpus within 1e-6).
pub const UNIT_NORM_TOL: f64 = 1e-6;

const HEADER: usize = 4; // 01 49 ty ff
const N_BYTES: usize = 4; // u32le n
const NORMAL: usize = 12; // 3 x f32le

/// One counts-less ``0x49`` triangle record, structurally valid.
///
/// ``refs`` are raw big-endian u16 values in the store's reference
/// space (the composite element space on composite stores — the
/// mapping into pool positions is the open question this module
/// documents, never asserted).
#[derive(Debug, Clone, PartialEq)]
pub struct CountlessTriangleRecord {
    pub offset: usize,
    pub ty: u8,
    pub n: u32,
    pub normal: [f32; 3],
    pub refs: Vec<u16>,
    pub end: usize,
}

/// Parse one counts-less ``0x49`` triangle record at ``o``.
///
/// Fail-closed: ``None`` unless the header form, the ``n == 3*ty``
/// law, the 12-byte unit normal and the record's byte extent all hold.
/// The references' VALUES are not bounds-checked (the caller supplies
/// the reference-space bound); the record's byte extent is.
pub fn parse_countsless_record(
    data: &[u8],
    o: usize,
    body_hi: usize,
) -> Option<CountlessTriangleRecord> {
    if o + HEADER > body_hi {
        return None;
    }
    if data[o] != 0x01 || data[o + 1] != MARKER || data[o + 3] != 0xFF {
        return None;
    }
    let ty = data[o + 2];
    if ty == 0 || ty > MAX_TY {
        return None;
    }
    if o + HEADER + N_BYTES > body_hi {
        return None;
    }
    let n = u32::from_le_bytes([data[o + 4], data[o + 5], data[o + 6], data[o + 7]]);
    if n != 3 * ty as u32 {
        return None;
    }
    let end = o + HEADER + N_BYTES + NORMAL + 2 * n as usize;
    if end > body_hi {
        return None;
    }
    let nx = f32::from_le_bytes([data[o + 8], data[o + 9], data[o + 10], data[o + 11]]);
    let ny = f32::from_le_bytes([data[o + 12], data[o + 13], data[o + 14], data[o + 15]]);
    let nz = f32::from_le_bytes([data[o + 16], data[o + 17], data[o + 18], data[o + 19]]);
    let norm = (nx as f64).hypot(ny as f64).hypot(nz as f64);
    if !norm.is_finite() || (norm - 1.0).abs() > UNIT_NORM_TOL {
        return None;
    }
    let base = o + HEADER + N_BYTES + NORMAL;
    let refs = (0..n as usize)
        .map(|j| u16::from_be_bytes([data[base + 2 * j], data[base + 2 * j + 1]]))
        .collect();
    Some(CountlessTriangleRecord {
        offset: o,
        ty,
        n,
        normal: [nx, ny, nz],
        refs,
        end,
    })
}

/// The family census over ``[lo, hi)``: candidates, accepted records
/// and the named reject classes (unit-normal, span-fit). Mirrors the
/// Python twin's :func:`census_family`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct FamilyCensus {
    pub candidates: usize,
    pub records: usize,
    pub unit_normal_rejects: usize,
    pub span_fit_rejects: usize,
}

/// The ``STRIP_RE`` header positions in ``[lo, hi)``: ``01 [41-4f] . ff``.
fn strip_header_positions(data: &[u8], lo: usize, hi: usize) -> Vec<usize> {
    let mut out = Vec::new();
    if hi < 4 {
        return out;
    }
    let mut p = lo;
    while p + 4 <= hi {
        if data[p] == 0x01 && (0x41..=0x4f).contains(&data[p + 1]) && data[p + 3] == 0xFF {
            out.push(p);
            p += 1;
        } else {
            p += 1;
        }
    }
    out
}

/// Census the counts-less ``0x49`` family over ``[lo, hi)``. Read-only;
/// candidates inside an accepted record's extent are not re-counted.
pub fn census_family(data: &[u8], lo: usize, hi: usize) -> FamilyCensus {
    let positions = strip_header_positions(data, lo, hi);
    let mut records = 0usize;
    let mut unit_rejects = 0usize;
    let mut fit_rejects = 0usize;
    let mut skip_until = 0usize;
    for &o in &positions {
        if o < skip_until {
            continue;
        }
        if data[o] != 0x01 || data[o + 1] != MARKER || data[o + 3] != 0xFF {
            continue;
        }
        let ty = data[o + 2];
        if ty == 0 || ty > MAX_TY || o + HEADER + N_BYTES > hi {
            continue;
        }
        let n = u32::from_le_bytes([data[o + 4], data[o + 5], data[o + 6], data[o + 7]]);
        if n != 3 * ty as u32 {
            continue;
        }
        let end = o + HEADER + N_BYTES + NORMAL + 2 * n as usize;
        if end > hi {
            fit_rejects += 1;
            continue;
        }
        let nx = f32::from_le_bytes([data[o + 8], data[o + 9], data[o + 10], data[o + 11]]);
        let ny = f32::from_le_bytes([data[o + 12], data[o + 13], data[o + 14], data[o + 15]]);
        let nz = f32::from_le_bytes([data[o + 16], data[o + 17], data[o + 18], data[o + 19]]);
        let norm = (nx as f64).hypot(ny as f64).hypot(nz as f64);
        if !norm.is_finite() || (norm - 1.0).abs() > UNIT_NORM_TOL {
            unit_rejects += 1;
            continue;
        }
        records += 1;
        skip_until = end;
    }
    FamilyCensus {
        candidates: positions.len(),
        records,
        unit_normal_rejects: unit_rejects,
        span_fit_rejects: fit_rejects,
    }
}

/// The family's triangle reading: loop ``i`` = ``refs[3i:3i+3]``, one
/// triangle per loop, vertex order as stored.
pub fn record_triangles(rec: &CountlessTriangleRecord) -> Vec<[u16; 3]> {
    (0..rec.ty as usize)
        .map(|i| [rec.refs[3 * i], rec.refs[3 * i + 1], rec.refs[3 * i + 2]])
        .collect()
}

// --- the deterministic 2D ear clipper --------------------------------------
//
// The route's polygon triangulator for planar boundary-cycle loops
// (0x4c rings and any future correctly-mapped polygon loop). Scope and
// determinism contract mirror the Python twin's doc verbatim: ONE
// simple polygon (no holes — named open), caller-validated
// coplanarity; the projection drops the largest-|component| normal
// axis (ties toward the earlier axis in x, y, z order); orientation
// from the f64 shoelace sign (zero area refuses); ears are strict
// convex (cross > 0) with no reflex vertex boundary-inclusively inside
// the candidate triangle; the FIRST ear in index order clips — exact
// f64 comparisons only, no numeric tie-breaks.

/// The loop's Newell normal (f64; the f32 coordinates widen once, then
/// f64 throughout — the twin's exact arithmetic).
fn newell_normal_2d(points: &[[f64; 3]]) -> [f64; 3] {
    let (mut nx, mut ny, mut nz) = (0.0f64, 0.0f64, 0.0f64);
    let n = points.len();
    for i in 0..n {
        let a = points[i];
        let b = points[(i + 1) % n];
        nx += (a[1] - b[1]) * (a[2] + b[2]);
        ny += (a[2] - b[2]) * (a[0] + b[0]);
        nz += (a[0] - b[0]) * (a[1] + b[1]);
    }
    [nx, ny, nz]
}

/// The (u, v) projection axes: drop the largest-|component| axis
/// (ties break toward the earlier axis).
fn project_axes(normal: &[f64; 3]) -> (usize, usize) {
    let comps = [normal[0].abs(), normal[1].abs(), normal[2].abs()];
    let mut drop = 0usize;
    for axis in 1..3 {
        if comps[axis] > comps[drop] {
            drop = axis;
        }
    }
    let axes: Vec<usize> = (0..3).filter(|&a| a != drop).collect();
    (axes[0], axes[1])
}

fn cross2(o: [f64; 2], a: [f64; 2], b: [f64; 2]) -> f64 {
    (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
}

/// Boundary-inclusive containment (the ear test's blocker rule).
fn point_in_tri(p: [f64; 2], a: [f64; 2], b: [f64; 2], c: [f64; 2]) -> bool {
    let d1 = cross2(a, b, p);
    let d2 = cross2(b, c, p);
    let d3 = cross2(c, a, p);
    let has_neg = d1 < 0.0 || d2 < 0.0 || d3 < 0.0;
    let has_pos = d1 > 0.0 || d2 > 0.0 || d3 > 0.0;
    !(has_neg && has_pos)
}

/// Triangulate one simple planar polygon loop, deterministically.
///
/// ``point_indices`` is the loop's vertex sequence into ``points`` (3D
/// coordinate triples, caller-validated coplanar); returns the
/// triangles in the loop's winding, or ``None`` on a degenerate loop
/// (fewer than 3 vertices, repeated indices, zero projected area, no
/// ear found). O(n^3) worst case; a numeric pathology fails closed.
pub fn clip_planar_loop(point_indices: &[usize], points: &[[f32; 3]]) -> Option<Vec<[usize; 3]>> {
    let n = point_indices.len();
    if n < 3 {
        return None;
    }
    let mut seen = std::collections::HashSet::new();
    if point_indices.iter().any(|i| !seen.insert(*i)) {
        return None;
    }
    let coords: Vec<[f64; 3]> = point_indices
        .iter()
        .map(|&i| {
            [
                points[i][0] as f64,
                points[i][1] as f64,
                points[i][2] as f64,
            ]
        })
        .collect();
    let normal = newell_normal_2d(&coords);
    let (u, v) = project_axes(&normal);
    let mut poly2d: Vec<[f64; 2]> = coords.iter().map(|c| [c[u], c[v]]).collect();
    let area2 = (0..n)
        .map(|i| cross2([0.0, 0.0], poly2d[i], poly2d[(i + 1) % n]))
        .sum::<f64>()
        / 2.0;
    if area2 == 0.0 {
        return None;
    }
    let order: Vec<usize> = if area2 < 0.0 {
        poly2d.reverse();
        point_indices.iter().rev().copied().collect()
    } else {
        point_indices.to_vec()
    };
    let mut out: Vec<[usize; 3]> = Vec::new();
    let mut idx: Vec<usize> = (0..n).collect();
    let mut guard = 0usize;
    while idx.len() > 3 {
        guard += 1;
        if guard > n * n {
            return None; // numeric pathology; fail-closed, never loop
        }
        let mut clipped = false;
        let m = idx.len();
        for k in 0..m {
            let i0 = idx[(k + m - 1) % m];
            let i1 = idx[k];
            let i2 = idx[(k + 1) % m];
            let a = poly2d[i0];
            let b = poly2d[i1];
            let c = poly2d[i2];
            if cross2(a, b, c) <= 0.0 {
                continue; // reflex or collinear: not an ear
            }
            let mut blocker = false;
            for &j in &idx {
                if j == i0 || j == i1 || j == i2 {
                    continue;
                }
                if point_in_tri(poly2d[j], a, b, c) {
                    blocker = true;
                    break;
                }
            }
            if blocker {
                continue;
            }
            out.push([order[i0], order[i1], order[i2]]);
            idx.remove(k);
            clipped = true;
            break;
        }
        if !clipped {
            return None; // no ear found: self-intersecting input
        }
    }
    out.push([order[idx[0]], order[idx[1]], order[idx[2]]]);
    Some(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// One valid ty=1 record: `01 49 01 ff | n=3 | unit normal | 3 u16be refs`.
    fn valid_record(refs: [u16; 3]) -> Vec<u8> {
        let mut b = vec![0x01, 0x49, 0x01, 0xFF];
        b.extend_from_slice(&3u32.to_le_bytes());
        // a genuinely unit normal: (0, 0, 1)
        b.extend_from_slice(&0f32.to_le_bytes());
        b.extend_from_slice(&0f32.to_le_bytes());
        b.extend_from_slice(&1f32.to_le_bytes());
        for r in refs {
            b.extend_from_slice(&r.to_be_bytes());
        }
        b
    }

    #[test]
    fn valid_ty1_record_parses() {
        let buf = valid_record([10, 20, 30]);
        let rec = parse_countsless_record(&buf, 0, buf.len()).expect("parses");
        assert_eq!(rec.ty, 1);
        assert_eq!(rec.n, 3);
        assert_eq!(rec.refs, vec![10, 20, 30]);
        assert_eq!(rec.end, 26);
        assert_eq!(record_triangles(&rec), vec![[10, 20, 30]]);
    }

    #[test]
    fn non_unit_normal_refused() {
        let mut buf = valid_record([1, 2, 3]);
        buf[8..12].copy_from_slice(&2f32.to_le_bytes()); // |n| = 2
        assert!(parse_countsless_record(&buf, 0, buf.len()).is_none());
    }

    #[test]
    fn wrong_n_law_refused() {
        let mut buf = valid_record([1, 2, 3]);
        buf[4..8].copy_from_slice(&4u32.to_le_bytes()); // n != 3*ty
        assert!(parse_countsless_record(&buf, 0, buf.len()).is_none());
    }

    #[test]
    fn ty_over_cap_refused() {
        // ty = 17 with n = 51 would need 102 ref bytes; the header gate
        // fires first on MAX_TY.
        let mut buf = vec![0x01, 0x49, 17, 0xFF];
        buf.extend_from_slice(&51u32.to_le_bytes());
        buf.extend_from_slice(&[0u8; 12]);
        buf.extend_from_slice(&[0u8; 102]);
        assert!(parse_countsless_record(&buf, 0, buf.len()).is_none());
    }

    #[test]
    fn truncation_refused() {
        let buf = valid_record([1, 2, 3]);
        assert!(parse_countsless_record(&buf, 0, buf.len() - 1).is_none());
        assert!(parse_countsless_record(&buf, 0, 10).is_none());
    }

    #[test]
    fn wrong_marker_refused() {
        let mut buf = valid_record([1, 2, 3]);
        buf[1] = 0x4A;
        assert!(parse_countsless_record(&buf, 0, buf.len()).is_none());
        buf[1] = 0x49;
        buf[3] = 0x00; // form byte
        assert!(parse_countsless_record(&buf, 0, buf.len()).is_none());
    }

    #[test]
    fn ty2_record_is_two_loops() {
        let mut b = vec![0x01, 0x49, 0x02, 0xFF];
        b.extend_from_slice(&6u32.to_le_bytes());
        b.extend_from_slice(&0f32.to_le_bytes());
        b.extend_from_slice(&0f32.to_le_bytes());
        b.extend_from_slice(&1f32.to_le_bytes());
        for r in [1u16, 2, 3, 4, 5, 6] {
            b.extend_from_slice(&r.to_be_bytes());
        }
        let rec = parse_countsless_record(&b, 0, b.len()).expect("parses");
        assert_eq!(record_triangles(&rec), vec![[1, 2, 3], [4, 5, 6]]);
    }

    #[test]
    fn census_counts_and_skips_overlaps() {
        let mut buf = valid_record([1, 2, 3]);
        buf.extend_from_slice(&valid_record([4, 5, 6])); // tiles at 26 B
        let c = census_family(&buf, 0, buf.len());
        assert_eq!(c.candidates, 2);
        assert_eq!(c.records, 2);
        assert_eq!(c.unit_normal_rejects, 0);
        assert_eq!(c.span_fit_rejects, 0);
        // a truncated record past the span counts as span-fit reject
        let c2 = census_family(&buf, 0, buf.len() - 2);
        assert_eq!(c2.records, 1);
        assert_eq!(c2.span_fit_rejects, 1);
    }

    // --- the deterministic 2D ear clipper -----------------------------------
    //
    // The pinned fixtures mirror tests/test_brep_mesh.py one to one —
    // the expected triangle sequences below were derived from the
    // Python implementation and asserted verbatim here (the parity bar
    // for the unwired component).

    const SQUARE: [[f32; 3]; 4] = [
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [1.0, 1.0, 0.0],
        [0.0, 1.0, 0.0],
    ];
    const CONCAVE: [[f32; 3]; 6] = [
        [0.0, 0.0, 0.0],
        [4.0, 0.0, 0.0],
        [4.0, 4.0, 0.0],
        [2.0, 4.0, 0.0],
        [2.0, 1.0, 0.0],
        [0.0, 1.0, 0.0],
    ];
    const STAR: [[f32; 3]; 8] = [
        [0.0, -2.0, 0.0],
        [0.6, -0.6, 0.0],
        [2.0, 0.0, 0.0],
        [0.6, 0.6, 0.0],
        [0.0, 2.0, 0.0],
        [-0.6, 0.6, 0.0],
        [-2.0, 0.0, 0.0],
        [-0.6, -0.6, 0.0],
    ];

    #[test]
    fn clip_convex_square() {
        let tris = clip_planar_loop(&[0, 1, 2, 3], &SQUARE).expect("clips");
        assert_eq!(tris, vec![[3, 0, 1], [1, 2, 3]]);
    }

    #[test]
    fn clip_concave_polygon_pinned() {
        let tris = clip_planar_loop(&[0, 1, 2, 3, 4, 5], &CONCAVE).expect("clips");
        assert_eq!(tris, vec![[5, 0, 1], [1, 2, 3], [1, 3, 4], [1, 4, 5]]);
    }

    #[test]
    fn clip_star_polygon_pinned() {
        let tris = clip_planar_loop(&[0, 1, 2, 3, 4, 5, 6, 7], &STAR).expect("clips");
        assert_eq!(
            tris,
            vec![
                [7, 0, 1],
                [7, 1, 2],
                [7, 2, 3],
                [7, 3, 4],
                [7, 4, 5],
                [5, 6, 7],
            ]
        );
    }

    #[test]
    fn clip_normalizes_winding() {
        let tris = clip_planar_loop(&[3, 2, 1, 0], &SQUARE).expect("clips");
        assert_eq!(tris, vec![[3, 0, 1], [1, 2, 3]]);
    }

    #[test]
    fn clip_refuses_degenerate_inputs() {
        assert!(clip_planar_loop(&[0, 1], &SQUARE).is_none());
        assert!(clip_planar_loop(&[0, 1, 2, 0], &SQUARE).is_none());
        let collinear = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]];
        assert!(clip_planar_loop(&[0, 1, 2], &collinear).is_none());
    }

    #[test]
    fn clip_non_planar_still_triangulates_in_projection() {
        let tilted = [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 1.0],
            [1.0, 1.0, 1.0],
            [0.0, 1.0, 0.0],
        ];
        let tris = clip_planar_loop(&[0, 1, 2, 3], &tilted).expect("clips");
        assert_eq!(tris, vec![[0, 3, 2], [2, 1, 0]]);
    }

    #[test]
    fn clip_result_is_manifold_local() {
        let tris = clip_planar_loop(&[0, 1, 2, 3, 4, 5, 6, 7], &STAR).expect("clips");
        assert_eq!(tris.len(), 6); // n - 2
        let mut undirected: std::collections::HashMap<[usize; 2], usize> =
            std::collections::HashMap::new();
        for tri in &tris {
            for e in [[tri[0], tri[1]], [tri[1], tri[2]], [tri[2], tri[0]]] {
                let mut key = e;
                key.sort();
                *undirected.entry(key).or_insert(0) += 1;
            }
        }
        assert!(undirected.values().all(|&v| v <= 2));
    }
}
