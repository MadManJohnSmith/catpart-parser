#!/usr/bin/env python3
"""Decode/verify the mixed-write float stream (stage 8, #34).

Population: the 93 fail-closed walk-mismatch composite stores of the
stage-6 raw trigger probe (verdicts start-unpinned / weak-fit /
pool-unabsorbed) -- the stage-7 note's 68 unexplained plus the 14
pair-variant / 10 partial / 1 tiled stores, which this reading
re-measures under one law.

The stage-8 finding this script pins, from observed bytes only
(docs/evidence/2026-11-12-mixedwrite-reps.md carries the law):

  1. LOCATOR ARTIFACT (the mass's root cause): the exporter's list-node
     window ends at the FIRST STRIP_RE match (composite.decode_
     composite_store: node_hi = hdrs[0]).  STRIP_RE (01 [41-4f] ? ff)
     false-matches INSIDE point regions and pool wrappers, so on these
     stores the window cuts the real list node: the raw-array law's
     12*elem_decl span no longer fits (ccbb7862 class), or the window
     retains only 67-B stub nodes whose walk fails at element 0
     (0f18f772 class).  On the FULL node window (NODE_MAGIC to
     NODE_MAGIC -- the exporter's own _scan_token_nodes convention)
     the committed decoders parse the payloads directly.

  2. PER-REP DECOMPOSITION COMPOSES WITH BOTH ENCODINGS: a store body
     is a sequence of reps (the stage-5 law); rep k's token node
     payload is EITHER the stage-3b table layout ([zero block][2-bit
     table][P1g count][mixed-write region]) OR the stage-4a raw-array
     layout ([tail field][elem_decl x [x][y][z] stride 12][FF escape]
     [count3]).  Both decode with the COMMITTED decoders on the full
     window; no new write-shape law is needed for the stores this
     census covers.

  3. The k-th pool group re-lists verbatim (or within the stage-4b
     noise tolerance) in the k-th decoded rep's region, and the gated
     record references resolve inside their OWN rep's element count
     (M2b identity per rep).

Verdicts per store (fail-closed, named):
  reps-full        : every pool group paired (diagonal, body order)
                     to a decoded rep, absorbed verbatim/noise, and
                     every gated ref in-bounds per rep.
  reps-partial     : some pool groups unpaired (their rep's decode
                     failed -- reason named) or refs out of bounds.
  unexplained      : no pool group pairs to any decoded rep.

Read-only over the corpus (symlink).  Analysis only: src/ untouched.
Run:  python3 -I scripts/triage/mixedwrite_decode.py [--sha16 SUBSTR]
Out:  docs/evidence/data/mixedwrite-reps-files.csv
      docs/evidence/data/mixedwrite-reps-nodes.csv
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
PROBE_CSV = OUT_DIR / "stage6-raw-trigger-probe.csv"
MC_CSV = OUT_DIR / "multipart-container-files.csv"

sys.path.insert(0, str(ROOT / "scripts" / "triage"))
sys.path.insert(0, str(ROOT / "src"))

from catpart.geometry import composite, pool, store  # noqa: E402

NOISE_REL = 1e-5  # the stage-4b REP-noise tolerance
RAW_MAX_START = 64
GATED = (0x42, 0x49, 0x4A, 0x4C)

STORE_FIELDS = [
    "sha256", "split", "verdict_stage6", "verdict_stage7", "body_bytes",
    "payload_full_bytes", "payload_window_bytes", "first_strip_hdr",
    "pool_groups", "pool_sizes", "token_nodes", "decoded_reps",
    "table_reps", "raw_reps", "flat_reps", "failed_nodes", "diag_paired",
    "abs_map", "pool_in_region", "pool_subnode_only",
    "paired_pools", "unpaired_pools", "noise_pools", "refs_ok",
    "refs_bad", "verdict", "residue", "note",
]

NODE_FIELDS = [
    "sha256", "node_pos", "payload_bytes", "c1", "c2", "law", "pts",
    "skips", "region_end_rel", "write_count", "absorbed_pool_hits",
    "pool_group", "gated_max_ref", "gated_refs_ok", "failure",
]


def raw_probe(payload, c1):
    """The stage-4a raw-array law probe on a full node payload.

    Returns (start, nice_rate, asc_rate) for the UNIQUE FF-escape
    candidate, or None.  The committed criteria (classify_residue_
    family.raw_scan / composite.decode_raw_array): 4-aligned starts
    32..64, trail byte payload[s + 12*c1] == 0xFF."""
    cands = [
        s
        for s in range(32, RAW_MAX_START + 1, 4)
        if s + 12 * c1 < len(payload) and payload[s + 12 * c1] == 0xFF
    ]
    if len(cands) != 1:
        return None
    s = cands[0]
    nicec = 0
    xs = []
    for k in range(c1):
        x, y, z = struct.unpack_from("<fff", payload, s + 12 * k)
        if composite._raw_nice(x) and composite._raw_nice(y) and composite._raw_nice(z):
            nicec += 1
        xs.append(x)
    rate = nicec / c1
    asc = (
        sum(1 for a, b in zip(xs, xs[1:]) if b >= a - 1e-6) / (c1 - 1)
        if c1 > 1
        else 1.0
    )
    return s, rate, asc


def table_decode(payload, c1, counts_end):
    """The stage-3b table walk with the zero-block extent as a candidate.

    Mirrors the committed decode_region walk exactly (SHAPES, _nice,
    the write_count <= 3*c1 sanity, walk-exact end), except the zero
    block after the counts may span 1..k 4-byte groups: the committed
    layout() skips ALL consecutive zero groups, which on these stores
    eats the table's own leading zero bytes when the region opens with
    >= 4 full-write slots (stage-8 finding; the misaligned count reads
    are the 'declared 0' / 'declared 194' walk failures the exporter
    reports).  counts_end = the P1g counts' end (token+5+counts), so
    1-B-count stores decode too (the committed layout() computes it
    the same way).  Returns (extent, pts, skips, region_end_rel, count)
    for a UNIQUE walk-exact extent, ('ambiguous', ...) when several
    decode, or None."""
    if payload[counts_end : counts_end + 4] != b"\x00\x00\x00\x00":
        return None
    ext = 1
    while payload[counts_end + 4 * ext : counts_end + 4 + 4 * ext] == b"\x00\x00\x00\x00":
        ext += 1
    results = []
    table_len = (c1 + 3) // 4
    for e in range(1, ext + 1):
        table_start = counts_end + 4 * e
        count_pos = table_start + table_len
        if count_pos >= len(payload):
            continue
        try:
            wc, region_start = composite.read_count(payload, count_pos)
        except (IndexError, struct.error):
            continue
        if wc > 3 * c1:
            continue
        region_end = region_start + 4 * wc
        if region_end > len(payload):
            continue
        pos = region_start
        pts = skips = 0
        ok = True
        x = y = z = 0.0  # the initial LCP state is the origin (P1i)
        for i in range(c1):
            v = (payload[table_start + i // 4] >> (2 * (i % 4))) & 3
            shape = composite.SHAPES[v]
            if shape == 0:
                skips += 1
                continue
            if pos + 4 * shape > region_end:
                ok = False
                break
            if shape == 3:
                x, y, z = struct.unpack_from("<fff", payload, pos)
            elif shape == 2:
                y, z = struct.unpack_from("<ff", payload, pos)
            else:
                z = struct.unpack_from("<f", payload, pos)[0]
            vals = (x, y, z) if shape == 3 else ((y, z) if shape == 2 else (z,))
            if not all(composite._nice(c) for c in vals):
                ok = False
                break
            pos += 4 * shape
            pts += 1
        if ok and pos == region_end:
            results.append((e, pts, skips, region_end, wc))
    if len(results) == 1:
        return results[0]
    if len(results) > 1:
        return ("ambiguous", results)
    return None


def noise_eq(a, b):
    """Per-coordinate relative tolerance 1e-5 (the stage-4b REP-noise
    law); exact f32 equality also passes.  FULL triples only -- a
    partial write is not a coordinate match."""
    if len(a) != len(b):
        return False
    for u, v in zip(a, b):
        if u == v:
            continue
        d = abs(u - v)
        if d > NOISE_REL * max(1e-30, abs(u), abs(v)):
            return False
    return True


def close_eq(points, pt):
    for q in points:
        if q == pt or noise_eq(q, pt):
            return True
    return False


def decode_node(payload, c1, counts_end, poolv=()):
    """Decode one token-node payload with the committed laws.

    Returns (law, pts, skips, region_end_rel, write_count, failure):
    law in {'table', 'raw', 'flat', None}.  The table law uses the
    zero-block extent candidates (see table_decode); the raw law uses
    the FF escape start rule with the committed strong-fit bar; the
    flat law is the stage-7 container PART-1 reading with the start
    pinned by counts_end."""
    td = table_decode(payload, c1, counts_end)
    if td is not None and td[0] != "ambiguous":
        e, _pts, skips, region_end, wc = td
        # rebuild the written points in region order -- the LCP carrier
        # state (x, y, z) persists across slots (the committed
        # decode_region semantics); every written slot stores the FULL
        # triple, a skip slot stores nothing
        table_start = counts_end + 4 * e
        pos = region_end - 4 * wc
        out = []
        x = y = z = 0.0
        for i in range(c1):
            v = (payload[table_start + i // 4] >> (2 * (i % 4))) & 3
            shape = composite.SHAPES[v]
            if shape == 0:
                continue
            if shape == 3:
                x, y, z = struct.unpack_from("<fff", payload, pos)
            elif shape == 2:
                y, z = struct.unpack_from("<ff", payload, pos)
            else:
                z = struct.unpack_from("<f", payload, pos)[0]
            out.append((x, y, z))
            pos += 4 * shape
        # the committed layout() skips ALL consecutive zero groups from
        # counts_end -- when the table's own leading bytes are zero it
        # overshoots into the table (the stage-8 misalignment finding)
        skip = 0
        q = counts_end
        while payload[q : q + 4] == b"\x00\x00\x00\x00":
            skip += 1
            q += 4
        mis = skip - e
        return (
            "table",
            out,
            skips,
            region_end,
            wc,
            f"extent={e} committed_skip={skip} misalign={mis}",
        )
    if td is not None and td[0] == "ambiguous":
        return None, [], 0, 0, 0, "table: ambiguous zero-block extent"
    probe = raw_probe(payload, c1)
    if probe is not None:
        s, rate, asc = probe
        if rate >= 0.98 and asc >= 0.98:
            pts = list(
                struct.iter_unpack("<fff", payload[s : s + 12 * c1])
            )
            return ("raw", pts, 0, s + 12 * c1, 3 * c1, "")
        raw_weak = (s, rate, asc)
    else:
        raw_weak = None
    # flat reading (the stage-7 container PART-1 law, start pinned by
    # counts_end): c1 full triples straight after the 4-B tail field,
    # all-nice under the EXPORTER predicate (the raw scan's 1e-6 floor
    # rejects real near-zero coordinates on these stores -- stage-7
    # fact), x-ascending -- no zero block, no table; the FF escape may
    # or may not close the region, the sub-sections follow
    # byte-adjacent.  Absorption is judged by the content pairing in
    # audit_store (fail-closed there).
    s = counts_end + 4
    if s + 12 * c1 <= len(payload) and c1 >= 2:
        ok = True
        xs = []
        for k in range(c1):
            x, y, z = struct.unpack_from("<fff", payload, s + 12 * k)
            if not (composite._nice(x) and composite._nice(y) and composite._nice(z)):
                ok = False
                break
            xs.append(x)
        if ok:
            asc = sum(1 for a, b in zip(xs, xs[1:]) if b >= a - 1e-6) / (c1 - 1)
            pts = list(
                struct.iter_unpack("<fff", payload[s : s + 12 * c1])
            )
            # the order law: x-ascending (the raw family's order) OR the
            # parametric grid sweep -- validated by the pool absorbing
            # verbatim from the region (the stage-7 container reading's
            # criterion); junk spans absorb nothing and fail here
            pset = set(poolv)
            hits = len(pset & set(pts))
            if asc >= 0.98 or (pset and hits == len(pset)):
                return ("flat", pts, 0, s + 12 * c1, 3 * c1, f"asc={asc:.3f} hits={hits}/{len(pset)}")
    if raw_weak is not None:
        s, rate, asc = raw_weak
        return (
            None,
            [],
            0,
            0,
            0,
            f"raw-weak-fit@{s} nice={rate:.4f} asc={asc:.4f}",
        )
    return None, [], 0, 0, 0, "table: no walk-exact zero-block extent"


def audit_store(sha, rel, mm, stage6_verdict, stage7_verdict):
    d8_outer = int.from_bytes(mm[8:12], "big") if mm.size() >= 12 else 0
    blocks = store.valid_blocks(mm)
    body = groups = None
    lo = hi = 0
    for blk in [b for b, nm in blocks if nm == "CATStdCont"]:
        span = store.locate_store(mm, blk, blocks, d8_outer)
        if span is None:
            continue
        lo, hi = span.body_lo, span.body_hi
        groups, kinds = pool.scan_pool_groups(mm, lo, hi)
        if pool.has_composite_space(kinds):
            body = mm[lo:hi]
            break
    row = {k: "" for k in STORE_FIELDS}
    row["sha256"] = sha
    row["split"] = rel["split"]
    row["verdict_stage6"] = stage6_verdict
    row["verdict_stage7"] = stage7_verdict
    if body is None:
        row["verdict"] = "no-body"
        return row, []
    bd = bytes(body)
    row["body_bytes"] = len(bd)
    row["pool_groups"] = len(groups)
    row["pool_sizes"] = ";".join(str(len(g.vertices)) for g in groups[:20])

    # token nodes over the FULL body (the _scan_token_nodes convention)
    nodes = []
    pos = 0
    while True:
        pos = bd.find(composite.NODE_MAGIC, pos)
        if pos < 0:
            break
        end = bd.find(composite.NODE_MAGIC, pos + 4)
        if end < 0:
            end = len(bd)
        payload = bd[pos + 4 : end]
        tok = payload.find(composite.LIST_TOKEN)
        if 0 <= tok <= 64:
            p = tok + 5
            try:
                c1, p = composite.read_count(payload, p)
                c2, p = composite.read_count(payload, p)
            except (IndexError, struct.error):
                pos += 1
                continue
            if 0 < c1 <= composite.MAX_ELEMENT_COUNT:
                nodes.append((pos, payload, c1, c2, p))
        pos += 1
    row["token_nodes"] = len(nodes)

    # the exporter's window (find_list_node within [lo, first STRIP_RE))
    m = composite.STRIP_RE.search(bd, 0, len(bd))
    first_hdr = m.start() if m is not None else ""
    row["first_strip_hdr"] = first_hdr
    win_hi = first_hdr if m is not None else len(bd)
    best = None
    for npos, payload, c1, c2, _ce in nodes:
        if npos < win_hi and (best is None or len(payload) > len(best[1])):
            best = (npos, payload, c1, c2)
    row["payload_window_bytes"] = len(best[1]) if best else ""
    row["payload_full_bytes"] = max((len(pl) for _p, pl, _c, _c2, _ce in nodes), default="")

    node_rows = []
    decoded = []  # (pos, payload, c1, c2, law, pts, skips, region_end_abs, elements)
    poolv_all = [v for g in groups for v in g.vertices]
    for npos, payload, c1, c2, counts_end in nodes:
        law, pts, skips, reg_end_rel, wc, failure = decode_node(
            payload, c1, counts_end, poolv_all
        )
        nrow = {k: "" for k in NODE_FIELDS}
        nrow["sha256"] = sha[:16]
        nrow["node_pos"] = npos
        nrow["payload_bytes"] = len(payload)
        nrow["c1"] = c1
        nrow["c2"] = c2
        nrow["law"] = law
        nrow["pts"] = len(pts)
        nrow["skips"] = skips
        nrow["region_end_rel"] = reg_end_rel
        nrow["write_count"] = wc
        nrow["failure"] = failure
        if law is not None:
            elements = (
                [(0, pt) for pt in pts]
                if law == "raw"
                else None
            )
            decoded.append(
                {
                    "pos": npos,
                    "payload": payload,
                    "c1": c1,
                    "c2": c2,
                    "law": law,
                    "pts": pts,
                    "skips": skips,
                    "region_end_abs": npos + 4 + reg_end_rel,
                    "elements": elements,
                }
            )
        node_rows.append(nrow)

    row["decoded_reps"] = len(decoded)
    row["table_reps"] = sum(1 for r in decoded if r["law"] == "table")
    row["raw_reps"] = sum(1 for r in decoded if r["law"] == "raw")
    row["flat_reps"] = sum(1 for r in decoded if r["law"] == "flat")
    row["failed_nodes"] = len(nodes) - len(decoded)

    # per-rep pool absorption: CONTENT pairing over region-bearing reps
    # (pts > 0) -- each pool group is absorbed by the rep whose region
    # re-lists it verbatim (or within the stage-4b noise tolerance);
    # the diagonal (pool k <-> k-th region rep in body order) is the
    # stage-5 presentation when every rep decodes, and mis-aligns when
    # earlier reps fail (the stage-4b 'shifted' case), so the content
    # test is the law and the diagonal is reported separately.
    pair_reps = [r for r in decoded if r["pts"]]
    pool_sets = [{v for v in g.vertices} for g in groups]
    rep_sets = [set(r["pts"]) for r in pair_reps]
    # the vertex-subnode records (05 08 01 + 12B f32, the twins' law):
    # their points are a second absorption route for the pool
    sub_pts = set()
    q = 0
    while True:
        q = bd.find(b"\x05\x08\x01", q)
        if q < 0:
            break
        sub_pts.add(struct.unpack_from("<fff", bd, q + 3))
        q += 3
    pairs = 0
    noise_pairs = 0
    unpaired = []
    diag_ok = 0
    abs_map = []
    pool_region_total = 0
    pool_subonly_total = 0
    for gi, pset in enumerate(pool_sets):
        # union matching per rep: exact f32, then the stage-4b noise
        # tolerance (relative 1e-5), then the 05 08 01 sub-node records
        # (the twins' second absorption route) -- a pool vertex counts
        # ONCE (union, no double counting)
        exact_hits = []
        region_matched_all = set()
        for j, rep in enumerate(pair_reps):
            ptset = rep_sets[j]
            matched = pset & ptset
            exact = len(matched)
            noise = 0
            if len(pset) <= 10_000:
                # the noise fallback is O(pts) per miss -- cap it (the
                # stage-4b noise deltas are a small residue; big pools
                # pair exact-only)
                for pt in pset - matched:
                    if close_eq(rep["pts"], pt):
                        matched = matched | {pt}
                        noise += 1
            region_matched_all |= matched
            sub_hits = 0
            if sub_pts:
                for pt in pset - matched:
                    if pt in sub_pts:
                        matched = matched | {pt}
                        sub_hits += 1
            exact_hits.append((len(matched), exact, noise, sub_hits, j))
            if len(matched) == len(pset):
                break
        full = [h for h in exact_hits if h[0] == len(pset)]
        if full:
            pairs += 1
            h, ex, nz, sh, j = full[0]
            if j == gi:
                diag_ok += 1
            if nz:
                noise_pairs += 1
            abs_map.append(
                f"{gi}->{j}" + ("n" if nz else "") + ("s" if sh else "")
            )
            # export-relevant accounting: pool vertices matched by a
            # DECODED REGION (exact or noise -- their element slot is
            # decodable) vs matched only by the sub-node records (the
            # element slot is not in any decoded region)
            pool_region_total += len(region_matched_all)
            pool_subonly_total += len(pset) - len(region_matched_all)
        else:
            best = max(exact_hits, default=(0, 0, 0, 0, -1))
            unpaired.append(
                f"pool{gi}({len(pset)})max{best[0]}"
                + (f"@rep{best[4]}" if best[4] >= 0 else "")
            )
    row["diag_paired"] = diag_ok
    row["pool_in_region"] = pool_region_total
    row["pool_subnode_only"] = pool_subonly_total
    row["abs_map"] = ";".join(abs_map[:12])
    row["paired_pools"] = pairs
    row["noise_pools"] = noise_pairs
    row["unpaired_pools"] = len(pool_sets) - pairs

    # per-rep refs gate: gated records in the rep's territory
    # (region end -> the next node magic in the body)
    node_positions = sorted(npos for npos, _pl, _c1, _c2, _ce in nodes)
    refs_ok = 0
    refs_bad = 0
    ref_notes = []
    for gi, rep in enumerate(pair_reps):
        tlo = rep["region_end_abs"]
        nxt = [p for p in node_positions if p > tlo]
        thi = nxt[0] if nxt else len(bd)
        if thi <= tlo:
            continue
        try:
            records, _n = composite.parse_strip_records(
                bd, tlo, thi, rep["c1"], elements=None
            )
        except Exception as exc:  # noqa: BLE001 - named residue
            ref_notes.append(f"rep{gi}:parse-{type(exc).__name__}")
            continue
        gated = [
            r for _o, mk, _n, _c, refs, _w in records if mk in GATED for r in refs
        ]
        if gated:
            mx = max(gated)
            if mx < rep["c1"]:
                refs_ok += 1
            else:
                refs_bad += 1
                ref_notes.append(f"rep{gi}:maxref{mx}>=c1{rep['c1']}")
    row["refs_ok"] = refs_ok
    row["refs_bad"] = refs_bad

    if pairs == len(pool_sets) and pool_sets and refs_bad == 0:
        row["verdict"] = "reps-full"
    elif pairs > 0 or decoded:
        row["verdict"] = "reps-partial"
    else:
        row["verdict"] = "unexplained"
    row["residue"] = ";".join(unpaired[:6]) + (
        "|" + ";".join(ref_notes[:4]) if ref_notes else ""
    )
    return row, node_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sha16", default=None)
    ap.add_argument("--out", default=str(OUT_DIR / "mixedwrite-reps-files.csv"))
    ap.add_argument("--nodes-out", default=str(OUT_DIR / "mixedwrite-reps-nodes.csv"))
    args = ap.parse_args()
    probe = {r["sha256"]: r for r in csv.DictReader(PROBE_CSV.open())}
    mc = {r["sha256"]: r for r in csv.DictReader(MC_CSV.open())}
    targets = [
        s
        for s, r in probe.items()
        if r["verdict"] in ("start-unpinned", "weak-fit", "pool-unabsorbed")
    ]
    if args.sha16:
        targets = [s for s in targets if s.startswith(args.sha16)]
    manifest = {r["sha256"]: r for r in csv.DictReader(MANIFEST.open())}
    rows = []
    node_rows = []
    for sha in sorted(targets):
        path = ROOT / manifest[sha]["local_path"]
        with path.open("rb") as fh:
            mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                r, nr = audit_store(
                    sha,
                    manifest[sha],
                    mm,
                    probe[sha]["verdict"],
                    mc.get(sha, {}).get("verdict", ""),
                )
            finally:
                mm.close()
        rows.append(r)
        node_rows.extend(nr)
        if args.sha16:
            for k, v in r.items():
                print(f"  {k} = {v}")
            print("  ---")
    if not args.sha16:
        with open(args.out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=STORE_FIELDS)
            w.writeheader()
            w.writerows(rows)
        with open(args.nodes_out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=NODE_FIELDS)
            w.writeheader()
            w.writerows(node_rows)
        print(f"wrote {args.out} ({len(rows)} stores)")
        print(f"wrote {args.nodes_out} ({len(node_rows)} nodes)")
    print("verdicts:", Counter(r["verdict"] for r in rows).most_common())
    full = [r for r in rows if r["verdict"] == "reps-full"]
    print("reps-full:", len(full))
    print("reps-full by stage7 verdict:", Counter(r["verdict_stage7"] for r in full))
    print("pool vertices in decoded regions:", sum(int(r["pool_in_region"]) for r in rows if r["verdict"] == "reps-full"))
    print("pool vertices subnode-only:", sum(int(r["pool_subnode_only"]) for r in rows if r["verdict"] == "reps-full"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
