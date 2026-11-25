#!/usr/bin/env python3
"""W20 dodge routing probe (read-only triage, 2026-11-22).

The W12 finding: the dodge-challenger export matches 0 of 435,988
reference triangles, its bbox diagonal is 10.16x the reference's, and
6,310 tiny reps (~320 points each) form "the main foreign body"
(2,034,946 tris of the 2,496,624 exported).  Two probe phases separate
the hypotheses:

- **Phase A (``--phase pool``)**: units/scale + per-rep scale
  classification from the pool groups ALONE (``pool.scan_pool_groups``,
  no decode, no triangulation).  The reference STL is streamed (never
  materialized: 50-byte records, running bbox + a rounded-key set of
  unique vertices); the factors/permutations run as set intersections
  in both directions (ref-in-pool = the unit-law signal;
  pool-in-ref = the routing signal).
- **Phase B (``--phase decode``)**: the full composite decode —
  exported-rep routing, per-rep decode law/failure, per-rep exported
  triangle counts, unused-vertex ownership.  Run only when the gate
  window allows (the anti-OOM protocol; the decode is the heavy part).

Coordinate keys round to 0.01 (10 um at mm scale): float32 ulp at
car-scale magnitudes is <= 0.001, safely inside the half-grid 0.005.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from catpart.geometry import composite, pool  # noqa: E402 - path setup first

sys.path.insert(0, str(Path(__file__).resolve().parent))

from w20_probe_lib import coord_key, load_triage, stream_stl  # noqa: E402

PROBE = load_triage("probe_top10_mesh_gap_dump")

#: Candidate linear factors pool->reference (unit candidates first).
SCALES = [1.0, 0.1, 10.0, 2.54, 1 / 2.54, 25.4, 1 / 25.4, 0.001, 1000.0]


def _bbox(points) -> tuple[list[float], list[float], float]:
    mins = [math.inf] * 3
    maxs = [-math.inf] * 3
    for x, y, z in points:
        if x < mins[0]:
            mins[0] = x
        if y < mins[1]:
            mins[1] = y
        if z < mins[2]:
            mins[2] = z
        if x > maxs[0]:
            maxs[0] = x
        if y > maxs[1]:
            maxs[1] = y
        if z > maxs[2]:
            maxs[2] = z
    diag = math.sqrt(sum((maxs[i] - mins[i]) ** 2 for i in range(3)))
    return mins, maxs, diag


def signed_permutations() -> list[tuple[int, int, int]]:
    """The 6 axis index permutations (sign handled by +/- scale pairs)."""
    out = []
    for i0 in range(3):
        for i1 in range(3):
            for i2 in range(3):
                if len({i0, i1, i2}) == 3:
                    out.append((i0, i1, i2))
    return out


def ref_in_pool_rate(ref_keys: set, pool_keys: set, scale: float) -> float:
    """Reference vertices present in the untransformed pool key set when
    the reference is transformed by 1/scale (the unit-law signal)."""
    inv = 1.0 / scale
    rkeys = set()
    for k in ref_keys:
        x, y, z = struct.unpack("<3f", k)
        rkeys.add(coord_key(x * inv, y * inv, z * inv))
    rate = sum(1 for k in rkeys if k in pool_keys) / len(rkeys)
    del rkeys
    return rate


def pool_in_ref_rate(ref_keys: set, points, scale: float) -> tuple[float, float]:
    """The point set transformed by ``scale`` against the reference
    (the routing signal): (share of ref vertices covered, share of the
    transformed point keys that are ref vertices)."""
    tkeys = set()
    for x, y, z in points:
        tkeys.add(coord_key(x * scale, y * scale, z * scale))
    covered = sum(1 for k in ref_keys if k in tkeys) / len(ref_keys)
    share = len(tkeys & ref_keys) / len(tkeys) if tkeys else 0.0
    del tkeys
    return covered, share


def permuted_scale_rates(ref_keys: set, pool_keys: set, perm, scale: float) -> float:
    """ref->pool ref->pool coincidence under an axis permutation
    (ref axes reordered by ``perm`` then scaled)."""
    i0, i1, i2 = perm
    inv = 1.0 / scale
    hit = 0
    for k in ref_keys:
        x, y, z = struct.unpack("<3f", k)
        p = (x, y, z)
        if coord_key(p[i0] * inv, p[i1] * inv, p[i2] * inv) in pool_keys:
            hit += 1
    return hit / len(ref_keys) if ref_keys else 0.0


def classify_rep(rate_s1: float, rate_best: float, best_scale: float) -> str:
    if rate_s1 >= 0.5:
        return "ref-scale"
    if best_scale != 1.0 and rate_best >= 0.5:
        return f"ref-scale-x{best_scale:g}"
    if rate_s1 > 0.0 or rate_best > 0.0:
        return "partial-coincidence"
    return "foreign"


def phase_decode(args, ref: dict, report: dict) -> None:
    """The full composite decode: scale sweep over the EXPORTED points,
    the per-rep routing map (the decode's own export decision rebuilt:
    absorption + the M2b refs gate, in group order = the decode's
    concatenation order), per-rep unused-vertex ownership and the
    rep-body spatial clusters."""
    started = time.monotonic()
    data = args.catpart.read_bytes()
    ref_keys = ref["keys"]
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
        pmins, pmaxs, pdiag = _bbox(points)
        tmins, tmaxs, tdiag = _bbox(
            (points[i] for t in triangles for i in t)
        )
        span_rec.update({
            "n_pool_groups": len(groups),
            "n_points": len(points),
            "n_triangles": len(triangles),
            "points_bbox_min": pmins, "points_bbox_max": pmaxs,
            "points_diag": pdiag,
            "tri_bbox_min": tmins, "tri_bbox_max": tmaxs, "tri_diag": tdiag,
            "stage": info.get("stage"),
            "reps_exported": info.get("reps_exported"),
            "unused_pool_vertices": info.get("unused_pool_vertices"),
        })
        print(f"[{time.monotonic() - started:6.1f}s] span {span_i}: "
              f"{len(points)} pts, {len(triangles)} tris, stage "
              f"{info.get('stage')}, pts diag {pdiag:.2f}", flush=True)

        # The scale sweep on the EXPORTED point set: build the
        # untransformed key set once, then sweep.
        pool_keys = set()
        for x, y, z in points:
            pool_keys.add(coord_key(x, y, z))
        scales = {}
        for s in SCALES:
            rip = ref_in_pool_rate(ref_keys, pool_keys, s)
            pir, share = pool_in_ref_rate(ref_keys, points, s)
            scales[s] = {"ref_in_pool": round(rip, 4),
                         "pool_in_ref": round(pir, 4),
                         "pool_share": round(share, 4)}
            print(f"[{time.monotonic() - started:6.1f}s]   scale {s:g}: "
                  f"{scales[s]}", flush=True)
        best_scale = max(scales, key=lambda s: scales[s]["ref_in_pool"])
        span_rec["scale_rates"] = {f"{s:g}": r for s, r in scales.items()}
        span_rec["best_scale"] = best_scale

        # The per-rep routing map over the decode's own structure: the
        # export decision rebuilt (absorption + refs gate) and the
        # point-space offsets replayed in group order (the decode's
        # concatenation order), so unused-vertex ownership per rep is
        # derivable.
        used = bytearray(len(points))
        for tri in triangles:
            used[tri[0]] = used[tri[1]] = used[tri[2]] = 1
        scanned = composite._scan_token_nodes(data, lo, hi)
        rep_nodes = composite._rep_node_positions(scanned, groups)
        pool_by_node = {}
        for group, node in zip(groups, rep_nodes):
            if node is not None and node not in pool_by_node:
                pool_by_node[node] = group
        scanned_map = {npos: (p, c1) for npos, p, c1, _c2 in scanned}
        scanned_positions = [npos for npos, _p, _c1, _c2 in scanned]

        base = 0
        for k, (group, node) in enumerate(zip(groups, rep_nodes)):
            gverts = list(group.vertices) if group is not None else []
            law = failure = ""
            n_pts = 0
            exported = False
            if node is not None and node in scanned_map:
                payload, c1 = scanned_map[node]
                record, failure = composite._decode_rep_node(payload, c1, gverts)
                if record is not None:
                    law = record["law"]
                    n_pts = len(record["pts"])
                    pts_set = set(record["pts"])
                    unmatched = [
                        v for v in set(gverts)
                        if v not in pts_set
                        and ((best := composite._tol_match(v, record["pts"]))
                             is None or best > composite.NOISE_REL)
                    ]
                    nxt_candidates = [p for p in scanned_positions if p > node]
                    nxt = min(nxt_candidates) if nxt_candidates else hi
                    records, _nh = composite.parse_strip_records(
                        data, node + 4 + record["region_end_rel"], nxt, c1,
                        elements=record["elements"],
                    )
                    grefs = [
                        r for _o, mk, _n, _c, refs, _w in records
                        if mk in composite.GATED for r in refs
                    ]
                    refs_ok = not grefs or max(grefs) < c1
                    exported = not unmatched and refs_ok
                else:
                    failure = failure[:120]
            rep_unused = ""
            if exported:
                rep_unused = sum(
                    1 for i in range(base, base + n_pts) if not used[i]
                )
                base += n_pts
            gmins, gmaxs, gdiag = _bbox(gverts) if gverts else (
                [0.0] * 3, [0.0] * 3, 0.0)
            rep_rows.append([
                span_i, k, node if node is not None else "", law, failure,
                n_pts, len(gverts), round(gdiag, 4),
                int(exported), rep_unused,
            ])
            del gverts
        span_rec["reps_classified"] = len(rep_rows)
        span_rec["points_consumed_by_reps"] = base
        del pool_keys, scanned, rep_nodes, pool_by_node, scanned_map

    report["elapsed_s"] = round(time.monotonic() - started, 1)

    if args.rep_csv:
        with open(args.rep_csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["span", "rep", "node", "law", "failure", "n_pts",
                        "n_group_verts", "group_diag", "exported",
                        "unused_pts"])
            w.writerows(rep_rows)
        print(f"rep rows: {args.rep_csv}", file=sys.stderr)


def phase_pool(args, ref: dict, report: dict) -> None:
    started = time.monotonic()
    data = args.catpart.read_bytes()
    ref_keys = ref["keys"]
    rep_rows: list[list] = []

    # Scan every span first, then release the file bytes: the sweep and
    # the per-rep classification only need the decoded groups, and the
    # 100 MB buffer is dead weight from here on.
    span_state: list[tuple[int, str, list, list]] = []
    for span_i, (container, span) in enumerate(PROBE.locate_spans(data)):
        groups, kinds = pool.scan_pool_groups(data, span.body_lo, span.body_hi)
        span_state.append((span_i, container, groups, kinds))
    del data

    for span_i, container, groups, kinds in span_state:
        span_rec = {"span": span_i, "container": container,
                    "composite": pool.has_composite_space(kinds)}
        report["spans"].append(span_rec)
        if not span_rec["composite"]:
            span_rec["outcome"] = "not-composite-skipped"
            continue

        all_points = [v for g in groups for v in g.vertices]
        pmins, pmaxs, pdiag = _bbox(all_points)
        span_rec.update({
            "n_pool_groups": len(groups),
            "n_pool_points": len(all_points),
            "pool_bbox_min": pmins, "pool_bbox_max": pmaxs, "pool_diag": pdiag,
        })
        print(f"[{time.monotonic() - started:6.1f}s] span {span_i}: "
              f"{len(groups)} groups, {len(all_points)} pool pts, "
              f"diag {pdiag:.2f}", flush=True)

        pool_keys = set()
        for x, y, z in all_points:
            pool_keys.add(coord_key(x, y, z))
        print(f"[{time.monotonic() - started:6.1f}s]   pool key set "
              f"{len(pool_keys)}", flush=True)
        scales = {}
        for s in SCALES:
            rip = ref_in_pool_rate(ref_keys, pool_keys, s)
            pir, share = pool_in_ref_rate(ref_keys, all_points, s)
            scales[s] = {"ref_in_pool": round(rip, 4),
                         "pool_in_ref": round(pir, 4),
                         "pool_share": round(share, 4)}
            print(f"[{time.monotonic() - started:6.1f}s]   scale {s:g}: "
                  f"{scales[s]}", flush=True)
        best_scale = max(scales, key=lambda s: scales[s]["ref_in_pool"])
        del all_points
        span_rec["scale_rates"] = {f"{s:g}": r for s, r in scales.items()}
        span_rec["best_scale"] = best_scale

        if args.perms and scales[best_scale]["ref_in_pool"] < 0.5:
            perm_rates = {}
            for s in {best_scale, -best_scale, 1.0, -1.0, 0.1, -0.1, 10.0, -10.0}:
                for perm in signed_permutations():
                    r = permuted_scale_rates(ref_keys, pool_keys, perm, s)
                    if r > 0.05:
                        perm_rates[f"{perm} @{s:g}"] = round(r, 4)
            span_rec["perm_rates_gt_0.05"] = dict(sorted(
                perm_rates.items(), key=lambda kv: -kv[1])[:12])

        # Per-rep (group) classification.
        for k, g in enumerate(groups):
            if args.max_reps is not None and k >= args.max_reps:
                break
            gverts = list(g.vertices)
            gmins, gmaxs, gdiag = _bbox(gverts)
            hit1 = sum(1 for v in gverts if coord_key(*v) in ref_keys)
            hitb = sum(
                1 for v in gverts
                if coord_key(v[0] * best_scale, v[1] * best_scale,
                        v[2] * best_scale) in ref_keys
            )
            n = len(gverts)
            rate_s1 = hit1 / n if n else 0.0
            rate_best = hitb / n if n else 0.0
            rep_rows.append([
                span_i, k, g.offset, n,
                round(gdiag, 4),
                round(rate_s1, 4), round(rate_best, 4),
                classify_rep(rate_s1, rate_best, best_scale),
            ])
            del gverts
        span_rec["reps_classified"] = len(rep_rows)
        del pool_keys

    report["elapsed_s"] = round(time.monotonic() - started, 1)

    if args.rep_csv:
        with open(args.rep_csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["span", "rep", "group_offset", "n_group_verts",
                        "group_diag", "rate_s1", "rate_best", "class"])
            w.writerows(rep_rows)
        print(f"rep rows: {args.rep_csv}", file=sys.stderr)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="w20_dodge_routing_probe",
        description="W20: scale/axis coincidence between a reference STL and "
        "the decoded CATPart pool (phase A), or the full per-rep decode "
        "routing map (phase B).",
    )
    ap.add_argument("--catpart", type=Path, required=True)
    ap.add_argument("--stl", type=Path, required=True)
    ap.add_argument("--phase", choices=["pool", "decode"], default="pool")
    ap.add_argument("--rep-csv", type=Path, default=None)
    ap.add_argument("--max-reps", type=int, default=None,
                    help="cap the per-rep walk (default: all)")
    ap.add_argument("--perms", action="store_true",
                    help="run the permutation sweep when identity fails")
    args = ap.parse_args(argv)

    started = time.monotonic()
    ref = stream_stl(args.stl)
    print(f"[{time.monotonic() - started:6.1f}s] ref: {ref['n_tri']} tris, "
          f"{ref['n_unique_verts']} unique verts, diag {ref['diag']:.2f}",
          flush=True)

    report: dict = {
        "catpart": str(args.catpart),
        "stl": str(args.stl),
        "phase": args.phase,
        "ref": {k: v for k, v in ref.items() if k != "keys"},
        "spans": [],
    }
    if args.phase == "pool":
        phase_pool(args, ref, report)
    else:
        phase_decode(args, ref, report)

    print(f"[{time.monotonic() - started:6.1f}s] done", flush=True)
    print(json.dumps(report, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
