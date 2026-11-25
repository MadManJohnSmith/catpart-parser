# W1-B marathon progress (not-manifold dedup>0 ∧ ext>0) — round v1

Branch `marathon/w1b-notmanifold-dedup`, base 6e3c8fb (W1's anti-half-read).
Worker W1-B, 2026-11-22. Bench state dir (not committed):
`~/.local/state/catpart-parser/w1b/`. Every figure traces to
`docs/evidence/data/marathon-w1b-multiregion-claims.csv` (757 rows, one
per snapshot part).

## The finding: the multi-period body misresolution

The not-manifold class's dominant cause is NOT record-level: the store
bodies carry MULTIPLE walk-exact token nodes — one per period — and the
single-rep reading (:func:`composite.find_list_node` returns the largest
payload) resolves every period's records against node 0's region. The
periods' record topologies are byte-identical, so the misresolved facets
are identical index triples over the wrong vertices — the
duplicate-triangle signature the brief named, at ~20 copies per facet.

Byte evidence (MB-Frames-middle-centr-YL.CATPart, 1,323,822 B):

- 50 token nodes, all walk-exact (payloads 7,803 B, elem_decl
  658/676/679/682), at a 12,352-B period. The k-th node's first written
  point is x = 1646.042236328125 + 120k — a row of 50 frame panels.
- Node 0's facet territory: 5 short records + 1 extended 0x4f record;
  the same byte sequence repeats per period (records byte-identical,
  nodes not — each panel has its own 682-element vertex region).
- Single-rep reading: 682 points / 40,893 triangles / 38,873 unordered
  duplicates (the dedup declines — the unique mesh still carries 368
  over-edges, edge multiplicity up to 6) / not-manifold / 4 degenerates.
- Per-period reading (each rep's records over its OWN region): 50 reps,
  each manifold; merged 33,925 points / 50,423 triangles (the dup-pin
  weld adds 181) / 0 degenerate / manifold / 0 over-edges / 16,396
  boundary edges (an open-shell row of panels — legitimate geometry,
  G3 F6).

Census over all 757 snapshot parts (streaming, one part in RAM):
553 parts carry a span with >= 2 walk-exact token nodes; 270 of them
PASS L2 today (their single-rep reading resolves — the route never
fires there, byte-identical PLY); of the 283 failing, 267 not-manifold
and 16 degenerate-triangles are multi-node. Projection with the strict
reading: 251 of the 296 failing multi-node parts resolve (237
not-manifold + 14 degenerate-triangles), 0 out-of-bounds reps, 29
still-broken, 5 with surviving records in node 0's head window, 11
single-node.

## The law (unit 1): the multi-region second chance

`composite._decode_multiregion` (port: `decode_multiregion`), invoked
from the entry point's fire-gate residue ONLY — after the seam, the
stage-15 dedup and the #70 relist post-pass have all left the store
not-manifold, so every passing store's decode never reaches it
(byte-identical PLY, Dev/Held-out unchanged). Fail-closed at every step:

1. every token node decodes walk-exact under the committed table law
   (:func:`decode_region`); fewer than 2 is not the family;
2. rep k = node k's territory `[region_end_k, node k+1)`: its records
   parse under the SAME committed record laws against node k's OWN
   element space;
3. every gated reference of every rep resolves in-bounds (the #66 gate
   per rep) — one OOB rep declines the whole reading;
4. no surviving record may precede node 0's region end (the head window
   must parse to zero records — surface must never silently vanish);
5. the merged mesh is adopted ONLY when it is manifold, degenerate-free
   and non-empty; any other outcome keeps the single-rep emission
   byte-for-byte with `multiregion_declined` naming the gap.

Per-rep emission runs the same `_triangulate` (the EdgeGuard, the
extended family, the relaxed families, the dup-pin weld) with the seam
off (registry behavior); the merged info carries stage
`identity-multiregion` + `multiregion_reps`, and the rep offsets ride
`_space_offsets` (the dedup keeper's emission units). New warning
classes `composite-multiregion-decode` /
`composite-multiregion-declined` (schema enum extended).

## Measured effect (Submarino snapshot, 757 parts, same probe as W1)

- **not-manifold 275 -> 40 (-235)**; L2 pass 448 -> 683 (59.18 % ->
  90.22 %)
- degenerate-triangles 19 -> 19 unchanged; empty-mesh 13 -> 13 unchanged
- **0 new not-manifold, 0 new degenerate-triangles, 0 class changes**
  (0 regressions; the 270 multi-node passers are byte-identical)
- triangles 1,821,817 -> 2,482,236 (+660,419: the panels' real
  surface, previously collapsed onto panel 0's vertices)

The remaining 40 not-manifold: 29 with a genuinely broken panel (over-
using loops inside a rep — the merged mesh is not adopted, fail-closed),
5 declined by the head-record guard, 6 single-node stores the family
does not cover. Reopening criterion for the 29: a per-rep seam pass
(the sliver rule at rep level) if the corpus ever demands it — NOT
attempted this round (the strict reading is the no-guessing law; the
seam's area rule would need a measured corpus precedent first).

**Later update (2026-11-25)**: `acc-Cont-Lft.CATPart` is the case where
the route's fire gate matters. W1's half-read fix leaves its single-rep
emission `manifold = True` / `degenerate = 0` (563 triangles), so this
route never runs even though the body has 13 token nodes (12 walk-exact
+ 1 container) and the per-rep reading is 6,602 triangles / manifold /
0 degenerate / 12 boundary edges. The claims row's 12-rep / 4,649-triangle projection
predates W17's container rep. Root cause and reopening criterion:
[2026-11-25-acc-cont-lft-single-rep.md](../2026-11-25-acc-cont-lft-single-rep.md).

## Parity, tests, gates

- Python tests:
  `tests/test_composite_export.py::test_composite_multiregion_merges_per_period_regions`
  (positive: 2 reps, 24 points, 20 triangles, manifold, 10+10 per rep)
  and `::test_composite_multiregion_nonmanifold_rep_declines_fail_closed`
  (a rep carrying an over-using fin declines the adoption; the
  single-rep emission is kept). Port twins
  `multiregion_merges_per_period_regions` /
  `multiregion_nonmanifold_rep_declines_fail_closed` construct the same
  bytes function-level (the twin's `_composite_node_payload` /
  `_facet_record` layouts, replicated in the test module).
- **Parity PLY byte-identical Py=Rust, 8/8 parts** (`fidelity-cli
  export` vs the Python seam, sha256-compared): the fixed
  MB-Frames-middle-centr-YL/YR, the declined BW-Bollard-35 /
  BW-Door-Ade-YL, the twin control BW-Eske-33dZ-YL, and the untouched
  passers BW-Eske-33dZ-YR / BW-Intercostal-Sup-YL / Anill-P.
- Decline naming: a not-family residue (< 2 walk-exact nodes) records
  NO decline key — the route's decline arm names only family reasons
  (OOB rep, head record, non-adopted merge), so the summary churn
  stays on the family (the reproduction smoke's fixture rows are
  unchanged).
- Gates: ruff clean; pytest 952 passed / 15 skipped (1 process); cargo
  test 229 passed; cargo fmt clean; clippy -D warnings clean; the
  wasm32 build (the ci.yml mirror's plain cargo step, NOT wasm-pack)
  compiles. The claims CSV parses at header width (86 CSVs, 15,512
  rows).
