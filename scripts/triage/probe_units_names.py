#!/usr/bin/env python3
"""Bounded probe: model unit system and part/product display names (ticket #25).

Phase A of C3.  Question (B3 evidence note, open question 1): where do the
model unit system (length/mass/angle) and the displayed part/product name
live, beyond the save-time file name the CATIA identity block stores?
Territories searched, per the ticket's scope: the two decoded ones only -
(1) the container payload regions (B3 block/region model) and (2) the
OSMX/stream territory, i.e. the main file area outside those regions plus
the CB0001 tail region (>= header dword8).  Nothing else is opened.

Method: framed-pattern scan (B3 framing families) for a fixed token
vocabulary over a version-scoped sample (R15-R24, up to 3 files per
detected_version evenly spaced by size, plus the 10 B3 step-(a) files
force-included).  Every ASCII/UTF-16 printable run of >= 2 chars is
classified by framing (B3 classify_*); only framed runs are matched
against the vocabulary, so bare substrings inside binary noise never
count.  Each hit is classified by territory: region / stream / tail.

Token families (exact match on the framed run):

  unit          candidate unit-system tokens: mm cm km um in ft kg mg deg
                rad grd MILLIMETER MILLIMETRE CENTIMETER CENTIMETRE INCH
                FOOT YARD MILE KILOGRAM GRAM TON DEGREE RADIAN Unit Units
                Unite Unites Magnitude
  model-content spec-tree parameter/attribute tokens seen on CAA-sample
                parts (Volume Density Mass Length Area Angle VOLUME MASS
                LENGTH ANGLE) - context rows, explicitly NOT counted as
                unit-system evidence
  name          candidate display-name property tokens: PartNumber
                "Part Number" Nomenclature Description Definition Revision
                InstanceName Part1 Product1 PartBody

Per-file and per-claim rates (claims, per release, in the claims CSV):

  D1  exactly one CATIA-named storage block per file (the identity block;
      B3: 114/114)
  D2  the identity block's name2 parses under the fixed model
      ``a0 02 00 00 00 00 34 <len> <ascii> <0x9f|type-tag>`` (structural
      walk succeeds; B3's 37/114 presence rate is D2's *presence* count)
  D3  document_name, when present, equals the manifest basename
  D4  document_name, when present, ends with .CATPart/.CATProduct
  D5  the manifest basename occurs as a framed string OUTSIDE the identity
      block region (expected negative; B3 searched inside regions only)
  U1  the file carries >= 1 framed unit-family token anywhere (expected
      negative for a unit-system claim; the drafting "Pixel"/"mm" store of
      B3 must show up as the documented exception)
  U2  the file carries >= 1 framed unit-family token in stream/tail
      territory on files with no drafting namespace (the model-unit
      candidate; expected negative)
  P1  the file carries >= 1 framed name-family token anywhere (expected
      negative for a display-name claim)

Read-only.  Run:

  .venv/bin/python -I scripts/triage/probe_units_names.py [--sample N]
      [--include-sha16 HEX,HEX,...] [--out-dir DIR]

Outputs (default docs/evidence/data/):

  units-names-probe-files.csv   one row per file: identity-block facts,
                                document_name, per-family per-territory
                                hit counts
  units-names-probe-hits.csv    one row per framed token hit (capped per
                                file)
  units-names-probe-claims.csv  per-claim, per-release rates
"""
import argparse
import csv
import mmap
import re
import sys
from bisect import bisect_right
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"

sys.path.insert(0, str(ROOT / "scripts" / "triage"))
from decode_container_payloads import (  # noqa: E402
    TAG34_FOLLOW,
    block_name,
    classify_ascii,
    classify_utf16,
    find_all,
    pick_sample,
    release_of,
)

STORAGE_WORD = b"CATStorageProperty"
BLOCK_TAG = b"\x34\x12"
OSMX = b"OSMX"
CB0001 = b"CATIA_V5 CB0001\x00"
IDENTITY_NAME = b"CATIA"

ASCII_RE = re.compile(rb"[\x20-\x7e]{2,}")
UTF16_RE = re.compile(rb"(?:[\x20-\x7e]\x00){2,}")

UNIT_TOKENS = (
    "mm", "cm", "km", "um", "in", "ft", "kg", "mg", "deg", "rad", "grd",
    "MILLIMETER", "MILLIMETRE", "CENTIMETER", "CENTIMETRE", "INCH", "FOOT",
    "YARD", "MILE", "KILOGRAM", "GRAM", "TON", "DEGREE", "RADIAN",
    "Unit", "Units", "Unite", "Unites", "Magnitude",
)
MODEL_CONTENT_TOKENS = (
    "Volume", "Density", "Mass", "Length", "Area", "Angle",
    "VOLUME", "MASS", "LENGTH", "ANGLE",
)
NAME_TOKENS = (
    "PartNumber", "Part Number", "Nomenclature", "Description", "Definition",
    "Revision", "InstanceName", "Part1", "Product1", "PartBody",
)
FAMILY = {}
for _t in UNIT_TOKENS:
    FAMILY[_t] = "unit"
for _t in MODEL_CONTENT_TOKENS:
    FAMILY[_t] = "model-content"
for _t in NAME_TOKENS:
    FAMILY[_t] = "name"
DRAFTING_NS = "drafting:"

HIT_CAP = 500  # per file

FILE_FIELDS = [
    "sha256", "detected_version", "release", "kind", "size_bytes",
    "blocks", "catia_blocks", "identity_model_ok",
    "doc_name_present", "doc_name", "doc_name_eq_basename",
    "doc_name_has_extension",
    "unit_hits", "unit_hits_region", "unit_hits_stream", "unit_hits_tail",
    "model_hits", "name_hits", "has_drafting_ns", "hits_overflow",
]
HIT_FIELDS = [
    "sha256", "detected_version", "release", "kind", "territory",
    "family", "framing", "text_kind", "offset", "n_chars", "text",
]
CLAIM_FIELDS = ["claim", "release", "files", "observations", "passes",
                "rate", "note"]


def storage_blocks(mm):
    """Start offsets of the storage blocks (B3 model, unbounded)."""
    occs = find_all(mm, STORAGE_WORD)
    return [o - 2 if mm[o - 2:o] == BLOCK_TAG else o for o in occs]


def regions_of(mm, block_starts, size, dword8):
    """(start, end) payload regions per the B3 nearest-boundary rule."""
    osmx_all = find_all(mm, OSMX)
    cb_all = find_all(mm, CB0001)
    out = []
    for k, blk in enumerate(block_starts):
        nxt = block_starts[k + 1] if k + 1 < len(block_starts) else size
        cands = [(size, "EOF"), (dword8, "dword8"), (nxt, "nxtblk")]
        i = bisect_right(osmx_all, blk)
        if i < len(osmx_all):
            cands.append((osmx_all[i], "OSMX"))
        i = bisect_right(cb_all, blk)
        if i < len(cb_all):
            cands.append((cb_all[i], "CB0001"))
        end, _ = min(cands)
        out.append((blk, min(end, size)))
    return out


def identity_name2(mm, blk):
    """Walk the identity block's name2 under the fixed model.

    Returns (ok, name2_text) - ok is False when the structural walk fails
    (framing violation); name2_text is '' when the name2 field is empty.
    """
    bi = mm.find(b"CATUnicodeString", blk, blk + 64)
    if bi < 0:
        return False, ""
    if (mm[bi + 16:bi + 22] != b"\xa0\x02\x00\x00\x00\x00"
            or mm[bi + 22] != 0x34):
        return False, ""
    ln1 = mm[bi + 23]
    p = bi + 24 + ln1
    if p >= mm.size() or mm[p] not in TAG34_FOLLOW:
        return False, ""
    if (mm[p + 1:p + 7] != b"\xa0\x02\x00\x00\x00\x00"
            or mm[p + 7] != 0x34):
        return False, ""
    ln2 = mm[p + 8]
    end = p + 9 + ln2
    if end >= mm.size() or mm[end] not in TAG34_FOLLOW:
        return False, ""
    text = bytes(mm[p + 9:end])
    if ln2 == 0:
        return True, ""
    try:
        decoded = text.decode("ascii")
    except UnicodeDecodeError:
        return False, ""
    if not decoded.isprintable():
        return False, ""
    return True, decoded


def scan_file(path, kind, basename):
    """Scan one file; returns (file_row, hit_rows)."""
    file_row = {
        "blocks": 0, "catia_blocks": 0, "identity_model_ok": "",
        "doc_name_present": "", "doc_name": "",
        "doc_name_eq_basename": "", "doc_name_has_extension": "",
        "unit_hits": 0, "unit_hits_region": 0, "unit_hits_stream": 0,
        "unit_hits_tail": 0, "model_hits": 0, "name_hits": 0,
        "has_drafting_ns": False, "hits_overflow": False,
    }
    hit_rows = []
    with path.open("rb") as fh:
        mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            size = mm.size()
            dword8 = int.from_bytes(mm[8:12], "big") if size >= 12 else 0
            blocks = storage_blocks(mm)
            regions = regions_of(mm, blocks, size, dword8)
            file_row["blocks"] = len(blocks)

            def territory(off):
                for b, e in regions:
                    if b <= off < e:
                        return "region"
                return "tail" if off >= dword8 else "stream"

            # identity block facts (D1/D2/D3/D4)
            catia = []
            for blk in blocks:
                name = block_name(mm, blk)[0]
                if name == "CATIA":
                    catia.append(blk)
            file_row["catia_blocks"] = len(catia)
            doc_name = None
            if len(catia) == 1:
                ok, name2 = identity_name2(mm, catia[0])
                file_row["identity_model_ok"] = ok
                if ok:
                    doc_name = name2 or None
            file_row["doc_name_present"] = doc_name is not None
            file_row["doc_name"] = doc_name or ""
            if doc_name:
                file_row["doc_name_eq_basename"] = doc_name == basename
                file_row["doc_name_has_extension"] = doc_name.lower().endswith(
                    (".catpart", ".catproduct"))

            # framed token scan, whole file, two text kinds
            n_hits = 0
            for rex, is16 in ((ASCII_RE, False), (UTF16_RE, True)):
                for m in rex.finditer(mm):
                    off, raw = m.start(), m.group()
                    n = len(raw) // 2 if is16 else len(raw)
                    if n > 64:
                        continue
                    if is16:
                        framing, _ = classify_utf16(mm, off, n)
                        if framing == "other":
                            continue
                        text = raw.decode("utf-16-le", "replace")
                    else:
                        framing, _, _, _ = classify_ascii(mm, off, n)
                        if framing == "other":
                            continue
                        text = raw.decode("ascii", "replace")
                    fam = FAMILY.get(text)
                    if fam is None:
                        continue
                    terr = territory(off)
                    if fam == "unit":
                        file_row["unit_hits"] += 1
                        file_row["unit_hits_" + terr] += 1
                    elif fam == "model-content":
                        file_row["model_hits"] += 1
                    else:
                        file_row["name_hits"] += 1
                    if n_hits < HIT_CAP:
                        n_hits += 1
                        hit_rows.append({
                            "territory": terr, "family": fam,
                            "framing": framing,
                            "text_kind": "utf16" if is16 else "ascii",
                            "offset": off, "n_chars": n, "text": text[:60],
                        })
                    else:
                        file_row["hits_overflow"] = True
            file_row["has_drafting_ns"] = mm.find(
                DRAFTING_NS.encode()) >= 0
        finally:
            mm.close()
    return file_row, hit_rows


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Bounded probe: units and names territories (ticket #25)")
    ap.add_argument("--sample", type=int, default=3, metavar="N",
                    help="files per detected_version, R15-R24 (default 3)")
    ap.add_argument("--include-sha16", default="",
                    metavar="HEX,HEX,...", help="force-include by sha prefix")
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    args = ap.parse_args(argv)

    manifest = [r for r in csv.DictReader(MANIFEST.open())
                if r["magic_ok"] == "yes"]
    r1524 = []
    for r in manifest:
        m = re.match(r"V5R(\d+)", r["detected_version"] or "")
        if m and 15 <= int(m.group(1)) <= 24:
            r1524.append(r)
    sample = pick_sample(r1524, args.sample)
    by_prefix = {r["sha256"][:16]: r for r in manifest}
    for pref in [p for p in args.include_sha16.split(",") if p]:
        if pref in by_prefix and by_prefix[pref] not in sample:
            sample.append(by_prefix[pref])
    seen = set()
    selected = [r for r in sample
                if not (r["sha256"] in seen or seen.add(r["sha256"]))]

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    file_rows, hit_rows = [], []
    per_claim = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    rels = set()
    for r in selected:
        p = ROOT / r["local_path"]
        frow, hits = scan_file(p, r.get("kind", ""), Path(r["path"]).name)
        sha16 = (r["sha256"] or p.name)[:16]
        ver = r.get("detected_version", "")
        rel = release_of(ver)
        rels.add(rel)
        frow.update({"sha256": sha16, "detected_version": ver, "release": rel,
                     "kind": r.get("kind", ""),
                     "size_bytes": r.get("size_bytes", "")})
        file_rows.append(frow)
        for h in hits:
            h.update({"sha256": sha16, "detected_version": ver,
                      "release": rel, "kind": r.get("kind", "")})
        hit_rows.extend(hits)

        # claims: per release, files as denominator
        def tally(claim, passed):
            per_claim[claim][rel][0] += 1
            per_claim[claim][rel][1] += int(passed)

        tally("D1", frow["catia_blocks"] == 1)
        if frow["catia_blocks"] == 1:
            tally("D2", frow["identity_model_ok"] is True)
            if frow["identity_model_ok"] is True and frow["doc_name_present"]:
                tally("D3", frow["doc_name_eq_basename"] is True)
                tally("D4", frow["doc_name_has_extension"] is True)
        tally("U1", frow["unit_hits"] > 0)
        tally("U2", (frow["unit_hits_stream"] + frow["unit_hits_tail"]) > 0
              and not frow["has_drafting_ns"])
        tally("P1", frow["name_hits"] > 0)

    # D5: basename as a framed string outside the identity block region.
    # Second pass over the selected files (bounded: framed runs equal to
    # the basename only); every selected file is a denominator.
    for r, frow in zip(selected, file_rows):
        basename = Path(r["path"]).name.encode()
        p = ROOT / r["local_path"]
        with p.open("rb") as fh:
            mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                size = mm.size()
                dword8 = int.from_bytes(mm[8:12], "big") if size >= 12 else 0
                blocks = storage_blocks(mm)
                regions = regions_of(mm, blocks, size, dword8)
                outside = False
                i = mm.find(basename)
                while i >= 0:
                    if not any(b <= i < e for b, e in regions):
                        # framed? any length-prefix equal to the basename
                        pre4 = mm[i - 4:i]
                        pre2 = mm[i - 2:i]
                        framed = (
                            (len(pre4) == 4
                             and int.from_bytes(pre4, "little") == len(basename))
                            or (len(pre2) == 2
                                and int.from_bytes(pre2, "little") == len(basename))
                            or (len(pre2) == 2 and pre2[0] == 0x34
                                and pre2[1] == len(basename)))
                        if framed:
                            outside = True
                            break
                    i = mm.find(basename, i + 1)
            finally:
                mm.close()
        rel = frow["release"]
        per_claim["D5"][rel][0] += 1
        per_claim["D5"][rel][1] += int(outside)

    with (out_dir / "units-names-probe-files.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FILE_FIELDS)
        w.writeheader()
        w.writerows(file_rows)
    with (out_dir / "units-names-probe-hits.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=HIT_FIELDS)
        w.writeheader()
        w.writerows(hit_rows)
    with (out_dir / "units-names-probe-claims.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CLAIM_FIELDS)
        w.writeheader()
        for claim in ("D1", "D2", "D3", "D4", "D5", "U1", "U2", "P1"):
            for rel in sorted(rels):
                obs, p_ = per_claim[claim][rel]
                if not obs:
                    continue
                w.writerow({
                    "claim": claim, "release": rel, "files": "",
                    "observations": obs, "passes": p_,
                    "rate": "%.4f" % (p_ / obs) if obs else "",
                    "note": ""})

    print("files scanned:", len(selected))
    agg = defaultdict(lambda: [0, 0])
    for claim in per_claim:
        for rel in per_claim[claim]:
            obs, p_ = per_claim[claim][rel]
            agg[claim][0] += obs
            agg[claim][1] += p_
    for claim in ("D1", "D2", "D3", "D4", "D5", "U1", "U2", "P1"):
        obs, p_ = agg[claim]
        print("  %-3s %d/%d = %s" % (claim, p_, obs,
              ("%.4f" % (p_ / obs)) if obs else "n/a"))
    n_present = sum(1 for f in file_rows if f["doc_name_present"])
    print("document_name present:", n_present, "/", len(file_rows))
    print("unit-family hits by territory:",
          {t: sum(f["unit_hits_" + t] for f in file_rows)
           for t in ("region", "stream", "tail")})
    print("model-content hits:", sum(f["model_hits"] for f in file_rows),
          " name-family hits:", sum(f["name_hits"] for f in file_rows))
    print("wrote", out_dir / "units-names-probe-files.csv")
    print("wrote", out_dir / "units-names-probe-hits.csv")
    print("wrote", out_dir / "units-names-probe-claims.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
