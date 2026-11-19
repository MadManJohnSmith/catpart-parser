"""Corpus-free tests for the structured point-grid **candidate** mesher.

The shipped module (``catpart.geometry.grid``) turns the committed E5 /
f64-net grid carriers into a mesh: an ``e5 0d`` record payload (or the
content-prefix f64 allocation) is fitted as a row-major ``rows x cols``
point net by the same shape law the E5 evidence note committed, and the
cells are triangulated two per quad.  Connectivity is an **inference**
(``connectivity = candidate``), never a decoded surface; every fixture
here is bytes built in this module and no corpus binary is read.

Pinned decisions:

- the row length is the **largest** divisor whose rows are near-constant
  in one coordinate (a smaller divisor splits a row, a larger one merges
  stations), and the ordering is row-major — a 4x5 net and its 5x4
  transpose are different grids, and the bytes decide which is which;
- a grid whose station or column steps stall (the corpus' trailing
  sentinel blocks) is refused, never partially emitted;
- the export fallback fires only when the nested-store path yields no
  facet triangles **and** no ``a5 03 34`` frame; a facet store and an
  a5 surface keep priority, and a grid candidate that cannot be
  triangulated raises the named ``untriangulable-grid`` class;
- the mesh is finite, has no degenerate triangle, a plausible bbox and a
  manifold cell complex, and its summary says the connectivity is a
  candidate.
"""

from __future__ import annotations

import hashlib
import math
import struct
from pathlib import Path

import pytest

from catpart.geometry import ExportError, build_export, grid, mesh

import fixtures_gen


def f64(*values: float) -> bytes:
    return b"".join(struct.pack("<d", value) for value in values)


def grid_points(rows: int, cols: int):
    """A row-major net: rows advance x/z, columns advance y."""
    return [
        (10.0 * i, 8.0 * j, 2.0 * i)
        for i in range(rows)
        for j in range(cols)
    ]


def record(cls: int, payload: bytes) -> bytes:
    return (
        b"\xe5\x0d"
        + b"\x03"
        + struct.pack("<H", cls)
        + struct.pack("<I", len(payload))
        + struct.pack("<I", 100)
        + payload
    )


def part(records: bytes) -> bytes:
    """A CATPrtCont block with a chained record run after it."""
    block = fixtures_gen.storage_property_block(b"CATPrtCont", b"CATContainer")
    return block + b"\x00" * 64 + records


def fixture(variant: str) -> bytes:
    return fixtures_gen.build_fixture("part", seed=0, variant=variant)


# ---------------------------------------------------------------- shape


def test_row_length_is_the_largest_admissible_divisor() -> None:
    shape = grid.fit_shape(grid_points(4, 5))
    assert shape is not None
    assert (shape.rows, shape.cols) == (4, 5)
    assert shape.spread == pytest.approx(0.0)
    # The transpose is a different grid, and the fit says so.
    shape = grid.fit_shape(grid_points(5, 4))
    assert shape is not None
    assert (shape.rows, shape.cols) == (5, 4)


def test_a_single_row_or_a_tiny_run_is_not_a_grid() -> None:
    row = [(0.0, float(j), 0.0) for j in range(30)]
    assert grid.fit_shape(row) is None
    assert grid.fit_shape([(0.0, 0.0, 0.0)] * 8) is None


def test_ordering_is_pinned_by_the_constant_row() -> None:
    # Row-major 4x5: every block of five points is one station row.
    shape = grid.fit_shape(grid_points(4, 5))
    assert shape.cols == 5
    # A 5x4 storage (the same 20 bytes interpreted column-major) has
    # constant blocks of four: the bytes pin the grouping, never a guess.
    shape = grid.fit_shape(grid_points(5, 4))
    assert shape.cols == 4


# ------------------------------------------------------------ candidates


def test_only_chained_records_are_admitted() -> None:
    payload = b"".join(f64(*point) for point in grid_points(4, 5))
    two = record(0x00E7, payload) + record(0x0018, b"\x01\x02\x03\x04")
    scan = grid.scan_part(part(two))
    assert scan.carriers == 0
    three = two + record(0x0018, b"\x05\x06\x07\x08")
    scan = grid.scan_part(part(three))
    assert scan.carriers == 1
    assert scan.shaped == 1
    assert scan.meshed == 1


def test_scan_merges_the_grid_with_two_triangles_per_cell() -> None:
    payload = b"".join(f64(*point) for point in grid_points(4, 5))
    scan = grid.scan_part(
        part(
            record(0x00E7, payload)
            + record(0x0018, b"\x01\x02\x03\x04")
            + record(0x0018, b"\x05\x06\x07\x08")
        )
    )
    assert scan.has_mesh
    assert scan.station_rows == 4
    assert scan.columns == 5
    assert scan.points == 20
    assert len(scan.triangles) == (4 - 1) * (5 - 1) * 2
    stats = mesh.mesh_stats(list(scan.triangles))
    assert stats.manifold
    assert not stats.closed
    assert stats.boundary_edges > 0
    assert all(math.isfinite(c) for point in scan.vertices for c in point)


def test_stalled_station_rows_are_refused_by_name() -> None:
    stalled = grid_points(5, 5)
    stalled[20:25] = stalled[15:20]  # the last station row repeats
    payload = b"".join(f64(*point) for point in stalled)
    scan = grid.scan_part(
        part(
            record(0x00E7, payload)
            + record(0x0018, b"\x01\x02\x03\x04")
            + record(0x0018, b"\x05\x06\x07\x08")
        )
    )
    assert scan.shaped == 1
    assert scan.meshed == 0
    assert dict(scan.refusals) == {grid.REFUSE_STALLED_STATIONS: 1}
    assert not scan.has_mesh
    assert scan.has_candidates


def test_identical_carriers_are_one_grid() -> None:
    payload = b"".join(f64(*point) for point in grid_points(4, 5))
    scan = grid.scan_part(
        part(
            record(0x00E7, payload)
            + record(0x00E7, payload)
            + record(0x0018, b"\x01\x02\x03\x04")
        )
    )
    assert scan.shaped == 2
    assert scan.duplicate_grids == 1
    assert scan.meshed == 1
    assert scan.points == 20


# ---------------------------------------------------------------- export


def test_export_falls_back_to_the_grid_mesh(tmp_path: Path) -> None:
    path = tmp_path / "grid.CATPart"
    path.write_bytes(fixture("geometry-point-grid"))
    out = tmp_path / "grid.ply"
    summary = build_export(path, out)
    assert summary["triangle_count"] == 24
    assert summary["vertex_count"] == 20
    assert summary["grid_meshing"]["connectivity"] == "candidate"
    assert summary["grid_meshing"]["meshed"] == 1
    assert summary["grid_meshing"]["shaped"] == 2
    assert summary["grid_meshing"]["refused"] == 1
    assert summary["grid_meshing"]["refusals"] == {"stalled-stations": 1}
    assert summary["grid_meshing"]["station_rows"] == 4
    assert summary["grid_meshing"]["columns"] == 5
    assert "surface_tessellation" not in summary
    classes = [warning["class"] for warning in summary["warnings"]]
    assert "point-grid-meshed" in classes
    assert "grid-candidates-refused" in classes
    assert "open-shell" in classes
    assert "candidate" in summary["warnings"][0]["detail"]
    assert summary["mesh"]["manifold"] is True
    assert summary["mesh"]["closed"] is False
    assert summary["degenerate_triangle_count"] == 0
    assert out.read_bytes().startswith(b"ply\nformat binary_little_endian 1.0\n")


def test_grid_export_is_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "grid.CATPart"
    path.write_bytes(fixture("geometry-point-grid"))
    first = tmp_path / "a.ply"
    second = tmp_path / "b.ply"
    build_export(path, first)
    build_export(path, second)
    assert hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(
        second.read_bytes()
    ).digest()


def test_facet_store_keeps_its_existing_path(tmp_path: Path) -> None:
    path = tmp_path / "facets.CATPart"
    path.write_bytes(fixture("geometry"))
    summary = build_export(path, tmp_path / "facets.ply")
    assert summary["triangle_count"] > 0
    assert "grid_meshing" not in summary
    assert "point-grid-meshed" not in [
        warning["class"] for warning in summary["warnings"]
    ]


def test_a5_surface_keeps_priority_over_the_grid_path(tmp_path: Path) -> None:
    path = tmp_path / "surface.CATPart"
    path.write_bytes(fixture("geometry-surface-bspline"))
    summary = build_export(path, tmp_path / "surface.ply")
    assert "surface_tessellation" in summary
    assert "grid_meshing" not in summary
    assert "point-grid-meshed" not in [
        warning["class"] for warning in summary["warnings"]
    ]


def test_untriangulable_grid_is_a_named_failure(tmp_path: Path) -> None:
    path = tmp_path / "stalled.CATPart"
    path.write_bytes(fixture("geometry-point-grid-stalled"))
    with pytest.raises(ExportError) as excinfo:
        build_export(path, tmp_path / "stalled.ply")
    assert excinfo.value.error_class == "untriangulable-grid"
    assert "stalled-stations=1" in excinfo.value.detail
    assert "candidate" in excinfo.value.detail


def test_part_without_a_grid_keeps_missing_geometry_store(tmp_path: Path) -> None:
    path = tmp_path / "plain.CATPart"
    path.write_bytes(fixtures_gen.build_fixture("part", seed=0))
    with pytest.raises(ExportError) as excinfo:
        build_export(path, tmp_path / "plain.ply")
    assert excinfo.value.error_class == "missing-geometry-store"
