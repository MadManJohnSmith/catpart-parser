"""The ``CATSurfacicRep`` patch sub-record stream — the CAT3DFaceGP law (#63).

The bag-rep family's remaining geometry carrier (issue #63, part of the
#50 L2 residuals): inside a ``CATSurfacicRep`` class record, the byte
pattern ``30 04 04 ff ff ff d2 d2`` + flag opens a sub-record stream,
and the ``0x51`` sub-records carry a patch mesh under the CAT3DFaceGP
law — the micro-probe measurement of 2026-11-20 (issue #63 comment 3,
``scripts/triage/probe_t63_face_gp.py``) plus the pairing refinement
(``probe_t63_pairing.py``), verified byte-exact on the anchors (the
40/604 exact closures: CAAMai N_tris 150/142/8, Plate N_tris=30 @+61 =
the 90-value ``3*vertex_id`` run, CAAPstPad1_1, CAAPstFunnel, Pad,
CAASamplePart, Screw, CAAPstHull):

- the class records frame the scan file-wide (a ``u32le`` length prefix
  followed by the ``CAT3DBagRep`` / ``CATSurfacicRep`` name — the
  probe's boundary law, both names, so a span ends at the next record
  of either kind; the route walks the ``CATSurfacicRep`` spans, where
  every measured carrier's sub-records live), covering the records
  that sit outside the named containers (the CAAMaiUserToolDatabase
  family);
- the record's **declared f32 point array** is its index space: a
  count-first ``u32le`` count (``9 <= count <= 3_000_000``,
  ``count % 3 == 0``) whose floats start **one word after the count**
  (the writer emits a non-coordinate word between count and data —
  measured on every clean array: Plate/Screw/CAAPstPad1_1 118/76/118
  points, CAAMai 286, CAKhw 187/417; at the count-adjacent start every
  array leads with a denormal non-coordinate word);
- the array gate is the count-first measurement's candidate filter
  (finite head, ``|w| < 1e9``, non-zero share >= 1/2, no constant run
  over 64 words) plus the FULL-array coordinate envelope: every word
  finite, part-scale (``|w| <= COORD_CEIL``, the display envelope's
  ceiling), and not denormal junk (``w == 0`` or ``|w| >= 1e-30`` —
  the junk arrays the corpus measurement refused are denormal clouds
  and non-finite tails; the real arrays' sub-floor values are rounding
  artifacts at 5.7e-14/7.3e-15, two-plus orders above the denormal
  range);
- the ``0x51`` sub-record (``0x50`` carries a different counter
  framing, ``0x00`` is a boundary artifact — both ignored) decodes:
  ``kind, N_tris, N_strips, N_fans`` as ``4 x u32le`` at ``+57`` (kind
  3 = the face GP), then after the FIRST ``ff 7f`` / ``01 80`` marker
  at ``>= +73`` (the stream starts at ``+73`` when neither appears):
  ``N_tris`` independent triangles (``3 * N_tris`` ``u16be`` indices),
  then ``N_strips`` strips and ``N_fans`` fans (each ``count:u32be`` +
  ``count`` ``u16be`` indices, strips through their sliding window,
  fans fanned from their first vertex).  The ``u16be`` framing is the
  measured one (the t7 ``u16le``/stride-3 reading is the parity
  artifact comment: at the marker-anchored offsets the values read
  ``u16be``);
- the STRICT per-sub-record gate (the approved design): the stream
  closes byte-exact (``pos == rel_len - 1`` — the trailing dangling
  byte), every index is ``mult-3`` and in-bounds (``v = idx // 3 <
  N_declared``), no triangle repeats a vertex index (the degenerate
  reading of the pairing probe's manifold verdict — repeated-index
  triangles are refused whole) and the sub-record is self-manifold
  (every undirected edge used at most twice — boundary edges are
  legitimate open shells, G3 F6);
- the assembly folds the gated sub-records IN ORDER per record with
  the unordered-triangle dedup (first copy wins) and the incremental
  :meth:`catpart.geometry.composite._mesh_safe` guard — a candidate
  that would push any undirected edge past two uses is refused whole,
  histogram and dedup keys untouched (fail-closed, deterministic in
  sub-record order).  This is what lets the anchor records close
  complete (Plate 64 triangles = 30+30+2+2, CAAMaiUserToolDatabase
  154 = 150+2+2) while ``CAAKhw*``/``Pad`` emit their manifold subset
  of the gated sub-records without over-use.

Zero-area triangles with DISTINCT indices (the writer's duplicate
pinned coordinates — the dup-point territory the dup-pin law already
names) ride as decoded: no skip convention fires and the summary's
degenerate count stays 0; the route's warning says so explicitly.

The route sits in the export fallback chain AFTER the facet stores,
the ``a5 03 34`` B-spline surfaces and the structured E5 grids and
BEFORE the point-only display fallback (export.py): a part whose
gated sub-records fold into a non-empty manifold mesh exports it
(source label :data:`SOURCE`, summary block ``bagrep_face_gp``); a
part with no gated sub-records, no clean array or no folded triangles
falls through to the display carriers with its summary unchanged.

Fail-closed rules: a span without a clean array contributes nothing;
a sub-record failing any strict-gate test contributes nothing and is
counted; a member the assembly guard refuses leaves the histogram
untouched; a part with no folded triangle at all never reaches this
route's summary (the display fallback runs unchanged).

The numerical contract matches the export's: the only arithmetic is
exact ``f32 -> f64`` widening at load (coordinates are written back
``f32`` unchanged — the PLY round-trip is exact), and the area-free
gates (mult-3, bounds, edge uses) are integer-exact, so the Rust twin
decides every branch identically.
"""

from __future__ import annotations

import dataclasses
import math
import struct

from catpart.geometry import grid
from catpart.geometry import mesh

#: The route's source label (the summary block and the warning detail).
SOURCE = "bagrep-face-gp"

#: The 8-byte pattern + the ``0x51`` face-GP flag (``0x50`` = different
#: counter framing, ``0x00`` = boundary artifact: both ignored).
SUBREC = b"\x30\x04\x04\xff\xff\xff\xd2\xd2"
FLAG_FACE_GP = 0x51
#: The kind/counts header sits at ``+57..+72``; the stream starts after
#: the first marker at ``>= +73`` (or at ``+73`` when neither appears).
HEADER_AT = 57
STREAM_AT = 73
MARKERS = (b"\xff\x7f", b"\x01\x80")
#: kind 3 = the CAT3DFaceGP primitive (the approved design's header law).
KIND_FACE_GP = 3
#: Count-first framing bounds (the bag-rep measurement's).
MAX_FLOATS = 3_000_000
#: The candidate filter's bounded head (the probe's pool-scale bound).
HEAD_WORDS = 96
HEAD_ABS_MAX = 1e9
#: The head gate's clean-share and fill-run bounds (the probe's).
HEAD_MIN_NONZERO = 0.5
HEAD_MAX_CONST_RUN = 64
#: The full-array coordinate envelope: part-scale, no denormal junk.
#: The corpus's junk arrays are denormal clouds (1e-38..1e-45) and
#: non-finite tails; the real arrays' sub-floor values are rounding
#: artifacts at 5.7e-14 / 7.3e-15.  ``grid.COORD_CEIL`` = 1e5 is the
#: display envelope's ceiling.
DENORMAL_MAX = 1e-30
#: The class-record framing: a ``u32le`` length prefix followed by the
#: record name, file-wide (the probe's boundary law, BOTH names — a
#: span ends at the next record of either kind).  The route walks the
#: ``CATSurfacicRep`` spans.
CLASS_RECORDS = ((b"CAT3DBagRep", 11), (b"CATSurfacicRep", 14))

_U32 = struct.Struct("<I")
_HEADER = struct.Struct("<4I")
_U16BE = struct.Struct(">H")
_U32BE = struct.Struct(">I")
_F3 = struct.Struct("<3f")


@dataclasses.dataclass(frozen=True)
class SubRecord:
    """One ``0x51`` sub-record's decode under the CAT3DFaceGP law."""

    kind: int
    n_tris: int
    n_strips: int
    n_fans: int
    pos_rel: int  # the stream position after the law's reads
    rel_len: int
    closed_exact: bool  # pos == rel_len - 1 (the trailing dangling byte)
    indices: tuple[int, ...]  # the raw u16be reads (mult-3 gate input)
    triangles: tuple[tuple[int, int, int], ...]  # v = idx // 3


@dataclasses.dataclass(frozen=True)
class FaceGpScan:
    """One part's face-gp decode: the folded patch meshes.

    ``vertices`` are the records' declared point arrays concatenated in
    span order (exact f32 widenings); ``triangles`` the folded, gated
    sub-record triangles with per-span index offsets.  The counters
    feed the summary's ``bagrep_face_gp`` block.
    """

    vertices: tuple[tuple[float, float, float], ...]
    triangles: tuple[tuple[int, int, int], ...]
    records: int  # spans that emitted triangles (patch streams)
    sub_records: int  # every 0x51 sub-record in the CATSurfacicRep spans
    sub_records_gated: int  # strict-gate passes
    guard_refused: int  # assembly refusals (the incremental guard)
    dedup_dropped: int  # unordered duplicate triangles dropped


def _class_record_spans(data) -> list[tuple[int, int, str]]:
    """The bag-rep class records' ``(start, end, name)``, file-wide.

    A record opens at the ``u32le`` length prefix preceding its name
    (``CAT3DBagRep`` = 11, ``CATSurfacicRep`` = 14 — the probe's
    framing) and ends at the next record of either kind (or the file
    end), so the last sub-record's extent reaches the true boundary.
    """
    found: list[tuple[int, str]] = []
    for name, length in CLASS_RECORDS:
        pos = 0
        while True:
            pos = data.find(name, pos)
            if pos < 0:
                break
            if pos >= 4 and _U32.unpack_from(data, pos - 4)[0] == length:
                found.append((pos - 4, name.decode()))
            pos += 1
    found.sort()
    out: list[tuple[int, int, str]] = []
    for i, (start, name) in enumerate(found):
        end = found[i + 1][0] if i + 1 < len(found) else len(data)
        out.append((start, end, name))
    return out


def _subrecord_positions(data, lo: int, hi: int) -> list[int]:
    """The ``0x51`` sub-record openings in ``[lo, hi)``, in order."""
    out: list[int] = []
    pos = lo
    while True:
        hit = data.find(SUBREC, pos, hi)
        if hit < 0:
            return out
        if data[hit + 8] == FLAG_FACE_GP:
            out.append(hit)
        pos = hit + 1


def _head_gate(head) -> bool:
    """The count-first measurement's candidate filter (the probe's).

    Finite head words under the absolute bound, a non-zero share of at
    least half, and no constant run over :data:`HEAD_MAX_CONST_RUN` —
    a fill artifact cannot pass, a real tessellation array always does
    on its head.
    """
    nonzero = 0
    previous = None
    run = 1
    longest = 1
    for value in head:
        if not (value == value and abs(value) < HEAD_ABS_MAX):
            return False
        if value != 0.0:
            nonzero += 1
        if previous is not None and value == previous:
            run += 1
            if run > longest:
                longest = run
        else:
            run = 1
        previous = value
    return nonzero >= HEAD_MIN_NONZERO * len(head) and longest <= HEAD_MAX_CONST_RUN


def _word_ok(value: float) -> bool:
    """The full-array coordinate envelope (the shipped array gate).

    Finite, part-scale (the display envelope's ceiling), and not
    denormal junk: exactly zero or at least :data:`DENORMAL_MAX`.
    """
    return math.isfinite(value) and abs(value) <= grid.COORD_CEIL and (
        value == 0.0 or abs(value) >= DENORMAL_MAX
    )


def _declared_arrays(data, lo: int, hi: int) -> list[tuple[int, int, int, int]]:
    """The clean declared f32 arrays in ``[lo, hi)`` as ``(count_at,
    data_start, floats, points)``.

    Count-first framing with the data start ONE WORD AFTER the count
    (the measured writer layout), the bounded head as the candidate
    filter, and the full-array envelope as the acceptance gate.
    Arrays contained in a longer one are dropped (the probe's
    containment law; ties sort by start, longer first).
    """
    found: list[tuple[int, int, int, int]] = []
    seen: set[tuple[int, int]] = set()
    view = memoryview(data)
    for offset in range(lo, max(lo, hi - 4)):
        if data[offset + 3]:
            continue
        count = _U32.unpack_from(data, offset)[0]
        if count < 9 or count > MAX_FLOATS or count % 3:
            continue
        start = offset + 8
        if start + 4 * count > hi:
            continue
        if (start, count) in seen:
            continue
        seen.add((start, count))
        words = view[start : start + 4 * count].cast("f")
        if not _head_gate(words[:HEAD_WORDS]):
            continue
        if not all(_word_ok(word) for word in words):
            continue
        found.append((offset, start, count, count // 3))
    found.sort(key=lambda item: (item[1], -item[2]))
    keep: list[tuple[int, int, int, int]] = []
    for item in found:
        if any(
            kept[1] <= item[1] and kept[1] + 4 * kept[2] >= item[1] + 4 * item[2]
            for kept in keep
        ):
            continue
        keep.append(item)
    return keep


def decode_sub_record(data, start: int, end: int) -> SubRecord:
    """The CAT3DFaceGP law on one ``0x51`` sub-record (the probe's,
    with the raw index list the strict gate reads).

    ``kind/N_tris/N_strips/N_fans`` at ``+57`` (``u32le``); the stream
    starts after the first ``ff 7f`` / ``01 80`` marker at ``>= +73``
    (or at ``+73``); ``N_tris`` independent triangles (``u16be``), then
    strips and fans (``count:u32be`` + ``count`` ``u16be``).  A declared
    count larger than the remaining bytes stops the reads (the record
    then cannot close and the gate refuses it).
    """
    rel_len = end - start
    if start + HEADER_AT + 16 > len(data):
        # a pattern match whose header would run past the file: structurally
        # truncated, refused fail-closed (never observed on the carriers)
        return SubRecord(
            kind=0, n_tris=0, n_strips=0, n_fans=0, pos_rel=rel_len,
            rel_len=rel_len, closed_exact=False, indices=(), triangles=(),
        )
    kind, n_tris, n_strips, n_fans = _HEADER.unpack_from(data, start + HEADER_AT)
    marker = -1
    for tag in MARKERS:
        at = data.find(tag, start + STREAM_AT, end)
        if at >= 0 and (marker < 0 or at < marker):
            marker = at
    pos = (marker + 2 - start) if marker >= 0 else STREAM_AT
    indices: list[int] = []
    ok = True
    for _ in range(n_tris):
        if pos + 6 > rel_len:
            ok = False
            break
        for _corner in range(3):
            indices.append(_U16BE.unpack_from(data, start + pos)[0])
            pos += 2
    strips: list[list[int]] = []
    for _ in range(n_strips if ok else 0):
        if pos + 4 > rel_len:
            ok = False
            break
        count = _U32BE.unpack_from(data, start + pos)[0]
        pos += 4
        values: list[int] = []
        for _ in range(count):
            if pos + 2 > rel_len:
                ok = False
                break
            values.append(_U16BE.unpack_from(data, start + pos)[0])
            pos += 2
        strips.append(values)
        if not ok:
            break
    fans: list[list[int]] = []
    for _ in range(n_fans if ok else 0):
        if pos + 4 > rel_len:
            ok = False
            break
        count = _U32BE.unpack_from(data, start + pos)[0]
        pos += 4
        values = []
        for _ in range(count):
            if pos + 2 > rel_len:
                ok = False
                break
            values.append(_U16BE.unpack_from(data, start + pos)[0])
            pos += 2
        fans.append(values)
        if not ok:
            break
    triangles: list[tuple[int, int, int]] = []
    # bound by what was READ: a junk-huge declared N_tris must not spin
    # this loop past the sub-record's own bytes
    for j in range(0, min(3 * n_tris, len(indices)) - 2, 3):
        triangles.append(
            (indices[j] // 3, indices[j + 1] // 3, indices[j + 2] // 3)
        )
    for values in strips:
        for j in range(len(values) - 2):
            triangles.append(
                (values[j] // 3, values[j + 1] // 3, values[j + 2] // 3)
            )
    for values in fans:
        for j in range(1, len(values) - 1):
            triangles.append(
                (values[0] // 3, values[j] // 3, values[j + 1] // 3)
            )
    return SubRecord(
        kind=kind,
        n_tris=n_tris,
        n_strips=n_strips,
        n_fans=n_fans,
        pos_rel=pos,
        rel_len=rel_len,
        closed_exact=ok and pos == rel_len - 1,
        indices=tuple(indices),
        triangles=tuple(triangles),
    )


def _gate_sub_record(sub: SubRecord, n_declared: int) -> bool:
    """The strict per-sub-record gate (the approved design).

    Byte-exact closure, kind 3, every raw index ``mult-3`` and in-bounds
    against the record's declared point array, no repeated-index
    triangle, and self-manifold (every undirected edge used at most
    twice).  An empty read is refused (the probe's ``empty`` arm).
    """
    if not sub.closed_exact or sub.kind != KIND_FACE_GP:
        return False
    if not sub.triangles:
        return False
    if any(index % 3 for index in sub.indices):
        return False
    if any(
        not 0 <= vertex < n_declared for tri in sub.triangles for vertex in tri
    ):
        return False
    if any(
        tri[0] == tri[1] or tri[1] == tri[2] or tri[0] == tri[2]
        for tri in sub.triangles
    ):
        return False
    return mesh.EdgeGuard().admit(sub.triangles)


def _assemble(members) -> tuple[list, int, int]:
    """Fold the gated sub-records in order: unordered dedup + guard.

    Returns ``(folded, dedup_dropped, guard_refused)``.  The dedup keys
    and the edge histogram update only on ACCEPT — a refused member
    leaves no trace (fail-closed, deterministic in sub-record order).
    The guard is the composite lever's ONE topology lever
    (:meth:`catpart.geometry.mesh.EdgeGuard.admit`).
    """
    folded: list[tuple[int, int, int]] = []
    seen: set[tuple[int, int, int]] = set()
    guard = mesh.EdgeGuard()
    dedup_dropped = 0
    guard_refused = 0
    for tris in members:
        fresh = []
        for tri in tris:
            key = tuple(sorted(tri))
            if key in seen:
                dedup_dropped += 1
                continue
            fresh.append(tri)
        if not guard.admit(fresh):
            guard_refused += 1
            continue
        seen.update(tuple(sorted(tri)) for tri in fresh)
        folded.extend(fresh)
    return folded, dedup_dropped, guard_refused


def scan_part(data) -> FaceGpScan | None:
    """Decode one part's ``CATSurfacicRep`` patch sub-records.

    Walks the file-wide class-record framing's ``CATSurfacicRep`` spans
    (the records the named containers do not frame — the CAAMai
    family — included), pairs every span's sub-records with the span's
    largest clean declared array (the pairing probe's law), applies the
    strict gate per sub-record and folds the gated members per span.
    Spans fold independently (disjoint index spaces — one declared
    array each) and are concatenated in file order with index offsets;
    the mesh invariants and the assembly guard are computed per span
    (never across spans: different arrays, no shared topology).

    ``None`` when no triangle folded anywhere — the caller falls
    through to the display route with its summary unchanged.
    """
    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    records = 0
    sub_records = 0
    gated = 0
    guard_refused = 0
    dedup_dropped = 0
    for start, end, name in _class_record_spans(data):
        if name != "CATSurfacicRep":
            continue
        subs = _subrecord_positions(data, start, end)
        if not subs:
            continue
        sub_records += len(subs)
        arrays = _declared_arrays(data, start, end)
        if not arrays:
            continue
        _count_at, data_start, _floats, points_count = max(
            arrays, key=lambda item: item[3]
        )
        points = [
            _F3.unpack_from(data, data_start + 12 * i) for i in range(points_count)
        ]
        members = []
        for j, sub_start in enumerate(subs):
            sub_end = subs[j + 1] if j + 1 < len(subs) else end
            sub = decode_sub_record(data, sub_start, sub_end)
            if _gate_sub_record(sub, points_count):
                gated += 1
                members.append(sub.triangles)
        if not members:
            continue
        folded, dropped, refused = _assemble(members)
        dedup_dropped += dropped
        guard_refused += refused
        if not folded:
            continue
        records += 1
        offset = len(vertices)
        vertices.extend(points)
        triangles.extend(
            (a + offset, b + offset, c + offset) for a, b, c in folded
        )
    if not triangles:
        return None
    return FaceGpScan(
        vertices=tuple(vertices),
        triangles=tuple(triangles),
        records=records,
        sub_records=sub_records,
        sub_records_gated=gated,
        guard_refused=guard_refused,
        dedup_dropped=dedup_dropped,
    )


def warning_detail(scan: FaceGpScan) -> str:
    """The route's summary warning (integer counts only — the summary
    is compared parsed-document equal against the port's)."""
    return (
        "no surface decoded: the CATSurfacicRep patch sub-records "
        "(30 04 04 ff ff ff d2 d2 51) decode under the CAT3DFaceGP law "
        "(#63): kind 3 at +57, u16be indices after the ff 7f / 01 80 "
        "marker, v = idx // 3 into the record's declared f32 point "
        f"array (one word after its count); {scan.sub_records_gated} "
        f"gated sub-record(s) of {scan.sub_records} folded into a "
        f"manifold mesh across {scan.records} patch stream(s), guard "
        f"refused {scan.guard_refused}, duplicate unordered triangles "
        f"dropped {scan.dedup_dropped}; source {SOURCE}. Every gated "
        "sub-record closes byte-exact (end == sub_len - 1) with mult-3 "
        "in-bounds indices and no repeated-index triangle; zero-area "
        "slivers from the writer's duplicate pinned coordinates ride "
        "as decoded (no skip convention fired, degenerate count 0). "
        "docs/evidence/2026-11-21-bagrep-face-gp.md"
    )
