#!/usr/bin/env python3
"""Verify the container-kind law: table names determine part vs product.

Evidence base: docs/evidence/2026-11-07-container-table-and-trailer.md
(record format) and docs/evidence/2026-11-07-container-triage.md (the
container-name table as the file's list of containers). The Phase 0
manifest records each file's kind (``part``/``product``, from its source
path and extension) independently of any byte parsing. This script
cross-tabulates the manifest kind against the container-name table
records decoded by ``scripts/triage/decode_container_table.py``
(docs/evidence/data/container-table.csv, ``names`` column = the records'
name1 values) and reports the confusion matrix.

Claim under test (kind law K1): among files whose table was found,

- ``CATPrtCont`` among the name1 values  <=>  manifest kind ``part``;
- ``CATProdCont`` or ``CATMechProdCont`` among the name1 values, with no
  ``CATPrtCont``  <=>  manifest kind ``product``.

Read-only over committed CSVs; run with: python3 -I scripts/triage/verify_kind_law.py
"""
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TABLE_CSV = ROOT / "docs" / "evidence" / "data" / "container-table.csv"
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"


def kind_from_names(names):
    """The K1 rule applied to a record's name1 values."""
    if "CATPrtCont" in names:
        return "part"
    if "CATProdCont" in names or "CATMechProdCont" in names:
        return "product"
    return "unknown"


def main():
    manifest = {r["sha256"]: r for r in csv.DictReader(MANIFEST.open())}
    confusion = Counter()
    mismatches = []
    no_table = Counter()
    for row in csv.DictReader(TABLE_CSV.open()):
        m = manifest[row["sha256"]]
        names = tuple(n for n in row["names"].split(";") if n)
        if not names:
            no_table[(m["kind"], m["detected_version"] or "unknown")] += 1
            continue
        predicted = kind_from_names(names)
        confusion[(m["kind"], predicted)] += 1
        if m["kind"] != predicted:
            mismatches.append((m["kind"], predicted, m["path"]))
    print("files with a parsed table:", sum(confusion.values()))
    print("manifest kind x K1-predicted kind:")
    for key, count in sorted(confusion.items()):
        print(f"  {key[0]:>8} -> {key[1]:>8}: {count}")
    disagreements = sum(
        c for (kind, predicted), c in confusion.items() if kind != predicted
    )
    print("disagreements:", disagreements)
    for m in mismatches[:10]:
        print("  MISMATCH", m)
    print("files without a table (excluded from K1):", sum(no_table.values()))
    for key, count in sorted(no_table.items()):
        print(f"  kind={key[0]} version={key[1]}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
