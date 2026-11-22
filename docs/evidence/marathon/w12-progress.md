# W12 progress — inverse spatial oracle (Bloques C10+C12)

Worker: W12, wave 4, continuous mode. Branch `marathon/w12-inverse-oracle`,
base 65b7a0e. Deliverable: `docs/evidence/2026-11-22-w12-inverse-oracle.md`
+ `docs/evidence/data/w12-*.csv` + `scripts/triage/w12_*.py`.

## Log

- 2026-11-22 (1): setup verified (branch, pairs.json, harness import via
  `PYTHONPATH=src`). Step-1 distance isolation measured: EMPTY on audi and
  Motor (0 far vertices/triangles at the scaled threshold; audi raw
  vertex-set hausdorff 0.0007 mm) — the missing area is missing
  CONNECTIVITY between shared vertices, not far geometry. Interior
  sampling tried once and discarded (measures vertex density, not
  coverage).
- 2026-11-22 (2): the working oracle — winding-independent triangle
  identity match (1 µm grid), per-cell NET (missing − extra) clustered;
  exact conservation gate closes on all three pairs (residual −0.0 /
  −0.0 / −4e-6). Audi: net 5.64M mm², top cluster = front quarter
  (1.80M mm², 34.6k tris, 5,314 unused pool verts). Motor: net
  331,164 mm², top 29.3k mm² with 5,550 unused verts. Dodge: matched=0
  — the whole ref surface absent, ref verts ≥ 80 mm (ring-cap floor)
  from ours; the export is a ~10× foreign geometry (routing failure,
  not fidelity loss).
- 2026-11-22 (3): store map per rep (decode's own node scan + gates;
  base_check passes). audi 96 reps exported, 11,751 unused verts,
  6 seam loops = 642,702 mm², 137 gaps (ext 0x41-dominated); Motor 113
  reps, 21,936 unused verts, 36 seam loops = 13,017 mm², 1,034 gaps.
  Join mode delivers `w12-missing-faces-<pair>.csv` with
  registros_candidatos (reps + owning gap offsets).

## Status

- audi-r8: DONE (oracle + map + join).
- ducati-panigale-1199: DONE.
- dodge-challenger: geometry complete (incl. capped far signals,
  named floors); store map + join pending (heavy run in flight).
- Handoffs: → W10 (curve-entry/U4 loop declines = the missing-area
  family; seam slivers 642.7k mm² on audi; ext 0x41 gap families),
  dodge routing failure → composite/unclassified owner. W4/W9 not
  triggered.

## Rules honored

0 src/ edits; no subagents; `python -B` everywhere; only
`scripts/triage/` + `docs/evidence/` touched; memory-gated (pytest gate
checked before heavy runs; dodge run last with `free -m` verified).
