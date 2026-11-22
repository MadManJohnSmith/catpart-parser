"""Exact-analytic surface availability scanner (W11, marathon B8).

The B8 question: do the parts without ``CAT3DFaceGP`` tessellation —
the ``undecoded-variant`` population of
``fitness/reports/20261121T103944Z-d2c9ff.json`` — carry *evaluable*
exact surfaces outside the shipped exact-surface routes, in the direct
analytic form (plane/cylinder/cone/sphere with axis+radius+limits)?

Scope against the committed exact-surface routes: B-spline/NURBS
surfaces are W3's E5 class-``0x00e7`` route
(docs/evidence/2026-11-22-e5-class-table.md — the degree-(3,1) sweeps
that model the analytic cylinders/planes), and the shipped ``a5 03 34``
frame route covers the compact-head B-splines; neither is re-derived
here. This scanner walks the two streams that could carry the *direct*
analytic form and the store-body record stream W3's class table does
not reach:

- **The nested store body's object stream** (the ``<seq u32le>``
  -prefixed records of the ``CATStdCont`` store: ``ff ff 02 00``
  object records, ``ff 03 01 00`` property definitions, ``04 04 fd ff``
  property values, ``14 0c ff ff ff ff ff`` scene records). The only
  analytic shapes observed are the class-``0x56`` plane objects whose
  direction pair (``0.7071, 0.7071, 0`` / ``0.7071, -0.7071, 0``, and
  the Y-normal twin) is byte-identical in every observed file — the
  store's template default, not part geometry — and no record carries
  parametric bounds.
- **The ``CATPrtCont`` content bulk** under the committed A/B frame
  law (docs/evidence/2026-11-19-bulk-stream.md §3: ``a4+a``/``b1+b``
  family bytes, flag ∈ {0x03, 0x13, 0x83}, class byte, length field,
  retained token). The frame classes carry scalar parameters and
  limits (``0x06``/``0x18``/``0x24`` limit ladders ±1e6/±5e5/±5e4;
  ``0x02``/``0x0e``/``0x27``/``0x5b`` per-part scalars).

The measured answer on the whole population is **no**
(docs/evidence/2026-11-22-w11-analytic-surfaces.md): no per-part
analytic record, 0 ``a5 03 34`` frames, 0 NURBS signatures (BR5
content detector), and — cross-measured with W3's own census — 0 E5
class-``0x00e7`` records. Nothing tessellates; the verdict is a
taxonomy word, not an export.

Detector honesty (the dispatch-recipes rule): the unit-vector shape
detector does NOT discriminate intent — two orthogonal unit f32
3-vectors are also what an axis frame or a rotation matrix row pair
looks like, its phase-census reads alias (the fixed-point-ladder guard
removes the measured 2^-k family), and the class byte ``0x56`` is a
vocabulary value, not a proven type. Template equivalence is the
byte-exact law; the shape census is diagnostic and never
verdict-driving. ``--selftest`` (the probe) pins the discriminating
edges with synthetic bytes.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field

from catpart.brep.cgm_nurbs import nurbs_signatures
from catpart.geometry import store

VERDICT_NO_ANALYTIC = "no-evaluable-analytic-surface"
VERDICT_ANALYTIC_PRESENT = "analytic-surface-records-present"

#: The store body's template plane payloads (W11: byte-identical in all
#: ten population files and present in passing files' bodies too). Two
#: measured default direction pairs — the Z-normal 45° pair
#: u = (0.7071, 0.7071, 0), v = (0.7071, -0.7071, 0), and the Y-normal
#: pair u = (0.7071, 0, 0.7071), v = (-0.7071, 0, 0.7071) — measured as
#: bytes, not recomputed floats.
TEMPLATE_PLANE_UV = (
    bytes.fromhex("f304353ff304353f00000000f304353ff30435bf"),
    bytes.fromhex("f304353f00000000f304353ff30435bf00000000f304353f"),
)

_OBJECT_HEADER = b"\xff\xff\x02\x00"
_PROPERTY_DEF_HEADER = b"\xff\x03\x01\x00"
_PROPERTY_VALUE_HEADER = b"\x04\x04\xfd\xff"
_SCENE_HEADER = b"\x14\x0c\xff\xff\xff\xff\xff"

_A_FAMILY_BASE = 0xA4
_B_FAMILY_BASE = 0xB1
_MAX_WIDTH = 4
_FLAGS = frozenset((0x03, 0x13, 0x83))
_MAX_PAYLOAD = 1 << 20

_SURFACE_FAMILY = 0xA5
_SURFACE_CLASS = 0x34


@dataclass(frozen=True)
class PlaneRecord:
    """One class-``0x56`` object record of the store body object stream.

    ``start`` is the absolute offset of the ``ff ff 02 00`` header;
    ``object_id`` the u32le that follows the ``01 56`` class bytes;
    ``is_template`` the byte-exact template-payload law above (either
    measured default direction pair).
    """

    start: int
    object_id: int
    is_template: bool


@dataclass(frozen=True)
class ShapeHits:
    """Diagnostic axis-shape census over phase-census floats.

    ``count`` is the number of 4-tuples passing the shape test,
    ``distinct`` the number of distinct tuples (a repeated template
    record inflates ``count`` but not ``distinct``). Phase-census reads
    alias, so a hit names where to look — it is never verdict-driving.
    """

    count: int
    distinct: int


@dataclass(frozen=True)
class BulkFrameClass:
    """One A/B frame class census entry of the content bulk."""

    family: str
    width: int
    cls: int
    count: int
    payload_bytes: int


@dataclass(frozen=True)
class AnalyticScan:
    """The analytic-availability taxonomy of one part."""

    verdict: str
    store_body_size: int | None
    object_records: int
    plane_records: tuple[PlaneRecord, ...] = ()
    template_planes: int = 0
    scene_records: int = 0
    property_values: int = 0
    cylinder_candidates: ShapeHits = ShapeHits(0, 0)
    cone_candidates: ShapeHits = ShapeHits(0, 0)
    nurbs_knot_runs: int = 0
    nurbs_weight_runs: int = 0
    a5_surface_frames: int = 0
    bulk_dialect: str | None = None
    bulk_frame_classes: tuple[BulkFrameClass, ...] = field(default_factory=tuple)

    @property
    def per_part_planes(self) -> int:
        return len(self.plane_records) - self.template_planes


def _store_body_span(data) -> tuple[int, int] | None:
    """The first located ``CATStdCont`` store body, or ``None``.

    Falls back to the block's own region when the shipped locator
    raises (the stage-3a/12 recovered stores keep their spans there,
    but the object-stream walk only needs a byte span to classify).
    """
    blocks = store.valid_blocks(data)
    stdcont = [b for b, nm in blocks if nm == "CATStdCont"]
    if not stdcont:
        return None
    d8 = int.from_bytes(data[8:12], "big") if len(data) >= 12 else 0
    try:
        span = store.locate_store(data, stdcont[0], blocks, d8)
    except Exception:
        index = [i for i, (b, _) in enumerate(blocks) if b == stdcont[0]][0]
        return stdcont[0], blocks[index + 1][0]
    if span is None:
        index = [i for i, (b, _) in enumerate(blocks) if b == stdcont[0]][0]
        return stdcont[0], blocks[index + 1][0]
    return span.body_lo, span.body_hi


def _record_spans(body: bytes) -> list[tuple[int, int]]:
    """The object-stream record spans of a store body.

    A record starts at one of the three observed headers (object,
    property definition, scene) and ends at the next header (or the
    body end). The walk is header-ordered, so the spans partition the
    body from the first header on; bytes before the first header are
    the body's preamble and are not framed here. An ``ff ff 02 00``
    occurrence whose next bytes are not an ``01/07 5X`` class pair is
    a coincidence, not a record, and is dropped so it cannot split a
    real record.
    """
    events: list[int] = []
    for header in (_OBJECT_HEADER, _PROPERTY_DEF_HEADER, _SCENE_HEADER):
        pos = 0
        while True:
            hit = body.find(header, pos)
            if hit < 0:
                break
            events.append(hit)
            pos = hit + 1
    events.sort()
    boundaries = []
    for start in events:
        if body[start : start + 4] == _OBJECT_HEADER:
            nxt = body[start + 4 : start + 6]
            if not (len(nxt) == 2 and nxt[0] in (0x01, 0x07) and 0x50 <= nxt[1] <= 0x58):
                continue
        boundaries.append(start)
    spans = []
    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(body)
        spans.append((start, end))
    return spans


def plane_records(data, lo: int, hi: int) -> list[PlaneRecord]:
    """The ``01 56`` plane objects in ``data[lo:hi)`` under the span walk."""
    body = bytes(data[lo:hi])
    out: list[PlaneRecord] = []
    for start, end in _record_spans(body):
        if body[start : start + 6] != _OBJECT_HEADER + b"\x01\x56":
            continue
        if start + 10 > len(body):
            continue
        object_id = int.from_bytes(body[start + 6 : start + 10], "little")
        payload = body[start + 10 : end]
        is_template = any(pattern in payload for pattern in TEMPLATE_PLANE_UV)
        out.append(PlaneRecord(lo + start, object_id, is_template))
    return out


def f32_values(body: bytes) -> list[float]:
    """Phase-tolerant f32 reads: the first finite hit per 4-byte window.

    A record's floats sit at arbitrary phases (the object stream packs
    them after odd-length headers), so every phase is tried and one
    value is kept per 4-byte window. This is a census read, not a
    field law — the alias risk is bounded by the shape guards that
    consume the values.
    """
    out: list[float] = []
    seen: set[int] = set()
    for off in range(len(body) - 3):
        v = struct.unpack_from("<f", body, off)[0]
        if v == 0 or v != v or v in (float("inf"), float("-inf")):
            continue
        if abs(v) < 1e-4 or abs(v) >= 1e7:
            continue
        window = off // 4
        if window in seen:
            continue
        seen.add(window)
        out.append(v)
    return out


def _unit(v: tuple[float, float, float]) -> bool:
    n = v[0] * v[0] + v[1] * v[1] + v[2] * v[2]
    return 0.999 <= n <= 1.001


def _dyadic(v: float) -> bool:
    """``v`` is an exact power of two (positive; the alias signature)."""
    if v <= 0 or not (v < 1e7):
        return False
    k = round(math.log2(v))
    return abs(v - 2.0**k) <= 1e-15 * max(1.0, abs(v))


def _fixed_point_alias(axis: tuple[float, float, float]) -> bool:
    """The W2 fixed-point-ladder alias: every non-unit axis component an
    exact 2^-k. A real axis direction carries irrational components."""
    others = [c for c in axis if abs(abs(c) - 1.0) > 1e-9 and c != 0.0]
    return bool(others) and all(_dyadic(abs(c)) for c in others)


def analytic_shape_candidates(values: list[float]) -> dict[str, ShapeHits]:
    """Axis+radius shape detections over census floats (diagnostic).

    Every consecutive 4-tuple of the census list is tested (the corpus
    band is mm-scale, so the radius bar is 1e-3..1e6):

    - **cylinder**: ``(axis(3), radius)`` with a unit axis and a
      positive radius;
    - **cone**: ``(axis(3), tan(half-angle))`` with a unit axis and a
      finite positive ``tan`` below 1e6.

    A sphere needs a law that distinguishes a center from an axis —
    none is measured, so spheres are not detected here (reported as
    absent, not guessed). The census read is candidate-grade and never
    verdict-driving: a hit names where to look, not a decoded surface.
    """
    cyl: list[tuple[float, float, float, float]] = []
    cone: list[tuple[float, float, float, float]] = []
    n = len(values)
    for i in range(n - 3):
        a = (values[i], values[i + 1], values[i + 2])
        r = values[i + 3]
        if not (1e-3 <= r < 1e6):
            continue
        if _unit(a) and not _fixed_point_alias(a):
            cyl.append((*a, r))
            cone.append((*a, r))
    return {
        "cylinder": ShapeHits(len(cyl), len(set(cyl))),
        "cone": ShapeHits(len(cone), len(set(cone))),
    }


def parse_frame(data, pos: int, hi: int):
    """One A/B frame at ``pos``; ``(family, width, cls, end)`` or ``None``.

    The committed two-family grammar (bulk-stream §3.1): the family byte
    names the width, the flag must be an observed value, the length
    field is u32le (A) / u8 (B), and the frame must close exactly.
    """
    if pos + 4 > hi:
        return None
    byte0 = data[pos]
    if _A_FAMILY_BASE < byte0 <= _A_FAMILY_BASE + _MAX_WIDTH:
        width = byte0 - _A_FAMILY_BASE
        if pos + 7 + width > hi or data[pos + 1] not in _FLAGS:
            return None
        payload_len = int.from_bytes(data[pos + 3 : pos + 7], "little")
        if payload_len > _MAX_PAYLOAD:
            return None
        end = pos + 7 + width + payload_len
        if end > hi:
            return None
        return "A", width, data[pos + 2], end
    if _B_FAMILY_BASE < byte0 <= _B_FAMILY_BASE + _MAX_WIDTH:
        width = byte0 - _B_FAMILY_BASE
        if pos + 4 + width > hi or data[pos + 1] not in _FLAGS:
            return None
        payload_len = data[pos + 3]
        end = pos + 4 + width + payload_len
        if end > hi:
            return None
        return "B", width, data[pos + 2], end
    return None


def bulk_clusters(data, lo: int, hi: int, min_chain: int = 3):
    """Contiguous A/B frame runs of >= ``min_chain`` frames in ``[lo, hi)``.

    The cluster law of bulk-stream §3.2: a run counts when it chains at
    least ``min_chain`` frames and closes exactly on its own end; later
    clusters are found by resuming the byte scan at the previous end.
    Returns ``(clusters, frame_classes)`` where clusters are
    ``(start, end)`` spans.
    """
    clusters: list[tuple[int, int]] = []
    counts: dict[tuple[str, int, int], list[int]] = {}
    pos = lo
    while pos < hi - 8:
        first = parse_frame(data, pos, hi)
        if first is None:
            pos += 1
            continue
        chain = 0
        scan = pos
        while True:
            frame = parse_frame(data, scan, hi)
            if frame is None:
                break
            chain += 1
            key = frame[:3]
            counts.setdefault(key, [0, 0])
            counts[key][0] += 1
            counts[key][1] += frame[3] - scan
            scan = frame[3]
        if chain >= min_chain:
            clusters.append((pos, scan))
            pos = scan
        else:
            pos += 1
    classes = tuple(
        BulkFrameClass(family, width, cls, n, payload_bytes)
        for (family, width, cls), (n, payload_bytes) in sorted(counts.items())
    )
    return clusters, classes


def bulk_frame_classes(data, lo: int, hi: int) -> tuple[BulkFrameClass, ...]:
    """The A/B frame class census of ``data[lo:hi)`` (bulk-stream law).

    The two-family grammar of docs/evidence/2026-11-19-bulk-stream.md
    §3.1, re-implemented read-only: family byte ``a4+a``/``b0+b`` (width
    1..4), flag in {0x03, 0x13, 0x83}, class byte, u32le (A) / u8 (B)
    payload length, a retained ``W``-byte token. A frame counts only
    when it closes exactly; the walk stops at the first non-frame byte.
    """
    counts: dict[tuple[str, int, int], list[int]] = {}
    pos = lo
    while pos < hi:
        frame = parse_frame(data, pos, hi)
        if frame is None:
            break
        family, width, cls, end = frame
        counts.setdefault((family, width, cls), [0, 0])
        counts[(family, width, cls)][0] += 1
        counts[(family, width, cls)][1] += end - pos
        pos = end
    return tuple(
        BulkFrameClass(family, width, cls, n, payload_bytes)
        for (family, width, cls), (n, payload_bytes) in sorted(counts.items())
    )


def _bulk_dialect(data) -> str | None:
    """The content dialect word of the ``CATPrtCont`` region.

    The metadata table of the committed bulk-stream probe is not
    re-derived here: the dialect is the coarse word — ``object-stream``
    when a frame cluster of >= 3 frames exists anywhere in the region,
    ``E5`` when an ``e5 0d`` marker sits in the head window,
    ``other`` otherwise. The probe
    (``scripts/triage/probe_bulk_stream.py``) remains the authority for
    the table-exact numbers.
    """
    from catpart.brep.cgm_nurbs import valid_regions

    for blk, name, rend in valid_regions(data):
        if name != "CATPrtCont":
            continue
        head = bytes(data[blk : min(blk + 1024, rend)])
        clusters, _classes = bulk_clusters(data, blk, rend)
        if clusters:
            return "object-stream"
        if b"\xe5\x0d" in head:
            return "E5"
        return "other"
    return None


def scan_part(data) -> AnalyticScan:
    """Classify one part's analytic-surface availability.

    Walks the store body's object stream, the ``CATPrtCont`` content
    bulk (cluster census + A/B payload float census), and runs the
    NURBS signature detector plus the shipped ``a5 03 34`` frame scan
    over the whole file. The verdict is
    ``analytic-surface-records-present`` only when a *law-pinned*
    analytic record is detected: a per-part (non-template) ``01 56``
    plane object, an ``a5 03 34`` surface frame, or a NURBS signature
    run. The diagnostic shape census (phase-aliased, candidate-grade)
    never drives the verdict. The measured population verdict is
    ``no-evaluable-analytic-surface``.
    """
    body_span = _store_body_span(data)
    planes: list[PlaneRecord] = []
    object_records = 0
    scene_records = 0
    property_values = 0
    body_size = None
    shape = {"cylinder": ShapeHits(0, 0), "cone": ShapeHits(0, 0)}
    knot_runs = weight_runs = 0
    if body_span is not None:
        body_lo, body_hi = body_span
        body_size = body_hi - body_lo
        body = bytes(data[body_lo:body_hi])
        planes = plane_records(data, body_lo, body_hi)
        for start, _end in _record_spans(body):
            if body[start : start + 4] == _OBJECT_HEADER:
                object_records += 1
            elif body[start : start + 7] == _SCENE_HEADER:
                scene_records += 1
        pos = body.find(_PROPERTY_VALUE_HEADER)
        while pos >= 0:
            property_values += 1
            pos = body.find(_PROPERTY_VALUE_HEADER, pos + 1)
        values = f32_values(body)
        shape = _add_shape(shape, analytic_shape_candidates(values))
        sigs = nurbs_signatures(data, body_lo, body_hi)
        knot_runs += len(sigs.knot_runs)
        weight_runs += len(sigs.weight_runs)
    # the content bulk: cluster census + payload float census over the
    # whole CATPrtCont region
    dialect = _bulk_dialect(data)
    frame_classes: tuple[BulkFrameClass, ...] = ()
    from catpart.brep.cgm_nurbs import valid_regions

    for blk, name, rend in valid_regions(data):
        if name != "CATPrtCont":
            continue
        clusters, frame_classes = bulk_clusters(data, blk, rend)
        bulk_values: list[float] = []
        for cl_start, cl_end in clusters:
            scan = cl_start
            while scan < cl_end:
                frame = parse_frame(data, scan, cl_end)
                if frame is None:
                    break
                chunk = bytes(data[scan : frame[3]])
                bulk_values.extend(f32_values(chunk))
                scan = frame[3]
        shape = _add_shape(shape, analytic_shape_candidates(bulk_values))
        sigs = nurbs_signatures(data, blk, rend)
        knot_runs += len(sigs.knot_runs)
        weight_runs += len(sigs.weight_runs)
        break
    a5 = _surface_frames(data)
    template_planes = sum(1 for p in planes if p.is_template)
    per_part_planes = len(planes) - template_planes
    analytic_present = (
        per_part_planes > 0
        or knot_runs > 0
        or weight_runs > 0
        or a5 > 0
    )
    return AnalyticScan(
        verdict=VERDICT_ANALYTIC_PRESENT if analytic_present else VERDICT_NO_ANALYTIC,
        store_body_size=body_size,
        object_records=object_records,
        plane_records=tuple(planes),
        template_planes=template_planes,
        scene_records=scene_records,
        property_values=property_values,
        cylinder_candidates=shape["cylinder"],
        cone_candidates=shape["cone"],
        nurbs_knot_runs=knot_runs,
        nurbs_weight_runs=weight_runs,
        a5_surface_frames=a5,
        bulk_dialect=dialect,
        bulk_frame_classes=frame_classes,
    )


def _add_shape(
    total: dict[str, ShapeHits], extra: dict[str, ShapeHits]
) -> dict[str, ShapeHits]:
    """Sum two shape-census dicts elementwise."""
    return {
        key: ShapeHits(
            total[key].count + extra[key].count,
            total[key].distinct + extra[key].distinct,
        )
        for key in total
    }


def _surface_frames(data) -> int:
    """The shipped ``a5 03 34`` surface-frame count of the part."""
    from catpart.geometry.surface import candidate_frames

    return len(candidate_frames(data))


def knot_runs(data, lo: int, hi: int):
    """The BR5-03 knot-array runs over ``[lo, hi)`` (twin:
    ``analytic::knot_runs`` — a thin delegation to
    ``cgm_nurbs._knot_runs``, the shipped all-defaults policy)."""
    from catpart.brep.cgm_nurbs import _knot_runs

    return _knot_runs(data, lo, hi)


def weight_runs(data, lo: int, hi: int, minimum: int = 4):
    """The rational-weight runs (>= ``minimum`` exact f64 1.0) over
    ``[lo, hi)`` (twin: ``analytic::weight_runs``)."""
    from catpart.brep.cgm_nurbs import _weight_runs

    return _weight_runs(data, lo, hi, minimum=minimum)
