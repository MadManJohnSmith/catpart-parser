#!/usr/bin/env python3
"""Probe the pre-CGM bulk stream: ``CATPrtCont`` content framing + pole nets.

Context (tickets #57 follow-up, 2026-11-19).  The CGM probe
(``docs/evidence/2026-11-18-cgm-grid-probe.md``) closed the ``CGMGeom``
region as a dictionary: 0/128 exact tilings, no numeric payload.  The
smallest next step it named was a *class-header law* for the bulk.  The
bulk is not the CGM region: it is the ``CATPrtCont`` storage block's
content stream, the region that immediately precedes ``CGMGeom`` on the
no-facet population (BR5-07a measured 337 MB of it on ``17930bab``; the
128 no-facet parts carry 10,950,647 B).

This probe asks two questions, both answered from bytes only:

1. **Does the content stream frame?**  The stream is a run of A/B-family
   length-framed records (the cadmpeg-documented CATIA object-stream
   framing, CC-BY)::

       A-family (u32 length): byte0 = 0xA4 + W  (a5/a6/a7/a8 = W 1..4)
         +1 flag (03/13/83)  +2 class  +3 payload_len:u32le
         +7 header_token[W]  payload @ +7+W  next @ +7+W+payload_len

       B-family (u8 length):  byte0 = 0xB1 + W  (b2/b3/b4/b5 = W 1..4)
         +1 flag (03/13/83)  +2 class  +3 payload_len:u8
         +4 header_token[W]  payload @ +4+W  next @ +4+W+payload_len

   The claim is *not* taken from the document: the probe walks the bytes
   and requires each record to close on the next record (or on the
   cluster end), then measures the exact-tiling clusters.  Where the walk
   stops, the residue is measured and classified — it is not called noise.

2. **Does the bulk carry numbers?**  Every A-family ``a5 03 34`` record's
   payload is scanned for a pole net: a run of finite f64le triples that
   closes on a constant tail.  The content-prefix allocation before the
   first record (the metadata table ends there) is scanned the same way.
   Every candidate net is validated by value (finite, plausible magnitude,
   rectangular row structure, monotone stations) and the layout is
   reported with both bases (block-relative and absolute file offset).

The metadata table that ends the preamble is parsed too: it is the
big-endian property table of the storage block (``total_size``,
``identity``, ``count``; records of ``size/identity/type/value_bytes``),
so the *content start* is derived from the bytes rather than guessed.

Read-only over the corpus; ``src/`` and the exporter are untouched.

Run one anchor first, then the population::

  export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
  .venv/bin/python -I scripts/triage/probe_bulk_stream.py --anchor 80aad8d8 --no-population
  .venv/bin/python -I scripts/triage/probe_bulk_stream.py

Writes ``docs/evidence/data/bulk-stream-claims.csv``.  The population is
the 128 no-facet stores of ``stage13-elementspace-census.csv`` (the same
split the CGM probe uses); the three facet carriers are reported as a
control.
"""

from __future__ import annotations

import argparse
import csv
import math
import mmap
import struct
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
POPULATION = ROOT / "docs" / "evidence" / "data" / "stage13-elementspace-census.csv"
OUT_CLAIMS = ROOT / "docs" / "evidence" / "data" / "bulk-stream-claims.csv"

sys.path.insert(0, str(ROOT / "src"))

from catpart.brep import cgm_nurbs  # noqa: E402

CLAIM_FIELDS = ["claim", "scope", "observations", "passes", "rate", "label", "detail"]

#: A/B family frames.  ``byte0 - base`` is the header-token width in
#: bytes; the two bases are four apart because the record header is four
#: bytes longer in the A family (u32 length instead of u8).
A_FAMILY_BASE = 0xA4
B_FAMILY_BASE = 0xB1
MAX_WIDTH = 4
#: Frame flags observed in the corpus (and documented): all three occur
#: with width-1 records, and wide records keep 0x03.
FLAGS = (0x03, 0x13, 0x83)

#: A frame longer than this is a misread (the largest real record in the
#: population is well under 64 KiB).
MAX_PAYLOAD = 1 << 20

#: Plausible model coordinate magnitude for a pole net.  Coordinates are
#: millimetres; the 128-part population sits in the 1e-2..1e4 band.
NET_FLOOR = 1e-3
NET_CEIL = 1e6

#: A pole net is a rectangular numpy-style grid: one coordinate is
#: near-constant within a row (a station).  "Near" = mean within-row
#: spread below this fraction of that axis's global span.
GRID_SPREAD_BAR = 0.01

#: A residue gap counts as a numeric allocation when this fraction of it
#: is covered by one plausible f64 run.
NUMERIC_GAP_BAR = 0.80

#: Class 0x34 = consolidated freeform surface (A family).  The marker is a
#: scan seed only: the frame walk must accept the offset and the payload
#: must close on a measured surface tail before the record is counted.
SURFACE_MARKER = b"\xa5\x03\x34"
SURFACE_CLASS = 0x34
#: The two tails measured on every corpus surface record whose grid is a
#: single net (the payload ends after the grid in 152 or 154 bytes).  This
#: is a *measured* closure law for the scan, not an assumed header.
SURFACE_TAILS = (152, 154)


@dataclass(frozen=True)
class MetadataRecord:
    """One property-table record (big-endian, §3.1 of the format notes)."""

    offset: int  # block-relative
    size: int
    identity: int
    value_type: int
    value_bytes: int
    text: str


@dataclass(frozen=True)
class MetadataTable:
    """The storage block's big-endian metadata property table."""

    offset: int  # block-relative
    total_size: int
    identity: int
    count: int
    records: tuple[MetadataRecord, ...]

    @property
    def end(self) -> int:
        return self.offset + self.total_size

    @property
    def tiles(self) -> bool:
        return sum(r.size for r in self.records) + 12 == self.total_size


@dataclass(frozen=True)
class BulkRecord:
    """One A/B-family frame.  ``end`` is exclusive."""

    start: int
    family: str
    width: int
    flag: int
    cls: int
    payload_len: int
    payload: int
    end: int


@dataclass(frozen=True)
class PoleNet:
    """A rectangular point net decoded from a run of f64le triples."""

    start: int  # absolute offset of the first triple
    points: int
    rows: int
    cols: int
    station_axis: int
    spread: float
    monotone: bool
    aabb: tuple[float, float, float, float, float, float]
    mean_closure: float

    @property
    def bytes(self) -> int:
        return self.points * 24

    @property
    def scale_ok(self) -> bool:
        """All coordinates stay inside a 100 m model envelope (mm units)."""
        return max(abs(v) for v in self.aabb) <= 1e5

    @property
    def ok(self) -> bool:
        """A validated net: rectangular by the spread bar and model-scale."""
        return self.spread <= GRID_SPREAD_BAR and self.scale_ok


@dataclass(frozen=True)
class Cluster:
    """A contiguous run of >=3 frames that closes on its own end."""

    start: int
    end: int
    records: int


@dataclass(frozen=True)
class RegionMeasure:
    """Everything the probe measures on one part's bulk region."""

    block: int
    end: int
    metadata: MetadataTable | None
    content: int
    prefix: PoleNet | None
    clusters: tuple[Cluster, ...]
    surfaces: tuple[tuple[int, int, int, PoleNet | None], ...]
    gaps: tuple[tuple[int, int], ...]
    numeric_gaps: int
    dialect: str
    surface_candidates: int
    gap_numeric: dict
    entropy: tuple[float, float, float, int]
    framed_entropy: float
    gap_entropy: float

    @property
    def bytes(self) -> int:
        return self.end - self.block

    @property
    def content_bytes(self) -> int:
        return self.end - self.content

    @property
    def framed(self) -> int:
        return sum(c.end - c.start for c in self.clusters)

    @property
    def records(self) -> int:
        return sum(c.records for c in self.clusters)

    @property
    def residue(self) -> int:
        return self.content_bytes - self.framed

    @property
    def surface_points(self) -> int:
        return sum(s[3].points for s in self.surfaces if s[3] is not None)

    @property
    def numeric_gap_bytes(self) -> int:
        return sum(b - a for a, b in self.gaps if self.gap_numeric.get((a, b), False))

    @property
    def accounted(self) -> int:
        """Frames plus the f64 allocations the gaps carry."""
        return self.framed + self.numeric_gap_bytes


def _u16be(data, off: int) -> int:
    return int.from_bytes(data[off : off + 2], "big")


def _u32be(data, off: int) -> int:
    return int.from_bytes(data[off : off + 4], "big")


def _u32le(data, off: int) -> int:
    return int.from_bytes(data[off : off + 4], "little")


def parse_metadata_table(data, block: int, hi: int) -> MetadataTable | None:
    """Locate and validate the storage block's metadata property table.

    The table opens with ``total_size:u32be``, ``identity:u32be``,
    ``count:u32be`` and each counted record is
    ``size:u32be identity:u32be value_type:u16be value_bytes:u32be`` +
    value, with ``size == 14 + value_bytes``; the records must close the
    table exactly at ``nat + total_size``.  This is a *validation* scan,
    not a fixed offset: the table is allowed to start anywhere in the
    header window.  The last value is the block's ``Cont_<hex>`` UTF-16BE
    content name, which is the reason the content stream starts here.
    """
    for start in range(block, min(hi, block + 8192)):
        if start + 12 > hi:
            return None
        total = _u32be(data, start)
        count = _u32be(data, start + 8)
        if not (32 <= total <= 1 << 20 and 1 <= count <= 128):
            continue
        end = start + total
        if end > hi:
            continue
        pos = start + 12
        records: list[MetadataRecord] = []
        ok = True
        for _ in range(count):
            if pos + 14 > end:
                ok = False
                break
            size = _u32be(data, pos)
            identity = _u32be(data, pos + 4)
            value_type = _u16be(data, pos + 8)
            value_bytes = _u32be(data, pos + 10)
            if size != 14 + value_bytes or pos + size > end:
                ok = False
                break
            raw = bytes(data[pos + 14 : pos + size])
            text = raw.decode("utf-16-be", "ignore") if value_type == 2 else ""
            records.append(
                MetadataRecord(
                    offset=pos - block,
                    size=size,
                    identity=identity,
                    value_type=value_type,
                    value_bytes=value_bytes,
                    text=text,
                )
            )
            pos += size
        if not ok or pos != end:
            continue
        if not records or "Cont_" not in records[-1].text:
            continue
        return MetadataTable(
            offset=start - block,
            total_size=total,
            identity=_u32be(data, start + 4),
            count=count,
            records=tuple(records),
        )
    return None


def parse_record(data, pos: int, hi: int) -> BulkRecord | None:
    """Parse one A/B-family frame at ``pos``; ``None`` when it does not close.

    The width is derived from the family byte, never guessed; the flag
    must be one of the three observed values.  This is the whole grammar:
    two families, one length field each, a width-``W`` header token that
    is *retained* (it is not interpreted, and it is not a per-record id).
    """
    if pos + 4 > hi:
        return None
    byte0 = data[pos]
    if A_FAMILY_BASE < byte0 <= A_FAMILY_BASE + MAX_WIDTH:
        width = byte0 - A_FAMILY_BASE
        if pos + 7 + width > hi or data[pos + 1] not in FLAGS:
            return None
        payload_len = _u32le(data, pos + 3)
        if payload_len > MAX_PAYLOAD:
            return None
        payload = pos + 7 + width
        end = payload + payload_len
        if end > hi:
            return None
        return BulkRecord(
            pos, "A", width, data[pos + 1], data[pos + 2], payload_len, payload, end
        )
    if B_FAMILY_BASE < byte0 <= B_FAMILY_BASE + MAX_WIDTH:
        width = byte0 - B_FAMILY_BASE
        if pos + 4 + width > hi or data[pos + 1] not in FLAGS:
            return None
        payload_len = data[pos + 3]
        payload = pos + 4 + width
        end = payload + payload_len
        if end > hi:
            return None
        return BulkRecord(
            pos, "B", width, data[pos + 1], data[pos + 2], payload_len, payload, end
        )
    return None


def walk(data, lo: int, hi: int) -> tuple[list[BulkRecord], int]:
    """Greedily walk frames from ``lo``; return the frames and the stop offset."""
    records: list[BulkRecord] = []
    pos = lo
    while pos < hi:
        rec = parse_record(data, pos, hi)
        if rec is None:
            break
        records.append(rec)
        pos = rec.end
    return records, pos


def clusters(data, lo: int, hi: int, min_chain: int = 3) -> tuple[Cluster, ...]:
    """Contiguous frame runs of at least ``min_chain`` records.

    A short accidental parse is not admitted: the run must chain at least
    three frames and close exactly on its own end.  Every later record
    cluster is found by resuming the byte scan at the end of the previous
    one, so clusters partition the framed part of the stream.
    """
    out: list[Cluster] = []
    pos = lo
    while pos < hi - 8:
        if parse_record(data, pos, hi) is None:
            pos += 1
            continue
        records, end = walk(data, pos, hi)
        if len(records) >= min_chain:
            out.append(Cluster(pos, end, len(records)))
            pos = end
        else:
            pos += 1
    return tuple(out)


def _plausible(value: float) -> bool:
    """A model coordinate: finite, in band, and 0.0 is a legitimate value.

    The floor rejects the denormal band that integer arrays alias as; an
    exact zero does not alias anything and occurs on the corpus grids
    (a profile crossing the origin), so it must not split a run.
    """
    return math.isfinite(value) and (
        value == 0.0 or NET_FLOOR <= abs(value) <= NET_CEIL
    )


def prefix_run(data, lo: int, hi: int) -> tuple[int, int]:
    """Longest plausible f64 run that *begins* at ``lo`` (phase 0..7).

    The content-prefix allocation has no length field of its own: it
    starts where the metadata table ends.  So the probe accepts a run whose
    first double starts within the first 8 bytes of the content and
    requires the run to be the maximal one from that phase — it does not
    search the whole region for a nicer array.
    """
    best = (0, lo)
    for phase in range(8):
        pos = lo + phase
        count = 0
        while pos + 8 <= hi:
            value = struct.unpack_from("<d", data, pos)[0]
            if not _plausible(value):
                break
            count += 1
            pos += 8
        if count > best[0]:
            best = (count, lo + phase)
    return best


def f64_run(data, lo: int, hi: int) -> tuple[int, int]:
    """Longest run of plausible f64, at any byte phase; ``(count, start)``.

    The byte phase is not assumed: the corpus stores these nets both
    8-aligned and 4-aligned to the region.  A run is the maximal sequence
    of consecutive plausible doubles; the caller divides it into triples.
    """
    best = (0, lo)
    for phase in range(8):
        pos = lo + phase
        current = 0
        start = pos
        while pos + 8 <= hi:
            value = struct.unpack_from("<d", data, pos)[0]
            if _plausible(value):
                if current == 0:
                    start = pos
                current += 1
                if current > best[0]:
                    best = (current, start)
            else:
                current = 0
            pos += 8
    return best


def pole_net(points: list[tuple[float, float, float]], start: int) -> PoleNet:
    """Validate a triple run as a rectangular pole net and report its shape.

    The net is a (rows x cols) grid.  The row length is the **largest**
    divisor of the point count whose rows are near-constant in one
    coordinate (a sweep station): a longer admissible row is a stronger
    rectangle, so the smallest factors are not allowed to win by being
    trivially constant.  The report carries the spread (mean within-row
    range / global range) so a reader can see how strong the rectangle
    is instead of trusting the factorisation.
    """
    n = len(points)
    axes = [[p[i] for p in points] for i in range(3)]
    aabb = (
        min(axes[0]),
        max(axes[0]),
        min(axes[1]),
        max(axes[1]),
        min(axes[2]),
        max(axes[2]),
    )
    spans = [aabb[1] - aabb[0], aabb[3] - aabb[2], aabb[5] - aabb[4]]

    def ratio_for(cols: int, axis: int) -> float:
        rows = n // cols
        if spans[axis] <= 0:
            return float("inf")
        spread = (
            sum(
                max(axes[axis][row * cols : (row + 1) * cols])
                - min(axes[axis][row * cols : (row + 1) * cols])
                for row in range(rows)
            )
            / rows
        )
        return spread / spans[axis]

    shape = None
    for cols in range(min(n, 256), 2, -1):
        if n % cols or n // cols < 3:
            continue
        axis = min(range(3), key=lambda a: ratio_for(cols, a))
        ratio = ratio_for(cols, axis)
        if ratio <= GRID_SPREAD_BAR:
            shape = (cols, axis, ratio)
            break
    if shape is None:
        for cols in range(3, min(n, 256) + 1):
            if n % cols or n // cols < 3:
                continue
            axis = min(range(3), key=lambda a: ratio_for(cols, a))
            ratio = ratio_for(cols, axis)
            if shape is None or ratio < shape[2]:
                shape = (cols, axis, ratio)
    if shape is None:
        shape = (n, 0, 0.0)
    cols, axis, ratio = shape
    rows = n // cols
    stations = [
        sum(axes[axis][row * cols : (row + 1) * cols]) / cols for row in range(rows)
    ]
    monotone = all(b >= a for a, b in zip(stations, stations[1:])) or all(
        b <= a for a, b in zip(stations, stations[1:])
    )
    closure = [
        math.dist(points[row * cols], points[row * cols + cols - 1])
        for row in range(rows)
    ]
    return PoleNet(
        start=start,
        points=n,
        rows=rows,
        cols=cols,
        station_axis=axis,
        spread=ratio,
        monotone=monotone,
        aabb=aabb,
        mean_closure=sum(closure) / len(closure),
    )


def decode_net(data, lo: int, hi: int) -> PoleNet | None:
    """Decode the longest f64 triple run in ``[lo, hi)`` as a pole net.

    When the span closes on a measured surface tail (152/154 B), the run
    is trimmed to that closure so zero padding inside the tail cannot
    extend the point count.  A run without a tail (the content prefix) is
    returned as found.
    """
    count, start = f64_run(data, lo, hi)
    n = count // 3
    for tail in SURFACE_TAILS:
        end = hi - tail
        if end > start and (end - start) % 24 == 0:
            trimmed = (end - start) // 24
            if 0 < trimmed <= n:
                n = trimmed
                break
    if n < 3:
        return None
    points = [struct.unpack_from("<3d", data, start + 24 * i) for i in range(n)]
    return pole_net(points, start)


def decode_prefix_net(data, lo: int, hi: int) -> PoleNet | None:
    """Decode the content-prefix allocation (the run that starts at ``lo``)."""
    count, start = prefix_run(data, lo, hi)
    n = count // 3
    if n < 3:
        return None
    points = [struct.unpack_from("<3d", data, start + 24 * i) for i in range(n)]
    return pole_net(points, start)


def surface_records(
    data, lo: int, hi: int
) -> list[tuple[int, int, int, PoleNet | None]]:
    """Every validated ``a5 03 34`` frame with its payload pole net.

    The marker seeds the scan; a hit is admitted only when the frame walk
    accepts the bytes at that exact offset, the class is 0x34, and the
    payload closes on a measured surface tail (152/154 B) with a
    tail-aligned grid.  A marker-shaped coincidence inside another frame's
    payload fails the closure and is not counted.
    """
    out: list[tuple[int, int, int, PoleNet | None]] = []
    pos = lo
    while True:
        hit = data.find(SURFACE_MARKER, pos)
        if hit < 0 or hit + 8 > hi:
            return out
        pos = hit + 1
        rec = parse_record(data, hit, hi)
        if rec is None or rec.family != "A" or rec.cls != SURFACE_CLASS:
            continue
        net = decode_net(data, rec.payload, rec.end)
        if net is None:
            continue
        if rec.end - (net.start + net.bytes) not in SURFACE_TAILS:
            continue
        out.append((rec.start, rec.payload, rec.end, net))


def _surface_candidates(data, lo: int, hi: int) -> int:
    """Marker-class ``a5 03 34`` frames, validated or not (the denominator)."""
    count = 0
    pos = lo
    while True:
        hit = data.find(SURFACE_MARKER, pos)
        if hit < 0 or hit + 8 > hi:
            return count
        pos = hit + 1
        rec = parse_record(data, hit, hi)
        if rec is not None and rec.family == "A" and rec.cls == SURFACE_CLASS:
            count += 1


def measure_region(data) -> RegionMeasure | None:
    """Measure the ``CATPrtCont`` content stream of one part."""
    regions = cgm_nurbs.valid_regions(data)
    for index, (block, name, _) in enumerate(regions):
        if name != "CATPrtCont":
            continue
        end = regions[index + 1][0] if index + 1 < len(regions) else len(data)
        table = parse_metadata_table(data, block, end)
        content = block + (table.end if table is not None else 0)
        if table is None:
            # No table: measure from the block end so the failure is
            # visible as a region that frames nothing.
            content = end
        prefix = decode_prefix_net(data, content, end)
        found = clusters(data, content, end)
        gaps: list[tuple[int, int]] = []
        previous = content
        for cluster in found:
            if cluster.start > previous:
                gaps.append((previous, cluster.start))
            previous = cluster.end
        if previous < end:
            gaps.append((previous, end))
        gap_numeric = {gap: _gap_numeric(data, gap) for gap in gaps}
        numeric_gaps = sum(1 for gap in gaps if gap_numeric[gap])
        head = bytes(data[content : content + 96])
        if found:
            dialect = "object-stream"
        elif b"\xe5\x0d" in head:
            dialect = "E5"
        elif prefix is not None and prefix.points >= 3:
            dialect = "f64-net"
        else:
            dialect = "other"
        framed_bytes = sum(c.end - c.start for c in found)
        gap_bytes = sum(b - a for a, b in gaps)
        framed_entropy = (
            sum(entropy(data, c.start, c.end) * (c.end - c.start) for c in found)
            / framed_bytes
            if framed_bytes
            else 0.0
        )
        gap_entropy = (
            sum(entropy(data, a, b) * (b - a) for a, b in gaps) / gap_bytes
            if gap_bytes
            else 0.0
        )
        return RegionMeasure(
            block=block,
            end=end,
            metadata=table,
            content=content,
            prefix=prefix,
            clusters=found,
            surfaces=tuple(surface_records(data, content, end)),
            gaps=tuple(gaps),
            numeric_gaps=numeric_gaps,
            dialect=dialect,
            surface_candidates=_surface_candidates(data, content, end),
            gap_numeric=gap_numeric,
            entropy=entropy_profile(data, content, end),
            framed_entropy=framed_entropy,
            gap_entropy=gap_entropy,
        )
    return None


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


def _region_for(sha: str, manifest: dict[str, str]):
    path = next((value for key, value in manifest.items() if key.startswith(sha)), None)
    if path is None:
        raise SystemExit(f"{sha} not in the manifest")
    handle = (ROOT / path).open("rb")
    return handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)


def entropy(data, lo: int, hi: int) -> float:
    """Shannon entropy of a byte span, in bits/byte (0..8)."""
    if hi <= lo:
        return 0.0
    counts = Counter(bytes(data[lo:hi]))
    total = hi - lo
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def entropy_profile(
    data, lo: int, hi: int, window: int = 4096
) -> tuple[float, float, float, int]:
    """``(min, median, max, windows_above_7.9)`` over fixed windows.

    A compressed span is the only thing in a CATIA stream that reaches
    ~8 bits/byte; a record stream and an f64 payload sit below 7.7.  The
    profile is a diagnostic, not a decoder.
    """
    values = [
        entropy(data, start, min(start + window, hi)) for start in range(lo, hi, window)
    ]
    if not values:
        return 0.0, 0.0, 0.0, 0
    values.sort()
    return (
        values[0],
        values[len(values) // 2],
        values[-1],
        sum(1 for value in values if value > 7.9),
    )


def _rate(num: int, den: int) -> str:
    return "" if den <= 0 else f"{num / den:.4f}"


def _fmt_net(net: PoleNet | None) -> str:
    if net is None:
        return "none"
    return (
        f"points={net.points} rows={net.rows} cols={net.cols} "
        f"axis={'xyz'[net.station_axis]} spread={net.spread:.4f} "
        f"monotone={int(net.monotone)} mean_closure={net.mean_closure:.3f} "
        f"aabb=({net.aabb[0]:.3f},{net.aabb[1]:.3f},"
        f"{net.aabb[2]:.3f},{net.aabb[3]:.3f},"
        f"{net.aabb[4]:.3f},{net.aabb[5]:.3f})"
    )


def _gap_numeric(data, gap: tuple[int, int]) -> bool:
    count, _ = f64_run(data, gap[0], gap[1])
    return count * 8 >= NUMERIC_GAP_BAR * (gap[1] - gap[0])


def anchor_claims(sha: str, measure: RegionMeasure, data) -> list[list[str]]:
    """Claim rows for one worked anchor (both bases in ``detail``)."""
    rows: list[list[str]] = []
    table = measure.metadata
    rows.append(
        [
            "BS-01",
            sha,
            "1",
            "1" if table is not None else "0",
            "",
            "fact",
            f"CATPrtCont abs=[{measure.block}, {measure.end}) bytes={measure.bytes} "
            f"content_start={measure.content} (block+{measure.content - measure.block})",
        ]
    )
    if table is not None:
        rows.append(
            [
                "BS-02",
                sha,
                str(len(table.records)),
                "1" if table.tiles else "0",
                _rate(table.total_size, table.total_size),
                "fact",
                f"metadata table block+{table.offset} total_size={table.total_size} "
                f"count={table.count} ends block+{table.end} "
                "names="
                + ";".join(
                    record.text.encode("unicode_escape").decode("ascii")
                    for record in table.records
                ),
            ]
        )
    rows.append(
        [
            "BS-03",
            sha,
            str(measure.prefix.points if measure.prefix else 0),
            "1" if measure.prefix and measure.prefix.ok else "0",
            "",
            "fact",
            f"content prefix allocation at abs={measure.content} "
            f"(block+{measure.content - measure.block}): {_fmt_net(measure.prefix)}",
        ]
    )
    rows.append(
        [
            "BS-04",
            sha,
            str(measure.records),
            str(len(measure.clusters)),
            _rate(measure.framed, measure.content_bytes),
            "fact",
            f"frame walk: clusters={len(measure.clusters)} records={measure.records} "
            f"framed={measure.framed} content={measure.content_bytes} "
            f"residue={measure.residue} coverage={_rate(measure.framed, measure.content_bytes)}",
        ]
    )
    rows.append(
        [
            "BS-19",
            sha,
            str(measure.entropy[3]),
            "1",
            f"{measure.entropy[1]:.2f}",
            "fact",
            f"entropy bits/byte over 4 KiB windows: min={measure.entropy[0]:.2f} "
            f"median={measure.entropy[1]:.2f} max={measure.entropy[2]:.2f} "
            f"windows>7.9={measure.entropy[3]}; framed_mean={measure.framed_entropy:.2f} "
            f"gap_mean={measure.gap_entropy:.2f}",
        ]
    )
    rows.append(
        [
            "BS-18",
            sha,
            str(measure.accounted),
            "1",
            _rate(measure.accounted, measure.content_bytes),
            "fact",
            f"accounted = frames {measure.framed} + f64 allocations "
            f"{measure.numeric_gap_bytes} = {measure.accounted} of content "
            f"{measure.content_bytes} ({_rate(measure.accounted, measure.content_bytes)}); "
            f"left out: text allocation(s) and the footer",
        ]
    )
    rows.append(
        [
            "BS-05",
            sha,
            str(len(measure.gaps)),
            str(measure.numeric_gaps),
            _rate(measure.numeric_gaps, len(measure.gaps)),
            "fact",
            "residue gaps="
            + ",".join(f"{b - a}" for a, b in measure.gaps)
            + "; f64-covered="
            + str(measure.numeric_gaps),
        ]
    )
    nets = [s[3] for s in measure.surfaces if s[3] is not None]
    rows.append(
        [
            "BS-06",
            sha,
            str(len(measure.surfaces)),
            str(sum(1 for n in nets if n.ok)),
            _rate(sum(1 for n in nets if n.ok), len(measure.surfaces)),
            "fact",
            f"a5 03 34 marker frames={measure.surface_candidates} "
            f"tail-closed grids={len(measure.surfaces)} "
            f"pole_points={sum(n.points for n in nets)}",
        ]
    )
    if nets:
        points = sorted(n.points for n in nets)
        rows.append(
            [
                "BS-07",
                sha,
                str(len(nets)),
                "1",
                "",
                "fact",
                "pole point counts="
                + ",".join(str(n.points) for n in nets[:12])
                + f" min={points[0]} median={points[len(points) // 2]} max={points[-1]}",
            ]
        )
        first = next((s for s in measure.surfaces if s[3] is not None), None)
        if first is not None:
            start, payload, end, net = first
            rows.append(
                [
                    "BS-08",
                    sha,
                    "1",
                    "1" if net.monotone and net.ok else "0",
                    "",
                    "fact",
                    f"first surface frame abs={start} (block+{start - measure.block}) "
                    f"payload abs={payload} grid abs={net.start} "
                    f"grid block+{net.start - measure.block} tail={end - (net.start + net.bytes)} "
                    f"payload_len={end - payload}; {_fmt_net(net)}",
                ]
            )
        if measure.prefix is not None:
            rows.append(
                [
                    "BS-09",
                    sha,
                    str(measure.prefix.points),
                    "1" if "identical=1" in _prefix_matches(measure, data) else "0",
                    "",
                    "fact",
                    "prefix grid vs first surface grid: "
                    + _prefix_matches(measure, data),
                ]
            )
    return rows


def _prefix_matches(measure: RegionMeasure, data) -> str:
    """Is the content-prefix allocation bit-identical to a surface grid?"""
    if measure.prefix is None:
        return "no prefix net"
    prefix = bytes(
        data[measure.prefix.start : measure.prefix.start + measure.prefix.bytes]
    )
    for _, _, _, net in measure.surfaces:
        if net is None or net.points != measure.prefix.points:
            continue
        other = bytes(data[net.start : net.start + net.bytes])
        return f"surface abs={net.start} identical={int(prefix == other)}"
    return "no surface grid with the same point count"


def population_claims(
    primary: list[tuple[str, RegionMeasure | None]],
    carriers: list[tuple[str, RegionMeasure | None]],
) -> list[list[str]]:
    """Aggregate claims over the 128 and the control."""

    def agg(rows):
        regions = [m for _, m in rows if m is not None]
        return {
            "files": len(rows),
            "regions": len(regions),
            "bytes": sum(m.bytes for m in regions),
            "content": sum(m.content_bytes for m in regions),
            "framed": sum(m.framed for m in regions),
            "records": sum(m.records for m in regions),
            "clusters": sum(len(m.clusters) for m in regions),
            "meta": sum(1 for m in regions if m.metadata is not None),
            "prefix": sum(
                1 for m in regions if m.prefix is not None and m.prefix.points >= 3
            ),
            "prefix_pts": sum(m.prefix.points for m in regions if m.prefix is not None),
            "surface_files": sum(1 for m in regions if m.surfaces),
            "surfaces": sum(len(m.surfaces) for m in regions),
            "candidates": sum(m.surface_candidates for m in regions),
            "net_surfaces": sum(
                1 for m in regions for s in m.surfaces if s[3] is not None
            ),
            "points": sum(m.surface_points for m in regions),
            "nogrid": sum(1 for m in regions if m.records == 0),
            "gaps": sum(len(m.gaps) for m in regions),
            "numeric_gaps": sum(m.numeric_gaps for m in regions),
            "accounted": sum(m.accounted for m in regions),
            "entropy": (
                sum(m.entropy[1] for m in regions) / len(regions) if regions else 0.0
            ),
            "high_entropy_files": sum(1 for m in regions if m.entropy[3] > 0),
            "numeric_gap_bytes": sum(m.numeric_gap_bytes for m in regions),
            "dialects": Counter(m.dialect for m in regions),
        }

    out = agg(primary)
    control = agg(carriers)
    total = out["bytes"]
    rows = [
        [
            "BS-10",
            "population:128",
            str(out["files"]),
            str(out["meta"]),
            _rate(out["meta"], out["files"]),
            "fact",
            f"bulk bytes={out['bytes']} content={out['content']} "
            f"metadata tables={out['meta']}/{out['files']}",
        ],
        [
            "BS-11",
            "population:128",
            str(out["records"]),
            str(out["clusters"]),
            _rate(out["framed"], out["content"]),
            "fact",
            f"clusters={out['clusters']} records={out['records']} "
            f"framed={out['framed']} content={out['content']} "
            f"coverage={_rate(out['framed'], out['content'])} "
            f"accounted={out['accounted']} "
            f"mean_entropy={out['entropy']:.2f} "
            f"files_with_window_above_7.9={out['high_entropy_files']} "
            f"accounted_rate={_rate(out['accounted'], out['content'])} "
            f"files_with_no_frame={out['nogrid']}",
        ],
        [
            "BS-12",
            "population:128",
            str(out["surfaces"]),
            str(out["net_surfaces"]),
            _rate(out["net_surfaces"], out["surfaces"]),
            "fact",
            f"a5 03 34 marker frames={out['candidates']} "
            f"tail-closed grids={out['surfaces']} files={out['surface_files']} "
            f"pole_points={out['points']}",
        ],
        [
            "BS-13",
            "population:128",
            str(out["prefix"]),
            str(out["prefix_pts"]),
            "",
            "fact",
            f"content-prefix nets in {out['prefix']}/{out['regions']} regions, "
            f"points={out['prefix_pts']}",
        ],
        [
            "BS-14",
            "population:128",
            str(out["gaps"]),
            str(out["numeric_gaps"]),
            _rate(out["numeric_gaps"], out["gaps"]),
            "fact",
            f"residue gaps={out['gaps']} f64-covered={out['numeric_gaps']} "
            f"residue_bytes={out['content'] - out['framed']}",
        ],
        [
            "BS-15",
            "control:3",
            str(control["files"]),
            str(control["surface_files"]),
            _rate(control["surface_files"], control["files"]),
            "fact",
            f"facet carriers: bytes={control['bytes']} framed={control['framed']} "
            f"records={control['records']} surfaces={control['surfaces']} "
            f"points={control['points']}",
        ],
        [
            "BS-16",
            "population:128",
            str(out["regions"]),
            str(out["dialects"].get("object-stream", 0)),
            _rate(out["dialects"].get("object-stream", 0), out["regions"]),
            "fact",
            "content dialect by head: "
            + " ".join(
                f"{name}={count}" for name, count in sorted(out["dialects"].items())
            ),
        ],
    ]
    ab = [m for _, m in primary if m is not None and m.dialect == "object-stream"]
    if ab:
        ab_content = sum(m.content_bytes for m in ab)
        ab_framed = sum(m.framed for m in ab)
        rows.append(
            [
                "BS-17",
                f"population:object-stream:{len(ab)}",
                str(sum(m.records for m in ab)),
                str(len(ab)),
                _rate(ab_framed, ab_content),
                "fact",
                f"object-stream dialect only: files={len(ab)} content={ab_content} "
                f"framed={ab_framed} residue={ab_content - ab_framed} "
                f"coverage={_rate(ab_framed, ab_content)} "
                f"accounted={sum(m.accounted for m in ab)} "
                f"surfaces={sum(len(m.surfaces) for m in ab)} "
                f"pole_points={sum(m.surface_points for m in ab)}",
            ]
        )
    return rows


def _print_metadata(table: MetadataTable | None) -> None:
    if table is None:
        print("   metadata table: none")
        return
    print(
        f"   metadata table block+{table.offset} total={table.total_size} "
        f"count={table.count} tiles={table.tiles}"
    )
    for record in table.records:
        print(
            f"     +{record.offset:5d} size={record.size:4d} "
            f"id={record.identity:4d} type={record.value_type} "
            f"bytes={record.value_bytes:4d} {record.text!r}"
        )


def _print_frames(data, measure: RegionMeasure, limit: int = 10) -> None:
    print("   first frames:")
    shown = 0
    for cluster in measure.clusters:
        records, _ = walk(data, cluster.start, cluster.end)
        for rec in records:
            if shown >= limit:
                return
            print(
                f"     abs={rec.start:8d} "
                f"{rec.family}{rec.width} flag=0x{rec.flag:02x} "
                f"class=0x{rec.cls:02x} len={rec.payload_len:5d}"
            )
            shown += 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--anchor",
        default="80aad8d8,d7ed0772",
        help="comma-separated sha16 of the two worked anchors",
    )
    parser.add_argument("--population", type=Path, default=POPULATION)
    parser.add_argument("--family", default="no-pool")
    parser.add_argument(
        "--limit", type=int, default=0, help="cap the population (0 = all)"
    )
    parser.add_argument("--out", type=Path, default=OUT_CLAIMS)
    parser.add_argument("--no-population", action="store_true", help="anchor only")
    args = parser.parse_args(argv)

    manifest = _load_manifest()
    rows: list[list[str]] = []

    anchor_measures = []
    for sha in (part.strip() for part in args.anchor.split(",") if part.strip()):
        handle, data = _region_for(sha, manifest)
        measure = measure_region(data)
        if measure is None:
            raise SystemExit(f"no CATPrtCont region in {sha}")
        anchor_measures.append((sha, measure))
        rows.extend(anchor_claims(sha, measure, data))

        print(f"== anchor {sha}: CATPrtCont abs {measure.block}..{measure.end}")
        print(
            f"   bytes={measure.bytes} content_start={measure.content} "
            f"content={measure.content_bytes}"
        )
        _print_metadata(measure.metadata)
        print(f"   content prefix net: {_fmt_net(measure.prefix)}")
        print(
            f"   frame walk: clusters={len(measure.clusters)} records={measure.records} "
            f"framed={measure.framed} residue={measure.residue} "
            f"coverage={_rate(measure.framed, measure.content_bytes)} "
            f"accounted={measure.accounted}"
        )
        _print_frames(data, measure)
        nets = [s for s in measure.surfaces if s[3] is not None]
        print(
            f"   a5 03 34 marker frames={measure.surface_candidates} "
            f"tail-closed grids={len(nets)}"
        )
        for start, payload, end, net in measure.surfaces[:6]:
            print(
                f"     abs={start} payload={payload} grid={net.start if net else '-'} "
                f"tail={end - (net.start + net.bytes) if net else '-'} "
                f"{_fmt_net(net)}"
            )
        data.close()
        handle.close()

    if not args.no_population:
        primary, carriers = split_facet_carriers(_census_rows(args.family))
        if args.limit:
            primary = primary[: args.limit]
        measured: list[tuple[str, RegionMeasure | None]] = []
        for sha in primary:
            handle, buf = _region_for(sha, manifest)
            measured.append((sha, measure_region(buf)))
            buf.close()
            handle.close()
        control: list[tuple[str, RegionMeasure | None]] = []
        for sha in carriers:
            handle, buf = _region_for(sha, manifest)
            control.append((sha, measure_region(buf)))
            buf.close()
            handle.close()
        rows.extend(population_claims(measured, control))
        total = sum(m.bytes for _, m in measured if m is not None)
        framed = sum(m.framed for _, m in measured if m is not None)
        content = sum(m.content_bytes for _, m in measured if m is not None)
        print(
            f"== population {len(measured)}: bytes={total} content={content} "
            f"framed={framed} coverage={_rate(framed, content)}"
        )
        print(
            "   surfaces="
            + str(sum(len(m.surfaces) for _, m in measured if m is not None))
            + " pole_points="
            + str(sum(m.surface_points for _, m in measured if m is not None))
        )

    write_claims(rows, args.out)
    exact = any(
        m.prefix is not None or any(s[3] is not None for s in m.surfaces)
        for _, m in anchor_measures
    )
    verdict = (
        "framing law + pole nets present -> the bulk carries exact-geometry point nets"
        if exact
        else "no pole net on the anchors -> report the blocker"
    )
    print("== verdict:", verdict)
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
