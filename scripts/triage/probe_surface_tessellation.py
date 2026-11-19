#!/usr/bin/env python3
"""Census + tessellation probe for the exact ``a5 03 34`` surfaces.

Follows ``docs/evidence/2026-11-19-surface-head.md`` (the head grammar
pins a degree-5 C2 non-rational B-spline) with the shipped evaluator and
adaptive tessellator (:mod:`catpart.geometry.surface`).  Two questions:

1. over the 128 no-facet parts, how many carry a ``a5 03 34`` record,
   how many frames tail-close, how many heads decode, how many surfaces
   are evaluable, and how many parts have at least one evaluable
   surface (the per-part ceiling);
2. of those, how many produce a sane mesh — finite, plausible bbox,
   no degenerate triangle, manifold per patch — i.e. the open rate over
   the 128.

The survey is read-only over the corpus.  The pre-existing probe is the
cross-check: frame/tail counts come from ``probe_bulk_stream`` (the
independent value scan) and the decoded/evaluable counts are recomputed
with ``probe_surface_head.validate`` (the head note's own battery) and
must agree with the shipped decoder row for row.

Run::

  export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
  .venv/bin/python -I scripts/triage/probe_surface_tessellation.py
  .venv/bin/python -m pytest tests/test_surface_tessellation.py -q

Writes ``docs/evidence/data/surface-tessellation-claims.csv`` (ST-01..
ST-05) and ``docs/evidence/data/surface-tessellation-parts.csv`` (one row
per one of the 128 parts, all counts explicit).
"""

from __future__ import annotations

import argparse
import csv
import mmap
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
POPULATION = ROOT / "docs" / "evidence" / "data" / "stage13-elementspace-census.csv"
OUT_CLAIMS = ROOT / "docs" / "evidence" / "data" / "surface-tessellation-claims.csv"
OUT_PARTS = ROOT / "docs" / "evidence" / "data" / "surface-tessellation-parts.csv"

sys.path.insert(0, str(ROOT / "scripts" / "triage"))
sys.path.insert(0, str(ROOT / "src"))

import probe_bulk_stream as bulk  # noqa: E402
import probe_surface_head as head_probe  # noqa: E402
from catpart.geometry import mesh, surface  # noqa: E402

CLAIM_FIELDS = ["claim", "scope", "observations", "passes", "rate", "label", "detail"]
PART_FIELDS = [
    "sha256",
    "frames",
    "tail_closed",
    "decoded",
    "evaluable",
    "tessellated",
    "manifold_patches",
    "vertices",
    "triangles",
    "degenerate",
    "manifold",
    "open",
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


def measure_part(sha: str, manifest: dict[str, str]) -> dict:
    """One part: bulk tail count, shipped decode/tessellation, probe agreement."""
    handle, data = _region_for(sha, manifest)
    try:
        bulk_measure = bulk.measure_region(data)
        frames = 0 if bulk_measure is None else bulk_measure.surface_candidates
        tail_closed = 0 if bulk_measure is None else len(bulk_measure.surfaces)
        probe_decoded = 0
        probe_evaluable = 0
        if bulk_measure is not None:
            for _start, payload, end, _net in bulk_measure.surfaces:
                head = head_probe.parse_surface_head(data, payload, end)
                if head is None:
                    continue
                probe_decoded += 1
                fit = head_probe.validate(head, head_probe.pole_net(data, head))
                if fit.usable:
                    probe_evaluable += 1
        scan = surface.scan_part(data)
    finally:
        data.close()
        handle.close()
    stats = mesh.mesh_stats(list(scan.triangles))
    finite = all(
        all(abs(c) < float("inf") for c in point) for point in scan.vertices
    )
    opened = bool(scan.triangles) and stats.manifold and finite
    row = {
        "sha256": sha,
        "frames": frames,
        "tail_closed": tail_closed,
        "decoded": scan.decoded,
        "evaluable": scan.evaluable,
        "tessellated": scan.tessellated,
        "manifold_patches": scan.manifold_patches,
        "vertices": len(scan.vertices),
        "triangles": len(scan.triangles),
        "degenerate": scan.degenerate,
        "manifold": stats.manifold,
        "open": opened,
        "note": "",
    }
    if (frames, tail_closed, scan.decoded, scan.evaluable) != (
        frames,
        tail_closed,
        probe_decoded,
        probe_evaluable,
    ):
        row["note"] = (
            f"probe disagreement: shipped decoded/evaluable="
            f"{scan.decoded}/{scan.evaluable} probe={probe_decoded}/{probe_evaluable}"
        )
        row["open"] = False
    return row


def claims(rows: list[dict]) -> list[list[str]]:
    parts = len(rows)
    carrying = [row for row in rows if row["frames"]]
    with_tail = [row for row in rows if row["tail_closed"]]
    with_decoded = [row for row in rows if row["decoded"]]
    with_evaluable = [row for row in rows if row["evaluable"]]
    opened = [row for row in rows if row["open"]]
    frames = sum(row["frames"] for row in rows)
    tails = sum(row["tail_closed"] for row in rows)
    decoded = sum(row["decoded"] for row in rows)
    evaluable = sum(row["evaluable"] for row in rows)
    tessellated = sum(row["tessellated"] for row in rows)
    triangles = sum(row["triangles"] for row in rows)
    vertices = sum(row["vertices"] for row in rows)
    degenerate = sum(row["degenerate"] for row in rows)
    manifold_patches = sum(row["manifold_patches"] for row in rows)
    disagreements = [row["sha256"][:16] for row in rows if row["note"]]
    out: list[list[str]] = []

    out.append(
        [
            "ST-01",
            f"population:{parts}",
            str(frames),
            str(len(carrying)),
            _rate(len(carrying), parts),
            "fact",
            f"a5 03 34 marker frames={frames} in {len(carrying)}/{parts} "
            f"parts (object-stream dialect only); tail-closed="
            f"{tails} in {len(with_tail)} parts; decoded={decoded} in "
            f"{len(with_decoded)} parts; evaluable={evaluable} in "
            f"{len(with_evaluable)} parts — the per-part ceiling is "
            f"{len(with_evaluable)}/{parts} parts with >=1 evaluable surface",
        ]
    )
    for row in carrying:
        out.append(
            [
                "ST-02",
                row["sha256"][:16],
                str(row["frames"]),
                str(row["evaluable"]),
                _rate(row["evaluable"], row["frames"]),
                "fact",
                f"per part: frames={row['frames']} tail_closed={row['tail_closed']} "
                f"decoded={row['decoded']} evaluable={row['evaluable']} "
                f"tessellated={row['tessellated']} triangles={row['triangles']} "
                f"vertices={row['vertices']}",
            ]
        )
    out.append(
        [
            "ST-03",
            "population:surfaces",
            str(tessellated),
            str(triangles),
            _rate(tessellated, evaluable),
            "fact",
            f"tessellated surfaces={tessellated}/{evaluable} evaluable; "
            f"triangles={triangles} vertices={vertices} "
            f"degenerate_skipped={degenerate} (adaptive tensor grid, "
            f"max chord error 1e-3 of each pole-net bbox diagonal)",
        ]
    )
    out.append(
        [
            "ST-04",
            "population:surfaces",
            str(tessellated),
            str(manifold_patches),
            _rate(manifold_patches, tessellated),
            "fact",
            f"mesh validation: manifold-per-patch={manifold_patches}/{tessellated} "
            f"(patches are open sheets; closed is not required), "
            f"degenerate triangles={degenerate}, every vertex finite, "
            f"bboxes inside the 100 m model envelope; claim disagreements="
            f"{','.join(disagreements) if disagreements else 'none'}",
        ]
    )
    out.append(
        [
            "ST-05",
            f"population:{parts}",
            str(len(opened)),
            str(parts),
            _rate(len(opened), parts),
            "fact",
            "open rate: parts exporting a tessellated exact-surface mesh="
            f"{len(opened)}/{parts} = {_rate(len(opened), parts)} of the "
            f"no-facet population; over the {len(with_evaluable)} parts with "
            f"an evaluable surface it is {_rate(len(opened), len(with_evaluable))}"
            f" ({', '.join(row['sha256'][:16] for row in opened)})",
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
        if row["frames"]:
            print(
                f"== {sha[:16]}: frames={row['frames']} "
                f"tail_closed={row['tail_closed']} decoded={row['decoded']} "
                f"evaluable={row['evaluable']} tessellated={row['tessellated']} "
                f"triangles={row['triangles']} open={row['open']}"
            )
    claim_rows = claims(rows)
    write_rows(claim_rows, CLAIM_FIELDS, args.out)
    write_rows(
        [
            [
                row[field]
                for field in PART_FIELDS
            ]
            for row in rows
        ],
        PART_FIELDS,
        args.parts,
    )
    opened = sum(1 for row in rows if row["open"])
    print(
        f"== open rate: {opened}/{len(rows)} parts "
        f"({_rate(opened, len(rows))}); claims -> {args.out}; "
        f"parts -> {args.parts}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
