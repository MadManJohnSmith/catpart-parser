#!/usr/bin/env python3
"""Export-seam A/B of the identity-law integration (G6 stage 3d, #34).

Runs the shipped export seam (:func:`catpart.geometry.build_export`)
over every dev/held-out part of the manifest and scores the runner's
L2 sanity gate (:func:`catpart.fitness.runner._score_export` — the
single gate authority, no fork) on each summary.  One row per part in
``docs/evidence/data/identity-export-files.csv``.  This is the
stage-3d pre-merge measurement: the fitness run itself stays with the
coordinator (no history row is written here).

Measurements (2026-11-11, #34 stage 3d):

- decode coverage reproduces the stage-3b rates through the seam: big
  464/654 and small 213/285 (the stage-3b audited denominators 650/283
  exclude the 28 audit-error stores this seam's locator reaches);
- exports 110 -> 753 (composite 34 -> 677); L2 gate pass 109 -> 686
  (dev 638/1,381, held-out 48/61 — held-out moves for the first time,
  up); the 76 baseline passes untouched; all 34 stage-2c exports
  preserved;
- the stage-2c sigma-search explosions dissolve (bounded sub-second
  exports; see the note's stage-3d section).

Deterministic: sorted manifest order; no wall-clock value enters the
CSV.  Read-only over the corpus; run with the worktree venv:

  .venv/bin/python -I scripts/triage/ab_identity_export.py
  [--include-sha16 HEX16,...] [--out-dir DIR]
"""

import argparse
import csv
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"

sys.path.insert(0, str(ROOT / "src"))

from catpart.fitness.runner import _score_export  # noqa: E402
from catpart.geometry import ExportError, build_export  # noqa: E402

FIELDS = [
    "sha256", "split", "export_ok", "error_class", "l2_status",
    "failed_check", "vertex_count", "triangle_count", "manifold",
    "closed", "element_decl", "node_points", "curve_entries",
    "loops_curve_entry",
]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--include-sha16", default="")
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    args = ap.parse_args()
    rows_in = [
        r
        for r in csv.DictReader(MANIFEST.open())
        if r["split"] in ("dev", "held-out") and r["kind"] == "part"
    ]
    if args.include_sha16:
        want = {h for h in args.include_sha16.split(",") if h}
        rows_in = [r for r in rows_in if r["sha256"][:16] in want]
    rows_in.sort(key=lambda r: r["sha256"])
    out_rows = []
    with tempfile.TemporaryDirectory(prefix="catpart-ab-l2-") as scratch:
        scratch_dir = Path(scratch)
        for r in rows_in:
            path = ROOT / r["local_path"]
            row = {k: "" for k in FIELDS}
            row["sha256"] = r["sha256"]
            row["split"] = r["split"]
            try:
                summary = build_export(path, scratch_dir / f"{r['sha256'][:16]}.ply")
            except ExportError as exc:
                row["export_ok"] = 0
                row["error_class"] = exc.error_class
                out_rows.append(row)
                continue
            row["export_ok"] = 1
            score = _score_export(summary)
            row["l2_status"] = score["status"]
            row["failed_check"] = score["failed_check"] or ""
            row["vertex_count"] = summary["vertex_count"]
            row["triangle_count"] = summary["triangle_count"]
            row["manifold"] = summary["mesh"]["manifold"]
            row["closed"] = summary["mesh"]["closed"]
            comp = summary.get("composite") or {}
            row["element_decl"] = comp.get("element_decl", "")
            row["node_points"] = comp.get("node_points", "")
            row["curve_entries"] = comp.get("curve_entries", "")
            row["loops_curve_entry"] = comp.get("loops_curve_entry", "")
            out_rows.append(row)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "identity-export-files.csv"
    with out_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out_rows)
    print(f"wrote {out_path} ({len(out_rows)} rows)")
    summarize(out_rows)
    return 0


def summarize(rows):
    """Split-level export and L2-gate rates."""
    for split in ("dev", "held-out"):
        fr = [r for r in rows if r["split"] == split]
        exp = [r for r in fr if str(r["export_ok"]) == "1"]
        passed = [r for r in exp if str(r["l2_status"]) == "pass"]
        comp = [r for r in exp if str(r["element_decl"]) not in ("", "None")]
        classes: dict[str, int] = {}
        for r in fr:
            if r["error_class"]:
                classes[r["error_class"]] = classes.get(r["error_class"], 0) + 1
        print(
            f"== {split}: {len(fr)} parts; exports {len(exp)} "
            f"(composite {len(comp)}); L2 gate pass {len(passed)} "
            f"({len(passed) / len(fr):.4f}); error classes {classes}"
        )


if __name__ == "__main__":
    sys.exit(main())
