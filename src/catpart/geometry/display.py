"""Display carriers for a part with **no surface** — never a reconstruction.

This is the shipped half of ``docs/evidence/2026-11-19-no-surface-fallback.md``.
The 120 no-facet parts of the 128-part population open as nothing today:
the nested-store path raises (no pool, no facets), there is no ``a5 03 34``
surface frame and no structured grid triangulates.  Their bytes *do* carry
geometry — the 3-divisible f64 point runs (profiles, limit boxes, sub-grid
arrays) and, in the store bodies, the ``33 3X`` curve records — so the
viewer can show exactly that: a point cloud and the curve segments the
record laws actually pin.

What is emitted here is a **faithful display of the decoded carriers**,
never a surface reconstruction:

- points are the decoded carrier coordinates, in decode order, rounded
  once to f32 (the viewer's array precision);
- a segment is emitted only where a curve record's own law pins two
  endpoints.  Only the ``33 32`` line record does: under the committed
  G2 ``[P][Q][P]+|Q|`` reading the block's first triple is the point P
  and the second is the displacement Q (the layout's trailing float is
  ``|Q|``), so the segment spans ``P -> P+Q``.  The reading is measured,
  not assumed: on the law-holding records of 120 pool-bearing files
  ``P+Q`` lands on a decoded pool vertex 3,503/5,531 = 0.6333 of the
  time at 5e-3 mm, against 11/5,531 for P and 38/5,531 for Q (claim
  DF-03);
- the circle / mid-ring / conic families (``33 37`` / ``33 33`` /
  ``33 38``) expose a center and a radius but **no orientation**, so they
  contribute their decoded center as a point and never a guessed circle
  or conic polyline;
- no triangle is ever emitted, no point is welded and no two points are
  joined unless a curve law carries the pair.  The summary block says
  ``surface = false`` and the warning class is ``no-surface-display``.

Fail-closed rules: a malformed record (short payload, non-finite or
out-of-envelope field, failed direction/length law) contributes nothing
and is counted as skipped; a run whose count is not a multiple of three
contributes nothing; a part with no displayable carrier keeps its
pre-display classification unchanged (the caller re-raises it).

The numerical contract matches the export's: plain f64 arithmetic in a
fixed expression order, and the one ``f64 -> f32`` narrowing is the same
round-to-nearest the Rust twin performs with ``as f32``.
"""

from __future__ import annotations

import dataclasses
import math
import struct

from catpart.geometry import grid
from catpart.geometry.errors import ExportError

#: The display arrays carry f32 coordinates (the viewer's precision).
F32 = struct.Struct("<f")

#: The curve-record families whose decoded payload is displayable at all.
FAMILY_LINE = 0x32
FAMILY_MIDRING = 0x33
FAMILY_CIRCLE = 0x37
FAMILY_CONIC = 0x38

#: The summary block's honesty labels.
KIND = "decoded-carriers"
#: ``surface = false``: this is not a surface render, by construction.
SURFACE = False


@dataclasses.dataclass(frozen=True)
class DisplayScan:
    """One part's display carriers: the point cloud and the pinned segments."""

    block: int | None
    regions: int
    point_runs: int
    run_points: int
    pool_points: int
    curve_records: int
    decoded_curve_records: int
    skipped_curve_records: int
    curve_points: int
    line_records: int
    families: tuple[tuple[int, int], ...]
    points: tuple[tuple[float, float, float], ...]
    segments: tuple[tuple[int, int], ...]

    @property
    def has_carriers(self) -> bool:
        return bool(self.points)

    @property
    def label(self) -> str:
        return label_for(len(self.points), len(self.segments))


def label_for(points: int, segments: int) -> str:
    """The visible, never-a-surface label (shared with the viewer)."""
    point_word = "point" if points == 1 else "points"
    segment_word = "segment" if segments == 1 else "segments"
    return (
        f"no surface — showing {points} {point_word}, "
        f"{segments} curve {segment_word}"
    )


def _f32(value: float) -> float:
    """Round one coordinate to f32 (the viewer's precision), kept as f64."""
    return F32.unpack(F32.pack(value))[0]


def _plausible(value: float) -> bool:
    """A model coordinate: finite, zero allowed, inside the 100 m envelope."""
    return math.isfinite(value) and (
        value == 0.0 or grid.COORD_FLOOR <= abs(value) <= grid.COORD_CEIL
    )


def _regions(data, spans) -> list[tuple[int, int]]:
    """The part's carrier regions: the located store bodies + CATPrtCont.

    The store bodies are where the exporter already trusts the bytes; the
    ``CATPrtCont`` regions are the part container itself (the grid path's
    region law).  Duplicates are collapsed so a nested range is walked once.
    """
    regions = {(int(lo), int(hi)) for lo, hi in spans}
    regions.update(grid.regions(data))
    return sorted(regions)


def _append_point(points, point) -> int | None:
    """Append one decoded point (f32-rounded) and return its index."""
    rounded = (_f32(point[0]), _f32(point[1]), _f32(point[2]))
    if not all(_plausible(value) for value in rounded):
        return None
    points.append(rounded)
    return len(points) - 1


def scan_part(data, spans=(), pool_points=()) -> DisplayScan:
    """Decode one part's display carriers.

    ``spans`` are the located store bodies ``(body_lo, body_hi)`` the
    export path already validated; ``pool_points`` are the store path's
    decoded vertices (the G2 P7 / composite vertices-only success), which
    are displayed first so the point cloud always contains them.  Nothing
    here raises: a record or run that does not decode is skipped and
    counted, and the caller decides whether the part still has a
    classified failure.
    """
    from catpart.brep import curves  # deferred: catpart.brep imports geometry

    regions = _regions(data, spans)
    points: list[tuple[float, float, float]] = []
    segments: list[tuple[int, int]] = []

    pool_count = 0
    for point in pool_points:
        if _append_point(points, point) is not None:
            pool_count += 1

    point_runs = 0
    run_points = 0
    for _kind, _start, _cls, run, _shape in grid.iter_runs(data):
        point_runs += 1
        for point in run:
            if _append_point(points, point) is not None:
                run_points += 1

    records: dict[int, object] = {}
    for lo, hi in regions:
        for record in curves.iter_curve_records(data, lo, hi):
            records.setdefault(record.offset, record)

    family_census: dict[int, int] = {}
    decoded = 0
    skipped = 0
    curve_points = 0
    line_records = 0
    for offset in sorted(records):
        record = records[offset]
        family_census[record.family] = family_census.get(record.family, 0) + 1
        if record.family == FAMILY_LINE:
            segment = _line(record, curves, data, points)
            if segment is None:
                skipped += 1
                continue
            first, second = segment
            curve_points += 2
            line_records += 1
            decoded += 1
            segments.append((first, second))
            continue
        if record.family in (FAMILY_MIDRING, FAMILY_CIRCLE, FAMILY_CONIC):
            center = _centre(record, curves)
            if center is None:
                skipped += 1
                continue
            if _append_point(points, center) is None:
                skipped += 1
                continue
            curve_points += 1
            decoded += 1
            continue
        # 33 36 is out of decode scope (no established payload form).
        skipped += 1

    block = regions[0][0] if regions else None
    return DisplayScan(
        block=block,
        regions=len(regions),
        point_runs=point_runs,
        run_points=run_points,
        pool_points=pool_count,
        curve_records=len(records),
        decoded_curve_records=decoded,
        skipped_curve_records=skipped,
        curve_points=curve_points,
        line_records=line_records,
        families=tuple(sorted(family_census.items())),
        points=tuple(points),
        segments=tuple(segments),
    )


def _line(record, curves, data, points) -> tuple[int, int] | None:
    """The ``P -> P+Q`` segment of a law-holding ``33 32`` record, or None.

    Both committed G2 laws must hold (the P-repeat triple is bit-exact and
    the trailing float is ``|Q|`` within 1e-6); a law-failing record's
    field roles are open (BR3), so it is not displayed.  The endpoints must
    be model-scale and the segment must have a length.
    """
    try:
        block = curves.decode_line(record, data)
    except ExportError:
        return None
    if not (block.p_rep_ok and block.length_ok):
        return None
    floats = block.floats
    p = (floats[0], floats[1], floats[2])
    q = (floats[3], floats[4], floats[5])
    end = (p[0] + q[0], p[1] + q[1], p[2] + q[2])
    if not all(_plausible(value) for value in p):
        return None
    if not all(_plausible(value) for value in end):
        return None
    if floats[9] <= 0.0 or p == end:
        return None
    first = _append_point(points, p)
    if first is None:
        return None
    second = _append_point(points, end)
    if second is None:
        points.pop()
        return None
    return first, second


def _centre(record, curves):
    """The decoded center of a ``33 33`` / ``33 37`` / ``33 38`` record."""
    decoder = {
        FAMILY_MIDRING: curves.decode_midring,
        FAMILY_CIRCLE: curves.decode_circle,
        FAMILY_CONIC: curves.decode_conic,
    }[record.family]
    try:
        arc = decoder(record)
    except ExportError:
        return None
    center = arc.center
    if not all(_plausible(value) for value in center):
        return None
    return center
