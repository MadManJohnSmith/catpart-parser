# Evidence: T1 grid relaxation + T2 display fallback & honest kind law — 2026-11-20

**Status**: COMPLETE. Shipped over the two states measured at the merge head of
`2026-11-19-fidelity-close.md` (open rate 96.12%, L2 dev 79.51%). Tickets #59
(T1) and #60 (T2), both `Part of #50`.

**Method**: implementation on `main` (`src/catpart/geometry/grid.py`,
`display.py`, `export.py`, `cli.py`, `containers.py`, schemas, and the Rust
twins), verified with the shipped merge gate (`scripts/check.sh`: ruff clean,
pytest 875 passed / 7 skipped, cargo test 181, wasm-pack 11, node suites,
assembly acceptance 24/24) and the fidelity harness functions
(`scripts/fidelity_run.py`) for Python=Rust byte-identity. Read-only over the
corpus; probes in the session state dir (`~/.local/state/catpart-parser/probes-2026-11-20/`).

## T1 — the refused grids relax (#59)

`grid._relaxed_triangles` (and the Rust twin) applies the measured relaxation
to the stalled / degenerate refusals only: near-duplicate station rows
collapse to their first row (the stall gate's own eps bar) and zero-area
cells drop (the committed area floor), never instead of a decoded carrier and
never under the prefix-dialect gates (non-monotone / non-uniform stay
refused — that fit has no committed dimension). A relaxed grid merges into a
part that already owns a mesh only under the strict merged-manifold guard
(`mesh_stats(merged).manifold`).

**Corpus-wide effect (measured, all 46 refused grids reproduce):**

| Gate | Refused | Relax → manifold |
| --- | --- | --- |
| stalled-stations | 36 | 36 |
| degenerate-cells | 7 | 7 |
| non-uniform-stations | 2 | 0 (out of scope, still refused) |
| non-monotone-stations | 1 | 0 (out of scope, still refused) |

The 5 named `untriangulable-grid` parts flip DISPLAY → MESH
(153a33fb CorrugateTube10-2, 5abff0b1 BranchableBundleSegment1, 827c5b7a
Tape5-2, cb6454b5 BranchableBundleSegment2, d665cd12 BACK_SHELL). Because the
law runs corpus-wide, 10 further L2-failing parts recover their owner grids
(BundleSegment2/3/4/5/6, Bundle_Segment2, Multi-branchable1, Tape001 ×2,
Corrugate002): **L2 dev 1,098 → 1,113 = 80.59% (+1.09 pts)**, held-out flat
57/61, L1/L3 unchanged; accepted under no-regret
(`20261120T183229Z-d503ff`, dev rose, held-out did not fall). MESH 1,163 →
1,178. Degenerate triangles stay 0 (the floor gate). The 8 already-passing
parts with relaxed secondary grids keep passing (all 15 status flips are
fail → pass; zero regressions).

**Parity**: Python vs Rust `fidelity-cli` export over the 13 affected parts —
13/13 summary-equal and PLY byte-identical.

## T2 — display fallback & honest kind law (#60)

1. **Located-span regions**: `display._regions` adds the container-probing
   law's store bodies (the census/brep-probe law), so curve records living
   in CATStdCont/CATSeeBodyCont are visible to the display walk.
2. **Empty-scan f32-run fallback**: when every primary carrier comes up
   empty, the scan walks the valid blocks' payload regions under the
   missing-store census law (12-byte-stride f32 triples, finite, 1e-2..1e5
   envelope, ≥ 3 triples) — the measured law of
   `missing_store_census_probe.point_runs`. Source label `store-f32-points`.
   It never runs when any primary carrier decoded (the bagrep gates test
   pins that side).
3. **`not-a-catpart` kind law**: bytes without the `V5_CFV2\0` magic
   classify `not-a-catpart` at the inspect seam (the 6 `magic_ok=no`
   manifest misfits; the K1 container law stays magic-independent). Schema
   enums updated (`v1.json`, `fitness-report-v0.json`).

**Measured effect** (`probe_open_rate.py`, report `20261120T183229Z-d503ff`):

| Population | Before | After |
| --- | --- | --- |
| Open (MESH + DISPLAY) | 1,386/1,442 = 96.12% | **1,412/1,442 = 97.92%** |
| Open over the honest CATIA denominator (1,442 − 4 `not-a-catpart` parts) | 1,386/1,438 = 96.38% | **1,412/1,438 = 98.19%** |
| MESH | 1,163 | 1,178 |
| DISPLAY | 223 | 234 |
| BLANK | 56 | 30 (dev only; held-out stays 0 BLANK) |

The 2 container-less `V5_CFV2` binaries open as DISPLAY
(CAAMaiUdfForMfgHoleInstance 254 points / Template 111 points under
`store-f32-points`), plus 24 further BLANK rows the same fallback rescues
(Crankshaft 4,114 points, Ehi_* bundles, NewScrew, … —
`no-surface-fallback-parts.csv` regenerated). The 4 non-CATIA files
(`dummy`, `MyTextDocCheck`, `fpb_assy_v3`, `CATIA_vol/test_tolerence`) are
`kind=not-a-catpart`, out of the CATIA denominator; the sibling
`CATIA/test_tolerence.CATPart` is untouched (still part, still opens).

## Documented negatives measured on the way

- **33 37 circles carry no orientation**: 2,586/2,588 record payloads in the
  279 no-mesh population are exactly 18 B (4 BE f32 + 2-B trailer); the
  unit-triple hypothesis at +18/+20/+22 yields 0 hits. A sampled circle
  would be a guessed plane — the display law (never a guessed circle)
  stands; circles keep contributing their decoded center. The curve lever
  in #60 is redesigned: real segments come from the 33 32 line law (already
  emitted) and from 01 01 polyline refs once the pool-pairing law lands.
- **CATCGRCont holds no CGR primitive vocabulary**: 0 hits on 10 GP tokens;
  23 files carry zlib-like magics but 0 streams decompress; bag tokens live
  outside the CATCGRCont blocks; median block ~0.9 KB. Deprioritized
  (decision 2026-11-20, ticket #50 thread).
- **Composite `used_vertex_fraction` ≈ 0 is structural**: the warning
  compares the WHOLE decoded element space (faces + edges + curves, up to
  330k slots) against the exported triangles (14–2,353), which reference
  only the law-pinned facet subset; the rest is declined by the manifold
  guard (`extended-header-geometry-declined` 448–2,857 per part) or held in
  the open U4 curve records (`curve-entry-loops-unexported` up to 11,136).

## Acceptance

1. #59: the 5 flips + no-regret acceptance + byte-identical parity + green
   gate — **met**.
2. #60: the +2 container-less opens and the honest denominator — **met**;
   the 77-circle segment lever — **measured negative** (no orientation
   field), redesign noted in the ticket.
