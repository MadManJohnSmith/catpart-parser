"""Unit tests for the BR3 boundary-curve decoders (ticket #55).

Synthetic fixtures only (corpus binaries stay out of the test suite);
every discriminating edge of the decode laws carries a negative
fixture — the detector-honesty fixtures of the evidence note
(docs/evidence/2026-11-17-br3-curves.md).
"""

from __future__ import annotations

import math
import struct

import pytest

from catpart.brep import curves
from catpart.geometry.errors import ExportError

WRAPPER = curves.WRAPPER


def be_f32(*values: float) -> bytes:
    return b"".join(struct.pack(">f", v) for v in values)


def le_f32(*values: float) -> bytes:
    return b"".join(struct.pack("<f", v) for v in values)


def record(family: int, payload: bytes, tag_a: int = 0x01, tag_b: int = 0x22,
           ident: int = 15, length: int | None = None) -> bytes:
    """A 7-B header + family + payload curve record."""
    ln = len(payload) if length is None else length
    return (
        bytes([tag_a, tag_b])
        + struct.pack("<H", ident)
        + b"\x00"
        + struct.pack("<H", ln)
        + bytes([0x33, family])
        + payload
    )


def line_block(p, q, length: float | None = None) -> bytes:
    """A 40-B [P][Q][P]+|Q| f32le block."""
    if length is None:
        length = math.sqrt(q[0] ** 2 + q[1] ** 2 + q[2] ** 2)
    return le_f32(*p, *q, *p, length)


def with_wrapper(body: bytes) -> bytes:
    """Body framed by two wrappers so walks have an end bound.

    ``body`` opens with its own sub-kind bytes (``01 02`` / ``01 01``);
    the trailing pool group carries a padding count byte so the pool
    scan never reads past the buffer.
    """
    return WRAPPER + body + WRAPPER + b"\x01\x06\x00"


# ---------------------------------------------------------------- lines


def test_line_decode_and_laws():
    rec = record(curves.FAMILY_LINE, b"", length=2)
    data = rec + line_block((1.0, 2.0, 3.0), (10.0, 0.0, 30.0))
    walked = curves.iter_curve_records(data, 0, len(data))
    assert len(walked) == 1
    seg = curves.decode_line(walked[0], data)
    assert seg.floats[0:3] == (1.0, 2.0, 3.0)
    assert seg.floats[3:6] == (10.0, 0.0, 30.0)
    assert seg.p_rep_ok and seg.length_ok


def test_line_negative_bad_length():
    rec = record(curves.FAMILY_LINE, b"", length=2)
    data = rec + line_block((1.0, 2.0, 3.0), (10.0, 0.0, 30.0), length=99.0)
    (rec_w,) = curves.iter_curve_records(data, 0, len(data))
    seg = curves.decode_line(rec_w, data)
    # Detector honesty edge: the |Q| law flag must fire on a wrong length.
    assert not seg.length_ok


def test_line_negative_non_finite_block():
    rec = record(curves.FAMILY_LINE, b"", length=2)
    data = rec + le_f32(1.0, 2.0, 3.0, 10.0, 0.0, 30.0, 1.0, 2.0, 3.0, float("nan"))
    (rec_w,) = curves.iter_curve_records(data, 0, len(data))
    with pytest.raises(ExportError):
        curves.decode_line(rec_w, data)


# --------------------------------------------------------------- circles


def test_circle_decode():
    rec = record(curves.FAMILY_CIRCLE, be_f32(5.0, 0.0, 0.0, 2.0) + b"\x00\x80")
    (rec_w,) = curves.iter_curve_records(rec, 0, len(rec))
    circ = curves.decode_circle(rec_w)
    assert circ.center == (5.0, 0.0, 0.0)
    assert circ.radius == 2.0


def test_circle_negative_zero_radius():
    rec = record(curves.FAMILY_CIRCLE, be_f32(5.0, 0.0, 0.0, 0.0) + b"\x00\x80")
    (rec_w,) = curves.iter_curve_records(rec, 0, len(rec))
    with pytest.raises(ExportError):
        curves.decode_circle(rec_w)


def test_circle_negative_nan_center():
    rec = record(curves.FAMILY_CIRCLE, be_f32(float("nan"), 0.0, 0.0, 2.0))
    # The walker's plausibility cap must skip the pseudo-record entirely.
    assert curves.iter_curve_records(rec, 0, len(rec)) == []


# ---------------------------------------------------------------- conics


def test_conic_decode():
    c, s = math.cos(0.7), math.sin(0.7)
    rec = record(curves.FAMILY_CONIC, be_f32(3.0, 4.0, 5.0, c, s, 3.0, 1.0) + b"\x00\x00")
    (rec_w,) = curves.iter_curve_records(rec, 0, len(rec))
    conic = curves.decode_conic(rec_w)
    assert conic.center == (3.0, 4.0, 5.0)
    assert abs(conic.direction[0] - c) < 1e-6
    assert conic.semi_a == 3.0 and conic.semi_b == 1.0


def test_conic_negative_non_unit_direction():
    # (0.6, 0.6): mid-range components whose norm is 0.849 — the
    # discriminating edge of the direction law.
    rec = record(curves.FAMILY_CONIC, be_f32(3.0, 4.0, 5.0, 0.6, 0.6, 3.0, 1.0))
    (rec_w,) = curves.iter_curve_records(rec, 0, len(rec))
    with pytest.raises(ExportError):
        curves.decode_conic(rec_w)


def test_conic_negative_non_positive_b():
    c, s = math.cos(0.7), math.sin(0.7)
    rec = record(curves.FAMILY_CONIC, be_f32(3.0, 4.0, 5.0, c, s, 3.0, 0.0))
    (rec_w,) = curves.iter_curve_records(rec, 0, len(rec))
    with pytest.raises(ExportError):
        curves.decode_conic(rec_w)


def test_conic_zero_direction_sentinel_accepts():
    rec = record(
        curves.FAMILY_CONIC, be_f32(3.0, 4.0, 5.0, 0.0, 0.0, 54.0, 4.0) + b"\x00\x00"
    )
    (rec_w,) = curves.iter_curve_records(rec, 0, len(rec))
    conic = curves.decode_conic(rec_w)
    assert conic.direction == (0.0, 0.0)


# -------------------------------------------------------------- midring


def test_midring_decode():
    c, s = math.cos(1.2), math.sin(1.2)
    rec = record(
        curves.FAMILY_MIDRING, be_f32(1.0, 2.0, 3.0, c, s, -2.36) + b"\x00\x00"
    )
    (rec_w,) = curves.iter_curve_records(rec, 0, len(rec))
    arc = curves.decode_midring(rec_w)
    assert arc.radius == pytest.approx(-2.36)  # negative radii observed corpus-wide
    assert abs(arc.direction[1] - s) < 1e-6


def test_midring_negative_non_unit_direction():
    rec = record(curves.FAMILY_MIDRING, be_f32(1.0, 2.0, 3.0, 0.5, 0.5, 2.0))
    (rec_w,) = curves.iter_curve_records(rec, 0, len(rec))
    with pytest.raises(ExportError):
        curves.decode_midring(rec_w)


# ----------------------------------------------------------- edge groups


def edge_group(records: list[tuple[int, list[int]]], width: int) -> bytes:
    body = b"\x01\x02"
    body += bytes([len(records)])
    for n, refs in records:
        body += bytes([0x02, n])
        for r in refs:
            body += r.to_bytes(width, "big")
    return body


def test_edge_group_u16be_walk():
    body = edge_group([(2, [3, 4]), (3, [5, 6, 7])], width=2)
    data = with_wrapper(body)
    groups = curves.scan_edge_groups(data, 0, len(data))
    assert len(groups) == 1
    g = groups[0]
    assert g.width == 2
    assert g.records == ((2, (3, 4)), (3, (5, 6, 7)))


def test_edge_group_u8_walk():
    body = edge_group([(2, [1, 2]), (2, [3, 4])], width=1)
    data = with_wrapper(body)
    (g,) = curves.scan_edge_groups(data, 0, len(data))
    assert g.width == 1
    assert g.records[1][1] == (3, 4)


def test_edge_group_negative_misaligned_end():
    # One reference byte short: neither width end-aligns, so strict
    # scanning raises and lenient scanning skips the group.
    body = edge_group([(2, [3, 4])], width=2)[:-1]
    data = with_wrapper(body)
    with pytest.raises(ExportError):
        curves.scan_edge_groups(data, 0, len(data))
    assert curves.scan_edge_groups(data, 0, len(data), strict=False) == []


def test_polyline_strips_n_gt_2():
    body = edge_group([(2, [1, 2]), (4, [3, 4, 5, 6])], width=1)
    data = with_wrapper(body)
    (g,) = curves.scan_edge_groups(data, 0, len(data))
    strips = [recs for recs in g.records if recs[0] > 2]
    assert strips == [(4, (3, 4, 5, 6))]


def test_unwrapped_polyline_list():
    body = (
        b"\x01\x01\x02"
        + b"\x02\x02" + (9).to_bytes(2, "big") + (10).to_bytes(2, "big")
        + b"\x02\x02" + (11).to_bytes(2, "big") + (12).to_bytes(2, "big")
    )
    data = with_wrapper(body)
    (lst,) = curves.scan_polyline_lists(data, 0, len(data))
    assert lst.count == 2
    assert lst.records == ((2, (9, 10)), (2, (11, 12)))


# ------------------------------------------------------------ vertex pool


def pool_group(vertices: list[tuple[float, float, float]]) -> bytes:
    body = b"\x01\x06" + bytes([len(vertices)])
    for x, y, z in vertices:
        body += b"\x05\x08\x01" + struct.pack("<fff", x, y, z)
    return WRAPPER + body


def test_vertex_pool_scan():
    data = pool_group([(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]) + WRAPPER + b"\x01\x06\x00"
    groups, kinds = curves.scan_vertex_pool(data, 0, len(data))
    assert [g.count_field for g in groups] == [2]
    assert groups[0].vertices[1] == (4.0, 5.0, 6.0)
    assert kinds == [b"\x01\x06", b"\x01\x06"]


def test_vertex_pool_negative_count_mismatch():
    bad = pool_group([(1.0, 2.0, 3.0)])
    # Declare two vertices but write one record: the P2g law must fire.
    broken = bad.replace(b"\x01\x06\x01", b"\x01\x06\x02")
    # Pad past the pool sanity gate so the short walk hits the P2g law
    # (an over-declaring group inside too small a buffer is skipped as
    # never-established, not raised).
    broken += WRAPPER + b"\x01\x06\x00" + b"\x00" * 5
    with pytest.raises(ExportError):
        curves.scan_vertex_pool(broken, 0, len(broken))


# ------------------------------------------------------------ record walk


def test_walker_tiles_mixed_families():
    line = record(curves.FAMILY_LINE, b"", length=2) + line_block(
        (0.0, 0.0, 1.0), (3.0, 4.0, 0.0)
    )
    circ = record(curves.FAMILY_CIRCLE, be_f32(1.0, 1.0, 0.0, 2.0) + b"\x00\x00")
    conic = record(
        curves.FAMILY_CONIC,
        be_f32(0.0, 0.0, 0.0, math.cos(0.5), math.sin(0.5), 3.0, 1.0) + b"\x00\x00",
    )
    data = line + circ + conic
    recs = curves.iter_curve_records(data, 0, len(data))
    assert [r.family for r in recs] == [
        curves.FAMILY_LINE,
        curves.FAMILY_CIRCLE,
        curves.FAMILY_CONIC,
    ]


def test_walker_skips_garbage_header():
    # A compressed-stream pseudo-record: family bytes behind a header
    # whose length is implausible must not absorb the walk.
    garbage = b"\x01\x22\x0f\x00\x00\xff\xff" + b"\x33\x37" + b"\xaa" * 8
    good = record(curves.FAMILY_CIRCLE, be_f32(1.0, 1.0, 0.0, 2.0) + b"\x00\x00")
    recs = curves.iter_curve_records(garbage + good, 0, len(garbage + good))
    assert [r.family for r in recs] == [curves.FAMILY_CIRCLE]
