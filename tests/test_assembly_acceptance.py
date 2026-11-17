"""Pytest integration and verification suite for the Phase 6 Assembly Viewer
Acceptance Runner (Ticket P3-V6 under Spec F #45, spec §8 and §9.2).

Verifies:
1. The acceptance runner CLI help, usage, and argument validation.
2. Synthetic assembly fixture generation, ZIP archive packaging, and folder writing.
3. In-browser headless Playwright acceptance across all 4 canonical synthetic fixtures:
   - fixture_assembly_canonical (3 instances, 3 placed)
   - fixture_assembly_identity (2 instances, 2 identity origin)
   - fixture_assembly_partial (4 instances: 2 placed, 2 unresolved)
   - fixture_assembly_undecodable (2 instances: 2 undecodable, anti-masked)
4. Graceful skipping when Playwright or Chromium is absent in CI or non-browser environments.
"""

from __future__ import annotations

import importlib.util
import socket
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from catpart.fixtures_assembly import (
    fixture_assembly_canonical,
    fixture_assembly_identity,
    fixture_assembly_partial,
    fixture_assembly_undecodable,
    package_to_zip,
    write_to_directory,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_SCRIPT = REPO_ROOT / "scripts" / "assembly_viewer_acceptance.py"


def load_acceptance_runner():
    spec = importlib.util.spec_from_file_location("assembly_viewer_acceptance", ACCEPTANCE_SCRIPT)
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


def test_acceptance_script_cli_help() -> None:
    """Verify scripts/assembly_viewer_acceptance.py --help returns exit code 0 and lists flags."""
    assert ACCEPTANCE_SCRIPT.is_file(), f"Acceptance script missing: {ACCEPTANCE_SCRIPT}"
    proc = subprocess.run(
        [sys.executable, str(ACCEPTANCE_SCRIPT), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "--port" in proc.stdout
    assert "--headless" in proc.stdout
    assert "--fixture" in proc.stdout


def test_acceptance_script_cli_unknown_fixture() -> None:
    """Verify unknown fixture argument results in exit code 2 usage error."""
    assert ACCEPTANCE_SCRIPT.is_file(), f"Acceptance script missing: {ACCEPTANCE_SCRIPT}"
    proc = subprocess.run(
        [sys.executable, str(ACCEPTANCE_SCRIPT), "--fixture", "nonexistent_unknown_fixture"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2
    assert "unknown fixture" in proc.stderr


@pytest.mark.parametrize(
    "factory, expected_counts",
    [
        (fixture_assembly_canonical, {"total": 3, "placed": 3, "identity": 0, "unresolved": 0, "undecodable": 0}),
        (fixture_assembly_identity, {"total": 2, "placed": 0, "identity": 2, "unresolved": 0, "undecodable": 0}),
        (fixture_assembly_partial, {"total": 4, "placed": 2, "identity": 0, "unresolved": 2, "undecodable": 0}),
        (fixture_assembly_undecodable, {"total": 2, "placed": 0, "identity": 0, "unresolved": 0, "undecodable": 2}),
    ],
)
def test_assembly_fixture_generation_and_packaging(tmp_path: Path, factory, expected_counts: dict[str, int]) -> None:
    """Verify fixture generation, file inventory, ZIP packaging, and directory export."""
    fixture = factory()

    # Verify basic fixture properties
    assert fixture.name.startswith("fixture_assembly_")
    assert fixture.product_filename in fixture.files
    assert fixture.files[fixture.product_filename] == fixture.product_bytes
    for part_name in fixture.part_files:
        assert part_name in fixture.files
        assert len(fixture.files[part_name]) > 0

    # Verify classification tallies match expected
    classifications = fixture.expected_classifications
    assert len(classifications) == expected_counts["total"]
    for status_key in ("placed", "identity", "unresolved", "undecodable"):
        actual_count = sum(1 for s in classifications.values() if s == status_key)
        assert actual_count == expected_counts[status_key], f"Mismatch for status {status_key} on {fixture.name}"

    # Verify ZIP packaging
    zip_path = tmp_path / f"{fixture.name}.zip"
    package_to_zip(fixture, zip_path)
    assert zip_path.is_file()

    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = set(zf.namelist())
        assert namelist == set(fixture.files.keys())
        for fn, expected_bytes in fixture.files.items():
            actual_bytes = zf.read(fn)
            assert actual_bytes == expected_bytes, f"ZIP payload mismatch for {fn}"

    # Verify directory export
    folder_path = tmp_path / f"{fixture.name}_dir"
    write_to_directory(fixture, folder_path)
    assert folder_path.is_dir()
    for fn, expected_bytes in fixture.files.items():
        disk_file = folder_path / fn
        assert disk_file.is_file()
        assert disk_file.read_bytes() == expected_bytes


def test_live_browser_assembly_acceptance_canonical() -> None:
    """Run headless Playwright acceptance over canonical fixture in-browser (Clauses 1-5)."""
    pytest.importorskip("playwright")
    if not chromium_available():
        pytest.skip("Chromium browser binary not installed in environment (spec §7)")

    runner = load_acceptance_runner()
    port = find_free_port()
    exit_code = runner.main(["--fixture", "canonical", "--port", str(port)])
    assert exit_code == 0, "Live canonical acceptance run failed"


def test_live_browser_assembly_acceptance_full_suite() -> None:
    """Run full headless Playwright acceptance suite over all 4 fixtures + folder upload."""
    pytest.importorskip("playwright")
    if not chromium_available():
        pytest.skip("Chromium browser binary not installed in environment (spec §7)")

    runner = load_acceptance_runner()
    port = find_free_port()
    exit_code = runner.main(["--port", str(port)])
    assert exit_code == 0, "Full live assembly acceptance suite failed"
