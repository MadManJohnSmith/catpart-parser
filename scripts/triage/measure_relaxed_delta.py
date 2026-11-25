#!/usr/bin/env python3
"""Net triangle/area delta of the T3 relaxed families 0x44/0x41 (#61).

The landing audit (:mod:`probe_relaxed_landing`) records what the
relaxed records' references resolve to.  This probe measures the shipped
effect: it exports each of the 115 carrier files twice — once with the
shipped ``RELAXED_SHORT_MARKERS = (0x44, 0x41)`` and once with the same
build patched to ``()`` — and reports the triangle/area/manifold delta
per file.  The base is the SAME code path, never a re-implementation.

Usage:
    .venv/bin/python -B scripts/triage/measure_relaxed_delta.py \
        --out docs/evidence/data/relaxed-facets-delta.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from catpart.geometry import composite, mesh  # noqa: E402
from catpart.geometry.export import _export_data  # noqa: E402

DEFAULT_REPORT = ROOT / "fitness/reports/20261120T183229Z-d503ff.json"
DEFAULT_OUT = ROOT / "docs/evidence/data/relaxed-facets-delta.csv"
MANIFEST = ROOT / "manifests/corpus-manifest.csv"


def carrier_roster(report_path: Path) -> dict[str, str]:
    manifest = {
        row["sha256"][:16]: row["local_path"]
        for row in csv.DictReader(MANIFEST.open(newline=""))
    }
    report = json.loads(report_path.read_text())
    carriers: dict[str, str] = {}
    for entry in report["files"]:
        for warning in (entry.get("l2") or {}).get("warnings") or []:
            if warning["class"] != "unresolved-facet-family":
                continue
            if "0x44" not in warning["detail"] and "0x41" not in warning["detail"]:
                continue
            sha = entry["sha256"][:16]
            local = manifest.get(sha) or entry.get("path")
            if local:
                carriers[sha] = local
    return carriers


def area(verts: list[tuple[float, float, float]], tris) -> float:
    total = 0.0
    for a, b, c in tris:
        va, vb, vc = verts[a], verts[b], verts[c]
        ux, uy, uz = vb[0] - va[0], vb[1] - va[1], vb[2] - va[2]
        wx, wy, wz = vc[0] - va[0], vc[1] - va[1], vc[2] - va[2]
        cx, cy, cz = uy * wz - uz * wy, uz * wx - ux * wz, ux * wy - uy * wx
        total += (cx * cx + cy * cy + cz * cz) ** 0.5 / 2.0
    return total


FIELDS = [
    "sha16",
    "path",
    "stage",
    "base_triangles",
    "shipped_triangles",
    "delta_triangles",
    "base_area_mm2",
    "shipped_area_mm2",
    "delta_area_mm2",
    "base_manifold",
    "shipped_manifold",
    "base_degenerate",
    "shipped_degenerate",
    "relaxed_loops_accepted",
    "relaxed_loops_declined",
]


def run(report_path: Path, out_path: Path, limit: int | None) -> int:
    carriers = carrier_roster(report_path)
    rows: list[dict] = []
    missing: list[str] = []
    errors: list[str] = []
    exported = 0

    for sha, local in sorted(carriers.items()):
        if limit is not None and exported >= limit:
            break
        path = ROOT / local
        if not path.exists():
            missing.append(local)
            continue
        data = path.read_bytes()
        try:
            shipped, verts, tris = _export_data(data)
            shipped_area = area(verts, tris)
            shipped_stats = mesh.mesh_stats(tris)
            original = composite.RELAXED_SHORT_MARKERS
            composite.RELAXED_SHORT_MARKERS = ()
            try:
                base, base_verts, base_tris = _export_data(data)
            finally:
                composite.RELAXED_SHORT_MARKERS = original
            base_area = area(base_verts, base_tris)
            base_stats = mesh.mesh_stats(base_tris)
        except Exception as exc:  # named, never silent
            errors.append(f"{sha} {local}: {type(exc).__name__}: {exc}")
            continue
        comp = shipped.get("composite") or {}
        rows.append(
            {
                "sha16": sha,
                "path": local,
                "stage": comp.get("stage", ""),
                "base_triangles": len(base_tris),
                "shipped_triangles": len(tris),
                "delta_triangles": len(tris) - len(base_tris),
                "base_area_mm2": f"{base_area:.6f}",
                "shipped_area_mm2": f"{shipped_area:.6f}",
                "delta_area_mm2": f"{shipped_area - base_area:.6f}",
                "base_manifold": int(base_stats.manifold),
                "shipped_manifold": int(shipped_stats.manifold),
                "base_degenerate": base.get("degenerate_triangle_count", 0),
                "shipped_degenerate": shipped.get("degenerate_triangle_count", 0),
                "relaxed_loops_accepted": comp.get("relaxed_loops_accepted", 0),
                "relaxed_loops_declined": comp.get("relaxed_loops_declined", 0),
            }
        )
        exported += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    gained = [r for r in rows if int(r["delta_triangles"]) > 0]
    print(
        f"carrier files: {len(carriers)}  exported: {len(rows)}  "
        f"missing: {len(missing)}  errors: {len(errors)}"
    )
    for line in missing[:10]:
        print(f"  missing: {line}")
    for line in errors[:10]:
        print(f"  error: {line}")
    print(
        "files gaining triangles: "
        f"{len(gained)}  extra triangles: "
        f"{sum(int(r['delta_triangles']) for r in rows)}  extra area: "
        f"{sum(float(r['delta_area_mm2']) for r in rows):.1f} mm²"
    )
    print(
        "manifold regressions: "
        f"{sum(1 for r in rows if r['base_manifold'] and not r['shipped_manifold'])}  "
        "degenerate delta on passing parts: "
        f"{sum(int(r['shipped_degenerate']) - int(r['base_degenerate']) for r in rows)}"
    )
    for r in sorted(rows, key=lambda x: -int(x["delta_triangles"]))[:10]:
        print(
            f"  {r['sha16']} {r['delta_triangles']:>+6} tris  "
            f"{float(r['delta_area_mm2']):>+10.1f} mm²  {r['path'][:70]}"
        )
    print(f"wrote {out_path} ({len(rows)} rows)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    return run(args.report, args.out, args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
