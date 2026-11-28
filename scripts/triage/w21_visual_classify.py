#!/usr/bin/env python3
"""W21 visual QA — verdict materialization + contact sheets (Bloque D14).

Input: the render harness JSONL + a hand-inspection verdicts JSONL
(one line per rendered part: batch/path/sha256 + verdict/view/note).
The visual criterion is declared in
docs/evidence/2026-11-22-w21-visual-qa.md and enforced here:

  ok | spaghetti | hole | inverted | collapsed | puntos | blank | dudosa

Outputs (all committed):
- docs/evidence/data/w21-visual-qa-verdicts.jsonl — render rec + verdict
- docs/evidence/data/w21-visual-qa-claims.csv — per batch/family/verdict
  counts (the CSV-composable rate table)
- docs/evidence/data/w21-visual-qa/sheet-<batch>.png — contact sheets
- docs/evidence/data/w21-visual-qa/<stem>.<view>.png — defect/dudosa
  close-ups copied from the session-state renders

Usage:
  python -B scripts/triage/w21_visual_classify.py \
      --render <render jsonl> --verdicts <verdict jsonl> \
      --png-root ~/.local/state/catpart-parser/w21-visual
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EVID = REPO / "docs/evidence/data"
VERDICTS = (
    "ok",
    "spaghetti",
    "hole",
    "inverted",
    "collapsed",
    "puntos",
    "blank",
    "dudosa",
)


def contact_sheet(png_root: Path, batch: str, recs: list, out_png: Path) -> None:
    """One sheet per batch: 4 views per part in reading order, labeled
    with the render filename (index + sha16 + view, via montage %f)."""
    files: list[str] = []
    for _i, r in enumerate(recs):
        for v in r.get("views", []):
            p = png_root / batch / v["png"]
            if p.is_file():
                files.append(str(p))
    if not files:
        return
    subprocess.run(
        [
            "montage",
            *files,
            "-tile",
            "4x",
            "-geometry",
            "300x200+2+2",
            "-label",
            "%f",
            "-background",
            "#111",
            "-fill",
            "#ddd",
            str(out_png),
        ],
        check=True,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", type=Path, required=True)
    ap.add_argument("--verdicts", type=Path, required=True)
    ap.add_argument("--png-root", type=Path, required=True)
    ap.add_argument(
        "--skip-sheets", action="store_true", help="verdicts/CSV only, no montage"
    )
    args = ap.parse_args()

    render = {}
    with open(args.render) as fh:
        for line in fh:
            r = json.loads(line)
            render[(r["batch"], r["path"])] = r
    verdicts = {}
    with open(args.verdicts) as fh:
        for line in fh:
            v = json.loads(line)
            key = (v["batch"], v["path"])
            if key in verdicts:
                raise SystemExit(f"duplicate verdict: {key}")
            verdicts[key] = v

    missing = sorted(set(render) - set(verdicts))
    extra = sorted(set(verdicts) - set(render))
    if missing:
        print(f"MISSING verdicts for {len(missing)}: {missing[:3]}", file=sys.stderr)
    if extra:
        print(f"EXTRA verdicts for {len(extra)}: {extra[:3]}", file=sys.stderr)
    if missing or extra:
        raise SystemExit(1)

    out_dir = EVID / "w21-visual-qa"
    out_dir.mkdir(parents=True, exist_ok=True)

    counts: Counter = Counter()
    by_batch: dict[str, list] = defaultdict(list)
    n_defects = 0
    with open(EVID / "w21-visual-qa-verdicts.jsonl", "w") as out:
        for key, v in sorted(verdicts.items()):
            r = render[key]
            verdict = v["verdict"]
            if verdict not in VERDICTS:
                raise SystemExit(f"bad verdict {verdict!r} for {key}")
            merged = {
                "batch": r["batch"],
                "path": r["path"],
                "sha256": r.get("sha256", ""),
                "family": r.get("family", ""),
                "bytes": r.get("bytes", 0),
                "expected_triangles": r.get("expected_triangles", 0),
                "status": r.get("status"),
                "gate_failed_check": r.get("gate_failed_check"),
                "triangles": r.get("triangles"),
                "vertices": r.get("vertices"),
                "display_mode": r.get("display_mode"),
                "verdict": verdict,
                "view": v.get("view", ""),
                "note": v.get("note", ""),
                "views": r.get("views", []),
            }
            out.write(json.dumps(merged, sort_keys=True) + "\n")
            counts[(r["batch"], r.get("family", ""), verdict)] += 1
            by_batch[r["batch"]].append(r)
            if verdict in ("spaghetti", "hole", "inverted", "collapsed"):
                n_defects += 1
                for view in merged["views"]:
                    src = args.png_root / r["batch"] / view["png"]
                    if src.is_file():
                        shutil.copy2(src, out_dir / view["png"])
            elif verdict == "dudosa":
                for view in merged["views"]:
                    if view["view"] == v.get("view", ""):
                        src = args.png_root / r["batch"] / view["png"]
                        if src.is_file():
                            shutil.copy2(src, out_dir / view["png"])

    if not args.skip_sheets:
        for batch, recs in sorted(by_batch.items()):
            contact_sheet(args.png_root, batch, recs, out_dir / f"sheet-{batch}.png")

    with open(EVID / "w21-visual-qa-claims.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["batch", "family", "verdict", "count"])
        for (batch, family, verdict), n in sorted(counts.items()):
            w.writerow([batch, family, verdict, n])
        totals = Counter()
        for (batch, family, verdict), n in counts.items():
            totals[verdict] += n
        for verdict in VERDICTS:
            w.writerow(["ALL", "", verdict, totals[verdict]])

    print(
        f"verdicts: {sum(counts.values())} parts; defects {n_defects}; dudosa {totals['dudosa']}"
    )
    for verdict in VERDICTS:
        if totals[verdict]:
            print(f"  {verdict}: {totals[verdict]}")


if __name__ == "__main__":
    main()
