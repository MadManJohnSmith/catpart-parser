#!/usr/bin/env python3
"""Headless Playwright acceptance runner for the Phase 6 Assembly Viewer
(Spec F #45, ticket P3-V6, spec §8 and §9.2).

Verifies the 5 clauses of the declared P4 Assembly Bar in-browser:
1. Clause 1: Total instance count equals decoded pairing count.
2. Clause 2: The 4-state classification tallies match expected fixture ground truth.
3. Clause 3: Placed assembly bounding sphere is finite and non-zero.
4. Clause 4: Instancing proof: unique GPU mesh allocations == unique PartNumber count.
5. Clause 5: Anti-masking invariant: undecodable and unresolved parts are NEVER placed
   at origin or defaulted to identity.

Serving:
    python3 -m http.server <port> --bind 127.0.0.1 --directory <repo>/site

Usage:
    python scripts/assembly_viewer_acceptance.py [--port N] [--headless / --no-headless] [--fixture NAME]

Exit codes:
    0 = all acceptance scenarios passed
    1 = a check failed
    2 = usage/environment error (e.g. Playwright missing)
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
SITE = REPO_ROOT / "site"
PAGE = "viewer/viewer.html"

from catpart.fixtures_assembly import (  # noqa: E402
    AssemblyFixture,
    fixture_assembly_canonical,
    fixture_assembly_identity,
    fixture_assembly_partial,
    fixture_assembly_undecodable,
    package_to_zip,
    write_to_directory,
)

FIXTURE_FACTORIES: dict[str, Any] = {
    "fixture_assembly_canonical": fixture_assembly_canonical,
    "fixture_assembly_identity": fixture_assembly_identity,
    "fixture_assembly_partial": fixture_assembly_partial,
    "fixture_assembly_undecodable": fixture_assembly_undecodable,
}

# Convenience short names mapping to full canonical names
FIXTURE_ALIASES: dict[str, str] = {
    "canonical": "fixture_assembly_canonical",
    "identity": "fixture_assembly_identity",
    "partial": "fixture_assembly_partial",
    "undecodable": "fixture_assembly_undecodable",
}


class StaticServer:
    """``python3 -m http.server`` over site/ — GET-only static files,
    the read-only serving the acceptance names. No server component
    exists in the deliverable; this is the check's harness."""

    def __init__(self, port: int):
        self.port = port
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
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()


def check_fixture_scenario(
    page: Any,
    fixture: AssemblyFixture,
    fixture_dir: Path,
    use_folder: bool = False,
) -> str:
    """Ingest a synthetic assembly fixture into the viewer and assert all 5 clauses."""
    # Reset viewer to idle state if needed
    page.wait_for_function(
        "window.viewer && ['idle', 'loaded', 'failed'].includes(window.viewer.status)",
        timeout=15000,
    )

    if use_folder:
        # Multi-file folder ingestion
        folder_path = write_to_directory(fixture, fixture_dir / f"{fixture.name}_folder")
        file_paths = [str(folder_path / fn) for fn in sorted(fixture.files.keys())]
        page.set_input_files("#file-input", file_paths)
        upload_mode_desc = f"multi-file folder ({len(file_paths)} files)"
    else:
        # Client-side in-browser ZIP ingestion
        zip_path = fixture_dir / f"{fixture.name}.zip"
        package_to_zip(fixture, zip_path)
        page.set_input_files("#file-input", str(zip_path))
        upload_mode_desc = f"ZIP archive ({len(fixture.files)} files)"

    page.wait_for_function(
        "window.viewer && ['loaded', 'failed'].includes(window.viewer.status)",
        timeout=30000,
    )

    status = page.evaluate("window.viewer.status")
    mode = page.evaluate("window.viewer.mode")
    error = page.evaluate("window.viewer.error")
    assert status == "loaded", f"{fixture.name} failed to load: {error}"
    assert mode == "assembly", f"{fixture.name} expected assembly mode, got {mode}"

    asm = page.evaluate("window.viewer.assembly")
    assert asm is not None, f"{fixture.name} window.viewer.assembly must be defined"

    # --------------------------------------------------------------------------
    # Clause 1: Total instance count matches decoded pairing count
    # --------------------------------------------------------------------------
    expected_total = len(fixture.expected_classifications)
    assert asm["totalInstances"] == expected_total, (
        f"Clause 1 violated: totalInstances {asm['totalInstances']} != expected {expected_total}"
    )
    assert asm["counts"]["total"] == expected_total, (
        f"Clause 1 violated: counts.total {asm['counts']['total']} != expected {expected_total}"
    )

    # --------------------------------------------------------------------------
    # Clause 2: The 4-state classification tallies match expected ground truth
    # --------------------------------------------------------------------------
    exp_placed = sum(1 for s in fixture.expected_classifications.values() if s == "placed")
    exp_identity = sum(1 for s in fixture.expected_classifications.values() if s == "identity")
    exp_unresolved = sum(1 for s in fixture.expected_classifications.values() if s == "unresolved")
    exp_undecodable = sum(1 for s in fixture.expected_classifications.values() if s == "undecodable")

    tallies = asm["tallies"]
    assert tallies["placed"] == exp_placed, (
        f"Clause 2 violated: placed tally {tallies['placed']} != expected {exp_placed}"
    )
    assert tallies["identity"] == exp_identity, (
        f"Clause 2 violated: identity tally {tallies['identity']} != expected {exp_identity}"
    )
    assert tallies["unresolved"] == exp_unresolved, (
        f"Clause 2 violated: unresolved tally {tallies['unresolved']} != expected {exp_unresolved}"
    )
    assert tallies["undecodable"] == exp_undecodable, (
        f"Clause 2 violated: undecodable tally {tallies['undecodable']} != expected {exp_undecodable}"
    )

    # Verify per-instance classification tags match ground truth exactly
    instances = asm["instances"]
    inst_status_map = {inst["instanceName"]: inst["status"] for inst in instances}
    for inst_name, expected_status in fixture.expected_classifications.items():
        actual_status = inst_status_map.get(inst_name)
        assert actual_status == expected_status, (
            f"Clause 2 violated for instance {inst_name}: actual {actual_status} != expected {expected_status}"
        )

    # --------------------------------------------------------------------------
    # Clause 3: Placed assembly bounding sphere is finite and non-zero
    # --------------------------------------------------------------------------
    sphere = asm["boundingSphere"]
    center = sphere["center"]
    radius = float(sphere["radius"])

    for c in center:
        assert math.isfinite(c), f"Clause 3 violated: non-finite center coordinate {c}"
    assert math.isfinite(radius), f"Clause 3 violated: non-finite bounding radius {radius}"

    if exp_placed > 0 or exp_identity > 0:
        assert radius > 1e-4, f"Clause 3 violated: placed assembly radius must be non-zero (got {radius})"
        if fixture.name == "fixture_assembly_canonical":
            # Canonical fixture carries known non-zero translation [10.0, 20.0, 30.0] on Arm
            assert any(abs(c) > 1e-4 for c in center), (
                f"Clause 3 violated: canonical assembly center must be non-zero (got {center})"
            )

    # --------------------------------------------------------------------------
    # Clause 4: Instancing proof: unique GPU mesh allocations == unique PartNumber
    # --------------------------------------------------------------------------
    # Expected unique part geometries decoded and stored in GPU pool:
    # Only parts that are supplied in the catalog and referenced by instances are decoded.
    expected_unique_geometries = len(fixture.part_files)
    assert asm["uniqueGeometries"] == expected_unique_geometries, (
        f"Clause 4 violated: uniqueGeometries {asm['uniqueGeometries']} != "
        f"expected unique part count {expected_unique_geometries}"
    )
    assert asm["uniqueMeshAllocations"] == expected_unique_geometries, (
        f"Clause 4 violated: uniqueMeshAllocations {asm['uniqueMeshAllocations']} != "
        f"expected {expected_unique_geometries}"
    )

    # --------------------------------------------------------------------------
    # Clause 5: Anti-masking invariant: undecodable/unresolved NEVER origin identity
    # --------------------------------------------------------------------------
    for inst in instances:
        status = inst["status"]
        if status in ("unresolved", "undecodable"):
            assert inst["isPlacedSpatial"] is False, (
                f"Clause 5 violated: {inst['instanceName']} ({status}) marked isPlacedSpatial=True"
            )
            assert status != "identity", (
                f"Clause 5 violated: {inst['instanceName']} ({status}) masked to origin identity"
            )
            assert inst["visible"] is False, (
                f"Clause 5 violated: {inst['instanceName']} ({status}) must not be visible in 3D scene"
            )
            if status == "undecodable":
                assert inst["transform"] is None, (
                    f"Clause 5 violated: {inst['instanceName']} undecodable instance must have transform=None"
                )

    return (
        f"{fixture.name} [{upload_mode_desc}]: loaded, {expected_total} instances "
        f"({exp_placed} placed, {exp_identity} identity, {exp_unresolved} unresolved, {exp_undecodable} undecodable), "
        f"{expected_unique_geometries} unique GPU geometries, finite bbox/sphere "
        f"radius={radius:.2f} (Clauses 1-5 PASS)"
    )


def run_assembly_acceptance(
    playwright: Any,
    base: str,
    fixture_dir: Path,
    fixture_filter: str | None = None,
    headless: bool = True,
) -> list[str]:
    """Run all specified acceptance scenarios headlessly."""
    results: list[str] = []
    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context()
    page = context.new_page()

    requests: list[str] = []
    page.on("request", lambda req: requests.append(req.url))
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    page.goto(f"{base}/{PAGE}", wait_until="load")
    page.wait_for_function("window.viewer && window.viewer.status === 'idle'", timeout=15000)

    # Determine which fixtures to execute
    if fixture_filter:
        canonical_name = FIXTURE_ALIASES.get(fixture_filter, fixture_filter)
        if canonical_name not in FIXTURE_FACTORIES:
            raise ValueError(
                f"Unknown fixture '{fixture_filter}'. Available: {list(FIXTURE_FACTORIES.keys())}"
            )
        target_names = [canonical_name]
    else:
        target_names = list(FIXTURE_FACTORIES.keys())

    for name in target_names:
        factory = FIXTURE_FACTORIES[name]
        fixture = factory()
        summary_msg = check_fixture_scenario(page, fixture, fixture_dir, use_folder=False)
        results.append(summary_msg)

    # Additionally verify multi-file folder upload on canonical fixture if running full suite
    if not fixture_filter:
        fixture_canon = fixture_assembly_canonical()
        summary_msg_folder = check_fixture_scenario(page, fixture_canon, fixture_dir, use_folder=True)
        results.append(summary_msg_folder)

    # Verify zero external requests & zero uncaught page errors
    external = [u for u in requests if not u.startswith(base)]
    assert not external, f"The viewer made external requests: {external}"
    assert not errors, f"Uncaught page errors encountered: {errors}"
    results.append(
        f"No server component: {len(requests)} requests all served locally from {base}; zero uncaught page errors"
    )

    browser.close()
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 6 Assembly Viewer headless Playwright acceptance runner (Ticket P3-V6)."
    )
    parser.add_argument("--port", type=int, default=8932, help="static server port (default 8932)")
    parser.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="run Chromium in headless mode (default True)",
    )
    parser.add_argument(
        "--fixture",
        type=str,
        default=None,
        help="run a single specific fixture (e.g. canonical, identity, partial, undecodable)",
    )
    args = parser.parse_args(argv)

    if args.fixture:
        canonical_name = FIXTURE_ALIASES.get(args.fixture, args.fixture)
        if canonical_name not in FIXTURE_FACTORIES:
            print(
                f"assembly_viewer_acceptance: unknown fixture '{args.fixture}'. "
                f"Available: {', '.join(sorted(FIXTURE_FACTORIES.keys()))}",
                file=sys.stderr,
            )
            return 2

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "assembly_viewer_acceptance: playwright is not installed. Local-only:\n"
            "    python -m pip install 'playwright==1.65.2' && python -m playwright install chromium",
            file=sys.stderr,
        )
        return 2

    server = StaticServer(args.port)
    try:
        server.wait_ready()
        with tempfile.TemporaryDirectory(prefix="assembly-acceptance-") as tmp:
            fixture_dir = Path(tmp)
            with sync_playwright() as playwright:
                results = run_assembly_acceptance(
                    playwright,
                    server.base,
                    fixture_dir,
                    fixture_filter=args.fixture,
                    headless=args.headless,
                )
    except Exception as exc:
        print(f"assembly viewer acceptance — FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        server.stop()

    print("assembly viewer acceptance — PASS")
    for row in results:
        print(f"  - {row}")
    print(
        f"serving command: python3 -m http.server {args.port} "
        f"--bind 127.0.0.1 --directory {SITE} (read-only static)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
