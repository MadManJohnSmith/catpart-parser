#!/usr/bin/env python3
"""Verify the container-tree assembly claim (ticket #24) on the corpus.

Evidence base: docs/evidence/2026-11-07-container-table-and-trailer.md
(record format, laws T1-T3) and docs/evidence/
2026-11-07-container-payload-layout.md (C7: CATFeatCont is never a
name1). The owner decision for ticket #24 makes the L1 "feature tree"
the container tree assembled from the container-name table records:
each record contributes node {name, parent_name, table_id, index, guid,
weight}, the tree is the hierarchy formed by those records (parent
relation via parent_name, ordering via table_id/index).

Claim under test (the simple parent_name law): every file's records
form a connected hierarchy rooted at AppliCont/CATContainer-style roots
via parent_name - i.e. each record's parent_name resolves to the name1
of another record of the same file (except roots), so the records hang
together under a small set of roots.

This script measures exactly that, corpus-wide, over the same validated
record parse as scripts/triage/decode_container_table.py: per record it
checks whether name2 matches the name1 of a same-file record (the only
parent relation expressible via parent_name), how many candidate
parents a match has, and whether the parent record precedes the child
in file order; per file it counts roots (records with an unresolved
parent_name), duplicate name1 values, AppliCont rows and the 0x00040001
table's rows.

Read-only over the corpus; run with:
python3 -I scripts/triage/verify_container_tree.py
Writes docs/evidence/data/container-tree-scan.csv (one row per file).
"""
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"
OUT_FILES = OUT_DIR / "container-tree-scan.csv"

SCAN_WINDOW = 2 * 1024 * 1024
ANCHOR = b"\x02\x00\x81\x20"          # f9 bytes; little-endian value 0x20810002
F5_CONST = 0x006C0001
TABLE_IDS = (0x00030001, 0x00040001, 0x00050001)
RECORD_TAIL = b"\x03\x00\xf7\x00\x03\x00\x00\x00"


def ceil8(n):
    return ((n + 7) // 8) * 8


def u32(buf, off):
    return int.from_bytes(buf[off:off + 4], "little")


def parse_record(buf, s):
    """The validated B1 record model (decode_container_table.py)."""
    if s < 0 or s + 40 > len(buf):
        return None
    f1, f2, f3, idx = u32(buf, s), u32(buf, s + 4), u32(buf, s + 8), u32(buf, s + 12)
    f5, f6, f8, f9, f10 = (u32(buf, s + o) for o in (16, 20, 28, 32, 36))
    if not (f5 == F5_CONST and f6 == 2 and f8 == 0 and f9 == 0x20810002):
        return None
    if f3 not in TABLE_IDS:
        return None
    p = s + 40
    n1 = buf.find(b"\x00", p)
    if n1 < 0 or n1 == p:
        return None
    n2 = buf.find(b"\x00", n1 + 1)
    if n2 < 0 or n2 == n1 + 1:
        return None
    if n2 - p > 256:
        return None
    try:
        name1 = buf[p:n1].decode("ascii")
        name2 = buf[n1 + 1:n2].decode("ascii")
    except UnicodeDecodeError:
        return None
    if not (name1.isprintable() and name2.isprintable()):
        return None
    total = (n2 + 1) - p
    area = ceil8(total)
    end_names = p + area
    if end_names + 8 + 16 > len(buf):
        return None
    if any(buf[n2 + 1:end_names]):
        return None
    if buf[end_names:end_names + 8] != RECORD_TAIL:
        return None
    if f10 != area // 8 + 1:
        return None
    return {
        "f1": f1, "f2": f2, "f3": f3, "idx": idx, "f10": f10,
        "name1": name1, "name2": name2,
        "guid": bytes(buf[end_names + 8:end_names + 24]).hex(),
    }


def scan_file(buf):
    recs = []
    pos = buf.find(ANCHOR)
    while pos >= 32:
        s = pos - 32
        rec = parse_record(buf, s)
        if rec:
            recs.append(rec)
            # record size = 64 + names area; area = (f10 - 1) * 8 (law T1)
            pos = buf.find(ANCHOR, s + 64 + (rec["f10"] - 1) * 8)
        else:
            pos = buf.find(ANCHOR, pos + 1)
    return recs


def main():
    rows = [r for r in csv.DictReader(MANIFEST.open()) if r["magic_ok"] == "yes"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fields = ["sha256", "repo", "detected_version", "kind", "table_found",
              "n_records", "dup_names", "n_parent_resolved",
              "n_parent_ambiguous", "n_parent_after_child",
              "n_parent_unresolved", "table_ids", "appli_count",
              "appli_f3_hex", "appli_idx", "appli_weight", "appli_name2",
              "n_40001_rows", "n_40001_non_appli", "names"]
    w = csv.DictWriter(OUT_FILES.open("w", newline=""), fieldnames=fields)
    w.writeheader()

    t = Counter()                       # corpus totals
    parent_vocab = Counter()            # name2 values corpus-wide
    unresolved_vocab = Counter()        # name2 values that never resolve
    name1_vocab = Counter()
    appli_f3 = Counter()
    appli_idx = Counter()
    appli_weight = Counter()
    appli_name2 = Counter()
    appli_position = Counter()          # record ordinal of AppliCont rows
    non_appli_40001 = Counter()         # name1 of 0x00040001 rows != AppliCont
    roots_per_file = Counter()
    resolved_share_per_file = Counter()

    for r in rows:
        p = ROOT / r["local_path"]
        size = int(r["size_bytes"])
        with p.open("rb") as fh:
            buf = fh.read(min(size, SCAN_WINDOW))
        recs = scan_file(buf)
        names1 = [rec["name1"] for rec in recs]
        names1_set = set(names1)
        name1_by_name = {}
        for i, rec in enumerate(recs):
            name1_by_name.setdefault(rec["name1"], []).append(i)

        n_resolved = n_ambiguous = n_after = 0
        for i, rec in enumerate(recs):
            parent_vocab[rec["name2"]] += 1
            name1_vocab[rec["name1"]] += 1
            if rec["name2"] in names1_set:
                n_resolved += 1
                candidates = name1_by_name[rec["name2"]]
                if len(candidates) > 1:
                    n_ambiguous += 1
                if all(j > i for j in candidates):
                    n_after += 1
            else:
                unresolved_vocab[rec["name2"]] += 1
        n_unresolved = len(recs) - n_resolved

        appli = [(i, rec) for i, rec in enumerate(recs) if rec["name1"] == "AppliCont"]
        rows_40001 = [rec for rec in recs if rec["f3"] == 0x00040001]
        appli_40001 = [(i, rec) for i, rec in appli if rec["f3"] == 0x00040001]
        for i, rec in appli:
            appli_f3["%#010x" % rec["f3"]] += 1
            appli_idx[rec["idx"]] += 1
            appli_weight[rec["f2"]] += 1
            appli_name2[rec["name2"]] += 1
            appli_position[i] += 1
        for rec in rows_40001:
            if rec["name1"] != "AppliCont":
                non_appli_40001[rec["name1"]] += 1

        dup = len(names1_set) < len(names1)
        roots_per_file[n_unresolved] += 1
        if recs:
            resolved_share_per_file[round(n_resolved / len(recs), 1)] += 1

        t["files"] += 1
        t["table_found"] += bool(recs)
        t["records"] += len(recs)
        t["resolved"] += n_resolved
        t["ambiguous"] += n_ambiguous
        t["after_child"] += n_after
        t["unresolved"] += n_unresolved
        t["dup_name_files"] += dup
        t["files_all_resolved"] += bool(recs) and n_unresolved == 0
        t["files_none_resolved"] += bool(recs) and n_resolved == 0
        t["appli_files_0"] += bool(recs) and not appli
        t["appli_files_1"] += len(appli) == 1
        t["appli_files_multi"] += len(appli) > 1
        t["rows_40001"] += len(rows_40001)
        t["rows_40001_non_appli"] += len(rows_40001) - len(appli_40001)
        t["appli_40001"] += len(appli_40001)

        w.writerow({
            "sha256": r["sha256"], "repo": r["repo"],
            "detected_version": r["detected_version"], "kind": r["kind"],
            "table_found": bool(recs), "n_records": len(recs),
            "dup_names": dup, "n_parent_resolved": n_resolved,
            "n_parent_ambiguous": n_ambiguous, "n_parent_after_child": n_after,
            "n_parent_unresolved": n_unresolved,
            "table_ids": ";".join(
                "%#010x" % tid for tid in sorted({rec["f3"] for rec in recs})),
            "appli_count": len(appli),
            "appli_f3_hex": ";".join("%#010x" % rec["f3"] for _, rec in appli),
            "appli_idx": ";".join(str(rec["idx"]) for _, rec in appli),
            "appli_weight": ";".join(str(rec["f2"]) for _, rec in appli),
            "appli_name2": ";".join(rec["name2"] for _, rec in appli),
            "n_40001_rows": len(rows_40001),
            "n_40001_non_appli": len(rows_40001) - len(appli_40001),
            "names": ";".join(names1),
        })

    n_tab = t["table_found"]
    n_rec = t["records"]
    print(f"files scanned: {t['files']}, with table: {n_tab}, records: {n_rec}")
    print(f"\n-- parent_name law (strict: name2 matches a same-file name1) --")
    print(f"resolved:   {t['resolved']}/{n_rec} = {t['resolved'] / n_rec:.3f}")
    print(f"unresolved: {t['unresolved']}/{n_rec} = {t['unresolved'] / n_rec:.3f}")
    print(f"ambiguous resolutions (>1 candidate parent): {t['ambiguous']}")
    print(f"resolutions where every candidate parent comes AFTER the child: {t['after_child']}")
    print(f"files where ALL records resolve: {t['files_all_resolved']}/{n_tab}")
    print(f"files where NO record resolves:  {t['files_none_resolved']}/{n_tab}")
    print(f"files with duplicate name1:      {t['dup_name_files']}/{n_tab}")
    print(f"roots (unresolved-parent records) per file distribution (top): "
          f"{roots_per_file.most_common(8)}")
    print(f"resolved-share per file (bucket 0.1) (top): "
          f"{sorted(resolved_share_per_file.items())[:6]} ... "
          f"{sorted(resolved_share_per_file.items())[-4:]}")
    print(f"\nparent_name vocabulary corpus-wide: {len(parent_vocab)} values")
    for name, c in parent_vocab.most_common(15):
        print(f"  {name}: {c}")
    print(f"unresolved-parent vocabulary: {len(unresolved_vocab)} values (top 15):")
    for name, c in unresolved_vocab.most_common(15):
        print(f"  {name}: {c}")
    print(f"\ndistinct name1 vocabulary: {len(name1_vocab)} values")
    print(f"CATContainer as name1: {name1_vocab['CATContainer']}")
    print(f"CATFeatCont as name1:  {name1_vocab['CATFeatCont']}")
    print(f"\n-- AppliCont rows --")
    print(f"files with 0 / 1 / >1 AppliCont rows: "
          f"{t['appli_files_0']} / {t['appli_files_1']} / {t['appli_files_multi']}")
    print(f"AppliCont f3: {dict(appli_f3)}")
    print(f"AppliCont idx: {dict(appli_idx)}")
    print(f"AppliCont weight: {dict(appli_weight)}")
    print(f"AppliCont name2: {dict(appli_name2)}")
    print(f"AppliCont record ordinal (top 8): {appli_position.most_common(8)}")
    print(f"\n-- 0x00040001 table --")
    print(f"rows in table 0x00040001: {t['rows_40001']}; named AppliCont: "
          f"{t['appli_40001']}; not AppliCont: {t['rows_40001_non_appli']}")
    print(f"non-AppliCont names in 0x00040001: {non_appli_40001.most_common(10)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
