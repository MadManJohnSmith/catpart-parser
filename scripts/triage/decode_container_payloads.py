#!/usr/bin/env python3
"""Enumerate CATStorageProperty payload regions and their string inventory.

Step (b) of ticket #19 (CATProdCont / CATFeatCont payload layouts),
productionized from the step (a) extractor.  Companion to
decode_container_table.py, which parses the plaintext container-name
table: this script walks the *payload* side and joins the two by GUID.

Block/region model (empirical, V5R15-V5R24 evidence; see
docs/evidence/2026-11-07-container-payload-layout.md):

  A "storage block" starts at every ASCII occurrence of
  CATStorageProperty, normally preceded by the two tag bytes 34 12
  (blocks without the prefix are counted, not silently accepted).
  Header layout: 34 12 "CATStorageProperty" 80 01 ... 34 10
  "CATUnicodeString" a0 02 00 00 00 00 34 <u8 len> <name1> 9f a0 02
  ... 34 <u8 len> <name2> 9f 3b 10 ... <16-byte GUID>, with the GUID
  inside the first ~0x60-0x70 bytes for the common short names.  The
  GUID equals the GUID of one container-name-table record - except for
  the per-file "CATIA" identity block, whose GUID slot holds 16 zero
  bytes and which carries the document file name as name2.

  The block's "payload region" runs from the block start to the nearest
  of these boundaries: the next storage block, the next OSMX marker,
  the next "CATIA_V5 CB0001\0" marker, the header dword8 tail start
  (big-endian u32 at file offset 8), or EOF.

  String framings observed inside regions (lengths are character counts
  of the text that follows):
    tag34-name     0x34 + u8 len + ASCII text (doc-type and property
                   names), followed by 0x9f (value end) or a type-tag
                   byte (0x80/0xa0/0xe0 for structural names)
    u8tag-ascii    tag byte in 0x30-0x3f (except 0x34) + u8 len + ASCII
                   text (e.g. 36 08 "FINJPL  " registration names)
    u32le-ascii    u32le len + ASCII text (registration strings and -
                   dominating at corpus scale - attribute strings
                   inside geometry/stream regions)
    u16le-ascii    u16le len + ASCII text
    utf16-prop     u16le (2*chars+4) + u16le marker (3, or 5 for
                   CATPreview) + UTF-16LE text (property names)
    utf16-storage  u16le (2*chars+2) + UTF-16LE text (storage/stream
                   names)
    other          anything else (printable runs inside binary data:
                   JPEG tables, geometry/stream bytes)

  Payload regions also embed binary payloads (JPEG previews, geometry
  streams); their printable runs are not framed strings and dominate
  the "other" bucket.  String rows carry an in_jpeg flag (offset at or
  after the region's first JPEG SOI marker) so analyses can exclude
  suspected preview bytes.

  CATFeatCont is the negative case: it never appears as a record name1
  or as a block, and its literal bytes do not occur outside the name
  table (claim C7).

Read-only.  Run:

  .venv/bin/python -I scripts/triage/decode_container_payloads.py [FILE ...]
  .venv/bin/python -I scripts/triage/decode_container_payloads.py --manifest
      [--sample N] [--include-sha16 HEX,HEX,...] [--out-dir DIR]
      [--max-blocks N] [--max-strings-per-region N]

With FILE args, exactly those files are scanned.  With --manifest, files
come from manifests/corpus-manifest.csv (magic_ok == yes); --sample N
picks N files per detected_version deterministically (evenly spaced by
size); --include-sha16 force-adds files by 16-hex-char sha256 prefix.
Outputs (default docs/evidence/data/):

  container-payloads-scan.csv     one row per storage block/region
  container-payloads-strings.csv  one row per decoded string in a region
  container-payloads-claims.csv   per-claim, per-release consistency rates

Claim rates are tallied on the FULL per-file string inventory inside
scan_file (independent of CSV row caps) and are exactly recomputable
from container-payloads-scan.csv: n_by_framing carries the complete
per-region framing counts, including tag34 follow-byte tallies.  The
strings CSV is a bounded inventory: at most --max-strings-per-region
rows per region per text kind (ASCII and UTF-16 capped independently,
file order), text capped at 60 characters.  Claims:

  C1   GUID join: every storage block's 16-byte GUID (inside its first
       0x90 bytes) equals the GUID of one container-table record.
  C1b  same, excluding the CATIA identity block (null GUID by design).
  C2   Region boundary: the nearest-boundary rule yields a non-empty
       region whose end byte-verifies against the claimed marker kind.
  C3   Name framing: tag34 names are terminated by 0x9f.
  C3b  refined: tag34 names are followed by 0x9f or a type-tag byte
       (0x80/0xa0/0xe0); the marker set was read off the step (b)
       trial sample and is applied as a fixed model here.
  C4   Non-tag34 ASCII runs are length-prefixed: u16le, u32le or
       u8tag framing.
  C4b  among u16le/u32le framed rows, the u16le share.
  C5   UTF-16 runs match 2*chars+4 (property) or 2*chars+2 (storage).
  C5b  among framed utf16 rows, the property-formula share.
  C6   Exactly one CATProdCont record and exactly one block joined to
       it, per file that has either.
  C7   CATFeatCont: no name1 record, no block (by name or join), no
       literal occurrence outside the name table, per file with a
       parsed container table.
"""
import argparse
import csv
import mmap
import re
import sys
from bisect import bisect_right
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"

# Reused from the container-table decoder: record parse + anchor.
sys.path.insert(0, str(ROOT / "scripts" / "triage"))
from decode_container_table import ANCHOR, parse_record  # noqa: E402

SCAN_WINDOW = 2 * 1024 * 1024          # container-table window (as in B1)
STORAGE_WORD = b"CATStorageProperty"
STORAGE_WORD_LEN = len(STORAGE_WORD)
BLOCK_TAG = b"\x34\x12"
OSMX = b"OSMX"
CB0001 = b"CATIA_V5 CB0001\x00"
FEAT_CONT = b"CATFeatCont"
JPEG_SOI = b"\xff\xd8\xff"
GUID_WINDOW = 0x90                     # GUID sits within the first ~0x60-0x70 bytes
ASCII_RE = re.compile(rb"[\x20-\x7e]{4,}")
UTF16_RE = re.compile(rb"(?:[\x20-\x7e]\x00){4,}")
TEXT_CAP = 60                          # CSV text cap per string row
RELEASE_RE = re.compile(r"^V5R(\d+)")
TAG34_FOLLOW = frozenset((0x80, 0x9F, 0xA0, 0xE0))
CLAIMS = ("C1", "C1b", "C2", "C3", "C3b", "C4", "C4b", "C5", "C5b", "C6", "C7")

BLOCK_FIELDS = ["sha256", "detected_version", "release", "kind", "block_ordinal",
                "block_start", "prefix3412", "block_name", "guid_slot", "guid_hex",
                "join_status", "record_name1", "region_start", "region_end",
                "boundary_kind", "boundary_verified", "region_size",
                "n_strings", "n_strings_full", "n_by_framing", "overflow",
                "jpeg_preview", "guid_occurrences_outside_table"]
STRING_FIELDS = ["sha256", "block_start", "string_offset", "text_kind", "framing",
                 "marker_u16", "term9f", "follow_byte", "in_jpeg", "n_chars", "text"]
CLAIM_FIELDS = ["claim", "release", "files", "observations", "passes", "rate", "note"]


def u16(buf, off):
    return int.from_bytes(buf[off:off + 2], "little")


def u32(buf, off):
    return int.from_bytes(buf[off:off + 4], "little")


def release_of(detected_version):
    m = RELEASE_RE.match(detected_version or "")
    return "R" + m.group(1) if m else "other"


def find_all(buf, needle, start=0, limit=None):
    out = []
    i = buf.find(needle, start)
    while i >= 0:
        out.append(i)
        if limit and len(out) >= limit:
            break
        i = buf.find(needle, i + 1)
    return out


def parse_table(buf):
    """Parse container-name records in the given (2 MiB) window."""
    recs = []
    pos = buf.find(ANCHOR)
    while pos >= 32:
        rec = parse_record(buf, pos - 32)
        if rec:
            recs.append(rec)
            pos = buf.find(ANCHOR, rec["end"])
        else:
            pos = buf.find(ANCHOR, pos + 1)
    return recs


def block_name(buf, blk):
    """Doc-type name from the block's CATUnicodeString header, or ''."""
    bi = buf.find(b"CATUnicodeString", blk, blk + 64)
    if bi < 0:
        return "", False
    if buf[bi + 16:bi + 22] != b"\xa0\x02\x00\x00\x00\x00" or buf[bi + 22] != 0x34:
        return "", False
    ln = buf[bi + 23]
    name = bytes(buf[bi + 24:bi + 24 + ln])
    if len(name) != ln:
        return "", False
    return name.decode("ascii", "replace"), True


def classify_ascii(buf, off, n):
    """Framing kind of the ASCII run at off with n bytes.

    Returns (kind, marker, term9f, follow_byte).  marker is the framing
    length value for the length-prefixed kinds; term9f/follow_byte are
    set only for tag34-name (follow_byte is the byte after the text).
    """
    pre = bytes(buf[off - 4:off]) if off >= 4 else b""
    post = bytes(buf[off + n:off + n + 1])
    if len(pre) >= 2 and pre[-2] == 0x34 and pre[-1] == n <= 0xFF:
        fb = post[0] if post else None
        return "tag34-name", pre[-1], post == b"\x9f", fb
    if (len(pre) >= 2 and 0x30 <= pre[-2] <= 0x3F and pre[-2] != 0x34
            and pre[-1] == n <= 0xFF):
        return "u8tag-ascii", pre[-2], None, None
    if len(pre) >= 4 and u32(pre, 0) == n:
        return "u32le-ascii", u32(pre, 0), None, None
    if len(pre) >= 2 and u16(pre, 2) == n:
        return "u16le-ascii", u16(pre, 2), None, None
    return "other", None, None, None


def classify_utf16(buf, off, n):
    """Framing kind of the UTF-16LE run at off with n chars.

    Returns (kind, marker).  For utf16-prop, marker is the u16 sitting
    between the (2*chars+4) length field and the text (3, or 5 for
    CATPreview); for utf16-storage, it is the (2*chars+2) field itself.
    """
    pre = bytes(buf[off - 4:off]) if off >= 4 else b""
    w2 = u16(pre, 2) if len(pre) >= 2 else -1
    w4 = u16(pre, 0) if len(pre) >= 4 else -1
    if w4 == 2 * n + 4:
        return "utf16-prop", w2
    if w2 == 2 * n + 2:
        return "utf16-storage", w2
    return "other", None


def next_occurrence(sorted_list, after):
    """First element of a sorted offset list strictly greater than after."""
    i = bisect_right(sorted_list, after)
    return sorted_list[i] if i < len(sorted_list) else None


def scan_file(path, max_blocks, max_strings):
    """Scan one file.

    Returns (csv_block_rows, csv_string_rows, file_stats).  Claim
    tallies over the FULL inventory are in file_stats["tallies"] as
    {claim: [observations, passes]}; the CSV rows are capped per region
    and text kind (see module docstring).
    """
    tallies = {c: [0, 0] for c in CLAIMS}

    def tally(claim, passed):
        tallies[claim][0] += 1
        tallies[claim][1] += int(passed)

    stats = {"size": path.stat().st_size, "records": [], "guid_occ_out": {},
             "blocks_truncated": False, "feat_literal_outside_table": 0,
             "cb0001_count": 0, "tallies": tallies}
    block_rows, string_rows = [], []
    with path.open("rb") as fh:
        mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            size = mm.size()
            dword8 = int.from_bytes(mm[8:12], "big") if size >= 12 else 0
            recs = parse_table(mm[:min(size, SCAN_WINDOW)])
            stats["records"] = recs
            stats["cb0001_count"] = len(find_all(mm, CB0001))
            tab_lo = recs[0]["start"] if recs else 0
            tab_hi = recs[-1]["end"] if recs else 0
            # GUID occurrences outside the name table, per record
            for rec in recs:
                occs = [o for o in find_all(mm, rec["guid"])
                        if o < tab_lo or o >= tab_hi]
                stats["guid_occ_out"][rec["guid"].hex()] = len(occs)
            stats["feat_literal_outside_table"] = len(
                [o for o in find_all(mm, FEAT_CONT) if o < tab_lo or o >= tab_hi])

            osmx_all = find_all(mm, OSMX)
            cb_all = find_all(mm, CB0001)
            occs = find_all(mm, STORAGE_WORD, limit=max_blocks + 1)
            stats["blocks_truncated"] = len(occs) > max_blocks
            occs = occs[:max_blocks]
            blk_starts = [o - 2 if mm[o - 2:o] == BLOCK_TAG else o for o in occs]
            recs_by_guid = defaultdict(list)
            for rec in recs:
                recs_by_guid[rec["guid"]].append(rec)
            guid_order = [rec["guid"] for rec in recs]

            for ordinal, blk in enumerate(blk_starts):
                prefix = mm[blk:blk + 2] == BLOCK_TAG
                name, name_ok = block_name(mm, blk)
                # GUID join: smallest-slot table-record GUID in the window
                guid, guid_slot, joined, dup = "", -1, None, False
                for g in guid_order:
                    k = mm.find(g, blk, blk + GUID_WINDOW)
                    if k >= 0 and (guid_slot < 0 or k - blk < guid_slot):
                        guid, guid_slot = g, k - blk
                        joined = recs_by_guid[g][0]
                        dup = len(recs_by_guid[g]) > 1
                join_status = ("no-match" if not guid else
                               ("record-dup-guid" if dup else "record"))
                # region end: nearest boundary after the block
                cands = [(size, 4, "EOF"), (dword8, 3, "dword8")]
                nxt = next_occurrence(blk_starts, blk)
                if nxt is not None:
                    cands.append((nxt, 0, "nxtblk"))
                o = next_occurrence(osmx_all, blk)
                if o is not None:
                    cands.append((o, 1, "OSMX"))
                o = next_occurrence(cb_all, blk)
                if o is not None:
                    cands.append((o, 2, "CB0001"))
                end, _, bkind = min(cands)
                end = min(end, size)
                # boundary byte verification
                if bkind == "nxtblk":
                    ok = (mm[end:end + 2] == BLOCK_TAG and
                          mm[end + 2:end + 2 + STORAGE_WORD_LEN] == STORAGE_WORD)
                elif bkind == "OSMX":
                    ok = mm[end:end + 4] == OSMX
                elif bkind == "CB0001":
                    ok = mm[end:end + 16] == CB0001
                elif bkind == "dword8":
                    ok = end == dword8 <= size
                else:
                    ok = end == size and blk == blk_starts[-1]
                joined_ok = bool(guid) and joined is not None
                tally("C1", joined_ok)
                if name != "CATIA":
                    tally("C1b", joined_ok)
                tally("C2", bool(ok) and end > blk)
                soi = mm.find(JPEG_SOI, blk, end)
                row = {
                    "sha256": "", "detected_version": "", "release": "", "kind": "",
                    "block_ordinal": ordinal, "block_start": blk,
                    "prefix3412": prefix, "block_name": name if name_ok else "",
                    "guid_slot": guid_slot, "guid_hex": guid.hex() if guid else "",
                    "join_status": join_status,
                    "record_name1": joined["name1"] if joined else "",
                    "region_start": blk, "region_end": end, "boundary_kind": bkind,
                    "boundary_verified": bool(ok), "region_size": end - blk,
                    "n_strings": 0, "n_strings_full": 0, "n_by_framing": "",
                    "overflow": False, "jpeg_preview": soi >= 0,
                    "guid_occurrences_outside_table":
                        stats["guid_occ_out"].get(guid.hex(), "") if guid else "",
                }
                block_rows.append(row)

            # strings: one pass per regex over the file, assigned to regions
            regions = sorted((b["region_start"], b["region_end"]) for b in block_rows)
            row_by_start = {}
            for b in block_rows:
                row_by_start.setdefault(b["region_start"], b)
            soi_by_start = {b["region_start"]: mm.find(JPEG_SOI, b["region_start"],
                                                       b["region_end"])
                            for b in block_rows if b["jpeg_preview"]}
            n_written = defaultdict(int)
            for rex, is_u16 in ((ASCII_RE, False), (UTF16_RE, True)):
                ri = 0
                for m in rex.finditer(mm):
                    off, raw = m.start(), m.group()
                    while ri < len(regions) and off >= regions[ri][1]:
                        ri += 1
                    if ri >= len(regions) or off < regions[ri][0]:
                        continue
                    blk_row = row_by_start[regions[ri][0]]
                    blk_row["n_strings_full"] += 1
                    if is_u16:
                        n = len(raw) // 2
                        kind, marker = classify_utf16(mm, off, n)
                        text = raw.decode("utf-16-le", "replace")
                        term, fbyte = None, None
                    else:
                        n = len(raw)
                        kind, marker, term, fbyte = classify_ascii(mm, off, n)
                        text = raw.decode("ascii", "replace")
                    kinds = blk_row.setdefault("_kinds", Counter())
                    kinds[kind] += 1
                    if kind == "tag34-name":
                        tally("C3", bool(term))
                        tally("C3b", fbyte in TAG34_FOLLOW)
                        kinds["tag34:follow%#04x" % (fbyte if fbyte is not None
                                                     else -1)] += 1
                    elif is_u16:
                        framed = kind in ("utf16-prop", "utf16-storage")
                        tally("C5", framed)
                        if framed:
                            tally("C5b", kind == "utf16-prop")
                    else:
                        framed = kind in ("u16le-ascii", "u32le-ascii", "u8tag-ascii")
                        tally("C4", framed)
                        if kind in ("u16le-ascii", "u32le-ascii"):
                            tally("C4b", kind == "u16le-ascii")
                    if n_written[(blk_row["block_start"], is_u16)] >= max_strings:
                        blk_row["overflow"] = True
                        continue
                    n_written[(blk_row["block_start"], is_u16)] += 1
                    blk_row["n_strings"] += 1
                    k = soi_by_start.get(blk_row["region_start"])
                    string_rows.append({
                        "sha256": "", "block_start": blk_row["block_start"],
                        "string_offset": off,
                        "text_kind": "utf16" if is_u16 else "ascii",
                        "framing": kind,
                        "marker_u16": "" if marker is None else marker,
                        "term9f": "" if term is None else term,
                        "follow_byte": "" if fbyte is None else "%#04x" % fbyte,
                        "in_jpeg": bool(k is not None and off >= k),
                        "n_chars": n, "text": text[:TEXT_CAP],
                    })
            for b in block_rows:
                kinds = b.pop("_kinds", Counter())
                b["n_by_framing"] = ";".join(
                    "%s=%d" % (k, kinds[k]) for k in sorted(kinds))
        finally:
            mm.close()

    # C6: record-side, one CATProdCont record joined by exactly one block
    n_prod_rec = sum(1 for x in recs if x["name1"] == "CATProdCont")
    prod_joined = [b for b in block_rows if b["record_name1"] == "CATProdCont"]
    if n_prod_rec or prod_joined:
        tally("C6", len(prod_joined) == 1 and n_prod_rec == 1)
    # C7: per-file negative claim (files with a parsed table)
    n_feat_rec = sum(1 for x in recs if x["name1"] == "CATFeatCont")
    feat_joined = [b for b in block_rows if b["record_name1"] == "CATFeatCont"]
    feat_named = [b for b in block_rows if b["block_name"] == "CATFeatCont"]
    clean = (bool(recs) and n_feat_rec == 0 and not feat_joined and not feat_named
             and stats["feat_literal_outside_table"] == 0)
    if recs:
        tally("C7", clean)
    stats["prod"] = (n_prod_rec, len(prod_joined))
    stats["feat"] = (n_feat_rec, len(feat_joined), len(feat_named),
                     stats["feat_literal_outside_table"])
    return block_rows, string_rows, stats


def pick_sample(manifest_rows, per_version):
    """Deterministic per-detected_version sample: evenly spaced by size."""
    pool = defaultdict(list)
    for r in manifest_rows:
        if r["detected_version"] and r["detected_version"] != "unknown":
            pool[r["detected_version"]].append(r)
    picked = set()
    for ver in sorted(pool):
        rs = sorted(pool[ver], key=lambda r: (int(r["size_bytes"]), r["sha256"]))
        n = min(per_version, len(rs))
        idx = sorted({round(i * (len(rs) - 1) / max(n - 1, 1)) for i in range(n)})
        for i in idx:
            picked.add(rs[i]["sha256"])
    return [r for r in manifest_rows if r["sha256"] in picked]


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Enumerate CATStorageProperty payload regions (ticket #19 step b)")
    ap.add_argument("files", nargs="*", help="corpus files to scan")
    ap.add_argument("--manifest", action="store_true",
                    help="walk manifests/corpus-manifest.csv (magic_ok == yes)")
    ap.add_argument("--sample", type=int, default=0, metavar="N",
                    help="with --manifest: N files per detected_version")
    ap.add_argument("--include-sha16", default="", metavar="HEX,HEX,...",
                    help="force-include files by 16-char sha256 prefix")
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    ap.add_argument("--max-blocks", type=int, default=4096)
    ap.add_argument("--max-strings-per-region", type=int, default=3000)
    args = ap.parse_args(argv)

    manifest = [r for r in csv.DictReader(MANIFEST.open()) if r["magic_ok"] == "yes"]
    by_prefix = {r["sha256"][:16]: r for r in manifest}

    selected = []
    if args.files:
        for f in args.files:
            p = Path(f).resolve()
            sha = next((r for r in manifest if (ROOT / r["local_path"]) == p), None)
            selected.append(sha or {"local_path": str(p), "sha256": "", "kind": "",
                                    "size_bytes": str(p.stat().st_size),
                                    "detected_version": ""})
    elif args.manifest:
        rows = pick_sample(manifest, args.sample) if args.sample else list(manifest)
        for pref in [p for p in args.include_sha16.split(",") if p]:
            if pref in by_prefix and by_prefix[pref] not in rows:
                rows.append(by_prefix[pref])
        seen = set()
        selected = [r for r in rows if not (r["sha256"] in seen or seen.add(r["sha256"]))]
    else:
        ap.error("give FILE args or --manifest")
        return 2

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    block_rows, string_rows = [], []
    per_claim = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    rels = set()
    feat_by_rel = defaultdict(Counter)
    prod_dist = Counter()
    no_table_files = 0
    cb2_files = 0
    overflow_regions = 0

    for r in selected:
        p = ROOT / r["local_path"]
        blocks, strings, stats = scan_file(p, args.max_blocks,
                                           args.max_strings_per_region)
        sha16 = (r["sha256"] or p.name)[:16]
        ver = r.get("detected_version", "")
        rel = release_of(ver)
        rels.add(rel)
        for b in blocks:
            b.update({"sha256": sha16, "detected_version": ver, "release": rel,
                      "kind": r.get("kind", "")})
        for s in strings:
            s["sha256"] = sha16
        block_rows.extend(blocks)
        string_rows.extend(strings)
        overflow_regions += sum(1 for b in blocks if b["overflow"])
        if not stats["records"]:
            no_table_files += 1
        if stats["cb0001_count"] >= 2:
            cb2_files += 1
        for claim, (obs, p_) in stats["tallies"].items():
            per_claim[claim][rel][0] += obs
            per_claim[claim][rel][1] += p_
        n_rec, n_joined = stats["prod"]
        if n_rec or n_joined:
            prod_dist[(rel, n_joined, n_rec)] += 1
        nf, fj, fnm, flit = stats["feat"]
        if nf or fj or fnm or flit:
            feat_by_rel[rel]["files"] += 1
            feat_by_rel[rel]["records"] += nf
            feat_by_rel[rel]["joined_blocks"] += fj
            feat_by_rel[rel]["named_blocks"] += fnm
            feat_by_rel[rel]["literal_outside"] += flit

    # ---- write CSVs ----
    with (out_dir / "container-payloads-scan.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=BLOCK_FIELDS)
        w.writeheader()
        w.writerows(block_rows)
    with (out_dir / "container-payloads-strings.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=STRING_FIELDS)
        w.writeheader()
        w.writerows(string_rows)

    claim_rows = []
    for claim in ("C1", "C1b", "C2", "C3", "C3b", "C4", "C4b", "C5", "C5b", "C6"):
        for rel in sorted(rels):
            obs, p_ = per_claim[claim][rel]
            rate = (p_ / obs) if obs else None
            claim_rows.append({"claim": claim, "release": rel, "files": "",
                               "observations": obs, "passes": p_,
                               "rate": "" if rate is None else "%.4f" % rate,
                               "note": ""})
    for rel in sorted(rels):
        obs, p_ = per_claim["C7"][rel]
        if not obs:
            continue
        c = feat_by_rel[rel]
        claim_rows.append({
            "claim": "C7", "release": rel, "files": c["files"],
            "observations": obs, "passes": p_,
            "rate": "%.4f" % (p_ / obs) if obs else "",
            "note": "feat_records=%d joined_blocks=%d named_blocks=%d "
                    "literal_outside_table=%d"
                    % (c["records"], c["joined_blocks"], c["named_blocks"],
                       c["literal_outside"])})
    with (out_dir / "container-payloads-claims.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CLAIM_FIELDS)
        w.writeheader()
        w.writerows(claim_rows)

    # ---- printed summary ----
    agg = defaultdict(lambda: [0, 0])
    for row in claim_rows:
        agg[row["claim"]][0] += row["observations"]
        agg[row["claim"]][1] += row["passes"]
    print("files scanned:", len(selected))
    print("blocks:", len(block_rows), " string rows written:", len(string_rows),
          " overflow regions:", overflow_regions)
    print("files with no container table parsed:", no_table_files)
    print("files with >=2 CB0001 markers:", cb2_files)
    print("per-claim corpus-wide (passes/observations = rate):")
    for claim in CLAIMS:
        obs, p_ = agg[claim]
        print("  %-3s %d/%d = %s" % (claim, p_, obs,
              ("%.4f" % (p_ / obs)) if obs else "n/a"))
    print("C6 distribution (release, prod_joined_blocks, prod_records) -> files:")
    for (rel, nb, nr), n in sorted(prod_dist.items()):
        print("  %-4s blocks=%d records=%d : %d files" % (rel, nb, nr, n))
    print("wrote", out_dir / "container-payloads-scan.csv")
    print("wrote", out_dir / "container-payloads-strings.csv")
    print("wrote", out_dir / "container-payloads-claims.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
