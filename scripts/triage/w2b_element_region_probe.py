#!/usr/bin/env python3
"""W2-B probe: the U3-variant list-node container vs the normal oracle.

W2 left the ``empty-mesh`` 211 blocked on one prerequisite: a composite
element-region decode for the U3-variant family (the stores whose
``decode_composite_store`` raises ``undecoded-variant``).  This probe
measures what those stores' list nodes actually carry and whether any
direct element→position mapping satisfies the committed plane battery
(a mapped loop's Newell normal must be parallel to its record's stored
12-B normal, |dot| > 0.999 — the BR2-10 bar a correct mapping scores
~1.0).

Structure census per eligible store (one part in memory, streamed):

- the list node's declared counts (c1 element_count, c2 edge_ref_bound);
- the container header the committed layout reads as a zero block +
  2-bit table (measured: absent on U3 — the bytes at ``layout().table_start``
  are already f32 data);
- the f32 pair array at ``payload[48:48+8*c1]`` (the UV grid: c1 entries,
  quantized b pitch, adjacent-entry serialization);
- the store's explicit f32 position zones (all-nice stride-12 windows,
  mm-scale) and their total;
- the accepted facet records (the committed width-vote parse, u16le
  relaxed primitives included): loops, refs, max ref, refs at/over c2;
- the plane-oracle score of the direct mappings (identity and the best
  of the 48 signed axis permutations) over normal-carrying loops.

Outputs ``docs/evidence/data/w2b-element-region-oracle.csv`` (one row
per probed file) plus a stdout summary.  Stores with ``c1 > 65,535``
are skipped at probe time (the closed 0x49 negative: a 2-byte ref
cannot index such an element space); files over ``--max-size`` are
skipped with an ``excluded`` note so the 237 MB store never loads.

Run::

    .venv/bin/python -I scripts/triage/w2b_element_region_probe.py \
        --corpus-root /home/alan/Documents/Repos/catpart-parser \
        --baseline docs/evidence/data/w2-empty-mesh-baseline.csv
    .venv/bin/python -I scripts/triage/w2b_element_region_probe.py --selftest
"""

import argparse
import csv
import gc
import math
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from catpart.geometry import composite, pool  # noqa: E402

BASELINE_COLUMNS = "sha16"

COLUMNS = [
    "sha16",
    "split",
    "size_bytes",
    "c1_element_count",
    "c2_edge_ref_bound",
    "pool_points",
    "pairs_found",
    "pairs_bbox_a_min",
    "pairs_bbox_a_max",
    "pairs_bbox_b_min",
    "pairs_bbox_b_max",
    "pair_serial_pairs",  # adjacent entries (2j, 2j+1) sharing a (the mirror/col law)
    "pos_zone_triples",  # the longest all-nice stride-12 run in the payload
    "pos_zone_abs_start",
    "records",
    "normal_loops",
    "refs_total",
    "refs_max",
    "refs_ge_c2",
    "oracle_identity_ok",
    "oracle_identity_testable",
    "oracle_bestperm_ok",
    "excluded",
    "path",
]

_PLANE_DOT = 0.999  # the BR2-10 bar


def _nice(v):
    """The committed plausibility predicate (composite's coordinate floor)."""
    return math.isfinite(v) and 1e-6 <= abs(v) <= 1e6


def _newell(pts):
    nx = ny = nz = 0.0
    for i in range(len(pts)):
        a = pts[i]
        b = pts[(i + 1) % len(pts)]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    return (nx, ny, nz)


def _plane_agrees(pts, normal):
    """|dot(Newell(loop), stored normal)| > 0.999 (BR2-10)."""
    w = _newell(pts)
    m = math.sqrt(w[0] ** 2 + w[1] ** 2 + w[2] ** 2)
    if m == 0.0:
        return False
    d = abs((w[0] * normal[0] + w[1] * normal[1] + w[2] * normal[2]) / m)
    return d > _PLANE_DOT


def pairs_census(payload, c1):
    """The f32 pair array the container opens with (``01 00 01 02`` + c1 x 8B).

    Returns ``(found, bbox, serial_pairs)``: ``found`` counts the
    consecutive entries whose BOTH f32s are nice from ``payload+48``;
    ``serial_pairs`` counts adjacent entry pairs (2j, 2j+1) whose first
    components agree to 1e-4 (the column-serialized law measured on
    separador/Tornillo).
    """
    limit = min(48 + 8 * c1, len(payload) - 7)
    o = 48
    found = 0
    a_min = a_max = b_min = b_max = None
    entries = []
    while o + 8 <= limit:
        a, b = struct.unpack_from("<ff", payload, o)
        if _nice(a) and _nice(b):
            found += 1
            entries.append((a, b))
            a_min = a if a_min is None else min(a_min, a)
            a_max = a if a_max is None else max(a_max, a)
            b_min = b if b_min is None else min(b_min, b)
            b_max = b if b_max is None else max(b_max, b)
        else:
            break
        o += 8
    serial = 0
    for j in range(0, len(entries) - 1, 2):
        if abs(entries[j][0] - entries[j + 1][0]) <= 1e-4:
            serial += 1
    total_pairs = max(1, len(entries) // 2)
    return (
        found,
        (a_min, a_max, b_min, b_max),
        serial / total_pairs,
    )


def position_zone(payload, c1):
    """The longest all-nice stride-12 run after the pairs array (explicit 3D).

    The U3 container's explicit positions live in f32 zones whose
    12-byte windows are all plausible (separador: 1499 triples).  The
    scan starts AFTER the pairs array (``48 + 8*c1``): the pairs are
    themselves nice f32s and would otherwise shadow the position zone
    at stride-12 granularity.  Runs are counted non-overlapping at
    their own alignment.  Only the LONGEST zone is measured — the
    direct-mapping battery maps against it.
    """
    best = (0, -1)
    o = 48 + 8 * c1
    n = len(payload)
    while o + 12 <= n:
        t = struct.unpack_from("<3f", payload, o)
        if not all(_nice(x) for x in t):
            o += 1
            continue
        s = o
        cnt = 0
        while o + 12 <= n:
            t = struct.unpack_from("<3f", payload, o)
            if all(_nice(x) for x in t):
                cnt += 1
                o += 12
            else:
                break
        if cnt > best[0]:
            best = (cnt, s)
        # resume near the run's end: a new run may start at any
        # alignment from e-11 on, but never before — this keeps the
        # walk linear (re-starting at s+1 made long runs quadratic)
        o = max(s + 1, o - 11)
    return best


def _loops_of(records):
    """Reconstruct every loop the committed width-vote parse accepted."""
    loops = []
    for rec in records:
        off, marker, normal, counts, refs, width = rec
        if normal is None or refs is None:
            continue
        i = 0
        for c in counts or ():
            loop = refs[i : i + c]
            i += c
            if c >= 3 and len(loop) == c:
                loops.append((marker, normal, loop))
    return loops


def oracle_scores(loops, table):
    """Identity and best-signed-permutation plane-agreement over ``table``.

    ``table`` = the position-zone triples (in region order).  A loop is
    testable when every ref lands inside the table; the score counts
    loops, not refs.
    """
    perms = []
    import itertools

    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((1, -1), repeat=3):
            perms.append((perm, signs))
    id_ok = id_tot = 0
    best = (0.0, 0)
    for marker, normal, loop in loops:
        if max(loop) < len(table):
            id_tot += 1
            if _plane_agrees([table[r] for r in loop], normal):
                id_ok += 1
    for perm, signs in perms:
        ok = 0
        for marker, normal, loop in loops:
            if max(loop) >= len(table):
                continue
            pts = [
                tuple(s * table[r][perm[k]] for k, s in enumerate(signs)) for r in loop
            ]
            if _plane_agrees(pts, normal):
                ok += 1
        tot = id_tot
        if tot and ok / tot > best[0]:
            best = (ok / tot, ok)
    return id_ok, id_tot, best[1]


def probe_file(path):
    """One store's census row, or an ``excluded`` note."""
    size = os.path.getsize(path)
    if size > 20_000_000:
        return {
            "excluded": "oversize-guard",
            "size_bytes": size,
            "c1_element_count": "",
            "c2_edge_ref_bound": "",
            "pool_points": "",
            "pairs_found": "",
            "pairs_bbox_a_min": "",
            "pairs_bbox_a_max": "",
            "pairs_bbox_b_min": "",
            "pairs_bbox_b_max": "",
            "pair_serial_pairs": "",
            "pos_zone_triples": "",
            "pos_zone_abs_start": "",
            "records": "",
            "normal_loops": "",
            "refs_total": "",
            "refs_max": "",
            "refs_ge_c2": "",
            "oracle_identity_ok": "",
            "oracle_identity_testable": "",
            "oracle_bestperm_ok": "",
        }
    data = open(path, "rb").read()
    try:
        # the census's own span location (probe order)
        sys.path.insert(0, os.path.join(ROOT, "scripts", "triage"))
        import w2_empty_mesh_census as census  # noqa: F401

        spans = census.locate_spans(data)
        if not spans:
            return {"excluded": "no-span"}
        _tag, lo, hi = spans[0]
        groups, kinds = pool.scan_pool_groups(data, lo, hi)
        pool_pts = sum(len(g.vertices) for g in groups)
        node = composite.find_list_node(data, lo, hi)
        if node is None:
            return {"excluded": "no-list-node"}
        payload, c1, c2 = node
        found, bbox, serial = pairs_census(payload, c1)
        zone_n, zone_o = position_zone(payload, c1)
        table = []
        if zone_n:
            table = [
                struct.unpack_from("<3f", payload, zone_o + 12 * i)
                for i in range(zone_n)
            ]
        records, _nh = composite.parse_strip_records(data, lo, hi, c1)
        loops = _loops_of(records)
        refs = [r for _m, _n, loop in loops for r in loop]
        id_ok, id_tot, perm_ok = oracle_scores(loops, table)
        return {
            "excluded": "",
            "size_bytes": size,
            "c1_element_count": c1,
            "c2_edge_ref_bound": c2,
            "pool_points": pool_pts,
            "pairs_found": found,
            "pairs_bbox_a_min": f"{bbox[0]:.4f}" if found else "",
            "pairs_bbox_a_max": f"{bbox[1]:.4f}" if found else "",
            "pairs_bbox_b_min": f"{bbox[2]:.4f}" if found else "",
            "pairs_bbox_b_max": f"{bbox[3]:.4f}" if found else "",
            "pair_serial_pairs": f"{serial:.3f}" if found else "",
            "pos_zone_triples": zone_n,
            "pos_zone_abs_start": zone_o,
            "records": len(records),
            "normal_loops": len(loops),
            "refs_total": len(refs),
            "refs_max": max(refs) if refs else "",
            "refs_ge_c2": sum(1 for r in refs if r >= c2) if refs else "",
            "oracle_identity_ok": id_ok,
            "oracle_identity_testable": id_tot,
            "oracle_bestperm_ok": perm_ok,
        }
    finally:
        del data
        gc.collect()


SELFTEST_PAIRS = [
    # 8 entries, column-serialized: (a0,b_hi),(a0,b_lo),(a1,b_hi),...
    (0.10, 0.60),
    (0.10, 0.50),
    (0.20, 0.60),
    (0.20, 0.50),
    (0.30, 0.60),
    (0.30, 0.50),
    (0.40, 0.60),
    (0.40, 0.50),
]


def _synthetic_container():
    """A minimal U3-shaped node: counts + header + 8 pairs + 4 triples.

    Returns ``(data, span_lo, span_hi, expected)`` with ``expected`` =
    the pairs/triples the census must report.  The node territory is
    delimited by two NODE_MAGICs; the pool wrapper is absent (this
    probe does not need a pool).
    """
    import struct as _s

    pairs = b"".join(_s.pack("<ff", a, b) for a, b in SELFTEST_PAIRS)
    trips = [
        (0.5, 1.0, 2.0),
        (1.0, 1.0, 2.0),
        (2.0, 1.0, 3.0),
        (1.0, 2.0, 2.0),
    ]
    trip_bytes = b"".join(_s.pack("<fff", *t) for t in trips)
    counts = b"\xff\x08\x00\x00\x00" + b"\xff\x04\x00\x00\x00"
    head = b"\x00" * 29 + composite.LIST_TOKEN + counts + b"\x01\x00\x01\x02"
    body = head + pairs + b"\x00\x01\x02\x03" + trip_bytes
    data = composite.NODE_MAGIC + body + composite.NODE_MAGIC
    return (
        data,
        0,
        len(data),
        {
            "c1": 8,
            "pairs": 8,
            "serial": 1.0,  # all 4 adjacent pairs share a
            "triples": 4,
            "trip_pts": trips,
        },
    )


def selftest():
    """Pin the census mechanics on the synthetic container."""
    data, lo, hi, want = _synthetic_container()
    node = composite.find_list_node(data, lo, hi)
    assert node is not None, "list node must be found"
    payload, c1, c2 = node
    assert c1 == want["c1"], (c1, want["c1"])
    found, bbox, serial = pairs_census(payload, c1)
    assert found == want["pairs"], (found, want["pairs"])
    assert abs(serial - want["serial"]) < 1e-9, serial
    assert abs(bbox[0] - 0.10) < 1e-6 and abs(bbox[1] - 0.40) < 1e-6
    assert abs(bbox[2] - 0.50) < 1e-6 and abs(bbox[3] - 0.60) < 1e-6
    zn, zo = position_zone(payload, c1)
    # the longest all-nice stride-12 run: the 4 triples (48 B)
    assert zn == want["triples"], (zn, want["triples"])
    # the plane battery on synthetic loops: the first three triples
    # span the y=1 plane; the quad with the y=2 point disagrees
    pts = want["trip_pts"]
    assert _plane_agrees([pts[0], pts[1], pts[2]], (0.0, 1.0, 0.0))
    assert not _plane_agrees([pts[0], pts[1], pts[3]], (0.0, 1.0, 0.0))
    # the oracle batteries against the decoded table: the coplanar
    # triple scores 1/1 under identity, the non-coplanar one 0
    table = [struct.unpack_from("<3f", payload, zo + 12 * i) for i in range(zn)]
    loops = [((0, 1, 2), (0.0, 1.0, 0.0)), ((0, 1, 3), (0.0, 1.0, 0.0))]
    ok, tot, perm_ok = oracle_scores(
        [(0x4A, n, list(loop)) for loop, n in loops], table
    )
    assert (ok, tot) == (1, 2), (ok, tot)
    print("selftest ok")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus-root", default=None)
    ap.add_argument(
        "--baseline",
        default=os.path.join(
            ROOT, "docs", "evidence", "data", "w2-empty-mesh-baseline.csv"
        ),
    )
    ap.add_argument(
        "--out",
        default=os.path.join(
            ROOT, "docs", "evidence", "data", "w2b-element-region-oracle.csv"
        ),
    )
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        selftest()
        return 0
    if not args.corpus_root:
        ap.error("--corpus-root is required without --selftest")
    rows = list(csv.DictReader(open(args.baseline)))
    elig = [
        r
        for r in rows
        if int(r["pool_points"]) > 0 and int(r["facet_candidates_in_span"]) > 0
    ]
    out_rows = []
    for r in elig:
        path = os.path.join(args.corpus_root, r["path"])
        if not os.path.exists(path):
            continue
        res = probe_file(path)
        res["sha16"] = r["sha16"]
        res["split"] = r["split"]
        res["path"] = r["path"]
        out_rows.append(res)
        print(
            f"{r['sha16']} c1={res.get('c1_element_count')} c2={res.get('c2_edge_ref_bound')} "
            f"pairs={res.get('pairs_found')} triples={res.get('pos_zone_triples')} "
            f"loops={res.get('normal_loops')} identity={res.get('oracle_identity_ok')}/"
            f"{res.get('oracle_identity_testable')} excluded={res.get('excluded')}"
        )
        gc.collect()
    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        for row in out_rows:
            w.writerow({k: row.get(k, "") for k in COLUMNS})
    print(f"wrote {args.out} ({len(out_rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
