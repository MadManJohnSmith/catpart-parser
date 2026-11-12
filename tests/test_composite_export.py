"""Composite-law export (G6 stages 2c->3d, #34).

The synthetic composite fixtures (small + big form, both with a 2-bit
table) through the CLI export seam: the point region decodes through
the deterministic table walk, the facet references resolve as 0-based
element indices in region order (the identity — no sigma search), the
PLY carries the written coordinates, the mesh invariants hold, and
every law gap keeps its ``undecoded-variant`` classification with the
specific gap named (fail-closed).  The law's shapes have their own
fixtures: slanted corner quads (coplanar vs the stored normal, not
axis-constant), loops referencing skip slots (curve entries, U4), and
the no-repeated-refs width rule.  Determinism: same inputs,
byte-identical fixtures and PLY.
"""

from __future__ import annotations

import json
import math
import struct
from pathlib import Path

import pytest

from catpart.geometry.composite import parse_strip_records
from catpart.schema import load_schema
from catpart.schema.validate import validate
from fixtures_gen import (
    COMPOSITE_FACES,
    COMPOSITE_GRID_SIDE,
    COMPOSITE_POINTS,
    build_fixture,
)

COMPOSITE_VARIANTS = (
    "geometry-composite-law",
    "geometry-composite-law-big",
    "geometry-composite-law-slanted",
    "geometry-composite-law-curve-entries",
    "geometry-composite-law-u16be",
    "geometry-composite-law-walk-mismatch",
    "geometry-composite-law-unabsorbed",
)


def run_export(tmp_path: Path, capsys, variant: str):
    """Export one composite variant; return (code, captured, ply_path)."""
    from catpart.cli import main_export

    path = tmp_path / "sample.CATPart"
    path.write_bytes(build_fixture("part", seed=7, variant=variant))
    code = main_export([str(path)])
    captured = capsys.readouterr()
    return code, captured, path.with_suffix(".ply")


def parse_ply(path: Path):
    raw = path.read_bytes()
    marker = b"end_header\n"
    head, body = raw.split(marker, 1)
    text = head.decode("ascii")
    n_vertices = int(
        next(
            ln
            for ln in text.splitlines()
            if "element vertex" in ln
        ).split()[-1]
    )
    n_faces = int(
        next(
            ln for ln in text.splitlines() if "element face" in ln
        ).split()[-1]
    )
    vertices = []
    off = 0
    for _ in range(n_vertices):
        vertices.append(struct.unpack_from("<fff", body, off))
        off += 12
    faces = []
    for _ in range(n_faces):
        cnt = body[off]
        idx = struct.unpack_from(f"<{cnt}i", body, off + 1)
        faces.append(tuple(idx))
        off += 1 + 4 * cnt
    return vertices, faces


def _warning_classes(summary) -> list[str]:
    return [w["class"] for w in summary["warnings"]]


@pytest.mark.parametrize("seed", [7, 0])
def test_composite_fixture_exports_closed_manifold(tmp_path, capsys, seed):
    code, captured, ply_path = run_export(tmp_path, capsys, "geometry-composite-law")
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    validate(summary, load_schema("export-summary-v1"))
    assert summary["vertex_count"] == len(COMPOSITE_POINTS)
    assert summary["triangle_count"] == 12
    assert summary["degenerate_triangle_count"] == 0
    assert summary["mesh"]["manifold"] is True
    assert summary["mesh"]["closed"] is True
    assert summary["mesh"]["oriented"] is True
    # the composite info block rides the summary additively: the
    # identity decode's counters (element space == written points,
    # curve entries 0, the walk's declared count 17 f32 words)
    info = summary["composite"]
    assert info["stage"] == "identity-table-walk"
    assert info["element_decl"] == len(COMPOSITE_POINTS)
    assert info["node_points"] == len(COMPOSITE_POINTS)
    assert info["curve_entries"] == 0
    assert info["write_count"] == 17
    assert info["loops_curve_entry"] == 0
    assert info["loops_exported"] == 6
    assert info["facet_candidates"] == 6
    assert info["facet_records"] == 6
    # the PLY carries the written coordinates in region order
    vertices, faces = parse_ply(ply_path)
    assert len(vertices) == len(COMPOSITE_POINTS)
    assert len(faces) == 12
    for got, want in zip(vertices, COMPOSITE_POINTS):
        assert got == pytest.approx(want, abs=1e-6)
    for tri in faces:
        assert all(0 <= i < len(COMPOSITE_POINTS) for i in tri)


def test_composite_vertex_order_is_the_region_order(tmp_path, capsys):
    """The PLY vertex order is the region order: the table's first slot
    opens [y][z] on the origin LCP state (the fixture's list opens
    (0, 10, 0), not the pool's (0, 10, 0) walk head — the pool walk is
    deliberately non-lex) and the writes reconstruct the lex list."""
    code, captured, ply_path = run_export(tmp_path, capsys, "geometry-composite-law")
    assert code == 0, captured.err
    vertices, _ = parse_ply(ply_path)
    assert vertices[0] == pytest.approx((0.0, 10.0, 0.0), abs=1e-6)
    assert vertices[1] == pytest.approx((0.0, 10.0, 30.0), abs=1e-6)
    assert vertices[6] == pytest.approx((20.0, 10.0, 0.0), abs=1e-6)


def test_composite_big_form_exports_closed_manifold(tmp_path, capsys):
    """The big form decodes under the same single-table law: 1,000
    elements, the write count 1,108 riding the ff-escape P1g count,
    u16be references, the pool absorbed, the box closed."""
    code, captured, ply_path = run_export(tmp_path, capsys, "geometry-composite-law-big")
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    n = COMPOSITE_GRID_SIDE**3
    assert summary["vertex_count"] == n
    assert summary["triangle_count"] == 12
    assert summary["degenerate_triangle_count"] == 0
    assert summary["mesh"]["manifold"] is True
    assert summary["mesh"]["closed"] is True
    info = summary["composite"]
    assert info["element_decl"] == n
    assert info["node_points"] == n
    assert info["curve_entries"] == 0
    assert info["write_count"] == 1108
    assert info["table_bytes"] == n // 4
    # the 8 grid corners are pool vertices (absorbed) and land at their
    # lex positions; the unused grid interior warns
    vertices, _ = parse_ply(ply_path)
    for x in (0.0, 9.0):
        for y in (0.0, 9.0):
            for z in (0.0, 9.0):
                assert (x, y, z) in vertices
    assert "unused-pool-vertices" in _warning_classes(summary)


def test_composite_slanted_quad_exports_under_coplanar_normal_law(tmp_path, capsys):
    """The plane law is coplanarity against the stored normal: the
    slanted corner quad (normal (120, -1200, -40), no axis-constant
    coordinate) exports — the axis-constant reading rejected exactly
    this shape (stage-3b correction, 2026-11-11)."""
    code, captured, ply_path = run_export(tmp_path, capsys, "geometry-composite-law-slanted")
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    assert summary["triangle_count"] == 12
    assert summary["mesh"]["closed"] is True
    vertices, _ = parse_ply(ply_path)
    quad = [
        v for v in vertices
        if v in (
            (20.0, 12.0, 0.0), (20.0, 10.0, 60.0),
            (0.0, 10.0, 0.0), (0.0, 8.0, 60.0),
        )
    ]
    assert len(quad) == 4
    # no axis-constant coordinate: the old dominant-axis law fails here
    assert len({p[1] for p in quad}) > 1
    # coplanarity against the stored normal (normalized residual ~ 0)
    normal = (120.0, -1200.0, -40.0)
    nn = math.sqrt(sum(c * c for c in normal))
    p0 = quad[0]
    residuals = [
        abs(sum((p[i] - p0[i]) * normal[i] for i in range(3))) / nn
        for p in quad[1:]
    ]
    assert max(residuals) < 2e-3


def test_composite_curve_entry_loops_named_not_guessed(tmp_path, capsys):
    """Loops referencing skip slots (curve entries) are not exported —
    the entries' coordinates live in the curve records (U4, open) —
    and the gap is named; the store's other loops export."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-curve-entries"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    info = summary["composite"]
    assert info["element_decl"] == 15
    assert info["node_points"] == 12
    assert info["curve_entries"] == 3
    assert info["loops_curve_entry"] == 1
    assert info["loops_exported"] == 6
    assert "curve-entry-loops-unexported" in _warning_classes(summary)
    # the box's 12 triangles export; the curve-entry loop adds none
    assert summary["triangle_count"] == 12
    assert summary["mesh"]["closed"] is True


def test_composite_u16be_no_repeat_width_rule(tmp_path, capsys):
    """The stage-3b no-repeated-refs rule: the fixture record's u8
    misread (k=5, counts 4,0,0,0,0, refs (3,1,3,2)) tiles exactly but
    repeats refs inside the loop; the u16be parse (refs (1, 258, 769,
    770), distinct) wins, and the fan triangulates from the true
    references."""
    code, captured, ply_path = run_export(tmp_path, capsys, "geometry-composite-law-u16be")
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    # 12 box triangles + the u16be record's 2-triangle fan
    assert summary["triangle_count"] == 14
    assert summary["degenerate_triangle_count"] == 0
    _, faces = parse_ply(ply_path)
    assert (1, 258, 769) in faces
    assert (1, 769, 770) in faces


def test_composite_walk_mismatch_stays_undecoded(tmp_path, capsys):
    """The declared write count exceeds what the table encodes: the
    walk is not exact — classified undecoded-variant with the
    walk-exact gap named, no PLY (fail-closed)."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-walk-mismatch"
    )
    assert code == 1
    error = json.loads(captured.err)
    assert error["error_class"] == "undecoded-variant"
    assert "walk-exact" in error["detail"]
    assert not ply_path.exists()


def test_composite_unabsorbed_pool_stays_undecoded(tmp_path, capsys):
    """A pool vertex the node list does not re-list: the pool
    absorption is not established there — classified
    undecoded-variant, no PLY."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-unabsorbed"
    )
    assert code == 1
    error = json.loads(captured.err)
    assert error["error_class"] == "undecoded-variant"
    assert "unabsorbed" in error["detail"]
    assert not ply_path.exists()


@pytest.mark.parametrize("variant", COMPOSITE_VARIANTS)
def test_composite_fixtures_deterministic(variant):
    a = build_fixture("part", seed=3, variant=variant)
    b = build_fixture("part", seed=3, variant=variant)
    assert a == b


def test_composite_export_determinism(tmp_path):
    """Two exports of the same composite fixture: byte-identical PLY."""
    import os

    from catpart.geometry import build_export

    ply_a = tmp_path / "a.ply"
    ply_b = tmp_path / "b.ply"
    fixture = build_fixture("part", seed=5, variant="geometry-composite-law")
    fa, fb = tmp_path / "a.CATPart", tmp_path / "b.CATPart"
    fa.write_bytes(fixture)
    fb.write_bytes(fixture)
    build_export(fa, ply_a)
    build_export(fb, ply_b)
    assert ply_a.read_bytes() == ply_b.read_bytes()
    assert os.stat(ply_a).st_size > 0


def test_composite_face_records_exercise_both_families():
    """The fixture's record set mirrors the clean box's shape: four 0x4a
    strips and two 0x4c polygons, so the composite path exercises both
    exported primitive families."""
    markers = sorted(mk for mk, _n, _r in COMPOSITE_FACES)
    assert markers == [0x4A, 0x4A, 0x4A, 0x4A, 0x4C, 0x4C]


def test_composite_u24be_width_law(tmp_path, capsys):
    """The stage-4b u24be width law (gap 1): the 65,600-element grid
    (> 65,535 — 2-byte refs cannot index the top corners at 65,599)
    exports: the face records tile exactly only at width 3, so the
    u24be parse wins and the box exports closed (13bb5c0c's law,
    docs/evidence/2026-11-11-per-rep-and-width-laws.md R10)."""
    code, captured, ply_path = run_export(tmp_path, capsys, "geometry-composite-law-u24be")
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    nx, ny, nz = (40, 40, 41)
    n = nx * ny * nz
    assert n > 65_535
    assert summary["vertex_count"] == n
    assert summary["triangle_count"] == 12
    assert summary["mesh"]["manifold"] is True
    assert summary["mesh"]["closed"] is True
    info = summary["composite"]
    assert info["element_decl"] == n
    assert info["table_bytes"] == (n + 3) // 4
    assert info["node_bytes"] > 4096  # the big-form marker
    # the PLY faces reference the >65,535 corners (u24be refs decoded)
    _, faces = parse_ply(ply_path)
    assert max(i for f in faces for i in f) == 65_599


def test_composite_width_plane_tiebreak(tmp_path, capsys):
    """The stage-4b plane tiebreak (width gap 2): the fixture record's
    u8/u16be parses tie on (tiling, repeats, oob) over the interleaved
    filler bytes; the u8 read (0, 10, 1, 4) is nonplanar against the
    stored normal (0,0,1), the u16be read (10, 260, 520, 770) coplanar
    (all z=0) — the plane law picks u16be (ef30cb2f's law, R11)."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-width-plane"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    # 12 box triangles + the extra record's 2-triangle strip
    assert summary["triangle_count"] == 14
    assert summary["degenerate_triangle_count"] == 0
    assert summary["mesh"]["manifold"] is True
    _, faces = parse_ply(ply_path)
    # the u16be reading's triangles; the u8 misread (0, 10, 1, 4)
    # would reference element 1, which no face does
    assert (10, 260, 520) in faces
    assert (770, 520, 260) in faces
    assert all(1 not in f for f in faces)


def test_composite_multi_rep_exports_merged(tmp_path, capsys):
    """The stage-4b per-rep decomposition law (R1-R3): rep k = (the
    k-th pool group, the k-th walk-exact node, that node's record
    territory); the stage-3d single-rep reading fails absorption on
    the two-rep store, the per-rep reading exports both reps' boxes
    merged (24 vertices, 24 triangles, closed)."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-multi-rep"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    assert summary["vertex_count"] == 24
    assert summary["triangle_count"] == 24
    assert summary["mesh"]["manifold"] is True
    assert summary["mesh"]["closed"] is True
    info = summary["composite"]
    assert info["stage"] == "identity-per-rep"
    assert info["reps_decoded"] == 2
    assert info["reps_exported"] == 2
    assert info["reps_unexported"] == 0
    assert info["element_decl"] == 24
    assert info["node_points"] == 24
    assert info["facet_records"] == 12
    assert info["node_bytes"] > 0
    _, faces = parse_ply(ply_path)
    # each rep's box exports over its own element space, offset by the
    # merged written-point base (rep 1 starts at written point 12)
    assert sum(1 for f in faces if all(i < 12 for i in f)) == 12
    assert sum(1 for f in faces if all(i >= 12 for i in f)) == 12


def test_composite_multi_rep_partial_stays_fail_closed_per_rep(tmp_path, capsys):
    """A rep whose pool does not absorb stays unexported — no guessing
    (per-rep fail-closed): rep 1's pool carries a 9th vertex no region
    re-lists, so only rep 0's box exports and the gap is named."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-multi-rep-partial"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    assert summary["vertex_count"] == 12
    assert summary["triangle_count"] == 12
    assert summary["mesh"]["closed"] is True
    info = summary["composite"]
    assert info["stage"] == "identity-per-rep"
    assert info["reps_exported"] == 1
    assert info["reps_unexported"] == 1
    assert any("not re-listed" in r for r in info["rep_reasons"])


def test_composite_single_rep_node_bytes_in_summary(tmp_path, capsys):
    """The stage-5 fold-in: ``node_bytes`` rides the composite info
    block additively (the list node's payload byte length; > 4096
    marks the big-form family), schema-valid."""
    code, captured, _ply_path = run_export(tmp_path, capsys, "geometry-composite-law")
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    validate(summary, load_schema("export-summary-v1"))
    info = summary["composite"]
    assert isinstance(info["node_bytes"], int)
    assert info["node_bytes"] <= 4096  # small form


def test_composite_u24be_candidate_is_threshold_gated():
    """The stage-5 review O1 pin: the u24be candidate exists ONLY above
    65,535 elements — and the suite must go red if the guard is
    removed OR narrowed.  The bytes below tile exactly at u24be (4 x
    [00 01 00], one count byte summing to n) and only at u24be; the
    2-byte parse falls short of the next header.  Below the threshold
    the 3-byte read is 256s past a 100-element space, so the guard is
    what keeps the OOB junk out of the candidate set (the corpus gate
    event: 4 exported stores flipped when u24be was offered
    unconditionally); above it the same parse is in-bounds and must be
    offered (a narrowed guard would pin the store to a non-tiling
    misread)."""
    rec = (
        bytes([0x01, 0x41, 0x01, 0xFF])
        + struct.pack("<I", 4)
        + bytes([4])
        + bytes([0x00, 0x01, 0x00] * 4)
    )
    # Below the threshold: no candidate may carry out-of-space refs.
    records, n_hdrs = parse_strip_records(rec, 0, len(rec), 100)
    assert n_hdrs == 1
    assert records
    for _o, _mk, _normal, _counts, refs, width in records:
        assert width in (1, 2)
        assert all(r < 100 for r in refs)
    # Above it: the tiling u24be parse is in-bounds and must win.
    records, n_hdrs = parse_strip_records(rec, 0, len(rec), 70_000)
    assert n_hdrs == 1
    assert records
    assert [w for _o, _mk, _n, _c, _r, w in records] == [3]
    assert all(r < 70_000 for _o, _mk, _n, _c, refs, _w in records for r in refs)
