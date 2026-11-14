//! Binary little-endian PLY output — the port of the Python reference
//! module ``catpart.geometry.ply`` (``src/catpart/geometry/ply.py``),
//! per spec §2.1 of ``docs/specs/phase5-viewer-spec.md`` (binary-LE
//! PLY writer; Fidelity compares the PLY byte-identical, §3.2).
//!
//! Vertices are the decoded pool in walk order (G3's soup convention:
//! the committed OBJ's ``v`` lines), faces the decoded triangles
//! as-is — the winding law (F5: counter-clockwise seen from the stored
//! normal, the OBJ/PLY convention) is preserved by the decode, so the
//! writer performs no reordering. Coordinates are float32 (the pool is
//! f32le, P3 — the round-trip is exact: the f64s hold exact f32
//! widenings, so the write-back ``as f32`` recovers the load bytes
//! exactly); face indices are int32 through a uchar-3 count list, the
//! standard single-property PLY face element. The header template is
//! the twin's byte for byte (§3.2 compares the PLY byte-identical).
//!
//! Evidence: the twin's docstring cites no dedicated evidence note —
//! it is ticket #32's writer over the G2/G3 conventions; its claims
//! trace to ``docs/evidence/2026-11-09-vertex-pool.md`` (P3, the
//! f32le pool) and ``docs/evidence/2026-11-09-facet-semantics.md``
//! (F5, the winding law; G3's soup convention). Those are the
//! citations this port carries.
//!
//! Numeric contract (spec §2.2): decode module — the
//! ``clippy::suboptimal_flops`` allow below is the pinned carve-out
//! (mul_add changes rounding and flips exact-equality decisions); see
//! the crate docs in ``../lib.rs`` for the full policy.
#![allow(clippy::suboptimal_flops)]

use std::io::Write;

/// The twin's ``_HEADER_TEMPLATE``, verbatim (all ASCII).
const HEADER_TEMPLATE: &str = "ply\n\
format binary_little_endian 1.0\n\
comment catpart-export: CATStdCont nested-store geometry \
(G1/G2/G3 decode model, catpart-parser #32)\n\
element vertex {n_vertices}\n\
property float x\n\
property float y\n\
property float z\n\
element face {n_faces}\n\
property list uchar int vertex_indices\n\
end_header\n";

/// Write the PLY to the open writer ``w`` — the twin's
/// :func:`catpart.geometry.ply.write_binary_little_endian_ply`.
///
/// ``vertices`` is a sequence of (x, y, z) float triples (the pool in
/// walk order), ``faces`` a sequence of (a, b, c) vertex-index
/// triples. Errors surface as the caller's ``io-error`` class (the
/// twin's OSError arm).
pub fn write_binary_little_endian_ply<W: Write>(
    w: &mut W,
    vertices: &[(f64, f64, f64)],
    faces: &[(u32, u32, u32)],
) -> std::io::Result<()> {
    let header = HEADER_TEMPLATE
        .replace("{n_vertices}", &vertices.len().to_string())
        .replace("{n_faces}", &faces.len().to_string());
    w.write_all(header.as_bytes())?;
    for &(x, y, z) in vertices {
        // struct.pack("<fff", ...) over the widened f64s: the values
        // hold exact f32 widenings, so the round-trip is exact (P3).
        w.write_all(&(x as f32).to_le_bytes())?;
        w.write_all(&(y as f32).to_le_bytes())?;
        w.write_all(&(z as f32).to_le_bytes())?;
    }
    for &(a, b, c) in faces {
        // struct.pack("<Biii", 3, a, b, c).
        w.write_all(&[3u8])?;
        w.write_all(&(a as i32).to_le_bytes())?;
        w.write_all(&(b as i32).to_le_bytes())?;
        w.write_all(&(c as i32).to_le_bytes())?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The fixture box's pool + 12 triangles produce the known PLY
    /// shape: the 184-byte header, 12 x 12 bytes of vertices,
    /// triangles x 13 bytes of faces.
    #[test]
    fn writes_the_exact_header_and_record_layout() {
        let mut out = Vec::new();
        let vertices = [(0.0f64, 0.0, 0.0), (20.0, 0.0, 0.0), (0.0, 100.0, 60.0)];
        let faces = [(0u32, 1u32, 2u32)];
        write_binary_little_endian_ply(&mut out, &vertices, &faces).unwrap();
        // 3 vertices x 12 bytes + 1 face x 13 bytes follow the header.
        let header = String::from_utf8(out[..out.len() - 36 - 13].to_vec()).unwrap();
        assert_eq!(
            header,
            "ply\n\
             format binary_little_endian 1.0\n\
             comment catpart-export: CATStdCont nested-store geometry \
             (G1/G2/G3 decode model, catpart-parser #32)\n\
             element vertex 3\n\
             property float x\n\
             property float y\n\
             property float z\n\
             element face 1\n\
             property list uchar int vertex_indices\n\
             end_header\n"
        );
        // Vertex 2 = (0.0, 100.0, 60.0) as f32le (the third record).
        let v2 = &out[out.len() - 13 - 12..out.len() - 13];
        assert_eq!(&v2[0..4], &0.0f32.to_le_bytes());
        assert_eq!(&v2[4..8], &100.0f32.to_le_bytes());
        assert_eq!(&v2[8..12], &60.0f32.to_le_bytes());
        // The face record: uchar 3 + three int32.
        let face = &out[out.len() - 13..];
        assert_eq!(face[0], 3);
        assert_eq!(&face[1..5], &0i32.to_le_bytes());
        assert_eq!(&face[5..9], &1i32.to_le_bytes());
        assert_eq!(&face[9..13], &2i32.to_le_bytes());
    }

    #[test]
    fn the_f32_round_trip_is_exact() {
        // An f32 value with no short decimal form survives the
        // widen-write-back cycle exactly (P3: the pool is f32le).
        let raw = 0.123456789f32;
        let widened = raw as f64;
        let mut out = Vec::new();
        write_binary_little_endian_ply(&mut out, &[(widened, 0.0, 0.0)], &[]).unwrap();
        let header_len = out.len() - 12;
        assert_eq!(&out[header_len..header_len + 4], &raw.to_le_bytes());
    }

    #[test]
    fn empty_pool_and_faces_write_the_header_only() {
        let mut out = Vec::new();
        write_binary_little_endian_ply(&mut out, &[], &[]).unwrap();
        let text = String::from_utf8(out).unwrap();
        assert!(text.contains("element vertex 0\n"));
        assert!(text.contains("element face 0\n"));
        assert!(text.ends_with("end_header\n"));
    }
}
