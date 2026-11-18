#!/usr/bin/env python3
"""BR6 TOP-03 corpus decoder: closed manifold face sets (Ticket #58, Spec G #47).

Decodes the TOP-03 Shell construct corpus-wide over the manifest's part
population (the census population, 1,442 parts) with the L2-pass join
(docs/evidence/data/stage15-identity-export-files.csv, 1,089 files).

A shell is not a stored record. The decode is the PARTITION of the
accepted facet records into edge-connected face components, with a
component resolving as a shell when every undirected triangle edge it
uses is used exactly twice (the census signature: "closed manifold face
sets with boundary_edge_count = 0"). The byte-level carrier is the BR2
facet record (its grammar is cited, never re-derived); the partition
law lives in ``catpart.brep.shell``.

Measured here:

1. Census tie-out — files carrying face records (the census label's own
   detector, which fires on ``facets_total > 0`` and does NOT
   discriminate a shell).
2. The shell resolution — files/parts/stores that actually partition
   into >= 1 closed manifold shell, on the pool-only (placeable) scope.
3. The ceiling — composite stores (references leave the pool, G3 F8),
   out-of-pool face records on pool-only stores, and accepted records
   on markers without an established primitive reading.

Outputs docs/evidence/data/br6-shell-claims.csv (per-claim rates —
every figure the evidence note's prose cites) and a stdout tie-out
table. Corpus binaries are read READ-ONLY from the MAIN checkout
(--corpus-root, never copied into the repo tree, never committed).

Detector honesty: the synthetic negative fixtures for every
discriminating edge run via ``--selftest`` (no corpus needed) and live
pinned in tests/test_brep_shell.py.

Reproduction (deterministic, manifest order, stdlib only):
    LD_LIBRARY_PATH=/usr/lib python -I scripts/triage/decode_brep_shell.py
"""

from __future__ import annotations

import argparse
import csv
import mmap
import sys
from collections import Counter
from pathlib import Path

from catpart.brep.shell import (
    SHELL_CLOSED,
    SHELL_NON_MANIFOLD,
    SHELL_OPEN,
    decode_shells,
)
from catpart.geometry import facets, pool, store

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "manifests" / "corpus-manifest.csv"
L2_STAGE15 = REPO_ROOT / "docs" / "evidence" / "data" / "stage15-identity-export-files.csv"
OUT_DIR = REPO_ROOT / "docs" / "evidence" / "data"
DEFAULT_CORPUS_ROOT = "/home/alan/Documents/Repos/catpart-parser"

CLAIMS_FIELDS = [
    "claim",
    "statement",
    "label",
    "scope",
    "release",
    "observations",
    "passes",
    "rate",
    "value",
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


def _unread_stats(records, pool_len: int) -> tuple[int, int, int]:
    """(unread records, count-grammar holds, references pass the pool).

    The unread class is every accepted record on a marker outside the
    pinned soup family (measured corpus-wide as marker 0x44 only). Its
    count-grammar figure is ``n == sum(counts)`` — the facet frame the
    parser already enforced — and its pool figure is the number whose
    references run past the pool end (the composite index space)."""
    unread = [r for r in records if r.marker not in facets.SOUP_MARKERS]
    grammar = sum(1 for r in unread if r.n == sum(r.counts))
    past_pool = sum(1 for r in unread if r.refs and max(r.refs) >= pool_len)
    return len(unread), grammar, past_pool


def audit_part(mm) -> dict:
    """One part's TOP-03 audit — the per-file counters feeding the claims."""
    out = {
        "has_store": False,
        "store_class": "",
        "edge_group": False,  # an 01 02 topology-table group is present
        "f8_opener": False,  # an ff.. trailer opener is present (G3 F8)
        "records": 0,  # accepted 01 [41-4f] records (any marker)
        "soup_faces": 0,  # accepted records on the pinned soup markers
        "unread_markers": 0,  # accepted records outside the soup markers
        "unread_grammar": 0,  # unread records with n == sum(count bytes)
        "unread_out_of_pool": 0,  # unread records whose refs pass the pool
        "shells": 0,
        "closed": 0,
        "open": 0,
        "non_manifold": 0,
        "closed_oriented": 0,
        "closed_vol_pos": 0,
        "closed_vol_neg": 0,
        "multi_closed": False,  # >= 2 closed shells in one store
        "all_closed": False,
        "no_placeable": False,  # face records exist but none entered a component
        "placed_faces": 0,
        "unplaced_faces": 0,
        "degenerate_faces": 0,
        "max_edge_degree": 0,
    }
    try:
        span = locate_store(mm)
    except Exception:
        span = None
    if span is None:
        return out
    out["has_store"] = True

    # Census tie-out scan FIRST and unconditionally (the census counts
    # facet records even where the pool walk raises).
    scan = facets.scan_facets(mm, span.body_lo, span.body_hi)
    out["records"] = len(scan.records)

    try:
        groups, kinds = pool.scan_pool_groups(mm, span.body_lo, span.body_hi)
    except Exception:
        out["store_class"] = "pool-scan-failed"
        return out
    flat = [v for g in groups for v in g.vertices]
    composite = pool.has_composite_space(kinds)
    out["store_class"] = "composite" if composite else "pool-only"
    out["edge_group"] = any(k == pool.EDGE_SUBKIND for k in kinds)
    out["f8_opener"] = any(k[:1] == b"\xff" for k in kinds)
    if composite:
        # Geometry is not placeable across the composite index space
        # (G3 F8): no shell is claimed, the record count is the ceiling.
        out["soup_faces"] = sum(1 for r in scan.records if r.marker in facets.SOUP_MARKERS)
        (
            out["unread_markers"],
            out["unread_grammar"],
            out["unread_out_of_pool"],
        ) = _unread_stats(scan.records, len(flat))
        return out

    # Pool-only stores: the store-width context applies to the geometry
    # scan (F1w as corrected 2026-11-10 #35) — the record population
    # the partition actually walks.
    gscan = facets.scan_facets(mm, span.body_lo, span.body_hi, clean_store=True)
    out["records"] = len(gscan.records)
    shells = decode_shells(flat, gscan)
    out["soup_faces"] = shells.faces
    (
        out["unread_markers"],
        out["unread_grammar"],
        out["unread_out_of_pool"],
    ) = _unread_stats(gscan.records, len(flat))
    out["placed_faces"] = shells.placed_faces
    out["unplaced_faces"] = shells.unplaced_faces
    out["degenerate_faces"] = shells.degenerate_faces
    out["all_closed"] = shells.all_faces_closed
    out["multi_closed"] = len(shells.closed_shells) >= 2
    out["no_placeable"] = shells.faces > 0 and not shells.shells
    for sh in shells.shells:
        out["shells"] += 1
        out["max_edge_degree"] = max(out["max_edge_degree"], sh.max_edge_degree)
        if sh.status == SHELL_CLOSED:
            out["closed"] += 1
            if sh.oriented:
                out["closed_oriented"] += 1
            if sh.signed_volume > 0.0:
                out["closed_vol_pos"] += 1
            elif sh.signed_volume < 0.0:
                out["closed_vol_neg"] += 1
        elif sh.status == SHELL_OPEN:
            out["open"] += 1
        elif sh.status == SHELL_NON_MANIFOLD:
            out["non_manifold"] += 1
    return out


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
    print(f"BR6 TOP-03 shell decode over {len(manifest_parts)} parts (corpus root: {corpus_root})")

    corpus = Counter()
    poolonly = Counter()
    composite = Counter()
    files_with_store = 0
    files_facet = files_shell = 0
    files_candidate = files_candidate_l2 = 0
    files_facet_l2 = files_shell_l2 = 0
    l2_total = 0

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
                    "soup_faces",
                    "unread_markers",
                    "unread_grammar",
                    "unread_out_of_pool",
                    "shells",
                    "closed",
                    "open",
                    "non_manifold",
                    "closed_oriented",
                    "closed_vol_pos",
                    "closed_vol_neg",
                    "placed_faces",
                    "unplaced_faces",
                    "degenerate_faces",
                ):
                    bucket[key] += audit[key]
                bucket["all_closed"] += audit["all_closed"]
                bucket["multi_closed"] += audit["multi_closed"]
                bucket["mixed_closure"] += audit["closed"] > 0 and not audit["all_closed"]
                bucket["no_placeable"] += audit["no_placeable"]
                bucket["no_faces"] += audit["soup_faces"] == 0
                bucket["edge_group"] += audit["edge_group"]
                bucket["f8_opener"] += audit["f8_opener"]
                bucket["max_edge_degree"] = max(bucket["max_edge_degree"], audit["max_edge_degree"])
            elif audit["store_class"] == "pool-scan-failed":
                corpus["pool_scan_failed"] += 1
        if audit["records"]:
            files_facet += 1
            if is_l2:
                files_facet_l2 += 1
        if audit["soup_faces"]:
            files_candidate += 1
            if is_l2:
                files_candidate_l2 += 1
        if audit["closed"]:
            files_shell += 1
            if is_l2:
                files_shell_l2 += 1
        if not audit["has_store"]:
            corpus["no_store"] += 1

    print(
        f"stores located: {files_with_store} | pool-only {poolonly['stores']} | "
        f"composite {composite['stores']} | pool-scan-failed {corpus['pool_scan_failed']}"
    )
    print(f"L2-pass population: {l2_total}")
    print(
        f"files with face records: {files_facet} | face candidates: {files_candidate} | "
        f"files with >=1 closed shell: {files_shell}"
    )

    rows = []

    def add(claim, statement, label, scope, release, obs, passes, rate=None, value=""):
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
                "value": value,
            }
        )

    # ---- Census tie-out (the label's own detector: facets_total > 0,
    # ANY accepted 01 [41-4f] record, exactly as the census counts it)
    add(
        "BR6S-01_facet_files_l2_pass",
        "L2-pass files with >=1 accepted facet record of any marker (the census TOP-03/TOP-04 detector; tie-out expect 1087/1089)",
        "fact",
        "L2-pass population",
        "all",
        l2_total,
        files_facet_l2,
    )
    add(
        "BR6S-02_facet_files_corpus",
        "corpus parts with >=1 accepted facet record of any marker (the census TOP-03 label carrier; vocabulary row 1133/1442)",
        "fact",
        "full corpus",
        "all",
        len(manifest_parts),
        files_facet,
    )
    add(
        "BR6S-02b_face_candidate_files_corpus",
        "corpus parts with >=1 face-candidate record on a pinned soup marker (the population that can enter the shell partition)",
        "fact",
        "full corpus",
        "all",
        len(manifest_parts),
        files_candidate,
    )
    add(
        "BR6S-02c_face_candidate_files_l2_pass",
        "L2-pass files with >=1 face-candidate record on a pinned soup marker",
        "fact",
        "L2-pass population",
        "all",
        l2_total,
        files_candidate_l2,
    )

    # ---- The shell resolution (the new measurement)
    add(
        "BR6S-03_shell_files_l2_pass",
        "L2-pass files resolving to >=1 closed manifold shell (TOP-03 at the closure law; NOT the census detector)",
        "fact",
        "L2-pass population",
        "all",
        l2_total,
        files_shell_l2,
    )
    add(
        "BR6S-04_shell_files_corpus",
        "corpus parts resolving to >=1 closed manifold shell",
        "fact",
        "full corpus",
        "all",
        len(manifest_parts),
        files_shell,
    )
    add(
        "BR6S-05_shell_rate_on_label_population",
        "shell-closure rate conditioned on the census label population (parts with >=1 closed shell / parts with any accepted facet record) - the census rate is detector-conditioned, this row is the construct rate",
        "fact",
        "parts with any accepted facet record",
        "all",
        files_facet,
        files_shell,
    )
    add(
        "BR6S-05b_shell_rate_on_candidate_population",
        "shell-closure rate conditioned on the face-candidate population (parts with >=1 closed shell / parts with a pinned-marker face record)",
        "fact",
        "parts with face-candidate records",
        "all",
        files_candidate,
        files_shell,
    )

    # ---- Store-class scopes (the ceiling)
    add(
        "BR6S-06_located_stores",
        "located nested stores (BR2-19/20 anchor 1317)",
        "fact",
        "located stores, census scan",
        "all",
        len(manifest_parts),
        files_with_store,
    )
    add(
        "BR6S-07_poolonly_stores",
        "located stores classified pool-only (the shell-decodable scope)",
        "fact",
        "located stores",
        "all",
        files_with_store,
        poolonly["stores"],
    )
    add(
        "BR6S-08_composite_stores",
        "located stores classified composite (references leave the pool - G3 F8; no shell claimed)",
        "fact",
        "located stores",
        "all",
        files_with_store,
        composite["stores"],
    )
    add(
        "BR6S-09_poolonly_partition_stores",
        "pool-only stores with >=1 face placed in a component (the partition population: face-candidate records minus unplaced/degenerate ones)",
        "fact",
        "pool-only stores carrying face-candidate records",
        "all",
        poolonly["stores"] - poolonly["no_faces"],
        poolonly["stores"] - poolonly["no_placeable"] - poolonly["no_faces"],
    )
    add(
        "BR6S-10_poolonly_all_closed",
        "pool-only partition stores where every placed face lies in a closed manifold shell and no face record is unplaced or degenerate (fully resolved stores)",
        "fact",
        "pool-only stores with face records",
        "all",
        poolonly["stores"] - poolonly["no_faces"],
        poolonly["all_closed"],
    )
    add(
        "BR6S-10b_poolonly_partition_stores_all_closed",
        "pool-only partition stores (>=1 face placed in a component) that close completely - the closure rate on the partition population, not on every face-bearing store",
        "fact",
        "pool-only partition stores",
        "all",
        poolonly["stores"] - poolonly["no_placeable"] - poolonly["no_faces"],
        poolonly["all_closed"],
    )
    add(
        "BR6S-11_poolonly_multi_closed",
        "pool-only stores with >=2 closed shells (multi-shell bodies: outer shell plus cavity/void shells)",
        "fact",
        "pool-only stores with face records",
        "all",
        poolonly["stores"] - poolonly["no_faces"],
        poolonly["multi_closed"],
    )
    add(
        "BR6S-11b_poolonly_mixed_closure",
        "pool-only stores mixing a closed shell with an open/non-manifold/unplaced remainder (expected 0 if closure is store-coherent)",
        "fact",
        "pool-only stores with face records",
        "all",
        poolonly["stores"] - poolonly["no_faces"],
        poolonly["mixed_closure"],
    )
    add(
        "BR6S-12_poolonly_no_placeable",
        "pool-only stores with face records but no component placed (every face record out-of-pool or degenerate)",
        "fact",
        "pool-only stores with face records",
        "all",
        poolonly["stores"] - poolonly["no_faces"],
        poolonly["no_placeable"],
    )

    # ---- Component-level laws (volume anchors)
    total_shells = poolonly["shells"] + composite["shells"]
    add(
        "BR6S-13_closed_shells",
        "closed manifold shell components decoded (volume anchor; every undirected edge used exactly twice)",
        "fact",
        "face components, pool-only stores",
        "all",
        total_shells,
        poolonly["closed"] + composite["closed"],
    )
    add(
        "BR6S-14_open_components",
        "open face components (at least one boundary edge used once; G3 F6's open-shell class)",
        "fact",
        "face components, pool-only stores",
        "all",
        total_shells,
        poolonly["open"] + composite["open"],
    )
    add(
        "BR6S-15_nonmanifold_components",
        "non-manifold face components (an undirected edge used more than twice)",
        "fact",
        "face components, pool-only stores",
        "all",
        total_shells,
        poolonly["non_manifold"] + composite["non_manifold"],
    )
    closed_total = poolonly["closed"] + composite["closed"]
    add(
        "BR6S-16_closed_shells_oriented",
        "closed shells with a consistent winding (no directed edge traversed twice)",
        "fact",
        "closed shell components",
        "all",
        closed_total,
        poolonly["closed_oriented"] + composite["closed_oriented"],
    )
    add(
        "BR6S-17_closed_shells_positive_volume",
        "closed shells whose signed volume is positive under the exported winding (outward convention)",
        "fact",
        "closed shell components",
        "all",
        closed_total,
        poolonly["closed_vol_pos"] + composite["closed_vol_pos"],
    )
    add(
        "BR6S-18_closed_shells_negative_volume",
        "closed shells whose signed volume is negative under the exported winding (inward winding: the convention does not hold for these)",
        "fact",
        "closed shell components",
        "all",
        closed_total,
        poolonly["closed_vol_neg"] + composite["closed_vol_neg"],
    )

    # ---- Partition coverage and the explicit ceilings
    pool_faces = poolonly["soup_faces"]
    add(
        "BR6S-19_faces_placed",
        "face-candidate records placed into a component (partition coverage on the decodable scope)",
        "fact",
        "face-candidate records, pool-only stores",
        "all",
        pool_faces,
        poolonly["placed_faces"],
    )
    add(
        "BR6S-20_faces_unplaced",
        "face-candidate records whose references leave the pool on pool-only stores (counted, not guessed; the within-scope ceiling)",
        "fact",
        "face-candidate records, pool-only stores",
        "all",
        pool_faces,
        poolonly["unplaced_faces"],
    )
    add(
        "BR6S-21_faces_degenerate",
        "face-candidate records whose primitive reading yields no non-degenerate triangle (no component possible)",
        "fact",
        "face-candidate records, pool-only stores",
        "all",
        pool_faces,
        poolonly["degenerate_faces"],
    )
    add(
        "BR6S-22_unread_marker_records",
        "accepted records on marker 0x44 (G3 F9's open primitive reading), excluded from the partition; every one sits on a composite store (BR6S-22b)",
        "fact",
        "accepted records, located stores",
        "all",
        poolonly["records"] + composite["records"],
        poolonly["unread_markers"] + composite["unread_markers"],
    )
    add(
        "BR6S-22b_unread44_composite_only",
        "the 0x44 records that sit on composite stores - the entire unread population, none on the 281 pool-only stores",
        "fact",
        "accepted records on marker 0x44",
        "all",
        poolonly["unread_markers"] + composite["unread_markers"],
        composite["unread_markers"],
    )
    add(
        "BR6S-22c_unread44_count_grammar",
        "0x44 records whose n equals the sum of their count bytes (the shared facet record grammar: the record frame is the facet frame)",
        "fact",
        "accepted records on marker 0x44",
        "all",
        poolonly["unread_markers"] + composite["unread_markers"],
        poolonly["unread_grammar"] + composite["unread_grammar"],
    )
    add(
        "BR6S-22d_unread44_out_of_pool",
        "0x44 records whose references run past the pool end (the composite index space - not placeable, so the marker cannot join the partition regardless of its primitive reading)",
        "fact",
        "accepted records on marker 0x44",
        "all",
        poolonly["unread_markers"] + composite["unread_markers"],
        poolonly["unread_out_of_pool"] + composite["unread_out_of_pool"],
    )
    add(
        "BR6S-23_composite_face_records",
        "face-candidate records on composite stores (the ceiling if the composite index space decodes: G3 F8, still open after BR5)",
        "fact",
        "face-candidate records, composite stores",
        "all",
        composite["soup_faces"],
        composite["soup_faces"],
    )
    add(
        "BR6S-23b_accepted_record_accounting_identity",
        "ACCOUNTING IDENTITY, not an independent check (records = soup + unread by construction): 2042 + 116057 + 708 = 118807, leaving 0 residual records that could carry shell identity; the independent anchor is BR2's accepted-record volume, 118807 (BR2-07/BR2-08)",
        "fact",
        "accepted records, located stores",
        "all",
        poolonly["records"] + composite["records"],
        poolonly["soup_faces"]
        + composite["soup_faces"]
        + poolonly["unread_markers"]
        + composite["unread_markers"],
    )
    add(
        "BR6S-24_poolonly_edge_groups",
        "pool-only stores carrying an 01 02 pool-group edge table (the composite index-space marker; 0 by construction, since the pool-only/composite split is the same F8 predicate - the detector's positive control is BR6S-24c)",
        "fact",
        "pool-only stores",
        "all",
        poolonly["stores"],
        poolonly["edge_group"],
    )
    add(
        "BR6S-24b_poolonly_f8_opener",
        "pool-only stores carrying any G3 F8 composite-space marker (01 02 edge group or ff trailer opener) - 0 by construction, recorded so the pool-only scope's definition is explicit",
        "fact",
        "pool-only stores",
        "all",
        poolonly["stores"],
        poolonly["edge_group"] + poolonly["f8_opener"],
    )
    add(
        "BR6S-24c_composite_edge_groups",
        "composite stores carrying an 01 02 pool-group edge table (the detector positive control: the 01 02 detector does fire, on the composite scope)",
        "fact",
        "composite stores",
        "all",
        composite["stores"],
        composite["edge_group"],
    )
    add(
        "BR6S-24d_composite_f8_openers",
        "composite stores carrying an ff trailer opener (G3 F8's second composite-space marker; the second half of the detector positive control)",
        "fact",
        "composite stores",
        "all",
        composite["stores"],
        composite["f8_opener"],
    )
    add(
        "BR6S-25_max_edge_degree",
        "max undirected edge usage over all decoded components on pool-only stores (the value column carries the measurement: 2 = manifold everywhere; the rate is the share of components at or below degree 2)",
        "fact",
        "face components, pool-only stores",
        "all",
        total_shells,
        total_shells - (poolonly["non_manifold"] + composite["non_manifold"]),
        value=poolonly["max_edge_degree"],
    )
    add(
        "BR6S-26_pool_scan_failures",
        "parts whose pool walk raised (malformed pool group/vertex; excluded from the class split, never guessed)",
        "fact",
        "full corpus",
        "all",
        len(manifest_parts),
        corpus["pool_scan_failed"],
    )

    print(f"\nclaims rows: {len(rows)}")
    return rows


def write_claims(rows: list[dict], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "br6-shell-claims.csv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CLAIMS_FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {path}")
    return path


def _facets(records):
    """A one-store scan wrapper for the synthetic fixtures."""
    return facets.FacetScan(
        candidates=len(records),
        records=tuple(records),
        unresolved_candidates=0,
        skipped_markers={},
    )


def _rec(offset, refs, marker=0x4C, normal=(0.0, 0.0, 1.0)):
    return facets.FacetRecord(
        offset=offset,
        marker=marker,
        type=1,
        header_len=4,
        n=len(refs),
        width=1,
        counts=(len(refs),),
        refs=tuple(refs),
        end=offset + 100,
        normal=normal,
    )


def _selftest() -> int:
    """The synthetic fixtures for every discriminating edge of the shell
    partition: two positives pin the law (closed tetrahedron, volume) and
    the nine negatives pin one discrimination each."""
    failures = []

    def check(name, cond):
        print(f"  {'PASS' if cond else 'FAIL'} {name}")
        if not cond:
            failures.append(name)

    def shells_of(pool_pts, face_walk_refs):
        """Decode faces given in POOL WALK order (the reader's view).

        The record grammar stores LEXICOGRAPHIC RANKS (G3 F2/C8), so the
        fixture helper maps walk positions to ranks exactly as a writer
        would; every fixture below is written in walk order, which keeps
        the geometry checks (volume, winding) readable.
        """
        lex = facets.lex_rank_map(pool_pts)
        rank = {walk: r for r, walk in enumerate(lex)}
        recs = [_rec(10 * i, tuple(rank[w] for w in f)) for i, f in enumerate(face_walk_refs)]
        return decode_shells(pool_pts, _facets(recs))

    # A unit tetrahedron, outward-wound faces (right-hand rule).
    tetra_pool = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
    tetra_refs = [(0, 2, 1), (0, 1, 3), (1, 2, 3), (0, 3, 2)]
    shells = shells_of(tetra_pool, tetra_refs)
    check(
        "closed tetrahedron is one shell",
        len(shells.shells) == 1
        and shells.shells[0].is_shell
        and shells.shells[0].oriented
        and shells.all_faces_closed,
    )
    check("tetra volume 1/6, positive", abs(shells.shells[0].signed_volume - 1.0 / 6.0) <= 1e-12)

    # Negative 1 — closed but inconsistently wound: flipping one face
    # breaks the directed-edge pairing, NOT the closure.
    flipped = tetra_refs[:3] + [(0, 2, 3)]
    shells_flipped = shells_of(tetra_pool, flipped)
    check(
        "closed is not oriented (inverted face)",
        shells_flipped.shells[0].is_shell and not shells_flipped.shells[0].oriented,
    )

    # Negative 2 — shell is not the B-rep shell: a closed octahedron (a
    # tessellated sphere cap has the same signature) is one closed
    # component and decodes identically.
    oct_pool = [
        (0.0, 0.0, 1.0),
        (0.0, 0.0, -1.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (-1.0, 0.0, 0.0),
        (0.0, -1.0, 0.0),
    ]
    oct_faces = [
        (0, 2, 3),
        (0, 3, 4),
        (0, 4, 5),
        (0, 5, 2),
        (1, 3, 2),
        (1, 4, 3),
        (1, 5, 4),
        (1, 2, 5),
    ]
    shells_oct = shells_of(oct_pool, oct_faces)
    check(
        "closed octahedron resolves as one shell (no B-rep discrimination)",
        len(shells_oct.shells) == 1 and shells_oct.shells[0].is_shell,
    )

    # Negative 3 — adjacency is edge-sharing, not vertex contact: two
    # tetrahedra that share exactly ONE VERTEX (the origin) are TWO
    # shells. A vertex-proximity union-find would merge them; the
    # edge-keyed partition must not.
    two_pool = tetra_pool + [(1.0, 1.0, 1.0), (1.0, 1.0, 0.0), (1.0, 0.0, 1.0)]
    two_faces = tetra_refs + [(0, 4, 5), (0, 5, 6), (0, 6, 4), (4, 6, 5)]
    shells_two = shells_of(two_pool, two_faces)
    check(
        "vertex-sharing tetrahedra are two shells (edge adjacency, not vertex proximity)",
        len(shells_two.shells) == 2
        and len(shells_two.closed_shells) == 2
        and all(s.boundary_edges == 0 for s in shells_two.shells),
    )

    # Negative 4 — a reversed tetrahedron reports NEGATIVE signed volume:
    # the sign is a measurement, never a role label.
    reversed_refs = [tuple(reversed(f)) for f in tetra_refs]
    shells_rev = shells_of(tetra_pool, reversed_refs)
    check(
        "reversed tetrahedron: closed, negative volume",
        shells_rev.shells[0].is_shell and shells_rev.shells[0].signed_volume < 0.0,
    )

    # Negative 5 — out-of-pool references are counted, never guessed:
    # one record exceeds the pool -> unplaced, no component.
    bad = [_rec(0, (0, 1, 2)), _rec(100, (0, 1, 99))]
    shells_bad = decode_shells(tetra_pool, _facets(bad))
    check(
        "out-of-pool face record is unplaced, not a component",
        shells_bad.unplaced_faces == 1 and shells_bad.faces == 2 and len(shells_bad.shells) == 1,
    )

    # Negative 6 — three faces on one edge are non-manifold, not a shell.
    nm_pool = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0)]
    nm_faces = [(0, 1, 2), (0, 1, 3), (0, 1, 4)]
    shells_nm = shells_of(nm_pool, nm_faces)
    check(
        "edge used three times is non-manifold",
        len(shells_nm.shells) == 1 and shells_nm.shells[0].status == SHELL_NON_MANIFOLD,
    )

    # Negative 7 — two triangles on one edge (a sheet) is open: boundary
    # edges, no shell, even though the shared edge pairs.
    sheet_faces = [(0, 1, 2), (1, 0, 3)]
    shells_sheet = shells_of(nm_pool, sheet_faces)
    check(
        "sheet with one paired edge is open, not a shell",
        shells_sheet.shells[0].status == SHELL_OPEN
        and shells_sheet.shells[0].boundary_edges > 0
        and not shells_sheet.all_faces_closed,
    )

    # Negative 8 — placed but shapeless: a fully degenerate ring (all
    # three references the same vertex) yields no triangle, so it is
    # counted as degenerate and joins no component.
    degenerate = decode_shells(tetra_pool, _facets([_rec(0, (0, 0, 0))]))
    check(
        "degenerate face yields no component",
        degenerate.faces == 1 and degenerate.degenerate_faces == 1 and not degenerate.shells,
    )

    # Negative 9 — a marker outside the pinned family (0x44, G3 F9) is
    # not a face-candidate and never enters the partition.
    unread = decode_shells(tetra_pool, _facets([_rec(0, (0, 1, 2), marker=0x44)]))
    check(
        "marker outside the pinned family is not a face candidate",
        unread.faces == 0 and not unread.shells,
    )

    print(f"selftest: {len(failures)} failures")
    return 1 if failures else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus-root", default=DEFAULT_CORPUS_ROOT)
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    ap.add_argument("--limit", type=int, default=0, help="first N manifest parts only")
    ap.add_argument("--sha16", action="append", default=[], help="sha16 prefix filter (repeatable)")
    ap.add_argument("--selftest", action="store_true", help="run the synthetic fixtures")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(_selftest())
    rows = run_corpus(args)
    write_claims(rows, Path(args.out_dir))


if __name__ == "__main__":
    main()
