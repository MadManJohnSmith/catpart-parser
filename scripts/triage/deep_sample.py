#!/usr/bin/env python3
"""Phase 1 deep analysis of a representative sample.

For each sample file: full 4 KB-block entropy profile (zone summary),
ASCII strings from the first 64 KB with offsets, and header hexdump.
For selected similar-file pairs: common prefix/suffix and first-64KB
byte agreement, to separate per-object from per-file fields.
Read-only; run with: python3 -I scripts/triage/deep_sample.py
"""
import csv, math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
BLOCK = 4096

SAMPLE_HINTS = [
    ("hssnadr/HTBX_01Ressources", "HITBOX.CATProduct"),
    ("hssnadr/HTBX_01Ressources", "DB25_08.CATPart"),
    ("Apoloo13/ASE_III", "modelos_originales/head.CATPart"),
    ("dolganin/SO_SPIDAR300", "Antdroid.CATProduct"),
    ("Guilherme115/Motor-V6", "Carter de Oleo - Motor V6.CATPart"),
    ("SSadayuki/B31CAADoc", ".CATPart"),
    ("povdoigt/SP-02", ".CATPart"),
]

PAIRS = [
    ("Case_Logo_Black", "Case_Logo_Blue"),
    ("lengua_v1/lengua_1.CATPart", "lengua_v2/lengua_1.CATPart"),
    ("TRABALHO MOTOR.CATPart", "TRABALHO MOTOR - Copia.CATPart"),
]


def entropy(block):
    if not block:
        return 0.0
    counts = [0] * 256
    for b in block:
        counts[b] += 1
    n = len(block)
    return -sum((c / n) * math.log2(c / n) for c in counts if c)


def zone_summary(path):
    """4 KB-block entropy profile; summarize zones, not per-block noise.
    Files > 32 MB are strided (every k-th block) to stay fast; the zone
    boundaries then carry that granularity."""
    fsize = path.stat().st_size
    stride = max(1, (fsize // (32 * 1024 * 1024)) + 1)
    sizes, zones = [], []
    with path.open("rb") as fh:
        off = 0
        while True:
            block = fh.read(BLOCK)
            if not block:
                break
            if (off // BLOCK) % stride == 0:
                sizes.append((off, entropy(block)))
            off += len(block)
    total = off
    def mean(a, b):
        sel = [h for o, h in sizes if a <= o < b]
        return sum(sel) / len(sel) if sel else 0
    # classify blocks
    low = [o for o, h in sizes if h < 4.0]
    mid = [o for o, h in sizes if 4.0 <= h < 7.2]
    high = [o for o, h in sizes if h >= 7.2]
    def rng(offsets):
        return "none" if not offsets else "{}-{}".format(offsets[0], offsets[-1] + BLOCK)
    return {
        "size": total,
        "mean_entropy": round(mean(0, total), 3),
        "head_entropy_16k": round(mean(0, 16384), 3),
        "tail_entropy_16k": round(mean(max(0, total - 16384), total), 3),
        "low_zone": rng(low), "mid_zone": rng(mid), "high_zone": rng(high),
        "high_share": round(len(high) / max(1, len(sizes)), 3),
    }


def strings_with_offsets(data, min_len=6, limit=40):
    out, cur, start = [], bytearray(), 0
    for i, b in enumerate(data):
        if 32 <= b < 127:
            if not cur:
                start = i
            cur.append(b)
        else:
            if len(cur) >= min_len:
                out.append((start, cur.decode("ascii")))
            cur = bytearray()
    return out[:limit]


def load_unique():
    return [r for r in csv.DictReader(MANIFEST.open()) if r["magic_ok"] == "yes"]


def find(rows, repo, needle):
    for r in rows:
        if r["repo"] == repo and needle in r["path"]:
            return r
    return None


def compare(rows, a_needle, b_needle):
    a = b = None
    for r in rows:
        if a_needle in r["path"] and a is None:
            a = r
        if b_needle in r["path"] and b is None:
            b = r
    if not a or not b:
        return "PAIR NOT FOUND: {} / {}".format(a_needle, b_needle)
    pa = ROOT / a["local_path"]
    pb = ROOT / b["local_path"]
    da, db = pa.read_bytes(), pb.read_bytes()
    prefix = 0
    for x, y in zip(da, db):
        if x != y:
            break
        prefix += 1
    suffix = 0
    for x, y in zip(reversed(da), reversed(db)):
        if x != y:
            break
        suffix += 1
    window = 65536
    agree = sum(1 for x, y in zip(da[:window], db[:window]) if x == y)
    return ("{} ({} B) vs {} ({} B)\n  common prefix: {} B | common suffix: {} B | "
            "first-64KB byte agreement: {:.1%}".format(
                a["path"], len(da), b["path"], len(db), prefix, suffix,
                agree / min(window, len(da), len(db))))


def main():
    rows = load_unique()
    print("== SAMPLE ENTROPY PROFILES ==")
    seen = set()
    for repo, needle in SAMPLE_HINTS:
        r = find(rows, repo, needle)
        if not r or r["sha256"] in seen:
            continue
        seen.add(r["sha256"])
        z = zone_summary(ROOT / r["local_path"])
        print("\n{} {}  ({} B, {})".format(r["repo"], r["path"], r["size_bytes"], r["kind"]))
        print("  " + "  ".join("{}={}".format(k, v) for k, v in z.items()))

    print("\n== STRINGS (first 64 KB, up to 40) ==")
    for repo, needle in SAMPLE_HINTS[:5]:
        r = find(rows, repo, needle)
        if not r:
            continue
        data = (ROOT / r["local_path"]).read_bytes()[:65536]
        ss = strings_with_offsets(data)
        print("\n{} {} — {} strings".format(r["repo"], r["path"], len(ss)))
        for off, s in ss[:40]:
            print("  @0x{:06x} {!r}".format(off, s[:90]))

    print("\n== SIMILAR-FILE PAIRS ==")
    for a, b in PAIRS:
        print("\n" + compare(rows, a, b))


if __name__ == "__main__":
    main()
