#!/usr/bin/env python3
"""Stream-version census probe (W19, B9 — read-only).

Population: every ``kind=part`` ``magic_ok=yes`` manifest row (the
1,442-part part population; products carry no streams and no stores).
Per file (mmap, one file mapped at a time, deterministic sha256 order):

1. **store locator outcome** (the "stores the scanner does not open"
   census): the shipped probe order (``CATStdCont`` -> xdoclink ->
   seebody -> other-container) via the committed
   ``store.locate_store`` — spans located per family, and the
   ``malformed-store-header`` rejections (a ``V5_CFV2`` header present
   but failing the N2 + stage-3a laws — the fixed-magic skip surface).
2. **territories**: the ``CGMGeom`` and ``CATPrtCont`` block regions
   (B3 boundary rule) plus every located store body — the stream
   territory the scanner reads today, measured for what it carries
   besides the pinned decode families.
3. **version tags** (``stream_version.scan_version_tags``): the framed
   ``[u32le L]"N-0"`` generation strings per territory — GE-V7's
   ``2-0``/``2X-0`` census generalized to the whole ladder.
4. **compression** (``stream_version``): signature census per
   territory; fail-closed verification of (a) zlib pairs at a
   territory head (first 64 B), (b) length-framed zlib candidates — a
   pair whose preceding u32le/u32be names the remaining span exactly —
   (c) every gzip/bzip2/xz signature. A verification is a claim only
   under the eof law; everything else stays a signature count.
5. **writer tags** (``stream_version.block_writer_tag``): the block+112
   ``36 08`` tag per block family, the version-header drift feature
   (``FINJPL`` on the bulk-stream anchors).

Detector limits (declared, per the census rule): zlib candidates under
a CMF other than ``0x78``, and unframed self-terminating zlib streams
outside territory heads (no length prefix, head not scanned) are NOT
discriminated — a negative on the framed arms does not exclude them;
raw-LZMA ``5D 00 00`` is counted, never verified; lz4/zstd/snappy are
signature presence only.

Run::

    .venv/bin/python -I scripts/triage/stream_version_probe.py \
        [--corpus-root /home/alan/catpart-parser] [--limit N]

Writes ``docs/evidence/data/stream-version-files.csv`` (one row per
file x territory for tags/signatures, plus per-file locator/writer-tag
rows) and prints the per-version tallies. Read-only over the corpus.
"""

from __future__ import annotations

import argparse
import csv
import gc
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from catpart.geometry import store as store_mod  # noqa: E402
from catpart.geometry import stream_version as sv  # noqa: E402

OUT_FILES = os.path.join(ROOT, "docs", "evidence", "data", "stream-version-files.csv")
OUT_TAGS = os.path.join(ROOT, "docs", "evidence", "data", "stream-version-tags.csv")

CGM_NAME = "CGMGeom"
PRT_NAME = "CATPrtCont"
HEAD_WINDOW = 64
MIN_LEN_FRAMED = 64  # a length-framed candidate must span >= 64 B


def load_manifest(corpus_root):
    """The kind=part magic_ok=yes rows, deterministic sha256 order."""
    rows = []
    with open(os.path.join(corpus_root, "manifests", "corpus-manifest.csv"), newline="") as fh:
        for row in csv.DictReader(fh):
            if row["kind"] != "part" or row["magic_ok"] != "yes":
                continue
            rows.append(
                {
                    "sha16": row["sha256"][:16],
                    "sha256": row["sha256"],
                    "version": row["detected_version"] or "unknown",
                    "major": ("R" + row["detected_version"][3:5]) if row["detected_version"].startswith("V5R") else "unknown",
                    "path": os.path.join(corpus_root, row["local_path"]),
                }
            )
    rows.sort(key=lambda r: r["sha256"])
    return rows


def locate_spans(data):
    """The shipped locator walk; (spans, malformed_errors, family tallies).

    Mirrors ``export._export_store_data``'s probe order without the
    export: every ``locate_store`` result and every
    ``malformed-store-header`` rejection is recorded per family.
    """
    size = len(data)
    d8_outer = int.from_bytes(data[8:12], "big") if size >= 12 else 0
    blocks = store_mod.valid_blocks(data)
    by_name = defaultdict(list)
    for blk, nm in blocks:
        by_name[nm].append(blk)

    spans = []
    errors = Counter()
    order = [
        (store_mod.CONTAINER_STDCONT, by_name.get("CATStdCont", [])),
        (store_mod.CONTAINER_XDOCLINK, by_name.get("CATXDocLinkCont", [])),
        (store_mod.CONTAINER_SEEBODY, by_name.get("CATSeeBodyCont", [])),
        (
            store_mod.CONTAINER_OTHER,
            [b for b, nm in blocks if nm not in store_mod.NAMED_PROBE_CONTAINERS],
        ),
    ]
    for container, cands in order:
        for blk in cands:
            try:
                span = store_mod.locate_store(data, blk, blocks, d8_outer, container=container)
            except Exception as exc:  # noqa: BLE001 — the probe records every rejection
                errors[getattr(exc, "error_class", type(exc).__name__)] += 1
                continue
            if span is not None:
                spans.append(span)
    return blocks, spans, errors


def territory_bounds(data, blocks, spans):
    """(CGMGeom, CATPrtCont) regions by the B3 boundary rule."""
    size = len(data)
    d8_outer = int.from_bytes(data[8:12], "big") if size >= 12 else 0
    out = {}
    for name in (CGM_NAME, PRT_NAME):
        regions = []
        for blk, nm in blocks:
            if nm != name:
                continue
            regions.append((blk, store_mod.probe_region(data, blk, blocks, d8_outer)))
        out[name] = regions
    return out


#: Verification budget per territory (deterministic order): candidates
#: past the budget stay counted (``candidates``) but unverified — the
#: census reports the cap instead of silently dropping the scan.
VERIFY_BUDGET = 4096


def scan_territory(data, lo, hi):
    """Tags + signatures + verified streams for one [lo, hi) territory."""
    tags = sv.scan_version_tags(data, lo, hi)
    sigs = sv.scan_compression_signatures(data, lo, hi)
    verified = []
    cands = 0

    def attempt(pos, gzip=False):
        nonlocal cands
        cands += 1
        if len(verified) >= VERIFY_BUDGET:
            return
        v = sv.verify_deflate(data, pos, hi, gzip=gzip)
        if v is not None:
            verified.append(v)

    # (a) zlib pairs at the territory head
    for pos in range(lo, min(lo + HEAD_WINDOW, hi - 1)):
        if data[pos] == 0x78 and data[pos + 1] in sv.ZLIB_FLG_VALID:
            attempt(pos)

    # (b) length-framed zlib candidates: a valid pair whose preceding
    # u32le/u32be at [pos-4] or [pos-8] names the remaining span — the
    # "sub-stream with its own length prefix" law, in its two honest
    # readings (span starts at the pair, or right after the dword).
    i = data.find(b"\x78", lo)
    while i >= 0 and i + 1 < hi:
        if data[i + 1] in sv.ZLIB_FLG_VALID:
            rem = hi - i
            for p in (i - 4, i - 8):
                if p < lo:
                    continue
                dw = data[p : p + 4]
                if int.from_bytes(dw, "little") in (rem, rem - (i - p - 4)) or int.from_bytes(
                    dw, "big"
                ) in (rem, rem - (i - p - 4)):
                    attempt(i)
                    break
        i = data.find(b"\x78", i + 1)

    # (c) every gzip / bzip2 / xz signature
    i = data.find(sv.SIG_GZIP, lo, hi)
    while i >= 0:
        attempt(i, gzip=True)
        i = data.find(sv.SIG_GZIP, i + 1, hi)
    for sig, verifier in (
        (b"BZh", sv.verify_bz2),
        (sv.SIG_XZ, sv.verify_xz),
    ):
        i = data.find(sig, lo, hi)
        while i >= 0:
            cands += 1
            if len(verified) < VERIFY_BUDGET:
                v = verifier(data, i, hi)
                if v is not None:
                    verified.append(v)
            i = data.find(sig, i + 1, hi)

    return tags, sigs, verified, cands


def writer_tags(data, blocks):
    """Writer-tag census per family (the head-drift feature).

    Two columns per family: the pinned +112 law result and the
    found-in-[0,512) scan ``(offset, tag)`` histogram — a block whose
    writer tag moved is reported by its new offset, not as absent.
    """
    hist = defaultdict(Counter)
    for blk, nm in blocks:
        tag = sv.block_writer_tag(data, blk)
        hist[nm][("+112:" + tag) if tag is not None else "+112:<none>"] += 1
        hits = sv.block_writer_tag_scan(data, blk)
        if hits:
            for off, t in hits:
                hist[nm][f"scan@{off}:{t}"] += 1
        else:
            hist[nm]["scan:<none>"] += 1
    return {nm: dict(c) for nm, c in hist.items()}


def measure(row):
    """One file's census row (memory-safe: one mmap at a time)."""
    with open(row["path"], "rb") as fh:
        import mmap

        data = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        blocks, spans, errors = locate_spans(data)
        regions = territory_bounds(data, blocks, spans)

        per_territory = []
        verified: list = []  # bound even when a territory has zero regions
        for name, regs in (("cgm", regions[CGM_NAME]), ("prt", regions[PRT_NAME])):
            tot_tags: Counter = Counter()
            tot_sigs: Counter = Counter()
            n_verified = 0
            n_cands = 0
            span_bytes = 0
            for lo, hi in regs:
                span_bytes += hi - lo
                tags, sigs, verified, cands = scan_territory(data, lo, hi)
                tot_tags.update(tags)
                tot_sigs.update(sigs)
                n_verified += len(verified)
                n_cands += cands
            per_territory.append(
                {
                    "territory": name,
                    "regions": len(regs),
                    "bytes": span_bytes,
                    "tags": dict(tot_tags),
                    "signatures": {k: v for k, v in tot_sigs.items() if v},
                    "verified": n_verified,
                    "candidates": n_cands,
                    "verified_detail": [f"{v.codec}@{v.position}:out={v.output},mk={sum(v.markers.values())}" for v in verified],
                }
            )

        # store bodies: one territory per span (bounded to the located ones)
        st_tags: Counter = Counter()
        st_sigs: Counter = Counter()
        st_verified = 0
        st_cands = 0
        st_bytes = 0
        st_detail: list[str] = []
        for span in spans:
            lo, hi = span.body_lo, span.body_hi
            st_bytes += hi - lo
            tags, sigs, verified, cands = scan_territory(data, lo, hi)
            st_tags.update(tags)
            st_sigs.update(sigs)
            st_verified += len(verified)
            st_cands += cands
            st_detail.extend(
                f"{v.codec}@{v.position}:out={v.output},mk={sum(v.markers.values())}"
                for v in verified
            )
        per_territory.append(
            {
                "territory": "store",
                "regions": len(spans),
                "bytes": st_bytes,
                "tags": dict(st_tags),
                "signatures": {k: v for k, v in st_sigs.items() if v},
                "verified": st_verified,
                "candidates": st_cands,
                "verified_detail": st_detail,
            }
        )

        wtags = writer_tags(data, blocks)
        data.close()

    return {
        "sha16": row["sha16"],
        "major": row["major"],
        "version": row["version"],
        "spans": len(spans),
        "span_families": dict(Counter(s.container for s in spans)),
        "errors": dict(errors),
        "no_store": 1 if not spans else 0,
        "territories": per_territory,
        "writer_tags": wtags,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus-root", default="/home/alan/catpart-parser")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    rows = load_manifest(args.corpus_root)
    if args.limit:
        rows = rows[: args.limit]
    print(f"population: {len(rows)} part rows", flush=True)

    files_out = open(OUT_FILES, "w", newline="")
    w = csv.writer(files_out)
    w.writerow(
        [
            "sha16",
            "major",
            "version",
            "territory",
            "regions",
            "bytes",
            "tags_top",
            "tag_texts",
            "signatures_nonzero",
            "verified",
            "candidates",
            "verified_detail",
            "spans",
            "errors",
            "writer_tags",
        ]
    )
    tag_hist: dict[str, Counter] = defaultdict(Counter)  # text -> major -> count
    per_major = defaultdict(
        lambda: {"files": 0, "no_store": 0, "malformed": 0, "verified_files": 0, "cgm_files": 0}
    )

    for n, row in enumerate(rows, 1):
        try:
            m = measure(row)
        except Exception as exc:  # noqa: BLE001 — record and continue (read-only probe)
            print(f"  FAIL {row['sha16']}: {type(exc).__name__}: {exc}", flush=True)
            continue
        pm = per_major[m["major"]]
        pm["files"] += 1
        pm["no_store"] += m["no_store"]
        pm["malformed"] += 1 if "malformed-store-header" in m["errors"] else 0
        has_cgm = any(t["territory"] == "cgm" and t["bytes"] for t in m["territories"])
        pm["cgm_files"] += 1 if has_cgm else 0
        any_verified = any(t["verified"] for t in m["territories"])
        pm["verified_files"] += 1 if any_verified else 0

        for t in m["territories"]:
            w.writerow(
                [
                    m["sha16"],
                    m["major"],
                    m["version"],
                    t["territory"],
                    t["regions"],
                    t["bytes"],
                    ",".join(f"{k}:{v}" for k, v in sorted(t["tags"].items(), key=lambda kv: -kv[1])[:6]),
                    len(t["tags"]),
                    ",".join(f"{k}:{v}" for k, v in sorted(t["signatures"].items(), key=lambda kv: -kv[1])),
                    t["verified"],
                    t["candidates"],
                    ";".join(t["verified_detail"]),
                    m["spans"],
                    ";".join(f"{k}:{v}" for k, v in sorted(m["errors"].items())),
                    ";".join(
                        f"{nm}={dict(c)}"
                        for nm, c in sorted(m["writer_tags"].items())
                    ),
                ]
            )
            if t["territory"] == "cgm":
                for text, cnt in t["tags"].items():
                    tag_hist[text][m["major"]] += cnt
        if n % 100 == 0:
            files_out.flush()
            gc.collect()
            print(f"  {n}/{len(rows)}", flush=True)

    files_out.close()

    tags_out = open(OUT_TAGS, "w", newline="")
    tw = csv.writer(tags_out)
    tw.writerow(["tag_text", "major", "occurrences"])
    for text in sorted(tag_hist, key=lambda t: (len(t), t)):
        for major in sorted(tag_hist[text]):
            tw.writerow([text, major, tag_hist[text][major]])
    tags_out.close()

    print("\nper-major tallies (files, no-store, malformed-header, cgm-carrying, files with verified compressed stream):")
    for major in sorted(per_major):
        pm = per_major[major]
        print(
            f"  {major:8s} files={pm['files']:4d} no_store={pm['no_store']:3d} "
            f"malformed={pm['malformed']:3d} cgm={pm['cgm_files']:4d} verified={pm['verified_files']:3d}"
        )
    print(f"\ntag vocabulary: {len(tag_hist)} texts; per-version histogram -> {OUT_TAGS}")
    print(f"files rows -> {OUT_FILES}")


if __name__ == "__main__":
    main()
