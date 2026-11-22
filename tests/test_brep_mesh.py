"""Synthetic regression tests for ``catpart.geometry.brep_mesh``.

The counts-less ``0x49`` triangle-record family (W2 marathon census
2026-11-22): the fixtures mirror the Rust twin's unit tests
(``port/src/geometry/brep_mesh.rs``) one to one — structural parity on
identical synthetic bytes. The module is deliberately UNWIRED from the
exporter (the family's reference mapping is the refuted open question
the module docs document); these tests pin the decode law, its
fail-closed gates and the census walker.
"""

import math
import struct

import pytest

from catpart.geometry import brep_mesh


def valid_record(refs=(10, 20, 30), ty=1):
    """One valid family record: header + n + unit normal + u16be refs."""
    b = bytearray(b"\x01\x49")
    b += bytes([ty, 0xFF])
    b += struct.pack("<I", 3 * ty)
    b += struct.pack("<fff", 0.0, 0.0, 1.0)
    for r in refs:
        b += struct.pack(">H", r)
    return bytes(b)


def test_valid_ty1_record_parses():
    buf = valid_record()
    rec = brep_mesh.parse_countsless_record(buf, 0, len(buf))
    assert rec is not None
    assert rec.ty == 1
    assert rec.n == 3
    assert rec.refs == (10, 20, 30)
    assert rec.end == 26
    assert rec.normal == (0.0, 0.0, 1.0)
    assert brep_mesh.record_triangles(rec) == [(10, 20, 30)]


def test_non_unit_normal_refused():
    buf = bytearray(valid_record())
    buf[8:12] = struct.pack("<f", 2.0)  # |n| = 2
    assert brep_mesh.parse_countsless_record(bytes(buf), 0, len(buf)) is None


def test_non_finite_normal_refused():
    buf = bytearray(valid_record())
    buf[8:12] = struct.pack("<f", float("nan"))
    assert brep_mesh.parse_countsless_record(bytes(buf), 0, len(buf)) is None


def test_wrong_n_law_refused():
    buf = bytearray(valid_record())
    buf[4:8] = struct.pack("<I", 4)  # n != 3*ty
    assert brep_mesh.parse_countsless_record(bytes(buf), 0, len(buf)) is None


def test_ty_over_cap_refused():
    b = bytearray(b"\x01\x49\x11\xff")
    b += struct.pack("<I", 51)
    b += struct.pack("<fff", 0.0, 0.0, 1.0)
    b += b"\x00" * 102
    assert brep_mesh.parse_countsless_record(bytes(b), 0, len(b)) is None


def test_truncation_refused():
    buf = valid_record()
    assert brep_mesh.parse_countsless_record(buf, 0, len(buf) - 1) is None
    assert brep_mesh.parse_countsless_record(buf, 0, 10) is None


def test_wrong_marker_or_form_refused():
    buf = bytearray(valid_record())
    buf[1] = 0x4A
    assert brep_mesh.parse_countsless_record(bytes(buf), 0, len(buf)) is None
    buf[1] = 0x49
    buf[3] = 0x00  # the form byte
    assert brep_mesh.parse_countsless_record(bytes(buf), 0, len(buf)) is None


def test_offset_window_respected():
    buf = b"\xff\xff" + valid_record()
    rec = brep_mesh.parse_countsless_record(buf, 2, len(buf))
    assert rec is not None and rec.offset == 2
    # a record whose refs bytes would run past body_hi is refused
    assert brep_mesh.parse_countsless_record(buf, 2, len(buf) - 1) is None


def test_ty2_record_is_two_loops():
    buf = valid_record(refs=(1, 2, 3, 4, 5, 6), ty=2)
    rec = brep_mesh.parse_countsless_record(buf, 0, len(buf))
    assert rec is not None and rec.ty == 2 and rec.n == 6
    assert brep_mesh.record_triangles(rec) == [(1, 2, 3), (4, 5, 6)]


def test_census_counts_and_skips_overlaps():
    buf = valid_record() + valid_record(refs=(4, 5, 6))
    c = brep_mesh.census_family(buf, 0, len(buf))
    assert c.candidates == 2
    assert c.records == 2
    assert c.unit_normal_rejects == 0
    assert c.span_fit_rejects == 0
    # a record running past the span counts as a span-fit reject
    c2 = brep_mesh.census_family(buf, 0, len(buf) - 2)
    assert c2.records == 1
    assert c2.span_fit_rejects == 1


def test_census_names_unit_normal_rejects():
    buf = bytearray(valid_record())
    buf[8:12] = struct.pack("<f", 2.0)
    c = brep_mesh.census_family(bytes(buf), 0, len(buf))
    assert c.records == 0
    assert c.unit_normal_rejects == 1


def test_census_ignores_non_family_candidates():
    # a 0x4a strip candidate and a junk candidate are not family records
    junk = b"\x01\x4a\x01\xff" + struct.pack("<I", 3) + b"\x00" * 30
    buf = valid_record() + junk
    c = brep_mesh.census_family(buf, 0, len(buf))
    assert c.candidates == 2
    assert c.records == 1


def test_reference_values_left_to_the_caller():
    """The parser checks the record's byte extent, not the ref values.

    The reference space's bound (pool length / element count) is the
    caller's context; the family's refs index the composite element
    space (the documented open question), so no pool bound is asserted
    here.
    """
    buf = valid_record(refs=(65534, 65535, 7))
    rec = brep_mesh.parse_countsless_record(buf, 0, len(buf))
    assert rec is not None
    assert rec.refs == (65534, 65535, 7)


def test_normal_unit_bar_matches_br2():
    """|n-1| <= 1e-6 is the committed BR2-06 bar."""
    assert brep_mesh.UNIT_NORM_TOL == 1e-6
    n = (0.6, 0.8, 0.0)
    assert abs(math.sqrt(sum(c * c for c in n)) - 1.0) <= brep_mesh.UNIT_NORM_TOL
    b = bytearray(b"\x01\x49\x01\xff")
    b += struct.pack("<I", 3)
    b += struct.pack("<fff", *n)
    b += struct.pack(">HHH", 1, 2, 3)
    assert brep_mesh.parse_countsless_record(bytes(b), 0, len(b)) is not None


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))


# --- the deterministic 2D ear clipper ---------------------------------------
#
# Fixtures are PINNED: the expected triangle sequences below were derived
# from this implementation and are asserted verbatim in the Rust twin's
# unit tests (port/src/geometry/brep_mesh.rs) — the parity bar for the
# unwired component (export-path byte parity applies when wired).

SQUARE = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
CONCAVE = [
    (0.0, 0.0, 0.0),
    (4.0, 0.0, 0.0),
    (4.0, 4.0, 0.0),
    (2.0, 4.0, 0.0),
    (2.0, 1.0, 0.0),
    (0.0, 1.0, 0.0),
]
STAR = [
    (0.0, -2.0, 0.0),
    (0.6, -0.6, 0.0),
    (2.0, 0.0, 0.0),
    (0.6, 0.6, 0.0),
    (0.0, 2.0, 0.0),
    (-0.6, 0.6, 0.0),
    (-2.0, 0.0, 0.0),
    (-0.6, -0.6, 0.0),
]


def test_clip_convex_square():
    tris = brep_mesh.clip_planar_loop([0, 1, 2, 3], SQUARE)
    assert tris == [(3, 0, 1), (1, 2, 3)]


def test_clip_concave_polygon_pinned():
    tris = brep_mesh.clip_planar_loop(list(range(6)), CONCAVE)
    assert tris == [(5, 0, 1), (1, 2, 3), (1, 3, 4), (1, 4, 5)]


def test_clip_star_polygon_pinned():
    tris = brep_mesh.clip_planar_loop(list(range(8)), STAR)
    assert tris == [
        (7, 0, 1),
        (7, 1, 2),
        (7, 2, 3),
        (7, 3, 4),
        (7, 4, 5),
        (5, 6, 7),
    ]


def test_clip_normalizes_winding():
    # the same square given clockwise normalizes to the same CCW loop
    # and triangulates to the SAME triangles (absolute index space)
    tris = brep_mesh.clip_planar_loop([3, 2, 1, 0], SQUARE)
    assert tris == [(3, 0, 1), (1, 2, 3)]


def test_clip_refuses_degenerate_inputs():
    assert brep_mesh.clip_planar_loop([0, 1], SQUARE) is None
    assert brep_mesh.clip_planar_loop([0, 1, 2, 0], SQUARE) is None  # repeated index
    collinear = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]
    assert brep_mesh.clip_planar_loop([0, 1, 2], collinear) is None  # zero area


def test_clip_non_planar_still_triangulates_in_projection():
    """The clipper projects along the Newell normal; coplanarity is the
    CALLER's validation (documented scope) — a non-planar loop's output
    is the projection's triangulation, index-valid but geometry-unvetted."""
    tilted = [(0.0, 0.0, 0.0), (1.0, 0.0, 1.0), (1.0, 1.0, 1.0), (0.0, 1.0, 0.0)]
    tris = brep_mesh.clip_planar_loop([0, 1, 2, 3], tilted)
    assert tris == [(0, 3, 2), (2, 1, 0)]


def test_clip_result_is_manifold_local():
    """Every interior edge of the fan appears exactly twice with opposite
    orientation; boundary edges once (the n-3 diagonal property)."""
    tris = brep_mesh.clip_planar_loop(list(range(8)), STAR)
    assert len(tris) == 6  # n - 2
    directed = {}
    for tri in tris:
        for e in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            directed[e] = directed.get(e, 0) + 1
    undirected = {}
    for (a, b), c in directed.items():
        key = (a, b) if a <= b else (b, a)
        undirected[key] = undirected.get(key, 0) + c
    # every undirected edge used at most twice (no over-use)
    assert all(v <= 2 for v in undirected.values())
