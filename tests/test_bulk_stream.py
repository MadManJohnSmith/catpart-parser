"""Corpus-free tests for the pre-CGM bulk-stream probe (2026-11-19).

The probe (``scripts/triage/probe_bulk_stream.py``) measures the
``CATPrtCont`` content stream: the big-endian metadata table that ends the
preamble, the A/B-family frame walk over the object stream, and the f64
pole nets the stream carries.  These tests build every ingredient from
bytes and pin the decisions the evidence note rests on:

- the metadata table parser only accepts a table whose counted records
  close ``total_size`` exactly and whose last value names a ``Cont_``
  stream — so a "content start" in the corpus is derived, not guessed;
- the A/B frame headers (four widths each) locate payload and next record
  from the family byte alone, and a wrong flag or a truncated frame is
  refused;
- the cluster walk tiles a synthetic stream exactly and reports the
  remainder as residue;
- the pole-net decoder recovers a 36x21 swept grid, rejects a reshuffled
  point bag (no rectangular station law), and rejects out-of-model scale;
- ``a5 03 34`` payloads are read through the frame walk, so the grid is
  located by value continuity and the tail is measured, not assumed.

Fixtures are synthetic; no corpus binary is read.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "triage"))

import probe_bulk_stream as probe  # noqa: E402


def u32be(*vals: int) -> bytes:
    return b"".join(struct.pack(">I", v) for v in vals)


def u16be(*vals: int) -> bytes:
    return b"".join(struct.pack(">H", v) for v in vals)


def f64le(*vals: float) -> bytes:
    return b"".join(struct.pack("<d", v) for v in vals)


def metadata_table(names: list[str]) -> bytes:
    """A big-endian property table with one type-2 record per name."""
    records = b""
    for name in names:
        value = name.encode("utf-16-be") + b"\x00\x00"
        records += u32be(14 + len(value), 24) + u16be(2) + u32be(len(value)) + value
    return u32be(12 + len(records), 7, len(names)) + records


def b_frame(cls: int, payload: bytes, width: int = 1, flag: int = 0x03) -> bytes:
    """B family: ``b1+W | flag | class | len:u8 | token[W] | payload``."""
    assert len(payload) < 256
    return (
        bytes([0xB1 + width, flag, cls, len(payload)]) + bytes(range(width)) + payload
    )


def a_frame(cls: int, payload: bytes, width: int = 1, flag: int = 0x03) -> bytes:
    """A family: ``a4+W | flag | class | len:u32le | token[W] | payload``."""
    return (
        bytes([0xA4 + width, flag, cls])
        + struct.pack("<I", len(payload))
        + bytes(range(width))
        + payload
    )


def swept_net(
    rows: int = 36, cols: int = 21, scale: float = 1.0
) -> list[tuple[float, float, float]]:
    """A station-constant grid: x advances per row, y/z trace a profile."""
    points = []
    for row in range(rows):
        for col in range(cols):
            points.append(
                (
                    scale * (row * 130.0 + 4000.0),
                    scale * (900.0 - col * 80.0),
                    scale * (-300.0 + col * 30.0 + row * 0.5),
                )
            )
    return points


def net_bytes(points: list[tuple[float, float, float]]) -> bytes:
    return b"".join(f64le(*point) for point in points)


# ---------------------------------------------------------------- metadata


def test_metadata_table_parses_and_tiles() -> None:
    table = metadata_table(
        ["CATPropertySets", "CATStorageProperty", "Cont_50f58d0d_1ae0"]
    )
    blob = b"\x00" * 37 + table
    parsed = probe.parse_metadata_table(blob, 0, len(blob))
    assert parsed is not None
    assert parsed.offset == 37
    assert parsed.total_size == len(table)
    assert parsed.count == 3
    assert parsed.tiles
    assert parsed.records[-1].text.startswith("Cont_")
    assert parsed.end == 37 + len(table)


def test_metadata_table_requires_cont_name() -> None:
    table = metadata_table(["CATPropertySets", "CATStorageProperty", "NotAContainer"])
    blob = b"\x00" * 8 + table
    assert probe.parse_metadata_table(blob, 0, len(blob)) is None


def test_metadata_table_refuses_broken_record_size() -> None:
    table = bytearray(metadata_table(["CATPropertySets", "Cont_abc"]))
    # Corrupt the first record's size so the records no longer close.
    table[12:16] = struct.pack(">I", 999)
    blob = b"\x00" * 4 + bytes(table)
    assert probe.parse_metadata_table(blob, 0, len(blob)) is None


# ------------------------------------------------------------------ frames


@pytest.mark.parametrize("width", [1, 2, 3, 4])
def test_b_frame_widths_and_next_offset(width: int) -> None:
    payload = bytes(range(20))
    raw = b_frame(0x34, payload, width=width)
    rec = probe.parse_record(raw, 0, len(raw))
    assert rec is not None
    assert rec.family == "B"
    assert rec.width == width
    assert rec.cls == 0x34
    assert rec.payload_len == 20
    assert rec.payload == 4 + width
    assert rec.end == len(raw)


@pytest.mark.parametrize("width", [1, 2, 3, 4])
def test_a_frame_widths_and_next_offset(width: int) -> None:
    payload = bytes(range(64))
    raw = a_frame(0x34, payload, width=width)
    rec = probe.parse_record(raw, 0, len(raw))
    assert rec is not None
    assert rec.family == "A"
    assert rec.width == width
    assert rec.payload_len == 64
    assert rec.payload == 7 + width
    assert rec.end == len(raw)


def test_frame_refuses_unknown_flag_and_truncation() -> None:
    good = b_frame(0x20, b"abcd")
    bad_flag = bytes([good[0], 0x07]) + good[2:]
    assert probe.parse_record(bad_flag, 0, len(bad_flag)) is None
    assert probe.parse_record(good, 0, len(good) - 1) is None
    assert probe.parse_record(b"\x00\x00\x00\x00", 0, 4) is None


def test_walk_and_clusters_tile_a_synthetic_stream() -> None:
    frames = b"".join(b_frame(0x20, bytes([i]) * 3) for i in range(8))
    blob = b"\xff" * 11 + frames + b"\x00" * 6
    found = probe.clusters(blob, 0, len(blob))
    assert len(found) == 1
    cluster = found[0]
    assert cluster.start == 11
    assert cluster.end == 11 + len(frames)
    assert cluster.records == 8
    records, stop = probe.walk(blob, cluster.start, cluster.end)
    assert len(records) == 8
    assert stop == cluster.end


# --------------------------------------------------------------- pole nets


def test_pole_net_recovers_a_swept_grid() -> None:
    points = swept_net(36, 21)
    net = probe.pole_net(points, 0)
    assert net.points == 756
    assert (net.rows, net.cols) == (36, 21)
    assert net.station_axis == 0
    assert net.spread <= probe.GRID_SPREAD_BAR
    assert net.monotone
    assert net.ok


def test_pole_net_rejects_a_scrambled_bag() -> None:
    # Scramble the station law: x is now a function of the index with no
    # row structure, so no divisor gives a station-constant row.
    points = [
        (
            4000.0 + ((i * 2654435761) % 5000),
            900.0 - ((i * 40503) % 1800),
            -300.0 + ((i * 7919) % 1000),
        )
        for i in range(756)
    ]
    net = probe.pole_net(points, 0)
    assert not net.ok


def test_pole_net_rejects_out_of_model_scale() -> None:
    points = swept_net(36, 21, scale=1e5)
    net = probe.pole_net(points, 0)
    assert net.spread <= probe.GRID_SPREAD_BAR
    assert not net.scale_ok
    assert not net.ok


def test_prefix_run_starts_at_content_not_elsewhere() -> None:
    grid = net_bytes(swept_net(6, 3))
    blob = b"\xff" * 4 + grid + b"\xff" * 8 + net_bytes(swept_net(6, 3))
    count, start = probe.prefix_run(blob, 4, len(blob))
    assert start == 4
    assert count == 54  # 18 points x 3 doubles
    # The whole-span scan finds the second, longer net too; the prefix
    # decoder deliberately does not.
    count_all, start_all = probe.f64_run(blob, 0, len(blob))
    assert count_all == 54
    assert start_all == 4


def test_decode_net_from_bytes() -> None:
    grid = net_bytes(swept_net(4, 5))
    blob = b"\xff" * 9 + grid + b"\x00" * 16
    net = probe.decode_net(blob, 9, len(blob))
    assert net is not None
    assert net.points == 20
    assert (net.rows, net.cols) == (4, 5)
    assert net.ok


# ------------------------------------------------------------ surface frame


def test_surface_record_payload_layout() -> None:
    points = swept_net(36, 21)
    grid = net_bytes(points)
    prefix = b"\xff" * 182
    tail = b"\x00" * 152
    frame = a_frame(0x34, prefix + grid + tail) + b_frame(0x20, b"ab") * 2
    found = probe.surface_records(frame, 0, len(frame))
    assert len(found) == 1
    start, payload, end, net = found[0]
    assert start == 0
    assert payload == 8
    assert end == 8 + len(prefix) + len(grid) + len(tail)
    assert net is not None
    assert net.start == payload + 182
    assert net.points == 756
    assert (net.rows, net.cols) == (36, 21)
    assert end - (net.start + net.bytes) == 152


def test_surface_marker_inside_payload_is_not_a_record() -> None:
    # A marker-shaped coincidence inside a payload must not surface: the
    # record scan only visits walk boundaries, so it never looks there.
    inner = b"\xa5\x03\x34" + b"\x00" * 40
    frames = b_frame(0x20, inner) + b_frame(0x20, b"tail")
    found = probe.surface_records(frames, 0, len(frames))
    assert found == []
