"""The deterministic triage router (Phase 3 P3.5, design B).

Pins every ROUTE_TABLE row against a record shaped like its real corpus
source (open-rate-files.csv for report-kind rows, m1_files.csv for
l2/failed-check rows), plus the residue contract: each documented reason
must actually fire, and the not-a-catpart kind check must beat the
missing-geometry-store class those rows carry (probe_open_rate.py records
the open outcome, so junk opens BLANK with an extraction-failure class).

Pure unit tests over normalized records — no corpus files, no network.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "triage"))

from router import (
    BUCKETS,
    RESIDUE_REASONS,
    ROUTE_TABLE,
    make_record,
    resolve_class,
    residue_reason,
    route,
)


def or_row(**kw) -> dict:
    """An open-rate part row; defaults route clean to already_healthy."""
    rec = make_record(
        path="p.CATPart", source="open-rate", error_class="pass",
        open_kind="MESH", triangle_count=100, point_count=0,
    )
    rec.update(kw)
    return rec


def m1_row(**kw) -> dict:
    """A submarine m1 row; defaults route clean to already_healthy."""
    rec = make_record(
        path="q.CATPart", source="submarine-m1", l2_status="pass",
        open_kind="MESH", triangle_count=50,
    )
    rec.update(kw)
    return rec


def test_table_covers_every_gt_class() -> None:
    routed = {
        "not-manifold": route(m1_row(l2_status="fail", failed_check="not-manifold")),
        "undecoded-variant": route(or_row(error_class="undecoded-variant")),
        "missing-geometry-store": route(or_row(error_class="missing-geometry-store")),
        "empty-mesh": route(or_row(error_class="empty-mesh", open_kind="DISPLAY",
                                   triangle_count=0, point_count=16,
                                   display_points=16)),
        "not-a-catpart": route(or_row(report_kind="not-a-catpart",
                                      error_class="missing-geometry-store")),
        "pass": route(or_row()),
    }
    assert set(routed) == set(ROUTE_TABLE)
    assert all(r is not None for r in routed.values())


def test_not_manifold_routes_seam_bucket() -> None:
    r = route(m1_row(l2_status="fail", error_class="", failed_check="not-manifold",
                     warnings=["open-shell", "primary-loop-manifold-declined"]))
    assert (r.bucket, r.escalate, r.risk, r.reason) == (
        "known_seam_not_manifold", True, 2, "table:not-manifold")


def test_undecoded_variant_and_missing_store_route_needs_new() -> None:
    r = route(or_row(error_class="undecoded-variant"))
    assert (r.bucket, r.escalate, r.risk, r.reason) == (
        "needs_new_re_subagent", True, 4, "table:undecoded-variant")
    r = route(or_row(error_class="missing-geometry-store"))
    assert (r.bucket, r.escalate, r.risk, r.reason) == (
        "needs_new_re_subagent", True, 4, "table:missing-geometry-store")
    r = route(m1_row(l2_status="fail", error_class="undecoded-variant"))
    assert r.bucket == "needs_new_re_subagent"


def test_empty_mesh_routes_feature_only_with_display_evidence() -> None:
    r = route(or_row(error_class="empty-mesh", open_kind="DISPLAY",
                     triangle_count=0, point_count=16, display_points=16))
    assert (r.bucket, r.escalate, r.risk, r.reason) == (
        "known_feature_only", False, 1, "table:empty-mesh")
    r = route(m1_row(l2_status="fail", error_class="", failed_check="empty-mesh",
                     open_kind="DISPLAY", triangle_count=0, display_points=16))
    assert r.bucket == "known_feature_only"


def test_not_a_catpart_kind_beats_missing_geometry_store_class() -> None:
    r = route(or_row(report_kind="not-a-catpart",
                     error_class="missing-geometry-store", open_kind="BLANK"))
    assert (r.bucket, r.escalate, r.risk, r.reason) == (
        "known_not_a_catpart", True, 3, "table:not-a-catpart")


def test_clean_pass_routes_healthy_on_both_sources() -> None:
    assert route(or_row()).reason == "table:pass"
    assert route(or_row()).bucket == "already_healthy"
    assert route(m1_row()).bucket == "already_healthy"
    r = route(m1_row(warnings=["duplicate-triangles-deduped"]))
    assert r is None and residue_reason(m1_row(
        warnings=["duplicate-triangles-deduped"])) == "pass_with_warnings"


def test_kind_unknown_display_row_routes_feature_only() -> None:
    r = route(or_row(report_kind="unknown", error_class="empty-mesh",
                     open_kind="DISPLAY", triangle_count=0, point_count=254,
                     display_points=254))
    assert (r.bucket, r.reason) == ("known_feature_only", "table:empty-mesh")


def test_residue_class_outside_table() -> None:
    for rec in (or_row(error_class="degenerate-triangles"),
                m1_row(l2_status="fail", error_class="", failed_check="degenerate-triangles"),
                m1_row(l2_status="fail", error_class="no-evaluable-surface"),
                m1_row(l2_status="fail", error_class="", failed_check="")):
        assert route(rec) is None
        assert residue_reason(rec) == "class_outside_table"


def test_residue_pass_with_warnings_even_benign_looking() -> None:
    rec = m1_row(warnings=["open-shell"])
    assert route(rec) is None
    assert residue_reason(rec) == "pass_with_warnings"


def test_residue_pass_without_rendered_mesh_evidence() -> None:
    no_mesh = or_row(open_kind="BLANK")
    assert route(no_mesh) is None
    assert residue_reason(no_mesh) == "pass_without_mesh"
    zero_tri = or_row(open_kind="MESH", triangle_count=0)
    assert residue_reason(zero_tri) == "pass_without_mesh"
    no_l2 = m1_row(l2_status="")
    assert route(no_l2) is None and residue_reason(no_l2) == "class_outside_table"


def test_residue_feature_only_without_display_evidence() -> None:
    rec = or_row(error_class="empty-mesh", open_kind="DISPLAY",
                 triangle_count=0, point_count=0)
    assert route(rec) is None
    assert residue_reason(rec) == "feature_only_without_display_evidence"


def test_residue_reason_is_empty_for_table_hits() -> None:
    for rec in (or_row(), or_row(report_kind="not-a-catpart",
                                 error_class="missing-geometry-store"),
                or_row(error_class="empty-mesh", open_kind="DISPLAY",
                       point_count=3, display_points=3)):
        assert residue_reason(rec) == ""


def test_resolve_class_precedence_matches_s8() -> None:
    # error_class wins over failed_check (the no-evaluable-surface row);
    # a failed l2 with neither named reason is unknown, not pass.
    assert resolve_class(m1_row(error_class="undecoded-variant")) == "undecoded-variant"
    assert resolve_class(m1_row(error_class="no-evaluable-surface",
                                failed_check="not-manifold")) == "no-evaluable-surface"
    assert resolve_class(m1_row(l2_status="fail")) == "unknown"
    assert resolve_class(m1_row()) == "pass"


def test_buckets_constant_matches_s8() -> None:
    assert BUCKETS == ("known_seam_not_manifold", "known_feature_only",
                       "known_not_a_catpart", "needs_new_re_subagent",
                       "already_healthy")
    assert set(RESIDUE_REASONS) == {
        "class_outside_table", "pass_with_warnings", "pass_without_mesh",
        "pass_without_l2", "feature_only_without_display_evidence"}
