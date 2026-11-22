"""The B-rep meshing lane of the W2 marathon round (2026-11-22).

This module is the future ``brep_mesh`` export route's home. Its first
committed content is a **measured, unwired** decode: the counts-less
``0x49`` triangle-record family — the population behind the official
211 ``empty-mesh`` parts' biggest store (``PalmDown5motors2``:
171,916 of its 171,978 unresolved facet candidates parse here with
zero rejects).

The family law (W2 census 2026-11-22, corpus-measured, see
``docs/evidence/marathon/w2-progress.md`` and
``docs/evidence/data/w2-empty-mesh-baseline.csv``):

- header ``01 49 ty ff`` (4 B, the F1 4-byte form);
- ``u32le n`` with ``n == 3*ty`` (BR2-18's law, this family included);
- 12 B f32le unit normal (|n-1| <= 1e-6, BR2-06's bar);
- ``3*ty`` u16be big-endian references, no counts table — the family
  where the ty loops are implicit: loop i is refs[3i:3i+3], one
  triangle per loop;
- the record's end must stay inside the span.

Why it is NOT wired into the exporter: the family's references index
the composite element space, whose element region does not decode
under any committed law (the U3-variant residue + the stage-8
mixed-write miss — both fail ``undecoded-variant`` on every one of the
9 empty-mesh stores that carry a pool and facet records). The
mapping-refutation measurements are committed: under identity,
lex-rank, and offset-shifted mappings the records' mapped triangles
disagree with their stored normals (identity 1/800, lex 290/800,
offsets δ ∈ [-16,16] all ≤ 10/800 — a correct mapping scores ~100%,
the pool-only scope validates at 98.99%, BR2-10). A manifold-but-
scrambled assembly (180,859 triangles, manifold true, 98% of records
admitted by an EdgeGuard simulation) is exactly the geometry the
no-guessing gate refuses to ship.

Reopening criterion: when ``catpart.geometry.composite`` gains an
element-region decode law for these stores, the mapping validates
per-record (plane agreement) and the route assembles behind the
committed gates — in-bounds refs, unit normals, per-record manifold
admission (:class:`catpart.geometry.mesh.EdgeGuard`), degenerate
members filtered and named (the 2026-11-21 member-filter law) — and
this family becomes emitable alongside the accepted records. The
parser here is deliberately standalone so that day needs no re-derive.
"""

from __future__ import annotations

import dataclasses
import math
import struct

#: the family's marker and header form (the F1 4-byte form).
MARKER = 0x49
FORM = b"\x01\x49"

#: structural bound on ``ty`` (T65's base cap; the corpus measures ty
#: 1..5 on this family — anything above is unobserved, fail-closed).
MAX_TY = 16

#: the unit-normal bar (BR2-06: |n-1| <= 1e-6, 54,265/54,265 corpus).
UNIT_NORM_TOL = 1e-6

_HEADER = 4  # 01 49 ty ff
_N = 4  # u32le n
_NORMAL = 12  # 3 x f32le


@dataclasses.dataclass(frozen=True)
class CountlessTriangleRecord:
    """One counts-less ``0x49`` triangle record, structurally valid.

    ``refs`` are raw big-endian u16 values in the store's reference
    space (the composite element space on composite stores — the
    mapping into pool positions is the open question this module
    documents, never asserted). ``ty`` loops of 3 references each;
    ``n == 3*ty``.
    """

    offset: int
    ty: int
    n: int
    normal: tuple[float, float, float]
    refs: tuple[int, ...]
    end: int


def parse_countsless_record(data, o: int, body_hi: int):
    """Parse one counts-less ``0x49`` triangle record at ``o``.

    Fail-closed: ``None`` unless the header form, the ``n == 3*ty``
    law, the 12-byte unit normal, the in-bounds length and the
    references' span fit all hold. The references' VALUES are not
    bounds-checked here (the caller supplies the reference-space
    bound); the record's byte extent is.
    """
    if o + _HEADER > body_hi:
        return None
    if bytes(data[o : o + 2]) != FORM or data[o + 3] != 0xFF:
        return None
    ty = data[o + 2]
    if not (1 <= ty <= MAX_TY):
        return None
    if o + _HEADER + _N > body_hi:
        return None
    n = int.from_bytes(data[o + 4 : o + 8], "little")
    if n != 3 * ty:
        return None
    end = o + _HEADER + _N + _NORMAL + 2 * n
    if end > body_hi:
        return None
    normal = struct.unpack_from("<fff", data, o + 8)
    norm = math.sqrt(normal[0] ** 2 + normal[1] ** 2 + normal[2] ** 2)
    if not math.isfinite(norm) or abs(norm - 1.0) > UNIT_NORM_TOL:
        return None
    refs = tuple(
        int.from_bytes(data[o + 20 + 2 * j : o + 22 + 2 * j], "big")
        for j in range(n)
    )
    return CountlessTriangleRecord(
        offset=o, ty=ty, n=n, normal=normal, refs=refs, end=end
    )


@dataclasses.dataclass(frozen=True)
class FamilyCensus:
    """The counts-less family content of one span."""

    candidates: int  # STRIP_RE header positions in the span
    records: int  # family records that parse and validate
    unit_normal_rejects: int  # header matches failing the normal bar
    span_fit_rejects: int  # header matches running past the span


def census_family(data, lo: int, hi: int) -> FamilyCensus:
    """Census the counts-less ``0x49`` family over ``[lo, hi)``.

    Every ``STRIP_RE`` header position is tested; candidates inside
    another family record (overlaps are not observed — the corpus
    records tile at 26 B — but a defensive walk skips them) are not
    re-counted. Read-only.
    """
    from catpart.geometry import facets

    positions = [m.start() for m in facets.STRIP_RE.finditer(data, lo, hi)]
    records = 0
    unit_rejects = 0
    fit_rejects = 0
    skip_until = -1
    for o in positions:
        if o < skip_until:
            continue
        if o + _HEADER > hi or bytes(data[o : o + 2]) != FORM or data[o + 3] != 0xFF:
            continue
        ty = data[o + 2]
        if not (1 <= ty <= MAX_TY) or o + _HEADER + _N > hi:
            continue
        n = int.from_bytes(data[o + 4 : o + 8], "little")
        if n != 3 * ty:
            continue
        end = o + _HEADER + _N + _NORMAL + 2 * n
        if end > hi:
            fit_rejects += 1
            continue
        normal = struct.unpack_from("<fff", data, o + 8)
        norm = math.sqrt(normal[0] ** 2 + normal[1] ** 2 + normal[2] ** 2)
        if not math.isfinite(norm) or abs(norm - 1.0) > UNIT_NORM_TOL:
            unit_rejects += 1
            continue
        records += 1
        skip_until = end
    return FamilyCensus(
        candidates=len(positions),
        records=records,
        unit_normal_rejects=unit_rejects,
        span_fit_rejects=fit_rejects,
    )


def record_triangles(rec: CountlessTriangleRecord) -> list[tuple[int, int, int]]:
    """The family's triangle reading: loop i = refs[3i:3i+3].

    One triangle per loop, vertex order as stored (the winding's
    orientation question is part of the refuted-mapping note — the
    committed strip-flip law does not apply: the loops are 3-ref
    triangles, not strip segments).
    """
    return [
        (rec.refs[3 * i], rec.refs[3 * i + 1], rec.refs[3 * i + 2])
        for i in range(rec.ty)
    ]


# --- the deterministic 2D ear clipper ---------------------------------------
#
# The route's polygon triangulator for planar boundary-cycle loops
# (0x4c rings and any future correctly-mapped polygon loop). Scope:
# ONE simple polygon (no holes — hole bridging is named open below),
# pre-validated coplanar by the caller. The committed fan law
# (decode_soup) stays untouched; this is the route-side component for
# the day the mapping lands, and the honest triangulation for
# concave loops where a fan from the first corner would leave the
# polygon.
#
# Determinism contract (byte-parity with the Rust twin):
# - the projection drops the |normal| axis with the LARGEST absolute
#   component (ties break toward the earlier axis in x, y, z order)
#   and keeps the remaining two axes in x < y < z cyclic order;
# - the polygon's orientation is the f64 shoelace sign (zero area is
#   a refusal — a degenerate loop never triangulates);
# - an ear is (convex at i: cross > 0) and (no reflex vertex strictly
#   inside the candidate triangle, boundary-inclusive: a reflex
#   vertex ON an edge blocks); candidates scan in index order and the
#   FIRST ear wins, clipping one vertex per pass — no numeric
#   tie-breaks beyond exact f64 comparisons.
# - Hole bridging is NOT implemented (named open): a multi-loop face
#   with holes needs the bridge step before clipping.


def newell_normal_2d(points):
    """The loop's Newell normal (f64, exact same arithmetic as the Rust
    twin: the f32 coordinates are widened once, then f64 throughout)."""
    nx = ny = nz = 0.0
    for i in range(len(points)):
        a = points[i]
        b = points[(i + 1) % len(points)]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    return nx, ny, nz


def _project_axes(normal):
    """The (u, v) projection axes: drop the largest-|component| axis."""
    comps = (abs(normal[0]), abs(normal[1]), abs(normal[2]))
    drop = 0
    for axis in (1, 2):
        if comps[axis] > comps[drop]:
            drop = axis
    axes = [a for a in (0, 1, 2) if a != drop]
    return axes[0], axes[1]


def _cross2(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _point_in_tri(p, a, b, c):
    """Boundary-inclusive containment (the ear test's blocker rule)."""
    d1 = _cross2(a, b, p)
    d2 = _cross2(b, c, p)
    d3 = _cross2(c, a, p)
    has_neg = d1 < 0.0 or d2 < 0.0 or d3 < 0.0
    has_pos = d1 > 0.0 or d2 > 0.0 or d3 > 0.0
    return not (has_neg and has_pos)


def clip_planar_loop(point_indices, points):
    """Triangulate one simple planar polygon loop, deterministically.

    ``point_indices`` is the loop's vertex sequence into ``points`` (3D
    coordinate triples, pre-validated coplanar by the caller); returns
    the triangle list in the loop's winding, or ``None`` when the loop
    is degenerate (fewer than 3 vertices, repeated indices in the
    convex hull sense, or zero projected area). O(n^3) worst case, the
    classic ear search with the fixed first-ear rule.
    """
    n = len(point_indices)
    if n < 3:
        return None
    if len(set(point_indices)) != n:
        return None
    coords = [points[i] for i in point_indices]
    normal = newell_normal_2d(coords)
    u, v = _project_axes(normal)
    poly2d = [(c[u], c[v]) for c in coords]
    area2 = sum(
        _cross2((0.0, 0.0), poly2d[i], poly2d[(i + 1) % n]) for i in range(n)
    ) / 2.0
    if area2 == 0.0:
        return None
    # ensure CCW in the projected plane
    if area2 < 0.0:
        poly2d.reverse()
        order = list(reversed(point_indices))
    else:
        order = list(point_indices)

    out = []
    idx = list(range(n))
    guard = 0
    while len(idx) > 3:
        guard += 1
        if guard > n * n:
            return None  # numeric pathology; fail-closed, never loop
        clipped = False
        m = len(idx)
        for k in range(m):
            i0 = idx[(k - 1) % m]
            i1 = idx[k]
            i2 = idx[(k + 1) % m]
            a, b, c = poly2d[i0], poly2d[i1], poly2d[i2]
            if _cross2(a, b, c) <= 0.0:
                continue  # reflex or collinear: not an ear
            blocker = False
            for j in idx:
                if j in (i0, i1, i2):
                    continue
                if _point_in_tri(poly2d[j], a, b, c):
                    blocker = True
                    break
            if blocker:
                continue
            out.append((order[i0], order[i1], order[i2]))
            idx.pop(k)
            clipped = True
            break
        if not clipped:
            return None  # no ear found: self-intersecting input
    i0, i1, i2 = idx[0], idx[1], idx[2]
    out.append((order[i0], order[i1], order[i2]))
    return out
