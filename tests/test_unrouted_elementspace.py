"""Stage 13: the second-chance element-space route (G6 #34, 2026-11-13).

Corpus-free external behavior on synthetic fixtures: the stage-13
finding is that the element space beyond the pool IS the list node's
point region — the composite structure without its ``01 02``/``ff ..``
markers — so the clean path's no-pool and refs-beyond failure points
re-route token-node-carrying stores through the UNCHANGED composite
decode (``allow_unrouted_elements`` skips only the marker-routing
check).  Positives (the refs-beyond and pool-less fixtures export
12 points / 12 triangles through the landed gates, no store_recovery —
the shipped stdcont law located them), the precedence pins (marker
stores route first, unchanged; a refs-beyond store with NO token node
keeps the exact original error), and the fail-closed negatives (a
walk-failing node and a node-less body re-raise the ORIGINAL clean-path
error, detail included).

Census counterparts: docs/evidence/2026-11-13-stage13-elementspace.md
sections 2-4 (32/38 refs-beyond exports / 28 passes + 3/131 no-pool
passes measured through this route's corpus A/B; the 134 non-covering
stores re-raise unchanged).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from catpart.fitness.runner import _score_export
from catpart.geometry.errors import ExportError
from catpart.geometry import export as export_mod
from catpart.schema import load_schema
from catpart.schema.validate import validate
from fixtures_gen import build_fixture

SUMMARY_SCHEMA = "export-summary-v1"


def run_export(tmp_path: Path, capsys, variant: str, seed: int = 7):
    """Export one variant through the CLI seam; return (code, captured)."""
    from catpart.cli import main_export

    path = tmp_path / f"{variant}.CATPart"
    path.write_bytes(build_fixture("part", seed=seed, variant=variant))
    code = main_export([str(path)])
    return code, capsys.readouterr()


# --- positives: the element space routes to the composite decode -------


def test_refs_beyond_routes_to_composite(tmp_path: Path, capsys) -> None:
    # The stage-13 census's refs-beyond shape: a pool (8 re-listed
    # corners) + a token-bearing list node (12-point region) + facet
    # records referencing elements 0..11 — max ref 11 >= pool 8, so
    # the clean path raises refs-beyond; the second chance decodes the
    # element space and exports the full box.  No store_recovery: the
    # shipped stdcont law located the store.
    code, captured = run_export(
        tmp_path, capsys, "geometry-unrouted-elementspace-refs-beyond"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    validate(summary, load_schema(SUMMARY_SCHEMA))
    assert summary["vertex_count"] == 12
    assert summary["triangle_count"] == 12
    assert summary["mesh"]["manifold"] is True
    assert summary["mesh"]["closed"] is True
    assert "store_recovery" not in summary
    assert summary["composite"]["stage"] == "identity-table-walk"
    assert summary["composite"]["element_decl"] == 12
    assert _score_export(summary)["status"] == "pass"


def test_no_pool_routes_to_composite(tmp_path: Path, capsys) -> None:
    # The no-pool facet-carrier shape (66049cf3/bf350820/fac22ea3): no
    # pool wrapper at all — the clean path raises the G2 P8 error —
    # but the list node's point region + in-bounds facets decode under
    # the unchanged composite law (the absorption gate is vacuous with
    # an empty pool).
    code, captured = run_export(
        tmp_path, capsys, "geometry-unrouted-elementspace-no-pool"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    validate(summary, load_schema(SUMMARY_SCHEMA))
    assert summary["vertex_count"] == 12
    assert summary["triangle_count"] == 12
    assert summary["pool_group_count"] == 0
    assert summary["composite"]["stage"] == "identity-table-walk"
    assert _score_export(summary)["status"] == "pass"


# --- precedence and fail-closed negatives ------------------------------


def test_marker_store_still_routes_first(tmp_path: Path, capsys) -> None:
    # The routing predicate's first arm is unchanged: a store WITH the
    # `01 02` edge group takes the composite path exactly as before
    # (the same box, markers present — the pre-stage-13 behavior).
    code, captured = run_export(tmp_path, capsys, "geometry-composite-law")
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    assert summary["vertex_count"] == 12
    assert summary["triangle_count"] == 12


def test_refs_beyond_without_node_keeps_original_error(
    tmp_path: Path, capsys
) -> None:
    # The clean store's refs-beyond shape with NO token node (the
    # corpus's geometry-out-of-range-refs family): the second chance
    # declines and the ORIGINAL error re-raises — class AND detail
    # byte-identical to the pre-stage-13 behavior (the row-identity
    # contract).
    data = build_fixture("part", seed=7, variant="geometry-out-of-range-refs")
    with pytest.raises(ExportError) as excinfo:
        export_mod._export_data(data)
    assert excinfo.value.error_class == "undecoded-variant"
    assert excinfo.value.detail.startswith("facet references beyond the pool")
    assert "element space" not in excinfo.value.detail


def test_no_node_keeps_no_pool_error(tmp_path: Path, capsys) -> None:
    # The second chance requires a token-bearing list node: a facet-
    # only body (no pool, no node) keeps the exact G2 P8 error.
    code, captured = run_export(
        tmp_path, capsys, "geometry-unrouted-elementspace-no-node"
    )
    assert code == 1
    error = json.loads(captured.err)
    assert error["error_class"] == "undecoded-variant"
    assert error["detail"].startswith("no 01 06 vertex pool decoded")


def test_walk_failing_node_keeps_no_pool_error(tmp_path: Path, capsys) -> None:
    # A token node whose walk fails (the declared write count exceeds
    # the region): the composite gates raise and the ORIGINAL no-pool
    # error re-raises — the composite gap is NOT substituted (the
    # 134-row row-identity contract; the gap stays probe-measurable).
    code, captured = run_export(
        tmp_path, capsys, "geometry-unrouted-elementspace-walk-mismatch"
    )
    assert code == 1
    error = json.loads(captured.err)
    assert error["error_class"] == "undecoded-variant"
    assert error["detail"].startswith("no 01 06 vertex pool decoded")
    assert "table walk" not in error["detail"]
