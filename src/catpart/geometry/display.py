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
- the bag-rep payload's **count-framed f32 point arrays** (source label
  ``bagrep-f32-points``) contribute their declared triples as points.
  This is the R-BAG-P lever of ``docs/evidence/2026-11-19-bagrep.md``:
  a ``u32le V`` (``V % 3 == 0``, a plausible float count) followed by
  ``V`` clean f32 at one 4-byte frame, ending where the clean run ends.
  The arrays carry coordinates only — no facet record, no triple index
  list, no implicit strip — so they are never connected (the note's
  measured negative for the mesh lever);
- no triangle is ever emitted, no point is welded and no two points are
  joined unless a curve law carries the pair.  The summary block says
  ``surface = false`` and the warning class is ``no-surface-display``.

Fail-closed rules: a malformed record (short payload, non-finite or
out-of-envelope field, failed direction/length law) contributes nothing
and is counted as skipped; a run whose count is not a multiple of three
contributes nothing; a framed array must pass every gate of the
count-first measurement (declared count, all-clean block, block ends
where the clean run ends, non-zero share, no fill run) or contributes
nothing; a part with no displayable carrier keeps its pre-display
classification unchanged (the caller re-raises it).

The numerical contract matches the export's: plain f64 arithmetic in a
fixed expression order, and the one ``f64 -> f32`` narrowing is the same
round-to-nearest the Rust twin performs with ``as f32``.
"""

from __future__ import annotations

import dataclasses
import math
import re
import struct
from array import array
from itertools import accumulate

from catpart.geometry import grid, store
from catpart.geometry.errors import ExportError

#: The display arrays carry f32 coordinates (the viewer's precision).
F32 = struct.Struct("<f")
U32 = struct.Struct("<I")

#: The bag-rep payload containers the count-framed arrays live in
#: (the ``probe_bagrep`` payload family; the arrays are written inside
#: these blocks, not in the ``CATPrtCont`` stream the grid path walks).
BAGREP_PAYLOAD_BLOCKS = (
    "CATStdCont",
    "CATSeeBodyCont",
    "CATBRepModeContainer",
    "CGMGeom",
    "CATCGRCont",
)
#: Count-first framing bounds from the bag-rep measurement.
BAGREP_MAX_FLOATS = 3_000_000
#: Largest payload region the count-first scan walks.  The scan builds
#: clean-f32 prefix sums over the region; on the corpus's 227 MB parts
#: that is not tractable, and every measured array lives in a small
#: payload region (the 69 BLANK rows' largest is 553,832 B).  A larger
#: region is skipped fail-closed (it contributes nothing).
BAGREP_MAX_REGION = 4 * 1024 * 1024
BAGREP_MIN_NONZERO = 0.5
BAGREP_MAX_CONST_RUN = 64
#: The clean-f32 window the framing test uses (the probe's pool-scale
#: bound); the stricter display envelope is applied per point after.
BAGREP_VALUE_FLOOR = 1e-6
BAGREP_VALUE_CEIL = 1e6

#: The curve-record families whose decoded payload is displayable at all.
FAMILY_LINE = 0x32
FAMILY_MIDRING = 0x33
FAMILY_CIRCLE = 0x37
FAMILY_CONIC = 0x38

#: The empty-scan fallback's 12-byte f32 point-run law (the missing-store
#: census measurement, ``missing_store_census_probe.point_runs``): a
#: triple is a run member when finite and inside the (1e-2, 1e5) envelope
#: (no near-zero coordinates — the measured law, stricter than the display
#: envelope), runs chain at exactly the 12-byte stride, and a run counts
#: from 3 triples.  It applies ONLY when every primary carrier came up
#: empty, over the body/geometry blocks' payload regions (bounded per
#: region).
F32_RUN_FLOOR = 1e-2
F32_RUN_CEIL = 1e5
F32_RUN_MIN_TRIPLES = 3
F32_SCAN_MAX_REGION = 16 * 1024 * 1024
#: The parametric blocks the fallback never reads (ticket #69).  These
#: blocks are the part tree / feature parameters; the runs law was
#: measured only in body and geometry containers (CATSeeBodyCont 57,
#: CATBRepModeContainer 11, CATStdCont 9, CGMGeom 6 — 0/83 census files
#: in CATPrtCont).  A part whose only "runs" live here has no display
#: carrier, not a point cloud: the McLaren Senna's 244,817 points were
#: 244,811 f32 triples of CATPrtCont tessellation cache, read as runs.
F32_RUN_SKIP_BLOCKS = ("CATPrtCont", "CATProdCont", "CATMechProdCont")

#: The summary block's honesty labels.
KIND = "decoded-carriers"
#: The added source label for the bag-rep count-framed f32 arrays.
SOURCE_BAGREP = "bagrep-f32-points"
#: The added source label for the empty-scan f32 point-run fallback.
SOURCE_F32_RUNS = "store-f32-points"
#: ``surface = false``: this is not a surface render, by construction.
SURFACE = False

#: The feature/spec-tree block's honesty label: the tree is a display
#: of the part's parametric records, never geometry (no triangle, no
#: point, no segment comes from it and the honest open rate does not
#: credit it).
FEATURE_KIND = "feature-tree-only"
#: The feature-tree block's source label (the framing the names sit in).
SOURCE_FEATURE_TREE = "catprtcont-feature-tokens"
#: The part-container token the kind law names the part marker (the
#: container-table measurement; ``CATMechProdCont`` sits next to it on
#: two corpus parts and ``CATProdCont`` marks products).
CONTAINER_TOKEN = b"CATPrtCont"
#: The measured feature-type vocabulary (the audit probe's shipped
#: subset, ``scripts/triage/probe_w4_feature_tree.py``): every type
#: carries >= 1 length-framed occurrence in the BLANK population.  The
#: parameter-type family (``Volume``/``Density``/``Area``/``Mass`` —
#: mass-properties headers like ``07 Volume 08 Density``) is excluded:
#: the framing alone cannot tell a feature instance from a parameter
#: header, and the parameter family appears in 51/51 files as a block,
#: not a feature.
FEATURE_TYPES = (
    "Axis",
    "Boundary",
    "Chamfer",
    "Circle",
    "Curve",
    "EdgeFillet",
    "Hole",
    "Line",
    "Mirror",
    "Offset",
    "Pad",
    "Pattern",
    "Plane",
    "Point",
    "Pocket",
    "Rib",
    "Sketch",
)
#: The feature-name framing: a length byte ``L`` (4..40) followed by
#: exactly ``L - 1`` ASCII name bytes — the writer's ``len = strlen +
#: 1`` layout (``00 07 Sketch``, ``05 Pad1``, ``09 Sketch.1``,
#: ``0b EdgeFillet``).  The candidate regex runs the C-level scan; the
#: framing and full-name validation runs per candidate.
FEATURE_CANDIDATE_RE = re.compile(rb"[\x04-\x28]([A-Z][A-Za-z0-9_.]{2,38})")
_FEATURE_INSTANCE_RE = re.compile(
    r"^(" + "|".join(re.escape(t) for t in FEATURE_TYPES) + r")(?:\.\d+|\d+)?$"
)


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
    bagrep_regions: int
    bagrep_arrays: int
    bagrep_floats: int
    bagrep_points: int
    bagrep_skipped: int
    points: tuple[tuple[float, float, float], ...]
    segments: tuple[tuple[int, int], ...]
    f32_runs: int = 0
    f32_points: int = 0

    @property
    def has_carriers(self) -> bool:
        return bool(self.points)

    @property
    def sources(self) -> tuple[str, ...]:
        """The non-empty source labels behind the displayed points."""
        names = []
        if self.pool_points or self.run_points or self.curve_points:
            names.append(KIND)
        if self.bagrep_points:
            names.append(SOURCE_BAGREP)
        if self.f32_points:
            names.append(SOURCE_F32_RUNS)
        return tuple(names)

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


@dataclasses.dataclass(frozen=True)
class FeatureTreeScan:
    """One part's feature/spec tree: the framed feature-type names.

    ``features`` are ``(type, count, first_offset)`` triples in
    first-occurrence (byte) order — the writer emits the feature
    records in creation order, so the byte order approximates the spec
    tree's order.  ``containers`` is the ``CATPrtCont`` token count
    (the kind law's part marker).  Nothing here is geometry: the scan
    names records, it does not decode coordinates.
    """

    containers: int
    features: tuple[tuple[str, int, int], ...]
    feature_names: int

    @property
    def has_tree(self) -> bool:
        return self.containers > 0 or bool(self.features)

    def block(self) -> dict:
        """The summary's additive ``feature_tree`` block (integer and
        string fields only — the port's block compares parsed-document
        equal)."""
        return {
            "source": SOURCE_FEATURE_TREE,
            "kind": FEATURE_KIND,
            "surface": False,
            "containers": {"catprtcont": self.containers},
            "features": [
                {"type": typ, "count": count, "first_offset": offset}
                for typ, count, offset in self.features
            ],
            "feature_names": self.feature_names,
        }


def _count_token(data, token: bytes) -> int:
    """Count ``token``'s occurrences (mmap has no ``bytes.count``)."""
    count = 0
    pos = data.find(token)
    while pos >= 0:
        count += 1
        pos = data.find(token, pos + 1)
    return count


def scan_feature_tree(data) -> FeatureTreeScan:
    """Decode one part's feature/spec-tree names.

    The whole file is scanned for the writer's length-framed ASCII
    names: a length byte ``L`` (4..40) followed by exactly ``L - 1``
    printable-ASCII bytes whose FULL text matches one of the pinned
    :data:`FEATURE_TYPES` (instance suffixes ``.N`` / ``N`` allowed) —
    the framing measured on the anchors (``00 07 Sketch``, ``05 Pad1``,
    ``09 Sketch.1``, ``0b EdgeFillet``; the audit probe measures every
    shipped type at >= 1 framed occurrence).  A name records its type,
    the count of its framed occurrences and its first offset; the
    container row is the ``CATPrtCont`` token count.

    The names live in the parametric streams outside the named
    containers (289/289 measured inside no ``CATPrtCont`` region), so
    the scan is framing-scoped, not region-scoped — and it is a name
    census only: no coordinate is decoded, no geometry is claimed.
    """
    containers = _count_token(data, CONTAINER_TOKEN)
    found: dict[str, list[int]] = {}
    total = 0
    for match in FEATURE_CANDIDATE_RE.finditer(data):
        name = match.group(1)
        length = data[match.start()]
        if length != len(name) + 1:
            continue
        text = name.decode("ascii")
        instance = _FEATURE_INSTANCE_RE.match(text)
        if instance is None:
            continue
        typ = text[: instance.end(1)]
        slot = found.get(typ)
        if slot is None:
            found[typ] = [1, match.start() + 1]
        else:
            slot[0] += 1
        total += 1
    features = tuple(
        (typ, count, offset)
        for typ, (count, offset) in sorted(
            found.items(), key=lambda item: item[1][1]
        )
    )
    return FeatureTreeScan(
        containers=containers, features=features, feature_names=total
    )


def _f32(value: float) -> float:
    """Round one coordinate to f32 (the viewer's precision), kept as f64."""
    return F32.unpack(F32.pack(value))[0]


def _plausible(value: float) -> bool:
    """A model coordinate: finite, zero allowed, inside the 100 m envelope."""
    return math.isfinite(value) and (
        value == 0.0 or grid.COORD_FLOOR <= abs(value) <= grid.COORD_CEIL
    )


def _located_store_regions(data) -> set[tuple[int, int]]:
    """The container-probing law's store bodies (the census/brep-probe law).

    The same law :mod:`catpart.brep` probes with — CATStdCont,
    CATXDocLinkCont, CATSeeBodyCont, then any other block — so the curve
    records that live in the geometry containers (not in ``CATPrtCont``)
    are visible to the display walk.  Failures contribute nothing.
    """
    d8 = int.from_bytes(data[8:12], "big") if len(data) >= 12 else 0
    blocks = store.valid_blocks(data)
    name_of = {
        store.CONTAINER_STDCONT: "CATStdCont",
        store.CONTAINER_XDOCLINK: "CATXDocLinkCont",
        store.CONTAINER_SEEBODY: "CATSeeBodyCont",
    }
    out: set[tuple[int, int]] = set()
    for container in (
        store.CONTAINER_STDCONT,
        store.CONTAINER_XDOCLINK,
        store.CONTAINER_SEEBODY,
        store.CONTAINER_OTHER,
    ):
        want = name_of.get(container)
        for blk, name in blocks:
            if want is not None and name != want:
                continue
            try:
                span = store.locate_store(data, blk, blocks, d8, container=container)
            except Exception:  # noqa: BLE001 - a failed probe contributes nothing
                continue
            if span is not None:
                out.add((int(span.body_lo), int(span.body_hi)))
    return out


def _regions(data, spans) -> list[tuple[int, int]]:
    """The part's carrier regions: located store bodies + CATPrtCont.

    ``spans`` are the exporter-validated bodies; the located store bodies
    (the probing law above) add the geometry containers the display route
    needs for its curve records; the ``CATPrtCont`` regions are the grid
    path's region law.  Duplicates are collapsed so a nested range is
    walked once.
    """
    regions = {(int(lo), int(hi)) for lo, hi in spans}
    regions.update(grid.regions(data))
    regions.update(_located_store_regions(data))
    return sorted(regions)


def _bagrep_regions(data) -> list[tuple[int, int]]:
    """The bag-rep payload containers' ``(start, end)``, in byte order.

    The count-framed f32 arrays are written inside the geometry containers
    the missing-store census named (``probe_bagrep``'s payload family), not
    in the ``CATPrtCont`` stream.  Duplicates are collapsed.
    """
    size = len(data)
    outer = int.from_bytes(data[8:12], "big") if size >= 12 else 0
    blocks = store.valid_blocks(data)
    regions = {
        (blk, store.probe_region(data, blk, blocks, outer))
        for blk, name in blocks
        if name in BAGREP_PAYLOAD_BLOCKS
    }
    return sorted(
        (lo, hi) for lo, hi in regions if hi - lo <= BAGREP_MAX_REGION
    )


def _bagrep_clean(value: float) -> bool:
    """The count-first measurement's clean-f32 test (pool scale)."""
    return math.isfinite(value) and (
        value == 0.0
        or BAGREP_VALUE_FLOOR <= abs(value) <= BAGREP_VALUE_CEIL
    )


class _BagrepClean:
    """Clean-f32 prefix sums per 4-byte frame (the probe's ``Clean``).

    A candidate count is tested against a multi-hundred-KB region, so the
    all-clean window and the clean-run-end test are prefix differences
    instead of O(count) scans; only the arrays that pass them are walked
    for the non-zero share and the fill-run gate.
    """

    def __init__(self, data, lo: int, hi: int) -> None:
        self.lo = lo
        self.sum = []
        view = memoryview(data)
        for shift in range(4):
            count = (hi - lo - shift) // 4
            if count <= 0:
                self.sum.append(array("I", [0]))
                continue
            words = view[lo + shift : lo + shift + 4 * count].cast("f")
            flags = (1 if _bagrep_clean(value) else 0 for value in words)
            self.sum.append(array("I", accumulate(flags, initial=0)))

    def all_clean(self, start: int, count: int) -> bool:
        relative = start - self.lo
        shift = relative % 4
        index = (relative - shift) // 4
        prefix = self.sum[shift]
        return (
            index + count < len(prefix)
            and prefix[index + count] - prefix[index] == count
        )

    def clean_at(self, start: int) -> bool:
        relative = start - self.lo
        shift = relative % 4
        index = (relative - shift) // 4
        prefix = self.sum[shift]
        return index + 1 < len(prefix) and prefix[index + 1] - prefix[index] == 1


def _bagrep_nonzero(data, start: int, count: int) -> float:
    nonzero = 0
    for index in range(count):
        if struct.unpack_from("<f", data, start + 4 * index)[0] != 0.0:
            nonzero += 1
    return nonzero / count


def _bagrep_max_const_run(data, start: int, count: int) -> int:
    longest = run = 1
    previous = struct.unpack_from("<f", data, start)[0]
    for index in range(1, count):
        value = struct.unpack_from("<f", data, start + 4 * index)[0]
        if value == previous:
            run += 1
            if run > longest:
                longest = run
        else:
            run = 1
            previous = value
    return longest


def _bagrep_arrays(
    data, lo: int, hi: int, clean: _BagrepClean | None = None
) -> list[tuple[int, int]]:
    """The count-framed f32 arrays in ``[lo, hi)`` as ``(start, floats)``.

    The same four gates as the bag-rep measurement: a plausible declared
    count (``V % 3 == 0``), ``V`` clean f32 at one 4-byte frame, the block
    ending where the clean run ends (the test that separates a declared
    array from a byte pattern), a non-zero share and no fill run.  Arrays
    contained in a longer one are dropped.
    """
    if clean is None:
        clean = _BagrepClean(data, lo, hi)
    found: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for offset in range(lo, hi - 4):
        if data[offset + 3]:
            continue
        count = U32.unpack_from(data, offset)[0]
        if count < 9 or count > BAGREP_MAX_FLOATS or count % 3:
            continue
        for delta in range(17):
            start = offset + 4 + delta
            if start + 4 * count > hi:
                break
            if not clean.all_clean(start, count):
                continue
            if start + 4 * count + 4 <= hi and clean.clean_at(start + 4 * count):
                continue
            if _bagrep_nonzero(data, start, count) < BAGREP_MIN_NONZERO:
                continue
            if _bagrep_max_const_run(data, start, count) > BAGREP_MAX_CONST_RUN:
                continue
            key = (start, count)
            if key not in seen:
                seen.add(key)
                found.append(key)
            break
    found.sort(key=lambda item: (item[0], -item[1]))
    keep: list[tuple[int, int]] = []
    for item in found:
        if any(
            kept[0] <= item[0] and kept[0] + 4 * kept[1] >= item[0] + 4 * item[1]
            for kept in keep
        ):
            continue
        keep.append(item)
    return keep


def _append_point(points, point) -> int | None:
    """Append one decoded point (f32-rounded) and return its index."""
    rounded = (_f32(point[0]), _f32(point[1]), _f32(point[2]))
    if not all(_plausible(value) for value in rounded):
        return None
    points.append(rounded)
    return len(points) - 1


def _f32_point_runs(data, lo: int, hi: int) -> list[tuple[int, int]]:
    """Maximal 12-byte-stride f32 point runs in ``[lo, hi)`` as (start, triples).

    The missing-store census law verbatim, region-local: a triple is a
    run member when finite and inside the (``F32_RUN_FLOOR``,
    ``F32_RUN_CEIL``) envelope; runs chain at exactly the 12-byte stride;
    a run starts where the previous slot is not a member; a run counts
    from ``F32_RUN_MIN_TRIPLES``.
    """
    size = hi - lo
    if size < 12:
        return []
    ok = bytearray(size - 11)
    for offset in range(size - 11):
        x, y, z = struct.unpack_from("<3f", data, lo + offset)
        ok[offset] = (
            1
            if (
                math.isfinite(x)
                and math.isfinite(y)
                and math.isfinite(z)
                and F32_RUN_FLOOR < abs(x) < F32_RUN_CEIL
                and F32_RUN_FLOOR < abs(y) < F32_RUN_CEIL
                and F32_RUN_FLOOR < abs(z) < F32_RUN_CEIL
            )
            else 0
        )
    runs: list[tuple[int, int]] = []
    offset = 0
    while offset < len(ok):
        if ok[offset] and (offset < 12 or not ok[offset - 12]):
            length = 0
            cursor = offset
            while cursor < len(ok) and ok[cursor]:
                length += 1
                cursor += 12
            if length >= F32_RUN_MIN_TRIPLES:
                runs.append((lo + offset, length))
            offset = max(cursor, offset + 1)
        else:
            offset += 1
    return runs


def _raw_block_regions(data) -> list[tuple[int, int]]:
    """Every body/geometry block's payload region (the fallback's scope).

    The parametric blocks (``F32_RUN_SKIP_BLOCKS``) are dropped from the
    scan set, but every valid block still bounds its neighbours' regions:
    ``probe_region`` ends at the next valid block, so filtering the list
    before the bounds would extend a body block over a part container.
    """
    size = len(data)
    outer = int.from_bytes(data[8:12], "big") if size >= 12 else 0
    blocks = store.valid_blocks(data)
    regions = {
        (blk, store.probe_region(data, blk, blocks, outer))
        for blk, name in blocks
        if name not in F32_RUN_SKIP_BLOCKS
    }
    return sorted(
        (lo, hi) for lo, hi in regions if hi - lo <= F32_SCAN_MAX_REGION
    )


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

    bagrep_regions = _bagrep_regions(data)
    bagrep_arrays = 0
    bagrep_floats = 0
    bagrep_points = 0
    bagrep_skipped = 0
    for lo, hi in bagrep_regions:
        for start, count in _bagrep_arrays(data, lo, hi):
            bagrep_arrays += 1
            bagrep_floats += count
            for index in range(count // 3):
                point = struct.unpack_from("<3f", data, start + 12 * index)
                if _append_point(points, point) is not None:
                    bagrep_points += 1
                else:
                    bagrep_skipped += 1

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

    # The empty-scan fallback (#60): a container-less ``V5_CFV2`` binary
    # (no container-name table, so no located spans and no carriers above)
    # still carries 12-byte f32 point runs in its body/geometry blocks —
    # the missing-store census measured them
    # (CAAMaiUdfForMfgHoleInstance: 93 points at 75029 in CATSeeBodyCont).
    # Only when every primary source came up empty, over the body blocks'
    # payload regions, under the measured run law — never instead of a
    # decoded carrier, and never inside the parametric part containers
    # (#69: their triples are tessellation cache, not a display carrier).
    f32_runs = 0
    f32_points = 0
    if not points:
        for lo, hi in _raw_block_regions(data):
            for start, length in _f32_point_runs(data, lo, hi):
                f32_runs += 1
                for index in range(length):
                    point = struct.unpack_from("<3f", data, start + 12 * index)
                    if _append_point(points, point) is not None:
                        f32_points += 1

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
        bagrep_regions=len(bagrep_regions),
        bagrep_arrays=bagrep_arrays,
        bagrep_floats=bagrep_floats,
        bagrep_points=bagrep_points,
        bagrep_skipped=bagrep_skipped,
        points=tuple(points),
        segments=tuple(segments),
        f32_runs=f32_runs,
        f32_points=f32_points,
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
