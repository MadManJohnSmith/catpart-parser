#!/usr/bin/env python3
"""Cross-validate the v1 parser against the committed evidence CSVs.

Before the C1 baseline row is recorded, this script runs the actual
``catpart-inspect`` seam (:func:`catpart.cli.build_inspect_report`, the
code the fitness run will use) over every manifest file and compares
each output field against the independently produced committed evidence
data:

- ``docs/evidence/data/container-table.csv`` (record count and name1
  sequence from scripts/triage/decode_container_table.py, magic_ok
  files);
- ``docs/evidence/data/trailer-scan.csv`` (header dwords, ff x8 flag,
  trailer A..G, ends_cbend from scripts/triage/decode_trailer.py,
  magic_ok files);
- the manifest's own ``detected_version`` and ``kind`` columns (kind:
  law K1, docs/evidence/2026-11-07-container-kind-law.md).

Every output is also validated against the committed schema v1. Any
mismatch is a parser bug to fix before recording a baseline row.

Read-only over the corpus; run with: python3 -I scripts/triage/verify_v1_parser.py
"""
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from catpart.cli import build_inspect_report  # noqa: E402
from catpart.schema import load_schema  # noqa: E402
from catpart.schema.validate import validate  # noqa: E402

MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
TABLE_CSV = ROOT / "docs" / "evidence" / "data" / "container-table.csv"
TRAILER_CSV = ROOT / "docs" / "evidence" / "data" / "trailer-scan.csv"


def main():
    schema = load_schema("v1")
    table = {r["sha256"]: r for r in csv.DictReader(TABLE_CSV.open())}
    trailer = {r["sha256"]: r for r in csv.DictReader(TRAILER_CSV.open())}
    mismatches = Counter()
    examples = {}
    checked = 0
    for m in csv.DictReader(MANIFEST.open()):
        sha = m["sha256"]
        path = ROOT / m["local_path"]
        if not path.is_file():
            mismatches["file-missing"] += 1
            continue
        try:
            report = build_inspect_report(path)
        except (OSError, ValueError) as exc:
            # The documented file-level refusal; legitimate only for the
            # 6 mislabeled (magic_ok=no) corpus files.
            if m["magic_ok"] == "yes":
                mismatches["unexpected-refusal"] += 1
                examples.setdefault("unexpected-refusal", (m["path"], "parse", str(exc)))
            else:
                checked += 1
            continue
        validate(report, schema)
        checked += 1

        def bad(field, expected, actual):
            mismatches[field] += 1
            examples.setdefault(field, (m["path"], expected, actual))

        if report["detected_version"] != (m["detected_version"] or "unknown"):
            bad("detected_version", m["detected_version"], report["detected_version"])
        if m["magic_ok"] != "yes":
            continue  # the 6 mislabeled files: no evidence-CSV row to compare

        t = table[sha]
        names = [n for n in t["names"].split(";") if n]
        got_names = [c["name"] for c in report["containers"]]
        if got_names != names:
            bad("container-names", (t["n_records"], names[:5]), (len(got_names), got_names[:5]))
        tv = trailer[sha]
        exp = {
            "header_dword": int(tv["dword8"]),
            "header_dword12": int(tv["dword12"]),
            "file_size": int(tv["size_bytes"]),
        }
        if report["ff8_at_16_24"] != (tv["ff8_at_16_24"] == "True"):
            bad("ff8_at_16_24", tv["ff8_at_16_24"], report["ff8_at_16_24"])
        for field in ("header_dword", "header_dword12", "file_size"):
            if report[field] != exp[field]:
                bad(field, exp[field], report[field])
        for out_field, col in (
            ("header_dword16", "dword16"),
            ("header_dword20", "dword20"),
        ):
            want = None if tv[col] == "" else int(tv[col])
            if report[out_field] != want:
                bad(out_field, want, report[out_field])
        tr = report["trailer"]
        if (tr is None) != (tv["ends_cbend"] == "False"):
            bad("trailer-presence", tv["ends_cbend"], tr is not None)
        elif tr is not None:
            for out_field, col in (
                ("a", "A"),
                ("registration_offset", "B"),
                ("c", "C"),
                ("d", "D"),
                ("e", "E"),
                ("f", "F"),
                ("tail_region_length", "G"),
            ):
                if tr[out_field] != int(tv[col]):
                    bad(f"trailer.{out_field}", int(tv[col]), tr[out_field])
        # kind: K1 with the documented 8 no-table exceptions
        if got_names:
            want_kind = m["kind"]
        else:
            want_kind = "unknown"
        if report["kind"] != want_kind:
            bad("kind", want_kind, report["kind"])

    print(f"files cross-checked (schema v1 validated): {checked}")
    if not mismatches:
        print("mismatches: 0 - parser agrees with every committed evidence artifact")
        return 0
    print("MISMATCHES:")
    for field, count in mismatches.most_common():
        print(f"  {field}: {count}")
        if field in examples:
            print(f"    e.g. {examples[field]}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
