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
  addendum): a dropped loop whose skip slots can be welded to the
  written vertex of their immediately preceding written element (the
  U4-D dup law, ported from the stage-4a decoder's ``dup_prev``, not
  re-derived: no new vertices) may export under the dup pin.

  PER-LOOP 2026-11-18 (the surface-loss fix, #34; see
  docs/evidence/2026-11-18-composite-loop-weld.md): the decision is
  made for EACH dropped loop, independently — a loop is welded exactly
  when (1) every referenced skip slot is pinnable, (2) the loop is
  battery-supported: its record carries no normal, or the dup-pinned
  coordinates are coplanar against that normal at
  :data:`PLANE_TOL` (2e-3), and (3) it is mesh-safe: the incremental
  guard keeps the assembled mesh manifold (no undirected edge past two
  uses, no degenerate emission; :func:`_e0b_dup_pin`).  The old E0
  whole-store precondition (the
  store's primary triangulation had to be EMPTY) is GONE: on
  labios/main the non-empty 4,261-triangle primary mesh hid 10
  droppable loops worth 3,097 mm² (the three envelope panels at
  x=-22.7 and y=±12.4 plus six smaller loops; measured deviations
  <= 1.4e-6).  The battery is NOT weakened: the three width-misparsed
  loops it refuses there measure 2e-2..8.  The mesh guard is what
  keeps a weld from tipping a passing store's L2 row: without it the
  first full-corpus A/B found 26 manifold -> non-manifold regressions
  (welded loops whose boundary edges already had two uses in the
  surviving primary mesh); with it the same A/B has zero.  A refused
  or unpinnable loop stays dropped under the
  conservative non-export rule with its warning — it never vetoes
  another loop's weld.  The U4-M mid law stays DEMOTED to unsupported
  and is NOT implemented; the battery discriminates dup from next/mid
  wherever a loop references a slot (twin probe), and a ``mid`` slot is
  by construction referenced by no facet loop, so it enters no
  triangle either way.
- Primary-emit seam (2026-11-18, #34; docs/evidence/
  2026-11-18-primary-emit-seam.md): the short records' primary loop
  emission is guarded by the same incremental :func:`_mesh_safe` lever.
  A refused candidate is dropped only when it is a sliver — its area
  <= :data:`PRIMARY_LOOP_AREA_REL` (1%) of the store-level mesh area
  (:func:`decode_composite_store` measures it in a registry pass with
  the seam off) — and the store's mesh becomes manifold
  (``primary-loop-manifold-skip``); a larger over-use is real surface
  and is kept exactly as before (``primary-loop-manifold-kept``); a
  store that stays not-manifold after the slivers are out declines the
  seam fail-closed and keeps its pre-seam emission
  (``primary-loop-manifold-declined``).  The 24 not-manifold corpus
  parts split 15 flips / 9 kept with no surface above 0.76% dropped.
- Loop plane law: coplanarity against the record's stored 12-B normal
  (the corner quads are slanted planes; the axis-constant reading was
  too strict).  It is the weld's validation battery (above) and the
  width rank's tiebreak; not a blanket export gate: multi-plane
  fillet/bevel strips are legitimate geometry where whole-loop
  coplanarity does not apply (stage-3b loop battery: coplanar +
  skip-ref + multi-plane = 98.3% of testable loops).
- Record width (stage-3b rule, extended 2026-11-11 stage 4b,
  integrated 2026-11-12 stage 5; gap-edge battery 2026-11-18): per-record
  u8/u16be/u24be chosen by
  end-alignment onto the next header, ranked exact tiling first, then
  **no-repeated-refs-within-a-loop** (a u8 misread of a u16be record
  repeats refs inside the loop), then no out-of-range refs, then the
  **loop plane law** (a candidate whose normal-carrying loops are
  non-coplanar against the record's stored normal loses to one that is
  coplanar — the narrow-width tiebreak over interleaved non-STRIP_RE
  families, where u8 and u16be tie on tiling/repeats/oob and the
  committed rule picked the narrower misread), then the narrower
  width.  From 2026-11-18 the plane-law tiebreak also tests skip-bearing
  loops on their dup-pinned coordinates (the same battery): a gap-edge
  width whose loops land on skip slots and are nonplanar there loses to
  the fully-written width (labios/main's 3 misparsed records, 13.4 mm²
  recovered), while a legitimate curve loop stays coplanar (<= 1.4e-6)
  and is not penalized.  u24be enters for element counts above 65,535 (a 2-byte ref
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

import bisect
import dataclasses
import math
import struct

from catpart.geometry.errors import ExportError
from catpart.geometry.facets import (
    EXTENDED_ESCAPED_B4_RE,
    EXTENDED_ESCAPED_TY_RE,
    MAX_REFS,
    NORMAL_MARKERS_ALL,
    STRIP_RE,
    facet_headers,
    header_len,
    read_count,
    read_counts,
)
from catpart.geometry import mesh

NODE_MAGIC = b"\x04\x04\xfd\xff"
LIST_TOKEN = b"\xff\xff\x02\x00\x01"

MAX_ELEMENT_COUNT = 10_000_000
MAX_TABLE_BYTES = 1 << 20
#: The #34-era strip vote's count-table length cap: the base the #65
#: extension gates on (see :data:`MAX_LOOP_COUNTS`).
BASE_LOOP_COUNTS = 16
#: The strip vote's count-table length cap. 16 through the #34 era (the
#: corpus's clean stores carry k <= 16); 64 from #65 (2026-11-20): the
#: Trappe_Parachute gap records carry k == ty 24..39 — the cap was their
#: only blocker (565 unresolved 0x42 candidates on 77 parts parse at
#: (w2, k = ty), 379 of them exact-tiling + in-bounds; probe
#: scripts/triage/probe_top10_mesh_gap_dump.py --census-42). The
#: extension is zero-gated: a u16be count table misreads as u8 pairs
#: with a zero at every other entry (the CAAGsiStartVolume regression
#: measured 16/32 zeros and a not-manifold mesh), while every corpus
#: record the extension admits carries a zero-free table — a strip
#: writer never emits an empty loop.
MAX_LOOP_COUNTS = 64

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


def parse_049_record(data, o: int, nxt: int, n: int, normal, element_count):
    """The 0x49 triangle-list record under its PINNED law (2026-11-18).

    ``01 49 ty ff`` + ``u32le n`` + the 12-B f32le normal, then **no
    count table**: the ``n`` references are u16be element indices, three
    consecutive refs per triangle (``n == 3 * ty`` — the
    ``BR2-18b`` predicate), one 3-ref strip loop per triangle.  The
    record ends at or before the next header.

    Corpus measurement behind the law (docs/evidence/
    2026-11-18-composite-0x49.md, claims 0X49-01..07; the census runs on
    the exact parse seam over every composite store the exporter
    reaches): of 270,762 short-form 0x49 candidate headers, 270,743
    satisfy ``n == 3 * ty``, 269,905 tile EXACTLY to the next header
    (the family's record is 26 B at ``ty=1``), 270,270 keep every
    reference inside the decoded element space, and **270,270 / 270,270
    of those loops are coplanar against the stored normal at
    ``PLANE_TOL``** (the dup-pinned battery used by the weld).  The
    generic count law reaches only 2,233 of them and never reproduces
    this shape (its count bytes eat the first reference byte), which is
    why the family has its own reader instead of a new (width, k) vote:
    the count table is absent, not variant.

    Returns ``(offset, marker, normal, counts, refs, 2)`` — the counts
    are ``ty`` loops of three references (the family's triangle split) —
    or ``None`` when the record does not fit the law (a false-positive
    ``01 49`` byte pattern, or a store outside the element space).
    """
    ty = data[o + 2]
    if n != 3 * ty:
        return None
    end = o + 20 + 2 * n
    if end > nxt:
        return None
    refs = tuple(
        int.from_bytes(data[o + 20 + 2 * j : o + 22 + 2 * j], "big")
        for j in range(n)
    )
    if element_count is not None and any(r >= element_count for r in refs):
        return None
    return (o, 0x49, normal, (3,) * ty, refs, 2)


def parse_strip_records(data, lo: int, hi: int, element_count: int, elements=None):
    """Every strip record with the width disambiguated (stage-3b rule,
    extended 2026-11-11 stage 4b: u24be candidate + the loop plane
    tiebreak; integrated 2026-11-12 stage 5, #34).

    The 0x49 triangle-list family has its own pinned reader
    (:func:`parse_049_record`, 2026-11-18): it carries no count table,
    so the generic (width, k) vote is not applied to it.

    Candidate parses: width u8/u16be (plus u24be ONLY when
    ``element_count > 65,535`` — a 2-byte ref cannot index such an
    element space, and on smaller spaces a 3-byte candidate can only
    read junk past them: measured on the corpus A/B, 4 exported stores
    flip to OOB junk when u24be is offered below the threshold) x
    count-byte k (0..16 through the #34 era; 0..64 from #65,
    2026-11-20 — the extension zero-gated: a u16be count table misreads
    as u8 pairs with a zero at every other entry, while every corpus
    record the extension admits carries a zero-free table) summing to
    n, ending at or before the next header.  Rank: exact tiling, then
    no out-of-range refs, then no-repeated-refs-within-a-loop, then
    **non-coplanar normal-carrying loops** (only computed when
    ``elements`` — the decoded element space the refs index — is
    passed; a candidate whose loops are non-coplanar against the
    record's stored normal loses to one that is coplanar; from
    2026-11-18 a skip-bearing loop is tested on its dup-pinned
    coordinates with the same battery, so the gap-edge width choice
    prefers the fully-written parse over a misread whose loops land on
    skip slots), then the narrower width.  The winning parse is then
    gated fail-closed on the element space (#66, 2026-11-20): a record
    whose refs leave it stays unresolved, the same post-vote rule the
    extended family applies.  Returns ``(records, n_headers)`` where
    each record is ``(offset, marker, normal, counts, refs, width)``.
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
        hlen = header_len(data, o)
        if hlen is None or hlen == 6:
            continue  # the extended 6-byte form has its own parser
        mk = data[o + 1]
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
        if mk == 0x49:
            # The triangle-list family's own law (no count table; u16be
            # refs; n == 3*ty). The generic (width, k) vote below would
            # eat the first reference byte as a count. The law is the
            # 4-byte header form (``01 49 ty ff``); a 5-byte-form
            # candidate (zero accepted corpus records, BR2-17) stays
            # unresolved rather than falling back to the misparse.
            if hlen == 4:
                rec = parse_049_record(data, o, nxt, n, normal, element_count)
                if rec is not None:
                    out.append(rec)
            continue
        best = None
        for width in widths:
            for k in range(0, MAX_LOOP_COUNTS + 1):
                read = read_counts(data, base, k, nxt)
                if read is None:
                    break
                counts, counts_bytes = read
                if sum(counts) != n:
                    continue
                if k > BASE_LOOP_COUNTS and 0 in counts:
                    # #65 zero gate on the k extension: a u16be count
                    # table misreads as u8 pairs with a zero at every
                    # other entry (CAAGsiStartVolume: 16/32 zeros, a
                    # not-manifold mesh); every corpus record the
                    # extension admits is zero-free.
                    continue
                counts_end = base + counts_bytes
                end = counts_end + width * n
                if end > nxt:
                    continue
                refs = [
                    int.from_bytes(
                        data[counts_end + width * j : counts_end + width * (j + 1)],
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
                        if any(r >= len(elements) for r in loop):
                            continue
                        if any(r in skips for r in loop):
                            # Gap-edge width choice (2026-11-18): a
                            # parse whose loop lands on skip slots is
                            # the usual misread.  Test it on its
                            # dup-pinned coordinates with the SAME
                            # battery — a wrong width is nonplanar
                            # there (measured 2e-2..8 on the 3 bad
                            # labios/main loops) while a real curve
                            # loop stays coplanar (<= 1.4e-6), so a
                            # fully-written width wins the rank
                            # without a blanket no-skip-ref penalty
                            # that would hurt legitimate curve loops.
                            pin = _dup_pin_map(elements, loop)
                            if pin is None:
                                continue  # untestable: no battery
                            test = [pin.get(r, r) for r in loop]
                        else:
                            test = loop
                        st, _res = _loop_plane_status(test, normal, elements)
                        if st == "nonplanar":
                            nonplanar += 1
                rank = (
                    0 if end == nxt else 1,
                    1 if oob else 0,
                    1 if repeats else 0,
                    nonplanar,
                    width,
                    k,
                )
                if best is None or rank < best[0]:
                    best = (rank, tuple(counts), tuple(refs), width)
        if best is None:
            continue
        _rank, counts, refs, width = best
        if element_count is not None and any(r >= element_count for r in refs):
            # Fail-closed refs gate (#66, 2026-11-20), symmetric to the
            # extended family's post-vote rule (parse_extended_facet_
            # records): a record whose winning parse leaves the element
            # space is NOT this family's record. Before this gate the
            # short-form vote ranked ``repeats`` above ``oob`` and never
            # re-checked the winner, so a w2 big-endian misread of a
            # relaxed 0x41/0x44 record (all refs >= element_count) could
            # win against an in-bounds parse and reach ``_triangulate``,
            # where it raised ``IndexError`` in ``_dup_pin_map`` (Audi
            # R8) or ``KeyError`` in the RELAXED pass (5 submarine
            # parts). The record stays unresolved instead of tripping
            # the store-level refs gate.
            continue
        out.append((o, mk, normal, counts, refs, width))
    return out, len(hdrs)


#: Short-record markers the composite path exports. 0x49 is the strip
#: family the clean path already exports (``facets.SOUP_MARKERS`` —
#: ``STRIP_MARKERS`` includes it; 2026-11-18 ticket: the composite
#: admission lagged the clean path by this one marker). It is admitted
#: on exactly the 0x42 terms: the record must pass the committed
#: count/tiling law (:func:`parse_strip_records` — the escaped-count
#: reader, the width/plane rank, exact tiling), its references must
#: resolve in the element space (:data:`GATED` already included 0x49),
#: written loops emit under the strip window, and skip-bearing loops go
#: through the SAME structural acceptance as every other loop — the
#: per-loop dup-pin weld's coplanarity battery and incremental edge-use
#: (manifold) guard. No new reading is introduced.
EXPORTED_SHORT_MARKERS = (0x42, 0x49, 0x4A, 0x4C)

#: The T3 relaxed families (#61, 2026-11-20): 0x44 and 0x41 parse under
#: the SAME (width, k) tiling law as the exported families (226/226
#: carrier records: header_len=4, types 1/2, widths 1/2, counts tiling,
#: refs in pool range) but carry no 12-B normal and their primitive
#: reading G3 has not pinned.  Their loops export in the SECOND pass of
#: :func:`_triangulate`, under the STRICT mesh guard — no seam-area
#: exception — so a base-manifold mesh stays manifold by construction
#: and the base pass stays byte-identical to the pre-T3 behavior.  The
#: accepted/declined loop counts ride the summary as
#: ``relaxed_loops_accepted`` / ``relaxed_loops_declined``.
RELAXED_SHORT_MARKERS = (0x44, 0x41)

# --- the extended-header facet family (0x47/0x4f, 2026-11-18) --------------
#
# The header form is ``01 <mk> ty b3 b4 ff`` (`ff` at +5, not +3), then
# `u32le n`, a 12-B f32le normal on 0x4f (none on 0x47), the `b3 + b4`
# loop counts (one u8 each), and the refs. The ref block is
# ``3*ty`` independent-triangle refs followed by the loops the counts
# delimit; the first `b3` loops are triangle strips (the 0x42 law) and
# the last `b4` are closed polygons (the 0x4c fan law). The ref WIDTH is
# voted per record (u8/u16be/u24be — #62, 2026-11-20: exact tiling, then
# refs in bounds, then no repeated refs, then the 0x4f plane law, then
# the narrower width; the corpus's big-element stores tile at u24be,
# 97.6% vs u16be's 2.1%). The HEADER bytes ty/b3/b4 may each escape via
# read_count (P1g: u8 or ff + u32le) before the fixed ff — the escaped
# form (#64, 2026-11-20) joins as a second pass with repeats RANKED
# (their exact-tile records carry legitimate strip joins); the 6-byte
# pass keeps the #62 misread disqualification. The law is
# byte-measured on the Gabarit store's 9 records
# (docs/evidence/2026-11-18-extended-header-family.md): `b3 + b4` equals
# the counts-table length, `sum(counts) + 3*ty == n`, every record ends at
# or before the next header (8/9 exact tiles; the ninth is body-final),
# and the decoded mesh is a closed manifold whose three 0x4f faces
# reproduce pi*(r_out^2 - r_in^2) to <2%.

#: Markers observed in the extended-header form (the family's scope).
EXTENDED_HEADER_MARKERS = (0x47, 0x4F)

#: Extended-header markers carrying the 12-byte normal payload.
EXTENDED_NORMAL_MARKERS = (0x4F,)


@dataclasses.dataclass(frozen=True)
class ExtendedFacetRecord:
    """One extended-header facet record (see the block comment above)."""

    offset: int
    marker: int
    triangles: int  # ty: independent triangles at the start of the refs
    strips: int  # b3: leading loops, triangle-strip semantics
    polygons: int  # b4: trailing loops, closed-polygon fan semantics
    counts: tuple[int, ...]
    refs: tuple[int, ...]
    end: int
    normal: tuple[float, float, float] | None
    width: int = 2  # the voted ref width (u8/u16be/u24be, #62)


#: The escaped-header counts-table cap (#64): ``b3 + b4`` may escape to
#: u32le values, so the counts-table length needs a sanity bound (the
#: corpus's escaped records carry ``k`` 192; 4,096 is 20x that).
ESCAPED_MAX_K = 4_096


def _parse_escaped_extended_records(data, lo, hi, hdrs, element_count, elements, shipped):
    """The P1g-escaped extended-header records (#64, 2026-11-20).

    The 2026-11-18 header law reads ``ty``/``b3``/``b4`` as raw u8; the
    CAASdd*Stiffener gap forensics (#62 follow-up) measured a second
    header form where each of them may escape via :func:`read_count`
    (P1g: ``u8`` or ``0xff + u32le``) before the fixed ``ff`` +
    ``u32le n``: ``01 <mk> <ty@P1g> <b3@P1g> <b4@P1g> ff <u32le n>
    [12B normal if 0x4f] <b3+b4 counts@P1g> <n refs>``. The +2 shape
    (``ty`` escaped) and the +4 shape (``b4`` escaped) are invisible to
    both committed discovery patterns; the +3 shape (``b3`` escaped)
    rides the committed ``STRIP_RE``/``FACET_HEADER_RE`` candidates that
    the 6-byte law skips (``header_len != 6``).

    Everything after the header is the #62 law unchanged — counts law
    (``n == 3*ty + sum(counts)``), the width vote ranked ``(exact
    tiling, in-bounds, repeats, loop plane law, narrower width)`` — with
    ONE deliberate difference: **repeats are RANKED, not disqualified**.
    The escaped records carry legitimate strip joins (the CAASdd
    exact-tile records repeat refs in 114 of 453 loop groups; the facets
    model F3 already treats repeated references as real geometry), so
    the #62 misread disqualification would decline 127 of the 129
    corpus records. The winner's refs must still resolve in-bounds (the
    false-positive rule), and the emission keeps the per-record
    ``_mesh_safe`` guard, so a repeats-laden misread that slips past the
    rank still has to survive the manifold battery.

    Returns ``(records, candidates)`` — candidates counts every tried
    position; a candidate whose winning parse's refs leave the element
    space stays unresolved, and a candidate overlapping an already
    accepted record (shipped or escaped) is skipped, so the bytes are
    never parsed twice.
    """
    positions = {m.start() for m in EXTENDED_ESCAPED_TY_RE.finditer(data, lo, hi)}
    positions |= {m.start() for m in EXTENDED_ESCAPED_B4_RE.finditer(data, lo, hi)}
    positions |= {
        h
        for h in hdrs
        if data[h + 1] in EXTENDED_HEADER_MARKERS and header_len(data, h) != 6
    }
    if not positions:
        return [], 0
    bounds = sorted(set(hdrs) | positions | {hi})
    skips = (
        {i for i, (_v, pt) in enumerate(elements) if pt is None}
        if elements is not None
        else None
    )
    widths = (1, 2, 3) if element_count is not None and element_count > 65_535 else (1, 2)
    shipped_spans = [(r.offset, r.end) for r in shipped]
    records = []
    accepted: list[tuple[int, int]] = []
    tried = 0
    for o in sorted(positions):
        tried += 1
        if any(a <= o < e for a, e in shipped_spans):
            continue
        if any(a <= o < e for a, e in accepted):
            continue
        mk = data[o + 1]
        if mk not in EXTENDED_HEADER_MARKERS:
            continue
        try:
            ty, p = read_count(data, o + 2)
            b3, p = read_count(data, p)
            b4, p = read_count(data, p)
            if p >= hi or data[p] != 0xFF or p + 5 > hi:
                continue
            n = int.from_bytes(data[p + 1 : p + 5], "little")
            p += 5
            if not (0 <= n <= MAX_REFS):
                continue
            has_normal = mk in EXTENDED_NORMAL_MARKERS
            if has_normal:
                if p + 12 > hi:
                    continue
                normal = struct.unpack("<fff", data[p : p + 12])
                p += 12
            else:
                normal = None
            k = b3 + b4
            if k > ESCAPED_MAX_K:
                continue
            read = read_counts(data, p, k, hi)
            if read is None:
                continue
            counts, clen = read
            counts = tuple(counts)
            refs_start = p + clen
            if n != 3 * ty + sum(counts):
                continue
        except (IndexError, struct.error):
            continue
        nxt = min((b for b in bounds if b > o), default=hi)
        best = None
        for width in widths:
            end = refs_start + width * n
            if end > min(nxt, hi):
                continue
            refs = [
                int.from_bytes(
                    data[refs_start + width * j : refs_start + width * (j + 1)],
                    "big",
                )
                for j in range(n)
            ]
            repeats = False
            for start in range(0, 3 * ty, 3):
                if len(set(refs[start : start + 3])) < 3:
                    repeats = True
                    break
            off = 3 * ty
            for c in counts:
                if c > 0 and len(set(refs[off : off + c])) < c:
                    repeats = True
                    break
                off += c
            oob = (
                any(r >= element_count for r in refs)
                if element_count is not None
                else False
            )
            nonplanar = 0
            if normal is not None and elements is not None:
                off = 3 * ty
                for c in counts:
                    loop = refs[off : off + c]
                    off += c
                    if not loop:
                        continue
                    if any(r >= len(elements) for r in loop):
                        continue
                    if any(r in skips for r in loop):
                        pin = _dup_pin_map(elements, loop)
                        if pin is None:
                            continue
                        test = [pin.get(r, r) for r in loop]
                    else:
                        test = loop
                    st, _dev = _loop_plane_status(test, normal, elements)
                    if st == "nonplanar":
                        nonplanar += 1
            rank = (
                0 if end == nxt else 1,
                1 if oob else 0,
                1 if repeats else 0,
                nonplanar,
                width,
            )
            if best is None or rank < best[0]:
                best = (rank, tuple(refs), width, end)
        if best is None:
            continue
        _rank, refs, width, end = best
        if element_count is not None and any(r >= element_count for r in refs):
            continue
        records.append(
            ExtendedFacetRecord(
                offset=o,
                marker=mk,
                triangles=ty,
                strips=b3,
                polygons=b4,
                counts=counts,
                refs=refs,
                end=end,
                normal=normal,
                width=width,
            )
        )
        accepted.append((o, end))
    return records, tried


def _short_record_spans(data, lo, hi, records):
    """(start, end) spans of the accepted short records.

    The #65 exact-tiling exception's overlap guard reads these: an
    extended candidate whose winning span would swallow an accepted
    short record stays unresolved. Ends are recomputed from the same
    deterministic walk the vote used (0x49 has no count table; its law
    pins ``o + 20 + 2*n``).
    """
    spans = []
    for o, mk, _normal, counts, _refs, width in records:
        if mk == 0x49:
            spans.append((o, o + 20 + 2 * sum(counts)))
            continue
        hlen = header_len(data, o)
        has_normal = mk in NORMAL_MARKERS_ALL
        base = o + hlen + 4 + (12 if has_normal else 0)
        read = read_counts(data, base, len(counts), hi)
        clen = read[1] if read else 0
        spans.append((o, base + clen + width * sum(counts)))
    return spans


def parse_extended_facet_records(
    data, lo: int, hi: int, element_count=None, elements=None, shipped_spans=()
):
    """Every extended-header record in ``[lo, hi)`` under the 2026-11-18 law.

    Returns ``(records, candidates)``: ``candidates`` counts the
    extended-header positions (``ff`` at +5) and ``records`` the ones the
    law accepts. The loop count comes from the header (``b3 + b4``), not
    from a tiling search — the counts table is exactly that long (and
    stays a raw ``u8`` table: the P1g escape never fires on the corpus's
    12,376 candidates — #62's probe measured zero ``0xff`` count bytes).

    ``element_count`` (when known) bounds the references: an extended
    candidate whose refs leave the element space is NOT this family (a
    false-positive ``01 4x ... ff`` byte pattern), so it stays an
    unresolved candidate instead of failing the whole store on the refs
    gate. Every accepted record ends at or before the next facet header.

    The ref width is VOTED per record (#62, 2026-11-20; the corpus probe
    behind it measured w2 exact-tiling 2.1% vs w3 97.6% on the 19
    declined files — the family's refs are u24be on the big-element
    stores, while the small-space stores stay u16be): the candidates are
    width u8/u16be (plus u24be ONLY when ``element_count > 65,535`` —
    the same threshold the short-form width law uses, and a 2-byte ref
    cannot index larger spaces) ranked by **exact tiling** first
    (``end == nxt``; width-unambiguous for ``n > 0`` — ``nxt -
    refs_start == width * n`` has one solution), then refs in bounds,
    then the loop plane law (0x4f only — the only normal-carrying
    marker; tested when ``elements`` is passed, on dup-pinned
    coordinates for skip-bearing loops, the same battery as
    :func:`parse_strip_records`), then the narrower width. A candidate
    whose parse REPEATS a reference within a triangle/loop is
    DISQUALIFIED outright (the short-form law's misread detector: a
    narrow misread of a wider record repeats refs inside the loop, and a
    legitimate record never repeats — a repeated ref emits a degenerate
    triangle the emission battery declines anyway). The counts law
    (``n == 3*ty + sum(counts)``) is width-independent, so a candidate
    failing it under one width fails under all. A record whose winning
    candidate's refs leave the element space is declined as a whole (the
    false-positive rule above), so the accepted records never trip the
    store-level refs gate.

    CAASdd*Stiffener verification (2026-11-20, the #62 fix design's
    second probe; CORRECTED 2026-11-20 #64 — the analysis below ran on
    the FIRST list node's elem_decl 640 before the per-rep pairing was
    known to split this file into four stores; the 0x47/0x4f records
    there live in a store with elem_decl 116,471, u24be IS offered, and
    they exact-tile at w3 — see the #64 paragraph and
    ``_parse_escaped_extended_records``): the CAASddEditStiffener/
    CreateStiffener stores carry
    ``elem_decl`` 640, so u24be is never offered there — and their
    0x47/0x4f records exact-tile at NO width (only rec@4772007 and
    rec@4772268 tile, at w2, areas 531/464 m2 inside the store's 104.6 m
    exported-mesh bbox diag — kept, no area guard). The non-tiling
    records' u8 misreads stay in-bounds and used to win the rank on the
    in-bounds slot; the repeats disqualification above declines them
    (measured 50,779 m2 of km-scale garbage exported without it — the
    documented decline the ticket asks for: no exact tiling, area
    4-60x beyond bbox_diag^2).

    #64 (2026-11-20, the P1g-escaped header form): the CAASdd gap
    forensics measured a SECOND header form where ``ty``/``b3``/``b4``
    each escape via :func:`read_count` before the fixed ``ff`` —
    ``01 <mk> <ty@P1g> <b3@P1g> <b4@P1g> ff <u32le n> …`` — invisible to
    both discovery patterns when the fixed ``ff`` lands at +2 or +4 (the
    +3 shape rides the committed candidates this law used to skip on
    ``header_len != 6``). Corpus census: 202 candidates, 129 parse (the
    counts law passes on every one that reaches it), 75 exact-tile +
    in-bounds on 44 files. The escaped records join as a SECOND pass
    (this 6-byte pass is byte-identical to the pre-#64 behavior; overlap
    rejection keeps the passes from claiming the same bytes) with ONE
    rank difference: **repeats are RANKED, not disqualified** — their
    exact-tile records carry legitimate strip joins (114/453 loop groups
    on the CAASdd records), so the misread disqualification would
    decline 127 of the 129. Everything else is the same law: the winner's
    refs must resolve in-bounds, and the emission keeps the per-record
    ``_mesh_safe`` guard. The CAASdd runtime twin measured +8,847
    triangles per Stiffener file (manifold; used_vertex_fraction
    0.037 -> 0.076 / 0.076 -> 0.111); the head/frente files carry no
    escaped-form records (measured negative).

    #65 (2026-11-20, the counts-table reading chain + the exact-tiling
    exception): the top-10 MESH gap probe
    (``scripts/triage/probe_top10_mesh_gap_dump.py``) measured two
    further readings of the SAME 6-byte form. The povdoigt
    _NPart#194287 / SP02_ALPHA5_SEPA2_MINI_RESSORTS gap (2 records,
    46,835 B) carries a plain u8 header whose COUNTS TABLE escapes via
    :func:`read_counts` (16/211 and 22/220 counts are ``ff + u32le``) —
    the #62 raw-u8 counts law breaks the n-law on it (+6,951 / +9,755)
    and the #64 escaped pass skips ``hlen == 6`` candidates, so the
    record fell between the two passes. The CAAEwrFilter BundleSegment3
    gap (2 records + an open 0x43, 3,729 B) carries a **u16be counts
    table** (n-law exact: 767 = 3*18 + 713, 765 = 3*17 + 714). Both
    exact-tile at w2 in-bounds. The law therefore retries the SAME
    table as P1g counts, then as ``k`` u16be words, only when the u8
    reading fails the counts law (byte-identical for every store the
    #62 law handled), ranks repeats instead of disqualifying them on
    the fallback readings (the #64 semantic), and adds the
    exact-tiling exception: a width whose end runs past the next
    candidate header is viable only when the record ends exactly on a
    later candidate header — the internal STRIP_RE matches are the
    record's own ref bytes (the MINI_RESSORTS 0x4f pair sits inside the
    second 0x47's refs) — and swallows no already-accepted record
    (``shipped_spans`` + this law's own accepts). The committed u8
    path's semantics are provably unchanged: with ``end <= nxt`` the
    ``_nxt_eff`` boundary degenerates to ``nxt`` and no candidate can
    sit inside the span.
    """
    records = []
    candidates = 0
    hdrs = sorted(
        [m.start() for m in STRIP_RE.finditer(data, lo, hi)]
        + facet_headers(data, lo, hi)
    )
    widths = (1, 2, 3) if element_count is not None and element_count > 65_535 else (1, 2)
    skips = (
        {i for i, (_v, pt) in enumerate(elements) if pt is None}
        if elements is not None
        else None
    )
    accepted: list[tuple[int, int]] = []
    for i, o in enumerate(hdrs):
        if header_len(data, o) != 6:
            continue
        if any(a <= o < e for a, e in shipped_spans) or any(
            a <= o < e for a, e in accepted
        ):
            # #65 (2026-11-20): a candidate inside an already-accepted
            # record's span (a shipped short record, or an earlier
            # extended one) is a false-positive byte pattern in that
            # record's refs, not a record of its own.
            continue
        candidates += 1
        nxt = hdrs[i + 1] if i + 1 < len(hdrs) else hi
        mk = data[o + 1]
        if mk not in EXTENDED_HEADER_MARKERS:
            continue
        ty, b3, b4 = data[o + 2], data[o + 3], data[o + 4]
        k = b3 + b4
        has_normal = mk in EXTENDED_NORMAL_MARKERS
        base = o + 10 + (12 if has_normal else 0)
        normal = None
        if has_normal:
            normal = struct.unpack("<fff", data[o + 10 : o + 22])
        refs_start = base + k
        if refs_start > hi:
            continue
        n = int.from_bytes(data[o + 6 : o + 10], "little")

        def _nxt_eff(end):
            # The exact-tiling boundary past the internal false
            # positives (#65): the first candidate header at or after
            # ``end`` (hi when none). An ``end`` that IS a header is an
            # exact tile; the candidates strictly inside (o, end) are
            # the record's own ref bytes (its internal STRIP_RE
            # matches), not record boundaries.
            j = bisect.bisect_left(hdrs, end)
            return hdrs[j] if j < len(hdrs) else hi

        def _overlaps(end):
            # The exact-tiling exception must never swallow an
            # already-accepted record: the shipped short spans and this
            # law's own earlier accepts bound it.
            return any(o < e and a < end for a, e in shipped_spans) or any(
                o < e and a < end for a, e in accepted
            )

        def _vote(counts, refs_start, repeats_ranked):
            # The #62 width vote (exact tiling, in-bounds, repeats,
            # loop plane law, narrower width). ``repeats_ranked`` is
            # the #64 escaped law's semantic — repeats are legitimate
            # strip joins on the escaped-form family — so the committed
            # u8 reading keeps the misread disqualification while the
            # #65 fallback readings rank them; the emission keeps the
            # per-record ``_mesh_safe`` guard either way.
            best = None
            for width in widths:
                end = refs_start + width * n
                if end > hi:
                    continue
                if end > min(nxt, hi):
                    # #65: past the next candidate header only the
                    # exact-tiling exception is viable — the record ends
                    # exactly on a later candidate header, and swallows
                    # no accepted record.
                    if end != _nxt_eff(end) or _overlaps(end):
                        continue
                refs = [
                    int.from_bytes(
                        data[refs_start + width * j : refs_start + width * (j + 1)],
                        "big",
                    )
                    for j in range(n)
                ]
                repeats = False
                for start in range(0, 3 * ty, 3):
                    if len(set(refs[start : start + 3])) < 3:
                        repeats = True
                        break
                off = 3 * ty
                for c in counts:
                    if c > 0 and len(set(refs[off : off + c])) < c:
                        repeats = True
                        break
                    off += c
                if repeats and not repeats_ranked:
                    # The misread detector (the same signal the
                    # short-form width law ranks on): a narrow misread
                    # of a wider record repeats refs inside the loop,
                    # and a legitimate record never repeats (a repeated
                    # ref emits a degenerate triangle the battery
                    # declines anyway). The committed u8 reading keeps
                    # this disqualification.  Measured (#62
                    # CAASdd*Stiffener check): without it, the u8
                    # misreads of the non-tiling CAASddEditStiffener
                    # records win the rank on in-bounds (their narrow
                    # refs stay under the 640-element space) and the
                    # store exports 50,779 m2 of area outside its own
                    # 104.6 m bbox — km-scale garbage.
                    continue
                oob = (
                    any(r >= element_count for r in refs)
                    if element_count is not None
                    else False
                )
                nonplanar = 0
                if normal is not None and elements is not None:
                    off = 3 * ty
                    for c in counts:
                        loop = refs[off : off + c]
                        off += c
                        if not loop:
                            continue
                        if any(r >= len(elements) for r in loop):
                            continue
                        if any(r in skips for r in loop):
                            # The same gap-edge battery as the short
                            # records: a skip-bearing loop is tested on
                            # its dup-pinned coordinates; untestable
                            # loops stay silent.
                            pin = _dup_pin_map(elements, loop)
                            if pin is None:
                                continue
                            test = [pin.get(r, r) for r in loop]
                        else:
                            test = loop
                        st, _dev = _loop_plane_status(test, normal, elements)
                        if st == "nonplanar":
                            nonplanar += 1
                rank = (
                    0 if end == _nxt_eff(end) else 1,
                    1 if oob else 0,
                    1 if repeats else 0,
                    nonplanar,
                    width,
                )
                if best is None or rank < best[0]:
                    best = (rank, tuple(refs), width, end, tuple(counts))
            return best

        # The counts-table reading chain (#65, 2026-11-20). The
        # committed u8 reading (the #62 law) runs first and alone on
        # every candidate it covers — every store the #62 law handled
        # keeps its exact parse. A candidate whose u8 table fails the
        # counts law retries the SAME table as P1g counts (u8 or
        # ``ff + u32le`` — the #64 encoding; the povdoigt _NPart#194287/
        # MINI_RESSORTS gap records carry 16/211 and 22/220 escaped
        # counts and exact-tile at w2 under it), then as ``k`` u16be
        # words (the BundleSegment3 gap records: the table IS 2-byte
        # big-endian there — n-law exact at 767 = 3*18 + 713). The
        # fallback variants join with repeats RANKED and the same
        # gates (in-bounds refs, emission ``_mesh_safe``).
        counts_u8 = tuple(data[base:refs_start])
        best = None
        if n == 3 * ty + sum(counts_u8):
            best = _vote(counts_u8, refs_start, repeats_ranked=False)
        if best is None:
            read = read_counts(data, base, k, hi)
            if read is not None:
                counts_p1g, clen = read
                counts_p1g = tuple(counts_p1g)
                if n == 3 * ty + sum(counts_p1g):
                    best = _vote(counts_p1g, base + clen, repeats_ranked=True)
        if best is None and base + 2 * k <= hi:
            counts16 = tuple(
                int.from_bytes(data[base + 2 * j : base + 2 * j + 2], "big")
                for j in range(k)
            )
            if n == 3 * ty + sum(counts16):
                best = _vote(counts16, base + 2 * k, repeats_ranked=True)
        if best is None:
            continue
        _rank, refs, width, end, counts = best
        if element_count is not None and any(r >= element_count for r in refs):
            # The winning parse's refs leave the element space: not this
            # family (the false-positive rule; the record stays
            # unresolved instead of tripping the store-level refs gate).
            continue
        records.append(
            ExtendedFacetRecord(
                offset=o,
                marker=mk,
                triangles=ty,
                strips=b3,
                polygons=b4,
                counts=counts,
                refs=refs,
                end=end,
                normal=normal,
                width=width,
            )
        )
        accepted.append((o, end))
    # #64 (2026-11-20): the P1g-escaped header form joins as a SECOND
    # pass over the same span — the 6-byte form's candidates, boundaries
    # and rank above are byte-identical to the pre-#64 behavior, so every
    # store the #62 law handled keeps its exact parse; the escaped-form
    # records only fill the gaps (candidates whose header bytes escape
    # via read_count, invisible to the 6-byte discovery and declined by
    # its raw-u8 counts law). Overlap rejection keeps both passes from
    # claiming the same bytes.
    escaped, escaped_candidates = _parse_escaped_extended_records(
        data, lo, hi, hdrs, element_count, elements, records
    )
    if escaped:
        records = sorted(records + escaped, key=lambda r: r.offset)
    return records, candidates + escaped_candidates


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
    0x42/0x49/0x4a strips use the sliding window with the odd-triangle
    winding flip (0x49 enters as a triangle list — its reader emits
    three-ref loops, :func:`parse_049_record`); degenerate triangles
    (repeated coordinates, or the exactly-zero cross product on strips,
    G3 F7) are skipped and counted.

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


def _dup_pin_map(elements, loop):
    """The dup-pin weld targets for one loop — ``{skip_slot: written
    element}`` for every referenced skip slot — or ``None`` when a
    referenced skip slot has no preceding written element (unpinnable:
    the weld's fail-closed arm).

    The U4-D dup law (ported from the stage-4a decoder's ``dup_prev``,
    decode_curve_entries.py — not re-derived): a loop-referenced skip
    slot carries the bit-exact coordinates of the written vertex of its
    immediately preceding written element (the per-face copy — no new
    vertices)."""
    pin: dict[int, int] = {}
    for r in loop:
        if elements[r][1] is not None:
            continue
        j = r - 1
        while j >= 0 and elements[j][1] is None:
            j -= 1
        if j < 0:
            return None
        pin[r] = j
    return pin


def _edge_key(a, b):
    """The undirected edge key (the mesh-stat edge histogram's key)."""
    return (a, b) if a <= b else (b, a)


def _edge_uses(triangles):
    """Undirected edge-use histogram of a triangle list (the mesh
    invariant's key; ``manifold`` == every value <= 2)."""
    uses: dict[tuple[int, int], int] = {}
    for tri in triangles:
        a, b, c = tri
        for key in (_edge_key(a, b), _edge_key(b, c), _edge_key(c, a)):
            uses[key] = uses.get(key, 0) + 1
    return uses


def _mesh_safe(edge_uses, tris):
    """The incremental manifold guard (2026-11-18) — ONE topology lever.

    True when adding ``tris`` keeps every undirected edge at two uses or
    fewer, in which case the edges are folded into ``edge_uses``.  The
    dup-pin weld (:func:`_e0b_dup_pin`), the extended-header emission
    and the primary-loop seam (:func:`_triangulate`) share this single
    check; a refused unit leaves the histogram untouched (fail-closed,
    deterministic in record/loop order).  ``False`` means the unit would
    tip the assembled mesh past the G3 manifold invariant."""
    candidate = _edge_uses(tris)
    if any(edge_uses.get(edge, 0) + n > 2 for edge, n in candidate.items()):
        return False
    _fold_edge_uses(edge_uses, candidate)
    return True


def _fold_edge_uses(edge_uses, candidate):
    """Fold one unit's edge-use histogram into the assembled one (the
    accept arm of :func:`_mesh_safe`).  The primary seam also uses it for
    an over-use loop it deliberately keeps (the large-loop arm)."""
    for edge, n in candidate.items():
        edge_uses[edge] = edge_uses.get(edge, 0) + n


def _triangle_area(tri, points):
    """One triangle's area from the written points (mm²)."""
    a, b, c = points[tri[0]], points[tri[1]], points[tri[2]]
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    cx = uy * vz - uz * vy
    cy = uz * vx - ux * vz
    cz = ux * vy - uy * vx
    return 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)


def _loop_area(tris, points):
    """A candidate loop's area (the sum over its emitted triangles)."""
    return sum(_triangle_area(tri, points) for tri in tris)


def _mesh_area(triangles, points):
    """The assembled mesh's area — the primary seam's reference (the
    store-level mesh area, so the rule is order-independent)."""
    return sum(_triangle_area(tri, points) for tri in triangles)


# The primary-loop seam's keep threshold (2026-11-18, #34).  A refused
# candidate loop is dropped only when its area is at most this fraction
# of the assembled mesh's area (the store-level mesh area: the guard is
# order-independent and per-rep stores compare against the whole part,
# not one rep).  A larger loop is real surface and is kept as today (the
# over-use is named, never hidden).
#
# Measured on the 24 not-manifold corpus parts: the refused loops split
# at 0.76% / 2.92% (largest declined 0.7599% = d4127e6b, the held-out
# row; smallest kept 2.9175% = 26504a08), so 1% sits in the measured
# gap and yields the 15/9 split the ticket's targets require.  The
# ticket's 0.1% was measured too and does not reproduce its own target:
# 0.1% of the store area flips 11/24 (the held-out row needs 0.7599%)
# and 0.1% of the running area flips 3/24 (an early duplicate loop is
# 100% of its rep's area but 0.003% of the part) — docs/evidence/
# 2026-11-18-primary-emit-seam.md section 3.
PRIMARY_LOOP_AREA_REL = 1e-2

# The entry-point sentinel of :func:`decode_composite_store`: unset means
# "run the registry pass first, then the guarded pass with the measured
# store area"; ``None`` disables the seam (the registry pass);
# a float is the reference area.
_SEAM_UNSET = object()


def _e0b_dup_pin(elements, points, written_rank, dropped, triangles):
    """The dup-pin weld, evaluated PER LOOP behind a mesh guard
    (2026-11-18, #34).

    Each dropped loop is welded independently when it is

    1. fully pinnable — every referenced skip slot has a preceding
       written element (:func:`_dup_pin_map`), and
    2. battery-supported — the record carries no normal, or the
       dup-pinned coordinates are coplanar against it at
       :data:`PLANE_TOL` (:func:`_loop_plane_status`; the real corpus
       loops measure <= 1.4e-6, the width-misparsed ones 2e-2..8), and
    3. mesh-safe — its triangles contain no degenerate emission
       (:func:`_loop_triangles`' skip convention) and adding them keeps
       the assembled mesh MANIFOLD: no undirected edge would exceed two
       uses (``triangles`` is the primary mesh already emitted by this
       call; previously welded loops are folded in as they are
       accepted).

    The guard is incremental — O(the loop's triangles) per loop, with
    the edge histogram built once from the primary mesh — and
    fail-closed: a rejected loop leaves the histogram untouched and
    stays dropped.  The loop order is the records'/dropped order, so
    the accepted set is deterministic.  It is what keeps a weld from
    tipping a passing store's L2 row: the 26 non-manifold regressions
    of the 2026-11-18 full-corpus A/B were exactly welded loops whose
    boundary edges already had two uses in the surviving primary mesh.

    A loop failing any test stays dropped on the conservative rule; it
    does not veto another loop's weld, and the decision no longer
    depends on the store's primary mesh being empty (the 2026-11-18
    surface-loss fix: the empty-mesh precondition hid 10 droppable
    loops / 3,097 mm² on labios/main behind a non-empty 4,261-triangle
    primary mesh).

    Returns ``{"triangles", "degenerate", "loops", "refused"}``: the
    welded loops' triangles (written-rank indexed), the degenerate
    count, the welded-loop count and the refused-loop count."""
    welded_triangles = []
    degenerate = 0
    welded = 0
    refused = 0
    edge_uses = _edge_uses(triangles)
    for mk, normal, loop in dropped:
        pin = _dup_pin_map(elements, loop)
        if pin is None:
            refused += 1
            continue
        resolved = [pin.get(r, r) for r in loop]
        if normal is not None:
            status, _dev = _loop_plane_status(resolved, normal, elements)
            if status != "coplanar":
                refused += 1
                continue
        tris, deg = _loop_triangles(
            mk, [written_rank[r] for r in resolved], points
        )
        if deg:
            # Fail-closed: a degenerate emission means the pinned loop
            # is not a clean facet — do not weld it.
            refused += 1
            continue
        # Incremental manifold guard (the shared _mesh_safe lever): any
        # edge the candidate loop would push past two uses rejects the
        # whole loop (no partial weld).
        if not _mesh_safe(edge_uses, tris):
            refused += 1
            continue
        welded_triangles += tris
        degenerate += deg
        welded += 1
    return {
        "triangles": welded_triangles,
        "degenerate": degenerate,
        "loops": welded,
        "refused": refused,
    }


def _triangulate(elements, records, extended=(), seam_area=None):
    """Triangles under the identity mapping (strip/polygon semantics).

    Loop references are 0-based element indices; triangles index the
    WRITTEN points (the exported vertex list), so referenced elements
    are remapped through the written rank.  Loops referencing skip
    slots (curve entries — their coordinates live in the curve records,
    U4) are evaluated per loop by the dup-pin weld
    (:func:`_e0b_dup_pin`, 2026-11-18): a loop that is fully pinnable and
    battery-supported (its record carries no normal, or the dup-pinned
    coordinates are coplanar at :data:`PLANE_TOL`) and mesh-safe (its
    triangles keep the assembled mesh manifold, no degenerate emission)
    exports with its skip
    slots welded to the written vertex of the immediately preceding
    written element (no new vertices); every other loop stays dropped
    under the conservative rule, which names the gap instead of guessing
    coordinates.  The decision is per loop — it never depends on the
    store's primary mesh being empty, and the incremental edge-use guard
    is the topology check the coplanarity battery cannot make.  Strip
    triangles (0x42/0x49/0x4a) skip the degenerate ones (repeated
    coordinates or exactly-zero cross product, G3 F7); polygon fans
    (0x4c) skip repeated coordinates.  The 0x49 triangle-list family is
    admitted on these exact terms (2026-11-18): its own pinned reader
    (no count table, u16be refs, n == 3*ty) feeds the same per-loop
    emission, so a skip-bearing 0x49 loop faces the same weld battery
    and manifold guard as every other marker.

    ``extended`` carries the extended-header records
    (:class:`ExtendedFacetRecord`, 2026-11-18): their ``ty`` independent
    triangles first (each is one triangle, not a loop — the loop counters
    exclude them), then the loops the counts delimit — the first
    ``strips`` loops under the 0x42 strip law, the last ``polygons``
    loops under the 0x4c fan law. The family's geometry was the one
    emission outside a structural check (the 2026-11-18 review: 9 carrier
    parts flipped to not-manifold), so each record is emitted ONLY when
    its triangles keep the assembled mesh manifold (:func:`_mesh_safe` —
    the same lever as the weld) and its emission carries no degenerate
    triangle (the G3 F7 skip convention makes any degenerate emission an
    L2 failure). A record failing either test is declined as a whole,
    counted in ``extended_declined``, and its skip-bearing loops stay
    dropped; skip-slot references of an accepted record follow the same
    conservative curve-entry rule as the short records.

    The primary-loop seam (2026-11-18, #34): each short record's loop is
    emitted behind the same incremental guard, made fidelity-neutral by
    an area rule — a loop the guard refuses is dropped only when its
    area is <= :data:`PRIMARY_LOOP_AREA_REL` (1%) of ``seam_area``, the
    store-level assembled mesh's area (a sliver over-using an edge); a
    larger over-use is kept exactly as before (never drop real surface),
    counted in ``primary_loop_kept``.  ``seam_area=None`` disables the
    seam — the registry pass :func:`decode_composite_store` runs first to
    measure the store's area (the guard is order-independent and
    per-rep stores compare against the whole part, not one rep).  A kept
    over-use's edges are folded in, so later loops see the same
    over-used histogram today's unguarded emission produced.  The
    skipped slivers are counted in ``primary_loop_skips``; the two
    counters and the warning classes ``primary-loop-manifold-skip`` /
    ``primary-loop-manifold-kept`` name both outcomes
    (docs/evidence/2026-11-18-primary-emit-seam.md).

    Returns ``(triangles, degenerate, stats)`` where ``stats`` carries
    the loop counters for the summary's composite block (plus the
    ``dup_pin`` block exactly when at least one dropped loop was
    evaluated; consumers pop it before assembling ``info``, offset it
    per rep and merge the welded loops; the two primary-seam counters
    ride ``stats`` and are summed per rep by the multi-rep paths).
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
    extended_triangles = 0
    primary_skips = 0
    primary_kept = 0
    edge_uses: dict[tuple[int, int], int] = {}
    dropped = []

    def emit(kind, normal, loop, count_loop=True):
        nonlocal degenerate, loops_exported, loops_curve_entry
        nonlocal primary_skips, primary_kept
        if not loop:
            return
        if any(r in skips for r in loop):
            loops_curve_entry += 1
            dropped.append((kind, normal, loop))
            return
        if count_loop:
            loops_exported += 1
        idxs = [written_rank[r] for r in loop]
        tris, deg = _loop_triangles(kind, idxs, points)
        degenerate += deg
        area = _loop_area(tris, points)
        # The primary-loop seam (2026-11-18, #34): the same incremental
        # manifold guard the weld and the extended family use, made
        # fidelity-neutral by the area rule — a refused loop is dropped
        # only when it is <= PRIMARY_LOOP_AREA_REL of the store mesh's
        # area (a sliver over-using an edge); a larger over-use is real
        # surface and is kept as before, counted and named.
        if not _mesh_safe(edge_uses, tris):
            if seam_area is not None and area <= PRIMARY_LOOP_AREA_REL * seam_area:
                primary_skips += 1
                return
            primary_kept += 1
            _fold_edge_uses(edge_uses, _edge_uses(tris))
        triangles.extend(tris)

    for _off, mk, normal, counts, refs, _w in records:
        if mk not in EXPORTED_SHORT_MARKERS:
            continue
        o = 0
        for c in counts:
            emit(mk, normal, refs[o : o + c])
            o += c

    extended_declined = 0
    for rec in extended:
        rec_triangles = []
        rec_degenerate = 0
        rec_loops = 0
        rec_dropped = []
        for j in range(0, 3 * rec.triangles, 3):
            loop = rec.refs[j : j + 3]
            if any(r in skips for r in loop):
                rec_dropped.append((0x42, rec.normal, loop))
                continue
            idxs = [written_rank[r] for r in loop]
            tris, deg = _loop_triangles(0x42, idxs, points)
            rec_triangles += tris
            rec_degenerate += deg
        o = 3 * rec.triangles
        for index, c in enumerate(rec.counts):
            loop = rec.refs[o : o + c]
            o += c
            if not loop:
                continue
            kind = 0x42 if index < rec.strips else 0x4C
            if any(r in skips for r in loop):
                rec_dropped.append((kind, rec.normal, loop))
                continue
            idxs = [written_rank[r] for r in loop]
            tris, deg = _loop_triangles(kind, idxs, points)
            rec_triangles += tris
            rec_degenerate += deg
            rec_loops += 1
        if rec_degenerate == 0 and _mesh_safe(edge_uses, rec_triangles):
            triangles += rec_triangles
            degenerate += rec_degenerate
            loops_exported += rec_loops
            loops_curve_entry += len(rec_dropped)
            dropped += rec_dropped
            extended_triangles += len(rec_triangles)
        else:
            extended_declined += 1
            loops_curve_entry += len(rec_dropped)

    # The T3 relaxed families (#61): a SECOND pass over the same records,
    # so the base pass's outcome is bit-identical to the pre-T3 behavior
    # (the relaxed loops never touch the base pass's edge budget).  Each
    # relaxed loop enters only under the STRICT mesh guard — no
    # seam-area exception — so every fold keeps every edge at <= 2 uses
    # and a base-manifold mesh stays manifold by construction.
    relaxed_accepted = 0
    relaxed_declined = 0
    for _off, mk, normal, counts, refs, _w in records:
        if mk not in RELAXED_SHORT_MARKERS:
            continue
        o = 0
        for c in counts:
            loop = refs[o:o + c]
            o += c
            if not loop:
                continue
            if any(r in skips for r in loop):
                loops_curve_entry += 1
                dropped.append((mk, normal, loop))
                continue
            loops_exported += 1
            idxs = [written_rank[r] for r in loop]
            tris, deg = _loop_triangles(mk, idxs, points)
            if deg:
                # The extended-family precondition: a loop carrying a
                # degenerate emission is declined WHOLE and its skip is
                # never counted — the L2 law treats any skipped
                # degenerate as anomalous (G3 F7 rate 0 on clean stores),
                # so the corpus invariant degenerate_triangle_count == 0
                # on passing parts is preserved by construction.
                relaxed_declined += 1
                continue
            if _mesh_safe(edge_uses, tris):
                triangles.extend(tris)
                _fold_edge_uses(edge_uses, _edge_uses(tris))
                relaxed_accepted += 1
            else:
                relaxed_declined += 1

    stats = {
        "loops_exported": loops_exported,
        "loops_curve_entry": loops_curve_entry,
    }
    if primary_skips:
        stats["primary_loop_skips"] = primary_skips
    if primary_kept:
        stats["primary_loop_kept"] = primary_kept
    if extended:
        stats["extended_triangles"] = extended_triangles
        stats["extended_declined"] = extended_declined
    if relaxed_accepted or relaxed_declined:
        stats["relaxed_loops_accepted"] = relaxed_accepted
        stats["relaxed_loops_declined"] = relaxed_declined
    if dropped:
        stats["dup_pin"] = _e0b_dup_pin(
            elements, points, written_rank, dropped, triangles
        )
    return triangles, degenerate, stats


# --- stage 15: the unordered-triangle dedup law (the stage-14 review
# F1 family, owner-authorized 2026-11-13, #34) ---------------------------
#
# The mechanism (review F1, byte-verified): the same three ELEMENT
# indices emitted twice — from two different records 13-42 B apart in
# the same rep (6 corpus stores), from two loops of one record
# (b912cbef, ef61cfc2), or from two records in the same order
# (1d256d12, the ordered case the stage-14 child's detector saw) — the
# writer re-listed the facet; territory overlap 0 (two parses never).
# The second copy's winding is opposite (the plane normals are exact
# opposites), so the pair over-uses nothing TOGETHER — each shared edge
# is used once per copy — but every edge shared with the surrounding
# mesh counts the extra use, and the corpus stores' over-edges resolve
# when the later copy is dropped.
#
# The identity is COORDINATE identity (2026-11-18, #34): two triangles
# are the same facet when their three VERTEX POSITIONS are identical as
# an unordered triple.  An index triple is only a same-rep spelling —
# the per-rep decomposition keeps each rep's element space disjoint, so
# a rep that re-lists an earlier rep's facet necessarily writes
# DIFFERENT indices for it, and an index-keyed pass cannot see that
# copy at all (545707b9: 67 index duplicates in one rep plus 451
# coordinate duplicates re-listed by a later rep — the index pass
# declines, 212 over-edges stay; docs/evidence/
# 2026-11-18-coordinate-duplicate-dedup.md).  Coordinate identity is
# also what makes the drop AREA-PRESERVING by construction: the area of
# a triangle is a pure function of its three vertex positions, so a
# dropped copy can never remove surface the kept copy does not already
# carry (the same three points, one copy).
#
# The keeper is the copy from the EARLIEST emission unit: the rep-space
# rank of its first vertex (``space_offsets`` — ties by list order).  A
# rep's welded loops (stage-10 dup-pin) carry that rep's point base, so
# they belong to that rep's unit even though they are appended after
# every rep's primary loops; the earlier rep's listing therefore always
# wins over a later rep's re-listing.  Emission ORDER alone is not the
# rule: the welded triangles are appended last, so ordering by position
# would hand a re-listed facet to the later rep and leave the earlier
# rep's mesh split (545707b9 measures exactly that: position-order
# keeps 329 of the later rep's copies and the mesh stays not-manifold).
#
# Fail-closed fire gate (the law applies ONLY where it resolves the
# store's over-use — the stage-14 measured yield is 8 dev full-gate
# flips + b912cbef's fail-class change): the emitted mesh must be NOT
# manifold (an over-use) AND the deduplicated list must be manifold.
# A manifold (passing) store is never touched — its row must not
# change; a not-manifold store whose duplicates do NOT resolve the
# over-use keeps its exact emitted triangles (the L2 gate names
# not-manifold) and the declined dedup is named on the summary.
# Degenerate triangles never enter the list (skipped at emission and
# counted separately — b912cbef's 3 pre-existing skips are a SEPARATE
# gate check); a repeated-index triple is never deduped regardless.
# ``space_offsets`` empty means one index space (the single-rep paths):
# every copy ranks equal and list order decides.


def _apply_unordered_dedup(triangles, info, points=None, space_offsets=()):
    """The unordered-triangle dedup at one store's assembled mesh.

    Two triangles are the same facet when their vertex COORDINATES are
    identical as an unordered triple (``points`` is the store's written
    point list, the coordinates the triangles index); the later
    emission unit's copy is dropped, so an earlier rep's listing keeps
    the facet and a later rep that re-lists it loses the copy.  The
    drop is area-preserving by construction: identical coordinates mean
    identical triangle area, and exactly one copy of the facet survives.
    With ``points=None`` the index triple is the key (the same headline
    behavior inside one index space).

    Returns the triangle list to export — unchanged unless the law
    fires — and records the outcome on ``info``:
    ``unordered_dedup_dropped`` (fired: N later duplicate copies
    dropped, the mesh is manifold) or ``unordered_dedup_declined``
    (fired and declined: N duplicates found, removal leaves the mesh
    not-manifold, the emitted list is kept verbatim).  Both keys are
    additive (consumers ignore unknown properties).
    """
    if len(triangles) < 2 or mesh.mesh_stats(list(triangles)).manifold:
        return triangles
    starts = tuple(space_offsets)
    keyed: list[tuple | None] = []
    best: dict[tuple, tuple[int, int]] = {}
    for pos, tri in enumerate(triangles):
        if tri[0] == tri[1] or tri[1] == tri[2] or tri[0] == tri[2]:
            keyed.append(None)  # degenerate-shaped: never deduped
            continue
        if points is None:
            key = tuple(sorted(tri))
        else:
            key = tuple(sorted((points[i] for i in tri)))
        rank = bisect.bisect_right(starts, min(tri)) - 1 if starts else 0
        keyed.append(key)
        incumbent = best.get(key)
        if incumbent is None or (rank, pos) < incumbent:
            best[key] = (rank, pos)
    keep = {pos for _rank, pos in best.values()}
    kept = [
        tri
        for pos, tri in enumerate(triangles)
        if keyed[pos] is None or pos in keep
    ]
    dropped = len(triangles) - len(kept)
    if not dropped:
        return triangles
    if mesh.mesh_stats(kept).manifold:
        info["unordered_dedup_dropped"] = dropped
        return kept
    # The duplicates do not explain the over-use (fins/coplanar residue
    # alongside): fail-closed — keep the emitted list, name the gap.
    info["unordered_dedup_declined"] = dropped
    return triangles


def decode_composite_store(
    data, span, groups, kinds, allow_unrouted_elements=False, *, _seam_area=_SEAM_UNSET
):
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

    Stage-13 second-chance element-space route (2026-11-13, #34):
    ``allow_unrouted_elements`` skips ONLY the marker-routing check
    below.  It is set by ``export._export_store``'s clean-path failure
    points (the no-pool raise and the refs-beyond raise) for stores
    whose body carries a token-bearing list node: the stage-13 finding
    is that the element space beyond the pool IS the list node's point
    region — the composite structure without the ``01 02`` edge group
    / ``ff ..`` opener markers (docs/evidence/
    2026-11-13-stage13-elementspace.md sections 2-3) — so the routing
    predicate was the only blocker.  Every other gate (layout,
    walk-exact, absorption, per-rep, the M2b refs gate,
    triangulation) is unchanged; on any failure the caller re-raises
    the ORIGINAL clean-path error.

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

    Stage-10 dup-pin weld (2026-11-12, #34; PER LOOP from 2026-11-18,
    #34 — the surface-loss fix): on every exported path, a dropped
    curve-entry loop exports when it is fully pinnable (:func:`_e0b_dup_pin`
    — each skip slot welded to the written vertex of its immediately
    preceding written element, no new vertices), battery-supported
    (its record carries no normal, or the dup-pinned coordinates are
    coplanar at :data:`PLANE_TOL`) AND mesh-safe (its triangles contain
    no degenerate emission and keep the assembled mesh manifold — the
    incremental edge-use guard).  The decision is independent per
    loop and no longer depends on the store's primary mesh being empty;
    a refused or unpinnable loop keeps the conservative non-export rule
    and its warning without vetoing the others.  The U4-M mid law stays
    unsupported and is not implemented.

    Stage-15 unordered-triangle dedup law (2026-11-13, #34; the
    stage-14 review F1 family, owner-authorized; COORDINATE identity
    added 2026-11-18): a store whose ASSEMBLED MESH (the emission it
    actually exports, after the primary seam's decision) is NOT
    manifold and whose triangle list carries duplicate UNORDERED
    triples drops the later copies when — and only when — the
    deduplicated list is manifold (:func:`_apply_unordered_dedup`; a
    store whose duplicates do not resolve the over-use keeps its exact
    emitted triangles with the declined dedup named).  A duplicate is
    the same three vertex POSITIONS (a facet the writer re-listed from
    a second record/loop with opposite winding, or that a later rep
    re-listed in its own disjoint element space); an index triple alone
    only proves the same-rep case.  The drop is area-preserving by
    construction — identical coordinates mean identical triangle area,
    and exactly one copy of the facet survives.  The law runs once, at
    the entry (``decode_composite_store``), on every path — the mesh
    the store exports is the one the fire gate must see, and running it
    after the seam keeps the seam's committed surface trade untouched.
    The raw-array path carries the same gate (it triangulates records);
    measured corpus incidence 0.

    Primary-emit seam (2026-11-18, #34; docs/evidence/
    2026-11-18-primary-emit-seam.md): the short records' primary loops
    are the one emission that had no manifold guard.  The entry point
    runs the decode twice — a registry pass with the seam off measures
    the store mesh's area, then the guarded pass drops only the refused
    loops whose area is <= :data:`PRIMARY_LOOP_AREA_REL` (1%) of it,
    keeping every larger over-use as today.  The reference is the
    store-level area, so the rule is order-independent and a per-rep
    store's sliver is compared against the whole part (a duplicate loop
    can be 100% of its rep and 0.003% of the part).  The seam stands only
    when it RESOLVES the store's over-use: after the slivers are out the
    mesh must be manifold, otherwise the pre-seam emission is returned
    unchanged and the decline named (:func:`decode_composite_store`'s
    fire gate, the dedup law's discipline).
    """
    if _seam_area is _SEAM_UNSET:
        # The registry pass: decode with the seam off, measure the
        # assembled mesh's area, then re-decode with the seam armed.
        # Deterministic (same input, same walk); the cost is the one
        # extra triangulation of already-parsed records.
        points, triangles, degenerate, info = decode_composite_store(
            data,
            span,
            groups,
            kinds,
            allow_unrouted_elements=allow_unrouted_elements,
            _seam_area=None,
        )
        base_offsets = info.pop("_space_offsets", ())
        area = _mesh_area(triangles, points)
        seam_points, seam_triangles, seam_degenerate, seam_info = (
            decode_composite_store(
                data,
                span,
                groups,
                kinds,
                allow_unrouted_elements=allow_unrouted_elements,
                _seam_area=area,
            )
        )
        seam_offsets = seam_info.pop("_space_offsets", ())
        skipped = seam_info.get("primary_loop_skips", 0)
        if skipped and not mesh.mesh_stats(list(seam_triangles)).manifold:
            # The seam fires ONLY where it resolves the store's over-use
            # (the same fail-closed discipline as the dedup law): a
            # store whose mesh is still not manifold after the slivers
            # are out keeps its exact pre-seam emission — no surface is
            # lost for no L2 gain.  The decline is named.
            info["primary_loop_seam_declined"] = skipped
            if seam_info.get("primary_loop_kept"):
                info["primary_loop_kept"] = seam_info["primary_loop_kept"]
            offsets = base_offsets
        else:
            points, triangles, degenerate, info = (
                seam_points,
                seam_triangles,
                seam_degenerate,
                seam_info,
            )
            offsets = seam_offsets
        # Stage-15 unordered-triangle dedup (see _apply_unordered_dedup):
        # applied to the mesh the store ACTUALLY exports (the seam's
        # decision above is unchanged, so its committed surface trade
        # stands) — fires only on a not-manifold assembled mesh whose
        # duplicate unordered triples (COORDINATE identity across the
        # store's disjoint index spaces) resolve it, so a passing
        # store's mesh is never touched.
        triangles = _apply_unordered_dedup(triangles, info, points, offsets)
        return points, triangles, degenerate, info
    seam_area = _seam_area
    lo, hi = span.body_lo, span.body_hi
    if not allow_unrouted_elements and not any(
        k == b"\x01\x02" or k[:1] == b"\xff" for k in kinds
    ):
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
            return _decode_raw_array(
                data, lo, hi, groups, payload, elem_decl, seam_area=seam_area
            )
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
            return _decode_mixedwrite(data, lo, hi, groups, seam_area=seam_area)
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
        return _decode_per_rep(
            data, lo, hi, groups, len(missing), len(pool_set), seam_area=seam_area
        )

    records, n_hdrs = parse_strip_records(
        data, lo, hi, elem_decl, elements=elements
    )
    # Refs are 0-based element indices: every gated family's references
    # must resolve inside the element space (the exported markers plus
    # the normal-carrying 0x49, the stage-2c gate set). The extended-header
    # family (2026-11-18) indexes the same space, so its refs are gated
    # too.
    extended, ext_candidates = parse_extended_facet_records(
        data,
        lo,
        hi,
        elem_decl,
        elements=elements,
        shipped_spans=_short_record_spans(data, lo, hi, records),
    )
    all_refs = [r for _o, mk, _n, _c, refs, _w in records if mk in GATED for r in refs]
    all_refs += [r for rec in extended for r in rec.refs]
    if all_refs:
        mx = max(all_refs)
        if mx >= elem_decl:
            raise ExportError(
                "undecoded-variant",
                f"facet references beyond the element space: max ref {mx} "
                f">= element count {elem_decl} (refs are 0-based element "
                "indices in region order, M2b identity; G3 open question 2)",
            )

    triangles, degenerate, loop_stats = _triangulate(
        elements, records, extended=extended, seam_area=seam_area
    )
    # The dup-pin weld (2026-11-18, per loop): ``_triangulate`` already
    # evaluated every dropped loop independently (fully pinnable,
    # battery-supported and mesh-safe).  Merge the welded loops; the
    # ones the battery or the mesh guard refused stay counted as
    # dropped.  The old empty-primary-mesh precondition is gone.
    dup_pin = loop_stats.pop("dup_pin", None)
    curve_entry_law = 0
    if dup_pin is not None and dup_pin["loops"]:
        triangles = triangles + dup_pin["triangles"]
        degenerate += dup_pin["degenerate"]
        loop_stats["loops_exported"] += dup_pin["loops"]
        loop_stats["loops_curve_entry"] -= dup_pin["loops"]
        curve_entry_law = dup_pin["loops"]

    skipped_markers: dict[int, int] = {}
    for _o, mk, _n, _c, _refs, _w in records:
        if mk not in EXPORTED_SHORT_MARKERS and mk not in RELAXED_SHORT_MARKERS:
            skipped_markers[mk] = skipped_markers.get(mk, 0) + 1

    # The extended records' counters ride their own summary keys (the
    # soup triples are not loops; the declined records are named).
    ext_triangles = loop_stats.pop("extended_triangles", 0)
    ext_declined = loop_stats.pop("extended_declined", 0)
    info = {
        "stage": "identity-table-walk",
        "element_decl": elem_decl,
        "node_points": len(points),
        "curve_entries": skip_slots,
        "write_count": region_info["write_count"],
        "table_bytes": region_info["table_bytes"],
        "facet_candidates": n_hdrs + ext_candidates,
        "facet_records": len(records) + len(extended),
        "skipped_markers": skipped_markers,
        # stage-5 fold-in (reconciliation note section 5): the list
        # node's payload byte length — lets big/small form be derived
        # from summaries/CSVs (big > 4096 B).
        "node_bytes": len(payload),
        **loop_stats,
    }
    if extended:
        info["extended_header_records"] = len(extended)
        info["extended_header_triangles"] = ext_triangles
        if ext_declined:
            info["extended_header_declined"] = ext_declined
    if curve_entry_law:
        info["curve_entry_law"] = "e0b-dup-pin"
        info["loops_curve_entry_exported"] = curve_entry_law
    # The index spaces this emission indexes (one, on this path): the
    # stage-15 dedup's keeper rule needs them at the assembled mesh
    # (:func:`decode_composite_store` pops the key and applies the law
    # there — the mesh the store actually exports).
    info["_space_offsets"] = (0,)
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


def _rep_node_positions(scanned, groups):
    """Pair each pool group with its rep node (2026-11-18, #50 B3).

    The measured corpus law: the pool wrapper FOLLOWS its rep's list
    node — the rep node is the last token-bearing list node before the
    group's wrapper.  Measured over the 1,036 located composite stores
    (1,442 manifest parts, read-only scan): 2,175 ``01 06`` pool
    groups, ALL of them with a preceding token node; that node absorbs
    the group on 2,149 of 2,175 (the 26 misses are partial/unexported
    reps, named per rep, not pairing failures).  The first node AFTER
    the wrapper absorbs 2 of 1,186 and in both cases the preceding
    node absorbs too, so "after" is never the reading — there is no
    pool-first fallback.  A node already claimed by an earlier group
    cannot re-list a second pool: the later group gets ``None``
    (ambiguous → fail-closed).  Pre-rep token nodes (the
    assembly/scene-graph nodes a recovered container can carry before
    the rep sequence) are simply not the last node before any group.
    """
    positions = []
    claimed = set()
    order = [pos for pos, _p, _c1, _c2 in scanned]
    for g in groups:
        before = [pos for pos in order if pos < g.offset]
        node = before[-1] if before else None
        if node in claimed:
            node = None
        if node is not None:
            claimed.add(node)
        positions.append(node)
    return positions


def _decode_rep_node(payload, element_count, poolv):
    """One rep node under the per-rep law ladder (2026-11-18, #50 B3).

    The committed table layout (:func:`decode_region`) is tried first,
    so every rep the per-rep path already decoded keeps that exact
    reading.  A node the committed layout rejects falls back to the
    stage-8 law set (:func:`_decode_node_mixedwrite`): the zero-block
    extent table, the raw f32 array and the flat all-triples region.
    The flat law's absorption reference is the rep's OWN pool group — a
    multi-rep store's pool spans every rep, so the store-level pool can
    never re-list in one region (the TolerantSweepDev0/1 twins: each
    8-vertex group re-lists 8/8 in its own flat region and 0/8 against
    the other rep's).  Returns ``(record, failure)``; ``record`` is
    ``None`` when no law decodes the node.
    """
    try:
        elements, info = decode_region(payload, element_count)
        return (
            {
                "law": "table",
                "elements": elements,
                "pts": [pt for _v, pt in elements if pt is not None],
                "region_end_rel": info["walk_end"],
                "write_count": info["write_count"],
                "table_bytes": info["table_bytes"],
            },
            "",
        )
    except ExportError as exc:
        committed = exc.detail
    counts_end = _token_counts_end(payload)
    if counts_end is None:
        # Unreachable behind _scan_token_nodes' validated counts.
        return None, committed
    law, elements, pts, region_end_rel, wc, failure = _decode_node_mixedwrite(
        payload, element_count, counts_end, poolv
    )
    if law is None:
        return None, failure or committed
    return (
        {
            "law": law,
            "elements": elements,
            "pts": pts,
            "region_end_rel": region_end_rel,
            "write_count": wc,
            "table_bytes": (element_count + 3) // 4 if law == "table" else 0,
        },
        "",
    )


def _decode_per_rep(data, lo, hi, groups, n_missing, n_pool, seam_area=None):
    """The sequence-of-reps reading (stage-4b per-rep law, stage-5
    integration; pairing/territory corrected 2026-11-18, #50 B3).

    Rep k = (pool group k, the token node immediately preceding that
    group, that node's record territory ``[region_end_k, next token
    node)``); the k-th pool re-lists verbatim (or within
    :data:`NOISE_REL`) in the k-th rep's region.  Each node decodes under
    the law ladder of :func:`_decode_rep_node` (the committed table
    layout first, then the stage-8 extent/raw/flat laws with the rep's
    OWN pool group as the flat law's absorption reference).  A rep
    exports only when its pool absorbs and its gated references resolve
    in-bounds against its OWN element count; failing reps stay
    unexported with the reason named.  When no rep exports, raises the
    stage-3d ``unabsorbed`` classification with the per-rep residue
    named (fail-closed, no guessing).

    The pairing is by the GROUP's position, not by the decoded index
    (:func:`_rep_node_positions`): a rep whose region does not decode
    (or that cannot be paired) is unexported, and the next group keeps
    its own node — the shift that lost
    CAAGsiStartVolumeForBoolean's reps is closed by construction.  A
    rep's records end at the next token node (decoded or not), so a
    rep's records are never attributed to its predecessor.
    """
    scanned = _scan_token_nodes(data, lo, hi)
    rep_nodes = _rep_node_positions(scanned, groups)
    # A paired node's flat law is gated on its OWN group's vertices (see
    # _decode_rep_node); an unpaired node decodes against no pool.
    pool_by_node = {}
    for group, node in zip(groups, rep_nodes):
        if node is not None and node not in pool_by_node:
            pool_by_node[node] = group
    decoded: dict[int, dict] = {}
    node_failures = []
    for npos, payload, c1, _c2 in scanned:
        group = pool_by_node.get(npos)
        record, failure = _decode_rep_node(
            payload, c1, list(group.vertices) if group is not None else []
        )
        if record is None:
            node_failures.append(f"node@{npos}: {failure}")
            continue
        record.update(
            {
                "pos": npos,
                "payload": payload,
                "elem": c1,
                # absolute end of the point region (the territory start)
                "region_end": npos + 4 + record["region_end_rel"],
            }
        )
        decoded[npos] = record
    if not decoded:
        raise ExportError(
            "undecoded-variant",
            f"node list does not re-list the pool: {n_missing} of "
            f"{n_pool} pool vertices absent from the decoded point "
            "region (unabsorbed variant; the per-rep decomposition "
            "decodes no rep node under the table, extent, raw or flat "
            f"law either: {'; '.join(node_failures[:2]) or 'no nodes'})",
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
    node_bytes = sum(len(d["payload"]) for d in decoded.values())
    # N1 (2026-11-18 review): the per-rep path exports the extended
    # family too, so its summary must name it like the single-rep path.
    ext_records = 0
    ext_triangles = 0
    ext_declined = 0
    reps_unexported = []
    reps_dup_pin = []
    space_offsets = []
    reps_decoded = 0
    reps_exported = 0
    scanned_positions = [npos for npos, _p, _c1, _c2 in scanned]
    for k, (group, node) in enumerate(zip(groups, rep_nodes)):
        if node is None:
            # Fail-closed (2026-11-18, #50 B3): the group has no
            # preceding token node, or its node was already claimed by
            # an earlier group — never the "first node after" reading.
            reps_unexported.append(
                f"rep {k}: no token node precedes pool group {k} "
                "(the group's rep node is missing or ambiguous; per-rep "
                "absorption not established)"
            )
            continue
        d = decoded.get(node)
        if d is None:
            reps_unexported.append(
                f"rep {k}: the token node at {node} has no region under "
                "the committed table layout or the stage-8 extent/raw/"
                "flat laws (its pool group stays unexported)"
            )
            continue
        reps_decoded += 1
        distinct = set(group.vertices)
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
        # A rep's territory ends at the NEXT TOKEN NODE (decoded or
        # not), so an undecoded rep's records are never attributed to
        # its predecessor (2026-11-18, #50 B3).
        nxt_candidates = [p for p in scanned_positions if p > d["pos"]]
        nxt = min(nxt_candidates) if nxt_candidates else hi
        records, n_hdrs = parse_strip_records(
            data, d["region_end"], nxt, d["elem"], elements=d["elements"]
        )
        ext_k, ext_cands = parse_extended_facet_records(
            data,
            d["region_end"],
            nxt,
            d["elem"],
            elements=d["elements"],
            shipped_spans=_short_record_spans(data, d["region_end"], nxt, records),
        )
        grefs = [
            r for _o, mk, _n, _c, refs, _w in records if mk in GATED for r in refs
        ]
        grefs += [r for rec in ext_k for r in rec.refs]
        if grefs and max(grefs) >= d["elem"]:
            mx = max(grefs)
            reps_unexported.append(
                f"rep {k}: facet references beyond the rep's element "
                f"space (max ref {mx} >= element count {d['elem']}, "
                "M2b identity per rep)"
            )
            continue
        base = len(points)
        space_offsets.append(base)
        tri_k, deg_k, stats_k = _triangulate(
            d["elements"], records, extended=ext_k, seam_area=seam_area
        )
        # The dup-pin weld is per loop (2026-11-18): the rep's dropped
        # loops were evaluated independently (pinnable + battery + mesh
        # guard).  The welded ones ride along and merge at the store
        # level below with this rep's point offset; refused loops stay
        # counted as dropped.
        if "dup_pin" in stats_k:
            reps_dup_pin.append((base, stats_k.pop("dup_pin")))
        points += d["pts"]
        triangles += [(a + base, b + base, c + base) for a, b, c in tri_k]
        degenerate += deg_k
        loop_stats["loops_exported"] += stats_k["loops_exported"]
        loop_stats["loops_curve_entry"] += stats_k["loops_curve_entry"]
        # The primary-seam counters are per rep (each rep's
        # ``_triangulate`` assembled its own mesh) and sum at the store
        # level; a zero never enters ``info`` (passing rows unchanged).
        # The relaxed-family counters sum the same way (T3, #61).
        for _key in (
            "primary_loop_skips",
            "primary_loop_kept",
            "relaxed_loops_accepted",
            "relaxed_loops_declined",
        ):
            if _key in stats_k:
                loop_stats[_key] = loop_stats.get(_key, 0) + stats_k.pop(_key)
        ext_records += len(ext_k)
        ext_triangles += stats_k.pop("extended_triangles", 0)
        ext_declined += stats_k.pop("extended_declined", 0)
        facet_candidates += n_hdrs + ext_cands
        facet_records += len(records) + len(ext_k)
        write_count += d["write_count"]
        table_bytes += d["table_bytes"]
        element_decl += d["elem"]
        curve_entries += len(d["elements"]) - len(d["pts"])
        reps_exported += 1
        for _o, mk, _n, _c, _refs, _w in records:
            if mk not in EXPORTED_SHORT_MARKERS and mk not in RELAXED_SHORT_MARKERS:
                skipped_markers[mk] = skipped_markers.get(mk, 0) + 1
    if not points:
        raise ExportError(
            "undecoded-variant",
            f"node list does not re-list the pool: {n_missing} of "
            f"{n_pool} pool vertices absent from the decoded point "
            "region (unabsorbed variant; the per-rep decomposition "
            f"exports no rep: {'; '.join(reps_unexported) or 'no reps'})",
        )
    # The dup-pin weld at the store level (2026-11-18, per loop): every
    # rep's dropped loops were evaluated independently; merge each rep's
    # welded loops with its point offset.  A rep whose loops the battery
    # or the mesh guard refused contributes none — its loops stay in
    # ``loops_curve_entry``.
    curve_entry_law = 0
    for b, c in reps_dup_pin:
        if not c["loops"]:
            continue
        triangles += [(a + b, s + b, t + b) for a, s, t in c["triangles"]]
        degenerate += c["degenerate"]
        loop_stats["loops_exported"] += c["loops"]
        loop_stats["loops_curve_entry"] -= c["loops"]
        curve_entry_law += c["loops"]
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
        "reps_decoded": reps_decoded,
        "reps_exported": reps_exported,
        "reps_unexported": len(reps_unexported),
        "rep_reasons": reps_unexported,
        **loop_stats,
    }
    if ext_records:
        info["extended_header_records"] = ext_records
        info["extended_header_triangles"] = ext_triangles
        if ext_declined:
            info["extended_header_declined"] = ext_declined
    if curve_entry_law:
        info["curve_entry_law"] = "e0b-dup-pin"
        info["loops_curve_entry_exported"] = curve_entry_law
    # The disjoint per-rep index spaces, in emission order: the
    # stage-15 dedup's keeper rule (the earliest unit wins) needs them
    # at the assembled mesh, where a rep's re-listing of an earlier
    # rep's facet is visible by COORDINATE identity
    # (:func:`decode_composite_store` pops the key and applies the law
    # to the mesh the store actually exports).
    info["_space_offsets"] = tuple(space_offsets)
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


def _decode_raw_array(data, lo, hi, groups, payload, elem_decl, seam_area=None):
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
    extended, ext_candidates = parse_extended_facet_records(
        data, lo, hi, elem_decl, shipped_spans=_short_record_spans(data, lo, hi, records)
    )
    all_refs = [
        r for _o, mk, _n, _c, refs, _w in records if mk in GATED for r in refs
    ]
    all_refs += [r for rec in extended for r in rec.refs]
    if all_refs:
        mx = max(all_refs)
        if mx >= elem_decl:
            raise ExportError(
                "undecoded-variant",
                f"facet references beyond the raw-array element space: "
                f"max ref {mx} >= element count {elem_decl} (M2b "
                "identity on the raw array; G3 open question 2)",
            )
    triangles, degenerate, loop_stats = _triangulate(
        elements, records, extended=extended, seam_area=seam_area
    )
    # The raw-array path keeps the committed curve-entry rule (it has no
    # weld branch; measured corpus incidence 0) and names the extended
    # family like every other path (N1): consume the weld candidate and
    # lift the extended counters into their own summary keys.
    loop_stats.pop("dup_pin", None)
    ext_triangles = loop_stats.pop("extended_triangles", 0)
    ext_declined = loop_stats.pop("extended_declined", 0)
    skipped_markers: dict[int, int] = {}
    for _o, mk, _n, _c, _refs, _w in records:
        if mk not in EXPORTED_SHORT_MARKERS and mk not in RELAXED_SHORT_MARKERS:
            skipped_markers[mk] = skipped_markers.get(mk, 0) + 1
    info = {
        "stage": "identity-raw-array",
        "element_decl": elem_decl,
        "node_points": len(points),
        "curve_entries": 0,
        "facet_candidates": n_hdrs + ext_candidates,
        "facet_records": len(records) + len(extended),
        "skipped_markers": skipped_markers,
        "node_bytes": len(payload),
        **raw_info,
        **loop_stats,
    }
    if extended:
        info["extended_header_records"] = len(extended)
        info["extended_header_triangles"] = ext_triangles
        if ext_declined:
            info["extended_header_declined"] = ext_declined
    # One index space on this path (see the single-region note above).
    info["_space_offsets"] = (0,)
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


def _decode_mixedwrite(data, lo: int, hi: int, groups, seam_area=None):
    """The stage-8 mixed-write per-rep composition (stage 9, #34): the
    stage-5 per-rep decomposition applied to the walk-mismatch residue
    over the FULL-body window, with the stage-8 locator/predicate laws
    per node (:func:`_decode_node_mixedwrite`).

    Rep k = (pool group k, the token node immediately preceding that
    group's wrapper — the measured order, 2026-11-18 #50 B3 —, that
    node's record territory ``[region_end_k, next token node)``).
    The store exports only when EVERY pool vertex is absorbed by its
    paired rep's region (exact f32, then the stage-4b noise
    tolerance capped at 10,000-vertex pools): vertices re-listed only
    by the ``05 08 01`` sub-node records have unpinned element indices
    and keep the store fail-closed for export (the stage-8 note's
    integration item (e); bad44bdf's class).  Per rep: the M2b refs
    gate against the rep's own element count, records parsed with the
    committed width laws, strip/polygon triangulation; merged meshes
    concatenate the exported reps' written points.  A rep whose gated
    references leave its own element space stays unexported with the
    reason named (stage-5 per-rep fail-closed); a group whose rep node
    is missing or was already claimed by an earlier group stays
    unexported too.

    Raises :class:`ExportError` (``undecoded-variant``) with the
    specific gap when no node decodes, absorption is not established,
    or no rep exports."""
    poolv = [v for g in groups for v in g.vertices]
    pool_set = set(poolv)
    nodes = _scan_token_nodes(data, lo, hi)
    # The rep pairing (2026-11-18, #50 B3; see _decode_per_rep): group
    # k pairs with the token node immediately preceding its wrapper.
    # The flat law's absorption gate uses that group's vertices only —
    # a multi-rep store's whole pool cannot re-list in one region.
    rep_nodes = _rep_node_positions(nodes, groups)
    pool_by_node = {}
    for k, node in enumerate(rep_nodes):
        if node is not None and node not in pool_by_node:
            pool_by_node[node] = k
    decoded: dict[int, dict] = {}
    law_counts = {"table": 0, "raw": 0, "flat": 0}
    node_failures = []
    for npos, payload, c1, _c2 in nodes:
        counts_end = _token_counts_end(payload)
        if counts_end is None:  # unreachable behind _scan_token_nodes
            continue
        k = pool_by_node.get(npos)
        node_poolv = list(groups[k].vertices) if k is not None else []
        law, elements, pts, region_end_rel, wc, failure = _decode_node_mixedwrite(
            payload, c1, counts_end, node_poolv
        )
        if law is None:
            node_failures.append(f"node@{npos}: {failure}" if failure else f"node@{npos}: undecoded")
            continue
        law_counts[law] += 1
        decoded[npos] = {
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
    if not decoded:
        raise ExportError(
            "undecoded-variant",
            f"the stage-8 mixed-write per-rep composition decodes none "
            f"of the {len(nodes)} token nodes over the full-body "
            f"window (table/raw/flat laws; "
            f"{'first: ' + node_failures[0] if node_failures else 'no token nodes'})",
        )
    # Store-level absorption precondition: every pool vertex in its
    # PAIRED rep's region (exact f32, then the stage-4b noise
    # tolerance; the census measured exact f32 on all 81).  Vertices no
    # region re-lists are the sub-node record route's residue — their
    # element slots are unpinned, the store stays fail-closed (named).
    uncovered = 0
    for k, g in enumerate(groups):
        node = rep_nodes[k]
        rep = decoded.get(node) if node is not None else None
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
    node_bytes = sum(len(d["payload"]) for d in decoded.values())
    # N1 (2026-11-18 review): the per-rep path exports the extended
    # family too, so its summary must name it like the single-rep path.
    ext_records = 0
    ext_triangles = 0
    ext_declined = 0
    reps_unexported = []
    reps_dup_pin = []
    space_offsets = []
    reps_decoded = 0
    reps_exported = 0
    scanned_positions = [npos for npos, _p, _c1, _c2 in nodes]
    for k, node in enumerate(rep_nodes):
        if node is None:
            reps_unexported.append(
                f"rep {k}: the pool group's rep node (missing) has no "
                "law-decoded region (per-rep absorption unestablished)"
            )
            continue
        d = decoded.get(node)
        if d is None:
            reps_unexported.append(
                f"rep {k}: the pool group's rep node at {node} has no "
                "law-decoded region (per-rep absorption unestablished)"
            )
            continue
        reps_decoded += 1
        # A rep's territory ends at the NEXT TOKEN NODE (decoded or
        # not), so an undecoded node's records are never attributed to
        # its predecessor.
        nxt_candidates = [p for p in scanned_positions if p > d["pos"]]
        nxt = min(nxt_candidates) if nxt_candidates else hi
        records, n_hdrs = parse_strip_records(
            data, d["region_end"], nxt, d["elem"], elements=d["elements"]
        )
        ext_k, ext_cands = parse_extended_facet_records(
            data,
            d["region_end"],
            nxt,
            d["elem"],
            elements=d["elements"],
            shipped_spans=_short_record_spans(data, d["region_end"], nxt, records),
        )
        grefs = [
            r for _o, mk, _n, _c, refs, _w in records if mk in GATED for r in refs
        ]
        grefs += [r for rec in ext_k for r in rec.refs]
        if grefs and max(grefs) >= d["elem"]:
            mx = max(grefs)
            reps_unexported.append(
                f"rep {k}: facet references beyond the rep's element "
                f"space (max ref {mx} >= element count {d['elem']}, "
                "M2b identity per rep)"
            )
            continue
        base = len(points)
        space_offsets.append(base)
        tri_k, deg_k, stats_k = _triangulate(
            d["elements"], records, extended=ext_k, seam_area=seam_area
        )
        # The dup-pin weld is per loop (see _decode_per_rep).
        if "dup_pin" in stats_k:
            reps_dup_pin.append((base, stats_k.pop("dup_pin")))
        points += d["pts"]
        triangles += [(a + base, b + base, c + base) for a, b, c in tri_k]
        degenerate += deg_k
        loop_stats["loops_exported"] += stats_k["loops_exported"]
        loop_stats["loops_curve_entry"] += stats_k["loops_curve_entry"]
        # The primary-seam counters are per rep (each rep's
        # ``_triangulate`` assembled its own mesh) and sum at the store
        # level; a zero never enters ``info`` (passing rows unchanged).
        # The relaxed-family counters sum the same way (T3, #61).
        for _key in (
            "primary_loop_skips",
            "primary_loop_kept",
            "relaxed_loops_accepted",
            "relaxed_loops_declined",
        ):
            if _key in stats_k:
                loop_stats[_key] = loop_stats.get(_key, 0) + stats_k.pop(_key)
        ext_records += len(ext_k)
        ext_triangles += stats_k.pop("extended_triangles", 0)
        ext_declined += stats_k.pop("extended_declined", 0)
        facet_candidates += n_hdrs + ext_cands
        facet_records += len(records) + len(ext_k)
        write_count += d["write_count"]
        if d["law"] == "table":
            table_bytes += (d["elem"] + 3) // 4
        element_decl += d["elem"]
        curve_entries += len(d["elements"]) - len(d["pts"])
        reps_exported += 1
        for _o, mk, _n, _c, _refs, _w in records:
            if mk not in EXPORTED_SHORT_MARKERS and mk not in RELAXED_SHORT_MARKERS:
                skipped_markers[mk] = skipped_markers.get(mk, 0) + 1
    if not points:
        raise ExportError(
            "undecoded-variant",
            f"the stage-8 mixed-write per-rep composition exports no "
            f"rep: {'; '.join(reps_unexported) or 'no reps'}",
        )
    # The dup-pin weld at the store level (see _decode_per_rep).
    curve_entry_law = 0
    for b, c in reps_dup_pin:
        if not c["loops"]:
            continue
        triangles += [(a + b, s + b, t + b) for a, s, t in c["triangles"]]
        degenerate += c["degenerate"]
        loop_stats["loops_exported"] += c["loops"]
        loop_stats["loops_curve_entry"] -= c["loops"]
        curve_entry_law += c["loops"]
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
        "reps_decoded": reps_decoded,
        "reps_exported": reps_exported,
        "reps_unexported": len(reps_unexported),
        "rep_reasons": reps_unexported,
        "rep_laws": law_counts,
        **loop_stats,
    }
    if ext_records:
        info["extended_header_records"] = ext_records
        info["extended_header_triangles"] = ext_triangles
        if ext_declined:
            info["extended_header_declined"] = ext_declined
    if curve_entry_law:
        info["curve_entry_law"] = "e0b-dup-pin"
        info["loops_curve_entry_exported"] = curve_entry_law
    # The disjoint per-rep index spaces, in emission order (see the
    # _decode_per_rep note above).
    info["_space_offsets"] = tuple(space_offsets)
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
