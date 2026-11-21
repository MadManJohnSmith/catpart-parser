"""The deterministic triage router (Phase 3 P3.5, design B).

Pins every ROUTE_TABLE row against a record shaped like its real corpus
source (open-rate-files.csv for report-kind rows, m1_files.csv for
l2/failed-check rows), plus the residue contract: each documented reason
must actually fire, and the not-a-catpart kind check must beat the
missing-geometry-store class those rows carry (probe_open_rate.py records
the open outcome, so junk opens BLANK with an extraction-failure class).

Also pins the arbiter's critical contracts without touching the network:
key resolution (env var -> external file -> None, never from the repo),
typed-answer normalization with the clarified criteria, the stratified
residue sampler, and the run_triage no-key fallback (residue ->
needs_review, exit 0).

Pure unit tests over normalized records — no corpus files, no network.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "triage"))

import jev_arbiter
import run_triage
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


# ---- arbiter contracts (no network) ----

def test_resolve_key_env_then_file_then_none(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    assert jev_arbiter.resolve_key() is None
    assert jev_arbiter.resolve_key(str(tmp_path / "absent.txt")) is None
    key_file = tmp_path / "k.txt"
    key_file.write_text("sk-file-key\n")
    assert jev_arbiter.resolve_key(str(key_file)) == "sk-file-key"
    monkeypatch.setenv("OPENCODE_API_KEY", "sk-env-key")
    assert jev_arbiter.resolve_key(str(key_file)) == "sk-env-key"


def test_normalize_answers_maps_typed_shape() -> None:
    answers = {
        "route_bucket": {"choice": "known_feature_only",
                         "probabilities": {"known_feature_only": 0.7}},
        "escalate_to_system2": {"noul": 0.12},
        "visual_fidelity_risk": {"score": 0},
    }
    d = jev_arbiter.normalize_answers(answers)
    assert d == {"bucket": "known_feature_only", "escalate": False,
                 "risk": 1, "confidence": 0.7}
    # level index 0-4 -> risk 1-5, clamped
    answers["visual_fidelity_risk"]["score"] = 4
    assert jev_arbiter.normalize_answers(answers)["risk"] == 5
    answers["escalate_to_system2"]["noul"] = 0.5
    assert jev_arbiter.normalize_answers(answers)["escalate"] is True
    answers["route_bucket"]["choice"] = "needs_new"
    with pytest.raises(ValueError):
        jev_arbiter.normalize_answers(answers)


def test_build_state_sends_only_feature_metadata() -> None:
    rec = m1_row(l2_status="pass", warnings=["open-shell"], size_bytes=123)
    state = jev_arbiter.build_state(rec)
    assert '"warnings": ["open-shell"]' in state
    assert '"size_bytes": 123' in state
    # none of the record's extra keys leak; only the documented fields
    for field in ("point_count", "display_points", "path"):
        assert f'"{field}"' in state
    assert "report_kind" not in state and '"source"' not in state


def test_clarified_criteria_present() -> None:
    criteria = jev_arbiter.QUESTIONS["route_bucket"]["criteria"]
    assert "NOT a decoding failure" in criteria["known_feature_only"]
    assert "real extraction or decoding failure" in criteria["needs_new_re_subagent"]
    legend = jev_arbiter.QUESTIONS["visual_fidelity_risk"]["criteria"]
    assert len(legend) == 5 and "junk container" in legend[2]


# ---- CLI sampling + fallback (no network) ----

def test_stratified_sample_proportional_and_seeded() -> None:
    recs = [m1_row() for _ in range(60)] + [or_row() for _ in range(40)]
    for r in recs[:60]:
        r["path"] = "a.CATPart"
    for r in recs[60:]:
        r["path"] = "b.CATPart"
    pick = run_triage.stratified_sample(
        recs, lambda r: (r["path"],), 20, seed=42)
    assert len(pick) == 20
    assert sum(1 for r in pick if r["path"] == "a.CATPart") == 12
    assert run_triage.stratified_sample(recs[:5], lambda r: (r["path"],), 20, 42) \
        == recs[:5]


def _write_open_rate_csv(path: Path) -> None:
    path.write_text(
        "sha16,path,split,report kind,report class,open kind,triangles,points,segments\n"
        "a,p1.CATPart,dev,part,pass,MESH,100,0,0\n"
        "b,p2.CATPart,dev,part,degenerate-triangles,MESH,300,0,0\n",
        encoding="utf-8")


def test_run_triage_without_key_falls_back_needs_review_exit0(
    monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    inv, out = tmp_path / "inv.csv", tmp_path / "out.csv"
    _write_open_rate_csv(inv)
    code = run_triage.main(["--input", str(inv), "--output", str(out),
                            "--no-arbiter"])
    assert code == 0
    with out.open() as f:
        rows = {r["path"]: r for r in csv.DictReader(f)}
    assert rows["p1.CATPart"]["route_bucket"] == "already_healthy"
    assert rows["p1.CATPart"]["decision_source"] == "deterministic"
    assert rows["p2.CATPart"]["route_bucket"] == "needs_review"
    assert rows["p2.CATPart"]["decision_source"] == "no_key"
    assert rows["p2.CATPart"]["residue_reason"] == "class_outside_table"


def test_record_adapters_shape_both_csv_dialects() -> None:
    or_rec = run_triage.record_from_open_rate({
        "path": "x.CATPart", "report kind": "part", "report class": "empty-mesh",
        "open kind": "DISPLAY", "triangles": "0", "points": "16", "segments": "2"})
    assert or_rec["error_class"] == "empty-mesh"
    assert or_rec["display_points"] == 16 and or_rec["display_segments"] == 2
    assert or_rec["point_count"] == 16  # same column on DISPLAY rows
    m1_rec = run_triage.record_from_m1({
        "path": "y.CATPart", "size_bytes": "48197", "l2_status": "fail",
        "error_class": "", "failed_check": "not-manifold", "open_class": "MESH",
        "vertex_count": "62", "triangle_count": "62", "display_points": "0",
        "display_segments": "0",
        "warnings": "open-shell;primary-loop-manifold-kept", "seconds": "0.006"})
    assert m1_rec["failed_check"] == "not-manifold"
    assert m1_rec["warnings"] == ["open-shell", "primary-loop-manifold-kept"]
    assert m1_rec["size_bytes"] == 48197 and m1_rec["point_count"] == 62
    assert route(m1_rec).bucket == "known_seam_not_manifold"
