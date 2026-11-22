#!/usr/bin/env python3
"""W20 dodge duplicate census (read-only triage, 2026-11-22).

The body map found ONE connected body (2,697,586 of 2,697,824 tris)
and rep bboxes that repeat EXACTLY (reps 919/2334 and 3749/5164 carry
identical coordinate ranges).  This census quantifies the duplicate
share of the exported mesh: unordered coordinate-identity keys (the
stage-15 dedup law's identity, 1 um grid) over every exported triangle,
with the duplicate copies' area sum — the mechanical upper bound a
dedup law could ever remove, stated against the stage-15 gates
(non-manifold assembled mesh whose over-use the dedup must resolve).

Output: one JSON line-set on stdout (unique keys, duplicate count and
area, the top duplicate groups by total area).
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from catpart.geometry import composite, pool  # noqa: E402 - path setup first

sys.path.insert(0, str(Path(__file__).resolve().parent))

from w20_probe_lib import load_triage  # noqa: E402

PROBE = load_triage("probe_top10_mesh_gap_dump")

MAX_GROUPS = 4_000_000


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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="w20_dodge_dup_census")
    ap.add_argument("--catpart", type=Path, required=True)
    ap.add_argument("--top", type=int, default=12,
                    help="top duplicate groups to report")
    args = ap.parse_args(argv)

    started = time.monotonic()
    data = args.catpart.read_bytes()
    for span_i, (container, span) in enumerate(PROBE.locate_spans(data)):
        lo, hi = span.body_lo, span.body_hi
        groups, kinds = pool.scan_pool_groups(data, lo, hi)
        if not pool.has_composite_space(kinds):
            continue
        points, triangles, _deg, info = composite.decode_composite_store(
            data, span, groups, kinds
        )
        print(f"[{time.monotonic() - started:6.1f}s] span {span_i}: "
              f"{len(points)} pts, {len(triangles)} tris", flush=True)

        # Unordered coordinate-identity keys (stage-15 identity, 1 um).
        census: dict[bytes, list] = {}
        total_area = 0.0
        for a, b, c in triangles:
            pa = points[a]
            pb = points[b]
            pc = points[c]
            area = heron_area(pa[0], pa[1], pa[2], pb[0], pb[1], pb[2],
                              pc[0], pc[1], pc[2])
            total_area += area
            tri = sorted((
                (round(pa[0], 3), round(pa[1], 3), round(pa[2], 3)),
                (round(pb[0], 3), round(pb[1], 3), round(pb[2], 3)),
                (round(pc[0], 3), round(pc[1], 3), round(pc[2], 3)),
            ))
            key = struct.pack(
                "<9f",
                tri[0][0], tri[0][1], tri[0][2],
                tri[1][0], tri[1][1], tri[1][2],
                tri[2][0], tri[2][1], tri[2][2],
            )
            rec = census.get(key)
            if rec is None:
                if len(census) >= MAX_GROUPS:
                    raise SystemExit("named-outcome: census-budget-exceeded")
                census[key] = [1, area]
            else:
                rec[0] += 1
                rec[1] += area
        print(f"[{time.monotonic() - started:6.1f}s] census done", flush=True)

        n_tris = len(triangles)
        n_unique = len(census)
        dup_tris = n_tris - n_unique
        dup_area = sum(area * (count - 1) for count, area in census.values()
                       if count > 1)
        print(f"total_area_mm2 {total_area:.2f}")
        print(f"unique_triangle_keys {n_unique}")
        print(f"duplicate_copies {dup_tris}")
        print(f"duplicate_area_mm2 {dup_area:.2f}")
        print(f"duplicate_area_share {dup_area / total_area:.4f}")
        top = sorted(
            ((key, count, area) for key, (count, area) in census.items()
             if count > 1),
            key=lambda e: -e[2] * (e[1] - 1),
        )[: args.top]
        for key, count, area in top:
            coords = struct.unpack("<9f", key)
            print(f"dup x{count} area {area:.3f} "
                  f"verts {coords[0]:.2f},{coords[1]:.2f},{coords[2]:.2f} | "
                  f"{coords[3]:.2f},{coords[4]:.2f},{coords[5]:.2f} | "
                  f"{coords[6]:.2f},{coords[7]:.2f},{coords[8]:.2f}")
        report = {
            "span": span_i,
            "stage": info.get("stage"),
            "n_tris": n_tris,
            "total_area_mm2": round(total_area, 2),
            "unique_triangle_keys": n_unique,
            "duplicate_copies": dup_tris,
            "duplicate_area_mm2": round(dup_area, 2),
            "duplicate_area_share": round(dup_area / total_area, 4),
        }
        print(json.dumps(report, indent=1))
        break

    print(f"[{time.monotonic() - started:6.1f}s] done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
