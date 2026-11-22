#!/usr/bin/env python3
"""W12 inverse-oracle shared machinery (read-only triage, 2026-11-22).

Everything the two W12 entry points (``w12_inverse_oracle.py`` — the
geometry side — and ``w12_store_decline_map.py`` — the store side)
share: the committed-harness loader, the per-cell aggregation, and the
voxel union-find clusterer.

Design constraints (the W12 dispatch brief):

- Memory is bounded by OCCUPIED CELLS, never by triangle count: every
  signal reduces to a ``{cell_key: CellAgg}`` dict before clustering,
  so the 2.5M-triangle Dodge pair clusters without holding per-triangle
  rows. ``MAX_CELLS`` aborts with a named outcome when a run would
  exceed the budget instead of degrading silently.
- Clustering is exact union-find over 26-adjacent occupied cells; the
  bbox/area/triangle-count of a cluster aggregate from the cell
  aggregates (each cell keeps its own vertex-coordinate bbox
  contribution, so cluster bboxes are true vertex bboxes, not cell
  bboxes).
"""

from __future__ import annotations

import importlib.util
import math
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: Cluster/aggregate cell budget: a named ``cell-budget-exceeded``
#: outcome instead of an OOM. At the default cell (diag/256) a full
#: car-scale part occupies ~1e5-1e6 cells; 4e6 is ~10x headroom.
MAX_CELLS = 4_000_000


class CellBudgetExceeded(RuntimeError):
    """A per-cell aggregation would exceed MAX_CELLS — raise, never trim."""

    def __init__(self, n: int):
        super().__init__(f"cell-budget-exceeded: {n} occupied cells >= MAX_CELLS={MAX_CELLS}")


def load_harness():
    """The committed W7 harness module (identical readers/grids/areas)."""
    path = ROOT / "scripts" / "benchmark_ground_truth.py"
    spec = importlib.util.spec_from_file_location("benchmark_ground_truth", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("benchmark_ground_truth", mod)
    spec.loader.exec_module(mod)
    return mod


def load_triage(name: str):
    """A sibling triage script by file path (probe_top10 machinery)."""
    path = ROOT / "scripts" / "triage" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, mod)
    spec.loader.exec_module(mod)
    return mod


def heron_area(ax, ay, az, bx, by, bz, cx, cy, cz) -> float:
    """Triangle area (the harness's total_area convention: degenerate = 0)."""
    abx, aby, abz = bx - ax, by - ay, bz - az
    acx, acy, acz = cx - ax, cy - ay, cz - az
    bcx, bcy, bcz = cx - bx, cy - by, cz - bz
    la = math.sqrt(abx * abx + aby * aby + abz * abz)
    lb = math.sqrt(acx * acx + acy * acy + acz * acz)
    lc = math.sqrt(bcx * bcx + bcy * bcy + bcz * bcz)
    s = (la + lb + lc) / 2.0
    q = s * (s - la) * (s - lb) * (s - lc)
    return math.sqrt(q) if q > 0 else 0.0


class CellAgg:
    """One cell's aggregates: triangle count, area sum, vertex bbox."""

    __slots__ = ("n", "area", "minx", "miny", "minz", "maxx", "maxy", "maxz")

    def __init__(self) -> None:
        self.n = 0
        self.area = 0.0
        self.minx = math.inf
        self.miny = math.inf
        self.minz = math.inf
        self.maxx = -math.inf
        self.maxy = -math.inf
        self.maxz = -math.inf

    def add(self, area, ax, ay, az, bx, by, bz, cx, cy, cz) -> None:
        self.n += 1
        self.area += area
        self.minx = min(self.minx, ax, bx, cx)
        self.miny = min(self.miny, ay, by, cy)
        self.minz = min(self.minz, az, bz, cz)
        self.maxx = max(self.maxx, ax, bx, cx)
        self.maxy = max(self.maxy, ay, by, cy)
        self.maxz = max(self.maxz, az, bz, cz)


def add_triangle(cells: dict, cell: float, ax, ay, az, bx, by, bz, cx, cy, cz) -> None:
    """Bucket one triangle by its centroid; keep vertex bbox per cell."""
    gx = (ax + bx + cx) / 3.0 / cell
    gy = (ay + by + cy) / 3.0 / cell
    gz = (az + bz + cz) / 3.0 / cell
    key = (int(gx), int(gy), int(gz))
    agg = cells.get(key)
    if agg is None:
        if len(cells) >= MAX_CELLS:
            raise CellBudgetExceeded(len(cells))
        agg = cells[key] = CellAgg()
    agg.add(heron_area(ax, ay, az, bx, by, bz, cx, cy, cz), ax, ay, az, bx, by, bz, cx, cy, cz)


def mesh_cell_areas(mesh, cell: float, bbox=None) -> dict:
    """Per-cell area aggregates for a harness MeshData (one pass)."""
    cells: dict[tuple[int, int, int], CellAgg] = {}
    t = mesh.triangles
    v = mesh.vertices
    for i in range(0, len(t), 3):
        a, b, c = t[i], t[i + 1], t[i + 2]
        ja, jb, jc = a * 3, b * 3, c * 3
        if bbox is not None and not _tri_in_bbox(
            (v[ja], v[ja + 1], v[ja + 2]),
            (v[jb], v[jb + 1], v[jb + 2]),
            (v[jc], v[jc + 1], v[jc + 2]),
            bbox,
        ):
            continue
        add_triangle(
            cells,
            cell,
            v[ja], v[ja + 1], v[ja + 2],
            v[jb], v[jb + 1], v[jb + 2],
            v[jc], v[jc + 1], v[jc + 2],
        )
    return cells


def _tri_in_bbox(a, b, c, bbox) -> bool:
    (x0, y0, z0), (x1, y1, z1) = bbox
    return (
        x0 <= a[0] <= x1 and y0 <= a[1] <= y1 and z0 <= a[2] <= z1
        and x0 <= b[0] <= x1 and y0 <= b[1] <= y1 and z0 <= b[2] <= z1
        and x0 <= c[0] <= x1 and y0 <= c[1] <= y1 and z0 <= c[2] <= z1
    )


_NEIGHBORS_26 = [
    (dx, dy, dz)
    for dx in (-1, 0, 1)
    for dy in (-1, 0, 1)
    for dz in (-1, 0, 1)
    if (dx, dy, dz) != (0, 0, 0)
]


def cluster_cells(cells: dict):
    """26-adjacency union-find over occupied cells.

    Returns ``[(cluster_key_set, cells_of_cluster)]`` — the caller
    aggregates bbox/area/count from the member CellAggs. Memory: two
    dicts of cell keys (visited + union-find root), never per triangle.
    """
    parent: dict = {}

    def find(k):
        root = k
        while parent[root] != root:
            root = parent[root]
        while parent[k] != root:  # path compression
            parent[k], k = root, parent[k]
        return root

    for k in cells:
        parent[k] = k
    for k in cells:
        kx, ky, kz = k
        for dx, dy, dz in _NEIGHBORS_26:
            nb = (kx + dx, ky + dy, kz + dz)
            if nb in parent:
                ra, rb = find(k), find(nb)
                if ra != rb:
                    parent[ra] = rb
    groups: dict = {}
    for k in cells:
        groups.setdefault(find(k), []).append(k)
    return list(groups.values())


def summarize_cluster(member_keys, cells: dict) -> dict:
    """bbox (true vertex bbox), n, area over a cluster's member cells."""
    minx = miny = minz = math.inf
    maxx = maxy = maxz = -math.inf
    n = 0
    area = 0.0
    for k in member_keys:
        agg = cells[k]
        n += agg.n
        area += agg.area
        minx, miny, minz = min(minx, agg.minx), min(miny, agg.miny), min(minz, agg.minz)
        maxx, maxy, maxz = max(maxx, agg.maxx), max(maxy, agg.maxy), max(maxz, agg.maxz)
    return {
        "n_tris": n,
        "area": area,
        "bbox_min": (minx, miny, minz),
        "bbox_max": (maxx, maxy, maxz),
    }


def bbox_diagonal(mesh) -> float:
    """The harness's _bbox_diagonal (re-exported for callers)."""
    xs = mesh.vertices[0::3]
    ys = mesh.vertices[1::3]
    zs = mesh.vertices[2::3]
    return math.sqrt(
        (max(xs) - min(xs)) ** 2 + (max(ys) - min(ys)) ** 2 + (max(zs) - min(zs)) ** 2
    )


def coord_digest(x, y, z) -> bytes:
    """A hashable coordinate identity (struct-packed float64 triple)."""
    return struct.pack("<3d", x, y, z)


def net_missing_clusters(miss_cells: dict, extra_cells: dict, floor: float = 1e-6):
    """Per-cell NET of the identity match: missing − extra area.

    Retriangulated regions (different diagonal splits over the same
    vertices — 33% of the audi mesh's area) carry matched total area on
    both sides, so their per-cell net cancels to ~0; genuinely missing
    faces keep a positive net. Only positive-net cells (above ``floor``,
    a float-noise guard) are clustered. Each cluster reports both sides
    plus the net, so a note can rank by net and still audit the raw
    masses.
    """
    net: dict[tuple[int, int, int], float] = {}
    for k, agg in miss_cells.items():
        d = agg.area - (extra_cells[k].area if k in extra_cells else 0.0)
        if d > floor:
            net[k] = d
    groups = cluster_cells(net)
    out = []
    for member_keys in groups:
        net_area = sum(net[k] for k in member_keys)
        miss_area = sum(miss_cells[k].area for k in member_keys)
        extra_area = sum(extra_cells[k].area for k in member_keys if k in extra_cells)
        n_miss = sum(miss_cells[k].n for k in member_keys)
        n_extra = sum(extra_cells[k].n for k in member_keys if k in extra_cells)
        minx = min(min(miss_cells[k].minx for k in member_keys),
                   min((extra_cells[k].minx for k in member_keys if k in extra_cells), default=math.inf))
        miny = min(min(miss_cells[k].miny for k in member_keys),
                   min((extra_cells[k].miny for k in member_keys if k in extra_cells), default=math.inf))
        minz = min(min(miss_cells[k].minz for k in member_keys),
                   min((extra_cells[k].minz for k in member_keys if k in extra_cells), default=math.inf))
        maxx = max(max(miss_cells[k].maxx for k in member_keys),
                   max((extra_cells[k].maxx for k in member_keys if k in extra_cells), default=-math.inf))
        maxy = max(max(miss_cells[k].maxy for k in member_keys),
                   max((extra_cells[k].maxy for k in member_keys if k in extra_cells), default=-math.inf))
        maxz = max(max(miss_cells[k].maxz for k in member_keys),
                   max((extra_cells[k].maxz for k in member_keys if k in extra_cells), default=-math.inf))
        out.append(
            {
                "n_cells": len(member_keys),
                "n_tris": n_miss,
                "n_extra_tris": n_extra,
                "area": net_area,
                "missing_area": miss_area,
                "extra_area": extra_area,
                "bbox_min": (minx, miny, minz),
                "bbox_max": (maxx, maxy, maxz),
            }
        )
    return out, sum(net.values())


def triangle_key_set(mesh, round_digits: int = 3) -> set:
    """Winding-independent coordinate-identity keys for every triangle.

    Each key: the triangle's three vertices rounded to the 1 µm grid
    (``round_digits`` decimals), sorted, packed as 9 float32 — a compact
    hashable identity for the exact-triangle match. Under the measured
    coincident-vertex regime (ref→ours raw max < 1 µm on audi) a
    reference triangle present in our mesh yields the SAME key.
    """
    return loop_key_set(mesh.vertices, mesh.triangles, round_digits)


def loop_key_set(points, triangles, round_digits: int = 3) -> set:
    """Winding-independent coordinate-identity keys over triangles.

    ``triangles`` accepts either the harness's FLAT index array
    (``array('i')``, stride 3 — ``MeshData.triangles``) or a decoded
    store's list of index triples. ``points`` is correspondingly either
    the flat vertex array (indexed ``v[j*3]``) or a list of xyz tuples.
    """
    flat_points = not isinstance(points, list)
    flat_tris = not (triangles and isinstance(triangles[0], (list, tuple)))
    pack = struct.pack
    rnd = round
    keys = set()
    add = keys.add

    def coord(p, j):
        if flat_points:
            return (rnd(p[j * 3], round_digits), rnd(p[j * 3 + 1], round_digits),
                    rnd(p[j * 3 + 2], round_digits))
        return (rnd(p[j][0], round_digits), rnd(p[j][1], round_digits), rnd(p[j][2], round_digits))

    def tri_iter(t):
        if flat_tris:
            for i in range(0, len(t), 3):
                yield (t[i], t[i + 1], t[i + 2])
        else:
            yield from t

    for tri in tri_iter(triangles):
        p = sorted((coord(points, tri[0]), coord(points, tri[1]), coord(points, tri[2])))
        add(pack(
            "<9f",
            p[0][0], p[0][1], p[0][2],
            p[1][0], p[1][1], p[1][2],
            p[2][0], p[2][1], p[2][2],
        ))
    return keys


def identity_missing_cells(mesh, keys, cell: float) -> tuple[dict, int, float, float, int]:
    """Triangles of ``mesh`` absent from ``keys`` (the identity match's
    unmatched side), bucketed per centroid cell with bbox/area/count.

    Returns ``(cells, n_missing, missing_area, matched_area, n_matched)``;
    matched area sums the Heron area of the matched triangles (the
    conservation check's both-sides bookkeeping).
    """
    v = mesh.vertices
    t = mesh.triangles
    cells: dict = {}
    n_missing = n_matched = 0
    missing_area = matched_area = 0.0
    for i in range(0, len(t), 3):
        a, b, c = t[i], t[i + 1], t[i + 2]
        ja, jb, jc = a * 3, b * 3, c * 3
        tri = sorted((
            (round(v[ja], 3), round(v[ja + 1], 3), round(v[ja + 2], 3)),
            (round(v[jb], 3), round(v[jb + 1], 3), round(v[jb + 2], 3)),
            (round(v[jc], 3), round(v[jc + 1], 3), round(v[jc + 2], 3)),
        ))
        key = struct.pack(
            "<9f",
            tri[0][0], tri[0][1], tri[0][2],
            tri[1][0], tri[1][1], tri[1][2],
            tri[2][0], tri[2][1], tri[2][2],
        )
        if key in keys:
            n_matched += 1
            matched_area += heron_area(
                v[ja], v[ja + 1], v[ja + 2], v[jb], v[jb + 1], v[jb + 2],
                v[jc], v[jc + 1], v[jc + 2],
            )
            continue
        n_missing += 1
        add_triangle(
            cells, cell,
            v[ja], v[ja + 1], v[ja + 2], v[jb], v[jb + 1], v[jb + 2],
            v[jc], v[jc + 1], v[jc + 2],
        )
    missing_area = sum(agg.area for agg in cells.values())
    return cells, n_missing, missing_area, matched_area, n_matched
