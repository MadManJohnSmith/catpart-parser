# Evidence: the list-node point streams and the recovered merge law (2026-11-10)

Ticket #34 (G6, stage 2b): crack the list-node point streams (the
big-store encoding, stage-2a unknown 1) and recover the exact merge law
(M1's outstanding planarity confirmation, stage-2a unknown 4). Analysis
+ decoder only — `src/` untouched, no fitness writes, no publication.
Method: read-only byte analysis,
`scripts/triage/decode_node_streams.py` (reuses the shipped
`catpart.geometry` scanners; stdlib + mmap, deterministic, sorted
manifest order; ~72 s wall clock over 1,442 parts; 1 audit error).
Data: `docs/evidence/data/node-streams-files.csv` (one row per part).
Builds on the stage-2a decode
([2026-11-10-composite-space.md](2026-11-10-composite-space.md)); that
model is cited, not re-derived. Anchors hand-decoded byte-by-byte:
026d6726007381a9 (the worked list node), 70b59f2a0eb60c1c (the settle-it
big store), e254a37e (second full merge-law validation), 0018baa8 and
02ee1544 (form comparison).

Labels: **fact** = byte-measured here and reproducible from the CSV;
**inference** = interpretation of measured bytes, named as such;
**unknown** = open. The house bar (established = validates at >= 0.98
on its scope) is applied mechanically; below-bar claims stay candidate.

The headline: **the point-stream encoding is one law on both forms** —
the list node's point region is a lex-nondecreasing point list stored
with suffix-after-LCP prefix coding (each point writes only the suffix
it does not share with its predecessor: [x][y][z] at a segment/x-group
start, [y][z] after an x repeat, [z] after an (x, y) repeat; f32le) —
and **the merge law is recovered**: the element space is the lex-sorted
merge of the pool vertices and the node's decoded points (plus the
curve-record points), references are 0-based positions in that
sequence, and on two independent stores (026d6726, e254a37e) every loop
of the `01 4a 07 ff` record (normal (0, 0, -1)) decodes EXACTLY planar
at z = 2.1 — all 7 loops, with the curve entries inserting a monotone
shift totaling exactly element_count − node points (26 = 124 − 98).
M1's outstanding confirmation is delivered on the anchors; M1 stays
candidate pending corpus-wide automation (the DP start-selection
currently full-decodes 5/285 small-form stores — the failure mode is
the automated region-start selection, not the law; every store where
the decode completes validates, 5/5).

## 1. The point-stream law (P1, fact on the anchors)

- **P1 (fact, byte-exact on 026d6726):** the list node's payload =
  header (29 B: `00 00 00 01`, node id, flags, origin xyz f32le,
  kind u32le) + token `ff ff 02 00 01` + two P1g counts
  (element_count, edge_ref_bound) + `00 00 00 00` + a per-node table
  (32 B here; semantics open, U1) + **the point region** + a trailing
  region (tolerance f32 + `00 04 02 0a` + P1g count, then further
  tables; semantics open, U2). On 026d6726 the point region =
  payload[72, 884) = 812 B = 203 f32 writes decoding to **exactly 98
  lex-nondecreasing points** (DP: 3 candidate parses, the pool-max
  parse unique at pool 10/10). The stage-2a hand-verified examples
  reproduce verbatim: `(392.65, 434.74, 2.3975) -> (392.65, 436.26,
  2.3975)` written as `[436.26, 2.3975]`; `(392.82, 434.60, 2.81) ->
  (392.82, 434.60, 2.9)` written as `[2.9]`; pool v1 (392.219879,
  435.5, 2.1) is the list's first point, full write.
- **The 98 points are 6 perfect circles** around the node origin's
  (x, y) = (395.0, 435.5): (z=2.1, r=1.55, 14 pts at 25.714° steps),
  (z=2.1, r=2.78, 18 pts at 20°), (z=2.3975, r=2.47, 20 pts at 18°),
  (z=2.81, r=2.36, 16 pts at 22.5°), (z=2.9, r=1.55, 14 pts),
  (z=2.9, r=2.36, 16 pts) — 98 total. The pool's 10 vertices are the
  axis-aligned samples of these circles (re-listed verbatim 10/10 at
  node indices 0, 4, 5, 20, 21, 76, 77, 92, 93, 97).
- **P2 (fact, big form):** 70b59f2a's list node (17,592 B) has the
  same header/token/counts (1,820, 1,812) and the same law: every
  pool x value is written ONCE (40 distinct x = 40 x-groups; the
  x=5258.914 group's 26 pool points decode as `[x][y][z]`-then-`[y][z]`
  pairs exactly, byte-verified), and the x-groups appear in ASCENDING
  x order across an 11,264-B point region (2,816 f32 writes ≈ 1,820
  points at ~1.55 writes/point). Two 4-point corner groups
  (x = 5210, 5900) sit in a tail segment with their own table —
  the stream is SEGMENTED (per-segment table + point block; the
  026d/70b59f2a segmentation bookkeeping is open, U3). The stage-2a
  "compressed-stream statistics" (runs of `77`/`bb`/`ff`) are the
  per-node 2-bit tables and segment tables — not a different encoding.
- **Form census (fact, 939 composite stores; 2026-11-10 correction
  (#34 review F1): the first wording said 938/284 — a zero-count loop
  crashed `plane_test` and silently dropped 8be9434a from the CSV;
  guarded, rerun, the census covers all 939 = 285 small / 654 big):**
  the list node =
  the LARGEST token-bearing node (every node carries
  `ff ff 02 00 01` + the declared counts — the stage-2a "list-node"
  census counted all of them). 285 small-form (108-4,096 B, median
  1,335), 654 big-form (4,144-2,516,042 B, median 19,295 —
  2026-11-10 correction (#34 review F2): 19,334 was never
  CSV-composable); 5 stores
  have element_count == pool_size (the empty-list degenerate, N4
  refined: 5/939, not 4/939); element_count > pool on 873, < pool on
  61 (the stage-2a residue, re-measured under the largest-node
  reading).
- **Reading note (2026-11-10, #34 review F3):** stage-2a's
  `element_count_declared` took the max count over ALL token-bearing
  nodes; this stage takes the largest-payload node's counts — the two
  disagree on 50 stores (same pool). The arbiter is N2 itself: the
  largest-node reading satisfies element_count == max_ref_all + 1 on
  35/50 disputed stores, the max reading on 0/50 (10 more carry no
  refs) — the stage-2b reading stands, and stage-2a's GE-N2N3 rates
  rest on the superseded reading (strict == 713/916 = 0.778 ->
  748/916 = 0.817 re-measured; the degenerate 4->5 and residue
  59->61 bucket changes follow).

## 2. The merge law (M1 confirmation, fact on the anchors)

- **M2b (fact, 2 stores):** with the decoded node points, the
  `01 4a 07 ff` record (normal (0, 0, -1); loops (6,7,7,6,7,7,6)
  summing to n = 46) validates under the recovered law: refs are
  0-based positions in the lex-sorted merge of pool ∪ node points ∪
  curve entries; for each of the 7 loops the loop's distinct refs map
  order-preservingly onto the decoded z = 2.1 points with a MONOTONE
  non-negative shift (the curve entries inserted before each plane
  point), and every mapped point has z = 2.1 — **all 7 loops exactly
  planar**. On 026d6726 AND e254a37e: pool 10, 98 node points,
  element_count 124, shift total 26 = 124 − 98. Loop 0
  (17, 2, 27, 1, 18, 3) maps to node points 0, 1, 2, 12, 13, 20
  (the shift profile 1,1,1,5,5,7 — the first curve entry sorts before
  the list's first point; the loop-0 refs and profile are
  026d6726-specific — on e254a37e loop 0 = (17, 1, 28, 0, 18, 2) with
  shifts starting at 0, 2026-11-10 #34 review F5).
- **M2c (inference, strong):** the curve entries are the curve
  records' points. On 026d6726 the curve records (24-25 by
  composition: 12 x `33 37` + 2 x `33 38` + 4 x `33 33` + 2 x
  `33 32` + 4-5 x `33 36` — 2026-11-10 correction (#34 review F5):
  the first wording said 22, which does not compose; the `33 36`'s
  record-boundary bookkeeping is fuzzy) decode as circle
  definitions matching the node's circles exactly — `33 37` = (cx, cy,
  z, r) BE f32 + 2-B trailer (12 records: FIVE of the six circles x2
  plus two slot arcs r=0.81 at (391.83, 435.5, 2.81) / (398.17, 435.5,
  2.81) — an obround slot whose tangent points ARE pool v0/v3; the
  (z=2.3975, r=2.47) circle is not a `33 37` record — 2026-11-10
  correction (#34 review F5));
  `33 38` = 3 BE f32 + zeros + params (-3.17, 0.81) + a 38-B LE block;
  `33 33` = same shape with one negative-radius param (-2.36 / -1.55)
  and z = 2.855 / 1.855 (the mid-plane circles);
  `33 32` = a 38-B [P][Q][P]-shaped LE block (P = the plate centers
  (395.0, 435.5, 2.9) / (395.0, 435.5, 2.1));
  `33 36` = a 2-B trailer only. The families tile the region exactly
  (33 37 stride 27 B, 33 36 stride 11 B). Which points each record
  contributes to the space (anchor vs endpoints vs samples) stays
  open (U4) — but their COUNT is pinned: 26 = element_count − node
  points, and the shift profile 1-4-2-1-2-2-2-1-3-7-1 pins where they
  sort.
- **M1 status:** the numbering law's construction is now documented
  (0-based positions, pool absorbed via the node list's verbatim
  re-listing, curve entries interleaved, global lex sort, no dedup
  between curve and node entries). It stays **candidate** — the
  corpus-wide automation (the DP start-selection) full-decodes only
  5/285 small-form stores; every completed decode validates (5/5:
  026d6726, e254a37e with the 7-loop planarity + shift law; 0710a58b,
  fa779a78, ff842b8a with pool fully contained and
  element_count == node points). The winding re-run on 70b59f2a is
  blocked on the segment bookkeeping (U3) — the stage-2a 0.5153
  half-rate figure is superseded by the byte-verified x-group trace
  but not yet replaced by an end-to-end winding number.

## Unknowns carried forward

1. **U1 — the per-node 2-bit table**: SOLVED 2026-11-11 (stage 3b,
   below) — 2 bits per element, LSB-first: 0 = `[x][y][z]`, 1 = skip
   (curve entry), 2 = `[z]`, 3 = `[y][z]`; the table spans exactly
   ceil(element_count / 4) bytes and is followed by a P1g count of the
   region's f32 words.
2. **U2 — the trailing region** of each list node (026d: payload[884,
   1452), 568 B of nibble-ish runs + floats ~10.88 + the tail
   signature): present on every anchor, per-store size varies; open.
3. **U3 — segment bookkeeping on big stores**: RESOLVED for the
   single-table family 2026-11-11 (stage 3b, below) — one table + one
   write count cover the whole region, no per-segment tables; the
   corner groups sit at their element slots.  A second layout family
   (~14% of big-form stores) stays open (multi-node payloads).
4. **U4 — curve-point participation**: refined 2026-11-11 (stage 3b):
   the curve entries are the table's skip slots (value 1) — they are
   IN the element space at known indices and ARE referenced by facet
   loops (M2c's "never referenced" inference corrected); their
   coordinates are still not in the region (the curve records remain
   the candidate source; 100/104 skip slots on 70b59f2a have both
   written neighbours sharing 2 coordinates, bracketing the missing
   values).

## Stage 2c: the decode hardened and integrated (2026-11-11, #34)

Stage 2c moved the decode into `src/catpart/geometry/composite.py`
(the exporter's path, fail-closed) and hardened the automation.  The
DP start-selection that full-decoded 5/285 small-form stores is
replaced; the failure census (272/280 failures produced no parse, 8
partial) resolved into five byte-measured refinements of P1, each
verified on the anchors and the corpus:

1. **P1t (fact, 2 anchors + corpus):** the per-node 2-bit table (U1)
   spans `ceil(element_count / 4) + 1` bytes after the zero block —
   32 B for 124 declared on 026d6726, 41 B for 160 on 0313b53d
   (region starts payload[72] and payload[81] respectively).  U1's
   semantics stay open; the length is what the start prediction needs.
2. **P1i (fact):** the stream's initial LCP state carries **x = 0.0
   implicitly** — the first point writes `[x][y][z]` only when its x
   differs from 0, else `[y][z]`.  On 0313b53d the region opens with
   the pool lex-min's `[y][z]` (its x = 0 is never written); 026d6726
   opens with a full write (x = 392.2 ≠ 0).  One law, both forms.
   This single rule dissolves most of the "extras-before-lex-min"
   residue the stage-2b dispatch named: those lists open with the
   pool's x = 0 vertices, not with extras.
3. **P1r (fact, 1b1e69cd):** the stream is a concatenation of
   **lex-nondecreasing runs**; each run starts with a full `[x][y][z]`
   write and may reset x (1b1e69cd: run A covers x 98980.95..99032.89,
   run B restarts at x 98873.89 — 44 points = element_count, pool
   24/24).  **Correction (2026-11-11):** stage-2b's "the point region
   is a lex-nondecreasing point list" holds per run, not globally;
   the merge law's global sort is what makes the space lex-ordered.
4. **P1n (fact):** the region ends where the law's content ends — no
   parse extends into the trailing region under the lex law (verified
   on 0313b53d: every end past the pool lex-max's write fails).
5. **The decode is a value-DP** over (position, last point, point
   count) states maximising pool containment, the count law
   (element_count = node points + curve entries ≥ 0) pruning
   over-parses, and the predicate widened to accept an exact 0.0
   coordinate (origin-placed geometry writes it; sub-normal noise
   stays rejected).

**Correction (2026-11-11, #34 stage 2c):** the stage-2b reading
"the first curve entry sorts before the list's first point" (loop-0
shifts starting at 1) is superseded — the edge table's first record
references position 0, so merged position 0 is the list's first node
point and the profile opens at shift 0 (M2b's σ form below).  The
stage-2b loop mappings were per-loop greedy matchings; the joint
constraint (one monotone profile + every facet reference resolving to
a node point + the normal-carrying loops planar) is the stronger law
and changes those per-loop shift figures.

**M2b's σ form (fact on 026d6726, the exporter's validator):** the
merged space is positions 0..element_count-1, each position a node
point (in list order) or a curve entry.  A solution = the assignment
satisfying (a) every facet reference resolves to a node point (curve
entries are never referenced — they are construction geometry; on
026d6726 the 84 distinct facet references all resolve), (b) every
normal-carrying record's loop maps onto points sharing one constant
coordinate on the normal's dominant axis, (c) the counts hold
(npts node positions + curves).  On 026d6726 the CSP reproduces the
anchor's planarity end-to-end and pins σ(97) = 26 = element_count − 98.
Stores where several solutions produce distinct meshes (the
unreferenced positions' node/curve choices unpinned) fail closed.
Stores with curve entries = 0 force σ ≡ 0 and export directly.
Superseded on skip-carrying stores (2026-11-11, #34 stage-3b review
F1, stage-3b item 7): the identity reading pins every position's
node/curve type off the decoded 2-bit table — the "2 ambiguous"
fail-closed entries (026d6726, e254a37e) dissolve and condition (a)
("curve entries are never referenced") is corrected (loops DO
reference skip slots); what blocks those stores now is U4.

Coverage (2026-11-11, this stage): small-form point-region decode with
pool fully contained rises from **5/285 to 70/285** (38 lex + 32
run-reset; the widened probe + count-law pruning recovers the implicit-x0
openers and the run-split streams); the composite export (decode + loop
law + unambiguous mapping) covers **34/285** small-form stores (24
lex-stage + 10 run-reset; 2026-11-11 correction (#34 stage-2c review):
the first wording said 24/285 — a pre-reset-stage gate number; the
committed code and the fitness run both measure 34, mapping 1:1 onto
the fitness movement; 2026-11-11 relabel: the fail-closed census is
236 unabsorbed-pool + 12 no-consistent-profile + 2 ambiguous
(026d6726, e254a37e) + 1 no-parse + 34 exported) — each with its
specific reason in the exporter's error
detail).  Big-form stays undecoded (U3).

## Stage 3b: the 2-bit table decoded, big form unblocked (2026-11-11, #34)

Stage 3b attacked U1 and U3 on the big-form point region.  Analysis +
decoder only — `src/` untouched; the committed decoder is
`scripts/triage/decode_big_form_points.py` (corpus runner, one row per
store in `docs/evidence/data/big-form-points-files.csv`).  The
breakthrough: the 2-bit table's semantics fall out of a DIRECT walk —
no DP — once the table's extent is corrected.

1. **P1t corrected (fact, all anchors + corpus):** the per-element
   2-bit table spans **exactly ceil(element_count / 4) bytes** after
   the zero block, followed by a **P1g count of the region's f32
   words** (1 B, `ff` escapes to u32le on big regions), then the
   region.  The stage-2c "+1 byte" was the count byte miscounted into
   the table span (026d: table [40, 71) = 31 B for 124 elements +
   count `cb` = 203 at [71, 72); 70b59f2a: table [48, 503) = 455 B
   for 1,820 + count `ff 00 0b 00 00` = 2,816 at [503, 508) —
   508 + 4·2,816 = 11,772 exactly where the trailing region begins).
2. **U1 solved (fact, byte-exact on 4 anchors, corpus-measured):** the
   table is 2 bits per element, **LSB-first within each byte**, one
   slot per element in region order; the value is the element's write
   shape in f32 words: **0 = `[x][y][z]` (3, an x-write/run start),
   1 = skip (0 — the curve entries: no coordinates in the region),
   2 = `[z]` (1), 3 = `[y][z]` (2)**.  The stage-2b "8 mappings 0/8"
   dead-end came from summing over 128 slots on 026d (the count byte's
   bits included) and from reading the 460 B before 70b59f2a's region
   as table-only.  The walk is deterministic and consumes exactly the
   declared write count on the anchors (026d/e254a37e: 203 words = 98
   points + 26 skips; 70b59f2a: 2,816 words = 1,716 points + 104
   skips; 0313b53d: 247 = 160 + 0; 1b1e69cd: 100 = 44 + 0).  P1i is
   subsumed: the initial LCP state is the origin, and the table
   encodes the first write's shape like any element's (0313b53d opens
   `[y][z]` with table slot 3; 70b59f2a opens `[x][y][z]` with slot 0).
3. **U3 resolved for the single-table family (fact on the anchors,
   corpus-measured):** there are NO per-segment tables and no segment
   headers on the decoded family — ONE table + ONE write count cover
   the whole region.  The x-groups/runs are delimited by the value-0
   slots (P1r's runs); the big-store corner groups sit OUT of x order
   at their element slots (70b59f2a: elements 1,812-1,819 = two
   4-point groups at x = 5210/5900, table pattern 0,2,3,2 each =
   `[x][y][z],[z],[y][z],[z]` byte-exact as stage-2b traced, with ONE
   x-break at element 1,812; all 8 are pool vertices).  The stage-2b
   reading "the tail segment has its own table" is corrected: the
   single table's slots 1,812-1,819 carry the corner patterns.
4. **M2b refined (fact on the anchors, corpus-measured):** facet and
   edge references are **0-based element indices in region order**
   (identity — the element space IS the region's element sequence;
   no sigma search).  Evidence: on 70b59f2a max_ref = 1,819 =
   element_count − 1 (N2 exact) and every normal-carrying loop's
   refs resolve to points sharing the loop's plane.  The stage-2b/2c
   "monotone shift profile" was the search artifact of matching refs
   onto WRITTEN-point indices; the shift = the number of skip slots
   before the point, automatically monotone.  The M2c inference
   "curve entries are never referenced" is CORRECTED: loops reference
   skip slots on every anchor with skips (3 of 7 loops on 026d, 26 of
   316 on 70b59f2a) — curve entries are loop vertices whose
   coordinates live in the curve records (U4).
5. **The loop plane law is coplanarity against the record's stored
   normal (fact on the anchors):** all (p − p0)·n ≈ 0 (max residual
   5.4e-05 on 70b59f2a, f32 rounding scale).  The stage-2b
   axis-constant reading was too strict: the big store's corner quads
   are slanted planes (e.g. the x = 5210/5900 corner quad's normal
   (-0.083, -0.997, 0)).  On 70b59f2a: 316 normal-carrying loops =
   **290 coplanar + 26 skip-ref + 0 nonplanar**; on 026d/e254a37e:
   7 loops = 4/2 coplanar + 3/5 skip-ref + 0 nonplanar.  Record
   reference width: u16be on all 292 normal-carrying records of
   70b59f2a; the width disambiguation adds a **no-repeated-refs rule**
   (a u8 misread of a u16be record repeats refs inside the loop).
   Correction (2026-11-11, #34 stage-3b review F4a): 70b59f2a carries
   **26 `counts=(8,)` records, occurring as 13 adjacent 37-B pairs**
   (the first member's u16be parse tiles exactly to the second's
   header); "the 13" of the stage-3b wording are the width-ambiguous
   (non-exact-tiling) half — the pairs' second members — and the
   13/13-coplanar-as-u16be figure holds on the WRITTEN (non-skip)
   refs: the battery itself classes those 13 loops skip-ref (each
   carries skip slots whose coordinates live in the curve records,
   U4).
6. **Corpus rates (fact, 950 composite stores audited; 22 audit
   errors, all layout: 21 region overruns + 1 table overrun).
   Correction (2026-11-11, #34 stage-3b review F2): the first wording
   said 933 audited / 28 errors with "6 without strip headers" — the
   6 crashing stores (88ad0be6, a7aef50e, ac9483aa, ae85fae7,
   bad44bdf, fd4201aa) carry 16-177,122 strip headers and crashed
   because the loop battery read refs in [len(elements), elem_decl)
   after the walk broke early on second-family stores (unguarded
   `elements[ref]`); guarded, they get real battery rows (2,408 of
   their 5,761 normal-carrying loops reference the unwalked window
   and class `beyond`, untestable here), and 11 further stores the
   committed CSV recorded as empty rows although the committed script
   decodes them are restored by the rerun (CSV regenerated against
   its script):**
   - the walk consumes exactly the declared write count on **557/661
     big-form (0.843) and 272/289 small-form (0.941)** stores;
   - the pool is fully re-listed in the decoded points on **465/557
     decoded big (0.835) and 216/272 decoded small (0.794)** —
     the headline: **465/661 big-form stores decode end-to-end**
     (walk + finite words + pool absorbed); big-form was 0/654
     before this stage;
   - the small-form pool-containment rate rises from the stage-2c
     DP probe's 70/285 to **216/272** under the table-driven walk
     (deterministic, no probe);
   - elem_decl == max_ref + 1 on 422/533 decoded big (0.792) and
     225/270 decoded small (0.833) ref-carrying stores;
   - the loop battery over decoded stores: big 32,541 loops =
     16,912 coplanar (0.520) + 12,646 skip-ref (0.389) + 2,983
     nonplanar (0.092) on 425 walk-exact big stores with loops;
   - **the nonplanar decomposition (2026-11-11, #34 stage-3b review
     F3; committed criterion, replaces the unreproducible 60-store
     sample):** every nonplanar loop of the walk-exact big-form
     stores — 2,983 loops on 425 stores — is classified by
     normal-direction clustering with unsigned cosine >= 0.999
     (`decode_big_form_points.py --planes`; committed per-loop run
     in `docs/evidence/data/big-form-planes-loops.csv`): **multi-plane
     (d = 2-3 distinct triangle-normal directions) 1,595/2,983 =
     0.535** — fillet/bevel strips where the whole-loop coplanarity
     does not apply and the per-triangle strip law (6.3.1 GE-F3/F5)
     is the applicable test; single-plane-uniform (d = 1) 1,072 —
     the loop's own triangles agree on one direction, and on 651 of
     them the stored normal disagrees grossly (cos1000 < 500: the
     battery's nonplanarity there is a stored-normal disagreement,
     not multi-plane geometry; 123 have the stored normal agreeing,
     cos1000 >= 999 — flat loops mis-tested against a foreign
     normal); a 4+-plane tail 301; 15 loops with no measurable
     (non-degenerate) triangle.  Families: 0x4A 2,653, 0x4C 285
     (210 of them 4+-plane — curved ring fans), 0x49 45 (primitive
     reading open, GE-F9).  Correction (2026-11-11, review F4b): the
     earlier "84%" was the multi-plane share of the SAMPLE's
     nonplanar (2,421/2,895 over 60 stores), not of its 2,571 0x4A
     strips (that would be 94%); the committed-census denominator is
     the 2,983 nonplanar loops of the 425 walk-exact big stores with
     loops.  The review's band (multi-plane ~1,900-2,150 of
     ~2,2xx-2,895 depending on criterion) sat higher than the
     committed criterion's 1,595 — recorded, not massaged: the
     single-plane-uniform residue the committed criterion isolates
     (stored-normal disagreements) is a real class the sample's
     reading folded into multi-plane.
   - the battery share restated under the committed criterion
     (review F3): **coplanar + skip-ref + multi-plane = 31,153/32,541
     = 0.957 of the testable loops** — below the 0.98 house bar, so
     the M2b-element-index battery clause is relabeled **candidate**
     (the review's honest full-census band 0.972-0.978 was
     criterion-dependent; the committed criterion's figure stands
     until a criterion establishes itself above the bar).

7. **Exporter consequence (2026-11-11, #34 stage-3b review F1;
   inference from the identity law and the decoded table — no export
   run was executed):** the identity reading (item 4) dissolves the
   stage-2c mapping ambiguity on 026d6726/e254a37e — the fail-closed
   census's "2 ambiguous": once the 2-bit table is decoded, every
   position's node/curve type is read off the table (slot value 1 =
   curve entry, else node point) — no sigma search, no unpinned
   choices.  The remaining blocker on those two stores is U4: 3/7 and
   5/7 of their loops reference skip slots whose coordinates are not
   in the region (the curve records remain the candidate source).
   The zero-skip stores (0313b53d, 1b1e69cd) decode and would export
   directly under identity.  The shipped `composite.py` sigma
   validator — including its "curve entries are never referenced" CSP
   condition (M2c's corrected inference) — is superseded on
   skip-carrying stores; the exporter integration of big form is a
   later stage (src/ untouched here).

**Residue (open, named):** ~16% of big-form stores (104 walk-mismatch +
22 layout overruns; 2026-11-11 stage-3b review F2 correction: was ~14%,
94 walk-mismatch — the rerun restores 10 more walk-mismatch big stores:
the 4 previously-crashing big stores plus 7 CSV-stale rows, one of them
walk-exact) carry a SECOND layout family:
the largest token-bearing node's payload is a multi-part container —
the list header + counts, then float-pair data (no zero block, no
table at the predicted offsets), then `02 02` edge-record sub-nodes
and `05 08 01` vertex sub-nodes INSIDE the payload, alongside small
per-rep list nodes (86-element nodes with cumulative edge bounds 1,
39, 77 on 38d6596733).  Whether the element space splits across those
sub-nodes or the aggregate node's floats encode a different block
structure is open (U3-variant).  The 92 decoded-but-unabsorbed stores
are the known unabsorbed variant (the node list misses pool
vertices); U4 (curve-entry coordinates) stays open with the skip-slot
bracketing as the new handle.

## Stage 3d: the exporter re-integrated under the identity law (2026-11-11, #34)

Stage 3d replaces the stage-2c exporter integration
(`src/catpart/geometry/composite.py`, `export.py`) with the stage-3b
law.  The deterministic table walk decodes BOTH forms (the big-form
size rejection is gone — one table covers small and big), facet/edge
references resolve as 0-based element indices in region order, and
triangles index the written points (the exported vertex list) through
the written rank.  The stage-2c sigma solver
(`solve_shift_profile`, the monotone shift-profile CSP) and its
ambiguity path are REMOVED, with the dated supersession note in the
module docstring (M2b-element-index): the profiles were artifacts of
matching refs onto written-point indices.  The stage-2c fail-closed
ladder is refined, not abandoned — a store exports only when the walk
is exact (layout fits, the walk consumes exactly the declared write
count, every coordinate finite and plausible), the pool is absorbed,
and the gated families' references resolve in-bounds; everything else
keeps `undecoded-variant` with the specific gap named (layout,
walk-exact — the U3-variant family's signature, non-finite
coordinates, unabsorbed pool, refs beyond the element space, no
token-bearing list node).

Corpus-free fixtures pin the law's shapes (tests/fixtures_gen.py,
both forms with real 2-bit tables): a 1,000-element grid exercising
the ff-escape write count and u16be refs; a slanted corner quad
(coplanar vs the stored normal — no axis-constant coordinate; the
axis-constant reading rejected exactly this shape); loops referencing
skip slots; and the no-repeated-refs width rule (a u8 misread that
tiles exactly but repeats refs inside the loop loses to u16be).

- **Curve entries are not guessed (U4):** a loop referencing a skip
  slot cannot triangulate exactly (the entry's coordinates live in
  the curve records, open), so the exporter skips exactly those loops
  and names the gap — the new `curve-entry-loops-unexported` warning
  class (additive schema extension); the store's other loops export.
- **The stage-2c/3a explosion dissolves.**  The sigma-search hotspots
  of the stage-2c exporter — 5e5e9258 45.3 s, 5f63b708 36.1 s,
  29a1c8de/b6a5ecc5/4a325539/688f51d2 29.5-30.6 s, all failing
  undecoded-variant after the burn — resolve in <= 0.003 s under the
  identity decode (fail-closed at the absorption gate, unabsorbed
  variant with the specific gap).  05208403 (the >300 s sigma-search
  observation of the stage-2c/3a analysis) carries NO validated
  nested store in its CATStdCont region under the shipped code:
  `missing-geometry-store` in 0.000 s, the sigma search never runs —
  the identity decode cannot explode on it either.  Corpus-wide the
  slowest export is 1.37 s (a 236,385-element store).
- **Corpus A/B (export seam, both censuses at this base's locator
  state; `scripts/triage/ab_identity_export.py` →
  `docs/evidence/data/identity-export-files.csv`):** the decode
  reproduces the stage-3b rates exactly through the seam — big 464/654
  decoded (451 with exported records + 13 vertices-only; 98
  walk-exact + 92 unabsorbed fail closed) and small 213/285 (211 + 2;
  17 walk-exact + 55 unabsorbed; the stage-3b note's audited
  denominators 650/283 exclude the 28 audit-error stores this seam's
  locator reaches).  Zero refs beyond the element space and zero
  missing list nodes on every decoded store (in-bounds holds by
  construction).  Exports 110 → 753 (composite 34 → 677); L2 gate
  pass 109 → 686: **dev 638/1,381 (46.20%), held-out 48/61 (78.69%)**
  — held-out L2 moves for the first time, UP.  The 76 baseline passes
  untouched (all 109 stage-2c passes kept), and all **34 stage-2c
  exports are preserved** (33 with identical gate outcomes, of which
  26 identical triangle counts; 8 stores' triangle counts change —
  the sigma mapping was the artifact the law corrects; 144cad57's
  degenerate-gate fail resolves, fail → pass).
  **Correction (2026-11-12, stage-3d reconciliation section 5,
  stage-5 fold-in):** "all 34 stage-2c exports preserved" means
  export SUCCESS only — on the joined `1a5c4b4`/`d832b86` CSVs, 28/34
  keep vertex/triangle counts (alt's replay over the 61 stage-2c
  baseline composites measured 45/61 PLY-identical and 54/61
  count-identical; source:
  [stage-3d-reconciliation.md](../../agents/stage-3d-reconciliation.md)
  section 2).
- **Projected fitness arithmetic (the coordinator runs the combined
  row; this branch does not):** dev L2 = 109 accepted + 36 stage-3a
  recovery-clean (disjoint — those stores are among the 313
  missing-geometry-store on this base) + 529 newly passing composite
  stores that pass sanity = **674/1,381 (48.8%)** post-rebase;
  measured on this base alone: 638/1,381.  Held-out: 0 → **48/61**
  (the 61 composite stores may now decode — measured: 50 export, 48
  pass the gate).  No-regret: held-out does not fall (it rises); L1
  untouched (no locator or inspect change in this stage).

## Reproduction

```
.venv/bin/python -I scripts/triage/decode_node_streams.py
# anchor subset:
.venv/bin/python -I scripts/triage/decode_node_streams.py \
  --include-sha16 026d6726007381a9,70b59f2a0eb60c1c,e254a37e2ba6902c,0710a58b
```

Outputs `docs/evidence/data/node-streams-files.csv` (committed; one
row per L2 part).  Since stage 2c the decode machinery lives in
`src/catpart/geometry/composite.py` (the exporter's integration); this
script is its corpus runner and reports the small-form decode rates.
Corpus binaries are not committed (corpus symlinked read-only).
Correction (2026-11-11, stage 3d): the committed
node-streams-files.csv is the stage-2c HISTORICAL measurement — the
script was re-based onto the identity law (its sigma-era shift columns
retired) and the current rates live in big-form-points-files.csv
(stage 3b) and identity-export-files.csv (stage 3d); the historical
CSV is not regenerated.

Stage 3b adds the table-driven decode (both forms; U1/U3, 2026-11-11):

```
.venv/bin/python -I scripts/triage/decode_big_form_points.py
# anchor subset:
.venv/bin/python -I scripts/triage/decode_big_form_points.py \
  --include-sha16 026d6726007381a9,70b59f2a0eb60c1c,e254a37e2ba6902c
# the multi-plane decomposition over the full census (F3 criterion):
.venv/bin/python -I scripts/triage/decode_big_form_points.py --planes
```

Outputs `docs/evidence/data/big-form-points-files.csv` (committed; one
row per composite store: layout, walk, pool containment, N2, loop
battery) and, with `--planes`, `big-form-planes-loops.csv` (one row
per nonplanar loop of the walk-exact big stores: family, triangle
count, direction classes d, class, cos1000 — deterministic,
byte-identical across runs).  Since stage 3d the exporter runs the
same law in `src/catpart/geometry/composite.py` (both forms); this
script stays the decode-level corpus runner.

Stage 3d adds the export-seam A/B (2026-11-11):

```
.venv/bin/python -I scripts/triage/ab_identity_export.py
```

Outputs `docs/evidence/data/identity-export-files.csv` (committed; one
row per part: export outcome, the runner's L2 gate verdict, the
composite counters).  The decode rates and the fail-closed ladder
histogram cited in the stage-3d section come from this runner plus
the decode-level audit above; the fitness row itself stays with the
coordinator.

**2026-11-12 restatement (stage-5 pre-step; the stage-3d
reconciliation note's section-2 finding):** the committed
`identity-export-files.csv` had been generated on a pre-3a lineage —
it predates the locator recovery's effect even though `e86e046` is an
ancestor of `1a5c4b4`. Regenerated on main @ `53ea4df`
(3a-inclusive, same code, `ab_identity_export.py` unchanged):
exports 753 -> 859 (composite 677 -> 747, clean 76 -> 112); L2 gate
pass 686 -> 782 (dev 638 -> 734 — matching the accepted fitness
row's dev figure; held-out 48/61 steady); error classes
missing-geometry-store 313 -> 178 and malformed-store-header 29 -> 0
(the recovery), undecoded-variant 347 -> 405 (58 recovered stores
fail-closed elsewhere). Nothing lost: the 2026-11-11
export/composite/clean/L2-pass sets are subsets of the 2026-11-12
ones (0 v/t mismatches on the 753 common exports). The 2026-11-11
figures above stand as the pre-3a measurement; stage-5 deltas
measure against the 2026-11-12 row
(`M2b-identity-export-post3a`).

## Stage 4a-residue: the walk-mismatch families split — a raw-array law (2026-11-11, coordinator-executed)

Dispatch note: this stage was dispatched twice to subagents and both
turns died with the provider's 3008 user-concurrency limit (the parallel
coordinator session's U4 curve-entry child held the slot); executed
coordinator-side per the documented fallback (handoff-2026-11-09
precedent).  Analysis only — src/ untouched.

**Census (fact, `residue-family-census.csv`):** the walk-mismatch
population is 121 composite stores — 83 walk-end-mismatch big + 16
small (walk runs but does not end at the declared region end) plus 22
where the P1t layout itself raises.  All 83 big mismatches are OVERRUNS
(delta_words > 0, range 19..415,192); the declared P1g write count
reads 1 byte in 99/99 (walk-OK big stores: count_bytes=5 on 656/829);
elem/write_count median 19.9 (walk-OK: 0.57).  Inference: the single
[zero block + table + count] P1t prefix does not describe these
payloads.

**Raw-array family (fact on 3 anchors; start rule pinned in 32/39):**
the payload continues past the header as RAW f32 triples —
`[token][count1][count2][tail][elem_decl x [x][y][z] stride 12, x
ascending][FF][count3 u32le][trail]`.  Anchors 278015fe (start 40),
92b9ef17 and 0280c202 (start 48) decode nice=1.000 / x-ascending=1.000
for the full elem_decl span; the trail opens with a 0xFF escape count.
The start is NOT discriminated by nice-rate alone (a +4 shift reads
(y,z,x') triples, also all-nice) — the arbiter is the trail-escape
condition `payload[start + 12*elem_decl] == 0xFF`, which selects a
unique start in 32/39 scan-fit stores.  Anchors byte-verified through
`scripts/triage/probe_residue_anchor.py`.

**Rates (fact, `residue-raw-scan.csv`, 121 walk-mismatch stores):**
strong raw-fit (nice >= 0.98 AND x-asc >= 0.98): **35 (31 big + 4
small)**, pool absorbed in **29/35**; weak-fit 45; no-fit 41.
Projected if integrated: ~29-31 additional passes (dev 734 -> ~763-765,
~55.3%) — an honest range, not a wish.

**Open, named:** (1) the tail field's semantics (4B `00 00 00 01`
observed; abacf110 shows a 3B variant `01 00 01`); (2) count3's
semantics (observed 480 / 1,848 / 2,764 — not the trail byte length);
(3) the 45 weak-fit stores; (4) the 41 no-fit stores — ccbb7862 (elem
245,621) exceeds 12*elem_decl against a 2.5 MB payload: a different
packing; and the stage-3b second-layout probe (P1t repeating after a
zero block) fits structurally on 41 stores — the multi-part-container
hypothesis holds for part of the rest.

Repro: `python3 -I scripts/triage/classify_residue_family.py`
(census) / `--raw` (raw scan) / `scripts/triage/probe_residue_anchor.py
<sha16>`.

## Stage 4b: the per-rep decomposition and the width-law gaps (2026-11-11, #34)

Stage 4b resolves the two decode-class residues this note carries.
Both are measured in
[2026-11-11-per-rep-and-width-laws.md](2026-11-11-per-rep-and-width-laws.md)
(`scripts/triage/unabsorbed_pool_law.py`,
`scripts/triage/not_manifold_audit.py`, claims rows in
`stage4b-claims.csv`); the corrections below are dated against this
note's sections.

1. **The unabsorbed-pool family is the single-rep reading applied to
   multi-rep stores (stage-3d section correction).**  A composite
   store body is a sequence of reps — the k-th `01 06` pool wrapper,
   the k-th walk-exact token-bearing list node, and the strip records
   in that node's territory — and the k-th pool re-lists VERBATIM in
   the k-th rep's region (107/148 family stores; 111/148 under a
   1e-5 noise tolerance for double-rounding deltas <= 1.25e-8).  The
   stage-3d reader's `find_list_node` window ends at the FIRST strip
   record, so on multi-rep stores it saw rep 0's node while the pool
   concatenated every rep's wrapper — that is what "the node list does
   not re-list the pool" measured.  The stage-3b residue paragraph's
   "the 92 decoded-but-unabsorbed stores are the known unabsorbed
   variant" is superseded by the per-rep decomposition; the "known
   unabsorbed variant" that remains is 37 stores whose unpaired pools
   belong to walk-failed reps (U3-variant at rep granularity) plus 4
   genuinely un-re-listed vertices (a real 0.001 x-offset on 2
   near-duplicate stores).
2. **The 29 not-manifold composite exports are width-rank artifacts,
   not strip joins (stage-3b item 5 refinement).**  The width law's
   candidate enumeration (u8/u16be) misses the u24be family that
   element_count > 65,535 requires (13bb5c0c: byte-verified exact
   tiling at u24be; its battery re-validates at 0 nonplanar), and the
   narrow-width tiebreak needs the loop plane law for records over
   interleaved non-STRIP_RE families (ef30cb2f rec 261274: the u8 loop
   is nonplanar, the u16be loop coplanar, u8 won).  A re-test with
   widths (1, 2, 3) + the plane tiebreak re-measures manifold on
   21/29 without suppressing a triangle; the residual 8 keep
   normal-less non-tiling 0x42 records with no in-store arbiter
   (named, open).  The cross-loop skip convention suppresses the gate
   symptom on 29/29 but is a degree cap, not the cause.
