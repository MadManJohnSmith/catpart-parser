//! The trailer terminating a CATIA V5 ``.CATPart``/``.CATProduct``
//! file — the port of the Python reference module ``catpart.trailer``
//! (``src/catpart/trailer.py``), per spec §2.1 of
//! ``docs/specs/phase5-viewer-spec.md`` (A..G dwords, CB__END).
//!
//! The twin's docstring carries the trailer model (seven big-endian
//! dwords plus the ``CB__END\0`` marker over the last 36 bytes) and the
//! writer registration block pattern; this port cites, never restates.
//! The behavior is mirrored 1:1 including the fail-closed arms: a file
//! not ending with the marker has no trailer (``None``), trailer fields
//! are never validated (reported as-is), and a registration block not
//! matching the documented 41-byte pattern byte-exact is ``None``
//! (the 3/1556 corpus failures are reported, not repaired).
//!
//! Evidence (the same citations the twin's docstring carries):
//!
//! - ``docs/evidence/2026-11-07-container-table-and-trailer.md``
//!   ("Trailer" — the dword rates, the registration block, the
//!   no-trailer population)
//!
//! Numeric contract (spec §2.2 point 3): decode module — the
//! ``suboptimal_flops`` allow below is the pinned carve-out (mul_add
//! changes rounding and flips exact-equality decisions); see the
//! crate docs in ``lib.rs`` for the full policy.
#![allow(clippy::suboptimal_flops)]

use serde::Serialize;

/// Twin constant: :data:`catpart.trailer.TRAILER_SIZE`.
pub const TRAILER_SIZE: usize = 36;
/// The trailer marker ``CB__END\0`` (twin:
/// :data:`catpart.trailer.MARKER`).
pub const MARKER: [u8; 8] = *b"CB__END\x00";

const REGISTRATION_SIZE: usize = 41;
const REGISTRATION_TAGS: [u8; 2] = [0x4D, 0x4E];
const REGISTRATION_COMPANY: &[u8] = b"DASSAULT-SYSTEMES";
const REGISTRATION_PRODUCT: &[u8] = b"CATIA";
const REGISTRATION_CODE: &[u8] = b"041803";

/// The writer registration block at trailer field B (B1 evidence) —
/// the twin's :class:`catpart.trailer.RegistrationInfo` dataclass.
/// Field declaration order = the twin's ``to_json`` dict construction
/// order.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct RegistrationInfo {
    /// The block's tag byte as a single character (``'M'``/``'N'``).
    pub tag: String,
    /// First length-prefixed (u32le) string, byte-exact by validation.
    pub company: String,
    /// Second length-prefixed (u32le) string, byte-exact by validation.
    pub product: String,
    /// Third length-prefixed (u32le) string, byte-exact by validation.
    pub code: String,
}

/// The seven trailer dwords plus the decoded registration block — the
/// twin's :class:`catpart.trailer.TrailerInfo` dataclass. Field
/// declaration order = the twin's ``to_json`` dict construction order.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct TrailerInfo {
    /// Field A (size-36): constant ``0x00000001`` corpus-wide.
    pub a: u32,
    /// Field B (size-32): absolute file offset of the registration block.
    pub registration_offset: u32,
    /// Field C (size-28): first half of the C==D pair.
    pub c: u32,
    /// Field D (size-24): second half of the C==D pair.
    pub d: u32,
    /// Field E (size-20).
    pub e: u32,
    /// Field F (size-16).
    pub f: u32,
    /// Field G (size-12): == header dword12 == size - dword8 (law H1).
    pub tail_region_length: u32,
    /// The registration block at ``registration_offset``, when it
    /// validates; ``None`` otherwise.
    pub registration: Option<RegistrationInfo>,
}

/// Decode the registration block at ``offset``, or ``None`` (twin:
/// :func:`catpart.trailer.parse_registration`).
///
/// The block must match the documented 41-byte pattern byte-exact (tag
/// 0x4d/0x4e and the three length-prefixed strings); anything else —
/// including an offset that would run past the buffer — yields
/// ``None``. The twin's ``offset < 0`` arm is structurally unreachable
/// here: the offset arrives as a big-endian uint32 dword.
pub fn parse_registration(data: &[u8], offset: u32) -> Option<RegistrationInfo> {
    let start = offset as usize;
    let end = start.checked_add(REGISTRATION_SIZE)?;
    if end > data.len() {
        return None;
    }
    let block = &data[start..end];
    if !REGISTRATION_TAGS.contains(&block[0]) {
        return None;
    }
    let le =
        |at: usize| u32::from_le_bytes([block[at], block[at + 1], block[at + 2], block[at + 3]]);
    if le(1) != 17 || block[5..22] != *REGISTRATION_COMPANY {
        return None;
    }
    if le(22) != 5 || block[26..31] != *REGISTRATION_PRODUCT {
        return None;
    }
    if le(31) != 6 || block[35..41] != *REGISTRATION_CODE {
        return None;
    }
    Some(RegistrationInfo {
        tag: (block[0] as char).to_string(),
        company: String::from_utf8_lossy(REGISTRATION_COMPANY).into_owned(),
        product: String::from_utf8_lossy(REGISTRATION_PRODUCT).into_owned(),
        code: String::from_utf8_lossy(REGISTRATION_CODE).into_owned(),
    })
}

/// Parse the trailer of ``data``, or ``None`` when there is none (twin:
/// :func:`catpart.trailer.parse_trailer`).
///
/// The trailer exists when the buffer ends with the ``CB__END\0``
/// marker and carries the full 36-byte model; the seven dwords are
/// big-endian.
pub fn parse_trailer(data: &[u8]) -> Option<TrailerInfo> {
    let size = data.len();
    if size < TRAILER_SIZE || data[size - 8..size] != MARKER {
        return None;
    }
    let base = size - TRAILER_SIZE;
    let mut dwords = [0u32; 7];
    for (i, dword) in dwords.iter_mut().enumerate() {
        let at = base + 4 * i;
        *dword = u32::from_be_bytes([data[at], data[at + 1], data[at + 2], data[at + 3]]);
    }
    let [a, registration_offset, c, d, e, f, tail_region_length] = dwords;
    Some(TrailerInfo {
        a,
        registration_offset,
        c,
        d,
        e,
        f,
        tail_region_length,
        registration: parse_registration(data, registration_offset),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn trailer_bytes(a: u32, b: u32, c: u32, d: u32, e: u32, f: u32, g: u32) -> Vec<u8> {
        let mut bytes = Vec::new();
        for dword in [a, b, c, d, e, f, g] {
            bytes.extend_from_slice(&dword.to_be_bytes());
        }
        bytes.extend_from_slice(&MARKER);
        bytes
    }

    fn registration_block(tag: u8) -> Vec<u8> {
        let mut block = vec![tag];
        block.extend_from_slice(&17u32.to_le_bytes());
        block.extend_from_slice(REGISTRATION_COMPANY);
        block.extend_from_slice(&5u32.to_le_bytes());
        block.extend_from_slice(REGISTRATION_PRODUCT);
        block.extend_from_slice(&6u32.to_le_bytes());
        block.extend_from_slice(REGISTRATION_CODE);
        block
    }

    #[test]
    fn parses_trailer_and_registration() {
        let mut data = vec![0u8; 100];
        data.extend_from_slice(&registration_block(0x4E));
        data.extend_from_slice(&trailer_bytes(1, 100, 0xE7, 0xE7, 0, 0, 0x190));
        let trailer = parse_trailer(&data).unwrap();
        assert_eq!(trailer.a, 1);
        assert_eq!(trailer.registration_offset, 100);
        assert_eq!(trailer.c, 0xE7);
        assert_eq!(trailer.d, 0xE7);
        assert_eq!(trailer.e, 0);
        assert_eq!(trailer.f, 0);
        assert_eq!(trailer.tail_region_length, 0x190);
        let reg = trailer.registration.unwrap();
        assert_eq!(reg.tag, "N");
        assert_eq!(reg.company, "DASSAULT-SYSTEMES");
        assert_eq!(reg.product, "CATIA");
        assert_eq!(reg.code, "041803");
    }

    #[test]
    fn no_marker_means_no_trailer() {
        let data = vec![0u8; 64];
        assert!(parse_trailer(&data).is_none());
    }

    #[test]
    fn short_buffer_means_no_trailer() {
        let mut data = MARKER.to_vec();
        data[..8].copy_from_slice(&MARKER);
        assert!(parse_trailer(&data).is_none()); // 8 bytes < 36
    }

    #[test]
    fn registration_none_on_bad_tag_or_out_of_range() {
        let mut data = vec![0u8; 200];
        data.extend_from_slice(&registration_block(0x41)); // not 0x4d/0x4e
        data.extend_from_slice(&trailer_bytes(1, 200, 0, 0, 0, 0, 0));
        let trailer = parse_trailer(&data).unwrap();
        assert!(trailer.registration.is_none());
        // Offset beyond the buffer: None, not a panic.
        assert!(parse_registration(&data, u32::MAX).is_none());
    }

    #[test]
    fn registration_none_on_wrong_length_prefixes() {
        let mut block = registration_block(0x4D);
        block[1..5].copy_from_slice(&16u32.to_le_bytes()); // != 17
        let mut data = vec![0u8; 50];
        data.extend_from_slice(&block);
        data.extend_from_slice(&trailer_bytes(1, 50, 0, 0, 0, 0, 0));
        let trailer = parse_trailer(&data).unwrap();
        assert!(trailer.registration.is_none());
    }
}
