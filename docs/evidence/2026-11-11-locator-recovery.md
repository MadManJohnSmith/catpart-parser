# Evidence: the locator recovery extension shipped (stage 3a, 2026-11-11)

Ticket #34 (G6, stage 3a): the L5 lever made code — the store-locate
law extended to recover the 135 missed stores (67 shipped-law seebody/
xdoc probes + 68 relaxed-law) and the 29 malformed-store-header parts
(the L4 lever riding the same change). Scope: implementation only —
the decode models are unchanged; every recovered store enters the
existing export gates. The stage-1 census
([2026-11-10-l2-grind-classification.md](2026-11-10-l2-grind-
classification.md) sections 5-6) is the stated expectation; nothing in
it needed correction — every count reproduces exactly.

## The extension (src/catpart/)

Families and probe order (`store.locate_store` + `export._export_data`):

1. **CATStdCont regions, shipped law first** (unchanged behavior):
   header variant / header-less variant as shipped. A store located
   here (passing or failing decode) means the new probes never run.
2. **Relaxed tail law, fail-closed** (`_relaxed_tail_span`): when the
   shipped tail window `[cb, origin + dword8 + dword12)` fails the N6
   trailer laws, two G1-documented variants are tried on the corrected
   windows, each valid only if the FULL N6 laws hold on the corrected
   tail (`validate_catalog_tail`):
   - **dword8-overshoot** (G1 correction C3, k = 5..28): the true tail
     is `[cb, cb + dword12)` read from the true catalog magic — the
     shipped end inherits the dword8 overshoot;
   - **padded-tail** (G1): the trailer sits inside the tail; the tail
     ends at its `CB__END` (N4w: the trailer's G names the true
     catalog length).
   A tail neither family recovers keeps the shipped
   `malformed-store-header` rejection (detail updated to say so).
3. **Container probes, xdoclink then seebody** (`CATXDocLinkCont`
   regions first — G1's next_block_store family is xdoc-carrying —
   then `CATSeeBodyCont`), only when no `CATStdCont` region located a
   store AND no stdcont header raised. Both laws (shipped + relaxed)
   apply per probed region. A probed region that matches nothing
   stays as-is; the 178 genuinely store-less parts remain
   `missing-geometry-store`.

Provenance recording (the fail-closed audit trail): every recovered
store names HOW — `StoreSpan.container` (`stdcont`/`xdoclink`/
`seebody`) and `StoreSpan.tail_law` (`shipped`/`overshoot`/`padded`) —
surfaced as `store_recovery` on the success summary (additive schema
property, absent on shipped-law stores) or as a `[store recovered via
<container> probe, <tail law> tail law]` suffix on the failing error
detail.

## Corpus A/B — the stated gate, met exactly

`scripts/triage/check_locator_recovery_ab.py` replays the fitness L2
seam (`build_export` + the runner's sanity gate) over all 1,442 L2
parts and diffs against the committed census CSV:

| census replay_class | seam outcome | parts |
|---|---|---|
| pass (76) | pass | 76 |
| undecoded-variant (1,024 = 878 composite + 55 poolless + 30 refs + 61 held-out) | undecoded-variant | 1,024 |
| missing-geometry-store (313) | pass | **36** (the census-clean recoveries) |
| missing-geometry-store | undecoded-variant | **99** (70 composite + 21 poolless + 8 refs-beyond) |
| missing-geometry-store | missing-geometry-store | 178 (genuinely store-less) |
| malformed-store-header (29) | undecoded-variant | **29** (11 overshoot-composite + 18 padded-poolless) |

Totals: pass 112 / undecoded-variant 1,152 / missing-geometry-store
178 / malformed-store-header 0 — the stated gate, no other delta.
Recovery provenance recorded on all 164 moved parts, per family:
seebody/shipped 33, xdoclink/shipped 34 (the 67 shipped-law),
seebody/overshoot 51 + xdoclink/overshoot 1 + seebody/padded 16 (the
68 relaxed-law), stdcont/overshoot 11 + stdcont/padded 18 (the 29).

**The 36 clean recoveries all export PASS** (the near-term L2 value):
24 parts at 40 vertices / 48 triangles, 12 at 72 / 96, zero sanity
failures (no empty-mesh, no not-manifold, no nonfinite-bbox, no
degenerate skips) — they flow through the existing clean decode path
with their recovery named in `store_recovery`.

**L1 stability:** `build_inspect_report` over the 164 moved parts is
field-identical (detected_version, kind, container_names) to both the
committed baseline report and a baseline-interpreter run (pre-stage-3a
code at 14486db) — the locate law does not touch container inventory.
(The comparison mirrors the runner's container_names derivation:
unique, first-occurrence order — 2026-11-11 correction (#34 stage-3a
review): the gate script's baseline probe now applies the same dedup;
before the fix the stronger `--inspect-baseline-python` mode exited 1
on 12 corpus parts whose container tables genuinely repeat names —
raw interpreter output verified identical on all 12.)

## Projected L2 arithmetic (not run — the coordinator runs the combined row)

- This branch alone: dev L2 76 -> **112** / 1,381 (5.50% -> 8.11%);
  held-out unchanged (61 undecoded-variant).
- Combined with stage 2c (composite integration, Dev 76 -> 109 on its
  branch): **109 + up to 36** = up to 145 / 1,381 (10.50%) from the
  clean recoveries alone, before stage 2c's composite decode lifts any
  of the 70 + 11 composite bodies this stage moved into the attempted
  pool and the 8 refs-beyond (L3) / 21 + 18 poolless (L2-lever) bodies
  it moved onto the content levers' pools.

## Files

- `src/catpart/geometry/store.py`: `_relaxed_tail_span`, `container`
  parameter, `StoreSpan.container`/`.tail_law`, probe-family constants.
- `src/catpart/geometry/export.py`: `_export_data` probe loop (xdoc
  then seebody), `_recovered_error` detail provenance, `store_recovery`
  summary field.
- `src/catpart/geometry/errors.py`: error-class doc updates.
- `src/catpart/schema/export-summary-v1.json`: additive
  `store_recovery` property + `store_ordinal` description (additive
  evolution keeps schema v1).
- `tests/fixtures_gen.py`: seven recovery variants (seebody store,
  xdoclink store, overshoot tail, padded tail, recovered-composite,
  seebody-empty, unrecoverable-tail).
- `tests/test_locator_recovery.py`: 11 tests — locate-level
  provenance, seam classification, fail-closed negatives, shipped-law
  byte-stability, L1 clean-parse cross-check.
- `scripts/triage/check_locator_recovery_ab.py`: the A/B gate.

## Reproduction

```
# corpus A/B gate (needs the corpus on disk; read-only)
.venv/bin/python -I scripts/triage/check_locator_recovery_ab.py \
  --corpus-root <repo-root-with-corpus>
# optional stronger L1 check against the pre-stage-3a code:
#   --inspect-baseline-python <baseline-checkout>/.venv/bin/python
```
