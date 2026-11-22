#!/usr/bin/env python3
"""W7-B triage probe: attribute the PRIMARY degenerate triangle
emissions (the L2 ``degenerate-triangles-skipped`` count) to their
records. Wraps ``composite._triangulate``: for each primary exported
record it replays the emit mapping (skips -> written rank), replays
``_loop_triangles`` per counts-delimited loop and reports the loops
whose degenerate count is non-zero — with the record's offset, marker,
width, and the offending coordinates.

One JSON line per degenerate-carrying primary loop, plus a per-call
summary line (``{"kind": "call", ...}``) on stdout.

Usage: python3 scripts/triage/w7b_degenerate_probe.py <file.catpart>
"""

import json
import sys


def main() -> int:
    path = sys.argv[1]
    import catpart.geometry.composite as comp

    orig_triangulate = comp._triangulate
    EXPORTED = comp.EXPORTED_SHORT_MARKERS
    RELAXED = comp.RELAXED_SHORT_MARKERS

    def wrapped(elements, records, extended=(), seam_area=None, relist_skip=False):
        written_rank = {}
        skips = set()
        for i, (_v, pt) in enumerate(elements):
            if pt is None:
                skips.add(i)
            else:
                written_rank[i] = len(written_rank)
        points = [e[1] for e in elements if e[1] is not None]

        total = 0
        for rec in records:
            _off, mk, _normal, counts, refs, _w = rec
            if mk not in EXPORTED:
                continue
            o = 0
            rec_deg = 0
            for c in counts:
                loop = refs[o:o + c]
                o += c
                if not loop or any(r in skips for r in loop):
                    continue
                idxs = [written_rank[r] for r in loop]
                _tris, deg = comp._loop_triangles(mk, idxs, points)
                if deg:
                    rec_deg += deg
                    lp = [points[i] for i in idxs]
                    # locate the offending windows
                    bad = []
                    if mk == 0x4C:
                        for t in range(1, len(lp) - 1):
                            a, b, cc = lp[0], lp[t], lp[t + 1]
                            if a == b or b == cc or a == cc:
                                bad.append([t - 1, a, b, cc])
                    else:
                        for t in range(len(lp) - 2):
                            a, b, cc = lp[t], lp[t + 1], lp[t + 2]
                            if a == b or b == cc or a == cc:
                                bad.append([t, a, b, cc])
                            elif comp._cross_zero(a, b, cc):
                                bad.append([t, a, b, cc])
                    print(json.dumps({
                        "kind": "degenerate-loop", "marker": mk,
                        "offset": _off, "loop_len": c,
                        "loop_head": list(loop[:10]),
                        "written_head": idxs[:10],
                        "offenders": [[list(x[1]), list(x[2]), list(x[3])]
                                      for x in bad[:4]],
                        "n_offenders": len(bad),
                    }), flush=True)
            if rec_deg:
                print(json.dumps({
                    "kind": "call", "offset": _off, "marker": mk,
                    "degenerate": rec_deg,
                }), flush=True)
            total += rec_deg
        print(json.dumps({"kind": "total-primary-degenerate", "sum": total}),
              flush=True)
        return orig_triangulate(elements, records, extended=extended,
                                seam_area=seam_area, relist_skip=relist_skip)

    comp._triangulate = wrapped

    from catpart.cli import main_export
    sys.argv = ["catpart-export", path, "-o", "/tmp/w7b-run/degen-probe.ply"]
    return main_export()


if __name__ == "__main__":
    sys.exit(main())
