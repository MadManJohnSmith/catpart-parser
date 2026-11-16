"""Verification suite for VirtualFileCatalog & Ingestion Coordinator (Ticket P3-V3).

Exercises the Node-compatible ES module test suite `tests/test_viewer_catalog.mjs`
under Node 18+ to verify:
- VirtualFileCatalog exact and case-insensitive stem matching (248/382 join law).
- Unresolved part tracking and listUnresolved / listResolved.
- Catalog summary and clear lifecycle.
- Zero-dependency in-browser ZIP archive extraction (STORED + DEFLATE-raw).
- Recursive directory traversal and multi-file input handling.
- Multi-product candidate list and root assembly disambiguation.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
NODE_TEST_SCRIPT = REPO_ROOT / "tests" / "test_viewer_catalog.mjs"


def test_viewer_catalog_and_ingest_node_suite() -> None:
    """Run the Node.js ES module test suite for catalog and ingestion."""
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
