"""Committed append-only fitness history and the no-regret rule (ADR-0001).

``fitness/history.jsonl`` records one row per run — accepted or
rejected — so any session or CI run can see the trend and the cost of
failed attempts (GLOSSARY: Fitness history). Rows follow the committed
schema ``fitness-history-row-v0.json``; the runner appends exactly one
row per run and never rewrites earlier content.

The no-regret rule is pinned by ADR-0001: an increment is accepted only
if the headline rises on the Dev split AND does not fall on the Held-out
split. Comparisons use exact rational rates (:class:`fractions.Fraction`
of the recorded clean/total counts) instead of the rounded floats in
the rows, so two runs that differ below float precision cannot flip a
verdict.
"""

from __future__ import annotations

import dataclasses
import json
from fractions import Fraction
from pathlib import Path

from catpart.fitness import FitnessError
from catpart.schema import load_schema
from catpart.schema.validate import SchemaError, ValidationError, validate

#: Capability levels of the fitness ladder (ADR-0001). Only L1 (clean
#: parse) carries a scalar while the parser reports metadata only (L1 of
#: Spec C); L2 and L3 stay null in every artifact until those levels exist.
LEVELS: tuple[str, ...] = ("L1", "L2", "L3")

ROW_SCHEMA = load_schema("fitness-history-row-v0")

#: Fixed verdict strings. The baseline cases have no comparison to make:
#: the first accepted run, or a run whose last accepted baseline row was
#: measured on a different corpus (ADR-0001: a corpus change invalidates
#: history comparison, made detectable by the recorded corpus digest).
REASON_BASELINE_FIRST = "baseline: no previous accepted row"
REASON_BASELINE_CORPUS_CHANGED = (
    "baseline: previous accepted row has a different corpus digest"
)
REASON_ACCEPTED = "dev rose and held-out did not fall"
REASON_REJECTED_DEV = "dev did not rise"
REASON_REJECTED_HELD_OUT = "held-out fell"
REASON_REJECTED_BOTH = "dev did not rise and held-out fell"


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
        if isinstance(self.clean, bool) or isinstance(self.total, bool):
            raise ValueError("clean/total must be integers, not booleans")
        if not isinstance(self.clean, int) or not isinstance(self.total, int):
            raise ValueError("clean/total must be integers")
        if self.total < 1:
            raise ValueError(f"total must be at least 1, got {self.total}")
        if not 0 <= self.clean <= self.total:
            raise ValueError(f"clean must be within [0, total], got {self.clean}/{self.total}")

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
class LevelScore:
    """One level's Dev/Held-out pair of :class:`SplitScore`."""

    dev: SplitScore
    held_out: SplitScore

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


def level_scores_from_json(obj: object, where: str) -> dict[str, LevelScore | None]:
    """Rebuild per-level scalars from a history row's ``scalars`` object."""
    if not isinstance(obj, dict):
        raise FitnessError(f"{where}: expected an object, got {type(obj).__name__}")
    out: dict[str, LevelScore | None] = {}
    for level in LEVELS:
        value = obj.get(level)
        out[level] = None if value is None else LevelScore.from_json(value, f"{where}.{level}")
    return out


@dataclasses.dataclass(frozen=True)
class NoRegret:
    """Verdict of the no-regret comparison (ADR-0001).

    ``dev_rose``/``held_out_fell`` are ``None`` when no baseline
    comparison happened (baseline runs). ``accepted`` is the run's
    verdict: the row and report record it at their top level.
    """

    accepted: bool
    dev_rose: bool | None
    held_out_fell: bool | None
    reason: str

    def to_json(self) -> dict:
        return {
            "dev_rose": self.dev_rose,
            "held_out_fell": self.held_out_fell,
            "reason": self.reason,
        }


def evaluate_no_regret(
    baseline: dict[str, LevelScore | None],
    current: dict[str, LevelScore | None],
) -> NoRegret:
    """Apply the ADR-0001 no-regret rule level by level.

    A level compares when both sides carry a scalar for it; every
    comparable level must satisfy "Dev rises AND Held-out does not
    fall". Raises :class:`ValueError` when no level is comparable —
    with a baseline row there is always at least L1.
    """
    comparable = [
        level
        for level in LEVELS
        if baseline.get(level) is not None and current.get(level) is not None
    ]
    if not comparable:
        raise ValueError("no comparable level scalars between baseline and current run")
    dev_rose = all(
        current[level].dev.fraction() > baseline[level].dev.fraction()  # type: ignore[union-attr]
        for level in comparable
    )
    held_out_fell = any(
        current[level].held_out.fraction() < baseline[level].held_out.fraction()  # type: ignore[union-attr]
        for level in comparable
    )
    accepted = dev_rose and not held_out_fell
    if accepted:
        reason = REASON_ACCEPTED
    elif not dev_rose and held_out_fell:
        reason = REASON_REJECTED_BOTH
    elif not dev_rose:
        reason = REASON_REJECTED_DEV
    else:
        reason = REASON_REJECTED_HELD_OUT
    return NoRegret(
        accepted=accepted,
        dev_rose=dev_rose,
        held_out_fell=held_out_fell,
        reason=reason,
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
