# Evidence: the no-surface display fallback — the decoded carriers, not a surface (2026-11-19)

**Date**: 2026-11-19
**Status**: COMPLETE for the display route. **104 of the 120** non-opening no-facet parts open in the viewer as exactly what their bytes decode — a point cloud and the curve segments the ``33 32`` law pins — and the other **16** carry no displayable carrier and keep their named failure. This is a **faithful display of the decoded carriers**, never a surface reconstruction: zero triangles are emitted, no point is welded and no connectivity is inferred.
**Target**: the 120 parts of the 128-row grid-meshing census that open as nothing (`docs/evidence/2026-11-19-grid-meshing.md`): 115 carry no triangulable point grid and 5 have a grid candidate that no gate admits. Today the viewer shows a classified failure over all of them.
**Method**: shipped module `src/catpart/geometry/display.py`, export wiring in `src/catpart/geometry/export.py` (`_display_fallback`), Rust port `port/src/geometry/display.rs`; the WASM boundary's additive `points` / `curveSegments` typed arrays; probe `scripts/triage/probe_no_surface_fallback.py`; corpus-free tests `tests/test_no_surface_fallback.py` (11) + the port's `display.rs` unit tests (4) + the boundary test (`port/tests/wasm.rs`); claims `docs/evidence/data/no-surface-fallback-claims.csv` (`DF-01`..`DF-06`) and per-part `docs/evidence/data/no-surface-fallback-parts.csv` (120 rows); viewer acceptance cases (point cloud + curve segments) in `scripts/viewer_acceptance.py`. Read-only over the corpus.

**Later update (same day)**: the display route was extended with the bag-rep count-framed f32 arrays (`bagrep-f32-points`), so the same 120-row population now shows **106** displays with **26,993** points (the 8,319 added points ride on 29 of its rows), and the manifest-wide open rate rises from 95.19% to 96.17%. The route, the gates and the parity are recorded in [2026-11-19-bagrep-display.md](2026-11-19-bagrep-display.md); the historical figures above stay as the measurement of the pre-extension seam.

---

## 1. Executive summary

The 120 parts carry real geometry — just not a surface. The display route decodes three carrier forms and draws them:

| Carrier | 120 parts | Displayed as |
| :--- | ---: | :--- |
| 3-divisible f64 point runs (`e5 0d` payloads + content prefix) | 3,303 runs / **17,288 points** on 97 parts | a point cloud (coordinates only — no row length is inferred) |
| `33 3X` curve-record centers (`33 33` / `33 37` / `33 38`) | 1,010 decoded centers | points |
| `33 32` line records whose G2 laws hold | **188** on 31 parts | **188 segments**, `P -> P+Q` |
| store pool points | 0 in this population | — (the vertices-only family, outside this census, also displays its pool) |

| Measurement | Value |
| :--- | ---: |
| Parts that render with the display fallback | **104/120 = 0.8667** |
| Parts with a point cloud | 97/104 |
| Parts with curve segments | 31/104 |
| Display points (total) | **18,674** |
| Display curve segments (total) | **188** |
| Triangles emitted | **0** |
| Parts that keep a named failure (no carrier at all) | **16** (`undecoded-variant`) |
| `33 3X` records walked / decoded / skipped | 3,032 / 1,198 / 1,834 |

**Verdict.** Every part with anything decodable opens as that thing, labelled `no surface — showing N points, M curve segments`. The §3.4 gate still records `empty-mesh` (0 triangles), so **L2 is unchanged by construction**; nothing here is reported as a surface.

---

## 2. What is decoded

### 2.1 The point runs

The grid module's own scan (`catpart.geometry.grid.iter_runs`) already walks every 3-divisible run of plausible f64le triples in the part's `CATPrtCont` content stream (the `e5 0d` payloads and the f64 content prefix). The display route takes **the points and only the points**: the runs that the grid shape law cannot read — single-row profiles, limit boxes, sub-grid arrays — are exactly the 115-part majority, and their coordinates are shown as decoded. No row length, ordering or adjacency is inferred, so a profile never becomes a polyline.

### 2.2 The `33 3X` curve records

The BR3 record law (`catpart.brep.curves`) is reused unchanged: a 7-B header + family + payload, walked over the **located store bodies** the exporter already trusts plus the part's `CATPrtCont` regions, deduplicated by record offset. The families:

| Family | Payload | Display |
| :--- | :--- | :--- |
| `33 32` line | 40-B f32le block, G2 `[P][Q][P]+\|Q\|` | a **segment** `P -> P+Q` when **both** laws hold |
| `33 37` circle | 4 BE f32 `(cx, cy, cz, r)` | the center point |
| `33 33` mid-ring | 6 BE f32 `(cx, cy, cz, cos t, sin t, r)` | the center point |
| `33 38` conic | 7 BE f32 `(cx, cy, cz, cos t, sin t, a, b)` | the center point |
| `33 36` | out of decode scope (BR3) | nothing (counted as skipped) |

The circle/conic families expose **no orientation** — no normal, no plane frame — so a 3-D polyline would be a guess. They contribute their decoded center and nothing else. Only the line record's own fields pin two endpoints.

### 2.3 Why the line segment is `P -> P+Q`

The block is `[P][Q][P]` plus a trailing float, and BR3 measured that float as `|Q|` — the norm of the **middle triple as a vector**, not the distance from any point. The display therefore reads the first triple as P and the second as a displacement, and the segment spans `P -> P+Q`. That reading is measured on the corpus, not assumed (**DF-03**): over the law-holding records of the first 120 pool-bearing files in manifest order, `P+Q` lands on a decoded pool vertex at 5e-3 mm **3,503/5,531 = 0.6333** of the time, against **11/5,531** for P and **38/5,531** for Q. A wrong reading would not hit the pool at that rate; `Q` as a point is refuted.

---

## 3. Fail-closed gates

1. **Full payload only.** A record whose declared length runs past the buffer is not a record (the walker's slice check). This is also a latent-crash fix in `catpart.brep.curves.iter_curve_records`: a truncated BE payload previously raised a `struct.error` mid-walk; it now contributes nothing.
2. **Both line laws, bit-exact.** The P-repeat triple must repeat `f0:f2` exactly and the trailing float must equal `|Q|` within 1e-6. A law-failing record's field roles are open (BR3), so it emits **nothing** — not even its P point.
3. **Model envelope.** Every coordinate must be finite, zero or inside 1e-6..1e5 (the 100 m envelope the grid module uses). A line endpoint outside it emits nothing.
4. **Length.** A zero-length segment (`|Q| = 0`, or `P == P+Q`) is not geometry and is dropped.
5. **BE-family plausibility and direction laws.** The circle/mid-ring/conic decoders keep BR3's checks (finite, pool-scale, mid-range direction pair unit-norm at 2e-3, `b > 0`); a rejected record is counted as skipped, never partially displayed.
6. **No carrier, no success.** A part with 0 points and 0 segments re-raises its pre-display classification (or returns the store path's vertices-only success). The viewer keeps the named failure.

Nothing is trimmed or invented to make a part display: the skipped census rides on the summary block (`skipped_curve_records`).

---

## 4. Export wiring

`_export_data` keeps its seam and adds a fourth rung:

1. **Nested store first** (`_export_store_data`, byte-for-byte unchanged). Every facet export is unchanged.
2. **Exact a5 surface** when the store path yields zero triangles (`_surface_fallback`, unchanged). A part with surface frames but no evaluable surface **keeps** the named `no-evaluable-surface` — the display route is not consulted (a5 priority).
3. **Structured grid** when there is no a5 frame (`_grid_fallback`, unchanged for a triangulating grid).
4. **Display carriers** (`_display_fallback`) when the grid yields no triangle — or immediately when there is no grid at all. It returns the store path's vertices-only summary with the display block appended when such a success exists, otherwise a fresh summary.

The summary is schema v1 additive: `no_surface_display` (`block`, `kind = "decoded-carriers"`, `surface = false`, `label`, `points` flat f32 xyz, `curve_segments` flat point-index pairs, `point_count`, `curve_segment_count`, `regions`, `pool_points`, `point_runs`, `run_points`, `curve_records`, `decoded_curve_records`, `skipped_curve_records`, `curve_points`, `line_records`, `families`, and `grid_shaped`/`grid_refusals` on a part that had a refused structured grid) and the warning class **`no-surface-display`**. For a fresh display summary `vertex_count` and `triangle_count` are 0 and the PLY is an empty (0-vertex, 0-face) file; the mesh block is vacuously manifold/closed/oriented per the schema.

**The `untriangulable-grid` class is superseded.** The 5 grid parts whose candidates no gate admits (153a33fb, 5abff0b1, 827c5b7a, cb6454b5, d665cd12) now open as point clouds; their refusal census is still named data (`grid_shaped`, `grid_refusals`, the `grid-candidates-refused` warning), so nothing is hidden. The constant stays in the vocabulary (scripts reference it) but `build_export` no longer raises it for a part that carries points.

---

## 5. Viewer

- A part with 0 triangles and a `no_surface_display` block renders its `points` (`THREE.Points`, pixel-sized) and `curveSegments` (`THREE.LineSegments`, indexed into the same array), frames the camera on the cloud, and shows the visible label **`no surface — showing N points, M curve segments`** with the note *decoded carriers — not a surface render*.
- The §3.4 gate panel still records `empty-mesh` and the gate's counts stay on screen; `viewerState.display.mode = "no-surface"` exposes the same state to the acceptance harness.
- A part with 0 points / 0 segments / 0 triangles keeps yesterday's terminal state: the named failure panel (`empty-mesh` or its classified decode error), canvas hidden.
- A mesh (facets, a5 surface, structured grid) keeps the pre-existing path and never grows a display block.

The acceptance harness (`scripts/viewer_acceptance.py`) drives both new cases over the generated fixtures: `geometry-no-surface-points` (6 points, 0 segments, gate `empty-mesh`) and `geometry-no-surface-curves` (3 points, 1 segment, gate `empty-mesh`), each labelled and each asserting the drawn objects.

---

## 6. Parity

The Rust port (`port/src/geometry/display.rs`) mirrors the module expression for expression: the same region set (located store spans + `CATPrtCont`), the same BR3 walk with the same resume rule, the same law gates in the same order, the same point order (pool, then runs, then records by offset) and the same `P -> P+Q` arithmetic. The one narrowing is the f32 display precision: the decode rounds each coordinate once (`struct.pack("<f")` / `as f32`, round-to-nearest) and stores the f64 value of that f32, so the summary's `points` are exactly the typed array's values.

`port/pkg/` was rebuilt with the pinned `wasm-pack` 0.15.1 and synced to `site/viewer/pkg/`. The boundary returns the arrays as `points: Float32Array` and `curveSegments: Uint32Array`; the summary's block is the single source (the harness compares it parsed).

| fixture | Python summary | Rust summary | typed arrays |
| :--- | :--- | :--- | :--- |
| `geometry-no-surface-points` | 6 points / 0 segments | parsed-identical | `points` 18 f32, `curveSegments` 0 |
| `geometry-no-surface-curves` | 3 points / 1 segment | parsed-identical | `points` 9 f32, `curveSegments` 2 |
| `geometry-point-grid-stalled` | display block (20 points, stalled census) | parsed-identical | — |
| `geometry-composite-law-e0b-unpinnable` | 12 pool points + display block | parsed-identical | — |
| real part `49b5981a…` (`Ehi_Support2`, CATBRepModeContainer store) | 484 points / 11 segments | parsed-identical | `points` 1,452 f32, `curveSegments` 22; PLY byte-identical (`catpart-export` vs `fidelity-cli export`) |

---

## 7. What stays closed

- **It is not a surface.** No triangle, no shell, no face, no weld. The display cannot be measured by area or by L2; it is a rendering of the decoded carriers and is labelled as such.
- **16 parts still fail.** They carry no point run and no decodable curve record (the 16 are the `error` rows of the per-part CSV); they keep `undecoded-variant`.
- **Circles, mid-rings and conics are dots.** Their payloads expose a center and a radius but no orientation; a 3-D circle would be invented.
- **Profiles are dots.** No row length exists for the 115-part majority, so their points are never joined.
- **The a5 route is unchanged.** A part with `a5 03 34` frames and no evaluable surface keeps `no-evaluable-surface`; the display fallback does not mask a surface decode gap.
- **Points are f32.** The viewer array precision; model-scale f64 values are rounded once, and the round-trip is stated, not hidden.
- **Sentinel-block points are shown.** A refused grid's trailing stalled block (e.g. the tiny 0.833 mm box behind a real sweep) is still in the bytes, so its points appear in the cloud. The refusal is named in `grid_refusals`; nothing is triangulated.

---

## 8. Detector honesty

- **The premise is measured, not assumed.** The task's population is re-derived from the 128-row grid census (`open = False` and `a5_open = False` → 120), and the display route is measured over exactly those rows.
- **The line reading is refuted-tested.** `P+Q` hits the pool at 63% and `Q`-as-a-point at 0.7%; the claim is labelled `candidate` because the block's other field roles stay open (BR3), and the segment is only drawn where both committed laws hold.
- **Center-only is a decision.** The alternative — drawing circles from center + radius in a guessed plane — would be an invention, so it is refused and stated.
- **The skipped census is published.** 1,834 of 3,032 walked records contribute nothing; the block carries the number.
- **L2 is unchanged by construction.** The gate's `empty-mesh` check fires on `triangle_count < 1`; no display summary can pass it. The fitness rate cannot move on this change.
- **The old named class is retired honestly.** `untriangulable-grid` no longer fires for a part with points; the refusal census rides as data instead, and the note says so.
- **No corpus binary is read by the tests.** The corpus-free suite builds its own bytes; the one corpus-gated test pins the population counts and one mixed part, and skips without the corpus.

---

## 9. Reproduction

```bash
export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
.venv/bin/python -I scripts/triage/probe_no_surface_fallback.py   # ~2m20s (the line-reading sample)
.venv/bin/python -m pytest tests/test_no_surface_fallback.py -q
.venv/bin/python scripts/viewer_acceptance.py                     # local Playwright (both new cases)
cd port && cargo test --locked && wasm-pack test --node
bash scripts/check.sh
```

The probe writes `no-surface-fallback-claims.csv` (6 rows) and `no-surface-fallback-parts.csv` (120 rows). Deterministic; read-only `mmap`.
