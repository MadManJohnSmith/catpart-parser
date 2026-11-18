"""Exact planar faces & boundary loops of the nested store's facet records
(BR2, Ticket #54, Spec G #47).

Builds on the G3 facet model (``catpart.geometry.facets`` — record grammar
F1/F1w, lexicographic index space F2/C8, strip vs polygon primitive
semantics F3/F4) and decodes the three BR2 constructs on top of it:

- **TOP-04 Face**: one accepted facet record on the planar markers is the
  face carrier — ``01 <mk> <ty> ff [u32le n][12B f32le normal][counts]
  [refs]`` with the 12-byte normal payload on 0x49/0x4a/0x4c (4-byte
  header form). The record's boundary loops delimit the face patch.
- **TOP-05 Loop**: the ``ty`` byte is the loop count; the per-loop
  reference lengths follow as ``ty`` integers at a per-record COUNT
  WIDTH (u8 or u16be) that is independent of the record's reference
  width — u16 counts appear to the G3 byte-parse as ``(0, lo)`` pairs
  (high byte 0), which makes ``facets.record_loops`` emit phantom empty
  loops on such stores (:func:`record_true_loops` is the corrected
  split; the phantom empties consume no references, so triangle
  geometry is unaffected).
- **SRF-01 Plane**: the 12-byte f32le payload is a unit normal; the
  record's loop vertices are coplanar on a plane ``n.p + d = 0`` whose
  offset ``d`` is DERIVED (not stored) — validated corpus-wide on the
  pool-only scope; the composite index space (G3 F8) leaves most
  stores' references unverifiable against the pool.

Detector honesty (per construct, what the detector does NOT
discriminate — each edge has a committed synthetic negative in
``tests/test_brep_planar.py`` and ``scripts/triage/decode_brep_planar.py
--selftest``):

- TOP-04: the record-acceptance detector does NOT discriminate face
  records from any other accepted ``01 [41-4f]`` record (0x41/0x42/0x44
  triangle/strip content parses under the same grammar) — "record ==
  planar face" is a geometric reading (plane validation), not a byte
  marker; on composite stores it is unverifiable (refs leave the pool).
- TOP-05: the count-structure law does NOT discriminate outer boundary
  loops from inner hole loops (no orientation/role byte is claimed) and
  does not establish ring closure on the strip families (0x4a/0x42
  loops are strip segments, not boundary cycles); closure is a reading
  of 0x4c rings only.
- SRF-01: the normal detector does NOT discriminate an exact plane
  surface from a planar TESSELLATION PATCH of a curved surface (each
  0x4a strip record carries its own facet normal; a cylinder's facets
  are individually planar) — the per-record plane decode never
  establishes the underlying B-rep surface, only the record-local
  plane; and the derived offset ``d`` is an inference, not a stored
  field.
"""

from __future__ import annotations

import dataclasses
import math

from catpart.geometry.facets import (
    FacetRecord,
    POLY_MARKERS,
    record_loops,
)

#: Normal-bearing 4-byte-form markers (the facet-semantics note's
#: NORMAL_MARKERS_ALL minus the 5-byte-form 0x4b/0x4e, which are not
#: BR2's slice).
PLANAR_NORMAL_MARKERS = (0x49, 0x4A, 0x4C)

#: Plane coplanarity tolerance, relative to the record's point scale
#: (max |coordinate|, floored at 1.0): ``max |n.p + d| <= tol_rel * scale``.
#: Separates f32 rounding (observed <= 5.5e-7 absolute on the corpus's
#: pool-only seeds) from wrong-index-space decodes (observed >= 0.01
#: relative); the evidence note reports the spread distribution so the
#: threshold is not load-bearing.
PLANE_TOL_REL = 1e-4

#: Unit-normal acceptance window on ``|n| - 1`` (f32 components carry
#: 2^-23 relative rounding; the corpus's stored normals measure within
#: 1e-7 of 1).
UNIT_NORM_TOL = 1e-6

Point3 = tuple[float, float, float]

FACE_OK = "ok"
FACE_OUT_OF_POOL = "out-of-pool"
FACE_COUNT_VARIANT = "count-variant"
FACE_NO_LOOPS = "no-loops"


@dataclasses.dataclass(frozen=True)
class CountStructure:
    """The corrected loop delimitation of one record (TOP-05).

    ``count_width`` is the per-record count integer width (1 = u8,
    2 = u16be) — independent of the record's reference width; lengths
    are the ``ty`` per-loop reference lengths (summing to ``rec.n``).
    """

    count_width: int
    lengths: tuple[int, ...]


@dataclasses.dataclass(frozen=True)
class PlaneEquation:
    """The decoded record-local plane ``n.p + d = 0`` (SRF-01).

    ``normal`` is the record's stored 12B f32le triple; ``offset`` is
    the DERIVED ``d`` (mean of ``-n.p`` over the record's loop
    vertices); ``max_dev`` is ``max |n.p + d|`` over the same points.
    """

    normal: Point3
    offset: float
    max_dev: float
    tol: float

    @property
    def coplanar(self) -> bool:
        return self.max_dev <= self.tol


def count_structure(rec: FacetRecord) -> CountStructure | None:
    """The true loop delimitation of an accepted record (TOP-05 law).

    ``ty`` is the loop count; the lengths follow at the record's count
    width: ``len(counts) == ty`` reads u8 lengths; ``len(counts) ==
    2*ty`` with zero high bytes reads u16be lengths. Anything else is a
    count-encoding variant — ``None``, the loop structure is NOT
    established for that record (do not guess).
    """
    k = len(rec.counts)
    if rec.type and k == rec.type:
        return CountStructure(count_width=1, lengths=tuple(rec.counts))
    if rec.type and k == 2 * rec.type and all(c == 0 for c in rec.counts[0::2]):
        return CountStructure(
            count_width=2,
            lengths=tuple(rec.counts[i + 1] for i in range(0, k, 2)),
        )
    return None


def record_true_loops(rec: FacetRecord) -> list[tuple[int, ...]]:
    """The record's boundary loops under the corrected delimitation.

    Unlike ``facets.record_loops`` (the G3 byte-parse split, which sees
    u16 lengths as ``(0, lo)`` pairs and yields phantom empty loops),
    this splits at the true per-loop lengths. A count-encoding variant
    record falls back to the byte-parse split (which consumes no
    references on the u16 pattern and keeps triangle geometry stable);
    callers that need the LOOP structure must check
    :func:`count_structure` first — a fallback here means the loop
    structure is not established.
    """
    cs = count_structure(rec)
    if cs is None:
        return record_loops(rec)
    loops = []
    o = 0
    for length in cs.lengths:
        loops.append(rec.refs[o : o + length])
        o += length
    return loops


def _dot(a: Point3, b: Point3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Point3, b: Point3) -> Point3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _sub(a: Point3, b: Point3) -> Point3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def normal_unit_deviation(normal: Point3) -> float:
    """``|n| - 1`` for the stored normal (SRF-01 unit-normal law)."""
    return math.sqrt(_dot(normal, normal)) - 1.0


def fit_plane(points: list[Point3], normal: Point3) -> PlaneEquation | None:
    """The plane ``n.p + d = 0`` through ``points`` with the given normal.

    ``d`` is derived (mean of ``-n.p``); ``max_dev`` is the worst point
    deviation. Tolerance scales with the point cloud (``PLANE_TOL_REL``).
    Returns ``None`` for an empty point list.
    """
    if not points:
        return None
    proj = [_dot(normal, p) for p in points]
    d = -sum(proj) / len(proj)
    max_dev = max(abs(pr + d) for pr in proj)
    scale = max(1.0, max(abs(c) for p in points for c in p))
    return PlaneEquation(
        normal=normal, offset=d, max_dev=max_dev, tol=PLANE_TOL_REL * scale
    )


def newell_normal(points: list[Point3]) -> Point3:
    """The closed ring's Newell normal (ring order, cyclic closure)."""
    nx = ny = nz = 0.0
    for i in range(len(points)):
        x1, y1, z1 = points[i]
        x2, y2, z2 = points[(i + 1) % len(points)]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    return (nx, ny, nz)


@dataclasses.dataclass(frozen=True)
class LoopReading:
    """One loop's primitive reading (TOP-05).

    ``closed_cycle`` is the READING assertion for rings (0x4c: the
    boundary cycle closes last->first by construction of the polygon
    reading, G3 F4) — not a byte-measured property; strips carry
    ``None`` (a strip segment is not a boundary cycle). No byte marks
    outer vs inner loops — the detector does not discriminate loop
    roles.
    """

    length: int
    kind: str  # "ring" (0x4c closed cycle) or "strip" (strip segment)
    closed_cycle: bool | None  # rings: the closed-cycle reading; strips: None
    degenerate: bool  # fewer than 3 refs


@dataclasses.dataclass(frozen=True)
class DecodedPlanarFace:
    """One accepted facet record decoded as a planar face (BR2 output).

    ``status``: ``ok`` — in-pool, fully decoded and validated;
    ``out-of-pool`` — references leave the pool (composite index space
    or a clean-store variant; geometry NOT validated);
    ``count-variant`` — the loop delimitation is not established;
    ``no-loops`` — ``ty == 0`` (the normal and layout still decode).
    """

    offset: int
    marker: int
    loop_count: int
    header_len: int
    ref_width: int
    count_width: int | None
    loops: tuple[tuple[int, ...], ...]  # lexicographic ranks, raw refs
    normal: Point3 | None
    normal_unit_dev: float | None
    plane: PlaneEquation | None
    oriented: bool | None  # winding/Newell sign vs the stored normal
    loop_readings: tuple[LoopReading, ...]
    status: str


def _strip_triangles(refs: tuple[int, ...]) -> list[tuple[int, int, int]]:
    """G3's strip reading: (r_t, r_{t+1}, r_{t+2}), flip on odd t."""
    tris = []
    for t in range(len(refs) - 2):
        tri = (refs[t], refs[t + 1], refs[t + 2])
        if t % 2 == 1:
            tri = (tri[2], tri[1], tri[0])
        tris.append(tri)
    return tris


def decode_planar_face(
    pool: list[Point3],
    lex: list[int],
    rec: FacetRecord,
) -> DecodedPlanarFace:
    """Decode one accepted facet record as a planar face (TOP-04/05/SRF-01).

    ``pool`` is the flattened pool in walk order and ``lex`` the
    lexicographic rank map (:func:`facets.lex_rank_map`). The record's
    reference width/count structure/normal layout decode byte-exactly;
    the geometric plane validation needs in-pool references and is
    skipped (status) otherwise — never guessed.
    """
    cs = count_structure(rec)
    loops = record_true_loops(rec)
    all_out = any(x >= len(pool) for lp in loops for x in lp)
    normal = rec.normal
    unit_dev = normal_unit_deviation(normal) if normal is not None else None

    readings = []
    for lp in loops:
        if rec.marker in POLY_MARKERS:
            kind = "ring"
            closed = len(lp) >= 3
        else:
            kind = "strip"
            closed = None
        readings.append(
            LoopReading(length=len(lp), kind=kind, closed_cycle=closed, degenerate=len(lp) < 3)
        )

    if all_out:
        return DecodedPlanarFace(
            offset=rec.offset,
            marker=rec.marker,
            loop_count=rec.type,
            header_len=rec.header_len,
            ref_width=rec.width,
            count_width=cs.count_width if cs else None,
            loops=tuple(loops),
            normal=normal,
            normal_unit_dev=unit_dev,
            plane=None,
            oriented=None,
            loop_readings=tuple(readings),
            status=FACE_OUT_OF_POOL,
        )
    if cs is None and rec.type:
        return DecodedPlanarFace(
            offset=rec.offset,
            marker=rec.marker,
            loop_count=rec.type,
            header_len=rec.header_len,
            ref_width=rec.width,
            count_width=None,
            loops=tuple(loops),
            normal=normal,
            normal_unit_dev=unit_dev,
            plane=None,
            oriented=None,
            loop_readings=tuple(readings),
            status=FACE_COUNT_VARIANT,
        )
    if not loops or all(len(lp) == 0 for lp in loops):
        return DecodedPlanarFace(
            offset=rec.offset,
            marker=rec.marker,
            loop_count=rec.type,
            header_len=rec.header_len,
            ref_width=rec.width,
            count_width=cs.count_width if cs else None,
            loops=tuple(loops),
            normal=normal,
            normal_unit_dev=unit_dev,
            plane=None,
            oriented=None,
            loop_readings=tuple(readings),
            status=FACE_NO_LOOPS,
        )

    pts = [pool[lex[x]] for lp in loops for x in lp]
    oriented = None
    if normal is not None:
        signs = []
        if rec.marker in POLY_MARKERS:
            for lp in loops:
                if len(lp) >= 3:
                    ring = [pool[lex[x]] for x in lp]
                    signs.append(_dot(newell_normal(ring), normal) > 0.0)
        else:
            for lp in loops:
                for tri in _strip_triangles(lp):
                    a, b, c = (pool[lex[x]] for x in tri)
                    if a == b or b == c or a == c:
                        continue
                    cr = _cross(_sub(b, a), _sub(c, a))
                    if cr == (0.0, 0.0, 0.0):
                        continue
                    signs.append(_dot(cr, normal) > 0.0)
        if signs:
            oriented = all(signs)

    plane = fit_plane(pts, normal) if normal is not None else None
    return DecodedPlanarFace(
        offset=rec.offset,
        marker=rec.marker,
        loop_count=rec.type,
        header_len=rec.header_len,
        ref_width=rec.width,
        count_width=cs.count_width if cs else None,
        loops=tuple(loops),
        normal=normal,
        normal_unit_dev=unit_dev,
        plane=plane,
        oriented=oriented,
        loop_readings=tuple(readings),
        status=FACE_OK,
    )
