# Evidence: the facet records' primitive semantics + one decoded triangle soup (2026-11-09)

Ticket #31 (G3, spec D #28): decide what the nested store's facet records
MEAN geometrically — triangles vs polygons vs polylines per marker family —
and decode one part end-to-end to a validated triangle soup. Scope: the
same corpus-wide sample as G1/G2 (**all 1,377 dev parts** of the manifest,
`kind=part`, `split=dev`, `magic_ok=yes`; 1,068 carry a decoded store).
Method: read-only byte analysis,
`scripts/triage/decode_facet_semantics.py` (stdlib, mmap, deterministic;
run with `python3 -I`; ~72 s wall clock, three consecutive runs
byte-identical, md5-verified). Data:
`docs/evidence/data/facet-semantics-files.csv` (one row per part),
`facet-semantics-loops.csv` (one row per decoded loop of the
clean-store subset; the composite stores' loop aggregates live in the
files-CSV columns),
`facet-semantics-claims.csv` (per-claim, per-release rates),
`facet-soup-369fc90b25b4977d.obj` (the committed soup, 3.6 KB). Builds
on G1 ([2026-11-09-nested-store.md](2026-11-09-nested-store.md)) and G2
([2026-11-09-vertex-pool.md](2026-11-09-vertex-pool.md)) — those models
are cited, not re-derived.

Labels: **established** = the model validates with rate >= 0.98 on its
scope (counterexamples named); **candidate** = below the bar or
scope-limited; every claim states whether it is a fact (byte-measured),
an inference, or an unknown.

The headline: **the facet records decode as per-loop primitive segments
whose vertex references are LEXICOGRAPHIC RANKS of the pool coordinates
(not walk order), 0x4a/0x42/0x49 loops are triangle-strip segments and
0x4c loops are closed polygons, and the winding law is "counter-clockwise
seen from the stored normal" — on the 76 clean single-source stores the
decoded soup is a manifold on 76/76, closed on 66/76, oriented on 66/66
closed solids, with 0 degenerate triangles, and the strip reading
reproduces the stored normals at 0.9923 vs 0.2746 under the walk-order
control.** Stores that also carry an `01 02` edge group and/or a
`10 24 ... ff` trailer opener use a larger composite index space that
this ticket bounds but does not fully decode (open question 1).

## 1. The facet record grammar, refined (F1)

The record header refines G2's `01 <mk> <ty> ff [u32le n]` into two
forms, both byte-measured:

- **4-byte form** `01 <mk> <ty> ff [u32le n][12B f32le normal][k u8
  counts][n refs]` — markers 0x41-0x4f; the 12-byte normal payload
  appears on 0x49/0x4a/0x4c (and on the 5-byte-form markers 0x4b/0x4e,
  see below); the k count bytes (0..4) sum to n and delimit the ty
  sub-loops.
- **5-byte form** `01 <mk> <ty> <b3> ff ...` — one extra byte before
  ff (observed `01 4b 01 01 ff` and `01 4e 0x 02 ff`-shaped headers).
  STRIP_RE does not match this form, so these records sit in the gaps
  between 4-byte records; 446 of them start exactly at a preceding
  record's end across 105 parts (counted at gap starts only — the
  count is a lower bound; semantics open, question 3).

- **F1 (established (observed), 516/1,068 = 0.483 stores with every
  candidate tiling; per-file 0.0-1.000):** a record is accepted when
  some (width, k) parse ends at or before the next header, and the
  exact-tiling parse (end == next header) wins.  Real facet records
  tile their region header-to-header; 516 stores tile completely and
  the rest carry gap content (the composite-space stores, section 6).

- **F1w (fact, measured on every accepted record):** the reference
  width is per-record u8 or u16be (big-endian), chosen by the tiling
  law — small stores use u8 (the 8-vertex box: 4-byte tails), large
  stores u16be (70b59f2a: 9-byte tails for n=4).  G2's "u8 on every
  facet the committed decoder accepts" is a special case.

## 2. The index mapping: lexicographic ranks (F2, correction C8)

G2's association rule ("indices are local to their pool group") holds
for bounds but the ORDER is not the walk order.  The functional test:

- **F2 (established on the clean-store scope, 1,290/1,300 = 0.9923
  winding triangles parallel):** mapping each reference to the pool
  vertex at its **lexicographic rank of (x, y, z)** reproduces the
  stored normals under the per-family readings (section 3).  Controls
  on the same 1,300 triangles: walk order 357/1,300 = 0.2746; lex
  (x,z,y) 0.379; lex (y,x,z) 0.286; lex (y,z,x) 0.091; lex (z,x,y)
  0.059; lex (z,y,x) 0.272 — every alternative mapping fails.
- **F2b (fact, one store):** the 8-vertex box `10b9ae4a3cd58298`
  makes the mapping explicit: its walked pool order is
  `(0,0,0), (20,0,0), (0,100,0), (20,100,0), (0,100,60), (20,100,60),
  (0,0,60), (20,0,60)` and the facet records reference the
  lexicographic ranks — rank 4 = (20,0,0), rank 0 = (0,0,0), rank 6 =
  (20,100,0), rank 2 = (0,100,0) — under which all six records decode
  to the six faces with their stored normals (12/12 triangles, 12
  sign-positive).  Under walk order the same records are bowties
  (zero Newell area) — G2's P6 "in-bounds" test could not see this.
- **F2c (candidate, 77/1,068 = 0.072 parts):** the lex mapping
  validates end-to-end only on stores whose element space is the pool
  alone (the 76 souped stores + 1; see section 6: 889/1,068 = 0.832
  stores carry an `01 02` edge group and/or a trailer opener and their
  references run beyond the pool — 793/889 = 0.892 of them).

## 3. Primitive semantics per marker family (F3, F4, F9, F10)

Each record = **ty sub-loops** (the k count bytes give the per-loop
reference lengths, summing to n — G2's law, retained).  The loop
content differs per family, decided by the winding test (section 4)
and the closure test (section 5):

| marker | carries | loop reading | evidence | label |
|---|---|---|---|---|
| 0x4a | 12B normal | **triangle-strip segment** per loop (n_refs-2 triangles, alternating flip, phase reset per loop) | clean stores: 1,274/1,284 strip triangles parallel, 1,272 sign+ (1 anti-parallel record named below); the box 12/12 | established (clean-store scope) |
| 0x42 | none | triangle-strip segment (structurally identical tails to 0x4a; no normal to winding-test) | adding 0x42-as-strips closes the two R17 open shells (90135d46, b9b887db) — closure 64/76 -> 66/76; loops 10,684 corpus-wide | established (functional, closure) |
| 0x4c | 12B normal | **closed polygon** per loop, corners in ring order (Newell normal == stored normal) | 16/16 clean-store loops Newell sign+; strip reading gives 16/16 MIXED signs (rejected); ring-order refs are lex-adjacent hops | established (clean-store scope) |
| 0x41 | none | triangle list (n == 3*type) | 59/59 records n == 3*type corpus-wide | established (byte law); primitive not winding-tested |
| 0x49 | 12B normal | n == 3*type law holds; primitive reading NOT established | 3,722/3,722 records n == 3*type; the one in-pool 0x49 loop fails strip/list/Newell readings | candidate (law); semantics open |
| 0x44 | none | unknown | 649 records; tails parse under the k-count law on some stores | open |
| 0x4b/0x4e | 12B normal (0x4b byte-verified) | unknown (5-byte header variant) | 446 gap-start records; 0x4b tails violate the count-sum law (count 5, n 8, 8 refs — 2 records hand-verified) | open (G2 unknown 6 sharpens to: the variant is real, frequent on 105 parts) |

- **F3 (established on scope):** 0x4a loops are strip segments.  The
  discriminator is the SIGN: the fan reading of the same loops is
  equally parallel (140/140 on 369fc90b) but sign-mixed (79/61),
  while the strip reading is 140/140 all-positive.
- **F4 (established on scope):** 0x4c loops are closed polygons in
  ring order.  The strip reading of the same loops is parallel but
  16/16 sign-mixed; the Newell reading is 16/16 sign-positive.
  B4's "annular zig-zag = closed triangle strip" is thereby SPLIT:
  true for 0x4a/0x42 content, false for 0x4c (correction C10).
- **F9/F10 (established byte laws):** n == 3*type holds on 59/59
  0x41 and 3,722/3,722 0x49 records.
- **Counterexamples named (not massaged):** on the clean subset, one
  record reads anti-parallel — `6888b9868df81c00` (R16), one 0x4a ty=1
  record with refs (0, 1, 2, 3): both strip triangles exactly parallel
  to the stored normal but sign-negative (a reversed-normal writer
  variant).  Five further clean-subset loops are off-plane, all on
  `b9b887db0d516d88` (R17).  Writer variants at the ~1% level.

## 4. The winding law (F5)

**All normal-bearing facet geometry is counter-clockwise seen from the
stored normal (right-hand rule), i.e. the OBJ convention.** Measured:
1,288 sign-positive vs 2 sign-negative triangles on the clean subset
(1,290 parallel of 1,300; the 10 off-plane are the counterexamples
above).  Concretely: for strip loops the consistent triangle sequence
is (r_t, r_{t+1}, r_{t+2}) with the flip on odd t (phase reset per
loop); for polygon loops the ring order has positive Newell normal.
G4 (the exporter) can emit every decoded triangle as-is.

- **F5 (established on the clean-store scope):** 1,288/1,290 = 0.9984
  of parallel winding triangles are sign-positive; the one
  anti-parallel record is `6888b9868df81c00` (R16), the five
  off-plane loops are on `b9b887db0d516d88` (R17).

## 5. Degenerate/repeat observations and the export convention (F6, F7)

- **Repeat references are real geometry (fact):** 48,509/157,981 =
  0.307 of decoded loops repeat at least one reference (per-part
  columns `n_loops`/`n_loops_repeat` in the files CSV; 150,788/157,981
  = 0.954 of loops belong to the strip families) — the strip-join
  pattern B4 saw.  The dominant shape re-emits one vertex
  between the others (fan strips around an apex: `[apex, rim_i, apex,
  rim_{i+1}, ...]` — cone-like patches); the standard strip reading
  yields the degenerate (apex, rim, apex) triangles between the real
  ones.  Repeats are NOT padding to be deduplicated at decode time.
- **F7 (established, 1,354/1,354 souped triangles):** zero degenerate
  triangles survive on the clean-store soups after the standard skip
  (triangles with a repeated vertex or zero cross product are skipped
  at export; measured skip count 0 — the writer does not emit
  degenerate strips on these stores).
- **Export convention for G4 (fact + convention):** decode strips with
  the alternating flip and phase reset per loop; fan-triangulate 0x4c
  polygons from the first corner (orientation-preserving for the CCW
  ring order); skip exactly the degenerate strip triangles; emit as-is
  otherwise.  0x42 records participate as strips (no normal payload —
  the surface orientation is not double-checked by a stored normal).

## 6. The triangle soup: end-to-end decode + manifold closure (F6, F8)

**The n=1 acceptance seed — `369fc90b25b4977d`** (R20,
Apoloo13/ASE_III, 217,665 B; store origin at block + 252, body 9,142 B;
1 pool group of 80 vertices, bbox (-1.2, 0, -0.95)..(21.2, 30, 0.95) —
a thin bracket; **no `01 02` group, no trailer opener**):

- 50 facet records (41 x 0x4a ty=1, 9 x 0x4a ty=2), 50/50 tile exactly,
  50/50 in-pool (max ref 79 < 80), 0 unresolved bytes of facet content.
- Soup: **140 triangles** (ty=1 records contribute 2-3 triangles per
  loop, ty=2 records 1+5), 0 degenerate, all 80 pool vertices used.
- Mesh invariants: **210 undirected edges, every one used exactly
  twice — a closed manifold; oriented-consistent (each edge used once
  per direction); bbox as above**.  Committed as
  `docs/evidence/data/facet-soup-369fc90b25b4977d.obj` (3.6 KB, 80 `v`
  lines = the pool in walk order, 140 `f` lines).
- Normals: 140/140 winding triangles parallel to the stored normals,
  140 sign-positive.

- **F6 (established on the clean-store scope, 76/76 = 1.000 manifold;
  closed 66/76 = 0.868; oriented 66/66 of the closed):** every
  clean store with a decodable facet set soups to a manifold — no
  edge used more than twice on any of the 76.  The 10 non-closed are
  sheet-like open shells (paired boundary edges): the 2-triangle
  single-quad parts (R16 96efc97f, R20 81f730b6/e5768c51), a 12-triangle
  strip shell (R19 fe6d27fd), and the 24-record 48-triangle tube family
  (bb996ab7/c5dfda57/e066a5ff — usage {1: 48, 2: 48}, a rim-paired
  open surface).  Per release: R15 2/2, R16 0/2, R17 5/5, R18 1/1,
  R19 12/16, R20 20/22, R21 21/23, R23 1/1, R26 2/2, unknown 2/2.
- **F8 (measured, interpretation open):** 889/1,068 = 0.832 stores
  carry an `01 02` group and/or a `10 24 04 ff ff 00 00 00 ff [u32le
  region length]` opener (the latter opens the trailer-named region
  [B, B+C) — the opener's u32le equals C on the worked example 70b59f2a:
  80,297).  On 793/889 = 0.892 of them the facet references exceed the
  pool (max ref up to 1,819 vs pool 1,164 on 70b59f2a; up to 18,442 vs
  1,624 on 97a0a420).  The reference space is a COMPOSITE (pool +
  further element sources): the `01 02` groups carry 6-byte records
  `02 02 (u16be)(u16be)` whose references map to lex-ADJACENT pool
  vertices (median edge length 2.0 on 70b59f2a — an edge/rim table),
  and the trailer region carries curve-like records (`02 00 33 32/36`
  + f32le triples + a trailing f32le length equal to the middle
  triple's norm, as G2 sketched).  The exact composite numbering is
  OPEN (question 1) — under pool-only mapping the composite stores'
  in-pool-looking loops wind at only 0.167, i.e. the mapping is
  genuinely incomplete there, not wrong-by-variant.

## 7. Render sanity check (the visual gate)

Viewer tooling on this host: none — `blender`, `meshlab`, `f3d`,
`assimp`, `paraview` absent from PATH; `trimesh`/`numpy` not importable;
nothing installed (per the dispatch rules).  The machine check stands
on the mesh invariants above (manifold/closure/orientation/bbox) which
are the acceptance seed's numbers; **the visual confirmation of the
soup is deferred to the coordinator** (render
`docs/evidence/data/facet-soup-369fc90b25b4977d.obj` — a bracket-like
thin solid).

## 8. Corrections to G2/B4 (recorded, none massaged)

1. **C8 — the index order:** G2's P5/P6 association rule (indices
   local to their pool group, walk-order positions) is refined: the
   references are **lexicographic ranks of (x, y, z) within the pool**,
   not walk positions.  Byte evidence: the box's six records decode to
   bowties under walk order and to the six faces with correct stored
   normals under lex ranks; corpus-wide the strip winding under lex
   ranks scores 0.9923 vs 0.2746 walk order on the clean subset (and
   <= 0.38 for the five other axis orders).  The in-bounds rate G2
   measured is unaffected (ranks share the pool's bounds).
2. **C9 — "0x42/0x4a/0x4c boundary loops":** the loop-count structure
   (k bytes summing to n) is retained, but the primitive reading
   splits: 0x4a (and 0x42) loops are **triangle-strip segments** —
   B4's strip reading was right about the CONTENT and wrong about the
   grammar (its u16be-everywhere + no-count-bytes model); 0x4c loops
   are **closed polygons in ring order**, not strips.  Byte evidence:
   the sign test (section 3) — a strip reading of 0x4c is 16/16
   sign-mixed while Newell is 16/16 sign-positive, and vice versa the
   fan reading of 0x4a is sign-mixed while the strip reading is
   all-positive.
3. **C10 — B4's "triangle strip" family label:** B4 recorded the whole
   `01 4x` family as triangle strips with u16be indices; the corpus
   shows per-record adaptive u8/u16be width (F1w), per-loop count
   bytes, per-family primitive semantics, and the lex-rank index
   space.  B4's verified records are reattributed accordingly; the
   zig-zag patterns B4 saw in `e9ca6192a2854002` are strip joins and
   apex-fan repeats (section 5), now measured corpus-wide (0.313 of
   strip loops repeat a reference).
4. **C11 — G2's "u8 on every facet the committed decoder accepts":**
   true as far as it went; the tiling law shows u16be records exist
   corpus-wide wherever the element space exceeds 255 (they were the
   unresolved-candidate mass of G2's P6u, 834/1,377 parts).

## Claims

| claim | statement | rate | label |
|---|---|---|---|
| F1 | facet records tile their region header-to-header under the (width, k) tiling law; two header forms (4-byte, 5-byte variant) | 516/1,068 = 0.483 stores tile completely (composite-space stores carry gap content); per-file 0.0-1.000 | established (observed) |
| F1w | reference width is per-record u8 or u16be (big-endian), chosen by the tiling law | every accepted record | established (observed) |
| F2 | facet references are lexicographic ranks of (x, y, z) into the pool | clean subset 1,290/1,300 = 0.9923 winding triangles parallel (walk-order control 0.2746; other axis orders <= 0.38); box 12/12 with 12 sign+ | established (clean-store scope) |
| F2b | the box worked example decodes to its six faces only under lex ranks | 1 store, 12/12 triangles | established (one store) |
| F2c | the lex mapping validates end-to-end on pool-only stores | 77/1,068 = 0.072 parts (the 76 souped stores + 1) | candidate (scope-limited) |
| F3 | 0x4a loops are triangle-strip segments (flip phase, reset per loop) | clean subset 1,274/1,284 strip triangles parallel (1,272 sign+); box 12/12 | established (clean-store scope) |
| F4 | 0x4c loops are closed polygons in ring order (Newell == stored normal) | 16/16 clean-store loops sign+; strip reading 16/16 sign-mixed (rejected) | established (clean-store scope) |
| F5 | winding law: CCW seen from the stored normal (RH rule) | 1,288 sign+ vs 2 sign- of 1,290 parallel (0.9984); counterexamples named | established (clean-store scope) |
| F6 | clean-store soups are manifolds; closed solids 66/76; oriented 66/66 closed | 76/76 = 1.000 manifold; 0.868 closed | established (clean-store scope) |
| F7 | zero degenerate triangles in the soups (skip convention applied) | 1,354/1,354 | established (clean-store scope) |
| F8 | composite index space: `01 02` edge groups + `ff`-opener trailer region; refs beyond pool | 889/1,068 = 0.832 stores; 793/889 refs beyond pool | candidate (numbering open) |
| F9 | 0x41: n == 3*type | 59/59 | established (byte law) |
| F10 | 0x49: n == 3*type; primitive semantics otherwise open | 3,722/3,722; one in-pool loop fails all readings | candidate (law); semantics open |

Version scope: F1-F10 measured on the 1,068 decoded stores of the
1,377 dev parts; the established scopes are the 179 pool-only
("clean") stores (76 of which soup), per-release rows in
`facet-semantics-claims.csv`.

## Unknowns / next questions (G4 pointers)

1. **The composite index space (the big one):** on `01 02`-carrying
   stores the references exceed the pool.  Evidence assembled: the
   `01 02` groups = 6-byte `02 02 (u16be)(u16be)` records whose
   endpoints are lex-adjacent pool vertices (edge/rim table);
   the `ff`-opener region = the trailer-named region (its u32le ==
   C) carrying curve records.  Candidates for the numbering: pools
   first then edges then curve points, or walk order with the edge
   table interleaved.  One controlled decode of 70b59f2a (1,164-vertex
   pool, 604 edges, 594 facets, max ref 1,819) should settle it.
2. **The 30 pool-only stores whose references still exceed the pool**
   (30/179 clean stores): a further element source (the `00 00`
   sub-kind wrappers seen next to `01 06` groups on box-family parts)
   or a second pool form.
3. **The 5-byte-header variant (0x4b/0x4e):** 446 gap-start records on
   105 parts; 0x4b carries a 12-byte normal (byte-verified) but its
   count law differs (count 5 vs n 8); 0x4e tails look nested
   (a count byte followed by sub-counted runs).  G2 unknown 6.
4. **0x44 and 0x41 primitive semantics:** both lack normals so the
   winding test is silent; 0x44 = 649 records with tails that parse
   only on some stores.
5. **0x49 primitive reading:** n == 3*type holds; the single in-pool
   loop fails strip/list/Newell — likely composite-space on its store.
6. **The 10 open shells:** confirm the sheet-body interpretation
   (rim-paired boundary edges) against a part with known content.

## Reproduction

```
python3 -I scripts/triage/decode_facet_semantics.py
python3 -I scripts/triage/decode_facet_semantics.py \
  --soup-sha16 369fc90b25b4977d --include-sha16 369fc90b25b4977d
```

Deterministic: file order is the sorted manifest order; three
consecutive runs produce byte-identical CSVs (md5-verified).  Runtime
~72 s.  Corpus binaries are not committed.
