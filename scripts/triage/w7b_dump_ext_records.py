#!/usr/bin/env python3
"""W7-B triage probe: dump every extended-header facet record the Python
decoder parses from one file, one JSON line per record on stdout, so the
Rust twin's dump can be diffed record by record (the head_ia 61/62
decline divergence, 2026-11-22).

Monkey-patches ``parse_extended_facet_records`` (no source edits), then
runs the standard ``catpart-export`` main. Also dumps the short-form
strip records (offset + marker only) for the same diff.

Usage: python3 scripts/triage/w7b_dump_ext_records.py <file.catpart>
"""

import hashlib
import json
import struct
import sys


def main() -> int:
    path = sys.argv[1]
    import catpart.geometry.composite as comp

    orig_ext = comp.parse_extended_facet_records
    orig_strip = comp.parse_strip_records

    def wrapped_ext(data, lo, hi, element_count=None, elements=None, shipped_spans=()):
        recs, cands = orig_ext(data, lo, hi, element_count,
                               elements=elements, shipped_spans=shipped_spans)
        for r in recs:
            refs_bytes = struct.pack(f"<{len(r.refs)}I", *r.refs)
            print(json.dumps({
                "kind": "ext", "region_lo": lo, "region_hi": hi,
                "offset": r.offset, "marker": r.marker,
                "triangles": r.triangles, "strips": r.strips,
                "polygons": r.polygons, "width": r.width, "end": r.end,
                "n_refs": len(r.refs),
                "refs_sha1": hashlib.sha1(refs_bytes).hexdigest(),
                "counts": list(r.counts)[:8],
                "counts_sum": sum(r.counts),
                "n_counts": len(r.counts),
                "normal": list(r.normal) if r.normal is not None else None,
            }), flush=True)
        return recs, cands

    def wrapped_strip(data, lo, hi, element_count, elements=None):
        recs, n_hdrs = orig_strip(data, lo, hi, element_count, elements)
        for rec in recs:
            print(json.dumps({"kind": "strip", "offset": rec[0],
                              "marker": rec[1]}), flush=True)
        return recs, n_hdrs

    comp.parse_extended_facet_records = wrapped_ext
    comp.parse_strip_records = wrapped_strip

    from catpart.cli import main_export
    sys.argv = ["catpart-export", path, "-o", "/tmp/w7b-run/dump-py.ply"]
    return main_export()


if __name__ == "__main__":
    sys.exit(main())
