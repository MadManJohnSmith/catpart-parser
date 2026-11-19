"""Exact ``a5 03 34`` B-spline surfaces: decode, evaluate, tessellate.

This is the shipped half of ``docs/evidence/2026-11-19-surface-head.md``
(the payload grammar) joined to
``docs/evidence/2026-11-19-surface-tessellation.md`` (the mesh).  The
triage probe stays the analysis tool; nothing here depends on
``scripts/``.

The record is a self-delimiting degree-5, C2, non-rational tensor-product
B-spline surface.  Each lane block names ``n`` distinct knots; the pole
net that follows is exactly ``3*n_u`` by ``3*n_v`` triples, and the only
constant ``(degree, interior multiplicity)`` pair that maps a lane of
``n`` knots to ``3*n`` poles is ``(5, 3)``.  The knot vector is therefore
``[u0]*6 + interior*3 + [un]*6`` (length ``3n + 6``), and the grid begins
exactly after the head (``30 + 8*(n_u + n_v)`` bytes).

The tessellator subdivides each knot span by a bounded adaptive tensor
grid: cells whose centre departs from the bilinear cell by more than
``1e-3`` of the pole-net bounding-box diagonal refine that span (never
the whole patch), up to a fixed per-span and total sample budget.  A
tensor grid has no T-junctions, so every patch is a manifold sheet with
boundary by construction.  Patches are concatenated into one mesh with
disjoint index spaces — no topology join is attempted between records.

The evaluable test is the probe's measured battery: exact corner poles,
finite samples on a 21x21 lattice, containment in the pole hull, no
normal fold, model scale and a chord-length-coherent knot span.  A
surface that fails is not tessellated and is counted, never exported.
"""

from __future__ import annotations

import dataclasses
import math
import struct

from catpart.geometry import mesh, store

#: Marker that seeds the surface scan (A family, flag 0x03, class 0x34).
SURFACE_MARKER = b"\xa5\x03\x34"
#: Class byte of the consolidated freeform surface record.
SURFACE_CLASS = 0x34
#: Record tag at the head of each lane block and at the second lane.
HEAD_TAG = 5
#: Second-lane tag byte after the u lane.
LANE_TAG = 1
#: Closing bytes after the v lane.
CLOSING = b"\x01\x00\x00"
#: A lane length is a distinct-knot count: small, and never zero.
MIN_LANE = 2
MAX_LANE = 256
#: The two measured surface payload tails (the bulk probe's closure law).
SURFACE_TAILS = (152, 154)

#: Degree and interior multiplicity the count law derives from the grid.
DEGREE = 5
MULTIPLICITY = 3
POLES_PER_LANE = 3

#: Plausible model coordinate magnitude (mm), the bulk probe's net band.
NET_FLOOR = 1e-3
NET_CEIL = 1e6
#: A coordinate outside a 100 m envelope is not a part coordinate.
MODEL_SCALE = 1e5
#: ``u knot span / pole-polygon arc length`` band for a chord-length lane.
ARC_RATIO_BAND = (0.5, 2.0)
#: Parameter-lattice steps used by the evaluable battery.
NORMAL_STEPS = 20
#: Corner-pole residual bound, relative to the pole-net diagonal.
CORNER_TOL = 1e-9

#: Maximum chord error as a fraction of the pole-net bbox diagonal.
TOLERANCE_FRACTION = 1e-3
#: Cells per span before the first refinement round.
INITIAL_STEPS = 2
#: Hard per-span subdivision cap (2**MAX_REFINEMENTS cells at most).
MAX_STEPS = 16
#: Refinement rounds before the budget stops the loop.
MAX_ROUNDS = 8
#: Total parameter samples per patch (vertices, not triangles).
MAX_GRID_POINTS = 65_536
#: A triangle whose area is below this fraction of diagonal^2 is degenerate.
DEGENERATE_AREA_FRACTION = 1e-12


@dataclasses.dataclass(frozen=True)
class SurfaceHead:
    """The decoded head of one surface payload; ``grid`` is predicted."""

    start: int
    end: int
    n_u: int
    n_v: int
    knots_u: tuple[float, ...]
    knots_v: tuple[float, ...]
    mode_u: int
    mode_v: int
    grid: int

    @property
    def head_bytes(self) -> int:
        return self.grid - self.start

    @property
    def poles_u(self) -> int:
        return POLES_PER_LANE * self.n_u

    @property
    def poles_v(self) -> int:
        return POLES_PER_LANE * self.n_v

    @property
    def points(self) -> int:
        return self.poles_u * self.poles_v

    @property
    def tail(self) -> int:
        return self.end - (self.grid + 24 * self.points)

    @property
    def knots(self) -> tuple[tuple[float, ...], tuple[float, ...]]:
        return knot_vector(self.knots_u), knot_vector(self.knots_v)

    @property
    def lanes_monotone(self) -> bool:
        return _strictly_increasing(self.knots_u) and _strictly_increasing(
            self.knots_v
        )


@dataclasses.dataclass(frozen=True)
class SurfaceAssessment:
    """The evaluable battery's measurements for one decoded surface."""

    corner_residual: float
    finite: bool
    hull_violations: int
    folds: int
    arc_ratio: float
    bbox: tuple[float, float, float, float, float, float]

    @property
    def plausible_scale(self) -> bool:
        return max(abs(c) for c in self.bbox) <= MODEL_SCALE

    @property
    def arc_coherent(self) -> bool:
        low, high = ARC_RATIO_BAND
        return low <= self.arc_ratio <= high

    @property
    def evaluable(self) -> bool:
        return (
            self.corner_residual <= CORNER_TOL
            and self.finite
            and self.hull_violations == 0
            and self.folds == 0
            and self.plausible_scale
            and self.arc_coherent
        )


@dataclasses.dataclass(frozen=True)
class TessellatedPatch:
    """One surface's triangle sheet (indices are patch-local)."""

    vertices: tuple[tuple[float, float, float], ...]
    triangles: tuple[tuple[int, int, int], ...]
    degenerate: int
    tolerance: float
    grid_points: int
    manifold: bool
    oriented: bool


@dataclasses.dataclass(frozen=True)
class SurfaceScan:
    """One part's surface census plus the merged tessellation."""

    block: int | None
    candidates: int
    decoded: int
    evaluable: int
    tessellated: int
    refused: int
    manifold_patches: int
    vertices: tuple[tuple[float, float, float], ...]
    triangles: tuple[tuple[int, int, int], ...]
    degenerate: int
    tolerances: tuple[float, ...]
    points: int

    @property
    def has_mesh(self) -> bool:
        return bool(self.triangles)


def _u8(data, off: int) -> int:
    return data[off]


def _u32le(data, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def _f64le(data, off: int) -> float:
    return struct.unpack_from("<d", data, off)[0]


def _strictly_increasing(values) -> bool:
    return all(a < b for a, b in zip(values, values[1:]))


def _parse_frame(data, pos: int, hi: int):
    """``(payload, end, class)`` of an A-family frame at ``pos``, or ``None``."""
    if pos < 0 or pos + 8 > hi:
        return None
    family = data[pos]
    if not 0xA5 <= family <= 0xA8:
        return None
    if data[pos + 1] not in (0x03, 0x13, 0x83):
        return None
    width = family - 0xA4
    payload = pos + 7 + width
    length = int.from_bytes(data[pos + 3 : pos + 7], "little")
    end = payload + length
    if payload > hi or end > hi:
        return None
    return payload, end, data[pos + 2]


def _surface_block(data) -> tuple[int, int] | None:
    """The first ``CATPrtCont`` block's ``(start, region_end)``."""
    blocks = store.valid_blocks(data)
    outer = int.from_bytes(data[8:12], "big") if len(data) >= 12 else 0
    for blk, name in blocks:
        if name == "CATPrtCont":
            return blk, store.probe_region(data, blk, blocks, outer)
    return None


def candidate_frames(data) -> list[tuple[int, int, int]]:
    """Every marker-class ``a5 03 34`` frame ``(start, payload, end)``."""
    region = _surface_block(data)
    if region is None:
        return []
    lo, hi = region
    out: list[tuple[int, int, int]] = []
    pos = lo
    while True:
        hit = data.find(SURFACE_MARKER, pos, hi)
        if hit < 0 or hit + 8 > hi:
            return out
        pos = hit + 1
        record = _parse_frame(data, hit, hi)
        if record is None or record[2] != SURFACE_CLASS:
            continue
        out.append((hit, record[0], record[1]))


def parse_surface_head(data, payload: int, end: int) -> SurfaceHead | None:
    """Decode one payload head; ``None`` when its arithmetic does not close.

    The grid offset is *predicted* by the head, never searched for: the
    tag, both lane lengths, both strictly increasing lanes, the closing
    bytes and a measured 152/154-byte tail must all agree.
    """
    if payload + 13 > end:
        return None
    if _u32le(data, payload) != HEAD_TAG:
        return None
    n_u = _u32le(data, payload + 4)
    if not MIN_LANE <= n_u <= MAX_LANE:
        return None
    if _u8(data, payload + 8) != 0:
        return None
    mode_u = _u32le(data, payload + 9)
    lane_u = payload + 13
    if lane_u + 8 * n_u + 14 > end:
        return None
    knots_u = tuple(_f64le(data, lane_u + 8 * i) for i in range(n_u))
    if not _strictly_increasing(knots_u):
        return None
    second = lane_u + 8 * n_u
    if _u8(data, second) != LANE_TAG:
        return None
    if _u32le(data, second + 1) != HEAD_TAG:
        return None
    n_v = _u32le(data, second + 5)
    if not MIN_LANE <= n_v <= MAX_LANE:
        return None
    if _u8(data, second + 9) != 0:
        return None
    mode_v = _u32le(data, second + 10)
    lane_v = second + 14
    if lane_v + 8 * n_v + len(CLOSING) > end:
        return None
    knots_v = tuple(_f64le(data, lane_v + 8 * i) for i in range(n_v))
    if not _strictly_increasing(knots_v):
        return None
    close = lane_v + 8 * n_v
    if bytes(data[close : close + len(CLOSING)]) != CLOSING:
        return None
    head = SurfaceHead(
        start=payload,
        end=end,
        n_u=n_u,
        n_v=n_v,
        knots_u=knots_u,
        knots_v=knots_v,
        mode_u=mode_u,
        mode_v=mode_v,
        grid=close + len(CLOSING),
    )
    if head.tail not in SURFACE_TAILS:
        return None
    return head


def knot_vector(distinct) -> tuple[float, ...]:
    """Clamped degree-5 knots with multiplicity-3 interior values."""
    if len(distinct) < 2:
        raise ValueError("a knot lane needs at least two distinct values")
    out = [distinct[0]] * (DEGREE + 1)
    for value in distinct[1:-1]:
        out.extend([value] * MULTIPLICITY)
    out.extend([distinct[-1]] * (DEGREE + 1))
    return tuple(out)


def basis_values(t: float, knots, degree: int, count: int) -> list[float]:
    """All ``count`` degree-``degree`` basis values at ``t`` (Cox-de Boor)."""
    width = count + degree
    current = [0.0] * width
    for i in range(min(len(knots) - 1, width)):
        if knots[i] <= t < knots[i + 1]:
            current[i] = 1.0
            break
    else:
        for i in range(min(len(knots) - 1, width) - 1, -1, -1):
            if knots[i] < knots[i + 1]:
                current[i] = 1.0
                break
    for p in range(1, degree + 1):
        nxt = [0.0] * width
        for i in range(width - p):
            left = 0.0
            den = knots[i + p] - knots[i]
            if den > 0:
                left = (t - knots[i]) / den * current[i]
            right = 0.0
            den = knots[i + p + 1] - knots[i + 1]
            if den > 0:
                right = (knots[i + p + 1] - t) / den * current[i + 1]
            nxt[i] = left + right
        current = nxt
    return current[:count]


def evaluate(
    poles: list[list[tuple[float, float, float]]],
    knots_u,
    knots_v,
    u: float,
    v: float,
) -> tuple[float, float, float]:
    """Evaluate the tensor-product surface at ``(u, v)``."""
    nu = len(poles)
    nv = len(poles[0])
    bu = basis_values(u, knots_u, DEGREE, nu)
    bv = basis_values(v, knots_v, DEGREE, nv)
    out = [0.0, 0.0, 0.0]
    for i, wi in enumerate(bu):
        if wi == 0.0:
            continue
        row = poles[i]
        for j, wj in enumerate(bv):
            weight = wi * wj
            if weight == 0.0:
                continue
            point = row[j]
            out[0] += weight * point[0]
            out[1] += weight * point[1]
            out[2] += weight * point[2]
    return (out[0], out[1], out[2])


def pole_net(data, head: SurfaceHead) -> list[list[tuple[float, float, float]]]:
    """The ``3*n_u x 3*n_v`` pole matrix the head predicts, row-major."""
    nv = head.poles_v
    return [
        [
            struct.unpack_from("<3d", data, head.grid + 24 * (i * nv + j))
            for j in range(nv)
        ]
        for i in range(head.poles_u)
    ]


def _bbox(points) -> tuple[float, float, float, float, float, float]:
    return (
        min(p[0] for p in points),
        max(p[0] for p in points),
        min(p[1] for p in points),
        max(p[1] for p in points),
        min(p[2] for p in points),
        max(p[2] for p in points),
    )


def _diagonal(box) -> float:
    return math.dist((box[0], box[2], box[4]), (box[1], box[3], box[5]))


def _pole_arc_polyline(poles, lo: int, hi: int) -> float:
    nv = len(poles[0])
    return sum(
        sum(math.dist(poles[r][j], poles[r + 1][j]) for j in range(nv)) / nv
        for r in range(lo, hi)
    )


def assess(head: SurfaceHead, poles) -> SurfaceAssessment:
    """Run the evaluable battery (the surface-head note's four checks)."""
    knots_u, knots_v = head.knots
    u0, u1 = head.knots_u[0], head.knots_u[-1]
    v0, v1 = head.knots_v[0], head.knots_v[-1]
    steps = NORMAL_STEPS
    us = [u0 + (u1 - u0) * a / steps for a in range(steps + 1)]
    vs = [v0 + (v1 - v0) * b / steps for b in range(steps + 1)]
    grid = [
        [evaluate(poles, knots_u, knots_v, u, v) for v in vs] for u in us
    ]
    box = _bbox([p for row in poles for p in row])
    diagonal = _diagonal(box) or 1.0
    corners = (
        math.dist(grid[0][0], poles[0][0]),
        math.dist(grid[-1][-1], poles[-1][-1]),
        math.dist(grid[0][-1], poles[0][-1]),
        math.dist(grid[-1][0], poles[-1][0]),
    )
    finite = all(
        math.isfinite(c) for row in grid for point in row for c in point
    )
    violations = sum(
        1
        for row in grid
        for point in row
        for k in range(3)
        if not (box[2 * k] - 1e-6 <= point[k] <= box[2 * k + 1] + 1e-6)
    )
    normals: dict[tuple[int, int], tuple[float, float, float]] = {}
    for a in range(steps):
        for b in range(steps):
            p00, p01, p10 = grid[a][b], grid[a][b + 1], grid[a + 1][b]
            du = [p01[k] - p00[k] for k in range(3)]
            dv = [p10[k] - p00[k] for k in range(3)]
            normal = (
                du[1] * dv[2] - du[2] * dv[1],
                du[2] * dv[0] - du[0] * dv[2],
                du[0] * dv[1] - du[1] * dv[0],
            )
            length = math.sqrt(sum(c * c for c in normal))
            if length > 0.0:
                normals[(a, b)] = tuple(c / length for c in normal)
    folds = 0
    for (a, b), normal in normals.items():
        for neighbour in ((a, b + 1), (a + 1, b)):
            other = normals.get(neighbour)
            if other is not None and sum(
                normal[k] * other[k] for k in range(3)
            ) < 0:
                folds += 1
    arc = _pole_arc_polyline(poles, 0, len(poles) - 1)
    arc_ratio = (u1 - u0) / arc if arc > 0 else 0.0
    return SurfaceAssessment(
        corner_residual=max(corners) / diagonal,
        finite=finite,
        hull_violations=violations,
        folds=folds,
        arc_ratio=arc_ratio,
        bbox=box,
    )


def _plausible(value: float) -> bool:
    """The bulk decoder's model-coordinate band (zero is legitimate)."""
    return math.isfinite(value) and (
        value == 0.0 or NET_FLOOR <= abs(value) <= NET_CEIL
    )


def plausible_net(poles) -> bool:
    """Every pole is a finite model coordinate (the tail-closed gate).

    A head can parse over a payload whose predicted grid lands on
    non-numeric bytes; the bulk decoder rejects those records because
    its f64 run is not a point net.  Keeping that gate here reproduces
    the measured tail-closed population (63 head-decodable of 83).
    """
    return all(_plausible(c) for row in poles for point in row for c in point)


def _sample_axis(distinct, counts):
    """Sample one parameter axis, recording each segment's knot span."""
    values: list[float] = []
    spans: list[int] = []
    for span, count in enumerate(counts):
        lo, hi = distinct[span], distinct[span + 1]
        step = hi - lo
        for k in range(count):
            values.append(lo + step * k / count)
            spans.append(span)
    values.append(distinct[-1])
    return values, spans


def _refined(counts, errors, tolerance):
    changed = False
    for span, error in enumerate(errors):
        if error > tolerance and counts[span] < MAX_STEPS:
            counts[span] *= 2
            changed = True
    return changed


def _area2(a, b, c) -> float:
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    cx = uy * vz - uz * vy
    cy = uz * vx - ux * vz
    cz = ux * vy - uy * vx
    return math.sqrt(cx * cx + cy * cy + cz * cz)


def tessellate(
    head: SurfaceHead,
    poles,
    tolerance_factor: float = TOLERANCE_FRACTION,
) -> TessellatedPatch | None:
    """Tessellate one evaluable surface; ``None`` when no sane mesh exists.

    A per-patch tensor grid keeps the sheet manifold: subdivisions are
    whole knot spans, so adjacent cells share the same vertices and no
    T-junction is created.  The refinement error is the distance between
    the surface at a cell's parameter centre and the bilinear cell
    centre, checked against ``tolerance_factor * diagonal``.
    """
    knots_u, knots_v = head.knots
    distinct_u, distinct_v = head.knots_u, head.knots_v
    box = _bbox([p for row in poles for p in row])
    diagonal = _diagonal(box) or 1.0
    tolerance = tolerance_factor * diagonal
    counts_u = [INITIAL_STEPS] * (len(distinct_u) - 1)
    counts_v = [INITIAL_STEPS] * (len(distinct_v) - 1)
    best = None
    for _ in range(MAX_ROUNDS):
        us, span_u = _sample_axis(distinct_u, counts_u)
        vs, span_v = _sample_axis(distinct_v, counts_v)
        if len(us) * len(vs) > MAX_GRID_POINTS:
            break
        grid = [
            [evaluate(poles, knots_u, knots_v, u, v) for v in vs] for u in us
        ]
        best = (us, vs, grid)
        errors_u = [0.0] * len(counts_u)
        errors_v = [0.0] * len(counts_v)
        for i in range(len(us) - 1):
            for j in range(len(vs) - 1):
                p00, p10 = grid[i][j], grid[i + 1][j]
                p01, p11 = grid[i][j + 1], grid[i + 1][j + 1]
                middle = (
                    (p00[0] + p10[0] + p01[0] + p11[0]) / 4.0,
                    (p00[1] + p10[1] + p01[1] + p11[1]) / 4.0,
                    (p00[2] + p10[2] + p01[2] + p11[2]) / 4.0,
                )
                centre = evaluate(
                    poles,
                    knots_u,
                    knots_v,
                    (us[i] + us[i + 1]) / 2.0,
                    (vs[j] + vs[j + 1]) / 2.0,
                )
                deviation = math.dist(centre, middle)
                if deviation > errors_u[span_u[i]]:
                    errors_u[span_u[i]] = deviation
                if deviation > errors_v[span_v[j]]:
                    errors_v[span_v[j]] = deviation
        changed = _refined(counts_u, errors_u, tolerance)
        changed = _refined(counts_v, errors_v, tolerance) or changed
        if not changed:
            break
    if best is None:
        return None
    us, vs, grid = best
    nv = len(vs)
    vertices = [grid[i][j] for i in range(len(us)) for j in range(nv)]
    triangles: list[tuple[int, int, int]] = []
    degenerate = 0
    area_floor = DEGENERATE_AREA_FRACTION * diagonal * diagonal
    for i in range(len(us) - 1):
        for j in range(nv - 1):
            a = i * nv + j
            b = (i + 1) * nv + j
            c = (i + 1) * nv + j + 1
            d = i * nv + j + 1
            if _area2(vertices[a], vertices[b], vertices[c]) > area_floor:
                triangles.append((a, b, c))
            else:
                degenerate += 1
            if _area2(vertices[a], vertices[c], vertices[d]) > area_floor:
                triangles.append((a, c, d))
            else:
                degenerate += 1
    if not triangles:
        return None
    stats = mesh.mesh_stats(triangles)
    if not stats.manifold:
        return None
    return TessellatedPatch(
        vertices=tuple(vertices),
        triangles=tuple(triangles),
        degenerate=degenerate,
        tolerance=tolerance,
        grid_points=len(vertices),
        manifold=stats.manifold,
        oriented=stats.oriented,
    )


def scan_part(data, tolerance_factor: float = TOLERANCE_FRACTION) -> SurfaceScan:
    """Census one part and merge every tessellatable surface's mesh.

    A decoded surface that fails the evaluable battery, or whose
    tessellation is not a manifold sheet, is counted as refused and
    contributes no triangle.  Nothing is welded between surfaces: each
    patch keeps its own index space (the task's "no topology joins").
    """
    region = _surface_block(data)
    frames = candidate_frames(data)
    decoded = 0
    evaluable = 0
    tessellated = 0
    refused = 0
    manifold_patches = 0
    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    tolerances: list[float] = []
    degenerate = 0
    points = 0
    for _start, payload, end in frames:
        head = parse_surface_head(data, payload, end)
        if head is None:
            continue
        poles = pole_net(data, head)
        if not plausible_net(poles):
            continue
        decoded += 1
        points += head.points
        if not assess(head, poles).evaluable:
            refused += 1
            continue
        evaluable += 1
        patch = tessellate(head, poles, tolerance_factor)
        if patch is None:
            refused += 1
            continue
        tessellated += 1
        if mesh.mesh_stats(list(patch.triangles)).manifold:
            manifold_patches += 1
        base = len(vertices)
        vertices.extend(patch.vertices)
        triangles.extend(
            (a + base, b + base, c + base) for a, b, c in patch.triangles
        )
        tolerances.append(patch.tolerance)
        degenerate += patch.degenerate
    return SurfaceScan(
        block=None if region is None else region[0],
        candidates=len(frames),
        decoded=decoded,
        evaluable=evaluable,
        tessellated=tessellated,
        refused=refused,
        manifold_patches=manifold_patches,
        vertices=tuple(vertices),
        triangles=tuple(triangles),
        degenerate=degenerate,
        tolerances=tuple(tolerances),
        points=points,
    )
