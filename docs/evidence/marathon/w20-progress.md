# W20 progress — dodge routing verdict (Bloque W12-dodge)

Worker: W20, wave 4, continuous mode. Branch `marathon/w20-dodge-routing`,
base `647f324`. Deliverable: `docs/evidence/2026-11-22-w20-dodge-routing.md`
+ `docs/evidence/data/w20-dodge-*.csv` + `scripts/triage/w20_*.py`.

## Log

- 2026-11-22 (1): setup verified (`PYTHONPATH=src` import resolves to
  this worktree; gate windows honored — the orchestrator's/peer pytest
  runs were polled before every heavy job; all probes ran single-file,
  `del`+release, streaming STL). Reference measured by streaming: 435,988
  tris, 216,468 unique verts, diag 553.249, extents (217.683, 129.846,
  491.771). Pool anchors measured: 6,310 groups carry only 120,880
  points — the exported geometry lives in the token-node regions, so
  the units question was re-aimed at the decode's points.
- 2026-11-22 (2): H1 measured — vertex-identity 0.0 at every candidate
  factor {1, 0.1, 10, 2.54, 1/2.54, 25.4, 1/25.4, 0.001, 1000}, both
  directions (ref->points, points->ref), on pool anchors AND exported
  points (2,017,633 pts incl. 424,754 unused); permutation sweep ≤ 0.05.
  The ref is NOT a rescaling of any written tessellation. Surviving
  evidence: the car body's x-extent is f32-EXACT vs ref ×10
  (−1942.5543..234.2802 both); per-axis extent ratios x 1.0000000,
  y 1.09293, z 1.01352 — no pure factor; the harness's own centered+
  scaled metrics (8.33 mm chamfer / 128.1 mm hausdorff_max) say same
  car family, independently re-tessellated variant.
- 2026-11-22 (3): H2 measured — ALL 6,310 reps export (4,557 table +
  1,253 flat + 500 raw; 0 declines); ONE connected body owns 99.999%
  of the mesh (2,697,586 of 2,697,824 tris, 30,229,703.79 mm², full car
  bbox) + two 119-tri mirror twins (109.05 mm² each); every rep
  centroid in that body (no wrong store, no scale mixing). Duplicate
  census (stage-15 identity): 0 duplicate copies — 2,697,824 unique
  keys; the identical-range rep pairs re-triangulate differently.
- 2026-11-22 (4): metric decomposition — area_ratio 202.20 on this
  base (30,229,921.89 / 149,504.95) = ×100 units × 2.022 physical
  (overlap/variant, NOT duplication). matched=0 is structural:
  different tessellation + units with no unit field to read (documented
  negative, payload-blocks §5.3). W12's 177.3 was base 65b7a0e; the
  wave-13→20 laws grew the dodge export +14% area (no dodge gate;
  the four gated pairs stayed clean). VERDICT: negative for a
  parser-side fix; map committed; three reopening criteria in the note.
- 2026-11-22 (5): decode info counters on this base captured (see the
  note §6); CSV family checker `check_w20_csvs.py` committed with
  --selftest (wired locally; the one-line check.sh wiring is a
  coordinator handoff — scripts/check.sh is outside this ticket's
  exclusive files).

## Status

- dodge-challenger: DONE — negative with exact map + reopening criteria.
- 0 src/port changes (probe-only ticket; parity N/A, no emission law
  touched, no gated pair re-run needed — the diff carries no runtime
  code).
- Handoffs: → coordinator (check.sh one-liner for check_w20_csvs.py);
  → benchmark owner (the pair is cross-unit ×10 and cross-tessellation;
  ref×10-normalized pairing would make 2.022 the target and re-enable
  the parser-side census route); → W15/W16 (nothing to take: the
  identity sweep covers the surface/face-gp paths' written coordinates;
  unwritten geometry is criterion 1's reopening edge).

## Rules honored

No subagents; `python -B` everywhere; only `scripts/triage/` +
`docs/evidence/` touched; memory-gated (heavy jobs only when
available > 4 GB, one large file at a time, streaming STL never
materialized); max-2-tries per hypothesis respected (H1: 1 probe
family; H2: 1 probe family + census).
