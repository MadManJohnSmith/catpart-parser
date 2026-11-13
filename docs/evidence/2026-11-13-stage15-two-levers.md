# Evidence: stage-15 implementation of the two owner-authorized levers — the dup-pin relaxation + the unordered-triangle dedup (2026-11-13)

Ticket #34 (G6 stage 15): the owner decision (handoff-2026-11-11.md
cont. 23, dated 2026-11-13) lands the two stage-14-measured levers on
branch `t3/dup-pin-all-unordered-tri-dedup` (worktree off main
`6fc5935`):

1. **The dup-pin relaxation** (lever 1): the stage-10 E0-b battery
   criterion is REMOVED from `composite._e0b_dup_pin` — the
   owner-authorized overturn of the stage-10 U4 conservative rule.  A
   store whose primary triangulation is EMPTY (the E0 whole-store
   scope, unchanged) exports its dropped curve-entry loops when every
   referenced skip slot is PINNABLE (each welded to the written vertex
   of its immediately preceding written element, the U4-D dup law, no
   new vertices) — normal-less and nonplanar dropped loops export
   under the same weld.  The fail-closed arm stays: a referenced skip
   slot with no preceding written element (element 0) rejects the
   whole store onto the conservative rule; the per-rep paths'
   None-candidate veto (stage-10 review F1) stays, re-scoped to
   unpinnable (the normal-less veto was the overturned behavior).
2. **The unordered-triangle dedup** (lever 2, the stage-14 review F1
   family): `composite._apply_unordered_dedup` runs on ALL FOUR
   exported composite exits (single-rep table walk, raw array, per-rep,
   mixed-write — the raw path triangulates records too, measured
   corpus incidence 0).  Fire gate (fail-closed, minimal): the
   assembled mesh must be NOT manifold AND carry duplicate UNORDERED
   index triples (the same facet re-written from a second record/loop,
   opposite winding — the review F1 mechanism) AND the deduplicated
   list must be manifold — only then do the later copies drop (first
   occurrence's winding wins).  A manifold (passing) store is never
   touched; a store whose duplicates do NOT resolve the over-use keeps
   its emitted triangles verbatim and surfaces
   `duplicate-triangles-dedup-declined` (measured corpus incidence:
   exactly 1 store, row byte-identical).  Degenerate triangles are
   never deduped (they are skipped at emission and counted separately —
   b912cbef's 3 pre-existing skips stay a separate L2 gate check).

Labels: **fact** = measured here (through the REAL seam, `build_export`
+ the committed `_score_export`, at the implementation commit
`8241006`, BEFORE the corpus run — the stage-13 Phase-B precedent);
**inference** = derived, reasoning shown; **unknown** = open.

## Pre-declaration measurement (the declaration's basis)

The 26 dup-pin rows (the committed `stage14-dup-pin-ceiling.csv`,
review-verified 26/26) plus ALL 33 not-manifold rows (the committed
`stage14-notmanifold-mechanism.csv` — lever 2's only possible fire
surface: the fire gate requires a not-manifold assembled mesh, and
passing stores are manifold by the gate's own order; the other 58
empty-mesh rows carry no dropped loops and cannot fire lever 1) ran
through the seam via `ab_identity_export.py --include-sha16` (59
stores; the subset CSV + a warnings dump in the session dir,
`~/.local/state/catpart-parser/stage15/`).  Measured: **35 changed
rows, 24 byte-identical rows** — the changed set is exactly the 26
dup-pin rows + 9 dedup carriers, and the 24 identical rows include the
24 non-carrier not-manifold stores AND the 1 declined store
(a61588e5).  The full-corpus changed-row set is therefore exactly the
35 declared below: lever 1 cannot fire elsewhere (its fire condition
is the committed census's 26), and lever 2's fire surface is the 33
not-manifold rows, all measured here.

## The DECLARED A/B delta (committed BEFORE the corpus run)

- **D1 (exports)**: 1,173 UNCHANGED — 0 gained, 0 lost.  Both levers
  run after a successful decode and cannot raise; the dup-pin merge
  adds triangles to already-exporting stores (the 26 are the
  census's exported-but-failing rows) and the dedup is a pure
  triangle-list transform gated on a returned summary's own mesh.
- **D2 (L2 gate)**: dev **1,001 -> 1,033/1,381 = 74.80% (+32 EXACTLY:
  24 dup-pin + 8 dedup, measured pre-declaration)**; held-out
  **55 -> 56 (+1: the dup-pin held-out member 1b1ae784)**; 0 lost
  passes; L1 untouched (no format/CLI changes).
- **D3 (row-level)**: EXACTLY 35 of the 1,442 census rows differ; every
  other row byte-identical:
  - the **26 dup-pin rows** (the committed ceiling CSV, all 26) — 25
    flip `empty-mesh` -> pass with `triangle_count` == the CSV's
    `pinned_tris` (32-3,456) and `loops_curve_entry` -> 0; **3dff4d93
    stays FAILED** with `failed_check` `empty-mesh` -> `not-manifold`,
    `triangle_count` 3 (the CSV's `pinned_tris`), `manifold`
    True -> False;
  - the **9 dedup carriers** — 8 flip `not-manifold` -> pass
    (1d256d12 -4, 25aeb5a0 -2, 2d59ff19 -13, 396a9d79 -2, 4a21610f -2,
    e1eed721 -2, f4a5df2a -2, ef61cfc2 -1 triangles; `manifold`
    False -> True); **b912cbef stays FAILED** with `failed_check`
    `not-manifold` -> `degenerate-triangles` (-1 triangle, `manifold`
    True).  The measured drop counts are the law's own unordered
    census — the review F1 note named one evidence PAIR per store
    (e.g. 396a9d79's 17-B pair), not the full census; the corpus
    stores carry the additional pairs the census counts here.
  - every row NOT in the two sets is byte-identical, including the 24
    non-carrier not-manifold stores and a61588e5 (the declined store).
- **D4 (warning deltas, summary-level — the A/B CSV carries no
  warnings column)**: the 26 dup-pin rows lose
  `curve-entry-loops-unexported` and gain
  `curve-entry-loops-exported-dup-pin` (detail re-dated to the relaxed
  law); 23 of them additionally gain `open-shell` +
  `unused-pool-vertices` (their pinned meshes are open shells with
  unwritten-vertex ranks), 2 (08f2eccb, e8dbf460) gain nothing extra
  (their pinned meshes close), and 3dff4d93 additionally gains
  `open-shell` + `unused-pool-vertices` +
  `degenerate-triangles-skipped` (its 1 pinned degenerate, the CSV's
  `pinned_degenerate`).  The 9 dedup carriers gain
  `duplicate-triangles-deduped` and keep every existing class (their
  own dropped curve-entry loops stay counted — separate mechanism).
  a61588e5 gains `duplicate-triangles-dedup-declined` (the fail-closed
  arm naming the gap).  NEW schema enum classes `duplicate-triangles-
  deduped` + `duplicate-triangles-dedup-declined` (additive); the
  `curve-entry-loops-exported-dup-pin` description re-dated.
- **D5 (the ceiling reproduction gate)**: the 25 passing dup-pin rows
  must equal the committed ceiling CSV's `ceiling_pass=1` rows
  row-for-row (`triangle_count` == `pinned_tris`,
  `pinned_degenerate=0` on every pass row); 3dff4d93 must stay failed
  with `triangle_count` == 3 and `failed_check` `not-manifold`;
  b912cbef must stay failed with `failed_check`
  `degenerate-triangles`; a61588e5 must stay failed `not-manifold`
  with a byte-identical row.
- **D6 (STOP gates)**: ANY lost export or lost pass = STOP (the
  zero-regression premise); any changed row outside the 35 =
  stop-and-root-cause; any `duplicate-triangles-dedup-declined` store
  whose row is NOT byte-identical = stop-and-root-cause (the declined
  arm must keep the emitted list verbatim).

## Tests (both directions, mutation-verifiable)

The stage-10 suite is RE-SCOPED, not deleted (the overturn is
owner-authorized; the pins guard the NEW scope):

- the two old battery negatives (`e0b-nonplanar`, `e0b-normal-less`)
  are now FIRE pins (`..._exports_under_relaxed_law`): the same
  fixtures export their pinned loops; restoring the battery goes red;
- NEW `e0b-relaxed-not-manifold` (the 3dff4d93 GATE analog): the law
  fires and the mesh stays NOT manifold — the decode does not veto,
  the L2 gate owns the failed check;
- NEW `e0b-multi-rep-relaxed`: BOTH reps carry normal-less dropped
  loops and BOTH export (the overturned stage-10 veto shape at the
  store level);
- the veto fixture's rep-0 loop is UNPINNABLE (skip slot = rep 0's
  element 0) — `test_composite_e0b_multi_rep_unpinnable_veto` keeps
  the None-candidate veto protection under the new law;
- `e0b-unpinnable`, `e0b-nonempty`, `e0b-multi-rep-conservative` and
  the two positives are unchanged (the unpinnable arm and the E0
  whole-store scope survive the relaxation);
- NEW dedup tests: the positive (`dedup-unordered` — box + a reversed
  re-write of one box triangle from a second record; the later copy
  drops, first winding wins), the zero-regression direction
  (`dedup-manifold-no-fire` — a two-sided sheet is manifold and keeps
  BOTH copies verbatim), the fail-closed arm (`dedup-declined` —
  duplicates + a fin on the same edge; triangles kept verbatim, gap
  named), and the b912cbef shape (`dedup-degenerate` — the dedup fires
  while the pre-existing skip rides untouched, a separate gate check).
  Mutations: removing the pre-manifold or post-manifold condition
  goes red on the corresponding negative.

Gate: ruff clean, 361 passed + 7 skipped (worktree-local venv;
349+7 at main, +6 new tests, +6 determinism params).

## Reproduction

```
cd <worktree @ 8241006> && ln -s /home/alan/Documents/Repos/catpart-parser/corpus corpus
python3 -m venv .venv && .venv/bin/pip install -e '.[test]' -e '.[lint]'
set -o pipefail && bash scripts/check.sh
# the pre-declaration subset (59 stores = 26 dup-pin + 33 not-manifold):
.venv/bin/python -I scripts/triage/ab_identity_export.py \
  --include-sha16 <the 59 sha16s> \
  --out-dir ~/.local/state/catpart-parser/stage15 --out-name stage15-subset-ab.csv
# the full A/B (the OBSERVED run — only after this commit):
.venv/bin/python -I scripts/triage/ab_identity_export.py \
  --out-dir docs/evidence/data --out-name stage15-identity-export-files.csv
```

Corpus binaries are not committed (corpus symlinked read-only);
`python3 -I` throughout; the fitness row itself stays with the
coordinator.
