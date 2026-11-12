#!/usr/bin/env python3
"""The per-rep decomposition law measured on the unabsorbed-pool family
(G6 stage 4b, #34).

Stage 3d's single-node reading leaves 148 walk-exact composite stores
(92 big + 56 small at the decode level; 92 + 55 at the export seam)
fail-closed at the pool-absorption gate: the node list does not re-list
every `01 06` pool vertex, so the identity mapping (refs = 0-based
element indices in region order) leaves the pool's element slots
unexplained.  This script measures the law that explains them:

- **The store body is a sequence of reps.**  Rep k = (the k-th `01 06`
  pool wrapper, the k-th walk-exact token-bearing list node, the strip
  records between that node's region end and the next token node).
  The stage-3d reader searched for list nodes only BEFORE the first
  strip record (`node_hi = hdrs[0]`), so on multi-rep stores it saw
  rep 0's node — often a small stub — while the pool concatenated
  every rep's wrapper: absorption failed on the other reps' vertices
  and refs "beyond the element space" were other reps' references.
- **Pool absorption holds per rep** (the k-th pool re-lists verbatim —
  exact f32 — in the k-th decoded node's region).  A residual noise
  variant: single-rep stores where a few pool vertices differ from
  their re-listing by double-rounding noise (measured; tolerance
  NOISE_REL in the code, justified by the measured gap between the
  noise deltas and real coordinate differences).
- **References are per rep** (M2b identity per rep): each rep's gated
  strip records resolve in-bounds against their OWN rep's element
  count; N2 (elem_decl == max_ref + 1) is re-measured per rep.
- **The loop plane battery holds per rep** (coplanarity against the
  stored normal, stage-3b criterion, PLANE_TOL).

Outputs (docs/evidence/data/):
- unabsorbed-pool-files.csv   one row per composite store
- unabsorbed-pool-reps.csv    one row per decoded rep

Deterministic: sorted manifest order, integers/floats rounded, no
wall-clock values.  Read-only over the corpus (corpus symlinked); run
with the worktree venv:

  .venv/bin/python -I scripts/triage/unabsorbed_pool_law.py
  [--include-sha16 HEX16,...]
"""

import argparse
import csv
import mmap
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"

sys.path.insert(0, str(ROOT / "scripts" / "triage"))
sys.path.insert(0, str(ROOT / "src"))

from catpart.geometry import composite, facets, pool, store  # noqa: E402
from decode_big_form_points import (  # noqa: E402
    classify_loop_planes,
    decode_region,
    loop_plane_status,
    normal_loops,
    parse_strip_records,
    plane_battery,
)
from decode_nested_store import release_of  # noqa: E402

GATED = (0x42, 0x49, 0x4A, 0x4C)

# Noise-aware absorption tolerance: a pool vertex "re-listed with
# noise" matches a written point within NOISE_REL (relative, per
# coordinate, scale max(1, |coord|)).  The measured corpus gap justifies
# the value: noise deltas reach ~1e-11 relative, the smallest
# genuinely-different coordinate pair measured is far above it (see the
# note's noise section and max_noise_delta / min_real_gap columns).
NOISE_REL = 1e-5

FILES_FIELDS = [
    "sha256", "split", "release", "size_bytes", "store_body",
    "pool_groups", "pool_vertices", "token_nodes", "decoded_reps",
    "stage3d_absorbed", "stage3d_class", "per_rep_verbatim",
    "per_rep_tol", "pools_shifted", "pools_unpaired", "noise_vertices",
    "max_noise_delta", "refs_oob_reps", "refs_n2_reps",
    "loops", "loops_coplanar", "loops_skipref", "loops_beyond",
    "loops_nonplanar", "nonplanar_multi", "nonplanar_single_agree",
    "nonplanar_single_mid", "nonplanar_single_disagree",
    "nonplanar_fourplus", "nonplanar_no_tri",
    "max_plane_residual", "stage3d_node_bytes", "min_unpaired_gap",
    "residual_class", "audit_error",
]

REPS_FIELDS = [
    "sha256", "rep", "node_pos", "pool_group", "pool_vertices",
    "elem_decl", "node_points", "skip_slots", "absorbed_verbatim",
    "absorbed_tol", "noise_deltas", "records", "max_ref_gated_w2",
    "refs_oob", "elem_eq_maxref1", "loops", "loops_coplanar",
    "loops_skipref", "loops_beyond", "loops_nonplanar",
    "max_plane_residual",
]


def tol_match(v, pts):
    """Noise-aware re-listing test: some written point matches v within
    NOISE_REL per coordinate.  Returns (matched, max_rel_delta)."""
    scale = max(1.0, abs(v[0]), abs(v[1]), abs(v[2]))
    best = None
    for p in pts:
        d = max(
            abs(p[0] - v[0]) / scale,
            abs(p[1] - v[1]) / scale,
            abs(p[2] - v[2]) / scale,
        )
        if best is None or d < best:
            best = d
    return (best is not None and best <= NOISE_REL), best


def scan_token_nodes(mm, lo, hi):
    """Every token-bearing list node in [lo, hi): (pos, payload, c1, c2)."""
    nodes = []
    pos = lo
    while True:
        pos = mm.find(composite.NODE_MAGIC, pos, hi)
        if pos < 0:
            break
        end = mm.find(composite.NODE_MAGIC, pos + 4, hi)
        if end < 0:
            end = hi
        payload = bytes(mm[pos + 4 : end])
        tok = payload.find(composite.LIST_TOKEN)
        if 0 <= tok <= 64:
            p = tok + 5
            try:
                c1, p = composite.read_count(payload, p)
                c2, p = composite.read_count(payload, p)
            except Exception:  # noqa: BLE001 - unreadable counts: not a node
                pos += 1
                continue
            if 0 < c1 <= composite.MAX_ELEMENT_COUNT:
                nodes.append((pos, payload, c1, c2))
        pos += 1
    return nodes


def audit_part(mm, rel):
    """One part: the per-rep census.  Returns (files_row, reps_rows)."""
    frow = {k: "" for k in FILES_FIELDS}
    frow["sha256"] = rel["sha256"]
    frow["split"] = rel["split"]
    frow["release"] = release_of(rel["detected_version"])
    frow["size_bytes"] = mm.size()
    reps_rows = []
    d8_outer = int.from_bytes(mm[8:12], "big") if mm.size() >= 12 else 0
    blocks = store.valid_blocks(mm)
    for blk in [b for b, nm in blocks if nm == "CATStdCont"]:
        try:
            span = store.locate_store(mm, blk, blocks, d8_outer)
        except Exception:  # noqa: BLE001 - recorded per part
            continue
        if span is None:
            continue
        lo, hi = span.body_lo, span.body_hi
        frow["store_body"] = f"{lo}-{hi}"
        try:
            groups, kinds = pool.scan_pool_groups(mm, lo, hi)
        except Exception as exc:  # noqa: BLE001 - recorded per part
            frow["audit_error"] = f"pool: {type(exc).__name__}"
            return frow, reps_rows
        if not pool.has_composite_space(kinds):
            continue
        pool_groups = [list(g.vertices) for g in groups]
        frow["pool_groups"] = len(pool_groups)
        frow["pool_vertices"] = sum(len(g) for g in pool_groups)
        nodes = scan_token_nodes(mm, lo, hi)
        frow["token_nodes"] = len(nodes)
        # decode every token node; walk-exact ones are the rep regions
        decoded = []
        for npos, payload, c1, c2 in nodes:
            try:
                elements, rs, we, nok, info = decode_region(payload, c1)
            except ValueError:
                continue
            if we != rs + 4 * info["write_count"] or not nok:
                continue
            decoded.append(
                {
                    "pos": npos,
                    "elem": c1,
                    "elements": elements,
                    "pts": [pt for _v, pt in elements if pt is not None],
                    "region_end": npos + 4 + info["region_start"]
                    + 4 * info["write_count"],
                    "payload_len": len(payload),
                }
            )
        frow["decoded_reps"] = len(decoded)
        # the stage-3d single-node reading (control column): the largest
        # payload among token nodes BEFORE the first strip record
        hdrs = [m.start() for m in facets.STRIP_RE.finditer(mm, lo, hi)]
        node_hi = hdrs[0] if hdrs else hi
        ln = composite.find_list_node(mm, lo, node_hi)
        if ln is None:
            frow["stage3d_class"] = "no-list-node"
            return frow, reps_rows
        payload0, elem0, _c2 = ln
        try:
            elements0, rs0, we0, nok0, info0 = decode_region(payload0, elem0)
        except ValueError:
            frow["stage3d_class"] = "layout"
            return frow, reps_rows
        if we0 != rs0 + 4 * info0["write_count"] or not nok0:
            frow["stage3d_class"] = "walk-exact"
            return frow, reps_rows
        pts0 = [pt for _v, pt in elements0 if pt is not None]
        frow["stage3d_node_bytes"] = len(payload0)
        poolv_all = [v for g in pool_groups for v in g]
        stage3d_missing = len(set(poolv_all) - set(pts0))
        frow["stage3d_absorbed"] = 0 if stage3d_missing else 1
        frow["stage3d_class"] = "absorbed" if not stage3d_missing else "unabsorbed"
        # per-rep pairing: pool group k <-> decoded rep k (diagonal);
        # content cross-check names shifted/unpaired pools.  Verbatim
        # membership first (set-based); the noise tolerance only runs on
        # a rep's verbatim misses (the big pools make the O(|pool| x
        # |pts|) scan the census's hotspot otherwise).
        def rep_tol_hits(gv, pts):
            distinct = set(gv)
            ps = set(pts)
            tol_hits = 0
            for v in distinct:
                if v in ps:
                    continue
                m, _ = tol_match(v, pts)
                tol_hits += m
            return tol_hits

        diag = []
        for gi, gv in enumerate(pool_groups):
            distinct = set(gv)
            if gi < len(decoded):
                ps = set(decoded[gi]["pts"])
                hits = sum(1 for v in distinct if v in ps)
                tol_hits = (
                    hits + rep_tol_hits(gv, decoded[gi]["pts"])
                    if hits < len(distinct)
                    else hits
                )
                diag.append((gi, hits, tol_hits, len(distinct)))
            else:
                diag.append((gi, 0, 0, len(distinct)))
        verbatim_all = all(h == n for _g, h, _t, n in diag)
        tol_all = all(t == n for _g, _h, t, n in diag)
        frow["per_rep_verbatim"] = int(verbatim_all)
        frow["per_rep_tol"] = int(tol_all)
        # shifted/unpaired/noise decomposition: a pool failing its
        # diagonal verbatim is either noise-resolved on the diagonal rep
        # (tol), verbatim-absorbed in ANOTHER decoded rep (shifted), or
        # genuinely unpaired (the named residue).
        shifted = unpaired = 0
        noise_vertices = 0
        max_noise = 0.0
        min_gap = None
        for gi, gv in enumerate(pool_groups):
            distinct = set(gv)
            gi_hits, gi_tol = diag[gi][1], diag[gi][2]
            if gi_hits == len(distinct):
                continue
            if gi_tol == len(distinct) and gi < len(decoded):
                ps = set(decoded[gi]["pts"])
                for v in distinct:
                    if v in ps:
                        continue
                    m, dlt = tol_match(v, decoded[gi]["pts"])
                    if m:
                        noise_vertices += 1
                        if dlt is not None and dlt > max_noise:
                            max_noise = dlt
                continue
            found_elsewhere = False
            for k, d in enumerate(decoded):
                if k == gi:
                    continue
                ps = set(d["pts"])
                if sum(1 for v in distinct if v in ps) == len(distinct):
                    found_elsewhere = True
                    break
            if found_elsewhere:
                shifted += 1
            else:
                unpaired += 1
                if gi < len(decoded):
                    for v in distinct:
                        _m, dlt = tol_match(v, decoded[gi]["pts"])
                        if dlt is not None and (min_gap is None or dlt < min_gap):
                            min_gap = dlt
        frow["pools_shifted"] = shifted
        frow["pools_unpaired"] = unpaired
        frow["noise_vertices"] = noise_vertices
        frow["max_noise_delta"] = round(max_noise, 12) if max_noise else 0.0
        frow["min_unpaired_gap"] = round(min_gap, 6) if min_gap else ""
        # records per rep territory [region_end_k, node_{k+1}.pos)
        # records per rep territory [region_end_k, node_{k+1}.pos), each
        # territory parsed with ITS rep's element count (the oob rank of
        # the committed width rule needs the rep's own bound — a
        # whole-body parse at a dummy bound would rank differently).
        per_rep = [[] for _ in decoded]
        for k, d in enumerate(decoded):
            nxt = decoded[k + 1]["pos"] if k + 1 < len(decoded) else hi
            recs_k, _nh = parse_strip_records(mm, d["region_end"], nxt, d["elem"])
            per_rep[k] = recs_k
        # per-rep absorption, refs, battery
        oob_reps = n2_reps = 0
        tot = dict(loops=0, cop=0, skp=0, bey=0, non=0)
        npl = dict(multi=0, single_agree=0, single_mid=0, single_disagree=0, fourplus=0, no_tri=0)
        max_res = 0.0
        for k, d in enumerate(decoded):
            pts = d["pts"]
            skips = {i for i, (v, pt) in enumerate(d["elements"]) if pt is None}
            gv = pool_groups[k] if k < len(pool_groups) else []
            distinct = set(gv)
            ps = set(pts)
            v_hits = sum(1 for v in distinct if v in ps)
            tol_hits = (
                v_hits + rep_tol_hits(gv, pts)
                if v_hits < len(distinct)
                else v_hits
            )
            my = per_rep[k]
            grefs = [
                r
                for _o, mk, _n, _c, refs, w in my
                if mk in GATED and w == 2
                for r in refs
            ]
            mx = max(grefs) if grefs else None
            oob = sum(1 for r in grefs if r >= d["elem"])
            if oob:
                oob_reps += 1
            if mx is not None and mx == d["elem"] - 1:
                n2_reps += 1
            nr, loops, cop, skp, bey, non, max_r = plane_battery(
                my, d["elements"], d["elem"]
            )
            if max_r > max_res:
                max_res = max_r
            tot["loops"] += loops
            tot["cop"] += cop
            tot["skp"] += skp
            tot["bey"] += bey
            tot["non"] += non
            # the committed multi-plane criterion (stage-3b review F3)
            # over this rep's nonplanar loops
            for mk_l, normal_l, loop_l, _o, _j in normal_loops(my):
                st, _r = loop_plane_status(
                    loop_l, normal_l, d["elements"], skips, d["elem"]
                )
                if st != "nonplanar":
                    continue
                _nt, dd, pcls, cos1000 = classify_loop_planes(
                    loop_l, mk_l, d["elements"], normal_l
                )
                if pcls == "multi-plane":
                    npl["multi"] += 1
                elif pcls == "single-plane-uniform":
                    if cos1000 >= 999:
                        npl["single_agree"] += 1
                    elif cos1000 < 500:
                        npl["single_disagree"] += 1
                    else:
                        npl["single_mid"] += 1
                elif pcls == "4-plus-plane":
                    npl["fourplus"] += 1
                else:
                    npl["no_tri"] += 1
            reps_rows.append(
                {
                    "sha256": rel["sha256"],
                    "rep": k,
                    "node_pos": d["pos"],
                    "pool_group": k if k < len(pool_groups) else "",
                    "pool_vertices": len(distinct) if gv else 0,
                    "elem_decl": d["elem"],
                    "node_points": len(pts),
                    "skip_slots": len(skips),
                    "absorbed_verbatim": v_hits,
                    "absorbed_tol": tol_hits,
                    "noise_deltas": "",
                    "records": len(my),
                    "max_ref_gated_w2": mx if mx is not None else "",
                    "refs_oob": oob,
                    "elem_eq_maxref1": int(mx == d["elem"] - 1)
                    if mx is not None
                    else "",
                    "loops": loops,
                    "loops_coplanar": cop,
                    "loops_skipref": skp,
                    "loops_beyond": bey,
                    "loops_nonplanar": non,
                    "max_plane_residual": round(max_r, 6) if max_r else 0.0,
                }
            )
        frow["refs_oob_reps"] = oob_reps
        frow["refs_n2_reps"] = n2_reps
        frow["loops"] = tot["loops"]
        frow["loops_coplanar"] = tot["cop"]
        frow["loops_skipref"] = tot["skp"]
        frow["loops_beyond"] = tot["bey"]
        frow["loops_nonplanar"] = tot["non"]
        frow["nonplanar_multi"] = npl["multi"]
        frow["nonplanar_single_agree"] = npl["single_agree"]
        frow["nonplanar_single_mid"] = npl["single_mid"]
        frow["nonplanar_single_disagree"] = npl["single_disagree"]
        frow["nonplanar_fourplus"] = npl["fourplus"]
        frow["nonplanar_no_tri"] = npl["no_tri"]
        frow["max_plane_residual"] = round(max_res, 6) if max_res else 0.0
        # residual class after the per-rep law
        if tol_all and not shifted and not unpaired:
            frow["residual_class"] = "per-rep-absorbed"
        elif tol_all and (shifted or unpaired):
            frow["residual_class"] = f"shifted-{shifted}-unpaired-{unpaired}"
        else:
            frow["residual_class"] = (
                f"unabsorbed-residue (shifted {shifted}, unpaired {unpaired})"
            )
        return frow, reps_rows
    return frow, reps_rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--include-sha16", default="")
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    args = ap.parse_args()
    rows_in = [
        r
        for r in csv.DictReader(MANIFEST.open())
        if r["split"] in ("dev", "held-out") and r["kind"] == "part"
    ]
    if args.include_sha16:
        want = {h for h in args.include_sha16.split(",") if h}
        rows_in = [r for r in rows_in if r["sha256"][:16] in want]
    rows_in.sort(key=lambda r: r["sha256"])
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    files_rows = []
    reps_rows = []
    for rel in rows_in:
        path = ROOT / rel["local_path"]
        with path.open("rb") as fh:
            mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                frow, rrows = audit_part(mm, rel)
            except Exception as exc:  # noqa: BLE001 - recorded per part
                frow = {k: "" for k in FILES_FIELDS}
                frow["sha256"] = rel["sha256"]
                frow["split"] = rel["split"]
                frow["audit_error"] = f"{type(exc).__name__}: {exc}"
                rrows = []
            finally:
                mm.close()
        files_rows.append(frow)
        reps_rows += rrows
    fpath = out_dir / "unabsorbed-pool-files.csv"
    with fpath.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FILES_FIELDS)
        w.writeheader()
        w.writerows(files_rows)
    rpath = out_dir / "unabsorbed-pool-reps.csv"
    with rpath.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=REPS_FIELDS)
        w.writeheader()
        w.writerows(reps_rows)
    print(f"wrote {fpath} ({len(files_rows)} rows)")
    print(f"wrote {rpath} ({len(reps_rows)} rep rows)")
    summarize(files_rows)


def summarize(files_rows):
    """The rates the note cites."""
    comp = [r for r in files_rows if r["stage3d_class"] in ("absorbed", "unabsorbed")]
    un = [r for r in comp if r["stage3d_class"] == "unabsorbed"]
    print(f"== per-rep census: {len(comp)} composite stores "
          f"(stage-3d absorbed {len(comp) - len(un)}, unabsorbed {len(un)})")
    if not un:
        return
    n = len(un)
    from collections import Counter

    forms = Counter(
        "big" if int(r["size_bytes"] or 0) else ""
        for r in un
    )
    print(f"   unabsorbed family: {n} stores")
    print(f"   pool groups per store: {Counter(r['pool_groups'] for r in un)}")
    print(f"   decoded reps per store: {Counter(r['decoded_reps'] for r in un)}")
    prv = sum(1 for r in un if r["per_rep_verbatim"] == 1)
    prt = sum(1 for r in un if r["per_rep_tol"] == 1)
    print(f"   per-rep absorption verbatim: {prv}/{n}; with noise tolerance: {prt}/{n}")
    print(f"   residual classes: "
          f"{Counter(r['residual_class'] for r in un)}")
    shifted = sum(int(r["pools_shifted"] or 0) for r in un)
    unpaired = sum(int(r["pools_unpaired"] or 0) for r in un)
    noise = sum(int(r["noise_vertices"] or 0) for r in un)
    mx = max((float(r["max_noise_delta"] or 0) for r in un), default=0.0)
    print(f"   pools shifted {shifted}, unpaired {unpaired}; "
          f"noise vertices {noise} (max rel delta {mx:.3g})")
    # the falsifiable test: per-rep refs in-bounds + battery
    oob = sum(int(r["refs_oob_reps"] or 0) for r in un)
    print(f"   reps with out-of-bounds gated refs: {oob}")
    L = sum(int(r["loops"] or 0) for r in un)
    C = sum(int(r["loops_coplanar"] or 0) for r in un)
    S = sum(int(r["loops_skipref"] or 0) for r in un)
    B = sum(int(r["loops_beyond"] or 0) for r in un)
    N = sum(int(r["loops_nonplanar"] or 0) for r in un)
    print(f"   battery over the family: {L} normal-carrying loops = "
          f"coplanar {C} + skipref {S} + beyond {B} + nonplanar {N}")
    M = sum(int(r["nonplanar_multi"] or 0) for r in un)
    SA = sum(int(r["nonplanar_single_agree"] or 0) for r in un)
    SM = sum(int(r["nonplanar_single_mid"] or 0) for r in un)
    SD = sum(int(r["nonplanar_single_disagree"] or 0) for r in un)
    F = sum(int(r["nonplanar_fourplus"] or 0) for r in un)
    NT = sum(int(r["nonplanar_no_tri"] or 0) for r in un)
    print(f"   nonplanar decomposition (committed criterion): multi-plane "
          f"{M}, single-plane-uniform {SA + SM + SD} (stored normal agrees "
          f"{SA} / mid {SM} / disagrees {SD}), 4-plus-plane {F}, "
          f"no-triangles {NT}")
    # absorbed control group under the per-rep law
    ab = [r for r in comp if r["stage3d_class"] == "absorbed"]
    multi = sum(1 for r in ab if int(r["pool_groups"] or 0) > 1)
    prv_ab = sum(1 for r in ab if r["per_rep_verbatim"] == 1)
    print(f"   control (stage-3d absorbed) {len(ab)} stores: multi-pool {multi}, "
          f"per-rep verbatim {prv_ab}")


if __name__ == "__main__":
    sys.exit(main())
