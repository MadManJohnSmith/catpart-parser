#!/usr/bin/env python3
"""W27 residual deep dive (read-only over the snapshot).

For each named .CATPart, reproduce ``build_export``'s composite-store
cascade and name the structure that keeps the part out of the L2 pass:

- every ``decode_composite_store`` call in the entry cascade (the
  registry pass, the seam-armed pass, the relist-skip pass) with its
  outcome — the multi-region route runs INSIDE the entry call, so its
  own counters (``multiregion_*``, ``multiregion_declined``) ride the
  adopted call's info
- the FINAL adopted mesh's edge-use histogram: the over-used edges
  (use > 2), each with the triangles that share it (whether two of
  them are the same three COORDINATES — a re-list — or distinct
  surface) and each triangle's area as a fraction of the mesh area
- coordinate-identity duplicate-triangle census over the adopted mesh
- the degenerate-carrying loops of the decode: every
  ``_loop_triangles`` call whose enumeration carries a degenerate
  triangle, named by marker kind and loop size (the emission's
  degenerate source attribution)

Every figure traces to this probe's stdout; the script never writes
inside the repo (the PLY goes to a temporary directory and is
discarded).  ``--selftest`` runs the sanity fixture (a synthetic
manifold box asserts the histogram math) before anything else.

Usage:
  python probe_w27_residual_deep.py <snapshot-dir> <repo-root> \
      part1.CATPart [part2.CATPart ...] [--selftest]
"""

from __future__ import annotations

import collections
import sys
import tempfile
from pathlib import Path


def _selftest() -> int:
    # The histogram/duplicate math on a synthetic manifold box: 12
    # triangles, every edge exactly 2 uses.
    pts = [
        (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (1.0, 1.0, 1.0), (0.0, 1.0, 1.0),
    ]
    tris = [
        (0, 2, 1), (0, 3, 2),  # bottom
        (4, 5, 6), (4, 6, 7),  # top
        (0, 1, 5), (0, 5, 4),  # front
        (1, 2, 6), (1, 6, 5),  # right
        (2, 3, 7), (2, 7, 6),  # back
        (3, 0, 4), (3, 4, 7),  # left
    ]
    use = collections.Counter()
    for a, b, c in tris:
        for e in ((a, b), (b, c), (c, a)):
            use[tuple(sorted(e))] += 1
    over = {e: n for e, n in use.items() if n > 2}
    assert not over, over
    assert all(n == 2 for n in use.values()), "box edges must all be 2-use"
    print("selftest OK: box 12 tris, all edges 2-use, 0 over-use")
    return 0


def _area(p0, p1, p2):
    ax = p1[0] - p0[0]
    ay = p1[1] - p0[1]
    az = p1[2] - p0[2]
    bx = p2[0] - p0[0]
    by = p2[1] - p0[1]
    bz = p2[2] - p0[2]
    cx = ay * bz - az * by
    cy = az * bx - ax * bz
    cz = ax * by - ay * bx
    return 0.5 * (cx * cx + cy * cy + cz * cz) ** 0.5


def _key(p):
    # f32-exact coordinate key (the values come from f32 triples).
    return tuple(float(x) for x in p)


def analyze_mesh(points, triangles):
    """Edge-use histogram + over-use structure + duplicate census."""
    use = collections.Counter()
    edge_tris: dict = collections.defaultdict(list)
    for ti, (a, b, c) in enumerate(triangles):
        for e in ((a, b), (b, c), (c, a)):
            k = tuple(sorted(e))
            use[k] += 1
            edge_tris[k].append(ti)
    over_edges = {e: n for e, n in use.items() if n > 2}
    # coordinate-identity duplicates (unordered)
    coord_count = collections.Counter()
    for a, b, c in triangles:
        coord_count[frozenset((_key(points[a]), _key(points[b]), _key(points[c])))] += 1
    dup_tris = sum(n - 1 for n in coord_count.values() if n > 1)
    dup_groups = sum(1 for n in coord_count.values() if n > 1)
    areas = [_area(points[a], points[b], points[c]) for a, b, c in triangles]
    total_area = sum(areas) or 1.0
    return {
        "over_edges": over_edges,
        "edge_tris": edge_tris,
        "dup_tris": dup_tris,
        "dup_groups": dup_groups,
        "areas": areas,
        "total_area": total_area,
    }


def deep_dive(part: Path, repo_root: Path) -> dict:
    sys.path.insert(0, str(repo_root / "src"))
    from catpart.geometry import composite
    from catpart.geometry.export import build_export

    calls: list[dict] = []
    meshes: list = []
    orig_decode = composite.decode_composite_store
    orig_loop = composite._loop_triangles

    def decode_capture(data, span, groups, kinds, **kw):
        rec = {
            "span": (span.body_lo, span.body_hi),
            "seam_area": kw.get("_seam_area", "unset"),
            "relist_skip": kw.get("_relist_skip", False),
        }
        try:
            result = orig_decode(data, span, groups, kinds, **kw)
        except Exception as exc:
            rec["error"] = f"{type(exc).__name__}: {exc}"
            calls.append(rec)
            raise
        pts, tris, degen, info = result
        rec.update(
            tris=len(tris),
            degenerate=degen,
            stage=info.get("stage"),
            reps=info.get("multiregion_reps"),
            extent_reps=info.get("multiregion_extent_reps"),
            container_reps=info.get("multiregion_container_reps"),
            kept=info.get("primary_loop_kept"),
            skips=info.get("primary_loop_skips"),
            seam_declined=info.get("primary_loop_seam_declined"),
            mr_declined=info.get("multiregion_declined"),
            dedup_dropped=info.get("unordered_dedup_dropped"),
            dedup_declined=info.get("unordered_dedup_declined"),
            relist_skips=info.get("primary_loop_relist_skips"),
            ext_filtered=info.get("extended_members_filtered"),
            split_skips=info.get("curve_entry_split_skips"),
        )
        calls.append(rec)
        meshes.append((pts, list(tris), info))
        return result

    deg_loops: list[dict] = []

    def loop_capture(mk, idxs, points):
        tris, deg = orig_loop(mk, idxs, points)
        if deg:
            deg_loops.append({"mk": mk, "loop": len(idxs), "deg": deg})
        return tris, deg

    composite.decode_composite_store = decode_capture
    composite._loop_triangles = loop_capture
    try:
        tmp = tempfile.mkdtemp(prefix="w27-deep-")
        summary = build_export(part, Path(tmp) / "out.ply")
    finally:
        composite.decode_composite_store = orig_decode
        composite._loop_triangles = orig_loop

    last_mesh = meshes[-1] if meshes else None
    analysis = None
    if last_mesh is not None:
        analysis = analyze_mesh(last_mesh[0], last_mesh[1])
    return {
        "summary": summary,
        "calls": calls,
        "last_mesh": last_mesh,
        "analysis": analysis,
        "deg_loops": deg_loops,
    }


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--selftest" in sys.argv:
        rc = _selftest()
        if not args:
            return rc
    snapshot = Path(args[0]).resolve()
    repo_root = Path(args[1]).resolve()
    names = args[2:]
    for name in names:
        part = snapshot / name
        if not part.exists():
            hits = sorted(snapshot.rglob(name))
            if not hits:
                print(f"== {name}: NOT FOUND")
                continue
            part = hits[0]
        d = deep_dive(part, repo_root)
        s = d["summary"]
        print(f"== {part.name}")
        print(
            f"   summary: tris={s['triangle_count']} vtx={s['vertex_count']} "
            f"degen={s.get('degenerate_triangle_count')}"
        )
        for w in s.get("warnings") or []:
            print(f"   warn: {w.get('class')}: {str(w.get('detail'))[:170]}")
        for c in d["calls"]:
            if "error" in c:
                print(f"   call: ERROR {c['error'][:140]}")
                continue
            print(
                f"   call: seam={c['seam_area']} relist={c['relist_skip']} "
                f"-> tris={c['tris']} degen={c['degenerate']} stage={c['stage']} "
                f"reps={c['reps']} ext={c.get('extent_reps')} cont={c.get('container_reps')} "
                f"kept={c['kept']} skips={c['skips']} seamdecl={c['seam_declined']} "
                f"relist={c['relist_skips']} dedupD={c['dedup_dropped']} "
                f"dedupX={c['dedup_declined']} extF={c['ext_filtered']} split={c['split_skips']}"
            )
            if c.get("mr_declined"):
                print(f"      mr_declined: {str(c['mr_declined'])[:220]}")
        if d["deg_loops"]:
            by = collections.Counter((l["mk"], l["loop"]) for l in d["deg_loops"])
            tot = sum(l["deg"] for l in d["deg_loops"])
            print(f"   degenerate loops: total deg={tot} by (mk,loopsize): {dict(by)}")
        a = d["analysis"]
        if a:
            print(
                f"   adopted mesh: over-edges={len(a['over_edges'])} "
                f"dup-coord-tris={a['dup_tris']} ({a['dup_groups']} groups) "
                f"total_area={a['total_area']:.4g}"
            )
            pts, tris, _info = d["last_mesh"]
            shown = 0
            for e, n in sorted(a["over_edges"].items(), key=lambda kv: -kv[1]):
                tis = a["edge_tris"][e]
                coord_sets = [
                    frozenset(_key(pts[i]) for i in tris[ti]) for ti in tis
                ]
                same = len(coord_sets) != len({frozenset(cs) for cs in coord_sets})
                ars = [100 * a["areas"][ti] / a["total_area"] for ti in tis]
                print(
                    f"     edge {e} use={n} tris={tis} "
                    f"coord-dup-within={'YES' if same else 'no'} "
                    f"area%={[round(x, 3) for x in ars]}"
                )
                shown += 1
                if shown >= 12:
                    print("     ... (truncated)")
                    break
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
