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
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("catpart-inspect") is None or shutil.which("catpart-fitness") is None,
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
    assert report["schema_version"] == 0
    assert report["magic"] == "V5_CFV2"


def test_fitness_console_script_stub() -> None:
    proc = subprocess.run(
        ["catpart-fitness"], capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert "not implemented yet" in proc.stderr


def test_inspect_console_script_help() -> None:
    proc = subprocess.run(
        ["catpart-inspect", "--help"], capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0
    assert "catpart-inspect" in proc.stdout
    assert proc.stdout.strip().startswith("usage:")
