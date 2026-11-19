"""Corpus-free tests for the E5 bulk-dialect probe (2026-11-19).

The probe (``scripts/triage/probe_e5_bulk.py``) frames the ``e5 0d``
dialect of the ``CATPrtCont`` content stream: the 13-byte record header,
the writer block that opens the content, the ``06`` container that declares
the span of a record run, and the payload census (f64 arrays, f32 arrays,
small-integer arrays, text).  These tests build every ingredient from bytes
and pin the decisions the evidence note rests on:

- a record is ``e5 0d | flag | class:u16le | length:u32le | id:u32le`` and
  its payload starts 13 bytes in; a wrong marker or a length that overruns
  the region is refused;
- the walk admits chained records, the cluster pass requires three in a row
  and reports the remainder as residue;
- the ``06`` container is header-only: its length slot does not describe its
  own bytes and its last ``u32le`` is the span of the following run, so a
  ``parse_record`` reading of it is wrong by construction;
- the payload census partitions bytes by the longest *varied* renderable
  shape, so a zero field never names a payload and a f64 array is not
  re-counted as f32;
- the triple-array decoder reports points, bbox and a rectangularity check.

Fixtures are synthetic; no corpus binary is read.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "triage"))

import probe_e5_bulk as probe  # noqa: E402


def u32le(*vals: int) -> bytes:
    return b"".join(struct.pack("<I", v) for v in vals)


def u16le(*vals: int) -> bytes:
    return b"".join(struct.pack("<H", v) for v in vals)


def f64le(*vals: float) -> bytes:
    return b"".join(struct.pack("<d", v) for v in vals)


def f32le(*vals: float) -> bytes:
    return b"".join(struct.pack("<f", v) for v in vals)


def writer_header(name: str = "V5R12-TEST:012003", total: int = 1000) -> bytes:
    """``01 | total:u32le | name_len:u32le | name``."""
    raw = name.encode("ascii")
    return b"\x01" + u32le(total) + u32le(len(raw)) + raw


def record(cls: int, payload: bytes, flag: int = 0x03, ident: int = 1) -> bytes:
    """One ``e5 0d`` record: marker, flag, class, length, id, payload."""
    return (
        b"\xe5\x0d"
        + bytes([flag])
        + u16le(cls)
        + u32le(len(payload))
        + u32le(ident)
        + payload
    )


def container(span: int, field: int = 78) -> bytes:
    """The header-only ``06`` container: its two u32 slots are field, span."""
    return b"\xe5\x0d" + bytes([0x06]) + u16le(1) + u32le(field) + u32le(span)


def swept_net(rows: int = 6, cols: int = 5) -> list[tuple[float, float, float]]:
    """A station-constant grid: z advances per row, x/y trace a profile."""
    points = []
    for row in range(rows):
        for col in range(cols):
            points.append(
                (
                    4000.0 + row * 130.0 + col * 0.5,
                    900.0 - col * 80.0,
                    -300.0 + row * 20.0,
                )
            )
    return points


def net_bytes(points: list[tuple[float, float, float]]) -> bytes:
    return b"".join(f64le(*point) for point in points)


# ------------------------------------------------------------ writer block


def test_writer_header_parses_total_name_and_end() -> None:
    banner = writer_header("V5R11-TCX:XP", total=5488)
    parsed = probe.parse_writer_header(banner, 0, len(banner))
    assert parsed is not None
    assert parsed.total == 5488
    assert parsed.name == "V5R11-TCX:XP"
    assert parsed.name_len == 12
    assert parsed.end == len(banner)


def test_writer_header_refuses_non_printable_name() -> None:
    banner = bytearray(writer_header("V5R11-TCX:XP"))
    banner[9] = 0x00
    assert probe.parse_writer_header(bytes(banner), 0, len(banner)) is None


def test_writer_header_refuses_absurd_name_length() -> None:
    banner = b"\x01" + u32le(10) + u32le(4096) + b"ab"
    assert probe.parse_writer_header(banner, 0, len(banner)) is None


# ----------------------------------------------------------------- record


def test_record_fields_and_payload_offset() -> None:
    payload = bytes(range(20))
    raw = record(0x00E7, payload, flag=0x43, ident=469)
    parsed = probe.parse_record(raw, 0, len(raw))
    assert parsed is not None
    assert parsed.flag == 0x43
    assert parsed.cls == 0x00E7
    assert parsed.length == 20
    assert parsed.ident == 469
    assert parsed.payload == probe.HEADER_BYTES
    assert parsed.end == len(raw)


def test_record_class_is_u16_not_u8() -> None:
    # 0x0209 needs both class bytes: a one-byte class would read 0x09.
    raw = record(0x0209, b"abcd")
    parsed = probe.parse_record(raw, 0, len(raw))
    assert parsed is not None
    assert parsed.cls == 0x0209


def test_record_refuses_wrong_marker_and_overrun() -> None:
    good = record(0x00E7, b"abcd")
    assert probe.parse_record(b"\xe5\x0c" + good[2:], 0, len(good)) is None
    assert probe.parse_record(good, 0, len(good) - 1) is None
    assert probe.parse_record(b"\x00" * 16, 0, 16) is None


def test_record_keeps_unknown_flags_for_the_census() -> None:
    # The flag vocabulary is measured, not whitelisted: an unseen flag must
    # still frame so it shows up in the census instead of vanishing.
    raw = record(0x000D, b"abc", flag=0x53)
    parsed = probe.parse_record(raw, 0, len(raw))
    assert parsed is not None and parsed.flag == 0x53


def test_walk_and_clusters_tile_and_report_residue() -> None:
    frames = b"".join(record(0x000E, bytes([i]) * 4, ident=i) for i in range(1, 8))
    blob = b"\xff" * 7 + frames + b"\x00" * 5
    found = probe.clusters(blob, 0, len(blob))
    assert len(found) == 1
    cluster = found[0]
    assert cluster.start == 7
    assert cluster.end == 7 + len(frames)
    assert cluster.records == 7
    records, stop = probe.walk(blob, cluster.start, cluster.end)
    assert len(records) == 7
    assert stop == cluster.end


def test_short_run_is_not_a_cluster() -> None:
    blob = b"".join(record(0x000E, b"ab") for _ in range(2))
    assert probe.clusters(blob, 0, len(blob)) == ()


# -------------------------------------------------------------- container


def test_container_is_header_only_and_declares_the_span() -> None:
    run = b"".join(record(0x000E, b"abcd", ident=i) for i in range(1, 6))
    head = container(span=len(run), field=78)
    blob = head + run + b"\x00" * 3
    # Read as an ordinary record the container would swallow 78 bytes and
    # land in the middle of the run, so the container pass must be separate.
    naive = probe.parse_record(blob, 0, len(blob))
    assert naive is not None and naive.length == 78
    found = probe.clusters(blob, 0, len(blob))
    assert len(found) == 1
    assert found[0].start == len(head)
    assert found[0].declared_span == len(run)
    assert found[0].start + found[0].declared_span == found[0].end


def test_container_span_mismatch_is_visible() -> None:
    run = b"".join(record(0x000E, b"abcd") for _ in range(4))
    blob = container(span=len(run) + 40) + run
    found = probe.clusters(blob, 0, len(blob))
    assert found and found[0].declared_span == len(run) + 40
    assert found[0].start + found[0].declared_span != found[0].end


def test_container_signature_needs_the_class_bytes() -> None:
    # `e5 0d 06` alone is not enough: the class slot must read `01 00`, so a
    # 0x06 byte at the tail of another record is not mistaken for one.
    run = b"".join(record(0x000E, b"abcd") for _ in range(4))
    fake = b"\xe5\x0d\x06\x02\x00" + u32le(0) + u32le(len(run))
    blob = fake + run
    found = probe.clusters(blob, 0, len(blob))
    assert found and found[0].declared_span is None


# ----------------------------------------------------------- payload census


def test_census_counts_a_f64_array() -> None:
    grid = net_bytes(swept_net(6, 5))
    payload = b"\x80\x05\x00\x00\x00" + b"\x00" * 8 + grid
    census = probe.census_payload(payload, 0, len(payload))
    assert census.kind == "f64"
    # The run starts at whichever byte phase renders as a double, so it can
    # swallow a leading tag word; what matters is that it owns the array.
    assert census.f64 >= len(grid)
    assert census.f32 == 0


def test_census_refuses_a_zero_field() -> None:
    # 64 bytes of zeros render as plausible doubles, but a constant run is
    # not an array: the variety bar is what rejects it.
    payload = b"\x00" * 64
    census = probe.census_payload(payload, 0, len(payload))
    assert census.kind == "opaque"
    assert census.f64 == 0


def test_census_counts_an_f32_array_and_f64_is_not_f32() -> None:
    floats = [1.5 + index * 0.25 for index in range(32)]
    payload = f32le(*floats) + b"\x00\x00\x00\x00"
    census = probe.census_payload(payload, 0, len(payload))
    assert census.kind == "f32"
    assert census.f32 >= 128
    double_payload = f64le(*[float(value) for value in range(8)])
    double_census = probe.census_payload(double_payload, 0, len(double_payload))
    assert double_census.kind == "f64"


def test_census_counts_text_and_small_integers() -> None:
    text = b"Cont_50f58d0d_1ae0_63f47193_33d25\x00\x00"
    census = probe.census_payload(text, 0, len(text))
    assert census.kind == "text"
    assert census.text >= 8
    counts = u32le(*[6, 3, 3, 3, 3, 3, 3, 6])
    index_census = probe.census_payload(counts, 0, len(counts))
    assert index_census.kind == "index"
    assert index_census.index == len(counts)


def test_census_bytes_partition_the_payload() -> None:
    payload = b"\x80\x05\x00\x00\x00" + net_bytes(swept_net(4, 4)) + b"abcdefgh"
    census = probe.census_payload(payload, 0, len(payload))
    assert census.f64 + census.f32 + census.index + census.text + census.opaque == (
        census.total
    )


# ----------------------------------------------------------- triple arrays


def test_triple_array_reports_points_bbox_and_grid() -> None:
    points = swept_net(6, 5)
    payload = b"\x80" + b"\x07\x00\x00\x00" + net_bytes(points)
    array, _, _, _ = probe.triple_array(payload, 0, len(payload))
    assert array is not None
    assert array.payload_offset == 5
    assert array.points == 30
    net = array.net
    assert (net.rows, net.cols) == (6, 5)
    assert net.spread <= probe.bulk.GRID_SPREAD_BAR
    assert net.ok
    assert array.bbox[0] == 4000.0


def test_triple_array_refuses_a_non_multiple_of_three() -> None:
    payload = f64le(*[float(value) for value in range(1, 11)])  # 10 doubles
    array, _, _, _ = probe.triple_array(payload, 0, len(payload))
    assert array is None


def test_triple_array_reports_the_f32_run() -> None:
    # An f32 payload must not yield a triple array, but its run is reported.
    payload = f32le(*[1.5 + index * 0.5 for index in range(16)])
    array, f32_count, f32_net, f32_varied = probe.triple_array(
        payload, 0, len(payload)
    )
    assert array is None
    assert f32_count >= 16
    assert f32_varied >= 16
    # 16 floats is not 3-divisible, so no f32 point net is even attempted.
    assert f32_net is None


def test_is_grid_needs_three_rows_and_three_columns() -> None:
    row = probe.bulk.pole_net(
        [(4000.0 + index * 10.0, 900.0, -300.0) for index in range(20)], 0
    )
    grid = probe.bulk.pole_net(swept_net(6, 5), 0)
    assert not probe._is_grid(row)
    assert probe._is_grid(grid)


def test_f32_triple_grid_is_detected() -> None:
    # The f32 path exists and works: a 6x5 float grid decodes as a net, so
    # the population's "0 f32 grids" is a measurement, not a blind spot.
    points = swept_net(6, 5)
    payload = f32le(*[value for point in points for value in point])
    array, f32_count, f32_net, _ = probe.triple_array(payload, 0, len(payload))
    assert array is None
    assert f32_count == 90
    assert f32_net is not None
    assert probe._is_grid(f32_net)


def test_marker_inside_a_payload_is_not_a_record() -> None:
    # A well-formed record header embedded in a payload must never be
    # visited: the walk moves record to record, it does not scan for markers.
    inner = b"\xe5\x0d\x03\x0e\x00\x04\x00\x00\x00\x01\x00\x00\x00abcd"
    frames = b"".join(record(0x000E, inner) for _ in range(3))
    found = probe.clusters(frames, 0, len(frames))
    assert len(found) == 1
    records, stop = probe.walk(frames, found[0].start, found[0].end)
    assert len(records) == 3
    assert stop == len(frames)
    assert {record.start for record in records} == {
        0,
        probe.HEADER_BYTES + len(inner),
        2 * (probe.HEADER_BYTES + len(inner)),
    }
