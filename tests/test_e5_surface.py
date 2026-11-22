"""Corpus-free tests for the E5 dialect's exact-surface record (2026-11-22).

The ``e5 0d`` stream's class ``0x00e7`` payload is the compact head's pole
law with u32 fields (``docs/evidence/2026-11-22-e5-class-table.md``):
``0x80`` + five u32s per lane (degree, a, b, knot count, q), strictly
increasing knots, one multiplicity per knot, then the two-byte pole marker
(``00 00`` plain, ``01 00`` rational — coordinates then weights) and the
``poles_u x poles_v`` f64 net stored **v-major outer**.  These tests pin:

- the lane law, the pole law ``sum(mult) - degree - 1`` and the net offset
  the head predicts;
- the two marker values, and that the rational marker reads the weights
  that follow the coordinate net;
- the v-major byte order (pole ``(i, j)`` at ``net + 24*(j*poles_u + i)``);
- the fail-closed refusals: non-monotone knots, a zero multiplicity, a net
  that overruns the record, a marker outside the measured pair;
- the scan's no-regret fold law: E5 records join the totals and the mesh
  only when at least one E5 surface tessellated — with nothing
  tessellated the census stays invisible and the totals are the pre-E5
  ones;
- the admitted-run record walk the route consumes.

Fixtures are synthetic; no corpus binary is read.
"""

from __future__ import annotations

import struct

import pytest

from catpart.geometry import grid, surface

import fixtures_gen


def u32le(*values: int) -> bytes:
    return b"".join(struct.pack("<I", v) for v in values)


def f64(*values: float) -> bytes:
    return b"".join(struct.pack("<d", v) for v in values)


def e5_lane(
    degree: int = 1,
    knots: tuple[float, ...] = (0.0, 1.0),
    mult: tuple[int, ...] = (2, 2),
) -> bytes:
    """One E5 lane: ``deg:u32 a:u32 b:u32 n:u32 q:u32`` + knots + mults."""
    return (
        u32le(degree, 0, 0, len(knots), 0)
        + f64(*knots)
        + u32le(*mult)
    )


def e5_payload(
    lane_v: bytes | None = None,
    lane_u: bytes | None = None,
    poles_u: int = 2,
    poles_v: int = 2,
    marker: bytes = b"\x00\x00",
    weights: bool = False,
    tail: int = 148,
) -> bytes:
    """An E5 surface payload: two lanes + marker + net + tail."""
    if lane_v is None:
        lane_v = e5_lane()
    if lane_u is None:
        lane_u = e5_lane()
    # The E5 net is v-major outer: consecutive poles_u triples are the
    # u-polygon at a fixed v.
    net = []
    for j in range(poles_v):
        for i in range(poles_u):
            net.append((5.0 * i, 7.0 * j, 2.0 + 0.5 * i + 0.25 * j))
    blob = b"\x80" + lane_v + lane_u + marker + b"".join(
        f64(*point) for point in net
    )
    if weights:
        blob += f64(*([1.0] * poles_u * poles_v))
    return blob + bytes(tail)


def e5_record(payload: bytes, cls: int = surface.E5_SURFACE_CLASS, ident: int = 7) -> bytes:
    """``e5 0d | flag | class:u16le | length:u32le | id:u32le | payload``."""
    return (
        b"\xe5\x0d"
        + b"\x03"
        + struct.pack("<H", cls)
        + struct.pack("<I", len(payload))
        + struct.pack("<I", ident)
        + payload
    )


def e5_part(records: bytes) -> bytes:
    """A CATPrtCont block with a chained E5 record run after it."""
    block = fixtures_gen.storage_property_block(b"CATPrtCont", b"CATContainer")
    return block + b"\x00" * 64 + records


def parse(payload: bytes):
    return surface.parse_e5_surface(payload, 0, len(payload))


# ----------------------------------------------------------------- head


def test_lane_law_and_the_pole_law() -> None:
    payload = e5_payload(
        lane_v=e5_lane(degree=3, knots=(0.0, 2.0, 4.0), mult=(4, 1, 4)),
        lane_u=e5_lane(degree=1, knots=(0.0, 1.0), mult=(2, 2)),
        poles_u=2,
        poles_v=5,
    )
    head = parse(payload)
    assert head is not None
    assert head.subtype == surface.SUBTYPE_COMPACT
    assert (head.degree_u, head.degree_v) == (1, 3)
    assert (head.n_u, head.n_v) == (2, 3)
    assert head.mult_v == (4, 1, 4)
    # sum(mult) - degree - 1, per direction.
    assert (head.poles_u, head.poles_v) == (2, 5)
    assert head.points == 10
    # The grid is predicted by the head: tag + two lane blocks (five u32s,
    # n knots, n mults each), then the two-byte pole marker.
    lane_bytes = 20 + 8 * 3 + 4 * 3 + 20 + 8 * 2 + 4 * 2
    assert head.grid == 1 + lane_bytes + 2
    assert head.tail == 148


def test_rational_marker_reads_the_weights_that_follow_the_net() -> None:
    payload = e5_payload(marker=b"\x01\x00", weights=True)
    head = parse(payload)
    assert head is not None
    assert head.rational is True
    poles, weights = surface.e5_pole_data(payload, head)
    assert weights is not None
    assert all(value == 1.0 for row in weights for value in row)
    # The weights follow the coordinates: the rational record is the plain
    # record plus 8 * poles bytes, with the same 148-byte tail law.
    plain = parse(e5_payload(marker=b"\x00\x00"))
    assert plain is not None
    assert plain.tail == head.tail == 148
    assert head.end == plain.end + 8 * head.points


def test_pole_net_is_v_major_outer() -> None:
    payload = e5_payload(
        lane_v=e5_lane(degree=1, knots=(0.0, 0.5, 1.0), mult=(2, 2, 2)),
        lane_u=e5_lane(degree=1, knots=(0.0, 1.0), mult=(3, 2)),
        poles_u=3,
        poles_v=4,
    )
    head = parse(payload)
    assert head is not None
    assert (head.poles_u, head.poles_v) == (3, 4)
    poles, _ = surface.e5_pole_data(payload, head)
    # pole (i, j) sits at net + 24*(j*poles_u + i): consecutive poles_u
    # triples are the u-polygon at a fixed v.
    assert poles[0][0] == (0.0, 0.0, 2.0)
    assert poles[1][0] == (5.0, 0.0, 2.5)
    assert poles[0][1] == (0.0, 7.0, 2.25)
    assert poles[2][3] == (10.0, 21.0, 3.75)


def test_the_battery_accepts_a_plane_and_tessellates_it() -> None:
    payload = e5_payload()
    head = parse(payload)
    assert head is not None
    poles, weights = surface.e5_pole_data(payload, head)
    assert surface.plausible_net(poles)
    assessment = surface.assess(head, poles, weights)
    assert assessment.evaluable
    assert assessment.corner_residual == pytest.approx(0.0)
    assert assessment.arc_applicable is False  # the compact pole law
    patch = surface.tessellate(head, poles, weights)
    assert patch is not None
    assert patch.degenerate == 0


# -------------------------------------------------------------- refusals


def test_non_monotone_knots_refuse() -> None:
    bad_v = e5_lane(knots=(0.0, 2.0, 1.0), mult=(2, 2, 2))
    assert parse(e5_payload(lane_v=bad_v, poles_u=2, poles_v=2)) is None
    bad_u = e5_lane(knots=(1.0, 0.0), mult=(2, 2))
    assert parse(e5_payload(lane_u=bad_u)) is None


def test_a_zero_multiplicity_refuses() -> None:
    bad = e5_lane(mult=(0, 2))
    assert parse(e5_payload(lane_u=bad)) is None


def test_a_net_that_overruns_the_record_refuses() -> None:
    payload = e5_payload()
    # Cut into the pole net (the 148-byte tail is no closure law, so a
    # truncated tail must still decode).
    assert parse(payload[: payload.rindex(b"") if False else len(payload) - 40]) is not None
    assert parse(payload[: 160]) is None


def test_a_marker_outside_the_measured_pair_refuses() -> None:
    assert parse(e5_payload(marker=b"\x02\x00")) is None


def test_a_tag_outside_the_measured_one_refuses() -> None:
    payload = e5_payload()
    assert surface.parse_e5_surface(b"\x81" + payload[1:], 0, len(payload)) is None


# ------------------------------------------------------------------ walk


def test_the_admitted_run_walk_yields_the_surface_class() -> None:
    filler = e5_record(b"\x00" * 8, cls=0x000E, ident=1)
    surface_record = e5_record(e5_payload(), ident=2)
    filler2 = e5_record(b"\x00" * 8, cls=0x000D, ident=3)
    data = e5_part(filler + surface_record + filler2)
    records = grid.e5_records(data)
    assert [cls for _payload, _end, cls in records] == [0x000E, 0x00E7, 0x000D]
    frames = surface.e5_surface_frames(data)
    assert len(frames) == 1
    payload, end = frames[0]
    head = surface.parse_e5_surface(data, payload, end)
    assert head is not None
    assert head.points == 4


def test_a_lone_record_is_not_admitted() -> None:
    data = e5_part(e5_record(e5_payload()))
    assert grid.e5_records(data) == []
    assert surface.e5_surface_frames(data) == []


# ------------------------------------------------------------------ scan


def test_scan_folds_the_e5_route_when_a_surface_tessellates() -> None:
    filler = e5_record(b"\x00" * 8, cls=0x000E, ident=1)
    data = e5_part(filler + e5_record(e5_payload(), ident=2) + e5_record(e5_payload(), ident=3))
    scan = surface.scan_part(data)
    assert scan.candidates == 2
    assert (scan.e5_candidates, scan.e5_decoded, scan.e5_evaluable) == (2, 2, 2)
    assert scan.e5_tessellated == 2
    assert scan.tessellated == 2
    assert scan.evaluable == 2
    assert scan.has_mesh


def test_scan_keeps_the_pre_e5_totals_when_nothing_tessellates() -> None:
    # A decoded head whose poles sit outside the 1 km net band: the net
    # is implausible, nothing folds, and the E5 census is the only trace
    # the attempt left (the no-regret law).
    payload = e5_payload()
    head = parse(payload)
    assert head is not None
    huge = bytearray(payload)
    net = head.grid
    for j in range(head.poles_v):
        for i in range(head.poles_u):
            off = net + 24 * (j * head.poles_u + i)
            struct.pack_into("<3d", huge, off, 5e6 * i, 7e6 * j, 2e6)
    filler = e5_record(b"\x00" * 8, cls=0x000E, ident=1)
    data = e5_part(filler + e5_record(bytes(huge), ident=2) + e5_record(bytes(huge), ident=3))
    scan = surface.scan_part(data)
    assert (scan.e5_candidates, scan.e5_decoded) == (2, 0)
    assert (scan.e5_evaluable, scan.e5_tessellated, scan.e5_refused) == (0, 0, 0)
    # The totals are the pre-E5 ones: no candidate, no mesh.
    assert scan.candidates == 0
    assert not scan.has_mesh


def test_scan_folds_both_a5_and_e5_meshes() -> None:
    # The a5 route and the E5 route coexist: the merged mesh concatenates
    # both patches with disjoint index spaces.
    lane = e5_lane(degree=3, knots=(0.0, 1.0), mult=(4, 4))
    payload = e5_payload(lane_v=lane, lane_u=lane, poles_u=4, poles_v=4)
    data = e5_part(
        e5_record(b"\x00" * 8, cls=0x000E, ident=1)
        + e5_record(payload, ident=2)
        + e5_record(payload, ident=3)
    )
    scan = surface.scan_part(data)
    assert scan.e5_tessellated == 2
    assert scan.tessellated == 2
    assert len(scan.triangles) == 2 * len(surface.tessellate(
        parse(payload), *surface.e5_pole_data(payload, parse(payload))
    ).triangles)


# ------------------------------------------------------------------ port


def test_the_rust_twin_decodes_the_same_head() -> None:
    # The twin's test pins the same lane law in Rust; here the Python side
    # pins the exact payload shape the twin's fixture reproduces.
    payload = e5_payload(
        lane_v=e5_lane(degree=5, knots=(0.0, 0.5, 1.0), mult=(6, 3, 6)),
        lane_u=e5_lane(degree=5, knots=(0.0, 1.0), mult=(6, 6)),
        poles_u=6,
        poles_v=9,
    )
    head = parse(payload)
    assert head is not None
    assert (head.poles_u, head.poles_v) == (6, 9)
    assert head.tail == 148


# ---------------------------------------------------------- member filter


def collapsed_row_payload() -> bytes:
    """A slab whose two inner ``v`` pole rows coincide (a collapsed row).

    The collapsed interior row makes the surface constant on its knot
    span — every cell there is a zero-area degenerate member — while the
    battery still passes: the corner poles stay exact, the flat span's
    v-steps are exactly zero so the fold check skips them, and the
    surviving cells face one way.  This is the collapsed-pole-row
    mechanism behind the corpus's filtered members (the E5 tessellation's
    degenerate cells at knife edges and apex rows).
    """
    lane_v = e5_lane(degree=1, knots=(0.0, 0.5, 1.0), mult=(2, 1, 2))
    lane_u = e5_lane(degree=1, knots=(0.0, 1.0), mult=(2, 2))
    rows = [
        [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)],
        [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)],  # the collapsed row
        [(0.0, 1.0, 2.0), (10.0, 1.0, 2.0)],
    ]
    net = [point for row in rows for point in row]  # v-major outer
    return (
        b"\x80"
        + lane_v
        + lane_u
        + b"\x00\x00"
        + b"".join(f64(*point) for point in net)
        + bytes(148)
    )


def test_degenerate_members_are_filtered_not_counted() -> None:
    payload = collapsed_row_payload()
    head = parse(payload)
    assert head is not None
    assert (head.poles_u, head.poles_v) == (2, 3)
    poles, _ = surface.e5_pole_data(payload, head)
    assert surface.assess(head, poles).evaluable
    patch = surface.tessellate(head, poles)
    assert patch is not None
    assert patch.degenerate > 0  # the collapsed span's cells
    assert patch.triangles  # the valid strip still emits
    filler = e5_record(b"\x00" * 8, cls=0x000E, ident=1)
    data = e5_part(filler + e5_record(payload, ident=2) + e5_record(payload, ident=3))
    scan = surface.scan_part(data)
    # The member-filter law: the exported mesh carries no degenerate
    # triangle and the skips are named, never counted as degenerate.
    assert scan.degenerate == 0
    assert scan.degenerate_filtered == 2 * patch.degenerate
    assert scan.has_mesh


def test_export_names_the_filtered_members_and_passes_the_l2_gate(tmp_path) -> None:
    from catpart.fitness import runner
    from catpart.geometry import build_export

    payload = collapsed_row_payload()
    filler = e5_record(b"\x00" * 8, cls=0x000E, ident=1)
    records = filler + e5_record(payload, ident=2) + e5_record(payload, ident=3)
    block = fixtures_gen.storage_property_block(b"CATPrtCont", b"CATContainer")
    part_path = tmp_path / "collapsed.CATPart"
    part_path.write_bytes(
        fixtures_gen.build_catpart(
            header_dword=0x0000_0100,
            payload=block + b"\x00" * 64 + records,
            pad_before_table=0x600,
        )
    )
    summary = build_export(part_path, tmp_path / "collapsed.ply")
    assert summary["degenerate_triangle_count"] == 0
    classes = [warning["class"] for warning in summary["warnings"]]
    assert "surface-members-filtered" in classes
    assert "degenerate-triangles-skipped" not in classes
    detail = next(
        warning["detail"]
        for warning in summary["warnings"]
        if warning["class"] == "surface-members-filtered"
    )
    assert detail.startswith("16 degenerate tessellation member triangles filtered")
    # The L2 sanity gate passes: the first failed check is None.
    assert runner._score_export(summary)["status"] == runner.L2_PASS
