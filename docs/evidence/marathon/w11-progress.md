# W11 progress — analytic surfaces & NURBS outside E5 (B8, 2026-11-22)

Branch `marathon/w11-analytic-surfaces`, base `8e13ed6`. Population: the
10 `undecoded-variant` rows of `fitness/reports/20261121T103944Z-d2c9ff.json`
(all dev, resolved by sha256). Exclusive files respected: `brep/` untouched,
new `geometry/analytic.py` + `port/src/geometry/analytic.rs`, no
`display/face_gp`/`composite/facets/vote/mesh/pool`/`surface/grid`/`product`
edits, `export.{py,rs}` untouched (no wiring — nothing to flip).

## Hypotheses and outcome

1. **H1 exact analytic blocks (axis+radius+limits)** — RESOLVED NEGATIVE
   with a taxonomy. The store bodies are a template object stream: the
   only analytic objects are class-`0x56` plane records whose direction
   pair is byte-identical in every observed file (two measured default
   pairs; 19/19 template across the population, and the same defaults in
   passing files' bodies — a format constant, not part geometry). No
   record carries bounds; no cylinder/cone/sphere block exists anywhere
   in the 10 (store bodies, bulk frames, CGM region). The bulk frames
   (A/B law, 91–95 % framed) carry scalar limits and feature parameters
   only. One attempt consumed; the second was not needed.
2. **H2 evaluable NURBS** — RESOLVED NEGATIVE for this population,
   with W3's route respected: the E5 class-`0x00e7` exact-surface law
   (d4a1fbc) is not re-derived; W3's own census anchored on the 10
   sha16s reports 0 records (CT-03 0/0). BR5 content signatures: 0 knot
   runs, 0 weight runs. `a5 03 34` frames: 0.
3. **Outcome 3 (taxonomy)** — DELIVERED: per-file taxonomy with body
   size, template/per-part plane split, bulk dialect, per-part scalars;
   the zero-carrier census (0 pools, 0 a5, 0 E5, 0 grids, 0 face-gp
   BagRep, 0 display points); measured bound = the parts carry no
   surface-describing bytes at all; reopening criteria in the note §5.

## Measured

- 10/10 verdict `no-evaluable-analytic-surface` (W11-01); export class
  unchanged `undecoded-variant` (W11-07) — no runtime change, 0 L2
  regressions by construction (dev/held-out untouched: no gate edits).
- Bulk dialect split 5 object-stream / 5 E5; the E5 contents are a
  4,116-B template stream with ≤ 20 differing bytes per file pair.
- Parity: Python=Rust on all 10 taxonomy rows (10 columns/row) via
  `port/tests/analytic_parity.rs` against the committed CSV, plus
  mirrored synthetic fixtures (22 Python + 17 Rust tests).
- Control (6 seeded clean files): the detector discriminates — 3 flip
  `analytic-present` on real carriers (2,218 `a5` frames + 18 knot
  runs; 2 × 3 weight runs), the template-plane control hits 5/6.

## Commits (this branch)

1. `9ced80a` feat(geometry): analytic availability scanner + 22 tests
2. `184e025` feat(triage): w11 probe + measured CSVs (W11-01..08)
3. `177f771` port(geometry): analytic twin + corpus parity gate
4. evidence note + this progress file (last commit)

Evidence: `docs/evidence/2026-11-22-w11-analytic-surfaces.md`,
`docs/evidence/data/w11-analytic-{files,claims}.csv`.

## Negative closed

The 10 `undecoded-variant` official rows carry no direct analytic
surface record and no NURBS payload outside W3's E5 route: the class is
the honest classification for zero-carrier parts. Reopen only on a
corpus change (probe exit 2) or the store-body framing-law recovery
(note §5).
