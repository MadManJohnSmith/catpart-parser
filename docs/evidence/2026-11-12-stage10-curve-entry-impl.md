# Evidence: stage-10 implementation of the E0-b dup-pin law (the U4 curve-entry coordinates, restricted) (2026-11-12)

Ticket #34 (G6 stage 10): the landed analysis's restricted recommendation
(`docs/evidence/2026-11-12-curve-entry-analysis.md` section 5, claims row
`U4-stage5-recommendation`; the stage-9-baseline recompute addendum)
lands in `src/catpart/geometry/composite.py` (branch
`t3/e0-curve-entry-impl`, this worktree off main `9630285`):

- **The law (U4-D dup pin, ported from the stage-4a decoder's
  `dup_prev` — not re-derived)**: a loop-referenced skip slot welds to
  the written vertex of its immediately preceding written element (the
  per-face copy; NO new vertices — the exported vertex list is
  unchanged).
- **The restriction (E0-b, the landed analysis's battery-supported
  subset)**: a store exports its dropped curve-entry loops ONLY when
  (a) its primary triangulation is EMPTY (the census's `empty-mesh`
  class — E0 by construction: it can only move fail -> pass, so no L2
  pass can regress), and (b) EVERY dropped loop is battery-supported —
  its record carries a 12-B normal AND the loop is coplanar against
  that normal with the dup-pinned coordinates (the stage-3b battery,
  `PLANE_TOL`; the analysis's criterion "coverage full AND zero
  nonplanar").  One normal-less (untestable) or nonplanar dropped loop
  keeps the WHOLE store on the conservative `curve-entry-loops-
  unexported` rule with its warning.
- **Implementation choice (named per the dispatch): a law-level
  predicate, NOT a digest gate.**  The pre-declaration probe (claims
  row `U4-E0b-live-predicate`) evaluated the predicate LIVE on the
  exporter's own decode of all 26 current E0 members and it selects
  EXACTLY the 4 battery-supported stores (`2fca9bc4`, `4ad53b87`,
  `4ae0392d`, `505bbe1f`) — matching the committed
  `e0_battery_supported` classification on every store the analysis
  measured; the 3 former census-scope-blind stores measure normal-less
  (untestable) live, closing their battery-unknown gap.  A digest gate
  would freeze the corpus instead of the law.
- **Scope**: wired on all three exported decode paths — the single-rep
  table walk (`decode_composite_store`), the per-rep decomposition
  (`_decode_per_rep`) and the mixed-write composition
  (`_decode_mixedwrite`).  The per-rep paths gate the merge on the
  WHOLE store's mesh being empty: a rep-level fire inside an
  otherwise-exporting store would be exactly the 471-passing-stores
  downside exposure the analysis warned about.  The raw-array path is
  untouched (all-written element space — no skip slots exist there).
- **NOT implemented**: the U4-M mid law (DEMOTED to unsupported in the
  landed analysis; the battery discriminates dup from next/mid wherever
  a loop references a slot — twin probe, section 4).  Unreferenced
  skip slots never enter a loop or a triangle either way.
- **Counters/warnings**: a fired store's info block gains
  `curve_entry_law: "e0b-dup-pin"` and `loops_curve_entry_exported`;
  `loops_curve_entry` counts only the loops still dropped (0 when the
  law exported them all — the E0 membership join's `loops_curve_entry>0`
  arm therefore leaves a fired store, correctly: it is no longer
  empty-mesh).  New warning class `curve-entry-loops-exported-dup-pin`
  (schema enum + composite description extended additively).

Labels: **fact** = measured/cited from a committed artifact;
**inference** = derived, reasoning shown; **unknown** = open.

## Tests (both directions, corpus-free)

Six fixtures (`tests/fixtures_gen.py`, `geometry-composite-law-e0b-*`):
two positives (the two-loop `2fca9bc4`/`505bbe1f` shape and the
one-loop `4ad53b87`/`4ae0392d` shape — the law fires, the exported
faces pin the WELD to the pin targets' written ranks) and four
negatives: the `3dff4d93` nonplanar shape, the `08f2eccb` normal-less
mixed-coverage shape, the non-empty-mesh shape (a passing store with a
battery-supported dropped loop — 12 triangles, NOT 14), and the
multi-rep store-level gate (rep 1's supported dropped loop stays
dropped because rep 0 exports its box).  Removing the law goes red on
the positives; removing the conservative gate (the empty-mesh
condition, the coverage requirement, or the store-level scope) goes
red on the negatives.  Gate: ruff clean, 333 passed + 7 skipped
(worktree-local venv — the main `.venv`'s editable install shadows
worktree src).

## The DECLARED A/B delta (committed BEFORE the corpus run)

Basis: the pre-declaration per-store probe — the 4 stores exported
through the seam with this branch's code
(`ab_identity_export.py --include-sha16 <the 4>`, 2026-11-12; all four
measured `pass` with the triangles below) plus the 26-member live
predicate probe (every other E0 member measured conservative).  The
fitness row itself stays with the coordinator.

- **D1 (exports)**: 1,120 exports UNCHANGED — 0 gained (E0 stores are
  already exported; the law adds triangles to existing exports), 0
  lost (the law runs after a successful decode and cannot raise; no
  decode path changes for any store the law does not fire on).
- **D2 (L2 gate)**: dev **948 -> 952 (+4 EXACTLY, measured on the 4
  stores pre-declaration: all four flip `empty-mesh` -> `pass`)**;
  held-out 55/61 UNCHANGED (the only held-out E0 member `1b1ae784`
  keeps the conservative rule — all its dropped loops are
  normal-less); 0 lost passes; L1 untouched (no format/CLI changes).
- **D3 (row-level)**: EXACTLY 4 of the 1,442 census rows differ; every
  other row byte-identical — including the 22 other E0 members (0
  triangles added: all measured conservative pre-declaration).
- **D4 (the 4 rows' exact transitions)**:
  `triangle_count` 0 -> 4 (`2fca9bc4`), 35 (`4ad53b87`), 35
  (`4ae0392d`), 4 (`505bbe1f`); `loops_curve_entry` 2/1/1/2 -> 0;
  `closed` True -> False (the pinned loops are open shells —
  legitimate geometry, G3 F6); `manifold` stays True;
  `vertex_count`/`element_decl`/`node_points`/`curve_entries`/
  `node_bytes`/`stage` unchanged; `failed_check` `empty-mesh` -> "".
- **D5 (warnings, summary-level)**: the 4 stores lose
  `curve-entry-loops-unexported` and gain
  `curve-entry-loops-exported-dup-pin` (+ `open-shell`); every other
  row's warnings unchanged.
- **D6 (STOP gates)**: ANY lost export or lost pass = STOP (the
  zero-regression premise violated); any changed row outside the 4 =
  stop-and-root-cause; a fired store that stays `empty-mesh` (pinned
  loops all degenerate) is a report-and-reconcile finding, not a stop.

Known harness quirk (pre-existing, named): `ab_identity_export.py`'s
`summarize` divides by the per-split part count and raises
ZeroDivisionError on `--include-sha16` runs that leave a split empty —
after the CSV is written; the full A/B run (both splits non-empty) is
unaffected.
