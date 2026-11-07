#!/usr/bin/env python3
"""Phase 1 header scan over the unique corpus.

Reads manifests/corpus-manifest.csv, parses the first 64 bytes of every
magic_ok file, and emits docs/evidence/data/header-scan.csv plus a summary
to stdout. Read-only; run with: python3 -I scripts/triage/header_scan.py
"""
import csv, math, re, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"
OUT = OUT_DIR / "header-scan.csv"


def entropy(block):
    if not block:
        return 0.0
    counts = Counter(block)
    n = len(block)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def ascii_strings(data, min_len=5):
    out = []
    cur = bytearray()
    start = 0
    for i, b in enumerate(data):
        if 32 <= b < 127:
            if not cur:
                start = i
            cur.append(b)
        else:
            if len(cur) >= min_len:
                out.append((start, cur.decode("ascii")))
            cur = bytearray()
    if len(cur) >= min_len:
        out.append((start, cur.decode("ascii")))
    return out


VERSION_RE = re.compile(r"V5R(\d{2})SP(\d+)HF(\d+)")


def main():
    rows = [r for r in csv.DictReader(MANIFEST.open())
            if r["magic_ok"] == "yes"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fields = ["sha256", "size_bytes", "split", "repo", "kind",
              "dword8_be", "dword8_le", "tail_delta", "word24_be",
              "entropy_head", "entropy_q25", "entropy_q75",
              "strings_8k", "cnext_version"]
    w = csv.DictWriter(OUT.open("w", newline=""), fieldnames=fields)
    w.writeheader()
    deltas, ratios = [], []
    word24 = Counter()
    ffff12 = Counter()
    files_with_version_strings = 0
    for r in rows:
        p = ROOT / r["local_path"]
        size = int(r["size_bytes"])
        with p.open("rb") as fh:
            head = fh.read(8192)
            fh.seek(size // 4)
            q25 = fh.read(4096)
            fh.seek((size * 3) // 4)
            q75 = fh.read(4096)
        dword8_be = int.from_bytes(head[8:12], "big")
        dword8_le = int.from_bytes(head[8:12], "little")
        word24_be = int.from_bytes(head[24:28], "big")
        ffff12[head[12:16] == b"\xff\xff\xff\xff"] += 1
        strings = ascii_strings(head)
        vmatches = VERSION_RE.findall(head.decode("latin-1"))
        vstrings = ["V5R{}SP{}HF{}".format(*m) for m in vmatches]
        if vstrings:
            files_with_version_strings += 1
        deltas.append(size - dword8_be)
        ratios.append(dword8_be / size if size else 0)
        w.writerow({
            "sha256": r["sha256"], "size_bytes": size, "split": r["split"],
            "repo": r["repo"], "kind": r["kind"],
            "dword8_be": dword8_be, "dword8_le": dword8_le,
            "tail_delta": size - dword8_be, "word24_be": word24_be,
            "entropy_head": round(entropy(head[:4096]), 3),
            "entropy_q25": round(entropy(q25), 3),
            "entropy_q75": round(entropy(q75), 3),
            "strings_8k": len(strings),
            "cnext_version": vstrings[0] if vstrings else "",
        })
    n = len(deltas)
    deltas.sort()
    ratios.sort()
    print("files scanned:", n)
    print("header[12:16] == ffffffff: {}/{} = {:.1%}".format(
        ffff12[True], n, ffff12[True] / n))
    print("tail_delta (size - dword8_be): min {} / p25 {} / median {} / p75 {} / max {}".format(
        deltas[0], deltas[n // 4], deltas[n // 2], deltas[3 * n // 4], deltas[-1]))
    print("dword8/size ratio: min {:.4f} / median {:.4f} / max {:.4f}".format(
        ratios[0], ratios[n // 2], ratios[-1]))
    print("files with version-looking strings in first 8KB: {}/{} ({:.1%})".format(
        files_with_version_strings, n, files_with_version_strings / n))
    print("wrote", OUT)


if __name__ == "__main__":
    sys.exit(main())
