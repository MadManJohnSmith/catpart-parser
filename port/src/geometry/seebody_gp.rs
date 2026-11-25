//! Compact ``CATSeeBodyCont`` CAT3DFaceGP decoder (W26, 2026-11-24) —
//! the port of the Python reference module
//! ``catpart.geometry.seebody_gp`` (``src/catpart/geometry/seebody_gp.py``),
//! per spec §2.1 of ``docs/specs/phase5-viewer-spec.md``.
//!
//! The official ``empty-mesh`` parts carry a compact face-GP stream
//! inside ``CATSeeBodyCont`` / ``CATBRepModeContainer`` regions: a
//! declared vertex region whose 2-bit LCP table writes only the
//! coordinates that changed since the previous vertex, followed
//! immediately by ``0x51`` face-GP (and ``0x50`` counter-table)
//! records over that node's own element space.  The nested-store route
//! finds no 01 06 pool in these parts, so the regular composite,
//! facet, surface, grid and CATSurfacicRep routes all stay empty; this
//! module decodes the compact stream directly and sits in the export
//! fallback chain after face-gp and before the display carriers.
//!
//! Format law and fail-closed gates mirror the twin verbatim (see its
//! docstring and ``docs/evidence/2026-11-24-seebody-compact-face-gp.md``):
//! the ``04 04 fd ff`` node's ``ff ff 02 00`` token declares
//! ``n_floats`` (``n_verts = n_floats // 3``), the ``a5 d4 68 53``
//! header carries ``ceil(n_verts / 4)`` LCP-table bytes
//! (``SHAPES = {0: 3, 1: 0, 2: 1, 3: 2}``), the ``u32le write_count``
//! must equal ``sum(SHAPES[v])`` (walk-exact), and the written
//! ``f32le`` values reconstruct each element through the running
//! (x, y, z).  A record that does not close byte-exact, a reference
//! outside the node's element space, or a member that tips an
//! undirected edge past two uses is refused whole; the scan returns
//! ``None`` unless the merged soup is non-empty and manifold.
//!
//! Numeric contract (spec §2.2): coordinates are f32 widened to f64
//! once at read (every gate compares the widening, so Python and Rust
//! decide identically); the triangle records carry the native BGR
//! color bytes read back as RGB.
#![allow(clippy::suboptimal_flops)]

use super::mesh::{self, EdgeGuard};

/// The route's source label (the twin's ``seebody_gp.SOURCE``).
pub const SOURCE: &str = "seebody-compact-face-gp";

/// LCP slot shape -> written coordinate count: 0 = full write,
/// 1 = keep (no words), 2 = z only, 3 = y/z.
const SHAPES: [usize; 4] = [3, 0, 1, 2];
const NODE_MAGIC: &[u8; 4] = b"\x04\x04\xfd\xff";
const CGR_TOKEN: &[u8; 4] = b"\xff\xff\x02\x00";
const LCP_SIG: &[u8; 4] = b"\xa5\xd4\x68\x53";
const TAG_51: &[u8; 4] = b"\x02\x00\x33\x32";
const COL_MID: &[u8; 4] = b"\x04\x04\xff\xff";
/// CATIA V5's default PartBody solid color (the twin's default).
pub const DEFAULT_COLOR: [u8; 3] = [210, 210, 255];
/// Walk-exact node bound (anti-OOM): the declared vertex count must stay
/// inside a part-scale envelope before the LCP table's slot list is built.
const MAX_VERTS: usize = 3_000_000;

/// One part's compact see-body decode — the twin's
/// :class:`catpart.geometry.seebody_gp.SeeBodyScan` dataclass.
#[derive(Debug, Clone, PartialEq)]
pub struct SeeBodyScan {
    /// The written points of every accepted node, node order.
    pub vertices: Vec<(f64, f64, f64)>,
    /// The accepted triangles (per-node offsets applied).
    pub triangles: Vec<(u32, u32, u32)>,
    /// The native CATIA RGB per triangle (same order as ``triangles``).
    pub tri_colors: Vec<[u8; 3]>,
    /// Walk-exact compact nodes.
    pub nodes: usize,
    /// Every candidate record over the nodes' territories.
    pub records_total: usize,
    /// Records closing byte-exact at their extent.
    pub records_exact_close: usize,
    /// Records emitted behind the incremental edge guard.
    pub records_accepted: usize,
    /// Collapsed member triangles skipped by the strip/fan law.
    pub degenerate_filtered: usize,
}

fn nice(v: f64) -> bool {
    v.is_finite() && v.abs() < 1e9
}

fn read_p1g(data: &[u8], p: usize) -> Option<(usize, usize)> {
    if p >= data.len() {
        return None;
    }
    if data[p] == 0xFF {
        if p + 5 > data.len() {
            return None;
        }
        let val = u32::from_le_bytes(data[p + 1..p + 5].try_into().ok()?) as usize;
        Some((val, p + 5))
    } else {
        Some((data[p] as usize, p + 1))
    }
}

fn find_bytes(data: &[u8], needle: &[u8], lo: usize, hi: usize) -> Option<usize> {
    let end = hi.min(data.len());
    if lo >= end || needle.len() > end - lo {
        return None;
    }
    data[lo..end]
        .windows(needle.len())
        .position(|w| w == needle)
        .map(|off| lo + off)
}

fn find_all_bytes(data: &[u8], needle: &[u8], lo: usize, hi: usize) -> Vec<usize> {
    let end = hi.min(data.len());
    let mut out = Vec::new();
    let mut pos = lo;
    while let Some(hit) = find_bytes(data, needle, pos, end) {
        out.push(hit);
        pos = hit + 1;
    }
    out
}

fn cross_zero(a: (f64, f64, f64), b: (f64, f64, f64), c: (f64, f64, f64)) -> bool {
    let ab = (b.0 - a.0, b.1 - a.1, b.2 - a.2);
    let ac = (c.0 - a.0, c.1 - a.1, c.2 - a.2);
    let cx = ab.1 * ac.2 - ab.2 * ac.1;
    let cy = ab.2 * ac.0 - ab.0 * ac.2;
    let cz = ab.0 * ac.1 - ab.1 * ac.0;
    cx == 0.0 && cy == 0.0 && cz == 0.0
}

/// One loop's triangles under the strip/fan semantics — twin:
/// ``composite._loop_triangles`` (repeated coordinates always skipped;
/// strips also skip the exactly-zero cross product, fans do not).
/// Returns the emitted triangles and the skipped degenerate count.
fn loop_triangles(
    is_fan: bool,
    idxs: &[u32],
    pts: &[(f64, f64, f64)],
) -> (Vec<(u32, u32, u32)>, usize) {
    let mut out = Vec::new();
    let mut degenerate = 0usize;
    if idxs.len() < 3 {
        return (out, degenerate);
    }
    if is_fan {
        let a = pts[idxs[0] as usize];
        for t in 1..idxs.len() - 1 {
            let b = pts[idxs[t] as usize];
            let c = pts[idxs[t + 1] as usize];
            if a != b && b != c && a != c {
                out.push((idxs[0], idxs[t], idxs[t + 1]));
            } else {
                degenerate += 1;
            }
        }
    } else {
        for t in 0..idxs.len() - 2 {
            let tri = if t % 2 == 1 {
                (idxs[t + 2], idxs[t + 1], idxs[t])
            } else {
                (idxs[t], idxs[t + 1], idxs[t + 2])
            };
            let a = pts[tri.0 as usize];
            let b = pts[tri.1 as usize];
            let c = pts[tri.2 as usize];
            if a != b && b != c && a != c && !cross_zero(a, b, c) {
                out.push(tri);
            } else {
                degenerate += 1;
            }
        }
    }
    (out, degenerate)
}

struct CgrNode {
    pos: usize,
    n_verts: usize,
    fend: usize,
    elems: Vec<Option<(f64, f64, f64)>>,
}

#[allow(unused_assignments)] // the running (x, y, z) carry the LCP slots
fn find_cgr_nodes(data: &[u8]) -> Vec<CgrNode> {
    let mut nodes = Vec::new();
    let n = data.len();
    let mut pos = 0usize;
    while let Some(npos) = find_bytes(data, NODE_MAGIC, pos, n) {
        if let Some(tok) = find_bytes(data, CGR_TOKEN, npos + 4, (npos + 64).min(n))
            && let Some((n_floats, p2)) = read_p1g(data, tok + 4)
            && n_floats > 0
            && n_floats % 3 == 0
            && n_floats / 3 <= MAX_VERTS
        {
            let n_verts = n_floats / 3;
            if let Some(sig) = find_bytes(data, LCP_SIG, p2, (p2 + 32).min(n)) {
                let tab_start = sig + 5;
                let tab_len = n_verts.div_ceil(4);
                let wc_pos = tab_start + tab_len;
                if wc_pos + 4 <= n {
                    let wc =
                        u32::from_le_bytes(data[wc_pos..wc_pos + 4].try_into().unwrap()) as usize;
                    let mut slots = Vec::with_capacity(n_verts);
                    'slot_fill: for &b in &data[tab_start..tab_start + tab_len] {
                        for shift in [0, 2, 4, 6] {
                            if slots.len() == n_verts {
                                break 'slot_fill;
                            }
                            slots.push(((b >> shift) & 3) as usize);
                        }
                    }
                    let ewc: usize = slots.iter().map(|&v| SHAPES[v]).sum();
                    if wc == ewc && wc_pos + 4 + 4 * wc <= n {
                        let mut fp = wc_pos + 4;
                        let (mut x, mut y, mut z) = (0.0f64, 0.0f64, 0.0f64);
                        let mut elems = Vec::with_capacity(n_verts);
                        let mut ok = true;
                        for v in slots {
                            match SHAPES[v] {
                                0 => {
                                    elems.push(None);
                                    continue;
                                }
                                3 => {
                                    x = f32::from_le_bytes(data[fp..fp + 4].try_into().unwrap())
                                        as f64;
                                    y = f32::from_le_bytes(data[fp + 4..fp + 8].try_into().unwrap())
                                        as f64;
                                    z = f32::from_le_bytes(
                                        data[fp + 8..fp + 12].try_into().unwrap(),
                                    ) as f64;
                                    fp += 12;
                                }
                                2 => {
                                    y = f32::from_le_bytes(data[fp..fp + 4].try_into().unwrap())
                                        as f64;
                                    z = f32::from_le_bytes(data[fp + 4..fp + 8].try_into().unwrap())
                                        as f64;
                                    fp += 8;
                                }
                                _ => {
                                    z = f32::from_le_bytes(data[fp..fp + 4].try_into().unwrap())
                                        as f64;
                                    fp += 4;
                                }
                            }
                            if !nice(x) || !nice(y) || !nice(z) {
                                ok = false;
                                break;
                            }
                            elems.push(Some((x, y, z)));
                        }
                        if ok {
                            nodes.push(CgrNode {
                                pos: npos,
                                n_verts,
                                fend: fp,
                                elems,
                            });
                        }
                    }
                }
            }
        }
        pos = npos + 4;
    }
    nodes
}

/// Decode a part's compact see-body nodes, fail-closed — the twin's
/// :func:`catpart.geometry.seebody_gp.scan_part`.
pub fn scan_part(data: &[u8]) -> Option<SeeBodyScan> {
    let nodes = find_cgr_nodes(data);
    if nodes.is_empty() {
        return None;
    }
    let mut all_pts: Vec<(f64, f64, f64)> = Vec::new();
    let mut all_tris: Vec<(u32, u32, u32)> = Vec::new();
    let mut all_cols: Vec<[u8; 3]> = Vec::new();
    let (mut tot_recs, mut tot_exact, mut tot_acc, mut tot_degenerate) =
        (0usize, 0usize, 0usize, 0usize);

    for (ni, node) in nodes.iter().enumerate() {
        let hi = if ni + 1 < nodes.len() {
            nodes[ni + 1].pos
        } else {
            data.len()
        };
        let fend = node.fend;
        let width: usize = if node.n_verts <= 255 { 1 } else { 2 };

        // Collect (record_start, flag, kind_offset, optional RGB).
        let mut events: Vec<(usize, u8, usize, Option<[u8; 3]>)> = Vec::new();
        for o in find_all_bytes(data, TAG_51, fend, hi) {
            if o >= fend + 5
                && data[o - 5] == 0x51
                && o + 49 <= hi
                && data[o + 44] == 0x00
                && data[o + 45] == 0x03
            {
                let has_col = o >= fend + 13
                    && (data[o - 13] == 0x20 || data[o - 13] == 0x30)
                    && &data[o - 12..o - 8] == COL_MID;
                let rstart = if has_col { o - 13 } else { o - 5 };
                let rgb = if has_col {
                    Some([data[o - 6], data[o - 7], data[o - 8]])
                } else {
                    None
                };
                events.push((rstart, 0x51, o + 44, rgb));
            }
        }
        let mut terms: Vec<usize> = Vec::new();
        for mid in find_all_bytes(data, COL_MID, fend + 1, hi) {
            let o = mid - 1;
            if o + 9 <= hi && (data[o] == 0x20 || data[o] == 0x30) {
                if data[o + 8] == 0x00 {
                    terms.push(o);
                } else if data[o + 8] == 0x50 && o + 15 <= hi {
                    let extra = u16::from_le_bytes([data[o + 13], data[o + 14]]) as usize;
                    if extra <= 256 {
                        let kind_off = o + 55 + extra;
                        if kind_off + 7 <= hi
                            && data[kind_off] == 0x00
                            && data[kind_off + 1] == 0x00
                        {
                            events.push((
                                o,
                                0x50,
                                kind_off,
                                Some([data[o + 7], data[o + 6], data[o + 5]]),
                            ));
                        }
                    }
                }
            }
        }
        events.sort_by_key(|e| e.0);

        let mut points: Vec<(f64, f64, f64)> = Vec::new();
        let mut written_rank: Vec<Option<u32>> = vec![None; node.n_verts];
        for (i, opt_pt) in node.elems.iter().enumerate() {
            if let Some(pt) = opt_pt {
                written_rank[i] = Some(points.len() as u32);
                points.push(*pt);
            }
        }
        let resolve = |r: usize| -> Option<u32> {
            if r >= node.n_verts {
                return None;
            }
            if let Some(wr) = written_rank[r] {
                return Some(wr);
            }
            let mut j = r;
            while j > 0 {
                j -= 1;
                if let Some(wr) = written_rank[j] {
                    return Some(wr);
                }
            }
            None
        };
        let read_ref = |p: usize| -> (usize, usize) {
            if width == 1 {
                (data[p] as usize, p + 1)
            } else {
                (u16::from_be_bytes([data[p], data[p + 1]]) as usize, p + 2)
            }
        };

        let mut guard = EdgeGuard::default();
        let mut node_tris: Vec<(u32, u32, u32)> = Vec::new();
        let mut node_cols: Vec<[u8; 3]> = Vec::new();
        let mut last_rgb = DEFAULT_COLOR;
        tot_recs += events.len();

        for (idx, &(rstart, flag, kind_off, rgb)) in events.iter().enumerate() {
            if let Some(color) = rgb {
                last_rgb = color;
            }
            let mut rend = if idx + 1 < events.len() {
                events[idx + 1].0
            } else {
                hi
            };
            for &tm in &terms {
                if tm > rstart && tm < rend {
                    rend = tm;
                    break;
                }
            }
            let n_tris = data[kind_off + 2] as usize;
            let n_strips = data[kind_off + 3] as usize;
            let n_fans = data[kind_off + 4] as usize;
            let mut p = kind_off + 5 + if flag == 0x51 { 8 } else { 2 };
            let mut rec_tris: Vec<(u32, u32, u32)> = Vec::new();
            let mut rec_degenerate = 0usize;
            let mut ok = true;

            for _ in 0..n_tris {
                if p + 3 * width > rend {
                    ok = false;
                    break;
                }
                let (a, p1) = read_ref(p);
                let (b, p2) = read_ref(p1);
                let (c, p3) = read_ref(p2);
                p = p3;
                match (resolve(a), resolve(b), resolve(c)) {
                    (Some(ra), Some(rb), Some(rc)) => {
                        if ra != rb && rb != rc && ra != rc {
                            rec_tris.push((ra, rb, rc));
                        } else {
                            rec_degenerate += 1;
                        }
                    }
                    _ => {
                        ok = false;
                        break;
                    }
                }
            }
            if ok && (n_strips > 0 || n_fans > 0) {
                if p + (n_strips + n_fans) * width > rend {
                    ok = false;
                } else {
                    let mut cnts = Vec::with_capacity(n_strips + n_fans);
                    for _ in 0..(n_strips + n_fans) {
                        let (c, np) = read_ref(p);
                        p = np;
                        cnts.push(c);
                    }
                    for (si, c) in cnts.into_iter().enumerate() {
                        if c < 3 || p + c * width > rend {
                            ok = false;
                            break;
                        }
                        let mut rloop = Vec::with_capacity(c);
                        for _ in 0..c {
                            let (r, np) = read_ref(p);
                            p = np;
                            match resolve(r) {
                                Some(rr) => rloop.push(rr),
                                None => {
                                    ok = false;
                                    break;
                                }
                            }
                        }
                        if !ok {
                            break;
                        }
                        let (tris, degenerate) = loop_triangles(si >= n_strips, &rloop, &points);
                        rec_tris.extend(tris);
                        rec_degenerate += degenerate;
                    }
                }
            }
            let exact = ok && (p == rend || p + 1 == rend);
            if exact {
                tot_exact += 1;
            }
            if exact && !rec_tris.is_empty() && guard.admit(&rec_tris) {
                node_cols.extend(std::iter::repeat_n(last_rgb, rec_tris.len()));
                node_tris.extend(rec_tris);
                tot_degenerate += rec_degenerate;
                tot_acc += 1;
            }
        }
        if !node_tris.is_empty() {
            let base = all_pts.len() as u32;
            all_pts.extend(points);
            all_tris.extend(
                node_tris
                    .into_iter()
                    .map(|(a, b, c)| (a + base, b + base, c + base)),
            );
            all_cols.extend(node_cols);
        }
    }

    if all_tris.is_empty() || !mesh::mesh_stats(&all_tris).manifold {
        return None;
    }
    Some(SeeBodyScan {
        vertices: all_pts,
        triangles: all_tris,
        tri_colors: all_cols,
        nodes: nodes.len(),
        records_total: tot_recs,
        records_exact_close: tot_exact,
        records_accepted: tot_acc,
        degenerate_filtered: tot_degenerate,
    })
}

/// The summary warning's prose — twin:
/// :func:`catpart.geometry.seebody_gp.warning_detail`.
pub fn warning_detail(scan: &SeeBodyScan) -> String {
    let mut detail = format!(
        "{} compact see-body node(s), {}/{} face record(s) accepted \
         ({} byte-exact closures), {} vertices, {} triangles: the \
         declared vertex region's 2-bit LCP table walk-exact gate, the \
         per-record byte-exact closure gate and the incremental edge \
         guard (docs/evidence/2026-11-24-seebody-compact-face-gp.md)",
        scan.nodes,
        scan.records_accepted,
        scan.records_total,
        scan.records_exact_close,
        scan.vertices.len(),
        scan.triangles.len(),
    );
    if scan.degenerate_filtered > 0 {
        detail.push_str(&format!(
            "; {} collapsed (zero-area or repeated-coordinate) member \
             triangle(s) skipped by the strip/fan law",
            scan.degenerate_filtered
        ));
    }
    detail
}

#[cfg(test)]
mod tests {
    use super::*;

    const TETRA: [(f64, f64, f64); 4] = [
        (0.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        (0.0, 10.0, 0.0),
        (0.0, 0.0, 10.0),
    ];
    const TETRA_TRIS: [(u32, u32, u32); 4] = [(0, 2, 1), (0, 1, 3), (1, 2, 3), (0, 3, 2)];

    fn lcp_node(points: &[(f64, f64, f64)], slots: &[usize]) -> Vec<u8> {
        assert_eq!(points.len(), slots.len());
        let mut floats: Vec<f32> = Vec::new();
        for (pt, &slot) in points.iter().zip(slots) {
            match SHAPES[slot] {
                3 => floats.extend([pt.0 as f32, pt.1 as f32, pt.2 as f32]),
                2 => floats.extend([pt.1 as f32, pt.2 as f32]),
                1 => floats.push(pt.2 as f32),
                _ => {}
            }
        }
        let n_verts = points.len();
        let mut out = Vec::new();
        out.extend_from_slice(NODE_MAGIC);
        out.extend_from_slice(CGR_TOKEN);
        out.push((3 * n_verts) as u8);
        out.extend_from_slice(&[0x11; 5]);
        out.extend_from_slice(LCP_SIG);
        out.push(0);
        let mut table = vec![0u8; n_verts.div_ceil(4)];
        for (i, &slot) in slots.iter().enumerate() {
            table[i / 4] |= (slot as u8) << (2 * (i % 4));
        }
        out.extend_from_slice(&table);
        out.extend_from_slice(&(floats.len() as u32).to_le_bytes());
        for value in floats {
            out.extend_from_slice(&value.to_le_bytes());
        }
        out
    }

    fn face_record(tris: &[(u32, u32, u32)], n_verts: usize, color: Option<[u8; 3]>) -> Vec<u8> {
        let width = if n_verts <= 255 { 1 } else { 2 };
        let mut out = Vec::new();
        if let Some([r, g, b]) = color {
            out.extend_from_slice(&[0x30, 0x04, 0x04, 0xff, 0xff, b, g, r]);
        }
        out.push(0x51);
        out.extend_from_slice(&1u32.to_le_bytes());
        out.extend_from_slice(TAG_51);
        out.extend_from_slice(&[0x22; 40]);
        out.extend_from_slice(&3u16.to_be_bytes());
        out.extend_from_slice(&[tris.len() as u8, 0, 0]);
        out.extend_from_slice(&[0x33; 8]);
        for tri in tris {
            for &v in &[tri.0, tri.1, tri.2] {
                if width == 1 {
                    out.push(v as u8);
                } else {
                    out.extend_from_slice(&(v as u16).to_be_bytes());
                }
            }
        }
        out.push(0);
        out
    }

    fn compact_part(color: Option<[u8; 3]>, tris: &[(u32, u32, u32)], tail: &[u8]) -> Vec<u8> {
        let mut out = lcp_node(&TETRA, &[0, 0, 0, 0]);
        out.extend(face_record(tris, TETRA.len(), color));
        out.extend_from_slice(tail);
        out
    }

    #[test]
    fn tetra_walks_exact_and_is_manifold() {
        let scan = scan_part(&compact_part(None, &TETRA_TRIS, &[])).unwrap();
        assert_eq!(scan.vertices.len(), 4);
        assert_eq!(scan.triangles.len(), 4);
        assert_eq!(scan.records_total, 1);
        assert_eq!(scan.records_exact_close, 1);
        assert_eq!(scan.records_accepted, 1);
        assert!(mesh::mesh_stats(&scan.triangles).manifold);
    }

    #[test]
    fn color_header_is_bgr_to_rgb() {
        let scan = scan_part(&compact_part(Some([0x30, 0x20, 0x10]), &TETRA_TRIS, &[])).unwrap();
        assert_eq!(scan.tri_colors, vec![[0x30, 0x20, 0x10]; 4]);
    }

    #[test]
    fn default_color_is_catia_lavender_gray() {
        let scan = scan_part(&compact_part(None, &TETRA_TRIS, &[])).unwrap();
        assert_eq!(scan.tri_colors, vec![DEFAULT_COLOR; 4]);
    }

    #[test]
    fn a_wrong_write_count_declines_the_node() {
        let mut data = compact_part(None, &TETRA_TRIS, &[]);
        let at = find_bytes(&data, LCP_SIG, 0, data.len()).unwrap() + 5 + 1;
        assert_eq!(u32::from_le_bytes(data[at..at + 4].try_into().unwrap()), 12);
        data[at..at + 4].copy_from_slice(&13u32.to_le_bytes());
        assert!(scan_part(&data).is_none());
    }

    #[test]
    fn an_over_using_edge_refuses_the_record() {
        let tris = [(0, 1, 2), (0, 1, 3), (0, 1, 3)];
        assert!(scan_part(&compact_part(None, &tris, &[])).is_none());
    }

    #[test]
    fn a_record_that_does_not_close_is_not_emitted() {
        assert!(scan_part(&compact_part(None, &TETRA_TRIS, &[0, 0])).is_none());
    }

    #[test]
    fn corpus_samples_if_available() {
        let root = concat!(env!("CARGO_MANIFEST_DIR"), "/../corpus/");
        let cases = [
            (
                "zhoujason457-stack/CAA_PrjSrc/CAAElecHarnessItf.edu/CNext/resources/graphic/Ehi_BundleSegment1_2.CATPart",
                5,
                2919,
            ),
            (
                "zhoujason457-stack/CAA_PrjSrc/CAAElecHarnessItf.edu/CNext/resources/graphic/Ehi_Equipment.CATPart",
                55,
                1008,
            ),
            (
                "zhoujason457-stack/CAA_PrjSrc/CAAElecDeviceItf.edu/CNext/resources/graphic/PN-0812000-1707.CATPart",
                84,
                718,
            ),
        ];
        for (rel, records, triangles) in cases {
            let data = match std::fs::read(format!("{root}{rel}")) {
                Ok(data) => data,
                Err(_) => continue,
            };
            let scan = scan_part(&data).expect(rel);
            assert_eq!(scan.records_total, records, "{rel}");
            assert_eq!(scan.records_exact_close, records, "{rel}");
            assert_eq!(scan.triangles.len(), triangles, "{rel}");
        }
    }
}
