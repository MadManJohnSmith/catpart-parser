#!/usr/bin/env python3
"""Byte-level probe of one residue anchor (stage 4a-residue, #34).

Dumps the payload anatomy the census measured, for one sha16:
layout fields, zero runs, table bytes, slot run-lengths, and the bytes
around the declared region end — the raw material for the layout law.

Run:  python3 -I scripts/triage/probe_residue_anchor.py <sha16>
Read-only over the corpus (symlink). Analysis only: src/ untouched.
"""

import csv
import mmap
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"

sys.path.insert(0, str(ROOT / "scripts" / "triage"))
sys.path.insert(0, str(ROOT / "src"))

from catpart.geometry import composite  # noqa: E402
from classify_residue_family import locate_payload, zero_runs  # noqa: E402
from decode_big_form_points import decode_region  # noqa: E402


def rle(slots):
    return [(k, sum(1 for _ in g)) for k, g in __import__("itertools").groupby(slots)]


def main(sha16):
    rel = next(
        r
        for r in csv.DictReader(MANIFEST.open())
        if r["sha256"].startswith(sha16)
    )
    path = ROOT / rel["local_path"]
    with path.open("rb") as fh:
        mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        ln = locate_payload(mm)
    payload, c1, c2 = ln
    print(f"== {sha16}  payload={len(payload)}B  elem_decl={c1}  c2={c2}")
    tok = payload.find(composite.LIST_TOKEN)
    p = tok + 5
    v1, p = composite.read_count(payload, p)
    v2, p = composite.read_count(payload, p)
    print(f"header: token@{tok} count1={v1} count2={v2} zero_block@{p}")
    zb = 0
    while p + 4 <= len(payload) and payload[p : p + 4] == b"\x00\x00\x00\x00":
        p += 4
        zb += 4
    print(f"zero block: {zb}B -> table@{p}")
    table_len = (c1 + 3) // 4
    print(
        f"table[{table_len}B]: {payload[p : p + min(table_len, 24)].hex(' ')}"
        + (" ..." if table_len > 24 else "")
    )
    count_pos = p + table_len
    wc, region_start = composite.read_count(payload, count_pos)
    print(
        f"count@{count_pos}: bytes={payload[count_pos : count_pos + 8].hex(' ')}"
        f" -> wc={wc} region@{region_start}"
    )
    region_end = region_start + 4 * wc
    elements, rs, walk_end, nice, info = decode_region(payload, c1)
    slots = [v for v, pt in elements]
    pts = [pt for v, pt in elements if pt is not None]
    print(f"walk: end={walk_end} (delta={(walk_end - region_end) // 4} words)"
          f" nice={nice} pts={len(pts)} skips={slots.count(1)}")
    print("slot RLE (first 14):", rle(slots)[:14])
    runs = zero_runs(payload, p)
    print(
        "zero runs >=1 group in payload (offset,len), first 10:",
        [(o, l) for o, l in runs[:10]],
    )
    # bytes around the declared region end and around walk_end
    for tag, at in (("region_end", region_end), ("walk_end", walk_end)):
        lo = max(0, at - 16)
        print(
            f"bytes @{tag}({at}) [{lo}..{at + 24}):",
            payload[lo : at + 24].hex(" "),
        )
    # what read_count would say at each zero-run end (segment candidates)
    print("-- segment candidates (zero run -> P1t re-read):")
    for o, l in runs[:6]:
        if o + 4 * l >= len(payload):
            continue
        p2 = o + 4 * l
        for t2name, t2 in (
            ("ceil(c1/4)", (c1 + 3) // 4),
            ("ceil(c1/8)", (c1 + 7) // 8),
        ):
            cp2 = p2 + t2
            if cp2 >= len(payload):
                continue
            v, rs2 = composite.read_count(payload, cp2)
            print(
                f"  zb@{o}(+{l}) -> table@{p2} ({t2name}={t2}) count@{cp2}"
                f": {payload[cp2 : cp2 + 8].hex(' ')} -> wc2={v} region2@{rs2}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
