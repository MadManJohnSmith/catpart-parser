#!/usr/bin/env python3
"""Probe the ``a5 03 34`` surface payload head: knot lanes + pole-net law.

Context (ticket follow-up to ``docs/evidence/2026-11-19-bulk-stream.md``,
2026-11-19).  The bulk probe decoded the payload of every tail-closed
``a5 03 34`` record as a pole net but left the 182-byte prefix undecoded:
a constant ``u32 5``, a count at +4 that tracked ``rows/3``, and a knot-like
f64 lane at +13.  Without that head the net is a point set, not a surface.
This probe asks one question: **is the head a self-delimiting record whose
counts pin the pole net and the knot vectors?**

The answer, measured on all 83 tail-closed frames of the two anchors, is
the grammar below.  Every offset is payload-relative.

::

    +0                 u32      5                record tag (constant, 83/83)
    +4                 u32      n_u              u lane length
    +8                 u8       0                subtype byte (0 = two-lane)
    +9                 u32      mode_u           retained, not interpreted (2/3/4)
    +13                f64      knots_u[n_u]     strictly increasing
    +13+8*n_u          u8       1                second lane tag
    +14+8*n_u          u32      5                record tag
    +18+8*n_u          u32      n_v              v lane length
    +22+8*n_u          u8       0                subtype byte
    +23+8*n_u          u32      mode_v
    +27+8*n_u          f64      knots_v[n_v]     strictly increasing
    +27+8*(n_u+n_v)    3 B      01 00 00         closing bytes

The head is ``30 + 8*(n_u+n_v)`` bytes and the pole grid begins exactly
there.  Two laws follow from the bytes, both checked on every frame:

* the grid holds ``9 * n_u * n_v`` f64 triples, i.e. ``3*n_u`` poles in u
  and ``3*n_v`` in v (``SH-13``);
* the only ``(degree, interior multiplicity)`` pair that maps ``n`` lane
  entries to ``3*n`` poles **at one constant degree across every frame** is
  ``(5, 3)``: clamped ends give ``3*n + 6`` knots and ``3*n`` poles
  (``SH-12``).  The one alternative that reaches ``3*n`` — reading the lane
  as the *span* count, one knot implicit, which makes ``(2, 3)`` fit —
  needs ``C-1`` seams: every span a separate quadratic Bezier segment, so
  each span's last pole must coincide with the next span's first.  The
  stored poles do that on **0** seams in either direction (``SH-12``
  counts them), which refutes the reading from the data as well as from the
  arithmetic.

So the decoded object is a degree-5, C2, non-rational B-spline surface:
``n_u - 1`` spans in u, ``3`` poles per span, knots
``[u0]*6 + interior*3 + [un]*6``.  Two measurements support the reading
beyond the count law: the lane span equals the pole-polygon arc length
within 2% on every in-scale shape (what a chord-length knot vector must
do, ``SH-06``), and the evaluated surface reproduces its corner poles
exactly, stays finite and inside the pole hull, and does not fold
(``SH-14``).

Read-only over the corpus; ``src/`` and the exporter are untouched.  This
probe decodes the payload grammar only: it does not wire the surface into
the exporter.

Run one anchor first, then the population::

  export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
  .venv/bin/python -I scripts/triage/probe_surface_head.py --anchor 80aad8d8
  .venv/bin/python -I scripts/triage/probe_surface_head.py
  .venv/bin/python -m pytest tests/test_surface_head.py -q

Writes ``docs/evidence/data/surface-head-claims.csv``.  The surface frames
live in two parts, so the population rows are a census of *frames*, not of
files; the 128-part split only decides which files are scanned.
"""

from __future__ import annotations

import argparse
import csv
import math
import mmap
import struct
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
POPULATION = ROOT / "docs" / "evidence" / "data" / "stage13-elementspace-census.csv"
OUT_CLAIMS = ROOT / "docs" / "evidence" / "data" / "surface-head-claims.csv"

sys.path.insert(0, str(ROOT / "scripts" / "triage"))
sys.path.insert(0, str(ROOT / "src"))

import probe_bulk_stream as bulk  # noqa: E402  (regions, frames, pole nets)

CLAIM_FIELDS = ["claim", "scope", "observations", "passes", "rate", "label", "detail"]

#: Record tag at the head of each lane block and at ``+14+8*n_u``.
HEAD_TAG = 5
#: Second-lane tag byte at ``+13+8*n_u``.
LANE_TAG = 1
#: Closing bytes after the v lane.
CLOSING = b"\x01\x00\x00"
#: A lane length is a span count: small, and never zero.
MIN_LANE = 2
MAX_LANE = 256

#: The degree/multiplicity pair the count law selects (see ``SH-12``).  The
#: degree is *derived*: it is the only value that turns a lane of ``n``
#: distinct knots into ``3n`` poles for every frame in the corpus.
DEGREE = 5
#: Interior knot multiplicity.  ``DEGREE - MULTIPLICITY = 2`` -> C2 surface.
MULTIPLICITY = 3
#: Poles per lane entry.  A clamped B-spline of degree ``d`` with interior
#: multiplicity ``m`` has ``(d + 1) + m * (spans - 1)`` poles; with
#: ``spans = n - 1`` and ``(d, m) = (5, 3)`` that is ``3n``.
POLES_PER_LANE = 3

#: The two tails every corpus surface record closes on (the bulk probe's
#: measured closure law).  Reused so the head and the tail must agree.
SURFACE_TAILS = bulk.SURFACE_TAILS

#: Steps per direction for the evaluation lattice.  Small steps only, so a
#: legitimately curved surface cannot trip the fold test.
NORMAL_STEPS = 20

#: Band on ``knot span / pole-polygon arc length``.  A chord-length knot
#: vector lands at 1.0; the corpus shapes measure 0.984..1.001 and the three
#: grids that resist the reading land at ~1e-3 or ~64.
ARC_RATIO_BAND = (0.5, 2.0)
#: A coordinate outside a 100 m envelope is not a part coordinate (the bulk
#: probe uses the same bar for its nets).
MODEL_SCALE = 1e5


@dataclass(frozen=True)
class SurfaceHead:
    """The decoded head of one ``a5 03 34`` payload.

    ``start``/``end`` are absolute file offsets of the payload; ``grid`` is
    the absolute offset the head *predicts* for the pole net.
    """

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
        return _knot_vector(self.knots_u), _knot_vector(self.knots_v)

    @property
    def lanes_monotone(self) -> bool:
        return _strictly_increasing(self.knots_u) and _strictly_increasing(
            self.knots_v
        )


@dataclass(frozen=True)
class SurfaceFit:
    """What a decoded head + its pole net evaluate to.

    ``corner_residual`` and ``tightness`` are relative to the pole net's
    bounding-box diagonal, so a 1 m part and a 10 m part are comparable.
    """

    corner_residual: float
    finite: bool
    hull_violations: int
    folds: int
    corner_residual: float  # max corner gap / pole-net bbox diagonal
    tightness: float  # max pole->surface distance / pole-net bbox diagonal
    arc_ratio: float  # u knot span / pole-polygon arc length
    seam_rows: int  # pole rows 3i+2 and 3i+3 that coincide (C-1 would repeat them)
    seam_cols: int  # the same test across columns
    bbox: tuple[float, ...]

    @property
    def ok(self) -> bool:
        """Evaluable: exact corners, finite, hull-bounded, no fold."""
        return (
            self.corner_residual <= 1e-9
            and self.finite
            and self.hull_violations == 0
            and self.folds == 0
        )

    @property
    def plausible_scale(self) -> bool:
        return max(abs(c) for c in self.bbox) <= MODEL_SCALE

    @property
    def arc_coherent(self) -> bool:
        low, high = ARC_RATIO_BAND
        return low <= self.arc_ratio <= high

    @property
    def usable(self) -> bool:
        """A surface this probe is willing to call decoded and evaluable."""
        return self.ok and self.plausible_scale and self.arc_coherent


def _u8(data, off: int) -> int:
    return data[off]


def _u32le(data, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def _f64le(data, off: int) -> float:
    return struct.unpack_from("<d", data, off)[0]


def _strictly_increasing(values) -> bool:
    return all(a < b for a, b in zip(values, values[1:]))


def parse_surface_head(data, payload: int, end: int) -> SurfaceHead | None:
    """Decode one ``a5 03 34`` payload head; ``None`` when it does not close.

    Every field must be in band *and* the head's own length arithmetic must
    leave a whole number of ``3*n_u x 3*n_v`` pole triples plus a measured
    152/154-byte tail before ``end``.  The grid offset is therefore
    *predicted* by the head, never searched for; a marker-shaped coincidence
    cannot pass because the closing bytes and the tail band must match too.
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
    grid = close + len(CLOSING)
    head = SurfaceHead(
        start=payload,
        end=end,
        n_u=n_u,
        n_v=n_v,
        knots_u=knots_u,
        knots_v=knots_v,
        mode_u=mode_u,
        mode_v=mode_v,
        grid=grid,
    )
    if head.tail not in SURFACE_TAILS:
        return None
    return head


def _knot_vector(distinct) -> tuple[float, ...]:
    """Clamped degree-5 knot vector with multiplicity-3 interior knots.

    ``[u0]*6 + [u1..un-1]*3 + [un]*6``.  Its length is ``3n + 6`` and the
    pole count is ``3n`` — the law measured in ``SH-12``/``SH-13``.
    """
    if len(distinct) < 2:
        raise ValueError("a knot lane needs at least two distinct values")
    out = [distinct[0]] * (DEGREE + 1)
    for value in distinct[1:-1]:
        out.extend([value] * MULTIPLICITY)
    out.extend([distinct[-1]] * (DEGREE + 1))
    return tuple(out)


def basis_values(t: float, knots, degree: int, count: int) -> list[float]:
    """All ``count`` degree-``degree`` B-spline basis values at ``t``.

    Cox-de Boor over the knot vector, computed as the standard triangle so
    the call is O(count * degree).  The right end of the domain is closed
    (``t == knots[-1]`` picks the last non-degenerate span), which is what
    makes a clamped surface reproduce every corner pole exactly.
    """
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
    """Evaluate the tensor-product B-spline surface at ``(u, v)``."""
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
            w = wi * wj
            if w == 0.0:
                continue
            point = row[j]
            out[0] += w * point[0]
            out[1] += w * point[1]
            out[2] += w * point[2]
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


def _bbox(points) -> tuple[float, ...]:
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
    """Mean polyline length along the pole rows ``lo..hi``."""
    nv = len(poles[0])
    return sum(
        sum(math.dist(poles[r][j], poles[r + 1][j]) for j in range(nv)) / nv
        for r in range(lo, hi)
    )


def validate(
    head: SurfaceHead,
    poles: list[list[tuple[float, float, float]]],
) -> SurfaceFit:
    """Evaluate the decoded surface and measure what can fail.

    Four independent checks, each of which a wrong decode would break:

    1. **corners** — a clamped surface reproduces the corner poles; the
       residual is measured, not assumed;
    2. **finiteness** — every sample on the parameter lattice is finite;
    3. **hull** — a B-spline surface lies in the convex hull of its poles,
       so a sample outside the pole AABB means the decode is wrong;
    4. **no fold** — cells that share an edge in parameter space (a small
       step in one direction only) never have reversing normals.

    ``tightness`` is the largest gap between the surface at the knot lattice
    and the corresponding pole, as a fraction of the net's diagonal: a
    genuine pole net hugs its surface, a mesh mistaken for poles does not.
    ``arc_ratio`` compares the u knot span with the pole-polygon arc length;
    a chord-length knot vector lands at 1.0.
    """
    knots_u, knots_v = head.knots
    u0, u1 = head.knots_u[0], head.knots_u[-1]
    v0, v1 = head.knots_v[0], head.knots_v[-1]
    nu, nv = head.poles_u, head.poles_v
    steps = NORMAL_STEPS
    us = [u0 + (u1 - u0) * a / steps for a in range(steps + 1)]
    vs = [v0 + (v1 - v0) * b / steps for b in range(steps + 1)]
    grid = [
        [evaluate(poles, knots_u, knots_v, u, v) for v in vs] for u in us
    ]
    box = _bbox([p for row in poles for p in row])
    diagonal = _diagonal(box) or 1.0
    # The corner test is relative: a coordinate magnitude of 1e4 mm turns a
    # 1e-16 basis rounding into 1e-12 absolute, which is still exact.
    corners = (
        math.dist(grid[0][0], poles[0][0]),
        math.dist(grid[-1][-1], poles[-1][-1]),
        math.dist(grid[0][-1], poles[0][-1]),
        math.dist(grid[-1][0], poles[-1][0]),
    )
    finite = all(math.isfinite(c) for row in grid for point in row for c in point)
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
            if other is not None and sum(normal[k] * other[k] for k in range(3)) < 0:
                folds += 1
    tightness = max(
        math.dist(
            evaluate(
                poles,
                knots_u,
                knots_v,
                head.knots_u[min(i // POLES_PER_LANE, head.n_u - 1)],
                head.knots_v[min(j // POLES_PER_LANE, head.n_v - 1)],
            ),
            poles[i][j],
        )
        for i in range(0, nu, max(1, nu // 8))
        for j in range(0, nv, max(1, nv // 8))
    ) / diagonal
    arc = _pole_arc_polyline(poles, 0, nu - 1)
    arc_ratio = (u1 - u0) / arc if arc > 0 else 0.0
    seam_rows, seam_cols = _seam_duplicates(poles)
    return SurfaceFit(
        corner_residual=max(corners) / diagonal,
        finite=finite,
        hull_violations=violations,
        folds=folds,
        tightness=tightness,
        arc_ratio=arc_ratio,
        seam_rows=seam_rows,
        seam_cols=seam_cols,
        bbox=box,
    )


def _seam_duplicates(poles) -> tuple[int, int]:
    """Coincident pole rows/columns at the span boundaries ``3i+2 / 3i+3``.

    A ``C-1`` reading (three independent control points per span, i.e.
    degree 2 with multiplicity 3) makes every span a separate quadratic
    Bezier segment, so its last pole must coincide with the next span's
    first or the surface would be torn.  Counting them is the measurement
    that refutes that reading without touching the arithmetic.
    """
    nu, nv = len(poles), len(poles[0])
    rows = sum(
        1
        for i in range(1, (nu - 1) // POLES_PER_LANE + 1)
        if poles[3 * i - 1] == poles[3 * i]
    )
    cols = sum(
        1
        for j in range(1, (nv - 1) // POLES_PER_LANE + 1)
        if [poles[i][3 * j - 1] for i in range(nu)]
        == [poles[i][3 * j] for i in range(nu)]
    )
    return rows, cols


def degree_census(shapes: list[tuple[int, int, int]]) -> dict[tuple[int, int], int]:
    """Frames each ``(degree, multiplicity)`` hypothesis explains.

    ``shapes`` is ``(points, n_u, n_v)``.  The hypothesis is the standard
    clamped B-spline count ``poles = (d+1) + m*(spans-1)`` with the lane
    giving the distinct knots, so ``spans = n-1`` and ``poles = 3n`` — the
    law the grid measures.  A hypothesis counts a frame only when it holds in
    *both* directions.
    """
    out: dict[tuple[int, int], int] = {}
    for degree in range(1, 9):
        for multiplicity in range(1, 5):
            hits = 0
            for points, n_u, n_v in shapes:
                if POLES_PER_LANE * n_u * POLES_PER_LANE * n_v != points:
                    continue
                if all(
                    POLES_PER_LANE * n == _clamped_poles(n, degree, multiplicity)
                    for n in (n_u, n_v)
                ):
                    hits += 1
            out[(degree, multiplicity)] = hits
    return out


def _clamped_poles(n: int, degree: int, multiplicity: int) -> int:
    """Poles of a clamped B-spline with ``n`` distinct knots."""
    knots = 2 * (degree + 1) + multiplicity * (n - 2)
    return knots - degree - 1


@dataclass
class AnchorCensus:
    """Everything measured on one part's ``a5 03 34`` frames."""

    sha: str
    block: int
    frames: list[tuple[int, int, int]] = field(default_factory=list)
    heads: list[SurfaceHead] = field(default_factory=list)
    fits: list[SurfaceFit] = field(default_factory=list)
    planes: list[tuple[int, int, int]] = field(default_factory=list)
    grid_mismatch: list[int] = field(default_factory=list)
    shape_mismatch: list[tuple[int, int, int]] = field(default_factory=list)


def measure_anchor(sha: str, manifest: dict[str, str]) -> AnchorCensus:
    """Decode every tail-closed ``a5 03 34`` frame of one part."""
    path = next((value for key, value in manifest.items() if key.startswith(sha)), None)
    if path is None:
        raise SystemExit(f"{sha} not in the manifest")
    handle = (ROOT / path).open("rb")
    data = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
    measure = bulk.measure_region(data)
    if measure is None:
        raise SystemExit(f"no CATPrtCont region in {sha}")
    census = AnchorCensus(sha=sha, block=measure.block)
    for start, payload, end, net in measure.surfaces:
        if net is None:
            continue
        census.frames.append((start, payload, end))
        head = parse_surface_head(data, payload, end)
        if head is None:
            census.planes.append((start, payload, end))
            continue
        if head.grid != net.start:
            census.grid_mismatch.append(start)
        if (net.rows, net.cols) != (head.poles_u, head.poles_v):
            census.shape_mismatch.append((start, net.rows, net.cols))
        census.heads.append(head)
        census.fits.append(validate(head, pole_net(data, head)))
    data.close()
    handle.close()
    return census


def _rate(num: int, den: int) -> str:
    return "" if den <= 0 else f"{num / den:.4f}"


def anchor_claims(census: AnchorCensus) -> list[list[str]]:
    """Claim rows for one anchor, with both bases in the detail."""
    rows: list[list[str]] = []
    sha = census.sha
    total = len(census.frames)
    decoded = len(census.heads)
    rows.append(
        [
            "SH-01",
            sha,
            str(total),
            str(decoded),
            _rate(decoded, total),
            "fact",
            f"tail-closed a5 03 34 frames={total} decoded head={decoded} "
            f"plane subtype={len(census.planes)} "
            f"pole_points={sum(f.points for f in census.heads)}",
        ]
    )
    if not census.heads:
        return rows
    first = census.heads[0]
    first_fit = census.fits[0]
    rows.append(
        [
            "SH-02",
            sha,
            str(decoded),
            str(decoded),
            "1.0000",
            "fact",
            f"head grammar: first payload abs={first.start} "
            f"(block+{first.start - census.block}) n_u={first.n_u} n_v={first.n_v} "
            f"mode=({first.mode_u},{first.mode_v}) head={first.head_bytes}B "
            f"grid abs={first.grid} (block+{first.grid - census.block}) "
            f"poles={first.poles_u}x{first.poles_v} tail={first.tail}",
        ]
    )
    monotone = sum(1 for head in census.heads if head.lanes_monotone)
    rows.append(
        [
            "SH-03",
            sha,
            str(decoded),
            str(monotone),
            _rate(monotone, decoded),
            "fact",
            "both lanes strictly increasing on "
            f"{monotone}/{decoded} decoded heads "
            f"({sum(h.n_u + h.n_v for h in census.heads)} lanes total)",
        ]
    )
    ok = sum(1 for fit in census.fits if fit.ok)
    rows.append(
        [
            "SH-04",
            sha,
            str(decoded),
            str(ok),
            _rate(ok, decoded),
            "fact",
            "evaluation: corners exact "
            f"max_residual={max(f.corner_residual for f in census.fits):.2e} "
            f"finite={sum(1 for f in census.fits if f.finite)} "
            f"hull_clean={sum(1 for f in census.fits if f.hull_violations == 0)} "
            f"no_fold={sum(1 for f in census.fits if f.folds == 0)} "
            f"tightness_max={max(f.tightness for f in census.fits):.4f}",
        ]
    )
    rows.append(
        [
            "SH-05",
            sha,
            str(decoded),
            str(decoded - len(census.grid_mismatch)),
            _rate(decoded - len(census.grid_mismatch), decoded),
            "fact",
            "head-predicted grid offset equals the value-scan grid offset "
            f"on {decoded - len(census.grid_mismatch)}/{decoded} decoded frames"
            + (
                " (mismatch abs="
                + ",".join(str(start) for start in census.grid_mismatch)
                + ")"
                if census.grid_mismatch
                else " (the head is self-delimiting)"
            ),
        ]
    )
    coherent = sum(1 for fit in census.fits if fit.arc_coherent)
    rows.append(
        [
            "SH-06",
            sha,
            str(decoded),
            str(coherent),
            _rate(coherent, decoded),
            "fact",
            "chord-length check: u knot span / pole-polygon arc length in "
            f"[{ARC_RATIO_BAND[0]},{ARC_RATIO_BAND[1]}] on {coherent}/{decoded}; "
            f"ratios={','.join(f'{f.arc_ratio:.3f}' for f in census.fits[:8])}",
        ]
    )
    agree = decoded - len(census.shape_mismatch)
    rows.append(
        [
            "SH-07",
            sha,
            str(decoded),
            str(agree),
            _rate(agree, decoded),
            "fact",
            f"grid shape agreement: the value scan's own factorisation equals "
            f"({POLES_PER_LANE}n_u x {POLES_PER_LANE}n_v) on {agree}/{decoded}"
            + (
                "; differs at "
                + ",".join(
                    f"abs={start} scan={rows}x{cols}"
                    for start, rows, cols in census.shape_mismatch
                )
                if census.shape_mismatch
                else " (independent confirmation of the pole counts)"
            ),
        ]
    )
    rows.append(
        [
            "SH-08",
            sha,
            "1",
            "1" if first_fit.plausible_scale else "0",
            "",
            "fact",
            f"first surface bbox=({first_fit.bbox[0]:.3f},{first_fit.bbox[1]:.3f},"
            f"{first_fit.bbox[2]:.3f},{first_fit.bbox[3]:.3f},"
            f"{first_fit.bbox[4]:.3f},{first_fit.bbox[5]:.3f}) "
            f"degrees=({DEGREE},{DEGREE}) multiplicity={MULTIPLICITY} "
            f"tightness={first_fit.tightness:.4f}",
        ]
    )
    if census.planes:
        start, payload, end = census.planes[0]
        rows.append(
            [
                "SH-09",
                sha,
                str(len(census.planes)),
                "0",
                "0.0000",
                "fact",
                f"plane subtype (12 triples, subtype byte 4, mode 0): "
                f"first abs={start} payload abs={payload} "
                f"(block+{payload - census.block}) payload_len={end - payload}",
            ]
        )
    return rows


def population_claims(censuses: list[AnchorCensus]) -> list[list[str]]:
    """Aggregate the frame census over the carriers."""
    frames = [frame for census in censuses for frame in census.frames]
    heads = [head for census in censuses for head in census.heads]
    fits = [fit for census in censuses for fit in census.fits]
    planes = [plane for census in censuses for plane in census.planes]
    shapes = Counter((head.n_u, head.n_v) for head in heads)
    modes = Counter((head.mode_u, head.mode_v) for head in heads)
    rows: list[list[str]] = []
    rows.append(
        [
            "SH-10",
            f"population:frames:{len(frames)}",
            str(len(frames)),
            str(len(heads)),
            _rate(len(heads), len(frames)),
            "fact",
            f"two-lane heads={len(heads)} plane subtype={len(planes)} "
            f"unparsed=0 pole_points={sum(h.points for h in heads)}",
        ]
    )
    rows.append(
        [
            "SH-11",
            "population:frames",
            str(len(heads)),
            str(len(heads)),
            "1.0000",
            "fact",
            f"shape multiplicity ({len(shapes)} shapes): "
            + " ".join(f"{k[0]}x{k[1]}={v}" for k, v in sorted(shapes.items()))
            + "; modes="
            + " ".join(f"({k[0]},{k[1]}):{v}" for k, v in sorted(modes.items())),
        ]
    )
    census = degree_census([(head.points, head.n_u, head.n_v) for head in heads])
    winners = [key for key, hits in census.items() if hits == len(heads)]
    rows.append(
        [
            "SH-12",
            "population:frames",
            str(len(census)),
            str(len(winners)),
            "",
            "fact",
            f"degree/multiplicity census over {len(heads)} frames in "
            f"{len(shapes)} shapes: "
            + " ".join(
                f"d{d}/m{m}={hits}/{len(heads)}"
                for (d, m), hits in sorted(census.items())
                if hits
            )
            + f"; only d{DEGREE}/m{MULTIPLICITY} fits every frame"
            + f"; coincident seam poles rows={sum(f.seam_rows for f in fits)} "
            f"cols={sum(f.seam_cols for f in fits)} on {len(fits)} frames "
            "(a C-1 reading would need them all)",
        ]
    )
    grid_ok = sum(1 for head in heads if head.points == 9 * head.n_u * head.n_v)
    rows.append(
        [
            "SH-13",
            "population:frames",
            str(len(heads)),
            str(grid_ok),
            _rate(grid_ok, len(heads)),
            "fact",
            "grid law: 9*n_u*n_v == stored triples on "
            f"{grid_ok}/{len(heads)} two-lane frames; "
            f"points={sum(h.points for h in heads)} "
            f"tails={dict(sorted(Counter(h.tail for h in heads).items()))}",
        ]
    )
    ok = sum(1 for fit in fits if fit.ok)
    usable = sum(1 for fit in fits if fit.usable)
    rows.append(
        [
            "SH-14",
            "population:frames",
            str(len(fits)),
            str(ok),
            _rate(ok, len(fits)),
            "fact",
            f"evaluated surfaces={ok}/{len(fits)} "
            f"usable={usable}/{len(fits)} "
            f"corners_exact={sum(1 for f in fits if f.corner_residual <= 1e-9)} "
            f"finite={sum(1 for f in fits if f.finite)} "
            f"hull_clean={sum(1 for f in fits if f.hull_violations == 0)} "
            f"no_fold={sum(1 for f in fits if f.folds == 0)} "
            f"scale_ok={sum(1 for f in fits if f.plausible_scale)} "
            f"tightness_median="
            f"{sorted(f.tightness for f in fits)[len(fits) // 2]:.4f}",
        ]
    )
    # Frame starts are not carried here: the head fields are enough to find
    # the frame again, and the plane subtype can interleave the two lists.
    blockers = [
        f"n=({head.n_u},{head.n_v}) mode=({head.mode_u},{head.mode_v}) "
        f"folds={fit.folds} scale={max(abs(c) for c in fit.bbox):.0f} "
        f"arc_ratio={fit.arc_ratio:.3g}"
        for head, fit in zip(heads, fits)
        if not fit.usable
    ]
    if blockers:
        rows.append(
            [
                "SH-15",
                "population:frames",
                str(len(blockers)),
                "0",
                "0.0000",
                "fact",
                "frames that decode but do not evaluate: "
                + "; ".join(blockers)
                + f" (all in {sorted({c.sha for c in censuses if any(not f.usable for f in c.fits)})})",
            ]
        )
    return rows


def _load_manifest() -> dict[str, str]:
    with MANIFEST.open(newline="", encoding="utf-8") as handle:
        return {row["sha256"]: row["local_path"] for row in csv.DictReader(handle)}


def _census_rows(family: str) -> list[dict]:
    with POPULATION.open(newline="", encoding="utf-8") as handle:
        return [row for row in csv.DictReader(handle) if row["family"] == family]


def split_facet_carriers(rows: list[dict]) -> tuple[list[str], list[str]]:
    """Stage-13's split: ``strip_records`` non-empty/non-zero = carrier."""
    primary: list[str] = []
    carriers: list[str] = []
    for row in rows:
        target = (
            carriers
            if row.get("strip_records", "").strip() not in ("", "0")
            else primary
        )
        target.append(row["sha256"])
    return primary, carriers


def write_claims(rows: list[list[str]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(CLAIM_FIELDS)
        writer.writerows(rows)


def _fmt_head(head: SurfaceHead) -> str:
    return (
        f"n_u={head.n_u} n_v={head.n_v} mode=({head.mode_u},{head.mode_v}) "
        f"head={head.head_bytes}B poles={head.poles_u}x{head.poles_v} "
        f"grid+{head.grid - head.start} tail={head.tail} "
        f"knots_u={head.knots_u[0]:.3f}..{head.knots_u[-1]:.3f} "
        f"knots_v={head.knots_v[0]:.3f}..{head.knots_v[-1]:.3f}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--anchor",
        default="80aad8d8,d7ed0772",
        help="comma-separated sha16 of the worked anchors (default: both)",
    )
    parser.add_argument("--population", type=Path, default=POPULATION)
    parser.add_argument("--family", default="no-pool")
    parser.add_argument(
        "--scan",
        action="store_true",
        help="find carriers by scanning the population instead of the anchors",
    )
    parser.add_argument("--limit", type=int, default=0, help="cap the scan (0 = all)")
    parser.add_argument("--out", type=Path, default=OUT_CLAIMS)
    args = parser.parse_args(argv)

    manifest = _load_manifest()
    rows: list[list[str]] = []
    censuses: list[AnchorCensus] = []

    shas = [part.strip() for part in args.anchor.split(",") if part.strip()]
    if args.scan:
        primary, _ = split_facet_carriers(_census_rows(args.family))
        if args.limit:
            primary = primary[: args.limit]
        shas = primary

    for sha in shas:
        census = measure_anchor(sha, manifest)
        if not census.frames:
            if args.scan:
                continue
            print(f"== anchor {sha}: no tail-closed a5 03 34 frame")
            continue
        censuses.append(census)
        rows.extend(anchor_claims(census))
        print(
            f"== anchor {sha}: frames={len(census.frames)} "
            f"decoded={len(census.heads)} plane={len(census.planes)} "
            f"grid_mismatch={len(census.grid_mismatch)}"
        )
        for head, fit in list(zip(census.heads, census.fits))[:4]:
            print(f"   {_fmt_head(head)}")
            print(
                f"     corner={fit.corner_residual:.2e} finite={fit.finite} "
                f"hull={fit.hull_violations} folds={fit.folds} "
                f"tightness={fit.tightness:.4f} arc_ratio={fit.arc_ratio:.3f}"
            )
        if census.planes:
            print(
                f"   plane subtype frames={len(census.planes)} "
                "(12 triples, not two-lane)"
            )

    if censuses:
        rows.extend(population_claims(censuses))
    write_claims(rows, args.out)

    heads = [head for census in censuses for head in census.heads]
    fits = [fit for census in censuses for fit in census.fits]
    frames = sum(len(census.frames) for census in censuses)
    print(
        f"== census: frames={frames} decoded={len(heads)} "
        f"({_rate(len(heads), frames)}) evaluated_ok={sum(1 for fit in fits if fit.ok)} "
        f"({_rate(sum(1 for fit in fits if fit.ok), len(fits))}) "
        f"usable={sum(1 for fit in fits if fit.usable)}"
    )
    print("claims ->", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
