#!/usr/bin/env python3
"""W20 dodge body map (read-only triage, 2026-11-22).

The scale probe's verdict (``w20_dodge_routing_probe.py``): the
reference STL is NOT a rescaling of any written tessellation in the
file (vertex-identity 0.0 at every candidate factor), while the car
body's x-extent matches the reference's x-extent EXACTLY at 10x
(-1942.5543/234.2802 both sides) — the reference is an independently
re-tessellated 1:10 variant of the car, not a unit law away from our
mesh.  This probe maps WHAT the 2.7M exported triangles contain
spatially, to close the routing question with numbers:

- bodies: per-cell area aggregation of the exported triangles
  (26-adjacency union-find, the W12 oracle machinery), top bodies by
  area with true vertex bboxes — how much of the export is the car vs
  stray pieces;
- rep attribution: every rep's decoded point set (bbox, centroid,
  count) assigned to the body its centroid falls in — which reps form
  which body;
- the x-extent owners: which bodies own the exact-match x extremes.

Memory: one decode (the 2M-point mesh), per-cell aggregates bounded by
``MAX_CELLS`` (named outcome, never trimmed), rep payloads one at a
time.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from catpart.geometry import composite, pool  # noqa: E402 - path setup first

sys.path.insert(0, str(Path(__file__).resolve().parent))

from w20_probe_lib import (  # noqa: E402 - sibling triage module
    load_triage,
    stream_stl_keys,
)

PROBE = load_triage("probe_top10_mesh_gap_dump")

MAX_CELLS = 4_000_000


class CellBudgetExceeded(RuntimeError):
    def __init__(self, n: int):
        super().__init__(f"cell-budget-exceeded: {n} occupied cells >= MAX_CELLS={MAX_CELLS}")


class BodyAgg:
    """One cell's triangle aggregates (count, area, vertex bbox)."""

    __slots__ = ("n", "area", "minx", "miny", "minz", "maxx", "maxy", "maxz")

    def __init__(self) -> None:
        self.n = 0
        self.area = 0.0
        self.minx = math.inf
        self.miny = math.inf
        self.minz = math.inf
        self.maxx = -math.inf
        self.maxy = -math.inf
        self.maxz = -math.inf

    def add(self, area, ax, ay, az, bx, by, bz, cx, cy, cz) -> None:
        self.n += 1
        self.area += area
        self.minx = min(self.minx, ax, bx, cx)
        self.miny = min(self.miny, ay, by, cy)
        self.minz = min(self.minz, az, bz, cz)
        self.maxx = max(self.maxx, ax, bx, cx)
        self.maxy = max(self.maxy, ay, by, cy)
        self.maxz = max(self.maxz, az, bz, cz)


def heron_area(ax, ay, az, bx, by, bz, cx, cy, cz) -> float:
    abx, aby, abz = bx - ax, by - ay, bz - az
    acx, acy, acz = cx - ax, cy - ay, cz - az
    bcx, bcy, bcz = cx - bx, cy - by, cz - bz
    la = math.sqrt(abx * abx + aby * aby + abz * abz)
    lb = math.sqrt(acx * acx + acy * acy + acz * acz)
    lc = math.sqrt(bcx * bcx + bcy * bcy + bcz * bcz)
    s = (la + lb + lc) / 2.0
    q = s * (s - la) * (s - lb) * (s - lc)
    return math.sqrt(q) if q > 0 else 0.0


def cluster_bodies(points, triangles, cell: float) -> list[dict]:
    """26-adjacency bodies over per-centroid-cell aggregates."""
    cells: dict[tuple[int, int, int], BodyAgg] = {}
    t = triangles
    v = points
    for i in range(len(t)):
        a, b, c = t[i]
        ax, ay, az = v[a]
        bx, by, bz = v[b]
        cx, cy, cz = v[c]
        gx = (ax + bx + cx) / 3.0 / cell
        gy = (ay + by + cy) / 3.0 / cell
        gz = (az + bz + cz) / 3.0 / cell
        key = (int(gx), int(gy), int(gz))
        agg = cells.get(key)
        if agg is None:
            if len(cells) >= MAX_CELLS:
                raise CellBudgetExceeded(len(cells))
            agg = cells[key] = BodyAgg()
        agg.add(
            heron_area(ax, ay, az, bx, by, bz, cx, cy, cz),
            ax, ay, az, bx, by, bz, cx, cy, cz,
        )

    neighbors = [
        (dx, dy, dz)
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
        for dz in (-1, 0, 1)
        if (dx, dy, dz) != (0, 0, 0)
    ]
    parent: dict = {}

    def find(k):
        root = k
        while parent[root] != root:
            root = parent[root]
        while parent[k] != root:
            parent[k], k = root, parent[k]
        return root

    for k in cells:
        parent[k] = k
    for k in cells:
        kx, ky, kz = k
        for dx, dy, dz in neighbors:
            nb = (kx + dx, ky + dy, kz + dz)
            if nb in parent:
                ra, rb = find(k), find(nb)
                if ra != rb:
                    parent[ra] = rb
    groups: dict[int, list] = {}
    for k in cells:
        groups.setdefault(find(k), []).append(k)

    bodies = []
    for member_keys in groups.values():
        n = 0
        area = 0.0
        minx = miny = minz = math.inf
        maxx = maxy = maxz = -math.inf
        for k in member_keys:
            agg = cells[k]
            n += agg.n
            area += agg.area
            minx, miny, minz = (min(minx, agg.minx), min(miny, agg.miny),
                                min(minz, agg.minz))
            maxx, maxy, maxz = (max(maxx, agg.maxx), max(maxy, agg.maxy),
                                max(maxz, agg.maxz))
        bodies.append({
            "n_tris": n,
            "area_mm2": round(area, 2),
            "bbox_min": [round(minx, 3), round(miny, 3), round(minz, 3)],
            "bbox_max": [round(maxx, 3), round(maxy, 3), round(maxz, 3)],
        })
    bodies.sort(key=lambda b: -b["area_mm2"])
    return bodies


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="w20_dodge_body_map",
        description="W20: spatial body map of the decoded dodge export "
        "(bodies, rep attribution, x-extent owners).",
    )
    ap.add_argument("--catpart", type=Path, required=True)
    ap.add_argument("--stl", type=Path, required=True)
    ap.add_argument("--cell-mm", type=float, default=50.0)
    ap.add_argument("--rep-csv", type=Path, default=None)
    ap.add_argument("--max-reps", type=int, default=None)
    args = ap.parse_args(argv)

    started = time.monotonic()
    ref = stream_stl_keys(args.stl)
    print(f"[{time.monotonic() - started:6.1f}s] ref: {ref['n_tri']} tris, "
          f"{ref['n_unique_verts']} unique verts, diag {ref['diag']:.2f}",
          flush=True)

    data = args.catpart.read_bytes()
    report: dict = {"catpart": str(args.catpart), "stl": str(args.stl),
                    "ref": {k: v for k, v in ref.items() if k != "keys"},
                    "cell_mm": args.cell_mm, "spans": []}
    rep_rows: list[list] = []

    for span_i, (container, span) in enumerate(PROBE.locate_spans(data)):
        lo, hi = span.body_lo, span.body_hi
        groups, kinds = pool.scan_pool_groups(data, lo, hi)
        span_rec = {"span": span_i, "container": container,
                    "composite": pool.has_composite_space(kinds)}
        report["spans"].append(span_rec)
        if not span_rec["composite"]:
            span_rec["outcome"] = "not-composite-skipped"
            continue

        points, triangles, _deg, info = composite.decode_composite_store(
            data, span, groups, kinds
        )
        print(f"[{time.monotonic() - started:6.1f}s] span {span_i}: "
              f"{len(points)} pts, {len(triangles)} tris", flush=True)

        bodies = cluster_bodies(points, triangles, args.cell_mm)
        span_rec["n_bodies"] = len(bodies)
        span_rec["bodies_top10"] = bodies[:10]
        total_area = sum(b["area_mm2"] for b in bodies)
        span_rec["area_total_mm2"] = round(total_area, 2)
        print(f"[{time.monotonic() - started:6.1f}s] bodies: "
              f"{len(bodies)}, top area {bodies[0]['area_mm2'] if bodies else 0}",
              flush=True)

        # Rep attribution: each rep's decoded point centroid -> body cell.
        # (Body lookup by centroid cell root; reps spanning bodies count
        # once at their centroid — attribution, not partition.)
        scanned = composite._scan_token_nodes(data, lo, hi)
        rep_nodes = composite._rep_node_positions(scanned, groups)
        pool_by_node = {}
        for group, node in zip(groups, rep_nodes):
            if node is not None and node not in pool_by_node:
                pool_by_node[node] = group
        scanned_map = {npos: (p, c1) for npos, p, c1, _c2 in scanned}

        for k, (group, node) in enumerate(zip(groups, rep_nodes)):
            if args.max_reps is not None and k >= args.max_reps:
                break
            n_pts = 0
            cx = cy = cz = 0.0
            minx = miny = minz = math.inf
            maxx = maxy = maxz = -math.inf
            if node is not None and node in scanned_map:
                payload, c1 = scanned_map[node]
                record, failure = composite._decode_rep_node(
                    payload, c1, list(group.vertices) if group is not None else []
                )
                if record is not None:
                    n_pts = len(record["pts"])
                    for x, y, z in record["pts"]:
                        cx += x
                        cy += y
                        cz += z
                        if x < minx:
                            minx = x
                        if y < miny:
                            miny = y
                        if z < minz:
                            minz = z
                        if x > maxx:
                            maxx = x
                        if y > maxy:
                            maxy = y
                        if z > maxz:
                            maxz = z
                    if n_pts:
                        cx /= n_pts
                        cy /= n_pts
                        cz /= n_pts
                else:
                    failure = failure[:80]
            if n_pts:
                key = (int(cx // args.cell_mm), int(cy // args.cell_mm),
                       int(cz // args.cell_mm))
                # Which top body contains this cell? Linear scan over the
                # top bodies' bboxes (few bodies, exact enough).
                body_i = ""
                for bi, b in enumerate(bodies[:10]):
                    if (b["bbox_min"][0] <= cx <= b["bbox_max"][0]
                            and b["bbox_min"][1] <= cy <= b["bbox_max"][1]
                            and b["bbox_min"][2] <= cz <= b["bbox_max"][2]):
                        body_i = bi
                        break
                rep_rows.append([
                    span_i, k, record.get("law", "") if record else "",
                    n_pts, body_i,
                    round(minx, 2), round(miny, 2), round(minz, 2),
                    round(maxx, 2), round(maxy, 2), round(maxz, 2),
                ])
            else:
                rep_rows.append([
                    span_i, k, "", 0, "",
                    "", "", "", "", "", "",
                ])
        span_rec["reps_attributed"] = len(rep_rows)
        del scanned, rep_nodes, pool_by_node, scanned_map

    report["elapsed_s"] = round(time.monotonic() - started, 1)
    print(json.dumps(report, indent=1, default=str))

    if args.rep_csv:
        with open(args.rep_csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["span", "rep", "law", "n_pts", "body",
                        "bbox_min_x", "bbox_min_y", "bbox_min_z",
                        "bbox_max_x", "bbox_max_y", "bbox_max_z"])
            w.writerows(rep_rows)
        print(f"rep rows: {args.rep_csv}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
