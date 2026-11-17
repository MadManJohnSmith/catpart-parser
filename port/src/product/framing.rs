//! CATProduct structure pool framing and candidate selection.
//!
//! Authority: `docs/specs/phase6-assembly-viewer-spec.md` (§2.2) and
//! `docs/evidence/2026-11-14-p2-pool-pairing.md` (§2).
//! Reference implementation: `scripts/triage/p2_pool_pairing.py`.
//!
//! # The Length Law
//!
//! The CATProduct structure pool is framed by a record anchored at `fe 7c 02`:
//!
//! ```text
//! Offset   Length   Field             Description
//! --------------------------------------------------------------------------------------
//! 0x00     2        b"\xfe\x7c"       Frame signature
//! 0x02     1        0x02              Frame tag (structure pool)
//! 0x03     4        u32le ln          Length field (counts bytes from 0x01 through pool end)
//! 0x07     tb       tail_bytes        1-2 bytes (high-bit set; tb in {0, 1, 2})
//! 0x07+tb  pool_span items...         Tiled item chain spanning [0x07+tb, 0x01+ln)
//! ```
//!
//! Length Law (P2-length-law, 100% verified):
//! $$\text{ln} = 6 + tb + \text{pool\_span}$$
//! The record spans $[h, h + 1 + \text{ln})$.
//! Disambiguation requires $\ge 2$ assembly vocabulary tokens from [`POOL_TOKENS`].

#![allow(clippy::suboptimal_flops)]

use serde::{Deserialize, Serialize};

use super::pool::{PoolItem, walk_chain};

/// Framing record anchor signature (`\xfe\x7c`).
pub const FRAME_MARK: [u8; 2] = [0xfe, 0x7c];

/// Frame tag for the structure pool record.
pub const FRAME_TAG_POOL: u8 = 0x02;

/// Census pool tokens used to identify the structure pool among framing candidates.
pub const POOL_TOKENS: &[&str] = &[
    "ASMPRODUCT",
    "PRDREP",
    "PRDBAGREP",
    "_Component",
    "_PartNumber",
    "_RefProduct",
    "_InstanceName",
    "_Position",
    "CONNECTOR",
    "CONNECTION",
    "IsRoot",
    "_Version",
    "_Reps",
    "3DIC",
];

/// Structural pool classification of a CATProduct file.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum PoolForm {
    /// Framed `fe 7c 02` record with tiled item chain satisfying length law & vocabulary gate.
    Framed,
    /// R15 generation attribute-reference form (`80 ... e8/e7` tags).
    R15Ref,
    /// Unframed or unrecognized format.
    Unframed,
}

impl PoolForm {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Framed => "framed",
            Self::R15Ref => "r15-ref",
            Self::Unframed => "unframed",
        }
    }
}

/// A framing record candidate discovered in a CATProduct file.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PoolCandidate<'a> {
    /// Offset of the `0xfe` marker in the file.
    pub header_offset: usize,
    /// Length field `ln` (u32le) at `header_offset + 3`.
    pub length: u32,
    /// Tail bytes count `tb` (0, 1, or 2).
    pub tail_bytes_count: usize,
    /// Start offset of the pool items payload (`header_offset + 7 + tb`).
    pub payload_start: usize,
    /// End offset of the record (`header_offset + 1 + ln`).
    pub payload_end: usize,
    /// The decoded pool items that tile `[payload_start, payload_end)`.
    pub items: Vec<PoolItem<'a>>,
    /// Length law verification result: `ln == 6 + tb + pool_span`.
    pub length_law_ok: bool,
    /// Count of recognized assembly vocabulary tokens among decoded items.
    pub assembly_token_count: usize,
}

/// Verify the Length Law: `ln == 6 + tb + pool_span`.
#[inline]
pub fn verify_length_law(ln: u32, tb: usize, pool_span: usize) -> bool {
    ln as usize == 6 + tb + pool_span
}

/// Count assembly vocabulary tokens in an item list.
pub fn count_assembly_tokens(items: &[PoolItem<'_>]) -> usize {
    items
        .iter()
        .filter(|item| {
            if let Ok(s) = std::str::from_utf8(item.payload) {
                POOL_TOKENS.contains(&s)
            } else {
                false
            }
        })
        .count()
}

/// Scan `data` for all framing records anchored at `fe 7c 02` that tile into $\ge 3$ items.
pub fn scan_framing_candidates<'a>(data: &'a [u8]) -> Vec<PoolCandidate<'a>> {
    let mut candidates = Vec::new();
    if data.len() < 8 {
        return candidates;
    }

    let limit = data.len() - 7;
    for h in 0..limit {
        if data[h] == FRAME_MARK[0] && data[h + 1] == FRAME_MARK[1] {
            if data[h + 2] != FRAME_TAG_POOL {
                continue;
            }
            let ln = u32::from_le_bytes(data[h + 3..h + 7].try_into().unwrap());
            if ln < 8 {
                continue;
            }
            let rec_end = h + 1 + ln as usize;
            if rec_end > data.len() {
                continue;
            }

            for tb in 0..=2 {
                let st = h + 7 + tb;
                if st > rec_end {
                    continue;
                }
                let (items, tiled) = walk_chain(data, st, rec_end);
                if tiled && items.len() >= 3 {
                    let pool_span = rec_end - st;
                    let length_law_ok = verify_length_law(ln, tb, pool_span);
                    let assembly_token_count = count_assembly_tokens(&items);
                    candidates.push(PoolCandidate {
                        header_offset: h,
                        length: ln,
                        tail_bytes_count: tb,
                        payload_start: st,
                        payload_end: rec_end,
                        items,
                        length_law_ok,
                        assembly_token_count,
                    });
                }
            }
        }
    }
    candidates
}

/// Disambiguate and pick the structure pool candidate.
///
/// Requires $\ge 2$ assembly vocabulary tokens among items.
/// Picks candidate with the most items; ties select the first occurrence.
pub fn pick_structure_pool<'a>(candidates: &[PoolCandidate<'a>]) -> Option<PoolCandidate<'a>> {
    let mut best: Option<&PoolCandidate<'a>> = None;
    for cand in candidates {
        if cand.assembly_token_count < 2 {
            continue;
        }
        match best {
            None => best = Some(cand),
            Some(curr) => {
                if cand.items.len() > curr.items.len() {
                    best = Some(cand);
                }
            }
        }
    }
    best.cloned()
}

/// Find the structure pool in `data` by scanning candidates and selecting the winning pool.
pub fn find_structure_pool<'a>(data: &'a [u8]) -> Option<PoolCandidate<'a>> {
    let candidates = scan_framing_candidates(data);
    pick_structure_pool(&candidates)
}

/// Count R15-generation attribute-reference entries (`\xfe\xfe?[\x01-\x7f][name]\x80`).
pub fn r15_reference_count(data: &[u8]) -> usize {
    if data.len() < 10 {
        return 0;
    }
    let mut count = 0;
    let mut i = 0;
    while i < data.len() - 6 {
        if data[i] == 0xfe {
            let mut off = i + 1;
            if off < data.len() && data[off] == 0xfe {
                off += 1;
            }
            if off < data.len() {
                let len_byte = data[off];
                if (1..=127).contains(&len_byte) {
                    let str_len = len_byte as usize - 1;
                    if (3..=60).contains(&str_len)
                        && off + 1 + str_len < data.len()
                        && data[off + 1 + str_len] == 0x80
                        && data[off + 1..off + 1 + str_len]
                            .iter()
                            .all(|&b| (0x20..=0x7E).contains(&b))
                        && let Ok(name_str) = std::str::from_utf8(&data[off + 1..off + 1 + str_len])
                        && (name_str.starts_with('_') || POOL_TOKENS.contains(&name_str))
                    {
                        count += 1;
                    }
                }
            }
        }
        i += 1;
    }
    count
}

/// Extract R15 legacy dot-shaped instance names (`\xfe\xfe?[\x01-\x7f][name]\x80`).
pub fn extract_r15_instance_names(data: &[u8]) -> Vec<String> {
    if data.len() < 10 {
        return Vec::new();
    }
    let mut names = Vec::new();
    let mut i = 0;
    while i < data.len() - 6 {
        if data[i] == 0xfe {
            let mut off = i + 1;
            if off < data.len() && data[off] == 0xfe {
                off += 1;
            }
            if off < data.len() {
                let len_byte = data[off];
                if (1..=127).contains(&len_byte) {
                    let str_len = len_byte as usize - 1;
                    if (3..=60).contains(&str_len)
                        && off + 1 + str_len < data.len()
                        && data[off + 1 + str_len] == 0x80
                        && data[off + 1..off + 1 + str_len]
                            .iter()
                            .all(|&b| (0x20..=0x7E).contains(&b))
                        && let Ok(name_str) = std::str::from_utf8(&data[off + 1..off + 1 + str_len])
                        && crate::product::pool::is_dot_shape(name_str)
                        && !crate::product::pairing::is_constraint_name(name_str)
                    {
                        names.push(name_str.to_string());
                    }
                }
            }
        }
        i += 1;
    }
    names
}

/// Classify the pool format of the document.
pub fn detect_pool_form(data: &[u8]) -> PoolForm {
    if find_structure_pool(data).is_some() {
        PoolForm::Framed
    } else if r15_reference_count(data) >= 3 {
        PoolForm::R15Ref
    } else {
        PoolForm::Unframed
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn build_synthetic_framed_record(tb: usize, items_payload: &[u8]) -> Vec<u8> {
        let pool_span = items_payload.len();
        let ln = (6 + tb + pool_span) as u32;
        let mut rec = Vec::new();
        rec.extend_from_slice(&FRAME_MARK);
        rec.push(FRAME_TAG_POOL);
        rec.extend_from_slice(&ln.to_le_bytes());
        rec.extend_from_slice(&vec![0xbf; tb]); // tail bytes
        rec.extend_from_slice(items_payload);
        rec
    }

    #[test]
    fn length_law_verification() {
        assert!(verify_length_law(2165, 1, 2158));
        assert!(verify_length_law(100, 0, 94));
        assert!(verify_length_law(100, 2, 92));
        assert!(!verify_length_law(2165, 1, 2157));
        assert!(!verify_length_law(2165, 2, 2158));
    }

    #[test]
    fn parses_valid_framed_structure_pool() {
        // Build items: ASMPRODUCT, Product1, _PartNumber, Part001, _InstanceName, Part001.1
        let mut payload = Vec::new();
        payload.push(11);
        payload.extend_from_slice(b"ASMPRODUCT");
        payload.push(9);
        payload.extend_from_slice(b"Product1");
        payload.push(12);
        payload.extend_from_slice(b"_PartNumber");
        payload.push(8);
        payload.extend_from_slice(b"Part001");
        payload.push(14);
        payload.extend_from_slice(b"_InstanceName");
        payload.push(10);
        payload.extend_from_slice(b"Part001.1");

        let rec = build_synthetic_framed_record(1, &payload);
        let mut file_buf = vec![0x12; 50]; // Prefix noise
        file_buf.extend_from_slice(&rec);
        file_buf.extend_from_slice(&[0x34; 50]); // Suffix noise

        let cands = scan_framing_candidates(&file_buf);
        assert_eq!(cands.len(), 1);
        let cand = &cands[0];
        assert_eq!(cand.header_offset, 50);
        assert_eq!(cand.tail_bytes_count, 1);
        assert!(cand.length_law_ok);
        assert_eq!(cand.items.len(), 6);
        assert_eq!(cand.assembly_token_count, 3); // ASMPRODUCT, _PartNumber, _InstanceName

        let chosen = pick_structure_pool(&cands);
        assert!(chosen.is_some());
        assert_eq!(chosen.unwrap().header_offset, 50);
    }

    #[test]
    fn vocabulary_gate_rejects_under_two_tokens() {
        // 3 items, but only 1 assembly token (_InstanceName)
        let mut payload = Vec::new();
        payload.push(8);
        payload.extend_from_slice(b"Part001");
        payload.push(14);
        payload.extend_from_slice(b"_InstanceName");
        payload.push(10);
        payload.extend_from_slice(b"Part001.1");

        let rec = build_synthetic_framed_record(1, &payload);
        let cands = scan_framing_candidates(&rec);
        assert_eq!(cands.len(), 1);
        assert_eq!(cands[0].assembly_token_count, 1);

        // Vocabulary gate strictly requires >= 2 tokens
        let chosen = pick_structure_pool(&cands);
        assert!(chosen.is_none());
    }

    #[test]
    fn tie_breaking_picks_first_candidate() {
        let mut payload1 = Vec::new();
        payload1.push(11);
        payload1.extend_from_slice(b"ASMPRODUCT");
        payload1.push(9);
        payload1.extend_from_slice(b"Product1");
        payload1.push(7);
        payload1.extend_from_slice(b"PRDREP");

        let mut payload2 = Vec::new();
        payload2.push(11);
        payload2.extend_from_slice(b"ASMPRODUCT");
        payload2.push(9);
        payload2.extend_from_slice(b"Product2");
        payload2.push(7);
        payload2.extend_from_slice(b"PRDREP");

        let mut file = build_synthetic_framed_record(1, &payload1);
        file.extend_from_slice(&build_synthetic_framed_record(1, &payload2));

        let cands = scan_framing_candidates(&file);
        assert_eq!(cands.len(), 2);
        let chosen = pick_structure_pool(&cands).unwrap();
        // Ties -> first
        assert_eq!(chosen.header_offset, 0);
    }

    #[test]
    fn detect_pool_form_classification() {
        let empty = vec![0u8; 100];
        assert_eq!(detect_pool_form(&empty), PoolForm::Unframed);

        let mut payload = Vec::new();
        payload.push(11);
        payload.extend_from_slice(b"ASMPRODUCT");
        payload.push(7);
        payload.extend_from_slice(b"PRDREP");
        payload.push(7);
        payload.extend_from_slice(b"IsRoot");
        let framed = build_synthetic_framed_record(1, &payload);
        assert_eq!(detect_pool_form(&framed), PoolForm::Framed);
    }
}
