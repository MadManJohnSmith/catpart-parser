//! The nested store's facet records and their primitive semantics
//! (G3) — the port of the Python reference module
//! ``catpart.geometry.facets`` (``src/catpart/geometry/facets.py``),
//! per spec §2.1 of ``docs/specs/phase5-viewer-spec.md`` (G3 tiling +
//! soup). The behavior is mirrored 1:1, fail-closed arms included:
//! header positions no parse accepts are gap variant content
//! (``unresolved_candidates``), never guessed geometry.
//!
//! Adapted from ``scripts/triage/decode_facet_semantics.py`` (G3's
//! corpus decoder) with the decode semantics unchanged; the triage
//! script stays the analysis tool (ticket #32). The docstring
//! citations below are the twin's.
//!
//! Model (docs/evidence/2026-11-09-facet-semantics.md):
//!
//! - Record grammar (F1): ``01 <mk> <ty> ff [u32le n][12B f32le
//!   normal][k u8 counts][n refs]`` — markers 0x41-0x4f; the 12-byte
//!   normal payload appears on 0x49/0x4a/0x4c (and on the 5-byte-form
//!   markers 0x4b/0x4e, whose header carries one extra byte before
//!   ``ff``). The k count bytes (0..4) sum to n and delimit the ty
//!   sub-loops. The reference width is per-record u8 or u16be
//!   (big-endian), chosen by the tiling law (F1w, as corrected
//!   2026-11-10 #35, class-bounded to clean stores 2026-11-10): a
//!   record is accepted when some (width, k) parse ends at or before
//!   the next record header (or the body end); the exact-tiling parse
//!   wins, then — on a gap edge of a CLEAN store (no ``01 02`` edge
//!   group and no trailer opener, the class where the defect was
//!   verified) — the store-width context: the widths of the store's
//!   exact-tile records (those ending at the next header position)
//!   vote, and a unanimous vote wins the gap-edge tie-break (a
//!   cluster-final u16be record before a gap keeps its width); mixed
//!   votes or no exact tiles fall back to the narrower width.
//!   Composite stores keep the unconditional narrower-width gap
//!   behavior (until G6 decodes the composite index space from first
//!   principles). Records tile their region header-to-header; content
//!   that fails every parse is gap variant content (unresolved), not
//!   exported geometry.
//! - Index space (F2, correction C8): the references are
//!   LEXICOGRAPHIC RANKS of the pool coordinates (x, then y, then z),
//!   not walk positions — on the clean subset the strip reading under
//!   lex ranks reproduces the stored normals at 0.9923 vs 0.2746 under
//!   walk order.
//! - Primitive semantics (F3/F4/F9/F10): 0x4a loops (and 0x42, which
//!   is structurally identical without the normal payload) are
//!   triangle-strip segments — (r_t, r_{t+1}, r_{t+2}) with the flip
//!   on odd t, phase reset per loop; 0x4c loops are closed polygons in
//!   ring order, fan-triangulated from the first corner
//!   (orientation-preserving for the CCW ring order). 0x41/0x49
//!   satisfy the byte law n == 3*type but their primitive reading is
//!   not established (they carry no count bytes in the grammar, so
//!   they contribute no loops); 0x44/0x4b/0x4e are open.
//! - Export convention (F5/F7): the winding law is counter-clockwise
//!   seen from the stored normal (right-hand rule, the OBJ/PLY
//!   convention) — every decoded triangle is emitted as-is; the only
//!   skips are degenerate strip triangles (a repeated vertex or an
//!   exactly-zero cross product). Repeated references are real
//!   geometry (strip joins / apex fans), never deduplicated.
//!
//! The ``STRIP_RE`` header regex (``\x01[\x41-\x4f].\xff`` DOTALL) is
//! mirrored by :func:`strip_headers` with the regex engine's exact
//! leftmost-non-overlapping scan (the next search resumes at the
//! match's end) and the twin's ``finditer(data, pos, endpos)``
//! bounds (a match must fit the window).
//!
//! Evidence (the same citations the twin's docstring carries):
//!
//! - ``docs/evidence/2026-11-09-facet-semantics.md`` (the G3 model:
//!   F1/F1w/F2/F3/F4/F5/F6/F7/F8/F9/F10; the #35 record-width
//!   correction, 2026-11-10, class-bounded to clean stores)
//!
//! Numeric contract (spec §2.2 — the keystone lives here): the
//! degenerate-triangle test is TUPLE EQUALITY against
//! ``(0.0, 0.0, 0.0)`` on a cross product (:func:`decode_soup`,
//! ``facets.py:decode_soup``), the cross-product argument order
//! verbatim (``cross(sub(b, a), sub(c, a))``); coordinates load f32
//! and widen to f64 once at load (in ``pool.rs`` — this module's
//! normals widen the same way at :func:`parse_facet_record`); every
//! decision arithmetic is IEEE-exact ``+ - * /`` and comparisons;
//! expression shape copies the Python verbatim (``a[1]*b[2] -
//! a[2]*b[1]`` stays exactly that — no mul_add, no reassociation).
//! The lex-rank sort reproduces Python's stable tuple sort exactly
//! (IEEE comparisons, ties keep walk order — ``f64::total_cmp`` would
//! order -0.0 below 0.0 where Python sorts them equal, so it is
//! deliberately NOT used).
#![allow(clippy::suboptimal_flops)]

use std::collections::BTreeMap;

/// The header regex as a predicate over a 4-byte window: the twin's
/// ``STRIP_RE = re.compile(rb"\x01[\x41-\x4f].\xff", re.DOTALL)``.
pub const STRIP_MARKERS: [u8; 4] = [0x41, 0x42, 0x49, 0x4A];
/// Loop families: strips (triangle-strip segments) and closed polygons
/// (twin constants, verbatim).
pub const POLY_MARKERS: [u8; 1] = [0x4C];
/// Markers that carry the 12-B normal (twin: ``NORMAL_MARKERS_ALL``).
pub const NORMAL_MARKERS_ALL: [u8; 5] = [0x49, 0x4A, 0x4B, 0x4C, 0x4E];
/// The soup-decoded families (twin: ``SOUP_MARKERS``).
pub const SOUP_MARKERS: [u8; 5] = [0x41, 0x42, 0x49, 0x4A, 0x4C];
/// Markers whose primitive semantics are pinned end-to-end by G3 (the
/// exported families); anything else a record parses under is reported
/// as an unresolved facet family in the summary warnings (twin:
/// ``EXPORTED_MARKERS``).
pub const EXPORTED_MARKERS: [u8; 3] = [0x42, 0x4A, 0x4C];

/// G3's sanity cap on n (twin: ``MAX_REFS``).
pub const MAX_REFS: u32 = 1_000_000;

/// One facet record parsed under the (width, k) tiling law (F1/F1w) —
/// the twin's :class:`catpart.geometry.facets.FacetRecord` dataclass
/// (frozen).
#[derive(Debug, Clone, PartialEq)]
pub struct FacetRecord {
    /// The record header's body offset.
    pub offset: usize,
    /// The marker byte (0x41-0x4f).
    pub marker: u8,
    /// The type byte.
    pub ty: u8,
    /// 4 (``ff`` header form) or 5 (one extra byte before ``ff``).
    pub header_len: usize,
    /// The reference count (u32le).
    pub n: u32,
    /// 1 = u8 references, 2 = u16be (big-endian) references.
    pub width: u8,
    /// The k loop-count bytes, summing to n.
    pub counts: Vec<u8>,
    /// The references — lexicographic ranks into the pool.
    pub refs: Vec<u32>,
    /// The record's end position (the tiling law's extent).
    pub end: usize,
    /// The widened f64 normal triple when the marker carries one.
    pub normal: Option<(f64, f64, f64)>,
}

/// The facet content of one store body — the twin's
/// :class:`catpart.geometry.facets.FacetScan` dataclass (frozen).
#[derive(Debug, Clone, PartialEq)]
pub struct FacetScan {
    /// The ``01 [41-4f] . ff`` header positions.
    pub candidates: usize,
    /// The records accepted by the tiling law.
    pub records: Vec<FacetRecord>,
    /// Header positions no parse accepted (gap variant content).
    pub unresolved_candidates: usize,
    /// Parsed records outside ``EXPORTED_MARKERS``, per marker.
    pub skipped_markers: BTreeMap<u8, u32>,
}

/// The twin's ``STRIP_RE.finditer(data, body_lo, body_hi)``: the
/// leftmost-non-overlapping scan of the 4-byte header pattern
/// (``\x01 [41-4f] . \xff``, DOTALL — the third byte is any value),
/// resumed at each match's end, matches confined to the window.
pub fn strip_headers(data: &[u8], body_lo: usize, body_hi: usize) -> Vec<usize> {
    let mut out = Vec::new();
    let mut i = body_lo;
    while i + 4 <= body_hi {
        if data[i] == 0x01 && (0x41..=0x4f).contains(&data[i + 1]) && data[i + 3] == 0xff {
            out.push(i);
            i += 4;
        } else {
            i += 1;
        }
    }
    out
}

/// Parse one facet record at header offset ``o`` under the tiling law —
/// the twin's :func:`catpart.geometry.facets.parse_facet_record`.
///
/// ``nxt`` is the next record header offset (or the body end). The
/// (width, k) combo must end at or before ``nxt``; the exact-tiling
/// parse wins, then the narrower width — except on a gap edge
/// (``end < nxt``), where ``prefer_width`` (the store-width context
/// derived by :func:`scan_facets`, default 1 = the historical narrower
/// width) wins the tie-break (F1/F1w). Returns ``None`` when no
/// variant of the grammar validates — gap variant content.
///
/// The twin's lazy ref computation is mirrored: within one width the
/// FIRST k whose parse ranks best wins (later equal ranks do not
/// recompute), which pins the smallest qualifying k exactly as the
/// Python comparison chain does.
pub fn parse_facet_record(
    data: &[u8],
    o: usize,
    body_hi: usize,
    nxt: usize,
    prefer_width: u8,
) -> Option<FacetRecord> {
    let mk = data[o + 1];
    let ty = data[o + 2];
    let header_len: usize = if data[o + 3] == 0xFF { 4 } else { 5 };
    if o + header_len + 4 > body_hi {
        return None;
    }
    let n = u32::from_le_bytes([
        data[o + header_len],
        data[o + header_len + 1],
        data[o + header_len + 2],
        data[o + header_len + 3],
    ]);
    if n > MAX_REFS {
        return None;
    }
    let has_normal = NORMAL_MARKERS_ALL.contains(&mk);
    let base = o + header_len + 4 + if has_normal { 12 } else { 0 };
    if base > body_hi {
        return None;
    }
    // best = (rank, width, counts, refs, end); rank = (tiling, width
    // preference) ordered lexicographically, the twin's tuple rank.
    type Rank = (u8, u32);
    type BestParse = (Rank, u8, Vec<u8>, Vec<u32>, usize);
    let mut best: Option<BestParse> = None;
    for width in [1u8, 2u8] {
        for k in 0u8..5 {
            // The count bytes read over the WHOLE buffer past base —
            // the twin's ``data[base + j]`` reaches into the catalog
            // territory when base sits at the body edge (unreachable
            // here: base <= body_hi <= len - 36 for a validated span,
            // and the byte range only panics past the buffer end,
            // which is the twin's IndexError crash).
            let counts: Vec<u8> = (0..k).map(|j| data[base + j as usize]).collect();
            let sum: u32 = counts.iter().map(|&c| u32::from(c)).sum();
            if !((n > 0 && sum == n) || (n == 0 && k == 0)) {
                continue;
            }
            let end = base + k as usize + width as usize * n as usize;
            if end > nxt {
                continue;
            }
            let rank: Rank = if end == nxt {
                (0, u32::from(width)) // exact tiling wins; narrower on exact ties
            } else {
                // Gap edge: the store-width context wins the tie-break
                // (P3-B, #35 2026-11-10); the default context of 1 keeps
                // the historical narrower-width preference.
                (1, if width == prefer_width { 0 } else { 1 })
            };
            if best.as_ref().is_none_or(|(b, ..)| rank < *b) {
                let refs: Vec<u32> = (0..n)
                    .map(|j| {
                        let at = base + k as usize + width as usize * j as usize;
                        match width {
                            1 => u32::from(data[at]),
                            _ => u32::from(u16::from_be_bytes([data[at], data[at + 1]])),
                        }
                    })
                    .collect();
                best = Some((rank, width, counts, refs, end));
            }
        }
    }
    let (_, width, counts, refs, end) = best?;
    let normal = if has_normal {
        // The 12-byte f32le normal, widened to f64 at load (spec §2.2).
        let at = o + header_len + 4;
        let f = |i: usize| {
            f32::from_le_bytes([
                data[at + i],
                data[at + i + 1],
                data[at + i + 2],
                data[at + i + 3],
            ]) as f64
        };
        Some((f(0), f(4), f(8)))
    } else {
        None
    };
    Some(FacetRecord {
        offset: o,
        marker: mk,
        ty,
        header_len,
        n,
        width,
        counts,
        refs,
        end,
        normal,
    })
}

/// Walk the store body's facet region header-to-header (G3
/// scan_store) — the twin's :func:`catpart.geometry.facets.scan_facets`.
///
/// Candidates come from the ``01 [41-4f] . ff`` header regex; each
/// accepted record's end positions the walk at the next header at or
/// after it. Header positions no parse accepts are gap variant content
/// and surface as ``unresolved_candidates``.
///
/// ``clean_store`` bounds the store-width context to the clean store
/// class (no ``01 02`` edge group and no trailer opener — the class
/// where the cluster-final truncation was verified; #35's third
/// re-scope, 2026-11-10). The store decode knows the class and passes
/// it down. On a clean store the walk is preceded by the store-width
/// pre-pass (F1w as corrected 2026-11-10 #35): every candidate header
/// is parsed under the default tie-break and the exact-tile records —
/// those whose end equals the next header position — vote their width;
/// a unanimous vote becomes the gap-edge tie-break width, mixed votes
/// (or no exact tiles) keep the default narrower-width preference.
/// Composite stores — the default, and any caller that does not pass
/// the flag (fail-safe) — keep the historical unconditional width-1
/// gap behavior.
pub fn scan_facets(data: &[u8], body_lo: usize, body_hi: usize, clean_store: bool) -> FacetScan {
    let hdrs = strip_headers(data, body_lo, body_hi);
    let next_of = |i: usize| -> usize {
        if i + 1 < hdrs.len() {
            hdrs[i + 1]
        } else {
            body_hi
        }
    };
    let mut prefer: u8 = 1;
    if clean_store {
        let mut exact_widths: Vec<u8> = Vec::new();
        for (i, &o) in hdrs.iter().enumerate() {
            let nxt = next_of(i);
            if let Some(rec) = parse_facet_record(data, o, body_hi, nxt, 1)
                && rec.end == nxt
                && !exact_widths.contains(&rec.width)
            {
                exact_widths.push(rec.width);
            }
        }
        if exact_widths.len() == 1 {
            prefer = exact_widths[0];
        }
    }
    let mut records: Vec<FacetRecord> = Vec::new();
    let mut consumed: Vec<usize> = Vec::new();
    let mut i = 0;
    while i < hdrs.len() {
        let o = hdrs[i];
        let nxt = next_of(i);
        let rec = parse_facet_record(data, o, body_hi, nxt, prefer);
        match rec {
            None => {
                i += 1;
            }
            Some(rec) => {
                consumed.push(o);
                i = match hdrs.iter().position(|&h| h >= rec.end) {
                    Some(position) => position,
                    None => hdrs.len(),
                };
                records.push(rec);
            }
        }
    }
    let mut skipped: BTreeMap<u8, u32> = BTreeMap::new();
    for rec in &records {
        if !EXPORTED_MARKERS.contains(&rec.marker) {
            *skipped.entry(rec.marker).or_insert(0) += 1;
        }
    }
    FacetScan {
        candidates: hdrs.len(),
        records,
        unresolved_candidates: hdrs.len() - consumed.len(),
        skipped_markers: skipped,
    }
}

/// Pool positions ordered by lexicographic rank of (x, y, z) (F2/C8) —
/// the twin's :func:`catpart.geometry.facets.lex_rank_map`.
///
/// ``lex[rank]`` is the pool's walk position of the rank-``rank``
/// coordinate triple; ties keep walk order (Python's stable sort, as
/// in G3's decoder). Duplicate coordinates are not deduplicated.
/// IEEE comparisons (``partial_cmp``) reproduce Python's float
/// ordering — including -0.0 == 0.0, which ``f64::total_cmp`` would
/// break.
pub fn lex_rank_map(pool: &[(f64, f64, f64)]) -> Vec<usize> {
    let mut order: Vec<usize> = (0..pool.len()).collect();
    order.sort_by(|&a, &b| {
        let axis = |p: usize, q: usize, which: usize| -> std::cmp::Ordering {
            let value = if which == 0 {
                pool[p].0.partial_cmp(&pool[q].0)
            } else if which == 1 {
                pool[p].1.partial_cmp(&pool[q].1)
            } else {
                pool[p].2.partial_cmp(&pool[q].2)
            };
            value.unwrap_or(std::cmp::Ordering::Equal)
        };
        axis(a, b, 0).then(axis(a, b, 1)).then(axis(a, b, 2))
    });
    order
}

/// Split the record's references into its ty sub-loops (the k count
/// bytes delimit them; G2's law, retained by G3) — the twin's
/// :func:`catpart.geometry.facets.record_loops`.
pub fn record_loops(rec: &FacetRecord) -> Vec<&[u32]> {
    let mut loops = Vec::new();
    let mut at = 0usize;
    for &c in &rec.counts {
        loops.push(&rec.refs[at..at + c as usize]);
        at += c as usize;
    }
    loops
}

/// The twin's ``_cross`` — argument order and expression shape
/// verbatim (``a[1]*b[2] - a[2]*b[1]``; no mul_add, spec §2.2).
fn cross(a: (f64, f64, f64), b: (f64, f64, f64)) -> (f64, f64, f64) {
    (
        a.1 * b.2 - a.2 * b.1,
        a.2 * b.0 - a.0 * b.2,
        a.0 * b.1 - a.1 * b.0,
    )
}

/// The twin's ``_sub``.
fn sub(a: (f64, f64, f64), b: (f64, f64, f64)) -> (f64, f64, f64) {
    (a.0 - b.0, a.1 - b.1, a.2 - b.2)
}

/// The decoded triangle soup (G3's export convention) — the twin's
/// :class:`catpart.geometry.facets.TriangleSoup` dataclass (frozen).
#[derive(Debug, Clone, PartialEq)]
pub struct TriangleSoup {
    /// Pool walk positions per triangle.
    pub triangles: Vec<(u32, u32, u32)>,
    /// The degenerate strip triangles skipped (F7).
    pub degenerate_skipped: usize,
}

/// Decode the pinned facet families to a triangle soup (F3/F4/F5/F7)
/// — the twin's :func:`catpart.geometry.facets.decode_soup`.
///
/// Strips: (r_t, r_{t+1}, r_{t+2}) with the flip on odd t, phase reset
/// per loop. Polygons (0x4c): fan from the first corner. Skips exactly
/// the degenerate strip triangles (repeated vertex or zero cross
/// product — coordinate equality, as in G3's decoder); polygon fans
/// skip only repeated vertices. Repeated references are real geometry.
///
/// THE NUMERIC CONTRACT (spec §2.2): the zero-cross test is tuple
/// equality against ``(0.0, 0.0, 0.0)`` — IEEE-exact component
/// equality on f64 values derived from the once-widened f32
/// coordinates — with the cross-product argument order verbatim.
pub fn decode_soup(pool: &[(f64, f64, f64)], lex: &[usize], scan: &FacetScan) -> TriangleSoup {
    let mut triangles: Vec<(u32, u32, u32)> = Vec::new();
    let mut degenerate = 0usize;
    for rec in &scan.records {
        if !SOUP_MARKERS.contains(&rec.marker) {
            continue;
        }
        for refs in record_loops(rec) {
            let pts: Vec<usize> = refs.iter().map(|&x| lex[x as usize]).collect();
            if POLY_MARKERS.contains(&rec.marker) {
                for t in 1..pts.len().saturating_sub(1) {
                    let tri = (pts[0] as u32, pts[t] as u32, pts[t + 1] as u32);
                    let (a, b, c) = (
                        pool[tri.0 as usize],
                        pool[tri.1 as usize],
                        pool[tri.2 as usize],
                    );
                    if a == b || b == c || a == c {
                        degenerate += 1;
                        continue;
                    }
                    triangles.push(tri);
                }
            } else {
                for t in 0..pts.len().saturating_sub(2) {
                    let mut tri = (pts[t] as u32, pts[t + 1] as u32, pts[t + 2] as u32);
                    if t % 2 == 1 {
                        tri = (tri.2, tri.1, tri.0);
                    }
                    let (a, b, c) = (
                        pool[tri.0 as usize],
                        pool[tri.1 as usize],
                        pool[tri.2 as usize],
                    );
                    if a == b || b == c || a == c || cross(sub(b, a), sub(c, a)) == (0.0, 0.0, 0.0)
                    {
                        degenerate += 1;
                        continue;
                    }
                    triangles.push(tri);
                }
            }
        }
    }
    TriangleSoup {
        triangles,
        degenerate_skipped: degenerate,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The fixture generator's `_facet_record`: 4-byte header, u32le n,
    /// optional 12-byte f32le normal, one count byte (k=1), refs.
    fn facet_record(
        marker: u8,
        normal: Option<(f32, f32, f32)>,
        refs: &[u32],
        width: u8,
    ) -> Vec<u8> {
        let mut rec = vec![0x01, marker, 0x01, 0xFF];
        rec.extend_from_slice(&(refs.len() as u32).to_le_bytes());
        if let Some((x, y, z)) = normal {
            rec.extend_from_slice(&x.to_le_bytes());
            rec.extend_from_slice(&y.to_le_bytes());
            rec.extend_from_slice(&z.to_le_bytes());
        }
        rec.push(refs.len() as u8);
        for &r in refs {
            match width {
                1 => rec.push(r as u8),
                _ => rec.extend_from_slice(&(r as u16).to_be_bytes()),
            }
        }
        rec
    }

    #[test]
    fn strip_headers_mirror_the_regex_scan() {
        // 01 4a 01 ff = a header; 01 50 01 ff (0x50 outside 41-4f) is
        // not; the scan resumes at each match's end (finditer).
        let mut data = vec![0u8; 32];
        data[4..8].copy_from_slice(&[0x01, 0x4a, 0x01, 0xff]);
        data[10..14].copy_from_slice(&[0x01, 0x50, 0x01, 0xff]);
        data[16..20].copy_from_slice(&[0x01, 0x42, 0x01, 0xff]);
        data[20..24].copy_from_slice(&[0x01, 0x4c, 0x01, 0xff]);
        assert_eq!(strip_headers(&data, 0, data.len()), vec![4, 16, 20]);
        // A candidate whose 4 bytes do not fit the window is dropped
        // (finditer endpos semantics: the match must fit the slice).
        assert_eq!(strip_headers(&data, 0, 18), vec![4]);
    }

    #[test]
    fn exact_tiling_wins_and_the_normal_widens_at_load() {
        // A 0x4a record (normal-carrying) with u8 refs tiling exactly
        // to the next header position.
        let rec_bytes = facet_record(0x4A, Some((0.0, 0.0, -1.0)), &[4, 0, 6, 2], 1);
        let mut data = rec_bytes.clone();
        data.extend_from_slice(&[0x00; 8]); // the next record's territory
        let rec = parse_facet_record(&data, 0, 8 + rec_bytes.len(), rec_bytes.len(), 1).unwrap();
        assert_eq!(rec.width, 1);
        assert_eq!(rec.end, rec_bytes.len());
        assert_eq!(rec.refs, vec![4, 0, 6, 2]);
        assert_eq!(rec.normal, Some((0.0, 0.0, -1.0)));
        assert_eq!(rec.header_len, 4);
    }

    #[test]
    fn narrower_width_wins_exact_ties() {
        // Counts laid out so BOTH width parses tile exactly:
        // count bytes [2, 0, 0] + 2 refs. width1 k3 reads [2,0,0]
        // (sum 2 = n), end = base+3+2; width2 k1 reads [2], end =
        // base+1+4 — the same byte. Rank (0,1) < (0,2): the narrower
        // width wins the exact tie (the twin's law).
        let mut data = vec![0x01u8, 0x42, 0x01, 0xFF];
        data.extend_from_slice(&2u32.to_le_bytes());
        data.extend_from_slice(&[2, 0, 0]);
        data.extend_from_slice(&[7, 9]); // the u8 refs
        let body_hi = data.len(); // 13
        let rec = parse_facet_record(&data, 0, body_hi, body_hi, 1).unwrap();
        assert_eq!(rec.width, 1);
        assert_eq!(rec.end, body_hi);
        assert_eq!(rec.refs, vec![7, 9]);
    }

    #[test]
    fn u16be_records_parse_big_endian() {
        // Refs above 255 (the corpus clean-store u16be family): the u8
        // reads all fail the count law, the u16be parse tiles exactly.
        let rec_bytes = facet_record(0x42, None, &[300, 258, 5, 6], 2);
        let mut data = rec_bytes.clone();
        data.extend_from_slice(&[0x00; 4]);
        let rec = parse_facet_record(&data, 0, 4 + rec_bytes.len(), rec_bytes.len(), 1).unwrap();
        assert_eq!(rec.width, 2);
        assert_eq!(rec.refs, vec![300, 258, 5, 6]);
        assert_eq!(rec.end, rec_bytes.len());
    }

    #[test]
    fn gap_edge_uses_the_store_width_context() {
        // A cluster-final record whose u16be parse ends BEFORE the body
        // end (gap edge): with prefer=2 the u16be parse wins the
        // tie-break; with prefer=1 the u8 parse wins (the #35
        // correction's composite-store default).
        let wide = facet_record(0x4A, Some((0.0, 0.0, 1.0)), &[300, 258], 2);
        let mut data = wide.clone();
        data.extend_from_slice(&[0x00; 6]); // trailing gap
        let body_hi = wide.len() + 6;
        let rec = parse_facet_record(&data, 0, body_hi, body_hi, 2).unwrap();
        assert_eq!(rec.width, 2);
        assert_eq!(rec.refs, vec![300, 258]);
        let rec_narrow = parse_facet_record(&data, 0, body_hi, body_hi, 1).unwrap();
        assert_eq!(rec_narrow.width, 1);
    }

    #[test]
    fn scan_facets_votes_the_store_width_on_clean_stores() {
        // Three u16be exact-tile records whose u8 misreads all fail
        // the count law (the first ref's high byte poisons every u8
        // count window): the unanimous vote sets prefer=2.
        let mut data = vec![0u8; 128];
        let mut at = 0;
        for marker in [0x42u8, 0x42, 0x42] {
            let rec = facet_record(marker, None, &[300, 258, 5, 6], 2);
            data[at..at + rec.len()].copy_from_slice(&rec);
            at += rec.len();
        }
        let body_hi = at; // the last record tiles exactly to body_hi
        let scan = scan_facets(&data, 0, body_hi, true);
        assert_eq!(scan.candidates, 3);
        assert_eq!(scan.unresolved_candidates, 0);
        assert!(scan.records.iter().all(|rec| rec.width == 2));
        assert!(scan.skipped_markers.is_empty());
    }

    #[test]
    fn scan_facets_walks_header_to_header_and_counts_gaps() {
        // One good record, an unparseable candidate (n > MAX_REFS),
        // then a good record: the walk resumes at the next header and
        // the gap surfaces as unresolved_candidates.
        let mut data = vec![0u8; 96];
        let good = facet_record(0x4A, Some((0.0, 0.0, -1.0)), &[4, 0, 6, 2], 1);
        data[..good.len()].copy_from_slice(&good);
        let mut at = good.len();
        data[at..at + 4].copy_from_slice(&[0x01, 0x44, 0x01, 0xff]);
        data[at + 4..at + 8].copy_from_slice(&[0xff, 0xff, 0xff, 0x7f]); // n > MAX_REFS
        at += 8;
        let good2 = facet_record(0x42, None, &[7, 3, 5, 1], 1);
        data[at..at + good2.len()].copy_from_slice(&good2);
        at += good2.len();
        let scan = scan_facets(&data, 0, at, false);
        // Three candidates (both good records' headers + the bad one),
        // two accepted records, one gap.
        assert_eq!(scan.candidates, 3);
        assert_eq!(scan.records.len(), 2);
        assert_eq!(scan.unresolved_candidates, 1);
        assert!(scan.skipped_markers.is_empty());
    }

    #[test]
    fn skipped_markers_count_outside_exported_families() {
        let mut data = vec![0u8; 64];
        // 0x41 parses (the n == 3*ty byte law satisfied by k=1) but
        // exports nothing: it is not in EXPORTED_MARKERS.
        let rec = facet_record(0x41, None, &[0, 0, 0], 1);
        data[..rec.len()].copy_from_slice(&rec);
        let scan = scan_facets(&data, 0, rec.len(), false);
        assert_eq!(scan.records.len(), 1);
        assert_eq!(scan.skipped_markers.get(&0x41), Some(&1));
    }

    #[test]
    fn lex_rank_map_is_the_stable_lexicographic_order() {
        // The fixture box's pool walk order and GEOMETRY_LEX (the
        // generator's literal): lex[rank] = walk position.
        let pool = [
            (0.0, 0.0, 0.0),
            (20.0, 0.0, 0.0),
            (0.0, 100.0, 0.0),
            (20.0, 100.0, 0.0),
            (0.0, 100.0, 60.0),
            (20.0, 100.0, 60.0),
            (0.0, 0.0, 60.0),
            (20.0, 0.0, 60.0),
        ];
        assert_eq!(lex_rank_map(&pool), vec![0, 6, 2, 4, 1, 7, 3, 5]);
        // Duplicate coordinates keep walk order (stable sort).
        let dup = [(1.0, 0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)];
        assert_eq!(lex_rank_map(&dup), vec![1, 0, 2]);
        // -0.0 and 0.0 compare equal in Python's sort (IEEE): ties keep
        // walk order — total_cmp would flip this.
        let signed = [(0.0, 0.0, 0.0), (-0.0, 0.0, 0.0)];
        assert_eq!(lex_rank_map(&signed), vec![0, 1]);
        let signed_rev = [(-0.0, 0.0, 0.0), (0.0, 0.0, 0.0)];
        assert_eq!(lex_rank_map(&signed_rev), vec![0, 1]);
    }

    /// The fixture box's pool walk order + GEOMETRY_LEX, as literals.
    fn box_pool() -> Vec<(f64, f64, f64)> {
        vec![
            (0.0, 0.0, 0.0),
            (20.0, 0.0, 0.0),
            (0.0, 100.0, 0.0),
            (20.0, 100.0, 0.0),
            (0.0, 100.0, 60.0),
            (20.0, 100.0, 60.0),
            (0.0, 0.0, 60.0),
            (20.0, 0.0, 60.0),
        ]
    }

    #[test]
    fn decode_soup_strips_flip_and_export_real_geometry() {
        // The fixture box's y=0 face as a 0x4a strip over the lex
        // ranks (4, 0, 6, 2): pts = [lex[4], lex[0], lex[6], lex[2]] =
        // [1, 0, 3, 2]; the strip flip on odd t.
        let pool = box_pool();
        let lex = lex_rank_map(&pool);
        let rec = FacetRecord {
            offset: 0,
            marker: 0x4A,
            ty: 1,
            header_len: 4,
            n: 4,
            width: 1,
            counts: vec![4],
            refs: vec![4, 0, 6, 2],
            end: 20,
            normal: Some((0.0, 0.0, -1.0)),
        };
        let scan = FacetScan {
            candidates: 1,
            records: vec![rec],
            unresolved_candidates: 0,
            skipped_markers: BTreeMap::new(),
        };
        let soup = decode_soup(&pool, &lex, &scan);
        assert_eq!(soup.degenerate_skipped, 0);
        assert_eq!(soup.triangles, vec![(1, 0, 3), (2, 3, 0)]);
    }

    #[test]
    fn decode_soup_zero_cross_and_distinct_vertices_skip() {
        // A collinear strip triangle (three DISTINCT pool vertices,
        // exactly-zero cross product) skips on the tuple-equality test;
        // a following real triangle exports. The refs are lex ranks:
        // pool [(0,0,0), (10,0,0), (20,0,0), (0,100,0)] has
        // lex = [0, 3, 1, 2], so refs [0, 2, 3, 1] walk 0,1,2,3.
        let pool = vec![
            (0.0, 0.0, 0.0),
            (10.0, 0.0, 0.0),
            (20.0, 0.0, 0.0),
            (0.0, 100.0, 0.0),
        ];
        let lex = lex_rank_map(&pool);
        assert_eq!(lex, vec![0, 3, 1, 2]);
        let rec = FacetRecord {
            offset: 0,
            marker: 0x4A,
            ty: 1,
            header_len: 4,
            n: 4,
            width: 1,
            counts: vec![4],
            refs: vec![0, 2, 3, 1],
            end: 24,
            normal: Some((0.0, -1.0, 0.0)),
        };
        let scan = FacetScan {
            candidates: 1,
            records: vec![rec],
            unresolved_candidates: 0,
            skipped_markers: BTreeMap::new(),
        };
        let soup = decode_soup(&pool, &lex, &scan);
        // t=0: (0,1,2) collinear -> zero cross -> skipped;
        // t=1: (1,2,3) distinct non-collinear -> flipped -> (3,2,1).
        assert_eq!(soup.degenerate_skipped, 1);
        assert_eq!(soup.triangles, vec![(3, 2, 1)]);
    }

    #[test]
    fn decode_soup_polygon_fans_skip_only_repeated_vertices() {
        // 0x4c ring: fan from the first corner; a collinear fan
        // triangle (zero cross, distinct vertices) is NOT skipped on
        // the polygon path — only repeated vertices are (the twin's
        // asymmetry, F7).
        let pool = vec![(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (20.0, 0.0, 0.0)];
        let lex = lex_rank_map(&pool);
        let rec = FacetRecord {
            offset: 0,
            marker: 0x4C,
            ty: 1,
            header_len: 4,
            n: 3,
            width: 1,
            counts: vec![3],
            refs: vec![0, 1, 2],
            end: 20,
            normal: Some((-1.0, 0.0, 0.0)),
        };
        let scan = FacetScan {
            candidates: 1,
            records: vec![rec],
            unresolved_candidates: 0,
            skipped_markers: BTreeMap::new(),
        };
        let soup = decode_soup(&pool, &lex, &scan);
        assert_eq!(soup.degenerate_skipped, 0);
        assert_eq!(soup.triangles.len(), 1);
    }

    #[test]
    fn record_loops_split_by_the_count_bytes() {
        let rec = FacetRecord {
            offset: 0,
            marker: 0x4A,
            ty: 2,
            header_len: 4,
            n: 5,
            width: 1,
            counts: vec![2, 3],
            refs: vec![9, 8, 7, 6, 5],
            end: 40,
            normal: None,
        };
        assert_eq!(record_loops(&rec), vec![&[9u32, 8][..], &[7u32, 6, 5][..]]);
    }
}
