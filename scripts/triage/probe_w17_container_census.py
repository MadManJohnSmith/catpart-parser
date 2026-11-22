#!/usr/bin/env python3
"""W17 container-family census over the local corpus (read-only).

For every .CATPart under the given directories:

1. run the committed export (``export._export_data``) — streaming, one
   file in RAM at a time (the anti-OOM rule);
2. classify: not-manifold stores (``summary['mesh']['manifold'] is
   False``) are the W17 candidate set;
3. for each candidate: scan the store body for token nodes, classify
   each as walk-exact / container (``00 00 00 01`` at counts_end) /
   walk-fail-other; report the multiregion decline string when present.

Output CSV rows to --out: part, vtx, tris, degenerate, manifold,
multiregion_declined_short, nodes_total, walk_exact, containers,
walk_fail_other.

Run::

    .venv/bin/python -I scripts/triage/probe_w17_container_census.py \
        --out <csv> <dir>...

Read-only over the corpus.
"""

import argparse
import csv
import gc
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catpart.geometry import composite, export, store  # noqa: E402
from catpart.geometry.errors import ExportError  # noqa: E402

from probe_w17_container_scan import scan_nodes  # noqa: E402


def node_class(payload, c1):
    counts_end = composite._token_counts_end(payload)
    if counts_end is None:
        return "unreadable"
    if payload[counts_end : counts_end + 4] == b"\x00\x00\x00\x01":
        return "container"
    try:
        composite.decode_region(payload, c1)
        return "walk-exact"
    except ExportError:
        return "walk-fail-other"


def probe_part(path):
    with open(path, "rb") as fh:
        data = fh.read()
    try:
        summary, _verts, _tris = export._export_data(data)
    except Exception:
        return None
    meshinfo = summary.get("mesh") or {}
    if meshinfo.get("manifold", True) and summary.get("triangle_count"):
        return None  # manifold or empty: not the W17 set
    comp = summary.get("composite") or {}
    # store-scoped node census (the exporter's located spans)
    size = len(data)
    d8_outer = int.from_bytes(data[8:12], "big") if size >= 12 else 0
    blocks = store.valid_blocks(data)
    classes = []
    for blk, nm in blocks:
        try:
            span = store.locate_store(data, blk, blocks, d8_outer)
        except ExportError:
            continue
        if span is None:
            continue
        nodes = scan_nodes(data, span.body_lo, span.body_hi)
        for _p, payload, c1, _c2 in nodes:
            classes.append(node_class(payload, c1))
        break  # the first located store only (the exporter's win order)
    declined = comp.get("multiregion_declined", "")
    if len(declined) > 90:
        declined = declined[:90]
    return {
        "part": os.path.basename(path),
        "vtx": summary.get("vertex_count", 0),
        "tris": summary.get("triangle_count", 0),
        "degenerate": summary.get("degenerate_triangle_count", 0),
        "stage": comp.get("stage", ""),
        "containers": classes.count("container"),
        "walk_exact": classes.count("walk-exact"),
        "walk_fail_other": classes.count("walk-fail-other"),
        "multiregion_declined": declined,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="*")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    files = []
    for root in args.dirs:
        for dirpath, _dirs, names in os.walk(root):
            for nm in sorted(names):
                if nm.lower().endswith(".catpart"):
                    files.append(os.path.join(dirpath, nm))
    fields = [
        "part", "vtx", "tris", "degenerate", "stage",
        "containers", "walk_exact", "walk_fail_other", "multiregion_declined",
    ]
    n = cand = withcont = 0
    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for i, path in enumerate(files):
            n += 1
            try:
                row = probe_part(path)
            except Exception as exc:  # noqa: BLE001 — census keeps going
                print(f"ERR {os.path.basename(path)}: {exc}", file=sys.stderr)
                row = None
            if row is not None:
                cand += 1
                w.writerow(row)
                if row["containers"]:
                    withcont += 1
                    print(
                        f"CANDIDATE {row['part']}: tris={row['tris']} "
                        f"containers={row['containers']} walk_exact={row['walk_exact']} "
                        f"other={row['walk_fail_other']} declined="
                        f"{row['multiregion_declined'][:60]}"
                    )
            if (i + 1) % 100 == 0:
                print(f"  .. {i + 1}/{len(files)} files, {cand} candidates, "
                      f"{withcont} with containers", flush=True)
            del row
            gc.collect()
    print(f"== {n} files, {cand} not-manifold/nonempty candidates, "
          f"{withcont} carry container nodes -> {args.out}")


if __name__ == "__main__":
    main()
