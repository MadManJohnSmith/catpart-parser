# W12 — the inverse spatial oracle (Bloques C10+C12, 2026-11-22)

Worker W12, marathon wave 4. Base `65b7a0e`. Deliverable: localize
WHERE the fidelity gap lives for the three external pairs with
area_ratio far from 1 — audi-r8 (0.8775), ducati-panigale-1199 /
Motor (0.828), dodge-challenger (177.3, bbox-diag ratio 10.16) — and
map each spatial cluster to the concrete declined/not-decoded
CATPart records. Zero `src/`/`port/` changes; everything reuses
committed code (the W7 harness's readers/grids/areas, the composite
decode, the probe_top10 gap machinery), by file-path import.

## Commands (reproduction)

```bash
# geometry side (per pair; dodge: --max-ring 8 --cell-mm 10, see §3)
python -B scripts/triage/w12_inverse_oracle.py --pair audi-r8 \
  --pairs-json ~/.local/state/catpart-parser/bench-external/pairs.json \
  --csv docs/evidence/data/w12-oracle-raw-audi-r8.csv
# store side (per pair)
python -B scripts/triage/w12_store_decline_map.py --pair audi-r8 \
  --pairs-json ~/.local/state/catpart-parser/bench-external/pairs.json \
  --records-csv docs/evidence/data/w12-declined-records-audi-r8.csv \
  --spatial-csv docs/evidence/data/w12-store-spatial-audi-r8.csv
# the deliverable join
python -B scripts/triage/w12_store_decline_map.py --pair audi-r8 \
  --join-missing docs/evidence/data/w12-oracle-raw-audi-r8.csv \
  --records-csv docs/evidence/data/w12-declined-records-audi-r8.csv \
  --spatial-csv docs/evidence/data/w12-store-spatial-audi-r8.csv \
  --joined-csv docs/evidence/data/w12-missing-faces-audi-r8.csv
```

(`pairs.json` lost its dodge entry at 12:45 today — another worker's
edit; the dodge commands pass `--catpart/--reference` explicitly with
the same paths the 5-pair file carried: `datasets/dodge/original.CATPart`,
`datasets/dodge/dodge_final1.stl`.)

## 1. The brief's step 1 measured, and what it means

The distance isolation (ref→ours > 1 mm, exact per-vertex by the
harness's ring-outward voxel search) is EMPTY for audi AND Motor:

| pair | ref verts | far verts (>1 mm-scaled) | far tris |
|---|---|---|---|
| audi-r8 | 113,519 | 0 | 0 |
| ducati Motor | 125,568 | 0 (thr. 0.188 mm) | 0 |

This is a finding, not a failure: the harness's own numbers (audi raw
vertex-set hausdorff_max 0.0007 mm; Motor 0.0735 mm centered) say every
reference vertex ALREADY sits on our vertex set. The missing area lives
between shared vertices — it is missing CONNECTIVITY, and no vertex
distance can see it. A centroid+midpoint interior-sampling oracle was
tried first and measured vertex density, not coverage (every interior
point is >1 mm from the nearest vertex on meshes this coarse); it is
documented here as the discarded attempt (2-tries rule: one try used).

## 2. The oracle that works: winding-independent triangle identity

Both meshes are triangulations over (nearly) the same vertex set, so
the oracle matches TRIANGLES by coordinate identity: each triangle's
three vertices rounded to the 1 µm grid, sorted, packed — a triangle
is matched iff the other mesh contains the same key. Unmatched ref
triangles = the missing faces; unmatched our-triangles = extra. Both
sides bucket per centroid cell (diag/256) and cluster by 26-adjacency;
the CLUSTERED signal is the per-cell NET (missing − extra), because
retriangulated regions (different diagonal splits over the same
vertices) cancel cell by cell.

**The conservation gate** (exact, algebraic):
`ref_area − ours_area = (matched_ref − matched_ours) + missing − extra`,
so `missing − extra − gap` must equal the µm-coordinate noise term
`matched_ours − matched_ref`. All three pairs close:

| pair | gap (harness) | missing − extra | precision term | residual |
|---|---|---|---|---|
| audi-r8 | 5,641,329.87 | 5,639,631.58 | −1,698.29 | −0.0 ok |
| ducati Motor | 331,163.68 | 331,163.68 | −0.01 | −0.0 ok |
| dodge | −26,361,020.2 | −26,361,020.2 | 0.0 | −4e-6 ok |

Per-side conservation is exact too (matched + missing = ref_area,
−0.0 both pairs). The regime assumption (coincident vertices, missing
connectivity) is proven for audi/Motor and REFUTED for dodge (§3).

### audi-r8 (area_ratio 0.8775)

Raw masses: missing 98,072 tris / 18.94M mm², extra 46,436 tris /
13.30M mm² (33% of our area is retriangulation over shared vertices),
matched 127,901 tris / 27.10M mm². Net clusters: 1,520; top-10
(`w12-missing-faces-audi-r8.csv`):

| # | net mm² | cells | missing tris | seam-skip verts | unused verts |
|---|---|---|---|---|---|
| 1 | 1,803,266 | 7,509 | 34,635 | 45 | 5,314 |
| 2 | 594,042 | 1 | 1 | 0 | 16 |
| 3 | 592,419 | 1 | 1 | 0 | 15 |
| 4 | 466,752 | 2,820 | 15,845 | 0 | 1,610 |
| 5 | 356,954 | 1 | 1 | 0 | 2 |
| 6 | 346,999 | 1 | 1 | 0 | 1 |
| 7 | 346,814 | 2,543 | 15,245 | 174 | 1,317 |
| 8 | 245,594 | 489 | 2,571 | 0 | 678 |
| 9 | 172,488 | 15 | 17 | 0 | 37 |
| 10 | 172,488 | 15 | 17 | 0 | 37 |

(#1 = the car's front quarter, bbox x −4317..−3059; #9/#10 and #2/#3
etc. are ±y-symmetric pairs — fenders/flanks; #2/#3/#5/#6 are the
giant flat z=247.7 underbody panels, one unmatched ref triangle each.)

### ducati Motor (area_ratio 0.828)

Missing 122,701 tris / 680,897 mm², extra 35,357 / 349,733, matched
128,679 / 1,238,761. Net 384,254 mm² in 1,586 clusters; top-10
(`w12-missing-faces-ducati-panigale-1199.csv`): #1 29,278 mm²
(3,300 cells, 16,333 tris, 5,550 unused verts), #2 22,868 (4,504
unused), #3 22,072 (3,952), #4 13,060, #5/#6 ~12,400 single-cell with
1,200+ unused verts each, #7 12,266, #8 10,536, #9 4,932, #10 4,890.

## 3. dodge-challenger: the regime REFUTED, the ref object absent

matched = **0 of 435,988** ref triangles; missing = the WHOLE ref
surface (149,504.95 mm² = area_ref, conservation exact); extra = ALL
2,496,624 of our triangles (26.51M mm², 594 clusters — top cluster
195,237 cells / 2,034,946 tris, the main foreign body); 216,739 of
216,739 ref vertices ≥ 80 mm (ring-cap floor, `--max-ring 8`) from
every one of our 1.25M vertices. Our export (2,496,624 tris / 26.51M
mm², bbox diag 5,621 mm vs the ref's 553 mm — the 10.16× the brief
names) contains NO part of the reference object: it is a DIFFERENT
geometry at ~10× scale. (Cluster inventories:
`w12-oracle-raw-dodge-challenger.csv`; the pair column there reads
`original` because the dodge commands pass `--catpart` explicitly.)

## 4. The store side: what was declined, per pair

`w12_store_decline_map.py` walks the decode's own per-rep structure
(`_scan_token_nodes`/`_rep_node_positions`/`_decode_rep_node`), frames
gaps per rep territory with the probe_top10 machinery, and reports
four coordinate-bearing signals. The registry decode pops
`info['_space_offsets']` without re-attaching it, so rep bases are
rebuilt by the decode's own gates (absorption + refs); `base_check`
(rebuilt base sum == len(points)) passes on all three pairs.

| signal | audi-r8 | ducati Motor | dodge |
|---|---|---|---|
| stage | identity-per-rep | identity-mixedwrite-reps | identity-mixedwrite-reps |
| reps exported / declined | 96 / 0 | 113 / 0 | **6,310 / 0** |
| unused pool vertices | **11,751** | **21,936** | **531,614** (26% of points) |
| curve entries (in store) | 22,466 | 5,616 | 7 |
| seam-skipped loops | 6 loops = 73 tris = **642,702 mm²** | 36 loops = 71 tris = 13,017 mm² | 0 (no seam) |
| extended-header declined | 29 (members filtered 985) | 33 (418) | 72 (**126,722 filtered**) |
| gap clusters (unresolved candidates) | 137 | 1,034 | 236 |
| gap records owning unused verts | 10 | 20 | **124** |

The dominant family on BOTH audi and Motor: the unused pool vertices
are the written vertices of curve-entry/U4 loops declined at emission
(their coordinates are pool-written, their connectivity record is a
skip-bearing loop the battery refused; only the dup-pin subset
exports). They fall INSIDE accepted records — the per-gap framing
sees only the residue: 137/1,034 unresolved candidates, dominated by
`ext 0x41` headers (audi 108, Motor 937) plus 0x42/0x47/0x4f/0x4d
families. The join (`registros_candidatos` column) ties clusters to
reps and to the owning gap records (audi #1: reps 38/53/80/90/…, gap
offsets 45031183, 50424943, 48515236, 48549226, 49656244, 49677046;
Motor #1: rep 7 gaps 50218123/50365277/50384964, rep 18 gap 52321935).

Dodge differs: 6,310 tiny reps (≈320 points each), NO seam skips,
only 7 curve entries — and 124 of 236 gap records OWN unused vertices
(ext 0x47×51, 0x4f×27, 0x41×19, short 0x4a×18, 0x42×13, 0x48×13,
0x46×12, 0x4d×11). Its missing-ref clusters' join: the three largest
(#1 74,242 mm², #2/#3 33,991 mm² each — the ref object's main faces)
carry ZERO unused pool vertices (the ref's vertices are not in our
pool at all), while #4 (5,475 mm²) carries 22,144 unused vertices of
rep 244 owned by gap offsets 62431761/62435201/62462384/62464933/
62466205/62516390 — one rep whose declined records sit exactly where
reference geometry should be.

## 5. What the oracle does NOT discriminate (per the detector rule)

- The net signal cancels retriangulation only cell-wise at diag/256;
  single-cell giant-triangle rows (#2/#3/#5/#6 audi) can be either a
  genuinely unmatched ref panel or a retriangulation pair whose halves
  straddle cells — the unused-vertex join separates them (16/15/2/1
  unused verts respectively; the 594k-mm² pair has 16+15 unused pool
  vertices inside → likely real declined panels, labeled candidate).
- `far_at_cap` floors distances at max_ring×cell (dodge only): the
  80 mm figure is a floor, not a measurement.
- Winding-independent matching cannot see orientation flips (an
  area-conserving inverted face reads as matched).
- The gap-index interval is labeled INFERENCE (walk order makes
  before/after refs bound the declined record's refs, not proven).

## 6. Handoffs (no src/ change from W12)

- **→ W10 (composite)**: (a) curve-entry/U4 loop declines are THE
  missing-area family on audi (11,751 unused verts, front-quarter
  cluster carries 5,314) and Motor (21,936): the dup-pin battery's
  coplanarity/manifold guards refuse loops whose vertices are already
  pool-written — the spatial inventory above is the acceptance test
  for any law widening; (b) the primary-emit seam's 6 skipped loops
  cost 642,702 mm² on audi (11.4% of the gap) — 73 slivers whose
  removal the manifold gate wanted but the area ledger pays for; (c) 137
  (audi) / 1,034 (Motor) unresolved gap candidates, `ext 0x41`-
  dominated, sit in the same territories as the unused-vertex mass.
- **→ W4 (display/face_gp) / W9 (product)**: not triggered by this
  run — all three pairs decode through the composite path; no
  display-carrier or product-level decline surfaced in the mapped
  spans.
- **→ dodge owner (composite/unclassified)**: the export is a ~10×
  foreign geometry, not a fidelity loss: matched=0 with exact
  conservation and ≥80 mm vertex floors. The fix class is ROUTING
  (which reps/scale the exporter picks for this file), not emission
  law — the store map's numbers (6,310 reps, 531,614 unused points,
  126,722 extended-header members filtered, 124 gap records owning
  unused vertices) plus the extra-direction clusters in
  `w12-oracle-raw-dodge-challenger.csv` are the entry point; the
  rep-244 gap cluster (22,144 unused verts at the ref's own location)
  is the first concrete probe target.

## Artifacts

`scripts/triage/w12_oracle_lib.py`, `scripts/triage/w12_inverse_oracle.py`,
`scripts/triage/w12_store_decline_map.py`;
`docs/evidence/data/w12-{missing-faces,oracle-raw,declined-records,store-spatial}-<pair>.csv`
for the three pairs. Every figure above traces to one of those CSVs or
to the JSON the commands print.
