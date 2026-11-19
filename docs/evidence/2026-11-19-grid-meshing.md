# Evidence: the structured point grids as **candidate** meshes (2026-11-19)

**Date**: 2026-11-19
**Status**: COMPLETE for the grid law and the triangulation; the connectivity is an **inference** (`candidate`) by construction, never a decoded surface. **Closed** for 115/128 parts that carry no `>=3x3` grid at all, and for 5 candidate-bearing parts whose grid does not triangulate (named `untriangulable-grid`).
**Target**: the next step named by `docs/evidence/2026-11-19-surface-tessellation.md` §6: the 126 no-facet parts that carry no `a5 03 34` frame. The task asked to "open the grid-only parts by triangulating their structured point grids".
**Method**: shipped module `src/catpart/geometry/grid.py`, export wiring in `src/catpart/geometry/export.py`, Rust port `port/src/geometry/grid.rs`; probe `scripts/triage/probe_grid_meshing.py`; corpus-free tests `tests/test_grid_meshing.py` (13) and the port's `grid.rs` unit tests (4); claims `docs/evidence/data/grid-meshing-claims.csv` (`GM-01`..`GM-06`) and per-part `docs/evidence/data/grid-meshing-parts.csv` (128 rows); fixtures `geometry-point-grid` / `geometry-point-grid-stalled` in the Fidelity matrix. Read-only over the corpus.

---

## 1. Executive summary

The grid carriers **do** triangulate, but the population's shape is not what the task assumed. Of the 128 no-facet parts, **13** carry at least one `>=3x3` grid candidate (101 candidates in total: 98 in `e5 0d` record payloads — exactly the committed E5 census — plus 3 in the f64-net content prefix). The other **115 parts carry no grid at all**: their 3-divisible f64 runs are the 665 single-row profiles / limit boxes and sub-grid arrays the E5 note already counted (`docs/evidence/2026-11-19-e5-dialect.md` §4.2), which cannot be triangulated without guessing a row length.

| Measurement | 128 no-facet parts |
| :--- | ---: |
| Parts with a `>=3x3` grid candidate | **13** |
| … candidates | **101** (`e5` 98 + f64-net prefix 3) |
| Candidates triangulated | **55/101** = 0.5446 |
| … refused, by named gate | 46 (stalled stations 34, degenerate cells 8, non-monotone prefix 1, non-uniform prefix 2, stalled columns 0, not-manifold 0) |
| Triangles / vertices | **28,044 / 15,818** |
| Degenerate triangles emitted | **0** (a grid with a zero-area cell is refused, not trimmed) |
| Manifold per grid | **55/55** (open sheets; `closed = false` by nature) |
| Parts opened by the grid route | **6/126 = 0.0476** (parts without an `a5 03 34` frame) |
| … over the whole no-facet population | **8/128 = 0.0625** (the 6 grid parts + the 2 a5-surface parts) |
| Candidate-bearing parts that raise `untriangulable-grid` | **5** (153a33fb, 5abff0b1, 827c5b7a, cb6454b5, d665cd12) |
| Candidate-bearing parts that export via a5 priority | **2** (80aad8d8, d7ed0772) |

| Part | candidates | meshed | triangles | vertices | boundary edges | PLY sha256 (Python = Rust) |
| :--- | ---: | ---: | ---: | ---: | ---: | :--- |
| `07d3c70b…` | 9 | 7 | 1,964 | 1,152 | 326 | `c7b8a6e25769bb35b94410f262859ded886e0cf0e215d23ec51a5998fa0b7f96` |
| `0f0ff88b…` | 22 | 20 | 11,782 | 6,597 | 1,372 | `271b18e49542e6ca3805378530962fdddab9306c479fe2ca2f355b963e23ed2a` |
| `bdd7ec87…` | 9 | 5 | 2,038 | 1,152 | 256 | `22d354b89edecae38b2dbd2011f600900a5eaad01e0465d2f06315831e4be077` |
| `c377cd20…` | 8 | 2 | 288 | 200 | 108 | `75c553d79bb843b31ec421dec79efad191ac2f6ee1c7a2f38b8ce7cf83e8d12e` |
| `d9ad440e…` | 10 | 1 | 190 | 120 | 48 | `95504f7584ad2de04aff3d320a3713bea5ba96b5b9ffc75ccfe118c20c919eeb` |
| `eb8df968…` | 22 | 20 | 11,782 | 6,597 | 1,372 | `271b18e49542e6ca3805378530962fdddab9306c479fe2ca2f355b963e23ed2a` |

`0f0ff88b` and `eb8df968` are two vendor copies of the same geometry: they produce the same 22 candidates, the same 20 admissible grids and a **byte-identical PLY**, which is itself a parity check on the decode.

**Verdict.** The grid route is real and it is labelled for what it is: **candidate connectivity**. It opens 6 of the 126 grid-only parts (and 1 in 5 candidate-bearing parts), and it proves the rest closed by name. It is a fallback behind facets and behind the exact a5 surfaces; no facet store and no evaluable a5 surface changed output.

---

## 2. What the carriers are

Both dialects were already framed; this note joins them to a mesh.

### 2.1 The `e5 0d` record payloads

The record law is the E5 note's: `e5 0d | flag:u8 | class:u16le | length:u32le | id:u32le | payload`, admitted only in chained runs of `>=3` records that close on their own end. For every admitted record the module takes the **longest 3-divisible run of plausible f64le triples** in the payload (finite, `0` allowed, inside the 100 m envelope — the committed band, floor `1e-6`, ceiling `1e5`). On the population that reproduces the committed count exactly: **98 grids**, and part by part the same `(rows, cols)` multiset (`GM-01`, disagreements `none`).

### 2.2 The f64-net content prefix

The content start is the metadata table's end (the bulk probe's validation scan: `total_size/count` big-endian, records closing exactly at `start + total`, the last value naming a `Cont_` stream). The prefix allocation is the maximal plausible f64 run that **begins** there — never a search over the whole region for a nicer array. Three prefix candidates fit a `>=3x3` shape (`80aad8d8` 36×21 = the known 756-point prefix, `d7ed0772` 48×21 after the 100 m band cut the merged run, and `bdd7ec87` 81×9). None triangulates (two non-uniform, one non-monotone — §4.3); the two a5 parts export through the surface route.

### 2.3 Row/column structure and point ordering

The grid is **row-major**: consecutive `cols` points are one station row, rows advance with the outer index. The bytes pin the grouping and the ordering at once, because the committed shape law is:

- `cols` is probed from the top down (`min(n, 256) … 3`), and the **largest** divisor whose every row is near-constant in one coordinate (mean within-row range `<= 1%` of that axis's span) wins;
- **rows `>= 3`, cols `>= 3`**, all coordinates model-scale.

The largest-divisor rule is not arbitrary. A smaller divisor **splits** a station row (still near-constant, but it is no longer the row), while a larger divisor **merges** two station rows (the within-row range grows by a station step and fails the 1% bar). The committed E5 dimensions are exactly this fit's output, and the module reproduces all 98 of them part by part. A column-major storage is a **different grid** under the same fit (its constant groups have another length), so the ordering is read from the bytes, never guessed. Accepted and refused shapes:

| Accepted (meshed) | grids | Refused (named gate) | grids |
| :--- | ---: | :--- | ---: |
| 18×18 | 40 | 60×5 stalled | 6 |
| 6×6 | 4 | 24×18 stalled | 4 |
| 15×12 | 2 | 36×5 / 44×5 / 32×5 stalled | 4 each |
| 21×21 | 2 | 24×5 / 20×5 stalled | 3 each |
| 4×25 | 2 | 108×3 degenerate | 3 |
| 24×12 / 24×9 / 12×18 / 24×18 / 20×6 | 1 each | 60×3 / 52×5 / 36×10 / 12×5 / 12×10 / 63×9 / 72×4 | 1–2 each |

The **40 accepted 18×18 grids are the committed 40** — the largest single family in the E5 census.

---

## 3. Triangulation — the inference

Each grid contributes two triangles per cell, `(a, b, c)` and `(a, c, d)` over the cell corners `a = i*cols + j`, `b = (i+1)*cols + j`, `c = (i+1)*cols + j + 1`, `d = i*cols + j + 1` — the same winding convention the exact-surface tessellator uses. A tensor grid has no T-junctions, so each grid is a manifold sheet with a boundary by construction. Grids of a part are concatenated with **disjoint index spaces**: one vertex per grid point, no welding, no topology join.

This is explicitly **not a surface decode**: the carriers have no degree, knot vector or evaluation, and the summary says so (`grid_meshing.connectivity = "candidate"`, warning class `point-grid-meshed`, detail "connectivity is an INFERENCE (candidate), not a decoded surface").

---

## 4. Validation — and the fail-closed gates

### 4.1 The three-level check

| check | 55 grids |
| :--- | :--- |
| every vertex finite | 55/55 |
| plausible bbox | 55/55 (inside the 100 m envelope; every grid inside its own point AABB) |
| degenerate triangles emitted | **0** (a grid with any zero-area cell is refused whole) |
| manifold per grid | **55/55** (existing edge-count law: every edge used `<= 2`) |
| closed | 0/55 — a single grid sheet is open by nature; `oriented = false` for the same boundary-edge reason the surface patches have |

Part level: 6/6 opened parts are finite, bbox-plausible and manifold.

### 4.2 The gates, and what they catch

1. **No `>=3x3` shape** — not a grid: 665 single-row profiles and sub-grid arrays; the part keeps its pre-grid classification.
2. **Stalled station or column step** (advance `<= 1e-9` of the grid diagonal): 34 grids. This is the corpus' trailing sentinel block — e.g. `c377cd20`'s 44×5 run is 32 real station rows followed by 12 rows of a tiny `0.833`-mm box; `153a33fb`/`5abff0b1`/`cb6454b5`/`827c5b7a` end in repeated identical rows. Triangulating them would append a bogus box to real surface, so the whole grid is refused.
3. **Zero-area cell**: 8 grids (the 3-column `60×3`, `108×3`, `63×9`, `72×4` runs collapse a cell).
4. **Non-manifold cell complex**: 0 (the tensor grid is manifold unless a gate above already fired).
5. **Prefix-only fit**: monotone stations and a bounded station-centroid step ratio (`<= 4`). The prefix dialect has no committed dimension, so it must fit the conservative fallback. It refuses `bdd7ec87`'s 81×9 (non-monotone) and the two a5 prefixes (non-uniform); `d665cd12`'s 72×4 helical prefix fails the degenerate-cell gate first.
6. **Duplicate point runs** are one grid (the writer's copy is not a second surface): 0 duplicates measured in this population.

E5 grids are **not** re-tested for monotonicity: a cyclic sweep is a legitimate grid (`07d3c70b`'s 24×12/24×9 and `d9ad440e`'s 20×6 are cyclic and mesh; the monotone count rides on the summary as `station_monotone`). That asymmetry is deliberate and documented: the E5 dimension is committed, the prefix fit is not.

### 4.3 Per part

`docs/evidence/data/grid-meshing-parts.csv` carries all 128 rows. The candidate-bearing parts:

| Part | carriers | candidates | meshed | refused | gate(s) | opened |
| :--- | ---: | ---: | ---: | ---: | :--- | :--- |
| `07d3c70b…` | 427 | 9 | 7 | 2 | degenerate-cells 2 | yes |
| `0f0ff88b…` | 396 | 22 | 20 | 2 | stalled-stations 2 | yes |
| `153a33fb…` | 16 | 2 | 0 | 2 | stalled-stations 2 | **no** — `untriangulable-grid` |
| `5abff0b1…` | 51 | 4 | 0 | 4 | stalled-stations 4 | **no** |
| `80aad8d8…` | 1 | 1 | 0 | 1 | non-uniform-stations 1 | a5 surface (priority) |
| `827c5b7a…` | 18 | 4 | 0 | 4 | stalled-stations 4 | **no** |
| `bdd7ec87…` | 412 | 9 | 5 | 4 | degenerate-cells 3, non-monotone 1 | yes |
| `c377cd20…` | 105 | 8 | 2 | 6 | stalled-stations 6 | yes |
| `cb6454b5…` | 53 | 8 | 0 | 8 | stalled-stations 8 | **no** |
| `d665cd12…` | 409 | 1 | 0 | 1 | degenerate-cells 1 | **no** |
| `d7ed0772…` | 1 | 1 | 0 | 1 | non-uniform-stations 1 | a5 surface (priority) |
| `d9ad440e…` | 70 | 10 | 1 | 9 | stalled-stations 8, degenerate 1 | yes |
| `eb8df968…` | 386 | 22 | 20 | 2 | stalled-stations 2 | yes |

---

## 5. Export wiring

`_export_data` keeps the two-stage seam and adds a third rung:

1. **Nested store first** (`_export_store_data`, byte-for-byte unchanged). When it returns triangles the grid path is never entered — every facet export is unchanged.
2. **Exact a5 surface only when the store path raises or yields zero facet triangles** (`_surface_fallback`, unchanged). A part with surface frames but no evaluable surface keeps the named `no-evaluable-surface` — the grid path is **not** consulted (a5 priority).
3. **Structured grid only when there are no a5 frames** (`_grid_fallback`). A part with no `>=3x3` candidate returns the store path's previous success or re-raises its original classification; a part with candidates and no mesh raises the named **`untriangulable-grid`** with the per-gate census in the detail.

The summary is schema v1 additive: `grid_meshing` (`block`, `carriers`, `shaped`, `meshed`, `refused`, `refusals`, `duplicate_grids`, `station_rows`, `columns`, `station_monotone`, `points`, `connectivity`) and the warning classes **`point-grid-meshed`** (the candidate mesh) and **`grid-candidates-refused`** (a part that meshed some grids and refused others, with the per-gate census); `open-shell` rides as usual. `origin_kind` is `block`, `pool_group_count` / facet counters are 0, `degenerate_triangle_count` is 0.

---

## 6. Parity

The Rust port (`port/src/geometry/grid.rs`) mirrors the module expression for expression: the same record walk, the same largest-divisor fit with the same tie order, the same plain-`sqrt` distance/area arithmetic (no `hypot`, no `mul_add`), the same gate order and the same triangle order. The port's `export_data` has the same three-rung seam and the same typed summary block. `port/pkg/` was rebuilt with the pinned `wasm-pack` and synced to `site/viewer/pkg/`.

| file | Python PLY sha256 | Rust PLY sha256 | summary |
| :--- | :--- | :--- | :--- |
| `07d3c70b` | `c7b8a6e2…f96` | same | parsed-identical |
| `0f0ff88b` | `271b18e4…d2a` | same | parsed-identical |
| `bdd7ec87` | `22d354b8…077` | same | parsed-identical |
| `c377cd20` | `75c553d7…d2e` | same | parsed-identical |
| `d9ad440e` | `95504f75…eeb` | same | parsed-identical |
| `eb8df968` | `271b18e4…d2a` | same | parsed-identical |
| fixture `geometry-point-grid` | `19dc35d9…add` | same | parsed-identical |
| fixture `geometry-point-grid-stalled` | (refused) `untriangulable-grid` | same class | class-identical |

The two fixtures join the Fidelity export matrix (`geometry-point-grid` valid — it carries one meshable 4×5 net **and** one stalled 5×5 net, so both warning paths run; `geometry-point-grid-stalled` in the corrupted list), so `tests/test_port_fidelity.py` keeps the byte-identity pin live and the refusal class is compared exactly.

---

## 7. What stays closed

- **115/128 parts** carry no `>=3x3` grid: their point runs are single-row profiles, limit boxes and sub-grid arrays. No row length exists to triangulate; they keep their pre-grid classification.
- **5/13 candidate-bearing parts** do not triangulate: four end in a stalled sentinel block (`153a33fb`, `5abff0b1`, `827c5b7a`, `cb6454b5`) and `d665cd12`'s 72×4 helical prefix collapses a cell. They raise `untriangulable-grid`; nothing is emitted.
- **46/101 candidate grids** are refused with a named gate (§4.2). The 34 stalled ones are the corpus' padded runs — refusing them is what prevents a sentinel box being appended to real surface.
- **No ground truth.** Validation is geometric (finite, hull-bounded, no degenerate cell, manifold), not a comparison against a CAD kernel; the connectivity itself is an inference.
- **No topology joins.** Two grids that meet in the model are independent sheets; shared boundaries are two coincident boundary edges, not one welded edge.
- **Prefix candidates are all refused.** The f64-net dialect's allocations do not pin a clean grid (non-monotone or non-uniform stations); the two a5 parts among them export through the surface route.

---

## 8. Detector honesty

- **The premise is corrected, not adopted.** The task said "the other 126 parts carry structured point grids"; the measurement says 13/128 carry a `>=3x3` grid and 115 carry profiles/sub-grid arrays. The note reports that instead of fitting a grid where none exists.
- **The committed census is cross-checked.** The shipped E5 shape census must equal `probe_e5_bulk.measure_region(...).grids` and its shape multiset part by part; the probe marks the part closed on a disagreement (`none` observed). The 98 E5 candidates are the committed 98.
- **The shape pin is stated, not hidden.** "Largest admissible row length" is the rule; it reproduces the committed E5 dimensions exactly, and the split/merge argument explains why smaller/larger divisors fail. The prefix dialect has no committed dimension, so it gets the conservative monotone/uniform fallback instead.
- **Refusals are whole-grid, named and counted.** A stalled or degenerate grid contributes no triangle; the summary and the error detail carry the per-gate census. Nothing is trimmed to make a grid pass.
- **"Manifold" is the existing edge-count law**, measured per grid; it is not a topological-solid claim, and every grid is open.
- **The fallback is narrow.** It fires only when the facet path yields no triangles and no a5 frame exists; a facet store and an a5 surface keep their output byte-for-byte, and a part with no candidate keeps its original error class.

---

## 9. Reproduction

```bash
export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
.venv/bin/python -I scripts/triage/probe_grid_meshing.py
.venv/bin/python -m pytest tests/test_grid_meshing.py -q
port/target/release/fidelity-cli export \
  'corpus/.../510.000_NOTE A.CATPart' /tmp/grid.ply
scripts/check.sh
```

The probe writes `grid-meshing-claims.csv` (6 rows) and `grid-meshing-parts.csv` (128 rows). Deterministic; read-only `mmap`; ~20 s for the population.
