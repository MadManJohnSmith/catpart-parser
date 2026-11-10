"""The nested store's vertex pool (G2 model, ticket #30).

Adapted from ``scripts/triage/decode_vertex_pool.py`` /
``decode_facet_semantics.py`` (G2/G3's corpus decoders) with the decode
semantics unchanged; the triage scripts stay the analysis tools
(ticket #32).

Model (docs/evidence/2026-11-09-vertex-pool.md):

- Pool groups are opened by the 8-byte wrapper ``10 24 04 ff ff 00 00
  00`` followed by the sub-kind ``01 06`` and a vertex count: one byte
  when it fits (<= 255), else ``ff`` escaping to a u32le count at +11
  (P1g). The 15-byte vertex records ``[05 08 01][f32le x][f32le y]
  [f32le z]`` follow contiguously and the walked record count equals the
  count field on every corpus group (P2/P2g, 2,090/2,090 = 1.000) — a
  mismatch is broken structure, not a variant, and raises
  ``malformed-pool-group``.
- Coordinates are little-endian float32 triplets, one vertex per record,
  interleaved (P3); 100% of corpus vertices are finite, so non-finite
  values raise ``malformed-pool-vertex``.
- Other sub-kinds after the same wrapper mark the composite index space:
  ``01 02`` groups are the 6-byte edge table (F8), ``ff ..`` wrappers
  open the trailer-named region — stores carrying either use a larger,
  undecoded reference space (G3 open question 1).

The exporter consumes the flattened pool of all groups in body order —
G3's soup convention (``pool = [v for g in pools for v in g]``).
"""

from __future__ import annotations

import dataclasses
import math
import struct

from catpart.geometry.errors import ExportError
from catpart.geometry.store import find_all

FULL_WRAP = b"\x10\x24\x04\xff\xff\x00\x00\x00"
VREC = b"\x05\x08\x01"
POOL_SUBKIND = b"\x01\x06"
EDGE_SUBKIND = b"\x01\x02"

MAX_COUNT = 1_000_000  # G2's sanity cap on the count field


@dataclasses.dataclass(frozen=True)
class PoolGroup:
    """One decoded ``01 06`` pool group (P1g/P2g)."""

    offset: int
    count_field: int
    vertices: tuple[tuple[float, float, float], ...]


def scan_pool_groups(data, body_lo: int, body_hi: int) -> tuple[list[PoolGroup], list[bytes]]:
    """Decode every pool group in the store body.

    Returns ``(groups, kinds)`` where ``kinds`` lists the sub-kind bytes
    found after every ``10 24 04 ff ff 00 00 00`` wrapper (``01 06`` =
    pool, ``01 02`` = edge group, ``ff ..`` = trailer opener) in body
    order — the composite-index-space markers of G3 claim F8.

    Raises ``malformed-pool-group`` when a group's walked vertex-record
    count differs from its count field (P2g violation) and
    ``malformed-pool-vertex`` on non-finite coordinates (P3 violation).
    """
    groups: list[PoolGroup] = []
    kinds: list[bytes] = []
    for o in find_all(data, FULL_WRAP, body_lo, body_hi):
        sub_kind = bytes(data[o + 8 : o + 10])
        kinds.append(sub_kind)
        if sub_kind != POOL_SUBKIND:
            continue
        b10 = data[o + 10]
        if b10 == 0xFF:
            if o + 15 > body_hi:
                continue  # G2: an insane wrapper is not an established group
            cnt = int.from_bytes(data[o + 11 : o + 15], "little")
            q = o + 15
        else:
            cnt = b10
            q = o + 11
        if not (1 <= cnt <= MAX_COUNT) or q + 15 * min(cnt, 4) > body_hi:
            continue  # G2's count sanity: not an established group
        vertices = []
        while len(vertices) < cnt and q + 15 <= body_hi and data[q : q + 3] == VREC:
            x, y, z = struct.unpack("<fff", data[q + 3 : q + 15])
            if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
                raise ExportError(
                    "malformed-pool-vertex",
                    f"pool group at {o}: non-finite f32le coordinate at "
                    f"vertex record {len(vertices)} (G2 P3: 100% finite "
                    "corpus-wide)",
                )
            vertices.append((x, y, z))
            q += 15
        if len(vertices) != cnt:
            raise ExportError(
                "malformed-pool-group",
                f"pool group at {o}: count field {cnt} but walked "
                f"{len(vertices)} vertex records (G2 P2g: the count field "
                "is a true count, 2,090/2,090 corpus groups walk exactly)",
            )
        groups.append(PoolGroup(offset=o, count_field=cnt, vertices=tuple(vertices)))
    return groups, kinds


def has_composite_space(kinds: list[bytes]) -> bool:
    """True when an ``01 02`` edge group or trailer opener marks the
    composite index space (G3 F8: references run beyond the pool there;
    the numbering is open, question 1)."""
    return any(k == EDGE_SUBKIND or k[:1] == b"\xff" for k in kinds)
