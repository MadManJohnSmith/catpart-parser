# W2-B: the U3-variant element region vs the stored-normal oracle (2026-11-22)

Worker: W2-B, wave 4, branch `marathon/w2b-element-region`, base
`065634b`. Question (W2 hand-off): is there a findable **indirection
table** (element→region/vertex) for the U3-variant composite stores,
such that the facet records' refs map onto explicit positions and pass
the committed plane battery? Deliverable: the measured negative below
plus the container structure it rests on. Probe:
`scripts/triage/w2b_element_region_probe.py` (selftest pins the census
mechanics on a synthetic container); CSV:
`docs/evidence/data/w2b-element-region-oracle.csv` (12 eligible
stores, one row each, streamed). Eligibility: pool + facet candidates
in the W2 baseline (211 rows) — the >65,535-element store is skipped
by the oversize guard (the closed 0x49 negative: a 2-byte ref cannot
index such an element space).

## Container structure (facts, byte-measured)

- **F1 — the U3 node is a multi-part container, not the committed
  table+region layout.** After the declared counts the payload carries
  a 4-B header `01 00 01 02` (Tornillo `c6eaac5e`, separador
  `e42e3805`, Tapa `1b0eef98`, Base `38d65967`, Correia 1
  `219c099e`, Correia 2 `a722b491`, Part 3 `abacf110`) or the variant
  `01 00 01 01` + a zero block (Coxa `12dc542e`), with **no zero block
  at all** on the `..02` stores — the committed `layout()` reads the
  first data bytes as the 2-bit table and misaligns everything after.
- **F2 — the container opens with c1 f32 pairs.** `pairs_found ==
  c1_element_count` on all 7 `..02` stores (1312, 1325, 424, 2430,
  14662, 792, 3128). The pairs are UV-grid entries: quantized pitches
  (separador b-steps 0.08 and 1/32; Tornillo symmetric around
  (0.5, 0.5)), loops' UVs trace axis-aligned rectangles (face cells),
  and the adjacent-entry serialization (entries 2j, 2j+1 sharing a)
  holds at fractions 0.23..1.0 per store.
- **F3 — explicit f32 position zones exist after the pairs** (all-nice
  stride-12 runs; probe `pos_zone_triples`): separador 1499, Part 3
  14063 (≈ c1 − 599), Tornillo 111, Coxa 39, Correia 1 196, Base 154,
  Tapa 22. The zone CONTENT differs per store: separador/Part 3
  re-list pool coordinates bit-exact (separador: z=3.5/11.5 rows and
  x=36.0/44.0/46.47487…) while Tornillo's zone is parametric
  (a unit-circle family at constant radius 0.9635 — cos/sin samples,
  not points). The store's own frame is NOT the pool frame: separador
  position-zone bbox ≈ cubic [-46.4, 46.5]³ vs pool bbox
  x[-12.475, 46.475] y[-46.877, 15.137] z[3.5, 11.5].
- **F4 — the refs index the declared element count exactly.** On every
  store with parsed loops the committed width-vote parse (the u16le
  relaxed families included) yields `refs_max == c1 − 1` and zero
  out-of-range refs (1870→1869, 1312→1310, 1325→1324, 424→423, 2430→2391,
  792→777, 3128→3127).
- **F5 — the topology lives in known families.** Edge tables (`01 02`)
  carry u16be element-index runs (Tornillo: 447, 442, …, 371 then
  791, 790, 788, …); inter-record streams carry u16le index runs
  (separador rec@862420: counts [15, 19], 34 u16le refs — the
  committed relaxed-primitive family parses them).
- **F6 — Part 3's records carry no normal** (19 records, 0 normal-
  carrying loops): the plane battery cannot test that store at all.

## The oracle: NEGATIVE (measured, 2 attempts + corpus sweep)

The battery: a mapped loop's Newell normal must be parallel to its
record's stored 12-B normal (|dot| > 0.999 — the BR2-10 bar; the
pool-only scope validates 0.9899 on the committed stores, so a correct
mapping scores ~1.0). Attempts:

1. **Direct mappings over the position zones** (identity; the best of
   the 48 signed axis permutations; constant shifts δ ∈ [−c1, 0]):
   corpus-wide **0/16 testable loops** pass identity (separador 0/13,
   Correia 1 0/2, Coxa 0/1); best permutation 1/13 on separador
   (noise); best shift 1.0 on 1 loop with coverage 16 at 0.188.
2. **An explicit indirection array does not exist**: no c1-length
   u16be/u16le index run in the span (separador's longest u16be run
   < c1 is 2278 values at abs 874054 = the edge/curve tables), and
   UV-normalization matching (pairs vs the position zone's own bbox,
   3 axis pairs) hits 0/3128.

**Conclusion: the element→position mapping is law-based, not
table-based.** The refs index a UV-grid element space (F2, F4); the
explicit 3D sits in zones whose frame is not the pool's (F3); and the
per-face UV→3D affine that would connect them is present nowhere in
the node territory in explicit f32 form (searched: inter-record bytes
= index streams, edge tables, the `0001` sub-node group's transform-
like 48-B blocks). Shipping the manifold-but-scrambled assembly is
exactly what the no-guessing gate refuses (W2's refutation stands for
every direct mapping tried here).

## Cota (the measured bound)

- **0 flips** empty-mesh → PASS on the 12 probed stores; the 211
  official rows are unaffected.
- Direct-mapping coverage: 16 testable loops corpus-wide, 0 pass; the
  remaining normal-carrying loops reference curve-entry indices (≥ the
  position zone) and cannot be scored without the frame law at all.
- The counts-less 0x49 family stays out of scope: its only eligible
  population lives on the oversize store (c1 > 65,535 — closed
  negative, excluded by the probe's guard).

## Reopening criteria

- **R1 — a per-face UV→3D frame law** lands in
  `catpart.geometry.composite` (the frames' byte source found —
  candidates: the `0001` sub-node group, the post-refs record
  structures): re-run the probe's battery per record; flips expected
  on the 7 pairs-shaped stores.
- **R2 — a store-frame↔pool-frame transform law** lands (the F3 cubic
  bbox): pin the position zones' frame, re-test the direct mappings on
  transformed tables.
- **R3 — the no-pairs variant** (`..01` header + zero block, 5/12
  stores): extend the census when a layout law pins their post-header
  structure.

Claims ledger: `docs/evidence/data/w2b-element-region-claims.csv`
(W2B-01..W2B-14). Reproduction:

```bash
.venv/bin/python -I scripts/triage/w2b_element_region_probe.py --selftest
.venv/bin/python -I scripts/triage/w2b_element_region_probe.py \
    --corpus-root /home/alan/Documents/Repos/catpart-parser
```
