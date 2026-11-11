"""Seam 3: ``catpart-export`` — the Phase 4 vertical build slice (G4, #32).

External behavior only, through the CLI entry point
(:func:`catpart.cli.main_export`, the seam the console script wraps) on
synthetic fixtures built by :mod:`fixtures_gen`: the schema-versioned
summary contract, the PLY parse-back (header, counts, index bounds,
finite coordinates), the golden geometry fixture's mesh invariants
(12 triangles, closed oriented manifold, CCW-outward winding) and the
classified error classes of every corrupted geometry variant.
"""

from __future__ import annotations

import json
import math
import struct
from pathlib import Path

import pytest

from catpart.schema import load_schema
from catpart.schema.validate import ValidationError, validate
from fixtures_gen import build_fixture

SUMMARY_SCHEMA = "export-summary-v1"


def run_export(tmp_path: Path, capsys, data: bytes, *, output: Path | None = None):
    """Write ``data`` as a .CATPart, run the export seam, return
    ``(code, captured, input_path, ply_path)``."""
    from catpart.cli import main_export

    path = tmp_path / "sample.CATPart"
    path.write_bytes(data)
    argv = [str(path)]
    if output is not None:
        argv += ["-o", str(output)]
        ply_path = output
    else:
        ply_path = path.with_suffix(".ply")
    code = main_export(argv)
    captured = capsys.readouterr()
    return code, captured, path, ply_path


def export_geometry(tmp_path: Path, capsys, variant: str = "geometry", seed: int = 7):
    """Export one geometry variant; assert success and schema validity."""
    code, captured, _, ply_path = run_export(
        tmp_path, capsys, build_fixture("part", seed=seed, variant=variant)
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    validate(summary, load_schema(SUMMARY_SCHEMA))
    return summary, ply_path


def parse_ply(path: Path):
    """Minimal stdlib parse-back of the binary little-endian PLY."""
    raw = path.read_bytes()
    marker = b"end_header\n"
    end = raw.index(marker) + len(marker)
    header = raw[:end].decode("ascii").splitlines()
    body = raw[end:]
    format_line = next(line for line in header if line.startswith("format "))
    n_vertices = int(
        next(line for line in header if line.startswith("element vertex")).split()[-1]
    )
    n_faces = int(
        next(line for line in header if line.startswith("element face")).split()[-1]
    )
    vertices = [
        struct.unpack("<fff", body[12 * i : 12 * i + 12]) for i in range(n_vertices)
    ]
    faces = []
    offset = 12 * n_vertices
    for _ in range(n_faces):
        count, a, b, c = struct.unpack("<Biii", body[offset : offset + 13])
        assert count == 3
        faces.append((a, b, c))
        offset += 13
    assert offset == len(body), "PLY body length mismatch"
    return format_line, vertices, faces, header


# --- golden geometry fixture: summary contract --------------------------

def test_golden_summary_contract(tmp_path: Path, capsys) -> None:
    # The 20x100x60 box: 8 pool vertices, 4 x 0x4a strips + 2 x 0x4c
    # polygons -> 12 triangles (F3/F4), a closed oriented manifold (F6)
    # with zero degenerate skips (F7) and no warnings.
    summary, _ = export_geometry(tmp_path, capsys)
    assert summary["schema_version"] == 1
    assert summary["vertex_count"] == 8
    assert summary["triangle_count"] == 12
    assert summary["bounding_box"]["min"] == [0.0, 0.0, 0.0]
    assert summary["bounding_box"]["max"] == [20.0, 100.0, 60.0]
    assert summary["store_ordinal"] == 0
    assert summary["origin_kind"] == "v5header"
    assert summary["pool_group_count"] == 1
    assert summary["facet_candidate_count"] == 6
    assert summary["facet_record_count"] == 6
    assert summary["degenerate_triangle_count"] == 0
    assert summary["mesh"] == {
        "edge_count": 18,
        "manifold": True,
        "closed": True,
        "oriented": True,
        "boundary_edge_count": 0,
    }
    assert summary["warnings"] == []


def test_golden_ply_parse_back(tmp_path: Path, capsys) -> None:
    summary, ply_path = export_geometry(tmp_path, capsys)
    format_line, vertices, faces, header = parse_ply(ply_path)
    assert format_line == "format binary_little_endian 1.0"
    assert header[0] == "ply"
    assert header[-1] == "end_header"
    assert len(vertices) == summary["vertex_count"] == 8
    assert len(faces) == summary["triangle_count"] == 12
    for x, y, z in vertices:
        assert all(math.isfinite(v) for v in (x, y, z))
    for a, b, c in faces:
        for index in (a, b, c):
            assert 0 <= index < len(vertices)


def test_golden_closed_manifold_edge_histogram(tmp_path: Path, capsys) -> None:
    # 12 box edges (once per adjacent face) + 6 face diagonals (once per
    # direction within the face): every undirected edge exactly twice,
    # each directed edge once — the F6 closed-solid invariants.
    _, vertices, faces, _ = parse_ply(export_geometry(tmp_path, capsys)[1])
    assert len(vertices) == 8
    undirected: dict[tuple[int, int], int] = {}
    directed: dict[tuple[int, int], int] = {}
    for a, b, c in faces:
        for e in ((a, b), (b, c), (c, a)):
            key = tuple(sorted(e))
            undirected[key] = undirected.get(key, 0) + 1
            directed[e] = directed.get(e, 0) + 1
    assert len(undirected) == 18
    assert set(undirected.values()) == {2}
    assert all(directed[(a, b)] == directed[(b, a)] for (a, b) in directed)


def test_golden_winding_ccw_outward(tmp_path: Path, capsys) -> None:
    # Winding law F5 preserved: the box is convex, so every triangle's
    # normal must point away from the solid's centroid (CCW seen from
    # outside = the OBJ/PLY convention).
    _, vertices, faces, _ = parse_ply(export_geometry(tmp_path, capsys)[1])
    centroid = [sum(v[i] for v in vertices) / len(vertices) for i in range(3)]

    def sub(a, b):
        return (a[0] - b[0], a[1] - b[1], a[2] - b[2])

    def cross(a, b):
        return (
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        )

    for a, b, c in faces:
        normal = cross(sub(vertices[b], vertices[a]), sub(vertices[c], vertices[a]))
        face_center = [
            (vertices[a][i] + vertices[b][i] + vertices[c][i]) / 3 for i in range(3)
        ]
        outward = sub(face_center, centroid)
        assert sum(normal[i] * outward[i] for i in range(3)) > 0.0


def test_export_is_deterministic(tmp_path: Path, capsys) -> None:
    # Same (kind, seed, variant) -> byte-identical PLY and summary.
    summary_a, ply_a = export_geometry(tmp_path, capsys, seed=11)
    summary_b, ply_b = export_geometry(tmp_path, capsys, seed=11)
    assert ply_a.read_bytes() == ply_b.read_bytes()
    assert json.dumps(summary_a, sort_keys=True) == json.dumps(summary_b, sort_keys=True)


def test_default_output_path_next_to_input(tmp_path: Path, capsys) -> None:
    code, captured, path, ply_path = run_export(
        tmp_path, capsys, build_fixture("part", seed=3, variant="geometry")
    )
    assert code == 0, captured.err
    assert ply_path == path.with_suffix(".ply")
    assert ply_path.is_file()


def test_output_flag_overrides_path(tmp_path: Path, capsys) -> None:
    out = tmp_path / "elsewhere.ply"
    code, captured, path, ply_path = run_export(
        tmp_path,
        capsys,
        build_fixture("part", seed=3, variant="geometry"),
        output=out,
    )
    assert code == 0, captured.err
    assert ply_path == out and out.is_file()
    assert not path.with_suffix(".ply").exists()


# --- open-shell valid variant: the warnings machinery -------------------

def test_open_shell_variant_exports_with_warnings(tmp_path: Path, capsys) -> None:
    # 5 of 6 faces (G3 F6's sheet-like open shells are legitimate clean
    # stores) plus one well-formed 0x41 record with a degenerate loop:
    # 10 triangles, boundary edges, and three warning classes — errors
    # stay reserved for genuinely unexportable stores.
    summary, _ = export_geometry(tmp_path, capsys, variant="geometry-open-shell")
    assert summary["vertex_count"] == 8
    assert summary["triangle_count"] == 10
    assert summary["degenerate_triangle_count"] == 1
    assert summary["mesh"]["manifold"] is True
    assert summary["mesh"]["closed"] is False
    assert summary["mesh"]["boundary_edge_count"] == 4
    classes = [w["class"] for w in summary["warnings"]]
    assert classes == [
        "degenerate-triangles-skipped",
        "open-shell",
        "unresolved-facet-family",
    ]
    unresolved = summary["warnings"][2]
    assert "0x41=1" in unresolved["detail"]


# --- corrupted geometry variants: classified error classes --------------

@pytest.mark.parametrize(
    ("variant", "error_class"),
    [
        ("geometry-bad-nested-magic", "missing-geometry-store"),
        ("geometry-truncated-pool", "malformed-pool-group"),
        ("geometry-out-of-range-refs", "undecoded-variant"),
        ("geometry-nan-coords", "malformed-pool-vertex"),
        ("geometry-missing-facet-payload", "undecoded-variant"),
        ("geometry-composite-index-space", "undecoded-variant"),
    ],
)
def test_corrupted_variants_classified(
    tmp_path: Path, capsys, variant: str, error_class: str
) -> None:
    code, captured, _, ply_path = run_export(
        tmp_path, capsys, build_fixture("part", seed=5, variant=variant)
    )
    assert code == 1
    assert captured.out == ""
    error = json.loads(captured.err)
    assert error["error_class"] == error_class
    assert error["detail"]
    assert not ply_path.exists(), "no partial PLY on failure"


def test_undecoded_variants_name_the_open_question(tmp_path: Path, capsys) -> None:
    # The refs-beyond-pool class cites G3's open item 2 in the detail
    # (the ticket's "no guessing" rule).  The composite-space class
    # cites its own gap since the stage-2c integration (#34,
    # 2026-11-11): this fixture's edge group carries no list node, so
    # the failure names the missing N1 node — the law decodes composite
    # stores that DO carry one.
    for variant, marker in (
        ("geometry-composite-index-space", "token-bearing list node"),
        ("geometry-out-of-range-refs", "open question"),
    ):
        code, captured, _, _ = run_export(
            tmp_path, capsys, build_fixture("part", seed=5, variant=variant)
        )
        assert code == 1
        error = json.loads(captured.err)
        assert error["error_class"] == "undecoded-variant"
        assert marker in error["detail"]


def test_plain_fixture_has_no_geometry_store(tmp_path: Path, capsys) -> None:
    # The A2 fixtures carry no CATStdCont block: nothing to export.
    code, captured, _, ply_path = run_export(
        tmp_path, capsys, build_fixture("part", seed=1)
    )
    assert code == 1
    assert json.loads(captured.err)["error_class"] == "missing-geometry-store"
    assert not ply_path.exists()


def test_missing_file_is_unreadable(tmp_path: Path, capsys) -> None:
    from catpart.cli import main_export

    code = main_export([str(tmp_path / "absent.CATPart")])
    captured = capsys.readouterr()
    assert code == 1
    assert json.loads(captured.err)["error_class"] == "unreadable-file"


# --- schema is the authority --------------------------------------------

def test_summary_schema_rejects_mutations(tmp_path: Path, capsys) -> None:
    summary, _ = export_geometry(tmp_path, capsys)
    schema = load_schema(SUMMARY_SCHEMA)
    with pytest.raises(ValidationError):
        validate({**summary, "schema_version": 0}, schema)
    with pytest.raises(ValidationError):
        validate({**summary, "triangle_count": "12"}, schema)
    with pytest.raises(ValidationError):
        validate(
            {**summary, "warnings": [{"class": "bogus", "detail": "x"}]}, schema
        )


# --- fixture generator contract ------------------------------------------

def test_geometry_fixture_seed_determinism() -> None:
    assert build_fixture("part", seed=9, variant="geometry") == build_fixture(
        "part", seed=9, variant="geometry"
    )
    assert build_fixture("part", seed=9, variant="geometry") != build_fixture(
        "part", seed=10, variant="geometry"
    )


def test_geometry_variants_classify_clean_through_fitness(
    tmp_path: Path,
) -> None:
    # Cross-ticket seam: the geometry-bearing files are genuine CATIA V5
    # containers — the fitness classifier (A2/#14) reads them clean.
    from catpart.fitness.runner import _classify_file

    for variant in ("geometry", "geometry-open-shell"):
        path = tmp_path / f"{variant}.CATPart"
        path.write_bytes(build_fixture("part", seed=4, variant=variant))
        classification, error, output = _classify_file(path)
        assert classification == "clean", (variant, error)
        assert output is not None and output["kind"] == "part"
