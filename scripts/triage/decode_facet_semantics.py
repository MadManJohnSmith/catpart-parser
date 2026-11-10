#!/usr/bin/env python3
"""Decode the primitive semantics of the nested store's facet records (G3, #31).

Builds on G1's nested-store decode (decode_nested_store.py: store origin,
catalog, body extent) and G2's vertex-pool decode (decode_vertex_pool.py:
pool groups, strip candidates).  Static reads only; no structure is parsed
by the package.

Model (claims F1-F10 in the evidence note
docs/evidence/2026-11-09-facet-semantics.md):

  Facet records.  The connectivity records refine G2's grammar into

      01 <mk> [<ty>] [01] ff [u32le n] [12B f32le normal][k u8 counts][n refs]

  with marker families 0x41-0x4f; markers 0x49/0x4a/0x4c carry a 12-byte
  f32le unit normal; the k count bytes (0..4) sum to n; markers 0x43/0x45/
  0x4b/0x4e use the 5-byte header form (two bytes before ff).  The refs are
  u8 or u16be (big-endian) per record, selected by the tiling law: the
  exact-tiling parse wins, then — on a gap edge of a CLEAN store (no
  `01 02` edge group and no trailer opener, the class where the defect
  was verified) — the store-width context (the widths of the store's
  exact-tile records vote; a unanimous vote wins the tie-break, mixed
  votes or none keep the narrower width, 2026-11-10 correction #35,
  class-bounded 2026-11-10).  Composite stores keep the unconditional
  narrower-width gap behavior.  Records tile the facet region
  header-to-header.

  Index space.  Refs index the store's vertex pool by LEXICOGRAPHIC RANK
  of the coordinates (x, then y, then z), NOT by walk order (correction
  C8): on the clean subset the strip reading under lex ranks reproduces
  the stored normals at 0.993 vs 0.275 under walk order.  On stores that
  also carry an `01 02` edge group and/or a `10 24 ... ff` trailer opener
  the refs run beyond the pool (composite index space, F8/open).

  Primitive semantics (per loop; the k count bytes delimit ty loops).
    0x4a (and 0x42 structurally): each loop is a TRIANGLE STRIP segment;
    the consistent strip normal (cross products with alternating flip,
    phase reset per loop) equals the stored 12-byte normal, sign +1
    (CCW seen from the normal side) — F3/F5.
    0x4c: each loop is a CLOSED POLYGON in ring order; the Newell normal
    equals the stored normal, sign +1 — F4/F5.
    0x41: n == 3*type triangle lists (byte law, no normal payload).
    0x49: n == 3*type with normal; primitive reading unproven (F10/open).
  A loop's repeated references (strip joins) are real geometry: fan strips
  around an apex (cone-like) re-emit the apex between rim vertices.

  Triangle soup.  Decoding the clean stores (no `01 02` group, no trailer
  opener; every ref inside the pool) to a triangle soup yields a MANIFOLD:
  every undirected edge is used at most twice (1.000), closed solids (all
  edges exactly twice) on 0.868 of the souped parts, the rest sheet-like
  open shells whose boundary edges pair up — F6.  The winding is
  oriented-consistent (each edge used once per direction) on the closed
  solids.

Read-only; run with:  python3 -I scripts/triage/decode_facet_semantics.py
  [--max-per-release N]        cap the per-release sample (0 = all dev
                               parts; the default scans all of them)
  [--include-sha16 HEX16,...]  restrict to these files (sha16 prefixes)
  [--soup-sha16 HEX16]         additionally emit the OBJ triangle soup of
                               this part to docs/evidence/data/
  [--out-dir DIR]              output directory (default
                               docs/evidence/data)

Outputs (docs/evidence/data/):
  facet-semantics-files.csv   one row per scanned part
  facet-semantics-loops.csv   one row per decoded loop of the clean-store
                              subset (pool-only stores; the composite
                              stores' loop aggregates live in the files
                              CSV columns)
  facet-semantics-claims.csv  per-claim, per-release rates
  facet-soup-<sha16>.obj      the soup OBJ when --soup-sha16 is given
and a claim-rate summary on stdout.  Deterministic: file order is the
sorted manifest order and no wall-clock value enters the CSVs.
"""
import argparse
import csv
import math
import mmap
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"

sys.path.insert(0, str(ROOT / "scripts" / "triage"))
from decode_nested_store import valid_blocks, analyze_region  # noqa: E402
from decode_vertex_pool import (  # noqa: E402
    VREC, find_all, STRIP_RE,
)
from decode_tail_region import release_of  # noqa: E402

FULL_WRAP = b"\x10\x24\x04\xff\xff\x00\x00\x00"
STRIP_MARKERS = (0x41, 0x42, 0x49, 0x4A)   # loops = triangle-strip segments
POLY_MARKERS = (0x4C,)                      # loops = closed polygons
NORMAL_MARKERS_ALL = (0x49, 0x4A, 0x4B, 0x4C, 0x4E)  # carry the 12-B normal
SOUP_MARKERS = STRIP_MARKERS + POLY_MARKERS

FILE_FIELDS = [
    "sha256", "size_bytes", "repo", "detected_version", "release",
    "n_stores", "store_class", "body_size",
    "n_pool_groups", "n_vertices", "has_edge_group", "has_trailer_opener",
    "n_candidates", "n_records", "n_records_inbounds", "n_unresolved",
    "record_tiling_rate",
    "n_loops_strip", "n_loops_poly", "n_loops_noclass",
    "winding_tri_total", "winding_parallel", "winding_sign_pos",
    "winding_sign_neg", "winding_offplane", "winding_degenerate",
    "lex_parallel", "walk_parallel",
    "n_41", "n_41_3ty_ok", "n_49", "n_49_3ty_ok",
    "n_44", "n_5byte_header", "gap_bytes",
    "soup_ok", "soup_triangles", "soup_degenerate",
    "soup_manifold", "soup_closed", "soup_oriented",
    "soup_boundary_edges", "max_ref", "pool_size",
    "n_loops", "n_loops_repeat",
]
LOOP_FIELDS = [
    "sha256", "release", "record_offset", "marker", "type", "n_refs",
    "loop_counts", "width", "has_normal", "normal",
    "refs", "lex_refs", "in_pool",
    "reading", "parallel", "sign_pos", "sign_neg", "offplane", "degenerate",
]
CLAIMS = []


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def unit(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    return (v[0] / n, v[1] / n, v[2] / n) if n > 1e-12 else (0.0, 0.0, 0.0)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def scan_pool_groups(mm, body_lo, body_hi):
    """Decode every `01 06` pool group.  Returns (pools, kinds, openers)."""
    pools = []
    kinds = []
    for o in find_all(mm, FULL_WRAP, body_lo, body_hi):
        sub_kind = mm[o + 8:o + 10].hex()
        kinds.append(sub_kind)
        if sub_kind == "0106":
            if mm[o + 10] == 0xFF:
                cnt = int.from_bytes(mm[o + 11:o + 15], "little")
                q = o + 15
            else:
                cnt = mm[o + 10]
                q = o + 11
            vs = []
            while len(vs) < cnt and q + 15 <= body_hi and mm[q:q + 3] == VREC:
                vs.append(struct.unpack("<fff", mm[q + 3:q + 15]))
                q += 15
            pools.append(vs)
    return pools, kinds


def parse_facet_record(mm, o, body_hi, nxt, prefer_width=1):
    """Parse one facet record at header offset o under the tiling law.

    Header: 4-byte form `01 <mk> <ty> ff` or 5-byte form (markers 0x43/
    0x45/0x4b/0x4e observed: `01 <mk> <ty> 01 ff`).  Then u32le n, the
    12-byte normal for normal markers, k count bytes summing to n, and
    n refs of u8 or u16be width.  The (width, k) combo must end at or
    before the next header; exact tiling wins, then the narrower width —
    except on a gap edge (end < nxt), where prefer_width (the
    store-width context derived by scan_store, default 1 = the
    historical narrower width) wins the tie-break.  Returns a dict or
    None.
    """
    mk = mm[o + 1]
    ty = mm[o + 2]
    hlen = 4 if mm[o + 3] == 0xFF else 5
    if o + hlen + 4 > body_hi:
        return None
    n = int.from_bytes(mm[o + hlen:o + hlen + 4], "little")
    if not (0 <= n <= 1_000_000):
        return None
    has_normal = mk in NORMAL_MARKERS_ALL
    base = o + hlen + 4 + (12 if has_normal else 0)
    if base > body_hi:
        return None
    best = None
    for width in (1, 2):
        for k in range(0, 5):
            counts = [mm[base + j] for j in range(k)]
            if not ((n > 0 and sum(counts) == n) or (n == 0 and k == 0)):
                continue
            end = base + k + width * n
            if end > nxt:
                continue
            if end == nxt:
                rank = (0, width)  # exact tiling wins; narrower on exact ties
            else:
                # Gap edge: the store-width context wins the tie-break
                # (P3-B, #35 2026-11-10); the default context of 1 keeps
                # the historical narrower-width preference.
                rank = (1, 0 if width == prefer_width else 1)
            if best is None or rank < best[0]:
                refs = [int.from_bytes(
                    mm[base + k + width * j:base + k + width * (j + 1)], "big")
                    for j in range(n)]
                best = (rank, width, counts, refs, end)
    if best is None:
        return None
    _, width, counts, refs, end = best
    normal = None
    if has_normal:
        normal = struct.unpack("<fff", mm[o + hlen + 4:o + hlen + 16])
    return {"offset": o, "marker": mk, "type": ty, "hlen": hlen, "n": n,
            "width": width, "counts": counts, "refs": refs, "end": end,
            "normal": normal}


def strip_loop_dots(pts, normal):
    """Strip reading of one loop: dots of the consistent normal per triangle."""
    dots = []
    for t in range(len(pts) - 2):
        n0 = cross(sub(pts[t + 1], pts[t]), sub(pts[t + 2], pts[t]))
        if t % 2 == 1:
            n0 = (-n0[0], -n0[1], -n0[2])
        ln = math.sqrt(dot(n0, n0))
        if ln < 1e-12:
            dots.append(None)   # degenerate
            continue
        dots.append(dot(unit(n0), normal))
    return dots


def newell_normal(pts):
    nx = ny = nz = 0.0
    for i in range(len(pts)):
        x0, y0, z0 = pts[i]
        x1, y1, z1 = pts[(i + 1) % len(pts)]
        nx += y0 * z1 - z0 * y1
        ny += z0 * x1 - x0 * z1
        nz += x0 * y1 - y0 * x1
    return (nx, ny, nz)


def poly_loop_dots(pts, normal):
    """Closed-polygon reading: the Newell normal of the ring-order loop."""
    n0 = newell_normal(pts)
    ln = math.sqrt(dot(n0, n0))
    if ln < 1e-12:
        return [None]
    return [dot(unit(n0), normal)]


def loop_measured_dots(pool, lex, refs, marker, normal):
    """Dispatch one loop to its family reading.

    Returns (reading_name, dots) where dots[i] is the cosine against the
    stored normal (None = degenerate/off-plane under the reading).
    """
    pts = [pool[lex[x]] for x in refs]
    if marker in STRIP_MARKERS:
        return "strip", strip_loop_dots(pts, normal)
    if marker in POLY_MARKERS:
        return "polygon", poly_loop_dots(pts, normal)
    return "noclass", []


def soup_triangles(pool, lex, recs):
    """Decode clean stores to a triangle soup (walked-index triples).

    Strips: (r_t, r_{t+1}, r_{t+2}) with the flip on odd t.  Polygons:
    fan from the first corner (orientation-preserving for the ring-order
    CCW loops).  Returns (tris, degenerate, unresolved).
    """
    tris = []
    degenerate = 0
    unresolved = []
    for rec in recs:
        if rec["marker"] not in SOUP_MARKERS or \
                any(x >= len(pool) for x in rec["refs"]):
            unresolved.append(rec)
            continue
        offs = []
        o = 0
        for c in rec["counts"]:
            offs.append(rec["refs"][o:o + c])
            o += c
        for refs in offs:
            pts = [lex[x] for x in refs]
            if rec["marker"] in STRIP_MARKERS:
                for t in range(len(pts) - 2):
                    tri = (pts[t], pts[t + 1], pts[t + 2])
                    if t % 2 == 1:
                        tri = (tri[2], tri[1], tri[0])
                    a, b, c = pool[tri[0]], pool[tri[1]], pool[tri[2]]
                    if a == b or b == c or a == c or \
                            cross(sub(b, a), sub(c, a)) == (0.0, 0.0, 0.0):
                        degenerate += 1
                        continue
                    tris.append(tri)
            else:
                for t in range(1, len(pts) - 1):
                    tri = (pts[0], pts[t], pts[t + 1])
                    a, b, c = pool[tri[0]], pool[tri[1]], pool[tri[2]]
                    if a == b or b == c or a == c:
                        degenerate += 1
                        continue
                    tris.append(tri)
    return tris, degenerate, unresolved


def soup_stats(pool, tris):
    """Mesh invariants: bbox, edge usage, closure, orientation."""
    if not pool:
        return {}
    xs = [v[0] for v in pool]
    ys = [v[1] for v in pool]
    zs = [v[2] for v in pool]
    edge = Counter()
    directed = Counter()
    for tri in tris:
        for e in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            edge[tuple(sorted(e))] += 1
            directed[e] += 1
    manifold = all(v <= 2 for v in edge.values())
    closed = all(v == 2 for v in edge.values())
    oriented = all(directed[(a, b)] == directed[(b, a)]
                   for (a, b) in directed)
    boundary = sum(1 for v in edge.values() if v == 1)
    return {
        "bbox": (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)),
        "n_edges": len(edge),
        "manifold": manifold,
        "closed": closed,
        "oriented": oriented,
        "boundary_edges": boundary,
    }


def scan_store(mm, blk, blocks, d8_outer, rel, ordinal):
    """Decode one store's pools + facet records + soup invariants."""
    cls, srow, _ = analyze_region(mm, blk, blocks, d8_outer, rel, ordinal)
    if srow is None:
        return None
    origin = srow["origin_abs"]
    body_lo = origin + (32 if srow["origin_kind"] == "v5header" else 64)
    body_hi = srow["catalog_start"]
    pools, kinds = scan_pool_groups(mm, body_lo, body_hi)
    pool = [v for g in pools for v in g]
    lex = sorted(range(len(pool)),
                 key=lambda i: (pool[i][0], pool[i][1], pool[i][2]))
    hdrs = [m.start() for m in STRIP_RE.finditer(mm, body_lo, body_hi)]
    # Store-width pre-pass (F1w as corrected 2026-11-10 #35), bounded to
    # the clean store class (no `01 02` edge group AND no trailer opener —
    # the class where the cluster-final truncation was verified; the
    # third re-scope): composite stores keep the unconditional width-1
    # gap behavior.  Every candidate header is parsed under the default
    # tie-break and the exact-tile records — those whose end equals the
    # next header position — vote their width; a unanimous vote becomes
    # the gap-edge tie-break width, mixed votes (or no exact tiles) keep
    # the default narrower-width preference.  Mirrors scan_facets exactly.
    prefer = 1
    if not ("0102" in kinds or any(k.startswith("ff") for k in kinds)):
        exact_widths = set()
        for i, o in enumerate(hdrs):
            nxt = hdrs[i + 1] if i + 1 < len(hdrs) else body_hi
            rec = parse_facet_record(mm, o, body_hi, nxt)
            if rec is not None and rec["end"] == nxt:
                exact_widths.add(rec["width"])
        prefer = exact_widths.pop() if len(exact_widths) == 1 else 1
    recs = []
    n_5byte = 0
    gap_bytes = 0
    i = 0
    pos = body_lo
    while i < len(hdrs):
        o = hdrs[i]
        nxt = hdrs[i + 1] if i + 1 < len(hdrs) else body_hi
        rec = parse_facet_record(mm, o, body_hi, nxt, prefer_width=prefer)
        if rec is None:
            i += 1
            continue
        # gaps between the consumed region and the record start hold the
        # 5-byte-header variant records (0x4b/0x4e observed: G2 unknown 6);
        # they start exactly at the previous record's end (observed form)
        gap_bytes += o - pos
        if pos + 5 <= o and mm[pos] == 0x01 and 0x41 <= mm[pos + 1] <= 0x4F \
                and mm[pos + 3] != 0xFF and mm[pos + 4] == 0xFF:
            n_5byte += 1
        recs.append(rec)
        pos = rec["end"]
        nxt2 = [h for h in hdrs if h >= rec["end"]]
        i = hdrs.index(nxt2[0]) if nxt2 else len(hdrs)
    gap_bytes += body_hi - pos
    return {
        "class": cls, "body": (body_lo, body_hi), "pool": pool, "lex": lex,
        "kinds": kinds, "recs": recs, "candidates": len(hdrs),
        "n_5byte_header": n_5byte, "gap_bytes": gap_bytes,
    }


def measure_store(st, rel):
    """Measure one store; returns (file_row_update, loop_rows)."""
    pool, lex, recs = st["pool"], st["lex"], st["recs"]
    body_lo, body_hi = st["body"]
    upd = {
        "body_size": body_hi - body_lo,
        "n_pool_groups": sum(1 for k in st["kinds"] if k == "0106"),
        "n_vertices": len(pool),
        "has_edge_group": "0102" in st["kinds"],
        "has_trailer_opener": any(k.startswith("ff") for k in st["kinds"]),
        "n_candidates": st["candidates"],
        "n_records": len(recs),
        "n_records_inbounds": 0,
        "n_unresolved": st["candidates"] - len(recs),
        "record_tiling_rate": 0,
        "n_loops_strip": 0, "n_loops_poly": 0, "n_loops_noclass": 0,
        "winding_tri_total": 0, "winding_parallel": 0,
        "winding_sign_pos": 0, "winding_sign_neg": 0,
        "winding_offplane": 0, "winding_degenerate": 0,
        "lex_parallel": 0, "walk_parallel": 0,
        "n_41": 0, "n_41_3ty_ok": 0, "n_49": 0, "n_49_3ty_ok": 0,
        "n_44": 0, "n_5byte_header": st["n_5byte_header"],
        "gap_bytes": st["gap_bytes"],
        "soup_ok": 0, "soup_triangles": 0, "soup_degenerate": 0,
        "soup_manifold": 0, "soup_closed": 0, "soup_oriented": 0,
        "soup_boundary_edges": 0,
        "max_ref": max((max(r["refs"]) for r in recs if r["refs"]), default=-1),
        "pool_size": len(pool),
        "n_loops": 0, "n_loops_repeat": 0,
    }
    walk_lex = list(range(len(pool)))
    loop_rows = []
    clean = (not upd["has_edge_group"]) and (not upd["has_trailer_opener"])
    emit_loops = clean
    for rec in recs:
        mk = rec["marker"]
        offs_all = []
        o0 = 0
        for c0 in rec["counts"]:
            offs_all.append(rec["refs"][o0:o0 + c0])
            o0 += c0
        upd["n_loops"] += len(offs_all)
        upd["n_loops_repeat"] += sum(
            1 for refs in offs_all if len(set(refs)) != len(refs))
        if mk == 0x41:
            upd["n_41"] += 1
            if rec["n"] == 3 * rec["type"]:
                upd["n_41_3ty_ok"] += 1
        elif mk == 0x49:
            upd["n_49"] += 1
            if rec["n"] == 3 * rec["type"]:
                upd["n_49_3ty_ok"] += 1
        elif mk == 0x44:
            upd["n_44"] += 1
        if rec["refs"] and max(rec["refs"]) < len(pool):
            upd["n_records_inbounds"] += 1
        offs = []
        o = 0
        for c in rec["counts"]:
            offs.append(rec["refs"][o:o + c])
            o += c
        for refs in offs:
            reading = ("strip" if mk in STRIP_MARKERS else
                       "polygon" if mk in POLY_MARKERS else "noclass")
            upd["n_loops_%s" % ("strip" if reading == "strip" else
                                "poly" if reading == "polygon" else
                                "noclass")] += 1
            if not emit_loops:
                continue
            if rec["normal"] is None or reading == "noclass" or \
                    any(x >= len(pool) for x in refs):
                loop_rows.append(_loop_row(rel, rec, refs, reading, offs,
                                           pool, lex, None))
                continue
            name, dots = loop_measured_dots(pool, lex, refs, mk,
                                            unit(rec["normal"]))
            par = sum(1 for d in dots if d is not None and abs(d) > 0.99)
            pos = sum(1 for d in dots if d is not None and d > 0)
            neg = sum(1 for d in dots if d is not None and d < 0)
            off = sum(1 for d in dots if d is not None and abs(d) <= 0.99)
            degen = sum(1 for d in dots if d is None)
            upd["winding_tri_total"] += len(dots)
            upd["winding_parallel"] += par
            upd["winding_sign_pos"] += pos
            upd["winding_sign_neg"] += neg
            upd["winding_offplane"] += off
            upd["winding_degenerate"] += degen
            upd["lex_parallel"] += par
            # walk-order control: same reading on walk-ordered pool
            wname, wdots = loop_measured_dots(pool, walk_lex, refs, mk,
                                              unit(rec["normal"]))
            upd["walk_parallel"] += sum(
                1 for d in wdots if d is not None and abs(d) > 0.99)
            loop_rows.append(_loop_row(rel, rec, refs, name, offs, pool, lex,
                                       dots))
    upd["record_tiling_rate"] = (len(recs) / st["candidates"]
                                 if st["candidates"] else "")
    if clean and pool and not any(x >= len(pool) for r in recs for x in r["refs"]):
        tris, degenerate, unresolved = soup_triangles(pool, lex, recs)
        tris = tris if tris else []
        if not tris:
            return upd, loop_rows
        stats = soup_stats(pool, tris)
        upd["soup_ok"] = 1
        upd["soup_triangles"] = len(tris)
        upd["soup_degenerate"] = degenerate
        upd["soup_manifold"] = int(stats["manifold"])
        upd["soup_closed"] = int(stats["closed"])
        upd["soup_oriented"] = int(stats["oriented"])
        upd["soup_boundary_edges"] = stats["boundary_edges"]
    return upd, loop_rows


def _loop_row(rel, rec, refs, reading, offs, pool, lex, dots):
    in_pool = all(x < len(pool) for x in refs)
    lex_txt = " ".join(str(lex[x]) for x in refs if x < len(lex))
    if dots is None:
        par = pos = neg = off = degen = ""
    else:
        par = sum(1 for d in dots if d is not None and abs(d) > 0.99)
        pos = sum(1 for d in dots if d is not None and d > 0)
        neg = sum(1 for d in dots if d is not None and d < 0)
        off = sum(1 for d in dots if d is not None and abs(d) <= 0.99)
        degen = sum(1 for d in dots if d is None)
        tri = par + off + degen
        par = "%d/%d" % (par, tri) if tri else ""
    return {
        "sha256": rel["sha256"], "release": release_of(rel["detected_version"]),
        "record_offset": rec["offset"], "marker": "0x%02x" % rec["marker"],
        "type": rec["type"], "n_refs": rec["n"],
        "loop_counts": "+".join(str(c) for c in rec["counts"]),
        "width": rec["width"], "has_normal": rec["normal"] is not None,
        "normal": ("%.6g,%.6g,%.6g" % rec["normal"]
                   if rec["normal"] else ""),
        "refs": " ".join(str(x) for x in refs),
        "lex_refs": lex_txt,
        "in_pool": in_pool,
        "reading": reading, "parallel": par, "sign_pos": pos,
        "sign_neg": neg, "offplane": off, "degenerate": degen,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-per-release", type=int, default=0)
    ap.add_argument("--include-sha16", default="")
    ap.add_argument("--soup-sha16", default="")
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [r for r in csv.DictReader(MANIFEST.open())
            if r["magic_ok"] == "yes" and r["split"] == "dev"
            and r["kind"] == "part"]
    if args.include_sha16:
        want = {h for h in args.include_sha16.split(",") if h}
        rows = [r for r in rows if r["sha256"][:16] in want]
        if not rows:
            print("error: no manifest row matches --include-sha16 %s"
                  % args.include_sha16, file=sys.stderr)
            return 2
    if args.max_per_release > 0:
        byrel = defaultdict(list)
        for r in rows:
            byrel[release_of(r["detected_version"])].append(r)
        picked = []
        for reln in sorted(byrel):
            picked.extend(byrel[reln][:args.max_per_release])
        rows = picked
    rows.sort(key=lambda r: r["sha256"])

    f_fh = (out_dir / "facet-semantics-files.csv").open("w", newline="")
    fw = csv.DictWriter(f_fh, fieldnames=FILE_FIELDS)
    fw.writeheader()
    l_fh = (out_dir / "facet-semantics-loops.csv").open("w", newline="")
    lw = csv.DictWriter(l_fh, fieldnames=LOOP_FIELDS)
    lw.writeheader()

    soup_sha = args.soup_sha16
    soup_written = False
    for r in rows:
        path = ROOT / r["local_path"]
        try:
            with path.open("rb") as fh:
                mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
                size = mm.size()
                d8_outer = int.from_bytes(mm[8:12], "big") if size >= 12 else 0
                blocks = valid_blocks(mm)
                stores = []
                for ordinal, blk in enumerate(b for b, nm in blocks
                                              if nm == "CATStdCont"):
                    st = scan_store(mm, blk, blocks, d8_outer, r, ordinal)
                    if st is not None:
                        stores.append(st)
                soup_payload = None
                if soup_sha and r["sha256"][:16] == soup_sha and stores:
                    st = stores[0]
                    pool, lex, recs = st["pool"], st["lex"], st["recs"]
                    composite = any(k == "0102" or k.startswith("ff")
                                    for k in st["kinds"])
                    if not composite and not any(
                            x >= len(pool) for rc in recs for x in rc["refs"]):
                        tris, _, _ = soup_triangles(pool, lex, recs)
                        stats = soup_stats(pool, tris)
                        soup_payload = (pool, tris, stats, r)
                mm.close()
        except OSError as exc:
            print("error: %s: %s" % (r["sha256"][:16], exc), file=sys.stderr)
            continue
        if not stores:
            continue
        frow = {
            "sha256": r["sha256"], "size_bytes": r["size_bytes"],
            "repo": r["repo"], "detected_version": r["detected_version"],
            "release": release_of(r["detected_version"]),
            "n_stores": len(stores), "store_class": stores[0]["class"],
        }
        num_keys = [k for k in FILE_FIELDS if k not in frow]
        for k in num_keys:
            frow[k] = 0
        for st in stores:
            upd, loop_rows = measure_store(st, r)
            for k, v in upd.items():
                if k in ("body_size",):
                    frow[k] = frow.get(k, 0) + v
                elif isinstance(v, bool):
                    frow[k] = max(frow.get(k, 0), int(v))
                elif isinstance(v, int):
                    frow[k] = frow.get(k, 0) + v
                else:
                    frow[k] = v
            for lr in loop_rows:
                lw.writerow({k: lr.get(k, "") for k in LOOP_FIELDS})
        fw.writerow({k: frow.get(k, "") for k in FILE_FIELDS})
        if soup_payload and not soup_written:
            pool, tris, stats, relrow = soup_payload
            obj_path = out_dir / ("facet-soup-%s.obj" % soup_sha)
            with obj_path.open("w") as f:
                f.write("# triangle soup decoded from the CATStdCont nested "
                        "store (G3 #31)\n")
                f.write("# part sha256=%s release=%s repo=%s\n"
                        % (relrow["sha256"], relrow["detected_version"],
                           relrow["repo"]))
                f.write("# vertices = the decoded pool in walk order; "
                        "facet refs resolve through lexicographic ranks\n")
                for v in pool:
                    f.write("v %.9g %.9g %.9g\n" % v)
                for tri in tris:
                    f.write("f %d %d %d\n" % (tri[0] + 1, tri[1] + 1,
                                              tri[2] + 1))
            soup_written = True
            print("soup stats for %s:" % soup_sha)
            print("  vertices: %d (pool groups decoded)" % len(pool))
            print("  triangles: %d" % len(tris))
            print("  bbox: %s" % (" ".join("%.6g" % v for v in stats["bbox"])))
            print("  edges: %d; usage<=2: %s; closed(all==2): %s; "
                  "oriented: %s" % (stats["n_edges"], stats["manifold"],
                                    stats["closed"], stats["oriented"]))
            print("  boundary edges: %d" % stats["boundary_edges"])
            print("  wrote", obj_path)

    for fh in (f_fh, l_fh):
        fh.close()

    tally_claims(out_dir)
    return 0


def tally_claims(out_dir):
    """Per-claim, per-release rates recomputed from the emitted CSVs."""
    files = list(csv.DictReader((out_dir / "facet-semantics-files.csv").open()))
    tallies = defaultdict(lambda: defaultdict(lambda: [0, 0]))

    def tally(claim, rel, passed):
        tallies[claim][rel][0] += 1
        tallies[claim][rel][1] += int(bool(passed))

    def num(f, k):
        return int(f[k]) if f[k] != "" else 0

    for f in files:
        rel = f["release"]
        cands = num(f, "n_candidates")
        tally("F1_record_tiling", rel, cands > 0 and
              num(f, "n_records") == cands)
        wd = num(f, "winding_tri_total")
        real = wd - num(f, "winding_degenerate")
        tally("F2_lex_mapping", rel, real > 0 and
              num(f, "lex_parallel") == real)
        tally("F2w_walk_control", rel, real > 0 and
              num(f, "walk_parallel") == real)
        nsa = num(f, "n_loops_strip")
        tally("F3_strip_law_4a42", rel, real > 0 and nsa > 0 and
              num(f, "winding_sign_neg") == 0 and
              num(f, "winding_offplane") == 0)
        npoly = num(f, "n_loops_poly")
        tally("F4_polygon_law_4c", rel, real > 0 and npoly > 0 and
              num(f, "winding_sign_neg") == 0 and
              num(f, "winding_offplane") == 0)
        tally("F5_winding_ccw", rel, real > 0 and
              num(f, "winding_sign_neg") == 0)
        tally("F6a_soup_manifold", rel, num(f, "soup_ok") == 1 and
              num(f, "soup_manifold") == 1)
        tally("F6b_soup_closed", rel, num(f, "soup_ok") == 1 and
              num(f, "soup_closed") == 1)
        tally("F6c_soup_oriented", rel, num(f, "soup_ok") == 1 and
              num(f, "soup_oriented") == 1)
        tally("F7_soup_degenerate_free", rel, num(f, "soup_ok") == 1 and
              num(f, "soup_degenerate") == 0)
        tally("F8_composite_index_space", rel, num(f, "has_edge_group") == 1
              or num(f, "has_trailer_opener") == 1)
        tally("F8o_refs_beyond_pool", rel, num(f, "pool_size") > 0 and
              num(f, "max_ref") >= num(f, "pool_size"))
        tally("F9_41_triangle_law", rel, num(f, "n_41") > 0 and
              num(f, "n_41") == num(f, "n_41_3ty_ok"))
        tally("F10_49_triangle_law", rel, num(f, "n_49") > 0 and
              num(f, "n_49") == num(f, "n_49_3ty_ok"))

    with (out_dir / "facet-semantics-claims.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["claim", "release", "observations", "passes", "rate"])
        for c in sorted(tallies):
            for rel in sorted(tallies[c]):
                obs, ok = tallies[c][rel]
                w.writerow([c, rel, obs, ok,
                            "%.3f" % (ok / obs if obs else 0)])

    print("== facet semantics scan ==")
    tot = defaultdict(lambda: [0, 0])
    for c in sorted(tallies):
        for rel in sorted(tallies[c]):
            obs, ok = tallies[c][rel]
            tot[c][0] += obs
            tot[c][1] += ok
    for c in sorted(tot):
        obs, ok = tot[c]
        print("  %-28s %5d/%5d = %.3f" % (c, ok, obs, ok / obs if obs else 0))
    print("wrote CSVs under", out_dir)


if __name__ == "__main__":
    sys.exit(main())
