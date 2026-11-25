"""Corpus-free tests for the compact see-body face-GP route (W26).

The fixtures build the measured stream in this module:

- the ``04 04 fd ff`` node with its ``ff ff 02 00`` token, the
  ``a5 d4 68 53 00`` LCP header, the 2-bit slot table and the
  ``u32le`` write count (the walk-exact gate);
- the ``0x51`` face record with its optional
  ``[0x20|0x30] 04 04 ff ff <B><G><R>`` native-color header.

Every gate is fail-closed: a wrong write count, a record that does not
close byte-exact or an over-using edge leaves the part without a mesh.
"""

from __future__ import annotations

import struct

from catpart.geometry import build_export, mesh, seebody_gp

SHAPES = {0: 3, 1: 0, 2: 1, 3: 2}

TETRA = [
    (0.0, 0.0, 0.0),
    (10.0, 0.0, 0.0),
    (0.0, 10.0, 0.0),
    (0.0, 0.0, 10.0),
]
TETRA_TRIS = [(0, 2, 1), (0, 1, 3), (1, 2, 3), (0, 3, 2)]


def lcp_node(points, slots) -> bytes:
    """A compact node: token, LCP header, slot table, count, written words."""
    n_verts = len(points)
    assert len(slots) == n_verts
    floats = []
    for pt, slot in zip(points, slots):
        shape = SHAPES[slot]
        if shape == 3:
            floats += list(pt)
        elif shape == 2:
            floats += [pt[1], pt[2]]
        elif shape == 1:
            floats += [pt[2]]
    out = b"\x04\x04\xfd\xff"
    out += b"\xff\xff\x02\x00" + bytes([3 * n_verts])
    out += b"\x11" * 5
    out += b"\xa5\xd4\x68\x53\x00"
    table = bytearray((n_verts + 3) // 4)
    for i, slot in enumerate(slots):
        table[i // 4] |= slot << (2 * (i % 4))
    out += bytes(table)
    out += struct.pack("<I", len(floats))
    out += b"".join(struct.pack("<f", value) for value in floats)
    return out


def face_record(tris, n_verts: int, color=None, tail: bytes = b"\x00") -> bytes:
    """One ``0x51`` compact face record over the node's element space."""
    width = 1 if n_verts <= 255 else 2
    out = b""
    if color is not None:
        r, g, b = color
        out += b"\x30\x04\x04\xff\xff" + bytes([b, g, r])
    out += b"\x51" + struct.pack("<I", 1)
    out += b"\x02\x00\x33\x32"
    out += b"\x22" * 40
    out += struct.pack(">H", 3)
    out += bytes([len(tris), 0, 0])
    out += b"\x33" * 8
    for tri in tris:
        for vertex in tri:
            out += bytes([vertex]) if width == 1 else struct.pack(">H", vertex)
    return out + tail


def compact_part(color=None, tris=TETRA_TRIS, tail=b"\x00") -> bytes:
    return lcp_node(TETRA, [0, 0, 0, 0]) + face_record(tris, len(TETRA), color, tail)


def test_the_tetra_walks_exact_and_exports(tmp_path) -> None:
    path = tmp_path / "tetra.CATPart"
    path.write_bytes(compact_part())
    summary = build_export(path, tmp_path / "tetra.ply")
    assert summary["vertex_count"] == 4
    assert summary["triangle_count"] == 4
    assert summary["degenerate_triangle_count"] == 0
    assert summary["mesh"]["manifold"] is True
    assert summary["mesh"]["closed"] is True
    block = summary["seebody_gp"]
    assert block["source"] == seebody_gp.SOURCE
    assert block["nodes"] == 1
    assert block["records_total"] == 1
    assert block["records_exact_close"] == 1
    assert block["records_accepted"] == 1
    assert block["native_color_count"] == 1
    assert [w["class"] for w in summary["warnings"]] == [
        "seebody-compact-face-gp-meshed"
    ]


def test_the_native_color_header_is_read_bgr_to_rgb() -> None:
    # the header carries <B><G><R> = 10 20 30; the scan exposes RGB
    scan = seebody_gp.scan_part(compact_part(color=(0x30, 0x20, 0x10)))
    assert scan is not None
    assert scan.tri_colors == ((0x30, 0x20, 0x10),) * len(TETRA_TRIS)


def test_a_part_without_a_color_header_uses_catia_lavender_gray() -> None:
    scan = seebody_gp.scan_part(compact_part())
    assert scan is not None
    assert scan.tri_colors == (seebody_gp.DEFAULT_COLOR,) * len(TETRA_TRIS)


def test_a_wrong_write_count_declines_the_node() -> None:
    data = bytearray(compact_part())
    # the count sits right after the 1-byte slot table (4 vertices)
    at = data.find(b"\xa5\xd4\x68\x53\x00") + 5 + 1
    assert struct.unpack_from("<I", data, at)[0] == 12
    struct.pack_into("<I", data, at, 13)
    assert seebody_gp.scan_part(bytes(data)) is None


def test_an_over_using_edge_refuses_the_record() -> None:
    # edge 0-1 appears in all three triangles: the guard refuses the
    # whole record, so no mesh survives
    scan = seebody_gp.scan_part(
        compact_part(tris=[(0, 1, 2), (0, 1, 3), (0, 1, 3)])
    )
    assert scan is None


def test_a_record_that_does_not_close_byte_exact_is_not_emitted() -> None:
    # two trailing bytes after the record's own terminator: the stream
    # stops two bytes short of the extent, the closure gate refuses it
    scan = seebody_gp.scan_part(compact_part(tail=b"\x00\x00\x00"))
    assert scan is None


def test_a_truncated_stream_never_raises() -> None:
    data = compact_part()
    for cut in range(1, len(data), 7):
        assert seebody_gp.scan_part(data[:cut]) is None or isinstance(
            seebody_gp.scan_part(data[:cut]), seebody_gp.SeeBodyScan
        )


def test_the_merged_mesh_is_manifold_by_construction() -> None:
    scan = seebody_gp.scan_part(compact_part())
    assert scan is not None
    assert mesh.mesh_stats(list(scan.triangles)).manifold is True
