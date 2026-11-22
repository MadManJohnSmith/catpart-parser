#!/usr/bin/env python3
"""Measure the U4 skip-slot coordinate law on CATPart files (A4, W16).

For every part file given on the command line (the bench-external
targets are not in the corpus manifest), drives the SHIPPED decode
(``build_export`` with ``composite._triangulate`` patched to expose
each per-rep element space and facet records) and measures, with the
law module ``catpart.geometry.curves``:

- the skip-slot population and the unpinnable rate (the U4-D dup law
  needs a preceding written element; measured 0 unpinnable on the
  targets),
- every skip-referencing loop (sub-loops per counts, plus the
  extended records' independent triangles) classified by the dup-pin
  battery: coplanar / nonplanar / normal-less,
- the degenerate-emission class: dup-pinned loops carrying collapsed
  triangles, with the real triangles and area the G3 F7
  skip-degenerate convention would recover (the A4 lever; the weld
  itself lives in composite.py and is not changed here),
- the shipped summary counters (``loops_curve_entry``,
  ``loops_curve_entry_exported``, ``curve_entries``) for the row's
  before/after framing.

Outputs docs/evidence/data/u4-skip-law-files.csv (one row per part)
and a claims CSV (docs/evidence/data/u4-skip-law-claims.csv) in the
stage4b claims schema, plus a stdout summary.  Deterministic: the
parts are processed in argument order, no wall-clock value enters the
CSVs.  Read-only over the parts (the PLY lands in --out-dir, default
a temp dir; keep it out of the repo).  Run with the worktree venv:

  .venv/bin/python -I scripts/triage/measure_u4_skip_law.py \
      [--out-dir DIR] <part1.CATPart> [part2.CATPart ...]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from catpart.geometry import composite, curves  # noqa: E402
from catpart.geometry.export import build_export  # noqa: E402

FIELDS = [
    "part", "reps_unique", "skips", "unpinnable",
    "skipref_loops", "battery_coplanar", "battery_nonplanar", "normalless",
    "degenerate_emission_loops", "split_real_tris", "split_real_area_mm2",
    "all_degenerate_loops",
    "curve_entries", "loops_curve_entry", "loops_curve_entry_exported",
]

CLAIM_FIELDS = [
    "claim", "construct", "statement", "scope", "observations",
    "passes", "rate", "label", "note",
]


def _new_stats():
    return {
        "reps_unique": 0, "skips": 0, "unpinnable": 0,
        "skipref_loops": 0, "battery_coplanar": 0, "battery_nonplanar": 0,
        "normalless": 0,
        "degenerate_emission_loops": 0, "split_real_tris": 0,
        "split_real_area": 0.0, "all_degenerate_loops": 0,
    }


def _analyze_rep(elements, records, extended, t):
    els = [tuple(e) for e in elements]
    key = (len(els), sum(1 for _v, p in els if p is None), str(els[:2]))
    seen = t.setdefault("_seen", set())
    if key in seen:
        return
    seen.add(key)
    t["reps_unique"] += 1
    pins, _ = curves.pin_skips(els)
    t["skips"] += sum(1 for _v, p in els if p is None)
    t["unpinnable"] += len(curves.unpinned_skips(els, pins))
    skips = {i for i, (_v, p) in enumerate(els) if p is None}
    for rec in records + list(extended):
        if isinstance(rec, tuple):
            _o, mk, normal, counts, refs, _w = rec
            ty = 0
        else:
            mk = rec.marker
            normal = rec.normal
            counts = rec.counts
            refs = rec.refs
            ty = getattr(rec, "triangles", 0)
        # extended records: the ty independent triangles are weld
        # candidates too (one triangle, not a loop — classified the
        # same way the weld's battery sees them)
        for base in range(0, 3 * ty, 3):
            tri = refs[base : base + 3]
            _classify_loop(tri, mk, normal, els, pins, skips, t)
        off = 3 * ty
        for c in counts:
            loop = refs[off : off + c]
            off += c
            _classify_loop(loop, mk, normal, els, pins, skips, t)


def _classify_loop(loop, mk, normal, els, pins, skips, t):
    if not loop or not any(x in skips for x in loop):
        return
    if any(x >= len(els) for x in loop):
        return
    pts = curves.loop_pinned_points(loop, els, pins)
    if pts is None:
        return
    t["skipref_loops"] += 1
    if not curves.loop_is_battery_supported(normal, pts):
        t["battery_nonplanar"] += 1
        return
    if normal is None:
        t["normalless"] += 1
    else:
        t["battery_coplanar"] += 1
    real, degen = curves.split_loop_triangles(mk, loop, pts)
    if degen:
        t["degenerate_emission_loops"] += 1
        t["split_real_tris"] += len(real)
        t["split_real_area"] += sum(a for _tr, a in real)
        if not real:
            t["all_degenerate_loops"] += 1


def measure_part(path: Path, out_dir: Path):
    t = _new_stats()
    orig = composite._triangulate

    def tri(elements, records, extended=(), seam_area=None, relist_skip=False):
        _analyze_rep(elements, records, extended, t)
        return orig(
            elements, records, extended=extended,
            seam_area=seam_area, relist_skip=relist_skip,
        )

    composite._triangulate = tri
    try:
        ply_path = out_dir / (path.stem + ".ply")
        result = build_export(path, ply_path)
    finally:
        composite._triangulate = orig
    t.pop("_seen", None)
    comp = (result or {}).get("composite", {}) if isinstance(result, dict) else {}
    row = {k: "" for k in FIELDS}
    row["part"] = path.name
    for k, v in t.items():
        if k == "split_real_area":
            k = "split_real_area_mm2"
        row[k] = round(v, 1) if isinstance(v, float) else v
    row["curve_entries"] = comp.get("curve_entries", "")
    row["loops_curve_entry"] = comp.get("loops_curve_entry", "")
    row["loops_curve_entry_exported"] = comp.get("loops_curve_entry_exported", "")
    return row


def claims_rows(rows):
    """Per-claim rates, stage4b claims schema (fact / inference labels)."""
    out = []
    n_parts = len(rows)
    if not n_parts:
        return out
    tot_skips = sum(r["skips"] for r in rows)
    tot_unpin = sum(r["unpinnable"] for r in rows)
    tot_loops = sum(r["skipref_loops"] for r in rows)
    tot_nonplanar = sum(r["battery_nonplanar"] for r in rows)
    tot_deg_loops = sum(r["degenerate_emission_loops"] for r in rows)
    tot_tris = sum(r["split_real_tris"] for r in rows)
    tot_area = sum(r["split_real_area_mm2"] for r in rows)
    names = ", ".join(r["part"] for r in rows)
    out.append({
        "claim": "U4_dup_law_total",
        "construct": "composite/U4",
        "statement": "every skip slot pins to its immediately preceding "
                     "written element (U4-D dup law); the unpinnable class "
                     "is empty",
        "scope": names,
        "observations": tot_skips,
        "passes": tot_skips - tot_unpin,
        "rate": round((tot_skips - tot_unpin) / tot_skips, 6) if tot_skips else "",
        "label": "fact",
        "note": "per-part rows in u4-skip-law-files.csv",
    })
    out.append({
        "claim": "U4_dup_battery_on_targets",
        "construct": "composite/U4",
        "statement": "skip-referencing loops are coplanar under the dup "
                     "pin against their record's stored normal (the "
                     "coordinate law is confirmed on the targets)",
        "scope": names,
        "observations": tot_loops,
        "passes": tot_loops - tot_nonplanar,
        "rate": round((tot_loops - tot_nonplanar) / tot_loops, 6) if tot_loops else "",
        "label": "fact",
        "note": "normal-less loops accepted untested (the weld's battery "
                "rule); the nonplanar class is the coordinate-law residual",
    })
    out.append({
        "claim": "U4_degenerate_split_recoverable",
        "construct": "composite/U4",
        "statement": "dup-pinned loops carrying collapsed triangles yield "
                     "real surface under the G3 F7 skip-degenerate "
                     "convention (the A4 lever; needs the composite.py "
                     "weld to adopt the split)",
        "scope": names,
        "observations": tot_deg_loops,
        "passes": tot_tris,
        "rate": "",
        "label": "fact",
        "note": f"{tot_tris} real triangles, {round(tot_area, 1)} mm2 total; "
                "mesh-guard refusals (edge over-use) and declined "
                "extended-header records are separate, non-coordinate "
                "classes",
    })
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("parts", nargs="+", type=Path)
    ap.add_argument(
        "--out-dir", type=Path, default=None,
        help="where the PLYs go (default: a temp dir; keep out of the repo)",
    )
    args = ap.parse_args()
    out_dir = args.out_dir or Path(tempfile.mkdtemp(prefix="u4-skip-law-"))
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for path in args.parts:
        if not path.exists():
            print(f"SKIP (not found): {path}")
            continue
        row = measure_part(path, out_dir)
        rows.append(row)
        print(json.dumps(row, default=str))

    data_dir = ROOT / "docs" / "evidence" / "data"
    files_csv = data_dir / "u4-skip-law-files.csv"
    claims_csv = data_dir / "u4-skip-law-claims.csv"
    with open(files_csv, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    with open(claims_csv, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CLAIM_FIELDS)
        w.writeheader()
        w.writerows(claims_rows(rows))
    print(f"wrote {files_csv}")
    print(f"wrote {claims_csv}")


if __name__ == "__main__":
    main()
