#!/usr/bin/env python3
"""Curve-entry coordinates pinned from the 33 3X records (G6 stage 4a, #34).

U4 (the curve-entry point semantics, open since stage 3b): the point
region's skip slots (table value 1) are loop vertices whose coordinates
live in the curve records.  This decoder pins them and re-runs the
coplanarity battery with the pinned coordinates — the falsifiable test
stated in the stage-4a dispatch.

Model (byte-measured on the anchors 026d6726007381a9 and
e254a37e2ba6902c — the same part saved twice; verified against the
strip parity, the edge-table polylines and the record counts; dated
2026-11-11):

- Curve-record layout (C1 refined): every record = a 7-B header
  ``<u8 a><u8 b><u16le id><00><u16le len>`` + family ``33 3X`` + ``len``
  payload bytes; records tile header-to-family.  Families measured:
  33 37 = 4 BE f32 ``(cx, cy, cz, r)`` + a 2-B trailer (18 B; the
  written ring circles — stride 27 tiling); 33 33 = 6 BE f32
  ``(cx, cy, cz, p1, p2, r)`` + a 2-B trailer (26 B; the MID-RING
  circles, r negative on the anchors); 33 38 = 7 BE f32 + 2-B trailer
  (30 B, followed by a 40-B f32le block); 33 32 = 2-B payload followed
  by a 40-B f32le ``[P][Q][P]+|Q|`` block; 33 36 = 2-B payload.
  Point semantics beyond 33 37/33 33 stay open.
- Dup law (U4-D): every skip slot REFERENCED by a facet loop pins to
  the BIT-EXACT coordinates of its immediately preceding written
  element — the per-face tessellation copies of shared ring/pool
  vertices (12/12 skips on each anchor; the edge-table polylines tile
  the same rings through the dups, e.g. the z=2.81 floor ring polyline
  (115, 107, 97, 75, 61, 45, 24, 14, 5) on 026d6726 uses dups 115/61
  at its 0/90-degree positions).
- Mid-ring law (U4-M): every skip slot NOT referenced by a facet loop
  whose bracketing written points share (x, y) with z_lo < z_hi and
  which matches a 33 33 record (z_lo <= cz <= z_hi,
  ||(x,y)-(cx,cy)| - |r|| within tolerance) pins to
  ``(x, y, cz)`` — the record's mid-ring circle sampled at the written
  angular positions.  On 026d6726 the 14 mid slots (z = 2.8552,
  r = 2.36) = the two 33 33 arcs' interiors (7 + 7, the arcs splitting
  at 90/270 degrees); the profile edges (0, 4, 6) and (114, 119, 123)
  of the edge table confirm slots 6/114 at z = cz.
- Every other skip pins to the preceding written element as well
  (fallback, 1/26 on 026d6726 — the r2.47 ring copy confirmed by the
  edge polyline (114, 119, 123)).

Outputs docs/evidence/data/curve-entries-files.csv (one row per
composite store) and a summary on stdout.  Deterministic: sorted
manifest order; no wall-clock value enters the CSV.  Read-only over the
corpus; run with the worktree venv:

  .venv/bin/python -I scripts/triage/decode_curve_entries.py
  # anchor subset:
  .venv/bin/python -I scripts/triage/decode_curve_entries.py \
    --include-sha16 026d6726007381a9,e254a37e2ba6902c,70b59f2a0eb60c1c
"""

import argparse
import csv
import mmap
import math
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
from decode_big_form_points import (  # noqa: E402
    decode_region,
    parse_strip_records,
    normal_loops,
    PLANE_TOL,
)

FIELDS = [
    "sha256", "split", "release", "size_bytes", "pool_size",
    "node_form", "elem_decl", "skip_slots", "walk_end_ok",
    "records_parsed", "c37_records", "c33_records",
    "c37_ring_match", "c37_ring_total", "c33_mid_slots", "c33_mid_total",
    "skips_dup_prev", "skips_mid", "skips_unpinned_dup",
    "loops", "loops_coplanar", "loops_skipref_coplanar",
    "loops_skipref_nonplanar", "loops_beyond", "loops_nonplanar",
    "max_plane_residual", "audit_error",
]

BE = struct.Struct(">f")
FAMILIES = (0x32, 0x33, 0x36, 0x37, 0x38)
R_TOL = 5e-3  # |radius Written - radius record| tolerance (f32 rounding)


def parse_curve_records(data, lo, hi):
    """Every 33 3X record behind its 7-B header, sanity-checked.

    Returns a list of dicts: offset, family, b, id, len, payload.  A
    candidate is accepted when the family is known, the length is
    plausible (0 < len <= 256) and, for the BE-float families, the
    leading coordinates are finite and pool-scale — the compressed
    streams carry 33 3X byte pairs whose 'headers' decode as garbage
    and must not absorb the walk.
    """
    out = []
    p = lo
    while p < hi - 9:
        if data[p] == 0x33 and data[p + 1] in FAMILIES:
            ln = int.from_bytes(data[p - 2 : p], "little")
            fam = data[p + 1]
            if 0 < ln <= 256:
                pay = data[p + 2 : p + 2 + ln]
                ok = True
                if fam in (0x33, 0x37, 0x38):
                    nbe = min((ln - 2) // 4, 4)
                    vals = [BE.unpack_from(pay, 4 * i)[0] for i in range(nbe)]
                    ok = all(math.isfinite(v) and abs(v) < 1e7 for v in vals)
                if ok:
                    out.append({
                        "off": p,
                        "fam": fam,
                        "b": data[p - 6],
                        "id": int.from_bytes(data[p - 5 : p - 3], "little"),
                        "len": ln,
                        "payload": pay,
                    })
                    p += 2 + ln
                    continue
        p += 1
    return out


def circle_of(rec):
    """(cx, cy, cz, r) of a 33 37/33 33 record, or None."""
    if rec["fam"] not in (0x33, 0x37):
        return None
    nbe = (rec["len"] - 2) // 4
    if (rec["fam"] == 0x33 and nbe < 6) or (rec["fam"] == 0x37 and nbe < 4):
        return None
    v = [BE.unpack_from(rec["payload"], 4 * i)[0] for i in range(nbe)]
    r = v[5] if rec["fam"] == 0x33 else v[3]
    return v[0], v[1], v[2], r


def pin_skips(elements, records, loop_refs):
    """Pin every skip slot's coordinates.

    Returns (coords, kinds) where coords[i] is the pinned (x, y, z) of
    skip i and kinds[i] in {'dup_prev', 'mid', 'unpinned_dup'}.
    """
    n = len(elements)
    skips = [i for i, (v, pt) in enumerate(elements) if pt is None]
    circles = [c for c in (circle_of(r) for r in records) if c is not None]
    coords = {}
    kinds = {}
    for i in skips:
        j = i - 1
        while j >= 0 and elements[j][1] is None:
            j -= 1
        k = i + 1
        while k < n and elements[k][1] is None:
            k += 1
        prev = elements[j][1] if j >= 0 else None
        nxt = elements[k][1] if k < n else None
        if i in loop_refs or prev is None:
            # dup law: the per-face copy of the preceding written point
            coords[i] = prev
            kinds[i] = "dup_prev" if i in loop_refs else "unpinned_dup"
            continue
        # mid-ring candidate: bracket shares (x, y), z_lo < z_hi, and a
        # 33 33 circle matches (cz inside the bracket, radius equal)
        if prev is not None and nxt is not None:
            if (prev[0], prev[1]) == (nxt[0], nxt[1]) and prev[2] < nxt[2]:
                best = None
                for cx, cy, cz, r in circles:
                    if not (prev[2] <= cz <= nxt[2]):
                        continue
                    if r == 0:
                        continue
                    d = math.hypot(prev[0] - cx, prev[1] - cy)
                    if abs(d - abs(r)) > R_TOL:
                        continue
                    if best is None or abs(cz - (prev[2] + nxt[2]) / 2) < abs(
                        best[2] - (prev[2] + nxt[2]) / 2
                    ):
                        best = (cx, cy, cz, r)
                if best is not None:
                    coords[i] = (prev[0], prev[1], best[2])
                    kinds[i] = "mid"
                    continue
        coords[i] = prev
        kinds[i] = "unpinned_dup"
    return coords, kinds


def battery(records, elements, elem_count, skip_coords):
    """Coplanarity of every normal-carrying loop with pinned skip coords.

    'skipref_coplanar' / 'skipref_nonplanar' = loops referencing skip
    slots, re-tested with the pinned coordinates (the stage-3b battery
    classed them untestable).  'beyond' = refs in the unwalked window
    (second-family stores).  Returns the counters + max residual.
    """
    skips = {i for i, (v, pt) in enumerate(elements) if pt is None}
    loops = cop = skcop = sknon = bey = non = 0
    max_res = 0.0
    for _mk, normal, loop, _o, _j in normal_loops(records):
        loops += 1
        has_skip = any(r in skips for r in loop)
        if any(r >= elem_count for r in loop):
            bey += 1
            continue
        if any(r >= len(elements) and r not in skips for r in loop):
            bey += 1
            continue
        pts = []
        broken = False
        for r in loop:
            if r in skips:
                c = skip_coords.get(r)
                if c is None:
                    broken = True
                    break
                pts.append(c)
            elif r < len(elements):
                pts.append(elements[r][1])
            else:
                broken = True
                break
        if broken:
            bey += 1
            continue
        nn = (normal[0] ** 2 + normal[1] ** 2 + normal[2] ** 2) ** 0.5
        if nn == 0:
            non += 1
            continue
        p0 = pts[0]
        maxr = 0.0
        status = "coplanar"
        for q in pts[1:]:
            d = (
                (q[0] - p0[0]) * normal[0]
                + (q[1] - p0[1]) * normal[1]
                + (q[2] - p0[2]) * normal[2]
            ) / nn
            res = abs(d)
            if res > maxr:
                maxr = res
            if res > PLANE_TOL:
                status = "nonplanar"
                break
        if res > max_res:
            max_res = res
        if has_skip:
            if status == "coplanar":
                skcop += 1
            else:
                sknon += 1
        elif status == "coplanar":
            cop += 1
        else:
            non += 1
    return loops, cop, skcop, sknon, bey, non, max_res


def audit_part(mm, rel):
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
            continue
        payload, c1, _c2 = ln
        row["elem_decl"] = c1
        row["node_form"] = "big" if len(payload) > 4096 else "small"
        try:
            elements, _rs, _we, _nice, info = decode_region(payload, c1)
        except ValueError as exc:
            row["audit_error"] = f"layout: {exc}"
            return row
        row["walk_end_ok"] = _we == info["region_start"] + info["region_bytes"]
        row["skip_slots"] = sum(1 for _v, pt in elements if pt is None)
        records = parse_curve_records(mm, lo, hi)
        row["records_parsed"] = len(records)
        row["c37_records"] = sum(1 for r in records if r["fam"] == 0x37)
        row["c33_records"] = sum(1 for r in records if r["fam"] == 0x33)
        # 33 37 -> written-ring cross-check
        written = [pt for _v, pt in elements if pt is not None]
        match = total = 0
        c37 = [circle_of(r) for r in records if r["fam"] == 0x37]
        c37 = [c for c in c37 if c is not None]
        if c37:
            cx = sum(c[0] for c in c37) / len(c37)
            cy = sum(c[1] for c in c37) / len(c37)
            rings = {}
            for p in written:
                key = (round(p[2], 3), round(math.hypot(p[0] - cx, p[1] - cy), 3))
                rings[key] = rings.get(key, 0) + 1
            for _cx0, _cy0, cz0, r0 in c37:
                total += 1
                for (zr, rr) in rings:
                    if abs(zr - cz0) <= 2e-3 and abs(rr - abs(r0)) <= 5e-3:
                        match += 1
                        break
        row["c37_ring_match"] = match
        row["c37_ring_total"] = total
        strips, _nh = parse_strip_records(mm, lo, hi, c1)
        loop_refs = {r for _o, _mk, _n, _c, refs, _w in strips for r in refs}
        skip_coords, kinds = pin_skips(elements, records, loop_refs)
        row["skips_dup_prev"] = sum(1 for k in kinds.values() if k == "dup_prev")
        row["skips_mid"] = sum(1 for k in kinds.values() if k == "mid")
        row["skips_unpinned_dup"] = sum(
            1 for k in kinds.values() if k == "unpinned_dup"
        )
        # 33 33 arcs' interiors vs the mid slots (count cross-check)
        mid_slots = [i for i, k in kinds.items() if k == "mid"]
        row["c33_mid_slots"] = len(mid_slots)
        row["c33_mid_total"] = row["c33_records"]
        loops, cop, skcop, sknon, bey, non, max_res = battery(
            strips, elements, c1, skip_coords
        )
        row["loops"] = loops
        row["loops_coplanar"] = cop
        row["loops_skipref_coplanar"] = skcop
        row["loops_skipref_nonplanar"] = sknon
        row["loops_beyond"] = bey
        row["loops_nonplanar"] = non
        row["max_plane_residual"] = round(max_res, 6) if max_res else 0.0
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
    out_dir = Path(args.out_dir)
    out_rows = []
    for rel in rows_in:
        path = ROOT / rel["local_path"]
        with path.open("rb") as fh:
            mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                row = audit_part(mm, rel)
            except Exception as exc:  # noqa: BLE001 - recorded per part
                row = {k: "" for k in FIELDS}
                row["sha256"] = rel["sha256"]
                row["split"] = rel["split"]
                row["audit_error"] = f"{type(exc).__name__}: {exc}"
            finally:
                mm.close()
        out_rows.append(row)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "curve-entries-files.csv"
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
    aerr = [r for r in rows if r["audit_error"]]
    print(f"== curve-entry audit: {len(have)} composite stores of "
          f"{len(rows)} parts (audit errors: {len(aerr)})")
    for form in ("small", "big"):
        fr = [r for r in have if r["node_form"] == form]
        if not fr:
            continue
        we = [r for r in fr if str(r["walk_end_ok"]) == "True"]
        print(f"-- {form}-form: {len(fr)} stores (walk-exact {len(we)})")
        for label, sub in (("all", fr), ("walk-exact", we)):
            if not sub:
                continue
            sk = sum(int(r["skip_slots"] or 0) for r in sub)
            dup = sum(int(r["skips_dup_prev"] or 0) for r in sub)
            mid = sum(int(r["skips_mid"] or 0) for r in sub)
            unp = sum(int(r["skips_unpinned_dup"] or 0) for r in sub)
            print(f"   [{label}] skips {sk}: dup-prev {dup}, mid {mid}, "
                  f"fallback-dup {unp}")
        m = [r for r in fr if str(r.get("c37_ring_total")) not in ("", "0")
             and r["c37_ring_total"] is not None and str(r["c37_ring_total"]) != "0"]
        tm = sum(int(r["c37_ring_total"] or 0) for r in m)
        mm_ = sum(int(r["c37_ring_match"] or 0) for r in m)
        print(f"   33 37 records matching a written ring: {mm_}/{tm}")
        lp = [r for r in we if str(r["loops"]) not in ("", "0")]
        tot = sum(int(r["loops"] or 0) for r in lp)
        cop = sum(int(r["loops_coplanar"] or 0) for r in lp)
        skcop = sum(int(r["loops_skipref_coplanar"] or 0) for r in lp)
        sknon = sum(int(r["loops_skipref_nonplanar"] or 0) for r in lp)
        bey = sum(int(r["loops_beyond"] or 0) for r in lp)
        non = sum(int(r["loops_nonplanar"] or 0) for r in lp)
        print(f"   pinned battery over walk-exact stores with loops "
              f"({len(lp)}): {tot} loops = coplanar {cop} + "
              f"skipref-coplanar {skcop} + skipref-nonplanar {sknon} + "
              f"beyond {bey} + nonplanar {non}")
        if tot:
            ok = cop + skcop
            print(f"   planar share: {ok}/{tot} = {ok / tot:.3f} "
                  f"(skipref: {skcop}/{skcop + sknon} coplanar)")


if __name__ == "__main__":
    sys.exit(main())
