#!/usr/bin/env python3
"""Decode and corpus-validate the container-name table record format.

Evidence base: docs/evidence/2026-11-07-container-triage.md (Phase 1) and
ticket #17 (Spec B, Phase 2). Phase 1 located the plaintext container-name
table (~0x650-0xd00 in samples) and left the record format as an open
question. This script parses every table with one byte-level model and
reports, per file, how much of the model holds.

Record model (all multi-byte fields little-endian, unless stated):

  container-name record, starting at S:
    S+0   f1   u32   stream position value (join key, see below)
    S+4   f2   u32   per-record weight (11/12/13/21... observed)
    S+8   f3   u32   table id: 0x00030001 containers, 0x00040001
                      AppliCont row, 0x00050001 observed on some files
    S+12  idx  u32   1-based index within the table id
    S+16  f5   u32   constant 0x006c0001
    S+20  f6   u32   constant 2
    S+24  f7   u32   small value (0/1/2/9/10/11 observed)
    S+28  f8   u32   constant 0
    S+32  f9   u32   constant 0x20810002  (record anchor)
    S+36  f10  u32   names-area 8-byte slots + 1
    S+40  names: name1 0x00 name2 0x00 (ASCII), zero-padded so the
          names area is a multiple of 8 bytes
    then  8 bytes  03 00 f7 00 03 00 00 00   (constant)
    then  16 bytes GUID (per-record object id)
  record size = 64 + 8*ceil((len(name1)+len(name2)+2)/8); the next
  record starts immediately after. Satellite blobs (tags 04 00 c0 20 /
  04 00 fc 3f, e.g. the V5USERID row) may sit between records.

  directory record (precedes the name records), 40 bytes:
    +0   d0   u32   low u16 varies, high u16 0x00bf
    +4   d1   u32   constant 0x2e
    +8   d2   u32   0
    +12  d3   u32   usually 0xe7000200 (varies on some files)
    +16  d4   u32   0x01000000 | k  (k = 1..N)
    +20  d5   u32   1 + sum of f2 over the name records that precede,
               in table order, the record whose f1 == d5's record d6
    +24  d6   u32   join key: equals the f1 of one name record
    +28  d7   u32   equals d6
    +32  d8   u32   (low u16, high u16) small values
    +36  d9   u32   0
  Variable 4-byte arrays (values == the f1 sequence, second u16 0x1a00)
  sit after some directory records; the script counts them as gaps.

Validated laws (rates reported per file and corpus-wide):
  L1 constants: f5, f6, f8, f9 hold on every record.
  L2 f10 == ceil(names/8) + 1 on every record.
  L3 contiguity: next record start == current record end.
  L4 count(directory records) == count(name records) (bijection family;
     the directory is sometimes a strict subset of the records).
  L5 join: every directory d6 equals some record f1 (multiset subset;
     a bijection when L4 holds).
  L6 cumulative: d5 == 1 + sum of f2 over preceding joined records.
  L7 d7 == d6.

Records are located by the f9 anchor and fully validated; anything
between records that is not a record is counted as a gap and classified
by its start bytes (satellite vs unknown).

Read-only; run with: python3 -I scripts/triage/decode_container_table.py
Writes docs/evidence/data/container-table.csv (one row per file) and
docs/evidence/data/container-table-records-sample.csv (one row per record
for the deterministic version-stratified sample).
"""
import csv, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"
OUT_FILES = OUT_DIR / "container-table.csv"
OUT_RECORDS = OUT_DIR / "container-table-records-sample.csv"

SCAN_WINDOW = 2 * 1024 * 1024
ANCHOR = b"\x02\x00\x81\x20"          # f9 bytes; little-endian value 0x20810002
F5_CONST = 0x006C0001
TABLE_IDS = (0x00030001, 0x00040001, 0x00050001)
RECORD_TAIL = b"\x03\x00\xf7\x00\x03\x00\x00\x00"
DIR_D1 = 0x2E
SATELLITE_TAGS = (b"\x04\x00\xc0\x20",   # V5USERID satellite blob
                  b"\x04\x00\xfc\x3f")   # second satellite tag observed


def ceil8(n):
    return ((n + 7) // 8) * 8


def u32(buf, off):
    return int.from_bytes(buf[off:off + 4], "little")


def parse_record(buf, s):
    """Parse and validate one container-name record at S.

    Returns a dict of fields, or None when any layout element of the
    model is violated (constants, names, padding, tail bytes).
    """
    if s < 0 or s + 40 > len(buf):
        return None
    f1, f2, f3, idx = u32(buf, s), u32(buf, s + 4), u32(buf, s + 8), u32(buf, s + 12)
    f5, f6, f7, f8, f9, f10 = (u32(buf, s + o) for o in (16, 20, 24, 28, 32, 36))
    if not (f5 == F5_CONST and f6 == 2 and f8 == 0 and f9 == 0x20810002):
        return None
    if f3 not in TABLE_IDS:
        return None
    # names: two printable ASCII NUL-terminated strings starting at S+40
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
        return None                       # padding must be zeros
    if buf[end_names:end_names + 8] != RECORD_TAIL:
        return None
    if f10 != area // 8 + 1:
        return None                       # law L2
    guid = bytes(buf[end_names + 8:end_names + 24])
    return {
        "start": s, "f1": f1, "f2": f2, "f3": f3, "idx": idx, "f7": f7,
        "f10": f10, "name1": name1, "name2": name2, "total": total,
        "area": area, "guid": guid, "end": end_names + 24,
    }


def parse_directory(buf, first_record_start):
    """Collect the directory group in the window before the first record.

    Directory records are 40 bytes with d4 = 0x0100000k (k = 1..N),
    d1 = 0x2e, d0 high u16 = 0x00bf, and zero d2/d9. d3 is usually
    0xe7000200 but varies on some files, so it is recorded, not matched.
    Candidates are accepted only while their k runs 1, 2, 3, ... in
    file order, which rejects payload false positives.
    """
    out = []
    lo = max(0, first_record_start - 4096)
    off = buf.find(b"\x00\x00\x01", lo)      # bytes 2-4 of d4 = k 00 00 01
    expected_k = 1
    while 0 <= off < first_record_start:
        s = off - 17                           # d4 dword starts at s+16
        d4 = u32(buf, s + 16)
        if (d4 >> 8 == 0x010000 and d4 & 0xFF == expected_k
                and u32(buf, s + 4) == DIR_D1 and u32(buf, s + 8) == 0
                and u32(buf, s + 36) == 0
                and u32(buf, s) >> 16 == 0x00BF
                and 1 <= u32(buf, s + 20) < 1 << 20
                and 1 <= u32(buf, s + 24) < 1 << 20):
            out.append({
                "start": s, "k": d4 & 0xFF, "d1": u32(buf, s + 4),
                "d3": u32(buf, s + 12), "d5": u32(buf, s + 20),
                "d6": u32(buf, s + 24), "d7": u32(buf, s + 28),
                "d8": u32(buf, s + 32),
            })
            expected_k += 1
        off = buf.find(b"\x00\x00\x01", off + 1)
    return out


def scan_file(buf):
    """Return the table summary for one file image (first SCAN_WINDOW)."""
    recs = []
    rejected = 0
    pos = buf.find(ANCHOR)
    while pos >= 32:
        rec = parse_record(buf, pos - 32)
        if rec:
            recs.append(rec)
            pos = buf.find(ANCHOR, rec["end"])
        else:
            rejected += 1
            pos = buf.find(ANCHOR, pos + 1)
    dirs = parse_directory(buf, recs[0]["start"]) if recs else []
    dirs.sort(key=lambda d: d["k"])
    # L3 contiguity + satellite gaps
    contiguous = 0
    gaps = []
    for a, b in zip(recs, recs[1:]):
        if b["start"] == a["end"]:
            contiguous += 1
        else:
            gap = b["start"] - a["end"]
            kind = ("satellite" if buf[a["end"]:a["end"] + 4] in SATELLITE_TAGS
                    else "unknown")
            gaps.append((gap, kind))
    # L4 counts
    count_match = len(dirs) == len(recs) and len(recs) > 0
    # L5 join: bijection when counts match; otherwise the directory
    # multiset must still be a subset of the record f1 multiset
    f1_ms = Counter(r["f1"] for r in recs)
    d6_ms = Counter(d["d6"] for d in dirs)
    join = bool(recs and dirs) and d6_ms == f1_ms
    join_subset = bool(recs and dirs) and not (d6_ms - f1_ms)
    # L6 cumulative: order name records by position; prefix sums of f2;
    # d5[dir bound to record j] == 1 + sum(f2 of records before j)
    cum_ok = None
    if recs and dirs and len(dirs) == len(recs):
        prefix = [1]
        acc = 1
        for r in recs:
            acc += r["f2"]
            prefix.append(acc)
        d5_by_d6 = {d["d6"]: d["d5"] for d in dirs}
        cum_ok = all(d5_by_d6.get(r["f1"]) == prefix[j] for j, r in enumerate(recs))
    # L7 d7 == d6
    d7_ok = all(d["d7"] == d["d6"] for d in dirs) if dirs else None
    span = (recs[-1]["start"] - recs[0]["start"]) if len(recs) >= 2 else 0
    return {
        "records": recs, "dirs": dirs, "contiguous": contiguous,
        "gaps": gaps, "count_match": count_match, "join": join,
        "join_subset": join_subset,
        "cum_ok": cum_ok, "d7_ok": d7_ok, "span": span,
        "anchors_rejected": rejected,
    }


def sample_rows(rows):
    """Deterministic stratified sample: first/middle/last size per version."""
    byver = {}
    for r in rows:
        byver.setdefault(r["detected_version"] or "unknown", []).append(r)
    picks = []
    for ver in sorted(byver):
        rs = sorted(byver[ver], key=lambda r: int(r["size_bytes"]))
        for pick in (rs[0], rs[len(rs) // 2], rs[-1]):
            if pick not in picks:
                picks.append(pick)
    return picks


def main():
    rows = [r for r in csv.DictReader(MANIFEST.open()) if r["magic_ok"] == "yes"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fields = ["sha256", "size_bytes", "repo", "detected_version", "kind",
              "table_found", "n_records", "n_dir_records", "contiguous_pairs",
              "open_gaps", "satellite_gaps", "count_match", "join",
              "join_subset", "cum_ok", "d7_ok", "span", "names",
              "table_start", "table_end"]
    w = csv.DictWriter(OUT_FILES.open("w", newline=""), fieldnames=fields)
    w.writeheader()
    sample = sample_rows(rows)
    sample_shas = {r["sha256"] for r in sample}
    rfields = ["sha256", "detected_version", "record_ordinal", "record_start",
               "f1", "f2", "f3_hex", "idx", "f7", "f10", "name1", "name2",
               "names_total", "names_area", "guid_hex"]
    rw = csv.DictWriter(OUT_RECORDS.open("w", newline=""), fieldnames=rfields)
    rw.writeheader()

    totals = Counter()
    f2_dist = Counter()
    f3_dist = Counter()
    f7_dist = Counter()
    name_vocab = Counter()
    sample_set = set()
    for r in rows:
        p = ROOT / r["local_path"]
        size = int(r["size_bytes"])
        with p.open("rb") as fh:
            buf = fh.read(min(size, SCAN_WINDOW))
        t = scan_file(buf)
        recs = t["records"]
        totals["files"] += 1
        totals["table_found"] += bool(recs)
        totals["files_all_contiguous"] += bool(recs) and not t["gaps"]
        totals["files_count_match"] += bool(t["count_match"])
        totals["files_join_ok"] += bool(t["join"])
        totals["files_join_subset"] += bool(t["join_subset"])
        totals["files_cum_ok"] += t["cum_ok"] is True
        totals["files_d7_ok"] += t["d7_ok"] is True
        totals["anchors_rejected"] += t["anchors_rejected"]
        for rec in recs:
            totals["records"] += 1
            f2_dist[rec["f2"]] += 1
            f3_dist["%#010x" % rec["f3"]] += 1
            f7_dist[rec["f7"]] += 1
            name_vocab[rec["name1"]] += 1
        if r["sha256"] in sample_shas and r["sha256"] not in sample_set:
            sample_set.add(r["sha256"])
            for i, rec in enumerate(recs):
                rw.writerow({
                    "sha256": r["sha256"], "detected_version": r["detected_version"],
                    "record_ordinal": i, "record_start": rec["start"],
                    "f1": rec["f1"], "f2": rec["f2"], "f3_hex": "%#010x" % rec["f3"],
                    "idx": rec["idx"], "f7": rec["f7"], "f10": rec["f10"],
                    "name1": rec["name1"], "name2": rec["name2"],
                    "names_total": rec["total"], "names_area": rec["area"],
                    "guid_hex": rec["guid"].hex(),
                })
        gap_sat = sum(1 for _, kind in t["gaps"] if kind == "satellite")
        gap_unk = len(t["gaps"]) - gap_sat
        w.writerow({
            "sha256": r["sha256"], "size_bytes": size, "repo": r["repo"],
            "detected_version": r["detected_version"], "kind": r["kind"],
            "table_found": bool(recs), "n_records": len(recs),
            "n_dir_records": len(t["dirs"]),
            "contiguous_pairs": t["contiguous"], "open_gaps": gap_unk,
            "satellite_gaps": gap_sat, "count_match": t["count_match"],
            "join": t["join"], "join_subset": t["join_subset"],
            "cum_ok": t["cum_ok"], "d7_ok": t["d7_ok"],
            "span": t["span"],
            "names": ";".join(rec["name1"] for rec in recs),
            "table_start": recs[0]["start"] if recs else "",
            "table_end": recs[-1]["end"] if recs else "",
        })

    n = totals["files"]
    print("files scanned:", n)
    print("table found: {}/{}".format(totals["table_found"], n))
    print("records parsed:", totals["records"])
    print("anchor positions rejected by the record validator:", totals["anchors_rejected"])
    print("files with strictly contiguous records (no gaps): {}/{} table files".format(
        totals["files_all_contiguous"], totals["table_found"]))
    print("dir/name count match: {}/{} table files".format(
        totals["files_count_match"], totals["table_found"]))
    print("d6<->f1 bijection: {}/{} table files".format(
        totals["files_join_ok"], totals["table_found"]))
    print("d6<->f1 subset law: {}/{} table files".format(
        totals["files_join_subset"], totals["table_found"]))
    print("d5 cumulative law: {}/{} table files".format(
        totals["files_cum_ok"], totals["table_found"]))
    print("d7 == d6: {}/{} table files".format(totals["files_d7_ok"], totals["table_found"]))
    print("f2 distribution:", f2_dist.most_common(10))
    print("f3 distribution:", f3_dist.most_common())
    print("f7 distribution:", f7_dist.most_common(10))
    print("distinct name1 values:", len(name_vocab),
          "top:", name_vocab.most_common(12))
    print("sample records for {} files -> {}".format(len(sample_shas), OUT_RECORDS))
    print("wrote", OUT_FILES)
    return 0


if __name__ == "__main__":
    sys.exit(main())
