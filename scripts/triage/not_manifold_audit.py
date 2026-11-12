#!/usr/bin/env python3
"""The not-manifold composite exports classified (G6 stage 4b, #34).

Stage 3d's identity decode exports 677 composite stores; 29 of them
(28 dev + 1 held-out) fail the runner's manifold check — every other
L2 component passes (non-empty mesh, plausible bbox, degenerates below
the cap; the planarity battery of stage 3b validated their loops).
This script classifies the failure:

1. **Signature**: the undirected edge-degree histogram of each export
   (mesh.mesh_stats only reports `manifold`; the histogram is the
   non-manifold signature) — edges used 3x, 4x, ..., n times, plus
   duplicate-triangle counts (same coordinate triangle exported twice).
2. **Provenance**: every triangle use of every degree->2 edge is
   attributed to its strip record (offset, marker) and loop index —
   inside one loop (strip-internal sharing, legitimate), across loops
   of one record (the strip-join hypothesis), or across records.
3. **The width-law test**: the byte evidence locates the non-manifold
   edge degrees not in strip joins but in the stage-3b WIDTH RANK —
   two gaps measured here:
   - **u24be missing**: a store whose element_count exceeds 65,535
     needs 3-byte big-endian refs; the committed enumeration (u8,
     u16be) misreads those records (13bb5c0c: element_count 236,385;
     the u24be candidate tiles its records exactly — byte-verified).
   - **the narrow-width tiebreak without the plane law**: a record
     whose byte stream carries an interleaved non-``ff``-byte-3
     family never tiles onto the next STRIP_RE header, so both width
     candidates tie on (tiling, repeats, oob) and the narrower wins —
     ef30cb2f rec 261274: the u8 loop is NONPLANAR against the
     record's stored normal, the u16be loop COPLANAR, and the u8 won.
     The re-test adds width 3 and breaks ties by the loop plane law
     (nonplanar normal-carrying loops lose), then re-measures
     manifoldness.

Outputs docs/evidence/data/not-manifold-files.csv (one row per store:
histogram + both test results) and docs/evidence/data/not-manifold-edges.csv
(one row per degree>2 edge use: degree, provenance class, duplicate
flag).  Deterministic: sorted manifest order, the store's record order
fixes every tiebreak.

Read-only over the corpus; the export seam is replayed through the
shipped :func:`catpart.geometry.export._export_data` (no src/ change):

  .venv/bin/python -I scripts/triage/not_manifold_audit.py
  [--include-sha16 HEX16,...]
"""

import argparse
import csv
import mmap
import struct
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"
COMMITTED = OUT_DIR / "identity-export-files.csv"

sys.path.insert(0, str(ROOT / "src"))

from catpart.geometry import mesh  # noqa: E402
from catpart.geometry import export as export_mod  # noqa: E402
from catpart.geometry.errors import ExportError  # noqa: E402
from catpart.geometry import composite  # noqa: E402

FIELDS = [
    "sha256", "split", "vertex_count", "triangle_count",
    "edge_count", "deg1", "deg2", "deg3", "deg4", "deg5plus",
    "max_degree", "excess_uses", "dup_triangles", "deg_edge_uses",
    "uses_same_loop", "uses_cross_loop_same_record",
    "uses_cross_record", "skip_test_manifold", "skip_test_dropped",
    "w3_records", "width_flips", "v2_triangle_count", "v2_manifold",
    "v2_nonmanifold_edges", "residual_class",
]

EDGE_FIELDS = [
    "sha256", "va", "vb", "degree", "use", "record_off", "marker",
    "loop_idx", "loop_len", "tri_idx", "dup_of", "degenerate",
    "prov_class",
]


def _cross_zero(a, b, c):
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    return (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    ) == (0.0, 0.0, 0.0)


def triangulate_with_provenance(elements, records):
    """The shipped ``composite._triangulate`` walk, with provenance.

    Same loop iteration, same degenerate skips, same triangle order;
    each produced triangle carries (record_off, marker, loop_idx,
    tri_idx, loop_len).  Returns (triangles, prov, stats) where
    ``prov[i]`` is the provenance of ``triangles[i]``.
    """
    written_rank = {}
    skips = set()
    for i, (_v, pt) in enumerate(elements):
        if pt is None:
            skips.add(i)
        else:
            written_rank[i] = len(written_rank)
    points = [pt for _v, pt in elements if pt is not None]

    triangles = []
    prov = []
    loops_curve_entry = 0
    for off, mk, _normal, counts, refs, _w in records:
        if mk not in (0x42, 0x4A, 0x4C):
            continue
        loops = []
        o = 0
        for c in counts:
            loops.append(refs[o : o + c])
            o += c
        for li, loop in enumerate(loops):
            if not loop:
                continue
            if any(r in skips for r in loop):
                loops_curve_entry += 1
                continue
            idxs = [written_rank[r] for r in loop]
            lp = [points[i] for i in idxs]
            if mk == 0x4C:
                for t in range(1, len(lp) - 1):
                    tri = (idxs[0], idxs[t], idxs[t + 1])
                    a, b, c = lp[0], lp[t], lp[t + 1]
                    if a == b or b == c or a == c:
                        continue
                    triangles.append(tri)
                    prov.append((off, mk, li, t - 1, len(lp)))
            else:
                for t in range(len(lp) - 2):
                    tri = (idxs[t], idxs[t + 1], idxs[t + 2])
                    if t % 2 == 1:
                        tri = (tri[2], tri[1], tri[0])
                    a, b, c = lp[t], lp[t + 1], lp[t + 2]
                    if a == b or b == c or a == c:
                        continue
                    if _cross_zero(a, b, c):
                        continue
                    triangles.append(tri)
                    prov.append((off, mk, li, t, len(lp)))
    return triangles, prov, loops_curve_entry


def key3(tri, points):
    """Order-independent coordinate key of a triangle."""
    return tuple(sorted((points[tri[0]], points[tri[1]], points[tri[2]])))


def provenance_for(mm, summary):
    """Re-derive the record/element stream the seam decoded (single-rep
    composite stores only — the exported set's shape)."""
    d8_outer = int.from_bytes(mm[8:12], "big") if mm.size() >= 12 else 0
    blocks = export_mod.store.valid_blocks(mm)
    for blk in [b for b, nm in blocks if nm == "CATStdCont"]:
        try:
            span = export_mod.store.locate_store(mm, blk, blocks, d8_outer)
        except ExportError:
            continue
        if span is None:
            continue
        try:
            groups, kinds = export_mod.pool.scan_pool_groups(
                mm, span.body_lo, span.body_hi
            )
        except ExportError:
            continue
        if not export_mod.pool.has_composite_space(kinds):
            continue
        lo, hi = span.body_lo, span.body_hi
        hdrs = [m.start() for m in export_mod.facets.STRIP_RE.finditer(mm, lo, hi)]
        node_hi = hdrs[0] if hdrs else hi
        ln = composite.find_list_node(mm, lo, node_hi)
        if ln is None:
            continue
        payload, elem_decl, _c2 = ln
        elements, info = composite.decode_region(payload, elem_decl)
        records, _n = composite.parse_strip_records(mm, lo, hi, elem_decl)
        return elements, records
    return None, None


# the width re-test: candidate ref widths extended with u24be (element
# counts above 65,535 cannot index in two bytes), and the narrow-width
# tiebreak demoted below the loop plane law (a candidate whose
# normal-carrying loops are nonplanar loses to one that is coplanar —
# the stage-3b battery is the law's validation).  Everything else
# (header law, count enumeration, tiling/no-repeat/oob ranks) is the
# committed :func:`composite.parse_strip_records` enumeration.
WIDTHS = (1, 2, 3)


def _ref(data, pos, width):
    return int.from_bytes(data[pos : pos + width], "big")


def parse_width_test(data, lo, hi, elements, elem_count):
    """The width re-parse: committed enumeration + width 3 + plane tiebreak.

    Returns ``(records, n_hdrs, w3_count, flips)`` where ``flips`` is
    the number of records whose chosen (width, k) differs from the
    committed parse.  Record tuple layout matches the committed parse.
    """
    committed, _nh = composite.parse_strip_records(data, lo, hi, elem_count)
    committed_map = {r[0]: r for r in committed}
    skips = {i for i, (_v, pt) in enumerate(elements) if pt is None}
    hdrs = [m.start() for m in composite.STRIP_RE.finditer(data, lo, hi)]
    out = []
    w3 = 0
    flips = 0
    for i, o in enumerate(hdrs):
        nxt = hdrs[i + 1] if i + 1 < len(hdrs) else hi
        mk = data[o + 1]
        hlen = 4 if data[o + 3] == 0xFF else 5
        if o + hlen + 4 > nxt:
            continue
        n = int.from_bytes(data[o + hlen : o + hlen + 4], "little")
        if not (0 <= n <= 1_000_000):
            continue
        has_normal = mk in composite.NORMAL_MARKERS_ALL
        base = o + hlen + 4 + (12 if has_normal else 0)
        normal = None
        if has_normal:
            if base > hi:
                continue
            normal = struct.unpack("<fff", data[o + hlen + 4 : o + hlen + 16])
        best = None
        for width in WIDTHS:
            for k in range(0, composite.MAX_LOOP_COUNTS + 1):
                if base + k > nxt:
                    break
                counts = [data[base + j] for j in range(k)]
                if sum(counts) != n:
                    continue
                end = base + k + width * n
                if end > nxt:
                    continue
                refs = [_ref(data, base + k + width * j, width) for j in range(n)]
                repeats = False
                off = 0
                for c in counts:
                    loop = refs[off : off + c]
                    if c > 0 and len(set(loop)) < c:
                        repeats = True
                    off += c
                oob = any(r >= elem_count for r in refs)
                nonplanar = 0
                if normal is not None:
                    off = 0
                    for c in counts:
                        loop = refs[off : off + c]
                        off += c
                        if not loop:
                            continue
                        if any(r in skips or r >= len(elements) for r in loop):
                            continue
                        st, _res = _loop_plane_status(loop, normal, elements)
                        if st == "nonplanar":
                            nonplanar += 1
                rank = (
                    0 if end == nxt else 1,
                    1 if repeats else 0,
                    1 if oob else 0,
                    nonplanar,
                    width,
                    k,
                )
                if best is None or rank < best[0]:
                    best = (rank, tuple(counts), tuple(refs), width)
        if best is None:
            continue
        _rank, counts, refs, width = best
        if width == 3:
            w3 += 1
        old = committed_map.get(o)
        if old is None or old[5] != width or old[3] != counts:
            flips += 1
        out.append((o, mk, normal, counts, refs, width))
    return out, len(hdrs), w3, flips


def _loop_plane_status(loop, normal, elements):
    """Coplanarity of one fully-resolved loop (PLANE_TOL as committed)."""
    nn = (normal[0] ** 2 + normal[1] ** 2 + normal[2] ** 2) ** 0.5
    if nn == 0:
        return "nonplanar", 0.0
    pts = [elements[r][1] for r in loop]
    p0 = pts[0]
    for p in pts[1:]:
        d = (
            (p[0] - p0[0]) * normal[0]
            + (p[1] - p0[1]) * normal[1]
            + (p[2] - p0[2]) * normal[2]
        ) / nn
        if abs(d) > 2e-3:
            return "nonplanar", abs(d)
    return "coplanar", 0.0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--include-sha16", default="")
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    args = ap.parse_args()
    # the 29: composite exports whose L2 failed_check is not-manifold
    want = []
    with COMMITTED.open() as fh:
        for r in csv.DictReader(fh):
            if (
                r["l2_status"] == "fail"
                and r["failed_check"] == "not-manifold"
                and r["element_decl"] not in ("", "None")
            ):
                want.append(r["sha256"])
    if args.include_sha16:
        keep = {h for h in args.include_sha16.split(",") if h}
        want = [s for s in want if s[:16] in keep]
    want.sort()
    print(f"not-manifold composite exports: {len(want)}")
    rows = []
    edge_rows = []
    for sha in want:
        rel = manifest_row(sha)
        if rel is None:
            continue
        path = ROOT / rel["local_path"]
        with path.open("rb") as fh:
            mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                row, edges = audit_store(mm, sha, rel)
            finally:
                mm.close()
        if row is None:
            continue
        rows.append(row)
        edge_rows += edges
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fpath = out_dir / "not-manifold-files.csv"
    with fpath.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    epath = out_dir / "not-manifold-edges.csv"
    with epath.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=EDGE_FIELDS)
        w.writeheader()
        w.writerows(edge_rows)
    print(f"wrote {fpath} ({len(rows)} rows)")
    print(f"wrote {epath} ({len(edge_rows)} edge rows)")
    summarize(rows)


def manifest_row(sha):
    for r in csv.DictReader(MANIFEST.open()):
        if r["sha256"] == sha:
            return r
    return None


def audit_store(mm, sha, rel):
    size = mm.size()
    d8_outer = int.from_bytes(mm[8:12], "big") if size >= 12 else 0
    try:
        summary, vertices, triangles = export_mod._export_data(mm)
    except ExportError as exc:
        print(f"  {sha[:16]}: seam replay failed: {exc.error_class}")
        return None, []
    elements, records = provenance_for(mm, summary)
    if elements is None:
        print(f"  {sha[:16]}: provenance replay failed")
        return None, []
    tri2, prov, _lce = triangulate_with_provenance(elements, records)
    if tri2 != [tuple(t) for t in triangles]:
        print(f"  {sha[:16]}: provenance replay MISMATCH vs the seam")
        return None, []
    points = vertices
    # edge histogram with provenance
    edge_uses = {}
    for i, tri in enumerate(tri2):
        for e in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            edge_uses.setdefault(tuple(sorted(e)), []).append(i)
    deg = Counter(len(v) for v in edge_uses.values())
    nm_edges = {e: uses for e, uses in edge_uses.items() if len(uses) > 2}
    # duplicate triangles (same coordinate key)
    seen = {}
    dup_of = {}
    for i, tri in enumerate(tri2):
        k = key3(tri, points)
        if k in seen:
            dup_of[i] = seen[k]
        else:
            seen[k] = i
    # provenance classes per non-manifold edge use
    rec_of = lambda i: prov[i][0]
    loop_of = lambda i: (prov[i][0], prov[i][2])
    e_rows = []
    use_cls = Counter()
    for e, uses in sorted(nm_edges.items()):
        recs = [rec_of(i) for i in uses]
        loops = [loop_of(i) for i in uses]
        for j, i in enumerate(uses):
            if len(set(loops)) == 1:
                cls = "same-loop"
            elif len(set(recs)) == 1:
                cls = "cross-loop-same-record"
            else:
                cls = "cross-record"
            use_cls[cls] += 1
            ri, mk, li, ti, ll = prov[i]
            e_rows.append(
                {
                    "sha256": sha,
                    "va": e[0],
                    "vb": e[1],
                    "degree": len(uses),
                    "use": j,
                    "record_off": ri,
                    "marker": f"0x{mk:02x}",
                    "loop_idx": li,
                    "loop_len": ll,
                    "tri_idx": ti,
                    "dup_of": dup_of.get(i, ""),
                    "degenerate": "",
                    "prov_class": cls,
                }
            )
    # the cross-loop skip test: G3 F7 extended across loop boundaries —
    # a triangle is skipped when (a) it duplicates a triangle an earlier
    # loop already produced (same coordinate key), or (b) one of its
    # edges has already been used twice by OTHER loops' triangles
    # (the join re-emission).  Record order fixes the priority.
    edge_deg = Counter()
    kept = []
    dropped = 0
    seen_keys = set()
    for i, tri in enumerate(tri2):
        k = key3(tri, points)
        es = [tuple(sorted(e)) for e in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0]))]
        if k in seen_keys:
            dropped += 1
            continue
        # join-re-emission rule: an edge already at degree 2 from other
        # loops suppresses the triangle (the shipped skip convention is
        # inside-loop only; this extends it across loops)
        sat = any(edge_deg[e] >= 2 for e in es)
        if sat:
            dropped += 1
            continue
        seen_keys.add(k)
        kept.append(tri)
        for e in es:
            edge_deg[e] += 1
    stats = mesh.mesh_stats(list(kept))
    deg1 = deg.get(1, 0)
    deg2 = deg.get(2, 0)
    excess = sum(len(v) - 2 for v in nm_edges.values())
    row = {
        "sha256": sha,
        "split": rel["split"],
        "vertex_count": summary["vertex_count"],
        "triangle_count": summary["triangle_count"],
        "edge_count": len(edge_uses),
        "deg1": deg1,
        "deg2": deg2,
        "deg3": deg.get(3, 0),
        "deg4": deg.get(4, 0),
        "deg5plus": sum(v for d, v in deg.items() if d >= 5),
        "max_degree": max(deg) if deg else 0,
        "excess_uses": excess,
        "dup_triangles": sum(1 for i in dup_of),
        "deg_edge_uses": sum(len(v) for v in nm_edges.values()),
        "uses_same_loop": use_cls["same-loop"],
        "uses_cross_loop_same_record": use_cls["cross-loop-same-record"],
        "uses_cross_record": use_cls["cross-record"],
        "skip_test_manifold": int(stats.manifold),
        "skip_test_dropped": dropped,
        "residual_class": "",
    }
    # the width re-test: extend the candidate widths with u24be and break
    # the narrow-width ties by the loop plane law, then re-triangulate
    # and re-measure manifoldness.
    d8_outer2 = d8_outer
    blocks = export_mod.store.valid_blocks(mm)
    v2_manifold = ""
    v2_tri = 0
    v2_nm = ""
    w3 = flips = 0
    for blk in [b for b, nm in blocks if nm == "CATStdCont"]:
        try:
            span = export_mod.store.locate_store(mm, blk, blocks, d8_outer2)
        except ExportError:
            continue
        if span is None:
            continue
        lo2, hi2 = span.body_lo, span.body_hi
        try:
            records2, _nh, w3, flips = parse_width_test(
                mm, lo2, hi2, elements, summary["composite"]["element_decl"]
            )
        except Exception:  # noqa: BLE001 - the re-test is best-effort
            break
        tri3, _prov3, _lce3 = triangulate_with_provenance(elements, records2)
        st3 = mesh.mesh_stats(list(tri3))
        deg3 = Counter()
        for t in tri3:
            for e in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                deg3[tuple(sorted(e))] += 1
        v2_manifold = int(st3.manifold)
        v2_tri = len(tri3)
        v2_nm = sum(1 for v in deg3.values() if v > 2)
        break
    row["w3_records"] = w3
    row["width_flips"] = flips
    row["v2_triangle_count"] = v2_tri
    row["v2_manifold"] = v2_manifold
    row["v2_nonmanifold_edges"] = v2_nm
    row["residual_class"] = _residual(row)
    return row, e_rows


def _residual(row):
    """The store's class after both tests."""
    if row["v2_manifold"] == 1:
        return "width-rank artifact (u24be / plane tiebreak resolves)"
    if row["skip_test_manifold"] == 1:
        return "manifold under the cross-loop skip test only"
    return "unresolved"


def summarize(rows):
    n = len(rows)
    if not n:
        return
    print(f"== {n} not-manifold composite exports")
    print(f"   edge-degree totals: deg1 {sum(r['deg1'] for r in rows)}, "
          f"deg2 {sum(r['deg2'] for r in rows)}, deg3 {sum(r['deg3'] for r in rows)}, "
          f"deg4 {sum(r['deg4'] for r in rows)}, deg5+ {sum(r['deg5plus'] for r in rows)}")
    print(f"   stores resolved by the cross-loop skip test: "
          f"{sum(r['skip_test_manifold'] for r in rows)}/{n} "
          f"({sum(r['skip_test_dropped'] for r in rows)} triangles dropped)")
    print(f"   stores resolved by the width re-test: "
          f"{sum(1 for r in rows if r['v2_manifold'] == 1)}/{n}")
    print(f"   u24be records: {sum(r['w3_records'] for r in rows)}; "
          f"width flips: {sum(r['width_flips'] for r in rows)}")
    print(f"   residual classes: {Counter(r['residual_class'] for r in rows)}")
    print(f"   duplicate triangles: {sum(r['dup_triangles'] for r in rows)}")


if __name__ == "__main__":
    sys.exit(main())
