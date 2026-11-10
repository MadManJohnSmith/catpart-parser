"""The nested store's facet records and their primitive semantics (G3).

Adapted from ``scripts/triage/decode_facet_semantics.py`` (G3's corpus
decoder) with the decode semantics unchanged; the triage script stays
the analysis tool (ticket #32).

Model (docs/evidence/2026-11-09-facet-semantics.md):

- Record grammar (F1): ``01 <mk> <ty> ff [u32le n][12B f32le normal]
  [k u8 counts][n refs]`` — markers 0x41-0x4f; the 12-byte normal
  payload appears on 0x49/0x4a/0x4c (and on the 5-byte-form markers
  0x4b/0x4e, whose header carries one extra byte before ``ff``). The k
  count bytes (0..4) sum to n and delimit the ty sub-loops. The
  reference width is per-record u8 or u16be (big-endian), chosen by the
  tiling law (F1w, as corrected 2026-11-10 #35): a record is accepted
  when some (width, k) parse ends at or before the next record header
  (or the body end); the exact-tiling parse wins, then — on a gap edge
  — the store-width context: the widths of the store's exact-tile
  records (those ending at the next header position) vote, and a
  unanimous vote wins the gap-edge tie-break (a cluster-final u16be
  record before a gap keeps its width); mixed votes or no exact tiles
  fall back to the narrower width. Records tile their region
  header-to-header; content that fails every parse is gap variant
  content (unresolved), not exported geometry.
- Index space (F2, correction C8): the references are LEXICOGRAPHIC
  RANKS of the pool coordinates (x, then y, then z), not walk positions
  — on the clean subset the strip reading under lex ranks reproduces the
  stored normals at 0.9923 vs 0.2746 under walk order.
- Primitive semantics (F3/F4/F9/F10): 0x4a loops (and 0x42, which is
  structurally identical without the normal payload) are triangle-strip
  segments — (r_t, r_{t+1}, r_{t+2}) with the flip on odd t, phase reset
  per loop; 0x4c loops are closed polygons in ring order, fan-
  triangulated from the first corner (orientation-preserving for the CCW
  ring order). 0x41/0x49 satisfy the byte law n == 3*type but their
  primitive reading is not established (they carry no count bytes in the
  grammar, so they contribute no loops); 0x44/0x4b/0x4e are open.
- Export convention (F5/F7): the winding law is counter-clockwise seen
  from the stored normal (right-hand rule, the OBJ/PLY convention) —
  every decoded triangle is emitted as-is; the only skips are
  degenerate strip triangles (a repeated vertex or an exactly-zero cross
  product). Repeated references are real geometry (strip joins / apex
  fans), never deduplicated.
"""

from __future__ import annotations

import dataclasses
import re
import struct

STRIP_RE = re.compile(rb"\x01[\x41-\x4f].\xff", re.DOTALL)

#: Loop families: strips (triangle-strip segments) and closed polygons.
STRIP_MARKERS = (0x41, 0x42, 0x49, 0x4A)
POLY_MARKERS = (0x4C,)
NORMAL_MARKERS_ALL = (0x49, 0x4A, 0x4B, 0x4C, 0x4E)  # carry the 12-B normal
SOUP_MARKERS = STRIP_MARKERS + POLY_MARKERS

#: Markers whose primitive semantics are pinned end-to-end by G3 (the
#: exported families); anything else a record parses under is reported
#: as an unresolved facet family in the summary warnings.
EXPORTED_MARKERS = (0x42, 0x4A, 0x4C)

MAX_REFS = 1_000_000  # G3's sanity cap on n


@dataclasses.dataclass(frozen=True)
class FacetRecord:
    """One facet record parsed under the (width, k) tiling law (F1/F1w)."""

    offset: int
    marker: int
    type: int
    header_len: int
    n: int
    width: int  # 1 = u8, 2 = u16be
    counts: tuple[int, ...]  # k loop-count bytes, summing to n
    refs: tuple[int, ...]  # lexicographic ranks into the pool
    end: int
    normal: tuple[float, float, float] | None


@dataclasses.dataclass(frozen=True)
class FacetScan:
    """The facet content of one store body."""

    candidates: int  # STRIP_RE header positions
    records: tuple[FacetRecord, ...]  # records accepted by the tiling law
    unresolved_candidates: int  # header positions no parse accepted
    skipped_markers: dict[int, int]  # parsed records outside EXPORTED_MARKERS


def parse_facet_record(
    data, o: int, body_hi: int, nxt: int, prefer_width: int = 1
) -> FacetRecord | None:
    """Parse one facet record at header offset ``o`` under the tiling law.

    ``nxt`` is the next record header offset (or the body end). The
    (width, k) combo must end at or before ``nxt``; the exact-tiling
    parse wins, then the narrower width — except on a gap edge
    (``end < nxt``), where ``prefer_width`` (the store-width context
    derived by :func:`scan_facets`, default 1 = the historical narrower
    width) wins the tie-break (F1/F1w). Returns ``None`` when no
    variant of the grammar validates — gap variant content.
    """
    mk = data[o + 1]
    ty = data[o + 2]
    header_len = 4 if data[o + 3] == 0xFF else 5
    if o + header_len + 4 > body_hi:
        return None
    n = int.from_bytes(data[o + header_len : o + header_len + 4], "little")
    if not (0 <= n <= MAX_REFS):
        return None
    has_normal = mk in NORMAL_MARKERS_ALL
    base = o + header_len + 4 + (12 if has_normal else 0)
    if base > body_hi:
        return None
    best = None
    for width in (1, 2):
        for k in range(0, 5):
            counts = [data[base + j] for j in range(k)]
            if not ((n > 0 and sum(counts) == n) or (n == 0 and k == 0)):
                continue
            end = base + k + width * n
            if end > nxt:
                continue
            if end == nxt:
                rank = (0, width)  # exact tiling wins; narrower on exact ties
            else:
                # Gap edge: the store-width context wins the tie-break
                # (P3-B, #35 2026-11-10); the default context of 1 keeps
                # the historical narrower-width preference.
                rank = (1, 0 if width == prefer_width else 1)
            if best is None or rank < best[0]:
                refs = [
                    int.from_bytes(
                        data[base + k + width * j : base + k + width * (j + 1)],
                        "big",
                    )
                    for j in range(n)
                ]
                best = (rank, width, counts, refs, end)
    if best is None:
        return None
    _, width, counts, refs, end = best
    normal = None
    if has_normal:
        normal = struct.unpack("<fff", data[o + header_len + 4 : o + header_len + 16])
    return FacetRecord(
        offset=o,
        marker=mk,
        type=ty,
        header_len=header_len,
        n=n,
        width=width,
        counts=tuple(counts),
        refs=tuple(refs),
        end=end,
        normal=normal,
    )


def scan_facets(data, body_lo: int, body_hi: int) -> FacetScan:
    """Walk the store body's facet region header-to-header (G3 scan_store).

    Candidates come from the ``01 [41-4f] . ff`` header regex; each
    accepted record's end positions the walk at the next header at or
    after it. Header positions no parse accepts are gap variant content
    and surface as ``unresolved_candidates``.

    The walk is preceded by a store-width pre-pass (F1w as corrected
    2026-11-10 #35): every candidate header is parsed under the default
    tie-break and the exact-tile records — those whose end equals the
    next header position — vote their width; a unanimous vote becomes
    the gap-edge tie-break width, mixed votes (or no exact tiles) keep
    the default narrower-width preference.
    """
    hdrs = [m.start() for m in STRIP_RE.finditer(data, body_lo, body_hi)]
    exact_widths: set[int] = set()
    for i, o in enumerate(hdrs):
        nxt = hdrs[i + 1] if i + 1 < len(hdrs) else body_hi
        rec = parse_facet_record(data, o, body_hi, nxt)
        if rec is not None and rec.end == nxt:
            exact_widths.add(rec.width)
    prefer = exact_widths.pop() if len(exact_widths) == 1 else 1
    records = []
    consumed: set[int] = set()
    i = 0
    while i < len(hdrs):
        o = hdrs[i]
        nxt = hdrs[i + 1] if i + 1 < len(hdrs) else body_hi
        rec = parse_facet_record(data, o, body_hi, nxt, prefer_width=prefer)
        if rec is None:
            i += 1
            continue
        records.append(rec)
        consumed.add(o)
        following = [h for h in hdrs if h >= rec.end]
        i = hdrs.index(following[0]) if following else len(hdrs)
    skipped: dict[int, int] = {}
    for rec in records:
        if rec.marker not in EXPORTED_MARKERS:
            skipped[rec.marker] = skipped.get(rec.marker, 0) + 1
    return FacetScan(
        candidates=len(hdrs),
        records=tuple(records),
        unresolved_candidates=len(hdrs) - len(consumed),
        skipped_markers=skipped,
    )


def lex_rank_map(pool: list[tuple[float, float, float]]) -> list[int]:
    """Pool positions ordered by lexicographic rank of (x, y, z) (F2/C8).

    ``lex[rank]`` is the pool's walk position of the rank-``rank``
    coordinate triple; ties keep walk order (Python's stable sort, as in
    G3's decoder). Duplicate coordinates are not deduplicated.
    """
    return sorted(
        range(len(pool)),
        key=lambda i: (pool[i][0], pool[i][1], pool[i][2]),
    )


def record_loops(rec: FacetRecord) -> list[tuple[int, ...]]:
    """Split the record's references into its ty sub-loops (the k count
    bytes delimit them; G2's law, retained by G3)."""
    loops = []
    o = 0
    for c in rec.counts:
        loops.append(rec.refs[o : o + c])
        o += c
    return loops


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


@dataclasses.dataclass(frozen=True)
class TriangleSoup:
    """The decoded triangle soup (G3's export convention)."""

    triangles: tuple[tuple[int, int, int], ...]  # pool walk positions
    degenerate_skipped: int


def decode_soup(
    pool: list[tuple[float, float, float]],
    lex: list[int],
    scan: FacetScan,
) -> TriangleSoup:
    """Decode the pinned facet families to a triangle soup (F3/F4/F5/F7).

    Strips: (r_t, r_{t+1}, r_{t+2}) with the flip on odd t, phase reset
    per loop. Polygons (0x4c): fan from the first corner. Skips exactly
    the degenerate strip triangles (repeated vertex or zero cross
    product — coordinate equality, as in G3's decoder); polygon fans
    skip only repeated vertices. Repeated references are real geometry.
    """
    triangles: list[tuple[int, int, int]] = []
    degenerate = 0
    for rec in scan.records:
        if rec.marker not in SOUP_MARKERS:
            continue
        for refs in record_loops(rec):
            pts = [lex[x] for x in refs]
            if rec.marker in POLY_MARKERS:
                for t in range(1, len(pts) - 1):
                    tri = (pts[0], pts[t], pts[t + 1])
                    a, b, c = pool[tri[0]], pool[tri[1]], pool[tri[2]]
                    if a == b or b == c or a == c:
                        degenerate += 1
                        continue
                    triangles.append(tri)
            else:
                for t in range(len(pts) - 2):
                    tri = (pts[t], pts[t + 1], pts[t + 2])
                    if t % 2 == 1:
                        tri = (tri[2], tri[1], tri[0])
                    a, b, c = pool[tri[0]], pool[tri[1]], pool[tri[2]]
                    if a == b or b == c or a == c or _cross(_sub(b, a), _sub(c, a)) == (
                        0.0,
                        0.0,
                        0.0,
                    ):
                        degenerate += 1
                        continue
                    triangles.append(tri)
    return TriangleSoup(triangles=tuple(triangles), degenerate_skipped=degenerate)
