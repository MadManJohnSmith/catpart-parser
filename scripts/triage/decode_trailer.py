#!/usr/bin/env python3
"""Decode and corpus-validate the file trailer and header dword chain.

Evidence base: docs/evidence/2026-11-07-container-triage.md (Phase 1) and
ticket #17 (Spec B, Phase 2). Phase 1 observed the trailer (last bytes:
`CB__END\\0` preceded by dwords) and left the field semantics open. This
script parses every magic_ok file and validates the model below.

Trailer model — the last 36 bytes of a file that ends with `CB__END\\0`
(all multi-byte fields big-endian):

  -36  A   u32   constant 0x00000001                      (the "...01" dword)
  -32  B   u32   absolute file offset of the writer
                 registration block: at B the file carries
                 [tag byte 0x4d|0x4e][u32le 17]"DASSAULT-SYSTEMES"
                 [u32le 5]"CATIA"[u32le 6]"041803"...
                 (the Phase 1 "size-like dword": it moves by exactly the
                 size delta between near-identical saves, because the
                 block sits after the preview image in the payload)
  -28  C   u32   == D (pair, stored twice); value varies per file,
                 0x000000e7 on most R19/R21 parts   (the "0x...e7 pair")
  -24  D   u32   == C
  -20  E   u32   0
  -16  F   u32   0 or 1 (1 observed on oldest releases)
  -12  G   u32   == header dword12 == size - header dword8
                 (length of the CATIA_V5 CB0001 tail region)
   -8  "CB__END\0"                                       (8 bytes)

Header model:
  8-12   dword8   BE; start offset of the tail region
  12-16  dword12  BE; == size - dword8 (tail length) and == trailer G
  16-24  eight 0xFF bytes, except 146 files that carry two more BE
         dwords (dword16, dword20) instead — a different generation
         whose layout carries a second CATIA_V5 CB0001 region.

The 262 files that do not end with CB__END\\0 are counted and
cross-tabulated with the ff x8 exceptions. The near-identical save pairs
from Phase 1 (the "+12-byte Copia pair") are re-measured exactly.

Read-only; run with: python3 -I scripts/triage/decode_trailer.py
Writes docs/evidence/data/trailer-scan.csv and a summary to stdout.
"""
import csv, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"
OUT = OUT_DIR / "trailer-scan.csv"

CB_END = b"CB__END\x00"
CB0001 = b"CATIA_V5 CB0001\x00"
DASSAULT = b"DASSAULT-SYSTEMES"
REG_TAG = (0x4D, 0x4E)

# Near-identical save pairs from the Phase 1 evidence note
# (deep_sample.py PAIRS), used to re-measure the trailer delta behavior.
PAIRS = [
    ("TRABALHO MOTOR.CATPart", "TRABALHO MOTOR - Copia.CATPart"),
    ("Case_Logo_Black", "Case_Logo_Blue"),
    ("lengua_v1/lengua_1.CATPart", "lengua_v2/lengua_1.CATPart"),
]


def be(buf, off):
    return int.from_bytes(buf[off:off + 4], "big")


def read_trailer(path, size):
    """Return (head32, tail36) reading only the file edges."""
    with path.open("rb") as fh:
        fh.seek(0)
        head = fh.read(32)
        fh.seek(max(0, size - 36))
        tail = fh.read(36)
    return head, tail


def parse_registration(path, b):
    """Validate the writer registration block at absolute offset B."""
    with path.open("rb") as fh:
        fh.seek(b)
        blk = fh.read(41)
    if len(blk) < 41:
        return False, False, False, ""
    tag_ok = blk[0] in REG_TAG
    le = lambda o: int.from_bytes(blk[o:o + 4], "little")
    d_ok = tag_ok and le(1) == 17 and blk[5:22] == DASSAULT
    c_ok = d_ok and le(22) == 5 and blk[26:31] == b"CATIA"
    code_ok = c_ok and le(31) == 6 and blk[35:41] == b"041803"
    return d_ok, c_ok, code_ok, chr(blk[0])


def main():
    rows = [r for r in csv.DictReader(MANIFEST.open()) if r["magic_ok"] == "yes"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fields = ["sha256", "size_bytes", "repo", "detected_version", "kind",
              "ff8_at_16_24", "ends_cbend", "dword8", "dword12",
              "dword16", "dword20", "A", "B", "C", "D", "E", "F", "G",
              "A_is_1", "C_eq_D", "E_is_0", "G_eq_dword12",
              "reg_tag", "reg_dassault", "reg_catia", "reg_code",
              "size_eq_d8_plus_d12", "cb0001_at_dword8",
              "cb0001_offsets", "cbend_offsets"]
    w = csv.DictWriter(OUT.open("w", newline=""), fieldnames=fields)
    w.writeheader()

    t = Counter()
    cvals = Counter()
    fvals = Counter()
    f_by_ver = {}
    tags = Counter()
    noff_by_repo = Counter()
    noff_by_ver = Counter()
    noff_kinds = Counter()
    noff_dual = 0
    noff_last_at_size_minus_d12 = 0
    noff_first_at_d16 = 0
    noend = Counter()
    for r in rows:
        path = ROOT / r["local_path"]
        size = int(r["size_bytes"])
        head, tail = read_trailer(path, size)
        ff8 = head[16:24] == b"\xff" * 8
        t["files"] += 1
        t["ff8"] += ff8
        if not ff8:
            noff_by_repo[r["repo"]] += 1
            noff_by_ver[r["detected_version"] or "unknown"] += 1
            noff_kinds[r["kind"]] += 1
        dword8, dword12 = be(head, 8), be(head, 12)
        dword16 = be(head, 16) if not ff8 else ""
        dword20 = be(head, 20) if not ff8 else ""
        ends = tail.endswith(CB_END)
        t["ends_cbend"] += ends
        if not ends:
            noend[(r["detected_version"] or "unknown", ff8)] += 1
        row = {
            "sha256": r["sha256"], "size_bytes": size, "repo": r["repo"],
            "detected_version": r["detected_version"], "kind": r["kind"],
            "ff8_at_16_24": ff8, "ends_cbend": ends,
            "dword8": dword8, "dword12": dword12,
            "dword16": dword16, "dword20": dword20,
        }
        if not ff8:
            # no-ff generation: locate the CB0001 regions and CB__ENDs
            data = path.read_bytes()
            offs, eoffs = [], []
            i = data.find(CB0001)
            while i >= 0:
                offs.append(i)
                i = data.find(CB0001, i + 1)
            i = data.find(CB_END)
            while i >= 0:
                eoffs.append(i)
                i = data.find(CB_END, i + 1)
            noff_dual += len(offs) >= 2
            noff_first_at_d16 += bool(offs) and offs[0] == dword16
            noff_last_at_size_minus_d12 += bool(offs) and offs[-1] == size - dword12
            row["cb0001_offsets"] = ";".join(map(str, offs))
            row["cbend_offsets"] = ";".join(map(str, eoffs))
        if ends:
            a, b, c, d, e, f, g = (be(tail, -36 + 4 * i) for i in range(7))
            d_ok, c_ok, code_ok, tag = parse_registration(path, b)
            t["parsed"] += 1
            t["A_is_1"] += a == 1
            t["C_eq_D"] += c == d
            t["E_is_0"] += e == 0
            t["G_eq_dword12"] += g == dword12
            t["reg_dassault"] += d_ok
            t["reg_catia"] += c_ok
            t["reg_code"] += code_ok
            t["size_eq_d8_plus_d12"] += dword8 + dword12 == size
            cvals[c] += 1
            fvals[f] += 1
            tags[tag] += 1
            f_by_ver.setdefault(r["detected_version"] or "unknown", Counter())[f] += 1
            # CB0001 tail region starts at dword8 on ff8 files
            with path.open("rb") as fh:
                fh.seek(dword8)
                magic = fh.read(16)
            if ff8:
                t["ff8_ends"] += 1
                t["cb0001_at_dword8"] += magic == CB0001
            row.update({"A": a, "B": b, "C": c, "D": d, "E": e, "F": f, "G": g,
                        "A_is_1": a == 1, "C_eq_D": c == d, "E_is_0": e == 0,
                        "G_eq_dword12": g == dword12, "reg_tag": tag,
                        "reg_dassault": d_ok, "reg_catia": c_ok,
                        "reg_code": code_ok,
                        "size_eq_d8_plus_d12": dword8 + dword12 == size,
                        "cb0001_at_dword8": ff8 and magic == CB0001})
            if not (a == 1 and c == d and e == 0 and g == dword12 and d_ok):
                t["law_exception_files"] += 1
        w.writerow(row)

    n = t["files"]
    print("files scanned:", n)
    print("ff x8 at bytes 16-24: {}/{} ({:.1%}); exceptions: {}".format(
        t["ff8"], n, t["ff8"] / n, n - t["ff8"]))
    print("  exception repos:", noff_by_repo.most_common())
    print("  exception versions:", noff_by_ver.most_common())
    print("  exception kinds:", noff_kinds.most_common())
    print("  exceptions with >=2 CB0001 regions: {}/{}".format(noff_dual, n - t["ff8"]))
    print("  exceptions first CB0001 at dword16: {}/{}".format(
        noff_first_at_d16, n - t["ff8"]))
    print("  exceptions last CB0001 at size-dword12: {}/{}".format(
        noff_last_at_size_minus_d12, n - t["ff8"]))
    print("files ending CB__END\\0: {}/{} ({:.1%})".format(
        t["ends_cbend"], n, t["ends_cbend"] / n))
    print("  without CB__END:", dict(noend))
    p = t.get("parsed", 0)
    print("trailer parsed (ends with CB__END):", p)
    for law in ("A_is_1", "C_eq_D", "E_is_0", "G_eq_dword12",
                "reg_dassault", "reg_catia", "reg_code",
                "size_eq_d8_plus_d12"):
        print("  {}: {}/{}".format(law, t[law], p))
    print("  cb0001_at_dword8 (ff8 files only): {}/{}".format(
        t["cb0001_at_dword8"], t["ff8_ends"]))
    print("  files violating any trailer law:", t["law_exception_files"])
    print("C value distribution (top 8):", cvals.most_common(8))
    print("F value distribution:", fvals.most_common())
    print("F by version (F=1 files):",
          sorted(v for v, c in f_by_ver.items() if c.get(1)))
    print("registration tag bytes:", tags.most_common())
    print("wrote", OUT)

    print("\n== near-identical save pairs (trailer deltas) ==")
    by_path = {}
    for r in rows:
        by_path[r["path"]] = r
    for a_needle, b_needle in PAIRS:
        ra = rb = None
        for path, r in by_path.items():
            if ra is None and a_needle in path:
                ra = r
            if rb is None and b_needle in path:
                rb = r
        if not ra or not rb:
            print("  pair not found: {} / {}".format(a_needle, b_needle))
            continue
        vals = {}
        for key, r in (("a", ra), ("b", rb)):
            with (ROOT / r["local_path"]).open("rb") as fh:
                fh.seek(max(0, int(r["size_bytes"])) - 36)
                tail = fh.read(36)
                fh.seek(0)
                head = fh.read(32)
            if tail.endswith(CB_END):
                vals[key] = (int(r["size_bytes"]), be(head, 8), be(head, 12),
                             *[be(tail, -36 + 4 * i) for i in range(7)])
        if "a" in vals and "b" in vals:
            names = ("size", "dword8", "dword12", "A", "B", "C", "D", "E", "F", "G")
            deltas = ["{} {:+d}".format(nm, vb - va)
                      for nm, va, vb in zip(names, vals["a"], vals["b"])]
            print("  {} vs {}".format(a_needle, b_needle))
            print("    deltas: " + ", ".join(deltas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
