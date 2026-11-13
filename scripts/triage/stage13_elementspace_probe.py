#!/usr/bin/env python3
"""Stage-13 Phase A (#34): the element space beyond the pool — live
memberships + byte census of the no-pool and refs-beyond families at
the stage-12 LANDED baseline (main eed27a9).

Population: every fail-closed row of the accepted stage-12 A/B
(``stage12-identity-export-files.csv``, ``export_ok != 1``) —
re-derived LIVE (the stage-12 census CSVs are stage-10-baseline
artifacts; the exporter anchor shifted per the stage-12 A/B: the 53
recoverable parts row as 12 pass + 41 undecoded-variant).  Two passes:

  membership — OWN span walk replicating ``export._export_data``'s
    four-family probe order (stdcont; xdoclink/seebody only when
    nothing located AND no header raised; other-container when STILL
    nothing located AND no header raised — the landed stage-12
    extension), composite-span detection per located span, and the
    exporter anchor (``build_export`` black box) partitioning the
    fail-closed mass into missing-locator / no-pool / refs-beyond /
    other.  Deltas vs the committed stage-12 census CSV are named per
    row (the 37 locator-recovered no-pool bodies are NEW surface this
    stage opens: at the stage-10 baseline they were missing-locator
    rows, absent from the stage-12 census).

  census (no-pool + refs-beyond rows only) — the byte census that
    answers WHERE the non-pool elements' vertices live:
    - pool/wrapper/sub-kind census (the refs-beyond "no second pool
      form" negative claim re-verified with own walkers: every
      ``05 08 01`` run >= 3 outside the located pool spans; every
      ``01 06`` sub-kind occurrence vs the located pool groups);
    - the clean facet scan (candidates/records/max ref);
    - a PER-NODE census: every token-bearing list node's payload
      length, declared counts (c1 = element_count, c2), and whether
      the COMMITTED table law (``composite.decode_region``) decodes
      its point region — how many points, how many skip slots, and
      whether the store's pool vertices are absorbed verbatim (exact
      f32, then the committed NOISE_REL tolerance);
    - the element-space law measurement: the largest decoded node's
      c1 vs the facet max ref (the N2 shape) and vs the pool size.

The committed geometry modules are infrastructure
(``store``/``pool``/``facets``/``composite``/``export``); the
orchestration and every census below is this probe's own.  Anchor runs
(``--sha16``) write ``*-anchor.csv`` so committed CSVs are never
clobbered.  Analysis only: ``src/`` untouched, corpus read-only.

Run:
  python3 -I scripts/triage/stage13_elementspace_probe.py
Out: docs/evidence/data/stage13-membership.csv
     docs/evidence/data/stage13-elementspace-census.csv
"""

import argparse
import csv
import dataclasses
import mmap
import struct
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"
STAGE12_AB_CSV = OUT_DIR / "stage12-identity-export-files.csv"
STAGE12_CENSUS_CSV = OUT_DIR / "stage12-noncomposite-census.csv"

sys.path.insert(0, str(ROOT / "src"))

from catpart.geometry import composite, facets, pool, store  # noqa: E402
from catpart.geometry.errors import ExportError  # noqa: E402
from catpart.geometry.export import build_export  # noqa: E402

FULL_WRAP = pool.FULL_WRAP
VREC = pool.VREC
NODE_MAGIC = composite.NODE_MAGIC
LIST_TOKEN = composite.LIST_TOKEN
NOISE_REL = composite.NOISE_REL

MFIELDS = [
    "sha256", "split", "stage12_error_class", "family", "anchor_detail_head",
    "recovered_suffix", "spans", "composite_spans", "container", "tail_law",
    "s12_census_family", "s12_census_shown", "delta", "note",
]

CFIELDS = [
    "sha256", "family", "container", "tail_law",
    "body_lo", "body_hi", "body_bytes",
    "pool_groups", "pool_vertices", "pool_sizes_head", "kinds",
    "wrap_occ", "wrap_subkinds", "pool_wrap_under_groups",
    "strip_candidates", "strip_records", "max_ref", "markers",
    "vrec_occ", "vrec_runs_head", "vrec_outside_pool", "vrec_run3_outside",
    "node_magic_hits", "token_nodes", "nodes_decoded",
    "node_rows", "c1_max", "c1_of_largest", "largest_node_bytes",
    "largest_decoded", "largest_points", "largest_skips",
    "largest_fail", "pool_absorbed_largest", "pool_absorbed_any",
    "elem_space_c1_vs_maxref", "elem_space_c1_vs_pool",
    "second_pool_0106_outside", "second_pool_vrec_run3",
    "raw_triples", "raw_nice_rate", "raw_xasc_rate", "note",
]


def own_spans(mm):
    """``export._export_data``'s probe order, replicated and recorded.

    Returns ``(blocks, d8_outer, spans, first_error, located)`` where
    ``spans`` lists ``(container_tag, ordinal, span)`` in probe order.
    """
    size = mm.size()
    d8_outer = int.from_bytes(mm[8:12], "big") if size >= 12 else 0
    blocks = store.valid_blocks(mm)
    first_error = None
    located = False
    spans = []
    named = (
        ("stdcont", "CATStdCont"),
        ("xdoclink", "CATXDocLinkCont"),
        ("seebody", "CATSeeBodyCont"),
    )
    for fidx, (tag, name) in enumerate(named):
        cands = [b for b, nm in blocks if nm == name]
        for ordinal, blk in enumerate(cands):
            try:
                span = store.locate_store(mm, blk, blocks, d8_outer, container=tag)
            except ExportError as exc:
                if first_error is None:
                    first_error = exc
                continue
            if span is None:
                continue
            located = True
            spans.append((tag, ordinal, span))
        if fidx == 0 and (located or first_error is not None):
            break
    if not located and first_error is None:
        # the landed stage-12 other-container family
        others = [
            (b, nm) for b, nm in blocks if nm not in store.NAMED_PROBE_CONTAINERS
        ]
        for ordinal, (blk, nm) in enumerate(others):
            try:
                span = store.locate_store(
                    mm, blk, blocks, d8_outer, container=store.CONTAINER_OTHER
                )
            except ExportError as exc:
                if first_error is None:
                    first_error = exc
                continue
            if span is None:
                continue
            located = True
            spans.append((store.CONTAINER_OTHER, ordinal, span))
    return blocks, d8_outer, spans, first_error, located


def anchor_family(err_class, detail):
    if err_class == "missing-geometry-store":
        return "missing-locator"
    if "no 01 06 vertex pool decoded" in detail:
        return "no-pool"
    if "facet references beyond the pool" in detail:
        return "refs-beyond"
    return "other"


def _hex(counter):
    return ";".join(f"{k}:{v}" for k, v in sorted(counter.items()))


def vrec_runs(bd, pool_spans):
    """``05 08 01`` occurrence census: positions, contiguous runs,
    outside-pool classification."""
    positions = []
    q = 0
    while True:
        q = bd.find(VREC, q)
        if q < 0:
            break
        if q + 15 <= len(bd):
            positions.append(q)
        q += 1
    runs = []
    run = 0
    prev = None
    outside = 0
    run3_outside = 0
    for p in positions:
        run = run + 1 if prev is not None and p == prev + 15 else 1
        if run == 1 and prev is not None:
            runs.append(run)
        if not any(a <= p < b for a, b in pool_spans):
            outside += 1
        prev = p
    if prev is not None:
        runs.append(run)
    # a run >= 3 counts as a candidate vertex-record stretch when it is
    # not inside a located pool span (the N5 second-pool vocabulary)
    for start, ln in iter_runs(positions):
        if ln >= 3 and not any(a <= start < b for a, b in pool_spans):
            run3_outside += 1
    return len(positions), runs, outside, run3_outside


def iter_runs(positions):
    if not positions:
        return
    start = prev = positions[0]
    for p in positions[1:]:
        if p == prev + 15:
            prev = p
            continue
        yield start, prev - start + 1
        start = prev = p
    yield start, prev - start + 1


def raw_signature(bd):
    n = len(bd) // 12
    if n < 2:
        return n, "", ""
    vals = struct.unpack(f"<{n * 3}f", bd[: n * 12])
    nice = sum(1 for v in vals if composite._raw_nice(v)) / (n * 3)
    xs = vals[0::3]
    asc = sum(1 for i in range(n - 1) if xs[i + 1] > xs[i]) / (n - 1)
    return n, f"{nice:.4f}", f"{asc:.4f}"


def tol_count(pool_set, points):
    """Pool vertices present among ``points`` exact-f32, then within
    the committed NOISE_REL relative tolerance (the stage-4b law)."""
    exact = sum(1 for v in pool_set if v in points)
    if exact == len(pool_set):
        return exact, exact
    tol = 0
    for v in pool_set:
        if v in points:
            tol += 1
            continue
        hit = False
        for pt in points:
            if abs(pt[0] - v[0]) <= NOISE_REL * max(1.0, abs(v[0])) and abs(
                pt[1] - v[1]
            ) <= NOISE_REL * max(1.0, abs(v[1])) and abs(pt[2] - v[2]) <= NOISE_REL * max(
                1.0, abs(v[2])
            ):
                hit = True
                break
        tol += 1 if hit else 0
    return exact, tol


def node_census(bd, poolv):
    """Per-token-node census: every token-bearing node's counts and
    whether the committed table law decodes its point region."""
    rows = []
    pos = 0
    while True:
        pos = bd.find(NODE_MAGIC, pos)
        if pos < 0:
            break
        end = bd.find(NODE_MAGIC, pos + 4)
        if end < 0:
            end = len(bd)
        payload = bytes(bd[pos + 4 : end])
        tok = payload.find(LIST_TOKEN)
        if 0 <= tok <= 64:
            p = tok + 5
            try:
                c1, p = composite.read_count(payload, p)
                c2, _p2 = composite.read_count(payload, p)
            except (IndexError, struct.error):
                pos += 1
                continue
            if 0 < c1 <= composite.MAX_ELEMENT_COUNT:
                rows.append({"off": pos, "payload": payload, "c1": c1, "c2": c2})
        pos += 1
    out = []
    pool_set = set(poolv)
    for nr in rows:
        payload, c1, c2 = nr["payload"], nr["c1"], nr["c2"]
        rec = {
            "off": nr["off"], "payload_bytes": len(payload), "c1": c1, "c2": c2,
            "decoded": 0, "points": "", "skips": "", "fail": "", "absorbed_exact": "",
            "absorbed_tol": "",
        }
        try:
            elements, info = composite.decode_region(payload, c1)
        except ExportError as exc:
            rec["fail"] = exc.detail[:160]
        else:
            pts = [pt for _v, pt in elements if pt is not None]
            skips = len(elements) - len(pts)
            rec["decoded"] = 1
            rec["points"] = len(pts)
            rec["skips"] = skips
            if pool_set:
                ex, tl = tol_count(pool_set, set(pts))
                rec["absorbed_exact"] = f"{ex}/{len(pool_set)}"
                rec["absorbed_tol"] = f"{tl}/{len(pool_set)}"
        out.append(rec)
    return out


def census_store(mm, span, family):
    """The element-space byte census of one located span."""
    bd = bytes(mm[span.body_lo : span.body_hi])
    row = {k: "" for k in CFIELDS}
    row["family"] = family
    row["container"] = span.container
    row["tail_law"] = span.tail_law
    row["body_lo"] = span.body_lo
    row["body_hi"] = span.body_hi
    row["body_bytes"] = len(bd)
    groups, kinds = pool.scan_pool_groups(mm, span.body_lo, span.body_hi)
    row["pool_groups"] = len(groups)
    poolv = [v for g in groups for v in g.vertices]
    row["pool_vertices"] = len(poolv)
    row["pool_sizes_head"] = ";".join(str(len(g.vertices)) for g in groups[:8])
    row["kinds"] = _hex(Counter(k.hex(" ") for k in kinds))
    pool_spans = []
    pool_wrap_spans = []
    for g in groups:
        o = g.offset - span.body_lo
        q = o + (15 if bd[o + 10] == 0xFF else 11)
        pool_spans.append((q, q + 15 * g.count_field))
        pool_wrap_spans.append((o, q + 15 * g.count_field))
    # wrapper census over the body (sub-kinds; how many wrappers are
    # accounted by the located pool groups' own wrappers)
    subs = Counter()
    wrap_occ = 0
    under = 0
    w = 0
    while True:
        w = bd.find(FULL_WRAP, w)
        if w < 0:
            break
        wrap_occ += 1
        sub = bd[w + 8 : w + 10].hex(" ")
        subs[sub] += 1
        if any(a <= w < b for a, b in pool_wrap_spans):
            under += 1
        w += 1
    row["wrap_occ"] = wrap_occ
    row["wrap_subkinds"] = _hex(subs)
    row["pool_wrap_under_groups"] = under
    scan = facets.scan_facets(mm, span.body_lo, span.body_hi, clean_store=True)
    row["strip_candidates"] = scan.candidates
    row["strip_records"] = len(scan.records)
    refs = [r for rec in scan.records for r in rec.refs]
    row["max_ref"] = max(refs, default=-1)
    row["markers"] = _hex(Counter(scan.skipped_markers))
    occ, runs, outside, run3 = vrec_runs(bd, pool_spans)
    row["vrec_occ"] = occ
    row["vrec_runs_head"] = ";".join(str(x) for x in runs[:12])
    row["vrec_outside_pool"] = outside
    row["vrec_run3_outside"] = run3
    row["node_magic_hits"] = bd.count(NODE_MAGIC)
    # the "second pool form" negative claim, own walkers (N5 vocabulary
    # + any 01 06 sub-kind OUTSIDE the located pool groups' wrappers)
    v06 = 0
    w = 0
    while True:
        w = bd.find(FULL_WRAP, w)
        if w < 0:
            break
        if bd[w + 8 : w + 10] == b"\x01\x06" and not any(
            a <= w < b for a, b in pool_wrap_spans
        ):
            v06 += 1
        w += 1
    row["second_pool_0106_outside"] = v06
    row["second_pool_vrec_run3"] = run3
    # per-node decode census (the committed table law as measurement)
    nrecs = node_census(bd, poolv)
    row["token_nodes"] = len(nrecs)
    row["nodes_decoded"] = sum(1 for r in nrecs if r["decoded"])
    row["node_rows"] = ";".join(
        f"@{r['off']}:p{r['payload_bytes']}:c{r['c1']}/{r['c2']}"
        + (
            f":d{r['points']}+{r['skips']}abs{r['absorbed_exact']}"
            if r["decoded"]
            else ":FAIL"
        )
        for r in nrecs[:14]
    )
    dec = [r for r in nrecs if r["decoded"]]
    row["c1_max"] = max((r["c1"] for r in nrecs), default=-1)
    if nrecs:
        largest = max(nrecs, key=lambda r: r["payload_bytes"])
        row["c1_of_largest"] = largest["c1"]
        row["largest_node_bytes"] = largest["payload_bytes"]
        row["largest_decoded"] = largest["decoded"]
        row["largest_points"] = largest["points"]
        row["largest_skips"] = largest["skips"]
        row["largest_fail"] = (largest["fail"] or "")[:160]
        row["pool_absorbed_largest"] = largest["absorbed_exact"]
        anyabs = ""
        for r in dec:
            if r["absorbed_exact"] and r["absorbed_exact"].split("/")[0] == str(
                len(poolv)
            ) and len(poolv):
                anyabs = f"@{r['off']}:c{r['c1']}:{r['absorbed_exact']}"
                break
        row["pool_absorbed_any"] = anyabs
    mx = int(row["max_ref"])
    if mx >= 0 and row["c1_max"] not in ("", -1):
        c1m = int(row["c1_max"])
        row["elem_space_c1_vs_maxref"] = (
            "eq" if c1m == mx + 1 else ("gt" if c1m > mx + 1 else "lt")
        )
    if poolv:
        c1m = int(row["c1_max"]) if row["c1_max"] not in ("",) else -1
        row["elem_space_c1_vs_pool"] = (
            "gt" if c1m > len(poolv) else ("eq" if c1m == len(poolv) else "lt")
        )
    n, nice, asc = raw_signature(bd)
    row["raw_triples"] = n
    row["raw_nice_rate"] = nice
    row["raw_xasc_rate"] = asc
    return row


DFIELDS = [
    "sha256", "family", "container", "tail_law",
    "route", "outcome", "fail_detail", "l2_status", "failed_check",
    "vertex_count", "triangle_count", "manifold", "element_decl",
    "node_points", "curve_entries", "stage", "window", "note",
]


def decode_probe(mm, span, sha16, family):
    """The real composite decode, bypassing only the ROUTING predicate.

    ``_export_composite_store`` IS the landed composite path (summary +
    per-rep + mixedwrite fallbacks included); it is called directly on
    the anchor span — the marker-routing check inside
    ``decode_composite_store`` is measured as its own outcome.  For
    marker-less stores (the no-pool facet carriers) the replicated
    single-rep flow (the committed ``find_list_node`` /
    ``decode_region`` / ``parse_strip_records`` / ``_triangulate`` on
    the exporter's window) measures what a routing change WOULD decode
    — recorded under ``route=bypass``, clearly separated.
    """
    rows = []
    groups, kinds = pool.scan_pool_groups(mm, span.body_lo, span.body_hi)
    from catpart.geometry.export import _export_composite_store
    from catpart.fitness.runner import _score_export
    from catpart.geometry import mesh as _mesh

    # (a) the real path, routing predicate untouched
    row = {k: "" for k in DFIELDS}
    row["sha256"] = sha16
    row["family"] = family
    row["container"] = span.container
    row["tail_law"] = span.tail_law
    row["route"] = "real"
    try:
        summary, _pts, _tris = _export_composite_store(mm, span, 0, groups, kinds)
    except ExportError as exc:
        row["outcome"] = "raise"
        row["fail_detail"] = exc.detail[:200]
        rows.append(row)
    else:
        score = _score_export(summary)
        row.update(_scored(score, summary))
        rows.append(row)
        return rows

    # (b) the bypassed flow for marker-less stores (measurement only)
    if not any(k == b"\x01\x02" or k[:1] == b"\xff" for k in kinds):
        lo, hi = span.body_lo, span.body_hi
        for window, node_hi in (
            ("exporter", ( [m.start() for m in facets.STRIP_RE.finditer(mm, lo, hi)] or [hi] )[0]),
            ("full-body", hi),
        ):
            row = {k: "" for k in DFIELDS}
            row["sha256"] = sha16
            row["family"] = family
            row["container"] = span.container
            row["tail_law"] = span.tail_law
            row["route"] = "bypass"
            row["window"] = window
            try:
                ln = composite.find_list_node(mm, lo, node_hi)
                if ln is None:
                    raise ExportError("undecoded-variant", "no token-bearing list node in window")
                payload, elem_decl, _eb = ln
                elements, info = composite.decode_region(payload, elem_decl)
                points = [pt for _v, pt in elements if pt is not None]
                poolv = [v for g in groups for v in g.vertices]
                missing = set(poolv) - set(points)
                if missing:
                    # the landed per-rep fallback (decode_composite_store's
                    # own next step on a pool the region does not absorb)
                    per_pts, per_tris, per_deg, per_info = composite._decode_per_rep(
                        mm, lo, hi, groups, len(missing), len(poolv)
                    )
                    stats = _mesh.mesh_stats(list(per_tris))
                    bmin, bmax = _mesh.bounding_box(per_pts)
                    summary = {
                        "schema_version": 1,
                        "vertex_count": len(per_pts),
                        "triangle_count": len(per_tris),
                        "bounding_box": {"min": bmin, "max": bmax},
                        "warnings": [],
                        "store_ordinal": 0,
                        "origin_kind": span.origin_kind,
                        "pool_group_count": len(groups),
                        "facet_candidate_count": per_info.get("facet_candidates", 0),
                        "facet_record_count": per_info.get("facet_records", 0),
                        "degenerate_triangle_count": per_deg,
                        "mesh": {
                            "edge_count": stats.edge_count,
                            "manifold": stats.manifold,
                            "closed": stats.closed,
                            "oriented": stats.oriented,
                            "boundary_edge_count": stats.boundary_edges,
                        },
                        "composite": dict(per_info),
                    }
                    score = _score_export(summary)
                    row.update(_scored(score, summary))
                    rows.append(row)
                    continue
                records, n_hdrs = composite.parse_strip_records(
                    mm, lo, hi, elem_decl, elements=elements
                )
                all_refs = [
                    rf for _o, mk, _n, _c, refs, _w in records
                    if mk in composite.GATED
                    for rf in refs
                ]
                if all_refs and max(all_refs) >= elem_decl:
                    raise ExportError(
                        "undecoded-variant",
                        f"facet references beyond the element space: max ref "
                        f"{max(all_refs)} >= element count {elem_decl}",
                    )
                triangles, degenerate, _ls = composite._triangulate(elements, records)
                stats = _mesh.mesh_stats(list(triangles))
                bmin, bmax = _mesh.bounding_box(points)
                summary = {
                    "schema_version": 1,
                    "vertex_count": len(points),
                    "triangle_count": len(triangles),
                    "bounding_box": {"min": bmin, "max": bmax},
                    "warnings": [],
                    "store_ordinal": 0,
                    "origin_kind": span.origin_kind,
                    "pool_group_count": len(groups),
                    "facet_candidate_count": n_hdrs,
                    "facet_record_count": len(records),
                    "degenerate_triangle_count": degenerate,
                    "mesh": {
                        "edge_count": stats.edge_count,
                        "manifold": stats.manifold,
                        "closed": stats.closed,
                        "oriented": stats.oriented,
                        "boundary_edge_count": stats.boundary_edges,
                    },
                    "composite": {"stage": "identity-table-walk", "element_decl": elem_decl,
                                  "node_points": len(points), "curve_entries": len(elements) - len(points)},
                }
            except ExportError as exc:
                row["outcome"] = "raise"
                row["fail_detail"] = exc.detail[:200]
                rows.append(row)
                continue
            score = _score_export(summary)
            row.update(_scored(score, summary))
            rows.append(row)
    return rows


def _scored(score, summary):
    comp = summary.get("composite") or {}
    return {
        "outcome": "export",
        "l2_status": score["status"],
        "failed_check": score["failed_check"] or "",
        "vertex_count": summary["vertex_count"],
        "triangle_count": summary["triangle_count"],
        "manifold": summary["mesh"]["manifold"],
        "element_decl": comp.get("element_decl", ""),
        "node_points": comp.get("node_points", ""),
        "curve_entries": comp.get("curve_entries", ""),
        "stage": comp.get("stage", ""),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sha16", action="append", default=[], help="anchor subset")
    args = ap.parse_args(argv)
    ab = list(csv.DictReader(STAGE12_AB_CSV.open()))
    fail_closed = [r for r in ab if r["export_ok"] != "1"]
    s12census = {}
    for r in csv.DictReader(STAGE12_CENSUS_CSV.open()):
        s12census[r["sha256"]] = r["family"]
    manifest = {r["sha256"]: r for r in csv.DictReader(MANIFEST.open())}
    if args.sha16:
        fail_closed = [
            r for r in fail_closed if r["sha256"].startswith(tuple(args.sha16))
        ]
    print(f"stage-12 A/B rows: {len(ab)}; fail-closed: {len(fail_closed)}")

    mrows = []
    crows = []
    drows = []
    fam_count = Counter()
    for sr in sorted(fail_closed, key=lambda r: r["sha256"]):
        sha = sr["sha256"]
        rel = manifest[sha]
        path = ROOT / rel["local_path"]
        mrow = {k: "" for k in MFIELDS}
        mrow["sha256"] = sha
        mrow["split"] = sr["split"]
        mrow["stage12_error_class"] = sr["error_class"]
        crow = None
        with path.open("rb") as fh:
            mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                blocks, _d8, spans, first_err, located = own_spans(mm)
                mrow["spans"] = len(spans)
                composite_spans = 0
                for tag, _ordinal, span in spans:
                    try:
                        _groups, kinds = pool.scan_pool_groups(
                            mm, span.body_lo, span.body_hi
                        )
                    except ExportError:
                        continue
                    if pool.has_composite_space(kinds):
                        composite_spans += 1
                mrow["composite_spans"] = composite_spans
                if composite_spans:
                    mrow["family"] = "composite-failclosed"
                    mrow["note"] = (
                        f"{composite_spans} composite span(s) — outside this "
                        "stage's non-composite families"
                    )
                    fam_count[mrow["family"]] += 1
                    mrow["s12_census_family"] = s12census.get(sha, "")
                    mrow["s12_census_shown"] = 1 if sha in s12census else 0
                    mrow["delta"] = (
                        f"s12-was-{s12census[sha]}" if sha in s12census
                        else "absent-from-s12-census"
                    )
                    mrows.append(mrow)
                    continue
                with tempfile.TemporaryDirectory(prefix="stage13-phasea-") as td:
                    out = Path(td) / f"{sha[:16]}.ply"
                    try:
                        build_export(path, out)
                    except ExportError as exc:
                        mrow["family"] = anchor_family(exc.error_class, exc.detail)
                        mrow["anchor_detail_head"] = exc.detail[:200]
                        mrow["recovered_suffix"] = (
                            1 if "[store recovered via the" in exc.detail else 0
                        )
                    else:
                        mrow["family"] = "exported?!"
                fam_count[mrow["family"]] += 1
                if spans:
                    tag, ordinal, span = spans[0]
                    mrow["container"] = tag
                    mrow["tail_law"] = span.tail_law
                if mrow["family"] in ("no-pool", "refs-beyond"):
                    crow = census_store(mm, span, mrow["family"])
                    crow["sha256"] = sha
                    crows.append(crow)
                    drows.extend(decode_probe(mm, span, sha, mrow["family"]))
            finally:
                mm.close()
        # delta vs the committed stage-12 census (stage-10-baseline artifact)
        mrow["s12_census_family"] = s12census.get(sha, "")
        mrow["s12_census_shown"] = 1 if sha in s12census else 0
        if sha not in s12census:
            if mrow["family"] in ("no-pool", "refs-beyond"):
                mrow["delta"] = "new-surface"
            elif mrow["family"] == "composite-failclosed":
                mrow["delta"] = "composite (stage-12 recovery)"
            else:
                mrow["delta"] = "absent-from-s12-census"
        elif s12census[sha] != mrow["family"] and mrow["family"] != "composite-failclosed":
            mrow["delta"] = f"s12-was-{s12census[sha]}"
        mrows.append(mrow)

    anchor = "-anchor" if args.sha16 else ""
    mout = OUT_DIR / f"stage13-membership{anchor}.csv"
    cout = OUT_DIR / f"stage13-elementspace-census{anchor}.csv"
    dout = OUT_DIR / f"stage13-decode-probe{anchor}.csv"
    with mout.open("w", newline="") as fh:
        wtr = csv.DictWriter(fh, fieldnames=MFIELDS)
        wtr.writeheader()
        wtr.writerows(mrows)
    with cout.open("w", newline="") as fh:
        wtr = csv.DictWriter(fh, fieldnames=CFIELDS)
        wtr.writeheader()
        wtr.writerows(crows)
    with dout.open("w", newline="") as fh:
        wtr = csv.DictWriter(fh, fieldnames=DFIELDS)
        wtr.writeheader()
        wtr.writerows(drows)
    print(f"wrote {mout} ({len(mrows)} rows)")
    print(f"wrote {cout} ({len(crows)} rows)")
    print(f"wrote {dout} ({len(drows)} rows)")

    print("\n== decode probe (the real composite path, routing bypassed) ==")
    real = [r for r in drows if r["route"] == "real"]
    byp = [r for r in drows if r["route"] == "bypass"]
    print(f"  real: {len(real)} — outcomes {Counter(r['outcome'] for r in real).most_common()}")
    exp = [r for r in real if r["outcome"] == "export"]
    print(f"  real exports: {len(exp)} — L2 {Counter(r['l2_status'] for r in exp).most_common()}"
          f" — failed_check {Counter(r['failed_check'] for r in exp).most_common()}")
    print(f"  real raises: {Counter(r['fail_detail'][:60] for r in real if r['outcome']=='raise').most_common(6)}")
    print(f"  bypass rows: {len(byp)} — L2 {Counter(r['l2_status'] for r in byp if r['outcome']=='export').most_common()}"
          f" — failed_check {Counter(r['failed_check'] for r in byp if r['outcome']=='export').most_common()}")
    print(f"  bypass raises: {Counter(r['fail_detail'][:60] for r in byp if r['outcome']=='raise').most_common(6)}")

    print("\n== family taxonomy (exporter anchor, live baseline) ==")
    for fam, n in fam_count.most_common():
        print(f"  {fam}: {n}")
    recov = [r for r in mrows if str(r["recovered_suffix"]) == "1"]
    print(f"rows with the store_recovery failure suffix: {len(recov)}")
    newsurf = [r for r in mrows if r["delta"] == "new-surface"]
    print(f"new-surface rows (not in the s12 census): {len(newsurf)}")
    by = Counter((r["family"], r["s12_census_family"] or "-") for r in mrows)
    print("family x s12-census-family:")
    for k, v in sorted(by.items()):
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
