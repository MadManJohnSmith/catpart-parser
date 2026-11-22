"""The ground-truth fidelity harness's tests (marathon W7).

Pinned edges, on synthetic fixtures (the negative-fixture rule, with
the harness's own ``--selftest`` as the committed --selftest mode):

- identical meshes -> Chamfer 0, Hausdorff p95/max 0, area_ratio 1.0 —
  proven BOTH on the library metrics (synthetic cubes) and END TO END
  (a geometry-bearing .CATPart exported by the shipped seam, its PLY
  converted to binary STL, measured back against itself);
- a unit translation -> directed Hausdorff exactly the shift;
- a 2x scale -> area_ratio exactly 4.0;
- the stated blind spot: a vertex-identical density change passes
  Hausdorff/Chamfer and is caught ONLY by area_ratio;
- ``.STEP`` reference -> the named refusal (exit 2), never a fake mesh.
"""

from __future__ import annotations

import importlib.util
import struct
from pathlib import Path


from fixtures_gen import build_fixture

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "benchmark_ground_truth.py"


def load_harness():
    spec = importlib.util.spec_from_file_location("benchmark_ground_truth", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gt = load_harness()

TOL = 1e-5
CUBE_TRIANGLES = (
    (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
    (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
    (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7),
)
CUBE_CORNERS = (
    (0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
    (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1),
)


def _cube_mesh(scale: float = 1.0, shift: tuple[float, float, float] = (0.0, 0.0, 0.0)):
    mesh = gt.MeshData()
    for x, y, z in CUBE_CORNERS:
        mesh.vertices.extend(((x + shift[0]) * scale, (y + shift[1]) * scale, (z + shift[2]) * scale))
    for tri in CUBE_TRIANGLES:
        mesh.triangles.extend(tri)
    return mesh


def _write_binary_stl(path: Path, mesh) -> None:
    """Minimal binary STL writer for the fixtures (normals zeroed —
    the harness reads geometry, never shading)."""
    with path.open("wb") as fh:
        fh.write(b"ground-truth fixture".ljust(80, b"\0"))
        fh.write(struct.pack("<I", mesh.triangle_count))
        for i in range(mesh.triangle_count):
            t = mesh.triangles[i * 3 : i * 3 + 3]
            record = struct.pack("<12f", 0.0, 0.0, 0.0, *[v for idx in t for v in mesh.vertex(idx)])
            fh.write(record + struct.pack("<H", 0))


def _write_ascii_stl(path: Path, mesh) -> None:
    with path.open("w", encoding="utf-8") as fh:
        fh.write("solid cube\n")
        for i in range(mesh.triangle_count):
            t = mesh.triangles[i * 3 : i * 3 + 3]
            fh.write("facet normal 0 0 0\nouter loop\n")
            for idx in t:
                x, y, z = mesh.vertex(idx)
                fh.write(f"vertex {x!r} {y!r} {z!r}\n")
            fh.write("endloop\nendfacet\n")
        fh.write("endsolid cube\n")


# --- the library metrics -----------------------------------------------------


def test_identical_meshes_zero_everywhere() -> None:
    base, other = _cube_mesh(), _cube_mesh()
    grid = gt.VertexGrid(other, 0.25)
    distances, mean, peak = gt.directed_distances(base, grid)
    assert mean == 0.0 and peak == 0.0
    assert gt.percentile(sorted(distances), 0.95) == 0.0
    assert abs(gt.total_area(base) / gt.total_area(other) - 1.0) <= TOL


def test_unit_shift_is_the_directed_hausdorff() -> None:
    base, shifted = _cube_mesh(), _cube_mesh(shift=(1.0, 0.0, 0.0))
    _, _, peak = gt.directed_distances(base, gt.VertexGrid(shifted, 0.25))
    assert abs(peak - 1.0) <= TOL
    _, _, back = gt.directed_distances(shifted, gt.VertexGrid(base, 0.25))
    assert abs(back - 1.0) <= TOL


def test_2x_scale_doubles_nothing_and_quadruples_area() -> None:
    base, scaled = _cube_mesh(), _cube_mesh(scale=2.0)
    ratio = gt.total_area(scaled) / gt.total_area(base)
    assert abs(ratio - 4.0) <= TOL
    _, _, peak = gt.directed_distances(base, gt.VertexGrid(scaled, 0.25))
    assert peak > 0.5, "a scaled cube's vertices are NOT within Hausdorff 0.5"


def test_density_change_is_the_named_blind_spot() -> None:
    """The detector's stated non-discrimination, pinned as a negative:
    same vertices, doubled triangle list -> Hausdorff 0, area 2x
    (caught ONLY by area_ratio)."""
    base, dense = _cube_mesh(), _cube_mesh()
    dense.triangles.extend(base.triangles)
    _, _, peak = gt.directed_distances(base, gt.VertexGrid(dense, 0.25))
    assert peak <= TOL, "the vertex blind spot must stay a blind spot"
    assert abs(gt.total_area(dense) / gt.total_area(base) - 2.0) <= TOL


def test_stl_binary_and_ascii_readers_agree() -> None:
    cube = _cube_mesh()
    binary_path, ascii_path = Path("/tmp/gt-binary.stl"), Path("/tmp/gt-ascii.stl")
    _write_binary_stl(binary_path, cube)
    _write_ascii_stl(ascii_path, cube)
    from_binary, from_ascii = gt._read_stl(binary_path), gt._read_stl(ascii_path)
    assert from_binary.vertex_count == 8, "STL per-facet duplication must dedup to the 8 cube corners"
    assert from_ascii.vertex_count == from_binary.vertex_count
    assert abs(gt.total_area(from_ascii) - gt.total_area(from_binary)) <= TOL
    assert abs(gt.total_area(from_binary) - gt.total_area(cube)) <= TOL
    binary_path.unlink()
    ascii_path.unlink()


# --- end to end: CATPart export vs STL of the same mesh ----------------------


def _geometry_fixture(tmp_path: Path) -> Path:
    path = tmp_path / "geometry.CATPart"
    path.write_bytes(build_fixture(variant="geometry"))
    return path


def test_measure_pair_catpart_vs_same_mesh_stl_is_zero(tmp_path: Path) -> None:
    """The harness's headline invariant: comparing the shipped export
    against a reference mesh OF THE SAME GEOMETRY gives Hausdorff 0,
    Chamfer 0, area_ratio 1 — .CATPart to .STL, end to end."""
    catpart_path = _geometry_fixture(tmp_path)
    ply_path = tmp_path / "export.ply"
    from catpart.geometry import build_export

    build_export(catpart_path, ply_path)
    mesh = gt._read_binary_le_ply(ply_path)
    assert mesh.vertex_count > 0 and mesh.triangle_count > 0
    stl_path = tmp_path / "reference.stl"
    _write_binary_stl(stl_path, mesh)

    record = gt.measure_pair(catpart_path, stl_path)
    assert record["outcome"] == gt.OUTCOME_METRICS, record
    assert record["hausdorff_max"] <= TOL, "identical geometry must give Hausdorff 0"
    assert record["hausdorff_p95"] <= TOL
    assert record["chamfer"] <= TOL
    assert abs(record["area_ratio"] - 1.0) <= TOL
    assert record["exact_nearest"] is True


def test_measure_pair_shifted_reference_tracks_hausdorff(tmp_path: Path) -> None:
    """A translated reference (1 unit in x) must show up: the directed
    Hausdorff to it is the shift, from a real exporter's mesh."""
    catpart_path = _geometry_fixture(tmp_path)
    ply_path = tmp_path / "export.ply"
    from catpart.geometry import build_export

    build_export(catpart_path, ply_path)
    mesh = gt._read_binary_le_ply(ply_path)
    shifted = gt.MeshData()
    shifted.vertices.extend(mesh.vertices)
    shifted.triangles.extend(mesh.triangles)
    for i in range(shifted.vertex_count):
        shifted.vertices[i * 3] += 1.0
    stl_path = tmp_path / "shifted.stl"
    _write_binary_stl(stl_path, shifted)

    record = gt.measure_pair(catpart_path, stl_path)
    assert record["outcome"] == gt.OUTCOME_METRICS
    assert record["hausdorff_ab_max"] >= 1.0 - 1e-3, "the shift must appear A->B"
    assert record["area_ratio"] <= 1.0 + TOL and record["area_ratio"] >= 1.0 - TOL


def test_measure_pair_refuses_step_by_name(tmp_path: Path) -> None:
    catpart_path = _geometry_fixture(tmp_path)
    step_path = tmp_path / "reference.step"
    step_path.write_bytes(b"ISO-10303-21;\nEND-ISO-10303-21;\n")
    record = gt.measure_pair(catpart_path, step_path)
    assert record["outcome"] == gt.OUTCOME_STEP_REFUSED, record
    assert gt.main(["--catpart", str(catpart_path), "--reference", str(step_path)]) == 2


def test_main_selftest_is_green() -> None:
    assert gt.main(["--selftest"]) == 0


def test_storeless_catpart_is_a_named_outcome(tmp_path: Path) -> None:
    """A geometry-store-less CATPart: the export seam's classified
    failure is the record's outcome (exit 2 via main), never a fake 0."""
    path = tmp_path / "plain.CATPart"
    path.write_bytes(build_fixture())  # canonical: no geometry store
    record = gt.measure_pair(path, tmp_path / "unused.stl")
    assert record["outcome"] == gt.OUTCOME_EXPORT_FAILURE, record
    assert record["error_class"] == "missing-geometry-store"


def test_batch_mode_streams_one_row_per_pair(tmp_path: Path) -> None:
    catpart_path = _geometry_fixture(tmp_path)
    ply_path = tmp_path / "export.ply"
    from catpart.geometry import build_export

    build_export(catpart_path, ply_path)
    mesh = gt._read_binary_le_ply(ply_path)
    stl_path = tmp_path / "reference.stl"
    _write_binary_stl(stl_path, mesh)
    step_path = tmp_path / "ref.step"
    step_path.write_bytes(b"ISO-10303-21;\n")
    pairs = tmp_path / "pairs.csv"
    pairs.write_text(
        "catpart_path,reference_path\n"
        + f"{catpart_path},{stl_path}\n"
        + f"{catpart_path},{step_path}\n",
        encoding="utf-8",
    )
    out_csv = tmp_path / "batch.csv"
    code = gt.main(["--batch", str(pairs), "--csv", str(out_csv)])
    assert code == 2  # the STEP row refuses; the metrics row succeeded
    rows = out_csv.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 3, "one CSV row per pair, streamed"
    assert rows[0].startswith("catpart_path,")
    metrics_row, step_row = rows[1].split(","), rows[2].split(",")
    assert metrics_row[2] == gt.OUTCOME_METRICS
    assert step_row[2] == gt.OUTCOME_STEP_REFUSED
