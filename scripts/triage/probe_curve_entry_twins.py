#!/usr/bin/env python3
"""Twin / validation probes for the U4 curve-entry analysis (stage 4a-residue).

Corpus-reading companion to analyze_curve_entries.py.  Two modes (read-only
over the corpus; ``python3 -I``; writes only under docs/evidence/data/):

  --validate  re-run decode_curve_entries.py AND ab_identity_export.py on the
              committed 78-file validation subset (mixed outcome classes; the
              list is the VALIDATION_SHA16 constant below) into scratch dirs
              and compare every row with the committed CSVs, byte for byte
              (CSV text of the row).  -> curve-entries-validation.csv
  --twins     the 026d6726007381a9 / e254a37e2ba6902c twin probe + the
              pin-independence probe over the validation stores whose
              skip-referencing loops fail the battery.  -> curve-entries-
              twin-probe.csv (long format: probe,subject,metric,value)

Twin probe contents (all under the decoder's own pins, decode_curve_entries
.pin_skips - no new pin rule):

  layout     element / written / skip counts, written-element coordinate
             alignment after the constant x offset, skip-index sets;
  slots      per skip slot: pin kind, loop-referenced?, edge-referenced?;
  edges      the 01 02 edge group (wrapper 10 24 04 ff ff 00 00 00): record
             sizes, per-record written/skip reference counts, the pinned
             geometry of each record (ring: z spread + radius spread about
             the midpoint of its end points; vertical: xy delta; profile:
             pinned z sequence);
  strips     per facet record: marker, normal-carrying?, skip refs, and the
             cross-twin match of its PINNED coordinate sequence (after the x
             offset) against the best same-shape record of the other twin;
  battery    skip-referencing normal loops re-tested under the dup pin (the
             decoder's) vs the next-written pin vs the mid-ring pin;
  failloops  for each skip-referencing normal loop that FAILS the battery
             on the named stores: are the loop's WRITTEN points already
             non-coplanar (a pin-independent failure), and does ANY
             alternative pin (next / prev-prev / per-slot choice among
             prev,next,prev-prev) restore coplanarity.

Run:
  python3 -I scripts/triage/probe_curve_entry_twins.py --validate
  python3 -I scripts/triage/probe_curve_entry_twins.py --twins
"""

import argparse
import csv
import itertools
import mmap
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "docs" / "evidence" / "data"
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
sys.path.insert(0, str(ROOT / "scripts" / "triage"))
sys.path.insert(0, str(ROOT / "src"))

import decode_curve_entries as D  # noqa: E402
from catpart.geometry import composite, facets, pool, store  # noqa: E402
from decode_big_form_points import (  # noqa: E402
    PLANE_TOL,
    decode_region,
    normal_loops,
    parse_strip_records,
)

TWINS = ("026d6726007381a9", "e254a37e2ba6902c")
# validation stores whose skip-referencing normal loops fail the battery
# (decoder CSV: loops_skipref_nonplanar > 0), all inside the validation set
FAIL_STORES = (
    "02ee154402795740", "02ff71f5b7a33d13", "0a64c44c29e6cfa6",
    "278015fe3d3d603d", "ffdbc4f7a2569ab8",
)
VALIDATION_SHA16 = """
0018baa84f3bff6b 00198dd9de8caadf 002e03ea032528d3 01bd888df54c2790
01d289f459924d13 026d6726007381a9 0280c202dbb94ed2 02ee154402795740
02ff71f5b7a33d13 0313b53db2bbd818 03478c827bfba430 05091b5d7fa8e755
059d871a5f0b85c4 05d3ebd19ddc8043 067086b8a8e28a22 07f621d6222361db
08f2eccbef48714a 09184fd7e95e2f09 0a64c44c29e6cfa6 0b62cc281bd9a55f
0cc9c994594fa80f 1b1ae7841ff84bf8 1f9685813701ed10 24c26a4cf81b8d45
278015fe3d3d603d 3fe33236959e891c 4f186e337383e22c 5728856e6fe04473
5a43f2f9e07e79b6 5abb042b3a19c899 5f8f00de9dd9a592 61765d51d3d73cb1
6a693e273e425620 77af3e0fd6ebab4d 78685667f05e9f43 7d27c73d693ef60c
7eb7ac18bec52f93 802a113eb42bce1e 827c5b7ab5cfe15c 839552c2e8239d23
86e6a5c36f09354d 909d3080c8b3d3c0 954140923a62863a 97a0a420923c5c67
97b7bc248e728bca a2a6fc2793465df9 a7ae6758c15daa4e a9a564cd2803bb72
a9d296d612910c25 ab3fe519db36d7c5 ae646da50dddd9af b55584b8d2ffcb34
b6713632931d2d58 c551643a192b6f7b c93c92f909260c94 dd7b2b4d7520ab88
e0ed4cddaba79cab e460139494d5c9aa e8dbf4605f8f6716 ec5026e5bb8ab425
ed2637160af57e26 ef30cb2f71dc2c73 f21255ac24b9f7d2 f365e18d0556aa22
f4d15246bacc93e7 f761ee7ee0bb802a f95e2dd32c28fb2b faa1ed869a80edbf
fac22ea3ee861d6d fd4201aa361d9c63 fd4ff542aaea8b8a fe6d27fdc91cf54a
fec863960e434b76 ff51cf21bc520af0 ff60483c070b8f5d ff716a8865e03765
ff842b8ab2869583 ffdbc4f7a2569ab8
""".split()
VALIDATION_FILE = DATA / "curve-entries-validation.csv"


def manifest_rows():
    return {r["sha256"][:16]: r for r in csv.DictReader(MANIFEST.open())
            if r["split"] in ("dev", "held-out") and r["kind"] == "part"}


def open_store(sha16):
    """(mm, lo, hi, elements, elem_decl, strips) of a composite store."""
    rel = manifest_rows()[sha16]
    fh = (ROOT / rel["local_path"]).open("rb")
    mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
    d8 = int.from_bytes(mm[8:12], "big")
    blocks = store.valid_blocks(mm)
    for blk, nm in blocks:
        if nm != "CATStdCont":
            continue
        span = store.locate_store(mm, blk, blocks, d8)
        lo, hi = span.body_lo, span.body_hi
        groups, kinds = pool.scan_pool_groups(mm, lo, hi)
        if not pool.has_composite_space(kinds):
            continue
        hdrs = [m.start() for m in facets.STRIP_RE.finditer(mm, lo, hi)]
        payload, c1, _c2 = composite.find_list_node(mm, lo, hdrs[0])
        elements, *_ = decode_region(payload, c1)
        strips, _ = parse_strip_records(mm, lo, hi, c1)
        return fh, mm, lo, hi, elements, c1, strips
    raise RuntimeError(f"no composite store in {sha16}")


def neighbours(el, i):
    n = len(el)
    j = i - 1
    while j >= 0 and el[j][1] is None:
        j -= 1
    k = i + 1
    while k < n and el[k][1] is None:
        k += 1
    j2 = j - 1
    while j2 >= 0 and el[j2][1] is None:
        j2 -= 1
    g = lambda x: el[x][1] if 0 <= x < n else None  # noqa: E731
    return {"prev": g(j), "next": g(k), "prev2": g(j2)}


def plane_ok(pts, normal):
    if any(p is None for p in pts):
        return None
    nn = sum(x * x for x in normal) ** 0.5
    return max(
        abs(sum((q[a] - pts[0][a]) * normal[a] for a in range(3))) / nn
        for q in pts[1:]
    ) <= PLANE_TOL


def mid_pins(el, rec):
    """Pin every skip slot with the MID law where eligible (else prev)."""
    circles = [c for c in (D.circle_of(r) for r in rec) if c]
    out = {}
    for i, (_v, p) in enumerate(el):
        if p is not None:
            continue
        nb = neighbours(el, i)
        prev, nxt = nb["prev"], nb["next"]
        c = prev
        if prev and nxt and prev[:2] == nxt[:2] and prev[2] < nxt[2]:
            best = None
            for cx, cy, cz, r in circles:
                if prev[2] <= cz <= nxt[2] and r != 0 and abs(
                    ((prev[0] - cx) ** 2 + (prev[1] - cy) ** 2) ** 0.5 - abs(r)
                ) <= D.R_TOL:
                    if best is None or abs(cz - (prev[2] + nxt[2]) / 2) < abs(
                        best[2] - (prev[2] + nxt[2]) / 2
                    ):
                        best = (cx, cy, cz, r)
            if best:
                c = (prev[0], prev[1], best[2])
        out[i] = c
    return out


def edge_groups(mm, lo, hi):
    groups = []
    for m in re.finditer(rb"\x10\x24\x04\xff\xff\x00\x00\x00", mm[lo:hi]):
        g = lo + m.start() + 8
        if mm[g:g + 2] != b"\x01\x02":
            continue
        cp = g + 2
        cnt = mm[cp]
        rp = cp + 1
        if cnt == 0xFF:
            cnt = struct.unpack_from("<I", mm, cp + 1)[0]
            rp = cp + 5
        p = rp
        recs = []
        for _ in range(cnt):
            n = mm[p + 1]
            recs.append(list(mm[p + 2:p + 2 + n]))
            p += 2 + n
        groups.append(recs)
    return groups


def r4(v):
    return round(v, 4)


def twin_probe(out):
    put = lambda probe, subject, metric, value: out.append(  # noqa: E731
        {"probe": probe, "subject": subject, "metric": metric, "value": value})
    data = {}
    for sha in TWINS:
        fh, mm, lo, hi, el, c1, strips = open_store(sha)
        rec = D.parse_curve_records(mm, lo, hi)
        skips = [i for i, (_v, p) in enumerate(el) if p is None]
        loop_refs = {r for _o, _mk, _n, _c, refs, _w in strips for r in refs}
        coords, kinds = D.pin_skips(el, rec, loop_refs)
        groups = edge_groups(mm, lo, hi)
        edge_refs = {r for g in groups for rr in g for r in rr}
        data[sha] = dict(el=el, strips=strips, rec=rec, skips=skips,
                         coords=coords, kinds=kinds, loop_refs=loop_refs,
                         edge_refs=edge_refs, groups=groups, c1=c1)
        put("layout", sha, "elem_decl", c1)
        put("layout", sha, "written", len(el) - len(skips))
        put("layout", sha, "skips", len(skips))
        put("layout", sha, "skip_indices", " ".join(map(str, skips)))
        put("layout", sha, "loop_referenced_skips",
            " ".join(str(i) for i in skips if i in loop_refs))
        put("layout", sha, "edge_referenced_skips",
            " ".join(str(i) for i in skips if i in edge_refs))
        put("layout", sha, "unreferenced_skips(mid/unpinned)",
            " ".join(str(i) for i in skips
                     if i not in loop_refs))
        put("layout", sha, "facet_records", len(strips))
        put("layout", sha, "curve_records", len(rec))
        for i in skips:
            put("slots", sha, f"slot{i}",
                f"{kinds[i]} loop={'y' if i in loop_refs else 'n'} "
                f"edge={'y' if i in edge_refs else 'n'} "
                f"pin=({r4(coords[i][0])},{r4(coords[i][1])},{r4(coords[i][2])})")
        # edge group
        for gi, g in enumerate(groups):
            put("edges", sha, f"group{gi}.records", len(g))
            put("edges", sha, f"group{gi}.sizes", " ".join(str(len(r)) for r in g))
            for ri, refs in enumerate(g):
                pts = [coords[r] if el[r][1] is None else el[r][1] for r in refs]
                nsk = sum(1 for r in refs if el[r][1] is None)
                shape = {9: "ring", 2: "vertical", 3: "profile"}.get(len(refs), "other")
                desc = f"n={len(refs)} skip_refs={nsk}"
                if shape == "ring":
                    cx = (pts[0][0] + pts[-1][0]) / 2
                    cy = (pts[0][1] + pts[-1][1]) / 2
                    rad = [((p[0] - cx) ** 2 + (p[1] - cy) ** 2) ** 0.5 for p in pts]
                    desc += (f" z_spread={max(p[2] for p in pts) - min(p[2] for p in pts):.6f}"
                             f" radius={sum(rad) / len(rad):.4f}"
                             f" radius_spread={max(rad) - min(rad):.6f}")
                elif shape == "vertical":
                    desc += (f" dxy=({pts[1][0] - pts[0][0]:.6f},"
                             f"{pts[1][1] - pts[0][1]:.6f})"
                             f" z=({r4(pts[0][2])},{r4(pts[1][2])})")
                else:
                    desc += " z=" + ",".join(str(r4(p[2])) for p in pts)
                put("edges", sha, f"group{gi}.rec{ri}.{shape}", desc)
    a, b = TWINS
    A, B = data[a], data[b]
    xa = min(p[0] for _v, p in A["el"] if p is not None)
    xb = min(p[0] for _v, p in B["el"] if p is not None)
    dx = round(xb - xa, 4)
    put("layout", "twins", "x_offset(e254a37e-026d6726)", dx)
    put("layout", "twins", "same_elem_decl", A["c1"] == B["c1"])
    sa, sb = set(A["skips"]), set(B["skips"])
    put("layout", "twins", "skip_sets_equal", sa == sb)
    put("layout", "twins", "skips_only_026d", " ".join(map(str, sorted(sa - sb))))
    put("layout", "twins", "skips_only_e254a37e", " ".join(map(str, sorted(sb - sa))))
    common_written = [i for i in range(min(len(A["el"]), len(B["el"])))
                      if A["el"][i][1] is not None and B["el"][i][1] is not None]
    eq = sum(1 for i in common_written
             if tuple(round(v, 3) for v in (A["el"][i][1][0], *A["el"][i][1][1:]))
             == tuple(round(v, 3) for v in (B["el"][i][1][0] - dx, *B["el"][i][1][1:])))
    put("layout", "twins", "index_aligned_written_equal_after_offset",
        f"{eq}/{len(common_written)}")
    # slots unreferenced on 026d (mid) vs referenced on e254a37e
    unref_a = [i for i in A["skips"] if i not in A["loop_refs"] and A["kinds"][i] == "mid"]
    put("slots", "twins", "026d_mid_slots", " ".join(map(str, unref_a)))
    put("slots", "twins", "026d_mid_slots_that_are_loop_referenced_dups_on_e254a37e",
        f"{sum(1 for i in unref_a if i in B['loop_refs'] and B['kinds'].get(i) == 'dup_prev')}/{len(unref_a)}")
    # strips
    seqs = {}
    for sha, d in ((a, A), (b, B)):
        rows = []
        for o, mk, n, c, refs, w in d["strips"]:
            pts = [tuple(round(v, 3) for v in (
                d["coords"][r] if d["el"][r][1] is None else d["el"][r][1]))
                for r in refs]
            nsk = sum(1 for r in refs if d["el"][r][1] is None)
            rows.append((mk, n, tuple(c), nsk, pts))
        seqs[sha] = rows
        for i, (mk, n, c, nsk, pts) in enumerate(rows):
            put("strips", sha, f"strip{i}",
                f"marker={hex(mk)} normal={'y' if n else 'n'} counts={list(c)} "
                f"skip_refs={nsk}/{len(pts)}")
    tot_pos = tot_eq = 0
    for i, (mk, n, c, nsk, pts) in enumerate(seqs[a]):
        best = None
        for j, (mk2, n2, c2, nsk2, pts2) in enumerate(seqs[b]):
            if (mk, c) != (mk2, c2):
                continue
            t = [(round(p[0] - dx, 3), p[1], p[2]) for p in pts2]
            eq = sum(1 for u, v in zip(pts, t) if u == v)
            if best is None or eq > best[0]:
                best = (eq, j, nsk2)
        put("strips", "twins", f"026d_strip{i}_best_match",
            f"e254a37e_strip{best[1]} seq_equal={best[0]}/{len(pts)} "
            f"skip_refs 026d={nsk} e254a37e={best[2]}")
        tot_pos += len(pts)
        tot_eq += best[0]
    put("strips", "twins", "pinned_sequence_positions_equal", f"{tot_eq}/{tot_pos}")
    put("strips", "twins", "skip_refs_in_strips_026d",
        sum(s[3] for s in seqs[a]))
    put("strips", "twins", "skip_refs_in_strips_e254a37e",
        sum(s[3] for s in seqs[b]))
    # battery under pin variants
    for sha, d in ((a, A), (b, B)):
        mid = mid_pins(d["el"], d["rec"])
        pins = {
            "dup(prev)": lambda i, d=d: neighbours(d["el"], i)["prev"],
            "next": lambda i, d=d: neighbours(d["el"], i)["next"],
            "mid-where-eligible": lambda i, mid=mid: mid[i],
        }
        sk = set(d["skips"])
        for name, fn in pins.items():
            tested = cop = 0
            slots = set()
            for _mk, normal, loop, _o, _j in normal_loops(d["strips"]):
                ss = [r for r in loop if r in sk]
                if not ss:
                    continue
                pts = [fn(r) if r in sk else d["el"][r][1] for r in loop]
                tested += 1
                slots.update(ss)
                cop += 1 if plane_ok(pts, normal) else 0
            put("battery", sha, f"pin={name}",
                f"skipref_normal_loops={tested} coplanar={cop} "
                f"slots={sorted(slots)}")
        put("battery", sha, "normal_loop_slot_z",
            " ".join(sorted({f"{s}:{r4(d['coords'][s][2])}" for _mk, _n, loop, _o, _j
                             in normal_loops(d["strips"]) for s in loop if s in sk},
                            key=lambda x: int(x.split(":")[0]))))
        put("battery", sha, "unreferenced_slots_tested_by_battery", 0)


def fail_probe(out):
    put = lambda probe, subject, metric, value: out.append(  # noqa: E731
        {"probe": probe, "subject": subject, "metric": metric, "value": value})
    grand = dict(failing=0, written_noncop=0, written_cop=0,
                 written_untestable=0, any_alt=0, beyond=0)
    for sha in FAIL_STORES:
        fh, mm, lo, hi, el, c1, strips = open_store(sha)
        sk = {i for i, (_v, p) in enumerate(el) if p is None}
        cnt = dict(failing=0, written_noncop=0, written_cop=0,
                   written_untestable=0, any_alt=0, beyond=0)
        for _mk, normal, loop, _o, _j in normal_loops(strips):
            ss = [r for r in loop if r in sk]
            if not ss:
                continue
            if any(r >= len(el) for r in loop):
                cnt["beyond"] += 1
                continue
            nbs = {r: neighbours(el, r) for r in set(ss)}
            pts = [nbs[r]["prev"] if r in sk else el[r][1] for r in loop]
            if plane_ok(pts, normal) is not False:
                continue
            cnt["failing"] += 1
            wr = [el[r][1] for r in loop if r not in sk]
            ok = plane_ok(wr, normal) if len(wr) > 1 else None
            if ok is False:
                cnt["written_noncop"] += 1
            elif ok:
                cnt["written_cop"] += 1
            else:
                cnt["written_untestable"] += 1
            alt = False
            uniq = sorted(set(ss))
            if len(uniq) <= 6:
                for combo in itertools.product(("prev", "next", "prev2"),
                                               repeat=len(uniq)):
                    m = dict(zip(uniq, combo))
                    p2 = [nbs[r][m[r]] if r in sk else el[r][1] for r in loop]
                    if plane_ok(p2, normal):
                        alt = True
                        break
            cnt["any_alt"] += 1 if alt else 0
        for k, v in cnt.items():
            put("failloops", sha, k, v)
            grand[k] += v
        mm.close()
        fh.close()
    for k, v in grand.items():
        put("failloops", "total", k, v)


def classify(cur, exp):
    c, e = cur, exp
    if c["audit_error"]:
        return "audit-error"
    if not c["node_form"]:
        return "noncomposite:" + (e["error_class"] or "exported")
    ce = int(e["loops_curve_entry"] or 0) > 0
    if e["export_ok"] == "1":
        return (f"exported-{c['node_form']}-{e['l2_status']}"
                f"{'-' + e['failed_check'] if e['failed_check'] else ''}-"
                f"{'ce-loops' if ce else 'no-ce-loops'}")
    return f"fail-closed-{c['node_form']}-{e['error_class']}-walk{c['walk_end_ok']}"


def validate():
    committed_cur = {r["sha256"][:16]: r for r in csv.DictReader(
        (DATA / "curve-entries-files.csv").open())}
    committed_exp = {r["sha256"][:16]: r for r in csv.DictReader(
        (DATA / "identity-export-files.csv").open())}
    ids = ",".join(sorted(committed_cur_ids()))
    rows = []
    with tempfile.TemporaryDirectory(prefix="catpart-curve-val-") as tmp:
        t1, t2 = Path(tmp) / "cur", Path(tmp) / "exp"
        for script, out in (("decode_curve_entries.py", t1),
                            ("ab_identity_export.py", t2)):
            subprocess.run(
                [sys.executable, "-I", str(ROOT / "scripts" / "triage" / script),
                 "--include-sha16", ids, "--out-dir", str(out)],
                check=True, stdout=subprocess.DEVNULL)
        new_cur = {r["sha256"][:16]: r for r in csv.DictReader(
            (t1 / "curve-entries-files.csv").open())}
        new_exp = {r["sha256"][:16]: r for r in csv.DictReader(
            (t2 / "identity-export-files.csv").open())}
    for k in sorted(new_cur):
        drift = [f for f in new_exp[k] if new_exp[k][f] != committed_exp[k][f]]
        rows.append({
            "sha16": k,
            "split": committed_cur[k]["split"],
            "class": classify(committed_cur[k], committed_exp[k]),
            "curve_row_identical": new_cur[k] == committed_cur[k],
            "export_row_identical": not drift,
            "export_drift_fields": " ".join(drift),
            "committed_export_error_class": committed_exp[k]["error_class"],
            "rerun_export_ok": new_exp[k]["export_ok"],
            "rerun_error_class": new_exp[k]["error_class"],
        })
    with VALIDATION_FILE.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    n = len(rows)
    print(f"validated {n} files: curve rows identical "
          f"{sum(r['curve_row_identical'] for r in rows)}/{n}; export rows "
          f"identical {sum(r['export_row_identical'] for r in rows)}/{n}")


def committed_cur_ids():
    return [x[:16] for x in VALIDATION_SHA16]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--twins", action="store_true")
    args = ap.parse_args()
    if args.validate:
        validate()
    if args.twins:
        out = []
        twin_probe(out)
        fail_probe(out)
        path = DATA / "curve-entries-twin-probe.csv"
        with path.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["probe", "subject", "metric", "value"])
            w.writeheader()
            w.writerows(out)
        print(f"wrote {path} ({len(out)} rows)")
        for r in out:
            if r["probe"] in ("layout", "strips", "battery", "failloops") and r[
                    "subject"] in ("twins", "total") or r["probe"] == "battery":
                print(r["probe"], r["subject"], r["metric"], r["value"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
