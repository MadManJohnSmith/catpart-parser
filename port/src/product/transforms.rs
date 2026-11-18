//! CATIA V5 transform record decoders (Phase 6, Ticket P3-V1 under Spec F #45).
//!
//! Authority: `docs/specs/phase6-assembly-viewer-spec.md` (§2.4, §5.2).
//! Prior evidence: `scripts/triage/p26_instance_binding.py`, `scripts/triage/p6_r15_position_probe.py`,
//! `docs/evidence/2026-11-16-p26-binding-probe.md`, and `docs/evidence/2026-11-16-r15-position-probe.md`.
//!
//! # Record Architectures
//!
//! 1. **129-byte Modern Transform Record** (R18–R26 `CATCtorProxyCont` / `Cont_*`):
//!    - Bytes `0x00..0x04`: 4-byte Magic (`\xb5\x13\x27\x79` or `\xb5\x03\x27\x79`)
//!    - Bytes `0x04..0x08`: `u32le` OmbObjectTag ID
//!    - Byte `0x08`: Invariant separator byte `0x80`
//!    - Bytes `0x09..0x21`: Translation vector `[tx, ty, tz]` (3 × `f64le`)
//!    - Bytes `0x21..0x41`: Rotation unit quaternion `[qw, qx, qy, qz]` (4 × `f64le`), **w-first**
//!    - Bytes `0x41..0x61`: Flags / coordinate qualifiers (4 × `f64le`)
//!    - Bytes `0x61..0x81`: Bounding box sentinels / extents (4 × `f64le`)
//!
//! 2. **81-byte Connector Point Record** (`CATCtorProxyCont`):
//!    - Bytes `0x00..0x04`: 4-byte Magic (`\xb5\x13\x0e\x49`)
//!    - Bytes `0x04..0x08`: `u32le` OmbObjectTag ID
//!    - Byte `0x08`: Invariant separator byte `0x80`
//!    - Bytes `0x09..0x51`: Point coordinates (3 × `f64le`), axis direction (4 × `f64le`), limits (2 × `f64le`)
//!    - Identified and filtered out as constraint geometry (never parsed as instance transforms).
//!
//! 3. **R15 Inline Run-Length Matrix Stream** (`8d 81` marker):
//!    - Marker `[0x8d, 0x81]` in attribute stream
//!    - 12 run-length IEEE-754 floats:
//!      - `0xe8`: literal `0.0` (1 byte)
//!      - `0xe7`: literal `1.0` (1 byte)
//!      - `0xe9`: literal `-1.0` (1 byte)
//!      - `0xe6`: literal `f64le` (9 bytes: 1 tag + 8-byte double)
//!    - Floats 0..8: row-major 3x3 proper rotation matrix R (det(R) = +1.0)
//!    - Floats 9..11: 3D translation [Tx, Ty, Tz] in mm
//!    - Matrix R converted to w-first unit quaternion `[qw, qx, qy, qz]`.

#![allow(clippy::suboptimal_flops)]

use serde::{Deserialize, Serialize};

/// Primary magic for 129-byte transform record (`\xb5\x13\x27\x79`).
pub const RECORD_129B_MAGIC_R20: [u8; 4] = [0xb5, 0x13, 0x27, 0x79];
/// Alternative magic for 129-byte transform record (`\xb5\x03\x27\x79`).
pub const RECORD_129B_MAGIC_R20_ALT: [u8; 4] = [0xb5, 0x03, 0x27, 0x79];
/// Magic for 81-byte connector point record (`\xb5\x13\x0e\x49`).
pub const RECORD_81B_MAGIC_R20: [u8; 4] = [0xb5, 0x13, 0x0e, 0x49];

/// Invariant separator byte between header and double-precision array.
pub const SEPARATOR_BYTE: u8 = 0x80;

/// Length of the modern 129-byte transform record.
pub const RECORD_129B_LEN: usize = 129;
/// Length of the 81-byte connector point record.
pub const RECORD_81B_LEN: usize = 81;

/// Unit quaternion gate tolerance: `abs(qw^2 + qx^2 + qy^2 + qz^2 - 1.0) <= 1e-4`.
pub const QUAT_NORM_TOL: f64 = 1e-4;
/// Maximum physical translation bound (1e7 mm = 10 km).
pub const TRANSLATION_BOUND_MAX: f64 = 1e7;

/// Marker for R15 inline matrix stream: `[0x8d, 0x81]`.
pub const R15_MATRIX_MARKER: [u8; 2] = [0x8d, 0x81];

/// Attribute header immediately preceding an explicit instance `_Position` matrix.
///
/// The 8d81 stream is the `_Position` value layer (P3 position-layer segmentation):
/// the product root carries `e8 e0 07 37`, an explicit instance position
/// `e8 f4 07 37`, and an abbreviated identity position `e9 f4 07 04 37`.
pub const POSITION_EXPLICIT_HEADER: [u8; 4] = [0xe8, 0xf4, 0x07, 0x37];
/// Attribute header immediately preceding an identity attribute frame.
///
/// This header is shared by constraint/connector objects and `_Reps`; it is an
/// ordinal placeholder, not an instance `_Position`.
pub const POSITION_IDENTITY_HEADER: [u8; 5] = [0xe9, 0xf4, 0x07, 0x04, 0x37];
/// Attribute header immediately preceding the product-root position matrix.
pub const POSITION_ROOT_HEADER: [u8; 4] = [0xe8, 0xe0, 0x07, 0x37];

/// Header constant table offset threshold below which fixed false-positives reside.
pub const HEADER_FP_MAX_OFFSET: usize = 0x400;

/// Fixed false-positive patterns in the header constant table (P25-11).
pub const HEADER_FP_PATTERNS: &[[f64; 7]] = &[
    [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],
    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
];

/// A decoded CATIA transform record.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TransformRecord {
    /// 3D Translation vector [tx, ty, tz] in millimeters.
    pub translation: [f64; 3],
    /// Unit rotation quaternion [qw, qx, qy, qz], w-first.
    pub quaternion: [f64; 4],
    /// Persistent OmbObjectTag ID.
    pub tag_id: u32,
    /// Bounding box limits [min_x, max_x, min_y, max_y] or extents.
    pub bounding_box: [f64; 4],
    /// Coordinate qualifiers and flags.
    pub flags: [f64; 4],
}

impl TransformRecord {
    /// Construct a new [`TransformRecord`].
    pub fn new(
        translation: [f64; 3],
        quaternion: [f64; 4],
        tag_id: u32,
        bounding_box: [f64; 4],
        flags: [f64; 4],
    ) -> Self {
        Self {
            translation,
            quaternion,
            tag_id,
            bounding_box,
            flags,
        }
    }

    /// Construct a pure placement record with default metadata.
    pub fn from_placement(translation: [f64; 3], quaternion: [f64; 4], tag_id: u32) -> Self {
        Self {
            translation,
            quaternion,
            tag_id,
            bounding_box: [0.0; 4],
            flags: [0.0; 4],
        }
    }

    /// Export the 7-tuple `[tx, ty, tz, qw, qx, qy, qz]`.
    pub fn to_transform_7(&self) -> [f64; 7] {
        [
            self.translation[0],
            self.translation[1],
            self.translation[2],
            self.quaternion[0],
            self.quaternion[1],
            self.quaternion[2],
            self.quaternion[3],
        ]
    }

    /// Check if the quaternion satisfies the unit-norm gate.
    pub fn is_unit_quaternion(&self, tol: f64) -> bool {
        let norm2 = self.quaternion[0] * self.quaternion[0]
            + self.quaternion[1] * self.quaternion[1]
            + self.quaternion[2] * self.quaternion[2]
            + self.quaternion[3] * self.quaternion[3];
        (norm2 - 1.0).abs() <= tol
    }
}

/// Check if a 4-byte slice matches any modern 129-byte transform record magic.
pub fn is_129b_magic(magic: &[u8]) -> bool {
    magic == RECORD_129B_MAGIC_R20 || magic == RECORD_129B_MAGIC_R20_ALT
}

/// The attribute class of an 8d81 matrix in the `_Position` value layer.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PositionKind {
    /// Explicit instance `_Position` (`e8 f4 07 37`). Decodes to a real transform.
    Explicit,
    /// Abbreviated identity attribute frame (`e9 f4 07 04 37`). Shared by
    /// constraint/connector objects and `_Reps`; it is an ordinal placeholder,
    /// never an instance transform.
    Identity,
}

/// One matrix of the `_Position` value layer, in document order.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PositionRecord {
    /// Attribute class (explicit or identity).
    pub kind: PositionKind,
    /// Decoded transform record.
    pub transform: TransformRecord,
    /// Byte offset of the `8d 81` marker.
    pub offset: usize,
}

impl PositionRecord {
    /// Export the 7-tuple `[tx, ty, tz, qw, qx, qy, qz]`.
    pub fn to_transform_7(&self) -> [f64; 7] {
        self.transform.to_transform_7()
    }
}

/// Classify the attribute header immediately preceding an `8d 81` marker.
///
/// Returns `None` for the product-root position (`e8 e0 07 37`) and for any
/// other matrix that is not part of the instance `_Position` layer.
pub fn position_kind_before(data: &[u8], marker: usize) -> Option<PositionKind> {
    let pre = &data[..marker];
    if pre.ends_with(&POSITION_IDENTITY_HEADER) {
        Some(PositionKind::Identity)
    } else if pre.ends_with(&POSITION_EXPLICIT_HEADER) {
        Some(PositionKind::Explicit)
    } else {
        None
    }
}

/// Check if a slice starts with the 81-byte connector point record header.
pub fn is_81b_connector_record(buf: &[u8]) -> bool {
    if buf.len() < RECORD_81B_LEN {
        return false;
    }
    buf[0..4] == RECORD_81B_MAGIC_R20 && buf[8] == SEPARATOR_BYTE
}

/// Check if an offset and 7-tuple match the fixed header false-positive table.
pub fn is_header_false_positive(offset: usize, vals: &[f64; 7]) -> bool {
    if offset >= HEADER_FP_MAX_OFFSET {
        return false;
    }
    HEADER_FP_PATTERNS.iter().any(|pat| {
        vals.iter()
            .zip(pat.iter())
            .all(|(a, b)| (a - b).abs() <= 1e-12)
    })
}

/// Decode one 129-byte modern transform record from a slice.
///
/// Fails closed (`None`) if:
/// - Buffer length < 129 bytes
/// - Magic is unrecognized
/// - Separator byte at offset 8 is not `0x80`
/// - Any double is non-finite (`NaN` or infinite)
/// - Quaternion fails unit-norm gate (`abs(qw^2+qx^2+qy^2+qz^2 - 1.0) > 1e-4`)
/// - Translation exceeds bounds (`abs(t) > 1e7 mm`)
pub fn decode_129b_record(buf: &[u8]) -> Option<TransformRecord> {
    if buf.len() < RECORD_129B_LEN {
        return None;
    }
    if !is_129b_magic(&buf[0..4]) {
        return None;
    }
    if buf[8] != SEPARATOR_BYTE {
        return None;
    }

    let tag_id = u32::from_le_bytes(buf[4..8].try_into().ok()?);

    let mut doubles = [0.0f64; 15];
    for (i, d) in doubles.iter_mut().enumerate() {
        let start = 9 + i * 8;
        let bytes = buf[start..start + 8].try_into().ok()?;
        let val = f64::from_le_bytes(bytes);
        if !val.is_finite() {
            return None;
        }
        *d = val;
    }

    let translation = [doubles[0], doubles[1], doubles[2]];
    let quaternion = [doubles[3], doubles[4], doubles[5], doubles[6]];
    let flags = [doubles[7], doubles[8], doubles[9], doubles[10]];
    let bounding_box = [doubles[11], doubles[12], doubles[13], doubles[14]];

    // Validate unit quaternion gate
    let norm2 = quaternion[0] * quaternion[0]
        + quaternion[1] * quaternion[1]
        + quaternion[2] * quaternion[2]
        + quaternion[3] * quaternion[3];
    if (norm2 - 1.0).abs() > QUAT_NORM_TOL {
        return None;
    }

    // Validate translation bounds
    for &t in &translation {
        if t.abs() > TRANSLATION_BOUND_MAX {
            return None;
        }
    }

    Some(TransformRecord {
        translation,
        quaternion,
        tag_id,
        bounding_box,
        flags,
    })
}

/// Scan a buffer for modern 129-byte transform records.
///
/// Automatically identifies and skips 81-byte connector point records (`\xb5\x13\x0e\x49`)
/// as constraint geometry without parsing them as instance transforms.
pub fn scan_modern_transform_records(data: &[u8]) -> Vec<TransformRecord> {
    let mut records = Vec::new();
    let n = data.len();
    let mut i = 0;

    while i + RECORD_81B_LEN <= n {
        // Check for 129-byte record
        if let Some(rec) = data
            .get(i..i + RECORD_129B_LEN)
            .and_then(decode_129b_record)
        {
            records.push(rec);
            i += RECORD_129B_LEN;
            continue;
        }
        // Check for 81-byte connector point record -> filter as constraint geometry
        if is_81b_connector_record(&data[i..]) {
            i += RECORD_81B_LEN;
            continue;
        }

        i += 1;
    }

    records
}

// --- R15 Inline Run-Length Matrix Stream Decoder ------------------------------

/// Parse up to `count` run-length encoded floating point numbers from `stream`.
///
/// Tag grammar:
/// - `0xe8`: literal `0.0` (1 byte)
/// - `0xe7`: literal `1.0` (1 byte)
/// - `0xe9`: literal `-1.0` (1 byte)
/// - `0xe6`: literal `f64le` (9 bytes: 1 tag + 8-byte double)
///
/// Returns `Some((values, bytes_consumed))` if exactly `count` finite floats are decoded.
pub fn parse_run_length_floats(stream: &[u8], count: usize) -> Option<(Vec<f64>, usize)> {
    let mut vals = Vec::with_capacity(count);
    let mut p = 0;

    while p < stream.len() && vals.len() < count {
        let tag = stream[p];
        match tag {
            0xE8 => {
                vals.push(0.0);
                p += 1;
            }
            0xE7 => {
                vals.push(1.0);
                p += 1;
            }
            0xE9 => {
                vals.push(-1.0);
                p += 1;
            }
            0xE6 if p + 9 <= stream.len() => {
                let bytes = stream[p + 1..p + 9].try_into().ok()?;
                let val = f64::from_le_bytes(bytes);
                if !val.is_finite() {
                    return None;
                }
                vals.push(val);
                p += 9;
            }
            0xE6 => return None,
            _ => return None,
        }
    }

    if vals.len() == count {
        Some((vals, p))
    } else {
        None
    }
}

/// Compute 3x3 matrix determinant.
pub fn det3(r: &[[f64; 3]; 3]) -> f64 {
    r[0][0] * (r[1][1] * r[2][2] - r[1][2] * r[2][1])
        - r[0][1] * (r[1][0] * r[2][2] - r[1][2] * r[2][0])
        + r[0][2] * (r[1][0] * r[2][1] - r[1][1] * r[2][0])
}

fn dot3(u: &[f64; 3], v: &[f64; 3]) -> f64 {
    u[0] * v[0] + u[1] * v[1] + u[2] * v[2]
}

fn norm3(u: &[f64; 3]) -> f64 {
    dot3(u, u).sqrt()
}

/// Verify that a 3x3 matrix is a proper rotation (SO(3)):
/// determinant is +1.0, rows have unit norm, and rows are mutually orthogonal.
pub fn is_proper_rotation(r: &[[f64; 3]; 3], tol: f64) -> bool {
    let d = det3(r);
    if (d - 1.0).abs() > tol {
        return false;
    }
    let r1 = &r[0];
    let r2 = &r[1];
    let r3 = &r[2];
    if (norm3(r1) - 1.0).abs() > tol
        || (norm3(r2) - 1.0).abs() > tol
        || (norm3(r3) - 1.0).abs() > tol
    {
        return false;
    }
    if dot3(r1, r2).abs() > tol || dot3(r1, r3).abs() > tol || dot3(r2, r3).abs() > tol {
        return false;
    }
    true
}

/// Convert row-major 3x3 proper rotation matrix to w-first unit quaternion `[qw, qx, qy, qz]`.
///
/// Normalizes the result and pins `qw >= 0.0`.
pub fn mat3_to_quat(r: &[[f64; 3]; 3]) -> [f64; 4] {
    let m00 = r[0][0];
    let m01 = r[0][1];
    let m02 = r[0][2];
    let m10 = r[1][0];
    let m11 = r[1][1];
    let m12 = r[1][2];
    let m20 = r[2][0];
    let m21 = r[2][1];
    let m22 = r[2][2];

    let tr = m00 + m11 + m22;
    let (mut qw, mut qx, mut qy, mut qz) = if tr > 0.0 {
        let s = (tr + 1.0).sqrt() * 2.0;
        (0.25 * s, (m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s)
    } else if (m00 > m11) && (m00 > m22) {
        let s = (1.0 + m00 - m11 - m22).max(0.0).sqrt() * 2.0;
        ((m21 - m12) / s, 0.25 * s, (m01 + m10) / s, (m02 + m20) / s)
    } else if m11 > m22 {
        let s = (1.0 + m11 - m00 - m22).max(0.0).sqrt() * 2.0;
        ((m02 - m20) / s, (m01 + m10) / s, 0.25 * s, (m12 + m21) / s)
    } else {
        let s = (1.0 + m22 - m00 - m11).max(0.0).sqrt() * 2.0;
        ((m10 - m01) / s, (m02 + m20) / s, (m12 + m21) / s, 0.25 * s)
    };

    let q_norm = (qw * qw + qx * qx + qy * qy + qz * qz).sqrt();
    if q_norm > 1e-12 {
        qw /= q_norm;
        qx /= q_norm;
        qy /= q_norm;
        qz /= q_norm;
    }
    if qw < 0.0 {
        qw = -qw;
        qx = -qx;
        qy = -qy;
        qz = -qz;
    }
    [qw, qx, qy, qz]
}

/// Decode a 12-element run-length matrix stream from bytes following `[0x8d, 0x81]`.
///
/// Returns `Some(([tx, ty, tz], [qw, qx, qy, qz]))` on success.
pub fn decode_r15_matrix_stream(stream: &[u8]) -> Option<([f64; 3], [f64; 4])> {
    let (vals, _) = parse_run_length_floats(stream, 12)?;
    let r = [
        [vals[0], vals[1], vals[2]],
        [vals[3], vals[4], vals[5]],
        [vals[6], vals[7], vals[8]],
    ];
    let t = [vals[9], vals[10], vals[11]];

    if !is_proper_rotation(&r, QUAT_NORM_TOL) {
        return None;
    }

    for &coord in &t {
        if coord.abs() > TRANSLATION_BOUND_MAX {
            return None;
        }
    }

    let quat = mat3_to_quat(&r);
    Some((t, quat))
}

/// Scan a buffer for R15 inline matrix streams anchored at marker `[0x8d, 0x81]`.
pub fn scan_r15_matrix_streams(data: &[u8]) -> Vec<TransformRecord> {
    let mut records = Vec::new();
    let marker = &R15_MATRIX_MARKER;
    let mut idx = 0;

    while idx + 2 <= data.len() {
        if let Some(pos) = data[idx..]
            .windows(2)
            .position(|w| w == marker)
            .map(|p| idx + p)
        {
            if let Some((t, q)) = decode_r15_matrix_stream(&data[pos + 2..]) {
                records.push(TransformRecord::from_placement(t, q, 0));
            }
            idx = pos + 2;
        } else {
            break;
        }
    }

    records
}

/// Scan the `_Position` value layer: valid `8d 81` matrices whose attribute
/// header is an explicit (`e8 f4 07 37`) or identity (`e9 f4 07 04 37`) instance
/// position. The product-root position (`e8 e0 07 37`) and every other matrix
/// are excluded.
///
/// Records are returned in document order (the serialization order).
pub fn scan_position_matrix_streams(data: &[u8]) -> Vec<PositionRecord> {
    let mut records = Vec::new();
    let mut idx = 0;

    while idx + 2 <= data.len() {
        let Some(pos) = data[idx..]
            .windows(2)
            .position(|w| w == R15_MATRIX_MARKER)
            .map(|p| idx + p)
        else {
            break;
        };
        if let Some(kind) = position_kind_before(data, pos)
            && let Some((t, q)) = decode_r15_matrix_stream(&data[pos + 2..])
        {
            records.push(PositionRecord {
                kind,
                transform: TransformRecord::from_placement(t, q, 0),
                offset: pos,
            });
        }
        idx = pos + 2;
    }

    records
}

/// Scan a buffer for raw 56-byte transform records (`[tx, ty, tz, qw, qx, qy, qz]`),
/// filtering out header false positives and denormal phantoms.
pub fn scan_raw_56b_records(data: &[u8]) -> Vec<TransformRecord> {
    const RECORD_BYTES: usize = 56;
    if data.len() < RECORD_BYTES {
        return Vec::new();
    }

    let mut units: Vec<(usize, [f64; 7])> = Vec::new();
    for off in 0..=(data.len() - RECORD_BYTES) {
        let mut vals = [0.0f64; 7];
        let mut all_finite = true;
        for (i, v) in vals.iter_mut().enumerate() {
            let start = off + i * 8;
            if let Ok(b) = data[start..start + 8].try_into() {
                let d = f64::from_le_bytes(b);
                if !d.is_finite() {
                    all_finite = false;
                    break;
                }
                *v = d;
            } else {
                all_finite = false;
                break;
            }
        }
        if !all_finite {
            continue;
        }

        // Header FP rejection
        if is_header_false_positive(off, &vals) {
            continue;
        }

        // Unit quaternion check
        let q = &vals[3..7];
        let norm2 = q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3];
        if (norm2 - 1.0).abs() > QUAT_NORM_TOL {
            continue;
        }

        // Translation bounds check
        let t = &vals[0..3];
        if t.iter().any(|coord| coord.abs() > TRANSLATION_BOUND_MAX) {
            continue;
        }

        units.push((off, vals));
    }

    // Group overlapping 56-byte windows and keep earliest window
    let mut records = Vec::new();
    let mut i = 0;
    while i < units.len() {
        let mut j = i;
        let mut end = units[i].0 + RECORD_BYTES;
        while j + 1 < units.len() && units[j + 1].0 < end {
            j += 1;
            end = end.max(units[j].0 + RECORD_BYTES);
        }
        let (off, vals) = units[i];
        records.push(TransformRecord::from_placement(
            [vals[0], vals[1], vals[2]],
            [vals[3], vals[4], vals[5], vals[6]],
            off as u32,
        ));
        i = j + 1;
    }

    records
}

#[cfg(test)]
mod tests {
    use super::*;

    fn build_synthetic_129b(
        magic: [u8; 4],
        id: u32,
        sep: u8,
        t: [f64; 3],
        q: [f64; 4],
        flags: [f64; 4],
        bbox: [f64; 4],
    ) -> Vec<u8> {
        let mut rec = Vec::with_capacity(129);
        rec.extend_from_slice(&magic);
        rec.extend_from_slice(&id.to_le_bytes());
        rec.push(sep);
        for v in t {
            rec.extend_from_slice(&v.to_le_bytes());
        }
        for v in q {
            rec.extend_from_slice(&v.to_le_bytes());
        }
        for v in flags {
            rec.extend_from_slice(&v.to_le_bytes());
        }
        for v in bbox {
            rec.extend_from_slice(&v.to_le_bytes());
        }
        rec
    }

    #[test]
    fn decodes_valid_129b_record_r20_and_alt() {
        let rec_bytes = build_synthetic_129b(
            RECORD_129B_MAGIC_R20,
            42,
            SEPARATOR_BYTE,
            [10.0, -20.5, 300.0],
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 2.0, 3.0],
            [-100.0, 100.0, -50.0, 50.0],
        );
        let rec = decode_129b_record(&rec_bytes).expect("decode valid 129b");
        assert_eq!(rec.tag_id, 42);
        assert_eq!(rec.translation, [10.0, -20.5, 300.0]);
        assert_eq!(rec.quaternion, [1.0, 0.0, 0.0, 0.0]);
        assert_eq!(rec.flags, [0.0, 1.0, 2.0, 3.0]);
        assert_eq!(rec.bounding_box, [-100.0, 100.0, -50.0, 50.0]);
        assert_eq!(
            rec.to_transform_7(),
            [10.0, -20.5, 300.0, 1.0, 0.0, 0.0, 0.0]
        );

        // Alt magic
        let rec_alt = build_synthetic_129b(
            RECORD_129B_MAGIC_R20_ALT,
            99,
            SEPARATOR_BYTE,
            [0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0; 4],
            [0.0; 4],
        );
        let parsed_alt = decode_129b_record(&rec_alt).expect("decode alt magic");
        assert_eq!(parsed_alt.tag_id, 99);
    }

    #[test]
    fn rejects_non_0x80_separator() {
        let rec_bytes = build_synthetic_129b(
            RECORD_129B_MAGIC_R20,
            1,
            0x00, // non-0x80 separator
            [0.0; 3],
            [1.0, 0.0, 0.0, 0.0],
            [0.0; 4],
            [0.0; 4],
        );
        assert!(decode_129b_record(&rec_bytes).is_none());
    }

    #[test]
    fn rejects_non_unit_quaternion() {
        let rec_bytes = build_synthetic_129b(
            RECORD_129B_MAGIC_R20,
            1,
            SEPARATOR_BYTE,
            [0.0; 3],
            [0.0, 0.0, 1.0, 1.0], // norm2 = 2.0 (directional sentinel)
            [0.0; 4],
            [0.0; 4],
        );
        assert!(decode_129b_record(&rec_bytes).is_none());
    }

    #[test]
    fn rejects_out_of_bounds_translation() {
        let rec_bytes = build_synthetic_129b(
            RECORD_129B_MAGIC_R20,
            1,
            SEPARATOR_BYTE,
            [1e8, 0.0, 0.0], // > 1e7 mm
            [1.0, 0.0, 0.0, 0.0],
            [0.0; 4],
            [0.0; 4],
        );
        assert!(decode_129b_record(&rec_bytes).is_none());
    }

    #[test]
    fn identifies_and_filters_81b_connector_records() {
        let mut data = Vec::new();
        // Record 1: 129b
        let rec1 = build_synthetic_129b(
            RECORD_129B_MAGIC_R20,
            10,
            SEPARATOR_BYTE,
            [1.0, 2.0, 3.0],
            [1.0, 0.0, 0.0, 0.0],
            [0.0; 4],
            [0.0; 4],
        );
        data.extend_from_slice(&rec1);

        // Record 2: 81b connector point record
        let mut rec81 = Vec::with_capacity(81);
        rec81.extend_from_slice(&RECORD_81B_MAGIC_R20);
        rec81.extend_from_slice(&20u32.to_le_bytes());
        rec81.push(SEPARATOR_BYTE);
        for _ in 0..9 {
            rec81.extend_from_slice(&0.0f64.to_le_bytes());
        }
        assert_eq!(rec81.len(), 81);
        assert!(is_81b_connector_record(&rec81));
        data.extend_from_slice(&rec81);

        // Record 3: another 129b
        let rec3 = build_synthetic_129b(
            RECORD_129B_MAGIC_R20_ALT,
            30,
            SEPARATOR_BYTE,
            [4.0, 5.0, 6.0],
            [1.0, 0.0, 0.0, 0.0],
            [0.0; 4],
            [0.0; 4],
        );
        data.extend_from_slice(&rec3);

        let scanned = scan_modern_transform_records(&data);
        assert_eq!(scanned.len(), 2);
        assert_eq!(scanned[0].tag_id, 10);
        assert_eq!(scanned[1].tag_id, 30);
    }

    #[test]
    fn decodes_r15_run_length_floats() {
        // [1.0, 0.0, -1.0, 42.5]
        let mut stream = Vec::new();
        stream.push(0xE7); // 1.0
        stream.push(0xE8); // 0.0
        stream.push(0xE9); // -1.0
        stream.push(0xE6); // f64
        stream.extend_from_slice(&42.5f64.to_le_bytes());

        let (vals, consumed) = parse_run_length_floats(&stream, 4).expect("parse 4 floats");
        assert_eq!(vals, vec![1.0, 0.0, -1.0, 42.5]);
        assert_eq!(consumed, 1 + 1 + 1 + 9);
    }

    #[test]
    fn decodes_r15_identity_matrix_stream() {
        // Identity: R = I3, T = [0, 0, 0] -> 12 bytes: e7 e8 e8 e8 e7 e8 e8 e8 e7 e8 e8 e8
        let stream = [
            0xE7, 0xE8, 0xE8, 0xE8, 0xE7, 0xE8, 0xE8, 0xE8, 0xE7, 0xE8, 0xE8, 0xE8,
        ];
        let (t, q) = decode_r15_matrix_stream(&stream).expect("decode identity R15");
        assert_eq!(t, [0.0, 0.0, 0.0]);
        assert_eq!(q, [1.0, 0.0, 0.0, 0.0]);
    }

    #[test]
    fn decodes_r15_rotation_matrix_to_quaternion() {
        // 90 deg rotation about Z:
        // R = [ [0, -1, 0], [1, 0, 0], [0, 0, 1] ]
        // T = [10.0, 20.0, 30.0]
        // R1: 0, -1, 0 -> e8 e9 e8
        // R2: 1,  0, 0 -> e7 e8 e8
        // R3: 0,  0, 1 -> e8 e8 e7
        // T: 10, 20, 30 -> e6 10.0, e6 20.0, e6 30.0
        let mut stream = vec![0xE8, 0xE9, 0xE8, 0xE7, 0xE8, 0xE8, 0xE8, 0xE8, 0xE7];
        stream.push(0xE6);
        stream.extend_from_slice(&10.0f64.to_le_bytes());
        stream.push(0xE6);
        stream.extend_from_slice(&20.0f64.to_le_bytes());
        stream.push(0xE6);
        stream.extend_from_slice(&30.0f64.to_le_bytes());

        let (t, q) = decode_r15_matrix_stream(&stream).expect("decode rotated R15");
        assert_eq!(t, [10.0, 20.0, 30.0]);
        // 90 deg rotation about Z: qw = cos(45 deg) = sqrt(2)/2 ≈ 0.70710678, qz = sin(45 deg) ≈ 0.70710678
        let half_sqrt2 = std::f64::consts::FRAC_1_SQRT_2;
        assert!((q[0] - half_sqrt2).abs() < 1e-6);
        assert!(q[1].abs() < 1e-6);
        assert!(q[2].abs() < 1e-6);
        assert!((q[3] - half_sqrt2).abs() < 1e-6);
    }

    #[test]
    fn scans_r15_matrix_streams_in_data() {
        let mut data = vec![0xAA; 50];
        // Embed marker 8d 81 followed by identity stream
        data.extend_from_slice(&R15_MATRIX_MARKER);
        data.extend_from_slice(&[
            0xE7, 0xE8, 0xE8, 0xE8, 0xE7, 0xE8, 0xE8, 0xE8, 0xE7, 0xE8, 0xE8, 0xE8,
        ]);
        data.extend_from_slice(&[0xBB; 20]);

        let found = scan_r15_matrix_streams(&data);
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].translation, [0.0, 0.0, 0.0]);
        assert_eq!(found[0].quaternion, [1.0, 0.0, 0.0, 0.0]);
    }

    #[test]
    fn position_kind_before_recognizes_position_headers() {
        let identity_stream = [
            0xE7, 0xE8, 0xE8, 0xE8, 0xE7, 0xE8, 0xE8, 0xE8, 0xE7, 0xE8, 0xE8, 0xE8,
        ];

        let mut explicit = POSITION_EXPLICIT_HEADER.to_vec();
        explicit.extend_from_slice(&R15_MATRIX_MARKER);
        assert_eq!(
            position_kind_before(&explicit, explicit.len() - R15_MATRIX_MARKER.len()),
            Some(PositionKind::Explicit)
        );

        let mut identity = POSITION_IDENTITY_HEADER.to_vec();
        identity.extend_from_slice(&R15_MATRIX_MARKER);
        assert_eq!(
            position_kind_before(&identity, identity.len() - R15_MATRIX_MARKER.len()),
            Some(PositionKind::Identity)
        );

        let mut root = POSITION_ROOT_HEADER.to_vec();
        root.extend_from_slice(&R15_MATRIX_MARKER);
        assert_eq!(
            position_kind_before(&root, root.len() - R15_MATRIX_MARKER.len()),
            None
        );

        // A non-position header is not attributed.
        let mut other = vec![0x00, 0x01, 0x02, 0x03];
        other.extend_from_slice(&R15_MATRIX_MARKER);
        assert_eq!(
            position_kind_before(&other, other.len() - R15_MATRIX_MARKER.len()),
            None
        );

        assert_eq!(identity_stream.len(), 12);
    }

    #[test]
    fn scan_position_streams_excludes_root_and_keeps_document_order() {
        let mut data = Vec::new();
        // Root position (excluded).
        data.extend_from_slice(&POSITION_ROOT_HEADER);
        data.extend_from_slice(&R15_MATRIX_MARKER);
        data.extend_from_slice(&[
            0xE7, 0xE8, 0xE8, 0xE8, 0xE7, 0xE8, 0xE8, 0xE8, 0xE7, 0xE8, 0xE8, 0xE8,
        ]);
        data.push(0xFE);
        // Explicit position.
        data.extend_from_slice(&POSITION_EXPLICIT_HEADER);
        data.extend_from_slice(&R15_MATRIX_MARKER);
        data.extend_from_slice(&[0xE7, 0xE8, 0xE8, 0xE8, 0xE7, 0xE8, 0xE8, 0xE8, 0xE7, 0xE6]);
        data.extend_from_slice(&12.5f64.to_le_bytes());
        data.push(0xE6);
        data.extend_from_slice(&0.0f64.to_le_bytes());
        data.push(0xE6);
        data.extend_from_slice(&14.4f64.to_le_bytes());
        data.push(0xFE);
        // Identity position.
        data.extend_from_slice(&POSITION_IDENTITY_HEADER);
        data.extend_from_slice(&R15_MATRIX_MARKER);
        data.extend_from_slice(&[
            0xE7, 0xE8, 0xE8, 0xE8, 0xE7, 0xE8, 0xE8, 0xE8, 0xE7, 0xE8, 0xE8, 0xE8,
        ]);

        let records = scan_position_matrix_streams(&data);
        assert_eq!(records.len(), 2);
        assert_eq!(records[0].kind, PositionKind::Explicit);
        assert_eq!(records[0].transform.translation, [12.5, 0.0, 14.4]);
        assert_eq!(records[1].kind, PositionKind::Identity);
        assert_eq!(records[1].transform.translation, [0.0, 0.0, 0.0]);
    }

    #[test]
    fn corpus_records_on_coso_and_servo_if_available() {
        let manifest_dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
        // Coso: 8 records, root_plus_sequential
        let coso_path = manifest_dir
            .join("../corpus/Apoloo13/ASE_III/diseño_3d/prueba_tensor_cable/coso.CATProduct");
        if coso_path.exists() {
            let data = std::fs::read(&coso_path).expect("read coso");
            let recs = scan_modern_transform_records(&data);
            assert_eq!(recs.len(), 8);
            let positions = scan_position_matrix_streams(&data);
            assert_eq!(positions.len(), 7);
            assert_eq!(
                positions
                    .iter()
                    .filter(|p| p.kind == PositionKind::Explicit)
                    .count(),
                6
            );
            assert_eq!(
                positions
                    .iter()
                    .filter(|p| p.kind == PositionKind::Identity)
                    .count(),
                1
            );
        }

        // Servo: 2 records, sequential_1to1
        let servo_path = manifest_dir.join(
            "../corpus/Apoloo13/ASE_III/diseño_3d/lengua/lengua_v2/servo_STS3215_03a v1.CATProduct",
        );
        if servo_path.exists() {
            let data = std::fs::read(&servo_path).expect("read servo");
            let recs = scan_modern_transform_records(&data);
            assert_eq!(recs.len(), 2);
            let positions = scan_position_matrix_streams(&data);
            assert_eq!(positions.len(), 4);
            assert_eq!(
                positions
                    .iter()
                    .filter(|p| p.kind == PositionKind::Explicit)
                    .count(),
                3
            );
        }
    }
}
