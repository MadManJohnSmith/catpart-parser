"""Binary little-endian PLY output (ticket #32).

Vertices are the decoded pool in walk order (G3's soup convention: the
committed OBJ's ``v`` lines), faces the decoded triangles as-is — the
winding law (F5: counter-clockwise seen from the stored normal, the
OBJ/PLY convention) is preserved by the decode, so the writer performs
no reordering. Coordinates are float32 (the pool is f32le, P3 — the
round-trip is exact); face indices are int32 through a uchar-3 count
list, the standard single-property PLY face element.
"""

from __future__ import annotations

import struct

_HEADER_TEMPLATE = (
    "ply\n"
    "format binary_little_endian 1.0\n"
    "comment catpart-export: CATStdCont nested-store geometry "
    "(G1/G2/G3 decode model, catpart-parser #32)\n"
    "element vertex {n_vertices}\n"
    "property float x\n"
    "property float y\n"
    "property float z\n"
    "element face {n_faces}\n"
    "property list uchar int vertex_indices\n"
    "end_header\n"
)


def write_binary_little_endian_ply(fh, vertices, faces) -> None:
    """Write the PLY to the open binary file handle ``fh``.

    ``vertices`` is a sequence of (x, y, z) float triples (the pool in
    walk order), ``faces`` a sequence of (a, b, c) vertex-index triples.
    """
    fh.write(
        _HEADER_TEMPLATE.format(n_vertices=len(vertices), n_faces=len(faces)).encode(
            "ascii"
        )
    )
    for x, y, z in vertices:
        fh.write(struct.pack("<fff", x, y, z))
    for a, b, c in faces:
        fh.write(struct.pack("<Biii", 3, a, b, c))
