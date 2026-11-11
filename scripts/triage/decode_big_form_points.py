#!/usr/bin/env python3
"""Big-form point regions decoded via the 2-bit table (G6 stage 3b, #34).

Byte decode of the list-node point region driven by the per-element
2-bit table (U1, solved 2026-11-11) and the segment bookkeeping it
implies (U3): the region is ONE table + ONE P1g write count + the
writes, on both forms.  Analysis + decoder only — ``src/`` untouched
(the exporter integration of big form is a later stage).

Model (docs/evidence/2026-11-10-node-streams.md, stage-3b refinements
dated 2026-11-11, byte-measured on the corpus):

- Layout (P1t refined): payload = header + token ``ff ff 02 00 01`` +
  the declared counts (element_count, edge_ref_bound, P1g) + a zero
  block + **the 2-bit table: exactly ceil(element_count / 4) bytes**
  (the stage-2c "+1 byte" was the write-count byte miscounted into the
  table span) + **a P1g count** (1 B, ff escapes to u32le) of the
  region's f32 words + **the point region** (count x f32) + a trailing
  region (U2, open).
- Table semantics (U1, fact on the anchors): 2 bits per element,
  LSB-first within each byte, one slot per element in region order:
  value 0 = ``[x][y][z]`` full write (3 f32, x-group start), value 1 =
  skip (the element carries no coordinates in the region — the curve
  entries, U4), value 2 = ``[z]`` (1 f32), value 3 = ``[y][z]``
  (2 f32).  The initial LCP state is the origin (P1i subsumed: the
  first write's shape comes from the table like every other).  The
  walk is deterministic: no DP, no probe — it consumes exactly
  ``write_count`` f32 words.
- Segments (U3, resolved): there are no separate segment tables and no
  segment headers — the single table IS the bookkeeping.  Value-0
  slots delimit the x-groups/runs (P1r); the big-store corner groups
  sit out of x order at their element slots (70b59f2a: elements
  1812-1819, table pattern 0,2,3,2 = [x][y][z],[z],[y][z],[z] each)
  after ONE x-break; the region is otherwise lex-ascending.
- References (M2b refined): facet/edge references are 0-based ELEMENT
  indices in region order (identity — no sigma search).  Skip slots
  referenced by loops are curve entries whose coordinates live in the
  curve records (U4); their written neighbours bracket them (100/104
  skip slots on 70b59f2a have both neighbours sharing 2 coordinates).
  The loop plane law is coplanarity against the record's stored 12-B
  normal (the corner quads are slanted planes — the axis-constant
  reading was too strict).

Outputs docs/evidence/data/big-form-points-files.csv (one row per
composite store) and a summary on stdout.  Deterministic: sorted
manifest order; no wall-clock value enters the CSV.

Read-only over the corpus; run with the worktree venv:
  .venv/bin/python -I scripts/triage/decode_big_form_points.py
  [--include-sha16 HEX16,...]
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
    "node_form", "list_node_bytes", "elem_decl", "edge_bound_decl",
    "table_bytes", "write_count", "count_bytes", "region_bytes",
    "walk_end_ok", "nice_ok", "pts_written", "skip_slots",
    "pool_in_list", "pool_coverage", "pool_absorbed",
    "max_ref", "elem_eq_maxref1", "records_parsed", "width2_records",
    "norm_records", "loops", "loops_coplanar", "loops_skipref",
    "loops_nonplanar", "max_plane_residual", "audit_error",
]

# table value -> f32 writes (0 = skip: the element carries no coordinates)
SHAPES = {0: 3, 1: 0, 2: 1, 3: 2}
PLANE_TOL = 2e-3  # |(p - p0) . n| / |n| bound; f32 coordinate rounding ~1e-4


def layout(payload: bytes, elem_count: int):
    """Region layout after the zero block (P1t refined): table + P1g count.

    Returns (table_start, table_len, count_pos, region_start, write_count)
    or raises ValueError when the layout does not fit the payload.
    """
    tok = payload.find(composite.LIST_TOKEN)
    if tok < 0:
        raise ValueError("no list token")
    p = tok + 5
    _, p = composite.read_count(payload, p)
    _, p = composite.read_count(payload, p)
    while p + 4 <= len(payload) and payload[p : p + 4] == b"\x00\x00\x00\x00":
        p += 4
    table_len = (elem_count + 3) // 4
    count_pos = p + table_len
    if count_pos >= len(payload):
        raise ValueError("table runs past payload")
    write_count, region_start = composite.read_count(payload, count_pos)
    region_end = region_start + 4 * write_count
    if region_end > len(payload):
        raise ValueError("region overruns payload")
    return p, table_len, count_pos, region_start, write_count


def table_slots(payload: bytes, table_start: int, table_len: int, elem_count: int):
    """The 2-bit table: LSB-first slots, one per element."""
    slots = []
    for i in range(table_start, table_start + table_len):
        b = payload[i]
        slots += [(b >> 0) & 3, (b >> 2) & 3, (b >> 4) & 3, (b >> 6) & 3]
    return slots[:elem_count]


def decode_region(payload: bytes, elem_count: int):
    """Deterministic table-driven decode of the point region.

    Returns (elements, region_start, walk_end, nice_ok, info) where
    ``elements[i] = (value, point_or_None)`` in region order (point is
    None for skip slots) and ``walk_end`` is the byte the walk reached
    (the region's declared end when the law holds).
    """
    table_start, table_len, count_pos, region_start, write_count = layout(
        payload, elem_count
    )
    slots = table_slots(payload, table_start, table_len, elem_count)
    pos = region_start
    x = y = z = 0.0  # the initial LCP state is the origin (P1i subsumed)
    elements = []
    nice_ok = True
    for v in slots:
        shape = SHAPES[v]
        if shape == 0:
            elements.append((v, None))
            continue
        if pos + 4 * shape > len(payload):
            nice_ok = False  # the walk overruns the payload: stop cleanly
            elements.append((v, None))
            break
        if shape == 3:
            x, y, z = _f32(payload, pos), _f32(payload, pos + 4), _f32(payload, pos + 8)
            ok = all(_nice(c) for c in (x, y, z))
        elif shape == 2:
            y, z = _f32(payload, pos), _f32(payload, pos + 4)
            ok = all(_nice(c) for c in (y, z))
        else:
            z = _f32(payload, pos)
            ok = _nice(z)
        nice_ok &= ok
        pos += 4 * shape
        elements.append((v, (x, y, z)))
    info = {
        "table_start": table_start,
        "table_len": table_len,
        "count_pos": count_pos,
        "write_count": write_count,
        "count_bytes": region_start - count_pos,
        "region_start": region_start,
        "region_bytes": 4 * write_count,
    }
    return elements, region_start, pos, nice_ok, info


def _f32(data, pos):
    return struct.Struct("<f").unpack_from(data, pos)[0]


def _nice(v):
    """Finite coordinate check.

    The table-driven walk needs no pruning predicate (the table fixes
    the parse), so the stage-2c probe's 1e-6 floor is dropped here:
    real tessellation coordinates reach ~1e-15 around zero (the writer
    stores sin(pi)-scale noise verbatim; the pool carries exact -0.0),
    and junk detection falls to the walk-end / pool / plane checks.
    """
    return v == v and abs(v) < 1e9


def parse_strip_records(data, lo, hi, elem_count):
    """Every strip record with the width disambiguated (stage-3b rule).

    Candidate parses: width u8/u16be x count-byte k (0..16) summing to n,
    ending at or before the next header.  Rank: exact tiling, then
    no-repeated-refs-within-a-loop, then no out-of-range refs, then the
    narrower width (the tiling law first; the no-repeat rule resolves
    the u8-misread of u16be records whose next header is not adjacent).
    Returns a list of (offset, marker, normal, counts, refs, width).
    """
    hdrs = [m.start() for m in facets.STRIP_RE.finditer(data, lo, hi)]
    out = []
    for i, o in enumerate(hdrs):
        nxt = hdrs[i + 1] if i + 1 < len(hdrs) else hi
        mk = data[o + 1]
        hlen = 4 if data[o + 3] == 0xFF else 5
        if o + hlen + 4 > nxt:
            continue
        n = int.from_bytes(data[o + hlen : o + hlen + 4], "little")
        if not (0 <= n <= 1_000_000):
            continue
        has_normal = mk in facets.NORMAL_MARKERS_ALL
        base = o + hlen + 4 + (12 if has_normal else 0)
        normal = None
        if has_normal:
            normal = struct.unpack("<fff", data[o + hlen + 4 : o + hlen + 16])
        best = None
        for width in (1, 2):
            for k in range(0, 17):
                if base + k > nxt:
                    break
                counts = [data[base + j] for j in range(k)]
                if sum(counts) != n:
                    continue
                end = base + k + width * n
                if end > nxt:
                    continue
                refs = [
                    int.from_bytes(
                        data[base + k + width * j : base + k + width * (j + 1)],
                        "big",
                    )
                    for j in range(n)
                ]
                repeats = False
                off = 0
                for c in counts:
                    loop = refs[off : off + c]
                    if c > 0 and len(set(loop)) < c:
                        repeats = True
                    off += c
                oob = any(r >= elem_count for r in refs)
                rank = (
                    0 if end == nxt else 1,
                    1 if repeats else 0,
                    1 if oob else 0,
                    width,
                    k,
                )
                if best is None or rank < best[0]:
                    best = (rank, tuple(counts), tuple(refs), width)
        if best is None:
            continue
        _rank, counts, refs, width = best
        out.append((o, mk, normal, counts, refs, width))
    return out, len(hdrs)


def plane_battery(records, elements, elem_count):
    """Coplanarity of every normal-carrying loop against its stored normal.

    Loops referencing skip slots are counted separately (curve entries:
    coordinates live in the curve records, U4 — not testable here).
    Returns (norm_records, loops, coplanar, skipref, nonplanar, max_residual).
    """
    skips = {i for i, (v, pt) in enumerate(elements) if pt is None}
    norm_records = 0
    loops = coplanar = skipref = nonplanar = 0
    max_res = 0.0
    for _o, mk, normal, counts, refs, _w in records:
        if normal is None:
            continue
        norm_records += 1
        nn = (normal[0] ** 2 + normal[1] ** 2 + normal[2] ** 2) ** 0.5
        off = 0
        for c in counts:
            loop = refs[off : off + c]
            off += c
            if not loop:
                continue
            loops += 1
            if any(r in skips or r >= elem_count for r in loop):
                skipref += 1
                continue
            pts = [elements[r][1] for r in loop]
            ok = True
            if nn == 0:
                ok = False
            else:
                p0 = pts[0]
                for p in pts[1:]:
                    d = (
                        (p[0] - p0[0]) * normal[0]
                        + (p[1] - p0[1]) * normal[1]
                        + (p[2] - p0[2]) * normal[2]
                    ) / nn
                    res = abs(d)
                    if res > max_res:
                        max_res = res
                    if res > PLANE_TOL:
                        ok = False
                        break
            if ok:
                coplanar += 1
            else:
                nonplanar += 1
    return norm_records, loops, coplanar, skipref, nonplanar, max_res


def audit_part(mm, rel):
    """One part: table-driven point-region audit. Returns the CSV row."""
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
        try:
            elements, region_start, walk_end, nice_ok, info = decode_region(
                payload, c1
            )
        except ValueError as exc:
            row["audit_error"] = f"layout: {exc}"
            return row
        row["table_bytes"] = info["table_len"]
        row["write_count"] = info["write_count"]
        row["count_bytes"] = info["count_bytes"]
        row["region_bytes"] = info["region_bytes"]
        row["walk_end_ok"] = walk_end == info["region_start"] + info["region_bytes"]
        row["nice_ok"] = nice_ok
        written = [pt for _v, pt in elements if pt is not None]
        row["pts_written"] = len(written)
        row["skip_slots"] = sum(1 for _v, pt in elements if pt is None)
        ps = set(poolv)
        hits = len(ps & set(written))
        row["pool_in_list"] = hits
        row["pool_coverage"] = round(hits / len(poolv), 4) if poolv else ""
        row["pool_absorbed"] = hits == len(ps)
        records, n_hdrs = parse_strip_records(mm, lo, hi, c1)
        row["records_parsed"] = len(records)
        row["width2_records"] = sum(1 for r in records if r[5] == 2)
        all_refs = [r for _o, _mk, _n, _c, refs, _w in records for r in refs]
        row["max_ref"] = max(all_refs) if all_refs else ""
        row["elem_eq_maxref1"] = (
            (c1 == max(all_refs) + 1) if all_refs else ""
        )
        nr, loops, cop, skp, non, max_res = plane_battery(records, elements, c1)
        row["norm_records"] = nr
        row["loops"] = loops
        row["loops_coplanar"] = cop
        row["loops_skipref"] = skp
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
    out_path = out_dir / "big-form-points-files.csv"
    with out_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out_rows)
    print(f"wrote {out_path} ({len(out_rows)} rows)")
    summarize(out_rows)
    return 0


def _rate(rows, key):
    have = [r for r in rows if str(r.get(key)) not in ("", "None")]
    return have, len(have)


def summarize(rows):
    """Per-claim rates over the audited stores."""
    have = [r for r in rows if r.get("node_form") in ("small", "big")]
    aerr = [r for r in rows if r["audit_error"]]
    print(f"== table-driven point-region audit: {len(have)} composite stores "
          f"of {len(rows)} parts (audit errors: {len(aerr)})")
    if not have:
        return
    for form in ("big", "small"):
        fr = [r for r in have if r["node_form"] == form]
        if not fr:
            continue
        print(f"-- {form}-form: {len(fr)} stores")
        end_ok = [r for r in fr if str(r["walk_end_ok"]) == "True"]
        nice = [r for r in fr if str(r["nice_ok"]) == "True"]
        both = [r for r in end_ok if str(r["nice_ok"]) == "True"]
        print(f"   walk consumes exactly write_count words: {len(end_ok)}/{len(fr)}"
              f" (nice words throughout: {len(nice)}, both: {len(both)})")
        absorbed = [r for r in fr if str(r["pool_absorbed"]) == "True"]
        print(f"   pool fully re-listed in the decoded points: "
              f"{len(absorbed)}/{len(fr)}")
        n2 = [r for r in fr if str(r["elem_eq_maxref1"]) == "True"]
        n2_have, n2_n = _rate(fr, "elem_eq_maxref1")
        print(f"   elem_decl == max_ref + 1: {len(n2)}/{n2_n} stores carrying refs")
        lp = [r for r in fr if str(r["loops"]) not in ("", "0")]
        cp = [r for r in lp if str(r["loops_nonplanar"]) == "0"]
        skp = [r for r in lp if str(r["loops_skipref"]) not in ("", "0")]
        clean = [r for r in lp if str(r["loops_skipref"]) in ("", "0")]
        clean_ok = [r for r in clean if str(r["loops_coplanar"]) == str(r["loops"])]
        tot_loops = sum(int(r["loops"]) for r in lp)
        tot_cop = sum(int(r["loops_coplanar"]) for r in lp)
        tot_skp = sum(int(r["loops_skipref"]) for r in lp)
        tot_non = sum(int(r["loops_nonplanar"]) for r in lp)
        print(f"   normal-carrying loops: {tot_loops} across {len(lp)} stores —"
              f" coplanar {tot_cop}, skip-ref (curve entries, U4) {tot_skp},"
              f" nonplanar {tot_non}")
        print(f"   stores with zero nonplanar loops: {len(cp)}/{len(lp)};"
              f" skip-ref-free stores fully coplanar: "
              f"{len(clean_ok)}/{len(clean) if clean else 0}")
    big = [r for r in have if r["node_form"] == "big"]
    dec = [r for r in big if str(r["walk_end_ok"]) == "True"
           and str(r["nice_ok"]) == "True" and str(r["pool_absorbed"]) == "True"]
    print(f"== headline: big-form stores whose region decodes under the table"
          f" law with the pool fully contained: {len(dec)}/{len(big)}")


if __name__ == "__main__":
    sys.exit(main())
