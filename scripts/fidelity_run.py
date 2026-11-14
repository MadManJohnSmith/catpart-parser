#!/usr/bin/env python3
"""The Fidelity harness (spec ``docs/specs/phase5-viewer-spec.md`` §4, V1
ticket #40 + V2 ticket #41): prove Port ≡ Python over one diff
implementation, dual-mode.

- **Fixture mode** (``--fixtures``): generates the A2 synthetic fixtures
  via ``tests/fixtures_gen.py`` in-process, runs both implementations
  over them, diffs — wired into the gate as ``tests/test_port_fidelity.py``.
  This is how "CI covers the port with the synthetic fixtures from A2"
  is satisfied with one harness: the same diff code proves parity in CI
  on fixtures and locally on the corpus. V2 adds the export comparison
  over the non-composite geometry variants (the composite-law and
  unrouted-elementspace variants are V3 scope, #42 — excluded from the
  export matrix). ``--slice`` selects l1 (inspect rows), l2 (export
  rows) or both (default).

- **Corpus mode** (default, local-only per ADR-0003): walks
  ``manifests/corpus-manifest.csv``, applies the slice populations
  (§3.1 — the L1-JSON slice is ALL manifest rows, junk included; the
  L2-export slice is the ``kind=part`` rows), and drives the Python
  reference (``catpart-inspect`` / ``catpart-export``) and the Rust
  port (``port/target/release/fidelity-cli``, built once per run by
  ``cargo build --release``) as subprocesses — the exact shipped
  seams, no in-process imports, one shape for both.

Diff definitions (§3.2):

- **L1 slice** (V1): the inspect document is compared by
  parsed-document equality — recursive structural equality, object key
  sets equal, arrays equal in order, numbers equal with the int/float
  distinction preserved. A failed run is compared by ``error_class``
  string equality: the Python side's exit 1 on the shipped seam is the
  fitness class ``crash`` (``runner._classify_file`` maps every inspect
  exception there; the A2 fixture table pins short-file → crash), and
  the port's stderr JSON line carries the same single-class L1
  vocabulary (``bin/fidelity-cli.rs``).
- **L2 export slice** (V2 + V3): the export summary is compared by
  parsed-document equality AND the PLY bytes byte-identical; a failed
  run is compared by ``error_class`` string equality (the geometry
  vocabulary of ``catpart.geometry.errors``, at the same raise sites
  both sides). ``detail`` is never compared byte-wise. The
  composite-path semantics carry the V2->V3 flip (#42): while the
  composite decode is partially ported (V3 stages 1-2), composite-path
  EXPORTS (the Python summary carries the additive ``composite`` key)
  with a port refusal are **excluded** as the outcome
  ``excluded-composite-path`` (the ticket #41 hard stop; the corpus
  sample stays biased away from the identity-law families via the
  stage-15 roster) and the fixture export matrix covers only the
  landed stages (:data:`COMPOSITE_EXPORT_STAGES`). With the full
  composite model landed (V3 stage 3) the exclusion lifts: composite
  exports compare fully (a port refusal against a twin export is a
  mismatch), the fixture matrix covers every composite family, and the
  corpus sampler gains the composite-family stratification
  (``--sample composite-stratified:N`` — drawn per-family from the
  stage-15 roster, every firing law and the fail-closed composite
  class included; V2's ``stratified:N`` stays available unchanged).

Any harness-level failure (timeout, missing binary, unreadable output)
is recorded as its own outcome class and NEVER counts as a match — the
run is invalid until every row is match/mismatch/error-class-mismatch
by evidence (an excluded row is a measurement intentionally not made;
it is named per-row in the note and never counted as a match or a
mismatch).

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
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "manifests" / "corpus-manifest.csv"
FITNESS_DIR = REPO_ROOT / "fitness"
DATA_DIR = REPO_ROOT / "docs" / "evidence" / "data"

#: The stage-15 roster (spec §4: the stage CSVs name the per-family
#: stores; V2 biases away from the composite family via
#: ``element_decl > 0``).
COMPOSITE_ROSTER_PATH = DATA_DIR / "stage15-identity-export-files.csv"

#: The L1 slice's single error class (see the module docstring and
#: ``port/src/bin/fidelity-cli.rs``): the Python side's exit 1 on the
#: shipped inspect seam is the fitness class ``crash``.
L1_PYTHON_ERROR_CLASS = "crash"

#: The fail-closed classes the V2 sample biases toward (ticket #41:
#: "biased to non-composite exports AND to fail-closed classes:
#: undecoded-variant, missing-store families") and their seat weight.
FAIL_CLOSED_CLASSES = (
    "undecoded-variant",
    "missing-geometry-store",
    "malformed-store-header",
    "malformed-pool-group",
    "malformed-pool-vertex",
)
FAIL_CLOSED_WEIGHT = 3

#: Outcome vocabulary (§4 + the V2 exclusion).
OUTCOME_MATCH = "match"
OUTCOME_OUTPUT_MISMATCH = "output-mismatch"
OUTCOME_CLASS_MISMATCH = "error-class-mismatch"
OUTCOME_HARNESS_ERROR = "harness-error"
OUTCOME_EXCLUDED_COMPOSITE = "excluded-composite-path"

#: The Python export summary's additive composite-only key (the twin
#: emits it on every composite-path decode) — the authoritative
#: composite-path marker at run time.
COMPOSITE_SUMMARY_KEY = "composite"

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

#: The composite-family export-matrix additions by port stage (ticket
#: #42's internal order; the fixture work lands where the families are
#: known, spec §6 V3). Stage 1: the table-walk + per-rep families and
#: the routing/fail-closed shapes of those families (the stage-13
#: unrouted route, the N1/walk-mismatch/unabsorbed refusals, the
#: recovered composite stores). Stage 2: the raw-array + mixedwrite
#: families (positives and fail-closed negatives). Stage 3: the dup-pin
#: and dedup families (the stage-14 ceiling set's fixture twins and
#: the review-F1 dedup shapes).
COMPOSITE_EXPORT_STAGES: dict[int, tuple[str, ...]] = {
    1: (
        "geometry-composite-law",
        "geometry-composite-law-big",
        "geometry-composite-law-slanted",
        "geometry-composite-law-curve-entries",
        "geometry-composite-law-u16be",
        "geometry-composite-law-u24be",
        "geometry-composite-law-width-plane",
        "geometry-composite-law-multi-rep",
        "geometry-composite-law-multi-rep-partial",
        "geometry-othercontainer-composite-law",
        "geometry-unrouted-elementspace-refs-beyond",
        "geometry-unrouted-elementspace-no-pool",
        "geometry-unrouted-elementspace-no-node",
        "geometry-unrouted-elementspace-walk-mismatch",
        "geometry-composite-law-walk-mismatch",
        "geometry-composite-law-unabsorbed",
        "geometry-composite-law-walk-nan",
        "geometry-composite-index-space",
        "geometry-seebody-composite",
        "geometry-othercontainer-composite",
    ),
    2: (
        "geometry-composite-law-raw-array",
        "geometry-composite-law-raw-array-strip-false-match",
        "geometry-composite-law-table-overshoot",
        "geometry-composite-law-flat-near-zero",
        "geometry-composite-law-mixedwrite-multi-rep",
        "geometry-composite-law-raw-array-wrong-offset",
        "geometry-composite-law-raw-array-unabsorbed",
        "geometry-composite-law-mixedwrite-multi-rep-subnode",
    ),
    3: (
        "geometry-composite-law-e0b-dup-pin",
        "geometry-composite-law-e0b-single-loop",
        "geometry-composite-law-e0b-nonplanar",
        "geometry-composite-law-e0b-normal-less",
        "geometry-composite-law-e0b-nonempty",
        "geometry-composite-law-e0b-multi-rep-conservative",
        "geometry-composite-law-e0b-multi-rep-unsupported-veto",
        "geometry-composite-law-e0b-unpinnable",
        "geometry-composite-law-e0b-relaxed-not-manifold",
        "geometry-composite-law-e0b-multi-rep-relaxed",
        "geometry-composite-law-dedup-unordered",
        "geometry-composite-law-dedup-manifold-no-fire",
        "geometry-composite-law-dedup-declined",
        "geometry-composite-law-dedup-degenerate",
    ),
}

#: The port's landed composite stage (V3 #42's internal order — grows
#: one commit at a time; 3 = the full landed model). The fixture-mode
#: export matrix covers the stages landed so far; the composite-path
#: comparison semantic flips with it (see :func:`compare_row_export`).
COMPOSITE_EXPORT_STAGE = 1

SLICE_L1 = "l1"
SLICE_L2 = "l2"
SLICE_BOTH = "both"


# --- seam resolution -----------------------------------------------------


def _resolve_console_script(name: str, override_env: str) -> str:
    """Locate a shipped console script (the shared resolution order).

    Order: the ``override_env`` override, the console script next to the
    running interpreter (the venv layout both the gate and the corpus
    machine use), then ``PATH``.
    """
    override = os.environ.get(override_env)
    if override:
        return override
    adjacent = Path(sys.executable).parent / name
    if adjacent.is_file():
        return str(adjacent)
    found = shutil.which(name)
    if found:
        return found
    raise SystemExit(
        f"fidelity_run: cannot find the {name} console script "
        f"(set {override_env} or install the package: "
        "python -m venv .venv && .venv/bin/pip install -e '.[test,lint]')"
    )


def resolve_python_inspect() -> str:
    """Locate the shipped ``catpart-inspect`` console script."""
    return _resolve_console_script("catpart-inspect", "FIDELITY_PY_INSPECT")


def resolve_python_export() -> str:
    """Locate the shipped ``catpart-export`` console script."""
    return _resolve_console_script("catpart-export", "FIDELITY_PY_EXPORT")


def build_port_bin() -> Path:
    """Build the release ``fidelity-cli`` once per run (§4) and return it.

    Runs ``cargo build --release --locked`` inside ``port/``; the run
    aborts if the build fails or the binary is missing — cargo's own
    rebuild is the freshness guarantee: a no-op build still refreshes
    the artifact, so whatever survives the build is current by
    construction (review F2, ticket #40: the post-build mtime check
    was unreachable — cargo freshens the binary even on a no-op build
    — and is dropped; correction dated 2026-11-14 in the V1 note).
    The artifact is ``fidelity-cli`` (spec §2.4); the harness resolves
    both spellings for older checkouts.
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
            return candidate
    raise SystemExit("fidelity_run: cargo build reported success but the fidelity-cli binary is missing")


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


def run_seam(command: list[str], path: str, timeout: float, trailing: tuple[str, ...] = ()) -> SeamResult:
    """Run one implementation over ``path`` with the shared shape.

    The subprocess gets the file path as its first argument plus
    ``trailing`` (the export seam's PLY path) and must answer with its
    document on stdout (exit 0) or a classified failure (exit 1);
    anything else is a harness-level failure (§3.2).
    """
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command + [path] + list(trailing),
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


def parse_error_class(seam: SeamResult) -> str | None:
    """The ``error_class`` of the one-JSON-line stderr failure.

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


def parse_summary(seam: SeamResult) -> tuple[dict | None, str | None]:
    """The parsed stdout document of a successful seam run.

    Returns ``(document, None)`` or ``(None, harness_error_detail)`` —
    unparsable stdout is a harness-level failure (§3.2), never a
    comparison.
    """
    try:
        return json.loads(seam.stdout), None
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, f"{seam.side} stdout is not JSON: {seam.stdout[:200]!r}"


def compare_row(py: SeamResult, port: SeamResult, timeout: float) -> tuple[str, str]:
    """Compare one (python, port) inspect pair → ``(outcome, first_divergence)``.

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
        port_class = parse_error_class(port)
        if port_class is None:
            return OUTCOME_HARNESS_ERROR, f"port stderr is not an error-class JSON line: {port.stderr[:200]!r}"
        if port_class == L1_PYTHON_ERROR_CLASS:
            return OUTCOME_MATCH, ""
        return OUTCOME_CLASS_MISMATCH, f"error_class python={L1_PYTHON_ERROR_CLASS} port={port_class}"
    if py.ok and port.ok:
        py_doc, err = parse_summary(py)
        if err:
            return OUTCOME_HARNESS_ERROR, err
        port_doc, err = parse_summary(port)
        if err:
            return OUTCOME_HARNESS_ERROR, err
        found = first_divergence(py_doc, port_doc)
        if found is None:
            return OUTCOME_MATCH, ""
        return OUTCOME_OUTPUT_MISMATCH, found
    sides = "python produced a document, port failed" if py.ok else "port produced a document, python failed"
    port_class = parse_error_class(port) if port.failed else None
    return OUTCOME_OUTPUT_MISMATCH, f"{sides}" + (f" (port error_class={port_class})" if port_class else "")


def compare_row_export(
    py: SeamResult,
    port: SeamResult,
    timeout: float,
    ply_py_path: Path,
    ply_port_path: Path,
    composite_exclusion: bool = False,
) -> tuple[str, str, str]:
    """Compare one (python, port) export pair (§3.2, V2 + V3).

    Returns ``(outcome, first_divergence, ply_equal)`` — ``ply_equal``
    is ``"true"``/``"false"`` when compared, ``""`` when not (refused
    rows write no comparable PLY pair). The ``composite_exclusion``
    flag selects the composite-path semantic (V2 vs V3, #42):

    - ``True`` (the V2-biased corpus sample while the composite decode
      is partially ported): a Python summary carrying the additive
      ``composite`` key with a port refusal is
      ``excluded-composite-path`` (the ticket #41 hard stop — never a
      false match; a measurement intentionally not made).
    - ``False`` (V3: the port claims the composite decode — the
      fixture matrix and the composite-stratified corpus sample): a
      Python composite-path export with a port refusal is an
      ``output-mismatch`` — the port must reproduce the twin's
      composite exports, so a refusal is a divergence, never an
      exclusion.

    With the port ALSO succeeding the row compares fully on both
    semantics (the composite block included in the parsed-document
    equality).
    """
    if py.timed_out or port.timed_out:
        side = "python" if py.timed_out else "port"
        return OUTCOME_HARNESS_ERROR, f"{side} exceeded the {timeout:g}s timeout", ""
    if py.exit_code not in (0, 1):
        return OUTCOME_HARNESS_ERROR, f"python exit {py.exit_code} outside the seam contract (0/1): {py.stderr[:200]!r}", ""
    if port.exit_code not in (0, 1, 2):
        return OUTCOME_HARNESS_ERROR, f"port exit {port.exit_code} outside the seam contract (0/1/2): {port.stderr[:200]!r}", ""
    if port.exit_code == 2:
        return OUTCOME_HARNESS_ERROR, "port usage error (exit 2) — harness invoked the seam wrongly", ""
    py_doc = None
    if py.ok:
        py_doc, err = parse_summary(py)
        if err:
            return OUTCOME_HARNESS_ERROR, err, ""
    port_doc = None
    if port.ok:
        port_doc, err = parse_summary(port)
        if err:
            return OUTCOME_HARNESS_ERROR, err, ""
    if py_doc is not None and COMPOSITE_SUMMARY_KEY in py_doc and port_doc is None:
        if composite_exclusion:
            # The V2 hard stop (ticket #41): a composite-path export
            # with no port decode is excluded, never a false match.
            return OUTCOME_EXCLUDED_COMPOSITE, "python summary carries the composite key (V3 decode, #42); port refused", ""
        # V3 (ticket #42): the port claims the composite decode — a
        # refusal against a twin export is a divergence.
        return OUTCOME_OUTPUT_MISMATCH, "python summary carries the composite key and exported; the port refused (V3 covers the composite path)", ""
    if py.failed and port.failed:
        py_class = parse_error_class(py)
        if py_class is None:
            return OUTCOME_HARNESS_ERROR, f"python stderr is not an error-class JSON line: {py.stderr[:200]!r}", ""
        port_class = parse_error_class(port)
        if port_class is None:
            return OUTCOME_HARNESS_ERROR, f"port stderr is not an error-class JSON line: {port.stderr[:200]!r}", ""
        if py_class == port_class:
            return OUTCOME_MATCH, "", ""
        return OUTCOME_CLASS_MISMATCH, f"error_class python={py_class} port={port_class}", ""
    if py_doc is not None and port_doc is not None:
        found = first_divergence(py_doc, port_doc)
        if found is not None:
            return OUTCOME_OUTPUT_MISMATCH, found, ""
        if not ply_py_path.is_file() or not ply_port_path.is_file():
            return OUTCOME_HARNESS_ERROR, "a PLY output is missing on a successful export pair", ""
        ply_equal = ply_py_path.read_bytes() == ply_port_path.read_bytes()
        if ply_equal:
            return OUTCOME_MATCH, "", "true"
        return (
            OUTCOME_OUTPUT_MISMATCH,
            f"PLY bytes differ (python {ply_py_path.stat().st_size} B, port {ply_port_path.stat().st_size} B)",
            "false",
        )
    sides = "python produced a document, port failed" if py.ok else "port produced a document, python failed"
    class_note = ""
    if py.failed:
        py_class = parse_error_class(py)
        class_note = f" (python error_class={py_class})" if py_class else ""
    else:
        port_class = parse_error_class(port)
        class_note = f" (port error_class={port_class})" if port_class else ""
    return OUTCOME_OUTPUT_MISMATCH, f"{sides}{class_note}", ""


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
    """The A2 fixture population the gate compares on the L1 slice (§4).

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


def export_fixture_matrix() -> list[dict]:
    """The export-comparison fixture population (§3.2 L2, V2 #41 + V3 #42).

    All geometry-bearing A2 variants (the canonical store, the recovery
    variants, the corrupted classes — the ticket's acceptance set) at
    seeds 0 and 7, plus the store-less shapes (``None``, ``dual-region``
    and the plain corrupted families) which refuse
    ``missing-geometry-store`` / the short-file path — the fail-closed
    vocabulary on fixtures. kind=part only: the L2 population is the
    runner's part rows (§3.1).

    V3 (#42): the composite-family variants join the export matrix as
    their port stage lands (:data:`COMPOSITE_EXPORT_STAGES` grown by
    :data:`COMPOSITE_EXPORT_STAGE` — walk + per-rep, then raw-array +
    mixedwrite, then dup-pin + dedup). One seed each: the composite
    store body is a pure function of the variant (the seed drives the
    file framing's GUIDs and padding, which the decode does not read).
    """
    gen = load_fixtures_gen()
    plain = {"dual-region", "bad-magic", "truncated-table", "missing-trailer", "junk-payload", "oversized-dword", "short-file"}
    matrix: list[dict] = [{"kind": "part", "seed": 0, "variant": None}]
    for variant in sorted(plain):
        matrix.append({"kind": "part", "seed": 0, "variant": variant})
    for variant in sorted(set(gen.GEOMETRY_VARIANTS)):
        for seed in (0, 7):
            matrix.append({"kind": "part", "seed": seed, "variant": variant})
    for stage in range(1, COMPOSITE_EXPORT_STAGE + 1):
        for variant in COMPOSITE_EXPORT_STAGES[stage]:
            matrix.append({"kind": "part", "seed": 0, "variant": variant})
    return matrix


def _export_commands(port_bin: Path) -> tuple[list[str], list[str]]:
    """The export subprocess shapes (one shape per implementation).

    Python: ``catpart-export <file> -o <ply>`` (the console script's
    contract); port: ``fidelity-cli export <file> <ply>`` (spec §2.4's
    "PLY to a second path argument").
    """
    return (
        [resolve_python_export()],
        [str(port_bin), "export"],
    )


def run_fixture_mode(csv_path: Path, note_path: Path, timeout: float, port_bin: Path | None, slice_name: str = SLICE_BOTH) -> int:
    """Generate the A2 fixtures in-process, run both seams, diff (§4)."""
    gen = load_fixtures_gen()
    bin_path = port_bin or build_port_bin()
    python_inspect = [resolve_python_inspect()]
    port_inspect = [str(bin_path), "inspect"]
    python_export, port_export = _export_commands(bin_path)
    fixtures_dir = csv_path.parent / "fidelity-fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    ply_dir = fixtures_dir / "ply"
    ply_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    started = time.monotonic()

    def add_row(entry: dict, fixture_id: str, path: Path, py: SeamResult, port: SeamResult, outcome: str, divergence: str, ply_equal: str, slice_label: str) -> None:
        rows.append({
            "row_id": f"{fixture_id}|{slice_label}" if slice_label else fixture_id,
            "path": str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path),
            "split": "fixture",
            "kind": entry["kind"],
            "magic_ok": "",
            "detected_version": "",
            "export_outcome_class": "",
            "python_exit": py.exit_code,
            "port_exit": port.exit_code,
            "outcome": outcome,
            "python_error_class": parse_error_class(py) or (L1_PYTHON_ERROR_CLASS if py.failed else ""),
            "port_error_class": parse_error_class(port) or "",
            "ply_equal": ply_equal,
            "first_divergence": divergence,
            "python_seconds": f"{py.seconds:.3f}",
            "port_seconds": f"{port.seconds:.3f}",
        })

    if slice_name in (SLICE_L1, SLICE_BOTH):
        for entry in fixture_matrix():
            fixture_id = (
                f"{entry['variant'] or 'canonical'}|k{entry['kind']}|s{entry['seed']}"
                + ("|doc" if entry.get("document_name") else "")
            )
            path = fixtures_dir / f"{_safe_name(fixture_id)}.CATPart"
            path.write_bytes(gen.build_fixture(entry["kind"], seed=entry["seed"], variant=entry["variant"], document_name=entry.get("document_name")))
            py = run_seam(python_inspect, str(path), timeout)
            port = run_seam(port_inspect, str(path), timeout)
            outcome, divergence = compare_row(py, port, timeout)
            add_row(entry, fixture_id, path, py, port, outcome, divergence, "", "l1")
    if slice_name in (SLICE_L2, SLICE_BOTH):
        for entry in export_fixture_matrix():
            fixture_id = f"{entry['variant'] or 'canonical'}|k{entry['kind']}|s{entry['seed']}"
            path = fixtures_dir / f"{_safe_name(fixture_id)}.CATPart"
            path.write_bytes(gen.build_fixture(entry["kind"], seed=entry["seed"], variant=entry["variant"]))
            ply_py = ply_dir / "python.ply"
            ply_port = ply_dir / "port.ply"
            py = run_seam(python_export, str(path), timeout, ("-o", str(ply_py)))
            port = run_seam(port_export, str(path), timeout, (str(ply_port),))
            outcome, divergence, ply_equal = compare_row_export(py, port, timeout, ply_py, ply_port)
            add_row(entry, fixture_id, path, py, port, outcome, divergence, ply_equal, "l2")
    shutil.rmtree(fixtures_dir, ignore_errors=True)
    wall_clock = time.monotonic() - started
    write_csv(csv_path, rows)
    write_note(
        note_path,
        run_kind="fixture-mode (A2 fixtures, generated in-process via tests/fixtures_gen.py)",
        population_rows=rows,
        wall_clock=wall_clock,
        csv_path=csv_path,
        slice_note=fixture_slice_note(slice_name),
    )
    return exit_code_for(rows)


def fixture_slice_note(slice_name: str) -> str:
    """The fixture-mode slice note (the composite coverage named)."""
    if slice_name == SLICE_L1:
        return "L1 slice (inspect document equality); --slice l1: the L2 export rows skipped"
    composite_note = (
        f"; composite-family variants covered through port stage "
        f"{COMPOSITE_EXPORT_STAGE} of 3 (ticket #42's internal order: walk + "
        "per-rep -> raw-array + mixedwrite -> dup-pin + dedup + curve exposure)"
    )
    if slice_name == SLICE_L2:
        return (
            "L2 export slice on fixtures (summary parsed-document equality + PLY "
            "byte-identical + error_class equality, §3.2): the geometry-bearing A2 "
            "variants + the store-less refusals"
            + composite_note
        )
    return (
        "L1 slice (inspect document equality) + L2 export slice on fixtures "
        "(summary + PLY bytes + error classes, §3.2)"
        + composite_note
    )


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


def load_composite_roster() -> dict[str, bool]:
    """The stage-15 roster's composite-family map (spec §4).

    ``element_decl > 0`` marks the stores the G6 identity law decoded —
    the corpus's composite-family stores, both the exporting ones (the
    twin's additive ``composite`` summary key at run time is the
    authoritative marker) and the whole family the V2 sample must bias
    away from. Returns ``{sha256: is_composite}`` so the sampler can
    also verify every part row is covered (fail-closed on a stale
    roster or a missing file).
    """
    if not COMPOSITE_ROSTER_PATH.is_file():
        raise SystemExit(
            f"fidelity_run: the stage-15 roster {COMPOSITE_ROSTER_PATH} is missing — "
            "the V2 composite bias needs it (spec §4: the stage CSVs name the "
            "per-family stores)"
        )
    with COMPOSITE_ROSTER_PATH.open(newline="", encoding="utf-8") as fh:
        return {
            row["sha256"]: row["element_decl"] not in ("", "0")
            for row in csv.DictReader(fh)
        }


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


def biased_l2_sample(rows: list[dict], report: dict, count: int) -> tuple[list[dict], dict]:
    """The V2 L2 sample: biased away from composite, toward fail-closed.

    The pool is the ``kind=part`` rows NOT in the stage-15 composite
    roster (``element_decl > 0`` — the ticket's "bias AWAY from
    composite-family stores"); every part row must be in the roster
    (fail-closed: a stale roster must stop the run, not silently
    sample over unknown families). Strata are the §4 axis
    (detected_version x split x export outcome class); the fail-closed
    classes (:data:`FAIL_CLOSED_CLASSES`) carry a seat weight of
    :data:`FAIL_CLOSED_WEIGHT` — a stratum occupies that many slots in
    the round-wise priority list, so per round it receives that many
    seats while quota lasts. Within a stratum the picks are evenly
    spaced over the sha256-sorted rows — no RNG; the same N yields the
    same sample. Returns ``(sample, stats)`` where ``stats`` names the
    exclusion arithmetic for the note.
    """
    by_sha = {record["sha256"]: record for record in report["files"]}
    roster = load_composite_roster()
    kept: list[tuple[dict, str, str, str]] = []
    composite_in_split = 0
    for row in rows:
        is_composite = roster.get(row["sha256"])
        if is_composite is None:
            raise SystemExit(
                f"fidelity_run: part row {row['sha256'][:16]} is not in the stage-15 "
                "roster — a stale stratification basis; the composite-family "
                "exclusion cannot be applied fail-closed"
            )
        if is_composite:
            composite_in_split += 1
            continue
        record = by_sha[row["sha256"]]
        version = record.get("detected_version") or "unknown"
        split = record.get("split") or "unknown"
        stratum_class = export_outcome_class(record)
        kept.append((row, version, split, stratum_class))
    strata: dict[tuple, list[dict]] = {}
    for row, version, split, stratum_class in kept:
        strata.setdefault((version, split, stratum_class), []).append(row)
    for members in strata.values():
        members.sort(key=lambda row: row["sha256"])
    ordered = sorted(strata.items(), key=lambda item: item[0])
    weights = [
        FAIL_CLOSED_WEIGHT if members_key[2] in FAIL_CLOSED_CLASSES else 1
        for members_key, _ in ordered
    ]
    sizes = [len(members) for _, members in ordered]
    if count >= sum(sizes):
        quota = list(sizes)
    else:
        quota = [0] * len(ordered)
        remaining = count
        priority: list[int] = []
        for index in sorted(range(len(ordered)), key=lambda index: (-weights[index] * sizes[index], ordered[index][0])):
            priority.extend([index] * weights[index])
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
            ranks = sorted({round(i * (len(members) - 1) / (n - 1)) for i in range(n)})
            if len(ranks) < n:
                ranks = sorted(set(range(len(members))) | set(ranks))[:n]
        sample.extend(members[rank] for rank in ranks)
    stats = {
        "part_rows_in_split": len(kept) + composite_in_split,
        "composite_family_excluded": composite_in_split,
        "non_composite_pool": len(kept),
        "sampled": len(sample),
        "by_class": dict(sorted(Counter(export_outcome_class(by_sha[row["sha256"]]) for row in sample).items())),
    }
    return sample, stats


def run_corpus_mode(csv_path: Path, note_path: Path, split: str, slice_name: str, sample: tuple[str, int] | None, timeout: float, port_bin: Path | None) -> int:
    """Walk the manifest, apply the slice population, diff both seams."""
    manifest = read_manifest()
    report = load_accepted_report()
    bin_path = port_bin or build_port_bin()
    python_inspect = [resolve_python_inspect()]
    port_inspect = [str(bin_path), "inspect"]
    python_export, port_export = _export_commands(bin_path)
    rows = manifest
    if split != "all":
        rows = [row for row in rows if row["split"] == split]

    l2_stats: dict | None = None
    if slice_name == SLICE_L2:
        # The L2 population (§3.1): the kind=part rows. The sample is
        # the V2-biased one (composite-family exclusion + fail-closed
        # weight); without --sample the FULL non-composite population
        # runs (the V6 shape).
        part_rows = [row for row in rows if row["kind"] == "part"]
        if sample is not None:
            method, count = sample
            if method != "stratified":
                # composite-stratified:N lands with port stage 3 (the
                # composite decode must be complete before its sample
                # compares fully).
                raise SystemExit(f"fidelity_run: unknown --sample method {method!r} (only stratified:N)")
            sampled, l2_stats = biased_l2_sample(part_rows, report, count)
            rows = sorted(sampled, key=lambda row: row["sha256"])
        else:
            _, l2_stats = biased_l2_sample(part_rows, report, len(part_rows))
            rows = sorted(part_rows, key=lambda row: row["sha256"])
        if COMPOSITE_EXPORT_STAGE >= 3:
            slice_note = (
                "L2-export slice (§3.1: the kind=part rows): summary parsed-document "
                "equality + PLY byte-identical + error_class equality on double "
                "refusals (§3.2); the composite path is ported (V3 #42) — composite-path "
                "exports compare fully (a port refusal against a twin export is a mismatch)"
            )
        else:
            slice_note = (
                "L2-export slice (§3.1: the kind=part rows): summary parsed-document "
                "equality + PLY byte-identical + error_class equality on double "
                "refusals (§3.2); composite-path exports excluded "
                "(excluded-composite-path — the ticket #41 hard stop, the composite "
                "decode is V3 #42)"
            )
    else:
        slice_note = "L1-JSON slice (§3.1: ALL manifest rows — parts, products and the magic_ok=no junk)"
        if sample is not None:
            method, count = sample
            if method != "stratified":
                raise SystemExit(f"fidelity_run: unknown --sample method {method!r} (only stratified:N)")
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
        if slice_name == SLICE_BOTH:
            slice_note += (
                "; --slice both: the L2 export comparison runs on the part rows "
                "of the same sample (summary + PLY bytes + error classes; "
                "composite-path exports excluded, ticket #41 hard stop)"
            )
    if slice_name == SLICE_L1 and l2_stats is None:
        pass  # the L1-only shape: no export pass
    by_sha = {record["sha256"]: record for record in report["files"]}
    result_rows: list[dict] = []
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="fidelity-run-") as ply_dir:
        for row in rows:
            path = str(REPO_ROOT / row["local_path"])
            record = by_sha[row["sha256"]]
            base_row = {
                "row_id": row["sha256"],
                "path": row["path"],
                "split": row["split"],
                "kind": row["kind"],
                "magic_ok": row["magic_ok"],
                "detected_version": record.get("detected_version") or "unknown",
                "export_outcome_class": export_outcome_class(record),
            }
            if slice_name in (SLICE_L1, SLICE_BOTH):
                py = run_seam(python_inspect, path, timeout)
                port = run_seam(port_inspect, path, timeout)
                outcome, divergence = compare_row(py, port, timeout)
                result_rows.append({
                    **base_row,
                    "python_exit": py.exit_code,
                    "port_exit": port.exit_code,
                    "outcome": outcome,
                    "python_error_class": L1_PYTHON_ERROR_CLASS if py.failed else "",
                    "port_error_class": parse_error_class(port) or "",
                    "ply_equal": "",
                    "first_divergence": divergence,
                    "python_seconds": f"{py.seconds:.3f}",
                    "port_seconds": f"{port.seconds:.3f}",
                })
            if slice_name in (SLICE_L2, SLICE_BOTH) and row["kind"] == "part":
                ply_py = Path(ply_dir) / f"{row['sha256'][:24]}.python.ply"
                ply_port = Path(ply_dir) / f"{row['sha256'][:24]}.port.ply"
                py = run_seam(python_export, path, timeout, ("-o", str(ply_py)))
                port = run_seam(port_export, path, timeout, (str(ply_port),))
                # The V2 composite exclusion stays armed while the
                # composite decode is partially ported (stages 1-2 of
                # #42); with the full model landed (stage 3) the
                # composite path compares everywhere — a port refusal
                # against a twin export is a mismatch.
                outcome, divergence, ply_equal = compare_row_export(
                    py, port, timeout, ply_py, ply_port,
                    composite_exclusion=COMPOSITE_EXPORT_STAGE < 3,
                )
                result_rows.append({
                    **base_row,
                    "row_id": f"{row['sha256']}|export",
                    "python_exit": py.exit_code,
                    "port_exit": port.exit_code,
                    "outcome": outcome,
                    "python_error_class": parse_error_class(py) or "",
                    "port_error_class": parse_error_class(port) or "",
                    "ply_equal": ply_equal,
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
        l2_stats=l2_stats,
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


def write_note(note_path: Path, run_kind: str, population_rows: list[dict], wall_clock: float, csv_path: Path, slice_note: str, l2_stats: dict | None = None) -> None:
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
    excluded = outcomes[OUTCOME_EXCLUDED_COMPOSITE]
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
    if excluded:
        lines += [
            f"- Excluded composite-path rows (the ticket #41 hard stop: the "
            f"composite decode is V3, #42; never matches, never mismatches): {excluded}",
        ]
    if l2_stats is not None:
        lines += [
            f"- V2 sample bias (stage-15 roster): {l2_stats['part_rows_in_split']} part rows in the "
            f"split, {l2_stats['composite_family_excluded']} composite-family rows excluded "
            f"(element_decl > 0), pool {l2_stats['non_composite_pool']}, sampled {l2_stats['sampled']} "
            f"(fail-closed classes weight {FAIL_CLOSED_WEIGHT}); sampled by export outcome class: "
            f"{l2_stats['by_class']}",
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
        diverging = [row for row in population_rows if row["outcome"] not in (OUTCOME_MATCH, OUTCOME_EXCLUDED_COMPOSITE)]
        if diverging:
            lines += ["", "## Non-match rows (first divergence per row)", ""]
            for row in diverging:
                detail = row["first_divergence"][:220]
                lines.append(f"- `{row['row_id'][:16]}` {row['outcome']}: {detail}")
        excluded_rows = [row for row in population_rows if row["outcome"] == OUTCOME_EXCLUDED_COMPOSITE]
        if excluded_rows:
            lines += ["", "## Excluded composite-path rows (named per-row, §3.2 discipline)", ""]
            for row in excluded_rows:
                lines.append(f"- `{row['row_id'][:16]}` {row['path']}")
    else:
        lines += ["- No rows compared (slice-empty)."]
    lines.append("")
    note_path.write_text("\n".join(lines), encoding="utf-8")


def exit_code_for(rows: list[dict]) -> int:
    """0 when every row is a match or an excluded row (§4 + the V2 hard
    stop: the run is invalid on any mismatch or harness-level failure;
    an excluded row is a measurement intentionally not made, named
    per-row in the note, never a match and never a mismatch)."""
    bad = [row for row in rows if row["outcome"] not in (OUTCOME_MATCH, OUTCOME_EXCLUDED_COMPOSITE)]
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
    slice_name: str | None = None  # None = the mode's default (fixture: both; corpus: l1)
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
    if fixtures:
        # Fixture mode defaults to BOTH slices at V2: the gate's fixture
        # pin covers the inspect matrix AND the export matrix (V2, #41).
        slice_name = slice_name or SLICE_BOTH
        if csv_path is None:
            csv_path = DATA_DIR / "v2-fidelity-fixture-claims.csv"
        if note_path is None:
            note_path = REPO_ROOT / "docs" / "evidence" / f"{stamp}-v2-fidelity-fixtures.md"
        return run_fixture_mode(csv_path, note_path, timeout, port_bin, slice_name)
    slice_name = slice_name or SLICE_L1
    if csv_path is None:
        csv_path = DATA_DIR / ("v2-fidelity-l2-claims.csv" if slice_name == SLICE_L2 else "v1-fidelity-l1-claims.csv")
    if note_path is None:
        note_path = REPO_ROOT / "docs" / "evidence" / f"{stamp}-v1-fidelity-l1.md"
    return run_corpus_mode(csv_path, note_path, split, slice_name, sample, timeout, port_bin)


if __name__ == "__main__":
    sys.exit(main())
