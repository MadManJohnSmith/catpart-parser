"""B-rep topology graph assembler (BR6, Ticket #58, Spec G #47).

Contract: ``docs/agents/br6-graph-design.md`` (the design note is the
interface of record; this module implements it as written). The graph is
the *assembler*: it calls the shipped decoders and never re-derives their
laws —

- ``facets.scan_facets`` for the record walk (with the pool-only
  store-width context ``clean_store=True`` the shell slice ships),
- ``planar.decode_planar_face`` for the normal-bearing face family
  (``planar.PLANAR_NORMAL_MARKERS`` = 0x49/0x4a/0x4c),
- ``planar.record_true_loops`` for loop delimitation (inside the face
  decode; loop segments are the edge source, never triangles),
- ``quadrics.classify_strip_patch`` per strip loop, only to decide
  ``FaceData.surface``,
- ``shell.decode_shells`` for the edge-connected face partition,
- ``cgm_nurbs.top01_carrier`` for the body carrier,
- ``pool.scan_pool_groups`` for vertex coordinates,
- ``pool.has_composite_space`` for the store's index space.

Provenance is mandatory on every node and every arc: five provenance
facts (decoder, construct, claim, labels + the nominated
``export_label``, index_space) plus the honesty axes (scope, unit,
anchor). Claims allowlist against the committed
``docs/evidence/data/br*claims*.csv`` rows — this note's own
``br6-graph-claims.csv`` is excluded, a note cannot justify its own
graph — and the cited row's scope is checked against the node's index
space.

Detector honesty (what this graph does NOT decode — each edge has a
committed synthetic negative in ``tests/test_brep_graph.py`` and the
``--selftest`` roster of ``scripts/triage/decode_brep_graph.py``):

- **Composite index space.** 1,036/1,317 located stores (BR6S-08) number
  their references in an element space this slice does not decode. No
  vertex, edge or shell is materialised there; the graph is
  ``status="unverified"`` with a body and an assumed lump only. The
  element numbering is never remapped onto pool ranks.
- **No shell record.** A shell is a derived partition (BR6S-22b/23 name
  the byte-level negative); it is labelled ``derived``, never a stored
  record.
- **No lump record.** BR5-06a reports the *absence of a detector*
  (``observations=0``) — it says nothing about lump cardinality. "One
  lump per body" is an **assumption** (``export_label="assumed"``) and
  blocks export unless ``StepOptions.accept_assumed_lump`` is set.
- **No first-class edge/vertex identity.** Edges are loop segments of the
  decoded face loops (BR2-15 ring / BR2-16 strip readings), never
  triangle chords; no edge record binds to a face (BR3 §4). Vertices are
  pool slots: no welding, no dedup, topological identity undiscriminated.
- **Face family.** ``FaceData`` exists only for the normal-bearing planar
  family (0x49/0x4a/0x4c). A component carrying a 0x41/0x42 record (no
  12B normal) has no FaceNode for it; the count is
  ``Completeness.excluded_faces`` and the exporter refuses
  ``face-family-unread``.
- **Unread records.** Accepted records outside the face families (0x44,
  0x4b, 0x4e) produce no node: ``Completeness.unknown`` (BR6S-22).
- **Store-wide counts.** ``skipped_refs``/``excluded_loops`` stay 0 here:
  the composite element-space exclusions are BR4 §1's measurement and are
  cited, not re-derived.
"""

from __future__ import annotations

import csv
import dataclasses
import functools
import hashlib
import re
from collections import Counter
from pathlib import Path

from catpart.brep import cgm_nurbs, planar, quadrics
from catpart.brep import shell as shell_decode
from catpart.geometry import facets, pool as pool_decode, store
from catpart.geometry.errors import ExportError

# --------------------------------------------------------------------
# Vocabulary (design §1)
# --------------------------------------------------------------------

INDEX_POOL = "pool"
INDEX_COMPOSITE = "composite-element"
INDEX_NONE = "none"
INDEX_SPACES = (INDEX_POOL, INDEX_COMPOSITE, INDEX_NONE)

NODE_BODY = "body"
NODE_LUMP = "lump"
NODE_SHELL = "shell"
NODE_FACE = "face"
NODE_LOOP = "loop"
NODE_EDGE = "edge"
NODE_VERTEX = "vertex"
NODE_KINDS = (
    NODE_BODY,
    NODE_LUMP,
    NODE_SHELL,
    NODE_FACE,
    NODE_LOOP,
    NODE_EDGE,
    NODE_VERTEX,
)
NODE_KIND_ORDER = {kind: i for i, kind in enumerate(NODE_KINDS)}

ARC_BODY_LUMP = "body-lump"
ARC_LUMP_SHELL = "lump-shell"
ARC_SHELL_FACE = "shell-face"
ARC_FACE_LOOP = "face-loop"
ARC_LOOP_EDGE = "loop-edge"
ARC_EDGE_VERTEX = "edge-vertex"
ARC_KINDS = {
    ARC_BODY_LUMP: (NODE_BODY, NODE_LUMP),
    ARC_LUMP_SHELL: (NODE_LUMP, NODE_SHELL),
    ARC_SHELL_FACE: (NODE_SHELL, NODE_FACE),
    ARC_FACE_LOOP: (NODE_FACE, NODE_LOOP),
    ARC_LOOP_EDGE: (NODE_LOOP, NODE_EDGE),
    ARC_EDGE_VERTEX: (NODE_EDGE, NODE_VERTEX),
}
ARC_KIND_ORDER = {kind: i for i, kind in enumerate(ARC_KINDS)}

#: Every label the graph uses; ``export_label`` must name one of these.
LABELS = (
    "fact",
    "inference",
    "derived",
    "reading",
    "candidate",
    "assumed",
    "unknown",
    "user",
)
#: Labels that are a guess: no-guess refuses them everywhere.
BLOCKING_LABELS = ("unknown",)
#: Assumed facts are declared, not guessed; they block export until the
#: owner accepts them (design §5.6, F4).
ASSUMPTION_LABELS = ("assumed",)

DECODERS = (
    "planar",
    "curves",
    "quadrics",
    "cgm_nurbs",
    "shell",
    "facets",
    "pool",
    "composite",
    "derived",
    "user",
)
UNITS = ("model", "none", "caller-supplied")

STATUS_OK = "ok"
STATUS_UNPLACED = "unplaced"
STATUS_DEGENERATE = "degenerate"
STATUS_UNKNOWN = "unknown"
STATUS_UNSUPPORTED = "unsupported"

STATUS_COMPLETE = "complete"
STATUS_UNVERIFIED = "unverified"
STATUS_LUMP_UNDECODED = "lump-undecoded"

#: Cylinder-loop coherence (design §2): a *reading* threshold, not a
#: surface validation. Axis agreement is a cosine (a length residual
#: cannot compare directions); radius agreement is relative.
CYL_AXIS_COS_MIN = 0.999
CYL_RADIUS_REL_TOL = 1e-2

DATA_DIR = Path(__file__).resolve().parents[3] / "docs" / "evidence" / "data"

#: This note's own claims file cannot justify its nodes (self-reference).
CLAIM_ALLOWLIST_EXCLUDED = ("br6-graph-claims.csv",)

Point3 = tuple[float, float, float]


# --------------------------------------------------------------------
# Records (design §1/§2)
# --------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, order=True)
class NodeId:
    """``NodeId(kind, index)`` — index = store order per kind."""

    kind: str
    index: int


@dataclasses.dataclass(frozen=True)
class Provenance:
    """The five provenance facts plus the honesty axes (design §1.3).

    ``labels`` is every applicable label; ``export_label`` is the one that
    gates export (``assumed``/``unknown`` block). ``scope`` is the cited
    claims row's scope (checked against ``index_space``), ``unit`` the
    coordinate basis, ``anchor`` the byte or store anchor of the reading.
    """

    decoder: str
    construct: str
    claim: str
    labels: tuple[str, ...]
    export_label: str
    index_space: str
    scope: str
    unit: str
    anchor: str
    detail: str = ""


@dataclasses.dataclass(frozen=True)
class Arc:
    """One topology arc; its provenance names the law that made it."""

    kind: str
    parent: NodeId
    child: NodeId
    orientation: bool | None
    provenance: Provenance


@dataclasses.dataclass(frozen=True)
class StoreRef:
    """The byte extent a graph describes (``sha256`` of the whole file)."""

    local_path: str
    container: str
    body_lo: int
    body_hi: int
    sha256: str | None = None


@dataclasses.dataclass(frozen=True)
class GraphPolicy:
    """The three permitted derivations (design §2)."""

    # False -> status "lump-undecoded", no lump and no shell subtree.
    derive_single_lump: bool = True
    # False -> only closed components become ShellNodes.
    include_open_shells: bool = True
    # False -> FaceData.surface is never assigned.
    coherent_face_surface: bool = True


@dataclasses.dataclass(frozen=True)
class SurfaceReading:
    """The whole supported surface set (PLANE, CYLINDRICAL_SURFACE).

    Both are ``candidate`` readings: a planar patch can be a curved
    surface's tessellation (SRF-01) and a torus band is a valid cylinder
    at either equator (SRF-05's upper bound). No cone/sphere/pencil fit
    ever becomes a face surface (BR4 §4: no face-level grouping).
    """

    entity: str
    label: str
    claim: str
    normal: Point3 | None = None
    offset: float | None = None
    axis: Point3 | None = None
    axis_point: Point3 | None = None
    radius: float | None = None
    detail: str = ""


@dataclasses.dataclass(frozen=True)
class BodyData:
    seebody_block: bool
    store_root: str | None


@dataclasses.dataclass(frozen=True)
class LumpData:
    basis: str


@dataclasses.dataclass(frozen=True)
class ShellData:
    """A copy of the shell slice's ``FaceShell`` (never re-walked)."""

    status: str
    face_offsets: tuple[int, ...]
    triangle_count: int
    edge_count: int
    boundary_edges: int
    max_edge_degree: int
    oriented: bool
    signed_volume: float


@dataclasses.dataclass(frozen=True)
class FaceData:
    record_offset: int
    marker: int
    loop_count: int
    triangles: tuple[tuple[int, int, int], ...]
    surface: SurfaceReading | None
    surface_labels: tuple[str, ...]
    surface_disagreement: bool
    count_variant: bool
    oriented: bool | None


@dataclasses.dataclass(frozen=True)
class LoopData:
    face: NodeId
    length: int
    kind: str
    closed_cycle: bool | None
    degenerate: bool


@dataclasses.dataclass(frozen=True)
class EdgeData:
    start: int
    end: int


@dataclasses.dataclass(frozen=True)
class VertexData:
    rank: int
    position: Point3


NodeData = BodyData | LumpData | ShellData | FaceData | LoopData | EdgeData | VertexData


@dataclasses.dataclass(frozen=True)
class Node:
    id: NodeId
    provenance: Provenance
    data: NodeData
    status: str


@dataclasses.dataclass(frozen=True)
class Completeness:
    """Counts only — rates live in the claims CSV (design §2)."""

    body: int
    lump: int
    shell: int
    shell_closed: int
    face: int
    face_placed: int
    face_unplaced: int
    loop: int
    edge: int
    vertex: int
    unknown: int
    skipped_refs: int
    excluded_loops: int
    excluded_shells: int = 0
    excluded_faces: int = 0


@dataclasses.dataclass(frozen=True)
class Violation:
    """A named invariant failure (design §5). Never raised by checks."""

    code: str
    node: NodeId | None
    detail: str
    arc: int | None = None


@dataclasses.dataclass(frozen=True)
class BodyGraph:
    nodes: tuple[Node, ...]
    arcs: tuple[Arc, ...]
    store: StoreRef
    policy: GraphPolicy
    completeness: Completeness
    annotations: tuple[str, ...]
    status: str
    #: "pool"|"composite-element"|"none" — the store's reference space.
    #: Never inherited by a node: every node carries its own axis.
    index_space: str = INDEX_NONE


# --------------------------------------------------------------------
# Claim allowlist (design §5.4)
# --------------------------------------------------------------------

_UNIT_TOKEN_RE = re.compile(r"(?<![a-z])(mm|cm|inch|metres?|meters?)(?![a-z])")


def _unit_named(text: str) -> str:
    """The unit token a claims row names, or ``""``."""
    match = _UNIT_TOKEN_RE.search(text.lower())
    return match.group(1) if match else ""


def scope_conflict(scope: str, index_space: str, unit: str, *, statement: str = "") -> str:
    """The problem with citing a row of ``scope`` for these node axes.

    A row measured on composite stores cannot justify a pool-space node
    (and the converse), and a row naming a unit cannot justify a node
    whose geometry is in model units. Index-space-neutral scopes pass.
    """
    low = scope.lower()
    if index_space == INDEX_POOL and "composite" in low:
        return f"cited row scope {scope!r} names composite space; node is {INDEX_POOL}"
    if index_space == INDEX_COMPOSITE and "pool" in low:
        return f"cited row scope {scope!r} names pool space; node is {INDEX_COMPOSITE}"
    named = _unit_named(scope + " " + statement)
    if named and named not in unit.lower():
        return f"cited row names unit {named!r}; node unit is {unit!r}"
    return ""


@functools.lru_cache(maxsize=1)
def committed_claims() -> dict[str, tuple[tuple[str, str], ...]]:
    """``claim id -> ((scope, statement), ...)`` from committed claims CSVs.

    ``br6-graph-claims.csv`` is excluded: this note's own rows describe
    the graph, so citing them as a node basis would be self-referential.
    A missing/unreadable data directory yields an empty allowlist —
    fail-closed.
    """
    out: dict[str, list[tuple[str, str]]] = {}
    try:
        paths = sorted(DATA_DIR.glob("br*claims.csv"))
    except OSError:
        return {}
    for path in paths:
        if path.name in CLAIM_ALLOWLIST_EXCLUDED:
            continue
        try:
            with path.open(newline="", encoding="utf-8") as fh:
                rows = list(csv.reader(fh))
        except OSError:
            continue
        if not rows:
            continue
        header = rows[0]

        def column(name: str) -> int:
            try:
                return header.index(name)
            except ValueError:
                return -1

        claim_col = column("claim") if column("claim") >= 0 else 0
        scope_col = column("scope")
        statement_col = column("statement")

        def field(row: list[str], col: int) -> str:
            return row[col] if 0 <= col < len(row) else ""

        for row in rows[1:]:
            claim = field(row, claim_col)
            if not claim:
                continue
            out.setdefault(claim, []).append(
                (field(row, scope_col), field(row, statement_col))
            )
    return {claim: tuple(rows) for claim, rows in out.items()}


@functools.lru_cache(maxsize=None)
def claim_rows(claim: str) -> tuple[tuple[str, str], ...]:
    """Rows whose committed claim id is ``claim`` or ``claim + "_*"``."""
    table = committed_claims()
    if claim in table:
        return table[claim]
    out: list[tuple[str, str]] = []
    prefix = claim + "_"
    for key in sorted(table):
        if key.startswith(prefix):
            out.extend(table[key])
    return tuple(out)


def _claim_scope(claim: str, index_space: str, unit: str) -> str:
    """The first committed row scope compatible with the node's axes."""
    rows = claim_rows(claim)
    for scope, statement in rows:
        if not scope_conflict(scope, index_space, unit, statement=statement):
            return scope
    return rows[0][0] if rows else ""


def _prov(
    decoder: str,
    construct: str,
    claim: str,
    labels: tuple[str, ...],
    export_label: str,
    index_space: str,
    unit: str,
    anchor: str,
    detail: str,
) -> Provenance:
    return Provenance(
        decoder=decoder,
        construct=construct,
        claim=claim,
        labels=labels,
        export_label=export_label,
        index_space=index_space,
        scope=_claim_scope(claim, index_space, unit),
        unit=unit,
        anchor=anchor,
        detail=detail,
    )


# --------------------------------------------------------------------
# Surface coherence (design §2)
# --------------------------------------------------------------------


def _unit_normal(normal: Point3) -> bool:
    return abs(planar.normal_unit_deviation(normal)) <= planar.UNIT_NORM_TOL


def _surface_for_face(
    decoded: planar.DecodedPlanarFace,
    rec: facets.FacetRecord,
    by_rank: list[Point3],
) -> tuple[SurfaceReading | None, tuple[str, ...], bool]:
    """The face surface under the coherence rule (design §2).

    Returns ``(surface, per_loop_labels, disagreement)``. Rings are read
    by the record plane only: ``classify_strip_patch`` is a strip law and
    labels a ring's refs ``degenerate`` (3 refs) or ``pencil-noncyl``
    (4+) by construction (F2). Strips are read loop by loop; a
    cone/sphere/pencil fit never becomes a face surface (BR4 §4).
    """
    plane_ok = (
        decoded.plane is not None
        and decoded.plane.coplanar
        and decoded.normal is not None
        and _unit_normal(decoded.normal)
    )
    if rec.marker in facets.POLY_MARKERS:
        if plane_ok:
            return (
                SurfaceReading(
                    entity="PLANE",
                    label="candidate",
                    claim="BR2-10",
                    normal=decoded.plane.normal,
                    offset=decoded.plane.offset,
                    detail=(
                        "ring loop; record plane passes (BR2-10), offset d is "
                        "derived; a planar tessellation patch of a curved "
                        "surface is not excluded (SRF-01)"
                    ),
                ),
                (),
                False,
            )
        return None, (), False

    fits = [
        quadrics.classify_strip_patch(list(loop), by_rank) for loop in decoded.loops
    ]
    labels = tuple(fit.label for fit in fits)
    if not fits:
        return None, labels, False
    if all(label in ("planar", "degenerate") for label in labels):
        if plane_ok:
            return (
                SurfaceReading(
                    entity="PLANE",
                    label="candidate",
                    claim="BR2-10",
                    normal=decoded.plane.normal,
                    offset=decoded.plane.offset,
                    detail=(
                        "every loop fits planar (SRF-01) and the record plane "
                        "passes (BR2-10); planar patch of a curved surface "
                        "not excluded"
                    ),
                ),
                labels,
                False,
            )
        return None, labels, False
    if all(label == "cylinder" for label in labels):
        axes = [fit.axis for fit in fits]
        radii = [fit.radius for fit in fits]
        first_axis, first_radius = axes[0], radii[0]
        if first_axis is None or first_radius is None:
            return None, labels, True
        axes_agree = all(
            axis is not None
            and abs(sum(a * b for a, b in zip(axis, first_axis))) >= CYL_AXIS_COS_MIN
            for axis in axes
        )
        radii_agree = all(
            radius is not None
            and abs(radius - first_radius)
            <= CYL_RADIUS_REL_TOL * max(first_radius, 1e-9)
            for radius in radii
        )
        if not (axes_agree and radii_agree):
            return None, labels, True
        points = [by_rank[rank] for loop in decoded.loops for rank in loop]
        fit = quadrics.fit_cylinder(points, first_axis)
        if fit is None:
            return None, labels, True
        return (
            SurfaceReading(
                entity="CYLINDRICAL_SURFACE",
                label="candidate",
                claim="SRF-02",
                axis=first_axis,
                axis_point=fit[0],
                radius=first_radius,
                detail=(
                    "every loop fits one cylinder (SRF-02); the axis point is "
                    "the fit's perpendicular foot whose axial component is "
                    "unconstrained (BR4 §2.2); a torus equator band is not "
                    "excluded (SRF-05)"
                ),
            ),
            labels,
            False,
        )
    return None, labels, len(set(labels)) > 1


# --------------------------------------------------------------------
# Node provenance (design §1 table, one construction site each)
# --------------------------------------------------------------------


def _shell_prov(shell: shell_decode.FaceShell) -> Provenance:
    claim = {
        shell_decode.SHELL_CLOSED: "BR6S-13",
        shell_decode.SHELL_OPEN: "BR6S-14",
        shell_decode.SHELL_NON_MANIFOLD: "BR6S-15",
    }[shell.status]
    return _prov(
        "shell",
        "TOP-03",
        claim,
        ("derived",),
        "derived",
        INDEX_POOL,
        "none",
        "store",
        "edge-connected face partition, closure by the twice-used-edge law "
        "(no stored shell record: BR6S-22b/23)",
    )


def _body_prov() -> Provenance:
    return _prov(
        "cgm_nurbs",
        "TOP-01",
        "BR5-04a",
        ("inference",),
        "inference",
        INDEX_NONE,
        "none",
        "store",
        "container/root structure, not body semantics (BR5 §4; BR5-04b "
        "store root); exactly one body per located store is an assumption "
        "(BR5-04a/b count no bodies)",
    )


def _lump_prov() -> Provenance:
    return _prov(
        "derived",
        "TOP-02",
        "BR5-06a",
        ("assumed",),
        "assumed",
        INDEX_NONE,
        "none",
        "none",
        "one lump per body is an ASSUMPTION: BR5-06a reports no lump "
        "detector (observations=0), not lump cardinality; blocks export "
        "unless StepOptions.accept_assumed_lump",
    )


def _lump_arc_prov() -> Provenance:
    return _prov(
        "derived",
        "TOP-02",
        "BR5-06a",
        ("assumed",),
        "assumed",
        INDEX_NONE,
        "none",
        "none",
        "lump grouping follows the assumed single lump per body",
    )


def _face_prov(rec: facets.FacetRecord) -> Provenance:
    return _prov(
        "planar",
        "TOP-04",
        "BR2-01",
        ("fact", "inference"),
        "fact",
        INDEX_POOL,
        "model",
        f"record+0x{rec.offset:x}",
        f"accepted record on marker 0x{rec.marker:02x}; record == face is "
        "an inference (BR2 §5); placed in a component (BR6S-19)",
    )


def _loop_prov(rec: facets.FacetRecord, loop_index: int) -> Provenance:
    return _prov(
        "planar",
        "TOP-05",
        "BR2-07",
        ("fact", "reading"),
        "fact",
        INDEX_POOL,
        "model",
        f"record+0x{rec.offset:x}/loop[{loop_index}]",
        "loop delimitation (BR2-07); closure is a reading (BR2-15 ring / "
        "BR2-16 strip)",
    )


def _vertex_prov(rank: int) -> Provenance:
    return _prov(
        "pool",
        "TOP-07",
        "T07_pool_count_law",
        ("fact", "unknown"),
        "fact",
        INDEX_POOL,
        "model",
        f"pool[rank={rank}]",
        "pool slot coordinate (T07 law); no welding and no dedup — "
        "topological identity/order/duplicates not discriminated (BR3 §4)",
    )


def _edge_prov(lo_rank: int, hi_rank: int) -> Provenance:
    return _prov(
        "derived",
        "TOP-06",
        "BR6S-13",
        ("derived",),
        "derived",
        INDEX_POOL,
        "model",
        f"pool[rank={lo_rank}]-pool[rank={hi_rank}]",
        "loop segment between corner slots; never a B-rep curve (BR3 §4) "
        "and never a triangle chord; the winding evidence is the loop "
        "reading (BR2-15/16)",
    )


# --------------------------------------------------------------------
# Assembler (design §2)
# --------------------------------------------------------------------


def _record_triangles(
    flat: list[Point3], lex: list[int], rec: facets.FacetRecord
) -> tuple[tuple[int, int, int], ...]:
    """One record's triangles under the shipped export reading (G3 F7).

    Same one-record ``decode_soup`` call the shell partition makes, so
    facet mode emits exactly the triangles ``shell.decode_shells``
    partitions — no second primitive law.
    """
    one = facets.FacetScan(
        candidates=1,
        records=(rec,),
        unresolved_candidates=0,
        skipped_markers={},
    )
    return tuple(facets.decode_soup(flat, lex, one).triangles)


class _Builder:
    """One store's graph. The only assembler (design §2)."""

    def __init__(self, data, span: store.StoreSpan, policy: GraphPolicy) -> None:
        self.data = data
        self.span = span
        self.policy = policy
        self.nodes: list[Node] = []
        self.arcs: list[Arc] = []
        self.annotations: list[str] = []
        self._next: Counter[str] = Counter()
        self._by_id: dict[NodeId, Provenance] = {}
        self.index_space = INDEX_NONE

    # -- helpers -----------------------------------------------------

    def _add(self, kind: str, provenance: Provenance, data: NodeData, status: str) -> NodeId:
        node_id = NodeId(kind, self._next[kind])
        self._next[kind] += 1
        self._by_id[node_id] = provenance
        self.nodes.append(Node(id=node_id, provenance=provenance, data=data, status=status))
        return node_id

    def _arc(
        self,
        kind: str,
        parent: NodeId,
        child: NodeId,
        provenance: Provenance,
        orientation: bool | None = None,
    ) -> None:
        self.arcs.append(
            Arc(
                kind=kind,
                parent=parent,
                child=child,
                orientation=orientation,
                provenance=provenance,
            )
        )

    # -- store shapes ------------------------------------------------

    def build(self) -> BodyGraph:
        span = self.span
        carrier = cgm_nurbs.top01_carrier(self.data)
        groups, kinds = pool_decode.scan_pool_groups(
            self.data, span.body_lo, span.body_hi
        )
        flat = [vertex for group in groups for vertex in group.vertices]
        composite = pool_decode.has_composite_space(kinds)
        self.index_space = INDEX_COMPOSITE if composite else INDEX_POOL
        scan = facets.scan_facets(
            self.data, span.body_lo, span.body_hi, clean_store=not composite
        )

        body_id = self._add(NODE_BODY, _body_prov(), BodyData(
            seebody_block=carrier.seebody_block,
            store_root=carrier.store_root,
        ), STATUS_OK)

        if not self.policy.derive_single_lump:
            self.annotations.append(
                "lump-undecoded: GraphPolicy.derive_single_lump=False; no lump "
                "node and no shell subtree is attached (BR5-06a)"
            )
            return self._graph(
                Completeness(
                    body=1,
                    lump=0,
                    shell=0,
                    shell_closed=0,
                    face=0,
                    face_placed=0,
                    face_unplaced=0,
                    loop=0,
                    edge=0,
                    vertex=0,
                    unknown=sum(
                        1
                        for rec in scan.records
                        if rec.marker not in facets.SOUP_MARKERS
                    ),
                    skipped_refs=0,
                    excluded_loops=0,
                ),
                STATUS_LUMP_UNDECODED,
            )

        lump_id = self._add(NODE_LUMP, _lump_prov(), LumpData(
            basis="BR5-06a (detector absence, not cardinality)",
        ), STATUS_OK)
        self._arc(ARC_BODY_LUMP, body_id, lump_id, _lump_arc_prov())
        self.annotations.append(
            "lump assumed: one lump per body (BR5-06a is a detector "
            "negative, not a cardinality measurement)"
        )

        if composite:
            return self._composite_graph(scan, lump_id)
        return self._pool_graph(scan, flat, lump_id)

    def _composite_graph(self, scan: facets.FacetScan, lump_id: NodeId) -> BodyGraph:
        faces = sum(1 for rec in scan.records if rec.marker in facets.SOUP_MARKERS)
        unknown = sum(1 for rec in scan.records if rec.marker not in facets.SOUP_MARKERS)
        self.annotations.append(
            f"composite-element space not decoded (BR6S-08/BR6S-23): {faces} "
            "face-candidate record(s) counted unplaced, 0 vertices, 0 shells; "
            "element numbering is never remapped onto pool ranks"
        )
        self.annotations.append(
            "skipped_refs/excluded_loops not measured here: the composite "
            "element-space decode is BR4 §1's claim, not this slice's"
        )
        return self._graph(
            Completeness(
                body=1,
                lump=1,
                shell=0,
                shell_closed=0,
                face=0,
                face_placed=0,
                face_unplaced=faces,
                loop=0,
                edge=0,
                vertex=0,
                unknown=unknown,
                skipped_refs=0,
                excluded_loops=0,
            ),
            STATUS_UNVERIFIED,
        )

    def _pool_graph(
        self, scan: facets.FacetScan, flat: list[Point3], lump_id: NodeId
    ) -> BodyGraph:
        lex = facets.lex_rank_map(flat)
        by_rank = [flat[walk] for walk in lex]
        shells = shell_decode.decode_shells(flat, scan)
        by_offset = {rec.offset: rec for rec in scan.records}
        excluded_faces = 0
        excluded_shells = 0
        face_frames: list[
            tuple[NodeId, planar.DecodedPlanarFace, facets.FacetRecord, list[NodeId], list[tuple[int, ...]]]
        ] = []

        for shell in shells.shells:
            if not self.policy.include_open_shells and not shell.is_shell:
                excluded_shells += 1
                self.annotations.append(
                    f"policy include_open_shells=False: the {shell.status} "
                    f"component's {len(shell.face_offsets)} face(s) are excluded "
                    "(excluded_shells, not excluded_faces)"
                )
                continue
            shell_id = self._add(
                NODE_SHELL,
                _shell_prov(shell),
                ShellData(
                    status=shell.status,
                    face_offsets=shell.face_offsets,
                    triangle_count=shell.triangle_count,
                    edge_count=shell.edge_count,
                    boundary_edges=shell.boundary_edges,
                    max_edge_degree=shell.max_edge_degree,
                    oriented=shell.oriented,
                    signed_volume=shell.signed_volume,
                ),
                STATUS_OK if shell.is_shell else STATUS_UNSUPPORTED,
            )
            self._arc(
                ARC_LUMP_SHELL,
                lump_id,
                shell_id,
                _prov(
                    "shell",
                    "TOP-03",
                    "BR6S-13" if shell.is_shell else (
                        "BR6S-14" if shell.status == shell_decode.SHELL_OPEN else "BR6S-15"
                    ),
                    ("derived",),
                    "derived",
                    INDEX_POOL,
                    "none",
                    "store",
                    "shell membership follows the assumed single lump and the "
                    "edge-connected face partition",
                ),
            )
            for offset in shell.face_offsets:
                rec = by_offset.get(offset)
                if rec is None or rec.marker not in planar.PLANAR_NORMAL_MARKERS:
                    excluded_faces += 1
                    continue
                decoded = planar.decode_planar_face(flat, lex, rec)
                face_data = self._face_data(decoded, rec, flat, lex, by_rank)
                count_variant = decoded.status in (
                    planar.FACE_COUNT_VARIANT,
                    planar.FACE_NO_LOOPS,
                )
                face_id = self._add(
                    NODE_FACE,
                    _face_prov(rec),
                    face_data,
                    STATUS_UNSUPPORTED
                    if count_variant or face_data.surface is None
                    else STATUS_OK,
                )
                self._arc(
                    ARC_SHELL_FACE,
                    shell_id,
                    face_id,
                    _prov(
                        "shell",
                        "TOP-03",
                        "BR6S-13" if shell.is_shell else (
                            "BR6S-14" if shell.status == shell_decode.SHELL_OPEN else "BR6S-15"
                        ),
                        ("derived",),
                        "derived",
                        INDEX_POOL,
                        "none",
                        f"face_offset=0x{offset:x}",
                        "shell-face membership from the edge-connected face "
                        "partition (shared triangle edges); the arc cites the "
                        "partition law, not the child",
                    ),
                )
                loop_ids: list[NodeId] = []
                if not count_variant:
                    for loop_index, reading in enumerate(decoded.loop_readings):
                        loop_ids.append(
                            self._add(
                                NODE_LOOP,
                                _loop_prov(rec, loop_index),
                                LoopData(
                                    face=face_id,
                                    length=reading.length,
                                    kind=reading.kind,
                                    closed_cycle=reading.closed_cycle,
                                    degenerate=reading.degenerate,
                                ),
                                STATUS_DEGENERATE if reading.degenerate else STATUS_OK,
                            )
                        )
                        self._arc(
                            ARC_FACE_LOOP,
                            face_id,
                            loop_ids[-1],
                            _loop_prov(rec, loop_index),
                        )
                face_frames.append((face_id, decoded, rec, loop_ids, list(decoded.loops)))

        self._edges(face_frames, flat, lex)

        unknown = sum(
            1 for rec in scan.records if rec.marker not in facets.SOUP_MARKERS
        )
        if excluded_faces:
            self.annotations.append(
                f"face-family-unread: {excluded_faces} record(s) inside a "
                "component carry a marker with no FaceNode producer "
                "(0x41/0x42, no 12B normal); the component is not exportable"
            )
        if shells.unplaced_faces:
            self.annotations.append(
                f"{shells.unplaced_faces} face record(s) leave the pool "
                "(BR6S-20); counted, never placed or remapped"
            )
        if shells.degenerate_faces:
            self.annotations.append(
                f"{shells.degenerate_faces} face record(s) decode no "
                "non-degenerate triangle (BR6S-21); no component"
            )
        if unknown:
            self.annotations.append(
                f"{unknown} accepted record(s) outside the face families "
                "(BR6S-22); counted as unknown, no node"
            )
        if scan.unresolved_candidates:
            self.annotations.append(
                f"{scan.unresolved_candidates} facet header candidate(s) "
                "unparsed (outside the tiling law); not faces"
            )

        complete = (
            shells.all_faces_closed
            and unknown == 0
            and excluded_faces == 0
            and excluded_shells == 0
        )
        completeness = Completeness(
            body=1,
            lump=1,
            shell=sum(1 for n in self.nodes if n.id.kind == NODE_SHELL),
            shell_closed=len(shells.closed_shells),
            face=sum(1 for n in self.nodes if n.id.kind == NODE_FACE),
            face_placed=sum(1 for n in self.nodes if n.id.kind == NODE_FACE),
            face_unplaced=shells.unplaced_faces + shells.degenerate_faces,
            loop=sum(1 for n in self.nodes if n.id.kind == NODE_LOOP),
            edge=sum(1 for n in self.nodes if n.id.kind == NODE_EDGE),
            vertex=sum(1 for n in self.nodes if n.id.kind == NODE_VERTEX),
            unknown=unknown,
            skipped_refs=0,
            excluded_loops=0,
            excluded_shells=excluded_shells,
            excluded_faces=excluded_faces,
        )
        return self._graph(
            completeness, STATUS_COMPLETE if complete else STATUS_UNVERIFIED
        )

    def _face_data(
        self,
        decoded: planar.DecodedPlanarFace,
        rec: facets.FacetRecord,
        flat: list[Point3],
        lex: list[int],
        by_rank: list[Point3],
    ) -> FaceData:
        count_variant = decoded.status in (
            planar.FACE_COUNT_VARIANT,
            planar.FACE_NO_LOOPS,
        )
        if not self.policy.coherent_face_surface:
            surface, labels, disagreement = None, (), False
        elif count_variant:
            surface, labels, disagreement = None, (), False
            self.annotations.append(
                f"face-count-variant at record+0x{rec.offset:x}: loop "
                "delimitation not established (BR2-07d); no loop nodes"
            )
        else:
            surface, labels, disagreement = _surface_for_face(decoded, rec, by_rank)
            if surface is None and disagreement:
                self.annotations.append(
                    f"surface-disagreement: face at record+0x{rec.offset:x} "
                    f"loops fit {list(labels)} (BR4 §4)"
                )
        return FaceData(
            record_offset=rec.offset,
            marker=rec.marker,
            loop_count=rec.type,
            triangles=_record_triangles(flat, lex, rec),
            surface=surface,
            surface_labels=labels,
            surface_disagreement=disagreement,
            count_variant=count_variant,
            oriented=decoded.oriented,
        )

    def _edges(
        self,
        face_frames: list[
            tuple[NodeId, planar.DecodedPlanarFace, facets.FacetRecord, list[NodeId], list[tuple[int, ...]]]
        ],
        flat: list[Point3],
        lex: list[int],
    ) -> None:
        """Edges from face loop segments; never from triangles (F7)."""
        rank_pairs: set[tuple[int, int]] = set()
        loop_segments: list[tuple[NodeId, list[tuple[tuple[int, int], tuple[int, int]]]]] = []
        for _face_id, decoded, _rec, loop_ids, loops in face_frames:
            for loop_id, loop, reading in zip(loop_ids, loops, decoded.loop_readings):
                if reading.degenerate or len(loop) < 2:
                    continue
                if reading.closed_cycle:
                    pairs = [(loop[i], loop[(i + 1) % len(loop)]) for i in range(len(loop))]
                else:
                    pairs = [(loop[i], loop[i + 1]) for i in range(len(loop) - 1)]
                pairs = [(a, b) for a, b in pairs if a != b]
                segments = [(a, b) if a < b else (b, a) for a, b in pairs]
                rank_pairs.update(segments)
                loop_segments.append((loop_id, list(zip(pairs, segments))))

        if not rank_pairs:
            return
        ranks = sorted({rank for pair in rank_pairs for rank in pair})
        vertex_index = {rank: i for i, rank in enumerate(ranks)}
        for rank in ranks:
            self._add(
                NODE_VERTEX,
                _vertex_prov(rank),
                VertexData(rank=rank, position=flat[lex[rank]]),
                STATUS_OK,
            )
        ordered_pairs = sorted(rank_pairs)
        edge_index = {pair: i for i, pair in enumerate(ordered_pairs)}
        for pair in ordered_pairs:
            edge_id = self._add(
                NODE_EDGE,
                _edge_prov(pair[0], pair[1]),
                EdgeData(
                    start=vertex_index[pair[0]],
                    end=vertex_index[pair[1]],
                ),
                STATUS_OK,
            )
            for vertex_node in (
                NodeId(NODE_VERTEX, vertex_index[pair[0]]),
                NodeId(NODE_VERTEX, vertex_index[pair[1]]),
            ):
                self._arc(
                    ARC_EDGE_VERTEX,
                    edge_id,
                    vertex_node,
                    self._by_id[vertex_node],
                )
        for loop_id, pairs in loop_segments:
            for (a, _b), segment in pairs:
                edge_id = NodeId(NODE_EDGE, edge_index[segment])
                self._arc(
                    ARC_LOOP_EDGE,
                    loop_id,
                    edge_id,
                    self._by_id[edge_id],
                    orientation=(a == segment[0]),
                )

    # -- output ------------------------------------------------------

    def _graph(self, completeness: Completeness, status: str) -> BodyGraph:
        nodes = tuple(
            sorted(self.nodes, key=lambda n: (NODE_KIND_ORDER[n.id.kind], n.id.index))
        )
        orientation_key = {None: -1, True: 0, False: 1}
        arcs = tuple(
            sorted(
                self.arcs,
                key=lambda a: (
                    ARC_KIND_ORDER[a.kind],
                    a.parent.index,
                    a.child.index,
                    orientation_key[a.orientation],
                ),
            )
        )
        return BodyGraph(
            nodes=nodes,
            arcs=arcs,
            store=StoreRef(
                local_path="",
                container=self.span.container,
                body_lo=self.span.body_lo,
                body_hi=self.span.body_hi,
            ),
            policy=self.policy,
            completeness=completeness,
            annotations=tuple(self.annotations),
            status=status,
            index_space=self.index_space,
        )


def build_store_graph(
    data, span: store.StoreSpan, *, policy: GraphPolicy = GraphPolicy()
) -> BodyGraph:
    """Assemble one store's topology graph (the only assembler).

    Incomplete input degrades to ``status="unverified"`` with the reason
    recorded in ``annotations``. A shipped decoder's ``ExportError``
    (``malformed-pool-*``, ``malformed-store-header``) propagates
    unchanged: this function does not wrap or rename upstream failures.
    """
    return _Builder(data, span, policy).build()


def _locate_store(data) -> store.StoreSpan | None:
    """The exporter's probe order (export.py stage-3a/12).

    ``stdcont`` -> ``xdoclink`` -> ``seebody`` -> every remaining valid
    block (``other-container``). A malformed header is skipped while
    probing (a later family can still locate a store) but resurfaces as
    the named error when no store is found — the exporter's own
    ``first_error`` rule.
    """
    size = len(data)
    d8_outer = int.from_bytes(data[8:12], "big") if size >= 12 else 0
    blocks = store.valid_blocks(data)
    families = (
        (store.CONTAINER_STDCONT, "CATStdCont"),
        (store.CONTAINER_XDOCLINK, "CATXDocLinkCont"),
        (store.CONTAINER_SEEBODY, "CATSeeBodyCont"),
        (store.CONTAINER_OTHER, None),
    )
    first_error: ExportError | None = None
    for tag, name in families:
        if name is None:
            cands = [blk for blk, _ in blocks]
        else:
            cands = [blk for blk, nm in blocks if nm == name]
        for blk in cands:
            try:
                span = store.locate_store(data, blk, blocks, d8_outer, container=tag)
            except ExportError as exc:
                if first_error is None:
                    first_error = exc
                continue
            if span is not None:
                return span
    if first_error is not None:
        raise first_error
    return None


def build_part_graph(
    path, *, policy: GraphPolicy = GraphPolicy()
) -> BodyGraph:
    """Locate a part's store (the exporter's probe order) and assemble it.

    A part with no validated store yields a body-less graph with
    ``status="unverified"`` — the 125-of-1,442 no-store population is a
    measurement, not an error.
    """
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ExportError("unreadable-file", f"{path}: {exc}") from exc
    digest = hashlib.sha256(data).hexdigest()
    span = _locate_store(data)
    if span is None:
        return BodyGraph(
            nodes=(),
            arcs=(),
            store=StoreRef(
                local_path=str(path), container="", body_lo=0, body_hi=0, sha256=digest
            ),
            policy=policy,
            completeness=Completeness(
                body=0,
                lump=0,
                shell=0,
                shell_closed=0,
                face=0,
                face_placed=0,
                face_unplaced=0,
                loop=0,
                edge=0,
                vertex=0,
                unknown=0,
                skipped_refs=0,
                excluded_loops=0,
            ),
            annotations=(
                "no validated nested store in any probe family (the "
                "exporter's order); no body, status unverified",
            ),
            status=STATUS_UNVERIFIED,
            index_space=INDEX_NONE,
        )
    graph = build_store_graph(data, span, policy=policy)
    return dataclasses.replace(
        graph,
        store=dataclasses.replace(
            graph.store, local_path=str(path), sha256=digest
        ),
    )


# --------------------------------------------------------------------
# Invariants (design §5)
# --------------------------------------------------------------------


def _provenance_problem(prov: Provenance) -> str:
    if prov.decoder not in DECODERS:
        return f"decoder {prov.decoder!r} outside {DECODERS}"
    if not prov.construct:
        return "construct is empty"
    if not prov.labels:
        return "labels is empty"
    if prov.export_label not in LABELS:
        return f"export_label {prov.export_label!r} outside {LABELS}"
    if prov.export_label not in prov.labels:
        return f"export_label {prov.export_label!r} not in labels {prov.labels}"
    if prov.index_space not in INDEX_SPACES:
        return f"index_space {prov.index_space!r} outside {INDEX_SPACES}"
    if prov.unit not in UNITS:
        return f"unit {prov.unit!r} outside {UNITS}"
    if not prov.claim:
        return "claim is empty"
    rows = claim_rows(prov.claim)
    if not rows:
        return f"claim {prov.claim!r} is not a committed claims row"
    scopes = {scope for scope, _ in rows}
    if prov.scope not in scopes:
        return f"scope {prov.scope!r} is not a row scope of {prov.claim!r}"
    statement = next((stmt for scope, stmt in rows if scope == prov.scope), "")
    conflict = scope_conflict(prov.scope, prov.index_space, prov.unit, statement=statement)
    if conflict:
        return conflict
    if not prov.anchor:
        return "anchor is empty"
    return ""


def _surface_problem(surface: SurfaceReading, index_space: str) -> str:
    if surface.label not in LABELS:
        return f"surface label {surface.label!r} outside {LABELS}"
    rows = claim_rows(surface.claim)
    if not rows:
        return f"surface claim {surface.claim!r} is not a committed claims row"
    for scope, statement in rows:
        if not scope_conflict(scope, index_space, "model", statement=statement):
            return ""
    return f"surface claim {surface.claim!r} scope conflicts with {index_space}"


def check_invariants(graph: BodyGraph) -> tuple[Violation, ...]:
    """Every invariant failure, as a tuple. This function never raises.

    Four are load-bearing tests (edge-use-pair, orientation,
    provenance-complete, no-guess); four are construction guarantees the
    builder is expected to keep (no-orphan, index-space-homogeneous,
    determinism, arc-kind-table). A malformed hand-built graph is
    reported, never raised on.
    """
    violations: list[Violation] = []
    nodes: dict[NodeId, Node] = {}
    for node in graph.nodes:
        if node.id in nodes:
            violations.append(Violation("determinism", node.id, "duplicate node id"))
        nodes[node.id] = node

    # determinism: dense per-kind indices in store order, known kinds only.
    for node in graph.nodes:
        if node.id.kind not in NODE_KIND_ORDER:
            violations.append(
                Violation("determinism", node.id, f"unknown node kind {node.id.kind!r}")
            )
    for kind in NODE_KINDS:
        indices = sorted(n.id.index for n in graph.nodes if n.id.kind == kind)
        if len(indices) != len(set(indices)):
            violations.append(
                Violation("determinism", NodeId(kind, indices[0]), "duplicate index")
            )
        if indices and indices != list(range(len(indices))):
            violations.append(
                Violation(
                    "determinism",
                    NodeId(kind, indices[0]),
                    f"indices are not 0..n-1 in store order: {indices}",
                )
            )

    # arc maps: children and loop-edge arcs, one pass.
    children_of: dict[tuple[str, NodeId], list[NodeId]] = {}
    loop_edge_arcs: dict[NodeId, list[tuple[int, Arc]]] = {}
    for arc_index, arc in enumerate(graph.arcs):
        children_of.setdefault((arc.kind, arc.parent), []).append(arc.child)
        if arc.kind == ARC_LOOP_EDGE:
            loop_edge_arcs.setdefault(arc.parent, []).append((arc_index, arc))

    def children(parent: NodeId, kind: str) -> list[NodeId]:
        return children_of.get((kind, parent), [])

    # arc-kind-table: kinds follow §1 and the graph is acyclic.
    for arc_index, arc in enumerate(graph.arcs):
        table = ARC_KINDS.get(arc.kind)
        if table is None:
            violations.append(
                Violation("arc-kind-table", None, f"unknown arc kind {arc.kind!r}", arc_index)
            )
            continue
        parent = nodes.get(arc.parent)
        child = nodes.get(arc.child)
        if parent is None:
            violations.append(
                Violation("arc-kind-table", arc.parent, "arc parent is not a node", arc_index)
            )
        elif parent.id.kind != table[0]:
            violations.append(
                Violation(
                    "arc-kind-table",
                    parent.id,
                    f"arc {arc.kind!r} parent kind {parent.id.kind!r} != {table[0]!r}",
                    arc_index,
                )
            )
        if child is None:
            violations.append(
                Violation("arc-kind-table", arc.child, "arc child is not a node", arc_index)
            )
        elif child.id.kind != table[1]:
            violations.append(
                Violation(
                    "arc-kind-table",
                    child.id,
                    f"arc {arc.kind!r} child kind {child.id.kind!r} != {table[1]!r}",
                    arc_index,
                )
            )

    state: dict[NodeId, int] = {}
    for start in nodes:
        if state.get(start, 0) == 2:
            continue
        stack: list[tuple[NodeId, int]] = [(start, 0)]
        state[start] = 1
        while stack:
            node_id, position = stack[-1]
            kids = children_of.get((ARC_BODY_LUMP, node_id), []) + children_of.get(
                (ARC_LUMP_SHELL, node_id), []
            ) + children_of.get((ARC_SHELL_FACE, node_id), []) + children_of.get(
                (ARC_FACE_LOOP, node_id), []
            ) + children_of.get((ARC_LOOP_EDGE, node_id), []) + children_of.get(
                (ARC_EDGE_VERTEX, node_id), []
            )
            if position < len(kids):
                stack[-1] = (node_id, position + 1)
                child = kids[position]
                if state.get(child, 0) == 1:
                    violations.append(
                        Violation("arc-kind-table", child, "graph contains a cycle")
                    )
                elif state.get(child, 0) == 0:
                    state[child] = 1
                    stack.append((child, 0))
            else:
                state[node_id] = 2
                stack.pop()

    # no-orphan: every non-body node reachable from a body; loops have a
    # face use, edges a loop use, vertices an edge.
    reachable: set[NodeId] = set()
    queue = [n.id for n in graph.nodes if n.id.kind == NODE_BODY]
    reachable.update(queue)
    while queue:
        current = queue.pop()
        for kind in ARC_KINDS:
            if ARC_KINDS[kind][0] != current.kind:
                continue
            for child in children(current, kind):
                if child not in reachable:
                    reachable.add(child)
                    queue.append(child)
    for node in graph.nodes:
        if node.id.kind != NODE_BODY and node.id not in reachable:
            violations.append(Violation("no-orphan", node.id, "not reachable from a body"))
    used_loops = {a.child for a in graph.arcs if a.kind == ARC_FACE_LOOP}
    used_edges = {a.child for a in graph.arcs if a.kind == ARC_LOOP_EDGE}
    used_vertices = {a.child for a in graph.arcs if a.kind == ARC_EDGE_VERTEX}
    for node in graph.nodes:
        if node.id.kind == NODE_LOOP and node.id not in used_loops:
            violations.append(Violation("no-orphan", node.id, "loop has no face use"))
        if node.id.kind == NODE_EDGE and node.id not in used_edges:
            violations.append(Violation("no-orphan", node.id, "edge has no loop use"))
        if node.id.kind == NODE_VERTEX and node.id not in used_vertices:
            violations.append(Violation("no-orphan", node.id, "vertex has no edge"))

    # index-space-homogeneous: one shell's vertices share one space.
    for shell in (n for n in graph.nodes if n.id.kind == NODE_SHELL):
        vertices: set[NodeId] = set()
        for face in children(shell.id, ARC_SHELL_FACE):
            for loop in children(face, ARC_FACE_LOOP):
                for edge in children(loop, ARC_LOOP_EDGE):
                    vertices.update(children(edge, ARC_EDGE_VERTEX))
        spaces = {
            nodes[vertex].provenance.index_space
            for vertex in vertices
            if vertex in nodes
        }
        if len(spaces) > 1:
            violations.append(
                Violation(
                    "index-space-homogeneous",
                    shell.id,
                    f"vertices disagree on index space: {sorted(spaces)}",
                )
            )

    # edge-use-pair + orientation: the loop-segment boundary law (F7).
    for shell in (n for n in graph.nodes if n.id.kind == NODE_SHELL):
        uses: dict[NodeId, list[tuple[int, Arc]]] = {}
        for face in children(shell.id, ARC_SHELL_FACE):
            for loop in children(face, ARC_FACE_LOOP):
                for arc_index, arc in loop_edge_arcs.get(loop, ()):
                    uses.setdefault(arc.child, []).append((arc_index, arc))
        for edge_id, arcs in uses.items():
            if len(arcs) != 2:
                violations.append(
                    Violation(
                        "edge-use-pair",
                        edge_id,
                        f"shell {shell.id} uses the loop segment "
                        f"{len(arcs)} time(s); a B-rep-paired boundary needs "
                        "exactly 2",
                    )
                )
            edge = nodes.get(edge_id)
            if edge is None or not isinstance(edge.data, EdgeData):
                continue
            directed: Counter[tuple[int, int]] = Counter()
            for arc_index, arc in arcs:
                if arc.orientation is None:
                    violations.append(
                        Violation(
                            "orientation",
                            edge_id,
                            "loop-edge arc without an orientation reading",
                            arc_index,
                        )
                    )
                elif arc.orientation:
                    directed[(edge.data.start, edge.data.end)] += 1
                else:
                    directed[(edge.data.end, edge.data.start)] += 1
            for _direction, count in directed.items():
                if count > 1:
                    violations.append(
                        Violation(
                            "orientation",
                            edge_id,
                            f"shell {shell.id} traverses one direction {count} "
                            "times (no directed edge twice)",
                        )
                    )

    # provenance-complete: every node, surface claim and arc.
    for node in graph.nodes:
        problem = _provenance_problem(node.provenance)
        if problem:
            violations.append(Violation("provenance-complete", node.id, problem))
        if isinstance(node.data, FaceData) and node.data.surface is not None:
            problem = _surface_problem(
                node.data.surface, node.provenance.index_space
            )
            if problem:
                violations.append(Violation("provenance-complete", node.id, problem))
    for arc_index, arc in enumerate(graph.arcs):
        problem = _provenance_problem(arc.provenance)
        if problem:
            violations.append(
                Violation("provenance-complete", arc.child, problem, arc_index)
            )

    # no-guess: unknown never ships; derived/assumed need a stated basis.
    for node in graph.nodes:
        prov = node.provenance
        if prov.export_label in BLOCKING_LABELS or node.status == STATUS_UNKNOWN:
            violations.append(
                Violation(
                    "no-guess",
                    node.id,
                    f"export_label {prov.export_label!r} / status "
                    f"{node.status!r} cannot reach a file",
                )
            )
        if prov.export_label in ("derived", "assumed") and not prov.detail:
            violations.append(
                Violation("no-guess", node.id, "derived/assumed node without a basis")
            )

    return tuple(violations)
