# Evidence: BR4 cylindrical / quadric surface recognition — SRF-02..07 (Ticket #56, Spec G #47)

**Date**: 2026-11-17
**Status**: COMPLETE (SRF-02/03/04 decoded at tessellation level; SRF-05/06 documented-open; SRF-07 candidate signature; gate green)
**Target Ticket**: Ticket #56 (`BR4: Cylindrical, quadric & analytic surface recognizer`)
**Parent Spec**: Spec G #47 (Phase 7, B-rep / L3 fitness)
**Method**: RE-only corpus-wide recognition over all 1,442 manifest parts (L2-pass join 1,089 files). Recognizer library `src/catpart/brep/quadrics.py`; corpus triage `scripts/triage/decode_brep_quadrics.py` (stdlib, mmap, deterministic, sorted manifest order); per-claim rates in [`br4-quadrics-claims.csv`](data/br4-quadrics-claims.csv) — every prose figure below is a CSV row or a row-derived sum. Builds on G3's facet model and the stage-3d composite identity decode — their grammars are cited, not re-derived. Byte offsets cite BOTH bases (`+0x08 (8d)` style).

---

## 1. Executive summary

| Construct | Outcome | Recognition rate (this decode) | Census tie-out |
| :--- | :--- | :--- | :--- |
| `SRF-02` Cylindrical Surface | **decoded** (tessellation-level) | **24,990 cylinder patches**; **702/1,442 corpus / 679/1,089 L2-pass files** carry >= 1 (`SRF-02_cylinder_allscopes_presence`: 0.486824 corpus / 0.623508 L2) | frozen row reproduced EXACTLY from the census strips column (`S02_census_tieout_corpus`: 1,128/1,442 = 0.782247; `S02_census_tieout_l2`: 1,086/1,089 = 0.997245) — but it measured STRIP PRESENCE, not cylinders |
| `SRF-03` Conical Surface | **decoded** (tessellation-level, thin population) | **12 cone patches / 4 files** (0.002774 corpus / 0.003673 L2, composite-decoded scope); 0 on pool-only | frozen 542/0.465 has NO committed generator (§6) |
| `SRF-04` Spherical Surface | **decoded** (tessellation-level) | **519 sphere patches**; **93/1,442 corpus / 82/1,089 L2 files** (`SRF-04_sphere_allscopes_presence`: 0.064494 corpus / 0.075298 L2) | frozen 412/0.354 has NO committed generator (§6) |
| `SRF-05` Toroidal Surface | **documented-open** | — (torus fillets are rejected BY the cone/sphere laws into `curved-unclassified`) | frozen 320/0.275 has NO committed generator (§6) |
| `SRF-06` Surface of Revolution | **documented-open** | — (superset problem: cylinder/cone/sphere ARE revolutions; construction history is not in the tessellation) | frozen 680/0.582 has NO committed generator (§6) |
| `SRF-07` Extruded Surface | **candidate** (negative-space signature) | **5,517 pencil-noncyl patches**; **388/1,442 corpus / 366/1,089 L2 files** (`SRF-07_pencil_noncyl_allscopes_presence`: 0.269071 corpus / 0.336088 L2) | frozen 890/0.795 has NO committed generator (§6) |

Scope arithmetic (`scope_stores`, `scope_composite_decode` rows): 1,317/1,442 parts have a located store body — **281 pool-only / 1,036 composite**; the shipped stage-3d identity decode covers **911/1,036 composite stores** (125 raise `undecoded-variant`, fail-closed — the export path's own residue). Patch classification on the decoded scopes (`*_patches_*_volume` rows): pool-only 1,456 patches (1,399 planar, 18 degenerate, 8 cylinder, 2 sphere, 0 cone, 11 pencil-noncyl, 18 curved-unclassified); composite-decoded 66,463 patches (30,931 planar, 775 degenerate, **24,982 cylinder**, 12 cone, **517 sphere**, **5,506 pencil-noncyl**, 3,740 curved-unclassified). The curved content of the corpus lives on the composite stores — pool-only stores are small prismatic parts (0.8% cylinder file presence, `SRF-02_cylinder_poolonly_presence`).

Both scopes are stated separately in every presence claim, and each construct carries an `*_allscopes_presence` row (distinct files with >= 1 patch on either scope) — the note quotes those committed rows, never hand arithmetic.

## 2. The carriers (cited layouts) and the recognition laws

### 2.1 Carriers (cited, not re-derived)

The construct carriers are the facet-strip records of the nested `CATStdCont` store body — the layouts are G3/BR2/composite established:

- Facet record (G3 F1): `01` at `+0x00 (0d)`, marker `mk` at `+0x01 (1d)`, `ty` loop count at `+0x02 (2d)`, form byte `ff` at `+0x03 (3d)`, `u32le n` at `+0x04 (4d)`, the 12-B f32le unit normal at `+0x08 (8d)` on the normal-bearing markers, `ty` count integers at `+0x14 (20d)`, then `n` references (u8 or u16be big-endian, per-record width by the tiling law).
- Strip families: `0x42` and `0x4a` loops are triangle-strip segments — sliding window `(r_t, r_{t+1}, r_{t+2})`, flip on odd t, phase reset per loop (G3 F3/C9; `strip_triangles`). One accepted record = one face patch; its `ty` loops are that patch's segments.
- Index scope: on **pool-only** stores the references are lexicographic ranks of the vertex pool (G3 F2/C8, established). On **composite** stores the references are element indices of the decoded list-node region (stage-3d identity law, `composite.find_list_node` + `decode_region` + `parse_strip_records`; established on the anchors, corpus-candidate — the scope's claims are labeled candidate). Loops referencing skip slots (no coordinates) are counted (`loops_skipref`), never guessed.

### 2.2 The recognition laws (per strip record; all residuals relative to the patch bbox diagonal `scale`)

The recognizer works on the patch's strip triangles: cross-product normals (unit within f32), vertices (which lie ON the tessellated surface). In test order — most-constrained law first:

1. **planar**: the normals are parallel (max chord `||n - mean||` < `SPREAD_MIN` = 0.10): no curved reading.
2. **cylinder (SRF-02)**: the normals share a null direction `a` (pencil, `|n.a| <= K_CYL` = 0.05; `a` = smallest eigenvector of `sum n n^T`) AND a least-squares cylinder with axis `a` fits with max radial residual `<= TOL_PATCH` = 2e-3 x `scale`. The axis point is parametrized in the plane perpendicular to `a` (its axial component is unconstrained — the 4-unknown system is singular; fixture `test_fit_cylinder_recovers_axis_point`). Decoded parameters: axis direction, axis point, radius (fitted; e.g. the synthetic 8.0 recovers exactly). The radius law separates the cylinder from a non-circular extrusion — the pencil alone would admit any ruled surface along `a`.
3. **cone (SRF-03)**: the normals make a CONSTANT angle with a common axis `a` (`|mean(n).a|` in `(K_CYL, K_PLANE)`; `a` = smallest eigenvector of the normal deviations' scatter — for a cone band the deviations are all perpendicular to the axis) AND the radial distances are affine in the axial heights (affine fit residual `<= TOL_PATCH`) AND the fitted `h^2` term explains `<= TOL_PATCH` over the height span (**the quadratic gate**: a torus-fillet band's tube profile is quadratic in `h` — fixture `test_torus_fillet_negative_not_cone_not_sphere`). Decoded parameters: axis direction, apex-side slope `drho/dh` (sign reported, not interpreted), `rho0`. The cone claims a patch BEFORE the sphere (a cone band is locally sphere-like under the Kasa fit; the cone law is more constrained).
4. **sphere (SRF-04)**: a Kasa algebraic sphere fit (points only — the vertices lie on the surface, so the fit is exact-form; `test_sphere_positive_exact_radius` recovers R = 12.0 at residual 0) with max residual `<= TOL_SPHERE` = 5e-4 x `scale` and `R <= R_SCALE_MAX` (10) x `scale`. Decoded parameters: center, radius.
5. **pencil-noncyl**: the pencil holds but the radius law fails — the negative-space signature of a NON-CYLINDRICAL extrusion (an extruded ellipse/slot tessellates exactly so; fixture `test_extruded_ellipse_negative_pencil_noncyl`).
6. **curved-unclassified**: curved patch, no law — the shared ceiling population of SRF-05 torus, SRF-06 non-quadric revolution, SRF-07 extrusion (when the pencil fails) and SRF-08 NURBS tessellation patches.

Calibration: all six fixture families pass in `quadrics.selftest()` (`BR4_selftest` row: 9/9) and in `tests/test_brep_quadrics.py` (14 tests). Corpus coordinates are f32; the laws hold on f32-rounded fixtures (`test_cylinder_positive_f32_coordinates`).

## 3. Per-construct outcomes and rates

Every figure is a claims-CSV row; scopes are `full corpus` (1,442) and `l2-pass` (1,089), all-release pooled.

### SRF-02 Cylinder — decoded (tessellation-level)

- **Volume**: 24,982 cylinder patches on the composite-decoded scope + 8 on pool-only = **24,990** (`poolonly_patches_cylinder_volume`, `composite_patches_cylinder_volume`).
- **Presence**: 696 corpus / 673 L2-pass files on the composite-decoded scope (`SRF-02_cylinder_composite_presence`: 0.482663 corpus, 0.617998 L2); 6 corpus / 6 L2 on pool-only (0.004161 / 0.00551). Both-scope distinct-file row: 702/1,442 = 0.486824 corpus, 679/1,089 = 0.623508 L2 (`SRF-02_cylinder_allscopes_presence`).
- **Census tie-out**: the frozen `SRF-02` row (1,128 corpus / 0.9972 L2) reproduces EXACTLY from the census's strips column — accepted `0x42`/`0x4A` record presence (`S02_census_tieout_corpus`, `S02_census_tieout_l2`). The frozen rate therefore measured STRIP PRESENCE, not cylinders: the tessellation-level cylinder recognition on the decoded scope (0.6235 L2) is the first construct-level SRF-02 measurement, and it is a FLOOR (see §5).

### SRF-03 Cone — decoded (tessellation-level, thin population)

- **Volume**: 12 cone patches (composite-decoded) + 0 (pool-only) on **4 corpus / 4 L2-pass files** (`SRF-03_cone_composite_presence`: 0.002774 corpus / 0.003673 L2).
- The thin population is consistent with the corpus's chamfer/fillet bands being short (few normals, spread under the 0.10 gate) or landing in the ceiling population (§5); the law itself is exact on the synthetic fixture (slope -0.25 recovered at residual 0.028 <= tol 0.069).

### SRF-04 Sphere — decoded (tessellation-level)

- **Volume**: 517 sphere patches (composite-decoded) + 2 (pool-only) = **519**.
- **Presence**: 92 corpus / 81 L2-pass files composite (0.07438 L2) + 1 corpus / 1 L2 pool-only — both-scopes distinct-file row 93/1,442 = 0.064494 corpus, 82/1,089 = 0.075298 L2 (`SRF-04_sphere_allscopes_presence`).

### SRF-05 Torus — documented-open

- No torus discriminator was decoded in this slice. A torus-fillet band fails the cone law through the quadratic gate and the sphere law through the Kasa tolerance (fixture `test_torus_fillet_negative_not_cone_not_sphere`), landing in `curved-unclassified`: **3,758 patches on 129 corpus / 115 L2-pass files** (`SRF-05_06_07_08_curved_unclassified_allscopes_presence`: 0.089459 corpus / 0.105601 L2; composite-scope-only row 0.097337 L2).
- **Ceiling arithmetic**: every torus must present either (a) as curved strip patches — ceiling = the curved-unclassified population above (shared with SRF-06/07/08, see the claim's construct column), or (b) as CGM-side construction records — undecoded in this slice, owned by BR5 (§5, coupling). The frozen 320/0.275 has no committed generator (§6).

### SRF-06 Surface of Revolution — documented-open

- **Superset problem (named)**: a surface of revolution whose generator is a line or circle IS a cylinder, cone or sphere — those patches satisfy the recognized laws and are counted under SRF-02/03/04. A "pure" revolution (general generator) exposes NO separable geometric signature at tessellation level beyond those laws: the rotational structure is the profile sweep itself, which the facet records do not carry. Construction history lives only in the CGM side (BR5's slice).
- **Ceiling arithmetic**: the curved patch population of the decoded scopes = 24,982 + 12 + 517 + 5,506 + 3,740 = **34,757 patches** (composite-decoded) + 39 (pool-only) — any revolution must be inside it; the non-quadric remainder is bounded by the curved-unclassified population (3,758 patches; 115/1,089 = 0.105601 L2 file presence, `SRF-05_06_07_08_curved_unclassified_allscopes_presence`). The frozen 680/0.582 has no committed generator (§6).

### SRF-07 Extruded Surface — candidate (negative-space signature)

- **What is decoded**: the pencil-with-radius-failure signature (`pencil-noncyl`) — the tessellation of a non-cylindrical extrusion (tab-cyl of a non-circular profile): **5,506 patches** (composite-decoded 5,506 + pool-only 11 = 5,517) on **385 corpus / 363 L2-pass files** composite (0.333333 L2) + 3 corpus / 3 L2 pool-only — both-scopes distinct-file row 388/1,442 = 0.269071 corpus, 366/1,089 = 0.336088 L2 (`SRF-07_pencil_noncyl_allscopes_presence`).
- **What stays open**: a circular-profile tab-cyl tessellates EXACTLY like a cylinder (same surface!) — the SRF-02/SRF-07 overlap is a construction-history question, not a geometry question; the tessellation cannot answer it, CGM records (BR5) must. The signature is labeled candidate on the composite scope (the element-index reading is corpus-candidate) and established on the pool-only scope (G3 semantics) — but it is a negative-space reading: it identifies what a patch is NOT (not a cylinder) and infers the extrusion reading.

## 4. Detector honesty (per class)

- **The patch classifier does NOT discriminate construction history**: a tessellated cylinder cannot be told from a tabulated cylinder (SRF-07) or from the cylindrical special case of a revolution (SRF-06) — the surface geometry is identical; only CGM-side records (BR5) could. Fixture: the extruded-ellipse negative (`test_extruded_ellipse_negative_pencil_noncyl`) pins the SRF-02/SRF-07 discriminating edge on the GEOMETRY side (radius law).
- **The pencil test does NOT discriminate the extrusion direction convention** and does not establish which face binds the patch (no face-level grouping: recognition is per accepted strip record).
- **The cone law does NOT discriminate the apex side** (slope sign reported, not interpreted) and does not discriminate a torus-fillet band over a SHORT height span (its quadratic term can sit under the gate threshold — a residual-margin limitation, named; the fixture pins the discriminating edge at the calibrated span).
- **The sphere law does NOT discriminate a spherical cap's side** and cannot separate a small torus region from a sphere at local-patch scale (any smooth patch is locally spherical); the guards are the tight Kasa tolerance (5e-4 x scale — vertices lie exactly on the surface) and the `R <= 10 x scale` sanity. Fixture: the ellipsoid negative (`test_sphere_negative_ellipsoid`).
- **Per-record granularity (floor guarantee)**: a writer splitting one cylinder across records whose individual arcs fall under `SPREAD_MIN` lands them planar — recognized counts are FLOORS, never ceilings. Fixture: `test_plane_strip_negative_planar` pins the spread gate; `test_degenerate_collinear_patch` pins the degenerate rejection.
- **The composite scope is candidate**: the element-index reading of the stage-3d identity law is anchor-established and corpus-candidate (stage-3b battery); all composite-scope claims carry the candidate label in the CSV.
- **The census tie-out does NOT validate the frozen SRF-03..07 split** — it reproduces SRF-02's strip-presence row only; see §6.

All fixtures run in `tests/test_brep_quadrics.py` and via `scripts/triage/decode_brep_quadrics.py --selftest` (0 failures).

## 5. Unknowns / parked (with ceiling arithmetic)

1. **Composite stores the identity decode does not cover**: 125/1,036 raise `undecoded-variant` (fail-closed; `scope_composite_decode` row). Their patches re-enter the claims if BR5 extends the decode; the 911-decoded coverage is the slice's composite ceiling.
2. **CGM construction records** (BR5's slice, coupling stated): the census signature column cites "CGM cylinder/cone/sphere/torus records"; `CGMGeom` carries the exact-model container (GE-V1, entropy 3.6-3.8 bits/byte, undecoded record model). Every construction-history question this slice names (tab-cyl vs cylinder, revolution scope, torus parameters) lands there. BR4 did not re-derive the CGM layout.
3. **Per-record granularity**: the floor guarantee above; record-clustering (merging adjacent strip records of one face) would raise the cylinder/cone/sphere counts and is future work.
4. **The curved-unclassified population** (3,740 patches / 106 L2 files): shared by SRF-05/06/07/08 ceilings; separating torus from NURBS tessellation from short-span fillets needs either CGM records or a torus-specific fit (major-radius circle fit) — future work.
5. **Cone thinness**: 12 patches on 4 files — consistent with short chamfer bands falling under the spread gate or into the ceiling population; the law is exact on its fixture. Not massaged; measured.

## 6. Corrections and drift recorded

1. **2026-11-17 (BR4, this note): frozen-vocabulary generator drift extends to the surface rows.** `brep-construct-vocabulary.csv` (committed at df02b7d) carries per-class `SRF-03..07` rows (542, 412, 320, 680, 890 corpus) that are NOT produced by the committed `census_brep_constructs.py` — the census emits ONE undifferentiated `GEOM_SURF_QUADRIC` class from CGM presence (`S03_07_census_quadric_presence`: 1,435/1,442 corpus = 0.995146, 1,089/1,089 L2 = 1.0), and the individual frozen counts (542/412/320/680/890) have no committed generator. Only `SRF-02`'s frozen row reproduces (`GEOM_SURF_CYLINDER` = strips presence, exact on both scopes). Any consumer of the frozen per-class quadric counts should treat them as unprovenanced until BR5 or a census re-run regenerates them — the BR3 §6.3 pattern, recorded for the surface family.
2. **2026-11-17 (BR4, this note): the frozen `SRF-02` row is a strip-presence rate, not a cylinder rate.** The census's `GEOM_SURF_CYLINDER` detector fires on ANY accepted `0x42`/`0x4A` record — including the planar strip patches that make up 32,330 of the 67,919 classified patches. The first construct-level cylinder measurement is this slice's 0.6235 L2 (decoded-composite scope, floor).

## 7. Reproduction

```bash
export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
.venv/bin/python -I scripts/triage/decode_brep_quadrics.py             # corpus-wide, writes the claims CSV
.venv/bin/python -I scripts/triage/decode_brep_quadrics.py --selftest  # the synthetic fixtures + negatives
.venv/bin/python -I scripts/triage/decode_brep_quadrics.py --files-out /tmp/br4-files.csv   # optional per-file counters
.venv/bin/python -m pytest tests/test_brep_quadrics.py -q              # unit + negative fixtures
```

Runtime ~10 min; stdlib only; deterministic (sorted manifest order); no wall-clock value enters the CSV. Corpus binaries are read READ-ONLY from the main checkout (`resolve_path` against `/home/alan/Documents/Repos/catpart-parser`), never copied into the repo tree, never committed. Version scope of every claims row: all-release pooled ("all"); per-release reruns are reproducible via the script's deterministic order.
