"""The composite index space decoded under the recovered law (G6, #34).

Integrates the decode of the scene-graph list nodes' point streams into
the exporter (docs/evidence/2026-11-10-node-streams.md; stage-3b
refinements dated 2026-11-11, byte-measured on the corpus):

- Layout (P1t, stage-3b): the list node's payload = header + token
  ``ff ff 02 00 01`` + the declared counts (element_count,
  edge_ref_bound) + a zero block + **the 2-bit per-element table of
  exactly ``ceil(element_count / 4)`` bytes** + **a P1g count of the
  region's f32 words** (1 B, ``ff`` escapes to u32le) + the point
  region + a trailing region (semantics open, U2).  The stage-2c
  "+1 byte" table span was the write-count byte miscounted into it.
- Point region (U1, stage-3b, both forms): the table is 2 bits per
  element, LSB-first within each byte, one slot per element in region
  order; the value is the element's write shape in f32 words: 0 =
  ``[x][y][z]`` (3, an x-write/run start), 1 = skip (0 — the curve
  entries: no coordinates in the region, U4), 2 = ``[z]`` (1), 3 =
  ``[y][z]`` (2).  The walk's initial LCP state is the origin (P1i
  subsumed) and carries x/y/z across skip and suffix writes.  The walk
  is deterministic — no DP, no probe — and must consume exactly the
  declared write count (the walk-end check).
- Element space (M2b, stage-3b identity): the element space IS the
  region's element sequence — facet and edge references are 0-based
  element indices in region order (the stage-2c lex-sorted merge +
  monotone shift profile was the search artifact of matching refs onto
  written-point indices; the shift is the skip-slot count before the
  point).  Curve entries ARE referenced (the stage-2c "never
  referenced" inference is corrected); their coordinates live in the
  curve records (U4, open), so loops referencing skip slots contribute
  no triangles and are reported (labeled, not forced).  On every store
  the law decodes, the node list re-lists the pool verbatim (pool
  absorbed).
- Loop plane law (stage-3b): a fully-written loop of the one-plane-per
  -loop families (0x49 triangle lists, 0x4c closed polygons) must be
  coplanar against the record's stored 12-B normal (f32-rounding
  tolerance); the axis-constant reading was too strict (the big-store
  corner quads are slanted planes).  0x4a/0x42 strips are exempt: the
  stage-3b loop battery names multi-plane fillet/bevel strips as
  legitimate geometry where the per-triangle strip law (6.3.1
  GE-F3/F5) is the applicable test, not whole-loop coplanarity.

Decode paths (stage 3d): a region that walks byte-exact (the walk
consumes exactly the declared write count, every word finite) decodes
under the identity law on BOTH forms — the stage-2c big-form rejection
is replaced by the walk gate.  A region that does not walk keeps a
labeled ``undecoded-variant`` naming the walk-failure cause on big-form
stores (the second layout family, multi-part node payloads, is the
named residue, U3-variant); small-form stores fall back to the
stage-2c decode below (the value-DP over pool containment + the sigma
shift-profile CSP, itself fail-closed), which keeps the stage-2c
fixtures' decode (their encoding predates the walk layout) while the
walk covers the rest.  Stores whose region walks never reach the
sigma CSP (the sigma-explosion family is gone by construction; the
stage-3d replay measured 16 of the 61 formerly-exporting composite
stores with corrected PLY bytes — the table law fixes what the DP
inferred — docs/evidence/2026-11-10-node-streams.md, stage-3d).
"""

from __future__ import annotations

import heapq
import struct

from catpart.geometry.errors import ExportError
from catpart.geometry.facets import NORMAL_MARKERS_ALL

NODE_MAGIC = b"\x04\x04\xfd\xff"
LIST_TOKEN = b"\xff\xff\x02\x00\x01"
TAIL_MARK = b"\x00\x04\x02\x0a"

MAX_ELEMENT_COUNT = 10_000_000
MAX_TABLE_BYTES = 1 << 20
MAX_STATES = 400_000
MAX_LOOP_COUNTS = 16

# Stage 3d (#34): the walk gate replaces the big-form rejection; the
# walk law is form-independent, but the small form keeps the stage-2c
# DP fallback for stores whose region does not walk (the no-regression
# condition: every currently-exporting store must stay byte-identical —
# measured on the replay CSV, docs/evidence/data/replay-export-seam.csv).
WALK_SMALL_FORM = True

#: U1 (stage 3b): the 2-bit table value's write shape in f32 words —
#: 0 = ``[x][y][z]``, 1 = skip (curve entry, no coordinates), 2 =
#: ``[z]``, 3 = ``[y][z]``.
WALK_SHAPE_WORDS = {0: 3, 1: 0, 2: 1, 3: 2}

#: The loop plane law's tolerance: |(p - p0) . n| / |n| (f32 coordinate
#: rounding ~1e-4; the anchors' max residual is 5.4e-05).
WALK_PLANE_TOL = 2e-3

_F32 = struct.Struct("<f")

WARN_COMPOSITE = "composite-law-decode"

#: The record reference-width laws (:func:`parse_composite_facets`):
#: the stage-2c narrower-width gap behavior (the DP path's shipped
#: law) and the stage-3b no-repeat / no-out-of-bound disambiguation
#: (the identity path's law).
STAGE2C_LAW = "stage-2c"
WALK_LAW = "stage-3b"


def _f32(data, pos: int) -> float:
    return _F32.unpack_from(data, pos)[0]


def _nice(v: float) -> bool:
    """A plausible coordinate (the stage-2b probe's predicate, widened
    2026-11-11: an exact 0.0 is a legitimate coordinate — origin-placed
    geometry writes it — while sub-normal noise stays rejected)."""
    return v == v and abs(v) < 1e9 and (v == 0.0 or 1e-6 < abs(v))


def read_count(data, pos: int) -> tuple[int, int]:
    """P1g count: one byte, ff escapes to u32le. Returns (value, next_pos)."""
    if data[pos] == 0xFF:
        return int.from_bytes(data[pos + 1 : pos + 5], "little"), pos + 5
    return data[pos], pos + 1


def find_list_node(data, lo: int, hi: int):
    """The largest token-bearing scene-graph node in [lo, hi).

    Returns ``(payload, element_count, edge_ref_bound)`` or ``None``.
    Every composite store's node territory carries the token (N1,
    939/939); the LIST node is the one whose payload carries the point
    region — the largest payload (the stage-2b census).
    """
    best = None
    pos = lo
    while True:
        pos = data.find(NODE_MAGIC, pos, hi)
        if pos < 0:
            break
        end = data.find(NODE_MAGIC, pos + 4, hi)
        if end < 0:
            end = hi
        payload = bytes(data[pos + 4 : end])
        tok = payload.find(LIST_TOKEN)
        if 0 <= tok <= 64:
            p = tok + 5
            c1, p = read_count(payload, p)
            c2, p = read_count(payload, p)
            if 0 < c1 <= MAX_ELEMENT_COUNT:
                if best is None or len(payload) > len(best[0]):
                    best = (payload, c1, c2)
        pos += 1
    return best


def predict_region_start(payload: bytes, element_count: int) -> int:
    """Payload offset the point region opens at (P1 refined layout).

    The 2-bit per-element table spans ``ceil(element_count / 4) + 1``
    bytes after the zero block (32 B for 124 declared, 41 B for 160 —
    the +1 byte measured on both anchors; U1's semantics stay open).
    """
    q = payload.find(LIST_TOKEN)
    if q < 0:
        return -1
    p = q + 5
    _, p = read_count(payload, p)
    _, p = read_count(payload, p)
    while p + 4 <= len(payload) and payload[p : p + 4] == b"\x00\x00\x00\x00":
        p += 4
    table = (element_count + 3) // 4 + 1
    if table > MAX_TABLE_BYTES:
        return -1
    return p + table


def walk_layout(payload: bytes, element_count: int):
    """The stage-3b point-region layout after the zero block (P1t).

    The 2-bit per-element table spans **exactly ``ceil(element_count /
    4)`` bytes** after the zero block, followed by a P1g count of the
    region's f32 words (1 B, ``ff`` escapes to u32le), then the region.
    The stage-2c "+1 byte" span was the write-count byte miscounted into
    the table.  Returns ``(table_start, table_len, count_pos,
    region_start, write_count)``; :class:`ValueError` (labeled cause)
    when the layout does not fit the payload.
    """
    tok = payload.find(LIST_TOKEN)
    if tok < 0:
        raise ValueError("no list token")
    p = tok + 5
    _, p = read_count(payload, p)
    _, p = read_count(payload, p)
    while p + 4 <= len(payload) and payload[p : p + 4] == b"\x00\x00\x00\x00":
        p += 4
    table_len = (element_count + 3) // 4
    if table_len > MAX_TABLE_BYTES:
        raise ValueError(f"table of {table_len} B exceeds the cap")
    count_pos = p + table_len
    if count_pos >= len(payload):
        raise ValueError(
            f"table [{p}, {count_pos}) runs past the payload "
            f"({len(payload)} B): no write count follows it"
        )
    write_count, region_start = read_count(payload, count_pos)
    region_end = region_start + 4 * write_count
    if region_end > len(payload):
        raise ValueError(
            f"declared region of {write_count} words overruns the payload "
            f"({region_end} > {len(payload)})"
        )
    return p, table_len, count_pos, region_start, write_count


def _walk_nice(v: float) -> bool:
    """A finite coordinate (the walk needs no pruning predicate — the
    table fixes the parse — so the stage-2c probe's 1e-6 floor is
    dropped: real tessellation coordinates reach ~1e-15 around zero and
    junk detection falls to the walk-end / pool / plane checks)."""
    return v == v and abs(v) < 1e9


def walk_decode_region(payload: bytes, element_count: int):
    """Deterministic table-driven decode of the point region (U1, 3b).

    One slot per element in region order, LSB-first within each table
    byte; the slot's value is the element's write shape
    (:data:`WALK_SHAPE_WORDS`).  The walk's initial LCP state is the
    origin and carries x/y/z across skip and suffix writes; there is no
    DP and no probe — the table fixes the parse.

    Returns ``(elements, info)`` where ``elements[i] = (value, point_or
    _None)`` in region order (the point is ``None`` for skip slots —
    the curve entries, U4) and ``info`` carries the layout plus the
    walk verdict: ``walk_ok`` (the walk consumed exactly the declared
    write count and every word is finite) and ``failure`` (the labeled
    cause when it did not).
    """
    table_start, table_len, count_pos, region_start, write_count = walk_layout(
        payload, element_count
    )
    slots = []
    for i in range(table_start, table_start + table_len):
        b = payload[i]
        slots += [(b >> 0) & 3, (b >> 2) & 3, (b >> 4) & 3, (b >> 6) & 3]
    slots = slots[:element_count]
    pos = region_start
    x = y = z = 0.0  # the initial LCP state is the origin (P1i subsumed)
    elements = []
    failure = ""
    for i, v in enumerate(slots):
        shape = WALK_SHAPE_WORDS[v]
        if shape == 0:
            elements.append((v, None))
            continue
        if pos + 4 * shape > len(payload):
            failure = (
                f"the walk overruns the payload at element {i} "
                f"(element {pos}, {shape} words)"
            )
            elements.append((v, None))
            break
        if shape == 3:
            x, y, z = _f32(payload, pos), _f32(payload, pos + 4), _f32(payload, pos + 8)
            words = (x, y, z)
        elif shape == 2:
            y, z = _f32(payload, pos), _f32(payload, pos + 4)
            words = (y, z)
        else:
            z = _f32(payload, pos)
            words = (z,)
        pos += 4 * shape
        if not all(_walk_nice(c) for c in words) and not failure:
            failure = (
                f"element {i} writes a non-finite or out-of-range "
                f"coordinate (shape {shape}: {words})"
            )
        elements.append((v, (x, y, z)))
    slot_words = sum(WALK_SHAPE_WORDS[v] for v in slots)
    region_end = region_start + 4 * write_count
    if pos != region_end and not failure:
        failure = (
            f"the table walk does not consume the declared write count: "
            f"the slots' shapes total {slot_words} words but the declared "
            f"P1g count is {write_count} (walk end {pos} vs region end "
            f"{region_end})"
        )
    info = {
        "table_start": table_start,
        "table_len": table_len,
        "count_pos": count_pos,
        "write_count": write_count,
        "region_start": region_start,
        "region_bytes": 4 * write_count,
        "walk_end": pos,
        "walk_ok": pos == region_end and not failure,
        "failure": failure,
    }
    return elements, info


def _pool_pair_anchors(payload: bytes, pool_sorted):
    """Payload offsets opening a pool vertex's contiguous [y][z] write.

    The region opens at the list's first point: a full write whose
    (y, z) words match a pool vertex when the pool is re-listed
    verbatim.  Anchors give the candidate starts ``a - 4`` (full-write
    form) and ``a`` (implicit-x0 form); the value-DP scores them.
    """
    if not pool_sorted:
        return []
    pairs = {(v[1], v[2]) for v in pool_sorted}
    anchors = []
    seen = set()
    for off in range(0, len(payload) - 8):
        key = (
            _F32.unpack_from(payload, off)[0],
            _F32.unpack_from(payload, off + 4)[0],
        )
        if key in pairs and key not in seen:
            seen.add(key)
            anchors.append(off)
            if len(anchors) >= 6:
                break
    return anchors


def decode_stream(data, start: int, bound: int, pool_set, allow_reset: bool = False,
                  max_points: int | None = None):
    """Max pool-containment parse of [start, bound) under the point law.

    Value-DP over ``(position, last point, point count)`` states; the
    score is the pool-hit count (containment first), ties resolving to
    the fuller reading (more points) through the final selection.
    ``max_points`` prunes parses beyond the count law (the declared
    element count bounds the node points: element_count = node points
    + curve entries, curve entries >= 0).  Branch order per state:
    ``[x][y][z]`` (full write, lex-ascending; or run-reset when
    ``allow_reset``), ``[y][z]``, ``[z]``.  The initial state carries
    x = 0.0 implicitly: the first write may be ``[x][y][z]``, ``[y][z]``
    (x_first == 0), or ``[z]`` (x_first == y_first == 0).

    Returns ``(hits, points, end_pos, path)`` for the best parse, or
    ``None`` when no state exists.  ``end_pos`` is where the best
    parse's states die — the region's natural end (the trailing region
    does not encode points under the law).
    """
    scores: dict = {}
    parent: dict = {}
    heap: list = []

    def relax(st, val, par, pt):
        cur = scores.get(st)
        if cur is None or val > cur:
            scores[st] = val
            parent[st] = (par, pt)
            if len(scores) > MAX_STATES:
                return False
            heapq.heappush(heap, (st[0], st))
            return True
        return False

    init = []
    if bound - start >= 12:
        x0, y0, z0 = _f32(data, start), _f32(data, start + 4), _f32(data, start + 8)
        if _nice(x0) and _nice(y0) and _nice(z0):
            init.append(((start + 12, x0, y0, z0, 1), (x0, y0, z0)))
    if bound - start >= 8:
        y0, z0 = _f32(data, start), _f32(data, start + 4)
        if _nice(y0) and _nice(z0):
            init.append(((start + 8, 0.0, y0, z0, 1), (0.0, y0, z0)))
    if bound - start >= 4:
        z0 = _f32(data, start)
        if _nice(z0):
            init.append(((start + 4, 0.0, 0.0, z0, 1), (0.0, 0.0, z0)))
    for st, pt in init:
        relax(st, 1 if pt in pool_set else 0, None, pt)

    while heap:
        pos, st = heapq.heappop(heap)
        base = scores[st]
        if pos >= bound:
            continue
        px, py, pz, k = st[1], st[2], st[3], st[4]
        if max_points is not None and k >= max_points:
            continue
        cands = []
        if pos + 12 <= bound:
            x, y, z = _f32(data, pos), _f32(data, pos + 4), _f32(data, pos + 8)
            if _nice(x) and _nice(y) and _nice(z):
                lex_ok = (
                    x >= px
                    and (x > px or y >= py)
                    and (x > px or y > py or z >= pz)
                )
                if lex_ok or allow_reset:
                    cands.append(((pos + 12, x, y, z, k + 1), (x, y, z)))
        if pos + 8 <= bound:
            y, z = _f32(data, pos), _f32(data, pos + 4)
            if _nice(y) and _nice(z) and y >= py and (y > py or z >= pz):
                cands.append(((pos + 8, px, y, z, k + 1), (px, y, z)))
        if pos + 4 <= bound:
            z = _f32(data, pos)
            if _nice(z) and z >= pz:
                cands.append(((pos + 4, px, py, z, k + 1), (px, py, z)))
        for nst, pt in cands:
            relax(nst, base + (1 if pt in pool_set else 0), st, pt)

    if not scores:
        return None
    max_hits = max(scores.values())
    # candidate parses: the fuller readings among equally-containing
    # parses, one per distinct point count (the count law and the loop
    # mapping law arbitrate between them downstream)
    best_states = [
        st for st in scores
        if scores[st] == max_hits
        and (max_points is None or st[4] <= max_points)
    ]
    if not best_states:
        return None
    best_states.sort(key=lambda s: (-s[4], s[0]))
    parses = []
    seen_k = set()
    for st in best_states:
        if st[4] in seen_k:
            continue
        seen_k.add(st[4])
        path = []
        cur = st
        while cur is not None:
            par, pt = parent[cur]
            path.append(pt)
            cur = par
        path.reverse()
        parses.append((max_hits, len(path), st[0], path))
        if len(parses) >= 3:
            break
    return parses


def decode_node_points(payload: bytes, element_count: int, pool_sorted):
    """Decode the list node's point region (small form, refined P1 law).

    The predicted region start (the measured table layout) is tried
    first and wins outright when its parse contains every pool vertex
    (the pool is re-listed verbatim, absorbed) — other offsets only
    risk reading the 2-bit table as point writes.  Only when the
    prediction fails does the probe widen: the pool (y, z) pair
    anchors and a window around the prediction, the value-DP scoring
    each; a run-reset stage retries (the stream is a concatenation of
    lex-ascending runs).

    Returns a list of ``(points, stage, region_end)`` candidate parses,
    best containment first (the count law and the loop mapping law
    arbitrate; the caller validates).  Empty when the law does not
    decode the region.
    """
    pool_set = set(pool_sorted)
    predicted = predict_region_start(payload, element_count)
    tail = payload.rfind(TAIL_MARK)
    bound_raw = (tail - 4) if tail > 0 else len(payload)
    bound = min(len(payload), bound_raw + 8)

    # 1. the predicted start, alone: a full-containment parse here is
    # the law's reading (the table layout is byte-measured on both
    # anchors); wider probes would only add table-byte misreads.
    if 0 <= predicted and predicted + 12 <= len(payload):
        parses = decode_stream(
            payload, predicted, bound, pool_set,
            allow_reset=False, max_points=element_count,
        )
        if parses and parses[0][0] == len(pool_set):
            out = []
            seen = set()
            for _h, _k, end, path in parses:
                key = tuple(path)
                if key not in seen:
                    seen.add(key)
                    out.append((path, "lex", end))
            return out

    # 2. widen: anchors + window, lex stage then run-reset stage.
    cands = []
    if 0 <= predicted:
        cands.extend(range(max(0, predicted - 16), predicted + 17))
    for a in _pool_pair_anchors(payload, pool_sorted):
        cands.extend((a - 4, a))
    seen_start = set()
    starts = []
    for c in cands:
        if c in seen_start or c < 0 or c + 12 > len(payload):
            continue
        seen_start.add(c)
        starts.append(c)
    if not starts:
        return []

    candidates = []
    seen_paths = set()
    for allow_reset, stage in ((False, "lex"), (True, "reset")):
        stage_parses = []
        for s in starts:
            parses = decode_stream(
                payload, s, bound, pool_set,
                allow_reset=allow_reset, max_points=element_count,
            )
            stage_parses.extend(parses or [])
        if not stage_parses:
            continue
        max_hits = max(h for h, _k, _e, _p in stage_parses)
        # only equally-containing parses are candidates; among them the
        # fuller readings first (the count law arbitrates)
        picked = sorted(
            (p for p in stage_parses if p[0] == max_hits),
            key=lambda p: (-p[1], p[2]),
        )
        seen_k = set()
        for h, k, e, path in picked:
            if k in seen_k:
                continue
            seen_k.add(k)
            key = tuple(path)
            if key in seen_paths:
                continue
            seen_paths.add(key)
            candidates.append((path, stage, e))
            if len(candidates) >= 8:
                return candidates
        if max_hits == len(pool_set):
            break
    return candidates


def parse_composite_facets(
    data, body_lo: int, body_hi: int, width_law: str = "stage-2c", element_bound: int | None = None
):
    """Parse the facet records of a composite store body (counts law).

    Composite records carry up to ``MAX_LOOP_COUNTS`` count bytes
    summing to n (the clean-store grammar's k <= 4 does not hold here —
    026d6726's ``01 4a`` record carries 7); the reference width is
    per-record u8/u16be chosen by end-alignment onto the next header
    (or the body end), the exact-tiling parse winning, then the
    narrower width (the composite gap behavior the stage-2b validator
    used; the clean-store width-vote context does not apply here).

    ``width_law="stage-3b"`` (the identity path's law) adds the
    stage-3b width disambiguation to the rank — a parse whose loops
    repeat a reference inside one loop (the u8 misread of a u16be
    record) or whose references leave the element space
    (``element_bound``, the declared element count) ranks below a
    clean parse of the other width: the 13 ``counts=(8,)`` records of
    70b59f2a decode 0/13 coplanar as u8 and 13/13 as u16be.

    Returns ``(records, candidates)`` where each record is
    ``(offset, marker, normal, counts, refs)``; header positions no
    parse accepts are dropped (they surface as the gap between
    candidates and records).
    """
    import re

    strip_re = re.compile(rb"\x01[\x41-\x4f].\xff", re.DOTALL)
    hdrs = [m.start() for m in strip_re.finditer(data, body_lo, body_hi)]
    records = []
    for i, o in enumerate(hdrs):
        mk = data[o + 1]
        nxt = hdrs[i + 1] if i + 1 < len(hdrs) else body_hi
        header_len = 4 if data[o + 3] == 0xFF else 5
        if o + header_len + 4 > body_hi:
            continue
        n = int.from_bytes(data[o + header_len : o + header_len + 4], "little")
        if not (0 <= n <= 1_000_000):
            continue
        has_normal = mk in NORMAL_MARKERS_ALL
        base = o + header_len + 4 + (12 if has_normal else 0)
        if base > body_hi:
            continue
        normal = None
        if has_normal:
            normal = struct.unpack(
                "<fff", data[o + header_len + 4 : o + header_len + 16]
            )
        best = None
        for width in (1, 2):
            for k in range(0, MAX_LOOP_COUNTS + 1):
                if base + k > body_hi:
                    break
                counts = [data[base + j] for j in range(k)]
                if not ((n > 0 and sum(counts) == n) or (n == 0 and k == 0)):
                    continue
                end = base + k + width * n
                if end > nxt:
                    continue
                refs = [
                    int.from_bytes(
                        data[base + k + width * j : base + k + width * (j + 1)],
                        "big",
                    )
                    for j in range(n)
                ]
                if width_law == "stage-3b":
                    repeats = any(
                        len(set(refs[off : off + c])) < c
                        for off, c in _loop_offsets(counts)
                    )
                    oob = (
                        any(r >= element_bound for r in refs)
                        if element_bound is not None
                        else False
                    )
                    rank = (
                        0 if end == nxt else 1,
                        1 if repeats else 0,
                        1 if oob else 0,
                        width,
                        k,
                    )
                else:
                    rank = (0, width) if end == nxt else (1, 0 if width == 1 else 1)
                if best is None or rank < best[0]:
                    best = (rank, counts, refs, end)
        if best is None:
            continue
        _rank, counts, refs, _end = best
        records.append((o, mk, normal, tuple(counts), tuple(refs)))
    return records, len(hdrs)


def _loop_offsets(counts):
    """The ``(offset, count)`` pairs the count bytes delimit."""
    off = 0
    for c in counts:
        yield off, c
        off += c


def _loop_planarity_sets(records):
    """The planarity constraints: (axis, distinct refs) per normal-carrying
    loop; the exported-marker records' refs (all of them) are the
    node-mandatory positions."""
    loops_c = []
    refs_all = set()
    for _off, mk, normal, counts, refs in records:
        if mk not in (0x42, 0x49, 0x4A, 0x4C):
            continue
        refs_all.update(refs)
        if mk not in NORMAL_MARKERS_ALL:
            continue
        loops = []
        o = 0
        for c in counts:
            loops.append(refs[o : o + c])
            o += c
        axis = max(range(3), key=lambda k: abs(normal[k]))
        for loop in loops:
            if loop:
                loops_c.append((axis, frozenset(set(loop))))
    return loops_c, refs_all


def solve_shift_profile(points, elem_decl, records, max_solutions=64):
    """The element-mapping CSP (M2b, the sigma form).

    The merged space = the decoded node points + the curve entries,
    lex-sorted, positions 0..element_count-1.  A solution assigns each
    merged position to a node point (in list order — positions ascend
    with the point index) or a curve entry, i.e. the monotone shift
    profile sigma(idx) = curve entries before node point idx:

    - every facet/edge reference resolves to a node point (curve
      entries are construction geometry; the facet loops never
      reference them — measured on 026d6726: the profile that satisfies
      all loops plus this rule reproduces the anchor's planarity);
    - every normal-carrying record's loop maps onto points sharing one
      constant coordinate on the normal's dominant axis (the plane
      law);
    - the counts hold: npts node positions + (elem - npts) curve
      entries.

    Returns the list of solutions, each ``{idx: position}``; empty when
    the store admits none.  Deterministic (positions walked in order,
    node branch first).
    """
    npts = len(points)
    curves = elem_decl - npts
    if curves < 0:
        return []
    loops_c, refs_all = _loop_planarity_sets(records)
    if any(r >= elem_decl for r in refs_all):
        return []
    ref_loops: dict[int, list[int]] = {}
    for li, (_axis, fs) in enumerate(loops_c):
        for r in fs:
            ref_loops.setdefault(r, []).append(li)
    elem = elem_decl
    solutions: list[dict[int, int]] = []
    assign: dict[int, int] = {}

    def walk(p, idx, nc, loop_state):
        if len(solutions) >= max_solutions:
            return
        if p == elem:
            if idx == npts and nc == curves:
                solutions.append(dict(assign))
            return
        if (elem - p) != (npts - idx) + (curves - nc):
            return
        if idx < npts:
            pt = points[idx]
            ls2 = list(loop_state)
            ok = True
            for r in ref_loops.get(p, ()):
                rem, vals = ls2[r]
                axis, _fs = loops_c[r]
                nv = vals | {pt[axis]}
                if len(nv) > 1:
                    ok = False
                    break
                ls2[r] = (rem - 1, nv)
            if ok:
                assign[idx] = p
                walk(p + 1, idx + 1, nc, ls2)
                del assign[idx]
        if nc < curves and p not in refs_all:
            walk(p + 1, idx, nc + 1, loop_state)

    st0 = [(len(fs), frozenset()) for _a, fs in loops_c]
    walk(0, 0, 0, st0)
    return solutions


def _triangulate(points, records, pos_to_idx):
    """Triangles under one position assignment (strip/polygon semantics)."""
    triangles = []
    degenerate = 0
    unresolved = 0
    for _off, mk, _normal, counts, refs in records:
        if mk not in (0x42, 0x4A, 0x4C):
            continue
        loops = []
        o = 0
        for c in counts:
            loops.append(refs[o : o + c])
            o += c
        for loop in loops:
            if not loop:
                continue
            if any(r not in pos_to_idx for r in loop):
                unresolved += 1
                continue
            idxs = [pos_to_idx[r] for r in loop]
            lp = [points[i] for i in idxs]
            if mk == 0x4C:
                for t in range(1, len(lp) - 1):
                    tri = (idxs[0], idxs[t], idxs[t + 1])
                    a, b, c = lp[0], lp[t], lp[t + 1]
                    if a == b or b == c or a == c:
                        degenerate += 1
                        continue
                    triangles.append(tri)
            else:
                for t in range(len(lp) - 2):
                    tri = (idxs[t], idxs[t + 1], idxs[t + 2])
                    if t % 2 == 1:
                        tri = (tri[2], tri[1], tri[0])
                    a, b, c = lp[t], lp[t + 1], lp[t + 2]
                    if a == b or b == c or a == c:
                        degenerate += 1
                        continue
                    if _cross_zero(a, b, c):
                        degenerate += 1
                        continue
                    triangles.append(tri)
    return triangles, degenerate, unresolved


def _decode_identity(elements, winfo, elem_decl, node_bytes, records, candidates, poolv):
    """The M2b identity decode of a walk-exact region (stage 3d).

    The element space IS the region's element sequence: element ``i``
    is the table slot ``i`` — a written point (exported, in region
    order) or a skip slot (a curve entry whose coordinates live in the
    curve records, U4).  Facet and edge references are 0-based element
    indices; loops referencing skip slots contribute no triangles and
    are reported.  Fully-written loops of the one-plane-per-loop
    families (0x49/0x4c) must be coplanar against the record's stored
    normal (0x4a/0x42 strips are exempt — the stage-3b loop battery's
    multi-plane strips).  Raises :class:`ExportError` (``undecoded-
    variant``) with the specific gap on every law violation.
    """
    points = [pt for _v, pt in elements if pt is not None]
    skips = {i for i, (_v, pt) in enumerate(elements) if pt is None}
    elem_to_vertex = {}
    for ei, (_v, pt) in enumerate(elements):
        if pt is not None:
            elem_to_vertex[ei] = len(elem_to_vertex)

    pool_set = set(poolv)
    if len(pool_set & set(points)) != len(pool_set):
        missing = len(pool_set) - len(pool_set & set(points))
        raise ExportError(
            "undecoded-variant",
            f"node list does not re-list the pool: {missing} of "
            f"{len(pool_set)} pool vertices absent from the walked "
            "point region (unabsorbed variant; the merge law's pool "
            "absorption is not established there)",
        )

    skipref_loops = 0
    coplanar_loops = 0
    for _off, mk, normal, counts, refs in records:
        if mk not in (0x42, 0x49, 0x4A, 0x4C):
            continue
        if any(r >= elem_decl for r in refs):
            bad = max(refs)
            raise ExportError(
                "undecoded-variant",
                f"facet references beyond the element space: max ref "
                f"{bad} >= element count {elem_decl} (M2b identity: refs "
                "are 0-based element indices in region order; the "
                "records disagree with the walked region)",
            )
        if mk not in (0x49, 0x4C) or normal is None:
            # strips (0x4a/0x42) are exempt from the whole-loop plane
            # gate — the stage-3b loop battery names multi-plane
            # fillet/bevel strips as legitimate geometry where the
            # per-triangle strip law is the applicable test
            skipref_loops += sum(
                1 for _o, c in _loop_offsets(counts)
                if c and any(r in skips for r in refs[_o : _o + c])
            )
            continue
        nn = (normal[0] ** 2 + normal[1] ** 2 + normal[2] ** 2) ** 0.5
        for off, c in _loop_offsets(counts):
            loop = refs[off : off + c]
            if not loop:
                continue
            if any(r in skips for r in loop):
                skipref_loops += 1
                continue
            pts = [elements[r][1] for r in loop]
            if len(pts) < 2:
                continue  # a one-point loop carries no plane information
            if nn == 0:
                raise ExportError(
                    "undecoded-variant",
                    "normal-carrying loop with a zero stored normal "
                    f"(record 0x{mk:02x}): the loop plane law has "
                    "nothing to validate against (fail-closed)",
                )
            p0 = pts[0]
            residual = max(
                abs(
                    (
                        (p[0] - p0[0]) * normal[0]
                        + (p[1] - p0[1]) * normal[1]
                        + (p[2] - p0[2]) * normal[2]
                    )
                    / nn
                )
                for p in pts[1:]
            )
            if residual > WALK_PLANE_TOL:
                raise ExportError(
                    "undecoded-variant",
                    f"normal-carrying loop off the stored plane: residual "
                    f"{residual:.3g} > {WALK_PLANE_TOL} (record "
                    f"0x{mk:02x}, normal {normal}; the identity decode's "
                    "loop plane law fails — labeled, not forced)",
                )
            coplanar_loops += 1

    triangles = []
    degenerate = 0
    for _off, mk, _normal, counts, refs in records:
        if mk not in (0x42, 0x4A, 0x4C):
            continue
        for off, c in _loop_offsets(counts):
            loop = refs[off : off + c]
            if not loop or any(r in skips for r in loop):
                continue  # skip-ref loops: coordinates not in the region (U4)
            idxs = [elem_to_vertex[r] for r in loop]
            lp = [points[i] for i in idxs]
            if mk == 0x4C:
                for t in range(1, len(lp) - 1):
                    tri = (idxs[0], idxs[t], idxs[t + 1])
                    a, b, cc = lp[0], lp[t], lp[t + 1]
                    if a == b or b == cc or a == cc:
                        degenerate += 1
                        continue
                    triangles.append(tri)
            else:
                for t in range(len(lp) - 2):
                    tri = (idxs[t], idxs[t + 1], idxs[t + 2])
                    if t % 2 == 1:
                        tri = (tri[2], tri[1], tri[0])
                    a, b, cc = lp[t], lp[t + 1], lp[t + 2]
                    if a == b or b == cc or a == cc:
                        degenerate += 1
                        continue
                    if _cross_zero(a, b, cc):
                        degenerate += 1
                        continue
                    triangles.append(tri)

    info = {
        "stage": "walk",
        "mapping": "identity",
        "element_decl": elem_decl,
        "node_points": len(points),
        "curve_entries": len(skips),
        "write_count": winfo["write_count"],
        "table_bytes": winfo["table_len"],
        "node_bytes": node_bytes,
        "facet_candidates": candidates,
        "facet_records": len(records),
        "coplanar_loops": coplanar_loops,
        "skipref_loops": skipref_loops,
    }
    return points, triangles, degenerate, info


def decode_composite_store(data, span, groups, kinds):
    """Decode one composite store span under the recovered law.

    Stage 3d (#34): the point region decodes under the 2-bit table
    walk (U1) on BOTH forms — the stage-2c big-form rejection at this
    seam is replaced by the walk gate.  A region that walks byte-exact
    (the walk consumes exactly the declared write count, every word
    finite) decodes under the M2b identity law (refs are 0-based
    element indices in region order; :func:`_decode_identity`) — there
    is no sigma search on a walk-exact region, and no DP fallback (a
    walk-exact region re-read by the sigma CSP would be a forced
    guess).  A region that does not walk keeps a labeled
    ``undecoded-variant`` naming the walk-failure cause on big-form
    stores (the second layout family — multi-part node payloads — is
    the named residue, U3-variant); small-form stores fall back to the
    stage-2c decode (the pool-containment DP + the sigma shift-profile
    CSP, itself fail-closed) so no currently-exporting store regresses.

    Returns ``(points, triangles, degenerate, info)`` where ``points``
    is the decoded point list in region order and ``triangles`` are
    index triples into it.
    """
    lo, hi = span.body_lo, span.body_hi
    if not any(k == b"\x01\x02" or k[:1] == b"\xff" for k in kinds):
        raise ExportError(
            "undecoded-variant",
            "composite decode invoked on a store without composite markers",
        )
    poolv = [v for g in groups for v in g.vertices]
    from catpart.geometry.facets import STRIP_RE

    hdrs = [m.start() for m in STRIP_RE.finditer(data, lo, hi)]
    node_hi = hdrs[0] if hdrs else hi
    ln = find_list_node(data, lo, node_hi)
    if ln is None:
        raise ExportError(
            "undecoded-variant",
            "composite store without a token-bearing list node "
            "(N1: 939/939 composite stores carry one)",
        )
    payload, elem_decl, _edge_bound = ln
    big = len(payload) > 4096

    walk_failure: str | None = None
    elements = None
    winfo = None
    try:
        elements, winfo = walk_decode_region(payload, elem_decl)
        if not winfo["walk_ok"]:
            walk_failure = winfo["failure"]
    except ValueError as exc:
        walk_failure = str(exc)

    if elements is not None and walk_failure is None and (big or WALK_SMALL_FORM):
        records, candidates = parse_composite_facets(
            data, lo, hi, width_law="stage-3b", element_bound=elem_decl
        )
        return _decode_identity(
            elements, winfo, elem_decl, len(payload), records, candidates, poolv
        )

    if big:
        raise ExportError(
            "undecoded-variant",
            f"big-form list node ({len(payload)} B): the point region "
            f"does not walk byte-exact under the stage-3b single-table "
            f"law ({walk_failure}); the second layout family (multi-part "
            "node payloads, U3-variant) stays open — labeled, not forced",
        )
    # Small form, walk failure: the stage-2c DP path stays (its own
    # fail-closed classification below); the walk cause rides the
    # error when the fallback also fails.
    try:
        return _decode_small_form_dp(data, lo, hi, payload, elem_decl, poolv)
    except ExportError as exc:
        raise ExportError(
            exc.error_class,
            f"{exc.detail} [the stage-3b table walk does not read this "
            f"region either: {walk_failure}]",
        ) from exc


def _decode_small_form_dp(data, lo: int, hi: int, payload, elem_decl, poolv):
    """The stage-2c small-form decode (the DP probe + the sigma CSP).

    Extracted unchanged from the pre-3d ``decode_composite_store`` body
    so the walk gate can sit in front of it; every classification and
    its error detail are the shipped stage-2c ones.
    """
    candidate_parses = decode_node_points(payload, elem_decl, sorted(poolv))
    if not candidate_parses:
        raise ExportError(
            "undecoded-variant",
            "small-form point region does not decode under the refined "
            "suffix-after-LCP law (start probe + lex runs, value-DP on "
            "pool containment); no parse covering the pool",
        )
    records, candidates = parse_composite_facets(data, lo, hi)

    first_error: ExportError | None = None
    for points, stage, _end in candidate_parses:
        try:
            pool_set = set(poolv)
            if len(pool_set & set(points)) != len(pool_set):
                missing = len(pool_set) - len(pool_set & set(points))
                raise ExportError(
                    "undecoded-variant",
                    f"node list does not re-list the pool: {missing} of "
                    f"{len(pool_set)} pool vertices absent from the "
                    "decoded point region (unabsorbed variant; the merge "
                    "law's pool absorption is not established there)",
                )
            curve_count = elem_decl - len(points)
            if curve_count < 0:
                raise ExportError(
                    "undecoded-variant",
                    f"decoded {len(points)} points exceed the declared "
                    f"element count {elem_decl} (count law violated)",
                )
            sols = solve_shift_profile(points, elem_decl, records)
            if not sols:
                raise ExportError(
                    "undecoded-variant",
                    "no consistent element mapping: the facet records' "
                    "references cannot all resolve to node points with "
                    "the normal-carrying loops planar under one monotone "
                    "shift profile (M2b sigma CSP; the store's element "
                    "space disagrees with the recovered law)",
                )
            tri_sets: dict[tuple, tuple] = {}
            best_info = None
            for sol in sols[:8]:
                pos_to_idx = {p: i for i, p in sol.items()}
                tris, degen, unres = _triangulate(points, records, pos_to_idx)
                if unres:
                    raise ExportError(
                        "undecoded-variant",
                        f"{unres} facet loops reference curve-entry "
                        "positions under the shift profile (the loops "
                        "must reference node points; profile rejected)",
                    )
                sigma = sorted(sol.items())
                info = {
                    "stage": stage,
                    "element_decl": elem_decl,
                    "node_points": len(points),
                    "curve_entries": curve_count,
                    "facet_candidates": candidates,
                    "facet_records": len(records),
                    "profile_top_shift": sigma[-1][1] if sigma else 0,
                    "sigma_solutions": len(sols),
                }
                key = tuple(sorted(tris))
                if key not in tri_sets:
                    tri_sets[key] = (tris, degen, info)
                if best_info is None:
                    best_info = info
            if len(tri_sets) > 1:
                raise ExportError(
                    "undecoded-variant",
                    f"ambiguous element mapping: {len(tri_sets)} distinct "
                    f"meshes over {len(sols)} consistent shift profiles — "
                    "the unreferenced positions' node/curve choices are "
                    "not pinned by the facet law (fail-closed)",
                )
            tris, degen, info = next(iter(tri_sets.values()))
            return points, tris, degen, info
        except ExportError as exc:
            if first_error is None:
                first_error = exc
    raise first_error


def _cross_zero(a, b, c):
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    cross = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    return cross == (0.0, 0.0, 0.0)
