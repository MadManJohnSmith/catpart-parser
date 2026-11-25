# Evidence: T3 relaxed families — per-record landing audit (2026-11-25)

**Status**: COMPLETE for the per-record landing audit (ticket #61, parent
#50). The admission is unchanged; this note adds the ref-resolution
table and the shipped net delta the ticket asked for.

## 1. What was open

The T3 admission (2026-11-20, `44f2b1e`; evidence
[2026-11-20-t3-relaxed-facet-families.md](2026-11-20-t3-relaxed-facet-families.md))
shipped `0x44`/`0x41` under the strict mesh guard. The remaining item was
the lex-rank resolution audit: every relaxed record's refs must land in
the rep's decoded element space, and its loops must triangulate, before
the family's admission is evidence-complete.

The pre-T3 report `20261120T183229Z-d503ff` carries
`unresolved-facet-family` on **115 files**: `0x44` 716 records / 98
files, `0x41` 68 records / 26 files.

## 2. Population and method

Three populations are in play; they are not interchangeable:

| population | `0x44` | `0x41` | files |
| --- | ---: | ---: | --- |
| report warning (2026-11-20) | 716 | 68 | 98 / 26 |
| T3 structural micro-probe (strict header filter) | 217 | 9 | — |
| export seam (this audit) | **720** | **1,989** | **98 / 55** (115 union) |

The export-seam population is larger than the warning because the audit
counts every record the shipped relaxed pass processes on the same 115
carriers, including the additional `0x41` records that later routing laws
(`#76` LE primitive, W7-B, W17) expose; the warning counted the old
`skipped_markers` subset. The `0x44` count is stable (720 vs 716). The
`0x41` family is broader than the warning roster: 29 of its 55 files
carried only a `0x44` warning in the old report.

Method:

* [`scripts/triage/probe_relaxed_landing.py`](../../scripts/triage/probe_relaxed_landing.py)
  wraps `composite.parse_strip_records` during the shipped
  `_export_data`, captures the final record tuple and the rep's decoded
  `elements` (the same objects `_triangulate` receives), and replays the
  same `_loop_triangles` per loop. **Landed** = refs inside the element
  space and the loop triangulates; it is the structural gate before the
  mesh guard.
* [`scripts/triage/measure_relaxed_delta.py`](../../scripts/triage/measure_relaxed_delta.py)
  exports each carrier twice — shipped vs the same build with
  `RELAXED_SHORT_MARKERS = ()` — and reports the emitted
  triangle/area/manifold delta.
* Read-only over the corpus. CSVs:
  [landing](data/relaxed-facets-landing.csv) (2,709 rows),
  [files](data/relaxed-facets-landing-files.csv) (115 rows),
  [claims](data/relaxed-facets-landing-claims.csv),
  [delta](data/relaxed-facets-delta.csv).

## 3. Landing

| | records | refs | in bounds | written | skip | loops | triangulated | landed records | triangles | degenerate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all | 2,709 | 52,691 | 52,691 (100%) | 44,076 (83.65%) | 8,615 | 15,059 | 10,784 (71.61%) | 1,977 (72.98%) | 12,553 | 0 |
| `0x44` | 720 | 11,312 | 11,312 (100%) | 7,600 (67.19%) | 3,712 | 1,266 | 370 (29.23%) | 248 (34.44%) | 2,139 | 0 |
| `0x41` | 1,989 | 41,379 | 41,379 (100%) | 36,476 (88.15%) | 4,903 | 13,793 | 10,414 (75.50%) | 1,729 (86.93%) | 10,414 | 0 |

Every relaxed ref is inside the rep's element space: the lex-rank law
holds, with **0 out-of-bounds refs in 52,691**. The 16.35% skip slots are
decoded `None` coordinates (the curve entries), not junk; the skip-bearing
loops enter the dup-pin weld under its own strict guard. The `0x44`
family is skip-heavy (32.8% of refs, only 29.2% of loops triangulate
directly); `0x41` contributes 10,414 of the 10,784 triangulated loops
(96.6%) and triangulates 75.5% of its own loops.

The landed loops are not the emitted delta: the mesh guard and the
stage-15 identity dedup run after this table. The per-file
`relaxed_loops_accepted` sum (10,767) is 0.16% below the 10,784
structurally triangulated loops; the 17-loop difference is 16 records
captured from a multi-stage trial plus one guard-declined loop
(`relaxed_loops_declined = 1`).

## 4. Net emitted delta

The audit re-measures the shipped effect instead of reusing the
2026-11-20 row: later laws changed the base mesh, so the historical
+701 triangles / +191,338 mm² is not the current number. Over the 115
carriers:

| metric | value |
| --- | ---: |
| files gaining triangles | 115 / 115 |
| extra triangles (net) | **+22,578** |
| extra area (net) | **+176,185.3 mm²** |
| manifold regressions | **0** |
| degenerate delta on passing parts | **0** |

Top gains by area (the triangle leader is `PowerBoard_CI/Board.CATPart`,
+4,416 triangles / +144.5 mm²):

| file | delta triangles | delta area |
| --- | ---: | ---: |
| `CAAEwrListWiresInBundleSegment/Support-plate` | +20 | +51,693.9 mm² |
| `PartWithPlaneAndSketchForSectionView` | +92 | +40,928.9 mm² |
| `SP02_BETA_COIFFE` | +144 | +36,703.0 mm² |
| `CAATestModifyJoggle` | +5 | +12,360.3 mm² |
| `head_hueca_x1.5` | +18 | +11,296.7 mm² |
| `Disc-2DL` | +504 | +10,026.8 mm² |

The 12,553 direct-loop triangles in §3 are not the emitted delta: the
dup-pin weld resolves skip-bearing loops (Support-plate: 0 direct
triangles, +20 welded triangles / +51,694 mm²), and the stage-15
identity dedup plus the guard remove duplicates/refusals. The shipped
delta is the authoritative number.

## 5. Reading and closure

* **Acceptance 1 (pinned layout)** is already met by the T3 structural
  micro-probe: 226/226 strict-filter records parse under the same
  `(width, k)` tiling law, with no 12-B normal carrier.
* **Acceptance 2 (warnings drop, 0 regressions, parity)** is met by the
  T3 commit and re-confirmed here: the relaxed families leave
  `skipped_markers`, so the warning names only the still-open families;
  0 manifold regressions and 0 degenerate triangles; the port parity
  flips are byte-identical.
* **The fidelity metric is unchanged.** L2 counts pass/fail files, so a
  richer mesh on an already-passing part is invisible to the rate. The
  T3 fitness row `20261120T192800Z-c3cb79` remains rejected by the
  no-regret letter; that is a metric-definition decision, not a decode
  gap.
* **A guard-policy finding, not a landing gap.** The landed area is
  extremely concentrated: 1,398 of 1,977 landed records are below 0.01
  mm² and the top 8 carry ~94% of the landed area. On
  `SP02_PCB_Allumage_Pre-RCE` (821 `0x41` records), the shipped delta is
  +2,084 triangles for +0.108 mm² — mesh density, not surface. The
  strict guard has no minimum-area floor and the stage-15 dedup removes
  exact duplicates only. A sliver floor, if wanted, is a separate guard
  ticket. The net delta is also concentrated, and it includes real large
  faces: `Support-plate` +51,694 mm², `PartWithPlane` +40,929 mm² and
  `SP02_BETA_COIFFE` +36,703 mm² account for +129,326 mm², so the
  admission is not only density.
* **Reopening criteria**: any relaxed ref outside its rep's element
  space; any landed degenerate triangle; any manifold regression; or a
  negative net delta on a passing part.

## 6. Reproduction

```bash
.venv/bin/python -B scripts/triage/probe_relaxed_landing.py
.venv/bin/python -B scripts/triage/measure_relaxed_delta.py
.venv/bin/python scripts/triage/check_claims_csv_quoting.py
```
