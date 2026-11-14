#!/usr/bin/env python3
"""The V5 in-browser reproduction harness (ticket #52, spec §6 V5) —
drives the COMMITTED viewer over a population, reads the per-file
per-check outcome the page computes (the §3.4 gate mirror exposed on
``window.viewer``), compares it per-file against the Python fitness
records' per-check outcomes, aggregates per split, and writes a
figures-only note + a per-file CSV named for the ``*claims*.csv`` glob
(#37-composable, the ``scripts/fidelity_run.py`` output convention).

LOCAL ONLY, never CI (spec §7: real-browser runs and the corpus stay
out of Actions). Stdlib + Playwright (the one non-stdlib dependency,
the ``scripts/viewer_acceptance.py`` precedent). The serving is
read-only static (``python3 -m http.server`` over ``site/``); the
corpus files cross to the browser through the file input
(``set_input_files``), never through the server.

Two modes:

- ``--smoke`` (fixture machinery smoke): generates a handful of A2
  fixture variants in-process (``tests/fixtures_gen.py``), builds
  reference per-check outcomes for them by running the SHIPPED fitness
  seam (``catpart-fitness`` as a subprocess over a generated
  mini-manifest — the exact production scoring path, so the reference
  records have the true report shape), drives the viewer over the
  fixtures, compares, writes rows. This mode proves the MACHINERY and
  nothing else: its outcome data is mechanical validation, never a
  rate, and must not inform the §3.4 margin (whose inputs are native
  Fidelity evidence only).

- Corpus mode (default): the full L2 population (§3.1: ALL manifest
  rows with ``kind=part`` — successes and fail-closed alike, 1,442
  rows today: Dev 1,381 + held-out 61), compared against the accepted
  fitness run's per-file ``l2`` records. This mode is margin-gated BY
  CONSTRUCTION: it refuses to run without an explicit ``--margin``
  value — the mechanical form of §3.4's declared-before-run discipline
  (the margin is the owner's decision, recorded dated in the spec §11
  BEFORE the run; it may cite native Fidelity evidence, never an
  in-browser measurement). There is deliberately no ``--limit``: the
  only population run this tool can make is the FULL population, so no
  subset rate (not even a pilot) can precede the declaration.

Comparison (§3.4, the per-file per-check drift detector): status,
error_class, failed_check, the three counts, the mesh invariants the
runner's record projects (manifold/closed/oriented/boundary_edge_count),
the bounding box (null-ness agreement + exact float equality — both
sides hold widened f32s, §3.2's parsed-equality convention), and the
warnings' class sequence (order-fixed; the human detail prose is never
compared, the §3.2 error-class convention). A mismatch names its first
diverging field.

Exclusion (§3.4's one declared exclusion, independent of the margin
value): harness-error files — browser crash, per-file timeout, page
error on a pathological file — drop out of the compared rate and are
reported PER-FILE in the note, never silent. A reference-unavailable
row (no accepted-run record, or the file missing on disk) is likewise
reported per-file and makes the run invalid: every compared row must
be match/mismatch by evidence (§3.2).

Deterministic ordering: manifest row order (the committed CSV order) /
the fixed smoke variant list. Wall-clock is measured (total + per-file
seconds on every row), never estimated.

Usage:
    python scripts/reproduction_run.py --smoke [--csv P] [--note P]
    python scripts/reproduction_run.py --margin M [--csv P] [--note P]
            [--fitness-report P] [--manifest P] [--corpus-root P]
            [--port N] [--per-file-timeout S] [--restart-every N]

Exit 0 = every row compared and matched; 1 = any mismatch,
harness-error or reference-unavailable row (each named on stderr; the
note is written either way — the evidence, not the exit code, is the
deliverable); 2 = usage/environment failure.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SITE = REPO_ROOT / "site"
PAGE = "viewer/viewer.html"
DEFAULT_MANIFEST = REPO_ROOT / "manifests" / "corpus-manifest.csv"
DEFAULT_FITNESS_DIR = REPO_ROOT / "fitness"
DATA_DIR = REPO_ROOT / "docs" / "evidence" / "data"

DEFAULT_CSV = DATA_DIR / "v5-reproduction-l2-claims.csv"
DEFAULT_SMOKE_CSV = DATA_DIR / "v5-reproduction-smoke-claims.csv"

#: §3.1: the L2 population is the manifest's ``kind=part`` rows (the
#: runner's own law; products and junk rows are out of this slice).
L2_POPULATION_KIND = "part"
SPLITS = ("dev", "held-out")

OUTCOME_MATCH = "match"
OUTCOME_MISMATCH = "mismatch"
OUTCOME_HARNESS_ERROR = "harness-error"
OUTCOME_REFERENCE_UNAVAILABLE = "reference-unavailable"

#: The runner's mesh projection (runner.py::_score_export's record:
#: ``edge_count`` is measured by the summary but NOT carried by the
#: fitness record, so it is not compared either).
MESH_FIELDS = ("manifold", "closed", "oriented", "boundary_edge_count")

CSV_FIELDS = [
    "row_id",
    "path",
    "split",
    "kind",
    "detected_version",
    "outcome",
    "python_status",
    "viewer_status",
    "python_failed_check",
    "viewer_failed_check",
    "python_error_class",
    "viewer_error_class",
    "python_vertex_count",
    "viewer_vertex_count",
    "python_triangle_count",
    "viewer_triangle_count",
    "python_degenerate_triangle_count",
    "viewer_degenerate_triangle_count",
    "mesh_equal",
    "bbox_equal",
    "warnings_equal",
    "first_divergence",
    "viewer_seconds",
    "harness_note",
]

#: The fixture machinery-smoke population (fixed, deterministic — the
#: "handful of fixture files" the phase-A acceptance names). Each row
#: proves one comparison branch; the branch annotation is what the
#: smoke note and the pytest pin assert. The ``empty-mesh`` and
#: ``nonfinite-bbox`` gate branches are unreachable on the A2 fixture
#: population (no vertices-only variant exists; named in the note).
SMOKE_VARIANTS = [
    ("geometry", "gate pass, closed, warning-free"),
    ("geometry-composite-law-curve-entries", "gate pass with warnings (composite path)"),
    ("geometry-composite-law-dedup-unordered", "gate pass with dedup warning"),
    ("geometry-composite-law-e0b-relaxed-not-manifold", "gate fail: not-manifold"),
    ("geometry-composite-law-dedup-degenerate", "gate fail: degenerate-triangles"),
    ("geometry-open-shell", "gate fail: degenerate-triangles + open-shell warning"),
    ("geometry-nan-coords", "decode failure: malformed-pool-vertex"),
    ("geometry-out-of-range-refs", "decode failure: undecoded-variant"),
    ("geometry-seebody-empty", "decode failure: missing-geometry-store"),
    ("geometry-othercontainer-bad-tail", "decode failure: malformed-store-header"),
]


class RunError(Exception):
    """An operator-facing failure: the run aborts loudly (no partial
    population rate is possible — the CSV/note are written only by the
    two modes' own completion paths)."""


def load_fixtures_gen():
    """``tests/fixtures_gen.py`` by file path — the fidelity_run.py
    convention (the one repo import, in-process fixture generation)."""
    path = REPO_ROOT / "tests" / "fixtures_gen.py"
    spec = importlib.util.spec_from_file_location("repro_fixtures_gen", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# The reference: the accepted fitness run's per-file l2 records
# ---------------------------------------------------------------------------


def resolve_reference_report(fitness_dir: Path, explicit: Path | None) -> tuple[dict, Path]:
    """Locate the Python fitness record source: the ACCEPTED run.

    Explicit ``--fitness-report`` wins; otherwise the LAST row with
    ``accepted=true`` in ``fitness/history.jsonl`` names its report.
    The note names the source (run_id + path) — the per-file comparison
    is only as good as the records it joins to.
    """
    if explicit is not None:
        if not explicit.is_file():
            raise RunError(f"--fitness-report {explicit} does not exist")
        report = json.loads(explicit.read_text(encoding="utf-8"))
        return report, explicit
    history = fitness_dir / "history.jsonl"
    if not history.is_file():
        raise RunError(f"no fitness history at {history} (pass --fitness-report)")
    accepted = None
    with history.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("accepted") is True:
                accepted = row
    if accepted is None:
        raise RunError(f"{history} has no accepted run; nothing to compare against")
    report_path = fitness_dir / accepted["report"]
    if not report_path.is_file():
        raise RunError(f"the accepted run's report is missing: {report_path}")
    return json.loads(report_path.read_text(encoding="utf-8")), report_path


def check_corpus_binding(report: dict, manifest_path: Path) -> None:
    """The manifest binds the corpus (the runner's own rule): the
    accepted report's corpus_digest must equal the sha256 of the
    manifest bytes, else the records predate this corpus and the
    comparison would join across a corpus change."""
    digest = report.get("corpus_digest")
    actual = sha256_file(manifest_path)
    if digest != actual:
        raise RunError(
            "the accepted fitness report does not bind this corpus: "
            f"report corpus_digest={digest}, manifest sha256={actual}. "
            "The reference records predate the manifest — a new accepted "
            "fitness run is required before any reproduction comparison."
        )


def reference_records(report: dict) -> dict[str, dict]:
    """sha256 -> l2 record, over the report's per-file records. Every
    manifest ``kind=part`` row carries an l2 record in a fitness report
    (unavailable included); rows without one surface as
    reference-unavailable at comparison time."""
    records = {}
    for record in report.get("files", []):
        if record.get("l2") is not None:
            records[record["sha256"]] = record
    return records


def published_l2_scalars(report: dict) -> dict[str, float | None]:
    """The published L2 scalar per split (the accepted run's rate)."""
    out = {}
    for split in SPLITS:
        block = report.get("splits", {}).get(split, {}).get("l2")
        if block is None:
            raise RunError(f"the accepted report has no L2 block for split {split!r}")
        out[split] = block.get("rate")
    return out


# ---------------------------------------------------------------------------
# The page-side outcome: what window.viewer exposes, normalized to the
# runner's l2 record shape
# ---------------------------------------------------------------------------

READ_STATE = (
    "({ gate: window.viewer.gate, error: window.viewer.error,"
    " summary: window.viewer.summary })"
)


def viewer_record(state: dict) -> dict:
    """Compose the page's per-check outcome (the §3.4 gate mirror) into
    the runner's l2 record shape. On a decode failure the gate record
    is null and the classified error object carries the class — the
    runner's ``_l2_failure`` shape (status fail, failed_check None,
    every summary component null)."""
    gate = state.get("gate")
    summary = state.get("summary")
    error = state.get("error")
    if gate is not None:
        mesh = summary.get("mesh") if summary else None
        warnings = summary.get("warnings") if summary else None
        return {
            "status": gate["status"],
            "error_class": None,
            "failed_check": gate["failed_check"],
            "vertex_count": gate["vertex_count"],
            "triangle_count": gate["triangle_count"],
            "degenerate_triangle_count": gate["degenerate_triangle_count"],
            "mesh": None if mesh is None else {k: mesh[k] for k in MESH_FIELDS},
            "bounding_box": gate["bounding_box"],
            "warning_classes": (
                None if warnings is None else [w["class"] for w in warnings]
            ),
        }
    if error is not None:
        return {
            "status": "fail",
            "error_class": error.get("error_class"),
            "failed_check": None,
            "vertex_count": None,
            "triangle_count": None,
            "degenerate_triangle_count": None,
            "mesh": None,
            "bounding_box": None,
            "warning_classes": None,
        }
    raise RunError("the page reached a terminal state with neither gate nor error")


def python_record(l2: dict) -> dict:
    """Normalize the fitness record's l2 dict to the same shape (the
    warnings' prose detail is dropped here too — never compared)."""
    warnings = l2.get("warnings")
    mesh = l2.get("mesh")
    return {
        "status": l2.get("status"),
        "error_class": l2.get("error_class"),
        "failed_check": l2.get("failed_check"),
        "vertex_count": l2.get("vertex_count"),
        "triangle_count": l2.get("triangle_count"),
        "degenerate_triangle_count": l2.get("degenerate_triangle_count"),
        "mesh": None if mesh is None else {k: mesh[k] for k in MESH_FIELDS},
        "bounding_box": l2.get("bounding_box"),
        "warning_classes": (
            None if warnings is None else [w["class"] for w in warnings]
        ),
    }


def _fmt(value) -> str:
    return repr(value)[:80]


def compare_records(py: dict, vw: dict) -> tuple[bool, bool, bool, str]:
    """The per-file per-check comparison (§3.4). Returns
    (mesh_equal, bbox_equal, warnings_equal, first_divergence) —
    first_divergence empty means everything matched. The three surface
    flags are computed independently (each is the per-surface agreement
    record the CSV carries); the divergence names the FIRST differing
    field in the fixed order: the headline checks, then the supporting
    summary surfaces, each named when it diverges."""
    mesh_equal = py["mesh"] == vw["mesh"]
    bbox_equal = py["bounding_box"] == vw["bounding_box"]
    warnings_equal = py["warning_classes"] == vw["warning_classes"]
    divergence = ""
    for field in (
        "status",
        "error_class",
        "failed_check",
        "vertex_count",
        "triangle_count",
        "degenerate_triangle_count",
    ):
        if py[field] != vw[field]:
            divergence = f"{field}: python={_fmt(py[field])} viewer={_fmt(vw[field])}"
            break
    if not divergence and not mesh_equal:
        if py["mesh"] is None or vw["mesh"] is None:
            divergence = (
                f"mesh null-ness: python={_fmt(py['mesh'] is None)} "
                f"viewer={_fmt(vw['mesh'] is None)}"
            )
        else:
            for field in MESH_FIELDS:
                if py["mesh"][field] != vw["mesh"][field]:
                    divergence = (
                        f"mesh.{field}: python={_fmt(py['mesh'][field])} "
                        f"viewer={_fmt(vw['mesh'][field])}"
                    )
                    break
    if not divergence and not bbox_equal:
        if (py["bounding_box"] is None) != (vw["bounding_box"] is None):
            divergence = (
                f"bounding_box null-ness: python={_fmt(py['bounding_box'] is None)} "
                f"viewer={_fmt(vw['bounding_box'] is None)}"
            )
        elif py["bounding_box"] is not None:
            for side in ("min", "max"):
                for axis in range(3):
                    a = py["bounding_box"][side][axis]
                    b = vw["bounding_box"][side][axis]
                    if a != b:
                        divergence = (
                            f"bounding_box.{side}[{axis}]: python={_fmt(a)} "
                            f"viewer={_fmt(b)}"
                        )
                        break
    if not divergence and not warnings_equal:
        detail = ""
        if py["warning_classes"] is not None and vw["warning_classes"] is not None:
            for i, (a, b) in enumerate(zip(py["warning_classes"], vw["warning_classes"])):
                if a != b:
                    detail = f" first diff at [{i}]: python={_fmt(a)} viewer={_fmt(b)}"
                    break
        divergence = f"warning_classes:{detail}"
    return mesh_equal, bbox_equal, warnings_equal, divergence


def margin_verdict(rate: float, published: float, margin: float) -> bool:
    """§3.4's letter: the in-browser rate must equal the published L2
    scalar within the declared margin, per split. The margin arrives
    from the owner's declaration (via --margin); it is never chosen
    here and never re-declared to absorb a failing run."""
    return abs(rate - published) <= margin


# ---------------------------------------------------------------------------
# The static serve + the browser driver (the viewer_acceptance.py pattern)
# ---------------------------------------------------------------------------


class StaticServer:
    """``python3 -m http.server`` over site/ — GET-only static files,
    the read-only serving the spec names. The corpus files never pass
    through it (they cross via the file input)."""

    def __init__(self, port: int):
        self.proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "http.server",
                str(port),
                "--bind",
                "127.0.0.1",
                "--directory",
                str(SITE),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.base = f"http://127.0.0.1:{port}"
        self.command = (
            f"python3 -m http.server {port} --bind 127.0.0.1 "
            f"--directory {SITE} (read-only static)"
        )

    def wait_ready(self, timeout: float = 10.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(f"{self.base}/index.html", timeout=1) as resp:
                    if resp.status == 200:
                        return
            except OSError:
                time.sleep(0.1)
        raise RunError("the static server never became ready")

    def stop(self) -> None:
        self.proc.terminate()
        self.proc.wait(timeout=5)


class Driver:
    """One headless Chromium driving the committed viewer page, with a
    deterministic recovery ladder (reload -> fresh context -> fresh
    browser) so one pathological file cannot take down the run
    silently: its row is a harness-error and the next file starts from
    a verified-idle page."""

    def __init__(self, playwright, base: str, per_file_timeout: float):
        self.playwright = playwright
        self.base = base
        self.per_file_timeout = per_file_timeout
        self.browser = None
        self.context = None
        self.page = None
        self.page_errors: list[str] = []
        self.requests_total = 0
        self.external_requests: list[str] = []
        self._launch()

    def _count_request(self, url: str) -> None:
        self.requests_total += 1
        if not url.startswith(self.base):
            self.external_requests.append(url)

    def _track(self, page) -> None:
        page.on("pageerror", lambda exc: self.page_errors.append(str(exc)))
        page.on("request", lambda req: self._count_request(req.url))

    def _launch(self) -> None:
        self.browser = self.playwright.chromium.launch(headless=True)
        self._new_context()

    def _new_context(self) -> None:
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self._track(self.page)
        self.page.goto(f"{self.base}/{PAGE}", wait_until="load")
        self._wait_idle()
        self.page_errors.clear()

    def _wait_idle(self, timeout: float = 20000.0) -> None:
        self.page.wait_for_function(
            "window.viewer && window.viewer.status === 'idle'", timeout=timeout
        )

    def _close(self) -> None:
        for closer in (
            lambda: self.context.close(),
            lambda: self.browser.close(),
        ):
            try:
                closer()
            except Exception:
                pass
        self.context = None
        self.page = None
        self.browser = None

    def restart(self) -> None:
        """A deterministic full relaunch (the --restart-every boundary;
        bounds any slow cumulative growth across a long population)."""
        self._close()
        self._launch()

    def recover(self) -> None:
        """The ladder after a per-file harness failure. The page may be
        mid-decode (a timed-out feed) or dead (a crash): reload first,
        then a fresh context, then a fresh browser — each verified by
        the page reaching idle."""
        try:
            self.page.reload(timeout=15000)
            self._wait_idle()
            self.page_errors.clear()
            return
        except Exception:
            pass
        try:
            self.context.close()
        except Exception:
            pass
        try:
            self._new_context()
            return
        except Exception:
            pass
        try:
            self.browser.close()
        except Exception:
            pass
        self._launch()

    def feed(self, link_path: Path) -> tuple[dict, float]:
        """Feed one file through the file input and return
        (state, seconds). The unique link name is the race-free marker:
        the wait condition (fileName === name AND terminal status) can
        only be satisfied by THIS file's outcome — the previous file's
        terminal state (a different name) can never match, and a fast
        decode that jumps straight to terminal is still caught. The
        name is embedded in the expression as a constant (json-quoted;
        it is this tool's own ``f{i}.CATPart`` token, never user data):
        probed on the pinned Playwright 1.65.2, the ``arg=`` binding
        does not reliably reach the polled function, while the embedded
        constant does."""
        name = link_path.name
        self.page_errors.clear()
        started = time.monotonic()
        self.page.set_input_files("#file-input", str(link_path))
        self.page.wait_for_function(
            f"() => window.viewer && window.viewer.fileName === {json.dumps(name)}"
            " && ['loaded','failed'].includes(window.viewer.status)",
            timeout=self.per_file_timeout * 1000,
        )
        state = self.page.evaluate(READ_STATE)
        seconds = time.monotonic() - started
        return state, seconds

    def close(self) -> None:
        self._close()


# ---------------------------------------------------------------------------
# The run loops
# ---------------------------------------------------------------------------


def prepare_links(paths: list[Path], scratch: Path) -> list[Path]:
    """One deterministic per-feed symlink (``f{i}.CATPart``) per file:
    the unique name doubles as the race-free wait marker; the corpus
    itself is never touched."""
    scratch.mkdir(parents=True, exist_ok=True)
    links = []
    for i, target in enumerate(paths):
        link = scratch / f"f{i}.CATPart"
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(target)
        links.append(link)
    return links


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def csv_row(row_id: str, path: str, split: str, kind: str, detected_version: str,
            outcome: str, py: dict | None, vw: dict | None, mesh_equal: bool,
            bbox_equal: bool, warnings_equal: bool, first_divergence: str,
            seconds: float | None, note: str) -> dict:
    def side(prefix: str, record: dict | None) -> dict:
        values = {
            f"{prefix}_status": "",
            f"{prefix}_failed_check": "",
            f"{prefix}_error_class": "",
            f"{prefix}_vertex_count": "",
            f"{prefix}_triangle_count": "",
            f"{prefix}_degenerate_triangle_count": "",
        }
        if record is not None:
            values[f"{prefix}_status"] = record["status"]
            values[f"{prefix}_failed_check"] = "" if record["failed_check"] is None else record["failed_check"]
            values[f"{prefix}_error_class"] = "" if record["error_class"] is None else record["error_class"]
            for name in ("vertex_count", "triangle_count", "degenerate_triangle_count"):
                value = record[name]
                values[f"{prefix}_{name}"] = "" if value is None else str(value)
        return values

    row = {
        "row_id": row_id,
        "path": path,
        "split": split,
        "kind": kind,
        "detected_version": detected_version,
        "outcome": outcome,
        # The per-surface agreement record: filled whenever the row was
        # actually compared (match/mismatch), empty otherwise.
        "mesh_equal": "", "bbox_equal": "", "warnings_equal": "",
        "first_divergence": first_divergence,
        "viewer_seconds": "" if seconds is None else f"{seconds:.3f}",
        "harness_note": note,
    }
    if outcome in (OUTCOME_MATCH, OUTCOME_MISMATCH):
        row["mesh_equal"] = "true" if mesh_equal else "false"
        row["bbox_equal"] = "true" if bbox_equal else "false"
        row["warnings_equal"] = "true" if warnings_equal else "false"
    row.update(side("python", py))
    row.update(side("viewer", vw))
    return row


def drive_population(driver: Driver, links: list[Path], restart_every: int,
                     on_state, on_harness_error) -> None:
    """Feed every file in the given order, containing failures per-file
    (the §3.4 exclusion discipline). ``on_state`` receives
    (index, state, seconds); ``on_harness_error`` receives
    (index, note) — both record the row; the caller owns the rows."""
    since_restart = 0
    for i, link in enumerate(links):
        try:
            state, seconds = driver.feed(link)
            on_state(i, state, seconds)
        except Exception as exc:  # noqa: BLE001 - the per-file containment boundary
            note = f"{type(exc).__name__}: {str(exc)[:160]}"
            if driver.page_errors:
                note += " | pageerror: " + " | ".join(driver.page_errors[-3:])[:160]
                driver.page_errors.clear()
            on_harness_error(i, note)
            driver.recover()
            since_restart = 0
            continue
        since_restart += 1
        if restart_every and since_restart >= restart_every:
            driver.restart()
            since_restart = 0


def exit_code_for(rows: list[dict]) -> int:
    """0 when every row is a match (§3.2: the run is valid only when
    every row is evidence-based; a harness-error or
    reference-unavailable row is a measurement not made — named here
    and in the note, never a match)."""
    bad = [row for row in rows if row["outcome"] != OUTCOME_MATCH]
    for row in bad:
        print(
            f"reproduction_run: {row['outcome']}: {row['row_id'][:16]}"
            f" {row['first_divergence'] or row['harness_note']}"[:240],
            file=sys.stderr,
        )
    return 1 if bad else 0


# ---------------------------------------------------------------------------
# Smoke mode: the fixture machinery validation
# ---------------------------------------------------------------------------


def build_reference_records_smoke(fixture_dir: Path, variants: list[str]) -> tuple[dict, dict, Path]:
    """Run the SHIPPED fitness seam (``catpart-fitness``, subprocess)
    over a generated mini-manifest so the reference records have the
    true production shape (the runner's own scoring path, unavailable
    rows included). Returns (records-by-sha, report, report_path)."""
    fitness_bin = Path(sys.executable).parent / "catpart-fitness"
    if not fitness_bin.is_file():
        which = shutil.which("catpart-fitness")
        if which is None:
            raise RunError(
                "catpart-fitness not found next to the running interpreter "
                f"({fitness_bin}) or on PATH — the smoke needs the shipped "
                "fitness seam (pip install -e . into the running venv)"
            )
        fitness_bin = Path(which)
    gen = load_fixtures_gen()
    manifest_path = fixture_dir / "smoke-manifest.csv"
    digests: dict[str, str] = {}
    with manifest_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(["sha256", "kind", "split", "path", "local_path", "magic_ok"])
        for variant in variants:
            data = gen.build_fixture("part", seed=0, variant=variant)
            digest = hashlib.sha256(data).hexdigest()
            if digest in digests.values():
                raise RunError(f"two smoke fixtures share a sha256 ({variant})")
            digests[variant] = digest
            name = f"{variant}.CATPart"
            (fixture_dir / name).write_bytes(data)
            writer.writerow([digest, "part", "dev", name, name, "yes"])
        # The runner fails closed on a split with no rows (the no-regret
        # comparison's precondition): one held-out fixture row makes the
        # mini-manifest a valid fitness population. It is measured for
        # the record's sake only — never part of the browser population
        # (the smoke's rows all report split='fixture').
        held_data = gen.build_fixture("part", seed=7, variant=None)
        held_name = "canonical-s7-heldout.CATPart"
        (fixture_dir / held_name).write_bytes(held_data)
        writer.writerow([hashlib.sha256(held_data).hexdigest(), "part", "held-out", held_name, held_name, "yes"])
    fitness_dir = fixture_dir / "fitness"
    result = subprocess.run(
        [str(fitness_bin), "--manifest", str(manifest_path), "--corpus-root", str(fixture_dir),
         "--fitness-dir", str(fitness_dir)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise RunError(
            f"catpart-fitness failed on the smoke manifest "
            f"(rc={result.returncode}): {result.stderr[-400:]}"
        )
    row = json.loads(result.stdout)
    report_path = fitness_dir / row["report"]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return reference_records(report), report, report_path


def run_smoke(csv_path: Path, note_path: Path, port: int, per_file_timeout: float) -> int:
    """The machinery smoke over the fixed fixture population. The rows
    it writes prove the machinery (page load, feed, per-check read,
    comparison, CSV write) — the outcome data is mechanical validation
    ONLY: never a rate, never a margin input (§3.4's letter)."""
    from playwright.sync_api import sync_playwright

    variants = [name for name, _ in SMOKE_VARIANTS]
    with tempfile.TemporaryDirectory(prefix="repro-smoke-") as tmp:
        fixture_dir = Path(tmp) / "fixtures"
        fixture_dir.mkdir()
        records, report, report_path = build_reference_records_smoke(fixture_dir, variants)
        feed_paths = [fixture_dir / f"{v}.CATPart" for v in variants]
        for variant, path in zip(variants, feed_paths):
            if sha256_file(path) not in records:
                raise RunError(f"the smoke fitness report lacks a record for {variant}")

        server = StaticServer(port)
        server.wait_ready()
        wall_started = time.monotonic()
        try:
            with sync_playwright() as playwright:
                driver = Driver(playwright, server.base, per_file_timeout)
                rows: list[dict] = [None] * len(variants)  # type: ignore[list-item]

                def on_state(i: int, state: dict, seconds: float) -> None:
                    variant = variants[i]
                    sha = sha256_file(feed_paths[i])
                    py = python_record(records[sha]["l2"])
                    vw = viewer_record(state)
                    mesh_equal, bbox_equal, warnings_equal, divergence = compare_records(py, vw)
                    outcome = OUTCOME_MISMATCH if divergence else OUTCOME_MATCH
                    rows[i] = csv_row(
                        variant, f"{variant}.CATPart", "fixture", "part",
                        report_record_version(report, sha), outcome, py, vw,
                        mesh_equal, bbox_equal, warnings_equal, divergence,
                        seconds, "",
                    )

                def on_harness_error(i: int, note: str) -> None:
                    variant = variants[i]
                    sha = sha256_file(feed_paths[i])
                    py = python_record(records[sha]["l2"])
                    rows[i] = csv_row(
                        variant, f"{variant}.CATPart", "fixture", "part",
                        report_record_version(report, sha), OUTCOME_HARNESS_ERROR,
                        py, None, False, False, False, "", None, note,
                    )

                links = prepare_links(feed_paths, Path(tmp) / "links")
                drive_population(driver, links, 0, on_state, on_harness_error)
                requests_total = driver.requests_total
                external_requests = list(driver.external_requests)
                driver.close()
        finally:
            server.stop()
        wall = time.monotonic() - wall_started

    write_csv(csv_path, rows)
    write_note(
        note_path,
        mode="smoke",
        rows=rows,
        wall=wall,
        csv_path=csv_path,
        reference_note=(
            f"the shipped fitness seam over a generated mini-manifest "
            f"(in-run temp report, not committed): {len(records)} l2 records"
        ),
        margin=None,
        published=None,
        served_command=server.command,
        per_file_timeout=per_file_timeout,
        requests_total=requests_total,
        external_requests=external_requests,
    )
    return exit_code_for(rows)


def report_record_version(report: dict, sha: str) -> str:
    for record in report.get("files", []):
        if record.get("sha256") == sha:
            return str(record.get("detected_version") or "")
    return ""


# ---------------------------------------------------------------------------
# Corpus mode: the full L2 population, margin-gated by construction
# ---------------------------------------------------------------------------


def load_population(manifest_path: Path) -> list[dict]:
    """The L2 population in manifest order (the committed CSV order —
    deterministic). Fail closed on unknown splits (the runner's rule)."""
    with manifest_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    population = [row for row in rows if row["kind"] == L2_POPULATION_KIND]
    if not population:
        raise RunError(f"no {L2_POPULATION_KIND!r} rows in {manifest_path}")
    for row in population:
        if row["split"] not in SPLITS:
            raise RunError(f"manifest split {row['split']!r} is not one of {SPLITS}")
    return population


def run_corpus(csv_path: Path, note_path: Path, manifest_path: Path, corpus_root: Path,
               fitness_dir: Path, margin: float, port: int, per_file_timeout: float,
               restart_every: int, explicit_report: Path | None) -> int:
    """The full L2 population run (§3.1: all 1,442 kind=part rows today
    — successes AND fail-closed alike). Requires the owner's declared
    margin (the --margin gate above)."""
    from playwright.sync_api import sync_playwright

    report, report_path = resolve_reference_report(fitness_dir, explicit_report)
    check_corpus_binding(report, manifest_path)
    records = reference_records(report)
    scalars = published_l2_scalars(report)
    population = load_population(manifest_path)

    file_paths: list[Path | None] = []
    for row in population:
        path = corpus_root / row["local_path"]
        file_paths.append(path if path.is_file() else None)

    with tempfile.TemporaryDirectory(prefix="repro-corpus-") as tmp:
        feedable = [p for p in file_paths if p is not None]
        links = prepare_links(feedable, Path(tmp))
        server = StaticServer(port)
        server.wait_ready()
        wall_started = time.monotonic()
        try:
            with sync_playwright() as playwright:
                driver = Driver(playwright, server.base, per_file_timeout)
                rows: list[dict] = [None] * len(population)  # type: ignore[list-item]

                def fill_common(i: int) -> tuple[str, str, str, dict | None, str]:
                    """(row_id, path, split, python record | None, detected_version)."""
                    row = population[i]
                    record = records.get(row["sha256"])
                    py = None if record is None else python_record(record["l2"])
                    version = "" if record is None else str(record.get("detected_version") or "")
                    return row["sha256"], row["path"], row["split"], py, version

                def on_state(i: int, state: dict, seconds: float) -> None:
                    sha, path, split, py, version = fill_common(i)
                    vw = viewer_record(state)
                    mesh_equal, bbox_equal, warnings_equal, divergence = compare_records(py, vw)
                    outcome = OUTCOME_MISMATCH if divergence else OUTCOME_MATCH
                    rows[i] = csv_row(
                        sha, path, split, L2_POPULATION_KIND, version, outcome, py, vw,
                        mesh_equal, bbox_equal, warnings_equal, divergence,
                        seconds, "",
                    )

                def on_harness_error(i: int, note: str) -> None:
                    sha, path, split, py, version = fill_common(i)
                    rows[i] = csv_row(
                        sha, path, split, L2_POPULATION_KIND, version,
                        OUTCOME_HARNESS_ERROR, py, None, False, False, False,
                        "", None, note,
                    )

                # The population loop: manifest order. Files missing on
                # disk are pre-classified reference-unavailable and never
                # fed (the browser could not measure them either); the
                # rest feed through the driver with per-file containment.
                indices = list(range(len(population)))
                for i in indices:
                    if file_paths[i] is None:
                        sha, path, split, py, version = fill_common(i)
                        note = "missing on disk: cannot be fed"
                        if py is not None and py["status"] == "unavailable":
                            note = "reference unavailable + missing on disk"
                        rows[i] = csv_row(
                            sha, path, split, L2_POPULATION_KIND, version,
                            OUTCOME_REFERENCE_UNAVAILABLE, py, None, False, False,
                            False, "", None, note,
                        )
                drive_population(driver, links, restart_every, on_state, on_harness_error)
                requests_total = driver.requests_total
                external_requests = list(driver.external_requests)
                driver.close()
        finally:
            server.stop()
        wall = time.monotonic() - wall_started

    write_csv(csv_path, rows)
    write_note(
        note_path,
        mode="corpus",
        rows=rows,
        wall=wall,
        csv_path=csv_path,
        reference_note=(
            f"{report_path.relative_to(REPO_ROOT)} (run_id {report.get('run_id')}, "
            f"corpus_digest {str(report.get('corpus_digest'))[:16]}…, manifest "
            f"{manifest_path.relative_to(REPO_ROOT)} sha256-verified against it)"
        ),
        margin=margin,
        published=scalars,
        served_command=server.command,
        per_file_timeout=per_file_timeout,
        requests_total=requests_total,
        external_requests=external_requests,
    )
    return exit_code_for(rows)


# ---------------------------------------------------------------------------
# The figures-only note (#37: every figure derivable from the CSV rows)
# ---------------------------------------------------------------------------


def write_note(note_path: Path, mode: str, rows: list[dict], wall: float, csv_path: Path,
               reference_note: str, margin: float | None, published: dict | None,
               served_command: str, per_file_timeout: float, requests_total: int,
               external_requests: list[str]) -> None:
    """The dated evidence note's figures block: a pure function of the
    run and its CSV rows. Prose curation happens before commit (the
    fidelity_run.py convention)."""
    note_path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    outcomes = Counter(row["outcome"] for row in rows)
    seconds = [float(r["viewer_seconds"]) for r in rows if r["viewer_seconds"]]
    lines = []
    if mode == "smoke":
        lines += [
            "# Reproduction harness — fixture machinery smoke (ticket #52, phase A)",
            "",
            "**MACHINERY VALIDATION ONLY — NOT A RATE.** The rows below are",
            "A2 synthetic fixtures driven to prove the harness machinery",
            "(page load, feed, per-check read, comparison, CSV write).",
            "They are not a population measurement and must not inform the",
            "§3.4 margin, whose inputs are native Fidelity evidence only.",
            "",
        ]
    else:
        lines += [
            "# Reproduction run — the full L2 population (ticket #52, phase B)",
            "",
            f"- Margin: {margin} (the owner's declared value, passed via "
            "--margin; declared-before-run per §3.4 — the dated declaration "
            "record lives in the spec §11 and the run note's prose)",
            "- No --limit exists: this run is the FULL population (§3.1)",
            "",
        ]
    lines += [
        f"- Run stamp: {stamp} (UTC)",
        f"- Serving: {served_command}",
        f"- Page requests: {requests_total} total; external: {len(external_requests)}"
        + ("" if not external_requests else " — " + "; ".join(external_requests[:5])),
        f"- Reference records: {reference_note}",
        f"- CSV: `{csv_path.relative_to(REPO_ROOT) if csv_path.is_relative_to(REPO_ROOT) else csv_path}` ({len(rows)} rows)",
        f"- Wall-clock: {wall:.1f} s (measured)",
        f"- Per-file viewer seconds: n={len(seconds)}"
        + (f", mean {statistics.mean(seconds):.3f}, max {max(seconds):.3f}" if seconds else ""),
        f"- Per-file timeout: {per_file_timeout:.0f} s (a hit records a harness-error row)",
        f"- Outcomes: {dict(sorted(outcomes.items())) or '{}'}",
    ]
    if mode == "corpus":
        by_split = {split: [row for row in rows if row["split"] == split] for split in SPLITS}
        for split, split_rows in by_split.items():
            compared = [row for row in split_rows if row["outcome"] in (OUTCOME_MATCH, OUTCOME_MISMATCH)]
            matched = sum(1 for row in compared if row["outcome"] == OUTCOME_MATCH)
            harness_errors = [row for row in split_rows if row["outcome"] == OUTCOME_HARNESS_ERROR]
            ref_unavailable = [row for row in split_rows if row["outcome"] == OUTCOME_REFERENCE_UNAVAILABLE]
            rate = (matched / len(compared)) if compared else None
            pub = (published or {}).get(split)
            lines += [
                f"- Split {split}: population {len(split_rows)}, compared {len(compared)}, "
                f"matched {matched}, mismatched {len(compared) - matched}, "
                f"harness-errors {len(harness_errors)} (excluded per §3.4, named below), "
                f"reference-unavailable {len(ref_unavailable)} (named below)",
            ]
            if rate is not None and pub is not None and margin is not None:
                delta = abs(rate - pub)
                # The §3.4 verdict, plus the conservative cross-check: the
                # same split's rate with the harness-errors counted as
                # not-pass (the published scalar's own unavailable-as-not-
                # pass convention) — both figures CSV-composable.
                conservative_rate = matched / len(split_rows) if split_rows else None
                conservative_line = ""
                if conservative_rate is not None and harness_errors:
                    conservative_line = (
                        f"; conservative cross-check (harness-errors as not-pass): "
                        f"rate {conservative_rate:.6f}, |delta| "
                        f"{abs(conservative_rate - pub):.6f} "
                        f"({'WITHIN' if margin_verdict(conservative_rate, pub, margin) else 'EXCEEDED'})"
                    )
                lines += [
                    f"  - rate {rate:.6f} vs published scalar {pub:.6f}, "
                    f"|delta| {delta:.6f} vs margin {margin} → "
                    f"{'WITHIN' if margin_verdict(rate, pub, margin) else 'EXCEEDED'}"
                    + conservative_line,
                ]
        exclusions = [row for row in rows if row["outcome"] == OUTCOME_HARNESS_ERROR]
        if exclusions:
            lines += ["", "## Harness-error rows (§3.4: excluded from the rate, named per-file)", ""]
            for row in exclusions:
                lines.append(f"- `{row['row_id'][:16]}` {row['path']}: {row['harness_note']}")
        unavailable = [row for row in rows if row["outcome"] == OUTCOME_REFERENCE_UNAVAILABLE]
        if unavailable:
            lines += ["", "## Reference-unavailable rows (no accepted-run record / missing on disk — the run is invalid)", ""]
            for row in unavailable:
                lines.append(f"- `{row['row_id'][:16]}` {row['path']}: {row['harness_note']}")
    else:
        branches = Counter(
            row["viewer_failed_check"] or row["viewer_error_class"] or "pass"
            for row in rows
            if row["outcome"] in (OUTCOME_MATCH, OUTCOME_MISMATCH)
        )
        lines.append(f"- Comparison branches exercised: {dict(sorted(branches.items()))}")
    mismatches = [row for row in rows if row["outcome"] == OUTCOME_MISMATCH]
    if mismatches:
        lines += ["", "## Mismatch rows (first divergence per row)", ""]
        for row in mismatches:
            lines.append(f"- `{row['row_id'][:16]}` {row['path']}: {row['first_divergence'][:220]}")
    lines.append("")
    note_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="reproduction_run",
        description=(
            "The V5 in-browser reproduction harness (ticket #52): --smoke for "
            "the fixture machinery validation; the full L2 population run "
            "(margin-gated, §3.4) otherwise. LOCAL ONLY, never CI (§7)."
        ),
    )
    parser.add_argument("--smoke", action="store_true",
                        help="fixture machinery smoke (the phase-A deliverable)")
    parser.add_argument("--margin", type=float, default=None,
                        help="the owner's declared margin (corpus mode REQUIRED; "
                        "refused in smoke mode)")
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--note", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--corpus-root", type=Path, default=REPO_ROOT,
                        help="where the manifest's local_path entries resolve "
                        "(default: the repository root; local_path starts with corpus/)")
    parser.add_argument("--fitness-dir", type=Path, default=DEFAULT_FITNESS_DIR)
    parser.add_argument("--fitness-report", type=Path, default=None,
                        help="explicit reference report (default: the last accepted "
                        "row of fitness/history.jsonl)")
    parser.add_argument("--port", type=int, default=8933)
    parser.add_argument("--per-file-timeout", type=float, default=300.0)
    parser.add_argument("--restart-every", type=int, default=250,
                        help="full browser relaunch every N files (0 disables; "
                        "bounds cumulative growth across the population)")
    args = parser.parse_args(argv)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        if args.smoke:
            if args.margin is not None:
                raise RunError(
                    "--margin is refused in smoke mode: the smoke is machinery "
                    "validation, never a rate (§3.4's letter)"
                )
            csv_path = args.csv or DEFAULT_SMOKE_CSV
            note_path = args.note or REPO_ROOT / "docs" / "evidence" / f"{stamp}-v5-reproduction-smoke.md"
            return run_smoke(csv_path, note_path, args.port, args.per_file_timeout)
        if args.margin is None:
            raise RunError(
                "corpus mode requires --margin: the §3.4 margin is the owner's "
                "declaration, recorded dated in the spec §11 BEFORE the run "
                "(native Fidelity evidence only — never an in-browser "
                "measurement). The harness runs the population only with that "
                "declared value passed explicitly."
            )
        if args.margin < 0:
            raise RunError("--margin must be >= 0")
        csv_path = args.csv or DEFAULT_CSV
        note_path = args.note or REPO_ROOT / "docs" / "evidence" / f"{stamp}-v5-reproduction-l2.md"
        return run_corpus(
            csv_path, note_path, args.manifest, args.corpus_root, args.fitness_dir,
            args.margin, args.port, args.per_file_timeout, args.restart_every,
            args.fitness_report,
        )
    except RunError as exc:
        print(f"reproduction_run: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
