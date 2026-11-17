#!/usr/bin/env python3
"""Corpus decode of the CGM exact-model container (BR5, ticket #57).

Runs the ``catpart.brep.cgm_nurbs`` decoders over the L2-pass
population (docs/evidence/data/stage15-identity-export-files.csv,
1,089 files) and lands the per-claim rates in
docs/evidence/data/br5-cgm-nurbs-claims.csv (the ticket's owned data
file; no per-file CSV — every prose figure derives from a claims row,
per the dispatch hard rules).

Measured per file (all read-only, mmap, deterministic):

- BR5-01 CGM container identity (``FINJPL  `` writer id, UTF-16LE
  ``Cont_<hex>`` name, vendor footer + release token) — the CGM side
  of TOP-01/CONT_CGMGEOM.
- BR5-02 object dictionary: validated object id-run records
  (``[u32le 0x0004000k][u32le x][u8 flag][u32le|u16le count]
  [ids][00 00]``) and marker-1 offset records (counted, not decoded).
- BR5-03 NURBS payload signatures (content-based: knot-array runs with
  the u32-alias + denormal guards, weight-1.0 runs) over the CGMGeom
  region and the whole file — the honest correction of BR1's
  CGM-presence NURBS label (the census labels GEOM_CURV_NURBS /
  GEOM_SURF_NURBS from ``cgm_present`` alone).
- BR5-04 TOP-01 structural carrier (``CATSeeBodyCont`` block + nested
  store root via the committed locator law).
- BR5-05 ``XX-0`` version-tag reference records inside the CGM region.

Outputs docs/evidence/data/br5-cgm-nurbs-claims.csv with per-release
and corpus-wide rows; prints the worked-example summary to stdout.
Read-only over the corpus; run with the worktree venv:

  export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
  .venv/bin/python -I scripts/triage/decode_brep_cgm_nurbs.py
"""

from __future__ import annotations

import argparse
import csv
import mmap
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
L2_STAGE15 = ROOT / "docs" / "evidence" / "data" / "stage15-identity-export-files.csv"
OUT_CLAIMS = ROOT / "docs" / "evidence" / "data" / "br5-cgm-nurbs-claims.csv"

sys.path.insert(0, str(ROOT / "src"))

from catpart.brep import cgm_nurbs  # noqa: E402

CLAIM_FIELDS = ["claim", "release", "observations", "passes", "rate", "detail"]

_XX0_TAG = re.compile(rb"[0-9][0-9X?]-0")


def load_population() -> list[dict]:
    l2_by_sha = {}
    with L2_STAGE15.open() as f:
        for r in csv.DictReader(f):
            l2_by_sha[r["sha256"]] = r
    rows = []
    with MANIFEST.open() as f:
        for r in csv.DictReader(f):
            if r["kind"] != "part":
                continue
            info = l2_by_sha.get(r["sha256"])
            if info and info["l2_status"] == "pass":
                rows.append(r)
    rows.sort(key=lambda r: r["sha256"])
    return rows


def release_of(detected_version: str) -> str:
    # "V5R19SP0HF0" -> "R19"; per-release rows need the release number,
    # not the common "V5R" prefix the census's [:3] bucket yields.
    v = detected_version
    return f"R{v[3:5]}" if v.startswith("V5R") and len(v) >= 5 else "unk"


def audit_file(path: Path) -> dict:
    with path.open("rb") as fh:
        mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            row: dict = {}
            regs = cgm_nurbs.valid_regions(mm)
            cgm = [(b, e) for b, nm, e in regs if nm == cgm_nurbs.CGM_BLOCK_NAME]
            row["cgm_present"] = bool(cgm)
            row["identity_full"] = False
            row["identity_writer"] = False
            row["identity_name"] = False
            row["identity_footer"] = False
            row["cont_name"] = ""
            row["release_token"] = ""
            row["writer_offset"] = -1
            row["has_runs"] = False
            row["objects"] = 0
            row["max_id"] = 0
            row["offset_markers"] = 0
            row["knot_runs"] = 0
            row["knot_sig"] = False
            row["weight_sig"] = False
            row["xx0_tags"] = 0
            row["carrier_seebody"] = False
            row["carrier_root"] = ""
            if cgm:
                blk, end = cgm[0]
                ident = cgm_nurbs.parse_identity(mm, blk, end)
                row["identity_writer"] = ident.writer_offset >= 0
                row["identity_name"] = bool(ident.cont_name)
                row["identity_footer"] = (
                    ident.vendor_offset >= 0 and bool(ident.release)
                )
                row["identity_full"] = ident.ok()
                row["cont_name"] = ident.cont_name
                row["release_token"] = ident.release
                row["writer_offset"] = ident.writer_offset
                dscan = cgm_nurbs.scan_dictionary(mm, blk, end)
                row["has_runs"] = bool(dscan.runs)
                row["objects"] = dscan.objects
                row["max_id"] = dscan.max_id
                row["offset_markers"] = dscan.offset_markers
                sig = cgm_nurbs.nurbs_signatures(mm, blk, end)
                row["knot_runs"] = len(sig.knot_runs)
                row["knot_sig"] = bool(sig.knot_runs)
                row["weight_sig"] = bool(sig.weight_runs)
                row["xx0_tags"] = len(_XX0_TAG.findall(mm, blk, end))
            carrier = cgm_nurbs.top01_carrier(mm)
            row["carrier_seebody"] = carrier.seebody_block
            row["carrier_root"] = carrier.store_root or ""
            return row
        finally:
            mm.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus-root",
        default=str(ROOT),
        help="checkout holding the gitignored corpus/ binaries (default: this "
        "checkout; pass the main checkout from a worktree)",
    )
    args = parser.parse_args()
    corpus_root = Path(args.corpus_root)
    population = load_population()
    print(f"L2-pass population: {len(population)} files (corpus root {corpus_root})")
    per_release: dict[str, list[dict]] = defaultdict(list)
    n_total = 0
    objects_total = 0
    offset_markers_total = 0
    xx0_total = 0
    knot_total = 0
    max_objects_file = ("", 0)
    worked = []
    for r in population:
        path = corpus_root / r["local_path"]
        row = audit_file(path)
        rel = release_of(r["detected_version"])
        row["release"] = rel
        per_release[rel].append(row)
        per_release["all"].append(row)
        n_total += 1
        objects_total += row["objects"]
        offset_markers_total += row["offset_markers"]
        xx0_total += row["xx0_tags"]
        knot_total += row["knot_runs"]
        if row["objects"] > max_objects_file[1]:
            max_objects_file = (r["sha256"][:16], row["objects"])
        if len(worked) < 5 and row["cgm_present"] and row["has_runs"]:
            worked.append((r["sha256"][:16], rel, row))

    def emit(claims: list[list], claim: str, key, detail: str = "") -> None:
        rows = per_release["all"]
        obs = len(rows)
        passes = sum(1 for x in rows if (x[key] if key else False))
        rate = round(passes / obs, 4) if obs else 0.0
        claims.append([claim, "all", obs, passes, rate, detail])

    claims: list[list] = []

    def emit_rel(claims: list[list], claim: str, key, detail: str = "") -> None:
        for rel in sorted(per_release):
            if rel == "all":
                continue
            rows = per_release[rel]
            obs = len(rows)
            passes = sum(1 for x in rows if (x[key] if key else False))
            rate = round(passes / obs, 4) if obs else 0.0
            claims.append([claim, rel, obs, passes, rate, detail])

    emit(claims, "BR5-01a_cgm_identity_full", "identity_full",
         "FINJPL writer id + Cont_ name + vendor/release footer")
    emit_rel(claims, "BR5-01a_cgm_identity_full", "identity_full")
    emit(claims, "BR5-01b_cgm_identity_writer", "identity_writer")
    emit(claims, "BR5-01c_cgm_identity_name", "identity_name")
    emit(claims, "BR5-01d_cgm_identity_footer", "identity_footer")
    emit(claims, "BR5-02a_dictionary_idruns", "has_runs")
    emit_rel(claims, "BR5-02a_dictionary_idruns", "has_runs")
    claims.append(["BR5-02b_objects_total", "all", n_total,
                   sum(1 for x in per_release["all"] if x["has_runs"]),
                   round(sum(1 for x in per_release["all"] if x["has_runs"]) / max(n_total, 1), 4),
                   f"total_objects={objects_total};max_objects_file={max_objects_file[0]}:{max_objects_file[1]}"])
    claims.append(["BR5-02c_offset_markers_total", "all", n_total, n_total, 1.0,
                   f"marker1_records={offset_markers_total}"])
    emit(claims, "BR5-03a_nurbs_knot_sig_cgm_region", "knot_sig",
         "content-based knot-array signature (alias-guarded)")
    emit_rel(claims, "BR5-03a_nurbs_knot_sig_cgm_region", "knot_sig")
    emit(claims, "BR5-03b_nurbs_weight_sig_cgm_region", "weight_sig",
         ">=4 consecutive exact f64 1.0 inside the CGM region")
    claims.append(["BR5-03c_nurbs_content_rate_vs_census", "all", n_total,
                   sum(1 for x in per_release["all"]
                       if x["knot_sig"] or x["weight_sig"]),
                   round(sum(1 for x in per_release["all"]
                             if x["knot_sig"] or x["weight_sig"]) / max(n_total, 1), 4),
                   "census BR1 labels 100% from cgm_present alone; this is the content rate"])
    emit(claims, "BR5-04a_top01_seebody_block", "carrier_seebody")
    emit(claims, "BR5-04b_top01_store_root", "carrier_root",
         "nested store root via the committed locator probe order")
    emit(claims, "BR5-05_xx0_reference_tags", "xx0_tags")
    claims.append(["BR5-05b_xx0_tags_total", "all", n_total, n_total, 1.0,
                   f"tags={xx0_total};knot_runs={knot_total}"])
    claims.append(["BR5-06a_top02_lump_ceiling", "all", n_total, 0, 0.0,
                   "no committed detector discriminates lump records; carrier-only"])
    claims.append(["BR5-06b_crv06_srf08_nurbs_ceiling", "all", n_total, 0, 0.0,
                   "payload framing parked; 0 knot/weight signatures corpus-wide"])

    with OUT_CLAIMS.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(CLAIM_FIELDS)
        w.writerows(claims)
    print(f"Wrote {OUT_CLAIMS} ({len(claims)} rows)")

    print("\nWorked examples (first five runnable dictionaries):")
    for sha, rel, row in worked:
        print(f"  {sha} {rel}: writer=+{row['writer_offset']} "
              f"name={row['cont_name']!r} release={row['release_token']!r} "
              f"objects={row['objects']} max_id={row['max_id']} "
              f"off_markers={row['offset_markers']} root={row['carrier_root']}")
    print(f"\nCorpus totals: objects={objects_total} marker1={offset_markers_total} "
          f"xx0_tags={xx0_total} knot_runs={knot_total} "
          f"max_objects={max_objects_file[0]}:{max_objects_file[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
