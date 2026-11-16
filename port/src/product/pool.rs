//! The CATProduct structure pool item chain and Law-B typing.
//!
//! Authority: `docs/specs/phase6-assembly-viewer-spec.md` (§2.2) and
//! `docs/evidence/2026-11-14-p2-pool-pairing.md` (§3).
//! Reference implementation: `scripts/triage/p2_pool_pairing.py`.
//!
//! # Item Chain Tiling Law
//!
//! The pool payload tiles completely into two item types with zero padding
//! and zero delimiters:
//!
//! 1. **SHORT item (Law B)**: `<u8 L> <L-1 payload bytes>`, $L \ge 1$.
//!    $L = 1$ is the zero-length string `""`. Payload is UTF-8 text (or binary values
//!    in inline-value generations) with optional newlines `\n`.
//! 2. **LONG item (00-escape)**: `<0x00> <u32le n> <n payload bytes>`, $n \ge 1$.
//!    Carries relation strings (e.g. `CtorToProd:...`) or binary blocks.

#![allow(clippy::suboptimal_flops)]

use serde::{Deserialize, Serialize};

/// The binary sentinel for non-text payloads (matches no pairing classifier).
pub const BINARY_SENTINEL: &str = "\0binary";

/// Class tokens observed as record anchors (successor = an object name value).
pub const CLASS_TOKENS: &[&str] = &[
    "ASMPRODUCT",
    "PRDREP",
    "PRDBAGREP",
    "CONNECTOR",
    "CONNECTION",
    "CONNECTORSFAMILY",
    "ASMGEOMETRY",
    "PUBLISHING",
    "IsRoot",
    "ElecLogTerm",
    "ElecLogicalTermination",
    "ElecCavity",
    "AdaptativeSupport",
    "R15HEADER",
];

/// Item classification in the structure pool chain.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ItemKind {
    /// SHORT item (Law B: length = chars + 1).
    Short,
    /// LONG item (00-escape followed by u32le exact byte count).
    Long,
}

/// A decoded item in the structure pool chain.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PoolItem<'a> {
    pub kind: ItemKind,
    pub offset: usize,
    pub total_len: usize,
    pub payload: &'a [u8],
}

/// Acceptable byte range for text items: UTF-8 printable text, `\n`, and high bytes (accented characters).
#[inline]
pub fn is_text_byte(b: u8) -> bool {
    b == 0x0A || (0x20..=0x7E).contains(&b) || (0x80..=0xFF).contains(&b)
}

/// Check if all bytes in a payload belong to the text byte class.
pub fn is_text_payload(payload: &[u8]) -> bool {
    payload.iter().copied().all(is_text_byte)
}

/// Check if a token string represents an attribute token (leading underscore).
#[inline]
pub fn is_token(s: &str) -> bool {
    s.starts_with('_')
}

/// Check if a string is one of the known class tokens.
#[inline]
pub fn is_class_token(s: &str) -> bool {
    CLASS_TOKENS.contains(&s)
}

/// Match CATIA dot-shaped instance names: `^.+\.\d{1,4}$`.
pub fn is_dot_shape(s: &str) -> bool {
    match s.rfind('.') {
        Some(pos) if pos > 0 => {
            let suffix = &s[pos + 1..];
            (1..=4).contains(&suffix.len()) && suffix.chars().all(|c| c.is_ascii_digit())
        }
        _ => false,
    }
}

/// Match CATIA colon-shaped instance names: `^.+:\d{1,4}$`.
pub fn is_colon_shape(s: &str) -> bool {
    match s.rfind(':') {
        Some(pos) if pos > 0 => {
            let suffix = &s[pos + 1..];
            (1..=4).contains(&suffix.len()) && suffix.chars().all(|c| c.is_ascii_digit())
        }
        _ => false,
    }
}

/// Match CATIA underscore-shaped instance names: `^.+_\d{1,4}$`.
pub fn is_uscore_shape(s: &str) -> bool {
    match s.rfind('_') {
        Some(pos) if pos > 0 => {
            let suffix = &s[pos + 1..];
            (1..=4).contains(&suffix.len()) && suffix.chars().all(|c| c.is_ascii_digit())
        }
        _ => false,
    }
}

/// Walk and tile the item chain within `[start, end)`.
///
/// Returns `(items, tiles_exactly)`.
/// The chain is valid if and only if every item's length fits and the items consume
/// `[start, end)` exactly with zero padding.
pub fn walk_chain<'a>(data: &'a [u8], start: usize, end: usize) -> (Vec<PoolItem<'a>>, bool) {
    if start > end || end > data.len() {
        return (Vec::new(), false);
    }
    let mut items = Vec::new();
    let mut i = start;
    while i < end {
        let head = data[i];
        if head == 0x00 {
            // LONG item: <00> <u32le n> <n bytes>
            if i + 5 > end {
                return (items, false);
            }
            let n = u32::from_le_bytes(data[i + 1..i + 5].try_into().unwrap()) as usize;
            if n == 0 || i + 5 + n > end {
                return (items, false);
            }
            items.push(PoolItem {
                kind: ItemKind::Long,
                offset: i,
                total_len: 5 + n,
                payload: &data[i + 5..i + 5 + n],
            });
            i += 5 + n;
        } else {
            // SHORT item (Law B): <u8 L> <L-1 bytes>
            let len = head as usize;
            if i + len > end {
                return (items, false);
            }
            items.push(PoolItem {
                kind: ItemKind::Short,
                offset: i,
                total_len: len,
                payload: &data[i + 1..i + len],
            });
            i += len;
        }
    }
    let tiled = i == end;
    (items, tiled)
}

/// Decode a sequence of pool items into strings.
/// Text payloads decode as UTF-8 (with replacement characters if invalid UTF-8);
/// binary payloads are replaced with [`BINARY_SENTINEL`].
pub fn decode_pool_texts(items: &[PoolItem<'_>]) -> Vec<String> {
    items
        .iter()
        .map(|item| {
            if is_text_payload(item.payload) {
                String::from_utf8_lossy(item.payload).into_owned()
            } else {
                BINARY_SENTINEL.to_string()
            }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_short_empty_item() {
        // L = 1 -> 0 payload bytes
        let data = [0x01];
        let (items, tiled) = walk_chain(&data, 0, 1);
        assert!(tiled);
        assert_eq!(items.len(), 1);
        assert_eq!(items[0].kind, ItemKind::Short);
        assert_eq!(items[0].total_len, 1);
        assert_eq!(items[0].payload, b"");
        let texts = decode_pool_texts(&items);
        assert_eq!(texts, vec![""]);
    }

    #[test]
    fn parses_short_text_items() {
        // Law B: len = char count + 1
        // "Part001" (7 chars -> len 8)
        let mut data = vec![0x08];
        data.extend_from_slice(b"Part001");
        // "_InstanceName" (13 chars -> len 14 = 0x0e)
        data.push(0x0e);
        data.extend_from_slice(b"_InstanceName");

        let (items, tiled) = walk_chain(&data, 0, data.len());
        assert!(tiled);
        assert_eq!(items.len(), 2);
        assert_eq!(items[0].kind, ItemKind::Short);
        assert_eq!(items[0].payload, b"Part001");
        assert_eq!(items[1].payload, b"_InstanceName");

        let texts = decode_pool_texts(&items);
        assert_eq!(texts, vec!["Part001", "_InstanceName"]);
    }

    #[test]
    fn parses_long_item() {
        let rel = b"CtorToProd:Product!ProdToRep:Shape 1";
        let mut data = vec![0x00];
        data.extend_from_slice(&(rel.len() as u32).to_le_bytes());
        data.extend_from_slice(rel);

        let (items, tiled) = walk_chain(&data, 0, data.len());
        assert!(tiled);
        assert_eq!(items.len(), 1);
        assert_eq!(items[0].kind, ItemKind::Long);
        assert_eq!(items[0].total_len, 5 + rel.len());
        assert_eq!(items[0].payload, rel);

        let texts = decode_pool_texts(&items);
        assert_eq!(texts, vec![std::str::from_utf8(rel).unwrap()]);
    }

    #[test]
    fn fails_closed_on_zero_length_long_item() {
        let data = [0x00, 0x00, 0x00, 0x00, 0x00];
        let (items, tiled) = walk_chain(&data, 0, 5);
        assert!(!tiled);
        assert!(items.is_empty());
    }

    #[test]
    fn fails_closed_on_truncated_long_header() {
        let data = [0x00, 0x01, 0x00];
        let (items, tiled) = walk_chain(&data, 0, 3);
        assert!(!tiled);
        assert!(items.is_empty());
    }

    #[test]
    fn fails_closed_on_truncated_payload() {
        let data = [0x08, b'P', b'a', b'r', b't']; // L=8 requires 7 bytes, got 4
        let (items, tiled) = walk_chain(&data, 0, data.len());
        assert!(!tiled);
        assert!(items.is_empty());
    }

    #[test]
    fn binary_item_yields_sentinel() {
        // L=4 -> 3 bytes payload with control bytes
        let data = [0x04, 0x01, 0x02, 0x03];
        let (items, tiled) = walk_chain(&data, 0, 4);
        assert!(tiled);
        assert_eq!(items.len(), 1);
        assert!(!is_text_payload(items[0].payload));
        let texts = decode_pool_texts(&items);
        assert_eq!(texts, vec![BINARY_SENTINEL]);
    }

    #[test]
    fn shape_predicates() {
        assert!(is_dot_shape("Part001.1"));
        assert!(is_dot_shape("A.B.12"));
        assert!(!is_dot_shape(".1"));
        assert!(!is_dot_shape("Part.12345"));
        assert!(!is_dot_shape("Part."));
        assert!(!is_dot_shape("Part001"));

        assert!(is_colon_shape("ac2:1"));
        assert!(is_colon_shape("SP02:12"));
        assert!(!is_colon_shape("ac2:12345"));
        assert!(!is_colon_shape(":1"));

        assert!(is_uscore_shape("ac2_1"));
        assert!(is_uscore_shape("lengua_8"));
        assert!(!is_uscore_shape("ac2_12345"));
        assert!(!is_uscore_shape("_1"));
    }
}
