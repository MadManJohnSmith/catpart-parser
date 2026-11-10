"""L2 fitness integration (ticket #33): scalars, no-regret policy, seam.

Covers the L2 extension of the fitness system at three layers:

- history level: the L2 score type (:class:`catpart.fitness.PartScore`,
  pass/total counts over the kind=part population) and the extended
  no-regret rule — L1 (the headline) must strictly rise on Dev and not
  fall on Held-out; L2 is protective and must not fall on either split,
  so an L2-only improvement with a flat L1 is acceptable (reason
  recorded);
- runner level: the L2 measurement per split over the manifest's
  kind=part rows through the G4 export seam
  (``catpart.geometry.build_export``), mocked exactly the way
  ``test_fitness_runner.py`` mocks the inspect seam — ``monkeypatch`` on
  ``catpart.fitness.runner.build_export``;
- schema level: the committed fitness artifact schemas accept the L2
  shapes (scalars.L2 pass/total objects) and still accept the pre-G5
  null.

The suite stays corpus-free: synthetic fixtures only, the real corpus is
never present.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from catpart.fitness import LevelScore, PartScore, SplitScore, evaluate_no_regret
from catpart.fitness.history import (
    REASON_ACCEPTED,
    REASON_ACCEPTED_L2,
    REASON_BASELINE_NO_L2,
    REASON_REJECTED_BOTH,
    REASON_REJECTED_DEV,
    REASON_REJECTED_HELD_OUT,
    REASON_REJECTED_L1_DEV,
    REASON_REJECTED_L2_DEV,
    level_scores_from_json,
)
from catpart.fitness import FitnessError
from catpart.geometry.errors import ExportError
from catpart.schema import load_schema
from catpart.schema.validate import ValidationError, validate

from test_fitness_runner import (
    VALID_ROW,
    clean_bytes,
    digest_of_manifest,
    manifest_row,
    run_fitness_cli,
    write_manifest,
)


def write_fixture_files(root: Path, files: dict[str, tuple[str, bytes]]) -> None:
    """Write ``{name: (split, bytes)}`` fixture files under ``root``."""
    parts = root / "corpus" / "fixture" / "parts"
    parts.mkdir(parents=True, exist_ok=True)
    for name, (_, data) in files.items():
        (parts / f"{name}.CATPart").write_bytes(data)


# --- the L2 score type: pass/total counts over the parts population ------


def test_part_score_json_shape_mirrors_l1_with_pass_counts() -> None:
    score = PartScore(passed=7, total=10)
    assert score.to_json() == {"rate": 0.7, "pass": 7, "total": 10}
    assert score.rate == 0.7
    assert PartScore.from_json({"rate": 0.7, "pass": 7, "total": 10}, "w") == score


def test_part_score_rejects_malformed_counts() -> None:
    with pytest.raises(FitnessError):
        PartScore.from_json({"rate": 0.7, "total": 10}, "w")  # no pass count
    with pytest.raises(FitnessError):
        PartScore.from_json({"pass": 11, "total": 10}, "w")  # pass beyond total
    with pytest.raises(FitnessError):
        PartScore.from_json({"pass": True, "total": 10}, "w")  # booleans are not counts
    with pytest.raises(ValueError):
        PartScore(0, 0)  # an empty population is not a measurable rate (mirrors SplitScore)


def test_l1_score_rejects_the_l2_shape_and_vice_versa() -> None:
    # The two score types are keyed differently on purpose: feeding an L2
    # object into the L1 reader (or the reverse) is a row-shape bug and
    # must fail closed, not read None as 0.
    with pytest.raises(FitnessError):
        SplitScore.from_json({"rate": 0.7, "pass": 7, "total": 10}, "w")
    with pytest.raises(FitnessError):
        PartScore.from_json({"rate": 0.7, "clean": 7, "total": 10}, "w")


def test_level_scores_round_trip_l2_through_the_row_shape() -> None:
    scores = {
        "L1": LevelScore(dev=SplitScore(2, 3), held_out=SplitScore(2, 2)),
        "L2": LevelScore(dev=PartScore(1, 2), held_out=PartScore(2, 2)),
        "L3": None,
    }
    rebuilt = level_scores_from_json(
        {
            "L1": scores["L1"].to_json(),
            "L2": scores["L2"].to_json(),
            "L3": None,
        },
        "row",
    )
    assert rebuilt == scores
    assert rebuilt["L2"].dev.to_json()["pass"] == 1  # L2 reads pass/total keys


def test_level_scores_reject_an_l2_object_in_the_clean_shape() -> None:
    with pytest.raises(FitnessError, match="pass"):
        level_scores_from_json(
            {
                "L1": {"dev": {"rate": 0.5, "clean": 1, "total": 2},
                       "held-out": {"rate": 1.0, "clean": 1, "total": 1}},
                "L2": {"dev": {"rate": 0.5, "clean": 1, "total": 2},
                       "held-out": {"rate": 1.0, "clean": 1, "total": 1}},
                "L3": None,
            },
            "row",
        )


# --- the extended no-regret rule (history level) --------------------------


def l2_scores(
    l1_dev: tuple[int, int],
    l1_ho: tuple[int, int],
    l2_dev: tuple[int, int] | None = None,
    l2_ho: tuple[int, int] | None = None,
) -> dict:
    """Level-score dicts from (clean, total)/(pass, total) count pairs."""
    return {
        "L1": LevelScore(dev=SplitScore(*l1_dev), held_out=SplitScore(*l1_ho)),
        "L2": (
            None
            if l2_dev is None
            else LevelScore(dev=PartScore(*l2_dev), held_out=PartScore(*l2_ho))
        ),
        "L3": None,
    }


def test_no_regret_l1_only_cases_are_unchanged() -> None:
    # L2 not comparable (null on both sides): the ADR-0001 rule verbatim.
    verdict = evaluate_no_regret(
        l2_scores((2, 3), (2, 2)),
        l2_scores((3, 3), (2, 2)),
    )
    assert verdict.accepted is True
    assert verdict.reason == REASON_ACCEPTED
    assert (verdict.l2_dev_rose, verdict.l2_dev_fell, verdict.l2_held_out_fell) == (
        None,
        None,
        None,
    )


def test_no_regret_l2_held_out_fall_is_rejected() -> None:
    # L1 rose, but L2's Held-out fell: the protective leg rejects the run.
    verdict = evaluate_no_regret(
        l2_scores((2, 3), (2, 2), (2, 2), (2, 2)),
        l2_scores((3, 3), (2, 2), (2, 2), (1, 2)),
    )
    assert verdict.accepted is False
    assert verdict.reason == REASON_REJECTED_HELD_OUT
    assert verdict.held_out_fell is True  # any comparable level's held-out fall
    assert verdict.l2_held_out_fell is True
    assert verdict.dev_rose is True


def test_no_regret_l2_only_improvement_with_flat_l1_is_accepted() -> None:
    # The ticket's named case: L1 flat everywhere, L2 Dev rises -> accept.
    verdict = evaluate_no_regret(
        l2_scores((2, 3), (2, 2), (1, 2), (1, 2)),
        l2_scores((2, 3), (2, 2), (2, 2), (1, 2)),
    )
    assert verdict.accepted is True
    assert verdict.reason == REASON_ACCEPTED_L2
    assert verdict.dev_rose is True  # something rose on Dev (L2)
    assert verdict.l2_dev_rose is True


def test_no_regret_l1_dev_fall_rejects_even_when_l2_rises() -> None:
    # No-regret on the headline: an L1 Dev regression is never acceptable,
    # not even in exchange for an L2 improvement.
    verdict = evaluate_no_regret(
        l2_scores((2, 3), (2, 2), (1, 2), (1, 2)),
        l2_scores((1, 3), (2, 2), (2, 2), (1, 2)),
    )
    assert verdict.accepted is False
    assert verdict.reason == REASON_REJECTED_L1_DEV
    assert verdict.l2_dev_rose is True


def test_no_regret_l2_dev_fall_rejects_despite_l1_rise() -> None:
    verdict = evaluate_no_regret(
        l2_scores((2, 3), (2, 2), (2, 2), (2, 2)),
        l2_scores((3, 3), (2, 2), (1, 2), (2, 2)),
    )
    assert verdict.accepted is False
    assert verdict.reason == REASON_REJECTED_L2_DEV
    assert verdict.l2_dev_fell is True
    assert verdict.dev_rose is True  # L1 rose; L2's regression still rejects


def test_no_regret_l2_flat_with_l1_rise_accepts_with_the_l1_reason() -> None:
    verdict = evaluate_no_regret(
        l2_scores((2, 3), (2, 2), (2, 2), (2, 2)),
        l2_scores((3, 3), (2, 2), (2, 2), (2, 2)),
    )
    assert verdict.accepted is True
    assert verdict.reason == REASON_ACCEPTED
    assert (verdict.l2_dev_rose, verdict.l2_dev_fell, verdict.l2_held_out_fell) == (
        False,
        False,
        False,
    )


def test_no_regret_nothing_rises_anywhere_is_rejected() -> None:
    verdict = evaluate_no_regret(
        l2_scores((2, 3), (2, 2), (2, 2), (2, 2)),
        l2_scores((2, 3), (2, 2), (2, 2), (2, 2)),
    )
    assert verdict.accepted is False
    assert verdict.reason == REASON_REJECTED_DEV


def test_no_regret_held_out_fall_with_no_dev_rise_keeps_the_pinned_reason() -> None:
    # Nothing rose on Dev and a Held-out split fell: the pinned ADR-0001
    # string covers the L2-comparable case too.
    verdict = evaluate_no_regret(
        l2_scores((2, 3), (2, 2), (2, 2), (2, 2)),
        l2_scores((1, 3), (1, 2), (1, 2), (1, 2)),
    )
    assert verdict.accepted is False
    assert verdict.reason == REASON_REJECTED_BOTH
    assert verdict.l2_dev_fell is True
    assert verdict.l2_held_out_fell is True


# --- the committed schemas accept the L2 shapes (and keep the old) --------


def test_history_row_schema_accepts_populated_l2_scalars() -> None:
    l2_object = {
        "dev": {"rate": 0.5, "pass": 1, "total": 2},
        "held-out": {"rate": 1.0, "pass": 2, "total": 2},
    }
    validate(
        {**VALID_ROW, "scalars": {**VALID_ROW["scalars"], "L2": l2_object}},
        load_schema("fitness-history-row-v0"),
    )


def test_history_row_schema_still_accepts_the_pre_g5_null() -> None:
    validate(VALID_ROW, load_schema("fitness-history-row-v0"))


def test_history_row_schema_rejects_malformed_l2_scalars() -> None:
    l2_object = {
        "dev": {"rate": 1.5, "pass": 3, "total": 2},
        "held-out": {"rate": 1.0, "pass": 2, "total": 2},
    }
    with pytest.raises(ValidationError):
        validate(
            {**VALID_ROW, "scalars": {**VALID_ROW["scalars"], "L2": l2_object}},
            load_schema("fitness-history-row-v0"),
        )


def test_no_regret_verdict_with_l2_flags_validates_against_the_row_schema() -> None:
    verdict = evaluate_no_regret(
        l2_scores((2, 3), (2, 2), (2, 2), (2, 2)),
        l2_scores((3, 3), (2, 2), (3, 3), (2, 2)),
    )
    validate({**VALID_ROW, "no_regret": verdict.to_json()}, load_schema("fitness-history-row-v0"))


# --- the runner: L2 measured through the G4 export seam (mocked) ----------


def pass_summary(**overrides) -> dict:
    """A successful export summary in the export-summary-v1 shape, the way
    the real seam returns one (self-checked upstream; the runner reads it
    as-is). Overrides patch top-level keys."""
    summary = {
        "schema_version": 1,
        "vertex_count": 80,
        "triangle_count": 140,
        "bounding_box": {"min": [-1.0, -2.0, -3.0], "max": [1.0, 2.0, 3.0]},
        "warnings": [],
        "store_ordinal": 0,
        "origin_kind": "v5header",
        "pool_group_count": 1,
        "facet_candidate_count": 3,
        "facet_record_count": 3,
        "degenerate_triangle_count": 0,
        "mesh": {
            "edge_count": 210,
            "manifold": True,
            "closed": True,
            "oriented": True,
            "boundary_edge_count": 0,
        },
    }
    summary.update(overrides)
    return summary


def all_pass(_path, _out_path) -> dict:
    """An export seam fake where every part passes the whole gate."""
    return pass_summary()


def export_map(outcomes: dict[str, object], default) -> Callable:
    """An export seam fake keyed by the fixture file's stem: a summary dict
    means success, an ExportError is raised as the real seam would."""

    def fake(path, _out_path):
        outcome = outcomes.get(Path(path).stem, default)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return fake


def report_of(tmp_path: Path, out: str) -> dict:
    return json.loads(
        (tmp_path / "fitness" / json.loads(out)["report"]).read_text(encoding="utf-8")
    )


def run_mini_corpus_with_all_pass(tmp_path, build_catpart, capsys, monkeypatch) -> dict:
    """The standard mini corpus under an all-pass export seam, run once.

    L1: 2/3 dev (one crash fixture), 2/2 held-out; L2: 3/3 dev, 2/2
    held-out (all five manifest rows are kind=part). Returns the
    accepted baseline row.
    """
    from test_fitness_runner import write_mini_corpus

    write_mini_corpus(tmp_path, build_catpart)
    monkeypatch.setattr("catpart.fitness.runner.build_export", all_pass)
    code, out, err = run_fitness_cli(tmp_path, capsys)
    assert code == 0, err
    return json.loads(out)


def test_l2_population_is_parts_with_products_excluded(
    tmp_path: Path, build_catpart, capsys, monkeypatch
) -> None:
    files = {
        "dev-a": ("dev", clean_bytes(build_catpart)),
        "dev-b": ("dev", clean_bytes(build_catpart, payload=b"\x01\x02\x03\x04" * 8)),
        # A product: outside the L2 population (the documented negative,
        # 0/37 products carry any geometry store) — never exported.
        "dev-prod": (
            "dev",
            clean_bytes(build_catpart, records=(("CATProdCont", "CATFeatCont"),)),
        ),
        "ho-a": ("held-out", clean_bytes(build_catpart, payload=b"\xab\xcd\xef\x01" * 8)),
    }
    write_fixture_files(tmp_path, files)
    write_manifest(
        tmp_path,
        [
            manifest_row("dev-a", "dev", files["dev-a"][1]),
            manifest_row("dev-b", "dev", files["dev-b"][1]),
            manifest_row("dev-prod", "dev", files["dev-prod"][1], kind="product"),
            manifest_row("ho-a", "held-out", files["ho-a"][1]),
        ],
    )
    monkeypatch.setattr("catpart.fitness.runner.build_export", all_pass)

    code, out, err = run_fitness_cli(tmp_path, capsys)
    assert code == 0, err
    row = json.loads(out)
    report = report_of(tmp_path, out)

    # The headline counts parts only; both schemas accept the new shapes.
    validate(row, load_schema("fitness-history-row-v0"))
    validate(report, load_schema("fitness-report-v0"))
    assert row["scalars"]["L2"] == {
        "dev": {"rate": 1.0, "pass": 2, "total": 2},
        "held-out": {"rate": 1.0, "pass": 1, "total": 1},
    }

    by_path = {record["path"]: record for record in report["files"]}
    assert by_path["parts/dev-prod.CATPart"]["l2"] is None  # excluded, never exported
    passing = by_path["parts/dev-a.CATPart"]["l2"]
    assert passing["status"] == "pass"
    assert passing["error_class"] is None and passing["failed_check"] is None
    assert passing["vertex_count"] == 80 and passing["triangle_count"] == 140
    assert passing["mesh"] == {
        "manifold": True,
        "closed": True,
        "oriented": True,
        "boundary_edge_count": 0,
    }
    assert passing["bounding_box"] == {"min": [-1.0, -2.0, -3.0], "max": [1.0, 2.0, 3.0]}
    assert passing["warnings"] == []

    assert report["splits"]["dev"]["l2"] == {
        "parts": 2,
        "pass": 2,
        "fail": 0,
        "unavailable": 0,
        "rate": 1.0,
        "error_classes": {},
        "failed_checks": {},
        "components": {
            "closed": 2,
            "open_shell": 0,
            "degenerate_triangles": 0,
            "vertices_only": 0,
        },
    }


def test_l2_component_signals_are_reported_not_collapsed(
    tmp_path: Path, build_catpart, capsys, monkeypatch
) -> None:
    # An open shell passes the gate (G3 F6: sheet-like shells are
    # legitimate geometry) with closed-volume-where-expected reported; a
    # vertices-only export (G2 P7) fails the empty-mesh check and its
    # components are still reported.
    files = {
        "dev-a": ("dev", clean_bytes(build_catpart)),
        "dev-b": ("dev", clean_bytes(build_catpart, payload=b"\x01\x02\x03\x04" * 8)),
        "ho-a": ("held-out", clean_bytes(build_catpart, payload=b"\xab\xcd\xef\x01" * 8)),
    }
    write_fixture_files(tmp_path, files)
    write_manifest(tmp_path, [manifest_row(n, s, d) for n, (s, d) in files.items()])
    monkeypatch.setattr(
        "catpart.fitness.runner.build_export",
        export_map(
            {
                "dev-a": pass_summary(
                    mesh={
                        "edge_count": 200,
                        "manifold": True,
                        "closed": False,
                        "oriented": True,
                        "boundary_edge_count": 4,
                    },
                    warnings=[
                        {
                            "class": "open-shell",
                            "detail": "4 boundary edges: the mesh is a manifold but not closed",
                        }
                    ],
                ),
                "dev-b": pass_summary(
                    triangle_count=0,
                    warnings=[
                        {
                            "class": "no-facet-records",
                            "detail": "pool with no facet header candidates (G2 P7)",
                        }
                    ],
                ),
            },
            pass_summary(),
        ),
    )

    code, out, err = run_fitness_cli(tmp_path, capsys)
    assert code == 0, err
    report = report_of(tmp_path, out)

    block = report["splits"]["dev"]["l2"]
    assert block["parts"] == 2 and block["pass"] == 1 and block["fail"] == 1
    assert block["rate"] == 0.5
    assert block["error_classes"] == {}
    assert block["failed_checks"] == {"empty-mesh": 1}
    assert block["components"] == {
        "closed": 1,  # closed-volume-where-expected: reported, not gated
        "open_shell": 1,
        "degenerate_triangles": 0,
        "vertices_only": 1,
    }
    by_path = {record["path"]: record for record in report["files"]}
    assert by_path["parts/dev-a.CATPart"]["l2"]["mesh"]["closed"] is False
    assert json.loads(out)["scalars"]["L2"]["dev"] == {"rate": 0.5, "pass": 1, "total": 2}


def test_l2_held_out_fall_rejects_the_run(
    tmp_path: Path, build_catpart, capsys, monkeypatch
) -> None:
    run_mini_corpus_with_all_pass(tmp_path, build_catpart, capsys, monkeypatch)

    # Second run, same files: one held-out part's export now fails, so the
    # L2 held-out rate falls (2/2 -> 1/2) while L1 and L2-Dev stay flat.
    monkeypatch.setattr(
        "catpart.fitness.runner.build_export",
        export_map(
            {"ho-a": ExportError("undecoded-variant", "composite index space present")},
            pass_summary(),
        ),
    )
    _, out2, _ = run_fitness_cli(tmp_path, capsys)
    second = json.loads(out2)
    assert second["accepted"] is False
    assert second["no_regret"] == {
        "dev_rose": False,
        "held_out_fell": True,
        "reason": REASON_REJECTED_BOTH,
        "l2_dev_rose": False,
        "l2_dev_fell": False,
        "l2_held_out_fell": True,
    }
    assert second["scalars"]["L2"]["held-out"] == {"rate": 0.5, "pass": 1, "total": 2}


def test_l2_rise_with_flat_l1_is_accepted(
    tmp_path: Path, build_catpart, capsys, monkeypatch
) -> None:
    # Baseline: one dev part fails export (L2 dev 2/3); L1 is measured
    # as-is. The accepted baseline row carries the lower L2.
    from test_fitness_runner import write_mini_corpus

    write_mini_corpus(tmp_path, build_catpart)
    monkeypatch.setattr(
        "catpart.fitness.runner.build_export",
        export_map({"dev-a": ExportError("undecoded-variant", "boom")}, pass_summary()),
    )
    _, out1, _ = run_fitness_cli(tmp_path, capsys)
    baseline = json.loads(out1)
    assert baseline["accepted"] is True
    assert baseline["scalars"]["L2"]["dev"] == {"rate": 2 / 3, "pass": 2, "total": 3}

    # Run 2, same failure: flat L1, flat L2 — nothing rose, rejected.
    _, out2, _ = run_fitness_cli(tmp_path, capsys)
    assert json.loads(out2)["accepted"] is False

    # Run 3: the part exports; the L2 dev rate rises (2/3 -> 3/3) against
    # the last ACCEPTED baseline (run 1) while L1 stays flat — accepted as
    # the L2-only improvement, with the reason recorded.
    monkeypatch.setattr("catpart.fitness.runner.build_export", all_pass)
    _, out3, _ = run_fitness_cli(tmp_path, capsys)
    third = json.loads(out3)
    assert third["accepted"] is True
    assert third["baseline_run_id"] == baseline["run_id"]
    assert third["no_regret"] == {
        "dev_rose": True,
        "held_out_fell": False,
        "reason": REASON_ACCEPTED_L2,
        "l2_dev_rose": True,
        "l2_dev_fell": False,
        "l2_held_out_fell": False,
    }


def test_l2_failure_classification_flows_into_the_run_report(
    tmp_path: Path, build_catpart, capsys, monkeypatch
) -> None:
    run_mini_corpus_with_all_pass(tmp_path, build_catpart, capsys, monkeypatch)
    monkeypatch.setattr(
        "catpart.fitness.runner.build_export",
        export_map(
            {
                "dev-a": ExportError(
                    "missing-geometry-store", "no CATStdCont storage block in the file"
                ),
                "ho-a": ExportError("undecoded-variant", "composite index space present"),
            },
            pass_summary(),
        ),
    )
    code, out, err = run_fitness_cli(tmp_path, capsys)
    assert code == 0, err
    report = report_of(tmp_path, out)

    by_path = {record["path"]: record for record in report["files"]}
    failed = by_path["parts/dev-a.CATPart"]["l2"]
    assert failed["status"] == "fail"
    assert failed["error_class"] == "missing-geometry-store"
    assert failed["error"] == "no CATStdCont storage block in the file"
    assert failed["failed_check"] is None
    assert failed["mesh"] is None and failed["bounding_box"] is None

    assert report["splits"]["dev"]["l2"]["error_classes"] == {
        "missing-geometry-store": 1
    }
    assert report["splits"]["held-out"]["l2"]["error_classes"] == {"undecoded-variant": 1}
    assert json.loads(out)["scalars"]["L2"] == {
        "dev": {"rate": 2 / 3, "pass": 2, "total": 3},
        "held-out": {"rate": 0.5, "pass": 1, "total": 2},
    }


def test_export_crash_outside_the_exporterror_contract_is_classified(
    tmp_path: Path, build_catpart, capsys, monkeypatch
) -> None:
    run_mini_corpus_with_all_pass(tmp_path, build_catpart, capsys, monkeypatch)

    def boom(_path, _out_path):
        raise RuntimeError("exploded")

    monkeypatch.setattr("catpart.fitness.runner.build_export", boom)
    code, out, err = run_fitness_cli(tmp_path, capsys)
    # One broken export never aborts the run: classified and recorded.
    assert code == 0, err
    report = report_of(tmp_path, out)
    record = report["files"][0]["l2"]
    assert record["status"] == "fail"
    assert record["error_class"] == "export-crash"
    assert record["error"] == "RuntimeError: exploded"


@pytest.mark.parametrize(
    "overrides, failed_check",
    [
        ({"vertex_count": 0, "triangle_count": 0}, "empty-mesh"),
        ({"triangle_count": 0}, "empty-mesh"),
        (
            {
                "mesh": {
                    "edge_count": 9,
                    "manifold": False,
                    "closed": False,
                    "oriented": False,
                    "boundary_edge_count": 1,
                }
            },
            "not-manifold",
        ),
        (
            {"bounding_box": {"min": [float("nan"), 0.0, 0.0], "max": [1.0, 1.0, 1.0]}},
            "nonfinite-bbox",
        ),
        ({"degenerate_triangle_count": 3}, "degenerate-triangles"),
    ],
)
def test_l2_sanity_gate_failures(
    tmp_path, build_catpart, capsys, monkeypatch, overrides, failed_check
) -> None:
    run_mini_corpus_with_all_pass(tmp_path, build_catpart, capsys, monkeypatch)
    monkeypatch.setattr(
        "catpart.fitness.runner.build_export", lambda _p, _o: pass_summary(**overrides)
    )
    code, out, _err = run_fitness_cli(tmp_path, capsys)
    assert code == 0
    report = report_of(tmp_path, out)
    for record in report["files"]:
        l2 = record["l2"]
        assert l2["status"] == "fail"
        assert l2["failed_check"] == failed_check
        assert l2["error_class"] is None
    assert report["splits"]["dev"]["l2"]["failed_checks"] == {failed_check: 3}


def test_nonfinite_bounding_box_is_not_published(
    tmp_path, build_catpart, capsys, monkeypatch
) -> None:
    # A NaN must never reach the committed report (strict JSON): the
    # implausible bbox is recorded as null while the check is named.
    run_mini_corpus_with_all_pass(tmp_path, build_catpart, capsys, monkeypatch)
    monkeypatch.setattr(
        "catpart.fitness.runner.build_export",
        lambda _p, _o: pass_summary(
            bounding_box={"min": [float("nan"), 0.0, 0.0], "max": [1.0, 1.0, 1.0]}
        ),
    )
    code, out, _err = run_fitness_cli(tmp_path, capsys)
    assert code == 0
    report_path = tmp_path / "fitness" / json.loads(out)["report"]
    report_text = report_path.read_text(encoding="utf-8")
    assert "NaN" not in report_text  # strict JSON, not the Python float repr
    record = json.loads(report_text)["files"][0]["l2"]
    assert record["bounding_box"] is None
    assert record["failed_check"] == "nonfinite-bbox"


def test_unavailable_part_counts_against_the_l2_rate(
    tmp_path: Path, build_catpart, capsys, monkeypatch
) -> None:
    run_mini_corpus_with_all_pass(tmp_path, build_catpart, capsys, monkeypatch)
    (tmp_path / "corpus" / "fixture" / "parts" / "dev-a.CATPart").unlink()
    monkeypatch.setattr("catpart.fitness.runner.build_export", all_pass)

    code, out, _err = run_fitness_cli(tmp_path, capsys)
    assert code == 0
    report = report_of(tmp_path, out)
    by_path = {record["path"]: record for record in report["files"]}
    missing = by_path["parts/dev-a.CATPart"]["l2"]
    assert missing["status"] == "unavailable"
    assert "missing on disk" in missing["error"]
    assert missing["error_class"] is None
    block = report["splits"]["dev"]["l2"]
    assert block["parts"] == 3 and block["pass"] == 2 and block["unavailable"] == 1
    assert block["rate"] == 2 / 3
    assert json.loads(out)["scalars"]["L2"]["dev"] == {"rate": 2 / 3, "pass": 2, "total": 3}


def test_manifest_unknown_kind_fails_closed(tmp_path: Path, build_catpart, capsys) -> None:
    data = clean_bytes(build_catpart)
    write_manifest(tmp_path, [manifest_row("only", "dev", data, kind="assembly")])
    write_fixture_files(tmp_path, {"only": ("dev", data)})
    code, out, err = run_fitness_cli(tmp_path, capsys)
    assert code == 1
    assert out == ""
    assert "unknown kind 'assembly'" in err


def test_manifest_missing_kind_column_fails_closed(
    tmp_path: Path, build_catpart, capsys
) -> None:
    # The kind column defines the L2 population: a manifest without it
    # cannot define one and must stop the run.
    data = clean_bytes(build_catpart)
    write_fixture_files(tmp_path, {"only": ("dev", data)})
    row = manifest_row("only", "dev", data)
    del row["kind"]
    from test_fitness_runner import MANIFEST_COLUMNS

    import csv
    import io

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=[c for c in MANIFEST_COLUMNS if c != "kind"])
    writer.writeheader()
    writer.writerow(row)
    (tmp_path / "manifests").mkdir(exist_ok=True)
    (tmp_path / "manifests" / "corpus-manifest.csv").write_text(
        buffer.getvalue(), encoding="utf-8"
    )
    code, out, err = run_fitness_cli(tmp_path, capsys)
    assert code == 1
    assert "missing required columns: kind" in err


def test_baseline_without_l2_scalar_is_accepted_as_the_new_baseline(
    tmp_path: Path, build_catpart, capsys, monkeypatch
) -> None:
    # A pre-G5 accepted baseline (scalars.L2 null) cannot support an L2
    # comparison: the corpus-change precedent accepts the run as the new
    # baseline — the ticket's "first accepted L2 row is the baseline".
    from test_fitness_runner import write_mini_corpus

    manifest_path, _files = write_mini_corpus(tmp_path, build_catpart)
    monkeypatch.setattr("catpart.fitness.runner.build_export", all_pass)
    pre_g5 = {
        **VALID_ROW,
        "run_id": "20261107T120000Z-abc123",
        "timestamp": "2026-11-07T12:00:00Z",
        "corpus_digest": digest_of_manifest(manifest_path),
        "accepted": True,
        "scalars": {**VALID_ROW["scalars"], "L2": None},
    }
    history_path = tmp_path / "fitness" / "history.jsonl"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        json.dumps(pre_g5, separators=(",", ":")) + "\n", encoding="utf-8"
    )

    code, out, err = run_fitness_cli(tmp_path, capsys)
    assert code == 0, err
    row = json.loads(out)
    assert row["accepted"] is True
    assert row["baseline_run_id"] == pre_g5["run_id"]
    assert row["no_regret"] == {
        "dev_rose": None,
        "held_out_fell": None,
        "reason": REASON_BASELINE_NO_L2,
        "l2_dev_rose": None,
        "l2_dev_fell": None,
        "l2_held_out_fell": None,
    }
