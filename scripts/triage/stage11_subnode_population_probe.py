#!/usr/bin/env python3
"""Stage-11 Phase A probe (#34): the corpus-wide subnode-only-blocked
population at the stage-10 baseline.

The stage-8 census named a "subnode-assisted" class (22 stores whose
pool absorption supposedly needed the ``05 08 01`` vertex sub-node
records, ceiling "<= +22"); the stage-9 pre-declaration probe
(``mixedwrite_absorption_probe.py``) corrected that class as the
census's own early-break pairing artifact and re-measured the 93
trigger stores with own walkers: 81/82 reps-full stores are fully
region-absorbed; bad44bdf (1 uncovered vertex) + the 11 UV-family
stores stay fail-closed.  The lever's ceiling has never been
re-measured CORPUS-WIDE at the current baseline — that is this probe.

Population: every fail-closed store of the accepted stage-10 fitness
row (``stage10-identity-export-files.csv``, ``export_ok != 1``).
Exported rows cannot carry subnode-only vertices (the exporter's
absorption precondition — every pool vertex region-absorbed — gates
export), and the "exported-empty on absorption grounds" disjunct is
measured vacuous (0 exported rows with ``vertex_count == 0``;
empty-mesh exports carry vertices — the count is printed).

Method — OWN walkers, the stage-9 correction method; the census's
``pool_subnode_only`` column is joined for reference only, never
trusted:

  - composite spans: CATStdCont in body order, then the exporter's
    xdoclink / seebody recovery probes (``export.py``'s order); a span
    is composite when ``pool.scan_pool_groups`` finds
    ``has_composite_space``.  A part classifies on its spans: it is
    subnode-only-blocked when ANY composite span is (the exporter
    returns the FIRST span that exports; the part is fail-closed, so
    no span exports).
  - token nodes over the FULL body (the ``_scan_token_nodes``
    convention), each decoded with ``mixedwrite_decode.decode_node``
    (the committed stage-8 law set the exporter ports verbatim: table
    with the zero-block extent candidates -> raw -> flat).
  - absorption WITHOUT the early break: per pool group the UNION over
    ALL decoded reps (exact f32, then the exporter's ``_tol_match``
    noise <= 1e-5, capped at 10,000-vertex groups; the union noise
    pass is work-bounded and a bound skip is named) AND the exporter's
    diagonal (pool group k vs the k-th decoded node — its committed
    absorption precondition).
  - per uncovered vertex (cap 200 distinct values per span): every
    occurrence of its 12-byte pattern in the body, classified by
    position — at an ``05 08 01`` record prefix / inside the pool's
    own record spans / elsewhere.  MEASURED CAVEAT (fact, pool.py
    ``VREC``): the pool's own vertex records carry the SAME ``05 08
    01`` marker as the vertex sub-node records, so "appears only in
    05 08 01 records" is byte-checkable, while "re-listed by a
    sub-node record" needs an occurrence OUTSIDE the pool's own
    record spans — reported separately
    (``uncovered_outside_pool_relisted``).
  - refs gate per decoded rep k < pool_groups, the exporter's
    territory ``[region_end_k, next decoded node or body end)``.

A store span counts as SUBNODE-ONLY-BLOCKED iff (the stage-11 Phase A
definition): fail-closed at stage-10 AND a composite pool exists AND
at least one pool vertex is re-listed by NO decoded region (union) AND
every byte occurrence of that vertex in the body sits at an ``05 08
01`` record position AND no other blocker applies: the uncovered
groups' diagonal reps all decoded (no walk mismatch on a pool-carrying
rep), no gated reference beyond its rep's element space, and the
diagonal residue equals the union residue (no pairing co-blocker).

Read-only over the corpus (symlink).  Analysis only: src/ untouched.
Run:  .venv/bin/python -I scripts/triage/stage11_subnode_population_probe.py
Out:  docs/evidence/data/stage11-subnode-population.csv
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
STAGE10_CSV = OUT_DIR / "stage10-identity-export-files.csv"

sys.path.insert(0, str(ROOT / "scripts" / "triage"))
sys.path.insert(0, str(ROOT / "src"))

from catpart.geometry import composite, pool, store  # noqa: E402
from catpart.geometry.errors import ExportError  # noqa: E402
from mixedwrite_decode import decode_node  # noqa: E402

VREC = b"\x05\x08\x01"  # pool.py's vertex-record marker (and the sub-node records')
BYTE_VERIFY_CAP = 200  # distinct uncovered vertices byte-verified per span
NOISE_WORK_CAP = 20_000_000  # miss*point products per (group, rep) pair
# the exporter's container walk (export.py): CATStdCont first; the
# recovery probes run only when NO CATStdCont span located
CONTAINERS = (
    ("stdcont", "CATStdCont"),
    ("xdoclink", "CATXDocLinkCont"),
    ("seebody", "CATSeeBodyCont"),
)

FIELDS = [
    "sha256", "split", "stage10_error_class", "composite_spans",
    "container", "span_ordinal", "body_bytes", "pool_groups",
    "pool_vertices", "pool_distinct", "pool_sizes_head", "token_nodes",
    "decoded_reps", "table_reps", "raw_reps", "flat_reps", "failed_nodes",
    "node_failures_head", "groups_diag_full", "groups_other_full",
    "groups_split", "groups_uncovered", "uncovered_union_vertices",
    "uncovered_diag_vertices", "group_residue_head", "refs_ok", "refs_bad",
    "refs_notes", "uncovered_byte_verified", "uncovered_occ_total",
    "uncovered_occ_at_vrec", "uncovered_occ_in_pool_records",
    "uncovered_occ_outside_pool_vrec", "uncovered_occ_not_at_vrec",
    "uncovered_outside_pool_relisted", "noise_skipped_pairs",
    "verdict_stage8_census", "pool_subnode_only_census",
    "s9_all_region_absorbed", "s9_subnode_only_vertices",
    "classification", "note",
]


def rep_matched(distinct, pts):
    """One rep's matched subset of a pool group's distinct vertices:
    exact f32, then the exporter's ``_tol_match`` noise (<= NOISE_REL,
    the stage-4b law) — capped at 10,000-vertex groups and work-bounded
    exactly like the exporter's fallback; a bound skip is returned."""
    ptset = set(pts)
    matched = distinct & ptset
    skipped = False
    if len(distinct) <= 10_000:
        misses = distinct - matched
        if misses and len(misses) * len(pts) > NOISE_WORK_CAP:
            skipped = True
        else:
            for v in misses:
                best = composite._tol_match(v, pts)
                if best is not None and best <= composite.NOISE_REL:
                    matched = matched | {v}
    return matched, skipped


def scan_token_nodes(bd):
    """Token-bearing list nodes over the FULL body (the census and
    ``_scan_token_nodes`` convention): NODE_MAGIC to NODE_MAGIC,
    LIST_TOKEN within the first 64 bytes, 0 < c1 <= MAX_ELEMENT_COUNT."""
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
                _c2, p = composite.read_count(payload, p)
            except (IndexError, struct.error):
                pos += 1
                continue
            if 0 < c1 <= composite.MAX_ELEMENT_COUNT:
                nodes.append((pos, payload, c1, p))
        pos += 1
    return nodes


def pool_record_spans(bd, body_lo, groups):
    """Byte spans of each pool group's own 15-B vertex records, in BODY
    coordinates (the pool wrappers' ``05 08 01`` records — distinct
    from any vertex sub-node's re-listing only by position)."""
    spans = []
    for g in groups:
        o = g.offset - body_lo
        if o < 0 or o + 11 > len(bd):
            continue
        q = o + (15 if bd[o + 10] == 0xFF else 11)
        spans.append((q, q + 15 * g.count_field))
    return spans


def measure_span(bd, body_lo, groups, census_row, s9_row):
    """One composite span's absorption measurement + classification."""
    row = {k: "" for k in FIELDS}
    row["body_bytes"] = len(bd)
    row["pool_groups"] = len(groups)
    row["pool_vertices"] = sum(len(g.vertices) for g in groups)
    row["pool_distinct"] = len({v for g in groups for v in g.vertices})
    row["pool_sizes_head"] = ";".join(str(len(g.vertices)) for g in groups[:8])
    if census_row:
        row["verdict_stage8_census"] = census_row.get("verdict", "")
        row["pool_subnode_only_census"] = census_row.get("pool_subnode_only", "")
    if s9_row:
        row["s9_all_region_absorbed"] = s9_row.get("all_region_absorbed", "")
        row["s9_subnode_only_vertices"] = s9_row.get("subnode_only_vertices", "")
    if not groups:
        row["classification"] = "no-pool-groups"
        return row

    pool_spans = pool_record_spans(bd, body_lo, groups)
    nodes = scan_token_nodes(bd)
    row["token_nodes"] = len(nodes)
    poolv_all = [v for g in groups for v in g.vertices]
    decoded = []
    failures = []
    for npos, payload, c1, counts_end in nodes:
        try:
            law, pts, _skips, reg_end_rel, _wc, failure = decode_node(
                payload, c1, counts_end, poolv_all
            )
        except Exception as exc:  # noqa: BLE001 - named residue
            failures.append(f"node@{npos}:{type(exc).__name__}")
            continue
        if law is None:
            failures.append(f"node@{npos}: {failure}" if failure else f"node@{npos}: undecoded")
            continue
        decoded.append(
            {
                "pos": npos,
                "pts": pts,
                "c1": c1,
                "law": law,
                "region_end_abs": npos + 4 + reg_end_rel,
            }
        )
    row["decoded_reps"] = len(decoded)
    row["table_reps"] = sum(1 for r in decoded if r["law"] == "table")
    row["raw_reps"] = sum(1 for r in decoded if r["law"] == "raw")
    row["flat_reps"] = sum(1 for r in decoded if r["law"] == "flat")
    row["failed_nodes"] = len(nodes) - len(decoded)
    row["node_failures_head"] = ";".join(failures[:4])

    # absorption: union over ALL reps (no early break) + the exporter's
    # diagonal; per-group residue sets kept for the pairing check
    noise_skipped = 0
    union_residue = set()
    diag_residue = set()
    g_diag = g_other = g_split = g_unc = 0
    residue_head = []
    for k, g in enumerate(groups):
        distinct = set(g.vertices)
        # union: every rep, exact then noise, no early break
        covered = set()
        for rep in decoded:
            m, skipped = rep_matched(distinct, rep["pts"])
            noise_skipped += int(skipped)
            covered |= m
        unc_union = distinct - covered
        # diagonal: the exporter's committed precondition (pool k vs
        # decoded[k], its exact noise path)
        rep = decoded[k] if k < len(decoded) else None
        if rep is None:
            unc_diag = set(distinct)
        else:
            unc_diag = distinct - set(rep["pts"])
            if unc_diag and len(distinct) <= 10_000:
                unc_diag = {
                    v
                    for v in unc_diag
                    if (best := composite._tol_match(v, rep["pts"]))
                    is None
                    or best > composite.NOISE_REL
                }
        if not unc_union:
            if rep is not None and not unc_diag:
                g_diag += 1
            else:
                g_other += 1
        elif rep is not None and not unc_diag:
            g_split += 1
        else:
            g_unc += 1
        union_residue |= {(k, v) for v in unc_union}
        diag_residue |= {(k, v) for v in unc_diag}
        if unc_union:
            residue_head.append(
                f"g{k}({len(distinct)})unc_union={len(unc_union)}"
                f"_unc_diag={len(unc_diag)}"
            )
    row["groups_diag_full"] = g_diag
    row["groups_other_full"] = g_other
    row["groups_split"] = g_split
    row["groups_uncovered"] = g_unc
    row["uncovered_union_vertices"] = len(union_residue)
    row["uncovered_diag_vertices"] = len(diag_residue)
    row["group_residue_head"] = ";".join(residue_head[:6])
    row["noise_skipped_pairs"] = noise_skipped

    # refs gate per decoded rep k < pool_groups (the exporter's gate;
    # territory = [region_end_k, next decoded node or body end))
    refs_ok = refs_bad = 0
    ref_notes = []
    for k, rep in enumerate(decoded):
        if k >= len(groups):
            break
        tlo = rep["region_end_abs"]
        nxt = [d["pos"] for d in decoded if d["pos"] > tlo]
        thi = min(nxt) if nxt else len(bd)
        if thi <= tlo:
            continue
        try:
            records, _n = composite.parse_strip_records(
                bd, tlo, thi, rep["c1"], elements=None
            )
        except Exception as exc:  # noqa: BLE001 - named residue
            ref_notes.append(f"rep{k}:parse-{type(exc).__name__}")
            refs_bad += 1
            continue
        grefs = [
            r for _o, mk, _n, _c, refs, _w in records if mk in composite.GATED
            for r in refs
        ]
        if not grefs or max(grefs) < rep["c1"]:
            refs_ok += 1
        else:
            refs_bad += 1
            ref_notes.append(f"rep{k}:maxref{max(grefs)}>=c1{rep['c1']}")
    row["refs_ok"] = refs_ok
    row["refs_bad"] = refs_bad
    row["refs_notes"] = ";".join(ref_notes[:4])

    if not union_residue:
        row["classification"] = "absorbed-other-blocker"
        return row

    # uncovered-vertex byte verification (the definition's clause 3):
    # every occurrence of the vertex's 12-B pattern must sit at an
    # 05 08 01 record position; occurrences OUTSIDE the pool's own
    # record spans are the vertex sub-node re-listing evidence
    unc_values = sorted({v for _k, v in union_residue})
    verified = unc_values[:BYTE_VERIFY_CAP]
    occ_total = occ_vrec = occ_pool = occ_outside = occ_not_vrec = 0
    outside_relisted = 0
    for v in verified:
        pat = struct.pack("<fff", *v)
        q = 0
        v_outside = False
        while True:
            q = bd.find(pat, q)
            if q < 0:
                break
            occ_total += 1
            at_vrec = bd[q - 3 : q] == VREC
            in_pool = any(a <= q < b for a, b in pool_spans)
            if at_vrec:
                occ_vrec += 1
                if in_pool:
                    occ_pool += 1
                else:
                    occ_outside += 1
                    v_outside = True
            else:
                occ_not_vrec += 1
            q += 1
        outside_relisted += int(v_outside)
    row["uncovered_byte_verified"] = len(verified)
    row["uncovered_occ_total"] = occ_total
    row["uncovered_occ_at_vrec"] = occ_vrec
    row["uncovered_occ_in_pool_records"] = occ_pool
    row["uncovered_occ_outside_pool_vrec"] = occ_outside
    row["uncovered_occ_not_at_vrec"] = occ_not_vrec
    row["uncovered_outside_pool_relisted"] = outside_relisted

    # classification (the stage-11 Phase A definition)
    diag_missing = {k for k, _v in diag_residue if k >= len(decoded)}
    pairing_co = len(diag_residue) > len(union_residue)
    note = []
    if len(unc_values) > BYTE_VERIFY_CAP:
        note.append(f"byte-verify sampled {len(verified)} of {len(unc_values)}")
    note.append(
        f"uncovered re-listed outside pool records: {outside_relisted}"
        f"/{len(verified)} verified"
    )
    if diag_missing:
        row["classification"] = "unabsorbed-walk-mismatch"
        note.append(f"groups without a diagonal rep: {sorted(diag_missing)[:6]}")
    elif pairing_co:
        row["classification"] = "unabsorbed-pairing"
    elif refs_bad:
        row["classification"] = "unabsorbed-refs-beyond"
    elif occ_not_vrec:
        row["classification"] = "unabsorbed-other-cause"
        note.append("uncovered vertex bytes occur outside 05 08 01 records")
    else:
        row["classification"] = "subnode-only-blocked"
    row["note"] = "; ".join(note)
    return row


def main():
    stage10 = list(csv.DictReader(STAGE10_CSV.open()))
    fail_closed = [r for r in stage10 if r["export_ok"] != "1"]
    empty_exports = [
        r for r in stage10 if r["export_ok"] == "1" and r["vertex_count"] == "0"
    ]
    print(f"stage-10 rows: {len(stage10)}; fail-closed: {len(fail_closed)}")
    print(
        "exported rows with vertex_count == 0 (the 'exported-empty on "
        f"absorption grounds' disjunct): {len(empty_exports)}"
    )
    manifest = {r["sha256"]: r for r in csv.DictReader(MANIFEST.open())}
    census = {}
    cpath = OUT_DIR / "mixedwrite-reps-files.csv"
    if cpath.exists():
        census = {r["sha256"]: r for r in csv.DictReader(cpath.open())}
    s9 = {}
    s9path = OUT_DIR / "stage9-absorption-probe.csv"
    if s9path.exists():
        s9 = {r["sha256"]: r for r in csv.DictReader(s9path.open())}

    rows = []
    for sr in sorted(fail_closed, key=lambda r: r["sha256"]):
        sha = sr["sha256"]
        path = ROOT / manifest[sha]["local_path"]
        with path.open("rb") as fh:
            mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                d8 = int.from_bytes(mm[8:12], "big") if mm.size() >= 12 else 0
                blocks = store.valid_blocks(mm)
                composite_spans = []
                malformed_rows = []
                for tag, blk_name in CONTAINERS:
                    cands = [b for b, nm in blocks if nm == blk_name]
                    located_here = False
                    for ordinal, blk in enumerate(cands):
                        try:
                            span = store.locate_store(
                                mm, blk, blocks, d8, container=tag
                            )
                        except ExportError:
                            continue
                        if span is None:
                            continue
                        located_here = True
                        try:
                            groups, kinds = pool.scan_pool_groups(
                                mm, span.body_lo, span.body_hi
                            )
                        except ExportError as exc:
                            malformed_rows.append((tag, ordinal, exc))
                            continue
                        if pool.has_composite_space(kinds):
                            composite_spans.append((tag, ordinal, span, groups))
                    # export.py's order: the recovery probes run only when
                    # NO span of the current container located
                    if located_here or composite_spans or malformed_rows:
                        break
                for tag, ordinal, exc in malformed_rows:
                    r = {k: "" for k in FIELDS}
                    r["sha256"] = sha
                    r["split"] = sr["split"]
                    r["stage10_error_class"] = sr["error_class"]
                    r["container"] = tag
                    r["span_ordinal"] = ordinal
                    r["classification"] = "pool-malformed"
                    r["note"] = f"{type(exc).__name__}: {exc.detail[:120]}"
                    rows.append(r)
                if not composite_spans:
                    r = {k: "" for k in FIELDS}
                    r["sha256"] = sha
                    r["split"] = sr["split"]
                    r["stage10_error_class"] = sr["error_class"]
                    r["composite_spans"] = 0
                    r["classification"] = "no-composite-store"
                    rows.append(r)
                    continue
                for tag, ordinal, span, groups in composite_spans:
                    bd = bytes(mm[span.body_lo : span.body_hi])
                    r = measure_span(
                        bd, span.body_lo, groups, census.get(sha), s9.get(sha)
                    )
                    r["sha256"] = sha
                    r["split"] = sr["split"]
                    r["stage10_error_class"] = sr["error_class"]
                    r["composite_spans"] = len(composite_spans)
                    r["container"] = tag
                    r["span_ordinal"] = ordinal
                    rows.append(r)
            finally:
                mm.close()

    out = OUT_DIR / "stage11-subnode-population.csv"
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out} ({len(rows)} rows)")

    by_store = {}
    for r in rows:
        by_store.setdefault(r["sha256"], []).append(r)
    store_class = {
        sha: "subnode-only-blocked"
        if any(r["classification"] == "subnode-only-blocked" for r in rs)
        else rs[0]["classification"] if len(rs) == 1
        else "multi-span:" + "+".join(sorted({r["classification"] for r in rs}))
        for sha, rs in by_store.items()
    }
    print("store-level classification:", Counter(store_class.values()).most_common())
    pop = [sha for sha, c in store_class.items() if c == "subnode-only-blocked"]
    print(f"SUBNODE-ONLY-BLOCKED population: {len(pop)}")
    for sha in sorted(pop):
        for r in by_store[sha]:
            if r["classification"] == "subnode-only-blocked":
                print(f"  {sha[:16]} {r['split']} groups={r['pool_groups']} "
                      f"uncovered_union={r['uncovered_union_vertices']} "
                      f"uncovered_diag={r['uncovered_diag_vertices']} "
                      f"refs_bad={r['refs_bad']} "
                      f"outside_pool_relisted={r['uncovered_outside_pool_relisted']} "
                      f"note={r['note']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
