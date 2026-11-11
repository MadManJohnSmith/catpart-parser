"""The docs/format/ claim-hygiene and drift checker (tickets #22 and #36).

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

Ticket #36 adds the spec-to-code / spec-to-data drift pass
(``check_spec_drift()``): geometry parse-status markers, the
implementability-matrix row, the open register, ``catpart.<mod>``
reference-vs-``src/catpart/`` existence, AST-extracted ``INVARIANTS``
sync, the ROADMAP claim-count vs the live inventory, README.es <->
README tracker sync, and evidence-note <-> CSV arithmetic (P6u, C11,
the full-scope winding rate). The pass auto-runs on any root that has
``src/catpart/`` and is opt-in via ``--check-drift`` otherwise.

This test pins the checker with a passing run over the real docs (which
the auto-run makes a drift-free run too) and failing runs over synthetic
broken pages and roots (the guard must be able to fail, like the
import-hygiene checker).
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


# --- Spec-to-code / spec-to-data drift (ticket #36) -------------------------
#
# Every check in check_spec_drift() gets a corpus-free failure-injection
# test on a synthetic root: pure-hygiene cases run on docs-only roots (the
# drift pass is off unless --check-drift is passed), repo-shaped cases run
# with a minimal src/catpart/ (the drift pass auto-runs there, which the
# control tests pin).

CLEAN_GEOM_PAGE = "# 6. Geometry containers **(partially parsed)**\n\nDecoded.\n"

README_PAGES_ROW = (
    "| Page | Structural area | Parser status |\n|---|---|---|\n"
    "| [geometry.md](geometry.md) | geometry containers | {status} |\n"
)


def _write_docs(root: Path, pages: dict[str, str]) -> None:
    """Write docs/format pages plus the evidence note their links resolve to."""
    docs = root / "docs" / "format"
    docs.mkdir(parents=True, exist_ok=True)
    (root / "docs" / "evidence").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "evidence" / "real-note.md").write_text("note", encoding="utf-8")
    for name, text in pages.items():
        (docs / name).write_text(text, encoding="utf-8")


def _make_repo_shaped(root: Path, *files: str) -> None:
    """Minimal src/catpart/ shape: ``__init__.py`` plus the named files."""
    for rel in files:
        path = root / "src" / "catpart" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")


def run_drift_check(root: Path, *flags: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", str(CHECKER), "--root", str(root), *flags],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_check_drift_controls_the_pass_on_docs_only_roots(tmp_path: Path) -> None:
    _write_docs(
        tmp_path,
        {
            "README.md": README_PAGES_ROW.format(status="parsed"),
            "header.md": (
                "Evidence: [note](../evidence/real-note.md).\n\n"
                "| ID | Field | Claim | Label | Scope |\n|---|---|---|---|---|\n"
                "| A | 0-8 | magic | established | corpus |\n"
            ),
        },
    )
    (tmp_path / "docs" / "ROADMAP.md").write_text(
        "9 claims — 9 established / 0 candidate / 0 open\n", encoding="utf-8"
    )
    # Docs-only root: the drift pass is opt-in, so the plain run stays green.
    assert run_drift_check(tmp_path).returncode == 0
    proc = run_drift_check(tmp_path, "--check-drift")
    assert proc.returncode != 0
    assert "claim inventory states 9" in proc.stdout


def test_drift_pass_auto_runs_on_repo_shaped_roots(tmp_path: Path) -> None:
    _write_docs(
        tmp_path,
        {"README.md": "Refs `catpart.ghost`.\n" + README_PAGES_ROW.format(status="parsed")},
    )
    _make_repo_shaped(tmp_path, "__init__.py")
    # The deliberate auto-run: no flag needed once src/catpart exists (#36).
    proc = run_drift_check(tmp_path)
    assert proc.returncode != 0
    assert "catpart.ghost" in proc.stdout


def test_drift_flags_geometry_marked_not_parsed(tmp_path: Path) -> None:
    _write_docs(
        tmp_path,
        {
            "README.md": README_PAGES_ROW.format(status="documented, not parsed"),
            "geometry.md": CLEAN_GEOM_PAGE,
        },
    )
    _make_repo_shaped(tmp_path, "geometry/__init__.py", "geometry/export.py")
    proc = run_drift_check(tmp_path)
    assert proc.returncode != 0
    assert "documented, not parsed" in proc.stdout


def test_drift_flags_implementability_matrix_row(tmp_path: Path) -> None:
    _write_docs(
        tmp_path,
        {
            "README.md": (
                README_PAGES_ROW.format(status="parsed at L2")
                + "\n| Page | L1 implements | Stays documented |\n|---|---|---|\n"
                "| geometry.md | nothing | the nested store |\n"
            ),
            "geometry.md": CLEAN_GEOM_PAGE,
        },
    )
    _make_repo_shaped(tmp_path, "geometry/__init__.py", "geometry/export.py")
    proc = run_drift_check(tmp_path)
    assert proc.returncode != 0
    assert "implements 'nothing'" in proc.stdout


def test_drift_flags_stale_open_register(tmp_path: Path) -> None:
    _write_docs(
        tmp_path,
        {
            "README.md": (
                README_PAGES_ROW.format(status="parsed at L2")
                + "- **Strip-record primitive semantics** (`UT-strip-semantics`);"
                " the nested-store header variants.\n"
            ),
            "geometry.md": CLEAN_GEOM_PAGE,
        },
    )
    _make_repo_shaped(tmp_path, "geometry/__init__.py", "geometry/export.py")
    proc = run_drift_check(tmp_path)
    assert proc.returncode != 0
    assert "open register" in proc.stdout


def test_drift_flags_geometry_header_marker(tmp_path: Path) -> None:
    _write_docs(
        tmp_path,
        {
            "README.md": README_PAGES_ROW.format(status="parsed at L2"),
            "geometry.md": "# 6. Geometry **(documented, not parsed)**\n",
        },
    )
    _make_repo_shaped(tmp_path, "geometry/__init__.py", "geometry/export.py")
    proc = run_drift_check(tmp_path)
    assert proc.returncode != 0
    assert "geometry.md: line 1" in proc.stdout


def test_drift_flags_geometry_schema_omission(tmp_path: Path) -> None:
    _write_docs(
        tmp_path,
        {
            "README.md": README_PAGES_ROW.format(status="parsed at L2"),
            "geometry.md": (
                "# 6. Geometry **(partially parsed)**\n\n"
                "No schema v1 field touches the geometry containers;\n"
                "this page documents their location.\n"
            ),
        },
    )
    _make_repo_shaped(
        tmp_path,
        "geometry/__init__.py",
        "geometry/export.py",
        "schema/export-summary-v1.json",
    )
    proc = run_drift_check(tmp_path)
    assert proc.returncode != 0
    assert "export-summary-v1" in proc.stdout


def test_drift_flags_geometry_reproduction_block(tmp_path: Path) -> None:
    _write_docs(
        tmp_path,
        {
            "README.md": README_PAGES_ROW.format(status="parsed at L2"),
            "geometry.md": (
                "# 6. Geometry **(partially parsed)**\n\n"
                "### 6.3.1 The facet-record primitive semantics (G3)\n\n"
                "Reproduction: `python3 -I scripts/triage/decode_geometry_payloads.py`.\n"
            ),
        },
    )
    _make_repo_shaped(tmp_path, "geometry/__init__.py", "geometry/export.py")
    proc = run_drift_check(tmp_path)
    assert proc.returncode != 0
    assert "decode_facet_semantics.py" in proc.stdout


def test_drift_flags_unscoped_validation_open(tmp_path: Path) -> None:
    _write_docs(
        tmp_path,
        {
            "README.md": README_PAGES_ROW.format(status="parsed at L2"),
            "geometry.md": CLEAN_GEOM_PAGE,
            "validation.md": (
                "| Diff. ID | Untested claim | Why | Label | Scope |\n"
                "|---|---|---|---|---|\n"
                "| UT-strip-semantics | strip-record primitive semantics | needs "
                "a decode pass | open | all marked lines (untested) |\n"
            ),
        },
    )
    _make_repo_shaped(tmp_path, "geometry/__init__.py", "geometry/export.py")
    proc = run_drift_check(tmp_path)
    assert proc.returncode != 0
    assert "UT-strip-semantics" in proc.stdout


def test_drift_flags_ast_invariant_sync(tmp_path: Path) -> None:
    _write_docs(
        tmp_path,
        {
            "README.md": README_PAGES_ROW.format(status="parsed at L2"),
            "geometry.md": CLEAN_GEOM_PAGE,
            "trailer.md": "Enforced: `trailer-constants`.\n",
        },
    )
    _make_repo_shaped(tmp_path, "geometry/__init__.py", "geometry/export.py")
    invariants = tmp_path / "src" / "catpart" / "fitness" / "invariants.py"
    invariants.parent.mkdir(parents=True, exist_ok=True)
    invariants.write_text('INVARIANTS = (("some-other-invariant", None),)\n', encoding="utf-8")
    proc = run_drift_check(tmp_path)
    assert proc.returncode != 0
    assert "missing from AST INVARIANTS" in proc.stdout and "trailer-constants" in proc.stdout
    # The sync holds once the invariant exists on both sides.
    invariants.write_text('INVARIANTS = (("trailer-constants", None),)\n', encoding="utf-8")
    assert run_drift_check(tmp_path).returncode == 0


def test_drift_flags_roadmap_claim_inventory(tmp_path: Path) -> None:
    _write_docs(
        tmp_path,
        {
            "README.md": README_PAGES_ROW.format(status="parsed at L2"),
            "geometry.md": CLEAN_GEOM_PAGE,
            "header.md": (
                "Evidence: [note](../evidence/real-note.md).\n\n"
                "| ID | Field | Claim | Label | Scope |\n|---|---|---|---|---|\n"
                "| A | 0-8 | magic | established | corpus |\n"
                "| B | 8-12 | dword | established | corpus |\n"
            ),
        },
    )
    (tmp_path / "docs" / "ROADMAP.md").write_text(
        "115 claims — 89 established / 8 candidate / 18 open\n", encoding="utf-8"
    )
    proc = run_drift_check(tmp_path, "--check-drift")
    assert proc.returncode != 0
    assert "claim inventory states 115" in proc.stdout
    # The live inventory the checker computes keeps it green.
    (tmp_path / "docs" / "ROADMAP.md").write_text(
        "2 table claims — 2 established / 0 candidate / 0 open\n", encoding="utf-8"
    )
    assert run_drift_check(tmp_path, "--check-drift").returncode == 0


def test_drift_flags_readme_es_phase_counter(tmp_path: Path) -> None:
    _write_docs(tmp_path, {"README.md": README_PAGES_ROW.format(status="parsed")})
    (tmp_path / "README.md").write_text("Phase 4: 5/6 (G1-G5 done).\n", encoding="utf-8")
    (tmp_path / "README.es.md").write_text("Fase 4: 2/6 (G1-G2 hechos).\n", encoding="utf-8")
    proc = run_drift_check(tmp_path, "--check-drift")
    assert proc.returncode != 0
    assert "Phase 4 progress counter" in proc.stdout
    (tmp_path / "README.es.md").write_text("Fase 4: 5/6 (G1-G5 hechos).\n", encoding="utf-8")
    assert run_drift_check(tmp_path, "--check-drift").returncode == 0


def test_drift_flags_readme_es_ticket_state(tmp_path: Path) -> None:
    _write_docs(tmp_path, {"README.md": README_PAGES_ROW.format(status="parsed")})
    (tmp_path / "README.md").write_text(
        "| D | [#31](https://example.com/31) G3 primitive semantics | done |\n",
        encoding="utf-8",
    )
    (tmp_path / "README.es.md").write_text(
        "| D | [#31](https://example.com/31) G3 primitive semantics | planeado |\n",
        encoding="utf-8",
    )
    proc = run_drift_check(tmp_path, "--check-drift")
    assert proc.returncode != 0
    assert "ticket #31 state is 'planeado'" in proc.stdout
    (tmp_path / "README.es.md").write_text(
        "| D | [#31](https://example.com/31) G3 primitive semantics | hecho |\n",
        encoding="utf-8",
    )
    assert run_drift_check(tmp_path, "--check-drift").returncode == 0


def test_drift_flags_p6u_note_vs_csv_arithmetic(tmp_path: Path) -> None:
    _write_docs(tmp_path, {"README.md": README_PAGES_ROW.format(status="parsed")})
    data = tmp_path / "docs" / "evidence" / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "vertex-pool-claims.csv").write_text(
        "claim,release,observations,passes\n"
        "P6u_facets_unresolved,R19,6,6\n"
        "P6u_facets_unresolved,R20,4,1\n",
        encoding="utf-8",
    )
    note = tmp_path / "docs" / "evidence" / "2026-11-09-vertex-pool.md"
    note.write_text(
        "- **P6u unresolved-facet variants (candidate, 6/10 = 0.600):** stale.\n"
        "| P6u | strict-unresolved remain | 6/10 = 0.600 parts | candidate |\n",
        encoding="utf-8",
    )
    proc = run_drift_check(tmp_path, "--check-drift")
    assert proc.returncode != 0
    assert "measures 7/10" in proc.stdout
    # The CSV-composed figure and rate keep the note green.
    note.write_text(
        "- **P6u unresolved-facet variants (candidate, 7/10 = 0.700):** ok.\n"
        "| P6u | strict-unresolved remain | 7/10 = 0.700 parts | candidate |\n",
        encoding="utf-8",
    )
    assert run_drift_check(tmp_path, "--check-drift").returncode == 0


def test_drift_flags_c11_partition_conflation(tmp_path: Path) -> None:
    _write_docs(tmp_path, {"README.md": README_PAGES_ROW.format(status="parsed")})
    note = tmp_path / "docs" / "evidence" / "2026-11-09-facet-semantics.md"
    note.write_text(
        "strict records 101,569 (G2) -> 111,287 (G3) on the 962 candidate-bearing "
        "parts — 619 parts improved, 434 unchanged, 15 worse\n",
        encoding="utf-8",
    )
    proc = run_drift_check(tmp_path, "--check-drift")
    assert proc.returncode != 0
    assert "conflates" in proc.stdout
    note.write_text(
        "strict records 101,569 (G2) -> 111,287 (G3) over the 1,068 decoded "
        "stores — 619 improved, 434 unchanged, 15 worse\n",
        encoding="utf-8",
    )
    assert run_drift_check(tmp_path, "--check-drift").returncode == 0


def test_drift_flags_winding_note_vs_csv_arithmetic(tmp_path: Path) -> None:
    _write_docs(tmp_path, {"README.md": README_PAGES_ROW.format(status="parsed")})
    data = tmp_path / "docs" / "evidence" / "data"
    data.mkdir(parents=True, exist_ok=True)
    # Two measured loops: parallel 2/2 + 1/2, no degenerates -> "3/4 = 0.7500".
    (data / "facet-semantics-loops.csv").write_text(
        "sha256,release,record_offset,marker,type,n_refs,loop_counts,width,"
        "has_normal,normal,refs,lex_refs,in_pool,reading,parallel,sign_pos,"
        "sign_neg,offplane,degenerate\n"
        'a,R19,0,0x4a,1,4,4,1,True,"0,0,1","0 1 2 3","0 1 2 3",True,strip,'
        "2/2,2,0,0,0\n"
        'a,R19,9,0x4a,1,4,4,1,True,"0,0,1","0 1 2 3","0 1 2 3",True,strip,'
        "1/2,1,0,1,0\n",
        encoding="utf-8",
    )
    note = tmp_path / "docs" / "evidence" / "2026-11-09-facet-semantics.md"
    # Drifted composition: right numerator, wrong denominator.
    note.write_text(
        "On the full 179-clean-store scope the rate is 3/5 = 0.6000.\n",
        encoding="utf-8",
    )
    proc = run_drift_check(tmp_path, "--check-drift")
    assert proc.returncode != 0
    assert "3/4 = 0.7500" in proc.stdout
    # Drifted rate: right pair, wrong rounding.
    note.write_text(
        "On the full 179-clean-store scope the rate is 3/4 = 0.7501.\n",
        encoding="utf-8",
    )
    proc = run_drift_check(tmp_path, "--check-drift")
    assert proc.returncode != 0
    assert "0.7501" in proc.stdout
    # Scope discussed without any quotable figure at all.
    note.write_text("The full-179 scope winds below the bar.\n", encoding="utf-8")
    proc = run_drift_check(tmp_path, "--check-drift")
    assert proc.returncode != 0
    assert "does not quote" in proc.stdout
    # The CSV-composed figure keeps the note green.
    note.write_text(
        "On the full 179-clean-store scope the rate is 3/4 = 0.7500.\n",
        encoding="utf-8",
    )
    assert run_drift_check(tmp_path, "--check-drift").returncode == 0


# --- Generic note-figure arithmetic (ticket #37) ----------------------------
#
# The mechanical layer under the hand-wired note-vs-CSV tripwires: rate
# triples, sum expressions, and table total rows over every evidence note
# and format doc. Repo-shaped roots (the drift pass auto-runs there) with
# failure injection, plus a no-false-positive control.


def test_drift_flags_rate_triple_mismatch(tmp_path: Path) -> None:
    _write_docs(tmp_path, {"README.md": README_PAGES_ROW.format(status="parsed")})
    _make_repo_shaped(tmp_path, "__init__.py")
    note = tmp_path / "docs" / "evidence" / "2027-01-01-sample.md"
    note.write_text("The class covers 785/878 = 0.500 of stores.\n", encoding="utf-8")
    proc = run_drift_check(tmp_path)
    assert proc.returncode != 0
    assert "composes 0.894" in proc.stdout
    note.write_text("The class covers 785/878 = 0.894 of stores.\n", encoding="utf-8")
    assert run_drift_check(tmp_path).returncode == 0


def test_drift_flags_sum_expression_mismatch(tmp_path: Path) -> None:
    _write_docs(tmp_path, {"README.md": README_PAGES_ROW.format(status="parsed")})
    _make_repo_shaped(tmp_path, "__init__.py")
    note = tmp_path / "docs" / "evidence" / "2027-01-01-sample.md"
    note.write_text("The families partition it: 208+63+34+9 = 313.\n", encoding="utf-8")
    proc = run_drift_check(tmp_path)
    assert proc.returncode != 0
    assert "does not add up" in proc.stdout and "sum to 314" in proc.stdout
    note.write_text("The families partition it: 208+63+34+8 = 313.\n", encoding="utf-8")
    assert run_drift_check(tmp_path).returncode == 0


def test_drift_flags_table_total_row(tmp_path: Path) -> None:
    _write_docs(tmp_path, {"README.md": README_PAGES_ROW.format(status="parsed")})
    _make_repo_shaped(tmp_path, "__init__.py")
    note = tmp_path / "docs" / "evidence" / "2027-01-01-sample.md"
    note.write_text(
        "| class | dev |\n|---|---|\n| a | 5 |\n| b | 6 |\n| total | 12 |\n",
        encoding="utf-8",
    )
    proc = run_drift_check(tmp_path)
    assert proc.returncode != 0
    assert "body rows sum to 11" in proc.stdout
    note.write_text(
        "| class | dev |\n|---|---|\n| a | 5 |\n| b | 6 |\n| total | 11 |\n",
        encoding="utf-8",
    )
    assert run_drift_check(tmp_path).returncode == 0


def test_drift_allows_paren_sum_rate_and_prose_fragments(tmp_path: Path) -> None:
    """No false positives: parenthesized sum rates, comma-grouped
    fragments, and bare pairs stay out of the generic checks (#37)."""
    _write_docs(tmp_path, {"README.md": README_PAGES_ROW.format(status="parsed")})
    _make_repo_shaped(tmp_path, "__init__.py")
    note = tmp_path / "docs" / "evidence" / "2027-01-01-sample.md"
    note.write_text(
        "Recomposed on the wider probe: (1,068+100)/1,377 = 0.848; among the\n"
        "fragments, sizes run 4-168 with pairs 5, 9 and bare 651/681 unquoted.\n",
        encoding="utf-8",
    )
    assert run_drift_check(tmp_path).returncode == 0
