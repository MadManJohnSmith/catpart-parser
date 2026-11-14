//! Nested V5_CFV2 stream-store navigation (G1 model) — the port of
//! the Python reference module ``catpart.geometry.store``
//! (``src/catpart/geometry/store.py``), per spec §2.1 of
//! ``docs/specs/phase5-viewer-spec.md`` (G1 + the stage-3a/12 probes).
//!
//! Adapted from ``scripts/triage/decode_nested_store.py`` (G1's corpus
//! decoder): the subset the exporter needs to bound a store's body —
//! the CATStdCont block region, the store origin (header / header-less
//! variants) and the catalog start — with the decode semantics
//! unchanged. The behavior is mirrored 1:1 including every fail-closed
//! arm: a region without a store is ``None`` (the G1
//! ``none_in_region``/``embedded_doc`` families), a ``V5_CFV2`` header
//! failing the N2 validation raises ``malformed-store-header``, and a
//! catalog tail neither stage-3a recovery family corrects keeps the
//! shipped rejection (fail-closed). The docstring citations below are
//! the twin's.
//!
//! Model (docs/evidence/2026-11-09-nested-store.md):
//!
//! - A nested store sits in the ``CATStdCont`` block region of a CATIA
//!   V5 file (N1). The region is bounded by the next valid storage
//!   block, the outer header dword8, or EOF (B3 boundary rule minus
//!   CB0001/OSMX, which occur legitimately inside a store region —
//!   correction C1).
//! - Header variant (N1h/N2, 1,056/1,173): a 32-byte header
//!   ``V5_CFV2\0`` + big-endian dword8 (catalog offset from origin) +
//!   big-endian dword12 (catalog tail length) + ff x 8 + zeros x 8; the
//!   catalog magic ``CATIA_V5 CB0001\0`` byte-verifies at
//!   ``origin + dword8`` (N3, 99.0%) or up to 64 B earlier (the
//!   dword8-overshoot variant, correction C3).
//! - Header-less variant (N1l, 12 R19 parts): origin = block start, the
//!   catalog sits directly in the region (found as the first
//!   ``CB0001``), the body starts at origin + 64, and the tail length
//!   is ``region_end - 126 - catalog`` (fallback ``region_end -
//!   catalog``).
//! - Catalog validation. G1 validates through B2's full record walk
//!   (``scan_tail``); the exporter consumes no catalog entries, so it
//!   validates the trailer laws instead — ``CB__END\0`` as the tail's
//!   last 8 bytes, ``C == D`` and ``G == tail length`` (N6, 1,050/1,050)
//!   — a strictly weaker but, combined with the header/magic
//!   requirements, sufficient structural check for the body extent. The
//!   body is ``origin + 32 .. catalog_start`` (header variant) or
//!   ``origin + 64 .. catalog_start`` (header-less).
//! - Recovery extension (stage 3a #34, the L5 lever). Two additions,
//!   both fail-closed, measured on the corpus in
//!   docs/evidence/2026-11-10-l2-grind-classification.md sections 5-6:
//!   (a) the relaxed tail law recovers the two G1-documented tail
//!   variants the shipped window rejects — the dword8-overshoot tail
//!   (C3: read ``[cb, cb + dword12)`` from the true catalog magic) and
//!   the padded tail (end the tail at its ``CB__END``, N4w); a tail
//!   neither family recovers keeps the shipped
//!   ``malformed-store-header`` rejection. (b) the caller may probe
//!   ``CATXDocLinkCont`` and ``CATSeeBodyCont`` regions with the same
//!   law (``container`` records the probing family on the span) —
//!   containers the locator never visited before stage 3a; the exporter
//!   does this only when no ``CATStdCont`` region located a store. Every
//!   recovered store names how it was recovered
//!   (``StoreSpan.container``/``StoreSpan.tail_law``).
//! - Stage 12 (#34, 2026-11-13) adds the final probe family:
//!   ``other-container`` — a store validated in a block region whose
//!   doc-type name is none of the three probed families (the census's
//!   C11 candidate upside, measured in
//!   docs/evidence/2026-11-13-noncomposite-census.md). The block's own
//!   name travels on the summary (``store_recovery.container_name``);
//!   the locator itself is container-name-agnostic — the family only
//!   records provenance.
//!
//! Twin-buffer semantics: ``data`` is any bytes-like buffer supporting
//! slicing, ``find()`` and ``len()`` (``bytes`` or a read-only
//! :class:`mmap.mmap`). Python slices CLAMP out-of-range ends and
//! ``bytes.find`` clamps its end bound; :func:`slice_clamped` and
//! :func:`find` reproduce exactly those semantics so the byte-walking
//! decisions match the twin at every arm (an index past the buffer end
//! is the twin's IndexError — an unclassified crash — mirrored here as
//! the natural Rust panic, which exits outside the seam contract and is
//! recorded as a harness-level failure, never a match, §3.2; no corpus
//! part reaches it — the accepted run carries no crash rows).
//!
//! Evidence (the same citations the twin's docstring carries):
//!
//! - ``docs/evidence/2026-11-09-nested-store.md`` (the G1 model: N1,
//!   N1h/N1l, N2, N3, N4w, N6; corrections C1/C3; section 6 the miss
//!   taxonomy)
//! - ``docs/evidence/2026-11-10-l2-grind-classification.md``
//!   (sections 5-6 — the stage-3a recovery extension, #34: the
//!   relaxed tail law and the non-stdcont probes)
//!
//! Numeric contract (spec §2.2 point 3): decode module — the
//! ``suboptimal_flops`` allow below is the pinned carve-out (mul_add
//! changes rounding and flips exact-equality decisions); see the
//! crate docs in ``../lib.rs`` for the full policy.
#![allow(clippy::suboptimal_flops)]

use super::errors::ExportError;

/// The nested-store header magic (twin: :data:`catpart.geometry.store.V5_CFV2`).
pub const V5_CFV2: &[u8; 8] = b"V5_CFV2\x00";
/// The catalog magic (twin: :data:`catpart.geometry.store.CB0001`).
pub const CB0001: &[u8; 16] = b"CATIA_V5 CB0001\x00";
/// The catalog trailer marker (twin: :data:`catpart.geometry.store.CB_END`).
pub const CB_END: &[u8; 8] = b"CB__END\x00";
/// The storage-block tag (twin: :data:`catpart.geometry.store.BLOCK_TAG`).
pub const BLOCK_TAG: &[u8; 2] = b"\x34\x12";
/// The storage-block word (twin: :data:`catpart.geometry.store.STORAGE_WORD`).
pub const STORAGE_WORD: &[u8] = b"CATStorageProperty";

/// The nested header length (twin: ``HEADER_LEN``).
pub const HEADER_LEN: usize = 32;
/// Header-less store body starts at origin + 64 (N1l; twin: ``HDRLESS_BODY``).
pub const HDRLESS_BODY: usize = 64;
/// Inter-block tail after the container (N3b/N9; twin: ``TAIL126``).
pub const TAIL126: usize = 126;

/// Origin kinds (twin: ``ORIGIN_KIND_HEADER``/``ORIGIN_KIND_BLOCK``).
pub const ORIGIN_KIND_HEADER: &str = "v5header";
pub const ORIGIN_KIND_BLOCK: &str = "block";

/// Stage 3a/12 recovery provenance (#34): which container family
/// located the store and which catalog-tail law validated it.
/// ``stdcont``/``shipped`` is the pre-stage-3a behavior; every other
/// combination is a recovery. Stage 12 (#34, 2026-11-13) adds the
/// final family: ``other-container`` (the corpus mass:
/// CATBRepModeContainer 39, CameraStartupContainer 8, contmeasure 2,
/// four others 1 each — the stage-1 census's C11 candidate upside,
/// measured in docs/evidence/2026-11-13-noncomposite-census.md). The
/// block's own name travels on the summary
/// (``store_recovery.container_name``). (Twin module constants, verbatim.)
pub const CONTAINER_STDCONT: &str = "stdcont";
pub const CONTAINER_XDOCLINK: &str = "xdoclink";
pub const CONTAINER_SEEBODY: &str = "seebody";
pub const CONTAINER_OTHER: &str = "other-container";
pub const TAIL_LAW_SHIPPED: &str = "shipped";
pub const TAIL_LAW_OVERSHOOT: &str = "overshoot";
pub const TAIL_LAW_PADDED: &str = "padded";

/// The doc-type names the export seam's named probe families cover
/// (stage 3a + the shipped law). Every other valid block name belongs
/// to the stage-12 ``other-container`` probe family. (Twin:
/// ``NAMED_PROBE_CONTAINERS``.)
pub const NAMED_PROBE_CONTAINERS: [&str; 3] = ["CATStdCont", "CATXDocLinkCont", "CATSeeBodyCont"];

/// The twin's Python slice semantics: ``data[start:end]`` clamps both
/// bounds (an ``end`` past the buffer shortens the slice; it never
/// raises). ``start > end`` yields the empty slice.
pub(crate) fn slice_clamped(data: &[u8], start: usize, end: usize) -> &[u8] {
    let lo = start.min(data.len());
    let hi = end.min(data.len()).max(lo);
    &data[lo..hi]
}

/// The twin's ``bytes.find``: the first ``needle`` occurrence in
/// ``data[start:end]``, with the end bound clamped to the buffer
/// (Python's ``find`` accepts an ``end`` past the buffer) and ``None``
/// where Python returns -1. Boyer-Moore-Horspool with a full byte
/// shift table (no runtime dependency; the corpus's largest file is
/// ~120 MB and ``valid_blocks`` scans it whole).
pub(crate) fn find(data: &[u8], needle: &[u8], start: usize, end: usize) -> Option<usize> {
    let end = end.min(data.len());
    if start >= end {
        return None;
    }
    let n = needle.len();
    if n == 0 {
        return Some(start);
    }
    if end - start < n {
        return None;
    }
    let mut shift = [n; 256];
    for (i, &byte) in needle[..n - 1].iter().enumerate() {
        shift[byte as usize] = n - 1 - i;
    }
    let mut pos = start + n - 1; // the window's last byte position
    loop {
        let window = pos + 1 - n;
        if &data[window..window + n] == needle {
            return Some(window);
        }
        let step = shift[data[pos] as usize];
        if pos + step >= end {
            return None;
        }
        pos += step;
    }
}

/// Every occurrence of ``needle`` in ``data[start:end]``, in order —
/// overlapping occurrences included, exactly the twin's
/// :func:`catpart.geometry.store.find_all` (the next search resumes at
/// ``hit + 1``).
pub fn find_all(data: &[u8], needle: &[u8], start: usize, end: usize) -> Vec<usize> {
    let mut out = Vec::new();
    let mut at = start;
    while let Some(hit) = find(data, needle, at, end) {
        out.push(hit);
        at = hit + 1;
    }
    out
}

/// The twin's ``name.decode("ascii", "replace")``: bytes outside ASCII
/// each become U+FFFD (``String::from_utf8_lossy`` would merge
/// multi-byte sequences instead — a different string).
pub(crate) fn ascii_replace(bytes: &[u8]) -> String {
    bytes
        .iter()
        .map(|&b| if b < 0x80 { b as char } else { '\u{FFFD}' })
        .collect()
}

/// Doc-type name from the block's CATUnicodeString header (G1/B1) —
/// the twin's :func:`catpart.geometry.store.block_name`. Returns
/// ``("", false)`` where the twin returns ``("", False)``.
pub fn block_name(data: &[u8], blk: usize) -> (String, bool) {
    let bi = match find(data, b"CATUnicodeString", blk, blk + 64) {
        Some(bi) => bi,
        None => return (String::new(), false),
    };
    if slice_clamped(data, bi + 16, bi + 22) != [0xa0, 0x02, 0x00, 0x00, 0x00, 0x00]
        || data[bi + 22] != 0x34
    {
        return (String::new(), false);
    }
    let ln = data[bi + 23] as usize;
    let name = slice_clamped(data, bi + 24, bi + 24 + ln);
    if name.len() != ln {
        return (String::new(), false);
    }
    (ascii_replace(name), true)
}

/// (start, name) of every storage block whose name field parses — the
/// twin's :func:`catpart.geometry.store.valid_blocks`. The ``o - 2``
/// BLOCK_TAG lookback reproduces the twin's negative-slice semantics
/// for ``o < 2`` (the slice is empty there, so no shift).
pub fn valid_blocks(data: &[u8]) -> Vec<(usize, String)> {
    let mut out = Vec::new();
    for o in find_all(data, STORAGE_WORD, 0, data.len()) {
        let blk = if o >= 2 && data[o - 2..o] == BLOCK_TAG[..] {
            o - 2
        } else {
            o
        };
        let (nm, ok) = block_name(data, blk);
        if ok {
            out.push((blk, nm));
        }
    }
    out
}

/// Region end of ``blk``: next valid block / outer dword8 / EOF (B3) —
/// the twin's :func:`catpart.geometry.store.probe_region`. ``nxt`` is
/// the first later block in ``blocks`` order (the twin's
/// ``next(...)``), not a minimum over names.
pub fn probe_region(blk: usize, blocks: &[(usize, String)], d8_outer: usize, size: usize) -> usize {
    let nxt = blocks.iter().find(|(b, _)| *b > blk).map(|(b, _)| *b);
    let mut ends = vec![size];
    if let Some(nxt) = nxt {
        ends.push(nxt);
    }
    if d8_outer > blk {
        ends.push(d8_outer);
    }
    *ends.iter().min().unwrap()
}

/// Structural trailer laws of a nested catalog tail (G1 N6) — the
/// twin's :func:`catpart.geometry.store.validate_catalog_tail`.
///
/// The tail must end with ``CB__END\0``, carry ``C == D`` and name its
/// own length in ``G``. This replaces G1's B2 record-walk validation
/// (``validate_catalog``) because the exporter reads no catalog
/// entries; see the twin's module docstring.
pub fn validate_catalog_tail(tail: &[u8]) -> bool {
    if tail.len() < 36 || tail[tail.len() - 8..] != CB_END[..] {
        return false;
    }
    let tb = &tail[tail.len() - 36..];
    let be = |at: usize| u32::from_be_bytes([tb[at], tb[at + 1], tb[at + 2], tb[at + 3]]);
    let c = be(8);
    let d = be(12);
    let g = be(24);
    c == d && g as usize == tail.len()
}

/// The byte extent one validated nested store occupies — the twin's
/// :class:`catpart.geometry.store.StoreSpan` dataclass (frozen).
/// ``body_lo``/``body_hi`` bound the store body (the pool and facet
/// territory the exporter reads); ``body_hi`` is the catalog start.
/// ``container``/``tail_law`` carry the stage-3a recovery provenance
/// (#34): how the store was located — which container family and which
/// catalog-tail law. ``stdcont``/``shipped`` is the default (the
/// pre-stage-3a law).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StoreSpan {
    /// The storage block the region belongs to.
    pub block_start: usize,
    /// The store origin (the V5_CFV2 header, or the block start).
    pub origin: usize,
    /// ``ORIGIN_KIND_HEADER`` or ``ORIGIN_KIND_BLOCK``.
    pub origin_kind: &'static str,
    /// The store body's lower bound (the pool/facet territory).
    pub body_lo: usize,
    /// The store body's upper bound = the catalog start.
    pub body_hi: usize,
    /// The validated catalog tail length.
    pub catalog_len: usize,
    /// The probing container family (stage-3a/12 provenance).
    pub container: &'static str,
    /// The validating catalog-tail law (stage-3a provenance).
    pub tail_law: &'static str,
}

/// The two G1-documented catalog-tail variants (stage 3a #34) — the
/// twin's :func:`catpart.geometry.store._relaxed_tail_span`.
///
/// Applies only after the shipped tail law rejected
/// ``[cb, j+d8n+d12n)``:
///
/// - dword8-overshoot (G1 correction C3, k = 5..28 B): ``dword8``
///   overshoots the catalog magic by ``k`` and the shipped tail end
///   inherits the same overshoot, running ``k`` bytes past the
///   catalog's ``CB__END``; the true tail is ``[cb, cb + d12n)``.
/// - padded-tail (G1): the catalog's trailer sits *inside* the tail,
///   ``CB__END`` followed by zero padding up to the round dword12; the
///   tail ends at its ``CB__END`` (N4w: the trailer's ``G`` names the
///   true catalog length).
///
/// Both recover only when the corrected tail satisfies the same N6
/// trailer laws (:func:`validate_catalog_tail`); otherwise ``None`` is
/// returned and the shipped rejection stands (fail-closed).
fn relaxed_tail_span(
    data: &[u8],
    blk: usize,
    j: usize,
    d8n: usize,
    d12n: usize,
    cb: usize,
    container: &'static str,
) -> Option<StoreSpan> {
    let k = j + d8n - cb;
    if k > 0 {
        let tail = slice_clamped(data, cb, cb + d12n);
        if validate_catalog_tail(tail) {
            return Some(StoreSpan {
                block_start: blk,
                origin: j,
                origin_kind: ORIGIN_KIND_HEADER,
                body_lo: j + HEADER_LEN,
                body_hi: cb,
                catalog_len: d12n,
                container,
                tail_law: TAIL_LAW_OVERSHOOT,
            });
        }
    }
    let ship_tail = slice_clamped(data, cb, j + d8n + d12n);
    if let Some(pos) = find(ship_tail, CB_END, 0, ship_tail.len()) {
        let tail = &ship_tail[..pos + 8];
        if validate_catalog_tail(tail) {
            return Some(StoreSpan {
                block_start: blk,
                origin: j,
                origin_kind: ORIGIN_KIND_HEADER,
                body_lo: j + HEADER_LEN,
                body_hi: cb,
                catalog_len: tail.len(),
                container,
                tail_law: TAIL_LAW_PADDED,
            });
        }
    }
    None
}

/// Bound one block region's nested store (G1 analyze_region) — the
/// twin's :func:`catpart.geometry.store.locate_store`.
///
/// Returns ``Ok(None)`` when the region carries no store (G1's
/// ``none_in_region`` / ``embedded_doc`` families) and raises
/// ``malformed-store-header`` when a ``V5_CFV2`` header is present but
/// fails both the N2 validation and the stage-3a relaxed tail law
/// (#34: G1's two documented tail variants, applied fail-closed — a
/// tail neither family recovers keeps the shipped rejection).
///
/// ``container`` records the probing family on the returned span (the
/// exporter probes ``CATXDocLinkCont``/``CATSeeBodyCont`` regions too,
/// stage 3a); the tail laws themselves are container-independent.
pub fn locate_store(
    data: &[u8],
    blk: usize,
    blocks: &[(usize, String)],
    d8_outer: usize,
    container: &'static str,
) -> Result<Option<StoreSpan>, ExportError> {
    let size = data.len();
    let rend = probe_region(blk, blocks, d8_outer, size);

    // ---- header variant
    if let Some(j) = find(data, V5_CFV2, blk, rend) {
        let nh = slice_clamped(data, j, j + HEADER_LEN);
        let ff8 = nh.len() == HEADER_LEN && nh[16..24] == [0xff; 8];
        let zeros8 = nh.len() == HEADER_LEN && nh[24..32] == [0x00; 8];
        let (d8n, d12n) = if nh.len() == HEADER_LEN {
            (
                u32::from_be_bytes([nh[8], nh[9], nh[10], nh[11]]) as usize,
                u32::from_be_bytes([nh[12], nh[13], nh[14], nh[15]]) as usize,
            )
        } else {
            (0, 0)
        };
        let sane = d8n > 0 && d12n > 0 && j + d8n + d12n <= size;
        let mut cb: Option<usize> = None;
        if sane && slice_clamped(data, j + d8n, j + d8n + 16) == CB0001.as_slice() {
            cb = Some(j + d8n);
        } else if sane {
            // dword8-overshoot variant (C3): the catalog magic sits up to
            // 64 B before origin + dword8; everything else standard.
            let cand = find(data, CB0001, j, rend.min(j + d8n + d12n + 512));
            if let Some(cand) = cand {
                let overshoot = (j + d8n) as isize - cand as isize;
                if (1..=64).contains(&overshoot) {
                    cb = Some(cand);
                }
            }
        }
        if !(ff8 && zeros8) || cb.is_none() {
            return Err(ExportError::new(
                super::errors::MALFORMED_STORE_HEADER,
                format!(
                    "V5_CFV2 header at {j} fails the G1 N2 validation \
                     (ff x 8 / zeros x 8 / sane dwords / CB0001 catalog magic \
                     at origin + dword8, N3 overshoot variant included)"
                ),
            ));
        }
        let cb = cb.unwrap();
        let tail = slice_clamped(data, cb, j + d8n + d12n);
        if !validate_catalog_tail(tail) {
            // Stage 3a (#34): the shipped tail window is wrong for two
            // G1-documented families — the dword8-overshoot tail (the
            // end inherits the dword8 overshoot, C3) and the padded
            // tail (the trailer sits inside the zero padding). Try the
            // corrected windows fail-closed; an unrecognized tail keeps
            // the shipped malformed-store-header classification.
            if let Some(span) = relaxed_tail_span(data, blk, j, d8n, d12n, cb, container) {
                return Ok(Some(span));
            }
            return Err(ExportError::new(
                super::errors::MALFORMED_STORE_HEADER,
                format!(
                    "catalog tail at {cb} (length {d12n}) violates the G1 N6 \
                     trailer laws (CB__END, C == D, G == tail length) and \
                     matches neither stage-3a recovery family (dword8-\
                     overshoot, padded-tail)"
                ),
            ));
        }
        return Ok(Some(StoreSpan {
            block_start: blk,
            origin: j,
            origin_kind: ORIGIN_KIND_HEADER,
            body_lo: j + HEADER_LEN,
            body_hi: cb,
            catalog_len: d12n,
            container,
            tail_law: TAIL_LAW_SHIPPED,
        }));
    }

    // ---- header-less variant / embedded document
    if let Some(cb) = find(data, CB0001, blk, rend) {
        // Python's candidates may go negative (rend - 126 - cb); the
        // `<= 100` guard skips them, so isize here mirrors that.
        for tail_len in [
            rend as isize - TAIL126 as isize - cb as isize,
            (rend - cb) as isize,
        ] {
            if tail_len <= 100 {
                continue;
            }
            let tail = slice_clamped(data, cb, cb + tail_len as usize);
            if validate_catalog_tail(tail) {
                return Ok(Some(StoreSpan {
                    block_start: blk,
                    origin: blk,
                    origin_kind: ORIGIN_KIND_BLOCK,
                    body_lo: blk + HDRLESS_BODY,
                    body_hi: cb,
                    catalog_len: tail_len as usize,
                    container,
                    tail_law: TAIL_LAW_SHIPPED,
                }));
            }
        }
    }
    // A CB0001 that validates as neither tail form is an embedded
    // document's own outer-style catalog (G1 N10), not a stream store.
    Ok(None)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A minimal validated catalog tail: the 16-byte CB0001 magic plus
    /// a 36-byte trailer (A..G big-endian dwords + CB__END) whose
    /// C == D == 0xE7 and G == 52 (the fixture generator's catalog).
    fn catalog_tail(c: u32, d: u32, g: u32) -> Vec<u8> {
        let mut tail = Vec::new();
        tail.extend_from_slice(CB0001);
        for dword in [1u32, 0, c, d, 0, 0, g] {
            tail.extend_from_slice(&dword.to_be_bytes());
        }
        tail.extend_from_slice(CB_END);
        tail
    }

    #[test]
    fn find_matches_bytes_find_with_clamped_end() {
        let data = b"abcabcabc";
        assert_eq!(find(data, b"cab", 0, 100), Some(2));
        assert_eq!(find(data, b"cab", 3, 100), Some(5));
        // Overlapping occurrences via find_all (the twin's law).
        assert_eq!(find_all(data, b"abca", 0, 100), vec![0, 3]);
        // End bound past the buffer clamps (Python bytes.find).
        assert_eq!(find(data, b"c", 0, 200), Some(2));
        // A hit at the very start bound still matches (Python: find
        // over data[8:100] finds "c" at 8); past it, none.
        assert_eq!(find(data, b"c", 8, 100), Some(8));
        assert_eq!(find(data, b"c", 9, 100), None);
        assert_eq!(find(data, b"abcabcabcX", 0, 100), None);
    }

    #[test]
    fn slice_clamped_matches_python_slicing() {
        let data = b"0123456789";
        assert_eq!(slice_clamped(data, 8, 20), b"89");
        assert_eq!(slice_clamped(data, 5, 5), b"");
        assert_eq!(slice_clamped(data, 7, 3), b"");
        assert_eq!(slice_clamped(data, 20, 30), b"");
    }

    #[test]
    fn catalog_tail_laws() {
        let tail = catalog_tail(0xE7, 0xE7, 52);
        assert_eq!(tail.len(), 52);
        assert!(validate_catalog_tail(&tail));
        // C != D rejected.
        assert!(!validate_catalog_tail(&catalog_tail(0xE7, 0xE8, 52)));
        // G != length rejected.
        assert!(!validate_catalog_tail(&catalog_tail(0xE7, 0xE7, 53)));
        // Short tail and wrong marker rejected.
        assert!(!validate_catalog_tail(&tail[..36]));
        let mut wrong_end = tail.clone();
        let last = wrong_end.len() - 8;
        wrong_end[last..].copy_from_slice(b"CB__ENX\x00");
        assert!(!validate_catalog_tail(&wrong_end));
    }

    /// Assemble a full store region like tests/fixtures_gen.py does:
    /// header (dword8 = 32 + body, dword12 = tail length) + body +
    /// catalog, preceded by a CATStdCont storage block.
    fn region(body: &[u8], tail: &[u8]) -> Vec<u8> {
        let mut region = Vec::new();
        region.extend_from_slice(BLOCK_TAG);
        region.extend_from_slice(STORAGE_WORD);
        region.extend_from_slice(b"\x80\x01\x00\x00\x00\x00\x22\x0c\x00\x00\x00");
        region.extend_from_slice(b"\x34\x01\x01\x00\x34\x10CATUnicodeString");
        region.extend_from_slice(b"\xa0\x02\x00\x00\x00\x00\x34\x0aCATStdCont\x9f");
        region.extend_from_slice(b"\x00\x00\x60"); // preamble to the store origin
        region.extend_from_slice(V5_CFV2);
        region.extend_from_slice(&((HEADER_LEN + body.len()) as u32).to_be_bytes());
        region.extend_from_slice(&(tail.len() as u32).to_be_bytes());
        region.extend_from_slice(&[0xff; 8]);
        region.extend_from_slice(&[0x00; 8]);
        region.extend_from_slice(body);
        region.extend_from_slice(tail);
        region
    }

    fn blocks_with(region_start: usize, name: &str) -> Vec<(usize, String)> {
        vec![(region_start, name.to_string())]
    }

    #[test]
    fn locates_the_canonical_header_store() {
        let tail = catalog_tail(0xE7, 0xE7, 52);
        let body = vec![0x11u8; 40];
        let region = region(&body, &tail);
        let blocks = blocks_with(0, "CATStdCont");
        let span = locate_store(&region, 0, &blocks, region.len(), CONTAINER_STDCONT)
            .unwrap()
            .unwrap();
        assert_eq!(span.origin_kind, ORIGIN_KIND_HEADER);
        assert_eq!(span.origin, region.len() - 32 - body.len() - tail.len());
        assert_eq!(span.body_lo, span.origin + HEADER_LEN);
        assert_eq!(span.body_hi, span.body_lo + body.len());
        assert_eq!(span.catalog_len, 52);
        assert_eq!(span.container, CONTAINER_STDCONT);
        assert_eq!(span.tail_law, TAIL_LAW_SHIPPED);
    }

    #[test]
    fn storeless_region_is_none() {
        let data = vec![0x00u8; 512];
        let blocks = blocks_with(0, "CATStdCont");
        let located = locate_store(&data, 0, &blocks, data.len(), CONTAINER_STDCONT).unwrap();
        assert!(located.is_none());
    }

    #[test]
    fn broken_header_fails_n2_fail_closed() {
        // A V5_CFV2 header whose ff x 8 marker is broken: the shipped
        // malformed-store-header rejection stands (the region has no
        // CB0001 either, so the header-less variant finds nothing).
        let mut data = vec![0x00u8; 256];
        let at = 64;
        data[at..at + 8].copy_from_slice(V5_CFV2);
        data[at + 8..at + 12].copy_from_slice(&96u32.to_be_bytes());
        data[at + 12..at + 16].copy_from_slice(&52u32.to_be_bytes());
        data[at + 16..at + 24].copy_from_slice(&[0xfe; 8]); // not ff x 8
        data[at + 24..at + 32].copy_from_slice(&[0x00; 8]);
        let blocks = blocks_with(0, "CATStdCont");
        let err = locate_store(&data, 0, &blocks, data.len(), CONTAINER_STDCONT).unwrap_err();
        assert_eq!(err.error_class, "malformed-store-header");
        assert!(err.detail.contains("fails the G1 N2 validation"));
    }

    #[test]
    fn overshoot_and_padded_tails_recover_fail_closed() {
        // Overshoot: dword8 names a position 9 bytes PAST the catalog
        // magic; the corrected window [cb, cb + d12n) validates.
        let tail = catalog_tail(0xE7, 0xE7, 52);
        let body = vec![0x11u8; 40];
        let overshoot_k = 9usize;
        let mut bytes = region(&body, &tail);
        // Patch dword8 += overshoot_k and pad the gap after the catalog
        // (the shipped tail window runs k bytes past CB__END).
        let origin = bytes.len() - 32 - body.len() - tail.len();
        let d8 = (HEADER_LEN + body.len()) as u32 + overshoot_k as u32;
        let at = origin + 8;
        bytes[at..at + 4].copy_from_slice(&d8.to_be_bytes());
        let after = origin + 32 + body.len() + tail.len();
        bytes.splice(after..after, vec![0u8; overshoot_k]);
        let blocks = blocks_with(0, "CATStdCont");
        let span = locate_store(&bytes, 0, &blocks, bytes.len(), CONTAINER_STDCONT)
            .unwrap()
            .unwrap();
        assert_eq!(span.tail_law, TAIL_LAW_OVERSHOOT);
        assert_eq!(span.body_hi, origin + 32 + body.len());

        // Padded: dword12 rounds past the trailer; the tail ends at its
        // CB__END and the trailer's G names the true catalog length.
        let padded_len = 128usize;
        let mut bytes = region(&body, &tail);
        let origin = bytes.len() - 32 - body.len() - tail.len();
        let at = origin + 12;
        bytes[at..at + 4].copy_from_slice(&(padded_len as u32).to_be_bytes());
        let after = origin + 32 + body.len() + tail.len();
        bytes.splice(after..after, vec![0u8; padded_len - tail.len()]);
        let blocks = blocks_with(0, "CATStdCont");
        let span = locate_store(&bytes, 0, &blocks, bytes.len(), CONTAINER_STDCONT)
            .unwrap()
            .unwrap();
        assert_eq!(span.tail_law, TAIL_LAW_PADDED);
        assert_eq!(span.catalog_len, tail.len());

        // Neither family recovers a broken tail: the shipped rejection.
        let bad_tail = catalog_tail(0xE7, 0xE8, 52); // C != D
        let bytes = region(&body, &bad_tail);
        let blocks = blocks_with(0, "CATStdCont");
        let err = locate_store(&bytes, 0, &blocks, bytes.len(), CONTAINER_STDCONT).unwrap_err();
        assert_eq!(err.error_class, "malformed-store-header");
        assert!(err.detail.contains("neither stage-3a recovery family"));
    }

    #[test]
    fn header_less_store_binds_block_origin() {
        // N1l: the catalog sits directly in the region (no V5_CFV2
        // magic anywhere), origin = block start, body at origin + 64,
        // tail length rend - 126 - cb (the 126-byte inter-block tail
        // follows the catalog, N9). The catalog tail must exceed the
        // twin's 100-byte floor for the first candidate to apply —
        // corpus header-less catalogs are record-carrying (N6 G names
        // the tail length).
        let mut tail = Vec::new();
        tail.extend_from_slice(CB0001);
        tail.extend_from_slice(&[0x55u8; 60]); // catalog record territory
        for dword in [1u32, 0, 0xE7, 0xE7, 0, 0, (16 + 60 + 36) as u32] {
            tail.extend_from_slice(&dword.to_be_bytes());
        }
        tail.extend_from_slice(CB_END);
        assert_eq!(tail.len(), 112);
        let mut region = Vec::new();
        region.extend_from_slice(BLOCK_TAG);
        region.extend_from_slice(STORAGE_WORD);
        region.extend_from_slice(b"\x80\x01\x00\x00\x00\x00\x22\x0c\x00\x00\x00");
        region.extend_from_slice(b"\x34\x01\x01\x00\x34\x10CATUnicodeString");
        region.extend_from_slice(b"\xa0\x02\x00\x00\x00\x00\x34\x0aCATStdCont\x9f");
        region.extend_from_slice(&vec![0x33u8; 60]); // the body territory
        let cb = region.len();
        region.extend_from_slice(&tail);
        region.extend_from_slice(&vec![0x44u8; 126]); // the inter-block tail
        let blocks = blocks_with(0, "CATStdCont");
        let span = locate_store(&region, 0, &blocks, region.len(), CONTAINER_STDCONT)
            .unwrap()
            .unwrap();
        assert_eq!(span.origin_kind, ORIGIN_KIND_BLOCK);
        assert_eq!(span.origin, 0);
        assert_eq!(span.body_lo, HDRLESS_BODY);
        assert_eq!(span.body_hi, cb);
        assert_eq!(span.catalog_len, 112);
        assert_eq!(span.tail_law, TAIL_LAW_SHIPPED);
    }

    #[test]
    fn block_name_parses_and_rejects() {
        let mut data = vec![0u8; 96];
        data[16..32].copy_from_slice(b"CATUnicodeString");
        data[32..38].copy_from_slice(&[0xa0, 0x02, 0x00, 0x00, 0x00, 0x00]);
        data[38] = 0x34;
        data[39] = 5;
        data[40..45].copy_from_slice(b"CATSt"); // name, truncated on purpose
        let (name, ok) = block_name(&data, 0);
        assert!(ok);
        assert_eq!(name, "CATSt");
        // Length field past the buffer: not ok.
        data[39] = 60;
        let (_, ok) = block_name(&data, 0);
        assert!(!ok);
        // Bad frame: not ok.
        data[39] = 5;
        data[32] = 0xa1;
        let (_, ok) = block_name(&data, 0);
        assert!(!ok);
    }

    #[test]
    fn valid_blocks_shifts_the_block_tag_lookback() {
        let data = region(&[0x11; 40], &catalog_tail(0xE7, 0xE7, 52));
        // The STORAGE_WORD hit two bytes after the BLOCK_TAG: blk = o-2.
        let blocks = valid_blocks(&data);
        assert_eq!(blocks.len(), 1);
        let (blk, name) = &blocks[0];
        assert_eq!(name, "CATStdCont");
        assert_eq!(data[*blk..*blk + 2], BLOCK_TAG[..]);
    }
}
