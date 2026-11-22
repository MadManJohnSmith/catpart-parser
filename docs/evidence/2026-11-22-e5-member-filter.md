# Evidence: the surface route's member-filter law — filtered degenerate
# tessellation members, named on `surface-members-filtered` (2026-11-22)

**Date**: 2026-11-22 (W15, marathon wave 4)
**Status**: COMPLETE — shipped on `marathon/w15-e5-tail`.
**Target**: the L2 regression the Orchestrator bisected to W3's merge
(`528a0a0`): two corpus parts moved PASS → **FAIL `degenerate-triangles`**
exactly when the E5 route (`0x00e7`) started tessellating:

| part | before (merge) | after (merge) |
| :--- | :--- | :--- |
| `First_Back_Shell.CATPart` (B31CAADoc) | grid route, 2,220 tris, degenerate 0 — pass | E5 route, 8,278 tris, degenerate **26** — fail |
| `backshell_M.CATPart` (CAA_EHIMultiSegmentSample) | grid route, 3,320 tris, degenerate 0 — pass | E5 route, 9,142 tris, degenerate **34** — fail |

**Root cause**: not an emission bug.  The E5 tessellation already skips
zero-area cells (`tessellate`'s area floor), so the exported mesh carries
no degenerate triangle — but the skip count flowed into
`SurfaceScan.degenerate` → the export summary's
`degenerate_triangle_count`, and the L2 gate
(`MAX_DEGENERATE_TRIANGLES = 0`) fails on any nonzero value.  The
mechanism is geometric, not byte corruption: the corpus's exact B-spline
records carry near-collapsed pole regions (knife edges, apex rows) whose
evaluated cells fall under the 1e-12 relative area floor.  Both parts
score `manifold: true` — the degenerate count was the only failing check.

**Law** (the established member-filter precedent, commit `e4cb87a`):
*"The skips never count as degenerate: the L2 gate's
MAX_DEGENERATE_TRIANGLES = 0 rate stays 0."*  Applied to the surface
route:

- the tessellation's degenerate member triangles are **filtered** and
  named: `SurfaceScan.degenerate_filtered` (new counter) + the
  `surface-members-filtered` warning class (new in
  `export-summary-v1.json`, with the count in the detail);
- `degenerate_triangle_count` stays the exported mesh's own count — 0 by
  construction (nothing degenerate is ever appended);
- the L2 gate is untouched (`MAX_DEGENERATE_TRIANGLES = 0`).

**Fallback**: the no-regret fold is the deterministic fallback and needs
no new arm.  A patch whose filtered remainder is empty or not a manifold
sheet returns `None` from `tessellate` → the record is `refused`; with
nothing tessellated the E5 census rides on the additive fields alone and
the totals, the mesh and the route decision are exactly the pre-E5 ones
(the grid / face-gp / display seam follows).  A part whose E5 mesh
tessellates and passes the gate keeps the exact surfaces (the fidelity
improvement is the point).

## Verification (measured, not asserted)

- **The two parts**: both export `degenerate_triangle_count == 0`,
  `manifold: true`, L2 `pass` via the runner's own `_score_export`
  (triangles 8,278 / 9,142 preserved).  Python and Rust summaries equal;
  PLY byte-identical (`cmp`) on both files.
- **Corpus L2 fast pass** (`scripts/triage/l2_fast_pass.py`, both hands:
  baseline = main `d8554e0`'s src in one subprocess, branch = this
  worktree): transition census in
  `docs/evidence/data/e5-member-filter-l2.csv` —
  **pass→pass 1,195 · fail→pass 15 · pass→fail 0** (fail→fail 232).
  Main does not carry the E5 route (the W3 merge `528a0a0` lives on the
  wave-4 integration branches), so the 15 fail→pass rows are exactly the
  class-table A/B's expected +15 dev (all `dev`, all `empty-mesh` →
  mesh through the E5 surfaces), the two bisected parts stay `pass`
  (their pre-E5 grid route passed; the fixed E5 route passes), and no
  part that passes on main fails on the branch.
- **Parity**: Python vs Rust `fidelity-cli export` over the 16 no-facet
  E5-bearing parts + the two bisected parts: PLY byte-identical, summary
  fields equal including the new warning.
- **Synthetic tests**: `tests/test_e5_surface.py` builds a slab whose
  inner v pole rows coincide (the collapsed-row mechanism) — the battery
  passes, the tessellation filters 8 members, `scan.degenerate == 0`,
  `scan.degenerate_filtered == 16`, the export names them on
  `surface-members-filtered` and passes `_score_export`; the schema
  validator accepts the new class.  The Rust twin pins the same fixture
  (`e5_degenerate_members_are_filtered_not_counted`).

## Detector honesty

- The law is route-wide (a5 `03 34` frames and E5 `0x00e7` records share
  `scan_part`'s fold), not E5-specific: the summary semantics change for
  any surface-route part that skips members.  The corpus A/B bounds the
  blast radius: the changed set is exactly the parts whose E5/a5
  tessellation filtered members (the two bisected parts and the flip
  set); no other row changed.
- The soup/composite routes keep their own `degenerate-triangles-skipped`
  semantics (their skipped strips still feed `degenerate_triangle_count`
  and can fail the gate) — this note changes only the tessellation
  route, where skipping is a geometric property of an exact surface, not
  byte corruption.
- What the detector does not discriminate: whether a filtered member
  came from a knife edge or an apex row (both are "collapsed pole
  geometry"); the warning carries the count only.

## Reproduce

```bash
cd ~/marathon-wt/w15
.venv/bin/python -B -m pytest tests/test_e5_surface.py -q
(cd port && CARGO_BUILD_JOBS=1 RUSTFLAGS="-C debuginfo=0" cargo test --lib geometry::surface)
.venv/bin/python -B -I scripts/triage/l2_fast_pass.py \
    --baseline-src /home/alan/catpart-parser/src
```
