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
import math
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


# --- the emission guards (2026-11-18, #34) --------------------------------
#
# ONE topology lever and its area measures, shared by every emission
# site of the composite decode: the dup-pin weld, the extended-header
# records, the T3 relaxed loops and the primary-emit seam all admit
# units through :class:`EdgeGuard`, and the seam's sliver rule reads
# the loop/store areas below.  They were composite-private helpers
# before the vote/guard split; the behavior is unchanged.


class EdgeGuard:
    """The incremental manifold guard — ONE topology lever.

    ``admit`` is true when adding ``tris`` keeps every undirected edge
    at two uses or fewer, in which case the edges are folded in; a
    refused unit leaves the histogram untouched (fail-closed,
    deterministic in record/loop order).  ``False`` means the unit
    would tip the assembled mesh past the G3 manifold invariant.  A
    caller that deliberately KEEPS an over-using unit (the primary
    seam's large-loop arm) folds it explicitly with :meth:`fold`, so
    later units see the same histogram the unguarded emission produced.
    """

    __slots__ = ("uses",)

    def __init__(self) -> None:
        self.uses: dict[tuple[int, int], int] = {}

    @classmethod
    def from_triangles(cls, triangles) -> "EdgeGuard":
        guard = cls()
        guard.fold(triangles)
        return guard

    def admit(self, tris) -> bool:
        candidate = edge_uses(tris)
        if any(self.uses.get(edge, 0) + n > 2 for edge, n in candidate.items()):
            return False
        for edge, n in candidate.items():
            self.uses[edge] = self.uses.get(edge, 0) + n
        return True

    def fold(self, tris) -> None:
        """Fold one unit's edge uses into the histogram (the accept arm
        of :meth:`admit`; the seam's keep arm)."""
        for edge, n in edge_uses(tris).items():
            self.uses[edge] = self.uses.get(edge, 0) + n


def edge_key(a: int, b: int) -> tuple[int, int]:
    """The undirected edge key (the mesh-stat edge histogram's key)."""
    return (a, b) if a <= b else (b, a)


def edge_uses(triangles):
    """Undirected edge-use histogram of a triangle list (the mesh
    invariant's key; ``manifold`` == every value <= 2)."""
    uses: dict[tuple[int, int], int] = {}
    for tri in triangles:
        a, b, c = tri
        for key in (edge_key(a, b), edge_key(b, c), edge_key(c, a)):
            uses[key] = uses.get(key, 0) + 1
    return uses


def triangle_area(tri, points):
    """One triangle's area from the written points (mm²)."""
    a, b, c = points[tri[0]], points[tri[1]], points[tri[2]]
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    cx = uy * vz - uz * vy
    cy = uz * vx - ux * vz
    cz = ux * vy - uy * vx
    return 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)


def loop_area(tris, points):
    """A candidate loop's area (the sum over its emitted triangles)."""
    return sum(triangle_area(tri, points) for tri in tris)


def mesh_area(triangles, points):
    """The assembled mesh's area — the primary seam's reference (the
    store-level mesh area, so the rule is order-independent)."""
    return sum(triangle_area(tri, points) for tri in triangles)


def bounding_box(
    pool: list[tuple[float, float, float]],
) -> tuple[list[float], list[float]]:
    """The pool coordinate extents as ``(min, max)`` triples."""
    xs, ys, zs = zip(*pool)
    return (
        [min(xs), min(ys), min(zs)],
        [max(xs), max(ys), max(zs)],
    )
