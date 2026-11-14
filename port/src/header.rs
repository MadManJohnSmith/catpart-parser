//! The 32-byte outer header of CATIA V5 ``.CATPart``/``.CATProduct``
//! files — the port of the Python reference module ``catpart.header``
//! (``src/catpart/header.py``), per spec §2.1 of
//! ``docs/specs/phase5-viewer-spec.md`` (the module-mapping table;
//! 32-byte header, H1 law).
//!
//! The twin's docstring carries the decoded field model (bytes 0-8
//! magic, big-endian dword8/dword12, the ff x8 marker or the dual-region
//! variant's dword16/dword20); this port cites, never restates. The
//! behavior is mirrored 1:1 including the fail-closed arm:
//! :func:`catpart.header.parse_header` raises :class:`ValueError` when
//! fewer than 32 bytes are available; [`parse_header`] returns
//! [`HeaderError`] carrying the same prose shape (spec §2.4: the detail
//! is human prose, never compared byte-wise — the machine contract is
//! the exit-code class at the CLI seam).
//!
//! Evidence (the same citations the twin's docstring carries):
//!
//! - ``docs/evidence/2026-11-07-container-triage.md`` ("Outer
//!   container structure")
//! - ``docs/evidence/2026-11-07-container-table-and-trailer.md``
//!   ("B1" — the dword12 chain law and the dual-region variant)
//!
//! Numeric contract (spec §2.2 point 3): decode module — the
//! ``suboptimal_flops`` allow below is the pinned carve-out (mul_add
//! changes rounding and flips exact-equality decisions); see the
//! crate docs in ``lib.rs`` for the full policy.
#![allow(clippy::suboptimal_flops)]

/// Twin constant: :data:`catpart.header.HEADER_SIZE`.
pub const HEADER_SIZE: usize = 32;
/// Twin constant: :data:`catpart.header.MAGIC_SIZE`.
pub const MAGIC_SIZE: usize = 8;

/// Bytes 16-24 of a standard-generation header (twin:
/// :data:`catpart.header.FF8`).
const FF8: [u8; 8] = [0xff; 8];

/// The short-buffer refusal (the twin's :class:`ValueError`).
///
/// ``available`` formats into the twin's exact prose shape —
/// ``not a CATIA V5 container: header needs 32 bytes, got N`` — at the
/// CLI seam ([`crate::header`]'s caller); the message is detail prose,
/// never compared byte-wise (spec §3.2).
#[derive(Debug)]
pub struct HeaderError {
    /// The buffer length the parser was handed.
    pub available: usize,
}

impl core::fmt::Display for HeaderError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        write!(
            f,
            "not a CATIA V5 container: header needs {HEADER_SIZE} bytes, got {}",
            self.available
        )
    }
}

/// The documented fields of the outer header (bytes 0-32) — the twin's
/// :class:`catpart.header.HeaderInfo` dataclass. ``header_dword16`` /
/// ``header_dword20`` are ``None`` on the standard ff x8 generation,
/// where bytes 16-24 are the marker itself rather than dwords.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HeaderInfo {
    /// ASCII (latin-1) decoding of bytes 0-8 with trailing NULs stripped.
    pub magic: String,
    /// Big-endian uint32 at bytes 8-12.
    pub header_dword: u32,
    /// Big-endian uint32 at bytes 12-16.
    pub header_dword12: u32,
    /// Bytes 16-24 are eight ``0xFF`` bytes.
    pub ff8_at_16_24: bool,
    /// Big-endian uint32 at bytes 16-20 (dual-region variant only).
    pub header_dword16: Option<u32>,
    /// Big-endian uint32 at bytes 20-24 (dual-region variant only).
    pub header_dword20: Option<u32>,
}

/// Parse the first [`HEADER_SIZE`] bytes of a file (twin:
/// :func:`catpart.header.parse_header`).
///
/// Fails closed with [`HeaderError`] when fewer than 32 bytes are
/// available: the 32-byte header is the smallest documented structure,
/// and a shorter buffer is not a CATIA V5 container (the fitness runner
/// classifies such truncations as crashes). The magic is reported as
/// observed — it is *not* verified here, because 6 corpus files are
/// known to lack it and the tool must still describe them.
pub fn parse_header(head: &[u8]) -> Result<HeaderInfo, HeaderError> {
    if head.len() < HEADER_SIZE {
        return Err(HeaderError {
            available: head.len(),
        });
    }
    // ``head[:8].rstrip(b"\x00")``: strip every trailing NUL byte, then
    // decode latin-1 (each byte value is its own Unicode scalar).
    let mut magic_end = MAGIC_SIZE;
    while magic_end > 0 && head[magic_end - 1] == 0 {
        magic_end -= 1;
    }
    let magic: String = head[..magic_end].iter().map(|&b| b as char).collect();
    let header_dword = u32::from_be_bytes([head[8], head[9], head[10], head[11]]);
    let header_dword12 = u32::from_be_bytes([head[12], head[13], head[14], head[15]]);
    let ff8_at_16_24 = head[16..24] == FF8;
    let (header_dword16, header_dword20) = if ff8_at_16_24 {
        (None, None)
    } else {
        (
            Some(u32::from_be_bytes([head[16], head[17], head[18], head[19]])),
            Some(u32::from_be_bytes([head[20], head[21], head[22], head[23]])),
        )
    };
    Ok(HeaderInfo {
        magic,
        header_dword,
        header_dword12,
        ff8_at_16_24,
        header_dword16,
        header_dword20,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_standard_generation_header() {
        let mut head = [0u8; 32];
        head[..8].copy_from_slice(b"V5_CFV2\x00");
        head[8..12].copy_from_slice(&0x0001_0000u32.to_be_bytes());
        head[12..16].copy_from_slice(&0x0000_0190u32.to_be_bytes());
        head[16..24].copy_from_slice(&FF8);
        let info = parse_header(&head).unwrap();
        assert_eq!(info.magic, "V5_CFV2");
        assert_eq!(info.header_dword, 0x0001_0000);
        assert_eq!(info.header_dword12, 0x0000_0190);
        assert!(info.ff8_at_16_24);
        assert_eq!(info.header_dword16, None);
        assert_eq!(info.header_dword20, None);
    }

    #[test]
    fn parses_dual_region_variant() {
        let mut head = [0u8; 32];
        head[..8].copy_from_slice(b"V5_CFV2\x00");
        head[16..20].copy_from_slice(&0x10u32.to_be_bytes());
        head[20..24].copy_from_slice(&0x20u32.to_be_bytes());
        let info = parse_header(&head).unwrap();
        assert!(!info.ff8_at_16_24);
        assert_eq!(info.header_dword16, Some(0x10));
        assert_eq!(info.header_dword20, Some(0x20));
    }

    #[test]
    fn fails_closed_on_short_buffer() {
        let err = parse_header(&[0u8; 16]).unwrap_err();
        assert_eq!(err.available, 16);
        assert_eq!(
            err.to_string(),
            "not a CATIA V5 container: header needs 32 bytes, got 16"
        );
    }

    #[test]
    fn magic_strips_all_trailing_nuls_and_decodes_latin1() {
        let mut head = [0u8; 32];
        head[..6].copy_from_slice(b"V5_CFV");
        head[6] = 0;
        head[7] = 0;
        // A non-ASCII byte decodes per latin-1 (byte value = code point);
        // it overwrites the '_' of the written prefix.
        head[2] = 0xe9;
        let info = parse_header(&head).unwrap();
        assert_eq!(info.magic, "V5\u{e9}CFV");
    }
}
