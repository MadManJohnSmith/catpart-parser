#!/usr/bin/env python3
"""Check docs/evidence/data/w12-*.csv CSV-composability at introduction.

The W12 inverse-oracle family (dispatch-recipes hard rule: a new
evidence-data CSV family lands WITH its mechanical hygiene check, not
at phase close). ``registros_candidatos`` carries comma-separated gap
offsets inside one field, so quoting is load-bearing: one unquoted
comma shifts bbox columns silently. Enforces, on every committed
``docs/evidence/data/w12-*.csv``:

1. the file parses under ``csv.reader``;
2. every row (header included) has exactly the header's field count;
3. every field is free of stray leading/trailing whitespace (the
   join writer emits clean fields only).

``--selftest`` pins the discriminating edge on a synthetic fixture: a
row whose candidates field carries an unquoted comma fails both width
(3 fields vs 2 header fields) and the parse, while the same field
properly quoted passes — the negative-fixture rule.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "docs" / "evidence" / "data"

_SELFTEST_CSV = (
    "pair,rank,registros_candidatos\n"
    'audi-r8,1,"rep 38: unused=1152 gaps_owning=45031183,48549226"\n'
    "audi-r8,2,rep 0: unused=16 gaps_owning=45031183,48549226\n"
)


def check_file(path: Path) -> list[str]:
    failures = []
    text = path.read_text(encoding="utf-8")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return [f"{path.name}: empty"]
    width = len(rows[0])
    for i, row in enumerate(rows):
        if len(row) != width:
            failures.append(
                f"{path.name}: row {i} has {len(row)} fields, header has {width}"
            )
        for field in row:
            if field != field.strip():
                failures.append(f"{path.name}: row {i} field has stray whitespace")
                break
    return failures


def run_selftest() -> list[str]:
    """The pinned edge: the quoted candidates row parses at header width;
    the SAME content unquoted shifts to 4 fields (the failure mode), and
    the checker flags it on a synthetic file."""
    rows = list(csv.reader(io.StringIO(_SELFTEST_CSV)))
    failures = []
    if len(rows[1]) != 3:
        failures.append(f"selftest: quoted row must parse at width 3, got {len(rows[1])}")
    if len(rows[2]) == 3:
        failures.append(
            "selftest: unquoted comma row unexpectedly parsed at width 3 — "
            "the fixture does not discriminate"
        )
    # The real check must FLAG a width-mismatched row (synthetic file).
    synth = Path("w12-selftest-fixture.csv")
    synth.write_text(_SELFTEST_CSV, encoding="utf-8")
    try:
        found = check_file(synth)
    finally:
        synth.unlink(missing_ok=True)
    if not found:
        failures.append("selftest: checker accepted a width-shifted row")
    return failures


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="check_w12_csvs",
        description="CSV-composability gate for the W12 evidence-data family.",
    )
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        failures = run_selftest()
        for line in failures:
            print(f"selftest FAIL: {line}", file=sys.stderr)
        print(f"selftest: {'FAIL' if failures else 'ok'}")
        return 1 if failures else 0
    failures = []
    files = sorted(DATA.glob("w12-*.csv"))
    if not files:
        print("check_w12_csvs: no w12-*.csv under docs/evidence/data/")
        return 0
    for path in files:
        failures.extend(check_file(path))
    for line in failures:
        print(f"check_w12_csvs: {line}", file=sys.stderr)
    print(f"check_w12_csvs: {'FAIL' if failures else 'ok'} ({len(files)} files)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
