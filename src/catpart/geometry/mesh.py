"""Mesh invariants over the decoded triangle soup (G3 F6/F8 measures).

Adapted from ``scripts/triage/decode_facet_semantics.py``'s
``soup_stats`` with the semantics unchanged: undirected edge usage,
manifold (no edge used more than twice), closure (every edge exactly
twice), orientation consistency (each edge used once per direction) and
the boundary-edge count — the numbers G3 validated the acceptance-seed
soup with (140 triangles, 210 edges, closed manifold, oriented).

A non-closed result is legitimate geometry (the sheet-like open shells
of F6: 10/76 clean-store soups), reported as the ``open-shell`` warning
class, never an error.
"""

from __future__ import annotations

import dataclasses
from collections import Counter


@dataclasses.dataclass(frozen=True)
class MeshStats:
    """Invariants of one decoded triangle mesh."""

    edge_count: int  # distinct undirected edges
    manifold: bool  # every edge used at most twice
    closed: bool  # every edge used exactly twice
    oriented: bool  # each edge used once per direction
    boundary_edges: int  # edges used exactly once


def mesh_stats(triangles: list[tuple[int, int, int]]) -> MeshStats:
    """Edge histogram and closure/orientation invariants (G3 soup_stats)."""
    edge: Counter[tuple[int, int]] = Counter()
    directed: Counter[tuple[int, int]] = Counter()
    for tri in triangles:
        for e in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            edge[tuple(sorted(e))] += 1
            directed[e] += 1
    return MeshStats(
        edge_count=len(edge),
        manifold=all(v <= 2 for v in edge.values()),
        closed=all(v == 2 for v in edge.values()),
        oriented=all(directed[(a, b)] == directed[(b, a)] for (a, b) in directed),
        boundary_edges=sum(1 for v in edge.values() if v == 1),
    )


def used_vertex_count(triangles: list[tuple[int, int, int]], n_vertices: int) -> int:
    """How many of the ``n_vertices`` pool positions any triangle uses."""
    used = {i for tri in triangles for i in tri}
    return sum(1 for i in range(n_vertices) if i in used)


def bounding_box(
    pool: list[tuple[float, float, float]],
) -> tuple[list[float], list[float]]:
    """The pool coordinate extents as ``(min, max)`` triples."""
    xs, ys, zs = zip(*pool)
    return (
        [min(xs), min(ys), min(zs)],
        [max(xs), max(ys), max(zs)],
    )
