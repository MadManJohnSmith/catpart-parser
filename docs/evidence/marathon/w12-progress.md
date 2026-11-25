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
- 2026-11-22 (4): dodge complete. Store map: 6,310 reps exported
  (base_check true), 531,614 unused pool verts (26% of points),
  126,722 extended-header members filtered, no seam skips, 236 gaps —
  124 of them OWN unused vertices (0x47/0x4f/0x41/0x4a/... mixed);
  rep 244's gaps own 22,144 unused verts at a ref-geometry location.
  Oracle: extra = ALL 2,496,624 our tris / 26.51M mm² / 594 clusters
  (top 2.03M-tri foreign body); missing = the whole ref surface
  (149,504.95 mm², 8 clusters); far_ref capped at 80 mm for all
  216,739 ref verts. Fix class: ROUTING (composite/unclassified).
  + `check_w12_csvs.py` (width/format checker for the new w12-* data
  family, --selftest-pinned, wired into scripts/check.sh).

## Status

- audi-r8: DONE (oracle + map + join).
- ducati-panigale-1199: DONE.
- dodge-challenger: DONE (oracle + map + join).
- Handoffs: → W10 (curve-entry/U4 loop declines = the missing-area
  family; seam slivers 642.7k mm² on audi; ext 0x41 gap families),
  dodge routing failure → composite/unclassified owner (rep 244 probe
  target). W4/W9 not triggered.

## Rules honored

0 src/ edits; no subagents; `python -B` everywhere; only
`scripts/triage/` + `docs/evidence/` touched; memory-gated (pytest gate
checked before heavy runs; dodge run last with `free -m` verified).

Gate note (2026-11-22): the push ran WITHOUT a second full check.sh —
the orchestrator's own check.sh was in flight on the main checkout
throughout (10+ min: cargo native + wasm32 + clippy + tests), and a
duplicate full gate would have contended for memory against it (the
anti-OOM brief's scenario). Local verifications actually run: pinned
ruff 0.17.4 over all four new scripts (clean), check_w12_csvs.py over
the 12 committed CSVs (ok), bash -n on check.sh, py_compile on every
script. The diff carries no runtime code (docs + scripts/triage only;
pytest does not collect scripts/), so the skipped duplicate run's
coverage delta is the cargo steps, untouched by this diff. CI and the
orchestrator's merge gate remain the authority for main.

**Later update (2026-11-25)**: W20
(`docs/evidence/2026-11-22-w20-dodge-routing.md`, merged with this note)
tested the Dodge "routing" inference. The reference is an independently
re-tessellated 1:10 variant (x-extent f32-exact at ×10; y/z differ
9.3 %/1.4 %), and all 6,310 reps export as one connected body with no
wrong-store pick. W20 therefore **supersedes this note's causal verdict**
("fix class ROUTING") while the oracle data (`matched=0`, Audi/Motor
connectivity) stands.
