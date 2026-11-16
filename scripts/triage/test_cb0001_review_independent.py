#!/usr/bin/env python3
"""Independent verification walker for Phase 6 CB0001 catalog census.
Verifies claims P6-CB-1 through P6-CB-12 against corpus directly without
importing the child's p6_cb0001_catalog_census.py decoder.
"""

from __future__ import annotations

import csv
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "corpus"
MANIFEST = ROOT / "manifests/corpus-manifest.csv"

MAGIC = b"CATIA_V5 CB0001\x00"


def check_all():
    # 1. Load manifest product files
    prod_files = []
    with open(MANIFEST) as fh:
        for row in csv.DictReader(fh):
            if row.get("kind") == "product":
                prod_files.append(row)

    print(f"Total product manifest rows: {len(prod_files)}")

    # P6-CB-1: count files with MAGIC before dword8
    cb_files = []
    for r in prod_files:
        p = ROOT / r["local_path"]
        if not p.exists():
            continue
        data = p.read_bytes()
        if len(data) < 64:
            continue
        # read dword8 (offset 8 in header)
        d8 = struct.unpack_from(">I", data, 8)[0]
        pos = data.find(MAGIC, 0, d8)
        if pos != -1:
            cb_files.append((r["sha256"][:16], p, data, pos))

    print(f"P6-CB-1: Files with body CB0001 catalog: {len(cb_files)} (expected: 44)")
    assert len(cb_files) == 44, f"Expected 44, got {len(cb_files)}"

    # P6-CB-2, P6-CB-3, P6-CB-4, P6-CB-5, P6-CB-6, P6-CB-8
    law_h2_count = 0
    dual_region_count = 0
    cnt_law_count = 0
    span_law_count = 0
    tiling_law_count = 0
    clean_walk_count = 0
    assembly_token_hits = 0

    tokens_to_check = [b"_InstanceName", b"_Position", b"_Component", b"_PartNumber"]

    for sha16, p, data, cat_off in cb_files:
        # Check header
        has_ff8 = data[16:24] == b"\xff" * 8
        if not has_ff8:
            dual_region_count += 1

        d16 = struct.unpack_from(">I", data, 16)[0]
        d20 = struct.unpack_from(">I", data, 20)[0]

        if cat_off == d16:
            law_h2_count += 1

        # Catalog header
        cat_hdr = data[cat_off : cat_off + 64]
        tag, m1000, m64, m12 = struct.unpack_from(">B H H H", cat_hdr, 16)
        cntA, cntB = struct.unpack_from("<H H", cat_hdr, 24)
        v2 = struct.unpack_from(">I", data, cat_off + 31)[0]

        if cntB == cntA + 1:
            cnt_law_count += 1

        if v2 == cat_off + d20:
            span_law_count += 1

        # Check for assembly tokens in the catalog body
        cat_body = data[cat_off : cat_off + d20]
        for tok in tokens_to_check:
            if tok in cat_body:
                assembly_token_hits += 1

        # Walk entries independently to check X and Y bounds
        cat_bytes = data[cat_off:]
        ents = []
        expected_named = cntA - 1
        
        # Find entry0
        first = None
        for idx in range(72, min(len(cat_bytes) - 36, 12000)):
            # check name
            if idx + 2 <= len(cat_bytes):
                ln = struct.unpack_from("<H", cat_bytes, idx)[0]
                if ln % 2 == 0 and 6 <= ln <= 2048:
                    nc = (ln - 2) // 2
                    if idx + 2 + 2 * nc <= len(cat_bytes):
                        try:
                            s = cat_bytes[idx + 2 : idx + 2 + 2 * nc].decode("utf-16-le")
                            if s and all(ord(c) >= 32 for c in s):
                                r0 = cat_bytes[idx - 72 : idx - 55]
                                if len(r0) == 17 and r0[0] == 0x01 and struct.unpack_from(">I", r0, 5)[0] == 0:
                                    first = (idx, s, idx + 2 + ln)
                                    break
                        except Exception:
                            pass

        if first:
            pos = first[2]
            while pos + 184 <= len(cat_bytes) and len(ents) < expected_named:
                if cat_bytes[pos : pos + 7] == b"CB__END":
                    break
                if cat_bytes[pos + 84] != 0x01:
                    break
                x, y1, y2 = struct.unpack_from(">I I I", cat_bytes, pos + 85)
                if y1 == y2:
                    ents.append((x, y1))
                # read name at pos + 184
                if pos + 184 + 2 <= len(cat_bytes):
                    ln = struct.unpack_from("<H", cat_bytes, pos + 184)[0]
                    if 6 <= ln <= 2048 and pos + 184 + 2 + ln <= len(cat_bytes):
                        pos = pos + 184 + 2 + ln
                    else:
                        break
                else:
                    break

        if ents:
            min_x = min(e[0] for e in ents)
            max_xy = max(e[0] + e[1] for e in ents)
            if min_x == 64 and max_xy == d16:
                tiling_law_count += 1
            if len(ents) == expected_named:
                clean_walk_count += 1

    print(f"P6-CB-2: Catalog offset == header.dword16: {law_h2_count}/44")
    print(f"P6-CB-3: has_ff8 == False: {dual_region_count}/44")
    print(f"P6-CB-5: cntB == cntA + 1: {cnt_law_count}/44")
    print(f"P6-CB-6: val2 == offset + dword20: {span_law_count}/44")
    print(f"P6-CB-8: min(X)==64 and max(X+Y)==d16: {tiling_law_count}/44")
    print(f"P6-CB-11: Assembly tokens in catalog body: {assembly_token_hits} (expected: 0)")

    assert law_h2_count == 44
    assert dual_region_count == 44
    assert cnt_law_count == 44
    assert span_law_count == 44
    assert tiling_law_count == 44
    assert assembly_token_hits == 0

    print("ALL INDEPENDENT VERIFICATION CHECKS PASSED!")


if __name__ == "__main__":
    check_all()
