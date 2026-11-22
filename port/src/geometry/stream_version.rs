//! Stream-level version-tag and compression-signature census (W19, B9)
//! — the port of the scan-half of the Python reference module
//! ``catpart.geometry.stream_version``
//! (``src/catpart/geometry/stream_version.py``).
//!
//! B9 asks the question the store level cannot answer: do some writer
//! generations carry a *stream-level* alternate version header or a
//! *compressed sub-stream* that fixed-magic scanning walks past? The
//! documented stream-level version artifact so far is GE-V7
//! (``docs/format/geometry.md`` 6.3): the framed ``[u32le L]"2-0"`` /
//! ``"2X-0"`` strings inside ``CGMGeom`` regions — the W19 census
//! generalizes that to the whole ``N-0`` ladder the framing carries.
//!
//! Ported here (the pure byte scans, no crate dependency — port/
//! Cargo.toml §2.1 allows none):
//!
//! - :fn:`scan_version_tags` — every ``[u32le L][L ASCII]`` frame whose
//!   text is version-shaped, counted per text; the text is read at its
//!   exact length ``L`` (a greedy printable match would over-extend a
//!   tag followed by ASCII — the twin's ``_TAG_PREFIX_RE`` law);
//! - :fn:`zlib_pair_count` — valid zlib header pairs (CMF ``0x78`` +
//!   RFC 1950 FCHECK);
//! - :fn:`signature_counts` — the fixed images of gzip/bzip2/xz/
//!   raw-LZMA/lz4/zstd/snappy;
//! - :fn:`block_writer_tag` / :fn:`block_writer_tag_scan` — the
//!   ``36 08`` + 6-printable writer tag at the pinned +112 offset and
//!   anywhere in the first 512 B (the head-drift feature).
//!
//! NOT ported (documented asymmetry, mirror of the Python module
//! docstring): the fail-closed deflate/bz2/xz *verification* arms
//! (``verify_deflate``/``verify_bz2``/``verify_xz``) are stdlib-only in
//! Python and the port ships no compression crate; the parity contract
//! covers the scan arms on the shared synthetic fixtures (the
//! ``PARITY_TAG_BUF``/``PARITY_SIG_BUF`` laws pinned by
//! ``tests/test_stream_version.py`` — mirror tests live here). A
//! signature is never a compression claim; only a verified stream is,
//! and verification runs Python-side.
//!
//! Evidence: ``docs/evidence/2026-11-22-w19-stream-version.md``.

use std::collections::BTreeMap;

/// The framed-tag scan: one length byte in 1..20, three zero bytes,
/// then exactly ``L`` printable bytes (twin:
/// ``stream_version._TAG_PREFIX_RE`` / ``MAX_TAG_TEXT``).
const MAX_TAG_TEXT: u8 = 20;

/// The writer-tag scan window (twin: ``WRITER_TAG_WINDOW``).
const WRITER_TAG_WINDOW: usize = 512;

/// The writer-tag hit cap (twin: ``WRITER_TAG_HITS``).
const WRITER_TAG_HITS: usize = 16;

fn is_printable(b: u8) -> bool {
    (0x20..=0x7e).contains(&b)
}

/// The version-shaped text law (twin:
/// ``stream_version.VERSION_TAG_TEXT_RE``): 1-2 digits, an optional
/// ``X``/``x`` generation letter, one to three dash-separated numeric
/// suffixes — ``2-0``, ``2X-0``, ``10-0``, ``3-1-0`` match;
/// ``Height``, ``2-``, ``-0`` do not.
pub fn is_version_shaped(text: &[u8]) -> bool {
    let n = text.len();
    let mut i = 0usize;
    // 1-2 leading digits
    let d0 = i < n && text[i].is_ascii_digit();
    if !d0 {
        return false;
    }
    i += 1;
    if i < n && text[i].is_ascii_digit() {
        i += 1;
    }
    // optional X/x
    if i < n && (text[i] == b'X' || text[i] == b'x') {
        i += 1;
    }
    // 1-3 dash-separated numeric suffixes
    let mut groups = 0usize;
    while i < n && groups < 3 {
        if text[i] != b'-' {
            return false;
        }
        i += 1;
        let start = i;
        while i < n && text[i].is_ascii_digit() {
            i += 1;
        }
        if i == start {
            return false; // a dash with no digits (``2-``) is refused
        }
        groups += 1;
    }
    i == n && groups >= 1
}

/// Count framed version-shaped strings in ``data`` (twin:
/// ``stream_version.scan_version_tags`` — the whole-buffer arm; the
/// Python census slices territories first).
pub fn scan_version_tags(data: &[u8]) -> BTreeMap<String, usize> {
    let mut counts: BTreeMap<String, usize> = BTreeMap::new();
    let n = data.len();
    let mut i = 0usize;
    while i + 4 <= n {
        let l = data[i];
        if (1..=MAX_TAG_TEXT).contains(&l)
            && data[i + 1] == 0
            && data[i + 2] == 0
            && data[i + 3] == 0
        {
            let start = i + 4;
            let end = start + l as usize;
            if end <= n {
                let text = &data[start..end];
                if text.iter().all(|&b| is_printable(b)) && is_version_shaped(text) {
                    let key = String::from_utf8_lossy(text).into_owned();
                    *counts.entry(key).or_insert(0) += 1;
                }
                i = end;
                continue;
            }
        }
        i += 1;
    }
    counts
}

/// Valid zlib header pairs in ``data``: CMF ``0x78`` with an FCHECK
/// byte satisfying the RFC 1950 law ``(0x78 << 8 | flg) % 31 == 0``
/// (twin: ``stream_version._count_zlib_pairs`` / ``ZLIB_FLG_VALID``).
pub fn zlib_pair_count(data: &[u8]) -> usize {
    let mut n = 0usize;
    let mut i = 0usize;
    while i + 1 < data.len() {
        if data[i] == 0x78 && (0x7800 | data[i + 1] as u32).is_multiple_of(31) {
            n += 1;
            i += 2;
        } else {
            i += 1;
        }
    }
    n
}

fn count_fixed(data: &[u8], sig: &[u8]) -> usize {
    if sig.is_empty() || data.len() < sig.len() {
        return 0;
    }
    let mut n = 0usize;
    let mut i = 0usize;
    while i + sig.len() <= data.len() {
        if &data[i..i + sig.len()] == sig {
            n += 1;
            i += 1;
        } else {
            i += 1;
        }
    }
    n
}

/// The bzip2 image: ``BZh`` + level 1-9 + the block magic ``1AY&SY``
/// (twin: ``stream_version.SIG_BZIP2``).
fn bzip2_count(data: &[u8]) -> usize {
    let mut n = 0usize;
    let mut i = 0usize;
    while i + 10 <= data.len() {
        if data[i] == b'B'
            && data[i + 1] == b'Z'
            && data[i + 2] == b'h'
            && (b'1'..=b'9').contains(&data[i + 3])
            && &data[i + 4..i + 10] == b"1AY&SY"
        {
            n += 1;
            i += 10;
            continue;
        }
        i += 1;
    }
    n
}

/// The signature census (twin: ``stream_version.scan_compression_signatures``).
///
/// Signature presence, never a compression claim; raw-LZMA ``5D 00 00``
/// is the highest-false-positive row and stays a candidate count.
pub fn signature_counts(data: &[u8]) -> BTreeMap<&'static str, usize> {
    let mut m = BTreeMap::new();
    m.insert("zlib_pair", zlib_pair_count(data));
    m.insert("gzip", count_fixed(data, b"\x1f\x8b\x08"));
    m.insert("bzip2", bzip2_count(data));
    m.insert("xz", count_fixed(data, b"\xfd7zXZ\x00"));
    m.insert("lzma_raw", count_fixed(data, b"\x5d\x00\x00"));
    m.insert("lz4_frame", count_fixed(data, b"\x04\x22\x4d\x18"));
    m.insert("zstd", count_fixed(data, b"\x28\xb5\x2f\xfd"));
    m.insert("snappy", count_fixed(data, b"\xff\x06\x00\x00sNaPpY"));
    m
}

/// The writer tag at ``blk+112`` (twin:
/// ``stream_version.block_writer_tag``): the ``36 08`` pair followed by
/// 6 printable bytes, per the bulk-stream anchors' layout.
pub fn block_writer_tag(data: &[u8], blk: usize) -> Option<String> {
    let start = blk + 112;
    let head = data.get(start..start + 8)?;
    if head[0] != 0x36 || head[1] != 0x08 || !head[2..].iter().all(|&b| is_printable(b)) {
        return None;
    }
    Some(String::from_utf8_lossy(&head[2..]).into_owned())
}

/// Every writer tag in ``[blk, blk+512)`` (twin:
/// ``stream_version.block_writer_tag_scan``) — the drift feature: where
/// the tag sits and what it says, per block family.
pub fn block_writer_tag_scan(data: &[u8], blk: usize) -> Vec<(usize, String)> {
    let mut out = Vec::new();
    if blk >= data.len() {
        return out;
    }
    let end = (blk + WRITER_TAG_WINDOW).min(data.len());
    let mut i = blk;
    while i + 8 <= end && out.len() < WRITER_TAG_HITS {
        if data[i] == 0x36 && data[i + 1] == 0x08 {
            let six = &data[i + 2..i + 8];
            if six.iter().all(|&b| is_printable(b)) {
                out.push((i - blk, String::from_utf8_lossy(six).into_owned()));
            }
        }
        i += 1;
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Rust mirror of ``TestRustParityFixtures.test_tag_fixture``: the
    /// shared parity buffer counts exactly the two GE-V7 texts — the
    /// length-mismatch ``[4]"2-0"`` tail is refused.
    #[test]
    fn parity_tag_fixture() {
        let mut buf: Vec<u8> = Vec::new();
        buf.extend_from_slice(&3u32.to_le_bytes());
        buf.extend_from_slice(b"2-0");
        buf.extend_from_slice(b"junk");
        buf.extend_from_slice(&4u32.to_le_bytes());
        buf.extend_from_slice(b"2X-0");
        buf.extend_from_slice(&4u32.to_le_bytes());
        buf.extend_from_slice(b"2-0"); // length mismatch: L=4, 3 bytes

        let got = scan_version_tags(&buf);
        assert_eq!(got.get("2-0"), Some(&1));
        assert_eq!(got.get("2X-0"), Some(&1));
        assert_eq!(got.len(), 2);
    }

    /// The greedy-over-extension regression: ``[3]"2-0"`` followed by
    /// printable ``junk`` must read the exact 3-byte text (the twin's
    /// ``_TAG_PREFIX_RE`` law), not ``2-0junk``.
    #[test]
    fn tag_followed_by_ascii_reads_exact_length() {
        let mut buf: Vec<u8> = Vec::new();
        buf.extend_from_slice(&3u32.to_le_bytes());
        buf.extend_from_slice(b"2-0junk");
        let got = scan_version_tags(&buf);
        assert_eq!(got.get("2-0"), Some(&1));
        assert_eq!(got.len(), 1);
    }

    /// Non-version texts are refused (twin: ``test_non_version_text_refused``).
    #[test]
    fn non_version_texts_refused() {
        let mut buf: Vec<u8> = Vec::new();
        for t in [b"Height".as_slice(), b"2-", b"-0", b"2X-"] {
            buf.extend_from_slice(&(t.len() as u32).to_le_bytes());
            buf.extend_from_slice(t);
        }
        assert!(scan_version_tags(&buf).is_empty());
    }

    /// The ladder texts the corpus anchor carries (``1-0``..``29-0``)
    /// all count under the shape law.
    #[test]
    fn ladder_texts_count() {
        let mut buf: Vec<u8> = Vec::new();
        for t in [b"1-0".as_slice(), b"10-0", b"29-0", b"3-1-0"] {
            buf.extend_from_slice(&(t.len() as u32).to_le_bytes());
            buf.extend_from_slice(t);
        }
        let got = scan_version_tags(&buf);
        assert_eq!(got.len(), 4);
        assert_eq!(got.get("29-0"), Some(&1));
        assert_eq!(got.get("3-1-0"), Some(&1));
    }

    /// Rust mirror of ``TestRustParityFixtures.test_signature_fixture``.
    #[test]
    fn parity_signature_fixture() {
        let mut buf: Vec<u8> = Vec::new();
        buf.extend_from_slice(b"\x78\x9c");
        buf.extend_from_slice(b"\x78\x00"); // invalid FCHECK: not a pair
        buf.extend_from_slice(b"\x1f\x8b\x08");
        buf.extend_from_slice(b"\x00");
        buf.extend_from_slice(b"\xfd7zXZ\x00");
        buf.extend_from_slice(b"\x28\xb5\x2f\xfd");
        let got = signature_counts(&buf);
        assert_eq!(got["zlib_pair"], 1);
        assert_eq!(got["gzip"], 1);
        assert_eq!(got["xz"], 1);
        assert_eq!(got["zstd"], 1);
        assert_eq!(got["bzip2"], 0);
        assert_eq!(got["lz4_frame"], 0);
        assert_eq!(got["snappy"], 0);
    }

    /// The FCHECK law: every FLG with ``(0x7800 | flg) % 31 == 0``
    /// counts; ``0x00`` does not (RFC 1950).
    #[test]
    fn zlib_fcheck_law() {
        assert_eq!(zlib_pair_count(&[0x78, 0x9c]), 1);
        assert_eq!(zlib_pair_count(&[0x78, 0xda]), 1);
        assert_eq!(zlib_pair_count(&[0x78, 0x01]), 1);
        assert_eq!(zlib_pair_count(&[0x78, 0x00]), 0);
        assert_eq!(zlib_pair_count(&[0x79, 0x9c]), 0);
    }

    /// Writer tag: the +112 law reads ``FINJPL`` on the synthetic block
    /// and the scan finds it when the layout moves (twin:
    /// ``TestWriterTag``).
    #[test]
    fn writer_tag_law_and_drift() {
        let mut buf = vec![0u8; 130];
        buf[112..114].copy_from_slice(b"\x36\x08");
        buf[114..120].copy_from_slice(b"FINJPL");
        assert_eq!(block_writer_tag(&buf, 0).as_deref(), Some("FINJPL"));
        assert_eq!(
            block_writer_tag_scan(&buf, 0),
            vec![(112, "FINJPL".to_string())]
        );

        let mut moved = vec![0u8; 140];
        moved[130..132].copy_from_slice(b"\x36\x08");
        moved[132..138].copy_from_slice(b"FINJPL");
        assert_eq!(block_writer_tag(&moved, 0), None);
        assert_eq!(
            block_writer_tag_scan(&moved, 0),
            vec![(130, "FINJPL".to_string())]
        );

        let mut nonp = vec![0u8; 120];
        nonp[112..114].copy_from_slice(b"\x36\x08");
        nonp[114..120].copy_from_slice(&[0x01, 0x02, 0x03, 0x04, 0x05, 0x06]);
        assert_eq!(block_writer_tag(&nonp, 0), None);
        assert!(block_writer_tag_scan(&nonp, 0).is_empty());
    }
}
