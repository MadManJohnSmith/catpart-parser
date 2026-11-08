#!/usr/bin/env python3
"""Locate and characterize the geometry payloads (B4, ticket #20).

Builds on B2's tail catalog (decode_tail_region.py: named regions with
absolute (X, Y) offsets) and B3's CATStorageProperty block scan
(decode_container_payloads.py: doc-type blocks joined to the container
table by GUID).  This script maps WHERE the high-entropy geometry bytes
sit and tests the embedded-tessellation question with byte evidence.

Model (all claims labeled in the evidence note):

  Tail catalog.  The tail's named regions tile the file body (B2).
  On large files the primary walk stops early (B2's known decoder
  limits); a RESYNC continuation re-anchors on the next `00 00 6a`
  hdr84 pattern and keeps parsing entries with a relaxed name check
  (NUL char inside the field instead of B2's next-record zeros check).
  Resync entries are marked and their coverage is labeled candidate.
  Embedded tail blobs (B2's 20-65 KB family) appear as resync gaps.

  Storage blocks.  Every `34 12 CATStorageProperty` block carries a
  doc-type name (name1: CGMGeom, CATCGRCont, CATStdCont, ...); its
  B3 payload region runs to the nearest of next block / OSMX / CB0001 /
  dword8 / EOF.  The corpus-wide region-size profile by container name
  is the bulk-payload locator.

  Nested stream stores.  CATStdCont / CATSeeBodyCont (and rarely other)
  block regions embed a nested `V5_CFV2\\0` container: a 32-byte header
  (dword8/dword12 big-endian, ff x 8) whose dword8 points at a nested
  `CATIA_V5 CB0001\\0` catalog that names sub-streams (measured
  vocabulary: MainDataStream, Describe, Header, SceneGraph,
  SurfacicReps, MAIN).  Nested entry X/Y coordinates are recorded
  as-is (their coordinate base is not resolved here).

  Strip-index records (the tessellation candidate signature, G1).
  Inside the nested stream stores the payload is a sequence of records
  `01 <marker 0x41-0x4f> <type> ff [u32le n] [n x u16be]` - a u16be
  marker in 0x0141-0x014f, a type byte, 0xff, a little-endian count,
  then n big-endian u16 indices (observed n = 6 and 21 with strip-like
  zig-zag index patterns; markers 0x0141/0142/0143/0149/014a/014c/014f
  observed on the probe file).  A record is "verified" when
  1 <= n <= 1e6 and the record fits in the file; "chained" when the
  next bytes start the next record of the family.

  CGMGeom record tags.  CGMGeom regions carry a different record
  family: `[u16le t][u32le n]"2-0"/"2X-0"` version tags (exact byte
  signatures `03 00 00 00 "2-0"` and `04 00 00 00 "2X-0"`).

Read-only; run with:  python3 -I scripts/triage/decode_geometry_payloads.py
  --deep-sha16 HEX16[,HEX16...]   location-map sample (entropy + zones +
                                  regions + blocks CSVs)
  [--validate-sample N]           stratified corpus sample: N files per
                                  detected_version (evenly spaced by
                                  size) for the signature rates
  [--include-sha16 HEX16,...]     extra files for the validation sample

Outputs (docs/evidence/data/):
  geometry-payloads-files.csv     one row per scanned file (all modes)
  geometry-payloads-regions.csv   tail regions of the deep sample
  geometry-payloads-zones.csv     high-entropy zones of the deep sample
  geometry-payloads-blocks.csv    storage blocks of the deep sample
  geometry-payloads-sigscan.csv   per-file signature counts (all files)
and a claim-rate summary on stdout.
"""
import argparse
import csv
import math
import mmap
import re
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"

sys.path.insert(0, str(ROOT / "scripts" / "triage"))
from decode_tail_region import scan_tail, release_of  # noqa: E402
from decode_container_payloads import block_name  # noqa: E402

DEEP16_DEFAULT = [
    "17930babf0fd01a8",  # 375.7 MB V5R20 Apoloo13/ASE_III diente_superior_molde
    "bad44bdf52f5c411",  # 237.9 MB V5R24 Dictor/HaneulMyo PalmDown5motors2
    "13bb5c0c49616ade",  # 190.2 MB V5R21 hssnadr LedStrips_Smooth
    "50cd280f35dc350b",  # 175.0 MB V5R21 hssnadr Hitbox_WorkFile_main
    "086a4effaab79779",  #  18.7 MB V5R20 Apoloo13 head
    "e9ca6192a2854002",  #   8.9 MB V5R19 povdoigt/SP-02 SP02_PCB_Allumage_Pre-RCE
    "70b59f2a0eb60c1c",  #   5.4 MB V5R21 huanhuan233/CAAclean 550.001 A
    "3d9cb9548b01918b",  #   2.3 MB V5R18 dolganin/SO_SPIDAR300 471510001_HDMI
]

V5_CFV2 = b"V5_CFV2\x00"
CB0001 = b"CATIA_V5 CB0001\x00"
OSMX = b"OSMX"
JPEG_SOI = b"\xff\xd8\xff"
BLOCK_TAG = b"\x34\x12"
STORAGE_WORD = b"CATStorageProperty"
STRIP_RE = re.compile(rb"\x01[\x41-\x4f].\xff", re.DOTALL)
HDR84_ANCHOR = re.compile(rb"\x00\x00\x6a\x00\x00")
TAG20_RE = re.compile(rb"\x03\x00\x00\x002-0")
TAG2X0_RE = re.compile(rb"\x04\x00\x00\x002[0-9]-0")
ENT_BLK = 65536
ENT_HI = 7.2
NESTED_PROBE = 0x400
STREAM_TOKENS = ("SurfacicReps", "SceneGraph", "MainDataStream")
NESTED_CONTAINERS = ("CATStdCont", "CATSeeBodyCont", "CATBRepModeContainer",
                     "CATXDocLinkCont", "CGMGeom", "CATPrtCont", "CATMFBRP",
                     "CATCGRCont")

FILE_FIELDS = [
    "sha256", "size_bytes", "repo", "detected_version", "release", "kind",
    "sample", "dword8", "dword12",
    "n_blocks", "block_names", "n_parts_like",
    "cgmgeom_region_max", "cgrcont_region_max", "stdcont_region_max",
    "stdcont_nested", "seebody_nested", "stream_tokens_any_region",
    "surfacicreps_files_token", "scenegraph_files_token",
    "strip_markers", "strip_verified", "strip_chained",
    "strip_in_stdcont", "strip_in_cgmgeom", "strip_bytes_est",
    "tag20_hits", "tag2x0_hits", "catcgm_hits",
    "osmx_count", "cb0001_count", "jpeg_count",
    "ent_share_hi", "ent_mean", "hi_bytes_in_stdcont",
    "hi_bytes_in_cgmgeom", "hi_bytes_in_tail_named", "hi_bytes_total",
    "tail_entries_primary", "tail_entries_resync", "tail_resync_gaps",
]
REGION_FIELDS = ["sha256", "size_bytes", "detected_version", "entry_ordinal",
                 "seq", "space", "name_kind", "name", "X", "Y", "walk_part",
                 "reg_ent_mean", "reg_ent_max", "reg_hi_share"]
ZONE_FIELDS = ["sha256", "size_bytes", "detected_version", "zone_ordinal",
               "zone_start", "zone_end", "zone_bytes", "zone_ent_mean",
               "tail_owner_names", "tail_owner_cover", "block_owner",
               "nested_store"]
BLOCK_FIELDS = ["sha256", "size_bytes", "detected_version", "block_ordinal",
                "block_start", "block_name", "region_start", "region_end",
                "region_size", "boundary_kind", "nested_v5cfv2",
                "nested_d8", "nested_d12", "nested_tail_magic",
                "nested_entries", "nested_names", "reg_ent_mean",
                "reg_hi_share"]
SIG_FIELDS = ["sha256", "detected_version", "release", "kind", "size_bytes",
              "sig", "count"]
def find_all(mm, needle, start=0, limit=None):
    out = []
    i = mm.find(needle, start)
    while i >= 0:
        out.append(i)
        if limit and len(out) >= limit:
            break
        i = mm.find(needle, i + 1)
    return out


def u16(buf, off):
    return int.from_bytes(buf[off:off + 2], "little")


def u32(buf, off):
    return int.from_bytes(buf[off:off + 4], "little")


def entropy_list(mm, size, blk=ENT_BLK):
    """Per-block Shannon entropy (bits/byte) over [0, size)."""
    out = []
    for off in range(0, size, blk):
        b = mm[off:min(off + blk, size)]
        c = Counter(b)
        n = len(b)
        e = -sum((v / n) * math.log2(v / n) for v in c.values()) if n else 0.0
        out.append(e)
    return out


def high_runs(ent, blk=ENT_BLK, thresh=ENT_HI):
    """Merged high-entropy byte runs [(start, end)]."""
    runs = []
    for i, e in enumerate(ent):
        if e >= thresh:
            if runs and runs[-1][1] == i * blk:
                runs[-1][1] = (i + 1) * blk
            else:
                runs.append([i * blk, (i + 1) * blk])
    return runs


def relaxed_name(t, i):
    """Catalog name with only the in-field NUL check (resync walk).

    Same framing families as decode_tail_region.parse_name; the trailing
    next-record zeros check is dropped so entries followed by an
    embedded tail blob still parse.
    """
    N = len(t)
    if i + 4 > N:
        return None
    ln = u16(t, i)
    if ln % 2 or ln < 6 or ln > 1024:
        return None
    nc = (ln - 2) // 2
    if nc >= 1 and i + 2 + ln <= N and \
            t[i + 2 + ln - 2:i + 2 + ln] == b"\x00\x00":
        seg = t[i + 2:i + 2 + 2 * nc]
        if len(seg) == 2 * nc:
            try:
                s = seg.decode("utf-16-le")
            except UnicodeDecodeError:
                s = None
            if s and all(ord(c) >= 32 for c in s):
                return ("storage", s, i + 2 + ln)
    nc = (ln - 4) // 2
    if nc >= 1 and i + 2 + ln <= N and u16(t, i + 2) in (3, 5) and \
            t[i + 2 + ln - 2:i + 2 + ln] == b"\x00\x00":
        seg = t[i + 4:i + 4 + 2 * nc]
        if len(seg) == 2 * nc:
            try:
                s = seg.decode("utf-16-le")
            except UnicodeDecodeError:
                s = None
            if s and all(ord(c) >= 32 for c in s):
                return ("prop", s, i + 2 + ln)
    return None


def resync_walk(t, start, max_iter=200000):
    """Continue a broken catalog walk from tail offset `start`.

    Finds the next hdr84 anchor `00 00 6a 00 00` whose entry validates
    (flag 01, Y1 == Y2, relaxed name) and appends entries until the
    trailer zone.  Returns (new_entries, gap_bytes_total, gaps).
    """
    new = []
    gaps = []
    pos = start
    n = len(t)
    for _ in range(max_iter):
        if pos + 184 + 8 > n - 36:
            break
        m = HDR84_ANCHOR.search(t, pos, n - 36)
        if not m:
            break
        base = m.start()
        gap = base - pos
        if gap > 0:
            gaps.append((pos, gap))
        ok = False
        if t[base + 84] == 0x01:
            X, Y1, Y2 = struct.unpack(">III", t[base + 85:base + 97])
            if Y1 == Y2:
                nm = relaxed_name(t, base + 184)
                if nm and nm[2] <= n - 28:
                    new.append({"base": base, "seq": u16(t, base + 6),
                                "sp": u32(t, base + 8), "X": X, "Y": Y1,
                                "kind": nm[0], "name": nm[1],
                                "walk_part": "resync"})
                    pos = nm[2]
                    ok = True
        if not ok:
            pos = base + 1
    return new, sum(g for _, g in gaps), gaps


def catalog_with_resync(t, d8):
    """B2 primary walk + resync continuation.  Returns (entries, stats)."""
    s = scan_tail(t, d8)
    ents = list(s["entries"])
    for e in ents:
        e["walk_part"] = "primary"
    gaps_total = 0
    gaps = []
    if not s["walk_ok"] and s["break"]:
        brk = s["break"]
        if "@" in brk:
            pos = int(brk.split("@")[1])
            new, gt, gp = resync_walk(t, pos)
            ents.extend(new)
            gaps_total, gaps = gt, gp
    return ents, {"primary": len([e for e in ents if e["walk_part"] == "primary"]),
                  "resync": len([e for e in ents if e["walk_part"] == "resync"]),
                  "gaps_total": gaps_total, "gaps": gaps,
                  "ends_cbend": s.get("ends_cbend", False),
                  "trailer": (s.get("B"), s.get("C")) if s.get("ends_cbend") else None}


def strip_records(mm, size, markers):
    """Verify `01 4X <type> ff [u32le n] [n x u16be]` records.

    Returns (n_verified, n_chained, index_bytes_total).
    """
    ver = chained = 0
    idx_bytes = 0
    for m in markers:
        o = m.start()
        n = u32(mm, o + 4)
        if 1 <= n <= 1000000 and o + 8 + 2 * n <= size:
            ver += 1
            idx_bytes += 2 * n
            nxt = mm[o + 8 + 2 * n:o + 10 + 2 * n]
            if len(nxt) == 2 and nxt[0] == 0x01 and 0x41 <= nxt[1] <= 0x4F:
                chained += 1
    return ver, chained, idx_bytes


def nested_probe(mm, blk, size):
    """Probe a block region for a nested V5_CFV2 container + its catalog."""
    out = {"nested_v5cfv2": False, "nested_d8": "", "nested_d12": "",
           "nested_tail_magic": "", "nested_entries": "", "nested_names": ""}
    hi = min(blk + NESTED_PROBE, size)
    j = mm.find(V5_CFV2, blk, hi)
    if j < 0:
        return out
    out["nested_v5cfv2"] = True
    nh = mm[j:j + 32]
    if len(nh) == 32:
        nd8 = int.from_bytes(nh[8:12], "big")
        nd12 = int.from_bytes(nh[12:16], "big")
        out["nested_d8"] = nd8
        out["nested_d12"] = nd12
        tl = j + nd8
        if nh[16:24] == b"\xff" * 8 and 0 < tl < size and \
                mm[tl:tl + 16] == CB0001:
            out["nested_tail_magic"] = True
            nt = mm[tl:min(tl + nd12, size)]
            ents, st = catalog_with_resync(nt, 0)
            out["nested_entries"] = len(ents)
            names = []
            for e in ents:
                if e["name"] not in names:
                    names.append(e["name"])
            out["nested_names"] = ";".join(names[:24])
    return out


def overlap_names(regs, lo, hi):
    """Tail regions overlapping [lo, hi): (name list, covered bytes)."""
    cov = 0
    names = []
    for X, Y, nm in regs:
        a, b = max(X, lo), min(X + Y, hi)
        if a < b:
            cov += b - a
            if nm not in names:
                names.append(nm)
    return names, cov


def sample_by_version(rows, n):
    """N files per detected_version, evenly spaced by size (B3 rule)."""
    byver = defaultdict(list)
    for r in rows:
        byver[r["detected_version"] or "unknown"].append(r)
    picks = []
    for ver in sorted(byver):
        rs = sorted(byver[ver], key=lambda r: int(r["size_bytes"]))
        if len(rs) <= n:
            picks.extend(rs)
        else:
            step = (len(rs) - 1) / (n - 1) if n > 1 else 0
            picks.extend(rs[round(k * step)] for k in range(n))
    return picks


def scan_file(path, deep):
    """One file: blocks, signatures, nested stores, (deep: entropy+catalog)."""
    stats = {}
    with path.open("rb") as fh:
        mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        size = mm.size()
        head = bytes(mm[:32])
        d8 = int.from_bytes(head[8:12], "big") if size >= 12 else 0
        d12 = int.from_bytes(head[12:16], "big") if size >= 16 else 0
        stats["size"] = size
        stats["d8"], stats["d12"] = d8, d12

        # storage blocks
        occs = find_all(mm, STORAGE_WORD)
        blk_starts = [o - 2 if mm[o - 2:o] == BLOCK_TAG else o for o in occs]
        osmx_all = find_all(mm, OSMX)
        cb_all = find_all(mm, CB0001)
        blocks = []
        for ordinal, blk in enumerate(blk_starts):
            name, _ = block_name(mm, blk)
            cands = [(size, 4, "EOF"), (d8, 3, "dword8")]
            nxt = blk_starts[ordinal + 1] if ordinal + 1 < len(blk_starts) else None
            if nxt is not None:
                cands.append((nxt, 0, "nxtblk"))
            o = next((x for x in osmx_all if x > blk), None)
            if o is not None:
                cands.append((o, 1, "OSMX"))
            o = next((x for x in cb_all if x > blk), None)
            if o is not None:
                cands.append((o, 2, "CB0001"))
            end, _, bkind = min(cands)
            end = min(end, size)
            blocks.append({"ordinal": ordinal, "start": blk, "name": name,
                           "region_start": blk, "region_end": end,
                           "boundary": bkind})
        stats["blocks"] = blocks
        stats["n_parts_like"] = sum(
            1 for b in blocks
            if b["name"] in ("CGMGeom", "CATCGRCont", "CATStdCont",
                             "CATSeeBodyCont", "CATBRepModeContainer",
                             "CATPart", "CATPrtCont", "CATProdCont"))

        def reg_max(nm):
            return max((b["region_end"] - b["region_start"]
                        for b in blocks if b["name"] == nm), default=0)
        for nm, key in (("CGMGeom", "cgmgeom_region_max"),
                        ("CATCGRCont", "cgrcont_region_max"),
                        ("CATStdCont", "stdcont_region_max")):
            stats[key] = reg_max(nm)

        # nested stream stores
        nested_cnt = Counter()
        tok_any = 0
        surf = scen = 0
        for b in blocks:
            if b["name"] in NESTED_CONTAINERS:
                pr = nested_probe(mm, b["start"], size)
                b.update(pr)
                if pr["nested_v5cfv2"]:
                    nested_cnt[b["name"]] += 1
            for tok in STREAM_TOKENS:
                tb = tok.encode("utf-16-le")
                if mm.find(tb, b["region_start"], b["region_end"]) >= 0:
                    tok_any = 1
                    if tok == "SurfacicReps":
                        surf = 1
                    elif tok == "SceneGraph":
                        scen = 1
        stats["stdcont_nested"] = nested_cnt.get("CATStdCont", 0)
        stats["seebody_nested"] = nested_cnt.get("CATSeeBodyCont", 0)
        stats["stream_tokens_any_region"] = tok_any
        stats["surfacicreps"] = surf
        stats["scenegraph"] = scen

        # signatures
        markers = list(STRIP_RE.finditer(mm))
        ver, chained, idx_bytes = strip_records(mm, size, markers)
        stats["strip_markers"] = len(markers)
        stats["strip_verified"] = ver
        stats["strip_chained"] = chained
        stats["strip_bytes_est"] = idx_bytes
        # strip records inside CATStdCont / CGMGeom block regions
        def strip_in(nm):
            tot = 0
            regs = [(b["region_start"], b["region_end"]) for b in blocks
                    if b["name"] == nm]
            for m in markers:
                o = m.start()
                if any(a <= o < e for a, e in regs):
                    tot += 1
            return tot
        stats["strip_in_stdcont"] = strip_in("CATStdCont")
        stats["strip_in_cgmgeom"] = strip_in("CGMGeom")
        stats["tag20_hits"] = len(TAG20_RE.findall(mm))
        stats["tag2x0_hits"] = len(TAG2X0_RE.findall(mm))
        stats["catcgm_hits"] = len(find_all(mm, b"CATCGM"))
        stats["osmx_count"] = len(osmx_all)
        stats["cb0001_count"] = len(cb_all)
        stats["jpeg_count"] = len(find_all(mm, JPEG_SOI))

        # deep: entropy + tail catalog + attribution
        if deep:
            ent = entropy_list(mm, size)
            stats["ent"] = ent
            stats["ent_mean"] = sum(ent) / len(ent)
            stats["ent_share_hi"] = sum(1 for e in ent if e >= ENT_HI) / len(ent)
            runs = high_runs(ent)
            stats["runs"] = runs
            tail = mm[d8:]
            ents, cst = catalog_with_resync(tail, d8)
            stats["tail_entries_primary"] = cst["primary"]
            stats["tail_entries_resync"] = cst["resync"]
            stats["tail_resync_gaps"] = cst["gaps_total"]
            regs = [(e["X"], e["Y"], e["name"]) for e in ents]
            if cst["ends_cbend"] and cst["trailer"]:
                regs.append((cst["trailer"][0], cst["trailer"][1], "<trailer>"))
            regs.sort()
            stats["tail_regs"] = regs
            stats["tail_entries"] = ents

            def region_ent_stats(lo, hi):
                i0, i1 = lo // ENT_BLK, max(lo // ENT_BLK, (hi - 1) // ENT_BLK)
                es = ent[i0:i1 + 1]
                if not es:
                    return 0.0, 0.0, 0.0
                return (sum(es) / len(es), max(es),
                        sum(1 for e in es if e >= ENT_HI) / len(es))

            stats["region_ent_stats"] = region_ent_stats
            # high-entropy byte attribution
            hi_total = sum(b - a for a, b in runs)
            std_regs = [(b["region_start"], b["region_end"]) for b in blocks
                        if b["name"] == "CATStdCont"]
            cgm_regs = [(b["region_start"], b["region_end"]) for b in blocks
                        if b["name"] == "CGMGeom"]

            def hi_in(spans):
                """spans: (start, end) pairs; sum of run bytes covered."""
                tot = 0
                for a, bnd in runs:
                    for lo, hi2 in spans:
                        s, e = max(lo, a), min(hi2, bnd)
                        if s < e:
                            tot += e - s
                return tot
            stats["hi_total"] = hi_total
            stats["hi_in_stdcont"] = hi_in(std_regs)
            stats["hi_in_cgmgeom"] = hi_in(cgm_regs)
            stats["hi_in_tail_named"] = hi_in(
                [(X, X + Y) for X, Y, _ in regs])
        mm.close()
    return stats


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--deep-sha16", default=",".join(DEEP16_DEFAULT))
    ap.add_argument("--validate-sample", type=int, default=2)
    ap.add_argument("--include-sha16", default="")
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [r for r in csv.DictReader(MANIFEST.open()) if r["magic_ok"] == "yes"]
    by16 = defaultdict(list)
    for r in rows:
        by16[r["sha256"][:16]].append(r)

    deep16 = [h for h in args.deep_sha16.split(",") if h]
    inc16 = [h for h in args.include_sha16.split(",") if h]
    val = sample_by_version(rows, args.validate_sample)
    val = [r for r in val if r["sha256"][:16] not in deep16]
    for h in inc16:
        val.extend(by16.get(h, []))
    # validation sample = stratified picks + includes; deep files are
    # scanned once (in the deep pass) so rates are not double-counted.
    val_seen = set()
    val_rows = []
    for r in val:
        if r["sha256"] not in val_seen and r["sha256"][:16] not in deep16:
            val_seen.add(r["sha256"])
            val_rows.append(r)

    deep_rows = []
    for h in deep16:
        deep_rows.extend(by16.get(h, []))

    f_fh = (out_dir / "geometry-payloads-files.csv").open("w", newline="")
    fw = csv.DictWriter(f_fh, fieldnames=FILE_FIELDS)
    fw.writeheader()
    r_fh = (out_dir / "geometry-payloads-regions.csv").open("w", newline="")
    rw = csv.DictWriter(r_fh, fieldnames=REGION_FIELDS)
    rw.writeheader()
    z_fh = (out_dir / "geometry-payloads-zones.csv").open("w", newline="")
    zw = csv.DictWriter(z_fh, fieldnames=ZONE_FIELDS)
    zw.writeheader()
    b_fh = (out_dir / "geometry-payloads-blocks.csv").open("w", newline="")
    bw = csv.DictWriter(b_fh, fieldnames=BLOCK_FIELDS)
    bw.writeheader()
    s_fh = (out_dir / "geometry-payloads-sigscan.csv").open("w", newline="")
    sw = csv.DictWriter(s_fh, fieldnames=SIG_FIELDS)
    sw.writeheader()

    tallies = defaultdict(lambda: [0, 0])

    def tally(claim, passed, rel=None):
        tallies[claim][0] += 1
        tallies[claim][1] += int(bool(passed))

    def emit(r, st, deep):
        frow = {
            "sha256": r["sha256"], "size_bytes": r["size_bytes"],
            "repo": r["repo"], "detected_version": r["detected_version"],
            "release": release_of(r["detected_version"]), "kind": r["kind"],
            "sample": "deep" if deep else "validate",
            "dword8": st["d8"], "dword12": st["d12"],
            "n_blocks": len(st["blocks"]),
            "block_names": ";".join(
                "%s:%d" % (k, v) for k, v in
                sorted(Counter(b["name"] or "<noname>" for b in st["blocks"]).items())),
            "n_parts_like": st["n_parts_like"],
            "cgmgeom_region_max": st["cgmgeom_region_max"],
            "cgrcont_region_max": st["cgrcont_region_max"],
            "stdcont_region_max": st["stdcont_region_max"],
            "stdcont_nested": st["stdcont_nested"],
            "seebody_nested": st["seebody_nested"],
            "stream_tokens_any_region": st["stream_tokens_any_region"],
            "surfacicreps_files_token": st["surfacicreps"],
            "scenegraph_files_token": st["scenegraph"],
            "strip_markers": st["strip_markers"],
            "strip_verified": st["strip_verified"],
            "strip_chained": st["strip_chained"],
            "strip_in_stdcont": st["strip_in_stdcont"],
            "strip_in_cgmgeom": st["strip_in_cgmgeom"],
            "strip_bytes_est": st["strip_bytes_est"],
            "tag20_hits": st["tag20_hits"], "tag2x0_hits": st["tag2x0_hits"],
            "catcgm_hits": st["catcgm_hits"],
            "osmx_count": st["osmx_count"], "cb0001_count": st["cb0001_count"],
            "jpeg_count": st["jpeg_count"],
            "tail_entries_primary": st.get("tail_entries_primary", ""),
            "tail_entries_resync": st.get("tail_entries_resync", ""),
            "tail_resync_gaps": st.get("tail_resync_gaps", ""),
        }
        if deep:
            frow.update({
                "ent_share_hi": "%.4f" % st["ent_share_hi"],
                "ent_mean": "%.3f" % st["ent_mean"],
                "hi_bytes_total": st["hi_total"],
                "hi_bytes_in_stdcont": st["hi_in_stdcont"],
                "hi_bytes_in_cgmgeom": st["hi_in_cgmgeom"],
                "hi_bytes_in_tail_named": st["hi_in_tail_named"],
            })
        else:
            for k in ("ent_share_hi", "ent_mean", "hi_bytes_total",
                      "hi_bytes_in_stdcont", "hi_bytes_in_cgmgeom",
                      "hi_bytes_in_tail_named"):
                frow[k] = ""
        fw.writerow(frow)
        for sig, val in (("strip_markers", st["strip_markers"]),
                         ("strip_verified", st["strip_verified"]),
                         ("strip_in_stdcont", st["strip_in_stdcont"]),
                         ("strip_in_cgmgeom", st["strip_in_cgmgeom"]),
                         ("tag20", st["tag20_hits"]),
                         ("tag2x0", st["tag2x0_hits"]),
                         ("CATCGM", st["catcgm_hits"]),
                         ("surfacicreps_token", st["surfacicreps"]),
                         ("scenegraph_token", st["scenegraph"]),
                         ("nested_v5cfv2", int(st["stdcont_nested"] > 0 or
                                               st["seebody_nested"] > 0))):
            sw.writerow({"sha256": r["sha256"],
                         "detected_version": r["detected_version"],
                         "release": release_of(r["detected_version"]),
                         "kind": r["kind"], "size_bytes": r["size_bytes"],
                         "sig": sig, "count": val})

    for r in deep_rows:
        st = scan_file(ROOT / r["local_path"], deep=True)
        emit(r, st, deep=True)
        size = int(r["size_bytes"])
        reg_stats = st["region_ent_stats"]
        # regions CSV
        for k, e in enumerate(st["tail_entries"]):
            lo, hi2 = e["X"], min(e["X"] + e["Y"], size)
            mean, mx, hish = reg_stats(lo, hi2)
            rw.writerow({
                "sha256": r["sha256"], "size_bytes": size,
                "detected_version": r["detected_version"],
                "entry_ordinal": k, "seq": e["seq"], "space": e["sp"],
                "name_kind": e["kind"], "name": e["name"][:64],
                "X": e["X"], "Y": e["Y"], "walk_part": e["walk_part"],
                "reg_ent_mean": "%.3f" % mean,
                "reg_ent_max": "%.3f" % mx,
                "reg_hi_share": "%.3f" % hish,
            })
        # zones CSV
        regs = st["tail_regs"]
        blocks = st["blocks"]
        for zi, (a, b) in enumerate(st["runs"]):
            names, cov = overlap_names(regs, a, b)
            bstart = max((bl["start"] for bl in blocks if bl["start"] <= a),
                         default=None)
            bname = next((bl["name"] for bl in blocks
                          if bl["start"] == bstart), "")
            nested = next((bl.get("nested_v5cfv2", False) for bl in blocks
                           if bl["name"] in ("CATStdCont", "CATSeeBodyCont")
                           and bl["region_start"] <= a < bl["region_end"]), False)
            mean, _, _ = reg_stats(a, b)
            zw.writerow({
                "sha256": r["sha256"], "size_bytes": size,
                "detected_version": r["detected_version"],
                "zone_ordinal": zi, "zone_start": a, "zone_end": b,
                "zone_bytes": b - a,
                "zone_ent_mean": "%.3f" % mean,
                "tail_owner_names": ";".join(names[:6]),
                "tail_owner_cover": cov,
                "block_owner": bname,
                "nested_store": bool(nested),
            })
        # blocks CSV
        for bl in st["blocks"]:
            if bl["region_end"] <= bl["region_start"]:
                continue
            lo, hi2 = bl["region_start"], bl["region_end"]
            mean, _, hish = reg_stats(lo, hi2)
            bw.writerow({
                "sha256": r["sha256"], "size_bytes": size,
                "detected_version": r["detected_version"],
                "block_ordinal": bl["ordinal"], "block_start": bl["start"],
                "block_name": bl["name"], "region_start": lo,
                "region_end": hi2, "region_size": hi2 - lo,
                "boundary_kind": bl["boundary"],
                "nested_v5cfv2": bl.get("nested_v5cfv2", ""),
                "nested_d8": bl.get("nested_d8", ""),
                "nested_d12": bl.get("nested_d12", ""),
                "nested_tail_magic": bl.get("nested_tail_magic", ""),
                "nested_entries": bl.get("nested_entries", ""),
                "nested_names": (bl.get("nested_names") or "")[:200],
                "reg_ent_mean": "%.3f" % mean,
                "reg_hi_share": "%.3f" % hish,
            })

    for r in val_rows:
        st = scan_file(ROOT / r["local_path"], deep=False)
        emit(r, st, deep=False)

    for fh in (f_fh, r_fh, z_fh, b_fh, s_fh):
        fh.close()
    # claim tallies (recomputed from the emitted CSVs)
    fw2 = list(csv.DictReader((out_dir / "geometry-payloads-files.csv").open()))
    for row in fw2:
        kind = row["kind"]
        rel = row["release"]
        if kind == "part":
            tally("V1_one_cgmgeom_per_part", "CGMGeom:1" in row["block_names"], rel)
            tally("V2_cgrcont_small",
                  int(row["cgrcont_region_max"] or 0) < 65536, rel)
            tally("V3_stdcont_nested", int(row["stdcont_nested"] or 0) > 0, rel)
            tally("V4_surfacicreps", row["surfacicreps_files_token"] == "1", rel)
            tally("V5_strip_in_stdcont", int(row["strip_in_stdcont"] or 0) > 0, rel)
            tally("V6_strip_in_cgmgeom", int(row["strip_in_cgmgeom"] or 0) > 0, rel)
            tally("V7_tag2x0_in_parts",
                  (int(row["tag20_hits"] or 0) + int(row["tag2x0_hits"] or 0)) > 0, rel)
        elif kind == "product":
            tally("V1_one_cgmgeom_per_part",
                  "CGMGeom:1" not in row["block_names"], rel)

    # V8: the CGMGeom block region is named by a tail catalog region
    # (deep sample only): |X - block_start| < 400 and the tail region
    # ends within 400 B before the block region's end.
    blocks = list(csv.DictReader((out_dir / "geometry-payloads-blocks.csv").open()))
    regs = list(csv.DictReader((out_dir / "geometry-payloads-regions.csv").open()))
    rel_by_sha = {r["sha256"]: r["release"] for r in fw2}
    for b in blocks:
        if b["block_name"] != "CGMGeom":
            continue
        bs, re_ = int(b["block_start"]), int(b["region_end"])
        hit = any(t["sha256"] == b["sha256"] and
                  abs(int(t["X"]) - bs) < 400 and
                  0 < re_ - (int(t["X"]) + int(t["Y"])) <= 400
                  for t in regs)
        tally("V8_cgm_region_in_catalog", hit, rel_by_sha.get(b["sha256"], ""))

    # per-release claims CSV
    tallies_rel = defaultdict(lambda: defaultdict(lambda: [0, 0]))

    def tally_rel(claim, passed, rel):
        tallies_rel[claim][rel][0] += 1
        tallies_rel[claim][rel][1] += int(bool(passed))

    # recompute per release from the same rows
    for row in fw2:
        kind, rel = row["kind"], row["release"]
        if kind == "part":
            tally_rel("V1_one_cgmgeom_per_part", "CGMGeom:1" in row["block_names"], rel)
            tally_rel("V2_cgrcont_small", int(row["cgrcont_region_max"] or 0) < 65536, rel)
            tally_rel("V3_stdcont_nested", int(row["stdcont_nested"] or 0) > 0, rel)
            tally_rel("V4_surfacicreps", row["surfacicreps_files_token"] == "1", rel)
            tally_rel("V5_strip_in_stdcont", int(row["strip_in_stdcont"] or 0) > 0, rel)
            tally_rel("V6_strip_in_cgmgeom", int(row["strip_in_cgmgeom"] or 0) > 0, rel)
            tally_rel("V7_tag2x0_in_parts",
                      (int(row["tag20_hits"] or 0) + int(row["tag2x0_hits"] or 0)) > 0, rel)
        elif kind == "product":
            tally_rel("V1_one_cgmgeom_per_part",
                      "CGMGeom:1" not in row["block_names"], rel)
    for b in blocks:
        if b["block_name"] != "CGMGeom":
            continue
        bs, re_ = int(b["block_start"]), int(b["region_end"])
        hit = any(t["sha256"] == b["sha256"] and
                  abs(int(t["X"]) - bs) < 400 and
                  0 < re_ - (int(t["X"]) + int(t["Y"])) <= 400
                  for t in regs)
        tally_rel("V8_cgm_region_in_catalog", hit, rel_by_sha.get(b["sha256"], ""))

    with (out_dir / "geometry-payloads-claims.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["claim", "release", "observations", "passes", "rate"])
        for c in sorted(tallies_rel):
            for rel in sorted(tallies_rel[c]):
                obs, ok = tallies_rel[c][rel]
                w.writerow([c, rel, obs, ok, "%.3f" % (ok / obs if obs else 0)])

    print("== geometry payload scan ==")
    print("deep files: %d, validation files: %d" % (len(deep_rows), len(val_rows)))
    for c, (obs, ok) in sorted(tallies.items()):
        print("  %-28s %5d/%5d = %.3f" % (c, ok, obs, ok / obs if obs else 0))
    print("wrote CSVs under", out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
