#!/usr/bin/env python3
"""W6 features builder: one compact JSONL record per labeled part (official
corpus + Submarino) for the laya domain-calibration run.

Sources (all already committed on this branch, no parser invocation here):
- ``fitness/reports/<latest>.json`` — per-part ``l2`` block (status,
  error_class, failed_check, counts, mesh manifold/closed/boundary, warning
  classes, containers, detected_version) for the 1,442 official parts.
- ``docs/evidence/data/open-rate-files.csv`` — open outcome per sha16
  (report kind/class, open kind, display points/segments) for the corpus.
- ``manifests/corpus-manifest.csv`` — size_bytes per sha256.
- ``~/.local/state/catpart-parser/bench-submarine/m1_files.csv`` — the
  Submarino rows (same feature columns, plus seconds).

Label (``fail_family``): ``pass`` | ``check:<failed_check>`` |
``error:<error_class>`` | ``fail-unclassified`` — exactly the census
families. Files with no l2 verdict (products, not-a-catpart) are skipped.

Streaming: the fitness report is the only JSON loaded whole (2.3 MB);
everything else is a line-at-a-time reader, and the JSONL out file is
appended record by record.

Usage:
  python -B scripts/triage/w6_build_features.py \
      --out ~/.local/state/catpart-parser/w6-laya/features.jsonl \
      [--fitness-report fitness/reports/20261121T103944Z-d2c9ff.json]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SUBMARINE_CSV = Path.home() / ".local/state/catpart-parser/bench-submarine/m1_files.csv"

VERSION_RE = re.compile(r"V(\d+)R(\d+)")


def version_family(detected: str | None) -> str:
    m = VERSION_RE.match(detected or "")
    return f"V{m.group(1)}R{m.group(2)}" if m else (detected or "unknown")


def fail_family(l2: dict) -> str:
    # fitness-report l2 blocks carry "status"; m1_files.csv rows carry
    # "l2_status" — same verdict, two shapes
    status = l2.get("status") or l2.get("l2_status")
    if status == "pass":
        return "pass"
    if l2.get("error_class"):
        return f"error:{l2['error_class']}"
    if l2.get("failed_check"):
        return f"check:{l2['failed_check']}"
    return "fail-unclassified"


def corpus_records(args) -> Counter:
    """Yield one feature record per official part with an l2 verdict."""
    # sha256 -> (size_bytes, local_path)
    manifest: dict[str, dict] = {}
    with open(args.manifest, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            manifest[row["sha256"]] = row

    # sha16 -> open-rate outcome
    openrate: dict[str, dict] = {}
    with open(args.open_rate_csv, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            openrate[row["sha16"]] = row

    dist: Counter = Counter()
    report = json.loads(Path(args.fitness_report).read_text(encoding="utf-8"))
    with open(args.out, "a", encoding="utf-8") as out:
        for f in report["files"]:
            l2 = f.get("l2")
            if not l2:
                continue
            sha16 = f["sha256"][:16]
            orow = openrate.get(sha16)
            mrow = manifest.get(f["sha256"]) or {}
            mesh = l2.get("mesh") or {}
            rec = {
                "source": "corpus",
                "split": f.get("split") or "unknown",
                "sha256": f["sha256"],
                "path": f["path"],
                "local_path": mrow.get("local_path") or "",
                "version_family": version_family(f.get("detected_version")),
                "classification": f.get("classification") or "",
                "containers": list(f.get("container_names") or []),
                "size_bytes": int(mrow.get("size_bytes") or 0),
                "l2_status": l2.get("status") or "",
                "error_class": l2.get("error_class") or "",
                "failed_check": l2.get("failed_check") or "",
                "report_kind": (orow or {}).get("report kind", "part"),
                "report_class": (orow or {}).get("report class", ""),
                "open_class": (orow or {}).get("open kind", ""),
                "vertex_count": int(l2.get("vertex_count") or 0),
                "triangle_count": int(l2.get("triangle_count") or 0),
                "degenerate_triangle_count": int(l2.get("degenerate_triangle_count") or 0),
                "display_points": int((orow or {}).get("points") or 0),
                "display_segments": int((orow or {}).get("segments") or 0),
                "mesh_manifold": mesh.get("manifold"),
                "mesh_closed": mesh.get("closed"),
                "boundary_edge_count": int(mesh.get("boundary_edge_count") or 0),
                "warnings": sorted({w.get("class") for w in l2.get("warnings") or [] if w.get("class")}),
                "seconds": 0.0,
                "fail_family": fail_family(l2),
            }
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            dist[rec["fail_family"]] += 1
    return dist


def submarine_records(args) -> Counter:
    """Yield one feature record per Submarino row of m1_files.csv."""
    dist: Counter = Counter()
    with open(args.submarine_csv, newline="", encoding="utf-8") as fh, open(
        args.out, "a", encoding="utf-8"
    ) as out:
        for row in csv.DictReader(fh):
            rec = {
                "source": "submarine",
                "split": "submarine",
                "sha256": "",
                "path": row["path"],
                "version_family": "unknown",
                "classification": "",
                "containers": [],
                "size_bytes": int(row["size_bytes"] or 0),
                "l2_status": row["l2_status"] or "",
                "error_class": row["error_class"] or "",
                "failed_check": row["failed_check"] or "",
                "report_kind": "part",
                "report_class": row["error_class"] or row["failed_check"] or row["l2_status"],
                "open_class": row["open_class"] or "",
                "vertex_count": int(row["vertex_count"] or 0),
                "triangle_count": int(row["triangle_count"] or 0),
                "degenerate_triangle_count": int(row["degenerate_triangle_count"] or 0),
                "display_points": int(row["display_points"] or 0),
                "display_segments": int(row["display_segments"] or 0),
                "mesh_manifold": None,
                "mesh_closed": None,
                "boundary_edge_count": 0,
                "warnings": sorted({w for w in (row["warnings"] or "").split(";") if w}),
                "seconds": float(row["seconds"] or 0.0),
                "fail_family": fail_family(row),
            }
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            dist[rec["fail_family"]] += 1
    return dist


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out",
        type=Path,
        default=Path.home() / ".local/state/catpart-parser/w6-laya/features.jsonl",
    )
    ap.add_argument(
        "--fitness-report",
        default="fitness/reports/20261121T103944Z-d2c9ff.json",
    )
    ap.add_argument("--manifest", default=REPO / "manifests/corpus-manifest.csv")
    ap.add_argument(
        "--open-rate-csv",
        default=REPO / "docs/evidence/data/open-rate-files.csv",
    )
    ap.add_argument("--submarine-csv", type=Path, default=SUBMARINE_CSV)
    args = ap.parse_args()
    if not Path(args.fitness_report).is_absolute():
        args.fitness_report = REPO / args.fitness_report
    args.out.parent.mkdir(parents=True, exist_ok=True)
    # fresh output file (append mode is for resumable streams within a run)
    args.out.write_text("")

    cdist = corpus_records(args)
    sdist = submarine_records(args)
    print("corpus fail_family:", dict(cdist))
    print("submarine fail_family:", dict(sdist))
    print(f"total records: {sum(cdist.values()) + sum(sdist.values())} -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
