#!/usr/bin/env python3
"""Classify the walk-mismatch big-form residue (stage 4a-residue, #34).

Stage-3b (commit 249135b) left ~83 big-form stores whose deterministic
2-bit-table walk does not end exactly at the declared region end
(``walk_end_ok=False``).  This script computes, per store, the structural
features that separate sub-variants — WITHOUT guessing the law:

- delta_words  = walk_end - region_end (in f32 words; the table's
  sum-of-shapes minus the declared write count — a pure table/count
  inconsistency measure when the walk runs to completion)
- zeros_in_region / zero-run anatomy at and after the declared region
  end (the multi-part hypothesis: the payload carries more than one
  [zero block + table + count + region] segment)
- a second-layout probe: at each zero run at/after the region end, does
  P1t repeat (table of ceil(elem_decl/4) bytes, then a count whose
  region stays in bounds)?

Read-only over the corpus (symlink).  Analysis only: src/ untouched.
Run:  python3 -I scripts/triage/classify_residue_family.py
Out:  docs/evidence/data/residue-family-census.csv
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

sys.path.insert(0, str(ROOT / "scripts" / "triage"))
sys.path.insert(0, str(ROOT / "src"))

from catpart.geometry import facets, pool, store  # noqa: E402
from catpart.geometry import composite  # noqa: E402
from decode_big_form_points import decode_region  # noqa: E402

FIELDS = [
    "sha256", "split", "size_bytes", "list_node_bytes", "elem_decl",
    "table_len", "write_count", "count_bytes", "region_start",
    "region_end", "walk_end", "delta_words", "nice_ok", "pts_written",
    "skip_slots", "zeros_in_region", "zb1_off_from_end", "zb1_run_len",
    "second_layout_ok", "second_count", "second_region_ok", "audit_error",
]


def locate_payload(mm):
    """The composite list-node payload of a part, or None."""
    d8_outer = int.from_bytes(mm[8:12], "big") if mm.size() >= 12 else 0
    blocks = store.valid_blocks(mm)
    for blk in [b for b, nm in blocks if nm == "CATStdCont"]:
        span = store.locate_store(mm, blk, blocks, d8_outer)
        if span is None:
            continue
        lo, hi = span.body_lo, span.body_hi
        groups, kinds = pool.scan_pool_groups(mm, lo, hi)
        if not pool.has_composite_space(kinds):
            continue
        hdrs = [m.start() for m in facets.STRIP_RE.finditer(mm, lo, hi)]
        node_hi = hdrs[0] if hdrs else hi
        ln = composite.find_list_node(mm, lo, node_hi)
        if ln is None:
            continue
        return ln
    return None


def zero_runs(data, start):
    """4-byte-aligned zero-group runs [(start, n_groups)] from `start`."""
    out = []
    p = start & ~3
    n = len(data)
    while p + 4 <= n:
        if data[p : p + 4] == b"\x00\x00\x00\x00":
            q = p
            while q + 4 <= n and data[q : q + 4] == b"\x00\x00\x00\x00":
                q += 4
            out.append((p, (q - p) // 4))
            p = q
        p += 4
    return out


def audit_row(mm, rel):
    row = {k: "" for k in FIELDS}
    row["sha256"] = rel["sha256"]
    row["split"] = rel["split"]
    row["size_bytes"] = mm.size()
    ln = locate_payload(mm)
    if ln is None:
        return None
    payload, c1, _c2 = ln
    row["list_node_bytes"] = len(payload)
    row["elem_decl"] = c1
    try:
        elements, region_start, walk_end, nice_ok, info = decode_region(
            payload, c1
        )
    except ValueError as exc:
        row["audit_error"] = f"layout: {exc}"
        return row
    region_end = info["region_start"] + info["region_bytes"]
    row["table_len"] = info["table_len"]
    row["write_count"] = info["write_count"]
    row["count_bytes"] = info["count_bytes"]
    row["region_start"] = region_start
    row["region_end"] = region_end
    row["walk_end"] = walk_end
    row["delta_words"] = (walk_end - region_end) // 4
    row["nice_ok"] = nice_ok
    written = [pt for _v, pt in elements if pt is not None]
    row["pts_written"] = len(written)
    row["skip_slots"] = sum(1 for _v, pt in elements if pt is None)
    # zero-group anatomy inside the walked span and after the region end
    runs = zero_runs(payload, region_start)
    in_walk = [r for r in runs if r[0] >= region_start and r[0] < walk_end]
    row["zeros_in_region"] = sum(c for _p, c in in_walk)
    after = [r for r in runs if r[0] >= min(walk_end, region_end)]
    if after:
        zb1p, zb1n = after[0]
        row["zb1_off_from_end"] = zb1p - region_end
        row["zb1_run_len"] = zb1n
        # second-layout probe: P1t repeated at this zero block?
        p2 = zb1p + 4 * zb1n
        t2 = (c1 + 3) // 4
        cp2 = p2 + t2
        if cp2 < len(payload):
            _val, rs2 = composite.read_count(payload, cp2)
            re2 = rs2 + 4 * _val
            row["second_layout_ok"] = bool(
                0 < _val <= 4_000_000 and re2 <= len(payload)
            )
            row["second_count"] = _val
            row["second_region_ok"] = re2 <= len(payload)
    return row


RAW_FIELDS = [
    "sha256", "split", "form", "size_bytes", "payload_bytes", "elem_decl",
    "raw_start", "raw_nice_rate", "raw_x_asc_rate", "raw_trail_bytes",
    "pool_size", "pool_in_raw", "pool_absorbed_raw", "audit_error",
]

RAW_MAX_START = 64  # 4-aligned candidates scanned for the first triple


def _nice_f32(v):
    return v == v and (v == 0.0 or 1e-6 < abs(v) < 1e7)


def raw_scan(payload, c1, poolv):
    """Raw-array law probe: c1 f32 triples at stride 12 from a 4-aligned
    start near the header. Returns the best (start, nice, xasc, trail)
    candidate or None when 12*c1 does not fit from any candidate."""
    best = None
    ps = set(poolv)
    for start in range(32, RAW_MAX_START + 1, 4):
        if start + 12 * c1 > len(payload):
            continue
        nicec = 0
        xs = []
        hits = set()
        for k in range(c1):
            o = start + 12 * k
            x, y, z = struct.unpack_from("<fff", payload, o)
            if _nice_f32(x) and _nice_f32(y) and _nice_f32(z):
                nicec += 1
            if (x, y, z) in ps:
                hits.add((x, y, z))
            xs.append(x)
        rate = nicec / c1
        asc = sum(
            1 for a, b in zip(xs, xs[1:]) if b >= a - 1e-6
        ) / (c1 - 1)
        cand = (start, rate, asc, len(payload) - (start + 12 * c1), len(hits))
        if best is None or (rate, asc) > (best[1], best[2]):
            best = cand
    return best


def run_raw(out_path):
    """--raw: over the walk-mismatch stores, probe the raw-array law."""
    rows = []
    for r in csv.DictReader(MANIFEST.open()):
        if r["split"] not in ("dev", "held-out") or r["kind"] != "part":
            continue
        path = ROOT / r["local_path"]
        with path.open("rb") as fh:
            mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                ln = locate_payload(mm)
                if ln is None:
                    continue
                payload, c1, _c2 = ln
                try:
                    _e, _rs, walk_end, _n, info = decode_region(payload, c1)
                    if walk_end == info["region_start"] + info["region_bytes"]:
                        continue  # walk-OK: not the residue
                except ValueError:
                    pass  # layout-raised stores are residue too
                # pool for absorption
                d8_outer = int.from_bytes(mm[8:12], "big") if mm.size() >= 12 else 0
                blocks = store.valid_blocks(mm)
                poolv = []
                for blk in [b for b, nm in blocks if nm == "CATStdCont"]:
                    span = store.locate_store(mm, blk, blocks, d8_outer)
                    if span is None:
                        continue
                    groups, kinds = pool.scan_pool_groups(
                        mm, span.body_lo, span.body_hi
                    )
                    if pool.has_composite_space(kinds):
                        poolv = [
                            v for g in groups for v in g.vertices
                        ]
                    break
                row = {k: "" for k in RAW_FIELDS}
                row["sha256"] = r["sha256"]
                row["split"] = r["split"]
                row["form"] = "big" if len(payload) > 4096 else "small"
                row["size_bytes"] = mm.size()
                row["payload_bytes"] = len(payload)
                row["elem_decl"] = c1
                best = raw_scan(payload, c1, poolv)
                if best is not None:
                    row["raw_start"] = best[0]
                    row["raw_nice_rate"] = round(best[1], 4)
                    row["raw_x_asc_rate"] = round(best[2], 4)
                    row["raw_trail_bytes"] = best[3]
                    row["pool_size"] = len(set(poolv))
                    row["pool_in_raw"] = best[4]
                    row["pool_absorbed_raw"] = best[4] == len(set(poolv))
                rows.append(row)
            except Exception as exc:  # noqa: BLE001 - recorded per part
                rows.append(
                    {
                        k: ""
                        for k in RAW_FIELDS
                    }
                    | {
                        "sha256": r["sha256"],
                        "split": r["split"],
                        "audit_error": f"{type(exc).__name__}: {exc}",
                    }
                )
            finally:
                mm.close()
    out_path = Path(out_path)
    with out_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=RAW_FIELDS)
        w.writeheader()
        w.writerows(rows)
    fitted = [r for r in rows if r.get("raw_nice_rate") not in ("", None)]
    strong = [r for r in fitted if float(r["raw_nice_rate"]) >= 0.98
              and float(r["raw_x_asc_rate"]) >= 0.98]
    print(f"wrote {out_path} ({len(rows)} walk-mismatch stores)")
    print(
        "raw-fit: strong (nice>=.98 & xasc>=.98):",
        len(strong),
        "| weak-fit:",
        len(fitted) - len(strong),
        "| no-fit:",
        len(rows) - len(fitted),
    )
    print(
        "strong by form:",
        dict(Counter(r["form"] for r in strong)),
        "| pool absorbed among strong:",
        dict(Counter(str(r["pool_absorbed_raw"]) for r in strong)),
    )
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--raw", action="store_true",
        help="raw-array law scan over the walk-mismatch stores",
    )
    ap.add_argument(
        "--raw-out", default=str(OUT_DIR / "residue-raw-scan.csv")
    )
    args = ap.parse_args()
    if args.raw:
        return run_raw(args.raw_out)
    out_rows = []


if __name__ == "__main__":
    sys.exit(main())
