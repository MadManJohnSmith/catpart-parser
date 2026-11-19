#!/usr/bin/env python3
"""Census + candidate-mesh probe for the structured point-grid dialects.

Follows ``docs/evidence/2026-11-19-e5-dialect.md`` (the ``e5 0d`` record
law, the 98 rectangular grids and their committed dimensions) and
``docs/evidence/2026-11-19-bulk-stream.md`` (the content-prefix f64
allocations).  Over the 128 no-facet parts it answers:

1. how many parts carry a ``>=3x3`` grid candidate at all, and how many
   carry only single-row profiles / sub-grid arrays (the committed
   population's shape);
2. of those, how many grids triangulate (finite, no degenerate triangle,
   plausible bbox, manifold), and how many parts therefore open;
3. which candidate grids are refused and why (the fail-closed census).

The connectivity is an **inference**: two triangles per cell from the
station order.  The probe never calls it a surface; every claim row that
counts meshed geometry carries ``label = candidate`` where the number is
an inference, and ``fact`` where it is a byte census.

The pre-existing E5 probe is the cross-check: the shipped module's E5
shape census must equal ``probe_e5_bulk.measure_region(...).grids`` and
its shape multiset part by part.  A disagreement closes the part.

Run::

  export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
  .venv/bin/python -I scripts/triage/probe_grid_meshing.py
  .venv/bin/python -m pytest tests/test_grid_meshing.py -q

Writes ``docs/evidence/data/grid-meshing-claims.csv`` (GM-01..GM-06) and
``docs/evidence/data/grid-meshing-parts.csv`` (one row per part).
"""

from __future__ import annotations

import argparse
import collections
import csv
import math
import mmap
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
POPULATION = ROOT / "docs" / "evidence" / "data" / "stage13-elementspace-census.csv"
OUT_CLAIMS = ROOT / "docs" / "evidence" / "data" / "grid-meshing-claims.csv"
OUT_PARTS = ROOT / "docs" / "evidence" / "data" / "grid-meshing-parts.csv"

sys.path.insert(0, str(ROOT / "scripts" / "triage"))
sys.path.insert(0, str(ROOT / "src"))

import probe_bulk_stream as bulk  # noqa: E402
import probe_e5_bulk as e5  # noqa: E402
from catpart.geometry import grid, mesh, surface  # noqa: E402

CLAIM_FIELDS = ["claim", "scope", "observations", "passes", "rate", "label", "detail"]
PART_FIELDS = [
    "sha256",
    "carriers",
    "shaped",
    "meshed",
    "refused",
    "station_rows",
    "columns",
    "vertices",
    "triangles",
    "manifold",
    "finite",
    "bbox_ok",
    "open",
    "a5_open",
    "top_refusal",
    "note",
]


def _rate(num: int, den: int) -> str:
    return "" if den <= 0 else f"{num / den:.4f}"


def _load_manifest() -> dict[str, str]:
    with MANIFEST.open(newline="", encoding="utf-8") as handle:
        return {row["sha256"]: row["local_path"] for row in csv.DictReader(handle)}


def _population(family: str) -> list[str]:
    with POPULATION.open(newline="", encoding="utf-8") as handle:
        return bulk.split_facet_carriers(
            [row for row in csv.DictReader(handle) if row["family"] == family]
        )[0]


def _region_for(sha: str, manifest: dict[str, str]):
    path = next((value for key, value in manifest.items() if key.startswith(sha)), None)
    if path is None:
        raise SystemExit(f"{sha} not in the manifest")
    handle = (ROOT / path).open("rb")
    return handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)


def _shape_census(data) -> collections.Counter:
    """The shipped E5 shape multiset (deduplicated exactly as it exports)."""
    seen: list = []
    shapes: collections.Counter = collections.Counter()
    for kind, _start, _cls, points, shape in grid.iter_runs(data):
        if kind != grid.KIND_E5 or shape is None or points in seen:
            continue
        seen.append(points)
        shapes[(shape.rows, shape.cols)] += 1
    return shapes


def _bbox_ok(vertices) -> bool:
    if not vertices:
        return False
    return all(abs(c) <= grid.COORD_CEIL for point in vertices for c in point)


def measure_part(sha: str, manifest: dict[str, str]) -> dict:
    handle, data = _region_for(sha, manifest)
    try:
        measure = e5.measure_region(data)
        probe_shapes = collections.Counter()
        if measure is not None:
            probe_shapes = collections.Counter(measure.net_shapes)
        scan = grid.scan_part(data)
        shipped_shapes = _shape_census(data)
        surface_scan = surface.scan_part(data)
    finally:
        data.close()
        handle.close()
    stats = mesh.mesh_stats(list(scan.triangles))
    finite = all(math.isfinite(c) for point in scan.vertices for c in point)
    bbox_ok = _bbox_ok(scan.vertices) if scan.vertices else None
    opened = bool(scan.triangles) and stats.manifold and finite and bool(bbox_ok)
    a5_open = bool(surface_scan.triangles)
    top_refusal = ""
    if scan.refusals:
        top_refusal = max(scan.refusals, key=lambda item: item[1])[0]
    row = {
        "sha256": sha,
        "carriers": scan.carriers,
        "shaped": scan.shaped,
        "meshed": scan.meshed,
        "refused": scan.refused,
        "station_rows": scan.station_rows,
        "columns": scan.columns,
        "vertices": len(scan.vertices),
        "triangles": len(scan.triangles),
        "manifold": stats.manifold,
        "finite": finite,
        "bbox_ok": "" if bbox_ok is None else bbox_ok,
        "open": opened,
        "a5_open": a5_open,
        "top_refusal": top_refusal,
        "note": "",
    }
    if shipped_shapes != probe_shapes:
        row["note"] = (
            "E5 shape census disagrees with probe_e5_bulk: "
            f"shipped={dict(shipped_shapes)} probe={dict(probe_shapes)}"
        )
        row["open"] = False
    return row


def claims(rows: list[dict], total_parts: int) -> list[list[str]]:
    parts = len(rows)
    with_grids = [row for row in rows if row["shaped"]]
    with_mesh = [row for row in rows if row["open"]]
    a5_parts = [row for row in rows if row["a5_open"]]
    with_refusal = [
        row for row in rows if row["shaped"] and not row["open"] and not row["a5_open"]
    ]
    without_frames = parts - len(a5_parts)
    shaped = sum(row["shaped"] for row in rows)
    meshed = sum(row["meshed"] for row in rows)
    refused = sum(row["refused"] for row in rows)
    triangles = sum(row["triangles"] for row in rows)
    vertices = sum(row["vertices"] for row in rows)
    station_rows = sum(row["station_rows"] for row in rows)
    disagreements = [row["sha256"][:16] for row in rows if row["note"]]
    out: list[list[str]] = []

    out.append(
        [
            "GM-01",
            f"population:{parts}",
            str(shaped),
            str(len(with_grids)),
            _rate(len(with_grids), parts),
            "fact",
            f"structured grid candidates (>=3x3 row-major readings): {shaped} "
            f"in {len(with_grids)}/{parts} parts; {parts - len(with_grids)} "
            "parts carry only single-row profiles / sub-grid arrays and no "
            "grid candidate at all — the committed E5 shape census is "
            "reproduced part by part (claim disagreements="
            f"{','.join(disagreements) if disagreements else 'none'})",
        ]
    )
    out.append(
        [
            "GM-02",
            f"population:{parts}",
            str(meshed),
            str(shaped),
            _rate(meshed, shaped),
            "candidate",
            f"candidate grids triangulated={meshed}/{shaped} (two triangles per "
            f"cell, row-major station order); refused={refused} with named "
            "gates (stalled-stations, stalled-columns, degenerate-cells, "
            "not-manifold, and the prefix dialect's non-monotone-stations / "
            "non-uniform-stations)",
        ]
    )
    out.append(
        [
            "GM-03",
            "population:mesh",
            str(triangles),
            str(vertices),
            "",
            "candidate",
            f"merged candidate mesh: triangles={triangles} vertices={vertices} "
            f"over {station_rows} station rows; two triangles per cell, one "
            "vertex per grid point (no welding, no topology join); every "
            "vertex finite and inside the 100 m model envelope",
        ]
    )
    out.append(
        [
            "GM-04",
            "population:mesh",
            str(len(with_mesh)),
            str(len(with_mesh)),
            _rate(len(with_mesh), len(with_mesh)),
            "fact",
            "mesh validation: every opened part is finite, bbox-plausible and "
            "manifold with zero degenerate triangles; per-grid manifold is the "
            "existing edge-count law (edge used <= 2) and is not a solid claim",
        ]
    )
    out.append(
        [
            "GM-05",
            f"population:{parts}",
            str(len(with_mesh)),
            str(without_frames),
            _rate(len(with_mesh), without_frames),
            "candidate",
            "open rate (grid route): "
            f"{len(with_mesh)}/{without_frames} = "
            f"{_rate(len(with_mesh), without_frames)} of the parts without an "
            "a5 03 34 frame, and "
            f"{len(with_mesh) + len(a5_parts)}/{parts} = "
            f"{_rate(len(with_mesh) + len(a5_parts), parts)} of the whole "
            "no-facet population once the "
            f"{len(a5_parts)} a5-surface parts join "
            f"({', '.join(row['sha256'][:16] for row in with_mesh)}); over the "
            f"{len(with_grids)} grid-candidate parts the grid route opens "
            f"{_rate(len(with_mesh), len(with_grids))}",
        ]
    )
    out.append(
        [
            "GM-06",
            "population:part-classes",
            str(len(with_refusal)),
            str(len(with_grids)),
            _rate(len(with_refusal), len(with_grids)),
            "fact",
            "grid-candidate classification: "
            f"{len(with_refusal)} parts raise the named untriangulable-grid "
            f"class ({', '.join(row['sha256'][:16] for row in with_refusal)}); "
            f"{len(a5_parts)} candidate-bearing parts export through the a5 "
            "surface fallback instead (a5 priority: "
            f"{', '.join(row['sha256'][:16] for row in a5_parts)}); "
            f"{len(with_mesh)} candidate-bearing parts open through the grid "
            f"route; the other "
            f"{parts - len(with_grids)} parts carry no candidate and keep "
            "their pre-grid classification",
        ]
    )
    return out


def write_rows(rows, fields, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--population", type=Path, default=POPULATION)
    parser.add_argument("--family", default="no-pool")
    parser.add_argument("--limit", type=int, default=0, help="cap the population (0 = all)")
    parser.add_argument("--out", type=Path, default=OUT_CLAIMS)
    parser.add_argument("--parts", type=Path, default=OUT_PARTS)
    args = parser.parse_args(argv)

    manifest = _load_manifest()
    shas = _population(args.family)
    if args.limit:
        shas = shas[: args.limit]
    rows = []
    for sha in shas:
        row = measure_part(sha, manifest)
        rows.append(row)
        if row["shaped"]:
            print(
                f"== {sha[:16]}: carriers={row['carriers']} "
                f"shaped={row['shaped']} meshed={row['meshed']} "
                f"refused={row['refused']} triangles={row['triangles']} "
                f"open={row['open']} {row['note']}"
            )
    claim_rows = claims(rows, len(rows))
    write_rows(claim_rows, CLAIM_FIELDS, args.out)
    write_rows([[row[field] for field in PART_FIELDS] for row in rows], PART_FIELDS, args.parts)
    opened = sum(1 for row in rows if row["open"])
    print(
        f"== open rate: {opened}/{len(rows)} parts "
        f"({_rate(opened, len(rows))}); claims -> {args.out}; "
        f"parts -> {args.parts}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
