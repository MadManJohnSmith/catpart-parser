# Evidence: BR4 cylindrical / quadric surface recognition — SRF-02..07 (Ticket #56, Spec G #47)

**Date**: 2026-11-17
**Status**: COMPLETE (SRF-02/03/04 decoded at tessellation level; SRF-05/06 documented-open with a measured ceiling; SRF-07 candidate signature; gate green)
**Target Ticket**: Ticket #56 (`BR4: Cylindrical, quadric & analytic surface recognizer`)
**Parent Spec**: Spec G #47 (Phase 7, B-rep / L3 fitness)
**Method**: RE-only corpus-wide recognition over all 1,442 manifest parts (L2-pass join 1,089 files). Recognizer library `src/catpart/brep/quadrics.py`; corpus triage `scripts/triage/decode_brep_quadrics.py` (stdlib, mmap, deterministic, sorted manifest order); per-claim rates in [`br4-quadrics-claims.csv`](data/br4-quadrics-claims.csv) — every prose figure below is a CSV row or a row-derived sum, named in parentheses. Builds on G3's facet model and the stage-3d composite identity decode — their grammars are cited, not re-derived. Byte offsets cite BOTH bases (`+0x08 (8d)` style).

---

## 1. Executive summary

| Construct | Outcome | Recognition rate (this decode) | Census tie-out |
| :--- | :--- | :--- | :--- |
| `SRF-02` Cylindrical Surface | **decoded** (tessellation-level) | **24,990 cylinder strip loops**; **702/1,442 corpus / 679/1,089 L2-pass files** carry >= 1 (`SRF-02_cylinder_allscopes_presence`: 0.486824 corpus / `SRF-02_cylinder_allscopes_presence_l2`: 0.623508 L2) | frozen row reproduced EXACTLY from the census strips column (`S02_census_tieout_corpus`: 1,128/1,442 = 0.782247; `S02_census_tieout_l2`: 1,086/1,089 = 0.997245) — but it measured STRIP PRESENCE, not cylinders |
| `SRF-03` Conical Surface | **decoded** (tessellation-level, thin population) | **12 cone strip loops / 4 files** (`SRF-03_cone_composite_presence`: 0.002774 corpus / `SRF-03_cone_composite_presence_l2`: 0.003673 L2, composite identity-decoded scope); 0 on pool-only | frozen 542/0.465 has NO committed generator (§6) |
| `SRF-04` Spherical Surface | **decoded** (tessellation-level, floor) | **519 sphere strip loops**; **93/1,442 corpus / 82/1,089 L2 files** (`SRF-04_sphere_allscopes_presence`: 0.064494 corpus / `SRF-04_sphere_allscopes_presence_l2`: 0.075298 L2) | frozen 412/0.354 has NO committed generator (§6) |
| `SRF-05` Toroidal Surface | **documented-open** | ceiling **4,289 strip loops**; **168/1,442 corpus / 153/1,089 L2 files** (`SRF-05_ceiling_patches`, `SRF-05_ceiling_allscopes_presence`: 0.116505 corpus / `SRF-05_ceiling_allscopes_presence_l2`: 0.140496 L2) | frozen 320/0.275 has NO committed generator (§6) |
| `SRF-06` Surface of Revolution | **documented-open** | same ceiling as SRF-05 (superset problem: cylinder/cone/sphere ARE revolutions; construction history is not in the tessellation) | frozen 680/0.582 has NO committed generator (§6) |
| `SRF-07` Extruded Surface | **candidate** (negative-space signature) | **5,517 pencil-noncyl strip loops**; **388/1,442 corpus / 366/1,089 L2 files** (`SRF-07_pencil_noncyl_allscopes_presence`: 0.269071 corpus / `SRF-07_pencil_noncyl_allscopes_presence_l2`: 0.336088 L2) | frozen 890/0.795 has NO committed generator (§6) |

Scope arithmetic (`scope_stores`: 1,317/1,442 = 0.913315 parts have a located store body — **281 pool-only / 1,036 composite**). Two composite numbers, kept apart:

- **BR4's classification scope**: the identity table-walk reading (`find_list_node` + `decode_region`) covers **911/1,036 composite stores** (`scope_composite_decode`: 0.879344). The classified composite volumes below cover THESE stores only.
- **The shipped stage-3d export**: cross-tabulated against `stage15-identity-export-files.csv`, it covers **1,020/1,036** (`scope_composite_decode_shipped`: 0.984556) — the identity reading's 911 minus 1 identity-decoded store the shipped path rejects, plus 110 stores only the shipped fallback laws export (`identity-mixedwrite-reps` 82, `identity-raw-array` 28). **15** stores stay undecoded by both (`scope_composite_decode_gap`).

Unit: one counted recognition is one `ty` strip loop of an accepted `0x42`/`0x4a` record (a strip segment, G3 phase reset) — a record whose `ty` count exceeds 1 contributes that many units (`*_volume` rows state the same in their notes). Volumes (`*_patches_*_volume` rows): pool-only 1,456 loops (1,399 planar, 18 degenerate, 8 cylinder, 2 sphere, 0 cone, 11 pencil-noncyl, 18 curved-unclassified); composite identity-decoded 66,463 loops (30,931 planar, 775 degenerate, **24,982 cylinder**, 12 cone, **517 sphere**, **5,506 pencil-noncyl**, 3,740 curved-unclassified). The curved content of the corpus lives on the composite stores — pool-only stores are small prismatic parts (6/1,442 = 0.004161 corpus, 6/1,089 = 0.00551 L2 cylinder file presence, `SRF-02_cylinder_poolonly_presence`).

Loops the recognizer never saw (composite identity-decoded scope): **78,255 skip-reference loops** over 637 files (`composite_loops_skipref_volume`) and **12,196 beyond-element-space loops** over 59 files (`composite_loops_oob_volume`) — **90,451 of 156,914 loops = 0.576437 excluded** (`composite_loops_excluded_share`). They are cap-raisers of every composite ceiling in this note (§3, §5), never guesses.

Both scopes are stated separately in every presence claim, and each construct carries an `*_allscopes_presence` row (distinct files with >= 1 loop on either scope; the L2 row carries the `_l2` suffix) — the note quotes committed rows, never hand arithmetic.

## 2. The carriers (cited layouts) and the recognition laws

### 2.1 Carriers (cited, not re-derived)

The construct carriers are the facet-strip records of the nested `CATStdCont` store body — the layouts are G3/BR2/composite established:

- Facet record header (G3 F1): `01` at `+0x00 (0d)`, marker `mk` at `+0x01 (1d)`, `ty` loop count at `+0x02 (2d)`, form byte `ff` at `+0x03 (3d)`, `u32le n` at `+0x04 (4d)` on the 4-byte form. The normal is **not** universal: `facets.NORMAL_MARKERS_ALL = 0x49/0x4a/0x4b/0x4c/0x4e` carry the 12-B f32le unit normal — **`0x42` does not**. The two strip families therefore split:

  - **`0x4a`** (normal-bearing): normal at `+0x08 (8d)` .. `+0x13 (19d)`, `ty` count integers at `+0x14 (20d)`, then `n` references.
  - **`0x42`** (no normal — the DOMINANT strip family, 61,554 of 98,919 strip records, the four `*_strip_records_*_volume` rows): no normal block, first `ty` count at `+0x08 (8d)`, then `n` references.
  - **5-byte header form** (byte at `+0x03 (3d)` is not `0xff`): every following offset shifts +1 — `n` at `+0x05 (5d)`, `ty` counts at `+0x09 (9d)` on `0x42`; on the normal-bearing markers the same +1 shift puts the counts at `+0x15 (21d)` (`facets.parse_facet_record`'s `base = o + header_len + 4 + 12`). Measured incidence among strip records in this slice: 0 (`strip_records_5byte_volume`).

  References are `u8` or `u16be` big-endian, per-record width by the tiling law.
- Strip families: `0x42` and `0x4a` loops are triangle-strip segments — sliding window `(r_t, r_{t+1}, r_{t+2})`, flip on odd t, phase reset per loop (G3 F3/C9; `strip_triangles`). One accepted record = one face patch; its `ty` loops are that patch's strip segments and the recognition unit of this slice.
- Index scope: on **pool-only** stores the references are lexicographic ranks of the vertex pool (G3 F2/C8, established). On **composite** stores the references are element indices of the decoded list-node region (stage-3d identity law, `composite.find_list_node` + `decode_region` + `parse_strip_records`; established on the anchors, corpus-candidate — the scope's claims are labeled candidate). Loops referencing skip slots (no coordinates) are counted (`composite_loops_skipref_volume`, `loops_skipref` per file) and loops leaving the element space are counted (`composite_loops_oob_volume`, `loops_oob`); neither is guessed.

### 2.2 The recognition laws (per `ty` strip loop; all residuals relative to the patch bbox diagonal `scale`)

The recognizer works on the loop's strip triangles: cross-product normals (unit within f32), vertices (which lie ON the tessellated surface). Actual test order — the **pencil branch returns**, so the cone and sphere laws are only reached by non-pencil patches:

1. **planar**: the normals are parallel (max chord `||n - mean||` < `SPREAD_MIN` = 0.10): no curved reading.
2. **pencil branch — cylinder (SRF-02) or pencil-noncyl (SRF-07)**: the normals share a null direction `a` (`|n.a| <= K_CYL` = 0.05; `a` = smallest eigenvector of `sum n n^T`). If a least-squares cylinder with axis `a` fits with max radial residual `<= TOL_PATCH` = 2e-3 x `scale`, the loop is a cylinder; otherwise it is `pencil-noncyl` (a non-circular extrusion). The axis point is parametrized in the plane perpendicular to `a` (its axial component is unconstrained — the 4-unknown system is singular; fixture `test_fit_cylinder_recovers_axis_point`). Decoded parameters: axis direction, axis point, radius. The radius law separates the cylinder from a non-circular extrusion — the pencil alone would admit any ruled surface along `a`.
3. **cone (SRF-03)**: the normals make a CONSTANT angle with a common axis `a` (`|mean(n).a|` in `(K_CYL, K_PLANE)`; `a` = smallest eigenvector of the normal deviations' scatter — for a cone band the deviations are all perpendicular to the axis) AND the radial distances are affine in the axial heights (affine fit residual `<= TOL_PATCH`) AND the fitted `h^2` term explains `<= TOL_PATCH` over the height span (**the quadratic gate**: a torus-fillet band's tube profile is quadratic in `h` — fixture `test_torus_fillet_negative_not_cone_not_sphere`). Decoded parameters: axis direction, apex-side slope `drho/dh` (sign reported, not interpreted), `rho0`.
4. **sphere (SRF-04)**: a Kasa algebraic sphere fit (points only — the vertices lie on the surface, so the fit is exact-form; `test_sphere_positive_exact_radius` recovers R = 12.0 at residual 0) with max residual `<= TOL_SPHERE` = 5e-4 x `scale` and `R <= R_SCALE_MAX` (10) x `scale`. Decoded parameters: center, radius.
5. **curved-unclassified**: curved loop, no law — the shared ceiling population of SRF-05 torus, SRF-06 non-quadric revolution, SRF-07 extrusion (when the pencil fails) and SRF-08 NURBS tessellation patches.

**Why the cone law precedes the sphere law** — precedence, not constraint: over a short span the two laws are MUTUALLY satisfiable, measured on both fixtures. A true sphere band (R 12.0, lats 1.30/1.25/1.20 rad) satisfies the cone gates and is labeled cone (`test_sphere_short_span_lands_cone`: residual 8.7e-3 <= tol 6.5e-2, quadratic term 6.3e-2 <= tol); a short cone band satisfies the Kasa sphere fit (`test_cone_short_span_satisfies_sphere_law`). Precedence decides the label, so the sphere count is a floor and short sphere-shaped spans are counted under SRF-03.

Calibration: all 14 fixture cases pass in `quadrics.selftest()` (`BR4_selftest` row: 14/14, the count derived from the case list) and in `tests/test_brep_quadrics.py` (17 tests). Corpus coordinates are f32; the laws hold on f32-rounded fixtures (`test_cylinder_positive_f32_coordinates`).

## 3. Per-construct outcomes and rates

Every figure is a claims-CSV row; scopes are `full corpus` (1,442) and `l2-pass` (1,089), all-release pooled.

### SRF-02 Cylinder — decoded (tessellation-level)

- **Volume**: 24,982 cylinder loops on the composite identity-decoded scope + 8 on pool-only = **24,990** (`composite_patches_cylinder_volume`, `poolonly_patches_cylinder_volume`).
- **Presence**: 696 corpus / 673 L2-pass files on the composite scope (`SRF-02_cylinder_composite_presence`: 0.482663 corpus, `SRF-02_cylinder_composite_presence_l2`: 0.617998 L2); 6 corpus / 6 L2 on pool-only (0.004161 / 0.00551). Both-scope distinct-file row: 702/1,442 = 0.486824 corpus, 679/1,089 = 0.623508 L2 (`SRF-02_cylinder_allscopes_presence`, `SRF-02_cylinder_allscopes_presence_l2`).
- **Census tie-out**: the frozen `SRF-02` row (1,128 corpus / 0.9972 L2) reproduces EXACTLY from the census's strips column — accepted `0x42`/`0x4A` record presence (`S02_census_tieout_corpus`, `S02_census_tieout_l2`). The frozen rate therefore measured STRIP PRESENCE, not cylinders: the composite-scope construct-level measurement (0.617998 L2) is the first SRF-02 measurement, and it is a FLOOR (see §5).
- The pool-only scope is small prismatic stock (0.004161 corpus / 0.00551 L2 cylinder file presence) — no broad claim is made from it.

### SRF-03 Cone — decoded (tessellation-level, thin population)

- **Volume**: 12 cone loops (composite identity-decoded) + 0 (pool-only) on **4 corpus / 4 L2-pass files** (`SRF-03_cone_composite_presence`: 0.002774 corpus / `SRF-03_cone_composite_presence_l2`: 0.003673 L2).
- The thin population is consistent with the corpus's chamfer/fillet bands being short (few normals, spread under the 0.10 gate) or landing in the ceiling population (§5); the law itself is exact on the synthetic fixture (slope -0.25 recovered at residual 0.028 <= tol 0.069). Note the same span effect works the other way: a short sphere band lands HERE (§2.2), so the 12 absorb an unknown share of sphere-shaped short spans.

### SRF-04 Sphere — decoded (tessellation-level, floor)

- **Volume**: 517 sphere loops (composite identity-decoded) + 2 (pool-only) = **519** (`composite_patches_sphere_volume`, `poolonly_patches_sphere_volume`).
- **Presence**: 92 corpus / 81 L2-pass files composite (0.0638 corpus, `SRF-04_sphere_composite_presence_l2`: 0.07438 L2) + 1 corpus / 1 L2 pool-only — both-scopes distinct-file row 93/1,442 = 0.064494 corpus, 82/1,089 = 0.075298 L2 (`SRF-04_sphere_allscopes_presence`, `_l2`).
- **Floor, not ceiling**: short-span sphere bands are labeled cone (§2.2), and a short torus band satisfies the sphere law (`test_torus_short_span_cap_raisers`, `torus_short_span_sphere` inside `BR4_selftest`) — both directions leak.

### SRF-05 Torus — documented-open (measured ceiling)

- No torus discriminator was decoded in this slice. A torus-fillet band over the calibrated span fails the cone law through the quadratic gate and the sphere law through the Kasa tolerance (fixture `test_torus_fillet_negative_not_cone_not_sphere`), landing in `curved-unclassified`: **3,758 loops on 129 corpus / 115 L2-pass files** (`SRF-05_06_07_08_curved_unclassified_allscopes_presence`: 0.089459 corpus / `_l2`: 0.105601; composite-scope-only row `SRF-05_06_07_08_curved_unclassified_composite_presence_l2`: 0.097337).
- **Ceiling arithmetic — the ceiling includes the cone and sphere classes, because a SHORT torus band does not stay in `curved-unclassified`**: a 0.2 rad span lands in cone and a 0.3 rad span lands in sphere (`test_torus_short_span_cap_raisers`; both cases in `BR4_selftest`). So every torus must present as (a) a **cone, sphere or curved-unclassified strip loop** — ceiling = 12 (cone) + 519 (sphere) + 3,758 (curved-unclassified) = **4,289 loops** (`SRF-05_ceiling_patches`), on **168/1,442 = 0.116505 corpus / 153/1,089 = 0.140496 L2 files** (`SRF-05_ceiling_allscopes_presence`, `_l2`) — or (b) as CGM-side construction records, undecoded in this slice and owned by BR5 (§5). Both branches are cap-raisers: the 90,451 excluded composite loops (0.576437, §1) and the 110 shipped-fallback-only stores are outside every count here. The frozen 320/0.275 has no committed generator (§6).

### SRF-06 Surface of Revolution — documented-open

- **Superset problem (named)**: a surface of revolution whose generator is a line or circle IS a cylinder, cone or sphere — those loops satisfy the recognized laws and are counted under SRF-02/03/04. A "pure" revolution (general generator) exposes NO separable geometric signature at tessellation level beyond those laws: the rotational structure is the profile sweep itself, which the facet records do not carry. Construction history lives only in the CGM side (BR5's slice).
- **Ceiling arithmetic**: the curved loop population of the decoded scopes = 24,982 + 12 + 517 + 5,506 + 3,740 = **34,757 loops** (composite identity-decoded) + 39 (pool-only: 8 + 2 + 0 + 11 + 18) — any revolution must be inside it (`composite_patches_*_volume` + `poolonly_patches_*_volume` sums); the non-quadric remainder is bounded by the SRF-05 ceiling population (4,289 loops, 168/153 files). The frozen 680/0.582 has no committed generator (§6).

### SRF-07 Extruded Surface — candidate (negative-space signature)

- **What is decoded**: the pencil-with-radius-failure signature (`pencil-noncyl`) — the tessellation of a non-cylindrical extrusion (tab-cyl of a non-circular profile): **5,506 loops** composite + 11 pool-only = **5,517** (`composite_patches_pencil_noncyl_volume`, `poolonly_patches_pencil_noncyl_volume`) on **385 corpus / 363 L2-pass files** composite (`SRF-07_pencil_noncyl_composite_presence`: 0.26699 corpus / `_l2`: 0.333333) + 3 corpus / 3 L2 pool-only — both-scopes distinct-file row 388/1,442 = 0.269071 corpus, 366/1,089 = 0.336088 L2 (`SRF-07_pencil_noncyl_allscopes_presence`, `_l2`).
- **What stays open**: a circular-profile tab-cyl tessellates EXACTLY like a cylinder (same surface!) — the SRF-02/SRF-07 overlap is a construction-history question, not a geometry question; the tessellation cannot answer it, CGM records (BR5) must. The signature is labeled candidate on the composite scope (the element-index reading is corpus-candidate) and established on the pool-only scope (G3 semantics) — but it is a negative-space reading: it identifies what a loop is NOT (not a cylinder) and infers the extrusion reading.

## 4. Detector honesty (per class)

- **The patch classifier does NOT discriminate construction history**: a tessellated cylinder cannot be told from a tabulated cylinder (SRF-07) or from the cylindrical special case of a revolution (SRF-06) — the surface geometry is identical; only CGM-side records (BR5) could. Fixture: the extruded-ellipse negative (`test_extruded_ellipse_negative_pencil_noncyl`) pins the SRF-02/SRF-07 discriminating edge on the GEOMETRY side (radius law).
- **The pencil test does NOT discriminate the extrusion direction convention** and does not establish which face binds the loop (no face-level grouping: recognition is per `ty` strip loop).
- **The cone law does NOT discriminate the apex side** (slope sign reported, not interpreted), does NOT discriminate a torus-fillet band over a short height span (its quadratic term can sit under the gate threshold — a residual-margin limitation, named), and does NOT discriminate a sphere band over a short meridional span — which it ABSORBS by precedence (`test_sphere_short_span_lands_cone`). Fixture: the calibrated torus-fillet negative pins the edge at the calibrated span.
- **The sphere law does NOT discriminate a spherical cap's side** and cannot separate a small torus region from a sphere at local-patch scale (any smooth patch is locally spherical); the guards are the tight Kasa tolerance (5e-4 x scale — vertices lie exactly on the surface) and the `R <= 10 x scale` sanity. Fixture: the ellipsoid negative (`test_sphere_negative_ellipsoid`) pins the distance law; `test_torus_short_span_cap_raisers` pins the leak.
- **Per-loop granularity (floor guarantee)**: a writer splitting one cylinder across `ty` loops whose individual arcs fall under `SPREAD_MIN` lands them planar — recognized counts are FLOORS, never ceilings. Fixture: `test_plane_strip_negative_planar` pins the spread gate; `test_degenerate_collinear_patch` pins the degenerate rejection.
- **The composite scope is candidate and identity-only**: the element-index reading of the stage-3d identity law is anchor-established and corpus-candidate (stage-3b battery); all composite-scope claims carry the candidate label in the CSV. The classifier runs the identity table-walk ONLY — the shipped export's raw-array / per-rep / mixed-write fallbacks are not run and its refs-beyond gate is computed locally, so 110 stores the shipped path exports are outside the classified volumes (`scope_composite_decode_shipped`, `scope_composite_decode_gap`).
- **The census tie-out does NOT validate the frozen SRF-03..07 split** — it reproduces SRF-02's strip-presence row only; see §6.

All fixtures run in `tests/test_brep_quadrics.py` (17 tests) and via `scripts/triage/decode_brep_quadrics.py --selftest` (14/14 cases, 0 failures).

## 5. Unknowns / parked (with ceiling arithmetic)

1. **The shipped-vs-identity composite gap**: identity reading 911/1,036 (`scope_composite_decode`) vs shipped export 1,020/1,036 (`scope_composite_decode_shipped`); 110 stores are exported only by the shipped fallback laws (82 `identity-mixedwrite-reps`, 28 `identity-raw-array`), 15 stay undecoded by both (`scope_composite_decode_gap`), and 1 identity-decoded store is a shipped `undecoded-variant`. Running the shipped path per store (rather than the identity reading) is the route to folding that residue into the classified volumes — future work, and it would raise every composite count.
2. **Excluded composite loops**: 78,255 skip-reference loops (637 files) + 12,196 beyond-element-space loops (59 files) = 90,451 of 156,914 = 0.576437 (`composite_loops_skipref_volume`, `composite_loops_oob_volume`, `composite_loops_excluded_share`). A cap-raiser of every composite ceiling in §3; recovering them needs a skip-slot coordinate law, not a looser recognizer.
3. **CGM construction records** (BR5's slice, coupling stated): the census signature column cites "CGM cylinder/cone/sphere/torus records"; `CGMGeom` carries the exact-model container (GE-V1, entropy 3.6-3.8 bits/byte, undecoded record model). Every construction-history question this slice names (tab-cyl vs cylinder, revolution scope, torus parameters) lands there. BR4 did not re-derive the CGM layout.
4. **Per-loop granularity**: the floor guarantee above; record/loop clustering (merging adjacent strip loops of one face) would raise the cylinder/cone/sphere counts and is future work.
5. **The curved-unclassified population** (3,740 composite loops / 106 L2 files, `SRF-05_06_07_08_curved_unclassified_composite_presence_l2`: 0.097337): shared by SRF-05/06/07/08 ceilings; separating torus from NURBS tessellation from short-span fillets needs either CGM records or a torus-specific fit (major-radius circle fit) — future work. The cone-absorbs-sphere edge (§2.2) also has to be handled by that fit, not by tightening TOL_PATCH alone.
6. **Cone thinness**: 12 loops on 4 files — consistent with short chamfer bands falling under the spread gate or into the ceiling population; the law is exact on its fixture. Not massaged; measured.

## 6. Corrections and drift recorded

1. **2026-11-17 (BR4, this note): frozen-vocabulary generator drift extends to the surface rows.** `brep-construct-vocabulary.csv` (committed at df02b7d) carries per-class `SRF-03..07` rows (542, 412, 320, 680, 890 corpus) that are NOT produced by the committed `census_brep_constructs.py` — the census emits ONE undifferentiated `GEOM_SURF_QUADRIC` class from CGM presence (`S03_07_census_quadric_presence`: 1,435/1,442 corpus = 0.995146, 1,089/1,089 L2 = 1.0), and the individual frozen counts (542/412/320/680/890) have no committed generator. Only `SRF-02`'s frozen row reproduces (`GEOM_SURF_CYLINDER` = strips presence, exact on both scopes). Any consumer of the frozen per-class quadric counts should treat them as unprovenanced until BR5 or a census re-run regenerates them — the BR3 §6.3 pattern, recorded for the surface family.
2. **2026-11-17 (BR4, this note): the frozen `SRF-02` row is a strip-presence rate, not a cylinder rate.** The census's `GEOM_SURF_CYLINDER` detector fires on ANY accepted `0x42`/`0x4A` record — including the planar strip loops that make up 32,330 of the 67,919 classified loops (`*_patches_planar_volume` / `*_patches_*_volume` rows). The first construct-level cylinder measurement is this slice's composite-scope 0.617998 L2 (`SRF-02_cylinder_composite_presence_l2`, floor).
3. **2026-11-17 (BR4 review correction, this note): the 125 identity-undecoded composite stores are NOT "the export path's own residue".** The earlier draft read the identity classifier's `undecoded-variant` count as shipped-path failures. The stage15 cross-tabulation measures the opposite for 110 of them: the shipped export succeeds through the fallback laws (`scope_composite_decode_shipped`), so the residue belongs to BR4's identity-only classifier, not to the export path. Restated in §1/§5 with three committed rows (`scope_composite_decode`, `scope_composite_decode_shipped`, `scope_composite_decode_gap`); the classified composite volumes are the 911-store subset and are labeled as such in every composite row.

## 7. Reproduction

```bash
export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
.venv/bin/python -I scripts/triage/decode_brep_quadrics.py             # corpus-wide, writes the claims CSV
.venv/bin/python -I scripts/triage/decode_brep_quadrics.py --selftest  # the synthetic fixtures + negatives
.venv/bin/python -I scripts/triage/decode_brep_quadrics.py --files-out /tmp/br4-files.csv   # optional per-file counters
.venv/bin/python -I scripts/triage/decode_brep_quadrics.py --include-sha16 369fc90b25b4977d --out-dir /tmp/br4-anchor
.venv/bin/python -m pytest tests/test_brep_quadrics.py -q              # unit + negative fixtures
```

The default run writes ONLY the claims CSV (the per-file counter table needs `--files-out PATH`); `--include-sha16` prefix-matches the full supplied digest prefix, aborts non-zero on an empty selection, and refuses to write a subset into the committed data dir. Runtime measured at 79 s for all 1,442 parts on this host; stdlib only; deterministic (sorted manifest order) — regenerating the claims CSV reproduces it byte-for-byte (no wall-clock value enters it). Corpus binaries are read READ-ONLY from the main checkout (`resolve_path` against `/home/alan/Documents/Repos/catpart-parser`), never copied into the repo tree, never committed. Version scope of every claims row: all-release pooled ("all"); per-release reruns are reproducible via the script's deterministic order.
