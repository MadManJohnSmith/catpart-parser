# The remaining over-uses and degenerate parts (#34)

Date: 2026-11-19
Base: `5c2640e` (main), report `fitness/reports/20261119T035609Z-7dc3ea.json`
Status: **audit (read-only over the corpus; no `src/` change, no gate change).**
Verdict: **all six remaining over-uses are content — the writer's own
records list more than two distinct facets on one element edge. No decode
artifact was found. The two degenerate stores are writer-emitted zero-area
facets on a manifold mesh; only `MAX_DEGENERATE_TRIANGLES = 0` blocks them.**

Claims: `docs/evidence/data/overuse-audit-claims.csv`
Per-edge data: `docs/evidence/data/overuse-audit-edges.csv`
Reproduce: `.venv/bin/python -I scripts/triage/overuse_audit.py
--corpus-root <checkout with corpus/>` (~80 s, deterministic, read-only;
the probe replays every emission through the shipped helpers and asserts
the triangle list equals the shipped export before any number is printed).

## 1. The population

The committed report has exactly eight failed dev rows that the two
shipped laws do not explain: six `not-manifold` and two
`degenerate-triangles` (the held-out split has no failed checks):

| sha16 | split | failed_check | tris | area mm² | deg | stage |
|---|---|---|---:|---:|---:|---|
| 26504a08b641ad7a | dev | not-manifold | 3,071 | 41,421.608 | 0 | identity-table-walk |
| 341bd488e61d6061 | dev | not-manifold | 46,833 | 34,222.971 | 28 | identity-per-rep |
| 5689954c867a0f70 | dev | not-manifold | 1,692 | 78.291 | 0 | identity-table-walk |
| 5a982112b4f5edc1 | dev | not-manifold | 2,306 | 590.707 | 0 | identity-per-rep |
| cd88ae9d4d51a439 | dev | not-manifold | 3,014 | 36,354.696 | 0 | identity-per-rep |
| e8d9a35806f5fcf7 | dev | not-manifold | 15,680 | 111,437.859 | 0 | identity-per-rep |
| 13bb5c0c49616ade | dev | degenerate-triangles | 152,010 | 1,065,284,389.026 | 33 | identity-table-walk |
| b912cbef805c541b | dev | degenerate-triangles | 31,203 | 2,585.251 | 3 | identity-mixedwrite-reps |

L2 dev is 1,084 / 1,381 = 78.49 %. These eight are the residue after the
primary-emit seam's 15 manifold flips (`2026-11-18-primary-emit-seam.md`)
and the coordinate dedup's one flip
(`2026-11-18-coordinate-duplicate-dedup.md`). They are the two rows the
close-out lists as documented negatives
(`2026-11-19-fidelity-close.md` section 2); section 7 relates the measured
levers to that note's reopen criteria.

## 2. Method, and the artifact hypotheses ruled out

Every store was decoded through the shipped entry, then the emission walk
(`_triangulate` → extended records → dup-pin, per rep where applicable)
was replayed with provenance: each triangle carries its emission unit,
record offset, marker, loop index and strip window. The replay is asserted
**equal to the shipped triangle list**, so every attribution below is the
shipped geometry, not a re-derivation.

For each over-used edge (undirected use count > 2) the census records the
number of incident faces, the number of distinct writer loops and records
they come from, the number of distinct coordinate triples, the pairwise
normal-dot range and the incident area.

Artifact hypotheses, tested per store:

- **Ref width.** Enumerating every `(width ∈ {1,2[,3]}, k ≤ 16)` candidate
  that fits before the next header leaves the shipped parse as the
  committed law's choice, but these padded records are not decided by
  exact tiling. The wider candidate is ruled out by content, not by rank:
  on 26504a08 its refs repeat (2362 twice, 2407 twice — the repeated-ref
  criterion the law ranks on); on 26504a08 and e8d9a358 they land on
  *skip slots* and on one unrelated point repeated; on 5a982112 the six
  refs resolve to a 1 mm cluster instead of the six thread-band points.
  The narrower reading is the one that resolves to the points the rest of
  the store shares. On 341bd488's 114-ref record the width-2 candidate
  does not fit at all (249 B needed, 219 B to the next header).
- **Count split.** The loop boundaries are the record's count bytes
  (`(4,4)`, `(5,)`, `(20,)`, `(5,5,6)`, `(114,)`, …) and `sum(counts) == n`
  is checked by the parser; no alternative prefix sums to `n`. The
  over-uses sit across these explicit loops/records, not inside a
  mis-split one.
- **Ref mapping (single-rep vs per-rep).** 26504a08 and 5689954c carry a
  single pool group (544 / 803 vertices), so no per-rep reading exists.
  In the per-rep stores every over-use face is inside one rep's own
  element space (unit 0 or unit 2); no cross-rep index mapping is
  involved. In 5a982112 the per-rep path also exports exactly one rep.
- **Re-listed facets.** Five stores have zero identical-coordinate
  triangle pairs. 341bd488 has 2,633 cross-rep coordinate copies, but the
  dedup declares them (correctly) unable to resolve the over-use, and
  none of them touches the over-used edges.
- **Triangulation law.** The over-used loops are 0x42/0x49/0x4a strips.
  A polygon-fan reading (0x4c) of the same refs is wrong for these loops:
  their order alternates between two rails (rim point, far point, rim
  point, …), so a fan would create *more* shared edges, not fewer, and
  would cover a different region.

Supporting evidence that this is the file and not the decoder: the
same-family parts decode through the same paths and pass — M3x10 / M3x20 /
M3x30_CHC and M2.5x25_CHC all pass (M3x20 and M2.5x25 even via the same
table/per-rep paths), while M3x16_CHC fails; LedStrips_GND_final,
LedStrips_WorkFile and LedStrips_WireControl_final pass (the first two via
the same per-rep path), while LedStrips_5V_final fails; TouchRows_Strips,
TouchRows_Support and TouchRows_Solders pass while TouchRows_Wires fails.

## 3. The six over-uses, store by store

Edges are the exported written-rank indices (the store-level vertex list).
"Writer loops" counts the explicit loops/records whose refs produce a face
on the edge.

| sha16 | edge | deg | faces | writer loops / records | distinct coord triples | normal dot | incident mm² |
|---|---|---:|---:|---|---|---:|---:|
| 26504a08 | (5,6) | 4 | 4 | 4 / 3 | 4 | −0.858 … 0.998 | 43.848 |
| 341bd488 | (21613,21614) | 15 | 15 | 1 / 1 (0x4a, 114-ref loop) | 15 | −0.999 … 1.000 | 247.066 |
| 341bd488 | (21614,21615) | 15 | 15 | 1 / 1 (same loop) | 15 | −0.999 … 1.000 | 224.866 |
| 341bd488 | (21614,21802) | 4 | 4 | 1 / 1 (same loop) | 4 | −0.999 … 0.962 | 421.250 |
| 341bd488 | (21615,21616) | 3 | 3 | 2 / 2 (0x49 + 0x4a) | 3 | 0.617 … 0.959 | 1.681 |
| 5689954c | (17,18) | 3 | 3 | 2 / 2 (5-ref + 20-ref) | 3 | 0.352 … 0.940 | 2.622 |
| 5a982112 | (3,7) | 10 | 10 | 10 / 10 (9 × 0x42 + 1 × 0x4a) | 10 | −0.949 … 1.000 | 68.653 |
| 5a982112 | (3,6) | 5 | 5 | 5 / 5 (0x42) | 5 | 0.558 … 0.999 | 47.479 |
| 5a982112 | (3,5) | 4 | 4 | 4 / 4 (0x42) | 4 | 0.826 … 0.999 | 27.789 |
| cd88ae9d | (7,54) | 4 | 4 | 2 / 1 (one record, loops 1+2) | 4 | −0.924 … 0.431 | 16,115.350 |
| cd88ae9d | (1,7) | 3 | 3 | 3 / 1 (one record, loops 0-2) | 3 | 0.012 … 0.996 | 1,575.393 |
| cd88ae9d | (6,7) | 3 | 3 | 2 / 2 (0x42 loops) | 3 | −0.991 … 0.000 | 104.090 |
| e8d9a358 | (27,28) | 5 | 5 | 5 / 5 (0x42 4-ref loops) | 5 | 0.953 … 0.999 | 246.561 |
| e8d9a358 | (28,58) | 3 | 3 | 2 / 2 (4-ref + 10-ref) | 3 | −1.000 … 0.862 | 27,685.348 |

No pair of incident faces is a coordinate duplicate, and the normals
range from opposite to nearly parallel: these are fans of *distinct*
sheets meeting on one edge, not one facet listed twice.

### 3.1 26504a08 — `model/Guntle.ver5.CATPart`

The edge is element edge (8,9) (written 5,6), 0.628 mm long. Four 4-ref
0x42 loops — record `0x3a3a2e` loop 0 `(8,113,9,58)`, record `0x3a3a85`
loop 1 `(8,116,9,60)`, record `0x3a89a2` loops 0/1 `(8,195,9,27)` and
`(8,212,9,10)` — each produce exactly one face on it. The four faces are
distinct quads whose far corners reach y ≈ −36 mm, +36 mm, z = 170 mm and
z = 32.8 mm: four real ribs hinged on the same 0.6 mm edge.

The seam guard refuses the third and fourth faces' loops (26.436 mm²,
skipped; 1,208.316 mm², kept). The fourth is a 1,208.316 mm² loop
(2.9171 % of the part) carrying a 19.285 mm² face on the edge, so the fire
gate keeps the pre-seam emission (declined = 1, kept = 1). Dropping the
*loops* would either leave three uses (only the 26.4 mm² loop is a sliver)
or delete the 1,208 mm² patch.

### 3.2 5689954c — `_standard/M3x16_CHC.CATPart`

Edge (17,18) is a 1.4 mm segment at the *start* of the element space; its
two endpoints share x,y exactly (z 15.876 → 17.276). Three faces use it:
the 20-ref strip `(6814,6815,4383,…,17,18,4,5,…)` uses it twice as an
interior rung (the two triangles that straddle the rung), and the 5-ref
strip `(19,55,18,93,17)` adds a third use through its closing triangle
`(18,93,17)`. The 20-ref loop is the seam's kept loop (12.034 mm² =
15.3706 % of the 78.3 mm² part); the other loop is real too. This is one
writer band whose interior rung is shared with a second writer strip.

### 3.3 5a982112 — `_standard/M4x10_Poelier.CATPart`

Three low-index edges of the same small anchor quad (elements 3, 5, 6, 7,
a ~0.5 mm patch at z ≈ 9.8-10.1). Nine 0x42 records each emit one 6-ref
band `(X, A, 3, B, 7, C)` (X = 5 or 6) and a tenth record (0x4a) adds one
more face; every band uses (3,7) as its rail, five bands use (3,6) and
four use (3,5). The far points of the bands sit at z = 0.5 … 9.6 mm — ten
distinct thread-like sheets all anchored on the same rim quad. All eight
seam refusals are kept (2.28 % … 8.07 % of the 590.7 mm² part).

### 3.4 cd88ae9d — `SYSTEM/TouchRows_Wires.CATPart`

Rep 0, record `0x33abc5`, counts `(5,5,6)`; loops 0 `(0,208,7,6,1)`,
1 `(2,7,54,1,195)` and 2 `(1,195,7,54,3,45)` form a small fan around
vertices 1, 6, 7, 54. Edge (7,54) is used twice by loop 1 and twice by
loop 2 (4 uses, one record); (1,7) once by each of the three loops;
(6,7) twice by loop 0 and once by loop 0 of record `0x338a68`
(`(4,12,6,14,7,15,5,13,3,11)`). The kept loop is 17,385.989 mm² =
47.8232 % of the part; a 341.517 mm² loop (0.9394 %, just under the 1 %
rule) is the only seam skip.

### 3.5 e8d9a358 — `SYSTEM/LedStrips_5V_final.CATPart`

Edge (27,28) (0.55 mm, written x identical, y 0.08 mm apart) is the first
rung of five 4-ref 0x42 strips (`(32,240,33,72)`, `(32,236,33,68)`,
`(32,237,33,69)`, `(32,239,33,71)`, `(32,238,33,70)`). Edge (28,58) joins
the 27,667.6 mm² face of the 4-ref strip `(32,236,33,68)` (its 56.4 mm-long
edge) with the 10-ref loop `(69,34,68,33,66,31,64,29,59,24)` (two faces).
Three kept loops (19.53 %, 10.03 %, 15.99 %) and one 66.8 mm² skip.

### 3.6 341bd488 — `frente_&_UPPER_teeth.CATPart`

The two degree-15 edges and (21614,21802) all come from **one writer
loop**: record `0x6b2990d`, marker 0x4a, counts `(114,)`, refs
`(4,45,4,48,4,34,…)` — a strip whose ref stream alternates between two
rail vertices and a sequence of far points, so every other triangle is a
page hinged on a rail edge. Store-level, the rail is (21613,21614) at
t = 82, 84, … 110 and (21614,21615) at t = 18, 20, … 46 (base 21,611).
The same loop is the seam's kept loop (4,868.093 mm² = 14.22 %), and the
same loop emits **all 28 of the store's degenerate skips** (its repeated
rail windows). Edge (21615,21616) is 3 faces from a 0x49 triangle
`(4,10488,5)` plus the 0x4a loop.

This store also carries 2,633 cross-rep coordinate-duplicate copies
(double-listed area 1,338.333 mm² = 3.911 % of the listed area); the dedup
fire gate declines them because they do not resolve the over-use. They do
not touch the over-used edges.

## 4. The two degenerate-triangle stores

Both meshes are **manifold**, non-empty and have finite plausible
bounding boxes; the only failed check is the degenerate count. Across the
whole corpus exactly three stores have `degenerate_triangle_count > 0`
(these two plus 341bd488), so `MAX_DEGENERATE_TRIANGLES = 0` blocks only
these rows — a gate policy question, not a geometry defect.

### 4.1 13bb5c0c — `SYSTEM/LedStrips_Smooth.CATPart` (33)

All 33 are `strip-zero-cross`: three *distinct* elements and three
*distinct* coordinates with an exactly-zero cross product. They come from
25 records, always **loop 1** (8 records contribute 2 triangles, 17
contribute 1). Every one of the 33 triangles is on the single line
`x = −88.78697967529297`, `y = 194.1308135986328`; the first **60 written
points** of the store are on that line (z 430.595 → 1,467.400), and none
of them is a pool vertex (the 43,050-vertex pool has zero points there).
The writer's second loop of those records is a strip *along* that straight
boundary — e.g. record `0xadeecca` loop 1 `(100,0,32,26)` — so every
window is collinear and skipped. The record's loop 0 carries a skip slot
and is dropped as a curve entry; loop 1 is fully written, so the law
rightly treats it as geometry and the skips are counted.

Source: writer-emitted zero-area boundary strips on a straight boundary.
Not a width artifact (this is the u24be store; width 3 is forced by the
236,385-element space, and the collinear points are exact f32 values in
the region's own point list).

### 4.2 b912cbef — `CATIA/CATIA_vol/_NPart#194321.CATPart` (3)

All 3 are `strip-repeated-coord` from **one loop**: record `0x1b2233`,
counts `(5,5,17,5,27,15,43,22)`, loop 0 `(0,0,37,0,0)`. Its windows
`(0,0,37)`, `(0,37,0)`, `(37,0,0)` repeat element 0, so they are skipped.
The writer emitted a degenerate "needle" loop at the head of the record;
the rest of the loop and the store are unaffected.

### 4.3 Gate-only

For 13bb5c0c and b912cbef the strict `MAX_DEGENERATE_TRIANGLES = 0` is the
only blocker: with the cap at 33 / 3 respectively both rows would pass
(the triangle lists already exclude the degenerate triangles, so the
exported mesh is manifold and unchanged). 341bd488 would surface the same
way after any manifold repair (its 28 skips are its rail-fan loop's).

## 5. Levers, measured (the law question)

The loop-level seam cannot move these rows: the refused loop that keeps
the store not-manifold is real surface (1,208 mm², 12.0 mm², 17,386 mm²,
…), and dropping it is exactly Option 1 of the seam note.

Two levers were measured on the same emitted triangle lists.

**T — minimum triangle-level trim.** On each over-used edge keep the two
largest incident faces and drop the rest (greedy smallest-area first).
Every store becomes manifold with holes; this is the *minimum* surface
the invariant costs, far below the loop-level cost:

| sha16 | triangles dropped | area lost mm² | % of store | boundary before → after |
|---|---:|---:|---:|---|
| 26504a08 | 2 | 3.368 | 0.0081 % | 1,027 → 1,027 |
| 341bd488 | 29 | 397.613 | 1.1618 % | 2,868 → 2,922 |
| 5689954c | 1 | 0.669 | 0.8539 % | 1,393 → 1,395 |
| 5a982112 | 13 | 76.505 | 12.9514 % | 835 → 851 |
| cd88ae9d | 3 | 197.256 | 0.5426 % | 1,046 → 1,047 |
| e8d9a358 | 4 | 133.673 | 0.1200 % | 4,292 → 4,292 |

**S — edge-sheet split.** For every over-used edge, duplicate its two
endpoints once per extra pair of incident faces and rewrite those faces
to the copies. This is the one law found that makes all six manifold
without deleting surface: **every triangle survives, every coordinate is
unchanged, the area delta is exactly 0.00e+00**, at the cost of 2-30
coincident vertices (and the corresponding boundary edges):

| sha16 | triangles | area delta | new vertices | manifold | would pass L2 |
|---|---:|---:|---:|---|---|
| 26504a08 | 3,071 (same) | 0.00e+00 | 2 | yes | yes |
| 341bd488 | 46,833 (same) | 0.00e+00 | 30 | yes | **no** — 28 deg skips |
| 5689954c | 1,692 (same) | 0.00e+00 | 2 | yes | yes |
| 5a982112 | 2,306 (same) | 0.00e+00 | 14 | yes | yes |
| cd88ae9d | 3,014 (same) | 0.00e+00 | 6 | yes | yes |
| e8d9a358 | 15,680 (same) | 0.00e+00 | 6 | yes | yes |

The split is a *representation* change, not a geometry fix: it declares
the sheets separate (coincident, shared-boundary-free) so the edge-use
invariant holds. It contradicts the merged-vertex discipline the
coordinate dedup advertises ("no vertex is invented, no edge is split"),
and it would export duplicate vertex records in the PLY. Whether that is
acceptable is an owner decision, not a decoder bug: the writer's data is a
non-manifold BRep — the faithful mesh has the over-use.

**Impact, if the levers were taken** (dev only; held-out is unaffected):
the split alone flips 5 rows (1,084 → 1,089 = 78.86 %); relaxing the
degenerate cap to 33/3 adds the two degenerate stores (→ 1,091 = 79.00 %);
341bd488 needs the cap ≥ 28 as well (→ 1,092 = 79.07 %). None of these is
proposed here.

## 6. What was NOT changed

- No `src/` or `port/` change, no gate change, no threshold change:
  `MAX_DEGENERATE_TRIANGLES` stays 0, `PRIMARY_LOOP_AREA_REL` stays 1 %,
  the seam's fire gate and the dedup's fire gate are untouched.
- No claim that any store is "wrong": the six over-uses are faithful to
  the writer's records; the L2 manifold invariant is stricter than the
  data (a policy question). The two degenerate rows are the same kind of
  question against a strict zero cap.
- 341bd488's 2,633 re-listed cross-rep facets remain exported (their drop
  is area-preserving but does not resolve the over-use, so the dedup's
  fire gate correctly declines); dropping them is a separate policy item,
  not part of this audit.

## 7. Relation to the close-out's reopen criteria

`2026-11-19-fidelity-close.md` section 2 already carries both rows as
documented negatives. This audit supplies the measurement those rows
asked for, and one correction:

- **Large over-uses (6).** The reopen criterion is "a law that resolves
  the over-use without deleting surface (edge split per sheet is
  fail-closed against)". The audit's contribution is the *premise*: the
  over-use is in the bytes (content), not a decode artifact, and the only
  law that resolves it without deleting surface is exactly the edge-sheet
  split the close-out already rules out. The row therefore stays a
  documented negative; the trade-off surface cost is measured for any
  future gate-policy decision (0.0081 %–12.9514 %).
- **Degenerate-triangles (2).** The close-out says "3 zero-cross slivers
  … (0.0096 % of the mesh)". That figure is b912cbef only (3 / 31,203 =
  0.0096 %); the row's population is **36 skipped triangles in 2 stores**:
  33 zero-cross on 13bb5c0c (33 / 152,010 = 0.000217, i.e. 0.0217 % of its triangles) and 3
  repeated-coord on b912cbef. Both meshes are manifold, so the reopen
  criterion (a relative degenerate cap) is a gate-policy decision, not a
  decode fix — and this audit reports the writer sources it needs.
