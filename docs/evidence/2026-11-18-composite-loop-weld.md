# Composite exporter: per-loop dup-pin weld behind a mesh-manifold guard (#34)

Date: 2026-11-18
Base: `df02aed` (main)
Branch: `fix/composite-per-loop-weld`
Status: **implemented, port-parity verified, full corpus A/B clean (0
manifold regressions, 0 decreases), full gate green.**

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
   `PLANE_TOL = 2e-3` (`_loop_plane_status`); and
3. it is **mesh-safe** — its triangles contain no degenerate emission and
   adding them keeps the assembled mesh MANIFOLD: no undirected edge would
   exceed two uses.

A refused/unpinnable loop stays dropped and counted; it no longer vetoes
another loop's weld. The `not triangles` precondition is deleted on the
single-rep path (`_triangulate` / `decode_composite_store`) and the
store-level empty-mesh gate is removed from both per-rep paths
(`_decode_per_rep`, `_decode_mixedwrite`), so every exported path makes the
same per-loop decision.

### 2.1 The incremental mesh guard

The guard (`_edge_uses` / `_e0b_dup_pin`) builds the undirected edge-use
histogram once from the primary triangles this `_triangulate` call already
emitted, then processes the dropped loops in record/encounter order:

- candidate loop triangles are histogrammed locally (O(the loop's
  triangles));
- if any `base_uses + candidate_uses > 2`, or the loop produced a
  degenerate skip (`_loop_triangles`' convention), the loop is refused and
  the histogram is left untouched;
- otherwise the candidate's uses fold into the histogram and the loop is
  welded, so later loops see it (deterministic, order-dependent by design).

This is fail-closed and does not revalidate the whole store. Per-rep
element spaces are disjoint (their exported indices are offset per rep), so
the per-rep guard is exact. A pre-existing non-manifold primary mesh stays
non-manifold (no regression), but the weld never adds an over-use to it.

Why the guard is required: after fix 1 alone the full-corpus A/B found 26
manifold → non-manifold regressions. The welded loops there are real
geometry (area grows, no duplicate unordered triples to dedupe), but their
boundary edges already had two uses in the surviving primary mesh — the
coplanarity battery cannot see mesh topology. The guard rejects exactly
those loops (section 4.3).

Measured on labios/main, fix 1 (battery + guard) alone:

| | triangles | area (mm²) | manifold | welded loops | dropped |
|---|---:|---:|---|---:|---:|
| before | 4,261 | 2,299.09 | true | 0 | 13 |
| fix 1 | 4,457 | 5,396.79 | true | 10 | 3 |

The 10 welded loops' record offsets: 317972, 318005, 325684 (2 loops),
326037 (2 loops), 331744, 331779, 335648 (2 loops). Deviations under the
battery: 0.0, 4.6e-15, 9.5e-7, 7.5e-7, 1.4e-6, 1.4e-6, 5.3e-15, normal-less,
9.5e-7, 8.8e-7. Their faces are the missing envelope panels, so the guard
accepts all ten (the panels are disjoint from the surviving edge set).

## 3. Fix 2 — the gap-edge width rank runs the same battery

`parse_strip_records` ranks width candidates by exact tiling, repeats,
out-of-range refs, then non-coplanar loops, then narrower width. In the
gap-edge case (no candidate tiles exactly) a width-1 misread can land its
loops on skip slots; those loops were previously excluded from the plane
battery, so the misread won the ranking and its loops were then dropped.

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
13.39 mm² / +7 triangles.

## 4. Corpus A/B method

Both sides use the same interpreter (`.venv`) and the same manifest order:

- base: a detached worktree at `df02aed`, `PYTHONPATH` pointing at its
  `src`;
- patched: this worktree's `src`;
- each part exported with `catpart.cli.main_export`, the PLY parsed back
  with stdlib `struct`, triangle count and summed triangle area recorded,
  and the summary's `mesh.manifold` flag compared.

### 4.1 The ~50-part sample

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
| M4x10_Poelier.CATPart | 449 | 1277 | +828 | 360.32 | 499.52 | +139.20 | false→false | 185 |
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

Totals over the 50: 28,702 → 58,451 triangles. `servo.CATPart` reproduces
labios/main's exact 4,464 / 5,410.18 row (same store content).

### 4.2 Full corpus (1,442 tried; 1,173 exported under the base)

The same 1,173 parts were re-exported with the guard (all still export):

- changed: 702 of the 703 pre-guard changes survive (one part, `Bateria`,
  returns exactly to its pre-fix mesh — its 2 candidate loops were the
  guard's rejects);
- welded loops: 93,426 without the guard → **91,255 with it**; the guard
  rejected **2,171 loops** on 43 parts (2.3% of the welded-loop set);
- triangles: 710,099 → 1,444,031;
- **manifold → non-manifold: 0**; triangle decreases: 0; area decreases: 0;
- of the 43 parts with guard rejections, 26 were the pre-guard regressions
  (all now manifold) and 17 were already manifold and simply stay manifold
  while welding fewer loops.

### 4.3 Guard rejections — five examples

Chosen from the 26 pre-guard regressions; each shows the loops the guard
kept out and the restored manifold verdict.

| part | rejected loops | welded (no guard) | welded (guard) | tris before | tris no-guard | tris guard | manifold guard |
|---|---:|---:|---:|---:|---:|---:|---|
| `Hitbox_WorkFile_main.CATPart` | 100 | 447 | 347 | 2,398 | 9,752 | 9,726 | true |
| `MPU6050_Solders.CATPart` | 24 | 79 | 55 | 161 | 369 | 307 | true |
| `MPU6050_Wires.CATPart` | 23 | 77 | 54 | 105 | 655 | 381 | true |
| `_NPart#194321.CATPart` | 20 | 1,731 | 1,711 | 10,030 | 31,504 | 31,175 | true |
| `Square.CATPart` | 2 | 57 | 55 | 96 | 408 | 399 | true |

The 26 fixed rows include `SP02_ALPHA5_SEPA2_PRINCIPALE` (8 rejected /
2,704 welded / 27,001 triangles, manifold), `TerminalBlock10_CI` (8 / 451 /
1,770), `Coletor de Admissao` (19 / 190 / 2,965), `Base` (1 / 467 / 2,897),
and `Bateria` (2 / 0 / 312 — the one fully-lost change). `Square.CATPart`
is the minimal case: the naive law added 312 triangles and exactly one edge
reached 4 uses; the guard refuses the 2 offending loops and the mesh stays
manifold at 399 triangles.

## 5. Port parity

`port/src/geometry/composite.rs` now mirrors the Python law:

- `e0b_dup_pin` is per-loop, with `dup_pin_map`, the 2e-3 battery
  (`loop_plane_status`) and the incremental `edge_uses_of` guard
  (undirected edges, max 2, degenerate refusal, fail-closed);
- `parse_strip_records` runs the same dup-pinned battery on skip-bearing
  loops in the width rank;
- both per-rep paths merge welded loops unconditionally and subtract the
  welded count from `loops_curve_entry`;
- the warning text and the schema description match the Python strings
  byte-for-byte (the fidelity harness compares them).

Rust unit tests: `dup_pin_welds_to_the_preceding_written_element` and
`dup_pin_battery_and_mesh_guard_refuse_fail_closed` (battery refusal, base
over-use refusal, disjoint weld, degenerate refusal).

`port/pkg` was rebuilt with `wasm-pack build --target web --release` and
copied to `site/viewer/pkg` (the gate's byte-identical check).

## 6. Tests and gate

- `pytest -q tests/test_composite_export.py tests/test_export_v1.py` →
  **89 passed**.
- `pytest -q` (whole suite) → **689 passed, 7 skipped, 0 failed**.
- `bash scripts/check.sh` → **exit 0**:
  - ruff clean; 689 passed / 7 skipped; claims-CSV checker clean;
  - cargo native + wasm32 builds, `fmt --check`, `clippy -D warnings`,
    `cargo test` 145 + 6 passed;
  - `wasm-pack build`/`wasm-pack test --node` 10 passed; `port/pkg` vs
    `site/viewer/pkg` sync; Node suites 10/10, 10/10, 14/14, 5/5; the
    Playwright assembly acceptance ran and passed.

New/re-scoped coverage:

- **non-empty primary mesh welds** (`e0b-nonempty`): the open box's 10
  triangles plus a disjoint loop → 12, manifold (labios' missing-panel
  shape);
- **mesh guard refuses a duplicate face** (`e0b-mesh-guard`): full box +
  the same loop → 12 (not 14), manifold, loop stays named;
- **battery is not weakened** (`e0b-nonplanar-refused`, formerly
  `e0b-relaxed-not-manifold`): the two nonplanar fans stay out, 2
  triangles, manifold;
- **per-rep paths weld per loop** (`e0b-multi-rep-conservative`,
  `e0b-multi-rep-unsupported-veto`);
- **labios/main corpus-gated regression** (skipped when the gitignored
  corpus is absent): 4,464 triangles, 5,410.18 ± 0.05 mm², manifold,
  10 welded loops, 0 dropped.

## 7. Files changed

- `src/catpart/geometry/composite.py` — per-loop weld, `_dup_pin_map`,
  `_edge_key`/`_edge_uses` guard, width-rank battery, docstrings.
- `src/catpart/geometry/export.py` — the dup-pin warning text.
- `src/catpart/schema/export-summary-v1.json` — the
  `curve-entry-loops-exported-dup-pin` description.
- `tests/test_composite_export.py` — re-scoped e0b tests, mesh-guard
  negative, labios case.
- `tests/fixtures_gen.py` — the opened-box non-empty positive, the new
  mesh-guard negative, the renamed nonplanar-refused variant.
- `scripts/fidelity_run.py`, `scripts/reproduction_run.py`,
  `tests/test_reproduction_smoke.py` — variant rename / not-manifold
  branch moved to `dedup-declined`.
- `port/src/geometry/composite.rs`, `port/src/geometry/export.rs` — the
  same law and the parity strings.
- `port/pkg/*` + `site/viewer/pkg/*` — rebuilt wasm artifact (binary only).
- `docs/evidence/2026-11-18-composite-loop-weld.md` (this note) and
  `docs/evidence/data/br6-composite-weld-claims.csv`.
