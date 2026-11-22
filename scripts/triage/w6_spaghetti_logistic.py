#!/usr/bin/env python3
"""W6 spaghetti distillation: a pure-python logistic head trained on the
visual sweep's laya verdicts, over geometric features only — the explicit
weights are the distillation artifact W1 can fold into a deterministic
rule (no laya, no model at parser runtime).

Labels (from ``visual-verdicts.jsonl``, gated ``route == "auto"`` only):
- positive = visible defect: ``debris_spaghetti`` or ``missing_faces``
- negative = clean: ``solid_ok``
- ``wireframe_only`` / ``blank`` / gated-out rows are excluded (they say
  nothing about spaghetti).

Features (geometric, all available at parse time):
log1p triangles, log1p vertices, degenerate ratio (degenerate / max(tris,1)),
boundary-edge presence, warning count, and indicator flags for the
dedup-declined / manifold-kept / open-shell / extended-header-declined
warning classes. ``elem_decl`` (<=255 = the ambiguous band) is joined
from the committed residue census when the file's sha256 is there.

Validation: leave-one-out CV accuracy (n is small) + the fitted weights
with a plain-language threshold rule derived from them.

Usage:
  python -B scripts/triage/w6_spaghetti_logistic.py \\
      --verdicts <visual/visual-verdicts.jsonl> \\
      --features <features.jsonl> [--census docs/evidence/data/residue-family-census.csv]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

FEATURE_NAMES = [
    "log1p_tris",
    "log1p_verts",
    "degen_ratio",
    "has_boundary",
    "warn_count",
    "dup_dedup_declined",
    "manifold_kept",
    "open_shell",
    "ext_header_declined",
]

POSITIVE = {"debris_spaghetti", "missing_faces"}
NEGATIVE = {"solid_ok"}


def featurize(r: dict) -> list[float]:
    tris = r["triangle_count"] or 0
    warns = set(r["warnings"])
    return [
        math.log1p(tris),
        math.log1p(r["vertex_count"] or 0),
        (r["degenerate_triangle_count"] or 0) / max(1, tris),
        1.0 if (r["boundary_edge_count"] or 0) > 0 else 0.0,
        float(len(r["warnings"])),
        1.0 if "duplicate-triangles-dedup-declined" in warns else 0.0,
        1.0 if "primary-loop-manifold-kept" in warns else 0.0,
        1.0 if "open-shell" in warns else 0.0,
        1.0 if "extended-header-geometry-declined" in warns else 0.0,
    ]


def fit_logistic(xs, ys, iters=3000, lr=0.1, l2=0.01):
    n, d = len(xs), len(xs[0])
    w = [0.0] * d
    b = 0.0
    for _ in range(iters):
        gw = [0.0] * d
        gb = 0.0
        for x, y in zip(xs, ys):
            z = b + sum(wi * xi for wi, xi in zip(w, x))
            p = 1 / (1 + math.exp(-z))
            e = p - y
            gb += e
            for i in range(d):
                gw[i] += e * x[i]
        b -= lr * gb / n
        for i in range(d):
            w[i] -= lr * (gw[i] / n + l2 * w[i])
    return w, b


def predict(w, b, x):
    z = b + sum(wi * xi for wi, xi in zip(w, x))
    return 1 / (1 + math.exp(-z))


def loo_accuracy(xs, ys):
    correct = 0
    for i in range(len(xs)):
        xs_tr = xs[:i] + xs[i + 1 :]
        ys_tr = ys[:i] + ys[i + 1 :]
        w, b = fit_logistic(xs_tr, ys_tr)
        p = predict(w, b, xs[i])
        correct += int((p >= 0.5) == (ys[i] == 1))
    return correct / len(xs)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verdicts", type=Path, required=True)
    ap.add_argument("--features", type=Path, required=True)
    ap.add_argument(
        "--census",
        type=Path,
        default=REPO / "docs/evidence/data/residue-family-census.csv",
    )
    args = ap.parse_args()

    feats = {}
    for line in args.features.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            feats[r["path"]] = r

    elem_by_sha = {}
    if args.census.exists():
        import csv

        with open(args.census, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                elem_by_sha[row["sha256"]] = int(row["elem_decl"] or 0)

    rows = []
    for line in args.verdicts.read_text().splitlines():
        if not line.strip():
            continue
        v = json.loads(line)
        if v["verdict"] not in POSITIVE | NEGATIVE:
            continue
        f = feats.get(v["path"])
        if not f:
            continue
        rows.append((v, f))

    xs = [featurize(f) for _, f in rows]
    ys = [1 if v["verdict"] in POSITIVE else 0 for v, _ in rows]
    print(f"training rows: {len(rows)} (pos={sum(ys)}, neg={len(ys) - sum(ys)})")
    if len(rows) < 8 or not sum(ys) or not (len(ys) - sum(ys)):
        print("NEGATIVE RESULT: not enough labeled variety to fit a head "
              "(reopen criterion: rerun after the sweep covers more meshes)")
        return 0

    w, b = fit_logistic(xs, ys)
    acc = sum(int((predict(w, b, x) >= 0.5) == (y == 1)) for x, y in zip(xs, ys)) / len(xs)
    print(f"fit accuracy (in-sample): {acc:.3f}")
    if len(xs) >= 10:
        print(f"leave-one-out CV accuracy: {loo_accuracy(xs, ys):.3f}")

    print("\nweights (distillation artifact):")
    print(f"  intercept {b:+.4f}")
    for name, wi in zip(FEATURE_NAMES, w):
        print(f"  {name:22s} {wi:+.4f}")

    # ambiguous band: elem_decl <= 255 where the census knows the file
    amb = [(v, f) for v, f in rows if elem_by_sha.get(f.get("sha256") or "", 10**9) <= 255]
    if amb:
        ax = [featurize(f) for _, f in amb]
        ay = [1 if v["verdict"] in POSITIVE else 0 for v, _ in amb]
        aacc = sum(int((predict(w, b, x) >= 0.5) == (y == 1)) for x, y in zip(ax, ay)) / len(ax)
        print(f"\nambiguous band (elem_decl<=255): n={len(amb)} sep-accuracy={aacc:.3f}")
    else:
        print("\nambiguous band (elem_decl<=255): no census rows in the sweep "
              "(submarine files carry no sha256 in the census)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
