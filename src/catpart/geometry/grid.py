"""Structured point grids -> **candidate** meshes (E5 and f64-net dialects).

This is the shipped half of ``docs/evidence/2026-11-19-grid-meshing.md``
(the triangulation), joined to the committed measurements of
``docs/evidence/2026-11-19-e5-dialect.md`` (the ``e5 0d`` record law and
its 98 rectangular grids) and ``docs/evidence/2026-11-19-bulk-stream.md``
(the content-prefix f64 allocations).

What is decoded here is the **grid**, not a surface.  A grid is the
largest 3-divisible run of plausible f64le triples in one carrier (an
``e5 0d`` record payload, or the content-prefix f64 allocation), fitted
as ``rows x cols`` by the committed shape law: the row length is the
**largest** divisor whose every row is near-constant in one coordinate
(mean within-row range <= 1% of that axis's span), rows >= 3, cols >= 3,
model scale.  Points are ordered **row-major**: consecutive ``cols``
points form one station row and rows advance with the outer index — the
bytes pin that grouping, and a column-major storage is a different grid
under the same fit (its constant groups are a different length).

Connectivity is an **inference**, never a decoded surface: two triangles
per cell with a consistent winding from the station order, patches
concatenated with disjoint index spaces (no topology join, no welding).
Every summary and warning says so (``connectivity = candidate``).

Fail-closed rules, all measured rather than tuned:

- a run with no ``rows x cols`` shape (fewer than 3 rows or 3 columns)
  is not a grid: profiles, limit boxes and small arrays contribute
  nothing and leave the part's pre-grid classification untouched;
- a grid whose consecutive station rows or consecutive within-row points
  do not advance (a stalled step, the corpus' trailing sentinel blocks)
  is refused;
- a grid whose cells contain a zero-area triangle is refused (the mesh
  never carries a degenerate triangle);
- a grid whose merged cell complex is not manifold is refused;
- the f64-net prefix has no committed dimension, so it must additionally
  fit the conservative fallback: monotone stations and a bounded station
  step ratio.  E5 grids use the committed dimension and are not
  re-tested for monotonicity (a cyclic sweep is a legitimate grid); the
  measurement rides on the summary instead.

The numerical contract is the same as :mod:`catpart.geometry.surface`:
plain f64 arithmetic in a fixed expression order (``sqrt`` of the
squared-difference sum, never ``hypot``/``mul_add``) so the Rust twin's
PLY stays byte-identical.
"""

from __future__ import annotations

import dataclasses
import math
import struct

from catpart.geometry import mesh, store

#: The two-byte marker every admitted ``e5 0d`` record starts with.
E5_MARKER = b"\xe5\x0d"
#: ``e5 0d | flag:u8 | class:u16le | length:u32le | id:u32le``.
E5_HEADER_BYTES = 13
#: A payload longer than this is a misread (the bulk note's bound).
E5_MAX_PAYLOAD = 1 << 20
#: Runs are admitted only with this many chained records (the record law).
E5_MIN_CHAIN = 3

#: A model coordinate: finite, zero allowed, inside the 100 m envelope.
COORD_FLOOR = 1e-6
COORD_CEIL = 1e5
#: A grid needs at least three stations and three sample columns.
MIN_ROWS = 3
MIN_COLS = 3
#: Largest divisor probed for the row length (the committed pole-net bar).
MAX_COLS_PROBE = 256
#: Mean within-row range / axis span bar (the committed 1% bar).
SPREAD_BAR = 0.01

#: A consecutive station/column step smaller than this fraction of the
#: grid's bbox diagonal is a stall (two identical rows/points).
STALL_FRACTION = 1e-9
#: A triangle whose area is below this fraction of diagonal^2 is degenerate.
DEGENERATE_AREA_FRACTION = 1e-12
#: The f64-net prefix fallback: stations must be monotone and the
#: largest/smallest station-centroid step ratio bounded.  E5 grids have
#: a committed dimension and do not go through this fit.
PREFIX_STEP_RATIO = 4.0

#: Refusal classes (the summary's ``refusals`` census).
REFUSE_STALLED_STATIONS = "stalled-stations"
REFUSE_STALLED_COLUMNS = "stalled-columns"
REFUSE_DEGENERATE = "degenerate-cells"
REFUSE_NOT_MANIFOLD = "not-manifold"
REFUSE_NON_MONOTONE = "non-monotone-stations"
REFUSE_NON_UNIFORM = "non-uniform-stations"

#: The summary's connectivity label: this is an inference, not a surface.
CONNECTIVITY = "candidate"

KIND_E5 = "e5"
KIND_PREFIX = "prefix"


@dataclasses.dataclass(frozen=True)
class GridShape:
    """One fitted rectangular reading of a point run (row-major)."""

    rows: int
    cols: int
    station_axis: int
    spread: float


@dataclasses.dataclass(frozen=True)
class GridScan:
    """One part's grid census plus the merged candidate mesh."""

    block: int | None
    carriers: int
    shaped: int
    meshed: int
    refused: int
    refusals: tuple[tuple[str, int], ...]
    duplicate_grids: int
    station_rows: int
    columns: int
    monotone_grids: int
    points: int
    vertices: tuple[tuple[float, float, float], ...]
    triangles: tuple[tuple[int, int, int], ...]

    @property
    def has_mesh(self) -> bool:
        return bool(self.triangles)

    @property
    def has_candidates(self) -> bool:
        """A ``>=3x3`` grid shape exists: the grid path owns the part."""
        return self.shaped > 0


def _u16le(data, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]


def _u32le(data, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def _u32be(data, off: int) -> int:
    return struct.unpack_from(">I", data, off)[0]


def _f64le(data, off: int) -> float:
    return struct.unpack_from("<d", data, off)[0]


def _distance(a, b) -> float:
    """Euclidean distance, plain f64 in a fixed order (the twin's form)."""
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    dz = b[2] - a[2]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _area2(a, b, c) -> float:
    """Twice the triangle area (the surface module's ``_area2`` form)."""
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    cx = uy * vz - uz * vy
    cy = uz * vx - ux * vz
    cz = ux * vy - uy * vx
    return math.sqrt(cx * cx + cy * cy + cz * cz)


def _plausible(value: float) -> bool:
    return math.isfinite(value) and (
        value == 0.0 or COORD_FLOOR <= abs(value) <= COORD_CEIL
    )


def _numeric_run(data, lo: int, hi: int) -> tuple[int, int]:
    """Longest run of plausible f64le values at any byte phase."""
    best_count = 0
    best_start = lo
    for phase in range(8):
        pos = lo + phase
        current = 0
        start = pos
        while pos + 8 <= hi:
            if _plausible(_f64le(data, pos)):
                if current == 0:
                    start = pos
                current += 1
                if current > best_count:
                    best_count = current
                    best_start = start
            else:
                current = 0
            pos += 8
    return best_count, best_start


def _leading_run(data, lo: int, hi: int) -> tuple[int, int]:
    """Longest plausible f64 run that *begins* at ``lo`` (phase 0..7).

    The content-prefix allocation has no length field of its own: it
    starts where the metadata table ends, so the run is the maximal one
    from that start and the scan never searches the whole region for a
    nicer array (the bulk probe's ``prefix_run``).
    """
    best_count = 0
    best_start = lo
    for phase in range(8):
        pos = lo + phase
        count = 0
        while pos + 8 <= hi:
            if not _plausible(_f64le(data, pos)):
                break
            count += 1
            pos += 8
        if count > best_count:
            best_count = count
            best_start = lo + phase
    return best_count, best_start


def _parse_record(data, pos: int, hi: int):
    """``(payload, end, cls)`` of an ``e5 0d`` record at ``pos``, or ``None``."""
    if pos + E5_HEADER_BYTES > hi or bytes(data[pos : pos + 2]) != E5_MARKER:
        return None
    length = _u32le(data, pos + 5)
    end = pos + E5_HEADER_BYTES + length
    if length > E5_MAX_PAYLOAD or end > hi:
        return None
    return pos + E5_HEADER_BYTES, end, _u16le(data, pos + 3)


def _records(data, lo: int, hi: int) -> list[tuple[int, int, int, int]]:
    """Every record of every admitted run in ``[lo, hi)``.

    A run is admitted only when it chains at least ``E5_MIN_CHAIN``
    records and closes on its own end (the committed record law); the
    byte scan resumes after an admitted run, so markers inside payloads
    are never visited as record starts.
    """
    out: list[tuple[int, int, int, int]] = []
    pos = lo
    while pos < hi - E5_HEADER_BYTES:
        first = _parse_record(data, pos, hi)
        if first is None:
            pos += 1
            continue
        run: list[tuple[int, int, int]] = []
        walk = pos
        while walk < hi:
            record = _parse_record(data, walk, hi)
            if record is None:
                break
            run.append(record)
            walk = record[1]
        if len(run) >= E5_MIN_CHAIN:
            out.extend((pos, payload, end, cls) for payload, end, cls in run)
            pos = walk
        else:
            pos += 1
    return out


def _metadata_content(data, block: int, hi: int) -> int | None:
    """The content-stream start after the block's metadata table.

    Port of the bulk probe's validation scan (the table is allowed to
    start anywhere in the header window and must close exactly at
    ``start + total``, its last value naming a ``Cont_`` stream).
    ``None`` when no table validates: the committed bulk probe then
    reads no content stream at all (``content = region end``), so the
    prefix dialect is never invented from arbitrary block bytes.
    """
    for start in range(block, min(hi, block + 8192)):
        if start + 12 > hi:
            break
        total = _u32be(data, start)
        count = _u32be(data, start + 8)
        if not (32 <= total <= 1 << 20 and 1 <= count <= 128):
            continue
        end = start + total
        if end > hi:
            continue
        pos = start + 12
        texts: list[bytes] = []
        ok = True
        for _ in range(count):
            if pos + 14 > end:
                ok = False
                break
            size = _u32be(data, pos)
            value_type = struct.unpack_from(">H", data, pos + 8)[0]
            value_bytes = _u32be(data, pos + 10)
            if size != 14 + value_bytes or pos + size > end:
                ok = False
                break
            if value_type == 2:
                texts.append(bytes(data[pos + 14 : pos + size]))
            pos += size
        if not ok or pos != end:
            continue
        if not texts or b"\x00C\x00o\x00n\x00t\x00_" not in texts[-1]:
            continue
        return end
    return None


def regions(data) -> list[tuple[int, int]]:
    """Every ``CATPrtCont`` region's ``(start, end)`` in block order."""
    blocks = store.valid_blocks(data)
    outer = int.from_bytes(data[8:12], "big") if len(data) >= 12 else 0
    return [
        (blk, store.probe_region(data, blk, blocks, outer))
        for blk, name in blocks
        if name == "CATPrtCont"
    ]


def _ratio(points_axes, spans, n: int, cols: int, axis: int) -> float:
    if spans[axis] <= 0:
        return float("inf")
    rows = n // cols
    spread = 0.0
    for row in range(rows):
        window = points_axes[axis][row * cols : (row + 1) * cols]
        spread += max(window) - min(window)
    return spread / rows / spans[axis]


def fit_shape(points) -> GridShape | None:
    """The committed grid shape: the largest admissible row length.

    ``cols`` is probed from the top down (the pole-net law): every
    candidate row must be near-constant in one coordinate, and the
    **largest** such divisor wins, because a smaller divisor splits a
    row (still constant, but not the row) while a larger one merges
    station rows (no longer constant).  ``None`` when no ``rows >= 3``,
    ``cols >= 3`` reading passes the 1% bar.
    """
    n = len(points)
    if n < MIN_ROWS * MIN_COLS:
        return None
    axes = [[point[k] for point in points] for k in range(3)]
    spans = [max(axis) - min(axis) for axis in axes]
    for cols in range(min(n, MAX_COLS_PROBE), 2, -1):
        if n % cols or n // cols < MIN_ROWS:
            continue
        axis = min(range(3), key=lambda a: _ratio(axes, spans, n, cols, a))
        spread = _ratio(axes, spans, n, cols, axis)
        if spread <= SPREAD_BAR:
            return GridShape(
                rows=n // cols, cols=cols, station_axis=axis, spread=spread
            )
    return None


def _diagonal(points) -> float:
    axes = [[point[k] for point in points] for k in range(3)]
    return _distance(
        (min(axes[0]), min(axes[1]), min(axes[2])),
        (max(axes[0]), max(axes[1]), max(axes[2])),
    )


def _stations(points, shape: GridShape):
    """Station centroids (one per row), in row order."""
    cols = shape.cols
    out = []
    for row in range(shape.rows):
        window = points[row * cols : (row + 1) * cols]
        x = 0.0
        y = 0.0
        z = 0.0
        for point in window:
            x += point[0]
            y += point[1]
            z += point[2]
        out.append((x / cols, y / cols, z / cols))
    return out


def _advance(points, shape: GridShape, eps: float) -> str | None:
    """The stall gate: every station and column step must advance."""
    stations = _stations(points, shape)
    for a, b in zip(stations, stations[1:]):
        if _distance(a, b) <= eps:
            return REFUSE_STALLED_STATIONS
    cols = shape.cols
    for row in range(shape.rows):
        window = points[row * cols : (row + 1) * cols]
        for a, b in zip(window, window[1:]):
            if _distance(a, b) <= eps:
                return REFUSE_STALLED_COLUMNS
    return None


def _station_measure(points, shape: GridShape) -> tuple[bool, float]:
    """``(monotone, largest/smallest station-centroid step ratio)``."""
    stations = _stations(points, shape)
    axis = shape.station_axis
    values = [station[axis] for station in stations]
    monotone = all(b >= a for a, b in zip(values, values[1:])) or all(
        b <= a for a, b in zip(values, values[1:])
    )
    steps = [
        _distance(a, b) for a, b in zip(stations, stations[1:])
    ]
    positive = [step for step in steps if step > 0.0]
    ratio = float("inf")
    if positive:
        ratio = max(positive) / min(positive)
    return monotone, ratio


def _triangulate(points, shape: GridShape, diagonal: float):
    """Two triangles per cell; ``None`` when any cell is degenerate."""
    rows, cols = shape.rows, shape.cols
    floor = DEGENERATE_AREA_FRACTION * diagonal * diagonal
    triangles: list[tuple[int, int, int]] = []
    for i in range(rows - 1):
        for j in range(cols - 1):
            a = i * cols + j
            b = (i + 1) * cols + j
            c = (i + 1) * cols + j + 1
            d = i * cols + j + 1
            if _area2(points[a], points[b], points[c]) <= floor:
                return None
            if _area2(points[a], points[c], points[d]) <= floor:
                return None
            triangles.append((a, b, c))
            triangles.append((a, c, d))
    return triangles


def _points_at(data, start: int, count: int):
    return tuple(
        struct.unpack_from("<3d", data, start + 24 * i) for i in range(count)
    )


def iter_runs(data):
    """Every 3-divisible point run of the part, in the committed scan order.

    Yields ``(kind, start, cls, points, shape)`` — ``shape`` is ``None``
    when the run has no ``>=3x3`` rectangular reading (a profile, a
    limit box, a small array).  The scan order is: the ``CATPrtCont``
    regions in block order, their admitted ``e5 0d`` runs in byte order,
    then the content-prefix f64 allocation of each region.
    """
    for block, hi in regions(data):
        for _record_start, payload, end, cls in _records(data, block, hi):
            count, start = _numeric_run(data, payload, end)
            if count % 3:
                continue
            if count < 3:
                continue
            points = _points_at(data, start, count // 3)
            yield KIND_E5, start, cls, points, fit_shape(points)
        content = _metadata_content(data, block, hi)
        if content is None:
            continue
        count, start = _leading_run(data, content, hi)
        if count % 3:
            continue
        if count < 3:
            continue
        points = _points_at(data, start, count // 3)
        yield KIND_PREFIX, start, None, points, fit_shape(points)


def _admit(points, shape, kind):
    """Run the triangulability gates for one shaped grid.

    Returns ``(triangles, reason, monotone)``.  ``triangles`` is ``None``
    when the grid is refused, with ``reason`` naming the failed gate.
    """
    diagonal = _diagonal(points)
    if diagonal <= 0.0:
        return None, REFUSE_DEGENERATE, False
    stall = _advance(points, shape, STALL_FRACTION * diagonal)
    if stall is not None:
        return None, stall, False
    monotone, step_ratio = _station_measure(points, shape)
    if kind == KIND_PREFIX:
        # The prefix allocation has no committed dimension: the
        # conservative fallback fit applies (monotone stations and a
        # bounded step ratio), exactly as the evidence note records.
        if not monotone:
            return None, REFUSE_NON_MONOTONE, monotone
        if step_ratio > PREFIX_STEP_RATIO:
            return None, REFUSE_NON_UNIFORM, monotone
    triangles = _triangulate(points, shape, diagonal)
    if triangles is None:
        return None, REFUSE_DEGENERATE, monotone
    if not mesh.mesh_stats(triangles).manifold:
        return None, REFUSE_NOT_MANIFOLD, monotone
    return triangles, None, monotone


def scan_part(data) -> GridScan:
    """Census one part's point runs and merge every admitted grid mesh.

    ``carriers`` counts the 3-divisible point runs (profiles included);
    ``shaped`` counts the runs with a ``>=3x3`` grid reading — only those
    make the grid path the part's owner.  A shaped grid that fails a
    gate is counted as refused with its named reason, never emitted.
    """
    region_list = regions(data)
    block = region_list[0][0] if region_list else None
    carriers_count = 0
    shaped = 0
    meshed = 0
    refused = 0
    refusals: dict[str, int] = {}
    duplicate_grids = 0
    station_rows = 0
    columns = 0
    monotone_grids = 0
    points_count = 0
    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    seen: list[tuple[tuple[float, float, float], ...]] = []
    for kind, _start, _cls, points, shape in iter_runs(data):
        carriers_count += 1
        if shape is None:
            continue
        shaped += 1
        if points in seen:
            duplicate_grids += 1
            continue
        seen.append(points)
        cell_triangles, reason, monotone = _admit(points, shape, kind)
        if cell_triangles is None:
            refused += 1
            refusals[reason] = refusals.get(reason, 0) + 1
            continue
        meshed += 1
        station_rows += shape.rows
        columns += shape.cols
        points_count += len(points)
        if monotone:
            monotone_grids += 1
        base = len(vertices)
        vertices.extend(points)
        triangles.extend(
            (a + base, b + base, c + base) for a, b, c in cell_triangles
        )
    return GridScan(
        block=block,
        carriers=carriers_count,
        shaped=shaped,
        meshed=meshed,
        refused=refused,
        refusals=tuple(sorted(refusals.items())),
        duplicate_grids=duplicate_grids,
        station_rows=station_rows,
        columns=columns,
        monotone_grids=monotone_grids,
        points=points_count,
        vertices=tuple(vertices),
        triangles=tuple(triangles),
    )
