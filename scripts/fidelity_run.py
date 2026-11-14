#!/usr/bin/env python3
"""The Fidelity harness (spec ``docs/specs/phase5-viewer-spec.md`` §4, V1
ticket #40): prove Port ≡ Python over one diff implementation, dual-mode.

- **Fixture mode** (``--fixtures``): generates the A2 synthetic fixtures
  via ``tests/fixtures_gen.py`` in-process, runs both implementations
  over them, diffs — wired into the gate as ``tests/test_port_fidelity.py``.
  This is how "CI covers the port with the synthetic fixtures from A2"
  is satisfied with one harness: the same diff code proves parity in CI
  on fixtures and locally on the corpus.

- **Corpus mode** (default, local-only per ADR-0003): walks
  ``manifests/corpus-manifest.csv``, applies the slice populations
  (§3.1 — the L1-JSON slice is ALL manifest rows, junk included), and
  drives the Python reference (``catpart-inspect``) and the Rust port
  (``port/target/release/fidelity_cli``, built once per run by
  ``cargo build --release``) as subprocesses — the exact shipped seams,
  no in-process imports, one shape for both.

Diff definition (§3.2, L1 slice): the inspect document is compared by
parsed-document equality — recursive structural equality, object key
sets equal, arrays equal in order, numbers equal with the int/float
distinction preserved. A failed run is compared by ``error_class``
string equality: the Python side's exit 1 on the shipped seam is the
fitness class ``crash`` (``runner._classify_file`` maps every inspect
exception there; the A2 fixture table pins short-file → crash), and the
port's stderr JSON line carries the same single-class L1 vocabulary
(see ``port/src/bin/fidelity_cli.rs``). ``detail`` is never compared
byte-wise. Any harness-level failure (timeout, missing binary, unreadable
output) is recorded as its own outcome class and NEVER counts as a
match — the run is invalid until every row is match/mismatch/
error-class-mismatch by evidence.

Outputs (§4): a dated evidence note (figures only; every figure
CSV-composable, #37) + a per-file CSV under ``docs/evidence/data/`` —
named to match the ``*claims*.csv`` glob so the mechanical hygiene
checker (``scripts/triage/check_claims_csv_quoting.py``) covers it from
birth. The CSV column 0 is the row key (``sha256`` / fixture id),
non-empty and unshifted.

Runtime budget (§4, design target): per-ticket sample runs ≤ 15 min at
N=100; the full dual-slice run ≤ 2 h. The wall-clock is measured and
recorded per run, never estimated.

Stdlib-only (the ``publish_fitness.py`` convention for local tools);
the one repo import is ``tests/fixtures_gen.py`` in fixture mode, by
file path, for the in-process fixture generation §4 pins.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "manifests" / "corpus-manifest.csv"
FITNESS_DIR = REPO_ROOT / "fitness"
DATA_DIR = REPO_ROOT / "docs" / "evidence" / "data"

#: The L1 slice's single error class (see the module docstring and
#: ``port/src/bin/fidelity_cli.rs``): the Python side's exit 1 on the
#: shipped inspect seam is the fitness class ``crash``.
L1_PYTHON_ERROR_CLASS = "crash"

#: Outcome vocabulary (§4).
OUTCOME_MATCH = "match"
OUTCOME_OUTPUT_MISMATCH = "output-mismatch"
OUTCOME_CLASS_MISMATCH = "error-class-mismatch"
OUTCOME_HARNESS_ERROR = "harness-error"

CSV_COLUMNS = (
    "row_id",
    "path",
    "split",
    "kind",
    "magic_ok",
    "detected_version",
    "export_outcome_class",
    "python_exit",
    "port_exit",
    "outcome",
    "python_error_class",
    "port_error_class",
    "ply_equal",
    "first_divergence",
    "python_seconds",
    "port_seconds",
)

SLICE_L1 = "l1"
SLICE_L2 = "l2"
SLICE_BOTH = "both"


# --- seam resolution -----------------------------------------------------


def resolve_python_inspect() -> str:
    """Locate the shipped ``catpart-inspect`` console script.

    Order: the ``FIDELITY_PY_INSPECT`` override, the console script
    next to the running interpreter (the venv layout both the gate and
    the corpus machine use), then ``PATH``.
    """
    override = os.environ.get("FIDELITY_PY_INSPECT")
    if override:
        return override
    adjacent = Path(sys.executable).parent / "catpart-inspect"
    if adjacent.is_file():
        return str(adjacent)
    found = shutil.which("catpart-inspect")
    if found:
        return found
    raise SystemExit(
        "fidelity_run: cannot find the catpart-inspect console script "
        "(set FIDELITY_PY_INSPECT or install the package: "
        "python -m venv .venv && .venv/bin/pip install -e '.[test,lint]')"
    )


def build_port_bin() -> Path:
    """Build the release ``fidelity-cli`` once per run (§4) and return it.

    Runs ``cargo build --release --locked`` inside ``port/``; the run
    aborts if the build fails or the binary is missing or stale (older
    than the newest crate source). Cargo names the artifact
    ``fidelity_cli`` (underscores); the harness resolves both spellings.
    """
    port_dir = REPO_ROOT / "port"
    cargo = shutil.which("cargo")
    if cargo is None:
        raise SystemExit(
            "fidelity_run: cargo not found — from V0 the Rust toolchain "
            "is a required dev dependency (spec §7); install rustup, then "
            "run 'rustup toolchain install' inside port/"
        )
    build = subprocess.run(
        [cargo, "build", "--release", "--locked"],
        cwd=port_dir,
        capture_output=True,
        text=True,
    )
    if build.returncode != 0:
        sys.stderr.write(build.stdout)
        sys.stderr.write(build.stderr)
        raise SystemExit("fidelity_run: cargo build --release failed")
    for name in ("fidelity-cli", "fidelity_cli"):
        candidate = port_dir / "target" / "release" / name
        if candidate.is_file():
            newest_source = newest_mtime(port_dir / "src", port_dir / "Cargo.toml", port_dir / "Cargo.lock")
            if newest_source is not None and candidate.stat().st_mtime < newest_source:
                raise SystemExit(
                    "fidelity_run: the release fidelity-cli binary is stale "
                    "relative to port/src — rebuild before running the harness"
                )
            return candidate
    raise SystemExit("fidelity_run: cargo build reported success but the fidelity-cli binary is missing")


def newest_mtime(*paths: Path) -> float | None:
    """Newest mtime over ``paths`` (directories walked for ``*.rs``)."""
    newest: float | None = None
    for path in paths:
        if path.is_dir():
            for source in path.rglob("*.rs"):
                newest = max(newest or 0.0, source.stat().st_mtime)
        elif path.is_file():
            newest = max(newest or 0.0, path.stat().st_mtime)
    return newest


# --- subprocess shape (one shape for both implementations) ----------------


class SeamResult:
    """One subprocess run of one implementation over one file."""

    def __init__(self, side: str, exit_code: int | None, stdout: bytes, stderr: bytes, seconds: float, timed_out: bool):
        self.side = side
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.seconds = seconds
        self.timed_out = timed_out

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    @property
    def failed(self) -> bool:
        return self.exit_code == 1


def run_seam(command: list[str], path: str, timeout: float) -> SeamResult:
    """Run one implementation over ``path`` with the shared shape.

    The subprocess gets the file path as its only argument and must
    answer with the inspect document on stdout (exit 0) or a failure
    (exit 1); anything else is a harness-level failure (§3.2).
    """
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command + [path],
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return SeamResult(command[0], None, b"", b"", time.monotonic() - started, True)
    except OSError as exc:
        # The seam itself could not be executed (missing binary).
        detail = json.dumps({"harness": f"cannot execute {command[0]}: {exc}"})
        return SeamResult(command[0], -2, b"", detail.encode(), time.monotonic() - started, False)
    return SeamResult(
        command[0], proc.returncode, proc.stdout, proc.stderr, time.monotonic() - started, False
    )


# --- §3.2 parsed-document equality ---------------------------------------


def first_divergence(py_doc, port_doc, path: str = "$") -> str | None:
    """The first structural divergence between the two parsed documents.

    Object key sets must be equal, arrays equal in order, numbers equal
    with the int/float distinction preserved (``bool`` vs ``int`` too:
    JSON ``true`` parsing to ``True`` must not equal ``1``). Returns a
    human-readable one-line description (``path`` + both values) or
    ``None``.
    """
    if type(py_doc) is not type(port_doc):
        return f"{path}: python={py_doc!r} ({type(py_doc).__name__}) port={port_doc!r} ({type(port_doc).__name__})"
    if isinstance(py_doc, dict):
        only_py = sorted(set(py_doc) - set(port_doc))
        only_port = sorted(set(port_doc) - set(py_doc))
        if only_py or only_port:
            return f"{path}: key-set differs python-only={only_py} port-only={only_port}"
        for key in py_doc:
            found = first_divergence(py_doc[key], port_doc[key], f"{path}.{key}")
            if found is not None:
                return found
        return None
    if isinstance(py_doc, list):
        if len(py_doc) != len(port_doc):
            return f"{path}: list length {len(py_doc)} vs {len(port_doc)}"
        for index, (py_item, port_item) in enumerate(zip(py_doc, port_doc)):
            found = first_divergence(py_item, port_item, f"{path}[{index}]")
            if found is not None:
                return found
        return None
    if py_doc != port_doc:
        return f"{path}: python={py_doc!r} port={port_doc!r}"
    return None


def parse_port_error_class(seam: SeamResult) -> str | None:
    """The ``error_class`` of the port's one-JSON-line stderr failure.

    Returns ``None`` when the line is missing or unparsable — a
    harness-level failure (§3.2: unreadable output), never a class.
    """
    try:
        payload = json.loads(seam.stderr.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("error_class"), str):
        return None
    return payload["error_class"]


def compare_row(py: SeamResult, port: SeamResult, timeout: float) -> tuple[str, str]:
    """Compare one (python, port) seam pair → ``(outcome, first_divergence)``.

    The outcome vocabulary is §4's: match / output-mismatch /
    error-class-mismatch / harness-error; a harness-level failure never
    counts as a match (§3.2).
    """
    if py.timed_out or port.timed_out:
        side = "python" if py.timed_out else "port"
        return OUTCOME_HARNESS_ERROR, f"{side} exceeded the {timeout:g}s timeout"
    if py.exit_code not in (0, 1):
        return OUTCOME_HARNESS_ERROR, f"python exit {py.exit_code} outside the seam contract (0/1): {py.stderr[:200]!r}"
    if port.exit_code not in (0, 1, 2):
        return OUTCOME_HARNESS_ERROR, f"port exit {port.exit_code} outside the seam contract (0/1/2): {port.stderr[:200]!r}"
    if port.exit_code == 2:
        return OUTCOME_HARNESS_ERROR, "port usage error (exit 2) — harness invoked the seam wrongly"
    if py.failed and port.failed:
        port_class = parse_port_error_class(port)
        if port_class is None:
            return OUTCOME_HARNESS_ERROR, f"port stderr is not an error-class JSON line: {port.stderr[:200]!r}"
        if port_class == L1_PYTHON_ERROR_CLASS:
            return OUTCOME_MATCH, ""
        return OUTCOME_CLASS_MISMATCH, f"error_class python={L1_PYTHON_ERROR_CLASS} port={port_class}"
    if py.ok and port.ok:
        try:
            py_doc = json.loads(py.stdout)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return OUTCOME_HARNESS_ERROR, f"python stdout is not JSON: {py.stdout[:200]!r}"
        try:
            port_doc = json.loads(port.stdout)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return OUTCOME_HARNESS_ERROR, f"port stdout is not JSON: {port.stdout[:200]!r}"
        found = first_divergence(py_doc, port_doc)
        if found is None:
            return OUTCOME_MATCH, ""
        return OUTCOME_OUTPUT_MISMATCH, found
    sides = "python produced a document, port failed" if py.ok else "port produced a document, python failed"
    port_class = parse_port_error_class(port) if port.failed else None
    return OUTCOME_OUTPUT_MISMATCH, f"{sides}" + (f" (port error_class={port_class})" if port_class else "")


# --- fixture mode (§4) ----------------------------------------------------


def load_fixtures_gen():
    """Import ``tests/fixtures_gen.py`` by file path (standalone module)."""
    spec = importlib.util.spec_from_file_location(
        "fidelity_fixtures_gen", REPO_ROOT / "tests" / "fixtures_gen.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_matrix() -> list[dict]:
    """The A2 fixture population the gate compares (spec §4 fixture mode).

    - The canonical shape (``variant=None``) and the geometry/composite
      variants sweep seeds 0 and 7 (table padding alignment); their
      payload is a pure function of the variant, so both kinds produce
      identical bytes and one kind is compared.
    - The plain variants (header/trailer/table corruption families)
      sweep seeds 0-2 x kinds part+product: the seed drives GUIDs,
      payload filler and table padding, so each sweep shifts byte
      positions and record alignment.
    - Every variant is additionally compared with the C3 identity block
      present (``document_name``), covering the document_name field on
      each variant family.
    """
    gen = load_fixtures_gen()
    plain = {"dual-region", "bad-magic", "truncated-table", "missing-trailer", "junk-payload", "oversized-dword", "short-file"}
    all_variants = [*gen.VALID_VARIANTS, *gen.CORRUPTED_VARIANTS]  # includes None: the canonical shape
    string_variants = [variant for variant in all_variants if variant is not None]
    plain_valid = plain & set(string_variants)
    geometry = [variant for variant in string_variants if variant not in plain_valid]
    matrix: list[dict] = []
    for seed in (0, 7):
        matrix.append({"kind": "part", "seed": seed, "variant": None})
    for variant in sorted(plain_valid):
        for seed in (0, 1, 2):
            for kind in ("part", "product"):
                matrix.append({"kind": kind, "seed": seed, "variant": variant})
    for variant in geometry:
        for seed in (0, 7):
            matrix.append({"kind": "part", "seed": seed, "variant": variant})
    for variant in sorted(all_variants, key=lambda v: "" if v is None else v):
        matrix.append({
            "kind": "part",
            "seed": 0,
            "variant": variant,
            "document_name": "Doc1.CATPart",
        })
    return matrix


def run_fixture_mode(csv_path: Path, note_path: Path, timeout: float, port_bin: Path | None) -> int:
    """Generate the A2 fixtures in-process, run both seams, diff (§4)."""
    gen = load_fixtures_gen()
    python_cmd = [resolve_python_inspect()]
    port_cmd = [str(port_bin or build_port_bin()), "inspect"]
    fixtures_dir = csv_path.parent / "fidelity-fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    started = time.monotonic()
    for entry in fixture_matrix():
        fixture_id = (
            f"{entry['variant'] or 'canonical'}|k{entry['kind']}|s{entry['seed']}"
            + ("|doc" if entry.get("document_name") else "")
        )
        path = fixtures_dir / f"{_safe_name(fixture_id)}.CATPart"
        path.write_bytes(gen.build_fixture(entry["kind"], seed=entry["seed"], variant=entry["variant"], document_name=entry.get("document_name")))
        py = run_seam(python_cmd, str(path), timeout)
        port = run_seam(port_cmd, str(path), timeout)
        outcome, divergence = compare_row(py, port, timeout)
        rows.append({
            "row_id": fixture_id,
            "path": str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path),
            "split": "fixture",
            "kind": entry["kind"],
            "magic_ok": "",
            "detected_version": "",
            "export_outcome_class": "",
            "python_exit": py.exit_code,
            "port_exit": port.exit_code,
            "outcome": outcome,
            "python_error_class": L1_PYTHON_ERROR_CLASS if py.failed else "",
            "port_error_class": parse_port_error_class(port) or "",
            "ply_equal": "",
            "first_divergence": divergence,
            "python_seconds": f"{py.seconds:.3f}",
            "port_seconds": f"{port.seconds:.3f}",
        })
    shutil.rmtree(fixtures_dir, ignore_errors=True)
    wall_clock = time.monotonic() - started
    write_csv(csv_path, rows)
    write_note(
        note_path,
        run_kind="fixture-mode (A2 fixtures, generated in-process via tests/fixtures_gen.py)",
        population_rows=rows,
        wall_clock=wall_clock,
        csv_path=csv_path,
        slice_note="L1 slice (inspect document equality); the L2 export slice is V2 scope",
    )
    return exit_code_for(rows)


def _safe_name(fixture_id: str) -> str:
    return "".join(char if char.isalnum() or char in "-._" else "_" for char in fixture_id)


# --- corpus mode (§4, local-only per ADR-0003) ----------------------------


def read_manifest() -> list[dict]:
    """Read the corpus manifest rows the slices are defined over."""
    with MANIFEST_PATH.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_accepted_report() -> dict:
    """The accepted run's per-file records (the stratification basis, §4).

    Resolves the latest accepted row of ``fitness/history.jsonl`` to its
    report JSON and fails closed when the report's corpus digest no
    longer matches the manifest bytes (a stale basis must stop the run,
    not silently stratify over a different corpus).
    """
    accepted_row = None
    with (FITNESS_DIR / "history.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("accepted"):
                accepted_row = row
    if accepted_row is None:
        raise SystemExit("fidelity_run: fitness/history.jsonl has no accepted row")
    report_path = FITNESS_DIR / accepted_row["report"]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    if report.get("corpus_digest") != digest:
        raise SystemExit(
            "fidelity_run: the accepted report's corpus_digest does not match "
            f"{MANIFEST_PATH} — a stale stratification basis; re-run "
            "catpart-fitness or sample from the current corpus"
        )
    return report


def export_outcome_class(record: dict) -> str:
    """The per-file export outcome class (the stratification axis, §4).

    The accepted report's L2 record carries the export outcome:
    ``error_class`` when classified, else the status (``pass``/``fail``);
    files the exporter never ran on (products, never-parsed rows) are
    ``not-exported``.
    """
    l2 = record.get("l2")
    if record.get("kind") != "part" or not l2:
        return "not-exported"
    return l2.get("error_class") or l2.get("status") or "not-exported"


def stratified_sample(rows: list[dict], report: dict, count: int) -> list[dict]:
    """Deterministic stratified sample (§4: ``--sample stratified:N``).

    Strata are (detected_version x split x export outcome class) over
    the accepted report's per-file records, joined to the manifest rows
    by sha256. Allocation is round-wise proportional: strata in
    descending size order (ties by stratum key), one seat per stratum
    per round until N seats are placed (largest-remainder behavior
    without float drift) — at N >= stratum count every population cell
    is covered, at smaller N the largest cells fill first. Within a
    stratum the picks are evenly spaced over the sha256-sorted rows —
    no RNG; the same N yields the same sample.
    """
    by_sha = {record["sha256"]: record for record in report["files"]}
    strata: dict[tuple, list[dict]] = {}
    for row in rows:
        record = by_sha.get(row["sha256"])
        if record is None:
            raise SystemExit(f"fidelity_run: manifest sha256 {row['sha256']} is not in the accepted report")
        version = record.get("detected_version") or "unknown"
        strata.setdefault((version, record.get("split") or "unknown", export_outcome_class(record)), []).append(row)
    for members in strata.values():
        members.sort(key=lambda row: row["sha256"])
    ordered = sorted(strata.items(), key=lambda item: item[0])
    if count >= len(rows):
        return [row for _, members in ordered for row in members]
    sizes = [len(members) for _, members in ordered]
    quota = [0] * len(ordered)
    remaining = count
    priority = sorted(range(len(ordered)), key=lambda index: (-sizes[index], ordered[index][0]))
    while remaining > 0:
        gave = False
        for index in priority:
            if remaining == 0:
                break
            if quota[index] < sizes[index]:
                quota[index] += 1
                remaining -= 1
                gave = True
        if not gave:
            break
    sample: list[dict] = []
    for (_, members), n in zip(ordered, quota):
        n = min(n, len(members))
        if n <= 0:
            continue
        if n == 1:
            ranks = [0]
        else:
            # Evenly spaced over the sorted stratum: deterministic,
            # spread over the whole stratum.
            ranks = sorted({round(i * (len(members) - 1) / (n - 1)) for i in range(n)})
            if len(ranks) < n:  # rounding collision: fill by lowest rank
                ranks = sorted(set(range(len(members))) | set(ranks))[:n]
        sample.extend(members[rank] for rank in ranks)
    return sample


def run_corpus_mode(csv_path: Path, note_path: Path, split: str, slice_name: str, sample: tuple[str, int] | None, timeout: float, port_bin: Path | None) -> int:
    """Walk the manifest, apply the slice population, diff both seams."""
    manifest = read_manifest()
    report = load_accepted_report()
    rows = manifest
    if split != "all":
        rows = [row for row in rows if row["split"] == split]
    slice_note = "L1-JSON slice (§3.1: ALL manifest rows — parts, products and the magic_ok=no junk)"
    if sample is not None:
        method, count = sample
        if method != "stratified":
            raise SystemExit(f"fidelity_run: unknown --sample method {method!r} (only stratified:N at V1)")
        # The junk rows are part of the slice's definition (§3.1) and
        # the ticket's acceptance names them explicitly: always include
        # every magic_ok=no row (6 in the current corpus), stratify the
        # remainder. N counts the total sample.
        forced = [row for row in rows if row["magic_ok"] == "no"]
        rest = [row for row in rows if row["magic_ok"] != "no"]
        sampled = stratified_sample(rest, report, max(count - len(forced), 0))
        rows = sorted(forced + sampled, key=lambda row: row["sha256"])
        slice_note += (
            f"; stratified sample N={count} (detected_version x split x export "
            f"outcome class; all {len(forced)} magic_ok=no rows always included)"
        )
    if slice_name == SLICE_L2:
        # V1: geometry is not ported (V0 stubs) — the L2 population
        # compares nothing yet; report slice-empty (§6 V2 owns it).
        write_csv(csv_path, [])
        write_note(
            note_path,
            run_kind="corpus-mode",
            population_rows=[],
            wall_clock=0.0,
            csv_path=csv_path,
            slice_note=(
                "L2-export slice requested (--slice l2): SLICE-EMPTY at V1 — "
                "the geometry modules are V0 stubs and export mode is V2 (#41); no rows compared"
            ),
        )
        print("fidelity_run: --slice l2 is slice-empty at V1 (geometry is not ported; V2, ticket #41)")
        return 0
    if slice_name == SLICE_BOTH:
        # Run the L1 slice now; the note records the L2 slice-empty.
        slice_note += "; --slice both: the L2-export slice is SLICE-EMPTY at V1 (V2, ticket #41)"
    python_cmd = [resolve_python_inspect()]
    port_cmd = [str(port_bin or build_port_bin()), "inspect"]
    by_sha = {record["sha256"]: record for record in report["files"]}
    result_rows: list[dict] = []
    started = time.monotonic()
    for row in rows:
        path = str(REPO_ROOT / row["local_path"])
        record = by_sha[row["sha256"]]
        py = run_seam(python_cmd, path, timeout)
        port = run_seam(port_cmd, path, timeout)
        outcome, divergence = compare_row(py, port, timeout)
        result_rows.append({
            "row_id": row["sha256"],
            "path": row["path"],
            "split": row["split"],
            "kind": row["kind"],
            "magic_ok": row["magic_ok"],
            "detected_version": record.get("detected_version") or "unknown",
            "export_outcome_class": export_outcome_class(record),
            "python_exit": py.exit_code,
            "port_exit": port.exit_code,
            "outcome": outcome,
            "python_error_class": L1_PYTHON_ERROR_CLASS if py.failed else "",
            "port_error_class": parse_port_error_class(port) or "",
            "ply_equal": "",
            "first_divergence": divergence,
            "python_seconds": f"{py.seconds:.3f}",
            "port_seconds": f"{port.seconds:.3f}",
        })
    wall_clock = time.monotonic() - started
    write_csv(csv_path, result_rows)
    write_note(
        note_path,
        run_kind="corpus-mode",
        population_rows=result_rows,
        wall_clock=wall_clock,
        csv_path=csv_path,
        slice_note=slice_note,
    )
    return exit_code_for(result_rows)


# --- outputs (§4) ---------------------------------------------------------


def write_csv(csv_path: Path, rows: list[dict]) -> None:
    """The per-file CSV (column 0 = row key, ``csv.writer`` quoting)."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(CSV_COLUMNS)
        for row in rows:
            writer.writerow([row[column] for column in CSV_COLUMNS])


def write_note(note_path: Path, run_kind: str, population_rows: list[dict], wall_clock: float, csv_path: Path, slice_note: str) -> None:
    """The dated evidence note: figures only, every figure CSV-composable.

    The prose curation around these figures happens before the note is
    committed; the figures themselves are a pure function of the run
    and its CSV rows (#37, prose-traceability).
    """
    note_path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    outcomes = Counter(row["outcome"] for row in population_rows)
    mismatches = outcomes[OUTCOME_OUTPUT_MISMATCH] + outcomes[OUTCOME_CLASS_MISMATCH]
    harness_errors = outcomes[OUTCOME_HARNESS_ERROR]
    lines = [
        f"# Fidelity run — {run_kind}",
        "",
        f"- Run stamp: {stamp} (UTC)",
        f"- Slice: {slice_note}",
        f"- CSV: `{csv_path.relative_to(REPO_ROOT) if csv_path.is_relative_to(REPO_ROOT) else csv_path}` ({len(population_rows)} rows)",
        f"- Wall-clock: {wall_clock:.1f} s (measured, both subprocess passes included)",
        f"- Outcomes: {dict(sorted(outcomes.items())) or '{}'}",
        f"- Mismatches (output-mismatch + error-class-mismatch): {mismatches}",
        f"- Harness-level failures (never matches, §3.2): {harness_errors}",
    ]
    if population_rows:
        by_split = Counter(row["split"] for row in population_rows)
        by_kind = Counter(row["kind"] for row in population_rows)
        by_magic = Counter(row["magic_ok"] or "n/a" for row in population_rows)
        py_total = sum(float(row["python_seconds"]) for row in population_rows)
        port_total = sum(float(row["port_seconds"]) for row in population_rows)
        lines += [
            f"- Population by split: {dict(sorted(by_split.items()))}",
            f"- Population by kind: {dict(sorted(by_kind.items()))}",
            f"- Population by magic_ok: {dict(sorted(by_magic.items()))}",
            f"- Subprocess time totals: python {py_total:.1f} s, port {port_total:.1f} s",
            f"- §4 budget (per-ticket sample runs ≤ 15 min at N=100): "
            f"{'WITHIN' if wall_clock <= 900 else 'EXCEEDED'} at N={len(population_rows)}",
        ]
        diverging = [row for row in population_rows if row["outcome"] != OUTCOME_MATCH]
        if diverging:
            lines += ["", "## Non-match rows (first divergence per row)", ""]
            for row in diverging:
                detail = row["first_divergence"][:220]
                lines.append(f"- `{row['row_id'][:16]}` {row['outcome']}: {detail}")
    else:
        lines += ["- No rows compared (slice-empty)."]
    lines.append("")
    note_path.write_text("\n".join(lines), encoding="utf-8")


def exit_code_for(rows: list[dict]) -> int:
    """0 when every row is a match (§4: the run is invalid otherwise)."""
    bad = [row for row in rows if row["outcome"] != OUTCOME_MATCH]
    for row in bad:
        print(
            f"fidelity_run: {row['outcome']}: {row['row_id'][:16]} {row['first_divergence'][:200]}",
            file=sys.stderr,
        )
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    split = "all"
    slice_name = SLICE_L1
    sample: tuple[str, int] | None = None
    fixtures = False
    timeout = 600.0
    csv_path: Path | None = None
    note_path: Path | None = None
    port_bin: Path | None = None
    it = iter(argv)
    for arg in it:
        if arg == "--fixtures":
            fixtures = True
        elif arg == "--split":
            split = next(it)
            if split not in ("dev", "held-out", "all"):
                raise SystemExit(f"fidelity_run: unknown --split {split!r}")
        elif arg == "--slice":
            slice_name = next(it)
            if slice_name not in (SLICE_L1, SLICE_L2, SLICE_BOTH):
                raise SystemExit(f"fidelity_run: unknown --slice {slice_name!r}")
        elif arg == "--sample":
            method, _, count_text = next(it).partition(":")
            sample = (method, int(count_text))
        elif arg == "--timeout":
            timeout = float(next(it))
        elif arg == "--csv":
            csv_path = Path(next(it))
        elif arg == "--note":
            note_path = Path(next(it))
        elif arg == "--port-bin":
            port_bin = Path(next(it))
        else:
            raise SystemExit(f"fidelity_run: unknown argument {arg!r}")
    if csv_path is None:
        csv_path = DATA_DIR / "v1-fidelity-l1-claims.csv"
    if note_path is None:
        note_path = REPO_ROOT / "docs" / "evidence" / f"{stamp}-v1-fidelity-l1.md"
    if fixtures:
        return run_fixture_mode(csv_path, note_path, timeout, port_bin)
    return run_corpus_mode(csv_path, note_path, split, slice_name, sample, timeout, port_bin)


if __name__ == "__main__":
    sys.exit(main())
