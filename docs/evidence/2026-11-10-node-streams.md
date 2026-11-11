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
currently full-decodes 5/284 small-form stores — the failure mode is
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
- **Form census (fact, 938 composite stores):** the list node =
  the LARGEST token-bearing node (every node carries
  `ff ff 02 00 01` + the declared counts — the stage-2a "list-node"
  census counted all of them). 284 small-form (108-4,096 B, median
  1,335), 654 big-form (4,144-2,516,042 B, median 19,334); 5 stores
  have element_count == pool_size (the empty-list degenerate, N4
  refined: 5/938, not 4/939); element_count > pool on 872, < pool on
  61 (the stage-2a residue, re-measured).

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
  the list's first point).
- **M2c (inference, strong):** the curve entries are the curve
  records' points. On 026d6726 the 22 curve records decode as circle
  definitions matching the node's circles exactly — `33 37` = (cx, cy,
  z, r) BE f32 + 2-B trailer (12 records: the six circles, some twice,
  plus two slot arcs r=0.81 at (391.83, 435.5, 2.81) / (398.17, 435.5,
  2.81) — an obround slot whose tangent points ARE pool v0/v3);
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
  5/284 small-form stores; every completed decode validates (5/5:
  026d6726, e254a37e with the 7-loop planarity + shift law; 0710a58b,
  fa779a78, ff842b8a with pool fully contained and
  element_count == node points). The winding re-run on 70b59f2a is
  blocked on the segment bookkeeping (U3) — the stage-2a 0.5153
  half-rate figure is superseded by the byte-verified x-group trace
  but not yet replaced by an end-to-end winding number.

## Unknowns carried forward

1. **U1 — the per-node 2-bit table** (payload[40, 72) on 026d; ~460 B
   on 70b59f2a before the point region): 2 bits per element for
   element_count entries (026d: 128 slots for 124 declared + pad;
   70b59f2a: 1,840 slots for 1,820) — value histogram {0: 38, 1: 26,
   2: 31, 3: 33} on 026d; the write-count sums do NOT match the point
   region's f32 count under any of the 8 mappings tried; semantics
   open.
2. **U2 — the trailing region** of each list node (026d: payload[884,
   1452), 568 B of nibble-ish runs + floats ~10.88 + the tail
   signature): present on every anchor, per-store size varies; open.
3. **U3 — segment bookkeeping on big stores** (per-segment tables,
   the corner-group tail segment, the extras' placement inside
   x-groups): blocks the 70b59f2a winding re-run.
4. **U4 — curve-point participation**: which points each `33 3X`
   record contributes (26 entries' sort positions pinned by the shift
   profile; values consistent with the circle geometry but not
   byte-pinned).

## Reproduction

```
.venv/bin/python -I scripts/triage/decode_node_streams.py
# anchor subset:
.venv/bin/python -I scripts/triage/decode_node_streams.py \
  --include-sha16 026d6726007381a9,70b59f2a0eb60c1c,e254a37e2ba6902c,0710a58b
```

Outputs `docs/evidence/data/node-streams-files.csv` (committed; one
row per L2 part). Corpus binaries are not committed (corpus symlinked
read-only). No exporter/runner code is touched; `catpart.geometry` is
imported read-only.
