//! The CATIA identity block: the save-time document name (schema v1) —
//! the port of the Python reference module ``catpart.identity``
//! (``src/catpart/identity.py``), per spec §2.1 of
//! ``docs/specs/phase5-viewer-spec.md`` (document_name, C3).
//!
//! The twin's docstring carries the walk model (claim D2) and the
//! presence rates; this port cites, never restates. The behavior is
//! mirrored 1:1 including the fail-closed arm: the walk never raises —
//! a file with no identity block, with more than one, or with a
//! malformed walk yields ``None`` (the corpus never shows these —
//! D1/D2 — so ``None`` is also the honest "not documented for this
//! file" value). The unit-system side of the phase A probe is a
//! **documented negative**, so this module parses names only — there
//! is deliberately no units field (docs/format/payload-blocks.md,
//! section 5.3).
//!
//! Evidence (the same citations the twin's docstring carries):
//!
//! - ``docs/evidence/2026-11-08-units-names-probe.md`` (C3 phase A,
//!   ticket #25 — claims D1/D2/D4, the save-time-name exceptions)
//! - ``docs/evidence/2026-11-07-container-payload-layout.md`` ("The
//!   CATIA identity block")
//! - ``docs/format/payload-blocks.md`` section 5.3 (the documented
//!   negative: no unit-system structure)
//!
//! Numeric contract (spec §2.2 point 3): decode module — the
//! ``suboptimal_flops`` allow below is the pinned carve-out (mul_add
//! changes rounding and flips exact-equality decisions); see the
//! crate docs in ``lib.rs`` for the full policy.
#![allow(clippy::suboptimal_flops)]

/// The 2-byte storage-block tag (twin: :data:`catpart.identity.BLOCK_TAG`).
pub const BLOCK_TAG: [u8; 2] = [0x34, 0x12];
/// The storage-block name (twin: :data:`catpart.identity.STORAGE_WORD`).
pub const STORAGE_WORD: &[u8] = b"CATStorageProperty";
/// The block-header marker (twin: :data:`catpart.identity.UNICODE_STRING`).
pub const UNICODE_STRING: &[u8] = b"CATUnicodeString";
/// The 6-byte property-name header preceding each tag34 name length
/// (twin: :data:`catpart.identity.NAME_HEADER6`).
pub const NAME_HEADER6: [u8; 6] = [0xa0, 0x02, 0x00, 0x00, 0x00, 0x00];
/// The tag34 name-length marker (twin: :data:`catpart.identity.NAME_TAG`).
pub const NAME_TAG: u8 = 0x34;
/// The identity block's name1 (twin: :data:`catpart.identity.IDENTITY_NAME`).
pub const IDENTITY_NAME: &[u8] = b"CATIA";

/// C3b follow bytes that terminate a tag34 name (0x9f or a type tag;
/// twin: :data:`catpart.identity.TERMINATORS`).
pub const TERMINATORS: [u8; 4] = [0x80, 0x9F, 0xA0, 0xE0];

/// Tag34 lengths are u8 (twin: ``catpart.identity._NAME_LIMIT`` —
/// documentation of the length ceiling, carried like the twin carries it).
pub const NAME_LIMIT: usize = 255;

/// ``CATUnicodeString`` sits within the block header (twin:
/// ``catpart.identity._MARKER_WINDOW``).
const MARKER_WINDOW: usize = 64;

/// ``buf.find(needle, start, end)`` — the first occurrence fully inside
/// ``haystack[start..end]``, or ``None`` (the twin scans with
/// :meth:`bytes.find`).
fn find_between(haystack: &[u8], needle: &[u8], start: usize, end: usize) -> Option<usize> {
    if needle.is_empty() {
        return Some(start.min(end));
    }
    if end > haystack.len() || start >= end || needle.len() > end - start {
        return None;
    }
    let last = end - needle.len();
    let mut i = start;
    while i <= last {
        if haystack[i] == needle[0] && &haystack[i..i + needle.len()] == needle {
            return Some(i);
        }
        i += 1;
    }
    None
}

/// ``buf.find(needle, from)`` over the whole buffer.
fn find_from(haystack: &[u8], needle: &[u8], from: usize) -> Option<usize> {
    find_between(haystack, needle, from, haystack.len())
}

/// Python :meth:`str.isprintable` on an ASCII-decoded string
/// (``0x20..=0x7E``; the name decodes as ASCII before the check).
fn ascii_printable(bytes: &[u8]) -> bool {
    bytes.iter().all(|&b| (0x20..=0x7e).contains(&b))
}

fn ascii_string(bytes: &[u8]) -> Option<String> {
    if bytes.iter().all(|&b| b < 0x80) {
        String::from_utf8(bytes.to_vec()).ok()
    } else {
        None
    }
}

fn is_terminator(byte: u8) -> bool {
    TERMINATORS.contains(&byte)
}

/// Return the save-time document name carried by the identity block
/// (twin: :func:`catpart.identity.parse_document_name`).
///
/// The whole file is scanned for storage blocks (the identity block
/// sits in the early property area, but claim D1 was measured
/// whole-file). Returns ``None`` when the file carries no identity
/// block, more than one, or when the name2 field is empty or its walk
/// fails — never fails on malformed input.
pub fn parse_document_name(data: &[u8]) -> Option<String> {
    let mut blocks: Vec<usize> = Vec::new();
    let mut pos = find_from(data, STORAGE_WORD, 0);
    while let Some(at) = pos {
        let blk = if at >= 2 && data[at - 2..at] == BLOCK_TAG {
            at - 2
        } else {
            at
        };
        if read_name1(data, blk).as_deref() == Some("CATIA") {
            blocks.push(blk);
            if blocks.len() > 1 {
                return None; // D1: exactly one identity block; never guess
            }
        }
        pos = find_from(data, STORAGE_WORD, at + 1);
    }
    let first = *blocks.first()?;
    read_name2(data, first)
}

/// name1 of the storage block at ``blk``, or ``None`` if malformed
/// (twin: :func:`catpart.identity._read_name1`).
fn read_name1(buf: &[u8], blk: usize) -> Option<String> {
    let bi = find_between(buf, UNICODE_STRING, blk, blk.saturating_add(MARKER_WINDOW))?;
    if bi + 24 > buf.len() {
        return None;
    }
    if buf[bi + 16..bi + 22] != NAME_HEADER6 || buf[bi + 22] != NAME_TAG {
        return None;
    }
    let ln = buf[bi + 23] as usize;
    let p = bi + 24 + ln;
    if ln == 0 || p >= buf.len() || !is_terminator(buf[p]) {
        return None;
    }
    let decoded = ascii_string(&buf[bi + 24..p])?;
    if ascii_printable(decoded.as_bytes()) {
        Some(decoded)
    } else {
        None
    }
}

/// name2 of the identity block at ``blk``; ``None`` when
/// absent/malformed (twin: :func:`catpart.identity._read_name2`).
fn read_name2(buf: &[u8], blk: usize) -> Option<String> {
    let bi = find_between(buf, UNICODE_STRING, blk, blk.saturating_add(MARKER_WINDOW))?;
    if bi + 24 > buf.len() {
        return None;
    }
    if buf[bi + 16..bi + 22] != NAME_HEADER6 || buf[bi + 22] != NAME_TAG {
        return None;
    }
    let p = bi + 24 + buf[bi + 23] as usize;
    if p + 8 >= buf.len() || !is_terminator(buf[p]) {
        return None;
    }
    if buf[p + 1..p + 7] != NAME_HEADER6 || buf[p + 7] != NAME_TAG {
        return None;
    }
    let ln2 = buf[p + 8] as usize;
    let end = p + 9 + ln2;
    if end >= buf.len() || !is_terminator(buf[end]) {
        return None;
    }
    if ln2 == 0 {
        return None;
    }
    let decoded = ascii_string(&buf[p + 9..end])?;
    if ascii_printable(decoded.as_bytes()) {
        Some(decoded)
    } else {
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The B3 block header + name1/name2 walk the twin documents —
    /// byte-for-byte ``tests/fixtures_gen.py::storage_property_block``.
    fn identity_block(name2: &[u8]) -> Vec<u8> {
        let mut block = Vec::new();
        block.extend_from_slice(&BLOCK_TAG); // 34 12
        block.extend_from_slice(STORAGE_WORD);
        block.extend_from_slice(&[
            0x80, 0x01, 0x00, 0x00, 0x00, 0x00, 0x22, 0x0c, 0x00, 0x00, 0x00,
        ]);
        block.extend_from_slice(&[0x34, 0x01, 0x01, 0x00, 0x34, 0x10]);
        block.extend_from_slice(UNICODE_STRING); // bi = blk + 37
        block.extend_from_slice(&NAME_HEADER6); // bi+16..bi+22
        block.extend_from_slice(&[NAME_TAG, 0x05]); // tag34, len(name1)
        block.extend_from_slice(b"CATIA"); // name1 at bi+24
        block.push(0x9F); // name1 terminator at p
        block.extend_from_slice(&NAME_HEADER6); // p+1..p+7
        block.extend_from_slice(&[NAME_TAG, name2.len() as u8]); // p+7, p+8
        block.extend_from_slice(name2); // p+9..end
        block.push(0x9F); // end terminator
        block.extend_from_slice(&[0x3b, 0x10]);
        block.extend_from_slice(&[0u8; 16]); // null GUID slot
        block.push(0x9F);
        block
    }

    #[test]
    fn reads_save_time_document_name() {
        let mut data = vec![0u8; 40];
        data.extend_from_slice(&identity_block(b"Box.CATPart"));
        assert_eq!(parse_document_name(&data).as_deref(), Some("Box.CATPart"));
    }

    #[test]
    fn empty_name2_is_none() {
        let mut data = vec![0u8; 40];
        data.extend_from_slice(&identity_block(b""));
        assert_eq!(parse_document_name(&data), None);
    }

    #[test]
    fn no_identity_block_is_none() {
        let data = vec![0u8; 128];
        assert_eq!(parse_document_name(&data), None);
    }

    #[test]
    fn non_catia_name1_is_not_an_identity_block() {
        let mut block = identity_block(b"X.CATPart");
        // name1 sits at bi+24..bi+29; rename it below CATIA.
        let name1_at = 2 + STORAGE_WORD.len() + 11 + 6 + UNICODE_STRING.len() + 8;
        block[name1_at] = b'Z';
        let mut data = vec![0u8; 40];
        data.extend_from_slice(&block);
        assert_eq!(parse_document_name(&data), None);
    }

    #[test]
    fn two_identity_blocks_fail_closed() {
        // D1: exactly one identity block; never guess.
        let mut data = vec![0u8; 40];
        data.extend_from_slice(&identity_block(b"A.CATPart"));
        data.extend_from_slice(&identity_block(b"B.CATPart"));
        assert_eq!(parse_document_name(&data), None);
    }

    #[test]
    fn storage_word_without_block_tag_blk_is_the_word_itself() {
        // The twin adjusts blk by -2 only when the 34 12 tag precedes.
        let mut data = vec![0u8; 40];
        let mut block = identity_block(b"X.CATPart");
        block.drain(..2); // drop the BLOCK_TAG: blk = word position itself
        data.extend_from_slice(&block);
        assert_eq!(parse_document_name(&data).as_deref(), Some("X.CATPart"));
    }

    #[test]
    fn non_printable_name_is_none() {
        let mut data = vec![0u8; 40];
        let mut block = identity_block(b"abc");
        // Overwrite the 3 name2 bytes with control characters: the ASCII
        // decode succeeds, the printability check fails.
        let name2_at = block
            .windows(3)
            .position(|window| window == b"abc")
            .unwrap();
        block[name2_at] = 0x01;
        block[name2_at + 1] = 0x01;
        block[name2_at + 2] = 0x01;
        data.extend_from_slice(&block);
        assert_eq!(parse_document_name(&data), None);
    }

    #[test]
    fn truncated_walk_never_fails() {
        // Every prefix of a valid identity block: the walk returns
        // None or the name, never an error/panic.
        let full = identity_block(b"Box.CATPart");
        for cut in 0..full.len() {
            let mut data = vec![0u8; 40];
            data.extend_from_slice(&full[..cut]);
            let _ = parse_document_name(&data);
        }
    }
}
