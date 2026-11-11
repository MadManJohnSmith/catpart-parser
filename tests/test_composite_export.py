"""Composite-law export (G6 stage 2c, #34).

The synthetic composite fixture (small form, curve entries 0) through
the CLI export seam: the merged element space decodes, the PLY carries
the merged coordinates, the mesh invariants hold, the ``composite``
info block rides the summary additively, and the store where the law
does NOT hold keeps its ``undecoded-variant`` classification with the
specific gap named (fail-closed).  Determinism: same inputs,
byte-identical fixtures.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from catpart.schema import load_schema
from catpart.schema.validate import validate
from fixtures_gen import (
    COMPOSITE_FACES,
    COMPOSITE_POINTS,
    build_fixture,
)


def run_export(tmp_path: Path, capsys, variant: str):
    """Export one composite variant; return (code, captured, ply_path)."""
    from catpart.cli import main_export

    path = tmp_path / "sample.CATPart"
    path.write_bytes(build_fixture("part", seed=7, variant=variant))
    code = main_export([str(path)])
    captured = capsys.readouterr()
    return code, captured, path.with_suffix(".ply")


def parse_ply(path: Path):
    raw = path.read_bytes()
    marker = b"end_header\n"
    head, body = raw.split(marker, 1)
    text = head.decode("ascii")
    n_vertices = int(
        next(
            ln
            for ln in text.splitlines()
            if "element vertex" in ln
        ).split()[-1]
    )
    n_faces = int(
        next(
            ln for ln in text.splitlines() if "element face" in ln
        ).split()[-1]
    )
    vertices = []
    off = 0
    for _ in range(n_vertices):
        vertices.append(struct.unpack_from("<fff", body, off))
        off += 12
    faces = []
    for _ in range(n_faces):
        cnt = body[off]
        idx = struct.unpack_from(f"<{cnt}i", body, off + 1)
        faces.append(tuple(idx))
        off += 1 + 4 * cnt
    return vertices, faces


@pytest.mark.parametrize("seed", [7, 0])
def test_composite_fixture_exports_closed_manifold(tmp_path, capsys, seed):
    code, captured, ply_path = run_export(tmp_path, capsys, "geometry-composite-law")
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    validate(summary, load_schema("export-summary-v1"))
    assert summary["vertex_count"] == len(COMPOSITE_POINTS)
    assert summary["triangle_count"] == 12
    assert summary["degenerate_triangle_count"] == 0
    assert summary["mesh"]["manifold"] is True
    assert summary["mesh"]["closed"] is True
    assert summary["mesh"]["oriented"] is True
    # the composite info block rides the summary additively; the merged
    # space is the pool re-listed plus the extras, curve entries 0, and
    # the shift profile is forced (unique solution)
    info = summary["composite"]
    assert info["element_decl"] == len(COMPOSITE_POINTS)
    assert info["node_points"] == len(COMPOSITE_POINTS)
    assert info["curve_entries"] == 0
    assert info["sigma_solutions"] == 1
    # the PLY carries the merged coordinates in decoded order
    vertices, faces = parse_ply(ply_path)
    assert len(vertices) == len(COMPOSITE_POINTS)
    assert len(faces) == 12
    for got, want in zip(vertices, COMPOSITE_POINTS):
        assert got == pytest.approx(want, abs=1e-6)
    for tri in faces:
        assert all(0 <= i < len(COMPOSITE_POINTS) for i in tri)


def test_composite_vertex_order_is_the_decoded_node_list(tmp_path, capsys):
    """The PLY vertex order is the decoded point list: the pool's lex-min
    opens the region under the implicit-x0 first write ([y][z] when the
    first point's x is 0) — the fixture's list opens (0, 10, 30), not the
    pool's (0, 10, 0) walk head."""
    code, captured, ply_path = run_export(tmp_path, capsys, "geometry-composite-law")
    assert code == 0, captured.err
    vertices, _ = parse_ply(ply_path)
    assert vertices[0] == pytest.approx((0.0, 10.0, 0.0), abs=1e-6)
    assert vertices[1] == pytest.approx((0.0, 10.0, 30.0), abs=1e-6)


def test_composite_nonplanar_loop_stays_undecoded(tmp_path, capsys):
    """The law does not hold (a normal-carrying loop spans two planes):
    classified undecoded-variant with the sigma-CSP gap named, no PLY."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-nonplanar"
    )
    assert code == 1
    error = json.loads(captured.err)
    assert error["error_class"] == "undecoded-variant"
    assert "shift profile" in error["detail"]
    assert not ply_path.exists()


@pytest.mark.parametrize("variant", ["geometry-composite-law", "geometry-composite-law-nonplanar"])
def test_composite_fixtures_deterministic(variant):
    a = build_fixture("part", seed=3, variant=variant)
    b = build_fixture("part", seed=3, variant=variant)
    assert a == b


def test_composite_face_records_exercise_both_families():
    """The fixture's record set mirrors the clean box's shape: four 0x4a
    strips and two 0x4c polygons, so the composite path exercises both
    exported primitive families."""
    markers = sorted(mk for mk, _n, _r in COMPOSITE_FACES)
    assert markers == [0x4A, 0x4A, 0x4A, 0x4A, 0x4C, 0x4C]
