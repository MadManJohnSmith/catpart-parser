# Composite exporter: per-loop dup-pin weld (surface-loss fix, #34)

Date: 2026-11-18
Base: `df02aed` (main)
Branch: `fix/composite-per-loop-weld`
Status: **implemented and tested; NOT ready to merge — the full-corpus A/B
found 26 non-manifold regressions (section 5). The implementation stopped
there per the task's fail-safe rule; the battery was not tuned.**

Claims: `docs/evidence/data/br6-composite-weld-claims.csv`

## 1. The bug

`src/catpart/geometry/composite.py` dropped every loop that referenced a
skip slot (curve entry, U4) and only evaluated the dup-pin weld when the
store's primary triangulation was EMPTY:

```python
if not triangles and dropped:          # composite.py:706 (before)
    stats["dup_pin"] = _e0b_dup_pin(...)
```

On `corpus/Apoloo13/ASE_III/diseño_3d/labios/main.CATPart` the primary mesh
has 4,261 triangles, so the weld never ran and 13 droppable loops stayed
out. Ten of them are battery-supported (record normal absent, or coplanar
under the dup pin at 2e-3, measured deviations <= 1.4e-6): the three
envelope panels at x = -22.7 (599.04 mm²) and y = ±12.4 (2 × 1,163.52 mm²)
plus six smaller loops. The other three loops are width misparses (see
section 3).

## 2. Fix 1 — the dup-pin weld is a per-loop decision

`_e0b_dup_pin` now evaluates each dropped loop independently and welds it
exactly when:

1. it is **fully pinnable** — every referenced skip slot has a preceding
   written element (`_dup_pin_map`, the U4-D dup law); and
2. it is **battery-supported** — the record carries no normal, or the
   dup-pinned coordinates are coplanar against that normal at
   `PLANE_TOL = 2e-3` (`_loop_plane_status`).

A refused/unpinnable loop stays dropped and counted; it no longer vetoes
another loop's weld. The `not triangles` precondition is deleted on the
single-rep path (`_triangulate` / `decode_composite_store`) and the
store-level empty-mesh gate is removed from both per-rep paths
(`_decode_per_rep`, `_decode_mixedwrite`), so every exported path makes the
same per-loop decision. The battery is unchanged (fix 3).

Measured on labios/main, fix 1 alone:

| | triangles | area (mm²) | manifold | welded loops | dropped |
|---|---:|---:|---|---:|---:|
| before | 4,261 | 2,299.09 | true | 0 | 13 |
| fix 1 | 4,457 | 5,396.79 | true | 10 | 3 |

The 10 welded loops' record offsets: 317972, 318005, 325684 (2 loops),
326037 (2 loops), 331744, 331779, 335648 (2 loops). Deviations under the
battery: 0.0, 4.6e-15, 9.5e-7, 7.5e-7, 1.4e-6, 1.4e-6, 5.3e-15, normal-less,
9.5e-7, 8.8e-7.

## 3. Fix 2 — the gap-edge width rank runs the same battery

`parse_strip_records` ranks width candidates by exact tiling, repeats,
out-of-range refs, then non-coplanar normal-carrying loops, then narrower
width. In the gap-edge case (no candidate tiles exactly) a width-1 misread
can land its loops on skip slots; those loops were previously excluded from
the plane battery, so the misread won the ranking and its loops were then
dropped.

From now the plane tiebreak also tests a skip-bearing loop on its
**dup-pinned coordinates**. A wrong width is nonplanar there; a legitimate
curve loop is coplanar there (<= 1.4e-6), so legitimate loop parses are not
penalized and no blanket "no skip refs" rule is needed.

On labios/main the three misparsed records now resolve to width 2, fully
written:

| offset | width before | width after | deviation of the width-1 loop under the pin |
|---|---:|---:|---:|
| 318240 | 1 | 2 | 1.19 |
| 321711 | 1 | 2 | 7.60 |
| 332837 | 1 | 2 | 5.2e-2 |

Fix 1 + fix 2 on labios/main:

| | triangles | area (mm²) | manifold |
|---|---:|---:|---|
| before | 4,261 | 2,299.09 | true |
| fix 1 | 4,457 | 5,396.79 | true |
| fix 1 + 2 | 4,464 | 5,410.18 | true |

5,410.18 mm² is 96.6% of the ~5,600 mm² envelope. The fix-2 delta is
13.39 mm² / +7 triangles, matching the independent root-cause estimate.

## 4. Corpus A/B method

Both sides use the same interpreter (`.venv`) and the same manifest order:

- base: a detached worktree at `df02aed`, `PYTHONPATH=/tmp/opencode/base/src`;
- patched: this worktree's `src`;
- each part exported with `catpart.cli.main_export`, the PLY parsed back
  with stdlib `struct`, triangle count and summed triangle area recorded,
  and the summary's `mesh.manifold` flag compared.

### 4.1 The requested ~50-part sample

Candidates: every 10th manifest part (stride 10 of 1,442 parts); the first
50 that export under the base are the sample. 34 of 50 change; all changes
are increases; **zero manifold→non-manifold regressions**.

| part | tris before | tris after | Δtris | area before (mm²) | area after (mm²) | Δarea (mm²) | manifold | welded loops |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| LedStrips_GND_final.CATPart | 4234 | 9943 | +5709 | 5785.98 | 19986.22 | +14200.25 | true→true | 511 |
| SP02_BETA5_SEPA2_PRINCIPALE.CATPart | 4664 | 8916 | +4252 | 8272.89 | 12460.95 | +4188.06 | true→true | 167 |
| SP02_BETA5_SEPA2_PALQUE-RETENUE.CATPart | 1171 | 4274 | +3103 | 906.99 | 2463.06 | +1556.06 | true→true | 98 |
| DB25_Female.CATPart | 299 | 2603 | +2304 | 95.19 | 3189.23 | +3094.04 | true→true | 743 |
| servo.CATPart | 2261 | 4464 | +2203 | 1740.21 | 5410.18 | +3669.97 | true→true | 49 |
| Bague_Para_2_etage-2.CATPart | 1921 | 4005 | +2084 | 1726.16 | 2405.96 | +679.80 | true→true | 25 |
| SP02_BETA_Moule_Cage_Parachute.CATPart | 957 | 2589 | +1632 | 65276.32 | 66419.02 | +1142.71 | true→true | 16 |
| Moule coiffe test SP.CATPart | 1094 | 2212 | +1118 | 13603.07 | 16715.13 | +3112.06 | true→true | 6 |
| Crochet_F_bas.CATPart | 2059 | 3064 | +1005 | 1787.73 | 2158.33 | +370.59 | true→true | 14 |
| M4x10_Poelier.CATPart | 449 | 1385 | +936 | 360.32 | 1053.88 | +693.55 | false→false | 213 |
| Bague exeterieur.CATPart | 147 | 904 | +757 | 8.60 | 123.98 | +115.37 | true→true | 8 |
| SP02_Alpha_BAS.CATPart | 252 | 870 | +618 | 2246.16 | 4031.53 | +1785.36 | true→true | 39 |
| 6005_2_03.CATPart | 216 | 760 | +544 | 162.89 | 4129.09 | +3966.20 | true→true | 62 |
| L0806~L0806_L2.0-W1.6-H1.0~U5Q5.CATPart | 525 | 1062 | +537 | 0.15 | 5.32 | +5.17 | true→true | 103 |
| SpatialLoft-4076E.CATPart | 73 | 429 | +356 | 215927.98 | 991719.38 | +775791.41 | true→true | 5 |
| HDR-M-2.54_1X4~HDR-M-2.54_1x4~iaXJ.CATPart | 984 | 1340 | +356 | 243.12 | 243.24 | +0.11 | true→true | 48 |
| SP02_ALPAH5_SEPA2_BLOQUE_RESSORT.CATPart | 314 | 628 | +314 | 157.07 | 314.14 | +157.07 | true→true | 2 |
| lengua_base.CATPart | 1368 | 1636 | +268 | 8935.75 | 8961.90 | +26.15 | true→true | 26 |
| Spur Gear23.CATPart | 163 | 422 | +259 | 9159.43 | 22058.22 | +12898.79 | true→true | 88 |
| main.CATPart | 331 | 570 | +239 | 1653.89 | 5298.52 | +3644.64 | true→true | 37 |
| backshell_F.CATPart | 78 | 302 | +224 | 1133.17 | 5818.21 | +4685.04 | true→true | 79 |
| Hole.CATPart | 130 | 286 | +156 | 53634.70 | 60997.50 | +7362.80 | true→true | 19 |
| SD Card.CATPart | 584 | 734 | +150 | 980.38 | 1123.30 | +142.92 | true→true | 43 |
| Guia.CATPart | 47 | 178 | +131 | 8038.83 | 16518.74 | +8479.91 | true→true | 10 |
| SP02_ALPHA5_SEPA2_RETENUE_ROULEMENT.CATPart | 388 | 512 | +124 | 921.79 | 1121.69 | +199.90 | true→true | 12 |
| Tornillo tapa servo M2x25.CATPart | 124 | 232 | +108 | 148.22 | 152.20 | +3.98 | true→true | 4 |
| ALPHA_SEPA_RONDELLE.CATPart | 294 | 394 | +100 | 256.41 | 364.73 | +108.32 | true→true | 2 |
| SP02_ALPHA5_SEPA2_RETENUE_ROULEMENT2.CATPart | 276 | 370 | +94 | 482.62 | 595.43 | +112.81 | true→true | 4 |
| pin2.CATPart | 8 | 48 | +40 | 2.78 | 195.52 | +192.74 | true→true | 7 |
| SP02_ALPHA_BAGUE_2.CATPart | 73 | 108 | +35 | 2394.91 | 2425.60 | +30.68 | true→true | 4 |
| uu.3.CATPart | 84 | 116 | +32 | 474.30 | 859.47 | +385.17 | true→true | 6 |
| SP02_BETA_TUBE (1).CATPart | 214 | 244 | +30 | 381251.19 | 488286.26 | +107035.07 | true→true | 4 |
| CAAPmiUdfForMfgHoleInstance.CATPart | 58 | 86 | +28 | 59903.66 | 61399.00 | +1495.34 | true→true | 2 |
| R0805~R0805_L2.0-W1.3-H0.6~iaXJ_1.CATPart | 120 | 131 | +11 | 17.61 | 17.61 | +0.00 | true→true | 1 |

Totals over the 50: 28,702 → 58,559 triangles. `servo.CATPart` reproduces
labios/main's exact 4,464 / 5,410.18 row (same store content).

## 5. Full-corpus A/B — the blocking finding

All 1,442 manifest parts were tried under the base; 1,173 exported. The
same 1,173 were re-exported with the patch (all still export):

- changed: 703 / 1,173 (654 of them stay manifold);
- triangle-decreasing rows: 0; area-decreasing rows: 0;
- welded loops: 93,426;
- triangles: 710,099 → 1,452,461;
- **manifold → non-manifold: 26 parts (2.2% of exported).**

The 26 regressions (all caused by fix 1 — sampled at fix-1-only, identical
triangle counts; fix 2 does not cause them):

| part | tris before | tris after | welded loops | area before (mm²) | area after (mm²) |
|---|---:|---:|---:|---:|---:|
| `Square.CATPart` | 96 | 408 | 57 | 24.1 | 303.3 |
| `TerminalBlock10_CI.CATPart` | 744 | 1778 | 459 | 614.6 | 1276.8 |
| `SP02_ALPHA5_SEPA2_PRINCIPALE.CATPart` | 1852 | 27045 | 2712 | 3969.6 | 16004.5 |
| `Symmetry of Part1.1.2.3.4.5.6.7.8.9.10.CATPart` | 106 | 663 | 110 | 13755.7 | 45271.2 |
| `Coletor de Escape.CATPart` | 115 | 663 | 115 | 13840.6 | 46674.2 |
| `5009980900_SD_reader.CATPart` | 2932 | 3196 | 66 | 1175.3 | 1226.6 |
| `Base.CATPart` | 643 | 2901 | 468 | 4663.6 | 98310.1 |
| `Coletor de Admissao.CATPart` | 403 | 3236 | 209 | 108325.1 | 285278.1 |
| `Hitbox_WorkFile_main.CATPart` | 2398 | 9752 | 447 | 145783.3 | 1547253.2 |
| `Carter de Oleo - Motor V6.CATPart` | 803 | 1176 | 68 | 18976.3 | 41825.0 |
| `MPU6050_Solders.CATPart` | 161 | 369 | 79 | 1299.9 | 2670.7 |
| `DB9_Female.CATPart` | 175 | 1323 | 359 | 58.5 | 1718.1 |
| `SP02_BETA_COUPLEUR.CATPart` | 433 | 1083 | 6 | 140.0 | 223.1 |
| `TouchRows_Strips.CATPart` | 2026 | 9214 | 1125 | 3205.0 | 796126.2 |
| `TouchCols_Wires.CATPart` | 1471 | 2560 | 226 | 674.5 | 3331.1 |
| `Bateria.CATPart` | 312 | 348 | 2 | 19956.4 | 20019.2 |
| `SP02_ALPHA5_SEPA2_LOQUET_RESSORT.CATPart` | 88 | 138 | 14 | 521.7 | 980.8 |
| `Moule1.CATPart` | 143 | 1184 | 12 | 61572.7 | 100686.0 |
| `SP02_BETA_Cage_Parachute.CATPart` | 432 | 1266 | 21 | 9419.8 | 47523.8 |
| `TSSOP-8_L3.0-W3.0-P0.65-LS4.9-BL~...7Q6T.CATPart` | 863 | 1439 | 89 | 9.0 | 22.4 |
| `_NPart#194321.CATPart` | 10030 | 31504 | 1731 | 268.4 | 6053.3 |
| `coneecting road.CATPart` | 143 | 407 | 51 | 8940.8 | 20712.9 |
| `MPU6050_Wires.CATPart` | 105 | 655 | 77 | 366.2 | 5684.6 |
| `Beta_Bague_Para_Sup_Pleine.CATPart` | 821 | 3937 | 25 | 813.1 | 2738.0 |
| `SP02_PCB_Allumage_Pre-RCE.CATPart` | 4067 | 6237 | 532 | 1045.1 | 2286.8 |
| `M3_Nut.CATPart` | 182 | 439 | 32 | 27.5 | 57.1 |

(The corpus's coordinate units are inconsistent across producers; the
absolute mm² column is not comparable between parts. The deltas are.)

### 5.1 What the regressions are

The welded loops on these parts are real geometry, not duplicated facets:
the area increases, and the pre-existing unordered-triangle dedup law does
not fire (there are no duplicate unordered triples to remove). The added
fans share a small number of edges with the surviving primary mesh. On
`Square.CATPart` the patch adds 312 triangles and exactly **one** edge with
4 uses (every other rule-of-two edge is fine); the mesh was manifold
before. The battery tests loop-vs-record-normal coplanarity only — it
cannot see that the welded loop's boundary edge is already used twice by
the primary mesh. That is the "471-passing-stores downside exposure" the
old E0 whole-store scope was protecting against, and it is not a property
of the three width-misparsed loops (fix 3): these loops all pass the
battery.

### 5.2 Decision

Per the task's fail-safe rule ("if a corpus regression appears, STOP and
report instead of tuning the battery"), the implementation stopped here.
No battery tolerance, coverage rule or mesh-level guard was added. Options
for an owner decision (NOT implemented):

1. a per-loop mesh guard — weld only when the added triangles keep the
   assembled mesh manifold (the law becomes topology-aware; the battery
   stays untouched); or
2. a narrower non-empty scope — e.g. weld only loops whose triangles are
   disjoint from the primary mesh's edge set (the "missing panel" shape,
   which is labios/main); or
3. accept the regressions as wrong L2 rows and re-baseline the gate (this
   contradicts the task's zero-regression requirement).

## 6. Tests

`pytest -q tests/test_composite_export.py tests/test_export_v1.py` →
**87 passed**. New/re-scoped coverage:

- **non-empty primary mesh welds** (`e0b-nonempty`): 12 → 14 triangles,
  `curve_entry_law = e0b-dup-pin` (the bug's core pin);
- **non-coplanar loop stays out** (`e0b-nonplanar`): only the coplanar fan
  exports (2 triangles), the refused loop stays counted;
- **no-manifold regression pin** (`e0b-relaxed-not-manifold`): the two
  nonplanar fans are refused, the mesh stays manifold at 2 triangles;
- **per-rep paths weld per loop** (`e0b-multi-rep-conservative`,
  `e0b-multi-rep-unsupported-veto`);
- **labios/main corpus-gated regression** (skipped when the gitignored
  corpus is absent): 4,464 triangles, 5,410.18 ± 0.05 mm², manifold,
  10 welded loops, 0 dropped.

`pytest -q` (whole suite) → **696 passed, 7 skipped, 2 failed**:

- `test_port_fidelity.py::test_port_fidelity_fixture_mode` and
  `test_reproduction_smoke.py::test_reproduction_smoke_fixture_mode` fail
  because `port/src/geometry/composite.rs` still carries the old
  empty-mesh law (`dup_pin = if triangles.is_empty() && ...`). The Rust
  port and its shipped `port/pkg` + `site/viewer/pkg` artifacts are not in
  this task's owned files, so they were not changed; the Python/Rust
  twin parity gate cannot pass until the port is updated.

## 7. Files changed

- `src/catpart/geometry/composite.py` — per-loop weld, `_dup_pin_map`,
  width-rank battery, docstrings.
- `src/catpart/geometry/export.py` — the dup-pin warning text (it said
  "primary triangulation is empty"), no logic change.
- `src/catpart/schema/export-summary-v1.json` — the
  `curve-entry-loops-exported-dup-pin` description.
- `tests/test_composite_export.py` — re-scoped e0b tests + labios case.
- `tests/fixtures_gen.py` — comments only.
- `docs/evidence/2026-11-18-composite-loop-weld.md` (this note) and
  `docs/evidence/data/br6-composite-weld-claims.csv`.
