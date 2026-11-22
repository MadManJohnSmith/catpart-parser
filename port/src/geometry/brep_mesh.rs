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
}
