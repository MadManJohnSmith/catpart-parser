#!/usr/bin/env python3
"""#63 micro-probe: per-CATSurfacicRep array pairing for the ``d2 d2 51``
sub-records (read-only, 2026-11-20).

Refines ``probe_t63_face_gp.py``: every ``0x51`` sub-record pairs with
the f32 point array IMMEDIATELY PRECEDING it inside its own class
record (not one global array per file). Measurements:

- (a) how many byte-exact sub-records are 100% manifold ON THEIR OWN
  (their own triangles over their own paired array: every edge used
  exactly twice, no degenerate, in-bounds);
- (b) the Plate assembly diagnosis: duplicate unordered triangles
  between sub-records and the edges with > 2 uses;
- (c) per file: sub-records grouped by paired array (one index space
  per group), duplicate unordered triangles dropped (first copy wins),
  and the file verdict — manifold + physical — over the concatenated
  groups; the projected L2 dev flips (currently-``fail`` files only).

Run::

    .venv/bin/python -I scripts/triage/probe_t63_pairing.py

Read-only over the corpus; no ``src/`` change.
"""

import csv
import json
import math
import os
import struct
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "triage"))

from probe_bagrep import load_manifest  # noqa: E402
from probe_t63_face_gp import (  # noqa: E402
    class_record_spans,
    fast_arrays,
    face_gp,
    subrecord_positions,
)

PHYSICAL_RATIO_MAX = 100.0
LATEST_REPORT = os.path.join(ROOT, "fitness", "reports", "20261121T002059Z-b2f7d8.json")


def pair_array(arrays, sub_start):
    """The sub-record's index space: the record's LARGEST declared array.

    The nearest-preceding-array framing was measured against this one:
    on Plate the later sub-records (#2/#3, N_tris=30) are out-of-bounds
    against their nearest-preceding 10-point arrays and fully in-bounds
    against the record's 118-point array — every 0x51 sub-record indexes
    the record's main point array, not the array that happens to sit in
    front of it.
    """
    return max(arrays, key=lambda a: a[3]) if arrays else None


def manifold_verdict(tris):
    """('manifold'|'over-use'|'degenerate'|'empty', over_used_edges).

    The repo's manifold bar (mesh_stats): every undirected edge used
    AT MOST twice — boundary (1-use) edges are legitimate open shells
    (G3 F6); only >2 uses break manifoldness.
    """
    uses = defaultdict(int)
    for a, b, c in tris:
        if a == b or b == c or a == c:
            return "degenerate", []
        for e in ((a, b), (b, c), (c, a)):
            uses[tuple(sorted(e))] += 1
    if not uses:
        return "empty", []
    over = [e for e, v in uses.items() if v > 2]
    return ("manifold", []) if not over else ("over-use", over)


def area_of(points, tris):
    total = 0.0
    for a, b, c in tris:
        pa, pb, pc = points[a], points[b], points[c]
        ux, uy, uz = (pb[k] - pa[k] for k in range(3))
        vx, vy, vz = (pc[k] - pa[k] for k in range(3))
        cx, cy, cz = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
        total += 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)
    return total


def bbox_diag(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points]
    return math.dist((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)))


def dedup(tris):
    """Drop duplicate UNORDERED triples (first copy wins)."""
    seen = set()
    out = []
    dups = 0
    for t in tris:
        key = tuple(sorted(t))
        if key in seen:
            dups += 1
            continue
        seen.add(key)
        out.append(t)
    return out, dups


def main():
    man = load_manifest(ROOT)
    rows = list(
        csv.DictReader(
            open(os.path.join(ROOT, "docs", "evidence", "data", "bagrep-probe.csv"))
        )
    )
    carriers = [r["path"] for r in rows if int(r["subrecords"] or 0) > 0]
    extra = [
        r["path"]
        for r in csv.DictReader(
            open(os.path.join(ROOT, "manifests", "corpus-manifest.csv"))
        )
        if "CAAMaiUserToolDatabase" in r["path"]
    ]
    report = json.load(open(LATEST_REPORT))

    def l2_status(f):
        l2 = f.get("l2")
        return l2["status"] if l2 else "fail"

    l2 = {f["path"]: l2_status(f) for f in report["files"]}
    dev_total = report["scalars"]["L2"]["dev"]["total"]
    dev_pass = report["scalars"]["L2"]["dev"]["pass"]

    exact_total = exact_self_manifold = inb_total = inb_self_manifold = 0
    exact_seen = 0
    files_ok = files_partial = flips = 0
    plate_diagnosis = None
    print(
        f"{'file':58} {'paired':>6} {'exact':>5} {'selfM':>5} {'dups':>5} "
        f"{'groups':>6} {'verdict':>9} {'l2':>5}"
    )
    for rel in carriers + extra:
        meta = man.get(rel)
        if meta is None:
            continue
        data = open(os.path.join(ROOT, meta["local"]), "rb").read()
        paired = exact = self_m = dups_total = 0
        exact_self_m = 0
        groups_ok = groups_bad = 0
        verdict_all = "no-tris"
        per_sub = []
        for start, end, nm in class_record_spans(data):
            pos = subrecord_positions(data, start, end)
            # the 0x51 patch sub-records only (0x00 = node-magic
            # artifacts; 0x50 carries a different counter framing)
            pos = [p for p in pos if data[p + 8] == 0x51]
            if not pos:
                continue
            arrays = fast_arrays(data, start, end)
            # group sub-records by their paired array (one index space)
            grouped = defaultdict(list)
            for j, p in enumerate(pos):
                nxt = pos[j + 1] if j + 1 < len(pos) else end
                arr = pair_array(arrays, p)
                if arr is None:
                    continue
                res = face_gp(data, p, nxt)
                _coff, astart, floats, npts = arr
                points = [
                    struct.unpack_from("<3f", data, astart + 12 * i)
                    for i in range(npts)
                ]
                paired += 1
                if res["closed_exact"]:
                    exact += 1
                tris = [
                    t
                    for t in res["tris"]
                    if all(0 <= v < len(points) for v in t)
                ]
                v, _over = manifold_verdict(tris)
                if v == "manifold":
                    self_m += 1
                    if res["closed_exact"]:
                        exact_self_m += 1
                per_sub.append((p, res["closed_exact"], v, len(tris)))
                grouped[(astart, npts)].append((points, tris, res, p, nxt))
            for _key, members in grouped.items():
                points, tris_all = [], []
                # concatenate the group's (identical) point tables once
                points = members[0][0]
                for _pt, tris, _res, _p, _n in members:
                    tris_all.extend(tris)
                tris_d, dups = dedup(tris_all)
                dups_total += dups
                v, over = manifold_verdict(tris_d)
                if v == "manifold":
                    area = area_of(points, tris_d)
                    diag = bbox_diag(points)
                    ratio = area / (diag * diag) if diag > 0 else math.inf
                    if 0 < ratio <= PHYSICAL_RATIO_MAX:
                        groups_ok += 1
                    else:
                        groups_bad += 1
                else:
                    groups_bad += 1
                if rel.endswith("Plate.CATPart") and "CAAScdAsm" in rel:
                    plate_diagnosis = {
                        "groups": len(grouped),
                        "members": len(members),
                        "dups": dups,
                        "verdict": v,
                        "over_edges": len(over),
                        "over_sample": over[:6],
                        "tris_raw": len(tris_all),
                        "tris_dedup": len(tris_d),
                        "per_sub": [
                            (p, ce, vv, nt) for p, ce, vv, nt in per_sub
                        ],
                    }
        n_tris_groups = groups_ok + groups_bad
        if n_tris_groups == 0:
            verdict_all = "no-tris"
        elif groups_bad == 0 and groups_ok > 0:
            verdict_all = "manifold"
        else:
            verdict_all = f"{groups_bad} bad"
        cur = l2.get(rel, "?")
        mark = ""
        if verdict_all == "manifold" and cur == "fail":
            flips += 1
            mark = " <-- FLIP"
        if verdict_all == "manifold":
            files_ok += 1
        elif groups_ok > 0:
            files_partial += 1
        exact_total += exact
        exact_seen += sum(1 for _p, ce, _v, _nt in per_sub if ce)
        exact_self_manifold += exact_self_m
        inb_total += sum(1 for _p, _ce, _v, nt in per_sub if nt)
        inb_self_manifold += self_m
        print(
            f"{rel[-56:]:58} {paired:>6} {exact:>5} {self_m:>5} {dups_total:>5} "
            f"{n_tris_groups:>6} {verdict_all:>9} {cur:>5}{mark}"
        )
    print(f"\n(a) self-manifold sub-records: {inb_self_manifold}/{inb_total} in-bounds; "
          f"{exact_self_manifold}/{exact_seen} of the byte-exact ones")
    print(f"(c) files with a manifold+physical d2d2 mesh: {files_ok}")
    print(f"    files with >=1 good group but a bad one: {files_partial}")
    print(f"    projected L2 dev flips (currently fail -> manifold+physical): {flips}")
    print(
        f"    L2 dev: {dev_pass}/{dev_total} = {dev_pass/dev_total:.4f} -> "
        f"{dev_pass+flips}/{dev_total} = {(dev_pass+flips)/dev_total:.4f} "
        f"(+{flips/dev_total*100:.2f} pp)"
    )
    if plate_diagnosis:
        print("\n(b) Plate assembly diagnosis:")
        for k, v in plate_diagnosis.items():
            print(f"    {k}: {v}")


if __name__ == "__main__":
    main()
