#!/usr/bin/env python3
"""W22 viewer acceptance (Bloque E18) — the standard CAD views, the
even-shading option, the interactive feature tree and the Bodies
section, driven headlessly over the A2 synthetic fixtures. LOCAL ONLY,
never CI (spec §7: no browsers in Actions) — the serving pattern and
the discipline are viewer_acceptance.py's (static read-only server,
window.viewer as the scripted surface, zero external requests).

What it checks:

1. Standard CAD views: Iso/Front/Top/Right buttons ease the camera
   into the CATIA-space preset for the current display mode (part
   mode here): direction + screen-up land on the resolved preset and
   the transition completes (camera-only work — no geometry pass).
2. Even shading: the flat-shading toggle flips ``viewerState.shading``
   (smooth -> flat -> smooth) with aria-pressed tracking — the
   material-level option that removes mixed-winding dark faces without
   touching the exported mesh.
3. Interactive feature tree: a feature row click highlights it,
   renders the record's byte-offset detail and sets
   ``viewerState.featureSelection``; the ``no-geometry`` badge renders
   for a part whose decode failed but whose raw bytes carry the
   CATPrtCont census (the client-side scan path).
4. Bodies: the visual-component measurement lands (``count`` >= 1);
   a multi-component mesh exposes per-component toggles (aria-pressed,
   allVisible flips); the panel stays hidden at one component.
5. No server component: every request stays on the serving origin;
   zero uncaught page errors.

Usage: python scripts/w22_viewer_acceptance.py [--port N]
Exit 0 = every check passed; 1 = a check failed; 2 = usage/environment.
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SITE = REPO_ROOT / "site"
PAGE = "viewer/viewer.html"
SCREENSHOTS = REPO_ROOT / "docs" / "evidence" / "screenshots"

FIXTURES = [
    ("geometry", "canonical"),
    ("geometry-second-store-exports", "second-store"),
    ("geometry-nan-coords", "corrupted"),
]

# The part-mode preset poses (CATIA axes) the camera must land on,
# keyed by view name: (direction target->camera, screen-up). The
# assertions tolerate 1e-3 — the ISO components are 1/sqrt(3).
PRESET_POSES = {
    "iso": ([0.57735, 0.57735, 0.57735], [0.0, 0.0, 1.0]),
    "front": ([0.0, 1.0, 0.0], [0.0, 0.0, 1.0]),
    "top": ([0.0, 0.0, 1.0], [0.0, 1.0, 0.0]),
    "right": ([1.0, 0.0, 0.0], [0.0, 0.0, 1.0]),
}


def load_fixtures_gen():
    path = REPO_ROOT / "tests" / "fixtures_gen.py"
    spec = importlib.util.spec_from_file_location("w22_fixtures_gen", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StaticServer:
    """``python3 -m http.server`` over site/ — GET-only static files."""

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

    def wait_ready(self, timeout: float = 10.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(f"{self.base}/index.html", timeout=1) as resp:
                    if resp.status == 200:
                        return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("the static server never became ready")

    def stop(self) -> None:
        self.proc.terminate()
        self.proc.wait(timeout=5)


def close_to(actual: list[float], expected: list[float], tol: float = 1e-3) -> bool:
    return all(abs(a - e) <= tol for a, e in zip(actual, expected))


def check(playwright, base: str, fixture_dir: Path, gen) -> list[str]:
    results: list[str] = []
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    requests: list[str] = []
    page.on("request", lambda req: requests.append(req.url))
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    origin = base
    page.goto(f"{base}/{PAGE}", wait_until="load")
    page.wait_for_function("window.viewer && window.viewer.status === 'idle'", timeout=15000)

    def load_variant(variant: str) -> str:
        name = ("canonical" if variant == "geometry" else variant) + ".CATPart"
        path = fixture_dir / name
        path.write_bytes(gen.build_fixture("part", seed=0, variant=variant))
        page.set_input_files("#file-input", str(path))
        page.wait_for_function(
            "['loaded','failed'].includes(window.viewer.status)", timeout=30000
        )
        return page.evaluate("window.viewer.status")

    # --- 1. standard CAD views ----------------------------------------
    status = load_variant("geometry")
    assert status == "loaded", "canonical fixture must load for the view checks"
    for view in ("iso", "front", "top", "right"):
        started = time.monotonic()
        page.click(f"#view-{view}")
        page.wait_for_function(
            "window.viewer.view && !window.viewer.view.transitioning", timeout=5000
        )
        elapsed = time.monotonic() - started
        pose = page.evaluate("window.viewer.view")
        assert pose["currentView"] == view, pose
        expected_dir, expected_up = PRESET_POSES[view]
        assert close_to(pose["dir"], expected_dir), f"{view}: direction {pose['dir']}"
        assert close_to(pose["up"], expected_up), f"{view}: screen-up {pose['up']}"
        assert elapsed < 2.0, f"{view}: transition took {elapsed:.2f}s"
    results.append(
        "CAD views: iso/front/top/right land the CATIA-space part-mode "
        "poses (direction + screen-up), each transition < 2s (camera-only)"
    )

    # The framing: the preset re-fits the model's bounding sphere with
    # the 2.2x margin; the canonical box spans ~100 units on Y.
    view = page.evaluate("window.viewer.view")
    assert view["radius"] > 0 and view["target"] is not None, view

    # --- 2. even shading (flat shading, material-only) ----------------
    assert page.evaluate("window.viewer.shading") == "smooth"
    page.click("#shading-toggle")
    assert page.evaluate("window.viewer.shading") == "flat"
    assert page.get_attribute("#shading-toggle", "aria-pressed") == "true"
    page.click("#shading-toggle")
    assert page.evaluate("window.viewer.shading") == "smooth"
    assert page.get_attribute("#shading-toggle", "aria-pressed") == "false"
    results.append(
        "even shading: smooth -> flat -> smooth (aria-pressed tracked; "
        "material flatShading only, mesh untouched)"
    )

    # --- 3. interactive feature tree ----------------------------------
    tree_html = page.evaluate("document.getElementById('feature-tree').innerHTML")
    assert "CATPrtCont" in tree_html, "the census carries the container row"
    feature_rows = page.locator("#feature-tree button.feature-row")
    if feature_rows.count() > 0:
        feature_rows.first.click()
        detail = page.evaluate("document.getElementById('feature-detail').innerText")
        assert detail and "byte" in detail, detail
        selection = page.evaluate("window.viewer.featureSelection")
        assert selection and selection["type"] and selection["firstOffset"] >= 0, selection
        selected_class = page.evaluate(
            "document.querySelector('#feature-tree button.feature-row.selected') !== null"
        )
        assert selected_class, "the clicked row must carry the selected class"
        # Toggle off.
        feature_rows.first.click()
        assert page.evaluate("window.viewer.featureSelection") is None
        results.append(
            f"feature tree: {feature_rows.count()} clickable row(s); highlight + "
            "byte-offset detail + viewerState.featureSelection tracked"
        )
    else:
        assert "no framed feature name" in tree_html
        results.append(
            "feature tree: container row only (the synthetic fixture carries no "
            "framed feature name); the interactivity path is row-delegated"
        )

    # --- 3b. the no-geometry badge (client-side scan path) ------------
    status = load_variant("geometry-nan-coords")
    assert status == "failed", "the corrupted fixture must fail the decode"
    badge = page.evaluate(
        "document.querySelector('#feature-tree .feature-badge')?.innerText || null"
    )
    assert badge == "no-geometry", f"expected the no-geometry badge, got {badge!r}"
    results.append(
        "no-geometry badge: rendered on the classified-failure part whose raw "
        "bytes still carry the CATPrtCont census (client-side scan)"
    )

    # --- 4. bodies (visual components) --------------------------------
    status = load_variant("geometry")
    assert status == "loaded"
    page.wait_for_function("window.viewer.bodies && !window.viewer.bodies.measuring")
    bodies = page.evaluate("window.viewer.bodies")
    assert bodies["count"] >= 1, bodies
    panel_visible = page.evaluate("!document.getElementById('bodies-panel').hidden")
    if bodies["count"] < 2:
        assert not panel_visible, "the panel stays hidden at one component"
    status = load_variant("geometry-second-store-exports")
    assert status == "loaded", "the second-store fixture must load"
    page.wait_for_function("window.viewer.bodies && !window.viewer.bodies.measuring")
    bodies = page.evaluate("window.viewer.bodies")
    assert bodies["count"] >= 1, bodies
    if bodies["count"] >= 2:
        panel_visible = page.evaluate("!document.getElementById('bodies-panel').hidden")
        assert panel_visible, "the panel must appear for a multi-component mesh"
        page.click("button.body-toggle[data-body='0']")
        bodies = page.evaluate("window.viewer.bodies")
        assert bodies["allVisible"] is False, bodies
        assert bodies["components"][0]["visible"] is False, bodies
        pressed = page.get_attribute("button.body-toggle[data-body='0']", "aria-pressed")
        assert pressed == "false", pressed
        page.click("#bodies-show-all")
        bodies = page.evaluate("window.viewer.bodies")
        assert bodies["allVisible"] is True and all(
            c["visible"] for c in bodies["components"]
        ), bodies
        results.append(
            f"bodies: {bodies['count']} visual components measured client-side; "
            "per-component toggle flips allVisible; show-all restores"
        )
    else:
        results.append(
            "bodies: 1 visual component on both fixtures (panel hidden — "
            "the synthetic pool never splits); the multi-component law is "
            "covered by tests/test_viewer_cadviews.mjs §9/§10"
        )

    # --- 5. screenshots for the evidence note -------------------------
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    page.click("#view-front")
    page.wait_for_function("window.viewer.view && !window.viewer.view.transitioning")
    page.screenshot(path=str(SCREENSHOTS / "w22-canonical-front.png"), full_page=False)
    page.click("#view-iso")
    page.wait_for_function("window.viewer.view && !window.viewer.view.transitioning")
    page.screenshot(path=str(SCREENSHOTS / "w22-canonical-iso.png"), full_page=False)
    results.append("screenshots: docs/evidence/screenshots/w22-canonical-{front,iso}.png")

    # --- 6. no external requests, no uncaught page errors -------------
    external = [u for u in requests if not u.startswith(origin)]
    assert not external, f"the viewer made external requests: {external}"
    assert not errors, f"uncaught page errors: {errors}"
    results.append(
        f"no server component: {len(requests)} requests, all on the serving "
        f"origin; zero uncaught page errors"
    )

    browser.close()
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="the W22 viewer's local Playwright acceptance")
    parser.add_argument("--port", type=int, default=8937, help="static serve port")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        print(
            "w22_viewer_acceptance: playwright is not installed. Local-only: "
            "python -m pip install 'playwright==1.65.2' && python -m playwright install chromium",
            file=sys.stderr,
        )
        return 2

    gen = load_fixtures_gen()
    import tempfile

    with tempfile.TemporaryDirectory(prefix="w22-viewer-acceptance-") as tmp:
        fixture_dir = Path(tmp)
        server = StaticServer(args.port)
        try:
            server.wait_ready()
            with sync_playwright() as playwright:
                results = check(playwright, server.base, fixture_dir, gen)
        finally:
            server.stop()
    print("w22 viewer acceptance — PASS")
    for row in results:
        print(f"  - {row}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
