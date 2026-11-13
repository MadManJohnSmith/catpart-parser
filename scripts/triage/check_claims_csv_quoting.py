#!/usr/bin/env python3
"""Check docs/evidence/data/*claims*.csv CSV-composability (#34 close sequence).

The claims CSVs are the machine-readable layer of the evidence notes: figures
must stay CSV-composable (the handoff's "conventions that must not drift").
Rows whose text contains commas were landed without CSV quoting, so a
csv.DictReader shifted rate/label/scope into wrong columns for exactly those
rows. This checker enforces the mechanical part on every committed claims
CSV, the same way ``check_format_claims.py`` pins docs/format/:

1. every ``docs/evidence/data/*claims*.csv`` parses under ``csv.reader``;
2. every row (header included) has exactly the header's field count, so
   ``csv.DictReader`` cannot shift columns;
3. the claim id stays field 0, non-empty and unshifted (no leading space).

``--verify-repair`` is the repair-session companion (not a repo gate): it
re-proves, against a git base (``--base``, default ``HEAD``), that every row
changed since the base is a pure re-split of the original row - never a
rewording. A repaired row verifies as either

- model A: a re-selection of the raw line's comma separators (the true
  fields are consecutive comma-token runs of the unquoted original), or
- model B: a consecutive-run merge of the base line's csv-parsed fields
  (the original was quoted except for one comma-bearing tail field),

and in both cases every token of the original row re-appears verbatim in the
repaired fields. Run it before committing a quoting repair (rows changed in
the worktree vs HEAD), or right after with ``--base HEAD~1``; on a clean
tree it reports zero changed rows and passes.
"""

from __future__ import annotations

import argparse
import csv
import io
import subprocess
from itertools import combinations
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def writer_line(fields: list[str]) -> str:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerow(fields)
    return buf.getvalue().rstrip("\n")


def check_widths(data_dir: Path) -> tuple[list[str], int, int]:
    """Walk every claims CSV; return (violations, files, rows)."""
    violations: list[str] = []
    files = rows_total = 0
    for path in sorted(data_dir.glob("*claims*.csv")):
        files += 1
        rel = path.relative_to(data_dir)
        with path.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        if not rows:
            violations.append(f"{rel}: file has no header row")
            continue
        width = len(rows[0])
        if width < 2:
            violations.append(f"{rel}: header {width} cols, expected >= 2")
        for lineno, row in enumerate(rows, start=1):
            if not row:
                continue  # blank (trailing) line
            rows_total += 1
            if len(row) != width:
                violations.append(
                    f"{rel}: line {lineno} parses to {len(row)} fields, "
                    f"header has {width} (unquoted comma shifts rate/scope/label)"
                )
            elif not row[0].strip() or row[0][0] == " ":
                violations.append(f"{rel}: line {lineno} claim id empty or shifted")
    return violations, files, rows_total


def _model_a_lines(raw_base_line: str, width: int) -> list[str]:
    """All csv re-serializations of consecutive comma-token runs of the raw
    base line (choose width-1 separators among the raw commas)."""
    toks = raw_base_line.split(",")
    out = []
    if len(toks) < width:
        return out
    for seps in combinations(range(1, len(toks)), width - 1):
        bounds = [0, *seps, len(toks)]
        fields = [",".join(toks[bounds[i] : bounds[i + 1]]) for i in range(width)]
        out.append(writer_line(fields))
    return out


def _model_b_lines(raw_base_line: str, width: int) -> list[str]:
    """All csv re-serializations of consecutive-run merges of the base line's
    csv-parsed fields (for originals whose quoted fields parse correctly and
    only a tail field is over-split)."""
    try:
        parsed = next(csv.reader(io.StringIO(raw_base_line)))
    except (csv.Error, StopIteration):
        return []
    if len(parsed) < width or not parsed:
        return []
    out = []
    for seps in combinations(range(1, len(parsed)), width - 1):
        bounds = [0, *seps, len(parsed)]
        fields = [",".join(parsed[bounds[i] : bounds[i + 1]]) for i in range(width)]
        out.append(writer_line(fields))
    return out


def _tokens_of(base_line: str, model: str) -> list[str]:
    if model == "A":
        return base_line.split(",")
    parsed = next(csv.reader(io.StringIO(base_line)), [])
    return [tok for field in parsed for tok in field.split(",")]


def verify_repair(repo_root: Path, base: str) -> tuple[list[str], int]:
    """Re-prove every claims-CSV row changed since ``base`` is a pure re-split."""
    data_dir = repo_root / "docs" / "evidence" / "data"
    violations: list[str] = []
    changed_rows = 0
    for path in sorted(data_dir.glob("*claims*.csv")):
        rel = path.relative_to(repo_root)
        proc = subprocess.run(
            ["git", "show", f"{base}:{rel}"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            violations.append(f"{rel}: not present in base {base} - nothing to verify")
            continue
        base_lines = proc.stdout.split("\n")
        now_lines = path.read_text(encoding="utf-8").split("\n")
        if len(base_lines) != len(now_lines):
            violations.append(
                f"{rel}: row count changed vs {base} "
                f"({len(base_lines)} -> {len(now_lines)} lines)"
            )
            continue
        width = len(next(csv.reader(io.StringIO(now_lines[0])))) if now_lines else 0
        for lineno, (old, new) in enumerate(zip(base_lines, now_lines), start=1):
            if old == new:
                continue  # row untouched by the repair
            changed_rows += 1
            model = None
            if any(line == new for line in _model_a_lines(old, width)):
                model = "A"
            elif any(line == new for line in _model_b_lines(old, width)):
                model = "B"
            if model is None:
                violations.append(
                    f"{rel}: line {lineno} is not a re-split of the {base} row "
                    f"(content moved, dropped, or reworded)"
                )
                continue
            joined = ",".join(next(csv.reader(io.StringIO(new))))
            missing = [t for t in _tokens_of(old, model) if t not in joined]
            if missing:
                violations.append(
                    f"{rel}: line {lineno} drops original tokens: {missing[:3]}"
                )
    return violations, changed_rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="repo root holding docs/evidence/data (default: this checkout)",
    )
    parser.add_argument(
        "--verify-repair",
        action="store_true",
        help="re-prove worktree rows changed since --base are pure re-splits",
    )
    parser.add_argument("--base", default="HEAD", help="git rev for --verify-repair")
    args = parser.parse_args()

    violations, files, rows_total = check_widths(args.root / "docs" / "evidence" / "data")
    print(f"claims csvs checked: {files} ({rows_total} rows, all at header width)")

    changed_rows = 0
    if args.verify_repair:
        violations_v, changed_rows = verify_repair(args.root.resolve(), args.base)
        violations.extend(violations_v)
        print(f"verify-repair vs {args.base}: {changed_rows} changed rows re-proven")

    if violations:
        print("violations:")
        for violation in violations:
            print(f"  - {violation}")
        return 1
    print("ok: every claims row parses at header width (csv.DictReader cannot shift)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
