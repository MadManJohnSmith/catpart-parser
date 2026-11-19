# Composite exporter: coordinate-identity duplicate-triangle dedup (#34)

Date: 2026-11-18
Base: `ac70db8` (main; the salvage branch forked at `de6fd39`)
Status: **implemented (Python + Rust, port-parity verified), full-corpus
A/B clean (0 pass→fail, 0 manifold regressions, 0 surface changes),
gate green.**

Claims: `docs/evidence/data/br6-coord-dedup-claims.csv`
A/B data: `docs/evidence/data/coord-duplicate-dedup-ab.csv` (one row per
manifest part: statuses, triangle counts, listed and unique-facet areas,
dedup outcomes).
Reproduce: `.venv/bin/python -I scripts/triage/coordinate_duplicate_dedup_ab.py`
(~4 min, deterministic, read-only over the corpus; the *before* pass is
the committed index-keyed law copied verbatim, anchored row-for-row to
`fitness/reports/20261118T232016Z-64b2a1.json`).

## 1. The case

`545707b9` (`CATIA/CATIA_vol/Usinage/Test_trappe.CATPart`, dev) was the
one not-manifold part whose over-use was dominated by re-listed
geometry: 4 reps, 2,266 triangles, 212 over-edges, L2 `not-manifold`.
The stage-15 law sees duplicate **index** triples only, and it was
declining here:

| quantity | value |
|---|---|
| exported triangles / vertices | 2,266 / 2,236 |
| over-edges (edges used 3+ times) | 212 |
| index-duplicate groups / extra copies | 67 / 67 (all inside rep 3) |
| coordinate-duplicate groups / extra copies | 384 / 451 |
| within-one-rep coordinate duplicates | 0 |
| cross-rep coordinate duplicates | 451 (space 0 ↔ space 3) |
| listed (soup) area | 15,976.412271 mm² |
| unique-facet area (each coordinate triple once) | 11,852.259218 mm² |
| double-listed area | 4,124.153053 mm² = 25.81% |

The 67 index duplicates are the same-rep re-listing the law was written
for; removing them alone (2,266 → 2,199 triangles) still leaves
**138 over-edges** — the index law's measured decline. The other 451
copies are invisible to an index key: the
per-rep decomposition keeps each rep's element space disjoint by
construction, so a rep that re-lists an earlier rep's facet writes
*different* indices for it.

Per index space (the exported reps):

| rep | points | triangles | area mm² | notes |
|---|---|---|---|---|
| 0 | 770 | 1,154 | 4,207.3241 | 221 primary + 933 dup-pin welded |
| 1 | 364 | 362 | 3,911.8986 | |
| 2 | 716 | 4 | 120.0000 | |
| 3 | 386 | 746 | 7,737.1896 | 451 of them re-list space 0 |

Rep 0's 27 curve-entry loops weld into 933 triangles (the stage-10
dup-pin law). **329 of those welded triangles — plus 55 of rep 0's
primary triangles — are coordinate-identical to a triangle rep 3
lists** (384 facets, 451 re-listed copies: 317 facets twice, 67 three
times). Independent evidence that the weld reconstructs the real
surface, and that rep 3 is the re-listing.

## 2. The law: COORDINATE identity, area-preserving by construction

`composite._apply_unordered_dedup` (twin: `apply_unordered_dedup` in
`port/src/geometry/composite.rs`) now keys a duplicate on the three
vertex **positions** as an unordered triple, not on the element indices:

```python
key = tuple(sorted((points[i] for i in tri)))   # was: tuple(sorted(tri))
```

- **Area-preserving by construction.** A triangle's area is a pure
  function of its three vertex positions (`_triangle_area`). Two
  copies with identical coordinates have identical area, and exactly
  one copy survives — so the drop can never remove surface the kept
  copy does not already carry. No vertex is invented, no edge is
  split, no coordinate is rewritten: the exported vertex list is
  untouched (2,236 points in and out on the case).
- **Degenerate guard unchanged**: a repeated-index triple is never
  deduped (degenerate skips stay a separate L2 gate check).
- **Fire gate unchanged** (fail-closed): the assembled mesh must be
  NOT manifold, and the deduplicated list must be manifold; otherwise
  the emitted triangles are kept verbatim and the decline is named.
- **Keeper = the earliest emission unit.** Per coordinate group the
  surviving copy is the one from the earliest index space (its first
  vertex's space rank; ties by emission order). A rep's welded loops
  carry that rep's point base, so they belong to that rep's unit even
  though they are appended after every rep's primary loops. Emission
  **order alone** is not the rule: with list order the later rep's
  copies win 329 times and the mesh stays not-manifold (125 over-edges
  — measured). The alternative keeper choices were measured too: last
  copy wins leaves 3,289 edges / not-manifold; latest rep space leaves
  1,339 boundary edges / not-manifold.
- **One site: the mesh the store actually exports.** The law runs once,
  in `decode_composite_store` (the entry), on the assembled store mesh
  the entry is about to return — after the primary-emit seam's
  fire-gated decision. The per-path decode functions hand the entry
  their index-space offsets and no longer call the dedup themselves, so
  the seam's committed surface trade is untouched and the fire gate
  sees exactly the exported mesh. Cross-space keeper rank is why the
  offsets are needed; a single-space store passes `(0,)` and falls back
  to emission order (the committed same-rep behavior).

### 2.1 The case, after

| quantity | before | after |
|---|---|---|
| triangles | 2,266 | 1,815 |
| manifold | no | **yes** |
| over-edges | 212 | 0 |
| boundary edges | 895 | 1,077 (open shell, legitimate) |
| listed area mm² | 15,976.412271 | 11,852.259218 |
| unique-facet area mm² | 11,852.259218 | 11,852.259218 |
| L2 | fail `not-manifold` | **pass** |
| dedup outcome | declined 67 | dropped 451 |

The listed area falls by exactly the double-listed 4,124.153053 mm²;
the geometric surface is unchanged (the unique-facet area moves only in
the 12th decimal: 11,852.25921825685 → 11,852.259218256844, i.e.
6e-12 mm², f64 summation order). After the drop the listed area *is*
the unique-facet area — one copy of every facet. Warnings:
`duplicate-triangles-deduped` replaces
`duplicate-triangles-dedup-declined`; `primary-loop-manifold-declined`
stays (the seam still declines: with the duplicates gone the remaining
over-use is the one large kept loop, and the seam may not drop it).

## 3. Full-corpus A/B (1,442 manifest parts, 1,173 exports)

| figure | value |
|---|---|
| parts / exports | 1,442 / 1,173 |
| L2 pass | 1,135 → **1,136** |
| pass → fail | **0** |
| fail → pass | **1** (545707b9) |
| manifold regressions | **0** |
| manifold flips | **1** (545707b9) |
| listed-area moves (rel > 1e-9) | **1** (545707b9, −25.81%) |
| unique-facet-area moves (rel > 1e-9) | **0** |

The before pass is anchored to the committed fitness report: every
part's L2 status, failed check and triangle count must equal its `l2`
record (the harness asserts it, so a baseline drift invalidates the run
instead of moving the comparison). It does — including `b912cbef`,
whose 31,203-triangle mixed-write emission and 2,585.251329 mm² are
byte-for-byte the committed ones: the seam still resolves that store
first, so the assembled mesh it exports is manifold and the dedup never
touches it.

Dedup outcomes over the corpus after the change (5 parts):

- **fired** — `545707b9` 451 (fail→pass), `1d256d12` 4,
  `ef61cfc2` 1 (both unchanged: same drops as the committed index law);
- **declined (fail-closed, geometry verbatim)** — `341bd488` 2,633,
  `995383c2` 97: coordinate duplicates that do not explain the store's
  over-use. The old index key could not see these copies at all (they
  are cross-space); naming the declined count is new, the triangles and
  areas are unchanged.

## 4. Port parity, fixtures, tests

- **Port parity**: `port/src/geometry/composite.rs` carries the same law
  (`CoordKey` = three sorted `vkey`s — exact f64 bits with −0.0
  collapsed, the twin's float equality; rank via
  `partition_point` on the space offsets; same fire gate), and
  `decode_composite_store` applies it once to the chosen emission. On
  `545707b9` and `b912cbef`, Python and `fidelity-cli export` produce
  **parsed-equal summaries and byte-identical PLY**
  (`test_coordinate_dedup_case_and_port_parity`); the new fixture is
  compared by the Fidelity harness's stage-3 composite export matrix.
  The shipped `port/pkg` / `site/viewer/pkg` wasm is byte-identical to
  a fresh `wasm-pack build` of this source (sha256 `97bf10a2…`).
- **Fixture** `geometry-composite-law-dedup-coord-relist`
  (`tests/fixtures_gen.py`): rep 1 re-lists rep 0's box at the same
  coordinates (its own pool group and element space, no index triple
  matching) plus one 2,000 mm² fin loop over box edge (0, 3) — edge
  used 3× in rep 1, store not-manifold. The coordinate arm drops rep
  1's 12 re-listed copies (rep 0 wins), the mesh is box + fin
  (13 triangles, manifold, 20,400 mm²), and the fin's surface survives
  (10.9% of the store, so the seam keeps it). Without the coordinate
  arm the same fixture stays at 25 triangles / not-manifold. The
  fixture rides the Fidelity harness's stage-3 composite export matrix.
- **Unit tests**:
  `test_unordered_dedup_matches_coordinates_across_disjoint_spaces`
  (Python) and `unordered_dedup_matches_coordinates_across_disjoint_spaces`
  (Rust) pin the keeper rule: the earlier space's copy wins even when
  it is later in the list; with one declared space the list order
  decides and the dedup declines; a manifold mesh is never touched.
- **Gate**: see `br6-coord-dedup-claims.csv` (`BR6-CD-12`).

## 5. What this does not do

- It does not invent vertices, split edges, merge vertices, or renumber
  the exported point list (all 2,236 points survive on the case).
- It does not touch a passing store: the fire gate's pre-condition is
  the exported mesh being not-manifold, so every passing row keeps its
  exact geometry (A/B: 0 unique-area moves, 0 triangle-count moves).
- It does not change the seam's decision procedure: the seam's
  fire-gated surface trade runs before the dedup, exactly as committed
  (b912cbef is the witness — identical triangles, area and warnings).
- The two declined corpus stores (`341bd488`, `995383c2`) keep their
  exact emitted triangles; their over-use joins distinct triangles, not
  re-listed facets, and the L2 gate records not-manifold as before.
