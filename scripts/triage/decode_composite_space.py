#!/usr/bin/env python3
"""Composite index space of the nested store, decoded (G6 stage 2a, #34).

Analysis-only byte decode of the L1 composite-space stores: the edge
tables, the scene-graph node territory that carries the extended element
space, and the curve-record families.  Reuses the shipped scanners
(``catpart.geometry``) read-only; no exporter/runner code is touched and
no fitness history is written.

Model (docs/evidence/2026-11-10-composite-space.md):

- Edge tables (E1/E2): every `10 24 04 ff ff 00 00 00` wrapper with
  sub-kind `01 02` opens a polyline table: a count field at +10 (one
  byte when it fits, `ff` escaping to a u32le at +11 -- the pool groups'
  P1g convention), then that many records `02 <n> <n refs>` (n = point
  count, 2 = a segment).  The reference width is per-group u8 or u16be
  (big-endian); the walk of `count` records must land EXACTLY on the
  next wrapper or the body end -- that end-alignment is the validator
  and decides the width.  The stage-1 census's `02 02 (u16be)(u16be)`
  6-byte records are the n=2 u16be case; the 157 "other 02 0X forms"
  are the n != 2 polylines.  Un-wrapped lists under `01 01 <count>`
  carry the same records (the box's 12 edges) and are validated by the
  same end-alignment.
- Scene-graph nodes (N1/N2): the pre-facet territory carries
  `04 04 fd ff` node records.  List-nodes (the ones holding the extended
  element space) carry the token `ff ff 02 00 01` followed by two
  counts in the P1g convention (u8, ff -> u32le): (element_count,
  edge_ref_bound).  element_count = max reference + 1 over the facet
  and edge records (declared space size); edge_ref_bound = the edge
  table's max endpoint + 1.  The node bodies hold per-rep point lists
  stored LEX-SORTED (x, y, z) with prefix compression: each point
  writes [x if changed][y if changed][z always] as f32le (verified
  point-by-point on 026d6726; loop-planarity under the merged space).
- No second vertex pool: `05 08 01` vertex records occur only inside
  `01 06` groups (checked on every audited store).
- Curve families (C1): the `00 00`-group bodies and `ff`-opener regions
  carry `33 3X` records behind a 7-byte header `<u8 a><u8 b><u16le
  id><00><u16le len>` (len = payload bytes; 33 32 also walks +40 B of
  [P][Q][P] f32le triples + a trailing |Q| length on the small-store
  form).  Their point semantics stay open (G2 unknown 5).

Outputs docs/evidence/data/composite-space-files.csv (one row per
composite store) and a summary on stdout.  Deterministic: sorted
manifest order; no wall-clock value enters the CSV.

Read-only; run with the worktree venv:
  .venv/bin/python -I scripts/triage/decode_composite_space.py
  [--include-sha16 HEX16,...]  restrict to these parts
"""

import argparse
import csv
import mmap
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"

sys.path.insert(0, str(ROOT / "scripts" / "triage"))
sys.path.insert(0, str(ROOT / "src"))

from catpart.geometry import facets, pool, store  # noqa: E402
from decode_nested_store import release_of  # noqa: E402

FULL_WRAP = pool.FULL_WRAP
EDGE_SUBKIND = b"\x01\x02"
NODE_MAGIC = b"\x04\x04\xfd\xff"
LIST_TOKEN = b"\xff\xff\x02\x00\x01"
THIRTY_MARK = b"\x30\x04\x04\xff\xff"

FIELDS = [
    "sha256",
    "split",
    "release",
    "size_bytes",
    "pool_size",
    "kinds",
    "edge_groups",
    "edge_width",
    "edge_walk_ok",
    "edge_records",
    "edge_max_ref",
    "unwrapped_lists",
    "unwrapped_records",
    "unwrapped_max_ref",
    "facet_records",
    "facet_max_ref",
    "facet_refs_beyond_pool",
    "node_count",
    "list_nodes",
    "element_count_declared",
    "edge_bound_declared",
    "max_ref_all",
    "count_law_ok",
    "count_law_eq",
    "refs_resolve",
    "count1_eq_pool_plus",
    "thirty_marks",
    "curve33_hits",
    "vrec_outside_pool",
    "audit_error",
]


def read_count(data, pos):
    """P1g count: one byte, ff escapes to u32le. Returns (value, next_pos)."""
    if data[pos] == 0xFF:
        return int.from_bytes(data[pos + 1 : pos + 5], "little"), pos + 5
    return data[pos], pos + 1


def walk_edge_records(data, pos, count, end):
    """Walk `count` polyline records `02 <n> <n refs>` from pos.

    Returns (refs, max_ref, ok) for the given width (the caller tries
    u8 then u16be).  ok requires every record to start with 0x02 and the
    walk to stop at or before `end` with all `count` records consumed.
    """
    refs = []
    max_ref = -1
    size = len(data)
    for _ in range(count):
        if pos >= end or data[pos] != 0x02:
            return refs, max_ref, False
        n = data[pos + 1]
        pos += 2
        if n > 4096 or pos + n > size:
            return refs, max_ref, False
        for j in range(n):
            if pos + 1 > size:
                return refs, max_ref, False
            r = int.from_bytes(data[pos : pos + 1], "big")
            refs.append(r)
            if r > max_ref:
                max_ref = r
            pos += 1
    return refs, max_ref, pos == end


def walk_edge_records_wide(data, pos, count, end):
    """Same walk with u16be references."""
    refs = []
    max_ref = -1
    size = len(data)
    for _ in range(count):
        if pos >= end or data[pos] != 0x02:
            return refs, max_ref, False
        n = data[pos + 1]
        pos += 2
        if n > 4096 or pos + 2 * n > size:
            return refs, max_ref, False
        for j in range(n):
            r = int.from_bytes(data[pos : pos + 2], "big")
            refs.append(r)
            if r > max_ref:
                max_ref = r
            pos += 2
    return refs, max_ref, pos == end


def decode_edge_group(data, group_off, body_hi, wraps_after):
    """Decode one `01 02` group; returns (width, records, max_ref, ok)."""
    count, pos = read_count(data, group_off + 10)
    end = wraps_after if wraps_after is not None else body_hi
    if not (0 < count <= 1_000_000):
        return None, 0, -1, False
    refs, max_ref, ok = walk_edge_records(data, pos, count, end)
    if ok:
        return 1, count, max_ref, True
    refs, max_ref, ok = walk_edge_records_wide(data, pos, count, end)
    if ok:
        return 2, count, max_ref, True
    return None, count, max(max_ref, -1), False


def find_unwrapped_lists(data, body_lo, body_hi, wrap_positions):
    """Find `01 01 <count>` polyline lists ending exactly on a wrapper."""
    ends = sorted(wrap_positions + [body_hi])
    out = []
    pos = body_lo
    while True:
        pos = data.find(b"\x01\x01", pos, body_hi - 3)
        if pos < 0:
            break
        count = data[pos + 2]
        if 1 <= count <= 5000:
            for end in ends:
                if end <= pos:
                    continue
                refs, max_ref, ok = walk_edge_records(data, pos + 3, count, end)
                if ok:
                    out.append((pos, count, max_ref, 1))
                    break
                refs, max_ref, ok = walk_edge_records_wide(data, pos + 3, count, end)
                if ok:
                    out.append((pos, count, max_ref, 2))
                    break
        pos += 1
    return out


def node_counts(data, lo, hi):
    """List-node census: token `ff ff 02 00 01` -> (element_count, edge_bound)."""
    out = []
    pos = lo
    while True:
        pos = data.find(LIST_TOKEN, pos, hi - 6)
        if pos < 0:
            break
        p = pos + 5
        c1, p = read_count(data, p)
        c2, p = read_count(data, p)
        if 0 < c1 <= 10_000_000:
            out.append((pos, c1, c2))
        pos += 1
    return out


def audit_part(mm, rel):
    """One part: composite-space audit. Returns the CSV row dict."""
    row = {k: "" for k in FIELDS}
    row["sha256"] = rel["sha256"]
    row["split"] = rel["split"]
    row["release"] = release_of(rel["detected_version"])
    size = mm.size()
    row["size_bytes"] = size
    d8_outer = int.from_bytes(mm[8:12], "big") if size >= 12 else 0
    blocks = store.valid_blocks(mm)
    VREC = b"\x05\x08\x01"
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
        composite = pool.has_composite_space(kinds)
        row["kinds"] = ";".join(k.hex() for k in kinds)
        row["pool_size"] = len([v for g in groups for v in g.vertices])
        if not composite:
            # record the pass/poolless context once, keep first store only
            if not row["edge_groups"]:
                row["edge_groups"] = 0
            continue
        wrap_positions = store.find_all(mm, FULL_WRAP, lo, hi)
        # ---- edge groups (wrapped 01 02)
        widths, recs, maxes, oks = [], 0, -1, True
        n_groups = 0
        for w in wrap_positions:
            if bytes(mm[w + 8 : w + 10]) != EDGE_SUBKIND:
                continue
            n_groups += 1
            after = next((p for p in wrap_positions if p > w), None)
            width, cnt, mx, ok = decode_edge_group(mm, w, hi, after)
            widths.append(width)
            recs += cnt
            maxes = max(maxes, mx)
            oks = oks and ok
        row["edge_groups"] = n_groups
        row["edge_width"] = ";".join(str(w) for w in widths)
        row["edge_walk_ok"] = oks
        row["edge_records"] = recs
        row["edge_max_ref"] = maxes
        # ---- unwrapped `01 01` lists
        ulists = find_unwrapped_lists(mm, lo, hi, wrap_positions)
        row["unwrapped_lists"] = len(ulists)
        row["unwrapped_records"] = sum(c for _, c, _, _ in ulists)
        row["unwrapped_max_ref"] = max((m for _, _, m, _ in ulists), default=-1)
        # ---- facets (shipped scanner, composite class)
        scan = facets.scan_facets(mm, lo, hi, clean_store=False)
        row["facet_records"] = len(scan.records)
        fmax = max((max(r.refs, default=-1) for r in scan.records), default=-1)
        row["facet_max_ref"] = fmax
        row["facet_refs_beyond_pool"] = sum(
            1 for r in scan.records if max(r.refs, default=-1) >= row["pool_size"]
        )
        # ---- scene-graph node territory (before the first facet header)
        hdrs = [m.start() for m in facets.STRIP_RE.finditer(mm, lo, hi)]
        node_hi = hdrs[0] if hdrs else hi
        nodes = store.find_all(mm, NODE_MAGIC, lo, node_hi)
        row["node_count"] = len(nodes)
        tokens = node_counts(mm, lo, node_hi)
        row["list_nodes"] = len(tokens)
        elem_decl = max((c1 for _, c1, _ in tokens), default=-1)
        bound_decl = max((c2 for _, _, c2 in tokens), default=-1)
        row["element_count_declared"] = elem_decl
        row["edge_bound_declared"] = bound_decl
        max_ref_all = max(row["edge_max_ref"], row["unwrapped_max_ref"], fmax)
        row["max_ref_all"] = max_ref_all
        # The declared count is the element-space SIZE; the top elements
        # need not be referenced by any record (026d6726: facets stop at
        # 117, edges reach 123, size 124).  The law is therefore
        # size == max ref + 1 when the top element is referenced and
        # size > max ref + 1 otherwise; the validator used here is the
        # pair (size >= max ref + 1, edge bound == edge max + 1).
        row["count_law_ok"] = bool(
            tokens
            and elem_decl >= max_ref_all + 1
            and (
                bound_decl == row["edge_max_ref"] + 1
                or (row["edge_max_ref"] == -1 and bound_decl <= 1)
            )
        )
        row["count_law_eq"] = bool(tokens and elem_decl == max_ref_all + 1)
        row["refs_resolve"] = bool(tokens and fmax < elem_decl) if tokens else ""
        row["count1_eq_pool_plus"] = bool(tokens and elem_decl == row["pool_size"])
        # ---- 30-records and curve census
        row["thirty_marks"] = len(store.find_all(mm, THIRTY_MARK, lo, hi))
        c33 = 0
        for fam in (0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39):
            c33 += len(store.find_all(mm, bytes([0x33, fam]), lo, hi))
        row["curve33_hits"] = c33
        # ---- no second pool: 05 08 01 outside 01 06 groups, as 15-B runs
        covered = []
        for g in groups:
            q = g.offset + (15 if mm[g.offset + 10] == 0xFF else 11)
            covered.append((q, q + 15 * len(g.vertices)))
        outside_runs = 0
        pos = lo
        while True:
            pos = mm.find(VREC, pos, hi)
            if pos < 0:
                break
            if not any(a <= pos < b for a, b in covered):
                # run detection: >= 3 consecutive 15-B-stride vertex records
                k = pos
                run = 0
                while k + 15 <= hi and bytes(mm[k : k + 3]) == VREC:
                    run += 1
                    k += 15
                if run >= 3:
                    outside_runs += 1
                pos = k if run >= 3 else pos + 1
            else:
                pos += 1
        row["vrec_outside_pool"] = outside_runs
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
    out_path = out_dir / "composite-space-files.csv"
    with out_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out_rows)
    print(f"wrote {out_path} ({len(out_rows)} rows)")
    summarize(out_rows)
    return 0


def summarize(rows):
    """Per-claim rates over the audited stores."""
    comp = [
        r
        for r in rows
        if r["kinds"]
        and ("0102" in r["kinds"] or r["kinds"].startswith("ff") or ";ff" in r["kinds"])
    ]
    print(
        f"== composite-space audit: {len(comp)} composite stores of {len(rows)} parts"
    )
    aerr = [r for r in rows if r["audit_error"]]
    print(f"  audit errors: {len(aerr)}")
    if not comp:
        return

    def n(row, key):
        v = row.get(key, "")
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    # E1: edge walk exactness
    with_edges = [r for r in comp if n(r, "edge_groups")]
    walk_ok = [r for r in with_edges if str(r["edge_walk_ok"]) == "True"]
    print(
        f"  E1 edge walk lands exactly: {len(walk_ok)}/{len(with_edges)} "
        f"edge-carrying stores"
    )
    wcnt = Counter()
    for r in with_edges:
        for w in set(str(r["edge_width"]).split(";")):
            wcnt[w] += 1
    print(f"  E1b edge widths (stores carrying each): {dict(wcnt)}")
    # unwrapped lists
    with_ul = [r for r in comp if n(r, "unwrapped_lists")]
    print(
        f"  E3 unwrapped 01 01 lists: {len(with_ul)}/"
        f"{len(comp)} stores, "
        f"records {sum(n(r, 'unwrapped_records') or 0 for r in with_ul)}"
    )
    # N2: count law
    with_tok = [r for r in comp if n(r, "list_nodes")]
    law_ok = [r for r in with_tok if str(r["count_law_ok"]) == "True"]
    law_eq = [r for r in with_tok if str(r["count_law_eq"]) == "True"]
    print(
        f"  N2 list-node token present: {len(with_tok)}/{len(comp)}; "
        f"count law (size >= max ref + 1, edge bound == edge max + 1): "
        f"{len(law_ok)}/{len(with_tok)}; "
        f"strict (size == max ref + 1): {len(law_eq)}/{len(with_tok)}"
    )
    res = [r for r in with_tok if str(r["refs_resolve"]) == "True"]
    print(f"  N3 facet refs resolve in the declared space: {len(res)}/{len(with_tok)}")
    eqp = [r for r in with_tok if str(r["count1_eq_pool_plus"]) == "True"]
    print(
        f"  N4 element_count == pool (clean-store degenerate): {len(eqp)}/{len(with_tok)}"
    )
    # no second pool
    outside = [r for r in comp if n(r, "vrec_outside_pool")]
    print(
        f"  N5 stores with >= 3 vertex records outside 01 06 groups: "
        f"{len(outside)}/{len(comp)}"
    )
    # 30 / curve census
    t30 = [r for r in comp if n(r, "thirty_marks")]
    print(
        f"  C2 30 04 04 ff ff marks: {len(t30)}/{len(comp)} stores, "
        f"total {sum(n(r, 'thirty_marks') or 0 for r in t30)}"
    )
    c33 = [r for r in comp if n(r, "curve33_hits")]
    print(
        f"  C1 33 3X curve families: {len(c33)}/{len(comp)} stores, "
        f"total {sum(n(r, 'curve33_hits') or 0 for r in c33)}"
    )
    print(
        f"  held-out composite rows: {sum(1 for r in comp if r['split'] == 'held-out')}"
    )


if __name__ == "__main__":
    sys.exit(main())
