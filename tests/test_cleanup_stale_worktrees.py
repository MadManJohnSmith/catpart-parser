"""Tests for the stale worktree and branch cleanup automation script.

Verifies the invariants and safeguards of scripts/triage/cleanup_stale_worktrees.sh:
- Default mode is dry-run (no mutations).
- Primary repository checkout is never removed.
- Protected branches (main, gh-pages) are never deleted.
- Flag parsing and error handling for forced deletions.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CLEANUP_SCRIPT = REPO_ROOT / "scripts" / "triage" / "cleanup_stale_worktrees.sh"


def run_cleanup(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CLEANUP_SCRIPT), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_cleanup_help_exits_zero() -> None:
    proc = run_cleanup("--help")
    assert proc.returncode == 0
    assert "Usage: cleanup_stale_worktrees.sh" in proc.stdout
    assert "--dry-run" in proc.stdout
    assert "--execute" in proc.stdout
    assert "--all-safe" in proc.stdout


def test_cleanup_default_dry_run_does_not_modify() -> None:
    proc = run_cleanup()
    assert proc.returncode == 0
    assert "Mode      : DRY-RUN" in proc.stdout
    assert "DRY-RUN COMPLETE" in proc.stdout
    # Invariant: Primary repo checkout is never in worktrees to remove
    lines = proc.stdout.splitlines()
    for line in lines:
        if line.strip().startswith("[") and "]" in line:
            assert str(REPO_ROOT) not in line


def test_cleanup_protected_branches_never_targeted() -> None:
    proc = run_cleanup("--all-safe")
    assert proc.returncode == 0
    output = proc.stdout

    # Verify protected branches are never in the deletion sections
    branch_del_section = False
    for line in output.splitlines():
        if "BRANCHES TO DELETE" in line:
            branch_del_section = True
        elif line.startswith("---"):
            branch_del_section = False

        if branch_del_section:
            # Main and gh-pages must not appear as targets
            assert " main " not in f" {line} "
            assert " gh-pages " not in f" {line} "


def test_cleanup_rebased_branches_requires_confirmation() -> None:
    proc = run_cleanup("--rebased-branches")
    assert proc.returncode != 0
    assert "requires explicit --confirm-rebased-delete" in proc.stderr
