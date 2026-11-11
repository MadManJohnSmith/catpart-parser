"""Walk-law composite export (G6 stage 3d, #34).

The stage-3b decode laws integrated into the shipped seam: the list
node's point region encoded under the 2-bit table law (U1) walks
byte-exact and exports under the M2b identity mapping — on the small
form and (formerly rejected at the composite.py big-form gate) on the
big form alike.  The fixtures are the stage-2c box re-encoded: 14
elements, 2 skip slots (curve entries), one 0x4a strip loop referencing
a skip slot (the U4 curve-entry case: the loop contributes no triangles
and is warned), the rest of the box exporting.  Determinism: same
inputs, byte-identical fixtures.  The suite stays corpus-free.
"""

from __future__ import annotations

import json

import pytest

from catpart.schema import load_schema
from catpart.schema.validate import validate
from fixtures_gen import (
    COMPOSITE_POINTS,
    COMPOSITE_WALK_VALUES,
    build_fixture,
)
from test_composite_export import parse_ply, run_export


def test_walk_fixture_exports_via_identity(tmp_path, capsys):
    """The walk-law fixture exports through the identity path: the
    element space is the region's element sequence, the curve entries
    ride it as skip slots, and the skip-ref strip loop is warned, not
    guessed."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-walk-law"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    validate(summary, load_schema("export-summary-v1"))
    assert summary["vertex_count"] == len(COMPOSITE_POINTS)
    assert summary["triangle_count"] == 10  # 12 minus the skip-ref strip
    info = summary["composite"]
    assert info["stage"] == "walk"
    assert info["mapping"] == "identity"
    assert info["element_decl"] == len(COMPOSITE_WALK_VALUES)
    assert info["node_points"] == len(COMPOSITE_POINTS)
    assert info["curve_entries"] == 2
    assert info["write_count"] == 17
    assert info["table_bytes"] == 4
    assert info["skipref_loops"] == 1
    assert info["coplanar_loops"] == 2
    # no sigma search ran on the walk-exact region
    assert "sigma_solutions" not in info
    classes = [w["class"] for w in summary["warnings"]]
    details = " | ".join(w["detail"] for w in summary["warnings"])
    assert "open-shell" in classes
    assert "curve entries (skip slots)" in details
    assert "U4" in details
    # the PLY carries the written points in region order
    vertices, faces = parse_ply(ply_path)
    assert len(vertices) == len(COMPOSITE_POINTS)
    assert len(faces) == 10
    for got, want in zip(vertices, COMPOSITE_POINTS):
        assert got == pytest.approx(want, abs=1e-6)


def test_walk_big_fixture_exports_where_2c_rejected(tmp_path, capsys):
    """A big-form list node (payload > 4096 B) exports through the walk:
    the stage-2c rejection at the composite seam is replaced by the walk
    gate (stage 3d)."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-walk-big"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    info = summary["composite"]
    assert info["node_bytes"] > 4096
    assert info["stage"] == "walk"
    assert info["mapping"] == "identity"
    assert summary["triangle_count"] == 10
    assert ply_path.exists()


def test_walk_count_mismatch_big_stays_labeled(tmp_path, capsys):
    """The declared write count disagrees with the table's shapes: the
    big-form store keeps its undecoded-variant classification with the
    walk-failure cause named (never a silent pass or a forced guess)."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-walk-count-mismatch"
    )
    assert code == 1
    error = json.loads(captured.err)
    assert error["error_class"] == "undecoded-variant"
    assert "big-form" in error["detail"]
    assert "write count" in error["detail"]
    assert not ply_path.exists()


def test_stage2c_fixture_takes_the_dp_fallback(tmp_path, capsys):
    """The stage-2c encoding (table of ceil(elem/4)+1 bytes, no write
    count) does not walk: the small-form store falls back to the
    stage-2c DP path and exports exactly as shipped (the no-regression
    condition), sigma CSP included."""
    code, captured, _ply = run_export(tmp_path, capsys, "geometry-composite-law")
    assert code == 0, captured.err
    info = json.loads(captured.out)["composite"]
    assert info["stage"] in ("lex", "reset")
    assert info["sigma_solutions"] == 1
    assert "mapping" not in info


@pytest.mark.parametrize(
    "variant",
    [
        "geometry-composite-walk-law",
        "geometry-composite-walk-big",
        "geometry-composite-walk-count-mismatch",
    ],
)
def test_walk_fixtures_deterministic(variant):
    a = build_fixture("part", seed=3, variant=variant)
    b = build_fixture("part", seed=3, variant=variant)
    assert a == b
