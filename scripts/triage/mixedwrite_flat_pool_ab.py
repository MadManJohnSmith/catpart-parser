#!/usr/bin/env python3
"""Full-corpus A/B harness for the mixedwrite flat-law per-rep pool test.

Runs the shipped export seam over every manifest part (dev + held-out)
and writes one row per part: export status, L2 gate result, mesh
invariants, counts and the composite stage.  Two runs (baseline and
after) are compared row-for-row by ``--compare``; the B2 reconciliation
(2026-11-21) changes nothing outside the twin family.

Read-only; deterministic; the corpus is never written.

  .venv/bin/python -I scripts/triage/mixedwrite_flat_pool_ab.py \
      --root <repo> --out /tmp/after.csv
  .venv/bin/python -I scripts/triage/mixedwrite_flat_pool_ab.py \
      --root <baseline-repo> --out /tmp/before.csv
  .venv/bin/python -I scripts/triage/mixedwrite_flat_pool_ab.py \
      --compare /tmp/before.csv /tmp/after.csv
"""
import argparse
import csv
import mmap
import sys
from pathlib import Path

FIELDS = [
    "sha256", "split", "path", "status", "error_class", "failed_check",
    "vertex_count", "triangle_count", "degenerate_triangle_count",
    "manifold", "closed", "oriented", "boundary_edge_count",
    "stage", "warnings",
]


def run(root: Path, out_path: Path) -> None:
    src = root / "src"
    sys.path.insert(0, str(src))
    from catpart.geometry import export  # noqa: E402
    from catpart.geometry.errors import ExportError  # noqa: E402
    from catpart.fitness import runner  # noqa: E402

    rows = []
    manifest = root / "manifests" / "corpus-manifest.csv"
    with open(manifest, newline="") as fh:
        parts = [r for r in csv.DictReader(fh) if r["kind"] == "part"]
    for r in parts:
        p = root / r["local_path"]
        row = {
            "sha256": r["sha256"], "split": r["split"], "path": r["path"],
            "status": "", "error_class": "", "failed_check": "",
            "vertex_count": "", "triangle_count": "",
            "degenerate_triangle_count": "", "manifold": "",
            "closed": "", "oriented": "", "boundary_edge_count": "",
            "stage": "", "warnings": "",
        }
        try:
            with open(p, "rb") as fh:
                mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
                try:
                    summary, _vertices, _triangles = export._export_data(mm)
                finally:
                    mm.close()
        except ExportError as exc:
            row["status"] = "fail"
            row["error_class"] = exc.error_class
            rows.append(row)
            continue
        except Exception as exc:  # noqa: BLE001 - classification boundary
            row["status"] = "crash"
            row["error_class"] = f"{type(exc).__name__}: {exc}"
            rows.append(row)
            continue
        score = runner._score_export(summary)
        row["status"] = "pass" if score["status"] == runner.L2_PASS else "fail"
        row["failed_check"] = score["failed_check"] or ""
        row["vertex_count"] = score["vertex_count"]
        row["triangle_count"] = score["triangle_count"]
        row["degenerate_triangle_count"] = score["degenerate_triangle_count"]
        row["manifold"] = score["mesh"]["manifold"]
        row["closed"] = score["mesh"]["closed"]
        row["oriented"] = score["mesh"]["oriented"]
        row["boundary_edge_count"] = score["mesh"]["boundary_edge_count"]
        comp = summary.get("composite") or {}
        row["stage"] = comp.get("stage", "clean")
        row["warnings"] = ";".join(w["class"] for w in summary["warnings"])
        rows.append(row)
    with open(out_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    passed = sum(1 for r in rows if r["status"] == "pass")
    print(f"{len(rows)} parts, {passed} pass -> {out_path}")


def compare(before_path: Path, after_path: Path) -> int:
    def load(p):
        with open(p, newline="") as fh:
            return {r["sha256"]: r for r in csv.DictReader(fh)}

    before, after = load(before_path), load(after_path)
    if set(before) != set(after):
        print("row-set mismatch", len(before), len(after))
        return 2
    pass_to_fail = []
    manifold_reg = []
    changed = []
    new_pass = []
    for sha, b in before.items():
        a = after[sha]
        if b["status"] == "pass" and a["status"] == "fail":
            pass_to_fail.append((sha, b["failed_check"], a["failed_check"]))
        if b["manifold"] == "True" and a["manifold"] != "True":
            manifold_reg.append((sha, a["manifold"]))
        if b["status"] != a["status"]:
            changed.append((sha, b["status"], a["status"], b["error_class"], a["error_class"]))
            if a["status"] == "pass":
                new_pass.append(sha)
        elif (b["vertex_count"], b["triangle_count"]) != (
            a["vertex_count"], a["triangle_count"]
        ):
            changed.append((sha, "geometry", "geometry", b["stage"], a["stage"]))
    print(f"pass->fail: {len(pass_to_fail)}")
    for row in pass_to_fail:
        print("  ", row)
    print(f"manifold regressions: {len(manifold_reg)}")
    for row in manifold_reg:
        print("  ", row)
    print(f"changed rows: {len(changed)}")
    for row in changed:
        print("  ", row)
    print(f"new passes: {len(new_pass)} {new_pass}")
    return 0 if not pass_to_fail and not manifold_reg else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--compare", nargs=2, type=Path)
    args = ap.parse_args()
    if args.compare:
        return compare(args.compare[0], args.compare[1])
    if not args.root or not args.out:
        ap.error("--root and --out are required")
    run(args.root.resolve(), args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
