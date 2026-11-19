#!/usr/bin/env python3
"""Probe the E5 dialect of the pre-CGM bulk: ``e5 0d`` records, tiling, payloads.

Context (tickets #57 follow-up, 2026-11-19).  The bulk-stream probe
(``docs/evidence/2026-11-19-bulk-stream.md``) framed the ``CATPrtCont``
content stream of the 19 object-stream parts under the A/B length law and
left the other **103 of 128** no-facet regions unframed: their content
opens with a ``01``-framed writer block and continues with a marker this
repository had only named (``e5 0d``), never measured.  That note's
smallest next step was exactly this: recover the E5 record law "by the
same close-on-the-next-record test".

This probe answers three questions from bytes only.

1. **Do the ``e5 0d`` records frame?**  A record is

        e5 0d | flag:u8 | class:u16le | length:u32le | id:u32le | payload[length]

   with a 13-byte header.  The law is not assumed: the walk admits a
   record only when its length lands inside the region and the walk
   continues, and record runs are admitted only when they chain at least
   three records and close on their own end (zero residue).  What the
   probe measures is *closure*: how far the marker stream tiles, which
   bytes sit between runs, and what the run tails are.

2. **What do the payloads carry?**  Every payload is scanned for four
   byte-renderable shapes — f64 arrays (le IEEE doubles at a plausible
   model magnitude), f32 arrays (same, le floats), printable text, and
   small-integer arrays (u32le counts/ids) — and the **largest** shape
   per payload is counted, so the byte census never double-counts a span.
   The rest of the payload is reported as opaque.  For the f64 arrays the
   probe reports the largest 3-divisible run (candidate pole net) with
   its point count, bbox and rectangularity.

3. **Where is the coordinate array?**  A triple array is pinned with
   **both bases** (absolute file offset and ``CATPrtCont``-block-relative),
   its payload-relative offset, its owning record (offset/class/id), and
   validated by value: finite, model-scale bbox, and — where the array is
   a swept grid — the same rectangularity/monotonicity test the bulk
   probe uses.  No degree, knot, weight or surface semantics are claimed.

The report also records the two structural fields the format states about
itself: the ``01`` writer block (``total:u32le`` + ``name_len`` + name,
with ``content_bytes - total`` measured constant on the population) and
the ``e5 0d 06`` container record whose last ``u32le`` field is the byte
span of the record run that follows it.

Read-only over the corpus; ``src/`` and the exporter are untouched.

Run one anchor first, then the population::

  export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
  .venv/bin/python -I scripts/triage/probe_e5_bulk.py --anchor 00198dd9
  .venv/bin/python -I scripts/triage/probe_e5_bulk.py

Writes ``docs/evidence/data/e5-bulk-claims.csv``.  The population is the
128 no-facet stores of ``stage13-elementspace-census.csv`` (the same split
the bulk probe uses), filtered to the **108 regions where the ``e5 0d``
walk admits a chained record run**: the bulk probe's 103 E5-head regions
plus five it classified by head as f64-net/other, whose content opens
with a numeric allocation before the same records (claim ``E5-20``).
"""

from __future__ import annotations

import argparse
import csv
import math
import mmap
import struct
import sys
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
POPULATION = ROOT / "docs" / "evidence" / "data" / "stage13-elementspace-census.csv"
OUT_CLAIMS = ROOT / "docs" / "evidence" / "data" / "e5-bulk-claims.csv"

sys.path.insert(0, str(ROOT / "scripts" / "triage"))
sys.path.insert(0, str(ROOT / "src"))

import probe_bulk_stream as bulk  # noqa: E402  (metadata table + pole nets)
from catpart.brep import cgm_nurbs  # noqa: E402

CLAIM_FIELDS = ["claim", "scope", "observations", "passes", "rate", "label", "detail"]

#: The two-byte record marker.  Every admitted record starts with it; the
#: walk resumes only on it, so a marker-shaped coincidence inside a payload
#: is never visited as a record start.
E5_MARKER = b"\xe5\x0d"
#: ``e5 0d | flag | class:u16le | length:u32le | id:u32le``.
HEADER_BYTES = 13
#: A payload longer than this is a misread (the largest record measured in
#: the population is under 8 KiB).
MAX_PAYLOAD = 1 << 20
#: The container record before a run: ``e5 0d 06 01 00 <u32 field> <span>``
#: where ``span`` is the byte length of the run that follows.  This is a
#: measured field position, not an interpreted type.
CONTAINER_FLAG = 0x06

#: Payload shapes.  A run must be at least this long to be counted, so a
#: stray scalar cannot name a payload.
MIN_F64 = 4  # doubles (32 B)
MIN_F32 = 8  # floats (32 B)
MIN_INDEX = 4  # u32 words
MIN_TEXT = 8  # printable bytes

#: A model coordinate: finite, inside a 100 m envelope, and 0.0 allowed (a
#: profile may cross the origin).  The floor rejects the denormal band that
#: integer arrays alias as; the ceiling is the same one the bulk probe uses.
NUMBER_FLOOR = 1e-6
NUMBER_CEIL = 1e5

#: The 4-byte word the brief read as a visible f32 coordinate (-10.9097 mm
#: and its positive twin).  Counted to show where that reading comes from;
#: the f32 *run* measurement is what decides whether an f32 array exists.
F32_WORD_MARKERS = (b"\x80\x84\x2e\xc1", b"\x80\x84\x2e\x41")


@dataclass(frozen=True)
class WriterHeader:
    """The ``01``-framed writer block that opens the content stream."""

    offset: int  # block-relative
    total: int
    name_len: int
    name: str
    #: Bytes between the name and the first ``e5 0d`` marker (a class table
    #: that this probe does not interpret).  Set once the marker is known.
    tail: int = 0

    @property
    def end(self) -> int:
        return self.offset + 9 + self.name_len


@dataclass(frozen=True)
class E5Record:
    """One ``e5 0d`` record.  ``end`` is exclusive."""

    start: int
    flag: int
    cls: int
    length: int
    ident: int
    payload: int
    end: int


@dataclass(frozen=True)
class Cluster:
    """A contiguous run of >=3 records that closes on its own end."""

    start: int
    end: int
    records: int
    #: ``span`` field of the container record immediately before the run,
    #: or ``None`` when the run is not preceded by one.
    declared_span: int | None


@dataclass(frozen=True)
class TripleArray:
    """The largest 3-divisible f64 run in a payload (candidate point net)."""

    payload_offset: int
    points: int
    bbox: tuple[float, float, float, float, float, float]
    net: object  # probe_bulk_stream.PoleNet (kept opaque here)

    @property
    def bytes(self) -> int:
        return self.points * 24


@dataclass(frozen=True)
class PayloadCensus:
    """Byte census of one payload, exclusive: one shape plus opaque."""

    total: int
    f64: int
    f32: int
    index: int
    text: int
    kind: str
    f64_count: int
    f32_count: int

    @property
    def opaque(self) -> int:
        return self.total - self.f64 - self.f32 - self.index - self.text


@dataclass(frozen=True)
class RegionMeasure:
    """Everything the probe measures on one part's E5 bulk region."""

    block: int
    end: int
    metadata: object  # probe_bulk_stream.MetadataTable | None
    content: int
    header: WriterHeader | None
    clusters: tuple[Cluster, ...]
    gaps: tuple[tuple[int, int], ...]
    records: int
    follower: int  # records whose end lands on the next marker
    census: PayloadCensus
    triple_arrays: int
    triple_points: int
    #: Point runs that validate as a swept grid: rows>=3, cols>=3, spread
    #: under the bulk probe's 1% bar, and inside the 100 m model envelope.
    grids: int
    #: Single-row point runs (rows == 1) at model scale: a profile, a knot
    #: lane or a limit box, reported apart from the grids.
    row_runs: int
    largest_grid: tuple[int, TripleArray] | None  # largest validated grid
    f32_max: int
    f32_varied_max: int
    f32_grids: int
    f32_words: int
    flags: Counter
    classes: Counter
    id_monotone: bool
    tail: int
    #: ``rows x cols`` of every validated net, as a multiset.
    net_shapes: Counter
    #: Candidate row-count law: grids whose ``3 * u32le(payload+13)`` equals
    #: the row count the *data* factorisation reports.  ``(checked, hits)``.
    row_law: tuple[int, int]
    #: Payload length distribution: min, median, max, and the commonest.
    lengths: tuple[int, int, int, tuple[tuple[int, int], ...]]

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
    def residue(self) -> int:
        return self.content_bytes - self.framed

    @property
    def close_rate(self) -> float:
        return self.follower / self.records if self.records else 0.0

    @property
    def header_gap(self) -> int:
        """``content_bytes - total``; 131 on every region that opens with it."""
        return self.content_bytes - self.header.total if self.header else 0

    @property
    def prefix(self) -> int:
        """Bytes between the content start and the first admitted record."""
        return self.clusters[0].start - self.content if self.clusters else 0

    @property
    def head_class(self) -> str:
        """How the region opens before the record stream.

        ``writer``: the ``01`` writer block opens the content (the bulk
        probe's E5 head class).  ``prefix``: a numeric allocation opens it.
        ``bare``: the first record starts within 32 bytes of the content.
        """
        if self.header is not None:
            return "writer"
        return "prefix" if self.prefix >= 512 else "bare"


def u16le(data, off: int) -> int:
    return int.from_bytes(data[off : off + 2], "little")


def u32le(data, off: int) -> int:
    return int.from_bytes(data[off : off + 4], "little")


def parse_writer_header(data, lo: int, hi: int) -> WriterHeader | None:
    """Parse the ``01 | total:u32le | name_len:u32le | name`` writer block.

    The block is only admitted when the name length is sane, the name fits
    in the region, and every name byte is printable — so a ``01`` byte that
    happens to open a payload is not mistaken for the writer block.
    """
    if lo + 9 > hi or data[lo] != 0x01:
        return None
    total = u32le(data, lo + 1)
    name_len = u32le(data, lo + 5)
    if not (0 < name_len <= 64) or lo + 9 + name_len > hi:
        return None
    raw = bytes(data[lo + 9 : lo + 9 + name_len])
    if not all(32 <= byte < 127 for byte in raw):
        return None
    return WriterHeader(
        offset=lo, total=total, name_len=name_len, name=raw.decode("ascii")
    )


def parse_record(data, pos: int, hi: int) -> E5Record | None:
    """Parse one ``e5 0d`` record at ``pos``; ``None`` when it does not close.

    The flag is *retained, not whitelisted*: the corpus is what defines the
    flag vocabulary, and a length that does not land inside the region is
    refused regardless of the flag.  Closure is what admits a record, so an
    unknown flag shows up in the census instead of being silently dropped.
    """
    if pos + HEADER_BYTES > hi or data[pos : pos + 2] != E5_MARKER:
        return None
    length = u32le(data, pos + 5)
    if length > MAX_PAYLOAD:
        return None
    end = pos + HEADER_BYTES + length
    if end > hi:
        return None
    return E5Record(
        start=pos,
        flag=data[pos + 2],
        cls=u16le(data, pos + 3),
        length=length,
        ident=u32le(data, pos + 9),
        payload=pos + HEADER_BYTES,
        end=end,
    )


def walk(data, lo: int, hi: int) -> tuple[list[E5Record], int]:
    """Greedily walk records from ``lo``; return the records and the stop."""
    records: list[E5Record] = []
    pos = lo
    while pos < hi:
        record = parse_record(data, pos, hi)
        if record is None:
            break
        records.append(record)
        pos = record.end
    return records, pos


def _container_span(data, start: int) -> int | None:
    """``span`` of the ``06`` container header that ends exactly at ``start``.

    The container is a **header-only** record: the same 13 bytes, but its
    body is the run that follows, and the slot that carries a payload
    length on an ordinary record carries the span there.  So it is read
    from the header alone — ``parse_record`` would reject it, because its
    declared length does not describe its own bytes.
    """
    pos = start - HEADER_BYTES
    if pos < 0 or pos + HEADER_BYTES > start:
        return None
    # The container signature measured on every population file: marker,
    # flag 0x06, class 1 (`01 00`).  Without the class bytes the two bytes
    # before a run can belong to the previous record's tail, and a
    # coincidental 0x06 there would read as a container.
    if data[pos : pos + 5] != E5_MARKER + bytes([CONTAINER_FLAG, 0x01, 0x00]):
        return None
    return u32le(data, pos + 9)


def clusters(data, lo: int, hi: int, min_chain: int = 3) -> tuple[Cluster, ...]:
    """Contiguous record runs of at least ``min_chain`` records.

    A short accidental parse is not admitted, and a run must close on its
    own end.  The byte scan resumes after each admitted run, so the runs
    partition the framed part of the stream and everything between them is
    reported as a measured gap rather than as noise.
    """
    out: list[Cluster] = []
    pos = lo
    while pos < hi - HEADER_BYTES:
        if parse_record(data, pos, hi) is None:
            pos += 1
            continue
        records, end = walk(data, pos, hi)
        if len(records) >= min_chain:
            out.append(
                Cluster(
                    start=pos,
                    end=end,
                    records=len(records),
                    declared_span=_container_span(data, pos),
                )
            )
            pos = end
        else:
            pos += 1
    return tuple(out)


def _number_ok(value: float) -> bool:
    return math.isfinite(value) and (
        value == 0.0 or NUMBER_FLOOR <= abs(value) <= NUMBER_CEIL
    )


def numeric_run(data, lo: int, hi: int, fmt: str, size: int, ok) -> tuple[int, int]:
    """Longest run of values passing ``ok``, at any byte phase.

    The phase is not assumed: these payloads store their arrays at every
    alignment.  ``(count, start)`` is returned; a run of zero means the
    span carries no such array.
    """
    best = (0, lo)
    for phase in range(size):
        pos = lo + phase
        current = 0
        start = pos
        while pos + size <= hi:
            if ok(struct.unpack_from(fmt, data, pos)[0]):
                if current == 0:
                    start = pos
                current += 1
                if current > best[0]:
                    best = (current, start)
            else:
                current = 0
            pos += size
    return best


def text_run(data, lo: int, hi: int) -> tuple[int, int]:
    """Longest run of printable ASCII bytes (0x20..0x7e)."""
    best = (0, lo)
    current = 0
    start = lo
    for pos in range(lo, hi):
        if 32 <= data[pos] < 127:
            if current == 0:
                start = pos
            current += 1
            if current > best[0]:
                best = (current, start)
        else:
            current = 0
    return best


def _index_ok(value: int) -> bool:
    """A count: a 12-bit word, the band the multiplicity lists live in.

    The bar is deliberately far below 2**16: an f64 payload also renders as
    u32 words below 65535 in long stretches, so a 16-bit bar would call the
    byte soup of a coordinate array an "index array".
    """
    return value <= 0x0FFF


def _varied(data, start: int, count: int, fmt: str, size: int, kind: str) -> bool:
    """A numeric array must *vary*: no zero padding, no one-value run.

    A run of plausible numbers is not yet an array — a payload of zeros, or
    a handful of ±10.9097 words padded with zeros, also renders as one.  So
    a float array must be mostly nonzero, must not be dominated by a single
    value, and must carry at least four distinct values.  A count array is
    *allowed* to repeat (a multiplicity list is `6,3,3,3,...,6`); it only
    has to hold two distinct values, which a zero field does not.
    """
    if count <= 0:
        return False
    values = [struct.unpack_from(fmt, data, start + size * i)[0] for i in range(count)]
    distinct = len(set(values))
    if kind == "index":
        return distinct >= 2
    nonzero = sum(1 for value in values if value != 0.0)
    top = Counter(values).most_common(1)[0][1]
    magnitude = max(abs(value) for value in values)
    # A run of one magnitude is a word pattern read at a step, not an array:
    # a 16-bit reference list renders as 55 "floats" of 3.08e-05 each.  A
    # real array spans a band, so require the band to be a visible fraction
    # of the magnitude.  This is the test that keeps aliasing out of the
    # f32 bucket without assuming anything about the payload's semantics.
    if magnitude > 0 and max(values) - min(values) < 1e-3 * magnitude:
        return False
    return distinct >= 4 and 2 * nonzero >= count and 2 * top <= count


def census_payload(data, lo: int, hi: int) -> PayloadCensus:
    """Classify one payload by its **longest** renderable shape.

    Exactly one shape owns the bytes, so the census is a partition: the
    reported bytes never overlap and ``opaque`` is the remainder.
    """
    total = hi - lo
    f64_count, f64_start = numeric_run(data, lo, hi, "<d", 8, _number_ok)
    f32_count, f32_start = numeric_run(data, lo, hi, "<f", 4, _number_ok)
    index_count, index_start = numeric_run(data, lo, hi, "<I", 4, _index_ok)
    text_count, _ = text_run(data, lo, hi)
    if f64_count < MIN_F64 or not _varied(
        data, f64_start, f64_count, "<d", 8, "f64"
    ):
        f64_count = 0
    if f32_count < MIN_F32 or not _varied(
        data, f32_start, f32_count, "<f", 4, "f32"
    ):
        f32_count = 0
    if index_count < MIN_INDEX or not _varied(
        data, index_start, index_count, "<I", 4, "index"
    ):
        index_count = 0
    shapes = {
        "f64": f64_count * 8,
        "f32": f32_count * 4,
        "index": index_count * 4,
        "text": text_count if text_count >= MIN_TEXT else 0,
    }
    # Ties go to the wider element type: a f32 run inside an f64 array is a
    # shadow of the same bytes, so the double array must win.
    order = ["f64", "text", "index", "f32"]
    kind = max(order, key=lambda name: (shapes[name], -order.index(name)))
    if shapes[kind] < 0.25 * total:
        kind = "opaque"
    return PayloadCensus(
        total=total,
        f64=shapes["f64"],
        f32=shapes["f32"],
        index=shapes["index"],
        text=shapes["text"],
        kind=kind,
        f64_count=f64_count,
        f32_count=f32_count,
    )


def _is_grid(net) -> bool:
    """A swept grid: at least 3 rows x 3 columns, flat within rows, model-scale.

    The bulk probe's ``PoleNet.ok`` also accepts a single-row point list,
    because a row of one station trivially has zero spread.  For this probe
    that is a different object (a profile or a limit box), so grids are
    counted with the stricter shape and single-row runs are reported apart.
    """
    return (
        net.rows >= 3
        and net.cols >= 3
        and net.spread <= bulk.GRID_SPREAD_BAR
        and net.scale_ok
    )


def _f32_net(data, start: int, count: int) -> object | None:
    """Decode an f32 triple run as a point net, if it forms one.

    The only question this answers is whether the dialect carries an **f32**
    coordinate array: a run that divides by three is fed through the same
    pole-net test the f64 arrays get.  A byte pattern that renders as floats
    (a reference list, a limit box) does not produce a rectangular or
    planar point net, so it cannot be mistaken for coordinates.
    """
    if count < 3 * MIN_F32 or count % 3:
        return None
    points = [
        struct.unpack_from("<3f", data, start + 12 * i) for i in range(count // 3)
    ]
    return bulk.pole_net(points, start)


def triple_array(
    data, lo: int, hi: int
) -> tuple[TripleArray | None, int, object | None, int]:
    """Largest 3-divisible f64 run in a payload, plus the f32 measurements.

    The candidate net is the longest run of plausible doubles; it is only
    reported as a point set when its count divides by three.  Extent is
    two-sided by construction: the run starts and ends where the payload
    stops rendering as plausible model doubles.
    """
    count, start = numeric_run(data, lo, hi, "<d", 8, _number_ok)
    f32_count, f32_start = numeric_run(data, lo, hi, "<f", 4, _number_ok)
    f32_net = _f32_net(data, f32_start, f32_count)
    f32_varied = (
        f32_count if _varied(data, f32_start, f32_count, "<f", 4, "f32") else 0
    )
    if count < 3 * MIN_F64 or count % 3:
        return None, f32_count, f32_net, f32_varied
    points = [
        struct.unpack_from("<3d", data, start + 24 * i) for i in range(count // 3)
    ]
    axes = [[point[i] for point in points] for i in range(3)]
    bbox = (
        min(axes[0]),
        max(axes[0]),
        min(axes[1]),
        max(axes[1]),
        min(axes[2]),
        max(axes[2]),
    )
    return (
        TripleArray(
            payload_offset=start - lo,
            points=len(points),
            bbox=bbox,
            net=bulk.pole_net(points, start),
        ),
        f32_count,
        f32_net,
        f32_varied,
    )


def measure_region(data) -> RegionMeasure | None:
    """Measure the ``CATPrtCont`` content stream of one part."""
    regions = cgm_nurbs.valid_regions(data)
    for index, (block, name, _) in enumerate(regions):
        if name != "CATPrtCont":
            continue
        end = regions[index + 1][0] if index + 1 < len(regions) else len(data)
        table = bulk.parse_metadata_table(data, block, end)
        content = block + (table.end if table is not None else 0)
        if table is None:
            content = end
        header = parse_writer_header(data, content, end)
        found = clusters(data, content, end)
        if header is not None and found:
            marker = data.find(E5_MARKER, header.end, found[0].start)
            stop = marker if marker >= 0 else found[0].start
            header = replace(header, tail=max(0, stop - header.end))
        gaps: list[tuple[int, int]] = []
        previous = content
        for cluster in found:
            if cluster.start > previous:
                gaps.append((previous, cluster.start))
            previous = cluster.end
        if previous < end:
            gaps.append((previous, end))

        records: list[E5Record] = []
        for cluster in found:
            run, _ = walk(data, cluster.start, cluster.end)
            records.extend(run)
        follower = 0
        for record in records:
            if record.end < end and data[record.end : record.end + 2] == E5_MARKER:
                follower += 1

        census = PayloadCensus(0, 0, 0, 0, 0, "opaque", 0, 0)
        arrays = 0
        points = 0
        grids = 0
        row_runs = 0
        largest_grid: tuple[int, TripleArray] | None = None
        f32_max = 0
        f32_varied_max = 0
        f32_grids = 0
        f32_words = 0
        net_shapes: Counter = Counter()
        lengths: Counter = Counter()
        law_checked = 0
        law_hits = 0
        flags: Counter = Counter()
        classes: Counter = Counter()
        previous_id = -1
        id_monotone = True
        for record in records:
            flags[record.flag] += 1
            classes[record.cls] += 1
            if record.ident < previous_id:
                id_monotone = False
            previous_id = record.ident
            lengths[record.length] += 1
            part = census_payload(data, record.payload, record.end)
            census = PayloadCensus(
                total=census.total + part.total,
                f64=census.f64 + part.f64,
                f32=census.f32 + part.f32,
                index=census.index + part.index,
                text=census.text + part.text,
                kind="opaque",
                f64_count=census.f64_count + part.f64_count,
                f32_count=census.f32_count + part.f32_count,
            )
            array, f32_count, f32_net, f32_varied = triple_array(
                data, record.payload, record.end
            )
            f32_max = max(f32_max, f32_count)
            f32_varied_max = max(f32_varied_max, f32_varied)
            if f32_net is not None and _is_grid(f32_net):
                f32_grids += 1
            if array is not None:
                arrays += 1
                points += array.points
                net = array.net
                if _is_grid(net):
                    grids += 1
                    net_shapes[(net.rows, net.cols)] += 1
                    if data[record.payload] == 0x80:
                        law_checked += 1
                        if 3 * u32le(data, record.payload + 13) == net.rows:
                            law_hits += 1
                    if largest_grid is None or array.points > largest_grid[1].points:
                        largest_grid = (record.start, array)
                elif net.rows == 1 and net.scale_ok:
                    row_runs += 1
            f32_words += sum(
                bytes(data[record.payload : record.end]).count(word)
                for word in F32_WORD_MARKERS
            )
        return RegionMeasure(
            block=block,
            end=end,
            metadata=table,
            content=content,
            header=header,
            clusters=found,
            gaps=tuple(gaps),
            records=len(records),
            follower=follower,
            census=census,
            triple_arrays=arrays,
            triple_points=points,
            grids=grids,
            row_runs=row_runs,
            largest_grid=largest_grid,
            f32_max=f32_max,
            f32_varied_max=f32_varied_max,
            f32_grids=f32_grids,
            f32_words=f32_words,
            flags=flags,
            classes=classes,
            id_monotone=id_monotone,
            tail=(end - found[-1].end) if found else end - content,
            net_shapes=net_shapes,
            row_law=(law_checked, law_hits),
            lengths=(
                min(lengths) if lengths else 0,
                sorted(lengths.elements())[sum(lengths.values()) // 2] if lengths else 0,
                max(lengths) if lengths else 0,
                tuple(lengths.most_common(5)),
            ),
        )
    return None


def _load_manifest() -> dict[str, str]:
    with MANIFEST.open(newline="", encoding="utf-8") as handle:
        return {row["sha256"]: row["local_path"] for row in csv.DictReader(handle)}


def _census_rows(family: str) -> list[dict]:
    with POPULATION.open(newline="", encoding="utf-8") as handle:
        return [row for row in csv.DictReader(handle) if row["family"] == family]


def _region_for(sha: str, manifest: dict[str, str]):
    path = next((value for key, value in manifest.items() if key.startswith(sha)), None)
    if path is None:
        raise SystemExit(f"{sha} not in the manifest")
    handle = (ROOT / path).open("rb")
    return handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)


def _rate(num: int, den: int) -> str:
    return "" if den <= 0 else f"{num / den:.4f}"


def _fmt_net(array: TripleArray | None) -> str:
    if array is None:
        return "none"
    net = array.net
    return (
        f"points={array.points} rows={net.rows} cols={net.cols} "
        f"axis={'xyz'[net.station_axis]} spread={net.spread:.4f} "
        f"monotone={int(net.monotone)} scale_ok={int(net.scale_ok)}"
    )


def anchor_claims(sha: str, measure: RegionMeasure, data) -> list[list[str]]:
    """Claim rows for one worked anchor (both bases in ``detail``)."""
    rows: list[list[str]] = []
    header = measure.header
    rows.append(
        [
            "E5-01",
            sha,
            "1",
            "1" if header is not None else "0",
            _rate(measure.header_gap, 131),
            "fact",
            f"CATPrtCont abs=[{measure.block}, {measure.end}) bytes={measure.bytes} "
            f"content_start={measure.content} (block+{measure.content - measure.block}) "
            f"header={'01 total=' + str(header.total) + ' name=' + repr(header.name) + ' end=block+' + str(header.end - measure.block) + ' tail=' + str(header.tail) if header else 'none'} "
            f"content_bytes={measure.content_bytes} header_gap={measure.header_gap}",
        ]
    )
    rows.append(
        [
            "E5-02",
            sha,
            str(measure.records),
            str(len(measure.clusters)),
            _rate(measure.framed, measure.content_bytes),
            "fact",
            f"e5 0d walk: clusters={len(measure.clusters)} records={measure.records} "
            f"framed={measure.framed} content={measure.content_bytes} "
            f"residue={measure.residue} coverage={_rate(measure.framed, measure.content_bytes)} "
            f"close_rate={_rate(measure.follower, measure.records)} "
            f"tail={measure.tail} gaps="
            + ",".join(f"{b - a}@{a}" for a, b in measure.gaps),
        ]
    )
    rows.append(
        [
            "E5-03",
            sha,
            str(measure.triple_arrays),
            str(measure.grids),
            _rate(measure.grids, measure.triple_arrays),
            "fact",
            f"f64 triple arrays={measure.triple_arrays} points={measure.triple_points} "
            f"grids={measure.grids} row_runs={measure.row_runs}",
        ]
    )
    if measure.largest_grid is not None:
        record_start, array = measure.largest_grid
        net = array.net
        owning = next(
            (
                record
                for cluster in measure.clusters
                for record in walk(data, cluster.start, cluster.end)[0]
                if record.start == record_start
            ),
            None,
        )
        rows.append(
            [
                "E5-04",
                sha,
                str(array.points),
                "1" if net.ok else "0",
                "",
                "fact",
                f"largest validated net: record abs={record_start} "
                f"(block+{record_start - measure.block}) "
                f"class=0x{owning.cls:04x} id={owning.ident} "
                f"payload abs={record_start + HEADER_BYTES} payload_off={array.payload_offset} "
                f"grid abs={record_start + HEADER_BYTES + array.payload_offset} "
                f"(block+{record_start + HEADER_BYTES + array.payload_offset - measure.block}) "
                f"points={array.points} rows={net.rows} cols={net.cols} "
                f"spread={net.spread:.6f} monotone={int(net.monotone)} "
                f"aabb=({array.bbox[0]:.3f},{array.bbox[1]:.3f},"
                f"{array.bbox[2]:.3f},{array.bbox[3]:.3f},"
                f"{array.bbox[4]:.3f},{array.bbox[5]:.3f})",
            ]
        )
    census = measure.census
    rows.append(
        [
            "E5-05",
            sha,
            str(census.total),
            str(census.f64),
            _rate(census.f64, census.total),
            "fact",
            f"payload bytes: total={census.total} f64={census.f64} f32={census.f32} "
            f"index={census.index} text={census.text} opaque={census.opaque}; "
            f"longest f32 run={measure.f32_max} floats "
            f"(varied run={measure.f32_varied_max}, +/-10.9097 words={measure.f32_words})",
        ]
    )
    flags = " ".join(f"{flag:02x}={count}" for flag, count in measure.flags.most_common())
    rows.append(
        [
            "E5-06",
            sha,
            str(len(measure.flags)),
            str(int(measure.id_monotone)),
            "",
            "fact",
            f"flags: {flags}; classes={len(measure.classes)} "
            f"top={','.join(f'0x{cls:04x}:{count}' for cls, count in measure.classes.most_common(8))}",
        ]
    )
    for start, span in [(c.start, c.declared_span) for c in measure.clusters][:4]:
        if span is None:
            continue
        cluster = next(c for c in measure.clusters if c.start == start)
        rows.append(
            [
                "E5-07",
                sha,
                str(cluster.records),
                "1" if start + span == cluster.end else "0",
                "",
                "fact",
                f"container before run abs={start - HEADER_BYTES} "
                f"(block+{start - HEADER_BYTES - measure.block}) declared_span={span} "
                f"actual={cluster.end - start} records={cluster.records}",
            ]
        )
    return rows


def population_claims(
    primary: list[tuple[str, RegionMeasure | None]],
) -> list[list[str]]:
    """Aggregate claims over the regions that carry a record run."""
    regions = [m for _, m in primary if m is not None]
    files = len(primary)
    scope = f"population:{len(regions)}"
    content = sum(m.content_bytes for m in regions)
    framed = sum(m.framed for m in regions)
    records = sum(m.records for m in regions)
    clusters = sum(len(m.clusters) for m in regions)
    headers = [m for m in regions if m.header is not None]
    gaps = [gap for m in regions for gap in m.gaps]
    census = PayloadCensus(
        total=sum(m.census.total for m in regions),
        f64=sum(m.census.f64 for m in regions),
        f32=sum(m.census.f32 for m in regions),
        index=sum(m.census.index for m in regions),
        text=sum(m.census.text for m in regions),
        kind="opaque",
        f64_count=0,
        f32_count=0,
    )
    flags: Counter = Counter()
    classes: Counter = Counter()
    shapes: Counter = Counter()
    names: Counter = Counter()
    for measure in regions:
        flags.update(measure.flags)
        classes.update(measure.classes)
        shapes.update(measure.net_shapes)
        if measure.header is not None:
            names[measure.header.name] += 1
    rows = [
        [
            "E5-10",
            scope,
            str(records),
            str(len(regions)),
            _rate(framed, content),
            "fact",
            f"E5 regions={len(regions)}/{files} content={content} framed={framed} "
            f"residue={content - framed} coverage={_rate(framed, content)} "
            f"records={records} clusters={clusters} "
            f"clusters_per_region={clusters / max(len(regions), 1):.2f} "
    f"families_of_the_split=128",
        ],
        [
            "E5-11",
            scope,
            str(len(headers)),
            str(sum(1 for m in headers if m.header_gap == 131)),
            _rate(sum(1 for m in headers if m.header_gap == 131), len(headers)),
            "fact",
            f"writer header at content start: {len(headers)}/{len(regions)} regions; "
            f"content_bytes-total==131 on "
            f"{sum(1 for m in headers if m.header_gap == 131)}/{len(headers)}; "
            f"header total_size range="
            f"{min((m.header.total for m in headers), default=0)}.."
            f"{max((m.header.total for m in headers), default=0)}",
        ],
        [
            "E5-12",
            scope,
            str(clusters),
            str(sum(1 for c in (c for m in regions for c in m.clusters) if c.declared_span is not None)),
            _rate(
                sum(
                    1
                    for m in regions
                    for c in m.clusters
                    if c.declared_span == c.end - c.start
                ),
                clusters,
            ),
            "fact",
            "container-declared runs: "
            f"{sum(1 for m in regions for c in m.clusters if c.declared_span is not None)}/{clusters} "
            "clusters preceded by a 06 container; span==actual on "
            f"{sum(1 for m in regions for c in m.clusters if c.declared_span == c.end - c.start)}",
        ],
        [
            "E5-13",
            scope,
            str(records),
            str(len(flags)),
            "",
            "fact",
            "flags: " + " ".join(f"{f:02x}={c}" for f, c in flags.most_common()),
        ],
        [
            "E5-14",
            scope,
            str(records),
            str(sum(1 for m in regions if m.id_monotone)),
            _rate(sum(1 for m in regions if m.id_monotone), len(regions)),
            "fact",
            f"record ids monotone in {sum(1 for m in regions if m.id_monotone)}/"
            f"{len(regions)} regions; close_rate="
            f"{_rate(sum(m.follower for m in regions), records)} "
            f"(records whose end lands on the next e5 0d marker)",
        ],
        [
            "E5-15",
            scope,
            str(census.total),
            str(census.f64 + census.index + census.text + census.f32),
            _rate(census.total - census.opaque, census.total),
            "fact",
            f"payload bytes total={census.total} f64={census.f64} f32={census.f32} "
            f"index={census.index} text={census.text} opaque={census.opaque} "
            f"shaped_rate={_rate(census.total - census.opaque, census.total)}",
        ],
        [
            "E5-16",
            scope,
            str(sum(m.triple_arrays for m in regions)),
            str(sum(m.grids for m in regions)),
            _rate(
                sum(m.grids for m in regions),
                sum(m.triple_arrays for m in regions),
            ),
            "fact",
            f"f64 triple arrays={sum(m.triple_arrays for m in regions)} "
            f"array_bytes={sum(m.triple_points for m in regions) * 24} "
            f"grids={sum(m.grids for m in regions)} "
            f"row_runs={sum(m.row_runs for m in regions)} "
            f"regions_with_arrays={sum(1 for m in regions if m.triple_arrays)}",
        ],
        [
            "E5-17",
            scope,
            str(sum(m.f32_grids for m in regions)),
            str(max((m.f32_max for m in regions), default=0)),
            _rate(sum(m.f32_grids for m in regions), records),
            "fact",
            "f32 coordinate arrays: f32 triple grids="
            f"{sum(m.f32_grids for m in regions)}; longest plausible f32 run="
            f"{max((m.f32_max for m in regions), default=0)} floats (zeros allowed, "
            "so a ±1e6 limit box renders as one); median of region maxima="
            f"{sorted(m.f32_max for m in regions)[len(regions) // 2]}; "
            f"(+/-10.9097) 4-byte words={sum(m.f32_words for m in regions)}",
        ],
        [
            "E5-18",
            scope,
            str(len(gaps)),
            str(sum(1 for a, b in gaps if b - a <= 256)),
            _rate(sum(1 for a, b in gaps if b - a <= 256), len(gaps)),
            "fact",
            f"gaps between record runs={len(gaps)} bytes={sum(b - a for a, b in gaps)}; "
            f"<=256 B={sum(1 for a, b in gaps if b - a <= 256)}; "
            f"largest=" + ",".join(str(b - a) for a, b in sorted(gaps, key=lambda g: g[1] - g[0])[-5:]),
        ],
    ]
    rows.append(
        [
            "E5-21",
            scope,
            str(sum(shapes.values())),
            str(len(shapes)),
            _rate(sum(shapes.values()), max(sum(m.triple_arrays for m in regions), 1)),
            "fact",
            "grid shapes(rows x cols): "
            + " ".join(
                f"{rows}x{cols}:{count}" for (rows, cols), count in shapes.most_common(10)
            ),
        ]
    )
    rows.append(
        [
            "E5-22",
            scope,
            str(len(names)),
            str(sum(names.values())),
            _rate(sum(names.values()), len(regions)),
            "fact",
            "writer names: "
            + ";".join(f"{name!r}:{count}" for name, count in names.most_common(8))
            + "; record payload length: region min "
            f"{min(m.lengths[0] for m in regions)}, medians "
            f"{sorted(m.lengths[1] for m in regions)[len(regions) // 2]}, region max "
            f"{max(m.lengths[2] for m in regions)}",
        ]
    )
    checked = sum(m.row_law[0] for m in regions)
    hits = sum(m.row_law[1] for m in regions)
    rows.append(
        [
            "E5-23",
            scope,
            str(checked),
            str(hits),
            _rate(hits, checked),
            "candidate",
            "grid row law candidate: 3 * u32le(payload+13) == rows on "
            f"{hits}/{checked} validated grids (rows>=3, cols>=3) whose payload "
            "opens with 0x80; not a header field the format states about itself",
        ]
    )
    outlier = [m for m in regions if m.header is None]
    heads = Counter(m.head_class for m in regions)
    rows.append(
        [
            "E5-19",
            scope,
            str(len(outlier)),
            str(sum(1 for m in outlier if m.records)),
            _rate(sum(m.framed for m in outlier), sum(m.content_bytes for m in outlier)),
            "fact",
            "content head: "
            + " ".join(f"{name}={count}" for name, count in sorted(heads.items()))
            + "; regions without a content-start writer header: "
            + ";".join(
                f"head={m.head_class} prefix={m.prefix} bytes={m.content_bytes} "
                f"framed={m.framed} records={m.records}"
                for m in outlier
            ),
        ]
    )
    rows.append(
        [
            "E5-20",
            scope,
            str(len(regions)),
            str(heads["writer"]),
            _rate(heads["writer"], len(regions)),
            "fact",
            "regions carrying e5 0d records="
            f"{len(regions)}; head=writer {heads['writer']} (the bulk probe's "
            f"E5 head class), head=prefix {heads['prefix']} (bulk probe: f64-net "
            f"head), head=bare {heads['bare']}; content of all law-bearing "
            f"regions={content} B",
        ]
    )
    return rows


def _print_region(data, measure: RegionMeasure) -> None:
    print(
        f"   bytes={measure.bytes} content_start={measure.content} "
        f"content={measure.content_bytes}"
    )
    if measure.header is not None:
        print(
            f"   writer header block+{measure.header.offset - measure.block} "
            f"total={measure.header.total} name={measure.header.name!r} "
            f"content-total={measure.header_gap}"
        )
    for cluster in measure.clusters:
        print(
            f"   cluster block+{cluster.start - measure.block}.."
            f"{cluster.end - measure.block} records={cluster.records} "
            f"declared={cluster.declared_span} actual={cluster.end - cluster.start}"
        )
    records, _ = walk(data, measure.clusters[0].start, measure.clusters[0].end) if measure.clusters else ([], 0)
    for record in records[:8]:
        print(
            f"     abs={record.start:8d} flag=0x{record.flag:02x} "
            f"class=0x{record.cls:04x} len={record.length:6d} id={record.ident}"
        )
    print(
        f"   payload: total={measure.census.total} f64={measure.census.f64} "
        f"f32={measure.census.f32} index={measure.census.index} "
        f"text={measure.census.text} opaque={measure.census.opaque}"
    )
    print(
        f"   arrays={measure.triple_arrays} points={measure.triple_points} "
        f"grids={measure.grids} row_runs={measure.row_runs} "
        f"f32max={measure.f32_max} f32grids={measure.f32_grids} "
        f"words={measure.f32_words}"
    )
    if measure.largest_grid is not None:
        start, array = measure.largest_grid
        net = array.net
        print(
            f"   largest validated net: record abs={start} block+{start - measure.block} "
            f"payload_off={array.payload_offset} grid abs="
            f"{start + HEADER_BYTES + array.payload_offset} block+"
            f"{start + HEADER_BYTES + array.payload_offset - measure.block} "
            f"{_fmt_net(array)} bbox={tuple(round(v, 3) for v in array.bbox)}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--anchor",
        default="00198dd9,07d3c70b,0f0ff88b",
        help="comma-separated sha16 of the worked anchors",
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

    for sha in (part.strip() for part in args.anchor.split(",") if part.strip()):
        handle, data = _region_for(sha, manifest)
        measure = measure_region(data)
        if measure is None:
            raise SystemExit(f"no CATPrtCont region in {sha}")
        rows.extend(anchor_claims(sha, measure, data))
        print(f"== anchor {sha}: CATPrtCont abs {measure.block}..{measure.end}")
        _print_region(data, measure)
        data.close()
        handle.close()

    if not args.no_population:
        primary, _ = bulk.split_facet_carriers(_census_rows(args.family))
        if args.limit:
            primary = primary[: args.limit]
        measured: list[tuple[str, RegionMeasure | None]] = []
        for sha in primary:
            handle, buf = _region_for(sha, manifest)
            measured.append((sha, measure_region(buf)))
            buf.close()
            handle.close()
        e5 = [(sha, m) for sha, m in measured if m is not None and m.records]
        if len(e5) != len(measured):
            print(
                f"   note: {len(measured) - len(e5)} regions of the family carry no "
                "e5 0d record run (the bulk probe's object-stream dialect)"
            )
        rows.extend(population_claims(e5))
        content = sum(m.content_bytes for _, m in e5)
        framed = sum(m.framed for _, m in e5)
        print(
            f"== population {len(e5)}: content={content} framed={framed} "
            f"coverage={_rate(framed, content)} records="
            f"{sum(m.records for _, m in e5)}"
        )
        print(
            "   payload bytes: "
            f"f64={sum(m.census.f64 for _, m in e5)} "
            f"f32={sum(m.census.f32 for _, m in e5)} "
            f"index={sum(m.census.index for _, m in e5)} "
            f"text={sum(m.census.text for _, m in e5)} "
            f"opaque={sum(m.census.opaque for _, m in e5)}"
        )
        print(
            f"   triple arrays={sum(m.triple_arrays for _, m in e5)} "
            f"points={sum(m.triple_points for _, m in e5)} "
            f"grids={sum(m.grids for _, m in e5)} "
            f"f32max={max((m.f32_max for _, m in e5), default=0)}"
        )

    write_claims(rows, args.out)
    verdict = (
        "e5 0d records tile the E5 bulk; payloads are f64 arrays (+ index/text), "
        "no f32 arrays"
        if rows
        else "no E5 region measured -> report the blocker"
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
