#!/usr/bin/env python3
"""List-node point streams of the composite stores, decoded (G6 stage 2b, #34).

Analysis-only byte decode of the scene-graph list nodes' point streams
(``04 04 fd ff`` node records carrying the ``ff ff 02 00 01`` token) and
of the merge law that turns them into the composite element space.
Reuses the shipped scanners (``catpart.geometry``) read-only; no
exporter/runner code is touched and no fitness history is written.

Model (docs/evidence/2026-11-10-node-streams.md):

- Point stream law (P1): the list node's point region is a
  lex-nondecreasing point list stored with suffix-after-LCP prefix
  coding: the first point writes [x][y][z] (f32le); each following
  point writes only the suffix after the longest common prefix shared
  with the previous point ([y][z] when x repeats, [z] when (x, y)
  repeats).  Byte-exact on 026d6726 (98 points, pool 10/10, 203 f32
  writes, region ends at the 32-B table's boundary), and the same law
  organises the big-store streams (70b59f2a: x-group segments traced
  through all 40 pool x values).
- Merge law (M1, the recovered construction): the element space is the
  lex-sorted merge of the pool vertices and the list node's decoded
  points (plus the curve-record points), the pool absorbed because the
  node list re-lists the pool vertices verbatim; facet and edge
  references are 0-based positions in that sorted sequence.  The
  decoder validates this per store through the plane test: a facet
  record's loop references must map, in order-preserving fashion with a
  monotone non-negative curve-shift, onto the decoded points sharing
  the loop's plane coordinate -- on 026d6726 the ``01 4a 07 ff``
  record (normal (0, 0, -1)) maps all 32 referenced positions onto the
  32 z = 2.1 points with shift profile 1-4-2-1-2-2-2-1-3-7-1 (26 curve
  entries = element_count 124 - 98 node points) and every loop decodes
  exactly planar.

Outputs docs/evidence/data/node-streams-files.csv (one row per
composite store) and a summary on stdout.  Deterministic: sorted
manifest order; no wall-clock value enters the CSV.

Read-only; run with the worktree venv:
  .venv/bin/python -I scripts/triage/decode_node_streams.py
  [--include-sha16 HEX16,...]  restrict to these parts
"""

import argparse
import csv
import mmap
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"

sys.path.insert(0, str(ROOT / "scripts" / "triage"))
sys.path.insert(0, str(ROOT / "src"))

from catpart.geometry import facets, pool, store  # noqa: E402
from decode_nested_store import release_of  # noqa: E402

NODE_MAGIC = b"\x04\x04\xfd\xff"
LIST_TOKEN = b"\xff\xff\x02\x00\x01"
TAIL_MARK = b"\x00\x04\x02\x0a"

FIELDS = [
    "sha256", "split", "release", "size_bytes", "pool_size",
    "list_node_bytes", "elem_decl", "edge_bound_decl", "node_form",
    "point_region_bytes", "pts_decoded", "f32_writes", "pool_in_list",
    "pool_coverage", "decode_ok", "plane_records", "plane_loops",
    "plane_loops_ok", "curve_shift_total", "audit_error",
]


def read_count(data, pos):
    """P1g count: one byte, ff escapes to u32le. Returns (value, next_pos)."""
    if data[pos] == 0xFF:
        return int.from_bytes(data[pos + 1 : pos + 5], "little"), pos + 5
    return data[pos], pos + 1


def f32(data, pos):
    return struct.unpack_from("<f", data, pos)[0]


def nice(v):
    return v == v and 1e-6 < abs(v) < 1e9


def find_list_node(mm, lo, hi):
    """Return (payload, elem_decl, edge_bound) of the list node.

    Every node carries the ``ff ff 02 00 01`` token with the declared
    (element_count, edge_ref_bound) pair; the LIST node is the one
    whose payload carries the point region -- the largest payload.
    """
    best = None
    pos = lo
    while True:
        pos = mm.find(NODE_MAGIC, pos, hi)
        if pos < 0:
            break
        end = mm.find(NODE_MAGIC, pos + 4, hi)
        if end < 0:
            end = hi
        payload = bytes(mm[pos + 4 : end])
        tok = payload.find(LIST_TOKEN)
        if 0 <= tok <= 64:
            p = tok + 5
            c1, p = read_count(payload, p)
            c2, p = read_count(payload, p)
            if 0 < c1 <= 10_000_000:
                if best is None or len(payload) > len(best[0]):
                    best = (payload, c1, c2)
        pos += 1
    return best


def candidate_starts(payload, pool_sorted):
    """Candidate point-region starts, probed and ranked.

    The region opens at the first full write of the list's lex-min
    point -- which may be an extra rather than the pool's lex-min --
    so every 4-aligned offset after the zero block that opens a
    f32-plausible run is a candidate; each is probed by a greedy
    lex-constrained decode scored on pool hits, and the best few are
    returned in payload order.
    """
    tail = payload.rfind(TAIL_MARK)
    hi = tail - 4 if tail > 0 else len(payload)
    q = payload.find(b"\xff\xff\x02\x00\x01")
    if q < 0:
        return [], hi
    p = q + 5
    _, p = read_count(payload, p)
    _, p = read_count(payload, p)
    while p + 4 <= len(payload) and payload[p : p + 4] == b"\x00\x00\x00\x00":
        p += 4
    pool_set = set(pool_sorted)
    cands = []
    # anchor: the pool's lex-min re-listed verbatim as a full write
    if pool_sorted:
        axb = struct.pack("<fff", *pool_sorted[0])
        a = payload.find(axb, p, hi)
        if a >= 0:
            cands.append((a, 99))
    pos = p
    # region end: the last long f32-plausible run before the tail
    run_start = None
    run_len = 0
    last_long = None
    scan = p
    while scan + 4 <= hi:
        if nice(f32(payload, scan)):
            if run_len == 0:
                run_start = scan
            run_len += 1
        else:
            if run_len >= 16:
                last_long = run_start + 4 * run_len
            run_len = 0
        scan += 4
    if run_len >= 16:
        last_long = run_start + 4 * run_len
    if last_long is None:
        return [], hi
    hi = last_long
    while pos + 48 <= hi:
        # a genuine run start follows non-plausible bytes (the node table)
        if (
            pos == p or not nice(f32(payload, pos - 4))
        ) and all(nice(f32(payload, pos + 4 * k)) for k in range(3)):
            score = _probe_score(payload, pos, min(192, hi - pos), pool_set)
            if score >= 2:
                cands.append((pos, score))
                if score >= 4:
                    break
        pos += 4
    cands.sort(key=lambda t: (-t[1], t[0]))
    return [c[0] for c in cands[:8]], hi


def _probe_score(data, start, span, pool_set):
    """Bounded free-end DP probe: decode from `start` over `span` bytes,
    accept every parse end, score the best parse on pool hits."""
    end = start + span
    best = [0]
    nodes = [0]

    def dfs(pos, px, py, pz, hits):
        if nodes[0] > 30_000:
            return
        nodes[0] += 1
        if pos >= end:
            best[0] = max(best[0], hits)
            return
        if pos + 12 <= end:
            x, y, z = f32(data, pos), f32(data, pos + 4), f32(data, pos + 8)
            if (nice(x) and nice(y) and nice(z)
                    and (px is None
                         or (x >= px and (x > px or y >= py)
                             and (x > px or y > py or z >= pz)))):
                dfs(pos + 12, x, y, z,
                    hits + (1 if (x, y, z) in pool_set else 0))
        if px is not None and pos + 8 <= end:
            y, z = f32(data, pos), f32(data, pos + 4)
            if nice(y) and nice(z) and y >= py and (y > py or z >= pz):
                dfs(pos + 8, px, y, z, hits)
        if px is not None and pos + 4 <= end:
            z = f32(data, pos)
            if nice(z) and (pz is None or z >= pz):
                dfs(pos + 4, px, py, z, hits)

    x0, y0, z0 = f32(data, start), f32(data, start + 4), f32(data, start + 8)
    if not (nice(x0) and nice(y0) and nice(z0)):
        return -1
    dfs(start + 12, x0, y0, z0, 1 if (x0, y0, z0) in pool_set else 0)
    return best[0]


def decode_points(data, start, end, node_cap=2_000_000):
    """Suffix-after-LCP decode of [start, end), lex-constrained.

    Depth-free DP: records every parse that consumes exactly to `end`
    (up to a solution cap) and returns them; the caller scores parses
    on pool containment.  Deterministic.
    """
    sols = []
    nodes = [0]
    seen = set()

    def dfs(pos, px, py, pz, path):
        if nodes[0] > node_cap or len(sols) > 4096:
            return
        nodes[0] += 1
        if pos == end:
            key = tuple(path)
            if key not in seen:
                seen.add(key)
                sols.append(list(path))
            return
        if pos > end:
            return
        if (end - pos) % 4:
            return
        # xyz (full lex triple >= previous)
        if pos + 12 <= end:
            x = f32(data, pos)
            y = f32(data, pos + 4)
            z = f32(data, pos + 8)
            if (
                nice(x) and nice(y) and nice(z)
                and (px is None
                     or (x >= px and (x > px or y >= py)
                         and (x > px or y > py or z >= pz)))
            ):
                path.append((x, y, z))
                dfs(pos + 12, x, y, z, path)
                path.pop()
        # yz (x repeats: y >= py, and if y equal then z >= pz)
        if px is not None and pos + 8 <= end:
            y = f32(data, pos)
            z = f32(data, pos + 4)
            if nice(y) and nice(z) and y >= py and (y > py or z >= pz):
                path.append((px, y, z))
                dfs(pos + 8, px, y, z, path)
                path.pop()
        # z (x, y repeat: z >= pz)
        if px is not None and pos + 4 <= end:
            z = f32(data, pos)
            if nice(z) and (pz is None or z >= pz):
                path.append((px, py, z))
                dfs(pos + 4, px, py, z, path)
                path.pop()

    x0 = f32(data, start)
    y0 = f32(data, start + 4)
    z0 = f32(data, start + 8)
    if not (nice(x0) and nice(y0) and nice(z0)):
        return None, 0
    dfs(start + 12, x0, y0, z0, [(x0, y0, z0)])
    if not sols:
        return None, 0
    return sols, nodes[0]


def plane_test(data, pts, lo, hi, pool_sorted):
    """Flat-face merge-law test over the store's facet records.

    For each facet record that carries a 12-B normal, take its loops'
    references, find the decoded points sharing a constant coordinate
    (the plane named by the normal's dominant axis), and require an
    order-preserving matching with a monotone non-negative shift
    (the curve entries inserted before each plane point).  Returns
    (records, loops, loops_ok, shift_total).
    """
    if not pts:
        return 0, 0, 0, ""
    hdrs = [m.start() for m in facets.STRIP_RE.finditer(data, lo, hi)]
    recs = 0
    loops_ok = 0
    loops = 0
    shift_total = None
    for i, o in enumerate(hdrs):
        mk = data[o + 1]
        if mk != 0x4A:
            continue
        nxt = hdrs[i + 1] if i + 1 < len(hdrs) else hi
        header_len = 4 if data[o + 3] == 0xFF else 5
        n = int.from_bytes(data[o + header_len : o + header_len + 4], "little")
        base = o + header_len + 4 + 12
        counts = None
        for k in range(1, 10):
            cs = [data[base + j] for j in range(k)]
            if sum(cs) == n and base + k + n <= nxt:
                counts = cs
                break
        if counts is None:
            continue
        recs += 1
        normal = struct.unpack("<fff", data[o + header_len + 4 : o + header_len + 16])
        axis = max(range(3), key=lambda k: abs(normal[k]))
        refs = list(data[base + len(counts) : base + len(counts) + n])
        off = 0
        for c in counts:
            loop = sorted(set(refs[off : off + c]))
            off += c
            loops += 1
            from collections import Counter

            cc = Counter(p[axis] for p in pts)
            ok = False
            for val, _cnt in cc.most_common(8):
                idxs = [j for j, p in enumerate(pts) if p[axis] == val]
                if len(idxs) < len(loop):
                    continue
                # monotone matching via DP: refs ascending onto plane
                # indices, shift = ref - idx non-negative, non-decreasing
                m = len(loop)
                states = {(-1, -1)}  # (last idx, last shift)
                for ref in loop:
                    nxt = set()
                    for li, ls in states:
                        for idx in idxs:
                            if idx <= li:
                                continue
                            s = ref - idx
                            if s < 0 or (ls >= 0 and s < ls):
                                continue
                            nxt.add((idx, s))
                    states = nxt
                    if not states:
                        break
                feasible = bool(states)
                if feasible:
                    ok = True
                    shift_total = min(s for _li, s in states if s >= 0)
                    break
            if ok:
                loops_ok += 1
    return recs, loops, loops_ok, shift_total


def audit_part(mm, rel):
    """One part: node-stream audit. Returns the CSV row dict."""
    row = {k: "" for k in FIELDS}
    row["sha256"] = rel["sha256"]
    row["split"] = rel["split"]
    row["release"] = release_of(rel["detected_version"])
    row["size_bytes"] = mm.size()
    d8_outer = int.from_bytes(mm[8:12], "big") if mm.size() >= 12 else 0
    blocks = store.valid_blocks(mm)
    for blk in [b for b, nm in blocks if nm == "CATStdCont"]:
        try:
            span = store.locate_store(mm, blk, blocks, d8_outer)
        except Exception:  # noqa: BLE001 - recorded per part
            continue
        if span is None:
            continue
        lo, hi = span.body_lo, span.body_hi
        try:
            groups, kinds = pool.scan_pool_groups(mm, lo, hi)
        except Exception:  # noqa: BLE001 - recorded per part
            continue
        if not pool.has_composite_space(kinds):
            continue
        poolv = [v for g in groups for v in g.vertices]
        row["pool_size"] = len(poolv)
        hdrs = [m.start() for m in facets.STRIP_RE.finditer(mm, lo, hi)]
        node_hi = hdrs[0] if hdrs else hi
        ln = find_list_node(mm, lo, node_hi)
        if ln is None:
            return row
        payload, c1, c2 = ln
        row["list_node_bytes"] = len(payload)
        row["elem_decl"] = c1
        row["edge_bound_decl"] = c2
        row["node_form"] = "big" if len(payload) > 4096 else "small"
        cands, phi = candidate_starts(payload, sorted(poolv))
        if not cands:
            return row
        plo = cands[0]
        row["point_region_bytes"] = phi - plo
        best_pts = None
        best_key = None
        best_start = plo
        if row["node_form"] == "small":
            for cand in cands:
                sols, _ = decode_points(payload, cand, phi)
                if not sols:
                    continue
                ps = set(poolv)
                pts = max(sols, key=lambda s: sum(1 for p in s if p in ps))
                hits = sum(1 for p in pts if p in ps)
                key = (hits / len(poolv) if poolv else 0, len(pts))
                if best_key is None or key > best_key:
                    best_key = key
                    best_pts = pts
                    best_start = cand
            if best_pts is not None:
                plo = best_start
                pts = best_pts
                row["point_region_bytes"] = phi - plo
                row["pts_decoded"] = len(pts)
                row["f32_writes"] = (phi - plo) // 4
                ps = set(poolv)
                hits = sum(1 for p in pts if p in ps)
                row["pool_in_list"] = hits
                row["pool_coverage"] = round(hits / len(poolv), 4) if poolv else ""
                row["decode_ok"] = hits == len(poolv)
                recs, loops, lok, shift = plane_test(mm, pts, lo, hi, poolv)
                row["plane_records"] = recs
                row["plane_loops"] = loops
                row["plane_loops_ok"] = lok
                row["curve_shift_total"] = shift
        return row
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--include-sha16", default="")
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    args = ap.parse_args()
    rows_in = [
        r
        for r in csv.DictReader(MANIFEST.open())
        if r["split"] in ("dev", "held-out") and r["kind"] == "part"
    ]
    if args.include_sha16:
        want = {h for h in args.include_sha16.split(",") if h}
        rows_in = [r for r in rows_in if r["sha256"][:16] in want]
    rows_in.sort(key=lambda r: r["sha256"])
    out_rows = []
    for r in rows_in:
        path = ROOT / r["local_path"]
        with path.open("rb") as fh:
            mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                row = audit_part(mm, r)
            except Exception as exc:  # noqa: BLE001 - recorded per part
                row = {k: "" for k in FIELDS}
                row["sha256"] = r["sha256"]
                row["split"] = r["split"]
                row["audit_error"] = f"{type(exc).__name__}: {exc}"
            finally:
                mm.close()
        out_rows.append(row)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "node-streams-files.csv"
    with out_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out_rows)
    print(f"wrote {out_path} ({len(out_rows)} rows)")
    summarize(out_rows)
    return 0


def summarize(rows):
    """Per-claim rates over the audited stores."""
    have = [r for r in rows if r.get("node_form") in ("small", "big")]
    print(f"== node-stream audit: {len(have)} composite stores with a list node "
          f"of {len(rows)} parts")
    aerr = [r for r in rows if r["audit_error"]]
    print(f"  audit errors: {len(aerr)}")
    if not have:
        return
    big = [r for r in have if r["node_form"] == "big"]
    small = [r for r in have if r["node_form"] == "small"]
    print(f"  forms: small {len(small)}, big {len(big)}")
    dec = [r for r in small if str(r["decode_ok"]) == "True"]
    print(f"  small-form DP decode with pool fully contained: {len(dec)}/{len(small)}")
    cov = [r for r in small if str(r["pool_coverage"]) not in ("",)
           and float(r["pool_coverage"]) >= 0.999]
    print(f"  small-form pool coverage >= 0.999: {len(cov)}/{len(small)}")
    pr = [r for r in have if str(r["plane_loops"]) not in ("", "0")]
    pok = [r for r in pr if str(r["plane_loops_ok"]) == str(r["plane_loops"])]
    print(f"  plane-ref monotone matching: {len(pok)}/{len(pr)} stores with "
          f"normal-carrying records")
    held = [r for r in have if r["split"] == "held-out"]
    print(f"  held-out rows: {len(held)}")


if __name__ == "__main__":
    sys.exit(main())
