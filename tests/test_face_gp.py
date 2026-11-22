"""Corpus-free tests for the ``CATSurfacicRep`` patch-stream route (#63).

The shipped module (``catpart.geometry.face_gp``) decodes the ``0x51``
patch sub-records under the CAT3DFaceGP law and the export fallback
exports their folded mesh between the grid route and the display
carriers.  Every fixture here is bytes built in this module and no
corpus binary is read.

Pinned decisions:

- the declared array's floats start ONE WORD after its count (the
  measured writer layout); a denormal cloud, a non-finite tail or a
  part-scale overshoot refuses the whole array (the envelope gate);
- the strict per-sub-record gate is fail-closed on every axis: not
  byte-exact, kind != 3, an index off the 3-multiple grid, an index
  beyond the declared array, a repeated-index triangle, an over-using
  edge — each refuses the whole sub-record;
- the assembly folds in order under the unordered dedup (first copy
  wins, its winding kept) and the incremental mesh-safe guard (a
  member that tips an edge past two uses is refused whole, no trace);
- the export route fires only when the nested-store path, the a5 03 34
  surfaces and the structured grids all produced nothing, and its
  summary names the source (``bagrep-face-gp``) with manifold by
  construction and degenerate count 0.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from catpart.geometry import ExportError, build_export, face_gp, mesh

import fixtures_gen


def f32le(*values: float) -> bytes:
    return b"".join(struct.pack("<f", value) for value in values)


def declared_array(points, gap_word: int = 1) -> bytes:
    """A count-first declared array: ``u32le`` float count, ONE
    non-coordinate word (the measured writer layout), f32le triples."""
    floats = [value for point in points for value in point]
    return (
        struct.pack("<I", len(floats))
        + struct.pack("<I", gap_word)
        + f32le(*floats)
    )


def sub_record(
    tris=(),
    strips=(),
    fans=(),
    kind: int = 3,
    marker: bool = True,
    dangling: bool = True,
) -> bytes:
    """One ``0x51`` sub-record: pattern + flag + padding + the ``+57``
    header + (the marker) + the u16be index stream + the dangling byte.

    ``tris`` are vertex triples (the stream carries ``3 * vertex``);
    ``strips``/``fans`` are index sequences (``u32be`` count + count
    ``u16be`` values, in law order after the triangles).
    """
    body = b"\xff\x7f" if marker else b""
    for tri in tris:
        body += b"".join(struct.pack(">H", 3 * vertex) for vertex in tri)
    for values in (*strips, *fans):
        body += struct.pack(">I", len(values))
        body += b"".join(struct.pack(">H", value) for value in values)
    tail = b"\x00" if dangling else b""
    padding = b"\x11" * (face_gp.HEADER_AT - 9)
    header = struct.pack("<4I", kind, len(tris), len(strips), len(fans))
    return (
        face_gp.SUBREC + bytes([face_gp.FLAG_FACE_GP]) + padding + header + body + tail
    )


def counter_table_record(
    tris=(),
    strips=(),
    fans=(),
    dangling: bool = True,
) -> bytes:
    """One ``0x50`` counter-table sub-record: pattern + flag + padding +
    the ``+57`` header (kind 0) + the pad word + the ``u16be`` stream at
    ``+74`` (``3 * N_tris`` values, the count table, the concatenated
    values) + the dangling byte.

    ``tris`` are vertex triples (the stream carries ``3 * vertex``);
    ``strips``/``fans`` are value sequences (one ``u16be`` count each in
    the table, then the values concatenated, in law order).
    """
    stream = b""
    for tri in tris:
        stream += b"".join(struct.pack(">H", 3 * vertex) for vertex in tri)
    for values in (*strips, *fans):
        stream += struct.pack(">H", len(values))
    for values in (*strips, *fans):
        stream += b"".join(struct.pack(">H", value) for value in values)
    tail = b"\x00" if dangling else b""
    padding = b"\x11" * (face_gp.HEADER_AT - 9)
    header = struct.pack(
        "<4I", face_gp.KIND_COUNTER_TABLE, len(tris), len(strips), len(fans)
    )
    pad = b"\x00" * (face_gp.COUNTER_TABLE_AT - face_gp.HEADER_AT - 16)
    return (
        face_gp.SUBREC
        + bytes([face_gp.FLAG_COUNTER_TABLE])
        + padding
        + header
        + pad
        + stream
        + tail
    )


def face_gp_span(points, *subs) -> bytes:
    """A ``CATSurfacicRep`` class record: the framing, the declared
    array and the sub-records, closed by a following record framing."""
    return (
        struct.pack("<I", 14)
        + b"CATSurfacicRep"
        + declared_array(points)
        + b"".join(subs)
        + struct.pack("<I", 11)
        + b"CAT3DBagRep"
    )


TWELVE_POINTS = [
    (10.0 * i, 5.0 * (i % 3), 2.0 + i)
    for i in range(12)
]


def part(body: bytes) -> bytes:
    """A minimal part file (no store — the fallback chain runs)."""
    block = fixtures_gen.storage_property_block(b"CATPrtCont", b"CATContainer")
    return block + b"\x00" * 64 + body


def test_class_record_spans_frame_both_names() -> None:
    body = (
        struct.pack("<I", 11)
        + b"CAT3DBagRep"
        + struct.pack("<I", 14)
        + b"CATSurfacicRep"
        + declared_array(TWELVE_POINTS)
        + struct.pack("<I", 11)
        + b"CAT3DBagRep"
    )
    spans = face_gp._class_record_spans(body)
    assert [name for _s, _e, name in spans] == [
        "CAT3DBagRep",
        "CATSurfacicRep",
        "CAT3DBagRep",
    ]
    # the surfacic span ends at the NEXT record of either kind, so the
    # declared array is fully inside it
    surfacic = [s for s in spans if s[2] == "CATSurfacicRep"]
    assert len(surfacic) == 1
    start, end, _name = surfacic[0]
    assert face_gp._declared_arrays(body, start, end)


def test_declared_array_starts_one_word_after_the_count() -> None:
    body = face_gp_span(
        TWELVE_POINTS, sub_record(tris=[(0, 1, 2), (2, 3, 4)])
    )
    start = body.find(b"CATSurfacicRep") - 4
    arrays = face_gp._declared_arrays(body, start, len(body))
    assert len(arrays) == 1
    _offset, data_start, floats, points = arrays[0]
    assert floats == 3 * 12 and points == 12
    # the floats begin after the count AND the gap word: the first
    # triple reads the array's own coordinates (not the gap word)
    assert struct.unpack_from("<3f", body, data_start) == (0.0, 0.0, 2.0)


@pytest.mark.parametrize(
    "points",
    [
        # a denormal cloud (the corpus's junk arrays)
        [(1e-40 * i, 2e-40 * i, 3e-40 * i) for i in range(12)],
        # a part-scale overshoot
        [(1e6 + i, 0.0, 0.0) for i in range(12)],
    ],
)
def test_array_envelope_refuses_junk(points) -> None:
    body = face_gp_span(points, sub_record(tris=[(0, 1, 2), (2, 3, 4)]))
    assert face_gp.scan_part(body) is None


def test_decode_reads_triangles_strips_and_fans() -> None:
    built = sub_record(
        tris=[(0, 1, 2)],
        strips=[(0, 3, 6, 9)],
        fans=[(0, 6, 9, 12)],
    )
    decoded = face_gp.decode_sub_record(built, 0, len(built))
    assert decoded.kind == 3
    assert (decoded.n_tris, decoded.n_strips, decoded.n_fans) == (1, 1, 1)
    assert decoded.closed_exact
    # the marker sits at +73; the stream reads 1 triangle, then the
    # strip (u32be count + 4 values), then the fan (count + 4 values)
    assert decoded.pos_rel == face_gp.STREAM_AT + 2 + 6 + (4 + 8) + (4 + 8)
    # the strip/fan values are raw indices (3 * vertex): the strip's
    # windows and the fan's triangles read v = idx // 3
    assert decoded.triangles == (
        (0, 1, 2),  # the independent triangle
        (0, 1, 2),  # the strip's first window (values 0, 3, 6)
        (1, 2, 3),  # the strip's second window (values 3, 6, 9)
        (0, 2, 3),  # the fan's first triangle (fan head 0; 6, 9)
        (0, 3, 4),  # the fan's second triangle (fan head 0; 9, 12)
    )


def test_closure_is_byte_exact() -> None:
    exact = sub_record(tris=[(0, 1, 2), (2, 3, 4)])
    assert face_gp.decode_sub_record(exact, 0, len(exact)).closed_exact
    # two dangling bytes: the stream stops one short of len - 1
    open_ended = sub_record(tris=[(0, 1, 2), (2, 3, 4)]) + b"\x00"
    assert not face_gp.decode_sub_record(open_ended, 0, len(open_ended)).closed_exact
    # a declared N_tris larger than the stream stops the reads
    fat_header = face_gp.SUBREC + bytes([face_gp.FLAG_FACE_GP]) + b"\x11" * (
        face_gp.HEADER_AT - 9
    ) + struct.pack("<4I", 3, 9, 0, 0) + b"\xff\x7f" + struct.pack(
        ">HHH", 0, 3, 6
    ) + b"\x00"
    assert not face_gp.decode_sub_record(fat_header, 0, len(fat_header)).closed_exact


def test_strict_gate_axes() -> None:
    n = len(TWELVE_POINTS)
    built = sub_record(tris=[(0, 1, 2), (2, 3, 4)])
    good = face_gp.decode_sub_record(built, 0, len(built))
    assert face_gp._gate_sub_record(good, n)

    def refused(**kwargs) -> bool:
        built = sub_record(**kwargs)
        sub = face_gp.decode_sub_record(built, 0, len(built))
        return not face_gp._gate_sub_record(sub, n)

    assert refused(kind=2)  # not the face-GP kind
    assert refused(tris=[(1, 1, 4)])  # a repeated-index triangle
    assert refused(tris=[(0, 1, 20)])  # 20 >= 12 declared points
    # an index off the 3-multiple grid: the raw stream carries 3v+1
    built = sub_record(tris=[(0, 1, 2)])
    raw = bytearray(built)
    at = built.rfind(struct.pack(">H", 6))  # the last index word
    raw[at : at + 2] = struct.pack(">H", 7)
    sub = face_gp.decode_sub_record(bytes(raw), 0, len(raw))
    assert not face_gp._gate_sub_record(sub, n)
    # an over-using edge (both triangles share two edges with the same
    # winding over-use): (0,1,2) + (2,0,3) reuse edge 0-2 twice is fine,
    # three uses is not
    over = sub_record(tris=[(0, 1, 2), (2, 0, 3), (0, 2, 4)])
    sub = face_gp.decode_sub_record(over, 0, len(over))
    assert not face_gp._gate_sub_record(sub, n)


def test_assembly_dedup_keeps_the_first_winding() -> None:
    # the second sub-record re-lists the first's triangle with the
    # opposite winding: the dedup drops it (first copy wins) and the
    # folded winding is the first's
    first = [(0, 1, 2), (2, 3, 4)]
    second = [(2, 1, 0), (2, 3, 4)]
    folded, dropped, refused = face_gp._assemble([first, second])
    assert dropped == 2
    assert refused == 0
    assert folded == first


def test_assembly_guard_refuses_whole_members() -> None:
    # the first member uses edge 0-3 twice (triangles 2 and 3), so the
    # second member's shared edge tips the histogram past two uses and
    # is refused WHOLE (its triangles leave no trace)
    first = [(0, 1, 2), (2, 3, 0), (0, 3, 5)]
    second = [(0, 3, 4)]
    folded, dropped, refused = face_gp._assemble([first, second])
    assert (folded, dropped, refused) == (first, 0, 1)
    assert mesh.mesh_stats(folded).manifold


def test_scan_folds_the_span_and_offsets_the_second() -> None:
    points_b = [(100.0 + i, 1.0 * i, 2.0) for i in range(12)]
    body = (
        struct.pack("<I", 14)
        + b"CATSurfacicRep"
        + declared_array(TWELVE_POINTS)
        + sub_record(tris=[(0, 1, 2), (2, 3, 4)])
        + struct.pack("<I", 14)
        + b"CATSurfacicRep"
        + declared_array(points_b)
        + sub_record(tris=[(0, 1, 2)])
        + struct.pack("<I", 11)
        + b"CAT3DBagRep"
    )
    scan = face_gp.scan_part(body)
    assert scan is not None
    assert scan.records == 2
    assert scan.triangles == (
        (0, 1, 2),
        (2, 3, 4),
        (12, 13, 14),  # the second span's vertices are offset by 12
    )
    assert len(scan.vertices) == 24
    assert scan.vertices[0] == TWELVE_POINTS[0]
    assert scan.vertices[12] == points_b[0]


def test_export_route_fires_with_the_source_label(tmp_path: Path) -> None:
    body = part(
        face_gp_span(TWELVE_POINTS, sub_record(tris=[(0, 1, 2), (2, 3, 4)]))
    )
    path = tmp_path / "facegp.CATPart"
    path.write_bytes(body)
    summary = build_export(path, tmp_path / "facegp.ply")
    assert summary["triangle_count"] == 2
    assert summary["vertex_count"] == 12
    block = summary["bagrep_face_gp"]
    assert block["source"] == face_gp.SOURCE
    assert block["records"] == 1
    assert block["sub_records_gated"] == 1
    assert summary["mesh"]["manifold"]
    assert summary["degenerate_triangle_count"] == 0
    classes = [warning["class"] for warning in summary["warnings"]]
    assert classes[0] == "bagrep-face-gp-meshed"
    # the PLY carries the declared array's coordinates verbatim
    ply = (tmp_path / "facegp.ply").read_bytes()
    assert struct.pack("<fff", *TWELVE_POINTS[0]) in ply


def test_export_falls_through_to_display_without_a_clean_array(
    tmp_path: Path,
) -> None:
    # the only array is a denormal cloud: the route yields nothing and
    # the file keeps its pre-face-gp classification (no displayable
    # carrier either, so the original error re-raises)
    junk = [(1e-40 * i, 2e-40 * i, 3e-40 * i) for i in range(12)]
    body = part(face_gp_span(junk, sub_record(tris=[(0, 1, 2), (2, 3, 4)])))
    path = tmp_path / "junk.CATPart"
    path.write_bytes(body)
    with pytest.raises(ExportError) as excinfo:
        build_export(path, tmp_path / "junk.ply")
    assert excinfo.value.error_class == "missing-geometry-store"


def test_grid_route_keeps_its_priority(tmp_path: Path) -> None:
    # a triangulable grid on top of a face-gp span: the grid route wins
    # (priority facets > a5 surface > grid > face-gp > display)
    body = fixtures_gen.build_fixture("part", seed=0, variant="geometry-point-grid")
    path = tmp_path / "both.CATPart"
    path.write_bytes(body + face_gp_span(TWELVE_POINTS, sub_record(tris=[(0, 1, 2)])))
    summary = build_export(path, tmp_path / "both.ply")
    assert "grid_meshing" in summary
    assert "bagrep_face_gp" not in summary


def test_route_never_raises_on_a_truncated_pattern(tmp_path: Path) -> None:
    # a pattern match whose header would run past the file end: the
    # scan refuses it and the export keeps the pre-face-gp behavior
    # (no displayable carrier — the original error re-raises)
    body = part(face_gp_span(TWELVE_POINTS, sub_record(tris=[(0, 1, 2)])))
    path = tmp_path / "trunc.CATPart"
    path.write_bytes(body[:-40])
    with pytest.raises(ExportError) as excinfo:
        build_export(path, tmp_path / "trunc.ply")
    assert excinfo.value.error_class == "missing-geometry-store"


def test_counter_table_law_reads_triangles_and_the_count_table() -> None:
    # one independent triangle, one strip declared by the table (4
    # values -> 2 windows), one fan (4 values -> 2 triangles): the same
    # mult-3 encoding, kind 0
    built = counter_table_record(
        tris=[(0, 1, 2)],
        strips=[(0, 3, 6, 9)],
        fans=[(0, 6, 9, 12)],
    )
    decoded = face_gp.decode_sub_record(built, 0, len(built))
    assert decoded.flag == face_gp.FLAG_COUNTER_TABLE
    assert decoded.kind == face_gp.KIND_COUNTER_TABLE
    assert (decoded.n_tris, decoded.n_strips, decoded.n_fans) == (1, 1, 1)
    assert decoded.closed_exact
    assert decoded.pos_rel == len(built) - 1
    assert decoded.triangles == (
        (0, 1, 2),  # the independent triangle
        (0, 1, 2),  # the strip's first window (values 0, 3, 6)
        (1, 2, 3),  # the strip's second window (values 3, 6, 9)
        (0, 2, 3),  # the fan's first triangle (fan head 0; 6, 9)
        (0, 3, 4),  # the fan's second triangle (fan head 0; 9, 12)
    )


def test_counter_table_gate_is_the_strict_gate_at_kind_0() -> None:
    n = len(TWELVE_POINTS)
    built = counter_table_record(tris=[(0, 1, 2), (2, 3, 4)])
    good = face_gp.decode_sub_record(built, 0, len(built))
    assert face_gp._gate_sub_record(good, n)

    # a kind other than the framing's kind refuses
    wrong = bytearray(counter_table_record(tris=[(0, 1, 2)]))
    at = wrong.find(struct.pack("<I", face_gp.KIND_COUNTER_TABLE))
    wrong[at : at + 4] = struct.pack("<I", 3)
    sub = face_gp.decode_sub_record(bytes(wrong), 0, len(wrong))
    assert not face_gp._gate_sub_record(sub, n)

    # an out-of-bounds index refuses
    oob = counter_table_record(tris=[(0, 1, 20)])
    sub = face_gp.decode_sub_record(oob, 0, len(oob))
    assert not face_gp._gate_sub_record(sub, n)

    # two dangling bytes: not byte-exact, refused
    loose = counter_table_record(tris=[(0, 1, 2)])
    sub = face_gp.decode_sub_record(loose + b"\x00", 0, len(loose) + 1)
    assert not sub.closed_exact
    assert not face_gp._gate_sub_record(sub, n)


def test_counter_table_folds_into_the_span_scan() -> None:
    body = face_gp_span(
        TWELVE_POINTS,
        counter_table_record(tris=[(0, 1, 2)], strips=[(6, 9, 12, 15)]),
        sub_record(tris=[(0, 1, 2), (2, 3, 4)]),
    )
    scan = face_gp.scan_part(body)
    assert scan is not None
    assert scan.records == 1
    assert scan.sub_records == 2
    assert scan.sub_records_gated == 2
    assert scan.sub_records_counter == 1
    assert scan.sub_records_counter_gated == 1
    # counter-table member first ((0,1,2) + strip windows (2,3,4),
    # (3,4,5)); the face-GP member's two triangles re-list both sorted
    # keys, so the dedup drops them (first copy wins)
    assert scan.triangles == ((0, 1, 2), (2, 3, 4), (3, 4, 5))
    assert scan.dedup_dropped == 2


def test_an_interleaved_counter_table_ends_the_face_gp_record() -> None:
    # the writer emits 0x50/0x51 interleaved: the 0x51 record's extent
    # ends at the 0x50 that follows it, so the scan must not run it
    # past its neighbor (that span could not close)
    body = face_gp_span(
        TWELVE_POINTS,
        sub_record(tris=[(0, 1, 2), (2, 3, 4)]),
        counter_table_record(strips=[(9, 12, 15)]),
    )
    scan = face_gp.scan_part(body)
    assert scan is not None
    assert scan.sub_records == 2
    assert scan.sub_records_gated == 2
    assert scan.triangles == ((0, 1, 2), (2, 3, 4), (3, 4, 5))
