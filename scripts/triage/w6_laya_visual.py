#!/usr/bin/env python3
"""W6 visual-QA judge: laya vision (``predict(image=...)``) over the sweep
renders, gated exactly like the fit script (``route == "auto"`` +
``probabilities``, never raw ``confidence``).

Per mesh the judge sees the three orthographic views (front/top/side) as
separate calls and the aggregate verdict is the worst (most-defective)
gated class across views. Questions: ``render_class`` (choice) and
``debris_score`` (score 1-5). Controls anchor the reading: clean-pass
meshes should come back ``solid_ok``; display rows ``wireframe_only``.

Run AFTER the fit process exits (one laya model resident at a time).

Usage:
  USE_TF=0 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 python -B \\
      scripts/triage/w6_laya_visual.py --manifest <visual/manifest.jsonl> \\
      [--out-dir ~/.local/state/catpart-parser/w6-laya/visual]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

DEFECT_RANK = {  # worst-case aggregation across views
    "blank": 0,
    "wireframe_only": 1,
    "solid_ok": 1,
    "missing_faces": 2,
    "debris_spaghetti": 3,
}

QUESTIONS = {
    "render_class": {
        "type": "choice",
        "instructions": (
            "This is one orthographic view of a mesh decoded from a CATPart "
            "by a reverse-engineered parser. Judge what the render shows."
        ),
        "criteria": {
            "solid_ok": "a coherent solid part, clean silhouette, no junk",
            "debris_spaghetti": (
                "visible junk: splinters, slivers, thin stray triangles or "
                " tangled debris that is not part of any real surface"
            ),
            "missing_faces": (
                "a recognizable solid with clearly missing/holes faces "
                "(open gaps where a closed surface should be)"
            ),
            "wireframe_only": "only points/line segments, no filled surface",
            "blank": "nothing rendered",
        },
    },
    "debris_score": {
        "type": "score",
        "instructions": (
            "Amount of visible debris/junk geometry in this view: "
            "1 none, 2 a few stray slivers, 3 noticeable clutter, "
            "4 heavy debris, 5 dominated by junk."
        ),
    },
}


def judge_mesh(agent, rec: dict, png_dir: Path) -> dict:
    state = (
        f"Mesh decoded from {rec['path']} ({rec['source']}). Parser outcome: "
        f"{rec['fail_family']}, {rec.get('ply_triangles') or 0} triangles, "
        f"warnings: {', '.join(rec['warnings']) or 'none'}. Judge the rendered view."
    )
    per_view = {}
    for view in rec.get("views") or []:
        png = png_dir / f"{rec['stem']}-{view}.png"
        if not png.exists():
            continue
        pred = agent.predict(state, QUESTIONS, image=str(png))
        ans = (pred or {}).get("answers", {})
        rc = ans.get("render_class") or {}
        ds = ans.get("debris_score") or {}
        per_view[view] = {
            "route": rc.get("route"),
            "choice": rc.get("choice"),
            "probabilities": rc.get("probabilities"),
            "debris_score": ds.get("choice"),
            "debris_route": ds.get("route"),
            "abstain": rc.get("abstain"),
        }
    gated = [v for v in per_view.values() if v["route"] == "auto" and v["probabilities"]]
    if gated:
        worst = max(gated, key=lambda v: DEFECT_RANK.get(v["choice"], 99))
        agg = {"verdict": worst["choice"], "gated": True, "worst_view": worst}
    else:
        agg = {"verdict": None, "gated": False}
    agg["debris_max"] = max(
        (v["debris_score"] for v in gated if isinstance(v["debris_score"], (int, float))),
        default=None,
    )
    return {"per_view": per_view, **agg}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args()
    out_dir = args.out_dir or args.manifest.parent
    png_dir = args.manifest.parent / "png"

    import laya

    agent = laya.VegaAgent(device="cpu")
    recs = [json.loads(l) for l in args.manifest.read_text().splitlines() if l.strip()]
    to_judge = [r for r in recs if r.get("views")]
    print(f"judging {len(to_judge)} meshes of {len(recs)}", flush=True)

    verdicts_path = out_dir / "visual-verdicts.jsonl"
    tally: Counter = Counter()
    by_batch: dict[str, Counter] = {}
    with open(verdicts_path, "w", encoding="utf-8") as vout:
        for i, r in enumerate(to_judge, 1):
            res = judge_mesh(agent, r, png_dir)
            row = {"stem": r["stem"], "batch": r["batch"], "source": r["source"],
                   "path": r["path"], "fail_family": r["fail_family"],
                   "l2_status": r["l2_status"], "ply_triangles": r.get("ply_triangles"),
                   **res}
            vout.write(json.dumps(row, ensure_ascii=False) + "\n")
            tally[res["verdict"] or "gated-out"] += 1
            b = by_batch.setdefault(r["batch"], Counter())
            b[res["verdict"] or "gated-out"] += 1
            print(f"  [{i}/{len(to_judge)}] {r['stem']} -> {res['verdict']} "
                  f"(debris_max={res.get('debris_max')})", flush=True)

    print("\nverdict tally:", dict(tally), flush=True)
    for b, c in sorted(by_batch.items()):
        print(f"  {b}: {dict(c)}", flush=True)
    (out_dir / "visual-summary.json").write_text(
        json.dumps({"tally": dict(tally), "by_batch": {b: dict(c) for b, c in by_batch.items()}}, indent=1)
    )
    print(f"verdicts -> {verdicts_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
