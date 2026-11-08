"""The docs/format/ claim-hygiene checker (ticket #22, format document v1).

Every claim in ``docs/format/`` carries a label (established / candidate /
open), a version scope, and a link to its committed evidence note (and
per-claim data CSV where one exists). The checker
``scripts/triage/check_format_claims.py`` enforces the mechanical part
statically over the committed pages:

- every ``docs/evidence/...`` reference (markdown link or inline code)
  resolves to a committed file;
- every row of a claim table (a table whose header names ``Label`` and
  ``Scope`` columns) carries a recognized label and a non-empty scope;
- paragraph claims carry a bold label marker (``**(established ...)**``).

This test pins the checker with a passing run over the real docs and
failing runs over synthetic broken pages (the guard must be able to
fail, like the import-hygiene checker).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKER = REPO_ROOT / "scripts" / "triage" / "check_format_claims.py"

LABELS = ("established", "candidate", "open")


def run_checker(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", str(CHECKER), "--root", str(root)],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_format_docs_pass() -> None:
    proc = run_checker(REPO_ROOT)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    # The inventory must be non-empty and cover all three labels.
    total_line = next(
        line for line in proc.stdout.splitlines() if line.startswith("total claims:")
    )
    counts = {label: 0 for label in LABELS}
    for label in LABELS:
        marker = f"{label} "
        if marker in total_line:
            after = total_line.split(marker, 1)[1]
            counts[label] = int(after.split(",", 1)[0].strip().rstrip(")"))
    assert sum(counts.values()) > 40, total_line
    assert counts["established"] > counts["candidate"], total_line
    assert counts["open"] > 0, total_line
    links_line = next(
        line for line in proc.stdout.splitlines() if line.startswith("evidence links checked:")
    )
    assert int(links_line.rsplit(" ", 1)[1]) > 20


def _write_page(root: Path, text: str) -> Path:
    docs = root / "docs" / "format"
    docs.mkdir(parents=True, exist_ok=True)
    page = docs / "sample.md"
    page.write_text(text, encoding="utf-8")
    (root / "docs" / "evidence").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "evidence" / "real-note.md").write_text("note", encoding="utf-8")
    return page


def test_checker_fails_on_broken_evidence_link(tmp_path: Path) -> None:
    _write_page(
        tmp_path,
        "Evidence: [missing](../evidence/2026-01-01-missing.md).\n\n"
        "| ID | Field | Claim | Label | Scope |\n|---|---|---|---|---|\n"
        "| X | 0-8 | magic | established | corpus |\n",
    )
    proc = run_checker(tmp_path)
    assert proc.returncode != 0
    assert "2026-01-01-missing.md" in proc.stdout


def test_checker_fails_on_unlabeled_claim_row(tmp_path: Path) -> None:
    _write_page(
        tmp_path,
        "Evidence: [note](../evidence/real-note.md).\n\n"
        "| ID | Field | Claim | Label | Scope |\n|---|---|---|---|---|\n"
        "| X | 0-8 | magic | verified | corpus |\n",
    )
    proc = run_checker(tmp_path)
    assert proc.returncode != 0
    assert "label" in proc.stdout.lower()


def test_checker_fails_on_empty_scope(tmp_path: Path) -> None:
    _write_page(
        tmp_path,
        "Evidence: [note](../evidence/real-note.md).\n\n"
        "| ID | Field | Claim | Label | Scope |\n|---|---|---|---|---|\n"
        "| X | 0-8 | magic | established | |\n",
    )
    proc = run_checker(tmp_path)
    assert proc.returncode != 0
    assert "scope" in proc.stdout.lower()


def test_checker_counts_paragraph_claims(tmp_path: Path) -> None:
    _write_page(
        tmp_path,
        "Evidence: [note](../evidence/real-note.md).\n\n"
        "Region rule **(established, 1082/1082, corpus sample)**: a block's "
        "payload region runs to the nearest boundary.\n",
    )
    proc = run_checker(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "paragraph claims: 1" in proc.stdout
