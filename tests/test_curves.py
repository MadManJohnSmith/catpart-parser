"""tests.test_curves — the U4 skip-slot coordinate law (A4, W16).

Synthetic fixtures only (no corpus): the dup pin, the battery, the
degenerate split, the 33 3X record parse and the ring cross-check —
each with its negative, mirroring the port's ``geometry::curves`` unit
tests.
"""

import math
import struct

import pytest

from catpart.geometry import curves

P = (0.0, 0.0, 0.0)
Q = (1.0, 0.0, 0.0)
R = (0.0, 1.0, 0.0)
S = (1.0, 1.0, 0.0)
T = (0.5, 0.5, 2.0)


def _elements_with_skips():
    """9 elements: written P, skip, written Q, skip, skip, written R,
    skip, skip, skip — every skip has a preceding written element."""
    return [
        (0, P),
        (1, None),
        (2, Q),
        (1, None),
        (1, None),
        (0, R),
        (1, None),
        (1, None),
        (1, None),
    ]


class TestPinSkips:
    def test_dup_law_pins_to_preceding_written(self):
        els = _elements_with_skips()
        pins, kinds = curves.pin_skips(els)
        assert pins[1] == P  # the skip right after P
        assert pins[3] == Q
        assert pins[4] == Q  # consecutive skips share the same preceding write
        assert pins[6] == R
        assert set(kinds.values()) == {"dup"}

    def test_leading_skip_is_unpinned(self):
        els = [(1, None), (0, P), (1, None)]
        pins, kinds = curves.pin_skips(els)
        assert pins[0] is None
        assert pins[2] == P
        assert curves.unpinned_skips(els, pins) == [0]

    def test_every_written_element_resets_the_preceding_state(self):
        els = [(0, P), (1, None), (0, Q), (1, None)]
        pins, _ = curves.pin_skips(els)
        assert pins[1] == P and pins[3] == Q


class TestLoopPinnedPoints:
    def test_resolves_written_and_skip_refs(self):
        els = _elements_with_skips()
        pins, _ = curves.pin_skips(els)
        pts = curves.loop_pinned_points((0, 1, 2), els, pins)
        assert pts == [P, P, Q]

    def test_out_of_range_ref_fails_closed(self):
        els = _elements_with_skips()
        pins, _ = curves.pin_skips(els)
        assert curves.loop_pinned_points((0, 1, 99), els, pins) is None

    def test_unpinned_skip_fails_closed(self):
        els = [(1, None), (0, P)]
        pins, _ = curves.pin_skips(els)
        assert curves.loop_pinned_points((0, 1), els, pins) is None


class TestBattery:
    def test_normal_less_record_is_accepted_untested(self):
        assert curves.loop_is_battery_supported(None, [P, Q, (9.9, 9.9, 9.9)])

    def test_coplanar_loop_passes(self):
        n = (0.0, 0.0, 1.0)
        assert curves.loop_is_battery_supported(n, [P, Q, R])

    def test_nonplanar_loop_fails(self):
        n = (0.0, 0.0, 1.0)
        pts = [P, Q, R, (395.0, 435.5, 50.0)]
        assert not curves.loop_is_battery_supported(n, pts)

    def test_zero_normal_is_not_testable(self):
        assert not curves.loop_is_battery_supported((0.0, 0.0, 0.0), [P, Q, R])


class TestSplitLoopTriangles:
    def test_strip_quad_emits_two_triangles(self):
        # a full non-degenerate quad: two real triangles
        loop = (0, 1, 2, 3)
        pts = [P, Q, S, T]
        real, degen = curves.split_loop_triangles(0x42, loop, pts)
        assert len(real) == 2 and not degen

    def test_degenerate_quad_PXPY_collapses_to_one_triangle(self):
        # the writer's degenerate-quad convention: (P, X, P, Y) where
        # the dup pin makes positions 0 and 2 coincide -> exactly one
        # real triangle (the measured A4 recoverable class)
        loop = (0, 1, 2, 3)
        pts = [P, Q, P, T]
        real, degen = curves.split_loop_triangles(0x42, loop, pts)
        assert [t for t, _a in real] == [(1, 2, 3)]
        assert degen == [(0, 1, 2)]

    def test_triangle_loop_PXP_is_all_degenerate(self):
        loop = (0, 1, 2)
        pts = [P, Q, P]
        real, degen = curves.split_loop_triangles(0x42, loop, pts)
        assert not real and degen == [(0, 1, 2)]

    def test_fan_loop_splits_real_and_collapsed_halves(self):
        # 0x4c fan whose last ref pins onto the first point: the first
        # fan triangle is real, the closing one collapses.
        loop = (0, 1, 2, 3)
        pts = [P, Q, R, P]
        real, degen = curves.split_loop_triangles(0x4C, loop, pts)
        assert [t for t, _a in real] == [(0, 1, 2)]
        assert degen == [(0, 2, 3)]

    def test_repeated_ref_fan_collapses_entirely(self):
        # a fan that references the same element twice with the dup pin
        # collapsing both halves: nothing real survives — the loop the
        # weld refuses as degenerate by construction.
        loop = (0, 1, 0, 2)
        pts = [P, Q, P, R]
        real, degen = curves.split_loop_triangles(0x4C, loop, pts)
        assert not real
        assert degen == [(0, 1, 0), (0, 0, 2)]

    def test_zero_area_cross_product_is_degenerate(self):
        # collinear points: zero cross product, no repeated coords
        a, b, c = (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)
        loop = (0, 1, 2)
        real, degen = curves.split_loop_triangles(0x42, loop, [a, b, c])
        assert not real and degen == [(0, 1, 2)]

    def test_unresolvable_reference_fails_closed(self):
        loop = (0, 1, 2)
        pts = [P, Q, None]
        real, degen = curves.split_loop_triangles(0x42, loop, pts)
        assert not real and degen == [(0, 1, 2)]


def _rec(fam: int, payload: bytes) -> bytes:
    """A 33 3X record: 7-B header + family + payload, tiled so the
    walker's length field (the 2 bytes before the family) reads right.

    The header layout is ``<u8 a><u8 b><u16le id><00><u16le len>`` and
    the family follows; the walker reads len from the 2 bytes before
    ``33``."""
    header = struct.pack("<BBH", 0x01, 0x02, 7) + b"\x00" + struct.pack("<H", len(payload))
    return header + bytes([0x33, fam]) + payload


class TestParseCurveRecords:
    def test_circle_record_parses(self):
        pay = struct.pack(">4f", 395.0, 435.5, 2.1, 2.78) + b"\x00\x00"
        blob = b"\x00\x08" + _rec(0x37, pay) + b"\x00\x00"
        recs = curves.parse_curve_records(blob, 0, len(blob))
        assert len(recs) == 1
        assert recs[0]["fam"] == 0x37 and recs[0]["len"] == 18
        assert curves.circle_of(recs[0]) == pytest.approx((395.0, 435.5, 2.1, 2.78))

    def test_line_record_parses(self):
        pay = b"\x21\x43" + struct.pack("<10f", *P, *Q, *P, 1.0)
        blob = b"\x00\x08" + _rec(0x32, pay) + b"\x00\x00"
        recs = curves.parse_curve_records(blob, 0, len(blob))
        assert len(recs) == 1
        lp = curves.line_of(recs[0])
        assert lp[0] == P and lp[1] == Q

    def test_garbage_stream_yields_nothing(self):
        blob = bytes(range(256))
        assert curves.parse_curve_records(blob, 0, len(blob)) == []

    def test_compressed_stream_false_positive_is_rejected(self):
        # 33 37-looking pair with a huge 'length': rejected by the
        # sanity rule, does not absorb the walk
        blob = b"\x21\x00" + bytes([0x33, 0x37]) + b"\xff" * 40
        assert curves.parse_curve_records(blob, 0, len(blob)) == []


class TestRingCrossCheck:
    def test_written_ring_matches_its_circle(self):
        # 8 points on a z=2.1 ring r=2.78 about (395, 435.5)
        els = []
        for k in range(8):
            ang = 2 * math.pi * k / 8
            els.append((0, (395.0 + 2.78 * math.cos(ang), 435.5 + 2.78 * math.sin(ang), 2.1)))
        rec = {"fam": 0x37, "len": 18,
               "payload": struct.pack(">4f", 395.0, 435.5, 2.1, 2.78) + b"\x00\x00"}
        matched, total = curves.ring_cross_check([rec], els)
        assert (matched, total) == (1, 1)

    def test_no_circles_is_zero_total(self):
        els = [(0, P)]
        rec = {"fam": 0x32, "len": 2, "payload": b"\x00\x00"}
        assert curves.ring_cross_check([rec], els) == (0, 0)

    def test_circle_without_a_written_ring_does_not_match(self):
        rec = {"fam": 0x37, "len": 18,
               "payload": struct.pack(">4f", 0.0, 0.0, 0.0, 5.0) + b"\x00\x00"}
        els = [(0, P)]
        assert curves.ring_cross_check([rec], els) == (0, 1)


class TestLoopTriangles:
    def test_strip_positions(self):
        assert curves.loop_triangles(0x42, 4) == [(0, 1, 2), (1, 2, 3)]

    def test_fan_positions(self):
        assert curves.loop_triangles(0x4C, 5) == [(0, 1, 2), (0, 2, 3), (0, 3, 4)]

    def test_two_ref_loop_has_no_triangles(self):
        assert curves.loop_triangles(0x42, 2) == []
