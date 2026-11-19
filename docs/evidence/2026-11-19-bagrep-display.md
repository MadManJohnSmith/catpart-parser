# Evidence: the bag-rep f32 point arrays open 14 more parts — 96.17% (2026-11-19)

**Date**: 2026-11-19
**Status**: COMPLETE. The display fallback now decodes the bag-rep payload's **count-framed f32 point arrays** as points (`bagrep-f32-points`). **14 of the 69** BLANK rows open: **12 of the 48** missing-store rows plus **2** of the 16 `undecoded-variant` rows. The manifest open rate rises from **95.19%** to **96.17%** (1,367 -> 1,381 of 1,436). Zero triangles are emitted: the arrays are coordinates only, and the measured negative for the mesh lever stands.
**Target**: the 69 BLANK rows of [2026-11-19-open-rate.md](2026-11-19-open-rate.md) — 48 missing store + no display carrier, 16 `undecoded-variant` with no display carrier, 5 `no-evaluable-surface`. The carrier is the R-BAG payload of [2026-11-19-bagrep.md](2026-11-19-bagrep.md): 41 declared arrays in 29 rows, count-first framing, 8,373 f32 (2,791 points by the 3-float convention), element shape varying inside one array.
**Method**: shipped module `src/catpart/geometry/display.py` (`_bagrep_regions`, `_bagrep_arrays`, `scan_part`), export wiring in `src/catpart/geometry/export.py` (`_display_fallback`), Rust port `port/src/geometry/display.rs`; probe `scripts/triage/probe_open_rate.py` (re-run, no new decoder); corpus-free tests `tests/test_no_surface_fallback.py` plus the port's `display.rs` unit tests. Read-only over the corpus.

---

## 1. Executive summary

| Measurement | Before | After |
| :--- | ---: | ---: |
| Part rows (report's `kind=part`) | 1,436 | 1,436 |
| MESH — triangles > 0 | 1,158 | **1,158** |
| DISPLAY — 0 triangles, points/segments non-empty | 209 | **223** |
| DISPLAY points (sum) | 343,433 | **358,103** |
| DISPLAY curve segments (sum) | 8,419 | **8,419** |
| BLANK — neither | **69** | **55** |
| Open (MESH + DISPLAY) | 1,367 (95.19%) | **1,381 (96.17%)** |
| BLANK share | 4.81% | **3.83%** |

The bag-rep lever adds points, never a surface: the MESH count and every L2 class are unchanged, and each new DISPLAY row has `triangle_count = 0`.

| The 69 BLANK rows | Rows |
| :--- | ---: |
| Carry at least one count-framed f32 array | **18** |
| … of the 48 missing-store group | 12 |
| … of the 16 `undecoded-variant` group | 2 |
| … of the 5 `no-evaluable-surface` group | 4 |
| **Now display through the arrays** | **14** |
| Kept `no-evaluable-surface` by the a5 priority | **4** |
| Carry no array at all | 51 |

The 18 rows carry **70 arrays / 2,355 displayed points**. The 14 that open hold 1,507 of those points; the four a5-blocked rows hold 848 and stay BLANK on purpose. The 209 pre-existing DISPLAY rows also gain the arrays they already carried: **13,163** more points, for the 343,433 -> 358,103 total above (8,419 segments unchanged).

---

## 2. What is decoded, and what is not

A bag-rep array is accepted exactly under the count-first measurement of the bag-rep note (§5), not under a new law:

1. a `u32le V` with `V % 3 == 0` and `9 <= V <= 3e6` in front of the block (a plausible float count);
2. the next `V` f32 at one 4-byte frame all clean (finite, zero or `1e-6 <= |v| <= 1e6`);
3. the block **ends** where the clean run ends (the next word is not a clean float) — the test that separates a declared array from a byte pattern;
4. at least 50% non-zero and no run of 64 identical words (a fill region is not a coordinate array);
5. arrays contained in a longer one are dropped.

Only then are the `V/3` triples read, in decode order, and each point is rounded once to f32 and put through the display route's existing model gate — finite, zero or inside the **100 m envelope** (`1e-6 .. 1e5`). A triple outside the envelope is counted in `bagrep_skipped` and displays nothing. The scan walks the geometry containers the missing-store census named (`CATStdCont`, `CATSeeBodyCont`, `CATBRepModeContainer`, `CGMGeom`, `CATCGRCont`), bounded at **4 MiB per region** (the largest region any of the 18 rows needs is 553,832 B; the corpus's 227 MB part skips its oversized regions fail-closed rather than building prefix sums over hundreds of MB).

**No connectivity is inferred.** The bag-rep note measured 0 facet/strip records, no triple index list (3 rows carry an in-bounds list, and all three read as pairs or a fan) and no implicit strip order (the arrays are not two rings). The arrays are coordinate write streams — the element shape varies inside one array — so they are shown as points and never joined. Zero segments and zero triangles come from this source.

---

## 3. Where the 14 come from

The 48 missing-store rows split 12 opened / 36 still BLANK; the 16 `undecoded-variant` rows split 2 opened / 14 still BLANK; the 5 a5 rows stay BLANK. By report class:

| Report class | Parts | MESH | DISPLAY | BLANK | Real open |
| :--- | ---: | ---: | ---: | ---: | ---: |
| `pass` | 1,150 | 1,150 | 0 | 0 | 1,150 |
| `not-manifold` | 6 | 6 | 0 | 0 | 6 |
| `degenerate-triangles` | 2 | 2 | 0 | 0 | 2 |
| `empty-mesh` | 20 | 0 | 20 | 0 | 20 |
| `untriangulable-grid` | 16 | 0 | 16 | 0 | 16 |
| `missing-geometry-store` | 113 | 0 | **77** | **36** | 77 |
| `undecoded-variant` | 124 | 0 | **110** | **14** | 110 |
| `no-evaluable-surface` | 5 | 0 | 0 | **5** | 0 |
| **total** | **1,436** | **1,158** | **223** | **55** | **1,381** |

Per split:

| Split | Parts | MESH | DISPLAY | BLANK | Open |
| :--- | ---: | ---: | ---: | ---: | ---: |
| dev | 1,375 | 1,101 | 219 | 55 | **1,320 (96.00%)** |
| held-out | 61 | 57 | 4 | 0 | **61 (100.00%)** |
| **all** | **1,436** | **1,158** | **223** | **55** | **1,381 (96.17%)** |

The 18 BLANK rows with an array, and the outcome of each:

| sha16 | report class | arrays | points | outcome |
| :--- | :--- | ---: | ---: | :--- |
| `084841b3a2068a72` | `missing-geometry-store` | 3 | 162 | DISPLAY |
| `18a5e736be72bf2d` | `missing-geometry-store` | 1 | 529 | DISPLAY |
| `2e1684b0e0461b11` | `missing-geometry-store` | 1 | 4 | DISPLAY |
| `314092359a7c42b0` | `missing-geometry-store` | 1 | 103 | DISPLAY |
| `3b9452edecb4f777` | `undecoded-variant` | 8 | 24 | DISPLAY |
| `4c361f3c5f63d9df` | `missing-geometry-store` | 1 | 118 | DISPLAY |
| `58ed8b2875b2734a` | `no-evaluable-surface` | 19 | 403 | BLANK (a5 priority) |
| `6c6a2e9f3d5f5303` | `no-evaluable-surface` | 17 | 358 | BLANK (a5 priority) |
| `8e8500b1c0627bcb` | `no-evaluable-surface` | 3 | 63 | BLANK (a5 priority) |
| `95636572111e8b7a` | `missing-geometry-store` | 1 | 187 | DISPLAY |
| `b00e31c89c8b5791` | `missing-geometry-store` | 1 | 17 | DISPLAY |
| `b0e07338249a0067` | `missing-geometry-store` | 1 | 16 | DISPLAY |
| `b4fd22e357f83410` | `no-evaluable-surface` | 8 | 24 | BLANK (a5 priority) |
| `c2598108ba61b0df` | `missing-geometry-store` | 1 | 76 | DISPLAY |
| `c2d1ecc6dca46685` | `missing-geometry-store` | 1 | 20 | DISPLAY |
| `d6aa6e71a25e9dd8` | `undecoded-variant` | 1 | 4 | DISPLAY |
| `dc7e292322cf3435` | `missing-geometry-store` | 1 | 187 | DISPLAY |
| `eaf6890653df8d33` | `missing-geometry-store` | 1 | 60 | DISPLAY |
| **total** | | **70** | **2,355** | **14 display / 4 a5-blocked** |

The four a5 rows are the deliberate exception: a part with `a5 03 34` frames never consults the display route, so a surface decode gap is not masked by a point cloud. They keep their named `no-evaluable-surface` class.

The 51 rows with no array keep their pre-display classification. The other 36 missing-store rows carry no framed array in a scanned payload region, and the 14 remaining `undecoded-variant` rows likewise.

---

## 4. Export wiring and the summary

`_display_fallback` gains the arrays **before** the `33 3X` record walk, after the pool and the 3-divisible f64 runs. The `no_surface_display` block is additive (schema v1, `additionalProperties: true`):

- `sources` — the non-empty carrier labels, `["decoded-carriers"]`, `["bagrep-f32-points"]`, or both;
- `bagrep_regions`, `bagrep_arrays`, `bagrep_floats`, `bagrep_points`, `bagrep_skipped` — the scan census;
- the existing `kind = "decoded-carriers"`, `surface = false`, `label`, `points`, `curve_segments` and decode counters are unchanged, so the viewer renders the array points through the same `THREE.Points` path and needs no change;
- the warning class stays `no-surface-display` (the detail names the arrays and cites this note and the bag-rep note).

The viewer's label is still the honest one — **`no surface — showing N points, M curve segments`** — and the gate still records `empty-mesh` (0 triangles), so **L2 is unchanged by construction**.

The 120-row no-surface population also gains the arrays it already carried: **29** of its rows add **8,319 points**, and the two rows `3b9452edecb4f777` / `d6aa6e71a25e9dd8` move from `undecoded-variant` to DISPLAY, so that population goes from **104 displays / 18,674 points** to **106 displays / 26,993 points** (still 188 law-pinned segments, 31 parts with segments, 0 triangles).

---

## 5. Parity

The Rust port mirrors the Python module expression for expression: the same payload-container set and 4 MiB bound, the same count-first gates in the same order, the same containment drop, the same point order (pool, f64 runs, bag-rep arrays, then `33 3X` records by offset) and the same f32 round/envelope check. The clean window is a prefix-sum difference on both sides (`_BagrepClean` / `BagrepClean`), so the accepted array set is identical.

| Population | Python summary | Rust summary |
| :--- | :--- | :--- |
| The 69 BLANK rows (including the 55 classified errors) | — | parsed-identical, 0 mismatches |
| The 120-row no-facet population | — | parsed-identical, 0 mismatches |
| `Plate.CATPart` (`4c361f3c…`) | 118 points, 1 array, 354 f32 | parsed-identical |
| `Ehi_BundleSegment3_2.CATPart` (`18a5e736…`) | 529 points, 1 array, 1,587 f32 | parsed-identical |
| `AnalysisMechfeat.CATPart` (the pre-note correction anchor) | display block + the 21-float array | parsed-identical |

`port/pkg/` was rebuilt with the pinned `wasm-pack` 0.15.1 and synced byte-for-byte to `site/viewer/pkg/`.

---

## 6. Reproduction

```bash
export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
export TMPDIR=/home/alan/.cache/t3-tmp
.venv/bin/python -I scripts/triage/probe_open_rate.py
.venv/bin/python -m pytest -q tests/test_no_surface_fallback.py
( cd port && cargo test --locked )
```

The open-rate probe writes `docs/evidence/data/open-rate-files.csv` (1,436 rows) and prints the overall, per-split, cross-class and BLANK tables. The corpus is opened read-only; the PLY goes to a temporary directory and is discarded.

## 7. Files

- `src/catpart/geometry/display.py`, `src/catpart/geometry/export.py` — the source and its summary block.
- `port/src/geometry/display.rs`, `port/src/geometry/export.rs` — the parity twin; `port/pkg/` + `site/viewer/pkg/` refreshed.
- `tests/test_no_surface_fallback.py` — the corpus-free gates plus the 14-row and 120-row corpus pins.
- `docs/evidence/data/bagrep-display-claims.csv` — the claims (`BD-01`..`BD-09`).
- `docs/evidence/data/open-rate-files.csv` — the re-run probe output.
