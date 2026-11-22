#!/usr/bin/env python3
"""W17 container mesh probe (read-only, 2026-11-22).

Hypothesis H1, mesh stage: a container-family node payload
([token][c1][c2]["00 00 00 01"][c1 raw f32 triples][middle][records])
carries a SELF-CONTAINED surface — its records triangulated against its
own triple window.  This probe, per container node:

1. extracts the triple window's written points (all c1 elements);
2. parses the strip + extended records from the window end (the
   committed parsers, skipping the undecoded middle);
3. runs the committed :func:`composite._triangulate` over them;
4. reports mesh_stats (manifold / closed / boundary), degenerate
   count, triangle count, and the used-vertex share;
5. ALSO reports the store context: the store span the exporter's
   probe order locates, every token node in it (walk-exact or
   container), so the container's position in the rep sequence is
   measurable (H2 input).

Run::

    .venv/bin/python -I scripts/triage/probe_w17_container_mesh.py <file.CATPart>...

Read-only; no src/ change.
"""

import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catpart.geometry import composite, mesh, store  # noqa: E402
from catpart.geometry.errors import ExportError  # noqa: E402

from probe_w17_container_scan import scan_file  # noqa: E402


def container_decode(payload, c1):
    """The container reading: (points, records, extended, failure)."""
    counts_end = composite._token_counts_end(payload)
    if payload[counts_end : counts_end + 4] != b"\x00\x00\x00\x01":
        return None
    start = counts_end + 4
    end = start + 12 * c1
    if end > len(payload):
        return None
    pts = []
    for k in range(c1):
        x, y, z = struct.unpack_from("<fff", payload, start + 12 * k)
        if not (x == x and abs(x) < 1e9 and y == y and abs(y) < 1e9 and z == z and abs(z) < 1e9):
            return None
        pts.append((x, y, z))
    return pts, start, end


def mesh_report(label, elements, records, extended):
    tris, deg, stats_k = composite._triangulate(elements, records, extended=extended)
    ms = mesh.mesh_stats(list(tris))
    print(
        f"    {label}: tris={len(tris)} degenerate={deg} manifold={ms.manifold} "
        f"closed={ms.closed} boundary={ms.boundary_edges} edges={ms.edge_count} "
        f"oriented={ms.oriented}"
    )
    return tris, deg, ms


def probe(path):
    data, nodes = scan_file(path)
    print(f"== {os.path.basename(path)}: {len(nodes)} token nodes")
    # store spans (the exporter's probe order)
    size = len(data)
    d8_outer = int.from_bytes(data[8:12], "big") if size >= 12 else 0
    blocks = store.valid_blocks(data)
    spans = []
    for blk, nm in blocks:
        try:
            span = store.locate_store(data, blk, blocks, d8_outer)
        except ExportError:
            continue
        if span is not None:
            spans.append((nm, span.body_lo, span.body_hi))
    for nm, lo, hi in spans:
        inspan = [(p, pl, c1, c2) for p, pl, c1, c2 in nodes if lo <= p < hi]
        if not inspan:
            continue
        print(f"  store {nm} [0x{lo:x},0x{hi:x}): {len(inspan)} nodes")
        for npos, payload, c1, c2 in inspan:
            counts_end = composite._token_counts_end(payload)
            is_container = (
                counts_end is not None
                and payload[counts_end : counts_end + 4] == b"\x00\x00\x00\x01"
            )
            try:
                _elements, info = composite.decode_region(payload, c1)
                status = f"walk-exact (region_end={info['walk_end']})"
            except ExportError as exc:
                status = "walk-fail"
            kind = "CONTAINER" if is_container else "p1t"
            print(f"    node@0x{npos:x} {kind} c1={c1} c2={c2} len={len(payload)}B {status}")
            if not is_container:
                continue
            dec = container_decode(payload, c1)
            if dec is None:
                print("      container: triples window not nice — H1 declines")
                continue
            pts, start, end = dec
            elements = [(3, pt) for pt in pts]
            abs_start = npos + 4
            try:
                records, n_hdrs = composite.parse_strip_records(
                    data, abs_start + end, abs_start + len(payload), c1
                )
            except ExportError as exc:
                print(f"      strip: ExportError {exc.detail[:60]}")
                records, n_hdrs = [], 0
            try:
                extended, _c = composite.parse_extended_facet_records(
                    data, abs_start + end, abs_start + len(payload), c1
                )
            except ExportError:
                extended = []
            print(
                f"      container: {len(pts)} pts [{start},{end}), "
                f"{len(records)} strip recs ({n_hdrs} hdrs), {len(extended)} ext recs"
            )
            if records or extended:
                mesh_report("container mesh", elements, records, extended)


def main():
    for path in sys.argv[1:]:
        probe(path)


if __name__ == "__main__":
    main()
