"""The composite index space decoded under the recovered law (G6, #34 stage 2c).

Integrates the stage-2b decode of the scene-graph list nodes' point
streams into the exporter (docs/evidence/2026-11-10-node-streams.md;
stage-2c refinements dated 2026-11-11, byte-measured on the corpus):

- Layout (P1, refined): the list node's payload = header + token
  ``ff ff 02 00 01`` + the declared counts (element_count,
  edge_ref_bound, P1g) + a zero block + a 2-bit per-element table of
  ``ceil(element_count / 4) + 1`` bytes (U1, length measured: 32 B for
  124 declared on 026d6726, 41 B for 160 on 0313b53d) + **the point
  region** + a trailing region (semantics open, U2).
- Point stream (P1, refined): a suffix-after-LCP coded point list
  (f32le) whose initial LCP state carries **x = 0.0 implicitly** — the
  first point is written ``[x][y][z]`` only when its x differs from 0,
  else ``[y][z]`` (0313b53d: the region opens with the pool lex-min's
  ``[y][z]``; 026d6726: a full write, x != 0 — one law, both forms).
  The stream is a concatenation of **lex-nondecreasing runs**; each run
  starts with a full ``[x][y][z]`` write and may reset x (1b1e69cd: run
  A covers x 98980.95..99032.89, run B restarts at x 98873.89 — the
  stream is not globally lex-sorted; the merge law's global sort is).
- Element space (M2b): the lex-sorted merge of the pool vertices and
  the node's decoded points (plus the curve-record points, values open
  U4); facet and edge references are 0-based positions in that
  sequence.  On every store the law decodes, the node list re-lists the
  pool verbatim (pool absorbed), so the decoded points carry the
  merge's known coordinates; the curve entries surface only as the
  monotone shift of the loop mapping (their count is pinned:
  element_count minus node points).
- Loop mapping law (M2b, the validator): a facet loop's distinct refs
  map order-preservingly onto an ascending run of decoded points
  sharing one constant coordinate (the plane named by the record
  normal's dominant axis, or any axis when the record carries no
  normal), with a monotone non-negative shift (the curve entries
  inserted before each plane point).  The shift profile is built
  incrementally across the store's records and must stay consistent
  (one monotone profile).  A store exports only when every
  exported-family record decodes under this law; anything else keeps
  its ``undecoded-variant`` classification with the specific reason
  (fail-closed, no guessing).

The decode is deterministic: a value-DP over (position, last-point)
states maximises pool containment (then the point count) with a fixed
branch order; ties resolve to the first parent in that order.  Big-form
stores stay undecoded (U3 segment bookkeeping open); unabsorbed pools
(node list missing pool vertices) stay undecoded with the gap named.
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

_F32 = struct.Struct("<f")

WARN_COMPOSITE = "composite-law-decode"


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


def parse_composite_facets(data, body_lo: int, body_hi: int):
    """Parse the facet records of a composite store body (counts law).

    Composite records carry up to ``MAX_LOOP_COUNTS`` count bytes
    summing to n (the clean-store grammar's k <= 4 does not hold here —
    026d6726's ``01 4a`` record carries 7); the reference width is
    per-record u8/u16be chosen by end-alignment onto the next header
    (or the body end), the exact-tiling parse winning, then the
    narrower width (the composite gap behavior the stage-2b validator
    used; the clean-store width-vote context does not apply here).
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
                rank = (0, width) if end == nxt else (1, 0 if width == 1 else 1)
                if best is None or rank < best[0]:
                    refs = [
                        int.from_bytes(
                            data[base + k + width * j : base + k + width * (j + 1)],
                            "big",
                        )
                        for j in range(n)
                    ]
                    best = (rank, counts, refs, end)
        if best is None:
            continue
        _rank, counts, refs, _end = best
        records.append((o, mk, normal, tuple(counts), tuple(refs)))
    return records, len(hdrs)


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


def decode_composite_store(data, span, groups, kinds):
    """Decode one composite store span under the recovered law.

    Returns ``(points, triangles, degenerate, info)`` where ``points``
    is the decoded node point list (the merged space's known
    coordinates; the pool is re-listed verbatim on every store the law
    decodes) and ``triangles`` are index triples into it.  Raises
    :class:`ExportError` (``undecoded-variant``) with the specific gap
    when the law does not cover the store: a big-form node (U3), a
    point region that does not decode, an unabsorbed pool, a count-law
    violation, a store with no consistent shift profile, or an
    ambiguous one (several profiles with distinct meshes — the
    unreferenced positions' node/curve choices are not pinned by the
    facet law there).
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
    if len(payload) > 4096:
        raise ExportError(
            "undecoded-variant",
            f"big-form list node ({len(payload)} B): the point region is "
            "segmented and the segment bookkeeping is open (U3); labeled, "
            "not forced",
        )
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
