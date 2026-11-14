//! The nested store's vertex pool (G2 model) — the port of the Python
//! reference module ``catpart.geometry.pool``
//! (``src/catpart/geometry/pool.py``), per spec §2.1 of
//! ``docs/specs/phase5-viewer-spec.md`` (G2, the ``01 06`` groups).
//!
//! Adapted from ``scripts/triage/decode_vertex_pool.py`` /
//! ``decode_facet_semantics.py`` (G2/G3's corpus decoders) with the
//! decode semantics unchanged; the triage scripts stay the analysis
//! tools (ticket #32). The behavior is mirrored 1:1 including the
//! fail-closed arms: a walked count differing from the count field
//! raises ``malformed-pool-group`` (P2g — broken structure, not a
//! variant) and non-finite coordinates raise ``malformed-pool-vertex``
//! (P3). The docstring citations below are the twin's.
//!
//! Model (docs/evidence/2026-11-09-vertex-pool.md):
//!
//! - Pool groups are opened by the 8-byte wrapper ``10 24 04 ff ff 00
//!   00 00`` followed by the sub-kind ``01 06`` and a vertex count: one
//!   byte when it fits (<= 255), else ``ff`` escaping to a u32le count
//!   at +11 (P1g). The 15-byte vertex records ``[05 08 01][f32le x]
//!   [f32le y][f32le z]`` follow contiguously and the walked record
//!   count equals the count field on every corpus group (P2/P2g,
//!   2,090/2,090 = 1.000) — a mismatch is broken structure, not a
//!   variant, and raises ``malformed-pool-group``.
//! - Coordinates are little-endian float32 triplets, one vertex per
//!   record, interleaved (P3); 100% of corpus vertices are finite, so
//!   non-finite values raise ``malformed-pool-vertex``.
//! - Other sub-kinds after the same wrapper mark the composite index
//!   space: ``01 02`` groups are the 6-byte edge table (F8), ``ff ..``
//!   wrappers open the trailer-named region — stores carrying either
//!   use a larger, undecoded reference space (G3 open question 1).
//!
//! The exporter consumes the flattened pool of all groups in body
//! order — G3's soup convention (``pool = [v for g in pools for v in
//! g]``).
//!
//! NUMERIC CONTRACT (spec §2.2 — the Fidelity keystone): the vertex
//! records load as **f32 and widen to f64 ONCE, here at load** (the
//! twin's ``struct.unpack('<fff')`` yields Python floats holding exact
//! f32 widenings). Every downstream value is an f64 derived from these
//! or from integers; all arithmetic is f64, never f32 — an f32
//! rounding at a different point flips exact-equality decisions. The
//! one finite check (the twin's ``math.isfinite`` at pool.py:89) runs
//! on the widened values (widening preserves NaN/inf).
//!
//! Evidence (the same citations the twin's docstring carries):
//!
//! - ``docs/evidence/2026-11-09-vertex-pool.md`` (the G2 model: the
//!   ``01 06`` groups, P1g/P2/P2g/P3, the composite-space sub-kinds)
//!
//! Numeric contract (spec §2.2 point 3): decode module — the
//! ``clippy::suboptimal_flops`` allow below is the pinned carve-out
//! (mul_add changes rounding and flips exact-equality decisions); see
//! the crate docs in ``../lib.rs`` for the full policy.
#![allow(clippy::suboptimal_flops)]

use super::errors::ExportError;
use super::store::find_all;

/// The group wrapper (twin: :data:`catpart.geometry.pool.FULL_WRAP`).
pub const FULL_WRAP: &[u8; 8] = b"\x10\x24\x04\xff\xff\x00\x00\x00";
/// The vertex-record prefix (twin: :data:`catpart.geometry.pool.VREC`).
pub const VREC: &[u8; 3] = b"\x05\x08\x01";
/// The pool sub-kind (twin: :data:`catpart.geometry.pool.POOL_SUBKIND`).
pub const POOL_SUBKIND: &[u8; 2] = b"\x01\x06";
/// The edge-table sub-kind (twin: :data:`catpart.geometry.pool.EDGE_SUBKIND`).
pub const EDGE_SUBKIND: &[u8; 2] = b"\x01\x02";

/// G2's sanity cap on the count field (twin: ``MAX_COUNT``).
pub const MAX_COUNT: u32 = 1_000_000;

/// One decoded ``01 06`` pool group (P1g/P2g) — the twin's
/// :class:`catpart.geometry.pool.PoolGroup` dataclass (frozen). The
/// vertices are the widened f64 triplets (the one f32 -> f64 widening
/// point, spec §2.2).
#[derive(Debug, Clone, PartialEq)]
pub struct PoolGroup {
    /// The group wrapper's body offset.
    pub offset: usize,
    /// The group's count field (the P1g escape resolved).
    pub count_field: u32,
    /// The walked vertices, in record order.
    pub vertices: Vec<(f64, f64, f64)>,
}

/// Decode every pool group in the store body — the twin's
/// :func:`catpart.geometry.pool.scan_pool_groups`.
///
/// Returns ``(groups, kinds)`` where ``kinds`` lists the sub-kind
/// bytes found after every ``10 24 04 ff ff 00 00 00`` wrapper
/// (``01 06`` = pool, ``01 02`` = edge group, ``ff ..`` = trailer
/// opener) in body order — the composite-index-space markers of G3
/// claim F8. A kind entry shorter than two bytes mirrors the twin's
/// clamped slice at the body's edge.
///
/// Raises ``malformed-pool-group`` when a group's walked vertex-record
/// count differs from its count field (P2g violation) and
/// ``malformed-pool-vertex`` on non-finite coordinates (P3 violation).
pub fn scan_pool_groups(
    data: &[u8],
    body_lo: usize,
    body_hi: usize,
) -> Result<(Vec<PoolGroup>, Vec<Vec<u8>>), ExportError> {
    let mut groups: Vec<PoolGroup> = Vec::new();
    let mut kinds: Vec<Vec<u8>> = Vec::new();
    for o in find_all(data, FULL_WRAP, body_lo, body_hi) {
        let sub_kind = super::store::slice_clamped(data, o + 8, o + 10).to_vec();
        kinds.push(sub_kind.clone());
        if sub_kind != POOL_SUBKIND {
            continue;
        }
        let b10 = data[o + 10]; // past-EOF here is the twin's IndexError (an unclassified crash)
        let (cnt, mut q) = if b10 == 0xFF {
            if o + 15 > body_hi {
                continue; // G2: an insane wrapper is not an established group
            }
            let cnt = u32::from_le_bytes([data[o + 11], data[o + 12], data[o + 13], data[o + 14]]);
            (cnt, o + 15)
        } else {
            (u32::from(b10), o + 11)
        };
        if !(1..=MAX_COUNT).contains(&cnt) || q + 15 * cnt.min(4) as usize > body_hi {
            continue; // G2's count sanity: not an established group
        }
        let mut vertices: Vec<(f64, f64, f64)> = Vec::new();
        while vertices.len() < cnt as usize && q + 15 <= body_hi && data[q..q + 3] == VREC[..] {
            // THE widening point (spec §2.2): f32 load, exact widen to
            // f64 once; everything downstream is f64.
            let x = f32::from_le_bytes([data[q + 3], data[q + 4], data[q + 5], data[q + 6]]) as f64;
            let y =
                f32::from_le_bytes([data[q + 7], data[q + 8], data[q + 9], data[q + 10]]) as f64;
            let z =
                f32::from_le_bytes([data[q + 11], data[q + 12], data[q + 13], data[q + 14]]) as f64;
            if !(x.is_finite() && y.is_finite() && z.is_finite()) {
                return Err(ExportError::new(
                    super::errors::MALFORMED_POOL_VERTEX,
                    format!(
                        "pool group at {o}: non-finite f32le coordinate at \
                         vertex record {} (G2 P3: 100% finite corpus-wide)",
                        vertices.len()
                    ),
                ));
            }
            vertices.push((x, y, z));
            q += 15;
        }
        if vertices.len() != cnt as usize {
            return Err(ExportError::new(
                super::errors::MALFORMED_POOL_GROUP,
                format!(
                    "pool group at {o}: count field {cnt} but walked {} \
                     vertex records (G2 P2g: the count field is a true \
                     count, 2,090/2,090 corpus groups walk exactly)",
                    vertices.len()
                ),
            ));
        }
        groups.push(PoolGroup {
            offset: o,
            count_field: cnt,
            vertices,
        });
    }
    Ok((groups, kinds))
}

/// True when an ``01 02`` edge group or trailer opener marks the
/// composite index space (G3 F8: references run beyond the pool there;
/// the numbering is open, question 1) — the twin's
/// :func:`catpart.geometry.pool.has_composite_space`.
pub fn has_composite_space(kinds: &[Vec<u8>]) -> bool {
    kinds
        .iter()
        .any(|k| k == EDGE_SUBKIND || k.first() == Some(&0xff))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The fixture generator's pool group shape: wrapper + sub-kind +
    /// one-byte count + 15-byte vertex records.
    fn pool_group(count: u32, vertices: &[(f32, f32, f32)]) -> Vec<u8> {
        let mut bytes = Vec::new();
        bytes.extend_from_slice(FULL_WRAP);
        bytes.extend_from_slice(POOL_SUBKIND);
        if count < 0xFF {
            bytes.push(count as u8);
        } else {
            bytes.push(0xFF);
            bytes.extend_from_slice(&count.to_le_bytes());
        }
        for &(x, y, z) in vertices {
            bytes.extend_from_slice(VREC);
            bytes.extend_from_slice(&x.to_le_bytes());
            bytes.extend_from_slice(&y.to_le_bytes());
            bytes.extend_from_slice(&z.to_le_bytes());
        }
        bytes
    }

    #[test]
    fn walks_the_canonical_group_and_widens_once() {
        let vertices = [
            (0.0f32, 0.0f32, 0.0f32),
            (20.0, 0.0, 0.0),
            (0.0, 100.0, 0.0),
            (20.0, 100.0, 60.0),
        ];
        let data = pool_group(4, &vertices);
        let (groups, kinds) = scan_pool_groups(&data, 0, data.len()).unwrap();
        assert_eq!(kinds, vec![POOL_SUBKIND.to_vec()]);
        assert_eq!(groups.len(), 1);
        let group = &groups[0];
        assert_eq!(group.count_field, 4);
        assert_eq!(group.offset, 0);
        // Widened f64 values equal the f32 widenings exactly.
        assert_eq!(group.vertices[3], (20.0f64, 100.0f64, 60.0f64));
    }

    #[test]
    fn count_field_mismatch_raises_malformed_pool_group() {
        // Count says 4, only 3 records present, with facet territory
        // following inside the body (the G2 P2g violation — the
        // fixture's geometry-truncated-pool shape: the count sanity
        // window (q + 15 * min(cnt, 4)) must fit the body, so the
        // truncated group is established before the walk falls short).
        let mut data = pool_group(4, &[(0.0, 0.0, 0.0), (20.0, 0.0, 0.0), (0.0, 100.0, 0.0)]);
        data.extend_from_slice(&[0x77u8; 80]); // facet territory follows
        let err = scan_pool_groups(&data, 0, data.len()).unwrap_err();
        assert_eq!(err.error_class, "malformed-pool-group");
        assert!(err.detail.contains("count field 4 but walked 3"));
    }

    #[test]
    fn non_finite_coordinate_raises_malformed_pool_vertex() {
        let nan = f32::NAN;
        let data = pool_group(2, &[(0.0, 0.0, 0.0), (nan, 1.0, 2.0)]);
        let err = scan_pool_groups(&data, 0, data.len()).unwrap_err();
        assert_eq!(err.error_class, "malformed-pool-vertex");
        assert!(err.detail.contains("vertex record 1"));
    }

    #[test]
    fn ff_escaped_count_and_insane_wrappers() {
        // P1g: a count above 255 escapes through ff + u32le at +11.
        let vertices: Vec<(f32, f32, f32)> = (0..256).map(|i| (i as f32, 0.0, 0.0)).collect();
        let data = pool_group(256, &vertices);
        let (groups, _) = scan_pool_groups(&data, 0, data.len()).unwrap();
        assert_eq!(groups.len(), 1);
        assert_eq!(groups[0].count_field, 256);
        assert_eq!(groups[0].vertices.len(), 256);
        // An insane wrapper (count window past body_hi) is not an
        // established group: skipped, the kind still recorded.
        let mut data = pool_group(300, &vertices[..8]);
        data[10] = 0xFF;
        data[11..15].copy_from_slice(&1_000_001u32.to_le_bytes()); // > MAX_COUNT
        let (groups, kinds) = scan_pool_groups(&data, 0, data.len()).unwrap();
        assert!(groups.is_empty());
        assert_eq!(kinds, vec![POOL_SUBKIND.to_vec()]);
    }

    #[test]
    fn non_pool_subkinds_mark_the_composite_space() {
        let mut data = pool_group(2, &[(0.0, 0.0, 0.0), (1.0, 2.0, 3.0)]);
        // An `01 02` edge group after the same wrapper (G3 F8).
        data.extend_from_slice(FULL_WRAP);
        data.extend_from_slice(EDGE_SUBKIND);
        data.extend_from_slice(&[0x02, 0x02, 0x00, 0x01, 0x00, 0x02]);
        // A trailer opener (ff ..) after that.
        data.extend_from_slice(FULL_WRAP);
        data.extend_from_slice(&[0xff, 0x00]);
        let (groups, kinds) = scan_pool_groups(&data, 0, data.len()).unwrap();
        assert_eq!(groups.len(), 1);
        assert_eq!(kinds.len(), 3);
        assert!(has_composite_space(&kinds));
        // A pool-only store is clean.
        assert!(!has_composite_space(&[POOL_SUBKIND.to_vec()]));
    }

    #[test]
    fn search_is_bounded_to_the_body_window() {
        // A wrapper before body_lo / after body_hi is invisible.
        let group = pool_group(1, &[(0.0, 0.0, 0.0)]);
        let mut data = group.clone();
        data.extend_from_slice(&group);
        let (groups, kinds) = scan_pool_groups(&data, 0, group.len()).unwrap();
        assert_eq!(groups.len(), 1);
        assert_eq!(kinds.len(), 1);
    }
}
