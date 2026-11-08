#!/usr/bin/env python3
"""Check docs/format/ claim hygiene (format document v1, ticket #22).

Every claim in ``docs/format/`` carries a label (established / candidate /
open; established negatives say "(negative)" in the claim text), a version
scope, and a link to its committed evidence note (plus the per-claim data
CSV where one exists). This checker enforces the mechanical part over the
committed pages, so a claim cannot silently lose its evidence:

1. every ``docs/evidence/...`` reference (markdown link, inline code, or
   ``../evidence/...`` form) resolves to a committed file;
2. every row of a claim table - a table whose header names ``Label`` and
   ``Scope`` columns - carries a recognized label and a non-empty scope;
3. paragraph claims (bold label markers like ``**(established, ...)**``)
   are recognized and counted; an unrecognized ``**( ...)**`` marker
   spelling fails the run.

Output: per-page claim inventory (established / candidate / open), the
evidence-link count, and any violations. Exit 1 when a violation exists.

Stdlib-only, read-only, deterministic; run with ``python3 -I``.

    python3 -I scripts/triage/check_format_claims.py
"""

from __future__ import annotations

import argparse
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
#: ``**(documented, not parsed)**`` is a page-scope marker, not a claim
#: label; any other lowercase bold-paren marker is a misspelled label.
UNKNOWN_MARKER = re.compile(
    r"\*\*\((?!established\b|candidate\b|open\b|documented\b)[a-z]+"
)


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=repo_root(),
        help="repository root (default: the checkout this script lives in)",
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
    if total_violations:
        print("violations:")
        for violation in total_violations:
            print(f"  - {violation}")
        return 1
    print("ok: all claim rows labeled + scoped, all evidence links resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
