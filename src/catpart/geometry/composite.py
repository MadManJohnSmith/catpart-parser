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

  Stage-10 E0-b dup-pin law (2026-11-12, #34; the landed analysis's
  RESTRICTED recommendation — docs/evidence/
  2026-11-12-curve-entry-analysis.md section 5, claims row
  ``U4-stage5-recommendation``, + the stage-9-baseline recompute
  addendum): on a store whose primary triangulation is EMPTY (the
  census's ``empty-mesh`` class — E0 by construction: it can only move
  fail -> pass, no L2 pass can regress) and when EVERY dropped loop is
  battery-supported — its record carries a 12-B normal and the loop is
  coplanar against that normal with the dup-pinned coordinates (the
  U4-D dup law, ported from the stage-4a decoder's ``dup_prev``, not
  re-derived: a loop-referenced skip slot welds to the written vertex
  of its immediately preceding written element, no new vertices) —
  those loops export (``e0b-dup-pin``).  One normal-less (untestable)
  or nonplanar dropped loop keeps the WHOLE store on the conservative
  non-export rule with its warning (the analysis's E0-b criterion:
  battery coverage full AND zero nonplanar).  The live law predicate
  selects exactly the battery-supported subset E0-b of the analysis
  (2fca9bc4 / 4ad53b87 / 4ae0392d / 505bbe1f at the stage-9 baseline;
  21 of the other 22 E0 members carry a normal-less dropped loop, and
  3dff4d93's two dropped loops are normal-carrying with one nonplanar
  (review F3 correction, 2026-11-13 — measured, stage-10 note).  The U4-M mid
  law stays DEMOTED to unsupported and is NOT implemented; the battery
  discriminates dup from next/mid wherever a loop references a slot
  (twin probe), and a ``mid`` slot is by construction referenced by no
  facet loop, so it enters no triangle either way.
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

- Raw-array law (stage 4a-residue, integrated 2026-11-12 stage 6, #34):
  a walk-mismatch composite payload continues past the header as RAW
  f32 triples — ``[token][count1][count2][tail][elem_decl x [x][y][z]
  stride 12, x ascending][FF][count3 u32le][trail]``
  (docs/evidence/2026-11-10-node-streams.md section "Stage 4a-residue";
  rates in residue-raw-scan.csv).  The start is pinned by the
  **trail-escape condition** ``payload[start + 12*elem_decl] == 0xFF``
  over the committed scan's 4-aligned candidate range 32..64 — the
  law applies only when exactly one candidate satisfies it.  Strong
  fit = nice >= 0.98 AND x-ascending >= 0.98 over the full elem_decl
  span (the committed scan criteria, ported verbatim including the
  scan's coordinate predicate) AND the pool re-listed verbatim in the
  triples (absorption, exact f32 — the scan's ``pool_absorbed_raw``).
  It triggers ONLY where the table walk fails with the census family
  signature (the layout raises, or the probe-semantics walk — all
  slots, bounded only by the payload, no coordinate aborts — does not
  end at the declared region end): a store the table walk handles is
  never routed here, and a walk-exact store with junk coordinates is
  not the family (its own failure is re-raised).  Everything else
  stays fail-closed with the gap named on top of the triggering walk
  failure.  Named opens stay open: the tail field's semantics, count3's
  semantics (recorded, unvalidated), the weak-fit and no-fit stores.

Mixed-write composition (stage 8 integrated 2026-11-12 stage 9, #34;
docs/evidence/2026-11-12-mixedwrite-reps.md + the amended declaration in
2026-11-12-stage9-integration.md): on the walk-mismatch residue the
stage-8 census located three LOCATOR/PREDICATE artifacts — the write
laws were never wrong on these payloads.  Integrated on the walk-
mismatch path ONLY (after the stage-6 raw-array reading declines), so
every store the table walk handles keeps its exact code path (the
trigger-ordering discipline; walk-OK rows byte-identical):

- (a) the list-node window: the per-rep scan runs over the FULL body
  (``_scan_token_nodes`` — NODE_MAGIC to NODE_MAGIC, the exporter's own
  convention).  The single-rep locator keeps the stage-3d window (it
  ends at the first STRIP_RE match, which false-matches INSIDE point
  regions on 8/93 stores); a full-window single-rep locator would
  re-select the payload on 823/857 non-trigger composite stores (829 walk-exact + 28 raw-family), so the full-body
  scan is the walk-mismatch path's locator (the artifact's only
  manifestation — a store whose window truncates its node fails the
  primary walk and lands here).
- (b) the zero-block extent: ``layout()`` skips ALL consecutive zero
  groups after the counts; when the region opens with >= 16 full-write
  slots the 2-bit table's own leading bytes form whole zero groups and
  the skip overshoots INTO the table (misaligned P1g count; 38/133
  decoded table reps, 36 stores).  The walk-mismatch path's table law
  takes the zero-block EXTENT as a candidate (1..k groups): exactly one
  extent must yield the walk-exact decode, ambiguity stays fail-closed
  (measured: all 133 corpus table reps resolve at a unique extent).
- (c) the flat law (the stage-7 container PART-1 reading) joins the
  raw law as the third per-node fallback: c1 full triples straight
  after the 4-B tail field (start pinned by counts_end, NO escape
  required), all-nice under :func:`_nice` (the raw scan's 1e-6 floor
  rejects real near-zero coordinates — d51eb38c: floor-fit 0.632,
  exporter-predicate all-nice), x-ascending or the pool fully
  re-listed; the sub-sections follow byte-adjacent.
- (d) on a walk-mismatch the per-rep composition runs over ALL token
  nodes before fail-closing: pool group k is absorbed by the k-th
  law-decoded rep's region (exact f32, then the stage-4b noise
  tolerance, capped at 10,000-vertex pools — measured 0 noise on the
  81), the M2b refs gate applies per rep, and the store exports only
  when EVERY pool vertex is region-absorbed (vertices re-listed only
  by the ``05 08 01`` sub-node records have unpinned element indices —
  the store stays fail-closed for export until the sub-node
  element-index law pins them).

Amended declaration basis (stage9-absorption-probe.csv, committed
before the A/B): the census's pairing loop breaks at the FIRST full
match and its sub-node record set includes the pool wrappers' own
``05 08 01`` vertex records, so on multi-rep stores pools 1+ were
matched at rep 0 before their diagonal rep's region was tested — the
census's "22 subnode-assisted" class is that early-break artifact.
Re-measured without the break: 81 of the 82 reps-full stores are fully
region-absorbed DIAGONALLY (60 single-rep strict + 21 multi-rep; all
dev, exact f32), bad44bdf (1 uncovered vertex) and the 11 UV-family
stores stay fail-closed.  D1 is therefore +81 exports (amended from
the note's +60); the amendment is committed before the corpus run.

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


def _loop_triangles(mk, idxs, points):
    """One exported loop's triangles under the strip/polygon semantics
    (G3): 0x4c polygon fans triangulate from the first reference,
    0x42/0x4a strips use the sliding window with the odd-triangle
    winding flip; degenerate triangles (repeated coordinates, or the
    exactly-zero cross product on strips, G3 F7) are skipped and
    counted.

    Returns ``(triangles, degenerate)``; ``idxs`` are written-point
    ranks (indices into ``points``, the exported vertex list)."""
    lp = [points[i] for i in idxs]
    triangles = []
    degenerate = 0
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
    return triangles, degenerate


def _e0b_dup_pin(elements, points, written_rank, dropped):
    """The stage-10 E0-b dup-pin evaluation over one call's dropped
    loops (the curve-entry coordinate law, restricted per the landed
    analysis's ``U4-stage5-recommendation``; see the module docstring).

    The U4-D dup law (ported from the stage-4a decoder's ``dup_prev``,
    decode_curve_entries.py — not re-derived): a loop-referenced skip
    slot carries the bit-exact coordinates of the written vertex of its
    immediately preceding written element (the per-face copy — no new
    vertices).  Battery-supported iff EVERY dropped loop is
    coplanarity-testable (its record carries a 12-B normal, and every
    referenced skip slot has a preceding written element to weld to)
    AND coplanar against that normal with the dup-pinned coordinates
    (the stage-3b battery, :func:`_loop_plane_status`,
    :data:`PLANE_TOL`) — the analysis's E0-b criterion (coverage full
    AND zero nonplanar).  One normal-less or nonplanar dropped loop
    keeps the whole store on the conservative non-export rule.

    Returns ``{"triangles", "degenerate", "loops"}`` when supported
    (the pinned loops' triangles, written-rank indexed), ``None``
    otherwise."""
    skips = {i for i, (_v, pt) in enumerate(elements) if pt is None}
    pin: dict[int, int] = {}
    for _mk, _normal, loop in dropped:
        for r in loop:
            if r in skips and r not in pin:
                j = r - 1
                while j >= 0 and elements[j][1] is None:
                    j -= 1
                if j >= 0:
                    pin[r] = j
                # j < 0: no preceding written element — unpinnable
    if any(r in skips and r not in pin for _mk, _n, loop in dropped for r in loop):
        return None
    pinned = list(elements)
    for r, j in pin.items():
        pinned[r] = (1, elements[j][1])
    triangles = []
    degenerate = 0
    for mk, normal, loop in dropped:
        if normal is None:
            return None  # a normal-less dropped loop: battery cannot test it
        st, _res = _loop_plane_status(loop, normal, pinned)
        if st != "coplanar":
            return None  # nonplanar under the dup pin (or a zero normal)
        resolved = [pin.get(r, r) for r in loop]
        tris, deg = _loop_triangles(mk, [written_rank[r] for r in resolved], points)
        triangles += tris
        degenerate += deg
    return {"triangles": triangles, "degenerate": degenerate, "loops": len(dropped)}


def _triangulate(elements, records):
    """Triangles under the identity mapping (strip/polygon semantics).

    Loop references are 0-based element indices; triangles index the
    WRITTEN points (the exported vertex list), so referenced elements
    are remapped through the written rank.  Loops referencing skip
    slots (curve entries — their coordinates live in the curve records,
    U4) are skipped and counted: the conservative rule names the gap
    instead of guessing coordinates — EXCEPT the stage-10 E0-b dup-pin
    law (:func:`_e0b_dup_pin`): when this call produced NO triangles
    (the store's primary triangulation is empty — the E0 class) and
    EVERY dropped loop is battery-supported under the dup pin, the
    candidate rides ``stats["dup_pin"]`` for the caller to merge at the
    store level (per-rep paths must gate on the WHOLE store's mesh
    being empty — a rep-level fire inside an otherwise-passing store
    would be the 471-passing-stores downside exposure).  Strip
    triangles (0x42/0x4a) skip the degenerate ones (repeated
    coordinates or exactly-zero cross product, G3 F7); polygon fans
    (0x4c) skip repeated coordinates.

    Returns ``(triangles, degenerate, stats)`` where ``stats`` carries
    the loop counters for the summary's composite block (plus the
    ``dup_pin`` candidate exactly when the law's precondition held and
    it evaluated; consumers pop it before assembling ``info``).
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
    dropped = []
    for _off, mk, normal, counts, refs, _w in records:
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
                dropped.append((mk, normal, loop))
                continue
            loops_exported += 1
            idxs = [written_rank[r] for r in loop]
            tris, deg = _loop_triangles(mk, idxs, points)
            degenerate += deg
            triangles += tris
    stats = {
        "loops_exported": loops_exported,
        "loops_curve_entry": loops_curve_entry,
    }
    if not triangles and dropped:
        stats["dup_pin"] = _e0b_dup_pin(elements, points, written_rank, dropped)
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

    Stage-6 raw-array fallback (stage-4a law, 2026-11-12, #34): when
    the table walk fails with the walk-mismatch family signature, the
    payload may continue past the header as raw f32 triples
    (:func:`decode_raw_array`); a store it covers exports with stage
    ``identity-raw-array``, one it does not cover keeps the
    ``undecoded-variant`` classification with the triggering walk
    failure AND the raw gap both named.

    Stage-9 mixed-write composition (stage-8 laws, 2026-11-12, #34):
    when the raw-array law declines the store too, the per-rep
    decomposition runs over ALL token nodes on the FULL-body window
    (:func:`_decode_mixedwrite` — the zero-block extent candidates,
    the flat law's counts_end-pinned start, the diagonal absorption
    precondition with the sub-node route fail-closed); a store it
    covers exports with stage ``identity-mixedwrite-reps``, one it
    does not cover keeps ``undecoded-variant`` with the walk, raw AND
    composition gaps all named.

    Stage-10 E0-b dup-pin law (2026-11-12, #34): on every exported
    path, a store whose primary triangulation is EMPTY (the census's
    ``empty-mesh`` class) exports its dropped curve-entry loops when
    EVERY one is battery-supported under the dup pin
    (:func:`_e0b_dup_pin` — the landed analysis's restricted
    battery-supported subset E0-b; the per-rep paths gate the merge on
    the WHOLE store's mesh being empty).  Anything else keeps the
    conservative non-export rule and its warning; the U4-M mid law
    stays unsupported and is not implemented.
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
    try:
        elements, region_info = decode_region(payload, elem_decl)
    except ExportError as exc:
        # Stage-6 (2026-11-12, #34): the walk-mismatch residue's
        # raw-array law runs ONLY where the table walk fails with the
        # census family signature (layout raise, or the probe-semantics
        # walk not ending at the declared region end).  A store the
        # table walk handles never reaches this branch; a walk-exact
        # store with junk coordinates is not the family (its own
        # failure is re-raised).  When the raw reading does not cover
        # the store either, both gaps are named (fail-closed).
        if _walk_mismatch(payload, elem_decl) is None:
            raise
        try:
            return _decode_raw_array(data, lo, hi, groups, payload, elem_decl)
        except ExportError as raw_exc:
            raw_detail = raw_exc.detail
        # Stage-9 (2026-11-12, #34): the stage-8 mixed-write
        # composition — the per-rep decomposition over ALL token nodes
        # on the FULL-body window (the stage-8 locator), each node
        # under the table/raw/flat laws (the zero-block extent
        # candidates; the flat law's counts_end-pinned start), runs
        # before the store fails closed.  The raw path above keeps the
        # stage-6 behavior (its 28 exports are byte-identical); this
        # path only sees stores the raw law declines.
        try:
            return _decode_mixedwrite(data, lo, hi, groups)
        except ExportError as reps_exc:
            raise ExportError(
                "undecoded-variant",
                f"{exc.detail}; the stage-4a raw-array law does not "
                f"cover the store either ({raw_detail}); the stage-8 "
                f"mixed-write per-rep composition does not export it "
                f"either ({reps_exc.detail})",
            ) from reps_exc
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
    # Stage-10 E0-b dup-pin law (2026-11-12, #34): the primary
    # triangulation is empty (the census's empty-mesh class) and EVERY
    # dropped curve-entry loop is battery-supported under the dup pin —
    # the loops export with their skip slots welded (the landed
    # analysis's restricted subset; single-rep path, so this call IS
    # the store-level mesh).  ``None`` (or no candidate) keeps the
    # conservative non-export rule and its warning.
    dup_pin = loop_stats.pop("dup_pin", None)
    curve_entry_law = 0
    if dup_pin is not None:
        triangles = triangles + dup_pin["triangles"]
        degenerate += dup_pin["degenerate"]
        loop_stats["loops_exported"] += dup_pin["loops"]
        curve_entry_law = dup_pin["loops"]
        loop_stats["loops_curve_entry"] = 0

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
    if curve_entry_law:
        info["curve_entry_law"] = "e0b-dup-pin"
        info["loops_curve_entry_exported"] = curve_entry_law
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
    reps_dup_pin = []
    for k, d in enumerate(decoded):
        node_bytes += len(d["payload"])
        if k >= len(groups):
            # stage-5 review O2 hardening: a walk-exact rep beyond the
            # pool groups has no pool to re-list — per-rep absorption
            # is unestablished, so it stays unexported (fail-closed;
            # measured 0/152 on the corpus A/B).
            reps_unexported.append(
                f"rep {k}: no pool group to re-list ({len(groups)} pool "
                f"groups for {len(decoded)} walk-exact reps; per-rep "
                "absorption unestablished)"
            )
            continue
        gv = groups[k].vertices
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
        # stage-10 E0-b candidate for this rep (its own triangulation
        # is empty and its dropped loops were battery-evaluated):
        # recorded even when the law REJECTED (None) — a rep with an
        # unsupported dropped loop must veto another rep's fire at the
        # store-level gate below (stage-10 review F1: dropping the None
        # candidate made that veto dead code and zeroed the curve-entry
        # counters while unexported loops remained).  Merged at the
        # STORE level below only when the whole store's mesh is empty —
        # a rep-level fire inside an otherwise-exporting store would be
        # the 471-passing-stores downside exposure.
        if "dup_pin" in stats_k:
            reps_dup_pin.append((base, stats_k.pop("dup_pin")))
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
    # Stage-10 E0-b store-level gate: fire only when the WHOLE store's
    # mesh is empty and every rep with dropped loops is battery-
    # supported; one unsupported rep keeps everything conservative.
    curve_entry_law = 0
    if not triangles and reps_dup_pin and all(c is not None for _b, c in reps_dup_pin):
        for b, c in reps_dup_pin:
            triangles += [(a + b, s + b, t + b) for a, s, t in c["triangles"]]
            degenerate += c["degenerate"]
            loop_stats["loops_exported"] += c["loops"]
            curve_entry_law += c["loops"]
        loop_stats["loops_curve_entry"] = 0
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
    if curve_entry_law:
        info["curve_entry_law"] = "e0b-dup-pin"
        info["loops_curve_entry_exported"] = curve_entry_law
    return points, triangles, degenerate, info


# --- stage-6: the walk-mismatch residue's raw-array law (stage 4a,
# integrated 2026-11-12, #34) -------------------------------------------
#
# The law as committed (docs/evidence/2026-11-10-node-streams.md section
# "Stage 4a-residue" + residue-raw-scan.csv + the reference
# implementations classify_residue_family.py --raw / probe_residue_anchor.py):
# a walk-mismatch payload continues past the header as raw f32 triples;
# the start is pinned by the trail-escape condition; strong fit = nice
# AND x-ascending over the full span (the scan's criteria and predicate,
# ported verbatim — not re-derived); the pool must re-list verbatim.
# The tail field's and count3's semantics stay open (named).

# The committed scan's candidate bound: 4-aligned starts 32..64
# (classify_residue_family.py RAW_MAX_START).
RAW_MAX_START = 64

# The committed strong-fit bar (residue-raw-scan.csv: strong = nice >=
# 0.98 AND x-ascending >= 0.98 over the full elem_decl span).
RAW_FIT_RATE = 0.98


def _raw_nice(v: float) -> bool:
    """The raw scan's coordinate predicate (the stage-2c probe's
    predicate, kept verbatim: the raw array has no table to fix the
    parse, so the rate IS the parse validation — :func:`_nice`'s
    dropped 1e-6 floor was never the measured criterion here)."""
    return v == v and (v == 0.0 or 1e-6 < abs(v) < 1e7)


def _walk_mismatch(payload: bytes, elem_decl: int):
    """The walk-mismatch family signature (the census probe's walk
    semantics, ``decode_big_form_points.decode_region``: all elem_decl
    slots walked bounded ONLY by the payload, no coordinate aborts).

    Returns the mismatch profile (dict) when the declared P1t prefix
    does not describe the payload — the layout raises, or the walk does
    not end exactly at the declared region end — and ``None`` when the
    walk is exact (a walk-exact store with junk coordinates is not the
    family; the caller re-raises the original failure).
    """
    tok = payload.find(LIST_TOKEN)
    if tok < 0:  # unreachable behind find_list_node, kept total
        return {"layout_error": "no list token"}
    p = tok + 5
    try:
        _, p = read_count(payload, p)
        _, p = read_count(payload, p)
    except (IndexError, struct.error):
        return {"layout_error": "unreadable declared counts"}
    while p + 4 <= len(payload) and payload[p : p + 4] == b"\x00\x00\x00\x00":
        p += 4
    table_len = (elem_decl + 3) // 4
    count_pos = p + table_len
    if count_pos >= len(payload):
        return {
            "layout_error": f"the {table_len} B 2-bit table runs past "
            f"the payload (count position {count_pos} >= {len(payload)})"
        }
    try:
        write_count, region_start = read_count(payload, count_pos)
    except (IndexError, struct.error):
        return {"layout_error": "unreadable write count"}
    region_end = region_start + 4 * write_count
    if region_end > len(payload):
        return {
            "layout_error": f"declared write count {write_count} "
            f"overruns the payload (region end {region_end} > "
            f"{len(payload)})"
        }
    pos = region_start
    for v in table_slots(payload, p, table_len, elem_decl):
        shape = SHAPES[v]
        if pos + 4 * shape > len(payload):
            break  # the probe's clean stop: bounded by the payload only
        pos += 4 * shape
    if pos != region_end:
        return {
            "walk_end": pos,
            "region_end": region_end,
            "delta_words": (pos - region_end) // 4,
        }
    return None


def decode_raw_array(payload: bytes, elem_decl: int, poolv):
    """The raw-array reading of a walk-mismatch list-node payload
    (stage-4a law, ported from ``classify_residue_family.py --raw`` and
    the committed start rule — not re-derived).

    ``[token][count1][count2][tail][elem_decl x [x][y][z] stride 12, x
    ascending][FF][count3 u32le][trail]``: the array start is the
    UNIQUE 4-aligned start in ``[32, RAW_MAX_START]`` whose full
    elem_decl span fits and whose trail-escape byte
    ``payload[start + 12*elem_decl]`` is ``0xFF`` (the committed start
    rule — it selected a unique start in 32/39 scan-fit stores; zero or
    several candidates stay fail-closed).  Strong fit = the scan's
    criteria at the pinned start: nice >= :data:`RAW_FIT_RATE` AND
    x-ascending >= :data:`RAW_FIT_RATE` (the scan's predicate and 1e-6
    pair tolerance).  Pool absorption = every distinct pool vertex
    re-listed verbatim in the triples (exact f32 — the scan's
    ``pool_absorbed_raw`` criterion).

    Returns ``(points, info)`` with ``points`` the elem_decl raw
    triples in array order (the element space — no skip slots, every
    element written) and ``info`` the raw anatomy for the composite
    summary block.  Raises :class:`ExportError` (``undecoded-variant``)
    with the specific gap otherwise: the start not pinned, a weak fit,
    or an unabsorbed pool.  The tail field's and count3's semantics are
    OPEN: count3 is recorded (``raw_count3``) when readable, never
    validated.
    """
    candidates = [
        s
        for s in range(32, RAW_MAX_START + 1, 4)
        if s + 12 * elem_decl < len(payload)
        and payload[s + 12 * elem_decl] == 0xFF
    ]
    n_cand = (RAW_MAX_START - 32) // 4 + 1
    if len(candidates) != 1:
        raise ExportError(
            "undecoded-variant",
            f"raw-array start not pinned: the trail-escape condition "
            f"payload[start + 12*{elem_decl}] == 0xFF selects "
            f"{len(candidates)} of the {n_cand} candidate starts "
            f"(4-aligned 32..{RAW_MAX_START}, the committed scan bound) "
            "— fail-closed (the law's start rule)",
        )
    start = candidates[0]
    if elem_decl < 2:
        raise ExportError(
            "undecoded-variant",
            f"raw-array fit undefined: elem_decl {elem_decl} leaves the "
            "scan's x-ascending rate without a consecutive pair (no-fit)",
        )
    ps = set(poolv)
    xs = []
    points = []
    nicec = 0
    span = payload[start : start + 12 * elem_decl]
    for x, y, z in struct.iter_unpack("<fff", span):
        if _raw_nice(x) and _raw_nice(y) and _raw_nice(z):
            nicec += 1
        xs.append(x)
        points.append((x, y, z))
    rate = nicec / elem_decl
    asc = sum(1 for a, b in zip(xs, xs[1:]) if b >= a - 1e-6) / (elem_decl - 1)
    if rate < RAW_FIT_RATE or asc < RAW_FIT_RATE:
        raise ExportError(
            "undecoded-variant",
            f"raw-array weak fit at the pinned start {start}: nice "
            f"{rate:.4f} / x-ascending {asc:.4f} below the "
            f"{RAW_FIT_RATE} strong-fit bar (the committed criteria; "
            "weak-fit family, fail-closed)",
        )
    missing = ps - set(points)
    if missing:
        raise ExportError(
            "undecoded-variant",
            f"raw-array pool not absorbed: {len(missing)} of {len(ps)} "
            f"pool vertices absent from the {elem_decl} raw triples "
            "(exact-f32 absorption, the scan's pool_absorbed_raw "
            "criterion; fail-closed)",
        )
    trail_at = start + 12 * elem_decl
    info = {
        "raw_start": start,
        "raw_nice_rate": round(rate, 4),
        "raw_x_asc_rate": round(asc, 4),
        "raw_trail_bytes": len(payload) - trail_at,
    }
    try:
        info["raw_count3"], _after = read_count(payload, trail_at)
    except (IndexError, struct.error):
        pass  # the escape byte's count runs past the payload: open, named
    return points, info


def _decode_raw_array(data, lo, hi, groups, payload, elem_decl):
    """Export path of the raw-array law: decode the array, then the
    committed export ladder on the raw element space — records parsed
    over the store body, the M2b identity refs gate (gated families'
    references resolve inside the elem_decl element space), strip/polygon
    triangulation.  Raises :class:`ExportError` (``undecoded-variant``)
    with the raw gap when the law does not cover the store."""
    poolv = [v for g in groups for v in g.vertices]
    points, raw_info = decode_raw_array(payload, elem_decl, poolv)
    elements = [(0, pt) for pt in points]
    records, n_hdrs = parse_strip_records(
        data, lo, hi, elem_decl, elements=elements
    )
    all_refs = [
        r for _o, mk, _n, _c, refs, _w in records if mk in GATED for r in refs
    ]
    if all_refs:
        mx = max(all_refs)
        if mx >= elem_decl:
            raise ExportError(
                "undecoded-variant",
                f"facet references beyond the raw-array element space: "
                f"max ref {mx} >= element count {elem_decl} (M2b "
                "identity on the raw array; G3 open question 2)",
            )
    triangles, degenerate, loop_stats = _triangulate(elements, records)
    skipped_markers: dict[int, int] = {}
    for _o, mk, _n, _c, _refs, _w in records:
        if mk not in (0x42, 0x4A, 0x4C):
            skipped_markers[mk] = skipped_markers.get(mk, 0) + 1
    info = {
        "stage": "identity-raw-array",
        "element_decl": elem_decl,
        "node_points": len(points),
        "curve_entries": 0,
        "facet_candidates": n_hdrs,
        "facet_records": len(records),
        "skipped_markers": skipped_markers,
        "node_bytes": len(payload),
        **raw_info,
        **loop_stats,
    }
    return points, triangles, degenerate, info


# --- stage-9: the mixed-write stream's locator/predicate artifacts
# (stage 8, integrated 2026-11-12, #34) ---------------------------------
#
# The stage-8 census (scripts/triage/mixedwrite_decode.py,
# docs/evidence/2026-11-12-mixedwrite-reps.md) showed the walk-mismatch
# residue's payloads parse end-to-end with the COMMITTED write laws once
# three locator/predicate artifacts are fixed.  The functions below port
# the census's laws verbatim (not re-derived): the zero-block extent
# candidates (table_decode), the escape-pinned raw probe (raw_probe),
# the per-node law order table -> raw -> flat (decode_node), and the
# per-rep composition (audit_store), scoped to the walk-mismatch path
# and to the exporter's absorption/refs/triangulation gates.


def _token_counts_end(payload: bytes):
    """The position after the declared counts (the P1g prefix's end),
    or ``None`` when unreadable.  The mixed-write node decode pins the
    flat law's start and the zero-block extent candidates on this
    offset (the stage-8 decoder's ``counts_end``);
    :func:`_scan_token_nodes` validated the counts already, so ``None``
    here is unreachable behind it."""
    tok = payload.find(LIST_TOKEN)
    if not 0 <= tok <= 64:
        return None
    p = tok + 5
    try:
        _, p = read_count(payload, p)
        _, p = read_count(payload, p)
    except (IndexError, struct.error):
        return None
    return p


def _table_decode_extents(payload: bytes, element_count: int, counts_end: int):
    """The stage-3b table walk with the zero-block EXTENT as a
    candidate (stage-8 artifact 2; ported from
    ``mixedwrite_decode.table_decode`` — not re-derived).

    The committed :func:`layout` skips ALL consecutive zero groups
    after the counts; when the region opens with >= 16 full-write slots
    the 2-bit table's own leading bytes form whole zero groups, the
    skip overshoots INTO the table, and the P1g count reads misaligned
    (38/133 decoded table reps, 36 stores; 221df959's "declared 194").
    The extent law: the table may start at ``counts_end + 4*e`` for
    ``e`` in ``1..k`` (``k`` = the zero-group run after the counts);
    exactly one extent must yield the walk-exact decode (the walk
    consumes exactly the declared write count, every coordinate
    finite and plausible) — several decode, the extent stays
    fail-closed (ambiguous); none, this is not a table store.  The
    committed layout() is untouched: a store whose committed skip
    misaligns fails the primary walk and lands on this path, so the
    candidates cover the artifact's full incidence without re-routing
    walk-OK stores (measured: extents inside the zero block read a
    zero count and can never walk exact — the committed skip position
    is the only other candidate the law can select).

    Returns ``(extent, elements, skips, region_end_rel, write_count)``
    for the unique walk-exact extent, ``("ambiguous", results)`` when
    several decode, or ``None``.
    """
    if payload[counts_end : counts_end + 4] != b"\x00\x00\x00\x00":
        return None
    ext = 1
    while (
        payload[counts_end + 4 * ext : counts_end + 4 + 4 * ext]
        == b"\x00\x00\x00\x00"
    ):
        ext += 1
    table_len = (element_count + 3) // 4
    results = []
    for e in range(1, ext + 1):
        table_start = counts_end + 4 * e
        count_pos = table_start + table_len
        if count_pos >= len(payload):
            continue
        try:
            wc, region_start = read_count(payload, count_pos)
        except (IndexError, struct.error):
            continue
        if wc > 3 * element_count:
            continue
        region_end = region_start + 4 * wc
        if region_end > len(payload):
            continue
        pos = region_start
        elements = []
        skips = 0
        ok = True
        x = y = z = 0.0  # the initial LCP state is the origin (P1i)
        for i in range(element_count):
            v = (payload[table_start + i // 4] >> (2 * (i % 4))) & 3
            shape = SHAPES[v]
            if shape == 0:
                skips += 1
                elements.append((v, None))
                continue
            if pos + 4 * shape > region_end:
                ok = False
                break
            if shape == 3:
                x, y, z = _f32(payload, pos), _f32(payload, pos + 4), _f32(payload, pos + 8)
            elif shape == 2:
                y, z = _f32(payload, pos), _f32(payload, pos + 4)
            else:
                z = _f32(payload, pos)
            vals = (x, y, z) if shape == 3 else ((y, z) if shape == 2 else (z,))
            if not all(_nice(c) for c in vals):
                ok = False
                break
            pos += 4 * shape
            elements.append((v, (x, y, z)))
        if ok and pos == region_end:
            results.append((e, elements, skips, region_end, wc))
    if len(results) == 1:
        return results[0]
    if len(results) > 1:
        return ("ambiguous", results)
    return None


def _raw_escape_probe(payload: bytes, element_count: int):
    """The stage-4a raw-array start rule + fit rates on one node
    payload (ported from ``mixedwrite_decode.raw_probe``): the UNIQUE
    4-aligned start in ``[32, RAW_MAX_START]`` whose full elem_decl
    span fits and whose trail-escape byte ``payload[start +
    12*elem_decl]`` is ``0xFF``, with the per-triple nice rate (the
    scan's :func:`_raw_nice` predicate — 1e-6 floor kept verbatim) and
    the x-ascending rate.  Returns ``(start, nice_rate, asc_rate)`` or
    ``None`` (zero or several candidates — fail-closed)."""
    cands = [
        s
        for s in range(32, RAW_MAX_START + 1, 4)
        if s + 12 * element_count < len(payload)
        and payload[s + 12 * element_count] == 0xFF
    ]
    if len(cands) != 1:
        return None
    s = cands[0]
    nicec = 0
    xs = []
    for k in range(element_count):
        x, y, z = struct.unpack_from("<fff", payload, s + 12 * k)
        if _raw_nice(x) and _raw_nice(y) and _raw_nice(z):
            nicec += 1
        xs.append(x)
    rate = nicec / element_count
    asc = (
        sum(1 for a, b in zip(xs, xs[1:]) if b >= a - 1e-6) / (element_count - 1)
        if element_count > 1
        else 1.0
    )
    return s, rate, asc


def _decode_node_mixedwrite(payload: bytes, element_count: int, counts_end: int, poolv):
    """Decode one token-node payload with the stage-8 law set (ported
    from ``mixedwrite_decode.decode_node`` — not re-derived), in the
    census's order:

    (a) the stage-3b table law with the zero-block extent candidates
        (:func:`_table_decode_extents`);
    (b) the stage-4a raw law — the committed start rule and fit
        criteria (:data:`RAW_FIT_RATE`, the scan's :func:`_raw_nice`).
        The pool-absorption gate is NOT applied here: the composition
        judges absorption per rep (a multi-rep store's pool spans
        several regions);
    (c) the flat law (the stage-7 container PART-1 reading; stage-8
        artifact 3): ``element_count`` full triples straight after the
        4-B tail field — start pinned by ``counts_end``, NO escape
        required, no zero block or table — all-nice under
        :func:`_nice` (the exporter predicate; the raw scan's 1e-6
        floor rejects real near-zero coordinates on these stores),
        x-ascending >= :data:`RAW_FIT_RATE` OR the pool fully
        re-listed verbatim (junk spans absorb nothing and fail here).

    Returns ``(law, elements, pts, region_end_rel, write_count,
    failure)`` with ``law`` in ``{'table', 'raw', 'flat', None}``;
    ``elements`` is the (slot, point) element space (raw/flat elements
    are all written, the stage-6 raw path's shape)."""
    td = _table_decode_extents(payload, element_count, counts_end)
    if td is not None and td[0] != "ambiguous":
        _e, elements, skips, region_end, wc = td
        return (
            "table",
            elements,
            [pt for _v, pt in elements if pt is not None],
            region_end,
            wc,
            "",
        )
    if td is not None and td[0] == "ambiguous":
        return None, [], [], 0, 0, "table: ambiguous zero-block extent"
    probe = _raw_escape_probe(payload, element_count)
    if probe is not None:
        s, rate, asc = probe
        if rate >= RAW_FIT_RATE and asc >= RAW_FIT_RATE:
            pts = list(
                struct.iter_unpack("<fff", payload[s : s + 12 * element_count])
            )
            return (
                "raw",
                [(0, pt) for pt in pts],
                pts,
                s + 12 * element_count,
                3 * element_count,
                "",
            )
    s = counts_end + 4
    if s + 12 * element_count <= len(payload) and element_count >= 2:
        ok = True
        xs = []
        for k in range(element_count):
            x, y, z = struct.unpack_from("<fff", payload, s + 12 * k)
            if not (_nice(x) and _nice(y) and _nice(z)):
                ok = False
                break
            xs.append(x)
        if ok:
            asc = (
                sum(1 for a, b in zip(xs, xs[1:]) if b >= a - 1e-6)
                / (element_count - 1)
            )
            pts = list(
                struct.iter_unpack("<fff", payload[s : s + 12 * element_count])
            )
            pset = set(poolv)
            hits = len(pset & set(pts))
            if asc >= RAW_FIT_RATE or (pset and hits == len(pset)):
                return (
                    "flat",
                    [(0, pt) for pt in pts],
                    pts,
                    s + 12 * element_count,
                    3 * element_count,
                    "",
                )
    if probe is not None:
        s, rate, asc = probe
        return (
            None,
            [],
            [],
            0,
            0,
            f"raw-weak-fit@{s} nice={rate:.4f} asc={asc:.4f}",
        )
    return None, [], [], 0, 0, "table: no walk-exact zero-block extent"


def _decode_mixedwrite(data, lo: int, hi: int, groups):
    """The stage-8 mixed-write per-rep composition (stage 9, #34): the
    stage-5 per-rep decomposition applied to the walk-mismatch residue
    over the FULL-body window, with the stage-8 locator/predicate laws
    per node (:func:`_decode_node_mixedwrite`).

    Rep k = (pool group k, the k-th law-decoded token node in body
    order — the diagonal, measured on the census population: all 81
    region-absorbable stores pair diagonally with exact f32 —, that
    node's record territory ``[region_end_k, next decoded node)``).
    The store exports only when EVERY pool vertex is absorbed by its
    diagonal rep's region (exact f32, then the stage-4b noise
    tolerance capped at 10,000-vertex pools): vertices re-listed only
    by the ``05 08 01`` sub-node records have unpinned element indices
    and keep the store fail-closed for export (the stage-8 note's
    integration item (e); bad44bdf's class).  Per rep: the M2b refs
    gate against the rep's own element count, records parsed with the
    committed width laws, strip/polygon triangulation; merged meshes
    concatenate the exported reps' written points.  A rep whose gated
    references leave its own element space stays unexported with the
    reason named (stage-5 per-rep fail-closed); reps beyond the pool
    groups have no pool to re-list and stay unexported (stage-5 O2).

    Raises :class:`ExportError` (``undecoded-variant``) with the
    specific gap when no node decodes, absorption is not established,
    or no rep exports."""
    poolv = [v for g in groups for v in g.vertices]
    pool_set = set(poolv)
    nodes = _scan_token_nodes(data, lo, hi)
    decoded = []
    law_counts = {"table": 0, "raw": 0, "flat": 0}
    node_failures = []
    for npos, payload, c1, _c2 in nodes:
        counts_end = _token_counts_end(payload)
        if counts_end is None:  # unreachable behind _scan_token_nodes
            continue
        law, elements, pts, region_end_rel, wc, failure = _decode_node_mixedwrite(
            payload, c1, counts_end, poolv
        )
        if law is None:
            node_failures.append(f"node@{npos}: {failure}" if failure else f"node@{npos}: undecoded")
            continue
        law_counts[law] += 1
        decoded.append(
            {
                "pos": npos,
                "payload": payload,
                "elem": c1,
                "law": law,
                "elements": elements,
                "pts": pts,
                # absolute end of the point region (the territory start)
                "region_end": npos + 4 + region_end_rel,
                "write_count": wc,
            }
        )
    if not decoded:
        raise ExportError(
            "undecoded-variant",
            f"the stage-8 mixed-write per-rep composition decodes none "
            f"of the {len(nodes)} token nodes over the full-body "
            f"window (table/raw/flat laws; "
            f"{'first: ' + node_failures[0] if node_failures else 'no token nodes'})",
        )
    # Store-level absorption precondition: every pool vertex in its
    # diagonal rep's region (exact f32, then the stage-4b noise
    # tolerance; the census measured exact f32 on all 81).  Vertices no
    # region re-lists are the sub-node record route's residue — their
    # element slots are unpinned, the store stays fail-closed (named).
    uncovered = 0
    for k, g in enumerate(groups):
        rep = decoded[k] if k < len(decoded) else None
        distinct = set(g.vertices)
        if rep is None:
            uncovered += len(distinct)
            continue
        pts_set = set(rep["pts"])
        missing = distinct - pts_set
        if missing and len(distinct) <= 10_000:
            missing = {
                v
                for v in missing
                if (best := _tol_match(v, rep["pts"])) is None
                or best > NOISE_REL
            }
        uncovered += len(missing)
    if uncovered:
        raise ExportError(
            "undecoded-variant",
            f"the stage-8 mixed-write per-rep composition does not "
            f"establish pool absorption: {uncovered} of {len(pool_set)} "
            f"pool vertices are absent from every decoded rep region "
            f"({len(decoded)} law-decoded reps for {len(groups)} pool "
            "groups; vertices re-listed only by the 05 08 01 sub-node "
            "records have unpinned element indices — fail-closed for "
            "export until the sub-node element-index law pins them)",
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
    reps_dup_pin = []
    for k, d in enumerate(decoded):
        node_bytes += len(d["payload"])
        if k >= len(groups):
            reps_unexported.append(
                f"rep {k}: no pool group to re-list ({len(groups)} pool "
                f"groups for {len(decoded)} law-decoded reps; per-rep "
                "absorption unestablished)"
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
        # stage-10 E0-b candidate (see _decode_per_rep; the None case
        # recorded too — stage-10 review F1, the same veto): merged at
        # the store level below, only when the whole mesh is empty.
        if "dup_pin" in stats_k:
            reps_dup_pin.append((base, stats_k.pop("dup_pin")))
        points += d["pts"]
        triangles += [(a + base, b + base, c + base) for a, b, c in tri_k]
        degenerate += deg_k
        loop_stats["loops_exported"] += stats_k["loops_exported"]
        loop_stats["loops_curve_entry"] += stats_k["loops_curve_entry"]
        facet_candidates += n_hdrs
        facet_records += len(records)
        write_count += d["write_count"]
        if d["law"] == "table":
            table_bytes += (d["elem"] + 3) // 4
        element_decl += d["elem"]
        curve_entries += len(d["elements"]) - len(d["pts"])
        for _o, mk, _n, _c, _refs, _w in records:
            if mk not in (0x42, 0x4A, 0x4C):
                skipped_markers[mk] = skipped_markers.get(mk, 0) + 1
    if not points:
        raise ExportError(
            "undecoded-variant",
            f"the stage-8 mixed-write per-rep composition exports no "
            f"rep: {'; '.join(reps_unexported) or 'no reps'}",
        )
    # Stage-10 E0-b store-level gate (see _decode_per_rep).
    curve_entry_law = 0
    if not triangles and reps_dup_pin and all(c is not None for _b, c in reps_dup_pin):
        for b, c in reps_dup_pin:
            triangles += [(a + b, s + b, t + b) for a, s, t in c["triangles"]]
            degenerate += c["degenerate"]
            loop_stats["loops_exported"] += c["loops"]
            curve_entry_law += c["loops"]
        loop_stats["loops_curve_entry"] = 0
    info = {
        "stage": "identity-mixedwrite-reps",
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
        "rep_laws": law_counts,
        **loop_stats,
    }
    if curve_entry_law:
        info["curve_entry_law"] = "e0b-dup-pin"
        info["loops_curve_entry_exported"] = curve_entry_law
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
