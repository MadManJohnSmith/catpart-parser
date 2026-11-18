"""STEP (ISO 10303-21) export of a BR6 topology graph.

Contract: ``docs/agents/br6-graph-design.md`` §4. ``render_step`` returns
text so byte stability and every negative fixture are testable without
the filesystem; ``write_step`` is the only filesystem path.

The emitted subset is pinned (§4.1): ``MANIFOLD_SOLID_BREP``,
``CLOSED_SHELL``, ``ADVANCED_FACE``, ``FACE_OUTER_BOUND``, ``EDGE_LOOP``,
``ORIENTED_EDGE``, ``EDGE_CURVE``, ``LINE``, ``VECTOR``,
``CARTESIAN_POINT``, ``VERTEX_POINT``, ``DIRECTION``,
``AXIS2_PLACEMENT_3D``, ``PLANE``, ``CYLINDRICAL_SURFACE``, the
context/units chain (``GEOMETRIC_REPRESENTATION_CONTEXT(3)``,
``GLOBAL_UNIT_ASSIGNED_CONTEXT``, ``LENGTH_UNIT``, ``SI_UNIT``,
``CONVERSION_BASED_UNIT``, ``UNCERTAINTY_MEASURE_WITH_UNIT``) and
``BREP_WITH_VOIDS`` under §4.4. There is no product structure: the file
is the contract's B-rep subset, never a schema-valid AP214 part. The
first ``FILE_DESCRIPTION`` line names this module's contract and the face
mode so no consumer reads a faceted shell as an exact B-rep.

Face modes (§4.3):

- ``facet`` (the default): one ``ADVANCED_FACE`` per decoded triangle,
  ``PLANE`` through its three points, three-edge loop; the face name
  carries ``derived_from face[k]``. Complete over any closed shell this
  graph can represent — and the only mode with measurable corpus
  coverage.
- ``exact``: one ``ADVANCED_FACE`` per graph face, which requires a
  single closed-cycle loop — in practice a ``0x4c`` ring with ``ty == 1``
  (BR2-15 is a *loop* count, not a face count) — and a PLANE decided from
  the record's stored normal. A ``CYLINDRICAL_SURFACE`` is unreachable in
  this mode (a ring's surface is the record plane), so it is refused as
  ``unsupported-surface``. Expected corpus success: 0/76 closed shells,
  published before the run (design §4.3).

Strictness (§4.6): ``strict=True`` raises
``catpart.geometry.errors.ExportError(error_class, detail)`` on the first
refusal; ``strict=False`` returns a ``StepExport`` with empty text and
the full ``refused`` tuple. Nothing is ever written for a refused graph
(``write_step`` raises in both cases).

Fail-closed units (§4.5): no measured model unit exists (U2 0/108), so
``length_unit=None`` refuses ``unit-undetermined``; a caller-supplied SI
prefix (``MM``/``CM``/``M``) is emitted and annotated as caller-supplied.
"""

from __future__ import annotations

import dataclasses
import hashlib
import math
from collections import Counter
from pathlib import Path

from catpart.brep.graph import (
    ARC_BODY_LUMP,
    ARC_FACE_LOOP,
    ARC_LUMP_SHELL,
    ARC_LOOP_EDGE,
    ARC_SHELL_FACE,
    NODE_BODY,
    NODE_FACE,
    NODE_LUMP,
    NODE_LOOP,
    NODE_SHELL,
    NODE_VERTEX,
    INDEX_COMPOSITE,
    BodyGraph,
    EdgeData,
    FaceData,
    NodeId,
    ShellData,
    SurfaceReading,
    VertexData,
    Violation,
    check_invariants,
)
from catpart.brep.shell import SHELL_CLOSED, SHELL_NON_MANIFOLD, SHELL_OPEN
from catpart.geometry.errors import ExportError

SUPPORTED_ENTITIES = frozenset(
    {
        "MANIFOLD_SOLID_BREP",
        "BREP_WITH_VOIDS",
        "CLOSED_SHELL",
        "ADVANCED_FACE",
        "FACE_OUTER_BOUND",
        "EDGE_LOOP",
        "ORIENTED_EDGE",
        "EDGE_CURVE",
        "LINE",
        "VECTOR",
        "CARTESIAN_POINT",
        "VERTEX_POINT",
        "DIRECTION",
        "AXIS2_PLACEMENT_3D",
        "PLANE",
        "CYLINDRICAL_SURFACE",
        "GEOMETRIC_REPRESENTATION_CONTEXT",
        "GLOBAL_UNIT_ASSIGNED_CONTEXT",
        "LENGTH_UNIT",
        "SI_UNIT",
        "CONVERSION_BASED_UNIT",
        "UNCERTAINTY_MEASURE_WITH_UNIT",
    }
)

#: Export refusal classes (design §4.6). ``CONVERSION_BASED_UNIT`` is
#: supported but only reachable for a non-SI caller unit; the shipped
#: path converts no unit (U2 0/108).
STEP_REFUSAL_CLASSES = frozenset(
    {
        "index-space-unplaceable",
        "face-unplaced",
        "shell-open",
        "shell-non-manifold",
        "shell-not-oriented",
        "shell-not-brep-paired",
        "loop-role-undecided",
        "surface-unbound",
        "unsupported-surface",
        "surface-disagreement",
        "lump-undecoded",
        "lump-assumed",
        "unknown-node",
        "provenance-incomplete",
        "vertex-not-shared",
        "unit-undetermined",
        "shell-role-undecided",
        "body-no-shell",
        "face-count-variant",
        "face-family-unread",
    }
)

#: Graph-structure refusals surfaced from §5's construction guarantees;
#: the export class list does not rename them.
STRUCTURE_REFUSAL_CLASSES = frozenset({"no-orphan", "determinism", "arc-kind-table"})

REFUSAL_CLASSES = STEP_REFUSAL_CLASSES | STRUCTURE_REFUSAL_CLASSES

VIOLATION_REFUSALS = {
    # Both are loop-segment laws (F7): the shell's decoded loop boundary is
    # not a B-rep-paired, consistently-oriented boundary. shell-not-oriented
    # is reserved for the TRIANGLE winding law (ShellData.oriented, BR6S-16).
    "edge-use-pair": "shell-not-brep-paired",
    "orientation": "shell-not-brep-paired",
    "provenance-complete": "provenance-incomplete",
    "index-space-homogeneous": "index-space-unplaceable",
    "no-guess": "unknown-node",
    "no-orphan": "no-orphan",
    "determinism": "determinism",
    "arc-kind-table": "arc-kind-table",
}

#: Strict-raise order: the most specific cause first.
REFUSAL_ORDER = (
    "index-space-unplaceable",
    "lump-undecoded",
    "body-no-shell",
    "unknown-node",
    "provenance-incomplete",
    "face-family-unread",
    "face-count-variant",
    "face-unplaced",
    "shell-open",
    "shell-non-manifold",
    "shell-not-oriented",
    "shell-not-brep-paired",
    "vertex-not-shared",
    "surface-disagreement",
    "surface-unbound",
    "unsupported-surface",
    "loop-role-undecided",
    "shell-role-undecided",
    "lump-assumed",
    "unit-undetermined",
    "no-orphan",
    "determinism",
    "arc-kind-table",
)
_REFUSAL_RANK = {name: i for i, name in enumerate(REFUSAL_ORDER)}

#: Pool coordinates are f32: 9 significant digits round-trip exactly.
POOL_DIGITS = 9
#: Derived values (placements, radii) are doubles: 12 digits, no more.
DERIVED_DIGITS = 12

_UNIT_ENTITIES = {
    "MM": "(.MILLI.,.METRE.)",
    "CM": "(.CENTI.,.METRE.)",
    "M": "($,.METRE.)",
}

_SURFACE_ENTITIES = ("PLANE", "CYLINDRICAL_SURFACE")


@dataclasses.dataclass(frozen=True)
class StepOptions:
    schema: str = "AP214"
    face_mode: str = "facet"
    strict: bool = True
    outer_shell: NodeId | None = None
    length_unit: str | None = None
    accept_assumed_lump: bool = False


@dataclasses.dataclass(frozen=True)
class StepHeader:
    """Caller-supplied ``FILE_NAME`` fields (never the wall clock)."""

    name: str = ""
    time_stamp: str = ""


@dataclasses.dataclass(frozen=True)
class StepExport:
    text: str
    sha256: str
    entity_counts: dict[str, int]
    annotations: tuple[str, ...]
    refused: tuple[Violation, ...]


def _real(value: float, digits: int) -> str:
    """A deterministic STEP real: no ``-0``, always a decimal point.

    ``1`` -> ``1.``, ``1e-7`` -> ``1.E-7``, ``-0.0`` -> ``0.``. ``digits``
    is 9 for pool f32 coordinates and 12 for derived doubles.
    """
    if value == 0.0:
        return "0."
    text = f"{value:.{digits}g}"
    mantissa, separator, exponent = text.partition("e")
    if "." not in mantissa:
        mantissa += "."
    if separator:
        return f"{mantissa}E{int(exponent)}"
    return mantissa


def _normalize(vector: tuple[float, float, float]) -> tuple[float, float, float] | None:
    norm = math.sqrt(sum(component * component for component in vector))
    if norm == 0.0:
        return None
    return tuple(component / norm for component in vector)  # type: ignore[return-value]


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _ref_direction(normal: tuple[float, float, float]) -> tuple[float, float, float]:
    """A deterministic placement X axis perpendicular to ``normal``."""
    axes = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    candidate = min(axes, key=lambda axis: (abs(normal[0] * axis[0] + normal[1] * axis[1] + normal[2] * axis[2]), axis))
    reference = _normalize(_cross(candidate, normal))
    return reference if reference is not None else (1.0, 0.0, 0.0)


class _Writer:
    """Deterministic instance numbering in emission order."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.counts: Counter[str] = Counter()
        self._next = 1

    def add(self, entity_type: str, body: str) -> str:
        reference = f"#{self._next}"
        self._next += 1
        self.lines.append(f"{reference}={body};")
        self.counts[entity_type] += 1
        return reference

    def comment(self, text: str) -> None:
        self.lines.append(f"/* {text} */")


@dataclasses.dataclass
class _ShellTopology:
    """The arc view of one closed shell (looked up once, never re-derived)."""

    faces: list[NodeId]
    loops: dict[NodeId, list[NodeId]]
    loop_edges: dict[NodeId, list[tuple[bool | None, NodeId]]]
    edges: dict[NodeId, tuple[int, int]]  # edge -> (vertex start, vertex end)
    vertices: dict[int, tuple[float, float, float]]  # vertex index -> position
    vertex_of_rank: dict[int, int]


def _topology(graph: BodyGraph, shell: NodeId) -> _ShellTopology:
    nodes = {node.id: node for node in graph.nodes}
    faces = [arc.child for arc in graph.arcs if arc.kind == ARC_SHELL_FACE and arc.parent == shell]
    loops: dict[NodeId, list[NodeId]] = {}
    loop_edges: dict[NodeId, list[tuple[bool | None, NodeId]]] = {}
    edges: dict[NodeId, tuple[int, int]] = {}
    vertices: dict[int, tuple[float, float, float]] = {}
    vertex_of_rank: dict[int, int] = {}
    for face in faces:
        loops[face] = [
            arc.child for arc in graph.arcs if arc.kind == ARC_FACE_LOOP and arc.parent == face
        ]
    for face_loops in loops.values():
        for loop in face_loops:
            loop_edges[loop] = [
                (arc.orientation, arc.child)
                for arc in graph.arcs
                if arc.kind == ARC_LOOP_EDGE and arc.parent == loop
            ]
    wanted_edges = {edge for uses in loop_edges.values() for _orientation, edge in uses}
    for edge in wanted_edges:
        node = nodes.get(edge)
        if node is None or not isinstance(node.data, EdgeData):
            continue
        edges[edge] = (node.data.start, node.data.end)
        for vertex_index in (node.data.start, node.data.end):
            vertex_node = nodes.get(NodeId(NODE_VERTEX, vertex_index))
            if vertex_node is not None and isinstance(vertex_node.data, VertexData):
                vertices[vertex_index] = vertex_node.data.position
                vertex_of_rank[vertex_node.data.rank] = vertex_index
    return _ShellTopology(
        faces=faces,
        loops=loops,
        loop_edges=loop_edges,
        edges=edges,
        vertices=vertices,
        vertex_of_rank=vertex_of_rank,
    )


def _refusals(graph: BodyGraph, options: StepOptions) -> list[Violation]:
    refused: list[Violation] = []

    if graph.index_space == INDEX_COMPOSITE:
        refused.append(
            Violation(
                "index-space-unplaceable",
                None,
                "composite-element space is unplaceable (BR6S-08/BR6S-23); "
                "the element numbering is never remapped onto pool ranks",
            )
        )

    for violation in check_invariants(graph):
        if options.face_mode == "facet" and violation.code in ("edge-use-pair", "orientation"):
            # Loop-segment laws are exact-mode laws; facet mode emits the
            # decoded triangle topology and checks it through the shell's
            # triangle closure (SHELL_CLOSED / ShellData.oriented).
            continue
        refused.append(
            Violation(
                VIOLATION_REFUSALS[violation.code],
                violation.node,
                violation.detail,
                violation.arc,
            )
        )

    if options.length_unit is None:
        refused.append(
            Violation(
                "unit-undetermined",
                None,
                "no model length unit is decoded (U2 0/108); pass "
                "StepOptions(length_unit=...) — never assume one",
            )
        )
    elif options.length_unit.upper() not in _UNIT_ENTITIES:
        refused.append(
            Violation(
                "unit-undetermined",
                None,
                f"unit {options.length_unit!r} has no emitted SI entity; "
                "only MM/CM/M are supported (no conversion is decoded)",
            )
        )

    bodies = [node for node in graph.nodes if node.id.kind == NODE_BODY]
    if not bodies:
        refused.append(
            Violation("body-no-shell", None, "no body node (no validated store)")
        )
    for body in bodies:
        lumps = {
            arc.child
            for arc in graph.arcs
            if arc.kind == ARC_BODY_LUMP and arc.parent == body.id
        }
        has_shell = any(
            arc.kind == ARC_LUMP_SHELL and arc.parent in lumps for arc in graph.arcs
        )
        if not has_shell:
            refused.append(
                Violation(
                    "body-no-shell",
                    body.id,
                    "no shell attached: the store places no closed component "
                    "(BR6S-10/BR6S-12; parent of a shell is a required body)",
                )
            )

    if graph.status == "lump-undecoded":
        refused.append(
            Violation(
                "lump-undecoded",
                None,
                "GraphPolicy.derive_single_lump=False: no lump subtree (BR5-06a)",
            )
        )
    if not options.accept_assumed_lump:
        for node in graph.nodes:
            if node.id.kind == NODE_LUMP and node.provenance.export_label == "assumed":
                refused.append(
                    Violation(
                        "lump-assumed",
                        node.id,
                        "lump cardinality is an assumption (BR5-06a is a "
                        "detector negative); pass accept_assumed_lump=True to "
                        "export it anyway",
                    )
                )

    for node in graph.nodes:
        if node.provenance.export_label == "unknown" or node.status == "unknown":
            refused.append(
                Violation("unknown-node", node.id, "an unknown node never reaches a file")
            )

    if graph.completeness.excluded_faces:
        refused.append(
            Violation(
                "face-family-unread",
                None,
                f"{graph.completeness.excluded_faces} component record(s) carry "
                "a marker with no FaceNode producer (0x41/0x42, no 12B "
                "normal); the shell would be incomplete",
            )
        )

    closed: list[NodeId] = []
    for node in graph.nodes:
        if node.id.kind != NODE_SHELL or not isinstance(node.data, ShellData):
            continue
        shell = node.data
        if shell.status == SHELL_OPEN:
            refused.append(
                Violation("shell-open", node.id, "open component (BR6S-14) is not a shell")
            )
        elif shell.status == SHELL_NON_MANIFOLD:
            refused.append(
                Violation(
                    "shell-non-manifold",
                    node.id,
                    "an edge is used more than twice (BR6S-15)",
                )
            )
        else:
            closed.append(node.id)
            if not shell.oriented:
                refused.append(
                    Violation(
                        "shell-not-oriented",
                        node.id,
                        "shell is closed but inconsistently wound (BR6S-16)",
                    )
                )
        topology = _topology(graph, node.id)
        incident: Counter[int] = Counter()
        for start, end in topology.edges.values():
            incident[start] += 1
            incident[end] += 1
        for vertex_index in sorted(topology.vertices):
            if incident[vertex_index] < 2:
                refused.append(
                    Violation(
                        "vertex-not-shared",
                        NodeId(NODE_VERTEX, vertex_index),
                        "a vertex reachable by fewer than two edges cannot be a "
                        "shared B-rep vertex",
                    )
                )

    if options.outer_shell is not None:
        if options.outer_shell not in closed:
            refused.append(
                Violation(
                    "shell-role-undecided",
                    options.outer_shell,
                    "outer_shell is not one of the closed shell nodes",
                )
            )
    elif len(closed) > 1:
        refused.append(
            Violation(
                "shell-role-undecided",
                None,
                f"{len(closed)} closed shells; positive signed volume does not "
                "identify a cavity (BR6S-17/18) — pass StepOptions(outer_shell=...)",
            )
        )

    loop_nodes = {node.id: node for node in graph.nodes if node.id.kind == NODE_LOOP}
    for node in graph.nodes:
        if node.id.kind != NODE_FACE or not isinstance(node.data, FaceData):
            continue
        face = node.data
        if node.status in ("unplaced", "degenerate"):
            refused.append(
                Violation("face-unplaced", node.id, f"face status {node.status!r}")
            )
        if face.count_variant:
            refused.append(
                Violation(
                    "face-count-variant",
                    node.id,
                    "loop delimitation is not established (BR2-07d); the face "
                    "record cannot be represented",
                )
            )
        if face.loop_count > 1:
            refused.append(
                Violation(
                    "loop-role-undecided",
                    node.id,
                    f"{face.loop_count} loops on one face: no byte marks outer "
                    "vs inner (BR2 §3, BR2-09); refused in both face modes",
                )
            )
        if options.face_mode == "facet":
            if not face.triangles:
                refused.append(
                    Violation(
                        "face-unplaced",
                        node.id,
                        "facet mode needs at least one decoded triangle",
                    )
                )
            continue
        if face.loop_count == 0:
            refused.append(
                Violation("face-unplaced", node.id, "a face without a loop has no boundary")
            )
            continue
        if face.oriented is None:
            refused.append(
                Violation(
                    "shell-not-oriented",
                    node.id,
                    "exact mode needs a winding reading; this face has none",
                )
            )
        loops = [arc.child for arc in graph.arcs if arc.kind == ARC_FACE_LOOP and arc.parent == node.id]
        for loop in loops:
            loop_node = loop_nodes.get(loop)
            if loop_node is None:
                continue
            if getattr(loop_node.data, "closed_cycle", None) is not True:
                refused.append(
                    Violation(
                        "loop-role-undecided",
                        loop,
                        "exact mode needs a closed-cycle boundary loop; this "
                        "loop is a strip segment (BR2-16), not a boundary cycle",
                    )
                )
        if face.surface is None:
            if face.surface_disagreement:
                refused.append(
                    Violation(
                        "surface-disagreement",
                        node.id,
                        f"loops fit disagreeing surfaces {list(face.surface_labels)} "
                        "(BR4 §4)",
                    )
                )
            elif "pencil-noncyl" in face.surface_labels:
                refused.append(
                    Violation(
                        "unsupported-surface",
                        node.id,
                        "pencil-noncyl strip fit: no supported B-rep surface "
                        "(BR4 §3)",
                    )
                )
            else:
                refused.append(
                    Violation(
                        "surface-unbound",
                        node.id,
                        f"no face-level surface decision ({list(face.surface_labels) or 'ring plane failed'}); "
                        "cone/sphere fits stay loop readings (BR4 §4)",
                    )
                )
            continue
        surface = face.surface
        if surface.entity not in _SURFACE_ENTITIES:
            refused.append(
                Violation(
                    "unsupported-surface",
                    node.id,
                    f"{surface.entity} has no emitter (BR5-03a/b, BR4 §3)",
                )
            )
        elif surface.entity == "CYLINDRICAL_SURFACE":
            refused.append(
                Violation(
                    "unsupported-surface",
                    node.id,
                    "CYLINDRICAL_SURFACE is unreachable in exact mode: exact "
                    "needs a 0x4c ring and a ring's surface is the record "
                    "plane (design §4.3)",
                )
            )
        elif not _surface_emittable(surface):
            refused.append(
                Violation(
                    "unsupported-surface",
                    node.id,
                    f"{surface.entity} reading lacks its required fields",
                )
            )

    def key(violation: Violation):
        node = violation.node
        return (
            _REFUSAL_RANK.get(violation.code, len(REFUSAL_ORDER)),
            "" if node is None else node.kind,
            -1 if node is None else node.index,
            violation.detail,
        )

    unique = {
        (violation.code, violation.node, violation.arc, violation.detail): violation
        for violation in refused
    }
    return sorted(unique.values(), key=key)


def _surface_emittable(surface: SurfaceReading) -> bool:
    if surface.entity == "PLANE":
        return surface.normal is not None and surface.offset is not None
    if surface.entity == "CYLINDRICAL_SURFACE":
        return surface.axis is not None and surface.axis_point is not None and surface.radius is not None
    return False


def _point(w: _Writer, position, digits: int) -> str:
    coordinates = ",".join(_real(component, digits) for component in position)
    return w.add("CARTESIAN_POINT", f"CARTESIAN_POINT('',({coordinates}))")


def _direction(w: _Writer, vector) -> str:
    unit = _normalize(tuple(vector))
    if unit is None:
        raise ExportError(
            "unsupported-surface",
            "zero-length direction while emitting STEP (design §4.1)",
        )
    coordinates = ",".join(_real(component, DERIVED_DIGITS) for component in unit)
    return w.add("DIRECTION", f"DIRECTION('',({coordinates}))")


def _placement(w: _Writer, point, axis, digits: int) -> str:
    point_ref = _point(w, point, digits)
    axis_ref = _direction(w, axis)
    reference_ref = _direction(w, _ref_direction(tuple(axis)))
    return w.add(
        "AXIS2_PLACEMENT_3D",
        f"AXIS2_PLACEMENT_3D('',{point_ref},{axis_ref},{reference_ref})",
    )


def _emit_surface(w: _Writer, surface: SurfaceReading) -> str:
    if surface.entity == "PLANE":
        normal = tuple(surface.normal)
        offset = surface.offset
        point = tuple(-offset * component for component in normal)
        placement = _placement(w, point, normal, DERIVED_DIGITS)
        return w.add("PLANE", f"PLANE('',{placement})")
    if surface.entity == "CYLINDRICAL_SURFACE":
        placement = _placement(w, surface.axis_point, surface.axis, DERIVED_DIGITS)
        return w.add(
            "CYLINDRICAL_SURFACE",
            f"CYLINDRICAL_SURFACE('',{placement},{_real(surface.radius, DERIVED_DIGITS)})",
        )
    raise ExportError(
        "unsupported-surface",
        f"{surface.entity}: no emitter in the pinned subset (design §4.1)",
    )


def _emit_edge(w: _Writer, start, end, point_refs: dict[int, str], vertex_refs: dict[int, str]) -> str:
    direction = _normalize(_sub(end, start))
    if direction is None:
        raise ExportError("face-unplaced", "zero-length edge segment (design §4.1)")
    length = math.sqrt(sum(component * component for component in _sub(end, start)))
    direction_ref = _direction(w, direction)
    vector_ref = w.add("VECTOR", f"VECTOR('',{direction_ref},{_real(length, DERIVED_DIGITS)})")
    line_ref = w.add("LINE", f"LINE('',{point_refs[0]},{vector_ref})")
    return w.add(
        "EDGE_CURVE",
        f"EDGE_CURVE('',{vertex_refs[0]},{vertex_refs[1]},{line_ref},.T.)",
    )


def _emit_vertices(w: _Writer, topology: _ShellTopology, vertex_refs: dict[int, str], point_refs: dict[int, str]) -> None:
    for vertex_index in sorted(topology.vertices):
        point_ref = _point(w, topology.vertices[vertex_index], POOL_DIGITS)
        point_refs[vertex_index] = point_ref
        vertex_refs[vertex_index] = w.add("VERTEX_POINT", f"VERTEX_POINT('',{point_ref})")


def _emit_exact_shell(w: _Writer, graph: BodyGraph, topology: _ShellTopology) -> str:
    nodes = {node.id: node for node in graph.nodes}
    vertex_refs: dict[int, str] = {}
    point_refs: dict[int, str] = {}
    _emit_vertices(w, topology, vertex_refs, point_refs)
    edge_refs: dict[NodeId, str] = {}
    for edge, (start, end) in topology.edges.items():
        edge_refs[edge] = _emit_edge(
            w,
            topology.vertices[start],
            topology.vertices[end],
            (point_refs[start], point_refs[end]),
            (vertex_refs[start], vertex_refs[end]),
        )
    face_refs: list[str] = []
    for face in topology.faces:
        face_node = nodes[face]
        face_data = face_node.data
        loops = topology.loops.get(face, [])
        oriented_refs = []
        for loop in loops:
            for orientation, edge in topology.loop_edges.get(loop, []):
                sense = ".T." if orientation else ".F."
                oriented_refs.append(
                    w.add("ORIENTED_EDGE", f"ORIENTED_EDGE('',*,*,{edge_refs[edge]},{sense})")
                )
        loop_ref = w.add("EDGE_LOOP", f"EDGE_LOOP('',({','.join(oriented_refs)}))")
        bound_ref = w.add("FACE_OUTER_BOUND", f"FACE_OUTER_BOUND('',{loop_ref},.T.)")
        surface_ref = _emit_surface(w, face_data.surface)
        same_sense = ".T." if face_data.oriented else ".F."
        face_refs.append(
            w.add("ADVANCED_FACE", f"ADVANCED_FACE('',({bound_ref}),{surface_ref},{same_sense})")
        )
    return w.add("CLOSED_SHELL", f"CLOSED_SHELL('',({','.join(face_refs)}))")


def _emit_facet_shell(w: _Writer, graph: BodyGraph, topology: _ShellTopology) -> str:
    nodes = {node.id: node for node in graph.nodes}
    vertex_refs: dict[int, str] = {}
    point_refs: dict[int, str] = {}
    _emit_vertices(w, topology, vertex_refs, point_refs)
    face_refs: list[str] = []
    for face in topology.faces:
        face_node = nodes[face]
        face_data = face_node.data
        for triangle_index, triangle in enumerate(face_data.triangles):
            try:
                indices = [topology.vertex_of_rank[rank] for rank in triangle]
            except KeyError as exc:
                raise ExportError(
                    "face-unplaced",
                    f"triangle corner {exc.args[0]!r} has no vertex node in "
                    f"face {face.kind}[{face.index}] (design §4.3)",
                ) from exc
            positions = [topology.vertices[index] for index in indices]
            normal = _normalize(_cross(_sub(positions[1], positions[0]), _sub(positions[2], positions[0])))
            if normal is None:
                raise ExportError(
                    "face-unplaced",
                    f"degenerate triangle in face {face.kind}[{face.index}] (design §4.3)",
                )
            placement = _placement(w, positions[0], normal, POOL_DIGITS)
            surface_ref = w.add("PLANE", f"PLANE('',{placement})")
            oriented_refs = []
            for corner in range(3):
                a = corner
                b = (corner + 1) % 3
                edge_ref = _emit_edge(
                    w,
                    positions[a],
                    positions[b],
                    (point_refs[indices[a]], point_refs[indices[b]]),
                    (vertex_refs[indices[a]], vertex_refs[indices[b]]),
                )
                oriented_refs.append(
                    w.add("ORIENTED_EDGE", f"ORIENTED_EDGE('',*,*,{edge_ref},.T.)")
                )
            loop_ref = w.add("EDGE_LOOP", f"EDGE_LOOP('',({','.join(oriented_refs)}))")
            bound_ref = w.add("FACE_OUTER_BOUND", f"FACE_OUTER_BOUND('',{loop_ref},.T.)")
            name = f"facet[{triangle_index}] derived_from {face.kind}[{face.index}]"
            face_refs.append(
                w.add(
                    "ADVANCED_FACE",
                    f"ADVANCED_FACE('{name}',({bound_ref}),{surface_ref},.T.)",
                )
            )
    return w.add("CLOSED_SHELL", f"CLOSED_SHELL('',({','.join(face_refs)}))")


def _description(options: StepOptions) -> str:
    if options.face_mode == "facet":
        return (
            "BR6 topology graph (docs/agents/br6-graph-design.md §4.5); "
            "face mode facet; decoded-triangle tessellation, not an exact B-rep"
        )
    return (
        "BR6 topology graph (docs/agents/br6-graph-design.md §4.5); "
        "face mode exact; edges are tessellation loop segments, not exact "
        "B-rep curves"
    )


def _render(graph: BodyGraph, options: StepOptions, header: StepHeader) -> StepExport:
    w = _Writer()
    annotations = list(graph.annotations)
    unit = options.length_unit.upper()
    w.comment(
        f"UNIT: caller-supplied {unit}; no model unit system decoded (U2 0/108)"
    )
    unit_ref = w.add(
        "LENGTH_UNIT",
        f"(LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT{_UNIT_ENTITIES[unit]})",
    )
    w.add(
        "GEOMETRIC_REPRESENTATION_CONTEXT",
        (
            "(GEOMETRIC_REPRESENTATION_CONTEXT(3)GLOBAL_UNIT_ASSIGNED_CONTEXT"
            f"(({unit_ref}))REPRESENTATION_CONTEXT('',''))"
        ),
    )
    w.add(
        "UNCERTAINTY_MEASURE_WITH_UNIT",
        f"UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-7),{unit_ref},'','')",
    )
    annotations.append(
        f"units: caller-supplied {unit} (no measured model unit); "
        "uncertainty 1.E-7 in that unit"
    )
    annotations.append(
        "plane placement location -d*n is derived from the record plane equation (BR2-10)"
    )
    if options.face_mode == "exact":
        annotations.append(
            "exact mode: edges are loop segments of the decoded loops, never "
            "B-rep curves (BR3 §4)"
        )
    if (
        graph.completeness.excluded_faces
        or graph.completeness.excluded_shells
        or graph.completeness.face_unplaced
        or graph.completeness.unknown
    ):
        annotations.append(
            "unsupported: "
            f"excluded_faces={graph.completeness.excluded_faces}, "
            f"excluded_shells={graph.completeness.excluded_shells}, "
            f"face_unplaced={graph.completeness.face_unplaced}, "
            f"unknown={graph.completeness.unknown} record(s) are not represented"
        )

    closed = [
        node.id
        for node in graph.nodes
        if node.id.kind == NODE_SHELL
        and isinstance(node.data, ShellData)
        and node.data.status == SHELL_CLOSED
    ]
    outer = options.outer_shell if options.outer_shell is not None else closed[0]
    voids = [shell for shell in closed if shell != outer]
    shell_refs: dict[NodeId, str] = {}
    for shell in closed:
        topology = _topology(graph, shell)
        if options.face_mode == "exact":
            shell_refs[shell] = _emit_exact_shell(w, graph, topology)
        else:
            shell_refs[shell] = _emit_facet_shell(w, graph, topology)
    if voids:
        w.add(
            "BREP_WITH_VOIDS",
            f"BREP_WITH_VOIDS('',{shell_refs[outer]},({','.join(shell_refs[shell] for shell in voids)}))",
        )
    else:
        w.add("MANIFOLD_SOLID_BREP", f"MANIFOLD_SOLID_BREP('',{shell_refs[outer]})")

    schema = (
        "AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }"
        if options.schema == "AP214"
        else "CONFIG_CONTROL_DESIGN"
    )
    lines = [
        "ISO-10303-21;",
        "HEADER;",
        f"FILE_DESCRIPTION(('{_description(options)}'),'2;1');",
        f"FILE_NAME('{header.name}','{header.time_stamp}',('catpart'),('catpart'),"
        "'catpart brep graph','catpart','');",
        f"FILE_SCHEMA(('{schema}'));",
        "ENDSEC;",
        "DATA;",
        *w.lines,
        "ENDSEC;",
        "END-ISO-10303-21;",
    ]
    text = "\n".join(lines) + "\n"
    return StepExport(
        text=text,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        entity_counts=dict(w.counts),
        annotations=tuple(annotations),
        refused=(),
    )


def render_step(
    graph: BodyGraph,
    *,
    options: StepOptions = StepOptions(),
    header: StepHeader | None = None,
) -> StepExport:
    """Render the graph's closed shells as an ISO 10303-21 text.

    ``strict=True`` (the default) raises ``ExportError`` on the first
    refusal; ``strict=False`` returns an empty-text export carrying the
    full ``refused`` tuple. A refused graph never yields text.
    """
    if options.schema not in ("AP203", "AP214"):
        raise ValueError(f"schema {options.schema!r}: expected 'AP203' or 'AP214'")
    if options.face_mode not in ("exact", "facet"):
        raise ValueError(f"face_mode {options.face_mode!r}: expected 'exact' or 'facet'")
    refused = _refusals(graph, options)
    if refused:
        if options.strict:
            raise ExportError(refused[0].code, refused[0].detail)
        return StepExport(
            text="",
            sha256=hashlib.sha256(b"").hexdigest(),
            entity_counts={},
            annotations=tuple(graph.annotations),
            refused=tuple(refused),
        )
    return _render(graph, options, header or StepHeader())


def write_step(
    graph: BodyGraph,
    path,
    *,
    options: StepOptions = StepOptions(),
    header: StepHeader | None = None,
) -> StepExport:
    """Render then write ``path`` (nothing is written for a refused graph)."""
    export = render_step(graph, options=options, header=header)
    try:
        Path(path).write_text(export.text, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise ExportError("io-error", f"{path}: {exc}") from exc
    return export
