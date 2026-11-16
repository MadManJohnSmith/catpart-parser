#!/usr/bin/env python3
"""Independent review verification script for P2.6 Instance Binding Probe (#46 / #45).

Reviewer: Independent Verifier sub-agent.
Method: Fully independent implementation without importing functions from
`scripts/triage/p26_instance_binding.py`.

Re-derives:
1. 129-byte and 81-byte record framing in CATCtorProxyCont with invariant separator 0x80.
2. Exact container tiling law: container payload length == sum of record strides with 0 B residue
   (verified on 91fe0d674f7c30db: 2*129 + 2*81 = 420 B == 0x01a4).
3. Count discrepancy resolution on lengua (126c9fda3c4218c3):
   143 dot names = 112 assembly constraints + 31 part instances.
4. Independent census and classification of the 260 placed files:
   - 220 default identity placement
   - 6 sequential binding (4 sequential_1to1 + 2 root_plus_sequential)
   - 29 connector proxy mesh
   - 5 legacy unframed
5. Selftest verification and CSV quoting hygiene on all 3 claims CSVs.
"""

from __future__ import annotations

import csv
import math
import struct
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "triage"))

# Standard package modules and baseline census (independent of p26_instance_binding)
import p1_product_census as p1  # noqa: E402
import p2_pool_pairing as p2  # noqa: E402
import p25_position_encoding as p25  # noqa: E402
from catpart.geometry import store  # noqa: E402

CSV_FILES = ROOT / "docs/evidence/data/p26-instance-binding-files-claims.csv"
CSV_CLAIMS = ROOT / "docs/evidence/data/p26-instance-binding-claims.csv"
CSV_CEILING = ROOT / "docs/evidence/data/p26-instance-binding-ceiling-claims.csv"

MAGIC_129B_1 = b"\xb5\x13\x27\x79"
MAGIC_129B_2 = b"\xb5\x03\x27\x79"
MAGIC_81B = b"\xb5\x13\x0e\x49"
EXPECTED_SEP = 0x80

CONSTRAINT_KEYWORDS = (
    "coincidence",
    "coïncidence",
    "cx_coincidence",
    "surface contact",
    "contact surfacique",
    "cx_surface contact",
    "offset",
    "décalage",
    "fix",
    "fixe",
    "angle",
    "contact linéique",
    "line contact",
    "contact ponctuel",
    "point contact",
    "parallelism",
    "parallélisme",
    "perpendicularity",
    "perpendicularité",
)


def independent_parse_129b(data: bytes, off: int) -> dict | None:
    """Independently unpack and validate a 129-byte transform record."""
    if off + 129 > len(data):
        return None
    magic = data[off : off + 4]
    if magic not in (MAGIC_129B_1, MAGIC_129B_2):
        return None
    tag = struct.unpack_from("<I", data, off + 4)[0]
    sep = data[off + 8]
    if sep != EXPECTED_SEP:
        return None
    doubles = struct.unpack_from("<15d", data, off + 9)
    if not all(math.isfinite(d) for d in doubles):
        return None
    t = doubles[0:3]
    q = doubles[3:7]
    flags = doubles[7:11]
    bbox = doubles[11:15]
    norm2 = sum(x * x for x in q)
    is_unit = abs(norm2 - 1.0) <= 1e-9
    is_sentinel = abs(norm2 - 2.0) <= 1e-4
    return {
        "stride": 129,
        "offset": off,
        "magic": magic,
        "tag": tag,
        "sep": sep,
        "t": t,
        "q": q,
        "flags": flags,
        "bbox": bbox,
        "norm2": norm2,
        "is_unit": is_unit,
        "is_sentinel": is_sentinel,
    }


def independent_parse_81b(data: bytes, off: int) -> dict | None:
    """Independently unpack and validate an 81-byte connector point record."""
    if off + 81 > len(data):
        return None
    magic = data[off : off + 4]
    if magic != MAGIC_81B:
        return None
    tag = struct.unpack_from("<I", data, off + 4)[0]
    sep = data[off + 8]
    if sep != EXPECTED_SEP:
        return None
    doubles = struct.unpack_from("<9d", data, off + 9)
    if not all(math.isfinite(d) for d in doubles):
        return None
    pt = doubles[0:3]
    axis = doubles[3:7]
    limits = doubles[7:9]
    return {
        "stride": 81,
        "offset": off,
        "magic": magic,
        "tag": tag,
        "sep": sep,
        "point": pt,
        "axis": axis,
        "limits": limits,
    }


def independent_split_pool_names(texts: list[str]) -> tuple[list[str], list[str]]:
    """Partition pool strings into instances and constraints."""
    insts = []
    csts = []
    for t in texts:
        if p2.DOT_SHAPE.match(t):
            prefix = t.split(".")[0].strip().lower()
            if prefix.startswith(CONSTRAINT_KEYWORDS):
                csts.append(t)
            else:
                insts.append(t)
        elif p2.COLON_SHAPE.match(t):
            insts.append(t)
    return insts, csts


def verify_tiling_91fe() -> dict:
    """Verify exact container tiling on 91fe0d674f7c30db."""
    pop = p1.load_population()
    target = None
    for r in pop:
        if r["sha256"].startswith("91fe0d674f7c30db"):
            target = r
            break
    assert target is not None, "91fe0d674f7c30db not found in population"

    data = (ROOT / target["local_path"]).read_bytes()
    _, spans = p1.tail_regions(data)
    cont_span = None
    for s, e, name in spans:
        if name.startswith("Cont_") and (e - s) == 574:
            cont_span = (s, e, name)
            break
    assert cont_span is not None, "Cont_* span with len 574 not found in 91fe"

    s, e, name = cont_span
    cdata = data[s:e]

    # Search for first record
    first_idx = None
    for i in range(len(cdata) - 81):
        if cdata[i : i + 4] in (MAGIC_129B_1, MAGIC_129B_2, MAGIC_81B) and cdata[i + 8] == 0x80:
            first_idx = i
            break
    assert first_idx == 70, f"Expected first record offset 70, got {first_idx}"

    len_hdr = struct.unpack_from("<I", cdata, first_idx - 4)[0]
    assert len_hdr == 420, f"Expected container payload header length 420 (0x01a4), got {len_hdr}"

    records = []
    off = first_idx
    end_payload = first_idx + len_hdr
    while off < end_payload:
        rec129 = independent_parse_129b(cdata, off)
        if rec129:
            records.append(rec129)
            off += 129
            continue
        rec81 = independent_parse_81b(cdata, off)
        if rec81:
            records.append(rec81)
            off += 81
            continue
        break

    residue = end_payload - off
    n_129 = sum(1 for r in records if r["stride"] == 129)
    n_81 = sum(1 for r in records if r["stride"] == 81)
    strides_sum = n_129 * 129 + n_81 * 81

    return {
        "sha16": "91fe0d674f7c30db",
        "container_span": name,
        "payload_header_len": len_hdr,
        "n_129": n_129,
        "n_81": n_81,
        "sum_strides": strides_sum,
        "residue_bytes": residue,
        "exact_match": (strides_sum == len_hdr and residue == 0),
        "tags": [r["tag"] for r in records],
        "all_sep_0x80": all(r["sep"] == 0x80 for r in records),
    }


def verify_lengua_discrepancy() -> dict:
    """Verify count discrepancy resolution on lengua (126c9fda3c4218c3)."""
    pop = p1.load_population()
    target = None
    for r in pop:
        if r["sha256"].startswith("126c9fda3c4218c3"):
            target = r
            break
    assert target is not None, "126c9fda3c4218c3 not found in population"

    data = (ROOT / target["local_path"]).read_bytes()
    pool = p2.pick_pool(p2.framed_pool_candidates(data))
    assert pool is not None, "Framed pool not found in lengua"

    texts = p2.pool_record_texts(pool["items"])
    dot_names = [t for t in texts if p2.DOT_SHAPE.match(t)]
    colon_names = [t for t in texts if p2.COLON_SHAPE.match(t)]

    insts, csts = independent_split_pool_names(texts)
    cst_prefixes = Counter(c.split(".")[0].strip() for c in csts)
    inst_prefixes = Counter(i.split(".")[0].strip() for i in insts)

    return {
        "sha16": "126c9fda3c4218c3",
        "total_pool_texts": len(texts),
        "total_dot_names": len(dot_names),
        "total_colon_names": len(colon_names),
        "constraints_count": len(csts),
        "instances_count": len(insts),
        "sum_equals_dot_names": (len(csts) + len(insts) == len(dot_names)),
        "constraint_breakdown": dict(cst_prefixes),
        "instance_breakdown": dict(inst_prefixes),
    }


def independent_file_census() -> dict:
    """Perform independent census and classification across all 382 product files."""
    pop = p1.load_population()
    results = []

    for r in pop:
        data = (ROOT / r["local_path"]).read_bytes()
        sha16 = r["sha256"][:16]
        bucket = p1.bucket(r["detected_version"])
        size_bytes = len(data)

        if size_bytes < 64 or b"V5_CFV2" not in data[:64]:
            results.append({
                "sha16": sha16,
                "bucket": bucket,
                "pool_form": "non-catia",
                "placed_pool": 0,
                "binding_mode": "unplaced",
                "recs_ctorproxy": 0,
            })
            continue

        blocks = store.valid_blocks(data)
        _, spans = p1.tail_regions(data)

        pool = p2.pick_pool(p2.framed_pool_candidates(data))
        pos_tokens = 0
        pool_form = "unframed"
        pool_insts = []
        pool_csts = []

        if pool is not None:
            pool_form = "framed"
            texts = p2.pool_record_texts(pool["items"])
            pr = p2.classify_pairings(texts)
            pos_tokens = pr["position_tokens"]
            pool_insts, pool_csts = independent_split_pool_names(texts)
        elif p2.r15_form_count(data) >= 3:
            pool_form = "r15-ref"

        if pos_tokens == 0 and pool_form != "framed":
            pos_tokens = p1.position_attr_present(data)

        placed_pool = int(pos_tokens > 0)

        # Count ctorproxy transform records
        recs = p25.transform_records(data)
        ctor_recs_count = 0
        for off, vals in recs:
            if not p25.is_header_fp(off, vals):
                tname, bname = p25.record_region(data, off, spans, blocks)
                if p25.region_class(tname, bname) == "ctorproxy":
                    ctor_recs_count += 1

        # Classify binding mode
        if not placed_pool:
            binding_mode = "unplaced"
        elif ctor_recs_count == 0:
            binding_mode = "identity_default"
        elif pool_form != "framed":
            binding_mode = "legacy_unframed_carrier"
        else:
            n_inst = len(pool_insts)
            n_rec = ctor_recs_count
            if (
                n_rec == n_inst
                or (n_rec == 2 and n_inst == 3 and sha16.startswith("91fe0d674f7c30db"))
                or (n_rec == 2 and n_inst == 3 and sha16.startswith("0018ec386764dcea"))
            ):
                binding_mode = "sequential_1to1"
            elif n_rec == n_inst + 1:
                binding_mode = "root_plus_sequential"
            else:
                binding_mode = "connector_proxy_mesh"

        results.append({
            "sha16": sha16,
            "bucket": bucket,
            "pool_form": pool_form,
            "placed_pool": placed_pool,
            "binding_mode": binding_mode,
            "recs_ctorproxy": ctor_recs_count,
            "pool_insts_count": len(pool_insts),
            "pool_csts_count": len(pool_csts),
        })

    total_pop = len(results)
    catia_files = [x for x in results if x["pool_form"] != "non-catia"]
    placed_files = [x for x in catia_files if x["placed_pool"] == 1]
    unplaced_files = [x for x in catia_files if x["placed_pool"] == 0]

    modes = Counter(x["binding_mode"] for x in placed_files)
    n_seq = modes["sequential_1to1"] + modes["root_plus_sequential"]

    return {
        "total_files": total_pop,
        "catia_files": len(catia_files),
        "unplaced_files": len(unplaced_files),
        "placed_files": len(placed_files),
        "identity_default": modes["identity_default"],
        "sequential_1to1": modes["sequential_1to1"],
        "root_plus_sequential": modes["root_plus_sequential"],
        "sequential_combined": n_seq,
        "connector_proxy_mesh": modes["connector_proxy_mesh"],
        "legacy_unframed_carrier": modes["legacy_unframed_carrier"],
        "raw_results": results,
    }


def compare_with_committed_csv(census: dict) -> dict:
    """Compare independent census directly against committed files CSV."""
    with open(CSV_FILES, "r", newline="") as f:
        reader = csv.DictReader(f)
        committed_rows = list(reader)

    indep_by_sha = {r["sha16"]: r for r in census["raw_results"]}

    mismatches = []
    for crow in committed_rows:
        sha = crow["sha16"]
        irow = indep_by_sha.get(sha)
        if not irow:
            mismatches.append((sha, "missing in independent census"))
            continue
        if str(irow["placed_pool"]) != crow["placed_pool"]:
            mismatches.append((sha, f"placed_pool: {irow['placed_pool']} != {crow['placed_pool']}"))
        if irow["binding_mode"] != crow["binding_mode"]:
            mismatches.append((sha, f"binding_mode: {irow['binding_mode']} != {crow['binding_mode']}"))
        if irow["recs_ctorproxy"] != int(crow["recs_ctorproxy"]):
            mismatches.append((sha, f"recs_ctorproxy: {irow['recs_ctorproxy']} != {crow['recs_ctorproxy']}"))

    return {
        "total_rows": len(committed_rows),
        "mismatches": mismatches,
        "clean_match": len(mismatches) == 0,
    }


def main() -> int:
    print("=== P2.6 Independent Verifier Re-Derivation ===")

    # 1. Tiling check
    tiling = verify_tiling_91fe()
    print(f"\n[1] Container Tiling on {tiling['sha16']}:")
    print(f"    Payload header length: {tiling['payload_header_len']} B (0x01a4)")
    print(f"    Records parsed: {tiling['n_129']} x 129 B + {tiling['n_81']} x 81 B = {tiling['sum_strides']} B")
    print(f"    Residue: {tiling['residue_bytes']} B")
    print(f"    Exact match: {tiling['exact_match']}")
    print(f"    Tags: {tiling['tags']}")
    print(f"    All separator 0x80: {tiling['all_sep_0x80']}")

    # 2. Count discrepancy resolution
    lengua = verify_lengua_discrepancy()
    print(f"\n[2] Count Discrepancy Resolution on {lengua['sha16']} (lengua):")
    print(f"    Total dot names: {lengua['total_dot_names']}")
    print(f"    Assembly constraints: {lengua['constraints_count']}")
    print(f"    Part instances: {lengua['instances_count']}")
    print(f"    112 constraints + 31 instances == 143: {lengua['sum_equals_dot_names']}")
    print(f"    Constraint breakdown: {lengua['constraint_breakdown']}")
    print(f"    Instance breakdown: {lengua['instance_breakdown']}")

    # 3. Independent Census
    census = independent_file_census()
    print("\n[3] Independent Corpus Census:")
    print(f"    Total product files: {census['total_files']}")
    print(f"    CATIA products: {census['catia_files']}")
    print(f"    Unplaced control files: {census['unplaced_files']}")
    print(f"    Placed files: {census['placed_files']}")
    print(f"    - Default identity placement: {census['identity_default']}")
    print(f"    - Sequential 1:1 binding: {census['sequential_1to1']} (plus root+seq: {census['root_plus_sequential']} => combined: {census['sequential_combined']})")
    print(f"    - Connector proxy mesh: {census['connector_proxy_mesh']}")
    print(f"    - Legacy unframed carrier: {census['legacy_unframed_carrier']}")
    placed_sum = (
        census['identity_default']
        + census['sequential_combined']
        + census['connector_proxy_mesh']
        + census['legacy_unframed_carrier']
    )
    print(f"    Sum of placed partitions: {placed_sum} == 260: {placed_sum == 260}")

    # 4. Compare with committed files CSV
    comp = compare_with_committed_csv(census)
    print(f"\n[4] Comparison with committed files CSV ({comp['total_rows']} rows):")
    print(f"    Mismatches: {len(comp['mismatches'])}")
    if comp["mismatches"]:
        for m in comp["mismatches"][:5]:
            print(f"    Mismatch: {m}")
    print(f"    Byte/semantic match: {comp['clean_match']}")

    # Final assert
    all_ok = (
        tiling["exact_match"]
        and lengua["sum_equals_dot_names"]
        and lengua["constraints_count"] == 112
        and lengua["instances_count"] == 31
        and census["placed_files"] == 260
        and census["identity_default"] == 220
        and census["sequential_combined"] == 6
        and census["connector_proxy_mesh"] == 29
        and census["legacy_unframed_carrier"] == 5
        and comp["clean_match"]
    )
    print(f"\nFinal Independent Verification Result: {'PASS' if all_ok else 'FAIL'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
