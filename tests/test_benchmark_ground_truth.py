"""The ground-truth fidelity harness's tests (marathon W7 + W24).

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
- ``.STEP`` reference -> the named refusal (exit 2), never a fake mesh;
- W24 normalization: a tenth-scale reference (the Dodge cross-unit
  shape) -> ``--ref-scale auto`` infers factor 10 with area unit 100
  and collapses the pair to Hausdorff ~0; a unit-matched reference
  (the Audi/Motor shape) stays at factor 1 with metrics IDENTICAL to
  the raw pairing; an unexplainable diagonal ratio is the named
  ``normalization-uncertain`` refusal (exit 2); forced ``1``/``10``
  bypass the confidence window but report the measured ratio.
"""

from __future__ import annotations

import importlib.util
import struct
from pathlib import Path

import pytest

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


# --- W24: the per-pair normalization -----------------------------------------


def _scaled_copy(mesh, factor: float):
    """A scaled duplicate of a mesh (the cross-unit reference shape)."""
    scaled = gt.MeshData()
    scaled.vertices.extend(mesh.vertices)
    scaled.triangles.extend(mesh.triangles)
    gt.scale_mesh(scaled, factor)
    return scaled


def _exported_mesh(tmp_path: Path):
    """The shipped seam's mesh for the geometry fixture (exported once
    per test — the CATPart side of every synthetic pair below)."""
    catpart_path = _geometry_fixture(tmp_path)
    ply_path = tmp_path / "export.ply"
    from catpart.geometry import build_export

    build_export(catpart_path, ply_path)
    return catpart_path, gt._read_binary_le_ply(ply_path)


# The f32 round trip (coords -> x0.1 -> STL float32 -> x10) perturbs
# coordinates by ~6e-8 relative (~1e-4 absolute at fixture scale): the
# normalized zero is pinned at 1e-3, not bit zero.
SCALE_ROUNDTRIP_TOL = 1e-3


def test_auto_infers_ten_on_a_tenth_scale_reference_and_collapses_it(tmp_path: Path) -> None:
    """The Dodge cross-unit shape, synthetic: the reference is the same
    mesh at x0.1 (cm-space vs the file's mm). Auto infers factor 10,
    reports the area unit x100, and the normalized pair collapses to
    Hausdorff ~0 with area_ratio 1 (raw ratio 100 travels alongside)."""
    catpart_path, mesh = _exported_mesh(tmp_path)
    stl_path = tmp_path / "tenth-scale.stl"
    _write_binary_stl(stl_path, _scaled_copy(mesh, 0.1))

    record = gt.measure_pair(catpart_path, stl_path, ref_scale="auto")
    assert record["outcome"] == gt.OUTCOME_METRICS, record
    assert record["ref_scale_mode"] == "auto"
    assert record["ref_scale_factor"] == 10.0
    assert record["area_unit_factor"] == 100.0
    assert record["normalization"]["resolution"] == "auto"
    assert record["normalization"]["basis"] == "bbox-diagonal"
    assert abs(record["normalization"]["raw_diagonal_ratio"] - 10.0) <= SCALE_ROUNDTRIP_TOL
    assert record["hausdorff_max"] <= SCALE_ROUNDTRIP_TOL, "x10 normalization must collapse the pair"
    assert record["hausdorff_p95"] <= SCALE_ROUNDTRIP_TOL
    assert record["chamfer"] <= SCALE_ROUNDTRIP_TOL
    assert abs(record["area_ratio"] - 1.0) <= SCALE_ROUNDTRIP_TOL
    assert abs(record["area_ratio_raw"] - 100.0) <= 1.0, "the raw cm2-vs-mm2 ratio must stay visible"


def test_auto_normalizes_nothing_on_a_unit_matched_pair(tmp_path: Path) -> None:
    """The Audi/Motor shape (diag ratio ~1, real pairs sit at Hausdorff
    0.0007/0.00003 mm): auto keeps factor 1 and the metrics are
    IDENTICAL to the raw pairing — no silent rescale of honest pairs."""
    catpart_path, mesh = _exported_mesh(tmp_path)
    stl_path = tmp_path / "same-units.stl"
    _write_binary_stl(stl_path, mesh)

    auto_record = gt.measure_pair(catpart_path, stl_path, ref_scale="auto")
    raw_record = gt.measure_pair(catpart_path, stl_path, ref_scale="1")
    assert auto_record["outcome"] == gt.OUTCOME_METRICS, auto_record
    assert auto_record["ref_scale_factor"] == 1.0
    assert auto_record["area_unit_factor"] == 1.0
    assert auto_record["normalization"]["raw_diagonal_ratio"] == 1.0
    assert auto_record["hausdorff_max"] <= TOL and auto_record["chamfer"] <= TOL
    for key in ("area_ratio", "area_ratio_raw", "chamfer", "hausdorff_max", "hausdorff_p95"):
        assert auto_record[key] == raw_record[key], f"{key} must not move on a unit-matched pair"


def test_forced_one_keeps_a_cross_unit_pair_raw(tmp_path: Path) -> None:
    """--ref-scale 1 on the x10 pair: no normalization (the operator's
    override), and the raw unit garbage shows — area_ratio 100, the
    scaled Hausdorff unfixed."""
    catpart_path, mesh = _exported_mesh(tmp_path)
    stl_path = tmp_path / "tenth-scale.stl"
    _write_binary_stl(stl_path, _scaled_copy(mesh, 0.1))

    record = gt.measure_pair(catpart_path, stl_path, ref_scale="1")
    assert record["outcome"] == gt.OUTCOME_METRICS, record
    assert record["ref_scale_factor"] == 1.0
    assert record["normalization"]["resolution"] == "forced"
    assert abs(record["area_ratio"] - 100.0) <= 1.0
    assert record["hausdorff_ab_max"] >= 1.0, "the raw pairing must show the scale gap"


def test_auto_refuses_an_unexplainable_diagonal_ratio(tmp_path: Path) -> None:
    """A reference at x0.37 (diag ratio ~2.7, inside no candidate's
    window): the named refusal, exit 2, no fabricated metrics."""
    catpart_path, mesh = _exported_mesh(tmp_path)
    stl_path = tmp_path / "odd-scale.stl"
    _write_binary_stl(stl_path, _scaled_copy(mesh, 0.37))

    record = gt.measure_pair(catpart_path, stl_path, ref_scale="auto")
    assert record["outcome"] == gt.OUTCOME_NORMALIZATION_UNCERTAIN, record
    assert "chamfer" not in record and "area_ratio" not in record, "a refusal carries no metrics"
    assert abs(record["raw_diagonal_ratio"] - 2.7) <= 0.01
    assert gt.main(["--catpart", str(catpart_path), "--reference", str(stl_path), "--ref-scale", "auto"]) == 2


def test_main_writes_the_normalization_columns(tmp_path: Path) -> None:
    """--ref-scale auto flows through main() into the CSV: the factor,
    the area unit and the raw ratio travel with every metrics row."""
    import csv as _csv

    catpart_path, mesh = _exported_mesh(tmp_path)
    stl_path = tmp_path / "tenth-scale.stl"
    _write_binary_stl(stl_path, _scaled_copy(mesh, 0.1))
    out_csv = tmp_path / "batch.csv"
    assert gt.main(["--catpart", str(catpart_path), "--reference", str(stl_path),
                    "--ref-scale", "auto", "--csv", str(out_csv)]) == 0
    with out_csv.open(newline="", encoding="utf-8") as fh:
        row = next(_csv.DictReader(fh))
    assert row["outcome"] == gt.OUTCOME_METRICS
    assert row["ref_scale_mode"] == "auto"
    assert float(row["ref_scale_factor"]) == 10.0
    assert float(row["area_unit_factor"]) == 100.0
    assert abs(float(row["area_ratio_raw"]) - 100.0) <= 1.0


def test_resolve_ref_scale_snaps_a_dodge_style_ratio() -> None:
    """The measured Dodge case at unit level: a x10.157 diagonal ratio
    (x-exact f32, y/z shifted by the re-tessellation) snaps to 10 with
    the deviation reported, never hidden."""
    factor, info = gt.resolve_ref_scale(5620.8, 553.249, "auto")
    assert factor == 10.0
    assert info["area_unit_factor"] == 100.0
    assert info["resolution"] == "auto"
    assert info["raw_diagonal_ratio"] == 5620.8 / 553.249
    assert abs(info["candidate_deviation"] - (5620.8 / 553.249 - 10.0) / 10.0) <= 1e-12


def test_resolve_ref_scale_forced_bypasses_the_window_but_reports() -> None:
    factor, info = gt.resolve_ref_scale(2.7, 1.0, "10")
    assert factor == 10.0 and info["resolution"] == "forced"
    assert info["raw_diagonal_ratio"] == 2.7, "the override must carry the measured ratio"
    factor, info = gt.resolve_ref_scale(2.7, 1.0, "1")
    assert factor == 1.0 and info["area_unit_factor"] == 1.0


def test_resolve_ref_scale_refuses_out_of_window_ratios() -> None:
    for catpart_diag, reference_diag in ((9.4, 1.0), (1.06, 1.0), (0.5, 1.0), (2.7, 1.0)):
        with pytest.raises(gt.NormalizationUncertain):
            gt.resolve_ref_scale(catpart_diag, reference_diag, "auto")
    with pytest.raises(gt.NormalizationUncertain, match="positive bbox diagonals"):
        gt.resolve_ref_scale(0.0, 1.0, "auto")  # a zero diagonal cannot be normalized


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
