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
  ``Cont_<hex>`` name + its length unit, vendor footer + release token)
  — the CGM side of TOP-01/CONT_CGMGEOM.
- BR5-02 object dictionary: validated object id-run records
  (``[u32le 0x0004000k][u32le x][u8 flag][u32le|u16le count]
  [ids][00 00]``) and marker-1 records (counted when the id-list parse
  fails).  ``id_refs`` counts id-list positions, not distinct objects.
- BR5-03 NURBS payload signatures (content-based: knot-array runs with
  the u32-alias + denormal guards, weight-1.0 runs) over the CGMGeom
  region — the honest correction of BR1's CGM-presence NURBS label
  (the census labels GEOM_CURV_NURBS / GEOM_SURF_NURBS from
  ``cgm_present`` alone).
- BR5-04 TOP-01 structural carrier (``CATSeeBodyCont`` block + nested
  store root via the committed locator law).
- BR5-05 ``XX-0`` version-tag reference records inside the CGM region.
- BR5-07 bulk window: the record-stream region immediately preceding
  the CGMGeom block of the largest part (``17930bab``, the dental
  mold): window span, zlib magic-pair counts (window and full region),
  zlib stream trials, knot/weight signatures (window) and the
  whole-file weight scan.

Outputs docs/evidence/data/br5-cgm-nurbs-claims.csv with per-release
and corpus-wide rows plus the numeric ceiling rows; prints the
worked-example summary to stdout.  Read-only over the corpus; run with
the worktree venv:

  export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
  .venv/bin/python -I scripts/triage/decode_brep_cgm_nurbs.py

The ceiling rows carry their byte arithmetic in ``detail``
(``ceiling:`` prefix); their ``observations``/``passes`` count the
population files the ceiling is defined on, not detections.  Rows with
``observations=0`` are the no-detector rows (no rate exists).
"""

from __future__ import annotations

import argparse
import csv
import mmap
import re
import sys
import zlib
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
L2_STAGE15 = ROOT / "docs" / "evidence" / "data" / "stage15-identity-export-files.csv"
OUT_CLAIMS = ROOT / "docs" / "evidence" / "data" / "br5-cgm-nurbs-claims.csv"

sys.path.insert(0, str(ROOT / "src"))

from catpart.brep import cgm_nurbs  # noqa: E402

CLAIM_FIELDS = ["claim", "release", "observations", "passes", "rate", "label", "detail"]

_XX0_TAG = re.compile(rb"[0-9][0-9X?]-0")

#: Smallest remaining span in which the u32 count of a u16 record can
#: fit and mask it (count 5, first id 3: 4 * 196_613 + 15).  No CGM
#: region below this can hide a u16 record from the gated policy.
U16_GATE_SPAN = 4 * ((3 << 16) | 5) + 15

#: zlib magic pairs (RFC 1950 CMF/FLG combinations with CM=8).
_ZLIB_MAGICS = (b"\x78\x01", b"\x78\x9c", b"\x78\xda", b"\x78\x5e")
_ZLIB_TRIAL_BYTES = 8192


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
            row["cont_name_offset"] = -1
            row["cont_name_prefix_ok"] = False
            row["release_token"] = ""
            row["writer_offset"] = -1
            row["region_bytes"] = 0
            row["has_runs"] = False
            row["has_u16"] = False
            row["run_records"] = 0
            row["id_refs"] = 0
            row["id_refs_local"] = 0
            row["framed_bytes"] = 0
            row["max_run"] = 0
            row["max_id"] = 0
            row["marker1_records"] = 0
            row["knot_runs"] = 0
            row["knot_sig"] = False
            row["weight_sig"] = False
            row["xx0_tags"] = 0
            row["carrier_seebody"] = False
            row["carrier_root"] = ""
            if cgm:
                blk, end = cgm[0]
                row["region_bytes"] = end - blk
                ident = cgm_nurbs.parse_identity(mm, blk, end)
                row["identity_writer"] = ident.writer_offset >= 0
                row["identity_name"] = bool(ident.cont_name)
                row["identity_footer"] = (
                    ident.vendor_offset >= 0 and bool(ident.release)
                )
                row["identity_full"] = ident.ok()
                row["cont_name"] = ident.cont_name
                row["cont_name_offset"] = ident.cont_name_offset
                row["cont_name_prefix_ok"] = ident.cont_name_prefix == (
                    2 * len(ident.cont_name) + 2
                )
                row["release_token"] = ident.release
                row["writer_offset"] = ident.writer_offset
                dscan = cgm_nurbs.scan_dictionary(mm, blk, end)
                local = cgm_nurbs.scan_dictionary(mm, blk, end, width_policy="local")
                row["has_runs"] = bool(dscan.runs)
                row["has_u16"] = any(r.width == 16 for r in dscan.runs)
                row["run_records"] = len(dscan.runs)
                row["id_refs"] = dscan.id_refs
                row["id_refs_local"] = local.id_refs
                row["framed_bytes"] = dscan.framed_bytes
                row["max_run"] = max((len(r.ids) for r in dscan.runs), default=0)
                row["max_id"] = dscan.max_id
                row["marker1_records"] = dscan.marker1_records
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


def _count_magic(mm, lo: int, hi: int, magic: bytes) -> int:
    n = 0
    pos = lo
    while True:
        i = mm.find(magic, pos, hi)
        if i < 0:
            return n
        n += 1
        pos = i + 1


def bulk_window(path: Path, mib: int) -> dict:
    """Measure the record-stream region before the CGM block (BR5-07)."""
    with path.open("rb") as fh:
        mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            regs = cgm_nurbs.valid_regions(mm)
            cgm_at = [b for b, nm, _ in regs if nm == cgm_nurbs.CGM_BLOCK_NAME]
            if not cgm_at:
                raise SystemExit(f"{path}: no CGMGeom block")
            blk = cgm_at[0]
            # The bulk is the block region that ends at the CGM block.
            bulk = [(b, e) for b, _, e in regs if e == blk]
            if not bulk:
                raise SystemExit(f"{path}: no block precedes the CGMGeom block")
            bulk_lo, bulk_hi = bulk[0]
            win_hi = min(bulk_lo + mib * 1024 * 1024, bulk_hi)
            window = {"lo": bulk_lo, "hi": win_hi, "bytes": win_hi - bulk_lo,
                      "bulk_lo": bulk_lo, "bulk_hi": bulk_hi,
                      "bulk_bytes": bulk_hi - bulk_lo}
            window["magic_window"] = {
                m: _count_magic(mm, bulk_lo, win_hi, m) for m in _ZLIB_MAGICS
            }
            window["magic_bulk"] = {
                m: _count_magic(mm, bulk_lo, bulk_hi, m) for m in _ZLIB_MAGICS
            }
            ok = attempts = 0
            for magic in _ZLIB_MAGICS:
                pos = bulk_lo
                while True:
                    i = mm.find(magic, pos, bulk_hi)
                    if i < 0:
                        break
                    attempts += 1
                    try:
                        out = zlib.decompressobj().decompress(
                            bytes(mm[i: i + _ZLIB_TRIAL_BYTES]), 65536
                        )
                        if out:
                            ok += 1
                    except zlib.error:
                        pass
                    pos = i + 1
            window["zlib_ok"] = ok
            window["zlib_attempts"] = attempts
            sig = cgm_nurbs.nurbs_signatures(mm, bulk_lo, win_hi)
            window["knot_runs"] = len(sig.knot_runs)
            window["weight_runs"] = len(sig.weight_runs)
            whole = cgm_nurbs.nurbs_signatures(mm, 0, len(mm))
            window["wholefile_bytes"] = len(mm)
            window["wholefile_weight_runs"] = len(whole.weight_runs)
            return window
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
    parser.add_argument(
        "--bulk-sha16",
        default="17930babf0fd01a8",
        help="sha256 prefix of the part whose pre-CGM region the bulk "
        "window measures (default: 17930bab, the largest L2-pass part)",
    )
    parser.add_argument(
        "--bulk-mib",
        type=int,
        default=96,
        help="bulk window size in MiB (default: 96)",
    )
    args = parser.parse_args()
    corpus_root = Path(args.corpus_root)
    population = load_population()
    print(f"L2-pass population: {len(population)} files (corpus root {corpus_root})")
    per_release: dict[str, list[dict]] = defaultdict(list)
    n_total = 0
    region_total = 0
    framed_total = 0
    run_records_total = 0
    id_refs_total = 0
    id_refs_local_total = 0
    marker1_total = 0
    xx0_total = 0
    xx0_files: list[tuple[str, int]] = []
    knot_total = 0
    name_offsets: Counter = Counter()
    writer_offsets: Counter = Counter()
    prefix_ok = 0
    releases: Counter = Counter()
    big_regions = 0
    big_region_bytes = 0
    max_id_refs_file = ("", 0)
    max_run_file = ("", 0)
    worked = []
    for r in population:
        path = corpus_root / r["local_path"]
        row = audit_file(path)
        rel = release_of(r["detected_version"])
        row["release"] = rel
        per_release[rel].append(row)
        per_release["all"].append(row)
        n_total += 1
        region_total += row["region_bytes"]
        framed_total += row["framed_bytes"]
        run_records_total += row["run_records"]
        id_refs_total += row["id_refs"]
        id_refs_local_total += row["id_refs_local"]
        marker1_total += row["marker1_records"]
        xx0_total += row["xx0_tags"]
        if row["xx0_tags"]:
            xx0_files.append((r["sha256"][:16], row["xx0_tags"]))
        knot_total += row["knot_runs"]
        writer_offsets[row["writer_offset"]] += 1
        if row["cont_name_offset"] >= 0:
            name_offsets[row["cont_name_offset"]] += 1
        prefix_ok += 1 if row["cont_name_prefix_ok"] else 0
        releases[row["release_token"]] += 1
        if row["region_bytes"] > U16_GATE_SPAN:
            big_regions += 1
            big_region_bytes += row["region_bytes"]
        if row["id_refs"] > max_id_refs_file[1]:
            max_id_refs_file = (r["sha256"][:16], row["id_refs"])
        if row["max_run"] > max_run_file[1]:
            max_run_file = (r["sha256"][:16], row["max_run"])
        if len(worked) < 5 and row["cgm_present"] and row["has_runs"]:
            worked.append((r["sha256"][:16], rel, row))

    def hist(counter: Counter, limit: int = 12) -> str:
        items = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
        return ",".join(f"{k}:{v}" for k, v in items[:limit])

    claims: list[list[str]] = []

    def emit(claim: str, key, label: str = "fact", detail: str = "") -> None:
        rows = per_release["all"]
        obs = len(rows)
        passes = sum(1 for x in rows if (x[key] if key else False))
        rate = round(passes / obs, 4) if obs else 0.0
        claims.append([claim, "all", str(obs), str(passes), str(rate), label, detail])

    def emit_rel(claim: str, key) -> None:
        for rel in sorted(per_release):
            if rel == "all":
                continue
            rows = per_release[rel]
            obs = len(rows)
            passes = sum(1 for x in rows if (x[key] if key else False))
            rate = round(passes / obs, 4) if obs else 0.0
            claims.append([claim, rel, str(obs), str(passes), str(rate), "fact", ""])

    def emit_ceiling(claim: str, label: str, detail: str) -> None:
        claims.append([claim, "all", str(n_total), str(n_total), "1.0", label, detail])

    emit("BR5-01a_cgm_identity_full", "identity_full",
         detail="FINJPL writer id + Cont_ name + vendor/release footer")
    emit_rel("BR5-01a_cgm_identity_full", "identity_full")
    emit("BR5-01b_cgm_identity_writer", "identity_writer",
         detail=f"writer_offset={hist(writer_offsets)}")
    emit("BR5-01c_cgm_identity_name", "identity_name",
         detail="cont_name_offset=" + hist(name_offsets)
         + f";u16_prefix_2len_plus_2={prefix_ok}/{n_total}")
    emit("BR5-01d_cgm_identity_footer", "identity_footer",
         detail=f"release_token={hist(releases)};vendor=DASSAULT-SYSTEMES")

    emit("BR5-02a_dictionary_idruns", "has_runs",
         detail="id-list shape parsed for every k in 0..15")
    emit_rel("BR5-02a_dictionary_idruns", "has_runs")
    emit("BR5-02b_id_references_total", "has_runs",
         detail=f"id_refs={id_refs_total};run_records={run_records_total}"
         f";max_id_refs_file={max_id_refs_file[0]}:{max_id_refs_file[1]}"
         f";max_run_file={max_run_file[0]}:{max_run_file[1]}")
    emit("BR5-02c_marker1_records", "has_runs",
         detail=f"marker1_records={marker1_total};field layout not established")
    emit("BR5-02f_u16_width_files", "has_u16",
         detail="per-record u16le count width; accepted on every release bucket")
    emit_rel("BR5-02f_u16_width_files", "has_u16")
    emit_ceiling(
        "BR5-02d_dictionary_framed_bytes", "fact",
        f"ceiling: framed_bytes={framed_total};region_bytes={region_total}"
        f";framed_fraction={round(framed_total / max(region_total, 1), 4)}",
    )
    emit_ceiling(
        "BR5-02e_u16_width_recall_ceiling", "fact",
        f"ceiling: regions_gt_{U16_GATE_SPAN}B={big_regions}"
        f";their_region_bytes={big_region_bytes}"
        f";id_refs_gated={id_refs_total};id_refs_local={id_refs_local_total}"
        f";u16_unreachable_refs={id_refs_local_total - id_refs_total}",
    )

    emit("BR5-03a_nurbs_knot_sig_cgm_region", "knot_sig",
         detail=f"content-based knot-array signature (alias-guarded);"
         f"knot_runs={knot_total}")
    emit_rel("BR5-03a_nurbs_knot_sig_cgm_region", "knot_sig")
    emit("BR5-03b_nurbs_weight_sig_cgm_region", "weight_sig",
         detail=">=4 consecutive exact f64 1.0 inside the CGM region")
    content_hits = sum(
        1 for x in per_release["all"] if x["knot_sig"] or x["weight_sig"]
    )
    claims.append([
        "BR5-03c_nurbs_content_rate_vs_census", "all", str(n_total),
        str(content_hits), str(round(content_hits / max(n_total, 1), 4)),
        "fact", "census BR1 labels 100% from cgm_present alone",
    ])

    emit("BR5-04a_top01_seebody_block", "carrier_seebody")
    emit("BR5-04b_top01_store_root", "carrier_root",
         detail="nested store root via the committed locator probe order")
    top = max(xx0_files, key=lambda kv: kv[1]) if xx0_files else ("", 0)
    emit("BR5-05_xx0_reference_tags", "xx0_tags",
         detail="files=" + ";".join(f"{s}:{n}" for s, n in
                                    sorted(xx0_files, key=lambda kv: -kv[1]))
         + f";total={xx0_total}"
         + f";top_share={round(top[1] / max(xx0_total, 1), 4)}")

    # --- BR5-07 bulk window (record stream before the CGM block)
    path = corpus_root / next(
        r["local_path"] for r in population if r["sha256"].startswith(args.bulk_sha16)
    )
    bulk = bulk_window(path, args.bulk_mib)
    chance_window = bulk["bytes"] / 65536
    chance_bulk = bulk["bulk_bytes"] / 65536
    claims.append([
        "BR5-07a_bulk_window_span", "all", "1", "1", "1.0", "fact",
        f"sha16={args.bulk_sha16[:16]};window=[{bulk['lo']},{bulk['hi']})"
        f";window_bytes={bulk['bytes']};bulk_region=[{bulk['bulk_lo']},{bulk['bulk_hi']})"
        f";bulk_bytes={bulk['bulk_bytes']}"
        f";window_share={round(bulk['bytes'] / bulk['bulk_bytes'], 4)}",
    ])
    claims.append([
        "BR5-07b_bulk_window_knot_sig", "all", "1",
        str(1 if bulk["knot_runs"] else 0), str(1.0 if bulk["knot_runs"] else 0.0),
        "fact", f"knot_runs={bulk['knot_runs']};span_bytes={bulk['bytes']}",
    ])
    claims.append([
        "BR5-07c_bulk_window_weight_sig", "all", "1",
        str(1 if bulk["weight_runs"] else 0), str(1.0 if bulk["weight_runs"] else 0.0),
        "fact", f"weight_runs={bulk['weight_runs']};span_bytes={bulk['bytes']}",
    ])
    win_ratios = [bulk["magic_window"][m] / chance_window for m in _ZLIB_MAGICS]
    bulk_ratios = [bulk["magic_bulk"][m] / chance_bulk for m in _ZLIB_MAGICS]
    claims.append([
        "BR5-07d_bulk_window_zlib_magics", "all", "4",
        str(sum(1 for x in win_ratios if x >= 2.0)),
        str(round(sum(1 for x in win_ratios if x >= 2.0) / 4, 4)), "fact",
        "counts=" + ",".join(str(bulk["magic_window"][m]) for m in _ZLIB_MAGICS)
        + f";chance_per_pattern={chance_window:.1f}"
        + ";ratios=" + ",".join(f"{x:.2f}" for x in win_ratios),
    ])
    claims.append([
        "BR5-07e_bulk_zlib_magics", "all", "4",
        str(sum(1 for x in bulk_ratios if x >= 2.0)),
        str(round(sum(1 for x in bulk_ratios if x >= 2.0) / 4, 4)), "fact",
        "counts=" + ",".join(str(bulk["magic_bulk"][m]) for m in _ZLIB_MAGICS)
        + f";chance_per_pattern={chance_bulk:.1f}"
        + ";ratios=" + ",".join(f"{x:.2f}" for x in bulk_ratios),
    ])
    claims.append([
        "BR5-07f_bulk_zlib_streams", "all", str(bulk["zlib_attempts"]),
        str(bulk["zlib_ok"]),
        str(round(bulk["zlib_ok"] / max(bulk["zlib_attempts"], 1), 6)), "fact",
        f"trials={bulk['zlib_attempts']};output_streams={bulk['zlib_ok']}"
        f";trial_bytes={_ZLIB_TRIAL_BYTES}",
    ])
    claims.append([
        "BR5-07g_wholefile_weight_sig", "all", "1",
        str(1 if bulk["wholefile_weight_runs"] else 0),
        str(1.0 if bulk["wholefile_weight_runs"] else 0.0), "fact",
        f"weight_runs={bulk['wholefile_weight_runs']}"
        f";bytes={bulk['wholefile_bytes']}",
    ])

    # --- construct ceilings (numeric; the ticket disallows a third state)
    claims.append([
        "BR5-06a_top02_lump_detector", "all", "0", "0", "", "unknown",
        "construct=TOP-02;no committed record-level detector;the census "
        "TOPO_LUMP trigger is shared with TOPO_BODY",
    ])
    emit_ceiling(
        "BR5-06b_top02_lump_ceiling", "fact",
        f"ceiling: cgm_region_bytes={region_total};framed_bytes={framed_total}"
        f";framed_fraction={round(framed_total / max(region_total, 1), 4)}"
        f";bulk_window_bytes={bulk['bytes']};bulk_region_bytes={bulk['bulk_bytes']}"
        f";lump_record_classes=0",
    )
    claims.append([
        "BR5-06c_crv06_srf08_record_detector", "all", "0", "0", "", "unknown",
        "construct=CRV-06,SRF-08;the content signature detector exists "
        "(BR5-03a/b) but frames no record: no degree/knot/control-point "
        "record class is isolated",
    ])
    emit_ceiling(
        "BR5-06d_crv06_srf08_ceiling", "fact",
        f"ceiling: knot_sig_files={sum(1 for x in per_release['all'] if x['knot_sig'])}"
        f";weight_sig_files={sum(1 for x in per_release['all'] if x['weight_sig'])}"
        f";cgm_region_bytes={region_total}"
        f";bulk_window_bytes={bulk['bytes']};bulk_region_bytes={bulk['bulk_bytes']}"
        f";knot_runs_bulk_window={bulk['knot_runs']}"
        f";weight_runs_bulk_window={bulk['weight_runs']}"
        f";weight_runs_wholefile={bulk['wholefile_weight_runs']}",
    )

    with OUT_CLAIMS.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(CLAIM_FIELDS)
        w.writerows(claims)
    print(f"Wrote {OUT_CLAIMS} ({len(claims)} rows)")

    print("\nWorked examples (first five runnable dictionaries):")
    for sha, rel, row in worked:
        print(f"  {sha} {rel}: writer=+{row['writer_offset']} "
              f"name_off=+{row['cont_name_offset']} prefix={row['cont_name_prefix_ok']} "
              f"name={row['cont_name']!r} release={row['release_token']!r} "
              f"id_refs={row['id_refs']} framed={row['framed_bytes']} "
              f"marker1={row['marker1_records']} max_id={row['max_id']} "
              f"root={row['carrier_root']}")
    print(f"\nCorpus totals: id_refs={id_refs_total} (local width policy "
          f"{id_refs_local_total}) run_records={run_records_total} "
          f"marker1={marker1_total} framed={framed_total}/{region_total} "
          f"xx0_tags={xx0_total} knot_runs={knot_total} "
          f"max_id_refs={max_id_refs_file[0]}:{max_id_refs_file[1]} "
          f"max_run={max_run_file[0]}:{max_run_file[1]}")
    print(f"Bulk window: {bulk['bytes']} B of {bulk['bulk_bytes']} B; "
          f"knot={bulk['knot_runs']} weight={bulk['weight_runs']} "
          f"zlib_trials={bulk['zlib_attempts']} zlib_ok={bulk['zlib_ok']} "
          f"wholefile_weight={bulk['wholefile_weight_runs']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
