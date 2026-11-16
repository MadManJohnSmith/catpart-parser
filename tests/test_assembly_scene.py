"""Verification suite for 3D Spatial Assembly Placement & Scene Graph (Ticket P3-V4).

Exercises the Node-compatible ES module test suite `tests/test_assembly_scene.mjs`
under Node 18+ to verify:
- Coordinate transformation B = R_X(-pi/2) and inverse B^{-1} = R_X(+pi/2).
- Matrix composition from 7-tuple [tx, ty, tz, qw, qx, qy, qz].
- Basis transformation M_Three = B * M_CATIA * B^{-1}.
- Geometry pooling and GPU buffer deduplication contract (unique geometry allocations == unique PartNumber count).
- Exploded view displacement math and non-accumulation.
- Scene graph hierarchy, AssemblyRoot, and userData tagging.
- Bounding box, bounding sphere, and camera framing.
- Visibility toggles and instance isolation.
- Anti-masking invariant: undecodable placements never defaulted to identity.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
NODE_TEST_SCRIPT = REPO_ROOT / "tests" / "test_assembly_scene.mjs"


def test_assembly_scene_node_suite() -> None:
    """Run the Node.js ES module test suite for assembly scene graph and placement."""
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js runtime not found on PATH")

    assert NODE_TEST_SCRIPT.is_file(), f"Test script missing: {NODE_TEST_SCRIPT}"

    proc = subprocess.run(
        [node, str(NODE_TEST_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )

    assert proc.returncode == 0, (
        f"Node test suite failed with exit code {proc.returncode}:\n"
        f"STDOUT:\n{proc.stdout}\n"
        f"STDERR:\n{proc.stderr}"
    )
