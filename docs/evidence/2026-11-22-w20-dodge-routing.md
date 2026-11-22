# W20 — the dodge routing verdict: cross-unit, cross-tessellation, no routing fix (2026-11-22)

Worker W20, marathon wave 4. Base `647f324` (main with all standing
laws). Deliverable: resolve the W12 dodge-challenger finding —
`matched=0`, `area_ratio 177.3`, bbox-diag ratio 10.16, "the export is
a ~10× foreign geometry; fix class ROUTING". Zero `src/`/`port/`
changes: every number below is a committed probe run against the
shipped decode (by-file-path triage imports, the W12 pattern).

## Commands (reproduction)

```bash
# H1: units/scale — identity sweep over the pool anchors AND the
# exported points, both directions, 9 candidate factors + permutations
python -B scripts/triage/w20_dodge_routing_probe.py \
  --catpart ~/.local/state/catpart-parser/bench-external/datasets/dodge/original.CATPart \
  --stl ~/.local/state/catpart-parser/bench-external/datasets/dodge/dodge_final1.stl \
  --phase pool --rep-csv docs/evidence/data/w20-dodge-pool-classes.csv
python -B scripts/triage/w20_dodge_routing_probe.py ... --phase decode \
  --rep-csv docs/evidence/data/w20-dodge-rep-routing.csv
# H2: routing — spatial bodies + rep attribution
python -B scripts/triage/w20_dodge_body_map.py ... --cell-mm 50 \
  --rep-csv docs/evidence/data/w20-dodge-rep-bodies.csv
# duplicate census (stage-15 identity over the exported mesh)
python -B scripts/triage/w20_dodge_dup_census.py --catpart ...
# CSV family hygiene
python -B scripts/triage/check_w20_csvs.py --selftest && python -B scripts/triage/check_w20_csvs.py
```

## 1. The scale question, measured (H1)

The reference STL (binary, streamed — never materialized): 435,988
triangles, 216,468 unique vertices, bbox diag **553.249**, extents
(217.683, 129.846, 491.771). The decode (this base): 2,017,633 points,
2,697,824 triangles, extents (2176.835, 1419.147, 4984.203), diag
**5620.931**.

**Identity is 0.0 at every candidate factor, in both directions, on
both point sets.** The probe sweeps factors {1, 0.1, 10, 2.54, 1/2.54,
25.4, 1/25.4, 0.001, 1000} as rounded-coordinate key intersections
(0.01 grid; f32 ulp at car scale ≤ 0.001, inside the half-grid): not
ONE of the 216,468 reference vertices coincides with any written
coordinate of the file — pool anchors (`w20-dodge-pool-classes.csv`)
or exported points including the 424,754 unused ones
(`w20-dodge-rep-routing.csv`) — at ANY factor. The permutation sweep
adds nothing (no axis assignment/flip exceeds 0.05).

Consequence: **the reference is not a rescaling of any tessellation
the file carries.** The W12 oracle's µm-identity match can never score
matched > 0 on this pair, regardless of routing or units.

What survives is this: the car body's x-extent matches the reference's
x-extent EXACTLY at ×10 (ours −1942.5543..234.2802; ref ×10
−1942.5543..234.2802 — f32-exact). Per-axis extent ratios ours/(ref×10):
x **1.0000000**, y **1.09293**, z **1.01352**. There is no pure factor
between the two meshes: the reference is the same car family
(x-extent bit-exact ×10 — the 1:10 unit relation), independently
re-tessellated, with y and z extents that differ by 9.3% and 1.4%
(a different variant/cut, not a unit). The harness's own historical
record already measured the shape-level distance
(`bench_results.on-8e13ed6.json`, `metrics_flags = ["scale~x10.16
(ref*0.09843 matches)"]`): chamfer centered+scaled **8.33 mm**,
hausdorff_max **128.1 mm** on a 5,621 mm object — same car, different
details, exactly what an independent re-tessellation of a variant
yields.

## 2. The routing question, measured (H2)

- **All 6,310 reps export** (rebuilt with the decode's own gates:
  absorption + the M2b refs gate; laws 4,557 table + 1,253 flat +
  500 raw; 0 declined reps, 0 failures —
  `w20-dodge-rep-routing.csv`). 424,754 of 2,017,633 exported points
  (21.05%) are unused by any triangle. There is no wrong-store pick
  and no multi-scale concatenation: every rep's point centroid falls
  in the ONE spatial body (`w20-dodge-rep-bodies.csv`).
- **The export is ONE connected body** (26-adjacency, 50 mm cells):
  2,697,586 of 2,697,824 triangles (99.999%), 30,229,703.79 mm²,
  spanning the full car bbox — plus two 119-triangle mirror twins
  (109.05 mm² each, 24×15×7 mm at x −522..−498 / −1209..−1185; no rep
  centroid inside them). W12's "main foreign body" (their top extra
  cluster, 2.03M tris) IS the car: the file's fine patch tessellation,
  connected, single-scale (mm).
- The file re-lists patches: reps 919/2334 and 3749/5164 carry
  IDENTICAL coordinate ranges (24,990 pts each), and reps 316/405
  (38,872 pts each) are the left/right x-halves of one region. The
  duplicate census (stage-15 unordered coordinate identity, 1 µm,
  over all 2,697,824 exported triangles): **duplicate_copies = 0**,
  duplicate_area = 0.00 mm², share 0.0000 — every exported triangle
  is coordinate-unique; the identical-range reps re-triangulate
  differently. The 2.022 physical area excess against the reference
  is therefore NOT exact duplication: it is overlapping
  distinct-coordinate patch surfaces and/or the variant's own extra
  area (the two sources are not separated by this probe). The
  stage-15 dedup law correctly has nothing to drop here — its gate
  requires the deduplicated list to RESOLVE the assembled mesh's
  non-manifoldness, and with zero duplicates there is nothing to
  dedup.

## 3. The metric decomposition (before/after)

`area_ratio` (harness, current base): 30,229,921.89 / 149,504.95 =
**202.20** — decomposes exactly into **×100 units** (ref cm² vs ours
mm²; the file has no unit field — the documented negative,
`docs/format/payload-blocks.md` §5.3) × **2.022 physical** (overlapping
distinct-coordinate patch surfaces + the variant's own area; exact
duplicates measured 0 — §2). W12's 177.3 measured base `65b7a0e`
(26.51M mm², 2,496,624 tris); the wave-13→20 laws grew the dodge
export by +14% area (no dodge gate existed; the four gated pairs
stayed clean).

`matched` (µm triangle identity): 0 of 435,988 before; **0 after —
structurally: different tessellation (identity 0.0 at every factor) +
×10 units (no unit field exists to read)**.

**Verdict: NEGATIVE for a parser-side fix.** The routing hypothesis is
refuted with the map: no wrong store (single composite store, single
body), no scale mixing (one scale, mm), nothing declined that should
export (0 rep declines). The reference is an external 1:10,
re-tessellated VARIANT of the car — a benchmark-side artifact, not a
fidelity loss the parser can close. Per the dispatch rules this is the
hypothesis-3 exit: the exact map (reps, members, bodies, bboxes) is
committed and the ticket reopens only on the criteria below.

## 4. Reopening criteria

1. A tessellation inside the CATPart (any path: composite, surfaces,
   face-gp, display carriers) whose vertex coordinates coincide with
   the reference ×10 at the 0.01 grid — the identity sweep is the
   acceptance test; today it is 0.0 over every written coordinate.
2. A unit-field discovery that overturns the documented negative
   (payload-blocks §5.3) — then the export unit law becomes decidable
   and the ×100 metric term closes.
3. A benchmark-side decision to compare against `ref×10` (unit-
   normalized pairing): the target becomes the physical 2.022, and the
   duplicate share (census) becomes the actionable parser-side number.

## 5. What the probes do NOT discriminate

- The identity sweep covers WRITTEN coordinates; a surface/face-gp
  path could carry unwritten geometry (W15/W16 territory — untouched
  here; criterion 1 covers the finding if it ever lands).
- The body map attributes reps by centroid: a rep spanning bodies
  counts once (the two 119-tri bodies have no centroid inside them).
- The duplicate census is winding-independent: a flipped-winding copy
  still counts as a duplicate (the stage-15 convention).

## Artifacts

`scripts/triage/w20_probe_lib.py`, `scripts/triage/w20_dodge_routing_probe.py`,
`scripts/triage/w20_dodge_body_map.py`, `scripts/triage/w20_dodge_dup_census.py`,
`scripts/triage/check_w20_csvs.py`;
`docs/evidence/data/w20-dodge-pool-classes.csv`,
`docs/evidence/data/w20-dodge-rep-routing.csv`,
`docs/evidence/data/w20-dodge-rep-bodies.csv`.
Every figure traces to one of those CSVs, to the probe JSON the
commands print, or to `bench_results.on-8e13ed6.json`.

## 6. Decode counters on this base (info, one decode)

Stage `identity-mixedwrite-reps`; the decode's own counters on
`647f324`: `element_decl` 2,017,640 / `node_points` 2,017,633;
`reps_decoded` = `reps_exported` = 6,310, `reps_unexported` = 0;
`rep_laws` {table 4557, raw 500, flat 1253}; `loops_exported` 108,247
(+5 curve-entry dup-pin loops); relaxed loops 534 accepted / 168
declined; `curve_entries` 7; `extended_header_records` 1,729 carrying
**2,565,529 triangles** (95% of the mesh), `extended_header_declined`
27 with **`extended_members_filtered` 41,031** (W12's 126,722 was
their base's figure). The 27 declined ext records would only ADD
area if exported — they cannot move `matched` (identity 0.0) and
worsen `area_ratio`; the residual decline is documented, not a fix
surface for this finding.
