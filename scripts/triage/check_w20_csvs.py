#!/usr/bin/env python3
"""Check docs/evidence/data/w20-*.csv CSV-composability at introduction.

The W20 dodge-routing family (dispatch-recipes hard rule: a new
evidence-data CSV family lands WITH its mechanical hygiene check, not
at phase close). The rep CSVs carry decode failure strings in one
field (``failure``), which may contain commas, so quoting is
load-bearing: one unquoted comma shifts the following bbox columns
silently. Enforces, on every committed ``docs/evidence/data/w20-*.csv``:

1. the file parses under ``csv.reader``;
2. every row (header included) has exactly the header's field count;
3. every field is free of stray leading/trailing whitespace (the
   probe writers emit clean fields only).

``--selftest`` pins the discriminating edge on a synthetic fixture: a
row whose failure field carries an unquoted comma fails both width
(4 fields vs 3 header fields) and the parse, while the same field
properly quoted passes — the negative-fixture rule.
"""

from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "docs" / "evidence" / "data"

_SELFTEST_CSV = (
    "span,rep,failure,exported\n"
    '0,244,"rep-declined: pool group not re-listed (2 of 320 vertices)",0\n'
    "0,245,rep-declined: facet refs beyond the element space (max 500 >= 320, M2b),0\n"
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
    """The pinned edge: the quoted failure row parses at header width;
    the SAME content unquoted shifts to 4 fields (the failure mode), and
    the checker flags it on a synthetic file."""
    rows = list(csv.reader(io.StringIO(_SELFTEST_CSV)))
    failures = []
    if len(rows[1]) != 4:
        failures.append(f"selftest: quoted row must parse at width 4, got {len(rows[1])}")
    if len(rows[2]) == 4:
        failures.append(
            "selftest: unquoted comma row unexpectedly parsed at width 4 — "
            "the fixture does not discriminate"
        )
    synth = Path("w20-selftest-fixture.csv")
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
        prog="check_w20_csvs",
        description="CSV-composability check for the docs/evidence/data/w20-*.csv family.",
    )
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        failures = run_selftest()
        if failures:
            for f in failures:
                print(f"selftest FAIL: {f}")
            return 1
        print("selftest ok")
        return 0
    failures = []
    files = sorted(DATA.glob("w20-*.csv"))
    if not files:
        failures.append("no docs/evidence/data/w20-*.csv files found")
    for path in files:
        failures.extend(check_file(path))
    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print(f"ok: {len(files)} w20 CSVs parse at constant width, clean fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
