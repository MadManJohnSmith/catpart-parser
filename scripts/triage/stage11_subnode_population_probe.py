#!/usr/bin/env python3
"""Stage-11 Phase A (#34): the corpus-wide subnode-only-blocked
population at the stage-10 baseline.

The stage-8 census named a "subnode-assisted" class (22 stores whose
pool absorption supposedly needed the ``05 08 01`` vertex sub-node
records; ceiling claim "the subnode law <= +22"), and the stage-9
pre-declaration probe corrected that class as the census's own
early-break pairing artifact: within the 93 trigger stores only
bad44bdf keeps a genuine gap (1 uncovered vertex).  The lever's
corpus-wide population at the CURRENT (stage-10) baseline has never
been measured — that is this probe.  Population: every fail-closed row
of the accepted stage-10 A/B (``stage10-identity-export-files.csv``,
``export_ok != 1``); exported rows cannot carry the blocker (the
exporter's absorption precondition — every pool vertex in its diagonal
rep's region — gates export), and empty-mesh exports carry vertices
(their ``vertex_count > 0`` is printed for the record).

Method — OWN walkers, the stage-9 correction method; the census's
``pool_subnode_only`` column is joined for reference only, never
trusted (its multi-rep early-break artifact is dated in
``stage9-claims.csv``):

  - composite spans: CATStdCont in body order, then the exporter's
    xdoclink / seebody recovery probes (``export.py``'s order — the
    recovery probes run only when no span of the current container
    located); a span is composite when ``pool.scan_pool_groups`` finds
    ``has_composite_space``.  A part classifies on its spans: the
    exporter returns the FIRST span that exports, so a fail-closed
    part has no exporting span and ANY span whose only blocker is the
    subnode residue bounds a +1 export.
  - route per store (the exporter's routing prelude,
    ``_export_composite_store``): the single-rep locator
    (``find_list_node`` on the first-STRIP_RE-match window) and
    ``decode_region`` decide n1 / walk-ok / walk-mismatch; the
    composition (``_decode_mixedwrite``) only sees walk-mismatch
    stores whose raw law declines (raw-covered stores export — none
    are in this fail-closed population).  A walk-ok store's absorption
    blocker lives at the primary/per-rep path, NOT at the composition.
  - token nodes over the FULL body (``_scan_token_nodes``
    convention), each decoded with ``mixedwrite_decode.decode_node``
    (the committed stage-8 law set the exporter ports verbatim:
    table with the zero-block extent candidates -> raw -> flat).
  - absorption, both in the exporter's terms and diagnostically:
    per pool group the DIAGONAL (group k vs decoded node k — the
    exporter's committed precondition; exact f32, then
    ``_tol_match`` noise <= 1e-5 capped at 10,000-vertex groups) and
    the UNION over ALL decoded reps (no early break — the stage-9
    method).  Per group diag residue ⊇ union residue by
    construction; diagonal == union means no pairing slack.
  - byte verification of EVERY uncovered (diag) vertex value: every
    occurrence of its 12-B f32 pattern in the body is classified by
    position — at an ``05 08 01`` record prefix / inside the pool's
    own record spans / outside them.  MEASURED CAVEAT (fact,
    ``pool.py`` VREC): the pool's own vertex records carry the SAME
    ``05 08 01`` marker as the vertex sub-node records, so
    "sub-node-only" = every occurrence sits at an ``05 08 01``
    position AND at least one occurrence sits OUTSIDE the pool's own
    records (per vertex — a vertex with no outside occurrence has no
    record a sub-node law could pin it by: unpinnable).
  - refs gate per decoded rep k < pool_groups, the exporter's
    territory ``[region_end_k, next decoded node or body end)``.
  - noise-skip accounting: the diagonal mirrors the exporter's
    10,000-vertex noise cap exactly (a group above it is exact-only
    at the diagonal — the exporter's own law); the union's noise
    pass runs under a work budget (misses x rep-points <= 50M) and a
    tripped budget is counted in ``noise_skipped_pairs``; population
    membership requires zero budget skips.

A store span counts as SUBNODE-ONLY-BLOCKED iff ALL of:
  (1) the part is fail-closed at stage-10 and this span is composite;
  (2) decoded reps exist and every pool group has a diagonal rep (no
      walk-mismatch co-blocker on any pool-carrying rep);
  (3) diagonal residue == union residue (no pairing co-blocker) and
      is non-empty;
  (4) every uncovered vertex byte-verifies: all occurrences at ``05
      08 01`` positions, >= 1 occurrence outside the pool's own
      records (pinnable), zero noise skips;
  (5) no gated reference beyond its rep's element space on any
      pool-carrying rep;
  (6) PASS 2 (exporter anchor): ``build_export`` on the part raises
      ExportError and the detail names the absorption gap with a
      residue count matching this span's measured uncovered count
      ("does not establish pool absorption: N of M" at the
      composition, or "does not re-list the pool: N of M" at the
      primary path) — proving the exporter routes the part to a path
      the subnode law could unblock, with the named residue the
      subnode-only one this span measured.

Method provenance: re-derived in this worktree; the interrupted
predecessor's draft (~/.local/state/catpart-parser/
stage11-phaseA-orphan-probe.py) contributed method notes, reviewed
against the committed sources first.  Differences from that draft:
the exporter-anchored pass 2, the route column, the noise-skip gate,
per-vertex pinnability, full (uncapped) byte verification, and the
diagonal-first classification.  Its numbers were never used.

Read-only over the corpus (symlink).  Analysis only: src/ untouched.
Run:  python3 -I scripts/triage/stage11_subnode_population_probe.py
Out:  docs/evidence/data/stage11-subnode-population.csv
"""

import argparse
import csv
import mmap
import struct
import sys
import tempfile
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
from catpart.geometry.export import build_export  # noqa: E402
from mixedwrite_decode import decode_node  # noqa: E402

VREC = b"\x05\x08\x01"  # pool.py's vertex-record marker (and the sub-node records')

FIELDS = [
    "sha256", "split", "stage10_error_class", "composite_spans",
    "container", "span_ordinal", "route", "body_bytes", "pool_groups",
    "pool_vertices", "pool_distinct", "pool_sizes_head", "token_nodes",
    "decoded_reps", "table_reps", "raw_reps", "flat_reps", "failed_nodes",
    "node_failures_head", "groups_diag_full", "groups_other_full",
    "groups_split", "groups_uncovered", "uncovered_diag_vertices",
    "uncovered_union_vertices", "residue_head", "refs_ok", "refs_bad",
    "refs_notes", "noise_skipped_pairs", "uncovered_byte_verified",
    "uncovered_pinnable", "uncovered_unpinnable", "occ_total",
    "occ_at_vrec", "occ_in_pool_records", "occ_outside_pool_vrec",
    "occ_not_at_vrec", "census_verdict", "census_pool_subnode_only",
    "s9_all_region_absorbed", "s9_subnode_only_vertices",
    "exporter_error_class", "exporter_absorption_gap",
    "exporter_detail_head", "classification", "note",
]


NOISE_WORK_BUDGET = 50_000_000  # miss*point products per (group, rep) pair


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


def pool_record_spans(bd, groups, body_lo=0):
    """Byte spans (body-relative) of each pool group's own 15-B vertex
    records (the pool wrappers' ``05 08 01`` records — distinct from
    any vertex sub-node's re-listing only by position; pool.py's width
    law: count byte 0xFF -> u32le count, records at +15; else at +11).
    ``PoolGroup.offset`` is an ABSOLUTE file offset (pool.py scans the
    mmap), so it is rebased by ``body_lo`` onto the body slice."""
    spans = []
    for g in groups:
        o = g.offset - body_lo
        q = o + (15 if bd[o + 10] == 0xFF else 11)
        spans.append((q, q + 15 * g.count_field))
    return spans


def route_of(mm, span):
    """The exporter's routing prelude (_export_composite_store): the
    single-rep locator on the first-STRIP_RE-match window, then
    decode_region.  Returns 'n1' (no list node), 'walk-ok' (the
    primary decode succeeds — the composition is never reached),
    'walk-mismatch' (decode_region raised WITH the family signature —
    the raw law and then the composition run; this part is fail-closed
    so its raw law declined), or 'walk-error-not-family' (decode_region
    raised without the signature — the exporter re-raises the original
    failure; neither the raw law nor the composition is reached)."""
    bd = mm[span.body_lo : span.body_hi]
    hdrs = [m.start() for m in composite.STRIP_RE.finditer(bd, 0, len(bd))]
    node_hi = hdrs[0] if hdrs else len(bd)
    ln = composite.find_list_node(bd, 0, node_hi)
    if ln is None:
        return "n1"
    payload, elem_decl, _eb = ln
    try:
        composite.decode_region(payload, elem_decl)
    except ExportError:
        if composite._walk_mismatch(payload, elem_decl) is None:
            return "walk-error-not-family"
        return "walk-mismatch"
    return "walk-ok"


def measure_span(bd, groups, census_row, s9_row, body_lo=0):
    """One composite span's absorption measurement + classification."""
    row = {k: "" for k in FIELDS}
    row["body_bytes"] = len(bd)
    row["pool_groups"] = len(groups)
    row["pool_vertices"] = sum(len(g.vertices) for g in groups)
    row["pool_distinct"] = len({v for g in groups for v in g.vertices})
    row["pool_sizes_head"] = ";".join(str(len(g.vertices)) for g in groups[:8])
    if census_row:
        row["census_verdict"] = census_row.get("verdict", "")
        row["census_pool_subnode_only"] = census_row.get("pool_subnode_only", "")
    if s9_row:
        row["s9_all_region_absorbed"] = s9_row.get("all_region_absorbed", "")
        row["s9_subnode_only_vertices"] = s9_row.get("subnode_only_vertices", "")
    if not groups:
        row["classification"] = "no-pool-groups"
        return row

    pool_spans = pool_record_spans(bd, groups, body_lo)
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

    # absorption: the exporter's DIAGONAL precondition per group +
    # the UNION over all reps (the stage-9 no-early-break method).
    # The diagonal is one of the union's reps, so a vertex outside the
    # diagonal residue is already union-covered; the union pass only
    # needs to test the diagonal residue against the NON-diagonal
    # reps (exact set ops, then noise under the work budget) — which
    # keeps the big-group case measurable instead of
    # O(misses x points) on 64k-vertex groups.
    noise_skipped = 0
    union_residue = set()
    diag_residue = set()
    g_diag = g_other = g_split = g_unc = 0
    residue_head = []
    for k, g in enumerate(groups):
        distinct = set(g.vertices)
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
        unc_union = set(unc_diag)
        for j, r in enumerate(decoded):
            if rep is not None and j == k:
                continue  # the diagonal's own coverage is unc_diag
            still = unc_union - set(r["pts"])
            if still and len(still) * len(r["pts"]) <= NOISE_WORK_BUDGET:
                still = {
                    v
                    for v in still
                    if (best := composite._tol_match(v, r["pts"]))
                    is None
                    or best > composite.NOISE_REL
                }
            elif still:
                noise_skipped += 1
                continue
            unc_union = still
            if not unc_union:
                break
        if not unc_diag:
            if rep is not None:
                g_diag += 1
            else:
                g_other += 1
        elif not unc_union:
            g_split += 1
        else:
            g_unc += 1
        union_residue |= {(k, v) for v in unc_union}
        diag_residue |= {(k, v) for v in unc_diag}
        if unc_diag:
            residue_head.append(
                f"g{k}({len(distinct)})diag={len(unc_diag)}union={len(unc_union)}"
            )
    row["groups_diag_full"] = g_diag
    row["groups_other_full"] = g_other
    row["groups_split"] = g_split
    row["groups_uncovered"] = g_unc
    row["uncovered_diag_vertices"] = len(diag_residue)
    row["uncovered_union_vertices"] = len(union_residue)
    row["residue_head"] = ";".join(residue_head[:6])
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

    if not diag_residue:
        row["classification"] = "absorbed-other-blocker"
        return row

    # byte verification of EVERY uncovered (diagonal) vertex value:
    # position of each occurrence of its 12-B pattern, and per-vertex
    # pinnability (>= 1 occurrence OUTSIDE the pool's own records)
    unc_values = sorted({v for _k, v in diag_residue})
    pinnable = unpinnable = 0
    occ_total = occ_vrec = occ_pool = occ_outside = occ_not_vrec = 0
    for v in unc_values:
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
        if v_outside:
            pinnable += 1
        else:
            unpinnable += 1
    row["uncovered_byte_verified"] = len(unc_values)
    row["uncovered_pinnable"] = pinnable
    row["uncovered_unpinnable"] = unpinnable
    row["occ_total"] = occ_total
    row["occ_at_vrec"] = occ_vrec
    row["occ_in_pool_records"] = occ_pool
    row["occ_outside_pool_vrec"] = occ_outside
    row["occ_not_at_vrec"] = occ_not_vrec

    # pass-1 classification (the definition's clauses 2-5; clause 6
    # is the exporter anchor, applied to candidates in main())
    note = []
    diag_missing = {k for k, _v in diag_residue if k >= len(decoded)}
    pairing_slack = len(diag_residue) > len(union_residue)
    if not decoded:
        row["classification"] = "walk-mismatch-co-blocker"
        note.append("no decoded reps")
    elif diag_missing:
        row["classification"] = "walk-mismatch-co-blocker"
        note.append(f"groups without a diagonal rep: {sorted(diag_missing)[:6]}")
    elif pairing_slack:
        row["classification"] = "pairing-co-blocker"
    elif refs_bad:
        row["classification"] = "refs-co-blocker"
    elif noise_skipped:
        row["classification"] = "noise-cap-ambiguous"
    elif occ_not_vrec:
        row["classification"] = "unabsorbed-other-cause"
        note.append("uncovered vertex bytes occur outside 05 08 01 records")
    elif unpinnable:
        row["classification"] = "subnode-residue-unpinnable"
        note.append(
            f"{unpinnable} uncovered vertex(es) occur at no outside-pool "
            "05 08 01 record — nothing for a sub-node law to pin"
        )
    else:
        row["classification"] = "subnode-only-blocked-candidate"
    row["note"] = "; ".join(note)
    return row


def exporter_anchor(sha, rel):
    """Pass 2: run the exporter on the candidate's part; require the
    raised ExportError to name an absorption gap (the composition's
    'does not establish pool absorption: N of M' or the primary path's
    'does not re-list the pool: N of M') — proving the exporter routes
    the part to a path the subnode law could unblock, with absorption
    the failing gate.  The residue count is RECORDED, not gated: the
    primary path's arithmetic (the locator node's single-rep decode)
    differs from this probe's law-ladder diagonal measure, so exact
    equality is expected only on the composition path (walk-mismatch
    stores) and is reported as a check there.  Returns
    (error_class, gap_named, residue, detail_head) — gap_named is
    'composition' / 'primary' / 'exported' / ''."""
    path = ROOT / rel["local_path"]
    with tempfile.TemporaryDirectory(prefix="stage11-phasea-") as td:
        out = Path(td) / f"{sha[:16]}.ply"
        try:
            build_export(path, out)
        except ExportError as exc:
            detail = exc.detail
            gap = ""
            residue = -1
            for tag, pat in (
                ("composition", "does not establish pool absorption: "),
                ("primary", "does not re-list the pool: "),
            ):
                i = detail.find(pat)
                if i >= 0:
                    gap = tag
                    tail = detail[i + len(pat) :]
                    residue = int(tail.split()[0]) if tail.split()[0].isdigit() else -1
                    break
            return exc.error_class, gap, residue, detail[:200]
        return "", "exported", -1, ""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--sha16",
        action="append",
        default=[],
        help="restrict to these sha16 prefixes (repeatable; anchor runs)",
    )
    args = ap.parse_args(argv)
    stage10 = list(csv.DictReader(STAGE10_CSV.open()))
    fail_closed = [r for r in stage10 if r["export_ok"] != "1"]
    if args.sha16:
        fail_closed = [
            r for r in fail_closed if r["sha256"].startswith(tuple(args.sha16))
        ]
    empty_exports = [
        r
        for r in stage10
        if r["export_ok"] == "1" and r["vertex_count"] == "0"
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
    candidates = []  # (sha, rel, span_row) needing the exporter anchor
    for sr in sorted(fail_closed, key=lambda r: r["sha256"]):
        sha = sr["sha256"]
        rel = manifest[sha]
        path = ROOT / rel["local_path"]
        with path.open("rb") as fh:
            mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                d8 = int.from_bytes(mm[8:12], "big") if mm.size() >= 12 else 0
                blocks = store.valid_blocks(mm)
                composite_spans = []
                malformed_rows = []
                located_any = False
                for tag, blk_name in (
                    ("stdcont", "CATStdCont"),
                    ("xdoclink", "CATXDocLinkCont"),
                    ("seebody", "CATSeeBodyCont"),
                ):
                    cands = [b for b, nm in blocks if nm == blk_name]
                    for ordinal, blk in enumerate(cands):
                        try:
                            span = store.locate_store(mm, blk, blocks, d8, container=tag)
                        except ExportError:
                            continue
                        if span is None:
                            continue
                        located_any = True
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
                    if located_any or composite_spans or malformed_rows:
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
                        bd, groups, census.get(sha), s9.get(sha), span.body_lo
                    )
                    r["sha256"] = sha
                    r["split"] = sr["split"]
                    r["stage10_error_class"] = sr["error_class"]
                    r["composite_spans"] = len(composite_spans)
                    r["container"] = tag
                    r["span_ordinal"] = ordinal
                    r["route"] = (
                        route_of(mm, span) if bd else ""
                    )
                    rows.append(r)
                    if r["classification"] in (
                        "subnode-only-blocked-candidate",
                        "subnode-residue-unpinnable",
                    ):
                        candidates.append((sha, rel, r))
            finally:
                mm.close()

    # pass 2: the exporter anchor on the pass-1 candidates AND the
    # unpinnable-residue stores (the correction record needs the
    # exporter's own word on those too; population membership still
    # requires the candidate + anchor)
    for sha, rel, r in candidates:
        err_class, gap, residue, head = exporter_anchor(sha, rel)
        r["exporter_error_class"] = err_class
        r["exporter_detail_head"] = head
        measured = int(r["uncovered_diag_vertices"])
        if gap == "exported" or not gap:
            if r["classification"] == "subnode-only-blocked-candidate":
                r["classification"] = "exporter-disagrees"
                r["note"] = (
                    f"exporter did not fail with an absorption gap "
                    f"(class={err_class or 'exported'}); pass-1 byte "
                    "reading stands unexplained"
                )
            else:
                r["note"] = (
                    f"exporter class={err_class or 'exported'} without an "
                    "absorption gap"
                )
        else:
            if gap == "composition" and residue != measured:
                r["note"] = (
                    f"CHECK: composition names residue {residue}, probe "
                    f"measured {measured} — same law decode, counts "
                    "should match"
                )
            else:
                r["note"] = (
                    f"exporter anchor: {gap} path names residue {residue} "
                    f"(probe measured {measured})"
                )

    out = OUT_DIR / (
        "stage11-subnode-population.csv"
        if not args.sha16
        else "stage11-subnode-population-anchor.csv"
    )
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
        if any(r["classification"] == "subnode-only-blocked-candidate" and r["note"].startswith("exporter anchor") for r in rs)
        else "multi-span:" + "+".join(sorted({r["classification"] for r in rs}))
        if len(rs) > 1
        else rs[0]["classification"]
        for sha, rs in by_store.items()
    }
    print("store-level classification:", Counter(store_class.values()).most_common())
    pop = [sha for sha, c in store_class.items() if c == "subnode-only-blocked"]
    print(f"SUBNODE-ONLY-BLOCKED population: {len(pop)}  (the export ceiling)")
    for sha in sorted(pop):
        for r in by_store[sha]:
            if r["classification"] == "subnode-only-blocked-candidate":
                print(
                    f"  {sha[:16]} {r['split']} route={r['route']} "
                    f"groups={r['pool_groups']} pool_distinct={r['pool_distinct']} "
                    f"uncovered_diag={r['uncovered_diag_vertices']} "
                    f"uncovered_union={r['uncovered_union_vertices']} "
                    f"pinnable={r['uncovered_pinnable']} "
                    f"refs_bad={r['refs_bad']} "
                    f"census_subnode_col={r['census_pool_subnode_only']} "
                    f"note={r['note']}"
                )
    cands = [sha for sha, c in store_class.items() if "subnode-only-blocked-candidate" in c]
    non_anchored = [
        sha
        for sha in cands
        if sha not in pop
    ]
    if non_anchored:
        print("pass-1 candidates NOT confirmed by the exporter anchor:")
        for sha in sorted(non_anchored):
            for r in by_store[sha]:
                if r["classification"].startswith("exporter-"):
                    print(f"  {sha[:16]} {r['classification']} {r['note']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
