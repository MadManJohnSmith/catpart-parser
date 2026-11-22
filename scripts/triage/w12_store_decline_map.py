#!/usr/bin/env python3
"""W12 store decline map — the store side of the inverse oracle
(read-only, 2026-11-22).

Bridges the geometry-side missing-face clusters
(``w12_inverse_oracle.py``) to the concrete declined/not-decoded
records of the .CATPart. Since declined records carry no coordinates
(their geometry is never decoded), the bridge runs through four
coordinate-bearing signals, all reusing the committed decode laws with
zero ``src/`` changes:

- ``unused-pool-vertices`` — written pool points no emitted triangle
  references. Their positions are known (the pool is re-listed
  verbatim), so they cluster spatially and fall inside the missing
  clusters' bboxes; a missing face's vertices MUST be pool vertices,
  and an unused one is a vertex whose connectivity was declined.
- ``seam/dedup-skipped loops`` — the pre-emission vs final triangle
  identity diff (the composite decode run with ``_seam_area=None``
  gives the exact pre-seam emission the shipped seam decided to skip;
  the registry default gives the final). Dropped triangles'
  coordinates are known — the strongest spatial evidence.
- ``unexported-rep-vertices`` — a pool group whose rep the per-rep
  decomposition declined (``reps_unexported``) never enters the decode
  points at all; its pool vertices' positions are the declined rep's
  geometry, named with the decline reason (not decodificado).
- ``gap records`` — the probe_top10 gap framing run PER REP over the
  rep's own territory (``region_end`` → the next token node — the
  decode's own windows, via the committed node scan) — every
  unresolved candidate header with its marker, byte offset and the
  per-law diagnosis (``diag_short``/``diag_extended`` reused verbatim).
  Each gap reports the would-be element-index interval (max written
  ref before the gap, min written ref after — labeled INFERENCE: the
  walk order makes it likely, not proven) and the unused pool
  positions whose element index falls inside — the record→cluster
  join.

The identity-per-rep decode concatenates the exported reps' points
(each rep re-lists its pool group verbatim), and emitted triangle
indices are store-level: rep base + written index. Unused vertices
The registry decode pops ``info['_space_offsets']`` without
re-attaching it, so the rep bases are rebuilt by the decode's own
rules (absorption + refs gate, verified against ``len(points)`` — the
``base_check``). Within a rep, a written index maps to its element
index by the rep's own skip layout. The first single-node framing was
WRONG here (9,428 pseudo-gaps): this store's facets live in per-rep
territories after their own token nodes, not in one body-wide window.

Run (reproduction commands live in the W12 evidence note)::

    python -B scripts/triage/w12_store_decline_map.py \
        --pair audi-r8 --pairs-json ~/.local/state/catpart-parser/bench-external/pairs.json \
        --records-csv docs/evidence/data/w12-declined-records-audi-r8.csv \
        --spatial-csv docs/evidence/data/w12-store-spatial-audi-r8.csv

Read-only over the data; nothing in ``src/`` or ``port/`` changes.
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from catpart.geometry import composite, facets, pool  # noqa: E402 - path setup first
from catpart.geometry.errors import ExportError  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from w12_oracle_lib import (  # noqa: E402 - sibling triage module
    cluster_cells,
    heron_area,
    load_harness,
    load_triage,
    loop_key_set,
)

PROBE = load_triage("probe_top10_mesh_gap_dump")


def decode_span(data, span, groups, kinds, seam_area=...):
    """One composite decode with the named seam mode (… = registry default)."""
    kwargs = {} if seam_area is ... else {"_seam_area": seam_area}
    return composite.decode_composite_store(data, span, groups, kinds, **kwargs)


def _tri_key(points, tri):
    p = sorted((
        (round(points[tri[0]][0], 3), round(points[tri[0]][1], 3), round(points[tri[0]][2], 3)),
        (round(points[tri[1]][0], 3), round(points[tri[1]][1], 3), round(points[tri[1]][2], 3)),
        (round(points[tri[2]][0], 3), round(points[tri[2]][1], 3), round(points[tri[2]][2], 3)),
    ))
    return struct.pack("<9f", p[0][0], p[0][1], p[0][2], p[1][0], p[1][1], p[1][2],
                       p[2][0], p[2][1], p[2][2])


def diff_dropped(pre_points, pre_triangles, final_points, final_triangles):
    """The pre-emission triangles absent from the final mesh, as
    coordinate triples (the emission laws' drops: seam skips, relist
    skips, dedup drops)."""
    final_keys = loop_key_set(final_points, final_triangles)
    dropped = []
    for tri in pre_triangles:
        if _tri_key(pre_points, tri) in final_keys:
            continue
        dropped.append((pre_points[tri[0]], pre_points[tri[1]], pre_points[tri[2]]))
    return dropped


def cluster_points(positions, cell):
    """Spatial clusters of point positions (bbox + count per cluster)."""
    cells: dict = {}

    class _A:
        __slots__ = ("n", "minx", "miny", "minz", "maxx", "maxy", "maxz")

    for x, y, z in positions:
        key = (int(x // cell), int(y // cell), int(z // cell))
        agg = cells.get(key)
        if agg is None:
            if len(cells) >= 4_000_000:
                raise MemoryError(f"cell-budget-exceeded: {len(cells)} cells in cluster_points")
            agg = cells[key] = _A()
            agg.n = 0
            agg.minx = agg.maxx = x
            agg.miny = agg.maxy = y
            agg.minz = agg.maxz = z
        agg.n += 1
        agg.minx, agg.maxx = min(agg.minx, x), max(agg.maxx, x)
        agg.miny, agg.maxy = min(agg.miny, y), max(agg.maxy, y)
        agg.minz, agg.maxz = min(agg.minz, z), max(agg.maxz, z)
    out = []
    for member_keys in cluster_cells(cells):
        out.append(
            {
                "n": sum(cells[k].n for k in member_keys),
                "bbox_min": (min(cells[k].minx for k in member_keys),
                             min(cells[k].miny for k in member_keys),
                             min(cells[k].minz for k in member_keys)),
                "bbox_max": (max(cells[k].maxx for k in member_keys),
                             max(cells[k].maxy for k in member_keys),
                             max(cells[k].maxz for k in member_keys)),
            }
        )
    return out


def diagnose_candidate(data, o, nxt, hi, elem_decl):
    """The per-law diagnosis for one unresolved candidate (the probe's
    dump logic, compacted)."""
    mk = data[o + 1] if o + 1 < len(data) else -1
    if mk in facets.NORMAL_MARKERS_ALL or mk in (0x42, 0x43, 0x44, 0x45, 0x46):
        d = PROBE.diag_short(data, o, nxt, hi, elem_decl, mk)
        if "error" in d:
            return f"short 0x{mk:02x}: {d['error']}"
        cap = "cap-blocked" if d.get("cap_blocked") else ""
        return (
            f"short 0x{mk:02x} hlen={d.get('hlen')} n={d.get('n')} "
            f"first_count={d.get('first_count')} min_k={d.get('min_k')} {cap}"
        ).strip()
    d = PROBE.diag_extended(data, o, hi, elem_decl, [])
    law6 = d.get("law6") or {}
    return (
        f"ext 0x{mk:02x} hlen={d.get('hlen')} "
        f"law6(n={law6.get('n')}, n_law={law6.get('n_law')}, gap={law6.get('n_law_gap')})"
    ).strip()


def add_spatial(spat_rows, pair_name, source, span_i, label, positions, cell_mm):
    """Cluster positions and append spatial rows (label carries the rep
    or reason)."""
    if not positions:
        return
    for ci, c in enumerate(cluster_points(positions, cell_mm)):
        spat_rows.append((pair_name, source, span_i, label, ci, c["n"],
                          *(round(v, 4) for v in c["bbox_min"]),
                          *(round(v, 4) for v in c["bbox_max"])))


def map_pair(pair_name, catpart_path, cell_mm, records_csv, spatial_csv):
    load_harness()
    started = time.monotonic()
    data = catpart_path.read_bytes()
    report = {"pair": pair_name, "catpart": str(catpart_path), "spans": []}
    rec_rows = []
    spat_rows = []

    for span_i, (container, span) in enumerate(PROBE.locate_spans(data)):
        lo, hi = span.body_lo, span.body_hi
        groups, kinds = pool.scan_pool_groups(data, lo, hi)
        span_rec = {"span": span_i, "container": container, "lo": lo, "hi": hi,
                    "composite": pool.has_composite_space(kinds)}
        if not span_rec["composite"]:
            span_rec["outcome"] = "not-composite-skipped"
            report["spans"].append(span_rec)
            continue
        # The final (registry-law) decode.
        try:
            points, triangles, _deg, info = decode_span(data, span, groups, kinds)
        except ExportError as exc:
            span_rec["outcome"] = "decode-error"
            span_rec["error_class"] = exc.error_class
            span_rec["detail"] = exc.detail[:300]
            report["spans"].append(span_rec)
            continue
        span_rec["points"] = len(points)
        span_rec["triangles"] = len(triangles)
        span_rec["stage"] = info.get("stage")
        span_rec["info"] = {
            k: v for k, v in info.items()
            if k in ("skipped_markers", "extended_header_declined",
                     "extended_members_filtered", "primary_loop_skips",
                     "primary_loop_kept", "curve_entries", "reps_unexported",
                     "rep_reasons", "facet_candidates", "facet_records")
            and v
        }

        # Unused pool vertices (written points no emitted triangle uses).
        used = bytearray(len(points))
        for tri in triangles:
            used[tri[0]] = used[tri[1]] = used[tri[2]] = 1
        unused_idx = [i for i, u in enumerate(used) if not u]
        span_rec["unused_pool_vertices"] = len(unused_idx)

        # The pre-emission decode + diff, ONLY when an emission law
        # actually skipped something (bounds the double-decode cost).
        dropped = []
        if info.get("primary_loop_skips") or info.get("primary_loop_kept"):
            try:
                pre_points, pre_triangles, _pd, _pi = decode_span(
                    data, span, groups, kinds, seam_area=None
                )
                dropped = diff_dropped(pre_points, pre_triangles, points, triangles)
            except ExportError as exc:
                span_rec["pre_decode_error"] = exc.error_class
        if dropped:
            span_rec["dropped_loop_triangles"] = len(dropped)
            span_rec["dropped_loop_area_mm2"] = round(sum(
                heron_area(a[0], a[1], a[2], b[0], b[1], b[2], c[0], c[1], c[2])
                for a, b, c in dropped
            ), 2)
            dropped_positions = []
            for a, b, c in dropped:
                dropped_positions.extend((a, b, c))
            add_spatial(spat_rows, pair_name, "seam-skipped-loop-verts", span_i,
                        "seam+relist+dedup drops", dropped_positions, cell_mm)

        # The per-rep structure (the decode's own node scan and windows).
        scanned = composite._scan_token_nodes(data, lo, hi)
        rep_nodes = composite._rep_node_positions(scanned, groups)
        pool_by_node = {}
        for group, node in zip(groups, rep_nodes):
            if node is not None and node not in pool_by_node:
                pool_by_node[node] = group
        scanned_positions = [npos for npos, _p, _c1, _c2 in scanned]

        # The registry decode pops info['_space_offsets'] and never
        # re-attaches it, so the rep bases are REBUILT by the decode's
        # own rules: exported = absorption (noise-aware) AND the M2b
        # refs gate; an exported rep contributes len(pts) to the
        # store-level point list, in group order.
        base = 0
        reps_exported = 0
        for k, (group, node) in enumerate(zip(groups, rep_nodes)):
            group_vertices = list(group.vertices) if group is not None else []
            # Unexported rep: the group's pool vertices are the declined
            # geometry (never entered the decode points).
            if node is None:
                add_spatial(spat_rows, pair_name, "unexported-rep-vertices",
                            span_i, f"rep {k}: no token node precedes pool group",
                            group_vertices, cell_mm)
                rec_rows.append((pair_name, span_i, container, k, "", "",
                                 "", f"rep-declined: no token node precedes pool group {k}",
                                 "", "", len(group_vertices), "group vertices"))
                continue
            group_ref = pool_by_node.get(node)
            npos_payload = next((p for npos, p, _c1, _c2 in scanned if npos == node), None)
            npos_c1 = next((c1 for npos, _p, c1, _c2 in scanned if npos == node), None)
            record, failure = composite._decode_rep_node(
                npos_payload, npos_c1,
                list(group_ref.vertices) if group_ref is not None else [],
            )
            if record is None:
                add_spatial(spat_rows, pair_name, "undecoded-node-vertices",
                            span_i, f"rep {k} node@{node}: {failure[:120]}",
                            group_vertices, cell_mm)
                rec_rows.append((pair_name, span_i, container, k, node, "",
                                 "", f"node-undecoded: {failure[:160]}",
                                 "", "", len(group_vertices), "group vertices"))
                continue
            territory_lo = node + 4 + record["region_end_rel"]
            nxt_candidates = [p for p in scanned_positions if p > node]
            territory_hi = min(nxt_candidates) if nxt_candidates else hi
            elem_decl = npos_c1
            elements = record["elements"]
            pts = record["pts"]

            # Per-rep gap framing over the decode's own window.
            hdrs = [m.start() for m in facets.STRIP_RE.finditer(data, territory_lo, territory_hi)]
            try:
                accepted, short_records, ext_records = PROBE.accepted_spans(
                    data, territory_lo, territory_hi, elem_decl, elements, hdrs
                )
                cands = PROBE.candidate_offsets(data, territory_lo, territory_hi)
                gaps = PROBE.gap_clusters(data, territory_lo, territory_hi, accepted, cands)
            except ExportError as exc:
                rec_rows.append((pair_name, span_i, container, k, node, territory_lo,
                                 territory_hi, f"framing-error: {exc.error_class}: {exc.detail[:120]}",
                                 "", "", "", ""))
                continue
            # The decode's own export decision, rebuilt: absorption
            # (noise-aware) AND the M2b refs gate.
            distinct = set(group_ref.vertices) if group_ref is not None else set()
            pts_set = set(pts)
            unmatched = [v for v in distinct if v not in pts_set]
            unmatched = [v for v in unmatched
                         if (best := composite._tol_match(v, pts)) is None
                         or best > composite.NOISE_REL]
            grefs = [r for _o, mk, _n, _c, refs, _w in short_records
                     if mk in composite.GATED for r in refs]
            grefs += [r for rec in ext_records for r in rec.refs]
            refs_ok = not grefs or max(grefs) < elem_decl
            exported = not unmatched and refs_ok
            if not exported:
                reason = (
                    f"rep-declined: pool group not re-listed ({len(unmatched)} of "
                    f"{len(distinct)} vertices)" if unmatched else
                    f"rep-declined: facet refs beyond the rep's element space "
                    f"(max ref {max(grefs)} >= {elem_decl})"
                )
                add_spatial(spat_rows, pair_name, "unexported-rep-vertices",
                            span_i, reason[:100], group_vertices, cell_mm)
                rec_rows.append((pair_name, span_i, container, k, node, "", "",
                                 reason, "", "", len(group_vertices), "group vertices"))
                span_rec.setdefault("reps", []).append({
                    "rep": k, "node": node, "territory": [territory_lo, territory_hi],
                    "exported": False, "reason": reason[:160],
                })
                continue
            # This rep's unused written vertices: store-level indices
            # [base, base + len(pts)) that no triangle used.
            elem_of_written = [i for i, (_v, pt) in enumerate(elements) if pt is not None]
            unused_elem = set()
            for j in range(base, base + len(pts)):
                if not used[j]:
                    wl = j - base
                    if wl < len(elem_of_written):
                        unused_elem.add(elem_of_written[wl])
            add_spatial(spat_rows, pair_name, "unused-pool-vertices", span_i,
                        f"rep {k}",
                        [points[base + j] for j in range(len(pts)) if not used[base + j]],
                        cell_mm)
            span_rec.setdefault("reps", []).append({
                "rep": k, "node": node, "territory": [territory_lo, territory_hi],
                "elem_decl": elem_decl, "elements": len(elements),
                "exported": True,
                "gaps": len(gaps),
                "unresolved_candidates": sum(len(os_) for _s, _e, os_, _p in gaps),
                "unused_elements": len(unused_elem),
            })
            for g_lo, g_hi, os_, _prev_end in gaps:
                before_max = -1
                after_min = None
                for o, mn, mx in _record_bounds(short_records, ext_records):
                    if o <= g_lo:
                        before_max = max(before_max, mx)
                    if o >= g_hi and after_min is None:
                        after_min = mn
                in_interval = sorted(
                    e for e in unused_elem
                    if before_max < e < (after_min if after_min is not None else math.inf)
                )
                for o in os_:
                    nxt = min((c for c in cands if c > o), default=g_hi)
                    rec_rows.append((
                        pair_name, span_i, container, k, node, o,
                        f"0x{data[o + 1]:02x}" if o + 1 < len(data) else "",
                        diagnose_candidate(data, o, nxt, hi, elem_decl),
                        before_max, after_min if after_min is not None else "",
                        len(in_interval), "yes" if in_interval else "",
                    ))
            base += len(pts)
            reps_exported += 1

        span_rec["reps_exported"] = reps_exported
        span_rec["base_check"] = base == len(points)

        report["spans"].append(span_rec)

    report["wall_seconds"] = round(time.monotonic() - started, 1)
    records_csv.parent.mkdir(parents=True, exist_ok=True)
    with records_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(("pair", "span", "container", "rep", "node", "rec_offset",
                    "marker", "diagnosis", "used_max_elem_before",
                    "used_min_elem_after", "unused_in_interval", "owns_unused"))
        w.writerows(rec_rows)
    spatial_csv.parent.mkdir(parents=True, exist_ok=True)
    with spatial_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(("pair", "source", "span", "label", "cluster", "n",
                    "bbox_min_x", "bbox_min_y", "bbox_min_z",
                    "bbox_max_x", "bbox_max_y", "bbox_max_z"))
        w.writerows(spat_rows)
    print(json.dumps(report, indent=2, default=str))
    return 0


def _record_bounds(short_records, ext_records):
    for o, _mk, _normal, _counts, refs, _w in short_records:
        yield o, min(refs, default=-1), max(refs, default=-1)
    for rec in ext_records:
        yield rec.offset, min(rec.refs, default=-1), max(rec.refs, default=-1)


def join_missing(pair_name, missing_csv, spat_csv_path, rec_csv_path, joined_csv):
    """Annotate the geometry-side net_missing clusters with the store
    evidence: unused pool vertices (per rep), seam-skip vertices and
    the gap records that own unused vertices — the deliverable's
    ``registros candidatos`` column."""
    with open(missing_csv, newline="", encoding="utf-8") as fh:
        missing = [r for r in csv.DictReader(fh) if r["signal"] == "net_missing"]
    with open(spat_csv_path, newline="", encoding="utf-8") as fh:
        spat = list(csv.DictReader(fh))
    with open(rec_csv_path, newline="", encoding="utf-8") as fh:
        recs = list(csv.DictReader(fh))

    def bbox(r):
        return (float(r["bbox_min_x"]), float(r["bbox_min_y"]), float(r["bbox_min_z"]),
                float(r["bbox_max_x"]), float(r["bbox_max_y"]), float(r["bbox_max_z"]))

    def inter(a, b):
        return all(a[i] <= b[i + 3] + 1e-6 and b[i] <= a[i + 3] + 1e-6 for i in range(3))

    owning = collections.defaultdict(list)  # rep -> [offset,...]
    for r in recs:
        if r["owns_unused"] == "yes" and r["rec_offset"]:
            owning[r["rep"]].append(r["rec_offset"])

    rows = []
    for m in missing:
        mb = bbox(m)
        by_rep = collections.defaultdict(int)
        for s in spat:
            if s["source"] == "unused-pool-vertices" and inter(mb, bbox(s)):
                by_rep[s["label"]] += int(s["n"])
        seam = sum(int(s["n"]) for s in spat
                   if s["source"] == "seam-skipped-loop-verts" and inter(mb, bbox(s)))
        cand = "; ".join(
            f"{lbl}: unused={n} gaps_owning={','.join(owning.get(lbl.split()[-1], [])[:6])}"
            for lbl, n in sorted(by_rep.items(), key=lambda kv: -kv[1])
        )
        rows.append((m["pair"], m["rank"], m["n_cells"], m["n_tris"], m["net_mm2"],
                     seam, sum(by_rep.values()), cand, *mb))
    with open(joined_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(("pair", "rank", "n_cells", "n_tris_missing", "net_mm2",
                    "seam_skip_verts_in_bbox", "unused_verts_in_bbox",
                    "registros_candidatos",
                    "bbox_min_x", "bbox_min_y", "bbox_min_z",
                    "bbox_max_x", "bbox_max_y", "bbox_max_z"))
        w.writerows(rows)
    print(f"join: {len(rows)} net_missing clusters annotated -> {joined_csv}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="w12_store_decline_map",
        description="W12 store decline map: per-rep gaps, unused pool vertices, seam-skipped loops per pair.",
    )
    ap.add_argument("--pair")
    ap.add_argument("--pairs-json", type=Path, default=None)
    ap.add_argument("--catpart", type=Path, default=None)
    ap.add_argument("--cell-mm", type=float, default=5.0, help="spatial cluster cell (mm)")
    ap.add_argument("--records-csv", type=Path, required=True)
    ap.add_argument("--spatial-csv", type=Path, required=True)
    ap.add_argument("--join-missing", type=Path, default=None,
                    help="the oracle's net_missing CSV; with --joined-csv, annotate it instead of mapping")
    ap.add_argument("--joined-csv", type=Path, default=None)
    args = ap.parse_args(argv)

    if args.join_missing is not None or args.joined_csv is not None:
        if args.join_missing is None or args.joined_csv is None:
            ap.error("--join-missing and --joined-csv go together")
        return join_missing(args.pair or "", args.join_missing, args.spatial_csv,
                            args.records_csv, args.joined_csv)
    if args.pair and args.pairs_json:
        pair = next(p for p in json.loads(args.pairs_json.read_text()) if p["name"] == args.pair)
        catpart_path = Path(pair["catpart"])
        pair_name = pair["name"]
    elif args.catpart:
        catpart_path = args.catpart
        pair_name = catpart_path.stem
    else:
        ap.error("need --pair + --pairs-json, or --catpart")
    return map_pair(pair_name, catpart_path, args.cell_mm, args.records_csv, args.spatial_csv)


if __name__ == "__main__":
    raise SystemExit(main())
