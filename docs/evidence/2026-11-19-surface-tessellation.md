# Evidence: the `a5 03 34` surfaces as meshes — census, tessellation, export (2026-11-19)

**Date**: 2026-11-19
**Status**: COMPLETE for the exact B-spline family (60/60 evaluable surfaces tessellate); **closed** for the 126 no-facet parts that carry no `a5 03 34` frame (their E5/f64-net dialects remain point nets)
**Target**: the next step named by `docs/evidence/2026-11-19-surface-head.md` §6/§9: the head is a degree-5 C2 non-rational B-spline — turn it into a mesh and open the 128 no-facet parts.
**Method**: shipped evaluator/tessellator `src/catpart/geometry/surface.py`, export wiring in `src/catpart/geometry/export.py`, Rust port `port/src/geometry/surface.rs`; probe `scripts/triage/probe_surface_tessellation.py`; corpus-free tests `tests/test_surface_tessellation.py` (18) and the port's `surface.rs` unit tests (5); claims `docs/evidence/data/surface-tessellation-claims.csv` (`ST-01`..`ST-05`) and per-part `docs/evidence/data/surface-tessellation-parts.csv` (128 rows). Read-only over the corpus.

---

## 1. Executive summary

The `a5 03 34` head is not just evaluable — it is **tessellatable**. Over the 128 no-facet parts the surface family is exactly the two object-stream parts the head note found. The census reproduces the head note digit for digit, the 60 evaluable surfaces all produce a sane mesh, and the export fallback opens **2/128 parts** (the per-part ceiling: **2/128 parts have ≥1 evaluable surface**, and both export).

| Measurement | 128 no-facet parts |
| :--- | ---: |
| `a5 03 34` marker frames | **106** in **2** parts |
| … tail-closed frames | **83** in 2 parts |
| … head-decodable (plausible pole net) | **63** in 2 parts |
| … evaluable surfaces | **60** in **2** parts — the per-part ceiling |
| Surfaces tessellated | **60/60** evaluable (0 refused) |
| Triangles / vertices | **86,032 / 46,562** |
| Degenerate triangles | **0** |
| Manifold per patch | **60/60** (open sheets; `closed = false` by nature) |
| Parts opened (non-empty, manifold, finite) | **2/128 = 0.0156** |

| Part | frames | tail-closed | decoded | evaluable | tessellated | triangles | vertices |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `80aad8d8…` | 70 | 66 | 46 | 46 | 46 | 68,304 | 36,942 |
| `d7ed0772…` | 36 | 17 | 17 | 14 | 14 | 17,728 | 9,620 |

The three refused surfaces are the three the head note already named (all in `d7ed0772`: two kilometre-scale merged allocations and one with no station-constant pole order). They are counted as refused, never exported.

**Verdict.** The surface head now has a mesh. The route is a **fallback**, not a replacement: the nested-store/facet path runs first and is untouched whenever it produces triangles. A part with surface frames and no tessellatable surface raises the named `no-evaluable-surface` class; a part with no surface frames re-raises its original classification. The Rust port produces **byte-identical PLY** and a parsed-identical summary on both corpus parts and on a synthetic fixture.

---

## 2. Census — what the 128 carry

The population is the bulk probe's 128 no-facet parts (`family = no-pool`, `strip_records` empty; `docs/evidence/2026-11-19-bulk-stream.md` §5.1). The census reuses the two independent pre-existing measurements and re-derives the third:

1. **frames / tail-closed** from `probe_bulk_stream.measure_region` — the A/B frame walk and the value-scan pole net (independent of the head);
2. **decoded / evaluable** from `probe_surface_head.validate` — the head note's own battery;
3. **tessellated / open** from the shipped `catpart.geometry.surface.scan_part`.

The probe asserts the shipped counters equal the head probe's, part by part (`ST-04`'s `claim disagreements=none`); a disagreement would mark the part closed.

**Population shape.** The frames are confined to two files: `80aad8d8` (70 marker frames, 66 tail-closed, 46 two-lane heads, 20 plane-subtype frames) and `d7ed0772` (36/17/17). The remaining **126 parts carry zero `a5 03 34` markers** — they are the E5 dialect (103), f64-net (4) and other (2) shapes the bulk note classified, plus the object-stream parts whose only surface frames are the two anchors. There is no hidden surface family in this population.

**A gate the direct scan needs.** Reading markers directly (rather than only tail-closed records) surfaces 4 extra head-shaped coincidences in `80aad8d8`: their head arithmetic closes on a 152/154-byte tail, but the predicted grid lands on non-numeric bytes (pole magnitudes ~1e307). The bulk decoder rejects them because its f64 run is not a point net. The shipped scanner keeps that gate (`plausible_net`: every pole finite and inside the bulk probe's `[1e-3, 1e6]` mm band, zero allowed), which is why it reports 46 decoded, not 50. The four are not surfaces and are not counted.

---

## 3. Tessellation

### 3.1 The evaluator

`catpart.geometry.surface` is the head note's grammar shipped:

- `parse_surface_head` accepts a head only when the tag, both lane counts, both strictly increasing lanes, the closing bytes and a 152/154-byte tail all agree; the grid offset is **predicted**, never searched for;
- `knot_vector` builds `[u0]×6 + interior×3 + [un]×6`; the pole net is `3·n_u × 3·n_v`;
- `basis_values` is Cox-de Boor over the built knots, degree 5, right-end closed;
- `evaluate` is the tensor-product sum in the probe's exact loop order;
- `assess` is the head note's four-check battery plus scale and chord-length coherence: exact corner poles (≤1e-9 of the net diagonal), finite samples on a 21×21 lattice, containment in the pole AABB, no reversing neighbouring normals, |coordinate| ≤ 100 m, and `u knot span / pole-polygon arc length ∈ [0.5, 2.0]`.

The battery reproduces the head note exactly: **46/46, 14/17, 60/63 evaluable** (the three refusals are the named ones). No threshold was tuned to make the count agree.

### 3.2 The grid

Each evaluable surface is sampled on an **adaptive tensor grid**:

- the parameter axis is the union of the record's knot spans; every span starts at 2 cells;
- for each cell, the surface is evaluated at the parameter centre and compared with the bilinear cell centre; a deviation above `1e-3 × bbox diagonal` doubles that span's count;
- refinement stops at 8 rounds, 16 cells per span or 65,536 grid points per patch — a bounded sample count;
- triangles are the two per cell, with a consistent (u, v) winding.

A tensor grid has **no T-junctions**, so each patch is a manifold sheet with boundary by construction. The diagonal-tied tolerance keeps a 1 m part and a 10 m part comparable; observed per-patch tolerances are **3.65–11.85 mm** (surface diagonals ~3.6–11.8 m). The polygons are **not welded between records**: each patch keeps a disjoint index space, and the merged mesh is a concatenation (the task's "no topology joins").

### 3.3 Validation

| check | 60 surfaces |
| :--- | :--- |
| every triangle finite | 60/60 (all vertices finite) |
| plausible bbox | 60/60 inside the 100 m envelope, each inside its own pole AABB |
| degenerate triangles | **0** (floor `1e-12 × diagonal²`; none dropped) |
| manifold per patch | **60/60** (`mesh.mesh_stats(...).manifold`) |
| closed | 0/60 — expected: a single tensor-product patch is an open sheet |
| oriented | false at the part level, because open-sheet boundary edges have no reverse; the existing `mesh` law defines `oriented` that way. Within each patch every interior edge is used once per direction |

Per part: `80aad8d8` 68,304 triangles / 36,942 vertices / 5,488 boundary edges; `d7ed0772` 17,728 / 9,620 / 1,484. Both are manifold and not closed.

---

## 4. Export wiring

`_export_data` is now a two-stage seam:

1. **Nested store first** (`_export_store_data`, the pre-existing code, byte-for-byte). When it returns triangles, the surface path is never entered — every facet export is unchanged.
2. **Exact-surface fallback** only when the store path raises, or when it succeeds with zero facet triangles (the G2 P7 vertices-only family). The fallback scans the `CATPrtCont` region, censuses the frames, tessellates the evaluable ones and returns one merged mesh.

Fail-closed rules:

- **No surface frames** → the store path's original classification is re-raised unchanged (`missing-geometry-store` / `undecoded-variant` / …); all 126 closed parts keep their existing failure.
- **Surface frames but no mesh** → `ExportError("no-evaluable-surface", …)` with the frame census in the detail. An empty or vertices-only mesh is never passed off as a surface export.
- **A patch that is not a manifold sheet** → refused and counted, not emitted; if all patches are refused, the same named class fires.

The summary is schema v1 additive: `surface_tessellation` (`block`, `frames`, `decoded`, `evaluable`, `tessellated`, `refused`, `pole_points`, `grid_points`, `tolerance_fraction`, `tolerance_min`, `tolerance_max`) and the warning class `bspline-surface-tessellated`; `open-shell` rides as usual. `origin_kind` is `block` (the `CATPrtCont` region), `pool_group_count` / facet counters are 0.

---

## 5. Parity

The Rust port mirrors the module expression for expression (same loop order, same `sqrt`/distance arithmetic, no `mul_add`; the module carries the pinned `suboptimal_flops` carve-out). The port's `export_data` has the same two-stage seam and the same typed summary block.

Measured on the two corpus parts and on the synthetic fixture (`geometry-surface-bspline`, a `CATPrtCont` block with one degree-5 record):

| file | Python PLY sha256 | Rust PLY sha256 | summary |
| :--- | :--- | :--- | :--- |
| `80aad8d8` (`510.000_NOTE A.CATPart`) | `6ffbfb5e5d331ce08d32a24f3815fb42c54dafc80cf9692eff6656b5d1b07458` | same | parsed-identical |
| `d7ed0772` (`512.000_NOTE A.CATPart`) | `92f2490187ad99612c3fc3c9983f4d9af4c0632a2446998451088c16267b99ee` | same | parsed-identical |
| synthetic fixture | byte-identical | byte-identical | parsed-identical |

The fixture also joins the Fidelity export matrix at seeds 0 and 7, so `tests/test_port_fidelity.py` keeps the byte-identity pin live. The fail-closed fixture `geometry-surface-no-evaluable` (a plausible all-zero pole net) produces the same `no-evaluable-surface` class on both sides. `port/pkg/` was rebuilt with the pinned `wasm-pack` and synced to `site/viewer/pkg/`.

---

## 6. What stays closed

- **126/128 parts** carry no `a5 03 34` marker: no exact B-spline surface exists in them under the pinned grammar. The E5 dialect's 98 rectangular grids (`docs/evidence/2026-11-19-e5-dialect.md`) are still **point nets** — their payload has no degree/knot reading, so they are not silently promoted to surfaces.
- **3 surfaces** in `d7ed0772` decode but do not evaluate (the head note's named blockers: two ~1 km merged allocations and one non-station-constant ordering). They remain refused.
- **No topology joins.** Two surfaces that meet in the CAD model are exported as independent patches; their shared boundary is two coincident boundary edges, not one welded edge. The mesh is a collection of sheets, not a watertight solid.
- **No ground truth.** The validation is geometric (finite, hull-bounded, chord tolerance, manifold), not a comparison against a CAD kernel.

---

## 7. Reproduction

```bash
export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
.venv/bin/python -I scripts/triage/probe_surface_tessellation.py
.venv/bin/python -m pytest tests/test_surface_tessellation.py -q
port/target/release/fidelity-cli export \
  'corpus/.../510.000_NOTE A.CATPart' /tmp/surface.ply
scripts/check.sh
```

The probe writes the two data files (`surface-tessellation-claims.csv`, 6 rows: `ST-01`..`ST-05` with `ST-02` per carrier; `surface-tessellation-parts.csv`, 128 rows). Deterministic; read-only `mmap`; ~36 s for the population.

---

## 8. Detector honesty

- **The census is cross-checked, not asserted.** Tail-closed counts come from the independent bulk value scan; decoded/evaluable counts are recomputed with the head probe's own battery. The probe marks a part closed on any disagreement (`none` observed).
- **The 4 head-shaped coincidences are excluded by a named gate**, not silently dropped: the pole net must be a plausible model-coordinate run, the same gate the bulk decoder applies. Without it the census would over-count decoded heads (50 vs 46 on `80aad8d8`).
- **Tessellation tolerance is measured, not assumed.** It is `1e-3` of each patch's own pole-net diagonal; the observed range is stated. The refinement error is the centre-to-bilinear deviation, an approximation of chord error, not a proof of a tight Hausdorff bound.
- **"Manifold" is the existing edge-count law**, measured per patch (`edge used ≤ 2`). It is not a topological-solid claim; every patch is open and patches are not joined.
- **The fallback is fail-closed and narrow.** It fires only when the facet path yields no triangles, and a part with no surface frames keeps its original error class. The 126 closed parts were not reclassified.
