#!/usr/bin/env python3
"""W2 marathon baseline census: the official empty-mesh population.

For every ``empty-mesh`` row of a committed fitness report: export
through the shipped route (the exact committed fallback chain) and
census the B-rep content each file actually carries — located store
spans, pool groups (vertex / edge-curve-entry), facet records by
marker (accepted / unresolved candidates, in-span vs outside), and
``33 3X`` curve records.  Read-only over the corpus; one CSV row per
file, streamed (never more than one part in memory).

Outputs ``docs/evidence/data/w2-empty-mesh-baseline.csv`` (27 columns;
sha16 keys join the fitness report's ``files`` rows) plus a stdout
summary.  ``--selftest`` pins the discriminating edges with synthetic
buffers (no corpus needed): a pool-only store with a 0x42 strip and a
curve-entry-carrying pool are the two populations the loop census must
NOT confuse.

Run::

    .venv/bin/python -I scripts/triage/w2_empty_mesh_census.py \
        fitness/reports/<run>.json [--out docs/evidence/data/...]
    .venv/bin/python -I scripts/triage/w2_empty_mesh_census.py --selftest
"""

import argparse
import collections
import csv
import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from catpart.brep import curves  # noqa: E402
from catpart.geometry import composite, facets, pool, store  # noqa: E402
from catpart.geometry.errors import ExportError  # noqa: E402

COLUMNS = [
    "sha16",
    "split",
    "size_bytes",
    "containers",
    "spans",
    "span_containers",
    "pool_groups",
    "pool_points",
    "edge_groups",
    "composite_space",
    "facet_candidates_in_span",
    "facet_records_in_span",
    "facet_records_42",
    "facet_records_4a",
    "facet_records_4c",
    "facet_records_other",
    "facet_unresolved_in_span",
    "facet_candidates_outside",
    "facet_records_outside",
    "ext_records_in_span",
    "curve_records",
    "line_records",
    "circle_records",
    "vertex_count",
    "triangle_count",
    "warnings",
    "path",
]


def locate_spans(data):
    """Every store span the exporter's probe order locates."""
    size = len(data)
    d8_outer = int.from_bytes(data[8:12], "big") if size >= 12 else 0
    blocks = store.valid_blocks(data)
    named = collections.OrderedDict(
        (
            ("stdcont", "CATStdCont"),
            ("xdoclink", "CATXDocLinkCont"),
            ("seebody", "CATSeeBodyCont"),
            ("other", None),
        )
    )
    spans = []
    for tag, name in named.items():
        for blk, nm in blocks:
            if name is not None and nm != name:
                continue
            if name is None and nm in store.NAMED_PROBE_CONTAINERS:
                continue
            try:
                span = store.locate_store(data, blk, blocks, d8_outer)
            except ExportError:
                continue
            if span is not None:
                spans.append((tag, span.body_lo, span.body_hi))
    return spans


def census_span(data, lo, hi):
    """One store body's pool + facet + extended content census."""
    groups, kinds = pool.scan_pool_groups(data, lo, hi)
    pool_points = sum(len(grp.vertices) for grp in groups)
    edge_groups = sum(1 for k in kinds if k == pool.EDGE_SUBKIND)
    comp = pool.has_composite_space(kinds)
    scan = facets.scan_facets(data, lo, hi)
    by_marker = collections.Counter(rec.marker for rec in scan.records)
    ext, _cands = composite.parse_extended_facet_records(data, lo, hi)
    return {
        "pool_groups": len(groups),
        "pool_points": pool_points,
        "edge_groups": edge_groups,
        "composite_space": comp,
        "candidates": scan.candidates,
        "records": len(scan.records),
        "by_marker": by_marker,
        "unresolved": scan.unresolved_candidates,
        "ext_records": len(ext),
    }


def census_file(path):
    """One part's full census row (read-only; nothing raises)."""
    with open(path, "rb") as fh:
        data = fh.read()
    size = len(data)
    blocks = store.valid_blocks(data)
    containers = ",".join(nm for _b, nm in blocks)
    spans = locate_spans(data)

    agg = {
        "pool_groups": 0,
        "pool_points": 0,
        "edge_groups": 0,
        "composite_space": False,
        "candidates_in": 0,
        "records_in": 0,
        "unresolved_in": 0,
        "ext_records": 0,
        "candidates_out": 0,
        "records_out": 0,
    }
    by_marker = collections.Counter()
    span_lo_hi = [(lo, hi) for _t, lo, hi in spans]
    for _tag, lo, hi in spans:
        c = census_span(data, lo, hi)
        agg["pool_groups"] += c["pool_groups"]
        agg["pool_points"] += c["pool_points"]
        agg["edge_groups"] += c["edge_groups"]
        agg["composite_space"] = agg["composite_space"] or c["composite_space"]
        agg["candidates_in"] += c["candidates"]
        agg["records_in"] += c["records"]
        agg["unresolved_in"] += c["unresolved"]
        agg["ext_records"] += c["ext_records"]
        by_marker.update(c["by_marker"])

    # Outside the located spans: same STRIP_RE discovery, whole-file minus
    # the span bytes (the exporter already trusted the spans).
    outside_marks = sorted(
        (m.start(), data[m.start() + 1])
        for m in facets.STRIP_RE.finditer(data, 0, size)
        if not any(lo <= m.start() < hi for lo, hi in span_lo_hi)
    )
    agg["candidates_out"] = len(outside_marks)
    agg["records_out"] = sum(1 for _o, _mk in outside_marks)

    curve = collections.Counter()
    for lo, hi in span_lo_hi:
        for record in curves.iter_curve_records(data, lo, hi):
            curve[record.family] += 1

    return {
        "size_bytes": size,
        "containers": containers,
        "spans": len(spans),
        "span_containers": ",".join(t for t, _l, _h in spans),
        "pool_groups": agg["pool_groups"],
        "pool_points": agg["pool_points"],
        "edge_groups": agg["edge_groups"],
        "composite_space": agg["composite_space"],
        "facet_candidates_in_span": agg["candidates_in"],
        "facet_records_in_span": agg["records_in"],
        "facet_records_42": by_marker[0x42],
        "facet_records_4a": by_marker[0x4A],
        "facet_records_4c": by_marker[0x4C],
        "facet_records_other": sum(
            n for mk, n in by_marker.items() if mk not in (0x42, 0x4A, 0x4C)
        ),
        "facet_unresolved_in_span": agg["unresolved_in"],
        "facet_candidates_outside": agg["candidates_out"],
        "facet_records_outside": agg["records_out"],
        "ext_records_in_span": agg["ext_records"],
        "curve_records": sum(curve.values()),
        "line_records": curve[0x32],
        "circle_records": curve[0x37],
    }


def export_row(path):
    """The shipped export route's counts + warning classes."""
    from catpart.geometry import export

    with open(path, "rb") as fh:
        data = fh.read()
    try:
        summary, _v, _t = export._export_data(data)
        warns = ",".join(w["class"] for w in summary.get("warnings", []))
        return summary.get("vertex_count"), summary.get("triangle_count"), warns
    except ExportError as exc:
        return None, None, f"export-error:{exc.klass}"
    except Exception as exc:  # noqa: BLE001 — census must not die on one file
        return None, None, f"census-exception:{type(exc).__name__}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("report", nargs="?", help="fitness report JSON to read")
    ap.add_argument("--out", default=os.path.join(
        ROOT, "docs", "evidence", "data", "w2-empty-mesh-baseline.csv"))
    ap.add_argument("--corpus-root", default=os.path.join(
        os.path.dirname(ROOT), "catpart-parser"))
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()

    with open(args.report) as fh:
        report = json.load(fh)
    rows = [
        f
        for f in report["files"]
        if f.get("l2") and f["l2"].get("failed_check") == "empty-mesh"
    ]
    manifest = {}
    with open(os.path.join(ROOT, "manifests", "corpus-manifest.csv"), newline="") as fh:
        for r in csv.DictReader(fh):
            manifest.setdefault(r["sha256"], r["local_path"])

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=COLUMNS)
        wr.writeheader()
        for f in rows:
            local = manifest.get(f["sha256"])
            if not local:
                continue
            path = os.path.join(args.corpus_root, local)
            row = {
                "sha16": f["sha256"][:16],
                "split": f["split"],
                "path": local,
            }
            row.update(census_file(path))
            vc, tc, warns = export_row(path)
            row["vertex_count"] = vc
            row["triangle_count"] = tc
            row["warnings"] = warns
            wr.writerow(row)
            fh.flush()
            print(
                row["sha16"],
                row["spans"],
                row["pool_points"],
                row["facet_records_42"],
                row["triangle_count"],
                local[-46:],
                flush=True,
            )
    print(f"wrote {args.out}")
    return 0


def selftest():
    """Synthetic pins for the two populations the census must not confuse."""
    # A minimal vertex pool group (kind 01 06) + one 0x42 strip record.
    pool_bytes = bytearray(pool.FULL_WRAP)
    pool_bytes += bytes((0x01, 0x06, 4))
    for p in [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]:
        pool_bytes += bytes((0x05, 0x08, 0x01)) + struct.pack("<3f", *p)
    # one 0x42 record: ty=1 loop of 3 refs, u8 width
    rec = b"\x01\x42\x01\xff" + struct.pack("<I", 3) + bytes([3]) + bytes([3, 0, 0])
    buf = bytes(pool_bytes) + rec
    span = census_span(buf, 0, len(buf))
    assert span["pool_points"] == 4, span
    assert span["by_marker"][0x42] == 1, span
    assert span["composite_space"] is False, span
    # An edge-curve-entry pool group (kind 01 02) carries NO vertex points.
    edge_bytes = bytearray(pool.FULL_WRAP)
    edge_bytes += bytes((0x01, 0x02, 0x02))
    edge_bytes += bytes((0x05, 0x08, 0x01)) + struct.pack("<3f", 1.0, 2.0, 3.0)
    edge_bytes += bytes((0x05, 0x08, 0x01)) + struct.pack("<3f", 4.0, 5.0, 6.0)
    span2 = census_span(bytes(edge_bytes) + rec, 0, len(edge_bytes) + len(rec))
    assert span2["edge_groups"] == 1, span2
    assert span2["pool_points"] == 0, span2
    assert span2["composite_space"] is True, span2
    assert span2["by_marker"][0x42] == 1, span2
    print("selftest ok")
    return 0


def census_file_from_buffer(data):
    """census_file over an in-memory buffer (selftest helper)."""
    size = len(data)
    blocks = store.valid_blocks(data)
    spans = locate_spans(data)
    span_lo_hi = [(lo, hi) for _t, lo, hi in spans]
    by_marker = collections.Counter()
    pool_points = 0
    edge_groups = 0
    comp = False
    cands_in = 0
    records_in = 0
    unresolved_in = 0
    ext_records = 0
    for _tag, lo, hi in spans:
        c = census_span(data, lo, hi)
        pool_points += c["pool_points"]
        edge_groups += c["edge_groups"]
        comp = comp or c["composite_space"]
        cands_in += c["candidates"]
        records_in += c["records"]
        unresolved_in += c["unresolved"]
        ext_records += c["ext_records"]
        by_marker.update(c["by_marker"])
    outside = [
        (m.start(), data[m.start() + 1])
        for m in facets.STRIP_RE.finditer(data, 0, size)
        if not any(lo <= m.start() < hi for lo, hi in span_lo_hi)
    ]
    curve = collections.Counter()
    for lo, hi in span_lo_hi:
        for record in curves.iter_curve_records(data, lo, hi):
            curve[record.family] += 1
    return {
        "size_bytes": size,
        "containers": ",".join(nm for _b, nm in blocks),
        "spans": len(spans),
        "span_containers": ",".join(t for t, _l, _h in spans),
        "pool_groups": pool_points > 0 or edge_groups > 0,
        "pool_points": pool_points,
        "edge_groups": edge_groups,
        "composite_space": comp,
        "facet_candidates_in_span": cands_in,
        "facet_records_in_span": records_in,
        "facet_records_42": by_marker[0x42],
        "facet_records_4a": by_marker[0x4A],
        "facet_records_4c": by_marker[0x4C],
        "facet_records_other": sum(
            n for mk, n in by_marker.items() if mk not in (0x42, 0x4A, 0x4C)
        ),
        "facet_unresolved_in_span": unresolved_in,
        "facet_candidates_outside": len(outside),
        "facet_records_outside": sum(1 for _o, _mk in outside),
        "ext_records_in_span": ext_records,
        "curve_records": sum(curve.values()),
        "line_records": curve[0x32],
        "circle_records": curve[0x37],
    }


if __name__ == "__main__":
    sys.exit(main())
