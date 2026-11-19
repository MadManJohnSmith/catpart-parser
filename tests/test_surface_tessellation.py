"""Corpus-free tests for the exact B-spline surface tessellator.

The shipped module (``catpart.geometry.surface``) turns the ``a5 03 34``
payload grammar pinned by ``docs/evidence/2026-11-19-surface-head.md``
into a mesh.  Every ingredient here is built from bytes: a hand-written
head (two tagged knot lanes), a pole net, the measured 152-byte tail and
a ``CATPrtCont`` block the exporter's scanner can find.  No corpus binary
is read.

Pinned decisions:

- the head is self-delimiting (tag, lane counts, monotone lanes, closing
  bytes and tail all agree) and the grid is predicted, not searched for;
- the knot vector is clamped degree-5 with multiplicity 3, carries ``3n``
  poles and its basis partitions unity with the degree-5 support;
- the evaluable battery accepts the planar synthetic surface and refuses
  a zero-arc net as ``no-evaluable-surface`` (never an empty mesh);
- the adaptive tessellator produces a manifold open sheet, with zero
  degenerate triangles and a plausible bbox, and a tighter tolerance
  samples more points than a loose one;
- the export fallback fires only when the nested-store path yields no
  facet triangles: a facet store's summary is unchanged (no
  ``surface_tessellation`` key).
"""

from __future__ import annotations

import math
import struct
from pathlib import Path

import pytest

from catpart.geometry import ExportError, build_export, surface
from catpart.geometry import mesh

import fixtures_gen


def f64(*values: float) -> bytes:
    return b"".join(struct.pack("<d", value) for value in values)


def make_planar_poles(n_u: int = 4, n_v: int = 3):
    """The same net on z = 0: an exactly planar surface."""
    return [
        [(10.0 * i, 8.0 * j, 0.0) for j in range(3 * n_v)]
        for i in range(3 * n_u)
    ]


def make_poles(n_u: int = 4, n_v: int = 3, degenerate: bool = False):
    """A 3*n_u x 3*n_v pole net: swept x/y, gently curved in z."""
    if degenerate:
        return [[(0.0, 0.0, 0.0) for _ in range(3 * n_v)] for _ in range(3 * n_u)]
    return [
        [(10.0 * i, 8.0 * j, 0.02 * i * i) for j in range(3 * n_v)]
        for i in range(3 * n_u)
    ]


def head_bytes(
    knots_u: tuple[float, ...] = (0.0, 30.0, 60.0, 110.0),
    knots_v: tuple[float, ...] = (0.0, 24.0, 64.0),
) -> bytes:
    return (
        struct.pack("<IIBI", surface.HEAD_TAG, len(knots_u), 0, 2)
        + f64(*knots_u)
        + bytes([surface.LANE_TAG])
        + struct.pack("<IIBI", surface.HEAD_TAG, len(knots_v), 0, 2)
        + f64(*knots_v)
        + surface.CLOSING
    )


def payload(
    n_u: int = 4,
    n_v: int = 3,
    tail: int = 152,
    poles=None,
) -> bytes:
    if poles is None:
        poles = make_poles(n_u, n_v)
    return (
        head_bytes()
        + b"".join(f64(*point) for row in poles for point in row)
        + bytes(tail)
    )


def frame(blob: bytes) -> bytes:
    return (
        surface.SURFACE_MARKER
        + struct.pack("<I", len(blob))
        + b"\x0f"
        + blob
    )


def patch_head_bytes(
    knots_u: tuple[float, ...] = (0.0, 50.0),
    knots_v: tuple[float, ...] = (0.0, 16.0),
    degree_v: int = 2,
    rational: bool = False,
) -> bytes:
    """The subtype-4 head: no u mode, a stored v degree, a rational flag."""
    return (
        struct.pack("<II", surface.HEAD_TAG, len(knots_u))
        + bytes([surface.SUBTYPE_PATCH])
        + f64(*knots_u)
        + bytes([surface.LANE_TAG])
        + struct.pack("<II", degree_v, len(knots_v))
        + bytes([surface.SUBTYPE_PATCH])
        + f64(*knots_v)
        + bytes([0x01, 0x01 if rational else 0x00, 0x00])
    )


def patch_payload(rational: bool = False, bad_weight: bool = False) -> bytes:
    n_u, degree_v, n_v = 2, 2, 2
    poles_u = 3 * n_u
    poles_v = (degree_v + 1) + 3 * (n_v - 2)
    poles = b"".join(
        f64(10.0 * i, 8.0 * j, 0.02 * i * i)
        for i in range(poles_u)
        for j in range(poles_v)
    )
    if not rational:
        return patch_head_bytes(rational=False) + poles + bytes(152)
    weights = b"".join(
        f64(0.0 if bad_weight and i == 0 else 1.0)
        for i in range(poles_u)
        for _ in range(poles_v)
    )
    return patch_head_bytes(rational=True) + poles + weights + bytes(152)


def patch_part(rational: bool = False, bad_weight: bool = False) -> bytes:
    block = fixtures_gen.storage_property_block(b"CATPrtCont", b"CATContainer")
    return block + b"\x00" * 64 + frame(patch_payload(rational, bad_weight))


# --------------------------------------------------------------- patch


@pytest.mark.parametrize("rational", [False, True])
def test_patch_head_pins_the_v_degree_and_the_pole_law(rational: bool) -> None:
    blob = patch_payload(rational)
    head = surface.parse_surface_head(blob, 0, len(blob))
    assert head is not None
    assert head.subtype == surface.SUBTYPE_PATCH
    assert (head.n_u, head.n_v) == (2, 2)
    assert (head.degree_u, head.degree_v) == (5, 2)
    assert (head.poles_u, head.poles_v) == (6, 3)
    assert head.points == 18
    assert head.rational is rational
    assert head.bytes_per_pole == (32 if rational else 24)
    assert head.tail == 152
    poles, weights = surface.pole_data(blob, head)
    assert surface.plausible_net(poles)
    assert surface.plausible_weights(weights)
    assert surface.assess(head, poles, weights).evaluable
    assert surface.tessellate(head, poles, weights) is not None


def test_patch_with_a_non_positive_weight_is_not_decoded() -> None:
    blob = patch_payload(rational=True, bad_weight=True)
    head = surface.parse_surface_head(blob, 0, len(blob))
    assert head is not None
    _poles, weights = surface.pole_data(blob, head)
    assert not surface.plausible_weights(weights)
    scan = surface.scan_part(patch_part(rational=True, bad_weight=True))
    assert (scan.candidates, scan.decoded, scan.tessellated) == (1, 0, 0)


def test_patch_part_exports_a_mesh(tmp_path: Path) -> None:
    path = tmp_path / "patch.CATPart"
    path.write_bytes(patch_part())
    summary = build_export(path, tmp_path / "patch.ply")
    assert summary["triangle_count"] > 0
    assert summary["surface_tessellation"]["tessellated"] == 1
    assert summary["surface_tessellation"]["frames"] == 1


# --------------------------------------------------------------- head


def test_head_is_self_delimiting_and_predicts_the_grid() -> None:
    blob = payload()
    head = surface.parse_surface_head(blob, 0, len(blob))
    assert head is not None
    assert (head.n_u, head.n_v) == (4, 3)
    assert (head.poles_u, head.poles_v) == (12, 9)
    assert head.points == 108
    assert head.head_bytes == 30 + 8 * (4 + 3)
    assert head.grid == head.head_bytes
    assert head.tail == 152
    assert head.lanes_monotone


@pytest.mark.parametrize("tail", [152, 154])
def test_only_the_measured_tails_close(tail: int) -> None:
    blob = payload(tail=tail)
    assert surface.parse_surface_head(blob, 0, len(blob)).tail == tail
    bogus = payload(tail=150)
    assert surface.parse_surface_head(bogus, 0, len(bogus)) is None


def test_non_monotone_lane_is_refused() -> None:
    blob = head_bytes(knots_u=(0.0, 30.0, 20.0, 110.0)) + b"".join(
        f64(*point) for row in make_poles() for point in row
    ) + bytes(152)
    assert surface.parse_surface_head(blob, 0, len(blob)) is None


def test_knot_vector_is_clamped_degree_five_multiplicity_three() -> None:
    knots = surface.knot_vector((0.0, 30.0, 60.0, 110.0))
    assert len(knots) == 3 * 4 + 6
    assert knots[:6] == (0.0,) * 6
    assert knots[-6:] == (110.0,) * 6
    assert knots[6:9] == (30.0,) * 3
    assert knots[9:12] == (60.0,) * 3


def test_basis_partitions_unity_and_has_the_degree_five_support() -> None:
    distinct = (0.0, 30.0, 60.0, 110.0)
    knots = surface.knot_vector(distinct)
    count = 12
    for t in (0.0, 1.0, 15.0, 30.0, 45.0, 60.0, 90.0, 110.0):
        values = surface.basis_values(t, knots, surface.DEGREE, count)
        assert len(values) == count
        assert sum(values) == pytest.approx(1.0, abs=1e-12)
        assert all(value >= 0.0 for value in values)
    # Degree-5 support: six functions mid-span, three at a multiplicity-3
    # interior knot (the C2 signature), one at the clamped end.
    assert sum(1 for value in surface.basis_values(45.0, knots, surface.DEGREE, count) if value > 0.0) == 6
    assert sum(1 for value in surface.basis_values(30.0, knots, surface.DEGREE, count) if value > 0.0) == 3
    assert sum(1 for value in surface.basis_values(110.0, knots, surface.DEGREE, count) if value > 0.0) == 1


def test_evaluation_reproduces_the_corner_poles() -> None:
    poles = make_poles()
    head = surface.parse_surface_head(payload(), 0, len(payload()))
    knots_u, knots_v = head.knots
    corners = (
        (head.knots_u[0], head.knots_v[0], poles[0][0]),
        (head.knots_u[-1], head.knots_v[-1], poles[-1][-1]),
        (head.knots_u[0], head.knots_v[-1], poles[0][-1]),
        (head.knots_u[-1], head.knots_v[0], poles[-1][0]),
    )
    for u, v, expected in corners:
        assert surface.evaluate(poles, knots_u, knots_v, u, v) == pytest.approx(
            expected, abs=1e-9
        )


def test_assessment_accepts_the_synthetic_surface() -> None:
    blob = payload()
    head = surface.parse_surface_head(blob, 0, len(blob))
    poles = surface.pole_net(blob, head)
    assert surface.plausible_net(poles)
    assessment = surface.assess(head, poles)
    assert assessment.finite
    assert assessment.hull_violations == 0
    assert assessment.folds == 0
    assert assessment.plausible_scale
    assert assessment.evaluable


def test_zero_arc_net_is_not_evaluable() -> None:
    blob = payload(poles=make_poles(degenerate=True))
    head = surface.parse_surface_head(blob, 0, len(blob))
    assert head is not None
    assert not surface.assess(head, surface.pole_net(blob, head)).evaluable


# ----------------------------------------------------------- tessellation


def test_planar_patch_is_a_manifold_open_sheet() -> None:
    blob = payload(poles=make_planar_poles())
    head = surface.parse_surface_head(blob, 0, len(blob))
    patch = surface.tessellate(head, surface.pole_net(blob, head))
    assert patch is not None
    assert patch.triangles
    assert patch.degenerate == 0
    assert patch.manifold
    stats = mesh.mesh_stats(list(patch.triangles))
    assert stats.manifold
    assert not stats.closed
    assert stats.boundary_edges > 0
    assert all(abs(point[2]) < 1e-12 for point in patch.vertices)
    assert len(patch.vertices) == patch.grid_points


def test_tighter_tolerance_samples_more_points() -> None:
    blob = payload()
    head = surface.parse_surface_head(blob, 0, len(blob))
    poles = surface.pole_net(blob, head)
    loose = surface.tessellate(head, poles, tolerance_factor=1e-1)
    tight = surface.tessellate(head, poles, tolerance_factor=1e-6)
    assert loose is not None and tight is not None
    assert loose.tolerance > tight.tolerance
    assert loose.grid_points < tight.grid_points
    assert tight.tolerance == pytest.approx(loose.tolerance * 1e-5)


def test_every_tessellated_vertex_is_finite_and_inside_the_pole_hull() -> None:
    blob = payload()
    head = surface.parse_surface_head(blob, 0, len(blob))
    poles = surface.pole_net(blob, head)
    patch = surface.tessellate(head, poles)
    box = surface._bbox([point for row in poles for point in row])
    for x, y, z in patch.vertices:
        assert all(map(math.isfinite, (x, y, z)))
        assert box[0] - 1e-6 <= x <= box[1] + 1e-6
        assert box[2] - 1e-6 <= y <= box[3] + 1e-6
        assert box[4] - 1e-6 <= z <= box[5] + 1e-6


# ------------------------------------------------------- synthetic part


def _part(variant: str) -> bytes:
    return fixtures_gen.build_fixture("part", seed=0, variant=variant)


def test_scan_part_censuses_the_synthetic_record() -> None:
    region = surface.scan_part(_part("geometry-surface-bspline"))
    assert region.candidates == 1
    assert region.decoded == 1
    assert region.evaluable == 1
    assert region.tessellated == 1
    assert region.refused == 0
    assert region.has_mesh
    stats = mesh.mesh_stats(list(region.triangles))
    assert stats.manifold


@pytest.mark.parametrize(
    "variant", ["geometry-surface-patch", "geometry-surface-patch-rational"]
)
def test_scan_part_censuses_the_patch_variants(variant: str) -> None:
    region = surface.scan_part(_part(variant))
    assert region.candidates == 1
    assert region.decoded == 1
    assert region.evaluable == 1
    assert region.tessellated == 1
    assert region.refused == 0
    assert region.has_mesh


def test_part_without_surface_frames_has_no_mesh() -> None:
    region = surface.scan_part(_part("geometry"))
    assert region.candidates == 0
    assert not region.has_mesh


# ------------------------------------------------------------- export


def test_export_falls_back_to_the_surface_mesh(tmp_path: Path) -> None:
    path = tmp_path / "surface.CATPart"
    path.write_bytes(_part("geometry-surface-bspline"))
    out = tmp_path / "surface.ply"
    summary = build_export(path, out)
    assert summary["triangle_count"] > 0
    assert summary["vertex_count"] > 0
    assert summary["surface_tessellation"]["frames"] == 1
    assert summary["surface_tessellation"]["tessellated"] == 1
    assert "bspline-surface-tessellated" in [
        warning["class"] for warning in summary["warnings"]
    ]
    assert "open-shell" in [warning["class"] for warning in summary["warnings"]]
    assert summary["mesh"]["manifold"] is True
    assert summary["mesh"]["closed"] is False
    assert out.read_bytes().startswith(b"ply\nformat binary_little_endian 1.0\n")


@pytest.mark.parametrize(
    "variant", ["geometry-surface-patch", "geometry-surface-patch-rational"]
)
def test_patch_variant_exports_a_mesh(tmp_path: Path, variant: str) -> None:
    path = tmp_path / f"{variant}.CATPart"
    path.write_bytes(_part(variant))
    summary = build_export(path, tmp_path / f"{variant}.ply")
    assert summary["triangle_count"] > 0
    assert summary["surface_tessellation"]["frames"] == 1
    assert summary["surface_tessellation"]["tessellated"] == 1
    assert summary["mesh"]["manifold"] is True


def test_facet_store_keeps_its_existing_path(tmp_path: Path) -> None:
    path = tmp_path / "facets.CATPart"
    path.write_bytes(_part("geometry"))
    summary = build_export(path, tmp_path / "facets.ply")
    assert summary["triangle_count"] > 0
    assert "surface_tessellation" not in summary
    assert "bspline-surface-tessellated" not in [
        warning["class"] for warning in summary["warnings"]
    ]


def test_no_evaluable_surface_is_a_named_failure(tmp_path: Path) -> None:
    path = tmp_path / "no-surface.CATPart"
    path.write_bytes(_part("geometry-surface-no-evaluable"))
    with pytest.raises(ExportError) as excinfo:
        build_export(path, tmp_path / "no-surface.ply")
    assert excinfo.value.error_class == "no-evaluable-surface"
    assert "no surface produced a sane mesh" in excinfo.value.detail


def test_store_less_part_keeps_missing_geometry_store(tmp_path: Path) -> None:
    path = tmp_path / "plain.CATPart"
    path.write_bytes(fixtures_gen.build_fixture("part", seed=0))
    with pytest.raises(ExportError) as excinfo:
        build_export(path, tmp_path / "plain.ply")
    assert excinfo.value.error_class == "missing-geometry-store"
