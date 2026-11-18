"""B-rep construct decoders and the topological boundary graph (Phase 7, Spec G #47).

Each decode ticket lands its own module here (``planar``, ``curves``,
``quadrics``, ``cgm_nurbs``, ``shell``); the BR6 integration step adds the
assembler (``graph``) and the STEP exporter (``step_export``). The public
surface is explicit: the modules plus the graph/export records and the
three entry points. Importing this package costs only the geometry
primitives those modules use — no corpus data, no decoder run.

The contract is ``docs/agents/br6-graph-design.md``; the L3 construct
denominator is the frozen vocabulary
(docs/evidence/data/brep-construct-vocabulary.csv, ticket #48 / BR1).
"""

from __future__ import annotations

from catpart.brep import cgm_nurbs, curves, graph, planar, quadrics, shell, step_export
from catpart.brep.graph import (
    INDEX_COMPOSITE,
    INDEX_NONE,
    INDEX_POOL,
    Arc,
    BodyGraph,
    Completeness,
    GraphPolicy,
    Node,
    NodeId,
    Provenance,
    StoreRef,
    SurfaceReading,
    Violation,
    build_part_graph,
    build_store_graph,
    check_invariants,
)
from catpart.brep.step_export import (
    REFUSAL_CLASSES,
    STEP_REFUSAL_CLASSES,
    STRUCTURE_REFUSAL_CLASSES,
    SUPPORTED_ENTITIES,
    StepExport,
    StepHeader,
    StepOptions,
    render_step,
    write_step,
)

__all__ = [
    "cgm_nurbs",
    "curves",
    "graph",
    "planar",
    "quadrics",
    "shell",
    "step_export",
    "INDEX_COMPOSITE",
    "INDEX_NONE",
    "INDEX_POOL",
    "Arc",
    "BodyGraph",
    "Completeness",
    "GraphPolicy",
    "Node",
    "NodeId",
    "Provenance",
    "StoreRef",
    "SurfaceReading",
    "Violation",
    "build_part_graph",
    "build_store_graph",
    "check_invariants",
    "REFUSAL_CLASSES",
    "STEP_REFUSAL_CLASSES",
    "STRUCTURE_REFUSAL_CLASSES",
    "SUPPORTED_ENTITIES",
    "StepExport",
    "StepHeader",
    "StepOptions",
    "render_step",
    "write_step",
]
