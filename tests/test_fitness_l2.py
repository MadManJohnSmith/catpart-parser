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

import pytest

from catpart.fitness import LevelScore, PartScore, SplitScore, evaluate_no_regret
from catpart.fitness.history import (
    REASON_ACCEPTED,
    REASON_ACCEPTED_L2,
    REASON_REJECTED_BOTH,
    REASON_REJECTED_DEV,
    REASON_REJECTED_HELD_OUT,
    REASON_REJECTED_L1_DEV,
    REASON_REJECTED_L2_DEV,
    level_scores_from_json,
)
from catpart.fitness import FitnessError
from catpart.schema import load_schema
from catpart.schema.validate import ValidationError, validate

from test_fitness_runner import VALID_ROW


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
