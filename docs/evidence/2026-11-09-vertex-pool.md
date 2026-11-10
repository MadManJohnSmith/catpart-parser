# Evidence: the nested store's vertex pool, decoded (2026-11-09)

Ticket #30 (G2, spec D #28): locate and decode the coordinate arrays
the nested store's strip-index records point into. Scope: **all 1,377
dev parts** of the corpus manifest (`kind=part`, `split=dev`,
`magic_ok=yes`) — the same corpus-wide sample as G1, so per-release n
is the actual manifest count (marked lines R15-R24 have n = 14-544;
R25/R28/R32 n = 1, R26 n = 2; `unknown` n = 236). Method: read-only
byte analysis, `scripts/triage/decode_vertex_pool.py` (stdlib, mmap,
deterministic; run with `python3 -I`; ~65 s wall clock, three
consecutive runs byte-identical, md5-verified). Data:
`docs/evidence/data/vertex-pool-files.csv` (one row per part),
`vertex-pool-pools.csv` (one row per decoded pool group),
`vertex-pool-claims.csv` (per-claim, per-release rates). Builds on the
G1 nested-store model ([2026-11-09-nested-store.md](2026-11-09-nested-store.md),
which fixes the store origin/catalog/body extent used here) and B4's
strip-record grammar ([2026-11-08-geometry-payloads.md](2026-11-08-geometry-payloads.md));
those models are cited, not re-derived.

Labels: **established** = the byte-level model validates with rate
>= 0.98 on its scope (counterexamples named); **candidate** = below the
bar or otherwise unproven; every claim states whether it is a fact
(byte-measured), an inference, or an unknown.

The headline: **the pool is found and decoded — the strip records'
indices point into runs of 15-byte vertex records
`[05 08 01][f32le x][f32le y][f32le z]` inside `10 24`-wrapped pool
groups of the store body, and on every one of the 2,090 pool groups
corpus-wide the walked record count equals the group's count field
(1.000) with 100% finite f32le values.** The connectivity records
decode as facet/loop records with per-record unit normals and
loop-count bytes; the exact binding of facet clusters to pool groups on
multi-group stores is measured but not fully determined (open
question 1).

## 1. Pool location and the pool-group grammar (P1, P2)

G1 unknown 1 named three candidates: (a) the unnamed bulk between
origin+32/64 and the trailer region, (b) the trailer-named region
`[B, B+C)`, (c) the SurfacicReps payload region. Measured answer:

- **P1 (established, 995/1,377 = 0.723 parts; every release line
  positive):** the vertex pool sits in the store **body** — candidate
  (a) — as runs of 15-byte vertex records `[05 08 01][3 x f32le]`
  (prefix `05 08 01`, then three little-endian float32: x, y, z).
  2,090 pool groups corpus-wide carry 493,775 vertices. The trailer
  region (candidate b) is **not** the pool: it carries edge/curve
  records instead (a `02 00 33 32`/`02 00 33 36`-prefixed family with
  a `[P][Q][P]` f32le triple pattern and a trailing f32le length equal
  to the norm of the middle triple Q — e.g. (10, 0, 30) with 31.62 =
  sqrt(10²+30²); 6/6 on the small-store worked example, but `e9ca`'s
  trailer family decodes len != abs(Q) at the same offsets, so the
  family varies — semantics open, unknown 5), plus a directory of
  increasing u32le offsets.
  Candidate (c) is unresolved as a *region bound* (G1 unknown 3), but
  the pool's location does not depend on it.
- **P1g (established (observed), 2,090 groups):** pool groups are
  opened by the 8-byte wrapper `10 24 04 ff ff 00 00 00` followed by
  `01 06` (sub-kind 06 = vertex pool) and a **count field**: one byte
  when the count fits (<= 255), else `ff` escaping to a **u32le count**
  at +11. Both forms verified against the walked records (P2g).
- **P2/P2g (established, 2,090/2,090 = 1.000):** the group's vertex
  records follow contiguously and the walked count equals the count
  field on **every** group — the count field is a true vertex count,
  not a heuristic. This is the functional anchor of the pool decode.

## 2. Float format (P3, P4)

- **P3 (established, 2,090/2,090 groups):** the vertex coordinates are
  **little-endian float32** xyz triplets, one vertex per 15-byte
  record, interleaved (xyz per record — not separate component
  arrays). 100% of decoded vertices are finite (IEEE values); no
  f16/f64 vertices were observed in any pool group (a sample of 500
  record payloads per probed store also byte-verifies as f32le).
- **P4 (established at 0.973, 2,033/2,090 groups):** all three
  components of every vertex in 2,033 groups are "plausible mm-scale"
  (|coord| <= 1e5). The 57 exceptions carry |coord| up to 2.3e5
  (110-230 m-scale parts — e.g. `08ab03c16e7c` bbox to 140,000): the
  format is the same f32le grammar; only the **unit assumption** is
  strained there (unknown 4). The 1D float arrays with u32le counts
  found in some bodies (e.g. counts 911/1,602/2,018 in
  `e9ca6192a2854002`, strictly contiguous `count x f32le`) are a
  **second float family, not the vertex pool** (0 of 5,903 vertex
  records fall inside them in the worked example; semantics open —
  parameter/UV arrays, unknown 5).

## 3. Connectivity records — the facet grammar and the association rule (P5, P6)

The B4 strip-record family `01 <marker 0x41-0x4f> <type> ff [u32le n]
[n x u16be]` refines into four marker families (all byte-measured on
`e9ca6192a2854002` and the small-store worked example):

- **0x41 triangle lists:** n == 3*type (type = triangle count,
  observed 1..10), no normal, indices only.
- **0x49 triangles with normal:** n == 3*type, plus a 12-byte payload
  of three f32le = a unit normal (verified |n| ≈ 1) before the indices.
- **0x42 boundary loops without normal; 0x4a/0x4c boundary loops with
  normal:** n = total loop indices; k loop-count **u8 bytes** (k <= 3
  observed) precede the indices and **sum to n** (e.g. 6; 5+5;
  5+7+4; 13+5) — k is validated per record, not assumed.
- **Normals:** 12 bytes = 3 x f32le, unit-length where non-trivial;
  the writer writes near-zero components as fixed epsilon bit patterns
  (`00 00 00 a5` = -1.11e-16, `32 31 0d 25` = 1.225e-16, `2e f9 e4 24`
  = 9.93e-17 as f32le — normal-range magnitudes, not subnormals) — a
  byte-level fingerprint, not noise.
- **Index width:** u8 on every facet the committed decoder accepts
  corpus-wide (the 8-vertex worked example stores indices as single
  bytes). A manual probe read pools of 257-746 vertices as u16be, but
  the committed decoder emitted no u16be facet on the sample (its u8
  accept covers what it measured; indices > 255 need a per-group parse
  it does not perform) — per-group width/binding is open question 1,
  and G3 must not treat the manual-probe numbers as reproduced.

- **P5/P6 (candidate, 612/1,377 = 0.444 parts; 834/1,377 = 0.606 have
  strictly-unresolved candidates):** on 612 parts at least one B4 strip
  candidate strict-parses AND resolves in-bounds under this grammar;
  on 834 parts some candidates remain unresolved — the facet grammar
  has further writer variants on large bodies (per-file strict rates
  span 0.000 (`006395786be0df4e`, R19, 0/12) to 1.000
  (`ff60483c070b8f5d`, R21, 17/17); among unresolved-carrying parts
  0.0-0.999; among >= 100 MB bodies 0.0114 (`17930babf0fd01a8`, the
  375.7 MB R20 part, 770/67,265) to 0.9056). On stores with no decoded
  pool a grammar-shape accept counts as unresolved, never strict (the
  in-bounds test is vacuous there — one part, `bf3508200ac996ea`, 4
  candidates). The grammar above is a byte-level fact on the worked
  examples; corpus-wide it is **incomplete** — labeled candidate.
- **Association rule (the G3-facing statement):** indices are **local
  to their pool group** (the 8-vertex worked example: all six facet
  records index 0..7 = exactly its pool). Facets bind to the pool of
  their enclosing store section; **on stores with a single pool group
  the binding is unique and the functional test passes exactly**. On
  multi-group stores the per-segment binding is **open**: facet
  clusters sitting between two pool groups show max indices up to
  ~2x the neighbouring group count (a manual probe on `e9ca6192a2854002`
  reads segments of its four identical 257-vertex groups indexing
  233..381 — not yet reproduced by the committed decoder, which emits
  no >255-index facet corpus-wide; see the index-width note above) —
  consistent with either a section-level cumulative base
  or clusters serving both neighbours; not determined here. The
  functional test as run (indices < the store's total decoded vertex
  count) is the P6 rate.

## 4. Units and scale (P9, P10)

CATStdCont/CATStorageProperty sizes carry no units, so the evidence is
magnitude plausibility + distribution (B4's sanity frame):

- **P10 (established (observed), 995/995):** every pool-carrying part
  has a non-degenerate bbox from decoded vertices.
- **P9 (candidate, 970/995 = 0.975):** max |coord| <= 1e5 on 970
  parts. Measured distribution over the 995 pool-carrying parts:
  median max |coord| 55.0, deciles [7.6, 20.5, 31.7, 45.0, 55.0,
  80.0, 140.9, 410.6, 1500.0], max 230,000 (`9b0995f4bf7c`, R20) —
  consistent with mm-scale CAD for ~97.5% of parts; the 2.5% tail
  (110-230 m) keeps the unit question open (mm is the plausible but
  unconfirmed assumption — the format carries no unit field we
  decoded). Size-stratified spot checks (41 KB -> 0.6; 103 KB ->
  185.4; 250 KB -> 55.0; 742 KB -> 1.0; 375.7 MB -> 39.0) show the
  scale tracks part content, not file size — no unit conclusion from
  size.

## 5. Worked example (end-to-end)

**`10b9ae4a3cd58298`** (R26 part, `SSadayuki/B31CAADoc`, 55,689 B):
store origin at block + 252 (G1 header variant), body 1,729 B. Decoded
end-to-end: **1 pool group, count field 8, walked 8 vertex records**
(15 B each, `[05 08 01][f32le xyz]`), bbox (0..20, 0..100, 0..60) — the
8 corners of a 20 x 100 x 60 box (mm assumed); **6 facet records**
(0x4a/1, each `01 4a 01 ff | u32le 4 | 12-B normal | u8 count 4 |
4 x u8 indices`), normals (0,0,-1), (0,1,0), (0,0,1), (0,-1,0),
(-1,0,0), (1,0,0) — the six face normals of the box; indices
(4,0,6,2), (6,2,7,3), (7,3,5,1), (5,1,4,0), (0,1,2,3), (4,6,5,7) —
four-corner loops per face, **all 6/6 resolve in-bounds (max index 7 <
8)**. The body additionally carries a 12-edge list (`01 01 0c` +
`02 v1 02 v2` pairs) and the trailer region starts with the
edge-geometry records. G1's own worked-example store
`e9ca6192a2854002` decodes to 17 pool groups / 5,903 vertices, bbox
(-29.99..33.99, -13.99..13.99, ..10.05), 1,783/3,347 strip candidates
strict-resolving in-bounds.

Reproduction of the worked example numbers:

```
python3 -I scripts/triage/decode_vertex_pool.py \
  --include-sha16 10b9ae4a3cd58298 --out-dir /tmp/vp-we
```

## 6. Variants, classified with rates

- **B4's "float64 store" `086a4effaab7` (reclassified, correction C6):**
  its 4.58 MB nested store carries a **normal f32le pool** — 1 pool
  group, 916 vertex records, 100% finite and plausible — with **20 B4
  strip candidates, none strict-resolving** (the store's second
  `10 24` wrapper opens `ff 70`, not `01 06` — not a pool group; the
  916 records of group 1 end exactly at it). The "float64 coordinate
  data" impression came from other body content; the pool format does
  not differ. It is a **pool without verified connectivity** (P7's
  zero-candidate definition does not apply), not an encoding variant.
- **P7 pool-without-strips (established (observed), 36/1,377 =
  0.026):** 36 stores decode pool groups but carry **no** B4 strip
  candidates at all — pools without connectivity are a real, if
  small, family (related to G1 unknown 7: pools can exist without
  strips; *why* G1's 12 SurfacicReps-less stores carry none stays
  open).
- **P8 strips-without-pool (established (negative at 3/1,377 =
  0.002)):** only 3 parts show strip candidates with no decodable
  pool group — the pool is present essentially whenever strips are.
- **P6u unresolved-facet variants (candidate, 834/1,377 = 0.606):**
  the remaining gap is grammar coverage on large bodies (further
  marker/normal variants), not pool absence — the pool decodes on
  100% of its groups regardless (P2g).

## 7. Corrections to the B4 model (recorded, none massaged)

1. **C6 — the float64 variant:** B4 recorded `086a4effaab7`'s nested
   store as "float64 coordinate data with zero strip records"; the
   pool decode shows f32le vertex records (1 group, 916 vertices) with
   20 strip candidates none of which verify, and the float64 impression
   belongs to other body content. The store is a pool without verified
   connectivity.
2. **C7 — strip-record payload structure:** B4's grammar treated
   markers 0x41-0x4f as one family with u32le n + n x u16be; the
   decode adds the 12-byte normal payload (0x49/0x4a/0x4c), the
   loop-count bytes summing to n (0x42/0x4a/0x4c), the n == 3*type
   law for triangle families (0x41/0x49), and the adaptive u8/u16be
   index width. Many B4 "verified" records are misaligned parses of
   these richer records (their index reads as be/le artifacts).

## Claims

| claim | statement | rate | label |
|---|---|---|---|
| P1 | vertex pool in the store body: 15-B records `[05 08 01][f32le xyz]` in `10 24`-wrapped `01 06` groups; trailer region holds edge geometry, not the pool | 995/1,377 = 0.723 parts, every release line positive | established (observed) |
| P1g | pool-group opening: wrapper + `01 06` + count (u8, ff-escape to u32le) | 2,090 groups | established (observed) |
| P2/P2g | walked vertex-record count == group count field | 2,090/2,090 = 1.000 (per-group); 995/1,377 = 0.723 parts all-groups-ok | established |
| P3 | vertex coordinates are f32le xyz triplets, interleaved, 100% finite | 2,090/2,090 groups | established |
| P4 | coordinates plausible mm-scale (<= 1e5) | 2,033/2,090 = 0.973 groups; exceptions 110-230 m-scale | candidate (unit tail open) |
| P5 | facet grammar (normals + loop counts + triangle lists) strict-parses strip candidates | 612/1,377 = 0.444 parts have >= 1; per-file 0.000-1.000 | candidate (grammar incomplete corpus-wide) |
| P6 | functional: strict facet indices resolve in-bounds (< store total vertices) | 612/1,377 = 0.444 parts; exact on single-pool stores | candidate (multi-group binding open) |
| P6u | strict-unresolved strip candidates remain (further facet variants) | 834/1,377 = 0.606 parts | established (observed) |
| P7 | pool without any strip candidates (pools can exist without connectivity) | 36/1,377 = 0.026 | established (observed) |
| P8 | strip candidates without any pool group | 3/1,377 = 0.002 | established (negative) |
| P9 | bbox max \|coord\| <= 1e5 (mm-scale sanity) | 970/995 = 0.975; median 55, p90 1,500, max 2.3e5 | candidate (unit assumption) |
| P10 | decoded-pool bbox non-degenerate | 995/995 | established (observed) |

Version scope: P1-P8 hold on every release line R15-R32 + `unknown`
(per-release table in `vertex-pool-claims.csv`); single-file lines
(R25/R28/R32, R26 n = 2) are stated as-is.

## Unknowns / next questions (G3 pointers)

1. **Facet-to-pool binding on multi-group stores:** facet clusters
   between two pool groups index up to ~2x the neighbour count —
   section-cumulative base vs dual-cluster service; needs one
   controlled decode of a mid-size multi-group part (the small-store
   and single-group cases are exact).
2. **The remaining facet families** (0.606 of parts keep unresolved
   candidates; strict rates 0.029-0.906 per file): further
   marker/normal/writer variants on large bodies — extend the
   grammar from a mid-size part with a low strict rate.
3. **The 1D counted float arrays** (counts like 911/1,602/2,018 in
   the worked example): strictly contiguous f32le runs, NOT vertex
   pools — parameter/UV candidates; semantics open.
4. **Units:** no unit field decoded; mm is plausible at 0.975 within
   1e5 but the 110-230 m tail is unexplained (import-scale parts or
   non-mm units).
5. **The edge-geometry records** (trailer-region family `02 00 33
   32/36` + triplet + length; `02 v1 02 v2` edge lists in the body):
   grammar sketched, semantics (curve/edge tessellation) open.
6. **The 0x4e marker family** (5-byte header variant `01 4e 01 01 ff`)
   seen 39 times in `e9ca6192a2854002` (absent from the small-store
   worked example): layout undecoded here.
7. **The 11-vertex-pool-less strip candidates** (P8 = 3 parts): what
   their stores carry instead.

## Reproduction

```
python3 -I scripts/triage/decode_vertex_pool.py
```

Deterministic: file order is the sorted manifest order; three
consecutive runs produce byte-identical CSVs (md5-verified). Runtime
~65 s. Corpus binaries are not committed.
