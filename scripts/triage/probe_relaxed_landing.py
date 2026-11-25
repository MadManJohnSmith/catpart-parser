#!/usr/bin/env python3
"""Landing audit for the relaxed facet families 0x44/0x41 (ticket #61).

The T3 admission (2026-11-20) shipped the two families under the strict
mesh guard and measured +701 triangles / +191,338 mm² on 55 of the 115
carrier files.  The open evidence item is the per-record landing table:
do the records' references resolve to decoded element coordinates, and
do their loops triangulate?

The probe re-runs the shipped ``_export_data`` seam with a thin wrapper
around :func:`catpart.geometry.composite.parse_strip_records`; it never
re-implements the store resolution.  For every 0x44/0x41 record the
export path sees it records:

- ``refs`` and how many are inside the record's element space;
- how many land on a WRITTEN element vs a skip slot (the curve entries
  the dup-pin weld handles);
- the loops' triangles/area when every ref of the loop is written
  (strip/fan semantics, the same ``_loop_triangles``);
- degenerate triangles and the record's area.

The carrier roster is the 115 files whose 2026-11-20 report entry names
``unresolved-facet-family`` with 0x44 or 0x41.  The probe is read-only
over the corpus and writes one CSV row per record plus a per-file CSV
with the shipped export's relaxed-loop counters.

Usage:
    .venv/bin/python -B scripts/triage/probe_relaxed_landing.py \
        --out docs/evidence/data/relaxed-facets-landing-claims.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from catpart.geometry import composite  # noqa: E402
from catpart.geometry.export import _export_data  # noqa: E402

DEFAULT_REPORT = ROOT / "fitness/reports/20261120T183229Z-d503ff.json"
DEFAULT_OUT = ROOT / "docs/evidence/data/relaxed-facets-landing.csv"
DEFAULT_FILES_OUT = ROOT / "docs/evidence/data/relaxed-facets-landing-files.csv"
MANIFEST = ROOT / "manifests/corpus-manifest.csv"
MARKERS = (0x44, 0x41)


def carrier_roster(report_path: Path) -> dict[str, str]:
    """The 115 carrier shas mapped to their repo-local paths.

    The report's ``path`` is corpus-relative, so the manifest's
    ``local_path`` is the authority; the report path is a fallback for
    entries the manifest does not list.
    """
    manifest = {
        row["sha256"][:16]: row["local_path"]
        for row in csv.DictReader(MANIFEST.open(newline=""))
    }
    report = json.loads(report_path.read_text())
    carriers: dict[str, str] = {}
    for entry in report["files"]:
        for warning in (entry.get("l2") or {}).get("warnings") or []:
            if warning["class"] != "unresolved-facet-family":
                continue
            if "0x44" not in warning["detail"] and "0x41" not in warning["detail"]:
                continue
            sha = entry["sha256"][:16]
            local = manifest.get(sha) or entry.get("path")
            if local:
                carriers[sha] = local
    return carriers


def area(points: list[tuple[float, float, float]], tris) -> float:
    total = 0.0
    for a, b, c in tris:
        va, vb, vc = points[a], points[b], points[c]
        ux, uy, uz = vb[0] - va[0], vb[1] - va[1], vb[2] - va[2]
        wx, wy, wz = vc[0] - va[0], vc[1] - va[1], vc[2] - va[2]
        cx, cy, cz = uy * wz - uz * wy, uz * wx - ux * wz, ux * wy - uy * wx
        total += (cx * cx + cy * cy + cz * cz) ** 0.5 / 2.0
    return total


def record_stats(sha: str, local: str, rec, element_count: int, elements):
    offset, marker, _normal, counts, refs, width = rec
    in_bounds = sum(1 for r in refs if 0 <= r < element_count)
    written = skip = 0
    decoded = elements is not None
    points: list[tuple[float, float, float]] = []
    rank: dict[int, int] = {}
    if decoded:
        for i, (_slot, point) in enumerate(elements):
            if point is not None:
                rank[i] = len(points)
                points.append(point)
        for r in refs:
            if 0 <= r < len(elements):
                if elements[r][1] is None:
                    skip += 1
                else:
                    written += 1
    triangles = degenerate = 0
    loop_count = loop_skip = loops_triangulated = 0
    record_area = 0.0
    pos = 0
    for count in counts:
        idxs = refs[pos : pos + count]
        pos += count
        loop_count += 1
        if any(r not in rank for r in idxs):
            loop_skip += 1
            continue
        kind = 0x4C if marker == 0x44 else 0x42
        tris, deg = composite._loop_triangles(kind, [rank[r] for r in idxs], points)
        triangles += len(tris)
        degenerate += deg
        loops_triangulated += 1
        record_area += area(points, tris)
    return {
        "sha16": sha,
        "path": local,
        "offset": offset,
        "marker": f"0x{marker:02x}",
        "width": width,
        "decoded": int(decoded),
        "loops": loop_count,
        "loops_with_skip": loop_skip,
        "loops_triangulated": loops_triangulated,
        "refs": len(refs),
        "refs_in_bounds": in_bounds,
        "refs_written": written,
        "refs_skip": skip,
        "triangles": triangles,
        "degenerate": degenerate,
        "area_mm2": f"{record_area:.6f}",
    }


RECORD_FIELDS = [
    "sha16",
    "path",
    "offset",
    "marker",
    "width",
    "decoded",
    "loops",
    "loops_with_skip",
    "loops_triangulated",
    "refs",
    "refs_in_bounds",
    "refs_written",
    "refs_skip",
    "triangles",
    "degenerate",
    "area_mm2",
]

FILE_FIELDS = [
    "sha16",
    "path",
    "stage",
    "relaxed_loops_accepted",
    "relaxed_loops_declined",
    "records",
    "records_landed",
    "record_triangles",
    "record_area_mm2",
    "export_triangles",
]


def run(report_path: Path, out_path: Path, files_out: Path, limit: int | None) -> int:
    carriers = carrier_roster(report_path)
    rows: list[dict] = []
    file_rows: list[dict] = []
    missing: list[str] = []
    exported = 0
    export_errors: list[str] = []

    for sha, local in sorted(carriers.items()):
        if limit is not None and exported >= limit:
            break
        path = ROOT / local
        if not path.exists():
            missing.append(local)
            continue
        captured: dict[tuple, tuple] = {}
        orig = composite.parse_strip_records

        def wrapper(data, lo, hi, element_count, elements=None):
            records, headers = orig(data, lo, hi, element_count, elements)
            for rec in records:
                if rec[1] not in MARKERS:
                    continue
                key = (rec[0], rec[1], rec[3], rec[4], rec[5])
                prev = captured.get(key)
                if prev is None or (prev[2] is None and elements is not None):
                    captured[key] = (rec, element_count, elements)
            return records, headers

        composite.parse_strip_records = wrapper
        try:
            summary, _verts, tris = _export_data(path.read_bytes())
            exported += 1
        except Exception as exc:  # named, never silent
            export_errors.append(f"{sha} {local}: {type(exc).__name__}: {exc}")
            summary, tris = None, []
        finally:
            composite.parse_strip_records = orig

        records = [
            record_stats(sha, local, rec, element_count, elements)
            for rec, element_count, elements in captured.values()
        ]
        rows.extend(records)
        comp = (summary or {}).get("composite") or {}
        file_rows.append(
            {
                "sha16": sha,
                "path": local,
                "stage": comp.get("stage", ""),
                "relaxed_loops_accepted": comp.get("relaxed_loops_accepted", 0),
                "relaxed_loops_declined": comp.get("relaxed_loops_declined", 0),
                "records": len(records),
                "records_landed": sum(1 for r in records if r["triangles"]),
                "record_triangles": sum(r["triangles"] for r in records),
                "record_area_mm2": f"{sum(float(r['area_mm2']) for r in records):.6f}",
                "export_triangles": len(tris),
            }
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RECORD_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    files_out.parent.mkdir(parents=True, exist_ok=True)
    with files_out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FILE_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(file_rows)

    print(
        f"carrier files: {len(carriers)}  exported: {exported}  "
        f"missing: {len(missing)}  errors: {len(export_errors)}"
    )
    for line in missing[:10]:
        print(f"  missing: {line}")
    for line in export_errors[:10]:
        print(f"  error: {line}")
    by_marker = Counter(row["marker"] for row in rows)
    totals = defaultdict(int)
    for row in rows:
        for key in (
            "loops",
            "loops_with_skip",
            "loops_triangulated",
            "refs",
            "refs_in_bounds",
            "refs_written",
            "refs_skip",
            "triangles",
            "degenerate",
        ):
            totals[key] += int(row[key])
        totals["area_mm2"] += float(row["area_mm2"])
    print(f"records: {len(rows)}  {dict(by_marker)}")
    print(
        "refs: {refs}  in-bounds: {refs_in_bounds}  written: {refs_written}  "
        "skip: {refs_skip}  loops: {loops}  loops-with-skip: {loops_with_skip}  "
        "loops-triangulated: {loops_triangulated}".format(**totals)
    )
    print(
        "triangles: {triangles}  degenerate: {degenerate}  "
        "area: {area_mm2:.1f} mm²".format(**totals)
    )
    print(
        "files with a landed record: "
        f"{sum(1 for r in file_rows if r['records_landed'])}"
    )
    print(f"wrote {out_path} ({len(rows)} rows)")
    print(f"wrote {files_out} ({len(file_rows)} rows)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--files-out", type=Path, default=DEFAULT_FILES_OUT)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    return run(args.report, args.out, args.files_out, args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
