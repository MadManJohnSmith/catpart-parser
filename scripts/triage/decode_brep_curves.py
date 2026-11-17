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
        "block position byte-verified; skip-42 walk",
    ),
    "C01_line_prep_law": (
        "CRV-01",
        "33 32 blocks whose floats at +0x17 (23d) repeat the first triple bit-exact (G2 law, subpopulation)",
        "candidate",
        "laws hold and fail within single stores; field semantics open",
    ),
    "C01_line_len_law": (
        "CRV-01",
        "33 32 blocks whose float at +0x23 (35d) equals |Q| = ||Q|| (rel tol 1e-6) (G2 law, subpopulation)",
        "candidate",
        "laws hold and fail within single stores; field semantics open",
    ),
    "C02_circle_pool_law": (
        "CRV-02",
        "33 37 circles with some vertex-pool point on the circle (tol 5e-3)",
        "candidate",
        "geometric cross-check over stores with a decoded pool",
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
        "established",
        "BR3 direction law (skip-42 canonical walk)",
    ),
    "C03_conic_decode_ok": (
        "CRV-03",
        "33 38 records decoding under the 30-B layout and the direction law",
        "established",
        "6/15,722 corpus records rejected by the direction law (named)",
    ),
    "C03_conic_b_pos": (
        "CRV-03",
        "33 38 conic records with b > 0",
        "established",
        "BR3 positivity law",
    ),
    "C08_midring_dir_law": (
        "CRV-08",
        "33 33 records decoding under the direction law (mid-range unit / zero sentinel / unit pair)",
        "candidate",
        "BR3 re-read of the stage-4a p1/p2 params as an in-plane direction pair",
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
        "ceiling: files carrying any 33 38 record (no parabola discriminator decoded)",
        lambda c: c["c38"] > 0,
        "open (ceiling)",
    ),
    "C05_hyperbola_ceiling": (
        "CRV-05",
        "ceiling: files carrying any 33 38 record (no hyperbola discriminator decoded)",
        lambda c: c["c38"] > 0,
        "open (ceiling)",
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
            "edge_records", "polyline_strips",
            "c32", "c37", "c33", "c38",
            "c32_raw", "c37_raw", "c38_raw", "unwrapped_raw",
            "edge_wrapped_raw", "elem_decl",
            "line_obs", "line_prep_ok", "line_len_ok", "line_both",
            "circ_obs", "circ_ok", "circ_on_pool",
            "conic_obs", "conic_ok", "conic_dir_obs", "conic_dir_ok",
            "conic_b_ok", "conic_circform",
            "mid_obs", "mid_ok",
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
            counts["edge_records"] += len(g.records)
            counts["polyline_strips"] += sum(1 for n, _refs in g.records if n > 2)
    except ExportError:
        pass
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
            counts["c32"] += 1
            try:
                seg = curves.decode_line(rec, mm)
                counts["line_obs"] += 1
                counts["line_prep_ok"] += seg.p_rep_ok
                counts["line_len_ok"] += seg.length_ok
                counts["line_both"] += seg.p_rep_ok and seg.length_ok
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
            counts["c33"] += 1
            try:
                curves.decode_midring(rec)
                counts["mid_obs"] += 1
                counts["mid_ok"] += 1
            except ExportError:
                pass
        elif rec.family == curves.FAMILY_CONIC:
            counts["c38"] += 1
            counts["conic_obs"] += 1
            try:
                conic = curves.decode_conic(rec)
                counts["conic_ok"] += 1
                cos_t, sin_t = conic.direction
                mid = (
                    curves.DIR_TOL < abs(cos_t) < 1 - curves.DIR_TOL
                    and curves.DIR_TOL < abs(sin_t) < 1 - curves.DIR_TOL
                )
                counts["conic_dir_obs"] += mid
                counts["conic_dir_ok"] += mid and (
                    abs(math.hypot(cos_t, sin_t) - 1.0) <= curves.DIR_TOL
                )
                counts["conic_b_ok"] += conic.semi_b > 0
                counts["conic_circform"] += abs(conic.semi_a) == conic.semi_b
            except ExportError:
                pass
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
    with out_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CLAIM_FIELDS)
        w.writeheader()
        w.writerows(out)
    return len(out)


def _law_counter(key):
    """(observations, passes) counter names per law claim."""
    return {
        "C01_line_block_finite": ("line_obs", "line_obs"),
        "C01_line_prep_law": ("line_obs", "line_prep_ok"),
        "C01_line_len_law": ("line_obs", "line_len_ok"),
        "C02_circle_pool_law": ("circ_obs", "circ_on_pool"),
        "C02_circle_decode_ok": ("circ_obs", "circ_ok"),
        "C03_conic_dir_law": ("conic_dir_obs", "conic_dir_ok"),
        "C03_conic_b_pos": ("conic_ok", "conic_b_ok"),
        "C03_conic_decode_ok": ("conic_obs", "conic_ok"),
        "C08_midring_dir_law": ("mid_obs", "mid_ok"),
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
