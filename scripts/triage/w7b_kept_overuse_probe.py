#!/usr/bin/env python3
"""W7-B triage probe: capture the primary loops the emit seam KEPT over
an over-use (``primary-loop-manifold-kept``) — the manifold breakers.

``EdgeGuard.fold`` is called exactly on the keep arm (the seam's
large-loop arm and the extended/relaxed folds ride admit's accept arm),
so wrapping ``fold`` logs the kept units' triangles; the loop triangles
are mapped back to the emitting records by re-running the strip walk
over the captured records list.

Usage: python3 scripts/triage/w7b_kept_overuse_probe.py <file.catpart>
"""

import json
import sys


def main() -> int:
    path = sys.argv[1]
    import catpart.geometry.composite as comp
    import catpart.geometry.mesh as mesh_mod

    ctx = {"fold_n": 0}

    orig_fold = mesh_mod.EdgeGuard.fold

    def wrapped_fold(self, tris):
        ctx.setdefault("folds", []).append(list(tris))
        ctx["fold_n"] += 1
        return orig_fold(self, tris)

    mesh_mod.EdgeGuard.fold = wrapped_fold
    # composite imports EdgeGuard by name — patch there too.
    comp.EdgeGuard = mesh_mod.EdgeGuard

    orig_tria = comp._triangulate

    def wrapped_tria(elements, records, extended=(), seam_area=None,
                     relist_skip=False):
        ctx["elements"] = elements
        ctx["records"] = list(records)
        ctx["extended"] = list(extended)
        written_rank = {}
        skips = set()
        for i, (_v, pt) in enumerate(elements):
            if pt is None:
                skips.add(i)
            else:
                written_rank[i] = len(written_rank)
        points = [e[1] for e in elements if e[1] is not None]
        ctx["written_rank"] = written_rank
        ctx["skips"] = skips
        ctx["points"] = points
        return orig_tria(elements, records, extended=extended,
                         seam_area=seam_area, relist_skip=relist_skip)

    comp._triangulate = wrapped_tria

    from catpart.cli import main_export
    sys.argv = ["catpart-export", path, "-o", "/tmp/w7b-run/kept-probe.ply"]
    rc = main_export()

    folds = ctx.get("folds", [])
    print(json.dumps({"kind": "fold-count", "n": len(folds)}))
    # Map each fold's triangles to a record loop by refs
    wr = ctx.get("written_rank", {})
    points = ctx.get("points", [])
    for tris in folds:
        # candidate loop refs: the union of tri vertices (written ranks)
        vs = sorted({v for t in tris for v in t})
        # find the record loop whose written-rank list matches
        best = None
        for _i, (off, mk, _n, counts, refs, _w) in enumerate(ctx.get("records", [])):
            if mk not in comp.EXPORTED_SHORT_MARKERS:
                continue
            o = 0
            for c in counts:
                loop = refs[o:o + c]
                o += c
                if not loop or any(r in ctx["skips"] for r in loop):
                    continue
                idxs = [wr[r] for r in loop]
                tris2, _deg = comp._loop_triangles(mk, idxs, points)
                if tris2 and list(map(tuple, tris2)) == list(map(tuple, tris)):
                    best = {"offset": off, "marker": mk, "loop_len": c,
                            "loop_refs": list(loop[:12])}
                    break
            if best:
                break
        print(json.dumps({"kind": "fold", "n_tris": len(tris),
                          "vertices": vs[:12], "record": best}))

    from catpart.cli import main_export as _me  # noqa: F401
    return rc


if __name__ == "__main__":
    sys.exit(main())
