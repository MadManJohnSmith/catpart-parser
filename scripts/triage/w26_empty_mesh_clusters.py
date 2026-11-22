#!/usr/bin/env python3
"""W26 (Bloque B6): structural clustering of the official empty-mesh population.

For every ``empty-mesh`` row of a committed fitness report: read the file
once (streamed, one part in memory) and derive a stable binary signature
exactly as the brief defines it —

1. writer version (the fitness row's ``detected_version``, joined — a
   re-detect cannot split a structural cluster),
2. the container table (``store.valid_blocks``, canonical sorted tuple),
3. the store/CATCGM shape (located span tags, pool presence, composite
   index space, in-span facet carriers, outside candidates),
4. the record opcodes (facet strip markers, curve families, the W13
   ``d2 d2`` sibling family and the ``30 04`` filler family — presence
   with coarse magnitude buckets, so one big file cannot split a class).

Clusters are exact signature matches.  Two CSVs land in
``docs/evidence/data/``: ``w26-empty-mesh-clusters.csv`` (one row per
file, signature parts + cluster id) and ``w26-cluster-ranks.csv`` (one
row per cluster, ranked by ``files x bytes`` with carrier classes and
the W2b U3-variant flag).  Read-only over the corpus; no runtime module
is touched.

``--selftest`` pins the signature mechanics on synthetic buffers (no
corpus needed): the bucket law, the carrier-class vocabulary, and the
W13 family counters.

Run::

    .venv/bin/python -I scripts/triage/w26_empty_mesh_clusters.py \
        fitness/reports/<run>.json [--out docs/evidence/data/...]
    .venv/bin/python -I scripts/triage/w26_empty_mesh_clusters.py --selftest
"""

import argparse
import collections
import csv
import gc
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from catpart.brep import curves  # noqa: E402
from catpart.geometry import composite, facets, pool, store  # noqa: E402
from catpart.geometry.errors import ExportError  # noqa: E402

CLUSTERS_CSV = os.path.join(
    ROOT, "docs", "evidence", "data", "w26-empty-mesh-clusters.csv"
)
RANKS_CSV = os.path.join(ROOT, "docs", "evidence", "data", "w26-cluster-ranks.csv")

#: The W2b element-region oracle's eligible stores (the U3-variant
#: composite family whose mapping is refuted measured-negative; the
#: brief says a top cluster matching it is skipped and documented).
U3_ORACLE_CSV = os.path.join(
    ROOT, "docs", "evidence", "data", "w2b-element-region-oracle.csv"
)
#: The W13 sweep's per-sha16 zone (no-hits / between-spans-only / in-span).
W13_SWEEP_CSV = os.path.join(
    ROOT, "docs", "evidence", "data", "w13-empty-mesh-sweep.csv"
)

FILE_COLUMNS = [
    "sha16",
    "split",
    "version",
    "cluster_id",
    "size_bytes",
    "container_table",
    "span_tags",
    "pool_groups",
    "pool_points",
    "composite_space",
    "facet_candidates_in",
    "facet_records_in",
    "facet_records_42",
    "facet_records_4a",
    "facet_records_4c",
    "facet_unresolved_in",
    "ext_records_in",
    "facet_candidates_out",
    "curve_records",
    "line_records",
    "circle_records",
    "d2d2_50_51_hits",
    "f3004_hits",
    "carrier_class",
    "u3_variant",
    "w13_class",
    "sig_hash",
    "path",
]

RANK_COLUMNS = [
    "rank",
    "cluster_id",
    "files",
    "total_bytes",
    "files_x_bytes",
    "version",
    "container_table",
    "span_tags",
    "sig_hash",
    "carrier_class",
    "u3_variant",
    "zero_carrier",
    "w13_classes",
    "pool_points_total",
    "facet_candidates_in_total",
    "facet_records_in_total",
    "curve_records_total",
    "candidates_out_total",
    "example_sha16",
    "example_path",
]

#: The W13 sibling flags (0x52 was measured absent corpus-wide, W13-01).
D2D2_SIBLINGS = (b"\xd2\xd2\x50", b"\xd2\xd2\x51")
#: The W13 filler-family core census (the committed W13 PATTERN).
F3004_RE = re.compile(rb"\x30\x04(.)\xff\xff\xff\xd2\xd2(.)")


def locate_spans(data):
    """Every store span the exporter's probe order locates (W2 census)."""
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


def bucket(n):
    """Coarse magnitude bucket: 0 / 1-99 / 100-9999 / >=10000."""
    if n == 0:
        return "0"
    if n < 100:
        return "1-99"
    if n < 10000:
        return "100-9999"
    return ">=10000"


def d2d2_hits(data):
    """The W13 sibling census: ``d2 d2 <flag>`` with flag in {0x50,0x51}."""
    return sum(data.count(marker) for marker in D2D2_SIBLINGS)


def f3004_hits(data):
    """The W13 filler family: ``30 04 <b2> ff ff ff d2 d2 <flag>`` cores."""
    return sum(1 for _m in F3004_RE.finditer(data))


def carrier_class(agg, by_marker, curve):
    """The carrier vocabulary: what content a file actually carries.

    - ``pool+facet``: pool points AND accepted in-span facet records
      (the composite U3-variant population of W2/W2b).
    - ``pool-only``: pool points, no accepted facet record.
    - ``facet-only``: in-span facet candidates/records, no pool.
    - ``outside-only``: strip candidates outside the located spans,
      nothing in-span.
    - ``curves-only``: curve records in-span, no pool/facet content.
    - ``zero-carrier``: none of the above (the W11-style structural
      floor: nothing any committed law could pair or walk).
    """
    has_pool = agg["pool_points"] > 0
    has_records = agg["records_in"] > 0
    has_cands_in = agg["candidates_in"] > 0
    has_out = agg["candidates_out"] > 0
    has_curves = sum(curve.values()) > 0
    if has_pool and has_records:
        return "pool+facet"
    if has_pool:
        return "pool-only"
    if has_records or has_cands_in:
        return "facet-only"
    if has_out:
        return "outside-only"
    if has_curves:
        return "curves-only"
    return "zero-carrier"


def sig_hash_of(parts):
    """Deterministic 6-hex signature id (hashlib — never salted hash())."""
    digest = hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()
    return "sig-" + digest[:6]


def census_file(path):
    """One part's full signature row (read-only; nothing raises).

    Byte-pattern families are counted whole-file with single streaming
    regex passes (the W13 family census); the store-content families use
    the committed probes over the located spans only.
    """
    with open(path, "rb") as fh:
        data = fh.read()
    size = len(data)
    blocks = store.valid_blocks(data)
    container_table = tuple(sorted(nm for _b, nm in blocks))
    spans = locate_spans(data)
    span_tags = tuple(t for t, _lo, _hi in spans)
    span_lo_hi = [(lo, hi) for _t, lo, hi in spans]

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
    }
    by_marker = collections.Counter()
    for _tag, lo, hi in spans:
        groups, kinds = pool.scan_pool_groups(data, lo, hi)
        agg["pool_groups"] += len(groups)
        agg["pool_points"] += sum(len(grp.vertices) for grp in groups)
        agg["edge_groups"] += sum(1 for k in kinds if k == pool.EDGE_SUBKIND)
        agg["composite_space"] = agg["composite_space"] or pool.has_composite_space(kinds)
        scan = facets.scan_facets(data, lo, hi)
        agg["candidates_in"] += scan.candidates
        agg["records_in"] += len(scan.records)
        agg["unresolved_in"] += scan.unresolved_candidates
        by_marker.update(rec.marker for rec in scan.records)
        ext, _cands = composite.parse_extended_facet_records(data, lo, hi)
        agg["ext_records"] += len(ext)

    outside = [
        (m.start(), data[m.start() + 1])
        for m in facets.STRIP_RE.finditer(data, 0, size)
        if not any(lo <= m.start() < hi for lo, hi in span_lo_hi)
    ]
    agg["candidates_out"] = len(outside)

    curve = collections.Counter()
    for lo, hi in span_lo_hi:
        for record in curves.iter_curve_records(data, lo, hi):
            curve[record.family] += 1

    # The W13 families, whole-file (their census scope).
    d2d2 = d2d2_hits(data)
    f3004 = f3004_hits(data)

    sig_parts = (
        str(len(blocks)),
        repr(container_table),
        repr(span_tags),
        "comp" if agg["composite_space"] else "lin",
        bucket(agg["pool_points"]),
        bucket(agg["candidates_in"]),
        bucket(agg["records_in"]),
        bucket(by_marker.get(0x42, 0)),
        bucket(by_marker.get(0x4A, 0)),
        bucket(by_marker.get(0x4C, 0)),
        bucket(agg["candidates_out"]),
        bucket(sum(curve.values())),
        "d2d2" if d2d2 else "",
        "f3004" if f3004 else "",
    )

    return {
        "size_bytes": size,
        "container_table": ",".join(container_table),
        "span_tags": ",".join(span_tags),
        "pool_groups": agg["pool_groups"],
        "pool_points": agg["pool_points"],
        "composite_space": agg["composite_space"],
        "facet_candidates_in": agg["candidates_in"],
        "facet_records_in": agg["records_in"],
        "facet_records_42": by_marker.get(0x42, 0),
        "facet_records_4a": by_marker.get(0x4A, 0),
        "facet_records_4c": by_marker.get(0x4C, 0),
        "facet_unresolved_in": agg["unresolved_in"],
        "ext_records_in": agg["ext_records"],
        "facet_candidates_out": agg["candidates_out"],
        "curve_records": sum(curve.values()),
        "line_records": curve.get(0x32, 0),
        "circle_records": curve.get(0x37, 0),
        "d2d2_50_51_hits": d2d2,
        "f3004_hits": f3004,
        "carrier_class": carrier_class(agg, by_marker, curve),
        "sig_hash": sig_hash_of(sig_parts),
        "sig_parts": sig_parts,
    }


def load_manifest_paths(manifest_path):
    """sha256 -> local_path from the corpus manifest (the W2 join)."""
    with open(manifest_path, newline="") as fh:
        return {r["sha256"]: r["local_path"] for r in csv.DictReader(fh)}


def iter_empty_mesh_rows(report_path, manifest_paths, corpus_root):
    """The report's ``failed_check == 'empty-mesh'`` rows.

    The report's ``path`` is repo-stripped; the on-disk join goes through
    the corpus manifest's ``local_path`` by sha256 (the committed W2
    census join), resolved against ``corpus_root``.
    """
    with open(report_path) as fh:
        report = json.load(fh)
    for row in report["files"]:
        l2 = row.get("l2") or {}
        if l2.get("failed_check") == "empty-mesh":
            local = manifest_paths.get(row["sha256"], "")
            row["disk_path"] = os.path.join(corpus_root, local) if local else ""
            yield row


def load_join_column(csv_path, column):
    """A committed evidence CSV's per-sha16 join column (absent: {})."""
    try:
        with open(csv_path, newline="") as fh:
            return {r["sha16"]: r.get(column, "") for r in csv.DictReader(fh)}
    except OSError:
        return {}


def run(report_path, out_clusters, out_ranks, corpus_root):
    manifest_paths = load_manifest_paths(os.path.join(ROOT, "manifests", "corpus-manifest.csv"))
    u3 = load_join_column(U3_ORACLE_CSV, "sha16")
    w13 = load_join_column(W13_SWEEP_CSV, "zone")
    rows = []
    for report_row in iter_empty_mesh_rows(report_path, manifest_paths, corpus_root):
        sha16 = report_row["sha256"][:16]
        path = report_row["disk_path"]
        if not os.path.isfile(path):
            print(f"missing on disk, skipped: {sha16} {report_row['path']}")
            continue
        sig = census_file(path)
        sig["sha16"] = sha16
        sig["split"] = report_row.get("split", "")
        sig["version"] = report_row.get("detected_version", "")
        sig["u3_variant"] = sha16 in u3
        sig["w13_class"] = w13.get(sha16, "")
        sig["path"] = report_row["path"]
        rows.append(sig)
        gc.collect()

    # Cluster = exact signature match; id = rank-order number.
    clusters = collections.defaultdict(list)
    for row in rows:
        clusters[row["sig_hash"]].append(row)

    ordered = sorted(
        clusters,
        key=lambda s: (
            -(len(clusters[s]) * sum(m["size_bytes"] for m in clusters[s])),
            -len(clusters[s]),
        ),
    )
    file_rows = []
    rank_rows = []
    for idx, sig_hash in enumerate(ordered, start=1):
        members = clusters[sig_hash]
        cid = f"C{idx:02d}"
        for m in members:
            m["cluster_id"] = cid
            file_rows.append(m)
        first = members[0]
        classes = collections.Counter(m["carrier_class"] for m in members)
        rank_rows.append(
            {
                "rank": idx,
                "cluster_id": cid,
                "files": len(members),
                "total_bytes": sum(m["size_bytes"] for m in members),
                "files_x_bytes": len(members) * sum(m["size_bytes"] for m in members),
                "version": ",".join(sorted({m["version"] for m in members})),
                "container_table": first["container_table"],
                "span_tags": first["span_tags"],
                "sig_hash": sig_hash,
                "carrier_class": ",".join(f"{k}:{v}" for k, v in classes.most_common()),
                "u3_variant": all(m["u3_variant"] for m in members),
                "zero_carrier": all(m["carrier_class"] == "zero-carrier" for m in members),
                "w13_classes": ",".join(
                    sorted({m["w13_class"] for m in members if m["w13_class"]})
                ),
                "pool_points_total": sum(m["pool_points"] for m in members),
                "facet_candidates_in_total": sum(m["facet_candidates_in"] for m in members),
                "facet_records_in_total": sum(m["facet_records_in"] for m in members),
                "curve_records_total": sum(m["curve_records"] for m in members),
                "candidates_out_total": sum(m["facet_candidates_out"] for m in members),
                "example_sha16": members[0]["sha16"],
                "example_path": members[0]["path"],
            }
        )

    os.makedirs(os.path.dirname(out_clusters), exist_ok=True)
    with open(out_clusters, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FILE_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in file_rows:
            out = dict(row)
            out["composite_space"] = str(row["composite_space"])
            out["u3_variant"] = str(row["u3_variant"])
            writer.writerow(out)
    with open(out_ranks, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=RANK_COLUMNS)
        writer.writeheader()
        writer.writerows(rank_rows)

    total_bytes = sum(m["size_bytes"] for m in rows)
    print(f"files: {len(rows)}  bytes: {total_bytes}  clusters: {len(ordered)}")
    for r in rank_rows[:12]:
        print(
            f"  {r['cluster_id']} files={r['files']} bytes={r['total_bytes']} "
            f"carriers={r['carrier_class']} u3={r['u3_variant']} "
            f"zero={r['zero_carrier']} ver={r['version']}"
        )
    return rows, rank_rows


# ---------------------------------------------------------------- selftest


def _selftest():
    """Synthetic signature pins (no corpus): the discriminating edges."""
    # bucket law
    assert bucket(0) == "0" and bucket(1) == "1-99"
    assert bucket(99) == "1-99" and bucket(100) == "100-9999"
    assert bucket(9999) == "100-9999" and bucket(10000) == ">=10000"

    # carrier vocabulary edges
    zero = {"pool_points": 0, "records_in": 0, "candidates_in": 0, "candidates_out": 0}
    assert carrier_class(zero, {}, {}) == "zero-carrier"
    poolfacet = dict(zero, pool_points=10, records_in=3)
    assert carrier_class(poolfacet, {0x42: 3}, {}) == "pool+facet"
    poolonly = dict(zero, pool_points=10)
    assert carrier_class(poolonly, {}, {}) == "pool-only"
    facetonly = dict(zero, candidates_in=5)
    assert carrier_class(facetonly, {}, {}) == "facet-only"
    assert carrier_class(
        dict(zero, candidates_out=2), {}, collections.Counter({0x32: 4})
    ) == "outside-only"
    assert carrier_class(zero, {}, collections.Counter({0x32: 4})) == "curves-only"

    # the d2 d2 sibling counter reads the W13 flags only (0x52 absent)
    buf = b"\xd2\xd2\x50" + b"\x00" * 5 + b"\xd2\xd2\x51" + b"\xd2\xd2\x52"
    assert d2d2_hits(buf) == 2

    # the 30 04 filler core counter (W13's PATTERN, 10-byte form)
    buf = b"\x30\x04\x05\xff\xff\xff\xd2\xd2\x04\x04" + b"\x00" * 3
    assert f3004_hits(buf) == 1
    assert f3004_hits(b"\x30\x04\x05\x00\x00\x00\xd2\xd2\x04") == 0

    # sig determinism: same parts -> same id; a different container
    # table -> a different id; magnitude never splits (bucket law)
    base = (
        "3",
        "('A', 'B')",
        "('stdcont',)",
        "lin",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "",
        "",
    )
    assert sig_hash_of(base) == sig_hash_of(base)
    assert sig_hash_of(base) != sig_hash_of((str(4),) + base[1:])
    assert bucket(50) == bucket(75) != bucket(150)

    print("selftest: 6/6 pins green")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("report", nargs="?", help="fitness report JSON to read")
    ap.add_argument("--out", default=CLUSTERS_CSV)
    ap.add_argument("--ranks", default=RANKS_CSV)
    ap.add_argument("--corpus-root", default=ROOT)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        _selftest()
        return 0
    if not args.report:
        ap.error("a fitness report JSON is required (or --selftest)")
    run(args.report, args.out, args.ranks, args.corpus_root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
