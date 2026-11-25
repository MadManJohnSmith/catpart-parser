#!/usr/bin/env python3
"""Probe: how many of the 120 non-opening no-facet parts render with the
display fallback, and what do they show? (2026-11-19)

The population is the 128-row grid-meshing census
(``docs/evidence/data/grid-meshing-parts.csv``): the arms carried by this
probe are the 120 rows that neither meshed through the structured grid
(``open = False``) nor through an ``a5 03 34`` surface (``a5_open =
False``).  Every part is pushed through the shipped export seam
(``catpart.geometry.export._export_data``) and classified as:

- ``display`` — the export succeeded with the ``no_surface_display``
  block (points and/or law-pinned curve segments, zero triangles);
- ``mesh`` — the export produced triangles through a non-display route
  (the W26 compact see-body stream, or a grid/facet route);
- ``error`` — the export raised a named class (a part with no
  displayable carrier keeps its pre-display classification).

It also reproduces the two law measurements the display rests on:

- the ``33 32`` ``[P][Q][P]+|Q|`` reading: on pool-bearing parts the
  law-holding record's ``P+Q`` lands on a decoded pool vertex at 5e-3 mm
  far more often than ``P`` or ``Q`` does, so the segment is P -> P+Q;
- the 120-part carrier census (point runs, curve records, decoded
  centres, segments).

Writes ``docs/evidence/data/no-surface-fallback-claims.csv`` and
``docs/evidence/data/no-surface-fallback-parts.csv``. Deterministic,
read-only over the corpus (``mmap``).

Usage: python scripts/triage/probe_no_surface_fallback.py
"""

from __future__ import annotations

import csv
import math
import mmap
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from catpart.brep import curves  # noqa: E402
from catpart.geometry import ExportError, pool, store  # noqa: E402
from catpart.geometry.export import _export_data  # noqa: E402

DATA = REPO_ROOT / "docs" / "evidence" / "data"
GRID_PARTS = DATA / "grid-meshing-parts.csv"
MANIFEST = REPO_ROOT / "manifests" / "corpus-manifest.csv"
CLAIMS = DATA / "no-surface-fallback-claims.csv"
PARTS = DATA / "no-surface-fallback-parts.csv"

#: The pool-hit tolerance the line-reading claim uses (mm).
POOL_TOL = 5e-3
#: How many pool-bearing files the line-reading sample walks.
LINE_SAMPLE = 120


def _distance(a, b) -> float:
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    dz = b[2] - a[2]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _targets() -> list[str]:
    rows = csv.DictReader(GRID_PARTS.open(newline="", encoding="utf-8"))
    return [
        row["sha256"]
        for row in rows
        if row["open"] == "False" and row["a5_open"] == "False"
    ]


def _manifest() -> dict[str, dict[str, str]]:
    rows = csv.DictReader(MANIFEST.open(newline="", encoding="utf-8"))
    return {row["sha256"]: row for row in rows}


def _open(path: Path):
    fh = open(path, "rb")
    return fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)


def _pool_points(data, blocks) -> list[tuple[float, float, float]]:
    outer = int.from_bytes(data[8:12], "big") if len(data) >= 12 else 0
    points: list[tuple[float, float, float]] = []
    for blk, name in blocks:
        if name != "CATStdCont":
            continue
        try:
            span = store.locate_store(data, blk, blocks, outer)
        except ExportError:
            continue
        if span is None:
            continue
        groups, _kinds = pool.scan_pool_groups(data, span.body_lo, span.body_hi)
        for group in groups:
            points.extend(group.vertices)
    return points


def _line_reading_sample(manifest) -> dict[str, int]:
    """Which reading of the 33 32 block lands on a decoded pool vertex."""
    hits = Counter()
    seen = 0
    for row in manifest.values():
        if seen >= LINE_SAMPLE:
            break
        if row.get("kind") != "part":
            continue
        path = REPO_ROOT / row["local_path"]
        if not path.exists():
            continue
        fh, data = _open(path)
        try:
            blocks = store.valid_blocks(data)
            vertices = _pool_points(data, blocks)
            if not vertices:
                continue
            records = 0
            for record in curves.iter_curve_records(data, 0, len(data)):
                if record.family != 0x32:
                    continue
                try:
                    block = curves.decode_line(record, data)
                except ExportError:
                    continue
                if not (block.p_rep_ok and block.length_ok):
                    continue
                f = block.floats
                p = (f[0], f[1], f[2])
                q = (f[3], f[4], f[5])
                end = (p[0] + q[0], p[1] + q[1], p[2] + q[2])
                records += 1
                hits["p"] += min(_distance(p, v) for v in vertices) <= POOL_TOL
                hits["q"] += min(_distance(q, v) for v in vertices) <= POOL_TOL
                hits["pq"] += min(_distance(end, v) for v in vertices) <= POOL_TOL
            if records:
                hits["records"] += records
                seen += 1
        finally:
            data.close()
            fh.close()
    return dict(hits)


def main() -> int:
    targets = _targets()
    manifest = _manifest()
    rows: list[dict[str, object]] = []
    classes = Counter()
    totals = Counter()
    for sha in targets:
        row = manifest[sha]
        path = REPO_ROOT / row["local_path"]
        if not path.exists():
            print(f"probe: missing corpus file {path}", file=sys.stderr)
            return 2
        fh, data = _open(path)
        try:
            entry: dict[str, object] = {"sha256": sha}
            try:
                summary, vertices, triangles = _export_data(data)
            except ExportError as exc:
                classes[f"error:{exc.error_class}"] += 1
                entry.update(
                    klass="error",
                    error_class=exc.error_class,
                    points=0,
                    curve_segments=0,
                    point_runs=0,
                    run_points=0,
                    pool_points=0,
                    curve_records=0,
                    decoded_curve_records=0,
                    skipped_curve_records=0,
                    line_records=0,
                    families="",
                )
                rows.append(entry)
                continue
            block = summary.get("no_surface_display")
            if block is None:
                classes["ok-without-display"] += 1
                entry.update(klass="mesh", error_class="", points=0, curve_segments=0)
                rows.append(entry)
                continue
            classes["display"] += 1
            totals["points"] += block["point_count"]
            totals["curve_segments"] += block["curve_segment_count"]
            totals["point_runs"] += block["point_runs"]
            totals["run_points"] += block["run_points"]
            totals["pool_points"] += block["pool_points"]
            totals["curve_records"] += block["curve_records"]
            totals["decoded_curve_records"] += block["decoded_curve_records"]
            totals["line_records"] += block["line_records"]
            totals["parts_with_runs"] += 1 if block["point_runs"] else 0
            totals["parts_with_segments"] += 1 if block["curve_segment_count"] else 0
            totals["triangles"] += summary["triangle_count"]
            entry.update(
                klass="display",
                error_class="",
                points=block["point_count"],
                curve_segments=block["curve_segment_count"],
                point_runs=block["point_runs"],
                run_points=block["run_points"],
                pool_points=block["pool_points"],
                curve_records=block["curve_records"],
                decoded_curve_records=block["decoded_curve_records"],
                skipped_curve_records=block["skipped_curve_records"],
                line_records=block["line_records"],
                families=",".join(
                    f"{name}={count}" for name, count in block["families"].items()
                ),
            )
            rows.append(entry)
        finally:
            data.close()
            fh.close()

    total = len(targets)
    assert total == 120, f"the population must be the 120 rows, got {total}"
    display = classes["display"]
    mesh = classes["ok-without-display"]
    named = total - display - mesh
    line = _line_reading_sample(manifest)
    records = line.get("records", 0)
    claims = [
        {
            "claim": "DF-01",
            "scope": f"population:{total}",
            "observations": display,
            "passes": total,
            "rate": f"{display / total:.4f}",
            "label": "fact",
            "detail": f"{display}/{total} of the 120 non-opening no-facet parts render with the "
            f"display fallback (decoded carriers: points and/or law-pinned curve segments, zero "
            f"triangles); the other {mesh} mesh through a non-display route "
            f"(W26 compact see-body / grid) and {named} keep a named failure class "
            "(no displayable carrier)",
        },
        {
            "claim": "DF-02",
            "scope": f"population:{total}",
            "observations": totals["parts_with_runs"],
            "passes": display,
            "rate": f"{totals['parts_with_runs'] / display:.4f}",
            "label": "fact",
            "detail": f"point cloud: {totals['points']} decoded points from "
            f"{totals['point_runs']} 3-divisible f64 point runs ({totals['run_points']} run "
            f"points + {totals['pool_points']} pool points), on {totals['parts_with_runs']}/"
            f"{display} display parts; a run's coordinates are shown, never connected (no row "
            "length is inferred)",
        },
        {
            "claim": "DF-03",
            "scope": f"sample:{LINE_SAMPLE}",
            "observations": line.get("pq", 0),
            "passes": records,
            "rate": f"{line.get('pq', 0) / records:.4f}" if records else "0.0000",
            "label": "candidate",
            "detail": f"the 33 32 [P][Q][P]+|Q| reading is P -> P+Q: on the law-holding "
            f"records of the first {LINE_SAMPLE} pool-bearing files in manifest order, P+Q "
            f"lands on a decoded pool vertex at {POOL_TOL:g} mm {line.get('pq', 0)}/{records}, "
            f"against {line.get('p', 0)}/{records} for P and {line.get('q', 0)}/{records} "
            "for Q",
        },
        {
            "claim": "DF-04",
            "scope": f"population:{total}",
            "observations": totals["decoded_curve_records"],
            "passes": totals["curve_records"],
            "rate": f"{totals['decoded_curve_records'] / totals['curve_records']:.4f}"
            if totals["curve_records"]
            else "0.0000",
            "label": "fact",
            "detail": f"the 33 3X walk over the located store bodies + CATPrtCont regions: "
            f"{totals['curve_records']} records walked, {totals['decoded_curve_records']} "
            f"decoded ({totals['line_records']} law-holding 33 32 lines, the only family that "
            "pins a segment); circles/conics contribute their center point only — no "
            "orientation law exists, so no circle or conic polyline is guessed",
        },
        {
            "claim": "DF-05",
            "scope": f"population:{total}",
            "observations": totals["parts_with_segments"],
            "passes": display,
            "rate": f"{totals['parts_with_segments'] / display:.4f}",
            "label": "fact",
            "detail": f"{totals['curve_segments']} curve segments on "
            f"{totals['parts_with_segments']}/{display} display parts; every segment is a "
            "33 32 record whose P-repeat and |Q| laws both hold — a law-failing record emits "
            "nothing (fail-closed)",
        },
        {
            "claim": "DF-06",
            "scope": f"population:{total}",
            "observations": totals["triangles"],
            "passes": display,
            "rate": "0.0000",
            "label": "fact",
            "detail": "no triangle is emitted on the display route: every display export has "
            "triangle_count = 0 (the PLY is empty) and the §3.4 gate still records empty-mesh, "
            "so L2 is unchanged by construction",
        },
    ]
    _write_csv(CLAIMS, claims)
    parts_fields = [
        "sha256",
        "klass",
        "error_class",
        "points",
        "curve_segments",
        "point_runs",
        "run_points",
        "pool_points",
        "curve_records",
        "decoded_curve_records",
        "skipped_curve_records",
        "line_records",
        "families",
    ]
    _write_csv(PARTS, [{key: row.get(key, "") for key in parts_fields} for row in rows])

    print(f"population: {total}")
    print(f"classes: {dict(sorted(classes.items()))}")
    print(f"totals: {dict(sorted(totals.items()))}")
    print(f"line reading: {line}")
    return 0


def _write_csv(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else [])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
