"""The V5 reproduction harness's machinery pin (ticket #52, phase A).

Spec: docs/specs/phase5-viewer-spec.md §3.4 (the margin discipline AS
AMENDED), §4 (outputs: note + CSV), §6 V5, §7 (real-browser runs stay
LOCAL — never CI).

Three pins, all FIXTURE- OR ARTIFACT-ONLY — none drives a population
subset (§3.4's letter: no in-browser rate data before the owner's
margin declaration):

1. ``test_margin_arithmetic`` — pure arithmetic, no browser, no rate
   data: the §3.4 verdict function's contract (|rate − published| ≤
   margin; margin 0 admits only equality).
2. ``test_reproduction_smoke_fixture_mode`` — the browser machinery
   smoke over the fixed A2 fixture population (the harness's own
   ``--smoke`` mode): the page loads, every fixture feeds, the per-check
   outcome reads back through ``window.viewer``, every row compares
   against the shipped fitness seam's records (``catpart-fitness`` over
   a generated mini-manifest — the production scoring path), and the
   CSV + figures-note land. Its outcome data is MECHANICAL VALIDATION
   ONLY — never a rate, never a margin input.
3. ``test_corpus_mode_requires_margin`` + ``test_reference_records_join``
   — the corpus mode's §3.4 gate (the loud margin refusal) and the
   reference-records machinery (accepted-run resolution, corpus-digest
   binding, the 1,442-row join) against the committed artifacts only.

The browser pin skips when Playwright or Chromium is absent (CI): the
gate stays corpus-free and browser-free; locally it runs.
"""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "reproduction_run.py"


def load_harness():
    spec = importlib.util.spec_from_file_location("reproduction_run", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rr = load_harness()


def chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    try:
        with sync_playwright() as playwright:
            return Path(playwright.chromium.executable_path).exists()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 1. The §3.4 verdict arithmetic (pure; runs everywhere incl. CI)
# ---------------------------------------------------------------------------


def test_margin_arithmetic() -> None:
    assert rr.margin_verdict(0.7480086893555394, 0.7480086893555394, 0.0)
    assert not rr.margin_verdict(0.6, 0.5, 0.0), "margin 0 admits only equality"
    assert rr.margin_verdict(0.6, 0.5, 0.1)
    assert not rr.margin_verdict(0.6, 0.5, 0.099999)
    assert rr.margin_verdict(0.4, 0.5, 0.1), "the delta is signed-agnostic"
    assert not rr.margin_verdict(0.4, 0.5, 0.05)


def test_compare_records_fields_and_divergence_order() -> None:
    def rec(**kw):
        base = dict(
            status="pass",
            error_class=None,
            failed_check=None,
            vertex_count=8,
            triangle_count=12,
            degenerate_triangle_count=0,
            mesh={"manifold": True, "closed": True, "oriented": True, "boundary_edge_count": 0},
            bounding_box={"min": [0.0, 0.0, 0.0], "max": [20.0, 100.0, 60.0]},
            warning_classes=[],
        )
        base.update(kw)
        return base

    # Full agreement: empty divergence, all surface flags true.
    assert rr.compare_records(rec(), rec()) == (True, True, True, "")
    # A decode-failure record shape (everything null) compares equal.
    fail = dict(
        status="fail", error_class="undecoded-variant", failed_check=None,
        vertex_count=None, triangle_count=None, degenerate_triangle_count=None,
        mesh=None, bounding_box=None, warning_classes=None,
    )
    assert rr.compare_records(rec(**fail), rec(**fail)) == (True, True, True, "")
    # The headline checks diverge first; the surfaces still report their
    # own agreement (the CSV's per-surface record).
    mesh_bad = {"manifold": False, "closed": False, "oriented": False, "boundary_edge_count": 4}
    m, b, w, d = rr.compare_records(rec(failed_check="not-manifold", mesh=mesh_bad), rec())
    assert d.startswith("failed_check:") and (m, b, w) == (False, True, True)
    # Exact float equality on the bbox (both sides hold widened f32s).
    _, _, _, d = rr.compare_records(rec(bounding_box={"min": [0.0, 0.0, 0.0], "max": [20.0, 100.0, 60.000001]}), rec())
    assert d.startswith("bounding_box.max[2]:")
    # Warning class sequences compare in order; details are not carried.
    _, _, _, d = rr.compare_records(rec(warning_classes=["open-shell"]), rec())
    assert d.startswith("warning_classes")
    # The counts are compared (the drift detector's supporting surface).
    _, _, _, d = rr.compare_records(rec(triangle_count=11), rec())
    assert d.startswith("triangle_count:")


# ---------------------------------------------------------------------------
# 2. The browser machinery smoke (fixtures only; skips without Chromium)
# ---------------------------------------------------------------------------


def test_reproduction_smoke_fixture_mode(tmp_path: Path) -> None:
    if not chromium_available():
        pytest.skip("playwright/chromium not installed (local-only tool, spec §7)")
    csv_path = tmp_path / "repro-smoke-claims.csv"
    note_path = tmp_path / "smoke-note.md"
    code = rr.main(["--smoke", "--csv", str(csv_path), "--note", str(note_path)])
    assert code == 0, "the fixture machinery smoke reported non-match rows (see stderr)"

    with csv_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == len(rr.SMOKE_VARIANTS), "the fixed smoke population must land whole"
    # Constant row width (the claims-CSV hygiene the gate enforces).
    widths = {len(row) for row in rows}
    assert len(widths) == 1, f"CSV rows shifted columns: widths {widths}"
    assert {row["outcome"] for row in rows} == {"match"}, "every fixture row must match"
    assert {row["split"] for row in rows} == {"fixture"}, "smoke rows are fixture rows, never split rates"
    assert {row["kind"] for row in rows} == {"part"}

    by_id = {row["row_id"]: row for row in rows}
    # The comparison branches the fixtures reach (each fixture is pinned
    # to its expected per-check outcome — the mechanical proof that the
    # page's gate mirror and the Python records agree through every
    # branch the fixtures can produce).
    assert by_id["geometry"]["python_failed_check"] == "", "canonical fixture must gate-pass"
    assert by_id["geometry-composite-law-e0b-relaxed-not-manifold"]["python_failed_check"] == "not-manifold"
    assert by_id["geometry-composite-law-dedup-degenerate"]["python_failed_check"] == "degenerate-triangles"
    assert by_id["geometry-nan-coords"]["python_error_class"] == "malformed-pool-vertex"
    assert by_id["geometry-out-of-range-refs"]["python_error_class"] == "undecoded-variant"
    assert by_id["geometry-seebody-empty"]["python_error_class"] == "missing-geometry-store"
    assert by_id["geometry-othercontainer-bad-tail"]["python_error_class"] == "malformed-store-header"
    # The viewer side agrees on every pinned row (the machinery under test).
    for row_id, row in by_id.items():
        assert row["python_failed_check"] == row["viewer_failed_check"], row_id
        assert row["python_error_class"] == row["viewer_error_class"], row_id
        assert row["mesh_equal"] == "true" and row["bbox_equal"] == "true" and row["warnings_equal"] == "true", row_id

    # The figures-note carries the not-a-rate label.
    note = note_path.read_text(encoding="utf-8")
    assert "MACHINERY VALIDATION ONLY" in note
    assert "NOT A RATE" in note


# ---------------------------------------------------------------------------
# 3. The corpus mode's §3.4 gate + the reference-records machinery
#    (committed artifacts only; no browser, no corpus binaries)
# ---------------------------------------------------------------------------


def test_corpus_mode_requires_margin(tmp_path: Path) -> None:
    # The loud refusal: the population run cannot start without the
    # owner's declared margin (the mechanical form of declared-before-
    # run, §3.4). Exit 2 = usage/environment failure.
    assert rr.main(["--csv", str(tmp_path / "x.csv"), "--note", str(tmp_path / "n.md")]) == 2
    assert rr.main(["--margin", "-0.1", "--csv", str(tmp_path / "x.csv"), "--note", str(tmp_path / "n.md")]) == 2
    # The smoke refuses a margin too (machinery validation is never a rate).
    assert rr.main(["--smoke", "--margin", "0", "--csv", str(tmp_path / "x.csv"), "--note", str(tmp_path / "n.md")]) == 2


def test_reference_records_join_the_population() -> None:
    """The accepted run's records join every manifest part row — the
    machinery check that pins the phase-B comparison's reference side
    to the committed artifacts (runs on the committed manifest +
    history; corpus binaries never read)."""
    report, report_path = rr.resolve_reference_report(rr.DEFAULT_FITNESS_DIR, None)
    assert report.get("accepted") is True
    rr.check_corpus_binding(report, rr.DEFAULT_MANIFEST)
    records = rr.reference_records(report)
    population = rr.load_population(rr.DEFAULT_MANIFEST)
    assert len(population) == 1442, "the §3.1 L2 population (1,381 dev + 61 held-out)"
    missing = [row["sha256"] for row in population if row["sha256"] not in records]
    assert not missing, f"{len(missing)} population rows lack an accepted-run record"
    scalars = rr.published_l2_scalars(report)
    for split in rr.SPLITS:
        assert scalars[split] is not None, f"published scalar missing for {split}"
    splits = {row["split"] for row in population}
    assert splits == set(rr.SPLITS)
