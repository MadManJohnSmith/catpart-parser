"""Unit tests for the BR6 topology graph and STEP export (Ticket #58).

Synthetic fixtures only — no corpus. Every invariant has a positive case
and one negative per discrimination the law makes; every export refusal
class has a constructible fixture; the STEP round-trip parses entity
counts and re-renders for byte-identical output.
"""

from __future__ import annotations

import csv
import dataclasses
import re
import struct
from pathlib import Path

import pytest

from catpart.brep import graph as G
from catpart.brep import step_export as S
from catpart.geometry import facets, store
from catpart.geometry.errors import ExportError

REPO_ROOT = Path(__file__).resolve().parents[1]
CLAIMS_CSV = REPO_ROOT / "docs" / "evidence" / "data" / "br6-graph-claims.csv"
EVIDENCE_MD = REPO_ROOT / "docs" / "evidence" / "2026-11-18-br6-graph.md"

CLAIMS_FIELDS = [
    "claim",
    "statement",
    "label",
    "scope",
    "release",
    "observations",
    "passes",
    "rate",
    "value",
]


# --------------------------------------------------------------------
# Synthetic store bytes
# --------------------------------------------------------------------

CUBE = [
    (0.0, 0.0, 0.0),
    (1.0, 0.0, 0.0),
    (1.0, 1.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, 0.0, 1.0),
    (1.0, 0.0, 1.0),
    (1.0, 1.0, 1.0),
    (0.0, 1.0, 1.0),
]
CUBE_FACES = [
    (0x4C, (0, 3, 2, 1), (0.0, 0.0, -1.0)),
    (0x4C, (4, 5, 6, 7), (0.0, 0.0, 1.0)),
    (0x4C, (0, 1, 5, 4), (0.0, -1.0, 0.0)),
    (0x4C, (1, 2, 6, 5), (1.0, 0.0, 0.0)),
    (0x4C, (2, 3, 7, 6), (0.0, 1.0, 0.0)),
    (0x4C, (3, 0, 4, 7), (-1.0, 0.0, 0.0)),
]

TETRA = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
TETRA_FACES = [(0, 2, 1), (0, 1, 3), (1, 2, 3), (0, 3, 2)]


def _f32(point):
    return tuple(struct.unpack("<f", struct.pack("<f", value))[0] for value in point)


def _normal(points, refs):
    a, b, c = (points[i] for i in refs[:3])
    u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    length = (n[0] ** 2 + n[1] ** 2 + n[2] ** 2) ** 0.5
    return tuple(component / length for component in n)


def _record(marker, refs, *, counts=None, normal=None, ty=None):
    counts = tuple(counts) if counts is not None else (len(refs),)
    return {
        "marker": marker,
        "refs": tuple(refs),
        "counts": counts,
        "normal": normal,
        "ty": len(counts) if ty is None else ty,
    }


def _store(points, faces):
    """Pool group + facet records; ``refs`` are POOL WALK positions."""
    points = [_f32(point) for point in points]
    lex = facets.lex_rank_map(points)
    rank = {walk: r for r, walk in enumerate(lex)}
    data = bytearray()
    data += b"\x10\x24\x04\xff\xff\x00\x00\x00" + b"\x01\x06" + bytes([len(points)])
    for point in points:
        data += b"\x05\x08\x01" + struct.pack("<fff", *point)
    for face in faces:
        data += (
            b"\x01"
            + bytes([face["marker"]])
            + bytes([face["ty"]])
            + b"\xff"
            + struct.pack("<I", len(face["refs"]))
        )
        if face["marker"] in facets.NORMAL_MARKERS_ALL:
            data += struct.pack("<fff", *(face["normal"] or (0.0, 0.0, 1.0)))
        data += bytes(face["counts"])
        data += bytes(rank.get(ref, ref) for ref in face["refs"])
    data = bytes(data)
    span = store.StoreSpan(
        block_start=0,
        origin=0,
        origin_kind=store.ORIGIN_KIND_BLOCK,
        body_lo=0,
        body_hi=len(data),
        catalog_len=0,
        container="synthetic",
        tail_law=store.TAIL_LAW_SHIPPED,
    )
    return data, span


def _graph(points, faces, *, policy=G.GraphPolicy()):
    data, span = _store(points, faces)
    return G.build_store_graph(data, span, policy=policy)


def _cube_graph(**kwargs):
    faces = [_record(marker, refs, normal=normal) for marker, refs, normal in CUBE_FACES]
    return _graph(CUBE, faces, **kwargs)


def _tetra_graph(**kwargs):
    points = [_f32(point) for point in TETRA]
    faces = [
        _record(0x4C, refs, normal=_normal(points, refs)) for refs in TETRA_FACES
    ]
    return _graph(points, faces, **kwargs)


def _rings(radius, z, count=12):
    import math

    return [
        (radius * math.cos(2 * math.pi * i / count), radius * math.sin(2 * math.pi * i / count), z)
        for i in range(count)
    ]


def _zigzag(first, second):
    out = []
    for a, b in zip(first, second):
        out.append(a)
        out.append(b)
    return out


def _codes(graph, options):
    export = S.render_step(graph, options=dataclasses.replace(options, strict=False))
    return {violation.code for violation in export.refused}


def _node(graph, kind, index=0):
    return next(node for node in graph.nodes if node.id == G.NodeId(kind, index))


def _replace_node(graph, node_id, **changes):
    return dataclasses.replace(
        graph,
        nodes=tuple(
            dataclasses.replace(node, **changes) if node.id == node_id else node
            for node in graph.nodes
        ),
    )


def _replace_data(graph, node_id, data):
    return _replace_node(graph, node_id, data=data)


@pytest.fixture(scope="module")
def cube():
    return _cube_graph()


@pytest.fixture(scope="module")
def step_options():
    return S.StepOptions(length_unit="MM", accept_assumed_lump=True)


# --------------------------------------------------------------------
# §1/§2 — the node/arc model and the assembler
# --------------------------------------------------------------------


def test_cube_is_the_contract_example(cube):
    assert cube.status == G.STATUS_COMPLETE
    assert cube.index_space == G.INDEX_POOL
    assert cube.completeness == G.Completeness(
        body=1,
        lump=1,
        shell=1,
        shell_closed=1,
        face=6,
        face_placed=6,
        face_unplaced=0,
        loop=6,
        edge=12,
        vertex=8,
        unknown=0,
        skipped_refs=0,
        excluded_loops=0,
        excluded_shells=0,
        excluded_faces=0,
    )
    kinds = [node.id.kind for node in cube.nodes]
    assert kinds == [
        "body",
        "lump",
        "shell",
        "face",
        "face",
        "face",
        "face",
        "face",
        "face",
    ] + ["loop"] * 6 + ["edge"] * 12 + ["vertex"] * 8
    assert {node.id.kind for node in cube.nodes} == set(G.NODE_KINDS)
    # ids are the store order per kind, dense.
    for kind in G.NODE_KINDS:
        indices = [n.id.index for n in cube.nodes if n.id.kind == kind]
        assert indices == list(range(len(indices)))
    assert G.check_invariants(cube) == ()


def test_every_arc_carries_its_own_provenance(cube):
    for arc in cube.arcs:
        assert arc.provenance.decoder in G.DECODERS
        assert arc.provenance.claim
        # the shell-face arc cites the partition law, not the child's face row
        if arc.kind == G.ARC_SHELL_FACE:
            assert arc.provenance.claim == "BR6S-13"
            child = _node(cube, "face", arc.child.index)
            assert arc.provenance.claim != child.provenance.claim
    assert {arc.kind for arc in cube.arcs} == set(G.ARC_KINDS)


def test_tetrahedron_counts_and_loop_segment_edges():
    graph = _tetra_graph()
    assert graph.status == G.STATUS_COMPLETE
    assert graph.completeness.face == 4
    assert graph.completeness.loop == 4
    assert graph.completeness.edge == 6
    assert graph.completeness.vertex == 4
    assert G.check_invariants(graph) == ()


def test_lump_is_labelled_assumed_not_fact(cube):
    lump = _node(cube, "lump")
    assert lump.provenance.export_label == "assumed"
    assert "assumed" in lump.provenance.labels
    assert "BR5-06a" in lump.provenance.claim
    # body cardinality is declared an assumption in the provenance detail
    assert "assumption" in _node(cube, "body").provenance.detail


def test_policy_without_lump_has_no_shell_subtree():
    graph = _cube_graph(policy=G.GraphPolicy(derive_single_lump=False))
    assert graph.status == G.STATUS_LUMP_UNDECODED
    assert {node.id.kind for node in graph.nodes} == {"body"}
    assert graph.completeness.shell == 0


def test_policy_without_open_shells_excludes_them():
    points = [_f32(p) for p in CUBE[:4]]
    faces = [
        _record(0x4C, (0, 1, 2), normal=_normal(points, (0, 1, 2))),
    ]
    graph = _graph(points, faces, policy=G.GraphPolicy(include_open_shells=False))
    assert graph.completeness.excluded_shells == 1
    assert graph.completeness.excluded_faces == 0
    assert graph.status == G.STATUS_UNVERIFIED
    assert not [n for n in graph.nodes if n.id.kind == "shell"]
    assert any("include_open_shells=False" in line for line in graph.annotations)


def test_policy_without_coherent_surface_assigns_no_surface(cube):
    graph = _cube_graph(policy=G.GraphPolicy(coherent_face_surface=False))
    assert all(_node(graph, "face", i).data.surface is None for i in range(6))


# --------------------------------------------------------------------
# §2 — surface coherence (F2: rings are the plane law, strips PatchFit)
# --------------------------------------------------------------------


def test_ring_face_surface_is_the_record_plane(cube):
    for index in range(6):
        surface = _node(cube, "face", index).data.surface
        assert surface.entity == "PLANE"
        assert surface.label == "candidate"
        assert surface.claim == "BR2-10"
        assert surface.offset is not None


def test_ring_refs_never_reach_the_strip_classifier(cube):
    # F2: a ring's refs would classify as degenerate/pencil-noncyl. The
    # ring path must not call it, so a 4-corner ring keeps its plane.
    for index in range(6):
        assert _node(cube, "face", index).data.surface_labels == ()


def test_agreeing_cylinder_loops_become_one_cylinder():
    band = _rings(8.0, 0.0) + _rings(8.0, 10.0)
    refs = _zigzag(range(12), range(12, 24))
    graph = _graph(band, [_record(0x4A, refs, normal=(0.0, 0.0, 1.0))])
    face = _node(graph, "face")
    assert face.data.surface.entity == "CYLINDRICAL_SURFACE"
    assert face.data.surface.label == "candidate"
    assert face.data.surface.claim == "SRF-02"
    assert abs(face.data.surface.radius - 8.0) < 0.05
    assert face.data.surface.axis_point is not None


def test_disagreeing_loops_never_become_a_face_surface():
    cylinder = _rings(8.0, 0.0) + _rings(8.0, 10.0)
    planar = [(x, 0.0, 0.0) for x in (0.0, 4.0, 8.0, 12.0, 16.0)] + [
        (x, 3.0, 0.0) for x in (0.0, 4.0, 8.0, 12.0, 16.0)
    ]
    points = cylinder + planar
    refs = _zigzag(range(12), range(12, 24)) + _zigzag(
        range(24, 29), range(29, 34)
    )
    record = _record(0x4A, refs, counts=(24, 10), normal=(0.0, 0.0, 1.0))
    graph = _graph(points, [record])
    face = _node(graph, "face")
    assert face.data.surface is None
    assert face.data.surface_disagreement
    assert set(face.data.surface_labels) == {"cylinder", "planar"}
    assert any("surface-disagreement" in line for line in graph.annotations)
    codes = _codes(
        graph,
        S.StepOptions(face_mode="exact", length_unit="MM", accept_assumed_lump=True),
    )
    assert "surface-disagreement" in codes


def test_cone_loops_never_become_a_face_surface():
    points = _rings(10.0, 0.0) + _rings(7.5, 10.0) + _rings(5.0, 20.0)
    refs = _zigzag(range(12), range(12, 24)) + _zigzag(range(12, 24), range(24, 36))
    graph = _graph(points, [_record(0x4A, refs, normal=(0.0, 0.0, 1.0))])
    face = _node(graph, "face")
    assert face.data.surface is None
    assert face.data.surface_labels == ("cone",)
    assert not face.data.surface_disagreement
    codes = _codes(
        graph,
        S.StepOptions(face_mode="exact", length_unit="MM", accept_assumed_lump=True),
    )
    assert "surface-unbound" in codes


# --------------------------------------------------------------------
# §5 — load-bearing invariants (1, 2, 4, 6)
# --------------------------------------------------------------------


def test_open_sheet_fails_edge_use_pairing():
    points = [_f32(p) for p in ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 1.0, 0.0))]
    faces = [
        _record(0x4C, (0, 1, 2), normal=(0.0, 0.0, 1.0)),
        _record(0x4C, (1, 3, 2), normal=(0.0, 0.0, 1.0)),
    ]
    graph = _graph(points, faces)
    codes = {v.code for v in G.check_invariants(graph)}
    assert "edge-use-pair" in codes
    export_codes = _codes(
        graph,
        S.StepOptions(face_mode="exact", length_unit="MM", accept_assumed_lump=True),
    )
    assert "shell-not-brep-paired" in export_codes
    assert "shell-open" in export_codes


def test_missing_loop_segment_is_not_brep_paired(cube):
    # Removing one loop-edge use leaves an edge used once (F7's law).
    arc_index = next(
        index
        for index, arc in enumerate(cube.arcs)
        if arc.kind == G.ARC_LOOP_EDGE
    )
    patched = dataclasses.replace(
        cube, arcs=cube.arcs[:arc_index] + cube.arcs[arc_index + 1 :]
    )
    codes = {v.code for v in G.check_invariants(patched)}
    assert "edge-use-pair" in codes
    assert "shell-not-brep-paired" in _codes(
        patched,
        S.StepOptions(face_mode="exact", length_unit="MM", accept_assumed_lump=True),
    )


def test_inward_wound_face_fails_orientation():
    points = [_f32(point) for point in CUBE]
    faces = []
    for index, (marker, refs, normal) in enumerate(CUBE_FACES):
        if index == 0:
            refs = tuple(reversed(refs))
        faces.append(_record(marker, refs, normal=normal))
    graph = _graph(points, faces)
    codes = {v.code for v in G.check_invariants(graph)}
    assert "orientation" in codes
    export_codes = _codes(
        graph,
        S.StepOptions(face_mode="exact", length_unit="MM", accept_assumed_lump=True),
    )
    assert "shell-not-oriented" in export_codes


def test_detached_face_is_an_orphan(cube):
    detached = G.Node(
        id=G.NodeId("face", 6),
        provenance=_node(cube, "face").provenance,
        data=_node(cube, "face").data,
        status=G.STATUS_OK,
    )
    patched = dataclasses.replace(cube, nodes=cube.nodes + (detached,))
    codes = {v.code for v in G.check_invariants(patched)}
    assert "no-orphan" in codes


def test_fabricated_claim_fails_the_allowlist(cube):
    face_id = G.NodeId("face", 0)
    prov = _node(cube, "face").provenance
    patched = _replace_node(
        cube, face_id, provenance=dataclasses.replace(prov, claim="BR6G-99")
    )
    codes = {v.code for v in G.check_invariants(patched)}
    assert "provenance-complete" in codes
    assert "provenance-incomplete" in _codes(
        patched,
        S.StepOptions(face_mode="exact", length_unit="MM", accept_assumed_lump=True),
    )


def test_cited_scope_must_match_the_index_space(cube):
    vertex_id = G.NodeId("vertex", 0)
    prov = _node(cube, "vertex").provenance
    patched = _replace_node(
        cube,
        vertex_id,
        provenance=dataclasses.replace(
            prov,
            claim="BR6S-23",
            scope="face-candidate records, composite stores",
        ),
    )
    problems = {v.code for v in G.check_invariants(patched)}
    assert "provenance-complete" in problems


def test_scope_conflict_is_checked_symmetrically():
    assert G.scope_conflict("face components, pool-only stores", "pool", "model") == ""
    assert G.scope_conflict("face-candidate records, composite stores", "pool", "model")
    assert G.scope_conflict("face components, pool-only stores", "composite-element", "model")
    assert G.scope_conflict("located stores", "pool", "model") == ""
    # a row naming a unit cannot justify model-unit geometry
    assert G.scope_conflict("unconverted", "pool", "model", statement="length in mm")


def test_unknown_node_is_a_guess(cube):
    node_id = G.NodeId("face", 0)
    prov = _node(cube, "face").provenance
    patched = _replace_node(
        cube,
        node_id,
        provenance=dataclasses.replace(
            prov, labels=("unknown",), export_label="unknown"
        ),
    )
    assert "no-guess" in {v.code for v in G.check_invariants(patched)}
    assert "unknown-node" in _codes(
        patched,
        S.StepOptions(face_mode="exact", length_unit="MM", accept_assumed_lump=True),
    )


# --------------------------------------------------------------------
# §5 — construction guarantees (3, 5, 7, 8)
# --------------------------------------------------------------------


def test_duplicate_coordinate_slots_are_not_topological_vertices():
    # p1 and p3 share coordinates: the pool slot is the vertex identity, so
    # the two faces never pair and the components stay open.
    points = [
        _f32(p)
        for p in (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
        )
    ]
    faces = [
        _record(0x4C, (0, 1, 2), normal=_normal(points, (0, 1, 2))),
        _record(0x4C, (0, 4, 3), normal=_normal(points, (0, 4, 3))),
    ]
    graph = _graph(points, faces)
    assert graph.completeness.vertex == 5
    assert graph.completeness.shell_closed == 0
    assert graph.status == G.STATUS_UNVERIFIED


def test_out_of_pool_face_is_counted_and_contributes_no_vertex():
    points = [_f32(point) for point in CUBE]
    faces = [_record(marker, refs, normal=normal) for marker, refs, normal in CUBE_FACES]
    faces.append(_record(0x4C, (0, 1, 99), normal=(0.0, 0.0, 1.0)))
    graph = _graph(points, faces)
    assert graph.completeness.face_unplaced == 1
    assert graph.completeness.vertex == 8
    assert graph.status == G.STATUS_UNVERIFIED
    assert any("leave the pool" in line for line in graph.annotations)


def test_duplicate_node_index_fails_determinism(cube):
    duplicated = dataclasses.replace(cube.nodes[3], id=G.NodeId("face", 2))
    patched = dataclasses.replace(cube, nodes=cube.nodes + (duplicated,))
    codes = {v.code for v in G.check_invariants(patched)}
    assert "determinism" in codes


def test_illegal_arc_kind_is_reported(cube):
    illegal = G.Arc(
        kind="body-lump",
        parent=G.NodeId("face", 0),
        child=G.NodeId("lump", 0),
        orientation=None,
        provenance=_node(cube, "lump").provenance,
    )
    patched = dataclasses.replace(cube, arcs=cube.arcs + (illegal,))
    codes = {v.code for v in G.check_invariants(patched)}
    assert "arc-kind-table" in codes


def test_check_invariants_never_raises_on_a_broken_graph(cube):
    broken = G.BodyGraph(
        nodes=(G.Node(id=G.NodeId("nonsense", 0), provenance=G.Provenance(
            "x", "y", "z", (), "nope", "nope", "nope", "nope", "nope"
        ), data=G.BodyData(False, None), status="weird"),),
        arcs=(G.Arc("bad", G.NodeId("a", 0), G.NodeId("b", 0), None, cube.nodes[0].provenance),),
        store=cube.store,
        policy=cube.policy,
        completeness=cube.completeness,
        annotations=(),
        status=G.STATUS_UNVERIFIED,
    )
    codes = {v.code for v in G.check_invariants(broken)}
    assert {"determinism", "arc-kind-table", "provenance-complete"} <= codes


# --------------------------------------------------------------------
# Reflexive / composite / unread stores (detector honesty)
# --------------------------------------------------------------------


def test_composite_store_builds_no_placeholder_geometry():
    data, span = _store(
        [_f32(p) for p in CUBE],
        [_record(marker, refs, normal=normal) for marker, refs, normal in CUBE_FACES],
    )
    data = data + b"\x10\x24\x04\xff\xff\x00\x00\x00" + b"\x01\x02"
    span = dataclasses.replace(span, body_hi=len(data))
    graph = G.build_store_graph(data, span)
    assert graph.index_space == G.INDEX_COMPOSITE
    assert graph.status == G.STATUS_UNVERIFIED
    assert {node.id.kind for node in graph.nodes} == {"body", "lump"}
    assert graph.completeness.face == 0
    assert graph.completeness.face_unplaced == 6
    assert graph.completeness.vertex == 0 and graph.completeness.shell == 0
    assert "index-space-unplaceable" in _codes(
        graph,
        S.StepOptions(face_mode="exact", length_unit="MM", accept_assumed_lump=True),
    )


def test_unread_marker_is_counted_not_noded(cube):
    data, span = _store(
        [_f32(p) for p in CUBE],
        [_record(marker, refs, normal=normal) for marker, refs, normal in CUBE_FACES]
        + [_record(0x44, (0, 1, 2))],
    )
    graph = G.build_store_graph(data, span)
    assert graph.completeness.unknown == 1
    assert not [node for node in graph.nodes if node.status == G.STATUS_UNKNOWN]
    assert graph.status == G.STATUS_UNVERIFIED


def test_face_family_without_a_node_producer_refuses():
    faces = [
        _record(0x42 if index == 0 else marker, refs, normal=normal)
        for index, (marker, refs, normal) in enumerate(CUBE_FACES)
    ]
    graph = _graph([_f32(p) for p in CUBE], faces)
    assert graph.completeness.excluded_faces == 1
    assert graph.completeness.face == 5
    assert "face-family-unread" in _codes(
        graph,
        S.StepOptions(face_mode="exact", length_unit="MM", accept_assumed_lump=True),
    )


def test_count_variant_face_has_no_loops_and_refuses():
    points = [_f32(p) for p in ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))]
    record = _record(0x4C, (0, 1, 2), counts=(3, 0, 0), normal=(0.0, 0.0, 1.0), ty=2)
    graph = _graph(points, [record])
    face = _node(graph, "face")
    assert face.data.count_variant
    assert graph.completeness.loop == 0
    assert "face-count-variant" in _codes(
        graph,
        S.StepOptions(face_mode="exact", length_unit="MM", accept_assumed_lump=True),
    )


def test_two_loop_ring_refuses_loop_roles_in_both_modes():
    points = [_f32(p) for p in ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 1.0, 0.0))]
    record = _record(
        0x4C, (0, 1, 2, 1, 3, 2), counts=(3, 3), normal=(0.0, 0.0, 1.0)
    )
    graph = _graph(points, [record])
    assert _node(graph, "face").data.loop_count == 2
    assert graph.completeness.loop == 2
    for mode in ("exact", "facet"):
        assert "loop-role-undecided" in _codes(
            graph,
            S.StepOptions(face_mode=mode, length_unit="MM", accept_assumed_lump=True),
        )


# --------------------------------------------------------------------
# §4.6 — one fixture per export refusal class
# --------------------------------------------------------------------


def test_refusal_lump_assumed(cube):
    codes = _codes(cube, S.StepOptions(face_mode="exact", length_unit="MM"))
    assert "lump-assumed" in codes
    with pytest.raises(ExportError) as error:
        S.render_step(
            cube, options=S.StepOptions(face_mode="exact", length_unit="MM")
        )
    assert error.value.error_class == "lump-assumed"


def test_refusal_lump_undecoded():
    graph = _cube_graph(policy=G.GraphPolicy(derive_single_lump=False))
    assert "lump-undecoded" in _codes(
        graph, S.StepOptions(face_mode="exact", length_unit="MM", accept_assumed_lump=True)
    )


def test_refusal_unit_undetermined(cube):
    assert "unit-undetermined" in _codes(
        cube, S.StepOptions(face_mode="exact", accept_assumed_lump=True)
    )
    assert "unit-undetermined" in _codes(
        cube, S.StepOptions(face_mode="exact", length_unit="INCH", accept_assumed_lump=True)
    )


def test_refusal_body_no_shell():
    points = [_f32(p) for p in ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))]
    graph = _graph(points, [])
    assert graph.status == G.STATUS_UNVERIFIED
    assert "body-no-shell" in _codes(
        graph, S.StepOptions(face_mode="exact", length_unit="MM", accept_assumed_lump=True)
    )


def test_refusal_body_no_shell_when_no_store(tmp_path):
    path = tmp_path / "not-a-part.CATPart"
    path.write_bytes(b"not a catpart")
    graph = G.build_part_graph(path)
    assert graph.nodes == ()
    assert graph.status == G.STATUS_UNVERIFIED
    assert graph.store.sha256 is not None
    assert "body-no-shell" in _codes(
        graph, S.StepOptions(face_mode="exact", length_unit="MM", accept_assumed_lump=True)
    )


def test_refusal_face_unplaced(cube):
    patched = _replace_node(cube, G.NodeId("face", 0), status=G.STATUS_UNPLACED)
    assert "face-unplaced" in _codes(
        patched,
        S.StepOptions(face_mode="exact", length_unit="MM", accept_assumed_lump=True),
    )


def test_refusal_shell_open():
    points = [_f32(p) for p in ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))]
    graph = _graph(points, [_record(0x4C, (0, 1, 2), normal=(0.0, 0.0, 1.0))])
    assert "shell-open" in _codes(
        graph, S.StepOptions(face_mode="facet", length_unit="MM", accept_assumed_lump=True)
    )


def test_refusal_shell_non_manifold():
    points = [_f32(p) for p in ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0))]
    faces = [
        _record(0x4C, refs, normal=_normal(points, refs))
        for refs in ((0, 1, 2), (0, 1, 3), (0, 1, 4))
    ]
    graph = _graph(points, faces)
    assert _node(graph, "shell").data.status == "non-manifold"
    assert "shell-non-manifold" in _codes(
        graph, S.StepOptions(face_mode="facet", length_unit="MM", accept_assumed_lump=True)
    )


def test_refusal_shell_not_brep_paired(cube):
    arc_index = next(
        index for index, arc in enumerate(cube.arcs) if arc.kind == G.ARC_LOOP_EDGE
    )
    patched = dataclasses.replace(
        cube, arcs=cube.arcs[:arc_index] + cube.arcs[arc_index + 1 :]
    )
    assert "shell-not-brep-paired" in _codes(
        patched,
        S.StepOptions(face_mode="exact", length_unit="MM", accept_assumed_lump=True),
    )


def test_facet_mode_does_not_refuse_on_loop_segment_pairing(cube):
    arc_index = next(
        index for index, arc in enumerate(cube.arcs) if arc.kind == G.ARC_LOOP_EDGE
    )
    patched = dataclasses.replace(
        cube, arcs=cube.arcs[:arc_index] + cube.arcs[arc_index + 1 :]
    )
    assert "shell-not-brep-paired" not in _codes(
        patched,
        S.StepOptions(face_mode="facet", length_unit="MM", accept_assumed_lump=True),
    )


def test_refusal_vertex_not_shared(cube):
    # A graph whose vertex identities were collapsed onto one slot: after
    # the patch, vertex 0 is incident to a single edge.
    nodes = list(cube.nodes)
    redirected = 0
    for index, node in enumerate(nodes):
        if node.id.kind != "edge" or not isinstance(node.data, G.EdgeData):
            continue
        if 0 not in (node.data.start, node.data.end):
            continue
        redirected += 1
        if redirected == 1:
            continue
        nodes[index] = dataclasses.replace(
            node,
            data=dataclasses.replace(
                node.data,
                start=1 if node.data.start == 0 else node.data.start,
                end=1 if node.data.end == 0 else node.data.end,
            ),
        )
    patched = dataclasses.replace(cube, nodes=tuple(nodes))
    assert "vertex-not-shared" in _codes(
        patched,
        S.StepOptions(face_mode="exact", length_unit="MM", accept_assumed_lump=True),
    )


def test_refusal_unsupported_surface(cube):
    face = _node(cube, "face")
    torus = G.SurfaceReading(
        entity="TOROIDAL_SURFACE", label="candidate", claim="SRF-05", radius=4.0
    )
    patched = _replace_data(
        cube,
        face.id,
        dataclasses.replace(face.data, surface=torus),
    )
    assert "unsupported-surface" in _codes(
        patched,
        S.StepOptions(face_mode="exact", length_unit="MM", accept_assumed_lump=True),
    )


def test_refusal_shell_role_undecided_with_two_shells():
    shifted = tuple((x + 3.0, y, z) for x, y, z in CUBE)
    points = [_f32(p) for p in CUBE + list(shifted)]
    faces = [_record(marker, refs, normal=normal) for marker, refs, normal in CUBE_FACES]
    faces += [
        _record(marker, tuple(index + 8 for index in refs), normal=normal)
        for marker, refs, normal in CUBE_FACES
    ]
    graph = _graph(points, faces)
    assert graph.completeness.shell_closed == 2
    options = S.StepOptions(face_mode="exact", length_unit="MM", accept_assumed_lump=True)
    assert "shell-role-undecided" in _codes(graph, options)
    export = S.render_step(
        graph, options=dataclasses.replace(options, outer_shell=G.NodeId("shell", 0))
    )
    assert "BREP_WITH_VOIDS" in export.entity_counts
    assert export.entity_counts.get("MANIFOLD_SOLID_BREP", 0) == 0


def test_refusal_index_space_unplaceable(cube):
    vertex_id = G.NodeId("vertex", 0)
    prov = _node(cube, "vertex").provenance
    patched = _replace_node(
        cube,
        vertex_id,
        provenance=dataclasses.replace(prov, index_space=G.INDEX_COMPOSITE),
    )
    assert "index-space-unplaceable" in _codes(
        patched,
        S.StepOptions(face_mode="exact", length_unit="MM", accept_assumed_lump=True),
    )


def test_refusal_exact_cylinder_is_unreachable(cube):
    face = _node(cube, "face")
    cylinder = G.SurfaceReading(
        entity="CYLINDRICAL_SURFACE",
        label="candidate",
        claim="SRF-02",
        axis=(0.0, 0.0, 1.0),
        axis_point=(0.0, 0.0, 0.0),
        radius=1.0,
    )
    patched = _replace_data(cube, face.id, dataclasses.replace(face.data, surface=cylinder))
    codes = _codes(
        patched,
        S.StepOptions(face_mode="exact", length_unit="MM", accept_assumed_lump=True),
    )
    assert "unsupported-surface" in codes
    # facet mode does not need the graph surface at all
    assert "unsupported-surface" not in _codes(
        patched,
        S.StepOptions(face_mode="facet", length_unit="MM", accept_assumed_lump=True),
    )


def test_refusal_face_family_unread():
    faces = [
        _record(0x42 if index == 0 else marker, refs, normal=normal)
        for index, (marker, refs, normal) in enumerate(CUBE_FACES)
    ]
    graph = _graph([_f32(p) for p in CUBE], faces)
    assert "face-family-unread" in _codes(
        graph,
        S.StepOptions(face_mode="facet", length_unit="MM", accept_assumed_lump=True),
    )


def test_refusal_provenance_incomplete(cube):
    prov = _node(cube, "face").provenance
    patched = _replace_node(
        cube,
        G.NodeId("face", 0),
        provenance=dataclasses.replace(prov, claim="BR6G-99"),
    )
    assert "provenance-incomplete" in _codes(
        patched,
        S.StepOptions(face_mode="exact", length_unit="MM", accept_assumed_lump=True),
    )


def test_refusal_unknown_node(cube):
    prov = _node(cube, "face").provenance
    patched = _replace_node(
        cube,
        G.NodeId("face", 0),
        provenance=dataclasses.replace(
            prov, labels=("unknown",), export_label="unknown"
        ),
    )
    assert "unknown-node" in _codes(
        patched,
        S.StepOptions(face_mode="exact", length_unit="MM", accept_assumed_lump=True),
    )


def test_refusal_classes_are_the_contract_set():
    assert len(S.STEP_REFUSAL_CLASSES) == 20
    assert S.STEP_REFUSAL_CLASSES <= S.REFUSAL_CLASSES
    assert S.STRUCTURE_REFUSAL_CLASSES == {"no-orphan", "determinism", "arc-kind-table"}
    assert S.REFUSAL_CLASSES == frozenset(S.REFUSAL_ORDER)


# --------------------------------------------------------------------
# §4 — STEP export
# --------------------------------------------------------------------

STEP_SUBSET = {
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


def test_supported_entities_are_pinned_to_the_contract():
    assert S.SUPPORTED_ENTITIES == frozenset(STEP_SUBSET)


def _records(text: str):
    body = text.split("DATA;\n", 1)[1].split("ENDSEC;", 1)[0]
    records = {}
    for line in body.splitlines():
        match = re.match(r"^#(\d+)=(.*);$", line)
        if not match:
            continue
        content = match.group(2)
        if content.startswith("("):
            content = content[1:]
        kind = content.split("(", 1)[0]
        records[int(match.group(1))] = (kind, line)
    return records


def test_exact_and_facet_counts_on_the_cube(cube, step_options):
    exact = S.render_step(
        cube, options=dataclasses.replace(step_options, face_mode="exact")
    )
    facet = S.render_step(
        cube, options=dataclasses.replace(step_options, face_mode="facet")
    )
    assert exact.entity_counts["ADVANCED_FACE"] == 6
    assert facet.entity_counts["ADVANCED_FACE"] == 12  # two triangles per quad
    assert exact.entity_counts["EDGE_CURVE"] == 12
    assert facet.entity_counts["EDGE_CURVE"] == 36  # three sides per triangle
    assert exact.entity_counts["PLANE"] == 6
    assert facet.entity_counts["PLANE"] == 12
    assert exact.entity_counts["MANIFOLD_SOLID_BREP"] == 1
    assert exact.entity_counts["CLOSED_SHELL"] == 1
    assert "derived_from face[0]" in facet.text


def test_facet_is_the_default_mode():
    assert S.StepOptions().face_mode == "facet"


def test_step_round_trip_parses_counts_and_references(cube, step_options):
    export = S.render_step(
        cube, options=dataclasses.replace(step_options, face_mode="exact")
    )
    records = _records(export.text)
    assert len(records) == sum(export.entity_counts.values())
    assert dict((kind, sum(1 for k, _ in records.values() if k == kind)) for kind in set(k for k, _ in records.values())) == export.entity_counts
    defined = set(records)
    for _identifier, (_kind, line) in records.items():
        for reference in re.findall(r"#(\d+)", line):
            assert int(reference) in defined, f"dangling reference #{reference}"


def test_step_entity_types_stay_inside_the_subset(cube, step_options):
    text = S.render_step(cube, options=step_options).text
    kinds = {kind for kind, _line in _records(text).values()}
    assert kinds <= STEP_SUBSET


def test_step_is_deterministic(cube, step_options):
    first = S.render_step(cube, options=step_options)
    second = S.render_step(cube, options=step_options)
    assert first.sha256 == second.sha256
    assert first.text == second.text
    assert len(first.sha256) == 64


def test_step_has_no_wall_clock_and_honours_the_header(cube, step_options):
    text = S.render_step(
        cube, options=step_options, header=S.StepHeader(name="cube", time_stamp="")
    ).text
    assert "FILE_NAME('cube',''" in text
    assert re.search(r"FILE_DESCRIPTION\(\('%BR6 topology graph", text) is None
    assert "docs/agents/br6-graph-design.md" in text


def test_step_schema_identifiers(cube, step_options):
    ap214 = S.render_step(cube, options=step_options).text
    assert "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));" in ap214
    ap203 = S.render_step(
        cube, options=dataclasses.replace(step_options, schema="AP203")
    ).text
    assert "FILE_SCHEMA(('CONFIG_CONTROL_DESIGN'));" in ap203


def test_cylinder_writer_path_is_exercised_directly():
    # CYLINDRICAL_SURFACE is unreachable through both face modes (F1), but
    # §4.1 pins the entity, so the writer path is tested directly.
    writer = S._Writer()
    reference = S._emit_surface(
        writer,
        G.SurfaceReading(
            entity="CYLINDRICAL_SURFACE",
            label="candidate",
            claim="SRF-02",
            axis=(0.0, 0.0, 1.0),
            axis_point=(1.0, 2.0, 3.0),
            radius=4.5,
        ),
    )
    assert reference.startswith("#")
    assert writer.counts["CYLINDRICAL_SURFACE"] == 1
    assert writer.counts["AXIS2_PLACEMENT_3D"] == 1
    assert "CYLINDRICAL_SURFACE('',#4,4.5)" in "\n".join(writer.lines)


def test_step_never_emits_the_refused_surface_entities(cube, step_options):
    text = S.render_step(cube, options=step_options).text
    for banned in (
        "B_SPLINE",
        "TOROIDAL_SURFACE",
        "CONICAL_SURFACE",
        "SPHERICAL_SURFACE",
        "SURFACE_OF_REVOLUTION",
        "SURFACE_OF_LINEAR_EXTRUSION",
    ):
        assert banned not in text


def test_step_real_format_is_pinned():
    assert S._real(0.0, 9) == "0."
    assert S._real(-0.0, 9) == "0."
    assert S._real(1.0, 9) == "1."
    assert S._real(0.1 + 0.2, 12) == "0.3"
    assert S._real(1.5e-7, 12) == "1.5E-7"
    assert S._real(-2.0, 9) == "-2."


def test_step_negative_zero_coordinate_never_emits_dash_zero(step_options):
    points = [_f32(point) for point in CUBE]
    points[0] = (-0.0, -0.0, -0.0)
    faces = [
        _record(marker, refs, normal=normal) for marker, refs, normal in CUBE_FACES
    ]
    graph = _graph(points, faces)
    text = S.render_step(
        graph, options=dataclasses.replace(step_options, face_mode="exact")
    ).text
    assert "-0." not in text


def test_step_unit_comment_is_emitted(cube, step_options):
    text = S.render_step(cube, options=step_options).text
    assert "/* UNIT: caller-supplied MM; no model unit system decoded (U2 0/108) */" in text
    assert "(LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT(.MILLI.,.METRE.));" in text


def test_non_strict_returns_refusals_without_text(cube):
    export = S.render_step(cube, options=S.StepOptions(strict=False))
    assert export.text == ""
    assert export.refused
    assert all(v.code in S.REFUSAL_CLASSES for v in export.refused)


def test_write_step_writes_only_a_successful_render(cube, step_options, tmp_path):
    path = tmp_path / "cube.stp"
    export = S.write_step(cube, path, options=step_options)
    assert path.read_text(encoding="utf-8") == export.text
    refused = tmp_path / "refused.stp"
    with pytest.raises(ExportError):
        S.write_step(cube, refused, options=S.StepOptions())
    assert not refused.exists()


# --------------------------------------------------------------------
# Committed artifacts (claims CSV + evidence note)
# --------------------------------------------------------------------


def test_br6_graph_claims_csv_parses():
    assert CLAIMS_CSV.is_file(), f"missing {CLAIMS_CSV}"
    with CLAIMS_CSV.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == CLAIMS_FIELDS
    seen = set()
    for row in rows[1:]:
        assert len(row) == len(CLAIMS_FIELDS), f"ragged row: {row}"
        assert row[0].startswith("BR6G-"), row[0]
        assert row[0] not in seen, row[0]
        seen.add(row[0])
        rate = float(row[7])
        assert 0.0 <= rate <= 1.0
        if row[8]:
            float(row[8])
        assert row[2] in {"fact", "inference", "candidate", "unknown"}, row
        int(row[5])
        int(row[6])


def test_br6_graph_note_cites_only_committed_claim_ids():
    assert EVIDENCE_MD.is_file(), f"missing {EVIDENCE_MD}"
    with CLAIMS_CSV.open(newline="", encoding="utf-8") as handle:
        committed = {row["claim"].split("_")[0] for row in csv.DictReader(handle)}
    cited = set(re.findall(r"BR6G-\d+[a-z]?", EVIDENCE_MD.read_text(encoding="utf-8")))
    assert not cited - committed, sorted(cited - committed)


def test_br6_graph_note_cites_its_artifacts_and_honesty_lines():
    content = EVIDENCE_MD.read_text(encoding="utf-8")
    assert "br6-graph-claims.csv" in content
    assert "decode_brep_graph.py" in content
    assert "does NOT discriminate" in content
    assert "0/76" in content
    assert "+0x01 (1d)" in content
