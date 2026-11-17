"""Verification suite for Assembly UI & Classification Tree (Ticket P3-V5).

Runs both:
- tests/test_assembly_ui.mjs (canonical suite)
- tests/independent_verify_p3_v5.mjs (independent verification suite)
under Node 18+ to verify:
- 4 Canonical Classification Badges (Placed, Identity, Unresolved, Undecodable).
- Anti-Omission Invariant (Unresolved parts never omitted or hidden).
- Anti-Masking Invariant (Undecodable placements never origin identity).
- Hierarchical instance tree view with root product row and instance rows.
- Instance Inspector panel with coordinate transform table (w-first quaternion).
- Toolbar exploded view slider (lambda in [0.0, 3.0]).
- Summary bar chips and multi-product switcher dropdown.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_TEST_SCRIPT = REPO_ROOT / "tests" / "test_assembly_ui.mjs"
INDEPENDENT_TEST_SCRIPT = REPO_ROOT / "tests" / "independent_verify_p3_v5.mjs"


def test_assembly_ui_canonical_node_suite() -> None:
    """Run the Node.js ES module canonical test suite for assembly UI."""
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js runtime not found on PATH")

    assert CANONICAL_TEST_SCRIPT.is_file(), f"Test script missing: {CANONICAL_TEST_SCRIPT}"

    proc = subprocess.run(
        [node, str(CANONICAL_TEST_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )

    assert proc.returncode == 0, (
        f"Canonical test suite failed with exit code {proc.returncode}:\n"
        f"STDOUT:\n{proc.stdout}\n"
        f"STDERR:\n{proc.stderr}"
    )


def test_assembly_ui_independent_verify_node_suite() -> None:
    """Run the independent verification test suite for assembly UI."""
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js runtime not found on PATH")

    assert INDEPENDENT_TEST_SCRIPT.is_file(), f"Test script missing: {INDEPENDENT_TEST_SCRIPT}"

    proc = subprocess.run(
        [node, str(INDEPENDENT_TEST_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )

    assert proc.returncode == 0, (
        f"Independent verification suite failed with exit code {proc.returncode}:\n"
        f"STDOUT:\n{proc.stdout}\n"
        f"STDERR:\n{proc.stderr}"
    )
