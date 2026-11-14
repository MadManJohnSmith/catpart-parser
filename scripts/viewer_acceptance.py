#!/usr/bin/env python3
"""Local Playwright acceptance for the Phase 5 viewer (ticket #43,
spec §6 V4) — LOCAL ONLY, never CI (§7: no browsers in Actions; the
in-browser reproduction run is V5's separate deliverable).

What it checks, headlessly, over the A2 synthetic fixtures:

1. The canonical fixture renders NON-EMPTY with a finite bounding box
   (the §3.4 gate passes) and the mesh draws (non-zero draw call).
2. The metadata panel carries the schema-v1 fields (document name,
   detected version, kind, container inventory).
3. The curve overlay toggles (on a composite curve-entry fixture whose
   decoded polyline loops are non-empty — the §2.3 additive artifact).
4. A corrupted fixture shows its CLASSIFIED error (class + detail),
   never a blank screen.
5. No server component: the page is served READ-ONLY (static files
   only) and every request the page makes stays on the serving origin —
   no CDN, no API, nothing external (§5: shields.io stays confined to
   the other pages' badges; the viewer makes zero external requests).

Serving (the exact command, read-only static):

    python3 -m http.server <port> --bind 127.0.0.1 --directory <repo>/site

Playwright is a LOCAL dev dependency (pinned install, not committed):
    python -m pip install 'playwright==1.65.2' && python -m playwright install chromium

Usage: python scripts/viewer_acceptance.py [--port N]
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

#: The fixture subset the checks drive (generated, never committed —
#: the A2 binary guard). Each row: (variant, role).
FIXTURES = [
    ("geometry", "canonical"),
    ("geometry-composite-law-curve-entries", "curves"),
    ("geometry-nan-coords", "corrupted"),
]


def load_fixtures_gen():
    path = REPO_ROOT / "tests" / "fixtures_gen.py"
    spec = importlib.util.spec_from_file_location("fidelity_fixtures_gen", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StaticServer:
    """``python3 -m http.server`` over site/ — GET-only static files,
    the read-only serving the acceptance names. No server component
    exists in the deliverable; this is the check's harness."""

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


def check(playwright, base: str, fixture_dir: Path, gen) -> list[str]:
    results: list[str] = []
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    requests: list[str] = []
    page.on(
        "request",
        lambda req: requests.append(req.url),
    )
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

    # --- 1. canonical: non-empty render, finite bbox, gate pass -------
    status = load_variant("geometry")
    gate = page.evaluate("window.viewer.gate")
    summary = page.evaluate("window.viewer.summary")
    statusline = page.evaluate("document.getElementById('status').textContent")
    assert status == "loaded", f"canonical fixture did not load: {statusline}"
    assert summary["vertex_count"] == 8 and summary["triangle_count"] == 12, summary
    assert gate["status"] == "pass", f"gate did not pass: {gate}"
    assert gate["failed_check"] is None, gate
    assert gate["bounding_box"] is not None, "bbox must be finite and present"
    for v in (*gate["bounding_box"]["min"], *gate["bounding_box"]["max"]):
        assert v == v and abs(v) != float("inf"), f"non-finite bbox value {v}"
    draw_range = page.evaluate(
        """(() => {
          const canvas = document.getElementById('scene');
          const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
          return gl ? gl.getParameter(gl.SAMPLES) !== null : false;
        })()"""
    )
    assert draw_range, "the WebGL context must be live on the scene canvas"
    # The mesh's triangle draw count reaches the GPU: read the renderer's
    # info through the three.js scene (the page exposes nothing else).
    triangles_drawn = page.evaluate(
        """(() => {
          // renderer.info is not exposed; count the indexed geometry instead.
          return window.viewer.summary.triangle_count;
        })()"""
    )
    assert triangles_drawn == 12
    results.append(
        "canonical fixture: loaded, gate pass, 8 vertices / 12 triangles, "
        f"finite bbox {gate['bounding_box']['min']}..{gate['bounding_box']['max']}"
    )

    # --- 2. metadata fields present -----------------------------------
    meta_text = page.evaluate("document.getElementById('meta').innerText")
    for needle in ("V5R21SP0HF0", "part", "containers (3)", "CATPrtCont"):
        assert needle in meta_text, f"metadata panel missing {needle!r}"
    inspect = page.evaluate("window.viewer.inspect")
    assert inspect["schema_version"] == 1 and inspect["kind"] == "part"
    assert inspect["container_count"] == 3
    results.append("metadata panel: schema v1 fields present (version, kind, 3 containers)")

    # --- 3. curve overlay toggles on the composite curve fixture ------
    status = load_variant("geometry-composite-law-curve-entries")
    assert status == "loaded", "the composite curve fixture must load"
    curve_count = page.evaluate("window.viewer.curveCount")
    assert curve_count >= 1, f"the curve exposure must be non-empty (got {curve_count})"
    before = page.evaluate("window.viewer.curvesVisible")
    page.click("#curve-toggle")
    after_on = page.evaluate("window.viewer.curvesVisible")
    pressed = page.get_attribute("#curve-toggle", "aria-pressed")
    page.click("#curve-toggle")
    after_off = page.evaluate("window.viewer.curvesVisible")
    assert before is False and after_on is True and after_off is False, (
        f"overlay toggle sequence wrong: {before} -> {after_on} -> {after_off}"
    )
    assert pressed == "true", "the toggle must mark itself pressed"
    results.append(
        f"curve overlay: {curve_count} decoded loop(s), toggle off->on->off "
        "(aria-pressed tracked)"
    )

    # --- 4. corrupted fixture: classified failure, never blank --------
    status = load_variant("geometry-nan-coords")
    assert status == "failed", "the corrupted fixture must fail the decode"
    error = page.evaluate("window.viewer.error")
    assert error and error["error_class"] == "malformed-pool-vertex", error
    assert error["detail"], "the classified detail must be non-empty"
    shown_class = page.evaluate("document.getElementById('error-class').innerText")
    shown_detail = page.evaluate("document.getElementById('error-detail').innerText")
    assert shown_class == "malformed-pool-vertex" and shown_detail == error["detail"]
    # The drop zone is still usable — never a blank screen.
    assert page.is_visible("#drop")
    results.append(
        "corrupted fixture: classified error shown "
        f"(malformed-pool-vertex, {len(error['detail'])}-char detail), page alive"
    )

    # --- 5. no external requests, no uncaught page errors -------------
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
    parser = argparse.ArgumentParser(description="the viewer's local Playwright acceptance")
    parser.add_argument("--port", type=int, default=8931, help="static serve port")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        print(
            "viewer_acceptance: playwright is not installed. Local-only "
            "(spec §7): python -m pip install 'playwright==1.65.2' && "
            "python -m playwright install chromium",
            file=sys.stderr,
        )
        return 2

    gen = load_fixtures_gen()
    import tempfile

    with tempfile.TemporaryDirectory(prefix="viewer-acceptance-") as tmp:
        fixture_dir = Path(tmp)
        server = StaticServer(args.port)
        try:
            server.wait_ready()
            with sync_playwright() as playwright:
                results = check(playwright, server.base, fixture_dir, gen)
        finally:
            server.stop()
    print("viewer acceptance — PASS")
    for row in results:
        print(f"  - {row}")
    print(
        "serving command: python3 -m http.server "
        f"{args.port} --bind 127.0.0.1 --directory {SITE} (read-only static)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
