#!/usr/bin/env python3
"""Decode the nested V5_CFV2 stream store corpus-wide (G1, ticket #29).

Builds on B4's nested-store discovery (decode_geometry_payloads.py: the
nested `V5_CFV2\\0` header inside the CATStdCont block region) and tests
B1/B2's container/trailer laws one level down.  Static reads only; no
structure is parsed by the package.

Model (all claims labeled in the evidence note
docs/evidence/2026-11-09-nested-store.md):

  Store origin.  A CATStdCont block region embeds a nested stream store.
  Two variants:
    - header variant: a 32-byte header
          [0:8]   magic "V5_CFV2\\0"        (same bytes as the file header)
          [8:12]  dword8, big-endian        offset of the nested catalog
          [12:16] dword12, big-endian       nested catalog tail length
          [16:24] ff x 8                    (generation marker, as the outer)
          [24:32] zeros x 8
      at the store origin (first magic in the block region; typically
      block + ~250-264, the block's property preamble);
    - header-less variant (R19 family): no V5_CFV2 header; the store
      origin is the CATStdCont block start itself and the catalog sits
      directly in the region (found as CB0001; the region carries the
      SurfacicReps token and the catalog walk validates with CB__END).
  A CB0001 magic inside the region that does NOT validate as a store
  catalog is an embedded document's own outer-style catalog (B1's
  distributed family), not a stream store.

  Catalog (one level down) = the outer tail model (B2) exactly:
    magic "CATIA_V5 CB0001\\0" + 20-byte tail header (tag 4e, 1000, 64,
    12, cntA, cntB = cntA+1, var8) + 28 zeros + entry 0 (M-law:
    e0_len == M + 87) + records (hdr84 + xrec13 + fil87 + UTF-16 name)
    + trailer (last 36 bytes, CB__END\\0).  The primary walk stops when
    a record is followed by something that is not another hdr84-record
    (B2's known name-stop limitation); B4's resync continuation applies.
  Nested deltas from the outer: entry-0 X0 = 132 (outer 94); trailer
  A = 0 on a minority of stores; the trailer's region does NOT start
  with a writer registration block (the outer's always does).

  Region model.  Catalog entry X/Y are relative to the store origin:
  header stores satisfy max(region end) == dword8 exactly; header-less
  stores tile [64, catalog) with min(region start) == 64.  The catalog
  names the stream regions: a SurfacicReps payload region plus small
  MAIN/Describe/MainDataStream/Header/SceneGraph records (9-132 B)
  tiling the end of the store body.

  Container extent.  The store ends at catalog_start + tail length and
  the next storage block starts exactly 126 bytes later - the same
  ~126 B inter-block tail the outer V8 delta law shows; those bytes
  carry the writer registration block (41 B) followed by zeros.

  Probe discipline.  The nested probe is bounded by the block REGION
  (next valid storage block / outer dword8 / EOF), not a fixed window:
  B4's 0x400 window catches the next block's own store when CATStdCont's
  region is short (the CATXDocLinkCont store family).  CB0001 and OSMX
  are dropped from the B3 boundary candidates here because both occur
  legitimately inside a store region.

Read-only; run with:  python3 -I scripts/triage/decode_nested_store.py
  [--max-per-release N]        cap the per-release sample (0 = all dev
                               parts; the default scans all of them)
  [--include-sha16 HEX16,...]  restrict to these files (sha16 prefixes)
  [--out-dir DIR]              output directory (default
                               docs/evidence/data)

Outputs (docs/evidence/data/):
  nested-store-files.csv     one row per scanned part
  nested-store-regions.csv   one row per decoded store (model laws)
  nested-store-streams.csv   one row per named stream region
  nested-store-claims.csv    per-claim, per-release rates
and a claim-rate summary on stdout.  Deterministic: file order is the
sorted manifest order and no wall-clock value enters the CSVs.
"""
import argparse
import csv
import mmap
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"

sys.path.insert(0, str(ROOT / "scripts" / "triage"))
from decode_tail_region import scan_tail, release_of, REG_RE  # noqa: E402
from decode_geometry_payloads import resync_walk  # noqa: E402
from decode_container_payloads import block_name  # noqa: E402

V5_CFV2 = b"V5_CFV2\x00"
CB0001 = b"CATIA_V5 CB0001\x00"
CB_END = b"CB__END\x00"
BLOCK_TAG = b"\x34\x12"
STORAGE_WORD = b"CATStorageProperty"
STREAM_NAMES = ("SurfacicReps", "SceneGraph", "MainDataStream",
                "Describe", "Header", "MAIN")
TAIL126 = 126
HEADER_LEN = 32
HDRLESS_BODY = 64          # header-less store body starts at origin + 64
STRIP_RE = re.compile(rb"\x01[\x41-\x4f].\xff", re.DOTALL)

FILE_FIELDS = [
    "sha256", "size_bytes", "repo", "detected_version", "release",
    "n_blocks_valid", "n_stdcont", "store_class", "n_stores",
    "store_origin_abs", "origin_kind", "dword8", "dword12", "d8_overshoot_k",
    "catalog_start_abs", "tail_len", "container_end_abs",
    "next_block_name", "next_block_abs", "delta_to_next", "reg_at_end",
    "cntA", "cntB", "M", "e0_X0", "e0_len_law", "walk_ok", "walk_break",
    "n_entries_primary", "n_entries_resync", "accounting_ok",
    "trailer_A", "trailer_B", "trailer_C", "trailer_D", "trailer_E",
    "trailer_F", "trailer_G", "C_eq_D", "G_eq_len", "ends_cbend",
    "r2_max_end_eq_d8", "region_min", "region_max_end",
    "stream_names", "surfacicreps_in_catalog", "surfacicreps_entry_parsed",
    "body_size", "strip_verified_body", "seebody_store", "xdoclink_store",
]
STORE_FIELDS = [
    "sha256", "release", "store_ordinal", "block_start", "origin_abs",
    "origin_kind", "dword8", "dword12", "d8_overshoot_k", "catalog_start",
    "tail_len", "container_end", "next_block_name", "next_block_abs",
    "delta_to_next", "reg_at_end", "header_ff8_zeros8", "cntA", "cntB",
    "M", "e0_X0", "e0_len_law", "walk_ok", "walk_break",
    "n_entries_primary", "n_entries_resync", "accounting_ok",
        "trailer_A", "trailer_B", "trailer_C", "trailer_D", "trailer_E",
        "trailer_F", "trailer_G", "C_eq_D", "G_eq_len", "ends_cbend",
        "cbend_within_tail", "tail_padded",
        "reg_in_trailer_region", "r2_max_end_eq_d8", "region_min",
    "region_max_end", "stream_names", "surfacicreps_in_catalog",
    "surfacicreps_entry_parsed", "sp1_all_y80_200", "seq_from_2",
    "body_size", "strip_verified_body",
]
STREAM_FIELDS = [
    "sha256", "release", "store_ordinal", "origin_kind", "walk_part",
    "seq", "sp", "name", "X", "Y", "abs_start", "abs_end",
]


def find_all(mm, needle, start=0, end=None):
    out = []
    if end is None:
        end = mm.size()
    i = mm.find(needle, start, end)
    while i >= 0:
        out.append(i)
        i = mm.find(needle, i + 1, end)
    return out


def valid_blocks(mm):
    """(start, name) of every storage block whose name field parses."""
    out = []
    for o in find_all(mm, STORAGE_WORD):
        blk = o - 2 if mm[o - 2:o] == BLOCK_TAG else o
        nm, ok = block_name(mm, blk)
        if ok:
            out.append((blk, nm))
    return out


def strip_verified(mm, lo, hi):
    """Verified `01 4X <type> ff [u32le n][n x u16be]` records in [lo, hi)."""
    n = 0
    size = mm.size()
    hi = min(hi, size)
    if lo >= hi:
        return 0
    for m in STRIP_RE.finditer(mm, lo, hi):
        o = m.start()
        cnt = int.from_bytes(mm[o + 4:o + 8], "little")
        if 1 <= cnt <= 1000000 and o + 8 + 2 * cnt <= size:
            n += 1
    return n


def probe_region(mm, blk, blocks, d8_outer):
    """Next valid block after blk and the region end (B3 boundary rule
    minus CB0001/OSMX; both occur legitimately inside a store region)."""
    nxt, nxt_name = next(((b, nm) for b, nm in blocks if b > blk),
                         (None, ""))
    ends = [(mm.size(), "EOF")]
    if nxt is not None:
        ends.append((nxt, "nxtblk"))
    if d8_outer > blk:
        ends.append((d8_outer, "dword8"))
    rend, rkind = min(ends)
    return nxt, nxt_name, rend, rkind


def probe_owner_store(mm, blk, blocks, d8_outer):
    """True when blk's own region carries a V5_CFV2 store header."""
    _, _, rend, _ = probe_region(mm, blk, blocks, d8_outer)
    return mm.find(V5_CFV2, blk, rend) >= 0


def region_row(rel, ordinal, origin_kind, walk_part, seq, sp, name,
               X, Y, origin):
    return {
        "sha256": rel["sha256"],
        "release": release_of(rel["detected_version"]),
        "store_ordinal": ordinal, "origin_kind": origin_kind,
        "walk_part": walk_part, "seq": seq, "sp": sp, "name": name,
        "X": X, "Y": Y, "abs_start": origin + X, "abs_end": origin + X + Y,
    }


def analyze_region(mm, blk, blocks, d8_outer, rel, ordinal):
    """Decode one CATStdCont block region.

    Returns (class, store_row_or_None, stream_rows).
    """
    size = mm.size()
    nxt, nxt_name, rend, _ = probe_region(mm, blk, blocks, d8_outer)

    # ---- header variant
    j = mm.find(V5_CFV2, blk, rend)
    if j >= 0:
        nh = bytes(mm[j:j + HEADER_LEN])
        ff8 = len(nh) == HEADER_LEN and nh[16:24] == b"\xff" * 8
        zeros8 = len(nh) == HEADER_LEN and nh[24:32] == b"\x00" * 8
        d8n = int.from_bytes(nh[8:12], "big") if len(nh) == HEADER_LEN else 0
        d12n = int.from_bytes(nh[12:16], "big") if len(nh) == HEADER_LEN else 0
        sane = 0 < d8n and 0 < d12n and j + d8n + d12n <= size
        cb = -1
        k = 0
        if sane and bytes(mm[j + d8n:j + d8n + 16]) == CB0001:
            cb = j + d8n
        elif sane:
            cand = mm.find(CB0001, j, min(rend, j + d8n + d12n + 512))
            if cand >= 0 and 1 <= (j + d8n - cand) <= 64:
                cb = cand
                k = j + d8n - cand
        if not (ff8 and zeros8) or cb < 0:
            return "header_invalid", None, []
        return finish_store(mm, blk, nxt, nxt_name, rel, ordinal,
                            origin=j, origin_kind="v5header", d8n=d8n,
                            d12n=d12n, k=k, cb=cb, tail_len=d12n,
                            ff8=ff8, zeros8=zeros8)

    # ---- header-less variant / embedded document
    cb = mm.find(CB0001, blk, rend)
    if cb < 0:
        return "none_in_region", None, []
    tail_len = rend - TAIL126 - cb
    ok = tail_len > 100 and validate_catalog(mm, cb, tail_len)
    if not ok:
        tail_len2 = rend - cb
        if tail_len2 > 100 and validate_catalog(mm, cb, tail_len2):
            tail_len = tail_len2
            ok = True
    if not ok:
        return "embedded_doc", None, []
    return finish_store(mm, blk, nxt, nxt_name, rel, ordinal,
                        origin=blk, origin_kind="block", d8n="", d12n="",
                        k="", cb=cb, tail_len=tail_len, ff8="", zeros8="")


def validate_catalog(mm, cb, tail_len):
    """A store catalog must parse and end with its own CB__END trailer."""
    s = scan_tail(bytes(mm[cb:cb + tail_len]), 0)
    return bool(s["magic"] and s["ends_cbend"] and s.get("G_eq_taillen"))


def finish_store(mm, blk, nxt, nxt_name, rel, ordinal, origin, origin_kind,
                 d8n, d12n, k, cb, tail_len, ff8, zeros8):
    """Shared store analysis once origin/catalog/length are known."""
    tail_start = cb
    container_end = tail_start + tail_len
    tail = bytes(mm[tail_start:container_end])
    s = scan_tail(tail, 0)
    ents = list(s["entries"])
    for e in ents:
        e["walk_part"] = "primary"
    n_resync = 0
    if not s["walk_ok"] and s["break"] and "@" in s["break"]:
        pos = int(s["break"].split("@")[1])
        new, _, _ = resync_walk(tail, pos)
        for e in new:
            e["walk_part"] = "resync"
        ents.extend(new)
        n_resync = len(new)

    # trailer fields (E/F are not extracted by scan_tail)
    tb = tail[-36:]
    A = int.from_bytes(tb[0:4], "big")
    B = int.from_bytes(tb[4:8], "big")
    C = int.from_bytes(tb[8:12], "big")
    D = int.from_bytes(tb[12:16], "big")
    E = int.from_bytes(tb[16:20], "big")
    F = int.from_bytes(tb[20:24], "big")
    G = int.from_bytes(tb[24:28], "big")

    regs = [(e["X"], e["Y"]) for e in ents]
    if s["ends_cbend"]:
        regs.append((B, C))
    region_min = min(regs)[0] if regs else ""
    region_max_end = max(x + y for x, y in regs) if regs else ""
    r2 = (region_max_end == d8n) if origin_kind == "v5header" else ""

    names = []
    for e in ents:
        if e["name"] not in names:
            names.append(e["name"])
    surf_entry = any(e["name"] == "SurfacicReps" for e in ents)
    surf_text = surf_entry or \
        mm.find("SurfacicReps".encode("utf-16-le"), tail_start, container_end) >= 0
    sp1 = [e for e in ents if e["sp"] == 1]
    sp_law = all(80 <= e["Y"] <= 200 for e in sp1) if sp1 else ""
    seq_ok = all(e["seq"] == i + 2 for i, e in enumerate(s["entries"]))

    body_start = origin + (HEADER_LEN if origin_kind == "v5header"
                           else HDRLESS_BODY)
    body_size = tail_start - body_start
    strips = strip_verified(mm, body_start, tail_start)
    size = mm.size()
    delta = (nxt - container_end) if nxt is not None else size - container_end
    reg_end = bool(REG_RE.match(mm, container_end)) \
        if container_end + 41 <= size else False
    reg_trailer = bool(REG_RE.match(mm, origin + B)) \
        if s["ends_cbend"] and 0 <= origin + B < size else False

    row = {
        "sha256": rel["sha256"],
        "release": release_of(rel["detected_version"]),
        "store_ordinal": ordinal, "block_start": blk,
        "origin_abs": origin, "origin_kind": origin_kind,
        "dword8": d8n, "dword12": d12n, "d8_overshoot_k": k,
        "catalog_start": tail_start, "tail_len": tail_len,
        "container_end": container_end,
        "next_block_name": nxt_name,
        "next_block_abs": nxt if nxt is not None else "",
        "delta_to_next": delta, "reg_at_end": reg_end,
        "header_ff8_zeros8": (ff8 and zeros8) if origin_kind == "v5header" else "",
        "cntA": s.get("cntA", ""), "cntB": s.get("cntB", ""),
        "M": s.get("M", ""), "e0_X0": s.get("e0_X0", ""),
        "e0_len_law": s.get("e0_len_law", ""),
        "walk_ok": s["walk_ok"], "walk_break": s["break"],
        "n_entries_primary": len(s["entries"]), "n_entries_resync": n_resync,
        "accounting_ok": s.get("accounting_ok", ""),
        "trailer_A": A, "trailer_B": B, "trailer_C": C, "trailer_D": D,
        "trailer_E": E, "trailer_F": F, "trailer_G": G,
        "C_eq_D": C == D, "G_eq_len": G == tail_len,
        "ends_cbend": s["ends_cbend"],
        "cbend_within_tail": tail.find(CB_END) >= 0,
        "tail_padded": (not s["ends_cbend"]) and tail.find(CB_END) >= 0,
        "reg_in_trailer_region": reg_trailer,
        "r2_max_end_eq_d8": r2, "region_min": region_min,
        "region_max_end": region_max_end,
        "stream_names": ";".join(names),
        "surfacicreps_in_catalog": surf_text,
        "surfacicreps_entry_parsed": surf_entry,
        "sp1_all_y80_200": sp_law, "seq_from_2": seq_ok,
        "body_size": body_size, "strip_verified_body": strips,
    }
    streams = []
    for e in ents:
        streams.append(region_row(rel, ordinal, origin_kind,
                                  e["walk_part"], e["seq"], e["sp"],
                                  e["name"], e["X"], e["Y"], origin))
    if s["ends_cbend"]:
        streams.append(region_row(rel, ordinal, origin_kind, "trailer",
                                  "", "", "<trailer>", B, C, origin))
    cls = "header" if origin_kind == "v5header" else "headerless"
    return cls, row, streams


def scan_file(path, rel):
    """One part: blocks, store classes, store decodes.

    Returns (file_row, store_rows, stream_rows).
    """
    with path.open("rb") as fh:
        mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        size = mm.size()
        d8_outer = int.from_bytes(mm[8:12], "big") if size >= 12 else 0
        blocks = valid_blocks(mm)
        stdcont = [b for b, nm in blocks if nm == "CATStdCont"]
        store_rows = []
        stream_rows = []
        classes = []
        for ordinal, blk in enumerate(stdcont):
            cls, srow, srows = analyze_region(mm, blk, blocks, d8_outer,
                                              rel, ordinal)
            classes.append(cls)
            if srow is not None:
                store_rows.append(srow)
                stream_rows.append(srows)
        seebody = next((b for b, nm in blocks if nm == "CATSeeBodyCont"), None)
        seebody_store = seebody is not None and \
            probe_owner_store(mm, seebody, blocks, d8_outer)
        xdoc = next((b for b, nm in blocks if nm == "CATXDocLinkCont"), None)
        xdoc_store = xdoc is not None and \
            probe_owner_store(mm, xdoc, blocks, d8_outer)
        mm.close()

    frow = {
        "sha256": rel["sha256"], "size_bytes": size, "repo": rel["repo"],
        "detected_version": rel["detected_version"],
        "release": release_of(rel["detected_version"]),
        "n_blocks_valid": len(blocks), "n_stdcont": len(stdcont),
        "n_stores": len(store_rows),
        "seebody_store": seebody_store, "xdoclink_store": xdoc_store,
    }
    if not stdcont:
        frow["store_class"] = "no_stdcont"
    else:
        frow["store_class"] = classes[0]
        if classes[0] == "none_in_region" and xdoc_store and \
                xdoc == next((b for b, _ in blocks if b > stdcont[0]), None):
            frow["store_class"] = "next_block_store"
    if store_rows:
        s0 = store_rows[0]
        for k in STORE_FIELDS:
            if k in ("sha256", "release", "store_ordinal", "block_start"):
                continue
            frow[k] = s0[k]
        frow["catalog_start_abs"] = s0["catalog_start"]
        frow["container_end_abs"] = s0["container_end"]
        frow["store_origin_abs"] = s0["origin_abs"]
    return frow, store_rows, stream_rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-per-release", type=int, default=0)
    ap.add_argument("--include-sha16", default="")
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [r for r in csv.DictReader(MANIFEST.open())
            if r["magic_ok"] == "yes" and r["split"] == "dev"
            and r["kind"] == "part"]
    if args.include_sha16:
        want = {h for h in args.include_sha16.split(",") if h}
        rows = [r for r in rows if r["sha256"][:16] in want]
        if not rows:
            print("error: no manifest row matches --include-sha16 %s"
                  % args.include_sha16, file=sys.stderr)
            return 2
    if args.max_per_release > 0:
        byrel = defaultdict(list)
        for r in rows:
            byrel[release_of(r["detected_version"])].append(r)
        picked = []
        for rel in sorted(byrel):
            picked.extend(byrel[rel][:args.max_per_release])
        rows = picked
    rows.sort(key=lambda r: r["sha256"])

    f_fh = (out_dir / "nested-store-files.csv").open("w", newline="")
    fw = csv.DictWriter(f_fh, fieldnames=FILE_FIELDS)
    fw.writeheader()
    s_fh = (out_dir / "nested-store-regions.csv").open("w", newline="")
    sw = csv.DictWriter(s_fh, fieldnames=STORE_FIELDS)
    sw.writeheader()
    t_fh = (out_dir / "nested-store-streams.csv").open("w", newline="")
    tw = csv.DictWriter(t_fh, fieldnames=STREAM_FIELDS)
    tw.writeheader()

    for r in rows:
        frow, store_rows, stream_rows = scan_file(ROOT / r["local_path"], r)
        for srow in store_rows:
            sw.writerow({k: srow.get(k, "") for k in STORE_FIELDS})
        for srows in stream_rows:
            for trow in srows:
                tw.writerow({k: trow.get(k, "") for k in STREAM_FIELDS})
        fw.writerow({k: frow.get(k, "") for k in FILE_FIELDS})

    for fh in (f_fh, s_fh, t_fh):
        fh.close()

    tally_claims(out_dir)
    return 0


def tally_claims(out_dir):
    """Per-claim, per-release rates recomputed from the emitted CSVs."""
    files = list(csv.DictReader((out_dir / "nested-store-files.csv").open()))
    stores = list(csv.DictReader((out_dir / "nested-store-regions.csv").open()))
    tallies = defaultdict(lambda: defaultdict(lambda: [0, 0]))

    def tally(claim, rel, passed):
        tallies[claim][rel][0] += 1
        tallies[claim][rel][1] += int(bool(passed))

    def tf(v):
        return v == "True"

    for f in files:
        rel = f["release"]
        cls = f["store_class"]
        tally("N1_store_present", rel, cls in ("header", "headerless"))
        tally("N10_seebody_store", rel, tf(f["seebody_store"]))
        if cls != "no_stdcont":
            tally("N1h_header_variant", rel, cls == "header")
            tally("N1l_headerless_variant", rel, cls == "headerless")
            tally("N10_embedded_doc_catalog", rel, cls == "embedded_doc")
            tally("N10_no_store_in_region", rel,
                  cls in ("none_in_region", "next_block_store"))
            tally("N10_store_on_next_xdoclink", rel,
                  cls == "next_block_store")

    for s in stores:
        rel = s["release"]
        is_hdr = s["origin_kind"] == "v5header"
        if is_hdr:
            tally("N2_header_fields", rel, tf(s["header_ff8_zeros8"]))
            tally("N3_tail_magic_at_d8", rel, s["d8_overshoot_k"] == "0")
            tally("N3v_d8_overshoot", rel,
                  s["d8_overshoot_k"] not in ("", "0"))
            tally("N5_r2_max_end_eq_d8", rel, tf(s["r2_max_end_eq_d8"]))
        else:
            tally("N5_min64_headerless", rel,
                  s["region_min"] != "" and
                  int(s["region_min"]) == HDRLESS_BODY)
        tally("N4_e0_len_law", rel, tf(s["e0_len_law"]))
        tally("N4_cntB_eq_cntA_plus1", rel,
              s["cntB"] != "" and int(s["cntB"]) == int(s["cntA"]) + 1)
        tally("N4_seq_from_2", rel, tf(s["seq_from_2"]))
        tally("N4_x0_132", rel, s["e0_X0"] != "" and int(s["e0_X0"]) == 132)
        tally("N6_cbend", rel, tf(s["ends_cbend"]))
        tally("N6b_cbend_within_tail", rel, tf(s["cbend_within_tail"]))
        if tf(s["walk_ok"]) and tf(s["ends_cbend"]):
            # accounting is defined only where the walk ends cleanly
            tally("N4_accounting", rel, tf(s["accounting_ok"]))
        if tf(s["ends_cbend"]):
            tally("N6_C_eq_D", rel, tf(s["C_eq_D"]))
            tally("N6_G_eq_tail_len", rel, tf(s["G_eq_len"]))
            tally("N6_A_eq_1", rel, int(s["trailer_A"]) == 1)
            tally("N6_A_eq_0", rel, int(s["trailer_A"]) == 0)
            tally("N6_no_reg_in_trailer_region", rel,
                  not tf(s["reg_in_trailer_region"]))
        tally("N9_reg_at_container_end", rel, tf(s["reg_at_end"]))
        tally("N9_delta126_exact", rel, s["delta_to_next"] != "" and
              int(s["delta_to_next"]) == TAIL126)
        tally("N9_delta_1_200", rel, s["delta_to_next"] != "" and
              1 <= int(s["delta_to_next"]) <= 200)
        tally("N7_names_vocabulary", rel,
              all(nm in STREAM_NAMES
                  for nm in filter(None, s["stream_names"].split(";"))))
        tally("N7_surfacicreps_in_catalog", rel,
              tf(s["surfacicreps_in_catalog"]))
        if s["sp1_all_y80_200"] != "":
            tally("N7_sp1_y80_200", rel, tf(s["sp1_all_y80_200"]))
        tally("N8_strip_in_body", rel, int(s["strip_verified_body"]) > 0)

    with (out_dir / "nested-store-claims.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["claim", "release", "observations", "passes", "rate"])
        for c in sorted(tallies):
            for rel in sorted(tallies[c]):
                obs, ok = tallies[c][rel]
                w.writerow([c, rel, obs, ok, "%.3f" % (ok / obs if obs else 0)])

    print("== nested store scan ==")
    classes = Counter(f["store_class"] for f in files)
    print("files: %d  classes: %s" % (len(files), dict(sorted(classes.items()))))
    totals = defaultdict(lambda: [0, 0])
    for c in sorted(tallies):
        for rel in sorted(tallies[c]):
            obs, ok = tallies[c][rel]
            totals[c][0] += obs
            totals[c][1] += ok
    for c in sorted(totals):
        obs, ok = totals[c]
        print("  %-30s %5d/%5d = %.3f" % (c, ok, obs, ok / obs if obs else 0))
    print("wrote CSVs under", out_dir)


if __name__ == "__main__":
    sys.exit(main())
