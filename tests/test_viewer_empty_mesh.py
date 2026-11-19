"""The viewer's no-surface honesty pins (viewer audit follow-up).

Two distinct zero-triangle outcomes must never be conflated (2026-11-19,
``docs/evidence/2026-11-19-no-surface-fallback.md``):

- a part that decoded **carriers** (pool points, point runs, law-pinned
  ``33 32`` segments) opens as exactly that — a labelled point cloud,
  never a surface, with the §3.4 gate still recording ``empty-mesh``;
- a part with **nothing** to display (0 points / 0 segments / 0
  triangles) keeps a named failure, never a blank "loaded" canvas.

The browser pins are LOCAL ONLY (Playwright, spec §7) and skip when
Playwright or Chromium is absent, like the assembly acceptance pins; the
reference-side preconditions run everywhere.
"""

from __future__ import annotations

import importlib.util
import json
import socket
from pathlib import Path

import pytest

from fixtures_gen import build_fixture

REPO_ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_SCRIPT = REPO_ROOT / "scripts" / "viewer_acceptance.py"

#: The vertices-only fixture: rep 0's dropped loop is unpinnable, the
#: store-level gate stays conservative — 12 decoded vertices, 0
#: triangles (tests/test_composite_export.py::
#: test_composite_e0b_unpinnable_keeps_conservative). Its pool points are
#: the display carriers.
CARRIERS_VARIANT = "geometry-composite-law-e0b-unpinnable"
CARRIERS_FILE = "vertices-only.CATPart"

#: The 0/0/0 fixture: a store-less shape with no CATPrtCont block, no
#: pool, no point run and no curve record. It keeps its classified
#: failure (missing-geometry-store), never a blank load.
EMPTY_VARIANT = "geometry-seebody-empty"
EMPTY_FILE = "nothing-to-show.CATPart"


def load_acceptance_runner():
    spec = importlib.util.spec_from_file_location("viewer_acceptance", ACCEPTANCE_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_carrier_fixture_exports_points_without_triangles(tmp_path, capsys):
    """The precondition the browser pin relies on: this file decodes to a
    pool with zero triangles, so the viewer takes the display-carrier arm
    with sane counts, not a decode error."""
    from catpart.cli import main_export

    path = tmp_path / CARRIERS_FILE
    path.write_bytes(build_fixture("part", seed=0, variant=CARRIERS_VARIANT))

    code = main_export([str(path)])
    summary = json.loads(capsys.readouterr().out)

    assert code == 0
    assert summary["vertex_count"] == 12
    assert summary["triangle_count"] == 0
    display = summary["no_surface_display"]
    assert display["surface"] is False
    assert display["point_count"] == 12
    assert display["curve_segment_count"] == 0
    assert display["label"] == "no surface — showing 12 points, 0 curve segments"


def test_empty_fixture_has_no_displayable_carrier(tmp_path, capsys):
    """The 0/0/0 precondition: this file raises its named class, so the
    viewer must keep the failed terminal state."""
    from catpart.cli import main_export

    path = tmp_path / EMPTY_FILE
    path.write_bytes(build_fixture("part", seed=0, variant=EMPTY_VARIANT))

    code = main_export([str(path)])
    assert code == 1
    assert "missing-geometry-store" in capsys.readouterr().err


def test_carrier_part_opens_as_a_labelled_point_cloud(tmp_path):
    """Drive the shipped page headlessly: a vertices-only part opens as the
    decoded point cloud, labelled, never as a surface render."""
    pytest.importorskip("playwright")
    if not chromium_available():
        pytest.skip("Chromium browser binary not installed in environment (spec §7)")
    from playwright.sync_api import sync_playwright

    runner = load_acceptance_runner()
    path = tmp_path / CARRIERS_FILE
    path.write_bytes(build_fixture("part", seed=0, variant=CARRIERS_VARIANT))

    server = runner.StaticServer(find_free_port())
    try:
        server.wait_ready()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page_errors: list[str] = []
            page.on("pageerror", lambda exc: page_errors.append(str(exc)))

            page.goto(f"{server.base}/{runner.PAGE}", wait_until="load")
            page.wait_for_function(
                "window.viewer && window.viewer.status === 'idle'", timeout=15000
            )
            page.set_input_files("#file-input", str(path))
            page.wait_for_function(
                "() => window.viewer"
                f" && window.viewer.fileName === {json.dumps(CARRIERS_FILE)}"
                " && ['loaded','failed'].includes(window.viewer.status)",
                timeout=30000,
            )

            status = page.evaluate("window.viewer.status")
            display = page.evaluate("window.viewer.display")
            error = page.evaluate("window.viewer.error")
            gate_text = page.inner_text("#gate")
            label = page.inner_text("#display-label-text")

            assert status == "loaded", f"the carrier part reported {status!r}"
            assert display["mode"] == "no-surface", display
            assert display["pointCount"] == 12 and display["curveSegmentCount"] == 0
            assert display["drawn"]["points"] is True
            assert label == "no surface — showing 12 points, 0 curve segments"
            assert page.is_visible("#display-label")
            assert page.is_visible("#scene")
            assert error is None
            # The gate still records the truth: no triangles, empty-mesh.
            assert "empty-mesh" in gate_text, gate_text
            assert not page_errors, f"uncaught page errors: {page_errors}"
            browser.close()
    finally:
        server.stop()


def test_part_with_no_carrier_keeps_its_named_failure(tmp_path):
    """The 0/0/0 pin: nothing displayable is a named failure, not a blank
    canvas pretending to be a render."""
    pytest.importorskip("playwright")
    if not chromium_available():
        pytest.skip("Chromium browser binary not installed in environment (spec §7)")
    from playwright.sync_api import sync_playwright

    runner = load_acceptance_runner()
    path = tmp_path / EMPTY_FILE
    path.write_bytes(build_fixture("part", seed=0, variant=EMPTY_VARIANT))

    server = runner.StaticServer(find_free_port())
    try:
        server.wait_ready()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"{server.base}/{runner.PAGE}", wait_until="load")
            page.wait_for_function(
                "window.viewer && window.viewer.status === 'idle'", timeout=15000
            )
            page.set_input_files("#file-input", str(path))
            page.wait_for_function(
                "() => window.viewer"
                f" && window.viewer.fileName === {json.dumps(EMPTY_FILE)}"
                " && ['loaded','failed'].includes(window.viewer.status)",
                timeout=30000,
            )
            status = page.evaluate("window.viewer.status")
            error = page.evaluate("window.viewer.error")
            assert status == "failed", status
            assert error and error["error_class"] == "missing-geometry-store", error
            assert page.is_visible("#error-panel")
            assert not page.is_visible("#scene")
            assert page.is_visible("#drop")
            browser.close()
    finally:
        server.stop()
