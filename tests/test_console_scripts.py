"""Packaging seam: the installed console scripts behave as documented.

These tests run the actual entry points from ``[project.scripts]`` in a
subprocess. They are skipped when the package is not installed (pytest
also runs from source checkouts without an install); the temp-venv
verification and CI cover the installed case.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("catpart-inspect") is None
    or shutil.which("catpart-fitness") is None
    or shutil.which("catpart-export") is None,
    reason="console scripts not installed (pip install -e .)",
)


def test_inspect_console_script(catpart_file: Path) -> None:
    proc = subprocess.run(
        ["catpart-inspect", str(catpart_file)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    assert report["schema_version"] == 1
    assert report["magic"] == "V5_CFV2"


def test_fitness_console_script_help() -> None:
    proc = subprocess.run(
        ["catpart-fitness", "--help"], capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0
    assert "catpart-fitness" in proc.stdout
    assert proc.stdout.strip().startswith("usage:")
    # The real run (ticket #14) needs the corpus manifest; its documented
    # surfaces are the report directory and the committed history.
    assert "--manifest" in proc.stdout
    assert "history.jsonl" in proc.stdout


def test_fitness_console_script_fails_cleanly_without_manifest(tmp_path: Path) -> None:
    # Outside a repository layout the default manifest does not exist:
    # a clean error line, not a traceback.
    proc = subprocess.run(
        ["catpart-fitness"], capture_output=True, text=True, timeout=60, cwd=tmp_path
    )
    assert proc.returncode == 1
    assert proc.stdout == ""
    assert "catpart-fitness: error:" in proc.stderr
    assert "cannot read corpus manifest" in proc.stderr


def test_inspect_console_script_help() -> None:
    proc = subprocess.run(
        ["catpart-inspect", "--help"], capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0
    assert "catpart-inspect" in proc.stdout
    assert proc.stdout.strip().startswith("usage:")


def test_export_console_script(tmp_path: Path, build_fixture) -> None:
    # The G4 geometry fixture exports end-to-end: PLY written next to the
    # input, schema-versioned summary on stdout (ticket #32).
    path = tmp_path / "box.CATPart"
    path.write_bytes(build_fixture("part", seed=3, variant="geometry"))
    proc = subprocess.run(
        ["catpart-export", str(path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    summary = json.loads(proc.stdout)
    assert summary["schema_version"] == 1
    assert summary["triangle_count"] == 12
    assert path.with_suffix(".ply").is_file()


def test_export_console_script_classified_error(tmp_path: Path, catpart_file: Path) -> None:
    # A container without a CATStdCont store fails classified, not with
    # a traceback: one JSON error_class line on stderr, exit 1.
    proc = subprocess.run(
        ["catpart-export", str(catpart_file)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 1
    assert proc.stdout == ""
    error = json.loads(proc.stderr)
    assert error["error_class"] == "missing-geometry-store"
    assert error["detail"]


def test_export_console_script_help() -> None:
    proc = subprocess.run(
        ["catpart-export", "--help"], capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0
    assert "catpart-export" in proc.stdout
    assert proc.stdout.strip().startswith("usage:")
    assert "-o" in proc.stdout
