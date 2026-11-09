#!/usr/bin/env python3
"""Decode the vertex pool of the nested V5_CFV2 stream store (G2, ticket #30).

Builds on G1's nested-store decode (decode_nested_store.py: store origin,
catalog, body extent) and B4's strip-record discovery.  Static reads only;
no structure is parsed by the package.

Model (claims P1-P10 in the evidence note
docs/evidence/2026-11-09-vertex-pool.md):

  Pool location.  The store body (origin+32/64 .. catalog start) carries
  the vertex coordinates as runs of 15-byte vertex records

      [05 08 01][f32le x][f32le y][f32le z]

  inside pool groups opened by the 8-byte wrapper `10 24 04 ff ff 00 00 00`
  followed by `01 06` and a vertex count (one byte; 0xff escapes to a
  u32le count at +11).  The walked record count equals the count field on
  verified groups.  The pool is NOT in the trailer region [B, B+C): that
  region carries edge/curve geometry records instead (edge triplet +
  length float32s).

  Facet (strip) records.  The connectivity records in the body are

      01 <mk> <ty> ff [u32le n][12B normal][k u8 loop counts][n x indices]

  with marker families: 0x41 triangle lists (n == 3*ty, no normal,
  no loop counts), 0x49 triangles with normal (n == 3*ty, no loop
  counts), 0x42 boundary loops without normal, 0x4a/0x4c boundary loops
  with f32le unit normal (the writer writes near-zero components as
  epsilon subnormals such as `00 00 00 a5` = 1.8e-40 and `32 31 0d 25`
  = 1.6e-16).  Loop counts are u8 bytes summing to n; the number of
  count bytes k is validated (0..4), not assumed from ty.  Indices are
  u8 when the pool is small (verified <= 255-vertex groups) and u16be
  otherwise.  Index width per record is resolved by trying u8 then
  u16be and accepting the width whose indices fall inside the store's
  decoded pool (see P6: per-store global pool = sum of walked groups).

  Association.  Facets bind to the pool of their enclosing store; on
  single-pool-group stores the binding is unique and the functional test
  is exact (all indices < group count).  Multi-group stores leave the
  per-segment binding open (measured overflow up to ~2x a group count;
  recorded as G2 open question 1, rates in the claims CSV).

Read-only; run with:  python3 -I scripts/triage/decode_vertex_pool.py
  [--max-per-release N]        cap the per-release sample (0 = all dev
                               parts; the default scans all of them)
  [--include-sha16 HEX16,...]  restrict to these files (sha16 prefixes)
  [--out-dir DIR]              output directory (default
                               docs/evidence/data)

Outputs (docs/evidence/data/):
  vertex-pool-files.csv     one row per scanned part
  vertex-pool-pools.csv     one row per pool group (decoded pool)
  vertex-pool-claims.csv    per-claim, per-release rates
and a claim-rate summary on stdout.  Deterministic: file order is the
sorted manifest order and no wall-clock value enters the CSVs.
"""
import argparse
import csv
import math
import mmap
import re
import struct
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"

sys.path.insert(0, str(ROOT / "scripts" / "triage"))
from decode_nested_store import valid_blocks, analyze_region  # noqa: E402
from decode_tail_region import release_of  # noqa: E402

WRAP = b"\x10\x24\x04\xff\xff"
VREC = b"\x05\x08\x01"
HDR = re.compile(rb"\x01[\x41-\x4f][\x01-\x0a]\xff", re.DOTALL)
STRIP_RE = re.compile(rb"\x01[\x41-\x4f].\xff", re.DOTALL)
NORMAL_MARKERS = (0x49, 0x4A, 0x4C, 0x4E)
LOOP_MARKERS = (0x42, 0x4A, 0x4C)
PLAUSIBLE_MM = 1e5     # |coord| bound for the mm-scale plausibility test

FILE_FIELDS = [
    "sha256", "size_bytes", "repo", "detected_version", "release",
    "n_stores", "store_class", "body_size", "n_wrappers", "n_pool_groups",
    "n_pool_ok", "n_vertices", "vertex_finite_rate", "vertex_plausible_rate",
    "bbox_min_x", "bbox_min_y", "bbox_min_z",
    "bbox_max_x", "bbox_max_y", "bbox_max_z",
    "n_strip_candidates", "n_facets_strict", "n_facets_u8",
    "n_facets_u16be", "n_facets_inbounds", "n_facets_shape_only",
    "n_facets_unresolved",
    "facet_inbounds_rate", "max_index_accepted",
    "pool_without_strips", "strips_without_pool",
]
POOL_FIELDS = [
    "sha256", "release", "pool_ordinal", "wrapper_abs", "count_field",
    "n_walked", "count_ok", "vertex_finite", "vertex_plausible",
    "bbox_min_x", "bbox_min_y", "bbox_min_z",
    "bbox_max_x", "bbox_max_y", "bbox_max_z",
]
CLAIMS = []


def find_all(mm, needle, start, end):
    out = []
    i = mm.find(needle, start, end)
    while i >= 0:
        out.append(i)
        i = mm.find(needle, i + 1, end)
    return out


def f32le(mm, off):
    return struct.unpack("<f", mm[off:off + 4])[0]


def plausible(v):
    """Coordinate-plausible f32: finite, mm-scale or exactly zero."""
    return math.isfinite(v) and (v == 0.0 or abs(v) <= PLAUSIBLE_MM)


def walk_pool_group(mm, o, body_hi):
    """Decode one pool group at wrapper offset o.

    Returns (count_field, n_walked, verts, finite, plausible) where verts
    is the list of (x, y, z) f32le triples of the walked vertex records.
    """
    if mm[o + 8] != 0x01 or mm[o + 9] != 0x06:
        return None
    b10 = mm[o + 10]
    if b10 == 0xFF:
        if o + 15 > body_hi:
            return None
        cnt = int.from_bytes(mm[o + 11:o + 15], "little")
        q = o + 15
    else:
        cnt = b10
        q = o + 11
    if not (1 <= cnt <= 1_000_000) or q + 15 * min(cnt, 4) > body_hi:
        return None
    verts = []
    finite = True
    plaushit = True
    while len(verts) < cnt and q + 15 <= body_hi \
            and mm[q:q + 3] == VREC:
        x, y, z = struct.unpack("<fff", mm[q + 3:q + 15])
        if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
            finite = False
        if not (plausible(x) and plausible(y) and plausible(z)):
            plaushit = False
        verts.append((x, y, z))
        q += 15
    return (cnt, len(verts), verts, finite, plaushit)


def parse_facet(mm, o, body_hi, total_verts):
    """Strictly parse one facet record at header offset o.

    Returns (mk, ty, n, width, idxs, maxidx) or None when no variant of
    the grammar validates (loop-count sums must equal n; the width whose
    indices all fall inside the decoded pool wins; u8 tried first).
    """
    mk, ty = mm[o + 1], mm[o + 2]
    n = int.from_bytes(mm[o + 4:o + 8], "little")
    if not (1 <= n <= 1_000_000):
        return None
    has_normal = mk in NORMAL_MARKERS
    base0 = o + 8 + (12 if has_normal else 0)
    if base0 > body_hi:
        return None
    for width in (1, 2):
        for k in range(0, 5):
            base = base0 + k
            if base + n * width > body_hi:
                continue
            cnts = [mm[base0 + j] for j in range(k)]
            if not ((n > 0 and sum(cnts) == n) or (n == 0 and k == 0)):
                continue
            idxs = [int.from_bytes(mm[base + i * width:base + (i + 1) * width],
                                   "big") for i in range(n)]
            if total_verts > 0 and max(idxs) < total_verts:
                return (mk, ty, n, width, idxs, max(idxs), True)
            if total_verts == 0 and k in (0, ty) and width == 1:
                # no pool decoded: accept the grammar shape only — this
                # is never a strict/inbounds facet (the in-bounds test
                # is vacuous without a pool); the caller tallies it as
                # unresolved.
                return (mk, ty, n, width, idxs, max(idxs), False)
    return None


def scan_store(mm, rel, ordinal, blk, blocks, d8_outer):
    """Decode one store's pool + facets.  Returns (row, pool_rows)."""
    cls, srow, _ = analyze_region(mm, blk, blocks, d8_outer, rel, ordinal)
    if srow is None:
        return None, []
    origin = srow["origin_abs"]
    body_lo = origin + (32 if srow["origin_kind"] == "v5header" else 64)
    body_hi = srow["catalog_start"]

    # ---- pool groups
    wraps = find_all(mm, WRAP, body_lo, body_hi)
    pools = []
    for o in wraps:
        g = walk_pool_group(mm, o, body_hi)
        if g is None:
            continue
        cnt, n, verts, finite, plaushit = g
        pools.append({
            "wrapper_abs": o, "count_field": cnt, "n_walked": n,
            "count_ok": n == cnt, "verts": verts,
            "vertex_finite": finite, "vertex_plausible": plaushit,
        })
    total_verts = sum(p["n_walked"] for p in pools)
    allv = [c for p in pools for c in p["verts"]]
    if allv:
        xs, ys, zs = zip(*allv)
        bbox = (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))
        finite_rate = sum(
            1 for p in pools for c in p["verts"]
            if all(math.isfinite(v) for v in c)) / len(allv)
        plausrate = sum(
            1 for p in pools for c in p["verts"]
            if all(plausible(v) for v in c)) / len(allv)
    else:
        bbox = None
        finite_rate = plausrate = ""

    # ---- facet records (candidates from B4's regex, strict parse)
    cands = []
    for m in STRIP_RE.finditer(mm, body_lo, body_hi):
        cands.append(m.start())
    facets = []
    i = 0
    while i < len(cands):
        o = cands[i]
        f = parse_facet(mm, o, body_hi, total_verts)
        if f is not None:
            facets.append(f)
            step = 8 + (12 if f[0] in NORMAL_MARKERS else 0)
            nxt = [c for c in cands if c > o + step]
            i = cands.index(nxt[0]) if nxt else len(cands)
        else:
            i += 1
    strict = [f for f in facets if f[6]]
    n_shape = len(facets) - len(strict)
    n_u8 = sum(1 for f in strict if f[3] == 1)
    n_u16 = sum(1 for f in strict if f[3] == 2)
    maxacc = max((f[5] for f in strict), default="")
    rate = (len(strict) / len(cands)) if cands else ""
    n_unresolved = max(0, len(cands) - len(strict))

    row = {
        "sha256": rel["sha256"], "size_bytes": rel["size_bytes"],
        "repo": rel["repo"],
        "detected_version": rel["detected_version"],
        "release": release_of(rel["detected_version"]),
        "n_stores": 1, "store_class": cls,
        "body_size": body_hi - body_lo,
        "n_wrappers": len(wraps), "n_pool_groups": len(pools),
        "n_pool_ok": sum(1 for p in pools if p["count_ok"]),
        "n_vertices": total_verts,
        "vertex_finite_rate": finite_rate,
        "vertex_plausible_rate": plausrate,
        "n_strip_candidates": len(cands),
        "n_facets_strict": len(strict),
        "n_facets_u8": n_u8, "n_facets_u16be": n_u16,
        "n_facets_inbounds": len(strict),
        "n_facets_shape_only": n_shape,
        "n_facets_unresolved": n_unresolved,
        "facet_inbounds_rate": rate,
        "max_index_accepted": maxacc,
        "pool_without_strips": bool(pools) and not cands,
        "strips_without_pool": bool(cands) and not pools,
    }
    if bbox is not None:
        for name, v in zip(("bbox_min_x", "bbox_min_y", "bbox_min_z",
                            "bbox_max_x", "bbox_max_y", "bbox_max_z"),
                           bbox):
            row[name] = "%.6g" % v
    pool_rows = []
    for j, p in enumerate(pools):
        pv = p["verts"]
        prow = {
            "sha256": rel["sha256"],
            "release": release_of(rel["detected_version"]),
            "pool_ordinal": j, "wrapper_abs": p["wrapper_abs"],
            "count_field": p["count_field"], "n_walked": p["n_walked"],
            "count_ok": p["count_ok"],
            "vertex_finite": p["vertex_finite"],
            "vertex_plausible": p["vertex_plausible"],
        }
        if pv:
            xs, ys, zs = zip(*pv)
            for name, v in zip(("bbox_min_x", "bbox_min_y", "bbox_min_z",
                                "bbox_max_x", "bbox_max_y", "bbox_max_z"),
                               (min(xs), min(ys), min(zs),
                                max(xs), max(ys), max(zs))):
                prow[name] = "%.6g" % v
        pool_rows.append(prow)
    return row, pool_rows


def scan_file(path, rel):
    """One part: every CATStdCont store's pool decode."""
    rows = []
    pool_rows = []
    with path.open("rb") as fh:
        mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        size = mm.size()
        d8_outer = int.from_bytes(mm[8:12], "big") if size >= 12 else 0
        blocks = valid_blocks(mm)
        stdcont = [b for b, nm in blocks if nm == "CATStdCont"]
        frow = None
        for ordinal, blk in enumerate(stdcont):
            row, prows = scan_store(mm, rel, ordinal, blk, blocks, d8_outer)
            if row is not None:
                rows.append(row)
                pool_rows.extend(prows)
                if frow is None:
                    frow = row
                else:
                    # accumulate multi-store parts into the file row
                    for k in ("n_pool_groups", "n_pool_ok", "n_vertices",
                              "n_strip_candidates", "n_facets_strict",
                              "n_facets_u8", "n_facets_u16be",
                              "n_facets_inbounds", "n_facets_unresolved"):
                        frow[k] += row[k]
                    frow["n_stores"] += 1
                    frow["pool_without_strips"] = (
                        frow["pool_without_strips"] or row["pool_without_strips"])
                    frow["strips_without_pool"] = (
                        frow["strips_without_pool"] or row["strips_without_pool"])
        mm.close()
    if frow is None:
        frow = {
            "sha256": rel["sha256"], "size_bytes": rel["size_bytes"],
            "repo": rel["repo"],
            "detected_version": rel["detected_version"],
            "release": release_of(rel["detected_version"]),
            "n_stores": 0, "store_class": "no_stdcont",
        }
        return frow, []
    return frow, pool_rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-per-release", type=int, default=0)
    ap.add_argument("--include-sha16", default="")
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
        for rel in sorted(byrel):
            picked.extend(byrel[rel][:args.max_per_release])
        rows = picked
    rows.sort(key=lambda r: r["sha256"])

    f_fh = (out_dir / "vertex-pool-files.csv").open("w", newline="")
    fw = csv.DictWriter(f_fh, fieldnames=FILE_FIELDS)
    fw.writeheader()
    p_fh = (out_dir / "vertex-pool-pools.csv").open("w", newline="")
    pw = csv.DictWriter(p_fh, fieldnames=POOL_FIELDS)
    pw.writeheader()

    for r in rows:
        frow, pool_rows = scan_file(ROOT / r["local_path"], r)
        fw.writerow({k: frow.get(k, "") for k in FILE_FIELDS})
        for prow in pool_rows:
            pw.writerow({k: prow.get(k, "") for k in POOL_FIELDS})

    for fh in (f_fh, p_fh):
        fh.close()

    tally_claims(out_dir)
    return 0


def tally_claims(out_dir):
    """Per-claim, per-release rates recomputed from the emitted CSVs."""
    files = list(csv.DictReader((out_dir / "vertex-pool-files.csv").open()))
    pools = list(csv.DictReader((out_dir / "vertex-pool-pools.csv").open()))
    tallies = defaultdict(lambda: defaultdict(lambda: [0, 0]))

    def tally(claim, rel, passed):
        tallies[claim][rel][0] += 1
        tallies[claim][rel][1] += int(bool(passed))

    def num(f, k):
        return int(f[k]) if f[k] != "" else 0

    def flt(f, k):
        return float(f[k]) if f[k] != "" else None

    for f in files:
        rel = f["release"]
        tally("P1_pool_groups_present", rel, num(f, "n_pool_groups") > 0)
        tally("P1v_vertices_present", rel, num(f, "n_vertices") > 0)
        tally("P2_pool_count_walk", rel, num(f, "n_pool_groups") ==
              num(f, "n_pool_ok") and num(f, "n_pool_groups") > 0)
        tally("P3_vertex_f32_finite", rel,
              flt(f, "vertex_finite_rate") == 1.0)
        tally("P4_vertex_plausible_mm", rel,
              (flt(f, "vertex_plausible_rate") or 0) >= 0.999)
        tally("P5_facets_strict_parse", rel,
              num(f, "n_strip_candidates") > 0 and
              num(f, "n_facets_strict") > 0)
        tally("P6_facets_inbounds", rel,
              num(f, "n_strip_candidates") > 0 and
              num(f, "n_facets_inbounds") > 0)
        tally("P7_pool_without_strips", rel,
              f["pool_without_strips"] == "True")
        tally("P8_strips_without_pool", rel,
              f["strips_without_pool"] == "True")
        tally("P6u_facets_unresolved", rel,
              num(f, "n_strip_candidates") > 0 and
              num(f, "n_facets_unresolved") > 0)
        if f["bbox_max_x"] != "":
            mx = max(abs(float(f["bbox_min_x"])),
                     abs(float(f["bbox_max_x"])))
            my = max(abs(float(f["bbox_min_y"])),
                     abs(float(f["bbox_max_y"])))
            mz = max(abs(float(f["bbox_min_z"])),
                     abs(float(f["bbox_max_z"])))
            tally("P9_bbox_mm_scale", rel, max(mx, my, mz) <= PLAUSIBLE_MM)
            tally("P10_bbox_nondegenerate", rel,
                 max(mx, my, mz) > 0)

    for p in pools:
        rel = p["release"]
        tally("P2g_group_count_walk", rel, p["count_ok"] == "True")
        tally("P3g_group_finite", rel, p["vertex_finite"] == "True")
        tally("P4g_group_plausible", rel, p["vertex_plausible"] == "True")

    with (out_dir / "vertex-pool-claims.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["claim", "release", "observations", "passes", "rate"])
        for c in sorted(tallies):
            for rel in sorted(tallies[c]):
                obs, ok = tallies[c][rel]
                w.writerow([c, rel, obs, ok,
                            "%.3f" % (ok / obs if obs else 0)])

    print("== vertex pool scan ==")
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
