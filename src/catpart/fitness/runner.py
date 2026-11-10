"""The fitness runner: one run = one report plus one history row.

Implements the fitness protocol of ADR-0001 for ticket #14. Per run,
``catpart-fitness``:

1. reads the corpus manifest — the corpus registry, one row per unique
   file with its SHA-256 (``manifests/corpus-manifest.csv``);
2. runs ``catpart-inspect`` in-process (:func:`catpart.cli.build_inspect_report`,
   not a subprocess) over the files available on disk and classifies
   each file: ``clean`` / ``schema-invalid`` (validated against the
   committed inspect schema — ``v1.json``, additively extended by
   ticket #25 — through :mod:`catpart.schema.validate`, the single
   validation authority, not a fork) / ``crash`` (inspect raised,
   including the documented file-level refusals such as a truncated
   header) / ``missing-invariant`` (output valid but a minimal
   invariant fails, :mod:`catpart.fitness.invariants`). Manifest rows
   whose file is not on disk are ``unavailable``: never parsed, and
   counted as not clean;
3. aggregates the clean-parse scalar per split — L1's fitness is "the
   share of the Corpus that is a Clean parse" (GLOSSARY), so the
   denominator is the manifest rows of the split. The manifest's
   ``split`` column encodes the ADR-0001 author-grouped split (dev =
   all repos except Motor-V6, held-out = Motor-V6); the runner consumes
   it as-is and fails closed on any other value, keeping the grouping in
   one place (the manifest) instead of forking it into code;
4. measures the L2 geometry-sanity scalar per split over the manifest's
   ``kind=part`` rows (ticket #33; products are excluded — the
   documented negative, 0/37 sampled products carry any geometry store)
   through the G4 export seam (:func:`catpart.geometry.build_export`,
   in-process): L2 pass = export success plus the sanity gate (non-empty
   mesh, manifold, finite plausible bounding box, degenerate triangles
   at or below the G3 F7 threshold). Failures carry the exporter's
   machine-readable ``error_class``; the per-part ``l2`` records and the
   per-split component signals (closed-volume-where-expected, degenerate
   counts, open shells) go into the run report, never collapsed into
   the headline scalar;
5. writes the full report to ``fitness/reports/<run_id>.json`` — per
   ADR-0001 the committed history is ``fitness/history.jsonl`` plus a
   report per run;
6. appends exactly one row — accepted or rejected — to the committed
   append-only ``fitness/history.jsonl``, including the corpus digest:
   the SHA-256 of the manifest file bytes (the manifest binds the
   corpus: per-file digests included; re-verifying every binary on each
   run would re-hash ~3.4 GB per run for no extra protection the
   manifest does not already record);
7. decides acceptance with the no-regret rule against the last accepted
   row (ADR-0001, extended by ticket #33: L1 Dev rises AND Held-out
   does not fall; L2 does not fall on either split; at least one
   comparable level's Dev rises). A first run, a run whose baseline row
   carries a different corpus digest, or a run whose baseline predates
   the L2 scalar, has no valid baseline and is accepted as the new
   baseline with the comparison recorded as void.

The corpus itself is measured only on the machine holding ``corpus/``
(ADR-0003); the test suite runs on synthetic fixtures without it.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import tempfile
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

from catpart.cli import build_inspect_report
from catpart.fitness import FitnessError
from catpart.fitness.history import (
    LEVELS,
    REASON_BASELINE_CORPUS_CHANGED,
    REASON_BASELINE_FIRST,
    REASON_BASELINE_NO_L2,
    REASON_REJECTED_BOTH,
    REASON_REJECTED_HELD_OUT,
    REASON_REJECTED_L1_DEV,
    LevelScore,
    NoRegret,
    PartScore,
    SplitScore,
    append_row,
    evaluate_no_regret,
    level_scores_from_json,
    level_scores_to_json,
    load_last_accepted_row,
)
from catpart.fitness.invariants import check_invariants
from catpart.geometry import ExportError, build_export
from catpart.geometry.export import WARN_NO_FACETS, WARN_OPEN_SHELL
from catpart.schema import load_schema
from catpart.schema.validate import SchemaError, ValidationError, validate

#: Manifest split values (ADR-0001 author-grouped split as encoded by
#: the Phase 0 manifest: held-out is the Motor-V6 repo).
SPLITS: tuple[str, str] = ("dev", "held-out")

#: Manifest kind values (container kind law K1). The L2 population is
#: the kind=part rows; products are excluded — the documented negative
#: (docs/evidence/2026-11-08-geometry-payloads.md): 0/37 sampled products
#: carry any geometry store, so an export share over products would
#: measure nothing.
MANIFEST_KINDS: tuple[str, str] = ("part", "product")
L2_POPULATION_KIND = "part"

#: Per-file classification vocabulary (ticket #14; ``unavailable`` marks
#: manifest rows whose file is not on disk and is therefore never parsed).
CLASS_CLEAN = "clean"
CLASS_SCHEMA_INVALID = "schema-invalid"
CLASS_CRASH = "crash"
CLASS_MISSING_INVARIANT = "missing-invariant"
CLASS_UNAVAILABLE = "unavailable"
CLASSIFICATIONS: tuple[str, ...] = (
    CLASS_CLEAN,
    CLASS_SCHEMA_INVALID,
    CLASS_CRASH,
    CLASS_MISSING_INVARIANT,
    CLASS_UNAVAILABLE,
)

#: Manifest columns the runner consumes; extra columns are ignored.
#: ``kind`` gates the L2 population (ticket #33).
REQUIRED_COLUMNS = ("sha256", "kind", "split", "path", "local_path")

INSPECT_SCHEMA = load_schema("v1")
REPORT_SCHEMA = load_schema("fitness-report-v0")
ROW_SCHEMA = load_schema("fitness-history-row-v0")

#: The catpart-inspect contract version the run validates against, taken
#: from the committed schema itself (single authority). It rides on every
#: report and history row additively (Spec C: "the schema version is part
#: of every output document and every history row"); the artifacts' own
#: ``schema_version`` keeps naming their shape (fitness-*-v0).
INSPECT_SCHEMA_VERSION = INSPECT_SCHEMA["properties"]["schema_version"]["const"]

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

#: Aggregation counters: the classification vocabulary itself, in order.
_COUNTERS = CLASSIFICATIONS


def _corpus_digest(manifest_path: Path) -> str:
    """SHA-256 of the manifest bytes — the recorded corpus digest."""
    digest = hashlib.sha256()
    with manifest_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_manifest(manifest_path: Path) -> list[dict[str, str]]:
    """Read and validate the manifest, returning the rows the runner needs.

    Fails closed on: unreadable file, missing required columns, a
    malformed SHA-256, an unknown split value, an unknown kind value
    (the L2 population is defined by the kind column, so an unexpected
    value must stop the run instead of silently leaving the population),
    empty path fields, or a duplicated SHA-256 (a duplicated row would
    double-count in the rate denominator).
    """
    try:
        with manifest_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            fieldnames = reader.fieldnames
            if fieldnames is None:
                raise FitnessError(f"{manifest_path}: manifest has no header row")
            missing = [name for name in REQUIRED_COLUMNS if name not in fieldnames]
            if missing:
                raise FitnessError(
                    f"{manifest_path}: manifest is missing required columns: "
                    + ", ".join(missing)
                )
            rows: list[dict[str, str]] = []
            seen: dict[str, int] = {}
            for index, row in enumerate(reader, start=2):
                where = f"{manifest_path}: row {index}"
                sha256 = (row.get("sha256") or "").strip()
                kind = (row.get("kind") or "").strip()
                split = (row.get("split") or "").strip()
                path = (row.get("path") or "").strip()
                local_path = (row.get("local_path") or "").strip()
                if not _SHA256_RE.fullmatch(sha256):
                    raise FitnessError(f"{where}: sha256 {sha256!r} is not 64 lowercase hex digits")
                if kind not in MANIFEST_KINDS:
                    raise FitnessError(
                        f"{where}: unknown kind {kind!r} (expected one of "
                        f"{', '.join(MANIFEST_KINDS)})"
                    )
                if split not in SPLITS:
                    raise FitnessError(
                        f"{where}: unknown split {split!r} (expected one of {', '.join(SPLITS)})"
                    )
                if not path or not local_path:
                    raise FitnessError(f"{where}: empty 'path' or 'local_path'")
                if sha256 in seen:
                    raise FitnessError(
                        f"{where}: duplicate sha256 (first seen on row {seen[sha256]})"
                    )
                seen[sha256] = index
                rows.append(
                    {
                        "sha256": sha256,
                        "kind": kind,
                        "split": split,
                        "path": path,
                        "local_path": local_path,
                    }
                )
    except csv.Error as exc:
        raise FitnessError(f"{manifest_path}: malformed CSV: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise FitnessError(f"{manifest_path}: manifest is not valid UTF-8: {exc}") from exc
    except OSError as exc:
        raise FitnessError(f"cannot read corpus manifest: {exc}") from exc
    if not rows:
        raise FitnessError(f"{manifest_path}: manifest has no data rows")
    return rows


def _classify_file(file_path: Path) -> tuple[str, str | None, dict | None]:
    """Run the in-process ``catpart-inspect`` seam and classify the outcome.

    Returns ``(classification, error, inspect_output)``. ``crash``
    covers every exception raised while producing the output — the
    documented file-level refusals (``OSError`` for unreadable files,
    ``ValueError`` for files smaller than the 32-byte header) as well as
    unexpected parser exceptions; the exception type name is preserved
    in the error string so a parser bug is distinguishable from a bad
    file. One broken file must never abort the run over the corpus.
    """
    try:
        report = build_inspect_report(file_path)
    except Exception as exc:  # noqa: BLE001 - classification boundary, see docstring
        return CLASS_CRASH, f"{type(exc).__name__}: {exc}", None
    try:
        validate(report, INSPECT_SCHEMA)
    except ValidationError as exc:
        return CLASS_SCHEMA_INVALID, str(exc), report
    except SchemaError as exc:
        raise FitnessError(f"the committed inspect schema is invalid: {exc}") from exc
    failure = check_invariants(report)
    if failure is not None:
        return CLASS_MISSING_INVARIANT, failure, report
    return CLASS_CLEAN, None, report


def _empty_counters() -> dict[str, int]:
    return {name: 0 for name in _COUNTERS}


#: L2 per-part statuses (ticket #33). ``unavailable`` marks part rows
#: whose file is not on disk: never exported, counted as not pass.
L2_PASS = "pass"
L2_FAIL = "fail"
L2_UNAVAILABLE = "unavailable"

#: The L2 sanity gate's failed-check vocabulary (ticket #33): the post-
#: export checks, in gate order. ``MAX_DEGENERATE_TRIANGLES`` pins the
#: degenerate threshold at the G3 F7 rate (0 on every clean-store soup),
#: so any skipped degenerate triangle is anomalous.
MAX_DEGENERATE_TRIANGLES = 0
CHECK_EMPTY_MESH = "empty-mesh"
CHECK_NOT_MANIFOLD = "not-manifold"
CHECK_NONFINITE_BBOX = "nonfinite-bbox"
CHECK_DEGENERATE = "degenerate-triangles"

#: error_class recorded when the export seam raises outside its
#: :class:`ExportError` contract (an exporter bug); the exception type
#: is preserved in the error string, mirroring the L1 crash
#: classification.
L2_EXPORT_CRASH = "export-crash"


def _l2_failure(error_class: str | None, error: str | None) -> dict:
    """A failed (or unmeasurable) part's ``l2`` record: no summary data."""
    return {
        "status": L2_FAIL,
        "error_class": error_class,
        "error": error,
        "failed_check": None,
        "vertex_count": None,
        "triangle_count": None,
        "degenerate_triangle_count": None,
        "mesh": None,
        "bounding_box": None,
        "warnings": None,
    }


def _l2_unavailable(detail: str) -> dict:
    record = _l2_failure(None, detail)
    record["status"] = L2_UNAVAILABLE
    return record


def _bbox_plausible(bbox: dict) -> bool:
    """Finite bounds with min <= max on every axis (the "plausible" part
    of the L2 bounding-box check)."""
    lo, hi = bbox["min"], bbox["max"]
    return all(math.isfinite(v) for v in (*lo, *hi)) and all(
        lo[axis] <= hi[axis] for axis in range(3)
    )


def _score_export(summary: dict) -> dict:
    """Score a successful export against the L2 sanity gate (ticket #33).

    The gate: non-empty mesh, manifold, finite plausible bounding box,
    degenerate triangles at or below :data:`MAX_DEGENERATE_TRIANGLES`.
    The first failed check is recorded as ``failed_check``; every
    summary component is reported either way (mesh invariants including
    closed-volume-where-expected, degenerate counts, open shells) and
    never collapses into the pass/fail headline. A bounding box that
    fails the plausibility check is recorded as null: non-finite floats
    must not reach the committed report.
    """
    mesh = summary["mesh"]
    bbox = summary["bounding_box"]
    if summary["vertex_count"] < 1 or summary["triangle_count"] < 1:
        failed_check = CHECK_EMPTY_MESH
    elif not mesh["manifold"]:
        failed_check = CHECK_NOT_MANIFOLD
    elif not _bbox_plausible(bbox):
        failed_check = CHECK_NONFINITE_BBOX
    elif summary["degenerate_triangle_count"] > MAX_DEGENERATE_TRIANGLES:
        failed_check = CHECK_DEGENERATE
    else:
        failed_check = None
    return {
        "status": L2_PASS if failed_check is None else L2_FAIL,
        "error_class": None,
        "error": None,
        "failed_check": failed_check,
        "vertex_count": summary["vertex_count"],
        "triangle_count": summary["triangle_count"],
        "degenerate_triangle_count": summary["degenerate_triangle_count"],
        "mesh": {
            "manifold": mesh["manifold"],
            "closed": mesh["closed"],
            "oriented": mesh["oriented"],
            "boundary_edge_count": mesh["boundary_edge_count"],
        },
        "bounding_box": bbox if _bbox_plausible(bbox) else None,
        "warnings": summary["warnings"],
    }


def _measure_l2(file_path: Path, out_path: Path) -> dict:
    """Export one part through the G4 seam and score the L2 sanity gate.

    Returns the per-part ``l2`` record of the run report. Export failures
    carry the exporter's machine-readable ``error_class`` (ticket #32);
    an exception outside that contract is recorded as
    :data:`L2_EXPORT_CRASH` with the type preserved, mirroring the L1
    crash classification — one broken file must never abort the run. A
    returned summary is consumed as-is: the exporter self-checks it
    against the committed export-summary-v1 schema before returning, so
    a shape violation there is an exporter bug, not a per-file
    classification.
    """
    try:
        summary = build_export(file_path, out_path)
    except ExportError as exc:
        return _l2_failure(exc.error_class, exc.detail)
    except Exception as exc:  # noqa: BLE001 - classification boundary, see docstring
        return _l2_failure(L2_EXPORT_CRASH, f"{type(exc).__name__}: {exc}")
    return _score_export(summary)


def _l2_split_block(l2_records: list[dict]) -> dict:
    """The ``l2`` detail block of one split's aggregate (ticket #33).

    Population, verdict counts, failure histograms and component signals
    (closed-volume-where-expected, open shells, degenerate-triangle
    totals, vertices-only exports) — reported per split, never collapsed
    into the headline scalar. ``rate`` is null when the split has no
    part rows: nothing measurable (the headline ``scalars.L2`` is null
    with it).
    """
    total = len(l2_records)
    passed = sum(1 for record in l2_records if record["status"] == L2_PASS)
    unavailable = sum(1 for record in l2_records if record["status"] == L2_UNAVAILABLE)
    failed = [record for record in l2_records if record["status"] == L2_FAIL]
    error_classes: dict[str, int] = {}
    failed_checks: dict[str, int] = {}
    for record in failed:
        if record["error_class"] is not None:
            error_classes[record["error_class"]] = (
                error_classes.get(record["error_class"], 0) + 1
            )
        if record["failed_check"] is not None:
            failed_checks[record["failed_check"]] = (
                failed_checks.get(record["failed_check"], 0) + 1
            )
    summaries = [record for record in l2_records if record["mesh"] is not None]
    return {
        "parts": total,
        "pass": passed,
        "fail": len(failed),
        "unavailable": unavailable,
        "rate": passed / total if total else None,
        "error_classes": error_classes,
        "failed_checks": failed_checks,
        "components": {
            "closed": sum(1 for record in summaries if record["mesh"]["closed"]),
            "open_shell": sum(
                1
                for record in summaries
                if any(w["class"] == WARN_OPEN_SHELL for w in record["warnings"])
            ),
            "degenerate_triangles": sum(
                record["degenerate_triangle_count"] or 0 for record in l2_records
            ),
            "vertices_only": sum(
                1
                for record in summaries
                if any(w["class"] == WARN_NO_FACETS for w in record["warnings"])
            ),
        },
    }


def _aggregate(
    results: list[tuple[dict[str, str], str, str | None, dict | None, dict | None]],
) -> tuple[dict, dict, dict[str, LevelScore | None]]:
    """Aggregate classifications into per-split counters, totals and scalars.

    The rate denominator per split is its manifest row count ("share of
    the Corpus", GLOSSARY), so ``unavailable`` rows count as not clean.
    A split with no manifest rows fails closed: without it the no-regret
    comparison is meaningless. The L2 detail blocks aggregate the
    kind=part population of each split (ticket #33); the L2 headline
    scalar exists only when both splits have part rows.
    """
    splits: dict[str, dict] = {}
    for split in SPLITS:
        rows = [row for row, _, _, _, _ in results if row["split"] == split]
        if not rows:
            raise FitnessError(f"split {split!r} has no manifest rows; cannot compute a rate")
        counters = _empty_counters()
        for row, classification, _, _, _ in results:
            if row["split"] == split:
                counters[classification] += 1
        splits[split] = {
            "files": len(rows),
            "available": len(rows) - counters[CLASS_UNAVAILABLE],
            "unavailable": counters[CLASS_UNAVAILABLE],
            "clean": counters[CLASS_CLEAN],
            "schema-invalid": counters[CLASS_SCHEMA_INVALID],
            "crash": counters[CLASS_CRASH],
            "missing-invariant": counters[CLASS_MISSING_INVARIANT],
            "rate": counters[CLASS_CLEAN] / len(rows),
            "l2": _l2_split_block(
                [
                    l2
                    for row, _, _, _, l2 in results
                    if row["split"] == split and row["kind"] == L2_POPULATION_KIND
                ]
            ),
        }
    totals = _empty_counters()
    totals["files"] = sum(splits[split]["files"] for split in SPLITS)
    totals["available"] = sum(splits[split]["available"] for split in SPLITS)
    for split in SPLITS:
        for name in _COUNTERS:
            totals[name] += splits[split][name]
    for split in SPLITS:
        counted = sum(splits[split][name] for name in _COUNTERS)
        if counted != splits[split]["files"]:  # pragma: no cover - internal bug guard
            raise RuntimeError(f"internal error: split {split!r} counters do not sum to files")
    level_scores: dict[str, LevelScore | None] = {level: None for level in LEVELS}
    level_scores["L1"] = LevelScore(
        dev=SplitScore(clean=splits["dev"]["clean"], total=splits["dev"]["files"]),
        held_out=SplitScore(
            clean=splits["held-out"]["clean"], total=splits["held-out"]["files"]
        ),
    )
    dev_l2, ho_l2 = splits["dev"]["l2"], splits["held-out"]["l2"]
    if dev_l2["parts"] > 0 and ho_l2["parts"] > 0:
        level_scores["L2"] = LevelScore(
            dev=PartScore(passed=dev_l2["pass"], total=dev_l2["parts"]),
            held_out=PartScore(passed=ho_l2["pass"], total=ho_l2["parts"]),
        )
    return splits, totals, level_scores


def _per_file_record(
    row: dict[str, str],
    classification: str,
    error: str | None,
    output: dict | None,
    l2: dict | None,
) -> dict:
    # Schema-invalid output may be missing any field, so inspect-derived
    # values use .get() and report whatever the parser actually emitted.
    # container_names carries the names at container level: the parsed
    # container-name table records (schema v1 dropped the v0 whole-file
    # string scan), unique, in first-occurrence order.
    containers = None if output is None else output.get("containers")
    container_names: list[str] | None = None
    if containers is not None:
        container_names = []
        for record in containers:
            name = record.get("name") if isinstance(record, dict) else None
            if name is not None and name not in container_names:
                container_names.append(name)
    return {
        "sha256": row["sha256"],
        "path": row["path"],
        "split": row["split"],
        "classification": classification,
        "detected_version": None if output is None else output.get("detected_version"),
        "kind": None if output is None else output.get("kind"),
        "container_names": container_names,
        "l2": l2,
        "error": error,
    }


def _tool_version() -> str:
    try:
        return metadata.version("catpart-parser")
    except metadata.PackageNotFoundError:
        return "0+unknown"


def _run_id(instant: datetime) -> str:
    """UTC timestamp plus six hex characters — unique per run, sortable."""
    return instant.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]


def _timestamp(instant: datetime) -> str:
    return instant.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_artifact(artifact: dict, schema: dict, name: str) -> None:
    """Self-check an artifact against its committed schema before writing."""
    try:
        validate(artifact, schema)
    except (ValidationError, SchemaError) as exc:
        raise FitnessError(f"internal error: emitted {name} violates its schema: {exc}") from exc


def _write_report(path: Path, report: dict) -> None:
    """Write the report JSON: indented head, one compact line per file.

    Keeping every per-file record on its own line makes the committed
    reports greppable by digest and diffable between runs; the file as a
    whole is ordinary JSON and round-trips to the in-memory report.
    """
    files = report["files"]
    head = {key: value for key, value in report.items() if key != "files"}
    head_text = json.dumps(head, indent=2)
    assert head_text.endswith("}")
    if files:
        items = ",\n".join(
            "    " + json.dumps(record, separators=(",", ": ")) for record in files
        )
        body = head_text[:-1] + ',\n  "files": [\n' + items + "\n  ]\n}\n"
    else:
        body = head_text[:-1] + ',\n  "files": []\n}\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n" keeps the committed artifacts at LF endings on every platform.
    path.write_text(body, encoding="utf-8", newline="\n")


def run_fitness(
    manifest_path: Path,
    *,
    corpus_root: Path | None = None,
    fitness_dir: Path | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict:
    """Run the fitness protocol over ``manifest_path`` and return the history row.

    Paths: the manifest lives in ``<repo>/manifests/``, so the repository
    root is the manifest's grandparent directory; ``corpus_root`` (where
    the manifest's ``local_path`` entries resolve against) defaults to
    it, and ``fitness_dir`` (holding ``history.jsonl`` and ``reports/``)
    defaults to ``<repo>/fitness``. ``corpus_root`` can point elsewhere
    for a corpus stored off-repository; the history stays in the repo.

    ``now`` injects the clock for tests; it defaults to
    :func:`datetime.now`. Returns the appended history row (also the
    console script's stdout JSON). Raises :class:`FitnessError` on every
    operator-facing failure; the run's acceptance verdict is data on the
    row, never a raised error.
    """
    manifest_path = Path(manifest_path)
    repo_root = manifest_path.resolve().parent.parent
    corpus_root = Path(corpus_root) if corpus_root is not None else repo_root
    fitness_dir = Path(fitness_dir) if fitness_dir is not None else repo_root / "fitness"
    clock = now if now is not None else datetime.now

    rows = _read_manifest(manifest_path)
    corpus_digest = _corpus_digest(manifest_path)

    results: list[tuple[dict[str, str], str, str | None, dict | None, dict | None]] = []
    # The exports' PLY output is a side effect of the seam contract; it is
    # written to a run-scoped scratch directory and discarded with it.
    with tempfile.TemporaryDirectory(prefix="catpart-fitness-l2-") as scratch:
        scratch_dir = Path(scratch)
        for row in rows:
            file_path = corpus_root / row["local_path"]
            if file_path.is_file():
                classification, error, output = _classify_file(file_path)
                l2 = (
                    _measure_l2(file_path, scratch_dir / f"{row['sha256'][:16]}.ply")
                    if row["kind"] == L2_POPULATION_KIND
                    else None
                )
            else:
                classification, error, output = (
                    CLASS_UNAVAILABLE,
                    f"missing on disk: {row['local_path']}",
                    None,
                )
                l2 = (
                    _l2_unavailable(f"missing on disk: {row['local_path']}")
                    if row["kind"] == L2_POPULATION_KIND
                    else None
                )
            results.append((row, classification, error, output, l2))

    splits, totals, level_scores = _aggregate(results)

    baseline = load_last_accepted_row(fitness_dir / "history.jsonl")
    if baseline is None:
        accepted = True
        baseline_run_id = None
        no_regret = NoRegret(True, None, None, REASON_BASELINE_FIRST)
    elif baseline["corpus_digest"] != corpus_digest:
        accepted = True
        baseline_run_id = baseline["run_id"]
        no_regret = NoRegret(True, None, None, REASON_BASELINE_CORPUS_CHANGED)
    else:
        baseline_scores = level_scores_from_json(baseline["scalars"], "baseline row scalars")
        if baseline_scores.get("L2") is None and level_scores.get("L2") is not None:
            # The first L2-bearing run against a pre-G5 baseline has no L2
            # baseline: L2 is ungated, but L1 IS comparable (same corpus
            # digest, same scalar) and stays protected — an L1 regression
            # must not ride the L2 baseline transition into the append-only
            # accepted history. This is NOT the corpus-change precedent:
            # there the digest itself differs and no level is comparable.
            # Flat L1 + the first L2 scalar is the expected transition and
            # is accepted (review of #33, 2026-11-10).
            l1_base, l1_cur = baseline_scores["L1"], level_scores["L1"]
            if l1_base is None or l1_cur is None:  # defensive; L1 always exists
                raise FitnessError("cannot evaluate the no-regret rule: L1 scalar missing")
            dev_fell = l1_cur.dev.fraction() < l1_base.dev.fraction()
            ho_fell = l1_cur.held_out.fraction() < l1_base.held_out.fraction()
            accepted = not dev_fell and not ho_fell
            if dev_fell and ho_fell:
                reason = REASON_REJECTED_BOTH
            elif ho_fell:
                reason = REASON_REJECTED_HELD_OUT
            elif dev_fell:
                reason = REASON_REJECTED_L1_DEV
            else:
                reason = REASON_BASELINE_NO_L2
            baseline_run_id = baseline["run_id"]
            no_regret = NoRegret(
                accepted=accepted,
                dev_rose=l1_cur.dev.fraction() > l1_base.dev.fraction(),
                held_out_fell=ho_fell,
                reason=reason,
                # l2_* stay None: L2 was not comparable.
            )
        else:
            try:
                verdict = evaluate_no_regret(baseline_scores, level_scores)
            except ValueError as exc:
                raise FitnessError(f"cannot evaluate the no-regret rule: {exc}") from exc
            accepted = verdict.accepted
            baseline_run_id = baseline["run_id"]
            no_regret = verdict

    instant = clock()
    scalars_json = level_scores_to_json(level_scores)
    report = {
        "schema_version": 0,
        "inspect_schema_version": INSPECT_SCHEMA_VERSION,
        "run_id": _run_id(instant),
        "timestamp": _timestamp(instant),
        "tool_version": _tool_version(),
        "manifest_path": str(manifest_path),
        "corpus_digest": corpus_digest,
        "splits": splits,
        "totals": totals,
        "scalars": scalars_json,
        "accepted": accepted,
        "baseline_run_id": baseline_run_id,
        "no_regret": no_regret.to_json(),
        "files": [_per_file_record(row, c, err, out, l2) for row, c, err, out, l2 in results],
    }
    history_row = {
        "schema_version": 0,
        "inspect_schema_version": INSPECT_SCHEMA_VERSION,
        "run_id": report["run_id"],
        "timestamp": report["timestamp"],
        "tool_version": report["tool_version"],
        "corpus_digest": corpus_digest,
        "accepted": accepted,
        "baseline_run_id": baseline_run_id,
        "no_regret": no_regret.to_json(),
        "scalars": scalars_json,
        "report": f"reports/{report['run_id']}.json",
    }

    _validate_artifact(report, REPORT_SCHEMA, "fitness-report-v0 report")
    _validate_artifact(history_row, ROW_SCHEMA, "history row")
    try:
        _write_report(fitness_dir / "reports" / f"{report['run_id']}.json", report)
        append_row(fitness_dir / "history.jsonl", history_row)
    except OSError as exc:
        raise FitnessError(f"cannot write fitness artifacts: {exc}") from exc
    return history_row
