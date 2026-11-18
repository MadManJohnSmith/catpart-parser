#!/usr/bin/env python3
"""BR2 corpus decoder: exact planar faces & boundary loops (Ticket #54, Spec G #47).

Decodes the three BR2 constructs corpus-wide over the manifest's part
population (the census population, 1,442 parts) with the L2-pass join
(docs/evidence/data/stage15-identity-export-files.csv, 1,089 files):

- TOP-04 Face: the accepted ``01 [41-4f]`` facet records as face
  carriers — census tie-out (files with >= 1 accepted record) plus the
  per-record decode (layout, loop delimitation, normal).
- TOP-05 Loop: the true loop delimitation (ty = loop count; per-record
  count width u8/u16be — independent of the reference width) and the
  primitive readings (0x4c closed rings, strip segments).
- SRF-01 Plane: the 12B f32le unit normal, the derived plane offset and
  the corpus plane validation on the pool-only scope (the composite
  index space, G3 F8, leaves composite stores' references unverifiable
  against the pool — measured, not guessed).

Outputs docs/evidence/data/br2-planar-claims.csv (per-claim rates —
every figure the evidence note's prose cites) and a stdout tie-out
table. Filtered runs (``--sha16`` / ``--limit``) write a DISTINCT
file name (``br2-planar-claims-sha16-<prefix>.csv`` /
``br2-planar-claims-limit-<n>.csv``) so a filtered probe can never
replace the all-corpus artifact (the Phase-5-retro clobber failure
mode, dispatch-recipes.md:122-132). Corpus binaries are read READ-ONLY
from the MAIN checkout (--corpus-root, never copied into the repo
tree, never committed).

Detector honesty: the synthetic negative fixtures for every
discriminating edge run via ``--selftest`` (no corpus needed) and live
pinned in tests/test_brep_planar.py.

Reproduction (deterministic, manifest order, stdlib only):
    LD_LIBRARY_PATH=/usr/lib python -I scripts/triage/decode_brep_planar.py
    LD_LIBRARY_PATH=/usr/lib python -I scripts/triage/decode_brep_planar.py --selftest
    LD_LIBRARY_PATH=/usr/lib python -I scripts/triage/decode_brep_planar.py \
        --sha16 bd79fa8e --out-dir /tmp/br2-sha16
"""

from __future__ import annotations

import argparse
import csv
import mmap
import struct
import sys
from collections import Counter
from pathlib import Path

from catpart.brep.planar import (
    FACE_COUNT_VARIANT,
    FACE_NO_LOOPS,
    FACE_OK,
    FACE_OUT_OF_POOL,
    UNIT_NORM_TOL,
    count_structure,
    decode_planar_face,
    normal_unit_deviation,
    record_true_loops,
)
from catpart.geometry import facets, pool, store

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "manifests" / "corpus-manifest.csv"
L2_STAGE15 = REPO_ROOT / "docs" / "evidence" / "data" / "stage15-identity-export-files.csv"
OUT_DIR = REPO_ROOT / "docs" / "evidence" / "data"
DEFAULT_CORPUS_ROOT = "/home/alan/Documents/Repos/catpart-parser"

#: G3's named counterexample stores (docs/evidence/2026-11-09-facet-semantics.md
#: §3 "Counterexamples named", 2026-11-10 correction #35): six off-plane
#: stores plus the one anti-parallel store. The attribution rows classify
#: by this CITATION — the counts are measured here; "G3 already named this
#: store" is read off G3's note, not re-derived.
G3_NAMED_OFF_PLANE = frozenset(
    {
        "aa84a202df09ed45",
        "bd79fa8e39e8fab2",
        "1ffad5964894f1ff",
        "a6d450edd4a8ff17",
        "0ae8c3e7dd3e74ad",
        "b9b887db0d516d88",
    }
)
G3_NAMED_ANTIPARALLEL = frozenset({"6888b9868df81c00"})
G3_NAMED_STORES = G3_NAMED_OFF_PLANE | G3_NAMED_ANTIPARALLEL


def g3_named_class(sha16: str) -> str:
    """The G3 citation for a store (or the explicit 'not named' bit)."""
    if sha16 in G3_NAMED_OFF_PLANE:
        return "G3-named off-plane store, 2026-11-09-facet-semantics.md §3"
    if sha16 in G3_NAMED_ANTIPARALLEL:
        return "G3-named anti-parallel store, 2026-11-09-facet-semantics.md §3"
    return "store NOT named by G3"


CLAIMS_FIELDS = [
    "claim",
    "statement",
    "label",
    "scope",
    "release",
    "observations",
    "passes",
    "rate",
]


def locate_store(mm):
    """The census's container probe order, byte-for-byte: stdcont,
    xdoclink, seebody, then other-container — whose filter in the
    census compares the block name against itself (always true), so the
    final pass probes EVERY valid block. The census tie-out requires
    the same behavior."""
    blocks = store.valid_blocks(mm)
    d8_outer = int.from_bytes(mm[8:12], "big") if len(mm) >= 12 else 0
    for container_tag in (
        store.CONTAINER_STDCONT,
        store.CONTAINER_XDOCLINK,
        store.CONTAINER_SEEBODY,
        store.CONTAINER_OTHER,
    ):
        if container_tag == store.CONTAINER_OTHER:
            cands = [b for b, _ in blocks]
        else:
            name = {
                store.CONTAINER_STDCONT: "CATStdCont",
                store.CONTAINER_XDOCLINK: "CATXDocLinkCont",
                store.CONTAINER_SEEBODY: "CATSeeBodyCont",
            }[container_tag]
            cands = [b for b, nm in blocks if nm == name]
        for blk in cands:
            try:
                span = store.locate_store(mm, blk, blocks, d8_outer, container=container_tag)
            except Exception:
                continue
            if span is not None:
                return span
    return None


def audit_part(mm) -> dict:
    """One part's BR2 audit — the per-file counters feeding the claims."""
    out = {
        "has_store": False,
        "store_class": "",
        "records": 0,
        "records_geometry": 0,
        "records_by_marker": Counter(),
        "five_byte_form": 0,
        "normal_records": 0,
        "unit_normals": 0,
        "unit_norm_max_dev": 0.0,
        "count_u8": 0,
        "count_u16": 0,
        "count_u16_u8ref": 0,  # u16be counts over u8 references
        "count_variant": 0,
        "nb_variants": 0,  # count-law variants among NORMAL-BEARING records
        "u16_count_present": False,
        "u16_u8ref_present": False,
        "resolved_triangle_list": 0,  # 0x49 records under the count law
        "mk_49_normal": 0,  # 0x49 records carrying a normal
        "mk_49_n_equals_3ty": 0,  # 0x49 records satisfying n == 3*ty
        "ty_zero": 0,  # accepted records with ty == 0 (no loops)
        "normal_less_strip_loops": Counter(),  # true loops of 0x41/0x42 records, by marker
        "ty_multi_loop": 0,  # ty >= 2 records (multi-loop faces)
        "ring_loops": 0,
        "strip_loops": 0,
        "face_status": Counter(),
        "geometry_decodable": 0,
        "coplanar": 0,
        "cop_fail": 0,  # in-pool faces failing the coplanarity test
        "sign_negative": 0,  # in-pool faces with a sign-negative winding
        "oriented": 0,
        "oriented_candidates": 0,
        "pass_rel_spreads": [],  # coplanar faces' max_dev/tol
        "fail_rel_spreads": [],  # non-coplanar faces' max_dev/tol
        "rel_spreads": [],
        "planar_marker_record": 0,  # accepted 0x4a/0x4c records
        "facet_record": 0,  # accepted 01 [41-4f] records (any marker)
    }
    try:
        span = locate_store(mm)
    except Exception:
        span = None
    if span is None:
        return out
    out["has_store"] = True
    lo, hi = span.body_lo, span.body_hi

    # Census tie-out scan FIRST and unconditionally (the census counts
    # facet records even where the pool walk raises).
    scan = facets.scan_facets(mm, lo, hi)
    out["records"] = len(scan.records)
    out["facet_record"] = len(scan.records)
    out["planar_marker_record"] = sum(
        1 for r in scan.records if r.marker in (0x4A, 0x4C)
    )

    try:
        groups, kinds = pool.scan_pool_groups(mm, lo, hi)
    except Exception:
        out["store_class"] = "pool-scan-failed"
        return out
    flat = [v for g in groups for v in g.vertices]
    composite = pool.has_composite_space(kinds)
    out["store_class"] = "composite" if composite else "pool-only"

    # Geometry scan: on pool-only stores the store-width context applies
    # (F1w as corrected 2026-11-10 #35); composite stores keep the
    # default (fail-safe) scan.
    gscan = facets.scan_facets(mm, lo, hi, clean_store=not composite) if not composite else scan
    lex = facets.lex_rank_map(flat)
    out["records_geometry"] = len(gscan.records)

    for r in gscan.records:
        out["records_by_marker"][r.marker] += 1
        if r.header_len == 5:
            out["five_byte_form"] += 1
        if r.type == 0:
            out["ty_zero"] += 1
        if r.marker == 0x49:
            if r.normal is not None:
                out["mk_49_normal"] += 1
            if r.n == 3 * r.type:
                out["mk_49_n_equals_3ty"] += 1
        cs = count_structure(r)
        if r.type:
            if cs is None:
                out["count_variant"] += 1
            elif cs.count_width == 1:
                out["count_u8"] += 1
            else:
                out["count_u16"] += 1
                out["u16_count_present"] = True
                if r.width == 1:
                    out["count_u16_u8ref"] += 1
                    out["u16_u8ref_present"] = True
            if r.marker == 0x49 and cs is not None:
                out["resolved_triangle_list"] += 1
        if r.normal is not None and cs is None and r.type:
            out["nb_variants"] += 1
        if r.normal is None:
            # Normal-less strip families sit outside the face-decode
            # population; their loop count is measured per marker for the
            # BR2-16 scope statement.
            if r.marker in (0x41, 0x42):
                out["normal_less_strip_loops"][r.marker] += len(record_true_loops(r))
            continue
        out["normal_records"] += 1
        if r.type >= 2:
            out["ty_multi_loop"] += 1
        dev = abs(normal_unit_deviation(r.normal))
        out["unit_norm_max_dev"] = max(out["unit_norm_max_dev"], dev)
        if dev <= UNIT_NORM_TOL:
            out["unit_normals"] += 1
        face = decode_planar_face(flat, lex, r)
        out["face_status"][face.status] += 1
        for lr in face.loop_readings:
            if lr.kind == "ring":
                out["ring_loops"] += 1
            else:
                out["strip_loops"] += 1
        if face.status != FACE_OK or face.plane is None:
            continue
        out["geometry_decodable"] += 1
        rel = face.plane.max_dev / face.plane.tol if face.plane.tol else 0.0
        out["rel_spreads"].append(rel)
        if face.plane.coplanar:
            out["coplanar"] += 1
            out["pass_rel_spreads"].append(rel)
        else:
            out["cop_fail"] += 1
            out["fail_rel_spreads"].append(rel)
        if face.oriented is not None:
            out["oriented_candidates"] += 1
            if face.oriented:
                out["oriented"] += 1
            else:
                out["sign_negative"] += 1
    return out


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    vs = sorted(values)
    idx = min(len(vs) - 1, int(round(q * (len(vs) - 1))))
    return vs[idx]


def run_corpus(args) -> list[dict]:
    """The corpus walk; returns the claims rows."""
    corpus_root = Path(args.corpus_root)
    l2_by_sha = {}
    if L2_STAGE15.exists():
        with L2_STAGE15.open() as f:
            for r in csv.DictReader(f):
                l2_by_sha[r["sha256"]] = r.get("l2_status", "")

    with MANIFEST.open() as f:
        manifest_parts = [r for r in csv.DictReader(f) if r["kind"] == "part"]
    manifest_parts.sort(key=lambda r: r["sha256"])
    if args.sha16:
        manifest_parts = [r for r in manifest_parts if r["sha256"].startswith(tuple(args.sha16))]
    if args.limit:
        manifest_parts = manifest_parts[: args.limit]
    print(f"BR2 decode over {len(manifest_parts)} parts (corpus root: {corpus_root})")

    corpus = Counter()
    poolonly = Counter()
    composite = Counter()
    poolonly_rel_spreads: list[float] = []
    poolonly_pass_spreads: list[float] = []
    poolonly_fail_spreads: list[float] = []
    composite_rel_spreads: list[float] = []
    unit_norm_max_dev = 0.0
    worst_poolonly_rel = 0.0
    worst_poolonly_sha = ""
    files_with_store = 0
    files_facet = files_planar = 0
    files_facet_l2 = files_planar_l2 = 0
    l2_total = 0
    stores_u16 = 0
    stores_u16_u8ref = 0
    cop_fail_by_store: Counter = Counter()
    signneg_by_store: Counter = Counter()

    for r in manifest_parts:
        fpath = corpus_root / r["local_path"]
        l2_status = l2_by_sha.get(r["sha256"], "")
        is_l2 = l2_status == "pass"
        if is_l2:
            l2_total += 1
        with fpath.open("rb") as fh:
            mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                audit = audit_part(mm)
            finally:
                mm.close()
        if audit["has_store"]:
            files_with_store += 1
            if audit["store_class"] in ("pool-only", "composite"):
                bucket = poolonly if audit["store_class"] == "pool-only" else composite
                bucket["stores"] += 1
                for key in (
                    "records",
                    "records_geometry",
                    "normal_records",
                    "unit_normals",
                    "count_u8",
                    "count_u16",
                    "count_u16_u8ref",
                    "count_variant",
                    "nb_variants",
                    "resolved_triangle_list",
                    "mk_49_normal",
                    "mk_49_n_equals_3ty",
                    "ty_zero",
                    "ty_multi_loop",
                    "ring_loops",
                    "strip_loops",
                    "geometry_decodable",
                    "coplanar",
                    "cop_fail",
                    "sign_negative",
                    "oriented",
                    "oriented_candidates",
                    "planar_marker_record",
                    "facet_record",
                    "five_byte_form",
                ):
                    bucket[key] += audit[key]
                for st, n in audit["face_status"].items():
                    bucket[f"status_{st}"] += n
                for mk, n in audit["records_by_marker"].items():
                    bucket[f"mk_{mk:#x}"] += n
                for mk, n in audit["normal_less_strip_loops"].items():
                    bucket[f"normal_less_loops_{mk:#x}"] += n
                if audit["unit_norm_max_dev"] > unit_norm_max_dev:
                    unit_norm_max_dev = audit["unit_norm_max_dev"]
                target_spreads = (
                    poolonly_rel_spreads if audit["store_class"] == "pool-only" else composite_rel_spreads
                )
                target_spreads.extend(audit["rel_spreads"])
                sha16 = r["sha256"][:16]
                if audit["store_class"] == "pool-only":
                    poolonly_pass_spreads.extend(audit["pass_rel_spreads"])
                    poolonly_fail_spreads.extend(audit["fail_rel_spreads"])
                    if audit["rel_spreads"]:
                        worst = max(audit["rel_spreads"])
                        if worst > worst_poolonly_rel:
                            worst_poolonly_rel = worst
                            worst_poolonly_sha = sha16
                    # The failure-attribution claims are pool-only (the
                    # geometry-validated scope, same as BR2-10/11): on
                    # composite stores the pool mapping is wrong by
                    # construction, so their sign-negative mass is not a
                    # counterexample population.
                    if audit["cop_fail"]:
                        cop_fail_by_store[sha16] += audit["cop_fail"]
                    if audit["sign_negative"]:
                        signneg_by_store[sha16] += audit["sign_negative"]
                if audit["u16_count_present"]:
                    stores_u16 += 1
                if audit["u16_u8ref_present"]:
                    stores_u16_u8ref += 1
        if audit["facet_record"]:
            files_facet += 1
            if is_l2:
                files_facet_l2 += 1
        if audit["planar_marker_record"]:
            files_planar += 1
            if is_l2:
                files_planar_l2 += 1

    corpus = poolonly + composite
    print(f"stores located: {files_with_store} | pool-only {poolonly['stores']} | composite {composite['stores']}")
    print(f"L2-pass population: {l2_total}")

    rows = []

    def add(claim, statement, label, scope, release, obs, passes, rate=None):
        if rate is None:
            rate = (passes / obs) if obs else 0.0
        rows.append(
            {
                "claim": claim,
                "statement": statement,
                "label": label,
                "scope": scope,
                "release": release,
                "observations": obs,
                "passes": passes,
                "rate": f"{rate:.6g}",
            }
        )

    # Census tie-out (TOP-04 / TOP-05 / SRF-01 detectors)
    add(
        "BR2-01_face_files_l2_pass",
        "L2-pass files with >=1 accepted 01 [41-4f] facet record (TOP-04 census detector; tie-out expect 1087/1089)",
        "fact",
        "L2-pass population",
        "all",
        l2_total,
        files_facet_l2,
    )
    add(
        "BR2-02_planar_files_l2_pass",
        "L2-pass files with >=1 accepted 01 4a/4c record (TOP-05/SRF-01 census detector; tie-out expect 856/1089)",
        "fact",
        "L2-pass population",
        "all",
        l2_total,
        files_planar_l2,
    )
    add(
        "BR2-03_face_files_corpus",
        "corpus parts with >=1 accepted facet record (TOP-04; census vocabulary row 1133/1442)",
        "fact",
        "full corpus",
        "all",
        len(manifest_parts),
        files_facet,
    )
    add(
        "BR2-04_planar_files_corpus",
        "corpus parts with >=1 accepted 01 4a/4c record (TOP-05/SRF-01; census 895/1442)",
        "fact",
        "full corpus",
        "all",
        len(manifest_parts),
        files_planar,
    )

    # Record-level laws (no index space needed — corpus-wide)
    normal_recs = corpus["normal_records"]
    add(
        "BR2-05_record_acceptance_planar",
        "accepted 01 4a/4c records under the G3 tiling law (F1) across located stores",
        "fact",
        "all located stores, census scan",
        "all",
        corpus["planar_marker_record"],
        corpus["planar_marker_record"],
    )
    add(
        "BR2-06_unit_normal",
        "normal-bearing records whose 12B f32le normal is unit within 1e-6",
        "fact",
        "all normal-bearing records corpus-wide",
        "all",
        normal_recs,
        corpus["unit_normals"],
    )
    add(
        "BR2-06b_unit_norm_max_dev",
        "max |n-1| over stored normals (rate column carries the value)",
        "fact",
        "all normal-bearing records corpus-wide",
        "all",
        1,
        1,
        rate=unit_norm_max_dev,
    )
    add(
        "BR2-07_count_structure_established",
        f"accepted records with ty>0 whose loop delimitation resolves (u8 or u16be count width); includes {corpus['resolved_triangle_list']:,} 0x49 triangle-list records whose loop/primitive semantics remain candidate (BR2-07b; carve-out in BR2-07c)",
        "fact",
        "all accepted records with ty>0",
        "all",
        corpus["count_u8"] + corpus["count_u16"] + corpus["count_variant"],
        corpus["count_u8"] + corpus["count_u16"],
    )
    add(
        "BR2-07b_triangle_list_share_resolved",
        "resolved count-law records that are 0x49 triangle-list records (n == 3*ty; loop/primitive semantics still candidate - BR2-18)",
        "fact",
        "all resolved records (u8 or u16be count width)",
        "all",
        corpus["count_u8"] + corpus["count_u16"],
        corpus["resolved_triangle_list"],
    )
    add(
        "BR2-07c_law_excluding_triangle_list",
        "the count-width law with ALL 0x49 triangle-list records carved out of the denominator (the candidate family removed)",
        "fact",
        "accepted records with ty>0, 0x49 excluded",
        "all",
        corpus["count_u8"] + corpus["count_u16"] + corpus["count_variant"] - corpus["mk_0x49"],
        corpus["count_u8"] + corpus["count_u16"] - corpus["resolved_triangle_list"],
    )
    add(
        "BR2-07e_normal_bearing_variants",
        "record-level count-law variants that are NORMAL-BEARING (the face decoder's reachable variant population; the rest of the 221 are normal-less records it never sees)",
        "fact",
        "normal-bearing records, geometry scan",
        "all",
        normal_recs,
        corpus["nb_variants"],
    )
    add(
        "BR2-07d_face_count_variant",
        "normal-bearing records whose FACE decode reports count-variant (loop structure not established at the face level; the record-level count-law variant population is 221 - BR2-07)",
        "fact",
        "normal-bearing records, geometry scan",
        "all",
        normal_recs,
        corpus[f"status_{FACE_COUNT_VARIANT}"],
    )
    add(
        "BR2-08_count_width_u16",
        "accepted records with u16be count integers (the (0,lo) byte pattern; count width independent of ref width)",
        "fact",
        "all accepted records with ty>0",
        "all",
        corpus["count_u8"] + corpus["count_u16"] + corpus["count_variant"],
        corpus["count_u16"],
    )
    add(
        "BR2-08b_u16_count_over_u8_ref",
        "u16be-count records whose references are u8 (count width is a per-record property, not inherited from the ref width)",
        "fact",
        "u16be-count records",
        "all",
        corpus["count_u16"],
        corpus["count_u16_u8ref"],
    )
    add(
        "BR2-08c_u16_count_stores",
        "located stores carrying >=1 u16be-count record, and the subset whose u16be counts sit over u8 references (the 36-store figure's denominator)",
        "fact",
        "located stores, geometry scan",
        "all",
        stores_u16,
        stores_u16_u8ref,
    )
    add(
        "BR2-09_multi_loop_faces",
        "normal-bearing records with ty>=2 (multi-loop face carriers) among normal-bearing records",
        "fact",
        "normal-bearing records (01 49/4a/4c), geometry scan",
        "all",
        normal_recs,
        corpus["ty_multi_loop"],
    )

    # Geometry claims: pool-only scope (the decodable scope)
    dec = poolonly["geometry_decodable"]
    add(
        "BR2-10_plane_coplanar_poolonly",
        "pool-only store faces: loop vertices coplanar with the stored normal (derived offset d, tol 1e-4 x scale)",
        "fact",
        "pool-only stores, geometry scan",
        "all",
        dec,
        poolonly["coplanar"],
    )
    add(
        "BR2-11_plane_oriented_poolonly",
        f"pool-only store faces: winding/Newell sign-positive vs the stored normal (CCW law, G3 F5); denominator = faces with a measured orientation candidate (signs computed: {poolonly['oriented_candidates']:,} of {dec:,} decodable in-pool faces)",
        "fact",
        "pool-only stores, geometry scan (oriented-candidate denominator)",
        "all",
        poolonly["oriented_candidates"],
        poolonly["oriented"],
    )
    if poolonly_rel_spreads:
        add(
            "BR2-12_spread_median_rel",
            "median relative plane spread (max_dev/tol; rate column carries the value)",
            "fact",
            "pool-only store faces",
            "all",
            1,
            1,
            rate=percentile(poolonly_rel_spreads, 0.5),
        )
        add(
            "BR2-12b_spread_max_rel",
            "max relative plane spread (max_dev/tol; rate column carries the value)",
            "fact",
            "pool-only store faces",
            "all",
            1,
            1,
            rate=max(poolonly_rel_spreads),
        )
        add(
            "BR2-12c_spread_p95_rel",
            "95th-percentile relative plane spread (max_dev/tol; rate column carries the value)",
            "fact",
            "pool-only store faces",
            "all",
            1,
            1,
            rate=percentile(poolonly_rel_spreads, 0.95),
        )
    if poolonly_pass_spreads:
        # The pass/fail gap is bounded by these two rows. The p95
        # (BR2-12c) is a distribution statistic, NOT the pass boundary:
        # quoting it as "the passing mass" overstates the separation by
        # three orders of magnitude.
        add(
            "BR2-12d_spread_pass_max_rel",
            "max relative plane spread over the PASSING (coplanar) pool-only faces (max_dev/tol; rate column carries the value)",
            "fact",
            "pool-only store faces, coplanar subset",
            "all",
            1,
            1,
            rate=max(poolonly_pass_spreads),
        )
    if poolonly_fail_spreads:
        add(
            "BR2-12e_spread_fail_min_rel",
            "min relative plane spread over the FAILING (non-coplanar) pool-only faces (max_dev/tol; rate column carries the value)",
            "fact",
            "pool-only store faces, non-coplanar subset",
            "all",
            1,
            1,
            rate=min(poolonly_fail_spreads),
        )
    print(
        f"worst pool-only plane counterexample: {worst_poolonly_sha} "
        f"(max_dev/tol = {worst_poolonly_rel:.6g})"
    )
    print(f"pool-only coplanar: {poolonly['coplanar']}/{poolonly['geometry_decodable']}")
    add(
        "BR2-13_composite_plane_rate",
        "composite-store in-pool faces passing the plane test (the composite index space is NOT pool-first - G3 F8 corroborated at plane level)",
        "fact",
        "composite stores, in-pool faces",
        "all",
        composite["geometry_decodable"],
        composite["coplanar"],
    )
    add(
        "BR2-14_outofpool_records",
        "normal-bearing records whose references leave the pool (composite index space + clean-store variants)",
        "fact",
        "normal-bearing records, all stores",
        "all",
        normal_recs,
        corpus["status_out-of-pool"],
    )

    # Loop-structure claims
    add(
        "BR2-15_ring_loops",
        "0x4c loops decoded as closed rings (cyclic boundary cycles, TOP-05 reading)",
        "fact",
        "loops of accepted records, geometry scan",
        "all",
        poolonly["ring_loops"] + composite["ring_loops"],
        poolonly["ring_loops"] + composite["ring_loops"],
    )
    add(
        "BR2-16_strip_loops",
        "strip-kind loops of normal-bearing records (0x49/0x4a) decoded as strip segments (not boundary cycles; normal-less 0x41/0x42 loops are outside this population and counted separately in BR2-26/26b)",
        "fact",
        "strip-kind loops of normal-bearing records (0x49/0x4a), geometry scan",
        "all",
        poolonly["strip_loops"] + composite["strip_loops"],
        poolonly["strip_loops"] + composite["strip_loops"],
    )
    add(
        "BR2-26_normal_less_strip_loops",
        "0x42 strip loops on NORMAL-LESS records under the true-loop split (outside the normal-bearing face-decode population; the G3 comparison figure, facet-semantics note §3)",
        "fact",
        "normal-less 0x42 records, geometry scan",
        "all",
        corpus["normal_less_loops_0x42"],
        corpus["normal_less_loops_0x42"],
    )
    add(
        "BR2-26b_normal_less_0x41_loops",
        "0x41 loops on NORMAL-LESS records under the true-loop split (outside the normal-bearing face-decode population; the 0x41 family's primitive role is open, so this is a loop-count reading only)",
        "fact",
        "normal-less 0x41 records, geometry scan",
        "all",
        corpus["normal_less_loops_0x41"],
        corpus["normal_less_loops_0x41"],
    )
    add(
        "BR2-17_five_byte_form",
        "accepted records on the 5-byte header form (01 mk ty b3 ff; outside BR2's marker slice)",
        "fact",
        "accepted records, geometry scan",
        "all",
        corpus["records_geometry"],
        corpus["five_byte_form"],
    )
    add(
        "BR2-25_zero_loop_records",
        "accepted records with ty == 0 (the no-loops face status' corpus population; the face decoder pins the status on a synthetic fixture - FACE_NO_LOOPS is unreachable on the corpus)",
        "fact",
        "accepted records, geometry scan",
        "all",
        corpus["records_geometry"],
        corpus["ty_zero"],
    )

    # 0x49 extension candidate. Observations and passes must come from
    # DIFFERENT counters or the rate asserts nothing: the predicates are
    # measured in BR2-18 (normal carried) and BR2-18b (n == 3*ty). The
    # CANDIDATE label belongs to the primitive/loop semantics, which no
    # rate here establishes.
    add(
        "BR2-18_triangle_list_normal_records",
        "0x49 records carrying a normal (volume anchor: both sides count the same records; the candidate content is the primitive/loop semantics, not this rate - n == 3*ty measured in BR2-18b)",
        "candidate",
        "0x49 records, geometry scan",
        "all",
        corpus["mk_0x49"],
        corpus["mk_49_normal"],
    )
    add(
        "BR2-18b_0x49_n_equals_3ty",
        "0x49 records satisfying the G3 F9/F10 byte law n == 3*ty (the triangle-list shape; measured, not assumed from the family's construction)",
        "fact",
        "0x49 records, geometry scan",
        "all",
        corpus["mk_0x49"],
        corpus["mk_49_n_equals_3ty"],
    )

    # Store-class scope rows (the 281/1,036 split the note cites)
    add(
        "BR2-19_store_class_poolonly",
        "located stores classified pool-only (store root + pool references; the geometry-validated scope of section 4)",
        "fact",
        "located stores, census scan",
        "all",
        files_with_store,
        poolonly["stores"],
    )
    add(
        "BR2-20_store_class_composite",
        "located stores classified composite (composite index space - G3 F8; per-face geometry parked on BR5)",
        "fact",
        "located stores, census scan",
        "all",
        files_with_store,
        composite["stores"],
    )

    # Failure attribution: the counts are measured here, the named/unnamed
    # split is a CITATION to G3's note (G3_NAMED_STORES). One store alone
    # does not reproduce the set - attribution needs the unfiltered run.
    cop_fail_total = sum(cop_fail_by_store.values())
    cop_fail_named = sum(n for s, n in cop_fail_by_store.items() if s in G3_NAMED_STORES)
    signneg_total = sum(signneg_by_store.values())
    signneg_named = sum(n for s, n in signneg_by_store.items() if s in G3_NAMED_STORES)
    add(
        "BR2-21_cop_fail_stores_named",
        "stores carrying >=1 coplanarity-failing pool-only face, and the share of them G3 already names (facet-semantics note §3)",
        "fact",
        "pool-only stores, geometry scan",
        "all",
        len(cop_fail_by_store),
        sum(1 for s in cop_fail_by_store if s in G3_NAMED_STORES),
    )
    add(
        "BR2-21b_cop_fail_faces_named",
        "coplanarity-failing pool-only faces, and the share sitting on G3-named stores (per-store counts in the BR2-23 block)",
        "fact",
        "pool-only stores, geometry scan",
        "all",
        cop_fail_total,
        cop_fail_named,
    )
    add(
        "BR2-22_signneg_stores_named",
        "stores carrying >=1 sign-negative pool-only face (the stored output, NOT a claim of anti-parallelism), and the share of them G3 already names",
        "fact",
        "pool-only stores, geometry scan",
        "all",
        len(signneg_by_store),
        sum(1 for s in signneg_by_store if s in G3_NAMED_STORES),
    )
    add(
        "BR2-22b_signneg_faces_named",
        "sign-negative pool-only faces, and the share sitting on G3-named stores (per-store counts in the BR2-24 block)",
        "fact",
        "pool-only stores, geometry scan",
        "all",
        signneg_total,
        signneg_named,
    )
    for sha16, n in sorted(cop_fail_by_store.items()):
        add(
            f"BR2-23_cop_fail_store_{sha16}",
            f"coplanarity-failing pool-only faces on store {sha16} ({g3_named_class(sha16)}; volume anchor)",
            "fact",
            "pool-only stores, geometry scan",
            "all",
            n,
            n,
        )
    for sha16, n in sorted(signneg_by_store.items()):
        add(
            f"BR2-24_signneg_store_{sha16}",
            f"sign-negative pool-only faces on store {sha16} ({g3_named_class(sha16)}; volume anchor)",
            "fact",
            "pool-only stores, geometry scan",
            "all",
            n,
            n,
        )
    print(f"coplanarity failures: {cop_fail_total} faces on {len(cop_fail_by_store)} stores")
    for sha16, n in sorted(cop_fail_by_store.items()):
        print(f"  cop-fail {sha16} {n}  [{g3_named_class(sha16)}]")
    print(f"sign-negative faces: {signneg_total} on {len(signneg_by_store)} stores")
    for sha16, n in sorted(signneg_by_store.items()):
        print(f"  sign-negative {sha16} {n}  [{g3_named_class(sha16)}]")

    print(f"\nclaims rows: {len(rows)}")
    return rows


def claims_filename(args) -> str:
    """The claims file name for this run.

    The all-corpus run owns ``br2-planar-claims.csv``. A filtered run
    (``--sha16`` / ``--limit``) gets a DISTINCT name so the documented
    reproduction command cannot replace the committed all-corpus artifact
    with a filtered subset (the Phase-5-retro clobber failure mode,
    dispatch-recipes.md:122-132).
    """
    if args.sha16:
        return f"br2-planar-claims-sha16-{'-'.join(sorted(args.sha16))}.csv"
    if args.limit:
        return f"br2-planar-claims-limit-{args.limit}.csv"
    return "br2-planar-claims.csv"


def write_claims(rows: list[dict], out_dir: Path, filename: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CLAIMS_FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {path}")
    return path


def _selftest() -> int:
    """The synthetic negative fixtures for every discriminating edge."""
    from catpart.brep.planar import (
        LoopReading,
        PlaneEquation,
        fit_plane,
        newell_normal,
        record_true_loops,
    )
    from catpart.geometry.facets import FacetRecord, parse_facet_record

    def rec(marker, ty, counts, refs, normal, width=1, header_len=4, offset=0):
        return FacetRecord(
            offset=offset,
            marker=marker,
            type=ty,
            header_len=header_len,
            n=len(refs),
            width=width,
            counts=tuple(counts),
            refs=tuple(refs),
            end=offset + 100,
            normal=normal,
        )

    failures = []

    def check(name, cond):
        print(f"  {'PASS' if cond else 'FAIL'} {name}")
        if not cond:
            failures.append(name)

    # 1. Coplanar positive: unit-z plane, square ring CCW from +z -> ok,
    #    coplanar, oriented.
    pool = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
    lex = [0, 1, 2, 3]
    r = rec(0x4C, 1, (4,), (0, 1, 2, 3), (0.0, 0.0, 1.0))
    face = decode_planar_face(pool, lex, r)
    check("ring coplanar+oriented", face.status == FACE_OK and face.plane.coplanar and face.oriented)

    # 2. SRF-01 negative: points NOT on the stored-normal plane (cylinder
    #    patch with a plane normal stamped on it) -> coplanar False.
    pool_cyl = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 3.0), (1.0, 0.0, 3.0), (0.0, 0.0, 9.0), (1.0, 0.0, 9.0)]
    lex_cyl = [0, 1, 2, 3, 4, 5]
    r = rec(0x4A, 1, (6,), (0, 1, 2, 3, 4, 5), (0.0, 0.0, 1.0), width=1)
    face = decode_planar_face(pool_cyl, lex_cyl, r)
    check(
        "non-coplanar strip rejected (SRF-01 edge)",
        face.status == FACE_OK and face.plane is not None and not face.plane.coplanar,
    )

    # 3. TOP-05 count-width edge: u16be counts (0, 4) -> ONE loop of 4,
    #    not the byte-parse's phantom-empty + 4.
    r = rec(0x4A, 1, (0, 4), (0, 1, 2, 3), (0.0, 0.0, 1.0))
    cs = count_structure(r)
    loops = record_true_loops(r)
    check(
        "u16 count structure resolves to one loop",
        cs is not None and cs.count_width == 2 and cs.lengths == (4,) and loops == [(0, 1, 2, 3)],
    )

    # 4. Count-variant negative: ty=1 but counts (2, 3) -> None (structure
    #    NOT established; no guessing), face status count-variant.
    r = rec(0x4A, 1, (2, 3), (0, 1, 2, 3, 4), (0.0, 0.0, 1.0))
    face = decode_planar_face(pool_cyl, lex_cyl, r)
    check(
        "count variant not guessed (TOP-05 edge)",
        count_structure(r) is None and face.status == FACE_COUNT_VARIANT,
    )

    # 5. Orientation negative: reversed ring order -> Newell anti-parallel.
    r = rec(0x4C, 1, (4,), (3, 2, 1, 0), (0.0, 0.0, 1.0))
    face = decode_planar_face(pool, lex, r)
    check("reversed ring not oriented", face.status == FACE_OK and face.oriented is False)

    # 6. Tiling negative: counts do not tile the record (n=4, one count
    #    byte 4, but only 3 ref bytes before the next header) -> no parse.
    data = b"\x01\x4a\x01\xff" + struct.pack("<I", 4) + struct.pack("<fff", 0, 0, 1) + b"\x04" + b"\x00\x00\x00"
    parsed = parse_facet_record(data, 0, len(data), len(data))
    check("non-tiling record rejected (F1 edge)", parsed is None)

    # 7. Unit-normal edge: a scaled normal (0,0,2) is flagged (|n|-1 = 1).
    dev = normal_unit_deviation((0.0, 0.0, 2.0))
    check("non-unit normal flagged", abs(dev - 1.0) <= 1e-9)

    # 8. Out-of-pool negative: refs beyond the pool -> no geometry guessed.
    r = rec(0x4A, 1, (4,), (0, 1, 2, 99), (0.0, 0.0, 1.0))
    face = decode_planar_face(pool, lex, r)
    check(
        "out-of-pool refs not validated",
        face.status == FACE_OUT_OF_POOL and face.plane is None and face.oriented is None,
    )

    # 9. fit_plane/newell sanity: offset d of the unit square ring.
    eq = fit_plane([(0.0, 0.0, 2.0), (1.0, 0.0, 2.0), (1.0, 1.0, 2.0)], (0.0, 0.0, 1.0))
    check("plane offset derived d=-2", eq is not None and abs(eq.offset + 2.0) <= 1e-12)
    nv = newell_normal([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)])
    check("newell +z for CCW ring", nv[2] > 0.0)

    # 10. LoopReading/PlaneEquation constructional sanity (frozen dtypes).
    check(
        "dataclasses frozen",
        LoopReading(length=3, kind="ring", closed_cycle=True, degenerate=False).length == 3
        and PlaneEquation(normal=(0, 0, 1), offset=0.0, max_dev=0.0, tol=1e-4).coplanar,
    )

    # 11. u16 counts over u16 references (the missing combination: the
    #     count width must not be read off the ref width in EITHER
    #     direction).
    r = rec(0x4A, 1, (0, 4), (0, 1, 2, 3), (0.0, 0.0, 1.0), width=2)
    cs = count_structure(r)
    check(
        "u16 counts over u16 refs resolve to one loop",
        cs is not None and cs.count_width == 2 and cs.lengths == (4,) and record_true_loops(r) == [(0, 1, 2, 3)],
    )

    # 12. TOP-04 marker blindness (the §6 declared non-discrimination, now
    #     with a fixture): a normal-less 0x42 record in-pool is FACE_OK with
    #     no normal and no plane - the status does NOT discriminate a face.
    r = rec(0x42, 1, (3,), (0, 1, 2), None)
    face = decode_planar_face(pool, lex, r)
    check(
        "marker-blind 0x42 record decodes as an ok face without geometry",
        face.status == FACE_OK and face.normal is None and face.plane is None and face.oriented is None,
    )

    # 13. Marker blindness across markers: 0x42 and 0x44 differ only in the
    #     marker byte, so every decoded field except the marker must agree.
    f42 = decode_planar_face(pool, lex, rec(0x42, 1, (3,), (0, 1, 2), None))
    f44 = decode_planar_face(pool, lex, rec(0x44, 1, (3,), (0, 1, 2), None))
    check(
        "0x42 and 0x44 records decode identically (marker-blind)",
        (f42.status, f42.plane, f42.oriented, f42.loops, f42.count_width)
        == (f44.status, f44.plane, f44.oriented, f44.loops, f44.count_width),
    )

    # 14. No-loops status pin: a ty=0 record (n=0, k=0 is grammar-legal)
    #     reports no-loops, never an "ok face". Unreachable on the corpus
    #     (BR2-25), so the fixture is the only witness.
    r = rec(0x4A, 0, (), (), (0.0, 0.0, 1.0))
    face = decode_planar_face(pool, lex, r)
    check("ty=0 record reports no-loops", face.status == FACE_NO_LOOPS and face.plane is None)

    print(f"selftest: {len(failures)} failures")
    return 1 if failures else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus-root", default=DEFAULT_CORPUS_ROOT)
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    ap.add_argument("--limit", type=int, default=0, help="first N manifest parts only")
    ap.add_argument("--sha16", action="append", default=[], help="sha16 prefix filter (repeatable)")
    ap.add_argument("--selftest", action="store_true", help="run the synthetic negative fixtures")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(_selftest())
    rows = run_corpus(args)
    write_claims(rows, Path(args.out_dir), claims_filename(args))


if __name__ == "__main__":
    main()
