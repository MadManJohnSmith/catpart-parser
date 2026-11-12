#!/usr/bin/env python3
"""Pre-declaration absorption probe for the stage-9 integration (#34).

The stage-8 census (``mixedwrite_decode.py``) pairs each pool group to
the FIRST rep that fully matches it, and its sub-node record set (every
``05 08 01`` occurrence in the body) includes the pool wrappers' own
vertex records — so on multi-rep stores a pool group can be marked
"matched at rep 0 via subnode" before its diagonal rep's region is ever
tested.  All 22 "subnode-assisted" stores are multi-rep and all 60
strict stores single-rep, which is consistent with that early break
masking diagonal region absorption.

This probe re-measures absorption WITHOUT the early break: every pool
group is tested against EVERY decoded rep's region (exact f32, then the
stage-4b noise tolerance), per rep, and only the residue no region
re-lists falls to the sub-node records.  Per store it reports:

  all_region_absorbed : every pool group fully covered by ONE rep's
                        region (exact or noise) — the exporter's
                        absorption precondition
  diag_full           : every group covered by its body-order diagonal
                        rep (the stage-4b/5 diagonal law)
  classes             : per-group coverage class counts

Read-only over the corpus.  Population: the stage-6 trigger probe's 93
fail-closed stores (the stage-8 census population).  Run:

  .venv/bin/python -I scripts/triage/mixedwrite_absorption_probe.py
  # -> docs/evidence/data/stage9-absorption-probe.csv (93 rows)
"""

import csv
import mmap
import struct
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"
PROBE_CSV = OUT_DIR / "stage6-raw-trigger-probe.csv"

sys.path.insert(0, str(ROOT / "scripts" / "triage"))
sys.path.insert(0, str(ROOT / "src"))

from catpart.geometry import composite, pool  # noqa: E402
from mixedwrite_decode import decode_node  # noqa: E402

NOISE_REL = 1e-5

FIELDS = [
    "sha256", "split", "verdict_stage8", "pool_groups", "decoded_reps",
    "groups_diag_full", "groups_other_full", "groups_split",
    "groups_uncovered", "region_covered_vertices",
    "subnode_only_vertices", "all_region_absorbed", "diag_full",
]


def close_eq(points, pt):
    """Per-coordinate relative tolerance 1e-5 (the stage-4b REP-noise
    law); exact f32 equality also passes.  FULL triples only."""
    for q in points:
        if q == pt:
            return True
        if len(q) == len(pt):
            for u, v in zip(q, pt):
                if u != v:
                    d = abs(u - v)
                    if d > NOISE_REL * max(1e-30, abs(u), abs(v)):
                        return False
            return True
    return False


def main():
    probe = {r["sha256"]: r for r in csv.DictReader(PROBE_CSV.open())}
    targets = [
        s
        for s, r in probe.items()
        if r["verdict"] in ("start-unpinned", "weak-fit", "pool-unabsorbed")
    ]
    manifest = {r["sha256"]: r for r in csv.DictReader(MANIFEST.open())}
    stage8 = {}
    st8_path = OUT_DIR / "mixedwrite-reps-files.csv"
    if st8_path.exists():
        stage8 = {
            r["sha256"]: r["verdict"] for r in csv.DictReader(st8_path.open())
        }
    rows = []
    summary_full = []
    for sha in sorted(targets):
        path = ROOT / manifest[sha]["local_path"]
        with path.open("rb") as fh:
            mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                # reuse the census's store walker for identical node/pool
                # populations: audit_store is heavy; instead re-walk here
                d8_outer = int.from_bytes(mm[8:12], "big") if mm.size() >= 12 else 0
                blocks = composite.__dict__ and None  # placeholder, unused
                from catpart.geometry import store as store_mod

                blocks = store_mod.valid_blocks(mm)
                body = None
                lo = hi = 0
                for blk in [b for b, nm in blocks if nm == "CATStdCont"]:
                    span = store_mod.locate_store(mm, blk, blocks, d8_outer)
                    if span is None:
                        continue
                    blo, bhi = span.body_lo, span.body_hi
                    groups, kinds = pool.scan_pool_groups(mm, blo, bhi)
                    if pool.has_composite_space(kinds):
                        body = mm[blo:bhi]
                        lo, hi = blo, bhi
                        break
                if body is None:
                    continue
                bd = bytes(body)
                # token nodes over the FULL body (the census convention)
                nodes = []
                pos = 0
                while True:
                    pos = bd.find(composite.NODE_MAGIC, pos)
                    if pos < 0:
                        break
                    end = bd.find(composite.NODE_MAGIC, pos + 4)
                    if end < 0:
                        end = len(bd)
                    payload = bd[pos + 4 : end]
                    tok = payload.find(composite.LIST_TOKEN)
                    if 0 <= tok <= 64:
                        p = tok + 5
                        try:
                            c1, p = composite.read_count(payload, p)
                            c2, p = composite.read_count(payload, p)
                        except (IndexError, struct.error):
                            pos += 1
                            continue
                        if 0 < c1 <= composite.MAX_ELEMENT_COUNT:
                            nodes.append((pos, payload, c1, c2, p))
                    pos += 1
                poolv_all = [v for g in groups for v in g.vertices]
                decoded = []
                for npos, payload, c1, c2, counts_end in nodes:
                    law, pts, _skips, reg_end, _wc, failure = decode_node(
                        payload, c1, counts_end, poolv_all
                    )
                    if law is not None and pts:
                        decoded.append(
                            {
                                "pos": npos,
                                "pts": pts,
                                "c1": c1,
                                "law": law,
                                "region_end_abs": npos + 4 + reg_end,
                            }
                        )
                pool_sets = [{v for v in g.vertices} for g in groups]
                g_diag = g_other = g_split = g_unc = 0
                region_covered = 0
                subnode_only = 0
                for gi, pset in enumerate(pool_sets):
                    # coverage per rep: exact, then noise (no early break)
                    rep_cover = []
                    for rep in decoded:
                        ptset = set(rep["pts"])
                        matched = pset & ptset
                        if len(pset) <= 10_000:
                            for pt in pset - matched:
                                if close_eq(rep["pts"], pt):
                                    matched = matched | {pt}
                        rep_cover.append(matched)
                    covered = set()
                    for m in rep_cover:
                        covered |= m
                    region_covered += len(covered)
                    full_reps = [
                        j for j, m in enumerate(rep_cover) if m == pset
                    ]
                    if gi in full_reps:
                        g_diag += 1
                    elif full_reps:
                        g_other += 1
                    elif covered == pset:
                        g_split += 1
                    else:
                        g_unc += 1
                    if covered != pset:
                        # the residue only the sub-node records re-list:
                        # count vertices no region covered AND present in
                        # the body's 05 08 01 records
                        q = 0
                        sub = set()
                        while True:
                            q = bd.find(b"\x05\x08\x01", q)
                            if q < 0:
                                break
                            sub.add(struct.unpack_from("<fff", bd, q + 3))
                            q += 3
                        subnode_only += len(pset - covered)
                row = dict.fromkeys(FIELDS, "")
                row["sha256"] = sha
                row["split"] = manifest[sha]["split"]
                row["verdict_stage8"] = stage8.get(sha, "")
                row["pool_groups"] = len(groups)
                row["decoded_reps"] = len(decoded)
                row["groups_diag_full"] = g_diag
                row["groups_other_full"] = g_other
                row["groups_split"] = g_split
                row["groups_uncovered"] = g_unc
                row["region_covered_vertices"] = region_covered
                row["subnode_only_vertices"] = subnode_only
                row["all_region_absorbed"] = int(
                    g_diag + g_other + g_split == len(pool_sets)
                    and bool(pool_sets)
                )
                row["diag_full"] = int(g_diag == len(pool_sets) and bool(pool_sets))
                rows.append(row)
                if row["all_region_absorbed"]:
                    summary_full.append(sha)
            finally:
                mm.close()
    out = OUT_DIR / "stage9-absorption-probe.csv"
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out} ({len(rows)} stores)")
    s8 = Counter(r["verdict_stage8"] for r in rows)
    print("by stage-8 verdict:", s8.most_common())
    ara = [r for r in rows if r["all_region_absorbed"] == 1]
    diag = [r for r in rows if r["diag_full"] == 1]
    print("all_region_absorbed:", len(ara), "splits:", Counter(r["split"] for r in ara))
    print("diag_full:", len(diag), "splits:", Counter(r["split"] for r in diag))
    print("all_region_absorbed by stage-8 verdict:", Counter(r["verdict_stage8"] for r in ara).most_common())
    not_ara = [r for r in rows if r["all_region_absorbed"] != 1]
    print("NOT region-absorbed:", len(not_ara), "by stage-8 verdict:", Counter(r["verdict_stage8"] for r in not_ara).most_common())
    return 0


if __name__ == "__main__":
    sys.exit(main())
