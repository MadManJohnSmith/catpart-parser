#!/usr/bin/env python3
"""L2 fast pass: the export seam + the runner's sanity gate, per part.

The marathon's fitness-fast measurement (W15, 2026-11-22): the committed
L2 protocol (:mod:`catpart.fitness.runner`) minus the L1 slice and the
history append — every manifest ``kind=part`` row is exported through
:func:`catpart.geometry.build_export` in-process, scored with the
runner's own :func:`_score_export` gate, and the per-part verdicts land
in ``docs/evidence/data/e5-member-filter-l2.csv``.

With ``--baseline-src`` the same pass runs from another source tree (the
baseline branch's ``src``) in ONE subprocess (its own import, its own
CSV in a temp dir) and the committed CSV carries both verdicts, so the
pass->fail set is measured, not asserted.  Read-only over the corpus;
nothing is appended to ``fitness/history.jsonl``.

Reproduce (the member-filter law A/B)::

    .venv/bin/python -B -I scripts/triage/l2_fast_pass.py \
        --baseline-src /home/alan/catpart-parser/src
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_ROWS = ROOT / "docs" / "evidence" / "data" / "e5-member-filter-l2.csv"

FIELDS = [
    "sha256", "split", "baseline_status", "baseline_failed_check",
    "baseline_triangles", "baseline_degenerate", "branch_status",
    "branch_failed_check", "branch_triangles", "branch_degenerate",
    "changed", "regression",
]

#: The whole-pass runner body; the baseline subprocess executes this with
#: its own source tree first on ``sys.path`` (one import for the corpus).
PASS_RUNNER = r"""
import json, sys, gc
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from catpart.geometry import build_export
from catpart.fitness.runner import _score_export

root = Path(sys.argv[2])
out_path = Path(sys.argv[3])
rows = []
import csv as _csv
manifest = list(_csv.DictReader(open(root / "manifests" / "corpus-manifest.csv", newline="")))
tmp = out_path.parent
for index, row in enumerate(manifest):
    if row["kind"] != "part":
        continue
    path = root / row["local_path"]
    if not path.is_file():
        continue
    try:
        summary = build_export(path, tmp / "out.ply")
    except Exception as exc:
        record = {"sha256": row["sha256"], "split": row.get("split", ""),
                  "status": "fail", "failed_check": None,
                  "error": type(exc).__name__, "triangles": None,
                  "degenerate": None}
    else:
        scored = _score_export(summary)
        record = {"sha256": row["sha256"], "split": row.get("split", ""),
                  "status": scored["status"],
                  "failed_check": scored["failed_check"],
                  "error": None, "triangles": scored["triangle_count"],
                  "degenerate": scored["degenerate_triangle_count"]}
    rows.append(record)
    if index % 200 == 0:
        print(f"{index}", file=sys.stderr, flush=True)
    gc.collect()
json.dump(rows, open(out_path, "w"))
"""


def manifest_parts() -> list[tuple[str, str, str]]:
    out = []
    for row in csv.DictReader(MANIFEST.open(newline="")):
        if row["kind"] != "part":
            continue
        path = ROOT / row["local_path"]
        if not path.is_file():
            continue
        out.append((row["sha256"], row["local_path"], row.get("split", "")))
    return out


def run_pass(src: Path, workdir: Path, out_name: str, progress: bool) -> list[dict]:
    """One whole-corpus pass from ``src``; ``[{sha, status, ...}]``."""
    runner = workdir / "pass_runner.py"
    runner.write_text(PASS_RUNNER)
    result = subprocess.run(
        [sys.executable, "-B", "-I", str(runner), str(src), str(ROOT),
         str(workdir / out_name)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pass from {src} failed: {result.stderr[-2000:]}")
    if progress and result.stderr:
        print(result.stderr.strip().splitlines()[-1], flush=True)
    return json.load(open(workdir / out_name))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-src", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=OUT_ROWS)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT / "src"))
    from catpart.geometry import build_export
    from catpart.fitness.runner import _score_export

    parts = manifest_parts()
    if args.limit:
        wanted = {sha for sha, _rel, _split in parts[: args.limit]}
    else:
        wanted = None

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        baseline_rows = None
        if args.baseline_src:
            print("baseline pass (subprocess)...", flush=True)
            baseline_rows = {
                row["sha256"]: row
                for row in run_pass(args.baseline_src, tmp, "baseline.json", True)
            }
        branch_rows = []
        for index, (sha, rel, split) in enumerate(parts):
            if wanted is not None and sha not in wanted:
                continue
            path = ROOT / rel
            try:
                summary = build_export(path, tmp / "branch.ply")
            except Exception as exc:  # noqa: BLE001 - classification boundary
                record = {
                    "sha256": sha, "split": split, "status": "fail",
                    "failed_check": None, "error": type(exc).__name__,
                    "triangles": None, "degenerate": None,
                }
            else:
                scored = _score_export(summary)
                record = {
                    "sha256": sha, "split": split,
                    "status": scored["status"],
                    "failed_check": scored["failed_check"],
                    "error": None, "triangles": scored["triangle_count"],
                    "degenerate": scored["degenerate_triangle_count"],
                }
            branch_rows.append(record)
            if index % 200 == 0:
                print(f"{index}/{len(parts)}", flush=True)
            gc.collect()

    counts: dict[str, int] = {}
    regressions = 0
    flips = 0
    with args.out.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(FIELDS)
        for record in branch_rows:
            base = (baseline_rows or {}).get(record["sha256"])
            if base:
                key = f"{base['status']}->{record['status']}"
                counts[key] = counts.get(key, 0) + 1
                regression = base["status"] == "pass" and record["status"] != "pass"
                flips += base["status"] == "fail" and record["status"] == "pass"
                regressions += regression
                base_cells = [
                    base["status"], base["failed_check"] or "",
                    base["triangles"] if base["triangles"] is not None else "",
                    base["degenerate"] if base["degenerate"] is not None else "",
                ]
            else:
                base_cells = ["", "", "", ""]
            writer.writerow([
                record["sha256"][:16], record["split"], *base_cells,
                record["status"], record["failed_check"] or "",
                record["triangles"] if record["triangles"] is not None else "",
                record["degenerate"] if record["degenerate"] is not None else "",
                int(bool(base)), int(regression) if base else "",
            ])
    print("transition census:", json.dumps(counts, sort_keys=True))
    print(f"fail->pass flips: {flips}   pass->fail regressions: {regressions}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
