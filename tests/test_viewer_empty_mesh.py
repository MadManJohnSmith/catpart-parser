"""The viewer's empty-mesh honesty pin (viewer audit follow-up).

A part whose decode succeeds but exports zero triangles is not a load:
the page used to end at ``status === 'loaded'`` over a blank canvas, so
the user could not tell the surface was missing. The §3.4 gate already
names the outcome ``empty-mesh``; the viewer must surface that as its
failed terminal state, with the counts still on screen.

The browser pin is LOCAL ONLY (Playwright, spec §7) and skips when
Playwright or Chromium is absent, like the assembly acceptance pins; the
reference-side precondition runs everywhere.
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
#: test_composite_e0b_unpinnable_keeps_conservative).
EMPTY_MESH_VARIANT = "geometry-composite-law-e0b-unpinnable"
FILE_NAME = "vertices-only.CATPart"


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


def test_empty_mesh_fixture_exports_vertices_without_triangles(tmp_path, capsys):
    """The precondition the browser pin relies on: this file decodes to a
    pool with zero triangles (so the viewer can reach the empty-mesh arm
    with sane counts, not a decode error)."""
    from catpart.cli import main_export

    path = tmp_path / FILE_NAME
    path.write_bytes(build_fixture("part", seed=0, variant=EMPTY_MESH_VARIANT))

    code = main_export([str(path)])
    summary = json.loads(capsys.readouterr().out)

    assert code == 0
    assert summary["vertex_count"] == 12
    assert summary["triangle_count"] == 0


def test_empty_mesh_part_reports_failed_status_and_message(tmp_path):
    """Drive the shipped page headlessly: a vertices-only part must end
    ``failed`` with the named empty-mesh reason and its counts visible,
    never ``loaded`` over a blank canvas."""
    pytest.importorskip("playwright")
    if not chromium_available():
        pytest.skip("Chromium browser binary not installed in environment (spec §7)")
    from playwright.sync_api import sync_playwright

    runner = load_acceptance_runner()
    path = tmp_path / FILE_NAME
    path.write_bytes(build_fixture("part", seed=0, variant=EMPTY_MESH_VARIANT))

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
                f" && window.viewer.fileName === {json.dumps(FILE_NAME)}"
                " && ['loaded','failed'].includes(window.viewer.status)",
                timeout=30000,
            )

            status = page.evaluate("window.viewer.status")
            summary = page.evaluate("window.viewer.summary")
            error = page.evaluate("window.viewer.error")
            status_text = page.inner_text("#status")
            gate_text = page.inner_text("#gate")

            assert status == "failed", (
                f"a vertices-only part reported {status!r}: {status_text!r}"
            )
            assert summary["vertex_count"] == 12
            assert summary["triangle_count"] == 0
            assert error and error["error_class"] == "empty-mesh", error
            assert (
                "empty-mesh: 12 vertices decoded, 0 triangles" in status_text
            ), status_text

            # The failure is visible, not a dim "loaded" line: the error
            # panel names the reason and the gate keeps the counts.
            assert page.is_visible("#error-panel")
            assert page.inner_text("#error-class") == "empty-mesh"
            assert "empty-mesh" in page.inner_text("#error-detail")
            assert "fail" in gate_text and "empty-mesh" in gate_text, gate_text
            assert "12" in gate_text and "0" in gate_text, gate_text

            # No blank canvas posing as a render, and the page stays usable.
            assert not page.is_visible("#scene")
            assert page.is_visible("#drop")
            assert not page_errors, f"uncaught page errors: {page_errors}"
            browser.close()
    finally:
        server.stop()
