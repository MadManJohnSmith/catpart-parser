//! The ``CATSurfacicRep`` patch sub-record stream — the CAT3DFaceGP law
//! (#63) — the port of the Python reference module
//! ``catpart.geometry.face_gp`` (``src/catpart/geometry/face_gp.py``),
//! per spec §2.1 of ``docs/specs/phase5-viewer-spec.md``.
//!
//! The bag-rep family's remaining geometry carrier (issue #63, part of
//! the #50 L2 residuals): inside a ``CATSurfacicRep`` class record, the
//! byte pattern ``30 04 04 ff ff ff d2 d2`` + flag opens a sub-record
//! stream, and the ``0x51`` sub-records carry a patch mesh under the
//! CAT3DFaceGP law — the micro-probe measurement of 2026-11-20 (issue
//! #63 comment 3, ``scripts/triage/probe_t63_face_gp.py``) plus the
//! pairing refinement (``probe_t63_pairing.py``), verified byte-exact
//! on the anchors (40/604 exact closures).  The route sits in the
//! export fallback chain AFTER the facet stores, the ``a5 03 34``
//! B-spline surfaces and the structured E5 grids and BEFORE the
//! point-only display fallback: a part whose gated sub-records fold
//! into a non-empty manifold mesh exports it (source label
//! ``bagrep-face-gp``, summary block ``bagrep_face_gp``); a part with
//! no gated sub-records, no clean array or no folded triangles falls
//! through to the display carriers with its summary unchanged.
//!
//! The law, the gates and the assembly mirror the twin verbatim (see
//! its docstring for the full statement and the evidence citations):
//! class records frame the scan file-wide (``u32le`` length prefix +
//! name, BOTH names, spans walked at ``CATSurfacicRep``), the record's
//! declared f32 point array starts ONE WORD after its count (the
//! measured writer layout) under the full coordinate envelope (finite,
//! ``<= COORD_CEIL``, not denormal junk), the ``0x51`` sub-record
//! decodes ``kind/N_tris/N_strips/N_fans`` at ``+57`` (``u32le``; kind
//! 3), ``u16be`` indices after the first ``ff 7f`` / ``01 80`` marker
//! at ``>= +73`` (strips/fans as ``count:u32be`` + ``count`` values),
//! the strict per-sub-record gate is fail-closed on every axis
//! (byte-exact closure ``pos == rel_len - 1``, ``mult-3`` in-bounds
//! indices, no repeated-index triangle, self-manifold) and the
//! assembly folds the gated members in order under the unordered
//! dedup (first copy wins) and the incremental mesh-safe guard (a
//! member that tips an edge past two uses is refused whole, no trace).
//! Zero-area triangles with distinct indices (the writer's duplicate
//! pinned coordinates) ride as decoded — no skip convention fires.
//!
//! Evidence: the twin's docstring cites the issue #63 probe comments
//! and ``docs/evidence/2026-11-21-bagrep-face-gp.md`` (the pinned law
//! and the corpus measurement); the dedup/guard levers trace to the
//! composite stage-15 dedup law and the 2026-11-18 manifold-assembly
//! gate (``docs/evidence/2026-11-18-extended-header-family.md``).
//!
//! Numeric contract (spec §2.2): decode module — coordinates are f32
//! widened to f64 once at read (every gate compares the widening, so
//! Python and Rust decide identically; the PLY write-back ``as f32``
//! recovers the load bytes exactly); the ``clippy::suboptimal_flops``
//! allow below is the pinned carve-out (mul_add changes rounding and
//! flips exact-equality decisions); see the crate docs in ``../lib.rs``
//! for the full policy.
#![allow(clippy::suboptimal_flops)]

use std::collections::HashSet;

use super::grid::COORD_CEIL;
use super::mesh;
use super::store::find_all;

/// The route's source label (the twin's ``face_gp.SOURCE``).
pub const SOURCE: &str = "bagrep-face-gp";

/// The 8-byte pattern + the two sub-record flags: ``0x51`` = the face-GP
/// framing (kind 3, marker-anchored ``u16be`` stream), ``0x50`` = the
/// counter-table framing (kind 0, table-anchored ``u16be`` stream —
/// decoded 2026-11-22); ``0x00`` = boundary artifact: ignored.
pub const SUBREC: &[u8; 8] = b"\x30\x04\x04\xff\xff\xff\xd2\xd2";
pub const FLAG_FACE_GP: u8 = 0x51;
pub const FLAG_COUNTER_TABLE: u8 = 0x50;
/// The kind/counts header sits at ``+57..+72``; the ``0x51`` stream
/// starts after the first marker at ``>= +73`` (or at ``+73`` when
/// neither appears); the ``0x50`` stream starts at ``+74`` — one pad
/// word after the header, before the ``u16be`` values and the count
/// table.
pub const HEADER_AT: usize = 57;
pub const STREAM_AT: usize = 73;
pub const COUNTER_TABLE_AT: usize = 74;
const MARKERS: [&[u8; 2]; 2] = [b"\xff\x7f", b"\x01\x80"];
/// kind 3 = the CAT3DFaceGP primitive of the ``0x51`` framing; kind 0 =
/// the counter-table primitive of the ``0x50`` framing (both measured
/// corpus-wide, every sub-record carrying its framing's kind).
pub const KIND_FACE_GP: u32 = 3;
pub const KIND_COUNTER_TABLE: u32 = 0;
/// Count-first framing bounds (the bag-rep measurement's).
const MAX_FLOATS: u32 = 3_000_000;
/// The candidate filter's bounded head (the probe's pool-scale bound).
const HEAD_WORDS: usize = 96;
const HEAD_ABS_MAX: f64 = 1e9;
/// The head gate's clean-share and fill-run bounds (the probe's).
const HEAD_MIN_NONZERO: f64 = 0.5;
const HEAD_MAX_CONST_RUN: usize = 64;
/// The full-array coordinate envelope: part-scale, no denormal junk.
/// The corpus's junk arrays are denormal clouds (1e-38..1e-45) and
/// non-finite tails; the real arrays' sub-floor values are rounding
/// artifacts at 5.7e-14 / 7.3e-15.  ``COORD_CEIL`` = 1e5 is the display
/// envelope's ceiling.
const DENORMAL_MAX: f64 = 1e-30;
/// The class-record framing: a ``u32le`` length prefix followed by the
/// record name, file-wide (the probe's boundary law, BOTH names — a
/// span ends at the next record of either kind).  The route walks the
/// ``CATSurfacicRep`` spans.
const CLASS_RECORDS: [(&[u8], u32); 2] = [(b"CAT3DBagRep", 11), (b"CATSurfacicRep", 14)];

/// One patch sub-record's decode under its framing's law — the twin's
/// :class:`catpart.geometry.face_gp.SubRecord` dataclass.  ``flag``
/// names the framing (``0x51`` face-GP, ``0x50`` counter table); the
/// gate checks ``kind`` against the framing's kind.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SubRecord {
    /// The ``+57`` kind word (3 = the face GP, 0 = the counter table).
    pub kind: u32,
    /// The declared independent-triangle count.
    pub n_tris: u32,
    /// The declared strip count.
    pub n_strips: u32,
    /// The declared fan count.
    pub n_fans: u32,
    /// The stream position after the law's reads (relative to the start).
    pub pos_rel: usize,
    /// The sub-record's byte length (pattern through the next opening).
    pub rel_len: usize,
    /// ``pos == rel_len - 1`` — the trailing dangling byte.
    pub closed_exact: bool,
    /// The raw ``u16be`` reads (the mult-3 gate's input).
    pub indices: Vec<u32>,
    /// The decoded ``v = idx // 3`` triples (windows and fans included).
    pub triangles: Vec<(u32, u32, u32)>,
    /// The framing flag (``0x51`` face-GP, ``0x50`` counter table).
    pub flag: u8,
}

/// One part's face-gp decode: the folded patch meshes — the twin's
/// :class:`catpart.geometry.face_gp.FaceGpScan` dataclass.  ``vertices``
/// are the records' declared point arrays concatenated in span order
/// (exact f32 widenings); ``triangles`` the folded, gated sub-record
/// triangles with per-span index offsets.  The counters feed the
/// summary's ``bagrep_face_gp`` block.
#[derive(Debug, Clone, PartialEq)]
pub struct FaceGpScan {
    /// The declared arrays' points, span order (f32 widenings).
    pub vertices: Vec<(f64, f64, f64)>,
    /// The folded triangles (per-span offsets applied).
    pub triangles: Vec<(u32, u32, u32)>,
    /// Spans that emitted triangles (patch streams).
    pub records: usize,
    /// Every ``0x51``/``0x50`` sub-record in the ``CATSurfacicRep`` spans.
    pub sub_records: usize,
    /// Strict-gate passes (both framings).
    pub sub_records_gated: usize,
    /// Assembly refusals (the incremental guard).
    pub guard_refused: usize,
    /// Unordered duplicate triangles dropped.
    pub dedup_dropped: usize,
    /// The ``0x50`` counter-table sub-records.
    pub sub_records_counter: usize,
    /// Their strict-gate passes.
    pub sub_records_counter_gated: usize,
}

fn u32_le(data: &[u8], at: usize) -> u32 {
    u32::from_le_bytes([data[at], data[at + 1], data[at + 2], data[at + 3]])
}

fn u16_be(data: &[u8], at: usize) -> u32 {
    u16::from_be_bytes([data[at], data[at + 1]]) as u32
}

fn u32_be(data: &[u8], at: usize) -> u32 {
    u32::from_be_bytes([data[at], data[at + 1], data[at + 2], data[at + 3]])
}

/// One ``f32le`` read widened to ``f64`` (the numeric contract's single
/// widening; the PLY write-back recovers the bytes exactly).
fn f32_wide(data: &[u8], at: usize) -> f64 {
    f32::from_le_bytes([data[at], data[at + 1], data[at + 2], data[at + 3]]) as f64
}

/// The bag-rep class records' ``(start, end, is_surfacic)``, file-wide —
/// the twin's :func:`catpart.geometry.face_gp._class_record_spans`.
///
/// A record opens at the ``u32le`` length prefix preceding its name
/// (``CAT3DBagRep`` = 11, ``CATSurfacicRep`` = 14 — the probe's
/// framing) and ends at the next record of either kind (or the file
/// end), so the last sub-record's extent reaches the true boundary.
fn class_record_spans(data: &[u8]) -> Vec<(usize, usize, bool)> {
    let mut found: Vec<(usize, bool)> = Vec::new();
    for (name, length) in CLASS_RECORDS {
        let mut pos = 0usize;
        while let Some(hit) = super::store::find(data, name, pos, data.len()) {
            if hit >= 4 && u32_le(data, hit - 4) == length {
                found.push((hit - 4, name == b"CATSurfacicRep"));
            }
            pos = hit + 1;
        }
    }
    found.sort_by_key(|&(start, _)| start);
    let mut out = Vec::new();
    for i in 0..found.len() {
        let (start, surfacic) = found[i];
        let end = if i + 1 < found.len() {
            found[i + 1].0
        } else {
            data.len()
        };
        out.push((start, end, surfacic));
    }
    out
}

/// The patch sub-record openings in ``[lo, hi)``, in order — the twin's
/// :func:`catpart.geometry.face_gp._subrecord_positions`.  Both framings
/// count (``0x51`` face-GP and ``0x50`` counter table): a sub-record's
/// extent ends at the NEXT sub-record of either kind, so an interleaved
/// ``0x50`` record ends the ``0x51`` it sits inside — the measured
/// writer emits them interleaved, and a span that runs past a
/// neighboring sub-record cannot close byte-exact.
fn subrecord_positions(data: &[u8], lo: usize, hi: usize) -> Vec<usize> {
    find_all(data, SUBREC, lo, hi)
        .into_iter()
        .filter(|&hit| data[hit + 8] == FLAG_FACE_GP || data[hit + 8] == FLAG_COUNTER_TABLE)
        .collect()
}

/// The count-first measurement's candidate filter (the probe's) — the
/// twin's :func:`catpart.geometry.face_gp._head_gate`.
fn head_gate(head: &[f64]) -> bool {
    let mut nonzero = 0usize;
    let mut previous: Option<f64> = None;
    let mut run = 1usize;
    let mut longest = 1usize;
    for &value in head {
        if !value.is_finite() || value.abs() >= HEAD_ABS_MAX {
            return false;
        }
        if value != 0.0 {
            nonzero += 1;
        }
        match previous {
            Some(prev) if value == prev => {
                run += 1;
                if run > longest {
                    longest = run;
                }
            }
            _ => run = 1,
        }
        previous = Some(value);
    }
    nonzero as f64 >= HEAD_MIN_NONZERO * head.len() as f64 && longest <= HEAD_MAX_CONST_RUN
}

/// The full-array coordinate envelope (the shipped array gate) — the
/// twin's :func:`catpart.geometry.face_gp._word_ok`.
fn word_ok(value: f64) -> bool {
    value.is_finite() && value.abs() <= COORD_CEIL && (value == 0.0 || value.abs() >= DENORMAL_MAX)
}

/// The clean declared f32 arrays in ``[lo, hi)`` as ``(count_at,
/// data_start, floats, points)`` — the twin's
/// :func:`catpart.geometry.face_gp._declared_arrays`.
///
/// Count-first framing with the data start ONE WORD AFTER the count
/// (the measured writer layout), the bounded head as the candidate
/// filter, and the full-array envelope as the acceptance gate.  Arrays
/// contained in a longer one are dropped (the probe's containment law;
/// ties sort by start, longer first).
fn declared_arrays(data: &[u8], lo: usize, hi: usize) -> Vec<(usize, usize, u32, u32)> {
    let mut found: Vec<(usize, usize, u32, u32)> = Vec::new();
    let mut seen: HashSet<(usize, u32)> = HashSet::new();
    let scan_hi = lo.max(hi.saturating_sub(4));
    let mut offset = lo;
    while offset < scan_hi {
        if data[offset + 3] == 0 {
            let count = u32_le(data, offset);
            if (9..=MAX_FLOATS).contains(&count) && count.is_multiple_of(3) {
                let start = offset + 8;
                let bytes = 4 * count as usize;
                if start + bytes <= hi && seen.insert((start, count)) {
                    // the bounded head as the candidate filter
                    let head_len = HEAD_WORDS.min(count as usize);
                    let head: Vec<f64> = (0..head_len)
                        .map(|i| f32_wide(data, start + 4 * i))
                        .collect();
                    if head_gate(&head) {
                        let words: Vec<f64> = (0..count as usize)
                            .map(|i| f32_wide(data, start + 4 * i))
                            .collect();
                        if words.iter().all(|&value| word_ok(value)) {
                            found.push((offset, start, count, count / 3));
                        }
                    }
                }
            }
        }
        offset += 1;
    }
    found.sort_by_key(|&(_offset, start, floats, _points)| (start, std::cmp::Reverse(floats)));
    let mut keep: Vec<(usize, usize, u32, u32)> = Vec::new();
    for item in &found {
        let item_end = item.1 + 4 * item.2 as usize;
        if keep.iter().any(|kept| {
            let kept_end = kept.1 + 4 * kept.2 as usize;
            kept.1 <= item.1 && kept_end >= item_end
        }) {
            continue;
        }
        keep.push(*item);
    }
    keep
}

/// One patch sub-record's decode under its framing's law — the twin's
/// :func:`catpart.geometry.face_gp.decode_sub_record`.  The flag byte
/// at ``+8`` picks the framing: ``0x51`` decodes the CAT3DFaceGP law
/// (kind 3, marker-anchored stream), ``0x50`` the counter-table law
/// (kind 0, table-anchored stream).
pub fn decode_sub_record(data: &[u8], start: usize, end: usize) -> SubRecord {
    if start + 8 < data.len() && data[start + 8] == FLAG_COUNTER_TABLE {
        return decode_counter_table(data, start, end);
    }
    decode_face_gp(data, start, end)
}

/// The counter-table law on one ``0x50`` sub-record — the twin's
/// :func:`catpart.geometry.face_gp._decode_counter_table`.
///
/// Measured corpus-wide (every ``0x50`` sub-record of the 44-carrier
/// population closes byte-exact under it — 100/100): the same
/// ``kind/N_tris/N_strips/N_fans`` header at ``+57`` with kind **0**,
/// then ONE pad word at ``+73`` and the ``u16be`` stream at ``+74``:
/// ``3 * N_tris`` values (the independent triangles), a **count
/// table** (one ``u16be`` count per strip, then one per fan), then the
/// table's values concatenated in the same order — strips through
/// their sliding windows, fans fanned from their first vertex.  The
/// reads close byte-exact at ``rel_len - 1`` and every value is
/// ``3 * vertex_id`` into the span's declared array.
fn decode_counter_table(data: &[u8], start: usize, end: usize) -> SubRecord {
    let rel_len = end.saturating_sub(start);
    if start + HEADER_AT + 16 > data.len() {
        return SubRecord {
            kind: 0,
            n_tris: 0,
            n_strips: 0,
            n_fans: 0,
            pos_rel: rel_len,
            rel_len,
            closed_exact: false,
            indices: Vec::new(),
            triangles: Vec::new(),
            flag: FLAG_COUNTER_TABLE,
        };
    }
    let kind = u32_le(data, start + HEADER_AT);
    let n_tris = u32_le(data, start + HEADER_AT + 4);
    let n_strips = u32_le(data, start + HEADER_AT + 8);
    let n_fans = u32_le(data, start + HEADER_AT + 12);
    let mut pos = COUNTER_TABLE_AT;
    let mut indices: Vec<u32> = Vec::new();
    let mut counts: Vec<u32> = Vec::new();
    let mut ok = true;
    for _ in 0..(n_tris.saturating_mul(3)) {
        if pos + 2 > rel_len {
            ok = false;
            break;
        }
        indices.push(u16_be(data, start + pos));
        pos += 2;
    }
    if ok {
        for _ in 0..(n_strips + n_fans) {
            if pos + 2 > rel_len {
                ok = false;
                break;
            }
            counts.push(u16_be(data, start + pos));
            pos += 2;
        }
    }
    if ok {
        for &count in &counts {
            for _ in 0..count {
                if pos + 2 > rel_len {
                    ok = false;
                    break;
                }
                indices.push(u16_be(data, start + pos));
                pos += 2;
            }
            if !ok {
                break;
            }
        }
    }
    let mut triangles: Vec<(u32, u32, u32)> = Vec::new();
    // bound by what was READ: a junk-huge declared N_tris must not spin
    // this loop past the sub-record's own bytes
    let head = (3 * n_tris).min(indices.len() as u32) as usize;
    let mut j = 0usize;
    while j + 3 <= head {
        triangles.push((indices[j] / 3, indices[j + 1] / 3, indices[j + 2] / 3));
        j += 3;
    }
    let mut cursor = head;
    for (k, &count) in counts.iter().enumerate() {
        let end_at = (cursor + count as usize).min(indices.len());
        let values = &indices[cursor..end_at];
        cursor += count as usize;
        if k < n_strips as usize {
            if values.len() >= 3 {
                for w in 0..=(values.len() - 3) {
                    triangles.push((values[w] / 3, values[w + 1] / 3, values[w + 2] / 3));
                }
            }
        } else {
            for w in 1..values.len().saturating_sub(1) {
                triangles.push((values[0] / 3, values[w] / 3, values[w + 1] / 3));
            }
        }
    }
    SubRecord {
        kind,
        n_tris,
        n_strips,
        n_fans,
        pos_rel: pos,
        rel_len,
        closed_exact: ok && pos == rel_len - 1,
        indices,
        triangles,
        flag: FLAG_COUNTER_TABLE,
    }
}

/// The CAT3DFaceGP law on one ``0x51`` sub-record — the twin's
/// :func:`catpart.geometry.face_gp._decode_face_gp` (with the raw
/// index list the strict gate reads).
///
/// ``kind/N_tris/N_strips/N_fans`` at ``+57`` (``u32le``); the stream
/// starts after the first ``ff 7f`` / ``01 80`` marker at ``>= +73``
/// (or at ``+73``); ``N_tris`` independent triangles (``u16be``), then
/// strips and fans (``count:u32be`` + ``count`` ``u16be``).  A declared
/// count larger than the remaining bytes stops the reads (the record
/// then cannot close and the gate refuses it).
fn decode_face_gp(data: &[u8], start: usize, end: usize) -> SubRecord {
    let rel_len = end.saturating_sub(start);
    if start + HEADER_AT + 16 > data.len() {
        // a pattern match whose header would run past the file:
        // structurally truncated, refused fail-closed (never observed
        // on the carriers)
        return SubRecord {
            kind: 0,
            n_tris: 0,
            n_strips: 0,
            n_fans: 0,
            pos_rel: rel_len,
            rel_len,
            closed_exact: false,
            indices: Vec::new(),
            triangles: Vec::new(),
            flag: FLAG_FACE_GP,
        };
    }
    let kind = u32_le(data, start + HEADER_AT);
    let n_tris = u32_le(data, start + HEADER_AT + 4);
    let n_strips = u32_le(data, start + HEADER_AT + 8);
    let n_fans = u32_le(data, start + HEADER_AT + 12);
    let mut marker: Option<usize> = None;
    for tag in MARKERS {
        let at = super::store::find(data, tag, start + STREAM_AT, end);
        if let Some(at) = at
            && marker.is_none_or(|best| at < best)
        {
            marker = Some(at);
        }
    }
    let mut pos = match marker {
        Some(at) => at + 2 - start,
        None => STREAM_AT,
    };
    let mut indices: Vec<u32> = Vec::new();
    let mut ok = true;
    for _ in 0..n_tris {
        if pos + 6 > rel_len {
            ok = false;
            break;
        }
        for _corner in 0..3 {
            indices.push(u16_be(data, start + pos));
            pos += 2;
        }
    }
    let mut strips: Vec<Vec<u32>> = Vec::new();
    if ok {
        for _ in 0..n_strips {
            if pos + 4 > rel_len {
                ok = false;
                break;
            }
            let count = u32_be(data, start + pos);
            pos += 4;
            let mut values: Vec<u32> = Vec::new();
            for _ in 0..count {
                if pos + 2 > rel_len {
                    ok = false;
                    break;
                }
                values.push(u16_be(data, start + pos));
                pos += 2;
            }
            strips.push(values);
            if !ok {
                break;
            }
        }
    }
    let mut fans: Vec<Vec<u32>> = Vec::new();
    if ok {
        for _ in 0..n_fans {
            if pos + 4 > rel_len {
                ok = false;
                break;
            }
            let count = u32_be(data, start + pos);
            pos += 4;
            let mut values: Vec<u32> = Vec::new();
            for _ in 0..count {
                if pos + 2 > rel_len {
                    ok = false;
                    break;
                }
                values.push(u16_be(data, start + pos));
                pos += 2;
            }
            fans.push(values);
            if !ok {
                break;
            }
        }
    }
    let mut triangles: Vec<(u32, u32, u32)> = Vec::new();
    // bound by what was READ: a junk-huge declared N_tris must not spin
    // this loop past the sub-record's own bytes
    let bound = (3 * n_tris).min(indices.len() as u32);
    let mut j = 0usize;
    while j + 3 <= bound as usize {
        triangles.push((indices[j] / 3, indices[j + 1] / 3, indices[j + 2] / 3));
        j += 3;
    }
    for values in &strips {
        if values.len() >= 3 {
            for j in 0..=(values.len() - 3) {
                triangles.push((values[j] / 3, values[j + 1] / 3, values[j + 2] / 3));
            }
        }
    }
    for values in &fans {
        for j in 1..values.len().saturating_sub(1) {
            triangles.push((values[0] / 3, values[j] / 3, values[j + 1] / 3));
        }
    }
    SubRecord {
        kind,
        n_tris,
        n_strips,
        n_fans,
        pos_rel: pos,
        rel_len,
        closed_exact: ok && pos == rel_len - 1,
        indices,
        triangles,
        flag: FLAG_FACE_GP,
    }
}

/// The strict per-sub-record gate (the approved design) — the twin's
/// :func:`catpart.geometry.face_gp._gate_sub_record`.
///
/// Byte-exact closure, the framing's kind (3 for ``0x51``, 0 for
/// ``0x50``), every raw index ``mult-3`` and in-bounds against the
/// record's declared point array, no repeated-index triangle, and
/// self-manifold (every undirected edge used at most twice).  An empty
/// read is refused (the probe's ``empty`` arm).
fn gate_sub_record(sub: &SubRecord, n_declared: u32) -> bool {
    let expected = if sub.flag == FLAG_COUNTER_TABLE {
        KIND_COUNTER_TABLE
    } else {
        KIND_FACE_GP
    };
    if !sub.closed_exact || sub.kind != expected {
        return false;
    }
    if sub.triangles.is_empty() {
        return false;
    }
    if sub.indices.iter().any(|&index| index % 3 != 0) {
        return false;
    }
    if sub
        .triangles
        .iter()
        .any(|&(a, b, c)| a >= n_declared || b >= n_declared || c >= n_declared)
    {
        return false;
    }
    if sub
        .triangles
        .iter()
        .any(|&(a, b, c)| a == b || b == c || a == c)
    {
        return false;
    }
    mesh::EdgeGuard::default().admit(&sub.triangles)
}

/// Fold the gated sub-records in order: unordered dedup + guard — the
/// twin's :func:`catpart.geometry.face_gp._assemble`.  Returns
/// ``(folded, dedup_dropped, guard_refused)``.  The dedup keys and the
/// edge histogram update only on ACCEPT — a refused member leaves no
/// trace (fail-closed, deterministic in sub-record order).
fn assemble(members: &[Vec<(u32, u32, u32)>]) -> (Vec<(u32, u32, u32)>, usize, usize) {
    let mut folded: Vec<(u32, u32, u32)> = Vec::new();
    let mut seen: HashSet<[u32; 3]> = HashSet::new();
    let mut guard = mesh::EdgeGuard::default();
    let mut dedup_dropped = 0usize;
    let mut guard_refused = 0usize;
    for tris in members {
        let mut fresh: Vec<(u32, u32, u32)> = Vec::new();
        for &tri in tris {
            let mut key = [tri.0, tri.1, tri.2];
            key.sort_unstable();
            if seen.contains(&key) {
                dedup_dropped += 1;
                continue;
            }
            fresh.push(tri);
        }
        if !guard.admit(&fresh) {
            guard_refused += 1;
            continue;
        }
        for &tri in &fresh {
            let mut key = [tri.0, tri.1, tri.2];
            key.sort_unstable();
            seen.insert(key);
        }
        folded.extend(fresh);
    }
    (folded, dedup_dropped, guard_refused)
}

/// Decode one part's ``CATSurfacicRep`` patch sub-records — the twin's
/// :func:`catpart.geometry.face_gp.scan_part`.
///
/// Walks the file-wide class-record framing's ``CATSurfacicRep`` spans
/// (the records the named containers do not frame — the CAAMai family
/// — included), pairs every span's sub-records with the span's largest
/// clean declared array (the pairing probe's law), applies the strict
/// gate per sub-record and folds the gated members per span.  Spans
/// fold independently (disjoint index spaces — one declared array
/// each) and are concatenated in file order with index offsets; the
/// mesh invariants and the assembly guard are computed per span (never
/// across spans: different arrays, no shared topology).
///
/// ``None`` when no triangle folded anywhere — the caller falls
/// through to the display route with its summary unchanged.
pub fn scan_part(data: &[u8]) -> Option<FaceGpScan> {
    let mut vertices: Vec<(f64, f64, f64)> = Vec::new();
    let mut triangles: Vec<(u32, u32, u32)> = Vec::new();
    let mut records = 0usize;
    let mut sub_records = 0usize;
    let mut gated = 0usize;
    let mut guard_refused = 0usize;
    let mut dedup_dropped = 0usize;
    let mut counter_records = 0usize;
    let mut counter_gated = 0usize;
    for (start, end, surfacic) in class_record_spans(data) {
        if !surfacic {
            continue;
        }
        let subs = subrecord_positions(data, start, end);
        if subs.is_empty() {
            continue;
        }
        sub_records += subs.len();
        counter_records += subs
            .iter()
            .filter(|&&hit| data[hit + 8] == FLAG_COUNTER_TABLE)
            .count();
        let arrays = declared_arrays(data, start, end);
        if arrays.is_empty() {
            continue;
        }
        let (_count_at, data_start, _floats, points_count) = arrays.iter().copied().fold(
            arrays[0],
            |best, item| if item.3 > best.3 { item } else { best },
        );
        let mut points: Vec<(f64, f64, f64)> = Vec::with_capacity(points_count as usize);
        for i in 0..points_count {
            points.push((
                f32_wide(data, data_start + 12 * i as usize),
                f32_wide(data, data_start + 12 * i as usize + 4),
                f32_wide(data, data_start + 12 * i as usize + 8),
            ));
        }
        let mut members: Vec<Vec<(u32, u32, u32)>> = Vec::new();
        for (j, &sub_start) in subs.iter().enumerate() {
            let sub_end = subs.get(j + 1).copied().unwrap_or(end);
            let sub = decode_sub_record(data, sub_start, sub_end);
            if gate_sub_record(&sub, points_count) {
                gated += 1;
                if sub.flag == FLAG_COUNTER_TABLE {
                    counter_gated += 1;
                }
                members.push(sub.triangles);
            }
        }
        if members.is_empty() {
            continue;
        }
        let (folded, dropped, refused) = assemble(&members);
        dedup_dropped += dropped;
        guard_refused += refused;
        if folded.is_empty() {
            continue;
        }
        records += 1;
        let offset = vertices.len() as u32;
        vertices.extend(points);
        triangles.extend(
            folded
                .iter()
                .map(|&(a, b, c)| (a + offset, b + offset, c + offset)),
        );
    }
    if triangles.is_empty() {
        return None;
    }
    Some(FaceGpScan {
        vertices,
        triangles,
        records,
        sub_records,
        sub_records_gated: gated,
        guard_refused,
        dedup_dropped,
        sub_records_counter: counter_records,
        sub_records_counter_gated: counter_gated,
    })
}

/// The route's summary warning (integer counts only — the summary is
/// compared parsed-document equal against the Python reference's) —
/// the twin's :func:`catpart.geometry.face_gp.warning_detail`.
pub fn warning_detail(scan: &FaceGpScan) -> String {
    format!(
        "no surface decoded: the CATSurfacicRep patch sub-records (30 04 04 ff ff \
         ff d2 d2 51|50) decode under their framing's law (#63): kind 3 at +57 \
         with u16be indices after the ff 7f / 01 80 marker (0x51), or kind 0 at \
         +57 with the u16be stream at +74 \u{2014} 3*N_tris values, then a u16be \
         count table (one per strip, then one per fan), then the concatenated \
         values (0x50); v = idx // 3 into the record's declared f32 point array \
         (one word after its count); {} gated sub-record(s) of {} folded into a \
         manifold mesh across {} patch stream(s), guard refused {}, duplicate \
         unordered triangles dropped {}; source {SOURCE}. Every gated sub-record \
         closes byte-exact (end == sub_len - 1) with mult-3 in-bounds indices \
         and no repeated-index triangle; zero-area slivers from the writer's \
         duplicate pinned coordinates ride as decoded (no skip convention \
         fired, degenerate count 0). docs/evidence/2026-11-21-bagrep-face-gp.md, \
         docs/evidence/2026-11-22-face-gp-counter-table.md",
        scan.sub_records_gated,
        scan.sub_records,
        scan.records,
        scan.guard_refused,
        scan.dedup_dropped,
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::geometry::mesh;

    /// One ``0x51`` sub-record's bytes: pattern + flag + padding + the
    /// ``+57`` header + (the marker) + the u16be stream + the dangling
    /// byte (the twin's ``tests.test_face_gp.sub_record`` helper).
    fn sub_record_bytes(
        tris: &[(u32, u32, u32)],
        strips: &[&[u32]],
        fans: &[&[u32]],
        kind: u32,
        marker: bool,
        dangling: bool,
    ) -> Vec<u8> {
        let mut body = Vec::new();
        if marker {
            body.extend_from_slice(b"\xff\x7f");
        }
        for &(v0, v1, v2) in tris {
            for vertex in [v0 * 3, v1 * 3, v2 * 3] {
                body.extend_from_slice(&(vertex as u16).to_be_bytes());
            }
        }
        for values in strips.iter().chain(fans.iter()) {
            body.extend_from_slice(&(values.len() as u32).to_be_bytes());
            for &value in *values {
                body.extend_from_slice(&(value as u16).to_be_bytes());
            }
        }
        let mut out = Vec::new();
        out.extend_from_slice(SUBREC);
        out.push(FLAG_FACE_GP);
        out.extend(std::iter::repeat(0x11).take(HEADER_AT - 9));
        out.extend_from_slice(&kind.to_le_bytes());
        out.extend_from_slice(&(tris.len() as u32).to_le_bytes());
        out.extend_from_slice(&(strips.len() as u32).to_le_bytes());
        out.extend_from_slice(&(fans.len() as u32).to_le_bytes());
        out.extend_from_slice(&body);
        if dangling {
            out.push(0x00);
        }
        out
    }

    fn twelve_points() -> Vec<(f64, f64, f64)> {
        (0..12)
            .map(|i| (10.0 * i as f64, 5.0 * (i % 3) as f64, 2.0 + i as f64))
            .collect()
    }

    /// A count-first declared array: ``u32le`` float count, ONE
    /// non-coordinate word, ``f32le`` triples (the measured layout).
    fn declared_array_bytes(points: &[(f64, f64, f64)]) -> Vec<u8> {
        let mut out = Vec::new();
        out.extend_from_slice(&((points.len() * 3) as u32).to_le_bytes());
        out.extend_from_slice(&1u32.to_le_bytes());
        for &(x, y, z) in points {
            out.extend_from_slice(&(x as f32).to_le_bytes());
            out.extend_from_slice(&(y as f32).to_le_bytes());
            out.extend_from_slice(&(z as f32).to_le_bytes());
        }
        out
    }

    /// A ``CATSurfacicRep`` class record: framing + array + sub-records,
    /// closed by a following record framing.
    fn span_bytes(points: &[(f64, f64, f64)], subs: &[Vec<u8>]) -> Vec<u8> {
        let mut out = Vec::new();
        out.extend_from_slice(&14u32.to_le_bytes());
        out.extend_from_slice(b"CATSurfacicRep");
        out.extend_from_slice(&declared_array_bytes(points));
        for sub in subs {
            out.extend_from_slice(sub);
        }
        out.extend_from_slice(&11u32.to_le_bytes());
        out.extend_from_slice(b"CAT3DBagRep");
        out
    }

    #[test]
    fn the_class_record_framing_spans_both_names() {
        let mut body = Vec::new();
        body.extend_from_slice(&11u32.to_le_bytes());
        body.extend_from_slice(b"CAT3DBagRep");
        // span_bytes opens with the u32le(14) + "CATSurfacicRep" framing
        body.extend_from_slice(&span_bytes(&twelve_points(), &[]));
        let spans = class_record_spans(&body);
        // bagrep (the opener), the surfacic record, bagrep (the closer)
        assert_eq!(spans.len(), 3);
        assert!(!spans[0].2);
        assert!(spans[1].2);
        assert!(!spans[2].2);
    }

    #[test]
    fn the_declared_array_starts_one_word_after_the_count() {
        let points = twelve_points();
        let body = span_bytes(
            &points,
            &[sub_record_bytes(
                &[(0, 1, 2), (2, 3, 4)],
                &[],
                &[],
                3,
                true,
                true,
            )],
        );
        let start = super::super::store::find(&body, b"CATSurfacicRep", 0, body.len())
            .expect("the framing names the record")
            - 4;
        let arrays = declared_arrays(&body, start, body.len());
        assert_eq!(arrays.len(), 1);
        let (_offset, data_start, floats, points_count) = arrays[0];
        assert_eq!((floats, points_count), (36, 12));
        assert_eq!(
            (
                f32_wide(&body, data_start),
                f32_wide(&body, data_start + 4),
                f32_wide(&body, data_start + 8)
            ),
            (0.0, 0.0, 2.0),
        );
    }

    #[test]
    fn the_array_envelope_refuses_junk() {
        // a denormal cloud (the corpus's junk arrays)
        let junk: Vec<(f64, f64, f64)> = (0..12)
            .map(|i| (1e-40 * i as f64, 2e-40 * i as f64, 3e-40 * i as f64))
            .collect();
        let body = span_bytes(
            &junk,
            &[sub_record_bytes(
                &[(0, 1, 2), (2, 3, 4)],
                &[],
                &[],
                3,
                true,
                true,
            )],
        );
        assert!(scan_part(&body).is_none());
        // a part-scale overshoot
        let huge: Vec<(f64, f64, f64)> = (0..12).map(|i| (1e6 + i as f64, 0.0, 0.0)).collect();
        let body = span_bytes(
            &huge,
            &[sub_record_bytes(
                &[(0, 1, 2), (2, 3, 4)],
                &[],
                &[],
                3,
                true,
                true,
            )],
        );
        assert!(scan_part(&body).is_none());
    }

    #[test]
    fn the_decode_reads_triangles_strips_and_fans() {
        let built = sub_record_bytes(
            &[(0, 1, 2)],
            &[&[0, 3, 6, 9]],
            &[&[0, 6, 9, 12]],
            3,
            true,
            true,
        );
        let decoded = decode_sub_record(&built, 0, built.len());
        assert_eq!(decoded.kind, 3);
        assert_eq!(
            (decoded.n_tris, decoded.n_strips, decoded.n_fans),
            (1, 1, 1)
        );
        assert!(decoded.closed_exact);
        assert_eq!(decoded.pos_rel, STREAM_AT + 2 + 6 + (4 + 8) + (4 + 8));
        assert_eq!(
            decoded.triangles,
            vec![(0, 1, 2), (0, 1, 2), (1, 2, 3), (0, 2, 3), (0, 3, 4)],
        );
    }

    #[test]
    fn the_closure_is_byte_exact() {
        let exact = sub_record_bytes(&[(0, 1, 2), (2, 3, 4)], &[], &[], 3, true, true);
        assert!(decode_sub_record(&exact, 0, exact.len()).closed_exact);
        let mut open_ended = exact.clone();
        open_ended.push(0x00);
        assert!(!decode_sub_record(&open_ended, 0, open_ended.len()).closed_exact);
        // a declared N_tris larger than the stream stops the reads
        let mut fat = Vec::new();
        fat.extend_from_slice(SUBREC);
        fat.push(FLAG_FACE_GP);
        fat.extend(std::iter::repeat(0x11).take(HEADER_AT - 9));
        fat.extend_from_slice(&3u32.to_le_bytes());
        fat.extend_from_slice(&9u32.to_le_bytes());
        fat.extend_from_slice(&0u32.to_le_bytes());
        fat.extend_from_slice(&0u32.to_le_bytes());
        fat.extend_from_slice(b"\xff\x7f");
        fat.extend_from_slice(&0u16.to_be_bytes());
        fat.extend_from_slice(&3u16.to_be_bytes());
        fat.extend_from_slice(&6u16.to_be_bytes());
        fat.push(0x00);
        assert!(!decode_sub_record(&fat, 0, fat.len()).closed_exact);
    }

    #[test]
    fn the_strict_gate_axes() {
        let n = 12u32;
        let built = sub_record_bytes(&[(0, 1, 2), (2, 3, 4)], &[], &[], 3, true, true);
        let good = decode_sub_record(&built, 0, built.len());
        assert!(gate_sub_record(&good, n));
        // not the face-GP kind
        let built = sub_record_bytes(&[(0, 1, 2), (2, 3, 4)], &[], &[], 2, true, true);
        assert!(!gate_sub_record(
            &decode_sub_record(&built, 0, built.len()),
            n
        ));
        // a repeated-index triangle
        let built = sub_record_bytes(&[(1, 1, 4)], &[], &[], 3, true, true);
        assert!(!gate_sub_record(
            &decode_sub_record(&built, 0, built.len()),
            n
        ));
        // an index beyond the declared array
        let built = sub_record_bytes(&[(0, 1, 20)], &[], &[], 3, true, true);
        assert!(!gate_sub_record(
            &decode_sub_record(&built, 0, built.len()),
            n
        ));
        // an over-using edge
        let built = sub_record_bytes(&[(0, 1, 2), (2, 0, 3), (0, 2, 4)], &[], &[], 3, true, true);
        assert!(!gate_sub_record(
            &decode_sub_record(&built, 0, built.len()),
            n
        ));
    }

    #[test]
    fn the_assembly_dedup_keeps_the_first_winding() {
        let first = vec![(0u32, 1, 2), (2, 3, 4)];
        let second = vec![(2u32, 1, 0), (2, 3, 4)];
        let (folded, dropped, refused) = assemble(&[first, second]);
        assert_eq!((dropped, refused), (2, 0));
        assert_eq!(folded, vec![(0, 1, 2), (2, 3, 4)]);
    }

    #[test]
    fn the_assembly_guard_refuses_whole_members() {
        let first = vec![(0u32, 1, 2), (2, 3, 0), (0, 3, 5)];
        let second = vec![(0u32, 3, 4)];
        let (folded, dropped, refused) = assemble(&[first.clone(), second]);
        assert_eq!((&folded, dropped, refused), (&first, 0, 1));
        assert!(mesh::mesh_stats(&folded).manifold);
    }

    #[test]
    fn the_scan_folds_the_span_and_offsets_the_second() {
        let points_b: Vec<(f64, f64, f64)> = (0..12)
            .map(|i| (100.0 + i as f64, 1.0 * i as f64, 2.0))
            .collect();
        let mut body = Vec::new();
        body.extend_from_slice(&14u32.to_le_bytes());
        body.extend_from_slice(b"CATSurfacicRep");
        body.extend_from_slice(&declared_array_bytes(&twelve_points()));
        body.extend_from_slice(&sub_record_bytes(
            &[(0, 1, 2), (2, 3, 4)],
            &[],
            &[],
            3,
            true,
            true,
        ));
        body.extend_from_slice(&14u32.to_le_bytes());
        body.extend_from_slice(b"CATSurfacicRep");
        body.extend_from_slice(&declared_array_bytes(&points_b));
        body.extend_from_slice(&sub_record_bytes(&[(0, 1, 2)], &[], &[], 3, true, true));
        body.extend_from_slice(&11u32.to_le_bytes());
        body.extend_from_slice(b"CAT3DBagRep");
        let scan = scan_part(&body).expect("two gated spans fold");
        assert_eq!(scan.records, 2);
        assert_eq!(scan.triangles, vec![(0, 1, 2), (2, 3, 4), (12, 13, 14)]);
        assert_eq!(scan.vertices.len(), 24);
        assert_eq!(scan.vertices[0], twelve_points()[0]);
        assert_eq!(scan.vertices[12], points_b[0]);
    }

    #[test]
    fn a_truncated_pattern_refuses_fail_closed() {
        let mut body = span_bytes(
            &twelve_points(),
            &[sub_record_bytes(&[(0, 1, 2)], &[], &[], 3, true, true)],
        );
        body.truncate(body.len() - 40);
        assert!(scan_part(&body).is_none());
    }

    /// One ``0x50`` counter-table sub-record's bytes: pattern + flag +
    /// padding + the ``+57`` header (kind 0) + the pad word + the
    /// ``u16be`` stream at ``+74`` (``3 * N_tris`` values, the count
    /// table, the concatenated values) + the dangling byte (the twin's
    /// ``tests.test_face_gp.counter_table_record`` helper).
    fn counter_table_bytes(
        tris: &[(u32, u32, u32)],
        strips: &[&[u32]],
        fans: &[&[u32]],
        dangling: bool,
    ) -> Vec<u8> {
        let mut stream = Vec::new();
        for &(v0, v1, v2) in tris {
            for vertex in [v0 * 3, v1 * 3, v2 * 3] {
                stream.extend_from_slice(&(vertex as u16).to_be_bytes());
            }
        }
        for values in strips.iter().chain(fans.iter()) {
            stream.extend_from_slice(&(values.len() as u16).to_be_bytes());
        }
        for values in strips.iter().chain(fans.iter()) {
            for &value in *values {
                stream.extend_from_slice(&(value as u16).to_be_bytes());
            }
        }
        let mut out = Vec::new();
        out.extend_from_slice(SUBREC);
        out.push(FLAG_COUNTER_TABLE);
        out.extend(std::iter::repeat(0x11).take(HEADER_AT - 9));
        out.extend_from_slice(&KIND_COUNTER_TABLE.to_le_bytes());
        out.extend_from_slice(&(tris.len() as u32).to_le_bytes());
        out.extend_from_slice(&(strips.len() as u32).to_le_bytes());
        out.extend_from_slice(&(fans.len() as u32).to_le_bytes());
        out.extend(std::iter::repeat(0x00).take(COUNTER_TABLE_AT - HEADER_AT - 16));
        out.extend_from_slice(&stream);
        if dangling {
            out.push(0x00);
        }
        out
    }

    #[test]
    fn the_counter_table_law_reads_triangles_and_the_count_table() {
        // one independent triangle, one strip declared by the table
        // (4 values -> 2 windows), one fan (4 values -> 2 triangles):
        // the same mult-3 encoding, kind 0
        let built = counter_table_bytes(&[(0, 1, 2)], &[&[0, 3, 6, 9]], &[&[0, 6, 9, 12]], true);
        let decoded = decode_sub_record(&built, 0, built.len());
        assert_eq!(decoded.flag, FLAG_COUNTER_TABLE);
        assert_eq!(decoded.kind, KIND_COUNTER_TABLE);
        assert_eq!(
            (decoded.n_tris, decoded.n_strips, decoded.n_fans),
            (1, 1, 1)
        );
        assert!(decoded.closed_exact);
        assert_eq!(decoded.pos_rel, built.len() - 1);
        assert_eq!(
            decoded.triangles,
            vec![
                (0, 1, 2), // the independent triangle
                (0, 1, 2), // the strip's first window (values 0, 3, 6)
                (1, 2, 3), // the strip's second window (values 3, 6, 9)
                (0, 2, 3), // the fan's first triangle (fan head 0; 6, 9)
                (0, 3, 4), // the fan's second triangle (fan head 0; 9, 12)
            ]
        );
    }

    #[test]
    fn the_counter_table_gate_is_the_strict_gate_at_kind_0() {
        let points = twelve_points();
        let n = points.len() as u32;
        let built = counter_table_bytes(&[(0, 1, 2), (2, 3, 4)], &[], &[], true);
        let good = decode_sub_record(&built, 0, built.len());
        assert!(gate_sub_record(&good, n));

        // a kind other than the framing's kind refuses
        let mut wrong_kind = built.clone();
        let kind_at = wrong_kind
            .windows(4)
            .position(|w| w == KIND_COUNTER_TABLE.to_le_bytes())
            .expect("the header carries the kind word");
        wrong_kind[kind_at..kind_at + 4].copy_from_slice(&3u32.to_le_bytes());
        let sub = decode_sub_record(&wrong_kind, 0, wrong_kind.len());
        assert!(!gate_sub_record(&sub, n));

        // an out-of-bounds index refuses
        let oob = counter_table_bytes(&[(0, 1, 20)], &[], &[], true);
        let sub = decode_sub_record(&oob, 0, oob.len());
        assert!(!gate_sub_record(&sub, n));

        // two dangling bytes: not byte-exact, refused
        let loose = counter_table_bytes(&[(0, 1, 2)], &[], &[], true);
        let mut two = loose.clone();
        two.push(0x00);
        let sub = decode_sub_record(&two, 0, two.len());
        assert!(!sub.closed_exact);
        assert!(!gate_sub_record(&sub, n));
    }

    #[test]
    fn the_counter_table_folds_into_the_span_scan() {
        let points = twelve_points();
        let body = span_bytes(
            &points,
            &[
                counter_table_bytes(&[(0, 1, 2)], &[&[6, 9, 12, 15]], &[], true),
                sub_record_bytes(&[(0, 1, 2), (2, 3, 4)], &[], &[], 3, true, true),
            ],
        );
        let scan = scan_part(&body).expect("both framings fold");
        assert_eq!(scan.records, 1);
        assert_eq!(scan.sub_records, 2);
        assert_eq!(scan.sub_records_gated, 2);
        assert_eq!(scan.sub_records_counter, 1);
        assert_eq!(scan.sub_records_counter_gated, 1);
        // counter-table member first ((0,1,2) + strip windows (2,3,4),
        // (3,4,5)); the face-GP member's two triangles re-list both
        // sorted keys, so the dedup drops them (first copy wins)
        assert_eq!(scan.triangles, vec![(0, 1, 2), (2, 3, 4), (3, 4, 5)]);
        assert_eq!(scan.dedup_dropped, 2);
    }

    #[test]
    fn an_interleaved_counter_table_ends_the_face_gp_record() {
        // the writer emits 0x50/0x51 interleaved: the 0x51 record's
        // extent ends at the 0x50 that follows it, so the scan must not
        // run it past its neighbor (that span could not close)
        let points = twelve_points();
        let body = span_bytes(
            &points,
            &[
                sub_record_bytes(&[(0, 1, 2), (2, 3, 4)], &[], &[], 3, true, true),
                counter_table_bytes(&[], &[&[9, 12, 15]], &[], true),
            ],
        );
        let scan = scan_part(&body).expect("both members fold");
        assert_eq!(scan.sub_records, 2);
        assert_eq!(scan.sub_records_gated, 2);
        assert_eq!(scan.triangles, vec![(0, 1, 2), (2, 3, 4), (3, 4, 5)]);
    }
}
