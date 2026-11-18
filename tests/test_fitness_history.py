"""The L3 construct-coverage scalar in the fitness ladder (ticket #58).

Two contracts live here, both read from committed artifacts:

- the history-row / report schema: ``scalars.L3`` is ``null`` (pre-#58
  rows) or the ``{rate, resolved, total, by_outcome}`` object over the
  frozen construct denominator, with **no dev/held-out split** — construct
  coverage is corpus-split independent;
- the no-regret rule's L3 path: introducing the scalar accepts with L1/L2
  intact, a rise accepts, a fall (or dropping the scalar an accepted row
  carries) rejects, and with L3 null on both sides the verdict is exactly
  the pre-#58 one.

The committed history is an input here, not a fixture: every row must
keep validating and the last accepted row must keep its recorded verdict.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from catpart.fitness import (
    FitnessError,
    LevelScore,
    PartScore,
    SplitScore,
    evaluate_no_regret,
)
from catpart.fitness.history import (
    REASON_ACCEPTED,
    REASON_ACCEPTED_L2,
    REASON_ACCEPTED_L3_INTRODUCED,
    REASON_ACCEPTED_L3_ROSE,
    REASON_REJECTED_BOTH,
    REASON_REJECTED_DEV,
    REASON_REJECTED_HELD_OUT,
    REASON_REJECTED_L1_DEV,
    REASON_REJECTED_L3_FELL,
    CoverageScore,
    coverage_from_scalars,
    level_scores_from_json,
    level_scores_to_json,
    load_last_accepted_row,
)
from catpart.schema import load_schema
from catpart.schema.validate import ValidationError, validate

from test_fitness_runner import VALID_ROW

REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = REPO_ROOT / "fitness" / "history.jsonl"
ROW_SCHEMA = load_schema("fitness-history-row-v0")

#: The BR6 headline as the scorer reports it (23/23 resolved, ticket #58).
L3_BLOCK = {
    "rate": 23 / 23,
    "resolved": 23,
    "total": 23,
    "by_outcome": {
        "decoded": 14,
        "documented-negative": 3,
        "documented-open": 6,
        "candidate": 0,
        "pending-merge": 0,
    },
}

#: The last accepted committed row (the pre-#58 baseline; L3 still null).
LAST_ACCEPTED_RUN_ID = "20261113T231506Z-c2ab64"


def row_with_l3(l3: object) -> dict:
    """A valid row carrying ``l3`` in its scalars slot."""
    return {**VALID_ROW, "scalars": {**VALID_ROW["scalars"], "L3": l3}}


def split_scores(
    l1_dev: tuple[int, int] = (2, 3),
    l1_ho: tuple[int, int] = (2, 2),
    l2_dev: tuple[int, int] = (4, 5),
    l2_ho: tuple[int, int] = (4, 5),
) -> dict:
    """A level-score dict with L1 and L2 comparable (L3 passed separately)."""
    return {
        "L1": LevelScore(dev=SplitScore(*l1_dev), held_out=SplitScore(*l1_ho)),
        "L2": LevelScore(dev=PartScore(*l2_dev), held_out=PartScore(*l2_ho)),
        "L3": None,
    }


def coverage(resolved: int = 23, total: int = 23) -> CoverageScore:
    """A coverage score; the full-rate case carries the real BR6 breakdown."""
    if resolved == total:
        by_outcome = dict(L3_BLOCK["by_outcome"])
    else:
        by_outcome = {
            "decoded": resolved,
            "documented-negative": 0,
            "documented-open": 0,
            "candidate": 0,
            "pending-merge": total - resolved,
        }
    return CoverageScore(resolved=resolved, total=total, by_outcome=by_outcome)


# --- schema: null (pre-#58) or the L3 object --------------------------------


def test_history_row_schema_accepts_a_null_l3() -> None:
    # The 14 committed rows carry "L3": null; the widening is additive.
    assert VALID_ROW["scalars"]["L3"] is None
    validate(VALID_ROW, ROW_SCHEMA)


def test_history_row_schema_accepts_the_full_l3_block() -> None:
    validate(row_with_l3(L3_BLOCK), ROW_SCHEMA)


def test_history_row_schema_rejects_the_l3_block_without_rate() -> None:
    block = {key: value for key, value in L3_BLOCK.items() if key != "rate"}
    with pytest.raises(ValidationError):
        validate(row_with_l3(block), ROW_SCHEMA)


def test_history_row_schema_rejects_an_out_of_range_l3_rate() -> None:
    for rate in (1.5, -0.1):
        with pytest.raises(ValidationError):
            validate(row_with_l3({**L3_BLOCK, "rate": rate}), ROW_SCHEMA)


def test_history_row_schema_requires_the_l3_counts() -> None:
    for missing in ("resolved", "total"):
        block = {key: value for key, value in L3_BLOCK.items() if key != missing}
        with pytest.raises(ValidationError):
            validate(row_with_l3(block), ROW_SCHEMA)


def test_history_row_schema_rejects_malformed_l3_outcome_counts() -> None:
    block = {**L3_BLOCK, "by_outcome": {"decoded": -1}}
    with pytest.raises(ValidationError):
        validate(row_with_l3(block), ROW_SCHEMA)
    block = {**L3_BLOCK, "by_outcome": {"decoded": "many"}}
    with pytest.raises(ValidationError):
        validate(row_with_l3(block), ROW_SCHEMA)


def test_history_row_schema_rejects_a_dev_held_out_shaped_l3() -> None:
    # L3 has no split: an L1/L2-shaped object is not a valid L3 scalar.
    with pytest.raises(ValidationError):
        validate(
            row_with_l3(
                {
                    "dev": {"rate": 1.0, "resolved": 23, "total": 23},
                    "held-out": {"rate": 1.0, "resolved": 23, "total": 23},
                }
            ),
            ROW_SCHEMA,
        )


# --- the committed history keeps its verdicts -------------------------------


def test_every_committed_history_row_still_validates() -> None:
    rows = [
        json.loads(line)
        for line in HISTORY_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 14
    for row in rows:
        validate(row, ROW_SCHEMA)
        assert row["scalars"]["L3"] is None  # every pre-#58 row is unchanged


def test_last_accepted_row_keeps_its_recorded_verdict() -> None:
    row = load_last_accepted_row(HISTORY_PATH)
    assert row is not None
    assert row["run_id"] == LAST_ACCEPTED_RUN_ID
    assert row["accepted"] is True
    assert row["no_regret"]["reason"] == "L2 dev rose with L1 dev flat"
    assert row["scalars"]["L3"] is None
    assert coverage_from_scalars(row["scalars"], "row scalars") is None


# --- the CoverageScore type -------------------------------------------------


def test_coverage_score_round_trips_the_row_shape() -> None:
    score = CoverageScore(resolved=23, total=23, by_outcome=dict(L3_BLOCK["by_outcome"]))
    assert score.to_json() == L3_BLOCK
    assert score.rate == 1.0
    assert CoverageScore.from_json(L3_BLOCK, "w") == score


def test_coverage_score_recomputes_the_rate_from_the_counts() -> None:
    score = CoverageScore.from_json({**L3_BLOCK, "rate": 0.0}, "w")
    assert score.rate == 1.0  # the recorded rate is never trusted


def test_coverage_score_rejects_malformed_counts() -> None:
    with pytest.raises(ValueError):
        CoverageScore(24, 23)  # resolved beyond the denominator
    with pytest.raises(ValueError):
        CoverageScore(True, 23)  # booleans are not counts
    with pytest.raises(ValueError):
        CoverageScore(0, 0)  # an empty denominator is not a measurable rate
    with pytest.raises(ValueError):
        CoverageScore(1, 2, by_outcome={"decoded": -1})
    with pytest.raises(FitnessError):
        CoverageScore.from_json({"total": 23}, "w")  # no resolved count
    with pytest.raises(FitnessError):
        CoverageScore.from_json({"resolved": 1, "total": 2, "by_outcome": []}, "w")
    with pytest.raises(FitnessError):
        CoverageScore.from_json({"resolved": 1, "total": 2, "by_outcome": {"x": "1"}}, "w")


def test_level_scores_keep_the_l3_slot_and_skip_it_on_the_way_back() -> None:
    scores = split_scores()
    scalars = level_scores_to_json(scores, coverage())
    assert list(scalars) == ["L1", "L2", "L3"]
    assert scalars["L3"] == L3_BLOCK
    assert level_scores_to_json(scores)["L3"] is None
    # The split reader never interprets the single L3 scalar as a split pair.
    assert level_scores_from_json(scalars, "row") == scores


def test_coverage_from_scalars_reads_the_l3_slot() -> None:
    assert coverage_from_scalars({"L3": L3_BLOCK}, "s") == coverage()
    assert coverage_from_scalars({"L3": None}, "s") is None
    with pytest.raises(FitnessError):
        coverage_from_scalars({"L3": "23/23"}, "s")


# --- the no-regret rule's L3 path (ticket #58) ------------------------------


def test_l3_introduction_is_accepted_with_l1_l2_intact() -> None:
    # The BR6 case: the baseline row predates L3, everything else is flat.
    verdict = evaluate_no_regret(
        split_scores(),
        split_scores(),
        baseline_l3=None,
        current_l3=coverage(),
    )
    assert verdict.accepted is True
    assert verdict.reason == REASON_ACCEPTED_L3_INTRODUCED
    assert verdict.dev_rose is False  # no Dev rise was needed or recorded
    assert verdict.held_out_fell is False


def test_l3_rise_with_flat_dev_is_accepted() -> None:
    verdict = evaluate_no_regret(
        split_scores(),
        split_scores(),
        baseline_l3=coverage(20),
        current_l3=coverage(),
    )
    assert verdict.accepted is True
    assert verdict.reason == REASON_ACCEPTED_L3_ROSE


def test_l3_rise_does_not_override_an_l1_dev_fall() -> None:
    verdict = evaluate_no_regret(
        split_scores(l1_dev=(3, 3)),
        split_scores(l1_dev=(2, 3)),
        baseline_l3=coverage(20),
        current_l3=coverage(),
    )
    assert verdict.accepted is False
    assert verdict.reason == REASON_REJECTED_L1_DEV


def test_l3_fall_is_rejected_even_when_dev_rises() -> None:
    verdict = evaluate_no_regret(
        split_scores(l1_dev=(2, 3)),
        split_scores(l1_dev=(3, 3)),
        baseline_l3=coverage(),
        current_l3=coverage(20),
    )
    assert verdict.accepted is False
    assert verdict.reason == REASON_REJECTED_L3_FELL
    assert verdict.dev_rose is True  # the Dev rise does not rescue the fall


def test_l3_fall_does_not_mask_an_l1_dev_fall() -> None:
    # Precedence regression: before the fix, an L3 fall was reported as the
    # reason even when L1 Dev also fell, hiding the Dev regression.
    verdict = evaluate_no_regret(
        split_scores(l1_dev=(3, 3)),
        split_scores(l1_dev=(2, 3)),
        baseline_l3=coverage(),
        current_l3=coverage(20),
    )
    assert verdict.accepted is False
    assert verdict.reason == REASON_REJECTED_L1_DEV


def test_dropping_the_l3_scalar_an_accepted_row_carries_is_rejected() -> None:
    verdict = evaluate_no_regret(
        split_scores(),
        split_scores(),
        baseline_l3=coverage(),
        current_l3=None,
    )
    assert verdict.accepted is False
    assert verdict.reason == REASON_REJECTED_L3_FELL


def test_a_flat_l3_is_not_an_increment() -> None:
    # Equal coverage is not a rise (ADR-0001: an increment must rise
    # somewhere); the L3 clause never turns a flat rerun into an acceptance.
    verdict = evaluate_no_regret(
        split_scores(),
        split_scores(),
        baseline_l3=coverage(),
        current_l3=coverage(),
    )
    assert verdict.accepted is False
    assert verdict.reason == REASON_REJECTED_DEV


def test_held_out_fall_outranks_the_l3_fall_reason() -> None:
    verdict = evaluate_no_regret(
        split_scores(),
        split_scores(l1_ho=(1, 2)),
        baseline_l3=coverage(),
        current_l3=coverage(20),
    )
    assert verdict.accepted is False
    assert verdict.reason == REASON_REJECTED_BOTH


@pytest.mark.parametrize(
    ("baseline", "current", "reason"),
    [
        (split_scores(), split_scores(l1_dev=(3, 3)), REASON_ACCEPTED),
        (
            split_scores(),
            split_scores(l2_dev=(5, 5)),
            REASON_ACCEPTED_L2,
        ),
        (split_scores(), split_scores(), REASON_REJECTED_DEV),
        (split_scores(), split_scores(l1_ho=(1, 2)), REASON_REJECTED_BOTH),
        (
            split_scores(),
            split_scores(l1_dev=(3, 3), l1_ho=(1, 2)),
            REASON_REJECTED_HELD_OUT,
        ),
    ],
)
def test_l3_null_on_both_sides_is_the_pre_58_verdict(
    baseline: dict, current: dict, reason: str
) -> None:
    explicit = evaluate_no_regret(baseline, current, baseline_l3=None, current_l3=None)
    implicit = evaluate_no_regret(baseline, current)
    assert explicit == implicit  # byte-identical verdict to the pre-#58 rule
    assert explicit.reason == reason


def test_l3_verdict_validates_against_the_row_schema() -> None:
    verdict = evaluate_no_regret(
        split_scores(),
        split_scores(),
        baseline_l3=None,
        current_l3=coverage(),
    )
    row = {
        **VALID_ROW,
        "no_regret": verdict.to_json(),
        "scalars": {**VALID_ROW["scalars"], "L3": L3_BLOCK},
    }
    validate(row, ROW_SCHEMA)
