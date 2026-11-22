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

from catpart.geometry import composite, mesh
from catpart.geometry.composite import parse_strip_records
from catpart.geometry.store import StoreSpan
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
    "geometry-composite-law-e0b-mesh-guard",
    "geometry-composite-law-e0b-multi-rep-conservative",
    "geometry-composite-law-e0b-nonplanar-refused",
    "geometry-composite-law-e0b-multi-rep-relaxed",
    "geometry-composite-law-dedup-unordered",
    "geometry-composite-law-dedup-manifold-no-fire",
    "geometry-composite-law-dedup-declined",
    "geometry-composite-law-dedup-degenerate",
    "geometry-composite-law-dedup-coord-relist",
    "geometry-composite-law-primary-seam-tiny",
    "geometry-composite-law-primary-seam-declined",
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


# --- #66 (2026-11-20): the short-form refs gate and the 0x41/0x44
# primitive (OOB fail-closed rank + u16le/u8) -----------------------------

def _strip_record(marker: int, n: int, counts: bytes, ref_bytes: bytes) -> bytes:
    return (
        bytes([0x01, marker, 1, 0xFF])
        + struct.pack("<I", n)
        + counts
        + ref_bytes
    )


def test_composite_short_vote_ranks_oob_before_repeats():
    """#66 pin: the in-bounds candidate wins even when it repeats refs.

    The old rank (exact, repeats, oob, ...) picked the w2be candidate:
    it does not repeat (0x0708/0x0709/0x0506 and 0x010a/0x010b/0x010c
    are distinct) while the w1 candidate repeats 7 — and all six w2
    refs are >= 100, i.e. out of the element space. The committed gate
    ranks oob first and then declines the winner if it is still OOB,
    which is what stopped the Audi IndexError / submarine KeyError.
    """
    ref_bytes = bytes([7, 8, 7, 9, 5, 6, 0x01, 0x0A, 0x01, 0x0B, 0x01, 0x0C, 0, 0])
    rec = _strip_record(0x42, 6, bytes([6]), ref_bytes)
    records, n_hdrs = parse_strip_records(rec, 0, len(rec), 100)
    assert n_hdrs == 1
    assert len(records) == 1
    _o, _mk, _normal, _counts, refs, width = records[0]
    assert width == 1
    assert refs == (7, 8, 7, 9, 5, 6)
    assert all(r < 100 for r in refs)


def test_composite_short_vote_declines_an_all_oob_winner():
    """#66 post-vote gate: a record with no in-bounds reading stays
    unresolved (it never reaches ``_triangulate``)."""
    rec = _strip_record(0x41, 2, bytes([2]), bytes([200, 200, 201, 201]))
    records, n_hdrs = parse_strip_records(rec, 0, len(rec), 100)
    assert n_hdrs == 1
    assert records == []


def test_composite_relaxed_primitive_reads_u16_little_endian():
    """#66: the MB-chair/Audi byte pattern. The same 8 bytes are u16be
    junk (0x4500 >= 100), u8 byte pairs ([69, 0, 72, 0], in bounds but
    the u8 sub-form) and u16le [69, 72, 73, 74] — the pinned primitive.
    u16 outranks u8 for the relaxed markers, so the u16le parse wins.
    """
    ref_bytes = bytes([69, 0, 72, 0, 73, 0, 74, 0])
    rec = _strip_record(0x44, 4, bytes([4]), ref_bytes)
    records, n_hdrs = parse_strip_records(rec, 0, len(rec), 100)
    assert n_hdrs == 1
    assert len(records) == 1
    _o, _mk, _normal, _counts, refs, width = records[0]
    assert width == 2
    assert refs == (69, 72, 73, 74)


def test_composite_relaxed_primitive_falls_back_to_u8():
    """#66: the MB-hatch sub-form — the u16 readings are out of space,
    the u8 reading [36, 29, 27, 34, 1] is the record."""
    rec = _strip_record(0x41, 5, bytes([5]), bytes([36, 29, 27, 34, 1]))
    records, n_hdrs = parse_strip_records(rec, 0, len(rec), 100)
    assert n_hdrs == 1
    assert len(records) == 1
    _o, _mk, _normal, _counts, refs, width = records[0]
    assert width == 1
    assert refs == (36, 29, 27, 34, 1)


def test_composite_u8_winner_over_a_truncated_u16be_stream_is_declined():
    """W1 marathon anti-half-read: the acc-Cont-Lft 0x5255e record,
    reproduced byte for byte.

    ``01 42 11 ff``, n=97, counts [5,5,5,5,9,5,5,9,5,5,5,5,5,5,5,5,9]
    (sum 97), and a ref block whose every even byte is 0x00 — a u16be
    stream (refs 0, 58, 1, 61, ... 253, 188, 255) over a store whose
    declared element space is 220. The u16be parse ends past the
    truncated span, so the vote's only viable candidate is the u8
    reading (0, 0, 0, 58, 0, 1, ...) — the permuted garbage the OOB
    gap-edge tiebreak kept; its triangles are false surface. The
    u16be re-reading leaves the element space too (refs to 255), so
    the record is unresolvable either way and is declined
    fail-closed instead of exporting the garbage (the real store's
    not-manifold flips to pass with the decline).
    """
    block = bytes.fromhex(
        "014211ff6100000005050505090505090505050505050505090000003a0001"
        "003d00030003003d00080042000e000e004200120048001500150048001900"
        "4e001e001e004e0022005500270059002b005e002f002f005e003300650035"
        "003500650039006b00510051006b00630072007000750079007b0080008000"
        "7b00880081009200920081009e008700ab00ab008700be008d00c200c2008d"
        "00c6009400ca00ca009400ce009900d200d2009900d600a200db00db00a200"
        "df00aa00e300e300aa00e800b500ed00ed00b500f400b700fb00b900fd00bc"
        "00ff"
    )
    assert len(block) == 219
    # The body carries the full u16be stream (the decline must be able
    # to re-read it) with zero filler past it — no further headers.
    data = block + bytes(16)
    records, n_hdrs = parse_strip_records(data, 0, len(data), 220)
    assert n_hdrs == 1
    assert records == []


def test_composite_u8_record_with_in_bounds_u16be_reread_still_exports():
    """W1 marathon anti-half-read, the negative control: the same
    0-heavy signature over a store whose u16be re-reading stays inside
    the declared element space is NOT declined — the decline fires
    only where the u16 stream leaves the space (fail-closed scope)."""
    counts = bytes([5, 5, 5, 5, 9, 5, 5, 9, 5, 5, 5, 5, 5, 5, 5, 5, 9])
    refs = bytes(97)  # every byte 0x00: the u16be re-read is in-bounds (0s)
    rec = (
        bytes([0x01, 0x42, 0x11, 0xFF])
        + struct.pack("<I", 97)
        + counts
        + refs
        + bytes(16)
    )
    records, n_hdrs = parse_strip_records(rec, 0, len(rec), 220)
    assert n_hdrs == 1
    assert len(records) == 1
    _o, _mk, _normal, _counts, got_refs, width = records[0]
    assert width == 1
    assert got_refs == (0,) * 97


def test_composite_relaxed_u8_half_read_of_a_u16le_stream_is_declined():
    """#66: the Audi 0x301e912 false header, reproduced byte for byte.

    A 0x41 candidate whose u8 winner ends before a 6-byte extended
    header, while its 2n-wide u16le reading is a complete in-bounds
    ref stream reaching at least one whole ref past that header, is a
    half-read of the previous record's u16le refs — not a record. The
    ``01 47 08 08 04 ff`` at +47 is the structure that gives it away
    (in the Audi file that record's n-law 116 = 3*8 + 92 is exact):
    the u16le ref spanning the header start reads 391 from ``87 01``
    and the next one reads 2119 from ``47 08``, so the apparent record
    swallows the real header's bytes. Every verified u8 record either
    straddles such a header by its single header byte or leaves OOB
    u16 refs (corpus census), so this declines no real one.
    """
    rec = bytearray(53)
    # 0x41 candidate at 21: n=9, counts [4, 2, 3] -> counts_end 32.
    rec[21:29] = bytes([0x01, 0x41, 0x03, 0xFF]) + struct.pack("<I", 9)
    rec[29:32] = bytes([4, 2, 3])
    # The ref block's first six u16le refs are plain in-bounds values.
    rec[32:44] = bytes([0x45, 0, 0x48, 0, 0x49, 0, 0x4A, 0, 0x4B, 0, 0x4C, 0])
    rec[44:46] = bytes([0x87, 0x01])  # ref 6 = 391
    rec[46] = 0  # ref 7's low byte = 256 with the header's 0x01
    # The real 6-byte extended header at 47 (ref 8 reads 0x47 0x08 = 2119).
    rec[47:53] = bytes([0x01, 0x47, 0x08, 0x08, 0x04, 0xFF])
    records, n_hdrs = parse_strip_records(bytes(rec), 0, len(rec), 3000)
    assert n_hdrs == 1
    assert records == []



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


# --- stage 10: the dup-pin law (the curve-entry coordinates); stage 15
# RELAXED it (the E0-b battery criterion removed, owner-authorized
# 2026-11-13 handoff cont. 23) — the old battery negatives re-scope to
# pins on the NEW scope: fire only at exported+tris==0+dropped>0
# whole-store gates, the unpinnable arm stays fail-closed, and the
# corpus's one relaxation exception (3dff4d93) stays failed -------------


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


def test_composite_e0b_nonplanar_loop_stays_out(tmp_path, capsys):
    """The battery is NOT weakened (fix 3, 2026-11-18): one coplanar +
    one NONPLANAR dropped loop on an empty-primary-mesh store — the
    coplanar loop welds, the nonplanar one is refused and stays
    counted as unexported.  Dropping the battery would also emit its
    fan (4 triangles) — red."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-e0b-nonplanar"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    validate(summary, load_schema("export-summary-v1"))
    info = summary["composite"]
    assert info["loops_curve_entry"] == 1  # the refused loop stays named
    assert info["loops_curve_entry_exported"] == 1
    assert info["loops_exported"] == 1
    assert info["curve_entry_law"] == "e0b-dup-pin"
    assert summary["vertex_count"] == 12  # the weld adds no vertices
    assert summary["triangle_count"] == 2
    assert summary["degenerate_triangle_count"] == 0
    assert summary["mesh"]["manifold"] is True
    classes = _warning_classes(summary)
    assert "curve-entry-loops-unexported" in classes
    assert "curve-entry-loops-exported-dup-pin" in classes
    # only the coplanar fan, in written ranks: skip 2 -> element 1 (P1)
    _, faces = parse_ply(ply_path)
    assert sorted(faces) == [(1, 0, 6), (1, 6, 2)]


def test_composite_e0b_normal_less_loop_exports(tmp_path, capsys):
    """The 08f2eccb mixed-coverage shape under the per-loop law: one
    coplanar loop + one on a NORMAL-LESS 0x42 strip — the normal-less
    record has no plane to test, so the loop welds (the stage-14
    measurement: the 25/26 corpus pinned meshes are exactly the
    normal-less family).  Requiring a stored normal keeps this store
    conservative at 0 triangles — red."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-e0b-normal-less"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    info = summary["composite"]
    assert info["loops_curve_entry"] == 0
    assert info["loops_curve_entry_exported"] == 2
    assert info["curve_entry_law"] == "e0b-dup-pin"
    assert summary["triangle_count"] == 4
    assert summary["mesh"]["manifold"] is True
    classes = _warning_classes(summary)
    assert "curve-entry-loops-unexported" not in classes
    assert "curve-entry-loops-exported-dup-pin" in classes
    # the coplanar fan (1,0,6),(1,6,2) + the normal-less STRIP's
    # triangles (4,3,9),(5,9,3) — the strip semantics (odd-triangle
    # winding flip) pinned through the weld
    _, faces = parse_ply(ply_path)
    assert sorted(faces) == [(1, 0, 6), (1, 6, 2), (4, 3, 9), (5, 9, 3)]


def test_composite_e0b_nonplanar_fans_refused_mesh_manifold(tmp_path, capsys):
    """The no-manifold regression pin (fix 3, 2026-11-18): three
    skip-bearing 0x4C fans, one coplanar and two NONPLANAR under the
    dup pin (the stage-15 fixture's (2,12,8)/(2,13,8) fans).  The
    per-loop battery exports ONLY the coplanar fan; the two refused
    loops never reach the mesh, which stays manifold at 2 triangles.
    Dropping the battery (the old stage-15 relaxation) emits all three
    fans, over-using edge (rank 1, rank 6) three times and leaving the
    mesh NOT-MANIFOLD — red on both the triangle count and the
    manifold verdict."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-e0b-nonplanar-refused"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    info = summary["composite"]
    assert info["loops_curve_entry"] == 2  # the two bad loops stay named
    assert info["loops_curve_entry_exported"] == 1
    assert info["curve_entry_law"] == "e0b-dup-pin"
    assert summary["triangle_count"] == 2
    assert summary["degenerate_triangle_count"] == 0
    assert summary["mesh"]["manifold"] is True
    classes = _warning_classes(summary)
    assert "curve-entry-loops-unexported" in classes
    assert "curve-entry-loops-exported-dup-pin" in classes
    _, faces = parse_ply(ply_path)
    assert sorted(faces) == [(1, 0, 6), (1, 6, 2)]


def test_composite_e0b_nonempty_primary_mesh_welds(tmp_path, capsys):
    """The surface-loss fix's core pin (fix 1 + the mesh guard,
    2026-11-18): the OPEN box exports its 10 primary triangles AND
    carries a battery-supported dropped loop whose edges are disjoint
    from the surviving edge set — the store's primary mesh is NOT empty
    and the weld still fires for that loop (10 -> 12 triangles,
    manifold).  The old empty-mesh precondition kept the open box at 10
    and left the loop unexported — red.  This is labios/main's shape:
    missing panels on a non-empty primary mesh."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-e0b-nonempty"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    info = summary["composite"]
    assert summary["triangle_count"] == 12  # 10 open-box + the 2 welded
    assert summary["mesh"]["manifold"] is True
    assert info["loops_curve_entry"] == 0
    assert info["loops_curve_entry_exported"] == 1
    assert info["curve_entry_law"] == "e0b-dup-pin"
    assert "curve-entry-loops-unexported" not in _warning_classes(summary)
    assert "curve-entry-loops-exported-dup-pin" in _warning_classes(summary)


def test_composite_e0b_mesh_guard_refuses_duplicate_face(tmp_path, capsys):
    """The per-loop mesh guard's fail-closed direction (2026-11-18):
    the FULL closed box plus the same battery-supported, pinnable
    coplanar loop.  The fan re-covers the box's y=10 face, so welding
    it would push an edge past two uses — the guard refuses the loop
    (the box's 12 triangles stay, mesh manifold, the loop stays named).
    The naive per-loop law without the guard adds the fan (14 triangles,
    one edge at 4 uses, not-manifold) — red on both counts."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-e0b-mesh-guard"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    info = summary["composite"]
    assert summary["triangle_count"] == 12  # the box, NOT 14
    assert summary["mesh"]["manifold"] is True
    assert summary["mesh"]["closed"] is True
    assert info["loops_curve_entry"] == 1  # the refused loop stays named
    assert "curve_entry_law" not in info
    assert "curve-entry-loops-unexported" in _warning_classes(summary)


def test_composite_e0b_multi_rep_welds_with_nonempty_store(tmp_path, capsys):
    """The per-rep paths weld per loop too (2026-11-18): rep 0 exports
    its box, rep 1 carries a battery-supported dropped loop — the
    store's merged mesh is not empty and rep 1's loop still welds
    (12 -> 14 triangles).  The old store-level empty-mesh gate kept the
    store at 12 and left rep 1's loop unexported — red."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-e0b-multi-rep-conservative"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    info = summary["composite"]
    assert info["stage"] == "identity-per-rep"
    assert info["reps_decoded"] == 2
    assert info["reps_exported"] == 2
    assert summary["triangle_count"] == 14  # 12 box + rep 1's welded 2
    assert summary["mesh"]["manifold"] is True
    assert info["loops_curve_entry"] == 0
    assert info["loops_curve_entry_exported"] == 1
    assert info["curve_entry_law"] == "e0b-dup-pin"
    assert "curve-entry-loops-unexported" not in _warning_classes(summary)
    assert "curve-entry-loops-exported-dup-pin" in _warning_classes(summary)


def test_composite_e0b_multi_rep_unpinnable_rep_does_not_veto(tmp_path, capsys):
    """The per-loop law removes the store-level veto (2026-11-18):
    BOTH reps' primary triangulations are empty — rep 0 carries an
    UNPINNABLE dropped loop (its skip slot is rep 0's ELEMENT 0: no
    preceding written element to weld to), rep 1 a pinnable one.  Rep
    1's loop welds; rep 0's stays dropped and counted.  The old
    store-level None-candidate veto kept the whole store at 0 triangles
    and zeroed the exported counter — red."""
    code, captured, ply_path = run_export(
        tmp_path, capsys,
        "geometry-composite-law-e0b-multi-rep-unsupported-veto",
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    info = summary["composite"]
    assert info["stage"] == "identity-per-rep"
    assert info["reps_decoded"] == 2
    assert info["reps_exported"] == 2
    assert summary["vertex_count"] == 24
    assert summary["triangle_count"] == 2  # only rep 1's welded fan
    assert info["loops_curve_entry"] == 1  # rep 0's unpinnable loop
    assert info["loops_curve_entry_exported"] == 1
    assert info["curve_entry_law"] == "e0b-dup-pin"
    classes = _warning_classes(summary)
    assert "curve-entry-loops-unexported" in classes
    assert "curve-entry-loops-exported-dup-pin" in classes


def test_composite_e0b_multi_rep_relaxed_fires(tmp_path, capsys):
    """The stage-15 overturn at the store level: BOTH reps' primary
    triangulations are empty and BOTH carry a NORMAL-LESS dropped loop —
    under the relaxed law neither rep vetoes (the battery criterion is
    removed, owner-authorized 2026-11-13), the store-level gate fires
    and BOTH reps' pins export.  Restoring the stage-10 battery keeps
    the whole store conservative at 0 triangles — red."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-e0b-multi-rep-relaxed"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    info = summary["composite"]
    assert info["stage"] == "identity-per-rep"
    assert info["reps_decoded"] == 2
    assert info["reps_exported"] == 2
    assert summary["vertex_count"] == 24
    assert summary["triangle_count"] == 4  # 2 strip triangles per rep
    assert info["loops_curve_entry"] == 0
    assert info["loops_curve_entry_exported"] == 2
    assert info["curve_entry_law"] == "e0b-dup-pin"
    assert summary["mesh"]["manifold"] is True
    classes = _warning_classes(summary)
    assert "curve-entry-loops-unexported" not in classes
    assert "curve-entry-loops-exported-dup-pin" in classes
    _, faces = parse_ply(ply_path)
    # rep 0's weld fan-strip (1,0,6),(2,6,0) + rep 1's same +12 base
    assert sorted(faces) == [
        (1, 0, 6), (2, 6, 0), (13, 12, 18), (14, 18, 12),
    ]


def test_composite_e0b_unpinnable_keeps_conservative(tmp_path, capsys):
    """The unpinnable arm (stage-10 review F4; the relaxed law's
    remaining fail-closed arm): the dropped loop's skip slot is
    ELEMENT 0 — no preceding written element exists to weld to — so the
    law rejects before any pin is welded and the store keeps the
    conservative rule.  Removing the unpinnable arm would let the law
    proceed on a missing pin target — red."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-e0b-unpinnable"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    info = summary["composite"]
    assert summary["vertex_count"] == 12
    assert summary["triangle_count"] == 0  # stays empty-mesh
    assert info["loops_curve_entry"] == 1
    assert "curve_entry_law" not in info
    assert "curve-entry-loops-unexported" in _warning_classes(summary)


# --- stage 15: the unordered-triangle dedup law (the stage-14 review
# F1 family, owner-authorized 2026-11-13) --------------------------------


def test_composite_dedup_unordered_drops_later_copy(tmp_path, capsys):
    """The dedup positive (the review F1 mechanism): a second record
    re-writes box triangle (6,0,9) REVERSED as (9,0,6) — edge (6,0) is
    a box edge, so the duplicate pushes it to 3 uses and the emitted
    mesh is not-manifold; the unordered dedup drops the LATER copy and
    the mesh is the exact 12-triangle box again.  First occurrence's
    winding wins.  Removing the dedup leaves the over-edge — red."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-dedup-unordered"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    validate(summary, load_schema("export-summary-v1"))
    info = summary["composite"]
    assert info["unordered_dedup_dropped"] == 1
    assert summary["triangle_count"] == 12
    assert summary["degenerate_triangle_count"] == 0
    assert summary["mesh"]["manifold"] is True
    assert summary["mesh"]["closed"] is True
    classes = _warning_classes(summary)
    assert "duplicate-triangles-deduped" in classes
    assert "duplicate-triangles-dedup-declined" not in classes
    _, faces = parse_ply(ply_path)
    assert (9, 0, 6) not in faces  # the later copy is gone
    assert (6, 0, 9) in faces  # the first occurrence's winding survives
    assert len(faces) == 12


def test_composite_dedup_manifold_no_fire(tmp_path, capsys):
    """The zero-regression direction: a two-sided sheet — two triangles
    over the SAME three written vertices in opposite windings — is
    MANIFOLD (each shared edge used once per winding) and carries an
    unordered duplicate pair, but the fire gate's pre-manifold
    condition holds: NO dedup, the emitted mesh exports verbatim (both
    copies ride; a passing store's row must not change).  Removing the
    pre-manifold condition collapses the sheet to 1 triangle — red."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-dedup-manifold-no-fire"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    info = summary["composite"]
    assert "unordered_dedup_dropped" not in info
    assert "unordered_dedup_declined" not in info
    assert summary["triangle_count"] == 2
    assert summary["mesh"]["manifold"] is True
    assert summary["mesh"]["closed"] is True
    assert summary["mesh"]["oriented"] is True
    classes = _warning_classes(summary)
    assert "duplicate-triangles-deduped" not in classes
    assert "duplicate-triangles-dedup-declined" not in classes
    _, faces = parse_ply(ply_path)
    assert sorted(faces) == [(0, 1, 3), (3, 1, 0)]


def test_composite_dedup_declined_fail_closed(tmp_path, capsys):
    """The fail-closed arm: duplicates whose removal does NOT produce a
    manifold keep failing — box + duplicate + one FIN triangle on the
    same box edge: dropping the duplicate still leaves the edge used
    3x, so the dedup declines, the emitted 14 triangles are kept
    VERBATIM and the declined dedup is named.  Applying the dedup
    anyway (dropping the post-manifold condition) would export 13 —
    red."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-dedup-declined"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    info = summary["composite"]
    assert info["unordered_dedup_declined"] == 1
    assert "unordered_dedup_dropped" not in info
    assert summary["triangle_count"] == 14  # the emitted list, verbatim
    assert summary["mesh"]["manifold"] is False
    classes = _warning_classes(summary)
    assert "duplicate-triangles-dedup-declined" in classes
    assert "duplicate-triangles-deduped" not in classes
    _, faces = parse_ply(ply_path)
    assert (9, 0, 6) in faces  # kept: nothing was dropped


def test_composite_dedup_degenerate_separate_gate(tmp_path, capsys):
    """The b912cbef shape: the dedup fires (box + duplicate -> 12
    triangles, manifold) while a PRE-EXISTING degenerate skip rides
    UNTOUCHED — degenerates are counted at emission, never deduped, and
    stay a separate L2 gate check (the corpus: b912cbef dedups to a
    manifold mesh and still fails on its 3 pre-existing skips,
    declared).  The dedup eating the skip count would zero it — red."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-dedup-degenerate"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    info = summary["composite"]
    assert info["unordered_dedup_dropped"] == 1
    assert summary["triangle_count"] == 12
    assert summary["degenerate_triangle_count"] == 1  # the skip survives
    assert summary["mesh"]["manifold"] is True
    assert summary["mesh"]["closed"] is True
    classes = _warning_classes(summary)
    assert "duplicate-triangles-deduped" in classes
    assert "degenerate-triangles-skipped" in classes


def test_composite_dedup_coordinate_relist_across_reps(tmp_path, capsys):
    """The coordinate arm (2026-11-18): rep 1 re-lists rep 0's 12-point
    box at the SAME coordinates in its own element space — not one
    index triple matches, so the index pass sees no duplicate — and
    adds one 2000 mm² fin loop over box edge (0, 3), which rep 1's own
    two box faces already use: the store is not-manifold.  The
    coordinate dedup drops rep 1's 12 re-listed copies (the earlier
    emission unit wins) and keeps the fin: 13 triangles, manifold,
    and the fin's surface (10.9% of the store, so the primary seam
    keeps it and declines) survives.  Without the coordinate arm the
    store stays not-manifold — red."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-dedup-coord-relist"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    validate(summary, load_schema("export-summary-v1"))
    info = summary["composite"]
    assert info["unordered_dedup_dropped"] == 12
    assert "unordered_dedup_declined" not in info
    assert info["reps_exported"] == 2
    assert summary["triangle_count"] == 13
    assert summary["mesh"]["manifold"] is True
    classes = _warning_classes(summary)
    assert "duplicate-triangles-deduped" in classes
    assert "primary-loop-manifold-skip" not in classes
    assert "primary-loop-manifold-kept" in classes
    # The surface is the box (18,400 mm²) plus the fin (2,000 mm²): the
    # dropped copies are the same three points as the kept ones, so no
    # area is lost.
    vertices, faces = parse_ply(ply_path)
    assert len(faces) == 13

    def _area(tri):
        a, b, c = (vertices[i] for i in tri)
        ux, uy, uz = (b[k] - a[k] for k in range(3))
        vx, vy, vz = (c[k] - a[k] for k in range(3))
        cx, cy, cz = (
            uy * vz - uz * vy,
            uz * vx - ux * vz,
            ux * vy - uy * vx,
        )
        return 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)

    assert math.isclose(sum(_area(f) for f in faces), 20400.0, rel_tol=1e-9)
    # The fin's apex (0, 60, -40) is referenced by exactly one triangle.
    apex = [i for i, v in enumerate(vertices) if v == pytest.approx((0.0, 60.0, -40.0))]
    assert len(apex) == 1
    assert sum(1 for f in faces if apex[0] in f) == 1


def test_unordered_dedup_matches_coordinates_across_disjoint_spaces():
    """The keeper rule at the seam's granularity: two per-rep element
    spaces whose written coordinates coincide are ONE facet.  The
    earlier space's copy wins even when it sits later in the emission
    list (a rep's welded loops are appended last), and the drop is
    area-preserving — the left copy is the same three points.  With one
    declared space the list order decides, the fin's edge keeps three
    uses and the dedup declines fail-closed."""
    pts = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (1.0, 1.0, 0.0),
        (2.0, 0.0, 0.0),
    ]
    # Space 1's re-listing (3,4,5) comes FIRST; space 0's copy (0,1,2)
    # comes LAST.  (3,6,4) and (3,7,4) push edge {3,4} to three uses.
    tris = [(3, 4, 5), (3, 6, 4), (3, 7, 4), (0, 1, 2)]
    info = {}
    kept = composite._apply_unordered_dedup(tris, info, pts, (0, 3))
    assert kept == [(3, 6, 4), (3, 7, 4), (0, 1, 2)]
    assert info == {"unordered_dedup_dropped": 1}
    # Same list, one index space: the list-order copy wins, the fin's
    # edge keeps three uses, and the dedup declines (kept verbatim).
    info = {}
    kept = composite._apply_unordered_dedup(tris, info, pts)
    assert kept == tris
    assert info == {"unordered_dedup_declined": 1}
    # A manifold mesh is never touched, even with coordinate twins.
    info = {}
    sheet = [(0, 1, 2), (3, 5, 4)]
    assert composite._apply_unordered_dedup(sheet, info, pts, (0, 3)) == sheet
    assert info == {}


# --- 2026-11-18: the primary-emit manifold seam (#34) --------------------
#
# The short records' primary loop emission was the one seam with no
# manifold guard.  These fixtures put a FIN loop over the box edge
# (0, 3) — already used twice — and pin both arms of the area rule plus
# the store-level fire gate (docs/evidence/
# 2026-11-18-primary-emit-seam.md).


def test_composite_primary_seam_skips_a_tiny_overuse_loop(tmp_path, capsys):
    """The tiny arm: the fin's apex is 0.5 mm from the box edge
    (0.05 mm² = 0.0003% of the 18,400 mm² box), so the seam drops the
    sliver, the mesh is the 12-triangle manifold box, and the skip is
    counted and named.  Without the seam the fin's edge use tips the
    mesh to not-manifold (13 triangles) — red."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-primary-seam-tiny"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    info = summary["composite"]
    assert summary["triangle_count"] == 12
    assert summary["mesh"]["manifold"] is True
    assert info["primary_loop_skips"] == 1
    assert "primary_loop_kept" not in info
    assert "primary_loop_seam_declined" not in info
    classes = _warning_classes(summary)
    assert "primary-loop-manifold-skip" in classes
    assert "primary-loop-manifold-kept" not in classes
    _, faces = parse_ply(ply_path)
    assert len(faces) == 12  # the box only


def test_composite_primary_seam_keeps_a_large_overuse(tmp_path, capsys):
    """The large arm + the fire gate: the store carries the tiny fin
    AND a 500 mm² fin (2.7% of the box).  The large loop is real
    surface and is kept; the mesh stays not-manifold, so the seam is
    declined fail-closed and the PRE-SEAM emission (box + both fins,
    14 triangles) is returned unchanged — no surface lost for no L2
    gain.  Both outcomes are named."""
    code, captured, ply_path = run_export(
        tmp_path, capsys, "geometry-composite-law-primary-seam-declined"
    )
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    info = summary["composite"]
    assert summary["triangle_count"] == 14  # the pre-seam emission
    assert summary["mesh"]["manifold"] is False
    assert info["primary_loop_kept"] == 1
    assert info["primary_loop_seam_declined"] == 1
    assert "primary_loop_skips" not in info
    classes = _warning_classes(summary)
    assert "primary-loop-manifold-declined" in classes
    assert "primary-loop-manifold-kept" in classes
    assert "primary-loop-manifold-skip" not in classes
    _, faces = parse_ply(ply_path)
    assert len(faces) == 14


# --- 2026-11-18: the per-loop dup-pin weld (the surface-loss fix, #34) --


#: The real-corpus regression case for the per-loop weld. The corpus is
#: gitignored and never present in CI (fixtures_gen's docstring), so the
#: test is corpus-gated: on a machine with the corpus it pins the
#: measured before/after numbers, elsewhere it skips.
LABIOS_MAIN = (
    Path(__file__).resolve().parents[1]
    / "corpus/Apoloo13/ASE_III/diseño_3d/labios/main.CATPart"
)


def _ply_area(vertices, faces) -> float:
    """Total surface area of a triangle-indexed PLY."""

    def _tri_area(p, q, r):
        ux, uy, uz = q[0] - p[0], q[1] - p[1], q[2] - p[2]
        vx, vy, vz = r[0] - p[0], r[1] - p[1], r[2] - p[2]
        cx = uy * vz - uz * vy
        cy = uz * vx - ux * vz
        cz = ux * vy - uy * vx
        return 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)

    total = 0.0
    for a, b, c in faces:
        total += _tri_area(vertices[a], vertices[b], vertices[c])
    return total


@pytest.mark.skipif(
    not LABIOS_MAIN.exists(),
    reason="corpus is gitignored / absent (the corpus-gated regression case)",
)
def test_labios_main_welds_panels_on_nonempty_primary_mesh(tmp_path, capsys):
    """The bug's real case (fix 1 + fix 2 measured on the corpus):

    BEFORE this fix the store's primary mesh was non-empty (4,261
    triangles), the dup-weld's ``if not triangles and dropped``
    precondition never fired, and 13 skip-bearing loops stayed
    unexported: 2,299.09 mm².  The 10 battery-supported loops (three
    envelope panels at x=-22.7 and y=±12.4 — 599.04 + 2 x 1,163.52
    mm² — plus six smaller ones) all measure <= 1.4e-6 against their
    record normals; the 3 width-misparsed loops measure 2e-2..8 and
    stay out.

    AFTER fix 1 alone: 4,457 triangles / 5,396.79 mm².
    AFTER fix 1 + the gap-edge width battery (fix 2): 4,464 triangles /
    5,410.18 mm² (96.6% of the ~5,600 mm² envelope), manifold.

    2026-11-18 (the extended-header family): the store is a carrier
    (27 records, all accepted behind the manifold-assembly gate), so the
    pinned totals now include its 4,527 triangles / 1,614.63 mm²:
    8,995 triangles / 7,024.81 mm², manifold, 29 loops welded under
    ``e0b-dup-pin``. The per-loop weld assertions are unchanged in
    kind — the store's primary mesh is non-empty and the welded loops
    still ride the same battery + mesh guard."""
    from catpart.cli import main_export

    code = main_export([str(LABIOS_MAIN), "-o", str(tmp_path / "labios.ply")])
    captured = capsys.readouterr()
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    validate(summary, load_schema("export-summary-v1"))
    info = summary["composite"]
    assert summary["triangle_count"] == 8995
    assert summary["vertex_count"] == 4813
    assert summary["mesh"]["manifold"] is True
    assert info["loops_curve_entry"] == 0
    assert info["loops_curve_entry_exported"] == 29
    assert info["curve_entry_law"] == "e0b-dup-pin"
    assert info["extended_header_records"] == 27
    assert info["extended_header_triangles"] == 4427
    vertices, faces = parse_ply(tmp_path / "labios.ply")
    assert abs(_ply_area(vertices, faces) - 7024.81) < 0.05
# --- the escaped facet count + the extended-header family (2026-11-18) -----


def _escaped_count_record(marker: int, n: int, refs: bytes, tail: bytes = b"") -> bytes:
    """One short-form record whose single count is the P1g escape."""
    out = bytearray(bytes((0x01, marker, 0x01, 0xFF)))
    out += struct.pack("<I", n)
    out += b"\xff" + struct.pack("<I", n)
    out += refs
    out += tail
    return bytes(out)


def test_parse_strip_records_reads_the_escaped_count() -> None:
    """The facet count position uses the same P1g escape as the list
    node (composite.read_count): the Gabarit store's 528-ref 0x42
    records parse as one 528 count instead of five raw u8 bytes summing
    to 273 (which no (width, k) tile accepts)."""
    refs = b"".join(struct.pack(">H", r) for r in range(528))
    body = _escaped_count_record(0x42, 528, refs)
    records, n_hdrs = parse_strip_records(body, 0, len(body), 1000)
    assert n_hdrs == 1
    (record,) = records
    _o, marker, _normal, counts, got_refs, width = record
    assert marker == 0x42
    assert counts == (528,)
    assert width == 2
    assert len(got_refs) == 528
    assert got_refs[0] == 0 and got_refs[-1] == 527


def _extended_record(
    marker: int,
    ty: int,
    b3: int,
    b4: int,
    counts: tuple[int, ...],
    normal: tuple[float, float, float] | None,
    refs: tuple[int, ...],
) -> bytes:
    """One 6-byte-form record (``01 mk ty b3 b4 ff``, normal iff 0x4f)."""
    out = bytearray(bytes((0x01, marker, ty, b3, b4, 0xFF)))
    out += struct.pack("<I", len(refs))
    if normal is not None:
        out += struct.pack("<fff", *normal)
    out += bytes(counts)
    out += b"".join(struct.pack(">H", r) for r in refs)
    return bytes(out)


def test_parse_extended_facet_records_pins_the_header_law() -> None:
    """The extended form's three header bytes are load-bearing: `ty` is
    the number of independent triangles at the start of the refs,
    `b3 + b4` is the counts-table length, and ``sum(counts) + 3*ty == n``
    — the Gabarit store's 9/9 law."""
    counts = (5, 7)
    ty = 2
    refs = tuple(range(3 * ty)) + tuple(range(10, 10 + sum(counts)))
    body = _extended_record(0x4F, ty, 1, 1, counts, (0.0, 0.0, 1.0), refs)
    records, candidates = composite.parse_extended_facet_records(
        body, 0, len(body), element_count=64
    )
    assert candidates == 1
    (record,) = records
    assert record.marker == 0x4F
    assert record.triangles == 2
    assert record.strips == 1
    assert record.polygons == 1
    assert record.counts == counts
    assert record.refs == refs
    assert record.normal == (0.0, 0.0, 1.0)
    assert record.end == len(body)


def test_parse_extended_facet_records_rejects_out_of_range_refs() -> None:
    """A false-positive ``01 4x ... ff`` byte pattern whose refs leave
    the element space is NOT the family: the candidate stays unresolved
    instead of failing the store on the refs gate."""
    refs = (0, 1, 2, 0xFFFF)
    body = _extended_record(0x47, 1, 1, 0, (3,), None, refs)
    records, candidates = composite.parse_extended_facet_records(
        body, 0, len(body), element_count=64
    )
    assert candidates == 1
    assert records == []


def test_triangulate_extended_record_soup_strips_polygons() -> None:
    """The extended record's refs decode under the pinned split: `ty`
    independent triangles, then the first `b3` loops under the strip law
    and the last `b4` loops under the polygon-fan law — emitted only
    when the assembled mesh stays manifold (the 2026-11-18 gate)."""
    elements = [
        (0, (0.0, 0.0, 0.0)),
        (0, (1.0, 0.0, 0.0)),
        (0, (0.0, 1.0, 0.0)),
        (0, (1.0, 0.0, 1.0)),
        (0, (0.0, 0.0, 1.0)),
        (0, (0.0, 1.0, 1.0)),
        (0, (2.0, 0.0, 0.0)),
        (0, (3.0, 0.0, 0.0)),
        (0, (3.0, 1.0, 0.0)),
        (0, (2.0, 1.0, 0.0)),
    ]
    record = composite.ExtendedFacetRecord(
        offset=0,
        marker=0x47,
        triangles=1,
        strips=1,
        polygons=1,
        counts=(3, 4),
        refs=(0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
        end=0,
        normal=None,
    )
    triangles, degenerate, stats = composite._triangulate(
        elements, (), extended=[record]
    )
    # 1 soup + 1 strip (3 refs) + 2 fan triangles (4 refs)
    assert len(triangles) == 4
    assert degenerate == 0
    assert stats["extended_triangles"] == 4
    assert stats["extended_declined"] == 0
    assert stats["loops_exported"] == 2  # strip + polygon (soup not a loop)
    assert stats["loops_curve_entry"] == 0
    # The manifold-assembly gate: a second record re-using the fan's
    # (6, 8) edge would push it to three uses -> declined as a whole.
    overlapping = composite.ExtendedFacetRecord(
        offset=1,
        marker=0x47,
        triangles=0,
        strips=1,
        polygons=0,
        counts=(3,),
        refs=(6, 8, 9),
        end=1,
        normal=None,
    )
    triangles, degenerate, stats = composite._triangulate(
        elements, (), extended=[record, overlapping]
    )
    assert len(triangles) == 4
    assert stats["extended_triangles"] == 4
    assert stats["extended_declined"] == 1


def test_triangulate_extended_degenerate_member_is_filtered_not_declining() -> None:
    """The member-filter law (2026-11-21, the Audi R8 forensics): a
    degenerate member of an extended record is dropped and named on
    `extended_members_filtered` instead of declining the record whole —
    the record's valid siblings still emit behind the manifold-assembly
    gate, and the skips never count as degenerate (the L2 gate's
    degenerate-triangle rate stays 0)."""
    # refs 0..9: the first independent triangle (0,1,2) is degenerate
    # by repeated COORDINATE? No — make it degenerate by a zero cross
    # product: collinear points (0,0,0), (1,0,0), (2,0,0) — element 9.
    elements = [
        (0, (0.0, 0.0, 0.0)),      # 0
        (0, (1.0, 0.0, 0.0)),      # 1
        (0, (0.0, 1.0, 0.0)),      # 2
        (0, (1.0, 0.0, 1.0)),      # 3
        (0, (0.0, 0.0, 1.0)),      # 4
        (0, (0.0, 1.0, 1.0)),      # 5
        (0, (2.0, 0.0, 0.0)),      # 6
        (0, (3.0, 0.0, 0.0)),      # 7
        (0, (3.0, 1.0, 0.0)),      # 8
        (0, (2.0, 1.0, 0.0)),      # 9
    ]
    # ty=2: member 0 = (0,6,7) collinear on y=0 (zero cross -> filtered);
    # member 1 = (3,4,5) valid. strips=1: loop (6,7,8) valid.
    record = composite.ExtendedFacetRecord(
        offset=0,
        marker=0x47,
        triangles=2,
        strips=1,
        polygons=0,
        counts=(3,),
        refs=(0, 6, 7, 3, 4, 5, 6, 7, 8),
        end=0,
        normal=None,
    )
    triangles, degenerate, stats = composite._triangulate(
        elements, (), extended=[record]
    )
    # the filtered member emits nothing; the valid member (1 tri) + the
    # strip loop (1 tri) emit
    assert len(triangles) == 2
    assert degenerate == 0  # the L2 gate stays clean
    assert stats["extended_members_filtered"] == 1
    assert stats["extended_declined"] == 0
    assert stats["extended_triangles"] == 2
    # a fully-degenerate record (every member filtered) is declined:
    # its valid remainder is empty
    all_degenerate = composite.ExtendedFacetRecord(
        offset=1,
        marker=0x47,
        triangles=1,
        strips=0,
        polygons=0,
        counts=(),
        refs=(0, 6, 7),
        end=1,
        normal=None,
    )
    triangles, degenerate, stats = composite._triangulate(
        elements, (), extended=[all_degenerate]
    )
    assert len(triangles) == 0
    assert degenerate == 0
    assert stats["extended_members_filtered"] == 1
    assert stats["extended_declined"] == 1


# --- 2026-11-18: the primary-emit seam's port parity on the corpus flips --
#
# The 15 not-manifold parts the seam flips (docs/evidence/
# 2026-11-18-primary-emit-seam.md; the A/B's
# docs/evidence/data/primary-emit-seam-ab.csv rows).  The corpus is
# gitignored and never present in CI, so this differential is
# corpus-gated: on a machine with the corpus it exports each part
# through BOTH shipped seams (the Python reference and the release
# ``fidelity-cli``) and pins parsed-summary equality plus
# byte-identical PLY; elsewhere it skips.
PRIMARY_SEAM_FLIPS = {
    # 13bb5c0c gained its 120 k=17/18 0x42 records (#65's MAX_LOOP_COUNTS
    # raise; all in-bounds, 90 exact-tiling, the store stays manifold) —
    # 215775 -> 224435. The 4abf3eea / c9fdd852 / d31ea2c1 gains ride the
    # #65 exact-tiling exception on the u8 extended path (their wins end
    # past an internal false-positive STRIP_RE match and land exactly on
    # the next real boundary).
    # 2026-11-22 (marathon W7-B patch 003): the width tie prefers the
    # wider reading, which clears this store's 33 degenerate-triangle
    # skips and admits +5,297 real triangles: 224435 -> 229732, still
    # manifold with 0 degenerates and L2 pass (Smooth 33->0 in W7-B's
    # micro-batch evidence).
    "13bb5c0c49616ade": 229732,
    "2fb5b092857f70ec": 1753,
    "44e63faa2d9abf84": 2520,
    "4a32f59c1e637acd": 2451,
    "4abf3eeaf892be44": 1973,
    # 612c5e7cc7291c71 gained its extended-header records' valid
    # siblings through the 2026-11-21 member-filter law (4505 -> 4521;
    # the degenerate members are filtered and named, the manifold
    # assembly gate unchanged) — the seam-flip pins the law recovers.
    "612c5e7cc7291c71": 4521,
    "6ab9e107b7f30308": 959,
    "97a0a420923c5c67": 8641,
    "a61588e5fe2cca5f": 3017,
    "ba0900267e2072e1": 4395,
    "bc235805f71fdf5a": 1753,
    "c9fdd85256ae1eba": 17598,
    "cd76cab52cf2fbe5": 1563,
    "d31ea2c17d63c041": 2633,
    "d4127e6b5cc39236": 5080,
}


def _corpus_part_paths(sha16s) -> dict[str, Path]:
    import csv

    root = Path(__file__).resolve().parents[1]
    rows = {
        r["sha256"][:16]: r
        for r in csv.DictReader((root / "manifests" / "corpus-manifest.csv").open())
        if r["kind"] == "part"
    }
    return {
        sha: root / rows[sha]["local_path"]
        for sha in sha16s
        if sha in rows and (root / rows[sha]["local_path"]).exists()
    }


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[1] / "corpus").exists(),
    reason="corpus is gitignored / absent (the corpus-gated seam differential)",
)
def test_primary_seam_port_parity_on_the_flips(tmp_path):
    """Python ≡ Port on the 15 primary-seam flips: parsed summaries and
    byte-identical PLY.  Every part must be manifold at its pinned
    triangle count."""
    import shutil
    import subprocess

    from catpart.geometry import build_export

    paths = _corpus_part_paths(PRIMARY_SEAM_FLIPS)
    assert set(paths) == set(PRIMARY_SEAM_FLIPS), "manifest/corpus rows missing"
    root = Path(__file__).resolve().parents[1]
    cargo = shutil.which("cargo")
    assert cargo is not None, "cargo is a required dev dependency (spec §7)"
    build = subprocess.run(
        [cargo, "build", "--release", "--locked"],
        cwd=root / "port",
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr
    port_bin = root / "port" / "target" / "release" / "fidelity-cli"
    assert port_bin.is_file()
    for sha, path in sorted(paths.items()):
        python_ply = tmp_path / f"{sha}-python.ply"
        port_ply = tmp_path / f"{sha}-port.ply"
        summary = build_export(path, python_ply)
        assert summary["triangle_count"] == PRIMARY_SEAM_FLIPS[sha]
        assert summary["mesh"]["manifold"] is True
        composite = summary["composite"]
        if "primary_loop_skips" in composite:
            assert composite["primary_loop_skips"] >= 1
        else:
            # 2026-11-22 (marathon W1-B/W10/W7-B): the identity-table-walk
            # and multi-region readings resolve some of these flips before
            # the primary seam, so the seam counter is correctly absent;
            # the pinned count and the byte-identical PLY carry the check
            # and the resolving stage must be named.
            assert str(composite.get("stage", "")).startswith("identity-"), (
                composite.get("stage")
            )
        port = subprocess.run(
            [str(port_bin), "export", str(path), str(port_ply)],
            capture_output=True,
            text=True,
        )
        assert port.returncode == 0, port.stderr
        assert json.loads(json.dumps(summary)) == json.loads(port.stdout)
        assert python_ply.read_bytes() == port_ply.read_bytes()


# --- 2026-11-18: the coordinate-identity dedup arm (#34) -----------------
#
# 545707b9 (Test_trappe) was the one artifact-dominant not-manifold case
# before the B3 rep-node pairing (2026-11-19): 4 reps exported, 67 index
# duplicates inside rep 3 plus 451 coordinate duplicates rep 3 re-lists
# from the earlier rep's welded loops; the index pass declined (removing
# 67 leaves 125 over-edges) and the coordinate pass dropped all 451.
#
# With B3 the store exports its own 5 reps: the mis-attributed records
# belong to the node that now decodes, the assembled mesh is manifold on
# its own, and the dedup's fire gate (a NOT-manifold assembled mesh)
# never engages — no dedup outcome at all.  Measured on 2026-11-19
# (docs/evidence/2026-11-19-b3-pairing.md §3): 2,266 triangles,
# 16,063.010778 mm², 5/5 reps, no dedup key.  #65's MAX_LOOP_COUNTS
# raise admitted the store's two k=25 0x42 records (2,266 -> 2,978
# triangles, 16,192.314366 mm² listed; still 5/5 reps, manifold, no
# dedup key).  The dedup law itself is
# unchanged and stays pinned by the fixture arm
# (test_composite_dedup_coordinate_relist_across_reps).

DEDUP_COORD_CASE = {"545707b9871a535c": 2978}
# The zero-regression direction on the same seam: a store the primary
# seam resolves keeps its committed geometry (the dedup never sees
# a passing assembled mesh).  The #62 width vote admitted the store's
# extended-header record (31203 -> 31298) and #64's escaped header form
# admitted two more (31298 -> 49780, 2026-11-20); #65's MAX_LOOP_COUNTS
# raise admitted the store's two k=25 0x42 records (49780 -> 51369,
# 2026-11-20); the manifold/no-dedup-outcome pins are unchanged.
# 2026-11-22 (marathon W1-B/W10 identity-per-rep): the multi-region
# reading emits +457 more real triangles (51369 -> 51826), still
# manifold, 0 degenerates, no dedup outcome.
DEDUP_COORD_NO_REGRESSION = {"b912cbef805c541b": 51826}

# --- 2026-11-21: the L1.1 adoption condition (#70) -------------------------
#
# The relist post-pass adopts its candidate only when the candidate
# mesh is manifold, its boundary-edge set does not grow, every skipped
# loop's vertex coordinates survive AND (L1.1) it carries no more
# degenerate-triangle skips than the kept emission — the 37
# `degenerate-triangles` side effects of L1 live in the EXTERNAL
# submarine snapshot (docs/evidence/2026-11-21-phase3-l3-residue.md;
# the external probe pins their return to not-manifold), while the ONE
# official-corpus part the pass fires on carries a degenerate-free
# candidate and must keep its adopted emission.
RELIST_ADOPTED_PIN = {"cd88ae9d4d51a439": 3420}


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[1] / "corpus").exists(),
    reason="corpus is gitignored / absent (the corpus-gated L1.1 pin)",
)
def test_relist_adoption_survives_the_degenerate_condition(tmp_path):
    """The one corpus relist adopter stays L2 pass at its pinned count.

    2026-11-22 (marathon W1-B/W10): the multi-region identity-per-rep
    reading now resolves this part before the relist post-pass, so the
    relist outcome keys are absent and the emission carries +34 real
    triangles (3386 -> 3420), manifold with 0 degenerates. The L1.1
    adoption law itself stays pinned by the fixture arm
    (test_composite_dedup_coordinate_relist_across_reps); when the store
    does reach the relist, its outcome must still be named.
    """
    from catpart.geometry import build_export

    paths = _corpus_part_paths(RELIST_ADOPTED_PIN)
    assert set(paths) == set(RELIST_ADOPTED_PIN), "manifest/corpus rows missing"
    for sha, path in paths.items():
        summary = build_export(path, tmp_path / f"{sha}.ply")
        assert summary["triangle_count"] == RELIST_ADOPTED_PIN[sha]
        assert summary["degenerate_triangle_count"] == 0
        assert summary["mesh"]["manifold"] is True
        composite = summary["composite"]
        if "primary_loop_relist_skips" in composite:
            assert composite["primary_loop_relist_skips"] >= 1
            assert "primary_loop_relist_boundary" in composite
        else:
            # The identity-per-rep route resolved the store first; the
            # relist never fires and its keys are correctly absent.
            assert composite.get("stage") in (
                "identity-per-rep",
                "identity-mixedwrite-reps",
            ), composite.get("stage")
            assert composite.get("reps_exported", 0) >= 1


def _triangle_area(vertices, tri):
    """One PLY triangle's area."""
    a, b, c = (vertices[i] for i in tri)
    ux, uy, uz = (b[k] - a[k] for k in range(3))
    vx, vy, vz = (c[k] - a[k] for k in range(3))
    cx, cy, cz = (
        uy * vz - uz * vy,
        uz * vx - ux * vz,
        ux * vy - uy * vx,
    )
    return 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[1] / "corpus").exists(),
    reason="corpus is gitignored / absent (the corpus-gated dedup differential)",
)
def test_coordinate_dedup_case_and_port_parity(tmp_path):
    """Python ≡ Port on the coordinate-dedup case store after B3: 545707b9
    keeps its 5 its own reps and stays manifold at 2,266 triangles with
    the coordinate dedup's fire gate never engaging (no dedup outcome),
    and b912cbef keeps its committed emission (49,780 triangles after
    #62 admitted its extended record and #64 admitted two escaped-form
    ones) with no dedup outcome at all."""
    import shutil
    import subprocess

    from catpart.geometry import build_export

    checked = {**DEDUP_COORD_CASE, **DEDUP_COORD_NO_REGRESSION}
    paths = _corpus_part_paths(checked)
    assert set(paths) == set(checked), "manifest/corpus rows missing"
    root = Path(__file__).resolve().parents[1]
    cargo = shutil.which("cargo")
    assert cargo is not None, "cargo is a required dev dependency (spec §7)"
    build = subprocess.run(
        [cargo, "build", "--release", "--locked"],
        cwd=root / "port",
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr
    port_bin = root / "port" / "target" / "release" / "fidelity-cli"
    assert port_bin.is_file()
    for sha, path in sorted(paths.items()):
        python_ply = tmp_path / f"{sha}-python.ply"
        port_ply = tmp_path / f"{sha}-port.ply"
        summary = build_export(path, python_ply)
        assert summary["triangle_count"] == checked[sha]
        assert summary["mesh"]["manifold"] is True
        vertices, faces = parse_ply(python_ply)
        if sha in DEDUP_COORD_CASE:
            composite = summary["composite"]
            # B3 exports the store's own reps: the assembled mesh is
            # manifold without the dedup, so its fire gate (not-manifold)
            # never engages and no duplicate resolution is claimed.
            assert composite["reps_decoded"] == 5
            assert composite["reps_exported"] == 5
            assert "unordered_dedup_dropped" not in composite
            assert "unordered_dedup_declined" not in composite
            listed = 0.0
            seen_facets = set()
            unique = 0.0
            copies = 0
            for face in faces:
                area = _triangle_area(vertices, face)
                listed += area
                key = tuple(
                    sorted(
                        tuple(round(c, 6) for c in vertices[i]) for i in face
                    )
                )
                if key in seen_facets:
                    copies += 1
                    continue
                seen_facets.add(key)
                unique += area
            assert math.isclose(listed, 16192.314366, rel_tol=1e-9)
            # B3 exports the store's own reps: 384 facets are coincident
            # copies with identical winding, so the listed area counts
            # them twice while the unique surface does not.
            assert copies == 384
            assert math.isclose(unique, 12280.4249, rel_tol=1e-4)
        else:
            assert "unordered_dedup_dropped" not in summary["composite"]
            assert "unordered_dedup_declined" not in summary["composite"]
            assert "duplicate-triangles-deduped" not in _warning_classes(summary)
        port = subprocess.run(
            [str(port_bin), "export", str(path), str(port_ply)],
            capture_output=True,
            text=True,
        )
        assert port.returncode == 0, port.stderr
        assert json.loads(json.dumps(summary)) == json.loads(port.stdout)
        assert python_ply.read_bytes() == port_ply.read_bytes()


# --- the 0x49 triangle-list family (2026-11-18) ---------------------------
#
# The composite path admitted 0x42/0x4a/0x4c while the clean path already
# exported 0x49 as a strip (facets.SOUP_MARKERS). The corpus shows the
# family's record is NOT the generic count-table form: ``01 49 ty ff`` +
# ``u32le n`` + the 12-B normal + n u16be refs, no count table, n == 3*ty
# (docs/evidence/2026-11-18-composite-0x49.md). These tests pin the reader
# and the structural acceptance the admission rides on.


def _record_049(
    ty: int, normal, refs: tuple[int, ...], n_override: int | None = None
) -> bytes:
    """One 0x49 record: ``01 49 ty ff`` + u32le n + normal + u16be refs
    (no count table — the family's pinned law)."""
    n = len(refs) if n_override is None else n_override
    return (
        bytes([0x01, 0x49, ty, 0xFF])
        + struct.pack("<I", n)
        + struct.pack("<fff", *normal)
        + b"".join(struct.pack(">H", r) for r in refs)
    )


def test_parse_049_record_pins_the_no_count_law() -> None:
    """The 0x49 record carries NO count table: n == 3*ty u16be refs, one
    3-ref strip loop per triangle. The first reference's high byte (here
    0x02) is data, not a count — the generic count law would split the
    loop 2+1 and lose the triangle (the corpus misparse)."""
    refs = (0x0201, 0x058B, 0x0231)
    body = _record_049(1, (0.0, 0.0, 1.0), refs)
    records, n_hdrs = parse_strip_records(body, 0, len(body), 2000)
    assert n_hdrs == 1
    (record,) = records
    _o, marker, normal, counts, got_refs, width = record
    assert marker == 0x49
    assert normal == (0.0, 0.0, 1.0)
    assert counts == (3,)
    assert got_refs == refs
    assert width == 2


def test_parse_049_record_multi_triangle_split() -> None:
    """ty > 1: the refs split into ty loops of three (the family's
    triangle list), not one long strip."""
    refs = (0, 1, 2, 3, 4, 5, 6, 7, 8)
    body = _record_049(3, (0.0, 0.0, 1.0), refs)
    records, _n = parse_strip_records(body, 0, len(body), 64)
    (record,) = records
    assert record[3] == (3, 3, 3)
    assert record[4] == refs


def test_parse_049_record_rejects_n_not_three_ty() -> None:
    """A ``01 49`` byte pattern whose reference count is not 3*ty is not
    the family: it stays unresolved (no guessing)."""
    body = _record_049(2, (0.0, 0.0, 1.0), (0, 1, 2, 3, 4), n_override=5)
    records, _n = parse_strip_records(body, 0, len(body), 64)
    assert records == []


def test_parse_049_record_rejects_out_of_space_refs() -> None:
    """References beyond the decoded element space are rejected at the
    record law (the refs gate does not guess a mapping)."""
    body = _record_049(1, (0.0, 0.0, 1.0), (0, 1, 99))
    records, _n = parse_strip_records(body, 0, len(body), 64)
    assert records == []


def test_parse_049_record_rejects_a_record_past_the_next_header() -> None:
    """The record must end at or before the next facet header (the
    committed tiling law): a record whose ref block would swallow a
    following header is not accepted."""
    body = _record_049(2, (0.0, 0.0, 1.0), (0, 1, 2, 3, 4, 5))
    # Slot a 0x42 header inside the 0x49 ref block.
    truncated = body[:28] + bytes([0x01, 0x42, 0x01, 0xFF])
    records, _n = parse_strip_records(truncated, 0, len(truncated), 64)
    assert records == []


def test_triangulate_admits_049_written_loops() -> None:
    """A fully-written 0x49 triangle-list loop emits under the strip law
    (the admission): the marker is no longer skipped."""
    elements = [
        (0, (0.0, 0.0, 0.0)),
        (0, (1.0, 0.0, 0.0)),
        (0, (0.0, 1.0, 0.0)),
    ]
    record = (0, 0x49, (0.0, 0.0, 1.0), (3,), (0, 1, 2), 2)
    triangles, degenerate, stats = composite._triangulate(elements, [record])
    assert triangles == [(0, 1, 2)]
    assert degenerate == 0
    assert stats["loops_exported"] == 1
    assert stats["loops_curve_entry"] == 0


def test_triangulate_049_skip_loop_rides_the_structural_gate() -> None:
    """A skip-bearing 0x49 loop goes through the SAME structural
    acceptance as every other loop: the dup-pin weld's coplanarity
    battery. A coplanar loop welds (the pin is the preceding written
    vertex); a non-coplanar one is refused and stays dropped — no
    marker-specific bypass."""
    elements = [
        (0, (0.0, 0.0, 0.0)),
        (1, None),  # skip slot -> welds to element 0
        (0, (1.0, 0.0, 0.0)),
        (0, (0.0, 1.0, 0.0)),
    ]
    coplanar = (0, 0x49, (0.0, 0.0, 1.0), (3,), (1, 2, 3), 2)
    triangles, degenerate, stats = composite._triangulate(elements, [coplanar])
    assert triangles == []  # the weld's triangles merge at the store level
    assert degenerate == 0
    assert stats["loops_curve_entry"] == 1  # decremented when the weld merges
    assert stats["dup_pin"]["loops"] == 1
    # (skip->0, 2, 3) in written rank: the pinned triangle.
    assert stats["dup_pin"]["triangles"] == [(0, 1, 2)]

    # The same loop against a normal the pinned points are NOT on: the
    # battery refuses it, so the loop stays dropped and counted.
    tilted = (0, 0x49, (1.0, 0.0, 0.0), (3,), (1, 2, 3), 2)
    triangles, _degenerate, stats = composite._triangulate(elements, [tilted])
    assert triangles == []
    assert stats["loops_curve_entry"] == 1
    assert stats["dup_pin"]["loops"] == 0
    assert stats["dup_pin"]["refused"] == 1


def test_composite_0x49_fixture_exports_the_box(tmp_path, capsys):
    """End-to-end: the box whose -z face is re-listed as two 0x49
    triangle records exports the same closed 12-triangle manifold as
    the 0x4a form — the admission is marker-for-marker on one mesh."""
    code, captured, ply_path = run_export(tmp_path, capsys, "geometry-composite-law-0x49")
    assert code == 0, captured.err
    summary = json.loads(captured.out)
    assert summary["vertex_count"] == 12
    assert summary["triangle_count"] == 12
    assert summary["degenerate_triangle_count"] == 0
    assert summary["mesh"]["manifold"] is True
    assert summary["mesh"]["closed"] is True
    assert summary["mesh"]["boundary_edge_count"] == 0
    info = summary["composite"]
    assert info["loops_exported"] == 7  # 4 strips + 2 fans + 2 0x49 triangles
    assert info["loops_curve_entry"] == 0
    assert info["skipped_markers"] == {}  # 0x49 is exported, not skipped
    vertices, faces = parse_ply(ply_path)
    assert len(vertices) == 12 and len(faces) == 12


# --- 2026-11-20: the T3 relaxed facet families (#61) ---------------------
#
# 0x44 and 0x41 parse under the same (width, k) tiling law as the
# exported families (226/226 carrier records, header_len=4, no 12-B
# normal) but their primitive reading G3 has not pinned.  Their loops
# export in the SECOND pass of `_triangulate` under the STRICT mesh
# guard — no seam-area exception — plus the extended-family
# degenerate precondition (a loop carrying a degenerate emission is
# declined whole and its skip never counted), so a passing part's L2
# row cannot regress: manifold stays, degenerate_triangle_count stays 0.

CORPUS_RELAXED_CARRIERS = {
    # a 0x44 carrier that gains real surface: head_hueca_x1.5 (+18 tris,
    # +32,859 mm^2 of previously undisplayed geometry)
    "ab1c7b09f52a9658",
    # a 0x41-carrier washer (a61588e5) is pinned in PRIMARY_SEAM_FLIPS
}


def test_relaxed_families_export_under_the_strict_guard(tmp_path: Path) -> None:
    import csv

    root = Path(__file__).resolve().parents[1]
    rows = {
        r["sha256"][:16]: r
        for r in csv.DictReader((root / "manifests" / "corpus-manifest.csv").open())
        if r["kind"] == "part"
    }
    missing = [
        sha
        for sha in CORPUS_RELAXED_CARRIERS
        if sha not in rows or not (root / rows[sha]["local_path"]).exists()
    ]
    if missing:
        pytest.skip(f"corpus is absent ({len(missing)} carrier files missing)")

    from catpart.geometry import build_export

    for sha in CORPUS_RELAXED_CARRIERS:
        path = root / rows[sha]["local_path"]
        summary = build_export(path, tmp_path / f"{sha}.ply")
        info = summary["composite"]
        assert info.get("relaxed_loops_accepted", 0) >= 1, (sha, info)
        assert summary["mesh"]["manifold"] is True, sha
        assert summary["degenerate_triangle_count"] == 0, sha
        # admitted families are no longer reported as unresolved
        assert "0x44" not in str(info.get("skipped_markers", {})), sha


# --- 2026-11-20: the P1g-escaped extended header (#64) ----------------------


def _escaped_record(
    marker: int,
    ty_bytes: bytes,
    b3_bytes: bytes,
    b4_bytes: bytes,
    counts: tuple[int, ...],
    normal: tuple[float, float, float] | None,
    refs: tuple[int, ...],
    width: int = 2,
) -> bytes:
    """One escaped-header record: `01 <mk> <ty@P1g> <b3@P1g> <b4@P1g> ff
    <u32le n> [12B normal] <counts u8> <refs at width>`."""
    out = bytearray(bytes((0x01, marker)))
    out += ty_bytes + b3_bytes + b4_bytes + b"\xFF"
    out += struct.pack("<I", len(refs))
    if normal is not None:
        out += struct.pack("<fff", *normal)
    out += bytes(counts)
    fmt = {1: ">B", 2: ">H", 3: ">I"}[width]
    for r in refs:
        out += struct.pack(fmt, r)
    return bytes(out)


def test_parse_extended_facet_records_admits_the_p1g_escaped_header() -> None:
    """#64 (2026-11-20): the CAASdd gap form — `ty`/`b3`/`b4` may each
    escape via read_count (P1g) before the fixed `ff` + `u32le n`. The
    escaped records RANK repeats instead of disqualifying them (their
    exact-tile records carry legitimate strip joins), and the winner's
    refs must still resolve in-bounds."""
    # ty escaped (ff + u32le = 1), b3 = 1, b4 = 0, counts [3],
    # n = 3*1 + 3 = 6; the strip loop repeats ref 1 (a strip join).
    body = _escaped_record(
        0x47,
        b"\xFF" + struct.pack("<I", 1),
        b"\x01",
        b"\x00",
        (3,),
        None,
        (0, 1, 2, 3, 1, 4),
    )
    records, candidates = composite.parse_extended_facet_records(
        body, 0, len(body), element_count=64
    )
    assert candidates == 1
    (record,) = records
    assert record.triangles == 1
    assert record.strips == 1
    assert record.counts == (3,)
    assert record.refs == (0, 1, 2, 3, 1, 4)
    assert record.width == 2
    assert record.end == len(body)  # exact tiling
    # Out-of-range refs at the winning width: the candidate stays
    # unresolved (the false-positive rule).
    bad = _escaped_record(
        0x47,
        b"\xFF" + struct.pack("<I", 1),
        b"\x01",
        b"\x00",
        (3,),
        None,
        (0, 1, 2, 3, 1, 0xFFFF),
    )
    records, candidates = composite.parse_extended_facet_records(
        bad, 0, len(bad), element_count=64
    )
    assert candidates == 1
    assert records == []


def test_parse_extended_facet_records_b3_and_b4_escapes() -> None:
    """The `b3`-escaped (+3) and `b4`-escaped (+4) header shapes parse
    under the same law; the all-u8 6-byte form is untouched."""
    # b3 escaped (ff + u32le = 1), ty = 1 u8, b4 = 0: ff lands at +3.
    body = _escaped_record(
        0x4F,
        b"\x01",
        b"\xFF" + struct.pack("<I", 1),
        b"\x00",
        (3,),
        (0.0, 0.0, 1.0),
        (0, 1, 2, 3, 4, 5),
    )
    records, _ = composite.parse_extended_facet_records(
        body, 0, len(body), element_count=64
    )
    (record,) = records
    assert record.triangles == 1
    assert record.strips == 1
    assert record.normal == (0.0, 0.0, 1.0)
    # b4 escaped (ff + u32le = 1), b3 = 0: ff at +4, then the fixed ff.
    body = _escaped_record(
        0x47,
        b"\x01",
        b"\x00",
        b"\xFF" + struct.pack("<I", 1),
        (3,),
        None,
        (0, 1, 2, 3, 4, 5),
    )
    records, _ = composite.parse_extended_facet_records(
        body, 0, len(body), element_count=64
    )
    (record,) = records
    assert record.polygons == 1
    assert record.refs == (0, 1, 2, 3, 4, 5)



# --- the W1-B multi-region second chance (2026-11-22) ----------------------
#
# Function-level twins of the port's decode_multiregion tests: the body
# is a two-period composite body (each period = its own token node +
# records over that node's region; no pool groups, no edge groups — the
# stage-13 unrouted family the MB-Frames-middle stores belong to).


def _mr_record(marker, normal, refs):
    from fixtures_gen import _facet_record

    return _facet_record(marker, normal, tuple(refs), width=1)


def _mr_open_faces():
    """The box's five quads (the z+ face dropped: an open shell)."""
    return [
        (m, n, tuple(r))
        for m, n, r in COMPOSITE_FACES
        if not (m == 0x4A and r == (2, 8, 5, 11))
    ]


def _mr_other_diagonal_faces():
    """The same five quads triangulated with the OTHER diagonal: the
    strips swap to the (b, a, d, c) zigzag, the fans rotate to
    (b, c, d, a) — over the SAME element space the misresolved facets
    are distinct triangles (no coordinate-duplicate copy for the dedup
    to drop) that over-use every quad boundary edge."""
    out = []
    for m, n, r in _mr_open_faces():
        a, b, c, d = r
        out.append((m, n, (b, a, d, c) if m == 0x4A else (b, c, d, a)))
    return out


def _mr_body(rep0_records, rep1_records, elem0_extra=(), node0_tail=b""):
    from fixtures_gen import _composite_elements, _composite_node_payload

    pts0 = tuple(COMPOSITE_POINTS) + tuple(elem0_extra)
    pts1 = tuple((x + 200.0, y, z) for x, y, z in COMPOSITE_POINTS)
    elements0 = _composite_elements(pts0)
    elements1 = _composite_elements(pts1)
    parts = [
        b"\x04\x04\xfd\xff"
        + _composite_node_payload(elements0)
        + node0_tail
    ]
    for m, n, r in rep0_records:
        parts.append(_mr_record(m, n, r))
    parts.append(b"\x04\x04\xfd\xff" + _composite_node_payload(elements1))
    for m, n, r in rep1_records:
        parts.append(_mr_record(m, n, r))
    return b"".join(parts)


def _mr_decode(body):
    span = StoreSpan(
        block_start=0,
        origin=0,
        origin_kind="header",
        body_lo=0,
        body_hi=len(body),
        catalog_len=0,
    )
    return composite.decode_composite_store(
        body, span, [], [], allow_unrouted_elements=True
    )


def test_composite_multiregion_merges_per_period_regions():
    """The W1-B multi-region second chance (2026-11-22): a two-period
    body whose periods each carry their own token node + records over
    that node's region.  The single-rep reading resolves period 1's
    records against node 0's region — the misresolved other-diagonal
    facets over-use the quad boundary edges and the dedup declines (no
    coordinate duplicates) — and the relist post-pass declines too (its
    candidate grows the boundary set).  The multi-region route, which
    fires only on that still-not-manifold residue, decodes each period
    against its OWN region and is adopted: manifold, degenerate-free,
    both reps merged over disjoint index spaces (MB-Frames-middle-centr-
    YL's law: 50 walk-exact token nodes, the k-th panel's first written
    point at x = 1646.04 + 120k)."""
    body = _mr_body(_mr_open_faces(), _mr_other_diagonal_faces())
    points, triangles, degenerate, info = _mr_decode(body)
    assert info["stage"] == "identity-multiregion"
    assert info["multiregion_reps"] == 2
    assert degenerate == 0
    assert len(points) == 24
    assert len(triangles) == 20
    stats = mesh.mesh_stats(list(triangles))
    assert stats.manifold is True
    # both reps' open boxes export over their own disjoint space
    assert sum(1 for t in triangles if all(i < 12 for i in t)) == 10
    assert sum(1 for t in triangles if all(i >= 12 for i in t)) == 10


def test_composite_multiregion_nonmanifold_rep_declines_fail_closed():
    """A rep whose OWN reading is not manifold declines the adoption
    (the merged-mesh gate: manifold + degenerate-free, fail-closed) —
    rep 1 carries one fin triangle over-using a box edge, so the merged
    mesh stays not-manifold and the single-rep emission is kept
    byte-for-byte with the gap named on the summary."""
    rep1 = _mr_other_diagonal_faces() + [(0x42, None, (0, 2, 4))]
    body = _mr_body(_mr_open_faces(), rep1)
    points, triangles, degenerate, info = _mr_decode(body)
    assert info["stage"] == "identity-table-walk"
    assert "multiregion_declined" in info
    assert "not adopted" in info["multiregion_declined"]
    # the single-rep emission, unchanged: both periods misresolved onto
    # node 0's region plus the fin, still not manifold
    stats = mesh.mesh_stats(list(triangles))
    assert stats.manifold is False


# W10 (2026-11-22): the multi-region node scan's extent recovery — a
# period whose region opens with >= 16 full-write slots carries a
# leading-zero 2-bit table, the committed layout skip overshoots INTO
# it (stage-8 artifact 2), and the extent law recovers the unique
# walk-exact extent.

def _mr_x_order_faces(faces):
    """The box faces remapped onto the x-interleaved index order
    [0, 6, 1, 7, 2, 8, 3, 9, 4, 10, 5, 11]: consecutive elements
    alternate x = 0 / 20, so every written slot is a full triple
    (slot 0) and the 2-bit table's first four bytes are zero."""
    perm = [0, 6, 1, 7, 2, 8, 3, 9, 4, 10, 5, 11]
    inv = {old: new for new, old in enumerate(perm)}
    return [
        (m, n, tuple(inv[r] for r in refs)) for m, n, refs in faces
    ]


def _mr_extent_body():
    from fixtures_gen import _composite_elements, _composite_node_payload

    pts0 = tuple(COMPOSITE_POINTS)
    elements0 = _composite_elements(pts0)
    perm = [0, 6, 1, 7, 2, 8, 3, 9, 4, 10, 5, 11]
    pts1 = tuple(
        (x + 1.0, y, z) for k in perm for x, y, z in [COMPOSITE_POINTS[k]]
    ) + tuple(
        (60.0 + 20.0 * i, 500.0, 700.0) for i in range(4)
    )
    elements1 = _composite_elements(pts1, skip_slots=(16, 17, 18, 19))
    slots = [slot for slot, _pt in elements1]
    assert slots[:16] == [0] * 16 and slots[16:] == [1] * 4
    parts = [
        b"\x04\x04\xfd\xff"
        + _composite_node_payload(elements0)
        + b"\x00" * 140  # node 0's payload the largest (find_list_node)
    ]
    for m, n, r in _mr_open_faces():
        parts.append(_mr_record(m, n, r))
    parts.append(b"\x04\x04\xfd\xff" + _composite_node_payload(elements1))
    for m, n, r in _mr_x_order_faces(_mr_other_diagonal_faces()):
        parts.append(_mr_record(m, n, r))
    return b"".join(parts)


def test_composite_multiregion_extent_recovery_adopts_leading_zero_table():
    """W10 (2026-11-22): period 1's node payload opens with 16 full-
    write slots — its table's leading bytes are zero, the committed
    layout skip overshoots INTO the table and the primary walk fails
    (the stage-8 artifact-2 shape; measured corpus incidence: the ntu
    quartet's 12 period nodes per part, 4 not-manifold stores).  The
    multi-region node scan applies the committed extent law
    (:func:`_table_decode_extents`) as a second chance and recovers
    the unique walk-exact extent (the true table at counts_end + 4;
    the shifted candidate fails) — the per-period reading merges
    manifold and degenerate-free and is adopted, with the recovered
    rep named in ``multiregion_extent_reps``.  Fail-closed arm: the
    ambiguity stays declined inside :func:`_table_decode_extents`
    (covered by the stage-8 extent tests)."""
    body = _mr_extent_body()
    points, triangles, degenerate, info = _mr_decode(body)
    assert info["stage"] == "identity-multiregion"
    assert info["multiregion_reps"] == 2
    assert info["multiregion_extent_reps"] == 1
    assert degenerate == 0
    stats = mesh.mesh_stats(list(triangles))
    assert stats.manifold is True
