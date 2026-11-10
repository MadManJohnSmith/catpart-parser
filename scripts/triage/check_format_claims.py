#!/usr/bin/env python3
"""Check docs/format/ claim hygiene and spec-to-code/data drift (#22, #36).

Every claim in ``docs/format/`` carries a label (established / candidate /
open; established negatives say "(negative)" in the claim text), a version
scope, and a link to its committed evidence note (plus the per-claim data
CSV where one exists). This checker enforces both the mechanical part and
the spec-to-code / spec-to-data drift part (ticket #36), so a claim cannot
silently lose its evidence and a doc cannot silently lag the code or the
committed CSVs:

1. every ``docs/evidence/...`` reference (markdown link, inline code, or
   ``../evidence/...`` form) resolves to a committed file;
2. every row of a claim table - a table whose header names ``Label`` and
   ``Scope`` columns - carries a recognized label and a non-empty scope;
3. paragraph claims (bold label markers like ``**(established, ...)**``)
   are recognized and counted; an unrecognized ``**( ...)**`` marker
   spelling fails the run;
4. spec-to-code & spec-to-data drift (run automatically whenever the root
   contains ``src/catpart``, or explicitly with ``--check-drift``; the
   deliberate auto-run keeps ``test_format_docs_pass`` enforcing
   drift-freedom on every test run):
   - Spec-to-Code module & status markers: ``docs/format/README.md`` and
     ``docs/format/geometry.md`` must reflect the shipped parser/exporter
     modules under ``src/catpart/`` (``catpart.<mod>`` references must
     exist; geometry is parsed since G4 shipped ``catpart.geometry`` and
     ``export-summary-v1.json``);
   - AST Invariant sync: invariants cited in ``docs/format/*.md`` must
     exist in the ``INVARIANTS`` tuple of
     ``src/catpart/fitness/invariants.py``;
   - Doc-to-Checker claim inventory: the headline claim counts in
     ``docs/ROADMAP.md`` must match the live table-claim inventory
     computed over ``docs/format/*.md``;
   - Cross-README tracker sync: ticket statuses and the Phase 4 counter
     in ``README.es.md`` must match ``README.md``;
   - Evidence-to-CSV arithmetic: quoted figures in
     ``2026-11-09-vertex-pool.md`` (P6u) and in
     ``2026-11-09-facet-semantics.md`` / ``geometry.md`` (the full-scope
     winding rate) must compose from the committed CSVs under
     ``docs/evidence/data/``.

Output: per-page claim inventory (established / candidate / open), the
evidence-link count, drift checks, and any violations. Exit 1 when a
violation exists.

Stdlib-only, read-only, deterministic; run with ``python3 -I``.

    python3 -I scripts/triage/check_format_claims.py
"""

from __future__ import annotations

import argparse
import ast
import csv
import re
import sys
from pathlib import Path

LABELS = ("established", "candidate", "open")

#: ``docs/evidence/...`` or ``../evidence/...`` references, as markdown
#: links (parenthesized) or inline code (backtick-quoted). The path must
#: not end in a slash (bare directory mentions are not file references).
EVIDENCE_REF = re.compile(
    r"(?:\(|`)((?:\.\./|docs/)?evidence/[A-Za-z0-9_./-]*[A-Za-z0-9_-])(?:\)|`)"
)

#: Paragraph-level claim marker, e.g. "**(established, 1082/1082, ...)**".
PARAGRAPH_CLAIM = re.compile(r"\*\*\((established|candidate|open)\b")
#: ``**(documented, not parsed)**`` and ``**(partially parsed)**`` are
#: page-scope markers, not claim labels; any other lowercase bold-paren
#: marker is a misspelled label.
UNKNOWN_MARKER = re.compile(
    r"\*\*\((?!established\b|candidate\b|open\b|documented\b|partially\b)[a-z]+"
)

#: Match the ROADMAP Phase 2 claim-inventory headline, e.g.
#: "139 table claims — 111 established / 11 candidate / 17 open".
ROADMAP_CLAIM_RE = re.compile(
    r"\b(\d+)\s+(?:table\s+)?claims\s+[—-]\s+(\d+)\s+established"
    r"\s*/\s*(\d+)\s+candidate\s*/\s*(\d+)\s+open\b"
)

#: Match ticket rows in README.md and README.es.md
#: ("| D | [#31](...) G3 primitive semantics (triangles) | done |").
TICKET_ROW_RE = re.compile(
    r"^\|\s*([A-Z])\s*\|\s*\[#(\d+)\]\([^)]+\)\s+([^|]+?)\s*\|\s*([^|]+?)\s*\|$"
)
#: The Phase 4 progress counter, e.g. "5/6 (G1-G5 done 2026-11-10)".
PHASE4_COUNT_RE = re.compile(r"\b(\d+)/6\s+\(G1")

#: An "N/M = 0.ZZZZ" winding figure as the evidence notes quote it.
WINDING_FIGURE_RE = re.compile(r"(\d[\d,]*)\s*/\s*(\d[\d,]*)\s*=\s*(0\.\d{4})")
#: Lines discussing the full clean-store winding scope. The expected
#: figure must appear wherever the scope is discussed, and no figure
#: sharing one component with the expected pair may quote the other
#: component differently (the drifted-composition tripwire, #36).
FULL_SCOPE_TRIGGERS = ("179-clean", "full 179", "full-179")

#: An "N/M" figure on a P6u line of the vertex-pool note.
P6U_FIGURE_RE = re.compile(r"(\d[\d,]*)\s*/\s*(\d[\d,]*)")
#: A "= 0.ZZZ" rate on a P6u line.
P6U_RATE_RE = re.compile(r"=\s*(0\.\d{3})\b")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def check_page(text: str) -> tuple[list[str], dict[str, int]]:
    """Return (violations, label_counts) for one page.

    ``label_counts`` carries the three LABELS keys plus ``paragraph``
    (paragraph-level claims, counted separately from table rows).
    """
    violations: list[str] = []
    counts = {label: 0 for label in LABELS}

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        header_cells = table_cells(line)
        if header_cells and "Label" in header_cells and "Scope" in header_cells:
            label_col = header_cells.index("Label")
            scope_col = header_cells.index("Scope")
            i += 1
            while i < len(lines) and table_cells(lines[i]) is not None:
                cells = table_cells(lines[i])
                if cells is not None and not all(
                    set(cell) <= set("-: ") for cell in cells
                ):
                    if len(cells) != len(header_cells):
                        violations.append(
                            f"line {i + 1}: claim row has {len(cells)} cells, "
                            f"the header has {len(header_cells)} (a stray pipe?)"
                        )
                    elif len(cells) <= max(label_col, scope_col):
                        violations.append(
                            f"line {i + 1}: malformed claim row (fewer cells than the header)"
                        )
                    else:
                        label = cells[label_col].strip().lower()
                        if not label.startswith(LABELS):
                            violations.append(
                                f"line {i + 1}: claim row label {cells[label_col]!r} "
                                "is not one of established/candidate/open"
                            )
                        else:
                            counts[
                                next(l for l in LABELS if label.startswith(l))
                            ] += 1
                        if not cells[scope_col].strip():
                            violations.append(f"line {i + 1}: claim row has an empty Scope")
                i += 1
            continue
        i += 1

    paragraph = 0
    for n, line in enumerate(lines, 1):
        paragraph += len(PARAGRAPH_CLAIM.findall(line))
        if UNKNOWN_MARKER.search(line):
            violations.append(
                f"line {n}: unrecognized bold claim marker (use **(established...**, "
                "**(candidate...** or **(open...**)"
            )
    counts["paragraph"] = paragraph
    return violations, counts


def table_cells(line: str) -> list[str] | None:
    """Cells of a markdown table row, or None when the line is not one."""
    if not (line.lstrip().startswith("|") and line.rstrip().endswith("|")):
        return None
    cells = [cell.strip() for cell in line.strip()[1:-1].split("|")]
    return cells


def _extract_ast_invariants(invariants_py: Path) -> set[str]:
    """Extract invariant names from the ``INVARIANTS`` tuple via AST."""
    if not invariants_py.is_file():
        return set()
    tree = ast.parse(
        invariants_py.read_text(encoding="utf-8"), filename=str(invariants_py)
    )
    names: set[str] = set()
    for node in ast.walk(tree):
        value = None
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "INVARIANTS":
                    value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "INVARIANTS":
                value = node.value
        if value is not None and isinstance(value, ast.Tuple):
            for elt in value.elts:
                if (
                    isinstance(elt, ast.Tuple)
                    and elt.elts
                    and isinstance(elt.elts[0], ast.Constant)
                    and isinstance(elt.elts[0].value, str)
                ):
                    names.add(elt.elts[0].value)
    return names


def _facet_winding_totals(loops_csv: Path) -> tuple[int, int]:
    """(parallel, non-degenerate winding triangles) over the loops CSV.

    The facet-semantics note's full-scope winding rate is parallel over
    total-minus-degenerate: per the F7 skip convention the degenerate
    triangles are excluded from the winding denominator at export.
    """
    parallel = total = degenerate = 0
    with loops_csv.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            made, _, all_ = (row.get("parallel") or "").partition("/")
            parallel += int(made) if made else 0
            total += int(all_) if all_ else 0
            cell = row.get("degenerate") or "0"
            degenerate += int(cell) if cell else 0
    return parallel, total - degenerate


def _check_winding_note(root: Path, violations: list[str]) -> None:
    """Police the full-scope winding figures against the loops CSV (#36).

    The 2026-11-10 review flagged the class: a note quoting a winding
    rate that its committed CSV does not compose. The expected figure is
    recomputed from ``facet-semantics-loops.csv``; wherever a page
    discusses the full 179-clean-store scope the expected figure must be
    quoted, and any "N/M = 0.ZZZZ" figure sharing one component with the
    expected pair must quote the other component and the rate exactly.
    """
    loops_csv = root / "docs" / "evidence" / "data" / "facet-semantics-loops.csv"
    if not loops_csv.is_file():
        return
    parallel, denom = _facet_winding_totals(loops_csv)
    if not denom:
        return
    expected = f"{parallel:,}/{denom:,} = {parallel / denom:.4f}"
    pages = [
        root / "docs" / "evidence" / "2026-11-09-facet-semantics.md",
        root / "docs" / "format" / "geometry.md",
    ]
    for page in pages:
        if not page.is_file():
            continue
        text = page.read_text(encoding="utf-8")
        rel = page.relative_to(root)
        if any(trigger in text for trigger in FULL_SCOPE_TRIGGERS) and (
            expected not in text
        ):
            violations.append(
                f"{rel}: discusses the full 179-clean-store winding scope but does not "
                f"quote the figure the loops CSV composes ({expected})"
            )
        for m in WINDING_FIGURE_RE.finditer(text):
            x, y, z = m.group(1), m.group(2), m.group(3)
            xi, yi = int(x.replace(",", "")), int(y.replace(",", ""))
            if xi == parallel and yi == denom and z != f"{parallel / denom:.4f}":
                violations.append(
                    f"{rel}: quotes {x}/{y} = {z} for the full-scope winding rate, "
                    f"but the loops CSV composes {expected}"
                )
            elif xi == parallel and yi != denom:
                violations.append(
                    f"{rel}: quotes {x}/{y} for the full-scope winding rate; the "
                    f"numerator is the loops CSV's parallel count, so the denominator "
                    f"must be the non-degenerate count ({expected})"
                )
            elif yi == denom and xi != parallel:
                violations.append(
                    f"{rel}: quotes {x}/{y} for the full-scope winding rate; the "
                    f"denominator is the loops CSV's non-degenerate count, so the "
                    f"numerator must be the parallel count ({expected})"
                )


def _check_vertex_pool_note(root: Path, violations: list[str]) -> None:
    """Police the P6u figures in the vertex-pool note against its CSV (#36)."""
    vp_csv = root / "docs" / "evidence" / "data" / "vertex-pool-claims.csv"
    vp_note = root / "docs" / "evidence" / "2026-11-09-vertex-pool.md"
    if not vp_csv.is_file() or not vp_note.is_file():
        return
    observed = passed = 0
    with vp_csv.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("claim") == "P6u_facets_unresolved":
                observed += int(row.get("observations") or 0)
                passed += int(row.get("passes") or 0)
    if not observed:
        return
    expected_rate = f"{passed / observed:.3f}"
    for n, line in enumerate(vp_note.read_text(encoding="utf-8").splitlines(), 1):
        if "P6u" not in line:
            continue
        for m in P6U_FIGURE_RE.finditer(line):
            x, y = int(m.group(1).replace(",", "")), int(m.group(2).replace(",", ""))
            if y == observed and x != passed:
                violations.append(
                    f"docs/evidence/2026-11-09-vertex-pool.md: line {n}: quotes "
                    f"{x}/{y} for P6u, but vertex-pool-claims.csv measures "
                    f"{passed}/{observed}"
                )
        for m in P6U_RATE_RE.finditer(line):
            if m.group(1) != expected_rate:
                violations.append(
                    f"docs/evidence/2026-11-09-vertex-pool.md: line {n}: quotes rate "
                    f"{m.group(1)} for P6u, but vertex-pool-claims.csv gives "
                    f"{passed}/{observed} = {expected_rate}"
                )


def check_spec_drift(root: Path, total_counts: dict[str, int]) -> list[str]:
    """Run the spec-to-code and spec-to-data drift checks under ``root`` (#36)."""
    violations: list[str] = []
    src_pkg = root / "src" / "catpart"
    docs_fmt = root / "docs" / "format"

    # 1. Spec-to-Code module, schema, and AST invariant drift
    if src_pkg.is_dir() and docs_fmt.is_dir():
        has_geom_export = (src_pkg / "geometry" / "export.py").is_file()
        has_export_schema = (src_pkg / "schema" / "export-summary-v1.json").is_file()
        fmt_readme = docs_fmt / "README.md"
        fmt_geom = docs_fmt / "geometry.md"
        fmt_val = docs_fmt / "validation.md"

        if fmt_readme.is_file():
            rtext = fmt_readme.read_text(encoding="utf-8")
            for idx, line in enumerate(rtext.splitlines(), 1):
                if (
                    has_geom_export
                    and "geometry.md" in line
                    and "| documented, not parsed |" in line
                ):
                    violations.append(
                        f"docs/format/README.md: line {idx}: geometry.md marked "
                        "'documented, not parsed' despite the shipped catpart.geometry "
                        "exporter (P2-DRIFT-01)"
                    )
                if has_geom_export and "| geometry.md | nothing |" in line:
                    violations.append(
                        f"docs/format/README.md: line {idx}: implementability table says "
                        "geometry.md implements 'nothing' despite shipped "
                        "catpart.geometry (P2-DRIFT-02)"
                    )
                if "Strip-record primitive semantics" in line and (
                    "UT-strip-semantics" in line
                ):
                    violations.append(
                        f"docs/format/README.md: line {idx}: the open register still "
                        "lists strip-record primitive semantics after the G3 decode "
                        "(P2-DRIFT-03)"
                    )
            for m in re.finditer(r"\bcatpart\.([a-z_][a-z0-9_]*)\b", rtext):
                submod = m.group(1)
                if not (
                    (src_pkg / f"{submod}.py").is_file()
                    or (src_pkg / submod / "__init__.py").is_file()
                ):
                    violations.append(
                        f"docs/format/README.md: references non-existent module "
                        f"'catpart.{submod}'"
                    )

        if fmt_geom.is_file():
            gtext = fmt_geom.read_text(encoding="utf-8")
            g_lines = gtext.splitlines()
            if (
                has_geom_export
                and g_lines
                and "**(documented, not parsed)**" in g_lines[0]
            ):
                violations.append(
                    "docs/format/geometry.md: line 1: header says "
                    "'**(documented, not parsed)**' despite the shipped "
                    "catpart.geometry exporter (P2-DRIFT-04)"
                )
            if (
                has_export_schema
                and "No schema v1 field touches the geometry containers;" in gtext
                and "export-summary-v1" not in gtext
            ):
                violations.append(
                    "docs/format/geometry.md: omits exported schema "
                    "'export-summary-v1' while claiming no schema touches the "
                    "geometry containers (P2-DRIFT-04)"
                )
            if "### 6.3.1" in gtext and "decode_facet_semantics.py" not in gtext.split(
                "### 6.3.1", 1
            )[1].split("Reproduction:", 1)[-1]:
                violations.append(
                    "docs/format/geometry.md: Section 6.3.1 Reproduction block omits "
                    "decode_facet_semantics.py (P2-DRIFT-05)"
                )

        if fmt_val.is_file():
            vtext = fmt_val.read_text(encoding="utf-8")
            for idx, line in enumerate(vtext.splitlines(), 1):
                if (
                    "UT-strip-semantics" in line
                    and "| open |" in line
                    and "resolved by G2/G3" not in line
                ):
                    violations.append(
                        f"docs/format/validation.md: line {idx}: UT-strip-semantics "
                        "still marked unqualified 'open' after the G2/G3 decode "
                        "(P2-DRIFT-06)"
                    )

        ast_invs = _extract_ast_invariants(src_pkg / "fitness" / "invariants.py")
        if ast_invs:
            doc_inv_pattern = re.compile(
                r"`(header-dword-below-file-size|magic-v5-cfv2|tail-region-chain|"
                r"trailer-constants|container-kind-known)`"
            )
            found_in_docs: set[str] = set()
            for page in sorted(docs_fmt.glob("*.md")):
                found_in_docs.update(
                    doc_inv_pattern.findall(page.read_text(encoding="utf-8"))
                )
            missing_in_ast = found_in_docs - ast_invs
            if missing_in_ast:
                violations.append(
                    "src/catpart/fitness/invariants.py: invariants documented in "
                    f"docs/format/ missing from AST INVARIANTS: {sorted(missing_in_ast)}"
                )

    # 2. Doc-to-Checker claim inventory in docs/ROADMAP.md
    roadmap = root / "docs" / "ROADMAP.md"
    if roadmap.is_file():
        rm_text = roadmap.read_text(encoding="utf-8")
        m = ROADMAP_CLAIM_RE.search(rm_text)
        if m:
            rm_tot, rm_est, rm_cand, rm_open = (int(x) for x in m.groups())
            actual_tot = sum(total_counts[l] for l in LABELS)
            actual_tuple = (
                actual_tot,
                total_counts["established"],
                total_counts["candidate"],
                total_counts["open"],
            )
            if (rm_tot, rm_est, rm_cand, rm_open) != actual_tuple:
                violations.append(
                    f"docs/ROADMAP.md: claim inventory states "
                    f"{rm_tot} ({rm_est} established / {rm_cand} candidate / "
                    f"{rm_open} open), but docs/format/ has {actual_tot} table claims "
                    f"({actual_tuple[1]} established / {actual_tuple[2]} candidate / "
                    f"{actual_tuple[3]} open)"
                )

    # 3. Cross-README tracker sync (README.md vs README.es.md)
    readme_en = root / "README.md"
    readme_es = root / "README.es.md"
    if readme_en.is_file() and readme_es.is_file():
        en_text = readme_en.read_text(encoding="utf-8")
        es_text = readme_es.read_text(encoding="utf-8")
        en_p4 = PHASE4_COUNT_RE.search(en_text)
        es_p4 = PHASE4_COUNT_RE.search(es_text)
        if en_p4 and es_p4 and en_p4.group(1) != es_p4.group(1):
            violations.append(
                f"README.es.md: Phase 4 progress counter is {es_p4.group(1)}/6, "
                f"drifting from README.md {en_p4.group(1)}/6"
            )
        state_map = {"done": "hecho", "planned": "planeado"}
        en_tickets: dict[str, str] = {}
        for line in en_text.splitlines():
            tm = TICKET_ROW_RE.match(line.strip())
            if tm:
                en_tickets[tm.group(2)] = tm.group(4).strip().lower()
        for idx, line in enumerate(es_text.splitlines(), 1):
            tm = TICKET_ROW_RE.match(line.strip())
            if tm:
                tnum = tm.group(2)
                es_state = tm.group(4).strip().lower()
                expected_es = state_map.get(en_tickets.get(tnum, ""), "")
                if expected_es and es_state != expected_es:
                    violations.append(
                        f"README.es.md: line {idx}: ticket #{tnum} state is "
                        f"{es_state!r}, expected {expected_es!r} to match README.md "
                        f"({en_tickets[tnum]!r})"
                    )

    # 4. Evidence-note-to-CSV arithmetic drift
    _check_vertex_pool_note(root, violations)

    fs_note = root / "docs" / "evidence" / "2026-11-09-facet-semantics.md"
    if fs_note.is_file():
        fs_text = fs_note.read_text(encoding="utf-8")
        if re.search(
            r"962\s+candidate-bearing\s+parts\s+[—-]\s+619\s+parts\s+improved,"
            r"\s+434\s+unchanged",
            fs_text,
        ):
            violations.append(
                "docs/evidence/2026-11-09-facet-semantics.md: C11 conflates the 962 "
                "candidate-bearing parts with the 1,068-store partition the CSVs "
                "compose (619 improved, 434 unchanged, 15 worse)"
            )

    _check_winding_note(root, violations)

    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=repo_root(),
        help="repository root (default: the checkout this script lives in)",
    )
    parser.add_argument(
        "--check-drift",
        action="store_true",
        help="run the spec-to-code/data drift checks even without src/catpart "
        "(they auto-run on any root that has it)",
    )
    args = parser.parse_args(argv)
    docs = args.root / "docs" / "format"
    if not docs.is_dir():
        print(f"error: {docs} does not exist", file=sys.stderr)
        return 2

    total_violations: list[str] = []
    total = {label: 0 for label in LABELS}
    total["paragraph"] = 0
    links = 0

    for page in sorted(docs.glob("*.md")):
        rel = page.relative_to(args.root)
        text = page.read_text(encoding="utf-8")
        violations, counts = check_page(text)
        for match in EVIDENCE_REF.finditer(text):
            target = match.group(1)
            if target.startswith("../"):
                resolved = (page.parent / target).resolve()
            else:
                resolved = (args.root / target).resolve()
            if not resolved.is_file():
                violations.append(f"evidence link does not resolve: {target}")
            links += 1
        if violations:
            total_violations.extend(f"{rel}: {v}" for v in violations)
        for label in LABELS:
            total[label] += counts[label]
        total["paragraph"] += counts["paragraph"]
        print(
            f"{rel}: claims {sum(counts[l] for l in LABELS)} "
            f"(established {counts['established']}, candidate {counts['candidate']}, "
            f"open {counts['open']}, of which paragraph claims: {counts['paragraph']})"
        )

    print(
        f"total claims: {sum(total[l] for l in LABELS)} "
        f"(established {total['established']}, candidate {total['candidate']}, "
        f"open {total['open']}, of which paragraph claims: {total['paragraph']})"
    )
    print(f"evidence links checked: {links}")

    # Deliberate auto-run (#36): drift checks are part of the pass on any
    # repo-shaped root, so test_format_docs_pass enforces drift-freedom;
    # docs-only roots (synthetic fixtures) opt in with --check-drift.
    if args.check_drift or (args.root / "src" / "catpart").is_dir():
        total_violations.extend(check_spec_drift(args.root, total))

    if total_violations:
        print("violations:")
        for violation in total_violations:
            print(f"  - {violation}")
        return 1
    print("ok: all claim rows labeled + scoped, all evidence links resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
