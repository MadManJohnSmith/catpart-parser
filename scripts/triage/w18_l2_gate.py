#!/usr/bin/env python3
"""W18 triage probe: the L2 gate over a micro-batch of corpus files.

Mirrors the fitness runner's L2 measurement exactly
(:func:`catpart.fitness.runner._measure_l2` — ``build_export`` + the
``_score_export`` gate order: empty-mesh, not-manifold, nonfinite-bbox,
degenerate-triangles) without launching a corpus run, so a
width-law change can be validated file by file. Prints one JSON line
per file: path, verdict, failed check, vertex/triangle/degenerate
counts, boundary edges.

Usage: python3 scripts/triage/w18_l2_gate.py <file.CATPart> [...] [--ply DIR]
"""

import json
import sys
from pathlib import Path


def main() -> int:
    args = sys.argv[1:]
    ply_dir = None
    if "--ply" in args:
        i = args.index("--ply")
        ply_dir = Path(args[i + 1])
        ply_dir.mkdir(parents=True, exist_ok=True)
        args = args[:i] + args[i + 2 :]

    from catpart.fitness.runner import _measure_l2

    tmp = Path("/tmp") if ply_dir is None else ply_dir
    for arg in args:
        path = Path(arg)
        out = tmp / ("w18-" + path.stem + ".ply")
        rec = _measure_l2(path, out)
        print(
            json.dumps(
                {
                    "file": str(path),
                    "status": rec["status"],
                    "failed_check": rec["failed_check"],
                    "vertices": rec["vertex_count"],
                    "triangles": rec["triangle_count"],
                    "degenerate": rec["degenerate_triangle_count"],
                    "boundary": (rec["mesh"] or {}).get("boundary_edge_count"),
                    "error": rec["error"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
