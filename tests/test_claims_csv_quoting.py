"""The docs/evidence/data claims-CSV CSV-composability checker (#34).

Every ``docs/evidence/data/*claims*.csv`` is the machine-readable layer of
its evidence note: figures must stay CSV-composable (the handoff's
"conventions that must not drift"). Rows whose text contains commas were
landed without CSV quoting, so ``csv.DictReader`` shifted rate/label/scope
into wrong columns for exactly those rows (30 rows across 6 files, repaired
in the #34 close sequence; the stage-13/14 pair was repaired earlier,
commit 5b0a74a). The checker
``scripts/triage/check_claims_csv_quoting.py`` enforces the mechanical part
statically over the committed data directory:

- every ``*claims*.csv`` (and only those) parses under ``csv.reader``;
- every row has exactly the header's field count, so no column can shift;
- the claim id stays field 0, non-empty and unshifted.

This test pins the checker with a passing run over the real data and failing
runs over synthetic broken directories (the guard must be able to fail,
like the import-hygiene and format-claims checkers). The checker's
``--verify-repair`` mode is the repair-session companion - it re-proves
worktree rows changed since a git base are pure re-splits - and is run
manually around quoting repairs, not pinned here (it needs git history and
would misfire on legitimate uncommitted claim-row appends).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKER = REPO_ROOT / "scripts" / "triage" / "check_claims_csv_quoting.py"

HEADER = "claim,statement,rate,scope,label\n"


def run_checker(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", str(CHECKER), "--root", str(root)],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_committed_claims_csvs_parse_at_header_width() -> None:
    proc = run_checker(REPO_ROOT)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    summary = next(
        line
        for line in proc.stdout.splitlines()
        if line.startswith("claims csvs checked:")
    )
    parts = summary.split()
    files = int(parts[3])
    rows = int(parts[4].lstrip("("))
    assert files > 15, summary
    assert rows > 1_000, summary


def _write_claims(root: Path, name: str, body: str) -> Path:
    data = root / "docs" / "evidence" / "data"
    data.mkdir(parents=True, exist_ok=True)
    path = data / name
    path.write_text(body, encoding="utf-8")
    return path


def test_checker_fails_on_unquoted_comma_row(tmp_path: Path) -> None:
    _write_claims(
        tmp_path,
        "broken-claims.csv",
        HEADER + "X,ok statement,5/5,corpus,fact\n" "Y,broken,5/5,corpus,fact,extra\n",
    )
    proc = run_checker(tmp_path)
    assert proc.returncode != 0
    assert "broken-claims.csv: line 3" in proc.stdout
    assert "header has 5" in proc.stdout


def test_checker_fails_on_truncated_row(tmp_path: Path) -> None:
    _write_claims(tmp_path, "short-claims.csv", HEADER + "X,only,three,fields\n")
    proc = run_checker(tmp_path)
    assert proc.returncode != 0
    assert "short-claims.csv: line 2" in proc.stdout


def test_checker_passes_on_quoted_commas_and_walks_only_claims_csvs(
    tmp_path: Path,
) -> None:
    _write_claims(
        tmp_path,
        "one-claims.csv",
        HEADER + 'X,"statement, with comma",5/5,corpus,fact\n',
    )
    _write_claims(
        tmp_path,
        "two-claims.csv",
        HEADER + 'Y,"statement ok","rate, comma too","scope, comma",inference\n',
    )
    # A non-claims CSV carrying the same defect is outside the walk's scope.
    _write_claims(
        tmp_path,
        "notes.csv",
        HEADER + "Z,broken,5/5,corpus,fact,extra\n",
    )
    proc = run_checker(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    summary = next(
        line
        for line in proc.stdout.splitlines()
        if line.startswith("claims csvs checked:")
    )
    assert summary.startswith("claims csvs checked: 2"), summary
    assert "ok: every claims row parses at header width" in proc.stdout
