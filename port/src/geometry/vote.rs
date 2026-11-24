//! The facet-record ref-width vote and its battery (G3 stage-5 law) —
//! the twin of ``catpart/geometry/vote.py``.
//!
//! ONE ranking for every candidate parse of every facet-record family —
//! the short-form strip records (u8/u16be/u24be, relaxed u16le for the
//! 0x41/0x44 primitive), the extended 6-byte headers (0x47/0x4f) and
//! the P1g-escaped second pass (#64).  Each viable (width, counts)
//! parse is scored by the tuple
//!
//! ```text
//! (exact tiling, out-of-bounds refs, repeated refs, non-coplanar
//! normal-carrying loops, u16-over-u8, endian, width, counts length)
//! ```
//!
//! and the minimum wins; the winner's refs must then resolve in-bounds
//! (the #66 fail-closed post-vote gate).  Before #76 the short-form
//! vote ranked ``repeats`` above ``oob`` and never re-checked the
//! winner, so a big-endian misread could reach the emission (the Audi
//! R8 ``IndexError``); this module is the single rank those amendments
//! apply to, so the families cannot drift apart again.
//!
//! The scoring battery (the loop plane law and the U4-D dup-pin weld
//! targets) lives here too: the same battery scores a candidate's
//! skip-bearing loops on their dup-pinned coordinates during the vote
//! (the 2026-11-18 gap-edge width choice) and validates a dropped loop
//! at emission time (``e0b_dup_pin``).

use std::collections::{HashMap, HashSet};

use super::composite::Element;

/// Plane tolerance of the committed loop battery (stage 3b): the
/// per-coordinate normal distance bound; f32 coordinate rounding
/// ~1e-4 (twin: ``PLANE_TOL``).
pub const PLANE_TOL: f64 = 2e-3;

/// Coplanarity of one fully-resolved loop against the record's stored
/// normal (the stage-3b battery criterion; ported from the stage-4b
/// width re-test, ``not_manifold_audit.py``) — the twin's
/// ``loop_plane_status``. Returns ``("coplanar", worst)`` or
/// ``("nonplanar", max_distance)``. See the composite module header
/// for the ``powf`` probe.
pub fn loop_plane_status(
    loop_refs: &[u32],
    normal: (f64, f64, f64),
    elements: &[Element],
) -> (&'static str, f64) {
    let nn = (normal.0.powf(2.0) + normal.1.powf(2.0) + normal.2.powf(2.0)).powf(0.5);
    if nn == 0.0 {
        return ("nonplanar", 0.0);
    }
    let pts: Vec<(f64, f64, f64)> = loop_refs
        .iter()
        .map(|&r| {
            elements[r as usize]
                .1
                .expect("guarded: the caller skips loops with skip slots or out-of-space refs")
        })
        .collect();
    let p0 = pts[0];
    let mut worst = 0.0f64;
    for p in &pts[1..] {
        let d = ((p.0 - p0.0) * normal.0 + (p.1 - p0.1) * normal.1 + (p.2 - p0.2) * normal.2) / nn;
        if d.abs() > worst {
            worst = d.abs();
        }
        if d.abs() > PLANE_TOL {
            return ("nonplanar", d.abs());
        }
    }
    ("coplanar", worst)
}

/// The dup-pin weld targets for one loop — ``{skip slot: written
/// element}`` — or ``None`` when a referenced skip slot has no
/// preceding written element (unpinnable: the weld's fail-closed arm).
/// The U4-D dup law (twin: ``dup_pin_map``).
pub fn dup_pin_map(
    elements: &[Element],
    skips: &HashSet<usize>,
    loop_refs: &[u32],
) -> Option<HashMap<u32, u32>> {
    let mut pin: HashMap<u32, u32> = HashMap::new();
    for &r in loop_refs {
        let r = r as usize;
        if !skips.contains(&r) {
            continue;
        }
        let mut j = r as i64 - 1;
        while j >= 0 && elements[j as usize].1.is_none() {
            j -= 1;
        }
        if j < 0 {
            return None;
        }
        pin.insert(r as u32, j as u32);
    }
    Some(pin)
}

/// ``n`` refs of ``width`` bytes each at ``start`` (u8, u16be, u24be —
/// or u16le for the relaxed primitive's ``little`` arm) — twin:
/// ``read_refs``.
pub fn read_refs(data: &[u8], start: usize, n: usize, width: u8, little: bool) -> Vec<u32> {
    (0..n)
        .map(|j| {
            let at = start + width as usize * j;
            match width {
                1 => u32::from(data[at]),
                2 if little => u32::from(u16::from_le_bytes([data[at], data[at + 1]])),
                2 => u32::from(u16::from_be_bytes([data[at], data[at + 1]])),
                _ => u32::from_be_bytes([0, data[at], data[at + 1], data[at + 2]]),
            }
        })
        .collect()
}

/// Repeated references within a triangle (the first ``3 * tri_count``
/// refs in 3-groups) or within a counts-delimited loop — the misread
/// detector (twin: ``groups_repeat``).
pub fn groups_repeat(refs: &[u32], tri_count: u32, counts: &[u32]) -> bool {
    for start in (0..3 * tri_count as usize).step_by(3) {
        let distinct: std::collections::HashSet<u32> =
            refs[start..start + 3].iter().copied().collect();
        if distinct.len() < 3 {
            return true;
        }
    }
    let mut off = 3 * tri_count as usize;
    for &c in counts {
        // Python slices past the end to an EMPTY loop, and an empty
        // loop is shorter than its count: a malformed/over-counted
        // candidate is a repeat (the no-count 0x41 candidate carries
        // its 3-ref groups in both slots). Mirror that exactly.
        if c > 0 && off + c as usize > refs.len() {
            return true;
        }
        let loop_refs = &refs[off..off + c as usize];
        if c > 0 {
            let distinct: std::collections::HashSet<u32> = loop_refs.iter().copied().collect();
            if distinct.len() < loop_refs.len() {
                return true;
            }
        }
        off += c as usize;
    }
    false
}

/// Any reference beyond the element space (the candidate's OOB rank
/// slot; the #66 post-vote gate declines an OOB winner) — twin:
/// ``refs_oob``.
pub fn refs_oob(refs: &[u32], element_count: u32) -> bool {
    refs.iter().any(|&r| r >= element_count)
}

/// The battery's non-coplanar loop count for one candidate parse (the
/// triangles never take the plane battery); a loop landing on skip
/// slots is tested on its dup-pinned coordinates, untestable loops
/// stay silent — twin: ``loop_plane_penalty``.
pub fn loop_plane_penalty(
    refs: &[u32],
    tri_count: u32,
    counts: &[u32],
    normal: Option<(f64, f64, f64)>,
    elements: Option<&[Element]>,
) -> u32 {
    let (Some(nm), Some(els)) = (normal, elements) else {
        return 0;
    };
    let skips: HashSet<usize> = els
        .iter()
        .enumerate()
        .filter(|(_, (_, pt))| pt.is_none())
        .map(|(i, _)| i)
        .collect();
    let mut nonplanar = 0u32;
    let mut off = 3 * tri_count as usize;
    for &c in counts {
        let loop_refs = &refs[off..off + c as usize];
        off += c as usize;
        if loop_refs.is_empty() {
            continue;
        }
        if loop_refs.iter().any(|&r| r as usize >= els.len()) {
            continue;
        }
        let resolved: Vec<u32>;
        let test: &[u32] = if loop_refs.iter().any(|&r| skips.contains(&(r as usize))) {
            let Some(pin) = dup_pin_map(els, &skips, loop_refs) else {
                continue; // untestable: no battery
            };
            resolved = loop_refs
                .iter()
                .map(|&r| pin.get(&r).copied().unwrap_or(r))
                .collect();
            &resolved
        } else {
            loop_refs
        };
        let (st, _m) = loop_plane_status(test, nm, els);
        if st == "nonplanar" {
            nonplanar += 1;
        }
    }
    nonplanar
}

/// One viable (width, endian, counts) parse of a facet record (twin:
/// ``WidthCandidate``).  ``exact`` is the caller's boundary law;
/// ``tri_count`` is the extended family's leading independent
/// triangles (0 on the short forms); ``relaxed_u16`` arms the #66
/// u16-over-u8 slot and ``k`` feeds the short-form counts-length slot.
#[derive(Clone)]
pub struct WidthCandidate {
    pub width: u8,
    pub little: bool,
    pub counts: Vec<u32>,
    pub counts_end: usize,
    pub end: usize,
    pub exact: bool,
    pub tri_count: u32,
    pub relaxed_u16: bool,
    pub k: u32,
}

/// The ONE rank tuple (see the module docs) — twin: ``_rank_key``.
/// Every family's vote compares candidates through this builder, so a
/// slot-order amendment lands on all of them at once (the #76
/// divergence class).
/// The shared rank tuple (the ONE key every family compares through).
type RankKey = (u8, u8, u8, u32, u8, u8, u8, u32);

fn rank_key(candidate: &WidthCandidate, oob: bool, repeats: bool, nonplanar: u32) -> RankKey {
    (
        u8::from(!candidate.exact),
        u8::from(oob),
        u8::from(repeats),
        nonplanar,
        // #66: the relaxed family's pinned primitive is u16
        // (little-endian first); u8 is its compact fallback.
        if !candidate.relaxed_u16 || candidate.width == 2 {
            0
        } else {
            1
        },
        u8::from(candidate.little),
        // W7-B (2026-11-22): full ties prefer the WIDER candidate — the
        // narrow preference left the u8 half-read of a u16 stream
        // standing on the ties (Guntle/M3x16/LedStrips_5V's kept
        // over-use loops broke the L2 manifold gate; the wider readings
        // fix all three and keep every micro-batch file at PASS).
        255 - candidate.width,
        candidate.k,
    )
}

/// The width vote's winning parse (twin: the ``vote_ref_width`` tuple).
pub struct RefVote {
    pub refs: Vec<u32>,
    pub counts: Vec<u32>,
    pub width: u8,
    pub end: usize,
}

/// The width vote over one record's viable candidates (twin:
/// ``vote_ref_width``).  A repeating candidate is declined outright
/// when ``repeats_ranked`` is false (the #62 misread detector on the
/// committed extended u8 reading); ties resolve to the first candidate
/// in iteration order (the callers' width-ascending,
/// big-endian-first enumeration).  ``None`` when no candidate survives
/// — including the #66 post-vote gate: a winner whose refs leave the
/// element space is NOT this family's record.
pub fn vote_ref_width(
    data: &[u8],
    n: u32,
    candidates: impl IntoIterator<Item = WidthCandidate>,
    element_count: u32,
    normal: Option<(f64, f64, f64)>,
    elements: Option<&[Element]>,
    repeats_ranked: bool,
) -> Option<RefVote> {
    let mut best: Option<RefVote> = None;
    let mut best_key: Option<RankKey> = None;
    for cand in candidates {
        let refs = read_refs(data, cand.counts_end, n as usize, cand.width, cand.little);
        let repeats = groups_repeat(&refs, cand.tri_count, &cand.counts);
        if repeats && !repeats_ranked {
            continue;
        }
        let oob = refs_oob(&refs, element_count);
        let nonplanar = loop_plane_penalty(&refs, cand.tri_count, &cand.counts, normal, elements);
        let key = rank_key(&cand, oob, repeats, nonplanar);
        if best_key.is_none_or(|b| key < b) {
            best_key = Some(key);
            best = Some(RefVote {
                refs,
                counts: cand.counts.clone(),
                width: cand.width,
                end: cand.end,
            });
        }
    }
    let won = best?;
    if refs_oob(&won.refs, element_count) {
        // Fail-closed refs gate (#66, 2026-11-20), the post-vote rule
        // every family shares: the winner's parse leaves the element
        // space, so the bytes are not this family's record.
        return None;
    }
    Some(won)
}
