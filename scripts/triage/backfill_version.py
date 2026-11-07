#!/usr/bin/env python3
"""Backfill the detected-version column into the corpus manifest.

Reads manifests/corpus-manifest.csv, detects the embedded CNEXTINFOS
release marker (docs/evidence/2026-11-07-container-triage.md, "Per-file
version marker") for every magic_ok file via catpart.version
(8 KB window first, 64 KB fallback, "unknown" bucket — map decision on
ticket #4), and rewrites the manifest with a ``detected_version`` column
inserted after ``reported_version``. Column semantics:

- ``V5RxxSPxxHFxx``: the marker token found in the file.
- ``unknown``: a magic-verified container with no marker (338/1818 in
  the Phase 1 evidence).
- empty: not a container (``magic_ok=no`` rows — detection is not
  applicable), so the manifest's ``unknown`` count stays comparable to
  the evidence's 338.

Read-only with respect to the corpus; only the manifest is rewritten.
Run with the project environment (the core is stdlib-only per ADR-0002):

    .venv/bin/python -I scripts/triage/backfill_version.py
"""
import csv
import sys
from collections import Counter
from pathlib import Path

from catpart.version import detect_version_with_window

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
VERSION_COLUMN = "detected_version"


def main():
    with MANIFEST.open(newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    if VERSION_COLUMN in fieldnames:
        print(f"{MANIFEST} already has a {VERSION_COLUMN} column; nothing to do")
        return 0
    fieldnames.insert(fieldnames.index("reported_version") + 1, VERSION_COLUMN)

    windows = Counter()
    for row in rows:
        if row["magic_ok"] != "yes":
            row[VERSION_COLUMN] = ""
            continue
        with (ROOT / row["local_path"]).open("rb") as fh:
            head = fh.read(65536)
        version, window = detect_version_with_window(head)
        row[VERSION_COLUMN] = version
        windows[window] += 1

    tmp = MANIFEST.with_suffix(".csv.tmp")
    with tmp.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(MANIFEST)

    print(f"magic_ok files: {sum(windows.values())}")
    print(f"detected in 8 KB window: {windows['8k']}")
    print(f"recovered by 64 KB fallback: +{windows['64k']}")
    print(f"unknown (no marker): {windows['unknown']}")
    print(f"wrote {MANIFEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
