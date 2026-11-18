#!/usr/bin/env python3
"""A/B of the primary-emit manifold seam (2026-11-18, #34).

The composite exporter's primary loop emission (``triangles.extend(tris)``
in ``composite._triangulate``) is the one seam that had no manifold guard.
This harness measures the shipped seam (docs/evidence/
2026-11-18-primary-emit-seam.md) against the pre-seam emission on every
dev/held-out part of the manifest:

- **baseline pass** — ``composite.decode_composite_store`` is called with
  ``_seam_area=None``, which disables the seam: every refused loop is
  kept, i.e. exactly the emission before the change (the guard folds the
  kept loop's edges, so the triangle list and its order are unchanged);
- **after pass** — the shipped entry point (registry pass + guarded
  pass).

Both passes score the same L2 gate (``fitness.runner._score_export`` —
the single gate authority, no fork) and measure the exported mesh's area
from its own vertices/triangles (the seam's own fidelity measure, the
sum of triangle areas in mm²).

The loop trace monkeypatches ``_loop_area`` / ``_mesh_safe`` for the
after pass only: ``emit`` calls them back-to-back on the same triangle
object, so a refusal whose object identity matches the last measured
area is a primary-seam refusal (the extended-record and dup-pin guards
never call ``_loop_area``).  The trace's own skip/keep decision (area <=
1% of the baseline store area) is checked against the shipped
``primary_loop_skips`` / ``primary_loop_kept`` counters; a mismatch
fails the run.

Outputs (deterministic, sorted manifest order; no wall-clock value):

  docs/evidence/data/primary-emit-seam-ab.csv     one row per part
  docs/evidence/data/primary-emit-seam-loops.csv  one row per refused loop

Read-only over the corpus:

  .venv/bin/python -I scripts/triage/primary_emit_seam_ab.py
  [--include-sha16 HEX16,...]
"""

import argparse
import csv
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"

sys.path.insert(0, str(ROOT / "src"))

from catpart.fitness.runner import _score_export  # noqa: E402
from catpart.geometry import ExportError  # noqa: E402
from catpart.geometry import composite  # noqa: E402
from catpart.geometry import export as export_mod  # noqa: E402

AB_FIELDS = [
    "sha256", "split", "stage",
    "before_export_ok", "after_export_ok",
    "before_l2_status", "after_l2_status",
    "before_failed_check", "after_failed_check",
    "before_triangle_count", "after_triangle_count",
    "before_manifold", "after_manifold",
    "before_area_mm2", "after_area_mm2",
    "area_delta_mm2", "area_rel",
    "primary_loop_skips", "primary_loop_kept",
    "primary_loop_seam_declined",
]

LOOP_FIELDS = [
    "sha256", "split", "loop_area_mm2", "store_area_mm2",
    "area_rel", "triangles", "decision",
]


def mesh_area(vertices, triangles):
    """The triangle-soup area in mm² (the seam's reference measure)."""
    total = 0.0
    for a, b, c in triangles:
        pa, pb, pc = vertices[a], vertices[b], vertices[c]
        ux, uy, uz = pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]
        vx, vy, vz = pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2]
        cx = uy * vz - uz * vy
        cy = uz * vx - ux * vz
        cz = ux * vy - uy * vx
        total += 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)
    return total


class LoopTrace:
    """The primary-seam refusal trace (after pass only)."""

    def __init__(self):
        self.entries = []
        self.active = False
        self._orig_loop_area = composite._loop_area
        self._orig_mesh_safe = composite._mesh_safe

    def install(self):
        trace = self

        def loop_area(tris, points):
            area = trace._orig_loop_area(tris, points)
            if trace.active:
                trace._last = {"area": area, "tris": tris}
            return area

        def mesh_safe(edge_uses, tris):
            ok = trace._orig_mesh_safe(edge_uses, tris)
            if (
                trace.active
                and not ok
                and trace._last.get("tris") is tris
            ):
                trace.entries.append(
                    {"area": trace._last["area"], "triangles": len(tris)}
                )
            return ok

        composite._loop_area = loop_area
        composite._mesh_safe = mesh_safe

    def install_decode(self):
        """Mark the guarded pass: the entry call (``_seam_area`` unset)
        is the registry pass; only the float-area recursion is traced."""
        trace = self
        original = composite.decode_composite_store

        def traced(*args, **kwargs):
            seam = kwargs.get("_seam_area", composite._SEAM_UNSET)
            trace.active = seam is not composite._SEAM_UNSET and seam is not None
            return original(*args, **kwargs)

        composite.decode_composite_store = traced

    def uninstall(self):
        composite._loop_area = self._orig_loop_area
        composite._mesh_safe = self._orig_mesh_safe

    def reset(self):
        self.entries = []
        self.active = False
        self._last = {"area": None, "tris": None}


def baseline_decode(original):
    """A ``decode_composite_store`` wrapper that forces the seam off."""

    def seam_off(*args, **kwargs):
        kwargs["_seam_area"] = None
        return original(*args, **kwargs)

    return seam_off


def export_once(path):
    """One export through the shipped seam: summary + written mesh area.

    ``export._export_data`` is the same decode ``build_export`` drives;
    calling it directly keeps the vertices in their decoded f64 form (the
    PLY writer rounds to f32) and skips the file I/O.
    """
    data = Path(path).read_bytes()
    summary, vertices, triangles = export_mod._export_data(data)
    return summary, mesh_area(vertices, triangles)


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

    ab_rows = []
    loop_rows = []
    trace = LoopTrace()
    original = composite.decode_composite_store
    seam_off = baseline_decode(original)
    try:
        for r in rows_in:
            sha = r["sha256"]
            path = ROOT / r["local_path"]
            ab = {k: "" for k in AB_FIELDS}
            ab["sha256"] = sha
            ab["split"] = r["split"]
            before = after = None
            composite.decode_composite_store = seam_off
            try:
                before = export_once(path)
            except ExportError as exc:
                ab["before_export_ok"] = 0
                ab["before_l2_status"] = "fail"
                ab["before_failed_check"] = exc.error_class
            # after pass: the shipped entry point, traced
            composite.decode_composite_store = original
            trace.reset()
            trace.install()
            trace.install_decode()
            try:
                after = export_once(path)
            except ExportError as exc:
                ab["after_export_ok"] = 0
                ab["after_l2_status"] = "fail"
                ab["after_failed_check"] = exc.error_class
            finally:
                trace.uninstall()
                composite.decode_composite_store = original
            if before is not None:
                summary, area = before
                score = _score_export(summary)
                ab["before_export_ok"] = 1
                ab["before_l2_status"] = score["status"]
                ab["before_failed_check"] = score["failed_check"] or ""
                ab["before_triangle_count"] = summary["triangle_count"]
                ab["before_manifold"] = summary["mesh"]["manifold"]
                ab["before_area_mm2"] = round(area, 6)
            if after is not None:
                summary, area = after
                score = _score_export(summary)
                comp = summary.get("composite") or {}
                ab["after_export_ok"] = 1
                ab["after_l2_status"] = score["status"]
                ab["after_failed_check"] = score["failed_check"] or ""
                ab["after_triangle_count"] = summary["triangle_count"]
                ab["after_manifold"] = summary["mesh"]["manifold"]
                ab["after_area_mm2"] = round(area, 6)
                ab["stage"] = comp.get("stage", "")
                ab["primary_loop_skips"] = comp.get("primary_loop_skips", 0)
                ab["primary_loop_kept"] = comp.get("primary_loop_kept", 0)
                ab["primary_loop_seam_declined"] = comp.get(
                    "primary_loop_seam_declined", 0
                )
                if before is not None:
                    base_area = before[1]
                    ab["area_delta_mm2"] = round(area - base_area, 6)
                    ab["area_rel"] = (
                        round((area - base_area) / base_area, 9)
                        if base_area
                        else ""
                    )
                    # The trace's decision must reproduce the shipped
                    # counters: skip iff area <= 1% of the before mesh;
                    # a store whose seam was declined keeps every
                    # candidate sliver (the pre-seam emission).
                    shipped_skips = ab["primary_loop_skips"]
                    shipped_keeps = ab["primary_loop_kept"]
                    declined = int(
                        comp.get("primary_loop_seam_declined", 0) or 0
                    )
                    skips = keeps = declines = 0
                    for entry in trace.entries:
                        rel = entry["area"] / base_area if base_area else 0.0
                        if rel <= composite.PRIMARY_LOOP_AREA_REL:
                            decision = "declined" if declined else "skip"
                        else:
                            decision = "keep"
                        skips += decision == "skip"
                        keeps += decision == "keep"
                        declines += decision == "declined"
                        loop_rows.append(
                            {
                                "sha256": sha,
                                "split": r["split"],
                                "loop_area_mm2": round(entry["area"], 9),
                                "store_area_mm2": round(base_area, 6),
                                "area_rel": round(rel, 9),
                                "triangles": entry["triangles"],
                                "decision": decision,
                            }
                        )
                    assert skips == shipped_skips, sha
                    assert keeps == shipped_keeps, sha
                    assert declines == declined, sha
            ab_rows.append(ab)
    finally:
        composite.decode_composite_store = original

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "primary-emit-seam-ab.csv", AB_FIELDS, ab_rows)
    write_csv(out_dir / "primary-emit-seam-loops.csv", LOOP_FIELDS, loop_rows)
    summarize(ab_rows, loop_rows)
    return 0


def write_csv(path, fields, rows):
    with Path(path).open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {path} ({len(rows)} rows)")


def summarize(ab_rows, loop_rows):
    exported = [r for r in ab_rows if r["after_export_ok"] == 1]
    before_pass = [r for r in ab_rows if r["before_l2_status"] == "pass"]
    after_pass = [r for r in ab_rows if r["after_l2_status"] == "pass"]
    lost = [
        r
        for r in ab_rows
        if r["before_l2_status"] == "pass" and r["after_l2_status"] != "pass"
    ]
    gained = [
        r
        for r in ab_rows
        if r["before_l2_status"] != "pass" and r["after_l2_status"] == "pass"
    ]
    manifold_lost = [
        r
        for r in ab_rows
        if r["before_manifold"] is True and r["after_manifold"] is not True
    ]
    manifold_gained = [
        r
        for r in ab_rows
        if r["before_manifold"] is False and r["after_manifold"] is True
    ]
    decreased = [
        r
        for r in ab_rows
        if r["before_area_mm2"] != ""
        and r["after_area_mm2"] != ""
        and r["after_area_mm2"] < r["before_area_mm2"]
    ]
    skip_rel = [r["area_rel"] for r in loop_rows if r["decision"] == "skip"]
    keep_rel = [r["area_rel"] for r in loop_rows if r["decision"] == "keep"]
    declined_rel = [
        r["area_rel"] for r in loop_rows if r["decision"] == "declined"
    ]
    print(
        f"parts {len(ab_rows)}; exported {len(exported)}; "
        f"L2 pass {len(before_pass)} -> {len(after_pass)}"
    )
    print(f"pass->fail {len(lost)}; fail->pass {len(gained)}")
    print(
        f"manifold regressions {len(manifold_lost)}; "
        f"manifold flips {len(manifold_gained)}"
    )
    print(f"area decreases {len(decreased)}")
    for label, rels in (
        ("skipped", skip_rel),
        ("kept", keep_rel),
        ("declined", declined_rel),
    ):
        if rels:
            print(
                f"{label} loops {len(rels)}: rel min {min(rels):.6%} "
                f"max {max(rels):.6%}"
            )
    worst = max(
        (
            r
            for r in decreased
            if r["before_area_mm2"] and r["after_area_mm2"] != ""
        ),
        key=lambda r: (r["before_area_mm2"] - r["after_area_mm2"])
        / r["before_area_mm2"],
        default=None,
    )
    if worst is not None:
        rel = (
            worst["before_area_mm2"] - worst["after_area_mm2"]
        ) / worst["before_area_mm2"]
        print(
            f"largest area loss {worst['sha256'][:16]} "
            f"{worst['split']} {rel:.4%} "
            f"({worst['before_area_mm2']:.4f} -> {worst['after_area_mm2']:.4f})"
        )


if __name__ == "__main__":
    sys.exit(main())
