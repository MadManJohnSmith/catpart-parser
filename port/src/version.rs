//! Per-file version detection via the embedded CNEXTINFOS release
//! marker — the port of the Python reference module
//! ``catpart.version`` (``src/catpart/version.py``), per spec §2.1 of
//! ``docs/specs/phase5-viewer-spec.md`` (CNEXTINFOS detection).
//!
//! The twin's docstring carries the anchored token rule (a release
//! token counts only when ``CNEXTINFOS`` occurs within the 128 bytes
//! preceding it — the naive ``V5 Rxx`` patterns are a documented
//! negative) and the windowing (8 KB primary, 64 KB fallback, else
//! ``unknown``); this port cites, never restates. The scan mirrors the
//! evidence scan exactly, including the leftmost-anchored-token rule
//! (the marker line repeats across saves; the evidence distribution is
//! the leftmost token, header_scan.py rule) and the non-overlapping
//! match consumption of the twin's :meth:`re.Pattern.finditer` — a
//! straddling token missed by the truncated primary window is
//! recovered by the fallback, matching the scan's counting rule.
//!
//! Evidence (the same citations the twin's docstring carries):
//!
//! - ``docs/evidence/2026-11-07-container-triage.md`` ("Per-file
//!   version marker" — the CNEXTINFOS-anchored release token, the
//!   windowing counts, the naive-pattern negative)
//!
//! Numeric contract (spec §2.2 point 3): decode module — the
//! ``suboptimal_flops`` allow below is the pinned carve-out (mul_add
//! changes rounding and flips exact-equality decisions); see the
//! crate docs in ``lib.rs`` for the full policy.
#![allow(clippy::suboptimal_flops)]

/// The ``unknown`` bucket (twin: :data:`catpart.version.UNKNOWN`).
pub const UNKNOWN: &str = "unknown";
/// Primary window (twin: :data:`catpart.version.PRIMARY_WINDOW`) —
/// 1402/1818 corpus files.
pub const PRIMARY_WINDOW: usize = 8192;
/// Fallback window (twin: :data:`catpart.version.FALLBACK_WINDOW`) —
/// +78 files, 1480/1818 = 81.4%.
pub const FALLBACK_WINDOW: usize = 65536;

/// Prefix bytes of the documented marker line (twin:
/// ``catpart.version._ANCHOR``): ``CNEXTINFOS``.
const ANCHOR: &[u8] = b"CNEXTINFOS";
/// 128 leaves headroom for line-form variation while still anchoring
/// the token to the line (twin: ``_ANCHOR_SPAN``; the documented line
/// carries the anchor 64 bytes back).
const ANCHOR_SPAN: usize = 128;

/// The window that produced the version (twin:
/// ``catpart.version.Window``): ``"8k" | "64k" | "unknown"``.
pub type Window = &'static str;

/// Try to match the twin's anchored release-token pattern
/// ``V5R(\d{2})SP(\d+)HF(\d+)`` at ``at``; return the token's end
/// offset. Hand-rolled because the crate carries no regex dependency
/// (spec §2.1: exactly serde/serde_json/wasm-bindgen) — the shape is
/// literal ``V5R``, exactly two digits, ``SP``, one-or-more digits,
/// ``HF``, one-or-more digits (greedy backtracking can never rescue a
/// failed ``HF`` placement: every backtrack position starts with a
/// digit, never ``H``).
fn token_end(view: &[u8], at: usize) -> Option<usize> {
    let mut i = at;
    if view.get(i..i + 3)? != b"V5R" {
        return None;
    }
    i += 3;
    for _ in 0..2 {
        if !view.get(i)?.is_ascii_digit() {
            return None;
        }
        i += 1;
    }
    if view.get(i..i + 2)? != b"SP" {
        return None;
    }
    i += 2;
    let sp_digits_start = i;
    while view.get(i).is_some_and(u8::is_ascii_digit) {
        i += 1;
    }
    if i == sp_digits_start || view.get(i..i + 2)? != b"HF" {
        return None;
    }
    i += 2;
    let hf_digits_start = i;
    while view.get(i).is_some_and(u8::is_ascii_digit) {
        i += 1;
    }
    if i == hf_digits_start {
        return None;
    }
    Some(i)
}

/// :func:`detect_version` plus the window that produced it (twin:
/// :func:`catpart.version.detect_version_with_window`).
///
/// Returns ``(version, window)`` with ``window`` in ``{"8k", "64k",
/// "unknown"}`` — the bucket split behind the evidence counts (1402 in
/// 8 KB, +78 in the 64 KB fallback, 338 unknown). The manifest-backfill
/// script reports this split.
pub fn detect_version_with_window(data: &[u8]) -> (String, Window) {
    for (name, window) in [("8k", PRIMARY_WINDOW), ("64k", FALLBACK_WINDOW)] {
        let view = &data[..data.len().min(window)];
        // finditer semantics: matches are consumed non-overlapping,
        // left to right, whether or not the anchor check accepts them.
        let mut i = 0usize;
        while i < view.len() {
            match token_end(view, i) {
                Some(end) => {
                    let head_start = i.saturating_sub(ANCHOR_SPAN);
                    if contains(&view[head_start..i], ANCHOR) {
                        // The token bytes are ASCII by construction.
                        let token = String::from_utf8_lossy(&view[i..end]).into_owned();
                        return (token, name);
                    }
                    i = end;
                }
                None => i += 1,
            }
        }
    }
    (UNKNOWN.to_string(), "unknown")
}

/// Return the release marker in ``data``, or [`UNKNOWN`] (twin:
/// :func:`catpart.version.detect_version`): the primary 8 KB window
/// first, then the 64 KB fallback window, else the unknown bucket.
pub fn detect_version(data: &[u8]) -> String {
    detect_version_with_window(data).0
}

/// ``needle in haystack`` for byte slices (the twin scans with
/// ``in`` over the anchor window).
fn contains(haystack: &[u8], needle: &[u8]) -> bool {
    needle.is_empty()
        || haystack
            .windows(needle.len())
            .any(|window| window == needle)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn marker_line(release: &str) -> Vec<u8> {
        let mut bytes = b"NOTHING-CNEXTINFOS-UpdateVersion-StreamBlock-".to_vec();
        bytes.extend_from_slice(b"SafeEarlyBlock-StrongEarly&");
        bytes.extend_from_slice(release.as_bytes());
        bytes.extend_from_slice(b" built on 01-15-2014.20.00");
        bytes
    }

    #[test]
    fn detects_anchored_token_in_primary_window() {
        let mut data = vec![0u8; 0x600];
        data.extend_from_slice(&marker_line("V5R21SP0HF0"));
        assert_eq!(detect_version(&data), "V5R21SP0HF0");
        assert_eq!(detect_version_with_window(&data).1, "8k");
    }

    #[test]
    fn unanchored_token_is_not_a_marker() {
        // The release token without CNEXTINFOS in the preceding 128 bytes:
        // the documented negative (naive patterns).
        let mut data = vec![0u8; 0x600];
        data.extend_from_slice(b"plain V5R21SP0HF0 token, no anchor");
        assert_eq!(detect_version(&data), UNKNOWN);
    }

    #[test]
    fn fallback_window_recovers_straddling_token() {
        // The token straddles the 8 KB boundary: missed by the truncated
        // primary window, recovered by the 64 KB fallback.
        let mut data = vec![0u8; 0];
        data.extend_from_slice(&vec![0u8; PRIMARY_WINDOW - 4]);
        data.extend_from_slice(&marker_line("V5R19SP0HF0"));
        assert_eq!(detect_version_with_window(&data).1, "64k");
        assert_eq!(detect_version(&data), "V5R19SP0HF0");
    }

    #[test]
    fn leftmost_anchored_token_wins() {
        let mut data = vec![0u8; 0x600];
        data.extend_from_slice(&marker_line("V5R16SP0HF0"));
        data.extend_from_slice(&marker_line("V5R21SP0HF0"));
        assert_eq!(detect_version(&data), "V5R16SP0HF0");
    }

    #[test]
    fn no_marker_anywhere_is_unknown() {
        let data = vec![0x42u8; 70000];
        assert_eq!(
            detect_version_with_window(&data),
            (UNKNOWN.to_string(), "unknown")
        );
    }

    #[test]
    fn malformed_token_shapes_decline() {
        // \d{2}: one release digit is not a token.
        let mut one_digit = vec![0u8; 16];
        one_digit.extend_from_slice(b"CNEXTINFOS V5R1SP0HF0");
        assert_eq!(detect_version(&one_digit), UNKNOWN);
        // \d+ after HF is mandatory.
        let mut no_hf_digits = vec![0u8; 16];
        no_hf_digits.extend_from_slice(b"CNEXTINFOS V5R19SP0HF");
        assert_eq!(detect_version(&no_hf_digits), UNKNOWN);
        // \d+ after SP is mandatory.
        let mut no_sp_digits = vec![0u8; 16];
        no_sp_digits.extend_from_slice(b"CNEXTINFOS V5R19SPHF0");
        assert_eq!(detect_version(&no_sp_digits), UNKNOWN);
    }
}
