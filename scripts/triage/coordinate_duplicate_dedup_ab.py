#!/usr/bin/env python3
"""A/B of the coordinate-identity duplicate-triangle dedup (2026-11-18, #34).

The stage-15 dedup law (``composite._apply_unordered_dedup``) used to key
a duplicate on the UNORDERED INDEX triple. That spelling only proves the
same-rep case: the per-rep decomposition keeps each rep's element space
disjoint, so a rep that re-lists an earlier rep's facet writes DIFFERENT
indices for it and the index pass cannot see the copy at all (545707b9:
67 index duplicates inside one rep plus 451 coordinate duplicates
re-listed by a later rep — the index pass declined, 212 over-edges
stayed). The shipped law keys on the three vertex COORDINATES instead
(the same facet = the same three points, whichever index space wrote
it), which is also what makes the drop area-preserving by construction:
a triangle's area is a pure function of its three vertex positions.

This harness measures the shipped law against the committed pre-change
law on every dev/held-out part of the manifest:

- **before pass** — ``_apply_unordered_dedup`` is replaced with the
  pre-change implementation (index triple key, first occurrence in list
  order wins), copied verbatim below;
- **after pass** — the shipped law (coordinate key, the earliest
  emission unit's copy wins; a rep's welded loops carry that rep's point
  base).

Both passes score the same L2 gate (``fitness.runner._score_export`` —
the single gate authority, no fork) and measure two areas from the
exported mesh's own vertices/triangles:

- ``area_mm2`` — the listed triangle-soup area (what a duplicate
  double-counts);
- ``uniq_area_mm2`` — the area with each coordinate-identical triple
  counted ONCE (the geometric surface). This is the fidelity measure the
  law must not change: a dropped copy is the same three points as the
  kept one, so the unique surface is invariant.

The before pass is anchored to the committed fitness report
(``fitness/reports/20261118T232016Z-64b2a1.json``, main @ de6fd39): every
part's L2 status / failed check / triangle count must match its l2
record, else the run is invalid (no silent baseline drift).

Outputs (deterministic, sorted manifest order; no wall-clock value):

  docs/evidence/data/coord-duplicate-dedup-ab.csv  one row per part

Read-only over the corpus:

  .venv/bin/python -I scripts/triage/coordinate_duplicate_dedup_ab.py
  [--include-sha16 HEX16,...]
"""

import argparse
import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"
BASELINE_REPORT = ROOT / "fitness" / "reports" / "20261118T232016Z-64b2a1.json"

sys.path.insert(0, str(ROOT / "src"))

from catpart.fitness.runner import _score_export  # noqa: E402
from catpart.geometry import ExportError  # noqa: E402
from catpart.geometry import composite  # noqa: E402
from catpart.geometry import export as export_mod  # noqa: E402
from catpart.geometry import mesh  # noqa: E402

AB_FIELDS = [
    "sha256", "split", "stage",
    "before_export_ok", "after_export_ok",
    "before_l2_status", "after_l2_status",
    "before_failed_check", "after_failed_check",
    "before_triangle_count", "after_triangle_count",
    "before_manifold", "after_manifold",
    "before_area_mm2", "after_area_mm2",
    "area_delta_mm2", "area_rel",
    "before_uniq_area_mm2", "after_uniq_area_mm2", "uniq_area_rel",
    "before_dedup_dropped", "before_dedup_declined",
    "after_dedup_dropped", "after_dedup_declined",
]


def triangle_area(vertices, tri):
    pa, pb, pc = vertices[tri[0]], vertices[tri[1]], vertices[tri[2]]
    ux, uy, uz = pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]
    vx, vy, vz = pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2]
    cx = uy * vz - uz * vy
    cy = uz * vx - ux * vz
    cz = ux * vy - uy * vx
    return 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)


def areas(vertices, triangles):
    """``(listed area, unique-facet area)`` in mm².

    The second counts each coordinate-identical unordered triple once —
    the geometric surface independent of how many times the writer (or a
    sibling rep) re-listed it."""
    listed = 0.0
    unique = 0.0
    seen = set()
    for tri in triangles:
        area = triangle_area(vertices, tri)
        listed += area
        key = tuple(sorted(tuple(vertices[i]) for i in tri))
        if key not in seen:
            seen.add(key)
            unique += area
    return listed, unique


def before_dedup(triangles, info, points=None, space_offsets=()):
    """The committed pre-change dedup (main @ de6fd39), verbatim.

    Index-triple key, first occurrence in list order wins; the fire gate
    and the degenerate guard are the shipped ones."""
    if len(triangles) < 2 or mesh.mesh_stats(list(triangles)).manifold:
        return triangles
    seen = set()
    kept = []
    dropped = 0
    for tri in triangles:
        if tri[0] == tri[1] or tri[1] == tri[2] or tri[0] == tri[2]:
            kept.append(tri)  # degenerate-shaped: never deduped
            continue
        key = tuple(sorted(tri))
        if key in seen:
            dropped += 1  # the later copy: first occurrence's winding wins
            continue
        seen.add(key)
        kept.append(tri)
    if not dropped:
        return triangles
    if mesh.mesh_stats(kept).manifold:
        info["unordered_dedup_dropped"] = dropped
        return kept
    # The duplicates do not explain the over-use (fins/coplanar residue
    # alongside): fail-closed — keep the emitted list, name the gap.
    info["unordered_dedup_declined"] = dropped
    return triangles


def export_once(path):
    """One export through the shipped seam: summary + both area measures."""
    data = Path(path).read_bytes()
    summary, vertices, triangles = export_mod._export_data(data)
    listed, unique = areas(vertices, triangles)
    return summary, listed, unique


def load_baseline_report():
    """The committed report's per-part L2 rows, keyed by sha256."""
    report = json.loads(BASELINE_REPORT.read_text())
    rows = {}
    for record in report["files"]:
        if not record["path"].endswith(".CATPart"):
            continue
        l2 = record.get("l2") or {}
        rows[record["sha256"]] = l2
    return rows


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
    baseline_report = load_baseline_report()

    shipped = composite._apply_unordered_dedup
    ab_rows = []
    try:
        for r in rows_in:
            sha = r["sha256"]
            path = ROOT / r["local_path"]
            ab = {k: "" for k in AB_FIELDS}
            ab["sha256"] = sha
            ab["split"] = r["split"]
            composite._apply_unordered_dedup = before_dedup
            try:
                before = export_once(path)
                summary, listed, unique = before
                comp = summary.get("composite") or {}
                score = _score_export(summary)
                ab["before_export_ok"] = 1
                ab["before_l2_status"] = score["status"]
                ab["before_failed_check"] = score["failed_check"] or ""
                ab["before_triangle_count"] = summary["triangle_count"]
                ab["before_manifold"] = summary["mesh"]["manifold"]
                ab["before_area_mm2"] = round(listed, 6)
                ab["before_uniq_area_mm2"] = round(unique, 6)
                ab["before_dedup_dropped"] = comp.get(
                    "unordered_dedup_dropped", 0
                ) or 0
                ab["before_dedup_declined"] = comp.get(
                    "unordered_dedup_declined", 0
                ) or 0
            except ExportError as exc:
                before = None
                ab["before_export_ok"] = 0
                ab["before_l2_status"] = "fail"
                ab["before_failed_check"] = exc.error_class
            finally:
                composite._apply_unordered_dedup = shipped
            try:
                after = export_once(path)
                summary, listed, unique = after
                comp = summary.get("composite") or {}
                score = _score_export(summary)
                ab["after_export_ok"] = 1
                ab["after_l2_status"] = score["status"]
                ab["after_failed_check"] = score["failed_check"] or ""
                ab["after_triangle_count"] = summary["triangle_count"]
                ab["after_manifold"] = summary["mesh"]["manifold"]
                ab["stage"] = comp.get("stage", "")
                ab["after_area_mm2"] = round(listed, 6)
                ab["after_uniq_area_mm2"] = round(unique, 6)
                ab["after_dedup_dropped"] = comp.get(
                    "unordered_dedup_dropped", 0
                ) or 0
                ab["after_dedup_declined"] = comp.get(
                    "unordered_dedup_declined", 0
                ) or 0
            except ExportError as exc:
                after = None
                ab["after_export_ok"] = 0
                ab["after_l2_status"] = "fail"
                ab["after_failed_check"] = exc.error_class
            if before is not None and after is not None:
                base_area = before[1]
                ab["area_delta_mm2"] = round(after[1] - base_area, 6)
                ab["area_rel"] = (
                    round((after[1] - base_area) / base_area, 9)
                    if base_area
                    else ""
                )
                base_unique = before[2]
                if base_unique:
                    ab["uniq_area_rel"] = round(
                        (after[2] - base_unique) / base_unique, 12
                    )
                # The baseline is the committed report: a drift here
                # invalidates the run instead of silently moving the
                # comparison.
                reference = baseline_report.get(sha)
                if reference and reference.get("status") in ("pass", "fail"):
                    assert ab["before_l2_status"] == reference["status"], sha
                    assert (
                        ab["before_failed_check"]
                        == (reference.get("failed_check") or "")
                    ), sha
                    if reference.get("triangle_count") is not None:
                        assert (
                            ab["before_triangle_count"]
                            == reference["triangle_count"]
                        ), sha
            ab_rows.append(ab)
    finally:
        composite._apply_unordered_dedup = shipped

    verify(ab_rows)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "coord-duplicate-dedup-ab.csv", AB_FIELDS, ab_rows)
    summarize(ab_rows)
    return 0


def verify(ab_rows):
    """The law's own gate: no lost row, no lost surface, no regression."""
    lost = [
        r
        for r in ab_rows
        if r["before_l2_status"] == "pass" and r["after_l2_status"] != "pass"
    ]
    assert not lost, f"pass->fail: {[r['sha256'][:16] for r in lost]}"
    manifold_lost = [
        r
        for r in ab_rows
        if r["before_manifold"] is True and r["after_manifold"] is not True
    ]
    assert not manifold_lost, [r["sha256"][:16] for r in manifold_lost]
    # The geometric surface: every coordinate-identical triple counted
    # once. A dropped copy repeats the kept copy's three points, so this
    # number must not move (f64 summation order is the only freedom).
    moved = [
        r
        for r in ab_rows
        if r["uniq_area_rel"] != ""
        and abs(float(r["uniq_area_rel"])) > 1e-9
    ]
    assert not moved, [
        (r["sha256"][:16], r["uniq_area_rel"]) for r in moved
    ]


def write_csv(path, fields, rows):
    with Path(path).open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {path} ({len(rows)} rows)")


def summarize(ab_rows):
    exported = [r for r in ab_rows if r["after_export_ok"] == 1]
    before_pass = [r for r in ab_rows if r["before_l2_status"] == "pass"]
    after_pass = [r for r in ab_rows if r["after_l2_status"] == "pass"]
    gained = [
        r
        for r in ab_rows
        if r["before_l2_status"] != "pass" and r["after_l2_status"] == "pass"
    ]
    flips = [
        r
        for r in ab_rows
        if r["before_manifold"] is False and r["after_manifold"] is True
    ]
    listed_moved = [
        r
        for r in ab_rows
        if r["area_rel"] != "" and abs(float(r["area_rel"])) > 1e-9
    ]
    print(
        f"parts {len(ab_rows)}; exported {len(exported)}; "
        f"L2 pass {len(before_pass)} -> {len(after_pass)}; "
        f"fail->pass {len(gained)}; manifold flips {len(flips)}"
    )
    for row in listed_moved:
        print(
            f"listed area {row['sha256'][:8]} "
            f"{row['before_area_mm2']} -> {row['after_area_mm2']} "
            f"(rel {row['area_rel']}); unique area rel "
            f"{row['uniq_area_rel']}"
        )
    dedup = [
        r
        for r in ab_rows
        if r["after_dedup_dropped"] or r["after_dedup_declined"]
    ]
    print(f"parts carrying a dedup outcome after: {len(dedup)}")


if __name__ == "__main__":
    sys.exit(main())
