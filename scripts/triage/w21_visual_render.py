#!/usr/bin/env python3
"""W21 visual QA — shipped-viewer render harness (Bloque D14).

Renders stratified part batches through the REAL viewer (site/viewer,
WASM pkg synced from the shipped port) with Playwright/Chromium, and
captures 4 views per part for the defect hunt the scalar metrics cannot
do (W6's documented reopening: stdlib renders had ~0 specificity):

- v0 iso: the viewer's own framed default (theta=45deg, phi=63deg).
- v1 orbit: CDP-mouse drag ~110deg azimuth / ~30deg polar.
- v2 wire: wireframe toggle on, mirrored drag (spaghetti/dup-tris view).
- v3 close: wheel dolly-in ~2.2x on the orbit view (holes/inversions).

Per-part verdict material is appended to a JSONL: viewer status, gate
failed_check, summary counts, page errors, PNG paths. Batches of
<= 20 with browser.close() between them; the anti-OOM gate (no
scripts/check.sh process, free -m available > 5000) is enforced before
the first Chromium launch and re-checked between batches.

Serving is the acceptance harness's READ-ONLY static server over
site/ (scripts/viewer_acceptance.py precedent). Nothing in site/ or
port/ is modified; outputs land under --out-dir (session state) —
the committed artifacts are the later contact sheets + CSVs.

Usage:
  python -B scripts/triage/w21_visual_render.py \
      --list <w21_visual_sample.py output jsonl> \
      --out-dir ~/.local/state/catpart-parser/w21-visual \
      [--batches sub-top,sub-notmanifold] [--port 8791] [--max-bytes N]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SITE = REPO / "site"
PAGE = "viewer/viewer.html"
MIN_FREE_MB = 5000


def gate_clear() -> tuple[bool, int]:
    """No `bash scripts/check.sh` gate process, and MemAvailable
    (kB in /proc, normalized to MB) over MIN_FREE_MB. The pattern is
    anchored to `bash ` so watcher/grep command lines never match."""
    try:
        out = subprocess.run(
            ["pgrep", "-f", "^bash scripts/check.sh"], capture_output=True, text=True
        ).stdout.split()
        running = len(out)
    except OSError:
        running = 0
    with open("/proc/meminfo") as fh:
        avail_kb = next(
            int(line.split()[1]) for line in fh if line.startswith("MemAvailable:")
        )
    avail_mb = avail_kb // 1024
    return running == 0 and avail_mb > MIN_FREE_MB, avail_mb


class StaticServer:
    """python3 -m http.server over site/ — the read-only serving the
    acceptance harness uses; no server component in the deliverable."""

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

    def wait_ready(self, timeout: float = 15.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(f"{self.base}/index.html", timeout=1) as r:
                    if r.status == 200:
                        return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("static server never became ready")

    def stop(self) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def drag(page, canvas_box, dx: float, dy: float) -> None:
    """Orbit drag with real CDP mouse input (real pointer id, so the
    viewer's setPointerCapture succeeds)."""
    cx = canvas_box["x"] + canvas_box["width"] / 2
    cy = canvas_box["y"] + canvas_box["height"] / 2
    page.mouse.move(cx, cy)
    page.mouse.down()
    page.mouse.move(cx + dx, cy + dy, steps=8)
    page.mouse.up()
    page.wait_for_timeout(120)


def render_part(page, entry, png_dir, views) -> dict:
    rec = {
        "batch": entry["batch"],
        "path": entry["path"],
        "sha256": entry.get("sha256", ""),
        "family": entry.get("family", ""),
        "bytes": entry.get("bytes", 0),
        "expected_triangles": entry.get("triangles", 0),
        "views": [],
    }
    page_errors = []

    def _on_error(exc) -> None:
        page_errors.append(str(exc)[:200])

    page.on("pageerror", _on_error)
    nbytes = entry.get("bytes") or 0
    timeout_ms = min(300_000, max(60_000, 30_000 + nbytes // 100))  # ~100 B/ms
    try:
        page.set_input_files("#file-input", entry["abs_path"])
    except Exception as exc:  # noqa: BLE001 — record and continue
        rec["error"] = f"input-files: {exc}"
        return rec
    try:
        page.wait_for_function(
            "['loaded','failed'].includes(window.viewer.status)",
            timeout=timeout_ms,
        )
    except Exception:
        rec["error"] = f"timeout after {timeout_ms // 1000}s"
        return rec
    state = page.evaluate(
        """(() => ({ status: window.viewer.status, gate: window.viewer.gate,
             summary: window.viewer.summary, error: window.viewer.error,
             display: window.viewer.display,
             inspect: window.viewer.inspect }))()"""
    )
    rec["status"] = state["status"]
    rec["gate_failed_check"] = (state["gate"] or {}).get("failed_check")
    rec["triangles"] = (state["summary"] or {}).get("triangle_count")
    rec["vertices"] = (state["summary"] or {}).get("vertex_count")
    rec["display_mode"] = (state["display"] or {}).get("mode")
    rec["viewer_error"] = state["error"]
    rec["detected_version"] = (state["inspect"] or {}).get("detected_version")

    canvas = page.locator("#scene")
    box = canvas.bounding_box()
    if box is None:
        rec["error"] = rec.get("error") or "no canvas box"
        return rec
    idx = entry["_idx"]
    stem = f"{entry['batch']}-{idx:02d}-{rec['sha256'][:8] or 'nosh'}"
    for view in views:
        if view == "orbit":
            drag(page, box, 240, 60)
        elif view == "wire":
            page.click("#wire-toggle")
            drag(page, box, -240, 40)
        elif view == "close":
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.mouse.wheel(0, -900)
            page.wait_for_timeout(150)
        png = png_dir / f"{stem}.{view}.png"
        canvas.screenshot(path=str(png))
        rec["views"].append({"view": view, "png": png.name})
        if view == "wire":
            page.click("#wire-toggle")  # restore
            drag(page, box, 240, -40)  # undo the mirror drag
        if view == "close":
            page.mouse.wheel(0, 900)
            page.wait_for_timeout(120)
    if page_errors:
        rec["page_errors"] = page_errors[:5]
    page.remove_listener("pageerror", _on_error)
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--batches", default="all")
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--max-bytes", type=int, default=120_000_000)
    ap.add_argument("--views", default="iso,orbit,wire,close")
    ap.add_argument("--per-batch", type=int, default=20)
    ap.add_argument(
        "--isolate-big",
        action="store_true",
        help="parts over --max-bytes get a fresh browser each instead of a skip record",
    )
    args = ap.parse_args()

    ok, avail = gate_clear()
    if not ok:
        print(
            f"ANTI-OOM: check.sh running or memory low (available {avail} MB) — abort",
            file=sys.stderr,
        )
        sys.exit(2)
    print(f"gate clear; available {avail} MB")

    wanted = None if args.batches == "all" else set(args.batches.split(","))
    entries: dict[str, list] = {}
    with open(args.list) as fh:
        for line in fh:
            e = json.loads(line)
            if wanted is not None and e["batch"] not in wanted:
                continue
            entries.setdefault(e["batch"], []).append(e)

    views = args.views.split(",")
    server = StaticServer(args.port)
    server.wait_ready()
    jsonl = args.out_dir / "w21-visual-render.jsonl"
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as pw:
            for batch, items in entries.items():
                png_dir = args.out_dir / batch
                png_dir.mkdir(parents=True, exist_ok=True)
                browser = pw.chromium.launch(headless=True)
                page = browser.new_context(
                    viewport={"width": 1150, "height": 900}
                ).new_page()
                page.goto(f"{server.base}/{PAGE}", wait_until="load")
                page.wait_for_function(
                    "window.viewer && window.viewer.status === 'idle'",
                    timeout=20000,
                )
                done = 0
                for i, e in enumerate(items[: args.per_batch]):
                    e["_idx"] = i
                    if e.get("skip"):
                        rec = {"batch": batch, "path": e["path"], "skip": e["skip"]}
                    elif e.get("bytes", 0) > args.max_bytes and not args.isolate_big:
                        rec = {
                            "batch": batch,
                            "path": e["path"],
                            "skip": f"over-cap {e['bytes']}B",
                        }
                    else:
                        if args.isolate_big and e.get("bytes", 0) > args.max_bytes:
                            # Oversized decode: fresh browser, one part, close.
                            browser.close()
                            browser = pw.chromium.launch(headless=True)
                            page = browser.new_context(
                                viewport={"width": 1150, "height": 900}
                            ).new_page()
                            page.goto(f"{server.base}/{PAGE}", wait_until="load")
                            page.wait_for_function(
                                "window.viewer && window.viewer.status === 'idle'",
                                timeout=20000,
                            )
                            print(
                                f"[{batch}] isolated browser for {e['bytes'] // 1_000_000} MB part"
                            )
                        rec = render_part(page, e, png_dir, views)
                    with open(jsonl, "a") as out:
                        out.write(json.dumps(rec, sort_keys=True) + "\n")
                    tag = (
                        rec.get("status") or rec.get("skip") or rec.get("error") or "?"
                    )
                    print(
                        f"[{batch} {i + 1}/{len(items)}] {Path(e['path']).name}: {tag}"
                    )
                    done += 1
                browser.close()  # anti-OOM: fresh browser per batch
                print(f"[{batch}] {done} parts rendered, browser closed")
                ok, avail = gate_clear()
                if not ok:
                    print(
                        f"ANTI-OOM stop before next batch (available {avail} MB)",
                        file=sys.stderr,
                    )
                    break
    finally:
        server.stop()


if __name__ == "__main__":
    main()
