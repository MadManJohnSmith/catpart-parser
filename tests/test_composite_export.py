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
    COMPOSITE_POOL_WALK,
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
    "geometry-composite-law-e0b-dup-pin",
    "geometry-composite-law-e0b-single-loop",
    "geometry-composite-law-e0b-nonplanar",
    "geometry-composite-law-e0b-normal-less",
    "geometry-composite-law-e0b-nonempty",
    "geometry-composite-law-e0b-multi-rep-conservative",
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
    walk-exact gap named, no PLY (fail-closed).  The stage-6 raw-array
    fallback runs on this signature and names its own gap too: a
    table-law payload is not a raw array (the array cannot even fit in
    this payload), so the store stays unexported with BOTH gaps."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-walk-mismatch"
    )
    assert code == 1
    error = json.loads(captured.err)
    assert error["error_class"] == "undecoded-variant"
    assert "walk-exact" in error["detail"]
    assert "raw-array law does not cover" in error["detail"]
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


@pytest.mark.parametrize(
    "variant",
    ["geometry-composite-law", "geometry-composite-law-raw-array"],
)
def test_composite_export_determinism(tmp_path, variant):
    """Two exports of the same composite fixture: byte-identical PLY
    (the table-walk and raw-array paths both pinned)."""
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


# --- stage-6: the walk-mismatch residue's raw-array law (stage-4a,
# integrated 2026-11-12, #34) -------------------------------------------

def test_composite_raw_array_exports(tmp_path, capsys):
    """The stage-4a raw-array law through the export seam: the walk
    overruns (no table, no write count — the declared P1t prefix does
    not describe the payload), the trail-escape condition pins start 40
    uniquely, the 12 raw triples are all-nice and x-ascending (strong
    fit), the pool re-lists verbatim -> the store exports closed with
    stage ``identity-raw-array`` and the raw anatomy in the info block."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-raw-array"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    validate(summary, load_schema("export-summary-v1"))
    info = summary["composite"]
    assert info["stage"] == "identity-raw-array"
    assert info["element_decl"] == 12
    assert info["node_points"] == 12
    assert info["curve_entries"] == 0
    assert info["raw_start"] == 40
    assert info["raw_nice_rate"] == 1.0
    assert info["raw_x_asc_rate"] == 1.0
    assert info["raw_trail_bytes"] == 9
    assert info["raw_count3"] == 480  # recorded, semantics open
    assert summary["vertex_count"] == 12
    assert summary["triangle_count"] == 12
    assert summary["degenerate_triangle_count"] == 0
    assert summary["mesh"]["manifold"] is True
    assert summary["mesh"]["closed"] is True
    # the PLY vertices are the raw triples in array order
    vertices, faces = parse_ply(ply_path)
    assert len(vertices) == 12
    assert len(faces) == 12
    for got, want in zip(vertices, COMPOSITE_POINTS):
        assert got == pytest.approx(want, abs=1e-6)


def test_composite_raw_array_wrong_offset_exports_via_flat_law(tmp_path, capsys):
    """The trail-escape byte one past every candidate start's array end:
    the stage-4a start rule pins nothing (0 selections — the raw law's
    fail-closed arm, pinned at unit level by
    test_composite_raw_array_start_rule_uniqueness).  DATED CORRECTION
    (stage 9, 2026-11-12): under the stage-8 composition the store no
    longer fails closed — the raw law declines it, and the flat law
    (start pinned by counts_end, NO escape required) decodes the same
    region, so the store exports with stage
    ``identity-mixedwrite-reps``.  The escape placement is irrelevant
    to the flat law by design (stage-8 artifact 3)."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-raw-array-wrong-offset"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    validate(summary, load_schema("export-summary-v1"))
    info = summary["composite"]
    assert info["stage"] == "identity-mixedwrite-reps"
    assert info["rep_laws"] == {"table": 0, "raw": 0, "flat": 1}
    assert summary["vertex_count"] == 12
    assert summary["triangle_count"] == 12
    assert summary["mesh"]["closed"] is True
    # the composition's raw arm still ran first and was declined: the
    # unit-level start rule stays fail-closed on this payload
    from catpart.geometry.composite import decode_raw_array
    from catpart.geometry.errors import ExportError
    from fixtures_gen import _composite_raw_node_payload

    with pytest.raises(ExportError) as exc:
        decode_raw_array(
            _composite_raw_node_payload(COMPOSITE_POINTS, escape="wrong"),
            12,
            COMPOSITE_POOL_WALK,
        )
    assert "raw-array start not pinned" in exc.value.detail
    assert "selects 0 of the 9 candidate starts" in exc.value.detail


def test_composite_raw_array_unabsorbed_stays_fail_closed(tmp_path, capsys):
    """Strong fit at the pinned start, but a 9th pool vertex the raw
    triples do not re-list: absorption is not established — fail-closed
    (the scan's 6/35 non-absorbed strong-fit stores).  Stage 9: the
    mixed-write composition runs after the raw decline and fails on the
    same ground — the 9th vertex is in no decoded rep region (the
    sub-node route's residue named, element indices unpinned)."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-raw-array-unabsorbed"
    )
    assert code == 1
    error = json.loads(captured.err)
    assert error["error_class"] == "undecoded-variant"
    assert "raw-array pool not absorbed" in error["detail"]
    assert "1 of 9 pool vertices" in error["detail"]
    assert "absent from every decoded rep region" in error["detail"]
    assert "05 08 01 sub-node records" in error["detail"]
    assert not ply_path.exists()


def test_composite_walk_nan_stays_out_of_the_raw_family(tmp_path, capsys):
    """The trigger-ordering pin: a walk-EXACT store with a non-finite
    coordinate is not the walk-mismatch family — the walk's own failure
    is re-raised and the raw-array law is never attempted (the probe
    walk ends exactly at the declared region, junk coordinates or not)."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-walk-nan"
    )
    assert code == 1
    error = json.loads(captured.err)
    assert error["error_class"] == "undecoded-variant"
    assert "non-finite" in error["detail"]
    assert "raw-array" not in error["detail"]
    assert not ply_path.exists()


def _raw_unit_payload(n, junk_y=(), junk_x=()):
    """A raw-array node payload of n ascending (x, 10, 30) triples with
    optional junk coordinates (1e8 y breaks nice; a -5.0 x breaks the
    ascending pairs around it)."""
    pts = []
    for i in range(n):
        x = -5.0 if i in junk_x else float(i)
        y = 1e8 if i in junk_y else 10.0
        pts.append((x, y, 30.0))
    from fixtures_gen import _composite_raw_node_payload

    return _composite_raw_node_payload(pts), pts


def test_composite_raw_array_fit_bar_both_directions():
    """The committed strong-fit bar (nice >= 0.98 AND x-ascending >=
    0.98 over the TRIPLES, the scan's per-triple rate) pinned in BOTH
    directions at the escape-pinned start: 49/50 nice (exactly 0.98) is
    strong fit, 48/50 (0.96) stays fail-closed — the stage-5 O1 lesson
    (a threshold guard must go red on removal AND narrowing)."""
    from catpart.geometry.composite import decode_raw_array
    from catpart.geometry.errors import ExportError

    payload, pts = _raw_unit_payload(50, junk_y=(3,))
    pool = [pts[i] for i in (0, 7, 13, 21, 29, 35, 42, 49)]
    points, info = decode_raw_array(payload, 50, pool)
    assert info["raw_start"] == 40
    assert info["raw_nice_rate"] == 0.98
    assert info["raw_x_asc_rate"] == 1.0
    assert len(points) == 50
    payload, pts = _raw_unit_payload(50, junk_y=(3, 4))
    with pytest.raises(ExportError) as exc:
        decode_raw_array(payload, 50, [pts[i] for i in (0, 7, 13, 21, 29, 35, 42, 49)])
    assert "weak fit" in exc.value.detail
    assert "0.9600" in exc.value.detail


def test_composite_raw_array_x_ascending_criterion():
    """The x-ascending half of the bar: one out-of-order x breaks the
    pair dropping into it (48/49 = 0.9796 < 0.98) while every
    coordinate stays nice — fail-closed, named."""
    from catpart.geometry.composite import decode_raw_array
    from catpart.geometry.errors import ExportError

    payload, pts = _raw_unit_payload(50, junk_x=(25,))
    with pytest.raises(ExportError) as exc:
        decode_raw_array(payload, 50, [pts[i] for i in (0, 7, 13, 21, 29, 35, 42, 49)])
    assert "weak fit" in exc.value.detail
    assert "0.9796" in exc.value.detail


def test_composite_raw_array_start_rule_uniqueness():
    """The committed start rule: the trail-escape condition must select
    EXACTLY ONE candidate start — two pinned starts stay fail-closed;
    so does elem_decl < 2 (the scan's ascending rate is undefined)."""
    from catpart.geometry.composite import decode_raw_array
    from catpart.geometry.errors import ExportError

    payload, pts = _raw_unit_payload(12)
    bytearray_payload = bytearray(payload)
    bytearray_payload[188] = 0xFF  # start 44's array end: a second pin
    with pytest.raises(ExportError) as exc:
        decode_raw_array(bytes(bytearray_payload), 12, pts)
    assert "selects 2 of the 9 candidate starts" in exc.value.detail

    payload, pts = _raw_unit_payload(1)
    with pytest.raises(ExportError) as exc:
        decode_raw_array(payload, 1, [pts[0]])
    assert "fit undefined" in exc.value.detail


def test_composite_raw_nice_boundaries_and_asc_tolerance():
    """The stage-6 review N2 pins (corpus-vacuous micro-arms): the
    scan's coordinate predicate boundaries — 0.0 is nice, the 1e-6
    floor and the 1e7 ceiling themselves are not, NaN is not — and the
    x-ascending pair tolerance: a 1e-7 regression still counts as
    ascending (b >= a - 1e-6), a 1e-5 regression drops the pair into
    the weak-fit arm."""
    from catpart.geometry.composite import _raw_nice, decode_raw_array
    from catpart.geometry.errors import ExportError

    assert _raw_nice(0.0)
    assert _raw_nice(5.0)
    assert not _raw_nice(float("nan"))
    assert not _raw_nice(1e-6)  # the floor itself: not nice
    assert _raw_nice(2e-6)  # just above it: nice
    assert not _raw_nice(1e7)  # the ceiling itself: not nice
    assert _raw_nice(1e7 - 1.0)  # just below it: nice

    def dip_payload(dip: float) -> bytes:
        base = 0.001
        xs = [base, base - dip, base]  # one regressing pair
        span = b"".join(struct.pack("<fff", x, 0.0, 0.0) for x in xs)
        return b"\x00" * 32 + span + b"\xff"  # escape pins start 32

    # f32 near 0.001 has ulp ~1.2e-10, so both dips survive the round
    # trip as distinct values; the 1e-7 dip sits inside the 1e-6
    # tolerance, the 1e-5 dip outside it.
    points, info = decode_raw_array(dip_payload(1e-7), 3, [])
    assert info["raw_x_asc_rate"] == 1.0
    assert points[1][0] < points[0][0]
    with pytest.raises(ExportError) as exc:
        decode_raw_array(dip_payload(1e-5), 3, [])
    assert "weak fit" in exc.value.detail
    assert "x-ascending 0.5000" in exc.value.detail


def test_walk_mismatch_signature():
    """The census probe's walk semantics (the trigger's signature test):
    a walk-exact payload is NOT the family (None — junk coordinates do
    not matter to the probe walk), a lying write count mismatches
    (delta_words != 0), a truncated payload raises the layout_error
    arm."""
    from fixtures_gen import (
        _composite_elements,
        _composite_node_payload,
    )

    from catpart.geometry.composite import _walk_mismatch

    elements = _composite_elements(list(COMPOSITE_POINTS))
    exact = _composite_node_payload(elements)
    assert _walk_mismatch(exact, len(COMPOSITE_POINTS)) is None
    lying = _composite_node_payload(elements, write_count_override=19)
    profile = _walk_mismatch(lying, len(COMPOSITE_POINTS))
    assert profile is not None and "layout_error" not in profile
    assert profile["delta_words"] != 0
    truncated = _composite_node_payload(elements)[:-10]
    profile = _walk_mismatch(truncated, len(COMPOSITE_POINTS))
    assert profile is not None and "overruns" in profile["layout_error"]


# --- stage 9: the stage-8 mixed-write locator/predicate artifacts ------


def test_composite_strip_false_match_exports_via_full_body_scan(tmp_path, capsys):
    """Stage-8 artifact 1 (the mass's root cause): the 13th triple's
    (y, z) bytes contain the STRIP_RE sequence ``01 45 00 ff`` (two
    adjacent NICE floats, 2064.0 and ~35.97), so the single-rep window
    truncates the node mid-region: the primary walk raises, the raw
    law's 12*elem_decl span no longer fits the truncated payload (0
    escape candidates — the ccbb7862 start-unpinned shape) and the
    store stays fail-closed WITHOUT the fix.  The stage-8 composition's
    full-body per-rep scan recovers the region: on the FULL payload the
    flat law decodes (the raw escape rule finds TWO candidates — the
    facet record's own ``01 4A 01 FF`` header pins a second one — so
    the census law order falls through to flat), the pool absorbs, the
    store exports closed with stage ``identity-mixedwrite-reps``."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-raw-array-strip-false-match"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    validate(summary, load_schema("export-summary-v1"))
    info = summary["composite"]
    assert info["stage"] == "identity-mixedwrite-reps"
    assert info["rep_laws"] == {"table": 0, "raw": 0, "flat": 1}
    assert info["element_decl"] == 13
    assert summary["vertex_count"] == 13
    assert summary["triangle_count"] == 12
    assert summary["mesh"]["manifold"] is True
    assert summary["mesh"]["closed"] is True
    # the truncated-window locator really does cut the node mid-region
    # (the false match sits inside the 13th triple), and the raw law
    # really is declined on the truncated payload
    from catpart.geometry import composite
    from catpart.geometry.errors import ExportError
    from fixtures_gen import (
        STRIP_FALSE_MATCH_Y,
        STRIP_FALSE_MATCH_Z,
        _composite_raw_node_payload,
    )

    payload = _composite_raw_node_payload(
        list(COMPOSITE_POINTS) + [(30.0, STRIP_FALSE_MATCH_Y, STRIP_FALSE_MATCH_Z)]
    )
    match = composite.STRIP_RE.search(payload, 40)
    assert match is not None and 40 < match.start() < 40 + 12 * 13
    with pytest.raises(ExportError) as exc:
        composite.decode_raw_array(payload[: match.start()], 13, COMPOSITE_POOL_WALK)
    assert "raw-array start not pinned" in exc.value.detail


def test_composite_table_overshoot_exports_via_extent_law(tmp_path, capsys):
    """Stage-8 artifact 2: the region opens with 20 full-write slots, so
    the 2-bit table's own leading bytes are zero and the committed
    layout() zero-group skip overshoots INTO the table — the count
    reads a region byte and the walk fails ("0 left of the declared 0",
    the 221df959 shape).  The stage-8 extent law selects the unique
    walk-exact extent (the true table at counts_end + 4; the shifted
    extent overruns) -> the store exports with stage
    ``identity-mixedwrite-reps`` and a table rep."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-table-overshoot"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    validate(summary, load_schema("export-summary-v1"))
    info = summary["composite"]
    assert info["stage"] == "identity-mixedwrite-reps"
    assert info["rep_laws"] == {"table": 1, "raw": 0, "flat": 0}
    assert info["element_decl"] == 20
    assert summary["vertex_count"] == 20
    assert summary["triangle_count"] == 12
    assert summary["mesh"]["closed"] is True


def test_table_decode_extents_both_directions():
    """The extent law in both directions: on a NO-overshoot payload
    (the table's first group non-zero) the unique extent equals the
    committed skip position and the decode matches decode_region's; on
    the overshoot payload the committed position is misaligned (the
    primary walk raises) and the law recovers the true extent.  The
    ambiguity arm (several walk-exact extents stay fail-closed) is
    measured corpus-vacuous by the stage-8 census (all 133 table reps
    resolve at a unique extent) and is not synthesizable without
    crafting a shifted-nice region — the census measurement is the
    pin."""
    from fixtures_gen import _composite_elements, _composite_node_payload

    from catpart.geometry.composite import (
        _table_decode_extents,
        decode_region,
    )
    from catpart.geometry.errors import ExportError

    # no overshoot: the standard 12-point table store
    elements = _composite_elements(list(COMPOSITE_POINTS))
    payload = _composite_node_payload(elements)
    td = _table_decode_extents(payload, 12, 36)
    assert td is not None and td[0] != "ambiguous"
    _e, td_elements, _skips, region_end, wc = td
    assert _e == 1
    ref_elements, ref_info = decode_region(payload, 12)
    assert td_elements == ref_elements
    assert region_end == ref_info["walk_end"]
    assert wc == ref_info["write_count"]

    # overshoot: the 20-full-write store's node payload — the primary
    # walk raises, the extent law recovers the true table
    corner_idx = (0, 2, 3, 5, 6, 8, 9, 11)
    points = []
    for i in range(20):
        if i in corner_idx:
            k = corner_idx.index(i)
            y = 10.0 if k in (0, 1, 4, 5) else 110.0
            z = 0.0 if k in (0, 1, 2, 3) else 60.0
            points.append((1.0 + 3.0 * i, y, z))
        else:
            points.append((1.0 + 3.0 * i, 50.0, 30.0))
    big = _composite_node_payload(_composite_elements(points))
    with pytest.raises(ExportError):
        decode_region(big, 20)
    td = _table_decode_extents(big, 20, 36)
    assert td is not None and td[0] != "ambiguous"
    e, td_elements, skips, region_end, wc = td
    assert e == 1  # the TRUE table (the committed skip ate it + the table)
    assert len(td_elements) == 20
    assert skips == 0
    assert all(pt is not None for _v, pt in td_elements)
    assert wc == 60


def test_composite_flat_law_near_zero_coordinates(tmp_path, capsys):
    """Stage-8 artifact 3: the four non-pool triples carry near-zero
    coordinates (|v| ~ 1e-14, the note's measured 7d27c73d/dd610ca5
    values) — the raw law's 1e-6 floor weak-fits (nice 8/12 = 0.667 <
    0.98, the d51eb38c shape) and declines; the flat law (start pinned
    by counts_end, NO escape required, the exporter predicate) decodes
    the same region and the store exports with stage
    ``identity-mixedwrite-reps``."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-flat-near-zero"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    validate(summary, load_schema("export-summary-v1"))
    info = summary["composite"]
    assert info["stage"] == "identity-mixedwrite-reps"
    assert info["rep_laws"] == {"table": 0, "raw": 0, "flat": 1}
    assert summary["vertex_count"] == 12
    assert summary["triangle_count"] == 12
    assert summary["mesh"]["closed"] is True
    # the raw law really does weak-fit at the pinned start while the
    # exporter predicate accepts every coordinate
    from catpart.geometry.composite import _nice, _raw_nice, decode_raw_array
    from catpart.geometry.errors import ExportError
    from fixtures_gen import NEAR_ZERO_A, _composite_raw_node_payload

    assert not _raw_nice(NEAR_ZERO_A)
    assert _nice(NEAR_ZERO_A)
    points = list(COMPOSITE_POINTS)
    points[1] = (points[1][0], NEAR_ZERO_A, points[1][2])
    payload = _composite_raw_node_payload(points)
    with pytest.raises(ExportError) as exc:
        decode_raw_array(payload, 12, COMPOSITE_POOL_WALK)
    assert "weak fit" in exc.value.detail
    assert "nice 0.9167" in exc.value.detail


def test_composite_mixedwrite_multi_rep_exports_merged(tmp_path, capsys):
    """The stage-9 composition on a multi-part store: two raw-layout
    reps (the single-rep walk raises; the raw-array law declines the
    store — the concatenated pool spans both groups and no single
    region re-lists it all); the composition decodes both nodes on the
    full-body window, absorbs each pool group by its diagonal rep's
    region and exports both boxes merged (24 vertices, 24 triangles,
    closed — the stage-5 merge shape on the walk-mismatch path)."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-mixedwrite-multi-rep"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    validate(summary, load_schema("export-summary-v1"))
    info = summary["composite"]
    assert info["stage"] == "identity-mixedwrite-reps"
    assert info["rep_laws"] == {"table": 0, "raw": 0, "flat": 2}
    assert info["reps_decoded"] == 2
    assert info["reps_exported"] == 2
    assert info["reps_unexported"] == 0
    assert info["element_decl"] == 24
    assert summary["vertex_count"] == 24
    assert summary["triangle_count"] == 24
    assert summary["mesh"]["manifold"] is True
    assert summary["mesh"]["closed"] is True
    _, faces = parse_ply(ply_path)
    assert sum(1 for f in faces if all(i < 12 for i in f)) == 12
    assert sum(1 for f in faces if all(i >= 12 for i in f)) == 12


def test_composite_mixedwrite_subnode_stays_fail_closed(tmp_path, capsys):
    """The stage-8 note's integration item (e): rep 1's pool carries a
    9th vertex no decoded region re-lists (the 05 08 01 sub-node
    records' residue) — its element index is unpinned, so the store
    stays fail-closed for export with the gap named (the corpus
    bad44bdf class; the composition never guesses coordinates)."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-mixedwrite-multi-rep-subnode"
    )
    assert code == 1
    error = json.loads(captured.err)
    assert error["error_class"] == "undecoded-variant"
    assert "does not establish pool absorption" in error["detail"]
    assert "1 of 17 pool vertices" in error["detail"]
    assert "05 08 01 sub-node records" in error["detail"]
    assert not ply_path.exists()


# --- stage 10: the E0-b dup-pin law (the curve-entry coordinates,
# restricted per the landed analysis U4-stage5-recommendation) ----------


def test_composite_e0b_dup_pin_exports_pinned_loops(tmp_path, capsys):
    """The stage-10 E0-b positive (the 2fca9bc4/505bbe1f corpus shape):
    the store's primary triangulation is EMPTY (its only facet record's
    two loops reference skip slots) and both dropped loops are
    normal-carrying and coplanar with the dup-pinned coordinates — the
    law fires: the loops export with each skip slot welded to the
    written vertex of its immediately preceding written element (no new
    vertices; the exported faces are the pinned fans over the written
    ranks).  Removing the law leaves this store empty-mesh — red."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-e0b-dup-pin"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    validate(summary, load_schema("export-summary-v1"))
    info = summary["composite"]
    assert info["curve_entries"] == 3
    assert info["loops_curve_entry"] == 0  # nothing stays dropped
    assert info["loops_curve_entry_exported"] == 2
    assert info["loops_exported"] == 2
    assert info["curve_entry_law"] == "e0b-dup-pin"
    assert summary["vertex_count"] == 12  # the weld adds no vertices
    assert summary["triangle_count"] == 4
    assert summary["degenerate_triangle_count"] == 0
    assert summary["mesh"]["manifold"] is True
    classes = _warning_classes(summary)
    assert "curve-entry-loops-unexported" not in classes
    assert "curve-entry-loops-exported-dup-pin" in classes
    # the pinned fans, in written ranks: skip 2 -> element 1 (P1),
    # skip 6 -> element 5 (P4) — the WELD, pinned by the face indices
    # (each fan originates at the pin target's written rank)
    _, faces = parse_ply(ply_path)
    assert sorted(faces) == [(1, 0, 6), (1, 6, 2), (4, 3, 9), (4, 9, 5)]


def test_composite_e0b_single_loop_exports_pinned(tmp_path, capsys):
    """The one-dropped-loop positive (the 4ad53b87/4ae0392d shape): a
    single coplanar loop fires the law on an otherwise-empty store."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-e0b-single-loop"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    info = summary["composite"]
    assert info["loops_curve_entry"] == 0
    assert info["loops_curve_entry_exported"] == 1
    assert info["curve_entry_law"] == "e0b-dup-pin"
    assert summary["triangle_count"] == 2
    _, faces = parse_ply(ply_path)
    assert sorted(faces) == [(1, 0, 6), (1, 6, 2)]


def test_composite_e0b_nonplanar_loop_keeps_conservative(tmp_path, capsys):
    """The 3dff4d93 pin: one coplanar + one NONPLANAR dropped loop —
    the battery is not fully green, so the WHOLE store keeps the
    conservative non-export rule (fail-closed, gap named).  Applying
    the law without the battery (removing the conservative gate) would
    export the pinned loops here — red."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-e0b-nonplanar"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    info = summary["composite"]
    assert info["loops_curve_entry"] == 2
    assert "curve_entry_law" not in info
    assert summary["triangle_count"] == 0  # stays empty-mesh
    classes = _warning_classes(summary)
    assert "curve-entry-loops-unexported" in classes
    assert "curve-entry-loops-exported-dup-pin" not in classes


def test_composite_e0b_normal_less_loop_keeps_conservative(tmp_path, capsys):
    """The 08f2eccb mixed-coverage pin: one coplanar loop + one on a
    NORMAL-LESS 0x42 strip — the untestable loop keeps the store on the
    conservative rule (the battery cannot cover it; coverage not full).
    Removing the coverage requirement would fire here — red."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-e0b-normal-less"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    info = summary["composite"]
    assert info["loops_curve_entry"] == 2
    assert "curve_entry_law" not in info
    assert summary["triangle_count"] == 0
    assert "curve-entry-loops-unexported" in _warning_classes(summary)


def test_composite_e0b_nonempty_stays_conservative(tmp_path, capsys):
    """The 471-passing-stores pin (the conservative gate's DOWNSIDE
    direction): the box exports its 12 triangles AND carries a
    battery-supported dropped loop — the store's mesh is not empty, so
    the law must NOT fire (a fire could flip a passing store's L2
    state).  Removing the empty-mesh condition adds the pinned
    triangles here (12 -> 14) — red."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-e0b-nonempty"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    info = summary["composite"]
    assert summary["triangle_count"] == 12  # NOT 14
    assert summary["mesh"]["closed"] is True
    assert info["loops_curve_entry"] == 1
    assert "curve_entry_law" not in info
    assert "curve-entry-loops-unexported" in _warning_classes(summary)


def test_composite_e0b_multi_rep_store_gate(tmp_path, capsys):
    """The per-rep paths' store-level gate: rep 0 exports its box, rep 1
    carries a battery-supported dropped loop on an empty rep — the
    store's merged mesh is not empty, so no rep fires (a per-rep gate
    would add rep 1's pinned triangles to an otherwise-passing store —
    red)."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-e0b-multi-rep-conservative"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    info = summary["composite"]
    assert info["stage"] == "identity-per-rep"
    assert info["reps_decoded"] == 2
    assert info["reps_exported"] == 2
    assert summary["triangle_count"] == 12  # NOT 14
    assert summary["mesh"]["closed"] is True
    assert info["loops_curve_entry"] == 1
    assert "curve_entry_law" not in info
    assert "curve-entry-loops-unexported" in _warning_classes(summary)
