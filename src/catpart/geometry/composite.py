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
- Record width (stage-3b rule, extended 2026-11-11 stage 4b,
  integrated 2026-11-12 stage 5): per-record u8/u16be/u24be chosen by
  end-alignment onto the next header, ranked exact tiling first, then
  **no-repeated-refs-within-a-loop** (a u8 misread of a u16be record
  repeats refs inside the loop), then no out-of-range refs, then the
  **loop plane law** (a candidate whose normal-carrying loops are
  non-coplanar against the record's stored normal loses to one that is
  coplanar — the narrow-width tiebreak over interleaved non-STRIP_RE
  families, where u8 and u16be tie on tiling/repeats/oob and the
  committed rule picked the narrower misread), then the narrower
  width.  u24be enters for element counts above 65,535 (a 2-byte ref
  cannot index them; 13bb5c0c: element_count 236,385, records tile
  exactly at u24be, byte-verified — docs/evidence/
  2026-11-11-per-rep-and-width-laws.md R10/R11).  The plane law is a
  tiebreak inside the width rank, not an export gate (the multi-plane
  fillet/bevel strips stay legitimate geometry, stage-3d decision).

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


def parse_strip_records(data, lo: int, hi: int, element_count: int, elements=None):
    """Every strip record with the width disambiguated (stage-3b rule,
    extended 2026-11-11 stage 4b: u24be candidate + the loop plane
    tiebreak; integrated 2026-11-12 stage 5, #34).

    Candidate parses: width u8/u16be (plus u24be ONLY when
    ``element_count > 65,535`` — a 2-byte ref cannot index such an
    element space, and on smaller spaces a 3-byte candidate can only
    read junk past them: measured on the corpus A/B, 4 exported stores
    flip to OOB junk when u24be is offered below the threshold) x
    count-byte k (0..16) summing to n, ending at or before the next
    header.  Rank: exact tiling, then no-repeated-refs-within-a-loop,
    then no out-of-range refs, then **non-coplanar normal-carrying
    loops** (only computed when ``elements`` — the decoded element
    space the refs index — is passed; a candidate whose loops are
    non-coplanar against the record's stored normal loses to one that
    is coplanar; without ``elements`` the rank is the committed
    stage-3b one), then the narrower width.  Returns ``(records,
    n_headers)`` where each record is ``(offset, marker, normal,
    counts, refs, width)``.
    """
    hdrs = [m.start() for m in STRIP_RE.finditer(data, lo, hi)]
    widths = (1, 2, 3) if element_count > 65_535 else (1, 2)
    skips = (
        {i for i, (_v, pt) in enumerate(elements) if pt is None}
        if elements is not None
        else None
    )
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
        for width in widths:
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
                nonplanar = 0
                if normal is not None and elements is not None:
                    off = 0
                    for c in counts:
                        loop = refs[off : off + c]
                        off += c
                        if not loop:
                            continue
                        if any(
                            r in skips or r >= len(elements) for r in loop
                        ):
                            continue
                        st, _res = _loop_plane_status(loop, normal, elements)
                        if st == "nonplanar":
                            nonplanar += 1
                rank = (
                    0 if end == nxt else 1,
                    1 if repeats else 0,
                    1 if oob else 0,
                    nonplanar,
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


# Plane tolerance of the committed loop battery (stage 3b): the
# per-coordinate normal distance bound; f32 coordinate rounding ~1e-4.
PLANE_TOL = 2e-3


def _loop_plane_status(loop, normal, elements):
    """Coplanarity of one fully-resolved loop against the record's
    stored normal (the stage-3b battery criterion; ported from the
    stage-4b width re-test, ``not_manifold_audit.py``).  Returns
    ``("coplanar", 0.0)`` or ``("nonplanar", max_distance)``."""
    nn = (normal[0] ** 2 + normal[1] ** 2 + normal[2] ** 2) ** 0.5
    if nn == 0:
        return "nonplanar", 0.0
    pts = [elements[r][1] for r in loop]
    p0 = pts[0]
    worst = 0.0
    for p in pts[1:]:
        d = (
            (p[0] - p0[0]) * normal[0]
            + (p[1] - p0[1]) * normal[1]
            + (p[2] - p0[2]) * normal[2]
        ) / nn
        if abs(d) > worst:
            worst = abs(d)
        if abs(d) > PLANE_TOL:
            return "nonplanar", abs(d)
    return "coplanar", worst


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
    """Decode one composite store span under the identity law (stage 3d;
    per-rep decomposition added 2026-11-12 stage 5, #34).

    Returns ``(points, triangles, degenerate, info)`` where ``points``
    is the written point list in region order (the exported vertices)
    and ``triangles`` are index triples into it.  Raises
    :class:`ExportError` (``undecoded-variant``) with the specific gap
    when the law does not cover the store: no token-bearing list node
    (N1), a layout that does not fit the P1t law, a walk-exact failure
    (the U3-variant second layout family), non-finite coordinates, an
    unabsorbed pool with no per-rep reading either, facet references
    beyond the element space, or no exportable facet records' families
    at all.

    Stage-5 per-rep decomposition (stage-4b law, 2026-11-11): when the
    single-rep reading fails the pool-absorption gate, the store body
    may be a SEQUENCE of reps — rep k = (the k-th ``01 06`` pool
    wrapper, the k-th walk-exact token-bearing list node, the strip
    records in that node's territory) — and the k-th pool re-lists
    verbatim (f32-exact, or within :data:`NOISE_REL` relative — the
    measured double-rounding noise) in the k-th rep's region.  The
    stage-3d "unabsorbed" family is the single-rep reading applied to
    multi-rep stores (docs/evidence/2026-11-11-per-rep-and-width-laws.md
    R1-R5).  Per rep: absorption, the M2b identity refs gate against
    the REP's element count, and triangulation of the rep's territory
    records; merged meshes concatenate the exported reps' written
    points (disjoint element spaces, so triangle indices offset per
    rep).  Fail-closed per rep: a rep whose pool does not absorb, or
    whose gated references leave its own element space, stays
    unexported with the reason named in ``info`` — no guessing.
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
        # Stage-5 per-rep decomposition (stage-4b law): try the
        # sequence-of-reps reading before failing closed.
        return _decode_per_rep(data, lo, hi, groups, len(missing), len(pool_set))

    records, n_hdrs = parse_strip_records(
        data, lo, hi, elem_decl, elements=elements
    )
    # Refs are 0-based element indices: every gated family's references
    # must resolve inside the element space (the exported markers plus
    # the normal-carrying 0x49, the stage-2c gate set).
    all_refs = [r for _o, mk, _n, _c, refs, _w in records if mk in GATED for r in refs]
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
        # stage-5 fold-in (reconciliation note section 5): the list
        # node's payload byte length — lets big/small form be derived
        # from summaries/CSVs (big > 4096 B).
        "node_bytes": len(payload),
        **loop_stats,
    }
    return points, triangles, degenerate, info


# The gated families whose references must resolve in-bounds (the
# exported markers plus the normal-carrying 0x49, the stage-2c gate set).
GATED = (0x42, 0x49, 0x4A, 0x4C)

# Noise-aware absorption tolerance (stage-4b R3): a pool vertex
# "re-listed with noise" matches a written point within NOISE_REL
# relative, per coordinate, scaled by max(1, |coord|).  Measured noise
# <= 1.25e-08 relative; the smallest genuinely-different coordinate
# pair measured is 4 decades above it.
NOISE_REL = 1e-5


def _tol_match(v, pts):
    """Noise-aware re-listing test: some written point matches ``v``
    within :data:`NOISE_REL` per coordinate.  Returns the best
    (smallest) relative delta, or ``None`` when ``pts`` is empty."""
    scale = max(1.0, abs(v[0]), abs(v[1]), abs(v[2]))
    best = None
    for p in pts:
        d = max(
            abs(p[0] - v[0]) / scale,
            abs(p[1] - v[1]) / scale,
            abs(p[2] - v[2]) / scale,
        )
        if best is None or d < best:
            best = d
    return best


def _scan_token_nodes(data, lo: int, hi: int):
    """Every token-bearing list node in [lo, hi) (stage-4b scan).

    Returns ``(pos, payload, element_count, edge_bound)`` per node in
    body order — unlike :func:`find_list_node` (largest payload BEFORE
    the first strip header — the stage-3d single-rep window), this
    scans the whole body: on multi-rep stores the k-th rep's node sits
    after the previous rep's records.
    """
    nodes = []
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
            try:
                c1, p = read_count(payload, p)
                c2, p = read_count(payload, p)
            except (IndexError, struct.error):
                pos += 1
                continue  # unreadable counts: not a node
            if 0 < c1 <= MAX_ELEMENT_COUNT:
                nodes.append((pos, payload, c1, c2))
        pos += 1
    return nodes


def _decode_per_rep(data, lo, hi, groups, n_missing, n_pool):
    """The sequence-of-reps reading (stage-4b per-rep law, stage-5
    integration).  Rep k = (pool group k, the k-th walk-exact token
    node, that node's record territory ``[region_end_k, node_{k+1})``);
    the k-th pool re-lists verbatim (or within :data:`NOISE_REL`) in
    the k-th rep's region.  A rep exports only when its pool absorbs
    and its gated references resolve in-bounds against its OWN element
    count; failing reps stay unexported with the reason named.  When
    no rep exports, raises the stage-3d ``unabsorbed`` classification
    with the per-rep residue named (fail-closed, no guessing)."""
    decoded = []
    for npos, payload, c1, _c2 in _scan_token_nodes(data, lo, hi):
        try:
            elements, info = decode_region(payload, c1)
        except ExportError:
            continue  # walk-exact failure: the rep has no decoded region
        decoded.append(
            {
                "pos": npos,
                "payload": payload,
                "elem": c1,
                "elements": elements,
                "pts": [pt for _v, pt in elements if pt is not None],
                # absolute end of the point region (the territory start)
                "region_end": npos + 4 + info["walk_end"],
                "write_count": info["write_count"],
                "table_bytes": info["table_bytes"],
            }
        )
    if not decoded:
        raise ExportError(
            "undecoded-variant",
            f"node list does not re-list the pool: {n_missing} of "
            f"{n_pool} pool vertices absent from the decoded point "
            "region (unabsorbed variant; the per-rep decomposition "
            "finds no walk-exact rep region either)",
        )
    points: list = []
    triangles: list = []
    degenerate = 0
    loop_stats = {"loops_exported": 0, "loops_curve_entry": 0}
    skipped_markers: dict[int, int] = {}
    facet_candidates = 0
    facet_records = 0
    write_count = 0
    table_bytes = 0
    element_decl = 0
    curve_entries = 0
    node_bytes = 0
    reps_unexported = []
    for k, d in enumerate(decoded):
        node_bytes += len(d["payload"])
        gv = groups[k].vertices if k < len(groups) else ()
        distinct = set(gv)
        pts_set = set(d["pts"])
        unmatched = [v for v in distinct if v not in pts_set]
        if unmatched:
            # noise-aware absorption (stage-4b R3): the verbatim misses
            # may be double-rounding re-listings
            unmatched = [
                v
                for v in unmatched
                if (best := _tol_match(v, d["pts"])) is None
                or best > NOISE_REL
            ]
        if unmatched:
            reps_unexported.append(
                f"rep {k}: pool group {k} not re-listed "
                f"({len(unmatched)} of {len(distinct)} vertices absent "
                "from the rep's region; per-rep absorption not "
                "established)"
            )
            continue
        nxt = decoded[k + 1]["pos"] if k + 1 < len(decoded) else hi
        records, n_hdrs = parse_strip_records(
            data, d["region_end"], nxt, d["elem"], elements=d["elements"]
        )
        grefs = [
            r for _o, mk, _n, _c, refs, _w in records if mk in GATED for r in refs
        ]
        if grefs and max(grefs) >= d["elem"]:
            mx = max(grefs)
            reps_unexported.append(
                f"rep {k}: facet references beyond the rep's element "
                f"space (max ref {mx} >= element count {d['elem']}, "
                "M2b identity per rep)"
            )
            continue
        base = len(points)
        tri_k, deg_k, stats_k = _triangulate(d["elements"], records)
        points += d["pts"]
        triangles += [(a + base, b + base, c + base) for a, b, c in tri_k]
        degenerate += deg_k
        loop_stats["loops_exported"] += stats_k["loops_exported"]
        loop_stats["loops_curve_entry"] += stats_k["loops_curve_entry"]
        facet_candidates += n_hdrs
        facet_records += len(records)
        write_count += d["write_count"]
        table_bytes += d["table_bytes"]
        element_decl += d["elem"]
        curve_entries += len(d["elements"]) - len(d["pts"])
        for _o, mk, _n, _c, _refs, _w in records:
            if mk not in (0x42, 0x4A, 0x4C):
                skipped_markers[mk] = skipped_markers.get(mk, 0) + 1
    if not points:
        raise ExportError(
            "undecoded-variant",
            f"node list does not re-list the pool: {n_missing} of "
            f"{n_pool} pool vertices absent from the decoded point "
            "region (unabsorbed variant; the per-rep decomposition "
            f"exports no rep: {'; '.join(reps_unexported) or 'no reps'})",
        )
    info = {
        "stage": "identity-per-rep",
        "element_decl": element_decl,
        "node_points": len(points),
        "curve_entries": curve_entries,
        "write_count": write_count,
        "table_bytes": table_bytes,
        "facet_candidates": facet_candidates,
        "facet_records": facet_records,
        "skipped_markers": skipped_markers,
        "node_bytes": node_bytes,
        "reps_decoded": len(decoded),
        "reps_exported": len(decoded) - len(reps_unexported),
        "reps_unexported": len(reps_unexported),
        "rep_reasons": reps_unexported,
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
