#!/usr/bin/env python3
"""W26 census: score the see-body compact route over the accepted
``empty-mesh`` rows.

For every row of the accepted fitness report whose L2 failure is
``empty-mesh``, read the part once, run the shipped ``_export_data``
chain (store → surface → grid → face-gp → see-body compact → display)
and score the summary with the fitness L2 gate.  Read-only over the
corpus; one CSV row per file, streamed (one part in memory at a time).

Output columns: ``sha16, path, split, outcome, failed_check, vertices,
triangles, seebody, warning, seconds, detail``.  The committed claim
rows are ``docs/evidence/data/w26-seebody-census-claims.csv``.

Run::

    .venv/bin/python -B scripts/triage/w26_seebody_census.py \
        fitness/reports/20261124T125633Z-38c46d.json \
        [--out /tmp/w26-seebody-census.csv]
"""

import argparse
import csv
import gc
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from catpart.fitness.runner import _score_export  # noqa: E402
from catpart.geometry.errors import ExportError  # noqa: E402
from catpart.geometry.export import _export_data  # noqa: E402


def load_paths(manifest_path):
    paths = {}
    with open(manifest_path, newline="") as fh:
        for row in csv.DictReader(fh):
            paths[row["sha256"]] = os.path.join(ROOT, row["local_path"])
    return paths


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", help="accepted fitness report JSON")
    parser.add_argument(
        "--manifest",
        default=os.path.join(ROOT, "manifests/corpus-manifest.csv"),
    )
    parser.add_argument(
        "--out",
        default="/tmp/w26-seebody-census.csv",
    )
    args = parser.parse_args(argv)

    report = json.load(open(args.report))
    rows = [
        row
        for row in report["files"]
        if row.get("l2") and row["l2"].get("failed_check") == "empty-mesh"
    ]
    paths = load_paths(args.manifest)
    fields = [
        "sha16", "path", "split", "outcome", "failed_check", "vertices",
        "triangles", "seebody", "warning", "seconds", "detail",
    ]
    counts = {}
    started_all = time.time()
    with open(args.out, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for i, row in enumerate(rows, 1):
            path = paths.get(row["sha256"])
            rec = {
                "sha16": row["sha256"][:16],
                "path": row["path"],
                "split": row["split"],
            }
            started = time.time()
            try:
                data = open(path, "rb").read()
                summary, _vertices, _triangles = _export_data(data)
                scored = _score_export(summary)
                rec.update(
                    outcome="export",
                    failed_check=scored["failed_check"] or "pass",
                    vertices=summary["vertex_count"],
                    triangles=summary["triangle_count"],
                    seebody="seebody_gp" in summary,
                    warning=",".join(w["class"] for w in summary["warnings"]),
                )
            except ExportError as exc:
                rec.update(
                    outcome="error",
                    failed_check=exc.error_class,
                    detail=exc.detail[:160],
                )
            except Exception as exc:  # noqa: BLE001 - the sweep must keep going
                rec.update(
                    outcome="crash",
                    failed_check=type(exc).__name__,
                    detail=str(exc)[:160],
                )
            rec["seconds"] = round(time.time() - started, 3)
            counts[rec["failed_check"]] = counts.get(rec["failed_check"], 0) + 1
            writer.writerow(rec)
            fh.flush()
            if i % 20 == 0:
                print(f"{i}/{len(rows)} {time.time() - started_all:.0f}s", flush=True)
            gc.collect()
    print("done", len(rows), f"{time.time() - started_all:.0f}s", counts, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
