#!/usr/bin/env python3
"""W12 inverse spatial oracle — geometry side (read-only, 2026-11-22).

Localizes WHERE the fidelity harness's area_ratio gap lives, for the
three external pairs with area_ratio far from 1: audi-r8 (0.8775),
ducati-panigale-1199/Motor (0.828), dodge-challenger (177.3). Zero
``src/`` changes: the export is the shipped seam
(:func:`catpart.geometry.build_export`), and every reader/grid/area
primitive is the committed W7 harness module loaded by path — the same
semantics the merge reports cite, never a fork.

Three signals, per pair. The first two bound the problem; the third is
the oracle. The measured regime (audi raw hausdorff_max 0.0007 mm over
the vertex sets, Motor 0.0735 mm centered) says every reference vertex
already sits ON our vertex set, so the area gap is NOT far geometry —
it is missing CONNECTIVITY between shared vertices, and a vertex-
distance threshold is provably blind to it (audi: zero far triangles
at 1 mm; a centroid+midpoint interior sampling was tried first and
measured vertex density, not coverage — every interior is > 1 mm from
the nearest VERTEX on meshes this coarse, which is why the oracle
below matches triangles, not points):

- ``far_ref_to_ours`` — the brief's step 1: exact per-vertex ref→ours
  distance (harness VertexGrid); triangles whose max vertex distance
  exceeds the threshold cluster by 26-adjacency. Localization for far
  geometry (Dodge's displaced bodies); empty for audi/ducati (a named,
  reproducible outcome).
- ``missing_triangles`` — the oracle for the coincident-vertex family:
  reference triangles absent from our triangle set under winding-
  independent coordinate-identity match (vertex coordinates rounded to
  the 1 µm grid, sorted triple). Under the measured vertex-coincidence
  regime the unmatched reference triangles ARE the missing faces (the
  declined loops' triangles), bucketed per centroid cell and clustered.
  The identity match CONSERVES area, which makes the claim exact and
  checkable: matched + missing = ref_area, and missing − extra must
  reproduce the harness's area gap. A conservation breach is reported,
  never silently absorbed (it would mean the regime assumption failed
  — e.g. real tessellation-density differences — and the note must say
  so).
- ``extra_triangles`` — the same identity match in reverse: OUR
  triangles absent from the reference set, localizing our extra area
  (Dodge's 177x: displaced/duplicated sheets).

All signals reduce to per-cell aggregates before clustering, so memory
is bounded by occupied cells, not triangles (the anti-OOM constraint;
a cell-budget breach is a named ``cell-budget-exceeded`` abort, never
a silent trim).

Run (reproduction commands live in the W12 evidence note)::

    python -B scripts/triage/w12_inverse_oracle.py \
        --pair audi-r8 --pairs-json ~/.local/state/catpart-parser/bench-external/pairs.json \
        --csv docs/evidence/data/w12-missing-faces-audi-r8.csv

Read-only over the data; the PLY the seam writes goes to a temp dir.
"""

from __future__ import annotations

import argparse
import array
import csv
import json
import math
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from catpart.geometry import build_export  # noqa: E402 - path setup first
from catpart.geometry.errors import ExportError  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from w12_oracle_lib import (  # noqa: E402 - sibling triage module
    CellBudgetExceeded,
    add_triangle,
    bbox_diagonal,
    cluster_cells,
    identity_missing_cells,
    load_harness,
    net_missing_clusters,
    summarize_cluster,
    triangle_key_set,
)

#: The audi pair's reference bbox diagonal (mm) — the threshold's scale
#: anchor: the auto threshold is "1.0 mm at audi scale", scaled by the
#: pair's own diagonal (the brief's "Dodge: umbral escalado").
AUDI_DIAG_MM = 4905.116880528735


def far_vertex_cells(mesh, grid, threshold, cell, signal, max_ring=0):
    """Triangles whose max VERTEX distance exceeds ``threshold``,
    bucketed per cell (bbox/area/count aggregates only).

    ``max_ring`` (0 = uncapped, the harness's exact behavior) bounds the
    ring-outward search for meshes with FAR displaced geometry (Dodge's
    10x bbox): a query still unresolved at that ring reports ``>=
    max_ring * cell`` (exact below the cap, a named floor above it —
    the cap count rides the report as ``far_at_cap``)."""
    vertices = mesh.vertices
    n = mesh.vertex_count
    cap_dist = max_ring * cell if max_ring else math.inf
    dists = array.array("d", bytes(8 * n))
    far_vertex_count = 0
    far_at_cap = 0
    for i in range(n):
        j = i * 3
        if max_ring:
            d = _capped_nearest(grid, (vertices[j], vertices[j + 1], vertices[j + 2]), max_ring, cap_dist)
        else:
            d = grid.nearest((vertices[j], vertices[j + 1], vertices[j + 2]))
        dists[i] = d
        if d > threshold:
            far_vertex_count += 1
            if max_ring and d >= cap_dist:
                far_at_cap += 1
    cells: dict = {}
    t = mesh.triangles
    far_tris = 0
    for i in range(0, len(t), 3):
        a, b, c = t[i], t[i + 1], t[i + 2]
        if not (dists[a] > threshold or dists[b] > threshold or dists[c] > threshold):
            continue
        far_tris += 1
        ja, jb, jc = a * 3, b * 3, c * 3
        try:
            add_triangle(
                cells,
                cell,
                vertices[ja], vertices[ja + 1], vertices[ja + 2],
                vertices[jb], vertices[jb + 1], vertices[jb + 2],
                vertices[jc], vertices[jc + 1], vertices[jc + 2],
            )
        except CellBudgetExceeded as exc:
            raise CellBudgetExceeded(f"{signal}: {exc}") from exc
    return cells, far_tris, far_vertex_count, n, far_at_cap


def _capped_nearest(grid, q, max_ring, cap_dist):
    """The harness's exact ring-outward nearest, bounded at ``max_ring``."""
    cell = grid.cell
    cx, cy, cz = (int(q[0] // cell), int(q[1] // cell), int(q[2] // cell))
    best = math.inf
    for ring in range(max_ring + 1):
        for ix in range(cx - ring, cx + ring + 1):
            for iy in range(cy - ring, cy + ring + 1):
                for iz in range(cz - ring, cz + ring + 1):
                    bucket = grid.cells.get((ix, iy, iz))
                    if not bucket:
                        continue
                    vertices = grid.mesh.vertices
                    for i in bucket:
                        j = i * 3
                        dx = vertices[j] - q[0]
                        dy = vertices[j + 1] - q[1]
                        dz = vertices[j + 2] - q[2]
                        d = dx * dx + dy * dy + dz * dz
                        if d < best:
                            best = d
        best_dist = math.sqrt(best)
        if best_dist <= ring * cell:
            return best_dist
    return cap_dist


def top_clusters(clusters, top):
    return sorted(clusters, key=lambda c: -c["area"])[:top]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="w12_inverse_oracle",
        description="W12 inverse spatial oracle: localize missing/extra mesh area per pair (three signals, cell-bounded).",
    )
    ap.add_argument("--pair", help="pair name inside --pairs-json (or explicit paths below)")
    ap.add_argument("--pairs-json", type=Path, default=None)
    ap.add_argument("--catpart", type=Path, default=None)
    ap.add_argument("--reference", type=Path, default=None)
    ap.add_argument("--threshold-mm", type=float, default=None,
                    help="sample-far threshold; default = diag/4905.116 (1.0 mm at audi scale)")
    ap.add_argument("--cell-mm", type=float, default=None,
                    help="cluster cell; default = diag/256")
    ap.add_argument("--skip-reverse", action="store_true",
                    help="skip all ours-side signals (the expensive direction on 2.5M-tri meshes)")
    ap.add_argument("--skip-far-reverse", action="store_true",
                    help="skip only far_ours_to_ref (ring-outward explodes on far displaced geometry); extra_triangles still runs")
    ap.add_argument("--max-ring", type=int, default=0,
                    help="cap the far signals' ring-outward search (0 = uncapped/exact; far-at-cap rides the report)")
    ap.add_argument("--csv", type=Path, required=True)
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args(argv)

    if args.pair and args.pairs_json:
        pair = next(p for p in json.loads(args.pairs_json.read_text()) if p["name"] == args.pair)
        catpart_path, reference_path = Path(pair["catpart"]), Path(pair["ref"])
        pair_name = pair["name"]
    elif args.catpart and args.reference:
        catpart_path, reference_path = args.catpart, args.reference
        pair_name = catpart_path.stem
    else:
        ap.error("need --pair + --pairs-json, or --catpart + --reference")

    harness = load_harness()
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="w12-oracle-ply-") as scratch:
        ply_path = Path(scratch) / "catpart.ply"
        try:
            summary = build_export(catpart_path, ply_path)
        except ExportError as exc:
            print(json.dumps({"outcome": "export-failure", "error_class": exc.error_class,
                              "detail": exc.detail, "pair": pair_name}, indent=2))
            return 2
        ours = harness._read_binary_le_ply(ply_path)
    ref = harness.read_reference_mesh(reference_path)
    if ours.vertex_count == 0 or ref.vertex_count == 0:
        print(json.dumps({"outcome": "empty-mesh", "pair": pair_name,
                          "side": "catpart" if ours.vertex_count == 0 else "reference"}, indent=2))
        return 2

    diag = bbox_diagonal(ref)
    threshold = args.threshold_mm if args.threshold_mm is not None else diag / AUDI_DIAG_MM
    cell = args.cell_mm if args.cell_mm is not None else diag / 256

    rows = []
    report = {
        "pair": pair_name,
        "outcome": "metrics",
        "catpart": str(catpart_path),
        "reference": str(reference_path),
        "diag_mm": round(diag, 3),
        "threshold_mm": round(threshold, 4),
        "cell_mm": round(cell, 4),
        "ours_tris": ours.triangle_count,
        "ref_tris": ref.triangle_count,
        "area_ours": harness.total_area(ours),
        "area_ref": harness.total_area(ref),
    }
    report["area_ratio"] = report["area_ours"] / report["area_ref"]

    # Signal 1: far ref→ours vertices (the brief's step 1).
    t0 = time.monotonic()
    grid_ours = harness.VertexGrid(ours, cell)
    far_cells, far_tris, far_verts, n_ref_verts, ref_at_cap = far_vertex_cells(
        ref, grid_ours, threshold, cell, "far_ref_to_ours", args.max_ring
    )
    far_clusters = []
    for member_keys in cluster_cells(far_cells):
        c = summarize_cluster(member_keys, far_cells)
        c["n_cells"] = len(member_keys)
        far_clusters.append(c)
    report["far_ref_to_ours"] = {
        "far_tris": far_tris,
        "far_verts": far_verts,
        "far_at_cap": ref_at_cap,
        "ref_verts": n_ref_verts,
        "clusters": len(far_clusters),
        "area_top": round(max((c["area"] for c in far_clusters), default=0.0), 2),
        "seconds": round(time.monotonic() - t0, 1),
    }
    for rank, c in enumerate(top_clusters(far_clusters, args.top), 1):
        rows.append(("far_ref_to_ours", rank, c))

    # Signal 2: the identity-match oracle. Both directions bucket per
    # cell on the SAME grid; the per-cell NET (missing − extra) is the
    # clustered signal, because retriangulated regions (different
    # diagonal splits over the same vertices) cancel cell by cell.
    t0 = time.monotonic()
    ours_keys = triangle_key_set(ours)
    miss_cells, miss_tris, miss_area, miss_matched_area, miss_matched = (
        identity_missing_cells(ref, ours_keys, cell)
    )
    del ours_keys
    report["missing_triangles"] = {
        "missing_tris": miss_tris,
        "missing_area_mm2": round(miss_area, 2),
        "matched_tris": miss_matched,
        "matched_area_mm2": round(miss_matched_area, 2),
        "conservation": round(miss_matched_area + miss_area - report["area_ref"], 4),
        "seconds": round(time.monotonic() - t0, 1),
    }

    # Signals 1b/2b: the reverse direction (our extra geometry).
    if not args.skip_reverse:
        if not args.skip_far_reverse:
            t0 = time.monotonic()
            grid_ref = harness.VertexGrid(ref, cell)
            rev_cells, rev_tris, rev_verts, n_ours_verts, ours_at_cap = far_vertex_cells(
                ours, grid_ref, threshold, cell, "far_ours_to_ref", args.max_ring
            )
            rev_clusters = []
            for member_keys in cluster_cells(rev_cells):
                c = summarize_cluster(member_keys, rev_cells)
                c["n_cells"] = len(member_keys)
                rev_clusters.append(c)
            report["far_ours_to_ref"] = {
                "far_tris": rev_tris,
                "far_verts": rev_verts,
                "far_at_cap": ours_at_cap,
                "ours_verts": n_ours_verts,
                "clusters": len(rev_clusters),
                "area_top": round(max((c["area"] for c in rev_clusters), default=0.0), 2),
                "seconds": round(time.monotonic() - t0, 1),
            }
            for rank, c in enumerate(top_clusters(rev_clusters, args.top), 1):
                rows.append(("far_ours_to_ref", rank, c))

        t0 = time.monotonic()
        ref_keys = triangle_key_set(ref)
        extra_cells, extra_tris, extra_area, extra_matched_area, extra_matched = (
            identity_missing_cells(ours, ref_keys, cell)
        )
        del ref_keys
        report["extra_triangles"] = {
            "extra_tris": extra_tris,
            "extra_area_mm2": round(extra_area, 2),
            "matched_tris": extra_matched,
            "matched_area_mm2": round(extra_matched_area, 2),
            "conservation": round(extra_matched_area + extra_area - report["area_ours"], 4),
            "seconds": round(time.monotonic() - t0, 1),
        }
        # The net signal: positive-net clusters (retriangulation cancels).
        t0 = time.monotonic()
        net_clusters, net_total = net_missing_clusters(miss_cells, extra_cells)
        report["net_missing"] = {
            "net_area_mm2": round(net_total, 2),
            "clusters": len(net_clusters),
            "seconds": round(time.monotonic() - t0, 1),
        }
        for rank, c in enumerate(top_clusters(net_clusters, args.top), 1):
            rows.append(("net_missing", rank, c))

    report["export_warnings"] = [w.get("class") for w in summary.get("warnings", [])]
    if not args.skip_reverse:
        # The conservation gate, in its exact algebraic form:
        #   gap = (matched_ref − matched_ours) + missing − extra
        # so missing − extra − gap must equal matched_ours − matched_ref
        # (the µm-coordinate noise on matched triangles' areas) — any
        # residue beyond that is a named breach: the coincident-vertex
        # regime assumption failed and the note must say so.
        gap = report["area_ref"] - report["area_ours"]
        net = miss_area - extra_area
        expected = extra_matched_area - miss_matched_area
        delta = net - gap - expected
        report["area_gap_check"] = {
            "harness_gap_mm2": round(gap, 2),
            "missing_minus_extra_mm2": round(net, 2),
            "matched_precision_term_mm2": round(expected, 2),
            "residual_mm2": round(delta, 6),
            "ok": abs(delta) <= max(1e-6 * abs(gap), 1e-4),
        }
    report["wall_seconds"] = round(time.monotonic() - started, 1)

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(("pair", "signal", "rank", "n_cells", "n_tris", "n_extra_tris",
                    "net_mm2", "missing_mm2", "extra_mm2",
                    "bbox_min_x", "bbox_min_y", "bbox_min_z",
                    "bbox_max_x", "bbox_max_y", "bbox_max_z"))
        for signal, rank, c in rows:
            w.writerow((pair_name, signal, rank, c["n_cells"], c["n_tris"],
                        c.get("n_extra_tris", ""), round(c["area"], 2),
                        round(c.get("missing_area", 0.0), 2) or "",
                        round(c.get("extra_area", 0.0), 2) or "",
                        *(round(v, 4) for v in c["bbox_min"]),
                        *(round(v, 4) for v in c["bbox_max"])))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
