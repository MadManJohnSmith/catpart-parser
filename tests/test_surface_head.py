"""Corpus-free tests for the ``a5 03 34`` surface-head probe (2026-11-19).

The probe (``scripts/triage/probe_surface_head.py``) decodes the payload
head of a class-``0x34`` surface record: two tagged lane blocks carrying the
u and v knot values, and the pole-count law that follows from their
lengths.  These tests build every ingredient from bytes and pin the
decisions the evidence note rests on:

- the head grammar is self-delimiting: the parser accepts a head only when
  the tag, both lane counts, both monotone lanes, the closing bytes and the
  measured 152/154-byte tail all agree, so the pole grid's offset is
  *predicted* rather than searched for;
- the knot vector built from a lane is clamped degree-5 with
  multiplicity-3 interior knots, its length is ``3n + 6`` and it therefore
  carries ``3n`` poles per direction;
- the basis functions partition unity and have the degree-5 support
  (six mid-span, three at a multiplicity-3 knot — the C2 signature);
- evaluation reproduces the corner poles exactly and stays inside the pole
  hull, and the fold/scale/arc-ratio checks reject the shapes they should;
- the degree census admits only ``(5, 3)`` when the grid law
  ``points = 9 * n_u * n_v`` holds.

Fixtures are synthetic; no corpus binary is read.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "triage"))

import probe_surface_head as probe  # noqa: E402


def f64(*vals: float) -> bytes:
    return b"".join(struct.pack("<d", v) for v in vals)


def lanes(n: int, step: float = 10.0, start: float = 0.0) -> list[float]:
    return [start + step * i for i in range(n)]


def head_bytes(
    n_u: int = 4,
    n_v: int = 3,
    mode_u: int = 2,
    mode_v: int = 2,
    knots_u: list[float] | None = None,
    knots_v: list[float] | None = None,
) -> bytes:
    """A hand-built payload head, independent of the parser's own layout."""
    ku = knots_u if knots_u is not None else lanes(n_u)
    kv = knots_v if knots_v is not None else lanes(n_v)
    return (
        struct.pack("<IIBI", probe.HEAD_TAG, len(ku), 0, mode_u)
        + f64(*ku)
        + bytes([probe.LANE_TAG])
        + struct.pack("<IIBI", probe.HEAD_TAG, len(kv), 0, mode_v)
        + f64(*kv)
        + probe.CLOSING
    )


def plane_poles(n_u: int = 4, n_v: int = 3, scale: float = 10.0):
    """A planar pole net: row i along x, column j along y, z = 0."""
    return [
        [(scale * i, scale * j, 0.0) for j in range(3 * n_v)]
        for i in range(3 * n_u)
    ]


def pole_bytes(poles) -> bytes:
    return b"".join(f64(*point) for row in poles for point in row)


def payload(
    n_u: int = 4,
    n_v: int = 3,
    tail: int = 152,
    poles=None,
    **kwargs,
) -> tuple[bytes, int]:
    """A whole payload: head + pole grid + tail.  Returns ``(bytes, grid)``."""
    if poles is None:
        poles = plane_poles(n_u, n_v)
    head = head_bytes(n_u=n_u, n_v=n_v, **kwargs)
    return head + pole_bytes(poles) + bytes(tail), len(head)


def grid_bytes(grid: bytes) -> list[list[tuple[float, float, float]]]:
    return [
        [struct.unpack_from("<3d", grid, 24 * (i * 3 + j)) for j in range(3)]
        for i in range(3)
    ]


# ------------------------------------------------------------------- head


def test_head_parses_and_predicts_the_grid() -> None:
    blob, grid = payload(n_u=4, n_v=3, mode_u=3, mode_v=2)
    head = probe.parse_surface_head(blob, 0, len(blob))
    assert head is not None
    assert (head.n_u, head.n_v) == (4, 3)
    assert (head.mode_u, head.mode_v) == (3, 2)
    assert head.grid == grid
    assert head.head_bytes == 30 + 8 * (4 + 3)
    assert (head.poles_u, head.poles_v) == (12, 9)
    assert head.points == 108
    assert head.tail == 152
    assert head.knots_u == tuple(lanes(4))
    assert head.knots_v == tuple(lanes(3))
    assert head.lanes_monotone


@pytest.mark.parametrize("tail", [152, 154])
def test_head_accepts_both_measured_tails(tail: int) -> None:
    blob, _ = payload(tail=tail)
    head = probe.parse_surface_head(blob, 0, len(blob))
    assert head is not None
    assert head.tail == tail


def test_head_refuses_wrong_tag() -> None:
    blob, _ = payload()
    broken = bytearray(blob)
    broken[0:4] = struct.pack("<I", 6)
    assert probe.parse_surface_head(bytes(broken), 0, len(broken)) is None


def test_head_refuses_non_monotone_lane() -> None:
    blob, _ = payload(knots_u=[0.0, 20.0, 10.0, 30.0])
    assert probe.parse_surface_head(blob, 0, len(blob)) is None


def test_head_refuses_broken_closing_bytes() -> None:
    blob, grid = payload()
    broken = bytearray(blob)
    broken[grid - 1] = 0x02  # the last closing byte is part of the head
    assert probe.parse_surface_head(bytes(broken), 0, len(blob)) is None


def test_head_refuses_unmeasured_tail() -> None:
    blob, _ = payload(tail=160)
    assert probe.parse_surface_head(blob, 0, len(blob)) is None


def test_head_refuses_the_plane_subtype() -> None:
    # The 20 twelve-triple records carry subtype byte 4 at +8 and mode 0;
    # they are a second grammar, so the two-lane parser must not accept them.
    blob, _ = payload(tail=152)
    broken = bytearray(blob)
    broken[8] = 4
    assert probe.parse_surface_head(bytes(broken), 0, len(broken)) is None


# ----------------------------------------------------------------- knots


@pytest.mark.parametrize("n", [2, 3, 7, 12, 17])
def test_knot_vector_is_clamped_degree_five(n: int) -> None:
    distinct = lanes(n)
    knots = probe._knot_vector(distinct)
    assert len(knots) == 3 * n + 6
    assert knots[:6] == (distinct[0],) * 6
    assert knots[-6:] == (distinct[-1],) * 6
    assert all(a <= b for a, b in zip(knots, knots[1:]))
    # every interior value appears exactly MULTIPLICITY times
    for value in distinct[1:-1]:
        assert knots.count(value) == probe.MULTIPLICITY


def test_knot_vector_needs_two_values() -> None:
    with pytest.raises(ValueError):
        probe._knot_vector([1.0])


def test_pole_count_law_matches_the_clamped_arithmetic() -> None:
    for n in (2, 5, 12, 17, 33):
        assert probe._clamped_poles(n, probe.DEGREE, probe.MULTIPLICITY) == 3 * n


# --------------------------------------------------------------- basis


def test_basis_partitions_unity() -> None:
    knots = probe._knot_vector(lanes(5))
    count = 15
    for k in range(41):
        t = knots[0] + (knots[-1] - knots[0]) * k / 40
        total = sum(probe.basis_values(t, knots, probe.DEGREE, count))
        assert total == pytest.approx(1.0, abs=1e-12)


def test_basis_support_is_degree_five_and_c2_at_a_knot() -> None:
    distinct = lanes(5)
    knots = probe._knot_vector(distinct)
    count = 15
    mid = 0.5 * (distinct[0] + distinct[1])
    at_knot = distinct[1]
    support = lambda t: sum(  # noqa: E731
        1 for v in probe.basis_values(t, knots, probe.DEGREE, count) if v > 0
    )
    assert support(mid) == probe.DEGREE + 1
    # a multiplicity-3 knot leaves DEGREE + 1 - 3 nonzero basis functions
    assert support(at_knot) == probe.DEGREE + 1 - probe.MULTIPLICITY


# ----------------------------------------------------------- evaluation


def test_evaluation_reproduces_corner_poles() -> None:
    n_u, n_v = 4, 3
    head = probe.parse_surface_head(*_single(payload(n_u=n_u, n_v=n_v)))
    assert head is not None
    poles = plane_poles(n_u, n_v)
    knots_u, knots_v = head.knots
    u0, u1 = head.knots_u[0], head.knots_u[-1]
    v0, v1 = head.knots_v[0], head.knots_v[-1]
    for (u, v), corner in (
        ((u0, v0), poles[0][0]),
        ((u1, v0), poles[-1][0]),
        ((u0, v1), poles[0][-1]),
        ((u1, v1), poles[-1][-1]),
    ):
        assert probe.evaluate(poles, knots_u, knots_v, u, v) == pytest.approx(corner)


def test_plane_surface_validates() -> None:
    n_u, n_v = 4, 3
    nu, nv = 3 * n_u, 3 * n_v
    # Chord-length knots: the lane spans the pole polygon's arc length, which
    # is what makes arc_ratio 1.0.
    blob, _ = payload(
        n_u=n_u,
        n_v=n_v,
        knots_u=[10.0 * (nu - 1) * i / (n_u - 1) for i in range(n_u)],
        knots_v=[10.0 * (nv - 1) * j / (n_v - 1) for j in range(n_v)],
    )
    head = probe.parse_surface_head(blob, 0, len(blob))
    assert head is not None
    poles = plane_poles(n_u, n_v)
    fit = probe.validate(head, poles)
    assert fit.corner_residual <= 1e-12
    assert fit.finite
    assert fit.hull_violations == 0
    assert fit.folds == 0
    assert fit.arc_ratio == pytest.approx(1.0, rel=1e-9)
    # This net is deliberately coarse (4x3 lane entries); the corpus shapes,
    # with 7..17 entries, measure 0.06..0.11 of the diagonal.
    assert 0.0 < fit.tightness < 0.5
    assert fit.ok and fit.usable


def test_scale_and_arc_ratio_reject_a_kilometre_net() -> None:
    head = probe.parse_surface_head(*_single(payload(n_u=4, n_v=3)))
    assert head is not None
    poles = plane_poles(4, 3, scale=1e6)
    fit = probe.validate(head, poles)
    assert not fit.plausible_scale
    assert fit.arc_ratio < probe.ARC_RATIO_BAND[0]
    assert not fit.usable


def test_folding_net_is_rejected() -> None:
    # Rows double back in u after the middle, so the surface folds: adjacent
    # cell normals reverse even though every point is finite and in hull.
    n_u, n_v = 4, 3
    nu, nv = 3 * n_u, 3 * n_v
    poles = [
        [(10.0 * (i if i < nu // 2 else nu - i), 10.0 * j, 0.0) for j in range(nv)]
        for i in range(nu)
    ]
    head = probe.parse_surface_head(*_single(payload(n_u=n_u, n_v=n_v)))
    assert head is not None
    fit = probe.validate(head, poles)
    assert fit.finite
    assert not fit.ok or fit.folds > 0


# ------------------------------------------------------------- census


def test_degree_census_pins_five_three() -> None:
    shapes = [(9 * 12 * 7, 12, 7), (9 * 8 * 6, 8, 6), (9 * 11 * 11, 11, 11)]
    census = probe.degree_census(shapes)
    assert census[(5, 3)] == len(shapes)
    assert all(hits == 0 for key, hits in census.items() if key != (5, 3))


def test_degree_census_rejects_a_grid_that_breaks_the_law() -> None:
    # A grid whose point count is not 9*n_u*n_v is explained by no hypothesis.
    shapes = [(100, 4, 3)]
    assert all(hits == 0 for hits in probe.degree_census(shapes).values())


def _single(prepared):
    blob, grid = prepared
    return blob, 0, len(blob)
