#!/usr/bin/env python3
"""The remaining composite over-uses and degenerate parts, audited (#34).

The primary-emit seam (2026-11-18) leaves six stores not-manifold because
their over-use is real surface (a larger loop is kept), and two stores
fail the degenerate gate with a manifold mesh. This probe attributes
every over-used edge and every skipped degenerate triangle to the
writer's own records/loops, rules out the decode-artifact hypotheses
(width rank, count split, ref mapping), and measures the two levers that
would change the row: the minimum triangle-level trim (surface lost) and
the edge-sheet split (area/triangle-preserving, vertices duplicated).

Read-only over the corpus; no src/ change. Every triangle list is
replayed with provenance through the shipped helpers and asserted equal
to the shipped export before any number is printed.

  .venv/bin/python -I scripts/triage/overuse_audit.py
  [--corpus-root PATH]   # a checkout that carries corpus/ (default: this repo)
  [--csv PATH]           # write the per-edge rows (docs/evidence/data/...)

Outputs the tables of docs/evidence/2026-11-19-overuse-audit.md.
"""

from __future__ import annotations

import argparse
import csv
import math
import mmap
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from catpart.geometry import composite, export as export_mod, mesh, pool  # noqa: E402

OVER_STORES = (
    "26504a08b641ad7a",
    "341bd488e61d6061",
    "5689954c867a0f70",
    "5a982112b4f5edc1",
    "cd88ae9d4d51a439",
    "e8d9a35806f5fcf7",
)
DEG_STORES = ("13bb5c0c49616ade", "b912cbef805c541b")

EDGE_FIELDS = [
    "sha16", "path", "split", "stage", "edge", "degree", "faces",
    "writer_loops", "writer_records", "kinds", "distinct_coord_triples",
    "normal_dot_min", "normal_dot_max", "incident_area_mm2",
]


# --- the shipped emission walk, with provenance -------------------------
def loop_triangles_prov(mk, idxs, points):
    """_loop_triangles with the strip index of every emitted/skipped tri."""
    lp = [points[i] for i in idxs]
    tris, deg = [], []
    if mk == 0x4C:
        for t in range(1, len(lp) - 1):
            tri = (idxs[0], idxs[t], idxs[t + 1])
            a, b, c = lp[0], lp[t], lp[t + 1]
            if a == b or b == c or a == c:
                deg.append((tri, t - 1, "0x4c-repeated-coord"))
                continue
            tris.append((tri, t - 1))
    else:
        for t in range(len(lp) - 2):
            tri = (idxs[t], idxs[t + 1], idxs[t + 2])
            if t % 2 == 1:
                tri = (tri[2], tri[1], tri[0])
            a, b, c = lp[t], lp[t + 1], lp[t + 2]
            if a == b or b == c or a == c:
                deg.append((tri, t, "strip-repeated-coord"))
                continue
            if composite._cross_zero(a, b, c):
                deg.append((tri, t, "strip-zero-cross"))
                continue
            tris.append((tri, t))
    return tris, deg


class Replay:
    """One emission unit (a whole single-rep store, or one rep)."""

    def __init__(self, elements, records, extended, seam_area, unit, base=0):
        self.elements = elements
        self.records = records
        self.extended = extended
        self.seam_area = seam_area
        self.unit = unit
        self.base = base
        self.out = []       # (store-level tri, prov)
        self.pin_out = []   # welded loops: merged after every rep
        self.deg = []       # (tri, prov, window idx, reason)
        self.trace = []     # seam decisions on refused loops
        self.stats = Counter()

    def run(self):
        elements, records, extended = self.elements, self.records, self.extended
        written_rank, skips = {}, set()
        for i, (_v, pt) in enumerate(elements):
            if pt is None:
                skips.add(i)
            else:
                written_rank[i] = len(written_rank)
        points = [pt for _v, pt in elements if pt is not None]
        edge_uses = {}
        dropped = []

        def emit(kind, normal, off, li, loop, source):
            if not loop:
                return
            if any(r in skips for r in loop):
                self.stats["curve_entry"] += 1
                dropped.append((kind, normal, off, li, loop, source))
                return
            self.stats["loops"] += 1
            idxs = [written_rank[r] for r in loop]
            tris, deg = loop_triangles_prov(kind, idxs, points)
            for tri, t, why in deg:
                self.deg.append((tri, (self.unit, off, kind, li, source), t, why))
            area = sum(composite._triangle_area(t, points) for t, _x in tris)
            cand = [t for t, _x in tris]
            prov0 = (self.unit, off, kind, li, source)
            ratio = round(area / self.seam_area * 100, 4) if self.seam_area else 0.0
            if not composite._mesh_safe(edge_uses, cand):
                if self.seam_area is not None and area <= composite.PRIMARY_LOOP_AREA_REL * self.seam_area:
                    self.stats["seam_skip"] += 1
                    self.trace.append(("SKIP", off, li, kind, len(idxs), round(area, 3), ratio))
                    return
                self.stats["seam_kept"] += 1
                self.trace.append(("KEEP", off, li, kind, len(idxs), round(area, 3), ratio))
                composite._fold_edge_uses(edge_uses, composite._edge_uses(cand))
            for t, ti in tris:
                self.out.append(((t[0] + self.base, t[1] + self.base, t[2] + self.base),
                                 prov0 + (ti, len(idxs), "emit")))

        for off, mk, normal, counts, refs, _w in records:
            if mk not in composite.EXPORTED_SHORT_MARKERS:
                continue
            o = 0
            for li, c in enumerate(counts):
                emit(mk, normal, off, li, refs[o:o + c], "primary")
                o += c

        for rec in extended:
            rec_triangles, rec_prov, rec_deg, rec_dropped = [], [], [], []
            for j in range(0, 3 * rec.triangles, 3):
                loop = rec.refs[j:j + 3]
                if any(r in skips for r in loop):
                    rec_dropped.append((0x42, rec.normal, j // 3, loop))
                    continue
                idxs = [written_rank[r] for r in loop]
                tris, deg = loop_triangles_prov(0x42, idxs, points)
                for tri, t in tris:
                    rec_triangles.append(tri)
                    rec_prov.append((self.unit, rec.offset, "ext-soup", j // 3, "extended"))
                for tri, t, why in deg:
                    rec_deg.append((tri, (self.unit, rec.offset, "ext-soup", j // 3, "extended"), t, why))
            o = 3 * rec.triangles
            for index, c in enumerate(rec.counts):
                loop = rec.refs[o:o + c]
                o += c
                if not loop:
                    continue
                kind = 0x42 if index < rec.strips else 0x4C
                if any(r in skips for r in loop):
                    rec_dropped.append((kind, rec.normal, index, loop))
                    continue
                idxs = [written_rank[r] for r in loop]
                tris, deg = loop_triangles_prov(kind, idxs, points)
                for tri, t in tris:
                    rec_triangles.append(tri)
                    rec_prov.append((self.unit, rec.offset, kind, index, "extended"))
                for tri, t, why in deg:
                    rec_deg.append((tri, (self.unit, rec.offset, kind, index, "extended"), t, why))
            if not rec_deg and composite._mesh_safe(edge_uses, rec_triangles):
                for tri, prov in zip(rec_triangles, rec_prov):
                    self.out.append(((tri[0] + self.base, tri[1] + self.base, tri[2] + self.base),
                                     prov + (0, 0, "emit")))
                self.stats["ext_tris"] += len(rec_triangles)
                self.stats["ext_records"] += 1
                for kind, normal, li, loop in rec_dropped:
                    dropped.append((kind, normal, rec.offset, li, loop, "extended"))
            else:
                self.stats["ext_declined"] += 1
                for tri, prov, t, why in rec_deg:
                    self.deg.append((tri, prov, t, why))

        for kind, normal, off, li, loop, source in dropped:
            pin = composite._dup_pin_map(elements, loop)
            if pin is None:
                self.stats["pin_refused"] += 1
                continue
            resolved = [pin.get(r, r) for r in loop]
            if normal is not None:
                status, _d = composite._loop_plane_status(resolved, normal, elements)
                if status != "coplanar":
                    self.stats["pin_refused"] += 1
                    continue
            idxs = [written_rank[r] for r in resolved]
            tris, deg = loop_triangles_prov(kind, idxs, points)
            if deg or not composite._mesh_safe(edge_uses, [t for t, _x in tris]):
                self.stats["pin_refused"] += 1
                continue
            for t, ti in tris:
                self.pin_out.append(((t[0] + self.base, t[1] + self.base, t[2] + self.base),
                                     (self.unit, off, kind, li, "dup-pin", ti, len(idxs), "emit")))
            self.stats["pin_loops"] += 1
        self.points = points
        return self


# --- path reconstruction (the shipped ladder, read-only) ----------------
def _composite_span(mm, summary):
    d8_outer = int.from_bytes(mm[8:12], "big")
    blocks = export_mod.store.valid_blocks(mm)
    for blk in [b for b, nm in blocks if nm == "CATStdCont"]:
        try:
            span = export_mod.store.locate_store(mm, blk, blocks, d8_outer)
        except export_mod.ExportError:
            continue
        if span is None:
            continue
        groups, kinds = pool.scan_pool_groups(mm, span.body_lo, span.body_hi)
        if pool.has_composite_space(kinds):
            return span, groups, kinds
    return None, None, None


def _decoded_units(mm, lo, hi, groups, stage):
    """[(base, elements, records, extended)] in emission order."""
    units = []
    if stage == "identity-table-walk":
        hdrs = [m.start() for m in composite.STRIP_RE.finditer(mm, lo, hi)]
        node_hi = hdrs[0] if hdrs else hi
        ln = composite.find_list_node(mm, lo, node_hi)
        if ln is None:
            return None
        payload, elem_decl, _ = ln
        elements, _info = composite.decode_region(payload, elem_decl)
        records, _n = composite.parse_strip_records(mm, lo, hi, elem_decl, elements=elements)
        extended, _c = composite.parse_extended_facet_records(mm, lo, hi, elem_decl)
        return [(0, elements, records, extended)]

    if stage in ("identity-per-rep", "identity-mixedwrite-reps"):
        scanned = composite._scan_token_nodes(mm, lo, hi)
        rep_nodes = composite._rep_node_positions(scanned, groups)
        pool_by_node = {}
        for k, node in enumerate(rep_nodes):
            if node is not None and node not in pool_by_node:
                pool_by_node[node] = k
        decoded = {}
        for npos, payload, c1, _c2 in scanned:
            group_k = pool_by_node.get(npos)
            node_poolv = list(groups[group_k].vertices) if group_k is not None else []
            if stage == "identity-per-rep":
                record, _failure = composite._decode_rep_node(payload, c1, node_poolv)
            else:
                counts_end = composite._token_counts_end(payload)
                if counts_end is None:
                    continue
                _law, elements, pts, region_end_rel, wc, _failure = composite._decode_node_mixedwrite(
                    payload, c1, counts_end, node_poolv
                )
                record = None if _law is None else {
                    "elements": elements, "pts": pts,
                    "region_end_rel": region_end_rel, "write_count": wc,
                }
            if record is None:
                continue
            record.update({"pos": npos, "payload": payload, "elem": c1,
                           "region_end": npos + 4 + record["region_end_rel"]})
            decoded[npos] = record
        scanned_positions = [npos for npos, _p, _c1, _c2 in scanned]
        base = 0
        for k, (group, node) in enumerate(zip(groups, rep_nodes)):
            if node is None:
                continue
            d = decoded.get(node)
            if d is None:
                continue
            if stage == "identity-per-rep":
                distinct = set(group.vertices)
                pts_set = set(d["pts"])
                unmatched = [v for v in distinct if v not in pts_set]
                if unmatched:
                    unmatched = [v for v in unmatched
                                 if (best := composite._tol_match(v, d["pts"])) is None
                                 or best > composite.NOISE_REL]
                if unmatched:
                    continue
            nxt_candidates = [p for p in scanned_positions if p > d["pos"]]
            nxt = min(nxt_candidates) if nxt_candidates else hi
            records, _n = composite.parse_strip_records(
                mm, d["region_end"], nxt, d["elem"], elements=d["elements"]
            )
            ext_k, _c = composite.parse_extended_facet_records(mm, d["region_end"], nxt, d["elem"])
            grefs = [r for _o, mk, _n2, _c2, refs, _w in records
                     if mk in composite.GATED for r in refs]
            grefs += [r for rec in ext_k for r in rec.refs]
            if grefs and max(grefs) >= d["elem"]:
                continue
            units.append((base, d["elements"], records, ext_k))
            base += len(d["pts"])
        return units
    return None


def replay_store(mm, summary):
    """(points, triangles, [(tri, prov)], [deg events], unit_count)."""
    span, groups, _kinds = _composite_span(mm, summary)
    if span is None:
        return None
    lo, hi = span.body_lo, span.body_hi
    stage = summary["composite"]["stage"]
    # the registry pass: seam off, the store mesh area
    pts0, tri0, _d0, _i0 = composite.decode_composite_store(
        mm, span, groups, _kinds, _seam_area=None
    )
    area = composite._mesh_area(tri0, pts0)
    units = _decoded_units(mm, lo, hi, groups, stage)
    if not units:
        return None

    def run(seam_area):
        outs, degs, traces, stats = [], [], [], Counter()
        for unit, (base, elements, records, extended) in enumerate(units):
            r = Replay(elements, records, extended, seam_area, unit, base).run()
            outs.append(r)
            degs += r.deg
            traces += r.trace
            stats.update(r.stats)
        out = []
        for r in outs:
            out += r.out
        for r in outs:
            out += r.pin_out
        return out, degs, traces, stats

    out, degs, traces, stats = run(area)
    got = [t for t, _p in out]
    guarded_traces = traces
    if stats["seam_skip"] and not mesh.mesh_stats(list(got)).manifold:
        # the entry fire gate: the pre-seam emission stands unchanged
        out, degs, _pre_traces, _pre_stats = run(None)
        got = [t for t, _p in out]
    return got, out, degs, guarded_traces, stage, len(units)


def audit_store(corpus_root, manifest, sha16):
    rel = manifest[sha16]
    path = corpus_root / rel["local_path"]
    with path.open("rb") as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as mm:
        summary, verts, tris = export_mod._export_data(mm)
        shipped = [tuple(t) for t in tris]
        replayed = replay_store(mm, summary)
        if replayed is None:
            raise SystemExit(f"{sha16}: no composite replay")
        got, out, degs, traces, stage, units = replayed
    if got != shipped:
        raise SystemExit(f"{sha16}: provenance replay MISMATCH vs the shipped export")
    return rel, summary, verts, shipped, out, degs, traces, stage, units


def _norm(t, pts):
    a, b, c = pts[t[0]], pts[t[1]], pts[t[2]]
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    cx = u[1] * v[2] - u[2] * v[1]
    cy = u[2] * v[0] - u[0] * v[2]
    cz = u[0] * v[1] - u[1] * v[0]
    n = math.sqrt(cx * cx + cy * cy + cz * cz)
    return (cx / n, cy / n, cz / n) if n else (0.0, 0.0, 0.0)


def edge_rows(rel, summary, verts, tris, out, stage):
    prov = [p for _t, p in out]
    uses = Counter()
    for i, t in enumerate(tris):
        for e in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            uses[tuple(sorted(e))] += 1
    rows = []
    for e, degree in sorted(uses.items(), key=lambda kv: (-kv[1], kv[0])):
        if degree <= 2:
            continue
        faces = [i for i, t in enumerate(tris) if e[0] in t and e[1] in t]
        loops = {(prov[i][0], prov[i][1], prov[i][3], prov[i][4]) for i in faces}
        recs = {(prov[i][0], prov[i][1]) for i in faces}
        kinds = sorted({f"0x{prov[i][2]:02x}" for i in faces})
        keys = {tuple(sorted((verts[x] for x in tris[i]))) for i in faces}
        ns = [_norm(tris[i], verts) for i in faces]
        dots = [sum(a * b for a, b in zip(ns[i], ns[j]))
                for i in range(len(ns)) for j in range(i + 1, len(ns))]
        rows.append({
            "sha16": rel["sha256"][:16],
            "path": rel["path"],
            "split": rel["split"],
            "stage": stage,
            "edge": f"({e[0]},{e[1]})",
            "degree": degree,
            "faces": len(faces),
            "writer_loops": len(loops),
            "writer_records": len(recs),
            "kinds": "/".join(kinds),
            "distinct_coord_triples": len(keys),
            "normal_dot_min": round(min(dots), 4),
            "normal_dot_max": round(max(dots), 4),
            "incident_area_mm2": round(
                sum(composite._triangle_area(tris[i], verts) for i in faces), 3),
        })
    return rows


def trim_cost(tris, verts):
    """Greedy smallest-triangle drop until every edge is used <= 2."""
    alive = set(range(len(tris)))
    while True:
        uses = Counter()
        for i in alive:
            t = tris[i]
            for e in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                uses[tuple(sorted(e))] += 1
        over = {e for e, d in uses.items() if d > 2}
        if not over:
            break
        cand = {}
        for i in alive:
            t = tris[i]
            if any(tuple(sorted(e)) in over for e in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0]))):
                cand[i] = composite._triangle_area(t, verts)
        victim = min(cand, key=lambda i: (cand[i], i))
        alive.remove(victim)
    return alive


def split_repair(tris, verts):
    """Duplicate the over-used edge's endpoints per sheet (area-preserving)."""
    T = [list(t) for t in tris]
    pts = list(verts)
    for _ in range(200):
        uses = Counter()
        for t in T:
            for e in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                uses[tuple(sorted(e))] += 1
        over = [e for e, d in uses.items() if d > 2]
        if not over:
            break
        e = min(over)
        inc = [i for i, t in enumerate(T) if e[0] in t and e[1] in t]
        for g in range(2, len(inc)):
            if g % 2 == 0:
                a = len(pts)
                pts.append(pts[e[0]])
                b = len(pts)
                pts.append(pts[e[1]])
                T[inc[g]] = [a if x == e[0] else b if x == e[1] else x for x in T[inc[g]]]
            else:
                prev = inc[g - 1]
                new = [x for x in T[prev] if x >= len(verts)]
                a, b = new[0], new[1]
                T[inc[g]] = [a if x == e[0] else b if x == e[1] else x for x in T[inc[g]]]
    return [tuple(t) for t in T], pts


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus-root", default=str(ROOT))
    ap.add_argument("--csv", default=None)
    args = ap.parse_args()
    corpus_root = Path(args.corpus_root)
    manifest = {r["sha256"][:16]: r for r in
                csv.DictReader((ROOT / "manifests" / "corpus-manifest.csv").open())}

    rows = []
    print("== over-used edges (store-level written-rank indices)")
    for sha16 in OVER_STORES:
        rel, summary, verts, tris, out, degs, traces, stage, units = audit_store(
            corpus_root, manifest, sha16)
        total = composite._mesh_area(tris, verts)
        erows = edge_rows(rel, summary, verts, tris, out, stage)
        rows += erows
        alive = trim_cost(tris, verts)
        lost = total - composite._mesh_area([tris[i] for i in sorted(alive)], verts)
        split_tris, split_pts = split_repair(tris, verts)
        dup_groups = {}
        for i, t in enumerate(tris):
            dup_groups.setdefault(tuple(sorted((verts[x] for x in t))), []).append(i)
        extra = sum(len(v) - 1 for v in dup_groups.values() if len(v) > 1)
        print(f"\n{sha16} {rel['path']} [{rel['split']}] stage={stage} units={units}")
        print(f"  tris={len(tris)} area={total:.3f} deg_skipped={summary.get('degenerate_triangle_count')} "
              f"coord_dup_extra={extra}")
        print(f"  seam: kept={summary['composite'].get('primary_loop_kept')} "
              f"skips={summary['composite'].get('primary_loop_skips')} "
              f"declined={summary['composite'].get('primary_loop_seam_declined')} "
              f"dedup_dropped={summary['composite'].get('unordered_dedup_dropped')} "
              f"dedup_declined={summary['composite'].get('unordered_dedup_declined')}")
        for r in erows:
            print(f"  edge {r['edge']} deg={r['degree']} faces={r['faces']} "
                  f"writer_loops={r['writer_loops']} writer_records={r['writer_records']} "
                  f"kinds={r['kinds']} distinct_coord_triples={r['distinct_coord_triples']} "
                  f"normal_dot={r['normal_dot_min']}..{r['normal_dot_max']} "
                  f"incident_area={r['incident_area_mm2']}")
        for row in traces:
            print(f"  seam {row[0]} loop rec@0x{row[1]:x} loop={row[2]} mk=0x{row[3]:02x} "
                  f"len={row[4]} area={row[5]} ({row[6]}% of store)")
        print(f"  trim: drop {len(tris)-len(alive)} tris, area lost {lost:.3f} "
              f"({lost/total*100:.4f}%)")
        print(f"  split: manifold={mesh.mesh_stats(split_tris).manifold} "
              f"tris={len(split_tris)} area_delta="
              f"{composite._mesh_area(split_tris, split_pts)-total:.2e} "
              f"new_vertices={len(split_pts)-len(verts)}")

    print("\n== degenerate-triangle stores (skipped at emission, mesh manifold)")
    for sha16 in DEG_STORES:
        rel, summary, verts, tris, out, degs, traces, stage, units = audit_store(
            corpus_root, manifest, sha16)
        primary = [d for d in degs if d[3] in ("strip-zero-cross", "strip-repeated-coord")]
        print(f"\n{sha16} {rel['path']} [{rel['split']}] stage={stage}")
        print(f"  tris={len(tris)} manifold={mesh.mesh_stats(tris).manifold} "
              f"shipped_deg={summary.get('degenerate_triangle_count')} "
              f"primary_deg={len(primary)}")
        loops = Counter((p[0], p[1], p[3], p[4], why) for _t, p, _ti, why in primary)
        for k, n in sorted(loops.items()):
            print(f"  deg source unit={k[0]} rec@0x{k[1]:x} loop={k[2]} src={k[3]} "
                  f"reason={k[4]} n={n}")
        for tri, p, ti, why in primary[:3]:
            print(f"    {why} tri={tri} pts="
                  f"{[tuple(round(x, 4) for x in verts[x]) for x in tri]}")

    if args.csv:
        out_path = Path(args.csv)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=EDGE_FIELDS)
            w.writeheader()
            w.writerows(rows)
        print(f"\nwrote {out_path} ({len(rows)} edge rows)")


if __name__ == "__main__":
    sys.exit(main())
