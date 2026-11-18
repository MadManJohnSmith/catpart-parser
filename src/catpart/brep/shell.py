"""Closed manifold face sets — the TOP-03 Shell partition (BR6, Ticket
#58, Spec G #47).

A shell is not a stored record. The census signature is "closed
manifold face sets with boundary_edge_count = 0" (BR1 vocabulary row
TOP-03), and that is exactly what the bytes support: on a pool-only
store the accepted facet records share the vertex pool, and the shell
partition is DERIVED from the records' decoded triangles — the maximal
connected sets of faces under a shared undirected triangle edge, with a
component being a shell when every edge it uses is used exactly twice
(G3 F6's closure law, applied per component instead of per store).

The derivation is the same shape as BR2's plane offset ``d`` (SRF-01):
a semantic quantity that no field stores. The byte-level carrier of a
shell is the facet record set itself (BR2 §2: marker ``01`` at
``+0x00 (0d)``, marker byte ``mk`` at ``+0x01 (1d)``, loop count ``ty``
at ``+0x02 (2d)``, form byte at ``+0x03 (3d)``, ``u32le n`` at
``+0x04 (4d)``, the 12B f32le normal at ``+0x08 (8d)``, the counts at
``+0x14 (20d)``, the references after them; per-record u8 or u16be
big-endian reference width, little-endian normal) — this module never
re-derives that grammar.

Scope honesty:

- **Pool-only stores.** The partition needs every reference to land in
  the pool. On a composite store (G3 F8; the 78.7% of located stores
  whose references leave the pool — BR2 §4) the geometry is not
  placeable and NO shell is claimed; the caller reports those stores as
  unverified rather than counting their faces as open shells.
- **Out-of-pool face records on pool-only stores** are counted
  (``unplaced_faces``) and excluded — never silently dropped, never
  guessed into a component.
- **Primitive-reading boundary.** The partition follows the shipped
  export reading exactly (``facets.decode_soup``): 0x41/0x42/0x49/0x4a
  decode as strips and 0x4c as rings, so 0x41/0x49 faces join the
  partition as triangles whose primitive reading is still the G3 F10
  candidate (their ``n == 3*type`` reading is established, the
  multi-loop semantics are not). Markers outside that family (0x44/
  0x4b/0x4e, G3 F9) carry no triangles and cannot join a shell — a
  boundary of this decode, not a property of the file.

Detector honesty (what the partition does NOT discriminate — each edge
has a committed synthetic negative in ``tests/test_brep_shell.py`` and
``scripts/triage/decode_brep_shell.py --selftest``):

- **Closed ≠ oriented.** The closure law counts edges, not winding: a
  closed component whose faces are wound inconsistently is still a
  shell (``oriented`` False). Negative: the inward-wound tetrahedron.
- **Shell ≠ B-rep shell.** Any closed tessellation of a curved surface
  produces a closed component; the decode establishes the partition of
  the DECODED TRIANGLES, never the underlying B-rep faces or surfaces
  (BR2's TOP-04/SRF-01 honesty lines stand unchanged). Negative: a
  closed octahedron (a tessellated sphere cap has the same signature).
- **Adjacency ≠ shared edge.** Two faces touching at a vertex only, or
  lying in each other's plane without sharing an edge, are separate
  components — components are edge-connected, not proximity-connected.
  Negative: two tetrahedra sharing one vertex.
- **Role ≠ geometry.** No byte marks an outer shell vs a cavity shell;
  the signed volume of a closed oriented component is reported as a
  measurement (positive = outward-wound by the right-hand rule), not as
  a role label. Negative: the reversed tetrahedron (negative volume).
"""

from __future__ import annotations

import dataclasses
from collections import Counter

from catpart.geometry.facets import (
    SOUP_MARKERS,
    FacetScan,
    decode_soup,
    lex_rank_map,
)

#: A closed, manifold face set: every undirected triangle edge of the
#: component is used exactly twice (boundary_edge_count == 0).
SHELL_CLOSED = "closed-manifold"
#: A component with at least one boundary edge (used once): a sheet, not
#: a shell (G3 F6's open-shell class).
SHELL_OPEN = "open"
#: A component with an edge used more than twice: not a manifold.
SHELL_NON_MANIFOLD = "non-manifold"

Point3 = tuple[float, float, float]


@dataclasses.dataclass(frozen=True)
class FaceShell:
    """One edge-connected component of faces and its manifold invariants.

    ``face_offsets`` are the component's facet-record offsets (store
    order); ``boundary_edges`` counts edges used exactly once;
    ``max_edge_degree`` is the worst undirected usage. ``oriented`` is
    the G3 F6 winding law at component level (no directed edge is
    traversed twice: each interior edge is used once per direction).
    ``signed_volume`` is ``sum dot(a, cross(b, c)) / 6`` over the
    component's triangles in the exported winding — meaningful as an
    enclosed volume only for a closed+oriented component, where its
    sign is the winding convention (positive = outward), never a role.
    """

    face_offsets: tuple[int, ...]
    triangle_count: int
    edge_count: int
    boundary_edges: int
    max_edge_degree: int
    oriented: bool
    signed_volume: float

    @property
    def manifold(self) -> bool:
        """No undirected edge is used more than twice."""
        return self.max_edge_degree <= 2

    @property
    def closed(self) -> bool:
        """Every undirected edge is used exactly twice."""
        return self.edge_count > 0 and self.boundary_edges == 0 and self.manifold

    @property
    def status(self) -> str:
        if not self.manifold:
            return SHELL_NON_MANIFOLD
        if self.closed:
            return SHELL_CLOSED
        return SHELL_OPEN

    @property
    def is_shell(self) -> bool:
        """The TOP-03 signature: a closed manifold face set."""
        return self.status == SHELL_CLOSED


@dataclasses.dataclass(frozen=True)
class ShellSet:
    """The shell partition of one store's decoded facet records.

    ``faces`` counts every accepted face-candidate record (the G3 soup
    markers); ``unplaced_faces`` are those whose references leave the
    pool (composite index space or a clean-store variant — counted, not
    guessed); ``degenerate_faces`` are placed records whose primitive
    reading yields no non-degenerate triangle; ``placed_faces`` are the
    records that entered a component.
    """

    shells: tuple[FaceShell, ...]
    faces: int
    unplaced_faces: int
    degenerate_faces: int

    @property
    def placed_faces(self) -> int:
        return sum(len(s.face_offsets) for s in self.shells)

    @property
    def closed_shells(self) -> tuple[FaceShell, ...]:
        return tuple(s for s in self.shells if s.is_shell)

    @property
    def all_faces_closed(self) -> bool:
        """True when the partition is complete and every component is a
        shell: no unplaced or degenerate face, no open/non-manifold
        component, at least one component."""
        return (
            self.unplaced_faces == 0
            and self.degenerate_faces == 0
            and bool(self.shells)
            and all(s.is_shell for s in self.shells)
        )



def _record_triangles(pool: list[Point3], lex: list[int], rec) -> tuple[tuple[int, int, int], ...]:
    """One record's triangles under the shipped export reading (G3 F7).

    Reuses :func:`catpart.geometry.facets.decode_soup` on a one-record
    scan so the shell partition is over exactly the triangles the
    exporter emits (degenerate skip included) — no second copy of the
    primitive semantics. The byte-parse loop split is identical to
    :func:`catpart.brep.planar.record_true_loops` for triangle geometry
    (BR2 §3: phantom empty u16 loops consume no references).
    """
    one = FacetScan(candidates=1, records=(rec,), unresolved_candidates=0, skipped_markers={})
    return decode_soup(pool, lex, one).triangles


def _edge_key(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def _dot(a: Point3, b: Point3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Point3, b: Point3) -> Point3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _signed_volume(pool: list[Point3], triangles: list[tuple[int, int, int]]) -> float:
    """``sum dot(a, cross(b, c)) / 6`` — the enclosed volume for a closed
    oriented component, in the exported winding (sign = convention)."""
    total = 0.0
    for i, j, k in triangles:
        total += _dot(pool[i], _cross(pool[j], pool[k]))
    return total / 6.0


def decode_shells(pool: list[Point3], scan: FacetScan) -> ShellSet:
    """Partition a store's decoded faces into shells (TOP-03).

    The pool is the flattened pool in walk order (the G3 soup
    convention) and ``scan`` the store's accepted facet records. Faces
    are the record markers with a pinned primitive reading
    (``SOUP_MARKERS``); each record's triangles come from the shipped
    export reading. Two faces join when they share an undirected
    triangle edge; a component is a shell iff every edge it uses is used
    exactly twice.

    Out-of-pool references are counted as ``unplaced_faces`` and the
    record joins no component (the partition on a composite store is
    empty and the caller must report the store as unverified — this
    function never guesses an index space).
    """
    lex = lex_rank_map(pool)
    n_pool = len(pool)
    placed: list[tuple[int, list[tuple[int, int, int]]]] = []
    faces = 0
    unplaced = 0
    degenerate = 0
    for rec in scan.records:
        if rec.marker not in SOUP_MARKERS:
            continue
        faces += 1
        if any(x >= n_pool for x in rec.refs):
            unplaced += 1
            continue
        triangles = list(_record_triangles(pool, lex, rec))
        if not triangles:
            degenerate += 1
            continue
        placed.append((rec.offset, triangles))

    # Edge-connected face components (union-find, deterministic: the
    # smaller face index is the root).
    parent = list(range(len(placed)))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if ra < rb:
            parent[rb] = ra
        else:
            parent[ra] = rb

    edge_owner: dict[tuple[int, int], int] = {}
    for fi, (_, triangles) in enumerate(placed):
        for tri in triangles:
            for e in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                key = _edge_key(*e)
                owner = edge_owner.get(key)
                if owner is None:
                    edge_owner[key] = fi
                elif owner != fi:
                    union(owner, fi)

    members: dict[int, list[int]] = {}
    for fi in range(len(placed)):
        members.setdefault(find(fi), []).append(fi)

    shells = []
    for root in sorted(members):
        face_indices = members[root]
        triangles = [tri for fi in face_indices for tri in placed[fi][1]]
        edge_use: Counter[tuple[int, int]] = Counter()
        directed_use: Counter[tuple[int, int]] = Counter()
        for tri in triangles:
            for e in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                edge_use[_edge_key(*e)] += 1
                directed_use[e] += 1
        shells.append(
            FaceShell(
                face_offsets=tuple(placed[fi][0] for fi in face_indices),
                triangle_count=len(triangles),
                edge_count=len(edge_use),
                boundary_edges=sum(1 for v in edge_use.values() if v == 1),
                max_edge_degree=max(edge_use.values()),
                oriented=all(v <= 1 for v in directed_use.values()),
                signed_volume=_signed_volume(pool, triangles),
            )
        )
    return ShellSet(
        shells=tuple(shells),
        faces=faces,
        unplaced_faces=unplaced,
        degenerate_faces=degenerate,
    )
