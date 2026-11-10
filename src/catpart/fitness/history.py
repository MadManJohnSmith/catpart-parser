"""Committed append-only fitness history and the no-regret rule (ADR-0001).

``fitness/history.jsonl`` records one row per run — accepted or
rejected — so any session or CI run can see the trend and the cost of
failed attempts (GLOSSARY: Fitness history). Rows follow the committed
schema ``fitness-history-row-v0.json``; the runner appends exactly one
row per run and never rewrites earlier content.

The no-regret rule is pinned by ADR-0001 and extended by ticket #33: an
increment is accepted only if no comparable split regresses and at least
one comparable level rises on Dev. L1 (the headline) must strictly rise
on Dev and not fall on Held-out; L2 is protective — neither of its
splits may fall — so an L2-only improvement with a flat L1 is
acceptable (reason recorded). Comparisons use exact rational rates
(:class:`fractions.Fraction` of the recorded counts) instead of the
rounded floats in the rows, so two runs that differ below float
precision cannot flip a verdict.
"""

from __future__ import annotations

import dataclasses
import json
from fractions import Fraction
from pathlib import Path

from catpart.fitness import FitnessError
from catpart.schema import load_schema
from catpart.schema.validate import SchemaError, ValidationError, validate

#: Capability levels of the fitness ladder (ADR-0001). L1 (clean parse)
#: carries a scalar since Spec C, L2 (geometry sanity over parts) since
#: ticket #33; L3 stays null in every artifact until that level exists.
LEVELS: tuple[str, ...] = ("L1", "L2", "L3")

ROW_SCHEMA = load_schema("fitness-history-row-v0")

#: Fixed verdict strings. The baseline cases have no comparison to make:
#: the first accepted run, a run whose last accepted baseline row was
#: measured on a different corpus (ADR-0001: a corpus change invalidates
#: history comparison, made detectable by the recorded corpus digest), or
#: a run whose baseline predates the L2 scalar (ticket #33 — the first
#: accepted L2 row is the baseline, the corpus-change precedent applies).
REASON_BASELINE_FIRST = "baseline: no previous accepted row"
REASON_BASELINE_CORPUS_CHANGED = (
    "baseline: previous accepted row has a different corpus digest"
)
REASON_BASELINE_NO_L2 = "baseline: previous accepted row has no L2 scalar"
REASON_ACCEPTED = "dev rose and held-out did not fall"
REASON_ACCEPTED_L2 = "L2 dev rose with L1 dev flat"
REASON_REJECTED_DEV = "dev did not rise"
REASON_REJECTED_HELD_OUT = "held-out fell"
REASON_REJECTED_BOTH = "dev did not rise and held-out fell"
REASON_REJECTED_L1_DEV = "L1 dev fell"
REASON_REJECTED_L2_DEV = "L2 dev fell"


def _validate_counts(numerator: int, total: int, name: str) -> None:
    """Shared exact-count validation of :class:`SplitScore`/`PartScore`."""
    if isinstance(numerator, bool) or isinstance(total, bool):
        raise ValueError(f"{name}/total must be integers, not booleans")
    if not isinstance(numerator, int) or not isinstance(total, int):
        raise ValueError(f"{name}/total must be integers")
    if total < 1:
        raise ValueError(f"total must be at least 1, got {total}")
    if not 0 <= numerator <= total:
        raise ValueError(f"{name} must be within [0, total], got {numerator}/{total}")


@dataclasses.dataclass(frozen=True)
class SplitScore:
    """One split's clean-parse score, kept as exact counts.

    ``rate`` (``clean / total``) is what the artifacts report; the
    comparisons use :meth:`fraction` so the verdict never depends on
    float rounding. ``total`` is the manifest rows of the split —
    the "share of the Corpus that is a Clean parse" denominator
    (GLOSSARY) — so files missing on disk count as not clean.
    """

    clean: int
    total: int

    def __post_init__(self) -> None:
        _validate_counts(self.clean, self.total, "clean")

    @property
    def rate(self) -> float:
        return self.clean / self.total

    def fraction(self) -> Fraction:
        return Fraction(self.clean, self.total)

    def to_json(self) -> dict:
        return {"rate": self.rate, "clean": self.clean, "total": self.total}

    @classmethod
    def from_json(cls, obj: object, where: str) -> SplitScore:
        """Rebuild a score from a history row's split-scalars object.

        The recorded ``rate`` is not trusted for comparisons (it is
        recomputed from the counts); malformed counts raise
        :class:`FitnessError` naming the row position ``where``.
        """
        if not isinstance(obj, dict):
            raise FitnessError(f"{where}: expected an object, got {type(obj).__name__}")
        clean = obj.get("clean")
        total = obj.get("total")
        try:
            return cls(clean=clean, total=total)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise FitnessError(f"{where}: {exc}") from exc


@dataclasses.dataclass(frozen=True)
class PartScore:
    """One split's L2 geometry-sanity score, kept as exact counts (#33).

    ``passed`` counts the split's ``kind=part`` manifest rows whose export
    passed the L2 sanity gate; ``total`` is the split's ``kind=part``
    manifest rows — the L2 population (products are excluded: the
    documented negative, 0/37 sampled products carry any geometry store).
    Mirrors :class:`SplitScore` with ``pass``/``total`` JSON keys;
    comparisons use :meth:`fraction`, never the rounded rate.
    """

    passed: int
    total: int

    def __post_init__(self) -> None:
        _validate_counts(self.passed, self.total, "pass")

    @property
    def rate(self) -> float:
        return self.passed / self.total

    def fraction(self) -> Fraction:
        return Fraction(self.passed, self.total)

    def to_json(self) -> dict:
        return {"rate": self.rate, "pass": self.passed, "total": self.total}

    @classmethod
    def from_json(cls, obj: object, where: str) -> PartScore:
        """Rebuild a score from a history row's L2 split-scalars object.

        The recorded ``rate`` is not trusted for comparisons (it is
        recomputed from the counts); malformed counts raise
        :class:`FitnessError` naming the row position ``where``.
        """
        if not isinstance(obj, dict):
            raise FitnessError(f"{where}: expected an object, got {type(obj).__name__}")
        passed = obj.get("pass")
        total = obj.get("total")
        try:
            return cls(passed=passed, total=total)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise FitnessError(f"{where}: {exc}") from exc


@dataclasses.dataclass(frozen=True)
class LevelScore:
    """One level's Dev/Held-out pair of split scores.

    L1 carries :class:`SplitScore` pairs (clean/total); L2 carries
    :class:`PartScore` pairs (pass/total, ticket #33).
    """

    dev: SplitScore | PartScore
    held_out: SplitScore | PartScore

    def to_json(self) -> dict:
        # The JSON key matches the manifest's split value ("held-out").
        return {"dev": self.dev.to_json(), "held-out": self.held_out.to_json()}

    @classmethod
    def from_json(cls, obj: object, where: str) -> LevelScore:
        if not isinstance(obj, dict):
            raise FitnessError(f"{where}: expected an object, got {type(obj).__name__}")
        if "dev" not in obj or "held-out" not in obj:
            raise FitnessError(f"{where}: missing 'dev' or 'held-out' split")
        return cls(
            dev=SplitScore.from_json(obj["dev"], f"{where}.dev"),
            held_out=SplitScore.from_json(obj["held-out"], f"{where}.held-out"),
        )


def level_scores_to_json(scores: dict[str, LevelScore | None]) -> dict:
    """Serialize the per-level scalars, keeping room for the whole ladder."""
    out: dict[str, object] = {}
    for level in LEVELS:
        score = scores.get(level)
        out[level] = score.to_json() if score is not None else None
    return out


#: The split-score class each level's scalars round-trip through: L1's
#: counts are clean/total, L2's are pass/total (ticket #33). A level
#: without an entry keeps L1's clean/total shape.
SPLIT_SCORE_CLASSES: dict[str, type] = {"L1": SplitScore, "L2": PartScore}


def level_scores_from_json(obj: object, where: str) -> dict[str, LevelScore | None]:
    """Rebuild per-level scalars from a history row's ``scalars`` object."""
    if not isinstance(obj, dict):
        raise FitnessError(f"{where}: expected an object, got {type(obj).__name__}")
    out: dict[str, LevelScore | None] = {}
    for level in LEVELS:
        value = obj.get(level)
        if value is None:
            out[level] = None
            continue
        if not isinstance(value, dict) or "dev" not in value or "held-out" not in value:
            raise FitnessError(f"{where}.{level}: missing 'dev' or 'held-out' split")
        score_cls = SPLIT_SCORE_CLASSES.get(level, SplitScore)
        out[level] = LevelScore(
            dev=score_cls.from_json(value["dev"], f"{where}.{level}.dev"),
            held_out=score_cls.from_json(value["held-out"], f"{where}.{level}.held-out"),
        )
    return out


@dataclasses.dataclass(frozen=True)
class NoRegret:
    """Verdict of the no-regret comparison (ADR-0001, extended by #33).

    ``dev_rose``/``held_out_fell`` are ``None`` when no baseline
    comparison happened (baseline runs); with L2 comparable they
    aggregate both levels (any Dev rise / any Held-out fall), and the
    ``l2_*`` fields carry L2's own outcomes — ``None`` when L2 was not
    comparable (a pre-G5 baseline row carries no L2 scalar).
    ``accepted`` is the run's verdict: the row and report record it at
    their top level.
    """

    accepted: bool
    dev_rose: bool | None
    held_out_fell: bool | None
    reason: str
    l2_dev_rose: bool | None = None
    l2_dev_fell: bool | None = None
    l2_held_out_fell: bool | None = None

    def to_json(self) -> dict:
        return {
            "dev_rose": self.dev_rose,
            "held_out_fell": self.held_out_fell,
            "reason": self.reason,
            "l2_dev_rose": self.l2_dev_rose,
            "l2_dev_fell": self.l2_dev_fell,
            "l2_held_out_fell": self.l2_held_out_fell,
        }


def evaluate_no_regret(
    baseline: dict[str, LevelScore | None],
    current: dict[str, LevelScore | None],
) -> NoRegret:
    """Apply the no-regret rule level by level (ADR-0001 + ticket #33).

    A level compares when both sides carry a scalar for it. L1 keeps the
    ADR-0001 rule — the headline must strictly rise on Dev and not fall
    on Held-out; L2 is protective — neither of its splits may fall. The
    run is accepted when no comparable split regressed and at least one
    comparable level's Dev rose, so an L2-only improvement with a flat
    L1 is acceptable (reason recorded). Raises :class:`ValueError` when
    no level is comparable — with a baseline row there is always at
    least L1.
    """
    comparable = [
        level
        for level in LEVELS
        if baseline.get(level) is not None and current.get(level) is not None
    ]
    if not comparable:
        raise ValueError("no comparable level scalars between baseline and current run")
    dev_rose = {
        level: current[level].dev.fraction() > baseline[level].dev.fraction()  # type: ignore[union-attr]
        for level in comparable
    }
    dev_fell = {
        level: current[level].dev.fraction() < baseline[level].dev.fraction()  # type: ignore[union-attr]
        for level in comparable
    }
    held_out_fell = {
        level: current[level].held_out.fraction() < baseline[level].held_out.fraction()  # type: ignore[union-attr]
        for level in comparable
    }
    l2_compared = "L2" in comparable
    any_dev_rose = any(dev_rose.values())
    any_dev_fell = any(dev_fell.values())
    any_held_out_fell = any(held_out_fell.values())

    accepted = any_dev_rose and not any_dev_fell and not any_held_out_fell
    if accepted:
        reason = REASON_ACCEPTED if dev_rose.get("L1") else REASON_ACCEPTED_L2
    elif any_held_out_fell:
        reason = REASON_REJECTED_HELD_OUT if any_dev_rose else REASON_REJECTED_BOTH
    elif dev_fell.get("L1"):
        reason = REASON_REJECTED_L1_DEV
    elif l2_compared and dev_fell["L2"]:
        reason = REASON_REJECTED_L2_DEV
    else:
        reason = REASON_REJECTED_DEV
    return NoRegret(
        accepted=accepted,
        dev_rose=any_dev_rose,
        held_out_fell=any_held_out_fell,
        reason=reason,
        l2_dev_rose=dev_rose.get("L2") if l2_compared else None,
        l2_dev_fell=dev_fell.get("L2") if l2_compared else None,
        l2_held_out_fell=held_out_fell.get("L2") if l2_compared else None,
    )


def load_last_accepted_row(history_path: Path) -> dict | None:
    """Return the last accepted row of the history, or ``None`` when absent.

    Every non-empty line must parse and validate against
    ``fitness-history-row-v0.json`` — the history is committed and its
    integrity is the basis of every comparison, so a corrupt line fails
    closed instead of being skipped.
    """
    try:
        text = history_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    last: dict | None = None
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FitnessError(
                f"{history_path}:{lineno}: history line is not valid JSON: {exc}"
            ) from exc
        try:
            validate(row, ROW_SCHEMA)
        except ValidationError as exc:
            raise FitnessError(
                f"{history_path}:{lineno}: history row violates "
                f"fitness-history-row-v0: {exc}"
            ) from exc
        except SchemaError as exc:
            raise FitnessError(f"schema fitness-history-row-v0 is invalid: {exc}") from exc
        if row["accepted"]:
            last = row
    return last


def append_row(history_path: Path, row: dict) -> None:
    """Append exactly one JSON line; existing content is never rewritten.

    The row is validated before writing, so no code path can append an
    invalid row to the committed history.
    """
    try:
        validate(row, ROW_SCHEMA)
    except ValidationError as exc:
        raise FitnessError(f"refusing to append invalid history row: {exc}") from exc
    except SchemaError as exc:
        raise FitnessError(f"schema fitness-history-row-v0 is invalid: {exc}") from exc
    history_path.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n" keeps the committed history at LF endings on every platform.
    with history_path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, separators=(",", ":")) + "\n")
