"""The composite index space decoded under the recovered identity law (G6, #34).

Integrates the stage-3b/3d decode of the scene-graph list nodes' point
regions into the exporter (docs/evidence/2026-11-10-node-streams.md;
stage-3b table law dated 2026-11-11, byte-measured on the corpus):

- Layout (P1t, corrected 2026-11-11 stage 3b): the list node's payload
  = header + token ``ff ff 02 00 01`` + the declared counts
  (element_count, edge_ref_bound, P1g) + a zero block + **the 2-bit
  per-element table of exactly ``ceil(element_count / 4)`` bytes** + a
  **P1g count of the region's f32 words** (1 B, ``ff`` escapes to
  u32le) + **the point region** (count x f32) + a trailing region
  (semantics open, U2).  The stage-2c ``+1 byte`` table span was the
  count byte miscounted into the table.
- Table semantics (U1, solved 2026-11-11 stage 3b): 2 bits per
  element, LSB-first within each byte, one slot per element in region
  order; the value is the element's write shape in f32 words:
  **0 = ``[x][y][z]``** (3 words, an x-write/run start), **1 = skip**
  (0 words — the curve entries: no coordinates in the region, U4),
  **2 = ``[z]``** (1 word), **3 = ``[y][z]``** (2 words).  The initial
  LCP state is the origin (P1i subsumed: the first write's shape comes
  from the table like every other element's).  The walk is
  deterministic — no DP, no probe — and consumes exactly the declared
  write count on every store the law decodes.
- Segments (U3, resolved for the single-table family): there are no
  per-segment tables and no segment headers — ONE table + ONE write
  count cover the whole region; value-0 slots delimit the x-groups,
  and corner groups sit out of x order at their element slots.  One
  table covers both forms (small and big differ only in size).
- Element space (M2b, refined 2026-11-11 stage 3b): facet and edge
  references are **0-based element indices in region order — the
  identity**.  The element space IS the region's element sequence
  (written points + skip slots); there is no sigma search.

  REVISED 2026-11-11 (stage 3d, #34): the stage-2c sigma solver
  (:func:`solve_shift_profile`, the monotone shift-profile CSP) and its
  ambiguity path are REMOVED.  The stage-3b corpus decode established
  the identity reading directly (elem_decl == max_ref + 1 on the
  ref-carrying decoded family; every normal-carrying loop's refs
  resolve to points sharing the loop's plane), so the shift profiles
  were artifacts of matching refs onto WRITTEN-point indices — the
  shift equalled the skip slots before each point and was
  automatically monotone.  Curve entries ARE referenced by loops (the
  stage-2c "never referenced" inference is corrected in the claims
  ledger); a loop referencing a skip slot cannot triangulate exactly
  (U4: the entry's coordinates live in the curve records, open), so
  the exporter skips exactly those loops and names the gap — the rest
  of the store exports.
- Loop plane law: coplanarity against the record's stored 12-B normal
  (the corner quads are slanted planes; the axis-constant reading was
  too strict).  It is the law's validation battery, not an export
  gate: multi-plane fillet/bevel strips are legitimate geometry where
  whole-loop coplanarity does not apply (stage-3b loop battery:
  coplanar + skip-ref + multi-plane = 98.3% of testable loops).
- Record width (stage-3b rule): per-record u8/u16be chosen by
  end-alignment onto the next header, ranked exact tiling first, then
  **no-repeated-refs-within-a-loop** (a u8 misread of a u16be record
  repeats refs inside the loop), then no out-of-range refs, then the
  narrower width.

Fail-closed ladder (refined 2026-11-11 stage 3d, not abandoned): a
store exports only when its table walk is exact (layout fits, the walk
consumes exactly the declared write count, every coordinate finite and
plausible), the pool is re-listed verbatim in the decoded points
(absorbed), and the exported-family references resolve in-bounds.
Stores outside the law keep the ``undecoded-variant`` classification
with the specific gap named: a layout that does not fit, a walk-exact
failure (the U3-variant second layout family, ~14% of big-form
stores), non-finite coordinates, an unabsorbed pool, references
beyond the element space, or a store without a token-bearing list
node.  There is no guessing.
"""

from __future__ import annotations

import struct

from catpart.geometry.errors import ExportError
from catpart.geometry.facets import NORMAL_MARKERS_ALL, STRIP_RE

NODE_MAGIC = b"\x04\x04\xfd\xff"
LIST_TOKEN = b"\xff\xff\x02\x00\x01"

MAX_ELEMENT_COUNT = 10_000_000
MAX_TABLE_BYTES = 1 << 20
MAX_LOOP_COUNTS = 16

_F32 = struct.Struct("<f")

# Table value -> f32 words written (0 = skip: the element carries no
# coordinates in the region — the curve entries, U4).
SHAPES = {0: 3, 1: 0, 2: 1, 3: 2}


def _f32(data, pos: int) -> float:
    return _F32.unpack_from(data, pos)[0]


def _nice(v: float) -> bool:
    """Finite coordinate check (the stage-3b walk's predicate).

    The table-driven walk needs no pruning predicate (the table fixes
    the parse), so the stage-2c probe's 1e-6 floor is dropped (dated
    2026-11-11): real tessellation coordinates reach ~1e-15 around
    zero, and junk detection falls to the walk-exact / pool / in-bounds
    checks."""
    return v == v and abs(v) < 1e9


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
    region — the largest payload (the stage-2b census; the stage-3b
    residue notes that on the U3-variant family this payload is a
    multi-part container — those stores fail the walk below, named).
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


def layout(payload: bytes, element_count: int):
    """Region layout after the zero block (P1t corrected, stage 3b).

    The 2-bit table spans exactly ``ceil(element_count / 4)`` bytes
    after the zero block, then the P1g write count, then the region.

    Returns ``(table_start, table_len, count_pos, region_start,
    write_count)``; raises :class:`ExportError` (``undecoded-variant``)
    when the layout does not fit the payload.
    """
    tok = payload.find(LIST_TOKEN)
    if tok < 0:
        raise ExportError("undecoded-variant", "list node payload without the list token")
    p = tok + 5
    _, p = read_count(payload, p)
    _, p = read_count(payload, p)
    while p + 4 <= len(payload) and payload[p : p + 4] == b"\x00\x00\x00\x00":
        p += 4
    table_len = (element_count + 3) // 4
    if table_len > MAX_TABLE_BYTES:
        raise ExportError(
            "undecoded-variant",
            f"declared element count {element_count} implies a "
            f"{table_len} B table, above the {MAX_TABLE_BYTES} B sanity cap",
        )
    count_pos = p + table_len
    if count_pos >= len(payload):
        raise ExportError(
            "undecoded-variant",
            f"the {table_len} B 2-bit table runs past the payload "
            f"(count position {count_pos} >= payload length {len(payload)}); "
            "the store's layout does not fit the P1t law",
        )
    write_count, region_start = read_count(payload, count_pos)
    region_end = region_start + 4 * write_count
    if region_end > len(payload):
        raise ExportError(
            "undecoded-variant",
            f"declared write count {write_count} overruns the payload "
            f"(region end {region_end} > {len(payload)})",
        )
    return p, table_len, count_pos, region_start, write_count


def table_slots(payload: bytes, table_start: int, table_len: int, element_count: int):
    """The 2-bit table: LSB-first slots, one per element."""
    slots = []
    for i in range(table_start, table_start + table_len):
        b = payload[i]
        slots += [(b >> 0) & 3, (b >> 2) & 3, (b >> 4) & 3, (b >> 6) & 3]
    return slots[:element_count]


def decode_region(payload: bytes, element_count: int):
    """Deterministic table-driven decode of the point region (U1, stage 3b).

    Returns ``(elements, info)`` where ``elements[i] = (slot_value,
    point_or_None)`` in region order (the point is ``None`` for skip
    slots — the curve entries) and ``info`` carries the layout.  The
    walk is bounded by the declared region: a slot needing words past
    ``region_start + 4 * write_count``, a walk ending short of it, or a
    non-finite/implausible coordinate each raise :class:`ExportError`
    (``undecoded-variant``) with the specific gap — the walk-exact
    failures are the U3-variant second layout family's signature.
    """
    table_start, table_len, count_pos, region_start, write_count = layout(
        payload, element_count
    )
    if write_count > 3 * element_count:
        raise ExportError(
            "undecoded-variant",
            f"declared write count {write_count} exceeds the table's word "
            f"budget (3 x {element_count} elements): the region does not "
            "decode under the table law",
        )
    slots = table_slots(payload, table_start, table_len, element_count)
    region_end = region_start + 4 * write_count
    pos = region_start
    x = y = z = 0.0  # the initial LCP state is the origin (P1i subsumed)
    elements = []
    for i, v in enumerate(slots):
        shape = SHAPES[v]
        if shape == 0:
            elements.append((v, None))
            continue
        if pos + 4 * shape > region_end:
            raise ExportError(
                "undecoded-variant",
                f"table walk exceeds the declared region at element {i} "
                f"(shape {v} needs {shape} f32 words, {region_end - pos} left "
                f"of the declared {write_count}): walk-exact failure — the "
                "store's layout family does not decode under the stage-3b "
                "table law (U3-variant residue)",
            )
        if shape == 3:
            x, y, z = _f32(payload, pos), _f32(payload, pos + 4), _f32(payload, pos + 8)
            vals = (x, y, z)
        elif shape == 2:
            y, z = _f32(payload, pos), _f32(payload, pos + 4)
            vals = (y, z)
        else:
            z = _f32(payload, pos)
            vals = (z,)
        if not all(_nice(c) for c in vals):
            raise ExportError(
                "undecoded-variant",
                f"non-finite or implausible coordinate at element {i} "
                f"(write shape {v}): {vals!r}",
            )
        pos += 4 * shape
        elements.append((v, (x, y, z)))
    if pos != region_end:
        raise ExportError(
            "undecoded-variant",
            f"table walk consumed {pos - region_start} of the declared "
            f"{4 * write_count} region words (write count {write_count}): "
            "walk-exact failure — the store's layout family does not decode "
            "under the stage-3b table law (U3-variant residue)",
        )
    info = {
        "table_bytes": table_len,
        "write_count": write_count,
        "region_bytes": 4 * write_count,
        "walk_end": pos,
    }
    return elements, info


def decode_node_points(payload: bytes, element_count: int):
    """Decode the list node's point region (both forms, identity law).

    Returns ``(points, skip_count, info)``: ``points`` is the written
    point list in region order (the skip slots — the curve entries —
    carry no coordinates, U4), ``skip_count`` the number of skip slots,
    ``info`` the layout block from :func:`decode_region`.  Raises
    :class:`ExportError` (``undecoded-variant``) when the layout does
    not fit or the walk is not exact.
    """
    elements, info = decode_region(payload, element_count)
    points = [pt for _v, pt in elements if pt is not None]
    return points, len(elements) - len(points), info


def parse_strip_records(data, lo: int, hi: int, element_count: int):
    """Every strip record with the width disambiguated (stage-3b rule).

    Candidate parses: width u8/u16be x count-byte k (0..16) summing to
    n, ending at or before the next header.  Rank: exact tiling, then
    no-repeated-refs-within-a-loop, then no out-of-range refs, then the
    narrower width (the tiling law first; the no-repeat rule resolves
    the u8-misread of u16be records whose next header is not adjacent —
    stage-3b, 2026-11-11).  Returns ``(records, n_headers)`` where each
    record is ``(offset, marker, normal, counts, refs, width)``.
    """
    hdrs = [m.start() for m in STRIP_RE.finditer(data, lo, hi)]
    out = []
    for i, o in enumerate(hdrs):
        nxt = hdrs[i + 1] if i + 1 < len(hdrs) else hi
        mk = data[o + 1]
        hlen = 4 if data[o + 3] == 0xFF else 5
        if o + hlen + 4 > nxt:
            continue
        n = int.from_bytes(data[o + hlen : o + hlen + 4], "little")
        if not (0 <= n <= 1_000_000):
            continue
        has_normal = mk in NORMAL_MARKERS_ALL
        base = o + hlen + 4 + (12 if has_normal else 0)
        normal = None
        if has_normal:
            if base > hi:
                continue
            normal = struct.unpack("<fff", data[o + hlen + 4 : o + hlen + 16])
        best = None
        for width in (1, 2):
            for k in range(0, MAX_LOOP_COUNTS + 1):
                if base + k > nxt:
                    break
                counts = [data[base + j] for j in range(k)]
                if sum(counts) != n:
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
                repeats = False
                off = 0
                for c in counts:
                    loop = refs[off : off + c]
                    if c > 0 and len(set(loop)) < c:
                        repeats = True
                    off += c
                oob = any(r >= element_count for r in refs)
                rank = (
                    0 if end == nxt else 1,
                    1 if repeats else 0,
                    1 if oob else 0,
                    width,
                    k,
                )
                if best is None or rank < best[0]:
                    best = (rank, tuple(counts), tuple(refs), width)
        if best is None:
            continue
        _rank, counts, refs, width = best
        out.append((o, mk, normal, counts, refs, width))
    return out, len(hdrs)


def _triangulate(elements, records):
    """Triangles under the identity mapping (strip/polygon semantics).

    Loop references are 0-based element indices; triangles index the
    WRITTEN points (the exported vertex list), so referenced elements
    are remapped through the written rank.  Loops referencing skip
    slots (curve entries — their coordinates live in the curve records,
    U4, open) are skipped and counted: the exporter names the gap
    instead of guessing coordinates.  Strip triangles (0x42/0x4a) skip
    the degenerate ones (repeated coordinates or exactly-zero cross
    product, G3 F7); polygon fans (0x4c) skip repeated coordinates.

    Returns ``(triangles, degenerate, stats)`` where ``stats`` carries
    the loop counters for the summary's composite block.
    """
    written_rank: dict[int, int] = {}
    skips: set[int] = set()
    for i, (_v, pt) in enumerate(elements):
        if pt is None:
            skips.add(i)
        else:
            written_rank[i] = len(written_rank)
    points = [pt for _v, pt in elements if pt is not None]

    triangles = []
    degenerate = 0
    loops_exported = 0
    loops_curve_entry = 0
    for _off, mk, _normal, counts, refs, _w in records:
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
            if any(r in skips for r in loop):
                loops_curve_entry += 1
                continue
            loops_exported += 1
            idxs = [written_rank[r] for r in loop]
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
    stats = {
        "loops_exported": loops_exported,
        "loops_curve_entry": loops_curve_entry,
    }
    return triangles, degenerate, stats


def decode_composite_store(data, span, groups, kinds):
    """Decode one composite store span under the identity law (stage 3d).

    Returns ``(points, triangles, degenerate, info)`` where ``points``
    is the written point list in region order (the exported vertices)
    and ``triangles`` are index triples into it.  Raises
    :class:`ExportError` (``undecoded-variant``) with the specific gap
    when the law does not cover the store: no token-bearing list node
    (N1), a layout that does not fit the P1t law, a walk-exact failure
    (the U3-variant second layout family), non-finite coordinates, an
    unabsorbed pool (the node list missing pool vertices), facet
    references beyond the element space, or no exportable facet
    records' families at all.
    """
    lo, hi = span.body_lo, span.body_hi
    if not any(k == b"\x01\x02" or k[:1] == b"\xff" for k in kinds):
        raise ExportError(
            "undecoded-variant",
            "composite decode invoked on a store without composite markers",
        )
    poolv = [v for g in groups for v in g.vertices]
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
    elements, region_info = decode_region(payload, elem_decl)
    points = [pt for _v, pt in elements if pt is not None]
    skip_slots = len(elements) - len(points)

    pool_set = set(poolv)
    missing = pool_set - set(points)
    if missing:
        raise ExportError(
            "undecoded-variant",
            f"node list does not re-list the pool: {len(missing)} of "
            f"{len(pool_set)} pool vertices absent from the decoded "
            "point region (unabsorbed variant; the merge law's pool "
            "absorption is not established there)",
        )

    records, n_hdrs = parse_strip_records(data, lo, hi, elem_decl)
    # Refs are 0-based element indices: every gated family's references
    # must resolve inside the element space (the exported markers plus
    # the normal-carrying 0x49, the stage-2c gate set).
    gated = (0x42, 0x49, 0x4A, 0x4C)
    all_refs = [r for _o, mk, _n, _c, refs, _w in records if mk in gated for r in refs]
    if all_refs:
        mx = max(all_refs)
        if mx >= elem_decl:
            raise ExportError(
                "undecoded-variant",
                f"facet references beyond the element space: max ref {mx} "
                f">= element count {elem_decl} (refs are 0-based element "
                "indices in region order, M2b identity; G3 open question 2)",
            )

    triangles, degenerate, loop_stats = _triangulate(elements, records)

    skipped_markers: dict[int, int] = {}
    for _o, mk, _n, _c, _refs, _w in records:
        if mk not in (0x42, 0x4A, 0x4C):
            skipped_markers[mk] = skipped_markers.get(mk, 0) + 1

    info = {
        "stage": "identity-table-walk",
        "element_decl": elem_decl,
        "node_points": len(points),
        "curve_entries": skip_slots,
        "write_count": region_info["write_count"],
        "table_bytes": region_info["table_bytes"],
        "facet_candidates": n_hdrs,
        "facet_records": len(records),
        "skipped_markers": skipped_markers,
        **loop_stats,
    }
    return points, triangles, degenerate, info


def _cross_zero(a, b, c):
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    cross = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    return cross == (0.0, 0.0, 0.0)
