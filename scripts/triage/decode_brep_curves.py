#!/usr/bin/env python3
"""Corpus triage of the BR3 boundary-curve slice (ticket #55, Spec G #47).

Reproduces and validates, corpus-wide over the 1,442-part manifest (and
specifically the 1,089 L2-pass population), the decode laws of
``src/catpart/brep/curves.py`` for the constructs TOP-06 Edge, TOP-07
Vertex, CRV-01 Line/Segment, CRV-02 Circle/Arc, CRV-03 Ellipse,
CRV-07 Polyline and CRV-08 Trimmed Curve, and pins the ceiling
arithmetic for the documented-open CRV-04 Parabola / CRV-05 Hyperbola
discriminators.

Outputs docs/evidence/data/br3-curves-claims.csv (one row per claim,
per scope) and a summary on stdout.  Deterministic: sorted manifest
order; no wall-clock value enters the CSV.  Read-only over the corpus
(binaries resolved against the main checkout when absent here); run
with the worktree venv:

  .venv/bin/python -I scripts/triage/decode_brep_curves.py
  # anchor subset:
  .venv/bin/python -I scripts/triage/decode_brep_curves.py \
    --include-sha16 026d6726007381a9,0018baa84f3bff6b
"""

from __future__ import annotations

import argparse
import csv
import math
import mmap
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
L2_STAGE15 = ROOT / "docs" / "evidence" / "data" / "stage15-identity-export-files.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"
MAIN_CHECKOUT = Path("/home/alan/Documents/Repos/catpart-parser")

sys.path.insert(0, str(ROOT / "src"))

from catpart.brep import curves  # noqa: E402
from catpart.geometry import store  # noqa: E402
from catpart.geometry.errors import ExportError  # noqa: E402

CLAIM_FIELDS = [
    "claim",
    "construct",
    "statement",
    "scope",
    "observations",
    "passes",
    "rate",
    "label",
    "note",
]

R_TOL = 5e-3  # |distance(vertex, center) - |r|| tolerance (f32 rounding)

# Record-level law claims: (construct, statement, label, note).
LAW_CLAIMS = {
    "T07_pool_count_law": (
        "TOP-07",
        "pool groups whose walked vertex-record count equals the count field (P2g)",
        "established",
        "structural validator: mismatches raise malformed-pool-group",
    ),
    "C01_line_block_finite": (
        "CRV-01",
        "33 32 canonical (len==2) records whose 40-B f32le block at +0x09 (9d) decodes finite (layout evidence)",
        "established",
        "block position byte-verified; skip-42 walk; denominator = walked canonical records (52 non-finite/out-of-scale block rejects)",
    ),
    "C01_line_prep_law": (
        "CRV-01",
        "33 32 blocks whose floats at +0x21 (33d)..+0x29 (41d) repeat the first triple at +0x09 (9d)..+0x11 (17d) bit-exact (G2 law, subpopulation)",
        "candidate",
        "laws hold and fail within single stores; field semantics open",
    ),
    "C01_line_len_law": (
        "CRV-01",
        "33 32 blocks whose float at +0x2D (45d) equals |Q| = ||Q|| over the Q triple at +0x15 (21d)..+0x1D (29d) (rel tol 1e-6) (G2 law, subpopulation)",
        "candidate",
        "laws hold and fail within single stores; field semantics open",
    ),
    "C01_line_prep_shift2": (
        "CRV-01",
        "33 32 P-rep law under the +2-byte-payload alignment (block read at +0x0B (11d)) - the alignment comparator",
        "candidate",
        "committed comparator for the alignment differential (canonical alignment wins corpus-wide)",
    ),
    "C02_circle_pool_law": (
        "CRV-02",
        "33 37 circles with some vertex-pool point on the circle (tol 5e-3)",
        "candidate",
        "geometric cross-check; denominator = ALL 33 37 records - pool-less-store records cannot pass (binding gap, not a law failure)",
    ),
    "C02_circle_decode_ok": (
        "CRV-02",
        "33 37 records decoding under the 18-B layout with finite non-zero radius",
        "established",
        "decoder accepts; zero/non-finite rejected (synthetic negative)",
    ),
    "C03_conic_dir_law": (
        "CRV-03",
        "33 38 direction pairs (both mid-range) with unit norm (tol 2e-3)",
        "candidate",
        "BR3 direction law (skip-42 canonical walk); measured from the payload before the decode gate, so direction-law rejects stay in the denominator",
    ),
    "C03_conic_decode_ok": (
        "CRV-03",
        "33 38 records decoding under the 30-B layout and the direction law",
        "established",
        "corpus rejections split across the committed rejection rows C03_conic_rej_short / _dir / _b / _implausible (11 = 15,768 - 15,757)",
    ),
    "C03_conic_b_pos": (
        "CRV-03",
        "33 38 conic records with b > 0",
        "established",
        "BR3 positivity law",
    ),
    "C03_conic_rej_short": (
        "CRV-03",
        "33 38 walked records whose payload is below the 30-B layout (rejection-reason counter)",
        "fact",
        "decode_conic length gate; denominator = walked 33 38 records",
    ),
    "C03_conic_rej_dir": (
        "CRV-03",
        "33 38 walked records rejected by the direction law (mid-range pair non-unit) (rejection-reason counter)",
        "fact",
        "measured from the payload before the decode gate; denominator = walked 33 38 records",
    ),
    "C03_conic_rej_b": (
        "CRV-03",
        "33 38 walked records rejected by b-positivity (b <= 0) (rejection-reason counter)",
        "fact",
        "measured from the payload before the decode gate; denominator = walked 33 38 records",
    ),
    "C03_conic_rej_implausible": (
        "CRV-03",
        "33 38 walked records rejected for non-finite/out-of-scale fields (rejection-reason counter)",
        "fact",
        "measured from the payload before the decode gate; denominator = walked 33 38 records",
    ),
    "C08_midring_dir_law": (
        "CRV-08",
        "33 33 records decoding under the direction law (mid-range unit / zero sentinel / unit pair)",
        "candidate",
        "BR3 re-read of the stage-4a p1/p2 params as an in-plane direction pair; denominator = walked canonical records (rejects = walked minus decoded, row-derived)",
    ),
    "C08_midring_midrange_unit": (
        "CRV-08",
        "33 33 mid-range direction pairs with unit norm (tol 2e-3)",
        "established",
        "corpus-wide mid-range subset of the BR3 re-read (10,051 unit of 10,696 mid-range; the 645 non-unit pairs sit in decode_midring's 710 rejects; 5,406/5,408 is the CONIC count)",
    ),
    "C36_block_read": (
        "walker",
        "33 36 records whose post-family bytes read as 10 finite f32le (measured for the exclusion claim; NOT a block-form establishment)",
        "fact",
        "33 36 stays out of slice: canonical len==2, no tiling/header-follow evidence for a 40-B block",
    ),
    "C01_line_walked": (
        "CRV-01",
        "33 32 canonical records walked by the skip-42 walker (volume anchor)",
        "fact",
        "walked, not decoded; the 52 non-finite/out-of-scale block rejects are the C01_line_block_finite gap",
    ),
    "C08_midring_walked": (
        "CRV-08",
        "33 33 canonical records walked by the skip-42 walker (volume anchor)",
        "fact",
        "walked, not decoded; the rejects are the C08_midring_dir_law gap",
    ),
    "C08_midring_zero_sentinel": (
        "CRV-08",
        "33 33 walked records whose direction pair is exactly (0, 0) - the observed axis-aligned sentinel",
        "fact",
        "dominant value of the BR3 re-read; denominator = walked 33 33 records with a readable direction pair (len >= 24 B)",
    ),
    "C08_midring_axis_pair": (
        "CRV-08",
        "33 33 walked records whose direction pair is exactly (+-1, 0) or (0, +-1)",
        "fact",
        "second dominant value of the BR3 re-read; denominator = walked 33 33 records with a readable direction pair (len >= 24 B)",
    ),
}

# File-level presence claims: (construct, statement, predicate over counts,
# label).
PRESENCE_CLAIMS = {
    "T07_vertex_presence": (
        "TOP-07",
        "file carries >= 1 vertex-pool point (P1)",
        lambda c: c["pool_vertices"] > 0,
        "established",
    ),
    "T07_census_presence": (
        "TOP-07",
        "census-equivalent presence: pool point or declared element space [frozen: 1282/1442 corpus; l2 1.0]",
        lambda c: c["pool_vertices"] > 0 or c["elem_decl"] > 0,
        "established",
    ),
    "T06_census_presence": (
        "TOP-06",
        "census-equivalent presence: wrapped edge group, 01 01 byte pair or 33 32 byte pair [frozen: 1311/1442 corpus; l2 1.0]",
        lambda c: c["edge_wrapped_raw"] > 0 or c["unwrapped_raw"] > 0 or c["c32_raw"] > 0,
        "established",
    ),
    "C01_census_presence": (
        "CRV-01",
        "census-equivalent presence: 33 32 byte pair or wrapped edge group [frozen: 1231/1442 corpus; l2 0.9853]",
        lambda c: c["c32_raw"] > 0 or c["edge_wrapped_raw"] > 0,
        "established",
    ),
    "C02_census_presence": (
        "CRV-02",
        "census-equivalent presence: 33 37 byte pair [frozen: 1077/1442 corpus; l2 0.8503]",
        lambda c: c["c37_raw"] > 0,
        "established",
    ),
    "C03_census_presence": (
        "CRV-03",
        "census-equivalent presence: 33 38 byte pair [frozen: 357/1442 corpus; l2 0.2874]",
        lambda c: c["c38_raw"] > 0,
        "established",
    ),
    "C07_census_presence": (
        "CRV-07",
        "census-equivalent presence: wrapped 01 02 edge group [frozen: 996/1442 corpus; l2 0.8365]",
        lambda c: c["edge_wrapped_raw"] > 0,
        "established",
    ),
    "T06_edge_presence": (
        "TOP-06",
        "file carries an edge group, an unwrapped list or a 33 32 record [census: 1311/1442 corpus; l2 1.0]",
        lambda c: c["edge_groups"] > 0 or c["polyline_lists"] > 0 or c["c32"] > 0,
        "established",
    ),
    "C01_line_presence": (
        "CRV-01",
        "file carries a 33 32 record or an edge group [census: 1231/1442 corpus; l2 0.9853]",
        lambda c: c["c32"] > 0 or c["edge_groups"] > 0,
        "established",
    ),
    "C02_circle_presence": (
        "CRV-02",
        "file carries a 33 37 record [census: 1077/1442 corpus; l2 0.8503]",
        lambda c: c["c37"] > 0,
        "established",
    ),
    "C03_conic_presence": (
        "CRV-03",
        "file carries a 33 38 record [census: 357/1442 corpus; l2 0.2874]",
        lambda c: c["c38"] > 0,
        "established",
    ),
    "C07_polyline_presence": (
        "CRV-07",
        "file carries an 01 02 edge group [census: 996/1442 corpus; l2 0.8365]",
        lambda c: c["edge_groups"] > 0,
        "established",
    ),
    "C07_polyline_strips": (
        "CRV-07",
        "file carries an n > 2 polyline strip record (CRV-07 proper)",
        lambda c: c["polyline_strips"] > 0,
        "established",
    ),
    "C08_trim_presence": (
        "CRV-08",
        "file carries parameter-carrier curve records (33 33 direction/radius or 33 38 axes/direction)",
        lambda c: c["c33"] > 0 or c["c38"] > 0,
        "candidate",
    ),
    "C04_parabola_ceiling": (
        "CRV-04",
        "ceiling: files carrying any 33 38 byte-pair carrier (no parabola discriminator decoded; frozen arithmetic 214+143=357)",
        lambda c: c["c38_raw"] > 0,
        "open (ceiling)",
    ),
    "C05_hyperbola_ceiling": (
        "CRV-05",
        "ceiling: files carrying any 33 38 byte-pair carrier (no hyperbola discriminator decoded; frozen arithmetic 214+143=357)",
        lambda c: c["c38_raw"] > 0,
        "open (ceiling)",
    ),
    "T06_edge_residue_files": (
        "TOP-06",
        "file with wrapped 01 02 edge groups that fail to end-align under either width (the E1 residue, named)",
        lambda c: c["edge_misaligned"] > 0,
        "named residue",
    ),
    "C01_store_prep_population": (
        "CRV-01",
        "file carries >= 4 walked 33 32 records with a full 40-B block (the per-store P-rep spread population)",
        lambda c: c["line_walked_full"] >= 4,
        "candidate",
    ),
}


def resolve_path(rel: dict) -> Path:
    path = ROOT / rel["local_path"]
    if path.exists():
        return path
    return MAIN_CHECKOUT / rel["local_path"]


def locate_span(mm):
    """Store-body span via the census's container-probing law, or None.

    Mirrors `census_brep_constructs.audit_part`: probe CATStdCont,
    CATXDocLinkCont, CATSeeBodyCont and other-container blocks in that
    order, so the census-equivalent presence rows scan the same spans
    the frozen census scanned.
    """
    d8 = int.from_bytes(mm[8:12], "big") if len(mm) >= 12 else 0
    blocks = store.valid_blocks(mm)
    name_of = {
        store.CONTAINER_STDCONT: "CATStdCont",
        store.CONTAINER_XDOCLINK: "CATXDocLinkCont",
        store.CONTAINER_SEEBODY: "CATSeeBodyCont",
    }
    for container in (
        store.CONTAINER_STDCONT,
        store.CONTAINER_XDOCLINK,
        store.CONTAINER_SEEBODY,
        store.CONTAINER_OTHER,
    ):
        want = name_of.get(container)
        cands = [b for b, nm in blocks if want is None or nm == want]
        for blk in cands:
            try:
                span = store.locate_store(mm, blk, blocks, d8, container=container)
            except Exception:  # noqa: BLE001 - recorded per part
                continue
            if span is not None:
                return span.body_lo, span.body_hi
    return None


def on_pool(circ, groups):
    """True when some pool vertex lies on the record's circle."""
    cx, cy, cz = circ.center
    r = abs(circ.radius)
    for g in groups:
        for x, y, z in g.vertices:
            if abs(math.dist((x, y, z), (cx, cy, cz)) - r) <= R_TOL:
                return True
    return False


def audit_part(mm):
    """One part: walk the slice's constructs. Returns the counts dict."""
    span = locate_span(mm)
    counts = {
        key: 0
        for key in (
            "pool_vertices", "pool_groups", "pool_groups_ok",
            "edge_groups", "edge_groups_ok", "polyline_lists",
            "polyline_strips",
            "c32", "c37", "c33", "c38",
            "c32_raw", "c37_raw", "c38_raw", "unwrapped_raw",
            "edge_wrapped_raw", "elem_decl",
            "line_obs", "line_prep_ok", "line_len_ok",
            "line_prep_shift2", "line_walked_full",
            "circ_obs", "circ_ok", "circ_on_pool",
            "conic_obs", "conic_ok", "conic_dir_obs", "conic_dir_ok",
            "conic_b_ok",
            "conic_rej_short", "conic_rej_dir", "conic_rej_b",
            "conic_rej_implausible",
            "mid_obs", "mid_ok", "mid_pair_obs", "mid_midrange",
            "mid_midrange_unit", "mid_zero_sentinel", "mid_axis_pair",
            "c36", "c36_block_ok",
            "edge_misaligned",
        )
    }
    if span is None:
        return counts
    lo, hi = span

    # TOP-07: vertex pool (P1-P3 via the structural validator).
    try:
        groups, _kinds = curves.scan_vertex_pool(mm, lo, hi)
        counts["pool_groups"] = len(groups)
        counts["pool_groups_ok"] = len(groups)
        counts["pool_vertices"] = sum(len(g.vertices) for g in groups)
    except ExportError:
        counts["pool_groups"] += 1

    # TOP-06 / CRV-07: edge groups + unwrapped lists (E1/E3 grammar).
    try:
        egroups = curves.scan_edge_groups(mm, lo, hi, strict=False)
        wraps = list(curves.pool.find_all(mm, curves.WRAPPER, lo, hi))
        counts["edge_groups"] = sum(
            1 for w in wraps if bytes(mm[w + 8 : w + 10]) == curves.EDGE_SUBKIND
        )
        counts["edge_groups_ok"] = len(egroups)
        for g in egroups:
            counts["polyline_strips"] += sum(1 for n, _refs in g.records if n > 2)
        if len(egroups) < counts["edge_groups"]:
            counts["edge_misaligned"] = 1
    except ExportError:
        counts["edge_misaligned"] = 1
    try:
        counts["polyline_lists"] = len(curves.scan_polyline_lists(mm, lo, hi))
    except ExportError:
        pass

    # Census-equivalent presence columns (byte-pair level, the frozen
    # census's detectors) so the frozen vocabulary rates reproduce.
    def count_pairs(needle: bytes) -> int:
        n = 0
        pos = lo
        while True:
            pos = mm.find(needle, pos, hi)
            if pos < 0:
                return n
            n += 1
            pos += 2

    counts["c32_raw"] = count_pairs(b"\x33\x32")
    counts["c37_raw"] = count_pairs(b"\x33\x37")
    counts["c38_raw"] = count_pairs(b"\x33\x38")
    counts["unwrapped_raw"] = count_pairs(b"\x01\x01")
    wraps = list(curves.pool.find_all(mm, curves.WRAPPER, lo, hi))
    counts["edge_wrapped_raw"] = sum(
        1 for w in wraps if bytes(mm[w + 8 : w + 10]) == curves.EDGE_SUBKIND
    )
    t_pos = mm.find(b"\xff\xff\x02\x00\x01", lo, hi)
    if t_pos >= 0:
        p = t_pos + 5
        if p < hi:
            if mm[p] == 0xFF and p + 5 <= hi:
                counts["elem_decl"] = int.from_bytes(mm[p + 1 : p + 5], "little")
            else:
                counts["elem_decl"] = mm[p]

    # Curve records and the per-family laws.
    for rec in curves.iter_curve_records(mm, lo, hi):
        if rec.family == curves.FAMILY_LINE:
            counts["c32"] += 1  # walked canonical 33 32 records
            start = rec.offset + 2
            block = mm[start : start + curves.LINE_BLOCK.size]
            if len(block) == curves.LINE_BLOCK.size:
                # The law flags, measured on the full-block walked
                # population (the non-finite/out-of-scale block rejects
                # never reach the laws — the honest denominators live
                # in the rows).
                counts["line_walked_full"] += 1
                prep, _lenok = curves.line_laws(block)
                counts["line_prep_ok"] += prep
                counts["line_len_ok"] += _lenok
                b2 = mm[start + 2 : start + 2 + curves.LINE_BLOCK.size]
                if len(b2) == curves.LINE_BLOCK.size:
                    counts["line_prep_shift2"] += curves.line_laws(b2)[0]
            try:
                curves.decode_line(rec, mm)
                counts["line_obs"] += 1
            except ExportError:
                pass
        elif rec.family == curves.FAMILY_CIRCLE:
            counts["c37"] += 1
            counts["circ_obs"] += 1
            try:
                circ = curves.decode_circle(rec)
                counts["circ_ok"] += 1
                if counts["pool_vertices"]:
                    counts["circ_on_pool"] += on_pool(circ, groups)
            except ExportError:
                pass
        elif rec.family == curves.FAMILY_MIDRING:
            counts["c33"] += 1  # walked canonical 33 33 records
            if len(rec.payload) >= 24:
                c = curves.BE_F32.unpack_from(rec.payload, 12)[0]
                s = curves.BE_F32.unpack_from(rec.payload, 16)[0]
                counts["mid_pair_obs"] += 1
                counts["mid_zero_sentinel"] += c == 0.0 and s == 0.0
                counts["mid_axis_pair"] += (
                    (abs(c) == 1.0 and s == 0.0) or (c == 0.0 and abs(s) == 1.0)
                )
                mid = (
                    curves.DIR_TOL < abs(c) < 1 - curves.DIR_TOL
                    and curves.DIR_TOL < abs(s) < 1 - curves.DIR_TOL
                )
                if mid:
                    counts["mid_midrange"] += 1
                    counts["mid_midrange_unit"] += (
                        abs(math.hypot(c, s) - 1.0) <= curves.DIR_TOL
                    )
            try:
                curves.decode_midring(rec)
                counts["mid_obs"] += 1
                counts["mid_ok"] += 1
            except ExportError:
                pass
        elif rec.family == curves.FAMILY_CONIC:
            counts["c38"] += 1  # walked canonical 33 38 records
            counts["conic_obs"] += 1
            # Rejection-reason split (short payload / non-finite-scale
            # field / non-unit mid-range direction / b-positivity),
            # measured from the PAYLOAD before the decode gate so the
            # direction-law denominator includes the direction-law
            # rejects themselves.  Threshold 30 B matches
            # decode_conic's length gate.
            if len(rec.payload) < 30:
                counts["conic_rej_short"] += 1
            else:
                v = [curves.BE_F32.unpack_from(rec.payload, 4 * i)[0] for i in range(7)]
                if not all(math.isfinite(x) and abs(x) < 1e7 for x in v):
                    counts["conic_rej_implausible"] += 1
                else:
                    norm = math.hypot(v[3], v[4])
                    mid = (
                        curves.DIR_TOL < abs(v[3]) < 1 - curves.DIR_TOL
                        and curves.DIR_TOL < abs(v[4]) < 1 - curves.DIR_TOL
                    )
                    counts["conic_dir_obs"] += mid
                    counts["conic_dir_ok"] += mid and (
                        abs(norm - 1.0) <= curves.DIR_TOL
                    )
                    if mid and abs(norm - 1.0) > curves.DIR_TOL:
                        counts["conic_rej_dir"] += 1
                    elif v[6] <= 0:
                        counts["conic_rej_b"] += 1
            try:
                conic = curves.decode_conic(rec)
                counts["conic_ok"] += 1
                counts["conic_b_ok"] += conic.semi_b > 0
            except ExportError:
                pass
        elif rec.family == 0x36:
            # 33 36: out of slice (canonical len==2, no block-form
            # evidence). The finite read is MEASURED for the exclusion
            # claim only — it neither establishes nor refutes a block.
            counts["c36"] += 1  # walked 33 36 records
            start = rec.offset + 2
            block = mm[start : start + curves.LINE_BLOCK.size]
            if len(block) == curves.LINE_BLOCK.size:
                vals = curves.LINE_BLOCK.unpack(block)
                if all(math.isfinite(x) for x in vals):
                    counts["c36_block_ok"] += 1
    return counts


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--include-sha16", default="")
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    args = ap.parse_args()

    l2_by_sha = {}
    if L2_STAGE15.exists():
        with L2_STAGE15.open() as f:
            for r in csv.DictReader(f):
                l2_by_sha[r["sha256"]] = r.get("l2_status", "")

    rows = [
        r
        for r in csv.DictReader(MANIFEST.open())
        if r["kind"] == "part" and r["split"] in ("dev", "held-out")
    ]
    if args.include_sha16:
        want = {h for h in args.include_sha16.split(",") if h}
        rows = [r for r in rows if r["sha256"][:16] in want]
    rows.sort(key=lambda r: r["sha256"])

    file_rows = []
    for rel in rows:
        path = resolve_path(rel)
        with path.open("rb") as fh:
            mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                counts = audit_part(mm)
            finally:
                mm.close()
        counts["sha256"] = rel["sha256"]
        counts["l2_status"] = l2_by_sha.get(rel["sha256"], "")
        file_rows.append(counts)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "br3-curves-claims.csv"
    n_claims = write_claims(out_path, file_rows)
    print(f"wrote {out_path} ({n_claims} claim rows)")
    summarize(file_rows)
    return 0


def write_claims(out_path, file_rows):
    """Fold the per-file counters into per-claim, per-scope rates."""
    scopes = (
        ("corpus", file_rows),
        ("l2-pass", [r for r in file_rows if r["l2_status"] == "pass"]),
    )
    out = []
    for key, (construct, statement, label, note) in LAW_CLAIMS.items():
        for scope, frows in scopes:
            if key == "T07_pool_count_law":
                obs = sum(r["pool_groups"] for r in frows)
                ok = sum(r["pool_groups_ok"] for r in frows)
            else:
                obs = sum(r[_law_counter(key)[0]] for r in frows)
                ok = sum(r[_law_counter(key)[1]] for r in frows)
            out.append({
                "claim": key,
                "construct": construct,
                "statement": statement,
                "scope": scope,
                "observations": obs,
                "passes": ok,
                "rate": round(ok / obs, 4) if obs else "",
                "label": label,
                "note": note,
            })
    for key, (construct, statement, pred, label) in PRESENCE_CLAIMS.items():
        for scope, frows in scopes:
            ok = sum(1 for r in frows if pred(r))
            out.append({
                "claim": key,
                "construct": construct,
                "statement": statement,
                "scope": scope,
                "observations": len(frows),
                "passes": ok,
                "rate": round(ok / len(frows), 4) if frows else "",
                "label": label,
                "note": "",
            })
    # Value row: the median per-store P-rep rate (the rate column
    # carries the value), companion to C01_store_prep_population.
    for scope, frows in scopes:
        rates = [
            r["line_prep_ok"] / r["line_walked_full"]
            for r in frows
            if r["line_walked_full"] >= 4
        ]
        if rates:
            out.append({
                "claim": "C01_store_prep_median",
                "construct": "CRV-01",
                "statement": "median per-store P-rep rate over files with >= 4 walked 33 32 records with a full 40-B block (companion row C01_store_prep_population)",
                "scope": scope,
                "observations": 1,
                "passes": 1,
                "rate": round(statistics.median(rates), 4),
                "label": "candidate",
                "note": "value row: the rate column carries the median",
            })
    with out_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CLAIM_FIELDS)
        w.writeheader()
        w.writerows(out)
    return len(out)


def _law_counter(key):
    """(observations, passes) counter names per law claim."""
    return {
        "C01_line_block_finite": ("c32", "line_obs"),
        "C01_line_prep_law": ("line_walked_full", "line_prep_ok"),
        "C01_line_len_law": ("line_walked_full", "line_len_ok"),
        "C01_line_prep_shift2": ("line_walked_full", "line_prep_shift2"),
        "C01_line_walked": ("c32", "c32"),
        "C02_circle_pool_law": ("circ_obs", "circ_on_pool"),
        "C02_circle_decode_ok": ("circ_obs", "circ_ok"),
        "C03_conic_dir_law": ("conic_dir_obs", "conic_dir_ok"),
        "C03_conic_b_pos": ("conic_ok", "conic_b_ok"),
        "C03_conic_rej_short": ("c38", "conic_rej_short"),
        "C03_conic_rej_dir": ("c38", "conic_rej_dir"),
        "C03_conic_rej_b": ("c38", "conic_rej_b"),
        "C03_conic_rej_implausible": ("c38", "conic_rej_implausible"),
        "C03_conic_decode_ok": ("conic_obs", "conic_ok"),
        "C08_midring_dir_law": ("c33", "mid_obs"),
        "C08_midring_midrange_unit": ("mid_midrange", "mid_midrange_unit"),
        "C08_midring_zero_sentinel": ("mid_pair_obs", "mid_zero_sentinel"),
        "C08_midring_axis_pair": ("mid_pair_obs", "mid_axis_pair"),
        "C08_midring_walked": ("c33", "c33"),
        "C36_block_read": ("c36", "c36_block_ok"),
        "T07_pool_count_law": ("pool_groups", "pool_groups_ok"),
    }[key]


def summarize(file_rows):
    l2 = [r for r in file_rows if r["l2_status"] == "pass"]
    print(f"== BR3 curve triage: {len(file_rows)} parts, {len(l2)} l2-pass")
    for key in LAW_CLAIMS:
        o_name, k_name = _law_counter(key)
        obs = sum(r[o_name] for r in l2)
        ok = sum(r[k_name] for r in l2)
        rate = f"{ok / obs:.4f}" if obs else "n/a"
        print(f"   {key:<24} {ok}/{obs} = {rate}  (l2-pass)")
    for scope, frows in (("corpus", file_rows), ("l2-pass", l2)):
        for key in ("T07_vertex_presence", "T07_census_presence", "T06_edge_presence",
                    "T06_census_presence", "C01_line_presence", "C01_census_presence",
                    "C02_circle_presence", "C02_census_presence", "C03_conic_presence",
                    "C03_census_presence", "C07_polyline_presence", "C07_census_presence",
                    "C02_circle_presence", "C03_conic_presence",
                    "C07_polyline_presence", "C07_polyline_strips",
                    "C08_trim_presence", "C04_parabola_ceiling",
                    "C05_hyperbola_ceiling"):
            pred = PRESENCE_CLAIMS[key][2]
            ok = sum(1 for r in frows if pred(r))
            print(f"   {key:<24} {ok}/{len(frows)} = {ok / len(frows):.4f}  [{scope}]")
        print()


if __name__ == "__main__":
    sys.exit(main())
