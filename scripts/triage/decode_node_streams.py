#!/usr/bin/env python3
"""List-node point streams of the composite stores, decoded (G6 stage 2b/2c, #34).

Byte decode of the scene-graph list nodes' point streams
(``04 04 fd ff`` node records carrying the ``ff ff 02 00 01`` token) and
of the merge law that turns them into the composite element space.
Since stage 2c the decode machinery lives in the shipped
``catpart.geometry.composite`` (the exporter's integration, fail-closed
under the same law); this script is its corpus runner.  No fitness
history is written.

Model (docs/evidence/2026-11-10-node-streams.md + the stage-2c
refinements dated 2026-11-11):

- Point stream law (P1, refined): the list node's payload = header +
  token ``ff ff 02 00 01`` + the declared counts + a zero block + a
  2-bit per-element table of ``ceil(element_count / 4) + 1`` bytes +
  the point region + a trailing region.  The region is a
  suffix-after-LCP coded point list (f32le) whose initial LCP state
  carries x = 0.0 implicitly (the first point writes ``[x][y][z]`` only
  when its x differs from 0, else ``[y][z]``), organised as a
  concatenation of lex-nondecreasing runs (each run starts with a full
  write and may reset x).  The region start is predicted from the
  measured table layout and probed with a value-DP scored on pool
  containment; the count law (element_count = node points + curve
  entries, curve entries >= 0) prunes over-parses.
- Merge law (M1/M2b): the element space is the lex-sorted merge of the
  pool vertices and the list node's decoded points (plus the
  curve-record points, values open U4); facet and edge references are
  0-based positions in that sequence.  The decoder validates per store
  through the plane test: a facet record's loop references must map,
  order-preservingly with a monotone non-negative curve-shift, onto
  the decoded points sharing the loop's plane coordinate -- on 026d6726
  the ``01 4a 07 ff`` record (normal (0, 0, -1)) maps all 32 referenced
  positions onto the 32 z = 2.1 points with shift profile 1-4-2-1-2-2-2-1-3-7-1
  (26 curve entries = element_count 124 - 98 node points) and every
  loop decodes exactly planar.

Outputs docs/evidence/data/node-streams-files.csv (one row per
composite store) and a summary on stdout.  Deterministic: sorted
manifest order; no wall-clock value enters the CSV.

Read-only over the corpus; run with the worktree venv:
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
from catpart.geometry import composite  # noqa: E402
from decode_nested_store import release_of  # noqa: E402

FIELDS = [
    "sha256", "split", "release", "size_bytes", "pool_size",
    "list_node_bytes", "elem_decl", "edge_bound_decl", "node_form",
    "point_region_bytes", "pts_decoded", "f32_writes", "pool_in_list",
    "pool_coverage", "decode_ok", "decode_stage", "curve_entries",
    "plane_records", "plane_loops",
    "plane_loops_ok", "curve_shift_total", "audit_error",
]


def nice(v):
    return v == v and 1e-6 < abs(v) < 1e9


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
            if not loop:
                # degenerate zero-count loop: no refs to match (2026-11-10
                # #34 review F1 — the crash that dropped 8be9434a)
                continue
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
                svals = [s for _li, s in states if s >= 0]
                if feasible and svals:
                    ok = True
                    shift_total = min(svals)
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
        ln = composite.find_list_node(mm, lo, node_hi)
        if ln is None:
            return row
        payload, c1, c2 = ln
        row["list_node_bytes"] = len(payload)
        row["elem_decl"] = c1
        row["edge_bound_decl"] = c2
        row["node_form"] = "big" if len(payload) > 4096 else "small"
        if row["node_form"] == "small":
            cands = composite.decode_node_points(payload, c1, sorted(poolv))
            ps = set(poolv)
            best_pts = None
            best_stage = None
            best_end = None
            for pts, stage, end in cands:
                hits = len(ps & set(pts))
                if best_pts is None or hits > len(ps & set(best_pts)) or (
                    hits == len(ps & set(best_pts)) and len(pts) > len(best_pts)
                ):
                    best_pts, best_stage, best_end = pts, stage, end
                if hits == len(ps):
                    break
            if best_pts is not None:
                plo = composite.predict_region_start(payload, c1)
                row["point_region_bytes"] = (best_end - plo) if best_end and plo >= 0 else ""
                row["pts_decoded"] = len(best_pts)
                row["f32_writes"] = (
                    (best_end - plo) // 4
                    if best_end and plo >= 0 and best_end > plo
                    else ""
                )
                hits = len(ps & set(best_pts))
                row["pool_in_list"] = hits
                row["pool_coverage"] = round(hits / len(poolv), 4) if poolv else ""
                row["decode_ok"] = hits == len(poolv)
                row["decode_stage"] = best_stage
                row["curve_entries"] = c1 - len(best_pts)
                recs, loops, lok, shift = plane_test(mm, best_pts, lo, hi, poolv)
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
    print(f"  small-form decode with pool fully contained: {len(dec)}/{len(small)}")
    stages = {}
    for r in dec:
        stages[str(r["decode_stage"])] = stages.get(str(r["decode_stage"]), 0) + 1
    print(f"  decode stages: {stages}")
    pr = [r for r in have if str(r["plane_loops"]) not in ("", "0")]
    pok = [r for r in pr if str(r["plane_loops_ok"]) == str(r["plane_loops"])]
    print(f"  plane-ref monotone matching: {len(pok)}/{len(pr)} stores with "
          f"normal-carrying records")
    held = [r for r in have if r["split"] == "held-out"]
    print(f"  held-out rows: {len(held)}")


if __name__ == "__main__":
    sys.exit(main())

