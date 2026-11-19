#!/usr/bin/env python3
"""Probe the residual ``a5 03 34`` frames: join, order, and the patch head.

Context (2026-11-19, follow-up to ``docs/evidence/2026-11-19-surface-head.md``
§6).  Five part rows open as BLANK with the report's ``no-evaluable-surface``
class: they carry ``a5 03 34`` marker frames but the shipped two-lane head
``30 + 8*(n_u + n_v)`` never closes, so every frame is skipped and the part
exports nothing.  The surface-head note names two candidate laws for the three
frames that resist *inside* the d7ed0772 anchor:

1. an **allocation <-> frame join law** for the two ``~993 m`` pole runs whose
   knot lanes are bit-identical to in-scale nets (so the run is not one
   surface's poles), and
2. an **ordering law** for the in-scale frame whose ``knot span / pole arc`` is
   ``63.7x`` (row-major vs column-major vs per-span transpose).

This probe asks whether either law recovers the five BLANK parts, and if not,
what the frames actually are.  It measures three things independently:

* **Join** — for every part, the content-prefix allocation (``BS-03``) is
  compared with each frame's predicted pole grid by exact length and bit
  identity.  A join law would have to explain the allocation's bytes as one or
  more frames' poles.
* **Order** — every decoded net is laid out three ways (as stored / whole
  transpose / per-span 3x3 transpose) and scored on the same battery the
  surface-head note uses: corner-pole residual, fold count, chord-length arc
  ratio.
* **Head** — the residual frames' own grammar is decoded from the bytes.  It
  is a second record subtype, not the two-lane one, and it **does** pin: the
  u lane is a distinct-knot count with degree 5 / multiplicity 3, the second
  lane stores its own degree, the pole grid is
  ``3*n_u`` by ``(degree_v + 1) + 3*(n_v - 2)``, and a closing middle byte
  selects rational (coords then weights) or non-rational (coords only).

Read-only over the corpus; ``src/`` and the exporter are untouched.  The
probe is the evidence tool; the shipped evaluator mirrors the pinned law in a
separate change.

Run::

  export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
  export TMPDIR=/home/alan/.cache/t3-tmp
  .venv/bin/python -I scripts/triage/probe_join_order.py
  .venv/bin/python -I scripts/triage/probe_join_order.py --anchor d7ed0772

Writes ``docs/evidence/data/join-order-claims.csv``.
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
OPEN_RATE = ROOT / "docs" / "evidence" / "data" / "open-rate-files.csv"
OUT_CLAIMS = ROOT / "docs" / "evidence" / "data" / "join-order-claims.csv"

sys.path.insert(0, str(ROOT / "scripts" / "triage"))
sys.path.insert(0, str(ROOT / "src"))

import probe_bulk_stream as bulk  # noqa: E402  (regions + prefix allocations)

CLAIM_FIELDS = ["claim", "scope", "observations", "passes", "rate", "label", "detail"]

#: The two record subtypes this probe sees at the head of an ``a5 03 34``
#: payload.  Subtype 0 is the two-lane surface the head note pinned; subtype 4
#: is the patch grammar the five BLANK parts carry.
SUBTYPE_TWO_LANE = 0
SUBTYPE_PATCH = 4

HEAD_TAG = 5
LANE_TAG = 1
CLOSING = b"\x01\x00\x00"
MIN_LANE = 2
MAX_LANE = 256

#: Degree / interior multiplicity of the u direction (both subtypes).
DEGREE_U = 5
MULTIPLICITY = 3
#: The two tails every corpus surface record closes on.
SURFACE_TAILS = (152, 154)

#: Model-coordinate upper band of the bulk probe (mm); there is no lower
#: floor, and the two-lane gate is the tighter 100 m envelope.
NET_CEIL = 1e6
MODEL_SCALE_TWO_LANE = 1e5
MODEL_SCALE_PATCH = 1e6
ARC_RATIO_BAND = (0.5, 2.0)
CORNER_TOL = 1e-9
NORMAL_STEPS = 20


def _u8(data, off: int) -> int:
    return data[off]


def _u32(data, off: int) -> int:
    return int.from_bytes(data[off : off + 4], "little")


def _f64(data, off: int) -> float:
    return struct.unpack_from("<d", data, off)[0]


def _strictly_increasing(values) -> bool:
    return all(a < b for a, b in zip(values, values[1:]))


@dataclass(frozen=True)
class Head:
    """One decoded payload head (both subtypes share the fields used here)."""

    start: int
    end: int
    subtype: int
    n_u: int
    n_v: int
    degree_u: int
    degree_v: int
    knots_u: tuple[float, ...]
    knots_v: tuple[float, ...]
    mode_u: int
    mode_v: int
    rational: bool
    grid: int

    @property
    def poles_u(self) -> int:
        return (self.degree_u + 1) + MULTIPLICITY * (self.n_u - 2)

    @property
    def poles_v(self) -> int:
        return (self.degree_v + 1) + MULTIPLICITY * (self.n_v - 2)

    @property
    def points(self) -> int:
        return self.poles_u * self.poles_v

    @property
    def bytes_per_pole(self) -> int:
        return 32 if self.rational else 24

    @property
    def net_bytes(self) -> int:
        return self.bytes_per_pole * self.points

    @property
    def tail(self) -> int:
        return self.end - (self.grid + self.net_bytes)

    @property
    def head_bytes(self) -> int:
        return self.grid - self.start


def parse_two_lane(data, payload: int, end: int) -> Head | None:
    """The head note's subtype-0 grammar, verbatim."""
    if payload + 13 > end:
        return None
    if _u32(data, payload) != HEAD_TAG:
        return None
    n_u = _u32(data, payload + 4)
    if not MIN_LANE <= n_u <= MAX_LANE:
        return None
    if _u8(data, payload + 8) != SUBTYPE_TWO_LANE:
        return None
    mode_u = _u32(data, payload + 9)
    lane_u = payload + 13
    if lane_u + 8 * n_u + 14 > end:
        return None
    knots_u = tuple(_f64(data, lane_u + 8 * i) for i in range(n_u))
    if not _strictly_increasing(knots_u):
        return None
    second = lane_u + 8 * n_u
    if _u8(data, second) != LANE_TAG:
        return None
    if _u32(data, second + 1) != HEAD_TAG:
        return None
    n_v = _u32(data, second + 5)
    if not MIN_LANE <= n_v <= MAX_LANE:
        return None
    if _u8(data, second + 9) != SUBTYPE_TWO_LANE:
        return None
    mode_v = _u32(data, second + 10)
    lane_v = second + 14
    if lane_v + 8 * n_v + len(CLOSING) > end:
        return None
    knots_v = tuple(_f64(data, lane_v + 8 * i) for i in range(n_v))
    if not _strictly_increasing(knots_v):
        return None
    close = lane_v + 8 * n_v
    if bytes(data[close : close + len(CLOSING)]) != CLOSING:
        return None
    head = Head(
        start=payload,
        end=end,
        subtype=SUBTYPE_TWO_LANE,
        n_u=n_u,
        n_v=n_v,
        degree_u=DEGREE_U,
        degree_v=DEGREE_U,
        knots_u=knots_u,
        knots_v=knots_v,
        mode_u=mode_u,
        mode_v=mode_v,
        rational=False,
        grid=close + len(CLOSING),
    )
    if head.tail not in SURFACE_TAILS:
        return None
    return head


def parse_patch(data, payload: int, end: int) -> Head | None:
    """The subtype-4 patch grammar measured on the five BLANK parts.

    ::

        +0    u32 5                 record tag
        +4    u32 n_u               u distinct-knot count
        +8    u8  4                 subtype
        +9    f64 knots_u[n_u]      strictly increasing
              u8  1                 lane tag
              u32 degree_v          the v direction's degree
              u32 n_v               v distinct-knot count
              u8  4                 subtype
              f64 knots_v[n_v]      strictly increasing
              u8  rational          1 = coords then weights, 0 = coords only
              u8  x                  closing byte (measured 0)
              u8  0                  closing byte

    ``degree_u`` is 5 with interior multiplicity 3 in every frame, exactly as
    in the two-lane grammar.  The pole grid is therefore ``3*n_u`` by
    ``(degree_v + 1) + 3*(n_v - 2)``; the closing middle byte selects the
    32-byte rational layout.  A trailing 152-byte block must close the frame.
    """
    if payload + 22 > end:
        return None
    if _u32(data, payload) != HEAD_TAG:
        return None
    n_u = _u32(data, payload + 4)
    if not MIN_LANE <= n_u <= MAX_LANE:
        return None
    if _u8(data, payload + 8) != SUBTYPE_PATCH:
        return None
    lane_u = payload + 9
    if lane_u + 8 * n_u + 14 > end:
        return None
    knots_u = tuple(_f64(data, lane_u + 8 * i) for i in range(n_u))
    if not _strictly_increasing(knots_u):
        return None
    second = lane_u + 8 * n_u
    if _u8(data, second) != LANE_TAG:
        return None
    degree_v = _u32(data, second + 1)
    if not 1 <= degree_v <= 16:
        return None
    n_v = _u32(data, second + 5)
    if not MIN_LANE <= n_v <= MAX_LANE:
        return None
    if _u8(data, second + 9) != SUBTYPE_PATCH:
        return None
    lane_v = second + 10
    if lane_v + 8 * n_v + 3 > end:
        return None
    knots_v = tuple(_f64(data, lane_v + 8 * i) for i in range(n_v))
    if not _strictly_increasing(knots_v):
        return None
    close = lane_v + 8 * n_v
    closing = bytes(data[close : close + 3])
    if closing[0] != 0x01 or closing[2] != 0x00 or closing[1] not in (0x00, 0x01):
        return None
    head = Head(
        start=payload,
        end=end,
        subtype=SUBTYPE_PATCH,
        n_u=n_u,
        n_v=n_v,
        degree_u=DEGREE_U,
        degree_v=degree_v,
        knots_u=knots_u,
        knots_v=knots_v,
        mode_u=0,
        mode_v=degree_v,
        rational=closing[1] == 1,
        grid=close + 3,
    )
    if head.poles_u < 2 or head.poles_v < 2:
        return None
    if head.tail not in SURFACE_TAILS:
        return None
    return head


def parse_head(data, payload: int, end: int) -> Head | None:
    """Try both grammars; the subtype byte decides, not the outcome."""
    if payload + 9 > end:
        return None
    return parse_two_lane(data, payload, end) or parse_patch(data, payload, end)


def knot_vector(distinct, degree: int) -> tuple[float, ...]:
    if len(distinct) < 2:
        raise ValueError("a knot lane needs at least two distinct values")
    out = [distinct[0]] * (degree + 1)
    for value in distinct[1:-1]:
        out.extend([value] * MULTIPLICITY)
    out.extend([distinct[-1]] * (degree + 1))
    return tuple(out)


def basis_values(t: float, knots, degree: int, count: int) -> list[float]:
    """Cox-de Boor; right-end closed (the same loop the shipped evaluator uses)."""
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


def evaluate(poles, weights, head: Head, u: float, v: float):
    knots_u = knot_vector(head.knots_u, head.degree_u)
    knots_v = knot_vector(head.knots_v, head.degree_v)
    bu = basis_values(u, knots_u, head.degree_u, len(poles))
    bv = basis_values(v, knots_v, head.degree_v, len(poles[0]))
    x = y = z = w = 0.0
    for i, wi in enumerate(bu):
        if wi == 0.0:
            continue
        for j, wj in enumerate(bv):
            if wi * wj == 0.0:
                continue
            point = poles[i][j]
            weight = wi * wj * weights[i][j]
            x += weight * point[0]
            y += weight * point[1]
            z += weight * point[2]
            w += weight
    if w == 0.0:
        raise ZeroDivisionError(f"weight sum vanished at ({u}, {v})")
    return (x / w, y / w, z / w)


def net(data, head: Head, layout: str = "row"):
    """Read the pole matrix in one of the three layouts the probe scores.

    ``row`` is as stored (the head note's row-major reading).  ``col`` is the
    whole transpose.  ``span`` transposes each 3x3 block of poles inside a
    span, the per-span reading a wrong multiplicity would produce.
    """
    nv = head.poles_v
    flat = [
        struct.unpack_from("<3d", data, head.grid + 24 * k) for k in range(head.points)
    ]
    if head.rational:
        base = head.grid + 24 * head.points
        weights_flat = [_f64(data, base + 8 * k) for k in range(head.points)]
    else:
        weights_flat = [1.0] * head.points
    rows = [flat[i * nv : (i + 1) * nv] for i in range(head.poles_u)]
    wrows = [weights_flat[i * nv : (i + 1) * nv] for i in range(head.poles_u)]
    if layout == "row":
        return rows, wrows
    if layout == "col":
        # The same flat triples read column-major under the stored lanes.
        return (
            [[flat[j * len(rows) + i] for j in range(nv)] for i in range(len(rows))],
            [
                [weights_flat[j * len(rows) + i] for j in range(nv)]
                for i in range(len(rows))
            ],
        )
    if layout == "span":
        out = [list(row) for row in rows]
        wout = [list(row) for row in wrows]
        for bi in range(0, len(rows) - 2, 3):
            for bj in range(0, nv - 2, 3):
                for di in range(3):
                    for dj in range(3):
                        out[bi + di][bj + dj] = rows[bi + dj][bj + di]
                        wout[bi + di][bj + dj] = wrows[bi + dj][bj + di]
        return out, wout
    raise ValueError(layout)


def weights_sane(weights) -> bool:
    """A rational net's weights are finite and strictly positive."""
    return all(math.isfinite(w) and w > 0.0 for row in weights for w in row)


def net_plausible(poles) -> bool:
    """Every pole is a finite model coordinate.

    There is no lower floor: a surface pole legitimately sits at ``0`` or at
    ``1e-16`` when the patch crosses its own coordinate plane.  The upper
    band (the bulk probe's ``NET_CEIL``) is what rejects a grid that lands on
    non-numeric bytes; the two-lane head note's four coincidences decode to
    pole magnitudes around ``1e307`` and stay rejected.
    """
    return all(
        math.isfinite(c) and abs(c) <= NET_CEIL
        for row in poles
        for point in row
        for c in point
    )


@dataclass(frozen=True)
class Fit:
    corner: float
    folds: int
    arc_ratio: float
    finite: bool
    hull: int
    bbox: tuple[float, float, float, float, float, float]
    diagonal: float

    @property
    def scale_ok(self) -> bool:
        return max(abs(c) for c in self.bbox) <= MODEL_SCALE_PATCH

    @property
    def arc_ok(self) -> bool:
        low, high = ARC_RATIO_BAND
        return low <= self.arc_ratio <= high

    @property
    def usable(self) -> bool:
        return (
            self.corner <= CORNER_TOL
            and self.finite
            and self.hull == 0
            and self.folds == 0
            and self.scale_ok
            and self.arc_ok
        )


def score(head: Head, poles, weights) -> Fit:
    """The surface-head note's battery, used unchanged to score each layout."""
    knots_u = knot_vector(head.knots_u, head.degree_u)
    knots_v = knot_vector(head.knots_v, head.degree_v)
    u0, u1 = head.knots_u[0], head.knots_u[-1]
    v0, v1 = head.knots_v[0], head.knots_v[-1]
    us = [u0 + (u1 - u0) * a / NORMAL_STEPS for a in range(NORMAL_STEPS + 1)]
    vs = [v0 + (v1 - v0) * b / NORMAL_STEPS for b in range(NORMAL_STEPS + 1)]
    grid = [[evaluate(poles, weights, head, u, v) for v in vs] for u in us]
    flat = [p for row in poles for p in row]
    box = (
        min(p[0] for p in flat),
        max(p[0] for p in flat),
        min(p[1] for p in flat),
        max(p[1] for p in flat),
        min(p[2] for p in flat),
        max(p[2] for p in flat),
    )
    diagonal = math.dist((box[0], box[2], box[4]), (box[1], box[3], box[5])) or 1.0
    corners = (
        math.dist(grid[0][0], poles[0][0]),
        math.dist(grid[-1][-1], poles[-1][-1]),
        math.dist(grid[0][-1], poles[0][-1]),
        math.dist(grid[-1][0], poles[-1][0]),
    )
    finite = all(math.isfinite(c) for row in grid for point in row for c in point)
    hull = sum(
        1
        for row in grid
        for point in row
        for k in range(3)
        if not (box[2 * k] - 1e-6 <= point[k] <= box[2 * k + 1] + 1e-6)
    )
    normals = {}
    for a in range(NORMAL_STEPS):
        for b in range(NORMAL_STEPS):
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
    nv = len(poles[0])
    arc = sum(
        sum(math.dist(poles[r][j], poles[r + 1][j]) for j in range(nv)) / nv
        for r in range(len(poles) - 1)
    )
    return Fit(
        corner=max(corners) / diagonal,
        folds=folds,
        arc_ratio=(u1 - u0) / arc if arc > 0 else 0.0,
        finite=finite,
        hull=hull,
        bbox=box,
        diagonal=diagonal,
    )


@dataclass
class PartCensus:
    sha: str
    path: str
    frames: list[tuple[int, int, int]] = field(default_factory=list)
    heads: list[Head] = field(default_factory=list)
    unparsed: list[int] = field(default_factory=list)
    orders: Counter = field(default_factory=Counter)
    fits: list[Fit] = field(default_factory=list)
    refused: list[tuple[int, str]] = field(default_factory=list)
    prefix_doubles: int = 0
    prefix_bytes: int = 0
    prefix_join: str = "no-prefix-allocation"
    prefix_frame: int | None = None
    prefix_copies: int = 0
    prefix_offset: int = 0

    @property
    def subtypes(self) -> Counter:
        return Counter(head.subtype for head in self.heads)


def manifest_paths() -> dict[str, str]:
    with MANIFEST.open(newline="", encoding="utf-8") as handle:
        return {row["sha256"]: row["local_path"] for row in csv.DictReader(handle)}


def blank_parts() -> list[tuple[str, str]]:
    """The report's ``no-evaluable-surface`` BLANK rows (the five to recover)."""
    with OPEN_RATE.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [
        (row["sha16"], row["path"])
        for row in rows
        if row["open kind"] == "BLANK" and row["report class"] == "no-evaluable-surface"
    ]


def part_region(data):
    return bulk.measure_region(data)


def measure(sha: str, path: str) -> PartCensus:
    census = PartCensus(sha=sha, path=path)
    handle = (ROOT / path).open("rb")
    data = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
    try:
        region = part_region(data)
        prefix = None if region is None else region.prefix
        if region is not None and prefix is not None:
            census.prefix_doubles = prefix.points * 3
            census.prefix_bytes = 24 * prefix.points
            census.prefix_offset = prefix.start - region.block
            census.prefix_join = "allocation-present"
        from catpart.geometry import surface as shipped

        for start, payload, end in shipped.candidate_frames(data):
            census.frames.append((start, payload, end))
            head = parse_head(data, payload, end)
            if head is None:
                census.unparsed.append(start)
                continue
            census.heads.append(head)
            if prefix is not None:
                allocation = bytes(
                    data[prefix.start : prefix.start + census.prefix_bytes]
                )
                frame_bytes = bytes(data[head.grid : head.grid + head.net_bytes])
                if frame_bytes and allocation.startswith(frame_bytes):
                    if len(allocation) % len(frame_bytes) == 0:
                        census.prefix_frame = start
                        census.prefix_copies = len(allocation) // len(frame_bytes)
                        census.prefix_join = "prefix-is-k-frame-grids"
            if not net_plausible(net(data, head)[0]):
                census.refused.append((start, "implausible-pole"))
                continue
            for layout in ("row", "col", "span"):
                poles, weights = net(data, head, layout)
                if not weights_sane(weights):
                    census.orders[(layout, "weights")] += 1
                    if layout == "row":
                        census.refused.append((start, "weights"))
                    continue
                try:
                    fit = score(head, poles, weights)
                except ZeroDivisionError:
                    census.orders[(layout, "zero")] += 1
                    continue
                census.orders[(layout, fit.usable)] += 1
                if layout == "row":
                    census.fits.append(fit)
                    if not fit.usable:
                        census.refused.append((start, "battery"))
    finally:
        data.close()
        handle.close()
    return census


def join_claim(census: PartCensus) -> list[str]:
    """Allocation <-> frame join: exact length and bit identity."""
    if census.prefix_bytes == 0:
        return [
            "JO-02",
            census.sha,
            "0",
            "0",
            "",
            "fact",
            "no content-prefix allocation (bulk measure_region prefix=None); "
            "the allocation<->frame join law has no input on this part",
        ]
    matched = "0" if census.prefix_frame is None else "1"
    rate = "" if census.prefix_frame is None else "1.0000"
    return [
        "JO-02",
        census.sha,
        str(census.prefix_bytes),
        matched,
        rate,
        "fact",
        f"prefix allocation={census.prefix_bytes}B at block+{census.prefix_offset} "
        f"({census.prefix_doubles} doubles); "
        + (
            f"bit-identical to frame abs={census.prefix_frame}'s predicted grid, "
            f"{census.prefix_copies} copies (allocation = {census.prefix_copies} x "
            "frame net)"
            if census.prefix_frame is not None
            else "no frame's predicted net is a bit-prefix of it"
        ),
    ]


def part_claims(census: PartCensus) -> list[list[str]]:
    rows: list[list[str]] = []
    rows.append(
        [
            "JO-01",
            census.sha,
            str(len(census.frames)),
            str(len(census.heads)),
            ""
            if not census.frames
            else f"{len(census.heads) / len(census.frames):.4f}",
            "fact",
            f"frames={len(census.frames)} heads={len(census.heads)} "
            f"subtypes={dict(census.subtypes)} unparsed={len(census.unparsed)} "
            f"refused={len(census.refused)} prefix={census.prefix_join}",
        ]
    )
    rows.append(join_claim(census))
    usable = sum(1 for fit in census.fits if fit.usable)
    rows.append(
        [
            "JO-03",
            census.sha,
            str(len(census.fits)),
            str(usable),
            "" if not census.fits else f"{usable / len(census.fits):.4f}",
            "fact",
            "orders: row="
            + str(dict((k[1], v) for k, v in census.orders.items() if k[0] == "row"))
            + " col="
            + str(dict((k[1], v) for k, v in census.orders.items() if k[0] == "col"))
            + " span="
            + str(dict((k[1], v) for k, v in census.orders.items() if k[0] == "span")),
        ]
    )
    if census.fits:
        folds = sum(fit.folds for fit in census.fits)
        arc = [fit.arc_ratio for fit in census.fits if fit.arc_ok]
        rows.append(
            [
                "JO-04",
                census.sha,
                str(len(census.fits)),
                str(sum(1 for fit in census.fits if fit.folds == 0)),
                "",
                "fact",
                f"row-major battery: folds={folds} "
                f"corner_max={max(fit.corner for fit in census.fits):.2e} "
                f"arc_in_band={len(arc)}/{len(census.fits)} "
                f"scale_ok={sum(1 for fit in census.fits if fit.scale_ok)}/"
                f"{len(census.fits)}",
            ]
        )
    return rows


def population_claims(censuses: list[PartCensus]) -> list[list[str]]:
    rows: list[list[str]] = []
    frames = sum(len(c.frames) for c in censuses)
    heads = sum(len(c.heads) for c in censuses)
    fits = [fit for c in censuses for fit in c.fits]
    subtypes = Counter()
    for census in censuses:
        subtypes.update(census.subtypes)
    rows.append(
        [
            "JO-05",
            f"population:parts:{len(censuses)}",
            str(frames),
            str(heads),
            "" if not frames else f"{heads / frames:.4f}",
            "fact",
            f"the BLANK population carries {frames} marker frames, {heads} with a "
            f"decodable head; subtypes={dict(subtypes)}; "
            f"unparsed={sum(len(c.unparsed) for c in censuses)}",
        ]
    )
    row_ok = sum(c.orders[("row", True)] for c in censuses)
    col_ok = sum(c.orders[("col", True)] for c in censuses)
    span_ok = sum(c.orders[("span", True)] for c in censuses)
    total = sum(
        census.orders[(layout, outcome)]
        for census in censuses
        for layout in ("row", "col", "span")
        for outcome in (True, False, "weights", "zero")
    )
    row_total = sum(
        census.orders[("row", True)] + census.orders[("row", False)]
        for census in censuses
    )
    rows.append(
        [
            "JO-06",
            "population:orders:row",
            str(row_total),
            str(row_ok),
            "" if not row_total else f"{row_ok / row_total:.4f}",
            "fact",
            f"layout wins: row={row_ok}/{row_total} col={col_ok}/{row_total} "
            f"span={span_ok}/{row_total} over {total} scored layouts (a layout "
            f"counts when the battery is usable: "
            "corner<=1e-9, folds=0, hull=0, model scale, arc in [0.5,2])",
        ]
    )
    usable = sum(1 for fit in fits if fit.usable)
    rows.append(
        [
            "JO-07",
            "population:frames",
            str(len(fits)),
            str(usable),
            "" if not fits else f"{usable / len(fits):.4f}",
            "fact",
            "decoded head law: grid = poles_u x poles_v from the stored lanes "
            "(patch: 3*n_u x ((degree_v+1)+3*(n_v-2))); "
            f"row-major usable={usable}/{len(fits)} "
            f"folds={sum(f.folds for f in fits)} "
            f"corner_max={max((f.corner for f in fits), default=0.0):.2e} "
            f"arc_range=("
            f"{min((f.arc_ratio for f in fits), default=0.0):.3f},"
            f"{max((f.arc_ratio for f in fits), default=0.0):.3f})",
        ]
    )
    prefixes = [c for c in censuses if c.prefix_bytes]
    rows.append(
        [
            "JO-08",
            "population:join",
            str(len(censuses)),
            str(len(prefixes)),
            f"{len(prefixes) / len(censuses):.4f}" if censuses else "",
            "fact",
            "parts with a content-prefix allocation: "
            + (", ".join(f"{c.sha}:{c.prefix_bytes}B" for c in prefixes) or "none")
            + " — the join law is not the blocker for the rest",
        ]
    )
    return rows


def _fmt_head(head: Head) -> str:
    return (
        f"subtype={head.subtype} n=({head.n_u},{head.n_v}) "
        f"deg=({head.degree_u},{head.degree_v}) rational={head.rational} "
        f"poles={head.poles_u}x{head.poles_v} head={head.head_bytes}B tail={head.tail}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--anchor",
        default="",
        help="comma-separated sha16 to measure instead of the BLANK population",
    )
    parser.add_argument("--out", type=Path, default=OUT_CLAIMS)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)

    paths = manifest_paths()
    if args.anchor:
        shas = [part.strip() for part in args.anchor.split(",") if part.strip()]
        targets = [
            (sha, next(path for key, path in paths.items() if key.startswith(sha)))
            for sha in shas
        ]
    else:
        targets = blank_parts()
    targets = [
        (sha, next(path for key, path in paths.items() if key.startswith(sha)))
        for sha, _ in targets
    ]
    if args.limit:
        targets = targets[: args.limit]

    rows: list[list[str]] = []
    censuses: list[PartCensus] = []
    for sha, path in targets:
        census = measure(sha, path)
        censuses.append(census)
        rows.extend(part_claims(census))
        print(
            f"== {sha} frames={len(census.frames)} heads={len(census.heads)} "
            f"subtypes={dict(census.subtypes)} refused={len(census.refused)} "
            f"prefix={census.prefix_join}"
        )
        for head, fit in list(zip(census.heads, census.fits))[:3]:
            print(f"   {_fmt_head(head)}")
            print(
                f"     corner={fit.corner:.2e} folds={fit.folds} "
                f"arc={fit.arc_ratio:.3f} scale={max(abs(c) for c in fit.bbox):.0f}"
            )
    if censuses:
        rows.extend(population_claims(censuses))
    write_claims(rows, args.out)
    fits = [fit for c in censuses for fit in c.fits]
    print(
        f"== population: parts={len(censuses)} "
        f"frames={sum(len(c.frames) for c in censuses)} "
        f"heads={sum(len(c.heads) for c in censuses)} "
        f"usable={sum(1 for fit in fits if fit.usable)}/{len(fits)}"
    )
    print("claims ->", args.out)
    return 0


def write_claims(rows: list[list[str]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(CLAIM_FIELDS)
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
