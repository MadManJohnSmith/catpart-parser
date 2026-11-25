#!/usr/bin/env python3
"""W6 target miner: rank the parser's residual work by ROI from the W6
features JSONL (no model, pure census math over the labeled records).

Ranking key per (fail_family x version_family) cluster: ``archivos x
triángulos`` — the number of affected files times the triangles those
files currently produce (or, for zero-mesh failures, the size-weighted
proxy). Per cluster: files, bytes, triangles, and the suggested
hypothesis for the re-routed worker. The top-10 files of the top
clusters are listed individually (archivo/familia/bytes/triángulos).

Markdown goes to stdout; redirect to
``~/.local/state/catpart-parser/w6-laya/top-targets.md`` and commit the
copy as ``scripts/triage/top-targets.md``.

Usage:
  python -B scripts/triage/w6_top_targets.py --features <features.jsonl>
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

HYPOTHESES = {
    "check:not-manifold": (
        "manifold/sewing law on kept-degenerate + duplicate-triangle "
        "stores; verify the L1.1 crease/edge vote on the top files"
    ),
    "check:empty-mesh": (
        "surface decode for display-only stores: bag-rep count-framed f32 "
        "arrays + 3X record centers already carry points; find the triangle law"
    ),
    "check:degenerate-triangles": (
        "degenerate-triangle emission guard: vertex-pool pairing on the "
        "failing stores"
    ),
    "error:undecoded-variant": (
        "undecoded container/record variant: byte-diff one file against a "
        "passing sibling of the same version family"
    ),
    "error:missing-geometry-store": (
        "container walk misses a geometry store: verify the store-kind law "
        "on the file's container table"
    ),
    "error:no-evaluable-surface": (
        "surface decoded but outside evaluable tolerance: check PLANE_TOL "
        "law on the failing store"
    ),
    "fail-unclassified": (
        "failures with no named reason: run the per-file check harness and "
        "name the family before routing"
    ),
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--features", type=Path, required=True)
    args = ap.parse_args()

    recs = [json.loads(l) for l in args.features.read_text().splitlines() if l.strip()]
    labeled = [r for r in recs if r["l2_status"] in ("pass", "fail")]

    clusters: dict[tuple, list] = defaultdict(list)
    for r in labeled:
        if r["fail_family"] == "pass":
            continue
        clusters[(r["fail_family"], r["version_family"])].append(r)

    def roi(rows: list) -> int:
        tris = sum(r["triangle_count"] or 0 for r in rows)
        if tris:
            return len(rows) * tris
        # zero-mesh failures: size proxy (bytes worth of blocked geometry)
        return len(rows) * sum(r["size_bytes"] or 0 for r in rows) // max(1, len(rows))

    ranked = sorted(clusters.items(), key=lambda kv: roi(kv[1]), reverse=True)

    out = []
    out.append("# W6 top targets — residual ROI ranking (ronda v3)")
    out.append("")
    out.append(
        f"Source: {len(labeled)} labeled parts (official corpus + Submarino), "
        f"baseline d8554e0. Rank = archivos x triangulos of the cluster; "
        f"zero-mesh clusters use bytes as the proxy. Hypotheses are starting "
        f"points, not verdicts."
    )
    out.append("")
    out.append("| # | familia | version | archivos | triángulos | bytes | ROI | hipótesis sugerida |")
    out.append("|---|---------|---------|----------|-----------:|------:|----:|--------------------|")
    for i, ((fam, ver), rows) in enumerate(ranked, 1):
        tris = sum(r["triangle_count"] or 0 for r in rows)
        byts = sum(r["size_bytes"] or 0 for r in rows)
        out.append(
            f"| {i} | {fam} | {ver} | {len(rows)} | {tris} | {byts} | {roi(rows)} | {HYPOTHESES.get(fam, 'investigate')} |"
        )
    out.append("")

    out.append("## Top archivos dentro de los 3 clusters de mayor ROI")
    out.append("")
    for (fam, ver), rows in ranked[:3]:
        rows_sorted = sorted(
            rows, key=lambda r: (r["triangle_count"] or 0) * (r["size_bytes"] or 0), reverse=True
        )
        out.append(f"### {fam} ({ver})")
        out.append("")
        out.append("| archivo | bytes | triángulos | warnings |")
        out.append("|---------|------:|-----------:|----------|")
        for r in rows_sorted[:10]:
            out.append(
                f"| {r['path']} | {r['size_bytes']} | {r['triangle_count']} | {', '.join(r['warnings'][:3]) or '-'} |"
            )
        out.append("")

    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
