#!/usr/bin/env python3
"""Probe: the real open rate over the whole part manifest (2026-11-19).

Every ``kind=part`` row of ``manifests/corpus-manifest.csv`` (1,442
rows) is pushed through the shipped export seam
(:func:`catpart.geometry.export.build_export`, in-process, no CLI) and
classified by what the export actually carries.  Six of those rows are
``kind=unknown`` in the latest report (four ``magic_ok=no``
non-containers and two files with no detectable version marker); they
are measured here too, because the question is the manifest, not the
report's population, and their report class (``missing-geometry-store``)
is the one the report recorded:

- ``MESH`` — the summary reports at least one triangle (facets, the
  exact ``a5 03 34`` surface route, or the structured-grid route);
- ``DISPLAY`` — zero triangles but a ``no_surface_display`` block with
  points and/or law-pinned curve segments (the shipped display route);
- ``BLANK`` — neither: no triangle and no display carrier.

The latest fitness report (highest ``fitness/reports/*.json`` timestamp)
supplies the per-part failure class of the same corpus digest, so the
census can be crossed with the class the previous run recorded:
``pass`` (L2 passed), the named ``error_class``, else the
``failed_check`` (``empty-mesh``, ``not-manifold``,
``degenerate-triangles``).

Writes ``docs/evidence/data/open-rate-files.csv`` (1,442 rows) in
deterministic order (manifest ``sha256``, then ``path``). The PLY output
lands in a temporary directory and is discarded; the corpus is opened
read-only. A BLANK row also gets a bare ``display.scan_part`` pass, so
the BLANK list can say whether the file carries a display carrier at all
and, in particular, whether it carries a count-framed f32 array.

Usage: python scripts/triage/probe_open_rate.py
"""

from __future__ import annotations

import csv
import json
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from catpart.geometry import ExportError, display  # noqa: E402
from catpart.geometry.export import build_export  # noqa: E402

DATA = REPO_ROOT / "docs" / "evidence" / "data"
MANIFEST = REPO_ROOT / "manifests" / "corpus-manifest.csv"
REPORTS = REPO_ROOT / "fitness" / "reports"
OUT = DATA / "open-rate-files.csv"

FIELDS = [
    "sha16",
    "path",
    "split",
    "report kind",
    "report class",
    "open kind",
    "triangles",
    "points",
    "segments",
]


def latest_report() -> tuple[Path, dict]:
    """The report with the highest timestamp (``YYYYMMDDTHHMMSSZ-*.json``)."""
    path = max(REPORTS.glob("*.json"), key=lambda p: p.name)
    return path, json.loads(path.read_text())


def report_class(entry: dict | None) -> str:
    """The class the report recorded: pass, a named error, or a failed check."""
    if entry is None:
        return "not-in-report"
    l2 = entry.get("l2")
    if not l2:
        return "no-l2"
    if l2.get("status") == "pass":
        return "pass"
    return l2.get("error_class") or l2.get("failed_check") or "unknown"


def report_kind(entry: dict | None) -> str:
    """The kind the report recorded for the sha (``part`` or ``unknown``)."""
    if entry is None:
        return "not-in-report"
    return entry.get("kind") or "unknown"


def manifest_rows() -> list[dict]:
    """Every ``kind=part`` row of the manifest (1,442).

    The latest report reclassifies six of them as ``unknown`` (four
    ``magic_ok=no`` non-containers and two files with no detectable
    version marker) and leaves them outside its L2 population. They are
    kept here: the manifest is the target, and the report still records
    a class for each (``missing-geometry-store``). The CSV's ``report
    kind`` column names the six.
    """
    with MANIFEST.open(newline="") as fh:
        rows = [row for row in csv.DictReader(fh) if row["kind"] == "part"]
    return sorted(rows, key=lambda row: (row["sha256"], row["path"]))


def classify(summary: dict) -> tuple[str, int, int, int]:
    """Return ``(open kind, triangles, points, segments)`` for a summary."""
    triangles = int(summary.get("triangle_count") or 0)
    block = summary.get("no_surface_display") or {}
    points = int(block.get("point_count") or 0)
    segments = int(block.get("curve_segment_count") or 0)
    if triangles > 0:
        return "MESH", triangles, points, segments
    if points > 0 or segments > 0:
        return "DISPLAY", triangles, points, segments
    return "BLANK", triangles, points, segments


def missing_carrier(
    error_class: str | None, summary: dict | None, scan: display.DisplayScan | None
) -> str:
    """A short phrase naming what a BLANK part lacks, measured not guessed."""
    arrays = scan.bagrep_arrays if scan is not None else 0
    if scan is not None and arrays and not scan.has_carriers:
        return (
            f"{arrays} count-framed f32 array(s) found but every triple "
            "left the model gate; no other display carrier"
        )
    if error_class == "missing-geometry-store":
        return (
            "no located geometry store and no display carrier "
            "(no 3-divisible f64 run, law-holding curve record, or "
            "count-framed f32 array)"
        )
    if error_class == "no-evaluable-surface":
        blocked = f"; {arrays} f32 array(s) held back" if arrays else ""
        return (
            "a5 03 34 frames but no evaluable surface "
            "(the a5 priority keeps the display route closed)" + blocked
        )
    if error_class == "untriangulable-grid":
        return "grid candidates but none triangulates; no display carrier"
    if error_class and error_class.startswith("malformed-"):
        return f"malformed store ({error_class}); no decodable carrier"
    if error_class == "undecoded-variant":
        return (
            "no exportable facet store, no a5 surface, no structured grid, "
            "no display carrier (no 3-divisible f64 run, law-holding curve "
            "record, or count-framed f32 array)"
        )
    if error_class:
        return f"export failed ({error_class}); no decodable carrier"
    if summary is not None:
        return (
            "vertices-only store success: no facet records, "
            "no surface/grid, no display carrier"
        )
    return "no decodable carrier"


def pct(part: int, whole: int) -> str:
    return f"{part}/{whole} = {part / whole:.4f}" if whole else "0/0"


def main() -> int:
    report_path, report = latest_report()
    by_sha = {entry["sha256"]: entry for entry in report["files"]}
    rows = manifest_rows()

    counts: Counter[tuple[str, str]] = Counter()
    by_split: dict[str, Counter[str]] = defaultdict(Counter)
    blank: list[dict] = []
    totals: Counter[str] = Counter()
    out_rows: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="catpart-open-rate-") as tmp:
        out_ply = Path(tmp) / "part.ply"
        for index, row in enumerate(rows, 1):
            entry = by_sha.get(row["sha256"])
            klass = report_class(entry)
            rkind = report_kind(entry)
            summary = None
            error_class = None
            try:
                summary = build_export(Path(row["local_path"]), out_ply)
            except ExportError as exc:
                error_class = exc.error_class
            except OSError:
                error_class = "unreadable-file"
            kind, triangles, points, segments = (
                classify(summary) if summary is not None else ("BLANK", 0, 0, 0)
            )
            counts[(kind, klass)] += 1
            by_split[row["split"]][kind] += 1
            totals[kind] += 1
            out_rows.append(
                {
                    "sha16": row["sha256"][:16],
                    "path": row["path"],
                    "split": row["split"],
                    "report kind": rkind,
                    "report class": klass,
                    "open kind": kind,
                    "triangles": triangles,
                    "points": points,
                    "segments": segments,
                }
            )
            if kind == "BLANK":
                scan = None
                try:
                    scan = display.scan_part(Path(row["local_path"]).read_bytes())
                except OSError:
                    pass
                blank.append(
                    {
                        "sha16": row["sha256"][:16],
                        "path": row["path"],
                        "split": row["split"],
                        "report kind": rkind,
                        "class": klass,
                        "export class": error_class or "pass",
                        "missing": missing_carrier(error_class, summary, scan),
                        "arrays": scan.bagrep_arrays if scan else 0,
                        "scan points": len(scan.points) if scan else 0,
                    }
                )
            if index % 200 == 0:
                print(f"  {index}/{len(rows)}", file=sys.stderr)

    DATA.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(out_rows)

    whole = len(rows)
    print(f"report {report['run_id']} ({report_path.name})")
    print(f"parts {whole}")
    print("overall")
    for kind in ("MESH", "DISPLAY", "BLANK"):
        print(f"  {kind:8s} {pct(totals[kind], whole)}")
    for split in sorted(by_split):
        split_total = sum(by_split[split].values())
        print(f"split {split} ({split_total})")
        for kind in ("MESH", "DISPLAY", "BLANK"):
            print(f"  {kind:8s} {pct(by_split[split][kind], split_total)}")
    print("cross (open kind x report class)")
    for kind in ("MESH", "DISPLAY", "BLANK"):
        for klass in sorted({k for (_, k) in counts}):
            n = counts[(kind, klass)]
            if n:
                print(f"  {kind:8s} {klass:24s} {n}")
    print(f"blank {len(blank)}")
    for row in blank:
        print(
            f"  {row['sha16']} {row['split']:8s} {row['report kind']:6s} "
            f"{row['class']:24s} {row['export class']:22s} "
            f"arrays={row['arrays']:2d} scan_points={row['scan points']:5d} "
            f"{row['path']}"
        )
    print("BLANK_GROUPS")
    groups = Counter(
        (row["class"], "array" if row["arrays"] else "no-array") for row in blank
    )
    for (klass, array), n in sorted(groups.items()):
        print(f"  {n:3d}  {klass:24s} {array}")
    print("BLANK_MISSING")
    for reason, n in Counter(row["missing"] for row in blank).most_common():
        print(f"  {n:3d}  {reason}")
    print("REPORT_KIND")
    for rkind in sorted({row["report kind"] for row in out_rows}):
        n = sum(1 for row in out_rows if row["report kind"] == rkind)
        print(f"  {rkind:14s} {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
