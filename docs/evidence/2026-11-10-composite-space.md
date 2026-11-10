# Evidence: the composite index space — edge tables, the scene-graph element space, the count law (2026-11-10)

Ticket #34 (G6, spec D #28), stage 2a: decode the composite index space
of the L1 stores (analysis + decoder only; **no exporter integration** —
`src/` untouched, no fitness writes, no publication). Scope: the **939
composite-structure stores** of the L2 population (878 dev
composite-space + 61 held-out — exactly the stage-1 census's composite
class; the 30 dev refs-beyond stores carry neither an `01 02` group nor
an opener and were not re-audited here). Method: read-only byte
analysis, `scripts/triage/decode_composite_space.py` (reuses the shipped
`catpart.geometry` scanners and G1's `release_of`; stdlib + mmap,
deterministic, sorted manifest order; ~48 s wall clock; 0 audit errors
over 1,442 parts). Data:
`docs/evidence/data/composite-space-files.csv` (one row per part).
Builds on G1/G2/G3 and the stage-1 census
([2026-11-10-l2-grind-classification.md](2026-11-10-l2-grind-classification.md));
those models are cited, not re-derived. Anchor stores (hand-decoded
byte-by-byte for this note): 70b59f2a0eb60c1c (the handoff's settle-it
store), 0018baa84f3bff6b, 02ee154402795740, 026d6726007381a9, and the
clean 8-vertex box 10b9ae4a3cd58298 as the degenerate control.

Labels: **fact** = byte-measured here and reproducible from the CSV;
**inference** = interpretation of measured bytes, named as such;
**unknown** = open. The house bar (established = validates at >= 0.98
on its scope) is applied mechanically; below-bar claims are candidate.

The headline: **the edge tables are polyline tables (`02 <n> <n refs>`,
per-group u8/u16be, count field in the pool groups' P1g convention)
whose walk lands byte-exactly on the next wrapper on 812/899 = 0.903
edge-carrying stores, and the extended element space is DECLARED in the
store's scene-graph nodes: every one of the 939 composite stores (939/
939) carries a node token `ff ff 02 00 01` followed by two counts
(element_count, edge_ref_bound), and on 877/939 = 0.934 the declared
element_count is >= max reference + 1 — i.e. every facet reference
resolves inside a declared element space that is LARGER than the pool
on 876/939 of them (2026-11-10 correction (#34 review): the first
wording said 935/939 = element_count != pool, conflating unequal with
larger — 4 stores have element_count == pool and 59 have it SMALLER
than the pool, both named residue). The extra elements live in the
pre-facet scene-graph
territory as per-rep point lists stored LEX-SORTED (x, y, z) with prefix
compression (byte-verified point-by-point on 026d6726), plus the
`33 3X` curve-record families in the `00 00`-group/opener territory.
There is no second `05 08 01` vertex pool anywhere (0 of the 4 anchors;
24/939 marginal multi-byte coincidences at corpus scale). The global
numbering law — refs are positions in the globally lex-sorted merge of
pool and node points, of which the clean stores' F2 "lex ranks" are the
degenerate case — is **candidate**, supported by loop-planarity on
026d6726 and a half-rate winding on 70b59f2a under an unfiltered point
extraction.**

## 1. The edge tables are polyline tables (E1-E3, fact + candidate)

Stage-1 C6 read the `01 02` groups as "6-byte records `02 02
(u16be)(u16be)` under a count byte" and left 157 groups as "other `02
0X` forms". The decode refines this — there are no other forms, only
other point counts:

- **E1 (candidate, 812/899 = 0.903 edge-carrying stores; grammar
  byte-verified on all 5 anchors):** a wrapped edge group is
  wrapper + `01 02` + **count field at +10 in the pool groups' P1g
  convention** (one byte when the count fits, `ff` escaping to a u32le
  at +11) + **that many polyline records `02 <n> <n refs>`** — n = the
  record's point count (n = 2 is a segment; n > 2 is a polyline strip),
  each reference u8 or u16be (big-endian) per GROUP, decided by
  end-alignment: the walk of `count` records must land **exactly** on
  the next `10 24 04 ff ff 00 00 00` wrapper or the body end. Measured:
  the walk lands exactly on 812/899 stores (u16be groups on 628 stores,
  u8 on 220, multi-group stores carrying both — per-group, not
  per-store). Byte checks on the anchors: 0018baa8 — count 0x46 = 70,
  70 records x 6 B + 11 B head = 431 B to the next wrapper, exact;
  02ee1544 — ff-escaped
  count 402, 402 x 6 B lands exactly; 70b59f2a — 604 x 6 B exact;
  026d6726 — count 8, records of 3, 3, 9, 2, 2, 2, 2 and 9 points
  (32 u8 refs), 59 B exact. The stage-1 "157 other forms" = groups
  whose records carry n != 2; the "ff escapes to u32le — P1g
  convention" note is confirmed as the record-count field.
- **Residue (named, 87 stores):** 79 stores where no width lands the
  walk exactly (e.g. 13bb5c0c: declared count 70,080 against a
  420 KB gap — a count-unit or record-form variant; 0e4bc645: 2-record
  groups) + 8 stores with mixed walking/failing groups. Left undecoded;
  recorded, not absorbed.
- **E2 (fact, box):** the 8-vertex box 10b9ae4a carries the same
  records un-wrapped under `01 01 0c` (12 records `02 02 <a> <b>`,
  u8) — and its 12 (a, b) pairs ARE the box's 12 edges as
  lexicographic ranks, the same index space as its facet records
  (G2's worked example). Edge records and facet records index ONE
  space.
- **E3 (candidate, 680/939 = 0.724 stores, 64,143 records):** the
  un-wrapped `01 01 <count>` lists are corpus-wide on composite stores
  (located by the same record walk with strict end-alignment onto a
  wrapper). Stage-1's edge census counted only the wrapped groups and
  therefore undercounted the edge-table territory (new evidence, not a
  correction).

## 2. The element space is declared in the scene-graph nodes (N1-N5)

The store body's pre-facet territory (everything before the first
`01 [41-4f] . ff` facet header) carries `04 04 fd ff` node records —
G1 N7's scene-graph stream payload. Two measured laws:

- **N1 (established (observed), 939/939 = 1.000):** every composite
  store's node territory contains the token **`ff ff 02 00 01`**
  followed by two counts in the P1g convention (u8, `ff` -> u32le):
  **(element_count, edge_ref_bound)**. Byte checks: 70b59f2a —
  (1,820, 1,812); 02ee1544 — (2,198, 1,502); 0018baa8 — (570, 570);
  026d6726 — (124, 124); the clean box — (8, 0).
- **N2 (candidate at corpus scale, 877/939 = 0.934; anchors 5/5):**
  **element_count = max reference + 1** over the facet and edge records
  — the declared size of the composite element space — and
  edge_ref_bound = the edge table's max endpoint + 1 where the edge
  table reaches the top of the space (strict equality of the size
  component alone: 713/939 = 0.759; both components strict: 323/939 —
  2026-11-10 relabel (#34 review): the first wording called 713/939
  "strict equality of both"; the edge-bound component alone: 335/899).
  The 62 stores
  where element_count < max ref + 1 are a named residue (count-field
  variants or multi-source refs; not massaged).
- **N3 (candidate, 883/939 = 0.940):** every facet reference is < the
  declared element_count — **the facet refs resolve inside a declared
  space larger than the pool**. On 876/939 composite stores the
  declared space EXCEEDS the pool size (element_count == pool on only
  4 — N4, the clean-store degenerate case, matching the box's (8, 0)
  with pool 8; smaller than the pool on 59 — named residue; 2026-11-10
  correction (#34 review): the first wording said 935/939, conflating
  unequal with larger).
- **N5 (established (negative) on the anchors; 24/939 marginal at
  corpus scale):** there is **no second vertex pool**: `05 08 01`
  vertex records occur only inside `01 06` groups on all 4 anchors; at
  corpus scale 24/939 stores show a >= 3-record `05 08 01` run outside
  the groups — named, unresolved (compressed-stream coincidence vs a
  rare second-pool form), 0.026 of stores.
- **N6 (fact, one store, the worked point list):** on 026d6726 the
  large node (1,456 B) carries a point list stored **LEX-SORTED (x, y,
  z) with prefix compression**: each point writes `[x if changed][y if
  changed][z always]` as f32le. Verified point-by-point for 30+
  consecutive points (e.g. `(392.65, 434.74, 2.3975) -> (392.65,
  436.26, 2.3975)` written as `[436.26, 2.3975]`; `(392.82, 434.60,
  2.81) -> (392.82, 434.60, 2.9)` written as `[2.9]`); the list is
  perfectly lex-nondecreasing and CONTAINS POOL VERTICES VERBATIM
  (10/10 pool vertices re-listed; 2026-11-10 example correction (#34
  review): pool v1 = (392.21988, 435.5, 2.1) is the list's FIRST point
  — the triple quoted before, (392.39, 434.55, 2.1), is node-list
  point 1, not a pool vertex). The
  small nodes carry `[f32 a][f32 0][origin xyz]` + the token counts
  only. On the big stores (70b59f2a's 262 KB / 17.6 KB nodes) the node
  payloads show compressed-stream byte statistics (runs of `77`/`bb`/
  `ff`) — **whether the big-store point lists are compressed, and the
  list terminator, is unknown**; the plain-list encoding is proven on
  the small-store form only.

## 3. The numbering law (M1, candidate — the ticket's central question)

The answer to "where do the >= pool refs resolve":

- **M1 (candidate):** the element space = **the pool vertices plus the
  scene-graph nodes' point lists (plus the curve points, quantitatively
  consistent on 026d6726)**, and the references — facet AND edge — are
  **positions in the globally lex-sorted merge** of that space. On a
  clean store the space is the pool alone, so positions == lex ranks of
  the pool: **G3's F2 law is the degenerate case of this law**, which
  explains why a writer would reference "lexicographic ranks" at all.
  Evidence: (a) on 026d6726 the facet record `01 4a 07 ff` (7 loops,
  stored normal exactly (0, 0, -1)) has first loop (17, 2, 27, 1, 18,
  3) — under pool-lex ranks the pool elements 1, 2, 3 carry z (2.81,
  2.9, 2.1) and refs 17, 18, 27 point BEYOND the 10-element pool
  entirely: the loop CANNOT be planar under pool-lex, and the pool's
  lex-z list is measured, so pool-lex indexing is falsified on
  composite stores.  2026-11-10 correction (#34 review): the first
  wording also claimed the confirmation — "under the global merge
  (pool 10 + the node's decoded points) the loop decodes exactly
  planar, all six z = 2.1" — but that construction does not reproduce
  under any documented reading (0/1-based, duplicates kept or deduped;
  the exact merge law is undocumented). The confirmation is OUTSTANDING,
  not checked; recovering the exact merge construction is open work
  (unknown 4), and M1 stays candidate on the falsification + N2/C1
  corroboration alone; (b) the declared
  element_count tracks max_ref + 1 (N2), which a pool-independent
  element space predicts; (c) on 70b59f2a the winding test under
  pool-lex + node-points-direct scores 0.5153 vs 0.4435 walk-order —
  real signal at half rate, limited by the unfiltered point extraction
  (42,613 points extracted against the ~656 the refs need — the
  compressed big-store lists are not yet parsed; unknown).
- **M2 (inference):** the refs-beyond-pool class (stage-1's L3, 30 dev
  + 8 recovery stores) is the same mechanism with a non-standard
  sub-kind beside the pool (stage-1 section 4's inference), not
  re-audited here.

## 4. The curve families and the 30-records (C1/C2, census)

- **C1 (census, 939/939 stores):** the `33 3X` curve-record families
  (G2 unknown 5) appear in the `00 00`-group bodies and `ff`-opener
  regions of every composite store (1,807,070 two-byte hits corpus-wide
  — a presence census; compressed streams inflate the count). Layout
  facts from the anchors: 7-byte header `<u8 a><u8 b><u16le id><00>
  <u16le len>` + family byte `33 3X` + `len` payload bytes; 33 32 =
  [P][Q][P] f32le triples + trailing f32le |Q| (G2's law, re-verified
  on the box: 31.62 = |(10, 0, 30)|); 33 37 = 4 BIG-endian f32 + u16;
  33 38 = 3 big-endian f32 (345.0, 435.0, 2.855 on 026d6726 — pool
  scale) + 8 zero bytes + 8 B params. Point semantics open.
- **C2 (census, 907/939 stores):** the `30 04 04 ff ff` records seen
  on the anchors between the facet region and the edge lists (7 on the
  box, 8 on 026d6726) — 612,180 five-byte hits corpus-wide (presence
  census only; the box's 7 match its 7 records).

## 5. Corrections and dated additions

1. **2026-11-10, stage-1 C6 (edge tables):** the "6-byte records `02 02
   (u16be)(u16be)`" are the n=2 u16be case of the polyline record `02
   <n> <n refs>`; the "157 other `02 0X` forms" are groups whose
   records carry n != 2 (e.g. 026d6726's eight records of 3, 3, 9, 2,
   2, 2, 2, 9 points); the ff-escaped count byte is the record count
   (P1g), confirmed. The count byte's position (+10, escape at +11)
   and the 6-byte n=2 u16be reading were correct.
2. **2026-11-10, G3 F8 ("edge/rim table", endpoints lex-adjacent):**
   the edge-table endpoints index the FULL composite element space, not
   only the pool — on 0018baa8 and 70b59f2a the max edge endpoint
   (569, 1,811) exceeds the pool (164, 1,164) and on 0018baa8 equals
   the max facet reference (569); on 70b59f2a the edge max 1,811 sits
   below the facet max 1,819 (2026-11-10 wording correction (#34
   review): "equals/exceeds" overstated that store). The
   "lex-adjacent median 2.0"
   measurement was an artifact of the in-pool subset. F8's store-level
   rates reproduce unchanged.
3. **New evidence (not a correction):** the un-wrapped `01 01` polyline
   lists (E3) — stage-1's edge census walked only the wrapped groups.

## Claims

| claim | statement | rate | label |
|---|---|---|---|
| E1 | edge-table grammar: wrapper + `01 02` + P1g count + `02 <n> <n refs>` records, per-group u8/u16be by exact end-alignment | 812/899 = 0.903 edge-carrying stores land exactly; grammar byte-verified on 5 anchors; residue 87 named | candidate (below bar; grammar observed) |
| E2 | the box's un-wrapped `01 01 0c` list = 12 `02 02` segment records indexing the same lex space as its facets | 1 store, 12/12 edges | established (one store) |
| E3 | un-wrapped `01 01` polyline lists on composite stores, same record grammar, strict end-alignment | 680/939 = 0.724 stores, 64,143 records | candidate |
| N1 | list-node token `ff ff 02 00 01` + two P1g counts (element_count, edge_ref_bound) in the scene-graph territory | 939/939 = 1.000 | established (observed) |
| N2 | element_count = max facet/edge reference + 1 (declared space size); edge_ref_bound = edge max + 1 | size >= max+1: 877/939 = 0.934; strict == of the size component: 713/939 = 0.759 (both components strict: 323/939); anchors 5/5 | candidate (below bar; residue 62 named) |
| N3 | every facet reference < declared element_count (resolves in the declared space) | 883/939 = 0.940 | candidate |
| N4 | element_count == pool size on composite-structured stores with no extra elements (the clean degenerate) | 4/939 (box: (8, 0) with pool 8) | established (observed) |
| N5 | no second `05 08 01` vertex pool outside `01 06` groups | 0/4 anchors; 24/939 marginal runs at corpus scale (named) | established (negative, anchors) |
| N6 | node point lists are LEX-SORTED (x, y, z) with prefix compression `[x if changed][y if changed][z always]`, f32le; pool vertices re-listed verbatim | 1 store, 30+ points hand-verified; big-store form unknown (compressed?) | established (one store); encoding candidate |
| M1 | element space = pool + node point lists (+ curve points); refs = positions in the globally lex-sorted merge (F2 = the degenerate case) | pool-lex FALSIFIED on 026d6726 (pool lex-z 2.81/2.9/2.1 for refs 1, 2, 3; refs 17/18/27 beyond the 10-pool); the merge-construction confirmation does not yet reproduce (2026-11-10 correction: exact merge law undocumented); 70b59f2a winding 0.5153 vs 0.4435 walk under unfiltered extraction | candidate (numbering) |
| C1 | `33 3X` curve families in `00 00`-group/opener territory; 7-B header + per-family payloads (33 32 = [P][Q][P]+ \|Q\|; 33 37/33 38 big-endian f32) | present 939/939; layouts verified on anchors; semantics open | established (observed, layout); semantics unknown |
| C2 | `30 04 04 ff ff` records between facets and edge lists | 907/939 stores (presence census) | established (observed) |

Version scope: E1-N5 measured on the 939 composite-structure stores of
the 1,442-part L2 population (878 dev composite-space + 61 held-out),
all release lines; per-release rows in
`composite-space-claims.csv`.

## Unknowns / next questions (the next dispatch's territory)

1. **The big-store node streams** (70b59f2a's 262 KB / 17.6 KB nodes):
   compressed? the plain lex-list encoding is proven only on the
   small-store form; the list terminator and the exact point-count
   field are open. This is what keeps M1 at candidate.
2. **The count-law residue:** 62 stores with element_count < max ref +
   1, 87 stores whose edge groups fail both widths, 24 stores with
   `05 08 01` runs outside the groups — variant families, recorded.
3. **The curve-record point semantics** (`33 3X` families): are their
   points part of the element space (quantitatively consistent on
   026d6726: ~90 node + ~25 curve points vs 114 needed) — and what the
   [P][Q][P] triples MEAN.
4. **The exact element numbering at corpus scale** (the merge order:
   per-node blocks vs one global sort; duplicates kept or deduped) —
   decidable with the winding test once unknown 1 closes.
5. **The refs-beyond class (L3):** same mechanism inferred, not
   audited here (30 dev + 8 recovery stores).

## Reproduction

```
.venv/bin/python -I scripts/triage/decode_composite_space.py
# anchor subset:
.venv/bin/python -I scripts/triage/decode_composite_space.py \
  --include-sha16 0018baa84f3bff6b,026d6726007381a9,02ee154402795740,\
70b59f2a0eb60c1c,10b9ae4a3cd58298
```

Outputs `docs/evidence/data/composite-space-files.csv` (committed; one
row per L2 part, 0 audit errors). Corpus binaries are not committed
(corpus symlinked read-only; the worktree needs the symlink). No
exporter/runner code is touched; `catpart.geometry` is imported
read-only.
