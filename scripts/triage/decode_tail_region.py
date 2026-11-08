#!/usr/bin/env python3
"""Decode and corpus-validate the CATIA_V5 CB0001 tail region (B2, ticket #18).

Evidence base: law H1 in docs/evidence/2026-11-07-container-table-and-trailer.md
(dword8 = start of the CB0001 tail region, dword12 = its length) and the Phase 1
observation "size - dword8 ~= 10 KB".  This script decodes what is INSIDE that
tail and validates the model below corpus-wide.

Tail model (ff x 8 generation; the tail spans [dword8, EOF), file offsets):

  T+0    16 B   magic "CATIA_V5 CB0001\\0"                     (law H1, B1)
  T+16   20 B   tail header:
                  +0  u8   tag 0x4e
                  +1  u16be 1000                              (constant)
                  +3  u16be 64  = region-chain origin         (constant)
                  +5  u16be 12                                (constant)
                  +7  u16le cntA
                  +9  u16le cntB = cntA + 1
                  +11 8 B  file-dependent (semantics open)
  T+36   28 B   zeros
  T+64   entry 0: [u32be M][u32be 1][zeros][01][u32be 94][u32be 0][ts8]
                  [zeros 19][12][zeros 35][name0]
                 M = 86 + 20k, k = 0..5 (0x56..0xba) and the entry0 length
                 == M + 87; the [01][X0][0][ts8] record sits at
                 (name0 start - 72) with X0 == 94.
  then   entries, each = 184-byte fixed part + a UTF-16 name:

    hdr84  [00 00][6a][000][seq u16le][space u32le][space u8][Y u32be]
           [0000][ts8][ts8][ts8][000][12][35 zeros]
    xrec13 [01][X u32be][Y u32be][Y u32be]        (Y stored twice)
    fil87  [11 zeros][u8][000][u8][00][Ynext u32be][000][ts8][ts8][ts8]
           [000][12][35 zeros]
    name   u16le len + UTF-16LE text + NUL char; two framings:
           storage len = 2*chars + 2, property len = 2*chars + 4 with a
           marker u16 (3 or 5) before the text.

  Laws (rates reported per file and corpus-wide):
    W1  entry walk: from name0, every next name starts exactly 184 bytes
        after the previous name field ends; each step's X-record has flag 01
        and Y1 == Y2.
    W2  hdr84 Y == xrec Y (same entry).
    W3  fil87 Y == next entry's xrec Y.
    W4  seq runs 2, 3, ... in list order.
  Region model (the interpretation that gives the header fields meaning):
    every entry names a FILE region [X, X+Y); together with the trailer
    record the regions tile [64, dword8) - the whole file body after the
    64-byte header:
    R1  min region start == 64 (the header's u16be@+19 constant)
    R2  max region end == dword8 (the tail start)
    R3  full tiling: sorted regions are contiguous (no unclaimed gaps)
    R4  the trailer is the catalog's last record: A == 1 (flag), B == X,
        C == D == Y; its region [B, B+C) starts with the writer
        registration block (B1's byte-proven B pointer).
  Space flag: 1 exactly on "Cont_*"-named entries and {CATIA1, Format,
  CATPreview}; 2 elsewhere (one-sided law; semantics open).

Generations and exceptions:
  - 146 dual-region files (no ff x 8 at bytes 16-24, B1): dword8 still starts
    a CB0001 tail (magic verified); dword16 = a first CB0001 region; dword20
    semantics tested here (first-region length and dword12/2).
  - ff x 8 files without CB__END (156): tails expected to be the magic plus
    zeros (measured).
  - tail_delta = size - dword8 outliers are cross-tabulated with the entry
    count: the tail scales with the region count (~184+ bytes per entry),
    not with file size.

Read-only; run with: python3 -I scripts/triage/decode_tail_region.py
Writes docs/evidence/data/tail-scan.csv (one row per file) and
docs/evidence/data/tail-entries-sample.csv (per-entry rows for the
deterministic version-stratified sample) and prints the claim summary.
"""
import csv
import mmap
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"
OUT_SCAN = OUT_DIR / "tail-scan.csv"
OUT_ENTRIES = OUT_DIR / "tail-entries-sample.csv"

CB0001 = b"CATIA_V5 CB0001\x00"
CB_END = b"CB__END\x00"
REG_RE = re.compile(rb"[\x4d\x4e]\x11\x00\x00\x00DASSAULT-SYSTEMES"
                    rb"\x05\x00\x00\x00CATIA\x06\x00\x00\x00041803")
RELEASE_RE = re.compile(r"^V5R(\d+)")
SP_TOP = {"CATIA1", "Format", "CATPreview"}


def u16le(b, o): return int.from_bytes(b[o:o + 2], "little")
def u32le(b, o): return int.from_bytes(b[o:o + 4], "little")
def u32be(b, o): return int.from_bytes(b[o:o + 4], "big")


def release_of(detected_version):
    m = RELEASE_RE.match(detected_version or "")
    return "R" + m.group(1) if m else "unknown"


def parse_name(t, i):
    """UTF-16 name field at i: storage (2n+2) or property (2n+4, marker 3|5).

    Text characters must be >= U+0020 (printable or accented); the field is
    NUL-terminated.  Returns (kind, text, end) or None.
    """
    N = len(t)
    if i + 4 > N:
        return None
    ln = u16le(t, i)
    if ln % 2 or ln < 6 or ln > 1024:
        return None
    nc = (ln - 2) // 2
    if i + 2 + ln <= N:
        seg = t[i + 2:i + 2 + 2 * nc]
        if len(seg) == 2 * nc:
            try:
                s = seg.decode("utf-16-le")
            except UnicodeDecodeError:
                s = None
            if s and all(ord(c) >= 32 for c in s) and \
                    t[i + 2 + ln:i + 4 + ln] == b"\x00\x00":
                return ("storage", s, i + 2 + ln)
    nc = (ln - 4) // 2
    if nc >= 1 and i + 2 + ln <= N:
        mk = u16le(t, i + 2)
        seg = t[i + 4:i + 4 + 2 * nc]
        if len(seg) == 2 * nc and mk in (3, 5):
            try:
                s = seg.decode("utf-16-le")
            except UnicodeDecodeError:
                s = None
            if s and all(ord(c) >= 32 for c in s) and \
                    t[i + 2 + ln:i + 4 + ln] == b"\x00\x00":
                return ("prop", s, i + 2 + ln)
    return None


def scan_tail(t, d8):
    """Parse one tail image (bytes dword8..EOF).  Returns measured facts."""
    out = {
        "magic": t[:16] == CB0001, "taillen": len(t),
        "walk_ok": False, "n_entries": 0, "entries": [],
        "break": "", "n_regions": 0, "tiling_full": None,
        "gaps": [], "nested_gap": False, "tail_end_gap": "",
    }
    if not out["magic"] or len(t) < 100:
        return out
    hdr = t[16:36]
    out["tag4e"] = hdr[0] == 0x4E
    out["k1000"] = int.from_bytes(hdr[1:3], "big") == 1000
    out["origin64"] = int.from_bytes(hdr[3:5], "big") == 64
    out["k12"] = int.from_bytes(hdr[5:7], "big") == 12
    out["cntA"] = u16le(hdr, 8)
    out["cntB"] = u16le(hdr, 10)
    out["var8_hex"] = hdr[12:20].hex()
    out["zeros36"] = all(not b for b in t[36:64])
    M = u32be(t, 64)
    out["M"] = M if (t[65:67] == b"\x00\x00" and
                     t[68:72] == b"\x00\x00\x00\x01") else -1

    # entry 0: first name at >= 72 whose [01][X0][0][ts8] record sits at -72
    first = None
    i = 72
    while i < len(t) - 36:
        nm = parse_name(t, i)
        if nm:
            r0 = t[i - 72:i - 55]
            if len(r0) == 17 and r0[0] == 0x01 and u32be(r0, 5) == 0:
                first = (i,) + nm
                out["e0_X0"] = u32be(r0, 1)
                break
        i += 1
    if not first:
        out["break"] = "entry0"
        return out
    out["e0_len"] = first[0] - 64
    out["e0_len_law"] = out["M"] >= 0 and out["e0_len"] == out["M"] + 87

    ents = []
    pos = first[3]
    while pos + 184 <= len(t):
        base = pos
        if base + 84 > len(t) - 36:
            break                      # trailer territory: clean end
        if t[base + 84] != 0x01:
            out["break"] = "flag@%d" % base
            break
        X, Y1, Y2 = (u32be(t, base + 85), u32be(t, base + 89),
                     u32be(t, base + 93))
        if Y1 != Y2:
            out["break"] = "Y1Y2@%d" % base
            break
        if base + 184 >= len(t) - 36:
            break                      # no room for another name: clean end
        nm = parse_name(t, base + 184)
        if not nm or nm[2] > len(t) - 28:
            out["break"] = "name@%d" % base
            break
        ents.append({
            "base": base, "seq": u16le(t, base + 6), "sp": u32le(t, base + 8),
            "sp_copy": t[base + 12], "Y_hdr": u32be(t, base + 13),
            "X": X, "Y": Y1, "Y_fil": u32be(t, base + 113),
            "kind": nm[0], "name": nm[1],
            "m12a": t[base + 48] == 0x12, "m12b": t[base + 148] == 0x12,
            "m6a": t[base + 2] == 0x6A,
        })
        pos = nm[2]
    out["entries"] = ents
    out["n_entries"] = len(ents)
    out["walk_ok"] = out["break"] == ""
    if out["walk_ok"]:
        out["tail_end_gap"] = len(t) - 36 - pos

    # trailer record + region model
    tb = t[len(t) - 36:]
    out["ends_cbend"] = tb[28:36] == CB_END
    if out["ends_cbend"]:
        out["A"] = u32be(tb, 0)
        out["B"] = u32be(tb, 4)
        out["C"] = u32be(tb, 8)
        out["D"] = u32be(tb, 12)
        out["G"] = u32be(tb, 24)
        out["G_eq_taillen"] = out["G"] == len(t)
        out["trailer_xrec"] = (out["A"] == 1 and out["C"] == out["D"] and
                               out["G_eq_taillen"])
    # end block: the final record's truncated hdr84 between the last name
    # and the trailer (81 bytes; seq == cntB, sp == 2, Y == C)
    if out["walk_ok"] and out["ends_cbend"]:
        eb = t[pos:pos + 81]
        if len(eb) == 81:
            out["endblock"] = (eb[0:2] == b"\x00\x00" and eb[2] == 0x6A and
                               u16le(eb, 6) == out["cntB"] and
                               u32le(eb, 8) == 2 and eb[12] == 2 and
                               u32be(eb, 13) == out["C"] and
                               eb[48] == 0x12)
            out["endblock_len"] = 81
        # exact length accounting:
        # 64 (magic+header+zeros) + entry0 area + entry0 name field
        # + sum over entries (184 fixed + name field) + 81 (end block) + 36
        acc = 64 + (first[3] - 64) + 81 + 36
        bounds = [e["base"] for e in ents] + [pos]
        for k in range(len(ents)):
            acc += bounds[k + 1] - bounds[k]
        out["predicted_len"] = acc
        out["accounting_ok"] = acc == len(t)
    regs = [(e["X"], e["Y"]) for e in ents]
    if out["ends_cbend"]:
        regs.append((out["B"], out["C"]))
    regs.sort()
    out["n_regions"] = len(regs)
    if regs:
        out["region_min"] = regs[0][0]
        out["region_max_end"] = regs[-1][0] + regs[-1][1]
        out["R1_min64"] = regs[0][0] == 64
        out["R2_max_d8"] = regs[-1][0] + regs[-1][1] == d8
        gaps = [(a[0] + a[1], b[0] - (a[0] + a[1]))
                for a, b in zip(regs, regs[1:]) if a[0] + a[1] != b[0]]
        out["gaps"] = gaps
        out["tiling_full"] = not gaps
    return out


def sample_rows(rows):
    """Deterministic stratified sample: smallest/middle/largest size per version."""
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
    fields = ["sha256", "size_bytes", "repo", "detected_version", "release",
              "kind", "ff8_at_16_24", "ends_cbend", "dword8", "dword12",
              "tail_delta", "magic", "tag4e", "k1000", "origin64", "k12",
              "cntA", "cntB", "cnt_law", "var8_hex", "zeros36", "M", "e0_len",
              "e0_len_law", "e0_X0_94", "walk_ok", "walk_break", "n_entries",
              "seq_law", "Y_laws", "sp1_implies_name", "cont_sp1", "e1_name",
              "e1_Y94", "A", "B", "C", "D", "G", "G_eq_taillen",
              "trailer_xrec", "B_eq_prev_end", "B_plus_C_eq_e2X",
              "n_regions", "region_min", "region_max_end",
              "R1_min64", "R2_max_d8", "tiling_full", "n_gaps", "gap_list",
              "reg_occurrences", "B_is_registration", "d8_end_pos",
              "tail_end_gap", "endblock", "accounting_ok", "predicted_len",
              "dword16", "dword20", "cb0001_offsets", "first_cbend"]
    w = csv.DictWriter(OUT_SCAN.open("w", newline=""), fieldnames=fields)
    w.writeheader()
    sample = sample_rows(rows)
    sample_shas = {r["sha256"] for r in sample}
    efields = ["sha256", "detected_version", "entry_ordinal", "seq", "space",
               "name_kind", "name", "X", "Y", "Y_hdr_copy", "Y_fil_next",
               "m6a", "m12a", "m12b"]
    ew = csv.DictWriter(OUT_ENTRIES.open("w", newline=""), fieldnames=efields)
    ew.writeheader()

    T = Counter()
    per_ver = defaultdict(Counter)   # main scope only
    tail_deltas = []
    entry_sample_shas = set()
    for r in rows:
        p = ROOT / r["local_path"]
        size = int(r["size_bytes"])
        rel = release_of(r["detected_version"])
        with p.open("rb") as fh:
            head = fh.read(32)
        if len(head) < 32:
            continue
        d8 = int.from_bytes(head[8:12], "big")
        d12 = int.from_bytes(head[12:16], "big")
        ff8 = head[16:24] == b"\xff" * 8
        T["files"] += 1
        T["ff8"] += ff8
        tail_delta = size - d8
        tail_deltas.append((tail_delta, r["sha256"], size, rel, ff8,
                            r["detected_version"] or "unknown"))
        with p.open("rb") as fh:
            mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            t = mm[d8:size]
            occs = [m.start() for m in REG_RE.finditer(mm)]
            d16 = u32be(head, 16) if not ff8 else ""
            d20 = u32be(head, 20) if not ff8 else ""
            cb_offs = []
            i = mm.find(CB0001)
            while i >= 0:
                cb_offs.append(i)
                i = mm.find(CB0001, i + 1)
            fc = mm.find(CB_END)
            mm.close()
        s = scan_tail(t, d8)
        T["magic"] += s["magic"]
        scope = ("main" if (ff8 and s.get("ends_cbend"))
                 else "notrail" if ff8 else "dual")
        T["scope_" + scope] += 1
        row = {
            "sha256": r["sha256"], "size_bytes": size, "repo": r["repo"],
            "detected_version": r["detected_version"], "release": rel,
            "kind": r["kind"], "ff8_at_16_24": ff8,
            "ends_cbend": s.get("ends_cbend", False),
            "dword8": d8, "dword12": d12, "tail_delta": tail_delta,
            "magic": s["magic"], "dword16": d16, "dword20": d20,
            "cb0001_offsets": ";".join(map(str, cb_offs)),
            "first_cbend": fc if fc >= 0 else "",
        }
        if s["magic"] and len(t) >= 100:
            T["hdr_files"] += 1
            for k in ("tag4e", "k1000", "origin64", "k12", "zeros36",
                      "e0_len_law"):
                T[k] += bool(s.get(k))
            cnt_law = s["cntB"] == s["cntA"] + 1
            T["cnt_law"] += cnt_law
            e0_ok = s.get("e0_X0") == 94 and bool(s.get("e0_len_law"))
            T["e0_X0_94"] += e0_ok
            T["M_" + str(s.get("M"))] += 1
            ents = s["entries"]
            T["entries"] += len(ents)
            T["skeleton_entries"] += len(ents)
            T["skeleton_entries_ok"] += sum(
                1 for e in ents if e["m6a"] and e["m12a"] and e["m12b"])
            seq_ok = all(e["seq"] == k + 2 for k, e in enumerate(ents))
            yhdr_ok = all(e["Y_hdr"] == e["Y"] for e in ents)
            yfil_ok = all(a["Y_fil"] == b["Y"] for a, b in zip(ents, ents[1:]))
            T["walk_files"] += 1
            T["walk_ok"] += s["walk_ok"]
            T["seq_law"] += seq_ok
            T["Y_hdr_law"] += yhdr_ok
            T["Y_fil_law"] += yfil_ok
            d8pos = []
            if ents:
                T["e1_name_CATIA1"] += ents[0]["name"] == "CATIA1"
                T["e1_Y94"] += ents[0]["Y"] == 94
                d8pos = [k for k, e in enumerate(ents)
                         if e["X"] + e["Y"] == d8]
                T["d8_end_top3"] += bool(d8pos) and d8pos[0] <= 2
                row["d8_end_pos"] = d8pos[0] if d8pos else ""
            sp1_names = all(not (e["sp"] == 1) or
                            e["name"].startswith("Cont_") or
                            e["name"] in SP_TOP for e in ents)
            cont_sp1 = all(e["sp"] == 1 for e in ents
                           if e["name"].startswith("Cont_"))
            T["sp1_implies_name"] += sp1_names
            T["cont_sp1"] += cont_sp1
            if s["walk_ok"] and s["n_regions"]:
                T["tile_files"] += 1
                T["R1_min64"] += bool(s.get("R1_min64"))
                T["R2_max_d8"] += bool(s.get("R2_max_d8"))
                T["R3_tiling_full"] += bool(s.get("tiling_full"))
                T["R3_le1_gap"] += len(s["gaps"]) <= 1
                if s["gaps"]:
                    T["files_with_gaps"] += 1
                    T["gap_bytes_total"] += sum(g for _, g in s["gaps"])
            if scope == "main":
                per_ver[rel]["files"] += 1
                for k, ok in (("walk_ok", s["walk_ok"]), ("seq_law", seq_ok),
                              ("Y_laws", yhdr_ok and yfil_ok),
                              ("sp1_implies_name", sp1_names),
                              ("cnt_law", cnt_law), ("e0_X0_94", e0_ok)):
                    per_ver[rel][k] += int(ok)
                per_ver[rel]["R3_le1_gap"] += int(
                    s["walk_ok"] and s["n_regions"] and len(s["gaps"]) <= 1)
                per_ver[rel]["tile_files"] += int(
                    s["walk_ok"] and s["n_regions"] > 0)
            if s.get("ends_cbend"):
                T["cbend_files"] += 1
                T["trailer_xrec"] += bool(s.get("trailer_xrec"))
                if s["walk_ok"]:
                    T["endblock_files"] += 1
                    T["endblock_ok"] += bool(s.get("endblock"))
                    T["accounting_ok"] += bool(s.get("accounting_ok"))
                if s["walk_ok"] and ents:
                    regs2 = sorted([(e["X"], e["Y"]) for e in ents] +
                                   [(s["B"], s["C"])])
                    idx = regs2.index((s["B"], s["C"]))
                    b_prev = (idx > 0 and
                              regs2[idx - 1][0] + regs2[idx - 1][1] == s["B"])
                    T["B_eq_prev_end"] += b_prev
                    b_e2 = (len(ents) >= 2 and
                            s["B"] + s["C"] == ents[1]["X"])
                    T["B+C_eq_e2X"] += b_e2
                    s["B_eq_prev_end"] = b_prev
                    s["B_plus_C_eq_e2X"] = b_e2
            row.update({
                "tag4e": s.get("tag4e"), "k1000": s.get("k1000"),
                "origin64": s.get("origin64"), "k12": s.get("k12"),
                "cntA": s.get("cntA"), "cntB": s.get("cntB"),
                "cnt_law": cnt_law,
                "var8_hex": s.get("var8_hex"), "zeros36": s.get("zeros36"),
                "M": s.get("M"), "e0_len": s.get("e0_len"),
                "e0_len_law": s.get("e0_len_law"), "e0_X0_94": e0_ok,
                "walk_ok": s["walk_ok"], "walk_break": s["break"],
                "n_entries": s["n_entries"], "seq_law": seq_ok,
                "Y_laws": yhdr_ok and yfil_ok,
                "sp1_implies_name": sp1_names, "cont_sp1": cont_sp1,
                "e1_name": ents[0]["name"] if ents else "",
                "e1_Y94": ents[0]["Y"] == 94 if ents else "",
                "A": s.get("A"), "B": s.get("B"), "C": s.get("C"),
                "D": s.get("D"), "G": s.get("G"),
                "G_eq_taillen": s.get("G_eq_taillen"),
                "trailer_xrec": s.get("trailer_xrec", ""),
                "B_eq_prev_end": s.get("B_eq_prev_end", ""),
                "B_plus_C_eq_e2X": s.get("B_plus_C_eq_e2X", ""),
                "n_regions": s["n_regions"],
                "region_min": s.get("region_min"),
                "region_max_end": s.get("region_max_end"),
                "R1_min64": s.get("R1_min64"), "R2_max_d8": s.get("R2_max_d8"),
                "tiling_full": s.get("tiling_full"),
                "n_gaps": len(s["gaps"]) if s["walk_ok"] else "",
                "gap_list": (";".join("%d@%d" % (g, at)
                                      for at, g in s["gaps"])
                             if s["walk_ok"] else ""),
                "reg_occurrences": len(occs),
                "B_is_registration": (s.get("B") in occs)
                if s.get("ends_cbend") else "",
                "tail_end_gap": s.get("tail_end_gap", ""),
                "endblock": s.get("endblock", ""),
                "accounting_ok": s.get("accounting_ok", ""),
                "predicted_len": s.get("predicted_len", ""),
            })
            if (r["sha256"] in sample_shas
                    and r["sha256"] not in entry_sample_shas):
                entry_sample_shas.add(r["sha256"])
                for k, e in enumerate(s["entries"]):
                    ew.writerow({
                        "sha256": r["sha256"],
                        "detected_version": r["detected_version"],
                        "entry_ordinal": k, "seq": e["seq"], "space": e["sp"],
                        "name_kind": e["kind"], "name": e["name"],
                        "X": e["X"], "Y": e["Y"], "Y_hdr_copy": e["Y_hdr"],
                        "Y_fil_next": e["Y_fil"], "m6a": e["m6a"],
                        "m12a": e["m12a"], "m12b": e["m12b"],
                    })
        if scope == "notrail":
            T["notrail_zerotail_after_magic"] += all(not b for b in t[16:])
            T["notrail_with_entries"] += s["n_entries"] > 0
        if scope == "dual":
            T["dual_d16_first_cb"] += bool(cb_offs) and cb_offs[0] == d16
            T["dual_d8_last_cb"] += bool(cb_offs) and cb_offs[-1] == d8
            T["dual_zerotail_after_magic"] += (not s.get("ends_cbend", False)
                                               and all(not b
                                                       for b in t[16:]))
            if cb_offs and fc >= 0:
                T["d20_both"] += 1
                T["d20_eq_first_region_len"] += d20 == fc + 8 - cb_offs[0]
                T["d20_eq_d12_half"] += d12 == 2 * d20
        w.writerow(row)

    # ---- summary ----
    tail_deltas.sort()
    n = len(tail_deltas)
    T["tail_delta_min"] = tail_deltas[0][0]
    T["tail_delta_p25"] = tail_deltas[n // 4][0]
    T["tail_delta_median"] = tail_deltas[n // 2][0]
    T["tail_delta_p75"] = tail_deltas[3 * n // 4][0]
    T["tail_delta_max"] = tail_deltas[-1][0]
    print("files:", T["files"], "(ff8 %d; main scope %d, no-trailer ff8 %d, "
          "dual-region %d)" % (T["ff8"], T["scope_main"], T["scope_notrail"],
                               T["scope_dual"]))
    print("CB0001 magic at dword8: %d/%d" % (T["magic"], T["files"]))
    print()
    print("== tail header + entry0 (files with a parsed tail: %d) ==" %
          T["hdr_files"])
    for k in ("tag4e", "k1000", "origin64", "k12", "zeros36", "cnt_law",
              "e0_len_law", "e0_X0_94"):
        print("  %-12s %d/%d" % (k, T[k], T["hdr_files"]))
    print("  M distribution:", {k[2:]: v for k, v in sorted(T.items())
                                if k.startswith("M_")})
    print()
    print("== entry walk (files entering the walk: %d) ==" % T["walk_files"])
    for k in ("walk_ok", "seq_law", "Y_hdr_law", "Y_fil_law", "sp1_implies_name",
              "cont_sp1", "e1_name_CATIA1", "e1_Y94", "d8_end_top3"):
        print("  %-18s %d/%d" % (k, T[k], T["walk_files"]))
    print("  entries parsed: %d; skeleton (6a/12/12) per entry: %d/%d" %
          (T["entries"], T["skeleton_entries_ok"], T["skeleton_entries"]))
    print()
    print("== region model (walk-complete files: %d) ==" % T["tile_files"])
    for k in ("R1_min64", "R2_max_d8", "R3_tiling_full", "R3_le1_gap"):
        print("  %-16s %d/%d" % (k, T[k], T["tile_files"]))
    print("  files with gaps: %d  total unclaimed gap bytes: %d" %
          (T["files_with_gaps"], T["gap_bytes_total"]))
    print()
    print("== trailer as last catalog record (CB__END-ending files: %d) ==" %
          T["cbend_files"])
    for k in ("trailer_xrec", "B_eq_prev_end", "B+C_eq_e2X"):
        print("  %-16s %d/%d" % (k, T[k], T["cbend_files"]))
    print("  end block (walk-ok files: %d): law %d/%d; exact length "
          "accounting %d/%d" % (T["endblock_files"], T["endblock_ok"],
                                T["endblock_files"], T["accounting_ok"],
                                T["endblock_files"]))
    print()
    print("== generations ==")
    print("  no-trailer ff8: %d; with parsed entries: %d; zero tail after "
          "magic: %d" % (T["scope_notrail"], T["notrail_with_entries"],
                         T["notrail_zerotail_after_magic"]))
    print("  dual-region: dword16==first CB0001 %d/%d, dword8==last CB0001 "
          "%d/%d, zero tail after magic %d/%d" %
          (T["dual_d16_first_cb"], T["scope_dual"], T["dual_d8_last_cb"],
           T["scope_dual"], T["dual_zerotail_after_magic"], T["scope_dual"]))
    print("  dword20 == first-region length: %d/%d; == dword12/2: %d/%d" %
          (T["d20_eq_first_region_len"], T["d20_both"],
           T["d20_eq_d12_half"], T["d20_both"]))
    print()
    print("== tail_delta = size - dword8 (all %d files) ==" % n)
    print("  min %d  p25 %d  median %d  p75 %d  max %d" %
          (T["tail_delta_min"], T["tail_delta_p25"], T["tail_delta_median"],
           T["tail_delta_p75"], T["tail_delta_max"]))
    print("  smallest 6:", [(d, sha[:12], sz, rel) for d, sha, sz, rel, _, _
                            in tail_deltas[:6]])
    print("  largest 6:", [(d, sha[:12], sz, rel) for d, sha, sz, rel, _, _
                           in tail_deltas[-6:]])
    print()
    print("== per-version rates, main scope (files / walk_ok / Y-laws / "
          "cnt+e0 / tiling<=1gap per walk-complete) ==")
    for rel in sorted(per_ver):
        v = per_ver[rel]
        f = v["files"]
        tf = v["tile_files"]
        print("  %-8s files %5d  walk %.3f  Ylaws %.3f  hdrlaws %.3f  "
              "tile<=1gap %.3f (of %d)" %
              (rel, f, v["walk_ok"] / f, v["Y_laws"] / f,
               (v["cnt_law"] + v["e0_X0_94"]) / (2 * f),
               (v["R3_le1_gap"] / tf) if tf else 0.0, tf))
    print("wrote", OUT_SCAN)
    print("wrote", OUT_ENTRIES)
    return 0


if __name__ == "__main__":
    sys.exit(main())
