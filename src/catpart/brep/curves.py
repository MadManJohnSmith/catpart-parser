"""B-rep boundary curve decoders (BR3, ticket #55, Spec G #47).

Decodes the curve-record families and the edge/vertex tables of the
nested ``CATStdCont`` store body.  Model provenance and corpus rates:
``docs/evidence/2026-11-17-br3-curves.md`` (BR3); the record layout
follows the byte-measured model of
``docs/evidence/2026-11-10-composite-space.md`` (C1) and
``docs/evidence/2026-11-09-vertex-pool.md`` (P1-P3), re-validated
corpus-wide on the L2-pass population by
``scripts/triage/decode_brep_curves.py``.

- Curve records: every record = a 7-B header ``<u8 a><u8 b><u16le id>
  <00><u16le len>`` + family ``33 3X`` + ``len`` payload bytes (C1).
  Families decoded here:
    - ``33 32`` line record (canonical form ``len == 2``): a 40-B
      f32le block follows the family bytes at +0x09 (9d) — floats
      ``[f0..f9]`` with the G2 ``[P][Q][P]+|Q|`` reading (``f6:f9``
      repeats ``f0:f3`` bit-exact, ``f9 == ||f3:f6||``) verified on the
      G2 small-store worked example and on a corpus subpopulation
      (P-rep 51,002/508,086 = 10.04%, ``|Q|`` 54,775/508,086 = 10.78%,
      skip-42 walk).  The per-field semantics of the remaining blocks
      stay open — the two laws hold and fail on records of the SAME
      store (per-store P-rep rates spread 0..1, median 0.59 over 813
      stores with >= 4 records), so the walker measures the laws as
      flags instead of rejecting.
    - ``33 37`` circle: 4 big-endian f32 ``(cx, cy, cz, r)`` + 2-B
      trailer (18 B payload).
    - ``33 33`` mid-ring circle: 6 big-endian f32 ``(cx, cy, cz, cos
      t, sin t, r)`` + 2-B trailer (26 B; the stage-4a "mid-ring"
      records, ``r`` observed negative; BR3 re-reads the stage-4a
      ``p1``/``p2`` params as an in-plane unit direction pair — the
      same pair shape as ``33 38`` (dominant values ``(0, 0)``,
      ``(+-1, 0)``, ``(0, +-1)``; corpus mid-range pairs 5,406/5,406
      unit).
    - ``33 38`` conic: 7 big-endian f32 ``(cx, cy, cz, cos t, sin t,
      a, b)`` + 2-B trailer (30 B).  BR3's direction law: the pair is
      unit-norm whenever mid-range and ``(0, 0)`` is the observed
      axis-aligned sentinel — 15,757/15,768 = 99.93% corpus records;
      ``b > 0`` on 15,757/15,757.
- Edge groups (TOP-06 / CRV-07): the pool wrapper ``10 24 04 ff ff 00
  00 00`` + sub-kind ``01 02`` + P1g count + records ``02 <n> <n
  refs>`` with per-group u8/u16be reference width resolved by exact
  end-alignment against the next wrapper (or store-body end) — the E1
  grammar.  Records with ``n > 2`` are the polyline strips (CRV-07).
- Unwrapped lists: ``01 01 <count>`` + the same record grammar ending
  exactly on a wrapper (E3).
- Vertex pool (TOP-07): ``catpart.geometry.pool.scan_pool_groups``
  (P1-P3); re-exported here as the vertex-table accessors of the
  boundary-curve slice.

Detector honesty (one line per class, echoed in the evidence note):
- The curve-record walker does NOT discriminate store sections or
  semantic roles: any byte pair ``33 3X`` behind a self-consistent
  7-B header with plausible lengths/values is accepted, so compressed
  streams can still carry pseudo-records (excluded only by the
  plausibility cap); it also does not discriminate which topology
  (edge, tessellation plate, mid-ring) consumes a record.
- ``decode_line`` (``33 32``) decodes the 40-B block LAYOUT only: it
  does NOT enforce the G2 ``[P][Q][P]+|Q|`` reading (laws measured as
  flags — they hold on a subpopulation and fail within single stores)
  and does not discriminate the segment orientation convention.
- ``decode_circle`` (``33 37``) does NOT discriminate a full circle
  from an arc — the payload carries no trim parameters — nor which
  face/edge binds the record.
- ``decode_midring`` (``33 33``) does not discriminate arc extent or
  the radius sign convention (negative radii observed on the anchors).
- ``decode_conic`` (``33 38``) does NOT discriminate ellipse from
  parabola from hyperbola: no eccentricity/type field is exposed at
  the decoded offsets (BR3 documented-open, ceiling arithmetic in the
  note); ``|a| == |b|`` records are reported as circle-form by the
  triage script, but the module does not assert the reading.
- ``decode_edge_group`` does not discriminate the element-space
  binding of its references (composite numbering, F8-corrected: refs
  index the full merged space, not only the pool).
"""

from __future__ import annotations

import dataclasses
import math
import struct

from catpart.geometry import pool
from catpart.geometry.errors import ExportError

WRAPPER = pool.FULL_WRAP
POOL_SUBKIND = pool.POOL_SUBKIND
EDGE_SUBKIND = pool.EDGE_SUBKIND
UNWRAPPED_TAG = b"\x01\x01"

FAMILIES = (0x32, 0x33, 0x36, 0x37, 0x38)
FAMILY_LINE = 0x32
FAMILY_MIDRING = 0x33
FAMILY_CIRCLE = 0x37
FAMILY_CONIC = 0x38

BE_F32 = struct.Struct(">f")
LE_F32 = struct.Struct("<f")
LINE_BLOCK = struct.Struct("<10f")

HEADER_BYTES = 7
MAX_RECORD_LEN = 256
MAX_VALUE = 1e7  # pool-scale plausibility cap for BE-float families
MAX_REFS = 4096  # per-record reference cap (composite-space walker)
MAX_GROUP_RECORDS = 1_000_000
MAX_LIST_RECORDS = 5000
DIR_TOL = 2e-3  # unit-norm tolerance for the 33 38 direction pair
LEN_TOL = 1e-6  # relative tolerance for the |Q| length law


@dataclasses.dataclass(frozen=True)
class CurveRecord:
    """One walked ``33 3X`` curve record (C1 layout)."""

    offset: int
    family: int
    tag_a: int
    ident: int
    length: int
    payload: bytes
    end: int  # offset just past the payload


@dataclasses.dataclass(frozen=True)
class LineSegment:
    """A ``33 32`` line record's 40-B f32le block (layout-decoded).

    The G2 ``[P][Q][P]+|Q|`` reading is carried as measured flags
    (``p_rep_ok``/``length_ok``), not as decoder preconditions: the
    laws hold on a corpus subpopulation and fail on records of the
    same store, so the per-field semantics stay open (BR3).
    """

    floats: tuple[float, ...]  # the 10 f32le values of the block
    p_rep_ok: bool  # f6:f9 repeats f0:f3 bit-exact
    length_ok: bool  # f9 == ||f3:f6|| (rel tol LEN_TOL)


@dataclasses.dataclass(frozen=True)
class CircleArc:
    """A ``33 37`` circle record (no trim parameters in the payload)."""

    center: tuple[float, float, float]
    radius: float


@dataclasses.dataclass(frozen=True)
class MidRingArc:
    """A ``33 33`` mid-ring circle record with its in-plane direction."""

    center: tuple[float, float, float]
    direction: tuple[float, float]
    radius: float


@dataclasses.dataclass(frozen=True)
class ConicArc:
    """A ``33 38`` conic record: center, in-plane direction, axes a/b."""

    center: tuple[float, float, float]
    direction: tuple[float, float]
    semi_a: float
    semi_b: float


@dataclasses.dataclass(frozen=True)
class EdgeGroup:
    """One decoded ``01 02`` edge group (E1 grammar)."""

    offset: int
    count: int
    width: int  # reference width in bytes: 1 or 2
    records: tuple[tuple[int, tuple[int, ...]], ...]  # (n, refs)


@dataclasses.dataclass(frozen=True)
class PolylineList:
    """One unwrapped ``01 01`` polyline list (E3 grammar)."""

    offset: int
    count: int
    width: int
    records: tuple[tuple[int, tuple[int, ...]], ...]


def _plausible(values: list[float]) -> bool:
    return all(math.isfinite(v) and abs(v) < MAX_VALUE for v in values)


def iter_curve_records(data, lo: int, hi: int) -> list[CurveRecord]:
    """Walk every ``33 3X`` curve record behind its 7-B header.

    A candidate is accepted when the family is known, the payload
    length is plausible (``0 < len <= 256``) and, for the BE-float
    families, the leading coordinates are finite and pool-scale — the
    compressed streams carry ``33 3X`` byte pairs whose "headers"
    decode as garbage and must not absorb the walk (C1).  The canonical
    ``33 32`` form (``len == 2``) carries a 40-B f32le block after the
    family bytes (byte-verified: 508,086/508,086 corpus blocks decode
    finite), so the walker resumes past the block instead of rescanning
    inside it.  Unusable candidates are skipped; the walk is a census
    walker, not a structural validator.
    """
    out: list[CurveRecord] = []
    p = lo
    while p < hi - HEADER_BYTES - 2:
        if data[p] == 0x33 and data[p + 1] in FAMILIES:
            ln = int.from_bytes(data[p - 2 : p], "little")
            fam = data[p + 1]
            if 0 < ln <= MAX_RECORD_LEN and p - 6 >= lo:
                pay = data[p + 2 : p + 2 + ln]
                ok = True
                if fam in (FAMILY_MIDRING, FAMILY_CIRCLE, FAMILY_CONIC):
                    nbe = min((ln - 2) // 4, 7)
                    vals = [
                        BE_F32.unpack_from(pay, 4 * i)[0] for i in range(nbe)
                    ]
                    ok = _plausible(vals)
                if ok:
                    out.append(
                        CurveRecord(
                            offset=p,
                            family=fam,
                            tag_a=data[p - 6],
                            ident=int.from_bytes(
                                data[p - 5 : p - 3], "little"
                            ),
                            length=ln,
                            payload=pay,
                            end=p + 2 + ln,
                        )
                    )
                    # 33 32 canonical (len == 2): resume past the
                    # following 40-B block (33 36's post-family bytes
                    # are NOT a finite-float block: 293,793/296,490
                    # corpus records fail the 10-finite-float read, so
                    # it tiles on 2 + len like the BE families).
                    p += LINE_BLOCK.size + 2 if fam == FAMILY_LINE and ln == 2 else 2 + ln
                    continue
        p += 1
    return out


def line_laws(block: bytes) -> tuple[bool, bool]:
    """The two G2 ``33 32`` laws over a 40-B f32le block.

    Returns ``(p_rep_ok, length_ok)``: the block's floats at +0x17
    (23d) repeat the first triple bit-exact, and the float at +0x23
    (35d) equals ``|Q| = ||Q||`` (relative tolerance ``LEN_TOL`` for
    the f32 rounding of the stored length).  Measured flags, not
    decoder preconditions (see the module docstring).
    """
    if len(block) < LINE_BLOCK.size:
        return False, False
    f = LINE_BLOCK.unpack(block[: LINE_BLOCK.size])
    p_rep_ok = f[6:9] == f[0:3]
    qx, qy, qz = f[3], f[4], f[5]
    norm = math.sqrt(qx * qx + qy * qy + qz * qz)
    length_ok = math.isclose(f[9], norm, rel_tol=LEN_TOL, abs_tol=0.0)
    return p_rep_ok, length_ok


def decode_line(record: CurveRecord, data) -> LineSegment:
    """Decode a ``33 32`` record's 40-B f32le block (layout only).

    ``record`` is the ``33 32`` record and ``data`` the full buffer:
    the block sits at +0x09 (9d) from the record offset — right after
    the family bytes.  Raises ``malformed-line-record`` when fewer
    than 40 bytes follow or the block is non-finite (the structural
    negative); the G2 law flags are measured, not enforced.
    """
    start = record.offset + 2
    block = data[start : start + LINE_BLOCK.size]
    if len(block) < LINE_BLOCK.size:
        raise ExportError(
            "malformed-line-record",
            f"33 32 record at {record.offset}: only {len(block)} B "
            "follow the family bytes, below the 40-B block layout",
        )
    f = LINE_BLOCK.unpack(block)
    if not _plausible(list(f)):
        raise ExportError(
            "malformed-line-record",
            f"33 32 record at {record.offset}: non-finite block values",
        )
    p_rep_ok, length_ok = line_laws(block)
    return LineSegment(floats=f, p_rep_ok=p_rep_ok, length_ok=length_ok)


def decode_circle(record: CurveRecord) -> CircleArc:
    """Decode a ``33 37`` record: 4 BE f32 ``(cx, cy, cz, r)`` + trailer.

    Raises ``malformed-circle-record`` on a non-finite center/radius or
    a zero radius (a zero-radius circle is not observed corpus-wide and
    carries no geometry).
    """
    if record.length < 18:
        raise ExportError(
            "malformed-circle-record",
            f"33 37 record at {record.offset}: payload {record.length} B "
            "is below the 18-B layout (4 BE f32 + 2-B trailer)",
        )
    cx, cy, cz, r = (BE_F32.unpack_from(record.payload, 4 * i)[0] for i in range(4))
    if not (math.isfinite(cx) and math.isfinite(cy) and math.isfinite(cz)) or not math.isfinite(r):
        raise ExportError(
            "malformed-circle-record",
            f"33 37 record at {record.offset}: non-finite center/radius",
        )
    if r == 0:
        raise ExportError(
            "malformed-circle-record",
            f"33 37 record at {record.offset}: zero radius",
        )
    return CircleArc(center=(cx, cy, cz), radius=r)


def decode_midring(record: CurveRecord) -> MidRingArc:
    """Decode a ``33 33`` record: ``(cx, cy, cz, cos t, sin t, r)`` BE f32.

    BR3 re-reads the stage-4a ``p1``/``p2`` params as an in-plane unit
    direction pair (same pair shape as ``33 38``).  ``r`` may be
    negative (observed on the stage-4a anchors).  Raises
    ``malformed-midring-record`` on the direction-law edges (a
    mid-range non-unit pair or a non-finite field).
    """
    if record.length < 26:
        raise ExportError(
            "malformed-midring-record",
            f"33 33 record at {record.offset}: payload {record.length} B "
            "is below the 26-B layout (6 BE f32 + 2-B trailer)",
        )
    v = [BE_F32.unpack_from(record.payload, 4 * i)[0] for i in range(6)]
    if not _plausible(v):
        raise ExportError(
            "malformed-midring-record",
            f"33 33 record at {record.offset}: implausible field values",
        )
    cos_t, sin_t = v[3], v[4]
    norm = math.sqrt(cos_t * cos_t + sin_t * sin_t)
    mid = DIR_TOL < abs(cos_t) < 1 - DIR_TOL and DIR_TOL < abs(sin_t) < 1 - DIR_TOL
    if mid and abs(norm - 1.0) > DIR_TOL:
        raise ExportError(
            "malformed-midring-record",
            f"33 33 record at {record.offset}: direction pair "
            f"({cos_t}, {sin_t}) has norm {norm:.6f}, not unit (BR3 "
            "direction law)",
        )
    return MidRingArc(center=(v[0], v[1], v[2]), direction=(cos_t, sin_t), radius=v[5])


def decode_conic(record: CurveRecord) -> ConicArc:
    """Decode a ``33 38`` record: ``(cx, cy, cz, cos t, sin t, a, b)``.

    BR3 laws (skip-42 canonical walk): the direction pair is unit-norm
    whenever mid-range and ``(0, 0)`` is the observed axis-aligned
    sentinel — 15,757/15,768 = 99.93% of corpus records decode under
    the law — and ``b > 0`` on 15,757/15,757.  Raises
    ``malformed-conic-record`` on violation.
    """
    if record.length < 30:
        raise ExportError(
            "malformed-conic-record",
            f"33 38 record at {record.offset}: payload {record.length} B "
            "is below the 30-B layout (7 BE f32 + 2-B trailer)",
        )
    v = [BE_F32.unpack_from(record.payload, 4 * i)[0] for i in range(7)]
    if not _plausible(v):
        raise ExportError(
            "malformed-conic-record",
            f"33 38 record at {record.offset}: implausible field values",
        )
    cos_t, sin_t = v[3], v[4]
    norm = math.sqrt(cos_t * cos_t + sin_t * sin_t)
    mid = DIR_TOL < abs(cos_t) < 1 - DIR_TOL and DIR_TOL < abs(sin_t) < 1 - DIR_TOL
    if mid and abs(norm - 1.0) > DIR_TOL:
        raise ExportError(
            "malformed-conic-record",
            f"33 38 record at {record.offset}: direction pair "
            f"({cos_t}, {sin_t}) has norm {norm:.6f}, not unit (BR3 "
            "direction law)",
        )
    if v[6] <= 0:
        raise ExportError(
            "malformed-conic-record",
            f"33 38 record at {record.offset}: b = {v[6]} not positive "
            "(BR3: b > 0 on 15,757/15,757 corpus records)",
        )
    return ConicArc(
        center=(v[0], v[1], v[2]), direction=(cos_t, sin_t), semi_a=v[5], semi_b=v[6]
    )


def _read_count(data, pos: int) -> tuple[int, int]:
    """P1g count: one byte, ``0xff`` escaping to a u32le at +1."""
    b = data[pos]
    if b == 0xFF:
        return int.from_bytes(data[pos + 1 : pos + 5], "little"), pos + 5
    return b, pos + 1


def _walk_records(data, pos: int, count: int, end: int, width: int):
    """Walk ``count`` records ``02 <n> <n refs>``; exact end-alignment.

    Returns ``(records, ok)``: ``ok`` requires every record to open
    with ``0x02``, carry ``n <= MAX_REFS`` and land exactly on ``end``.
    """
    records = []
    size = len(data)
    for _ in range(count):
        if pos + 2 > end or data[pos] != 0x02:
            return (), False
        n = data[pos + 1]
        pos += 2
        if n > MAX_REFS or pos + width * n > size:
            return (), False
        refs = []
        for _j in range(n):
            refs.append(int.from_bytes(data[pos : pos + width], "big"))
            pos += width
        records.append((n, tuple(refs)))
    return tuple(records), pos == end


def _resolve_width(data, pos, count, end):
    """Resolve the reference width by exact end-alignment (E1)."""
    for width in (1, 2):
        records, ok = _walk_records(data, pos, count, end, width)
        if ok:
            return width, records
    return None, ()


def scan_edge_groups(
    data, lo: int, hi: int, strict: bool = True
) -> list[EdgeGroup]:
    """Decode every ``01 02`` edge group in the store body (E1).

    The group's record region ends exactly at the next wrapper (any
    ``10 24 04 ff ff 00 00 00`` occurrence) or at ``hi``.  Groups whose
    records do not end-align under either width raise
    ``malformed-edge-group`` when ``strict`` (E1's named residue: 87
    stores corpus-wide do not land exactly); with ``strict=False`` the
    misaligned group is skipped and only aligned groups are returned.
    """
    wraps = list(pool.find_all(data, WRAPPER, lo, hi))
    bounds = sorted(set(wraps + [hi]))
    groups: list[EdgeGroup] = []
    for w in wraps:
        if bytes(data[w + 8 : w + 10]) != EDGE_SUBKIND:
            continue
        cnt, pos = _read_count(data, w + 10)
        if not (0 < cnt <= MAX_GROUP_RECORDS):
            if strict:
                raise ExportError(
                    "malformed-edge-group",
                    f"edge group at {w}: count field {cnt} outside the "
                    "P1g sanity range",
                )
            continue
        end = min((b for b in bounds if b > w), default=hi)
        width, records = _resolve_width(data, pos, cnt, end)
        if width is None:
            if strict:
                raise ExportError(
                    "malformed-edge-group",
                    f"edge group at {w}: {cnt} records do not end-align "
                    f"under u8 or u16be refs against bound {end} (E1 "
                    "residue)",
                )
            continue
        groups.append(EdgeGroup(offset=w, count=cnt, width=width, records=records))
    return groups


def scan_polyline_lists(data, lo: int, hi: int) -> list[PolylineList]:
    """Find unwrapped ``01 01 <count>`` polyline lists (E3).

    A list is accepted when its ``count`` records end-align exactly on
    some wrapper position or ``hi`` under either width.
    """
    wraps = list(pool.find_all(data, WRAPPER, lo, hi))
    ends = sorted(set(wraps + [hi]))
    out: list[PolylineList] = []
    pos = lo
    while True:
        pos = data.find(UNWRAPPED_TAG, pos, hi - 3)
        if pos < 0:
            break
        count = data[pos + 2]
        if 1 <= count <= MAX_LIST_RECORDS:
            for end in ends:
                if end <= pos:
                    continue
                width, records = _resolve_width(data, pos + 3, count, end)
                if width is not None:
                    out.append(
                        PolylineList(
                            offset=pos, count=count, width=width, records=records
                        )
                    )
                    break
        pos += 2
    return out


def scan_vertex_pool(data, lo: int, hi: int):
    """Vertex pool of the store body (TOP-07): P1-P3 via ``pool``.

    Re-raises ``malformed-pool-group`` / ``malformed-pool-vertex`` from
    ``catpart.geometry.pool`` — the count-field law is a structural
    validator there (2,090/2,090 corpus groups walk exactly).
    """
    return pool.scan_pool_groups(data, lo, hi)
