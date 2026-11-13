#!/usr/bin/env python3
"""Stage-14 Phase A (#34): the empty-mesh and not-manifold export
families — live memberships + byte-level mechanism census at the
stage-13 LANDED baseline (main a3edbab).

Population: the exported rows of the accepted stage-13 A/B
(``stage13-identity-export-files.csv``, ``export_ok == 1``) that fail
the L2 gate — ``failed_check == empty-mesh`` (triangles == 0) or
``not-manifold`` (an undirected edge used more than twice,
:func:`catpart.geometry.mesh.mesh_stats`).  Re-derived LIVE: the full
A/B re-run at a3edbab (``ab_identity_export.py``) is byte-identical to
the committed CSV (measured before this probe; the anchor is stable),
and every family row below is re-exported here through
``build_export`` with the census instrumentation attached.

Two passes per family row:

  anchor — the exporter black box (``build_export``) with module-level
    wrappers recording every committed-decode call: ``decode_region``,
    ``parse_strip_records``, ``_triangulate``, ``_decode_per_rep``,
    ``_decode_mixedwrite``.  The committed code runs UNMODIFIED (the
    wrappers observe; analysis only, ``src/`` untouched).

  census (this probe's own walkers) —
    empty-mesh: per store, every facet loop of the exported markers
      (0x42/0x4a/0x4c) classified from the captured records/elements:
      loops referencing ONLY written elements vs loops touching skip
      slots (curve entries, U4); the written loops' triangle outcome
      (exported / degenerate-skipped, with the degenerate cause: index
      repeat, duplicate coordinates, zero cross product); the
      ``no-facet-records`` collapse pattern; the E0-b dup-pin
      evaluation's decline reason (normal-less / nonplanar /
      unpinnable / fired-with-zero-triangles).
    not-manifold: the over-used edges (use count >= 3) of the final
      triangle soup, each incident triangle attributed to its source
      record offset + loop (own triangle attribution replicating
      :func:`composite._loop_triangles` semantics); identical-duplicate
      triples (a duplicated-parse artifact) vs distinct triples
      (content fins); duplicate-coordinate vertices; boundary/oriented
      state; the dedup ceiling (drop duplicate extras -> manifold?).

  ceiling probes —
    dup-pin-ALL (empty-mesh, U4 class): every dropped loop exported
      under the U4-D dup law WITHOUT the E0-b battery, gate-scored
      (:func:`runner._score_export`'s checks) — the measured ceiling of
      relaxing the battery criterion.  The committed conservative rule
      itself is NOT changed here (the U4 rule stands unless the bytes
      overturn it; this probe only measures).
    dedup (not-manifold): duplicate identical index triples dropped,
      mesh re-scored — the measured ceiling of a duplicated-parse law.

Membership CSVs committed with the note:
  stage14-export-failures-census.csv (one row per family store)
  stage14-dup-pin-ceiling.csv        (per empty-mesh store with dropped loops)
  stage14-notmanifold-mechanism.csv  (per not-manifold store)
Anchor runs (``--sha16``) write ``*-anchor.csv`` so committed CSVs are
never clobbered.  Run:
  python3 -I scripts/triage/stage14_export_failure_probe.py
"""

import argparse
import csv
import mmap
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"
AB_CSV = OUT_DIR / "stage13-identity-export-files.csv"

sys.path.insert(0, str(ROOT / "src"))

from catpart.geometry import composite, mesh, store  # noqa: E402
from catpart.geometry.errors import ExportError  # noqa: E402
from catpart.geometry.export import build_export  # noqa: E402

EXPORTED_MARKERS = (0x42, 0x4A, 0x4C)
GATED = composite.GATED

CFIELDS = [
    "sha256", "split", "family", "stage", "mechanism",
    "span_container", "span_tail_law", "body_bytes",
    "strip_candidates", "facet_records", "markers_exported",
    "markers_skipped", "loops_total", "loops_written", "loops_skip_ref",
    "tris_written_loops", "degenerate_written", "deg_index_repeat",
    "deg_coord_dup", "deg_cross_zero",
    "dup_pin_evaluated", "dup_pin_outcome",
    "vertex_count", "triangle_count", "element_decl", "node_points",
    "curve_entries", "loops_curve_entry", "duplicate_coord_points",
    "overuse_edges", "overuse_max", "dup_triangle_extras",
    "dedup_manifold", "territory_overlap_records", "boundary_edges",
    "oriented", "note",
]

DFIELDS = [
    "sha256", "split", "stage", "dropped_loops", "dropped_skips",
    "pin_unpinnable", "normal_less_loops", "nonplanar_loops",
    "pinned_tris", "pinned_degenerate", "ceiling_gate", "ceiling_pass",
    "e0b_declined",
]

NFIELDS = [
    "sha256", "split", "stage", "triangles", "overuse_edges",
    "overuse_max", "overuse_by_count", "dup_triangle_extras",
    "repeat_ref_edges", "crossloop_edges", "coplanar_overlap_edges",
    "fin_edges", "duplicate_coord_points",
    "boundary_edges", "oriented", "dedup_manifold", "dedup_leftover",
    "mechanism", "note",
]


# --- the capture layer (the committed code runs unmodified) ------------

CAP: dict = {}


def _install_captures():
    orig_triangulate = composite._triangulate
    orig_parse = composite.parse_strip_records
    orig_per_rep = composite._decode_per_rep
    orig_mixedwrite = composite._decode_mixedwrite

    def cap_triangulate(elements, records):
        tris, deg, stats = orig_triangulate(elements, records)
        CAP["tri_calls"].append(
            {
                "elements": list(elements),
                "records": list(records),
                "tris": list(tris),
                "deg": deg,
                "stats": dict(stats),
            }
        )
        return tris, deg, stats

    def cap_parse(data, lo, hi, element_count, elements=None):
        out, n_hdrs = orig_parse(data, lo, hi, element_count, elements=elements)
        CAP["parse_calls"].append(
            {"lo": lo, "hi": hi, "elem": element_count, "n_hdrs": n_hdrs,
             "offsets": [o for o, *_r in out]}
        )
        return out, n_hdrs

    def cap_per_rep(*a, **kw):
        out = orig_per_rep(*a, **kw)
        CAP["per_rep_result"] = out[3]
        return out

    def cap_mixedwrite(*a, **kw):
        out = orig_mixedwrite(*a, **kw)
        CAP["mixedwrite_result"] = out[3]
        return out

    composite._triangulate = cap_triangulate
    composite.parse_strip_records = cap_parse
    composite._decode_per_rep = cap_per_rep
    composite._decode_mixedwrite = cap_mixedwrite


_install_captures()


def reset_captures():
    CAP.clear()
    CAP["tri_calls"] = []
    CAP["parse_calls"] = []


# --- own span walk (the stage-13 probe's method, ported) ---------------

def own_spans(mm):
    """``export._export_data``'s probe order, replicated and recorded."""
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
        others = [
            (b, nm) for b, nm in blocks if nm not in store.NAMED_PROBE_CONTAINERS
        ]
        for ordinal, (blk, _nm) in enumerate(others):
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
    return spans


# --- own loop-level census (the wrappers' captures, this probe's math) --

def own_loop_census(call):
    """Per-:func:`_triangulate`-call loop census with own triangle
    attribution (the committed loop semantics, re-implemented here so
    every triangle maps to its (record offset, marker, loop) source).

    Returns a dict with the loop partitions and the per-triangle
    provenance ``[(tri, off, mk, loop_idx)]`` plus the degenerate-cause
    counters over the written loops."""
    elements = call["elements"]
    records = call["records"]
    skips = {i for i, (_v, pt) in enumerate(elements) if pt is None}
    written_rank: dict[int, int] = {}
    points = []
    for i, (_v, pt) in enumerate(elements):
        if pt is not None:
            written_rank[i] = len(written_rank)
            points.append(pt)
    loops_total = loops_written = loops_skip = 0
    tris = []
    tri_source = []
    deg = Counter()
    for off, mk, _normal, counts, refs, _w in records:
        if mk not in EXPORTED_MARKERS:
            continue
        o = 0
        for li, c in enumerate(counts):
            loop = refs[o : o + c]
            o += c
            if not loop:
                continue
            loops_total += 1
            if any(r in skips for r in loop):
                loops_skip += 1
                continue
            loops_written += 1
            idxs = [written_rank[r] for r in loop]
            lp = [points[i] for i in idxs]
            if mk == 0x4C:
                for t in range(1, len(lp) - 1):
                    a, b, cc = lp[0], lp[t], lp[t + 1]
                    tri = (idxs[0], idxs[t], idxs[t + 1])
                    if a == b or b == cc or a == cc:
                        if idxs[0] == idxs[t] or idxs[t] == idxs[t + 1] or idxs[0] == idxs[t + 1]:
                            deg["index_repeat"] += 1
                        else:
                            deg["coord_dup"] += 1
                        continue
                    tris.append(tri)
                    tri_source.append((tri, off, mk, li))
            else:
                for t in range(len(lp) - 2):
                    tri = (idxs[t], idxs[t + 1], idxs[t + 2])
                    a, b, cc = lp[t], lp[t + 1], lp[t + 2]
                    if idxs[t] == idxs[t + 1] or idxs[t + 1] == idxs[t + 2] or idxs[t] == idxs[t + 2]:
                        deg["index_repeat"] += 1
                        continue
                    if a == b or b == cc or a == cc:
                        deg["coord_dup"] += 1
                        continue
                    if composite._cross_zero(a, b, cc):
                        deg["cross_zero"] += 1
                        continue
                    if t % 2 == 1:
                        tri = (tri[2], tri[1], tri[0])
                    tris.append(tri)
                    tri_source.append((tri, off, mk, li))
    return {
        "loops_total": loops_total,
        "loops_written": loops_written,
        "loops_skip": loops_skip,
        "tris": tris,
        "tri_source": tri_source,
        "deg": deg,
        "points": points,
        "written_rank": written_rank,
        "skips": skips,
        "elements": elements,
        "records": records,
    }


def dup_pin_all(censuses, bases):
    """The U4-D dup law WITHOUT the E0-b battery (the ceiling probe):
    every dropped loop of every call exports with its loop-referenced
    skip slots welded to the written vertex of the immediately
    preceding written element.  Returns ``(triangles, degenerate)``
    store-indexed, or ``None`` when a referenced skip slot has no
    preceding written element (unpinnable)."""
    all_tris = []
    degenerate = 0
    for cen, base in zip(censuses, bases):
        elements = cen["elements"]
        skips = cen["skips"]
        dropped = []
        for off, mk, _normal, counts, refs, _w in cen["records"]:
            if mk not in EXPORTED_MARKERS:
                continue
            o = 0
            for c in counts:
                loop = refs[o : o + c]
                o += c
                if loop and any(r in skips for r in loop):
                    dropped.append((mk, loop))
        if not dropped:
            continue
        pin: dict[int, int] = {}
        for _mk, loop in dropped:
            for r in loop:
                if r in skips and r not in pin:
                    j = r - 1
                    while j >= 0 and elements[j][1] is None:
                        j -= 1
                    if j >= 0:
                        pin[r] = j
        if any(r in skips and r not in pin for _mk, loop in dropped for r in loop):
            return None
        pinned = list(elements)
        for r, j in pin.items():
            pinned[r] = (1, elements[j][1])
        for mk, loop in dropped:
            resolved = [pin.get(r, r) for r in loop]
            idxs = [cen["written_rank"][r] for r in resolved]
            lp = [cen["points"][i] for i in idxs]
            if mk == 0x4C:
                for t in range(1, len(lp) - 1):
                    a, b, cc = lp[0], lp[t], lp[t + 1]
                    if a == b or b == cc or a == cc:
                        degenerate += 1
                        continue
                    all_tris.append(
                        (idxs[0] + base, idxs[t] + base, idxs[t + 1] + base)
                    )
            else:
                for t in range(len(lp) - 2):
                    tri = (idxs[t], idxs[t + 1], idxs[t + 2])
                    a, b, cc = lp[t], lp[t + 1], lp[t + 2]
                    if a == b or b == cc or a == cc:
                        degenerate += 1
                        continue
                    if composite._cross_zero(a, b, cc):
                        degenerate += 1
                        continue
                    if t % 2 == 1:
                        tri = (tri[2], tri[1], tri[0])
                    all_tris.append((tri[0] + base, tri[1] + base, tri[2] + base))
    return all_tris, degenerate


def gate_score(vertex_count, triangles, degenerate, points):
    """:func:`runner._score_export`'s checks (the gate order)."""
    if vertex_count < 1 or len(triangles) < 1:
        return "empty-mesh"
    stats = mesh.mesh_stats(list(triangles))
    if not stats.manifold:
        return "not-manifold"
    lo = [min(p[i] for p in points) for i in range(3)]
    hi = [max(p[i] for p in points) for i in range(3)]
    if not all(v == v and abs(v) != float("inf") for v in (*lo, *hi)):
        return "nonfinite-bbox"
    if degenerate > 0:
        return "degenerate-triangles"
    return "pass"


def e0b_decline_reasons(censuses):
    """Why the committed E0-b evaluation declined (own re-derivation of
    the battery criterion over the captured dropped loops)."""
    normal_less = 0
    nonplanar = 0
    unpinnable = False
    for cen in censuses:
        elements = cen["elements"]
        skips = cen["skips"]
        pin: dict[int, int] = {}
        dropped = []
        for off, mk, normal, counts, refs, _w in cen["records"]:
            if mk not in EXPORTED_MARKERS:
                continue
            o = 0
            for c in counts:
                loop = refs[o : o + c]
                o += c
                if loop and any(r in skips for r in loop):
                    dropped.append((mk, normal, loop))
        for _mk, _normal, loop in dropped:
            for r in loop:
                if r in skips and r not in pin:
                    j = r - 1
                    while j >= 0 and elements[j][1] is None:
                        j -= 1
                    if j >= 0:
                        pin[r] = j
        for _mk, normal, loop in dropped:
            for r in loop:
                if r in skips and r not in pin:
                    unpinnable = True
        for _mk, normal, loop in dropped:
            if normal is None:
                normal_less += 1
                continue
            pinned = list(elements)
            for r, j in pin.items():
                pinned[r] = (1, elements[j][1])
            st, _res = composite._loop_plane_status(loop, normal, pinned)
            if st != "coplanar":
                nonplanar += 1
    return normal_less, nonplanar, unpinnable


# --- the not-manifold edge census --------------------------------------

def edge_census(triangles):
    """Undirected-edge histogram + the over-used edges' incident
    triangles (distinct vs duplicate extras)."""
    edge: dict[tuple[int, int], list] = {}
    for tri in triangles:
        for e in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            edge.setdefault(tuple(sorted(e)), []).append(tri)
    over = {e: ts for e, ts in edge.items() if len(ts) > 2}
    triple_counts = Counter(triangles)
    dup_extras = sum(c - 1 for c in triple_counts.values() if c > 1)
    return edge, over, dup_extras


def dedup_manifold(triangles):
    """Drop duplicate identical triples (keep one), re-score."""
    seen = set()
    out = []
    for tri in triangles:
        if tri not in seen:
            seen.add(tri)
            out.append(tri)
    return mesh.mesh_stats(out).manifold, out


# --- the main census ----------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--include-sha16", default="")
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    ap.add_argument("--suffix", default="")
    args = ap.parse_args()

    ab = list(csv.DictReader(AB_CSV.open()))
    manifest = {
        r["sha256"]: r
        for r in csv.DictReader(MANIFEST.open())
        if r["split"] in ("dev", "held-out") and r["kind"] == "part"
    }
    family_rows = [
        r
        for r in ab
        if r["export_ok"] == "1"
        and r["l2_status"] == "fail"
        and r["failed_check"] in ("empty-mesh", "not-manifold")
    ]
    if args.include_sha16:
        want = {h for h in args.include_sha16.split(",") if h}
        family_rows = [r for r in family_rows if r["sha256"][:16] in want]
    print(
        f"population: {len(family_rows)} exported rows failing the L2 gate "
        f"({Counter(r['failed_check'] for r in family_rows)})"
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    c_path = out_dir / f"stage14-export-failures-census{args.suffix}.csv"
    d_path = out_dir / f"stage14-dup-pin-ceiling{args.suffix}.csv"
    n_path = out_dir / f"stage14-notmanifold-mechanism{args.suffix}.csv"

    census_rows = []
    dup_rows = []
    nm_rows = []
    mech_counter = Counter()

    with tempfile.TemporaryDirectory(prefix="catpart-stage14-") as scratch:
        scratch_dir = Path(scratch)
        for row in family_rows:
            sha = row["sha256"]
            path = ROOT / manifest[sha]["local_path"]
            reset_captures()
            summary = build_export(path, scratch_dir / f"{sha[:16]}.ply")
            info = summary.get("composite") or {}
            stage = info.get("stage", "")

            # own span walk + the winning span (the one whose body the
            # captured parse territories fall inside)
            with open(path, "rb") as fh:
                mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            spans = own_spans(mm)
            body = None
            for _tag, _ord, span in spans:
                if all(
                    c["lo"] >= span.body_lo and c["hi"] <= span.body_hi
                    for c in CAP["parse_calls"]
                ):
                    body = span
                    break
            body_bytes = (body.body_hi - body.body_lo) if body else ""
            container = body.container if body else ""
            tail_law = body.tail_law if body else ""
            mm.close()

            censuses = [own_loop_census(c) for c in CAP["tri_calls"]]
            # per-rep bases: the k-th call's base = the written points of
            # the previous calls (exported reps append their full pts)
            bases = []
            acc = 0
            for cen in censuses:
                bases.append(acc)
                acc += len(cen["points"])
            store_points = acc
            store_tris = []
            tri_source = []
            for cen, base in zip(censuses, bases):
                store_tris.extend((a + base, b + base, c + base) for a, b, c in cen["tris"])
                tri_source.extend((t, off, mk, li) for t, off, mk, li in cen["tri_source"])
            loops_total = sum(c["loops_total"] for c in censuses)
            loops_written = sum(c["loops_written"] for c in censuses)
            loops_skip = sum(c["loops_skip"] for c in censuses)
            deg = Counter()
            for cen in censuses:
                deg.update(cen["deg"])

            # duplicate-coordinate vertices in the exported element space
            pt_counter = Counter(
                tuple(p) for cen in censuses for p in cen["points"]
            )
            duplicate_coord_points = sum(c - 1 for c in pt_counter.values() if c > 1)

            # record territory overlap: the same record offset parsed by
            # two calls of the same store (a double-parse artifact)
            seen_offsets = Counter()
            for cen in censuses:
                for off, *_r in cen["records"]:
                    seen_offsets[off] += 1
            territory_overlap = sum(c - 1 for c in seen_offsets.values() if c > 1)

            dup_pin_evaluated = any("dup_pin" in c["stats"] for c in CAP["tri_calls"])
            dup_pin_fired = bool(info.get("curve_entry_law"))

            strip_candidates = sum(c["n_hdrs"] for c in CAP["parse_calls"])
            facet_records = sum(
                len(cen["records"]) for cen in censuses
            )
            markers_exported = Counter()
            markers_skipped = Counter(info.get("skipped_markers") or {})
            for cen in censuses:
                for _o, mk, _n, _c, _refs, _w in cen["records"]:
                    if mk in EXPORTED_MARKERS:
                        markers_exported[mk] += 1

            note_bits = []
            if body is None:
                note_bits.append("span-not-matched")

            # ---------- family classification ----------
            family = row["failed_check"]
            c_row = {k: "" for k in CFIELDS}
            c_row.update(
                {
                    "sha256": sha,
                    "split": row["split"],
                    "family": family,
                    "stage": stage,
                    "span_container": container,
                    "span_tail_law": tail_law,
                    "body_bytes": body_bytes,
                    "strip_candidates": strip_candidates,
                    "facet_records": facet_records,
                    "markers_exported": dict(markers_exported) or "",
                    "markers_skipped": dict(markers_skipped) or "",
                    "loops_total": loops_total,
                    "loops_written": loops_written,
                    "loops_skip_ref": loops_skip,
                    "tris_written_loops": len(store_tris),
                    "degenerate_written": sum(deg.values()),
                    "deg_index_repeat": deg["index_repeat"],
                    "deg_coord_dup": deg["coord_dup"],
                    "deg_cross_zero": deg["cross_zero"],
                    "dup_pin_evaluated": int(dup_pin_evaluated),
                    "vertex_count": summary["vertex_count"],
                    "triangle_count": summary["triangle_count"],
                    "element_decl": info.get("element_decl", ""),
                    "node_points": info.get("node_points", ""),
                    "curve_entries": info.get("curve_entries", ""),
                    "loops_curve_entry": info.get("loops_curve_entry", ""),
                    "duplicate_coord_points": duplicate_coord_points,
                    "territory_overlap_records": territory_overlap,
                    "note": "; ".join(note_bits),
                }
            )

            if family == "empty-mesh":
                if facet_records == 0 and loops_total == 0:
                    mechanism = "no-facet-records"
                elif loops_written == 0 and loops_skip > 0:
                    mechanism = "u4-curve-entry-all-loops"
                elif loops_written > 0 and len(store_tris) == 0:
                    mechanism = (
                        "written-loops-all-degenerate"
                        if loops_skip == 0
                        else "mixed-skips-and-degenerate"
                    )
                elif loops_total == 0:
                    mechanism = "records-without-loops"
                else:
                    mechanism = "other-empty"
                c_row["mechanism"] = mechanism
                # the E0-b decline reason + the dup-pin-ALL ceiling
                if loops_skip > 0:
                    normal_less, nonplanar, unpinnable = e0b_decline_reasons(censuses)
                    pin = dup_pin_all(censuses, bases)
                    d_row = {k: "" for k in DFIELDS}
                    d_row.update(
                        {
                            "sha256": sha,
                            "split": row["split"],
                            "stage": stage,
                            "dropped_loops": loops_skip,
                            "dropped_skips": info.get("curve_entries", ""),
                            "pin_unpinnable": int(unpinnable),
                            "normal_less_loops": normal_less,
                            "nonplanar_loops": nonplanar,
                            "e0b_declined": (
                                "fired" if dup_pin_fired else
                                "unpinnable" if unpinnable else
                                "normal-less" if normal_less else
                                "nonplanar" if nonplanar else "none"
                            ),
                        }
                    )
                    if pin is None:
                        d_row["ceiling_gate"] = "unpinnable"
                        c_row["dup_pin_outcome"] = "unpinnable"
                    else:
                        tris, pdeg = pin
                        gate = gate_score(store_points, tris, pdeg, [p for cen in censuses for p in cen["points"]])
                        d_row["pinned_tris"] = len(tris)
                        d_row["pinned_degenerate"] = pdeg
                        d_row["ceiling_gate"] = gate
                        d_row["ceiling_pass"] = int(gate == "pass")
                        c_row["dup_pin_outcome"] = f"pin-all:{gate}"
                    dup_rows.append(d_row)
            else:
                # not-manifold: the over-used edge census + dedup ceiling
                edge, over, dup_extras = edge_census(store_tris)
                tri_by_tuple = {}
                for t, off, mk, li in tri_source:
                    tri_by_tuple.setdefault(t, []).append((off, mk, li))
                # per-over-edge cause: duplicate triples / a repeated-ref
                # source loop / distinct loops sharing the edge
                loops_by_key = {}
                for cen in censuses:
                    for off, mk, _n, counts, refs, _w in cen["records"]:
                        if mk not in EXPORTED_MARKERS:
                            continue
                        o = 0
                        for li, c in enumerate(counts):
                            loops_by_key[(off, li)] = refs[o : o + c]
                            o += c
                cause_dup = cause_repeat = cause_crossloop = 0
                coplanar_overlap = fin_edges = 0
                pts_by_idx = {}
                for cen, base in zip(censuses, bases):
                    for li, p in enumerate(cen["points"]):
                        pts_by_idx[base + li] = p
                for e, ts in over.items():
                    distinct = set(ts)
                    offs = {
                        tri_by_tuple[t][0][0] for t in distinct if tri_by_tuple.get(t)
                    }
                    loops = {
                        tri_by_tuple[t][0][:2] for t in distinct if tri_by_tuple.get(t)
                    }
                    if any(
                        sum(1 for tt in ts if tt == t) > 1 for t in distinct
                    ):
                        cause_dup += 1
                    if any(
                        len(set(loops_by_key[k])) < len(loops_by_key[k])
                        for k in loops
                        if k in loops_by_key
                    ):
                        cause_repeat += 1
                    if len(loops) > 1:
                        cause_crossloop += 1
                    if len(distinct) > 1:
                        # coplanar overlap vs a real fold at this edge
                        normals = set()
                        for t in distinct:
                            a, b, c = (pts_by_idx.get(i) for i in t)
                            if None in (a, b, c):
                                continue
                            ab = tuple(b[i] - a[i] for i in range(3))
                            ac = tuple(c[i] - a[i] for i in range(3))
                            cr = (
                                ab[1] * ac[2] - ab[2] * ac[1],
                                ab[2] * ac[0] - ab[0] * ac[2],
                                ab[0] * ac[1] - ab[1] * ac[0],
                            )
                            n = sum(v * v for v in cr) ** 0.5
                            normals.add(
                                None if n == 0 else tuple(round(v / n, 6) for v in cr)
                            )
                        normals.discard(None)
                        if len(normals) <= 1:
                            coplanar_overlap += 1
                        else:
                            fin_edges += 1
                dm, dedup_tris = dedup_manifold(store_tris)
                over_by_count = Counter(len(ts) for ts in over.values())
                if dup_extras and dm:
                    nm_mech = "duplicate-triangles-dedup-solves"
                elif dup_extras and not dm:
                    nm_mech = "duplicate-triangles-plus-content"
                elif over and cause_repeat == len(over) and cause_crossloop == 0:
                    nm_mech = "repeat-ref-loops"
                elif fin_edges:
                    nm_mech = "content-fins"
                elif coplanar_overlap:
                    nm_mech = "coplanar-overlap"
                else:
                    nm_mech = "other-nm"
                c_row["mechanism"] = nm_mech
                c_row["overuse_edges"] = len(over)
                c_row["overuse_max"] = max((len(ts) for ts in over.values()), default=0)
                c_row["dup_triangle_extras"] = dup_extras
                c_row["dedup_manifold"] = int(dm)
                c_row["boundary_edges"] = sum(
                    1 for ts in edge.values() if len(ts) == 1
                )
                c_row["oriented"] = int(_oriented(store_tris))
                n_row = {k: "" for k in NFIELDS}
                n_row.update(
                    {
                        "sha256": sha,
                        "split": row["split"],
                        "stage": stage,
                        "triangles": len(store_tris),
                        "overuse_edges": len(over),
                        "overuse_max": max((len(ts) for ts in over.values()), default=0),
                        "overuse_by_count": dict(sorted(over_by_count.items())) or "",
                        "dup_triangle_extras": dup_extras,
                        "repeat_ref_edges": cause_repeat,
                        "crossloop_edges": cause_crossloop,
                        "coplanar_overlap_edges": coplanar_overlap,
                        "fin_edges": fin_edges,
                        "duplicate_coord_points": duplicate_coord_points,
                        "boundary_edges": c_row["boundary_edges"],
                        "oriented": c_row["oriented"],
                        "dedup_manifold": int(dm),
                        "dedup_leftover": len(over) if not dm else sum(
                            1 for _e, ts in edge_census(dedup_tris)[1].items() if len(ts) > 2
                        ),
                        "mechanism": nm_mech,
                        "note": "; ".join(note_bits),
                    }
                )
                nm_rows.append(n_row)

            mech_counter[(family, c_row["mechanism"])] += 1
            census_rows.append(c_row)
            print(
                f"  {sha[:16]} {family:13s} {stage:24s} "
                f"{c_row['mechanism']}"
            )

    for path, fields, rows in (
        (c_path, CFIELDS, census_rows),
        (d_path, DFIELDS, dup_rows),
        (n_path, NFIELDS, nm_rows),
    ):
        with path.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {path} ({len(rows)} rows)")

    print("\n== mechanism taxonomy ==")
    for (family, mech), n in sorted(mech_counter.items()):
        print(f"  {family:13s} {mech:38s} {n}")


def _oriented(triangles):
    directed: Counter = Counter()
    for tri in triangles:
        for e in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            directed[e] += 1
    return int(
        all(directed[(a, b)] == directed[(b, a)] for (a, b) in directed)
    )


if __name__ == "__main__":
    sys.exit(main())
