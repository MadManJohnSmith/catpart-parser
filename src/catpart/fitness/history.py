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

L3 (construct coverage, ticket #58) has **no Dev/Held-out pair**:
construct coverage is a property of the committed evidence, independent
of the corpus split. It compares as a single scalar
(:class:`CoverageScore`): recording it for the first time
(``L3_INTRODUCED``) accepts a run with L1/L2 intact without requiring a
Dev rise, a strictly higher rate accepts (``L3_ROSE``), and a fall — or
dropping the scalar an accepted baseline carries — rejects
(``L3_FELL``). With L3 null on both sides the verdict is exactly the
pre-#58 one.
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
#: ticket #33, L3 (construct coverage) since ticket #58.
LEVELS: tuple[str, ...] = ("L1", "L2", "L3")

#: The levels scored on the Dev/Held-out split pair. L3 is deliberately
#: not one of them: construct coverage is corpus-split independent and
#: compares as a single scalar (:class:`CoverageScore`).
SPLIT_LEVELS: tuple[str, ...] = ("L1", "L2")

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
#: L3 (ticket #58). The introduction has its own acceptance reason: a
#: run that records the construct-coverage scalar for the first time is
#: accepted with L1/L2 intact, no Dev rise required.
REASON_ACCEPTED_L3_INTRODUCED = "L3 recorded with L1/L2 intact"
REASON_ACCEPTED_L3_ROSE = "L3 construct coverage rose"
REASON_REJECTED_L3_FELL = "L3 construct coverage fell"


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
class CoverageScore:
    """The L3 construct-coverage scalar (ADR-0001, ticket #58).

    ``resolved / total`` over the frozen construct denominator (23 at the
    BR1 freeze), with ``by_outcome`` recording the outcome split. Unlike
    :class:`SplitScore`/:class:`PartScore` there is **no Dev/Held-out
    pair**: construct coverage is a property of the committed evidence
    artifacts and is independent of the corpus split, so the row shape
    carries one scalar. Comparisons use :meth:`fraction`, never the
    rounded rate.
    """

    resolved: int
    total: int
    by_outcome: dict[str, int] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_counts(self.resolved, self.total, "resolved")
        for outcome, count in self.by_outcome.items():
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError(
                    f"by_outcome[{outcome!r}] must be a non-negative integer, "
                    f"got {count!r}"
                )

    @property
    def rate(self) -> float:
        return self.resolved / self.total

    def fraction(self) -> Fraction:
        return Fraction(self.resolved, self.total)

    def to_json(self) -> dict:
        return {
            "rate": self.rate,
            "resolved": self.resolved,
            "total": self.total,
            "by_outcome": dict(self.by_outcome),
        }

    @classmethod
    def from_json(cls, obj: object, where: str) -> CoverageScore:
        """Rebuild the L3 scalar from a history row's ``scalars.L3`` object.

        The recorded ``rate`` is not trusted (it is recomputed from the
        counts); malformed counts or a non-object ``by_outcome`` raise
        :class:`FitnessError` naming the row position ``where``.
        """
        if not isinstance(obj, dict):
            raise FitnessError(f"{where}: expected an object, got {type(obj).__name__}")
        by_outcome = obj.get("by_outcome", {})
        if not isinstance(by_outcome, dict):
            raise FitnessError(
                f"{where}.by_outcome: expected an object, got "
                f"{type(by_outcome).__name__}"
            )
        try:
            return cls(
                resolved=obj.get("resolved"),  # type: ignore[arg-type]
                total=obj.get("total"),  # type: ignore[arg-type]
                by_outcome=dict(by_outcome),
            )
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


def level_scores_to_json(
    scores: dict[str, LevelScore | None], l3: CoverageScore | None = None
) -> dict:
    """Serialize the per-level scalars, keeping the whole ladder in one shape.

    L1/L2 are the split-shaped scores; L3 is the single construct-coverage
    scalar (``None`` until a row records it, ticket #58).
    """
    out: dict[str, object] = {}
    for level in SPLIT_LEVELS:
        score = scores.get(level)
        out[level] = score.to_json() if score is not None else None
    out["L3"] = l3.to_json() if l3 is not None else None
    return out


#: The split-score class each level's scalars round-trip through: L1's
#: counts are clean/total, L2's are pass/total (ticket #33). A level
#: without an entry keeps L1's clean/total shape.
SPLIT_SCORE_CLASSES: dict[str, type] = {"L1": SplitScore, "L2": PartScore}


def level_scores_from_json(obj: object, where: str) -> dict[str, LevelScore | None]:
    """Rebuild the split-shaped per-level scalars from a row's ``scalars``.

    L3 is skipped: it has no ``dev``/``held-out`` pair and is read by
    :func:`coverage_from_scalars` instead.
    """
    if not isinstance(obj, dict):
        raise FitnessError(f"{where}: expected an object, got {type(obj).__name__}")
    out: dict[str, LevelScore | None] = {level: None for level in LEVELS}
    for level in SPLIT_LEVELS:
        value = obj.get(level)
        if value is None:
            continue
        if not isinstance(value, dict) or "dev" not in value or "held-out" not in value:
            raise FitnessError(f"{where}.{level}: missing 'dev' or 'held-out' split")
        score_cls = SPLIT_SCORE_CLASSES.get(level, SplitScore)
        out[level] = LevelScore(
            dev=score_cls.from_json(value["dev"], f"{where}.{level}.dev"),
            held_out=score_cls.from_json(value["held-out"], f"{where}.{level}.held-out"),
        )
    return out


def coverage_from_scalars(obj: object, where: str) -> CoverageScore | None:
    """The L3 scalar of a history row's ``scalars`` object (``None`` before #58)."""
    if not isinstance(obj, dict):
        raise FitnessError(f"{where}: expected an object, got {type(obj).__name__}")
    value = obj.get("L3")
    if value is None:
        return None
    return CoverageScore.from_json(value, f"{where}.L3")


@dataclasses.dataclass(frozen=True)
class NoRegret:
    """Verdict of the no-regret comparison (ADR-0001, extended by #33/#58).

    ``dev_rose``/``held_out_fell`` are ``None`` when no baseline
    comparison happened (baseline runs); with L2 comparable they
    aggregate both levels (any Dev rise / any Held-out fall), and the
    ``l2_*`` fields carry L2's own outcomes — ``None`` when L2 was not
    comparable (a pre-G5 baseline row carries no L2 scalar). L3 is
    carried by the ``reason`` (introducing, rising and falling coverage
    each have a fixed string) rather than by a split flag: it has no
    Dev/Held-out pair. ``accepted`` is the run's verdict: the row and
    report record it at their top level.
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
    *,
    baseline_l3: CoverageScore | None = None,
    current_l3: CoverageScore | None = None,
) -> NoRegret:
    """Apply the no-regret rule level by level (ADR-0001 + #33 + #58).

    A split level compares when both sides carry a scalar for it. L1 keeps
    the ADR-0001 rule — the headline must strictly rise on Dev and not
    fall on Held-out; L2 is protective — neither of its splits may fall.
    The run is accepted when no comparable split regressed and at least
    one comparable level's Dev rose, so an L2-only improvement with a
    flat L1 is acceptable (reason recorded).

    L3 is a single scalar with no split. ``baseline_l3``/``current_l3``
    describe it explicitly:

    - both present: comparable — a higher rate accepts
      (:data:`REASON_ACCEPTED_L3_ROSE`), a lower one rejects
      (:data:`REASON_REJECTED_L3_FELL`);
    - only the current present: ``L3_INTRODUCED`` — the first recorded
      coverage accepts with L1/L2 intact and needs no Dev rise
      (:data:`REASON_ACCEPTED_L3_INTRODUCED`);
    - only the baseline present: the scalar an accepted row carried was
      dropped, which rejects like a fall;
    - both absent: exactly the pre-#58 verdict.

    Raises :class:`ValueError` when no split level is comparable — with a
    baseline row there is always at least L1.
    """
    comparable = [
        level
        for level in SPLIT_LEVELS
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

    l3_introduced = baseline_l3 is None and current_l3 is not None
    l3_dropped = baseline_l3 is not None and current_l3 is None
    l3_compared = baseline_l3 is not None and current_l3 is not None
    l3_rose = l3_compared and current_l3.fraction() > baseline_l3.fraction()
    l3_fell = l3_dropped or (l3_compared and current_l3.fraction() < baseline_l3.fraction())

    accepted = (
        (any_dev_rose or l3_introduced or l3_rose)
        and not any_dev_fell
        and not any_held_out_fell
        and not l3_fell
    )
    if accepted:
        if dev_rose.get("L1"):
            reason = REASON_ACCEPTED
        elif dev_rose.get("L2"):
            reason = REASON_ACCEPTED_L2
        elif l3_introduced:
            reason = REASON_ACCEPTED_L3_INTRODUCED
        else:
            reason = REASON_ACCEPTED_L3_ROSE
    elif any_held_out_fell:
        reason = REASON_REJECTED_HELD_OUT if any_dev_rose else REASON_REJECTED_BOTH
    elif dev_fell.get("L1"):
        reason = REASON_REJECTED_L1_DEV
    elif l2_compared and dev_fell["L2"]:
        reason = REASON_REJECTED_L2_DEV
    elif l3_fell:
        reason = REASON_REJECTED_L3_FELL
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
