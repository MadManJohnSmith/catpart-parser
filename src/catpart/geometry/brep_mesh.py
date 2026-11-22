"""The B-rep meshing lane of the W2 marathon round (2026-11-22).

This module is the future ``brep_mesh`` export route's home. Its first
committed content is a **measured, unwired** decode: the counts-less
``0x49`` triangle-record family — the population behind the official
211 ``empty-mesh`` parts' biggest store (``PalmDown5motors2``:
171,916 of its 171,978 unresolved facet candidates parse here with
zero rejects).

The family law (W2 census 2026-11-22, corpus-measured, see
``docs/evidence/marathon/w2-progress.md`` and
``docs/evidence/data/w2-empty-mesh-baseline.csv``):

- header ``01 49 ty ff`` (4 B, the F1 4-byte form);
- ``u32le n`` with ``n == 3*ty`` (BR2-18's law, this family included);
- 12 B f32le unit normal (|n-1| <= 1e-6, BR2-06's bar);
- ``3*ty`` u16be big-endian references, no counts table — the family
  where the ty loops are implicit: loop i is refs[3i:3i+3], one
  triangle per loop;
- the record's end must stay inside the span.

Why it is NOT wired into the exporter: the family's references index
the composite element space, whose element region does not decode
under any committed law (the U3-variant residue + the stage-8
mixed-write miss — both fail ``undecoded-variant`` on every one of the
9 empty-mesh stores that carry a pool and facet records). The
mapping-refutation measurements are committed: under identity,
lex-rank, and offset-shifted mappings the records' mapped triangles
disagree with their stored normals (identity 1/800, lex 290/800,
offsets δ ∈ [-16,16] all ≤ 10/800 — a correct mapping scores ~100%,
the pool-only scope validates at 98.99%, BR2-10). A manifold-but-
scrambled assembly (180,859 triangles, manifold true, 98% of records
admitted by an EdgeGuard simulation) is exactly the geometry the
no-guessing gate refuses to ship.

Reopening criterion: when ``catpart.geometry.composite`` gains an
element-region decode law for these stores, the mapping validates
per-record (plane agreement) and the route assembles behind the
committed gates — in-bounds refs, unit normals, per-record manifold
admission (:class:`catpart.geometry.mesh.EdgeGuard`), degenerate
members filtered and named (the 2026-11-21 member-filter law) — and
this family becomes emitable alongside the accepted records. The
parser here is deliberately standalone so that day needs no re-derive.
"""

from __future__ import annotations

import dataclasses
import math
import struct

#: the family's marker and header form (the F1 4-byte form).
MARKER = 0x49
FORM = b"\x01\x49"

#: structural bound on ``ty`` (T65's base cap; the corpus measures ty
#: 1..5 on this family — anything above is unobserved, fail-closed).
MAX_TY = 16

#: the unit-normal bar (BR2-06: |n-1| <= 1e-6, 54,265/54,265 corpus).
UNIT_NORM_TOL = 1e-6

_HEADER = 4  # 01 49 ty ff
_N = 4  # u32le n
_NORMAL = 12  # 3 x f32le


@dataclasses.dataclass(frozen=True)
class CountlessTriangleRecord:
    """One counts-less ``0x49`` triangle record, structurally valid.

    ``refs`` are raw big-endian u16 values in the store's reference
    space (the composite element space on composite stores — the
    mapping into pool positions is the open question this module
    documents, never asserted). ``ty`` loops of 3 references each;
    ``n == 3*ty``.
    """

    offset: int
    ty: int
    n: int
    normal: tuple[float, float, float]
    refs: tuple[int, ...]
    end: int


def parse_countsless_record(data, o: int, body_hi: int):
    """Parse one counts-less ``0x49`` triangle record at ``o``.

    Fail-closed: ``None`` unless the header form, the ``n == 3*ty``
    law, the 12-byte unit normal, the in-bounds length and the
    references' span fit all hold. The references' VALUES are not
    bounds-checked here (the caller supplies the reference-space
    bound); the record's byte extent is.
    """
    if o + _HEADER > body_hi:
        return None
    if bytes(data[o : o + 2]) != FORM or data[o + 3] != 0xFF:
        return None
    ty = data[o + 2]
    if not (1 <= ty <= MAX_TY):
        return None
    if o + _HEADER + _N > body_hi:
        return None
    n = int.from_bytes(data[o + 4 : o + 8], "little")
    if n != 3 * ty:
        return None
    end = o + _HEADER + _N + _NORMAL + 2 * n
    if end > body_hi:
        return None
    normal = struct.unpack_from("<fff", data, o + 8)
    norm = math.sqrt(normal[0] ** 2 + normal[1] ** 2 + normal[2] ** 2)
    if not math.isfinite(norm) or abs(norm - 1.0) > UNIT_NORM_TOL:
        return None
    refs = tuple(
        int.from_bytes(data[o + 20 + 2 * j : o + 22 + 2 * j], "big")
        for j in range(n)
    )
    return CountlessTriangleRecord(
        offset=o, ty=ty, n=n, normal=normal, refs=refs, end=end
    )


@dataclasses.dataclass(frozen=True)
class FamilyCensus:
    """The counts-less family content of one span."""

    candidates: int  # STRIP_RE header positions in the span
    records: int  # family records that parse and validate
    unit_normal_rejects: int  # header matches failing the normal bar
    span_fit_rejects: int  # header matches running past the span


def census_family(data, lo: int, hi: int) -> FamilyCensus:
    """Census the counts-less ``0x49`` family over ``[lo, hi)``.

    Every ``STRIP_RE`` header position is tested; candidates inside
    another family record (overlaps are not observed — the corpus
    records tile at 26 B — but a defensive walk skips them) are not
    re-counted. Read-only.
    """
    from catpart.geometry import facets

    positions = [m.start() for m in facets.STRIP_RE.finditer(data, lo, hi)]
    records = 0
    unit_rejects = 0
    fit_rejects = 0
    skip_until = -1
    for o in positions:
        if o < skip_until:
            continue
        if o + _HEADER > hi or bytes(data[o : o + 2]) != FORM or data[o + 3] != 0xFF:
            continue
        ty = data[o + 2]
        if not (1 <= ty <= MAX_TY) or o + _HEADER + _N > hi:
            continue
        n = int.from_bytes(data[o + 4 : o + 8], "little")
        if n != 3 * ty:
            continue
        end = o + _HEADER + _N + _NORMAL + 2 * n
        if end > hi:
            fit_rejects += 1
            continue
        normal = struct.unpack_from("<fff", data, o + 8)
        norm = math.sqrt(normal[0] ** 2 + normal[1] ** 2 + normal[2] ** 2)
        if not math.isfinite(norm) or abs(norm - 1.0) > UNIT_NORM_TOL:
            unit_rejects += 1
            continue
        records += 1
        skip_until = end
    return FamilyCensus(
        candidates=len(positions),
        records=records,
        unit_normal_rejects=unit_rejects,
        span_fit_rejects=fit_rejects,
    )


def record_triangles(rec: CountlessTriangleRecord) -> list[tuple[int, int, int]]:
    """The family's triangle reading: loop i = refs[3i:3i+3].

    One triangle per loop, vertex order as stored (the winding's
    orientation question is part of the refuted-mapping note — the
    committed strip-flip law does not apply: the loops are 3-ref
    triangles, not strip segments).
    """
    return [
        (rec.refs[3 * i], rec.refs[3 * i + 1], rec.refs[3 * i + 2])
        for i in range(rec.ty)
    ]
